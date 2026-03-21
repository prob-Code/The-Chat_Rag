"""
RagGita FastAPI Server
A compassionate spiritual guide API based on Bhagavad Gita wisdom
"""
import os
import sys
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
from rag_core.bytez_llm import BytezGPT

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - load models on startup"""
    global embedding_model, db, retriever, llm, chain

    logger.info("Loading RagGita models...")

    try:
        # 1. Load embeddings
        logger.info("Loading embeddings model...")
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
        logger.info("Initializing Bytez GPT...")
        api_key = os.getenv("BYTEZ_API_KEY", "d58e5d706eddd608a4ff5b4153396c11")
        model_id = os.getenv("BYTEZ_MODEL", "openai/gpt-5.1")

        if not api_key:
            raise ValueError("BYTEZ_API_KEY not set")

        llm = BytezGPT(
            model_id=model_id,
            api_key=api_key,
            temperature=0.7,
        )

        # 4. Create prompt template
        prompt = PromptTemplate(
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
Keep the tone warm, supportive, and never preachy."""
        )

        # 5. Create chain
        chain = prompt | llm

        logger.info("RagGita API is ready!")

    except Exception as e:
        logger.error(f"Failed to load models: {e}")
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
        logger.error(f"Error in chat endpoint: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred: {str(e)}"
        )


@app.post("/ask", response_model=ChatResponse)
def ask_endpoint(request: ChatRequest):
    """Alias for /chat endpoint"""
    return chat_endpoint(request)


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
