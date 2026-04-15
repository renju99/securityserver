# Bid Board — workflow (start to finish)

This document describes the **happy path** and **end states** for an opportunity in **Bid Board**. Menu names match the Odoo app **Bid Board**.

---

## 1. Where the workflow starts

You can begin in any of these places; all paths converge on an **enquiry** (`bid.project`).

| Start here | Typical use |
|------------|-------------|
| **Bid Board → Leads** | Intake in CRM: capture customer, scope, dates, then use server actions (where configured) to **create a Bid Board enquiry** linked to the lead. |
| **Bid Board → New Enquiry** (or **Bid / No Bid → All Records → New**) | Create an enquiry directly when there is no lead, or after verbal / email intake. |
| **Bid Board → Bid / No Bid** | Opens the decision-focused list (default filters for the scorecard / review workflow). |
| **Bid Board → Bid / No Bid → All Records** | Same model as Bid / No Bid; full list with no default decision filters. |

**First things to complete on the enquiry**

- **Project info**: client, team, contract value and duration, scope-of-work % (must not exceed 100%), deadlines, industry, emirate, notes.
- **Scorecard**: complete lines and weights; overall score drives the **Bid / No bid** recommendation (default rule: **≥ 70%** suggests **Bid**).

Optional: use **Save draft** while the bid team is still editing.

---

## 2. Middle of the workflow — governance

### 2.1 Submit for review (bid team)

1. When the scorecard and project info are ready, click **Submit for review**.
2. **Review status** becomes **Pending review**.
3. A row appears under **Bid Board → Bid / No Bid → Submissions** (audit trail).

**Submit threshold** (if enabled): submission may be blocked until the overall score reaches the minimum set in configuration.

### 2.2 CSO review (approvers)

CSO ability is controlled by **email** on **Bid Board → Configuration → Settings → CSO (Email Approvers)**, in addition to access groups.

From an enquiry in **Pending review** or **Change requested**, a CSO can:

| Action | Result |
|--------|--------|
| **Approve** | Review is **Approved**. Project **state** becomes **Completed** if final decision is **Bid**, or **Declined** if **No bid**. Open change requests are closed. Notifications may be sent per settings. |
| **Decline** | Review is **Declined**; project is treated as declined per your rules; notifications per settings. |
| **Request change** | **Review status** → **Change requested**; bid team edits and **Submit for review** again. |

Approvers often work from **Bid Board → Review & reminders → Review Queue** (if their role includes it).

---

## 3. Where the enquiry workflow ends

These are the **terminal outcomes** for the **enquiry** side of Bid Board:

| End state | Meaning |
|-----------|---------|
| **Approved + Bid** | CSO approved; final decision is **Bid**. Enquiry **state** is **Completed**. Team may proceed to **proposals** (below). |
| **Approved + No bid** | CSO approved; final decision is **No bid**. Enquiry **state** is **Declined**. No proposal is expected. |
| **Review declined** | CSO declined the submission. Enquiry is locked for typical users per your access rules. |
| **Stopped without submit** | Enquiry remains **Draft** or is abandoned; no CSO decision. (Operational choice, not a system “closed” type.) |

After **Approved**, non-CSO users are usually restricted from editing the enquiry; CSO / managers / administrators can override where policy allows.

---

## 4. After a **Bid** decision — proposals (optional continuation)

When an enquiry is **Approved** with final decision **Bid**, and the record is opened from **Bid / No Bid** (required context for the button):

1. **Create proposal** opens a new **Proposal** (`bid.proposal`) with defaults from the enquiry (including commercial fields and **scope of work** mirrored from the enquiry).
2. Track outcome on the proposal: **Open → Won** or **Lost** (header / status bar actions).

**End of proposal workflow** (commercial pipeline):

- **Won** or **Lost** marks the end of the proposal record’s lifecycle for reporting; the original enquiry remains the historical **Bid / No bid** decision record.

Use **Bid Board → Proposals** for the full list.

---

## 5. Supporting processes (parallel, not “end”)

| Area | Role |
|------|------|
| **Deadline reminders** | Automated T-7 / T-3 / T-1 style emails while the enquiry is active (per configuration). |
| **Change requests** | Visible on the enquiry; resolved when review completes. |
| **Bid Board Analytics** | Reporting and drill-down across leads, enquiries, reps, proposals, activity. |
| **Project Reports** | Pivot/list reporting on enquiries. |

---

## 6. One-page diagram (mental model)

```text
START ──► Lead / New enquiry / Open enquiry
            │
            ▼
        Project info + Scorecard
            │
            ▼
        Submit for review ──► Pending review
            │
            ├─► Request change ──► edit ──► Submit again ──┐
            │                                                 │
            ├─► Decline ─────────────────────────► END (declined)
            │
            ▼
        Approve ──► final decision Bid or No bid
            │
            ├─► No bid ──────────────────────────► END (enquiry declined)
            │
            └─► Bid ──► (optional) Create proposal ──► Open ──► Won / Lost ──► END
```

---

## 7. Related docs

- In-app help: **Bid Board → Documentation** → section **Workflow: start to finish** (same content, readable inside Odoo)
- Deployment and upgrades: `DEPLOY_CHECKLIST.md`
- Sales stack overview: `../../README.md` (repo root `sales/README.md`)
