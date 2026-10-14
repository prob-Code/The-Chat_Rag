import sys
import os
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_core.bytez_llm import BytezGPT


def main():
    load_dotenv()
    api_key = os.getenv("BYTEZ_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Set BYTEZ_API_KEY before running this integration test.")

    llm = BytezGPT(
        model_id=os.getenv("BYTEZ_MODEL", "openai/gpt-5.1"),
        api_key=api_key,
        temperature=0.7,
    )
    result = llm.invoke("Say 'GPT-5.1 via Bytez is working!' and nothing else.")
    print("RESULT:", result.content)


if __name__ == "__main__":
    main()
