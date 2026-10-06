import json
import subprocess
import sys
from types import SimpleNamespace

import pytest

from igflow import pc_online
from igflow.runlock import AlreadyRunning, RunLock


def fake_run(status: dict, funnel_code: int = 0, log: list | None = None):
    def run(cmd, capture_output=False, text=False):
        if log is not None:
            log.append(cmd)
        if cmd[1:3] == ["status", "--json"]:
            return SimpleNamespace(returncode=0, stdout=json.dumps(status), stderr="")
        if cmd[1] == "funnel":
            return SimpleNamespace(returncode=funnel_code, stdout="", stderr="")
        raise AssertionError(cmd)
    return run


def test_public_url_comes_from_tailscale():
    run = fake_run({"BackendState": "Running", "Self": {"DNSName": "studio-pc.tail1234.ts.net."}})
    assert pc_online.public_url("ts", run) == "https://studio-pc.tail1234.ts.net"


def test_signed_out_tailscale_gives_a_clear_message():
    with pytest.raises(pc_online.PcOnlineError, match="not signed in"):
        pc_online.public_url("ts", fake_run({"BackendState": "NeedsLogin"}))


def test_funnel_start_and_stop_commands():
    log = []
    pc_online.start_funnel("ts", 8790, fake_run({}, log=log))
    pc_online.stop_funnel("ts", fake_run({}, log=log))
    assert log == [["ts", "funnel", "--bg", "8790"], ["ts", "funnel", "reset"]]
    with pytest.raises(pc_online.PcOnlineError, match="approve"):
        pc_online.start_funnel("ts", 8790, fake_run({}, funnel_code=1))


def test_password_asked_once_then_remembered(tmp_path, monkeypatch):
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    env = tmp_path / ".env"
    answers = iter(["short", "a long password", "different", "a long password", "a long password"])
    said = []
    pw = pc_online.dashboard_password(env, ask=lambda _: next(answers), say=said.append)
    assert pw == "a long password" and "DASHBOARD_PASSWORD=a long password" in env.read_text()
    assert any("Too short" in s for s in said) and any("didn't match" in s for s in said)
    # second start: no questions
    assert pc_online.dashboard_password(env, ask=lambda _: pytest.fail("asked again")) == "a long password"


def test_only_one_copy_can_run(tmp_path):
    first = RunLock(tmp_path).acquire()
    # a second process (like double-clicking both shortcuts) must be refused
    code = ("import sys; sys.path.insert(0, %r); from pathlib import Path; from igflow.runlock import RunLock, AlreadyRunning\n"
            "try:\n    RunLock(Path(%r)).acquire(); print('acquired')\nexcept AlreadyRunning: print('refused')") % (str(pc_online.Path(__file__).resolve().parent.parent), str(tmp_path))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
    assert out == "refused"
    first.release()
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True).stdout.strip()
    assert out == "acquired"
