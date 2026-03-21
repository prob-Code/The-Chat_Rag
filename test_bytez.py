import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag_core.bytez_llm import BytezGPT

llm = BytezGPT(
    model_id="openai/gpt-5.1",
    api_key="d58e5d706eddd608a4ff5b4153396c11",
    temperature=0.7,
)

result = llm.invoke("Say 'GPT-5.1 via Bytez is working!' and nothing else.")
print("RESULT:", result.content)
