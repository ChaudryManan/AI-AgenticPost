"""Validators — all pure, all deterministic."""
from __future__ import annotations

import pytest

from smauto.validators import (
    PlatformViolation,
    check_brand,
    check_drift,
    check_duration,
    check_grounding,
    check_policy,
    validate_platform,
)


# ── platform rules ────────────────────────────────────────────────────

def test_linkedin_clean_passes():
    validate_platform("linkedin", "Short professional post.", ["#ai"])


def test_linkedin_rejects_links_in_body():
    with pytest.raises(PlatformViolation):
        validate_platform("linkedin", "See https://example.com for more.")


def test_x_over_char_limit():
    with pytest.raises(PlatformViolation):
        validate_platform("x", "a" * 300)


def test_instagram_too_many_hashtags():
    with pytest.raises(PlatformViolation):
        validate_platform("instagram", "body", ["#x"] * 40)


def test_unknown_platform_rejected():
    with pytest.raises(PlatformViolation):
        validate_platform("myspace", "hello")


# ── policy ────────────────────────────────────────────────────────────

def test_policy_clean():
    assert check_policy("Plain honest copy.") == []


def test_policy_flags_banned_term():
    out = check_policy("This is a miracle cure!")
    assert any("miracle cure" in s for s in out)


def test_policy_empty_body():
    assert check_policy("") == []


# ── brand ─────────────────────────────────────────────────────────────

def test_brand_clean():
    assert check_brand("Concrete numbers beat adjectives.") == []


def test_brand_flags_forbidden_phrase():
    out = check_brand("Our revolutionary new tool.")
    assert any("revolutionary" in s for s in out)


# ── media ─────────────────────────────────────────────────────────────

def test_duration_within_tolerance():
    assert check_duration(30.5, 30.0, tolerance=1.5) is True


def test_duration_outside_tolerance():
    assert check_duration(34.0, 30.0, tolerance=1.5) is False


def test_drift_ok():
    ts = [
        {"start": 0.0, "end": 6.0, "text": "one"},
        {"start": 6.0, "end": 12.0, "text": "two"},
    ]
    assert check_drift(ts, [6.0, 6.0], tolerance=1.5) is True


def test_drift_bad():
    ts = [
        {"start": 0.0, "end": 6.0, "text": "one"},
        {"start": 6.0, "end": 12.0, "text": "two"},
    ]
    assert check_drift(ts, [6.0, 9.0], tolerance=1.5) is False


def test_drift_length_mismatch():
    ts = [{"start": 0, "end": 6, "text": "one"}]
    assert check_drift(ts, [6.0, 6.0]) is False


# ── grounding ─────────────────────────────────────────────────────────

def test_grounding_flags_unsupported_number():
    claims = ["RAG made retrieval 37% faster."]
    sources = [{"title": "RAG overview", "content": "Retrieval augmented generation."}]
    facts = ["RAG combines retrieval and generation."]
    fails = check_grounding(claims, sources, facts)
    assert len(fails) == 1
    assert fails[0]["severity"] == "hard"


def test_grounding_passes_supported_number():
    claims = ["It processes 42 documents."]
    sources = [{"title": "t", "content": "It processes 42 documents per run."}]
    assert check_grounding(claims, sources, []) == []


def test_grounding_no_numbers_no_flag():
    claims = ["RAG is a good approach."]
    assert check_grounding(claims, [], []) == []