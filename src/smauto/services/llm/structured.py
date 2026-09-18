"""
JSON parsing that tolerates the ways LLMs actually misbehave.

Three failure modes we repair:
  1. Markdown fences: ```json ... ``` around otherwise-valid JSON
  2. Leading/trailing prose: "Here's the JSON: {...} Hope that helps!"
  3. Trailing commas in objects / arrays

If none of that works, we raise — the caller (LLMClient.json) surfaces it.
"""
from __future__ import annotations

import json
import re
from typing import Any

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```\s*$", re.DOTALL)
_BLOCK_RE = re.compile(r"(\{.*\}|\[.*\])", re.DOTALL)
_TRAILING_COMMA_RE = re.compile(r",(\s*[}\]])")


def parse_json(text: str) -> Any:
    """Best-effort parse of a possibly-dirty JSON payload."""
    if not isinstance(text, str):
        raise TypeError(f"parse_json expects str, got {type(text).__name__}")

    text = text.strip()
    if not text:
        raise ValueError("empty response — nothing to parse")

    # 1. strip markdown fences
    text = _FENCE_RE.sub("", text).strip()

    # 2. try the cleaned text directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. extract the outermost {...} or [...]
    m = _BLOCK_RE.search(text)
    if m:
        candidate = m.group(1)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # 4. last resort: kill trailing commas and retry
            repaired = _TRAILING_COMMA_RE.sub(r"\1", candidate)
            return json.loads(repaired)

    raise ValueError(f"no JSON found in LLM response: {text[:200]!r}")