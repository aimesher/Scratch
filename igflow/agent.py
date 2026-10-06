"""Prompt agent: writes the master prompt (style bible) and per-post briefs for Google Flow.

The master prompt is generated once, edited by you, then applied verbatim to every shot
prompt by code, so the model cannot drift away from your look.
"""
from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import anthropic
import requests

from .config import Config
from .db import Store

MASTER_SECTIONS = ["STYLE BLOCK", "SUBJECT BIBLE", "AUDIO STYLE", "AVOID", "REFERENCE IMAGE PROMPT"]

FLOW_CRAFT = """\
You write prompts for Google Flow (Veo text-to-video with native audio). Craft rules:
- One shot = one clip. Each clip is 4, 6 or 8 seconds. A 10-12 second post is 2 or 3 chained shots.
- Prompt order that works: subject, action, setting, camera move and lens, lighting and grade, then audio.
- One camera move per shot. One main action per shot. Veo handles a single clear beat far better than a sequence.
- Spoken lines go in quotes with who says them and how. Keep dialogue under ~12 words per clip.
- Name sound effects and ambience explicitly. Veo generates audio from the prompt.
- Always forbid burned-in text, subtitles, watermarks and logos. Add text in post, never in the model.
- For continuity across shots, shot 2+ should use the final frame of the previous clip as its start frame
  (Flow's frames-to-video mode). Say so in `mode` and describe the frame in `continuity_note`.
- Vertical 9:16 framing. Put the subject in the centre 60% of the frame so UI overlays do not cover it.
- Instagram retention: the first 2 seconds must contain the hook visually. No slow fades in.
"""


def _client(client):
    return client or anthropic.Anthropic()


def _text(resp) -> str:
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"Model refused: {getattr(resp, 'stop_details', None)}")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("Model output was cut off (max_tokens). Retry with fewer posts.")
    return "".join(b.text for b in resp.content if b.type == "text")


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model output")
    return json.loads(text[start : end + 1])


def _ask_claude(cfg: Config, client, system: str, user: str) -> str:
    resp = _client(client).messages.create(
        model=cfg["agent"]["model"],
        max_tokens=16000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": cfg["agent"]["effort"]},
    )
    return _text(resp)


GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUS = {429, 500, 502, 503, 504}  # busy or rate-limited: worth waiting and trying again
RETRY_DELAYS = (3, 8)  # seconds before the 2nd and 3rd attempt on each model
_sleep = time.sleep


def _gemini_post(http, cfg: Config, model: str, key: str, system: str, user: str):
    """POST with waits between attempts. Returns the response, or None if the model stayed busy."""
    for attempt in range(len(RETRY_DELAYS) + 1):
        r = (http or requests).post(
            GEMINI_URL.format(model=model),
            headers={"x-goog-api-key": key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"responseMimeType": "application/json", "maxOutputTokens": 16000},
            },
            timeout=180,
        )
        if r.status_code not in RETRY_STATUS:
            return r
        if attempt < len(RETRY_DELAYS):
            wait = RETRY_DELAYS[attempt]
            retry_after = (getattr(r, "headers", None) or {}).get("Retry-After", "")
            if str(retry_after).isdigit():
                wait = min(int(retry_after), 30)
            _sleep(wait)
    return r


def _ask_gemini(cfg: Config, http, system: str, user: str) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set.")
    primary = cfg["agent"]["gemini_model"]
    models = [primary] + [m for m in cfg["agent"].get("gemini_fallback_models", []) if m != primary]
    last_status = None
    for model in models:
        r = _gemini_post(http, cfg, model, key, system, user)
        last_status = r.status_code
        if r.status_code in RETRY_STATUS or r.status_code == 404:
            continue  # this model is busy or unknown: try the next one
        if r.status_code in (400, 403) and "API key" in r.text:
            raise RuntimeError("Gemini rejected the API key. Check it in Settings.")
        if r.status_code >= 400:
            raise RuntimeError(f"Gemini error {r.status_code}: {r.text[:300]}")
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            raise RuntimeError(f"Gemini returned no answer: {data.get('promptFeedback')}")
        text = "".join(p.get("text", "") for p in candidates[0].get("content", {}).get("parts", []))
        if not text:
            raise RuntimeError(f"Gemini returned an empty answer (finish reason: {candidates[0].get('finishReason')}).")
        return text
    if last_status == 429:
        raise RuntimeError("Gemini's free-tier limit was reached on every model. Wait a few minutes and try again, or try tomorrow.")
    if last_status == 404:
        raise RuntimeError(f"Gemini does not know the model '{primary}'. Change gemini_model in config.yaml.")
    raise RuntimeError("Gemini is overloaded right now: every model I tried was busy. Wait a few minutes and try again.")


