# Odoo 18 Sales Instance (Isolated)

This stack runs a separate Odoo 18 instance for Sales and does not modify anything in `../security`.

## Isolation details

- Separate project folder: `sales/`
- Separate containers: `odoo_sales`, `odoo_sales_db`
- Separate Docker volumes: `sales-odoo-db-data`, `sales-odoo-web-data`
- Separate database name: `sales`
- Separate host port: `8071` (mapped to Odoo container `8069`)

## Start

```bash
cd /home/azureuser/sales
docker compose up -d
```

Open: <http://localhost:8071>

## Stop

```bash
cd /home/azureuser/sales
docker compose down
```

## First-time DB initialization

On first launch, create the `sales` database in Odoo web UI if it is not auto-created.
Use the master password from `config/odoo.conf` (`admin_passwd`).

## Custom add-ons

Application code lives under `custom_addons/`. Install or upgrade modules from **Apps** after syncing that path into the container (see your deployment notes).

| Module | Role |
|--------|------|
| `sales_bid_board` | Main Sales app: bid/no-bid pipeline, enquiries, proposals, CRM intake, dashboards, and reporting |
| `muk_web_appsbar`, `muk_web_chatter`, `muk_web_colors`, `muk_web_dialog`, `muk_web_theme` | MuK web UI extensions (theme and chrome) |

### Sales Bid Board (`sales_bid_board`)

- **Purpose:** Manage **enquiries** (`bid.project`) through stages, governance (review queue, submit-for-review rules), **submissions**, **deadline reminders**, and **analytics** dashboards. Depends on `sale_management`, `crm`, `mail`, `web`, and `auth_oauth`.
- **CRM leads:** Standard `crm.lead` records gain **bid intake** fields (scope of work, location, opportunity date, remarks, and related tracking). Leads require customer, customer name, and contact name when `type` is `lead`. Server actions support creating a **Bid Board enquiry** from a lead or opportunity and link the enquiry back to CRM.
- **Proposals:** Model `bid.proposal` records formal proposals after a **Bid** decision on an enquiry. Enquiries expose smart buttons and actions to open or create proposals when the workflow allows (typically from **Bid / No Bid**).
- **Menus (high level):** **Bid Board** root → All Enquiries, New Enquiry, Leads, Bid / No Bid, Proposals, Review Queue, Submissions, Deadline Reminders; **Reports** → Project Reports; **Analytics** → **Bid Board Analytics** (single tabbed action: Leads, Enquiries, By sales rep, Proposals, Activity & reminders); **Configuration** (managers) → Settings, Email Schedule, Submit Threshold, Team; **Documentation** (in-app training content).
- **Proposal flow-through:** Proposal records inherit key context from the linked enquiry, including services text and scope-of-work percentages (Cleaning, Maintenance, Security, Landscaping, Laundry, Support, Others, Total).

Module-specific upgrade and rollout steps (including two-phase field rollouts) are documented in [custom_addons/sales_bid_board/DEPLOY_CHECKLIST.md](custom_addons/sales_bid_board/DEPLOY_CHECKLIST.md).

End-to-end **workflow** (where work starts, CSO review, how an enquiry ends, and optional proposals) is in [custom_addons/sales_bid_board/WORKFLOW.md](custom_addons/sales_bid_board/WORKFLOW.md).
