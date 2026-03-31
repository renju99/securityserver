# -*- coding: utf-8 -*-
"""
Restore shift_template.site_id FK to ON DELETE RESTRICT (no cascade).

Cascade removed so deleting a client.site does not remove shift.template rows.
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
            "Migration skip: FK %s not found on shift_template.",
            CONSTRAINT,
        )
        return
    if row[0] in ("r", "a"):
        _logger.info(
            "FK %s already RESTRICT/NO ACTION; nothing to do.", CONSTRAINT
        )
        return

    _logger.info("Altering %s to ON DELETE RESTRICT...", CONSTRAINT)
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
        ON DELETE RESTRICT
        """
    )
    _logger.info("FK %s updated successfully.", CONSTRAINT)
