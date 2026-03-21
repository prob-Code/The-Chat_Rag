"""
Context Builder - Constructs structured context from retrieval results
"""
from typing import Dict, Any, List, Optional
import networkx as nx


class ContextBuilder:
    """Build structured context from retrieval results"""
    
    def __init__(self, config=None):
        from ..config import default_config
        self.config = config or default_config
    
    def build(self, retrieval_results: Dict[str, Any]) -> str:
        """
        Build structured context string from retrieval results.
        
        Args:
            retrieval_results: Results from hybrid retriever
            
        Returns:
            Formatted context string for LLM
        """
        context_parts = []
        
        # 1. Entity summaries
        entities = retrieval_results.get("entities", [])
        if entities:
            entity_section = self._build_entity_summaries(entities)
            context_parts.append(entity_section)
        
        # 2. Relationship summaries
        relationships = retrieval_results.get("relationships", [])
        if relationships:
            relation_section = self._build_relationship_summaries(relationships)
            context_parts.append(relation_section)
        
        # 3. Multi-hop context from subgraph
        subgraph = retrieval_results.get("subgraph")
        if subgraph and subgraph.number_of_nodes() > 0:
            multihop_section = self._build_multihop_context(subgraph)
            if multihop_section:
                context_parts.append(multihop_section)
        
        # 4. Supporting text chunks
        chunks = retrieval_results.get("chunks", [])
        if chunks:
            chunks_section = self._build_chunk_context(chunks)
            context_parts.append(chunks_section)
        
        return "\n\n".join(context_parts)
    
    def _build_entity_summaries(self, entities: List[Dict[str, Any]]) -> str:
        """Build entity summary section"""
        lines = ["=== KEY CONCEPTS ==="]
        
        # Sort by importance (pagerank if available)
        sorted_entities = sorted(
            entities,
            key=lambda e: e.get("pagerank", 0),
            reverse=True
        )
        
        for entity in sorted_entities[:10]:  # Limit to top 10
            name = entity.get("name", "Unknown")
            entity_type = entity.get("type", "CONCEPT")
            description = entity.get("description", "")
            faiths = entity.get("source_faiths", [])
            
            faith_str = f" [{', '.join(faiths)}]" if faiths else ""
            
            lines.append(f"• **{name}** ({entity_type}){faith_str}")
            if description:
                # Truncate long descriptions
                desc = description[:200] + "..." if len(description) > 200 else description
                lines.append(f"  {desc}")
        
        return "\n".join(lines)
    
    def _build_relationship_summaries(self, relationships: List[Dict[str, Any]]) -> str:
        """Build relationship summary section"""
        lines = ["=== CONNECTIONS ==="]
        
        # Sort by weight
        sorted_rels = sorted(
            relationships,
            key=lambda r: r.get("weight", 1),
            reverse=True
        )
        
        for rel in sorted_rels[:15]:  # Limit to top 15
            source = rel.get("source", "?")
            target = rel.get("target", "?")
            rel_type = rel.get("type", "relates to")
            description = rel.get("description", "")
            
            line = f"• {source} --[{rel_type}]--> {target}"
            if description:
                line += f": {description[:100]}"
            
            lines.append(line)
        
        return "\n".join(lines)
    
    def _build_multihop_context(self, subgraph: nx.DiGraph) -> str:
        """Build multi-hop reasoning paths from subgraph"""
        lines = ["=== REASONING PATHS ==="]
        
        # Find important nodes (high degree)
        nodes_by_degree = sorted(
            subgraph.nodes(),
            key=lambda n: subgraph.degree(n),
            reverse=True
        )
        
        if len(nodes_by_degree) < 2:
            return ""
        
        # Find paths between top nodes
        paths_found = []
        top_nodes = nodes_by_degree[:5]
        
        for i, source in enumerate(top_nodes):
            for target in top_nodes[i+1:]:
                try:
                    paths = list(nx.all_simple_paths(
                        subgraph, source, target, cutoff=3
                    ))
                    for path in paths[:2]:  # Limit paths per pair
                        paths_found.append(path)
                except:
                    pass
        
        # Format paths
        for path in paths_found[:5]:  # Limit total paths
            path_str = " → ".join(path)
            lines.append(f"• {path_str}")
        
        if len(lines) == 1:  # Only header
            return ""
        
        return "\n".join(lines)
    
    def _build_chunk_context(self, chunks: List[Dict[str, Any]]) -> str:
        """Build supporting text chunk section"""
        lines = ["=== RELEVANT PASSAGES ==="]
        
        # Sort by score
        sorted_chunks = sorted(
            chunks,
            key=lambda c: c.get("score", 0),
            reverse=True
        )
        
        for i, chunk in enumerate(sorted_chunks[:5], 1):  # Limit to top 5
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            source = metadata.get("source_faith", "")
            
            # Clean and truncate text
            text = text.strip()
            if len(text) > 500:
                text = text[:500] + "..."
            
            source_str = f" ({source})" if source else ""
            lines.append(f"\n[{i}]{source_str}:")
            lines.append(text)
        
        return "\n".join(lines)
    
    def build_minimal(self, retrieval_results: Dict[str, Any]) -> str:
        """
        Build minimal context for simpler queries.
        
        Args:
            retrieval_results: Results from retriever
            
        Returns:
            Minimal context string
        """
        parts = []
        
        # Just top entities
        entities = retrieval_results.get("entities", [])[:5]
        if entities:
            for e in entities:
                parts.append(f"• {e.get('name', '')}: {e.get('description', '')}")
        
        # Just top chunks
        chunks = retrieval_results.get("chunks", [])[:3]
        if chunks:
            for c in chunks:
                parts.append(f"\n{c.get('text', '')}")
        
        return "\n".join(parts)
    
    def get_context_stats(self, context: str) -> Dict[str, Any]:
        """Get statistics about generated context"""
        return {
            "total_length": len(context),
            "word_count": len(context.split()),
            "section_count": context.count("===")
        }
