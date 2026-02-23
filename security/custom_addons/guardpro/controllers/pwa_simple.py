# -*- coding: utf-8 -*-
"""Guard Pro PWA Controller - Simplified Odoo-Native Implementation.

This module provides a clean PWA interface using Odoo's standard web framework.
Following Odoo 18 best practices - minimal custom JavaScript, using standard views and actions.
"""

import logging
import json
import base64
from odoo import http, fields
from odoo.http import request
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class GuardProPWASimple(http.Controller):
    """Simplified PWA Controller using Odoo's standard patterns."""

    def _format_datetime_tz(self, record, datetime_value, format_str='%H:%M'):
        """Format datetime in user's timezone."""
        if not datetime_value:
            return ''
        user_tz = request.env.user.tz or 'UTC'
        tz_dt = fields.Datetime.context_timestamp(
            record.with_context(tz=user_tz).sudo(),
            datetime_value
        )
        return tz_dt.strftime(format_str)

    def _get_guard_from_user(self):
        """Get guard profile from current user."""
        user = request.env.user
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not guard:
            # Check if user is an employee with a guard profile
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            if employee:
                guard = request.env['guard.profile'].sudo().search([
                    ('employee_id', '=', employee.id)
                ], limit=1)
        
        return guard

    @http.route('/guardpro/mobile', type='http', auth='user', website=True)
    def mobile_dashboard(self, **kwargs):
        """Main mobile dashboard using Odoo website framework."""
        _logger.info('[GuardPro Mobile] Accessed by user: %s (ID: %s)', request.env.user.name, request.env.user.id)
        
        guard = self._get_guard_from_user()
        
        if not guard:
            _logger.warning('[Guard Pro Mobile] No guard profile found for user: %s', request.env.user.name)
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get today's data
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Fetch data using Odoo ORM (no caching needed - let Odoo handle it)
        shifts_today = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<', today_end),
        ], limit=5, order='start_datetime asc')
        
        active_tasks = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', 'in', ['assigned', 'in_progress']),
        ], limit=10, order='priority desc, due_date asc')
        
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        recent_incidents = request.env['incident.report'].sudo().search([
            ('guard_id', '=', guard.id),
        ], limit=5, order='incident_datetime desc')
        
        return request.render('guardpro.mobile_dashboard', {
            'guard': guard,
            'user': request.env.user,
            'shifts_today': shifts_today,
            'active_tasks': active_tasks,
            'is_checked_in': bool(active_attendance),
            'active_attendance': active_attendance,
            'recent_incidents': recent_incidents,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/checkin', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_checkin(self, latitude=None, longitude=None, **kwargs):
        """Check in - Standard form submission."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        
        # Check existing attendance
        existing = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1)
        
        if existing:
            return request.redirect('/guardpro/mobile?error=already_checked_in')
        
        # Find active shift
        now = datetime.now()
        shift = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '<=', now + timedelta(hours=2)),
            ('end_datetime', '>=', now - timedelta(hours=1)),
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
        ], limit=1, order='start_datetime asc')
        
        site_id = shift.site_id.id if shift else None
        
        # Fallback: Try guard's current site if no active shift
        if not site_id:
            if hasattr(guard, 'current_site_id') and guard.current_site_id:
                site_id = guard.current_site_id.id
                _logger.info('[Mobile Check-In] Using guard current_site_id: %s (ID: %s)', 
                           guard.current_site_id.name, site_id)
        
        # Fallback: Try last attendance site
        if not site_id:
            last_attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('site_id', '!=', False),
            ], limit=1, order='checkin_time desc')
            if last_attendance:
                site_id = last_attendance.site_id.id
                _logger.info('[Mobile Check-In] Using last attendance site: %s (ID: %s)', 
                           last_attendance.site_id.name, site_id)
        
        # Fallback: Try guard's assigned sites (first one)
        if not site_id:
            if guard.site_ids:
                site_id = guard.site_ids[0].id
                _logger.info('[Mobile Check-In] Using first assigned site: %s (ID: %s)', 
                           guard.site_ids[0].name, site_id)
        
        if not site_id:
            _logger.error('[Mobile Check-In] No site found for guard %s (ID: %s). '
                        'Guard has no active shift, no current_site_id, no previous attendance, and no assigned sites.', 
                        guard.name, guard.id)
            return request.redirect('/guardpro/mobile?error=no_site')
        
        # Create attendance
        vals = {
            'guard_id': guard.id,
            'site_id': site_id,
            'checkin_time': datetime.now(),
            'checkin_method': 'mobile_app',
        }
        
        if latitude and longitude:
            try:
                vals.update({
                    'checkin_latitude': float(latitude),
                    'checkin_longitude': float(longitude),
                })
            except (ValueError, TypeError):
                pass
        
        if shift:
            vals['shift_id'] = shift.id
        
        request.env['guard.attendance'].sudo().create(vals)
        
        return request.redirect('/guardpro/mobile?success=checked_in')

    @http.route('/guardpro/mobile/checkout', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_checkout(self, latitude=None, longitude=None, **kwargs):
        """Check out - Standard form submission."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        
        # Find active attendance
        attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        if not attendance:
            return request.redirect('/guardpro/mobile?error=not_checked_in')
        
        # Update attendance
        vals = {
            'checkout_time': datetime.now(),
            'checkout_method': 'mobile_app',
        }
        
        if latitude and longitude:
            try:
                vals.update({
                    'checkout_latitude': float(latitude),
                    'checkout_longitude': float(longitude),
                })
            except (ValueError, TypeError):
                pass
        
        attendance.write(vals)
        
        return request.redirect('/guardpro/mobile?success=checked_out')

    @http.route('/guardpro/mobile/task/start/<int:task_id>', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_task_start(self, task_id, **kwargs):
        """Start a task - Standard action."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        
        task = request.env['guard.task'].sudo().search([
            ('id', '=', task_id),
            ('assigned_to', '=', guard.id),
        ], limit=1)
        
        if not task:
            return request.redirect('/guardpro/mobile?error=task_not_found')
        
        if task.state not in ['draft', 'assigned']:
            return request.redirect('/guardpro/mobile?error=task_cannot_start')
        
        try:
            task.action_start()
            return request.redirect('/guardpro/mobile?success=task_started')
        except Exception as e:
            _logger.error("Task start error: %s", str(e))
            return request.redirect('/guardpro/mobile?error=task_start_failed')

    @http.route('/guardpro/mobile/task/complete/<int:task_id>', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_task_complete(self, task_id, notes=None, **kwargs):
        """Complete a task - Standard action."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        
        task = request.env['guard.task'].sudo().search([
            ('id', '=', task_id),
            ('assigned_to', '=', guard.id),
        ], limit=1)
        
        if not task:
            return request.redirect('/guardpro/mobile?error=task_not_found')
        
        if notes:
            task.write({'completion_notes': notes})
        
        try:
            task.action_complete()
            return request.redirect('/guardpro/mobile?success=task_completed')
        except Exception as e:
            _logger.error("Task complete error: %s", str(e))
            return request.redirect('/guardpro/mobile?error=task_complete_failed')

    @http.route('/guardpro/mobile/panic', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_panic(self, latitude=None, longitude=None, **kwargs):
        """Emergency panic button."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile?success=panic_sent')
        
        # Create emergency incident
        # Note: incident.report requires category_id and site_id
        # Get emergency category or create default
        emergency_category = request.env['incident.category'].sudo().search([
            ('name', 'ilike', 'emergency')
        ], limit=1)
        
        if not emergency_category:
            emergency_category = request.env['incident.category'].sudo().search([], limit=1)
        
        # Get site from active attendance or latest shift
        site_id = None
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        if active_attendance and active_attendance.site_id:
            site_id = active_attendance.site_id.id
        else:
            # Try to get from latest shift
            latest_shift = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),
            ], limit=1, order='start_datetime desc')
            if latest_shift and latest_shift.site_id:
                site_id = latest_shift.site_id.id
        
        # If still no site, get any site (required field)
        if not site_id:
            any_site = request.env['client.site'].sudo().search([], limit=1)
            site_id = any_site.id if any_site else None
        
        vals = {
            'guard_id': guard.id,
            'site_id': site_id,
            'category_id': emergency_category.id if emergency_category else False,
            'severity': 'critical',
            'title': 'PANIC ALERT',
            'description': f'Panic button activated by {guard.name}',
            'incident_datetime': datetime.now(),
            'status': 'open',
        }
        
        if latitude and longitude:
            try:
                vals.update({
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                })
            except (ValueError, TypeError):
                pass
        
        try:
            request.env['incident.report'].sudo().create(vals)
        except Exception as e:
            _logger.error("Panic incident creation error: %s", str(e))
        
        # Always show success for panic
        return request.redirect('/guardpro/mobile?success=panic_sent')

    # ==========================================
    # Separate Screen Routes
    # ==========================================

    @http.route('/guardpro/mobile/shifts', type='http', auth='user', website=True)
    def mobile_shifts(self, **kwargs):
        """Shifts screen - View and manage shifts."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get shifts - today, upcoming, and past
        # Use Odoo's Datetime utilities for proper UTC handling
        import pytz
        now_utc = fields.Datetime.now()
        
        # Get today in user's timezone, then convert to UTC for database comparison
        user_tz = request.env.user.tz or 'UTC'
        tz = pytz.timezone(user_tz)
        
        # Get current time in user's timezone
        today_start_local = fields.Datetime.context_timestamp(
            request.env['guard.shift'].with_context(tz=user_tz).sudo(),
            now_utc
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Convert local midnight back to UTC (context_timestamp already returns timezone-aware datetime)
        today_start_utc = today_start_local.astimezone(pytz.UTC).replace(tzinfo=None)
        today_end_utc = today_start_utc + timedelta(days=1)
        
        _logger.info('[GuardPro Mobile Shifts] Guard: %s, User TZ: %s, Today Start UTC: %s', 
                     guard.name, user_tz, today_start_utc)
        
        shifts_today = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_start_utc),
            ('start_datetime', '<', today_end_utc),
        ], order='start_datetime asc')
        
        upcoming_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_end_utc),
        ], limit=10, order='start_datetime asc')
        
        past_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '<', today_start_utc),
        ], limit=10, order='start_datetime desc')
        
        _logger.info('[GuardPro Mobile Shifts] Found %d today, %d upcoming, %d past shifts', 
                     len(shifts_today), len(upcoming_shifts), len(past_shifts))
        
        return request.render('guardpro.mobile_shifts', {
            'guard': guard,
            'user': request.env.user,
            'shifts_today': shifts_today,
            'upcoming_shifts': upcoming_shifts,
            'past_shifts': past_shifts,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/tours', type='http', auth='user', website=True)
    def mobile_tours(self, **kwargs):
        """Tours/Patrols screen - View and perform tours."""
        user = request.env.user
        _logger.info('[Mobile Tours] ===== START ===== User: %s (ID: %s, Login: %s)', 
                    user.name, user.id, user.login)
        
        guard = self._get_guard_from_user()
        
        if not guard:
            _logger.warning('[Mobile Tours] No guard profile found for user %s (ID: %s)', 
                          user.name, user.id)
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        _logger.info('[Mobile Tours] Guard found: %s (ID: %s)', guard.name, guard.id)
        
        # Get active tour logs (in progress)
        active_tours = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', '=', 'in_progress'),
        ], order='start_time desc')
        
        # Log tour progress for debugging
        for tour in active_tours:
            _logger.info('[Mobile Tours Page] Tour %s: %d/%d checkpoints scanned (%.1f%%), %d scan records',
                        tour.name, tour.scanned_checkpoints, tour.expected_checkpoints,
                        tour.completion_percentage, len(tour.scan_ids))
        
        # Get completed tour logs
        completed_tours = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'in', ['completed', 'incomplete']),
        ], limit=10, order='end_time desc')
        
        # Get available checkpoints for current site
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        # Get available tours that can be started
        # Check shifts that are relevant to today/current time (not just active status)
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        _logger.info('[Mobile Tours] ===== Checking shifts for guard %s (ID: %s) =====', 
                    guard.name, guard.id)
        
        # Get shifts that are happening today or upcoming (not cancelled/no_show)
        # Include shifts that:
        # 1. Start today or in the future (not past completed shifts)
        # 2. Or are currently in progress (end_datetime hasn't passed)
        # 3. Exclude cancelled/no_show shifts
        all_guard_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'not in', ['cancelled', 'no_show']),  # Exclude cancelled/no_show
        ], limit=100, order='start_datetime desc')
        
        # Filter to shifts that are relevant (today or upcoming, or still in progress)
        relevant_shifts = all_guard_shifts.filtered(lambda s: 
            (s.start_datetime and s.start_datetime >= today_start) or  # Starts today or later
            (s.end_datetime and s.end_datetime >= now)  # Or hasn't ended yet
        )
        
        _logger.info('[Mobile Tours] Total relevant shifts found for guard: %d', len(relevant_shifts))
        for shift in relevant_shifts:
            _logger.info('[Mobile Tours] Shift: %s (ID: %s), Status: %s, Start: %s, End: %s, Tour count: %d', 
                        shift.name, shift.id, shift.status, shift.start_datetime, shift.end_datetime, len(shift.tour_ids))
            if shift.tour_ids:
                for tour in shift.tour_ids:
                    _logger.info('[Mobile Tours]   - Tour: %s (ID: %s), Status: %s', 
                                tour.name, tour.id, tour.status)
        
        # Collect tour IDs from relevant shifts
        tour_ids_from_shifts = []
        
        # Collect tours from all relevant shifts (not just active status)
        # This includes shifts that are scheduled, confirmed, in_progress, or even completed if they're today
        for shift in relevant_shifts:
            if shift.tour_ids:
                # Include tours with status 'active' or 'draft' (draft tours assigned to shifts should be available)
                available_tours_in_shift = shift.tour_ids.filtered(lambda t: t.status in ['active', 'draft'])
                if available_tours_in_shift:
                    tour_ids_from_shifts.extend(available_tours_in_shift.ids)
                    _logger.info('[Mobile Tours] Shift %s (ID: %s, Status: %s) has %d available tours (status: active or draft)', 
                                shift.name, shift.id, shift.status, len(available_tours_in_shift))
                    for tour in available_tours_in_shift:
                        _logger.info('[Mobile Tours]     - Available tour: %s (ID: %s, Status: %s)', tour.name, tour.id, tour.status)
        
        # Remove duplicates
        tour_ids_from_shifts = list(set(tour_ids_from_shifts))
        _logger.info('[Mobile Tours] Collected %d unique tour IDs from relevant shifts: %s', 
                    len(tour_ids_from_shifts), tour_ids_from_shifts)
        
        # Exclude tours that are already in progress
        active_tour_ids = active_tours.mapped('tour_id').ids if active_tours else []
        _logger.info('[Mobile Tours] Active tour IDs (to exclude): %s', active_tour_ids)
        
        if tour_ids_from_shifts:
            # Get tours assigned to guard's shifts, excluding those already in progress
            available_tour_ids = [tid for tid in tour_ids_from_shifts if tid not in active_tour_ids]
            _logger.info('[Mobile Tours] Available tour IDs (after excluding active): %s', available_tour_ids)
            
            if available_tour_ids:
                # Include tours with status 'active' or 'draft' (draft tours assigned to shifts should be available)
                available_tours = request.env['security.tour'].sudo().search([
                    ('id', 'in', available_tour_ids),
                    ('status', 'in', ['active', 'draft']),
                ])
                _logger.info('[Mobile Tours] ✓✓✓ Found %d available tours assigned to guard %s shifts (%d already in progress)', 
                            len(available_tours), guard.name, len(active_tours))
                for tour in available_tours:
                    _logger.info('[Mobile Tours] ✓ Available tour: %s (ID: %s)', tour.name, tour.id)
            else:
                available_tours = request.env['security.tour'].sudo().browse([])
                _logger.info('[Mobile Tours] All tours from shifts are already in progress')
        else:
            # No tours found in shifts - try site-based fallback
            _logger.warning('[Mobile Tours] No tours found in shifts for guard %s', guard.name)
            if active_attendance and active_attendance.site_id:
                available_tours = request.env['security.tour'].sudo().search([
                    ('site_id', '=', active_attendance.site_id.id),
                    ('status', '=', 'active'),
                    ('id', 'not in', active_tour_ids),
                ])
                _logger.info('[Mobile Tours] Fallback: Found %d tours for site %s (%d already in progress)', 
                            len(available_tours), active_attendance.site_id.name, len(active_tours))
            else:
                available_tours = request.env['security.tour'].sudo().browse([])
                _logger.warning('[Mobile Tours] ✗✗✗ No tours found - guard not checked in and no tours assigned to shifts. '
                               'Total shifts checked: %d', len(all_guard_shifts))
        
        _logger.info('[Mobile Tours] ===== END - Returning %d available tours =====', len(available_tours))
        
        response = request.render('guardpro.mobile_tours', {
            'guard': guard,
            'user': request.env.user,
            'active_tours': active_tours,
            'completed_tours': completed_tours,
            'available_tours': available_tours,
            'is_checked_in': bool(active_attendance),
            'format_datetime_tz': self._format_datetime_tz,
        })
        
        # Disable caching to ensure fresh tour progress data
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        return response

    @http.route('/guardpro/mobile/tasks', type='http', auth='user', website=True)
    def mobile_tasks(self, **kwargs):
        """Tasks screen - View and manage tasks."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get tasks by state
        tasks_assigned = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'assigned'),
        ], order='priority desc, due_date asc')
        
        tasks_in_progress = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'in_progress'),
        ], order='priority desc, due_date asc')
        
        tasks_completed = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'completed'),
        ], limit=10, order='completed_date desc')
        
        return request.render('guardpro.mobile_tasks', {
            'guard': guard,
            'user': request.env.user,
            'tasks_assigned': tasks_assigned,
            'tasks_in_progress': tasks_in_progress,
            'tasks_completed': tasks_completed,
        })

    @http.route('/guardpro/mobile/incidents', type='http', auth='user', website=True)
    def mobile_incidents(self, **kwargs):
        """Incidents screen - View and report incidents."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get incidents
        open_incidents = request.env['incident.report'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'in', ['submitted', 'under_review', 'investigating']),
        ], order='incident_datetime desc')
        
        recent_incidents = request.env['incident.report'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'in', ['resolved', 'closed']),
        ], limit=10, order='incident_datetime desc')
        
        # Get incident categories
        categories = request.env['incident.category'].sudo().search([])
        
        # Get current site
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        current_site = active_attendance.site_id if active_attendance else None
        
        return request.render('guardpro.mobile_incidents', {
            'guard': guard,
            'user': request.env.user,
            'open_incidents': open_incidents,
            'recent_incidents': recent_incidents,
            'categories': categories,
            'current_site': current_site,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/incident/create', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_incident_create(self, title=None, description=None, category_id=None, 
                               severity=None, latitude=None, longitude=None, **kwargs):
        """Create a new incident report."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile/incidents?error=no_guard')
        
        if not title or not description:
            return request.redirect('/guardpro/mobile/incidents?error=missing_fields')
        
        # Get site from active attendance
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        site_id = active_attendance.site_id.id if active_attendance and active_attendance.site_id else None
        
        # If no site, try to get from latest shift
        if not site_id:
            latest_shift = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),
            ], limit=1, order='start_datetime desc')
            if latest_shift and latest_shift.site_id:
                site_id = latest_shift.site_id.id
        
        # If still no site, get any site (required field)
        if not site_id:
            any_site = request.env['client.site'].sudo().search([], limit=1)
            site_id = any_site.id if any_site else None
        
        if not site_id:
            return request.redirect('/guardpro/mobile/incidents?error=no_site')
        
        vals = {
            'guard_id': guard.id,
            'site_id': site_id,
            'title': title,
            'description': description,
            'severity': severity or 'medium',
            'incident_datetime': datetime.now(),
            'status': 'submitted',
        }
        
        if category_id:
            try:
                vals['category_id'] = int(category_id)
            except (ValueError, TypeError):
                pass
        
        if 'location' in kwargs:
            vals['location'] = kwargs['location']
        
        if latitude and longitude:
            try:
                vals.update({
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                })
            except (ValueError, TypeError):
                pass
        
        try:
            # Create the incident report
            incident = request.env['incident.report'].sudo().create(vals)
            
            # Handle image uploads
            uploaded_files = request.httprequest.files.getlist('incident_images')
            if uploaded_files:
                attachment_ids = []
                for uploaded_file in uploaded_files:
                    if uploaded_file and uploaded_file.filename:
                        try:
                            # Read file content
                            file_content = uploaded_file.read()
                            file_base64 = base64.b64encode(file_content)
                            
                            # Create attachment
                            attachment = request.env['ir.attachment'].sudo().create({
                                'name': uploaded_file.filename,
                                'type': 'binary',
                                'datas': file_base64,
                                'res_model': 'incident.report',
                                'res_id': incident.id,
                                'mimetype': uploaded_file.content_type or 'image/jpeg',
                            })
                            attachment_ids.append(attachment.id)
                            _logger.info("Created attachment %s for incident %s", 
                                       uploaded_file.filename, incident.name)
                        except Exception as e:
                            _logger.error("Error uploading file %s: %s", 
                                        uploaded_file.filename, str(e))
                
                # Link attachments to incident photos
                if attachment_ids:
                    incident.sudo().write({
                        'photo_ids': [(6, 0, attachment_ids)]
                    })
            
            return request.redirect('/guardpro/mobile/incidents?success=incident_created')
        except Exception as e:
            _logger.error("Incident creation error: %s", str(e))
            return request.redirect('/guardpro/mobile/incidents?error=creation_failed')

    @http.route('/guardpro/mobile/incident/<int:incident_id>', type='http', auth='user', website=True)
    def mobile_incident_detail(self, incident_id, **kwargs):
        """View and edit incident details."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get incident - ensure it belongs to this guard
        incident = request.env['incident.report'].sudo().search([
            ('id', '=', incident_id),
            ('guard_id', '=', guard.id),
        ], limit=1)
        
        if not incident:
            return request.redirect('/guardpro/mobile/incidents?error=incident_not_found')
        
        # Get incident categories
        categories = request.env['incident.category'].sudo().search([])
        
        # Get sites available to guard
        sites = request.env['client.site'].sudo().search([])
        
        return request.render('guardpro.mobile_incident_detail', {
            'guard': guard,
            'user': request.env.user,
            'incident': incident,
            'categories': categories,
            'sites': sites,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/incident/<int:incident_id>/update', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_incident_update(self, incident_id, **kwargs):
        """Update incident report with all fields."""
        _logger = logging.getLogger(__name__)
        _logger.info('[Mobile Incident Update] Received update request for incident %s', incident_id)
        _logger.debug('[Mobile Incident Update] Form data keys: %s', list(kwargs.keys()))
        
        guard = self._get_guard_from_user()
        
        if not guard:
            _logger.warning('[Mobile Incident Update] No guard profile found for user %s', request.env.user.name)
            return request.redirect('/guardpro/mobile/incidents?error=no_guard')
        
        # Get incident - ensure it belongs to this guard
        incident = request.env['incident.report'].sudo().search([
            ('id', '=', incident_id),
            ('guard_id', '=', guard.id),
        ], limit=1)
        
        if not incident:
            _logger.warning('[Mobile Incident Update] Incident %s not found or doesn\'t belong to guard %s', incident_id, guard.name)
            return request.redirect('/guardpro/mobile/incidents?error=incident_not_found')
        
        try:
            # Prepare update values
            vals = {}
            
            # Basic fields
            if 'title' in kwargs:
                vals['title'] = kwargs['title']
            if 'description' in kwargs:
                vals['description'] = kwargs['description']
            if 'category_id' in kwargs and kwargs['category_id']:
                try:
                    vals['category_id'] = int(kwargs['category_id'])
                except (ValueError, TypeError):
                    pass
            if 'severity' in kwargs:
                vals['severity'] = kwargs['severity']
            if 'location' in kwargs:
                vals['location'] = kwargs['location']
            if 'latitude' in kwargs and kwargs['latitude']:
                try:
                    vals['latitude'] = float(kwargs['latitude'])
                except (ValueError, TypeError):
                    pass
            if 'longitude' in kwargs and kwargs['longitude']:
                try:
                    vals['longitude'] = float(kwargs['longitude'])
                except (ValueError, TypeError):
                    pass
            
            # People involved
            if 'persons_involved' in kwargs:
                vals['persons_involved'] = kwargs['persons_involved']
            if 'witnesses' in kwargs:
                vals['witnesses'] = kwargs['witnesses']
            
            # Actions taken
            if 'immediate_actions' in kwargs:
                vals['immediate_actions'] = kwargs['immediate_actions']
            
            # Emergency services
            if 'police_notified' in kwargs:
                vals['police_notified'] = kwargs.get('police_notified') == 'on' or kwargs.get('police_notified') == 'true'
            if 'police_report_number' in kwargs:
                vals['police_report_number'] = kwargs['police_report_number']
            if 'medical_required' in kwargs:
                vals['medical_required'] = kwargs.get('medical_required') == 'on' or kwargs.get('medical_required') == 'true'
            if 'ambulance_called' in kwargs:
                vals['ambulance_called'] = kwargs.get('ambulance_called') == 'on' or kwargs.get('ambulance_called') == 'true'
            if 'fire_department' in kwargs:
                vals['fire_department'] = kwargs.get('fire_department') == 'on' or kwargs.get('fire_department') == 'true'
            
            # Injuries
            if 'injuries' in kwargs:
                vals['injuries'] = kwargs.get('injuries') == 'on' or kwargs.get('injuries') == 'true'
            if 'injury_details' in kwargs:
                vals['injury_details'] = kwargs['injury_details']
            
            # Property damage
            if 'property_damage' in kwargs:
                vals['property_damage'] = kwargs.get('property_damage') == 'on' or kwargs.get('property_damage') == 'true'
            if 'damage_details' in kwargs:
                vals['damage_details'] = kwargs['damage_details']
            if 'estimated_cost' in kwargs and kwargs['estimated_cost']:
                try:
                    vals['estimated_cost'] = float(kwargs['estimated_cost'])
                except (ValueError, TypeError):
                    pass
            
            # Follow-up
            if 'requires_followup' in kwargs:
                vals['requires_followup'] = kwargs.get('requires_followup') == 'on' or kwargs.get('requires_followup') == 'true'
            if 'followup_notes' in kwargs:
                vals['followup_notes'] = kwargs['followup_notes']
            if 'followup_completed' in kwargs:
                vals['followup_completed'] = kwargs.get('followup_completed') == 'on' or kwargs.get('followup_completed') == 'true'
            
            # Notes
            if 'notes' in kwargs:
                vals['notes'] = kwargs['notes']
            
            # Status update
            if 'status' in kwargs:
                vals['status'] = kwargs['status']
            
            # Incident datetime - convert from datetime-local format (YYYY-MM-DDTHH:MM) to Odoo format (YYYY-MM-DD HH:MM:SS)
            if 'incident_datetime' in kwargs and kwargs['incident_datetime']:
                try:
                    datetime_str = kwargs['incident_datetime'].strip()
                    # Handle datetime-local format: 2026-01-26T07:20 -> 2026-01-26 07:20:00
                    if 'T' in datetime_str:
                        # Replace T with space
                        datetime_str = datetime_str.replace('T', ' ')
                        # Add seconds if not present (datetime-local only sends HH:MM)
                        if datetime_str.count(':') == 1:  # Only HH:MM, add :00
                            datetime_str += ':00'
                    # Odoo expects format: YYYY-MM-DD HH:MM:SS
                    vals['incident_datetime'] = datetime_str
                    _logger.debug('[Mobile Incident Update] Converted incident_datetime: %s -> %s', kwargs['incident_datetime'], datetime_str)
                except Exception as e:
                    _logger.error('[Mobile Incident Update] Error processing incident_datetime "%s": %s', kwargs.get('incident_datetime'), str(e), exc_info=True)
                    # Don't set the value if processing fails - let it keep the existing value
            
            # Log what we're updating
            if vals:
                _logger.info('[Mobile Incident Update] Updating incident %s with %d fields', incident_id, len(vals))
                _logger.debug('[Mobile Incident Update] Update values: %s', vals)
            else:
                _logger.warning('[Mobile Incident Update] No values to update for incident %s', incident_id)
            
            # Update incident
            if vals:
                incident.sudo().write(vals)
                _logger.info('[Mobile Incident Update] Successfully updated incident %s', incident_id)
            else:
                _logger.warning('[Mobile Incident Update] Skipping update - no values provided')
            
            # Handle image uploads
            uploaded_files = request.httprequest.files.getlist('incident_images')
            if uploaded_files:
                attachment_ids = list(incident.photo_ids.ids) if incident.photo_ids else []
                for uploaded_file in uploaded_files:
                    if uploaded_file and uploaded_file.filename:
                        try:
                            file_content = uploaded_file.read()
                            file_base64 = base64.b64encode(file_content)
                            
                            attachment = request.env['ir.attachment'].sudo().create({
                                'name': uploaded_file.filename,
                                'type': 'binary',
                                'datas': file_base64,
                                'res_model': 'incident.report',
                                'res_id': incident.id,
                                'mimetype': uploaded_file.content_type or 'image/jpeg',
                            })
                            attachment_ids.append(attachment.id)
                        except Exception as e:
                            _logger.error("Error uploading file %s: %s", uploaded_file.filename, str(e))
                
                if attachment_ids:
                    incident.sudo().write({
                        'photo_ids': [(6, 0, attachment_ids)]
                    })
            
            return request.redirect(f'/guardpro/mobile/incident/{incident_id}?success=updated')
        except Exception as e:
            _logger.error("[Mobile Incident Update] Incident update error for incident %s: %s", incident_id, str(e), exc_info=True)
            return request.redirect(f'/guardpro/mobile/incident/{incident_id}?error=update_failed')

    @http.route('/guardpro/mobile/tour/checkpoint/<int:checkpoint_id>', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_tour_checkpoint(self, checkpoint_id, latitude=None, longitude=None, notes=None, **kwargs):
        """Record checkpoint visit during tour."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile/tours?error=no_guard')
        
        checkpoint = request.env['checkpoint'].sudo().search([
            ('id', '=', checkpoint_id),
        ], limit=1)
        
        if not checkpoint:
            return request.redirect('/guardpro/mobile/tours?error=checkpoint_not_found')
        
        # Find or create active tour log
        active_tour_log = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', '=', 'in_progress'),
        ], limit=1, order='start_time desc')
        
        if not active_tour_log:
            # Create new tour log
            active_attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1)
            
            if not active_attendance or not active_attendance.site_id:
                return request.redirect('/guardpro/mobile/tours?error=not_checked_in')
            
            # Get an available tour for this site
            available_tour = request.env['security.tour'].sudo().search([
                ('site_id', '=', active_attendance.site_id.id),
                ('status', '=', 'active'),
            ], limit=1)
            
            if not available_tour:
                # Get all active checkpoints for this site
                site_checkpoints = request.env['checkpoint'].sudo().search([
                    ('site_id', '=', active_attendance.site_id.id),
                    ('status', '=', 'active'),
                ])
                
                # Create a default tour if none exists
                available_tour = request.env['security.tour'].sudo().create({
                    'name': f"Tour - {active_attendance.site_id.name}",
                    'code': f"TOUR-{active_attendance.site_id.id}",
                    'site_id': active_attendance.site_id.id,
                    'status': 'active',
                    'checkpoint_ids': [(6, 0, site_checkpoints.ids)],
                })
            
            # Get shift if available
            shift = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),
                ('start_datetime', '<=', datetime.now()),
                ('end_datetime', '>=', datetime.now()),
                ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
            ], limit=1)
            
            # Get expected checkpoints from the tour
            expected_checkpoints = len(available_tour.checkpoint_ids)
            
            active_tour_log = request.env['tour.log'].sudo().create({
                'guard_id': guard.id,
                'site_id': active_attendance.site_id.id,
                'tour_id': available_tour.id,
                'shift_id': shift.id if shift else False,
                'start_time': datetime.now(),
                'status': 'in_progress',
                'expected_checkpoints': expected_checkpoints,
            })
        
        # Record checkpoint scan
        vals = {
            'tour_log_id': active_tour_log.id,
            'checkpoint_id': checkpoint_id,
            'guard_id': guard.id,
            'scan_time': datetime.now(),
            'scan_type': checkpoint.scan_type or 'manual',
            'status': 'verified',
        }
        
        if notes:
            vals['notes'] = notes
        
        if latitude and longitude:
            try:
                vals.update({
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                })
            except (ValueError, TypeError):
                pass
        
        try:
            request.env['checkpoint.scan'].sudo().create(vals)
            return request.redirect('/guardpro/mobile/tours?success=checkpoint_scanned')
        except Exception as e:
            _logger.error("Checkpoint scan error: %s", str(e))
            return request.redirect('/guardpro/mobile/tours?error=scan_failed')

    # ==========================================
    # PWA Manifest and Service Worker
    # ==========================================

    @http.route('/guardpro/mobile/manifest.json', type='http', auth='public')
    def mobile_manifest(self, **kwargs):
        """PWA manifest file."""
        manifest = {
            'name': 'GuardPro Mobile',
            'short_name': 'GuardPro',
            'version': '2.0.0',
            'description': 'Security guard management mobile app',
            'start_url': '/guardpro/mobile',
            'display': 'standalone',
            'orientation': 'any',
            'theme_color': '#1a237e',
            'background_color': '#ffffff',
            'icons': [
                {
                    'src': '/guardpro/static/src/img/icon-192x192.png',
                    'sizes': '192x192',
                    'type': 'image/png'
                },
                {
                    'src': '/guardpro/static/src/img/icon-512x512.png',
                    'sizes': '512x512',
                    'type': 'image/png'
                }
            ],
            'categories': ['business', 'productivity'],
        }
        
        return request.make_response(
            json.dumps(manifest, indent=2),
            headers=[
                ('Content-Type', 'application/manifest+json'),
                ('Cache-Control', 'public, max-age=3600'),
            ]
        )

    @http.route('/guardpro/mobile/profile', type='http', auth='user', website=True)
    def mobile_profile(self, **kwargs):
        """Mobile profile page."""
        _logger.info('[GuardPro Mobile] Accessing profile for user: %s', request.env.user.name)
        try:
            guard = self._get_guard_from_user()
            _logger.info('[GuardPro Mobile] Guard profile found: %s', guard.name if guard else 'None')
            
            if not guard:
                return request.render('guardpro.mobile_no_guard', {
                    'user': request.env.user,
                })
                
            return request.render('guardpro.mobile_profile_template', {
                'guard': guard,
                'user': request.env.user,
            })
        except Exception as e:
            _logger.error('[GuardPro Mobile] Error in mobile_profile: %s', str(e), exc_info=True)
            raise e
    
    @http.route('/guardpro/mobile/site_info', type='http', auth='user', website=True)
    def mobile_site_info(self, **kwargs):
        """Mobile site info page."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
            
        site = guard.current_site_id if guard else None
        
        return request.render('guardpro.mobile_site_info_template', {
            'guard': guard,
            'site': site,
        })

    @http.route('/guardpro/mobile/emergency', type='http', auth='user', website=True)
    def mobile_emergency(self, **kwargs):
        """Mobile emergency procedures page."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
            
        site = guard.current_site_id if guard else None
        
        # Get active emergency procedures for the site
        procedures = []
        if site:
             try:
                 procedures = request.env['emergency.procedure'].sudo().search([
                     ('site_ids', 'in', site.id),
                     ('active', '=', True)
                 ])
                 # Also get procedures with no specific site (global)
                 global_procedures = request.env['emergency.procedure'].sudo().search([
                     ('site_ids', '=', False),
                     ('active', '=', True)
                 ])
                 procedures = procedures | global_procedures
             except Exception:
                 _logger.warning("Could not load emergency procedures")

        return request.render('guardpro.mobile_emergency_template', {
            'guard': guard,
            'site': site,
            'procedures': procedures,
        })

    @http.route('/guardpro/mobile/settings', type='http', auth='user', website=True)
    def mobile_settings(self, **kwargs):
        """Settings screen - User preferences and profile."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get user statistics
        total_shifts = request.env['guard.shift'].sudo().search_count([
            ('guard_id', '=', guard.id),
            ('status', '=', 'completed'),
        ])
        
        total_tasks = request.env['guard.task'].sudo().search_count([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'completed'),
        ])
        
        total_incidents = request.env['incident.report'].sudo().search_count([
            ('guard_id', '=', guard.id),
        ])
        
        total_tours = request.env['tour.log'].sudo().search_count([
            ('guard_id', '=', guard.id),
            ('status', '=', 'completed'),
        ])
        
        return request.render('guardpro.mobile_settings', {
            'guard': guard,
            'user': request.env.user,
            'total_shifts': total_shifts,
            'total_tasks': total_tasks,
            'total_incidents': total_incidents,
            'total_tours': total_tours,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/more', type='http', auth='user', website=True)
    def mobile_more(self, **kwargs):
        """More menu screen - Additional options and features."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        return request.render('guardpro.mobile_more', {
            'guard': guard,
            'user': request.env.user,
        })

    @http.route('/guardpro/mobile/biometric', type='http', auth='user', website=True)
    def mobile_biometric(self, **kwargs):
        """Biometric management screen - View and enroll biometrics."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get guard's biometric templates
        templates = request.env['guard.biometric.template'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='create_date desc')
        
        # Get recent verifications
        recent_verifications = request.env['guard.biometric.verification'].sudo().search([
            ('guard_id', '=', guard.id),
        ], limit=10, order='verification_time desc')
        
        # Group templates by type
        fingerprint_templates = templates.filtered(lambda t: t.biometric_type == 'fingerprint')
        facial_templates = templates.filtered(lambda t: t.biometric_type == 'facial')
        voice_templates = templates.filtered(lambda t: t.biometric_type == 'voice')
        
        return request.render('guardpro.mobile_biometric', {
            'guard': guard,
            'user': request.env.user,
            'templates': templates,
            'fingerprint_templates': fingerprint_templates,
            'facial_templates': facial_templates,
            'voice_templates': voice_templates,
            'recent_verifications': recent_verifications,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/training', type='http', auth='user', website=True)
    def mobile_training(self, **kwargs):
        """Training screen - View courses and certifications."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', {
                'user': request.env.user,
            })
        
        # Get training enrollments
        enrollments = []
        if hasattr(guard, 'training_enrollment_ids') and guard.training_enrollment_ids:
            enrollments = guard.training_enrollment_ids
        elif 'slide.channel.partner' in request.env:
            enrollments = request.env['slide.channel.partner'].sudo().search([
                ('guard_id', '=', guard.id),
            ], order='create_date desc')
        
        return request.render('guardpro.mobile_training', {
            'guard': guard,
            'user': request.env.user,
            'enrollments': enrollments,
        })

    @http.route('/guardpro/mobile/sw.js', type='http', auth='public')
    def mobile_service_worker(self, **kwargs):
        """Minimal service worker for offline support."""
        sw_content = """
// GuardPro Mobile - Minimal Service Worker (Odoo 18)
const CACHE_VERSION = 'v2.0.5';
const CACHE_NAME = 'guardpro-mobile-' + CACHE_VERSION;

// Install event
self.addEventListener('install', (event) => {
    console.log('[SW] Installing...');
    self.skipWaiting();
});

// Activate event
self.addEventListener('activate', (event) => {
    console.log('[SW] Activating...');
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        console.log('[SW] Deleting old cache:', cacheName);
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    return self.clients.claim();
});

// Fetch event - Network first, then cache
self.addEventListener('fetch', (event) => {
    event.respondWith(
        fetch(event.request)
            .then((response) => {
                // Clone and cache good responses
                if (response && response.status === 200) {
                    const responseClone = response.clone();
                    caches.open(CACHE_NAME).then((cache) => {
                        cache.put(event.request, responseClone);
                    });
                }
                return response;
            })
            .catch(() => {
                // Fallback to cache on network error
                return caches.match(event.request).then((response) => {
                    return response || new Response('Offline', { status: 503 });
                });
            })
    );
});
"""
        
        return request.make_response(
            sw_content,
            headers=[
                ('Content-Type', 'application/javascript'),
                ('Service-Worker-Allowed', '/guardpro/'),
                ('Cache-Control', 'no-cache, no-store, must-revalidate'),
            ]
        )