def _ask(cfg: Config, client, system: str, user: str) -> str:
    """`client` is an injected Anthropic client or HTTP session (used by tests); None uses the real one."""
    if cfg["agent"]["provider"] == "manual":
        raise RuntimeError("Copy-and-paste mode is on, so the dashboard does not call an AI by itself.")
    if cfg["agent"]["provider"] == "gemini":
        return _ask_gemini(cfg, client, system, user)
    return _ask_claude(cfg, client, system, user)


def _brand_block(cfg: Config) -> str:
    b = cfg["brand"]
    return "\n".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in b.items() if v)


# ---------- master prompt ----------

class ReplyError(ValueError):
    """An answer could not be used. `problems` lists why, in plain words."""

    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


MASTER_KEYS = ("style_block", "subject_bible", "audio_style", "avoid", "reference_image_prompt")


def as_chat_message(system: str, user: str) -> str:
    """One block of text to paste into any chat assistant (Gemini app, Claude app, ChatGPT)."""
    return (
        "Act as the role below and complete the task. Reply with ONLY the JSON object requested. "
        "No explanation before or after it.\n\n"
        f"=== ROLE ===\n{system}\n\n=== TASK ===\n{user}\n"
    )


def master_request(cfg: Config, notes: str = "") -> tuple[str, str]:
    system = "You are a creative director who builds reusable prompt systems for AI video.\n\n" + FLOW_CRAFT
    user = f"""Build the master prompt for this Instagram account. It is written once and attached to every
shot prompt, so it must be reusable across any topic and short enough to paste (STYLE BLOCK <= 90 words).

ACCOUNT
{_brand_block(cfg)}

{('EXTRA DIRECTION: ' + notes) if notes else ''}

Return one JSON object, no prose, with exactly these string keys:
- "style_block": visual language appended to every shot: look, lens, lighting, grade, motion feel. Concrete, no vague adjectives.
- "subject_bible": recurring people, objects, locations with fixed physical descriptions, so they render the same each time. Say "none" if the account has no recurring subjects.
- "audio_style": the sonic identity: ambience, music feel, voice (age, tone, pace) if any.
- "avoid": comma-separated list of things to exclude in every prompt.
- "reference_image_prompt": one image prompt to generate a reference frame that locks the look (used as Flow ingredient or start frame).
"""
    return system, user


def master_from_reply(reply: str) -> str:
    try:
        data = _extract_json(reply)
    except ValueError:
        raise ReplyError(["The answer did not contain a JSON object. Copy the whole reply, including the curly brackets."])
    if not isinstance(data, dict):
        raise ReplyError(["The answer was not a JSON object."])
    missing = [k for k in MASTER_KEYS if not str(data.get(k) or "").strip()]
    if missing:
        raise ReplyError([f"The answer is missing: {', '.join(missing)}."])
    return render_master({k: str(data[k]) for k in MASTER_KEYS})


def generate_master(cfg: Config, client=None, notes: str = "") -> str:
    system, user = master_request(cfg, notes)
    return master_from_reply(_ask(cfg, client, system, user))


def render_master(data: dict) -> str:
    return (
        "# MASTER PROMPT\n\n"
        "Edit freely. Every shot prompt is built from these sections verbatim.\n\n"
        f"## STYLE BLOCK\n{data['style_block'].strip()}\n\n"
        f"## SUBJECT BIBLE\n{data['subject_bible'].strip()}\n\n"
        f"## AUDIO STYLE\n{data['audio_style'].strip()}\n\n"
        f"## AVOID\n{data['avoid'].strip()}\n\n"
        f"## REFERENCE IMAGE PROMPT\n{data['reference_image_prompt'].strip()}\n"
    )


def parse_master(md: str) -> dict[str, str]:
    sections: dict[str, str] = {}
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", md, flags=re.S | re.M):
        sections[m.group(1).strip().upper()] = m.group(2).strip()
    missing = [s for s in MASTER_SECTIONS if s not in sections]
    if missing:
        raise ValueError(f"master prompt is missing sections: {missing}")
    return sections


# ---------- post briefs ----------

