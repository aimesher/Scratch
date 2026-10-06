"""The online version: gateway login, Claude connector sign-in (OAuth + PKCE), MCP tools,
public video links and Instagram connect, all against a real in-process dashboard."""
import base64
import hashlib
import json
import re
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import pytest
import yaml
from starlette.testclient import TestClient

from igflow import agent, hosted, instagram_auth, security
from igflow.config import Config
from igflow.ui import App, make_handler
from test_pipeline import MASTER, make_clip, post

PASSWORD = "correct horse battery"
MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}


@pytest.fixture
def online(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "IG_USER_ID", "IG_ACCESS_TOKEN", "IG_APP_ID", "IG_APP_SECRET",
              "IG_USERNAME", "IG_TOKEN_EXPIRES_AT", "REELSTUDIO_SECRET"):
        monkeypatch.delenv(k, raising=False)
    cp = tmp_path / "config.yaml"
    cp.write_text(yaml.safe_dump({"brand": {"niche": "yoga", "voice": "warm"}, "watcher": {"stable_seconds": 0},
                                  "timezone": "Asia/Kolkata"}))
    app = App(Config.load(cp), cp)
    app.public_url = "https://testserver"
    internal = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=internal.serve_forever, daemon=True).start()
    asgi = hosted.build(app, internal.server_address[1], "https://testserver", PASSWORD)
    with TestClient(asgi, base_url="https://testserver", follow_redirects=False) as client:
        yield app, client
    internal.shutdown()


def sign_in(client):
    r = client.post("/login", data={"password": PASSWORD, "next": "/"})
    assert r.status_code == 303 and security.SESSION_COOKIE in r.cookies


def pkce():
    verifier = base64.urlsafe_b64encode(b"v" * 40).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def connect_claude(client) -> str:
    """Walk the same steps Claude takes when you add the connector. Returns the access token."""
    meta = client.get("/.well-known/oauth-authorization-server").json()
    reg = client.post(meta["registration_endpoint"].replace("https://testserver", ""), json={
        "redirect_uris": ["https://claude.ai/api/mcp/auth_callback"], "client_name": "Claude",
        "token_endpoint_auth_method": "client_secret_post", "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"]}).json()
    verifier, challenge = pkce()
    r = client.get("/authorize", params={
        "response_type": "code", "client_id": reg["client_id"], "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": "xyz"})
    assert r.status_code in (302, 307)
    consent = urlparse(r.headers["location"])
    req = parse_qs(consent.query)["req"][0]
    page = client.get(consent.path + "?" + consent.query)
    assert "Allow Claude to use Reel Studio" in page.text and "claude.ai" in page.text

    wrong = client.post("/connect-claude", data={"req": req, "password": "nope", "action": "allow"})
    assert wrong.status_code == 200 and "Wrong password" in wrong.text
    ok = client.post("/connect-claude", data={"req": req, "password": PASSWORD, "action": "allow"})
    assert ok.status_code == 303
    back = urlparse(ok.headers["location"])
    assert back.netloc == "claude.ai"
    q = parse_qs(back.query)
    assert q["state"] == ["xyz"]
    tok = client.post("/token", data={
        "grant_type": "authorization_code", "code": q["code"][0], "redirect_uri": "https://claude.ai/api/mcp/auth_callback",
        "client_id": reg["client_id"], "client_secret": reg["client_secret"], "code_verifier": verifier})
    assert tok.status_code == 200, tok.text
    connect_claude.last = {**tok.json(), "client_id": reg["client_id"], "client_secret": reg["client_secret"]}
    return tok.json()["access_token"]


def rpc(client, token, method, params=None, id_=1):
    r = client.post("/mcp", headers=MCP_HEADERS | {"Authorization": f"Bearer {token}"},
                    json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params or {}})
    assert r.status_code == 200, r.text
    return r.json()


def call_tool(client, token, name, args=None):
    out = rpc(client, token, "tools/call", {"name": name, "arguments": args or {}})["result"]
    text = out["content"][0]["text"] if out.get("content") else ""
    return out.get("isError", False), (out.get("structuredContent") or (json.loads(text) if text.startswith("{") else text))


# ---------- dashboard behind a password ----------

def test_dashboard_requires_sign_in_and_proxies_after(online):
    app, client = online
    assert client.get("/").headers["location"].startswith("/login")
    assert client.get("/api/posts").status_code == 401
    bad = client.post("/login", data={"password": "nope", "next": "/"})
    assert bad.status_code == 200 and "Wrong password" in bad.text
    sign_in(client)
    assert client.get("/").status_code == 200 and "Reel Studio" in client.get("/").text
    health = client.get("/api/health").json()
    assert any(c["id"] == "ffmpeg" for c in health["checks"])
    online_info = client.get("/api/settings").json()["online"]
    assert online_info["mcp_url"] == "https://testserver/mcp"
    assert online_info["ig_redirect_uri"] == "https://testserver/oauth/instagram/callback"


