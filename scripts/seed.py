#!/usr/bin/env python3
import os
import sys
from pathlib import Path

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
    from refunds.models import Case, Payment
    from refunds.services import record
    users = get_user_model().objects
    rows = [
        ("PAY-ASTER-001", "Aster Books", "USD", 18500, 2500),
        ("PAY-NORTH-002", "North Coast Supply", "USD", 7900, 0),
        ("PAY-JUNIPER-003", "Juniper & Co.", "CAD", 21200, 4000),
        ("PAY-ORBIT-004", "Orbit Market", "CAD", 10500, 0),
        ("PAY-LEGACY-DEMO", "Harbor Studio", "USD", 4300, 0),
    ]
    for ref, merchant, currency, amount, refunded in rows:
        Payment.objects.get_or_create(reference=ref, defaults={
            "merchant": merchant, "currency": currency, "amount_minor": amount,
            "previously_refunded_minor": refunded,
        })
    cases = [
        ("RF-1001", "PAY-ASTER-001", 4500, "Duplicate charge", "Customer supplied two receipts.", "new", "ops", "ops2"),
        ("RF-1002", "PAY-NORTH-002", 2400, "Item not received", "Awaiting delivery confirmation.", "information", "ops2", None),
        ("RF-1003", "PAY-JUNIPER-003", 5200, "Service canceled", "Cancellation verified.", "review", "ops", "ops2"),
        ("RF-1004", "PAY-ORBIT-004", 1100, "Pricing adjustment", "Approved simulation; no provider transfer.", "approved", "ops2", "ops"),
        ("RF-1005", "PAY-ASTER-001", 2000, "Outside policy", "Rejected during initial review.", "rejected", "ops", None),
    ]
    for ref, payment, minor, reason, note, status, submitter, assignee in cases:
        case, created = Case.objects.get_or_create(reference=ref, defaults={
            "payment": Payment.objects.get(reference=payment), "requested_minor": minor,
            "reason": reason, "note": note, "status": status, "submitter": users.get(username=submitter),
            "assignee": users.get(username=assignee) if assignee else None,
        })
        if created:
            record(case, users.get(username=submitter), "demo_seed", {})


if __name__ == "__main__":
    seed_users()
    if os.getenv("FINCORP_ROLE", "control") == "refunds":
        seed_refunds()
    print(f"Seeded {os.getenv('FINCORP_ROLE', 'control')} local synthetic demo data.")
