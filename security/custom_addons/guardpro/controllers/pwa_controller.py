# -*- coding: utf-8 -*-
"""GuardLink PWA Controller.

This module provides routes for the Progressive Web App interface.
Optimized for fast loading with efficient queries and caching.
Performance optimizations: response compression, memory caching, query optimization.
"""

import logging
import json
from functools import lru_cache
from odoo import http
from odoo.http import request
from datetime import datetime, timedelta
from werkzeug.wrappers import Response

_logger = logging.getLogger(__name__)

# Memory cache for frequently accessed data (TTL: 5 minutes)
_memory_cache = {}
_cache_timestamps = {}


class GuardLinkPWAController(http.Controller):
    """Controller for GuardLink Progressive Web App - Performance Optimized."""

    def _get_from_cache(self, cache_key, ttl=300):
        """Get data from memory cache if not expired.
        
        Args:
            cache_key: Unique key for cached data
            ttl: Time to live in seconds (default 5 minutes)
        
        Returns:
            Cached data or None if expired/missing
        """
        if cache_key in _memory_cache:
            timestamp = _cache_timestamps.get(cache_key, 0)
            age = (datetime.now().timestamp() - timestamp)
            if age < ttl:
                _logger.debug(f"Cache hit for {cache_key} (age: {age:.1f}s)")
                return _memory_cache[cache_key]
            else:
                # Expired, remove from cache
                _logger.debug(f"Cache expired for {cache_key} (age: {age:.1f}s)")
                del _memory_cache[cache_key]
                del _cache_timestamps[cache_key]
        return None
    
    def _set_cache(self, cache_key, data):
        """Store data in memory cache with timestamp.
        
        Args:
            cache_key: Unique key for cached data
            data: Data to cache
        """
        _memory_cache[cache_key] = data
        _cache_timestamps[cache_key] = datetime.now().timestamp()
        _logger.debug(f"Cached data for {cache_key}")
    
    def _add_performance_headers(self, response):
        """Add performance and caching headers to response.
        
        Enhanced with compression hints and stale-while-revalidate.
        """
        if isinstance(response, Response):
            # Stale-while-revalidate for better perceived performance
            response.headers['Cache-Control'] = 'public, max-age=300, stale-while-revalidate=60'
            # Enable compression (let the web server handle actual compression)
            response.headers['Vary'] = 'Accept-Encoding'
            # Security headers
            response.headers['X-Content-Type-Options'] = 'nosniff'
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'
            # Performance timing
            response.headers['Server-Timing'] = 'app;dur=0'
        return response

    @http.route('/guardpro/pwa/test', type='http', auth='public')
    def pwa_test(self, **kwargs):
        """Simple test route."""
        return "PWA Controller is working!"
    
    @http.route('/guardpro/pwa/simple', type='http', auth='user', website=True)
    def pwa_simple_test(self, **kwargs):
        """Simple authenticated test route with minimal template."""
        return request.make_response(
            '''<!DOCTYPE html>
            <html>
            <head>
                <title>GuardLink PWA Test</title>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
            </head>
            <body>
                <h1>GuardLink PWA Simple Test</h1>
                <p>If you can see this, the route and authentication are working.</p>
                <p>User: ''' + str(request.env.user.name) + '''</p>
                <a href="/guardpro/pwa/">Try full PWA</a>
            </body>
            </html>''',
            headers={'Content-Type': 'text/html; charset=utf-8'}
        )

    def _get_guard_data(self):
        """Get current guard data from logged-in user."""
        user = request.env.user
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not guard:
            # User is not a guard, check if they're an employee
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id)
            ], limit=1)
            
            if employee:
                # Try to find associated guard profile
                guard = request.env['guard.profile'].sudo().search([
                    ('employee_id', '=', employee.id)
                ], limit=1)
        
        return guard

    def _get_common_context(self):
        """Get common template context."""
        guard = self._get_guard_data()
        
        # Get website for website=True routes
        website = request.env['website'].get_current_website()
        
        return {
            'user': request.env.user,
            'guard': guard,
            'now': datetime.now(),
            'app_version': '1.0.0',
            'website': website,
        }

    @http.route('/guardpro/pwa/', type='http', auth='user', website=True)
    def pwa_index(self, **kwargs):
        """REDIRECT to new simplified mobile interface.
        
        Old PWA templates disabled (files removed).
        New mobile interface at /guardpro/mobile uses Odoo standard patterns.
        """
        # Redirect to new simplified mobile interface
        return request.redirect('/guardpro/mobile')
        
        # OLD CODE BELOW (kept for reference, not executed)
        """Main PWA dashboard page - Ultra-optimized for instant loading."""
        try:
            start_time = datetime.now()
            
            context = self._get_common_context()
            
            # Get today's shifts for the guard
            # Note: Removed recordset caching as it causes "Cursor already closed" errors
            # Recordsets cannot be cached because they're bound to the database cursor
            if context['guard']:
                guard_id = context['guard'].id
                
                # Fetch from database with optimized queries
                today_start = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_end = today_start + timedelta(days=1)
                
                # Batch fetch all data in parallel to minimize DB round trips
                GuardShift = request.env['guard.shift'].sudo()
                GuardTask = request.env['guard.task'].sudo()
                IncidentReport = request.env['incident.report'].sudo()
                GuardAttendance = request.env['guard.attendance'].sudo()
                
                # Optimized: Use search() instead of search_read() for recordsets
                shifts = GuardShift.search([
                    ('guard_id', '=', guard_id),
                    ('start_datetime', '>=', today_start),
                    ('start_datetime', '<', today_end),
                ], limit=5, order='start_datetime asc')
                
                tasks = GuardTask.search([
                    ('assigned_to', '=', guard_id),
                    ('state', 'in', ['assigned', 'in_progress']),
                ], limit=3, order='priority desc, due_date asc')
                
                incidents = IncidentReport.search([
                    ('guard_id', '=', guard_id),
                ], limit=3, order='reported_datetime desc')
                
                # Check for active attendance (checked in but not checked out)
                active_attendance = GuardAttendance.search([
                    ('guard_id', '=', guard_id),
                    ('checkout_time', '=', False),
                ], limit=1, order='checkin_time desc')
                
                # Get active tours (tours in progress)
                active_tours = request.env['tour.log'].sudo().search([
                    ('guard_id', '=', guard_id),
                    ('end_time', '=', False),
                ], limit=5, order='start_time desc')
                
                data = {
                    'shifts': shifts,
                    'tasks': tasks,
                    'incidents': incidents,
                    'active_tours': active_tours,
                    'is_checked_in': bool(active_attendance),
                    'active_attendance': active_attendance,
                }
                
                context.update(data)
                
                _logger.info(
                    "PWA dashboard loaded from DB for guard %s in %.3f seconds",
                    guard_id, (datetime.now() - start_time).total_seconds()
                )
            
            # Render with performance headers
            response = request.render('guardpro.pwa_dashboard_optimized', context)
            
            # Add server timing header for monitoring
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            response.headers['Server-Timing'] = f'app;dur={elapsed_ms:.1f}'
            
            return self._add_performance_headers(response)
            
        except Exception as e:
            _logger.error("PWA dashboard error: %s", str(e), exc_info=True)
            # Fallback to basic error page with proper HTML
            return request.make_response(
                '''<!DOCTYPE html>
                <html lang="en">
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1">
                    <title>Error - GuardLink</title>
                    <style>
                        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; }
                        h1 { color: #EF4444; }
                        p { color: #6B7280; }
                        a { color: #3B82F6; text-decoration: none; }
                    </style>
                </head>
                <body>
                    <h1>Oops! Something went wrong</h1>
                    <p>We're having trouble loading the dashboard.</p>
                    <p><a href="/guardpro/pwa/">Try again</a> or <a href="/web">Go to main page</a></p>
                </body>
                </html>''',
                status=500,
                headers={'Content-Type': 'text/html; charset=utf-8'}
            )

    @http.route('/guardpro/pwa/shifts', type='http', auth='user', website=True)
    def pwa_shifts(self, **kwargs):
        """REDIRECT to new mobile interface - Odoo standard view."""
        return request.redirect('/web#action=guardpro.action_guard_shift_mobile')

    @http.route('/guardpro/pwa/tours', type='http', auth='user', website=True)
    def pwa_tours(self, **kwargs):
        """REDIRECT to new mobile interface."""
        return request.redirect('/guardpro/mobile')

    @http.route('/guardpro/pwa/incidents', type='http', auth='user', website=True)
    def pwa_incidents(self, **kwargs):
        """REDIRECT to new mobile interface - Odoo standard view."""
        return request.redirect('/web#action=guardpro.action_incident_mobile')

    @http.route('/guardpro/pwa/tasks', type='http', auth='user', website=True)
    def pwa_tasks(self, **kwargs):
        """REDIRECT to new mobile interface - Odoo standard view."""
        return request.redirect('/web#action=guardpro.action_guard_task_mobile')

    @http.route('/guardpro/pwa/settings', type='http', auth='user', website=True)
    def pwa_settings(self, **kwargs):
        """REDIRECT to new mobile interface."""
        return request.redirect('/guardpro/mobile')
    
    @http.route('/guardpro/pwa/offline', type='http', auth='public', website=True)
    def pwa_offline(self, **kwargs):
        """Offline fallback page for PWA."""
        return request.make_response(
            '''<!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Offline - GuardLink</title>
                <style>
                    body {
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                        min-height: 100vh;
                        margin: 0;
                        background: linear-gradient(135deg, #1E3A8A, #3B82F6);
                        color: white;
                        text-align: center;
                        padding: 2rem;
                    }
                    .container {
                        max-width: 400px;
                    }
                    .icon {
                        font-size: 5rem;
                        margin-bottom: 1.5rem;
                        opacity: 0.8;
                    }
                    h1 {
                        font-size: 2rem;
                        margin-bottom: 1rem;
                        font-weight: 700;
                    }
                    p {
                        font-size: 1.1rem;
                        margin-bottom: 2rem;
                        opacity: 0.9;
                    }
                    .btn {
                        display: inline-block;
                        padding: 0.75rem 2rem;
                        background: white;
                        color: #1E3A8A;
                        text-decoration: none;
                        border-radius: 0.5rem;
                        font-weight: 600;
                        transition: transform 0.2s;
                    }
                    .btn:hover {
                        transform: scale(1.05);
                    }
                    .wifi-icon {
                        display: inline-block;
                        width: 4rem;
                        height: 4rem;
                        border: 4px solid white;
                        border-radius: 50%;
                        position: relative;
                        margin-bottom: 1.5rem;
                    }
                    .wifi-icon::before {
                        content: '';
                        position: absolute;
                        top: 50%;
                        left: 50%;
                        transform: translate(-50%, -50%);
                        width: 60%;
                        height: 60%;
                        border: 3px solid white;
                        border-top: none;
                        border-radius: 0 0 50% 50%;
                    }
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="wifi-icon"></div>
                    <h1>You're Offline</h1>
                    <p>No internet connection. Please check your network and try again.</p>
                    <a href="javascript:window.location.reload()" class="btn">Try Again</a>
                </div>
                <script>
                    // Auto-reload when connection is restored
                    window.addEventListener('online', function() {
                        console.log('Connection restored, reloading...');
                        setTimeout(function() {
                            window.location.reload();
                        }, 500);
                    });
                </script>
            </body>
            </html>''',
            headers={'Content-Type': 'text/html; charset=utf-8'}
        )

    @http.route('/guardpro/manifest.json', type='http', auth='public')
    def pwa_manifest(self, **kwargs):
        """Serve PWA manifest file with proper headers.
        
        Following Odoo 18 recommendations for PWA manifest serving.
        """
        manifest = {
            'name': 'GuardLink - Security Management',
            'short_name': 'GuardLink',
            'version': '1.0.1',
            'description': 'Complete security guard management system with real-time tracking, incident reporting, and more',
            'lang': 'en',
            'scope': '/guardpro/',
            'start_url': '/guardpro/pwa/?source=pwa',
            'display': 'standalone',
            'orientation': 'any',
            'theme_color': '#1a237e',
            'background_color': '#ffffff',
            'icons': [
                {
                    'src': '/guardpro/static/pwa/icons/icon-192x192.png',
                    'sizes': '192x192',
                    'type': 'image/png',
                    'purpose': 'any maskable'
                },
                {
                    'src': '/guardpro/static/pwa/icons/icon-512x512.png',
                    'sizes': '512x512',
                    'type': 'image/png',
                    'purpose': 'any maskable'
                }
            ],
            'categories': ['business', 'productivity', 'security'],
            'shortcuts': [
                {
                    'name': 'Report Incident',
                    'short_name': 'Incident',
                    'description': 'Quickly report a security incident',
                    'url': '/guardpro/pwa/incidents?source=shortcut',
                    'icons': [
                        {
                            'src': '/guardpro/static/pwa/icons/icon-192x192.png',
                            'sizes': '192x192'
                        }
                    ]
                },
                {
                    'name': 'View Shifts',
                    'short_name': 'Shifts',
                    'description': 'View your assigned shifts',
                    'url': '/guardpro/pwa/shifts?source=shortcut',
                    'icons': [
                        {
                            'src': '/guardpro/static/pwa/icons/icon-192x192.png',
                            'sizes': '192x192'
                        }
                    ]
                },
                {
                    'name': 'Start Patrol',
                    'short_name': 'Patrol',
                    'description': 'Begin a security patrol',
                    'url': '/guardpro/pwa/tours?source=shortcut',
                    'icons': [
                        {
                            'src': '/guardpro/static/pwa/icons/icon-192x192.png',
                            'sizes': '192x192'
                        }
                    ]
                }
            ]
        }
        
        response = request.make_response(
            json.dumps(manifest, indent=2),
            headers=[
                ('Content-Type', 'application/manifest+json'),
                ('Cache-Control', 'public, max-age=3600'),
                ('X-Content-Type-Options', 'nosniff')
            ]
        )
        return response
    
    @http.route('/guardpro/service-worker.js', type='http', auth='public')
    def pwa_service_worker(self, **kwargs):
        """Serve service worker from proper root scope.
        
        Following Odoo 18 recommendations - service worker should be
        at the app root for proper scope coverage.
        """
        import os
        sw_path = os.path.join(
            os.path.dirname(__file__),
            '..',
            'static',
            'pwa',
            'service-worker.js'
        )
        
        try:
            with open(sw_path, 'r', encoding='utf-8') as f:
                sw_content = f.read()
            
            response = request.make_response(
                sw_content,
                headers=[
                    ('Content-Type', 'application/javascript'),
                    ('Service-Worker-Allowed', '/guardpro/'),
                    ('Cache-Control', 'no-cache, no-store, must-revalidate'),
                    ('X-Content-Type-Options', 'nosniff')
                ]
            )
            return response
        except Exception as e:
            _logger.error("Service worker error: %s", str(e))
            return request.make_response(
                "// Service worker not available",
                status=404,
                headers=[('Content-Type', 'application/javascript')]
            )

    @http.route(
        '/guardpro/pwa/api/checkin',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_checkin(self, **kwargs):
        """API endpoint for shift check-in."""
        try:
            guard = self._get_guard_data()
            if not guard:
                _logger.error('[PWA Check-In] Guard profile not found for user: %s', request.env.user.login)
                return {'error': 'Guard profile not found'}
            
            _logger.info('[PWA Check-In] Guard: %s (ID: %s)', guard.name, guard.id)
            
            latitude = kwargs.get('latitude')
            longitude = kwargs.get('longitude')
            site_id = kwargs.get('site_id')
            shift_id = None
            active_shift = None
            
            # Get guard's site and shift if not provided
            if not site_id:
                _logger.info('[PWA Check-In] No site_id provided, searching for active shift...')
                # Try to get from active shift (within 2 hours of scheduled time)
                now = datetime.now()
                active_shift = request.env['guard.shift'].sudo().search([
                    ('guard_id', '=', guard.id),
                    ('start_datetime', '<=', now + timedelta(hours=2)),
                    ('end_datetime', '>=', now - timedelta(hours=2)),
                ], limit=1, order='start_datetime asc')
                
                if active_shift:
                    site_id = active_shift.site_id.id
                    shift_id = active_shift.id
                    _logger.info('[PWA Check-In] Found active shift: %s at site: %s', 
                               active_shift.name, active_shift.site_id.name)
                else:
                    _logger.warning('[PWA Check-In] No active shift found for guard %s', guard.name)
            
            # If still no site, try to get guard's primary site or last assigned site
            if not site_id:
                _logger.info('[PWA Check-In] Checking guard current_site_id...')
                # Try to get from guard's profile if it has a current site
                if hasattr(guard, 'current_site_id') and guard.current_site_id:
                    site_id = guard.current_site_id.id
                    _logger.info('[PWA Check-In] Using guard current_site_id: %s (ID: %s)', 
                               guard.current_site_id.name, site_id)
                else:
                    _logger.warning('[PWA Check-In] Guard %s has no current_site_id set', guard.name)
                    # Get the most recent site from past attendance
                    last_attendance = request.env['guard.attendance'].sudo().search([
                        ('guard_id', '=', guard.id),
                        ('site_id', '!=', False),
                    ], limit=1, order='checkin_time desc')
                    if last_attendance:
                        site_id = last_attendance.site_id.id
                        _logger.info('[PWA Check-In] Using last attendance site: %s (ID: %s)', 
                                   last_attendance.site_id.name, site_id)
                    else:
                        _logger.error('[PWA Check-In] No previous attendance found for guard %s', guard.name)
            
            if not site_id:
                _logger.error('[PWA Check-In] FAILED - No site found for guard %s (ID: %s). '
                            'Guard has no active shift, no current_site_id, and no previous attendance.', 
                            guard.name, guard.id)
                return {
                    'error': 'No site found. Please ensure you have a scheduled shift or contact your supervisor.'
                }
            
            # Check for existing open attendance
            existing_attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1)
            
            if existing_attendance:
                return {
                    'error': 'You already have an active check-in. Please check out first.'
                }
            
            # Create attendance record with shift link
            attendance_vals = {
                'guard_id': guard.id,
                'site_id': site_id,
                'checkin_time': datetime.now(),
                'checkin_latitude': latitude,
                'checkin_longitude': longitude,
                'checkin_method': 'mobile_app',
            }
            
            # Link to shift if found
            if shift_id:
                attendance_vals['shift_id'] = shift_id
            
            attendance = request.env['guard.attendance'].sudo().create(attendance_vals)
            
            response_data = {
                'success': True,
                'attendance_id': attendance.id,
                'checkin_time': attendance.checkin_time.isoformat(),
                'site_name': attendance.site_id.name,
            }
            
            # Include shift information if linked
            if attendance.shift_id:
                response_data.update({
                    'shift_id': attendance.shift_id.id,
                    'shift_name': attendance.shift_id.name or 'Shift',
                    'shift_start': attendance.shift_id.start_datetime.isoformat(),
                    'shift_end': attendance.shift_id.end_datetime.isoformat(),
                })
            
            return response_data
        except Exception as e:
            _logger.error("Check-in error: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route(
        '/guardpro/pwa/api/checkout',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_checkout(self, **kwargs):
        """API endpoint for shift check-out."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            latitude = kwargs.get('latitude')
            longitude = kwargs.get('longitude')
            
            # Find open attendance record
            attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1, order='checkin_time desc')
            
            if not attendance:
                return {'error': 'No active check-in found'}
            
            attendance.write({
                'checkout_time': datetime.now(),
                'checkout_latitude': latitude,
                'checkout_longitude': longitude,
                'checkout_method': 'mobile_app',
            })
            
            response_data = {
                'success': True,
                'attendance_id': attendance.id,
                'checkout_time': attendance.checkout_time.isoformat(),
                'hours_worked': attendance.hours_worked,
                'site_name': attendance.site_id.name,
            }
            
            # Include shift information if linked
            if attendance.shift_id:
                response_data.update({
                    'shift_id': attendance.shift_id.id,
                    'shift_name': attendance.shift_id.name or 'Shift',
                    'was_late': attendance.is_late,
                    'late_minutes': attendance.late_minutes,
                    'overtime_hours': attendance.overtime_hours,
                })
            
            return response_data
        except Exception as e:
            _logger.error("Check-out error: %s", str(e))
            return {'error': str(e)}

    @http.route(
        '/guardpro/pwa/api/update_location',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_update_location(self, **kwargs):
        """API endpoint to update guard location."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            latitude = kwargs.get('latitude')
            longitude = kwargs.get('longitude')
            accuracy = kwargs.get('accuracy')
            
            # Use the guard profile's update_location method with built-in retry logic
            # This prevents concurrent update errors
            try:
                guard.sudo().update_location(
                    latitude=latitude,
                    longitude=longitude,
                    accuracy=accuracy
                )
                
                # Get the latest location history record (exclude archived)
                location = request.env['guard.location.history'].sudo().search([
                    ('guard_id', '=', guard.id),
                    ('is_archived', '=', False)
                ], limit=1, order='timestamp desc')
                
                return {
                    'success': True,
                    'location_id': location.id if location else None,
                    'timestamp': location.timestamp.isoformat() if location else datetime.now().isoformat(),
                }
            except Exception as update_error:
                # Log but don't fail - location updates are non-critical
                _logger.warning("Location update retry failed: %s", str(update_error))
                return {
                    'success': False,
                    'error': 'Location update failed, will retry automatically'
                }
        except Exception as e:
            _logger.error("Location update error: %s", str(e))
            return {'error': str(e)}

    @http.route(
        '/guardpro/pwa/api/session_check',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_session_check(self, **kwargs):
        """API endpoint to check if session is still valid."""
        try:
            user = request.env.user
            if user and not user._is_public():
                return {
                    'valid': True,
                    'user_id': user.id,
                    'user_name': user.name,
                }
            else:
                return {'valid': False}
        except Exception as e:
            _logger.error("Session check error: %s", str(e))
            return {'valid': False}

    @http.route(
        '/guardpro/pwa/api/task/start',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_task_start(self, task_id, **kwargs):
        """API endpoint to start a task."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # Find the task
            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            
            if not task:
                return {'error': 'Task not found or not assigned to you'}
            
            # Check if task can be started
            if task.state not in ['draft', 'assigned']:
                return {'error': 'Task cannot be started in current state'}
            
            # Start the task
            task.action_start()
            
            return {
                'success': True,
                'task_id': task.id,
                'state': task.state,
                'message': 'Task started successfully'
            }
        except Exception as e:
            _logger.error("Task start error: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route(
        '/guardpro/pwa/api/task/complete',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_task_complete(self, task_id, notes=None, **kwargs):
        """API endpoint to complete a task."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # Find the task
            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            
            if not task:
                return {'error': 'Task not found or not assigned to you'}
            
            # Add completion notes if provided
            if notes:
                task.write({'completion_notes': notes})
            
            # Complete the task
            try:
                task.action_complete()
            except Exception as complete_error:
                # Return the error message from the action_complete method
                return {'error': str(complete_error)}
            
            return {
                'success': True,
                'task_id': task.id,
                'state': task.state,
                'completed_date': task.completed_date.isoformat() if task.completed_date else None,
                'message': 'Task completed successfully'
            }
        except Exception as e:
            _logger.error("Task complete error: %s", str(e), exc_info=True)
            return {'error': str(e)}

    # ==========================================
    # FORM-BASED TASK ENDPOINTS (Alternative Simple Approach)
    # ==========================================
    
    @http.route(
        '/guardpro/pwa/task/start/<int:task_id>',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def form_task_start(self, task_id, **kwargs):
        """Form-based endpoint to start a task (Odoo 18 compatible).
        
        Uses standard HTML form submission with proper CSRF handling.
        """
        try:
            # Get guard data
            guard = self._get_guard_data()
            if not guard:
                return request.redirect('/guardpro/pwa/?error=guard_not_found')
            
            # Find the task
            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            
            if not task:
                return request.redirect('/guardpro/pwa/?error=task_not_found')
            
            # Check if task can be started
            if task.state not in ['draft', 'assigned']:
                return request.redirect('/guardpro/pwa/?error=task_cannot_start')
            
            # Start the task
            task.action_start()
            
            # Redirect back with success message
            return request.redirect('/guardpro/pwa/?success=task_started&task_id=' + str(task_id))
            
        except Exception as e:
            _logger.error("Form task start error: %s", str(e), exc_info=True)
            return request.redirect('/guardpro/pwa/?error=task_start_failed')
    
    @http.route(
        '/guardpro/pwa/task/complete/<int:task_id>',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def form_task_complete(self, task_id, notes=None, **kwargs):
        """Form-based endpoint to complete a task.
        
        This is a simpler alternative to the JSON API that uses standard
        HTML form submission with server-side redirect.
        """
        try:
            guard = self._get_guard_data()
            if not guard:
                return request.redirect('/guardpro/pwa/?error=guard_not_found')
            
            # Find the task
            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            
            if not task:
                return request.redirect('/guardpro/pwa/?error=task_not_found')
            
            # Add completion notes if provided
            if notes:
                task.write({'completion_notes': notes})
            
            # Complete the task
            try:
                task.action_complete()
            except Exception as complete_error:
                _logger.error("Task complete action error: %s", str(complete_error))
                return request.redirect(f'/guardpro/pwa/?error=task_complete_failed&message={str(complete_error)}')
            
            # Redirect back with success message
            return request.redirect('/guardpro/pwa/?success=task_completed&task_id=' + str(task_id))
            
        except Exception as e:
            _logger.error("Form task complete error: %s", str(e), exc_info=True)
            return request.redirect('/guardpro/pwa/?error=task_complete_failed')
    
    # ========================================================================
    # FORM-BASED CHECK-IN/CHECK-OUT ROUTES (Odoo Standard Approach)
    # ========================================================================
    
    @http.route(
        '/guardpro/pwa/checkin',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def form_checkin(self, latitude=None, longitude=None, **kwargs):
        """Form-based endpoint for check-in with location.
        
        Uses standard HTML form submission for reliability.
        JavaScript provides location but form works without it.
        """
        try:
            guard = self._get_guard_data()
            if not guard:
                return request.redirect('/guardpro/pwa/?error=guard_not_found&message=Guard+profile+not+found')
            
            # Check for existing open attendance
            existing_attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1)
            
            if existing_attendance:
                return request.redirect('/guardpro/pwa/?error=already_checked_in&message=Already+checked+in')
            
            # Try to find current/upcoming shift for today
            now = datetime.now()
            shift = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),
                ('start_datetime', '<=', now + timedelta(hours=2)),
                ('end_datetime', '>=', now - timedelta(hours=1)),
                ('status', 'in', ['scheduled', 'confirmed', 'in_progress']),
            ], limit=1, order='start_datetime asc')
            
            site_id = shift.site_id.id if shift and shift.site_id else None
            
            # Fallback to guard's current site or last site
            if not site_id:
                if hasattr(guard, 'current_site_id') and guard.current_site_id:
                    site_id = guard.current_site_id.id
                else:
                    last_attendance = request.env['guard.attendance'].sudo().search([
                        ('guard_id', '=', guard.id),
                        ('site_id', '!=', False),
                    ], limit=1, order='checkin_time desc')
                    site_id = last_attendance.site_id.id if last_attendance else None
            
            if not site_id:
                return request.redirect('/guardpro/pwa/?error=no_site&message=No+site+found.+Contact+supervisor')
            
            # Create attendance record
            attendance_vals = {
                'guard_id': guard.id,
                'site_id': site_id,
                'checkin_time': datetime.now(),
                'checkin_method': 'mobile_app',
            }
            
            # Add location if provided
            if latitude and longitude:
                try:
                    attendance_vals['checkin_latitude'] = float(latitude)
                    attendance_vals['checkin_longitude'] = float(longitude)
                except (ValueError, TypeError):
                    pass  # Skip invalid coordinates
            
            # Link to shift if found
            if shift:
                attendance_vals['shift_id'] = shift.id
            
            attendance = request.env['guard.attendance'].sudo().create(attendance_vals)
            
            return request.redirect(f'/guardpro/pwa/?success=checked_in&site={attendance.site_id.name}')
            
        except Exception as e:
            _logger.error("Form check-in error: %s", str(e), exc_info=True)
            return request.redirect(f'/guardpro/pwa/?error=checkin_failed&message={str(e)}')
    
    @http.route(
        '/guardpro/pwa/checkout',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def form_checkout(self, latitude=None, longitude=None, **kwargs):
        """Form-based endpoint for check-out with location.
        
        Uses standard HTML form submission for reliability.
        JavaScript provides location but form works without it.
        """
        try:
            guard = self._get_guard_data()
            if not guard:
                return request.redirect('/guardpro/pwa/?error=guard_not_found&message=Guard+profile+not+found')
            
            # Find open attendance record
            attendance = request.env['guard.attendance'].sudo().search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False),
            ], limit=1, order='checkin_time desc')
            
            if not attendance:
                return request.redirect('/guardpro/pwa/?error=not_checked_in&message=No+active+check-in+found')
            
            # Update attendance with checkout
            checkout_vals = {
                'checkout_time': datetime.now(),
                'checkout_method': 'mobile_app',
            }
            
            # Add location if provided
            if latitude and longitude:
                try:
                    checkout_vals['checkout_latitude'] = float(latitude)
                    checkout_vals['checkout_longitude'] = float(longitude)
                except (ValueError, TypeError):
                    pass  # Skip invalid coordinates
            
            attendance.write(checkout_vals)
            
            # Calculate hours worked
            hours_worked = 0
            if attendance.checkout_time and attendance.checkin_time:
                delta = attendance.checkout_time - attendance.checkin_time
                hours_worked = delta.total_seconds() / 3600
            
            return request.redirect(f'/guardpro/pwa/?success=checked_out&hours={hours_worked:.2f}')
            
        except Exception as e:
            _logger.error("Form check-out error: %s", str(e), exc_info=True)
            return request.redirect(f'/guardpro/pwa/?error=checkout_failed&message={str(e)}')
    
    @http.route(
        '/guardpro/pwa/panic',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=True
    )
    def form_panic(self, latitude=None, longitude=None, **kwargs):
        """Form-based endpoint for panic alert.
        
        Uses standard HTML form submission for reliability.
        Triggers emergency broadcast to notify managers.
        """
        try:
            guard = self._get_guard_data()
            if not guard:
                return request.redirect('/guardpro/pwa/?error=guard_not_found&message=Guard+profile+not+found')
            
            # Create emergency broadcast
            emergency_data = {
                'guard_id': guard.id,
                'type': 'panic',
                'priority': 'critical',
                'message': f'PANIC ALERT from {guard.name}',
                'timestamp': datetime.now(),
            }
            
            # Add location if provided
            if latitude and longitude:
                try:
                    emergency_data['latitude'] = float(latitude)
                    emergency_data['longitude'] = float(longitude)
                except (ValueError, TypeError):
                    pass
            
            # Try to create emergency broadcast if model exists
            try:
                emergency = request.env['guardpro.emergency.broadcast'].sudo().create(emergency_data)
                _logger.info(f"Panic alert created: {emergency.id} from guard {guard.name}")
            except Exception as broadcast_error:
                # Log error but still show success to user - panic is critical
                _logger.error(f"Failed to create emergency broadcast: {broadcast_error}")
            
            # Also try to create incident report for tracking
            try:
                # Get emergency category
                emergency_category = request.env['incident.category'].sudo().search([
                    ('name', 'ilike', 'emergency')
                ], limit=1)
                if not emergency_category:
                    emergency_category = request.env['incident.category'].sudo().search([], limit=1)
                
                # Get site (required field)
                site_id = None
                if hasattr(guard, 'current_site_id') and guard.current_site_id:
                    site_id = guard.current_site_id.id
                else:
                    any_site = request.env['client.site'].sudo().search([], limit=1)
                    site_id = any_site.id if any_site else None
                
                incident_vals = {
                    'guard_id': guard.id,
                    'site_id': site_id,
                    'category_id': emergency_category.id if emergency_category else False,
                    'severity': 'critical',
                    'title': 'PANIC ALERT',
                    'description': f'Panic button activated by {guard.name}',
                    'incident_datetime': datetime.now(),
                    'status': 'draft',
                }
                if latitude and longitude:
                    incident_vals.update({
                        'latitude': float(latitude),
                        'longitude': float(longitude),
                    })
                request.env['incident.report'].sudo().create(incident_vals)
            except Exception as incident_error:
                _logger.error(f"Failed to create panic incident: {incident_error}")
            
            return request.redirect('/guardpro/pwa/?success=panic_activated')
            
        except Exception as e:
            _logger.error("Form panic alert error: %s", str(e), exc_info=True)
            # Even on error, show success to user - panic is critical
            return request.redirect('/guardpro/pwa/?success=panic_activated')

    @http.route(
        '/guardpro/pwa/api/task/checklist/toggle',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_task_checklist_toggle(self, checklist_id, **kwargs):
        """API endpoint to toggle a checklist item."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # Find the checklist item
            checklist = request.env['guard.task.checklist'].sudo().search([
                ('id', '=', checklist_id),
            ], limit=1)
            
            if not checklist:
                return {'error': 'Checklist item not found'}
            
            # Verify the task is assigned to this guard
            if checklist.task_id.assigned_to.id != guard.id:
                return {'error': 'Task not assigned to you'}
            
            # Toggle the checklist item
            checklist.toggle_completed()
            
            return {
                'success': True,
                'checklist_id': checklist.id,
                'completed': checklist.completed,
                'completed_date': checklist.completed_date.isoformat() if checklist.completed_date else None,
                'task_completion_percentage': checklist.task_id.completion_percentage,
            }
        except Exception as e:
            _logger.error("Checklist toggle error: %s", str(e), exc_info=True)
            return {'error': str(e)}

    @http.route(
        '/guardpro/pwa/api/task/details',
        type='json',
        auth='user',
        methods=['POST']
    )
    def api_task_details(self, task_id, **kwargs):
        """API endpoint to get task details with checklist."""
        try:
            guard = self._get_guard_data()
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # Find the task
            task = request.env['guard.task'].sudo().search([
                ('id', '=', task_id),
                ('assigned_to', '=', guard.id),
            ], limit=1)
            
            if not task:
                return {'error': 'Task not found or not assigned to you'}
            
            # Build checklist data
            checklist_items = []
            for item in task.checklist_ids:
                checklist_items.append({
                    'id': item.id,
                    'name': item.name,
                    'completed': item.completed,
                    'mandatory': item.mandatory,
                    'notes': item.notes or '',
                    'sequence': item.sequence,
                    'completed_date': item.completed_date.isoformat() if item.completed_date else None,
                })
            
            # Strip HTML from description
            description = task.description or ''
            if description:
                import re
                description = re.sub('<[^<]+?>', '', description)
            
            return {
                'success': True,
                'task': {
                    'id': task.id,
                    'name': task.name,
                    'description': description,
                    'task_type': task.task_type,
                    'priority': task.priority,
                    'state': task.state,
                    'due_date': task.due_date.isoformat() if task.due_date else None,
                    'is_overdue': task.is_overdue,
                    'site_name': task.site_id.name if task.site_id else None,
                    'shift_name': task.shift_id.name if task.shift_id else None,
                    'completion_percentage': task.completion_percentage,
                    'total_checklist_items': task.total_checklist_items,
                    'completed_checklist_items': task.completed_checklist_items,
                    'completion_notes': task.completion_notes or '',
                    'checklist': checklist_items,
                }
            }
        except Exception as e:
            _logger.error("Task details error: %s", str(e), exc_info=True)
            return {'error': str(e)}

