import uuid
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

CURRENCIES = [("USD", "USD"), ("CAD", "CAD")]


def new_reference():
    return f"RF-{uuid.uuid4().hex[:8].upper()}"


class Payment(models.Model):
    reference = models.CharField(max_length=32, unique=True)
    merchant = models.CharField(max_length=100)
    currency = models.CharField(max_length=3, choices=CURRENCIES)
    amount_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    previously_refunded_minor = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(currency__in=["USD", "CAD"]), name="payment_supported_currency"),
            models.CheckConstraint(condition=models.Q(amount_minor__gt=0), name="payment_positive_amount"),
            models.CheckConstraint(condition=models.Q(previously_refunded_minor__lte=models.F("amount_minor")), name="payment_refund_within_amount"),
        ]

    def __str__(self):
        return self.reference

    @property
    def remaining_minor(self):
        reserved = self.cases.filter(status=Case.APPROVED).aggregate(
            amount=models.Sum("requested_minor")
        )["amount"] or 0
        return max(0, self.amount_minor - self.previously_refunded_minor - reserved)


class Case(models.Model):
    NEW = "new"
    INFORMATION = "information"
    REVIEW = "review"
    APPROVED = "approved"
    REJECTED = "rejected"
    STATUSES = [
        (NEW, "Open"), (INFORMATION, "Needs information"),
        (REVIEW, "In review"), (APPROVED, "Approved (simulated)"), (REJECTED, "Rejected"),
    ]
    reference = models.CharField(max_length=32, unique=True, default=new_reference)
    payment = models.ForeignKey(Payment, on_delete=models.PROTECT, related_name="cases")
    requested_minor = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    reason = models.CharField(max_length=120)
    note = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=16, choices=STATUSES, default=NEW)
    assignee = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_cases")
    submitter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="submitted_cases")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("manage_case", "Manage refund cases"), ("approve_refund", "Approve refund decisions"), ("seed_legacy", "Seed demo legacy data")]
        constraints = [models.CheckConstraint(condition=models.Q(requested_minor__gt=0), name="case_positive_amount")]


class AuditEvent(models.Model):
    case = models.ForeignKey(Case, on_delete=models.PROTECT, related_name="history")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=30)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["occurred_at", "id"]


class RuntimeError(models.Model):
    fingerprint = models.CharField(max_length=64)
    correlation_id = models.CharField(max_length=64, db_index=True)
    source = models.CharField(max_length=16)
    route = models.CharField(max_length=250)
    case_reference = models.CharField(max_length=32, blank=True)
    deployed_commit = models.CharField(max_length=64)
    environment = models.CharField(max_length=16)
    message = models.CharField(max_length=400)
    stack = models.TextField()
    log_excerpt = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
