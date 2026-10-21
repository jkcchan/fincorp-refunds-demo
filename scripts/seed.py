#!/usr/bin/env python3
import os
import sys
from datetime import timedelta
from pathlib import Path
from django.utils import timezone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
import django
django.setup()
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission

USERS = [
    ("ops", "Operations", "Operations", "ops-demo-2026"),
    ("ops2", "Operations", "Operations", "ops2-demo-2026"),
    ("approver", "Refund approver", "Refund approvers", "approver-demo-2026"),
    ("toolsadmin", "Tools admin", "Tools admins", "tools-demo-2026"),
    ("policyowner", "Policy owner", "Refund policy owners", "owner-demo-2026"),
]


def seed_users():
    User = get_user_model()
    for name, label, group_name, password in USERS:
        user, created = User.objects.get_or_create(username=name, defaults={"first_name": label})
        if created:
            user.set_password(password)
            user.save()
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    if os.getenv("FINCORP_ROLE", "control") == "refunds":
        perms = {"Operations": ["manage_case"], "Refund approvers": ["approve_refund"], "Tools admins": ["seed_legacy"]}
    else:
        perms = {"Tools admins": ["review_change"]}
    for group_name, codes in perms.items():
        Group.objects.get(name=group_name).permissions.add(*Permission.objects.filter(
            content_type__app_label=os.getenv("FINCORP_ROLE", "control"), codename__in=codes,
        ))


def seed_refunds():
    from refunds.models import AuditEvent, Case, Payment
    from refunds.services import record
    users = get_user_model().objects
    rows = [
        ("PAY-ASTER-001", "Aster Books", "USD", 18500, 2500),
        ("PAY-NORTH-002", "North Coast Supply", "USD", 7900, 0),
        ("PAY-JUNIPER-003", "Juniper & Co.", "CAD", 21200, 4000),
        ("PAY-ORBIT-004", "Orbit Market", "CAD", 10500, 0),
        ("PAY-LEGACY-DEMO", "Harbor Studio", "USD", 4300, 0),
        ("PAY-LUMEN-005", "Lumen Lighting", "USD", 9640, 1200),
        ("PAY-BIRCH-006", "Birch & Pine Goods", "CAD", 15275, 0),
        ("PAY-HALO-007", "Halo Fitness Gear", "USD", 22100, 8900),
        ("PAY-MAPLE-008", "Maple Grove Pantry", "CAD", 6750, 0),
        ("PAY-VESPER-009", "Vesper Travel Co.", "USD", 134900, 45000),
        ("PAY-CINDER-010", "Cinder Ceramics", "USD", 3820, 0),
        ("PAY-FJORD-011", "Fjord Outfitters", "CAD", 54120, 7150),
        ("PAY-QUILL-012", "Quill Paperworks", "USD", 12480, 3100),
        ("PAY-SOL-013", "Sol Audio", "CAD", 28990, 0),
        ("PAY-TIDE-014", "Tide & Anchor Marine", "USD", 76300, 12000),
    ]
    for ref, merchant, currency, amount, refunded in rows:
        Payment.objects.get_or_create(reference=ref, defaults={
            "merchant": merchant, "currency": currency, "amount_minor": amount,
            "previously_refunded_minor": refunded,
        })
    cases = [
        ("RF-1001", "PAY-ASTER-001", 4500, "Duplicate charge", "Customer supplied two receipts.", "new", "ops", "ops2", 0),
        ("RF-1002", "PAY-NORTH-002", 2400, "Item not received", "Awaiting delivery confirmation.", "information", "ops2", None, 1),
        ("RF-1003", "PAY-JUNIPER-003", 5200, "Service canceled", "Cancellation verified.", "review", "ops", "ops2", 3),
        ("RF-1004", "PAY-ORBIT-004", 1100, "Pricing adjustment", "Approved simulation; no provider transfer.", "approved", "ops2", "ops", 9),
        ("RF-1005", "PAY-ASTER-001", 2000, "Outside policy", "Rejected during initial review.", "rejected", "ops", None, 14),
        ("RF-1006", "PAY-LUMEN-005", 3100, "Item arrived damaged", "Photos on file; awaiting merchant response.", "information", "ops", "ops2", 5),
        ("RF-1007", "PAY-BIRCH-006", 2750, "Duplicate charge", "Two authorizations for one order.", "review", "ops2", "ops", 7),
        ("RF-1008", "PAY-HALO-007", 6600, "Service canceled", "Subscription ended mid-cycle; partial refund.", "approved", "ops", "ops2", 21),
        ("RF-1009", "PAY-MAPLE-008", 1450, "Item not received", "Carrier shows delivered; customer disputes.", "review", "ops2", "ops", 2),
        ("RF-1010", "PAY-VESPER-009", 32800, "Trip canceled by merchant", "Airline-initiated cancellation, full fare.", "review", "ops", "ops2", 11),
        ("RF-1011", "PAY-CINDER-010", 3820, "Item not as described", "Full order return requested.", "new", "ops2", None, 0),
        ("RF-1012", "PAY-FJORD-011", 9900, "Duplicate charge", "Settled twice in one batch.", "approved", "ops", "ops2", 28),
        ("RF-1013", "PAY-QUILL-012", 1825, "Pricing adjustment", "Promo code not applied at checkout.", "new", "ops2", "ops", 4),
        ("RF-1014", "PAY-SOL-013", 7400, "Item arrived damaged", "Return label issued; awaiting scan.", "information", "ops", "ops2", 17),
        ("RF-1015", "PAY-TIDE-014", 15000, "Service not rendered", "Charter rescheduled three times, then canceled.", "rejected", "ops2", "ops", 35),
    ]
    for ref, payment, minor, reason, note, status, submitter, assignee, days_old in cases:
        case, created = Case.objects.get_or_create(reference=ref, defaults={
            "payment": Payment.objects.get(reference=payment), "requested_minor": minor,
            "reason": reason, "note": note, "status": status, "submitter": users.get(username=submitter),
            "assignee": users.get(username=assignee) if assignee else None,
        })
        if created:
            record(case, users.get(username=submitter), "demo_seed", {})
            stamp = timezone.now() - timedelta(days=days_old, hours=(case.pk * 7) % 24)
            Case.objects.filter(pk=case.pk).update(created_at=stamp, updated_at=stamp)
            AuditEvent.objects.filter(case=case, action="demo_seed").update(occurred_at=stamp)


if __name__ == "__main__":
    seed_users()
    if os.getenv("FINCORP_ROLE", "control") == "refunds":
        seed_refunds()
    print(f"Seeded {os.getenv('FINCORP_ROLE', 'control')} local synthetic demo data.")
