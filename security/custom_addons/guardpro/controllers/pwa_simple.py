# -*- coding: utf-8 -*-
"""Guard Pro PWA Controller - Simplified Odoo-Native Implementation.

This module provides a clean PWA interface using Odoo's standard web framework.
Following Odoo 18 best practices - minimal custom JavaScript, using standard views and actions.
"""

import logging
import json
import base64
import re
from urllib.parse import urlencode
from odoo import http, fields
from odoo.http import request
from odoo.exceptions import UserError, AccessError
from odoo.tools import html2plaintext
from datetime import datetime, timedelta
from ..common.video_optimizer import VideoOptimizer
from ..common.image_optimizer import ImageOptimizer
from ..common.upload_validation import (
    MAX_FILES_PER_REQUEST,
    UploadValidationError,
    validate_werkzeug_file,
)
from .mobile_entry import request_wants_mobile_shell

_logger = logging.getLogger(__name__)

# Mobile incident wizard: map step-1 types to incident.category codes.
# Include legacy aliases (STMT/FOUND/RETURN) and live DB codes
# (STATEMENT / FOUND ITEM / RETURN FORM).
MOBILE_COMMUNITY_VIOLATION_CODES = [
    'VAND', 'SHORT_LET', 'ILL_STAFF', 'MOVE_POL', 'SALE_POL',
    'ANIMAL', 'DMG_REC', 'DMG_COM', 'DMG_SPT', 'DMG_POOL',
    'DMG_PLNT', 'GARDEN', 'HOME_APP', 'EXT_MAJ', 'EXT_MIN',
    'SIGNAGE', 'TERRACE', 'PEST', 'GARAGE', 'RETAIL',
    # Related community / common-area categories present in live DB
    'ACS', 'ABSCS', 'MIS-COMMON', 'VOSSP', 'VSSP',
]

MOBILE_PARKING_VIOLATION_CODES = [
    'LT_PARK', 'DBL_PARK', 'BLK_ACCESS', 'ILLEGAL_PARK', 'VIS_PARK',
    'WRONG_PARK', 'UNDESIG_PARK', 'UNAUTH_VEH', 'PAVEMENT_PARK',
    'DISABLED_PARK', 'FIRE_HYD_PARK', 'LOAD_ZONE', 'PED_CROSS',
    'OVERNIGHT_PARK', 'RETAIL_PARK', 'NO_PAY_EXIT', 'LOST_TICKET', 'ABND_VEH',
]

MOBILE_INCIDENT_WIZARD_TYPE_DEFS = [
    {'type': 'suspicious_person', 'label': 'Suspicious Person', 'codes': ['SUSP', 'TRESP', 'DIST']},
    {'type': 'medical_emergency', 'label': 'Medical Emergency', 'codes': ['MED', 'FIRE']},
    {'type': 'property_damage', 'label': 'Property Damage', 'codes': [
        'SAFE', 'STRUCT', 'FLOOD', 'PWR_OUT', 'HVAC_FAIL',
    ]},
    {'type': 'community_violation', 'label': 'Community Violation', 'codes': list(MOBILE_COMMUNITY_VIOLATION_CODES)},
    {'type': 'parking_violation', 'label': 'Parking Violation', 'codes': list(MOBILE_PARKING_VIOLATION_CODES)},
    {'type': 'security_breach', 'label': 'Security Breach', 'codes': ['SEC', 'THEFT']},
    {'type': 'equipment_malfunction', 'label': 'Equipment Issue', 'codes': ['EQUIP', 'EQ_HO', 'CCTV_HO']},
    {'type': 'other', 'label': 'Other', 'codes': [
        'OTHER', 'STMT', 'STATEMENT', 'FOUND', 'FOUND ITEM', 'RETURN', 'RETURN FORM',
        'VEH', 'WEATH', 'AUTH_VISIT',
    ]},
]

# Codes that unlock Statement / Found / Return field blocks on mobile
MOBILE_STATEMENT_CATEGORY_CODES = frozenset({'STMT', 'STATEMENT'})
MOBILE_FOUND_CATEGORY_CODES = frozenset({'FOUND', 'FOUND ITEM'})
MOBILE_RETURN_CATEGORY_CODES = frozenset({'RETURN', 'RETURN FORM'})


