# -*- coding: utf-8 -*-
"""Fix checkpoint dropdown site_id on new tour lines (18.0.1.1.80)."""


def migrate(cr, version):
    cr.execute("""
        UPDATE security_tour_checkpoint_line line
        SET site_id = tour.site_id
        FROM security_tour tour
        WHERE line.tour_id = tour.id
          AND tour.site_id IS NOT NULL
          AND (line.site_id IS NULL OR line.site_id != tour.site_id)
    """)
