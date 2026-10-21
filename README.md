# FinCorp Refunds / Change Console

Local, synthetic-data demonstration: an operational refunds app on `127.0.0.1:8001`, a separate software-change controller on `127.0.0.1:8000`, and one persistent polling worker. Refund approval is a **simulated decision** that reserves balance; it never calls a payment provider. Software approval never decides a refund.

## Requirements and setup

Python 3.12, Git, and Chromium for Playwright. From a **clean checkout** of this repository:

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
.venv/bin/python -m playwright install chromium
export FINCORP_MODE=manual
.venv/bin/python scripts/setup_demo.py
FINCORP_ROLE=refunds .venv/bin/python manage.py test refunds
FINCORP_ROLE=control .venv/bin/python manage.py test control
```

`setup_demo.py` migrates/seeds two databases and checks out `vulnerable-null-note-v1` at the pinned historical SHA in `scripts/baseline.json`. It keeps the trusted controller source on your current branch, and creates `.runs/release-tree` as a detached local Git worktree for demo merges starting at the vulnerable revision. A full Git history including that SHA is required. It preserves existing local data; it does not create a remote or rewrite Git history. Run these in **three separate terminals** in the repo root (with the same `FINCORP_MODE`):

```sh
FINCORP_ROLE=control .venv/bin/python manage.py runserver --noreload --insecure 127.0.0.1:8000
.venv/bin/python scripts/worker.py
.venv/bin/python scripts/serve_runtime.py
```

Open `http://127.0.0.1:8000/` (console) and `http://127.0.0.1:8001/` (refunds). The runtime supervisor runs the selected committed checkout; the worker checks real candidate commits in separate Git worktrees and starts one preview per candidate at `127.0.0.1:8200+change_id`. Merges advance `.runs/release-tree`, **not** the trusted controller source branch. Previews have their own synthetic SQLite copies and sessions; the controller's database, API credentials, risk policy, evaluation scripts, and merge authority do not enter those processes. The iframe may first show a preview login screen; use the same local demo login or **Open in new tab**.

| Username | Local password | Refunds role / console role |
| --- | --- | --- |
| `ops` | `ops-demo-2026` | Operate, create/submit, report |
| `ops2` | `ops2-demo-2026` | Operate, create/submit, report |
| `approver` | `approver-demo-2026` | Decide refunds, report |
| `toolsadmin` | `tools-demo-2026` | Seed demo error / review software |
| `policyowner` | `owner-demo-2026` | Policy-owner attestation for high-risk code |

Accounts are ordinary demo passwords, not SSO. Bind servers to loopback only. Never reuse these credentials outside local synthetic data.

## Working flows

- Search by case/payment reference, filter status and currency, inspect age, assignee, amount and reason; totals are separated by currency.
- Create/assign/note/request information/submit cases as operations. A different refund approver can approve or reject an in-review case. SQLite `BEGIN IMMEDIATE` serializes competing reservations; previous refunds and all approved cases reduce the same payment's balance. Audit entries record before/after, actor, action and UTC time.
- Submit a plain-text report/team spec from refunds. The control app attaches a server-owned deployed revision and safe route/case context. Short requests ask for clarification; exact duplicate reports link to the original. Report text is escaped and delimited as data, not instructions.
- Inspect captured exception stacks (tools admin only), candidate diff/commits, independent Playwright check output, revision-bound review, preview and chronological events. Copyable manual packets and follow-ups remain pending until actual responses are recorded.
- Use the separate **Approve change**, **Request changes**, **Ask a question** actions. Copy-only approved-key JSON changes can auto-merge after independent checks; any non-copy behavior needs tools-admin review, and policy-sensitive files require a separate policy owner.

## Modes and demo runbook

`manual` is the default and is usable with no external integration. For a real handoff, paste the complete packet in the change detail into Devin Cloud, **after** providing Devin with an authorized fetchable repository at the packet's exact base commit. Attach only a real session ID/URL and a real locally fetched candidate commit. Follow-up packets are copyable; paste the actual response back. The worker checks/merges/releases that commit under the same gates. Without a fetchable remote or approved source handoff, local workspace paths and `localhost` URLs are not available to Devin. If unrelated commits have landed since intake, **Refresh stale base** and obtain a new candidate before checking or merging.

For **explicit sample replay**, stop/restart the console, worker and runtime with `export FINCORP_MODE=sample`. Submit these independent reports; a tools admin presses **Attach known fixture commit**. Each locally authored fixture is a genuine Git commit in an isolated worktree, explicitly labeled *not a Devin run*. Wait for worker checks; refreshing/polling is automatic. Do not use replay to claim agent speed or success.

