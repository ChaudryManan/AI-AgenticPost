"""
Image generation via Replicate.

Default model: black-forest-labs/flux-schnell (fast, cheap, good).
Override per-call via the `model` kwarg or globally in config/models.yaml.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx

from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("image_gen")

_REPLICATE_URL = "https://api.replicate.com/v1/models/{model}/predictions"


def _token() -> str:
    t = os.getenv("REPLICATE_API_TOKEN")
    if not t:
        raise MediaError("REPLICATE_API_TOKEN is not set")
    return t


async def generate_image(
    prompt: str,
    out_path: Path,
    negative_prompt: str = "",
    seed: int | None = None,
    model: str = "black-forest-labs/flux-schnell",
    timeout: float = 180.0,
) -> Path:
    """
    Generate one image and write it to `out_path`.  Returns the path.

    Raises MediaError on any provider or IO failure.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    await bucket("image_gen").acquire()

    payload_input: dict[str, Any] = {"prompt": prompt}
    if negative_prompt:
        payload_input["negative_prompt"] = negative_prompt
    if seed is not None:
        payload_input["seed"] = seed

    headers = {
        "Authorization": f"Token {_token()}",
        "Content-Type": "application/json",
        # synchronous-ish: Replicate waits up to 60s before returning a job id
        "Prefer": "wait",
    }

    url = _REPLICATE_URL.format(model=model)

    with span("image_gen", model=model, out=str(out_path)):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, headers=headers, json={"input": payload_input})
            if r.status_code >= 400:
                raise MediaError(f"replicate {r.status_code}: {r.text[:500]}")
            data = r.json()

            # "Prefer: wait" usually gives us the final output inline, but not
            # always — poll if we get a job id back with status != succeeded.
            output_url = _extract_output_url(data)
            if output_url is None:
                output_url = await _poll(c, data, headers)

            # download the image
            img = await c.get(output_url)
            if img.status_code >= 400:
                raise MediaError(f"image download {img.status_code}: {img.text[:300]}")

    out_path.write_bytes(img.content)
    log.info("image_gen ok path=%s bytes=%d", out_path, out_path.stat().st_size)
    return out_path


def _extract_output_url(data: dict[str, Any]) -> str | None:
    """Replicate returns output as either a str or list[str]."""
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
                max_wait: float = 240.0,
                interval: float = 2.0) -> str:
    """Poll a Replicate prediction until it succeeds or fails."""
    import time

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


async def generate_images_parallel(
    jobs: list[tuple[str, Path]],
    concurrency: int = 3,
    model: str = "black-forest-labs/flux-schnell",
) -> list[Path]:
    """
    Generate many images with a concurrency cap.
    Jobs: [(prompt, out_path), ...]
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(prompt: str, out: Path) -> Path:
        async with sem:
            return await generate_image(prompt, out, model=model)

    return await asyncio.gather(*(_one(p, o) for p, o in jobs))