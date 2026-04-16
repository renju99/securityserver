from . import controllers
from . import models


def post_init_hook(cr, registry):
    """Clean up retired menus/actions and legacy bid.training.documentation rows (removed in 18.0.1.0.5)."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})

    obsolete_training = (
        "training_doc_roles",
        "training_doc_projects",
        "training_doc_submissions_reminders",
        "training_doc_reports",
        "training_doc_admin",
        "training_doc_odoo_help",
        "training_doc_welcome",
        "training_doc_bid_no_bid_screen",
        "training_doc_scorecard",
        "training_doc_review",
    )
    env["ir.model.data"].search(
        [("module", "=", "sales_bid_board"), ("name", "in", list(obsolete_training))]
    ).unlink()

    for menu_xid in (
        "menu_bid_training_odoo_official",
        "menu_bid_training_documentation_topics",
        "menu_bid_training_documentation_root",
        "menu_bid_board_user_guide",
        "menu_bid_board_bid_no_bid_section",
    ):
        menu = env.ref(f"sales_bid_board.{menu_xid}", raise_if_not_found=False)
        if menu:
            menu.unlink()

    act = env.ref("sales_bid_board.action_odoo_sales_documentation_url", raise_if_not_found=False)
    if act:
        act.unlink()

    # Point Training menu at the client action before removing the legacy window action
    # (avoids "Missing Action" if the menu still referenced the old ir.actions.act_window row).
    training_menu = env.ref("sales_bid_board.menu_bid_board_bid_no_bid_training", raise_if_not_found=False)
    training_client = env.ref("sales_bid_board.action_bid_board_training_client", raise_if_not_found=False)
    if training_menu and training_client:
        training_menu.write({"action": "%s,%s" % (training_client._name, training_client.id)})

    # Legacy: window action on res.partner (replaced by ir.actions.client + OWL)
    legacy_training = env.ref("sales_bid_board.action_bid_training_documentation", raise_if_not_found=False)
    if legacy_training:
        legacy_training.unlink()

    env["ir.ui.view"].search([("model", "=", "bid.training.documentation")]).unlink()
    env["ir.model.access"].search(
        [
            "|",
            ("name", "=", "bid.training.documentation user"),
            ("name", "=", "bid.training.documentation manager"),
        ]
    ).unlink()
    cr.execute(
        """
        SELECT EXISTS (
            SELECT FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        ("bid_training_documentation",),
    )
    if cr.fetchone()[0]:
        cr.execute("DELETE FROM bid_training_documentation")
    legacy_model = env["ir.model"].search([("model", "=", "bid.training.documentation")])
    if legacy_model:
        legacy_model.unlink()

    # Ensure submit threshold parameter exists for score-gated submit checks.
    icp = env["ir.config_parameter"].sudo()
    if not icp.get_param("sales_bid_board.submit_review_min_score"):
        icp.set_param("sales_bid_board.submit_review_min_score", "70")

    # Legacy: Selection value "gemini_direct" was stored in ir.config_parameter; newer builds use a boolean instead.
    ext_prov = (icp.get_param("sales_bid_board.external_market_provider") or "").strip().lower()
    if ext_prov == "gemini_direct":
        icp.set_param("sales_bid_board.external_market_provider", "google_search_api")
        icp.set_param("sales_bid_board.external_market_gemini_direct", "True")

    # Cached web client bundles can omit newly added addon JS until regenerated; drop them on install.
    att = env["ir.attachment"].sudo()
    att.search(
        [
            (
                "name",
                "in",
                (
                    "web.assets_web.js",
                    "web.assets_web.min.js",
                    "web.assets_web.css",
                    "web.assets_web.min.css",
                    "web.assets_web.js.map",
                    "web.assets_web.min.js.map",
                    "web.assets_web.css.map",
                    "web.assets_web.min.css.map",
                    "web.assets_backend.js",
                    "web.assets_backend.min.js",
                    "web.assets_backend.css",
                    "web.assets_backend.min.css",
                ),
            ),
        ]
    ).unlink()
    att.search([("name", "=like", "web.assets_web%.xml")]).unlink()
    att.search([("name", "=like", "web.assets_web.bundle%")]).unlink()
    att.search([("name", "=like", "web.assets_backend%.xml")]).unlink()

    # Keep Dashboards / Apps off the main app bar (see views/bid_restrict_global_apps_dashboards.xml).
    for menu_xmlid in (
        "spreadsheet_dashboard.spreadsheet_dashboard_menu_root",
        "base.menu_management",
    ):
        menu = env.ref(menu_xmlid, raise_if_not_found=False)
        if menu:
            menu.sudo().write({"active": False})

    registry.clear_cache()
