def migrate(cr, version):
    """Drop legacy client actions replaced by Bid Board Analytics (unified)."""
    cr.execute(
        """
        DELETE FROM ir_act_client a
        WHERE a.id IN (
            SELECT imd.res_id
            FROM ir_model_data imd
            WHERE imd.model = 'ir.actions.client'
              AND imd.module = 'sales_bid_board'
              AND imd.name IN (
                  'action_sales_bid_board_dashboard_client',
                  'action_sales_bid_board_salesperson_dashboard_client'
              )
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'ir.actions.client'
          AND module = 'sales_bid_board'
          AND name IN (
              'action_sales_bid_board_dashboard_client',
              'action_sales_bid_board_salesperson_dashboard_client'
          )
        """
    )
