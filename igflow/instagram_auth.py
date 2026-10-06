"""Instagram Business Login with your own Meta app: connect once, the token stays on your server.

Endpoints (Meta's "Business Login for Instagram"):
  1. https://www.instagram.com/oauth/authorize       -> authorization code
  2. https://api.instagram.com/oauth/access_token     -> short-lived token (1 hour)
  3. https://graph.instagram.com/access_token         -> long-lived token (60 days)
  4. https://graph.instagram.com/refresh_access_token -> another 60 days
"""
from __future__ import annotations

import os
import time
from urllib.parse import urlencode

import requests

AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = "instagram_business_basic,instagram_business_content_publish"
REFRESH_WHEN_DAYS_LEFT = 10


class InstagramAuthError(RuntimeError):
    pass


def _check(resp) -> dict:
    try:
        body = resp.json()
    except ValueError:
        body = {"raw": resp.text[:300]}
    if resp.status_code >= 400 or (isinstance(body, dict) and "error" in body and "access_token" not in body):
        msg = body.get("error_message") or body.get("error", {}) if isinstance(body, dict) else body
        raise InstagramAuthError(f"Instagram said: {msg}")
    return body


def authorize_url(app_id: str, redirect_uri: str, state: str) -> str:
    return AUTHORIZE_URL + "?" + urlencode(
        {"client_id": app_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": SCOPES, "state": state}
    )


def connect(app_id: str, app_secret: str, redirect_uri: str, code: str, http=requests) -> dict:
    """Turn the code from Instagram's redirect into a 60-day token plus account details."""
    code = code.split("#")[0]  # Instagram appends "#_" to the code
    short = _check(http.post(SHORT_TOKEN_URL, data={
        "client_id": app_id, "client_secret": app_secret, "grant_type": "authorization_code",
        "redirect_uri": redirect_uri, "code": code,
    }, timeout=30))
    if "data" in short and isinstance(short["data"], list):  # some API versions wrap the answer
        short = short["data"][0]
    long = _check(http.get(f"{GRAPH}/access_token", params={
        "grant_type": "ig_exchange_token", "client_secret": app_secret, "access_token": short["access_token"],
    }, timeout=30))
    token = long["access_token"]
    me = _check(http.get(f"{GRAPH}/me", params={"fields": "user_id,username,account_type", "access_token": token}, timeout=30))
    return {
        "IG_ACCESS_TOKEN": token,
        "IG_USER_ID": str(me.get("user_id") or short.get("user_id")),
        "IG_USERNAME": me.get("username", ""),
        "IG_TOKEN_EXPIRES_AT": str(int(time.time()) + int(long.get("expires_in", 60 * 86400))),
        "IG_TOKEN_REFRESHED_AT": str(int(time.time())),
        "_account_type": me.get("account_type", ""),
    }


def refresh_if_needed(http=requests, now: float | None = None) -> dict | None:
    """Refresh the token when it has fewer than 10 days left. Returns new values to save, or None."""
    token = os.environ.get("IG_ACCESS_TOKEN")
    expires = float(os.environ.get("IG_TOKEN_EXPIRES_AT") or 0)
    refreshed = float(os.environ.get("IG_TOKEN_REFRESHED_AT") or 0)
    now = time.time() if now is None else now
    if not token or not expires or expires - now > REFRESH_WHEN_DAYS_LEFT * 86400 or now - refreshed < 86400:
        return None  # Meta only refreshes tokens that are at least a day old
    body = _check(http.get(f"{GRAPH}/refresh_access_token", params={"grant_type": "ig_refresh_token", "access_token": token}, timeout=30))
    return {
        "IG_ACCESS_TOKEN": body["access_token"],
        "IG_TOKEN_EXPIRES_AT": str(int(now) + int(body.get("expires_in", 60 * 86400))),
        "IG_TOKEN_REFRESHED_AT": str(int(now)),
    }


def recent_captions(limit: int = 12, http=requests) -> list[dict]:
    """Your latest Instagram captions, used to match your tone. Empty when not connected."""
    token = os.environ.get("IG_ACCESS_TOKEN")
    if not token:
        return []
    body = _check(http.get(f"{GRAPH}/me/media", params={
        "fields": "caption,media_type,timestamp,like_count,comments_count", "limit": limit, "access_token": token,
    }, timeout=30))
    return [
        {k: m.get(k) for k in ("caption", "media_type", "timestamp", "like_count", "comments_count")}
        for m in body.get("data", []) if m.get("caption")
    ]
