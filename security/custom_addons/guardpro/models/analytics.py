# -*- coding: utf-8 -*-
"""Business Intelligence Analytics Models for GuardPro."""

from odoo import models, fields, api, tools, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class GuardProductivityReport(models.Model):
    """Guard Productivity Analytics Report."""
    
    _name = 'guardpro.productivity.report'
    _description = 'Guard Productivity Analysis'
    _auto = False
    _order = 'date desc, guard_id'
    
    # Dimensions
    guard_id = fields.Many2one('guard.profile', string='Guard', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    year = fields.Char(string='Year', readonly=True)
    
    # Metrics
    shifts_scheduled = fields.Integer(string='Shifts Scheduled', readonly=True)
    shifts_completed = fields.Integer(string='Shifts Completed', readonly=True)
    shifts_missed = fields.Integer(string='Shifts Missed', readonly=True)
    attendance_rate = fields.Float(string='Attendance Rate (%)', readonly=True, aggregator='avg')
    
    hours_scheduled = fields.Float(string='Hours Scheduled', readonly=True)
    hours_worked = fields.Float(string='Hours Worked', readonly=True)
    overtime_hours = fields.Float(string='Overtime Hours', readonly=True)
    
    incidents_reported = fields.Integer(string='Incidents Reported', readonly=True)
    checkpoints_scanned = fields.Integer(string='Checkpoints Scanned', readonly=True)
    tours_completed = fields.Integer(string='Tours Completed', readonly=True)
    tours_missed = fields.Integer(string='Tours Missed', readonly=True)
    
    avg_checkin_delay = fields.Float(string='Avg Check-in Delay (min)', readonly=True, aggregator='avg')
    geofence_violations = fields.Integer(string='Geofence Violations', readonly=True)
    
    # Performance Score
    performance_score = fields.Float(string='Performance Score', readonly=True, aggregator='avg')
    
    def init(self):
        """Create SQL view for guard productivity analytics."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () as id,
                    gp.id as guard_id,
                    DATE(gs.start_datetime) as date,
                    TO_CHAR(gs.start_datetime, 'YYYY-MM') as month,
                    TO_CHAR(gs.start_datetime, 'YYYY') as year,
                    
                    -- Shift metrics
                    COUNT(DISTINCT gs.id) as shifts_scheduled,
                    COUNT(DISTINCT CASE WHEN ga.id IS NOT NULL THEN gs.id END) as shifts_completed,
                    COUNT(DISTINCT CASE WHEN ga.id IS NULL AND gs.start_datetime < NOW() THEN gs.id END) as shifts_missed,
                    CASE 
                        WHEN COUNT(DISTINCT gs.id) > 0 THEN
                            (COUNT(DISTINCT CASE WHEN ga.id IS NOT NULL THEN gs.id END)::float / 
                             COUNT(DISTINCT gs.id)::float)
                        ELSE 0 
                    END as attendance_rate,
                    
                    -- Hours metrics
                    SUM(EXTRACT(EPOCH FROM (gs.end_datetime - gs.start_datetime)) / 3600) as hours_scheduled,
                    COALESCE(SUM(ga.hours_worked), 0) as hours_worked,
                    COALESCE(SUM(ga.overtime_hours), 0) as overtime_hours,
                    
                    -- Activity metrics
                    COUNT(DISTINCT ir.id) as incidents_reported,
                    COUNT(DISTINCT cs.id) as checkpoints_scanned,
                    COUNT(DISTINCT CASE WHEN tl.status = 'completed' THEN tl.id END) as tours_completed,
                    COUNT(DISTINCT CASE WHEN tl.status IN ('cancelled', 'incomplete') THEN tl.id END) as tours_missed,
                    
                    -- Performance metrics
                    AVG(EXTRACT(EPOCH FROM (ga.checkin_time - gs.start_datetime)) / 60) as avg_checkin_delay,
                    COUNT(DISTINCT CASE 
                        WHEN gfa.alert_type IN ('outside_geofence', 'wrong_site') 
                        THEN gfa.id 
                    END) as geofence_violations,
                    
                    -- Overall performance score (0-100)
                    CASE 
                        WHEN COUNT(DISTINCT gs.id) > 0 THEN
                            (
                                (COUNT(DISTINCT CASE WHEN ga.id IS NOT NULL THEN gs.id END)::float / 
                                 COUNT(DISTINCT gs.id)::float * 40) +  -- Attendance: 40 points
                                (LEAST(COUNT(DISTINCT ir.id)::float / NULLIF(COUNT(DISTINCT gs.id), 0) * 20, 20)) +  -- Incidents: 20 points
                                (COUNT(DISTINCT CASE WHEN tl.status = 'completed' THEN tl.id END)::float / 
                                 NULLIF(COUNT(DISTINCT CASE WHEN tl.id IS NOT NULL THEN tl.id END), 0) * 40)  -- Tours: 40 points
                            )
                        ELSE 0
                    END as performance_score
                    
                FROM guard_profile gp
                LEFT JOIN guard_shift gs ON gs.guard_id = gp.id
                LEFT JOIN guard_attendance ga ON ga.guard_id = gp.id AND ga.shift_id = gs.id
                LEFT JOIN incident_report ir ON ir.guard_id = gp.id AND DATE(ir.incident_datetime) = DATE(gs.start_datetime)
                LEFT JOIN tour_log tl ON tl.guard_id = gp.id AND tl.shift_id = gs.id
                LEFT JOIN checkpoint_scan cs ON cs.guard_id = gp.id AND cs.tour_log_id = tl.id
                LEFT JOIN geofence_alert gfa ON gfa.guard_id = gp.id AND DATE(gfa.alert_datetime) = DATE(gs.start_datetime)
                
                WHERE gs.start_datetime >= NOW() - INTERVAL '1 year'
                
                GROUP BY gp.id, DATE(gs.start_datetime), TO_CHAR(gs.start_datetime, 'YYYY-MM'), TO_CHAR(gs.start_datetime, 'YYYY')
                
                ORDER BY date DESC, gp.id
            )
        """ % self._table)


