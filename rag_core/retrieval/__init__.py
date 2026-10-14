"""
LightRAG Retrieval Module
"""

from typing import TYPE_CHECKING

from .keyword_extractor import DualKeywordExtractor
from .graph_retriever import GraphRetriever

if TYPE_CHECKING:
    from .hybrid_retriever import HybridRetriever
    from .vector_retriever import VectorRetriever

__all__ = [
    "DualKeywordExtractor",
    "GraphRetriever",
    "VectorRetriever",
    "HybridRetriever"
]


def __getattr__(name):
    """Load Chroma-backed retrievers only when they are actually requested."""
    if name == "VectorRetriever":
        from .vector_retriever import VectorRetriever
        return VectorRetriever
    if name == "HybridRetriever":
        from .hybrid_retriever import HybridRetriever
        return HybridRetriever
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
