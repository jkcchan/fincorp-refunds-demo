import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from .logic import attach, can_merge, event, followup, invalidate, job, packet, triage
from .models import Change, Review
from .policy import git
from .provider import ProviderError, mode


@login_required
def changes(request):
    status = request.GET.get("status", "")
    items = Change.objects.select_related("reporter", "duplicate_of")
    show_evals = request.GET.get("show_evals") == "1"
    if not show_evals:
        items = items.exclude(source="eval fixture")
    if status in dict(Change.STATUSES):
        items = items.filter(status=status)
    return render(request, "control/list.html", {"items": items, "status": status, "statuses": Change.STATUSES, "show_evals": show_evals})


@login_required
def new(request):
    route = urlsplit(request.GET.get("route", "")).path[:250]
    case = request.GET.get("case", "")[:32]
    if not re.fullmatch(r"RF-[A-Z0-9-]+", case):
        case = ""
    if request.method == "POST":
        text = request.POST.get("report", "").strip()
        if len(text) < 4 or len(text) > 12000:
            messages.error(request, "Please enter a request between 4 and 12,000 characters.")
        else:
            # The commit is server-owned runtime state, not supplied by the report.
            state = settings.BASE_DIR / ".runs/runtime.json"
            source_commit = json.loads(state.read_text()).get("commit", "") if state.exists() else git("rev-parse", "HEAD")
            change = Change.objects.create(
                reporter=request.user, report=text, source=request.POST.get("source") if request.POST.get("source") in ("report", "team spec") else "report",
                route=urlsplit(request.POST.get("route", "")).path[:250],
                case_reference=case if case else (request.POST.get("case", "")[:32] if re.fullmatch(r"RF-[A-Z0-9-]+", request.POST.get("case", "")) else ""),
                source_commit=source_commit, mode=mode(),
                safe_context={"environment": "runtime", "route": urlsplit(request.POST.get("route", "")).path[:250]},
            )
            event(change, "intake", f"Report from {request.user.username}; source commit {source_commit}", actor=request.user.username, source="report")
            triage(change)
            return redirect("control:detail", pk=change.pk)
    return render(request, "control/new.html", {"route": route, "case": case})


@login_required
def detail(request, pk):
    change = get_object_or_404(Change.objects.select_related("reporter", "duplicate_of"), pk=pk)
    recording = change.source == "recorded sample"
    scenario = change.safe_context.get("sample_scenario") if change.mode == "sample" else None
    original = os.getenv("FINCORP_ORIGINAL_URL", "") if scenario else ""
    before_url = ""
    if original:
        path = f"/cases/{change.case_reference}/" if scenario == "case_link" else "/"
        before_url = original.rstrip("/") + path
    diff = ""
    if change.base and change.head:
        try:
            diff = git("diff", "--no-ext-diff", change.base, change.head)[:35000]
        except Exception as exc:
            diff = f"Diff unavailable: {exc}"
    admin = request.user.has_perm("control.review_change")
    return render(request, "control/detail.html", {
        "change": change, "diff": diff, "admin": admin,
        "recording": recording,
        "policy_owner": request.user.groups.filter(name="Refund policy owners").exists(),
        "events": change.events.all(), "incidents": change.incidents.all() if admin else [],
        "reviews": change.reviews.select_related("actor"),
        "merge_gate": ("Prior-cycle result; not the current release gate." if recording else can_merge(change)[1]) if change.head else "No candidate attached.",
        "followups": [(r, followup(r)) for r in change.reviews.filter(delivery__in=["pending", "failed", "uncertain"])] if admin else [],
        "before_url": before_url,
    })


@require_POST
@login_required
def answer(request, pk):
    change = get_object_or_404(Change, pk=pk)
    if change.reporter_id != request.user.id or change.status != "needs_info":
        raise PermissionDenied
    reply = request.POST.get("answer", "").strip()
    if len(reply) < 16:
        messages.error(request, "Please include where this happens and the expected result.")
    else:
        change.report += "\nReporter clarification: " + reply[:4000]
        change.save()
        event(change, "clarification", reply[:4000], actor=request.user.username, source="report")
        triage(change)
    return redirect("control:detail", pk=pk)


