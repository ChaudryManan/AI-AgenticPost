"""
SEO / READABILITY — Flesch–Kincaid grade + hook-length check.

Purely local, no LLM.  Writes state.text_state.seo.
"""
from __future__ import annotations

import re

from ...infra.logging import get_logger
from ...state.schema import GraphState

log = get_logger("node.seo_readability")

_WORD = re.compile(r"[A-Za-z']+")
_SENTENCE_END = re.compile(r"[.!?]")


def _count_syllables(word: str) -> int:
    """Rough syllable count — good enough for FK grade."""
    word = word.lower()
    if len(word) <= 3:
        return 1
    word = re.sub(r"(?:[^laeiouy]es|ed|[^laeiouy]e)$", "", word)
    word = re.sub(r"^y", "", word)
    return max(1, len(re.findall(r"[aeiouy]{1,2}", word)))


def _fk_grade(text: str) -> float:
    """Flesch–Kincaid grade level.  Lower = easier."""
    words = _WORD.findall(text)
    if not words:
        return 0.0
    sentences = max(1, len(_SENTENCE_END.findall(text)))
    syllables = sum(_count_syllables(w) for w in words)
    asl = len(words) / sentences
    asw = syllables / len(words)
    return round(0.39 * asl + 11.8 * asw - 15.59, 2)


async def seo_readability_node(state: GraphState) -> dict:
    ts = dict(state.get("text_state") or {})
    draft = ts.get("draft") or {}
    hook = (draft.get("hook") or "").strip()
    body = (draft.get("body") or "").strip()

    text = f"{hook}. {body}".strip()
    grade = _fk_grade(text)

    ts["seo"] = {
        "grade": grade,
        "hook_len": len(hook),
        "hook_ok": 0 < len(hook) <= 120,
        "body_len": len(body),
        "word_count": len(_WORD.findall(text)),
    }

    log.info("seo_readability done grade=%.2f hook_len=%d", grade, len(hook))
    return {"text_state": ts}