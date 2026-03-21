"""
Vector-Based Retrieval using ChromaDB
"""
from typing import List, Dict, Any, Optional
from pathlib import Path
import chromadb
from chromadb.config import Settings
from langchain_huggingface import HuggingFaceEmbeddings


class VectorRetriever:
    """Vector similarity search using ChromaDB"""
    
    def __init__(self, embedding_model: Optional[HuggingFaceEmbeddings] = None,
                 collection_name: str = "lightrag_chunks",
                 config=None):
        from ..config import default_config
        self.config = config or default_config
        
        if embedding_model is None:
            self.embedding_model = HuggingFaceEmbeddings(
                model_name=self.config.embedding_model
            )
        else:
            self.embedding_model = embedding_model
        
        # Initialize ChromaDB
        Path(self.config.chromadb_path).mkdir(parents=True, exist_ok=True)
        
        self.client = chromadb.PersistentClient(
            path=self.config.chromadb_path,
            settings=Settings(anonymized_telemetry=False)
        )
        
        self.collection_name = collection_name
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
    
    def add_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        """
        Add text chunks to vector store.
        
        Args:
            chunks: List of dictionaries with 'text', 'id', and optional metadata
        """
        if not chunks:
            return
        
        texts = []
        ids = []
        metadatas = []
        
        for i, chunk in enumerate(chunks):
            text = chunk.get("text", "")
            chunk_id = chunk.get("id", f"chunk_{i}")
            metadata = {
                "source_faith": chunk.get("source_faith", ""),
                "chunk_index": chunk.get("chunk_index", i),
                "source_file": chunk.get("source_file", "")
            }
            
            texts.append(text)
            ids.append(chunk_id)
            metadatas.append(metadata)
        
        # Generate embeddings
        embeddings = self.embedding_model.embed_documents(texts)
        
        # Add to collection
        self.collection.add(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        
        print(f"Added {len(chunks)} chunks to vector store")
    
    def add_entities(self, entities: List[Dict[str, Any]], 
                     collection_name: str = "lightrag_entities") -> None:
        """
        Add entity embeddings to a separate collection.
        
        Args:
            entities: List of entity dictionaries
            collection_name: Name for entity collection
        """
        if not entities:
            print("No entities to add to vector store")
            return
            
        entity_collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )
        
        texts = []
        ids = []
        metadatas = []
        
        for entity in entities:
            name = entity.get("name", "")
            description = entity.get("description", "")
            text = f"{name}: {description}"
            
            texts.append(text)
            ids.append(f"entity_{name}")
            metadatas.append({
                "name": name,
                "type": entity.get("type", "CONCEPT"),
                "source_faiths": str(entity.get("source_faiths", []))
            })
        
        embeddings = self.embedding_model.embed_documents(texts)
        
        entity_collection.add(
            documents=texts,
            embeddings=embeddings,
            ids=ids,
            metadatas=metadatas
        )
        
        print(f"Added {len(entities)} entities to vector store")
    
    def search(self, query: str, top_k: int = 4, 
               filter_metadata: Optional[Dict] = None) -> List[Dict[str, Any]]:
        """
        Search for similar chunks.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
            
        Returns:
            List of matched chunks with scores
        """
        query_embedding = self.embedding_model.embed_query(query)
        
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            where=filter_metadata
        )
        
        matches = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                matches.append({
                    "text": doc,
                    "id": results["ids"][0][i] if results["ids"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0
                })
        
        return matches
    
    def search_entities(self, query: str, top_k: int = 5,
                        collection_name: str = "lightrag_entities") -> List[Dict[str, Any]]:
        """
        Search for similar entities.
        
        Args:
            query: Search query
            top_k: Number of results
            collection_name: Entity collection name
            
        Returns:
            List of matched entities with scores
        """
        try:
            entity_collection = self.client.get_collection(name=collection_name)
        except:
            return []
        
        query_embedding = self.embedding_model.embed_query(query)
        
        results = entity_collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k
        )
        
        matches = []
        if results and results["documents"]:
            for i, doc in enumerate(results["documents"][0]):
                matches.append({
                    "text": doc,
                    "id": results["ids"][0][i] if results["ids"] else "",
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else 0
                })
        
        return matches
    
    def delete_collection(self, collection_name: Optional[str] = None) -> None:
        """Delete a collection"""
        name = collection_name or self.collection_name
        try:
            self.client.delete_collection(name=name)
            print(f"Deleted collection: {name}")
        except:
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get collection statistics"""
        return {
            "collection_name": self.collection_name,
            "count": self.collection.count()
        }
