# -*- coding: utf-8 -*-
"""Enhanced Client Portal Controller with Real-Time Features."""

from odoo import http, fields, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.tools import groupby as groupbyelem
from collections import OrderedDict
import json
import logging

_logger = logging.getLogger(__name__)


class ClientPortalEnhanced(CustomerPortal):
    """Enhanced client portal with real-time guard tracking, incidents, and feedback."""
    
    def _get_google_maps_api_key(self):
        """Return the configured Google Maps API key if available."""
        return request.env['ir.config_parameter'].sudo().get_param(
            'guardpro.google_maps_api_key'
        )

    def _portal_allowed_site_ids(self, user=None):
        """Site IDs the portal caller may access."""
        user = user or request.env.user
        if user.has_group('guardpro.group_guardpro_admin'):
            return None  # unrestricted
        return frozenset(user.site_ids.ids)

    def _portal_resolve_site_id(self, site_id, user=None):
        """Return a validated site id or ``None`` if not allowed / missing."""
        user = user or request.env.user
        allowed = self._portal_allowed_site_ids(user)
        try:
            site_id = int(site_id) if site_id not in (None, False, '') else None
        except (TypeError, ValueError):
            return None
        if not site_id:
            return None
        if allowed is None:
            return site_id
        if site_id not in allowed:
            return None
        return site_id

    def _portal_guard_allowed_for_sites(self, guard_id, site_ids, user=None):
        """True when ``guard_id`` shares at least one of ``site_ids`` (or admin)."""
        user = user or request.env.user
        if user.has_group('guardpro.group_guardpro_admin'):
            return True
        try:
            guard_id = int(guard_id)
        except (TypeError, ValueError):
            return False
        if not guard_id or not site_ids:
            return False
        guard = request.env['guard.profile'].sudo().browse(guard_id)
        if not guard.exists():
            return False
        return bool(set(guard.site_ids.ids) & set(site_ids))
    
    def _set_google_maps_csp(self, response):
        """Set Content Security Policy headers for Google Maps integration.
        
        Allows external resources needed for Google Maps API:
        - Google Maps JavaScript API
        - Marker clusterer from unpkg.com
        - Map tiles and images from Google domains
        - Inline scripts and styles required by Google Maps
        
        Args:
            response: HTTP response object to modify
        """
        if hasattr(response, 'headers'):
            # CSP that allows Google Maps and required external resources
            csp_policy = (
                "default-src 'self'; "
                "script-src 'self' https://maps.googleapis.com https://unpkg.com 'unsafe-inline' 'unsafe-eval'; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "img-src 'self' data: blob: https://maps.googleapis.com https://*.googleapis.com https://*.gstatic.com https://maps.gstatic.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "connect-src 'self' https://maps.googleapis.com https://*.googleapis.com; "
                "frame-src 'self' https://maps.google.com; "
                "object-src 'none'; "
                "base-uri 'self';"
            )
            response.headers['Content-Security-Policy'] = csp_policy
        return response
    
    def _prepare_home_portal_values(self, counters):
        """Add custom counters to portal home."""
        values = super()._prepare_home_portal_values(counters)
        user = request.env.user
        
        # Check if user has site access
        if user.site_ids:
            site_domain = [('site_id', 'in', user.site_ids.ids)]
            
            if 'incident_count' in counters:
                values['incident_count'] = request.env['incident.report'].search_count(
                    site_domain + [('visible_to_client', '=', True)]
                )
            
            if 'active_guard_count' in counters:
                values['active_guard_count'] = request.env['guard.location.live'].search_count(
                    site_domain + [('is_active', '=', True), ('share_with_client', '=', True)]
                )
            
            if 'shift_count' in counters:
                values['shift_count'] = request.env['guard.shift'].search_count(site_domain)
            
            if 'feedback_count' in counters:
                # Check if user is a resident
                resident = request.env['tenant.resident'].search([('user_id', '=', user.id)], limit=1)
                if resident:
                    values['feedback_count'] = request.env['client.feedback'].search_count([
                        ('resident_id', '=', resident.id)
                    ])
                else:
                    values['feedback_count'] = request.env['client.feedback'].search_count(site_domain)
        
        return values
    
    # ========== Real-Time Guard Location Tracking ==========
    
    @http.route(['/my/guards/map'], type='http', auth='user', website=True)
    def portal_guards_map(self, **kwargs):
        """Display live guard location map."""
        user = request.env.user
        
        if not user.site_ids:
            return request.render('guardpro.portal_no_site_access')
        
        # Get user's sites
        sites = user.site_ids
        
        values = {
            'page_name': 'guard_map',
            'sites': sites,
            'default_site': sites[0] if sites else None,
            'google_maps_api_key': self._get_google_maps_api_key(),
        }
        
        response = request.render('guardpro.portal_guard_location_map', values)
        return self._set_google_maps_csp(response)
    
    @http.route(['/my/guards/locations'], type='json', auth='user')
    def portal_get_guard_locations(self, site_id=None, **kwargs):
        """Get live guard locations from location history (JSON API for real-time updates)."""
        user = request.env.user

        # Security check
        allowed = self._portal_allowed_site_ids(user)
        if allowed is not None and not allowed:
            return {'error': 'No site access'}

        # Build domain; if a site filter is requested it must be in assigned projects
        if site_id:
            resolved = self._portal_resolve_site_id(site_id, user)
            if not resolved:
                return {'error': 'Project not found', 'locations': []}
            site_domain = [('site_id', '=', resolved)]
        elif allowed is None:
            site_domain = []
        else:
            site_domain = [('site_id', 'in', list(allowed))]
        
        # Get guards currently assigned to the site(s) with active shifts
        GuardShift = request.env['guard.shift']
        active_shifts = GuardShift.search(
            site_domain + [
                ('status', 'in', ['scheduled', 'in_progress']),
                ('start_datetime', '<=', fields.Datetime.now()),
                ('end_datetime', '>=', fields.Datetime.now())
            ]
        )
        
        # Get unique guard IDs from active shifts
        guard_ids = active_shifts.mapped('guard_id').ids
        
        if not guard_ids:
            return {'locations': []}
        
        # Get the last location from location history for each guard
        GuardLocationHistory = request.env['guard.location.history']
        result = []
        
        for guard_id in guard_ids:
            # Get the most recent location for this guard (exclude archived)
            last_location = GuardLocationHistory.search([
                ('guard_id', '=', guard_id),
                ('is_archived', '=', False)
            ], order='timestamp desc', limit=1)
            
            if last_location:
                guard = last_location.guard_id
                shift = active_shifts.filtered(lambda s: s.guard_id.id == guard_id)[:1]
                
                # Calculate time since update
                from datetime import datetime
                delta = datetime.now() - last_location.timestamp
                
                if delta.total_seconds() < 60:
                    time_since_update = 'Just now'
                elif delta.total_seconds() < 3600:
                    minutes = int(delta.total_seconds() / 60)
                    time_since_update = f'{minutes} minutes ago'
                elif delta.total_seconds() < 86400:
                    hours = int(delta.total_seconds() / 3600)
                    time_since_update = f'{hours} hours ago'
                else:
                    days = delta.days
                    time_since_update = f'{days} days ago'
                
                result.append({
                    'id': last_location.id,
                    'guard_id': guard.id,
                    'guard_name': guard.name,
                    'latitude': last_location.latitude,
                    'longitude': last_location.longitude,
                    'accuracy': last_location.accuracy,
                    'speed': last_location.speed,
                    'heading': last_location.heading,
                    'last_update': last_location.timestamp.isoformat() if last_location.timestamp else None,
                    'time_since_update': time_since_update,
                    'time_since_update_seconds': delta.total_seconds(),
                    'is_on_duty': shift.status == 'in_progress' if shift else False,
                    'is_live': delta.total_seconds() < 300,
                    'battery_level': last_location.battery_level,
                    'site_id': last_location.site_id.id if last_location.site_id else None,
                    'site_name': last_location.site_id.name if last_location.site_id else '',
                })

        result.sort(
            key=lambda g: (
                g.get('time_since_update_seconds') is None,
                g.get('time_since_update_seconds') if g.get('time_since_update_seconds') is not None else 10**18,
                (g.get('guard_name') or '').lower(),
            )
        )
        
        return {'locations': result}
    
    # ========== Live Incident Status Updates ==========
    
    @http.route(['/my/incidents', '/my/incidents/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_incidents(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kwargs):
        """Display incidents with live status updates."""
        user = request.env.user
        
        if not user.site_ids:
            return request.render('guardpro.portal_no_site_access')
        
        Incident = request.env['incident.report']
        
        domain = [
            ('site_id', 'in', user.site_ids.ids),
            ('visible_to_client', '=', True)
        ]
        
        # Filter by severity
        filterby_options = {
            'all': {'label': _('All'), 'domain': []},
            'critical': {'label': _('Critical'), 'domain': [('severity', '=', 'critical')]},
            'high': {'label': _('High'), 'domain': [('severity', '=', 'high')]},
            'medium': {'label': _('Medium'), 'domain': [('severity', '=', 'medium')]},
            'low': {'label': _('Low'), 'domain': [('severity', '=', 'low')]},
        }
        
        if not filterby:
            filterby = 'all'
        
        domain += filterby_options.get(filterby, filterby_options['all'])['domain']
        
        # Sort options
        sortby_options = {
            'date': {'label': _('Date'), 'order': 'incident_datetime desc'},
            'severity': {'label': _('Severity'), 'order': 'severity desc, incident_datetime desc'},
            'status': {'label': _('Status'), 'order': 'status, incident_datetime desc'},
        }
        
        if not sortby:
            sortby = 'date'
        
        order = sortby_options.get(sortby, sortby_options['date'])['order']
        
        # Pager
        incident_count = Incident.search_count(domain)
        pager = portal_pager(
            url='/my/incidents',
            url_args={'sortby': sortby, 'filterby': filterby},
            total=incident_count,
            page=page,
            step=10
        )
        
        # Get incidents
        incidents = Incident.search(domain, order=order, limit=10, offset=pager['offset'])
        
        values = {
            'page_name': 'incidents',
            'incidents': incidents,
            'pager': pager,
            'default_url': '/my/incidents',
            'sortby': sortby,
            'sortby_options': sortby_options,
            'filterby': filterby,
            'filterby_options': filterby_options,
        }
        
        return request.render('guardpro.portal_my_incidents', values)
    
    @http.route(['/my/incident/<int:incident_id>'], type='http', auth='user', website=True)
    def portal_incident_detail(self, incident_id, **kwargs):
        """Display incident detail with status updates."""
        try:
            incident = self._document_check_access('incident.report', incident_id)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        # Get status updates
        updates = request.env['incident.status.update'].search([
            ('incident_id', '=', incident_id),
            ('visible_to_client', '=', True)
        ], order='update_datetime desc')
        
        values = {
            'page_name': 'incident_detail',
            'incident': incident,
            'status_updates': updates,
        }
        
        return request.render('guardpro.portal_incident_detail', values)
    
    @http.route(['/my/incident/<int:incident_id>/updates'], type='json', auth='user')
    def portal_get_incident_updates(self, incident_id, **kwargs):
        """Get live incident status updates (JSON API for polling)."""
        try:
            incident = self._document_check_access('incident.report', incident_id)
        except (AccessError, MissingError):
            return {'error': 'Access denied'}
        
        updates = request.env['incident.status.update'].search([
            ('incident_id', '=', incident_id),
            ('visible_to_client', '=', True)
        ], order='update_datetime desc')
        
        result = []
        for update in updates:
            result.append({
                'id': update.id,
                'title': update.title,
                'description': update.description,
                'update_datetime': update.update_datetime.isoformat() if update.update_datetime else None,
                'update_type': update.update_type,
                'updated_by': update.updated_by_id.name,
            })
        
        return {
            'incident_status': incident.status,
            'last_update': incident.last_update_datetime.isoformat() if incident.last_update_datetime else None,
            'updates': result
        }
    
    # ========== Feedback & Rating System ==========
    
    @http.route(['/my/feedback', '/my/feedback/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_feedback(self, page=1, **kwargs):
        """Display feedback submitted by user."""
        user = request.env.user
        
        Feedback = request.env['client.feedback']
        
        # Check if user is a resident
        resident = request.env['tenant.resident'].search([('user_id', '=', user.id)], limit=1)
        
        if resident:
            domain = [('resident_id', '=', resident.id)]
        elif user.site_ids:
            domain = [('site_id', 'in', user.site_ids.ids), ('resident_id', '=', False)]
        else:
            domain = []
        
        # Pager
        feedback_count = Feedback.search_count(domain)
        pager = portal_pager(
            url='/my/feedback',
            total=feedback_count,
            page=page,
            step=10
        )
        
        # Get feedback
        feedbacks = Feedback.search(domain, order='create_date desc', limit=10, offset=pager['offset'])
        
        values = {
            'page_name': 'feedback',
            'feedbacks': feedbacks,
            'pager': pager,
            'is_resident': bool(resident),
            'resident': resident,
        }
        
        return request.render('guardpro.portal_my_feedback', values)
    
    @http.route(['/my/feedback/new'], type='http', auth='user', website=True)
    def portal_feedback_new(self, **kwargs):
        """Display feedback submission form."""
        user = request.env.user
        
        # Check if user is a resident
        resident = request.env['tenant.resident'].search([('user_id', '=', user.id)], limit=1)
        
        # Get available guards for this site
        if resident:
            site = resident.site_id
            guards = request.env['guard.profile'].search([
                ('site_id', '=', site.id)
            ])
        elif user.site_ids:
            site = user.site_ids[0]
            guards = request.env['guard.profile'].search([
                ('site_id', 'in', user.site_ids.ids)
            ])
        else:
            return request.redirect('/my')
        
        # Get recent shifts
        shifts = request.env['guard.shift'].search([
            ('site_id', '=', site.id),
            ('status', 'in', ['completed', 'in_progress'])
        ], order='start_datetime desc', limit=10)
        
        values = {
            'page_name': 'feedback_new',
            'guards': guards,
            'shifts': shifts,
            'site': site,
            'is_resident': bool(resident),
            'resident': resident,
        }
        
        return request.render('guardpro.portal_feedback_form', values)
    
    @http.route(['/my/feedback/submit'], type='http', auth='user', website=True, methods=['POST'], csrf=True)
    def portal_feedback_submit(self, **post):
        """Submit feedback (assigned projects / overlapping guards only)."""
        user = request.env.user

        # Check if user is a resident
        resident = request.env['tenant.resident'].search([('user_id', '=', user.id)], limit=1)

        # Validate required fields
        if not post.get('guard_id') or not post.get('overall_rating') or not post.get('comments'):
            return request.redirect('/my/feedback/new?error=missing_fields')

        allowed = self._portal_allowed_site_ids(user)
        if allowed is not None and not allowed and not resident:
            return request.redirect('/my/feedback/new?error=no_site')

        # Residents are limited to their community site; others to assigned projects
        if resident and resident.site_id:
            site_id = resident.site_id.id
        else:
            site_id = self._portal_resolve_site_id(post.get('site_id'), user)
            if not site_id and allowed:
                # Fall back to first assigned site only when form omitted site
                # but never accept an unvalidated posted foreign site
                if not post.get('site_id') and len(allowed) == 1:
                    site_id = next(iter(allowed))
            if not site_id:
                return request.redirect('/my/feedback/new?error=invalid_site')

        allowed_for_guard = [site_id] if site_id else list(allowed or [])
        if not self._portal_guard_allowed_for_sites(post.get('guard_id'), allowed_for_guard, user):
            return request.redirect('/my/feedback/new?error=invalid_guard')

        site = request.env['client.site'].sudo().browse(site_id)
        if not site.exists():
            return request.redirect('/my/feedback/new?error=invalid_site')

        # Create feedback
        vals = {
            'guard_id': int(post.get('guard_id')),
            'site_id': site_id,
            'feedback_type': post.get('feedback_type', 'general'),
            'overall_rating': post.get('overall_rating'),
            'professionalism_rating': post.get('professionalism_rating'),
            'punctuality_rating': post.get('punctuality_rating'),
            'communication_rating': post.get('communication_rating'),
            'appearance_rating': post.get('appearance_rating'),
            'comments': post.get('comments'),
            'request_same_guard': bool(post.get('request_same_guard')),
            'request_different_guard': bool(post.get('request_different_guard')),
        }

        if resident:
            vals['resident_id'] = resident.id
            vals['client_id'] = resident.client_id.id
        else:
            vals['client_id'] = site.client_id.id

        if post.get('shift_id'):
            try:
                shift_id = int(post.get('shift_id'))
            except (TypeError, ValueError):
                shift_id = False
            if shift_id:
                shift = request.env['guard.shift'].sudo().browse(shift_id)
                if (
                    shift.exists()
                    and shift.site_id
                    and shift.site_id.id == site_id
                    and shift.guard_id.id == int(post.get('guard_id'))
                ):
                    vals['shift_id'] = shift_id

        try:
            request.env['client.feedback'].create(vals)
            return request.redirect('/my/feedback?message=submitted')
        except Exception as e:
            _logger.error('Error submitting feedback: %s', str(e))
            return request.redirect('/my/feedback/new?error=submit_failed')
    
    @http.route(['/my/feedback/<int:feedback_id>'], type='http', auth='user', website=True)
    def portal_feedback_detail(self, feedback_id, **kwargs):
        """Display feedback detail."""
        try:
            feedback = self._document_check_access('client.feedback', feedback_id)
        except (AccessError, MissingError):
            return request.redirect('/my/feedback')
        
        values = {
            'page_name': 'feedback_detail',
            'feedback': feedback,
        }
        
        return request.render('guardpro.portal_feedback_detail', values)
    
    # ========== Site Dashboard ==========
    
    @http.route(['/my/dashboard'], type='http', auth='user', website=True)
    def portal_dashboard(self, **kwargs):
        """Display client dashboard with KPIs."""
        user = request.env.user
        
        if not user.site_ids:
            return request.render('guardpro.portal_no_site_access')
        
        # Get or create dashboard
        site = user.site_ids[0]
        dashboard = request.env['client.dashboard'].search([
            ('site_id', '=', site.id)
        ], limit=1)
        
        if not dashboard:
            dashboard = request.env['client.dashboard'].create({
                'client_id': site.client_id.id,
                'site_id': site.id
            })
        
        values = {
            'page_name': 'dashboard',
            'dashboard': dashboard,
            'site': site,
        }
        
        return request.render('guardpro.portal_client_dashboard', values)
    
    # ========== Guard Shifts ==========
    
    @http.route(['/my/shifts', '/my/shifts/page/<int:page>'], type='http', auth='user', website=True)
    def portal_my_shifts(self, page=1, **kwargs):
        """Display scheduled shifts."""
        user = request.env.user
        
        if not user.site_ids:
            return request.render('guardpro.portal_no_site_access')
        
        Shift = request.env['guard.shift']
        
        domain = [('site_id', 'in', user.site_ids.ids)]
        
        # Pager
        shift_count = Shift.search_count(domain)
        pager = portal_pager(
            url='/my/shifts',
            total=shift_count,
            page=page,
            step=10
        )
        
        # Get shifts
        shifts = Shift.search(domain, order='start_datetime desc', limit=10, offset=pager['offset'])
        
        values = {
            'page_name': 'shifts',
            'shifts': shifts,
            'pager': pager,
        }
        
        return request.render('guardpro.portal_my_shifts', values)
    
    # ========== Helper Methods ==========
    
    def _document_check_access(self, model_name, document_id, access_token=None):
        """Check if user has access to document."""
        document = request.env[model_name].browse([document_id])
        document_sudo = document.sudo()
        
        try:
            document.check_access_rights('read')
            document.check_access_rule('read')
        except AccessError:
            if access_token and document_sudo.access_token and access_token == document_sudo.access_token:
                return document_sudo
            raise
        
        # Additional check for site-based access
        user = request.env.user
        if hasattr(document_sudo, 'site_id') and document_sudo.site_id:
            if document_sudo.site_id not in user.site_ids:
                raise AccessError(_('You do not have access to this document'))
        
        return document_sudo

