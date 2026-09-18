"""
Replay / resume a run from its checkpoint.

    python scripts/replay_run.py --run-id abc123          # show state
    python scripts/replay_run.py --run-id abc123 --resume # continue graph
    python scripts/replay_run.py --run-id abc123 --dump state.json

Useful when:
  • A run stopped at an interrupt and you want to inspect it
  • You fixed something downstream and want to continue without re-running
  • You need to see the raw state JSON for debugging
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
_SRC = _HERE.parents[1] / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from smauto.graph.builder import build_graph                # noqa: E402
from smauto.graph.checkpointer import (                     # noqa: E402
    setup_async_checkpointer,
    teardown_async_checkpointer,
)
from smauto.infra.logging import get_logger, setup_logging  # noqa: E402
from smauto.storage.db.session import init_db               # noqa: E402

log = get_logger("replay")


# ── helpers ──────────────────────────────────────────────────────────

def _summarize(state: dict) -> None:
    """Print a human-friendly view of the state without dumping everything."""
    qa = state.get("qa") or {}
    strategy = state.get("strategy") or {}
    plan = state.get("plan") or {}

    print("-" * 68)
    print(f"  run_id         : {state.get('run_id')}")
    print(f"  content_type   : {state.get('content_type')}")
    print(f"  platforms      : {', '.join(state.get('platforms') or []) or '(none)'}")
    print(f"  goal           : {plan.get('objective', '(none)')}")
    print(f"  strategy hook  : {strategy.get('hook', '(none)')}")
    print(f"  qa.passed      : {qa.get('passed')}")
    print(f"  revision_count : {state.get('revision_count', 0)}")
    print(f"  escalate       : {state.get('escalate', False)}")

    failures = qa.get("failures") or []
    if failures:
        print(f"  qa failures    : {len(failures)}")
        for f in failures[:5]:
            print(f"    [{f.get('severity'):>4}] {f.get('stage')}: {f.get('reason')}")

    results = state.get("publish_results") or []
    if results:
        print(f"  publish results:")
        for r in results:
            print(f"    {r.get('platform'):10} {r.get('status'):6} "
                  f"{r.get('url') or r.get('error') or ''}")

    vstate = state.get("video_state") or {}
    if vstate:
        print(f"  video: clips={len(vstate.get('clips') or [])} "
              f"render={'yes' if vstate.get('render_path') else 'no'}")

    tstate = state.get("text_state") or {}
    if tstate:
        print(f"  text : visual={tstate.get('visual_type', 'none')} "
              f"images={len(tstate.get('image_paths') or [])} "
              f"hashtags={len(tstate.get('hashtags') or [])}")

    print("-" * 68)


# ── commands ─────────────────────────────────────────────────────────

async def _show(run_id: str, dump_path: Path | None) -> int:
    setup_logging()
    try:
        init_db()
    except Exception:  # noqa: BLE001
        pass

    checkpointer = await setup_async_checkpointer()
    try:
        graph = build_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": run_id}}

        try:
            snapshot = await graph.aget_state(config)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: could not fetch state for {run_id}: {e}")
            return 1

        state = dict(snapshot.values or {})
        if not state:
            print(f"run {run_id} not found in checkpointer")
            return 1

        _summarize(state)

        if dump_path:
            dump_path.write_text(
                json.dumps(state, indent=2, default=str),
                encoding="utf-8",
            )
            print(f"wrote full state -> {dump_path}")

        return 0
    finally:
        await teardown_async_checkpointer(checkpointer)


async def _resume(run_id: str) -> int:
    setup_logging()
    try:
        init_db()
    except Exception:  # noqa: BLE001
        pass

    checkpointer = await setup_async_checkpointer()
    try:
        graph = build_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": run_id}}

        print(f"resuming {run_id}...")
        try:
            state = await graph.ainvoke(None, config)
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: resume failed: {e}")
            return 1

        _summarize(state)
        return 0
    finally:
        await teardown_async_checkpointer(checkpointer)


# ── entry ────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="Inspect / resume a run")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--resume", action="store_true",
                    help="continue the graph from its checkpoint")
    ap.add_argument("--dump", type=Path, default=None,
                    help="write the full state to this file")
    args = ap.parse_args()

    if args.resume:
        return asyncio.run(_resume(args.run_id))
    return asyncio.run(_show(args.run_id, args.dump))


if __name__ == "__main__":
    sys.exit(main())