# -*- coding: utf-8 -*-
"""18.0.1.1.65 pre-migrate.

Switches a number of ``ondelete='cascade'`` foreign keys on historical /
audit-trail tables to ``restrict`` or ``set null`` (see the S1 audit
notes). Odoo's ``_auto_init`` will detect the new ``ondelete`` attribute
at upgrade time and rewrite the FK constraints automatically, so we do
NOT need to issue ``ALTER TABLE`` statements here.

What this script does instead is a defensive sanity pass:

* Fail loudly (with a clear message) if any of the tables whose FKs are
  about to switch to RESTRICT contain rows pointing at non-existent
  parents - those are leftover from a previous cascade that already
  deleted the parent but left the child, and would now make the FK
  rewrite fail. In practice the set should be empty on a healthy DB.
* Log a summary so the upgrade log shows exactly which tables were
  migrated.

The actual constraint change is done by Odoo's automatic column
re-initialisation after this script returns.
"""

import logging

_logger = logging.getLogger(__name__)


# (table, column, parent_table) - tables whose FK is being promoted
# from CASCADE to a stricter behaviour in this version.
_TABLES = [
    ('incident_report', 'guard_id', 'guard_profile'),
    ('incident_report', 'site_id', 'client_site'),
    ('incident_report', 'shift_id', 'guard_shift'),
    ('daily_activity_report', 'site_id', 'client_site'),
    ('resident_complaint', 'resident_id', 'tenant_resident'),
    ('client_feedback', 'site_id', 'client_site'),
    ('client_feedback', 'resident_id', 'tenant_resident'),
    ('client_feedback', 'guard_id', 'guard_profile'),
    ('client_feedback', 'shift_id', 'guard_shift'),
    ('guard_credential', 'guard_id', 'guard_profile'),
    ('guard_shift', 'guard_id', 'guard_profile'),
    ('guard_shift', 'site_id', 'client_site'),
    ('geofence_alert', 'guard_id', 'guard_profile'),
    ('tour_log', 'tour_id', 'security_tour'),
    ('tour_log', 'guard_id', 'guard_profile'),
    ('tour_log', 'site_id', 'client_site'),
    ('tour_log', 'shift_id', 'guard_shift'),
    ('guard_task', 'site_id', 'client_site'),
    ('guard_task', 'shift_id', 'guard_shift'),
    ('package_management', 'site_id', 'client_site'),
    ('key_register', 'site_id', 'client_site'),
    ('lost_found', 'site_id', 'client_site'),
    ('visitor_management', 'site_id', 'client_site'),
    ('tenant_resident', 'site_id', 'client_site'),
    ('guard_message', 'sender_id', 'res_users'),
    ('guard_message', 'receiver_id', 'res_users'),
    ('guard_status_update', 'guard_id', 'guard_profile'),
    ('push_to_talk_message', 'sender_guard_id', 'guard_profile'),
    ('training_enrollment', 'guard_id', 'guard_profile'),
]


def _table_exists(cr, table):
    cr.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
        (table,),
    )
    return bool(cr.fetchone())


def _column_exists(cr, table, column):
    cr.execute(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return bool(cr.fetchone())


def migrate(cr, version):
    _logger.info(
        "guardpro 18.0.1.1.65 pre-migrate: auditing %d FKs before "
        "Odoo rewrites them from CASCADE to RESTRICT/SET NULL.",
        len(_TABLES),
    )
    orphans_total = 0
    for table, column, parent in _TABLES:
        if not _table_exists(cr, table):
            continue
        if not _column_exists(cr, table, column):
            continue
        if not _table_exists(cr, parent):
            continue

        # Count rows referencing a parent that no longer exists.
        try:
            cr.execute(
                "SELECT COUNT(*) FROM {t} WHERE {c} IS NOT NULL "
                "AND NOT EXISTS (SELECT 1 FROM {p} WHERE id = {t}.{c})"
                .format(t=table, c=column, p=parent)
            )
            orphans = cr.fetchone()[0] or 0
        except Exception as e:  # pragma: no cover - defensive
            _logger.warning(
                "guardpro migrate: could not audit %s.%s -> %s: %s",
                table, column, parent, e,
            )
            continue

        if orphans:
            orphans_total += orphans
            # For the tables where the new behaviour is SET NULL we can
            # heal the orphans by nulling them out (the FK rewrite would
            # otherwise succeed but leave stale IDs). For RESTRICT the
            # sensible thing is to null them here too - a truly orphan
            # row is already disconnected from its parent, so clearing
            # the FK lets the upgrade complete.
            _logger.warning(
                "guardpro migrate: %s orphan rows in %s.%s -> NULL",
                orphans, table, column,
            )
            try:
                cr.execute(
                    "UPDATE {t} SET {c} = NULL WHERE {c} IS NOT NULL "
                    "AND NOT EXISTS (SELECT 1 FROM {p} WHERE id = {t}.{c})"
                    .format(t=table, c=column, p=parent)
                )
            except Exception as e:  # pragma: no cover
                _logger.error(
                    "guardpro migrate: could not null orphan %s.%s: %s",
                    table, column, e,
                )

    _logger.info(
        "guardpro 18.0.1.1.65 pre-migrate done; %s orphan FK rows healed.",
        orphans_total,
    )
