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


# ---------- Windows installer files (cannot be run here, so check what can be) ----------

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name", ["Install Reel Studio.bat", "Start Reel Studio.bat", "setup.ps1"])
def test_windows_scripts_are_ascii_and_crlf(name):
    raw = (ROOT / name).read_bytes()
    raw.decode("ascii")  # PowerShell 5 misreads UTF-8 without a BOM
    assert raw.count(b"\r\n") == raw.count(b"\n"), "needs CRLF line endings so batch labels work"


def test_installer_points_at_real_files_and_this_branch():
    ps1 = (ROOT / "setup.ps1").read_text()
    bat = (ROOT / "Install Reel Studio.bat").read_text()
    for needed in ("requirements.txt", "Start Reel Studio.bat"):
        assert needed in ps1 and (ROOT / needed).exists()
    assert "setup.ps1" in bat and 'BRANCH=claude/instagram-agentic-google-flow-9pjpec"' in bat
    assert "%~dp0." in bat  # a trailing backslash before a closing quote would break the argument


def test_choosing_gemini_changes_which_key_is_required(server):
    app, base = server
    payload = {"brand": {}, "video": {"min_seconds": 10, "max_seconds": 12}, "instagram": {"max_per_day": 3}, "agent": {"provider": "gemini"}}
    assert call(base, "/api/settings", payload, "PUT")[0] == 200
    assert call(base, "/api/settings")[1]["agent"]["provider"] == "gemini"
    code, body, _ = call(base, "/api/master/generate", {})
    assert code == 400 and "Gemini" in body["error"]
    ai = next(c for c in call(base, "/api/health")[1]["checks"] if c["id"] == "ai")
    assert not ai["ok"] and "Gemini" in ai["label"]
    call(base, "/api/settings", dict(payload, keys={"GEMINI_API_KEY": "g-123456789"}), "PUT")
    assert next(c for c in call(base, "/api/health")[1]["checks"] if c["id"] == "ai")["ok"]
    assert call(base, "/api/settings", dict(payload, agent={"provider": "bogus"}), "PUT")[0] == 400


# ---------- copy-and-paste mode ----------

@pytest.fixture
def manual_server(server):
    app, base = server
    payload = {"brand": {"niche": "archviz", "voice": "calm"}, "video": {"min_seconds": 10, "max_seconds": 12},
               "instagram": {"max_per_day": 3}, "agent": {"provider": "manual"}}
    assert call(base, "/api/settings", payload, "PUT")[0] == 200
    return app, base


def test_manual_mode_needs_no_key_and_blocks_automatic_calls(manual_server):
    _, base = manual_server
    ai = next(c for c in call(base, "/api/health")[1]["checks"] if c["id"] == "ai")
    assert ai["ok"] and "copy and paste" in ai["label"]
    code, body, _ = call(base, "/api/master/generate", {})
    assert code == 400 and "Copy-and-paste" in body["error"]


def test_manual_master_roundtrip(manual_server):
    app, base = manual_server
    code, body, _ = call(base, "/api/manual/master/request", {"notes": "golden hour"})
    assert code == 200 and "golden hour" in body["text"] and "ONLY the JSON" in body["text"]
    assert call(base, "/api/manual/master/submit", {"reply": "no json here"})[0] == 400
    reply = "Here you go\n```json\n" + json.dumps(MASTER) + "\n```"
    assert call(base, "/api/manual/master/submit", {"reply": reply})[0] == 200
    assert call(base, "/api/master")[1]["exists"]
    assert call(base, "/api/manual/master/submit", {"reply": reply})[0] == 400  # exists, needs force
    assert call(base, "/api/manual/master/submit", {"reply": reply, "force": True})[0] == 200


