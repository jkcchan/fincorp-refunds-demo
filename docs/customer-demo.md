# Customer walkthrough: one reviewed repair and one automatic copy change

This is a local **sample replay**. Source commits are locally authored fixtures,
not Devin output. The worker performs real browser checks, starts real candidate
previews, and enforces the review and release gates. Do not describe its events
as a live Devin session or its checks as an agent's hidden reasoning.

## Prepare a separate demo

Use a fresh local checkout to keep the current control database, refund cases,
and prior release worktrees untouched. From the repository root:

```sh
mkdir -p .runs
git clone --local --no-hardlinks . .runs/customer-demo
cd .runs/customer-demo
git remote remove origin
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium
source scripts/customer_demo_env.sh
.venv/bin/python scripts/prepare_customer_demo.py
```

The script refuses an existing release selection or database instead of
resetting it. Start these commands in four terminals in the fresh checkout.
Source `scripts/customer_demo_env.sh` in **each** terminal first:

```sh
FINCORP_ROLE=control .venv/bin/python manage.py runserver --noreload --insecure 127.0.0.1:8100
.venv/bin/python scripts/worker.py
.venv/bin/python scripts/serve_runtime.py
.venv/bin/python scripts/serve_original.py
```

Open `http://127.0.0.1:8101/` for refunds and `http://127.0.0.1:8100/` for
the console. The original baseline stays available at `:8401` even after
releases. The controller owns a separate database in this checkout; its
previews use `:8300+change_id` and separate SQLite copies. The original
demo still uses `:8000` and `:8001`.

Use `ops` / `ops-demo-2026` to report issues and `toolsadmin` /
`tools-demo-2026` to review software. Both are local synthetic accounts.

## Story 1: a broken case action, reviewed

Start on the default refund queue. Point out the search and filters, amounts
in USD and CAD, assignees, and status history. The queue-description typo is
the second story; do not fix it yet.

1. Search for **RF-1009**, the Maple Grove Pantry case on
   **PAY-MAPLE-008**. Open it. Click **Copy case link** in Share case.
   Nothing is copied and no confirmation appears on the named broken baseline
   `6e5ded63d3248592d3c6c68e791a71bd84e1a0d4`. The action does not
   delete or change the refund case.
2. Click **Report an issue / Request a change** on that detail page. Use this
   plain-language report:

   > On RF-1009, Copy case link does nothing when I click it. I expected a
   > link I can share and a confirmation.

   The intake carries `/cases/RF-1009/`, the case reference, and the runtime
   commit without asking the reporter for diagnostic details. In this fresh
   checkout, the work item is **change #1**.
3. Open `http://127.0.0.1:8100/changes/1/` and wait for **Ready for review**.
   The trace shows a queued sample task, an actual local fixture commit,
   enforced `review` routing for the frontend diff, baseline browser
   reproduction, candidate browser check, and the review gate. There is **no
   Devin session**. The pre-authored candidate is
   `698bfad42b14b3c0ce393aaf4ff10f05533d8d86`. No one needs to paste a
   commit or start a paid run.
4. Use **Open original version** for `http://127.0.0.1:8401/cases/RF-1009/`.
   Use the preview at `http://127.0.0.1:8301/cases/RF-1009/` for the
   candidate. Sign in as `ops` if either view requests it. The original
   button stays silent; the candidate shows **Case link copied.** Paste to
   verify the clipboard contains the candidate case URL. The preview works
   both in the review iframe and in a new tab.
5. Keep this item in review while explaining the policy. A frontend behavior
   fix needs a tools-admin decision; it cannot auto-merge. When ready, sign
   in as `toolsadmin`, inspect the diff and check output, then click
   **Approve change**. The worker records **Merged**, then separately
   **Released** after runtime health and browser smoke. Refresh RF-1009 in
   the runtime and repeat the copy action. **Approve refund** is unrelated.

The independent checks are reproducible without the review UI:

```sh
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8401 case-link-red
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8301 case-link-green
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8100 case-link-review 1
```

Run the iframe check before clicking **Approve change**, when its review
button is still visible.

## Story 2: copy-only automatic release

Do this **after** releasing change #1 so the next fixture uses the actual
current release as its base. Return to the refund queue. Its description
still reads **Review requets and track every decision.**

1. Click the queue's **Report an issue / Request a change** link and enter:

   > Queue copy typo: Review requets and track every decision. should read
   > Review requests and track every decision.

   In the fresh checkout this is **change #2**. It gets its own base,
   candidate, browser checks, and preview at `http://127.0.0.1:8302/`.
2. The worker creates a real **local fixture commit** on the current base
   changing only the existing escaped `refunds/copy.json` string. The
   independent browser checks observe the typo on the runtime and corrected
   text in the preview. Trusted policy computes `auto` from the actual diff.
   There is **no Approve change click** on this route. The worker merges,
   releases, and verifies the runtime.
3. Compare the stable original baseline at `http://127.0.0.1:8401/` with
   preview `:8302` or the released runtime at `:8101`. The console trace
   records both the merge and the separate release.

```sh
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8401 queue-intro-red
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8302 queue-intro-green
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8101 queue-intro-green
```

Do not use the older `scripts/reset_demo.py` on the original application
for this walkthrough. To rehearse again, stop the demo processes and create
another fresh local checkout; leave the earlier databases and evidence intact.
