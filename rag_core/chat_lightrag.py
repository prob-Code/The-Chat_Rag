"""
LightRAG Chat Interface
Graph-enhanced spiritual guidance system
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_huggingface import HuggingFaceEmbeddings

from rag_core.config import LightRAGConfig
from rag_core.indexing import KnowledgeGraphBuilder
from rag_core.retrieval import HybridRetriever, VectorRetriever
from rag_core.generation import ContextBuilder, ReflectionResponseGenerator


class LightRAGChat:
    """LightRAG-powered chat interface"""
    
    def __init__(self, config: LightRAGConfig = None):
        self.config = config or LightRAGConfig()
        
        print("Initializing LightRAG Chat...")
        
        # Load embedding model
        print("  Loading embedding model (used to embed your questions)...")
        self.embedding_model = HuggingFaceEmbeddings(
            model_name=self.config.embedding_model
        )
        
        # Load knowledge graph
        print("  Loading knowledge graph...")
        self.graph_builder = KnowledgeGraphBuilder(config=self.config)
        try:
            self.graph = self.graph_builder.load()
        except FileNotFoundError:
            print("\n⚠ Knowledge graph not found!")
            print("Please run ingest_lightrag.py first to build the graph.")
            raise
        
        # Initialize vector retriever
        print("  Initializing vector retriever...")
        self.vector_retriever = VectorRetriever(
            embedding_model=self.embedding_model,
            config=self.config
        )
        
        # Initialize hybrid retriever
        print("  Initializing hybrid retriever...")
        self.hybrid_retriever = HybridRetriever(
            graph=self.graph,
            vector_retriever=self.vector_retriever,
            config=self.config
        )
        
        # Initialize context builder
        self.context_builder = ContextBuilder(config=self.config)
        
        # Initialize response generator
        print("  Initializing response generator...")
        self.response_generator = ReflectionResponseGenerator(config=self.config)
        
        print("✓ LightRAG Chat initialized!\n")
    
    def chat(self, query: str, verbose: bool = False) -> str:
        """
        Process a query and generate response.
        
        Args:
            query: User's question
            verbose: Print retrieval details
            
        Returns:
            Generated response
        """
        # 1. Hybrid retrieval
        if verbose:
            print("\n--- Retrieval ---")
        
        results = self.hybrid_retriever.retrieve(query)
        
        if verbose:
            print(f"Found {results['entity_count']} entities")
            print(f"Found {results['relationship_count']} relationships")
            print(f"Found {results['chunk_count']} chunks")
        
        # 2. Build context
        context = self.context_builder.build(results)
        
        if verbose:
            stats = self.context_builder.get_context_stats(context)
            print(f"Context: {stats['word_count']} words")
        
        # 3. Generate response
        keywords = results.get("keywords", {})
        response = self.response_generator.generate_auto(query, context, keywords)
        
        return response
    
    def get_graph_info(self, entity_name: str) -> dict:
        """Get information about an entity in the graph"""
        return self.graph_builder.get_node(entity_name)
    
    def get_statistics(self) -> dict:
        """Get system statistics"""
        graph_stats = self.graph_builder.get_statistics()
        vector_stats = self.vector_retriever.get_stats()
        
        return {
            "graph": graph_stats,
            "vector": vector_stats
        }


def main():
    """Main chat loop"""
    # Initialize config (this now loads from .env)
    config = LightRAGConfig()
    
    # Check if graph exists
    if not os.path.exists(config.graph_path):
        print("\n⚠ LightRAG not initialized!")
        print("Please run one of:")
        print("  python rag_core/ingest_lightrag.py")
        print("  python ingest_lightrag_safe.py")
        print("This will build the knowledge graph + ChromaDB store from your documents.\n")
        return
    
    # Initialize chat
    try:
        chat = LightRAGChat(config)
    except FileNotFoundError:
        return
    
    # Print welcome message
    print("="*60)
    print("       LIGHTRAG SPIRITUAL GUIDANCE SYSTEM")
    print("="*60)
    print("\nThis system uses graph-enhanced retrieval to provide")
    print("deeper, more connected insights from sacred texts.")
    print("\nCommands:")
    print("  'exit'  - Exit the chat")
    print("  'stats' - Show system statistics")
    print("  'info <entity>' - Get info about an entity")
    print("  'verbose' - Toggle verbose mode")
    print("="*60)
    
    verbose = False
    
    while True:
        try:
            query = input("\n🙏 Your question: ").strip()
            
            if not query:
                continue
            
            if query.lower() == "exit":
                print("\nMay peace be with you. 🙏")
                break
            
            if query.lower() == "verbose":
                verbose = not verbose
                print(f"Verbose mode: {'ON' if verbose else 'OFF'}")
                continue
            
            if query.lower() == "stats":
                stats = chat.get_statistics()
                print("\n--- System Statistics ---")
                print(f"Graph: {stats['graph']['num_nodes']} nodes, {stats['graph']['num_edges']} edges")
                print(f"Vector Store: {stats['vector']['count']} chunks")
                continue
            
            if query.lower().startswith("info "):
                entity = query[5:].strip()
                info = chat.get_graph_info(entity)
                if info:
                    print(f"\n--- {entity} ---")
                    for key, value in info.items():
                        print(f"  {key}: {value}")
                else:
                    print(f"Entity '{entity}' not found in graph.")
                continue
            
            # Process query
            print("\n🔍 Searching wisdom...")
            response = chat.chat(query, verbose=verbose)
            
            print("\n" + "─"*60)
            print(response)
            print("─"*60)
            
        except KeyboardInterrupt:
            print("\n\nMay peace be with you. 🙏")
            break
        except Exception as e:
            print(f"\n⚠ Error: {e}")
            continue


if __name__ == "__main__":
    main()
