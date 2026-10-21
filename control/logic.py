import json
import os
import re
from pathlib import Path
from django.conf import settings
from django.db import transaction
from .customer_demo import identify
from .models import Change, Event, Job, Review
from .policy import git
from .provider import mode


def event(change, stage, detail, actor="controller", source="workflow", key=None, evidence=""):
    item, _ = Event.objects.get_or_create(key=key, defaults={
        "change": change, "actor": actor, "source": source, "stage": stage,
        "detail": str(detail)[:6000], "evidence": evidence[:250],
    }) if key else (Event.objects.create(
        change=change, actor=actor, source=source, stage=stage,
        detail=str(detail)[:6000], evidence=evidence[:250],
    ), True)
    return item


def job(change, kind, revision=""):
    return Job.objects.get_or_create(
        key=f"{change.run_id}:{kind}:{revision}", defaults={"change": change, "kind": kind},
    )[0]


def triage(change):
    text = change.report.lower()
    existing = Change.objects.filter(report__iexact=change.report.strip()).exclude(pk=change.pk).exclude(status="duplicate").first()
    if existing:
        change.duplicate_of = existing
        change.status = "duplicate"
        change.triage = f"Duplicate exact report; linked to change #{existing.pk}. No new repair run."
        change.save()
        event(change, "triage", change.triage)
        return
    if len(change.report.strip()) < 16 or text.strip() in ("it is broken", "please fix it", "doesn't work"):
        change.status = "needs_info"
        change.triage = "What happened, where did it happen, and what result do you expect?"
        change.save()
        event(change, "triage", "Needs information from reporter; no agent job created.")
        return
    sensitive = any(term in text for term in ("approval permission", "weaken approval", "skip approval", "remove approval", "bypass approval"))
    scenario = "" if sensitive else identify(change)
    if sensitive:
        change.type, change.risk, change.owner = "sensitive", "owner", "Refund policy owner + tools admin"
        change.urgency = "high"
        change.acceptance = "Policy owner specifies authority; independent permission and audit checks remain in force."
    elif scenario == "case_link":
        change.safe_context = {**change.safe_context, "sample_scenario": scenario}
        change.type = "bug"
        change.acceptance = "On RF-1009, Copy case link copies the actual case URL and confirms success without changing refund state."
    elif scenario == "queue_intro":
        change.safe_context = {**change.safe_context, "sample_scenario": scenario}
        change.type = "copy"
        change.acceptance = "Correct only the existing queue description string and preserve HTML escaping."
    elif "typo" in text or "label" in text:
        change.type = "copy"
        change.acceptance = "Correct the reported display string without changing routes, logic, or escaping."
    elif "crash" in text or "error" in text or "null" in text:
        change.type = "bug"
        change.urgency = "high"
        change.acceptance = "Reproduce the real error, keep the legacy row, and pass a browser regression check."
    elif "spec" in text:
        change.type = "spec"
        change.acceptance = "Implement the described behavior with independent browser and permission checks."
    else:
        change.type = "feature"
        change.acceptance = "Deliver the requested behavior without weakening status filters or refund permissions."
    change.status = "queued"
    change.triage = f"{change.get_type_display()}; {change.urgency} urgency. Owner: {change.owner}. Verify: {change.acceptance}"
    change.base = git("rev-parse", "HEAD")
    change.packet = packet(change)
    change.save()
    event(change, "triage", change.triage + f" Base {change.base}; mode {change.mode}.")
    if scenario:
        event(change, "sample task queued", f"Recorded fixture task {scenario}; no Devin session or generated patch.", source="fixture")
        job(change, "sample_fixture")
    elif change.mode == "live":
        job(change, "launch")


def packet(change):
    related = list(change.incidents.values("route", "case_reference", "deployed_commit", "message", "stack", "log_excerpt", "correlation_id"))
    context = {
        "run_id": change.run_id, "repository": os.getenv("FINCORP_REPO_URL", "NO AUTHORIZED REMOTE REPOSITORY CONFIGURED"),
        "base": change.base, "report": change.report, "route": change.route,
        "case_reference": change.case_reference, "source_commit": change.source_commit,
        "safe_context": change.safe_context, "triage": change.triage,
        "acceptance": change.acceptance, "permitted_scope": "refunds/ only; propose any broader change for owner review",
        "evidence": related, "setup": "See README: uv pip install -r requirements.txt; FINCORP_ROLE=refunds python manage.py migrate; python manage.py test refunds; python trusted_checks/browser.py URL",
        "data": "Synthetic demo users and payment PAY-LEGACY-DEMO; seed RF-LEGACY-NULL with note=NULL to reproduce incident.",
    }
    # JSON string and neutralized angle brackets stop report text escaping the data envelope.
    data = json.dumps(context, indent=2, ensure_ascii=True).replace("<", "\\u003c").replace(">", "\\u003e")
    return (settings.BASE_DIR / "prompts/change-v1.txt").read_text().format(packet=data)


def followup(review):
    template = (settings.BASE_DIR / "prompts/feedback-v1.txt").read_text()
    return template.format(feedback=json.dumps(review.message).replace("<", "\\u003c"), context=review.change.packet)


def invalidate(change):
    change.checked_base = change.checked_head = change.approved_base = change.approved_head = ""
    change.check_result = "pending"
    change.check_output = ""
    change.preview_url = ""
    change.preview_pid = None
    change.preview_db = ""
    change.merged_commit = change.released_commit = ""


def attach(change, head, session_id="", session_url=""):
    from .policy import validate_head
    from .runner import stop
    validate_head(change.base, head)
    old = change.head
    if old and old != head:
        stop(change.preview_pid)
    change.head = head
    if session_id:
        if not re.fullmatch(r"devin-[A-Za-z0-9_-]+", session_id):
            raise ValueError("Session ID must start with devin-.")
        change.session_id = session_id
    if session_url:
        if not re.fullmatch(r"https://(?:app\.)?devin\.ai/[^\s]+", session_url):
            raise ValueError("Expected an actual devin.ai session URL.")
        change.session_url = session_url
    invalidate(change)
    change.status = "working"
    change.save()
    event(change, "candidate", f"Attached local candidate {head}; previous {old or 'none'}. Evidence must be checked independently.")
    job(change, "checks", head)


def can_merge(change):
    if change.status not in ("ready",):
        return False, "Work is not ready for review."
    if not change.head or change.check_result != "passed" or change.checked_head != change.head or change.checked_base != change.base:
        return False, "Checks are missing, failed or stale."
    if change.reviews.filter(delivery__in=["pending", "failed"]).exists() or change.reviews.filter(response="").exists():
        return False, "Reviewer feedback has not been answered and delivered."
    if change.risk != "auto" and (change.approved_base != change.base or change.approved_head != change.head):
        return False, "Approval is missing or stale."
    if change.risk == "owner" and not change.reviews.filter(kind="owner", base=change.base, head=change.head, delivery="sent").exists():
        return False, "Relevant policy owner has not attested to this exact revision."
    if git("rev-parse", "HEAD") != change.base:
        return False, "Base revision is stale; refresh candidate and checks."
    return True, ""
