"""
RagGita FastAPI Server
A compassionate spiritual guide API based on Bhagavad Gita wisdom
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
from fastapi.responses import FileResponse
from starlette.responses import StreamingResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_community.vectorstores import FAISS
try:
    # Prefer remote embeddings when an API key is provided to avoid large local model requirements
    from langchain.embeddings import OpenAIEmbeddings
except Exception:
    OpenAIEmbeddings = None

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
from rag_core.config import LightRAGConfig, get_llm
from rag_core.streaming import TokenQueueCallbackHandler
import requests
import traceback


def _llm_ping() -> bool:
    """Quickly check whether the configured OpenAI-compatible LLM endpoint is reachable.

    Returns True if reachable (or no external base configured), False otherwise.
    """
    base = os.getenv("OPENAI_API_BASE", "").strip()
    if not base:
        return True

    # Try a lightweight GET to a common OpenAI-compatible path
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
chain = None
prompt_template = None


def _clamp_top_k(k: int) -> int:
    # For fast TTFT, keep context small.
    return max(1, min(5, int(k)))


def _truncate_context(text: str) -> str:
    max_context_chars = int(os.getenv("MAX_CONTEXT_CHARS", "6000"))
    if max_context_chars > 0 and len(text) > max_context_chars:
        return text[:max_context_chars] + "\n\n[...context truncated...]"
    return text


@lru_cache(maxsize=512)
def _cached_query_embedding(query: str) -> tuple[float, ...]:
    """LRU cache for query embeddings.

    This helps repeated questions and reduces CPU time.
    NOTE: This is per-process memory cache.
    """
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


def _sse(event: str | None, data) -> bytes:
    """Encode a Server-Sent Event payload."""
    payload = json.dumps(data, ensure_ascii=False)
    if event:
        return f"event: {event}\ndata: {payload}\n\n".encode("utf-8")
    return f"data: {payload}\n\n".encode("utf-8")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - load models on startup"""
    global embedding_model, db, retriever, llm, chain, prompt_template

    logger.info("Loading RagGita models...")

    try:
        # 1. Load embeddings
        # IMPORTANT: Always use HuggingFace embeddings for FAISS since the DB
        # was built with "all-MiniLM-L6-v2" (384 dimensions).
        # OpenAI embeddings (1536 dims) would cause a dimension mismatch crash.
        logger.info("Loading embeddings model...")
        force_local = os.getenv("FORCE_LOCAL_EMBEDDINGS", "true").strip().lower() in ("1", "true", "yes", "y")
        if not force_local and os.getenv("OPENAI_API_KEY") and OpenAIEmbeddings is not None:
            logger.info("OPENAI_API_KEY detected — using OpenAIEmbeddings (remote)")
            embedding_model = OpenAIEmbeddings()
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

        # 3. Initialize LLM (Bytez OR OpenAI-compatible like Ollama/Groq)
        logger.info("Initializing LLM...")
        config = LightRAGConfig()
        llm = get_llm(config, temperature=0.7)

        # 4. Create prompt template
        prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template="""You are a compassionate spiritual guide trained in the wisdom of Bhagavad Gita.

Your role is to provide comfort, hope, and practical guidance to someone who may be feeling lost, sad, anxious, or overwhelmed.

Guidelines for your response:
1. Start with empathy — acknowledge the person's feelings without judgment
2. Use warm, gentle, and encouraging language
3. Share relevant Gita wisdom in simple, relatable terms
4. Remind them that difficult times are temporary and part of life's journey
5. Offer small, actionable steps they can take today
6. End with an uplifting message of hope and strength

Context from Gita:
{context}

Question:
{question}

Respond with deep compassion. Speak as a caring friend who truly understands their pain.
Make them feel heard, valued, and capable of overcoming this phase.
Keep the tone warm, supportive, and never preachy.

Formatting Requirements (IMPORTANT):
- Output MUST be in Markdown.
- Use these exact section headers (in this order):
    1) **Empathy**
    2) **Gita Guidance (In Simple Words)**
    3) **From The Text**
    4) **Try Today**
    5) **Closing**
- Keep it concise and scannable (prefer bullets)."""
        )

        # 5. Create chain
        chain = prompt_template | llm

        logger.info("RagGita API is ready!")

    except Exception as e:
        logger.exception("Failed to load models")
        raise

    yield  # Server runs here

    # Cleanup on shutdown
    logger.info("Shutting down RagGita API...")


