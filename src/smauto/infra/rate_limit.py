"""
Token-bucket rate limiter, per named bucket.

Used to keep Replicate / ElevenLabs / platform APIs happy without tripping
their per-account limits.  Buckets are process-local — if you run multiple
workers, swap the store for Redis (the interface is the same).
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class TokenBucket:
    def __init__(self, rate: float, capacity: int) -> None:
        """
        rate     — tokens added per second (float)
        capacity — max tokens the bucket can hold (burst size)
        """
        if rate <= 0 or capacity <= 0:
            raise ValueError("rate and capacity must be positive")
        self.rate = float(rate)
        self.capacity = int(capacity)
        self._tokens = float(capacity)
        self._ts = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self, n: int = 1) -> None:
        """Wait until n tokens are available, then consume them."""
        if n > self.capacity:
            raise ValueError(f"requested {n} > capacity {self.capacity}")
        async with self._lock:
            while True:
                now = time.monotonic()
                # refill
                self._tokens = min(
                    self.capacity,
                    self._tokens + (now - self._ts) * self.rate,
                )
                self._ts = now

                if self._tokens >= n:
                    self._tokens -= n
                    return

                # sleep just long enough for the next refill
                deficit = n - self._tokens
                await asyncio.sleep(deficit / self.rate)


# ── named buckets ──────────────────────────────────────────────────────
# Tune per provider as you discover their real limits.
_DEFAULTS: dict[str, tuple[float, int]] = {
    "default":    (2.0, 5),   # 2 rps, burst 5
    "video_gen":  (0.2, 2),   # 1 clip every 5s, burst 2
    "image_gen":  (2.0, 5),
    "tts":        (1.0, 3),
    "publish":    (0.5, 2),
    "web_search": (5.0, 10),
}

_buckets: dict[str, TokenBucket] = {}
_lock = asyncio.Lock()


def bucket(name: str) -> TokenBucket:
    """Get-or-create the bucket for `name`."""
    b = _buckets.get(name)
    if b is not None:
        return b
    rate, cap = _DEFAULTS.get(name, _DEFAULTS["default"])
    b = TokenBucket(rate, cap)
    _buckets[name] = b
    return b


def reset_buckets() -> None:
    """Test helper."""
    _buckets.clear()