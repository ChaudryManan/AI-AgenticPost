"""
Central settings + path resolution.

Location:  src/smauto/config/settings.py

Path model
──────────
PKG_ROOT      = src/smauto/config            (this file's directory)
SMAUTO_ROOT   = src/smauto                   (the importable package)
PROJECT_ROOT  = the repo root (where pyproject.toml lives)

Config assets (yaml, prompts, policies) live INSIDE the package so they ship
with `pip install`.  Workspace artifacts (runs/, assets/) live at the project
root and are gitignored.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── path resolution ───────────────────────────────────────────────────
PKG_ROOT = Path(__file__).resolve().parent          # src/smauto/config
SMAUTO_ROOT = PKG_ROOT.parent                        # src/smauto
PROJECT_ROOT = PKG_ROOT.parents[2]                   # repo root
from dotenv import load_dotenv  # noqa: E402
load_dotenv(PROJECT_ROOT / ".env", override=False)

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ── providers ─────────────────────────────────────────────────────
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    default_llm_provider: Literal["openai", "anthropic", "gemini"] = "openai"

    replicate_api_token: str | None = None
    elevenlabs_api_key: str | None = None
    tavily_api_key: str | None = None

    # ── storage ───────────────────────────────────────────────────────
    artifact_root: Path = Field(default=PROJECT_ROOT / "runs")
    s3_bucket: str | None = None

    # ── infra ─────────────────────────────────────────────────────────
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/smauto"
    redis_url: str = "redis://localhost:6379/0"
    log_level: str = "INFO"

    # ── budgets / limits ──────────────────────────────────────────────
    max_revisions: int = 3
    max_retries: int = 3
    scene_retry_max: int = 2
    research_requery_max: int = 2
    token_budget: int = 400_000
    usd_budget: float = 5.0

    # ── config asset paths (inside the package) ───────────────────────
    config_dir: Path = Field(default=PKG_ROOT)
    brand_path: Path = Field(default=PKG_ROOT / "brand.yaml")
    platforms_path: Path = Field(default=PKG_ROOT / "platforms.yaml")
    models_path: Path = Field(default=PKG_ROOT / "models.yaml")
    prompts_dir: Path = Field(default=PKG_ROOT / "prompts")
    policies_dir: Path = Field(default=PKG_ROOT / "policies")

    # ── workspace paths (project root) ────────────────────────────────
    project_root: Path = Field(default=PROJECT_ROOT)
    assets_dir: Path = Field(default=PROJECT_ROOT / "assets")

    # ── helpers ───────────────────────────────────────────────────────
    def ensure_runtime_dirs(self) -> None:
        """Create the directories the app writes to at runtime."""
        self.artifact_root.mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "_dead_letter").mkdir(parents=True, exist_ok=True)
        (self.artifact_root / "_feedback").mkdir(parents=True, exist_ok=True)
        self.assets_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    s.ensure_runtime_dirs()
    return s