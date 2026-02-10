# -*- coding: utf-8 -*-
"""
Post-migration script to fix e-learning course visibility.

This migration ensures all GuardPro training courses are:
- Published (is_published=True)
- Public visibility
- Public enrollment
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Update all GuardPro training courses to be public and published."""
    _logger.info("Starting e-learning course visibility migration...")
    
    # Get all GuardPro training courses
    cr.execute("""
        SELECT sc.id, sc.name, sc.visibility, sc.is_published, sc.enroll
        FROM slide_channel sc
        WHERE sc.is_guard_training = TRUE
    """)
    
    courses = cr.fetchall()
    _logger.info(f"Found {len(courses)} GuardPro training courses")
    
    if not courses:
        _logger.warning("No GuardPro training courses found!")
        return
    
    # Update all courses to be public and published
    course_ids = [course[0] for course in courses]
    
    cr.execute("""
        UPDATE slide_channel
        SET 
            visibility = 'public',
            is_published = TRUE,
            enroll = 'public'
        WHERE id IN %s
    """, (tuple(course_ids),))
    
    updated_count = cr.rowcount
    _logger.info(f"Updated {updated_count} courses to public visibility and published status")
    
    # Log each course update for verification
    for course in courses:
        course_id, name, old_visibility, old_published, old_enroll = course
        _logger.info(
            f"  - [{course_id}] {name}: "
            f"visibility={old_visibility}→public, "
            f"published={old_published}→True, "
            f"enroll={old_enroll}→public"
        )
    
    _logger.info("E-learning course visibility migration completed successfully!")