def test_manual_plan_roundtrip_with_fix_request(manual_server):
    app, base = manual_server
    assert call(base, "/api/manual/plan/request", {"count": 1})[0] == 400  # no master yet
    app.master_path().write_text(agent.render_master(MASTER))
    code, body, _ = call(base, "/api/manual/plan/request", {"format": "reel", "count": 2, "theme": "lighting"})
    assert code == 200 and "Plan 2 Instagram reels" in body["text"] and "lighting" in body["text"]

    bad = json.dumps({"posts": [post(seconds=(8, 8))]})
    code, body, _ = call(base, "/api/manual/plan/submit", {"reply": bad, "format": "reel", "count": 1})
    assert code == 400 and any("16s" in p for p in body["problems"]) and "rejected" in body["fix_request"]
    assert call(base, "/api/posts")[1]["posts"] == []

    good = "Sure!\n" + json.dumps({"posts": [post()]})
    code, body, _ = call(base, "/api/manual/plan/submit", {"reply": good, "format": "reel", "count": 1})
    assert code == 200 and len(body["ids"]) == 1
    posts = call(base, "/api/posts")[1]["posts"]
    assert posts[0]["status"] == "briefed" and "Photoreal" in posts[0]["brief"]["shots"][0]["flow_prompt"]


# ---------- posting yourself (no Meta account) ----------

def test_default_is_manual_publishing_without_instagram_check(server):
    app, base = server
    assert call(base, "/api/settings")[1]["publish"] == {"method": "manual", "platforms": ["instagram", "youtube"]}
    assert "instagram" not in [c["id"] for c in call(base, "/api/health")[1]["checks"]]
    assert not app.auto_publish_active()  # the background loop never posts in manual mode
    payload = {"brand": {}, "video": {"min_seconds": 10, "max_seconds": 12}, "instagram": {"max_per_day": 3},
               "publish": {"method": "instagram_api", "platforms": ["instagram"]}}
    assert call(base, "/api/settings", payload, "PUT")[0] == 200
    assert app.auto_publish_active()
    assert "instagram" in [c["id"] for c in call(base, "/api/health")[1]["checks"]]
    for bad in ({"method": "fax", "platforms": ["instagram"]}, {"method": "manual", "platforms": []}, {"method": "manual", "platforms": ["tiktok"]}):
        assert call(base, "/api/settings", dict(payload, publish=bad), "PUT")[0] == 400


def test_mark_posted_per_platform_then_published(server):
    app, base = server
    seed(app)
    store = app.store()
    store.update("p1", status="briefed")
    store.close()
    assert call(base, "/api/posts/p1/posted", {"platform": "instagram"})[0] == 400  # not approved yet
    store = app.store()
    store.update("p1", status="approved")
    store.close()
    assert call(base, "/api/posts/p1/posted", {"platform": "tiktok"})[0] == 400
    code, body, _ = call(base, "/api/posts/p1/posted", {"platform": "instagram"})
    assert code == 200 and body["remaining"] == ["youtube"]
    post_row = call(base, "/api/posts")[1]["posts"][0]
    assert post_row["status"] == "approved" and "instagram" in post_row["posted"]
    assert call(base, "/api/posts/p1/posted", {"platform": "youtube"})[1]["remaining"] == []
    assert call(base, "/api/posts")[1]["posts"][0]["status"] == "published"


def test_story_only_needs_instagram(server):
    app, base = server
    store = app.store()
    store.create("s1", "story", post())
    store.update("s1", status="approved")
    store.close()
    assert call(base, "/api/posts")[1]["posts"][0]["platforms"] == ["instagram"]
    assert call(base, "/api/posts/s1/posted", {"platform": "youtube"})[0] == 400
    assert call(base, "/api/posts/s1/posted", {"platform": "instagram"})[1]["remaining"] == []


def test_download_link_sends_attachment_header(server):
    app, base = server
    seed(app)
    out = app.cfg.path("out") / "p1"
    out.mkdir(parents=True)
    make_clip(out / "final.mp4", 1)
    store = app.store()
    store.update("p1", status="approved", final_path=str(out / "final.mp4"))
    store.close()
    code, _, h = call(base, "/media/p1/final.mp4?download=1")
    assert code == 200 and h["Content-Disposition"] == 'attachment; filename="p1.mp4"'
    assert call(base, "/media/p1/final.mp4")[2].get("Content-Disposition") is None
