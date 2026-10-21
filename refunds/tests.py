import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections
from django.test import TransactionTestCase
from django.urls import reverse
from .forms import CaseForm
from .models import AuditEvent, Case, Payment
from .services import DecisionError, decide
from scripts.seed import seed_refunds, seed_users


class RefundFlowTests(TransactionTestCase):
    def setUp(self):
        seed_users()
        seed_refunds()
        User = get_user_model()
        self.ops = User.objects.get(username="ops")
        self.approver = User.objects.get(username="approver")
        self.admin = User.objects.get(username="toolsadmin")

    def test_queue_detail_and_actions_with_audit(self):
        self.client.force_login(self.ops)
        page = self.client.get(reverse("refunds:queue"), {"q": "PAY-ASTER", "status": "new", "currency": "USD"})
        self.assertContains(page, "RF-1001")
        self.assertNotContains(page, "RF-1003")
        detail = reverse("refunds:detail", args=["RF-1001"])
        self.assertContains(self.client.get(detail), "PAY-ASTER-001")
        action = reverse("refunds:action", args=["RF-1001"])
        self.client.post(action, {"action": "assign", "assignee": self.ops.id})
        self.client.post(action, {"action": "note", "note": "Merchant contacted."})
        self.client.post(action, {"action": "request_info"})
        self.assertEqual(Case.objects.get(reference="RF-1001").status, Case.INFORMATION)
        self.client.post(action, {"action": "submit"})
        case = Case.objects.get(reference="RF-1001")
        self.assertEqual(case.status, Case.REVIEW)
        self.assertEqual(case.assignee, self.ops)
        self.assertIn("Merchant contacted.", case.note)
        self.assertEqual(case.history.last().before["status"], Case.INFORMATION)
        self.assertEqual(case.history.last().after["status"], Case.REVIEW)

    def test_money_validation_and_currency_constraints(self):
        payment = Payment.objects.get(reference="PAY-ASTER-001")
        for amount in ("-2", "0", "1.234", "NaN", "xyz"):
            self.assertFalse(CaseForm({"payment": payment.id, "requested": amount, "reason": "test"}).is_valid())
        self.assertFalse(CaseForm({"payment": payment.id, "requested": "500", "reason": "test"}).is_valid())
        self.assertTrue(CaseForm({"payment": payment.id, "requested": "12.50", "reason": "test"}).is_valid())
        self.client.force_login(self.ops)
        self.assertEqual(self.client.post(reverse("refunds:new"), {"payment": payment.id, "requested": "12.50", "reason": "Test"}).status_code, 302)
        self.assertEqual(Case.objects.latest("id").requested_minor, 1250)
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            Payment.objects.create(reference="INVALID", merchant="Fictional", currency="EUR", amount_minor=100)

    def test_role_restrictions_idempotency_and_submitter(self):
        case = Case.objects.get(reference="RF-1003")
        with self.assertRaises(DecisionError):
            decide(case.pk, self.ops, Case.APPROVED)
        with self.assertRaises(DecisionError):
            decide(case.pk, self.admin, Case.APPROVED)
        self.assertTrue(decide(case.pk, self.approver, Case.APPROVED))
        self.assertFalse(decide(case.pk, self.approver, Case.APPROVED))
        self.assertEqual(case.payment.remaining_minor, 21200 - 4000 - 5200)
        self.assertEqual(case.history.filter(action=Case.APPROVED).count(), 1)
        case.submitter = self.approver
        case.status = Case.REVIEW
        case.save()
        with self.assertRaises(DecisionError):
            decide(case.pk, self.approver, Case.REJECTED)

    def test_competing_approvals_never_overspend(self):
        payment = Payment.objects.create(reference="PAY-RACE", merchant="Race Demo", currency="USD", amount_minor=5000)
        cases = [
            Case.objects.create(reference=f"RF-RACE-{n}", payment=payment, requested_minor=4000,
                                reason="Concurrent decision", note="", status=Case.REVIEW, submitter=self.ops)
            for n in (1, 2)
        ]
        barrier = threading.Barrier(2)

        def approve(case):
            close_old_connections()
            barrier.wait()
            try:
                return decide(case.pk, self.approver, Case.APPROVED)
            except DecisionError:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(approve, cases))
        self.assertEqual(results, [True, False] if results[0] else [False, True])
        self.assertEqual(Case.objects.filter(payment=payment, status=Case.APPROVED).count(), 1)
        self.assertEqual(payment.remaining_minor, 1000)
        self.assertEqual(AuditEvent.objects.filter(case__payment=payment, action=Case.APPROVED).count(), 1)

    def test_tools_admin_seed_only_and_operator_cannot_approve(self):
        self.client.force_login(self.ops)
        self.assertEqual(self.client.post(reverse("refunds:seed_legacy")).status_code, 403)
        response = self.client.post(reverse("refunds:action", args=["RF-1003"]), {"action": "approve"}, follow=True)
        self.assertContains(response, "Only a refund approver")
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(reverse("refunds:seed_legacy")).status_code, 302)
        self.assertIsNone(Case.objects.get(reference="RF-LEGACY-NULL").note)

    def test_untrusted_case_content_escaped_and_telemetry_sanitized(self):
        import json
        from .models import RuntimeError
        from .middleware import sanitize
        case = Case.objects.get(reference="RF-1001")
        case.reason = "<script>alert(1)</script>"
        case.save()
        self.client.force_login(self.ops)
        detail = self.client.get(reverse("refunds:detail", args=[case.reference]))
        self.assertContains(detail, "&lt;script&gt;alert(1)&lt;/script&gt;")
        response = self.client.post(reverse("refunds:telemetry"), data=json.dumps({
            "route": "/cases/RF-1001/?token=not-stored", "message": "Bearer private-token",
            "stack": "TypeError: cookie=abc123 at detail.js:3", "case_reference": "RF-1001",
            "correlation_id": "a" * 32,
        }), content_type="application/json")
        self.assertEqual(response.status_code, 201)
        error = RuntimeError.objects.get(pk=response.json()["recorded"])
        self.assertEqual(error.route, "/cases/RF-1001/")
        self.assertNotIn("private-token", error.message)
        self.assertNotIn("abc123", error.stack)
        self.assertNotIn("not-stored", error.log_excerpt)
        self.assertNotIn("secret123", sanitize("password=secret123"))
