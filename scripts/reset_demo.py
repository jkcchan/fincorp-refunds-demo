#!/usr/bin/env python3
"""Opt-in reset of named synthetic fixtures only; never rewrites Git history."""
import argparse
import json
import os
import sys
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
from control.runner import select_runtime
select_runtime(json.loads(baseline.read_text())["commit"])
print("Named legacy row removed and baseline selected. Unrelated cases, control history and Git commits preserved.")
