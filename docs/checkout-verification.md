# Verification in this checkout

This workspace is a local, network-free clone of the completed FinCorp demo
at `1a908f853023395e65001b0631c994dc09d482ae`. Its source repository
remains unchanged. This record reports only checks run in this workspace.

## Definition of done

From a clean local checkout, both Django apps migrate and pass their tests.
A browser sees the null-note failure on the named baseline and renders the
same row on the fixed fixture. An independent replay checks all three
delivery scenarios without claiming Devin performed the work. The UI remains
usable on loopback. No remote or paid sessions are created.

## Workflow

- [x] Phase A: Frame. Identify the source, pinned baseline, and access limits.
- [x] Phase B: Design the workflow. Check setup, tests, real browser behavior,
  and replay in that order; keep each result independent of the old record.
- [x] Phase C: Run the loop. Run the README setup and tests; inspect a real
  baseline crash, repaired preview, and replay output.
- [x] Phase D: Keep the audit trail. Record key decisions in
  `docs/checkout-decisions.tsv` as each check completes.
- [x] Phase E: Verify and hand back. Inspect the actual artifacts and limits.

## Throughput checkpoint

- Blocking first steps: local checkout, installed Python and browser, DB migrations.
- Independent workstreams: read-only source audit alongside setup; runtime and
  replay checks wait for setup.
- Shared mutable state: one worker or eval process at a time; the release
  worktree and SQLite databases are shared.
- Smallest safe decomposition: one local checkout and one coordinator; no
  parallel writers to the runtime or Git worktrees.

## Results

The clean clone had no Git remote. `uv venv --python 3.12 .venv` succeeded.
`uv pip install --offline` could not resolve Playwright from cached registry
metadata. To avoid network access, this checkout reused the installed packages
from the earlier local demo environment; Chromium was already installed.
The normal online dependency install was not tested in this run.
`FINCORP_MODE=manual .venv/bin/python scripts/setup_demo.py` migrated both
SQLite databases, seeded demo users, and selected
`4b4e52dbdd3ae80c5a8366add8fc68582dcaa765` as the named vulnerable
runtime. This checkout has 15 named payments and 15 named cases after the
synthetic seed expansion. The live demo DB also has the legacy case and one
case created through the UI.

- `FINCORP_ROLE=refunds .venv/bin/python manage.py test refunds`: 8 passed.
- `FINCORP_ROLE=control .venv/bin/python manage.py test control`: 18 passed.
- `manage.py check` under each role: no issues.
- Refund browser UI: rejected zero and over-balance amounts, created
  `RF-60C428EE`, added a note, submitted it, and approved it as another user.
  Operations had no approval action. The simulated decision reserved 825
  minor units once; the payment balance became 7075 minor units, with one
  approval audit event.
- `trusted_checks/browser.py` against the old runtime produced a real
  `trim` page error on `RF-LEGACY-NULL`. The fixed-outcome check failed there
  and passed against the checked preview and released runtime while that
  row's note remained `NULL`. The incident stored the stack, route, deployed
  SHA, and correlation ID `4aec0da817d54a2cad0ecb8a262f6c4d`.

Sample mode used local commits authored as fixtures, **not Devin patches**:

| Work item | Observed result |
| --- | --- |
| Copy #2 | Only `refunds/copy.json` changed in fixture `c19f93bca765971cb015c08355defabf7b18e289`. Trusted checks passed; risk was `auto`; merge/release `27d6a9e6825533547bb5f434c98b6f9f8c0569ee` happened without software approval. |
| Crash #1 | One captured incident was deduplicated. Fix fixture `d6e82434846a3de71f96527ab1183859d70f4aaf` passed the browser check at `:8201`. A tools admin approved the software change; release `48c119054f94bb98476fa9b985848aa6c124f1b0` rendered the retained row. |
| Feature #6 | First fixture passed. A question and a change request blocked approval until labeled sample replies were recorded. Revised fixture `e10d3e3358d6d9016767cfcdc867d66b4e9f2c21` invalidated old checks and passed fresh checks. A tools admin approved release `bfc82dbf80b33da766739304deb0b6c9813b36ae`. The actual runtime has Assigned to me and Unassigned with status filtering intact. |
| Boundary #4 | The request to weaken refund approval rules remains queued with enforced `owner` risk. #3 needs information; duplicate #5 links to #2 and did not start a repair. |

