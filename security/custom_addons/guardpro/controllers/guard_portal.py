# -*- coding: utf-8 -*-
"""GuardPro Portal Controller."""

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal
import logging
import html

_logger = logging.getLogger(__name__)


class GuardPortal(CustomerPortal):
    """Portal controller for guards."""

    @http.route(['/my', '/my/home'], type='http', auth="user", website=True)
    def home(self, **kw):
        """Override default portal home to auto-redirect guards to mobile dashboard."""
        # Check if user is a guard - if so, redirect to mobile dashboard
        if request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/guardpro/mobile')
        
        # For non-guard users, show default portal
        return super(GuardPortal, self).home(**kw)

    def _prepare_portal_layout_values(self):
        """Prepare portal layout values with guard-specific data."""
        values = super()._prepare_portal_layout_values()
        
        try:
            # Get guard profile for current user (using sudo for portal users)
            guard_profile = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if guard_profile:
                # Get guard's active shifts count (using sudo for portal users)
                active_shifts = request.env['guard.shift'].sudo().search_count([
                    ('guard_id', '=', guard_profile.id),
                    ('status', 'in', ['scheduled', 'confirmed', 'in_progress'])
                ])
                
                # Get pending incidents count (using sudo for portal users)
                pending_incidents = request.env['incident.report'].sudo().search_count([
                    ('guard_id', '=', guard_profile.id),
                    ('status', 'in', ['submitted', 'under_review'])
                ])
                
                # Get active tours count for TODAY only (using sudo for portal users)
                from datetime import datetime, timedelta
                import pytz
                
                # Get user's timezone
                tz = pytz.timezone(request.env.user.tz or 'UTC')
                now_utc = pytz.UTC.localize(datetime.utcnow())
                now_tz = now_utc.astimezone(tz)
                
                # Today's date range
                today_start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
                today_end_tz = today_start_tz + timedelta(days=1)
                today_start = today_start_tz.astimezone(pytz.UTC).replace(tzinfo=None)
                today_end = today_end_tz.astimezone(pytz.UTC).replace(tzinfo=None)
                
                active_tours = request.env['tour.log'].sudo().search_count([
                    ('guard_id', '=', guard_profile.id),
                    ('status', '=', 'in_progress'),
                    ('start_time', '>=', today_start),
                    ('start_time', '<', today_end)
                ])
                
                values.update({
                    'guard_profile': guard_profile,
                    'guard_active_shifts_count': active_shifts,
                    'guard_pending_incidents_count': pending_incidents,
                    'guard_active_tours_count': active_tours,
                })
        except Exception as e:
            _logger.warning('Error preparing guard portal layout values: %s', str(e))
            # Don't break portal if there's an error
            values.update({
                'guard_profile': False,
                'guard_active_shifts_count': 0,
                'guard_pending_incidents_count': 0,
                'guard_active_tours_count': 0,
            })
        
        return values

    @http.route(['/my/guardpro'], type='http', auth="user", website=True)
    def guardpro_portal_home(self, **kw):
        """Guard portal home page - accessible only to users with Guard User checkbox."""
        # Check if user has Guard User checkbox ticked (using existing group)
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.render("guardpro.portal_access_denied", {
                'page_name': 'guardpro_access_denied',
                'error_message': _('Access Denied: This portal is only accessible to Guard users. Please contact your administrator to enable Guard User access.')
            })
        
        # Auto-redirect guards to mobile dashboard (all features are available there)
        return request.redirect('/guardpro/mobile')
        
        values = self._prepare_portal_layout_values()
        
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            # User is not a guard, show message
            return request.render("guardpro.portal_not_guard", values)
        
        # Get today's shifts
        from datetime import datetime, timedelta
        import pytz
        
        # Get user's timezone
        tz = pytz.timezone(request.env.user.tz or 'UTC')
        
        # Get today's date in user's timezone
        now_utc = pytz.UTC.localize(datetime.utcnow())
        now_tz = now_utc.astimezone(tz)
        
        # Get start and end of today in user's timezone, then convert to UTC
        today_start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_tz = today_start_tz + timedelta(days=1)
        
        # Convert to UTC for database query
        today_start = today_start_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        today_end = today_end_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        
        # Get today's shifts (using sudo for portal users)
        today_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard_profile.id),
            ('start_datetime', '<', today_end),
            ('end_datetime', '>', today_start)
        ], order='start_datetime asc')
        
        # Convert datetime fields to user's timezone for template display
        # Store formatted datetime strings as temporary attributes (not modifying the record)
        for shift in today_shifts:
            # Always set display attributes (empty string if datetime is None)
            if shift.start_datetime:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.start_datetime)
                shift._display_start_datetime = tz_dt.strftime('%I:%M %p')
                shift._display_start_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_start_datetime = ''
                shift._display_start_datetime_full = ''
            if shift.end_datetime:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.end_datetime)
                shift._display_end_datetime = tz_dt.strftime('%I:%M %p')
                shift._display_end_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_end_datetime = ''
                shift._display_end_datetime_full = ''
            if shift.checkin_time:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.checkin_time)
                shift._display_checkin_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_checkin_time = ''
            if shift.checkout_time:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.checkout_time)
                shift._display_checkout_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_checkout_time = ''
        
        # Get recent incidents (using sudo for portal users)
        recent_incidents = request.env['incident.report'].sudo().search([
            ('guard_id', '=', guard_profile.id)
        ], order='incident_datetime desc', limit=5)
        
        # Get active tours for TODAY only (using sudo for portal users)
        active_tours = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard_profile.id),
            ('status', '=', 'in_progress'),
            ('start_time', '>=', today_start),
            ('start_time', '<', today_end)
        ])
        
        values.update({
            'today_shifts': today_shifts,
            'recent_incidents': recent_incidents,
            'active_tours': active_tours,
            'page_name': 'guardpro_home',
        })
        
        return request.render("guardpro.guard_portal_home", values)

    @http.route(['/my/shifts', '/my/shifts/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_shifts(self, page=1, date_begin=None, date_end=None, sortby=None, **kw):
        """List all shifts for the current guard - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Prepare search domain
        domain = [('guard_id', '=', guard_profile.id)]
        
        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'start_datetime desc'},
            'site': {'label': _('Site'), 'order': 'site_id'},
            'status': {'label': _('Status'), 'order': 'status'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Get shifts (using sudo for portal users)
        shifts = request.env['guard.shift'].sudo().search(domain, order=order)
        
        # Convert datetime fields to user's timezone for template display
        # Store formatted datetime strings as temporary attributes (not modifying the record)
        for shift in shifts:
            # Always set display attributes (empty string if datetime is None)
            if shift.start_datetime:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.start_datetime)
                shift._display_start_datetime = tz_dt.strftime('%I:%M %p')
                shift._display_start_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_start_datetime = ''
                shift._display_start_datetime_full = ''
            if shift.end_datetime:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.end_datetime)
                shift._display_end_datetime = tz_dt.strftime('%I:%M %p')
                shift._display_end_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_end_datetime = ''
                shift._display_end_datetime_full = ''
            if shift.checkin_time:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.checkin_time)
                shift._display_checkin_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_checkin_time = ''
            if shift.checkout_time:
                tz_dt = fields.Datetime.context_timestamp(shift, shift.checkout_time)
                shift._display_checkout_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
            else:
                shift._display_checkout_time = ''
        
        values.update({
            'shifts': shifts,
            'page_name': 'my_shifts',
            'default_url': '/my/shifts',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        
        return request.render("guardpro.portal_my_shifts", values)

    @http.route(['/my/shifts/<int:shift_id>'], type='http', auth="user", website=True)
    def portal_shift_detail(self, shift_id, **kw):
        """Display a specific shift - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Get the shift and verify it belongs to this guard (using sudo for portal users)
        shift = request.env['guard.shift'].sudo().search([
            ('id', '=', shift_id),
            ('guard_id', '=', guard_profile.id)
        ], limit=1)
        
        if not shift:
            return request.redirect('/my/shifts')
        
        # Convert datetime fields to user's timezone for template display
        # Store formatted datetime strings as temporary attributes (not modifying the record)
        # Always set display attributes (empty string if datetime is None)
        if shift.start_datetime:
            tz_dt = fields.Datetime.context_timestamp(shift, shift.start_datetime)
            shift._display_start_datetime = tz_dt.strftime('%I:%M %p')
            shift._display_start_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
        else:
            shift._display_start_datetime = ''
            shift._display_start_datetime_full = ''
        if shift.end_datetime:
            tz_dt = fields.Datetime.context_timestamp(shift, shift.end_datetime)
            shift._display_end_datetime = tz_dt.strftime('%I:%M %p')
            shift._display_end_datetime_full = tz_dt.strftime('%Y-%m-%d %I:%M %p')
        else:
            shift._display_end_datetime = ''
            shift._display_end_datetime_full = ''
        if shift.checkin_time:
            tz_dt = fields.Datetime.context_timestamp(shift, shift.checkin_time)
            shift._display_checkin_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
        else:
            shift._display_checkin_time = ''
        if shift.checkout_time:
            tz_dt = fields.Datetime.context_timestamp(shift, shift.checkout_time)
            shift._display_checkout_time = tz_dt.strftime('%Y-%m-%d %I:%M %p')
        else:
            shift._display_checkout_time = ''
        
        values.update({
            'shift': shift,
            'page_name': 'shift_detail',
        })
        
        return request.render("guardpro.portal_shift_detail", values)

    @http.route(['/my/incidents', '/my/incidents/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_incidents(self, page=1, sortby=None, **kw):
        """List all incidents for the current guard - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Prepare search domain
        domain = [('guard_id', '=', guard_profile.id)]
        
        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'incident_datetime desc'},
            'priority': {'label': _('Priority'), 'order': 'priority desc'},
            'status': {'label': _('Status'), 'order': 'status'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Get incidents (using sudo for portal users)
        incidents = request.env['incident.report'].sudo().search(domain, order=order)
        
        values.update({
            'incidents': incidents,
            'page_name': 'my_incidents',
            'default_url': '/my/incidents',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        
        return request.render("guardpro.portal_my_incidents", values)

    @http.route(['/my/incidents/<int:incident_id>'], type='http', auth="user", website=True)
    def portal_incident_detail(self, incident_id, **kw):
        """Display a specific incident - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Get the incident and verify it belongs to this guard (using sudo for portal users)
        incident = request.env['incident.report'].sudo().search([
            ('id', '=', incident_id),
            ('guard_id', '=', guard_profile.id)
        ], limit=1)
        
        if not incident:
            return request.redirect('/my/incidents')
        
        values.update({
            'incident': incident,
            'page_name': 'incident_detail',
        })
        
        return request.render("guardpro.portal_incident_detail", values)

    @http.route(['/my/tours', '/my/tours/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_tours(self, page=1, sortby=None, **kw):
        """List all tours for the current guard - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Prepare search domain
        domain = [('guard_id', '=', guard_profile.id)]
        
        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'start_time desc'},
            'status': {'label': _('Status'), 'order': 'status'},
            'completion': {'label': _('Completion'), 'order': 'completion_percentage desc'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Get tours (using sudo for portal users)
        tours = request.env['tour.log'].sudo().search(domain, order=order)
        
        values.update({
            'tours': tours,
            'page_name': 'my_tours',
            'default_url': '/my/tours',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        
        return request.render("guardpro.portal_my_tours", values)

    @http.route(['/my/tours/<int:tour_id>'], type='http', auth="user", website=True)
    def portal_tour_detail(self, tour_id, **kw):
        """Display a specific tour - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Get the tour and verify it belongs to this guard (using sudo for portal users)
        tour = request.env['tour.log'].sudo().search([
            ('id', '=', tour_id),
            ('guard_id', '=', guard_profile.id)
        ], limit=1)
        
        if not tour:
            return request.redirect('/my/tours')
        
        values.update({
            'tour': tour,
            'page_name': 'tour_detail',
        })
        
        return request.render("guardpro.portal_tour_detail", values)

    @http.route(['/my/attendance', '/my/attendance/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_attendance(self, page=1, sortby=None, **kw):
        """List all attendance records for the current guard - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Prepare search domain
        domain = [('guard_id', '=', guard_profile.id)]
        
        # Sorting options
        searchbar_sortings = {
            'date': {'label': _('Date'), 'order': 'checkin_time desc'},
            'hours': {'label': _('Hours'), 'order': 'hours_worked desc'},
        }
        
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Get attendance records (using sudo for portal users)
        attendances = request.env['guard.attendance'].sudo().search(domain, order=order)
        
        values.update({
            'attendances': attendances,
            'page_name': 'my_attendance',
            'default_url': '/my/attendance',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
        })
        
        return request.render("guardpro.portal_my_attendance", values)

    @http.route(['/my/incidents/new'], type='http', auth="user", website=True)
    def portal_new_incident(self, **kw):
        """Create new incident - accessible only to internal guard users."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Get incident categories for the form (using sudo for portal users)
        categories = request.env['incident.category'].sudo().search([])
        
        values.update({
            'categories': categories,
            'page_name': 'new_incident',
        })
        
        return request.render("guardpro.portal_new_incident", values)

    @http.route(['/my/incidents/create'], type='http', auth="user", website=True, methods=['POST'])
    def portal_create_incident(self, **kw):
        """Create incident from portal form."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my/guardpro')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        try:
            # Create incident
            incident_data = {
                'guard_id': guard_profile.id,
                'incident_datetime': kw.get('incident_datetime'),
                'category_id': int(kw.get('category_id', 0)) if kw.get('category_id') else False,
                'description': kw.get('description', ''),
                'location': kw.get('location', ''),
                'priority': kw.get('priority', 'medium'),
                'status': 'submitted',
            }
            
            incident = request.env['incident.report'].sudo().create(incident_data)
            
            return request.redirect('/my/incidents/%s' % incident.id)
            
        except Exception as e:
            _logger.error('Error creating incident: %s', str(e))
            values.update({
                'error_message': _('Error creating incident. Please try again.'),
                'categories': request.env['incident.category'].sudo().search([]),
            })
            return request.render("guardpro.portal_new_incident", values)

    @http.route(['/my/training'], type='http', auth="user", website=True)
    def portal_my_training(self, **kw):
        """Guard training portal page."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my')
        
        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')
        
        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)
        
        # Get mandatory courses (using sudo for portal users)
        mandatory_courses = request.env['slide.channel'].sudo().search([
            ('is_guard_training', '=', True),
            ('is_mandatory_for_guards', '=', True)
        ])
        
        # Get active enrollments (courses in progress)
        active_enrollments = request.env['slide.channel.partner'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id),
            ('member_status', 'in', ['joined', 'ongoing'])
        ])
        
        # Get completed enrollments
        completed_enrollments = request.env['slide.channel.partner'].sudo().search([
            ('partner_id', '=', request.env.user.partner_id.id),
            ('member_status', '=', 'completed')
        ])
        
        # Get available courses (not yet enrolled)
        enrolled_course_ids = (active_enrollments + completed_enrollments).mapped('channel_id').ids
        available_courses = request.env['slide.channel'].sudo().search([
            ('is_guard_training', '=', True),
            ('id', 'not in', enrolled_course_ids)
        ])
        
        values.update({
            'guard_profile': guard_profile,
            'mandatory_courses': mandatory_courses,
            'active_enrollments': active_enrollments,
            'completed_enrollments': completed_enrollments,
            'available_courses': available_courses,
            'page_name': 'training',
        })
        
        return request.render("guardpro.portal_my_training", values)

    @http.route(['/mobile/training'], type='http', auth="user", website=True)
    def mobile_training_dashboard(self, **kw):
        """Mobile training dashboard page."""
        # Check if user is a guard
        if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
            return request.redirect('/my')

        values = self._prepare_portal_layout_values()
        guard_profile = values.get('guard_profile')

        if not guard_profile:
            return request.render("guardpro.portal_not_guard", values)

        # Get training data via API call (simulate what the API would return)
        try:
            # This would normally call the API, but for template rendering we'll prepare the data directly
            courses = request.env['slide.channel'].sudo().search([
                ('is_guard_training', '=', True)
            ])

            course_data = []
            mandatory_completed = 0
            mandatory_total = 0

            for course in courses:
                enrollment = request.env['slide.channel.partner'].sudo().search([
                    ('channel_id', '=', course.id),
                    ('partner_id', '=', request.env.user.partner_id.id)
                ], limit=1)

                is_mandatory = course.is_mandatory_for_guards
                if course.required_for_sites and guard_profile.current_site_id:
                    is_mandatory = guard_profile.current_site_id in course.required_for_sites

                if is_mandatory:
                    mandatory_total += 1
                    if enrollment and enrollment.member_status == 'completed' and enrollment.passed_course:
                        mandatory_completed += 1

                course_data.append({
                    'id': course.id,
                    'name': course.name,
                    'description': course.description_short or course.description[:100] + '...',
                    'category': course.training_category,
                    'duration': course.total_time,
                    'mandatory': is_mandatory,
                    'enrolled': bool(enrollment),
                    'status': enrollment.member_status if enrollment else 'not_enrolled',
                    'progress': enrollment.completion if enrollment else 0,
                    'passed': enrollment.passed_course if enrollment else False,
                    'certification_status': enrollment.certification_status if enrollment else 'none',
                })

            values.update({
                'guard_profile': guard_profile,
                'courses': course_data,
                'mandatory_completed': mandatory_completed,
                'mandatory_total': mandatory_total,
                'page_name': 'mobile_training',
            })

        except Exception as e:
            values.update({
                'courses': [],
                'mandatory_completed': 0,
                'mandatory_total': 0,
                'error': str(e),
            })

        return request.render("guardpro.mobile_training_dashboard", values)

    @http.route(['/mobile/training/course/<int:course_id>'], type='http', auth="user", website=True)
    def mobile_course_view(self, course_id, **kw):
        """Mobile course view page."""
        values = {}
        guard_profile = None
        try:
            _logger.info('[Mobile Course View] Route accessed: course_id=%s, user=%s', course_id, request.env.user.login)
            # Check if user is a guard
            if not request.env.user.has_group('guardpro.group_guardpro_guard_portal'):
                _logger.warning('[Mobile Course View] User %s is not a guard, redirecting', request.env.user.login)
                return request.redirect('/my')

            values = self._prepare_portal_layout_values()
            guard_profile = values.get('guard_profile')

            if not guard_profile:
                _logger.warning('[Mobile Course View] No guard profile found for user %s', request.env.user.login)
                return request.render("guardpro.portal_not_guard", values)
            
            # Ensure guard is set for mobile_base template
            values['guard'] = guard_profile if guard_profile else False
        except Exception as init_error:
            _logger.error('[Mobile Course View] Error in initialization: %s', str(init_error), exc_info=True)
            import traceback
            _logger.error('[Mobile Course View] Init traceback: %s', traceback.format_exc())
            # Try to get basic values for template, even if _prepare_portal_layout_values failed
            try:
                if not values:
                    values = super()._prepare_portal_layout_values()
                # Try to get guard profile directly
                if not guard_profile:
                    guard_profile = request.env['guard.profile'].sudo().search([
                        ('user_id', '=', request.env.user.id)
                    ], limit=1)
                values['guard'] = guard_profile if guard_profile else False
                values['guard_profile'] = guard_profile
            except Exception:
                # If even that fails, set minimal values
                values = {
                    'guard': False,
                    'guard_profile': None,
                }
            # Return error page with proper values
            values['error'] = 'Error accessing course: %s' % str(init_error)
            return request.render("guardpro.mobile_training_dashboard", values)

        # Get course details
        try:
            course = request.env['slide.channel'].sudo().browse(course_id)
            if not course.exists():
                _logger.warning('[Mobile Course View] Course %s does not exist', course_id)
                return request.render("guardpro.mobile_training_dashboard", {
                    **values,
                    'error': 'Course not found'
                })
            
            # Check if it's a guard training course (use getattr to avoid AttributeError)
            is_guard_training = getattr(course, 'is_guard_training', False)
            if not is_guard_training:
                _logger.warning('[Mobile Course View] Course %s is not a guard training course', course_id)
                return request.render("guardpro.mobile_training_dashboard", {
                    **values,
                    'error': 'Course not found'
                })

            # Get enrollment
            enrollment = request.env['slide.channel.partner'].sudo().search([
                ('channel_id', '=', course_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            # Check if course is mandatory for this guard
            is_mandatory = getattr(course, 'is_mandatory_for_guards', False)
            required_for_sites = getattr(course, 'required_for_sites', False)
            if required_for_sites and guard_profile and guard_profile.current_site_id:
                try:
                    # Check if guard's current site is in required sites
                    if hasattr(required_for_sites, '__contains__'):
                        is_mandatory = guard_profile.current_site_id in required_for_sites
                except (TypeError, AttributeError):
                    # If comparison fails, keep original is_mandatory value
                    pass

            # Create course data dictionary with all required fields
            # Use getattr with defaults to avoid AttributeError
            course_name = getattr(course, 'name', '') or ''
            course_description = getattr(course, 'description', '') or ''
            # Convert Markup to string if needed, and handle None/empty cases
            if course_description:
                try:
                    # Convert Markup to string if it's a Markup object
                    if hasattr(course_description, '__html__'):
                        course_description = str(course_description)
                    elif not isinstance(course_description, str):
                        course_description = str(course_description) if course_description else ''
                    # Truncate if too long
                    if course_description and len(course_description) > 500:
                        course_description = course_description[:500] + '...'
                except (TypeError, AttributeError) as desc_error:
                    _logger.warning('[Mobile Course View] Error processing description: %s', str(desc_error))
                    course_description = ''
            else:
                course_description = ''
            
            course_data = {
                'id': course.id,
                'name': course_name,
                'description': course_description,
                'category': getattr(course, 'training_category', '') or '',
                'duration': getattr(course, 'total_time', 0) or 0,
                'mandatory': is_mandatory,
                'passing_score': getattr(course, 'minimum_passing_score', 0) or 0,
                'certification_validity': getattr(course, 'certification_validity_months', 0) or 0,
                'enrolled': bool(enrollment),
                'status': getattr(enrollment, 'member_status', 'not_enrolled') if enrollment else 'not_enrolled',
                'progress': getattr(enrollment, 'completion', 0) if enrollment else 0,
                'passed': getattr(enrollment, 'passed_course', False) if enrollment else False,
                'certification_status': getattr(enrollment, 'certification_status', 'none') if enrollment else 'none',
            }
            
            # Also pass the course recordset for direct access if needed
            course_recordset = course

            # Get slides - handle case where slide_ids might not exist
            try:
                slides = course.slide_ids
                if slides:
                    slides = slides.sorted('sequence')
                else:
                    slides = request.env['slide.slide']
            except (AttributeError, Exception) as slide_error:
                _logger.warning('[Mobile Course View] Error getting slides: %s', str(slide_error))
                slides = request.env['slide.slide']
            
            slide_data = []            for slide in slides:
                # Check completion status
                slide_partner = request.env['slide.slide.partner'].sudo().search([
                    ('slide_id', '=', slide.id),
                    ('partner_id', '=', request.env.user.partner_id.id)
                ], limit=1)

                slide_category_raw = getattr(slide, 'slide_category', None) or getattr(slide, 'slide_type', '') or ''
                # Fallback category detection for Odoo 19 where fields may differ
                try:
                    has_quiz = bool(getattr(slide, 'question_ids', False)) and len(slide.question_ids) > 0
                except Exception:
                    has_quiz = False
                if not slide_category_raw:
                    if has_quiz:
                        slide_category = 'quiz'
                    elif getattr(slide, 'video_url', False) or getattr(slide, 'video_source', False):
                        slide_category = 'video'
                    elif getattr(slide, 'document_url', False) or getattr(slide, 'document_binary', False) or getattr(slide, 'datas', False):
                        slide_category = 'document'
                    else:
                        slide_category = 'article'
                else:
                    slide_category = slide_category_raw or 'article'
                    if slide_category == 'quiz' and not has_quiz:
                        slide_category = 'article'
                # Get html_content safely, converting Markup to string if needed and unescaping HTML entities
                html_content = ''
                if slide_category in ['article', 'infographic']:
                    html_content_raw = getattr(slide, 'html_content', '') or ''
                    if html_content_raw:
                        try:
                            # Convert Markup to string if it's a Markup object
                            if hasattr(html_content_raw, '__html__'):
                                html_content = str(html_content_raw)
                            elif isinstance(html_content_raw, str):
                                html_content = html_content_raw
                            else:
                                html_content = str(html_content_raw) if html_content_raw else ''
                            # Unescape HTML entities so they render properly
                            if html_content:
                                html_content = html.unescape(html_content)
                        except (TypeError, AttributeError):
                            html_content = ''
                
                # Get completion_time and ensure it's a number (float)
                completion_time_raw = getattr(slide, 'completion_time', 0) or 0
                try:
                    completion_time = float(completion_time_raw) if completion_time_raw else 0.0
                except (ValueError, TypeError):
                    completion_time = 0.0
                
                slide_data.append({
                    'id': slide.id,
                    'name': getattr(slide, 'name', '') or '',
                    'category': slide_category,
                    'sequence': getattr(slide, 'sequence', 0) or 0,
                    'completed': getattr(slide_partner, 'completed', False) if slide_partner else False,
                    'completion_time': completion_time,
                    'html_content': html_content,
                })

            # Ensure course_data is a proper dictionary
            if not isinstance(course_data, dict):
                _logger.warning('[Mobile Course View] course_data is not a dict: %s', type(course_data))
                course_data = {}
            
            # Extract dictionary values as individual variables for template access
            # QWeb templates have issues accessing dictionary values with dot notation
            # Ensure course_obj is set even if course doesn't exist
            # Always set course_obj to the course recordset (even if empty) for template
            if not course_recordset or not course_recordset.exists():
                course_obj_final = None
            else:
                course_obj_final = course_recordset
            
            # Ensure guard variable is set for mobile_base template
            guard_for_template = guard_profile if guard_profile else False
            
            # Ensure all required variables are set with safe defaults
            course_id_val = course_data.get('id', 0) or 0
            course_name_val = course_data.get('name', '') or 'Untitled Course'
            course_description_val = course_data.get('description', '') or ''
            course_category_val = course_data.get('category', '') or ''
            course_duration_val = course_data.get('duration', 0) or 0
            course_mandatory_val = course_data.get('mandatory', False)
            course_passing_score_val = course_data.get('passing_score', 0) or 0
            course_certification_validity_val = course_data.get('certification_validity', 0) or 0
            course_enrolled_val = course_data.get('enrolled', False)
            course_status_val = course_data.get('status', 'not_enrolled') or 'not_enrolled'
            course_progress_val = course_data.get('progress', 0) or 0
            course_passed_val = course_data.get('passed', False)
            course_cert_status_val = course_data.get('certification_status', 'none') or 'none'
            
            values.update({
                'guard_profile': guard_profile,
                'guard': guard_for_template,  # mobile_base template expects 'guard' variable
                'course': course_data,
                'course_obj': course_obj_final,  # Recordset for direct attribute access (can be None)
                'course_id': course_id_val,
                'course_name': course_name_val,
                'course_description': course_description_val,
                'course_category': course_category_val,
                'course_duration': course_duration_val,
                'course_mandatory': course_mandatory_val,
                'course_passing_score': course_passing_score_val,
                'course_certification_validity': course_certification_validity_val,
                'course_enrolled': course_enrolled_val,
                'course_status': course_status_val,
                'course_progress': course_progress_val,
                'course_passed': course_passed_val,
                'course_cert_status': course_cert_status_val,
                'slides': slide_data or [],
                'page_name': 'mobile_course_view',
            })

        except Exception as e:
            _logger.error('[Mobile Course View] Error loading course %s: %s', course_id, str(e), exc_info=True)
            import traceback
            _logger.error('[Mobile Course View] Full traceback: %s', traceback.format_exc())
            # Ensure guard is set even on error (use False if guard_profile is None)
            guard_for_template = guard_profile if guard_profile else False
            
            values.update({
                'guard': guard_for_template,  # Ensure guard is set even on error
                'course': None,
                'course_obj': None,
                'course_name': 'Error',
                'course_description': '',
                'course_progress': 0,
                'course_mandatory': False,
                'course_status': 'error',
                'course_passed': False,
                'course_cert_status': 'none',
                'slides': [],
                'error': str(e),
            })
            # Still try to render the template with error info
            try:
                return request.render("guardpro.mobile_course_view", values)
            except Exception as render_error:
                _logger.error('[Mobile Course View] Error rendering template (from exception handler): %s', str(render_error), exc_info=True)
                import traceback
                _logger.error('[Mobile Course View] Render traceback: %s', traceback.format_exc())
                # Fallback to training dashboard
                try:
                    return request.render("guardpro.mobile_training_dashboard", {
                        **values,
                        'error': 'Error loading course: %s' % str(e)
                    })
                except Exception as fallback_error:
                    _logger.error('[Mobile Course View] Fallback also failed: %s', str(fallback_error))
                    # Last resort - return a simple error page
                    return "<h1>Error Loading Course</h1><p>%s</p><a href='/mobile/training'>Back to Training</a>" % str(e)

        # Render the template (if no exception occurred above)
        _logger.info('[Mobile Course View] Attempting to render template with values: course_obj=%s, course_name=%s', 
                    course_recordset if 'course_recordset' in locals() else None, 
                    course_name_val if 'course_name_val' in locals() else 'N/A')
        try:
            return request.render("guardpro.mobile_course_view", values)
        except Exception as render_error:
            _logger.error('[Mobile Course View] Error rendering template: %s', str(render_error), exc_info=True)
            import traceback
            _logger.error('[Mobile Course View] Render traceback: %s', traceback.format_exc())
            # Try a simpler fallback - just return error message
            try:
                return request.render("guardpro.mobile_training_dashboard", {
                    **values,
                    'error': 'Error rendering course view: %s' % str(render_error)
                })
            except Exception as fallback_error:
                _logger.error('[Mobile Course View] Fallback also failed: %s', str(fallback_error))
                # Last resort - return a simple error page
                return "<h1>Error Loading Course</h1><p>%s</p><a href='/mobile/training'>Back to Training</a>" % str(render_error)