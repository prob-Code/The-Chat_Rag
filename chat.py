from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
import os
import sys
from pathlib import Path
import time

# Resolve project root (directory containing this file) so script works from any CWD.
PROJECT_ROOT = Path(__file__).resolve().parent

# Add project root to path
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv
from rag_core.config import LightRAGConfig, get_llm

# Load environment variables
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# 1. Load embeddings
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# 2. Load vector DB
db = FAISS.load_local(
    str(PROJECT_ROOT / "gita_vector_db"),
    embedding_model,
    allow_dangerous_deserialization=True
)

retriever = db.as_retriever(search_kwargs={"k": 4})

# 4. Gita-centric modern prompt - Enhanced for emotional support
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a compassionate spiritual guide trained in the wisdom of Bhagavad Gita.

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
- Keep it concise and scannable (prefer bullets).
"""
)


def _is_bytez_insufficient_credits_error(exc: Exception) -> bool:
    msg = str(exc)
    return "Bytez API error" in msg and "status 402" in msg


def _is_ollama_insufficient_memory_error(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "requires more system memory" in msg and "available" in msg


def _build_chain(
    force_disable_bytez: bool = False,
    llm_model_override: str | None = None,
    openai_api_base_override: str | None = None,
    openai_api_key_override: str | None = None,
):
    config = LightRAGConfig()
    if force_disable_bytez:
        config.use_bytez = False
    if llm_model_override:
        config.llm_model = llm_model_override
    if openai_api_base_override:
        config.openai_api_base = openai_api_base_override
    if openai_api_key_override is not None:
        config.openai_api_key = openai_api_key_override
    llm = get_llm(config)
    return prompt | llm


# Create chain (prefers Bytez if enabled via USE_BYTEZ)
chain = _build_chain(force_disable_bytez=False)

# 5. Chat loop
while True:
    try:
        query = input("\nAsk your question (or 'exit'): ")
    except (EOFError, KeyboardInterrupt):
        print("\nExiting.")
        break

    if not query.strip():
        continue

    if query.lower() == "exit":
        break

    print("\n[Retrieval] Searching the Gita knowledge base...", flush=True)
    t0 = time.perf_counter()
    docs = retriever.invoke(query)
    t1 = time.perf_counter()

    context = "\n\n".join([d.page_content for d in docs])

    try:
        print(f"[Retrieval] Found {len(docs)} passages in {t1 - t0:.2f}s.", flush=True)
        print("[LLM] Generating response...", flush=True)
        answer = chain.invoke({
            "context": context,
            "question": query
        })
        print("\nAnswer:\n", answer.content)
    except Exception as e:
        # If local Ollama fails due to memory constraints, try a cloud backend (Groq)
        # or smaller local models before giving up.
        if _is_ollama_insufficient_memory_error(e):
            print("\n[Ollama] Model too large for available RAM. Attempting fallback...")

            groq_key = os.getenv("GROQ_API_KEY", "").strip()
            if groq_key:
                try:
                    print("[Groq] Retrying via Groq backend...")
                    chain = _build_chain(
                        force_disable_bytez=True,
                        openai_api_base_override="https://api.groq.com/openai/v1",
                        openai_api_key_override=groq_key,
                        llm_model_override=os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant"),
                    )
                    answer = chain.invoke({
                        "context": context,
                        "question": query
                    })
                    print("\nAnswer:\n", answer.content)
                    continue
                except Exception as groq_exc:
                    print(f"[Groq] Fallback failed: {groq_exc}")

            # As a last resort, try a few smaller common Ollama models.
            local_model_candidates = [
                "qwen2.5:0.5b",
                "llama3.2:1b",
                "phi3:mini",
                "gemma2:2b",
            ]
            for candidate in local_model_candidates:
                try:
                    print(f"[Ollama] Retrying with '{candidate}'...")
                    chain = _build_chain(force_disable_bytez=True, llm_model_override=candidate)
                    answer = chain.invoke({
                        "context": context,
                        "question": query
                    })
                    print("\nAnswer:\n", answer.content)
                    break
                except Exception as local_exc:
                    if _is_ollama_insufficient_memory_error(local_exc):
                        continue
                    raise
            else:
                print("[LLM] Unable to run any local model with current RAM.")
            continue

        # If Bytez is out of credits, transparently fall back to local Ollama/Groq.
        if _is_bytez_insufficient_credits_error(e):
            print("\n[Bytez] Insufficient credits (402). Falling back to non-Bytez LLM...")
            try:
                chain = _build_chain(force_disable_bytez=True)
                answer = chain.invoke({
                    "context": context,
                    "question": query
                })
                print("\nAnswer:\n", answer.content)
            except Exception as fallback_exc:
                if _is_ollama_insufficient_memory_error(fallback_exc):
                    # Prefer a cloud fallback when local Ollama is memory constrained.
                    groq_key = os.getenv("GROQ_API_KEY", "").strip()
                    if groq_key:
                        print("\n[Groq] Ollama is memory constrained. Retrying via Groq backend...")
                        chain = _build_chain(
                            force_disable_bytez=True,
                            openai_api_base_override="https://api.groq.com/openai/v1",
                            openai_api_key_override=groq_key,
                            llm_model_override=os.getenv("GROQ_LLM_MODEL", "llama-3.1-8b-instant"),
                        )
                        answer = chain.invoke({
                            "context": context,
                            "question": query
                        })
                        print("\nAnswer:\n", answer.content)
                    else:
                        # Common on low-RAM machines when using larger models.
                        smaller_model = "phi3:mini"
                        print(
                            f"\n[Ollama] Model too large for available RAM. Retrying with '{smaller_model}'..."
                        )
                        chain = _build_chain(force_disable_bytez=True, llm_model_override=smaller_model)
                        answer = chain.invoke({
                            "context": context,
                            "question": query
                        })
                        print("\nAnswer:\n", answer.content)
                else:
                    raise
        else:
            raise
