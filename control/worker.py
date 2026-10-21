import os
import sqlite3
import subprocess
import time
from pathlib import Path
from django.conf import settings
from django.db import IntegrityError
from .logic import event, job, packet, triage
from .models import Change, Event, Incident, Job, Review
from .policy import route
from .provider import Devin, ProviderError, mode
from .runner import PYTHON, ROOT, RUNTIME_DB, merge, preview, release, runtime_state


def ingest(db_path, environment, change=None):
    if not Path(db_path).exists():
        return
    with sqlite3.connect(str(db_path), timeout=3) as db:
        db.row_factory = sqlite3.Row
        try:
            rows = db.execute("SELECT * FROM refunds_runtimeerror ORDER BY id DESC LIMIT 100").fetchall()
        except sqlite3.OperationalError:
            return
    for row in reversed(rows):
        fingerprint = row["fingerprint"]
        commit = row["deployed_commit"]
        if environment != "runtime":
            if change and row["environment"] == "preview" and commit == change.head:
                event(change, "preview error", f"{row['message']} on {row['route']} (no repair enqueue)", source="preview",
                      key=f"preview:{change.run_id}:{row['id']}")
            continue
        if row["environment"] != "runtime":
            continue
        if commit != runtime_state()["commit"]:
            continue
        if Incident.objects.filter(fingerprint=fingerprint, environment="runtime", deployed_commit=commit).exists():
            continue
        ongoing = Incident.objects.filter(fingerprint=fingerprint, environment="runtime").exclude(change__status="released").first()
        if ongoing:
            event(ongoing.change, "recurrence", f"Same captured failure observed at {commit}; linked to existing investigation.",
                  source="telemetry", key=f"recurrence:{ongoing.change.run_id}:{commit}")
            continue
        report = f"Captured browser crash: {row['message']} on {row['route']}. Preserve the synthetic legacy row, reproduce the browser stack, and fix the failure."
        first = Change.objects.create(
            reporter_id=1, report=report, mode=mode(), source="captured error",
            route=row["route"], case_reference=row["case_reference"],
            source_commit=commit, safe_context={"environment": "runtime", "correlation_id": row["correlation_id"]},
        )
        try:
            Incident.objects.create(
                change=first, fingerprint=fingerprint, environment="runtime",
                correlation_id=row["correlation_id"], route=row["route"], case_reference=row["case_reference"],
                deployed_commit=commit, message=row["message"], stack=row["stack"], log_excerpt=row["log_excerpt"],
            )
        except IntegrityError:
            first.delete()
            continue
        triage(first)
        first.packet = packet(first)
        first.save()
        event(first, "captured exception", f"Actual {row['source']} error {row['message']} correlation {row['correlation_id']}.",
              source="telemetry", evidence=f"/changes/{first.pk}/")


def poll_sessions():
    if mode() != "live":
        return
    provider = Devin()
    for change in Change.objects.exclude(session_id="").exclude(status__in=["released", "duplicate"]):
        try:
            status = provider.status(change.session_id)
            value = status.get("status", "")
            if value != change.provider_status:
                change.provider_status = value
                change.save()
                event(change, "agent status", value, source="devin")
            # Cursor + unique event ID make repeated polls idempotent across restarts.
            for _ in range(10):
                result = provider.messages(change.session_id, change.provider_cursor)
                for message in result.get("items", []):
                    msg_id = str(message.get("event_id", ""))
                    if not msg_id:
                        continue
                    _, created = Event.objects.get_or_create(
                        key=f"devin:{change.session_id}:{msg_id}", defaults={
                            "change": change, "actor": str(message.get("source", "devin"))[:80],
                            "source": "devin", "stage": "session message",
                            "detail": str(message.get("message", ""))[:6000],
                        })
                    if created and message.get("source") == "devin":
                        unanswered = change.reviews.filter(delivery="sent", response="").first()
                        if unanswered:
                            unanswered.response = str(message.get("message", ""))[:4000]
                            unanswered.save()
                change.provider_cursor = result.get("end_cursor") or change.provider_cursor
                change.save()
                if not result.get("has_next_page"):
                    break
        except ProviderError as exc:
            event(change, "provider error", str(exc), source="devin")


