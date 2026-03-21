"""
Custom Bytez LLM wrapper for LangChain
Uses the OpenAI-compatible endpoint at api.bytez.com
"""
import requests
from typing import Any, Dict, List, Optional
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult, ChatGeneration


class BytezGPT(BaseChatModel):
    """Custom LangChain chat model wrapper for Bytez API (OpenAI-compatible)"""

    api_key: str = ""
    model_id: str = "openai/gpt-5.1"
    temperature: float = 0.7
    api_url: str = "https://api.bytez.com/models/v2/openai/v1/chat/completions"

    @property
    def _llm_type(self) -> str:
        return "bytez-gpt"

    def _convert_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        """Convert LangChain messages to OpenAI format"""
        result = []
        for msg in messages:
            if isinstance(msg, SystemMessage):
                result.append({"role": "system", "content": msg.content})
            elif isinstance(msg, HumanMessage):
                result.append({"role": "user", "content": msg.content})
            elif isinstance(msg, AIMessage):
                result.append({"role": "assistant", "content": msg.content})
            else:
                result.append({"role": "user", "content": msg.content})
        return result

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs) -> ChatResult:
        """Call the Bytez OpenAI-compatible API and return a ChatResult."""
        formatted_messages = self._convert_messages(messages)

        payload = {
            "model": self.model_id,
            "messages": formatted_messages,
            "temperature": self.temperature,
        }

        if stop:
            payload["stop"] = stop

        headers = {
            "Authorization": self.api_key,
            "Content-Type": "application/json",
        }

        response = requests.post(self.api_url, json=payload, headers=headers, timeout=120)

        if response.status_code != 200:
            raise ValueError(
                f"Bytez API error (status {response.status_code}): {response.text}"
            )

        data = response.json()

        # OpenAI-compatible format from Bytez
        if "choices" in data:
            content = data["choices"][0]["message"]["content"]
        elif "error" in data and data["error"]:
            raise ValueError(f"Bytez API error: {data['error']}")
        elif "output" in data:
            output = data["output"]
            if isinstance(output, dict) and "choices" in output:
                content = output["choices"][0]["message"]["content"]
            elif isinstance(output, str):
                content = output
            else:
                content = str(output)
        else:
            content = str(data)

        message = AIMessage(content=content)
        generation = ChatGeneration(message=message)
        return ChatResult(generations=[generation])
