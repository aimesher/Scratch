"""Prompt agent: writes the master prompt (style bible) and per-post briefs for Google Flow.

The master prompt is generated once, edited by you, then applied verbatim to every shot
prompt by code, so the model cannot drift away from your look.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import anthropic

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


def _ask(cfg: Config, client, system: str, user: str) -> str:
    resp = client.messages.create(
        model=cfg["agent"]["model"],
        max_tokens=16000,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": user}],
        output_config={"effort": cfg["agent"]["effort"]},
    )
    return _text(resp)


def _brand_block(cfg: Config) -> str:
    b = cfg["brand"]
    return "\n".join(f"{k.replace('_', ' ').title()}: {v}" for k, v in b.items() if v)


# ---------- master prompt ----------

def generate_master(cfg: Config, client=None, notes: str = "") -> str:
    client = _client(client)
    system = (
        "You are a creative director who builds reusable prompt systems for AI video.\n\n" + FLOW_CRAFT
    )
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
    data = _extract_json(_ask(cfg, client, system, user))
    missing = [k for k in ("style_block", "subject_bible", "audio_style", "avoid", "reference_image_prompt") if not data.get(k)]
    if missing:
        raise ValueError(f"master prompt missing {missing}")
    return render_master(data)


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
    client = _client(client)
    master = parse_master(master_md)
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
  "hashtags": ["without the # symbol"],
  "music_note": "optional trending-audio or music direction, or empty"
}}]}}"""

    raw = _ask(cfg, client, system, user)
    data, errors = None, []
    try:
        data = _extract_json(raw)
        errors = validate_posts(data, cfg, fmt)
    except (ValueError, json.JSONDecodeError) as e:
        errors = [f"output was not valid JSON: {e}"]
    if errors:
        # One corrective retry as a fresh single-turn request.
        retry = user + "\n\nYour previous attempt was rejected:\n- " + "\n- ".join(errors) + "\nFix these and return the full JSON again."
        raw = _ask(cfg, client, system, retry)
        data = _extract_json(raw)
        errors = validate_posts(data, cfg, fmt)
        if errors:
            raise ValueError("brief failed validation twice:\n- " + "\n- ".join(errors))

    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M")
    ids = []
    for n, post in enumerate(data["posts"][:count], 1):
        post["format"] = fmt
        for s in post["shots"]:
            s["flow_prompt"] = compose_shot_prompt(s, master)
        post_id = f"{stamp}-{n}-{_slug(post['title'])}"
        store.create(post_id, fmt, post)
        (cfg.path("drop") / post_id).mkdir(parents=True, exist_ok=True)
        brief_dir = cfg.path("data") / "briefs"
        brief_dir.mkdir(exist_ok=True)
        (brief_dir / f"{post_id}.md").write_text(render_brief(post_id, post, master))
        ids.append(post_id)
    return ids


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
