"""Fail together and forward shutdown signals for co-located demo processes."""
import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path


def run_services(commands: list[list[str]], grace_seconds: float = 15) -> int:
    stopping = False
    children = []

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, stop) for sig in (signal.SIGTERM, signal.SIGINT)}
    try:
        for command in commands:
            if stopping:
                return 0
            children.append(subprocess.Popen(command, start_new_session=True))
        while not stopping:
            for child in children:
                code = child.poll()
                if code is not None:
                    print(f"Critical service exited with code {code}: {child.args[0]}", file=sys.stderr, flush=True)
                    return code or 1
            time.sleep(0.1)
        return 0
    finally:
        for child in children:
            try:
                os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + grace_seconds
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["application", "monitoring", "standalone"])
    role = parser.parse_args().role
    if role == "standalone":
        from app.standalone import commands as standalone_commands

        raise SystemExit(run_services(standalone_commands(), grace_seconds=30))
    if role == "application":
        compact = os.getenv("SINGLE_STACK") == "true"
        if compact:
            subprocess.run([sys.executable, "-m", "app.standalone", "prepare"], check=True)
        subprocess.run([sys.executable, "-m", "app.bootstrap"], check=True)
        if os.getenv("ADMIN_EMAIL") and os.getenv("ADMIN_PASSWORD"):
            result = subprocess.run([sys.executable, "-m", "app.manage", "create-admin", "--non-interactive"])
            if result.returncode:
                print("Administrator provisioning did not complete; inspect the message above.", file=sys.stderr)
        commands = [
            ["uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000"],
            ["celery", "-A", "app.tasks.celery", "worker", "--pool=threads", "--concurrency=2", "--loglevel=INFO"],
            ["celery", "-A", "app.tasks.celery", "beat", "--loglevel=INFO", "--schedule=/tmp/celerybeat-schedule"],
            ["nginx", "-g", "daemon off;"],
        ]
        if compact:
            commands = [commands[0],
                        ["celery", "-A", "app.tasks.celery", "worker", "--pool=solo", "--concurrency=1", "--beat",
                         "--schedule=/tmp/celerybeat-schedule", "--loglevel=INFO"], commands[3]]
    else:
        Path("/data/prometheus").mkdir(parents=True, exist_ok=True)
        commands = [
            [sys.executable, "/opt/exporter.py"],
            ["prometheus", "--config.file=/etc/prometheus/prometheus.yml", "--storage.tsdb.path=/data/prometheus",
             "--storage.tsdb.retention.time=2d", "--storage.tsdb.retention.size=400MB"],
        ]
    raise SystemExit(run_services(commands))


if __name__ == "__main__":
    main()