def test_login_locks_after_repeated_wrong_passwords(online):
    _, client = online
    for _ in range(8):
        client.post("/login", data={"password": "nope"})
    r = client.post("/login", data={"password": PASSWORD})
    assert "Too many wrong attempts" in r.text


def test_open_redirect_is_refused(online):
    _, client = online
    r = client.post("/login", data={"password": PASSWORD, "next": "//evil.example/"})
    assert r.headers["location"] == "/"


def test_uploads_pass_through_the_gateway(online, tmp_path):
    app, client = online
    sign_in(client)
    s = app.store()
    s.create("p1", "reel", post())
    s.close()
    (app.cfg.path("drop") / "p1").mkdir(parents=True)
    make_clip(tmp_path / "a.mp4", 6)
    data = (tmp_path / "a.mp4").read_bytes()
    r = client.post("/api/posts/p1/upload?slot=shot1&ext=.mp4", content=data, headers={"X-IGFlow": "1"})
    assert r.status_code == 200, r.text
    assert (app.cfg.path("drop") / "p1" / "1.mp4").read_bytes() == data
    assert client.post("/api/automation", json={"publish": False}).status_code == 403  # CSRF header still required


# ---------- Claude connector ----------

def test_mcp_requires_a_token(online):
    _, client = online
    r = client.post("/mcp", headers=MCP_HEADERS, json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401 and "resource_metadata" in r.headers.get("www-authenticate", "")


def test_claude_signs_in_and_runs_the_workflow(online):
    app, client = online
    token = connect_claude(client)
    init = rpc(client, token, "initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                             "clientInfo": {"name": "test", "version": "1"}})
    assert init["result"]["serverInfo"]["name"] == "reelstudio"
    names = {t["name"] for t in rpc(client, token, "tools/list")["result"]["tools"]}
    assert {"reelstudio_get_account", "reelstudio_create_posts", "reelstudio_schedule_post"} <= names

    err, acct = call_tool(client, token, "reelstudio_get_account")
    assert not err and acct["profile"]["niche"] == "yoga" and acct["timezone"] == "Asia/Kolkata" and acct["master_prompt"] is None

    err, msg = call_tool(client, token, "reelstudio_create_posts", {"posts": [post()]})
    assert err and "master prompt" in str(msg)

    err, saved = call_tool(client, token, "reelstudio_save_master_prompt", dict(MASTER))
    assert not err and saved["saved"]
    err, again = call_tool(client, token, "reelstudio_save_master_prompt", dict(MASTER))
    assert err and "already exists" in str(again)

    bad = post(seconds=(8, 8))
    err, msg = call_tool(client, token, "reelstudio_create_posts", {"posts": [bad]})
    assert err and "16s" in str(msg)

    draft = post()
    draft["format"] = "reel"
    err, created = call_tool(client, token, "reelstudio_create_posts", {"posts": [draft]})
    assert not err, created
    pid = created["created"][0]["id"]
    assert "Photoreal" in created["created"][0]["flow_steps"][0]["flow_prompt"]

    err, msg = call_tool(client, token, "reelstudio_schedule_post", {"post_id": pid, "user_confirmed": True})
    assert err and "review" in str(msg)  # no video yet

    s = app.store()
    s.update(pid, status="review", final_path="x.mp4")
    s.close()
    err, msg = call_tool(client, token, "reelstudio_schedule_post", {"post_id": pid, "user_confirmed": False})
    assert err and "confirm" in str(msg)
    err, sched = call_tool(client, token, "reelstudio_schedule_post",
                           {"post_id": pid, "user_confirmed": True, "publish_at": "2026-10-07T10:00"})
    assert not err and sched["status"] == "approved" and "10:00" in sched["scheduled_for"]
    s = app.store()
    assert s.get(pid)["scheduled_at"] == "2026-10-07T04:30:00+00:00"  # 10:00 in Kolkata
    s.close()
    err, _ = call_tool(client, token, "reelstudio_update_post_text", {"post_id": pid, "caption": "New words", "hashtags": ["#yoga"]})
    assert not err
    err, got = call_tool(client, token, "reelstudio_get_post", {"post_id": pid})
    assert got["brief"]["caption"] == "New words" and got["caption_as_posted"].endswith("#yoga")
    err, listed = call_tool(client, token, "reelstudio_list_posts", {"status": "approved"})
    assert listed["count"] == 1
    err, _ = call_tool(client, token, "reelstudio_unschedule_post", {"post_id": pid})
    assert not err


def test_refresh_token_rotates_and_disconnect_signs_out(online):
    app, client = online
    connect_claude(client)
    first = connect_claude.last
    form = {"grant_type": "refresh_token", "refresh_token": first["refresh_token"],
            "client_id": first["client_id"], "client_secret": first["client_secret"]}
    new = client.post("/token", data=form)
    assert new.status_code == 200, new.text
    token = new.json()["access_token"]
    assert token != first["access_token"]
    assert client.post("/token", data=form).status_code == 400  # the old refresh token is spent
    old = client.post("/mcp", headers=MCP_HEADERS | {"Authorization": f"Bearer {first['access_token']}"},
                      json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert old.status_code == 401
    assert app.oauth.connected()
    sign_in(client)
    assert client.get("/api/settings").json()["online"]["claude_connected"]
    client.post("/api/claude/disconnect", json={}, headers={"X-IGFlow": "1"})
    r = client.post("/mcp", headers=MCP_HEADERS | {"Authorization": f"Bearer {token}"},
                    json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    assert r.status_code == 401


# ---------- video links for Instagram ----------

def test_public_media_link_needs_the_signature(online, tmp_path):
    app, client = online
    out = app.cfg.path("out") / "p1"
    out.mkdir(parents=True)
    make_clip(out / "final.mp4", 1)
    s = app.store()
    s.create("p1", "reel", post())
    s.update("p1", final_path=str(out / "final.mp4"))
    s.close()
    url = app.media_url_for("p1").replace("https://testserver", "")
    assert client.get(url).status_code == 200  # no sign-in needed: Instagram fetches this
    assert client.get(url.replace(url.split("/")[-1], "0" * 40 + ".mp4")).status_code == 404


# ---------- Instagram connect with your own Meta app ----------

def test_instagram_connect_flow(online, monkeypatch):
    app, client = online
    sign_in(client)
    r = client.get("/oauth/instagram/start")
    assert "Add your Meta app first" in r.text
    monkeypatch.setenv("IG_APP_ID", "123")
    monkeypatch.setenv("IG_APP_SECRET", "shh")
    r = client.get("/oauth/instagram/start")
    loc = urlparse(r.headers["location"])
    q = parse_qs(loc.query)
    assert loc.netloc == "www.instagram.com" and q["redirect_uri"] == ["https://testserver/oauth/instagram/callback"]
    assert "instagram_business_content_publish" in q["scope"][0]

    assert "expired" in client.get("/oauth/instagram/callback", params={"code": "c", "state": "forged"}).text

    seen = {}

    def fake_connect(app_id, secret, redirect, code):
        seen.update(app_id=app_id, code=code)
        return {"IG_ACCESS_TOKEN": "tok", "IG_USER_ID": "999", "IG_USERNAME": "yogastudio",
                "IG_TOKEN_EXPIRES_AT": "2000000000", "IG_TOKEN_REFRESHED_AT": "1", "_account_type": "BUSINESS"}

    monkeypatch.setattr(instagram_auth, "connect", fake_connect)
    r = client.get("/oauth/instagram/callback", params={"code": "abc#_", "state": q["state"][0]})
    assert "@yogastudio" in r.text and seen == {"app_id": "123", "code": "abc#_"}
    assert app.cfg["publish"]["method"] == "instagram_api"
    env = (app.config_path.parent / ".env").read_text()
    assert "IG_ACCESS_TOKEN=tok" in env and "_account_type" not in env
    assert client.get("/api/settings").json()["online"]["ig_username"] == "yogastudio"


def test_instagram_auth_exchanges_code_for_long_lived_token():
    calls = []

    class Http:
        def post(self, url, data, timeout):
            calls.append(("POST", url, data))
            return type("R", (), {"status_code": 200, "json": lambda s: {"access_token": "short", "user_id": 5}, "text": ""})()

        def get(self, url, params, timeout):
            calls.append(("GET", url, params))
            body = {"access_token": "long", "expires_in": 5184000} if url.endswith("/access_token") else {"user_id": "17841", "username": "me", "account_type": "BUSINESS"}
            return type("R", (), {"status_code": 200, "json": lambda s: body, "text": ""})()

    v = instagram_auth.connect("id", "secret", "https://x/cb", "CODE#_", http=Http())
    assert v["IG_ACCESS_TOKEN"] == "long" and v["IG_USER_ID"] == "17841" and v["IG_USERNAME"] == "me"
    assert calls[0][2]["code"] == "CODE" and calls[0][2]["grant_type"] == "authorization_code"
    assert calls[1][2]["grant_type"] == "ig_exchange_token"


def test_token_refresh_only_when_close_to_expiry(monkeypatch):
    class Http:
        def get(self, url, params, timeout):
            return type("R", (), {"status_code": 200, "json": lambda s: {"access_token": "new", "expires_in": 5184000}, "text": ""})()

    now = 1_800_000_000
    monkeypatch.setenv("IG_ACCESS_TOKEN", "old")
    monkeypatch.setenv("IG_TOKEN_REFRESHED_AT", str(now - 50 * 86400))
    monkeypatch.setenv("IG_TOKEN_EXPIRES_AT", str(now + 30 * 86400))
    assert instagram_auth.refresh_if_needed(Http(), now) is None  # plenty of time left
    monkeypatch.setenv("IG_TOKEN_EXPIRES_AT", str(now + 5 * 86400))
    assert instagram_auth.refresh_if_needed(Http(), now)["IG_ACCESS_TOKEN"] == "new"
