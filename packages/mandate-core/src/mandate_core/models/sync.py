"""Run one async provider call to completion from synchronous code.

The LangGraph buyer graph runs synchronously, but the provider adapters are
async. A fresh thread with its own event loop lets a node await a model call
without a running loop refusing ``asyncio.run``.
"""

import asyncio
import threading
from collections.abc import Awaitable
from typing import TypeVar

T = TypeVar("T")


def run_sync(awaitable: Awaitable[T]) -> T:
    """Block until ``awaitable`` finishes, even inside a running event loop."""

    box: dict[str, object] = {}

    def runner() -> None:
        try:
            box["value"] = asyncio.run(_await(awaitable))
        except BaseException as exc:  # re-raised on the calling thread below
            box["error"] = exc

    thread = threading.Thread(target=runner, name="mandate-model-call")
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box["value"]  # type: ignore[return-value]


async def _await(awaitable: Awaitable[T]) -> T:
    return await awaitable
