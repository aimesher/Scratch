"""Local web dashboard. Standard library only; serves igflow/static/index.html on 127.0.0.1."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from collections import deque
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yaml

from . import actions, agent
from .config import DEFAULTS, Config, mask, set_env_values
from .db import Store
from .publish import publish_due
from .watcher import AUDIO_EXT, VIDEO_EXT, process_drops

STATIC = Path(__file__).parent / "static"
MAX_UPLOAD = 2 * 1024**3
KEYS = ("GEMINI_API_KEY", "ANTHROPIC_API_KEY", "IG_USER_ID", "IG_ACCESS_TOKEN")
PROVIDER_KEY = {"gemini": "GEMINI_API_KEY", "anthropic": "ANTHROPIC_API_KEY"}
PROVIDERS = ("gemini", "anthropic", "manual")


class ApiError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


class _Handled(Exception):
    """The handler already wrote its response."""


class App:
    def __init__(self, cfg: Config, config_path: Path):
        self.cfg, self.config_path = cfg, config_path
        self.events: deque = deque(maxlen=300)
        self.publish_enabled = True
        self.stop = threading.Event()

    def store(self) -> Store:
        return Store(self.cfg.path("data") / "queue.db")

    def say(self, msg: str) -> None:
        self.events.appendleft({"t": datetime.now(timezone.utc).isoformat(timespec="seconds"), "msg": msg})

    def background(self) -> None:
        """Watch drop folders and publish due posts, like `igflow run`."""
        while not self.stop.is_set():
            try:
                store = self.store()
                try:
                    process_drops(self.cfg, store, self.say)
                    if self.auto_publish_active():
                        publish_due(self.cfg, store, log=self.say)
                finally:
                    store.close()
            except Exception as e:  # keep the loop alive
                self.say(f"Background error: {e}")
            self.stop.wait(self.cfg["watcher"]["poll_seconds"])

    def auto_publish_active(self) -> bool:
        return self.publish_enabled and self.cfg["publish"]["method"] == "instagram_api"

    # ----- views -----

    def provider(self) -> str:
        return self.cfg["agent"]["provider"] if self.cfg["agent"]["provider"] in PROVIDERS else "anthropic"

    def master_path(self) -> Path:
        return self.cfg.path("data") / "master_prompt.md"

    def post_view(self, p: dict) -> dict:
        drop = self.cfg.path("drop") / p["id"]
        files: dict[str, str] = {}
        if drop.is_dir():
            for f in sorted(drop.iterdir()):
                if not f.is_file():
                    continue
                m = re.match(r"(\d+)\.", f.name)
                if m and f.suffix.lower() in VIDEO_EXT:
                    files[f"shot{int(m.group(1))}"] = f.name
                elif f.stem.lower() == "music" and f.suffix.lower() in AUDIO_EXT:
                    files["music"] = f.name
        final = Path(p["final_path"]) if p["final_path"] else None
        return {
            "id": p["id"], "format": p["format"], "status": p["status"], "brief": p["brief"],
            "created_at": p["created_at"], "scheduled_at": p["scheduled_at"], "published_at": p["published_at"],
            "ig_media_id": p["ig_media_id"], "error": p["error"], "files": files,
            "has_video": bool(final and final.exists()),
            "drop_folder": str(drop),
            "platforms": actions.platforms_for(self.cfg, p["format"]),
            "posted": p["brief"].get("posted", {}),
        }

    def ai_check(self) -> dict:
        p = self.provider()
        if p == "manual":
            return {"id": "ai", "label": "Prompt writer: copy and paste (no key needed)", "ok": True, "go": None}
        name = "Gemini" if p == "gemini" else "Claude"
        return {"id": "ai", "label": f"Prompt writer connected ({name})", "ok": bool(os.environ.get(PROVIDER_KEY[p])), "go": "settings"}

    def health(self) -> dict:
        brand = self.cfg["brand"]
        ig_ready = bool(os.environ.get("IG_USER_ID") and os.environ.get("IG_ACCESS_TOKEN"))
        checks = [
                {"id": "ffmpeg", "label": "Video tools (ffmpeg) installed", "ok": bool(shutil.which("ffmpeg") and shutil.which("ffprobe")), "go": None},
                {"id": "brand", "label": "Account profile filled in", "ok": bool(brand.get("niche") and brand.get("voice")), "go": "settings"},
                self.ai_check(),
                {"id": "master", "label": "Master prompt created", "ok": self.master_path().exists(), "go": "create"},
        ]
        if self.cfg["publish"]["method"] == "instagram_api":
            checks.append({"id": "instagram", "label": "Instagram connected", "ok": ig_ready, "go": "settings"})
        return {"checks": checks}

    def settings_view(self) -> dict:
        raw = self.cfg.raw
        return {
            "brand": raw["brand"],
            "video": {"min_seconds": raw["video"]["min_seconds"], "max_seconds": raw["video"]["max_seconds"]},
            "instagram": {"max_per_day": raw["instagram"]["max_per_day"]},
            "agent": {"provider": self.provider()},
            "publish": {"method": raw["publish"]["method"], "platforms": raw["publish"]["platforms"]},
            "keys": {k: {"set": bool(os.environ.get(k)), "hint": mask(os.environ.get(k)) if k != "IG_USER_ID" else (os.environ.get(k) or "")} for k in KEYS},
        }

    def save_settings(self, data: dict) -> None:
        file_raw = yaml.safe_load(self.config_path.read_text()) or {}
        brand = {k: str(data.get("brand", {}).get(k, "")).strip() for k in DEFAULTS["brand"]}
        file_raw.setdefault("brand", {}).update(brand)
        video = data.get("video", {})
        try:
            lo, hi = int(video["min_seconds"]), int(video["max_seconds"])
            per_day = int(data["instagram"]["max_per_day"])
        except (KeyError, TypeError, ValueError):
            raise ApiError("Length and daily limit must be whole numbers.")
        if not (1 <= lo <= hi <= 60):
            raise ApiError("Minimum length must be at least 1 and no more than the maximum (up to 60 seconds).")
        if not 1 <= per_day <= 25:
            raise ApiError("Posts per day must be between 1 and 25.")
        file_raw.setdefault("video", {}).update({"min_seconds": lo, "max_seconds": hi})
        file_raw.setdefault("instagram", {})["max_per_day"] = per_day
        provider = (data.get("agent") or {}).get("provider", self.provider())
        if provider not in PROVIDERS:
            raise ApiError("Choose Gemini, Claude or copy and paste as the prompt writer.")
        file_raw.setdefault("agent", {})["provider"] = provider
        pub = data.get("publish") or {}
        method = pub.get("method", self.cfg["publish"]["method"])
        platforms = pub.get("platforms", self.cfg["publish"]["platforms"])
        if method not in ("manual", "instagram_api"):
            raise ApiError("Choose how you publish.")
        if not isinstance(platforms, list) or not platforms or any(p not in actions.PLATFORMS for p in platforms):
            raise ApiError("Pick at least one place to post: Instagram or YouTube.")
        file_raw["publish"] = {"method": method, "platforms": [p for p in actions.PLATFORMS if p in platforms]}
        self.config_path.write_text(yaml.safe_dump(file_raw, sort_keys=False, allow_unicode=True))
        keys = {k: str(v).strip() for k, v in (data.get("keys") or {}).items() if k in KEYS and str(v).strip()}
        if keys:
            set_env_values(self.config_path.parent / ".env", keys)
        self.cfg = Config(file_raw, self.config_path.parent)

    def require_key(self) -> None:
        if self.provider() == "manual":
            raise ApiError("Copy-and-paste mode is on. Use the Copy request button, then paste the reply.")
        if not os.environ.get(PROVIDER_KEY[self.provider()]):
            raise ApiError("Add your Gemini API key in Settings first." if self.provider() == "gemini" else "Add your Claude API key in Settings first.")

    def save_upload(self, post: dict, slot: str, ext: str, length: int, rfile) -> str:
        if not re.fullmatch(r"shot[1-3]|music", slot):
            raise ApiError("Unknown upload slot.")
        ext = ext.lower()
        allowed = AUDIO_EXT if slot == "music" else VIDEO_EXT
        if ext not in allowed:
            raise ApiError(f"Use one of: {', '.join(sorted(allowed))}")
        if post["status"] != "briefed":
            raise ApiError("This post already has its clips. Use 'Start over with new clips' first.")
        if slot != "music" and int(slot[4:]) > len(post["brief"]["shots"]):
            raise ApiError("This post does not have that many shots.")
        if not 0 < length <= MAX_UPLOAD:
            raise ApiError("File is empty or larger than 2 GB.")
        drop = self.cfg.path("drop") / post["id"]
        drop.mkdir(parents=True, exist_ok=True)
        stem = "music" if slot == "music" else slot[4:]
        tmp = drop / f".{stem}.upload"  # hidden, so the watcher ignores it until it is complete
        remaining = length
        with open(tmp, "wb") as f:
            while remaining:
                chunk = rfile.read(min(1024 * 1024, remaining))
                if not chunk:
                    tmp.unlink(missing_ok=True)
                    raise ApiError("Upload was interrupted. Try again.")
                f.write(chunk)
                remaining -= len(chunk)
        for old in drop.iterdir():
            if old.is_file() and old.stem == stem and old.suffix.lower() in (VIDEO_EXT | AUDIO_EXT):
                old.unlink()
        final = drop / f"{stem}{ext}"
        os.replace(tmp, final)
        self.say(f"Received {final.name} for {post['id']}")
        return final.name


def open_folder(path: Path) -> bool:
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        elif sys.platform.startswith("win"):
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(path)], stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
        return True
    except (OSError, FileNotFoundError):
        return False


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "igflow"

        def log_message(self, *a):  # quiet
            pass

        # ----- plumbing -----
        def _json(self, data, status=200):
            body = json.dumps(data).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                raise ApiError("Request too large.")
            return json.loads(self.rfile.read(n) or b"{}") if n else {}

        def _guard(self, method: str) -> None:
            if self.headers.get("Host", "").split(":")[0] not in ("127.0.0.1", "localhost"):
                raise ApiError("Forbidden", 403)
            if method != "GET" and self.headers.get("X-IGFlow") != "1":
                raise ApiError("Forbidden", 403)

        def _dispatch(self, method: str):
            try:
                self._guard(method)
                url = urlparse(self.path)
                if method == "GET" and url.path == "/":
                    return self._file(STATIC / "index.html", "text/html; charset=utf-8")
                if method == "GET" and (m := re.fullmatch(r"/media/([\w.-]+)/(final\.mp4|final\.jpg)", url.path)):
                    return self._media(m.group(1), m.group(2), "download" in parse_qs(url.query))
                if not url.path.startswith("/api/"):
                    raise ApiError("Not found", 404)
                self._json(self._api(method, url.path[5:], parse_qs(url.query)))
            except _Handled:
                pass
            except ApiError as e:
                self._json({"error": str(e)}, e.status)
            except KeyError:
                self._json({"error": "Post not found."}, 404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                app.say(f"Error: {e}")
                self._json({"error": f"Something went wrong: {e}"}, 500)

        do_GET = lambda self: self._dispatch("GET")
        do_POST = lambda self: self._dispatch("POST")
        do_PUT = lambda self: self._dispatch("PUT")

        # ----- files -----
        def _file(self, path: Path, ctype: str):
            data = path.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _media(self, post_id: str, name: str, download: bool = False):
            store = app.store()
            try:
                post = store.get(post_id)
            finally:
                store.close()
            if not post["final_path"]:
                raise ApiError("No video yet.", 404)
            path = Path(post["final_path"]).with_name(name)
            if not path.exists():
                raise ApiError("File missing.", 404)
            size = path.stat().st_size
            start, end, status = 0, size - 1, 200
            if m := re.fullmatch(r"bytes=(\d*)-(\d*)", self.headers.get("Range", "")):
                s, e = m.groups()
                if s:
                    start, end = int(s), min(int(e) if e else size - 1, size - 1)
                elif e:
                    start = max(size - int(e), 0)
                status = 206
            if start > end:
                raise ApiError("Bad range.", 416)
            self.send_response(status)
            self.send_header("Content-Type", "video/mp4" if name.endswith("mp4") else "image/jpeg")
            self.send_header("Accept-Ranges", "bytes")
            if download:
                self.send_header("Content-Disposition", f'attachment; filename="{post_id}{path.suffix}"')
            self.send_header("Content-Length", str(end - start + 1))
            if status == 206:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.end_headers()
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left:
                    chunk = f.read(min(1024 * 256, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)

        # ----- API -----
        def _api(self, method: str, route: str, query: dict):
            if (method, route) == ("GET", "health"):
                return app.health()
            if (method, route) == ("GET", "settings"):
                return app.settings_view()
            if (method, route) == ("PUT", "settings"):
                app.save_settings(self._body())
                app.say("Settings saved")
                return {"ok": True}
            if (method, route) == ("GET", "log"):
                return {"events": list(app.events)}
            if (method, route) == ("GET", "automation"):
                return {"publish": app.publish_enabled}
            if (method, route) == ("POST", "automation"):
                app.publish_enabled = bool(self._body().get("publish"))
                app.say("Auto-publish " + ("on" if app.publish_enabled else "paused"))
                return {"publish": app.publish_enabled}

            if route == "master":
                path = app.master_path()
                if method == "GET":
                    ref = ""
                    if path.exists():
                        ref = agent.parse_master(path.read_text()).get("REFERENCE IMAGE PROMPT", "")
                    return {"exists": path.exists(), "text": path.read_text() if path.exists() else "", "reference_image_prompt": ref}
                if method == "PUT":
                    text = str(self._body().get("text", ""))
                    try:
                        agent.parse_master(text)
                    except ValueError as e:
                        raise ApiError(f"{e}. Keep the five '## ' headings.")
                    path.write_text(text)
                    app.say("Master prompt saved")
                    return {"ok": True}
            if (method, route) == ("POST", "master/generate"):
                app.require_key()
                body = self._body()
                if app.master_path().exists() and not body.get("force"):
                    raise ApiError("A master prompt already exists.")
                app.master_path().write_text(agent.generate_master(app.cfg, notes=str(body.get("notes", ""))))
                app.say("Master prompt generated")
                return {"ok": True}
            if (method, route) == ("POST", "plan"):
                app.require_key()
                if not app.master_path().exists():
                    raise ApiError("Create your master prompt first.")
                body = self._body()
                fmt = body.get("format", "reel")
                count = max(1, min(int(body.get("count", 3)), 5))
                if fmt not in ("reel", "story"):
                    raise ApiError("Format must be reel or story.")
                store = app.store()
                try:
                    ids = agent.plan_posts(app.cfg, store, app.master_path().read_text(), count, fmt, str(body.get("theme", "")))
                finally:
                    store.close()
                app.say(f"Planned {len(ids)} {fmt}(s)")
                return {"ids": ids}

            if route.startswith("manual/"):
                return self._manual(method, route[7:])

            if (method, route) == ("GET", "posts"):
                store = app.store()
                try:
                    return {"posts": [app.post_view(p) for p in reversed(store.list())]}
                finally:
                    store.close()

            if m := re.fullmatch(r"posts/([\w.-]+)/(\w+)", route):
                post_id, action = m.groups()
                store = app.store()
                try:
                    post = store.get(post_id)
                    return self._post_action(store, post, method, action, query)
                finally:
                    store.close()
            raise ApiError("Not found", 404)

        def _manual(self, method: str, route: str):
            """Copy-and-paste mode: build the request text, then validate the pasted reply."""
            if method != "POST":
                raise ApiError("Not found", 404)
            body = self._body()
            if route == "master/request":
                return {"text": agent.as_chat_message(*agent.master_request(app.cfg, str(body.get("notes", ""))))}
            if route == "master/submit":
                if app.master_path().exists() and not body.get("force"):
                    raise ApiError("A master prompt already exists.")
                try:
                    app.master_path().write_text(agent.master_from_reply(str(body.get("reply", ""))))
                except agent.ReplyError as e:
                    raise ApiError(" ".join(e.problems))
                app.say("Master prompt created from a pasted reply")
                return {"ok": True}
            if route in ("plan/request", "plan/submit"):
                if not app.master_path().exists():
                    raise ApiError("Create your master prompt first.")
                fmt = body.get("format", "reel")
                if fmt not in ("reel", "story"):
                    raise ApiError("Format must be reel or story.")
                count = max(1, min(int(body.get("count", 3)), 5))
                master_md = app.master_path().read_text()
                store = app.store()
                try:
                    if route == "plan/request":
                        return {"text": agent.as_chat_message(*agent.plan_request(app.cfg, store, master_md, count, fmt, str(body.get("theme", ""))))}
                    try:
                        ids = agent.plan_from_reply(app.cfg, store, master_md, str(body.get("reply", "")), count, fmt)
                    except agent.ReplyError as e:
                        self._json({"error": "That reply could not be used: " + " ".join(e.problems), "problems": e.problems,
                                    "fix_request": agent.fix_note(e.problems)}, 400)
                        raise _Handled
                    app.say(f"Planned {len(ids)} {fmt}(s) from a pasted reply")
                    return {"ids": ids}
                finally:
                    store.close()
            raise ApiError("Not found", 404)

        def _post_action(self, store: Store, post: dict, method: str, action: str, query: dict):
            pid = post["id"]
            if method == "POST" and action == "upload":
                slot = (query.get("slot") or [""])[0]
                ext = (query.get("ext") or [""])[0]
                name = app.save_upload(post, slot, ext, int(self.headers.get("Content-Length") or 0), self.rfile)
                return {"file": name}
            body = self._body() if method != "GET" else {}
            try:
                if action == "approve":
                    actions.approve(store, pid, body.get("at") or None)
                    app.say(f"Approved {pid}")
                elif action == "reject":
                    actions.reject(store, pid, body.get("reason"))
                elif action == "redo":
                    actions.redo(app.cfg, store, pid)
                    app.say(f"{pid} is waiting for new clips")
                elif action == "caption":
                    brief = post["brief"]
                    brief["caption"] = str(body.get("caption", "")).strip()
                    brief["hashtags"] = [t.strip().lstrip("#") for t in body.get("hashtags", []) if t.strip()]
                    if not brief["caption"]:
                        raise ApiError("Caption cannot be empty.")
                    store.update_brief(pid, brief)
                elif action == "posted":
                    remaining = actions.mark_posted(app.cfg, store, pid, str(body.get("platform", "")))
                    app.say(f"{pid} marked as posted on {body.get('platform')}" + ("" if remaining else ", all done"))
                    return {"remaining": remaining}
                elif action == "folder":
                    return {"opened": open_folder(app.cfg.path("drop") / pid), "path": str(app.cfg.path("drop") / pid)}
                else:
                    raise ApiError("Not found", 404)
            except ValueError as e:
                raise ApiError(str(e))
            return {"ok": True}

    return Handler


def serve(config_path: str, port: int = 8765, open_browser: bool = True) -> None:
    cp = Path(config_path).resolve()
    if not cp.exists():
        example = Path(__file__).resolve().parent.parent / "config.example.yaml"
        shutil.copy(example, cp)
    cfg = Config.load(cp)
    app = App(cfg, cp)
    threading.Thread(target=app.background, daemon=True).start()
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app))
    url = f"http://127.0.0.1:{port}"
    print(f"Reel Studio is running at {url}\nLeave this window open. Press Ctrl+C to stop.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.stop.set()
        server.server_close()
