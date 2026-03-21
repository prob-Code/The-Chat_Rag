from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_core.prompts import PromptTemplate
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
from rag_core.bytez_llm import BytezGPT

# Load environment variables
load_dotenv()

# 1. Load embeddings
embedding_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

# 2. Load vector DB
db = FAISS.load_local(
    "gita_vector_db",
    embedding_model,
    allow_dangerous_deserialization=True
)

retriever = db.as_retriever(search_kwargs={"k": 4})

# 3. LLM (Bytez GPT-5.1)
llm = BytezGPT(
    model_id=os.getenv("BYTEZ_MODEL", "openai/gpt-5.1"),
    api_key=os.getenv("BYTEZ_API_KEY", "d58e5d706eddd608a4ff5b4153396c11"),
    temperature=0.7,
)

# 4. Gita-centric modern prompt - Enhanced for emotional support
prompt = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a compassionate spiritual guide trained in the wisdom of Bhagavad Gita.

Your role is to provide comfort, hope, and practical guidance to someone who may be feeling lost, sad, anxious, or overwhelmed.

Guidelines for your response:
1. Start with empathy — acknowledge the person's feelings without judgment
2. Use warm, gentle, and encouraging language
3. Share relevant Gita wisdom in simple, relatable terms
4. Remind them that difficult times are temporary and part of life's journey
5. Offer small, actionable steps they can take today
6. End with an uplifting message of hope and strength

Context from Gita:
{context}

Question:
{question}

Respond with deep compassion. Speak as a caring friend who truly understands their pain. 
Make them feel heard, valued, and capable of overcoming this phase.
Keep the tone warm, supportive, and never preachy.
"""
)

# Create chain
chain = prompt | llm

# 5. Chat loop
while True:
    query = input("\nAsk your question (or 'exit'): ")

    if query.lower() == "exit":
        break

    docs = retriever.invoke(query)

    context = "\n\n".join([d.page_content for d in docs])

    answer = chain.invoke({
        "context": context,
        "question": query
    })

    print("\nAnswer:\n", answer.content)
