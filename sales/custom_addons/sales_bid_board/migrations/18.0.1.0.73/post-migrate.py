def migrate(cr, version):
    """Drop cached web.assets_web* attachments so bundles match the current manifest (no 404 on removed files)."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    names = (
        "web.assets_web.js",
        "web.assets_web.min.js",
        "web.assets_web.css",
        "web.assets_web.min.css",
        "web.assets_web.js.map",
        "web.assets_web.min.js.map",
        "web.assets_web.css.map",
        "web.assets_web.min.css.map",
    )
    Att = env["ir.attachment"].sudo()
    Att.search([("name", "in", names)]).unlink()
    Att.search([("name", "=like", "web.assets_web%.xml")]).unlink()
    Att.search([("name", "=like", "web.assets_web.bundle%")]).unlink()
