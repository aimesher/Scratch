# igflow

Agent-assisted Instagram pipeline for 10-12 second Reels and Stories. Generation stays manual in Google Flow (your plan credits). Everything around it is automated.

```
master  ->  plan  ->  [you generate in Flow]  ->  drop folder  ->  watch  ->  review  ->  approve  ->  publish
Claude      Claude     paste prompts, download     auto-detected    ffmpeg    you        you         Instagram API
```

## Setup

```bash
pip install -r requirements.txt        # also needs ffmpeg on PATH
cp config.example.yaml config.yaml     # edit the brand section
cat > .env <<'EOF'
ANTHROPIC_API_KEY=...
IG_USER_ID=...
IG_ACCESS_TOKEN=...
EOF
```

## Daily loop

```bash
python -m igflow master                 # once. Writes data/master_prompt.md. Read it and edit it.
python -m igflow plan -n 3 --theme "..."  # briefs in data/briefs/<id>.md, drop folders in drop/<id>/
python -m igflow run                    # leave running: assembles clips, publishes approved posts
```

1. Open `data/briefs/<id>.md`. It holds the reference image prompt, one copy-paste Flow prompt per shot, caption, hashtags and on-screen text.
2. Generate each shot in Flow. For shot 2+, start from the last frame of the previous clip (frames-to-video) so the cut is continuous.
3. Download the clips into `drop/<id>/` named `1.mp4`, `2.mp4` in shot order. Optional `music.mp3`. If the files are not numbered, download order is used.
4. The watcher waits until every clip has arrived and stopped changing, then writes `out/<id>/final.mp4` (1080x1920, H.264/AAC, trimmed to 12s) and a `final.jpg` cover.
5. `python -m igflow review`, watch the file, then `approve <id> --at "2026-10-05 18:30"` or `reject <id>` or `redo <id>`.
6. `run` publishes approved posts when their time arrives, capped at `instagram.max_per_day`.

Other commands: `status`, `watch --once`, `publish --dry-run`, `refresh-token` (Instagram tokens last 60 days).

## Instagram setup

You need a professional (Business or Creator) account, a Meta developer app with the Instagram API (Instagram Login) product, and your own account added as a tester. For a single account you can stay in development mode and skip app review. Generate a token with the `instagram_business_basic` and `instagram_business_content_publish` permissions.

`publish.py` uploads the file directly (resumable upload), so you do not need to host videos publicly. **I wrote these endpoints from memory; the build environment could not reach Meta's docs.** The first real post is the test. Use a throwaway Story first. Errors print Meta's response body verbatim.

## Notes

- Stories cannot carry captions or stickers through the API. Add polls and links in the app.
- Text on screen is not burned in. Add it in Instagram's editor so it uses native fonts and stays inside the safe zone.
- The agent never sees your Flow account and never sends anything to Flow. Nothing is published without `approve`.
- Tests: `python -m pytest` (uses real ffmpeg, no network).
