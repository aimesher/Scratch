"""Operations shared by the command line and the dashboard."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone

from .config import Config
from .db import Store, now_iso

PLATFORMS = ("instagram", "youtube")


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


def platforms_for(cfg: Config, fmt: str) -> list[str]:
    """Where a post goes. Stories exist only on Instagram."""
    chosen = [p for p in cfg["publish"]["platforms"] if p in PLATFORMS] or ["instagram"]
    return ["instagram"] if fmt == "story" else chosen


def mark_posted(cfg: Config, store: Store, post_id: str, platform: str) -> list[str]:
    """Record that you posted it somewhere. Returns the platforms still to go; none left means published."""
    post = store.get(post_id)
    if post["status"] not in ("review", "approved", "published"):
        raise ValueError("Approve the video before marking it as posted.")
    needed = platforms_for(cfg, post["format"])
    if platform not in needed:
        raise ValueError(f"This post is not meant for {platform}.")
    brief = post["brief"]
    brief.setdefault("posted", {})[platform] = now_iso()
    store.update_brief(post_id, brief)
    remaining = [p for p in needed if p not in brief["posted"]]
    if not remaining and post["status"] != "published":
        store.update(post_id, status="published", published_at=now_iso(), error=None)
    return remaining
