"""
Video generation via Replicate.

Default model: minimax/video-01 (5–6 second clips, image-free text-to-video).
Video generation is SLOW — expect 30s–3min per clip depending on the model.
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path
from typing import Any

import httpx

from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("video_gen")

_REPLICATE_URL = "https://api.replicate.com/v1/models/{model}/predictions"


def _token() -> str:
    t = os.getenv("REPLICATE_API_TOKEN")
    if not t:
        raise MediaError("REPLICATE_API_TOKEN is not set")
    return t


async def generate_clip(
    prompt: str,
    out_path: Path,
    duration: float = 6.0,
    seed: int | None = None,
    model: str = "minimax/video-01",
    timeout: float = 600.0,
) -> Path:
    """Generate one short clip and write it to `out_path`."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    await bucket("video_gen").acquire()

    payload_input: dict[str, Any] = {"prompt": prompt}
    if seed is not None:
        payload_input["seed"] = seed

    headers = {
        "Authorization": f"Token {_token()}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }

    url = _REPLICATE_URL.format(model=model)

    with span("video_gen", model=model, out=str(out_path), dur=duration):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, headers=headers, json={"input": payload_input})
            if r.status_code >= 400:
                raise MediaError(f"replicate {r.status_code}: {r.text[:500]}")
            data = r.json()

            output_url = _extract_output_url(data)
            if output_url is None:
                output_url = await _poll(c, data, headers)

            vid = await c.get(output_url)
            if vid.status_code >= 400:
                raise MediaError(f"video download {vid.status_code}: {vid.text[:300]}")

    out_path.write_bytes(vid.content)
    log.info("video_gen ok path=%s bytes=%d", out_path, out_path.stat().st_size)
    return out_path


def _extract_output_url(data: dict[str, Any]) -> str | None:
    out = data.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, list) and out:
        first = out[0]
        return first if isinstance(first, str) else None
    return None


async def _poll(client: httpx.AsyncClient,
                created: dict[str, Any],
                headers: dict[str, str],
                max_wait: float = 900.0,
                interval: float = 3.0) -> str:
    poll_url = (created.get("urls") or {}).get("get")
    if not poll_url:
        raise MediaError(f"no poll url in replicate response: {created}")

    started = time.monotonic()
    while True:
        if time.monotonic() - started > max_wait:
            raise MediaError(f"replicate polling timed out after {max_wait}s")

        r = await client.get(poll_url, headers=headers)
        if r.status_code >= 400:
            raise MediaError(f"replicate poll {r.status_code}: {r.text[:300]}")

        data = r.json()
        status = data.get("status")
        if status == "succeeded":
            url = _extract_output_url(data)
            if not url:
                raise MediaError(f"replicate succeeded but no output: {data}")
            return url
        if status in ("failed", "canceled"):
            raise MediaError(f"replicate {status}: {data.get('error')}")

        await asyncio.sleep(interval)


async def generate_clips_parallel(
    jobs: list[tuple[str, Path, float, int | None]],
    concurrency: int = 3,
    model: str = "minimax/video-01",
) -> list[Path]:
    """
    Jobs: [(prompt, out_path, duration, seed), ...]
    Returns list of paths in the same order as `jobs`.
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(prompt: str, out: Path, dur: float, seed: int | None) -> Path:
        async with sem:
            return await generate_clip(prompt, out, duration=dur, seed=seed, model=model)

    return await asyncio.gather(*(_one(*j) for j in jobs))