class SitePerformanceReport(models.Model):
    """Site Performance and Coverage Analytics."""
    
    _name = 'guardpro.site.performance.report'
    _description = 'Site Performance Analysis'
    _auto = False
    _order = 'date desc, site_id'
    
    # Dimensions
    site_id = fields.Many2one('client.site', string='Site', readonly=True)
    client_id = fields.Many2one('res.partner', string='Client', readonly=True)
    date = fields.Date(string='Date', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    year = fields.Char(string='Year', readonly=True)
    
    # Coverage Metrics
    shifts_scheduled = fields.Integer(string='Shifts Scheduled', readonly=True)
    shifts_covered = fields.Integer(string='Shifts Covered', readonly=True)
    coverage_rate = fields.Float(string='Coverage Rate (%)', readonly=True, aggregator='avg')
    total_guard_hours = fields.Float(string='Total Guard Hours', readonly=True)
    
    # Incident Metrics
    total_incidents = fields.Integer(string='Total Incidents', readonly=True)
    critical_incidents = fields.Integer(string='Critical Incidents', readonly=True)
    high_incidents = fields.Integer(string='High Priority', readonly=True)
    medium_incidents = fields.Integer(string='Medium Priority', readonly=True)
    low_incidents = fields.Integer(string='Low Priority', readonly=True)
    avg_incident_response = fields.Float(string='Avg Response Time (min)', readonly=True, aggregator='avg')
    
    # Patrol Metrics
    tours_scheduled = fields.Integer(string='Tours Scheduled', readonly=True)
    tours_completed = fields.Integer(string='Tours Completed', readonly=True)
    tour_completion_rate = fields.Float(string='Tour Completion (%)', readonly=True, aggregator='avg')
    checkpoints_scanned = fields.Integer(string='Checkpoints Scanned', readonly=True)
    
    # Guard Count
    unique_guards = fields.Integer(string='Guards Assigned', readonly=True)
    
    def init(self):
        """Create SQL view for site performance analytics."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () as id,
                    cs.id as site_id,
                    cs.client_id as client_id,
                    DATE(gs.start_datetime) as date,
                    TO_CHAR(gs.start_datetime, 'YYYY-MM') as month,
                    TO_CHAR(gs.start_datetime, 'YYYY') as year,
                    
                    -- Coverage metrics
                    COUNT(DISTINCT gs.id) as shifts_scheduled,
                    COUNT(DISTINCT CASE WHEN ga.id IS NOT NULL THEN gs.id END) as shifts_covered,
                    CASE 
                        WHEN COUNT(DISTINCT gs.id) > 0 THEN
                            (COUNT(DISTINCT CASE WHEN ga.id IS NOT NULL THEN gs.id END)::float / 
                             COUNT(DISTINCT gs.id)::float)
                        ELSE 0 
                    END as coverage_rate,
                    COALESCE(SUM(ga.hours_worked), 0) as total_guard_hours,
                    
                    -- Incident metrics
                    COUNT(DISTINCT ir.id) as total_incidents,
                    COUNT(DISTINCT CASE WHEN ir.severity = 'critical' THEN ir.id END) as critical_incidents,
                    COUNT(DISTINCT CASE WHEN ir.severity = 'high' THEN ir.id END) as high_incidents,
                    COUNT(DISTINCT CASE WHEN ir.severity = 'medium' THEN ir.id END) as medium_incidents,
                    COUNT(DISTINCT CASE WHEN ir.severity = 'low' THEN ir.id END) as low_incidents,
                    AVG(EXTRACT(EPOCH FROM (ir.reported_datetime - ir.incident_datetime)) / 60) as avg_incident_response,
                    
                    -- Patrol metrics
                    COUNT(DISTINCT st.id) as tours_scheduled,
                    COUNT(DISTINCT CASE WHEN tl.status = 'completed' THEN tl.id END) as tours_completed,
                    CASE 
                        WHEN COUNT(DISTINCT st.id) > 0 THEN
                            (COUNT(DISTINCT CASE WHEN tl.status = 'completed' THEN tl.id END)::float / 
                             COUNT(DISTINCT st.id)::float)
                        ELSE 0 
                    END as tour_completion_rate,
                    COUNT(DISTINCT cs_scan.id) as checkpoints_scanned,
                    
                    -- Guard metrics
                    COUNT(DISTINCT gs.guard_id) as unique_guards
                    
                FROM client_site cs
                LEFT JOIN guard_shift gs ON gs.site_id = cs.id
                LEFT JOIN guard_attendance ga ON ga.shift_id = gs.id
                LEFT JOIN incident_report ir ON ir.site_id = cs.id AND DATE(ir.incident_datetime) = DATE(gs.start_datetime)
                LEFT JOIN security_tour st ON st.site_id = cs.id
                LEFT JOIN tour_log tl ON tl.shift_id = gs.id
                LEFT JOIN checkpoint_scan cs_scan ON cs_scan.tour_log_id = tl.id
                
                WHERE gs.start_datetime >= NOW() - INTERVAL '1 year'
                
                GROUP BY cs.id, cs.client_id, DATE(gs.start_datetime), TO_CHAR(gs.start_datetime, 'YYYY-MM'), TO_CHAR(gs.start_datetime, 'YYYY')
                
                ORDER BY date DESC, cs.id
            )
        """ % self._table)


