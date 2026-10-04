from __future__ import annotations

import copy
import os
from pathlib import Path

import yaml

DEFAULTS: dict = {
    "brand": {
        "niche": "",
        "audience": "",
        "voice": "",
        "visual_style": "",
        "recurring_subjects": "",
        "avoid": "",
    },
    "paths": {"data": "data", "drop": "drop", "out": "out"},
    "video": {
        "width": 1080,
        "height": 1920,
        "fps": 30,
        "min_seconds": 10,
        "max_seconds": 12,
        # Clip lengths Flow can produce. Shot plans are validated against this.
        "allowed_clip_seconds": [4, 6, 8],
        "music_volume": 0.25,
    },
    "agent": {"provider": "anthropic", "model": "claude-opus-5-5", "effort": "medium", "gemini_model": "gemini-flash-latest",
              "gemini_fallback_models": ["gemini-flash-lite-latest", "gemini-pro-latest"]},
    "watcher": {"poll_seconds": 5, "stable_seconds": 4},
    "instagram": {"api_version": "v23.0", "max_per_day": 3, "status_timeout_seconds": 300},
    # manual: you post with the dashboard's help. instagram_api: the dashboard posts Reels/Stories itself.
    "publish": {"method": "manual", "platforms": ["instagram", "youtube"]},
}


def _merge(base: dict, over: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def load_dotenv(path: Path) -> None:
    """Minimal .env reader. Real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


class Config:
    def __init__(self, raw: dict, base_dir: Path):
        self.raw = _merge(DEFAULTS, raw)
        self.base_dir = base_dir

    @classmethod
    def load(cls, path: str | Path = "config.yaml") -> "Config":
        path = Path(path).resolve()
        if not path.exists():
            raise SystemExit(f"{path} not found. Copy config.example.yaml to config.yaml and edit it.")
        load_dotenv(path.parent / ".env")
        return cls(yaml.safe_load(path.read_text()) or {}, path.parent)

    def __getitem__(self, key: str) -> dict:
        return self.raw[key]

    def path(self, name: str) -> Path:
        p = self.base_dir / self.raw["paths"][name]
        p.mkdir(parents=True, exist_ok=True)
        return p


def set_env_values(path: Path, values: dict[str, str]) -> None:
    """Update or add KEY=value lines in a .env file, keeping everything else."""
    lines = path.read_text().splitlines() if path.exists() else []
    pending = dict(values)
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in pending and "=" in line and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={pending.pop(key)}"
    lines += [f"{k}={v}" for k, v in pending.items()]
    path.write_text("\n".join(lines) + "\n")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    os.environ.update(values)


def mask(value: str | None) -> str:
    return "" if not value else ("\u2022" * 8 + value[-4:] if len(value) > 8 else "\u2022" * 8)
