# Local verification record

This record describes **local sample fixtures and real browser observations**, not Devin-generated patches or live API results. All candidate heads named here are actual Git commits in this local repository. Browser screenshots and JSONL traces are ignored local artifacts under `artifacts/` and are not submitted to an external service.

| Flow | Observed local result |
| --- | --- |
| Copy-only #2 | Fixture head `d1369ef62cfdae04fb039ceda85b88a604f2a4a3`, `auto` risk from actual `refunds/copy.json` diff, Playwright check passed, merge/release `3d2d8088843cf471b05efcb226ef24cddb1ac17c` without a human approval action. |
| Captured crash #1 | Browser reported `Cannot read properties of null (reading 'trim')` on `RF-LEGACY-NULL`, actual `detail.js:3:60` stack and correlation ID persisted. Old baseline check saw the pageerror. Fixture `ff982f74b3198ba46bb71c9c522da5defa6d34ad` kept the NULL row, passed independently at preview `:8201` and merged into `e088cc19abe1ca86b416286454265016ab83e5ba`. Initial release health failed when this host denied a process-group signal; the controller logged rollback, then a code fix and explicit retry released `e088cc19abe1ca86b416286454265016ab83e5ba`. Subsequent real runtime browser check passed. |
| Feature & feedback #3 | Initial fixture `114b8e834075c7053835a7c3a189d89e080acc7a` passed; tools admin asked about permission scope and requested Unassigned. Both follow-ups were **sample replies**, not messages delivered to Devin. Fresh revision `297b718acbb8183dd42e352a18f323e22127e5d3` passed independent combined-status browser check; approved merge/release `9490ad484cb48e65caa73dfaf9897685ee85b5e6` passed actual runtime browser check. |
| Risk boundary #4 | A request to weaken approvals triaged `sensitive`/`owner` and stayed queued; no fixture was auto-attached or merged. |
| Missing/duplicate #5/#6 | A short report stayed Needs information; the exact copy report linked to #2 without creating a repair job. |

Tests at handoff: `FINCORP_ROLE=control .venv/bin/python manage.py test control` and `FINCORP_ROLE=refunds .venv/bin/python manage.py test refunds` (tests include concurrent SQLite approvals, role separation, stale check/approval gates, conflict, rollback selection, telemetry origin and mocked provider message idempotency). The independent `trusted_checks/browser.py` fixed-outcome check **failed on actual baseline `4b4e52dbdd3ae80c5a8366add8fc68582dcaa765` with a `trim` pageerror** at `:8621`, and passed against fixture preview `:8221` with the same row. Preview DB was a separate SQLite copy; preview errors did not enqueue a repair incident.

`scripts/eval.py --mode sample --trials 3` (config `fixture-v2`) recorded 3/3 copy, 3/3 bug, and 3/3 feature **fixture browser-preview checks**, not Devin delivery success. An earlier `fixture-v1` run included one mis-triaged feature failure and falsely nonindependent duplicates; it remains in `artifacts/evals.jsonl` and is excluded by version. The eval runner now makes each trial unique, checks triage type, keeps failures, skips auto-merge for eval fixtures, and tears down its own preview servers. The demo's release-health failure also remains visible in the change trace. Usage cost is **unavailable**; no live sessions or remote source handoffs were provided.

Useful screenshots (local):

- `artifacts/console-mixed-work.png` - independent release, queued, duplicate and needs-information rows.
- `artifacts/crash-expected-8621.png` - vulnerable baseline with actual null-note browser exception captured separately.
- `artifacts/bug-8201.png` - checked candidate renders the retained null-note row.
- `artifacts/feature-review-feedback.png` - pending review thread and follow-up packet, marked sample.
- `artifacts/feature-revision-8001.png` - released Unassigned filter with preserved status.

The latest request was to stop local ports. All project servers and preview processes were stopped after verification; this record does not claim they are still available. To repeat the flows, start services using the README. No build-duration timer was recorded; elapsed agent-coding time is not estimated.