The first same-browser session check failed because logging into a historical
preview overwrote the runtime's `sessionid`. After adding the trusted launcher
and relaunching the children, `browser.py` with `session-isolation` passed with
different users signed into runtime `:8001` and preview `:8206`. An actual
browser error on copy preview `:8202` was attached to its run; it created no
new repair incident. A separate historical eval server persisted a real
`trim` stack with environment `eval` after the launcher change.

Sample eval
`FINCORP_MODE=sample .venv/bin/python scripts/eval.py --mode sample --trials 3`
recorded nine fresh browser-preview checks: 3/3 copy,
3/3 bug, and 3/3 feature. `artifacts/eval-status.json` marks delivery success
as **not scored** for replay; cost is unavailable. No remote repository, live
Devin session, API call, paid batch, protected PR, or production payment
operation was used.

Manual mode was also exercised without pretending that Devin responded.
Team-spec #16 holds a copyable packet with no authorized remote configured.
For #17, a locally authored commit
`9435d8a979302def8acfed714d44d15b2672cac9` was attached without a
session ID. Its preview at `:8217` rendered the requested empty-note copy
and its generic feature smoke check passed. A separate browser check observed
the requested text on the retained legacy row; the worker check alone did
not test that copy change. A tools-admin question has a copyable manual
follow-up packet in `pending` delivery; approval remains blocked. The manual
candidate is neither merged nor released.

Screenshots and traces are local, ignored files:

- `artifacts/checkout-refunds-desktop.png` and
  `artifacts/checkout-refunds-mobile.png`: enriched queue and filters.
- `artifacts/crash-expected-8001.png`,
  `artifacts/bug-8201.png`, and `artifacts/checkout-baseline-bug-check.txt`:
  real baseline failure and fixed preview.
- `artifacts/checkout-bug-review.png`,
  `artifacts/checkout-feature-feedback.png`,
  `artifacts/checkout-feature-review-ready.png`, and
  `artifacts/checkout-console-final.png`: review and mixed work states.
- `artifacts/checkout-manual-followup.png` and
  `artifacts/checkout-manual-preview.png`: offline handoff and local candidate.
- `artifacts/checkout-session-before.txt` and
  `artifacts/evals.jsonl`: red session repro and per-trial replay outcomes.

Old candidate commits still share the default CSRF cookie because their
telemetry code reads its literal name. Logging into another historical
instance can invalidate an already-open form; reload that form before
submitting. The launcher isolates sessions, not untrusted candidate code.
Worktrees are not a security sandbox. Live Devin verification requires a
scoped organization key and permissions, an authorized repository fetchable
at the exact base SHA, configured GitHub integration and security profile,
and protected remote review/merge access. None was provided here. The
provider contract recorded in `docs/architecture.md` was not exercised
against an organization account during this run. The old
`docs/verification.md` describes another local workspace and its ignored
screenshots; this document records this checkout's evidence. The
normal package download was not verified offline, and build duration was
not measured.

After committing the application changes at
`e728a91f1531e63483043e955db18fb900db8044`, a second local clone in
`.runs/checkout-reverify` had no remote and began with empty application
databases. It reused the same cached local Python packages without network
access, followed the README setup, migrated both databases, and created 15
cases and 15 payments. Its 8 refund and 18 control tests passed, and both
Django system checks reported no issues. On isolated ports `:8780` and
`:8781`, the real browser captured the vulnerable `trim` error, the current
fixed source rendered the same `NULL` row, and one browser context retained
independent runtime and preview logins. The browser processes on those two
ports were stopped; the source clone stayed clean. Screenshots are in
`.runs/checkout-reverify/artifacts/crash-expected-8780.png` and
`.runs/checkout-reverify/artifacts/bug-8781.png`.
