@echo off
setlocal
title Reel Studio - Installer
rem ------------------------------------------------------------------
rem  Double-click this file on Windows. It downloads Reel Studio and
rem  runs setup.ps1, which installs everything else it needs.
rem  You can send this one file on its own; it fetches the rest.
rem  After the code is merged into main, change BRANCH to: main
rem ------------------------------------------------------------------
set "REPO=aimesher/Scratch"
set "BRANCH=claude/instagram-agentic-google-flow-9pjpec"

if exist "%~dp0setup.ps1" goto run_local

echo.
echo Downloading Reel Studio from GitHub...
set "PS=$ErrorActionPreference='Stop';"
set "PS=%PS% [Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;"
set "PS=%PS% $zip=Join-Path $env:TEMP 'reelstudio.zip'; $tmp=Join-Path $env:TEMP 'reelstudio_src';"
set "PS=%PS% if(Test-Path $tmp){Remove-Item $tmp -Recurse -Force};"
set "PS=%PS% Invoke-WebRequest -Uri 'https://github.com/%REPO%/archive/refs/heads/%BRANCH%.zip' -OutFile $zip -UseBasicParsing;"
set "PS=%PS% Expand-Archive -Path $zip -DestinationPath $tmp -Force;"
set "PS=%PS% $src=(Get-ChildItem $tmp -Directory | Select-Object -First 1).FullName;"
set "PS=%PS% $dst=Join-Path $env:USERPROFILE 'ReelStudio';"
set "PS=%PS% New-Item -ItemType Directory -Force -Path $dst | Out-Null;"
set "PS=%PS% Copy-Item -Path (Join-Path $src '*') -Destination $dst -Recurse -Force"
powershell -NoProfile -ExecutionPolicy Bypass -Command "%PS%"
if errorlevel 1 goto download_failed

set "APP=%USERPROFILE%\ReelStudio"
goto run_setup

:run_local
set "APP=%~dp0."

:run_setup
powershell -NoProfile -ExecutionPolicy Bypass -File "%APP%\setup.ps1" -AppDir "%APP%"
endlocal
exit /b

:download_failed
echo.
echo Could not download Reel Studio. Check your internet connection and try again.
echo Or download the ZIP yourself from https://github.com/%REPO% , unzip it,
echo and double-click "Install Reel Studio.bat" inside the folder.
echo.
pause
endlocal
exit /b 1
