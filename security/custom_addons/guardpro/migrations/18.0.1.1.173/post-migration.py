"""Enable 13h auto-checkout cron and close already-stale open sessions."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Ensure cron exists (XML under noupdate parent may skip on some upgrades)
    cr.execute(
        """
        SELECT res_id FROM ir_model_data
         WHERE module = 'guardpro'
           AND name = 'cron_auto_checkout_stale_attendance'
           AND model = 'ir.cron'
        """
    )
    row = cr.fetchone()
    if row:
        # Odoo 18: code lives on ir_act_server, not ir_cron
        cr.execute(
            """
            UPDATE ir_cron
               SET active = TRUE,
                   interval_number = 15,
                   interval_type = 'minutes'
             WHERE id = %s
            """,
            (row[0],),
        )
        cr.execute(
            """
            UPDATE ir_act_server AS s
               SET code = 'model.cron_auto_checkout_stale_sessions(13)'
              FROM ir_cron AS c
             WHERE c.id = %s
               AND s.id = c.ir_actions_server_id
            """,
            (row[0],),
        )
        _logger.info('Activated auto-checkout cron id=%s', row[0])
    else:
        cr.execute(
            "SELECT id FROM ir_model WHERE model = 'guard.attendance' LIMIT 1"
        )
        model_row = cr.fetchone()
        if model_row:
            cr.execute(
                """
                INSERT INTO ir_act_server (
                    name, model_id, state, code,
                    create_uid, create_date, write_uid, write_date
                )
                VALUES (
                    'GuardLink: Auto Check-Out After 13 Hours',
                    %s, 'code', 'model.cron_auto_checkout_stale_sessions(13)',
                    1, (NOW() AT TIME ZONE 'UTC'),
                    1, (NOW() AT TIME ZONE 'UTC')
                )
                RETURNING id
                """,
                (model_row[0],),
            )
            action_id = cr.fetchone()[0]
            cr.execute(
                """
                INSERT INTO ir_cron (
                    cron_name, ir_actions_server_id,
                    interval_number, interval_type, active, priority,
                    create_uid, create_date, write_uid, write_date,
                    user_id, nextcall
                )
                VALUES (
                    'GuardLink: Auto Check-Out After 13 Hours',
                    %s,
                    15, 'minutes', TRUE, 5,
                    1, (NOW() AT TIME ZONE 'UTC'),
                    1, (NOW() AT TIME ZONE 'UTC'),
                    1, (NOW() AT TIME ZONE 'UTC')
                )
                RETURNING id
                """,
                (action_id,),
            )
            cron_id = cr.fetchone()[0]
            cr.execute(
                """
                INSERT INTO ir_model_data (name, module, model, res_id, noupdate)
                VALUES ('cron_auto_checkout_stale_attendance', 'guardpro', 'ir.cron', %s, TRUE)
                ON CONFLICT DO NOTHING
                """,
                (cron_id,),
            )
            _logger.info('Created auto-checkout cron id=%s', cron_id)
        else:
            _logger.warning('guard.attendance model not found; skipped cron create')

    # Close open sessions already past 13 hours (checkout = checkin + 13h)
    cr.execute(
        """
        UPDATE guard_attendance
           SET checkout_time = checkin_time + INTERVAL '13 hours',
               checkout_method = COALESCE(checkout_method, 'manual'),
               checkout_notes = CASE
                   WHEN checkout_notes IS NULL OR btrim(checkout_notes) = ''
                   THEN 'Automatically checked out after 13 hours (forgot check-out).'
                   ELSE checkout_notes || E'\n'
                        || 'Automatically checked out after 13 hours (forgot check-out).'
               END
         WHERE checkout_time IS NULL
           AND checkin_time IS NOT NULL
           AND checkin_time <= (NOW() AT TIME ZONE 'UTC') - INTERVAL '13 hours'
        """
    )
    _logger.info('Closed stale open attendances (>13h): %s', cr.rowcount)

    # Linked shifts with no remaining open attendance → completed if past end
    cr.execute(
        """
        UPDATE guard_shift AS s
           SET status = 'completed'
         WHERE s.status IN ('scheduled', 'confirmed', 'in_progress', 'no_show')
           AND s.end_datetime < (NOW() AT TIME ZONE 'UTC')
           AND EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id AND a.checkin_time IS NOT NULL
           )
           AND NOT EXISTS (
               SELECT 1 FROM guard_attendance a
                WHERE a.shift_id = s.id
                  AND a.checkin_time IS NOT NULL
                  AND a.checkout_time IS NULL
           )
        """
    )
    _logger.info('Completed shifts after auto-checkout: %s', cr.rowcount)
