#!/usr/bin/env python3
"""Explicit eval launcher; replay outcomes are never Devin-performance claims."""
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
os.environ["FINCORP_ROLE"] = "control"
import django
django.setup()
from django.contrib.auth import get_user_model
from control.fixtures import candidate
from control.logic import attach, job, triage
from control.models import Change
from control.policy import route
from control.runner import PYTHON, preview
from control.worker import handle

TASKS = {
    "copy": "Queue label typo: Refund requets should read Refund requests.",
    "bug": "Crash on case RF-LEGACY-NULL: null note causes trim browser TypeError; preserve row.",
    "feature": "Add Assigned to me queue filter, then Unassigned; preserve status filter and approval permissions.",
}
TASK_VERSION = "delivery-v1"
CONFIG_VERSION = "fixture-v1"


def append(row):
    folder = ROOT / "artifacts"
    folder.mkdir(exist_ok=True)
    with (folder / "evals.jsonl").open("a") as out:
        out.write(json.dumps(row, sort_keys=True) + "\n")


def sample(trials):
    baseline = ROOT / ".runs/baseline.json"
    if not baseline.exists():
        raise SystemExit("No baseline.json; follow README setup first.")
    base = json.loads(baseline.read_text())["commit"]
    reporter = get_user_model().objects.get(username="ops")
    for name, report in TASKS.items():
        for number in range(1, trials + 1):
            started = time.monotonic()
            change = Change.objects.create(reporter=reporter, report=report, source="eval fixture",
                                           mode="sample", safe_context={"trial": number, "task_version": TASK_VERSION})
            result = {"task": name, "trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION,
                      "mode": "sample (NOT Devin performance)", "base": base, "run_id": change.run_id,
                      "human_intervention": "fixture authored locally", "usage_cost": "unavailable"}
            try:
                triage(change)
                change.base = base
                change.save()
                head = candidate(change)
                attach(change, head)
                checks = change.jobs.filter(kind="checks").last()
                handle(checks)
                change.refresh_from_db()
                if name == "feature":
                    from control.models import Review
                    reviewer = get_user_model().objects.get(username="toolsadmin")
                    Review.objects.create(change=change, actor=reviewer, kind="changes", message="Include Unassigned, keep status.",
                                          response="Sample fixture revision", delivery="sample", base=base, head=head)
                    head = candidate(change, revision=True)
                    attach(change, head)
                    handle(change.jobs.filter(kind="checks").last())
                    change.refresh_from_db()
                result.update(head=head, checks=change.check_result, risk=change.risk,
                              output=change.check_output[-1000:], preview=change.preview_url,
                              outcome="preview verified" if change.check_result == "passed" else "failed",
                              merge_release="not assessed by eval replay")
            except Exception as exc:
                result.update(outcome="failed", error=f"{type(exc).__name__}: {exc}", head=change.head)
            result["elapsed_seconds"] = round(time.monotonic() - started, 3)
            append(result)
            print(f"{name} trial {number}: {result['outcome']} (fixture, no Devin session)")


def live(trials, confirmation):
    if not confirmation or trials != 3:
        raise SystemExit("Live mode requires exactly --trials 3 --confirm-paid-9; never auto-start paid batches.")
    if not all(os.getenv(k) for k in ("DEVIN_ORG_ID", "DEVIN_API_KEY", "FINCORP_REPO_NAME", "FINCORP_REPO_URL")):
        raise SystemExit("Missing scoped Devin service user or authorized fetchable remote repository.")
    if os.getenv("FINCORP_MODE") != "live":
        raise SystemExit("Set FINCORP_MODE=live explicitly before starting live eval.")
    reporter = get_user_model().objects.get(username="ops")
    for name, report in TASKS.items():
        for number in range(1, trials + 1):
            change = Change.objects.create(reporter=reporter, report=report, source="live eval", mode="live",
                                           safe_context={"trial": number, "task_version": TASK_VERSION})
            triage(change)
            append({"task": name, "trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION,
                    "mode": "live", "run_id": change.run_id, "base": change.base, "head": None,
                    "outcome": "pending real session and independent delivery checks", "usage_cost": "unavailable"})
    print("Nine pending live jobs enqueued; start worker. Pending is not delivery success. Attach real candidate commits and review each result.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sample", "live"), required=True)
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--confirm-paid-9", action="store_true")
    args = parser.parse_args()
    if args.trials != 3:
        parser.error("Use exactly three fresh trials per delivery case.")
    sample(args.trials) if args.mode == "sample" else live(args.trials, args.confirm_paid_9)
