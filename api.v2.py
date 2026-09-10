"""
RagGita FastAPI Server
A compassionate spiritual guide API based on Bhagavad Gita wisdom.

v2 changes:
  - Short, gentle replies (see rag_core/prompts.py)
  - Dynamic prompting per user class (see rag_core/gita_map.py)
  - Crisis safety guard before any LLM call
  - GET  /classes  -> UI ke liye class list
  - POST /tts      -> OpenAI text-to-speech (voice replies)
"""
import os
import sys
import logging
import json
import asyncio
from functools import lru_cache
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_community.vectorstores import FAISS

try:
    from langchain_huggingface import HuggingFaceEndpointEmbeddings
except ImportError:
    HuggingFaceEndpointEmbeddings = None

from langchain_huggingface import HuggingFaceEmbeddings
from rag_core.config import LightRAGConfig, get_llm
from rag_core.streaming import TokenQueueCallbackHandler
from rag_core.prompts import build_prompt, get_prompt_template, is_crisis, CRISIS_REPLY
from rag_core.gita_map import public_classes

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global references
embedding_model = None
db = None
retriever = None
llm = None
prompt_template = None


def _llm_ping() -> bool:
    """Quickly check whether the configured OpenAI-compatible LLM endpoint is reachable.

    Returns True if reachable (or no external base configured), False otherwise.
    """
    base = os.getenv("OPENAI_API_BASE", "").strip()
    if not base:
        return True

    test_paths = ["/models", "/v1/models", ""]
    for p in test_paths:
        url = base.rstrip("/") + p
        try:
            r = requests.get(url, timeout=2)
            if r.status_code < 500:
                return True
        except Exception:
            continue
    return False


def _clamp_top_k(k: int) -> int:
    # For fast TTFT, keep context small.
    return max(1, min(5, int(k)))


def _truncate_context(text: str) -> str:
    max_context_chars = int(os.getenv("MAX_CONTEXT_CHARS", "2500"))
    if max_context_chars > 0 and len(text) > max_context_chars:
        return text[:max_context_chars] + "\n\n[...context truncated...]"
    return text


@lru_cache(maxsize=512)
def _cached_query_embedding(query: str) -> tuple:
    """LRU cache for query embeddings (per-process memory cache)."""
    if embedding_model is None:
        raise RuntimeError("Embedding model not loaded")
    return tuple(embedding_model.embed_query(query))


def _retrieve_docs_faiss(question: str, k: int):
    """Retrieve top-k docs from FAISS using cached query embeddings."""
    if db is None:
        raise RuntimeError("Vector DB not loaded")
    k = _clamp_top_k(k)
    vector = list(_cached_query_embedding(question))
    return db.similarity_search_by_vector(vector, k=k)


def _docs_to_context(docs) -> str:
    return _truncate_context("\n\n".join([d.page_content for d in docs]))


