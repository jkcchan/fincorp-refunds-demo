"""Explicit, locally authored sample commits. Not agent-generated evidence."""
import subprocess
from .policy import git
from .runner import ROOT, RUNS


def replace(path, before, after):
    text = path.read_text()
    if before not in text:
        raise ValueError(f"Fixture anchor missing in {path.name}.")
    path.write_text(text.replace(before, after, 1))


def candidate(change, revision=False):
    name = change.run_id[:16] + "-" + change.base[:10]
    path = RUNS / "fixtures" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(path), change.base], check=True, capture_output=True)
    current = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if revision and (change.type != "feature" or current != change.head):
        raise ValueError("Revision requires the feature fixture at its current head.")
    if not revision and current != change.base:
        raise ValueError("Fixture already attached. Use revision only for the feature scenario.")
    if change.type == "copy":
        before, after = (
            ("Review requets", "Review requests") if change.safe_context.get("sample_scenario") == "queue_intro"
            else ("Refund requets", "Refund requests")
        )
        replace(path / "refunds/copy.json", before, after)
    elif change.type == "bug":
        replace(path / "refunds/static/refunds/detail.js", "note.trim()", "(note ?? \"\").trim()")
    elif change.type == "feature":
        view = path / "refunds/views.py"
        page = path / "refunds/templates/refunds/queue.html"
        if revision:
            replace(view, 'if assignee_filter == "mine":\n        cases = cases.filter(assignee=request.user)',
                'if assignee_filter == "mine":\n        cases = cases.filter(assignee=request.user)\n    elif assignee_filter == "unassigned":\n        cases = cases.filter(assignee__isnull=True)')
            replace(page, '<option value="mine" {% if assignee_filter == "mine" %}selected{% endif %}>Assigned to me</option>',
                '<option value="mine" {% if assignee_filter == "mine" %}selected{% endif %}>Assigned to me</option><option value="unassigned" {% if assignee_filter == "unassigned" %}selected{% endif %}>Unassigned</option>')
        else:
            replace(view, 'currency = request.GET.get("currency", "")',
                'currency = request.GET.get("currency", "")\n    assignee_filter = request.GET.get("assignee", "")')
            replace(view, 'if currency in ("USD", "CAD"):\n        cases = cases.filter(payment__currency=currency)',
                'if currency in ("USD", "CAD"):\n        cases = cases.filter(payment__currency=currency)\n    if assignee_filter == "mine":\n        cases = cases.filter(assignee=request.user)')
            replace(view, '"currency": currency, "statuses": Case.STATUSES,',
                '"currency": currency, "assignee_filter": assignee_filter, "statuses": Case.STATUSES,')
            replace(page, '  <button>Apply filters</button>',
                '  <div><label for="assignee">Assignee</label><select id="assignee" name="assignee"><option value="">Everyone</option><option value="mine" {% if assignee_filter == "mine" %}selected{% endif %}>Assigned to me</option></select></div>\n  <button>Apply filters</button>')
    else:
        raise ValueError("No sample fixture for this sensitive/spec request. Requires human owner and real candidate.")
    subprocess.run(["git", "-C", str(path), "add", "refunds/"], check=True)
    subprocess.run(["git", "-C", str(path), "-c", "user.name=FinCorp Sample Fixture",
                    "-c", "user.email=fixture@invalid.example", "commit", "-m",
                    f"Sample fixture: {change.type}{' revised' if revision else ''} (not Devin output)"], check=True, capture_output=True)
    return subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
