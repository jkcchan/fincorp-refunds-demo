import hashlib
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q, Sum
from django.http import HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from .forms import AssignForm, CaseForm, NoteForm
from .models import AuditEvent, Case, Payment, RuntimeError
from .services import DecisionError, decide, record, snapshot


def copy_strings():
    return json.loads((Path(__file__).parent / "copy.json").read_text())


@login_required
def queue(request):
    cases = Case.objects.select_related("payment", "assignee")
    query = request.GET.get("q", "").strip()[:100]
    status = request.GET.get("status", "")
    currency = request.GET.get("currency", "")
    if query:
        cases = cases.filter(Q(reference__icontains=query) | Q(payment__reference__icontains=query))
    if status in dict(Case.STATUSES):
        cases = cases.filter(status=status)
    if currency in ("USD", "CAD"):
        cases = cases.filter(payment__currency=currency)
    totals = cases.values("payment__currency").annotate(total=Sum("requested_minor")).order_by("payment__currency")
    return render(request, "refunds/queue.html", {
        "cases": cases, "query": query, "status": status, "currency": currency, "statuses": Case.STATUSES,
        "totals": totals, "copy": copy_strings(),
    })


@login_required
def create_case(request):
    if not request.user.has_perm("refunds.manage_case"):
        raise PermissionDenied
    form = CaseForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            case = Case.objects.create(
                payment=form.cleaned_data["payment"], requested_minor=form.cleaned_data["requested"],
                reason=form.cleaned_data["reason"], note=form.cleaned_data["note"],
                submitter=request.user,
            )
            record(case, request.user, "created", {})
        messages.success(request, "Refund case created.")
        return redirect("refunds:detail", reference=case.reference)
    return render(request, "refunds/new.html", {"form": form})


@login_required
def case_detail(request, reference):
    case = get_object_or_404(Case.objects.select_related("payment", "assignee", "submitter"), reference=reference)
    return render(request, "refunds/case.html", {
        "case": case, "events": case.history.select_related("actor"),
        "assign_form": AssignForm(initial={"assignee": case.assignee}),
        "note_form": NoteForm(), "remaining": case.payment.remaining_minor,
    })


@require_POST
@login_required
def case_action(request, reference):
    case = get_object_or_404(Case, reference=reference)
    action = request.POST.get("action")
    if action in ("approve", "reject"):
        try:
            changed = decide(case.id, request.user, Case.APPROVED if action == "approve" else Case.REJECTED)
            messages.success(request, "Decision recorded (simulated; no money moved)." if changed else "Decision already recorded; no duplicate reservation.")
        except DecisionError as exc:
            messages.error(request, str(exc))
        return redirect("refunds:detail", reference=reference)
    if not request.user.has_perm("refunds.manage_case"):
        raise PermissionDenied
    with transaction.atomic():
        case = Case.objects.select_for_update().get(pk=case.pk)
        before = snapshot(case)
        if action == "assign":
            form = AssignForm(request.POST)
            if not form.is_valid():
                messages.error(request, "Select a valid operations assignee.")
                return redirect("refunds:detail", reference=reference)
            case.assignee = form.cleaned_data["assignee"]
        elif action == "note":
            form = NoteForm(request.POST)
            if not form.is_valid():
                messages.error(request, "A note is required (maximum 2000 characters).")
                return redirect("refunds:detail", reference=reference)
            case.note = ((case.note or "") + "\n" + form.cleaned_data["note"]).strip()
        elif action == "request_info" and case.status in (Case.NEW, Case.REVIEW):
            case.status = Case.INFORMATION
        elif action == "submit" and case.status in (Case.NEW, Case.INFORMATION):
            case.status = Case.REVIEW
        else:
            messages.error(request, "That action is not available for this case.")
            return redirect("refunds:detail", reference=reference)
        case.save()
        record(case, request.user, action, before)
    messages.success(request, "Case updated.")
    return redirect("refunds:detail", reference=reference)


@require_POST
@login_required
def seed_legacy(request):
    if os.getenv("FINCORP_ENVIRONMENT", "runtime") != "runtime" or not request.user.has_perm("refunds.seed_legacy"):
        raise PermissionDenied
    payment = Payment.objects.get(reference="PAY-LEGACY-DEMO")
    case, created = Case.objects.get_or_create(
        reference="RF-LEGACY-NULL", defaults={
            "payment": payment, "requested_minor": 1250, "reason": "Legacy import: missing note",
            "note": None, "submitter": request.user,
        },
    )
    if created:
        record(case, request.user, "demo_seed_legacy", {})
    messages.success(request, "Demo-only legacy row is ready. Open its detail to reproduce the browser error.")
    return redirect("refunds:detail", reference=case.reference)


def sanitize(text):
    text = str(text)[:6000]
    text = re.sub(r"(?i)(bearer|password|cookie|api[_-]?key|secret)[=: ]+[^\\s,;]+", r"\1=[REDACTED]", text)
    return text


@require_POST
@login_required
def telemetry(request):
    if len(request.body) > 16000:
        return HttpResponseBadRequest("Payload too large")
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError
    except (ValueError, UnicodeDecodeError):
        return HttpResponseBadRequest("Invalid event")
    route = urlsplit(str(data.get("route", ""))).path[:250]
    if not route.startswith("/"):
        return HttpResponseBadRequest("Invalid route")
    stack = sanitize(data.get("stack", ""))
    message = sanitize(data.get("message", ""))[:400]
    case_ref = re.fullmatch(r"RF-[A-Z0-9-]{1,24}", str(data.get("case_reference", "")))
    correlation = re.fullmatch(r"[a-f0-9]{32}", str(data.get("correlation_id", "")))
    correlation_id = correlation.group() if correlation else request.correlation_id
    source = os.getenv("FINCORP_ENVIRONMENT", "runtime")
    event = RuntimeError.objects.create(
        fingerprint=hashlib.sha256((route + message + stack[:350]).encode()).hexdigest(),
        correlation_id=correlation_id, source="browser", route=route,
        case_reference=case_ref.group() if case_ref else "",
        deployed_commit=os.getenv("FINCORP_COMMIT", "local-unversioned"),
        environment=source, message=message, stack=stack,
        log_excerpt=f"{correlation_id} browser exception on {route} ({source})",
    )
    return JsonResponse({"recorded": event.id, "correlation_id": correlation_id}, status=201)


def health(request):
    return JsonResponse({"ok": Payment.objects.exists(), "environment": os.getenv("FINCORP_ENVIRONMENT", "runtime"), "commit": os.getenv("FINCORP_COMMIT", "local-unversioned")})