# Create FastAPI app
app = FastAPI(
    title="RagGita API",
    description="A compassionate spiritual guide API based on Bhagavad Gita wisdom",
    version="1.0.0",
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

    class Config:
        json_schema_extra = {
            "example": {
                "question": "I'm feeling anxious about my future. What does the Gita say?"
            }
        }


class ChatResponse(BaseModel):
    """Chat response model"""
    answer: str = Field(..., description="The AI-generated response")
    sources: list = Field(default=[], description="Source documents used")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "I understand you're feeling anxious...",
                "sources": []
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    message: str
    version: str = "1.0.0"


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
        version="1.0.0"
    )


@app.get("/health", response_model=HealthResponse)
def health_check():
    """Health check endpoint for monitoring"""
    global chain, retriever
    if chain is None or retriever is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models not loaded"
        )
    return HealthResponse(
        status="healthy",
        message="All systems operational",
        version="1.0.0"
    )


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """
    Chat with the Gita RAG bot.

    Send a question and receive a compassionate, spiritually-guided response
    based on the wisdom of the Bhagavad Gita.
    """
    global chain, retriever

    if not chain or not retriever:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    try:
        # Retrieve relevant context
        docs = retriever.invoke(request.question)
        context = "\n\n".join([d.page_content for d in docs])

        # Guardrail: local models (e.g., Ollama) can crash on very large prompts.
        context = _truncate_context(context)

        # Generate response
        answer = chain.invoke({
            "context": context,
            "question": request.question
        })

        return ChatResponse(
            answer=answer.content,
            sources=[]
        )

    except Exception as e:
        # Log full traceback
        logger.exception("Error in chat endpoint")

        # Detect backend connection problems (OpenAI/Groq/Ollama)
        err_str = str(e).lower()
        if "connection error" in err_str or isinstance(e, requests.RequestException):
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "LLM backend connection failed. "
                    "Check OPENAI_API_BASE, network connectivity, and API key."
                ),
            )

        # Generic 500 for other failures
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
    """Faster non-streaming endpoint.

    Differences vs `/chat`:
    - Uses cached embeddings for retrieval
    - Clamps RAG context to top 3-5 chunks (default 4)
    - Applies context truncation for local model stability
    """
    global chain, prompt_template

    if not chain or prompt_template is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet. Please try again in a moment."
        )

    try:
        if not _llm_ping():
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=(
                    "LLM backend is unreachable. "
                    "Verify OPENAI_API_BASE and that the Groq/OpenAI-compatible endpoint is accessible."
                ),
            )

        k = int(os.getenv("FAST_TOP_K", "4"))
        docs = _retrieve_docs_faiss(request.question, k=k)
        context = _docs_to_context(docs)

        answer = chain.invoke({
            "context": context,
            "question": request.question
        })

        return ChatResponse(answer=answer.content, sources=[])
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
    k: int = 4,
):
    """Stream tokens using Server-Sent Events (SSE).

    This endpoint is designed for low-latency UX (fast TTFT):
    - Retrieves only top 3-5 chunks
    - Truncates context for stability on local runners

    Client:
      - Use EventSource with a URL-encoded `question` query param.
    """
    global embedding_model, db, prompt_template

    if embedding_model is None or db is None or prompt_template is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Models are not loaded yet."
        )

    k = _clamp_top_k(k)

    async def event_generator():
        # Initial meta event
        yield _sse("meta", {"status": "starting", "k": k})

        try:
            docs = await asyncio.to_thread(_retrieve_docs_faiss, question, k)
            context = _docs_to_context(docs)
        except Exception as e:
            yield _sse("error", {"message": f"retrieval_failed: {str(e)}"})
            return

        # Build a streaming LLM chain.
        handler = TokenQueueCallbackHandler()
        config = LightRAGConfig()
        if config.use_bytez:
            # Bytez wrapper does not stream today; keep /chat for Bytez.
            yield _sse(
                "error",
                {
                    "message": "streaming_not_supported_for_bytez",
                    "hint": "Set USE_BYTEZ=false in .env to stream via local Ollama/Groq."
                },
            )
            return

        stream_llm = get_llm(config, temperature=0.7, streaming=True, callbacks=[handler])
        stream_chain = prompt_template | stream_llm

        # Start generation in background.
        async def run_generation():
            try:
                await stream_chain.ainvoke({"context": context, "question": question})
            finally:
                await handler.finish()

        task = asyncio.create_task(run_generation())

        # Stream tokens as they arrive.
        try:
            yield _sse("meta", {"status": "generating"})
            async for token in handler.aiter_tokens(timeout_s=15.0):
                if await request.is_disconnected():
                    break

                if token is None:
                    # Keep-alive comment (not an event)
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
            # Prevent proxy buffering (nginx)
            "X-Accel-Buffering": "no",
        },
    )


# ======================
# Error Handlers
# ======================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all unhandled exceptions"""
    logger.error(f"Unhandled exception: {exc}")
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error"
    )


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
