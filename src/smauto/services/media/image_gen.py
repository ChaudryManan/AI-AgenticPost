"""
Image generation — dispatches to Replicate or Hugging Face based on
config/models.yaml. Both produce a local PNG at the requested path.

The public entry point is `generate_image()` — callers don't need to know
which provider is active.
"""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

from ...config.settings import get_settings
from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("image_gen")


# ── dispatcher ────────────────────────────────────────────────────────────

def _image_provider_cfg() -> dict[str, Any]:
    s = get_settings()
    try:
        cfg = yaml.safe_load(s.models_path.read_text(encoding="utf-8"))
        return cfg.get("image_gen", {}).get("default", {}) or {}
    except Exception:  # noqa: BLE001
        return {}


async def generate_image(
    prompt: str,
    out_path: Path,
    negative_prompt: str = "",
    seed: int | None = None,
    model: str | None = None,
) -> Path:
    """
    Route to the configured provider.

    Reads config/models.yaml -> image_gen.default.provider:
      • "huggingface" / "hf"  → Hugging Face Inference Providers
      • "replicate"           → Replicate

    If no provider is configured:
      • uses HF when HUGGINGFACE_API_KEY or HF_TOKEN is set
      • otherwise falls back to Replicate
    """
    cfg = _image_provider_cfg()
    provider = (cfg.get("provider") or "").lower()
    model = model or cfg.get("model")

    if provider in ("huggingface", "hf"):
        from .hf_image_gen import generate_image_hf
        return await generate_image_hf(
            prompt, out_path,
            negative_prompt=negative_prompt,
            model=model,
            seed=seed,
        )

    if provider == "replicate":
        return await _generate_replicate(
            prompt, out_path,
            negative_prompt=negative_prompt,
            seed=seed,
            model=model or "black-forest-labs/flux-schnell",
        )

    # no explicit config → prefer HF if a key exists, else Replicate
    if os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN"):
        from .hf_image_gen import generate_image_hf
        return await generate_image_hf(
            prompt, out_path,
            negative_prompt=negative_prompt,
            seed=seed,
        )

    return await _generate_replicate(
        prompt, out_path,
        negative_prompt=negative_prompt,
        seed=seed,
    )


# ── Replicate backend ────────────────────────────────────────────────────

_REPLICATE_URL = "https://api.replicate.com/v1/models/{model}/predictions"


def _replicate_token() -> str:
    t = os.getenv("REPLICATE_API_TOKEN")
    if not t:
        raise MediaError("REPLICATE_API_TOKEN is not set")
    return t


async def _generate_replicate(
    prompt: str,
    out_path: Path,
    negative_prompt: str = "",
    seed: int | None = None,
    model: str = "black-forest-labs/flux-schnell",
    timeout: float = 180.0,
) -> Path:
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    await bucket("image_gen").acquire()

    payload_input: dict[str, Any] = {"prompt": prompt}
    if negative_prompt:
        payload_input["negative_prompt"] = negative_prompt
    if seed is not None:
        payload_input["seed"] = seed

    headers = {
        "Authorization": f"Token {_replicate_token()}",
        "Content-Type": "application/json",
        "Prefer": "wait",
    }
    url = _REPLICATE_URL.format(model=model)

    with span("image_gen.replicate", model=model, out=str(out_path)):
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, headers=headers, json={"input": payload_input})
            if r.status_code >= 400:
                raise MediaError(f"replicate {r.status_code}: {r.text[:500]}")
            data = r.json()
            output_url = _extract_output_url(data)
            if output_url is None:
                output_url = await _poll_replicate(c, data, headers)
            img = await c.get(output_url)
            if img.status_code >= 400:
                raise MediaError(
                    f"image download {img.status_code}: {img.text[:300]}"
                )

    out_path.write_bytes(img.content)
    log.info("image_gen.replicate ok path=%s bytes=%d",
             out_path, out_path.stat().st_size)
    return out_path


def _extract_output_url(data: dict[str, Any]) -> str | None:
    out = data.get("output")
    if isinstance(out, str):
        return out
    if isinstance(out, list) and out and isinstance(out[0], str):
        return out[0]
    return None


async def _poll_replicate(
    client: httpx.AsyncClient,
    created: dict[str, Any],
    headers: dict[str, str],
    max_wait: float = 240.0,
    interval: float = 2.0,
) -> str:
    import time
    poll_url = (created.get("urls") or {}).get("get")
    if not poll_url:
        raise MediaError(f"no poll url: {created}")

    started = time.monotonic()
    while True:
        if time.monotonic() - started > max_wait:
            raise MediaError(f"replicate poll timed out after {max_wait}s")
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
) -> list[Path]:
    """
    Generate many images with a concurrency cap.
    jobs: [(prompt, out_path), ...]
    """
    sem = asyncio.Semaphore(concurrency)

    async def _one(prompt: str, out: Path) -> Path:
        async with sem:
            return await generate_image(prompt, out)

    return await asyncio.gather(*(_one(p, o) for p, o in jobs))