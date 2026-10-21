import uuid
from django.conf import settings
from django.db import models


def new_run():
    return uuid.uuid4().hex


class Change(models.Model):
    STATUSES = [
        ("queued", "Queued"), ("working", "Work in progress"), ("needs_info", "Needs information"),
        ("ready", "Ready for review"), ("changes", "Changes requested"), ("blocked", "Blocked / failed"),
        ("merged", "Merged"), ("released", "Released"), ("duplicate", "Duplicate"),
    ]
    TYPES = [("bug", "Bug"), ("feature", "Feature"), ("copy", "Copy"), ("sensitive", "Sensitive"), ("spec", "Team spec")]
    source = models.CharField(max_length=20, default="report")
    mode = models.CharField(max_length=12, default="manual")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    report = models.TextField()
    route = models.CharField(max_length=250, blank=True)
    case_reference = models.CharField(max_length=32, blank=True)
    source_commit = models.CharField(max_length=64, blank=True)
    safe_context = models.JSONField(default=dict)
    type = models.CharField(max_length=15, choices=TYPES, default="feature")
    urgency = models.CharField(max_length=16, default="normal")
    triage = models.TextField(blank=True)
    acceptance = models.TextField(blank=True)
    owner = models.CharField(max_length=80, default="Tools engineering")
    status = models.CharField(max_length=16, choices=STATUSES, default="queued")
    risk = models.CharField(max_length=16, default="review")
    duplicate_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    base = models.CharField(max_length=64, blank=True)
    head = models.CharField(max_length=64, blank=True)
    checked_base = models.CharField(max_length=64, blank=True)
    checked_head = models.CharField(max_length=64, blank=True)
    check_result = models.CharField(max_length=16, default="pending")
    check_output = models.TextField(blank=True)
    approved_base = models.CharField(max_length=64, blank=True)
    approved_head = models.CharField(max_length=64, blank=True)
    preview_url = models.CharField(max_length=250, blank=True)
    preview_db = models.CharField(max_length=250, blank=True)
    preview_pid = models.IntegerField(null=True, blank=True)
    run_id = models.CharField(max_length=40, default=new_run, unique=True)
    session_id = models.CharField(max_length=100, blank=True)
    session_url = models.URLField(blank=True)
    provider_status = models.CharField(max_length=40, blank=True)
    provider_cursor = models.CharField(max_length=200, blank=True)
    usage_cost = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True)
    acus_consumed = models.PositiveIntegerField(null=True, blank=True)
    create_uncertain = models.BooleanField(default=False)
    packet = models.TextField(blank=True)
    merged_commit = models.CharField(max_length=64, blank=True)
    released_commit = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        permissions = [("review_change", "Review and release software changes")]


class Event(models.Model):
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="events")
    created_at = models.DateTimeField(auto_now_add=True)
    actor = models.CharField(max_length=80)
    source = models.CharField(max_length=32)
    stage = models.CharField(max_length=40)
    detail = models.TextField()
    evidence = models.CharField(max_length=250, blank=True)
    key = models.CharField(max_length=200, unique=True, null=True, blank=True)

    class Meta:
        ordering = ["created_at", "id"]


class Job(models.Model):
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="jobs")
    kind = models.CharField(max_length=25)
    status = models.CharField(max_length=15, default="pending")
    key = models.CharField(max_length=200, unique=True)
    attempts = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)


class Review(models.Model):
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="reviews")
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=16)
    message = models.TextField()
    delivery = models.CharField(max_length=12, default="pending")
    response = models.TextField(blank=True)
    base = models.CharField(max_length=64, blank=True)
    head = models.CharField(max_length=64, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]


class Incident(models.Model):
    change = models.ForeignKey(Change, on_delete=models.CASCADE, related_name="incidents")
    fingerprint = models.CharField(max_length=64)
    environment = models.CharField(max_length=16)
    correlation_id = models.CharField(max_length=64)
    route = models.CharField(max_length=250)
    case_reference = models.CharField(max_length=32, blank=True)
    deployed_commit = models.CharField(max_length=64)
    message = models.TextField()
    stack = models.TextField()
    log_excerpt = models.TextField()
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["fingerprint", "environment", "deployed_commit"], name="incident_dedup")]