def validate_posts(data: dict, cfg: Config, expected_format: str) -> list[str]:
    errors: list[str] = []
    v = cfg["video"]
    allowed = set(v["allowed_clip_seconds"])
    posts = data.get("posts")
    if not isinstance(posts, list) or not posts:
        return ["'posts' must be a non-empty list"]
    for i, p in enumerate(posts, 1):
        tag = f"post {i}"
        shots = p.get("shots") or []
        if not 1 <= len(shots) <= 3:
            errors.append(f"{tag}: needs 1-3 shots, got {len(shots)}")
        secs = [s.get("seconds") for s in shots]
        if any(s not in allowed for s in secs):
            errors.append(f"{tag}: each shot must be one of {sorted(allowed)} seconds, got {secs}")
        elif not v["min_seconds"] <= sum(secs) <= v["max_seconds"]:
            errors.append(f"{tag}: shots total {sum(secs)}s, must be {v['min_seconds']}-{v['max_seconds']}s")
        for j, s in enumerate(shots, 1):
            if not s.get("video_prompt") or not s.get("audio"):
                errors.append(f"{tag} shot {j}: video_prompt and audio are required")
            if j > 1 and s.get("mode") != "frames_to_video":
                errors.append(f"{tag} shot {j}: shots after the first must use mode frames_to_video")
        if not p.get("caption") or not p.get("hook") or not p.get("title"):
            errors.append(f"{tag}: title, hook and caption are required")
        tags = p.get("hashtags") or []
        if not 3 <= len(tags) <= 12:
            errors.append(f"{tag}: give 3-12 hashtags, got {len(tags)}")
        if p.get("format", expected_format) != expected_format:
            errors.append(f"{tag}: format must be {expected_format}")
    return errors


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:32] or "post"


def compose_shot_prompt(shot: dict, master: dict[str, str]) -> str:
    """The text you paste into Flow. Master sections are applied verbatim."""
    return (
        f"{shot['video_prompt'].strip()}\n\n"
        f"Look: {master['STYLE BLOCK']}\n"
        f"Subjects: {master['SUBJECT BIBLE']}\n"
        f"Audio: {shot['audio'].strip()} {master['AUDIO STYLE']}\n"
        f"Vertical 9:16. No text, subtitles, watermarks or logos. Avoid: {master['AVOID']}"
    )


def plan_request(cfg: Config, store: Store, master_md: str, count: int, fmt: str = "reel", theme: str = "") -> tuple[str, str]:
    system = "You are a short-form video producer for Instagram.\n\n" + FLOW_CRAFT + "\n\nMASTER PROMPT\n" + master_md
    v = cfg["video"]
    history = [f"- {b.get('title')}: {b.get('hook')}" for b in store.recent_briefs(20)]

    user = f"""Plan {count} Instagram {fmt}s. Each is {v['min_seconds']}-{v['max_seconds']} seconds total.

ACCOUNT
{_brand_block(cfg)}

THEME FOR THIS BATCH: {theme or 'your choice, vary the angles'}

RECENT POSTS (do not repeat these ideas or hooks):
{chr(10).join(history) or '(none yet)'}

Allowed shot lengths in seconds: {v['allowed_clip_seconds']}.
`video_prompt` describes only what is in this shot. Do NOT repeat the master prompt sections; they are added automatically.

Return one JSON object, no prose:
{{"posts": [{{
  "title": "internal name",
  "format": "{fmt}",
  "hook": "what the viewer sees and hears in the first 2 seconds",
  "concept": "one sentence",
  "shots": [{{
    "seconds": 6,
    "mode": "text_to_video" or "frames_to_video",
    "start_frame_image_prompt": "image prompt for the start frame, or null",
    "video_prompt": "...",
    "audio": "dialogue in quotes, sound effects, ambience for this clip"
  }}],
  "continuity_note": "what must match between the end of one shot and the start of the next",
  "on_screen_text": ["lines to add in Instagram's editor, with timing"],
  "caption": "ready to post, first line is a hook, matches the account voice",
  "youtube_title": "title for YouTube Shorts, under 70 characters, no hashtags",
  "hashtags": ["without the # symbol"],
  "music_note": "optional trending-audio or music direction, or empty"
}}]}}"""
    return system, user


def fix_note(problems: list[str]) -> str:
    """Appended to a request (or sent as a follow-up in the same chat) after a rejected answer."""
    return "Your previous attempt was rejected:\n- " + "\n- ".join(problems) + "\nFix these and return the complete JSON again, nothing else."


