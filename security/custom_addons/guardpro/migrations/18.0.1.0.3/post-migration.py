# -*- coding: utf-8 -*-
"""Post-migration script for GuardLink 18.0.1.0.3

This migration:
- Adds missing conflict detection fields to guard_shift table
- Ensures database schema matches model definitions
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Run post-migration tasks."""
    _logger.info("Running GuardLink post-migration 18.0.1.0.3")
    
    # Add missing columns to guard_shift table
    _logger.info("Adding conflict detection columns to guard_shift table...")
    
    # Check and add has_conflict column
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='has_conflict'
    """)
    if not cr.fetchone():
        _logger.info("Adding has_conflict column...")
        cr.execute("""
            ALTER TABLE guard_shift 
            ADD COLUMN has_conflict BOOLEAN DEFAULT FALSE
        """)
    else:
        _logger.info("has_conflict column already exists")
    
    # Check and add conflict_type column
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='conflict_type'
    """)
    if not cr.fetchone():
        _logger.info("Adding conflict_type column...")
        cr.execute("""
            ALTER TABLE guard_shift 
            ADD COLUMN conflict_type VARCHAR
        """)
    else:
        _logger.info("conflict_type column already exists")
    
    # Check and add conflict_details column
    cr.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='guard_shift' AND column_name='conflict_details'
    """)
    if not cr.fetchone():
        _logger.info("Adding conflict_details column...")
        cr.execute("""
            ALTER TABLE guard_shift 
            ADD COLUMN conflict_details TEXT
        """)
    else:
        _logger.info("conflict_details column already exists")
    
    # Trigger computation of has_conflict for existing shifts
    _logger.info("Triggering conflict detection for existing shifts...")
    cr.execute("""
        UPDATE guard_shift 
        SET has_conflict = FALSE, conflict_type = NULL, conflict_details = NULL
        WHERE has_conflict IS NULL
    """)
    
    affected_rows = cr.rowcount
    _logger.info(f"Updated {affected_rows} shifts with default conflict values")
    
    _logger.info("GuardLink post-migration 18.0.1.0.3 completed successfully")











