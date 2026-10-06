# Reel Studio setup for Windows. Safe to run again: it skips what is already installed
# and keeps your settings, keys and posts.
param([string]$AppDir = $PSScriptRoot)

$ErrorActionPreference = 'Stop'
$AppDir = (Resolve-Path $AppDir).Path
Set-Location $AppDir

function Say($m)  { Write-Host ""; Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Fail($m) {
    Write-Host ""
    Write-Host "Setup stopped: $m" -ForegroundColor Red
    Read-Host "Press Enter to close"
    exit 1
}
function Has($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }
function Refresh-Path {
    # Pick up programs that were installed a moment ago, without restarting the window.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Install-WithWinget($id, $name) {
    if (-not (Has 'winget')) {
        Fail "Windows' installer tool (winget) was not found. Install $name by hand, then run this setup again."
    }
    Say "Installing $name. Windows may ask for permission."
    winget install --id $id -e --silent --accept-package-agreements --accept-source-agreements
    # -1978335189 means "already installed, nothing to update".
    if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne -1978335189) {
        Fail "$name could not be installed (winget code $LASTEXITCODE). Install it by hand, then run this setup again."
    }
    Refresh-Path
}
function Python-Ok {
    if (-not (Has 'py')) { return $false }
    $out = & py -3 -c "import sys; print(int(sys.version_info >= (3, 10)))" 2>$null
    return ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq '1')
}

Write-Host ""
Write-Host "Reel Studio setup" -ForegroundColor White
Write-Host "Folder: $AppDir"

# 1. Python
Say "Checking Python"
if (-not (Python-Ok)) {
    Install-WithWinget 'Python.Python.3.12' 'Python 3.12'
    if (-not (Python-Ok)) { Fail "Python was installed but is not visible yet. Close this window and run the installer once more." }
}
Ok "Python is ready"

# 2. ffmpeg (joins and trims the video clips)
Say "Checking ffmpeg"
if (-not ((Has 'ffmpeg') -and (Has 'ffprobe'))) {
    Install-WithWinget 'Gyan.FFmpeg' 'ffmpeg'
    if (-not ((Has 'ffmpeg') -and (Has 'ffprobe'))) { Fail "ffmpeg was installed but is not visible yet. Close this window and run the installer once more." }
}
Ok "ffmpeg is ready"

# 3. Private Python environment and packages
Say "Installing Reel Studio's components (first time takes a minute or two)"
$venvPy = Join-Path $AppDir '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    & py -3 -m venv (Join-Path $AppDir '.venv')
    if ($LASTEXITCODE -ne 0) { Fail "Could not create the Python environment." }
}
& $venvPy -m pip install --quiet --disable-pip-version-check -r (Join-Path $AppDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Fail "Could not download the Python packages. Check your internet connection and run this again." }
& $venvPy -c "import igflow, anthropic, yaml, requests"
if ($LASTEXITCODE -ne 0) { Fail "The installed components did not load. Delete the .venv folder inside $AppDir and run this again." }
Set-Content -Path (Join-Path $AppDir '.venv\.installed') -Value 'ok'
Ok "Components installed"

# 4. Optional: Tailscale, for the online version (tablet, phone and Claude reach this PC)
Say "Online version (optional)"
Write-Host "    Reel Studio Online lets your tablet, phone and Claude reach this PC through a"
Write-Host "    free, private Tailscale address. Your data stays on this computer."
if ((Has 'tailscale') -or (Test-Path 'C:\Program Files\Tailscale\tailscale.exe')) {
    Ok "Tailscale is already installed"
} else {
    $want = Read-Host "Install Tailscale now? (y/N)"
    if ($want -match '^[Yy]') {
        Install-WithWinget 'Tailscale.Tailscale' 'Tailscale'
        Ok "Tailscale installed. Open it from the Start menu and sign in before using Reel Studio Online."
    } else {
        Write-Host "    Skipped. You can run this setup again later to add it." -ForegroundColor Yellow
    }
}

# 5. Desktop shortcuts
Say "Creating desktop shortcuts"
function Add-Shortcut($name, $target, $description) {
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut((Join-Path ([Environment]::GetFolderPath('Desktop')) "$name.lnk"))
    $link.TargetPath = Join-Path $AppDir $target
    $link.WorkingDirectory = $AppDir
    $link.Description = $description
    $link.Save()
}
try {
    Add-Shortcut 'Reel Studio' 'Start Reel Studio.bat' 'Open the Reel Studio dashboard on this PC'
    Add-Shortcut 'Reel Studio Online' 'Start Reel Studio Online.bat' 'Run Reel Studio for your tablet, phone and Claude'
    Ok "Shortcuts 'Reel Studio' and 'Reel Studio Online' added to your desktop"
} catch {
    Write-Host "    Could not create the shortcuts. You can still open the Start files in $AppDir" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "All done." -ForegroundColor Green
Write-Host "Next time, double-click 'Reel Studio' on your desktop."
Write-Host "To use it from your tablet or with Claude, double-click 'Reel Studio Online' instead (not both at once)."
Write-Host "The first screen of the dashboard will ask for your Claude API key."
Write-Host ""
$answer = Read-Host "Open Reel Studio now? (Y/n)"
if ($answer -eq '' -or $answer -match '^[Yy]') {
    Start-Process -FilePath (Join-Path $AppDir 'Start Reel Studio.bat') -WorkingDirectory $AppDir
}