def handle(item):
    change = Change.objects.get(pk=item.change_id)
    if item.kind == "launch":
        if change.session_id or change.create_uncertain:
            raise ValueError("Creation already attempted or uncertain. Reconcile actual session ID before retrying.")
        repo = os.getenv("FINCORP_REPO_NAME", "")
        if not repo or not os.getenv("FINCORP_REPO_URL", ""):
            raise ValueError("Authorized fetchable repository is not configured; no session created.")
        change.create_uncertain = True
        change.save()
        event(change, "provider request", f"Creating live session for run {change.run_id}; reconciliation required if response is ambiguous.", source="devin")
        provider = Devin()
        template = (ROOT / "prompts/triage-v1.txt").read_text()
        triage_prompt = template.format(report=change.report.replace("<", "\\u003c"), context=change.packet)
        result = provider.create(triage_prompt + "\n\n" + change.packet, f"FinCorp change #{change.pk}", repo)
        if not result.get("session_id", "").startswith("devin-") or not result.get("url", "").startswith("https://"):
            raise ValueError("Ambiguous create response; reconcile before retry.")
        change.session_id = result["session_id"]
        change.session_url = result["url"]
        change.provider_status = result.get("status", "new")
        change.create_uncertain = False
        change.status = "working"
        change.save()
        event(change, "session created", f"Actual session {change.session_id}", source="devin", evidence=change.session_url)
    elif item.kind == "feedback":
        review = Review.objects.get(pk=int(item.key.rsplit(":", 1)[-1]))
        if not change.session_id:
            raise ValueError("No live session; attach a real session or use manual handoff.")
        from .logic import followup
        Devin().send(change.session_id, followup(review))
        review.delivery = "sent"
        review.save()
        event(change, "feedback delivered", f"Sent review {review.pk} to {change.session_id}", source="devin")
    elif item.kind == "checks":
        if not change.head:
            raise ValueError("No candidate.")
        risk, reason = route(change.base, change.head)
        change.risk = risk
        change.check_result = "running"
        change.save()
        event(change, "policy", f"{risk}: {reason}; evaluated actual diff {change.base}..{change.head}")
        if change.type == "bug":
            actual_runtime = os.getenv("FINCORP_RUNTIME_URL", "http://127.0.0.1:8001")
            repro = subprocess.run(
                [str(PYTHON), str(ROOT / "trusted_checks/browser.py"), actual_runtime, "crash-expected"],
                cwd=ROOT, capture_output=True, text=True, timeout=75,
            )
            if repro.returncode:
                raise ValueError("Baseline browser failure was not reproduced: " + (repro.stdout + repro.stderr)[-1000:])
            event(change, "baseline reproduction", repro.stdout[-1000:], source="trusted browser",
                  evidence=f"/changes/{change.pk}/")
        url = preview(change)
        # Browser regression comes from the trusted controller checkout, not the candidate.
        scenario = "bug" if change.type == "bug" else ("feature-revision" if change.type == "feature" and change.reviews.filter(kind="changes").exists() else "feature" if change.type == "feature" else "copy" if change.type == "copy" else "smoke")
        result = subprocess.run([str(PYTHON), str(ROOT / "trusted_checks/browser.py"), url, scenario],
                                cwd=ROOT, capture_output=True, text=True, timeout=80)
        if change.head != Change.objects.get(pk=change.pk).head:
            raise ValueError("Candidate changed while checks ran.")
        change.checked_base = change.base
        change.checked_head = change.head
        change.check_result = "passed" if result.returncode == 0 else "failed"
        change.check_output = (result.stdout + result.stderr)[-6000:]
        change.status = "ready" if result.returncode == 0 else "blocked"
        change.save()
        event(change, "independent checks", f"{change.check_result} on {change.head}: {change.check_output[-1200:]}", source="trusted checks")
        if change.check_result == "passed" and risk == "auto" and not change.reviews.exists():
            job(change, "merge", change.head)
    elif item.kind == "merge":
        if change.merged_commit:
            return
        merged = merge(change)
        change.merged_commit = merged
        change.status = "merged"
        change.save()
        event(change, "merged", f"Local merge verified at {merged}; release is separate.")
        job(change, "release", merged)
    elif item.kind == "release":
        if change.released_commit:
            return
        output = release(change)
        change.released_commit = change.merged_commit
        change.status = "released"
        change.save()
        event(change, "released", f"Actual refunds runtime at {change.released_commit}. {output}")
    else:
        raise ValueError("Unknown job kind.")


def tick():
    ingest(RUNTIME_DB, "runtime")
    for change in Change.objects.exclude(preview_db=""):
        ingest(change.preview_db, "preview", change)
    try:
        poll_sessions()
    except ProviderError:
        pass
    for item in Job.objects.filter(status="pending").order_by("id")[:10]:
        item.status = "running"
        item.attempts += 1
        item.save()
        try:
            handle(item)
            item.status = "done"
            item.last_error = ""
        except Exception as exc:
            item.status = "failed"
            item.last_error = f"{type(exc).__name__}: {exc}"[:900]
            change = Change.objects.get(pk=item.change_id)
            if item.kind in ("checks", "merge", "release"):
                change.status = "blocked" if item.kind != "release" else "merged"
                change.save()
            if item.kind == "feedback":
                Review.objects.filter(pk=int(item.key.rsplit(":", 1)[-1])).update(delivery="failed")
            event(change, "job failed", f"{item.kind}: {item.last_error}", source="worker")
        item.save()
