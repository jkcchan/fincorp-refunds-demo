#!/usr/bin/env python3
"""Trusted launcher for checkout children: isolates the session cookie before Django binds."""
import os
import runpy
import sys
from pathlib import Path

from django.conf import settings

WORKTREE = Path.cwd()
sys.path.insert(0, str(WORKTREE))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
instance = os.environ.get("FINCORP_INSTANCE", "")
if not instance.isascii() or not instance.replace("-", "").replace("_", "").isalnum():
    raise SystemExit("FINCORP_INSTANCE must be an ASCII instance name")
# Legacy capture.js hardcodes "csrftoken", so leave its CSRF cookie untouched.
settings.SESSION_COOKIE_NAME = f"fincorp_{instance}_session"
sys.argv[0] = "manage.py"
runpy.run_path(str(WORKTREE / "manage.py"), run_name="__main__")
