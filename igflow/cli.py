from __future__ import annotations

import argparse
import shutil
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import agent
from .config import Config
from .db import Store
from .publish import InstagramClient, publish_due
from .watcher import process_drops


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def _store(cfg: Config) -> Store:
    return Store(cfg.path("data") / "queue.db")


def _master_path(cfg: Config) -> Path:
    return cfg.path("data") / "master_prompt.md"


def cmd_master(cfg: Config, args) -> None:
    path = _master_path(cfg)
    if path.exists() and not args.force:
        raise SystemExit(f"{path} exists. Edit it, or pass --force to regenerate.")
    path.write_text(agent.generate_master(cfg, notes=args.notes or ""))
    log(f"wrote {path}. Read it, edit it, then run `plan`.")


def cmd_plan(cfg: Config, args) -> None:
    path = _master_path(cfg)
    if not path.exists():
        raise SystemExit("No master prompt yet. Run `master` first.")
    ids = agent.plan_posts(cfg, _store(cfg), path.read_text(), args.count, args.format, args.theme or "")
    for i in ids:
        log(f"brief: {cfg.path('data') / 'briefs' / (i + '.md')}")
        log(f"drop clips in: {cfg.path('drop') / i}")


def cmd_status(cfg: Config, args) -> None:
    for p in _store(cfg).list(args.status):
        extra = f"  ({p['error']})" if p["error"] else ""
        sched = f"  @ {p['scheduled_at']}" if p["scheduled_at"] else ""
        print(f"{p['status']:<10} {p['format']:<5} {p['id']}{sched}{extra}")


def cmd_review(cfg: Config, args) -> None:
    posts = _store(cfg).list("review")
    if not posts:
        print("Nothing waiting for review.")
    for p in posts:
        print(f"\n{p['id']}\n  video:   {p['final_path']}\n  cover:   {Path(p['final_path']).with_suffix('.jpg')}")
        print(f"  caption: {p['brief']['caption']}\n  approve: python -m igflow approve {p['id']} [--at '2026-10-05 18:30']")
        if p["error"]:
            print(f"  note:    {p['error']}")


def _parse_when(text: str | None) -> str:
    if not text:
        return datetime.now(timezone.utc).isoformat(timespec="seconds")
    dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.astimezone()  # interpret as local time
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def cmd_approve(cfg: Config, args) -> None:
    store = _store(cfg)
    post = store.get(args.id)
    if post["status"] not in ("review", "failed"):
        raise SystemExit(f"{args.id} is {post['status']}, only posts in review (or failed) can be approved.")
    store.update(args.id, status="approved", scheduled_at=_parse_when(args.at), error=None)
    log(f"approved {args.id}")


def cmd_reject(cfg: Config, args) -> None:
    _store(cfg).update(args.id, status="rejected", error=args.reason)
    log(f"rejected {args.id}")


def cmd_redo(cfg: Config, args) -> None:
    """Send a post back to 'briefed' so new clips can be dropped in."""
    store = _store(cfg)
    store.get(args.id)
    drop = cfg.path("drop") / args.id
    old = drop / "_old"
    old.mkdir(parents=True, exist_ok=True)
    for f in drop.iterdir():
        if f.is_file():
            shutil.move(str(f), old / f.name)
    store.update(args.id, status="briefed", error=None, final_path=None)
    log(f"{args.id} is back to briefed. Drop new clips in {drop}")


def cmd_watch(cfg: Config, args) -> None:
    store = _store(cfg)
    while True:
        process_drops(cfg, store, log)
        if args.once:
            return
        time.sleep(cfg["watcher"]["poll_seconds"])


def cmd_publish(cfg: Config, args) -> None:
    publish_due(cfg, _store(cfg), dry_run=args.dry_run, log=log)


def cmd_run(cfg: Config, args) -> None:
    """Daemon: watch the drop folder and publish approved posts when due."""
    store = _store(cfg)
    log("running. Ctrl+C to stop.")
    while True:
        try:
            process_drops(cfg, store, log)
            publish_due(cfg, store, log=log)
        except Exception as e:  # keep the daemon alive; the post itself is marked failed where relevant
            log(f"loop error: {e}")
        time.sleep(cfg["watcher"]["poll_seconds"])


def cmd_refresh_token(cfg: Config, args) -> None:
    body = InstagramClient.from_env(cfg).refresh_token()
    days = body.get("expires_in", 0) // 86400
    print(f"New token valid for ~{days} days. Put this in IG_ACCESS_TOKEN:\n{body['access_token']}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(prog="igflow", description=__doc__)
    ap.add_argument("--config", default="config.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("master", help="generate the master prompt (style bible)")
    p.add_argument("--force", action="store_true")
    p.add_argument("--notes", help="extra direction for the agent")
    p.set_defaults(fn=cmd_master)

    p = sub.add_parser("plan", help="generate briefs and Flow prompts")
    p.add_argument("-n", "--count", type=int, default=3)
    p.add_argument("--format", choices=["reel", "story"], default="reel")
    p.add_argument("--theme")
    p.set_defaults(fn=cmd_plan)

    p = sub.add_parser("status")
    p.add_argument("--status")
    p.set_defaults(fn=cmd_status)

    sub.add_parser("review", help="list assembled posts awaiting approval").set_defaults(fn=cmd_review)

    p = sub.add_parser("approve")
    p.add_argument("id")
    p.add_argument("--at", help="local time, e.g. '2026-10-05 18:30'. Default: now")
    p.set_defaults(fn=cmd_approve)

    p = sub.add_parser("reject")
    p.add_argument("id")
    p.add_argument("--reason")
    p.set_defaults(fn=cmd_reject)

    p = sub.add_parser("redo", help="move old clips aside and wait for new ones")
    p.add_argument("id")
    p.set_defaults(fn=cmd_redo)

    p = sub.add_parser("watch", help="watch drop folders and assemble")
    p.add_argument("--once", action="store_true")
    p.set_defaults(fn=cmd_watch)

    p = sub.add_parser("publish", help="publish approved posts that are due")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(fn=cmd_publish)

    sub.add_parser("run", help="watch + publish loop").set_defaults(fn=cmd_run)
    sub.add_parser("refresh-token", help="refresh the Instagram access token").set_defaults(fn=cmd_refresh_token)

    args = ap.parse_args(argv)
    args.fn(Config.load(args.config), args)


if __name__ == "__main__":
    main(sys.argv[1:])
