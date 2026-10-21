# FinCorp demo: two existing before-and-after changes

Open the **refund queue** at http://127.0.0.1:8001/ and the **change
console** at http://127.0.0.1:8000/. Sign in to refunds as
`ops` / `ops-demo-2026`. To inspect the software review controls, use
`toolsadmin` / `tools-demo-2026` on the console.

These changes are already **released**. Do not file another report, reset
the database, or click **Approve change** again. The candidates are real
local commits in a **sample replay**, not patches or sessions from live Devin.
The browser checks, review decisions, merges, and releases shown in the
trace did actually run locally.

## 1. Show the working refund queue

Show the search, status and assignee filters, USD/CAD amounts, and synthetic
cases. Search for **RF-1009** (Maple Grove Pantry, PAY-MAPLE-008). Open its
detail and scroll to **Share case** below **Case actions**. **Copy case link**
now shows **Case link copied.** This is the released version.

Direct link after signing in:
http://127.0.0.1:8001/cases/RF-1009/#copy-case-link

## 2. Compare before and after for change #1

Open http://127.0.0.1:8000/changes/1/. Show the reporter's original
plain-language issue, its case reference and route, the source diff,
independent browser check output, and the **Trace inspector**. The
frontend change took the enforced **review** route. The trace records a
tools-admin **Approve change**, then separate **Merged** and **Released**
events. It did not change any refund decision.

Keep two tabs open, signing in as `ops` if prompted:

- **Before:** http://127.0.0.1:8401/cases/RF-1009/ . Click **Copy case
  link**. It does nothing and shows no confirmation.
- **Checked candidate:** http://127.0.0.1:8301/cases/RF-1009/ . Click the
  same button. It copies the case URL and shows **Case link copied.**

The original baseline remains available after release so this comparison
does not require rolling the live refunds app backward.

## 3. Show automatic low-risk change #2

Open http://127.0.0.1:8000/changes/2/. Its actual diff changes only an
existing display string. Show the `auto` policy result, the red/green
browser output, and the **Merged** and **Released** trace events. There
was no software approval click.

Compare the queue description at http://127.0.0.1:8401/ (**Review
requets and track every decision.**) with the checked preview at
http://127.0.0.1:8302/ or released runtime at `:8001` (**Review requests
and track every decision.**).

Call the trace a **recorded sample workflow**. It shows the controller's
persisted events and checks, not Devin's internal reasoning or a live agent
session.
