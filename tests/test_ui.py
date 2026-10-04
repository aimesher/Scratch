import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
import yaml

from igflow import agent
from igflow.config import Config
from igflow.db import Store
from igflow.ui import App, make_handler
from test_pipeline import MASTER, make_clip, post


@pytest.fixture
def server(tmp_path, monkeypatch):
    for k in ("ANTHROPIC_API_KEY", "IG_USER_ID", "IG_ACCESS_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    cp = tmp_path / "config.yaml"
    cp.write_text(yaml.safe_dump({"brand": {"niche": "archviz", "voice": "calm"}, "watcher": {"stable_seconds": 0}}))
    cfg = Config.load(cp)
    app = App(cfg, cp)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield app, f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()


def call(base, path, body=None, method=None, headers=None, raw=None):
    h = {"X-IGFlow": "1", **(headers or {})}
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(base + path, data=data, method=method or ("POST" if data is not None else "GET"), headers=h)
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, (json.loads(r.read()) if r.headers["Content-Type"] == "application/json" else r.read()), r.headers
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}"), e.headers


def seed(app, pid="p1", shots=(6, 6)):
    store = app.store()
    store.create(pid, "reel", post(shots))
    (app.cfg.path("drop") / pid).mkdir(parents=True, exist_ok=True)
    store.close()


def test_serves_page_and_rejects_cross_site_requests(server):
    app, base = server
    assert call(base, "/")[0] == 200
    assert call(base, "/api/automation", {"publish": False}, headers={"X-IGFlow": ""})[0] == 403
    assert call(base, "/api/health", headers={"Host": "evil.example"})[0] == 403


def test_generating_without_api_key_gives_friendly_error(server):
    _, base = server
    code, body, _ = call(base, "/api/master/generate", {})
    assert code == 400 and "API key" in body["error"]


def test_settings_roundtrip_hides_secrets(server):
    app, base = server
    payload = {"brand": {"niche": "new niche"}, "video": {"min_seconds": 8, "max_seconds": 14}, "instagram": {"max_per_day": 2},
               "keys": {"ANTHROPIC_API_KEY": "sk-ant-secret-1234", "IG_USER_ID": "555"}}
    assert call(base, "/api/settings", payload, "PUT")[0] == 200
    _, view, _ = call(base, "/api/settings")
    assert view["brand"]["niche"] == "new niche" and view["video"]["max_seconds"] == 14
    assert view["keys"]["ANTHROPIC_API_KEY"]["set"] and "secret" not in json.dumps(view)
    assert "sk-ant-secret-1234" in (app.config_path.parent / ".env").read_text()
    bad = dict(payload, video={"min_seconds": 20, "max_seconds": 10})
    assert call(base, "/api/settings", bad, "PUT")[0] == 400


def test_master_validation(server):
    _, base = server
    assert call(base, "/api/master", {"text": "no headings"}, "PUT")[0] == 400
    assert call(base, "/api/master", {"text": agent.render_master(MASTER)}, "PUT")[0] == 200
    _, m, _ = call(base, "/api/master")
    assert m["exists"] and m["reference_image_prompt"].startswith("Timber house")


def test_upload_slots_trigger_assembly_and_range_streaming(server):
    app, base = server
    seed(app)
    src = Path(app.cfg.base_dir) / "src"
    src.mkdir()
    make_clip(src / "a.mp4", 6)
    make_clip(src / "b.mov", 6, "720x1280", audio=False)
    for slot, f in (("shot1", "a.mp4"), ("shot2", "b.mov")):
        ext = Path(f).suffix
        code, body, _ = call(base, f"/api/posts/p1/upload?slot={slot}&ext={ext}", raw=(src / f).read_bytes())
        assert code == 200, body
    _, posts, _ = call(base, "/api/posts")
    assert posts["posts"][0]["files"] == {"shot1": "1.mp4", "shot2": "2.mov"}

    from igflow.watcher import process_drops
    store = app.store()
    process_drops(app.cfg, store, lambda m: None)
    assert store.get("p1")["status"] == "review"
    store.close()

    code, _, h = call(base, "/media/p1/final.mp4", headers={"Range": "bytes=0-99"})
    assert code == 206 and h["Content-Range"].startswith("bytes 0-99/")
    assert call(base, "/media/p1/final.jpg")[0] == 200
    assert call(base, "/api/posts/p1/upload?slot=shot1&ext=.mp4", raw=b"x")[0] == 400  # locked after processing


def test_upload_rejects_bad_slot_and_extension(server):
    app, base = server
    seed(app)
    assert call(base, "/api/posts/p1/upload?slot=shot9&ext=.mp4", raw=b"x")[0] == 400
    assert call(base, "/api/posts/p1/upload?slot=shot1&ext=.exe", raw=b"x")[0] == 400
    assert call(base, "/api/posts/p1/upload?slot=music&ext=.mp4", raw=b"x")[0] == 400
    assert call(base, "/api/posts/nope/upload?slot=shot1&ext=.mp4", raw=b"x")[0] == 404


def test_caption_edit_approve_and_redo(server):
    app, base = server
    seed(app)
    store = app.store()
    store.update("p1", status="review", final_path="x.mp4")
    store.close()
    assert call(base, "/api/posts/p1/caption", {"caption": "New caption", "hashtags": ["#a", " b "]})[0] == 200
    assert call(base, "/api/posts/p1/caption", {"caption": " ", "hashtags": []})[0] == 400
    assert call(base, "/api/posts/p1/approve", {"at": "2999-01-01T10:00"})[0] == 200
    store = app.store()
    row = store.get("p1")
    store.close()
    assert row["status"] == "approved" and row["brief"]["caption"] == "New caption" and row["brief"]["hashtags"] == ["a", "b"]
    assert call(base, "/api/posts/p1/approve", {})[0] == 400  # already approved


def test_auto_publish_toggle(server):
    app, base = server
    assert call(base, "/api/automation", {"publish": False})[1] == {"publish": False}
    assert app.publish_enabled is False
