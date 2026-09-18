"""
Token health check.

Reports which platform / provider tokens are set, whether they look like
plausible values, and whether `.env` is present.  Doesn't try to hit any
platform APIs — that's what the publishers' own auth check does.

Usage:
    python scripts/refresh_tokens.py                # report only
    python scripts/refresh_tokens.py --env-file .env.prod
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


# every env var we care about, grouped by purpose
_GROUPS = {
    "LLM": [
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
    ],
    "Media": [
        "REPLICATE_API_TOKEN",
        "ELEVENLABS_API_KEY",
    ],
    "Search": [
        "TAVILY_API_KEY",
    ],
    "Publishers": [
        "LINKEDIN_ACCESS_TOKEN",
        "X_BEARER_TOKEN",
        "IG_ACCESS_TOKEN",
        "FB_PAGE_TOKEN",
        "TIKTOK_ACCESS_TOKEN",
        "YT_ACCESS_TOKEN",
    ],
}

# minimum plausible length — catches accidental truncation
_MIN_LEN = 12


def _load_env(path: Path) -> None:
    if not path.exists():
        print(f"warning: env file not found: {path}")
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if k and k not in os.environ:      # don't override real env
            os.environ[k] = v


def _check(var: str) -> tuple[bool, str]:
    v = os.getenv(var, "").strip()
    if not v:
        return False, "not set"
    if len(v) < _MIN_LEN:
        return False, f"set but suspiciously short ({len(v)} chars)"
    return True, f"set ({len(v)} chars)"


def main() -> int:
    ap = argparse.ArgumentParser(description="Report token presence")
    ap.add_argument("--env-file", type=Path, default=Path(".env"))
    args = ap.parse_args()

    _load_env(args.env_file)
    print(f"env file: {args.env_file.resolve()}\n")

    total_ok = 0
    total = 0
    for group, keys in _GROUPS.items():
        print(f"[{group}]")
        for k in keys:
            ok, msg = _check(k)
            mark = "✅" if ok else "❌"
            print(f"  {mark} {k:<24} {msg}")
            total += 1
            if ok:
                total_ok += 1
        print()

    print(f"summary: {total_ok}/{total} configured")

    # non-zero exit if nothing at all is set — useful in CI
    if total_ok == 0:
        print("\nWARNING: no credentials found. The graph will fail at the "
              "first LLM call.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())