"""Backfill Community Violation structured fields from excel form values."""

import logging
from datetime import datetime

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    # Repair recent COMM_VIO / community parents that have form values but empty
    # violation_* columns (mobile saved excel values only).
    cr.execute(
        """
        SELECT i.id
          FROM incident_report i
          JOIN incident_form_parent p ON p.id = i.form_parent_id
         WHERE p.code IN ('COMM_VIO', 'DOOR_LOCK', 'PARK_VIO', 'PROP_REM',
                          'MOVE_IN', 'MOVE_OUT', 'MOVE_NP', 'GATE_DMG', 'RETAIL_PARK')
           AND EXISTS (
                SELECT 1 FROM incident_form_value v WHERE v.incident_id = i.id
           )
           AND (
                COALESCE(i.violation_details, '') = ''
             OR COALESCE(i.violation_unit_number, '') = ''
             OR COALESCE(i.door_lock_community_name, '') = ''
           )
         ORDER BY i.id DESC
         LIMIT 500
        """
    )
    ids = [r[0] for r in cr.fetchall()]
    if not ids:
        _logger.info('No community-style incidents need excel→structured backfill')
        return

    # Defer to ORM in env via registry after load — use SQL mapping for safety here.
    repaired = 0
    for incident_id in ids:
        cr.execute(
            """
            SELECT f.name, f.field_type,
                   v.value_char, v.value_text, v.value_boolean,
                   v.value_date, v.value_time
              FROM incident_form_value v
              JOIN incident_form_field f ON f.id = v.field_id
             WHERE v.incident_id = %s
            """,
            (incident_id,),
        )
        rows = cr.fetchall()
        community = unit = reported_by = notes = None
        observed_date = observed_time = None
        action_bits = []
        title = None
        for name, ftype, vchar, vtext, vbool, vdate, vtime in rows:
            n = ' '.join((name or '').lower().split())
            display = (vchar or vtext or (str(vdate) if vdate else '') or vtime or '').strip()
            if 'community name' in n and display:
                community = community or display
            elif (('unit' in n and 'number' in n) or n == 'unit number') and display:
                unit = unit or display
            elif n in ('date',) or n.endswith(' date'):
                observed_date = vdate or observed_date
            elif n in ('time',) or n.endswith(' time'):
                observed_time = vtime or vchar or observed_time
            elif 'type of violation' in n and display:
                title = title or display
                notes = ('<p><strong>Type of Violation:</strong> %s</p>' % display) + (notes or '')
            elif 'notes for the security' in n and display:
                notes = (notes or '') + (
                    display if display.startswith('<') else '<p>%s</p>' % display
                )
            elif 'speak with the resident' in n:
                action_bits.append('Spoke with resident: %s' % ('Yes' if vbool else 'No'))
            elif 'resident agree' in n:
                action_bits.append(
                    'Resident agreed to clear violation: %s' % ('Yes' if vbool else 'No')
                )
            elif ('security name' in n or n == 'reported by') and display:
                reported_by = reported_by or display

        observed_dt = None
        if observed_date:
            try:
                t = (str(observed_time or '00:00').strip() + ':00')[:8]
                if t.count(':') == 1:
                    t = t + ':00'
                observed_dt = datetime.strptime(
                    '%s %s' % (str(observed_date)[:10], t[:8]),
                    '%Y-%m-%d %H:%M:%S',
                )
            except Exception:
                observed_dt = None

        sets = []
        params = []
        if community:
            sets.append('door_lock_community_name = COALESCE(NULLIF(door_lock_community_name, \'\'), %s)')
            params.append(community)
            sets.append('involved_community = COALESCE(NULLIF(involved_community, \'\'), %s)')
            params.append(community)
        if unit:
            sets.append('violation_unit_number = COALESCE(NULLIF(violation_unit_number, \'\'), %s)')
            params.append(unit)
            sets.append('involved_unit_number = COALESCE(NULLIF(involved_unit_number, \'\'), %s)')
            params.append(unit)
            sets.append('door_lock_unit_number = COALESCE(NULLIF(door_lock_unit_number, \'\'), %s)')
            params.append(unit)
        if reported_by:
            sets.append('violation_reported_by = COALESCE(NULLIF(violation_reported_by, \'\'), %s)')
            params.append(reported_by)
        if notes:
            sets.append(
                "violation_details = CASE WHEN COALESCE(violation_details, '') IN ('', '<p><br></p>') "
                "THEN %s ELSE violation_details END"
            )
            params.append(notes)
        if action_bits:
            action = '\n'.join(action_bits)
            sets.append(
                "violation_action_taken = CASE WHEN COALESCE(violation_action_taken, '') = '' "
                "THEN %s ELSE violation_action_taken END"
            )
            params.append(action)
        if observed_dt:
            sets.append(
                'violation_observed_datetime = COALESCE(violation_observed_datetime, %s)'
            )
            params.append(observed_dt)
        if title:
            sets.append(
                "title = CASE WHEN title IN ('Community Violation', 'Incident Report') "
                "THEN %s ELSE title END"
            )
            params.append(title[:200])

        if not sets:
            continue
        params.append(incident_id)
        cr.execute(
            'UPDATE incident_report SET %s WHERE id = %%s' % ', '.join(sets),
            params,
        )
        repaired += 1

    _logger.info(
        'Backfilled excel→structured fields on %s community-style incidents',
        repaired,
    )
