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
from control.logic import attach, packet, triage
from control.models import Change
from control.policy import route
from control.runner import RUNTIME_DB, RUNS, backup, serve, stop
from control.worker import handle

TASKS = {
    "copy": "Queue label typo: Refund requets should read Refund requests.",
    "bug": "Crash on case RF-LEGACY-NULL: null note causes trim browser TypeError; preserve row.",
    "feature": "Add Assigned to me queue filter, then Unassigned; preserve the status filter.",
}
TASK_VERSION = "delivery-v1"
CONFIG_VERSION = "fixture-v2"


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
            trial_report = f"{report}\nEval fixture case: {name}-{number}-{time.time_ns()}"
            change = Change.objects.create(reporter=reporter, report=trial_report, source="eval fixture",
                                           mode="sample", safe_context={"trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION})
            result = {"task": name, "trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION,
                      "mode": "sample (NOT Devin performance)", "base": base, "run_id": change.run_id,
                      "human_intervention": "fixture authored locally", "usage_cost": "unavailable"}
            try:
                triage(change)
                if change.status == "duplicate" or change.type != name:
                    raise ValueError(f"Trial triage was not independent: {change.status}/{change.type}")
                change.base = base
                change.packet = packet(change)
                change.save()
                if name == "bug":
                    baseline_db = RUNS / "data" / f"eval-baseline-{change.run_id}.sqlite3"
                    backup(RUNTIME_DB, baseline_db)
                    baseline_pid, baseline_url = serve(base, baseline_db, "eval", 8600 + change.pk,
                                            f"eval-baseline-{change.run_id[:12]}")
                    change.safe_context["baseline_pid"] = baseline_pid
                    change.save()
                    os.environ["FINCORP_RUNTIME_URL"] = baseline_url
                head = candidate(change)
                attach(change, head)
                checks = change.jobs.filter(kind="checks").last()
                handle(checks)
                checks.status = "done"
                checks.save()
                change.refresh_from_db()
                if name == "feature":
                    from control.models import Review
                    reviewer = get_user_model().objects.get(username="toolsadmin")
                    Review.objects.create(change=change, actor=reviewer, kind="changes", message="Include Unassigned, keep status.",
                                          response="Sample fixture revision", delivery="sample", base=base, head=head)
                    head = candidate(change, revision=True)
                    attach(change, head)
                    revised_checks = change.jobs.filter(kind="checks").last()
                    handle(revised_checks)
                    revised_checks.status = "done"
                    revised_checks.save()
                    change.refresh_from_db()
                result.update(head=head, checks=change.check_result, risk=change.risk,
                              output=change.check_output[-1000:], preview=change.preview_url,
                              outcome="preview verified" if change.check_result == "passed" else "failed",
                              merge_release="not assessed by eval replay")
            except Exception as exc:
                result.update(outcome="failed", error=f"{type(exc).__name__}: {exc}", head=change.head)
            finally:
                os.environ.pop("FINCORP_RUNTIME_URL", None)
                change.jobs.filter(status="pending").update(status="skipped")
                stop(change.preview_pid)
                change.preview_url = ""
                change.preview_pid = None
                change.save()
                if name == "bug":
                    stop(change.safe_context.get("baseline_pid"))
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
            trial_report = f"{report}\nLive evaluation case: {name}-{number}-{time.time_ns()}"
            change = Change.objects.create(reporter=reporter, report=trial_report, source="live eval", mode="live",
                                           safe_context={"trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION})
            triage(change)
            if change.status == "duplicate" or change.type != name:
                raise SystemExit(f"Trial triage was not independent: {change.status}/{change.type}")
            append({"task": name, "trial": number, "task_version": TASK_VERSION, "config_version": CONFIG_VERSION,
                    "mode": "live", "run_id": change.run_id, "base": change.base, "head": None,
                    "outcome": "pending real session and independent delivery checks", "usage_cost": "unavailable"})
    print("Nine pending live jobs enqueued; start worker. Pending is not delivery success. Attach real candidate commits and review each result.")


def report():
    rows = []
    for change in Change.objects.filter(source__in=["live eval", "eval fixture"]).order_by("id"):
        delivered = bool(change.mode == "live" and change.session_id and change.status == "released"
                         and change.released_commit and change.check_result == "passed"
                         and change.checked_head == change.head)
        rows.append({
            "run_id": change.run_id, "task_version": change.safe_context.get("task_version"),
            "config_version": change.safe_context.get("config_version", "fixture-v1"),
            "trial": change.safe_context.get("trial"), "mode": change.mode,
            "base": change.base, "head": change.head or None,
            "status": change.status, "check": change.check_result,
            "merged_commit": change.merged_commit or None, "released_commit": change.released_commit or None,
            "session_id": change.session_id or None,
            "delivery_success": delivered if change.mode == "live" else "not scored (sample replay)",
            "human_intervention": change.reviews.count(), "review_rework": change.reviews.filter(kind="changes").count(),
            "elapsed_seconds": round((change.updated_at - change.created_at).total_seconds(), 3),
            "usage_cost": str(change.usage_cost) if change.usage_cost is not None else "unavailable",
            "acus_consumed": change.acus_consumed if change.acus_consumed is not None else "unavailable",
        })
    folder = ROOT / "artifacts"
    folder.mkdir(exist_ok=True)
    (folder / "eval-status.json").write_text(json.dumps(rows, indent=2))
    print(f"Wrote {len(rows)} actual persisted trial states to artifacts/eval-status.json")


def stop_old_evals():
    from control.runner import stop
    for change in Change.objects.filter(source="eval fixture"):
        if change.preview_pid:
            stop(change.preview_pid)
            change.preview_pid = None
            change.preview_url = ""
            change.save()
        pid = change.safe_context.get("baseline_pid")
        if not pid and "crash" in change.report.lower():
            # Old locally spawned trial runners predate persisted PID tracking.
            found = subprocess.run(["lsof", "-tiTCP:" + str(8600 + change.pk), "-sTCP:LISTEN"],
                                   capture_output=True, text=True)
            if found.returncode == 0 and found.stdout.strip().isdigit():
                pid = int(found.stdout.strip())
                cmd = subprocess.run(["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True).stdout
                if f"127.0.0.1:{8600 + change.pk}" not in cmd or "manage.py runserver" not in cmd:
                    pid = None
        stop(pid)
    print("Stopped only eval fixture preview/baseline servers; trials, evidence, DBs and commits retained.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("sample", "live"))
    parser.add_argument("--trials", type=int, default=3)
    parser.add_argument("--confirm-paid-9", action="store_true")
    parser.add_argument("--report", action="store_true", help="Export persisted outcomes without launching sessions")
    parser.add_argument("--stop-eval-previews", action="store_true", help="Stop local eval servers, retain trials")
    args = parser.parse_args()
    if args.stop_eval_previews:
        stop_old_evals()
        sys.exit(0)
    if args.report:
        report()
        sys.exit(0)
    if not args.mode:
        parser.error("--mode is required unless --report is set")
    if args.trials != 3:
        parser.error("Use exactly three fresh trials per delivery case.")
    sample(args.trials) if args.mode == "sample" else live(args.trials, args.confirm_paid_9)
