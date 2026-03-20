import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
load_dotenv(".env")

llm = ChatOpenAI(
    model="llama3.1",
    api_key="ollama",
    base_url="http://localhost:11434/v1",
)
try:
    print(llm.invoke("Hi").content)
except Exception as e:
    print(f"Error: {e}")
