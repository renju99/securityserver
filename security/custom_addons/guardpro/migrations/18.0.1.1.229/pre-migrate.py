# -*- coding: utf-8 -*-
"""
Migration 18.0.1.1.229 — PTT performance indexes

Creates the partial index referenced in the /pending SQL query comment:
  idx_ptt_message_pending  (channel_id, id DESC)
  WHERE is_streaming = FALSE AND file_size > 4000

Also creates a supporting index on created_at used by the audio purge cron
and the stale-stream closer.

Safe to run multiple times (CREATE INDEX IF NOT EXISTS).
"""
import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    _logger.info("GuardLink PTT migration 18.0.1.1.229: creating performance indexes")

    # Partial index that makes the /pending SQL O(1) for any number of messages.
    # Covers: channel_id = ANY(...), is_streaming = FALSE, file_size > 4000, id DESC.
    cr.execute("""
        CREATE INDEX IF NOT EXISTS idx_ptt_message_pending
        ON push_to_talk_message (channel_id, id DESC)
        WHERE is_streaming = FALSE
          AND file_size     > 4000
    """)

    # Index used by cron_purge_old_audio and stale-stream queries.
    cr.execute("""
        CREATE INDEX IF NOT EXISTS idx_ptt_message_created_streaming
        ON push_to_talk_message (created_at)
        WHERE is_streaming = TRUE
    """)

    _logger.info("GuardLink PTT migration 18.0.1.1.229: indexes created successfully")
