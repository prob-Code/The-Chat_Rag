"""
LightRAG Safe Ingestion Script
- Rate-limited to avoid hitting API limits
- Uses larger chunks + sampling to minimize API calls
- Saves progress after each extraction (resumable)
- Stores everything in ChromaDB
"""
import os
import sys
import json
import time
import math

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings

from lightrag.config import LightRAGConfig
from lightrag.indexing import EntityRelationExtractor, EntityDeduplicator, KnowledgeGraphBuilder
from lightrag.retrieval import VectorRetriever

# -- Configuration for API-safe ingestion --
EXTRACTION_CHUNK_SIZE = 2000   # Larger chunks = fewer API calls for extraction
EXTRACTION_CHUNK_OVERLAP = 200
STORAGE_CHUNK_SIZE = 800       # Smaller chunks for ChromaDB (better retrieval)
STORAGE_CHUNK_OVERLAP = 150

DELAY_BETWEEN_CALLS = 3       # seconds between API calls
DELAY_BETWEEN_BATCHES = 8     # seconds between batches
BATCH_SIZE = 5                 # chunks per batch
MAX_RETRIES = 3                # retries per chunk on API error

PROGRESS_FILE = "lightrag_storage/extraction_progress.json"


def load_progress():
    """Load saved extraction progress (if resuming)"""
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"  [RESUME] Found saved progress: {data['completed_chunks']} chunks already processed")
        return data
    return {"completed_chunks": 0, "extractions": [], "settings": {}}


def save_progress(progress):
    """Save extraction progress to disk"""
    os.makedirs(os.path.dirname(PROGRESS_FILE), exist_ok=True)
    with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def extract_with_retry(extractor, chunk_text, source_faith, chunk_id, max_retries=MAX_RETRIES):
    """Extract entities with retry logic and exponential backoff"""
    for attempt in range(max_retries):
        try:
            result = extractor.extract(chunk_text, source_faith=source_faith, chunk_id=chunk_id)
            return result
        except Exception as e:
            error_msg = str(e)
            if "rate" in error_msg.lower() or "429" in error_msg or "limit" in error_msg.lower():
                wait_time = (2 ** attempt) * 10  # 10s, 20s, 40s
                print(f"\n  RATE LIMITED! Waiting {wait_time}s before retry {attempt+1}/{max_retries}...")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                wait_time = (2 ** attempt) * 5
                print(f"\n  Error: {error_msg[:100]}... Retry {attempt+1}/{max_retries} in {wait_time}s")
                time.sleep(wait_time)
            else:
                print(f"\n  FAILED after {max_retries} retries: {error_msg[:100]}")
                return {"entities": [], "relationships": []}
    return {"entities": [], "relationships": []}


