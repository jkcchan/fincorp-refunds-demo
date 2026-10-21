#!/usr/bin/env python3
"""Opt-in reset of named synthetic fixtures only; never rewrites Git history."""
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
parser = argparse.ArgumentParser()
parser.add_argument("--confirm-demo-reset", action="store_true")
args = parser.parse_args()
if not args.confirm_demo_reset:
    parser.error("Explicit --confirm-demo-reset is required; this deletes only the named legacy fixture.")
baseline = ROOT / ".runs/baseline.json"
if not baseline.exists():
    parser.error("No named baseline recorded; run setup before reset.")
os.environ["FINCORP_ROLE"] = "refunds"
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
import django
django.setup()
from django.db import transaction
from refunds.models import AuditEvent, Case, Payment
from scripts.seed import seed_refunds, seed_users

with transaction.atomic():
    case = Case.objects.filter(reference="RF-LEGACY-NULL").first()
    if case:
        AuditEvent.objects.filter(case=case).delete()
        case.delete()
    seed_users()
    seed_refunds()
selected = json.loads(baseline.read_text())["commit"]
new_tree = ROOT / ".runs/release-cycles" / ("cycle-" + uuid.uuid4().hex[:12])
new_tree.parent.mkdir(parents=True, exist_ok=True)
subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(new_tree), selected], check=True)
active = ROOT / ".runs/active-release.json"
temp = active.with_suffix(".tmp")
temp.write_text(json.dumps({"path": str(new_tree)}))
os.replace(temp, active)
runtime = ROOT / ".runs/runtime.json"
temp = runtime.with_suffix(".tmp")
temp.write_text(json.dumps({"commit": selected}))
os.replace(temp, runtime)
print("Named legacy row removed and baseline selected in a NEW release worktree. Previous worktrees, unrelated cases, control history and Git commits preserved. Restart the controller and worker after reset.")