def plan_from_reply(
    cfg: Config, store: Store, master_md: str, reply: str, count: int, fmt: str = "reel", now: datetime | None = None
) -> list[str]:
    """Validate an answer and create the posts. Raises ReplyError with plain-language problems."""
    parse_master(master_md)  # fail early on a broken master prompt
    try:
        data = _extract_json(reply)
    except ValueError as e:
        raise ReplyError([f"The answer was not valid JSON ({e}). Copy the whole reply, from the first {{ to the last }}."])
    problems = validate_posts(data, cfg, fmt) if isinstance(data, dict) else ["The answer was not a JSON object."]
    if problems:
        raise ReplyError(problems)
    posts = data["posts"][:count]
    for p in posts:
        p["format"] = fmt
    return create_posts(cfg, store, master_md, posts, now)


def create_posts(cfg: Config, store: Store, master_md: str, posts: list[dict], now: datetime | None = None) -> list[str]:
    """Validate post drafts (each with its own "format"), attach the master prompt and save them as briefs."""
    master = parse_master(master_md)
    problems = []
    for i, p in enumerate(posts, 1):
        fmt = p.get("format", "reel")
        if fmt not in ("reel", "story"):
            problems.append(f"post {i}: format must be reel or story")
            continue
        problems += [e.replace("post 1", f"post {i}", 1) for e in validate_posts({"posts": [p]}, cfg, fmt)]
    if not posts:
        problems.append("give at least one post")
    if problems:
        raise ReplyError(problems)

    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    ids = []
    for n, post in enumerate(posts, 1):
        for s in post["shots"]:
            s["flow_prompt"] = compose_shot_prompt(s, master)
        post_id = f"{stamp}-{n}-{_slug(post['title'])}"
        while True:  # two batches in the same minute must not collide
            try:
                store.get(post_id)
            except KeyError:
                break
            post_id += "x"
        store.create(post_id, post["format"], post)
        (cfg.path("drop") / post_id).mkdir(parents=True, exist_ok=True)
        brief_dir = cfg.path("data") / "briefs"
        brief_dir.mkdir(exist_ok=True)
        (brief_dir / f"{post_id}.md").write_text(render_brief(post_id, post, master))
        ids.append(post_id)
    return ids


def plan_posts(
    cfg: Config,
    store: Store,
    master_md: str,
    count: int,
    fmt: str = "reel",
    theme: str = "",
    client=None,
    now: datetime | None = None,
) -> list[str]:
    system, user = plan_request(cfg, store, master_md, count, fmt, theme)
    try:
        return plan_from_reply(cfg, store, master_md, _ask(cfg, client, system, user), count, fmt, now)
    except ReplyError as first:
        # One corrective retry as a fresh single-turn request.
        retry = user + "\n\n" + fix_note(first.problems)
        try:
            return plan_from_reply(cfg, store, master_md, _ask(cfg, client, system, retry), count, fmt, now)
        except ReplyError as second:
            raise ValueError("brief failed validation twice:\n- " + "\n- ".join(second.problems))


def render_brief(post_id: str, post: dict, master: dict[str, str]) -> str:
    lines = [
        f"# {post['title']}  ({post['format']})",
        f"`{post_id}`",
        "",
        f"**Hook:** {post['hook']}",
        f"**Concept:** {post['concept']}",
        "",
        "## Reference image (generate once, reuse as ingredient or start frame)",
        "```",
        master["REFERENCE IMAGE PROMPT"],
        "```",
    ]
    for i, s in enumerate(post["shots"], 1):
        lines += ["", f"## Shot {i}: {s['seconds']}s, {s['mode']}"]
        if s.get("start_frame_image_prompt"):
            lines += ["Start frame image prompt:", "```", s["start_frame_image_prompt"], "```"]
        if s["mode"] == "frames_to_video" and i > 1:
            lines.append("Use the last frame of the previous clip as the start frame.")
        lines += ["Flow prompt:", "```", s["flow_prompt"], "```"]
    if post.get("continuity_note"):
        lines += ["", f"**Continuity:** {post['continuity_note']}"]
    if post.get("on_screen_text"):
        lines += ["", "## On-screen text (add in Instagram's editor)"] + [f"- {t}" for t in post["on_screen_text"]]
    lines += [
        "",
        "## Caption",
        post["caption"],
        "",
        f"**YouTube Shorts title:** {post.get('youtube_title') or post['title']}",
        "",
        " ".join("#" + t.lstrip("#") for t in post["hashtags"]),
    ]
    if post.get("music_note"):
        lines += ["", f"**Music:** {post['music_note']}"]
    lines += [
        "",
        "## Drop your files here",
        f"`drop/{post_id}/` named `1.mp4`, `2.mp4`" + (", `3.mp4`" if len(post["shots"]) > 2 else "")
        + " in shot order. Optional: `music.mp3`.",
        "",
    ]
    return "\n".join(lines)
