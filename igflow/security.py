"""Login sessions, password checks and signed links for the online version."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
from collections import defaultdict, deque
from pathlib import Path

SESSION_COOKIE = "rs_session"
SESSION_DAYS = 30


def secret_key(data_dir: Path) -> bytes:
    """REELSTUDIO_SECRET if set, else a random key created once and kept with your data."""
    if env := os.environ.get("REELSTUDIO_SECRET"):
        return env.encode()
    path = data_dir / "secret.key"
    if not path.exists():
        path.write_text(secrets.token_urlsafe(48))
        try:
            path.chmod(0o600)
        except OSError:
            pass
    return path.read_text().strip().encode()


def _sign(key: bytes, value: str) -> str:
    return hmac.new(key, value.encode(), hashlib.sha256).hexdigest()


def make_session(key: bytes, now: float | None = None) -> str:
    expires = int((now or time.time()) + SESSION_DAYS * 86400)
    return f"{expires}.{_sign(key, f'session:{expires}')}"


def valid_session(key: bytes, cookie: str | None, now: float | None = None) -> bool:
    if not cookie or "." not in cookie:
        return False
    expires, sig = cookie.split(".", 1)
    if not expires.isdigit() or int(expires) < (now or time.time()):
        return False
    return hmac.compare_digest(sig, _sign(key, f"session:{expires}"))


def media_signature(key: bytes, post_id: str) -> str:
    """Unguessable part of the public video link Instagram downloads from."""
    return _sign(key, f"media:{post_id}")[:40]


def check_password(given: str, expected: str) -> bool:
    return bool(expected) and hmac.compare_digest(given.encode(), expected.encode())


class LoginLimiter:
    """At most `attempts` wrong passwords per address in `window` seconds."""

    def __init__(self, attempts: int = 8, window: int = 900):
        self.attempts, self.window = attempts, window
        self.failures: dict[str, deque] = defaultdict(deque)

    def blocked(self, who: str, now: float | None = None) -> bool:
        now = now or time.time()
        q = self.failures[who]
        while q and now - q[0] > self.window:
            q.popleft()
        return len(q) >= self.attempts

    def fail(self, who: str, now: float | None = None) -> None:
        self.failures[who].append(now or time.time())

    def reset(self, who: str) -> None:
        self.failures.pop(who, None)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()
