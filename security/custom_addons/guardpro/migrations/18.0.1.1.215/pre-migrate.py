# -*- coding: utf-8 -*-
"""Allow supervisor/client PTT talkers without a guard.profile.

* Drop NOT NULL on ``push_to_talk_message.sender_guard_id``.
* Back-fill ``sender_user_id`` from the sender guard's user when empty.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("""
        SELECT 1 FROM information_schema.tables
         WHERE table_name = 'push_to_talk_message'
    """)
    if not cr.fetchone():
        return

    cr.execute("""
        SELECT is_nullable
          FROM information_schema.columns
         WHERE table_name = 'push_to_talk_message'
           AND column_name = 'sender_guard_id'
    """)
    row = cr.fetchone()
    if row and row[0] == 'NO':
        cr.execute("""
            ALTER TABLE push_to_talk_message
                ALTER COLUMN sender_guard_id DROP NOT NULL
        """)
        _logger.info('Dropped NOT NULL on push_to_talk_message.sender_guard_id')

    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'push_to_talk_message'
           AND column_name = 'sender_user_id'
    """)
    if not cr.fetchone():
        cr.execute("""
            ALTER TABLE push_to_talk_message
                ADD COLUMN sender_user_id INTEGER
        """)
        _logger.info('Added push_to_talk_message.sender_user_id')

    cr.execute("""
        UPDATE push_to_talk_message AS m
           SET sender_user_id = g.user_id
          FROM guard_profile AS g
         WHERE m.sender_user_id IS NULL
           AND m.sender_guard_id = g.id
           AND g.user_id IS NOT NULL
    """)
    _logger.info(
        'Back-filled sender_user_id on %s push-to-talk message(s)',
        cr.rowcount,
    )
