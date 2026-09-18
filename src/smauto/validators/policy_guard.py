"""
Policy scan — banned terms from config/policies/banned_terms.txt.

Used twice in the pipeline:
  1. input_validation — reject the raw request immediately if it contains a
     banned term (saves a full run)
  2. qa — re-check the final copy in case the LLM reintroduced something
"""
from __future__ import annotations

from functools import lru_cache

from ..config.settings import get_settings


@lru_cache(maxsize=1)
def _banned_terms() -> tuple[str, ...]:
    path = get_settings().policies_dir / "banned_terms.txt"
    if not path.exists():
        return ()
    raw = path.read_text(encoding="utf-8")
    # one term per line, ignore blanks / comments
    return tuple(
        line.strip().lower()
        for line in raw.splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def check_policy(body: str) -> list[str]:
    """Return a list of policy violations.  Empty list = clean."""
    if not body:
        return []
    low = body.lower()
    return [f"banned term used: '{t}'" for t in _banned_terms() if t in low]