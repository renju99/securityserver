# -*- coding: utf-8 -*-
"""
Ensure shift_template.site_id uses ON DELETE CASCADE so client.site records
can be deleted without FK errors (shift_template_site_id_fkey).

Python field ondelete='cascade' does not always recreate an existing PostgreSQL FK.
"""

import logging

_logger = logging.getLogger(__name__)

CONSTRAINT = "shift_template_site_id_fkey"


def migrate(cr, version):
    cr.execute(
        """
        SELECT c.confdeltype
        FROM pg_constraint c
        JOIN pg_class t ON c.conrelid = t.oid
        WHERE t.relname = 'shift_template'
          AND c.conname = %s
          AND c.contype = 'f'
        """,
        (CONSTRAINT,),
    )
    row = cr.fetchone()
    if not row:
        _logger.info(
            "Migration skip: FK %s not found on shift_template (table or name differs).",
            CONSTRAINT,
        )
        return
    # pg: a=restrict, c=cascade, n=set null, d=set default
    if row[0] == "c":
        _logger.info("FK %s already ON DELETE CASCADE; nothing to do.", CONSTRAINT)
        return

    _logger.info("Altering %s to ON DELETE CASCADE...", CONSTRAINT)
    cr.execute(
        """
        ALTER TABLE shift_template
        DROP CONSTRAINT shift_template_site_id_fkey
        """
    )
    cr.execute(
        """
        ALTER TABLE shift_template
        ADD CONSTRAINT shift_template_site_id_fkey
        FOREIGN KEY (site_id)
        REFERENCES client_site(id)
        ON DELETE CASCADE
        """
    )
    _logger.info("FK %s updated successfully.", CONSTRAINT)