def main():
    """Main safe ingestion function"""
    print("=" * 60)
    print("  LightRAG Safe Ingestion (Rate-Limited)")
    print("=" * 60)

    # Initialize config
    config = LightRAGConfig()
    print(f"\n[CONFIG]")
    if config.use_bytez:
        print(f"  Model: Bytez {config.bytez_model}")
    else:
        print(f"  Model: Groq {config.llm_model}")
    print(f"  Extraction chunks: size={EXTRACTION_CHUNK_SIZE}, overlap={EXTRACTION_CHUNK_OVERLAP}")
    print(f"  Storage chunks: size={STORAGE_CHUNK_SIZE}, overlap={STORAGE_CHUNK_OVERLAP}")
    print(f"  Delay: {DELAY_BETWEEN_CALLS}s between calls, {DELAY_BETWEEN_BATCHES}s between batches")

    # Load PDF
    pdf_path = "data/bgita.pdf"
    if not os.path.exists(pdf_path):
        print(f"ERROR: PDF not found at {pdf_path}")
        return

    print(f"\n[STEP 1] Loading PDF '{pdf_path}'...")
    loader = PyPDFLoader(pdf_path)
    documents = loader.load()
    print(f"  Loaded {len(documents)} pages")

    # Create LARGE chunks for entity extraction (fewer API calls)
    print(f"\n[STEP 2a] Creating extraction chunks (large, for entity extraction)...")
    extraction_splitter = RecursiveCharacterTextSplitter(
        chunk_size=EXTRACTION_CHUNK_SIZE,
        chunk_overlap=EXTRACTION_CHUNK_OVERLAP
    )
    extraction_chunks = extraction_splitter.split_documents(documents)
    print(f"  Created {len(extraction_chunks)} extraction chunks (API calls needed)")

    # Create SMALL chunks for ChromaDB storage (better retrieval)
    print(f"\n[STEP 2b] Creating storage chunks (small, for ChromaDB)...")
    storage_splitter = RecursiveCharacterTextSplitter(
        chunk_size=STORAGE_CHUNK_SIZE,
        chunk_overlap=STORAGE_CHUNK_OVERLAP
    )
    storage_chunks = storage_splitter.split_documents(documents)
    print(f"  Created {len(storage_chunks)} storage chunks")

    # Check progress
    progress = load_progress()
    total_extraction_chunks = len(extraction_chunks)
    remaining = total_extraction_chunks - progress["completed_chunks"]

    # Check if saved progress was from a different chunk setting
    saved_settings = progress.get("settings", {})
    if saved_settings.get("chunk_size") and saved_settings["chunk_size"] != EXTRACTION_CHUNK_SIZE:
        print(f"\n  WARNING: Previous progress used different chunk size ({saved_settings['chunk_size']})")
        print(f"  Resetting progress...")
        progress = {"completed_chunks": 0, "extractions": [], "settings": {}}
        remaining = total_extraction_chunks

    estimated_time = remaining * (DELAY_BETWEEN_CALLS + 8)
    print(f"\n[API USAGE ESTIMATE]")
    print(f"  Total extraction chunks: {total_extraction_chunks}")
    print(f"  Already processed: {progress['completed_chunks']}")
    print(f"  Remaining API calls: {remaining}")
    print(f"  Estimated time: ~{estimated_time // 60}m {estimated_time % 60}s")

    if remaining > 0:
        user_input = input(f"\n  Proceed with {remaining} API calls? (y/n): ").strip().lower()
        if user_input != 'y':
            print("  Aborted by user.")
            return

    if remaining == 0:
        print("\n  All chunks already extracted! Skipping to post-processing...")
        all_extractions = progress["extractions"]
    else:
        # Extract entities and relationships (rate-limited)
        print(f"\n[STEP 3] Extracting entities & relationships (rate-limited)...")
        extractor = EntityRelationExtractor(config=config)

        all_extractions = progress["extractions"]
        start_from = progress["completed_chunks"]

        for i in range(start_from, total_extraction_chunks):
            chunk = extraction_chunks[i]
            chunk_id = f"Bhagavad_Gita_{i}"

            print(f"  [{i+1}/{total_extraction_chunks}] Processing chunk {i}...", end="", flush=True)

            extraction = extract_with_retry(
                extractor, chunk.page_content,
                source_faith="Bhagavad Gita",
                chunk_id=chunk_id
            )

            entities_count = len(extraction.get("entities", []))
            relations_count = len(extraction.get("relationships", []))
            print(f" -> {entities_count} entities, {relations_count} relationships")

            all_extractions.append(extraction)

            # Save progress after each chunk
            progress["completed_chunks"] = i + 1
            progress["extractions"] = all_extractions
            progress["settings"] = {"chunk_size": EXTRACTION_CHUNK_SIZE}
            save_progress(progress)

            # Rate limiting
            if (i + 1) < total_extraction_chunks:
                if (i + 1 - start_from) % BATCH_SIZE == 0 and (i + 1 - start_from) > 0:
                    print(f"  [BATCH COMPLETE] Cooling down {DELAY_BETWEEN_BATCHES}s...")
                    time.sleep(DELAY_BETWEEN_BATCHES)
                else:
                    time.sleep(DELAY_BETWEEN_CALLS)

        print(f"\n  All {total_extraction_chunks} chunks extracted!")

    # Merge all extractions
    print(f"\n[STEP 4] Merging extractions...")
    all_entities = []
    all_relationships = []
    for extraction in all_extractions:
        all_entities.extend(extraction.get("entities", []))
        all_relationships.extend(extraction.get("relationships", []))
    print(f"  Total: {len(all_entities)} entities, {len(all_relationships)} relationships")

    if len(all_entities) == 0:
        print("\n  WARNING: No entities extracted! Check API key and model.")
        return

    # Deduplicate entities (local, no API)
    print(f"\n[STEP 5] Deduplicating entities (local)...")
    embedding_model = HuggingFaceEmbeddings(model_name=config.embedding_model)
    deduplicator = EntityDeduplicator(
        embedding_model=embedding_model,
        similarity_threshold=config.similarity_threshold,
        config=config
    )

    deduplicated_entities = deduplicator.deduplicate(all_entities)
    deduplicated_relationships = deduplicator.deduplicate_relationships(all_relationships)
    print(f"  Deduplicated to {len(deduplicated_entities)} unique entities")
    print(f"  Deduplicated to {len(deduplicated_relationships)} unique relationships")

    # Build knowledge graph (local, no API)
    print(f"\n[STEP 6] Building knowledge graph...")
    graph_builder = KnowledgeGraphBuilder(config=config)
    graph = graph_builder.build_from_extractions(
        deduplicated_entities,
        deduplicated_relationships
    )

    # Save graph
    print(f"\n[STEP 7] Saving knowledge graph...")
    graph_builder.save()

    # Store ALL storage chunks in ChromaDB (local embeddings, no API)
    print(f"\n[STEP 8] Storing {len(storage_chunks)} chunks in ChromaDB...")
    vector_store = VectorRetriever(
        embedding_model=embedding_model,
        config=config
    )

    # Process in batches to avoid memory issues
    batch_size = 50
    total_storage = len(storage_chunks)
    for batch_start in range(0, total_storage, batch_size):
        batch_end = min(batch_start + batch_size, total_storage)
        batch = storage_chunks[batch_start:batch_end]

        chunk_data = [
            {
                "text": chunk.page_content,
                "id": f"Bhagavad_Gita_chunk_{batch_start + j}",
                "source_faith": "Bhagavad Gita",
                "chunk_index": batch_start + j,
                "source_file": pdf_path
            }
            for j, chunk in enumerate(batch)
        ]
        vector_store.add_chunks(chunk_data)
        print(f"    Stored batch {batch_start//batch_size + 1}/{math.ceil(total_storage/batch_size)}")

    # Store entities in ChromaDB
    print(f"\n[STEP 9] Storing {len(deduplicated_entities)} entities in ChromaDB...")
    vector_store.add_entities(deduplicated_entities)

    # Print final statistics
    stats = graph_builder.get_statistics()
    chroma_stats = vector_store.get_stats()
    print("\n" + "=" * 60)
    print("  INGESTION COMPLETE!")
    print("=" * 60)
    print(f"  Knowledge Graph:")
    print(f"    - Nodes: {stats['num_nodes']}")
    print(f"    - Edges: {stats['num_edges']}")
    print(f"    - Node types: {stats['node_types']}")
    print(f"    - Edge types: {stats['edge_types']}")
    print(f"\n  ChromaDB Vector Store:")
    print(f"    - Chunks stored: {chroma_stats['count']}")
    print(f"    - Entities stored: {len(deduplicated_entities)}")
    print(f"    - Storage path: {config.chromadb_path}")
    print("=" * 60)
    print("\n  You can now run chat.py or lightrag/chat_lightrag.py to chat!")


if __name__ == "__main__":
    main()
