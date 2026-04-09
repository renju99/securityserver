def migrate(cr, version):
    """Remove inherited views that still reference removed field show_create_proposal_button.

    Without this, upgrading can fail: base form validates before XML drops the inherit,
    and the DB merge still contains the old arch.
    """
    cr.execute(
        """
        DELETE FROM ir_ui_view v
        WHERE v.inherit_id IN (
            SELECT imd.res_id
            FROM ir_model_data imd
            WHERE imd.model = 'ir.ui.view'
              AND imd.module = 'sales_bid_board'
              AND imd.name = 'view_bid_project_form'
        )
          AND COALESCE(v.arch_db, '') LIKE %s
        """,
        ("%show_create_proposal_button%",),
    )
