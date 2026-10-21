#!/usr/bin/env python3
import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fincorp.settings")
os.environ["FINCORP_ROLE"] = "control"
import django
django.setup()
from control.models import Job
from control.worker import tick

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    Job.objects.filter(status="running").update(status="pending")
    while True:
        tick()
        if args.once:
            break
        time.sleep(2)
