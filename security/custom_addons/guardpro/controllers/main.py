# -*- coding: utf-8 -*-
"""Main GuardPro Controllers."""

from odoo import http, fields
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)


class GuardProController(http.Controller):
    """Main GuardPro web controller."""

    # ====================================================
    # CCTV Stream Viewer
    # ====================================================

    @http.route('/guardpro/cctv/view/<int:camera_id>', type='http', auth='user', website=True)
    def cctv_viewer(self, camera_id, **kwargs):
        """Display CCTV camera stream viewer."""
        try:
            camera = request.env['cctv.camera'].browse(camera_id)
            if not camera.exists():
                return request.not_found()
            
            # Check access rights
            if not request.env.user.has_group('guardpro.group_guardpro_client_user') and \
               not request.env.user.has_group('guardpro.group_guardpro_supervisor') and \
               not request.env.user.has_group('guardpro.group_guardpro_manager') and \
               not request.env.user.has_group('guardpro.group_guardpro_admin'):
                return request.redirect('/web/login?redirect=/guardpro/cctv/view/%s' % camera_id)
            
            # Get stream URL with authentication if needed
            stream_url = camera.stream_url
            original_stream_url = stream_url  # Keep original for proxy
            
            # For HTTP image streams (snapshots), use proxy to avoid CORS issues
            use_proxy = (camera.stream_type == 'http' and 
                        ('picture' in stream_url.lower() or 
                         'snapshot' in stream_url.lower() or
                         'video.cgi' in stream_url.lower()))
            
            if use_proxy:
                # Use proxy endpoint which handles authentication server-side
                stream_url = f'/guardpro/cctv/proxy/{camera_id}'
            elif camera.stream_type in ['rtsp', 'http'] and camera.username and camera.password:
                # Add authentication to URL for RTSP and HTTP streams (not using proxy)
                if '@' not in stream_url:  # Only add auth if not already present
                    from urllib.parse import urlparse, urlunparse, quote
                    parsed = urlparse(stream_url)
                    # URL encode username and password to handle special characters
                    username_encoded = quote(camera.username, safe='')
                    password_encoded = quote(camera.password, safe='')
                    netloc = f"{username_encoded}:{password_encoded}@{parsed.netloc}"
                    new_parsed = parsed._replace(netloc=netloc)
                    stream_url = urlunparse(new_parsed)
            
            values = {
                'camera': camera,
                'stream_url': stream_url,
                'stream_type': camera.stream_type,
                'site': camera.site_id,
            }
            
            _logger.info('CCTV Viewer - Camera: %s, Stream URL: %s, Stream Type: %s', 
                        camera.name, stream_url, camera.stream_type)
            
            return request.render('guardpro.cctv_stream_viewer', values)
        except Exception as e:
            _logger.error('Error loading CCTV viewer: %s', str(e))
            return request.not_found()

    @http.route('/guardpro/cctv/proxy/<int:camera_id>', type='http', auth='user', cors='*')
    def cctv_stream_proxy(self, camera_id, **kwargs):
        """Proxy endpoint for CCTV camera streams to avoid CORS issues."""
        try:
            import requests
            from requests.auth import HTTPBasicAuth
            
            camera = request.env['cctv.camera'].browse(camera_id)
            if not camera.exists():
                return request.not_found()
            
            # Check access rights
            if not request.env.user.has_group('guardpro.group_guardpro_client_user') and \
               not request.env.user.has_group('guardpro.group_guardpro_supervisor') and \
               not request.env.user.has_group('guardpro.group_guardpro_manager') and \
               not request.env.user.has_group('guardpro.group_guardpro_admin'):
                return request.unauthorized()
            
            # Get the original stream URL without authentication in URL
            original_url = camera.stream_url
            _logger.info('CCTV Proxy - Original URL: %s', original_url)
            
            # Remove authentication from URL if present (format: http://user:pass@host/path)
            if '@' in original_url:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(original_url)
                # Extract just the hostname:port part (after @)
                if '@' in parsed.netloc:
                    netloc = parsed.netloc.split('@')[-1]
                else:
                    netloc = parsed.netloc
                new_parsed = parsed._replace(netloc=netloc)
                original_url = urlunparse(new_parsed)
            
            _logger.info('CCTV Proxy - Cleaned URL: %s', original_url)
            _logger.info('CCTV Proxy - Username: %s, Has Password: %s', 
                        camera.username, bool(camera.password))
            
            # Fetch the stream with authentication
            # Hikvision cameras typically require Digest authentication
            # Try both Digest and Basic auth methods
            auth = None
            if camera.username and camera.password:
                auth = HTTPBasicAuth(camera.username, camera.password)
            
            # First attempt with requests (Basic auth)
            try:
                response = requests.get(
                    original_url,
                    auth=auth,
                    timeout=10,
                    stream=False,  # Get full image content
                    verify=False,  # Disable SSL verification for self-signed certificates
                    allow_redirects=True
                )
                
                # If 401, try using embedded credentials in URL (some cameras support this)
                if response.status_code == 401 and camera.username and camera.password:
                    _logger.info('CCTV Proxy - Basic auth returned 401, trying embedded credentials in URL')
                    try:
                        from urllib.parse import urlparse, urlunparse
                        parsed = urlparse(original_url)
                        # Embed credentials in URL: http://user:pass@host/path
                        netloc_with_auth = f"{camera.username}:{camera.password}@{parsed.netloc}"
                        url_with_auth = urlunparse((
                            parsed.scheme,
                            netloc_with_auth,
                            parsed.path,
                            parsed.params,
                            parsed.query,
                            parsed.fragment
                        ))
                        
                        # Try with embedded credentials (no auth header)
                        response_embedded = requests.get(
                            url_with_auth,
                            timeout=10,
                            stream=False,
                            verify=False,
                            allow_redirects=True
                        )
                        
                        if response_embedded.status_code == 200:
                            _logger.info('CCTV Proxy - Successfully fetched stream with embedded credentials, Content-Type: %s, Size: %d bytes', 
                                        response_embedded.headers.get('Content-Type'), len(response_embedded.content))
                            
                            content_type = response_embedded.headers.get('Content-Type', 'image/jpeg')
                            headers = {
                                'Content-Type': content_type,
                                'Cache-Control': 'no-cache, no-store, must-revalidate',
                                'Pragma': 'no-cache',
                                'Expires': '0',
                                'Access-Control-Allow-Origin': '*',
                            }
                            
                            return request.make_response(response_embedded.content, headers=headers)
                        else:
                            _logger.warning('CCTV Proxy - Embedded credentials also failed with status %d', response_embedded.status_code)
                            
                    except Exception as embedded_err:
                        _logger.warning('CCTV Proxy - Embedded credentials failed: %s', str(embedded_err))
                    
                    # If embedded credentials also fail, try Digest auth using urllib
                    _logger.info('CCTV Proxy - Trying Digest authentication')
                    try:
                        from urllib.request import Request, build_opener, HTTPDigestAuthHandler, HTTPPasswordMgrWithDefaultRealm
                        from urllib.parse import urlparse
                        import socket
                        
                        # Create password manager
                        password_mgr = HTTPPasswordMgrWithDefaultRealm()
                        parsed_url = urlparse(original_url)
                        password_mgr.add_password(None, f"{parsed_url.scheme}://{parsed_url.netloc}", 
                                                 camera.username, camera.password)
                        
                        # Create digest auth handler
                        digest_handler = HTTPDigestAuthHandler(password_mgr)
                        opener = build_opener(digest_handler)
                        
                        # Create request
                        req = Request(original_url)
                        req.add_header('User-Agent', 'Odoo/18.0')
                        
                        # Set socket timeout
                        socket.setdefaulttimeout(10)
                        
                        # Open URL with digest auth
                        response_urllib = opener.open(req)
                        content = response_urllib.read()
                        
                        # Get content type from headers
                        content_type = 'image/jpeg'
                        if hasattr(response_urllib, 'headers'):
                            content_type = response_urllib.headers.get('Content-Type', 'image/jpeg')
                        elif hasattr(response_urllib, 'info'):
                            content_type = response_urllib.info().get('Content-Type', 'image/jpeg')
                        
                        _logger.info('CCTV Proxy - Successfully fetched stream with Digest auth, Content-Type: %s, Size: %d bytes', 
                                    content_type, len(content))
                        
                        # Return the stream with appropriate headers
                        headers = {
                            'Content-Type': content_type,
                            'Cache-Control': 'no-cache, no-store, must-revalidate',
                            'Pragma': 'no-cache',
                            'Expires': '0',
                            'Access-Control-Allow-Origin': '*',
                        }
                        
                        return request.make_response(content, headers=headers)
                        
                    except Exception as digest_err:
                        _logger.error('CCTV Proxy - Digest auth also failed: %s', str(digest_err), exc_info=True)
                        # Re-raise the original 401 error
                        response.raise_for_status()
                
                # If not 401, check for other errors
                response.raise_for_status()  # Raise exception for bad status codes
                _logger.info('CCTV Proxy - Successfully fetched stream, Content-Type: %s, Size: %d bytes', 
                            response.headers.get('Content-Type'), len(response.content))
                
            except requests.exceptions.RequestException as req_err:
                _logger.error('CCTV Proxy - Request failed: %s', str(req_err), exc_info=True)
                raise
            
            # Return the stream with appropriate headers
            content_type = response.headers.get('Content-Type', 'image/jpeg')
            headers = {
                'Content-Type': content_type,
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0',
                'Access-Control-Allow-Origin': '*',  # Allow CORS for image loading
            }
            
            return request.make_response(
                response.content,
                headers=headers
            )
            
        except requests.exceptions.RequestException as e:
            _logger.error('Error proxying CCTV stream for camera %s: %s', camera_id, str(e))
            _logger.error('URL attempted: %s', original_url if 'original_url' in locals() else 'unknown')
            # Return HTTP error with details
            error_msg = f'Error loading camera stream: {str(e)}'
            return request.make_response(
                error_msg.encode('utf-8'),
                headers={
                    'Content-Type': 'text/plain',
                    'X-Error': 'true'
                },
                status=500
            )
        except Exception as e:
            _logger.error('Error in CCTV proxy for camera %s: %s', camera_id, str(e), exc_info=True)
            error_msg = f'Internal error: {str(e)}'
            return request.make_response(
                error_msg.encode('utf-8'),
                headers={
                    'Content-Type': 'text/plain',
                    'X-Error': 'true'
                },
                status=500
            )

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
        """GuardPro landing page."""
        user = request.env.user
        is_logged_in = user and user._is_public() == False
        
        values = {
            'is_logged_in': is_logged_in,
            'user': user,
        }
        
        return request.render('guardpro.guardpro_homepage_template', values)


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

    @http.route('/guardpro/manifest.json', type='http', auth='public')
    def pwa_manifest(self):
        """PWA manifest file."""
        manifest = {
            "name": "GuardPro",
            "short_name": "GuardPro",
            "description": "Security Guard Management System",
            "start_url": "/guardpro/pwa/",
            "display": "standalone",
            "background_color": "#1f2937",
            "theme_color": "#3b82f6",
            "orientation": "portrait",
            "icons": [
                {
                    "src": "/guardpro/static/src/img/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png"
                },
                {
                    "src": "/guardpro/static/src/img/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png"
                }
            ]
        }
        
        return request.make_response(
            json.dumps(manifest),
            headers=[('Content-Type', 'application/json')]
        )

    @http.route('/guardpro/service-worker.js', type='http', auth='public')
    def service_worker(self):
        """Service worker for PWA offline functionality."""
        sw_content = """
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
    const request = indexedDB.open('GuardProDB', 1);
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
"""
        return request.make_response(
            sw_content,
            headers=[('Content-Type', 'application/javascript')]
        )

    @http.route('/guardpro/guards/locations', type='json', auth='user')
    def get_guard_locations(self, **kwargs):
        """Get all active guards' current locations from location history for map display."""
        try:
            from datetime import datetime
            
            # Get all active guards
            guards = request.env['guard.profile'].search([
                ('status', '=', 'active')
            ])
            
            locations = []
            GuardLocationHistory = request.env['guard.location.history']
            
            for guard in guards:
                # Get the most recent location from location history (exclude archived)
                last_location = GuardLocationHistory.search([
                    ('guard_id', '=', guard.id),
                    ('is_archived', '=', False)
                ], order='timestamp desc', limit=1)
                
                if last_location:
                    # Calculate time since last update
                    time_since_update = None
                    if last_location.timestamp:
                        delta = datetime.now() - last_location.timestamp
                        time_since_update = int(delta.total_seconds() / 60)  # minutes
                    
                    # Only include recent locations (within last 30 minutes)
                    if time_since_update is not None and time_since_update <= 30:
                        locations.append({
                            'id': guard.id,
                            'name': guard.name,
                            'badge_number': guard.badge_number,
                            'latitude': last_location.latitude,
                            'longitude': last_location.longitude,
                            'last_update': last_location.timestamp.isoformat() if last_location.timestamp else None,
                            'time_since_update': time_since_update,
                            'current_site': last_location.site_id.name if last_location.site_id else guard.current_site_id.name if guard.current_site_id else 'Unassigned',
                            'current_site_id': last_location.site_id.id if last_location.site_id else guard.current_site_id.id if guard.current_site_id else None,
                            'phone': guard.phone,
                            'status': guard.status,
                        })
            
            return {'success': True, 'locations': locations}
        except Exception as e:
            _logger.error('Error fetching guard locations: %s', str(e))
            return {'success': False, 'error': str(e)}

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
            _logger.error('Error fetching site geofences: %s', str(e))
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
                latitude: Site latitude (optional, updates if provided)
                longitude: Site longitude (optional, updates if provided)
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
                error_response = {'success': False, 'error': 'Site not found'}
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
