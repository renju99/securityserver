# -*- coding: utf-8 -*-
"""Rename hr.attendance Many2one column job_id -> attendance_job_code_id (field rename in Python)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_attendance'
              AND column_name = 'job_id'
        )
        """
    )
    (has_job_id,) = cr.fetchone()
    cr.execute(
        """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = 'hr_attendance'
              AND column_name = 'attendance_job_code_id'
        )
        """
    )
    (has_new,) = cr.fetchone()
    if has_job_id and not has_new:
        cr.execute("ALTER TABLE hr_attendance RENAME COLUMN job_id TO attendance_job_code_id")

    cr.execute(
        """
        UPDATE ir_model_fields imf
        SET name = 'attendance_job_code_id'
        FROM ir_model im
        WHERE imf.model_id = im.id
          AND im.model = 'hr.attendance'
          AND imf.name = 'job_id'
        """
    )
