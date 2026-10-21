"""Named local replay tasks; neither fixture is a Devin session."""
import json
import os
from django.conf import settings
from .policy import git, validate_head
from .provider import mode

CONFIG = json.loads((settings.BASE_DIR / "scripts/customer_demo.json").read_text())
CHECKS = {
    "case_link": ("case-link-red", "case-link-green"),
    "queue_intro": ("queue-intro-red", "queue-intro-green"),
}


def identify(change):
    if change.mode != "sample" or os.getenv("FINCORP_CUSTOMER_DEMO") != "1" or mode() != "sample":
        return ""
    text = change.report.lower()
    if (change.case_reference == CONFIG["case_reference"]
            and change.route == f"/cases/{CONFIG['case_reference']}/"
            and "copy case link" in text
            and any(word in text for word in ("nothing", "not work", "doesn't", "does not", "fails"))):
        return "case_link"
    if change.route == "/" and "queue" in text and "review requets" in text and "review requests" in text:
        return "queue_intro"
    return ""


def prepare(change):
    scenario = change.safe_context["sample_scenario"]
    if scenario == "case_link":
        if change.base != CONFIG["baseline"]:
            raise ValueError("The named broken-button baseline has changed; do not replay an old candidate.")
        head = CONFIG["case_link_fix"]
        validate_head(change.base, head)
        if git("diff", "--name-only", change.base, head) != "refunds/static/refunds/detail.js":
            raise ValueError("The pinned case-link fixture has unexpected scope.")
        return head
    if scenario == "queue_intro":
        from .fixtures import candidate
        if "Review requets" not in git("show", f"{change.base}:refunds/copy.json"):
            raise ValueError("The queue typo is no longer present; no replay candidate created.")
        return candidate(change)
    raise ValueError("Unknown sample scenario.")
