# -*- coding: utf-8 -*-
"""Main GuardLink Controllers."""

from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class GuardLinkController(http.Controller):
    """Main GuardLink web controller."""

    # ====================================================
    # Helpers
    # ====================================================

    def _get_google_maps_api_key(self):
        """Return the configured Google Maps API key if available.

        Uses sudo() because system parameters require elevated access,
        and the value is not record-dependent or security-sensitive.
        """
        return request.env['ir.config_parameter'].sudo().get_param(
            'guardpro.google_maps_api_key'
        )
    
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
                "img-src 'self' data: blob: https://maps.googleapis.com https://*.googleapis.com https://*.gstatic.com https://maps.gstatic.com http://maps.google.com http://*.googleapis.com http://*.gstatic.com; "
                "font-src 'self' https://fonts.gstatic.com data:; "
                "connect-src 'self' https://maps.googleapis.com https://*.googleapis.com http://maps.googleapis.com http://*.googleapis.com; "
                "frame-src 'self' https://maps.google.com http://maps.google.com; "
                "object-src 'none'; "
                "base-uri 'self';"
            )
            response.headers['Content-Security-Policy'] = csp_policy
        return response

    @http.route(['/guardpro', '/guardpro/home'], type='http', auth='public', website=True)
    def homepage(self, **kwargs):
        """GuardLink landing page."""
        user = request.env.user
        is_logged_in = user and user._is_public() == False
        
        values = {
            'is_logged_in': is_logged_in,
            'user': user,
        }
        
        return request.render('guardpro.guardpro_homepage_template', values)

    @http.route(
        ['/guardpro/privacy', '/guardpro/privacy-policy'],
        type='http',
        auth='public',
        website=True,
        sitemap=True,
    )
    def privacy_policy(self, **kwargs):
        """Public Privacy Policy for Play Console / App Store disclosure."""
        return request.render('guardpro.privacy_policy_template', {})


    @http.route('/guardpro/dashboard', type='http', auth='user', website=True)
    def dashboard(self, **kwargs):
        """Main dashboard page."""
        user = request.env.user
        
        # Get guard profile if user is a guard
        guard = request.env['guard.profile'].search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        # Get active shifts
        now = fields.Datetime.now()
        active_shifts = request.env['guard.shift'].search([
            ('start_datetime', '<=', now),
            ('end_datetime', '>=', now),
            ('status', '=', 'in_progress')
        ], limit=10)
        
        # Get recent incidents
        recent_incidents = request.env['incident.report'].search([
            ('status', 'in', ['submitted', 'under_review'])
        ], order='incident_datetime desc', limit=10)
        
        values = {
            'guard': guard,
            'active_shifts': active_shifts,
            'recent_incidents': recent_incidents,
        }
        
        return request.render('guardpro.dashboard_template', values)

    @http.route('/guardpro/mobile/test', type='http', auth='public', website=True)
    def mobile_test(self, **kwargs):
        """Public mobile app test page - uses same template as main mobile interface."""
        return request.render('guardpro.mobile_dashboard', {
            'guard': None,
            'user': request.env.user,
            'shifts_today': [],
            'active_tasks': [],
            'is_checked_in': False,
            'active_attendance': None,
            'recent_incidents': [],
        })
    
    # Old route removed - now using /guardpro/pwa/ instead
    # @http.route('/my/guardpro/mobile', type='http', auth='user', website=True)
    # def mobile_dashboard(self, **kwargs):
    #     """Mobile PWA dashboard page."""
    #     # Redirected to /guardpro/pwa/
    #     pass

    # NOTE: ``/guardpro/manifest.json`` and ``/guardpro/service-worker.js``
    # used to also live here. They were duplicates of the canonical
    # routes in ``pwa_controller.py`` (which return richer manifest
    # metadata and load the real service worker from
    # ``static/pwa/service-worker.js``). Odoo picks one of the two
    # duplicates non-deterministically based on module load order,
    # which caused the PWA install prompt to flicker between two
    # different app identities and the offline cache to occasionally
    # be served the stale inline stub. The canonical definitions are
    # the only ones kept; do NOT re-add these routes here.
    _DUPLICATE_ROUTES_REMOVED = """
const CACHE_NAME = 'guardpro-v1';
const urlsToCache = [
  '/guardpro/pwa/',
  '/guardpro/static/src/css/mobile_pwa.css',
  '/guardpro/static/src/js/mobile_app.js',
  '/guardpro/static/src/js/offline_sync.js'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => response || fetch(event.request))
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});

// Background sync for offline data
self.addEventListener('sync', event => {
  if (event.tag === 'sync-guardpro-data') {
    event.waitUntil(syncData());
  }
});

async function syncData() {
  // Sync checkpoint scans
  const db = await openDB();
  const scans = await db.getAll('pending_scans');
  
  for (const scan of scans) {
    try {
      await fetch('/guardpro/api/checkpoint/scan', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(scan)
      });
      await db.delete('pending_scans', scan.id);
    } catch (error) {
      console.error('Sync failed:', error);
    }
  }
}

function openDB() {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('GuardLinkDB', 1);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
"""

    @http.route('/guardpro/guards/locations', type='json', auth='user')
    def get_guard_locations(self, **kwargs):
        """Get last known locations for all active guards for map display.

        Live updates (within LIVE_MINUTES) are marked ``is_live=True``.
        Older last-known positions are still returned so every guard with a
        location remains visible (frontend renders non-live markers in red).
        """
        LIVE_MINUTES = 5
        try:
            user_sites = request.env.user.site_ids.ids
            _logger.info(
                'Live Map Request - User: %s, Assigned Projects: %s, Groups: %s',
                request.env.user.name,
                user_sites,
                request.env.user.groups_id.mapped('name'),
            )

            guards = request.env['guard.profile'].search([
                ('status', '=', 'active')
            ])
            _logger.info(
                'Found %d active guards visible to user %s',
                len(guards), request.env.user.name,
            )

            locations = []
            GuardLocationHistory = request.env['guard.location.history']
            from odoo import fields
            now_utc = fields.Datetime.now()

            for guard in guards:
                last_location = GuardLocationHistory.sudo().search([
                    ('guard_id', '=', guard.id),
                    ('is_archived', '=', False),
                ], order='timestamp desc', limit=1)

                latitude = longitude = timestamp = None
                site = False
                if last_location and last_location.latitude and last_location.longitude:
                    latitude = last_location.latitude
                    longitude = last_location.longitude
                    timestamp = last_location.timestamp
                    site = last_location.site_id
                elif guard.current_latitude and guard.current_longitude:
                    # Fallback to profile snapshot when history is empty
                    latitude = guard.current_latitude
                    longitude = guard.current_longitude
                    timestamp = guard.last_location_update
                    site = guard.current_site_id

                if not latitude or not longitude:
                    continue

                time_since_update = None
                if timestamp:
                    delta = now_utc - timestamp
                    time_since_update = max(0, int(delta.total_seconds() / 60))

                is_live = (
                    time_since_update is not None
                    and time_since_update <= LIVE_MINUTES
                )

                if time_since_update is None:
                    last_update_label = 'Unknown'
                elif time_since_update < 1:
                    last_update_label = 'Just now'
                elif time_since_update < 60:
                    last_update_label = '%d min ago' % time_since_update
                elif time_since_update < 1440:
                    last_update_label = '%dh ago' % (time_since_update // 60)
                else:
                    last_update_label = '%dd ago' % (time_since_update // 1440)

                locations.append({
                    'id': guard.id,
                    'name': guard.name,
                    'badge_number': guard.badge_number,
                    'latitude': latitude,
                    'longitude': longitude,
                    'last_update': timestamp.isoformat() if timestamp else None,
                    'time_since_update': time_since_update,
                    'last_update_label': last_update_label,
                    'is_live': is_live,
                    'current_site': (
                        site.name if site
                        else (guard.current_site_id.name if guard.current_site_id else 'Unassigned')
                    ),
                    'current_site_id': (
                        site.id if site
                        else (guard.current_site_id.id if guard.current_site_id else None)
                    ),
                    'phone': guard.phone,
                    'status': guard.status,
                })

            # Most recently active first; unknown timestamps last
            locations.sort(
                key=lambda g: (
                    g.get('time_since_update') is None,
                    g.get('time_since_update') if g.get('time_since_update') is not None else 10**9,
                    (g.get('name') or '').lower(),
                )
            )

            _logger.info(
                'Returning %d guard locations for user %s',
                len(locations), request.env.user.name,
            )
            return {'success': True, 'locations': locations}
        except Exception as e:
            _logger.error('Error fetching guard locations: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/guards/send-message', type='json', auth='user')
    def send_map_message_to_guard(self, guard_id=None, content='', is_urgent=False, **kwargs):
        """Send a text message to a guard from the live map (shows on mobile app).

        Supervisors / managers / admins use a Guard↔Supervisor conversation.
        Guards messaging peers use Guard↔Guard when they share a site.
        """
        from datetime import datetime

        content = (content or '').strip()
        if not content:
            return {'success': False, 'error': 'Message cannot be empty.'}
        if not guard_id:
            return {'success': False, 'error': 'Guard is required.'}

        user = request.env.user
        is_staff = (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        )
        sender_guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id),
        ], limit=1)
        if not is_staff and not sender_guard:
            return {
                'success': False,
                'error': 'Only supervisors or guards can send map messages.',
            }

        # Resolve target with normal ACL first (site rules), then sudo for FKs
        target = request.env['guard.profile'].browse(int(guard_id))
        if not target.exists():
            # Staff may see map via sudo location history; re-check with sudo + site filter
            target = request.env['guard.profile'].sudo().browse(int(guard_id))
            if not target.exists():
                return {'success': False, 'error': 'Guard not found.'}
            if not user.has_group('guardpro.group_guardpro_admin'):
                allowed_sites = set(user.site_ids.ids)
                if allowed_sites and not (allowed_sites & set(target.site_ids.ids)):
                    return {
                        'success': False,
                        'error': 'You can only message guards at your assigned projects.',
                    }

        if not target.user_id:
            return {
                'success': False,
                'error': 'This guard has no app login — cannot deliver a mobile message.',
            }
        if target.user_id.id == user.id:
            return {'success': False, 'error': 'You cannot message yourself.'}

        Conversation = request.env['guard.conversation'].sudo()
        Message = request.env['guard.message'].sudo()

        try:
            if is_staff:
                conversation = Conversation.search([
                    ('conversation_type', '=', 'guard_supervisor'),
                    ('guard_id', '=', target.id),
                    ('supervisor_id', '=', user.id),
                ], limit=1)
                if not conversation:
                    conversation = Conversation.create({
                        'conversation_type': 'guard_supervisor',
                        'guard_id': target.id,
                        'supervisor_id': user.id,
                        'is_active': True,
                    })
            else:
                # Peer guard → guard (must share a site)
                sender_sites = set(sender_guard.site_ids.ids)
                target_sites = set(target.site_ids.ids)
                if not sender_sites or not (sender_sites & target_sites):
                    return {
                        'success': False,
                        'error': 'You can only message guards assigned to the same site(s).',
                    }
                conversation = Conversation.get_or_create_guard_conversation(
                    sender_guard.id, target.id,
                )

            message = Message.create({
                'conversation_id': conversation.id,
                'sender_id': user.id,
                'receiver_id': target.user_id.id,
                'message_type': 'text',
                'content': content,
                'is_urgent': bool(is_urgent),
                'created_at': datetime.now(),
            })
            try:
                message.create_notification()
            except Exception as notify_err:
                _logger.warning(
                    'Map message %s created but notification failed: %s',
                    message.id, notify_err,
                )

            return {
                'success': True,
                'message_id': message.id,
                'conversation_id': conversation.id,
                'guard_name': target.name,
            }
        except Exception as e:
            _logger.error('Error sending map message to guard %s: %s', guard_id, e)
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/guards/map/panic-alerts', type='json', auth='user')
    def get_map_panic_alerts(self, since_minutes=30, **kwargs):
        """Recent panic alerts for the live map, scoped to the user's sites.

        Admins / system users see all sites. Other users only see panics for
        sites in ``res.users.site_ids``. Used by the map page popup poller.
        """
        from datetime import timedelta
        from odoo import fields

        try:
            user = request.env.user
            is_admin = (
                user.has_group('guardpro.group_guardpro_admin')
                or user.has_group('base.group_system')
            )
            try:
                window = max(1, min(int(since_minutes or 30), 180))
            except (TypeError, ValueError):
                window = 30

            cutoff = fields.Datetime.now() - timedelta(minutes=window)
            domain = [
                ('title', 'ilike', 'PANIC'),
                ('create_date', '>=', cutoff),
            ]

            if not is_admin:
                allowed = user.site_ids.ids
                if not allowed:
                    return {'success': True, 'alerts': []}
                domain.append(('site_id', 'in', allowed))

            incidents = request.env['incident.report'].sudo().search(
                domain, order='create_date desc', limit=20,
            )

            alerts = []
            for inc in incidents:
                alerts.append({
                    'id': inc.id,
                    'name': inc.name,
                    'title': inc.title,
                    'guard_id': inc.guard_id.id if inc.guard_id else None,
                    'guard_name': inc.guard_id.name if inc.guard_id else 'Unknown guard',
                    'site_id': inc.site_id.id if inc.site_id else None,
                    'site_name': inc.site_id.name if inc.site_id else 'Unknown site',
                    'latitude': inc.latitude or None,
                    'longitude': inc.longitude or None,
                    'create_date': fields.Datetime.to_string(inc.create_date) if inc.create_date else None,
                    'severity': inc.severity,
                    'status': inc.status,
                    'incident_url': '/web#id=%s&model=incident.report&view_type=form' % inc.id,
                })

            return {'success': True, 'alerts': alerts}
        except Exception as e:
            _logger.error('Error fetching map panic alerts: %s', e)
            return {'success': False, 'error': str(e), 'alerts': []}

    @http.route('/guardpro/guards/map', type='http', auth='user', website=True)
    def guards_map_view(self, **kwargs):
        """Display Google Maps with all guard locations."""
        # Get all sites for map
        sites = request.env['client.site'].search([])
        
        # Get all active guards for path tracking dropdown
        guards = request.env['guard.profile'].search([
            ('status', '=', 'active')
        ], order='name')
        
        values = {
            'sites': sites,
            'guards': guards,
            'google_maps_api_key': self._get_google_maps_api_key(),
        }
        
        response = request.render('guardpro.guards_map_template', values)
        return self._set_google_maps_csp(response)
    
    @http.route('/guardpro/guard/path', type='json', auth='user')
    def get_guard_path(self, guard_id, start_datetime=None, end_datetime=None, **kwargs):
        """Get historical path for a specific guard.
        
        Args:
            guard_id: ID of the guard
            start_datetime: Start of time range (ISO format string)
            end_datetime: End of time range (ISO format string)
            
        Returns:
            Dict with success status and path data
        """
        try:
            from datetime import datetime, timedelta
            
            # If no time range specified, default to last 24 hours
            if not start_datetime:
                start_datetime = (datetime.now() - timedelta(hours=24)).isoformat()
            if not end_datetime:
                end_datetime = datetime.now().isoformat()
            
            # Get location history model
            LocationHistory = request.env['guard.location.history']
            
            # Fetch path data
            path = LocationHistory.get_guard_path(
                guard_id=int(guard_id),
                start_datetime=start_datetime,
                end_datetime=end_datetime
            )
            
            # Get guard info
            guard = request.env['guard.profile'].browse(int(guard_id))
            
            return {
                'success': True,
                'guard': {
                    'id': guard.id,
                    'name': guard.name,
                    'badge_number': guard.badge_number,
                },
                'path': path,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
            }
        except Exception as e:
            _logger.error('Error fetching guard path: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/guards/paths/multiple', type='json', auth='user')
    def get_multiple_guard_paths(self, guard_ids, start_datetime=None, end_datetime=None, **kwargs):
        """Get historical paths for multiple guards.
        
        Args:
            guard_ids: List of guard IDs
            start_datetime: Start of time range (ISO format string)
            end_datetime: End of time range (ISO format string)
            
        Returns:
            Dict with success status and paths data for all guards
        """
        try:
            from datetime import datetime, timedelta
            
            # If no time range specified, default to last 24 hours
            if not start_datetime:
                start_datetime = (datetime.now() - timedelta(hours=24)).isoformat()
            if not end_datetime:
                end_datetime = datetime.now().isoformat()
            
            LocationHistory = request.env['guard.location.history']
            
            paths = {}
            for guard_id in guard_ids:
                path = LocationHistory.get_guard_path(
                    guard_id=int(guard_id),
                    start_datetime=start_datetime,
                    end_datetime=end_datetime
                )
                
                guard = request.env['guard.profile'].browse(int(guard_id))
                paths[guard_id] = {
                    'guard': {
                        'id': guard.id,
                        'name': guard.name,
                        'badge_number': guard.badge_number,
                    },
                    'path': path
                }
            
            return {
                'success': True,
                'paths': paths,
                'start_datetime': start_datetime,
                'end_datetime': end_datetime,
            }
        except Exception as e:
            _logger.error('Error fetching multiple guard paths: %s', str(e))
            return {'success': False, 'error': str(e)}
    
    @http.route('/guardpro/sites/geofences', type='json', auth='user')
    def get_site_geofences(self, **kwargs):
        """Get geofence boundaries for all active sites.
        
        Returns:
            Dict with success status and geofence data for all sites
        """
        try:
            # Get all active sites with geofencing enabled
            sites = request.env['client.site'].search([
                ('status', '=', 'active'),
                ('geofence_enabled', '=', True)
            ])
            
            geofences = []
            for site in sites:
                geofence_data = {
                    'id': site.id,
                    'name': site.name,
                    'code': site.code,
                    'type': site.geofence_type,
                    'center': {
                        'lat': site.latitude,
                        'lng': site.longitude
                    },
                    'client': site.client_id.name if site.client_id else '',
                }
                
                if site.geofence_type == 'circle':
                    geofence_data['radius'] = site.geofence_radius
                elif site.geofence_type == 'polygon' and site.geofence_polygon:
                    try:
                        geofence_data['polygon'] = json.loads(site.geofence_polygon)
                    except json.JSONDecodeError:
                        _logger.warning('Invalid polygon JSON for site %s', site.id)
                        continue
                
                geofences.append(geofence_data)
            
            return {'success': True, 'geofences': geofences}
        except Exception as e:
            _logger.error('Error fetching project geofences: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/route/map/<int:wizard_id>', type='http', auth='user', website=True)
    def route_map_view(self, wizard_id, **kwargs):
        """Display optimized route on Google Maps.
        
        Args:
            wizard_id: ID of the route optimizer wizard record
        """
        try:
            # Get the wizard record
            wizard = request.env['route.optimizer.wizard'].browse(wizard_id)
            
            if not wizard.exists():
                return request.render('guardpro.route_map_error', {
                    'error_message': 'Route not found. Please optimize the route again.'
                })
            
            if not wizard.optimized_route:
                return request.render('guardpro.route_map_error', {
                    'error_message': 'No optimized route available. Please optimize the route first.'
                })
            
            # Parse the optimized route JSON
            import json
            try:
                route_data = json.loads(wizard.optimized_route)
                _logger.info('Route data parsed successfully: %d points', len(route_data))
            except json.JSONDecodeError as e:
                _logger.error('JSON decode error: %s', str(e))
                _logger.error('Raw route data: %s', wizard.optimized_route[:200])
                return request.render('guardpro.route_map_error', {
                    'error_message': 'Invalid route data format.'
                })
            
            values = {
                'wizard': wizard,
                'route_data': route_data,
                'route_json': wizard.optimized_route,
                'total_distance': wizard.total_distance,
                'site': wizard.site_id,
                'google_maps_api_key': self._get_google_maps_api_key(),
            }
            
            response = request.render('guardpro.optimized_route_map_template', values)
            return self._set_google_maps_csp(response)
        except Exception as e:
            _logger.error('Error displaying route map: %s', str(e))
            return request.render('guardpro.route_map_error', {
                'error_message': str(e)
            })

    @http.route('/guardpro/checkpoints/map/creator', type='http', auth='user', website=True)
    def checkpoint_map_creator(self, **kwargs):
        """
        Interactive checkpoint map creator page.
        Allows users to create checkpoints by clicking on the map.
        """
        try:
            # Check if user has permission to create checkpoints
            if not request.env.user.has_group('guardpro.group_guardpro_supervisor'):
                return request.render('web.http_error', {
                    'status_code': '403',
                    'status_message': 'Access Denied',
                    'message': 'You do not have permission to create checkpoints.'
                })
            
            # Get all active sites
            sites = request.env['client.site'].search([
                ('status', '=', 'active')
            ], order='name')
            
            values = {
                'sites': sites,
                'google_maps_api_key': self._get_google_maps_api_key(),
            }
            
            response = request.render('guardpro.checkpoint_map_creator_template', values)
            return self._set_google_maps_csp(response)
        except Exception as e:
            _logger.error('Error loading checkpoint map creator: %s', str(e))
            return request.render('web.http_error', {
                'status_code': '500',
                'status_message': 'Internal Server Error',
                'message': str(e)
            })

    @http.route('/guardpro/site/<int:site_id>/geofence', type='http', auth='user', website=True)
    def site_geofence_map(self, site_id, **kwargs):
        """
        Interactive geofencing map page for a site.
        Allows users to mark geofence boundaries on a map.
        """
        try:
            # Get the site
            site = request.env['client.site'].browse(site_id)
            if not site.exists():
                return request.not_found()
            
            # Check access rights
            if not request.env.user.has_group('guardpro.group_guardpro_supervisor') and \
               not request.env.user.has_group('guardpro.group_guardpro_manager') and \
               not request.env.user.has_group('guardpro.group_guardpro_admin'):
                return request.render('web.http_error', {
                    'status_code': '403',
                    'status_message': 'Access Denied',
                    'message': 'You do not have permission to edit geofences.'
                })
            
            values = {
                'site': site,
                'google_maps_api_key': self._get_google_maps_api_key(),
            }
            
            response = request.render('guardpro.site_geofence_map_template', values)
            return self._set_google_maps_csp(response)
        except Exception as e:
            _logger.error('Error loading geofence map for site %s: %s', site_id, str(e))
            return request.render('web.http_error', {
                'status_code': '500',
                'status_message': 'Internal Server Error',
                'message': str(e)
            })

    @http.route('/guardpro/site/<int:site_id>/geofence/save', type='http', auth='user', methods=['POST'], csrf=False)
    def save_site_geofence(self, site_id, **kwargs):
        """
        Save geofence data for a site.
        
        Args:
            site_id: ID of the site
            JSON body should contain:
                geofence_type: 'circle' or 'polygon'
                geofence_radius: Radius in meters (for circle)
                geofence_polygon: JSON string of polygon coordinates (for polygon)
                latitude: Project latitude (optional, updates if provided)
                longitude: Project longitude (optional, updates if provided)
        """
        try:
            # Get data from JSON request body (HTTP type)
            import json
            try:
                data = json.loads(request.httprequest.data.decode('utf-8')) if request.httprequest.data else {}
            except (ValueError, AttributeError):
                data = {}
            geofence_type = data.get('geofence_type')
            geofence_radius = data.get('geofence_radius')
            geofence_polygon = data.get('geofence_polygon')
            latitude = data.get('latitude')
            longitude = data.get('longitude')
            
            site = request.env['client.site'].browse(site_id)
            if not site.exists():
                error_response = {'success': False, 'error': 'Project not found'}
                return request.make_response(
                    json.dumps(error_response),
                    headers=[('Content-Type', 'application/json')],
                    status=404
                )
            
            # Check access rights
            if not request.env.user.has_group('guardpro.group_guardpro_supervisor') and \
               not request.env.user.has_group('guardpro.group_guardpro_manager') and \
               not request.env.user.has_group('guardpro.group_guardpro_admin'):
                error_response = {'success': False, 'error': 'Access denied'}
                return request.make_response(
                    json.dumps(error_response),
                    headers=[('Content-Type', 'application/json')],
                    status=403
                )
            
            # Update coordinates if provided
            if latitude is not None and longitude is not None:
                site.write({
                    'latitude': float(latitude),
                    'longitude': float(longitude),
                })
            
            # Update geofence data
            update_vals = {
                'geofence_enabled': True,
                'geofence_type': geofence_type,
            }
            
            if geofence_type == 'circle' and geofence_radius is not None:
                update_vals['geofence_radius'] = float(geofence_radius)
                update_vals['geofence_polygon'] = False
            elif geofence_type == 'polygon' and geofence_polygon:
                # Validate and store polygon JSON
                try:
                    polygon_data = json.loads(geofence_polygon) if isinstance(geofence_polygon, str) else geofence_polygon
                    if not isinstance(polygon_data, list) or len(polygon_data) < 3:
                        error_response = {'success': False, 'error': 'Polygon must have at least 3 points'}
                        return request.make_response(
                            json.dumps(error_response),
                            headers=[('Content-Type', 'application/json')],
                            status=400
                        )
                    update_vals['geofence_polygon'] = json.dumps(polygon_data)
                    update_vals['geofence_radius'] = False
                except json.JSONDecodeError:
                    error_response = {'success': False, 'error': 'Invalid polygon JSON format'}
                    return request.make_response(
                        json.dumps(error_response),
                        headers=[('Content-Type', 'application/json')],
                        status=400
                    )
            
            site.write(update_vals)
            
            response_data = {
                'success': True,
                'message': 'Geofence saved successfully',
                'site_id': site.id
            }
            return request.make_response(
                json.dumps(response_data),
                headers=[('Content-Type', 'application/json')]
            )
        except Exception as e:
            _logger.error('Error saving geofence for site %s: %s', site_id, str(e))
            error_response = {'success': False, 'error': str(e)}
            return request.make_response(
                json.dumps(error_response),
                headers=[('Content-Type', 'application/json')],
                status=400
            )