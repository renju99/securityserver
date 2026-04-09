def migrate(cr, version):
    """Invalidate asset bundles after unified analytics template extraction (idempotent)."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    Att = env["ir.attachment"].sudo()
    base_names = (
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
    )
    Att.search([("name", "in", base_names)]).unlink()
    Att.search([("name", "=like", "web.assets_web%.xml")]).unlink()
    Att.search([("name", "=like", "web.assets_web.bundle%")]).unlink()
    Att.search([("name", "=like", "web.assets_backend%.xml")]).unlink()
