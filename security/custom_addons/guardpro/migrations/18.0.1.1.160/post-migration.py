"""Backfill empty site_ids on visitor.watchlist / visitor.host.

Legacy migration left unassigned entries admin-only. Assign sites from:
1) linked visitor history
2) creator / added_by user.site_ids (guardpro_user_site_rel)
3) all active sites (last resort so records are never invisible to site staff)
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Hosts: from historical visitor visits (idempotent)
    cr.execute(
        """
        INSERT INTO visitor_host_site_rel (host_id, site_id)
        SELECT DISTINCT v.host_id, v.site_id
          FROM visitor_management v
         WHERE v.host_id IS NOT NULL
           AND v.site_id IS NOT NULL
           AND NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r
                 WHERE r.host_id = v.host_id AND r.site_id = v.site_id
           )
        """
    )
    _logger.info('Host site backfill from visitors: %s rows', cr.rowcount)

    # Hosts still empty: creator's sites
    cr.execute(
        """
        INSERT INTO visitor_host_site_rel (host_id, site_id)
        SELECT DISTINCT h.id, rel.site_id
          FROM visitor_host h
          JOIN guardpro_user_site_rel rel ON rel.user_id = h.create_uid
         WHERE NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r WHERE r.host_id = h.id
           )
           AND NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r2
                 WHERE r2.host_id = h.id AND r2.site_id = rel.site_id
           )
        """
    )
    _logger.info('Host site backfill from create_uid sites: %s', cr.rowcount)

    # Watchlist: sites from matching visitors by id_number or name
    cr.execute(
        """
        INSERT INTO visitor_watchlist_site_rel (watchlist_id, site_id)
        SELECT DISTINCT w.id, v.site_id
          FROM visitor_watchlist w
          JOIN visitor_management v
            ON v.site_id IS NOT NULL
           AND (
                (w.id_number IS NOT NULL AND w.id_number <> ''
                 AND upper(regexp_replace(COALESCE(v.id_number, ''), '[\\s\\-]', '', 'g'))
                   = upper(regexp_replace(w.id_number, '[\\s\\-]', '', 'g')))
                OR (w.name IS NOT NULL AND lower(COALESCE(v.name, '')) = lower(w.name))
           )
         WHERE NOT EXISTS (
                SELECT 1 FROM visitor_watchlist_site_rel r
                 WHERE r.watchlist_id = w.id AND r.site_id = v.site_id
           )
        """
    )
    _logger.info('Watchlist site backfill from visitors: %s rows', cr.rowcount)

    # Watchlist still empty: added_by / create_uid sites
    cr.execute(
        """
        INSERT INTO visitor_watchlist_site_rel (watchlist_id, site_id)
        SELECT DISTINCT w.id, rel.site_id
          FROM visitor_watchlist w
          JOIN guardpro_user_site_rel rel
            ON rel.user_id = COALESCE(w.added_by, w.create_uid)
         WHERE NOT EXISTS (
                SELECT 1 FROM visitor_watchlist_site_rel r WHERE r.watchlist_id = w.id
           )
           AND NOT EXISTS (
                SELECT 1 FROM visitor_watchlist_site_rel r2
                 WHERE r2.watchlist_id = w.id AND r2.site_id = rel.site_id
           )
        """
    )
    _logger.info('Watchlist site backfill from added_by sites: %s', cr.rowcount)

    # Last resort: all active sites (avoids admin-only orphans)
    cr.execute(
        """
        INSERT INTO visitor_host_site_rel (host_id, site_id)
        SELECT h.id, s.id
          FROM visitor_host h
         CROSS JOIN client_site s
         WHERE COALESCE(s.active, TRUE) = TRUE
           AND NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r WHERE r.host_id = h.id
           )
           AND NOT EXISTS (
                SELECT 1 FROM visitor_host_site_rel r2
                 WHERE r2.host_id = h.id AND r2.site_id = s.id
           )
        """
    )
    _logger.info('Host site last-resort all-sites assign: %s', cr.rowcount)

    cr.execute(
        """
        INSERT INTO visitor_watchlist_site_rel (watchlist_id, site_id)
        SELECT w.id, s.id
          FROM visitor_watchlist w
         CROSS JOIN client_site s
         WHERE COALESCE(s.active, TRUE) = TRUE
           AND NOT EXISTS (
                SELECT 1 FROM visitor_watchlist_site_rel r WHERE r.watchlist_id = w.id
           )
           AND NOT EXISTS (
                SELECT 1 FROM visitor_watchlist_site_rel r2
                 WHERE r2.watchlist_id = w.id AND r2.site_id = s.id
           )
        """
    )
    _logger.info('Watchlist site last-resort all-sites assign: %s', cr.rowcount)

    _logger.info('Completed guardpro 18.0.1.1.160 watchlist/host site backfill')
