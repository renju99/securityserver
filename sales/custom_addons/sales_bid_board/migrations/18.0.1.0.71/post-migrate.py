def migrate(cr, version):
    """Remove legacy Analytics submenu items replaced by Bid Board Analytics."""
    cr.execute(
        """
        DELETE FROM ir_ui_menu m
        WHERE m.id IN (
            SELECT imd.res_id
            FROM ir_model_data imd
            WHERE imd.model = 'ir.ui.menu'
              AND imd.module = 'sales_bid_board'
              AND imd.name IN (
                  'menu_bid_board_analytics_dashboard',
                  'menu_bid_board_salesperson_analytics_dashboard',
                  'menu_bid_board_dashboards'
              )
        )
        """
    )
    cr.execute(
        """
        DELETE FROM ir_model_data
        WHERE model = 'ir.ui.menu'
          AND module = 'sales_bid_board'
          AND name IN (
              'menu_bid_board_analytics_dashboard',
              'menu_bid_board_salesperson_analytics_dashboard',
              'menu_bid_board_dashboards'
          )
        """
    )
