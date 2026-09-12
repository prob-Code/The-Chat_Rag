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
from rag_core.prompts import (
    analyse, get_prompt_template, is_crisis,
    crisis_reply, normalise_lang, public_langs, DEFAULT_LANG,
)
from rag_core.gita_map import public_classes
from rag_core.guard import enforce as guard_enforce
from rag_core.prompts import format_history
from rag_core import store
from rag_core import auth

import requests
import uuid
import traceback

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


def user_id(request: Request, body_uid: str = "") -> str:
    """Kaun bol raha hai. Poore app me identity ka ek hi source yahi hai.

    Teen level, is kram me:
      1. Firebase ID token  -> "fb:<uid>"     asli login, devices ke aar-paar chalta hai
      2. X-User-Id header   -> device id      anonymous, ek device tak
      3. IP                 -> "anon-<ip>"    aakhri sahara

    Anonymous jaan-boojh ke allowed hai. Mental health app me sign-in
    zabardasti karna sabse bura barrier hai — log sabse buri raat me
    account nahi banate. Jo sign in karte hain unhe multi-device history
    milti hai; jo nahi karte unhe bhi app milta hai.
    """
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and auth.enabled():
        token = header[7:].strip()
        try:
            return "fb:" + auth.verify_firebase_token(token)
        except auth.AuthError as e:
            # Token bheja gaya par galat hai — chupchaap anonymous pe girana
            # galat hoga, warna user ko lagega uska account kaam kar raha hai
            # jabki history kahin aur ja rahi hai.
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Sign-in expired or invalid. {e}",
            )

    uid = (body_uid or request.headers.get("x-user-id", "")).strip()
    if uid:
        return uid[:64]

    from rag_core.guard import client_ip
    return "anon-" + client_ip(request).replace(":", "-")[:48]


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
    lang: str = Field(default="en", max_length=16,
                      description="Reply language: en, hi (Devanagari), hi-latn (Hinglish)")
    conversation_id: str = Field(default="", max_length=64,
                                 description="Blank shuru karne ke liye; server naya id dega")
    user_id: str = Field(default="", max_length=64,
                         description="Stable device id. Header X-User-Id bhi chalta hai.")

    class Config:
        json_schema_extra = {
            "example": {"question": "I'm feeling anxious about my future.", "user_class": "anxious"}
        }


class ChatResponse(BaseModel):
    answer: str
    sources: list = Field(default=[])
    user_class: str = Field(default="auto")
    lang: str = Field(default="en")
    crisis: bool = Field(default=False)
    conversation_id: str = Field(default="")


class TTSRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=4000)
    lang: str = Field(default="en", max_length=16)


class HealthResponse(BaseModel):
    status: str
    message: str
    version: str = "2.1.0"


# ======================
# Core logic
# ======================

def _summarise(conv_id, uid, summary, messages, lang):
    """Purani baaton ko ek rolling summary me nichodo.

    Har 10 turns pe chalta hai, har message pe nahi — matlab ~10% overhead
    ke badle prompt ka size hamesha bandha rehta hai, chahe baat kitni bhi
    lambi ho jaye.
    """
    try:
        transcript = format_history(messages)
        if not transcript:
            return
        instruction = (
            "Update a running summary of this conversation for your own future reference.\n\n"
            "Record only: what the person is dealing with in their own words, what they have "
            "already tried, and anything that seemed to help.\n\n"
            "Do NOT record: any diagnosis, any mention of self-harm or suicide, medication, "
            "or anything you inferred rather than heard them say. Write plainly, under 80 words, "
            "third person, no advice.\n\n"
            f"Existing summary:\n{summary or '(none yet)'}\n\n"
            f"Recent conversation:\n{transcript}\n\n"
            "Updated summary:"
        )
        out = llm.invoke(instruction)
        text = getattr(out, "content", str(out)).strip()
        if text:
            store.update_summary(uid, conv_id, text)
            logger.info("summary refreshed for conv=%s (%d chars)", conv_id, len(text))
    except Exception:
        # Summary optional hai. Fail ho toh chat chalti rahe.
        logger.exception("summarise failed (non-fatal)")


