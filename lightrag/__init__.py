"""
LightRAG - Graph-Enhanced Retrieval Augmented Generation
A multi-faith, clarity-oriented Decision Support System
"""

try:
    from .config import LightRAGConfig
    __all__ = ["LightRAGConfig"]
except ImportError:
    # config module may not be available in all environments
    LightRAGConfig = None
    __all__ = []

__version__ = "1.0.0"
