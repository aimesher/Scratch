@echo off
rem Opens the Reel Studio dashboard. Run "Install Reel Studio.bat" first.
title Reel Studio
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
if not exist ".venv\.installed" (
  ".venv\Scripts\python.exe" -m pip install --quiet --disable-pip-version-check -r requirements.txt
  echo ok> ".venv\.installed"
)
".venv\Scripts\python.exe" -m igflow ui
echo.
echo Reel Studio has stopped.
pause