def _sse(event, data) -> bytes:
    """Encode a Server-Sent Event payload."""
    payload = json.dumps(data, ensure_ascii=False)
    if event:
        return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
    return f"data: {payload}\n\n".encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - load models on startup"""
    global embedding_model, db, retriever, llm, prompt_template

    logger.info("Loading RagGita models...")

    try:
        # 1. Load embeddings
        logger.info("Loading embeddings model...")
        use_remote = os.getenv("USE_REMOTE_EMBEDDINGS", "true").strip().lower() in ("1", "true", "yes", "y")
        hf_token = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_HUB_TOKEN", "")).strip()

        if use_remote and HuggingFaceEndpointEmbeddings is not None:
            logger.info("Using HuggingFace Inference API embeddings (low memory)")
            endpoint_kwargs = {"model": "sentence-transformers/all-MiniLM-L6-v2"}
            if hf_token:
                endpoint_kwargs["huggingfacehub_api_token"] = hf_token
            embedding_model = HuggingFaceEndpointEmbeddings(**endpoint_kwargs)
        else:
            logger.info("Using local HuggingFace embeddings (all-MiniLM-L6-v2)")
            embedding_model = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )

        # 2. Load vector DB
        logger.info("Loading FAISS vector database...")
        db = FAISS.load_local(
            "gita_vector_db",
            embedding_model,
            allow_dangerous_deserialization=True
        )
        retriever = db.as_retriever(search_kwargs={"k": 4})

        # 3. Initialize LLM
        logger.info("Initializing LLM...")
        config = LightRAGConfig()
        llm = get_llm(config)

        # 4. Default prompt (streaming endpoint uses this; /chat builds per-request)
        prompt_template = get_prompt_template("auto")

        logger.info("RagGita API is ready!")

    except Exception:
        logger.exception("Failed to load models")
        raise

    yield

    logger.info("Shutting down RagGita API...")


# Create FastAPI app
app = FastAPI(
    title="RagGita API",
    description="A compassionate spiritual guide API based on Bhagavad Gita wisdom",
    version="2.0.0",
    lifespan=lifespan
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")


# ======================
# Pydantic Models
# ======================

class ChatRequest(BaseModel):
    """Chat request model"""
    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The user's question or message"
    )
    user_class: str = Field(
        default="auto",
        max_length=32,
        description="Emotional context: low, anxious, grief, lonely, angry, lost, seeking, or auto"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "question": "I'm feeling anxious about my future.",
                "user_class": "anxious"
            }
        }


class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str = Field(..., description="The AI-generated response")
    sources: list = Field(default=[], description="Source documents used")
    user_class: str = Field(default="auto", description="Class actually used for this reply")
    crisis: bool = Field(default=False, description="True if the safety guard handled this message")


class TTSRequest(BaseModel):
    """Text-to-speech request"""
    text: str = Field(..., min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    version: str = "2.0.0"


# ======================
# API Endpoints
# ======================

@app.get("/", include_in_schema=False)
def root():
    """Serve the HTML frontend"""
    return FileResponse("static/index.html")


@app.get("/api", response_model=HealthResponse)
def api_info():
    """API info endpoint"""
    return HealthResponse(
        status="ok",
        message="RagGita API is running. Visit /docs for API documentation.",
        version="2.0.0"
    )


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for monitoring"""
    global retriever
    if llm is None or retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded"
        )
    return HealthResponse(
        status="healthy",
        message="All systems operational",
        version="2.0.0"
    )


@app.get("/classes")
def list_classes():
    """Available user classes, for the frontend selector."""
    return {"classes": public_classes(), "tts_enabled": _tts_enabled()}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """Chat with the Gita RAG bot.

    Send a question (and optionally a user_class) and receive a short,
    compassionate reply grounded in the Bhagavad Gita.
    """
    global llm, retriever

    if llm is None or retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    try:
        # Safety first — self-harm signal pe verse nahi, help chahiye
        if is_crisis(request.question):
            logger.info("Crisis guard triggered; returning helpline response.")
            return ChatResponse(
                answer=CRISIS_REPLY,
                sources=[],
                user_class="crisis",
                crisis=True,
            )

        # Retrieve relevant context
        docs = retriever.invoke(request.question)
        context = _truncate_context("\n\n".join([d.page_content for d in docs]))

        # Dynamic prompt for this person's class
        prompt, resolved_class = build_prompt(request.question, request.user_class)
        chain = prompt | llm

        answer = chain.invoke({
            "context": context,
            "question": request.question
        })

        return ChatResponse(
            answer=answer.content,
            sources=[],
            user_class=resolved_class,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in chat endpoint")

        err_str = str(e).lower()
        if "connection error" in err_str or isinstance(e, requests.RequestException):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "LLM backend connection failed. "
                    "Check OPENAI_API_BASE, network connectivity, and API key."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the response."
        )


@app.post("/ask", response_model=ChatResponse)
def ask_endpoint(request: ChatRequest):
    """Alias for /chat endpoint"""
    return chat_endpoint(request)


@app.post("/chat_fast", response_model=ChatResponse)
def chat_fast_endpoint(request: ChatRequest):
    """Faster non-streaming endpoint (cached embeddings, fewer chunks)."""
    global llm

    if llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    try:
        if is_crisis(request.question):
            logger.info("Crisis guard triggered; returning helpline response.")
            return ChatResponse(
                answer=CRISIS_REPLY,
                sources=[],
                user_class="crisis",
                crisis=True,
            )

        k = int(os.getenv("FAST_TOP_K", "3"))
        docs = _retrieve_docs_faiss(request.question, k=k)
        context = _docs_to_context(docs)

        prompt, resolved_class = build_prompt(request.question, request.user_class)
        chain = prompt | llm

        answer = chain.invoke({
            "context": context,
            "question": request.question
        })

        return ChatResponse(
            answer=answer.content,
            sources=[],
            user_class=resolved_class,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error in chat_fast endpoint")
        err_str = str(e).lower()
        if "connection error" in err_str or isinstance(e, requests.RequestException):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "LLM backend connection failed. "
                    "Check OPENAI_API_BASE, network connectivity, and API key."
                ),
            )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred while generating the response."
        )


