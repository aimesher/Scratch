import json
import os
import subprocess
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from igflow import agent
from igflow.assemble import probe
from igflow.config import Config
from igflow.db import Store
from igflow.publish import InstagramClient, InstagramError, publish_due
from igflow.watcher import order_clips, process_drops, scan

MASTER = {
    "style_block": "Photoreal, soft window light, slow dolly.",
    "subject_bible": "A timber house with a glass corner.",
    "audio_style": "Quiet room tone, no music.",
    "avoid": "text, logos",
    "reference_image_prompt": "Timber house at dusk, photoreal.",
}


def post(seconds=(6, 6), title="Glass corner reveal"):
    shots = []
    for i, s in enumerate(seconds, 1):
        shots.append({
            "seconds": s,
            "mode": "text_to_video" if i == 1 else "frames_to_video",
            "start_frame_image_prompt": None,
            "video_prompt": f"Shot {i} of the house.",
            "audio": 'A voice says "Look at this corner."',
        })
    return {
        "title": title, "format": "reel", "hook": "Corner dissolves", "concept": "c", "shots": shots,
        "continuity_note": "same light", "on_screen_text": ["0-2s: Glass corner"],
        "caption": "Watch the corner.", "hashtags": ["archviz", "bim", "render"], "music_note": "",
    }


class FakeClient:
    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.calls = []
        self.messages = self

    def create(self, **kw):
        self.calls.append(kw)
        text = self.outputs.pop(0)
        return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


@pytest.fixture
def cfg(tmp_path):
    return Config({"brand": {"niche": "archviz"}, "watcher": {"stable_seconds": 0}}, tmp_path)


def make_clip(path: Path, seconds: int, size="1280x720", audio=True):
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size={size}:rate=24"]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"] + (["-c:a", "aac", "-shortest"] if audio else []) + [str(path)]
    subprocess.run(cmd, check=True)


# ---------- agent ----------

def test_master_roundtrip(cfg):
    md = agent.generate_master(cfg, FakeClient(json.dumps(MASTER)))
    sections = agent.parse_master(md)
    assert sections["STYLE BLOCK"] == MASTER["style_block"]
    assert set(sections) == set(agent.MASTER_SECTIONS)


def test_plan_retries_on_bad_duration_then_creates_post(cfg):
    store = Store(cfg.path("data") / "q.db")
    md = agent.render_master(MASTER)
    bad = json.dumps({"posts": [post(seconds=(8, 8))]})  # 16s, over the 12s cap
    good = json.dumps({"posts": [post()]})
    client = FakeClient(bad, good)
    ids = agent.plan_posts(cfg, store, md, 1, client=client)
    assert len(client.calls) == 2 and "rejected" in client.calls[1]["messages"][0]["content"]
    row = store.get(ids[0])
    assert row["status"] == "briefed"
    assert "Photoreal, soft window light" in row["brief"]["shots"][0]["flow_prompt"]
    assert (cfg.path("drop") / ids[0]).is_dir()
    assert (cfg.path("data") / "briefs" / f"{ids[0]}.md").read_text().count("```") >= 6


def test_plan_fails_after_two_bad_attempts(cfg):
    store = Store(cfg.path("data") / "q.db")
    bad = json.dumps({"posts": [post(seconds=(8, 8))]})
    with pytest.raises(ValueError, match="twice"):
        agent.plan_posts(cfg, store, agent.render_master(MASTER), 1, client=FakeClient(bad, bad))


def test_validation_requires_frames_mode_after_first_shot(cfg):
    p = post()
    p["shots"][1]["mode"] = "text_to_video"
    assert any("frames_to_video" in e for e in agent.validate_posts({"posts": [p]}, cfg, "reel"))


# ---------- watcher ----------

def test_scan_waits_for_all_clips_and_stability(tmp_path):
    d = tmp_path / "drop"
    d.mkdir()
    (d / "1.mp4").write_bytes(b"x")
    assert scan(d, 2, 0) is None  # only one of two clips
    (d / "2.mp4").write_bytes(b"x")
    assert scan(d, 2, 0) is not None
    assert scan(d, 2, 60) is None  # modified too recently
    assert scan(d, 2, 60, now=time.time() + 120) is not None


def test_order_numbers_before_mtime(tmp_path):
    a, b = tmp_path / "10_b.mp4", tmp_path / "2_a.mp4"
    a.write_bytes(b"x"); b.write_bytes(b"x")
    assert order_clips([a, b]) == [b, a]


def test_ignores_partial_downloads(tmp_path):
    (tmp_path / "1.mp4.crdownload").write_bytes(b"x")
    assert scan(tmp_path, 1, 0) is None


# ---------- assembly (real ffmpeg) ----------

def test_end_to_end_assembly_with_mixed_inputs(cfg):
    store = Store(cfg.path("data") / "q.db")
    store.create("p1", "reel", post(seconds=(6, 6)))
    drop = cfg.path("drop") / "p1"
    drop.mkdir()
    make_clip(drop / "1.mp4", 6, "1280x720", audio=True)
    make_clip(drop / "2.mp4", 6, "720x1280", audio=False)  # no audio, different ratio
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=frequency=220:duration=20", str(drop / "music.mp3")], check=True)
    assert process_drops(cfg, store, lambda m: None) == 1
    row = store.get("p1")
    assert row["status"] == "review", row["error"]
    info = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", row["final_path"]],
        capture_output=True, text=True, check=True).stdout.strip()
    assert info == "1080,1920"
    assert 11.5 <= probe(Path(row["final_path"]))["duration"] <= 12.1
    assert probe(Path(row["final_path"]))["has_audio"]
    assert Path(row["final_path"]).with_suffix(".jpg").exists()


