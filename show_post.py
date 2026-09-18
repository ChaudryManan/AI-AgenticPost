"""
Print the finished post from a run.

Usage:
    python show_post.py f27437752a58
"""
import json
import sys
from pathlib import Path

run_id = sys.argv[1] if len(sys.argv) > 1 else None
if not run_id:
    print("usage: python show_post.py <run_id>")
    sys.exit(1)

state_path = Path("runs") / run_id / "state.json"
if not state_path.exists():
    # state.json isn't written automatically; fall back to the checkpointer
    import asyncio
    from smauto.graph.builder import build_graph
    from smauto.graph.checkpointer import (
        setup_async_checkpointer, teardown_async_checkpointer,
    )

    async def fetch():
        cp = await setup_async_checkpointer()
        try:
            g = build_graph(checkpointer=cp)
            cfg = {"configurable": {"thread_id": run_id}}
            snap = await g.aget_state(cfg)
            return dict(snap.values or {})
        finally:
            await teardown_async_checkpointer(cp)

    state = asyncio.run(fetch())
else:
    state = json.loads(state_path.read_text(encoding="utf-8"))

if not state:
    print(f"no state found for {run_id}")
    sys.exit(1)

# ── the actual post ──────────────────────────────────────────────────
ts = state.get("text_state") or {}
vs = state.get("video_state") or {}
strat = state.get("strategy") or {}
plan = state.get("plan") or {}

print("=" * 70)
print(f"  RUN: {run_id}")
print("=" * 70)

print(f"\n[OBJECTIVE]\n  {plan.get('objective', '(none)')}")

print(f"\n[STRATEGY HOOK]\n  {strat.get('hook', '(none)')}")

print(f"\n[TONE]\n  {strat.get('tone', '(none)')}")

# platform bodies
bodies = ts.get("platform_bodies") or {}
if bodies:
    for platform, body in bodies.items():
        print(f"\n[{platform.upper()} POST]")
        print("─" * 70)
        print(body)
        print("─" * 70)
elif vs.get("caption"):
    print(f"\n[CAPTION]\n{vs['caption']}")

# hashtags
tags = ts.get("hashtags") or vs.get("hashtags") or []
if tags:
    print(f"\n[HASHTAGS]\n  {' '.join(tags)}")

# visual
vtype = ts.get("visual_type")
imgs = ts.get("image_paths") or vs.get("thumbnail_paths") or []
if vtype:
    print(f"\n[VISUAL]\n  type: {vtype}")
    for p in imgs:
        print(f"  {p}")

# seo
seo = ts.get("seo") or {}
if seo:
    print(f"\n[SEO]\n  grade: {seo.get('grade')}   words: {seo.get('word_count')}")

# qa
qa = state.get("qa") or {}
print(f"\n[QA]\n  passed: {qa.get('passed')}   revisions: {state.get('revision_count', 0)}")
for f in qa.get("failures") or []:
    print(f"  [{f.get('severity')}] {f.get('stage')}: {f.get('reason')}")

print()