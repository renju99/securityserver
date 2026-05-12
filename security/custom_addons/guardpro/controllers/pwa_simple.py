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
from odoo.exceptions import UserError, AccessError
from odoo.tools import html2plaintext
from datetime import datetime, timedelta
from ..common.video_optimizer import VideoOptimizer
from ..common.image_optimizer import ImageOptimizer

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

    def _mobile_safe_next_url(self, raw_next, default='/guardpro/mobile/tasks'):
        """POST redirect target: only paths under /guardpro/mobile (avoid open redirects)."""
        if not raw_next:
            return default
        url = str(raw_next).strip()
        if not url.startswith('/guardpro/mobile') or '\n' in url or '\r' in url:
            return default
        return url

    def _redirect_mobile_flash(self, raw_next, default, flash_key, flash_value):
        """302 to next with one query param (e.g. success=task_started)."""
        base = self._mobile_safe_next_url(raw_next, default=default)
        sep = '&' if '?' in base else '?'
        return request.redirect(f'{base}{sep}{flash_key}={flash_value}')

    def _resolve_guard_operation_site_id(self, guard):
        """Site for mobile guard actions: active attendance, then latest shift, then user's sites."""
        if not guard:
            return None
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        if active_attendance and active_attendance.site_id:
            return active_attendance.site_id.id
        latest_shift = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
        ], limit=1, order='start_datetime desc')
        if latest_shift and latest_shift.site_id:
            return latest_shift.site_id.id
        user_sites = guard.user_id.site_ids
        if user_sites:
            return user_sites[0].id
        return None

    def _mobile_no_guard_render_vals(self):
        """Context for the no-guard profile screen (includes supervisor compliance entry)."""
        user = request.env.user
        return {
            'user': user,
            'show_compliance_audits': self._user_can_access_mobile_compliance(user),
        }

    def _compliance_user_is_assigned_auditor(self, audit, user):
        """True if user is lead auditor or on the audit team."""
        if not audit or not user:
            return False
        if audit.auditor_id and audit.auditor_id.id == user.id:
            return True
        return user.id in audit.auditor_team_ids.ids

    def _user_can_access_mobile_compliance(self, user):
        """Compliance mobile UI/API: GuardPro Supervisor / Manager / Admin (not guard-only portal)."""
        if not user or user._is_public():
            return False
        return (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        )

    def _compliance_user_can_write_audit(self, audit, user):
        """Whether user may start, edit checklist, or complete this audit (open states only)."""
        if not audit or not user or audit.state not in ('draft', 'in_progress', 'requires_action'):
            return False
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        if self._compliance_user_is_assigned_auditor(audit, user):
            return True
        if audit.site_id and audit.site_id.id in user.site_ids.ids:
            if (
                user.has_group('guardpro.group_guardpro_supervisor')
                or user.has_group('guardpro.group_guardpro_manager')
                or user.has_group('guardpro.group_guardpro_admin')
            ):
                return True
        return False

    def _compliance_open_audits_domain_staff(self):
        """Open audits; record rules scope to the user's allowed sites / assignments."""
        return [('state', 'in', ['draft', 'in_progress', 'requires_action'])]

    def _compliance_audit_type_label(self, audit_type):
        labels = {
            'site': 'Site Audit',
            'guard': 'Guard Performance',
            'equipment': 'Equipment',
            'training': 'Training Compliance',
            'safety': 'Safety',
            'security': 'Security Procedures',
            'operational': 'Operational Compliance',
            'regulatory': 'Regulatory Compliance',
            'quality': 'Quality Assurance',
        }
        return labels.get(audit_type or '', audit_type or '')

    def _normalize_signature_data(self, value):
        """Normalize data URL/base64 signature input for Binary fields."""
        if not value:
            return False
        if isinstance(value, bytes):
            value = value.decode('utf-8', errors='ignore')
        value = value.strip()
        if not value:
            return False
        if ',' in value and value.startswith('data:image'):
            return value.split(',', 1)[1]
        return value

    def _selection_from_yes_no(self, value):
        """Convert common yes/no form values to selection keys."""
        if not value:
            return False
        val = str(value).strip().lower()
        if val in ('yes', 'y', 'true', '1', 'on'):
            return 'yes'
        if val in ('no', 'n', 'false', '0', 'off'):
            return 'no'
        return False

    def _is_video_upload(self, uploaded_file):
        """Detect if uploaded file is a video based on mime or extension."""
        content_type = (uploaded_file.content_type or '').lower()
        if content_type.startswith('video/'):
            return True
        filename = (uploaded_file.filename or '').lower()
        return filename.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'))

    def _create_incident_media_attachment(self, incident, uploaded_file):
        """Create a media attachment for incident with video compression."""
        file_content = uploaded_file.read()
        is_video = self._is_video_upload(uploaded_file)
        mimetype = (uploaded_file.content_type or '').lower()

        if is_video:
            datas, compressed = VideoOptimizer.optimize_video(
                file_content,
                filename=uploaded_file.filename,
            )
            if compressed:
                mimetype = 'video/mp4'
            elif not mimetype:
                mimetype = 'video/mp4'
        else:
            datas = base64.b64encode(file_content)
            if not mimetype:
                mimetype = 'image/jpeg'

        return request.env['ir.attachment'].sudo().create({
            'name': uploaded_file.filename,
            'type': 'binary',
            'datas': datas,
            'res_model': 'incident.report',
            'res_id': incident.id,
            'mimetype': mimetype,
        }), is_video

    @http.route('/guardpro/mobile', type='http', auth='user', website=True)
    def mobile_dashboard(self, **kwargs):
        """Main mobile dashboard using Odoo website framework."""
        _logger.info('[GuardPro Mobile] Accessed by user: %s (ID: %s)', request.env.user.name, request.env.user.id)
        
        guard = self._get_guard_from_user()
        
        if not guard:
            _logger.warning('[Guard Pro Mobile] No guard profile found for user: %s', request.env.user.name)
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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

        user = request.env.user
        show_compliance_audits = self._user_can_access_mobile_compliance(user)
        compliance_open_count = 0
        if show_compliance_audits:
            compliance_open_count = request.env['compliance.audit'].search_count(
                self._compliance_open_audits_domain_staff()
            )
        
        return request.render('guardpro.mobile_dashboard', {
            'guard': guard,
            'user': user,
            'shifts_today': shifts_today,
            'active_tasks': active_tasks,
            'is_checked_in': bool(active_attendance),
            'active_attendance': active_attendance,
            'recent_incidents': recent_incidents,
            'show_compliance_audits': show_compliance_audits,
            'compliance_open_count': compliance_open_count,
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

    @http.route('/guardpro/mobile/visitors/register', type='http', auth='user', website=True, methods=['GET'])
    def mobile_visitor_register(self, **kwargs):
        """Mobile PWA: register a visitor (pre-registered) with optional Emirates ID camera OCR."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        site_id = self._resolve_guard_operation_site_id(guard)
        site_name = ''
        if site_id:
            site = request.env['client.site'].sudo().browse(site_id)
            if site.exists():
                site_name = site.name
        return request.render('guardpro.mobile_visitor_register', {
            'guard': guard,
            'user': request.env.user,
            'resolved_site_id': site_id,
            'resolved_site_name': site_name,
        })

    @http.route('/guardpro/mobile/visitors/register', type='http', auth='user', methods=['POST'], website=True, csrf=True)
    def mobile_visitor_register_submit(self, **kwargs):
        """Create visitor.management from mobile form."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile/visitors/register?error=no_guard')
        post = request.httprequest.form
        name = (post.get('name') or '').strip()
        host_name = (post.get('host_name') or '').strip()
        visit_purpose = (post.get('visit_purpose') or '').strip()
        if not name or not host_name or not visit_purpose:
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_missing_fields')
        site_id = self._resolve_guard_operation_site_id(guard)
        if not site_id:
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_no_site')

        def _strip_or_false(key):
            v = post.get(key)
            if v is None:
                return False
            s = str(v).strip()
            return s if s else False

        vals = {
            'name': name,
            'visitor_type': _strip_or_false('visitor_type') or 'visitor',
            'id_type': _strip_or_false('id_type') or 'emirates_id',
            'visit_date': _strip_or_false('visit_date') or fields.Date.today(),
            'host_name': host_name,
            'visit_purpose': visit_purpose,
            'site_id': site_id,
        }
        optional_char = [
            'id_number', 'nationality', 'occupation', 'employer_name', 'issuing_place',
            'mobile_number', 'email', 'company',
            'purpose_details', 'host_phone', 'host_email', 'vehicle_number',
        ]
        for key in optional_char:
            v = _strip_or_false(key)
            if v:
                vals[key] = v
        for key in ('date_of_birth', 'id_expiry_date', 'id_issue_date'):
            v = _strip_or_false(key)
            if v:
                vals[key] = v
        gender = _strip_or_false('gender')
        if gender in ('male', 'female'):
            vals['gender'] = gender
        id_photo = post.get('id_photo')
        if id_photo and str(id_photo).strip():
            vals['id_photo'] = str(id_photo).strip()

        Visitor = request.env['visitor.management']
        try:
            Visitor.create(vals)
        except AccessError:
            _logger.warning(
                'Mobile visitor register: access denied for user %s',
                request.env.user.id,
            )
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_no_access')
        except Exception as e:
            _logger.exception('Mobile visitor register failed: %s', str(e))
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_failed')
        return request.redirect('/guardpro/mobile/visitors/register?success=visitor_registered')

    @http.route('/guardpro/mobile/task/start/<int:task_id>', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_task_start(self, task_id, **kwargs):
        """Start a task - Standard action."""
        post = request.httprequest.form
        next_raw = post.get('next')
        default_next = '/guardpro/mobile/tasks'

        guard = self._get_guard_from_user()

        if not guard:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'no_guard')

        task = request.env['guard.task'].sudo().search([
            ('id', '=', task_id),
            ('assigned_to', '=', guard.id),
        ], limit=1)

        if not task:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_not_found')

        if task.state not in ['draft', 'assigned']:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_cannot_start')

        try:
            task.action_start()
            return self._redirect_mobile_flash(next_raw, default_next, 'success', 'task_started')
        except Exception as e:
            _logger.error("Task start error: %s", str(e))
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_start_failed')

    @http.route('/guardpro/mobile/task/complete/<int:task_id>', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_task_complete(self, task_id, notes=None, **kwargs):
        """Complete a task - Standard action."""
        post = request.httprequest.form
        next_raw = post.get('next')
        default_next = '/guardpro/mobile/tasks'

        guard = self._get_guard_from_user()

        if not guard:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'no_guard')

        task = request.env['guard.task'].sudo().search([
            ('id', '=', task_id),
            ('assigned_to', '=', guard.id),
        ], limit=1)

        if not task:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_not_found')

        if notes:
            task.write({'completion_notes': notes})

        try:
            task.action_complete()
            return self._redirect_mobile_flash(next_raw, default_next, 'success', 'task_completed')
        except UserError as e:
            _logger.info("Task complete validation: %s", str(e))
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_checklist_incomplete')
        except Exception as e:
            _logger.error("Task complete error: %s", str(e))
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_complete_failed')

    @http.route(
        '/guardpro/mobile/task/checklist/<int:checklist_id>/toggle',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True,
        website=True,
    )
    def mobile_task_checklist_toggle(self, checklist_id, **kwargs):
        """Toggle a checklist line from mobile tour/task cards (mandatory before complete)."""
        post = request.httprequest.form
        next_raw = post.get('next')
        default_next = '/guardpro/mobile/tasks'

        guard = self._get_guard_from_user()
        if not guard:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'no_guard')

        item = request.env['guard.task.checklist'].sudo().browse(checklist_id)
        if not item.exists():
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'checklist_item_not_found')

        task = item.task_id
        if not task or task.assigned_to.id != guard.id:
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'not_authorized')

        if task.state not in ('draft', 'assigned', 'in_progress'):
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'task_not_editable')

        try:
            item.toggle_completed()
        except Exception as e:
            _logger.exception('Mobile checklist toggle failed: %s', e)
            return self._redirect_mobile_flash(next_raw, default_next, 'error', 'checklist_toggle_failed')

        return self._redirect_mobile_flash(next_raw, default_next, 'success', 'checklist_toggled')

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
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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
            'format_datetime_tz': self._format_datetime_tz,
            'html2plaintext': html2plaintext,
        })

    @http.route('/guardpro/mobile/incidents', type='http', auth='user', website=True)
    def mobile_incidents(self, **kwargs):
        """Incidents screen - View and report incidents."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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

        # Category-specific fields (statement/found item/return form)
        category_specific_fields = {
            'statement_person_name': kwargs.get('statement_person_name'),
            'statement_person_mobile': kwargs.get('statement_person_mobile'),
            'statement_person_email': kwargs.get('statement_person_email'),
            'statement_person_nationality': kwargs.get('statement_person_nationality'),
            'statement_person_gender': kwargs.get('statement_person_gender'),
            'statement_person_eid_number': kwargs.get('statement_person_eid_number'),
            'statement_person_company': kwargs.get('statement_person_company'),
            'statement_person_department': kwargs.get('statement_person_department'),
            'statement_person_designation': kwargs.get('statement_person_designation'),
            'statement_text': kwargs.get('statement_text'),
            'found_item_time': kwargs.get('found_item_time'),
            'found_person_name': kwargs.get('found_person_name'),
            'found_person_home_address': kwargs.get('found_person_home_address'),
            'found_person_mobile': kwargs.get('found_person_mobile'),
            'found_person_email': kwargs.get('found_person_email'),
            'found_item_category': kwargs.get('found_item_category'),
            'found_item_description': kwargs.get('found_item_description'),
            'found_item_security_name': kwargs.get('found_item_security_name'),
            'found_item_security_designation': kwargs.get('found_item_security_designation'),
            'return_recipient_name': kwargs.get('return_recipient_name'),
            'return_recipient_home_address': kwargs.get('return_recipient_home_address'),
            'return_recipient_mobile': kwargs.get('return_recipient_mobile'),
            'return_recipient_email': kwargs.get('return_recipient_email'),
            'return_item_description': kwargs.get('return_item_description'),
            'return_item_category': kwargs.get('return_item_category'),
            'return_security_name': kwargs.get('return_security_name'),
            'return_security_designation': kwargs.get('return_security_designation'),
        }
        for field_name, field_value in category_specific_fields.items():
            if field_value:
                vals[field_name] = field_value

        # Date fields
        if kwargs.get('statement_person_eid_expiry'):
            vals['statement_person_eid_expiry'] = kwargs.get('statement_person_eid_expiry')
        if kwargs.get('found_item_date'):
            vals['found_item_date'] = kwargs.get('found_item_date')

        # Selection fields
        if kwargs.get('found_item_inspected'):
            vals['found_item_inspected'] = self._selection_from_yes_no(kwargs.get('found_item_inspected'))
        if kwargs.get('found_item_supervisor_informed'):
            vals['found_item_supervisor_informed'] = self._selection_from_yes_no(kwargs.get('found_item_supervisor_informed'))
        if kwargs.get('found_item_handover'):
            vals['found_item_handover'] = self._selection_from_yes_no(kwargs.get('found_item_handover'))

        # Signature fields
        statement_person_sig = self._normalize_signature_data(kwargs.get('statement_person_signature'))
        if statement_person_sig:
            vals['statement_person_signature'] = statement_person_sig
        security_officer_sig = self._normalize_signature_data(kwargs.get('security_officer_signature'))
        if security_officer_sig:
            vals['security_officer_signature'] = security_officer_sig
        found_person_sig = self._normalize_signature_data(kwargs.get('found_item_person_signature'))
        if found_person_sig:
            vals['found_item_person_signature'] = found_person_sig
        return_recipient_sig = self._normalize_signature_data(kwargs.get('return_recipient_signature'))
        if return_recipient_sig:
            vals['return_recipient_signature'] = return_recipient_sig
        
        try:
            # Create the incident report
            incident = request.env['incident.report'].sudo().create(vals)
            
            # Handle image uploads
            uploaded_files = request.httprequest.files.getlist('incident_images')
            uploaded_files += request.httprequest.files.getlist('incident_videos')
            if uploaded_files:
                photo_attachment_ids = []
                video_attachment_ids = []
                for uploaded_file in uploaded_files:
                    if uploaded_file and uploaded_file.filename:
                        try:
                            attachment, is_video = self._create_incident_media_attachment(
                                incident, uploaded_file
                            )
                            if is_video:
                                video_attachment_ids.append(attachment.id)
                            else:
                                photo_attachment_ids.append(attachment.id)
                            _logger.info("Created attachment %s for incident %s", 
                                       uploaded_file.filename, incident.name)
                        except Exception as e:
                            _logger.error("Error uploading file %s: %s", 
                                        uploaded_file.filename, str(e))
                
                update_vals = {}
                if photo_attachment_ids:
                    update_vals['photo_ids'] = [(6, 0, photo_attachment_ids)]
                if video_attachment_ids:
                    update_vals['video_ids'] = [(6, 0, video_attachment_ids)]
                if update_vals:
                    incident.sudo().write(update_vals)
            
            return request.redirect('/guardpro/mobile/incidents?success=incident_created')
        except Exception as e:
            _logger.error("Incident creation error: %s", str(e))
            return request.redirect('/guardpro/mobile/incidents?error=creation_failed')

    @http.route('/guardpro/mobile/incident/<int:incident_id>', type='http', auth='user', website=True)
    def mobile_incident_detail(self, incident_id, **kwargs):
        """View and edit incident details."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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

            # Category-specific fields
            category_specific_fields = [
                'statement_person_name',
                'statement_person_mobile',
                'statement_person_email',
                'statement_person_nationality',
                'statement_person_gender',
                'statement_person_eid_number',
                'statement_person_company',
                'statement_person_department',
                'statement_person_designation',
                'statement_text',
                'found_item_time',
                'found_person_name',
                'found_person_home_address',
                'found_person_mobile',
                'found_person_email',
                'found_item_category',
                'found_item_description',
                'found_item_security_name',
                'found_item_security_designation',
                'return_recipient_name',
                'return_recipient_home_address',
                'return_recipient_mobile',
                'return_recipient_email',
                'return_item_description',
                'return_item_category',
                'return_security_name',
                'return_security_designation',
            ]
            for field_name in category_specific_fields:
                if field_name in kwargs:
                    vals[field_name] = kwargs.get(field_name)

            if 'statement_person_eid_expiry' in kwargs and kwargs.get('statement_person_eid_expiry'):
                vals['statement_person_eid_expiry'] = kwargs.get('statement_person_eid_expiry')
            if 'found_item_date' in kwargs and kwargs.get('found_item_date'):
                vals['found_item_date'] = kwargs.get('found_item_date')

            if 'found_item_inspected' in kwargs:
                vals['found_item_inspected'] = self._selection_from_yes_no(kwargs.get('found_item_inspected'))
            if 'found_item_supervisor_informed' in kwargs:
                vals['found_item_supervisor_informed'] = self._selection_from_yes_no(kwargs.get('found_item_supervisor_informed'))
            if 'found_item_handover' in kwargs:
                vals['found_item_handover'] = self._selection_from_yes_no(kwargs.get('found_item_handover'))

            # Signatures
            if 'statement_person_signature' in kwargs:
                signature_data = self._normalize_signature_data(kwargs.get('statement_person_signature'))
                if signature_data:
                    vals['statement_person_signature'] = signature_data
            if 'security_officer_signature' in kwargs:
                signature_data = self._normalize_signature_data(kwargs.get('security_officer_signature'))
                if signature_data:
                    vals['security_officer_signature'] = signature_data
            if 'found_item_person_signature' in kwargs:
                signature_data = self._normalize_signature_data(kwargs.get('found_item_person_signature'))
                if signature_data:
                    vals['found_item_person_signature'] = signature_data
            if 'return_recipient_signature' in kwargs:
                signature_data = self._normalize_signature_data(kwargs.get('return_recipient_signature'))
                if signature_data:
                    vals['return_recipient_signature'] = signature_data
            
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
            uploaded_files += request.httprequest.files.getlist('incident_videos')
            if uploaded_files:
                photo_attachment_ids = list(incident.photo_ids.ids) if incident.photo_ids else []
                video_attachment_ids = list(incident.video_ids.ids) if incident.video_ids else []
                for uploaded_file in uploaded_files:
                    if uploaded_file and uploaded_file.filename:
                        try:
                            attachment, is_video = self._create_incident_media_attachment(
                                incident, uploaded_file
                            )
                            if is_video:
                                video_attachment_ids.append(attachment.id)
                            else:
                                photo_attachment_ids.append(attachment.id)
                        except Exception as e:
                            _logger.error("Error uploading file %s: %s", uploaded_file.filename, str(e))
                
                update_vals = {}
                if photo_attachment_ids:
                    update_vals['photo_ids'] = [(6, 0, photo_attachment_ids)]
                if video_attachment_ids:
                    update_vals['video_ids'] = [(6, 0, video_attachment_ids)]
                if update_vals:
                    incident.sudo().write(update_vals)
            
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
                return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
                
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
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
            
        try:
            site = guard.current_site_id if guard else None
            
            # Fallback: If no site on profile, check active attendance
            if not site and guard:
                active_attendance = request.env['guard.attendance'].sudo().search([
                    ('guard_id', '=', guard.id),
                    ('checkout_time', '=', False),
                ], limit=1, order='checkin_time desc')
                if active_attendance:
                    site = active_attendance.site_id
                    _logger.info('[GuardPro Mobile] Found site from active attendance: %s', site.name)
            
            # Second Fallback: Check most recent shift
            if not site and guard:
                recent_shift = request.env['guard.shift'].sudo().search([
                    ('guard_id', '=', guard.id),
                ], limit=1, order='start_datetime desc')
                if recent_shift:
                    site = recent_shift.site_id
                    _logger.info('[GuardPro Mobile] Found site from recent shift: %s', site.name)

            _logger.info('[GuardPro Mobile] Site Info for Guard %s: Site=%s (ID: %s)', guard.name, site.name if site else 'None', site.id if site else 'None')
            
            if site and site.manager_id:
                _logger.info('[GuardPro Mobile] Site Manager for Site %s: %s (ID: %s)', site.name, site.manager_id.name, site.manager_id.id)
            
            return request.render('guardpro.mobile_site_info_template', {
                'guard': guard,
                'site': site,
                'format_datetime_tz': self._format_datetime_tz,
            })
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            _logger.error('[GuardPro Mobile] Error in mobile_site_info: %s\n%s', str(e), error_trace)
            return request.make_response(f"Internal Server Error\n\n{str(e)}\n\n{error_trace}", status=500)

    @http.route('/guardpro/mobile/emergency', type='http', auth='user', website=True)
    def mobile_emergency(self, **kwargs):
        """Mobile emergency procedures page."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
            
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
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
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
        user = request.env.user
        guard = self._get_guard_from_user()
        show_compliance = self._user_can_access_mobile_compliance(user)
        if not guard and not show_compliance:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return request.render('guardpro.mobile_more', {
            'guard': guard,
            'user': user,
            'show_compliance_audits': show_compliance,
        })

    @http.route('/guardpro/mobile/messages', type='http', auth='user', website=True)
    def mobile_messages(self, **kwargs):
        """WhatsApp-style inbox: direct chats and team channels."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return request.render('guardpro.mobile_messages', {
            'guard': guard,
            'user': request.env.user,
        })

    @http.route('/guardpro/mobile/messages/new', type='http', auth='user', website=True)
    def mobile_messages_new(self, **kwargs):
        """Start a new direct chat (supervisor or guard)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return request.render('guardpro.mobile_messages_new', {
            'guard': guard,
            'user': request.env.user,
        })

    @http.route('/guardpro/mobile/messages/chat/<int:conversation_id>', type='http', auth='user', website=True)
    def mobile_messages_chat(self, conversation_id, **kwargs):
        """Direct / 1:1 conversation thread."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return request.render('guardpro.mobile_messages_chat', {
            'guard': guard,
            'user': request.env.user,
            'conversation_id': conversation_id,
        })

    @http.route('/guardpro/mobile/messages/channel/<int:channel_id>', type='http', auth='user', website=True)
    def mobile_messages_channel(self, channel_id, **kwargs):
        """Team channel thread."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return request.render('guardpro.mobile_messages_channel', {
            'guard': guard,
            'user': request.env.user,
            'channel_id': channel_id,
        })

    @http.route('/guardpro/mobile/compliance', type='http', auth='user', website=True)
    def mobile_compliance_audits(self, **kwargs):
        """Compliance audits for supervisor / manager / admin (not guard portal)."""
        user = request.env.user
        if not self._user_can_access_mobile_compliance(user):
            return request.redirect('/guardpro/mobile?error=compliance_staff_only')
        guard = self._get_guard_from_user()
        audits = request.env['compliance.audit'].search(
            self._compliance_open_audits_domain_staff(),
            order='audit_date desc, id desc',
            limit=80,
        )
        return request.render('guardpro.mobile_compliance_list', {
            'guard': guard,
            'user': user,
            'audits': audits,
            'compliance_audit_type_label': self._compliance_audit_type_label,
        })

    @http.route('/guardpro/mobile/compliance/<int:audit_id>', type='http', auth='user', website=True)
    def mobile_compliance_audit_detail(self, audit_id, **kwargs):
        """Run checklist for one audit."""
        user = request.env.user
        if not self._user_can_access_mobile_compliance(user):
            return request.redirect('/guardpro/mobile?error=compliance_staff_only')
        guard = self._get_guard_from_user()
        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit:
            return request.redirect('/guardpro/mobile/compliance?error=audit_not_found')
        can_edit = self._compliance_user_can_write_audit(audit, user)
        pending_items = len(audit.checklist_ids.filtered(lambda i: not i.result))
        return request.render('guardpro.mobile_compliance_detail', {
            'guard': guard,
            'user': user,
            'audit': audit,
            'can_edit': can_edit,
            'pending_items': pending_items,
            'compliance_audit_type_label': self._compliance_audit_type_label,
        })

    @http.route('/guardpro/mobile/compliance/<int:audit_id>/start', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_compliance_audit_start(self, audit_id, **kwargs):
        user = request.env.user
        if not self._user_can_access_mobile_compliance(user):
            return request.redirect('/guardpro/mobile?error=compliance_staff_only')
        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit or not self._compliance_user_can_write_audit(audit, user):
            return request.redirect('/guardpro/mobile/compliance?error=audit_access_denied')
        try:
            audit.action_start_audit()
        except UserError as e:
            _logger.warning('[Mobile Compliance] Start blocked: %s', e)
            return request.redirect('/guardpro/mobile/compliance/%s?error=audit_start_failed' % audit_id)
        except AccessError:
            return request.redirect('/guardpro/mobile/compliance?error=audit_access_denied')
        return request.redirect('/guardpro/mobile/compliance/%s?success=audit_started' % audit_id)

    @http.route('/guardpro/mobile/compliance/<int:audit_id>/complete', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_compliance_audit_complete(self, audit_id, **kwargs):
        user = request.env.user
        if not self._user_can_access_mobile_compliance(user):
            return request.redirect('/guardpro/mobile?error=compliance_staff_only')
        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit or not self._compliance_user_can_write_audit(audit, user):
            return request.redirect('/guardpro/mobile/compliance?error=audit_access_denied')
        try:
            audit.action_complete_audit()
        except UserError as e:
            _logger.warning('[Mobile Compliance] Complete blocked: %s', e)
            return request.redirect(
                '/guardpro/mobile/compliance/%s?error=audit_complete_failed' % audit_id
            )
        except AccessError:
            return request.redirect('/guardpro/mobile/compliance?error=audit_access_denied')
        return request.redirect('/guardpro/mobile/compliance/%s?success=audit_completed' % audit_id)

    @http.route(
        '/guardpro/mobile/compliance/item/<int:item_id>/save',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True,
    )
    def mobile_compliance_item_save(self, item_id, result=None, notes=None, **kwargs):
        """Save one checklist line (result, notes, optional photo)."""
        user = request.env.user
        if not self._user_can_access_mobile_compliance(user):
            return request.redirect('/guardpro/mobile?error=compliance_staff_only')
        item = request.env['compliance.audit.item'].search([('id', '=', item_id)], limit=1)
        if not item:
            return request.redirect('/guardpro/mobile/compliance?error=audit_not_found')
        audit = item.audit_id
        if not self._compliance_user_can_write_audit(audit, user):
            return request.redirect('/guardpro/mobile/compliance?error=audit_access_denied')
        if audit.state not in ('draft', 'in_progress', 'requires_action'):
            return request.redirect(
                '/guardpro/mobile/compliance/%s?error=audit_invalid_state' % audit.id
            )

        vals = {}
        if result in ('pass', 'fail', 'na'):
            vals['result'] = result
        elif result in ('', None, False):
            vals['result'] = False

        if notes is not None:
            vals['notes'] = notes or ''

        if 'requires_action' in kwargs:
            vals['requires_action'] = kwargs.get('requires_action') in ('on', 'true', 'True', '1', True)

        sev = kwargs.get('severity')
        if sev in ('low', 'medium', 'high', 'critical'):
            vals['severity'] = sev
        elif sev in ('', None):
            vals['severity'] = False

        uploaded = request.httprequest.files.get('photo')
        if uploaded and uploaded.filename:
            try:
                raw = uploaded.read()
                datas_b64 = base64.b64encode(raw).decode()
                try:
                    datas_b64 = ImageOptimizer.optimize_image(
                        datas_b64,
                        max_dimension=1200,
                        target_format='JPEG',
                    )
                except Exception as opt_err:
                    _logger.debug('[Mobile Compliance] Photo optimize skipped: %s', opt_err)
                att = request.env['ir.attachment'].sudo().create({
                    'name': uploaded.filename or 'audit_evidence.jpg',
                    'type': 'binary',
                    'datas': datas_b64,
                    'res_model': 'compliance.audit.item',
                    'res_id': item.id,
                    'mimetype': (uploaded.content_type or 'image/jpeg').lower(),
                })
                vals['photo_ids'] = [(4, att.id)]
            except Exception as e:
                _logger.exception('[Mobile Compliance] Photo upload failed')
                return request.redirect(
                    '/guardpro/mobile/compliance/%s?error=audit_photo_failed' % audit.id
                )

        try:
            if vals:
                item.write(vals)
        except (AccessError, UserError) as e:
            _logger.warning('[Mobile Compliance] Item save failed: %s', e)
            return request.redirect(
                '/guardpro/mobile/compliance/%s?error=audit_item_save_failed' % audit.id
            )

        return request.redirect('/guardpro/mobile/compliance/%s?success=audit_item_saved' % audit.id)

    @http.route('/guardpro/mobile/training', type='http', auth='user', website=True)
    def mobile_training(self, **kwargs):
        """Legacy training route - redirect to full mobile training dashboard."""
        return request.redirect('/mobile/training')
    @http.route('/guardpro/mobile/training/<int:enrollment_id>', type='http', auth='user', website=True)
    def mobile_training_view(self, enrollment_id, **kwargs):
        """View details of a specific training enrollment."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
            
        enrollment = request.env['slide.channel.partner'].sudo().browse(enrollment_id)
        if not enrollment.exists() or enrollment.guard_id.id != guard.id:
            # Fallback for security/integrity
            return request.redirect('/guardpro/mobile/training')
            
        # Redirect to the website_slides course page or render a custom mobile-friendly view
        # For now, let's redirect to the standard eLearning page if available
        if enrollment.channel_id:
            return request.redirect(f'/slides/{enrollment.channel_id.id}')
            
        return request.redirect('/guardpro/mobile/training')


    @http.route('/guardpro/mobile/sw.js', type='http', auth='public')
    def mobile_service_worker(self, **kwargs):
        """Minimal service worker for offline support."""
        sw_content = """
// GuardPro Mobile - Minimal Service Worker (Odoo 18)
const CACHE_VERSION = 'v2.0.7';
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

