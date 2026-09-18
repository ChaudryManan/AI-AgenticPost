"""
Retry helpers.

Two flavors:
  • `with_backoff(attempts)` — sync decorator, wraps tenacity.
  • `async_retry(times, base)` — async decorator, exponential backoff with
    jitter, useful when you don't want a tenacity dependency at call sites.

Both `reraise=True` so the caller sees the *last* error, not a wrapper.
"""
from __future__ import annotations

import asyncio
import functools
import random
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


def with_backoff(attempts: int = 3):
    """Sync tenacity-based decorator."""
    try:
        from tenacity import (retry, stop_after_attempt,
                              wait_exponential_jitter)
        return retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential_jitter(initial=1, max=30),
            reraise=True,
        )
    except ImportError:
        # minimal fallback so the app still runs without tenacity
        def deco(fn):
            @functools.wraps(fn)
            def wrapper(*a, **kw):
                last = None
                for _ in range(attempts):
                    try:
                        return fn(*a, **kw)
                    except Exception as e:  # noqa: BLE001
                        last = e
                raise last  # type: ignore[misc]
            return wrapper
        return deco


def async_retry(times: int = 3, base: float = 0.5,
                jitter: float = 0.25) -> Callable:
    """
    Async retry with exponential backoff + jitter.

    Usage:
        @async_retry(times=3, base=1.0)
        async def call(): ...
    """
    def deco(fn: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            last: BaseException | None = None
            for i in range(times):
                try:
                    return await fn(*args, **kwargs)
                except Exception as e:  # noqa: BLE001
                    last = e
                    if i == times - 1:
                        break
                    delay = base * (2 ** i) + random.uniform(0, jitter)
                    await asyncio.sleep(delay)
            assert last is not None
            raise last
        return wrapper
    return deco