@require_POST
@login_required
def action(request, pk):
    if not request.user.has_perm("control.review_change") and not (
        request.POST.get("action") == "owner_attest" and request.user.groups.filter(name="Refund policy owners").exists()
    ):
        raise PermissionDenied
    change = get_object_or_404(Change, pk=pk)
    if change.source == "recorded sample":
        raise PermissionDenied("A prior-run recording cannot be changed.")
    action_name = request.POST.get("action")
    try:
        if action_name == "attach":
            attach(change, request.POST.get("head", "").strip(), request.POST.get("session_id", "").strip(), request.POST.get("session_url", "").strip())
        elif action_name == "reconcile_session":
            if change.mode != "live" or not change.create_uncertain:
                raise ValueError("No uncertain live creation to reconcile.")
            session_id = request.POST.get("session_id", "").strip()
            if not re.fullmatch(r"devin-[A-Za-z0-9_-]+", session_id):
                raise ValueError("Enter the actual Devin session ID from Cloud.")
            from .provider import Devin
            actual = Devin().status(session_id)
            if actual.get("session_id") != session_id or actual.get("title") != f"FinCorp change #{change.pk}" or "fincorp-" + change.run_id not in actual.get("tags", []):
                raise ValueError("Session does not match this work item's title and run tag.")
            change.session_id = session_id
            change.session_url = actual.get("url", "")
            change.provider_status = actual.get("status", "")
            change.create_uncertain = False
            change.status = "working"
            change.save()
            event(change, "session reconciled", f"Verified existing Devin session {session_id}; no duplicate create.", actor=request.user.username, source="devin")
        elif action_name == "reconcile_feedback":
            from .provider import Devin
            review = get_object_or_404(Review, pk=request.POST.get("review_id"), change=change)
            if change.mode != "live" or review.delivery != "uncertain" or not change.session_id:
                raise ValueError("No ambiguous live feedback delivery to reconcile.")
            api = Devin()
            cursor = ""
            found = False
            for _ in range(20):
                messages_page = api.messages(change.session_id, cursor)
                found = any(m.get("message") == followup(review) and m.get("source") != "devin" for m in messages_page.get("items", []))
                if found or not messages_page.get("has_next_page"):
                    break
                cursor = messages_page.get("end_cursor", "")
                if not cursor:
                    break
            if not found:
                raise ValueError("No matching sent message was verified. Leave delivery uncertain; do not blindly resend.")
            from django.utils import timezone
            review.delivery = "sent"
            review.sent_at = timezone.now()
            review.save()
            event(change, "feedback reconciled", f"Confirmed matching message for review {review.pk} in actual session.", actor=request.user.username, source="devin")
        elif action_name == "fixture":
            if change.mode != "sample" or change.status in ("needs_info", "duplicate", "released"):
                raise ValueError("Fixtures require an active sample-replay item.")
            if not change.head and change.base != git("rev-parse", "HEAD"):
                previous = change.base
                change.base = git("rev-parse", "HEAD")
                change.packet = packet(change)
                change.save()
                event(change, "base refreshed", f"Rebased pending fixture from {previous} onto {change.base}; original deployed commit retained.")
            from .fixtures import candidate
            head = candidate(change, revision=request.POST.get("revision") == "1")
            attach(change, head)
            event(change, "sample replay", f"Fixture commit {head}; NOT produced by a Devin session.", source="fixture")
        elif action_name == "refresh_base":
            if change.status in ("merged", "released", "duplicate"):
                raise ValueError("Only unmerged work can refresh its base.")
            previous = change.base
            if change.preview_pid:
                from .runner import stop
                stop(change.preview_pid)
            change.base = git("rev-parse", "HEAD")
            change.head = ""
            invalidate(change)
            change.packet = packet(change)
            change.status = "queued"
            change.save()
            event(change, "base refreshed", f"{previous} -> {change.base}; original deployed revision remains in intake. New candidate and checks required.")
        elif action_name in ("question", "changes"):
            content = request.POST.get("message", "").strip()
            if not content:
                raise ValueError("Enter a review message.")
            review = Review.objects.create(
                change=change, actor=request.user, kind=action_name, message=content[:4000],
                base=change.base, head=change.head,
            )
            if action_name == "changes":
                change.status = "changes"
                change.approved_base = change.approved_head = ""
                change.save()
            event(change, "review", f"{action_name}: {content}", actor=request.user.username, source="review")
            if change.mode == "live":
                job(change, "feedback", str(review.pk))
        elif action_name == "owner_attest":
            if not request.user.groups.filter(name="Refund policy owners").exists() or change.risk != "owner" or change.check_result != "passed" or change.checked_head != change.head:
                raise ValueError("Only the policy owner can attest after checks on this revision.")
            Review.objects.create(change=change, actor=request.user, kind="owner",
                                  message="Policy-owner review of candidate diff and tested preview.",
                                  delivery="sent", response="Owner attested to this exact base and head.",
                                  base=change.base, head=change.head)
            event(change, "owner attestation", f"Policy owner reviewed {change.head}.", actor=request.user.username, source="review")
        elif action_name == "feedback_response":
            review = get_object_or_404(Review, pk=request.POST.get("review_id"), change=change)
            if change.mode == "live":
                raise ValueError("Live responses must come from the real session.")
            response = request.POST.get("response", "").strip()
            if not response:
                raise ValueError("Enter the actual copied reply, or mark a sample reply as replay.")
            review.response = response[:4000]
            review.delivery = "sample" if change.mode == "sample" else "sent"
            review.save()
            event(change, "feedback reply", review.response, actor="sample fixture" if change.mode == "sample" else request.user.username, source=change.mode)
        elif action_name == "approve":
            if change.risk == "auto":
                raise ValueError("Copy-only candidates are automatically routed after checks.")
            # Check everything except the as-yet-unrecorded approval.
            previous = (change.approved_base, change.approved_head)
            change.approved_base, change.approved_head = change.base, change.head
            original_status = change.status
            change.status = "ready"
            allowed, reason = can_merge(change)
            if not allowed:
                change.approved_base, change.approved_head = previous
                change.status = original_status
                raise ValueError(reason)
            change.save()
            event(change, "software approval", f"Tools-admin approved {change.head} on {change.base}. No refund decision changed.", actor=request.user.username, source="review")
            job(change, "merge", change.head)
        elif action_name == "retry":
            if change.head:
                job(change, "checks", change.head + "-retry-" + str(change.events.count()))
        elif action_name == "retry_release":
            if change.status != "merged" or not change.merged_commit or change.released_commit:
                raise ValueError("Only a verified, unreleased merge can retry release.")
            job(change, "release", change.merged_commit + "-retry-" + str(change.events.count()))
            event(change, "release retry", f"Retrying verified merge {change.merged_commit}.", actor=request.user.username, source="review")
        else:
            raise ValueError("Unknown action.")
        messages.success(request, "Change updated.")
    except (ValueError, OSError, ProviderError) as exc:
        messages.error(request, str(exc)[:300])
    return redirect("control:detail", pk=pk)


@login_required
def events(request, pk):
    change = get_object_or_404(Change, pk=pk)
    return JsonResponse({"status": change.status, "events": change.events.count(), "check": change.check_result})
