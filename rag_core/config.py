"""
LightRAG Configuration Settings
"""
import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, Sequence, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Resolve paths relative to the project root (so scripts work from any CWD)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_DEFAULT_BASE_PATH = _PROJECT_ROOT / "lightrag_storage"

@dataclass
class LightRAGConfig:
    """Configuration for LightRAG system"""
    
    # API Settings (Groq - legacy)
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_api_base: str = os.getenv("OPENAI_API_BASE", "https://api.groq.com/openai/v1")
    llm_model: str = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
    llm_temperature: float = 0.7
    llm_timeout: float = float(os.getenv("LLM_TIMEOUT", "60"))
    
    # Bytez Configuration (GPT-5.1)
    bytez_api_key: str = os.getenv("BYTEZ_API_KEY", "")
    bytez_model: str = os.getenv("BYTEZ_MODEL", "openai/gpt-5.1")
    use_bytez: bool = os.getenv("USE_BYTEZ", "false").strip().lower() in ("1", "true", "yes", "y")
    
    # Embedding Settings
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    
    # Storage Paths
    base_path: str = os.getenv("LIGHTRAG_BASE_PATH", str(_DEFAULT_BASE_PATH))
    graph_path: str = str(Path(base_path) / "knowledge_graph.gpickle")
    chromadb_path: str = str(Path(base_path) / "chromadb")
    entity_index_path: str = str(Path(base_path) / "entity_index.json")
    
    # Extraction Settings
    chunk_size: int = 800
    chunk_overlap: int = 150
    
    # Retrieval Settings
    top_k_entities: int = 5
    top_k_chunks: int = 4
    similarity_threshold: float = 0.85
    
    # Entity Types
    entity_types: tuple = (
        "CONCEPT", "PERSON", "TEACHING", "VIRTUE", 
        "PRACTICE", "DEITY", "SCRIPTURE", "PLACE"
    )
    
    # Relationship Types
    relationship_types: tuple = (
        "TEACHES", "EMBODIES", "LEADS_TO", "OPPOSES", 
        "PART_OF", "MENTIONED_IN", "GUIDES", "EXPLAINS"
    )
    
    def __post_init__(self):
        """Create storage directories if they don't exist"""
        os.makedirs(self.base_path, exist_ok=True)
        os.makedirs(self.chromadb_path, exist_ok=True)


def get_llm(
    config: LightRAGConfig = None,
    temperature: float = None,
    streaming: bool = False,
    callbacks: Optional[Sequence[Any]] = None,
):
    """
    Factory function to create the LLM based on config.
    Returns either BytezGPT (GPT-5.1) or ChatOpenAI (Groq).
    """
    if config is None:
        config = LightRAGConfig()
    
    temp = temperature if temperature is not None else config.llm_temperature
    
    if config.use_bytez and config.bytez_api_key:
        from .bytez_llm import BytezGPT
        # BytezGPT currently does not implement token streaming.
        return BytezGPT(
            model_id=config.bytez_model,
            api_key=config.bytez_api_key,
            temperature=temp,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=config.llm_model,
            base_url=config.openai_api_base,
            api_key=config.openai_api_key,
            temperature=temp,
            timeout=config.llm_timeout,
            streaming=streaming,
            callbacks=list(callbacks) if callbacks else None,
        )


# Default configuration instance
default_config = LightRAGConfig()
