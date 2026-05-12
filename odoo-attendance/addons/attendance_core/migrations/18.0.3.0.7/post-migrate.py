# -*- coding: utf-8 -*-
"""Ensure hr.work.location polygon column exists after Text→Char (no-op if already synced)."""


def migrate(cr, version):
    cr.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'hr_work_location'
          AND column_name = 'attendance_geofence_polygon_json'
        """
    )
    if cr.fetchone():
        return
    cr.execute(
        """
        ALTER TABLE hr_work_location
        ADD COLUMN attendance_geofence_polygon_json VARCHAR
        """
    )
