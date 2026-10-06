"""Run the online version on your own computer.

Tailscale Funnel gives this PC a fixed https:// address (it does not change when you restart),
so your tablet, phone and Claude can reach the dashboard without any hosting company.
Your data never leaves this computer. The PC has to stay on for scheduled posts to go out.
"""
from __future__ import annotations

import getpass
import json
import os
import shutil
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path

from .config import load_dotenv, set_env_values

PORT = 8790
WINDOWS_PATHS = [r"C:\Program Files\Tailscale\tailscale.exe", r"C:\Program Files (x86)\Tailscale\tailscale.exe"]
MAC_PATHS = ["/Applications/Tailscale.app/Contents/MacOS/Tailscale"]


class PcOnlineError(RuntimeError):
    pass


def find_tailscale() -> str | None:
    found = shutil.which("tailscale")
    if found:
        return found
    for p in WINDOWS_PATHS + MAC_PATHS:
        if Path(p).exists():
            return p
    return None


def public_url(ts: str, run=subprocess.run) -> str:
    """This PC's fixed address, from Tailscale."""
    out = run([ts, "status", "--json"], capture_output=True, text=True)
    try:
        status = json.loads(out.stdout or "{}")
    except json.JSONDecodeError:
        status = {}
    if status.get("BackendState") != "Running":
        raise PcOnlineError("Tailscale is installed but not signed in. Open the Tailscale app, sign in, then start Reel Studio Online again.")
    dns = (status.get("Self") or {}).get("DNSName", "").rstrip(".")
    if not dns:
        raise PcOnlineError("Tailscale did not report this computer's name. In the Tailscale admin page, turn on MagicDNS, then try again.")
    return f"https://{dns}"


def start_funnel(ts: str, port: int, run=subprocess.run) -> None:
    """Share the local port at the fixed address. The first time, Tailscale prints a link to approve Funnel."""
    print("Opening this PC to the internet through Tailscale Funnel...")
    print("(The first time, Tailscale shows a link: open it, approve Funnel, then come back to this window.)\n", flush=True)
    result = run([ts, "funnel", "--bg", str(port)])  # not captured, so you see Tailscale's own messages
    if result.returncode != 0:
        raise PcOnlineError(
            "Tailscale could not start Funnel. If it showed a link, approve it in your browser and start again. "
            "Otherwise check that HTTPS and Funnel are allowed in the Tailscale admin page.")


def stop_funnel(ts: str, run=subprocess.run) -> None:
    run([ts, "funnel", "reset"], capture_output=True, text=True)


def dashboard_password(env_file: Path, ask=getpass.getpass, say=print) -> str:
    """Saved password, or ask for one the first time and keep it in .env."""
    load_dotenv(env_file)
    pw = os.environ.get("DASHBOARD_PASSWORD", "")
    if len(pw) >= 10:
        return pw
    say("\nChoose a password for your online dashboard (at least 10 characters).")
    say("You'll type it on your tablet and when you connect Claude. Typing is hidden.")
    while True:
        first = ask("Password: ")
        if len(first) < 10:
            say("Too short, use at least 10 characters. A short sentence works well.")
            continue
        if ask("Same password again: ") != first:
            say("Those didn't match. Try again.")
            continue
        set_env_values(env_file, {"DASHBOARD_PASSWORD": first})
        say("Saved.\n")
        return first


def keep_awake() -> None:
    """Stop Windows from going to sleep while Reel Studio Online runs, so scheduled posts go out."""
    if os.name != "nt":
        return
    try:
        import ctypes

        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
    except Exception:
        pass


def offer_install(say=print, ask=input, run=subprocess.run) -> None:
    say("Tailscale is not installed. It gives this PC a private, secure web address for your tablet and Claude.")
    if os.name == "nt" and shutil.which("winget"):
        if ask("Install it now? (Y/n) ").strip().lower() in ("", "y", "yes"):
            run(["winget", "install", "--id", "Tailscale.Tailscale", "-e", "--accept-package-agreements", "--accept-source-agreements"])
            say("\nNow open Tailscale from the Start menu, sign in (a Google account works), then start Reel Studio Online again.")
            return
    say("Download it from https://tailscale.com/download, sign in, then start Reel Studio Online again.")


def run(config_path: str, port: int = PORT) -> None:
    from .hosted import serve
    from .runlock import AlreadyRunning

    ts = find_tailscale()
    if not ts:
        offer_install()
        raise SystemExit(1)
    try:
        url = public_url(ts)
        cp = Path(config_path).resolve()
        password = dashboard_password(cp.parent / ".env")
        start_funnel(ts, port)
    except PcOnlineError as e:
        raise SystemExit(f"\n{e}")
    keep_awake()
    print(f"\nReel Studio Online is ready at:\n\n    {url}\n")
    print("Open that address on your tablet or phone and sign in with your password.")
    print("Keep this window open and the PC switched on. Press Ctrl+C to stop.\n", flush=True)
    threading.Timer(2.0, lambda: webbrowser.open(url)).start()
    try:
        serve(str(cp), port, url, password, host="127.0.0.1", where="pc")
    except AlreadyRunning as e:
        raise SystemExit(f"\n{e}")
    except KeyboardInterrupt:
        pass
    finally:
        stop_funnel(ts)
        print("Stopped. Your PC is no longer reachable from the internet.")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "config.yaml")
