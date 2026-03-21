"""
Graph-Based Retrieval
"""
from typing import List, Dict, Any, Optional, Set
import networkx as nx
import numpy as np
from langchain_huggingface import HuggingFaceEmbeddings


class GraphRetriever:
    """Retrieve relevant nodes and subgraphs from knowledge graph"""
    
    def __init__(self, graph: nx.DiGraph, 
                 embedding_model: Optional[HuggingFaceEmbeddings] = None,
                 config=None):
        from ..config import default_config
        self.config = config or default_config
        self.graph = graph
        
        if embedding_model is None:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=self.config.embedding_model
            )
        else:
            self.embedding_model = embedding_model
        
        # Precompute node embeddings
        self.node_embeddings: Dict[str, np.ndarray] = {}
        self._precompute_embeddings()
    
    def _precompute_embeddings(self) -> None:
        """Precompute embeddings for all nodes"""
        print("Precomputing node embeddings...")
        for node in self.graph.nodes():
            node_data = self.graph.nodes[node]
            text = f"{node}: {node_data.get('description', '')}"
            self.node_embeddings[node] = np.array(
                self.embedding_model.embed_query(text)
            )
        print(f"Computed embeddings for {len(self.node_embeddings)} nodes")
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    def find_matching_nodes(self, keywords: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Find nodes matching keywords using exact and semantic matching.
        
        Args:
            keywords: List of keywords to match
            top_k: Maximum number of nodes to return
            
        Returns:
            List of matched nodes with scores
        """
        matches = []
        seen_nodes = set()
        
        for keyword in keywords:
            keyword_lower = keyword.lower()
            
            # 1. Exact match on node names
            for node in self.graph.nodes():
                if keyword_lower in node.lower() and node not in seen_nodes:
                    matches.append({
                        "node": node,
                        "score": 1.0,
                        "match_type": "exact",
                        "keyword": keyword
                    })
                    seen_nodes.add(node)
            
            # 2. Semantic match
            if keyword and self.node_embeddings:
                keyword_embedding = np.array(
                    self.embedding_model.embed_query(keyword)
                )
                
                for node, node_embedding in self.node_embeddings.items():
                    if node in seen_nodes:
                        continue
                    
                    similarity = self._cosine_similarity(keyword_embedding, node_embedding)
                    
                    if similarity > 0.5:  # Threshold for semantic match
                        matches.append({
                            "node": node,
                            "score": similarity,
                            "match_type": "semantic",
                            "keyword": keyword
                        })
                        seen_nodes.add(node)
        
        # Sort by score and return top_k
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:top_k]
    
    def expand_one_hop(self, nodes: List[str]) -> Set[str]:
        """
        Expand nodes to include one-hop neighbors.
        
        Args:
            nodes: List of node names
            
        Returns:
            Set of expanded node names
        """
        expanded = set(nodes)
        
        for node in nodes:
            if self.graph.has_node(node):
                # Add successors (outgoing edges)
                expanded.update(self.graph.successors(node))
                # Add predecessors (incoming edges)
                expanded.update(self.graph.predecessors(node))
        
        return expanded
    
    def build_subgraph(self, nodes: Set[str]) -> nx.DiGraph:
        """
        Build subgraph from node set.
        
        Args:
            nodes: Set of node names
            
        Returns:
            Subgraph containing the nodes and edges between them
        """
        existing_nodes = [n for n in nodes if self.graph.has_node(n)]
        return self.graph.subgraph(existing_nodes).copy()
    
    def get_node_info(self, node: str) -> Dict[str, Any]:
        """Get detailed information about a node"""
        if not self.graph.has_node(node):
            return {}
        
        node_data = dict(self.graph.nodes[node])
        node_data["name"] = node
        node_data["neighbors"] = {
            "outgoing": list(self.graph.successors(node)),
            "incoming": list(self.graph.predecessors(node))
        }
        
        # Get edges info
        node_data["outgoing_edges"] = [
            {
                "target": target,
                "type": self.graph.edges[node, target].get("type", ""),
                "description": self.graph.edges[node, target].get("description", "")
            }
            for target in self.graph.successors(node)
        ]
        
        node_data["incoming_edges"] = [
            {
                "source": source,
                "type": self.graph.edges[source, node].get("type", ""),
                "description": self.graph.edges[source, node].get("description", "")
            }
            for source in self.graph.predecessors(node)
        ]
        
        return node_data
    
    def retrieve(self, low_keywords: List[str], high_keywords: List[str]) -> Dict[str, Any]:
        """
        Perform graph-based retrieval.
        
        Args:
            low_keywords: Specific keywords (entity names, concepts)
            high_keywords: Abstract theme keywords
            
        Returns:
            Dictionary with matched nodes, expanded nodes, subgraph, and context
        """
        # 1. Find nodes matching low-level keywords (specific)
        low_matches = self.find_matching_nodes(low_keywords, top_k=self.config.top_k_entities)
        low_nodes = [m["node"] for m in low_matches]
        
        # 2. Find nodes matching high-level keywords (thematic)
        high_matches = self.find_matching_nodes(high_keywords, top_k=self.config.top_k_entities)
        high_nodes = [m["node"] for m in high_matches]
        
        # 3. Expand low-level matches one hop
        expanded_nodes = self.expand_one_hop(low_nodes)
        
        # 4. Combine all nodes
        all_nodes = expanded_nodes.union(set(high_nodes))
        
        # 5. Build subgraph
        subgraph = self.build_subgraph(all_nodes)
        
        # 6. Get detailed node info
        entities = []
        for node in all_nodes:
            if self.graph.has_node(node):
                info = self.get_node_info(node)
                entities.append(info)
        
        # 7. Get relationships from subgraph
        relationships = []
        for u, v in subgraph.edges():
            edge_data = dict(subgraph.edges[u, v])
            relationships.append({
                "source": u,
                "target": v,
                **edge_data
            })
        
        return {
            "low_level_matches": low_matches,
            "high_level_matches": high_matches,
            "expanded_nodes": list(expanded_nodes),
            "all_nodes": list(all_nodes),
            "entities": entities,
            "relationships": relationships,
            "subgraph": subgraph
        }
