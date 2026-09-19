"""
smauto CLI.

    smauto run --topic "..." --type both --platforms linkedin,x,youtube
    smauto serve              # alias for uvicorn
    smauto worker             # alias for celery worker
    smauto beat               # alias for celery beat
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from typing import Any

from .graph.builder import build_graph
from .graph.checkpointer import (
    setup_async_checkpointer,
    teardown_async_checkpointer,
)
from .infra.logging import get_logger, setup_logging
from .storage.db.session import init_db

log = get_logger("cli")


async def _run_once(topic, content_type, platforms, run_id):
    setup_logging()
    try:
        init_db()
    except Exception as e:
        log.warning("init_db failed: %s", e)

    run_id = run_id or uuid.uuid4().hex[:12]
    checkpointer = await setup_async_checkpointer()
    try:
        graph = build_graph(checkpointer=checkpointer)
        config = {"configurable": {"thread_id": run_id}}

        init = {
            "run_id": run_id,
            "request": topic,
            "content_type": content_type,
            "platforms": platforms,
        }

        state = await graph.ainvoke(init, config)

        print()
        print("=" * 68)
        print(f"  run_id        : {run_id}")
        print(f"  content_type  : {state.get('content_type')}")
        print(f"  platforms     : {', '.join(state.get('platforms', [])) or '(none)'}")
        print(f"  qa.passed     : {(state.get('qa') or {}).get('passed')}")
        print(f"  revision_cnt  : {state.get('revision_count', 0)}")
        print(f"  escalate      : {state.get('escalate', False)}")

        if (state.get("qa") or {}).get("failures"):
            print("  qa failures:")
            for f in state["qa"]["failures"]:
                print(f"    [{f.get('severity'):>4}] {f.get('stage')}: {f.get('reason')}")

        qa_ok = (state.get("qa") or {}).get("passed")
        published = state.get("publish_results") or []
        if qa_ok and not published:
            print()
            print("  QA passed; graph is paused before approval.")
            try:
                ans = input("  Approve and publish? [y/N] ").strip().lower()
            except EOFError:
                ans = "n"
            # accept y, yes, =y, =yes — users often paste from markdown blocks
            ans = ans.lstrip("= ").strip()
            decision = "approved" if ans in ("y", "yes") else "rejected"

            await graph.aupdate_state(config, {
                "approval": {"status": decision, "editor": "cli",
                             "notes": "cli decision"},
            })
            state = await graph.ainvoke(None, config)
            print()
            print("  after approval:")
            for r in state.get("publish_results", []):
                print(f"    {r.get('platform'):10} {r.get('status'):6} "
                      f"{r.get('url') or r.get('error') or ''}")

        print("=" * 68)
        return 0 if not state.get("escalate") else 1
    finally:
        await teardown_async_checkpointer(checkpointer)


def _cmd_run(args):
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    return asyncio.run(_run_once(args.topic, args.type, platforms, args.run_id))


def _cmd_serve(args):
    os.execvp("uvicorn", ["uvicorn", "smauto.api.main:app",
                          "--host", args.host, "--port", str(args.port)])
    return 0


def _cmd_worker(args):
    os.execvp("celery", ["celery", "-A", "smauto.workers.queue.celery_app",
                         "worker", "-l", args.loglevel])
    return 0


def _cmd_beat(args):
    os.execvp("celery", ["celery", "-A", "smauto.workers.queue.celery_app",
                         "beat", "-l", args.loglevel])
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="smauto",
        description="Social media automation graph (video + text).",
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the graph end-to-end")
    p_run.add_argument("--topic", required=True)
    p_run.add_argument("--type", default="text",
                       choices=["video", "text", "both"])
    p_run.add_argument("--platforms", default="",
                       help="comma-separated, e.g. 'linkedin,x,youtube' "
                            "(if omitted, parsed from the topic)")
    p_run.add_argument("--run-id", default=None)
    p_run.set_defaults(func=_cmd_run)

    p_serve = sub.add_parser("serve", help="start the FastAPI server")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(func=_cmd_serve)

    p_wk = sub.add_parser("worker", help="start a celery worker")
    p_wk.add_argument("-l", "--loglevel", default="info")
    p_wk.set_defaults(func=_cmd_worker)

    p_beat = sub.add_parser("beat", help="start celery beat scheduler")
    p_beat.add_argument("-l", "--loglevel", default="info")
    p_beat.set_defaults(func=_cmd_beat)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