def test_corrupt_clip_marks_failed(cfg):
    store = Store(cfg.path("data") / "q.db")
    store.create("p2", "reel", post(seconds=(6, 6)))
    drop = cfg.path("drop") / "p2"
    drop.mkdir()
    (drop / "1.mp4").write_bytes(b"not a video")
    (drop / "2.mp4").write_bytes(b"not a video")
    process_drops(cfg, store, lambda m: None)
    assert store.get("p2")["status"] == "failed"


# ---------- publish ----------

class FakeHTTP:
    def __init__(self, statuses=("IN_PROGRESS", "FINISHED")):
        self.calls, self.statuses = [], list(statuses)

    def _resp(self, body, code=200):
        return SimpleNamespace(status_code=code, json=lambda: body, text=json.dumps(body))

    def post(self, url, **kw):
        self.calls.append(("POST", url, kw))
        if url.endswith("/media"):
            return self._resp({"id": "C1"})
        if "rupload" in url:
            return self._resp({"success": True})
        return self._resp({"id": "M1"})

    def get(self, url, **kw):
        self.calls.append(("GET", url, kw))
        return self._resp({"status_code": self.statuses.pop(0)})


def test_publish_sequence_and_story_has_no_caption(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"12345")
    http = FakeHTTP()
    ig = InstagramClient("U1", "T", session=http, sleep=lambda s: None)
    assert ig.publish(video, "story", "cap") == "M1"
    create = http.calls[0]
    assert create[2]["data"]["media_type"] == "STORIES" and "caption" not in create[2]["data"]
    upload = http.calls[1]
    assert upload[2]["headers"]["file_size"] == "5" and upload[2]["headers"]["Authorization"] == "OAuth T"
    assert http.calls[-1][1].endswith("/U1/media_publish")


def test_publish_surfaces_container_error(tmp_path):
    video = tmp_path / "v.mp4"
    video.write_bytes(b"1")
    ig = InstagramClient("U1", "T", session=FakeHTTP(["ERROR"]), sleep=lambda s: None)
    with pytest.raises(InstagramError, match="ERROR"):
        ig.publish(video, "reel", "c")


def test_publish_due_honours_schedule_and_daily_limit(cfg, tmp_path):
    store = Store(cfg.path("data") / "q.db")
    video = tmp_path / "v.mp4"
    video.write_bytes(b"1")
    for pid, when in (("a", "2000-01-01T00:00:00+00:00"), ("b", "2999-01-01T00:00:00+00:00")):
        store.create(pid, "reel", post())
        store.update(pid, status="approved", scheduled_at=when, final_path=str(video))
    ig = InstagramClient("U1", "T", session=FakeHTTP(["FINISHED"]), sleep=lambda s: None)
    assert publish_due(cfg, store, ig, log=lambda m: None) == 1
    assert store.get("a")["status"] == "published" and store.get("a")["ig_media_id"] == "M1"
    assert store.get("b")["status"] == "approved"


# ---------- Gemini provider ----------

class FakeGemini:
    def __init__(self, text=None, status=200, body=None):
        self.calls, self.status = [], status
        self.body = body if body is not None else {"candidates": [{"content": {"parts": [{"text": text}]}, "finishReason": "STOP"}]}

    def post(self, url, **kw):
        self.calls.append((url, kw))
        return SimpleNamespace(status_code=self.status, json=lambda: self.body, text=json.dumps(self.body))


@pytest.fixture
def gcfg(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "g-key")
    return Config({"agent": {"provider": "gemini"}, "brand": {"niche": "archviz"}}, tmp_path)


def test_gemini_master_and_plan_use_json_mode_and_key_header(gcfg):
    http = FakeGemini(json.dumps(MASTER))
    md = agent.generate_master(gcfg, http)
    assert agent.parse_master(md)["STYLE BLOCK"] == MASTER["style_block"]
    url, kw = http.calls[0]
    assert "gemini-flash-latest:generateContent" in url and kw["headers"] == {"x-goog-api-key": "g-key"}
    assert kw["json"]["generationConfig"]["responseMimeType"] == "application/json"

    store = Store(gcfg.path("data") / "q.db")
    ids = agent.plan_posts(gcfg, store, md, 1, client=FakeGemini(json.dumps({"posts": [post()]})))
    assert store.get(ids[0])["status"] == "briefed"


@pytest.mark.parametrize("status,text,expect", [
    (429, "quota", "rate-limited"), (400, "API key not valid", "rejected the API key"), (404, "nope", "does not know the model")])
def test_gemini_errors_are_readable(gcfg, status, text, expect):
    with pytest.raises(RuntimeError, match=expect):
        agent.generate_master(gcfg, FakeGemini(status=status, body={"error": text}))


def test_gemini_empty_answer_is_reported(gcfg):
    with pytest.raises(RuntimeError, match="no answer"):
        agent.generate_master(gcfg, FakeGemini(body={"promptFeedback": {"blockReason": "SAFETY"}}))
