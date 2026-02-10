# -*- coding: utf-8 -*-
"""Post-migration script for GuardPro 18.0.1.0.2

This migration:
- Enables location sharing for all existing guards by default
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Run post-migration tasks."""
    _logger.info("Running GuardPro post-migration 18.0.1.0.2")
    
    # Enable location sharing for all existing guards
    _logger.info("Enabling location sharing for existing guards...")
    cr.execute("""
        UPDATE guard_profile 
        SET location_sharing_enabled = TRUE 
        WHERE location_sharing_enabled IS NULL
    """)
    
    affected_rows = cr.rowcount
    _logger.info(f"Updated {affected_rows} guard profiles with location_sharing_enabled=True")
    
    _logger.info("GuardPro post-migration 18.0.1.0.2 completed successfully")


