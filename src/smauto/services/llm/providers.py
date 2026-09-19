"""
Thin provider adapters.

Each adapter takes (model, messages, temperature, json_mode) and returns the
provider's raw JSON response.  Normalizing the *text out* happens one level up
in LLMClient.chat — this file only knows how to talk HTTP.
"""
from __future__ import annotations

import os
from typing import Any

import httpx


class ProviderError(RuntimeError):
    """Raised when a provider is misconfigured or returns an error."""


def _require(key_name: str) -> str:
    v = os.getenv(key_name)
    if not v:
        raise ProviderError(f"{key_name} is not set")
    return v


# ── OpenAI ────────────────────────────────────────────────────────────
async def openai_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.6,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    key = _require("OPENAI_API_KEY")

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code >= 400:
        raise ProviderError(f"openai {r.status_code}: {r.text[:500]}")
    return r.json()


# ── Anthropic ─────────────────────────────────────────────────────────
async def anthropic_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.6,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    key = _require("ANTHROPIC_API_KEY")

    # Anthropic wants system separate from the messages array.
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    system = "\n\n".join(system_parts).strip()
    user_msgs = [m for m in messages if m["role"] != "system"]

    body: dict[str, Any] = {
        "model": model,
        "max_tokens": 4096,
        "temperature": temperature,
        "messages": user_msgs,
    }
    if system:
        body["system"] = system

    # Anthropic doesn't have a json_mode flag; nudge via the prefill trick.
    # Callers already ask for "STRICT JSON only" in the prompt, so this is
    # usually unnecessary.  Leaving the door open for a prefill if needed.
    _ = json_mode

    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code >= 400:
        raise ProviderError(f"anthropic {r.status_code}: {r.text[:500]}")
    return r.json()


# ── Gemini ────────────────────────────────────────────────────────────
async def gemini_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.6,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    key = _require("GEMINI_API_KEY")

    # Gemini folds system into a "system_instruction" field.
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    system = "\n\n".join(system_parts).strip()
    contents = [
        {"role": "user" if m["role"] == "user" else "model",
         "parts": [{"text": m["content"]}]}
        for m in messages
        if m["role"] != "system"
    ]

    gen_config: dict[str, Any] = {"temperature": temperature}
    if json_mode:
        gen_config["responseMimeType"] = "application/json"

    body: dict[str, Any] = {
        "contents": contents,
        "generationConfig": gen_config,
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    try:
        async with httpx.AsyncClient(timeout=timeout) as c:
            r = await c.post(url, json=body)
    except httpx.TimeoutException as e:
        # Surface timeouts as a transient ProviderError so the fallback
        # chain can try the next model instead of crashing.
        raise ProviderError(f"gemini timeout: {type(e).__name__}") from e
    except httpx.RequestError as e:
        raise ProviderError(f"gemini network: {type(e).__name__}: {e}") from e

    if r.status_code >= 400:
        raise ProviderError(f"gemini {r.status_code}: {r.text[:500]}")
    return r.json()
async def openrouter_chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.6,
    json_mode: bool = False,
    timeout: float = 45.0,
) -> dict[str, Any]:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ProviderError("OPENROUTER_API_KEY is not set")

    body: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    async with httpx.AsyncClient(timeout=timeout) as c:
        r = await c.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=body,
        )
    if r.status_code >= 400:
        raise ProviderError(f"openrouter {r.status_code}: {r.text[:500]}")
    return r.json()