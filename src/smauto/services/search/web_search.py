"""
Tavily-backed web search.

Returns [] (not an error) when TAVILY_API_KEY is missing so the pipeline can
still run without search — research just produces nothing and QA flags the
lack of sources.
"""
from __future__ import annotations

import os
from typing import Any

import httpx

from ...infra.logging import get_logger
from ...infra.rate_limit import bucket
from ...infra.tracing import span

log = get_logger("web_search")
_TAVILY_URL = "https://api.tavily.com/search"


async def web_search(query: str,
                     max_results: int = 5,
                     depth: str = "basic") -> list[dict[str, Any]]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        log.warning("web_search disabled — TAVILY_API_KEY not set")
        return []

    await bucket("web_search").acquire()

    body = {
        "api_key": key,
        "query": query,
        "max_results": max_results,
        "search_depth": depth,
        "include_answer": False,
        "include_raw_content": False,
    }

    with span("web_search", q=query[:60]):
        async with httpx.AsyncClient(timeout=30.0) as c:
            r = await c.post(_TAVILY_URL, json=body)

    if r.status_code >= 400:
        log.error("web_search failed %s: %s", r.status_code, r.text[:300])
        return []

    data = r.json()
    out = []
    for hit in data.get("results", []):
        out.append({
            "title": hit.get("title") or "",
            "url": hit.get("url") or "",
            "content": hit.get("content") or "",
            "score": float(hit.get("score") or 0.0),
        })
    return out