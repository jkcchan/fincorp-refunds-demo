#!/usr/bin/env python3
import os
import sys
import time
from pathlib import Path

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
    try:
        while True:
            commit = runtime_state()["commit"]
            if commit != selected or (pid and not probe("http://127.0.0.1:8001", selected)):
                stop(pid)
                pid, _ = serve(commit, RUNTIME_DB, "runtime", 8001, "runtime-" + commit[:12])
                selected = commit
                print(f"Refund runtime {commit} at http://127.0.0.1:8001", flush=True)
            time.sleep(.5)
    except KeyboardInterrupt:
        pass
    finally:
        stop(pid)


if __name__ == "__main__":
    main()
