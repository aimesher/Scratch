"""Instagram publishing via the Instagram API with Instagram Login (resumable upload, no public hosting needed).

Flow: create container -> upload bytes to rupload -> poll status_code -> media_publish.
Endpoints are written from memory of Meta's docs and could not be checked from the build
environment. If a call fails, the HTTP error body is surfaced verbatim so you can compare
it with https://developers.facebook.com/docs/instagram-platform/content-publishing.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from . import actions
from .config import Config
from .db import Store, now_iso

GRAPH = "https://graph.instagram.com"
RUPLOAD = "https://rupload.facebook.com/ig-api-upload"
MEDIA_TYPES = {"reel": "REELS", "story": "STORIES"}


class InstagramError(RuntimeError):
    pass


def build_caption(post: dict) -> str:
    tags = " ".join("#" + t.lstrip("#") for t in post.get("hashtags", []))
    return f"{post['caption'].strip()}\n\n{tags}".strip()


class InstagramClient:
    def __init__(self, user_id: str, token: str, version: str = "v23.0", session=None, sleep=time.sleep, timeout_s: int = 300):
        self.user_id, self.token, self.version = user_id, token, version
        self.http = session or requests.Session()
        self.sleep, self.timeout_s = sleep, timeout_s

    @classmethod
    def from_env(cls, cfg: Config) -> "InstagramClient":
        user_id, token = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
        if not user_id or not token:
            raise InstagramError("Set IG_USER_ID and IG_ACCESS_TOKEN (in .env or the environment).")
        ig = cfg["instagram"]
        return cls(user_id, token, ig["api_version"], timeout_s=ig["status_timeout_seconds"])

    def _check(self, resp) -> dict:
        try:
            body = resp.json()
        except ValueError:
            body = {"raw": resp.text}
        if resp.status_code >= 400 or "error" in body:
            raise InstagramError(f"HTTP {resp.status_code}: {body}")
        return body

    def publish(self, video: Path, fmt: str, caption: str, video_url: str | None = None) -> str:
        """With `video_url` (a public link to the file) Instagram fetches it; otherwise the bytes are uploaded."""
        params = {"media_type": MEDIA_TYPES[fmt], "access_token": self.token}
        if video_url:
            params["video_url"] = video_url
        else:
            params["upload_type"] = "resumable"
        if fmt == "reel":
            params["caption"] = caption  # Stories do not take captions.
        container = self._check(
            self.http.post(f"{GRAPH}/{self.version}/{self.user_id}/media", data=params, timeout=60)
        )["id"]
        if not video_url:
            self._upload(container, video)
        self._wait_finished(container)
        return self._check(
            self.http.post(
                f"{GRAPH}/{self.version}/{self.user_id}/media_publish",
                data={"creation_id": container, "access_token": self.token},
                timeout=60,
            )
        )["id"]

    def _upload(self, container: str, video: Path) -> None:
        with open(video, "rb") as f:
            self._check(
                self.http.post(
                    f"{RUPLOAD}/{self.version}/{container}",
                    headers={
                        "Authorization": f"OAuth {self.token}",
                        "offset": "0",
                        "file_size": str(video.stat().st_size),
                    },
                    data=f,
                    timeout=600,
                )
            )

    def _wait_finished(self, container: str) -> None:
        deadline = time.monotonic() + self.timeout_s
        while True:
            body = self._check(
                self.http.get(
                    f"{GRAPH}/{self.version}/{container}",
                    params={"fields": "status_code,status", "access_token": self.token},
                    timeout=30,
                )
            )
            code = body.get("status_code")
            if code == "FINISHED":
                return
            if code in ("ERROR", "EXPIRED"):
                raise InstagramError(f"container {code}: {body.get('status')}")
            if time.monotonic() > deadline:
                raise InstagramError(f"container still {code} after {self.timeout_s}s")
            self.sleep(5)

    def refresh_token(self) -> dict:
        """Long-lived tokens last 60 days and can be refreshed after 24h."""
        return self._check(
            self.http.get(
                f"{GRAPH}/refresh_access_token",
                params={"grant_type": "ig_refresh_token", "access_token": self.token},
                timeout=30,
            )
        )


def publish_due(
    cfg: Config,
    store: Store,
    client: InstagramClient | None = None,
    dry_run: bool = False,
    log=print,
    media_url_for=None,
) -> int:
    """Post approved, due posts to Instagram, respecting max_per_day.

    `media_url_for(post_id)` returns a public link to the video when the server is online,
    which Instagram prefers over uploading the bytes. YouTube is left for you to post.
    """
    now = datetime.now(timezone.utc)
    limit = cfg["instagram"]["max_per_day"]
    since = now - timedelta(hours=24)
    posted = sum(
        1 for p in store.list()
        if (t := p["brief"].get("posted", {}).get("instagram")) and datetime.fromisoformat(t) >= since
    )
    count = 0
    for post in store.list("approved"):
        if "instagram" not in actions.platforms_for(cfg, post["format"]) or post["brief"].get("posted", {}).get("instagram"):
            continue
        if post["scheduled_at"] and datetime.fromisoformat(post["scheduled_at"]) > now:
            continue
        if posted + count >= limit:
            log(f"daily limit of {limit} reached, holding {post['id']}")
            break
        if dry_run:
            log(f"[dry-run] would publish {post['id']} ({post['format']}): {build_caption(post['brief'])[:60]}")
            continue
        client = client or InstagramClient.from_env(cfg)
        url = media_url_for(post["id"]) if media_url_for else None
        try:
            media_id = client.publish(Path(post["final_path"]), post["format"], build_caption(post["brief"]), video_url=url)
        except (InstagramError, requests.RequestException, OSError) as e:
            store.update(post["id"], status="failed", error=f"Instagram did not accept it: {e}")
            log(f"[{post['id']}] publish failed: {e}")
            continue
        store.update(post["id"], ig_media_id=media_id, error=None)
        remaining = actions.record_posted(cfg, store, store.get(post["id"]), "instagram")
        log(f"[{post['id']}] published to Instagram as {media_id}" + (f"; still to post: {', '.join(remaining)}" if remaining else ""))
        count += 1
    return count
