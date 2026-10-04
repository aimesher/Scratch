from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .config import Config


class AssembleError(RuntimeError):
    pass


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssembleError(f"{cmd[0]} failed: {proc.stderr.strip()[-800:]}")
    return proc.stdout


def probe(path: Path) -> dict:
    out = _run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)]
    )
    info = json.loads(out)
    streams = info.get("streams", [])
    if not any(s["codec_type"] == "video" for s in streams):
        raise AssembleError(f"{path.name} has no video stream")
    return {
        "duration": float(info["format"]["duration"]),
        "has_audio": any(s["codec_type"] == "audio" for s in streams),
    }


def build_command(clips: list[Path], infos: list[dict], music: Path | None, out: Path, cfg: Config) -> list[str]:
    v = cfg["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    total = min(sum(i["duration"] for i in infos), float(v["max_seconds"]))

    cmd = ["ffmpeg", "-y", "-v", "error"]
    for c in clips:
        cmd += ["-i", str(c)]
    if music:
        cmd += ["-i", str(music)]

    parts: list[str] = []
    for idx, info in enumerate(infos):
        # Scale to cover the 9:16 frame, then centre-crop, so any source ratio fits.
        parts.append(
            f"[{idx}:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},"
            f"fps={fps},setsar=1,format=yuv420p[v{idx}]"
        )
        if info["has_audio"]:
            parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo[a{idx}]")
        else:
            parts.append(f"aevalsrc=0|0:d={info['duration']:.3f}:s=48000[a{idx}]")

    n = len(clips)
    joined = "".join(f"[v{i}][a{i}]" for i in range(n))
    parts.append(f"{joined}concat=n={n}:v=1:a=1[vcat][acat]")

    fade_at = max(total - 0.4, 0)
    if music:
        parts.append(f"[{n}:a]aresample=48000,aformat=channel_layouts=stereo,volume={v['music_volume']}[mus]")
        # amix halves each input by default; volume=2 restores the dialogue level.
        parts.append("[acat][mus]amix=inputs=2:duration=first:dropout_transition=0,volume=2,alimiter=limit=0.95[amix]")
        audio_label = "amix"
    else:
        audio_label = "acat"
    parts.append(f"[{audio_label}]afade=t=out:st={fade_at:.3f}:d=0.4[aout]")

    cmd += [
        "-filter_complex", ";".join(parts),
        "-map", "[vcat]", "-map", "[aout]",
        "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-profile:v", "high",
        "-pix_fmt", "yuv420p", "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]
    return cmd


def assemble(clips: list[Path], music: Path | None, out: Path, cfg: Config) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    infos = [probe(c) for c in clips]
    _run(build_command(clips, infos, music, out, cfg))
    final = probe(out)
    thumb = out.with_suffix(".jpg")
    _run(["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(out), "-frames:v", "1", "-q:v", "2", str(thumb)])

    v = cfg["video"]
    warnings = []
    if final["duration"] < v["min_seconds"] - 0.5:
        warnings.append(f"shorter than target ({final['duration']:.1f}s < {v['min_seconds']}s)")
    return {"duration": final["duration"], "thumbnail": str(thumb), "warnings": warnings}
