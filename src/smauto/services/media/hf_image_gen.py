"""
Hugging Face Inference Providers image generation.

Uses huggingface_hub.AsyncInferenceClient — async-native, so it fits the
rest of smauto's pipeline without a sync/async bridge.

Falls back through a model chain when a model is unavailable (402/404/503).
Free-tier users get $0.10/month in credits (as of 2026); PRO users get $2.
"""
from __future__ import annotations

import os
from pathlib import Path

from ...infra.errors import MediaError
from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("hf_image_gen")


# Tried in order. If one model fails (402 credits depleted, 404 deprecated,
# 503 overloaded), the next is tried automatically.
_DEFAULT_MODELS = [
    "black-forest-labs/FLUX.1-schnell",
    "black-forest-labs/FLUX.1-dev",
    "stabilityai/stable-diffusion-xl-base-1.0",
]


def _token() -> str:
    # accept either name so users can reuse existing credentials
    t = os.getenv("HUGGINGFACE_API_KEY") or os.getenv("HF_TOKEN")
    if not t:
        raise MediaError(
            "HUGGINGFACE_API_KEY (or HF_TOKEN) is not set. "
            "Get one at https://huggingface.co/settings/tokens "
            "with the 'Make calls to Inference Providers' permission."
        )
    return t


async def generate_image_hf(
    prompt: str,
    out_path: Path,
    negative_prompt: str = "",
    model: str | None = None,
    models: list[str] | None = None,
    width: int = 1024,
    height: int = 1024,
    num_inference_steps: int = 4,   # FLUX.1-schnell works well at 4 steps
    guidance_scale: float = 0.0,    # schnell recommends 0.0
    seed: int | None = None,
    timeout: float = 120.0,
) -> Path:
    """
    Generate one image via HF Inference Providers and write it to out_path.

    model  — pin a single model
    models — try this list in order (overrides model)
    """
    from huggingface_hub import AsyncInferenceClient
    from huggingface_hub.errors import HfHubHTTPError

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    await bucket("image_gen").acquire()

    client = AsyncInferenceClient(
        api_key=_token(),
        timeout=timeout,
    )

    chain = models or ([model] if model else _DEFAULT_MODELS)

    kwargs: dict = {
        "prompt": prompt,
        "width": width,
        "height": height,
        "num_inference_steps": num_inference_steps,
        "guidance_scale": guidance_scale,
    }
    if negative_prompt:
        kwargs["negative_prompt"] = negative_prompt
    if seed is not None:
        kwargs["seed"] = seed

    last_err: Exception | None = None

    for idx, m in enumerate(chain):
        try:
            with span("hf_image_gen", model=m, out=str(out_path)):
                image = await client.text_to_image(model=m, **kwargs)

            image.save(out_path)
            log.info("hf_image_gen ok model=%s path=%s", m, out_path)
            return out_path

        except HfHubHTTPError as e:
            status = getattr(e.response, "status_code", None)
            last_err = e
            # 402 = credits depleted → try next model (different provider may
            #        bill differently, though usually not — still worth trying)
            # 404 = model unavailable → skip immediately
            # 503 = overloaded → try next
            log.warning("hf_image_gen model=%s failed (%s): %s",
                        m, status, str(e)[:150])
            if idx < len(chain) - 1:
                continue
            raise MediaError(f"all HF models failed; last: {e}") from e

        except Exception as e:  # noqa: BLE001
            last_err = e
            log.warning("hf_image_gen model=%s unexpected error: %s", m, e)
            if idx < len(chain) - 1:
                continue
            raise MediaError(f"all HF models failed; last: {e}") from e

    assert last_err is not None
    raise MediaError(f"all HF models failed; last: {last_err}")