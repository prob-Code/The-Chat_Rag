"""
Knowledge Graph Builder using NetworkX
"""
import json
import pickle
from pathlib import Path
from typing import List, Dict, Any, Optional
import networkx as nx


class KnowledgeGraphBuilder:
    """Build and manage knowledge graph from extracted entities and relations"""
    
    def __init__(self, config=None):
        from ..config import default_config
        self.config = config or default_config
        self.graph = nx.DiGraph()
        
    def add_entity(self, entity: Dict[str, Any]) -> None:
        """
        Add an entity as a node in the graph.
        
        Args:
            entity: Entity dictionary with name, type, description, etc.
        """
        name = entity.get("name", "")
        if not name:
            return
            
        if self.graph.has_node(name):
            # Update existing node
            existing = dict(self.graph.nodes[name])
            
            # Merge source faiths
            existing_faiths = set(existing.get("source_faiths", []))
            new_faiths = entity.get("source_faiths", [])
            if isinstance(new_faiths, str):
                new_faiths = [new_faiths]
            existing_faiths.update(new_faiths)
            
            # Merge descriptions
            existing_desc = existing.get("description", "")
            new_desc = entity.get("description", "")
            if new_desc and new_desc not in existing_desc:
                existing["description"] = f"{existing_desc} {new_desc}".strip()
            
            existing["source_faiths"] = list(existing_faiths)
            self.graph.nodes[name].update(existing)
        else:
            # Add new node
            self.graph.add_node(
                name,
                type=entity.get("type", "CONCEPT"),
                description=entity.get("description", ""),
                source_faiths=entity.get("source_faiths", []),
                source_texts=entity.get("source_texts", []),
                chunk_ids=entity.get("chunk_ids", [])
            )
    
    def add_relationship(self, relation: Dict[str, Any]) -> None:
        """
        Add a relationship as an edge in the graph.
        
        Args:
            relation: Relationship dictionary with source, target, type, etc.
        """
        source = relation.get("source", "")
        target = relation.get("target", "")
        rel_type = relation.get("type", "RELATES_TO")
        
        if not source or not target:
            return
        
        # Ensure nodes exist
        if not self.graph.has_node(source):
            self.graph.add_node(source, type="CONCEPT", description="")
        if not self.graph.has_node(target):
            self.graph.add_node(target, type="CONCEPT", description="")
        
        # Check if edge exists
        if self.graph.has_edge(source, target):
            # Update weight
            self.graph[source][target]["weight"] = self.graph[source][target].get("weight", 1) + 1
        else:
            # Add new edge
            self.graph.add_edge(
                source,
                target,
                type=rel_type,
                description=relation.get("description", ""),
                source_faith=relation.get("source_faith", ""),
                weight=relation.get("weight", 1)
            )
    
    def build_from_extractions(self, entities: List[Dict[str, Any]], 
                                relationships: List[Dict[str, Any]]) -> nx.DiGraph:
        """
        Build graph from extracted and deduplicated entities/relationships.
        
        Args:
            entities: List of deduplicated entity dictionaries
            relationships: List of deduplicated relationship dictionaries
            
        Returns:
            The constructed NetworkX DiGraph
        """
        print(f"Building graph from {len(entities)} entities and {len(relationships)} relationships...")
        
        # Add all entities
        for entity in entities:
            self.add_entity(entity)
        
        # Add all relationships
        for relation in relationships:
            self.add_relationship(relation)
        
        # Compute centrality scores
        self._compute_metrics()
        
        print(f"Graph built: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        
        return self.graph
    
    def _compute_metrics(self) -> None:
        """Compute and store graph metrics for each node"""
        if self.graph.number_of_nodes() == 0:
            return
            
        # PageRank for importance
        try:
            pagerank = nx.pagerank(self.graph)
            for node, score in pagerank.items():
                self.graph.nodes[node]["pagerank"] = score
        except:
            pass
        
        # Degree centrality
        in_degree = dict(self.graph.in_degree())
        out_degree = dict(self.graph.out_degree())
        
        for node in self.graph.nodes():
            self.graph.nodes[node]["in_degree"] = in_degree.get(node, 0)
            self.graph.nodes[node]["out_degree"] = out_degree.get(node, 0)
    
    def get_node(self, name: str) -> Optional[Dict[str, Any]]:
        """Get node attributes by name"""
        if self.graph.has_node(name):
            return dict(self.graph.nodes[name])
        return None
    
    def get_neighbors(self, name: str, direction: str = "both") -> List[str]:
        """
        Get neighboring nodes.
        
        Args:
            name: Node name
            direction: "in", "out", or "both"
            
        Returns:
            List of neighbor node names
        """
        if not self.graph.has_node(name):
            return []
        
        neighbors = set()
        
        if direction in ("out", "both"):
            neighbors.update(self.graph.successors(name))
        
        if direction in ("in", "both"):
            neighbors.update(self.graph.predecessors(name))
        
        return list(neighbors)
    
    def get_subgraph(self, nodes: List[str]) -> nx.DiGraph:
        """
        Extract subgraph containing specified nodes and edges between them.
        
        Args:
            nodes: List of node names to include
            
        Returns:
            Subgraph as NetworkX DiGraph
        """
        existing_nodes = [n for n in nodes if self.graph.has_node(n)]
        return self.graph.subgraph(existing_nodes).copy()
    
    def get_paths(self, source: str, target: str, max_length: int = 3) -> List[List[str]]:
        """
        Find all paths between two nodes up to max_length.
        
        Args:
            source: Source node name
            target: Target node name
            max_length: Maximum path length
            
        Returns:
            List of paths (each path is a list of node names)
        """
        if not self.graph.has_node(source) or not self.graph.has_node(target):
            return []
        
        try:
            paths = list(nx.all_simple_paths(
                self.graph, source, target, cutoff=max_length
            ))
            return paths
        except nx.NetworkXNoPath:
            return []
    
    def save(self, path: Optional[str] = None) -> None:
        """Save graph to file"""
        path = path or self.config.graph_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'wb') as f:
            pickle.dump(self.graph, f)
        
        # Also save as JSON for inspection
        json_path = path.replace('.gpickle', '.json')
        graph_data = {
            "nodes": [
                {"name": n, **dict(self.graph.nodes[n])}
                for n in self.graph.nodes()
            ],
            "edges": [
                {"source": u, "target": v, **dict(self.graph.edges[u, v])}
                for u, v in self.graph.edges()
            ]
        }
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
        print(f"Graph saved to {path}")
    
    def load(self, path: Optional[str] = None) -> nx.DiGraph:
        """Load graph from file"""
        path = path or self.config.graph_path
        
        with open(path, 'rb') as f:
            self.graph = pickle.load(f)
        
        print(f"Graph loaded: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges")
        return self.graph
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get graph statistics"""
        return {
            "num_nodes": self.graph.number_of_nodes(),
            "num_edges": self.graph.number_of_edges(),
            "node_types": self._count_by_attribute("type"),
            "edge_types": self._count_edge_types(),
            "avg_degree": sum(dict(self.graph.degree()).values()) / max(1, self.graph.number_of_nodes())
        }
    
    def _count_by_attribute(self, attr: str) -> Dict[str, int]:
        """Count nodes by attribute value"""
        counts = {}
        for node in self.graph.nodes():
            value = self.graph.nodes[node].get(attr, "UNKNOWN")
            counts[value] = counts.get(value, 0) + 1
        return counts
    
    def _count_edge_types(self) -> Dict[str, int]:
        """Count edges by type"""
        counts = {}
        for u, v in self.graph.edges():
            edge_type = self.graph.edges[u, v].get("type", "UNKNOWN")
            counts[edge_type] = counts.get(edge_type, 0) + 1
        return counts
