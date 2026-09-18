"""
Seed the brand configuration.

Writes src/smauto/config/brand.yaml with default values.  Useful when
onboarding a new brand or resetting after a bad edit.

Usage:
    python scripts/seed_brand.py                  # write defaults
    python scripts/seed_brand.py --from my.yaml   # copy from a file
    python scripts/seed_brand.py --print          # show current brand
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

import yaml

# add src/ to path so we can import smauto when run from repo root
_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from smauto.config.settings import get_settings  # noqa: E402


DEFAULT_BRAND = {
    "name": "Acme AI",
    "palette": {
        "primary": "#0F172A",
        "accent": "#22D3EE",
        "bg": "#FFFFFF",
        "text": "#0B1220",
    },
    "fonts": {
        "heading": "Inter-Bold",
        "body": "Inter-Regular",
    },
    "logo": "assets/brand/logo.png",
    "tone_rules": [
        "Confident, not hype-y",
        "No emojis in LinkedIn copy",
        "Prefer concrete numbers over adjectives",
        "Speak in second person; avoid 'we' as opener",
    ],
    "forbidden_phrases": [
        "game-changer",
        "revolutionary",
        "unleash",
        "cutting-edge",
        "seamlessly",
    ],
}


def _cmd_seed(from_path: Path | None) -> int:
    s = get_settings()
    target = s.brand_path

    if from_path:
        if not from_path.exists():
            print(f"ERROR: source file not found: {from_path}")
            return 1
        shutil.copy(from_path, target)
        print(f"copied {from_path} -> {target}")
        return 0

    target.write_text(
        yaml.safe_dump(DEFAULT_BRAND, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    print(f"wrote default brand -> {target}")
    print(f"  keys: {sorted(DEFAULT_BRAND.keys())}")
    return 0


def _cmd_print() -> int:
    s = get_settings()
    if not s.brand_path.exists():
        print(f"no brand file at {s.brand_path}")
        return 1
    data = yaml.safe_load(s.brand_path.read_text(encoding="utf-8"))
    print(yaml.safe_dump(data, sort_keys=False, allow_unicode=True))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Seed / inspect brand.yaml")
    ap.add_argument("--from", dest="from_path", type=Path, default=None,
                    help="copy from an existing YAML file instead of using defaults")
    ap.add_argument("--print", dest="do_print", action="store_true",
                    help="print the current brand config and exit")
    args = ap.parse_args()

    if args.do_print:
        return _cmd_print()
    return _cmd_seed(args.from_path)


if __name__ == "__main__":
    sys.exit(main())