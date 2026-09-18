"""
Cheap grounding check — flag numeric claims that don't appear in any source.

This is a heuristic, not a fact-checker.  It exists because the copywriter
sometimes invents statistics ("37% faster!", "3x ROI") and we'd rather catch
the obvious cases locally than pay an LLM call for every claim.

The fact_check node still runs the LLM-based check for semantic claims —
this one just kills the low-hanging fruit before that call.
"""
from __future__ import annotations

import re
from typing import Any


# numbers with units/percentages that look like claims, not prices or years
_CLAIM_NUMBER = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:%|x\b|percent|times|k\b|m\b|billion|million)?",
    re.IGNORECASE,
)

# skip obvious non-claims
_SKIP = re.compile(
    r"\b(?:19|20)\d{2}\b|"       # years like 2024
    r"\$\d|"                     # prices
    r"\bv\d+(?:\.\d+)*\b",       # version numbers
    re.IGNORECASE,
)


def _numeric_tokens(text: str) -> set[str]:
    """Extract candidate numeric claims from a piece of text."""
    tokens = set()
    for m in _CLAIM_NUMBER.finditer(text):
        s = m.group(0).strip()
        if not s or _SKIP.search(s):
            continue
        # normalize whitespace for matching
        tokens.add(re.sub(r"\s+", "", s))
    return tokens


def _corpus(sources: list[dict[str, Any]], facts: list[str]) -> str:
    parts = []
    for s in sources:
        parts.append(str(s.get("content") or ""))
        parts.append(str(s.get("title") or ""))
    parts.extend(facts or [])
    return " ".join(parts)


def check_grounding(
    claims: list[str],
    sources: list[dict[str, Any]],
    facts: list[str],
) -> list[dict[str, Any]]:
    """
    Return a list of failures:
        [{"claim": str, "reason": str, "severity": "hard"|"soft"}, ...]

    A claim is unsupported if it contains a numeric token that appears in
    NEITHER the sources NOR the facts.  Semantic (non-numeric) claims are
    left to the LLM-based fact_checker — we don't try to be clever here.
    """
    corpus = _corpus(sources, facts)
    corpus_normalized = re.sub(r"\s+", "", corpus)

    failures: list[dict[str, Any]] = []
    for c in claims or []:
        c = (c or "").strip()
        if not c:
            continue
        tokens = _numeric_tokens(c)
        if not tokens:
            continue
        unsupported = [t for t in tokens if t not in corpus_normalized]
        if unsupported:
            failures.append({
                "claim": c,
                "reason": f"unsupported number(s): {', '.join(sorted(unsupported))}",
                "severity": "hard",
            })
    return failures