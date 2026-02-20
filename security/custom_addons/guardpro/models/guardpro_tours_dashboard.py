# -*- coding: utf-8 -*-
"""GuardPro Tours Dashboard Model."""

from odoo import models, fields, api, _
from odoo.tools import date_utils
from datetime import datetime, timedelta
import datetime as dt
import json
import logging
import pytz

_logger = logging.getLogger(__name__)


class GuardProToursDashboard(models.Model):
    """Tours Analytics Dashboard for GuardPro System."""

    _name = 'guardpro.tours.dashboard'
    _description = 'GuardPro Tours Dashboard'

    name = fields.Char(
        'Dashboard Name',
        required=True,
        default='Tours Dashboard'
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
            
            _logger.info(f"Tours KPI Data - Date Range: {month_start} to {today}")
        except Exception as e:
            _logger.error(f"Error processing KPI dates: {e}", exc_info=True)
            # Fallback to safe defaults
            today = fields.Date.today()
            month_start = today.replace(day=1)
        
        # Build filter domains
        site_domain = []
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
        
        # Build tour domain
        month_start_dt = fields.Datetime.to_datetime(month_start)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
        tour_domain = [
            ('start_time', '>=', month_start_dt),
            ('start_time', '<', today_end)
        ]
        if guard_ids:
            tour_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            tour_domain += [('site_id', 'in', site_domain)]
        
        # Total Tours
        total_tours = self.env['tour.log'].search_count(tour_domain)
        
        # Completed Tours
        completed_tours = self.env['tour.log'].search_count(
            tour_domain + [('status', '=', 'completed')]
        )
        
        # In Progress Tours
        in_progress_tours = self.env['tour.log'].search_count(
            tour_domain + [('status', '=', 'in_progress')]
        )
        
        # Cancelled Tours
        cancelled_tours = self.env['tour.log'].search_count(
            tour_domain + [('status', '=', 'cancelled')]
        )
        
        # Completion Rate
        completion_rate = (completed_tours / total_tours * 100) if total_tours > 0 else 0
        
        # Average Tour Duration
        completed_tour_records = self.env['tour.log'].search(
            tour_domain + [('status', '=', 'completed'), ('duration', '>', 0)]
        )
        avg_duration = sum(completed_tour_records.mapped('duration')) / len(completed_tour_records) if completed_tour_records else 0
        
        # Total Checkpoints Scanned
        scan_domain = [
            ('scan_time', '>=', month_start_dt),
            ('scan_time', '<', today_end)
        ]
        if guard_ids:
            scan_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            scan_domain += [('checkpoint_id.site_id', 'in', site_domain)]
        
        total_scans = self.env['checkpoint.scan'].search_count(scan_domain)
        
        # Checkpoint Compliance Rate
        # Calculate based on expected vs actual scans
        expected_checkpoints = sum(completed_tour_records.mapped('expected_checkpoints'))
        actual_checkpoints = sum(completed_tour_records.mapped('scanned_checkpoints'))
        checkpoint_compliance = (actual_checkpoints / expected_checkpoints * 100) if expected_checkpoints > 0 else 0
        
        # Tours Today
        today_start = fields.Datetime.to_datetime(today)
        today_end_dt = today_start + timedelta(days=1)
        tours_today_domain = [
            ('start_time', '>=', today_start),
            ('start_time', '<', today_end_dt)
        ]
        if guard_ids:
            tours_today_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            tours_today_domain += [('site_id', 'in', site_domain)]
        
        tours_today = self.env['tour.log'].search_count(tours_today_domain)
        
        # Overdue Tours
        overdue_domain = [
            ('status', 'in', ['in_progress', 'scheduled']),
            ('scheduled_end_time', '<', fields.Datetime.now())
        ]
        if guard_ids:
            overdue_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            overdue_domain += [('site_id', 'in', site_domain)]
        
        overdue_tours = self.env['tour.log'].search_count(overdue_domain)

        return [
            {
                'name': _('Total Tours'),
                'value': total_tours,
                'previous_value': total_tours,
                'icon': 'fa-route',
                'color': 'primary',
                'action': 'action_view_all_tours',
                'suffix': ''
            },
            {
                'name': _('Completed Tours'),
                'value': completed_tours,
                'previous_value': completed_tours,
                'icon': 'fa-check-circle',
                'color': 'success',
                'action': 'action_view_completed_tours',
                'suffix': ''
            },
            {
                'name': _('Completion Rate'),
                'value': round(completion_rate, 1),
                'previous_value': round(completion_rate, 1),
                'icon': 'fa-percent',
                'color': 'success' if completion_rate >= 90 else 'warning',
                'action': 'action_view_all_tours',
                'suffix': '%'
            },
            {
                'name': _('Average Duration'),
                'value': round(avg_duration, 1),
                'previous_value': round(avg_duration, 1),
                'icon': 'fa-clock-o',
                'color': 'info',
                'action': 'action_view_completed_tours',
                'suffix': ' min'
            },
            {
                'name': _('Tours Today'),
                'value': tours_today,
                'previous_value': tours_today,
                'icon': 'fa-calendar-day',
                'color': 'primary',
                'action': 'action_view_tours_today',
                'suffix': ''
            },
            {
                'name': _('In Progress'),
                'value': in_progress_tours,
                'previous_value': in_progress_tours,
                'icon': 'fa-spinner',
                'color': 'warning',
                'action': 'action_view_in_progress_tours',
                'suffix': ''
            },
            {
                'name': _('Checkpoint Scans'),
                'value': total_scans,
                'previous_value': total_scans,
                'icon': 'fa-qrcode',
                'color': 'info',
                'action': 'action_view_checkpoint_scans',
                'suffix': ''
            },
            {
                'name': _('Checkpoint Compliance'),
                'value': round(checkpoint_compliance, 1),
                'previous_value': round(checkpoint_compliance, 1),
                'icon': 'fa-tasks',
                'color': 'success' if checkpoint_compliance >= 90 else 'warning',
                'action': 'action_view_checkpoint_scans',
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
            
            if isinstance(today, str):
                today = fields.Date.from_string(today)
            
            if date_from:
                month_start = date_from if isinstance(date_from, dt.date) else fields.Date.from_string(date_from)
            else:
                month_start = today.replace(day=1)
            
        except Exception as e:
            _logger.error(f"Error processing chart dates: {e}", exc_info=True)
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
        
        # Build base tour domain
        month_start_dt = fields.Datetime.to_datetime(month_start)
        today_end = fields.Datetime.to_datetime(today) + timedelta(days=1)
        tour_base_domain = [
            ('start_time', '>=', month_start_dt),
            ('start_time', '<', today_end)
        ]
        if guard_ids:
            tour_base_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            tour_base_domain += [('site_id', 'in', site_domain)]
        
        # Chart 1: Tour Status Distribution (Pie Chart)
        status_data = self.env['tour.log'].read_group(
            tour_base_domain,
            ['status'],
            ['status']
        )
        
        tour_status_chart = {
            'type': 'pie',
            'title': _('Tour Status Distribution'),
            'labels': [_('Completed'), _('In Progress'), _('Cancelled'), _('Scheduled')],
            'keys': ['completed', 'in_progress', 'cancelled', 'scheduled'], # Drill-down keys
            'action_model': 'tour.log',
            'action_domain_field': 'status',
            'datasets': [{
                'label': _('Tours'),
                'data': [
                    next((d['status_count'] for d in status_data if d['status'] == 'completed'), 0),
                    next((d['status_count'] for d in status_data if d['status'] == 'in_progress'), 0),
                    next((d['status_count'] for d in status_data if d['status'] == 'cancelled'), 0),
                    next((d['status_count'] for d in status_data if d['status'] == 'scheduled'), 0),
                ],
                'backgroundColor': [
                    'rgba(75, 192, 192, 0.8)',
                    'rgba(255, 206, 86, 0.8)',
                    'rgba(255, 99, 132, 0.8)',
                    'rgba(153, 102, 255, 0.8)',
                ],
                'borderWidth': 1
            }]
        }
        
        # Chart 2: Daily Tour Completion Trend (Last 30 Days)
        daily_data = []
        daily_labels = []
        date_keys = []
        for i in range(29, -1, -1):
            day = today - timedelta(days=i)
            day_start = fields.Datetime.to_datetime(day)
            day_end = day_start + timedelta(days=1)
            
            day_domain = [
                ('start_time', '>=', day_start),
                ('start_time', '<', day_end),
                ('status', '=', 'completed')
            ]
            if guard_ids:
                day_domain += [('guard_id', 'in', guard_ids)]
            if site_domain and len(site_domain) > 0:
                day_domain += [('site_id', 'in', site_domain)]
            
            count = self.env['tour.log'].search_count(day_domain)
            daily_data.append(count)
            daily_labels.append(day.strftime('%m/%d'))
            date_keys.append({
                'start': day_start.strftime('%Y-%m-%d %H:%M:%S'),
                'end': day_end.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        tour_trend_chart = {
            'type': 'line',
            'title': _('Daily Tour Completions (Last 30 Days)'),
            'labels': daily_labels,
            'keys': date_keys, # Drill-down keys
            'action_model': 'tour.log',
            'action_type': 'date_range',
            'datasets': [{
                'label': _('Completed Tours'),
                'data': daily_data,
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 2,
                'fill': True,
                'tension': 0.4
            }]
        }
        
        # Chart 3: Average Tour Duration by Site (Bar Chart)
        if site_domain and len(site_domain) > 0:
            sites = self.env['client.site'].browse(site_domain)
        else:
            # Get top 10 sites by tour count
            site_data = self.env['tour.log'].read_group(
                tour_base_domain + [('status', '=', 'completed')],
                ['site_id', 'duration:avg'],
                ['site_id'],
                limit=10,
                orderby='site_id_count desc'
            )
            site_ids_from_data = [d['site_id'][0] for d in site_data if d['site_id']]
            sites = self.env['client.site'].browse(site_ids_from_data)
        
        site_labels = []
        site_durations = []
        site_keys = []
        for site in sites:
            site_tours = self.env['tour.log'].search([
                ('site_id', '=', site.id),
                ('status', '=', 'completed'),
                ('duration', '>', 0),
                ('start_time', '>=', month_start_dt),
                ('start_time', '<', today_end)
            ])
            if site_tours:
                avg_duration = sum(site_tours.mapped('duration')) / len(site_tours)
                site_labels.append(site.name)
                site_durations.append(round(avg_duration, 1))
                site_keys.append(site.id)

        duration_by_site_chart = {
            'type': 'bar',
            'title': _('Average Tour Duration by Site (minutes)'),
            'labels': site_labels,
            'keys': site_keys, # Drill-down keys
            'action_model': 'tour.log',
            'action_domain_field': 'site_id',
            'datasets': [{
                'label': _('Avg Duration (min)'),
                'data': site_durations,
                'backgroundColor': 'rgba(54, 162, 235, 0.8)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        }
        
        # Chart 4: Checkpoint Compliance by Guard (Top 10)
        guard_domain = tour_base_domain + [('status', '=', 'completed')]
        if guard_ids:
            guards = self.env['guard.profile'].browse(guard_ids)
        else:
            # Get top 10 guards by tour count
            guard_data = self.env['tour.log'].read_group(
                guard_domain,
                ['guard_id'],
                ['guard_id'],
                limit=10,
                orderby='guard_id_count desc'
            )
            guard_ids_from_data = [d['guard_id'][0] for d in guard_data if d['guard_id']]
            guards = self.env['guard.profile'].browse(guard_ids_from_data)
        
        guard_labels = []
        guard_compliance = []
        guard_keys = []
        for guard in guards:
            guard_tours = self.env['tour.log'].search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'completed'),
                ('start_time', '>=', month_start_dt),
                ('start_time', '<', today_end)
            ])
            if guard_tours:
                expected_checkpoints = sum(guard_tours.mapped('expected_checkpoints'))
                total_scanned = sum(guard_tours.mapped('scanned_checkpoints'))
                compliance = (total_scanned / expected_checkpoints * 100) if expected_checkpoints > 0 else 0
                guard_labels.append(guard.name)
                guard_compliance.append(round(compliance, 1))
                guard_keys.append(guard.id)
        
        guard_compliance_chart = {
            'type': 'bar',
            'title': _('Checkpoint Compliance by Guard (%)'),
            'labels': guard_labels,
            'keys': guard_keys, # Drill-down keys
            'action_model': 'tour.log',
            'action_domain_field': 'guard_id',
            'datasets': [{
                'label': _('Compliance %'),
                'data': guard_compliance,
                'backgroundColor': 'rgba(255, 159, 64, 0.8)',
                'borderColor': 'rgba(255, 159, 64, 1)',
                'borderWidth': 1
            }]
        }
        
        return [
            tour_status_chart,
            tour_trend_chart,
            duration_by_site_chart,
            guard_compliance_chart,
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
        
        # Recent Completed Tours (Last 10)
        tour_domain = [
            ('status', '=', 'completed')
        ]
        if date_from:
            tour_domain += [('start_time', '>=', fields.Datetime.to_datetime(date_from))]
        if guard_ids:
            tour_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            tour_domain += [('site_id', 'in', site_domain)]
        
        recent_tours = self.env['tour.log'].search(
            tour_domain, limit=10, order='end_time desc'
        )
        
        recent_tours_table = {
            'title': _('Recent Completed Tours'),
            'res_model': 'tour.log',
            'columns': [
                _('Tour #'),
                _('Guard'),
                _('Site'),
                _('Start Time'),
                _('Duration (min)'),
                _('Checkpoints'),
                _('Compliance %')
            ],
            'rows': [{
                'id': tour.id,
                'data': [
                    tour.name,
                    tour.guard_id.name,
                    tour.site_id.name,
                    self._convert_to_user_tz(tour.start_time).strftime('%Y-%m-%d %H:%M')
                    if tour.start_time else '',
                    round(tour.duration, 1),
                    f"{tour.scanned_checkpoints}/{tour.expected_checkpoints}",
                    round((tour.scanned_checkpoints / tour.expected_checkpoints * 100) if tour.expected_checkpoints > 0 else 0, 1)
                ]
            } for tour in recent_tours]
        }
        
        # In Progress Tours
        in_progress_domain = [
            ('status', '=', 'in_progress')
        ]
        if guard_ids:
            in_progress_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            in_progress_domain += [('site_id', 'in', site_domain)]
        
        in_progress_tours = self.env['tour.log'].search(
            in_progress_domain, limit=10, order='start_time desc'
        )
        
        in_progress_table = {
            'title': _('Tours In Progress'),
            'res_model': 'tour.log',
            'columns': [
                _('Tour #'),
                _('Guard'),
                _('Site'),
                _('Start Time'),
                _('Checkpoints'),
                _('Progress %')
            ],
            'rows': [{
                'id': tour.id,
                'data': [
                    tour.name,
                    tour.guard_id.name,
                    tour.site_id.name,
                    self._convert_to_user_tz(tour.start_time).strftime('%Y-%m-%d %H:%M')
                    if tour.start_time else '',
                    f"{tour.scanned_checkpoints}/{tour.expected_checkpoints}",
                    round((tour.scanned_checkpoints / tour.expected_checkpoints * 100) if tour.expected_checkpoints > 0 else 0, 1)
                ]
            } for tour in in_progress_tours]
        }
        
        # Overdue Tours
        overdue_domain = [
            ('status', 'in', ['in_progress', 'scheduled']),
            ('scheduled_end_time', '<', fields.Datetime.now())
        ]
        if guard_ids:
            overdue_domain += [('guard_id', 'in', guard_ids)]
        if site_domain and len(site_domain) > 0:
            overdue_domain += [('site_id', 'in', site_domain)]
        
        overdue_tours = self.env['tour.log'].search(
            overdue_domain, limit=10, order='scheduled_end_time asc'
        )
        
        overdue_table = {
            'title': _('Overdue Tours'),
            'res_model': 'tour.log',
            'columns': [
                _('Tour #'),
                _('Guard'),
                _('Site'),
                _('Start Time'),
                _('Expected End'),
                _('Status')
            ],
            'rows': [{
                'id': tour.id,
                'data': [
                    tour.name,
                    tour.guard_id.name,
                    tour.site_id.name,
                    self._convert_to_user_tz(tour.start_time).strftime('%Y-%m-%d %H:%M')
                    if tour.start_time else '',
                    self._convert_to_user_tz(tour.scheduled_end_time).strftime('%Y-%m-%d %H:%M')
                    if tour.scheduled_end_time else '',
                    dict(tour._fields['status'].selection)[tour.status],
                ]
            } for tour in overdue_tours]
        }

        return [recent_tours_table, in_progress_table, overdue_table]

    # Action methods for KPI cards (Must be @api.model for RPC access)
    @api.model
    def action_view_all_tours(self):
        """View all tours."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('All Tours'),
            'res_model': 'tour.log',
            'view_mode': 'tree,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {'create': False}
        }

    @api.model
    def action_view_completed_tours(self):
        """View completed tours."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Completed Tours'),
            'res_model': 'tour.log',
            'view_mode': 'tree,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [('status', '=', 'completed')],
            'context': {'create': False}
        }

    @api.model
    def action_view_tours_today(self):
        """View tours today."""
        today_start = fields.Datetime.to_datetime(fields.Date.today())
        today_end = today_start + timedelta(days=1)
        return {
            'type': 'ir.actions.act_window',
            'name': _('Tours Today'),
            'res_model': 'tour.log',
            'view_mode': 'tree,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [
                ('start_time', '>=', today_start),
                ('start_time', '<', today_end)
            ],
            'context': {'create': False}
        }

    @api.model
    def action_view_in_progress_tours(self):
        """View in progress tours."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('In Progress Tours'),
            'res_model': 'tour.log',
            'view_mode': 'tree,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [('status', '=', 'in_progress')],
            'context': {'create': False}
        }

    @api.model
    def action_view_checkpoint_scans(self):
        """View checkpoint scans."""
        return {
            'type': 'ir.actions.act_window',
            'name': _('Checkpoint Scans'),
            'res_model': 'checkpoint.scan',
            'view_mode': 'tree,form',
            'views': [[False, 'list'], [False, 'form']],
            'target': 'current',
            'domain': [],
            'context': {'create': False}
        }

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

        if client_ids:
            client_site_ids = self.env['client.site'].search([
                ('client_id', 'in', client_ids)
            ]).ids
            client_site_ids = set(client_site_ids)
            sanitized_sites = (sanitized_sites & client_site_ids) if sanitized_sites else client_site_ids

        if enforce_limits:
            assigned_set = set(assigned_site_ids)
            if not assigned_set:
                return [], _('No sites are assigned to your user. Please contact your administrator.'), False
            
            if sanitized_sites:
                sanitized_sites &= assigned_set
            elif not filter_requested:
                sanitized_sites = assigned_set
            else:
                force_empty = True

        if filter_requested and not sanitized_sites:
            force_empty = True

        return sorted(sanitized_sites), None, force_empty

    def _sanitize_guard_filters(self, guard_ids=None, allowed_site_ids=None):
        """Ensure guard filters are limited to allowed sites."""
        guard_ids = guard_ids or []
        allowed_site_ids = allowed_site_ids or []
        if not guard_ids or not allowed_site_ids:
            return []
        return self.env['guard.profile'].search([
            ('id', 'in', guard_ids),
            ('site_ids', 'in', allowed_site_ids)
        ]).ids

    @api.model
    def get_dashboard_data(self, dashboard_id=None, context=None, filter_params=None):
        """API method for fetching dashboard data with security sanitization."""
        try:
            # Handle parameters
            if not filter_params and context:
                filter_params = context.get('filter_params', {}) or {}
            filter_params = dict(filter_params or {})
            
            # Helper to sanitize IDs
            def sanitize_ids(ids):
                if not ids: return []
                if isinstance(ids, (int, str)): ids = [ids]
                return [int(i) for i in ids if i and str(i).lstrip('-').isdigit()]

            date_from = filter_params.get('date_from')
            date_to = filter_params.get('date_to')
            site_ids = sanitize_ids(filter_params.get('site_ids', []))
            guard_ids = sanitize_ids(filter_params.get('guard_ids', []))
            client_ids = sanitize_ids(filter_params.get('client_ids', []))
            
            # Convert dates
            if date_from and isinstance(date_from, str):
                date_from = fields.Date.from_string(date_from)
            if date_to and isinstance(date_to, str):
                date_to = fields.Date.from_string(date_to)
            
            # Security limits
            user = self.env.user
            is_admin = user.has_group('guardpro.group_guardpro_admin') or user.has_group('base.group_system')
            enforce_site_limits = not is_admin and (
                user.has_group('guardpro.group_guardpro_client_user') or
                user.has_group('guardpro.group_guardpro_supervisor') or
                user.has_group('guardpro.group_guardpro_manager')
            )
            assigned_site_ids = user.site_ids.ids
            
            # Sanitize sites
            sanitized_sites, site_error, force_empty = self._sanitize_site_filters(
                site_ids=site_ids,
                client_ids=client_ids,
                enforce_limits=enforce_site_limits,
                assigned_site_ids=assigned_site_ids
            )
            if site_error:
                return {'kpis': [], 'charts': [], 'tables': [], 'error': site_error}
            
            # Site results
            site_ids = sanitized_sites
            filter_context = {
                'date_from': date_from,
                'date_to': date_to,
                'site_ids': [-1] if force_empty else site_ids,
                'guard_ids': guard_ids,
            }

            # Sanitize guards if sites are limited
            if enforce_site_limits and guard_ids:
                filter_context['guard_ids'] = self._sanitize_guard_filters(
                    guard_ids=guard_ids,
                    allowed_site_ids=site_ids or assigned_site_ids
                )

            return {
                'kpis': self._get_kpi_data(filter_context),
                'charts': self._get_chart_data(filter_context),
                'tables': self._get_table_data(filter_context),
            }
        except Exception as e:
            _logger.error(f"Error computing tours dashboard data: {e}", exc_info=True)
            return {'kpis': [], 'charts': [], 'tables': [], 'error': str(e)}

    @api.model
    def get_report_data(self, filter_params=None):
        """Prepare dashboard data for PDF export."""
        _logger.info("=== Tours PDF Export: Getting report data ===")
        _logger.info("Filter params received: %s", filter_params)
        filter_params = filter_params or {}
        
        try:
            # Get dashboard data with filters
            dashboard_data = self.get_dashboard_data(filter_params=filter_params)
            _logger.info("Dashboard data retrieved successfully")
            
            # Get filter information for display
            site_ids = filter_params.get('site_ids', [])
            site_names = []
            if site_ids:
                # Ensure site_ids is a list of integers
                site_ids_int = []
                for sid in site_ids:
                    try:
                        site_ids_int.append(int(sid))
                    except:
                        continue
                sites = self.env['client.site'].browse(site_ids_int)
                site_names = sites.mapped('name')
                
            guard_ids = filter_params.get('guard_ids', [])
            guard_names = []
            if guard_ids:
                # Ensure guard_ids is a list of integers
                guard_ids_int = []
                for gid in guard_ids:
                    try:
                        guard_ids_int.append(int(gid))
                    except:
                        continue
                guards = self.env['guard.profile'].browse(guard_ids_int)
                guard_names = guards.mapped('name')
                
            filters_info = {
                'date_from': filter_params.get('date_from', ''),
                'date_to': filter_params.get('date_to', ''),
                'site_names': site_names,
                'guard_names': guard_names,
            }
            
            result = {
                'kpis': dashboard_data.get('kpis', []),
                'charts': dashboard_data.get('charts', []),
                'tables': dashboard_data.get('tables', []),
                'filters': filters_info
            }
            _logger.info("Returning report data with %s KPIs", len(result['kpis']))
            return result
        except Exception as e:
            _logger.error("Error in get_report_data: %s", e, exc_info=True)
            return {
                'kpis': [],
                'charts': [],
                'tables': [],
                'filters': {}
            }
