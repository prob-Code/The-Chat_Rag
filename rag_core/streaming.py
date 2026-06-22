"""Utilities for streaming LLM output.

This module is intentionally small and dependency-light so it can be reused
from API endpoints without pulling in FastAPI types.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from langchain_core.callbacks import AsyncCallbackHandler


class TokenQueueCallbackHandler(AsyncCallbackHandler):
    """Collect streamed tokens into an async queue.

    Works with LangChain chat models that support token streaming and call
    `on_llm_new_token` as tokens are generated.
    """

    def __init__(self) -> None:
        super().__init__()
        self.queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        self.done = asyncio.Event()
        self.error: Optional[BaseException] = None

    async def on_llm_new_token(self, token: str, **kwargs) -> None:  # type: ignore[override]
        if token:
            await self.queue.put(token)

    async def on_llm_end(self, *args, **kwargs) -> None:  # type: ignore[override]
        self.done.set()

    async def on_llm_error(self, error: BaseException, **kwargs) -> None:  # type: ignore[override]
        self.error = error
        self.done.set()

    async def finish(self) -> None:
        """Mark the stream as finished (even if upstream didn't signal end)."""
        self.done.set()

    async def aiter_tokens(self, *, timeout_s: float = 15.0):
        """Async iterator of tokens.

        Yields:
          - str tokens as they arrive
          - None periodically as a keep-alive signal when no tokens arrive

        Stops when `done` is set and the queue is drained.
        Raises stored error (if any) after draining.
        """
        while True:
            if self.done.is_set() and self.queue.empty():
                break

            try:
                token = await asyncio.wait_for(self.queue.get(), timeout=timeout_s)
                yield token
            except asyncio.TimeoutError:
                # Keep-alive
                yield None

        if self.error is not None:
            raise self.error
