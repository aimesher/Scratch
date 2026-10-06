"""Sign-in for the Claude connector. When you add the connector, Claude sends you to a page here
where you type your dashboard password; Claude then gets a token for this server only."""
from __future__ import annotations

import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path

from mcp.server.auth.provider import (
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
    RefreshToken,
    construct_redirect_uri,
)
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken

from .security import token_hash

ACCESS_TTL = 24 * 3600
REFRESH_TTL = 90 * 86400
CODE_TTL = 300
PENDING_TTL = 900


class ReelStudioOAuth:
    def __init__(self, db_path: Path, public_url: str):
        self.public_url = public_url.rstrip("/")
        self.db = sqlite3.connect(db_path, check_same_thread=False, timeout=10)
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(
                """CREATE TABLE IF NOT EXISTS clients (client_id TEXT PRIMARY KEY, info TEXT NOT NULL);
                   CREATE TABLE IF NOT EXISTS tokens (hash TEXT PRIMARY KEY, kind TEXT NOT NULL, client_id TEXT NOT NULL,
                       scopes TEXT NOT NULL, expires_at INTEGER NOT NULL, pair TEXT NOT NULL);"""
            )
            self.db.commit()
        self.pending: dict[str, tuple[str, AuthorizationParams, float]] = {}
        self.codes: dict[str, AuthorizationCode] = {}

    # ----- clients (Claude registers itself the first time) -----
    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        with self.lock:
            row = self.db.execute("SELECT info FROM clients WHERE client_id = ?", (client_id,)).fetchone()
        return OAuthClientInformationFull.model_validate_json(row[0]) if row else None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO clients VALUES (?, ?)", (client_info.client_id, client_info.model_dump_json()))
            self.db.commit()

    # ----- authorization: send the person to the password page -----
    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        now = time.time()
        self.pending = {k: v for k, v in self.pending.items() if now - v[2] < PENDING_TTL}
        req = secrets.token_urlsafe(24)
        self.pending[req] = (client.client_id, params, now)
        return f"{self.public_url}/connect-claude?req={req}"

    def pending_request(self, req: str) -> tuple[str, AuthorizationParams] | None:
        item = self.pending.get(req)
        if not item or time.time() - item[2] > PENDING_TTL:
            return None
        return item[0], item[1]

    def approve(self, req: str) -> str:
        """Called after the right password: issue a code and return Claude's redirect URL."""
        client_id, params, _ = self.pending.pop(req)
        code = secrets.token_urlsafe(32)
        self.codes[code] = AuthorizationCode(
            code=code, scopes=params.scopes or [], expires_at=time.time() + CODE_TTL, client_id=client_id,
            code_challenge=params.code_challenge, redirect_uri=params.redirect_uri,
            redirect_uri_provided_explicitly=params.redirect_uri_provided_explicitly, resource=params.resource,
        )
        return construct_redirect_uri(str(params.redirect_uri), code=code, state=params.state)

    def deny(self, req: str) -> str | None:
        item = self.pending.pop(req, None)
        if not item:
            return None
        return construct_redirect_uri(str(item[1].redirect_uri), error="access_denied", state=item[1].state)

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> AuthorizationCode | None:
        code = self.codes.get(authorization_code)
        if not code or code.client_id != client.client_id or code.expires_at < time.time():
            return None
        return code

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        self.codes.pop(authorization_code.code, None)
        return self._issue(client.client_id, authorization_code.scopes)

    # ----- tokens -----
    def _issue(self, client_id: str, scopes: list[str]) -> OAuthToken:
        access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        now = int(time.time())
        pair = secrets.token_hex(8)
        with self.lock:
            self.db.executemany("INSERT INTO tokens VALUES (?, ?, ?, ?, ?, ?)", [
                (token_hash(access), "access", client_id, json.dumps(scopes), now + ACCESS_TTL, pair),
                (token_hash(refresh), "refresh", client_id, json.dumps(scopes), now + REFRESH_TTL, pair),
            ])
            self.db.execute("DELETE FROM tokens WHERE expires_at < ?", (now,))
            self.db.commit()
        return OAuthToken(access_token=access, token_type="Bearer", expires_in=ACCESS_TTL, refresh_token=refresh,
                          scope=" ".join(scopes) or None)

    def _row(self, token: str, kind: str):
        with self.lock:
            return self.db.execute(
                "SELECT client_id, scopes, expires_at, pair FROM tokens WHERE hash = ? AND kind = ?", (token_hash(token), kind)
            ).fetchone()

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> RefreshToken | None:
        row = self._row(refresh_token, "refresh")
        if not row or row[0] != client.client_id or row[2] < time.time():
            return None
        return RefreshToken(token=refresh_token, client_id=row[0], scopes=json.loads(row[1]), expires_at=row[2])

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        await self.revoke_token(refresh_token)  # rotate: the old pair stops working
        return self._issue(client.client_id, scopes or refresh_token.scopes)

    async def load_access_token(self, token: str) -> AccessToken | None:
        row = self._row(token, "access")
        if not row or row[2] < time.time():
            return None
        return AccessToken(token=token, client_id=row[0], scopes=json.loads(row[1]), expires_at=row[2])

    async def revoke_token(self, token: AccessToken | RefreshToken) -> None:
        with self.lock:
            row = self.db.execute("SELECT pair FROM tokens WHERE hash = ?", (token_hash(token.token),)).fetchone()
            if row:
                self.db.execute("DELETE FROM tokens WHERE pair = ?", (row[0],))
                self.db.commit()

    def disconnect_all(self) -> int:
        """Sign every connected Claude out (Settings > Disconnect Claude)."""
        with self.lock:
            n = self.db.execute("DELETE FROM tokens").rowcount
            self.db.commit()
        return n

    def connected(self) -> bool:
        with self.lock:
            return self.db.execute("SELECT 1 FROM tokens WHERE kind = 'refresh' AND expires_at > ? LIMIT 1", (int(time.time()),)).fetchone() is not None
