# -*- coding: utf-8 -*-
"""Post-migration script for version 18.0.1.0.4.

This migration ensures the incident_report_tag_rel table exists and is properly
configured for the many2many relationship between incident.report and incident.tag.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Run post-migration tasks.
    
    Args:
        cr: Database cursor
        version: Current module version
    """
    _logger.info('Running post-migration for version 18.0.1.0.4')
    
    # Verify the table exists
    cr.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'incident_report_tag_rel'
        );
    """)
    
    table_exists = cr.fetchone()[0]
    
    if table_exists:
        _logger.info('✓ incident_report_tag_rel table verified successfully')
        
        # Count existing relations
        cr.execute("SELECT COUNT(*) FROM incident_report_tag_rel;")
        count = cr.fetchone()[0]
        _logger.info('✓ Found %d existing tag relationships', count)
    else:
        _logger.error('✗ incident_report_tag_rel table still missing! Check pre-migration.sql')
        raise Exception('Migration failed: incident_report_tag_rel table not created')
    
    _logger.info('Post-migration 18.0.1.0.4 completed successfully')











