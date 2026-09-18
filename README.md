# smauto

A LangGraph-powered pipeline that turns a single raw prompt into multi-platform
**video and/or text** content — with research, strategy, QA, human approval,
publishing, analytics and an insights feedback loop back into the planner.

## Architecture

```
INPUT_VALIDATION ─┬─► REJECT/ESCALATE
                  ├─► CLARIFY ──► back to INPUT_VALIDATION
                  └─► PLANNER ─► RESEARCH ─► STRATEGY ─► CONTENT_ROUTER
                                                          │
                        ┌─────────────────────────────────┼───────────────────────────┐
                        ▼                                 ▼                           ▼
                   [VIDEO BRANCH]                    [TEXT BRANCH]              BOTH (A then B)
                   script → storyboard → chars       copywriter → scorer →      (join at QA)
                   → scene_prompts → generate*      formatter → hashtags →
                   → check* → assembly → voice      slide_splitter → images →
                   → subtitles → music → render     fact_check → seo
                   → thumbnail → caption
                        │                                 │                           │
                        └─────────────────────────────────┴───────────────────────────┘
                                                          ▼
                                                         QA ──► APPROVAL ──► SCHEDULER
                                                          ▲        │              │
                                                          │        ▼              ▼
                                                       REVISION  PUBLISH ──► ANALYTICS ──► INSIGHTS
                                                          │                                 │
                                                          └────── feedback ─────────────────┘
```

*Fan-out for the 5 video scenes and carousel slides is done with `asyncio.gather`
inside a single node (see `scene_generate.py`, `image_assembly.py`), keeping the
LangGraph topology acyclic and easy to checkpoint.*

## Layout

```
smauto/
├── pyproject.toml
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── assets/                  # brand logos, fonts, licensed music
├── runs/                    # gitignored, run_id-scoped artifacts
├── scripts/                 # ops utilities
├── tests/
└── src/smauto/
    ├── config/              # settings + YAML + prompts (package data)
    ├── infra/               # retry, budget, tracing, dead-letter
    ├── state/               # GraphState + sub-states + reducers
    ├── graph/               # builder, routers, checkpointer, interrupts
    ├── nodes/               # trunk / video / text / shared
    ├── services/            # llm, search, media, publishers
    ├── validators/          # platform, media, brand, policy, grounding
    ├── storage/             # artifacts + SQLAlchemy models + repos
    ├── api/                 # FastAPI app
    ├── workers/             # celery app + run/publish/metrics tasks
    └── cli.py
```

## Quick start

```bash
cp .env.example .env
pip install -e ".[dev]"

# optional: bring up infra
docker compose up -d postgres redis
make migrate

# run the API
make run                # http://localhost:8000/docs

# run a job from the CLI
smauto run --topic "RAG for customer support" --type both \
  --platforms linkedin,x,youtube
```

## API surface

| Method | Path                            | Purpose                              |
|--------|---------------------------------|--------------------------------------|
| POST   | `/runs`                         | Create a run                         |
| GET    | `/runs/{run_id}`                | Fetch run status + state             |
| POST   | `/runs/{run_id}/approve`        | Approve / reject / edit → resume     |
| GET    | `/runs/{run_id}/posts`          | Posts created by this run            |
| GET    | `/analytics/post/{post_id}`     | Metric pulls (1h / 24h / 7d)         |
| POST   | `/webhooks/{platform}`          | Platform callback receiver           |
| GET    | `/health`                       | Liveness                             |

## Notes on providers

The **LLM layer is provider-agnostic** (`services/llm/providers.py`) and reads
its model config from `config/models.yaml`. Image, video and TTS use Replicate
and ElevenLabs. Swap any of these by editing `models.yaml` and the adapter.

Publishers are registered via `services/publishers/registry.py`. Instagram,
TikTok and YouTube ship as **interface stubs** — they require public media URLs
or resumable upload flows and need your app credentials before they'll post for
real. Everything else is wired end-to-end.

## Configuration files

| File                              | Purpose                                    |
|-----------------------------------|--------------------------------------------|
| `config/models.yaml`              | Which LLM/TTS/image/video model per node   |
| `config/platforms.yaml`           | Char limits, hashtag caps, aspect ratios   |
| `config/brand.yaml`               | Palette, fonts, tone, forbidden phrases    |
| `config/prompts/*.j2`             | All LLM prompt templates (Jinja2)          |
| `config/policies/*`               | Banned terms, claim rules                  |

## Human-in-the-loop

Two interrupt points are compiled into the graph:

1. **CLARIFY** — pauses when the input is ambiguous. Resume with a `POST /runs/{id}/approve` after enriching state, or answer via your own endpoint.
2. **APPROVAL** — pauses after QA passes, before scheduling. Resume with an approval decision.

Both are configured in `graph/builder.py` via `interrupt_before=[...]` and
require a checkpointer (Postgres in prod, SQLite locally, memory as a fallback).

## License

Internal / your call.