import json
import sqlite3
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import AuditEvent, Case


class DecisionError(Exception):
    pass


def snapshot(case):
    return {
        "status": case.status, "requested_minor": case.requested_minor,
        "assignee": case.assignee_id, "note": case.note,
        "payment": case.payment.reference,
    }


def record(case, actor, action, before):
    AuditEvent.objects.create(case=case, actor=actor, action=action, before=before, after=snapshot(case))


def decide(case_id, actor, decision):
    """SQLite BEGIN IMMEDIATE serializes balance reads and reservations across processes."""
    if decision not in (Case.APPROVED, Case.REJECTED):
        raise DecisionError("Invalid decision")
    if not actor.has_perm("refunds.approve_refund"):
        raise DecisionError("Only a refund approver may decide a case.")
    path = settings.DATABASES["default"]["NAME"]
    with sqlite3.connect(path, timeout=15, isolation_level=None, uri=path.startswith("file:")) as db:
        db.execute("PRAGMA busy_timeout=15000")
        db.execute("BEGIN IMMEDIATE")
        try:
            row = db.execute(
                "SELECT payment_id, requested_minor, status, submitter_id, assignee_id, note FROM refunds_case WHERE id=?",
                (case_id,),
            ).fetchone()
            if not row:
                raise DecisionError("Case not found.")
            payment_id, requested, status, submitter_id, assignee_id, note = row
            if status == decision:
                db.execute("COMMIT")
                return False
            if status != Case.REVIEW:
                raise DecisionError("Only a case in review can be decided.")
            if actor.id == submitter_id:
                raise DecisionError("A submitter cannot decide their own case.")
            if decision == Case.APPROVED:
                payment = db.execute("SELECT reference, amount_minor, previously_refunded_minor FROM refunds_payment WHERE id=?", (payment_id,)).fetchone()
                reserved = db.execute(
                    "SELECT COALESCE(SUM(requested_minor), 0) FROM refunds_case WHERE payment_id=? AND status=?",
                    (payment_id, Case.APPROVED),
                ).fetchone()[0]
                if requested > payment[1] - payment[2] - reserved:
                    raise DecisionError("Not enough refundable balance remains.")
            else:
                payment = db.execute("SELECT reference FROM refunds_payment WHERE id=?", (payment_id,)).fetchone()
            before = {"status": status, "requested_minor": requested, "assignee": assignee_id, "note": note, "payment": payment[0]}
            after = dict(before, status=decision)
            db.execute("UPDATE refunds_case SET status=?, updated_at=? WHERE id=?", (decision, timezone.now(), case_id))
            db.execute(
                "INSERT INTO refunds_auditevent (case_id, actor_id, action, before, after, occurred_at) VALUES (?,?,?,?,?,?)",
                (case_id, actor.id, decision, json.dumps(before), json.dumps(after), timezone.now()),
            )
            db.execute("COMMIT")
            return True
        except Exception:
            db.execute("ROLLBACK")
            raise
