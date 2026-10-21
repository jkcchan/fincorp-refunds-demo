# FinCorp demo: broken runtime, checked preview

Open **refunds** at http://127.0.0.1:8001/ as `ops` /
`ops-demo-2026`. Open the **change console** at
http://127.0.0.1:8000/ as `toolsadmin` / `tools-demo-2026`.

This is a **sample replay** with a real, locally authored candidate commit
and real browser checks. It is **not** a live Devin session. Do not present
the trace as Devin's reasoning or the patch as Devin-generated.

## 1. Show the broken button at :8001

Show the search, status and assignee filters, USD/CAD amounts, and synthetic
cases. Search for **RF-1009** (Maple Grove Pantry, PAY-MAPLE-008). Open it
and scroll to **Share case** below **Case actions**, or use this direct link
after signing in:

http://127.0.0.1:8001/cases/RF-1009/#copy-case-link

Click **Copy case link**. On the **actual :8001 runtime**, nothing is copied
and no confirmation appears. The refund case itself is unchanged.

## 2. Compare change #1 in review

The plain-language issue has already been filed. Open
http://127.0.0.1:8000/changes/1/. It is **Ready for review**, not
released. Show the attached case and route, source diff, browser check
output, and **Trace inspector**. The behavioral fix is enforced as
`review`; no software approval has been recorded.

Open the checked preview at
http://127.0.0.1:8301/cases/RF-1009/ and sign in as `ops` if prompted.
Click the same button. It copies the case URL and shows **Case link
copied.** Keep the broken :8001 page next to it for the red/green contrast.
The preview also works inside the console's review workspace.

If you decide to ship during the demo, click **Approve change** as
`toolsadmin`. Wait for separate **Merged** and **Released** events; only
then will :8001 show the fixed behavior. **Approve refund** is unrelated.
Do not click this until you have finished showing the broken runtime.

## 3. Show the recorded automatic copy change

The current queue at :8001 still reads **Review requets and track every
decision.** Open http://127.0.0.1:8000/changes/2/. This is a **read-only
recording from a prior isolated sample run**, not the release deployed on
:8001 right now.

Show the original plain-language typo report, source diff limited to
`refunds/copy.json`, enforced `auto` route, passing browser checks, and
the actual **Merged** and **Released** trace events from that earlier
run. There was no human approval click. The console labels both the row
and detail page as a prior-cycle recording.

Compare the live queue at http://127.0.0.1:8001/ (**Review requets**)
with the recording's working candidate preview at
http://127.0.0.1:8352/ (**Review requests**). The recorded auto-release
commit is genuine, but the current runtime intentionally stays on the
broken baseline so change #1 can remain in review. Do not say #2's
release is currently deployed at :8001.