class IncidentTrendReport(models.Model):
    """Incident Trend Analytics."""
    
    _name = 'guardpro.incident.trend.report'
    _description = 'Incident Trend Analysis'
    _auto = False
    _order = 'date desc'
    
    # Dimensions
    date = fields.Date(string='Date', readonly=True)
    month = fields.Char(string='Month', readonly=True)
    year = fields.Char(string='Year', readonly=True)
    category_id = fields.Many2one('incident.category', string='Category', readonly=True)
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', readonly=True)
    site_id = fields.Many2one('client.site', string='Site', readonly=True)
    
    # Metrics
    incident_count = fields.Integer(string='Incident Count', readonly=True)
    avg_response_time = fields.Float(string='Avg Response Time (min)', readonly=True, aggregator='avg')
    avg_resolution_time = fields.Float(string='Avg Resolution Time (hours)', readonly=True, aggregator='avg')
    
    # Status tracking
    open_count = fields.Integer(string='Open', readonly=True)
    in_progress_count = fields.Integer(string='In Progress', readonly=True)
    resolved_count = fields.Integer(string='Resolved', readonly=True)
    closed_count = fields.Integer(string='Closed', readonly=True)
    
    def init(self):
        """Create SQL view for incident trend analytics."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    row_number() OVER () as id,
                    DATE(ir.incident_datetime) as date,
                    TO_CHAR(ir.incident_datetime, 'YYYY-MM') as month,
                    TO_CHAR(ir.incident_datetime, 'YYYY') as year,
                    ir.category_id,
                    ir.severity,
                    ir.site_id,
                    
                    COUNT(*) as incident_count,
                    AVG(EXTRACT(EPOCH FROM (ir.reported_datetime - ir.incident_datetime)) / 60) as avg_response_time,
                    AVG(EXTRACT(EPOCH FROM (ir.review_datetime - ir.incident_datetime)) / 3600) as avg_resolution_time,
                    
                    COUNT(CASE WHEN ir.status = 'draft' THEN 1 END) as open_count,
                    COUNT(CASE WHEN ir.status IN ('submitted', 'under_review', 'investigating') THEN 1 END) as in_progress_count,
                    COUNT(CASE WHEN ir.status = 'resolved' THEN 1 END) as resolved_count,
                    COUNT(CASE WHEN ir.status = 'closed' THEN 1 END) as closed_count
                    
                FROM incident_report ir
                
                WHERE ir.incident_datetime >= NOW() - INTERVAL '1 year'
                
                GROUP BY DATE(ir.incident_datetime), TO_CHAR(ir.incident_datetime, 'YYYY-MM'), 
                         TO_CHAR(ir.incident_datetime, 'YYYY'), ir.category_id, ir.severity, ir.site_id
                
                ORDER BY date DESC
            )
        """ % self._table)


