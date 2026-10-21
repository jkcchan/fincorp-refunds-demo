#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
os.environ["FINCORP_ROLE"] = "control"
import django
django.setup()
from control.runner import RUNTIME_DB, probe, runtime_state, serve, stop


def main():
    pid = None
    selected = None
    url = os.getenv("FINCORP_RUNTIME_URL", "http://127.0.0.1:8001").rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path:
        raise ValueError("FINCORP_RUNTIME_URL must be an http://127.0.0.1:PORT loopback origin.")
    try:
        while True:
            commit = runtime_state()["commit"]
            if commit != selected or (pid and not probe(url, selected)):
                stop(pid)
                pid, _ = serve(commit, RUNTIME_DB, "runtime", parsed.port, "runtime-" + commit[:12])
                selected = commit
                print(f"Refund runtime {commit} at {url}", flush=True)
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop(pid)


if __name__ == "__main__":
    main()
