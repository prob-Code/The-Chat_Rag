"""
Hybrid Retrieval - Combines Graph and Vector Search
"""
from typing import Dict, Any, List, Optional
import networkx as nx

from .keyword_extractor import DualKeywordExtractor
from .graph_retriever import GraphRetriever
from .vector_retriever import VectorRetriever


class HybridRetriever:
    """Combines graph-based and vector-based retrieval"""
    
    def __init__(self, 
                 graph: nx.DiGraph,
                 keyword_extractor: Optional[DualKeywordExtractor] = None,
                 graph_retriever: Optional[GraphRetriever] = None,
                 vector_retriever: Optional[VectorRetriever] = None,
                 config=None):
        from ..config import default_config
        self.config = config or default_config
        
        self.graph = graph
        
        # Initialize components
        self.keyword_extractor = keyword_extractor or DualKeywordExtractor(config=config)
        self.vector_retriever = vector_retriever or VectorRetriever(config=config)

        # Reuse the same embedding model for graph + vector retrieval to avoid
        # loading the sentence-transformers model twice.
        embedding_model = getattr(self.vector_retriever, "embedding_model", None)
        self.graph_retriever = graph_retriever or GraphRetriever(
            graph,
            embedding_model=embedding_model,
            config=config,
        )
    
    def retrieve(self, query: str) -> Dict[str, Any]:
        """
        Perform hybrid retrieval combining graph and vector search.
        
        Args:
            query: User's question
            
        Returns:
            Combined retrieval results
        """
        # 1. Extract keywords
        print("Extracting keywords...")
        keywords = self.keyword_extractor.extract(query)
        low_keywords = keywords.get("low_level_keywords", [])
        high_keywords = keywords.get("high_level_keywords", [])
        
        print(f"  Low-level: {low_keywords}")
        print(f"  High-level: {high_keywords}")
        
        # 2. Graph retrieval
        print("Performing graph retrieval...")
        graph_results = self.graph_retriever.retrieve(low_keywords, high_keywords)
        
        # 3. Vector retrieval - search chunks
        print("Performing vector retrieval...")
        vector_chunks = self.vector_retriever.search(
            query, 
            top_k=self.config.top_k_chunks
        )
        
        # 4. Vector retrieval - search entities for additional matches
        all_keywords = low_keywords + high_keywords
        vector_entities = []
        for keyword in all_keywords[:3]:  # Limit to top 3
            matches = self.vector_retriever.search_entities(keyword, top_k=2)
            vector_entities.extend(matches)
        
        # 5. Merge results
        merged = self._merge_results(graph_results, vector_chunks, vector_entities)
        
        # 6. Add metadata
        merged["query"] = query
        merged["keywords"] = keywords
        
        return merged
    
    def _merge_results(self, 
                       graph_results: Dict[str, Any],
                       vector_chunks: List[Dict[str, Any]],
                       vector_entities: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Merge graph and vector retrieval results.
        
        Args:
            graph_results: Results from graph retriever
            vector_chunks: Chunks from vector search
            vector_entities: Entities from vector search
            
        Returns:
            Merged results
        """
        # Start with graph results
        merged = {
            "entities": graph_results.get("entities", []),
            "relationships": graph_results.get("relationships", []),
            "subgraph": graph_results.get("subgraph"),
            "chunks": []
        }
        
        # Add vector chunks with deduplication
        seen_chunks = set()
        for chunk in vector_chunks:
            chunk_id = chunk.get("id", "")
            if chunk_id not in seen_chunks:
                seen_chunks.add(chunk_id)
                merged["chunks"].append({
                    "text": chunk.get("text", ""),
                    "metadata": chunk.get("metadata", {}),
                    "score": 1 - chunk.get("distance", 0),  # Convert distance to similarity
                    "source": "vector"
                })
        
        # Add vector entities that weren't found through graph
        graph_entity_names = {e.get("name", "").lower() for e in merged["entities"]}
        
        for entity in vector_entities:
            metadata = entity.get("metadata", {})
            name = metadata.get("name", "")
            if name.lower() not in graph_entity_names:
                merged["entities"].append({
                    "name": name,
                    "type": metadata.get("type", "CONCEPT"),
                    "description": entity.get("text", "").split(": ", 1)[-1] if ": " in entity.get("text", "") else "",
                    "source": "vector",
                    "score": 1 - entity.get("distance", 0)
                })
                graph_entity_names.add(name.lower())
        
        # Calculate relevance scores
        merged["entity_count"] = len(merged["entities"])
        merged["relationship_count"] = len(merged["relationships"])
        merged["chunk_count"] = len(merged["chunks"])
        
        return merged
    
    def retrieve_with_expansion(self, query: str, max_hops: int = 2) -> Dict[str, Any]:
        """
        Perform retrieval with multi-hop graph expansion.
        
        Args:
            query: User's question
            max_hops: Maximum graph hops for expansion
            
        Returns:
            Retrieval results with expanded context
        """
        # Basic retrieval
        results = self.retrieve(query)
        
        if max_hops <= 1:
            return results
        
        # Get initial nodes
        initial_nodes = [e.get("name") for e in results.get("entities", []) if e.get("name")]
        
        # Expand additional hops
        expanded = set(initial_nodes)
        current_layer = set(initial_nodes)
        
        for hop in range(1, max_hops):
            next_layer = set()
            for node in current_layer:
                if self.graph.has_node(node):
                    next_layer.update(self.graph.successors(node))
                    next_layer.update(self.graph.predecessors(node))
            
            next_layer -= expanded
            expanded.update(next_layer)
            current_layer = next_layer
        
        # Build expanded subgraph
        existing_nodes = [n for n in expanded if self.graph.has_node(n)]
        expanded_subgraph = self.graph.subgraph(existing_nodes).copy()
        
        # Update results
        results["expanded_subgraph"] = expanded_subgraph
        results["expansion_hops"] = max_hops
        results["total_nodes_expanded"] = len(existing_nodes)
        
        return results
