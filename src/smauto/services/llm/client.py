"""
Provider-agnostic LLM client.

Reads `config/models.yaml` to decide which provider/model/temperature each
named node uses.  Exposes two methods:

    await client.chat(node, system, user, json_mode=False)  -> str
    await client.json(node, system, user)                   -> Any

`json()` is the one every node uses — it asks for JSON mode, then repairs
the response with services/llm/structured.py.
"""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

from ...config.settings import get_settings
from ...infra.budget import BudgetMeter
from ...infra.logging import get_logger
from ...infra.tracing import span
from . import providers
from .structured import parse_json
import asyncio
import random
log = get_logger("llm")

# A process-wide meter.  Nodes that want per-run accounting can pass their
# own meter into `chat(meter=...)`; otherwise this default absorbs it.
_DEFAULT_METER = BudgetMeter(hard=False)


class LLMClient:
    def __init__(self) -> None:
        s = get_settings()
        cfg = yaml.safe_load(s.models_path.read_text(encoding="utf-8"))
        self._models: dict[str, dict[str, Any]] = cfg.get("llm", {})
        if "default" not in self._models:
            raise RuntimeError("config/models.yaml missing llm.default entry")

    # ── public API ────────────────────────────────────────────────────
    def _resolve(self, node: str) -> dict[str, Any]:
        default = self._models["default"]
        node_cfg = self._models.get(node) or {}
        # merge: node overrides default, but inherits anything it doesn't set
        # (notably `fallback` and `provider`)
        cfg = {**default, **node_cfg}
        forced = os.getenv("DEFAULT_LLM_PROVIDER")
        if forced:
            cfg = {**cfg, "provider": forced}
        return cfg

    async def chat(
        self,
        node: str,
        system: str,
        user: str,
        json_mode: bool = False,
        override: dict[str, Any] | None = None,
        meter: BudgetMeter | None = None,
    ) -> str:
        cfg = {**self._resolve(node), **(override or {})}
        provider = cfg["provider"]
        temperature = float(cfg.get("temperature", 0.6))
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        # Build the model chain: primary first, then fallbacks.
        primary = cfg["model"]
        fallbacks = cfg.get("fallback") or []
        if isinstance(fallbacks, str):
            fallbacks = [fallbacks]
        chain = [primary, *fallbacks]

        last_err: Exception | None = None

        for idx, model in enumerate(chain):
                    last_err: Exception | None = None

        # Try the whole chain. If every model fails on a transient error,
        # wait and try the chain again. This handles Google-wide 503 spikes.
        chain_attempts = 2
        for chain_try in range(chain_attempts):
            for idx, model in enumerate(chain):
                is_fallback = idx > 0
                try:
                    with span(f"llm.{node}" + (" (fallback)" if is_fallback else ""),
                              provider=provider, model=model):
                        if provider == "openai":
                            raw = await providers.openai_chat(model, messages, temperature, json_mode)
                            text = raw["choices"][0]["message"]["content"]
                            usage = raw.get("usage") or {}
                            in_tok = int(usage.get("prompt_tokens", 0))
                            out_tok = int(usage.get("completion_tokens", 0))
                        elif provider == "openrouter":
                            raw = await providers.openrouter_chat(model, messages, temperature, json_mode)
                            text = raw["choices"][0]["message"]["content"]
                            usage = raw.get("usage") or {}
                            in_tok = int(usage.get("prompt_tokens", 0))
                            out_tok = int(usage.get("completion_tokens", 0))
                        elif provider == "anthropic":
                            raw = await providers.anthropic_chat(model, messages, temperature, json_mode)
                            text = raw["content"][0]["text"]
                            usage = raw.get("usage") or {}
                            in_tok = int(usage.get("input_tokens", 0))
                            out_tok = int(usage.get("output_tokens", 0))
                        elif provider == "gemini":
                            raw = await providers.gemini_chat(model, messages, temperature, json_mode)
                            text = raw["candidates"][0]["content"]["parts"][0]["text"]
                            usage = raw.get("usageMetadata") or {}
                            in_tok = int(usage.get("promptTokenCount", 0))
                            out_tok = int(usage.get("candidatesTokenCount", 0))
                        else:
                            raise ValueError(f"unknown provider: {provider}")

                    if is_fallback:
                        log.warning("llm.%s: primary was %r, served by fallback %r",
                                    node, primary, model)
                    (meter or _DEFAULT_METER).charge(model, in_tok, out_tok, node)
                    return text

                except providers.ProviderError as e:
                    msg = str(e)
                    last_err = e
                    # 404 means the model name doesn't exist — skip to next immediately
                    not_found = " 404" in msg
                    # transient = overload / rate limit
                    transient = any(code in msg for code in
                                    (" 429", " 500", " 502", " 503", " 504",
                                     "timeout", "network"))

                    if not_found:
                        log.warning("llm.%s: model %r not available (404); skipping",
                                    node, model)
                        continue
                    if transient and idx < len(chain) - 1:
                        log.warning("llm.%s: model %r overloaded (%s); trying next",
                                    node, model, msg[:60])
                        await asyncio.sleep(1.0 + random.uniform(0, 0.5))
                        continue
                    if transient and idx == len(chain) - 1:
                        # last model in chain also overloaded → break to outer retry
                        break
                    # non-transient, non-404 → raise
                    raise

            # all models in the chain failed on this pass
            if chain_try < chain_attempts - 1:
                wait = 15.0 + random.uniform(0, 5.0)
                log.warning("llm.%s: full chain failed; waiting %.0fs and retrying",
                            node, wait)
                await asyncio.sleep(wait)

        assert last_err is not None
        raise last_err

        assert last_err is not None
        raise last_err
    async def json(
        self,
        node: str,
        system: str,
        user: str,
        override: dict[str, Any] | None = None,
        meter: BudgetMeter | None = None,
    ) -> Any:
        text = await self.chat(node, system, user, json_mode=True,
                               override=override, meter=meter)
        return parse_json(text)


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    return LLMClient()