class GuardLinkPWASimple(http.Controller):
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

    def _request_wants_mobile_shell(self):
        """True for the GuardLink app and typical phone browsers."""
        return request_wants_mobile_shell()

    def _mobile_role(self, guard=None):
        """Role for the mobile shell: guard, supervisor, client, or other."""
        if guard is None:
            guard = self._get_guard_from_user()
        if guard:
            return 'guard'
        user = request.env.user
        if (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        ):
            return 'supervisor'
        if user.has_group('guardpro.group_guardpro_client_user'):
            return 'client'
        return 'other'

    def _mobile_desktop_home_url(self, role):
        if role == 'client':
            return '/my/dashboard'
        return '/web'

    def _mobile_shell_vals(self, extra=None):
        user = request.env.user
        guard = extra.get('guard') if extra and 'guard' in extra else self._get_guard_from_user()
        vals = {
            'user': user,
            'guard': guard,
            'mobile_role': extra.get('mobile_role') if extra and extra.get('mobile_role') else self._mobile_role(guard),
            'show_compliance_audits': self._user_can_access_mobile_compliance(user),
            'format_datetime_tz': self._format_datetime_tz,
        }
        if extra:
            vals.update(extra)
            if 'mobile_role' not in extra:
                vals['mobile_role'] = self._mobile_role(vals.get('guard'))
        return vals

    def _mobile_render(self, template, values=None):
        """Render a mobile page with role-aware bottom navigation."""
        return request.render(template, self._mobile_shell_vals(values or {}))

    def _mobile_role_home_vals(self, role):
        user = request.env.user
        show_compliance = self._user_can_access_mobile_compliance(user)
        compliance_open_count = 0
        if show_compliance:
            compliance_open_count = request.env['compliance.audit'].search_count(
                self._compliance_open_audits_domain_staff()
            )
        Incident = request.env['incident.report'].sudo()
        site_dom = self._mobile_site_domain('incident.report')
        open_incidents_count = Incident.search_count(
            Incident._domain_security_incidents([
                ('status', 'in', ['submitted', 'under_review', 'investigating']),
            ] + site_dom)
        )
        return self._mobile_shell_vals({
            'guard': False,
            'mobile_role': role,
            'show_compliance_audits': show_compliance,
            'compliance_open_count': compliance_open_count,
            'open_incidents_count': open_incidents_count,
        })

    def _mobile_today_utc_range(self):
        """Start/end of 'today' in the guard user's timezone, as naive UTC for DB queries."""
        import pytz
        user_tz = pytz.timezone(request.env.user.tz or 'UTC')
        now_utc = pytz.UTC.localize(datetime.utcnow())
        now_tz = now_utc.astimezone(user_tz)
        today_start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_tz = today_start_tz + timedelta(days=1)
        today_start = today_start_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        today_end = today_end_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        now_naive = now_utc.replace(tzinfo=None)
        return today_start, today_end, now_naive

    def _mobile_guard_shifts_for_tours(self, guard, active_attendance=None):
        """Today's shifts for this guard (exclude cancelled only, include no_show)."""
        today_start, today_end, now = self._mobile_today_utc_range()
        Shift = request.env['guard.shift'].sudo()
        shifts = Shift.search([
            ('guard_id', '=', guard.id),
            ('status', '!=', 'cancelled'),
            ('start_datetime', '<', today_end),
            ('end_datetime', '>', today_start),
        ] + self._mobile_site_domain('guard.shift'), order='start_datetime asc')
        if active_attendance and active_attendance.shift_id:
            shifts |= active_attendance.shift_id
        if not shifts:
            # Overnight edge case: duty window crosses midnight
            shifts = Shift.search([
                ('guard_id', '=', guard.id),
                ('status', '!=', 'cancelled'),
                ('start_datetime', '<=', now + timedelta(hours=2)),
                ('end_datetime', '>=', now - timedelta(hours=1)),
            ], limit=3, order='start_datetime desc')
        return shifts

    def _mobile_tour_is_startable(self, tour):
        return tour.status in ('active', 'draft')

    def _mobile_active_tour_scan_config(self, active_tours):
        """JSON config for passive NFC auto-scan on the active patrol."""
        if not active_tours:
            return None
        tour_log = active_tours[0]
        scanned_ids = tour_log.scan_ids.filtered(
            lambda s: s.status == 'verified'
        ).mapped('checkpoint_id').ids
        return {
            'tour_log_id': tour_log.id,
            'tour_name': tour_log.tour_id.name or tour_log.name,
            'site_name': tour_log.site_id.name or '',
            'checkpoints': tour_log.tour_id.get_checkpoint_api_payloads(scanned_ids),
        }

    def _mobile_tour_log_is_stale(self, tour_log):
        """True when the patrol was started before today (guard local timezone)."""
        if not tour_log or not tour_log.start_time:
            return False
        today_start, _, _ = self._mobile_today_utc_range()
        return tour_log.start_time < today_start

    def _mobile_collect_available_tours(self, guard, active_tours, active_attendance=None):
        """Tours explicitly assigned on today's shift(s), not all historical assignments."""
        active_tour_ids = active_tours.mapped('tour_id').ids if active_tours else []
        shifts = self._mobile_guard_shifts_for_tours(guard, active_attendance)
        tour_ids = []

        for shift in shifts:
            for tour in shift.tour_ids:
                if self._mobile_tour_is_startable(tour):
                    tour_ids.append(tour.id)
                    _logger.info(
                        '[Mobile Tours] Tour "%s" (id=%s) from shift %s (status=%s)',
                        tour.name, tour.id, shift.name, shift.status,
                    )

        tour_ids = list(dict.fromkeys(tour_ids))  # preserve order, unique
        available_ids = [tid for tid in tour_ids if tid not in active_tour_ids]
        if available_ids:
            available = request.env['security.tour'].sudo().browse(available_ids)
            available = available.filtered(lambda t: t.status in ('active', 'draft'))
        elif active_attendance and active_attendance.shift_id:
            # Only tours on the checked-in shift — never all site tours
            available = active_attendance.shift_id.tour_ids.filtered(
                lambda t: t.status in ('active', 'draft') and t.id not in active_tour_ids
            )
        else:
            available = request.env['security.tour'].sudo().browse([])

        _, _, now = self._mobile_today_utc_range()
        overlapping = shifts.filtered(
            lambda s: s.start_datetime and s.end_datetime
            and s.start_datetime <= now + timedelta(hours=2)
            and s.end_datetime >= now - timedelta(hours=1)
        )
        current_shift = overlapping[:1] or shifts[:1]
        return available, shifts, current_shift

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
        """Project (client.site) for mobile actions: selected location, then attendance/shift."""
        user = request.env.user
        write_vals = user.guardpro_mobile_write_vals()
        if write_vals.get('site_id'):
            return write_vals['site_id']
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

    def _mobile_site_domain(self, model_name, project_field='site_id',
                            guard_site_field='guard_site_id'):
        """Domain for the guard's currently selected mobile site."""
        return request.env.user.guardpro_mobile_record_domain(
            model_name,
            project_field=project_field,
            guard_site_field=guard_site_field,
        )

    def _mobile_stamp_site(self, vals):
        """Apply selected project/site onto create vals when those fields exist."""
        extra = request.env.user.guardpro_mobile_write_vals()
        if extra.get('site_id'):
            vals['site_id'] = extra['site_id']
        if extra.get('guard_site_id'):
            vals['guard_site_id'] = extra['guard_site_id']
        return vals

    def _guard_allowed_site_ids(self, guard=None):
        """Site IDs the current user may operate on for mobile key/package flows."""
        user = request.env.user
        if user.has_group('guardpro.group_guardpro_admin'):
            return None  # unrestricted
        site_ids = set(user.site_ids.ids)
        if guard and guard.site_ids:
            site_ids |= set(guard.site_ids.ids)
        return frozenset(site_ids)

    def _site_allowed_for_guard(self, guard, site_id):
        """True when ``site_id`` is within the caller's assigned projects."""
        if not site_id:
            return False
        allowed = self._guard_allowed_site_ids(guard)
        if allowed is None:
            return True
        return site_id in allowed

    def _mobile_visitor_site(self, guard):
        """Resolved site record for mobile visitor operations."""
        site_id = self._resolve_guard_operation_site_id(guard)
        if not site_id:
            return None, request.env['client.site'].sudo().browse()
        site = request.env['client.site'].sudo().browse(site_id)
        return site_id, site

    def _mobile_visitors_list_domain(self, guard, search_query=None):
        """Domain for site visitors on the mobile list (checked in and checked out)."""
        site_id, _site = self._mobile_visitor_site(guard)
        domain = [('state', 'in', ['checked_in', 'checked_out'])]
        if site_id:
            domain.append(('site_id', '=', site_id))
        else:
            domain.extend([
                '|',
                ('guard_checkin_id', '=', guard.id),
                ('guard_checkout_id', '=', guard.id),
            ])
        domain += self._mobile_site_domain('visitor.management')
        q = (search_query or '').strip()
        if q:
            domain.extend([
                '|', '|', '|', '|',
                ('name', 'ilike', q),
                ('id_number', 'ilike', q),
                ('mobile_number', 'ilike', q),
                ('host_name', 'ilike', q),
                ('company', 'ilike', q),
            ])
        return domain

    def _mobile_no_guard_render_vals(self):
        """Context for the no-guard profile screen (includes supervisor compliance entry)."""
        user = request.env.user
        return self._mobile_shell_vals({
            'guard': False,
            'user': user,
            'show_compliance_audits': self._user_can_access_mobile_compliance(user),
        })

    def _compliance_user_is_assigned_auditor(self, audit, user):
        """True if user is lead auditor or on the audit team."""
        if not audit or not user:
            return False
        if audit.auditor_id and audit.auditor_id.id == user.id:
            return True
        return user.id in audit.auditor_team_ids.ids

    def _user_can_access_mobile_compliance(self, user):
        """Compliance mobile UI/API: GuardLink Supervisor / Manager / Admin (not guard-only portal)."""
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
            'site': 'Project Audit',
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

    def _wizard_type_for_category_code(self, category_code):
        """Map an incident.category code back to a mobile wizard type."""
        code = (category_code or '').strip()
        if not code:
            return None
        for defn in MOBILE_INCIDENT_WIZARD_TYPE_DEFS:
            if code in defn['codes']:
                return defn['type']
        return 'other'

    def _categories_for_wizard_type(self, wizard_type, categories=None):
        """Return only categories allowed for a mobile wizard type."""
        Category = request.env['incident.category'].sudo()
        if categories is None:
            categories = Category.search([('hide_from_guard_incidents', '=', False)])
        if not wizard_type:
            return categories
        codes = set()
        for defn in MOBILE_INCIDENT_WIZARD_TYPE_DEFS:
            if defn['type'] == wizard_type:
                codes.update(defn['codes'])
                break
        if not codes:
            return categories
        return categories.filtered(lambda c: c.code in codes)

    def _wizard_incident_category_groups(self, categories):
        """Build server-side category groups for the mobile incident wizard."""
        cats_by_code = {c.code: c for c in categories}
        groups = []
        for defn in MOBILE_INCIDENT_WIZARD_TYPE_DEFS:
            # Deduplicate when both legacy and live codes resolve to records
            seen_ids = set()
            matched = []
            for code in defn['codes']:
                cat = cats_by_code.get(code)
                if cat and cat.id not in seen_ids:
                    seen_ids.add(cat.id)
                    matched.append(cat)
            # Prefer a live/default code that actually exists
            default_code = False
            for code in defn['codes']:
                if code in cats_by_code:
                    default_code = code
                    break
            groups.append({
                'type': defn['type'],
                'label': defn['label'],
                'categories': matched,
                'default_code': default_code,
            })
        return groups

    def _infer_wizard_type_from_title(self, title):
        """Guess mobile wizard type from the prefilled / user-edited title."""
        if not title:
            return None
        t = title.lower().strip()
        hints = [
            ('suspicious person', 'suspicious_person'),
            ('suspicious', 'suspicious_person'),
            ('medical emergency', 'medical_emergency'),
            ('medical', 'medical_emergency'),
            ('community violation', 'community_violation'),
            ('parking violation', 'parking_violation'),
            ('double parking', 'parking_violation'),
            ('illegal parking', 'parking_violation'),
            ('property damage', 'property_damage'),
            ('security breach', 'security_breach'),
            ('equipment malfunction', 'equipment_malfunction'),
            ('equipment issue', 'equipment_malfunction'),
        ]
        for phrase, wizard_type in hints:
            if phrase in t:
                return wizard_type
        return None

    def _resolve_mobile_incident_category(self, category_id=None, wizard_type=None, title=None):
        """Resolve incident category from posted id, wizard type, or title."""
        wizard_type_codes = {
            'suspicious_person': 'SUSP',
            'medical_emergency': 'MED',
            'property_damage': 'SAFE',
            'community_violation': 'VAND',
            'parking_violation': 'ILLEGAL_PARK',
            'security_breach': 'SEC',
            'equipment_malfunction': 'EQUIP',
            'other': 'OTHER',
        }
        Category = request.env['incident.category'].sudo()
        if category_id:
            try:
                cat = Category.browse(int(category_id))
                if cat.exists() and not cat.hide_from_guard_incidents:
                    return cat
            except (ValueError, TypeError):
                pass

        resolved_type = (wizard_type or '').strip() or self._infer_wizard_type_from_title(title)
        code = wizard_type_codes.get(resolved_type)
        if code:
            cat = Category.search([
                ('code', '=', code),
                ('hide_from_guard_incidents', '=', False),
            ], limit=1)
            if cat:
                return cat

        # Last resort: match category display name from title keywords
        if title:
            t = title.lower()
            name_hints = [
                (('suspicious',), 'SUSP'),
                (('medical',), 'MED'),
                (('property damage', 'vandal'), 'VAND'),
                (('security breach',), 'SEC'),
                (('equipment',), 'EQUIP'),
            ]
            for phrases, code in name_hints:
                if any(p in t for p in phrases):
                    cat = Category.search([
                        ('code', '=', code),
                        ('hide_from_guard_incidents', '=', False),
                    ], limit=1)
                    if cat:
                        return cat
        return Category.browse()

    def _is_video_upload(self, uploaded_file):
        """Detect if uploaded file is a video based on mime or extension."""
        content_type = (uploaded_file.content_type or '').lower()
        if content_type.startswith('video/'):
            return True
        filename = (uploaded_file.filename or '').lower()
        return filename.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'))

    def _create_incident_media_attachment(self, incident, uploaded_file):
        """Create a media attachment for incident with type/size checks + compression."""
        validated = validate_werkzeug_file(
            uploaded_file, allow_video=True, allow_image=True
        )
        file_content = validated['data']
        is_video = validated['is_video']
        mimetype = validated['mimetype']
        safe_name = validated['filename']

        if is_video:
            datas, compressed = VideoOptimizer.optimize_video(
                file_content,
                filename=safe_name,
            )
            if compressed:
                mimetype = 'video/mp4'
            elif not mimetype:
                mimetype = 'video/mp4'
        else:
            try:
                optimized = ImageOptimizer.optimize_for_mobile(file_content)
                datas = base64.b64encode(optimized).decode('ascii')
            except Exception as opt_err:
                _logger.debug('[Mobile Incident] Photo optimize skipped: %s', opt_err)
                datas = base64.b64encode(file_content).decode('ascii')
            if not mimetype or mimetype == 'application/octet-stream':
                mimetype = 'image/jpeg'

        return request.env['ir.attachment'].sudo().create({
            'name': safe_name,
            'type': 'binary',
            'datas': datas,
            'res_model': 'incident.report',
            'res_id': incident.id,
            'mimetype': mimetype,
        }), is_video

    def _sync_excel_form_values_to_incident(self, incident):
        """Copy Excel dynamic values onto structured incident fields.

        Mobile community-violation (and similar) forms store answers in
        ``incident.form.value``, but the backend Community Violation page and
        PDF read ``violation_*`` / ``door_lock_*`` / ``involved_*``. Without
        this mapping those screens look empty after a successful submit.
        """
        if not incident or not incident.form_value_ids:
            return
        vals = {}
        observed_date = None
        observed_time = None
        detail_parts = []
        action_parts = []

        def _norm_name(name):
            return ' '.join(str(name or '').lower().split())

        for fv in incident.form_value_ids:
            fname = _norm_name(fv.field_id.name)
            display = (fv.get_display_value() or '').strip()
            if not display and fv.field_type != 'boolean':
                continue

            if 'community name' in fname:
                vals.setdefault('door_lock_community_name', display)
                vals.setdefault('involved_community', display)
            elif fname in ('unit number', 'unit/villa/shop number') or (
                'unit' in fname and 'number' in fname
            ):
                vals.setdefault('violation_unit_number', display)
                vals.setdefault('involved_unit_number', display)
                vals.setdefault('door_lock_unit_number', display)
            elif fname == 'date' or fname.endswith(' date'):
                observed_date = fv.value_date or display or observed_date
            elif fname == 'time' or fname.endswith(' time'):
                observed_time = (fv.value_time or fv.value_char or display or observed_time)
            elif 'type of violation' in fname or fname == 'violation type':
                if display:
                    detail_parts.insert(0, '<p><strong>Type of Violation:</strong> %s</p>' % display)
                    # Prefer a concrete title over the generic parent name
                    if not incident.title or incident.title in (
                        'Community Violation', 'Incident Report',
                    ):
                        vals['title'] = display[:200]
            elif 'notes for the security' in fname or fname in (
                'violation details', 'details', 'notes',
            ):
                if display:
                    detail_parts.append(display if display.startswith('<') else '<p>%s</p>' % display)
            elif 'speak with the resident' in fname:
                spoke = bool(fv.value_boolean) if fv.field_type == 'boolean' else display.lower() in (
                    'yes', 'true', '1', 'on',
                )
                action_parts.append(
                    'Spoke with resident: %s' % ('Yes' if spoke else 'No')
                )
            elif 'resident agree' in fname:
                agreed = bool(fv.value_boolean) if fv.field_type == 'boolean' else display.lower() in (
                    'yes', 'true', '1', 'on',
                )
                action_parts.append(
                    'Resident agreed to clear violation: %s' % ('Yes' if agreed else 'No')
                )
            elif fname in ('security name', 'reported by') or (
                'security name' in fname
            ):
                vals.setdefault('violation_reported_by', display)
            elif fv.field_type == 'signature' and fv.value_binary:
                vals.setdefault('security_officer_signature', fv.value_binary)

        if observed_date:
            try:
                from datetime import datetime as dt_cls
                date_str = str(observed_date)
                time_str = str(observed_time or '00:00').strip()
                if len(time_str) == 5:
                    time_str = time_str + ':00'
                combined = dt_cls.strptime(
                    '%s %s' % (date_str[:10], time_str[:8]),
                    '%Y-%m-%d %H:%M:%S',
                )
                # Store as naive UTC wall-clock (same convention as mobile create)
                vals['violation_observed_datetime'] = fields.Datetime.to_string(combined)
            except Exception as e:
                _logger.warning(
                    'Could not build violation_observed_datetime for %s: %s',
                    incident.name, e,
                )

        if detail_parts and not incident.violation_details:
            vals['violation_details'] = '\n'.join(detail_parts)
            # Keep description useful when it was auto-filled from the parent name
            if not incident.description or incident.description in (
                '<p>Community Violation</p>', 'Community Violation',
                '<p>Incident Report</p>', 'Incident Report',
            ):
                vals['description'] = vals['violation_details']

        if action_parts and not incident.violation_action_taken:
            vals['violation_action_taken'] = '\n'.join(action_parts)

        if vals:
            try:
                incident.sudo().write(vals)
            except Exception as e:
                _logger.warning(
                    'Failed syncing excel form values onto incident %s: %s',
                    incident.name, e,
                )

    def _persist_incident_excel_form_values(self, incident, media_only=False):
        """Save Excel form field values, including media file uploads.

        Text/signature values come from ``request.form``; media fields are
        ``<input type="file" name="form_field_<id>">`` and live in
        ``request.files`` (they never appear in form text). Media is also
        linked onto ``photo_ids`` / ``video_ids`` so PDFs and the Media tab
        show them.

        :param media_only: If True, only process media file uploads (used on
            incident update so we do not duplicate text form values).
        """
        FormValue = request.env['incident.form.value'].sudo()
        FormField = request.env['incident.form.field'].sudo()
        photo_ids = []
        video_ids = []

        if not media_only:
            for key, raw in request.httprequest.form.items():
                if not key.startswith('form_field_'):
                    continue
                try:
                    field_id = int(key.replace('form_field_', '', 1))
                except (TypeError, ValueError):
                    continue
                field = FormField.browse(field_id)
                if not field.exists():
                    continue
                ftype = field.field_type
                # File uploads are handled below from request.files
                if ftype == 'media':
                    continue
                vvals = {
                    'incident_id': incident.id,
                    'field_id': field.id,
                }
                if ftype == 'boolean':
                    vvals['value_boolean'] = str(raw).strip().lower() in (
                        'on', 'true', '1', 'yes',
                    )
                elif ftype == 'integer':
                    try:
                        vvals['value_integer'] = int(raw)
                    except (TypeError, ValueError):
                        vvals['value_char'] = raw
                elif ftype == 'date':
                    vvals['value_date'] = raw or False
                elif ftype == 'text':
                    vvals['value_text'] = raw
                elif ftype == 'time':
                    # Store in both columns — display helpers read value_char
                    vvals['value_time'] = raw
                    vvals['value_char'] = raw
                elif ftype == 'signature':
                    sig = self._normalize_signature_data(raw)
                    if not sig:
                        continue
                    vvals['value_binary'] = sig
                    vvals['value_filename'] = 'signature.png'
                else:
                    vvals['value_char'] = raw
                if raw not in (None, '', False) or ftype == 'boolean':
                    try:
                        FormValue.create(vvals)
                    except Exception as e:
                        _logger.warning(
                            'Skipped excel form field %s (%s) on incident %s: %s',
                            field.name, field_id, incident.name, e,
                        )

        # Media fields: read uploaded files named form_field_<id>
        media_budget = MAX_FILES_PER_REQUEST
        for key in list(request.httprequest.files.keys()):
            if not key.startswith('form_field_') or media_budget <= 0:
                continue
            try:
                field_id = int(key.replace('form_field_', '', 1))
            except (TypeError, ValueError):
                continue
            field = FormField.browse(field_id)
            if not field.exists() or field.field_type != 'media':
                continue
            for uploaded_file in request.httprequest.files.getlist(key):
                if media_budget <= 0:
                    break
                if not uploaded_file or not uploaded_file.filename:
                    continue
                try:
                    attachment, is_video = self._create_incident_media_attachment(
                        incident, uploaded_file
                    )
                except UploadValidationError as e:
                    _logger.warning(
                        'Rejected form media %s for incident %s: %s',
                        uploaded_file.filename, incident.name, e,
                    )
                    continue
                except Exception as e:
                    _logger.error(
                        'Error uploading form media %s: %s',
                        uploaded_file.filename, e,
                    )
                    continue
                media_budget -= 1
                FormValue.create({
                    'incident_id': incident.id,
                    'field_id': field.id,
                    'value_binary': attachment.datas,
                    'value_filename': attachment.name,
                })
                if is_video:
                    video_ids.append(attachment.id)
                else:
                    photo_ids.append(attachment.id)
                _logger.info(
                    'Saved Excel form media %s on incident %s (field %s)',
                    uploaded_file.filename, incident.name, field.name,
                )

        return photo_ids, video_ids

    def _attach_incident_step_media(self, incident, photo_ids=None, video_ids=None):
        """Attach Photos-step uploads and merge with any Excel form media ids."""
        photo_ids = list(photo_ids or [])
        video_ids = list(video_ids or [])
        remaining = max(0, MAX_FILES_PER_REQUEST - (len(photo_ids) + len(video_ids)))
        uploaded_files = request.httprequest.files.getlist('incident_images')
        uploaded_files += request.httprequest.files.getlist('incident_videos')
        uploaded_files = [f for f in uploaded_files if f and f.filename][:remaining]
        for uploaded_file in uploaded_files:
            try:
                attachment, is_video = self._create_incident_media_attachment(
                    incident, uploaded_file
                )
                if is_video:
                    video_ids.append(attachment.id)
                else:
                    photo_ids.append(attachment.id)
                _logger.info(
                    'Created attachment %s for incident %s',
                    uploaded_file.filename, incident.name,
                )
            except UploadValidationError as e:
                _logger.warning(
                    'Rejected upload %s for incident %s: %s',
                    uploaded_file.filename, incident.name, e,
                )
            except Exception as e:
                _logger.error(
                    'Error uploading file %s: %s',
                    uploaded_file.filename, e,
                )

        update_vals = {}
        # Merge with existing on update paths
        if photo_ids:
            merged_photos = list(dict.fromkeys(
                list(incident.photo_ids.ids) + photo_ids
            ))
            update_vals['photo_ids'] = [(6, 0, merged_photos)]
        if video_ids:
            merged_videos = list(dict.fromkeys(
                list(incident.video_ids.ids) + video_ids
            ))
            update_vals['video_ids'] = [(6, 0, merged_videos)]
        if update_vals:
            incident.sudo().write(update_vals)
        return photo_ids, video_ids

    @http.route('/guardpro/mobile/activity-consent', type='http', auth='user',
                methods=['POST'], csrf=True)
    def mobile_activity_consent(self, **kwargs):
        """Acknowledge activity-monitoring disclaimer for this login session."""
        request.session['guardpro_activity_monitor_consent'] = True
        next_url = self._mobile_safe_next_url(
            kwargs.get('next'), default='/guardpro/mobile')
        return request.redirect(next_url)

    @http.route('/guardpro/mobile/select_site', type='http', auth='user',
                methods=['GET', 'POST'], website=True, csrf=False)
    def mobile_select_site(self, location=None, next=None, **kwargs):
        """Switch the mobile working site for this session."""
        user = request.env.user
        options = user.guardpro_mobile_locations()
        if location and any(opt['key'] == location for opt in options):
            request.session['gp_mobile_loc_key'] = location
        nxt = self._mobile_safe_next_url(next, default='/guardpro/mobile')
        if nxt.startswith('/guardpro/mobile/select_site'):
            nxt = '/guardpro/mobile'
        sep = '&' if '?' in nxt else '?'
        return request.redirect('%s%sloc=%s' % (nxt, sep, location or ''))

    @http.route('/guardpro/mobile', type='http', auth='user', website=True)
    def mobile_dashboard(self, **kwargs):
        """Main mobile dashboard using Odoo website framework."""
        _logger.info('[GuardLink Mobile] Accessed by user: %s (ID: %s)', request.env.user.name, request.env.user.id)
        
        guard = self._get_guard_from_user()
        role = self._mobile_role(guard)

        if not guard:
            if role == 'supervisor':
                return request.render(
                    'guardpro.mobile_staff_dashboard',
                    self._mobile_role_home_vals(role),
                )
            if role == 'client':
                return request.render(
                    'guardpro.mobile_client_dashboard',
                    self._mobile_role_home_vals(role),
                )
            _logger.warning('[Guard Pro Mobile] No guard profile found for user: %s', request.env.user.name)
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
        # Get today's data
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        
        # Fetch data using Odoo ORM (no caching needed - let Odoo handle it)
        site_dom_shift = self._mobile_site_domain('guard.shift')
        shifts_today = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_start),
            ('start_datetime', '<', today_end),
        ] + site_dom_shift, limit=5, order='start_datetime asc')
        
        active_tasks = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', 'in', ['assigned', 'in_progress']),
        ] + self._mobile_site_domain('guard.task'), limit=10, order='priority desc, due_date asc')
        
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        recent_incidents = request.env['incident.report'].sudo().search(
            request.env['incident.report']._domain_security_incidents([
                ('guard_id', '=', guard.id),
            ] + self._mobile_site_domain('incident.report')),
            limit=5,
            order='incident_datetime desc',
        )

        user = request.env.user
        show_compliance_audits = self._user_can_access_mobile_compliance(user)
        compliance_open_count = 0
        if show_compliance_audits:
            compliance_open_count = request.env['compliance.audit'].search_count(
                self._compliance_open_audits_domain_staff()
            )
        
        # Active patrol progress for the home screen badge / summary
        active_tour_log = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', '=', 'in_progress'),
        ], limit=1, order='start_time desc')

        open_incidents_count = request.env['incident.report'].sudo().search_count(
            request.env['incident.report']._domain_security_incidents([
                ('guard_id', '=', guard.id),
                ('status', 'in', ['submitted', 'under_review', 'investigating']),
            ] + self._mobile_site_domain('incident.report'))
        )

        lost_found_today_count = request.env['lost.found.item'].sudo().search_count([
            ('guard_logged_by', '=', guard.id),
            ('found_date', '>=', today_start),
        ] + self._mobile_site_domain('lost.found.item'))

        site_id, _site = self._mobile_visitor_site(guard)
        visitor_domain = [('state', '=', 'checked_in')]
        if site_id:
            visitor_domain.append(('site_id', '=', site_id))
        visitor_domain += self._mobile_site_domain('visitor.management')
        checked_in_visitors_count = request.env['visitor.management'].sudo().search_count(
            visitor_domain
        )

        # Keys & Packages badge counts
        site_ids = [site_id] if site_id else (guard.site_ids.ids if guard.site_ids else [])
        keys_pending_count = request.env['key.transaction'].sudo().search_count([
            ('state', '=', 'issued'),
            ('key_id.site_id', 'in', site_ids),
        ]) if site_ids else 0
        packages_pending_count = request.env['package.management'].sudo().search_count([
            ('state', '=', 'received'),
            ('site_id', 'in', site_ids),
        ] + self._mobile_site_domain('package.management')) if site_ids else 0

        return self._mobile_render('guardpro.mobile_dashboard', {
            'guard': guard,
            'user': user,
            'mobile_role': 'guard',
            'shifts_today': shifts_today,
            'active_tasks': active_tasks,
            'is_checked_in': bool(active_attendance),
            'active_attendance': active_attendance,
            'recent_incidents': recent_incidents,
            'open_incidents_count': open_incidents_count,
            'active_tour_log': active_tour_log,
            'show_compliance_audits': show_compliance_audits,
            'compliance_open_count': compliance_open_count,
            'lost_found_today_count': lost_found_today_count,
            'checked_in_visitors_count': checked_in_visitors_count,
            'keys_pending_count': keys_pending_count,
            'packages_pending_count': packages_pending_count,
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
            ('status', 'in', ['scheduled', 'confirmed', 'in_progress', 'no_show']),
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
        
        # Fallback: Try guard's assigned projects (first one)
        if not site_id:
            if guard.site_ids:
                site_id = guard.site_ids[0].id
                _logger.info('[Mobile Check-In] Using first assigned site: %s (ID: %s)', 
                           guard.site_ids[0].name, site_id)
        
        if not site_id:
            _logger.error('[Mobile Check-In] No site found for guard %s (ID: %s). '
                        'Guard has no active shift, no current_site_id, no previous attendance, and no assigned projects.', 
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
        self._mobile_stamp_site(vals)
        
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

        open_tours = request.env['tour.log'].sudo().search_count([
            ('guard_id', '=', guard.id),
            ('status', '=', 'in_progress'),
        ])
        if open_tours:
            return request.redirect(
                '/guardpro/mobile/tours?error=tour_in_progress'
            )

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
        return self._mobile_render('guardpro.mobile_visitor_register', {
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
        mobile_number = (post.get('mobile_number') or '').strip()
        if not name or not host_name or not visit_purpose:
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_missing_fields')
        if not mobile_number:
            return request.redirect('/guardpro/mobile/visitors/register?error=visitor_register_missing_mobile')
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
            'mobile_number': mobile_number,
            'site_id': site_id,
            'state': 'checked_in',
            'checkin_time': fields.Datetime.now(),
            'guard_checkin_id': guard.id,
        }
        self._mobile_stamp_site(vals)
        optional_char = [
            'id_number', 'nationality', 'occupation', 'employer_name', 'issuing_place',
            'email', 'company',
            'purpose_details', 'host_phone', 'host_email',
            'host_community', 'host_unit_number', 'vehicle_number',
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
        return request.redirect('/guardpro/mobile/visitors?success=visitor_registered')

    @http.route('/guardpro/mobile/visitors', type='http', auth='user', website=True)
    def mobile_visitors(self, q=None, **kwargs):
        """Visitor hub: checked-in list + register button."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        site_id, site = self._mobile_visitor_site(guard)
        search_q = (q or kwargs.get('search') or '').strip()
        domain = self._mobile_visitors_list_domain(guard, search_q)
        visitors = request.env['visitor.management'].sudo().search(
            domain, order='checkin_time desc', limit=500
        )
        checked_in_count = len(visitors.filtered(lambda v: v.state == 'checked_in'))
        checked_out_count = len(visitors.filtered(lambda v: v.state == 'checked_out'))

        error = kwargs.get('error')
        success = kwargs.get('success')
        export_qs = ('?' + urlencode({'q': search_q})) if search_q else ''
        return self._mobile_render('guardpro.mobile_visitors', {
            'guard': guard,
            'user': request.env.user,
            'visitors': visitors,
            'checked_in_count': checked_in_count,
            'checked_out_count': checked_out_count,
            'site': site if site_id else None,
            'search_q': search_q,
            'export_url': '/guardpro/mobile/visitors/export' + export_qs,
            'error': error,
            'success': success,
            'format_datetime_tz': self._format_datetime_tz,
        })

    @http.route('/guardpro/mobile/visitors/export', type='http', auth='user', methods=['GET'])
    def mobile_visitors_export(self, q=None, **kwargs):
        """Download site visitor list as Excel."""
        import pytz

        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')

        try:
            search_q = (q or kwargs.get('search') or '').strip()
            domain = self._mobile_visitors_list_domain(guard, search_q)
            visitors = request.env['visitor.management'].sudo().search(
                domain, order='checkin_time desc', limit=5000
            )

            site_id, site = self._mobile_visitor_site(guard)
            today = fields.Date.context_today(request.env['visitor.management'])
            dubai_tz = pytz.timezone('Asia/Dubai')
            xlsx_data = request.env['visitor.management']._build_daily_visitor_log_xlsx(
                visitors, today, dubai_tz
            )

            site_slug = re.sub(
                r'[^\w\-]+', '_',
                (site.name if site_id and site.exists() else 'site'),
            )[:40]
            filename = f'visitors_{site_slug}_{today}.xlsx'
            return request.make_response(
                xlsx_data,
                headers=[
                    ('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'),
                    ('Content-Disposition', f'attachment; filename="{filename}"'),
                    ('Content-Length', str(len(xlsx_data))),
                    ('Cache-Control', 'no-store, no-cache, must-revalidate'),
                ],
            )
        except Exception as exc:
            _logger.exception('[GuardLink] Visitor Excel export failed: %s', exc)
            return request.redirect('/guardpro/mobile/visitors?error=export_failed')

    @http.route('/guardpro/mobile/visitors/checkout/<int:visitor_id>',
                type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_visitor_checkout(self, visitor_id, notes=None, **kwargs):
        """Check out a visitor."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        visitor = request.env['visitor.management'].sudo().browse(visitor_id)
        if not visitor.exists() or visitor.state != 'checked_in':
            return request.redirect('/guardpro/mobile/visitors?error=invalid_visitor')
        site_id, _site = self._mobile_visitor_site(guard)
        if site_id and visitor.site_id.id != site_id:
            return request.redirect('/guardpro/mobile/visitors?error=invalid_visitor')
        if not site_id and visitor.guard_checkin_id.id != guard.id:
            return request.redirect('/guardpro/mobile/visitors?error=invalid_visitor')
        try:
            visitor.write({
                'state': 'checked_out',
                'checkout_time': fields.Datetime.now(),
                'guard_checkout_id': guard.id,
            })
            return request.redirect('/guardpro/mobile/visitors?success=checked_out')
        except Exception as exc:
            _logger.error('[GuardLink] Visitor checkout failed: %s', exc)
            return request.redirect('/guardpro/mobile/visitors?error=checkout_failed')

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
            _logger.critical(
                'PANIC pressed by user %s (%s) with no guard profile',
                request.env.user.id, request.env.user.name,
            )
            return request.redirect('/guardpro/mobile?success=panic_sent')
        
        # incident.report requires category_id and site_id
        Category = request.env['incident.category'].sudo()
        emergency_category = Category.search([
            '|', ('name', 'ilike', 'emergency'), ('name', 'ilike', 'panic'),
        ], limit=1)
        if not emergency_category:
            emergency_category = Category.search([], limit=1)
        if not emergency_category:
            try:
                emergency_category = Category.create({
                    'name': 'Emergency',
                    'code': 'EMERGENCY',
                })
            except Exception as cat_err:
                _logger.critical('PANIC: could not resolve/create category: %s', cat_err)
        
        # Resolve site safely: attendance → latest shift → assigned projects only.
        # Never fall back to an arbitrary site from the database.
        site_id = self._resolve_guard_operation_site_id(guard)
        allowed = self._guard_allowed_site_ids(guard)
        if not site_id or (allowed is not None and site_id not in allowed):
            _logger.critical(
                'PANIC blocked for guard %s (%s): no allowed site context',
                guard.id, guard.name,
            )
            return request.redirect('/guardpro/mobile?error=no_site')

        if not emergency_category:
            _logger.critical(
                'PANIC blocked for guard %s: no incident category available',
                guard.id,
            )
            return request.redirect('/guardpro/mobile?success=panic_sent')

        now = fields.Datetime.now()
        # Valid statuses: draft, submitted, under_review, investigating, resolved, closed
        vals = {
            'guard_id': guard.id,
            'site_id': site_id,
            'category_id': emergency_category.id,
            'severity': 'critical',
            'priority': '3',
            'title': 'PANIC ALERT',
            'description': '<p>Panic button activated by %s</p>' % guard.name,
            'incident_datetime': now,
            'reported_datetime': now,
            'status': 'submitted',
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
            incident = request.env['incident.report'].sudo().create(vals)
            _logger.critical(
                'PANIC ALERT created: %s by guard %s at site_id=%s lat=%s lon=%s',
                incident.name, guard.name, site_id, latitude, longitude,
            )
            try:
                incident.action_panic()
            except Exception as alert_err:
                _logger.error('Panic alert notification failed: %s', alert_err)
        except Exception as e:
            _logger.critical("Panic incident creation error: %s", str(e), exc_info=True)
        
        # Always show success for panic (guard must not see a failure UI in crisis)
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
        
        _logger.info('[GuardLink Mobile Shifts] Guard: %s, User TZ: %s, Today Start UTC: %s', 
                     guard.name, user_tz, today_start_utc)
        
        site_dom = self._mobile_site_domain('guard.shift')
        shifts_today = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_start_utc),
            ('start_datetime', '<', today_end_utc),
        ] + site_dom, order='start_datetime asc')
        
        upcoming_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '>=', today_end_utc),
        ] + site_dom, limit=10, order='start_datetime asc')
        
        past_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_datetime', '<', today_start_utc),
        ] + site_dom, limit=10, order='start_datetime desc')
        
        _logger.info('[GuardLink Mobile Shifts] Found %d today, %d upcoming, %d past shifts', 
                     len(shifts_today), len(upcoming_shifts), len(past_shifts))
        
        return self._mobile_render('guardpro.mobile_shifts', {
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
        tour_dom = self._mobile_site_domain('tour.log')
        active_tours = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', '=', 'in_progress'),
        ] + tour_dom, order='start_time desc')
        
        # Log tour progress for debugging
        for tour in active_tours:
            _logger.info('[Mobile Tours Page] Tour %s: %d/%d checkpoints scanned (%.1f%%), %d scan records',
                        tour.name, tour.scanned_checkpoints, tour.expected_checkpoints,
                        tour.completion_percentage, len(tour.scan_ids))
        
        # Get completed tour logs
        completed_tours = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'in', ['completed', 'incomplete']),
        ] + tour_dom, limit=10, order='end_time desc')
        
        # Get available checkpoints for current site
        active_attendance = request.env['guard.attendance'].sudo().search([
            ('guard_id', '=', guard.id),
            ('checkout_time', '=', False),
        ], limit=1, order='checkin_time desc')
        
        _logger.info('[Mobile Tours] ===== Checking shifts for guard %s (ID: %s) =====',
                     guard.name, guard.id)

        available_tours, relevant_shifts, current_shift = self._mobile_collect_available_tours(
            guard, active_tours, active_attendance
        )

        for shift in relevant_shifts:
            _logger.info(
                '[Mobile Tours] Shift: %s (ID: %s), Status: %s, Tours: %s',
                shift.name, shift.id, shift.status,
                ', '.join(shift.tour_ids.mapped('name')) or '(none)',
            )
        _logger.info(
            '[Mobile Tours] ===== END - %d available tour(s), current shift: %s =====',
            len(available_tours),
            current_shift.name if current_shift else 'none',
        )
        
        stale_active = active_tours.filtered(
            lambda log: self._mobile_tour_log_is_stale(log)
        )

        active_tour_scan_config = self._mobile_active_tour_scan_config(active_tours)

        response = self._mobile_render('guardpro.mobile_tours', {
            'guard': guard,
            'user': request.env.user,
            'active_tours': active_tours,
            'completed_tours': completed_tours,
            'available_tours': available_tours,
            'current_shift': current_shift,
            'is_checked_in': bool(active_attendance),
            'has_blocking_tour': bool(active_tours),
            'stale_active_tours': stale_active,
            'format_datetime_tz': self._format_datetime_tz,
            'mobile_tour_log_is_stale': self._mobile_tour_log_is_stale,
            'active_tour_scan_json': json.dumps(active_tour_scan_config)
            if active_tour_scan_config else 'null',
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
        task_dom = self._mobile_site_domain('guard.task')
        tasks_assigned = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'assigned'),
        ] + task_dom, order='priority desc, due_date asc')
        
        tasks_in_progress = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'in_progress'),
        ] + task_dom, order='priority desc, due_date asc')
        
        tasks_completed = request.env['guard.task'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('state', '=', 'completed'),
        ] + task_dom, limit=10, order='completed_date desc')

        return self._mobile_render('guardpro.mobile_tasks', {
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
        role = self._mobile_role(guard)
        if not guard and role not in ('supervisor', 'client'):
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        
        Incident = request.env['incident.report'].sudo()
        site_dom = self._mobile_site_domain('incident.report')
        reporter_domain = [('guard_id', '=', guard.id)] if guard else []

        open_incidents = Incident.search(
            Incident._domain_security_incidents(
                reporter_domain + [
                    ('status', 'in', ['submitted', 'under_review', 'investigating']),
                ] + site_dom
            ),
            limit=20,
            order='incident_datetime desc',
        )

        # Count total open for "X more" link without loading extra rows.
        open_incidents_total = Incident.search_count(
            Incident._domain_security_incidents(
                reporter_domain + [
                    ('status', 'in', ['submitted', 'under_review', 'investigating']),
                ] + site_dom
            )
        )

        recent_incidents = Incident.search(
            Incident._domain_security_incidents(
                reporter_domain + [
                    ('status', 'in', ['resolved', 'closed']),
                ] + site_dom
            ),
            limit=5,
            order='incident_datetime desc',
        )

        recent_incidents_total = Incident.search_count(
            Incident._domain_security_incidents(
                reporter_domain + [
                    ('status', 'in', ['resolved', 'closed']),
                ] + site_dom
            )
        )

        open_patrol_issues = Incident.search(
            Incident._domain_patrol_issues(
                reporter_domain + [
                    ('status', 'in', ['submitted', 'under_review', 'investigating']),
                ] + site_dom
            ),
            limit=15,
            order='incident_datetime desc',
        )

        recent_patrol_issues = Incident.search(
            Incident._domain_patrol_issues(
                reporter_domain + [
                    ('status', 'in', ['resolved', 'closed']),
                ] + site_dom
            ),
            limit=3,
            order='incident_datetime desc',
        )

        categories = request.env['incident.category'].sudo().search([
            ('hide_from_guard_incidents', '=', False),
        ], order='sequence, name')

        # form_parents are lazy-loaded via AJAX when the wizard opens —
        # only send slim metadata (id/name/code/category) so the initial
        # page render is fast. The full section/field HTML is fetched on demand.
        form_parents_meta = request.env['incident.form.parent'].sudo().search_read(
            [('active', '=', True)],
            fields=['id', 'name', 'code', 'category_id'],
            order='name, sequence',
        )

        # Get current site
        current_site = None
        if guard:
            active_attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1, order='checkin_time desc')
            current_site = active_attendance.site_id if active_attendance else None
        if not current_site and request.env.user.site_ids:
            current_site = request.env.user.site_ids[0]

        open_wizard = (
            kwargs.get('open_wizard')
            or request.httprequest.args.get('open_wizard')
        )

        return self._mobile_render('guardpro.mobile_incidents', {
            'guard': guard,
            'user': request.env.user,
            'mobile_role': role,
            'open_incidents': open_incidents,
            'open_incidents_total': open_incidents_total,
            'recent_incidents': recent_incidents,
            'recent_incidents_total': recent_incidents_total,
            'open_patrol_issues': open_patrol_issues,
            'recent_patrol_issues': recent_patrol_issues,
            'categories': categories,
            # form_parents ORM recordset kept for wizard_category_groups; not rendered directly
            'form_parents': request.env['incident.form.parent'].sudo().browse(
                [r['id'] for r in form_parents_meta]
            ),
            'form_parents_json': json.dumps([
                {
                    'id': r['id'],
                    'name': r['name'],
                    'code': r['code'],
                    'category_id': r['category_id'][0] if r.get('category_id') else False,
                }
                for r in form_parents_meta
            ]),
            'incident_categories_json': json.dumps([
                {'id': c.id, 'n': c.name, 'code': c.code}
                for c in categories
            ]),
            'wizard_category_groups': self._wizard_incident_category_groups(categories),
            'current_site': current_site,
            'format_datetime_tz': self._format_datetime_tz,
            'facility_issue_type_labels': dict(
                request.env['checkpoint.scan']._fields['facility_issue_type'].selection
            ),
            'open_wizard_type': open_wizard or False,
        })

    @http.route(
        '/guardpro/mobile/incident/form-parent/<int:parent_id>',
        type='http', auth='user', methods=['GET'], csrf=False,
    )
    def mobile_incident_form_parent_json(self, parent_id, **kwargs):
        """Lazy-load one Excel parent form definition (sections + fields)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.make_json_response({'ok': False, 'error': 'no_guard'}, status=403)
        parent = request.env['incident.form.parent'].sudo().browse(parent_id)
        if not parent.exists() or not parent.active:
            return request.make_json_response({'ok': False, 'error': 'not_found'}, status=404)
        # Prefetch children to avoid N+1
        sections = parent.section_ids
        fields = sections.mapped('field_ids')
        _ = fields  # ensure prefetch
        payload = {
            'ok': True,
            'parent': {
                'id': parent.id,
                'name': parent.name,
                'code': parent.code,
                'category_id': parent.category_id.id if parent.category_id else False,
                'sections': [
                    {
                        'id': sec.id,
                        'name': sec.name,
                        'fields': [
                            {
                                'id': fld.id,
                                'name': fld.name,
                                'field_type': fld.field_type,
                                'required': bool(fld.required),
                                'options': fld.get_selection_list(),
                                'hint': fld.get_field_hint(),
                            }
                            for fld in sec.field_ids
                        ],
                    }
                    for sec in sections
                ],
            },
        }
        return request.make_json_response(payload)

    @http.route('/guardpro/mobile/community-violation', type='http', auth='user', website=True)
    def mobile_community_violation(self, **kwargs):
        """Community Violation home module — list + report entry point."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        Incident = request.env['incident.report'].sudo()
        cv_codes = list(MOBILE_COMMUNITY_VIOLATION_CODES)
        open_reports = Incident.search(
            Incident._domain_security_incidents([
                ('guard_id', '=', guard.id),
                ('category_id.code', 'in', cv_codes),
                ('status', 'in', ['submitted', 'under_review', 'investigating', 'draft']),
            ]),
            order='incident_datetime desc',
            limit=80,
        )
        recent_reports = Incident.search(
            Incident._domain_security_incidents([
                ('guard_id', '=', guard.id),
                ('category_id.code', 'in', cv_codes),
                ('status', 'in', ['resolved', 'closed']),
            ]),
            order='incident_datetime desc',
            limit=50,
        )
        cv_categories = request.env['incident.category'].sudo().search([
            ('code', 'in', cv_codes),
            ('hide_from_guard_incidents', '=', False),
        ], order='name')
        return self._mobile_render('guardpro.mobile_community_violation', {
            'guard': guard,
            'user': request.env.user,
            'open_reports': open_reports,
            'recent_reports': recent_reports,
            'cv_categories': cv_categories,
            'format_datetime_tz': self._format_datetime_tz,
            'auto_open': bool(kwargs.get('open') or request.httprequest.args.get('open')),
        })

    @http.route('/guardpro/mobile/incident/create', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_incident_create(self, title=None, description=None, category_id=None, 
                               severity=None, latitude=None, longitude=None, **kwargs):
        """Create a new incident report."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.redirect('/guardpro/mobile/incidents?error=no_guard')

        wizard_type = (
            kwargs.get('wizard_type')
            or request.httprequest.form.get('wizard_type')
            or request.httprequest.values.get('wizard_type')
        )
        form_parent_id = (
            kwargs.get('form_parent_id')
            or request.httprequest.form.get('form_parent_id')
        )
        form_parent = False
        if form_parent_id:
            try:
                form_parent = request.env['incident.form.parent'].sudo().browse(int(form_parent_id))
                if not form_parent.exists():
                    form_parent = False
            except (TypeError, ValueError):
                form_parent = False

        # Title / "What happened" removed from mobile UI — auto-fill from category
        if not title:
            if form_parent:
                title = form_parent.name
            elif wizard_type:
                label_map = {
                    d['type']: d['label'] for d in MOBILE_INCIDENT_WIZARD_TYPE_DEFS
                }
                title = label_map.get(
                    wizard_type, wizard_type.replace('_', ' ').title()
                )
            else:
                title = 'Incident Report'
        if not description:
            description = title

        if not category_id:
            category_id = (
                request.httprequest.form.get('category_id')
                or request.httprequest.values.get('category_id')
            )
        if form_parent and form_parent.category_id and not category_id:
            category_id = form_parent.category_id.id
        category = self._resolve_mobile_incident_category(category_id, wizard_type, title=title)
        if form_parent and form_parent.category_id:
            category = form_parent.category_id
        if not category:
            _logger.warning(
                'Mobile incident create missing category (category_id=%s, wizard_type=%s, user=%s, form_keys=%s)',
                category_id, wizard_type, request.env.user.login,
                list(request.httprequest.form.keys()),
            )
            return request.redirect('/guardpro/mobile/incidents?error=missing_category')
        
        # Resolve site safely: attendance → latest shift → assigned projects only.
        # Never fall back to an arbitrary site from the database.
        site_id = self._resolve_guard_operation_site_id(guard)
        allowed = self._guard_allowed_site_ids(guard)
        if site_id and allowed is not None and site_id not in allowed:
            site_id = None

        if not site_id:
            return request.redirect('/guardpro/mobile/incidents?error=no_site')
        
        now = fields.Datetime.now()
        vals = {
            'guard_id': guard.id,
            'site_id': site_id,
            'title': title,
            'description': description,
            'severity': severity or 'medium',
            'category_id': category.id,
            'incident_datetime': now,
            'reported_datetime': now,
            'status': 'submitted',
        }
        if form_parent:
            vals['form_parent_id'] = form_parent.id
        self._mobile_stamp_site(vals)
        
        if 'location' in kwargs:
            vals['location'] = kwargs['location']

        # Type-specific fields from mobile wizard
        type_fields = {
            'persons_involved': kwargs.get('persons_involved'),
            'witnesses': kwargs.get('witnesses'),
            'immediate_actions': kwargs.get('immediate_actions'),
            'injury_details': kwargs.get('injury_details'),
            'damage_details': kwargs.get('damage_details'),
            'involved_community': kwargs.get('involved_community'),
            'involved_unit_number': kwargs.get('involved_unit_number'),
            'involved_parking_slot': kwargs.get('involved_parking_slot'),
        }
        for field_name, field_value in type_fields.items():
            if field_value:
                vals[field_name] = field_value

        for bool_field in ('police_notified', 'medical_required', 'ambulance_called',
                           'fire_department', 'injuries', 'property_damage'):
            if kwargs.get(bool_field) in ('on', 'true', '1', True):
                vals[bool_field] = True
        
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

            # Persist Excel-aligned dynamic form field values (+ media files)
            form_photos, form_videos = self._persist_incident_excel_form_values(incident)
            self._sync_excel_form_values_to_incident(incident)

            # Photos/Videos step uploads (merged with Excel form media)
            self._attach_incident_step_media(
                incident, photo_ids=form_photos, video_ids=form_videos,
            )

            # Auto-create supervisor approval request for high/critical incidents
            if vals.get('severity') in ('high', 'critical'):
                try:
                    request.env['guard.approval.request'].sudo().create({
                        'request_type': 'critical_incident',
                        'guard_id': guard.id,
                        'site_id': incident.site_id.id if incident.site_id else False,
                        'reference_model': 'incident.report',
                        'reference_id': incident.id,
                        'guard_notes': f"{vals.get('severity', '').title()} severity: {title}",
                    })
                except Exception as ae:
                    _logger.warning('Could not create approval request: %s', ae)

            return request.redirect(
                '/guardpro/mobile/incident/%s?success=incident_created' % incident.id
            )
        except Exception as e:
            _logger.error("Incident creation error: %s", str(e), exc_info=True)
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

        if incident.is_facility_patrol and kwargs.get('error') == 'update_failed':
            return request.redirect(
                f'/guardpro/mobile/incident/{incident_id}?error=patrol_readonly'
            )
        
        categories = request.env['incident.category'].sudo().search([
            ('hide_from_guard_incidents', '=', False),
        ])
        # Only show categories for this incident's wizard type — avoid dumping
        # every guard-visible category after submission.
        wizard_type = self._wizard_type_for_category_code(
            incident.category_id.code if incident.category_id else ''
        )
        categories = self._categories_for_wizard_type(wizard_type, categories)
        # Only sites the guard may access (never dump all client.site names).
        allowed = self._guard_allowed_site_ids(guard)
        Site = request.env['client.site'].sudo()
        if allowed is None:
            sites = Site.search([])
        elif allowed:
            sites = Site.browse(list(allowed))
        else:
            sites = Site.browse()
        # Always include the incident's own site if set (display), even if
        # assignments changed after the report was filed.
        if incident.site_id and incident.site_id not in sites:
            sites |= incident.site_id
        facility_issue_type_labels = dict(
            request.env['checkpoint.scan']._fields['facility_issue_type'].selection
        )

        return self._mobile_render('guardpro.mobile_incident_detail', {
            'guard': guard,
            'user': request.env.user,
            'incident': incident,
            'is_patrol_issue': incident.is_facility_patrol,
            'categories': categories,
            'wizard_type': wizard_type,
            'sites': sites,
            'format_datetime_tz': self._format_datetime_tz,
            'facility_issue_type_labels': facility_issue_type_labels,
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

        if incident.is_facility_patrol:
            return request.redirect(
                f'/guardpro/mobile/incident/{incident_id}?error=patrol_readonly'
            )
        
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
            if 'involved_community' in kwargs:
                vals['involved_community'] = kwargs['involved_community']
            if 'involved_unit_number' in kwargs:
                vals['involved_unit_number'] = kwargs['involved_unit_number']
            if 'involved_parking_slot' in kwargs:
                vals['involved_parking_slot'] = kwargs['involved_parking_slot']
            
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
            
            # Excel form media (e.g. Community Violation "Violation Picture")
            # plus Photos/Videos step uploads
            form_photos, form_videos = self._persist_incident_excel_form_values(
                incident, media_only=True,
            )
            self._attach_incident_step_media(
                incident, photo_ids=form_photos, video_ids=form_videos,
            )
            
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
            'name': 'GuardLink Mobile',
            'short_name': 'GuardLink',
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
    def mobile_profile(self, tab='overview', **kwargs):
        """Mobile profile page — tabbed: Overview / Training / Performance."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        # Credentials (sorted by expiry asc so expiring first)
        credentials = request.env['guard.credential'].sudo().search([
            ('guard_id', '=', guard.id),
            ('active', '=', True),
        ], order='expiry_date asc')

        # Training history
        trainings = request.env['guard.training'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='date desc', limit=20)

        # Latest performance review
        latest_review = request.env['guard.performance.review'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='period_end desc', limit=1)

        # Badges
        badges = request.env['guard.performance.badge'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='earned_date desc', limit=6)

        today = fields.Date.today()
        expiring_soon = credentials.filtered(
            lambda c: c.expiry_date and (c.expiry_date - today).days <= 30
                      and c.state not in ('expired',)
        )

        return self._mobile_render('guardpro.mobile_profile_template', {
            'guard': guard,
            'user': request.env.user,
            'active_tab': tab,
            'credentials': credentials,
            'trainings': trainings,
            'latest_review': latest_review,
            'badges': badges,
            'expiring_soon': expiring_soon,
            'today': today,
        })
    
    @http.route('/guardpro/mobile/site_info', type='http', auth='user', website=True)
    def mobile_site_info(self, **kwargs):
        """Mobile site info page."""
        guard = self._get_guard_from_user()
        
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
            
        try:
            ctx = request.env.user.guardpro_ensure_mobile_context()
            site = None
            physical_site = None
            if ctx and ctx['type'] == 'site':
                physical_site = request.env['guard.site'].sudo().browse(ctx['id'])
                site = physical_site.project_id if physical_site.exists() else None
            elif ctx and ctx['type'] == 'project':
                site = request.env['client.site'].sudo().browse(ctx['id'])
            if not site or not site.exists():
                site = guard.current_site_id if guard else None
            
            # Fallback: If no site on profile, check active attendance
            if not site and guard:
                active_attendance = request.env['guard.attendance'].sudo().search([
                    ('guard_id', '=', guard.id),
                    ('checkout_time', '=', False),
                ], limit=1, order='checkin_time desc')
                if active_attendance:
                    site = active_attendance.site_id
                    _logger.info('[GuardLink Mobile] Found site from active attendance: %s', site.name)
            
            # Second Fallback: Check most recent shift
            if not site and guard:
                recent_shift = request.env['guard.shift'].sudo().search([
                    ('guard_id', '=', guard.id),
                ], limit=1, order='start_datetime desc')
                if recent_shift:
                    site = recent_shift.site_id
                    _logger.info('[GuardLink Mobile] Found site from recent shift: %s', site.name)

            return self._mobile_render('guardpro.mobile_site_info_template', {
                'guard': guard,
                'site': site,
                'physical_site': physical_site,
                'format_datetime_tz': self._format_datetime_tz,
            })
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            _logger.error('[GuardLink Mobile] Error in mobile_site_info: %s\n%s', str(e), error_trace)
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

        return self._mobile_render('guardpro.mobile_emergency_template', {
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
        
        return self._mobile_render('guardpro.mobile_settings', {
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
        role = self._mobile_role(guard)
        show_compliance = self._user_can_access_mobile_compliance(user)
        if not guard and role not in ('supervisor', 'client') and not show_compliance:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return self._mobile_render('guardpro.mobile_more', {
            'guard': guard,
            'user': user,
            'mobile_role': role,
            'show_compliance_audits': show_compliance,
        })

    @http.route('/guardpro/mobile/messages', type='http', auth='user', website=True)
    def mobile_messages(self, **kwargs):
        """WhatsApp-style inbox: direct chats and team channels."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return self._mobile_render('guardpro.mobile_messages', {
            'guard': guard,
            'user': request.env.user,
        })

    @http.route('/guardpro/mobile/messages/new', type='http', auth='user', website=True)
    def mobile_messages_new(self, **kwargs):
        """Start a new direct chat (supervisor or guard)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return self._mobile_render('guardpro.mobile_messages_new', {
            'guard': guard,
            'user': request.env.user,
        })

    @http.route('/guardpro/mobile/messages/chat/<int:conversation_id>', type='http', auth='user', website=True)
    def mobile_messages_chat(self, conversation_id, **kwargs):
        """Direct / 1:1 conversation thread."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())
        return self._mobile_render('guardpro.mobile_messages_chat', {
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
        return self._mobile_render('guardpro.mobile_messages_channel', {
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
        return self._mobile_render('guardpro.mobile_compliance_list', {
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
        return self._mobile_render('guardpro.mobile_compliance_detail', {
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
                validated = validate_werkzeug_file(
                    uploaded, allow_video=False, allow_image=True
                )
                datas_b64 = base64.b64encode(validated['data']).decode()
                try:
                    optimized = ImageOptimizer.optimize_image(
                        datas_b64,
                        max_dimension=1200,
                        target_format='JPEG',
                    )
                    if optimized:
                        if isinstance(optimized, bytes):
                            optimized = optimized.decode('ascii')
                        datas_b64 = optimized
                except Exception as opt_err:
                    _logger.debug('[Mobile Compliance] Photo optimize skipped: %s', opt_err)
                att = request.env['ir.attachment'].sudo().create({
                    'name': validated['filename'] or 'audit_evidence.jpg',
                    'type': 'binary',
                    'datas': datas_b64,
                    'res_model': 'compliance.audit.item',
                    'res_id': item.id,
                    'mimetype': validated['mimetype'] or 'image/jpeg',
                })
                vals['photo_ids'] = [(4, att.id)]
            except UploadValidationError as e:
                _logger.warning('[Mobile Compliance] Photo rejected: %s', e)
                return request.redirect(
                    '/guardpro/mobile/compliance/%s?error=audit_photo_failed' % audit.id
                )
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

    # ── Equipment ─────────────────────────────────────────────────────────────

    @http.route('/guardpro/mobile/equipment', type='http', auth='user', website=True)
    def mobile_equipment(self, **kwargs):
        """Equipment assigned to this guard."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        equipment = request.env['guardpro.equipment'].sudo().search([
            ('assigned_to', '=', guard.id),
            ('status', 'not in', ['decommissioned']),
        ], order='category, name')

        # Other guards at same site for handover target
        site = guard.site_ids[:1] if guard.site_ids else None
        other_guards = request.env['guard.profile'].sudo().search([
            ('id', '!=', guard.id),
            ('site_ids', 'in', site.ids if site else []),
        ], order='name', limit=30) if site else request.env['guard.profile'].sudo().browse([])

        error = kwargs.get('error')
        success = kwargs.get('success')
        return self._mobile_render('guardpro.mobile_equipment', {
            'guard': guard,
            'user': request.env.user,
            'equipment': equipment,
            'other_guards': other_guards,
            'error': error,
            'success': success,
        })

    @http.route('/guardpro/mobile/equipment/handover', type='http', auth='user',
                methods=['POST'], csrf=True)
    def mobile_equipment_handover(self, equipment_id=None, to_guard_id=None,
                                   condition=None, notes=None, **kwargs):
        """Create an equipment handover record."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        if not equipment_id:
            return request.redirect('/guardpro/mobile/equipment?error=missing_equipment')
        try:
            eq = request.env['guardpro.equipment'].sudo().browse(int(equipment_id))
            if not eq.exists() or eq.assigned_to.id != guard.id:
                return request.redirect('/guardpro/mobile/equipment?error=not_yours')
            vals = {
                'equipment_id': eq.id,
                'from_guard_id': guard.id,
                'handover_datetime': fields.Datetime.now(),
                'condition_at_handover': condition or 'good',
                'procedure_ack': True,
            }
            if to_guard_id:
                to_guard = request.env['guard.profile'].sudo().browse(int(to_guard_id))
                if not to_guard.exists():
                    return request.redirect('/guardpro/mobile/equipment?error=handover_failed')
                # Same-site handover only (fail closed if either side has no sites)
                sender_sites = set(guard.site_ids.ids)
                receiver_sites = set(to_guard.site_ids.ids)
                if not sender_sites or not receiver_sites or not (sender_sites & receiver_sites):
                    return request.redirect('/guardpro/mobile/equipment?error=handover_failed')
                vals['to_guard_id'] = to_guard.id
            if notes:
                vals['notes'] = notes
            request.env['equipment.handover'].sudo().create(vals)
            return request.redirect('/guardpro/mobile/equipment?success=handover_created')
        except Exception as exc:
            _logger.error('[GuardLink] Equipment handover failed: %s', exc)
            return request.redirect('/guardpro/mobile/equipment?error=handover_failed')

    # ── Keys & Packages ───────────────────────────────────────────────────────

    @http.route('/guardpro/mobile/keys-packages', type='http', auth='user', website=True)
    def mobile_keys_packages(self, tab='keys', **kwargs):
        """Combined keys and packages hub."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        allowed = self._guard_allowed_site_ids(guard)
        site = guard.site_ids[:1] if guard.site_ids else None
        Key = request.env['key.register'].sudo()
        Txn = request.env['key.transaction'].sudo()
        Pkg = request.env['package.management'].sudo()

        if allowed is not None and not allowed:
            keys_available = Key.browse([])
            keys_issued = Txn.browse([])
            packages_pending = Pkg.browse([])
            packages_recent = Pkg.browse([])
        else:
            project_domain = (
                [] if allowed is None else [('site_id', 'in', list(allowed))]
            )
            keys_available = Key.search(
                project_domain + self._mobile_site_domain('key.register') + [('status', '=', 'available')],
                order='name', limit=50
            )
            key_txn_domain = [('state', '=', 'active')]
            if allowed is not None:
                key_txn_domain.append(('key_id.site_id', 'in', list(allowed)))
            key_txn_domain += self._mobile_site_domain(
                'key.transaction',
                project_field='key_id.site_id',
                guard_site_field='key_id.guard_site_id',
            )
            keys_issued = Txn.search(key_txn_domain, order='issue_date desc', limit=50)
            pkg_domain = project_domain + self._mobile_site_domain('package.management')
            packages_pending = Pkg.search(
                pkg_domain + [('state', 'in', ['received', 'notified'])],
                order='received_date desc', limit=50
            )
            packages_recent = Pkg.search(
                pkg_domain + [('state', 'in', ['collected', 'returned'])],
                order='received_date desc', limit=20
            )

        # Package types for the log form
        pkg_types = request.env['package.management'].sudo().fields_get(
            ['package_type'])['package_type']['selection']

        # Key transaction issued_to_type list
        issuee_types = request.env['key.transaction'].sudo().fields_get(
            ['issued_to_type'])['issued_to_type']['selection']

        error = kwargs.get('error')
        success = kwargs.get('success')
        return self._mobile_render('guardpro.mobile_keys_packages', {
            'guard': guard,
            'user': request.env.user,
            'site': site,
            'keys_available': keys_available,
            'keys_issued': keys_issued,
            'packages_pending': packages_pending,
            'packages_recent': packages_recent,
            'pkg_types': pkg_types,
            'issuee_types': issuee_types,
            'active_tab': tab,
            'error': error,
            'success': success,
        })

    @http.route('/guardpro/mobile/keys-packages/key/issue', type='http', auth='user',
                methods=['POST'], csrf=True)
    def mobile_key_issue(self, key_id=None, issued_to_name=None, issued_to_type='staff',
                          issued_to_phone=None, **kwargs):
        """Issue a key to someone (assigned projects only)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        if not key_id or not issued_to_name:
            return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=missing_fields')
        try:
            key = request.env['key.register'].sudo().browse(int(key_id))
            if not key.exists() or key.status != 'available':
                return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=key_unavailable')
            if not self._site_allowed_for_guard(guard, key.site_id.id if key.site_id else False):
                return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=key_unavailable')
            txn_vals = {
                'key_id': key.id,
                'issued_to_name': issued_to_name.strip(),
                'issued_to_type': issued_to_type or 'employee',
                'issue_date': fields.Datetime.now(),
                'state': 'active',
            }
            if issued_to_phone:
                txn_vals['issued_to_phone'] = issued_to_phone.strip()
            request.env['key.transaction'].sudo().create(txn_vals)
            return request.redirect('/guardpro/mobile/keys-packages?tab=keys&success=key_issued')
        except Exception as exc:
            _logger.error('[GuardLink] Key issue failed: %s', exc)
            return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=issue_failed')

    @http.route('/guardpro/mobile/keys-packages/key/return/<int:txn_id>', type='http',
                auth='user', methods=['POST'], csrf=True)
    def mobile_key_return(self, txn_id, **kwargs):
        """Return a key (assigned projects only)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        try:
            txn = request.env['key.transaction'].sudo().browse(txn_id)
            if not txn.exists() or txn.state != 'active':
                return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=invalid_transaction')
            site_id = txn.key_id.site_id.id if txn.key_id and txn.key_id.site_id else False
            if not self._site_allowed_for_guard(guard, site_id):
                return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=invalid_transaction')
            txn.write({
                'return_date': fields.Datetime.now(),
                'returned_to': guard.id,
                'state': 'returned',
            })
            return request.redirect('/guardpro/mobile/keys-packages?tab=keys&success=key_returned')
        except Exception as exc:
            _logger.error('[GuardLink] Key return failed: %s', exc)
            return request.redirect('/guardpro/mobile/keys-packages?tab=keys&error=return_failed')

    @http.route('/guardpro/mobile/keys-packages/package/log', type='http', auth='user',
                methods=['POST'], csrf=True)
    def mobile_package_log(self, package_type='parcel', recipient_name=None,
                            sender_name=None, tracking_number=None, **kwargs):
        """Log a received package."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        if not recipient_name:
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=missing_fields')
        site = guard.site_ids[:1] if guard.site_ids else None
        if not site:
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=no_site')
        try:
            vals = {
                'package_type': package_type or 'parcel',
                'recipient_name': recipient_name.strip(),
                'site_id': site.id,
                'received_by': guard.id,
                'received_date': fields.Datetime.now(),
                'state': 'received',
            }
            self._mobile_stamp_site(vals)
            if sender_name:
                vals['sender_name'] = sender_name.strip()
            if tracking_number:
                vals['tracking_number'] = tracking_number.strip()

            photo = kwargs.get('package_photo') or request.httprequest.files.get('package_photo')
            if photo and hasattr(photo, 'read'):
                try:
                    validated = validate_werkzeug_file(
                        photo, allow_video=False, allow_image=True
                    )
                    optimized = ImageOptimizer.optimize_for_mobile(validated['data'])
                    vals['package_photo'] = base64.b64encode(optimized).decode('utf-8')
                except UploadValidationError as exc:
                    _logger.warning('[GuardLink] Package photo rejected: %s', exc)
                    return request.redirect(
                        '/guardpro/mobile/keys-packages?tab=packages&error=invalid_photo'
                    )
                except Exception as exc:
                    _logger.warning('[GuardLink] Package photo error: %s', exc)

            request.env['package.management'].sudo().create(vals)
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&success=package_logged')
        except Exception as exc:
            _logger.error('[GuardLink] Package log failed: %s', exc)
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=log_failed')

    @http.route('/guardpro/mobile/keys-packages/package/collect/<int:pkg_id>', type='http',
                auth='user', methods=['POST'], csrf=True)
    def mobile_package_collect(self, pkg_id, **kwargs):
        """Mark package as collected (assigned projects only)."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        try:
            pkg = request.env['package.management'].sudo().browse(pkg_id)
            if not pkg.exists() or pkg.state not in ('received', 'notified'):
                return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=invalid_package')
            if not self._site_allowed_for_guard(guard, pkg.site_id.id if pkg.site_id else False):
                return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=invalid_package')
            pkg.write({
                'state': 'collected',
                'handed_over_by': guard.id,
            })
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&success=package_collected')
        except Exception as exc:
            _logger.error('[GuardLink] Package collect failed: %s', exc)
            return request.redirect('/guardpro/mobile/keys-packages?tab=packages&error=collect_failed')

    # ── Lost & Found ──────────────────────────────────────────────────────────

    @http.route('/guardpro/mobile/lost-found', type='http', auth='user', website=True)
    def mobile_lost_found(self, **kwargs):
        """Lost & Found — list items and log new ones."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        error = kwargs.get('error')
        success = kwargs.get('success')
        item_id = kwargs.get('item_id')

        today_start, _today_end, now = self._mobile_today_utc_range()
        thirty_days_ago = now - timedelta(days=30)

        # Primary site for this guard
        site = guard.site_ids[:1] if guard.site_ids else None

        # Items logged by this guard OR from their site in the last 30 days
        LF = request.env['lost.found.item'].sudo()
        domain = [('found_date', '>=', thirty_days_ago)]
        if site:
            domain += ['|', ('guard_logged_by', '=', guard.id), ('site_id', '=', site.id)]
        else:
            domain += [('guard_logged_by', '=', guard.id)]
        domain += self._mobile_site_domain('lost.found.item')
        items = LF.search(domain, limit=50, order='found_date desc')

        today_items_count = sum(1 for i in items if i.found_date and i.found_date >= today_start)

        # Build category list from model selection field
        categories = LF.fields_get(['item_category'])['item_category']['selection']

        return self._mobile_render('guardpro.mobile_lost_found', {
            'guard': guard,
            'user': request.env.user,
            'items': items,
            'today_items_count': today_items_count,
            'categories': categories,
            'site': site,
            'error': error,
            'success': success,
            'new_item_id': int(item_id) if item_id else None,
        })

    @http.route('/guardpro/mobile/lost-found/log', type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_lost_found_log(self, item_category=None, description=None, location_found=None,
                               found_by=None, **kwargs):
        """Create a new lost & found record from mobile."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')

        if not item_category or not description or not location_found:
            return request.redirect('/guardpro/mobile/lost-found?error=missing_fields')

        site = guard.site_ids[:1] if guard.site_ids else None
        if not site:
            return request.redirect('/guardpro/mobile/lost-found?error=no_site')

        now = fields.Datetime.now()
        vals = {
            'item_category': item_category,
            'description': description,
            'location_found': location_found,
            'site_id': site.id,
            'guard_logged_by': guard.id,
            'found_date': now,
            'storage_date': now,
        }
        self._mobile_stamp_site(vals)
        if found_by and found_by.strip():
            vals['found_by'] = found_by.strip()

        # Handle optional photo upload (images only, size-capped)
        photo = kwargs.get('photo_1') or request.httprequest.files.get('photo_1')
        if photo and hasattr(photo, 'read'):
            try:
                validated = validate_werkzeug_file(
                    photo, allow_video=False, allow_image=True
                )
                optimized = ImageOptimizer.optimize_for_mobile(validated['data'])
                vals['photo_1'] = base64.b64encode(optimized).decode('utf-8')
            except UploadValidationError as exc:
                _logger.warning('[GuardLink] Lost & Found photo rejected: %s', exc)
                return request.redirect('/guardpro/mobile/lost-found?error=invalid_photo')
            except Exception as exc:
                _logger.warning('[GuardLink] Lost & Found photo upload error: %s', exc)

        try:
            item = request.env['lost.found.item'].sudo().create(vals)
            _logger.info('[GuardLink] Lost & Found item %s created by guard %s', item.name, guard.name)
            return request.redirect(
                '/guardpro/mobile/lost-found?success=item_logged&item_id=%s' % item.id
            )
        except Exception as exc:
            _logger.error('[GuardLink] Lost & Found creation failed: %s', exc)
            return request.redirect('/guardpro/mobile/lost-found?error=create_failed')

    # ── Training ───────────────────────────────────────────────────────────────

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
// GuardLink Mobile - Minimal Service Worker (Odoo 18)
const CACHE_VERSION = 'v2.0.31';
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

// Fetch event - Network first, then cache (skip file downloads)
self.addEventListener('fetch', (event) => {
    const url = event.request.url || '';
    if (url.indexOf('/guardpro/mobile/visitors/export') !== -1) {
        return;
    }
    // Never cache HTML app pages — site switcher must always hit the server
    if (event.request.mode === 'navigate' || url.indexOf('/guardpro/mobile') !== -1) {
        event.respondWith(fetch(event.request));
        return;
    }
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

    # ── Tour Completion Summary ───────────────────────────────────────────────

    @http.route('/guardpro/mobile/tours/summary/<int:tour_log_id>',
                type='http', auth='user', website=True)
    def mobile_tour_summary(self, tour_log_id, **kwargs):
        """Full-screen summary shown after a patrol is completed."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        tour_log = request.env['tour.log'].sudo().browse(tour_log_id)
        if not tour_log.exists() or tour_log.guard_id.id != guard.id:
            return request.redirect('/guardpro/mobile/tours')

        # Checkpoint scans for this log
        scans = tour_log.scan_ids.sorted('scan_time')

        # Patrol issues / incidents raised during this tour
        patrol_issues = request.env['incident.report'].sudo().search([
            ('tour_log_id', '=', tour_log_id),
        ], order='incident_datetime', limit=20)

        # Duration formatted
        duration_h = int(tour_log.duration or 0)
        duration_m = int(round(((tour_log.duration or 0) - duration_h) * 60))

        # Completion pct
        total = tour_log.expected_checkpoints or 0
        scanned = tour_log.scanned_checkpoints or 0
        pct = int((scanned / total * 100) if total else 100)

        return self._mobile_render('guardpro.mobile_tour_summary', {
            'guard': guard,
            'user': request.env.user,
            'tour_log': tour_log,
            'scans': scans,
            'patrol_issues': patrol_issues,
            'duration_h': duration_h,
            'duration_m': duration_m,
            'pct': pct,
        })

    # ── Notification Centre ───────────────────────────────────────────────────

    @http.route('/guardpro/mobile/notifications', type='http', auth='user', website=True)
    def mobile_notifications(self, **kwargs):
        """Aggregated notification inbox."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        today = fields.Date.today()
        now = fields.Datetime.now()

        # ── Push notifications (unacked, not expired) ──
        push_items = request.env['guardpro.mobile.outbox'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('acked', '=', False),
            '|', ('expiry_date', '=', False), ('expiry_date', '>', now),
        ], order='create_date desc', limit=30)

        # ── Geofence alerts for this guard (new/pending) ──
        geofence_alerts = request.env['geofence.alert'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', 'in', ['new', 'pending']),
        ], order='alert_datetime desc', limit=20)

        # ── Credentials expiring within 60 days ──
        cred_alerts = request.env['guard.credential'].sudo().search([
            ('guard_id', '=', guard.id),
            ('active', '=', True),
            ('expiry_date', '!=', False),
            ('state', 'not in', ['expired']),
        ]).filtered(lambda c: c.expiry_date and (c.expiry_date - today).days <= 60)

        # ── Upcoming shifts (next 48 hours) ──
        window_48h = fields.Datetime.add(now, hours=48)
        upcoming_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
            ('status', '=', 'scheduled'),
            ('start_datetime', '>=', now),
            ('start_datetime', '<=', window_48h),
        ], order='start_datetime asc', limit=5)

        # ── Unread guard messages ──
        unread_messages = request.env['guard.message'].sudo().search([
            ('receiver_id', '=', guard.id),
            ('is_read', '=', False),
        ], order='created_at desc', limit=20)

        total_unread = (len(push_items) + len(geofence_alerts) +
                        len(cred_alerts) + len(unread_messages))

        return self._mobile_render('guardpro.mobile_notifications', {
            'guard': guard,
            'user': request.env.user,
            'push_items': push_items,
            'geofence_alerts': geofence_alerts,
            'cred_alerts': cred_alerts,
            'upcoming_shifts': upcoming_shifts,
            'unread_messages': unread_messages,
            'total_unread': total_unread,
            'success': kwargs.get('success'),
        })

    @http.route('/guardpro/mobile/notifications/ack/<int:notif_id>',
                type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_notifications_ack(self, notif_id, **kwargs):
        """Acknowledge a push notification."""
        try:
            item = request.env['guardpro.mobile.outbox'].sudo().browse(notif_id)
            if item.exists() and item.user_id.id == request.env.user.id:
                item.write({'acked': True, 'acked_on': fields.Datetime.now()})
        except Exception as exc:
            _logger.error('[GuardLink] Notification ack failed: %s', exc)
        return request.redirect('/guardpro/mobile/notifications?success=acked')

    @http.route('/guardpro/mobile/notifications/ack-geofence/<int:alert_id>',
                type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_notifications_ack_geofence(self, alert_id, **kwargs):
        """Acknowledge a geofence alert."""
        guard = self._get_guard_from_user()
        try:
            alert = request.env['geofence.alert'].sudo().browse(alert_id)
            if alert.exists() and alert.guard_id.id == (guard.id if guard else -1):
                alert.write({
                    'status': 'acknowledged',
                    'acknowledged_by': request.env.user.id,
                    'acknowledged_date': fields.Datetime.now(),
                })
        except Exception as exc:
            _logger.error('[GuardLink] Geofence ack failed: %s', exc)
        return request.redirect('/guardpro/mobile/notifications?success=acked')

    # ── Supervisor Approval Workflow ──────────────────────────────────────────

    def _approval_supervisor_domain(self, user, extra_domain=None):
        """Domain limiting approvals to the caller's assigned projects (admins unrestricted)."""
        domain = list(extra_domain or [])
        if user.has_group('guardpro.group_guardpro_admin'):
            return domain
        site_ids = user.site_ids.ids
        if not site_ids:
            return domain + [('id', '=', False)]
        # Prefer stored site_id; also include legacy rows via guard site overlap
        return domain + [
            '|',
            ('site_id', 'in', site_ids),
            '&',
            ('site_id', '=', False),
            ('guard_id.site_ids', 'in', site_ids),
        ]

    @http.route('/guardpro/mobile/approvals', type='http', auth='user', website=True)
    def mobile_approvals(self, **kwargs):
        """Supervisor approval queue — partial tours and critical incidents."""
        user = request.env.user
        is_supervisor = (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        )
        guard = self._get_guard_from_user()
        Approval = request.env['guard.approval.request'].sudo()

        if is_supervisor:
            pending = Approval.search(
                self._approval_supervisor_domain(user, [('state', '=', 'pending')]),
                order='request_date asc',
                limit=50,
            )
            resolved = Approval.search(
                self._approval_supervisor_domain(
                    user, [('state', 'in', ('approved', 'rejected'))]
                ),
                order='resolve_date desc',
                limit=20,
            )
        else:
            # Guards see their own requests only
            pending, resolved = Approval.browse([]), Approval.browse([])
            if guard:
                pending = Approval.search(
                    [('guard_id', '=', guard.id), ('state', '=', 'pending')],
                    order='request_date asc',
                )
                resolved = Approval.search(
                    [('guard_id', '=', guard.id), ('state', 'in', ('approved', 'rejected'))],
                    order='resolve_date desc',
                    limit=10,
                )

        return self._mobile_render('guardpro.mobile_approvals', {
            'guard': guard,
            'user': user,
            'is_supervisor': is_supervisor,
            'pending': pending,
            'resolved': resolved,
        })

    @http.route('/guardpro/mobile/approvals/<int:req_id>/resolve',
                type='http', auth='user', methods=['POST'], csrf=True, website=True)
    def mobile_approval_resolve(self, req_id, action=None, supervisor_notes=None, **kwargs):
        """Approve or reject an approval request (assigned projects only)."""
        user = request.env.user
        is_supervisor = (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        )
        if not is_supervisor:
            return request.redirect('/guardpro/mobile/approvals?error=not_authorized')

        req = request.env['guard.approval.request'].sudo().browse(req_id)
        if not req.exists() or req.state != 'pending':
            return request.redirect('/guardpro/mobile/approvals?error=not_found')

        if not req.user_has_site_access(user):
            return request.redirect('/guardpro/mobile/approvals?error=not_authorized')

        try:
            if action == 'approve':
                req.action_approve(supervisor_notes=supervisor_notes)
            else:
                if not supervisor_notes:
                    return request.redirect(
                        f'/guardpro/mobile/approvals?error=rejection_requires_reason&req={req_id}')
                req.action_reject(supervisor_notes=supervisor_notes)
            return request.redirect('/guardpro/mobile/approvals?success=resolved')
        except Exception as e:
            _logger.error('[GuardLink] Approval resolve error: %s', e)
            return request.redirect('/guardpro/mobile/approvals?error=resolve_failed')

    # ── End-of-Shift Summary ──────────────────────────────────────────────────

    @http.route('/guardpro/mobile/shift-summary', type='http', auth='user', website=True)
    def mobile_shift_summary(self, **kwargs):
        """End-of-shift summary — stats for the guard's latest shift."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        # Most recent shift (any status), fallback to today
        shift = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='start_datetime desc', limit=1)

        site = guard.site_ids[:1] if guard.site_ids else None

        # Determine window for stats
        if shift:
            window_start = shift.start_datetime or shift.create_date
            window_end = shift.end_datetime or fields.Datetime.now()
        else:
            # Fallback: today UTC
            today = fields.Date.today()
            window_start = fields.Datetime.from_string('%s 00:00:00' % today)
            window_end = fields.Datetime.now()

        # ── Tour stats ────
        tour_logs = request.env['tour.log'].sudo().search([
            ('guard_id', '=', guard.id),
            ('start_time', '>=', window_start),
            ('start_time', '<=', window_end),
        ])
        tours_done = len(tour_logs.filtered(lambda t: t.status == 'completed'))
        tours_total = len(tour_logs)
        total_checkpoints = sum(tour_logs.mapped('scanned_checkpoints'))

        # ── Incidents ────
        inc_domain = [
            ('guard_id', '=', guard.id),
            ('incident_datetime', '>=', window_start),
            ('incident_datetime', '<=', window_end),
        ]
        incidents = request.env['incident.report'].sudo().search(inc_domain)

        # ── Visitors ────
        vis_domain = [('checkin_time', '>=', window_start), ('checkin_time', '<=', window_end)]
        if site:
            vis_domain.append(('site_id', '=', site.id))
        visitors_in = request.env['visitor.management'].sudo().search_count(vis_domain)
        visitors_out = request.env['visitor.management'].sudo().search_count(
            vis_domain + [('state', '=', 'checked_out')]
        )

        # ── Packages ────
        pkg_domain = [('received_date', '>=', window_start), ('received_date', '<=', window_end)]
        if site:
            pkg_domain.append(('site_id', '=', site.id))
        pkg_count = request.env['package.management'].sudo().search_count(pkg_domain)

        # ── Lost & Found ────
        lf_domain = [('found_date', '>=', window_start), ('found_date', '<=', window_end)]
        if site:
            lf_domain.append(('site_id', '=', site.id))
        lf_count = request.env['lost.found.item'].sudo().search_count(lf_domain)

        return self._mobile_render('guardpro.mobile_shift_summary', {
            'guard': guard,
            'user': request.env.user,
            'shift': shift,
            'window_start': window_start,
            'window_end': window_end,
            'tours_done': tours_done,
            'tours_total': tours_total,
            'total_checkpoints': total_checkpoints,
            'incidents': incidents,
            'visitors_in': visitors_in,
            'visitors_out': visitors_out,
            'pkg_count': pkg_count,
            'lf_count': lf_count,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })

    @http.route('/guardpro/mobile/shift-summary/handover-note',
                type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_shift_handover_note(self, handover_note=None, shift_id=None, **kwargs):
        """Save handover note to the shift record."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        try:
            note = (handover_note or '').strip()
            if shift_id:
                shift = request.env['guard.shift'].sudo().browse(int(shift_id))
                if shift.exists() and shift.guard_id.id == guard.id:
                    shift.write({'notes': note})
            return request.redirect('/guardpro/mobile/shift-summary?success=note_saved')
        except Exception as exc:
            _logger.error('[GuardLink] Shift handover note failed: %s', exc)
            return request.redirect('/guardpro/mobile/shift-summary?error=save_failed')

    # ── My Performance Dashboard ──────────────────────────────────────────────

    @http.route('/guardpro/mobile/performance', type='http', auth='user', website=True)
    def mobile_performance(self, **kwargs):
        """Guard's own performance dashboard."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        # Latest review
        reviews = request.env['guard.performance.review'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='period_end desc', limit=6)

        latest = reviews[:1] if reviews else request.env['guard.performance.review'].sudo().browse([])

        # Badges
        badges = request.env['guard.performance.badge'].sudo().search([
            ('guard_id', '=', guard.id),
        ], order='earned_date desc', limit=12)

        # Quick stats from all reviews (trend data — oldest first for display)
        trend = list(reversed(reviews))

        return self._mobile_render('guardpro.mobile_performance', {
            'guard': guard,
            'user': request.env.user,
            'latest': latest,
            'reviews': reviews,
            'badges': badges,
            'trend': trend,
        })

    # ── Knowledge Base / SOPs ─────────────────────────────────────────────────

    @http.route('/guardpro/mobile/knowledge', type='http', auth='user', website=True)
    def mobile_knowledge(self, tab='articles', search='', **kwargs):
        """Knowledge base — articles and SOPs."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        site = guard.site_ids[:1] if guard.site_ids else None

        # Base domain: published + active
        art_domain = [('is_published', '=', True), ('active', '=', True)]
        sop_domain = [('state', '=', 'approved'), ('active', '=', True)]

        if search:
            art_domain += [('name', 'ilike', search)]
            sop_domain += [('name', 'ilike', search)]

        articles = request.env['knowledge.article'].sudo().search(
            art_domain, order='sequence, name', limit=60
        )
        sops = request.env['knowledge.sop'].sudo().search(
            sop_domain, order='sequence, name', limit=60
        )

        # Which articles has this guard already acknowledged?
        acked_ids = set(request.env['knowledge.acknowledgment'].sudo().search([
            ('guard_id', '=', guard.id),
        ]).mapped('article_id').ids)

        return self._mobile_render('guardpro.mobile_knowledge', {
            'guard': guard,
            'user': request.env.user,
            'articles': articles,
            'sops': sops,
            'acked_ids': acked_ids,
            'active_tab': tab,
            'search': search,
            'success': kwargs.get('success'),
            'error': kwargs.get('error'),
        })

    @http.route('/guardpro/mobile/knowledge/article/<int:article_id>',
                type='http', auth='user', website=True)
    def mobile_knowledge_article(self, article_id, **kwargs):
        """Article detail page."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        article = request.env['knowledge.article'].sudo().browse(article_id)
        if not article.exists() or not article.is_published:
            return request.redirect('/guardpro/mobile/knowledge?error=not_found')

        acknowledged = bool(request.env['knowledge.acknowledgment'].sudo().search([
            ('guard_id', '=', guard.id),
            ('article_id', '=', article_id),
        ], limit=1))

        return self._mobile_render('guardpro.mobile_knowledge_article', {
            'guard': guard,
            'user': request.env.user,
            'article': article,
            'acknowledged': acknowledged,
            'success': kwargs.get('success'),
        })

    @http.route('/guardpro/mobile/knowledge/sop/<int:sop_id>',
                type='http', auth='user', website=True)
    def mobile_knowledge_sop(self, sop_id, **kwargs):
        """SOP detail with numbered steps and checklist."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.render('guardpro.mobile_no_guard', self._mobile_no_guard_render_vals())

        sop = request.env['knowledge.sop'].sudo().browse(sop_id)
        if not sop.exists() or sop.state != 'approved':
            return request.redirect('/guardpro/mobile/knowledge?tab=sops&error=not_found')

        steps = sop.step_ids.sorted('sequence')
        checklist = sop.checklist_ids.sorted('sequence')

        return self._mobile_render('guardpro.mobile_knowledge_sop', {
            'guard': guard,
            'user': request.env.user,
            'sop': sop,
            'steps': steps,
            'checklist': checklist,
        })

    @http.route('/guardpro/mobile/knowledge/acknowledge/<int:article_id>',
                type='http', auth='user', methods=['POST'], csrf=True)
    def mobile_knowledge_acknowledge(self, article_id, **kwargs):
        """Record guard acknowledgment of an article."""
        guard = self._get_guard_from_user()
        if not guard:
            return request.redirect('/guardpro/mobile?error=no_guard')
        try:
            article = request.env['knowledge.article'].sudo().browse(article_id)
            if not article.exists():
                return request.redirect('/guardpro/mobile/knowledge?error=not_found')
            # Create only if not already acknowledged
            existing = request.env['knowledge.acknowledgment'].sudo().search([
                ('guard_id', '=', guard.id),
                ('article_id', '=', article_id),
            ], limit=1)
            if not existing:
                request.env['knowledge.acknowledgment'].sudo().create({
                    'article_id': article_id,
                    'guard_id': guard.id,
                    'article_version': article.version or '1.0',
                })
            return request.redirect(
                f'/guardpro/mobile/knowledge/article/{article_id}?success=acknowledged'
            )
        except Exception as exc:
            _logger.error('[GuardLink] Knowledge acknowledge failed: %s', exc)
            return request.redirect(
                f'/guardpro/mobile/knowledge/article/{article_id}?error=ack_failed'
            )

