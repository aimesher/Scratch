"""Operations shared by the command line and the dashboard."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

from .config import Config
from .db import Store


def parse_when(text: str | None) -> str:
    """Local time (or an ISO string with offset) to UTC ISO. Empty means now."""
    if not text:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.astimezone()  # interpret as local time
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def approve(store: Store, post_id: str, at: str | None = None) -> None:
    post = store.get(post_id)
    if post["status"] not in ("review", "failed"):
        raise ValueError(f"{post_id} is {post['status']}; only posts in review (or failed) can be approved.")
    if post["status"] == "failed" and not post["final_path"]:
        raise ValueError("This post has no finished video yet. Start over with new clips.")
    store.update(post_id, status="approved", scheduled_at=parse_when(at), error=None)


def reject(store: Store, post_id: str, reason: str | None = None) -> None:
    store.get(post_id)
    store.update(post_id, status="rejected", error=reason)


def redo(cfg: Config, store: Store, post_id: str) -> None:
    """Move old clips aside and send the post back to 'briefed' to wait for new ones."""
    store.get(post_id)
    drop = cfg.path("drop") / post_id
    old = drop / "_old"
    old.mkdir(parents=True, exist_ok=True)
    for f in drop.iterdir():
        if f.is_file():
            shutil.move(str(f), old / f.name)
    store.update(post_id, status="briefed", error=None, final_path=None)
