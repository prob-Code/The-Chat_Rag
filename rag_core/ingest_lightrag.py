"""
LightRAG Ingestion Script
Extracts entities and relationships from religious texts and builds knowledge graph
"""
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from rag_core.config import LightRAGConfig
from rag_core.indexing import EntityRelationExtractor, EntityDeduplicator, KnowledgeGraphBuilder
from rag_core.retrieval import VectorRetriever


def ingest_document(pdf_path: str, source_faith: str, config: LightRAGConfig):
    """
    Ingest a document into LightRAG.
    
    Args:
        pdf_path: Path to PDF file
        source_faith: Name of the faith/text tradition
        config: LightRAG configuration
    """
    print(f"\n{'='*60}")
    print(f"Ingesting: {pdf_path}")
    print(f"Source: {source_faith}")
    print(f"{'='*60}\n")
    
    # 1. Load PDF
    print("Step 1: Loading PDF...")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    print(f"  Loaded {len(documents)} pages")
    
    # 2. Chunk the document
    print("\nStep 2: Chunking document...")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=config.chunk_size,
        chunk_overlap=config.chunk_overlap
    )
    chunks = splitter.split_documents(documents)
    print(f"  Created {len(chunks)} chunks")
    
    # 3. Extract entities and relationships
    print("\nStep 3: Extracting entities and relationships...")
    extractor = EntityRelationExtractor(config=config)
    
    all_extractions = []
    for i, chunk in enumerate(chunks):
        print(f"  Processing chunk {i+1}/{len(chunks)}...", end="\r")
        extraction = extractor.extract(
            chunk.page_content,
            source_faith=source_faith,
            chunk_id=f"{source_faith}_{i}"
        )
        all_extractions.append(extraction)
    
    # Merge all extractions
    merged = extractor.merge_extractions(all_extractions)
    print(f"\n  Extracted {len(merged['entities'])} entities")
    print(f"  Extracted {len(merged['relationships'])} relationships")
    
    # 4. Deduplicate entities
    print("\nStep 4: Deduplicating entities...")
    embedding_model = HuggingFaceEmbeddings(model_name=config.embedding_model)
    deduplicator = EntityDeduplicator(
        embedding_model=embedding_model,
        similarity_threshold=config.similarity_threshold,
        config=config
    )
    
    deduplicated_entities = deduplicator.deduplicate(merged["entities"])
    deduplicated_relationships = deduplicator.deduplicate_relationships(merged["relationships"])
    
    print(f"  Deduplicated to {len(deduplicated_entities)} unique entities")
    print(f"  Deduplicated to {len(deduplicated_relationships)} unique relationships")
    
    # 5. Build knowledge graph
    print("\nStep 5: Building knowledge graph...")
    graph_builder = KnowledgeGraphBuilder(config=config)
    graph = graph_builder.build_from_extractions(
        deduplicated_entities,
        deduplicated_relationships
    )
    
    # 6. Save graph
    print("\nStep 6: Saving knowledge graph...")
    graph_builder.save()
    
    # 7. Store chunks in vector database
    print("\nStep 7: Storing chunks in vector database...")
    vector_store = VectorRetriever(
        embedding_model=embedding_model,
        config=config
    )
    
    chunk_data = [
        {
            "text": chunk.page_content,
            "id": f"{source_faith}_chunk_{i}",
            "source_faith": source_faith,
            "chunk_index": i,
            "source_file": pdf_path
        }
        for i, chunk in enumerate(chunks)
    ]
    vector_store.add_chunks(chunk_data)
    
    # 8. Store entities in vector database
    print("\nStep 8: Storing entities in vector database...")
    vector_store.add_entities(deduplicated_entities)
    
    # Print statistics
    print("\n" + "="*60)
    print("INGESTION COMPLETE")
    print("="*60)
    stats = graph_builder.get_statistics()
    print(f"Graph Statistics:")
    print(f"  - Nodes: {stats['num_nodes']}")
    print(f"  - Edges: {stats['num_edges']}")
    print(f"  - Node types: {stats['node_types']}")
    print(f"  - Edge types: {stats['edge_types']}")
    print(f"\nVector Store:")
    print(f"  - Chunks stored: {len(chunk_data)}")
    print(f"  - Entities stored: {len(deduplicated_entities)}")
    print("="*60)
    
    return graph_builder, vector_store


def main():
    """Main ingestion function"""
    # Initialize config (this now loads from .env)
    config = LightRAGConfig()
    
    # Ingest Bhagavad Gita
    pdf_path = "data/bgita.pdf"
    
    if not os.path.exists(pdf_path):
        print(f"Error: PDF not found at {pdf_path}")
        print("Please ensure the file exists.")
        return
    
    ingest_document(pdf_path, "Bhagavad Gita", config)
    
    print("\n✓ LightRAG ingestion complete!")
    print("You can now run chat_lightrag.py to interact with the system.")


if __name__ == "__main__":
    main()