class EquipmentUtilizationReport(models.Model):
    """Equipment Utilization Analytics."""
    
    _name = 'guardpro.equipment.utilization.report'
    _description = 'Equipment Utilization Analysis'
    _auto = False
    _order = 'equipment_id'
    
    equipment_id = fields.Many2one('guardpro.equipment', string='Equipment', readonly=True)
    equipment_category = fields.Char(string='Category', readonly=True)
    equipment_status = fields.Char(string='Status', readonly=True)
    
    total_assignments = fields.Integer(string='Total Assignments', readonly=True)
    days_in_use = fields.Integer(string='Days in Use', readonly=True)
    utilization_rate = fields.Float(string='Utilization Rate (%)', readonly=True, aggregator='avg')
    
    maintenance_count = fields.Integer(string='Maintenance Count', readonly=True)
    last_maintenance = fields.Date(string='Last Maintenance', readonly=True)
    avg_maintenance_cost = fields.Float(string='Avg Maintenance Cost', readonly=True, aggregator='avg')
    
    def init(self):
        """Create SQL view for equipment utilization analytics."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW %s AS (
                SELECT 
                    eq.id,
                    eq.id as equipment_id,
                    eq.category as equipment_category,
                    eq.status as equipment_status,
                    
                    COUNT(DISTINCT eal.id) as total_assignments,
                    COUNT(DISTINCT DATE(eal.assignment_date)) as days_in_use,
                    CASE 
                        WHEN DATE_PART('day', NOW() - eq.purchase_date) > 0 THEN
                            (COUNT(DISTINCT DATE(eal.assignment_date))::float / 
                             DATE_PART('day', NOW() - eq.purchase_date)::float)
                        ELSE 0
                    END as utilization_rate,
                    
                    COUNT(DISTINCT eml.id) as maintenance_count,
                    MAX(eml.maintenance_date) as last_maintenance,
                    AVG(eml.cost) as avg_maintenance_cost
                    
                FROM guardpro_equipment eq
                LEFT JOIN equipment_assignment_log eal ON eal.equipment_id = eq.id
                LEFT JOIN equipment_maintenance_log eml ON eml.equipment_id = eq.id
                
                GROUP BY eq.id, eq.category, eq.status
            )
        """ % self._table)


