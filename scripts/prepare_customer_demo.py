#!/usr/bin/env python3
"""Create an isolated, non-destructive customer replay in a fresh checkout."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / ".runs"
config = json.loads((ROOT / "scripts/customer_demo.json").read_text())
base = config["baseline"]

if os.getenv("FINCORP_MODE") != "sample":
    raise SystemExit("Set FINCORP_MODE=sample explicitly for this recorded fixture demo.")
if any(path.exists() for path in (RUNS / "release-tree", RUNS / "runtime.json", ROOT / "control.sqlite3", ROOT / "refunds.sqlite3")):
    raise SystemExit("Use a fresh checkout. Existing demo data and release selections will not be changed.")
subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", base + "^{commit}"], check=True)
RUNS.mkdir(exist_ok=True)
subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(RUNS / "release-tree"), base], check=True)
for role in ("refunds", "control"):
    env = dict(os.environ, FINCORP_ROLE=role)
    subprocess.run([sys.executable, str(ROOT / "manage.py"), "migrate", "--noinput"], env=env, check=True)
    subprocess.run([sys.executable, str(ROOT / "scripts/seed.py")], env=env, check=True)
(RUNS / "active-release.json").write_text(json.dumps({"path": str(RUNS / "release-tree")}))
(RUNS / "baseline.json").write_text(json.dumps({"name": config["name"], "commit": base}))
(RUNS / "runtime.json").write_text(json.dumps({"commit": base}))
print(f"Prepared isolated {config['name']} at {base}; no remote or Devin session created.")
