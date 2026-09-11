"""
RagGita FastAPI Server
A compassionate spiritual guide API based on Bhagavad Gita wisdom.

v2.1:
  - Short, gentle replies (rag_core/prompts.py)
  - Dynamic prompting per user class (rag_core/gita_map.py)
  - Crisis safety guard before any LLM call
  - Abuse guard: per-IP rate limit + daily budget (rag_core/guard.py)
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
from rag_core.prompts import analyse, build_prompt, get_prompt_template, is_crisis, CRISIS_REPLY
from rag_core.gita_map import public_classes
from rag_core.guard import enforce as guard_enforce

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


# Jab OpenAI khud 429 de — yeh alag baat hai humare rate limit se.
BUSY_MESSAGE = (
    "A lot of people are here right now and I couldn't get through. "
    "Give it a few seconds and try again — I'm not going anywhere."
)


def _is_upstream_rate_limit(e: Exception) -> bool:
    s = str(e).lower()
    return "429" in s or "rate limit" in s or "rate_limit" in s or "overloaded" in s


def _llm_ping() -> bool:
    """Quickly check whether the configured OpenAI-compatible LLM endpoint is reachable."""
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
    if db is None:
        raise RuntimeError("Vector DB not loaded")
    k = _clamp_top_k(k)
    vector = list(_cached_query_embedding(question))
    return db.similarity_search_by_vector(vector, k=k)


def _docs_to_context(docs) -> str:
    return _truncate_context("\n\n".join([d.page_content for d in docs]))


def _sse(event, data) -> bytes:
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
            # sentence-transformers ab requirements.txt me nahi hai (torch ~2.5GB
            # laata tha aur Render ka build maar raha tha). Agar koi local
            # embeddings maange bina usse install kiye, toh crash karne ke bajaye
            # remote pe gir jao — app chalta rehna chahiye.
            try:
                logger.info("Using local HuggingFace embeddings (all-MiniLM-L6-v2)")
                embedding_model = HuggingFaceEmbeddings(
                    model_name="sentence-transformers/all-MiniLM-L6-v2"
                )
            except ImportError:
                logger.warning(
                    "sentence-transformers not installed; falling back to the "
                    "HuggingFace Inference API. Install it, or set "
                    "USE_REMOTE_EMBEDDINGS=true to silence this."
                )
                if HuggingFaceEndpointEmbeddings is None:
                    raise
                endpoint_kwargs = {"model": "sentence-transformers/all-MiniLM-L6-v2"}
                if hf_token:
                    endpoint_kwargs["huggingfacehub_api_token"] = hf_token
                embedding_model = HuggingFaceEndpointEmbeddings(**endpoint_kwargs)

        logger.info("Loading FAISS vector database...")
        db = FAISS.load_local(
            "gita_vector_db",
            embedding_model,
            allow_dangerous_deserialization=True
        )
        retriever = db.as_retriever(search_kwargs={"k": 4})

        logger.info("Initializing LLM...")
        config = LightRAGConfig()
        llm = get_llm(config)

        prompt_template = get_prompt_template("auto")

        logger.info("RagGita API is ready!")

    except Exception:
        logger.exception("Failed to load models")
        raise

    yield

    logger.info("Shutting down RagGita API...")


app = FastAPI(
    title="RagGita API",
    description="A compassionate spiritual guide API based on Bhagavad Gita wisdom",
    version="2.1.0",
    lifespan=lifespan
)

# CORS — production me ALLOWED_ORIGINS set karo (comma-separated).
# "*" sirf isliye default hai taaki local dev na toote.
_origins_env = os.getenv("ALLOWED_ORIGINS", "*").strip()
_allowed_origins = ["*"] if _origins_env == "*" else [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=_allowed_origins != ["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")


# ======================
# Pydantic Models
# ======================

class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_class: str = Field(default="auto", max_length=32)

    class Config:
        json_schema_extra = {
            "example": {"question": "I'm feeling anxious about my future.", "user_class": "anxious"}
        }


class ChatResponse(BaseModel):
    answer: str
    sources: list = Field(default=[])
    user_class: str = Field(default="auto")
    crisis: bool = Field(default=False)


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)


class HealthResponse(BaseModel):
    status: str
    message: str
    version: str = "2.1.0"


# ======================
# Core logic
# ======================

def _generate(question: str, user_class: str, retrieve) -> ChatResponse:
    """Intent + class decide karo, zaroorat ho tabhi retrieve karo, phir LLM chalao.

    `retrieve` ek callable hai jo context string laata hai. Use TABHI bulate hain
    jab prompt ko sach me Gita context chahiye — greeting aur off-topic pe
    embedding call aur FAISS search dono bach jaate hain.
    """
    prompt, meta = analyse(question, user_class)

    variables = {"question": question}
    if "context" in prompt.input_variables:
        variables["context"] = retrieve() if meta["needs_rag"] else ""

    logger.info("intent=%s class=%s rag=%s", meta["intent"], meta["user_class"], meta["needs_rag"])

    chain = prompt | llm
    answer = chain.invoke(variables)
    return ChatResponse(answer=answer.content, sources=[], user_class=meta["user_class"])


def _handle_llm_error(e: Exception):
    """Exception ko sahi HTTP response me badlo."""
    logger.exception("Generation failed")

    if _is_upstream_rate_limit(e):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=BUSY_MESSAGE,
            headers={"Retry-After": "10"},
        )

    err_str = str(e).lower()
    if "connection error" in err_str or isinstance(e, requests.RequestException):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM backend connection failed. Check OPENAI_API_BASE, network and API key.",
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="An internal error occurred while generating the response."
    )


# ======================
# API Endpoints
# ======================

@app.get("/", include_in_schema=False)
def root():
    return FileResponse("static/index.html")


@app.get("/api", response_model=HealthResponse)
def api_info():
    return HealthResponse(status="ok", message="RagGita API is running. Visit /docs.", version="2.1.0")


@app.get("/health", response_model=HealthResponse)
def health_check():
    if llm is None or retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded"
        )
    return HealthResponse(status="healthy", message="All systems operational", version="2.1.0")


@app.get("/classes")
def list_classes():
    return {"classes": public_classes(), "tts_enabled": _tts_enabled()}


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(payload: ChatRequest, request: Request):
    """Chat with the Gita RAG bot."""
    if llm is None or retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    # ORDER MATTERS: crisis check sabse pehle.
    # Yeh free hai (koi LLM call nahi), aur rate limit isse kabhi nahi rokta.
    crisis = is_crisis(payload.question)
    if crisis:
        logger.info("Crisis guard triggered; returning helpline response.")
        return ChatResponse(answer=CRISIS_REPLY, sources=[], user_class="crisis", crisis=True)

    guard_enforce(request, is_crisis_message=False)

    try:
        def retrieve():
            docs = retriever.invoke(payload.question)
            return _truncate_context("\n\n".join([d.page_content for d in docs]))

        return _generate(payload.question, payload.user_class, retrieve)
    except HTTPException:
        raise
    except Exception as e:
        _handle_llm_error(e)


@app.post("/ask", response_model=ChatResponse)
def ask_endpoint(payload: ChatRequest, request: Request):
    """Alias for /chat endpoint"""
    return chat_endpoint(payload, request)


@app.post("/chat_fast", response_model=ChatResponse)
def chat_fast_endpoint(payload: ChatRequest, request: Request):
    """Faster non-streaming endpoint (cached embeddings, fewer chunks)."""
    if llm is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    if is_crisis(payload.question):
        logger.info("Crisis guard triggered; returning helpline response.")
        return ChatResponse(answer=CRISIS_REPLY, sources=[], user_class="crisis", crisis=True)

    guard_enforce(request, is_crisis_message=False)

    try:
        def retrieve():
            k = int(os.getenv("FAST_TOP_K", "3"))
            return _docs_to_context(_retrieve_docs_faiss(payload.question, k=k))

        return _generate(payload.question, payload.user_class, retrieve)
    except HTTPException:
        raise
    except Exception as e:
        _handle_llm_error(e)


@app.get("/chat/stream")
async def chat_stream_endpoint(
    request: Request,
    question: str,
    k: int = 3,
    user_class: str = "auto",
):
    """Stream tokens using Server-Sent Events (SSE)."""
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

    guard_enforce(request, is_crisis_message=False)

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
            yield _sse("error", {
                "message": "streaming_not_supported_for_bytez",
                "hint": "Set USE_BYTEZ=false to stream via an OpenAI-compatible backend."
            })
            return

        stream_prompt, _meta = analyse(question, user_class)
        stream_llm = get_llm(config, streaming=True, callbacks=[handler])
        stream_chain = stream_prompt | stream_llm

        stream_vars = {"question": question}
        if "context" in stream_prompt.input_variables:
            stream_vars["context"] = context

        async def run_generation():
            try:
                await stream_chain.ainvoke(stream_vars)
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


_TTS_INSTRUCTIONS = os.getenv(
    "TTS_INSTRUCTIONS",
    "Speak slowly and softly, like someone sitting beside a tired friend late at night. "
    "Warm and steady, never bright or performative. Leave small pauses between sentences.",
)


@app.post("/tts")
def tts_endpoint(payload: TTSRequest, request: Request):
    """Convert a reply to speech. Returns audio/mpeg bytes."""
    if not _tts_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="TTS is disabled. Set ENABLE_TTS=true and OPENAI_API_KEY."
        )

    # TTS pe bhi paisa lagta hai — guard yahan bhi chahiye.
    guard_enforce(request, is_crisis_message=False)

    try:
        from openai import OpenAI

        client = OpenAI(
            api_key=os.getenv("OPENAI_API_KEY"),
            max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "3")),
        )

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

    except HTTPException:
        raise
    except Exception as e:
        logger.exception("TTS failed")
        if _is_upstream_rate_limit(e):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=BUSY_MESSAGE,
                headers={"Retry-After": "10"},
            )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Text-to-speech failed.")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
