# -*- coding: utf-8 -*-
"""Pre-migration for 18.0.1.1.64.

The unified mobile outbox is brand new, so there's no legacy data to
re-shape. This script exists purely to keep the migrations history
consistent and to defensively ensure that if the model is ever
loaded onto a DB where somebody already created a table with the
same name (very unlikely), we don't crash on column creation.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # If a stale ``guardpro_mobile_outbox`` table somehow exists,
    # touch it up so the new columns can be added cleanly. Otherwise
    # Odoo's ORM will create it fresh when the module loads.
    cr.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'guardpro_mobile_outbox'
        )
    """)
    row = cr.fetchone()
    exists = bool(row and row[0])
    if not exists:
        _logger.info(
            'guardpro_mobile_outbox table does not exist yet - ORM will '
            'create it during module install.'
        )
        return

    cr.execute("""
        ALTER TABLE guardpro_mobile_outbox
            ADD COLUMN IF NOT EXISTS dedup_key VARCHAR,
            ADD COLUMN IF NOT EXISTS expiry_date TIMESTAMP,
            ADD COLUMN IF NOT EXISTS acked BOOLEAN DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS acked_on TIMESTAMP,
            ADD COLUMN IF NOT EXISTS priority VARCHAR DEFAULT 'normal',
            ADD COLUMN IF NOT EXISTS kind VARCHAR DEFAULT 'other',
            ADD COLUMN IF NOT EXISTS res_model VARCHAR,
            ADD COLUMN IF NOT EXISTS res_id INTEGER,
            ADD COLUMN IF NOT EXISTS deep_link VARCHAR;
    """)
    _logger.info('guardpro_mobile_outbox columns back-filled (defensive).')
