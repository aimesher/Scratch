@echo off
rem Runs Reel Studio so your tablet, phone and Claude can reach this PC (needs Tailscale).
rem Keep this window open and the PC on. Do not run it together with "Start Reel Studio.bat".
title Reel Studio Online
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Reel Studio is not installed yet. Double-click "Install Reel Studio.bat" first.
  pause
  exit /b 1
)
where ffmpeg >nul 2>nul
if errorlevel 1 (
  echo ffmpeg was not found. Run "Install Reel Studio.bat" again to fix it.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
".venv\Scripts\python.exe" -m igflow online
echo.
echo Reel Studio Online has stopped.
pause
