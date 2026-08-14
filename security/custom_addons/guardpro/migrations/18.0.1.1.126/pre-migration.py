# -*- coding: utf-8 -*-
"""Migrate shift.template tour_id (Many2one) to tour_ids (Many2many)."""

import logging

_logger = logging.getLogger(__name__)

REL_TABLE = 'shift_template_tour_rel'


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'shift_template' AND column_name = 'tour_id'
        """
    )
    if not cr.fetchone():
        _logger.info('shift_template.tour_id already removed; skipping tour migration.')
        return

    cr.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {REL_TABLE} (
            template_id INTEGER NOT NULL
                REFERENCES shift_template(id) ON DELETE CASCADE,
            tour_id INTEGER NOT NULL
                REFERENCES security_tour(id) ON DELETE CASCADE,
            PRIMARY KEY (template_id, tour_id)
        )
        """
    )

    cr.execute(
        f"""
        INSERT INTO {REL_TABLE} (template_id, tour_id)
        SELECT id, tour_id FROM shift_template
        WHERE tour_id IS NOT NULL
        ON CONFLICT (template_id, tour_id) DO NOTHING
        """
    )
    _logger.info('Migrated shift_template.tour_id values into %s.', REL_TABLE)
