# -*- coding: utf-8 -*-
"""
Post-migration script to fix percentage fields that were incorrectly multiplied by 100.

This migration fixes:
- completion_rate in security.tour model (should be 0.0-1.0, not 0-100)

Fields with widget="percentage" expect values in range 0.0-1.0, but were stored as 0-100.
This causes display issues (e.g., 100% shows as 10000%).

Note: final_score in slide.channel.partner is a computed field (not stored),
so it doesn't need migration - it will compute correctly going forward.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Fix percentage fields that were incorrectly multiplied by 100."""
    _logger.info("Starting percentage fields migration...")
    
    # Check if completion_rate column exists and has values > 1.0
    cr.execute("""
        SELECT COUNT(*) FROM security_tour 
        WHERE completion_rate > 1.0
    """)
    count = cr.fetchone()[0]
    
    if count == 0:
        _logger.info("No security.tour records found with completion_rate > 1.0")
    else:
        # Fix completion_rate in security.tour
        _logger.info(f"Fixing completion_rate in {count} security.tour records...")
        cr.execute("""
            UPDATE security_tour
            SET completion_rate = completion_rate / 100.0
            WHERE completion_rate > 1.0
        """)
        fixed_tours = cr.rowcount
        _logger.info(f"Fixed {fixed_tours} security.tour records with completion_rate > 1.0")
    
    _logger.info("Percentage fields migration completed!")
    _logger.info("Note: The widget='percentage' expects values in range 0.0-1.0 (not 0-100).")
    _logger.info("Fields will be recomputed correctly going forward.")