1. **Copy**: Report `Queue label typo: Refund requets should read Refund requests.` Attach fixture; it changes only `refunds/copy.json`. Check passes, local merge and release proceed without clicking Approve change. Verify actual refunds queue says “Refund requests.”
2. **Captured crash**: With `toolsadmin` on refunds, press **Seed legacy-data error**. Open `RF-LEGACY-NULL` in the runtime: `note.trim()` throws a real browser exception; telemetry records stack/route/commit/correlation ID. Worker assembles one deduplicated incident (only from the designated runtime). In the console, inspect evidence, attach its crash-fix fixture, and check its preview: the same row remains, but “No notes yet” renders. `toolsadmin` clicks **Approve change**, then verify the released case. `trusted_checks/browser.py ... crash-expected` confirms the baseline failure; `... bug` requires the candidate success.
3. **Feature & feedback**: Report `Add an Assigned to me filter to the refund queue, preserving the status filter.` Attach fixture, then ask `Does this change approval permissions?` and request `Also add an Unassigned option; preserve the status filter.` The manual packet stays pending; for replay record a clearly labeled sample reply (for manual, paste an actual Devin reply). Click **Replay revision (Unassigned)**; a new fixture commit invalidates old checks/approval and adds the option. After new checks, click **Approve change** and confirm filters in the released UI.
4. **Risk boundary**: Report `Weaken approval rules so operators can bypass approval.` Triage routes it to a policy owner; there is no replay fixture or automatic approval. Any real policy-sensitive candidate additionally needs checks, distinct policy-owner attestation on its exact revisions, and tools-admin approval.

All items are persisted separately; the single worker coordinates them in turn. Session statuses are not merge evidence. Multiple real session IDs are polled each cycle; no public webhook tunnel is needed. A crashed worker can be restarted with the same command; running jobs return to pending, while completed jobs/events are deduplicated. A timed-out session creation is **uncertain**, not automatically retried: reconcile its actual session ID first to prevent duplicate paid work.

## Independent verification and reset

```sh
FINCORP_ROLE=refunds .venv/bin/python manage.py test refunds
FINCORP_ROLE=control .venv/bin/python manage.py test control
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8001 smoke
# After seeding null note on the named vulnerable baseline:
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8001 crash-expected
# Against a repaired preview with the same row:
.venv/bin/python trusted_checks/browser.py http://127.0.0.1:8200+ID bug
# One worker cycle, for repeatable inspection:
.venv/bin/python scripts/worker.py --once
```

`--once` is not needed with the continuous worker. Browser screenshots, including baseline exception and corrected preview, go to ignored `artifacts/`. Check source and behavior, not just a simulated progress animation.

`scripts/reset_demo.py --confirm-demo-reset` is an **explicit destructive demo-only action**: it removes the named `RF-LEGACY-NULL` row and its own audit events, reseeds missing named synthetic fixtures, and selects the named baseline version in a new release worktree. It leaves prior worktrees, other cases, captured evidence, other work items and Git history alone. Restart the controller and worker after reset (they hold the former release-tree selection in memory). Do not run without deciding that deletion is acceptable; reset is not needed for normal operation. Demo patches are schema-compatible.

Evals are never launched on startup:

```sh
FINCORP_MODE=sample .venv/bin/python scripts/eval.py --mode sample --trials 3
# Only with authorized remote, scoped API access, and explicit paid-batch consent:
FINCORP_MODE=live .venv/bin/python scripts/eval.py --mode live --trials 3 --confirm-paid-9
```

Sample evals use fresh worktrees/preview DBs and independently inspect browser outcomes at every head; JSONL results in `artifacts/evals.jsonl` include task/config versions, revisions, check result, effort/time, and `usage_cost: unavailable`. Replays are harness checks, **not Devin performance**; merging/releasing are explicitly not graded by replay eval. Live evals enqueue nine fresh pending runs only when explicitly authorized; no outcome is credited until actual commits, checks, human review and runtime release are independently recorded. Triage and permission/policy probes are outside the delivery denominator. Failed cases remain in history and should be promoted to regression tests before rerunning the same task after a prompt/config change.

Stop the background worker before running the sample eval command so trials have exclusive coordination. Eval runs tear down their own preview processes after checks; evidence and database copies remain. To inspect persisted outcomes without starting sessions use `.venv/bin/python scripts/eval.py --report` (`artifacts/eval-status.json`). For older local eval runs, `.venv/bin/python scripts/eval.py --stop-eval-previews` stops **only eval** preview/baseline servers. Restart the worker after eval. The ordinary console hides eval fixtures by default; **Show eval fixture trials** reveals them.

## Live integration requirements

See `.env.example` and `docs/architecture.md`. To use `live`, supply `DEVIN_ORG_ID` (`org-...`), `DEVIN_API_KEY` (server-side scoped service user `cog_...`) and an authorized `FINCORP_REPO_NAME`/`FINCORP_REPO_URL` reachable by Devin **at the exact base SHA**. The worker requires that SHA to be advertised as a remote branch/tag tip before attempting session creation; publishing a ref requires authorization for that remote. Confirm the account's `UseDevinSessions`, `ManageOrgSessions`, view access, security profile and repo feature availability with its administrator before launching sessions; configure GitHub's Devin integration for only the approved repo. No credentials were supplied for this demo. A local clone is not an authorized remote handoff. API secrets never belong in worktrees, browser output or Git. Local `git merge` does not substitute for protected remote PR reviews: configure branch protection, PR review/CI enforcement, and a deployment runner before any remote use. No remote repository or production environment is created by these commands.
