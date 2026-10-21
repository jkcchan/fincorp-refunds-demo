import fcntl
import json
import os
import secrets
import signal
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path
from django.conf import settings
from .policy import git

ROOT = settings.BASE_DIR
RUNS = ROOT / ".runs"
PYTHON = ROOT / ".venv/bin/python"
RUNTIME_DB = Path(os.getenv("FINCORP_REFUNDS_DB", ROOT / "refunds.sqlite3")).resolve()


def checkout(commit, name):
    path = RUNS / "worktrees" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if not (path / ".git").exists():
        subprocess.run(["git", "-C", str(ROOT), "worktree", "add", "--detach", str(path), commit], check=True, capture_output=True, text=True)
    actual = subprocess.check_output(["git", "-C", str(path), "rev-parse", "HEAD"], text=True).strip()
    if actual != commit:
        raise ValueError(f"Checkout at {actual}, expected {commit}.")
    return path


def child_env(commit, db, environment, name):
    # Explicit allowlist: preview and runtime never inherit controller/Devin credentials.
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(RUNS / "empty-home"),
        "DJANGO_SETTINGS_MODULE": "fincorp.settings",
        "FINCORP_ROLE": "refunds",
        "FINCORP_REFUNDS_DB": str(db),
        "FINCORP_COMMIT": commit,
        "FINCORP_ENVIRONMENT": environment,
        "FINCORP_INSTANCE": name,
        "FINCORP_MODE": os.getenv("FINCORP_MODE", "manual"),
        "FINCORP_CONTROL_URL": os.getenv("FINCORP_CONTROL_URL", "http://127.0.0.1:8000"),
        "FINCORP_SECRET_KEY": secrets.token_hex(32),
    }


def backup(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return
    with sqlite3.connect(str(source)) as original, sqlite3.connect(str(target)) as copy:
        original.backup(copy)


def probe(url, commit=None):
    try:
        with urllib.request.urlopen(url + "/health/", timeout=2) as response:
            data = json.load(response)
            return data.get("ok") and (not commit or data.get("commit") == commit)
    except (urllib.error.URLError, TimeoutError, ValueError):
        return False


def serve(commit, db, environment, port, name):
    path = checkout(commit, name)
    log_dir = RUNS / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    (RUNS / "empty-home").mkdir(parents=True, exist_ok=True)
    logfile = open(log_dir / f"{name}.log", "ab")
    try:
        proc = subprocess.Popen(
            [str(PYTHON), "manage.py", "runserver", "--noreload", "--insecure", f"127.0.0.1:{port}"],
            cwd=path, env=child_env(commit, db, environment, name), stdout=logfile, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
    finally:
        logfile.close()
    url = f"http://127.0.0.1:{port}"
    for _ in range(50):
        if probe(url, commit):
            return proc.pid, url
        if proc.poll() is not None:
            break
        time.sleep(.2)
    proc.terminate()
    raise RuntimeError(f"{environment} failed to start at {commit}; see .runs/logs/{name}.log")


def stop(pid):
    if pid:
        try:
            os.killpg(pid, signal.SIGTERM)
        except PermissionError:
            # Some local hosts disallow process-group signals even to owned children.
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        except ProcessLookupError:
            pass


def preview(change):
    port = 8200 + change.pk
    url = f"http://127.0.0.1:{port}"
    if change.preview_url and probe(url, change.head):
        return url
    db = RUNS / "data" / f"preview-{change.run_id}-{change.head[:12]}.sqlite3"
    backup(RUNTIME_DB, db)
    pid, url = serve(change.head, db, "preview", port, f"preview-{change.pk}-{change.head[:12]}")
    change.preview_pid = pid
    change.preview_db = str(db)
    change.preview_url = url
    change.save()
    return url


@contextmanager
def release_lock():
    RUNS.mkdir(exist_ok=True)
    with open(RUNS / "release.lock", "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
        fcntl.flock(lock, fcntl.LOCK_UN)


def runtime_state():
    path = RUNS / "runtime.json"
    if path.exists():
        return json.loads(path.read_text())
    return {"commit": git("rev-parse", "HEAD")}


def select_runtime(commit):
    path = RUNS / "runtime.json"
    path.parent.mkdir(exist_ok=True)
    temp = path.with_suffix(".tmp")
    temp.write_text(json.dumps({"commit": commit}))
    os.replace(temp, path)


def wait_for_health(url, commit, attempts):
    for _ in range(attempts):
        if probe(url, commit):
            return True
        time.sleep(.3)
    return False


def merge(change):
    from .logic import can_merge
    from .policy import route
    with release_lock():
        # Recompute actual policy and evaluate gates immediately before a serialized merge.
        risk, _ = route(change.base, change.head)
        if risk != change.risk:
            raise ValueError("Policy changed since checks; re-evaluate candidate.")
        allowed, reason = can_merge(change)
        if not allowed:
            raise ValueError(reason)
        if git("status", "--porcelain", "--untracked-files=no"):
            raise ValueError("Controller checkout has local edits; cannot merge safely.")
        result = subprocess.run(
            ["git", "-C", str(ROOT), "-c", "user.name=FinCorp Demo", "-c", "user.email=demo@invalid.example",
             "merge", "--no-ff", "--no-edit", change.head], capture_output=True, text=True,
        )
        if result.returncode:
            if (ROOT / ".git/MERGE_HEAD").exists():
                subprocess.run(["git", "-C", str(ROOT), "merge", "--abort"], check=True, capture_output=True)
            raise ValueError("Merge conflict or protection failure: " + result.stderr[-1000:])
        merged = git("rev-parse", "HEAD")
        if git("merge-base", change.head, merged) != change.head:
            raise ValueError("Merge result does not contain candidate.")
        return merged


def release(change):
    from .logic import event
    with release_lock():
        if git("rev-parse", f"{change.merged_commit}^{{commit}}") != change.merged_commit or git("merge-base", change.head, change.merged_commit) != change.head:
            raise ValueError("Release revision is not the verified merge of this candidate.")
        previous = runtime_state()["commit"]
        select_runtime(change.merged_commit)
        url = os.getenv("FINCORP_RUNTIME_URL", "http://127.0.0.1:8001")
        if not wait_for_health(url, change.merged_commit, 70):
            select_runtime(previous)
            restored = wait_for_health(url, previous, 20)
            event(change, "rollback", f"Runtime health failed for {change.merged_commit}; selected {previous}. Restored health: {restored}.")
            raise ValueError("Release health failed; selected previous runtime.")
        # The smoke check observes the actual version and authenticated UI, not just /health/.
        result = subprocess.run(
            [str(PYTHON), str(ROOT / "trusted_checks/browser.py"), url, "smoke"],
            cwd=ROOT, capture_output=True, text=True, timeout=65,
        )
        if result.returncode:
            select_runtime(previous)
            restored = wait_for_health(url, previous, 20)
            event(change, "rollback", f"Smoke failed: {result.stdout[-800:]} {result.stderr[-800:]}; selected {previous}. Restored health: {restored}.")
            raise ValueError("Release smoke failed; selected previous runtime.")
        return result.stdout[-2500:]
