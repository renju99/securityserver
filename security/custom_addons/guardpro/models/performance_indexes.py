# -*- coding: utf-8 -*-
"""Performance Indexes for GuardLink PWA.

This module adds database indexes to frequently queried fields
for maximum query performance in the PWA interface.
"""

from odoo import models
import logging

_logger = logging.getLogger(__name__)


class GuardShiftPerformance(models.Model):
    """Add performance indexes to guard.shift model."""
    
    _inherit = 'guard.shift'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        # Index for PWA dashboard query (guard_id + start_datetime)
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_guard_shift_guard_start_datetime 
            ON guard_shift(guard_id, start_datetime);
        """)
        
        # Index for shift status queries
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_guard_shift_status 
            ON guard_shift(status);
        """)
        
        # Composite index for common filters
        self.env.cr.execute("""
            CREATE INDEX IF NOT EXISTS idx_guard_shift_guard_status_datetime 
            ON guard_shift(guard_id, status, start_datetime);
        """)


class GuardTaskPerformance(models.Model):
    """Add performance indexes to guard.task model."""
    
    _inherit = 'guard.task'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for PWA dashboard query (assigned_to + state)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_task_assigned_state 
                ON guard_task(assigned_to, state);
            """)
            
            # Index for priority and due date sorting
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_task_priority_due_date 
                ON guard_task(priority DESC, due_date ASC);
            """)
            
            # Composite index for common filters
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_task_assigned_state_priority 
                ON guard_task(assigned_to, state, priority DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.task (database may be locked): %s', str(e))


class IncidentReportPerformance(models.Model):
    """Add performance indexes to incident.report model."""
    
    _inherit = 'incident.report'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for PWA dashboard query (guard_id + reported_datetime)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_incident_report_guard_datetime 
                ON incident_report(guard_id, reported_datetime DESC);
            """)
            
            # Index for severity filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_incident_report_severity 
                ON incident_report(severity);
            """)
            
            # Composite index for common filters
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_incident_report_guard_severity_datetime 
                ON incident_report(guard_id, severity, reported_datetime DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for incident.report (database may be locked): %s', str(e))


class GuardProfilePerformance(models.Model):
    """Add performance indexes to guard.profile model."""
    
    _inherit = 'guard.profile'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for user_id lookup (authentication)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_profile_user_id 
                ON guard_profile(user_id);
            """)
            
            # Index for employee_id lookup
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_profile_employee_id 
                ON guard_profile(employee_id);
            """)
            
            # Index for location tracking queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_profile_location_update 
                ON guard_profile(last_location_update);
            """)
        except Exception as e:
            # Handle lock timeouts gracefully - indexes will be created on next upgrade
            _logger.warning('Could not create indexes for guard.profile (database may be locked): %s', str(e))


class GuardLocationHistoryPerformance(models.Model):
    """Add performance indexes to guard.location.history model."""
    
    _inherit = 'guard.location.history'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for location history queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_location_history_guard_timestamp 
                ON guard_location_history(guard_id, timestamp DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.location.history (database may be locked): %s', str(e))


class GuardAttendancePerformance(models.Model):
    """Add performance indexes to guard.attendance model."""
    
    _inherit = 'guard.attendance'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for open attendance records (checkout_time = NULL)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_attendance_guard_checkout 
                ON guard_attendance(guard_id, checkout_time) 
                WHERE checkout_time IS NULL;
            """)
            
            # Index for checkin time queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_guard_attendance_checkin_time 
                ON guard_attendance(checkin_time DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.attendance (database may be locked): %s', str(e))


class TourLogPerformance(models.Model):
    """Add performance indexes to tour.log model."""
    
    _inherit = 'tour.log'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Index for tour log queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_tour_log_guard_start_time 
                ON tour_log(guard_id, start_time DESC);
            """)
            
            # Index for active tours
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_tour_log_guard_end_time 
                ON tour_log(guard_id, end_time) 
                WHERE end_time IS NULL;
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for tour.log (database may be locked): %s', str(e))


class PackageManagementPerformance(models.Model):
    """Add performance indexes to package.management model."""
    
    _inherit = 'package.management'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for common package queries (site + state + date)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_package_site_state_received 
                ON package_management(site_id, state, received_date DESC);
            """)
            
            # Index for tracking number lookups
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_package_tracking_number 
                ON package_management(tracking_number) 
                WHERE tracking_number IS NOT NULL;
            """)
            
            # Index for recipient searches
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_package_recipient_name 
                ON package_management(recipient_name);
            """)
            
            # Index for barcode scanning
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_package_barcode 
                ON package_management(barcode) 
                WHERE barcode IS NOT NULL;
            """)
            
            # Index for overdue package queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_package_overdue 
                ON package_management(state, is_overdue, received_date DESC) 
                WHERE is_overdue = TRUE;
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for package.management (database may be locked): %s', str(e))


class VisitorManagementPerformance(models.Model):
    """Add performance indexes to visitor.management model."""
    
    _inherit = 'visitor.management'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for common visitor queries (site + date + checkin)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_site_date_checkin 
                ON visitor_management(site_id, visit_date DESC, checkin_time DESC);
            """)
            
            # Index for visitor name searches
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_name 
                ON visitor_management(name);
            """)
            
            # Index for ID number lookups (watchlist checks)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_id_number 
                ON visitor_management(id_number) 
                WHERE id_number IS NOT NULL;
            """)
            
            # Index for QR code scanning
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_qr_code 
                ON visitor_management(qr_code) 
                WHERE qr_code IS NOT NULL;
            """)
            
            # Index for active visitors (checked in but not checked out)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_active 
                ON visitor_management(site_id, checkin_time DESC) 
                WHERE checkout_time IS NULL;
            """)
            
            # Index for watchlist hits
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_visitor_watchlist 
                ON visitor_management(watchlist_hit, visit_date DESC) 
                WHERE watchlist_hit = TRUE;
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for visitor.management (database may be locked): %s', str(e))


