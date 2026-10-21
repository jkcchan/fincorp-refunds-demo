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
source = json.loads((ROOT / "scripts/baseline.json").read_text())
commit = source["commit"]
subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", commit + "^{commit}"], check=True)
release_tree = RUNS / "release-tree"
if not (release_tree / ".git").exists():
    subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(release_tree), commit], check=True)
active = RUNS / "active-release.json"
if not active.exists():
    active.write_text(json.dumps({"path": str(release_tree)}))
if subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True).stdout.strip():
    print("Note: controller source has edits; the named baseline points to its pinned original commit.")
for role in ("refunds", "control"):
    env = dict(os.environ, FINCORP_ROLE=role)
    subprocess.run([sys.executable, str(ROOT / "manage.py"), "migrate", "--noinput"], env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/seed.py")], env=env, check=True)
baseline = RUNS / "baseline.json"
if not baseline.exists():
    baseline.write_text(json.dumps(source))
runtime = RUNS / "runtime.json"
if not runtime.exists():
    runtime.write_text(json.dumps({"commit": json.loads(baseline.read_text())["commit"]}))
print(f"Named baseline {json.loads(baseline.read_text())['commit']} selected; no remote created.")
