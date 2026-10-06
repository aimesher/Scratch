"""Operations shared by the command line and the dashboard."""
from __future__ import annotations

import shutil
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .config import Config
from .db import Store, now_iso

PLATFORMS = ("instagram", "youtube")


# Old names some browsers still report, mapped to the current ones.
TZ_ALIASES = {
    "Asia/Calcutta": "Asia/Kolkata", "Asia/Saigon": "Asia/Ho_Chi_Minh", "Asia/Katmandu": "Asia/Kathmandu",
    "Asia/Rangoon": "Asia/Yangon", "Asia/Dacca": "Asia/Dhaka", "Asia/Thimbu": "Asia/Thimphu",
    "Europe/Kiev": "Europe/Kyiv", "America/Buenos_Aires": "America/Argentina/Buenos_Aires",
    "Atlantic/Faeroe": "Atlantic/Faroe", "Pacific/Truk": "Pacific/Chuuk", "Pacific/Ponape": "Pacific/Pohnpei",
}


def normalize_tz(name: str) -> str:
    """A valid IANA timezone name, accepting old aliases. Raises ValueError if unknown."""
    name = name.strip()
    for candidate in (name, TZ_ALIASES.get(name, "")):
        if not candidate:
            continue
        try:
            ZoneInfo(candidate)
            return candidate
        except (ZoneInfoNotFoundError, ValueError):
            continue
    raise ValueError(f"Unknown timezone '{name}'. Use a name like Asia/Kolkata or Europe/London.")


def user_tz(tz_name: str | None):
    """The person's timezone. A hosted server runs in UTC, so local server time is not theirs."""
    if tz_name:
        try:
            return ZoneInfo(normalize_tz(tz_name))
        except ValueError:
            pass
    return datetime.now().astimezone().tzinfo


def parse_when(text: str | None, tz_name: str | None = None) -> str:
    """A time without an offset is read in the person's timezone. Returns UTC ISO. Empty means now."""
    if not text:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        dt = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        raise ValueError(f"Could not read the time '{text}'. Use a form like 2026-10-07T18:30.")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=user_tz(tz_name))
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def approve(store: Store, post_id: str, at: str | None = None, tz_name: str | None = None) -> None:
    post = store.get(post_id)
    if post["status"] not in ("review", "failed"):
        raise ValueError(f"{post_id} is {post['status']}; only posts in review (or failed) can be approved.")
    if post["status"] == "failed" and not post["final_path"]:
        raise ValueError("This post has no finished video yet. Start over with new clips.")
    store.update(post_id, status="approved", scheduled_at=parse_when(at, tz_name), error=None)


def unschedule(store: Store, post_id: str) -> None:
    """Take an approved post back to review, for example to change the time or caption."""
    post = store.get(post_id)
    if post["status"] != "approved":
        raise ValueError(f"{post_id} is {post['status']}; only approved posts can be unscheduled.")
    store.update(post_id, status="review", scheduled_at=None)


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


def auto_platforms(cfg: Config) -> list[str]:
    """Platforms the server posts to by itself. YouTube is always posted by hand."""
    return ["instagram"] if cfg["publish"]["method"] == "instagram_api" else []


def mark_posted(cfg: Config, store: Store, post_id: str, platform: str) -> list[str]:
    """Record that you posted it somewhere. Returns the platforms still to go; none left means published."""
    post = store.get(post_id)
    if post["status"] not in ("review", "approved", "published"):
        raise ValueError("Approve the video before marking it as posted.")
    if platform not in platforms_for(cfg, post["format"]):
        raise ValueError(f"This post is not meant for {platform}.")
    return record_posted(cfg, store, post, platform)


def record_posted(cfg: Config, store: Store, post: dict, platform: str) -> list[str]:
    post_id = post["id"]
    needed = platforms_for(cfg, post["format"])
    brief = post["brief"]
    brief.setdefault("posted", {})[platform] = now_iso()
    store.update_brief(post_id, brief)
    remaining = [p for p in needed if p not in brief["posted"]]
    if not remaining and post["status"] != "published":
        store.update(post_id, status="published", published_at=now_iso(), error=None)
    return remaining
