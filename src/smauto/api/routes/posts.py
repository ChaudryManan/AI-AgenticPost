"""Post registry endpoints."""
from __future__ import annotations

from fastapi import APIRouter

from ...storage.db.repositories import PostRepo
from ..schemas.responses import PostList

router = APIRouter(prefix="/runs", tags=["posts"])


@router.get("/{run_id}/posts", response_model=PostList)
async def list_posts_for_run(run_id: str) -> PostList:
    posts = PostRepo.list_for_run(run_id)
    return PostList(run_id=run_id, posts=posts)