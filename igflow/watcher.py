from __future__ import annotations

import re
import time
from pathlib import Path

from .assemble import AssembleError, assemble
from .config import Config
from .db import Store

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac"}


def order_clips(paths: list[Path]) -> list[Path]:
    """Sort by leading number (1.mp4, 02_x.mp4) when every file has one, else by modified time."""
    nums = [re.match(r"(\d+)", p.stem) for p in paths]
    if all(nums):
        return [p for _, p in sorted(zip((int(m.group(1)) for m in nums), paths), key=lambda t: t[0])]
    return sorted(paths, key=lambda p: (p.stat().st_mtime, p.name))


def scan(drop_dir: Path, expected: int, stable_seconds: float, now: float | None = None):
    """Return (clips, music) when the drop folder is complete and files stopped changing, else None."""
    if not drop_dir.is_dir():
        return None
    now = time.time() if now is None else now
    files = [p for p in drop_dir.iterdir() if p.is_file() and not p.name.startswith(".")]
    videos = [p for p in files if p.suffix.lower() in VIDEO_EXT]
    music = [p for p in files if p.suffix.lower() in AUDIO_EXT]
    if len(videos) < expected:
        return None
    if any(p.stat().st_size == 0 or now - p.stat().st_mtime < stable_seconds for p in videos + music):
        return None
    if len(videos) > expected:
        # Regenerated a shot: keep the newest `expected` files.
        videos = sorted(videos, key=lambda p: p.stat().st_mtime)[-expected:]
    return order_clips(videos), (max(music, key=lambda p: p.stat().st_mtime) if music else None)


def process_drops(cfg: Config, store: Store, log=print) -> int:
    """Assemble every briefed post whose clips have arrived. Returns the number processed."""
    done = 0
    for post in store.list("briefed"):
        found = scan(cfg.path("drop") / post["id"], len(post["brief"]["shots"]), cfg["watcher"]["stable_seconds"])
        if not found:
            continue
        clips, music = found
        store.update(post["id"], status="assembling")
        log(f"[{post['id']}] assembling {len(clips)} clips" + (f" + {music.name}" if music else ""))
        out = cfg.path("out") / post["id"] / "final.mp4"
        try:
            result = assemble(clips, music, out, cfg)
        except (AssembleError, OSError) as e:
            store.update(post["id"], status="failed", error=str(e))
            log(f"[{post['id']}] assembly failed: {e}")
            continue
        note = "; ".join(result["warnings"])
        store.update(post["id"], status="review", final_path=str(out), error=note or None)
        log(f"[{post['id']}] ready for review ({result['duration']:.1f}s) {out}" + (f"  WARN: {note}" if note else ""))
        done += 1
    return done
