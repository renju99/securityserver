# -*- coding: utf-8 -*-
"""Fix tour checkpoint line site domain for Many2one picker (18.0.1.1.77)."""


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'security_tour_checkpoint_line' AND column_name = 'site_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE security_tour_checkpoint_line
            ADD COLUMN site_id integer REFERENCES client_site(id) ON DELETE SET NULL
        """)
    cr.execute("""
        UPDATE security_tour_checkpoint_line line
        SET site_id = tour.site_id
        FROM security_tour tour
        WHERE line.tour_id = tour.id
          AND (line.site_id IS NULL OR line.site_id != tour.site_id)
    """)