@app.get("/chat/stream")
async def chat_stream_endpoint(
    request: Request,
    question: str,
    k: int = 3,
    user_class: str = "auto",
):
    """Stream tokens using Server-Sent Events (SSE)."""
    global embedding_model, db

    if embedding_model is None or db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet."
        )

    if is_crisis(question):
        async def crisis_gen():
            yield _sse("meta", {"status": "crisis"})
            yield _sse(None, {"token": CRISIS_REPLY})
            yield _sse("done", {"ok": True})
        return StreamingResponse(crisis_gen(), media_type="text/event-stream")

    k = _clamp_top_k(k)

    async def event_generator():
        yield _sse("meta", {"status": "starting", "k": k})

        try:
            docs = await asyncio.to_thread(_retrieve_docs_faiss, question, k)
            context = _docs_to_context(docs)
        except Exception as e:
            yield _sse("error", {"message": f"retrieval_failed: {str(e)}"})
            return

        handler = TokenQueueCallbackHandler()
        config = LightRAGConfig()
        if config.use_bytez:
            yield _sse(
                "error",
                {
                    "message": "streaming_not_supported_for_bytez",
                    "hint": "Set USE_BYTEZ=false to stream via an OpenAI-compatible backend."
                },
            )
            return

        stream_prompt, _resolved = build_prompt(question, user_class)
        stream_llm = get_llm(config, streaming=True, callbacks=[handler])
        stream_chain = stream_prompt | stream_llm

        async def run_generation():
            try:
                await stream_chain.ainvoke({"context": context, "question": question})
            finally:
                await handler.finish()

        task = asyncio.create_task(run_generation())

        try:
            yield _sse("meta", {"status": "generating"})
            async for token in handler.aiter_tokens(timeout_s=15.0):
                if await request.is_disconnected():
                    break

                if token is None:
                    yield b": ping\n\n"
                    continue

                yield _sse(None, {"token": token})
        except Exception as e:
            yield _sse("error", {"message": f"generation_failed: {str(e)}"})
        finally:
            if not task.done():
                task.cancel()
            yield _sse("done", {"ok": True})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ======================
# Text to Speech
# ======================

def _tts_enabled() -> bool:
    return (
        os.getenv("ENABLE_TTS", "true").strip().lower() in ("1", "true", "yes", "y")
        and bool(os.getenv("OPENAI_API_KEY", "").strip())
    )


# Yeh instructions gpt-4o-mini-tts ko tone batate hain.
_TTS_INSTRUCTIONS = os.getenv(
    "TTS_INSTRUCTIONS",
    "Speak slowly and softly, like someone sitting beside a tired friend late at night. "
    "Warm and steady, never bright or performative. Leave small pauses between sentences.",
)


@app.post("/tts")
def tts_endpoint(payload: TTSRequest):
    """Convert a reply to speech. Returns audio/mpeg bytes.

    Frontend isko try karta hai; fail hone pe browser ke apne speechSynthesis pe
    gir jaata hai, so yeh optional hai.
    """
    if not _tts_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS is disabled. Set ENABLE_TTS=true and OPENAI_API_KEY."
        )

    try:
        from openai import OpenAI

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Markdown asterisks bolna weird lagta hai — saaf kar do
        clean = payload.text.replace("*", "").replace("#", "").replace("`", "")

        speech = client.audio.speech.create(
            model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("TTS_VOICE", "sage"),
            input=clean[:4000],
            instructions=_TTS_INSTRUCTIONS,
            response_format="mp3",
        )

        return Response(
            content=speech.read(),
            media_type="audio/mpeg",
            headers={"Cache-Control": "no-store"},
        )

    except Exception:
        logger.exception("TTS failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Text-to-speech failed."
        )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
