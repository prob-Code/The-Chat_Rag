import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI


def main():
    load_dotenv(".env")
    llm = ChatOpenAI(
        model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        api_key="ollama",
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
    )
    try:
        print(llm.invoke("Hi").content)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
