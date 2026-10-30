"""Linux lifecycle checks for the actual multi-process container entrypoint."""
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="Container uses POSIX process groups")


def wait_file(path, runner):
    deadline = time.monotonic() + 10
    while not path.exists() and time.monotonic() < deadline:
        if runner.poll() is not None:
            pytest.fail(f"Supervisor exited early: {runner.communicate()}")
        time.sleep(0.05)
    assert path.exists()
    return int(path.read_text())


def launch(tmp_path, fail):
    pidfile = tmp_path / "child.pid"
    sleeper = f"import os,time; from pathlib import Path; p=Path({str(pidfile)!r}); t=p.with_suffix('.tmp'); t.write_text(str(os.getpid())); t.replace(p); time.sleep(120)"
    commands = [[sys.executable, "-c", sleeper]]
    if fail:
        failure = f"import time\nfrom pathlib import Path\nwhile not Path({str(pidfile)!r}).exists():\n time.sleep(.01)\nraise SystemExit(7)"
        commands.append([sys.executable, "-c", failure])
    code = f"from app.processes import run_services; raise SystemExit(run_services({commands!r}, grace_seconds=1))"
    runner = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              text=True, cwd=Path(__file__).resolve().parents[1])
    return runner, wait_file(pidfile, runner)


def assert_gone(pid):
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


def test_failed_child_stops_siblings_and_container(tmp_path):
    runner, child = launch(tmp_path, fail=True)
    try:
        assert runner.wait(timeout=10) != 0
        assert_gone(child)
    finally:
        if runner.poll() is None:
            runner.terminate()
            runner.wait(timeout=5)


def test_sigterm_stops_and_reaps_children(tmp_path):
    runner, child = launch(tmp_path, fail=False)
    try:
        runner.send_signal(signal.SIGTERM)
        assert runner.wait(timeout=10) == 0
        assert_gone(child)
    finally:
        if runner.poll() is None:
            runner.kill()
            runner.wait(timeout=5)
