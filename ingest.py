from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
print()
# 1. Load Gita PDF
loader = PyPDFLoader("data/bgita.pdf")
documents = loader.load()

# 2. Chunking
splitter = RecursiveCharacterTextSplitter(
    chunk_size=800,
    chunk_overlap=150
)

chunks = splitter.split_documents(documents)

# 3. Embedding model
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# 4. Store in vector DB
db = FAISS.from_documents(chunks, embedding_model)

db.save_local("gita_vector_db")

print("Vector DB created successfully")
