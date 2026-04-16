def migrate(cr, version):
    """Before XML drops deprecated res.groups, ensure members keep Sales Manager access."""
    from odoo import SUPERUSER_ID, api

    env = api.Environment(cr, SUPERUSER_ID, {})
    deprecated_names = (
        "group_bid_board_team_leader",
        "group_bid_board_bid_manager",
        "group_bid_board_commercial_manager",
        "group_bid_board_user",
        "group_bid_board_reviewer",
    )
    imd = env["ir.model.data"].sudo()
    sm = env.ref("sales_bid_board.group_bid_board_sales_manager", raise_if_not_found=False)
    if not sm:
        return
    for name in deprecated_names:
        row = imd.search(
            [
                ("module", "=", "sales_bid_board"),
                ("model", "=", "res.groups"),
                ("name", "=", name),
            ],
            limit=1,
        )
        if not row or not row.res_id:
            continue
        group = env["res.groups"].sudo().browse(row.res_id)
        if not group.exists():
            continue
        for user in group.users:
            if sm not in user.groups_id:
                user.sudo().write({"groups_id": [(4, sm.id)]})
