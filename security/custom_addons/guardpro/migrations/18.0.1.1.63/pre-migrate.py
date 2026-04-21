# -*- coding: utf-8 -*-
"""Pre-migration for 18.0.1.1.63.

Adds the mobile assignment notification tracking columns on ``guard_task``
with sane defaults so the backfill does not have to run after Odoo has
already filled every row with ``False``. Without this step, every already-
assigned task in the database would fire a phone notification on the very
next poll after deployment, which would hammer guards with hundreds of
historical alerts.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Column creations are idempotent - SQL IF NOT EXISTS guards against
    # rerunning the migration on a freshly restored DB.
    cr.execute("""
        ALTER TABLE guard_task
            ADD COLUMN IF NOT EXISTS mobile_assignment_ack BOOLEAN,
            ADD COLUMN IF NOT EXISTS mobile_assignment_notified_on TIMESTAMP,
            ADD COLUMN IF NOT EXISTS mobile_assignment_acked_on TIMESTAMP;
    """)

    # Back-fill existing rows as "already acknowledged" so we don't flood
    # guards with notifications about tasks assigned before this feature
    # existed.
    cr.execute("""
        UPDATE guard_task
           SET mobile_assignment_ack = TRUE
         WHERE mobile_assignment_ack IS NULL;
    """)
    _logger.info(
        'guard_task mobile assignment columns back-filled to acknowledged=TRUE.'
    )
