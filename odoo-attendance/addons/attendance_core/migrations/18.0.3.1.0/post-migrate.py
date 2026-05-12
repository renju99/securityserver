# -*- coding: utf-8 -*-
"""Copy legacy ir.config_parameter values into res.company after moving Maps/Twilio off res.config.settings."""


def migrate(cr, version):
    mapping = [
        ('attendance_core.google_maps_api_key', 'attendance_google_maps_api_key'),
        ('attendance_core.twilio_account_sid', 'attendance_twilio_account_sid'),
        ('attendance_core.twilio_auth_token', 'attendance_twilio_auth_token'),
        ('attendance_core.twilio_from_number', 'attendance_twilio_from_number'),
    ]
    for param_key, col in mapping:
        cr.execute('SELECT value FROM ir_config_parameter WHERE key = %s', (param_key,))
        row = cr.fetchone()
        if not row or not (row[0] or '').strip():
            continue
        val = (row[0] or '').strip()
        cr.execute(
            """
            UPDATE res_company
            SET {col} = %s
            WHERE ({col} IS NULL OR {col} = '' OR trim({col}) = '')
            """.format(col=col),
            (val,),
        )
