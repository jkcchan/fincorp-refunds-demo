import json
import subprocess
from pathlib import Path
from django.conf import settings

ROOT = settings.BASE_DIR
COPY = "refunds/copy.json"
HIGH_PREFIXES = (
    "refunds/models.py", "refunds/services.py", "refunds/forms.py", "refunds/migrations/",
    "refunds/middleware.py", "fincorp/", "control/", "trusted_checks/",
    "requirements.txt", ".github/", "scripts/", "prompts/",
)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True, stderr=subprocess.STDOUT).strip()


def validate_head(base, head):
    if not base or not head or not all(len(v) == 40 and all(c in "0123456789abcdef" for c in v) for v in (base, head)):
        raise ValueError("Expected full, locally available Git revision IDs.")
    if git("rev-parse", f"{base}^{{commit}}") != base or git("rev-parse", f"{head}^{{commit}}") != head:
        raise ValueError("Unknown commit.")
    if git("merge-base", base, head) != base or base == head:
        raise ValueError("Candidate must descend from the recorded base.")


def route(base, head):
    validate_head(base, head)
    names = git("diff", "--name-only", base, head).splitlines()
    if not names:
        raise ValueError("No change in candidate.")
    if names == [COPY]:
        old = json.loads(git("show", f"{base}:{COPY}"))
        new = json.loads(git("show", f"{head}:{COPY}"))
        if old.keys() != new.keys() or not all(isinstance(v, str) and len(v) <= 180 for v in new.values()):
            return "review", "Copy keys, types or length changed; not auto-eligible."
        return "auto", "Only allowlisted escaped display strings changed."
    if "refunds/views.py" in names:
        view_diff = git("diff", "-U0", base, head, "--", "refunds/views.py")
        hunks = [line for line in view_diff.splitlines() if line.startswith("@@")]
        if not hunks or any("def queue(" not in line for line in hunks):
            return "owner", "View changes outside queue filtering may affect refund decisions or authority."
    if any(name.startswith(HIGH_PREFIXES) for name in names):
        return "owner", "Sensitive refund, dependency, schema, harness or policy scope requires owner review."
    return "review", "Behavioral, frontend, or uncertain scope requires human review."