def _generate(question, user_class, lang, uid, conv_id, retrieve) -> ChatResponse:
    """Memory load karo, prompt banao, LLM chalao, turn save karo."""
    summary, history_msgs = store.load_memory(uid, conv_id)
    history_text = format_history(history_msgs)
    if summary:
        history_text = (f"Summary of earlier turns: {summary}\n\n" + history_text).strip()

    prompt, meta = analyse(question, user_class, lang, has_history=bool(history_text))

    variables = {"question": question}
    if "context" in prompt.input_variables:
        variables["context"] = retrieve() if meta["needs_rag"] else ""
    if "history" in prompt.input_variables:
        variables["history"] = history_text

    logger.info("uid=%s conv=%s intent=%s class=%s lang=%s rag=%s hist=%s",
                uid[:12], conv_id[:8], meta["intent"], meta["user_class"],
                meta["lang"], meta["needs_rag"], meta["has_history"])

    answer = (prompt | llm).invoke(variables)
    text = answer.content

    turns = store.save_turn(uid, conv_id, question, text,
                            user_class=meta["user_class"], lang=meta["lang"])

    if turns and turns % store.SUMMARISE_EVERY == 0:
        _, recent = store.load_memory(uid, conv_id, turns=store.SUMMARISE_EVERY * 2)
        _summarise(conv_id, uid, summary, recent, meta["lang"])

    return ChatResponse(answer=text, sources=[], user_class=meta["user_class"],
                        lang=meta["lang"], conversation_id=conv_id)


def _debug_errors() -> bool:
    return os.getenv("DEBUG_ERRORS", "true").strip().lower() in ("1", "true", "yes", "y")


def _detail(generic: str, e: Exception, err_id: str) -> str:
    if _debug_errors():
        return f"{generic} [{err_id}] {type(e).__name__}: {str(e)[:400]}"
    return f"{generic} (ref {err_id})"


def _handle_llm_error(e: Exception):
    """Exception ko sahi HTTP response me badlo, aur asli wajah batao."""
    err_id = uuid.uuid4().hex[:8]
    logger.error("[%s] generation failed: %s: %s\n%s",
                 err_id, type(e).__name__, e, traceback.format_exc())

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
            detail=_detail("LLM backend connection failed.", e, err_id),
        )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=_detail("Could not generate a reply.", e, err_id),
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
    return {"classes": public_classes(), "langs": public_langs(),
            "tts_enabled": _tts_enabled(), "history_enabled": store.enabled(),
            "auth_enabled": auth.enabled()}


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
    uid = user_id(request, payload.user_id)
    conv_id = payload.conversation_id or store.new_conversation_id()

    crisis = is_crisis(payload.question)
    if crisis:
        logger.info("Crisis guard triggered; returning helpline response.")
        # Event likhte hain, text nahi — guard chala yeh pata hona chahiye,
        # par kisi ki sabse buri raat ka record rakhna zaroori nahi.
        store.save_turn(uid, conv_id, payload.question, "",
                        user_class="crisis", lang=normalise_lang(payload.lang), crisis=True)
        return ChatResponse(answer=crisis_reply(payload.lang), sources=[],
                            user_class="crisis", lang=normalise_lang(payload.lang),
                            crisis=True, conversation_id=conv_id)

    guard_enforce(request, is_crisis_message=False)

    allowed, used = store.check_quota(uid)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="You have reached today's limit. I'll be here tomorrow.",
            headers={"Retry-After": "3600"},
        )

    try:
        def retrieve():
            docs = retriever.invoke(payload.question)
            return _truncate_context("\n\n".join([d.page_content for d in docs]))

        return _generate(payload.question, payload.user_class, payload.lang,
                         uid, conv_id, retrieve)
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

    uid = user_id(request, payload.user_id)
    conv_id = payload.conversation_id or store.new_conversation_id()

    if is_crisis(payload.question):
        logger.info("Crisis guard triggered; returning helpline response.")
        return ChatResponse(answer=crisis_reply(payload.lang), sources=[],
                            user_class="crisis", lang=normalise_lang(payload.lang),
                            crisis=True, conversation_id=conv_id)

    guard_enforce(request, is_crisis_message=False)

    try:
        def retrieve():
            k = int(os.getenv("FAST_TOP_K", "3"))
            return _docs_to_context(_retrieve_docs_faiss(payload.question, k=k))

        return _generate(payload.question, payload.user_class, payload.lang,
                         uid, conv_id, retrieve)
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
    lang: str = DEFAULT_LANG,
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
            yield _sse(None, {"token": crisis_reply(lang)})
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

        stream_prompt, _meta = analyse(question, user_class, lang)
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
# Conversations
# ======================

