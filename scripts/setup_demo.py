#!/usr/bin/env python3
"""Non-destructive initial setup for both independent SQLite applications."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / ".runs"
RUNS.mkdir(exist_ok=True)
commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
if subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip():
    print("Note: tracked source has edits; initial named baseline still points to the committed HEAD.")
for role in ("refunds", "control"):
    env = dict(os.environ, FINCORP_ROLE=role)
    subprocess.run([sys.executable, str(ROOT / "manage.py"), "migrate", "--noinput"], env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/seed.py")], env=env, check=True)
baseline = RUNS / "baseline.json"
if not baseline.exists():
    baseline.write_text(json.dumps({"name": "vulnerable-null-note-v1", "commit": commit}))
runtime = RUNS / "runtime.json"
if not runtime.exists():
    runtime.write_text(json.dumps({"commit": json.loads(baseline.read_text())["commit"]}))
print(f"Named baseline {json.loads(baseline.read_text())['commit']} selected; no remote created.")
