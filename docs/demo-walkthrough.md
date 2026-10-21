# FinCorp customer demo

Use **refunds at http://127.0.0.1:8001/** and the **change console at
http://127.0.0.1:8000/**. Sign in to refunds as `ops` / `ops-demo-2026`.
For software review, sign in to the console as `toolsadmin` /
`tools-demo-2026`. These are separate local demo accounts.

This is a **sample replay**, not a live Devin session. The candidate is a
real, locally authored commit. The worker performs real browser checks,
starts its preview, and enforces review and release policy. No agent session
or hidden reasoning is being shown.

## 1. Show the queue and reproduce the bug

Show the default refund queue, search and status filters, and USD/CAD amounts.
Search for **RF-1009** (Maple Grove Pantry) and open it. In the right column,
scroll past **Case actions** to **Share case**, then click **Copy case link**.
On this named baseline, nothing is copied and no confirmation appears.

To jump straight to the button after logging in, open
http://127.0.0.1:8001/cases/RF-1009/#copy-case-link.

## 2. Report it and compare the preview

On RF-1009, click **Report an issue / Request a change**. Enter:

> On RF-1009, Copy case link does nothing when I click it. I expected a link
> I can share and a confirmation.

Open **change #1** at http://127.0.0.1:8000/changes/1/. Wait for **Ready
for review**. Point out the attached case/route, locally authored candidate
revision, source diff, and trace. The trace records actual baseline and
preview browser checks. The frontend change is routed to **review**, not
automatic release.

Click **Open original version** to see the broken case at
http://127.0.0.1:8401/cases/RF-1009/. Open the candidate preview at
http://127.0.0.1:8301/cases/RF-1009/. Log in as `ops` if needed. On the
original, the button stays silent. On the preview, it shows **Case link
copied.** and copies the case URL.

## 3. Ship the reviewed change

In the console, sign in as `toolsadmin`. Review the preview and check output,
then click **Approve change**. Wait for **Merged**, then **Released**.
Refresh RF-1009 at `:8001` and confirm the button now works. This is
software approval; it does **not** approve a refund.

## 4. Show a low-risk automatic change

Return to the refund queue at `:8001`. Its description still says **Review
requets and track every decision.** Click the queue's **Report an issue /
Request a change** link and enter:

> Queue copy typo: Review requets and track every decision. should read
> Review requests and track every decision.

Open **change #2** at http://127.0.0.1:8000/changes/2/. The worker checks
the typo on the runtime and the correction in the preview at `:8302`.
The actual diff touches only an allowlisted display string, so the policy
routes it to **auto**. No approval click is required. Compare the original
queue at `:8401` with the preview or released queue at `:8001`, then point
out separate **Merged** and **Released** trace events.

Run #1 before #2: each fixture must be checked against the release that
actually exists at intake. The existing manual demo databases were preserved;
this customer walkthrough uses a separate checkout.
