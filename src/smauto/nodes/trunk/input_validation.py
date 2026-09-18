"""
INPUT_VALIDATION — the entry gate.

Responsibilities:
  1. Reject empty or policy-violating requests
  2. Parse content_type (video | text | both) from the raw request
  3. Parse target platforms
  4. Decide whether the request is too ambiguous and needs clarification
  5. If `content_type`/`platforms` were given explicitly by the caller,
     respect those over parsing (they win)

Outputs land in state: content_type, platforms, topic, clarification_needed,
clarification_question, escalate.
"""
from __future__ import annotations

import re

from ...infra.logging import get_logger
from ...state.schema import GraphState
from ...validators import check_policy

log = get_logger("node.input_validation")

# ── intent parsing ────────────────────────────────────────────────────

_VIDEO_KW = re.compile(
    r"\b(video|reel|reels|short|shorts|clip|clips|tiktok|youtube|"
    r"story|stories|animation|film)\b",
    re.IGNORECASE,
)
_TEXT_KW = re.compile(
    r"\b(post|posts|copy|write|article|thread|tweet|carousel|"
    r"caption|linkedin|copywriting|blog)\b",
    re.IGNORECASE,
)

# every platform we know how to publish to (must match config/platforms.yaml)
_KNOWN_PLATFORMS = (
    "linkedin", "x", "twitter", "instagram", "ig",
    "facebook", "fb", "youtube", "yt", "tiktok",
)
_PLATFORM_ALIASES = {
    "twitter": "x",
    "ig": "instagram",
    "fb": "facebook",
    "yt": "youtube",
}


def _parse_platforms(text: str) -> list[str]:
    low = text.lower()
    found: list[str] = []
    for kw in _KNOWN_PLATFORMS:
        # use a word-boundary-aware test — avoid matching "ig" inside "big"
        if re.search(rf"(?<![a-z]){re.escape(kw)}(?![a-z])", low):
            canonical = _PLATFORM_ALIASES.get(kw, kw)
            if canonical not in found:
                found.append(canonical)
    return found


def _parse_content_type(text: str) -> str:
    wants_video = bool(_VIDEO_KW.search(text))
    wants_text = bool(_TEXT_KW.search(text))
    if wants_video and wants_text:
        return "both"
    if wants_video:
        return "video"
    return "text"


def _looks_ambiguous(text: str, platforms: list[str]) -> bool:
    """
    Ambiguous = very short AND no explicit platform.
    The 4-word threshold is deliberately conservative — we'd rather run
    with a guess than annoy the user with a clarification question.
    """
    return len(text.split()) < 4 and not platforms


# ── the node ──────────────────────────────────────────────────────────

async def input_validation_node(state: GraphState) -> dict:
    req = (state.get("request") or "").strip()
    log.info("input_validation start chars=%d", len(req))

    # 1. hard fail: empty request
    if not req:
        return {
            "escalate": True,
            "errors": [{"node": "input_validation", "type": "empty_request"}],
        }

    # 2. hard fail: policy violation in raw input
    violations = check_policy(req)
    if violations:
        return {
            "escalate": True,
            "errors": [{
                "node": "input_validation",
                "type": "policy_violation",
                "detail": "; ".join(violations),
            }],
        }

    # 3. parse — explicit caller values take precedence
    parsed_platforms = _parse_platforms(req)
    parsed_type = _parse_content_type(req)

    content_type = state.get("content_type") or parsed_type
    platforms = list(state.get("platforms") or []) or parsed_platforms

    # 4. ambiguity check
    if _looks_ambiguous(req, platforms):
        return {
            "clarification_needed": True,
            "clarification_question": (
                "Which platform(s) should I target, and do you want "
                "video or text (or both)?"
            ),
            "content_type": content_type,
            "platforms": platforms,
            "topic": req,
        }

    log.info(
        "input_validation ok type=%s platforms=%s",
        content_type, platforms,
    )
    return {
        "content_type": content_type,
        "platforms": platforms,
        "topic": req,
        "clarification_needed": False,
    }