class LostFoundPerformance(models.Model):
    """Add performance indexes to lost.found.item model."""
    
    _inherit = 'lost.found.item'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for common lost & found queries (site + state + date)
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_lost_found_site_state_date 
                ON lost_found_item(site_id, state, found_date DESC);
            """)
            
            # Index for item category searches
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_lost_found_category 
                ON lost_found_item(item_category, state);
            """)
            
            # Index for holding expiry tracking
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_lost_found_expiry 
                ON lost_found_item(holding_expiry_date, state) 
                WHERE state IN ('found', 'stored');
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for lost.found.item (database may be locked): %s', str(e))


class GuardPerformanceReviewIndexes(models.Model):
    """Add performance indexes to guard.performance.review model."""
    
    _inherit = 'guard.performance.review'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for guard + period queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_review_guard_period 
                ON guard_performance_review(guard_id, period_start DESC, period_end DESC);
            """)
            
            # Index for state filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_review_state 
                ON guard_performance_review(state, review_date DESC);
            """)
            
            # Index for performance grade filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_review_grade 
                ON guard_performance_review(performance_grade, overall_score DESC);
            """)
            
            # Index for reviewer queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_review_reviewer 
                ON guard_performance_review(reviewer_id, state, review_date DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.performance.review (database may be locked): %s', str(e))


class GuardPerformanceMetricIndexes(models.Model):
    """Add performance indexes to guard.performance.metric model."""
    
    _inherit = 'guard.performance.metric'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for guard + period + criteria queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_metric_guard_period_criteria 
                ON guard_performance_metric(guard_id, period_start DESC, criteria_id);
            """)
            
            # Index for criteria type filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_metric_criteria_code 
                ON guard_performance_metric(criteria_code, period_start DESC);
            """)
            
            # Index for score filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_metric_score 
                ON guard_performance_metric(score DESC, weighted_score DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.performance.metric (database may be locked): %s', str(e))


class GuardPerformanceBadgeIndexes(models.Model):
    """Add performance indexes to guard.performance.badge model."""
    
    _inherit = 'guard.performance.badge'
    
    _sql_constraints = []
    
    def init(self):
        """Create database indexes for performance optimization."""
        try:
            # Composite index for guard + badge type queries
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_badge_guard_type 
                ON guard_performance_badge(guard_id, badge_type, earned_date DESC);
            """)
            
            # Index for badge type filtering
            self.env.cr.execute("""
                CREATE INDEX IF NOT EXISTS idx_performance_badge_type_date 
                ON guard_performance_badge(badge_type, earned_date DESC);
            """)
        except Exception as e:
            _logger.warning('Could not create indexes for guard.performance.badge (database may be locked): %s', str(e))