@app.get("/conversations")
def list_conversations_endpoint(request: Request, user_id_q: str = ""):
    """Iss user ki chats, nayi pehle."""
    uid = user_id(request, user_id_q)
    return {"user_id": uid, "conversations": store.list_conversations(uid)}


@app.get("/conversations/{conversation_id}")
def get_conversation_endpoint(conversation_id: str, request: Request, limit: int = 100):
    """Ek chat ke messages, purane se naye."""
    return {
        "conversation_id": conversation_id,
        "messages": store.get_messages(conversation_id, limit=min(limit, 200)),
    }


@app.delete("/conversations/{conversation_id}")
def delete_conversation_endpoint(conversation_id: str, request: Request, user_id_q: str = ""):
    uid = user_id(request, user_id_q)
    deleted = store.delete_conversation(uid, conversation_id)
    return {"deleted_messages": deleted, "conversation_id": conversation_id}


class LinkRequest(BaseModel):
    """Anonymous history ko abhi ke signed-in account se jodo."""
    device_id: str = Field(..., min_length=1, max_length=64)


@app.post("/link")
def link_endpoint(payload: LinkRequest, request: Request):
    """Sign-in ke baad ek baar call karo.

    Koi pehle bina login chat karta hai, phir account banata hai — uski
    purani baatein gayab nahi honi chahiye. Yeh unhe naye uid ke neeche
    le aata hai.
    """
    uid = user_id(request)
    if not uid.startswith("fb:"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in first, then link.",
        )
    moved = store.move_conversations(payload.device_id.strip(), uid)
    return {"user_id": uid, "conversations_moved": moved}


@app.delete("/me")
def delete_me_endpoint(request: Request, user_id_q: str = ""):
    """Sab kuch mita do. DPDP ke under yeh optional nahi hai — aur isse
    sach me delete hona chahiye, chhupana nahi."""
    uid = user_id(request, user_id_q)
    result = store.delete_user(uid)
    logger.info("erased all data for uid=%s: %s", uid[:12], result)
    return {"user_id": uid, "erased": result}


# ======================
# Text to Speech
# ======================

def _tts_enabled() -> bool:
    return (
        os.getenv("ENABLE_TTS", "true").strip().lower() in ("1", "true", "yes", "y")
        and bool(os.getenv("OPENAI_API_KEY", "").strip())
    )


# Voice ko "calming" banane ke teen lever hain, aur instructions sabse strong hai.
# Yeh deliberately detailed hai — gpt-4o-mini-tts choti-choti hint se zyada
# poori tasveer follow karta hai.
_CALM_EN = (
    "Speak very slowly and very softly, low and warm in your register, as if you are "
    "sitting beside someone who is exhausted and close to sleep. A natural Indian English "
    "accent, the way a kind Indian elder speaks. Let each sentence settle completely before "
    "the next one begins - leave a real pause there, not a rushed breath. Never bright, "
    "never cheerful, never rising at the end of a sentence. Pronounce Sanskrit and Hindi "
    "words the Indian way, not the anglicised way: dharma, karma, Krishna, Arjun, yog, shanti."
)

_CALM_HI = (
    "Speak in gentle, everyday spoken Hindi with a soft natural Indian accent. Very slow and "
    "very quiet, low and warm in your register, as if sitting beside someone who is exhausted "
    "and close to sleep. Leave a real pause between sentences. Never bright, never hurried, "
    "and never like a newsreader - this is one person speaking quietly at night, not an "
    "announcement. Use the relaxed pronunciation of conversation, not of recitation."
)

