# FinCorp Refunds and Change Console

FinCorp has a refunds dashboard and a separate console for changes to its
software. All merchants, payments, and users are fictional. Approving a
refund reserves a simulated balance; it does not transfer money. Software
approval is a separate decision.

## Run it from a fresh checkout

Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/)
first. From the root of a fresh clone, run these commands in a macOS or
Linux shell. uv uses Python 3.12, and Playwright installs Chromium.

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium
source scripts/customer_demo_env.sh
.venv/bin/python scripts/prepare_customer_demo.py
```

The setup script creates separate SQLite databases for refunds and the
console. It seeds the demo accounts and cases, then selects the version
with the broken case-link button. It refuses to overwrite an existing demo.
For another run, use another checkout. Free ports `8000` and `8001` first.

Open four terminals in the checkout. Run `source scripts/customer_demo_env.sh`
in each terminal, followed by that terminal's command:

| Terminal | Command |
| --- | --- |
| Change console | `FINCORP_ROLE=control .venv/bin/python manage.py runserver --noreload --insecure 127.0.0.1:8000` |
| Job worker | `.venv/bin/python scripts/worker.py` |
| Refunds runtime | `.venv/bin/python scripts/serve_runtime.py` |
| Original version for comparison | `.venv/bin/python scripts/serve_original.py` |

Refunds is at http://127.0.0.1:8001/ and the change console is at
http://127.0.0.1:8000/. The original version stays at
http://127.0.0.1:8401/ so you can compare it with a preview after release.
Press Ctrl+C in each terminal to stop the services.

| Username | Password | Purpose |
| --- | --- | --- |
| `ops` | `ops-demo-2026` | Manage cases and report issues |
| `ops2` | `ops2-demo-2026` | Second operations user |
| `approver` | `approver-demo-2026` | Decide simulated refunds |
| `toolsadmin` | `tools-demo-2026` | Review software changes |
| `policyowner` | `owner-demo-2026` | Attest to sensitive changes |

Sign in separately to each app. These passwords are for this local demo;
there is no SSO.

## What the app demonstrates

In refunds, an operator can search and filter cases, read a payment's audit
history, add notes, assign work, and submit a case for review. A different
user must decide the simulated refund. USD and CAD balances use integer
minor units, and competing approvals cannot reserve the same balance twice.

An operator can also report a problem in plain language. The console
records where it happened and which version was deployed. A persistent
worker checks a candidate commit in a separate preview, then saves the
diff, browser results, and trace for review. A tools admin must approve
a behavior change. A change confined to allowlisted display copy can
merge and release after the checks without that approval.

## Walk through a fresh demo

A fresh clone has seeded refund cases but no change requests. These two
reports use locally authored sample fixes. Devin did not generate them.

1. In refunds, open **RF-1009** (Maple Grove Pantry). Under **Share case**,
   click **Copy case link**. The named baseline does nothing. Click
   **Report an issue / Request a change** on that case and enter:

   > On RF-1009, Copy case link does nothing when I click it. I expected a
   > link I can share and a confirmation.

   The worker puts change #1 in review with a checked preview at `:8301`.
   The button works there and remains broken at `:8001`. Sign in as
   `toolsadmin` to inspect the diff and click **Approve change** when you
   want to release it.
2. After #1 is released, the refund queue still says **Review requets and
   track every decision.** Report the issue from the queue using:

   > Queue copy typo: Review requets and track every decision. should read
   > Review requests and track every decision.

   Change #2 gets a preview at `:8302`. Its diff changes only the queue
   description, so the worker merges and releases it after the browser
   checks. No one clicks **Approve change** for this item.

The original version at `:8401` stays available for comparison. The
pre-recorded change history in our local presenter instance is not included
in a GitHub clone; the reports above create new work items.

## Check the installation

```sh
FINCORP_ROLE=refunds .venv/bin/python manage.py test refunds
FINCORP_ROLE=control .venv/bin/python manage.py test control
```

The servers bind to loopback and use synthetic data. A preview runs in a
separate worktree and process, which is not a security sandbox. There is
no payment-provider connection or live Devin session in this setup. Live
integration requires separate credentials and repository access.
