# Sales Bid Board Deployment Checklist

Use this checklist whenever you deploy `sales_bid_board`, especially when adding/changing model fields.

## Troubleshooting: upgrade “hangs” or Docker looks stuck

- **`OSError: [Errno 98] Address already in use`** (or the command never finishes): you started a **second** Odoo process **inside the same container** while the main app is already listening on **8069** (multi-worker mode). The upgrade process tries to bind that port and fails or blocks.

  **Fix — pick one:**

  1. **In-place upgrade (container keeps running):** always pass **`--no-http`** so the upgrade process does not start HTTP:

     ```bash
     docker exec odoo_sales odoo -c /etc/odoo/odoo.conf -d sales -u sales_bid_board --stop-after-init --no-http
     ```

  2. **One-off container (no second listener on 8069):** stop the app container, run upgrade, start again (see “Recommended local command” below).

- **Upgrading from Odoo Apps UI:** the server may sit on “loading” for a while during registry reload; that is normal on large databases. If it never completes, check `/var/lib/odoo/odoo.log` in the container for tracebacks.

---

## Goal

Prevent upgrade failures like:
- `Field "... does not exist in model ..."`
- view parse errors during `-u sales_bid_board`
- OWL runtime errors caused by XML/Python mismatch

---

## Pre-Deployment

- Confirm all required changes are in one release artifact:
  - Python model changes (`models/*.py`)
  - XML view changes (`views/*.xml`)
  - manifest version bump (`__manifest__.py`)
- Confirm deployment target uses the same addon path as expected (`/mnt/extra-addons/sales_bid_board`).
- Confirm there are no partial file sync jobs still running.

---

## Safe Rollout for New Fields (Two-Phase)

### Phase 1: Backend First (No XML reference to new field)

1. Deploy Python changes that define the new field(s).
2. Ensure XML views do **not** reference the new field yet.
3. Restart Odoo (all workers/instances).
4. Run upgrade:

   ```bash
   docker exec odoo_sales odoo -c /etc/odoo/odoo.conf -d sales -u sales_bid_board --stop-after-init --no-http
   ```

5. Verify parameter key is readable (Odoo shell):

   ```python
   env["ir.config_parameter"].sudo().get_param("sales_bid_board.submit_review_min_score")
   ```

   Expected: numeric string value (for example `"70"`).

### Phase 2: UI Exposure

1. Deploy XML that references the new field in views.
2. Restart Odoo (all workers/instances).
3. Run upgrade again:

   ```bash
   docker exec odoo_sales odoo -c /etc/odoo/odoo.conf -d sales -u sales_bid_board --stop-after-init --no-http
   ```

4. Hard refresh browser (`Ctrl+Shift+R`).
5. Validate the screen that renders the field opens without error.

---

## Standard Upgrade Procedure (Any Release)

1. Deploy release files.
2. Restart Odoo service/container.
3. Upgrade module:

   ```bash
   docker exec odoo_sales odoo -c /etc/odoo/odoo.conf -d sales -u sales_bid_board --stop-after-init --no-http
   ```

4. Verify:
   - no traceback in upgrade output
   - key menus open (`Bid Board`, `Documentation`, `Settings`)
   - key actions run (`Submit for Review`, CSO actions, server actions on CRM if used)
   - `Bid Board -> Analytics -> Bid Board Analytics` opens without action-registry errors
   - KPI / chart / table drill-down opens target lists and forms

### Recommended local command (docker-compose stack)

If `odoo_sales` is already running, avoid port bind conflicts by running upgrade in a one-off container:

```bash
cd /home/azureuser/sales
docker-compose stop odoo_sales
docker-compose run --rm --no-deps odoo_sales odoo -c /etc/odoo/odoo.conf -d sales -u sales_bid_board --stop-after-init
docker-compose start odoo_sales
```

---

## Post-Deployment Functional Checks

- Open `Bid Board -> Configuration -> Settings`.
- Open `Bid Board -> Leads` and a lead form: intake fields (scope of work, location, opportunity date, etc.) load; required customer / name fields behave as expected.
- Open a project (enquiry) form and confirm header buttons render correctly, including proposal-related actions when the enquiry is in an allowed state.
- Confirm `Submit for Review` behavior:
  - visible/hidden as expected
  - blocked server-side if below threshold (if enabled in this release)
- Open `Bid Board -> Proposals` (list loads); from an approved **Bid** enquiry, exercise **Create proposal** / view proposals if your release includes that flow.
- Open a proposal linked to an enquiry and verify **Scope of work (from enquiry)** values match the source enquiry.
- In proposal and Bid/No Bid list views, verify contract value columns are visible and positioned as expected.
- Open `Bid Board -> Reports -> Project Reports` and run a print/report on a sample enquiry if applicable.
- Open `Documentation` page.
- Confirm no new JS/Owl errors in browser console.

---

## Recovery (If Upgrade Fails)

If error says field is missing in model:

1. Remove the field from XML views (temporary rollback in views only).
2. Bump `__manifest__.py` version.
3. Restart Odoo.
4. Run module upgrade again.
5. Reattempt two-phase rollout.

If error says action/tag missing:

1. Confirm JS asset is deployed.
2. Upgrade module.
3. Restart Odoo.
4. Hard refresh browser.

---

## Team Rules (Do Not Skip)

- Never deploy XML referencing fields that are not yet loaded in Python on the same running server.
- Always restart before upgrading when model fields changed.
- In multi-instance setups, restart all app instances before running upgrade.
- Keep fallback-safe backend code when introducing staged rollouts.

