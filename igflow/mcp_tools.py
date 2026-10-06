"""Tools Claude uses to run Reel Studio in conversation.

Claude writes the ideas, prompts and captions itself, so no AI key is needed on the server.
Video clips come from Google Flow (you), get assembled here, and nothing is scheduled until
you have watched the result and said so.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field

from . import actions, agent, instagram_auth
from .publish import build_caption

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False, openWorldHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)

STATUS_MEANING = {
    "briefed": "waiting for the person to generate the clips in Google Flow and upload them in the dashboard",
    "assembling": "clips are being joined into the final video",
    "review": "video is ready; the person should watch it in the dashboard before anything is scheduled",
    "approved": "scheduled",
    "published": "posted everywhere it was meant to go",
    "rejected": "rejected by the person",
    "failed": "something went wrong; see error",
}


class Shot(BaseModel):
    seconds: int = Field(description="Clip length. Must be one of the allowed clip lengths from reelstudio_get_account (usually 4, 6 or 8).")
    mode: Literal["text_to_video", "frames_to_video"] = Field(
        description="text_to_video for the first shot; frames_to_video for later shots, which start from the previous clip's last frame.")
    video_prompt: str = Field(description="What happens in this shot only: subject, action, setting, one camera move, lighting. Do not repeat the master prompt; it is added automatically.")
    audio: str = Field(description="Dialogue in quotes with who says it, sound effects and ambience for this clip.")
    start_frame_image_prompt: str | None = Field(default=None, description="Optional image prompt for the first frame.")


class PostDraft(BaseModel):
    format: Literal["reel", "story"] = Field(description="reel (also goes to YouTube Shorts if enabled) or story (Instagram only).")
    title: str = Field(description="Short internal name, e.g. 'Morning stretch in 3 moves'.")
    hook: str = Field(description="What the viewer sees and hears in the first 2 seconds.")
    concept: str = Field(description="One sentence.")
    shots: list[Shot] = Field(description="1 to 3 shots whose seconds add up to the allowed total length.", min_length=1, max_length=3)
    continuity_note: str = Field(default="", description="What must match between the end of one shot and the start of the next.")
    on_screen_text: list[str] = Field(default_factory=list, description="Text to add in Instagram's editor, with timing, e.g. '0-2s: 3 moves'.")
    caption: str = Field(description="Ready-to-post caption in the account's voice; first line is a hook.")
    hashtags: list[str] = Field(description="3 to 12 hashtags without the # sign.")
    youtube_title: str = Field(default="", description="YouTube Shorts title under 70 characters, no hashtags.")
    music_note: str = Field(default="", description="Optional music or trending-audio direction.")


def register(mcp: FastMCP, app) -> None:
    """`app` is the dashboard's App: it holds the live settings and the database location."""

    def store():
        return app.store()

    def link() -> str:
        return f"{app.public_url}/#posts" if app.public_url else "the Reel Studio dashboard"

    def tz_name() -> str:
        return app.cfg["timezone"]

    def summary(p: dict) -> dict[str, Any]:
        b = p["brief"]
        when = p["scheduled_at"]
        local = datetime.fromisoformat(when).astimezone(actions.user_tz(tz_name())).strftime("%a %d %b %Y, %H:%M") if when else None
        return {
            "id": p["id"], "title": b.get("title"), "format": p["format"], "status": p["status"],
            "meaning": STATUS_MEANING.get(p["status"], ""), "scheduled_for": local,
            "posted": b.get("posted", {}), "error": p["error"],
        }

    def get(post_id: str) -> dict[str, Any]:
        s = store()
        try:
            return s.get(post_id)
        except KeyError:
            raise ToolError(f"No post with id '{post_id}'. Call reelstudio_list_posts to see the ids.")
        finally:
            s.close()

    @mcp.tool(name="reelstudio_get_account", annotations=READ)
    def get_account() -> dict[str, Any]:
        """Start here. Returns the account profile, timezone and current local time, the content rules,
        the master prompt (the style guide every video follows), recent posts and recent Instagram captions
        to match the tone, and how publishing works for this account."""
        cfg = app.cfg
        v = cfg["video"]
        mp = app.master_path()
        s = store()
        try:
            recent = [summary(p) | {"hook": p["brief"].get("hook"), "caption": p["brief"].get("caption")} for p in reversed(s.list()[-10:])]
        finally:
            s.close()
        try:
            ig = instagram_auth.recent_captions(12)
        except Exception as e:  # not fatal: tone matching just has less to go on
            ig = [{"note": f"Could not read Instagram captions: {e}"}]
        auto = actions.auto_platforms(cfg)
        return {
            "profile": cfg["brand"],
            "timezone": tz_name() or "server local time",
            "local_time_now": datetime.now(actions.user_tz(tz_name())).strftime("%A %d %B %Y, %H:%M"),
            "rules": {
                "total_seconds": [v["min_seconds"], v["max_seconds"]],
                "allowed_clip_seconds": v["allowed_clip_seconds"],
                "formats": ["reel", "story"],
                "platforms": cfg["publish"]["platforms"],
                "max_posts_per_day": cfg["instagram"]["max_per_day"],
            },
            "publishing": (
                "Instagram posts automatically at the scheduled time. YouTube Shorts are posted by the person from the dashboard."
                if auto else "The person posts everything from the dashboard's Post it step; scheduling sets a reminder."
            ),
            "master_prompt": mp.read_text() if mp.exists() else None,
            "recent_posts": recent,
            "instagram_recent_captions": ig,
            "workflow": [
                "1. If master_prompt is null, propose one and save it with reelstudio_save_master_prompt after the person agrees.",
                "2. Draft posts and save them with reelstudio_create_posts. Show the person the Flow prompts it returns.",
                f"3. The person generates each shot in Google Flow and uploads the clips in the dashboard ({link()}). The video is assembled automatically.",
                "4. When a post's status is review, ask the person to watch it in the dashboard.",
                "5. Only after they confirm, call reelstudio_schedule_post.",
            ],
        }

    @mcp.tool(name="reelstudio_save_master_prompt", annotations=WRITE)
    def save_master_prompt(
        style_block: str = Field(description="Visual language added to every shot: look, lens, lighting, grade, motion feel. Under 90 words."),
        subject_bible: str = Field(description="Recurring people, objects and places with fixed descriptions, or 'none'."),
        audio_style: str = Field(description="Sonic identity: ambience, music feel, voice."),
        avoid: str = Field(description="Comma-separated things to exclude from every video."),
        reference_image_prompt: str = Field(description="One image prompt for a reference frame that locks the look."),
        replace_existing: bool = Field(default=False, description="Set true only if the person asked to replace their current master prompt."),
    ) -> dict[str, Any]:
        """Save the account's master prompt (style guide). Every shot prompt is built from it verbatim."""
        path = app.master_path()
        if path.exists() and not replace_existing:
            raise ToolError("A master prompt already exists. Show it to the person; set replace_existing=true only if they want it replaced.")
        md = agent.render_master({"style_block": style_block, "subject_bible": subject_bible, "audio_style": audio_style,
                                  "avoid": avoid, "reference_image_prompt": reference_image_prompt})
        path.write_text(md)
        app.say("Master prompt saved by Claude")
        return {"saved": True, "master_prompt": md}

    @mcp.tool(name="reelstudio_create_posts", annotations=WRITE)
    def create_posts(posts: list[PostDraft]) -> dict[str, Any]:
        """Save one or more drafted posts. Returns, per post, the exact prompts to paste into Google Flow.
        The shots must follow the rules from reelstudio_get_account. Nothing is published by this."""
        mp = app.master_path()
        if not mp.exists():
            raise ToolError("There is no master prompt yet. Propose one and save it with reelstudio_save_master_prompt first.")
        s = store()
        try:
            ids = agent.create_posts(app.cfg, s, mp.read_text(), [p.model_dump() for p in posts])
            created = [s.get(i) for i in ids]
        except agent.ReplyError as e:
            raise ToolError("Not saved. Fix these and call again: " + "; ".join(e.problems))
        finally:
            s.close()
        ref = agent.parse_master(mp.read_text())["REFERENCE IMAGE PROMPT"]
        app.say(f"Claude planned {len(ids)} post(s)")
        return {
            "created": [{
                "id": p["id"], "title": p["brief"]["title"], "format": p["format"],
                "flow_steps": [{"shot": n, "seconds": sh["seconds"], "mode": sh["mode"],
                                "start_frame_image_prompt": sh.get("start_frame_image_prompt"), "flow_prompt": sh["flow_prompt"]}
                               for n, sh in enumerate(p["brief"]["shots"], 1)],
            } for p in created],
            "reference_image_prompt": ref,
            "next": f"The person generates the shots in Google Flow, then uploads each clip into its slot at {link()}.",
        }

    @mcp.tool(name="reelstudio_list_posts", annotations=READ)
    def list_posts(
        status: Literal["briefed", "assembling", "review", "approved", "published", "rejected", "failed"] | None = Field(
            default=None, description="Only posts with this status. Omit for all."),
        limit: int = Field(default=20, ge=1, le=100),
    ) -> dict[str, Any]:
        """List posts, newest first, with what each status means for the next step."""
        s = store()
        try:
            rows = list(reversed(s.list(status)))[:limit]
        finally:
            s.close()
        return {"posts": [summary(p) for p in rows], "count": len(rows)}

    @mcp.tool(name="reelstudio_get_post", annotations=READ)
    def get_post(post_id: str) -> dict[str, Any]:
        """Everything about one post: the brief, the Flow prompts, caption, status and which clips are uploaded."""
        p = get(post_id)
        view = app.post_view(p)
        return summary(p) | {"brief": p["brief"], "clips_uploaded": view["files"], "video_ready": view["has_video"],
                             "platforms": view["platforms"], "caption_as_posted": build_caption(p["brief"])}

    @mcp.tool(name="reelstudio_update_post_text", annotations=WRITE)
    def update_post_text(
        post_id: str,
        caption: str | None = Field(default=None, description="New caption, or omit to keep it."),
        hashtags: list[str] | None = Field(default=None, description="New hashtags without #, or omit to keep them."),
        youtube_title: str | None = Field(default=None, description="New YouTube title, or omit to keep it."),
    ) -> dict[str, Any]:
        """Change the caption, hashtags or YouTube title of a post that has not been posted yet."""
        p = get(post_id)
        if p["status"] == "published":
            raise ToolError("This post is already published; its text can no longer be changed here.")
        b = p["brief"]
        if caption is not None:
            if not caption.strip():
                raise ToolError("The caption cannot be empty.")
            b["caption"] = caption.strip()
        if hashtags is not None:
            b["hashtags"] = [t.strip().lstrip("#") for t in hashtags if t.strip()]
        if youtube_title is not None:
            b["youtube_title"] = youtube_title.strip()[:100]
        s = store()
        try:
            s.update_brief(post_id, b)
        finally:
            s.close()
        return {"updated": True, "caption_as_posted": build_caption(b)}

    @mcp.tool(name="reelstudio_schedule_post", annotations=WRITE)
    def schedule_post(
        post_id: str,
        user_confirmed: bool = Field(description="True only if the person watched the finished video and told you to schedule it in this conversation."),
        publish_at: str | None = Field(default=None, description="Local time in the account's timezone, e.g. '2026-10-07T18:30'. Omit to post as soon as possible."),
    ) -> dict[str, Any]:
        """Approve a finished video and schedule it. Requires status 'review' and the person's explicit go-ahead."""
        if not user_confirmed:
            raise ToolError("Ask the person to watch the video in the dashboard and confirm before scheduling.")
        s = store()
        try:
            actions.approve(s, post_id, publish_at, tz_name())
            p = s.get(post_id)
        except KeyError:
            raise ToolError(f"No post with id '{post_id}'.")
        except ValueError as e:
            raise ToolError(str(e))
        finally:
            s.close()
        app.say(f"Claude scheduled {post_id}")
        auto = actions.auto_platforms(app.cfg)
        manual = [x for x in actions.platforms_for(app.cfg, p["format"]) if x not in auto]
        return summary(p) | {
            "instagram": "posts automatically at that time" if "instagram" in auto and "instagram" not in manual else "posted by the person",
            "posted_by_the_person": manual,
            "note": f"Manual platforms appear under 'Post it' at {link()}." if manual else "",
        }

    @mcp.tool(name="reelstudio_unschedule_post", annotations=WRITE)
    def unschedule_post(post_id: str) -> dict[str, Any]:
        """Take a scheduled post back to review so it does not go out."""
        s = store()
        try:
            actions.unschedule(s, post_id)
            return summary(s.get(post_id))
        except KeyError:
            raise ToolError(f"No post with id '{post_id}'.")
        except ValueError as e:
            raise ToolError(str(e))
        finally:
            s.close()

    @mcp.tool(name="reelstudio_reject_post", annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, openWorldHint=False))
    def reject_post(post_id: str, reason: str = "") -> dict[str, Any]:
        """Mark a post as rejected so it is never published. Only when the person asks."""
        get(post_id)
        s = store()
        try:
            actions.reject(s, post_id, reason or None)
            return summary(s.get(post_id))
        finally:
            s.close()
