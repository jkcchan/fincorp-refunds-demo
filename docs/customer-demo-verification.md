# Customer replay verification

This record covers an isolated local clone at
`.runs/customer-rehearsal`, not a Devin session. It has its own seeded
control and refunds databases. The original console at `:8000`, runtime at
`:8001`, and their work items were not reset or released as part of this run.
No remote, service credential, payment provider, or customer data was used.

## Observed browser behavior

The named baseline is `6e5ded63d3248592d3c6c68e791a71bd84e1a0d4`.
For synthetic case **RF-1009** on **PAY-MAPLE-008**, clicking **Copy case
link** left both the clipboard and status text unchanged. The candidate
`698bfad42b14b3c0ce393aaf4ff10f05533d8d86` copied the actual case URL
and displayed **Case link copied.** The candidate changed only
`refunds/static/refunds/detail.js`; the policy routed it to human `review`.
The baseline and candidate ran as distinct committed checkouts with separate
SQLite copies. `trusted_checks/browser.py` returned success for
`case-link-red` against the old runtime and `case-link-green` against the
preview, and the inverse expectations failed.

The first fixture implementation copied correctly in a new tab but failed
inside the cross-origin console iframe because browser clipboard permission
was denied. Its failed iframe check and
`.runs/customer-rehearsal/artifacts/customer-iframe-permission-before.png`
were retained. A revised
locally authored fixture added a browser copy fallback; an actual Playwright
iframe click then displayed the success message and put the candidate URL on
the clipboard. The iframe replay check passed at the revised head.

For the queue description, the released runtime still displayed **Review
requets and track every decision.** after the case-link release. A separate
locally authored fixture changed only `refunds/copy.json`. The browser check
observed the typo before and the corrected **Review requests and track every
decision.** in the preview. The trusted policy classified this exact diff
as `auto`. No reviewer approval was recorded for it.

## Workflow and release

- Work item #1 came from an `ops` report submitted through RF-1009's case
  detail page. The console attached the route, case and deployed commit.
  Persisted events record triage, a named sample task, actual fixture head,
  policy decision, baseline reproduction, independent preview check and a
  review gate. No Devin session or generated patch was claimed.
- A `toolsadmin` approved #1 after the revised preview passed. The worker
  verified local merge `79aec26649238c954ddbab88d2b3909454bf70fd`
  and separately released it. The runtime browser then copied the link.
- Work item #2 came from a separate queue report. The worker based its
  fixture `c8291b70f353310be481a17c581d8845415e1014` on #1's
  released revision. It passed its own red/green browser checks,
  auto-merged without approval, and released
  `acb5d0ac6460f90735df32804c336a675dcd3795`.
  The original version at `:8401` still showed the typo and broken button,
  while the released runtime at `:8101` showed both fixes.

The rehearsal clone passed 21 control tests and 8 refunds tests after the
first customer-replay implementation. The final fixture SHA and controller
test suite were rechecked in the source repository: 21 control and 8 refunds
tests passed. The customer runbook is in `docs/customer-demo.md`.

Local screenshots in the ignored rehearsal checkout:

- `.runs/customer-rehearsal/artifacts/case-link-red-8401.png`
- `.runs/customer-rehearsal/artifacts/case-link-green-8301.png`
- `.runs/customer-rehearsal/artifacts/case-link-review-1.png`
- `.runs/customer-rehearsal/artifacts/queue-intro-red-8401.png`
- `.runs/customer-rehearsal/artifacts/queue-intro-green-8302.png`
- `.runs/customer-rehearsal/artifacts/queue-intro-green-8101.png`
- `.runs/customer-rehearsal/artifacts/customer-console-releases.png`

These replay results verify the local application and release gates. They
do not measure Devin performance, usage cost, or protected remote merging.

## Presenter-ready checkout

A second fresh clone at `.runs/customer-demo` was prepared from
`6c82bb3490c41e52f9996c410b2a796ff1caa557` without a Git remote or
network download. Cached local Python packages were reused. Both migrations,
21 control tests, 8 refunds tests, and Django system checks passed. Browser
checks at the actual runtime `:8101` observed the inert case-link button
and the queue typo. The control database has **zero work items**. Control
`:8100`, runtime `:8101`, the stable original `:8401`, and the worker were
left running for a customer to submit #1 and #2. No candidate was merged
or released in this presenter-ready clone.