_TTS_INSTRUCTIONS = {
    "en":      os.getenv("TTS_INSTRUCTIONS_EN", os.getenv("TTS_INSTRUCTIONS", _CALM_EN)),
    "hi":      os.getenv("TTS_INSTRUCTIONS_HI", _CALM_HI),
    "hi-latn": os.getenv("TTS_INSTRUCTIONS_HI", _CALM_HI),
}


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
        lg = normalise_lang(payload.lang)

        kwargs = dict(
            model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            # 'ballad' gentle aur kahani-jaisi hai; 'sage' aur 'coral' bhi try karo.
            voice=os.getenv("TTS_VOICE", "ballad"),
            input=clean[:4000],
            instructions=_TTS_INSTRUCTIONS[lg],
            response_format="mp3",
        )

        # speed sirf tab bhejte hain jab explicitly set ho. gpt-4o-mini-tts
        # tone instructions se control karta hai, aur unsupported param pe
        # error de sakta hai — isliye opt-in rakha hai. 0.9 dhima aur natural hai.
        speed = os.getenv("TTS_SPEED", "").strip()
        if speed:
            kwargs["speed"] = float(speed)

        try:
            speech = client.audio.speech.create(**kwargs)
        except TypeError:
            kwargs.pop("speed", None)
            speech = client.audio.speech.create(**kwargs)

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


# ======================
# Diagnostics
# ======================
# Ek URL jo khud bata deta hai kaunsa hissa toota hai — embeddings, retrieval,
# LLM ya TTS. Iske bina har baar CloudWatch khodna padta tha aur guess karna
# padta tha. Token se guarded hai kyunki yeh asli API calls karta hai.

@app.get("/diag")
def diag_endpoint(token: str = ""):
    """GET /diag?token=<DIAG_TOKEN> — har hisse ko alag-alag test karta hai."""
    expected = os.getenv("DIAG_TOKEN", "").strip()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Diagnostics are off. Set a DIAG_TOKEN environment variable to enable.",
        )
    if token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bad token.")

    report = {"checks": [], "config": {}}

    def check(name, fn):
        try:
            report["checks"].append({"name": name, "ok": True, "info": fn()})
        except Exception as e:
            report["checks"].append({
                "name": name, "ok": False,
                "error": f"{type(e).__name__}: {str(e)[:300]}",
            })

    # Kaunse env vars set hain — values kabhi nahi, sirf haan/na
    for key in ("OPENAI_API_KEY", "HF_TOKEN", "OPENAI_API_BASE", "LLM_MODEL",
                "USE_REMOTE_EMBEDDINGS", "ENABLE_TTS", "TTS_MODEL", "TTS_VOICE",
                "LIGHTRAG_BASE_PATH", "DEBUG_ERRORS"):
        val = os.getenv(key, "")
        if key.endswith("_KEY") or key.endswith("TOKEN"):
            report["config"][key] = f"set ({len(val)} chars)" if val else "MISSING"
        else:
            report["config"][key] = val or "(default)"

    def _store():
        if not store.enabled():
            return {"enabled": False, "note": "DynamoDB unreachable or table missing"}
        uid = "diag-selftest"
        cid = store.new_conversation_id()
        store.save_turn(uid, cid, "diag ping", "diag pong")
        _sum, msgs = store.load_memory(uid, cid)
        out = {"enabled": True, "round_trip_messages": len(msgs)}
        store.delete_conversation(uid, cid)
        return out
    check("storage", _store)
    check("auth", lambda: {
        "enabled": auth.enabled(),
        "project_id": auth.project_id() or "(not set)",
        "note": "anonymous device ids still work when this is off",
    })

    check("startup", lambda: {
        "embedding_model": embedding_model is not None,
        "vector_db": db is not None,
        "retriever": retriever is not None,
        "llm": llm is not None,
    })

    def _embed():
        v = embedding_model.embed_query("test")
        return {"dimensions": len(v)}
    check("embeddings", _embed)

    def _retrieve():
        docs = retriever.invoke("what is dharma")
        return {"docs": len(docs), "first_chars": len(docs[0].page_content) if docs else 0}
    check("retrieval", _retrieve)

    def _llm():
        from rag_core.prompts import analyse
        prompt, meta = analyse("hi", "auto", "en")
        out = (prompt | llm).invoke({"question": "hi"})
        return {"intent": meta["intent"], "reply_chars": len(out.content)}
    check("llm", _llm)

    def _tts():
        if not _tts_enabled():
            return {"skipped": "TTS disabled or no key"}
        from openai import OpenAI
        c = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        sp = c.audio.speech.create(
            model=os.getenv("TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("TTS_VOICE", "ballad"),
            input="test", response_format="mp3",
        )
        return {"bytes": len(sp.read())}
    check("tts", _tts)

    report["all_ok"] = all(c["ok"] for c in report["checks"])
    return report


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
