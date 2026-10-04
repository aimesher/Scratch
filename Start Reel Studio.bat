@echo off
rem Double-click this file on Windows. First run takes a minute while it installs.
cd /d "%~dp0"
where py >nul 2>nul
if errorlevel 1 (
  echo Python 3 is needed. Install it from python.org and tick "Add Python to PATH", then run this again.
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg is needed. Open a terminal and run: winget install ffmpeg
  pause
  exit /b 1
)
if not exist .venv py -m venv .venv
.venv\Scripts\pip install -q -r requirements.txt
.venv\Scripts\python -m igflow ui
pause