class GuardProDashboard(models.Model):
    """Enhanced Main Dashboard KPI Model with Comprehensive Analytics."""
    
    _name = 'guardpro.dashboard'
    _description = 'GuardPro Advanced Dashboard'
    
    name = fields.Char(string='Dashboard', default='GuardPro Operations Dashboard', readonly=True)
    
    # ============================================
    # REAL-TIME OPERATIONS METRICS
    # ============================================
    active_guards = fields.Integer(string='Active Guards', compute='_compute_kpis')
    total_guards = fields.Integer(string='Total Guards', compute='_compute_kpis')
    guards_on_duty = fields.Integer(string='Guards On Duty Now', compute='_compute_kpis')
    guards_available = fields.Integer(string='Available Guards', compute='_compute_kpis')
    
    active_shifts_today = fields.Integer(string='Active Shifts Today', compute='_compute_kpis')
    total_shifts_today = fields.Integer(string='Total Shifts Today', compute='_compute_kpis')
    upcoming_shifts = fields.Integer(string='Upcoming Shifts', compute='_compute_kpis')
    missed_shifts = fields.Integer(string='Missed Shifts Today', compute='_compute_kpis')
    
    # ============================================
    # SITE COVERAGE METRICS
    # ============================================
    total_sites = fields.Integer(string='Total Sites', compute='_compute_kpis')
    sites_covered_today = fields.Integer(string='Sites Covered Today', compute='_compute_kpis')
    sites_coverage_rate = fields.Float(string='Sites Coverage Rate %', compute='_compute_kpis')
    sites_needing_coverage = fields.Integer(string='Sites Needing Coverage', compute='_compute_kpis')
    
    # ============================================
    # INCIDENT MANAGEMENT METRICS
    # ============================================
    total_incidents_today = fields.Integer(string='Incidents Today', compute='_compute_kpis')
    open_incidents = fields.Integer(string='Open Incidents', compute='_compute_kpis')
    critical_incidents = fields.Integer(string='Critical Incidents', compute='_compute_kpis')
    high_priority_incidents = fields.Integer(string='High Priority Incidents', compute='_compute_kpis')
    incidents_this_week = fields.Integer(string='Incidents This Week', compute='_compute_kpis')
    incidents_this_month = fields.Integer(string='Incidents This Month', compute='_compute_kpis')
    avg_incident_response_time = fields.Float(string='Avg Response Time (min)', compute='_compute_kpis')
    
    # ============================================
    # ATTENDANCE & PERFORMANCE METRICS
    # ============================================
    today_attendance_rate = fields.Float(string="Today's Attendance %", compute='_compute_kpis')
    week_attendance_rate = fields.Float(string="Week Attendance %", compute='_compute_kpis')
    month_attendance_rate = fields.Float(string="Month Attendance %", compute='_compute_kpis')
    total_hours_today = fields.Float(string='Total Hours Today', compute='_compute_kpis')
    total_hours_week = fields.Float(string='Total Hours This Week', compute='_compute_kpis')
    total_hours_month = fields.Float(string='Total Hours This Month', compute='_compute_kpis')
    
    # ============================================
    # TOUR & PATROL METRICS
    # ============================================
    tours_scheduled_today = fields.Integer(string='Tours Scheduled Today', compute='_compute_kpis')
    tours_completed_today = fields.Integer(string='Tours Completed Today', compute='_compute_kpis')
    tours_in_progress = fields.Integer(string='Tours In Progress', compute='_compute_kpis')
    today_tour_completion = fields.Float(string="Today's Tour Completion %", compute='_compute_kpis')
    week_tour_completion = fields.Float(string="Week Tour Completion %", compute='_compute_kpis')
    checkpoints_scanned_today = fields.Integer(string='Checkpoints Scanned Today', compute='_compute_kpis')
    checkpoints_scanned_week = fields.Integer(string='Checkpoints Scanned Week', compute='_compute_kpis')
    
    # ============================================
    # EQUIPMENT METRICS
    # ============================================
    total_equipment = fields.Integer(string='Total Equipment', compute='_compute_kpis')
    equipment_assigned = fields.Integer(string='Equipment Assigned', compute='_compute_kpis')
    equipment_available = fields.Integer(string='Equipment Available', compute='_compute_kpis')
    equipment_maintenance = fields.Integer(string='Under Maintenance', compute='_compute_kpis')
    equipment_damaged = fields.Integer(string='Damaged Equipment', compute='_compute_kpis')
    
    # ============================================
    # FINANCIAL METRICS (if applicable)
    # ============================================
    total_billable_hours_today = fields.Float(string='Billable Hours Today', compute='_compute_kpis')
    total_billable_hours_week = fields.Float(string='Billable Hours Week', compute='_compute_kpis')
    total_billable_hours_month = fields.Float(string='Billable Hours Month', compute='_compute_kpis')
    
    @api.depends_context('uid')
    def _compute_kpis(self):
        """Compute comprehensive real-time KPIs."""
        from datetime import timedelta, datetime
        
        for record in self:
            # Date ranges
            now = fields.Datetime.now()
            today = fields.Date.today()
            today_start = fields.Datetime.to_datetime(today)
            today_end = today_start + timedelta(days=1)
            
            week_start = today_start - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=7)
            
            month_start = today.replace(day=1)
            month_start_dt = fields.Datetime.to_datetime(month_start)
            if month_start.month == 12:
                month_end_dt = fields.Datetime.to_datetime(month_start.replace(year=month_start.year + 1, month=1))
            else:
                month_end_dt = fields.Datetime.to_datetime(month_start.replace(month=month_start.month + 1))
            
            # ============================================
            # GUARD METRICS
            # ============================================
            record.total_guards = self.env['guard.profile'].search_count([])
            record.active_guards = self.env['guard.profile'].search_count([
                ('status', '=', 'active')
            ])
            
            # Guards currently on duty
            current_shifts = self.env['guard.shift'].search([
                ('start_datetime', '<=', now),
                ('end_datetime', '>=', now),
                ('status', 'in', ['confirmed', 'in_progress'])
            ])
            record.guards_on_duty = len(current_shifts.mapped('guard_id'))
            record.guards_available = record.active_guards - record.guards_on_duty
            
            # ============================================
            # SHIFT METRICS
            # ============================================
            record.total_shifts_today = self.env['guard.shift'].search_count([
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', today_end)
            ])
            
            record.active_shifts_today = self.env['guard.shift'].search_count([
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', today_end),
                ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
            ])
            
            record.upcoming_shifts = self.env['guard.shift'].search_count([
                ('start_datetime', '>', now),
                ('start_datetime', '<', today_end),
                ('status', 'in', ['scheduled', 'confirmed'])
            ])
            
            record.missed_shifts = self.env['guard.shift'].search_count([
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', now),
                ('status', '=', 'cancelled')
            ])
            
            # ============================================
            # SITE COVERAGE METRICS
            # ============================================
            record.total_sites = self.env['client.site'].search_count([('active', '=', True)])
            
            covered_sites = self.env['guard.shift'].search([
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', today_end),
                ('site_id', '!=', False),
                ('status', 'in', ['confirmed', 'in_progress', 'completed'])
            ]).mapped('site_id')
            
            record.sites_covered_today = len(covered_sites)
            record.sites_coverage_rate = (record.sites_covered_today / record.total_sites * 100) if record.total_sites > 0 else 0
            record.sites_needing_coverage = record.total_sites - record.sites_covered_today
            
            # ============================================
            # INCIDENT METRICS
            # ============================================
            record.total_incidents_today = self.env['incident.report'].search_count([
                ('incident_datetime', '>=', today_start),
                ('incident_datetime', '<', today_end)
            ])
            
            record.open_incidents = self.env['incident.report'].search_count([
                ('status', 'in', ['draft', 'submitted', 'under_review', 'investigating'])
            ])
            
            record.critical_incidents = self.env['incident.report'].search_count([
                ('status', 'in', ['draft', 'submitted', 'under_review', 'investigating']),
                ('severity', '=', 'critical')
            ])
            
            record.high_priority_incidents = self.env['incident.report'].search_count([
                ('status', 'in', ['draft', 'submitted', 'under_review', 'investigating']),
                ('severity', 'in', ['critical', 'high'])
            ])
            
            record.incidents_this_week = self.env['incident.report'].search_count([
                ('incident_datetime', '>=', week_start),
                ('incident_datetime', '<', week_end)
            ])
            
            record.incidents_this_month = self.env['incident.report'].search_count([
                ('incident_datetime', '>=', month_start_dt),
                ('incident_datetime', '<', month_end_dt)
            ])
            
            # Average response time
            recent_incidents = self.env['incident.report'].search([
                ('incident_datetime', '>=', week_start),
                ('reported_datetime', '!=', False)
            ])
            if recent_incidents:
                total_response = sum([
                    (inc.reported_datetime - inc.incident_datetime).total_seconds() / 60
                    for inc in recent_incidents if inc.reported_datetime and inc.incident_datetime
                ])
                record.avg_incident_response_time = total_response / len(recent_incidents) if recent_incidents else 0
            else:
                record.avg_incident_response_time = 0
            
            # ============================================
            # ATTENDANCE METRICS
            # ============================================
            # Today
            today_shifts = self.env['guard.shift'].search([
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', today_end)
            ])
            if today_shifts:
                # Count unique shifts with attendance (not attendance records)
                attended_today_records = self.env['guard.attendance'].search([
                    ('shift_id', 'in', today_shifts.ids),
                    ('checkin_time', '!=', False)
                ])
                # Get unique shift IDs that have attendance
                attended_today = len(set(attended_today_records.mapped('shift_id').ids))
                record.today_attendance_rate = (attended_today / len(today_shifts) * 100) if today_shifts else 0
            else:
                record.today_attendance_rate = 0
            
            # Week
            week_shifts = self.env['guard.shift'].search([
                ('start_datetime', '>=', week_start),
                ('start_datetime', '<', week_end)
            ])
            if week_shifts:
                # Count unique shifts with attendance (not attendance records)
                attended_week_records = self.env['guard.attendance'].search([
                    ('shift_id', 'in', week_shifts.ids),
                    ('checkin_time', '!=', False)
                ])
                # Get unique shift IDs that have attendance
                attended_week = len(set(attended_week_records.mapped('shift_id').ids))
                record.week_attendance_rate = (attended_week / len(week_shifts) * 100) if week_shifts else 0
            else:
                record.week_attendance_rate = 0
            
            # Month
            month_shifts = self.env['guard.shift'].search([
                ('start_datetime', '>=', month_start_dt),
                ('start_datetime', '<', month_end_dt)
            ])
            if month_shifts:
                # Count unique shifts with attendance (not attendance records)
                attended_month_records = self.env['guard.attendance'].search([
                    ('shift_id', 'in', month_shifts.ids),
                    ('checkin_time', '!=', False)
                ])
                # Get unique shift IDs that have attendance
                attended_month = len(set(attended_month_records.mapped('shift_id').ids))
                record.month_attendance_rate = (attended_month / len(month_shifts) * 100) if month_shifts else 0
            else:
                record.month_attendance_rate = 0
            
            # Hours worked
            today_attendance = self.env['guard.attendance'].search([
                ('checkin_time', '>=', today_start),
                ('checkin_time', '<', today_end)
            ])
            record.total_hours_today = sum(today_attendance.mapped('hours_worked'))
            
            week_attendance = self.env['guard.attendance'].search([
                ('checkin_time', '>=', week_start),
                ('checkin_time', '<', week_end)
            ])
            record.total_hours_week = sum(week_attendance.mapped('hours_worked'))
            
            month_attendance = self.env['guard.attendance'].search([
                ('checkin_time', '>=', month_start_dt),
                ('checkin_time', '<', month_end_dt)
            ])
            record.total_hours_month = sum(month_attendance.mapped('hours_worked'))
            
            # Billable hours (same as worked hours for now)
            record.total_billable_hours_today = record.total_hours_today
            record.total_billable_hours_week = record.total_hours_week
            record.total_billable_hours_month = record.total_hours_month
            
            # ============================================
            # TOUR METRICS
            # ============================================
            record.tours_scheduled_today = self.env['tour.log'].search_count([
                ('start_time', '>=', today_start),
                ('start_time', '<', today_end)
            ])
            
            today_tours = self.env['tour.log'].search([
                ('start_time', '>=', today_start),
                ('start_time', '<', today_end)
            ])
            
            record.tours_completed_today = len(today_tours.filtered(lambda t: t.status == 'completed'))
            record.tours_in_progress = len(today_tours.filtered(lambda t: t.status == 'in_progress'))
            record.today_tour_completion = (record.tours_completed_today / record.tours_scheduled_today * 100) if record.tours_scheduled_today > 0 else 0
            
            # Week tours
            week_tours = self.env['tour.log'].search([
                ('start_time', '>=', week_start),
                ('start_time', '<', week_end)
            ])
            completed_week_tours = len(week_tours.filtered(lambda t: t.status == 'completed'))
            record.week_tour_completion = (completed_week_tours / len(week_tours) * 100) if week_tours else 0
            
            # Checkpoints
            record.checkpoints_scanned_today = self.env['checkpoint.scan'].search_count([
                ('scan_time', '>=', today_start),
                ('scan_time', '<', today_end)
            ])
            
            record.checkpoints_scanned_week = self.env['checkpoint.scan'].search_count([
                ('scan_time', '>=', week_start),
                ('scan_time', '<', week_end)
            ])
            
            # ============================================
            # EQUIPMENT METRICS
            # ============================================
            record.total_equipment = self.env['guardpro.equipment'].search_count([])
            record.equipment_assigned = self.env['guardpro.equipment'].search_count([
                ('status', '=', 'assigned')
            ])
            record.equipment_available = self.env['guardpro.equipment'].search_count([
                ('status', '=', 'available')
            ])
            record.equipment_maintenance = self.env['guardpro.equipment'].search_count([
                ('status', '=', 'maintenance')
            ])
            record.equipment_damaged = self.env['guardpro.equipment'].search_count([
                ('status', 'in', ['damaged', 'retired'])
            ])
    
    # ============================================
    # ACTION METHODS FOR DASHBOARD BUTTONS
    # ============================================
    
    def action_view_guards_on_duty(self):
        """Open guards currently on duty."""
        now = fields.Datetime.now()
        current_shifts = self.env['guard.shift'].search([
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now),
            ('status', 'in', ['confirmed', 'in_progress'])
        ])
        guard_ids = current_shifts.mapped('guard_id').ids
        
        return {
            'name': _('Guards On Duty Now'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'view_mode': 'kanban,list,form',
            'domain': [('id', 'in', guard_ids)],
            'context': {'create': False}
        }
    
    def action_view_available_guards(self):
        """Open available guards (active but not on duty)."""
        now = fields.Datetime.now()
        current_shifts = self.env['guard.shift'].search([
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now),
            ('status', 'in', ['confirmed', 'in_progress'])
        ])
        on_duty_ids = current_shifts.mapped('guard_id').ids
        
        return {
            'name': _('Available Guards'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'view_mode': 'kanban,list,form',
            'domain': [('status', '=', 'active'), ('id', 'not in', on_duty_ids)],
            'context': {'create': False}
        }
    
    def action_view_active_shifts(self):
        """Open active shifts today."""
        today = fields.Date.today()
        today_start = fields.Datetime.to_datetime(today)
        from datetime import timedelta
        today_end = today_start + timedelta(days=1)
        
        return {
            'name': _('Active Shifts Today'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'calendar,list,form',
            'domain': [
                ('start_datetime', '>=', today_start),
                ('start_datetime', '<', today_end),
                ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
            ],
            'context': {'create': False}
        }
    
    def action_view_upcoming_shifts(self):
        """Open upcoming shifts."""
        now = fields.Datetime.now()
        today = fields.Date.today()
        today_start = fields.Datetime.to_datetime(today)
        from datetime import timedelta
        today_end = today_start + timedelta(days=1)
        
        return {
            'name': _('Upcoming Shifts'),
            'type': 'ir.actions.act_window',
            'res_model': 'guard.shift',
            'view_mode': 'calendar,list,form',
            'domain': [
                ('start_datetime', '>', now),
                ('start_datetime', '<', today_end),
                ('status', 'in', ['scheduled', 'confirmed'])
            ],
            'context': {'create': False}
        }
    
    def action_view_open_incidents(self):
        """Open all open incidents."""
        return {
            'name': _('Open Incidents'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,kanban,form',
            'domain': [('status', 'in', ['draft', 'submitted', 'under_review', 'investigating'])],
            'context': {'create': False}
        }
    
    def action_view_critical_incidents(self):
        """Open critical incidents."""
        return {
            'name': _('Critical Incidents'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'domain': [
                ('status', 'in', ['draft', 'submitted', 'under_review', 'investigating']),
                ('severity', '=', 'critical')
            ],
            'context': {'create': False}
        }
    
    def action_view_todays_incidents(self):
        """Open today's incidents."""
        today = fields.Date.today()
        today_start = fields.Datetime.to_datetime(today)
        from datetime import timedelta
        today_end = today_start + timedelta(days=1)
        
        return {
            'name': _("Today's Incidents"),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.report',
            'view_mode': 'list,kanban,form',
            'domain': [
                ('incident_datetime', '>=', today_start),
                ('incident_datetime', '<', today_end)
            ],
            'context': {'create': False}
        }
    
    def action_view_tours_in_progress(self):
        """Open tours currently in progress."""
        return {
            'name': _('Tours In Progress'),
            'type': 'ir.actions.act_window',
            'res_model': 'tour.log',
            'view_mode': 'list,form',
            'domain': [('status', '=', 'in_progress')],
            'context': {'create': False}
        }
    
    def action_view_equipment(self):
        """Open assigned equipment."""
        return {
            'name': _('Assigned Equipment'),
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.equipment',
            'view_mode': 'list,kanban,form',
            'domain': [('status', '=', 'assigned')],
            'context': {'create': False}
        }
    
    def action_view_guard_productivity(self):
        """Open guard productivity report."""
        return {
            'name': _('Guard Productivity Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.productivity.report',
            'view_mode': 'graph,pivot,list',
            'context': {'search_default_last_30_days': 1}
        }
    
    def action_view_site_performance(self):
        """Open site performance report."""
        return {
            'name': _('Site Performance Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.site.performance.report',
            'view_mode': 'graph,pivot,list',
            'context': {'search_default_last_30_days': 1}
        }
    
    def action_view_incident_trends(self):
        """Open incident trends report."""
        return {
            'name': _('Incident Trends Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.incident.trend.report',
            'view_mode': 'graph,pivot,list',
            'context': {'search_default_last_30_days': 1}
        }
    
    def action_view_equipment_utilization(self):
        """Open equipment utilization report."""
        return {
            'name': _('Equipment Utilization Report'),
            'type': 'ir.actions.act_window',
            'res_model': 'guardpro.equipment.utilization.report',
            'view_mode': 'graph,pivot,list',
            'context': {}
        }
    
    def action_refresh_dashboard(self):
        """Refresh dashboard data by invalidating cache and recomputing KPIs."""
        self.ensure_one()
        # Invalidate cache to force recomputation of all computed fields
        self.invalidate_recordset()
        
        # Trigger recomputation by accessing one of the computed fields
        dummy = self.guards_on_duty
        
        # Return action to reload the current view with a notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Dashboard Refreshed'),
                'message': _('Guard Operations dashboard data has been updated successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

