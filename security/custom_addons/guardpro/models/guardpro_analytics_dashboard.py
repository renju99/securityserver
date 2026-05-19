# -*- coding: utf-8 -*-
"""GuardLink Analytics Dashboard Model."""

from odoo import models, fields, api, _
from odoo.tools import date_utils
from datetime import datetime, timedelta
import datetime as dt
import json
import logging
import pytz

_logger = logging.getLogger(__name__)


class GuardLinkAnalyticsDashboard(models.Model):
    """Analytics Dashboard for GuardLink System."""

    _name = 'guardpro.analytics.dashboard'
    _description = 'GuardLink Analytics Dashboard'

    name = fields.Char(
        'Dashboard Name',
        required=True,
        default='GuardLink Analytics'
    )
    user_id = fields.Many2one(
        'res.users',
        'User',
        default=lambda self: self.env.user
    )
    dashboard_data = fields.Text(
        compute='_compute_dashboard_data',
        string='Dashboard Data'
    )
    date_from = fields.Date(
        'Date From',
        default=lambda self: fields.Date.today() - timedelta(days=30)
    )
    date_to = fields.Date(
        'Date To',
        default=fields.Date.today
    )

    def _convert_to_user_tz(self, utc_datetime):
        """Convert UTC datetime to user's timezone.
        
        Args:
            utc_datetime: datetime object in UTC
            
        Returns:
            datetime object in user's timezone
        """
        if not utc_datetime:
            return None
        
        # Get user's timezone
        tz_name = self.env.user.tz or self.env.context.get('tz') or 'UTC'
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.exceptions.UnknownTimeZoneError:
            user_tz = pytz.UTC
        
        # Ensure datetime is timezone-aware (Odoo stores in UTC)
        if utc_datetime.tzinfo is None:
            utc_datetime = pytz.UTC.localize(utc_datetime)
        
        # Convert to user's timezone
        return utc_datetime.astimezone(user_tz)

    @api.depends('user_id', 'date_from', 'date_to')
    def _compute_dashboard_data(self):
        """Compute all dashboard data."""
        for record in self:
            record.dashboard_data = json.dumps({
                'kpis': record._get_kpi_data({}),
                'charts': record._get_chart_data({}),
                'tables': record._get_table_data({}),
            })

    def _get_kpi_data(self, filter_context=None):
        """Compute KPI values for dashboard cards."""
        filter_context = filter_context or {}
        
        try:
            # Get filter dates or use defaults
            date_from = filter_context.get('date_from')
            date_to = filter_context.get('date_to')
            today = date_to or fields.Date.today()
            
            # Ensure today is a date object
            if isinstance(today, str):
                today = fields.Date.from_string(today)
            
            # Calculate month_start safely
            if date_from:
                month_start = date_from if isinstance(date_from, dt.date) else fields.Date.from_string(date_from)
            else:
                month_start = today.replace(day=1)
            
            # Log filter parameters for debugging
            _logger.info(f"KPI Data - Date Range: {month_start} to {today}")
            _logger.info(f"KPI Data - Filter Context: {filter_context}")
        except Exception as e:
            _logger.error(f"Error processing KPI dates: {e}", exc_info=True)
            # Fallback to safe defaults
            today = fields.Date.today()
            month_start = today.replace(day=1)
        
        # Build site domain with filters first (needed for guard filtering)
        site_domain = []
        site_filter = filter_context.get('site_domain', [])
        site_ids = filter_context.get('site_ids', [])
        guard_ids = filter_context.get('guard_ids', [])
        
        if site_filter:
            site_domain = self.env['client.site'].search(site_filter).ids
        elif site_ids:
            # Use provided site IDs directly, including -1 if present for force-empty
            site_domain = site_ids
        
        _logger.info(f"KPI Data - Site Domain: {site_domain}, Site IDs from filter: {site_ids}")
        
        # Build guard domain with filters
        guard_domain = [('status', '=', 'active')]
        guard_filter_domain = filter_context.get('guard_domain', [])
        
        if guard_ids:
            guard_domain += [('id', 'in', guard_ids)]
        elif guard_filter_domain:
            guard_domain += guard_filter_domain
        
        # Apply site filter to guards if sites are selected
        # NOTE: Only filter by sites if there are valid site IDs
        if site_domain and len(site_domain) > 0 and not guard_ids:
            # Filter guards by assigned sites (guard.profile.site_ids is Many2many related to user_id.site_ids)
            guard_domain += [('site_ids', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Guard Domain: {guard_domain}")
        
        # Active Guards
        active_guards = self.env['guard.profile'].search_count(guard_domain)
        _logger.info(f"KPI Data - Active Guards Count: {active_guards}")
        
        # Active Shifts Today
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        shift_domain = [
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<', today_end),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
        ]
        if guard_ids:
            shift_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            shift_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Shift Domain: {shift_domain}")
        _logger.info(f"KPI Data - Today range: {today_start} to {today_end}")
        active_shifts = self.env['guard.shift'].search_count(shift_domain)
        _logger.info(f"KPI Data - Active Shifts Count: {active_shifts}")
        
        # Incidents This Month
        month_start_dt = fields.Datetime.to_datetime(month_start)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
        incident_domain = [
            ('incident_datetime', '>=', month_start_dt),
            ('incident_datetime', '<', today_end)
        ]
        if guard_ids:
            incident_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            incident_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Incident Domain: {incident_domain}")
        _logger.info(f"KPI Data - Date range: {month_start_dt} to {today_end}")
        incidents_count = self.env['incident.report'].search_count(incident_domain)
        _logger.info(f"KPI Data - Incidents Count: {incidents_count}")
        
        # Previous Month Incidents (for comparison)
        prev_month_start = (month_start - timedelta(days=1)).replace(day=1)
        prev_month_start_dt = fields.Datetime.to_datetime(prev_month_start)
        month_start_dt = fields.Datetime.to_datetime(month_start)
        prev_incident_domain = [
            ('incident_datetime', '>=', prev_month_start_dt),
            ('incident_datetime', '<', month_start_dt)
        ]
        if guard_ids:
            prev_incident_domain += [('guard_id', 'in', guard_ids)]
        if site_domain:
            prev_incident_domain += [('site_id', 'in', site_domain)]
        prev_incidents_count = self.env['incident.report'].search_count(prev_incident_domain)
        
        # Tasks Completed This Month
        task_completed_domain = [
            ('state', '=', 'completed'),
            ('completed_date', '>=', month_start),
            ('completed_date', '<=', today)
        ]
        if guard_ids:
            task_completed_domain += [('assigned_to', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            task_completed_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Task Domain: {task_completed_domain}")
        tasks_completed = self.env['guard.task'].search_count(task_completed_domain)
        _logger.info(f"KPI Data - Tasks Completed Count: {tasks_completed}")
        
        # Previous Month Tasks (for comparison)
        prev_task_domain = [
            ('state', '=', 'completed'),
            ('completed_date', '>=', prev_month_start),
            ('completed_date', '<', month_start)
        ]
        if guard_ids:
            prev_task_domain += [('assigned_to', 'in', guard_ids)]
        if site_domain:
            prev_task_domain += [('site_id', 'in', site_domain)]
        prev_tasks_completed = self.env['guard.task'].search_count(prev_task_domain)
        
        # Visitor Check-ins Today
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        visitor_domain = [
            ('checkin_time', '>=', today_start),
            ('checkin_time', '<', today_end)
        ]
        if site_domain and len(site_domain) > 0:
            visitor_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Visitor Domain: {visitor_domain}")
        visitors_today = self.env['visitor.management'].search_count(visitor_domain)
        _logger.info(f"KPI Data - Visitors Today Count: {visitors_today}")
        
        # Pending Packages
        package_domain = [('state', 'in', ['received', 'notified'])]
        if site_domain and len(site_domain) > 0:
            package_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Package Domain: {package_domain}")
        packages_pending = self.env['package.management'].search_count(package_domain)
        _logger.info(f"KPI Data - Pending Packages Count: {packages_pending}")
        
        # Tour Completion Rate
        tour_domain = [
            ('start_time', '>=', month_start),
            ('start_time', '<=', today)
        ]
        if guard_ids:
            tour_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            tour_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - Tour Domain: {tour_domain}")
        total_tours = self.env['tour.log'].search_count(tour_domain)
        completed_tours = self.env['tour.log'].search_count(tour_domain + [('status', '=', 'completed')])
        tour_completion_rate = (
            (completed_tours / total_tours * 100) if total_tours > 0 else 0
        )
        _logger.info(f"KPI Data - Tours: {completed_tours}/{total_tours} = {tour_completion_rate}%")
        
        # SLA Compliance Rate
        sla_domain = [
            ('period_start', '>=', month_start),
            ('period_start', '<=', today)
        ]
        if site_domain and len(site_domain) > 0:
            sla_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"KPI Data - SLA Domain: {sla_domain}")
        sla_records = self.env['sla.performance'].search(sla_domain)
        total_sla = len(sla_records)
        compliant_sla = len(sla_records.filtered(lambda r: r.achieved))
        sla_compliance_rate = (
            (compliant_sla / total_sla * 100) if total_sla > 0 else 100
        )
        _logger.info(f"KPI Data - SLA: {compliant_sla}/{total_sla} = {sla_compliance_rate}%")

        return [
            {
                'name': _('Active Guards'),
                'value': active_guards,
                'previous_value': active_guards,
                'icon': 'fa-users',
                'color': 'primary',
                'action': 'action_view_guards',
                'suffix': ''
            },
            {
                'name': _('Active Shifts Today'),
                'value': active_shifts,
                'previous_value': active_shifts,
                'icon': 'fa-calendar-check-o',
                'color': 'success',
                'action': 'action_view_shifts_today',
                'suffix': ''
            },
            {
                'name': _('Incidents This Month'),
                'value': incidents_count,
                'previous_value': prev_incidents_count,
                'icon': 'fa-exclamation-triangle',
                'color': 'warning',
                'action': 'action_view_incidents',
                'suffix': ''
            },
            {
                'name': _('Tasks Completed'),
                'value': tasks_completed,
                'previous_value': prev_tasks_completed,
                'icon': 'fa-check-circle',
                'color': 'info',
                'action': 'action_view_tasks',
                'suffix': ''
            },
            {
                'name': _('Visitors Today'),
                'value': visitors_today,
                'previous_value': visitors_today,
                'icon': 'fa-id-card',
                'color': 'primary',
                'action': 'action_view_visitors',
                'suffix': ''
            },
            {
                'name': _('Pending Packages'),
                'value': packages_pending,
                'previous_value': packages_pending,
                'icon': 'fa-cube',
                'color': 'info',
                'action': 'action_view_packages',
                'suffix': ''
            },
            {
                'name': _('Tour Completion'),
                'value': round(tour_completion_rate, 1),
                'previous_value': round(tour_completion_rate, 1),
                'icon': 'fa-route',
                'color': 'success',
                'action': 'action_view_tours',
                'suffix': '%'
            },
            {
                'name': _('SLA Compliance'),
                'value': round(sla_compliance_rate, 1),
                'previous_value': round(sla_compliance_rate, 1),
                'icon': 'fa-clock-o',
                'color': 'success' if sla_compliance_rate >= 90 else 'warning',
                'action': 'action_view_sla',
                'suffix': '%'
            },
        ]

    def _get_chart_data(self, filter_context=None):
        """Compute chart data for visualizations."""
        filter_context = filter_context or {}
        
        try:
            # Get filter dates or use defaults
            date_from = filter_context.get('date_from')
            date_to = filter_context.get('date_to')
            today = date_to or fields.Date.today()
            
            # Ensure today is a date object
            if isinstance(today, str):
                today = fields.Date.from_string(today)
            
            # Calculate month_start safely
            if date_from:
                month_start = date_from if isinstance(date_from, dt.date) else fields.Date.from_string(date_from)
            else:
                month_start = today.replace(day=1)
            
            _logger.info(f"Chart Data - Date Range: {month_start} to {today}")
        except Exception as e:
            _logger.error(f"Error processing chart dates: {e}", exc_info=True)
            # Fallback to safe defaults
            today = fields.Date.today()
            month_start = today.replace(day=1)
        
        # Get filter domains
        site_filter = filter_context.get('site_domain', [])
        site_ids = filter_context.get('site_ids', [])
        guard_ids = filter_context.get('guard_ids', [])
        
        if site_filter:
            site_domain = self.env['client.site'].search(site_filter).ids
        elif site_ids:
            # Use provided site IDs directly, including -1 if present for force-empty
            site_domain = site_ids
        else:
            site_domain = []
        
        _logger.info(f"Chart Data - Site Domain: {site_domain}")
        
        # Build incident domain with filters
        month_start_dt = fields.Datetime.to_datetime(month_start)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
        incident_base_domain = [
            ('incident_datetime', '>=', month_start_dt),
            ('incident_datetime', '<', today_end)
        ]
        if guard_ids:
            incident_base_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            incident_base_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Chart Data - Incident Base Domain: {incident_base_domain}")
        
        # Chart 1: Incidents by Severity (Pie Chart)
        severity_data = self.env['incident.report'].read_group(
            incident_base_domain,
            ['severity'],
            ['severity']
        )
        
        incident_severity_chart = {
            'type': 'pie',
            'title': _('Incidents by Severity (This Month)'),
            'labels': [_('Low'), _('Medium'), _('High'), _('Critical')],
            'keys': ['low', 'medium', 'high', 'critical'],  # Keys for drill-down
            'action_model': 'incident.report',
            'action_domain_field': 'severity',
            'datasets': [{
                'label': _('Incidents'),
                'data': [
                    next((d['severity_count'] for d in severity_data
                          if d['severity'] == 'low'), 0),
                    next((d['severity_count'] for d in severity_data
                          if d['severity'] == 'medium'), 0),
                    next((d['severity_count'] for d in severity_data
                          if d['severity'] == 'high'), 0),
                    next((d['severity_count'] for d in severity_data
                          if d['severity'] == 'critical'), 0),
                ],
                'backgroundColor': [
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(255, 206, 86, 0.8)',
                    'rgba(255, 159, 64, 0.8)',
                    'rgba(255, 99, 132, 0.8)',
                ],
                'borderColor': [
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(255, 159, 64, 1)',
                    'rgba(255, 99, 132, 1)',
                ],
                'borderWidth': 1
            }]
        }
        
        # Build shift domain with filters
        month_start_dt = fields.Datetime.to_datetime(month_start)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
        shift_base_domain = [
            ('start_datetime', '>=', month_start_dt),
            ('start_datetime', '<', today_end)
        ]
        if guard_ids:
            shift_base_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            shift_base_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Chart Data - Shift Base Domain: {shift_base_domain}")
        
        # Chart 2: Shift Status (Doughnut Chart)
        shift_status_data = self.env['guard.shift'].read_group(
            shift_base_domain,
            ['status'],
            ['status']
        )
        
        shift_status_chart = {
            'type': 'doughnut',
            'title': _('Shift Status Overview'),
            'labels': [
                _('Scheduled'), _('Confirmed'), _('In Progress'),
                _('Completed'), _('Cancelled'), _('No Show')
            ],
            'keys': ['scheduled', 'confirmed', 'in_progress', 'completed', 'cancelled', 'no_show'], # Keys for drill-down
            'action_model': 'guard.shift',
            'action_domain_field': 'status',
            'datasets': [{
                'label': _('Shifts'),
                'data': [
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'scheduled'), 0),
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'confirmed'), 0),
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'in_progress'), 0),
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'completed'), 0),
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'cancelled'), 0),
                    next((d['status_count'] for d in shift_status_data
                          if d['status'] == 'no_show'), 0),
                ],
                'backgroundColor': [
                    'rgba(153, 102, 255, 0.8)',
                    'rgba(54, 162, 235, 0.8)',
                    'rgba(255, 206, 86, 0.8)',
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(201, 203, 207, 0.8)',
                ],
                'borderWidth': 1
            }]
        }
        
        # Chart 3: Monthly Incident Trends (Line Chart - Last 6 Months)
        months_data = []
        labels = []
        date_keys = []
        for i in range(5, -1, -1):
            month_date = today - timedelta(days=30 * i)
            month_start_iter = month_date.replace(day=1)
            # Get last day of month
            if month_start_iter.month == 12:
                month_end_iter = month_start_iter.replace(
                    year=month_start_iter.year + 1, month=1, day=1
                ) - timedelta(days=1)
            else:
                month_end_iter = month_start_iter.replace(
                    month=month_start_iter.month + 1, day=1
                ) - timedelta(days=1)
            
            month_start_iter_dt = fields.Datetime.to_datetime(month_start_iter)
            month_end_iter_dt = fields.Datetime.to_datetime(month_end_iter) + timedelta(days=1)
            month_incident_domain = [
                ('incident_datetime', '>=', month_start_iter_dt),
                ('incident_datetime', '<', month_end_iter_dt)
            ]
            if guard_ids:
                month_incident_domain += [('guard_id', 'in', guard_ids)]
            if site_domain and len(site_domain) > 0:
                month_incident_domain += [('site_id', 'in', site_domain)]
            
            incident_count = self.env['incident.report'].search_count(month_incident_domain)
            months_data.append(incident_count)
            labels.append(month_start_iter.strftime('%B %Y'))
            date_keys.append({
                'start': month_start_iter.strftime('%Y-%m-%d'),
                'end': month_end_iter.strftime('%Y-%m-%d')
            })
        
        incident_trend_chart = {
            'type': 'line',
            'title': _('Incident Trends (Last 6 Months)'),
            'labels': labels,
            'keys': date_keys, # Keys for drill-down
            'action_model': 'incident.report',
            'action_type': 'date_range',
            'datasets': [{
                'label': _('Incidents'),
                'data': months_data,
                'backgroundColor': 'rgba(255, 99, 132, 0.2)',
                'borderColor': 'rgba(255, 99, 132, 1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.4
            }]
        }
        
        # Build task domain with filters
        task_base_domain = [
            ('state', '=', 'completed'),
            ('completed_date', '>=', month_start),
            ('completed_date', '<=', today)
        ]
        if guard_ids:
            task_base_domain += [('assigned_to', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            task_base_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Chart Data - Task Base Domain: {task_base_domain}")
        
        # Chart 4: Task Completion by Type (Bar Chart)
        task_type_data = self.env['guard.task'].read_group(
            task_base_domain,
            ['task_type'],
            ['task_type']
        )
        
        task_labels = []
        task_counts = []
        task_keys = []
        for task_data in task_type_data:
            if task_data['task_type']:
                task_labels.append(
                    dict(self.env['guard.task']._fields[
                        'task_type'
                    ].selection).get(task_data['task_type'], task_data['task_type'])
                )
                task_keys.append(task_data['task_type'])
                task_counts.append(task_data['task_type_count'])
        
        task_completion_chart = {
            'type': 'bar',
            'title': _('Tasks Completed by Type'),
            'labels': task_labels,
            'keys': task_keys, # Keys for drill-down
            'action_model': 'guard.task',
            'action_domain_field': 'task_type',
            'datasets': [{
                'label': _('Tasks Completed'),
                'data': task_counts,
                'backgroundColor': 'rgba(75, 192, 192, 0.8)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }]
        }
        
        # Chart 5: Guard Attendance Trend (Area Chart - Last 30 Days)
        attendance_data = []
        attendance_labels = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_start = fields.Datetime.to_datetime(day)
            day_end = day_start + timedelta(days=1)
            
            attendance_domain = [
                ('checkin_time', '>=', day_start),
                ('checkin_time', '<', day_end)
            ]
            if guard_ids:
                attendance_domain += [('guard_id', 'in', guard_ids)]
            if site_domain and len(site_domain) > 0:
                attendance_domain += [('site_id', 'in', site_domain)]
            
            attendance_count = self.env['guard.attendance'].search_count(attendance_domain)
            attendance_data.append(attendance_count)
            attendance_labels.append(day.strftime('%m/%d'))
        
        attendance_chart = {
            'type': 'line',
            'title': _('Guard Attendance (Last 30 Days)'),
            'labels': attendance_labels,
            'datasets': [{
                'label': _('Check-ins'),
                'data': attendance_data,
                'backgroundColor': 'rgba(54, 162, 235, 0.3)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.4
            }]
        }
        
        # Return charts excluding attendance trend (replaced by attendance matrix)
        return [
            incident_severity_chart,
            shift_status_chart,
            incident_trend_chart,
            task_completion_chart,
        ]

    def _get_table_data(self, filter_context=None):
        """Compute table data for dashboard."""
        filter_context = filter_context or {}
        
        # Get filter dates or use defaults
        date_from = filter_context.get('date_from')
        date_to = filter_context.get('date_to')
        today = date_to or fields.Date.today()
        
        # Get filter domains
        site_filter = filter_context.get('site_domain', [])
        site_ids = filter_context.get('site_ids', [])
        guard_ids = filter_context.get('guard_ids', [])
        
        if site_filter:
            site_domain = self.env['client.site'].search(site_filter).ids
        elif site_ids:
            # Use provided site IDs directly, including -1 if present for force-empty
            site_domain = site_ids
        else:
            site_domain = []
        
        _logger.info(f"Table Data - Site Domain: {site_domain}")
        
        # Recent Incidents (Last 10)
        incident_domain = [
            ('incident_datetime', '>=', (date_from or (today - timedelta(days=7))))
        ]
        if guard_ids:
            incident_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            incident_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Table Data - Incident Domain: {incident_domain}")
        
        recent_incidents = self.env['incident.report'].search(
            incident_domain, limit=10, order='incident_datetime desc'
        )
        
        # Determine table title based on date range
        if date_from:
            table_title = _('Recent Incidents (%s to %s)') % (
                date_from.strftime('%Y-%m-%d'),
                date_to.strftime('%Y-%m-%d') if date_to else _('Present')
            )
        else:
            table_title = _('Recent Incidents (Last 7 Days)')

        incidents_table = {
            'title': table_title,
            'res_model': 'incident.report',
            'columns': [
                _('Incident #'),
                _('Title'),
                _('Site'),
                _('Severity'),
                _('Date'),
                _('Status')
            ],
            'rows': [{
                'id': incident.id,
                'data': [
                    incident.name,
                    incident.title,
                    incident.site_id.name,
                    dict(incident._fields['severity'].selection)[incident.severity],
                    self._convert_to_user_tz(incident.incident_datetime).strftime('%Y-%m-%d %H:%M')
                    if incident.incident_datetime else '',
                    dict(incident._fields['status'].selection)[incident.status],
                ]
            } for incident in recent_incidents]
        }
        
        # Overdue Tasks
        task_domain = [
            ('state', 'not in', ['completed', 'cancelled']),
            ('due_date', '<', fields.Datetime.now())
        ]
        if guard_ids:
            task_domain += [('assigned_to', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            task_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Table Data - Task Domain: {task_domain}")
        
        overdue_tasks = self.env['guard.task'].search(
            task_domain, limit=10, order='due_date asc'
        )
        
        overdue_tasks_table = {
            'title': _('Overdue Tasks'),
            'res_model': 'guard.task',
            'columns': [
                _('Task'),
                _('Assigned To'),
                _('Site'),
                _('Due Date'),
                _('Priority'),
                _('Status')
            ],
            'rows': [{
                'id': task.id,
                'data': [
                    task.name,
                    task.assigned_to.name if task.assigned_to else _('Unassigned'),
                    task.site_id.name,
                    self._convert_to_user_tz(task.due_date).strftime('%Y-%m-%d %H:%M') if task.due_date else '',
                    dict(task._fields['priority'].selection)[task.priority],
                    dict(task._fields['state'].selection)[task.state],
                ]
            } for task in overdue_tasks]
        }
        
        # Active Shifts Today
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        shift_domain = [
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<', today_end),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
        ]
        if guard_ids:
            shift_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            shift_domain += [('site_id', 'in', site_domain)]
        
        _logger.info(f"Table Data - Shift Domain: {shift_domain}")
        
        active_shifts_today = self.env['guard.shift'].search(
            shift_domain, limit=10, order='start_datetime asc'
        )
        
        active_shifts_table = {
            'title': _('Active Shifts Today'),
            'res_model': 'guard.shift',
            'columns': [
                _('Guard'),
                _('Site'),
                _('Start Time'),
                _('End Time'),
                _('Type'),
                _('Status')
            ],
            'rows': [{
                'id': shift.id,
                'data': [
                    shift.guard_id.name,
                    shift.site_id.name,
                    self._convert_to_user_tz(shift.start_datetime).strftime('%H:%M')
                    if shift.start_datetime else '',
                    self._convert_to_user_tz(shift.end_datetime).strftime('%H:%M')
                    if shift.end_datetime else '',
                    dict(shift._fields['shift_type'].selection)[shift.shift_type],
                    dict(shift._fields['status'].selection)[shift.status],
                ]
            } for shift in active_shifts_today]
        }

        return [incidents_table, overdue_tasks_table, active_shifts_table]

    def _sanitize_site_filters(
        self, site_ids=None, client_ids=None, enforce_limits=False, assigned_site_ids=None
    ):
        """Sanitize site filters."""
        site_ids = site_ids or []
        client_ids = client_ids or []
        assigned_site_ids = assigned_site_ids or []
        filter_requested = bool(site_ids or client_ids)
        sanitized_sites = set(site_ids)
        force_empty = False

        _logger.info(f"Sanitizing Sites - Initial: {site_ids}, Clients: {client_ids}")

        if client_ids:
            client_site_ids = self.env['client.site'].search([
                ('client_id', 'in', client_ids)
            ]).ids
            client_site_ids = set(client_site_ids)
            _logger.info(f"Sanitizing Sites - Client Sites: {client_site_ids}")
            sanitized_sites = (sanitized_sites & client_site_ids) if sanitized_sites else client_site_ids

        if enforce_limits:
            assigned_set = set(assigned_site_ids)
            _logger.info(f"Sanitizing Sites - Enforcing Limits. Assigned: {assigned_set}")
            if not assigned_set:
                _logger.warning("Sanitizing Sites - User has no assigned sites!")
                return [], _('No sites are assigned to your user. Please contact your administrator.'), False
            
            if sanitized_sites:
                before_intersection = set(sanitized_sites)
                sanitized_sites &= assigned_set
                _logger.info(f"Sanitizing Sites - Intersection: {before_intersection} & {assigned_set} = {sanitized_sites}")
            elif not filter_requested:
                sanitized_sites = assigned_set
                _logger.info("Sanitizing Sites - Using all assigned sites.")
            else:
                _logger.info("Sanitizing Sites - Filter requested but yields no assigned sites.")
                force_empty = True

        if filter_requested and not sanitized_sites:
            _logger.info("Sanitizing Sites - Final check: Filter was requested but resulting site list is empty.")
            force_empty = True

        result = sorted(sanitized_sites)
        _logger.info(f"Sanitizing Sites - Result: {result}, force_empty: {force_empty}")
        return result, None, force_empty

    def _sanitize_guard_filters(self, guard_ids=None, allowed_site_ids=None):
        """
        Ensure guard filters cannot return data for guards outside allowed sites.

        Args:
            guard_ids (list): Requested guard IDs from filters.
            allowed_site_ids (list): Site IDs the user is allowed to access.

        Returns:
            list: Guard IDs limited to guards operating on allowed sites.
        """
        guard_ids = guard_ids or []
        allowed_site_ids = allowed_site_ids or []

        if not guard_ids:
            return []
        if not allowed_site_ids:
            return []

        allowed_guards = self.env['guard.profile'].search([
            ('id', 'in', guard_ids),
            ('site_ids', 'in', allowed_site_ids)
        ]).ids
        return allowed_guards

    @api.model
    def get_dashboard_data(self, dashboard_id=None, context=None, filter_params=None):
        """API method for fetching dashboard data via JavaScript."""
        try:
            # Get filter_params from arguments or kwargs (backwards compatibility)
            if not filter_params and context:
                # Try to get from context if not passed directly
                filter_params = context.get('filter_params', {}) or {}
            filter_params = dict(filter_params or {})
            context = context or {}
            
            # Extract filter parameters and ensure they are integers for set operations
            def sanitize_ids(ids):
                if not ids: return []
                if isinstance(ids, (int, str)): ids = [ids]
                return [int(i) for i in ids if i and str(i).lstrip('-').isdigit()]

            date_from = filter_params.get('date_from')
            date_to = filter_params.get('date_to')
            site_ids = sanitize_ids(filter_params.get('site_ids', []))
            guard_ids = sanitize_ids(filter_params.get('guard_ids', []))
            client_ids = sanitize_ids(filter_params.get('client_ids', []))
            
            # Convert date strings to date objects if provided
            if date_from:
                try:
                    if isinstance(date_from, str):
                        date_from = fields.Date.from_string(date_from)
                except (ValueError, TypeError) as e:
                    _logger.warning(f"Invalid date_from format: {date_from}, error: {e}")
                    date_from = None
            if date_to:
                try:
                    if isinstance(date_to, str):
                        date_to = fields.Date.from_string(date_to)
                except (ValueError, TypeError) as e:
                    _logger.warning(f"Invalid date_to format: {date_to}, error: {e}")
                    date_to = None
        except Exception as e:
            _logger.error(f"Error processing dashboard parameters: {e}", exc_info=True)
            return {
                'kpis': [],
                'charts': [],
                'tables': [],
                'error': str(e)
            }
        
        # Build filter domains
        user = self.env.user
        guard_domain = []
        is_admin = user.has_group('guardpro.group_guardpro_admin') or user.has_group('base.group_system')
        enforce_site_limits = not is_admin and (
            user.has_group('guardpro.group_guardpro_client_user') or
            user.has_group('guardpro.group_guardpro_supervisor') or
            user.has_group('guardpro.group_guardpro_manager')
        )
        assigned_site_ids = user.site_ids.ids
        _logger.info(f"Dashboard Data Request - User: {user.name}, is_admin: {is_admin}, enforce_limits: {enforce_site_limits}")

        sanitized_sites, site_error, force_empty_sites = self._sanitize_site_filters(
            site_ids=site_ids,
            client_ids=client_ids,
            enforce_limits=enforce_site_limits,
            assigned_site_ids=assigned_site_ids
        )
        if site_error:
            return {
                'kpis': [],
                'charts': [],
                'tables': [],
                'error': site_error
            }

        site_ids = sanitized_sites
        site_ids_for_context = [-1] if force_empty_sites else site_ids
        filter_params['site_ids'] = site_ids

        if enforce_site_limits:
            guard_ids = self._sanitize_guard_filters(
                guard_ids=guard_ids,
                allowed_site_ids=site_ids or assigned_site_ids
            )
            filter_params['guard_ids'] = guard_ids
        
        if guard_ids:
            guard_domain = [('id', 'in', guard_ids)]
        
        try:
            # Get or create default dashboard for current user
            dashboard = self.search([
                ('user_id', '=', self.env.user.id)
            ], limit=1)
            if not dashboard:
                dashboard = self.create({
                    'name': _('GuardLink Analytics'),
                    'user_id': self.env.user.id,
                })
            
            # Prepare filter context dictionary to pass to computation methods
            filter_context = {
                'date_from': date_from,
                'date_to': date_to,
                'site_ids': site_ids_for_context,
                'guard_ids': guard_ids or [],
                'client_ids': client_ids or [],
                'site_domain': [],
                'guard_domain': guard_domain,
            }
            
            # Compute dashboard data with filters
            kpis = dashboard._get_kpi_data(filter_context)
            charts = dashboard._get_chart_data(filter_context)
            tables = dashboard._get_table_data(filter_context)
            
            return {
                'kpis': kpis,
                'charts': charts,
                'tables': tables,
            }
        except Exception as e:
            _logger.error(f"Error computing dashboard data: {e}", exc_info=True)
            return {
                'kpis': [],
                'charts': [],
                'tables': [],
                'error': str(e)
            }

    # Action methods for KPI drill-down
    @api.model
    def action_view_guards(self, filter_params=None):
        """Navigate to guards list."""
        filter_params = filter_params or {}
        site_ids = filter_params.get('site_ids', [])
        
        domain = [('status', '=', 'active')]
        if site_ids:
            domain += [('site_ids', 'in', site_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Active Guards'),
            'res_model': 'guard.profile',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'context': {'create': False},
            'target': 'current',
        }

    @api.model
    def action_view_shifts_today(self, filter_params=None):
        """Navigate to today's shifts."""
        filter_params = filter_params or {}
        today = fields.Date.today()
        if filter_params.get('date_to'):
            today = fields.Date.from_string(filter_params['date_to'])
            
        today_start = fields.Datetime.to_datetime(today)
        today_end = today_start + timedelta(days=1)
        
        site_ids = filter_params.get('site_ids', [])
        guard_ids = filter_params.get('guard_ids', [])
        
        domain = [
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<', today_end),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
        if guard_ids:
            domain += [('guard_id', 'in', guard_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Active Shifts Today'),
            'res_model': 'guard.shift',
            'view_mode': 'list,form,calendar',
            'views': [[False, 'list'], [False, 'form'], [False, 'calendar']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_incidents(self, filter_params=None):
        """Navigate to incidents this month."""
        filter_params = filter_params or {}
        date_from = filter_params.get('date_from')
        date_to = filter_params.get('date_to')
        
        if date_from:
            start_date = fields.Datetime.to_datetime(date_from)
        else:
            start_date = fields.Datetime.to_datetime(fields.Date.today().replace(day=1))
            
        if date_to:
            end_date = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        else:
            end_date = fields.Datetime.now()
            
        site_ids = filter_params.get('site_ids', [])
        guard_ids = filter_params.get('guard_ids', [])
        
        domain = [
            ('incident_datetime', '>=', start_date),
            ('incident_datetime', '<', end_date)
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
        if guard_ids:
            domain += [('guard_id', 'in', guard_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Incidents'),
            'res_model': 'incident.report',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_tasks(self, filter_params=None):
        """Navigate to completed tasks."""
        filter_params = filter_params or {}
        date_from = filter_params.get('date_from')
        date_to = filter_params.get('date_to')
        
        if date_from:
            start_date = date_from
        else:
            start_date = fields.Date.today().replace(day=1)
            
        if date_to:
            end_date = date_to
        else:
            end_date = fields.Date.today()
            
        site_ids = filter_params.get('site_ids', [])
        guard_ids = filter_params.get('guard_ids', [])
        
        domain = [
            ('state', '=', 'completed'),
            ('completed_date', '>=', start_date),
            ('completed_date', '<=', end_date)
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
        if guard_ids:
            domain += [('assigned_to', 'in', guard_ids)] # Task uses assigned_to
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Completed Tasks'),
            'res_model': 'guard.task',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_visitors(self, filter_params=None):
        """Navigate to today's visitors."""
        filter_params = filter_params or {}
        date_from = filter_params.get('date_from')
        date_to = filter_params.get('date_to')
        
        if date_from:
            start_date = fields.Datetime.to_datetime(date_from)
        else:
            start_date = fields.Datetime.to_datetime(fields.Date.today())
            
        if date_to:
            end_date = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        else:
            end_date = start_date + timedelta(days=1)
            
        site_ids = filter_params.get('site_ids', [])
        
        domain = [
            ('checkin_time', '>=', start_date),
            ('checkin_time', '<', end_date)
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Visitors'),
            'res_model': 'visitor.management',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_packages(self, filter_params=None):
        """Navigate to pending packages."""
        filter_params = filter_params or {}
        site_ids = filter_params.get('site_ids', [])
        
        domain = [('state', 'in', ['received', 'notified'])]
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Pending Packages'),
            'res_model': 'package.management',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_tours(self, filter_params=None):
        """Navigate to tour logs."""
        filter_params = filter_params or {}
        date_from = filter_params.get('date_from')
        date_to = filter_params.get('date_to')
        
        if date_from:
            start_date = fields.Datetime.to_datetime(date_from)
        else:
            start_date = fields.Datetime.to_datetime(fields.Date.today().replace(day=1))
            
        if date_to:
            end_date = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        else:
            end_date = fields.Datetime.now()
            
        site_ids = filter_params.get('site_ids', [])
        guard_ids = filter_params.get('guard_ids', [])
        
        domain = [
            ('start_time', '>=', start_date),
            ('start_time', '<', end_date)
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
        if guard_ids:
            domain += [('guard_id', 'in', guard_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tour Logs'),
            'res_model': 'tour.log',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def action_view_sla(self, filter_params=None):
        """Navigate to SLA records."""
        filter_params = filter_params or {}
        date_from = filter_params.get('date_from')
        date_to = filter_params.get('date_to')
        
        if date_from:
            start_date = fields.Datetime.to_datetime(date_from)
        else:
            start_date = fields.Datetime.to_datetime(fields.Date.today().replace(day=1))
            
        if date_to:
            end_date = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
        else:
            end_date = fields.Datetime.now()
            
        site_ids = filter_params.get('site_ids', [])
        
        domain = [
            ('period_start', '>=', start_date),
            ('period_start', '<', end_date)
        ]
        
        if site_ids:
            domain += [('site_id', 'in', site_ids)]
            
        return {
            'type': 'ir.actions.act_window',
            'name': _('SLA Performance Records'),
            'res_model': 'sla.performance',
            'view_mode': 'list,form',
            'views': [[False, 'list'], [False, 'form']],
            'domain': domain,
            'target': 'current',
        }

    @api.model
    def get_report_data(self, filter_params=None):
        """Prepare dashboard data for PDF export."""
        import logging
        _logger = logging.getLogger(__name__)
        
        try:
            filter_params = filter_params or {}
            _logger.info("=== PDF Export: Getting report data ===")
            _logger.info("Filter params received: %s", filter_params)
            _logger.info("Filter params type: %s", type(filter_params))
            
            # Get dashboard data with filters - call as @api.model method
            dashboard_data = self.env['guardpro.analytics.dashboard'].get_dashboard_data(
                dashboard_id=None,
                context=None,
                filter_params=filter_params
            )
            
            _logger.info("Dashboard data retrieved successfully")
            _logger.info("KPIs count: %s", len(dashboard_data.get('kpis', [])))
            _logger.info("Charts count: %s", len(dashboard_data.get('charts', [])))
            _logger.info("Tables count: %s", len(dashboard_data.get('tables', [])))
            
            # Get filter information for display
            site_ids = filter_params.get('site_ids', [])
            site_names = []
            if site_ids:
                try:
                    sites = self.env['client.site'].browse(site_ids)
                    site_names = [site.name for site in sites if site]
                except Exception as e:
                    _logger.warning("Error getting site names: %s", e)
            
            # Prepare filter information
            filters_info = {
                'date_from': filter_params.get('date_from', ''),
                'date_to': filter_params.get('date_to', ''),
                'site_ids': site_ids,
                'site_names': site_names,
                'guard_ids': filter_params.get('guard_ids', []),
                'client_ids': filter_params.get('client_ids', []),
            }
            
            # Get attendance data for biometric report
            _logger.info("Fetching attendance data with filter_params: %s", filter_params)
            attendance_data = self._get_attendance_report_data(filter_params)
            _logger.info("Attendance data fetched: %s records", len(attendance_data))
            
            # Get attendance matrix (guards vs dates)
            _logger.info("Fetching attendance matrix data")
            attendance_matrix = self._get_attendance_matrix_data(filter_params)
            _logger.info("Attendance matrix fetched: %s guards, %s dates", 
                        len(attendance_matrix.get('guards', [])), 
                        len(attendance_matrix.get('dates', [])))
            
            result = {
                'kpis': dashboard_data.get('kpis', []),
                'charts': dashboard_data.get('charts', []),
                'tables': dashboard_data.get('tables', []),
                'attendance': attendance_data,
                'attendance_matrix': attendance_matrix,
                'filters': filters_info
            }
            
            _logger.info("Returning report data: %s KPIs, %s Charts, %s Tables, %s Attendance Records", 
                        len(result['kpis']), len(result['charts']), len(result['tables']),
                        len(result['attendance']))
            
            return result
            
        except Exception as e:
            _logger.error("=== ERROR in get_report_data ===")
            _logger.error("Exception: %s", e, exc_info=True)
            # Return minimal structure
            return {
                'kpis': [],
                'charts': [],
                'tables': [],
                'attendance': [],
                'attendance_matrix': {},
                'filters': filter_params or {}
            }

    def _get_attendance_report_data(self, filter_params=None):
        """Get attendance data formatted for biometric report."""
        try:
            filter_params = filter_params or {}
            _logger.info("=== _get_attendance_report_data called ===")
            _logger.info("Filter params: %s", filter_params)
            
            # Get date range
            date_from = filter_params.get('date_from')
            date_to = filter_params.get('date_to')
            
            _logger.info("Raw dates - from: %s, to: %s", date_from, date_to)
            
            if date_from:
                try:
                    date_from = fields.Date.from_string(date_from)
                except (ValueError, TypeError):
                    date_from = None
            if date_to:
                try:
                    date_to = fields.Date.from_string(date_to)
                except (ValueError, TypeError):
                    date_to = None
            
            # Default to last 30 days if no dates provided
            if not date_from:
                date_from = fields.Date.today() - timedelta(days=30)
            if not date_to:
                date_to = fields.Date.today()
            
            _logger.info("Processed dates - from: %s, to: %s", date_from, date_to)
            
            # Build attendance domain
            date_from_dt = fields.Datetime.to_datetime(date_from)
            date_to_dt = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
            attendance_domain = [
                ('checkin_time', '>=', date_from_dt),
                ('checkin_time', '<', date_to_dt)
            ]
            
            # Apply site filter
            site_ids = filter_params.get('site_ids', [])
            if site_ids:
                attendance_domain += [('site_id', 'in', site_ids)]
                _logger.info("Added site filter: %s", site_ids)
            
            # Apply guard filter
            guard_ids = filter_params.get('guard_ids', [])
            if guard_ids:
                attendance_domain += [('guard_id', 'in', guard_ids)]
                _logger.info("Added guard filter: %s", guard_ids)
            
            _logger.info("Attendance domain: %s", attendance_domain)
            
            # Get attendance records
            attendances = self.env['guard.attendance'].search(
                attendance_domain,
                order='checkin_time desc, guard_id'
            )
            
            _logger.info("Found %s attendance records", len(attendances))
            
            # Format attendance data
            attendance_list = []
            for att in attendances:
                # Convert UTC times to user timezone
                checkin_local = self._convert_to_user_tz(att.checkin_time) if att.checkin_time else None
                checkout_local = self._convert_to_user_tz(att.checkout_time) if att.checkout_time else None
                
                attendance_list.append({
                    'guard_name': att.guard_id.name if att.guard_id else 'N/A',
                    'badge_number': att.guard_id.badge_number if att.guard_id else '',
                    'site_name': att.site_id.name if att.site_id else 'N/A',
                    'date': checkin_local.strftime('%Y-%m-%d') if checkin_local else 'N/A',
                    'checkin_time': checkin_local.strftime('%H:%M:%S') if checkin_local else 'N/A',
                    'checkout_time': checkout_local.strftime('%H:%M:%S') if checkout_local else 'Still On Duty',
                    'hours_worked': round(att.hours_worked, 2) if att.hours_worked else 0,
                    'status': dict(att._fields['status'].selection)[att.status] if att.status else 'N/A',
                    'is_late': 'Yes' if att.is_late else 'No',
                    'late_minutes': att.late_minutes if att.late_minutes else 0,
                    'checkin_method': dict(att._fields['checkin_method'].selection)[att.checkin_method] if att.checkin_method else 'N/A',
                })
            
            return attendance_list
            
        except Exception as e:
            _logger.error("Error getting attendance report data: %s", e, exc_info=True)
            return []

    def _get_attendance_matrix_data(self, filter_params=None):
        """Get attendance matrix data: guards vs dates for presence tracking."""
        try:
            filter_params = filter_params or {}
            
            # Get date range
            date_from = filter_params.get('date_from')
            date_to = filter_params.get('date_to')
            
            if date_from:
                try:
                    date_from = fields.Date.from_string(date_from)
                except (ValueError, TypeError):
                    date_from = None
            if date_to:
                try:
                    date_to = fields.Date.from_string(date_to)
                except (ValueError, TypeError):
                    date_to = None
            
            # Default to last 30 days if no dates provided
            if not date_from:
                date_from = fields.Date.today() - timedelta(days=30)
            if not date_to:
                date_to = fields.Date.today()
            
            # Build attendance domain
            date_from_dt = fields.Datetime.to_datetime(date_from)
            date_to_dt = fields.Datetime.to_datetime(date_to) + timedelta(days=1)
            attendance_domain = [
                ('checkin_time', '>=', date_from_dt),
                ('checkin_time', '<', date_to_dt)
            ]
            
            # Apply site filter
            site_ids = filter_params.get('site_ids', [])
            if site_ids:
                attendance_domain += [('site_id', 'in', site_ids)]
            
            # Apply guard filter
            guard_ids = filter_params.get('guard_ids', [])
            if guard_ids:
                attendance_domain += [('guard_id', 'in', guard_ids)]
            
            # Get all attendance records
            attendances = self.env['guard.attendance'].search(attendance_domain)
            
            # Build matrix: {guard_id: {date: True}}
            attendance_matrix = {}
            guard_names = {}
            dates_set = set()
            
            for att in attendances:
                if not att.guard_id:
                    continue
                
                guard_id = att.guard_id.id
                guard_name = att.guard_id.name
                badge_number = att.guard_id.badge_number or ''
                
                # Store guard info
                guard_names[guard_id] = {
                    'name': guard_name,
                    'badge': badge_number,
                    'display': f"{badge_number} - {guard_name}" if badge_number else guard_name
                }
                
                # Get date from checkin_time (convert to user timezone first)
                if att.checkin_time:
                    checkin_local = self._convert_to_user_tz(att.checkin_time)
                    checkin_date = checkin_local.date()
                    dates_set.add(checkin_date)
                    
                    if guard_id not in attendance_matrix:
                        attendance_matrix[guard_id] = {}
                    
                    # Mark as present if checkin exists for that date
                    attendance_matrix[guard_id][checkin_date] = True
            
            # Sort dates
            sorted_dates = sorted(dates_set)
            
            # Sort guards by name
            sorted_guards = sorted(guard_names.items(), key=lambda x: x[1]['name'])
            
            # Build result structure
            result = {
                'guards': [{'id': gid, 'name': info['name'], 'badge': info['badge'], 'display': info['display']} 
                          for gid, info in sorted_guards],
                'dates': [date.strftime('%Y-%m-%d') for date in sorted_dates],
                'matrix': attendance_matrix,
                'date_from': date_from.strftime('%Y-%m-%d'),
                'date_to': date_to.strftime('%Y-%m-%d')
            }
            
            return result
            
        except Exception as e:
            _logger.error("Error getting attendance matrix data: %s", e, exc_info=True)
            return {}
    
    def _get_package_analytics(self, filter_context=None):
        """
        Get comprehensive package delivery analytics.
        
        Returns:
            dict: Package analytics including:
                - Delivery time tracking
                - Collection rates
                - Overdue statistics
                - Package type distribution
                - Site-wise breakdown
        """
        filter_context = filter_context or {}
        
        try:
            # Get filter dates or use defaults
            date_from = filter_context.get('date_from')
            date_to = filter_context.get('date_to')
            today = date_to or fields.Date.today()
            
            # Ensure today is a date object
            if isinstance(today, str):
                today = fields.Date.from_string(today)
            
            # Calculate date range
            if date_from:
                month_start = date_from if isinstance(date_from, dt.date) else fields.Date.from_string(date_from)
            else:
                month_start = today.replace(day=1)
            
            # Get filter domains
            site_filter = filter_context.get('site_domain', [])
            site_ids = filter_context.get('site_ids', [])
            
            site_domain = []
            if site_filter:
                site_domain = self.env['client.site'].search(site_filter).ids
            elif site_ids:
                site_domain = site_ids
            
            # Base package domain
            month_start_dt = fields.Datetime.to_datetime(month_start)
            today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
            package_domain = [
                ('received_date', '>=', month_start_dt),
                ('received_date', '<', today_end)
            ]
            if site_domain:
                package_domain += [('site_id', 'in', site_domain)]
            
            # Get all packages in date range
            packages = self.env['package.management'].search(package_domain)
            
            # Total packages received
            total_packages = len(packages)
            
            # Packages by status
            collected_packages = packages.filtered(lambda p: p.state == 'collected')
            notified_packages = packages.filtered(lambda p: p.state == 'notified')
            received_packages = packages.filtered(lambda p: p.state == 'received')
            overdue_packages = packages.filtered(lambda p: p.is_overdue)
            unclaimed_packages = packages.filtered(lambda p: p.state == 'unclaimed')
            
            # Collection rate calculation
            collection_rate = (
                (len(collected_packages) / total_packages * 100) 
                if total_packages > 0 else 0
            )
            
            # Average delivery to collection time (in hours)
            delivery_times = []
            for pkg in collected_packages:
                if pkg.received_date and pkg.pickup_date:
                    delta = pkg.pickup_date - pkg.received_date
                    delivery_times.append(delta.total_seconds() / 3600)  # Convert to hours
            
            avg_delivery_time = (
                sum(delivery_times) / len(delivery_times) 
                if delivery_times else 0
            )
            
            # Median delivery time
            if delivery_times:
                sorted_times = sorted(delivery_times)
                n = len(sorted_times)
                median_delivery_time = (
                    sorted_times[n // 2] if n % 2 != 0 
                    else (sorted_times[n // 2 - 1] + sorted_times[n // 2]) / 2
                )
            else:
                median_delivery_time = 0
            
            # Package type distribution
            package_types_data = packages.read_group(
                [('id', 'in', packages.ids)],
                ['package_type'],
                ['package_type']
            )
            
            package_type_distribution = {
                data['package_type']: data['package_type_count']
                for data in package_types_data if data['package_type']
            }
            
            # Site-wise package statistics
            site_stats = []
            if site_domain:
                for site_id in site_domain:
                    site_packages = packages.filtered(lambda p: p.site_id.id == site_id)
                    site = self.env['client.site'].browse(site_id)
                    
                    if len(site_packages) > 0:
                        site_collected = site_packages.filtered(lambda p: p.state == 'collected')
                        site_overdue = site_packages.filtered(lambda p: p.is_overdue)
                        
                        site_stats.append({
                            'site_name': site.name,
                            'total_packages': len(site_packages),
                            'collected': len(site_collected),
                            'overdue': len(site_overdue),
                            'collection_rate': (
                                len(site_collected) / len(site_packages) * 100
                                if len(site_packages) > 0 else 0
                            )
                        })
            
            # Overdue statistics
            overdue_by_days = {
                '1-3 days': 0,
                '4-7 days': 0,
                '8-14 days': 0,
                '15-30 days': 0,
                '30+ days': 0
            }
            
            for pkg in overdue_packages:
                days_overdue = pkg.days_in_storage
                if days_overdue <= 3:
                    overdue_by_days['1-3 days'] += 1
                elif days_overdue <= 7:
                    overdue_by_days['4-7 days'] += 1
                elif days_overdue <= 14:
                    overdue_by_days['8-14 days'] += 1
                elif days_overdue <= 30:
                    overdue_by_days['15-30 days'] += 1
                else:
                    overdue_by_days['30+ days'] += 1
            
            # Daily package trend (last 30 days)
            daily_trend = []
            for i in range(29, -1, -1):
                day = today - timedelta(days=i)
                day_start = fields.Datetime.to_datetime(day)
                day_end = day_start + timedelta(days=1)
                
                day_domain = [
                    ('received_date', '>=', day_start),
                    ('received_date', '<', day_end)
                ]
                if site_domain:
                    day_domain += [('site_id', 'in', site_domain)]
                
                day_packages = self.env['package.management'].search(day_domain)
                day_collected = day_packages.filtered(lambda p: p.state == 'collected')
                
                daily_trend.append({
                    'date': day.strftime('%Y-%m-%d'),
                    'received': len(day_packages),
                    'collected': len(day_collected)
                })
            
            # Top couriers
            courier_stats = {}
            for pkg in packages:
                if pkg.courier:
                    if pkg.courier not in courier_stats:
                        courier_stats[pkg.courier] = {
                            'total': 0,
                            'collected': 0,
                            'overdue': 0
                        }
                    courier_stats[pkg.courier]['total'] += 1
                    if pkg.state == 'collected':
                        courier_stats[pkg.courier]['collected'] += 1
                    if pkg.is_overdue:
                        courier_stats[pkg.courier]['overdue'] += 1
            
            # Sort couriers by total packages
            top_couriers = sorted(
                [
                    {
                        'name': name,
                        **stats,
                        'collection_rate': (
                            stats['collected'] / stats['total'] * 100
                            if stats['total'] > 0 else 0
                        )
                    }
                    for name, stats in courier_stats.items()
                ],
                key=lambda x: x['total'],
                reverse=True
            )[:10]  # Top 10 couriers
            
            return {
                'summary': {
                    'total_packages': total_packages,
                    'collected': len(collected_packages),
                    'pending': len(received_packages) + len(notified_packages),
                    'overdue': len(overdue_packages),
                    'unclaimed': len(unclaimed_packages),
                    'collection_rate': round(collection_rate, 2),
                    'avg_delivery_time_hours': round(avg_delivery_time, 2),
                    'median_delivery_time_hours': round(median_delivery_time, 2),
                },
                'package_type_distribution': package_type_distribution,
                'site_stats': site_stats,
                'overdue_by_days': overdue_by_days,
                'daily_trend': daily_trend,
                'top_couriers': top_couriers,
                'date_from': month_start.strftime('%Y-%m-%d'),
                'date_to': today.strftime('%Y-%m-%d')
            }
            
        except Exception as e:
            _logger.error("Error getting package analytics: %s", e, exc_info=True)
            return {
                'summary': {},
                'package_type_distribution': {},
                'site_stats': [],
                'overdue_by_days': {},
                'daily_trend': [],
                'top_couriers': []
            }
    
    def action_view_package_analytics(self):
        """Open package analytics dashboard."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Package Analytics'),
            'res_model': 'package.management',
            'view_mode': 'kanban,list,graph,pivot',
            'domain': [('received_date', '>=', fields.Date.today().replace(day=1))],
            'context': {
                'search_default_group_by_state': 1,
                'search_default_current_month': 1,
            },
        }

