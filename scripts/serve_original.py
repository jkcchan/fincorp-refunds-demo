#!/usr/bin/env python3
"""Serve a read-only-to-the-workflow snapshot of the named demo baseline."""
import json
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
from control.runner import ROOT as SOURCE, RUNS, RUNTIME_DB, backup, serve, stop


def main():
    url = os.getenv("FINCORP_ORIGINAL_URL", "http://127.0.0.1:8401").rstrip("/")
    parsed = urlsplit(url)
    if parsed.scheme != "http" or parsed.hostname != "127.0.0.1" or not parsed.port or parsed.path:
        raise ValueError("FINCORP_ORIGINAL_URL must be an http://127.0.0.1:PORT loopback origin.")
    commit = json.loads((SOURCE / "scripts/customer_demo.json").read_text())["baseline"]
    db = RUNS / "data" / "customer-original.sqlite3"
    backup(RUNTIME_DB, db)
    pid = None
    try:
        pid, _ = serve(commit, db, "demo-baseline", parsed.port, "customer-original-" + commit[:12])
        print(f"Original sample baseline {commit} at {url}", flush=True)
        while True:
            time.sleep(2)
    except KeyboardInterrupt:
        pass
    finally:
        stop(pid)


if __name__ == "__main__":
    main()
