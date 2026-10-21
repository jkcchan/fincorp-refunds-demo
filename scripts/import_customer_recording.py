#!/usr/bin/env python3
"""Display one verified prior sample release without selecting it as the runtime."""
import json
import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
os.environ["FINCORP_ROLE"] = "control"

if ROOT.name != "customer-demo" or os.getenv("FINCORP_MODE") != "sample" or os.getenv("FINCORP_CUSTOMER_DEMO") != "1":
    raise SystemExit("Run only in the prepared customer-demo checkout in sample mode.")

import django
django.setup()
from django.contrib.auth import get_user_model
from django.db import transaction
from control.models import Change, Event, Job
from control.policy import git, route
from control.runner import RUNS, RUNTIME_DB, backup, probe, serve

source = ROOT.parent / "customer-rehearsal" / "control.sqlite3"
if not source.exists():
    raise SystemExit(f"No prior rehearsal record at {source}.")
with sqlite3.connect(source.as_uri() + "?mode=ro", uri=True) as db:
    db.row_factory = sqlite3.Row
    original = db.execute("SELECT * FROM control_change WHERE id = 2").fetchone()
    if original is None:
        raise SystemExit("No prior automatic change #2.")
    username = db.execute("SELECT username FROM auth_user WHERE id = ?", (original["reporter_id"],)).fetchone()["username"]
    events = db.execute("SELECT * FROM control_event WHERE change_id = 2 ORDER BY id").fetchall()
    jobs = db.execute("SELECT * FROM control_job WHERE change_id = 2 ORDER BY id").fetchall()

if (original["mode"], original["status"], original["risk"], original["check_result"], original["session_id"]) != (
    "sample", "released", "auto", "passed", "",
):
    raise SystemExit("The source is not a completed, session-free automatic sample change.")
base, head, merged = original["base"], original["head"], original["released_commit"]
if route(base, head)[0] != "auto" or merged != original["merged_commit"] or git("merge-base", head, merged) != head:
    raise SystemExit("Source revisions do not prove the recorded copy-only merge.")
stages = {item["stage"] for item in events}
if not {"baseline reproduction", "independent checks", "merged", "released"} <= stages or "software approval" in stages:
    raise SystemExit("Source trace lacks independent checks or automatic release evidence.")

with transaction.atomic():
    change = Change.objects.filter(run_id=original["run_id"]).first()
    if change and change.source != "recorded sample":
        raise SystemExit("Run ID already belongs to another work item.")
    if change is None:
        context = json.loads(original["safe_context"])
        context["recorded_from"] = "prior isolated customer rehearsal"
        change = Change.objects.create(
            reporter=get_user_model().objects.get(username=username),
            source="recorded sample", mode="sample", report=original["report"],
            route=original["route"], case_reference=original["case_reference"],
            source_commit=original["source_commit"], safe_context=context,
            type=original["type"], urgency=original["urgency"], triage=original["triage"],
            acceptance=original["acceptance"], owner=original["owner"],
            status="released", risk="auto", base=base, head=head,
            checked_base=original["checked_base"], checked_head=original["checked_head"],
            check_result="passed", check_output=original["check_output"],
            run_id=original["run_id"], packet=original["packet"],
            merged_commit=merged, released_commit=merged,
        )
        Change.objects.filter(pk=change.pk).update(
            created_at=original["created_at"], updated_at=original["updated_at"],
        )
        for item in events:
            evidence = item["evidence"]
            if evidence == "/changes/2/":
                evidence = f"/changes/{change.pk}/"
            record = Event.objects.create(
                change=change, actor=item["actor"], source=item["source"],
                stage=item["stage"], detail=item["detail"], evidence=evidence,
                key=f"recorded:{change.run_id}:{item['id']}",
            )
            Event.objects.filter(pk=record.pk).update(created_at=item["created_at"])
        for item in jobs:
            record = Job.objects.create(
                change=change, kind=item["kind"], status=item["status"],
                attempts=item["attempts"], key=f"recorded:{item['key']}",
                last_error=item["last_error"],
            )
            Job.objects.filter(pk=record.pk).update(updated_at=item["updated_at"])
        Event.objects.create(
            change=change, stage="recording imported", actor="controller", source="local recording",
            detail=f"Prior-cycle sample release {merged}; current refunds runtime remains at {git('rev-parse', 'HEAD')}. No Devin session.",
            key=f"recorded:{change.run_id}:import",
        )

db = RUNS / "data" / f"recorded-copy-{change.run_id[:12]}.sqlite3"
backup(RUNTIME_DB, db)
port = 8352
url = f"http://127.0.0.1:{port}"
if not probe(url, head):
    pid, url = serve(head, db, "preview", port, "recorded-copy-" + head[:12])
    change.preview_pid = pid
change.preview_url = url
change.save(update_fields=["preview_url", "preview_pid"])
print(f"Read-only prior-cycle change #{change.pk} visible at /changes/{change.pk}/; preview {url}. Active runtime was not changed.")
