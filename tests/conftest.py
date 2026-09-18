"""
Shared pytest fixtures.

Provides:
  • src/ on sys.path (belt-and-braces — pyproject also does this)
  • mock_responses    — canned LLM outputs keyed by node name
  • mock_llm          — patches LLMClient.json to serve those responses
  • clean_run_dirs    — creates and tears down runs/<test_run_id>/
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

# ── path setup ────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()        # .../tests/conftest.py
_TESTS_DIR = _HERE.parent               # .../tests
_REPO = _TESTS_DIR.parent               # repo root
_SRC = _REPO / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# ── constants ─────────────────────────────────────────────────────────
FIXTURES = _TESTS_DIR / "fixtures"
TEST_RUN_ID = "pytest_run"


# ── fixtures ──────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def mock_responses() -> dict:
    """Load canned LLM responses for every node."""
    path = FIXTURES / "mock_responses" / "llm_responses.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def mock_llm(mock_responses):
    """
    Patch LLMClient.json so every node call returns a canned response.

    The patch is applied at the CLASS method level, which is where all
    node code reaches it (get_llm() returns a cached instance, but the
    method lookup still goes through the class).
    """
    async def fake_json(self, node, system, user, override=None, meter=None):
        if node not in mock_responses:
            raise KeyError(
                f"test fixture has no canned response for node {node!r}; "
                f"add it to tests/fixtures/mock_responses/llm_responses.json"
            )
        return mock_responses[node]

    with patch("smauto.services.llm.client.LLMClient.json", fake_json):
        yield mock_responses


@pytest.fixture
def clean_run_dirs():
    """Create runs/pytest_run/ before the test, remove it after."""
    from smauto.storage.paths import run_dir
    d = run_dir(TEST_RUN_ID)
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    yield d
    if d.exists():
        shutil.rmtree(d)