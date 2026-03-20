"""
Entity Deduplication and Normalization
"""
import re
import unicodedata
from typing import List, Dict, Any, Optional, Tuple
from langchain_huggingface import HuggingFaceEmbeddings
import numpy as np


class EntityDeduplicator:
    """Deduplicate and normalize entities using embeddings"""
    
    def __init__(self, embedding_model: Optional[HuggingFaceEmbeddings] = None, 
                 similarity_threshold: float = 0.85,
                 config=None):
        from ..config import default_config
        self.config = config or default_config
        
        if embedding_model is None:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=self.config.embedding_model
            )
        else:
            self.embedding_model = embedding_model
            
        self.threshold = similarity_threshold
        self.canonical_entities: Dict[str, Dict[str, Any]] = {}
        self.entity_embeddings: Dict[str, np.ndarray] = {}
        self.merge_map: Dict[str, str] = {}  # original_name -> canonical_name
        
        # Common aliases across faiths
        self.known_aliases = {
            "krishna": ["krsna", "kṛṣṇa", "shri krishna", "lord krishna"],
            "arjuna": ["arjun", "partha", "dhananjaya"],
            "karma": ["kamma"],
            "dharma": ["dhamma"],
            "moksha": ["moksa", "liberation", "mukti"],
            "yoga": ["yog"],
            "brahman": ["brahma", "the absolute"],
            "atman": ["atma", "soul", "self"],
        }
    
    def normalize_name(self, name: str) -> str:
        """
        Normalize entity name for comparison.
        
        Args:
            name: Original entity name
            
        Returns:
            Normalized name (lowercase, no diacritics)
        """
        # Convert to lowercase
        name = name.lower().strip()
        
        # Remove diacritics
        name = unicodedata.normalize('NFKD', name)
        name = ''.join(c for c in name if not unicodedata.combining(c))
        
        # Remove extra whitespace
        name = re.sub(r'\s+', ' ', name)
        
        return name
    
    def get_embedding(self, text: str) -> np.ndarray:
        """Get embedding for text"""
        return np.array(self.embedding_model.embed_query(text))
    
    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)
    
    def find_canonical(self, entity: Dict[str, Any]) -> Optional[Tuple[str, float]]:
        """
        Find if entity matches any canonical entity.
        
        Args:
            entity: Entity dictionary with name and description
            
        Returns:
            Tuple of (canonical_name, similarity) or None
        """
        name = entity.get("name", "")
        normalized = self.normalize_name(name)
        
        # Check known aliases first
        for canonical, aliases in self.known_aliases.items():
            if normalized == canonical or normalized in aliases:
                return (canonical, 1.0)
        
        # Check exact match
        if normalized in [self.normalize_name(k) for k in self.canonical_entities]:
            for canon_name in self.canonical_entities:
                if self.normalize_name(canon_name) == normalized:
                    return (canon_name, 1.0)
        
        # Semantic similarity check
        if not self.entity_embeddings:
            return None
            
        # Create embedding for new entity
        entity_text = f"{name}: {entity.get('description', '')}"
        entity_embedding = self.get_embedding(entity_text)
        
        best_match = None
        best_score = 0.0
        
        for canon_name, canon_embedding in self.entity_embeddings.items():
            similarity = self.cosine_similarity(entity_embedding, canon_embedding)
            if similarity > best_score and similarity >= self.threshold:
                best_score = similarity
                best_match = canon_name
        
        if best_match:
            return (best_match, best_score)
        
        return None
    
    def merge_entities(self, existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge new entity into existing canonical entity.
        
        Args:
            existing: Existing canonical entity
            new: New entity to merge
            
        Returns:
            Merged entity
        """
        merged = existing.copy()
        
        # Combine descriptions (keep unique parts)
        existing_desc = existing.get("description", "")
        new_desc = new.get("description", "")
        if new_desc and new_desc not in existing_desc:
            merged["description"] = f"{existing_desc} {new_desc}".strip()
        
        # Combine source texts
        existing_sources = existing.get("source_texts", [])
        if isinstance(existing_sources, str):
            existing_sources = [existing_sources]
        new_source = new.get("source_text", "")
        if new_source and new_source not in existing_sources:
            existing_sources.append(new_source)
        merged["source_texts"] = existing_sources
        
        # Combine source faiths
        existing_faiths = set(existing.get("source_faiths", []))
        if isinstance(existing.get("source_faith"), str):
            existing_faiths.add(existing["source_faith"])
        new_faith = new.get("source_faith", "")
        if new_faith:
            existing_faiths.add(new_faith)
        merged["source_faiths"] = list(existing_faiths)
        
        # Combine chunk IDs
        existing_chunks = existing.get("chunk_ids", [])
        new_chunk = new.get("chunk_id", "")
        if new_chunk and new_chunk not in existing_chunks:
            existing_chunks.append(new_chunk)
        merged["chunk_ids"] = existing_chunks
        
        # Keep most specific type
        if not existing.get("type") and new.get("type"):
            merged["type"] = new["type"]
        
        return merged
    
    def deduplicate(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate a list of entities.
        
        Args:
            entities: List of entity dictionaries
            
        Returns:
            List of deduplicated canonical entities
        """
        for entity in entities:
            name = entity.get("name", "")
            if not name:
                continue
            
            # Check if this matches an existing canonical entity
            match = self.find_canonical(entity)
            
            if match:
                canon_name, similarity = match
                # Initialize canonical entity if it was matched from known_aliases but doesn't exist yet
                if canon_name not in self.canonical_entities:
                    self.canonical_entities[canon_name] = {
                        "name": canon_name,
                        "type": entity.get("type", "CONCEPT"),
                        "description": entity.get("description", ""),
                        "source_texts": [],
                        "source_faiths": [],
                        "chunk_ids": []
                    }
                    self.entity_embeddings[canon_name] = self.get_embedding(f"{canon_name}: ")
                    
                # Merge with existing
                self.canonical_entities[canon_name] = self.merge_entities(
                    self.canonical_entities[canon_name],
                    entity
                )
                self.merge_map[name] = canon_name
            else:
                # Add as new canonical entity
                entity_text = f"{name}: {entity.get('description', '')}"
                embedding = self.get_embedding(entity_text)
                
                self.canonical_entities[name] = {
                    "name": name,
                    "type": entity.get("type", "CONCEPT"),
                    "description": entity.get("description", ""),
                    "source_texts": [entity.get("source_text", "")] if entity.get("source_text") else [],
                    "source_faiths": [entity.get("source_faith", "")] if entity.get("source_faith") else [],
                    "chunk_ids": [entity.get("chunk_id", "")] if entity.get("chunk_id") else []
                }
                self.entity_embeddings[name] = embedding
                self.merge_map[name] = name
        
        return list(self.canonical_entities.values())
    
    def get_canonical_name(self, name: str) -> str:
        """Get canonical name for an entity"""
        return self.merge_map.get(name, name)
    
    def deduplicate_relationships(self, relationships: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Deduplicate relationships by mapping to canonical entities.
        
        Args:
            relationships: List of relationship dictionaries
            
        Returns:
            Deduplicated relationships with canonical entity names
        """
        seen = set()
        deduplicated = []
        
        for rel in relationships:
            # Map to canonical names
            source = self.get_canonical_name(rel.get("source", ""))
            target = self.get_canonical_name(rel.get("target", ""))
            rel_type = rel.get("type", "RELATES_TO")
            
            # Create unique key
            key = (source, target, rel_type)
            
            if key not in seen:
                seen.add(key)
                deduplicated.append({
                    "source": source,
                    "target": target,
                    "type": rel_type,
                    "description": rel.get("description", ""),
                    "source_faith": rel.get("source_faith", ""),
                    "weight": 1
                })
            else:
                # Increment weight for duplicate relationships
                for ded_rel in deduplicated:
                    if (ded_rel["source"], ded_rel["target"], ded_rel["type"]) == key:
                        ded_rel["weight"] = ded_rel.get("weight", 1) + 1
                        break
        
        return deduplicated
