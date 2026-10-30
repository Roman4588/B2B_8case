"""Operator-only temporary entrypoint for the requested source-outage acceptance."""
import json
import os
import signal
import sys
import threading
import time
import urllib.request
from pathlib import Path


def probe():
    marker = Path('/data/source-failure-probe-result.json')
    if marker.exists():
        print('OPERATOR_SOURCE_PROBE_ALREADY_COMPLETED', flush=True)
        return
    paused = []
    try:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen('http://127.0.0.1/api/health/ready', timeout=5) as response:
                    if json.load(response).get('status') == 'ready':
                        break
            except Exception:
                pass
            time.sleep(2)
        else:
            raise RuntimeError('Readiness deadline exceeded')
        time.sleep(30)
        targets = []
        for folder in Path('/proc').iterdir():
            if not folder.name.isdigit():
                continue
            try:
                argv = (folder / 'cmdline').read_bytes().split(b'\0')
                if Path(os.fsdecode(argv[0])).name == 'prometheus' or b'/opt/exporter.py' in argv[1:]:
                    targets.append(int(folder.name))
            except (FileNotFoundError, ProcessLookupError, PermissionError):
                pass
        if len(targets) != 2:
            raise RuntimeError(f'Expected exactly two source processes, found {len(targets)}')
        for pid in targets:
            os.kill(pid, signal.SIGSTOP)
            paused.append(pid)
        print('OPERATOR_SOURCE_PROBE_PAUSED_90_SECONDS', flush=True)
        time.sleep(90)
    except Exception as exc:
        print('OPERATOR_SOURCE_PROBE_FAILED', type(exc).__name__, str(exc), flush=True)
        return
    finally:
        for pid in paused:
            try:
                os.kill(pid, signal.SIGCONT)
            except ProcessLookupError:
                pass
        if paused:
            print('OPERATOR_SOURCE_PROBE_RESUMED', flush=True)
    marker.write_text(json.dumps({'paused_processes': len(paused), 'pause_seconds': 90, 'resumed': True}))


def main():
    sys.path.insert(0, '/app')
    from app.processes import main as run_application

    threading.Thread(target=probe, daemon=True).start()
    sys.argv = ['app.processes', 'standalone']
    run_application()


if __name__ == '__main__':
    main()
