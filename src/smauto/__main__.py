"""
Entry point for `python -m smauto`.

Delegates to smauto.cli.main so both invocation styles work:

    python -m smauto run --topic "..."
    smauto run --topic "..."
"""
from __future__ import annotations

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
