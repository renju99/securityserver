# -*- coding: utf-8 -*-
"""Backfill visitor mobile_number so the column can become NOT NULL."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute(
        """
        SELECT count(*) FROM information_schema.columns
         WHERE table_name = 'visitor_management'
           AND column_name = 'mobile_number'
        """
    )
    if not cr.fetchone()[0]:
        return

    cr.execute(
        """
        UPDATE visitor_management
           SET mobile_number = 'N/A'
         WHERE mobile_number IS NULL
            OR btrim(mobile_number) = ''
        """
    )
    _logger.info(
        'Backfilled %s visitor_management.mobile_number null/empty rows with N/A',
        cr.rowcount,
    )
