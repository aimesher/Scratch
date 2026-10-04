#!/bin/bash
# Double-click this file on a Mac. First run takes a minute while it installs.
cd "$(dirname "$0")"
pause() { read -n 1 -s -r -p "Press any key to close."; echo; }
command -v python3 >/dev/null || { echo "Python 3 is needed. Install it from python.org, then double-click this file again."; pause; exit 1; }
command -v ffmpeg >/dev/null || { echo "ffmpeg is needed. Open Terminal and run: brew install ffmpeg   (get Homebrew at brew.sh)"; pause; exit 1; }
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt
.venv/bin/python -m igflow ui
pause
