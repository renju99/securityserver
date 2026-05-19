# -*- coding: utf-8 -*-
"""Mobile API Controllers."""

from odoo import http, fields
from odoo.http import request, Response
from odoo.exceptions import UserError, AccessError, ValidationError
import json
import logging
import base64
import time
import psycopg2
import html
import re
from datetime import datetime
from ..common import validators
from ..common.rate_limiter import rate_limit
from ..common.video_optimizer import VideoOptimizer

_logger = logging.getLogger(__name__)


class MobileAPIController(http.Controller):
    """Mobile app API endpoints."""

    def _check_auth(self):
        """Check if user is authenticated."""
        if not request.env.user or request.env.user._is_public():
            return {'error': 'Authentication required'}, 401
        return None, None

    def _is_video_payload(self, payload):
        """Detect whether JSON attachment payload contains a video."""
        name = (payload.get('name') or '').lower()
        mimetype = (payload.get('mimetype') or payload.get('content_type') or '').lower()
        if mimetype.startswith('video/'):
            return True
        return name.endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.m4v', '.3gp'))

    def _incident_photos_videos_payload(self, incident):
        """Build photo/video metadata for native app (relative paths; prepend base URL on device)."""
        photos = []
        for att in incident.photo_ids:
            photos.append({
                'id': att.id,
                'name': att.name,
                'mimetype': att.mimetype or 'image/jpeg',
                'url': '/web/image/ir.attachment/%s/datas' % att.id,
            })
        videos = []
        for att in incident.video_ids:
            videos.append({
                'id': att.id,
                'name': att.name,
                'mimetype': att.mimetype or 'video/mp4',
                'url': '/web/content/ir.attachment/%s/datas?download=true' % att.id,
            })
        return photos, videos

    @http.route('/guardpro/api/guard/profile', type='json', auth='user', methods=['POST'], csrf=False)
    def get_guard_profile(self):
        """Get current guard profile."""
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found'}
        
        return {
            'id': guard.id,
            'name': guard.name,
            'badge_number': guard.badge_number,
            'phone': guard.phone,
            'status': guard.status,
            'current_site': guard.current_site_id.name if guard.current_site_id else None
        }

    @http.route('/guardpro/api/shifts/today', type='json', auth='user', methods=['POST'], csrf=False)
    def get_today_shifts(self):
        """Get today's shifts for current guard."""
        user = request.env.user
        _logger.debug('Getting shifts for user: %s (ID: %s)', user.name, user.id)
        
        # Check if guard profile exists for current user
        # Use sudo() to allow guards to access their own profile regardless of site assignment
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not guard:
            _logger.warning('[Guard Pro] No guard profile found for user: %s', user.name)
            return {
                'error': 'No guard profile found. Please contact your administrator to set up your guard profile.',
                'shifts': []
            }
        
        _logger.debug('[Guard Pro] Found guard profile: %s (ID: %s)', guard.name, guard.id)
        
        from datetime import datetime, timedelta
        import pytz
        
        # Get user's timezone
        user_tz_str = request.env.user.tz or 'UTC'
        tz = pytz.timezone(user_tz_str)
        _logger.debug('[Guard Pro] User timezone: %s', user_tz_str)
        
        # Get today's date in user's timezone
        now_utc = pytz.UTC.localize(datetime.utcnow())
        now_tz = now_utc.astimezone(tz)
        
        # Get start and end of today in user's timezone, then convert to UTC
        today_start_tz = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end_tz = today_start_tz + timedelta(days=1)
        
        # Convert to UTC for database query
        today_start = today_start_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        today_end = today_end_tz.astimezone(pytz.UTC).replace(tzinfo=None)
        
        _logger.debug('[Guard Pro] Today range (user TZ): %s to %s', today_start_tz, today_end_tz)
        _logger.debug('[Guard Pro] Today range (UTC for DB): %s to %s', today_start, today_end)
        
        # Debug: Check total shifts for this guard (any date)
        all_guard_shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id)
        ], limit=10, order='start_datetime desc')
        _logger.debug('[Guard Pro] Total shifts found for guard %s: %d (showing last 10)', 
                     guard.name, request.env['guard.shift'].sudo().search_count([('guard_id', '=', guard.id)]))
        for s in all_guard_shifts[:5]:  # Log last 5 shifts
            _logger.debug('[Guard Pro] Sample shift: ID=%d, %s, Start=%s, End=%s, Status=%s', 
                         s.id, s.name, s.start_datetime, s.end_datetime, s.status)
        
        # SECURITY FIX: Only show shifts for THIS guard, not all guards at their sites
        # Use sudo() to allow guards to access their own shifts regardless of site assignment
        # Include all statuses except cancelled and no_show to ensure shifts are visible
        shifts = request.env['guard.shift'].sudo().search([
            ('guard_id', '=', guard.id),         # ✅ Only this guard's shifts
            ('start_datetime', '<', today_end),  # Starts before end of today
            ('end_datetime', '>', today_start),  # Ends after start of today
            ('status', '!=', 'cancelled')        # Exclude cancelled shifts
        ], order='start_datetime asc')
        
        _logger.debug('[Guard Pro] Found %d shift(s) for guard %s on %s (timezone: %s)', 
                     len(shifts), guard.name, now_tz.date(), tz.zone)
        
        # Log details of each shift found
        for shift in shifts:
            _logger.debug('[Guard Pro] Shift %d: %s at %s from %s to %s (status: %s)', 
                         shift.id, shift.name, shift.site_id.name if shift.site_id else 'No Site',
                         shift.start_datetime, shift.end_datetime, shift.status)
        
        # Also log the search domain for debugging
        _logger.debug('[Guard Pro] Search domain: guard_id=%s, start_datetime<%s, end_datetime>%s', 
                     guard.id, today_end, today_start)
        
        # Convert datetime values from UTC (as stored in DB) to user's timezone
        def convert_to_user_tz(dt):
            """Convert naive datetime (stored as UTC) to user's timezone."""
            if not dt:
                return None
            # Odoo stores datetimes as naive UTC, so we need to localize as UTC first
            dt_utc = pytz.UTC.localize(dt) if dt.tzinfo is None else dt
            dt_tz = dt_utc.astimezone(tz)
            return dt_tz
        
        return {
            'shifts': [{
                'id': s.id,
                'site': s.site_id.name if s.site_id else 'No Site',
                'start': convert_to_user_tz(s.start_datetime).isoformat() if s.start_datetime else None,
                'end': convert_to_user_tz(s.end_datetime).isoformat() if s.end_datetime else None,
                'status': s.status,
                'type': s.assignment_type,
                'duration': s.duration,
                'total_hours_worked': s.total_hours_worked,
                'remaining_hours': s.remaining_hours,
                'attendance_count': s.attendance_count,
                'has_active_checkin': any(a.status == 'checked_in' for a in s.attendance_ids)
            } for s in shifts]
        }

    @rate_limit(max_requests=10, window_seconds=60)  # Max 10 shift starts per minute
    @http.route('/guardpro/api/shift/checkin', type='json', auth='user', methods=['POST'], csrf=False)
    def shift_checkin(self, shift_id=None, latitude=None, longitude=None, checkpoint_scan_id=None, photo=None):
        """Start shift with retry logic for database concurrency and physical verification support."""
        # Validate input parameters
        valid, error, validated = validators.validate_shift_checkin_params({
            'shift_id': shift_id,
            'latitude': latitude,
            'longitude': longitude
        })
        
        if not valid:
            return validators.create_error_response(error)
        
        # Extract validated parameters
        shift_id = validated['shift_id']
        latitude = validated['latitude']
        longitude = validated['longitude']
        
        # Retry up to 3 times for database serialization errors
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # Use a new cursor/transaction for each retry
                with request.env.registry.cursor() as new_cr:
                    new_env = request.env(cr=new_cr)
                    shift = new_env['guard.shift'].browse(shift_id)
                    
                    if not shift.exists():
                        return validators.create_error_response('Shift not found', 'NOT_FOUND')
                    
                    # SECURITY FIX: Verify shift belongs to current user's guard profile
                    guard = new_env['guard.profile'].search([
                        ('user_id', '=', new_env.user.id)
                    ], limit=1)
                    
                    if not guard:
                        return validators.create_error_response('Guard profile not found', 'NOT_FOUND')
                    
                    if shift.guard_id.id != guard.id:
                        _logger.warning(
                            'Unauthorized shift start attempt: User %s (Guard %s) tried to start shift %s belonging to Guard %s',
                            new_env.user.login, guard.name, shift_id, shift.guard_id.name
                        )
                        return validators.create_error_response(
                            'Unauthorized: This shift is not assigned to you',
                            'ACCESS_DENIED'
                        )
                    
                    # Call checkin with physical verification parameters
                    result = shift.action_checkin(
                        latitude=latitude,
                        longitude=longitude,
                        checkpoint_scan_id=checkpoint_scan_id,
                        photo=photo
                    )
                    
                    # Commit the transaction
                    new_cr.commit()
                    
                    # Ensure result has success flag
                    if isinstance(result, dict):
                        if 'error' not in result and 'success' not in result:
                            result['success'] = True
                        return result
                    
                    return validators.create_success_response(message='Shift started successfully')
                    
            except psycopg2.extensions.TransactionRollbackError:
                # Serialization error - retry
                if attempt < max_retries - 1:
                    _logger.info('Shift start serialization error, retrying (attempt %d/%d)', attempt + 1, max_retries)
                    time.sleep(0.1 * (attempt + 1))  # Exponential backoff
                    continue
                else:
                    _logger.error('Shift start failed after %d retries due to database concurrency', max_retries)
                    return validators.create_error_response(
                        'Unable to start shift due to high system activity. Please try again.',
                        'CONCURRENCY_ERROR'
                    )
            except ValidationError as e:
                _logger.warning('Shift start validation error: %s', str(e))
                return validators.create_error_response(str(e), 'VALIDATION_ERROR')
            except AccessError as e:
                _logger.warning('Shift start access denied: %s', str(e))
                return validators.create_error_response('Access denied', 'ACCESS_DENIED')
            except UserError as e:
                _logger.info('Shift start user error: %s', str(e))
                return validators.create_error_response(str(e), 'USER_ERROR')
            except Exception as e:
                _logger.exception('Unexpected shift start error')
                return validators.create_error_response(
                    'An unexpected error occurred. Please try again.',
                    'INTERNAL_ERROR'
                )

    @rate_limit(max_requests=10, window_seconds=60)  # Max 10 shift ends per minute
    @http.route('/guardpro/api/shift/checkout', type='json', auth='user', methods=['POST'], csrf=False)
    def shift_checkout(self, shift_id=None, latitude=None, longitude=None, complete_shift=False):
        """
        End shift.
        
        Args:
            shift_id: ID of the shift to end
            latitude: GPS latitude for shift end verification
            longitude: GPS longitude for shift end verification
            complete_shift: If True, mark shift as completed (final end)
        """
        if not shift_id:
            return {'success': False, 'error': 'Shift ID is required'}
        
        try:
            shift = request.env['guard.shift'].browse(int(shift_id))
            
            if not shift.exists():
                return {'success': False, 'error': 'Shift not found'}
            
            # SECURITY FIX: Verify shift belongs to current user's guard profile
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'success': False, 'error': 'Guard profile not found'}
            
            if shift.guard_id.id != guard.id:
                _logger.warning(
                    'Unauthorized shift end attempt: User %s (Guard %s) tried to end shift %s belonging to Guard %s',
                    request.env.user.login, guard.name, shift_id, shift.guard_id.name
                )
                return {'success': False, 'error': 'Unauthorized: This shift is not assigned to you'}
            
            result = shift.action_checkout(latitude, longitude, complete_shift)
            
            # Ensure result has success flag
            if isinstance(result, dict):
                if 'error' not in result and 'success' not in result:
                    result['success'] = True
                return result
            
            return {'success': True, 'message': 'Shift ended successfully'}
        except ValueError:
            return {'success': False, 'error': 'Invalid shift ID'}
        except Exception as e:
            _logger.error('Shift end error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @http.route('/guardpro/api/shift/attendance', type='json', auth='user', methods=['POST'], csrf=False)
    def get_shift_attendance(self, shift_id=None):
        """
        Get all attendance records for a shift.
        Shows all shift start/end pairs for the shift.
        """
        if not shift_id:
            return {'success': False, 'error': 'Shift ID is required'}
        
        try:
            shift = request.env['guard.shift'].browse(int(shift_id))
            
            if not shift.exists():
                return {'success': False, 'error': 'Shift not found'}
            
            return {
                'success': True,
                'shift_id': shift.id,
                'shift_duration': shift.duration,
                'total_hours_worked': shift.total_hours_worked,
                'remaining_hours': shift.remaining_hours,
                'attendance_records': [{
                    'id': a.id,
                    'checkin_time': a.checkin_time.isoformat() + 'Z' if a.checkin_time else None,
                    'checkout_time': a.checkout_time.isoformat() + 'Z' if a.checkout_time else None,
                    'hours_worked': a.hours_worked,
                    'status': a.status,
                    'checkin_method': a.checkin_method,
                    'checkout_method': a.checkout_method,
                    'checkin_verified': a.checkin_verified,
                    'checkout_verified': a.checkout_verified,
                } for a in shift.attendance_ids.sorted('checkin_time')]
            }
        except ValueError:
            return {'success': False, 'error': 'Invalid shift ID'}
        except Exception as e:
            _logger.error('Get shift attendance error: %s', str(e))
            return {'success': False, 'error': str(e)}

    @rate_limit(max_requests=100, window_seconds=60)  # Max 100 scans per minute (tours have many checkpoints)
    @http.route('/guardpro/api/checkpoint/scan', type='json', auth='user', methods=['POST'], csrf=False)
    def scan_checkpoint(self, checkpoint_id, scan_data, latitude=None, longitude=None,
                        tour_log_id=None, photo=None, notes=None, videos=None):
        """Scan a checkpoint."""
        _logger.info('[API Checkpoint Scan] Received scan request: checkpoint_id=%s, tour_log_id=%s, scan_data=%s (type: %s)',
                    checkpoint_id, tour_log_id, scan_data, type(scan_data).__name__)
        
        # Validate checkpoint_id
        if not checkpoint_id:
            _logger.error('[API Checkpoint Scan] Missing checkpoint_id')
            return {'success': False, 'error': 'Checkpoint ID is required', 'message': 'Checkpoint ID is required'}
        
        try:
            checkpoint_id = int(checkpoint_id)
        except (ValueError, TypeError):
            _logger.error('[API Checkpoint Scan] Invalid checkpoint_id: %s', checkpoint_id)
            return {'success': False, 'error': 'Invalid checkpoint ID', 'message': 'Invalid checkpoint ID'}
        
        # Validate scan_data - ensure it's a string
        if scan_data is None:
            _logger.warning('[API Checkpoint Scan] scan_data is None, converting to empty string')
            scan_data = ''
        elif not isinstance(scan_data, str):
            try:
                scan_data = str(scan_data)
                _logger.info('[API Checkpoint Scan] Converted scan_data to string: %s', scan_data)
            except Exception as e:
                _logger.error('[API Checkpoint Scan] Error converting scan_data to string: %s', str(e))
                return {'success': False, 'error': 'Invalid scan data format', 'message': 'Invalid scan data format'}

        # Validate tour_log_id - ensure it's a valid integer or None
        if tour_log_id is not None and tour_log_id != '':
            try:
                tour_log_id = int(tour_log_id)
                if tour_log_id <= 0:
                    _logger.warning('[API Checkpoint Scan] Invalid tour_log_id: %s, setting to None', tour_log_id)
                    tour_log_id = None
            except (ValueError, TypeError):
                _logger.warning('[API Checkpoint Scan] Invalid tour_log_id format: %s, setting to None', tour_log_id)
                tour_log_id = None
        else:
            tour_log_id = None

        _logger.info('[API Checkpoint Scan] Processed tour_log_id: %s', tour_log_id)
        
        scan_data = scan_data.strip()
        _logger.info('[API Checkpoint Scan] Processed scan_data: "%s" (length: %d)', scan_data, len(scan_data))
        
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            _logger.error('[Guard Pro API Checkpoint Scan] Guard profile not found for user: %s', request.env.user.name)
            return {'success': False, 'error': 'Guard profile not found', 'message': 'Guard profile not found'}
        
        _logger.info('[API Checkpoint Scan] Guard found: %s (ID: %s)', guard.name, guard.id)
        
        try:
            result = request.env['checkpoint.scan'].scan_checkpoint(
                checkpoint_id=checkpoint_id,
                guard_id=guard.id,
                scan_data=scan_data,
                latitude=latitude,
                longitude=longitude,
                tour_log_id=tour_log_id,
                photo=photo,
                notes=notes,
                videos=videos,
            )
            _logger.info('[API Checkpoint Scan] Scan result: %s', result)
            
            # If successful and part of a tour, log the current progress
            if result.get('success') and tour_log_id:
                tour_log = request.env['tour.log'].sudo().browse(tour_log_id)
                if tour_log.exists():
                    _logger.info('[API Checkpoint Scan] Tour progress after scan: %d/%d (%.1f%%)',
                               tour_log.scanned_checkpoints, tour_log.expected_checkpoints,
                               tour_log.completion_percentage)
            
            return result
        except Exception as e:
            _logger.error('[API Checkpoint Scan] Exception: %s', str(e), exc_info=True)
            return {'success': False, 'error': str(e), 'message': 'An unexpected error occurred. Please try again.'}

    @rate_limit(max_requests=60, window_seconds=60)
    @http.route('/guardpro/api/checkpoint/scan/evidence', type='json', auth='user', methods=['POST'], csrf=False)
    def checkpoint_scan_append_evidence(self, scan_id, photos=None, videos=None, observations=None):
        """Add optional photos, videos, and observation text to an existing checkpoint scan (same guard only)."""
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        if not guard:
            return {
                'success': False,
                'error': 'guard_not_found',
                'message': 'Guard profile not found',
            }
        if not scan_id:
            return {
                'success': False,
                'error': 'scan_id_required',
                'message': 'Scan ID is required',
            }
        try:
            scan_id = int(scan_id)
        except (TypeError, ValueError):
            return {
                'success': False,
                'error': 'invalid_scan_id',
                'message': 'Invalid scan ID',
            }

        photos = photos or []
        videos = videos or []
        obs = (observations or '').strip() if observations else ''
        if not photos and not videos and not obs:
            return {'success': True, 'message': 'Nothing to attach'}

        scan = request.env['checkpoint.scan'].browse(scan_id)
        if not scan.exists() or scan.guard_id.id != guard.id:
            return {
                'success': False,
                'error': 'scan_not_found',
                'message': 'Scan not found or access denied',
            }

        try:
            scan.append_post_scan_evidence(
                photos_payload=photos,
                videos_payload=videos,
                observations_text=obs or None,
            )
            return {'success': True, 'message': 'Findings saved'}
        except (AccessError, ValidationError) as e:
            _logger.warning('[API Checkpoint Evidence] %s', str(e))
            return {'success': False, 'error': 'validation', 'message': str(e)}
        except Exception as e:
            _logger.exception('[API Checkpoint Evidence] Unexpected error')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    @http.route('/guardpro/api/shifts/tours', type='json', auth='user', methods=['POST'], csrf=False)
    def get_shift_tours(self, shift_id=None):
        """Get tours assigned to a shift or all active tours for current guard."""
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found', 'tours': []}
        
        tours_data = []
        active_tour_log = None
        
        if shift_id:
            # Get tours for specific shift
            shift = request.env['guard.shift'].sudo().browse(shift_id)
            if shift.exists() and shift.guard_id.id == guard.id:
                tours_data = [{
                    'id': tour.id,
                    'name': tour.name,
                    'code': tour.code,
                    'description': tour.description,
                    'status': tour.status,
                    'total_checkpoints': tour.total_checkpoints,
                    'estimated_duration': tour.estimated_duration,
                    'instructions': tour.instructions,
                    'site_name': tour.site_id.name
                } for tour in shift.tour_ids if tour.status == 'active']
                
                # Check for active tour log for this shift
                # Order by start_time DESC to get the most recent active tour
                active_tour_log_rec = request.env['tour.log'].sudo().search([
                    ('shift_id', '=', shift_id),
                    ('guard_id', '=', guard.id),
                    ('status', '=', 'in_progress')
                ], order='start_time DESC', limit=1)
                
                if active_tour_log_rec:
                    # Get checkpoint scan status
                    scanned_checkpoint_ids = active_tour_log_rec.scan_ids.filtered(
                        lambda s: s.status == 'verified'
                    ).mapped('checkpoint_id').ids
                    
                    # Get all tour checkpoints with scan status
                    tour_checkpoints = []
                    for checkpoint in active_tour_log_rec.tour_id.checkpoint_ids:
                        is_scanned = checkpoint.id in scanned_checkpoint_ids
                        tour_checkpoints.append({
                            'id': checkpoint.id,
                            'name': checkpoint.name,
                            'code': checkpoint.code,
                            'scan_type': checkpoint.scan_type,
                            'latitude': checkpoint.latitude,
                            'longitude': checkpoint.longitude,
                            'qr_code': checkpoint.qr_code if checkpoint.qr_code else '',
                            'nfc_tag_id': checkpoint.nfc_tag_id if checkpoint.nfc_tag_id else '',
                            'is_scanned': is_scanned,
                            'notes': checkpoint.notes if checkpoint.notes else ''
                        })
                    
                    active_tour_log = {
                        'id': active_tour_log_rec.id,
                        'tour_id': active_tour_log_rec.tour_id.id,
                        'tour_name': active_tour_log_rec.tour_id.name,
                        'start_time': active_tour_log_rec.start_time.isoformat() + 'Z',
                        'scanned_checkpoints': active_tour_log_rec.scanned_checkpoints,
                        'expected_checkpoints': active_tour_log_rec.expected_checkpoints,
                        'completion_percentage': active_tour_log_rec.completion_percentage / 100.0 if active_tour_log_rec.completion_percentage else 0.0,
                        'checkpoints': tour_checkpoints
                    }
        
        return {
            'success': True,
            'tours': tours_data,
            'active_tour_log': active_tour_log
        }

    @http.route('/guardpro/api/tour/start', type='json', auth='user', methods=['POST'], csrf=False)
    def start_tour(self, tour_id, shift_id=None):
        """Start a security tour."""
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found'}
        
        tour = request.env['security.tour'].sudo().browse(tour_id)
        
        if not tour.exists():
            return {'error': 'Tour not found'}
        
        try:
            result = tour.start_tour(guard.id)
            
            # If shift_id provided, link the tour log to the shift
            if shift_id and result.get('tour_log_id'):
                tour_log = request.env['tour.log'].sudo().browse(result['tour_log_id'])
                if tour_log.exists():
                    tour_log.write({'shift_id': shift_id})
            
            # Automatically link pending tasks for this guard at this site to the tour
            if result.get('tour_log_id'):
                tour_log = request.env['tour.log'].sudo().browse(result['tour_log_id'])
                if tour_log.exists():
                    # Find pending tasks for this guard at this site
                    pending_tasks = request.env['guard.task'].sudo().search([
                        ('assigned_to', '=', guard.id),
                        ('site_id', '=', tour.site_id.id),
                        ('state', 'in', ['assigned', 'in_progress'])
                    ])
                    
                    if pending_tasks:
                        tour_log.write({'task_ids': [(6, 0, pending_tasks.ids)]})
                        _logger.info(
                            'Linked %d pending tasks to tour log %d',
                            len(pending_tasks),
                            tour_log.id
                        )
            
            return {
                'success': True,
                'tour_log_id': result.get('tour_log_id'),
                'message': 'Tour started successfully'
            }
        except Exception as e:
            _logger.error('Error starting tour: %s', str(e))
            return {'error': str(e)}

    @http.route('/guardpro/api/tour/complete', type='json', auth='user', methods=['POST'], csrf=False)
    def complete_tour(self, tour_log_id, partial=False, reason=None):
        """Complete a security tour.
        
        Args:
            tour_log_id (int): Tour log ID
            partial (bool): If True, marks as partial completion
            reason (str): Reason for partial completion (required if partial=True)
        """
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found'}
        
        tour_log = request.env['tour.log'].sudo().browse(tour_log_id)
        
        if not tour_log.exists():
            return {'error': 'Tour log not found'}
        
        # Verify tour belongs to current guard
        if tour_log.guard_id.id != guard.id:
            return {'error': 'Unauthorized: This tour does not belong to you'}
        
        # If partial completion, reason is required
        if partial and not reason:
            return {'error': 'Reason is required for partial completion'}
        
        # Check if all checkpoints have been completed
        if not partial and tour_log.expected_checkpoints > 0:
            if tour_log.scanned_checkpoints < tour_log.expected_checkpoints:
                missing_count = tour_log.expected_checkpoints - tour_log.scanned_checkpoints
                return {
                    'error': 'Cannot complete tour. Not all checkpoints have been scanned.',
                    'checkpoint_status': {
                        'scanned': tour_log.scanned_checkpoints,
                        'expected': tour_log.expected_checkpoints,
                        'missing': missing_count,
                        'completion_percentage': tour_log.completion_percentage / 100.0 if tour_log.completion_percentage else 0.0
                    }
                }
        
        # Check for pending tasks
        if not partial and tour_log.pending_task_count > 0:
            pending_tasks = [{
                'id': task.id,
                'name': task.name,
                'state': task.state,
                'priority': task.priority
            } for task in tour_log.pending_task_ids]
            
            return {
                'error': 'Cannot complete tour. You must complete all tasks first.',
                'pending_tasks': pending_tasks,
                'pending_task_count': tour_log.pending_task_count
            }
        
        try:
            tour_log.action_complete(partial=partial, reason=reason)
            
            if partial:
                message = 'Tour marked as partially complete'
            else:
                message = 'Tour completed successfully'
            
            return {'success': True, 'message': message}
        except Exception as e:
            _logger.error('Error completing tour: %s', str(e))
            return {'error': str(e)}

    @rate_limit(max_requests=20, window_seconds=60)  # Max 20 incidents per minute
    @http.route('/guardpro/api/incident/create', type='json', auth='user', methods=['POST'], csrf=False)
    def create_incident(self, **kwargs):
        """Create incident report."""
        # Validate input parameters
        valid, error, validated = validators.validate_incident_create_params(kwargs)
        
        if not valid:
            return validators.create_error_response(error)
        
        # Get guard profile
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return validators.create_error_response('Guard profile not found', 'NOT_FOUND')
        
        try:
            # Get site_id - use provided value or auto-determine from active shift
            site_id = validated.get('site_id')
            
            if site_id:
                # SECURITY FIX: Verify guard has access to specified site
                if site_id not in request.env.user.site_ids.ids:
                    _logger.warning(
                        'Unauthorized incident creation attempt: User %s (Guard %s) tried to create incident at site %s without access',
                        request.env.user.login, guard.name, site_id
                    )
                    return validators.create_error_response(
                        'Access denied: You do not have access to this site',
                        'SITE_ACCESS_DENIED'
                    )
            else:
                # Auto-determine site from ACTIVE shift only (not most recent)
                active_shift = request.env['guard.shift'].search([
                    ('guard_id', '=', guard.id),
                    ('status', '=', 'in_progress'),  # Only in-progress shifts
                    ('site_id', '!=', False)
                ], limit=1)
                
                if active_shift:
                    site_id = active_shift.site_id.id
                    _logger.info('Incident: Auto-determined site from active shift: %s', active_shift.site_id.name)
                elif guard.current_site_id and guard.current_site_id.id in request.env.user.site_ids.ids:
                    # Fallback to current_site_id if it's in their authorized sites
                    site_id = guard.current_site_id.id
                    _logger.info('Incident: Using guard current_site_id: %s', guard.current_site_id.name)
                else:
                    return validators.create_error_response(
                        'Cannot determine site. Please start your shift first or select a site from the list.',
                        'SITE_REQUIRED'
                    )
            
            
            # Prepare values
            vals = {
                'guard_id': guard.id,
                'site_id': site_id,
                'shift_id': validated.get('shift_id'),
                'title': validated['title'],
                'description': validated['description'],
                'category_id': validated['category_id'],
                'severity': validated['severity'],
                'latitude': validated['latitude'],
                'longitude': validated['longitude'],
                'location': validated['location'],
            }
            
            # Handle uploaded media
            media_payloads = []
            media_payloads.extend(kwargs.get('photos', []) or [])
            media_payloads.extend(kwargs.get('videos', []) or [])
            if media_payloads:
                photos = []
                videos = []
                for payload in media_payloads:
                    payload = payload or {}
                    payload_name = payload.get('name', 'incident_media')
                    payload_data = payload.get('data')
                    if not payload_data:
                        continue

                    mimetype = (
                        payload.get('mimetype')
                        or payload.get('content_type')
                        or 'application/octet-stream'
                    )
                    is_video = self._is_video_payload(payload)
                    attachment_data = payload_data

                    if is_video:
                        attachment_data, compressed = VideoOptimizer.optimize_video(
                            payload_data,
                            filename=payload_name,
                        )
                        if compressed:
                            mimetype = 'video/mp4'

                    attachment = request.env['ir.attachment'].create({
                        'name': payload_name,
                        'datas': attachment_data,
                        'res_model': 'incident.report',
                        'mimetype': mimetype,
                    })
                    if is_video:
                        videos.append(attachment.id)
                    else:
                        photos.append(attachment.id)

                if photos:
                    vals['photo_ids'] = [(6, 0, photos)]
                if videos:
                    vals['video_ids'] = [(6, 0, videos)]
            
            incident = request.env['incident.report'].create(vals)
            incident.action_submit()
            
            return validators.create_success_response({
                'incident_id': incident.id,
                'incident_number': incident.name
            }, message='Incident reported successfully')
            
        except ValidationError as e:
            _logger.warning('Incident creation validation error: %s', str(e))
            return validators.create_error_response(str(e), 'VALIDATION_ERROR')
        except AccessError as e:
            _logger.warning('Incident creation access denied: %s', str(e))
            return validators.create_error_response('Access denied', 'ACCESS_DENIED')
        except Exception as e:
            _logger.exception('Unexpected incident creation error')
            return validators.create_error_response(
                'Failed to create incident. Please try again.',
                'INTERNAL_ERROR'
            )

    @rate_limit(max_requests=5, window_seconds=300)  # Max 5 panic alerts per 5 minutes
    @http.route('/guardpro/api/incident/panic', type='json', auth='user', methods=['POST'], csrf=False)
    def panic_button(self, site_id=None, latitude=None, longitude=None, notes=None):
        """Handle panic button activation - SAFETY CRITICAL."""
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        # CRITICAL: Even without guard profile, log the panic attempt
        if not guard:
            _logger.critical(
                '[Guard Pro] PANIC BUTTON: No guard profile for user %s (ID: %s) - Creating emergency incident anyway',
                request.env.user.name, request.env.user.id
            )
        
        # Auto-determine site if not provided
        if not site_id and guard:
            # Try current site first
            if guard.current_site_id:
                site_id = guard.current_site_id.id
                _logger.info('PANIC: Using guard current site: %s', guard.current_site_id.name)
            else:
                # Try to get from active shift
                active_shift = request.env['guard.shift'].search([
                    ('guard_id', '=', guard.id),
                    ('status', '=', 'in_progress')
                ], limit=1)
                if active_shift:
                    site_id = active_shift.site_id.id
                    _logger.info('PANIC: Using active shift site: %s', active_shift.site_id.name)
        
        try:
            # Create critical incident - NEVER fail on panic button
            incident_vals = {
                'guard_id': guard.id if guard else False,
                'site_id': site_id or False,  # OK to be False in emergencies
                'title': '🚨 PANIC BUTTON ACTIVATED - EMERGENCY 🚨',
                'description': notes or 'Guard activated panic button - IMMEDIATE RESPONSE REQUIRED',
                'severity': 'critical',
                'priority': '2',
                'latitude': latitude,
                'longitude': longitude,
                'status': 'submitted'
            }
            
            incident = request.env['incident.report'].create(incident_vals)
            
            _logger.critical(
                'PANIC BUTTON ACTIVATED: Incident %s created by %s at lat=%s, lon=%s',
                incident.name, guard.name if guard else request.env.user.name,
                latitude, longitude
            )
            
            # Send emergency alerts
            try:
                incident.action_panic()
            except Exception as alert_error:
                _logger.error('Panic alert notification failed: %s', str(alert_error))
                # Don't fail the whole panic button if alerts fail
            
            # Prepare response with emergency contact info
            emergency_phone = None
            if site_id:
                site = request.env['client.site'].browse(site_id)
                emergency_phone = site.emergency_phone if site.exists() else None
            
            return {
                'success': True,
                'incident_id': incident.id,
                'incident_number': incident.name,
                'message': 'Emergency alert sent successfully',
                'emergency_phone': emergency_phone
            }
        except Exception as e:
            # CRITICAL: Even if database fails, return success to avoid guard panic
            _logger.critical('PANIC BUTTON DATABASE ERROR: %s', str(e), exc_info=True)
            return {
                'success': True,  # Return success anyway
                'message': 'Emergency logged. Please call emergency services immediately.',
                'error_logged': True
            }

    @http.route('/guardpro/api/sites/accessible', type='json', auth='user', methods=['POST'], csrf=False)
    def get_accessible_sites(self):
        """Get list of sites accessible to the current guard."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # Get sites from user's assigned sites (synced from guard's shifts)
            sites = request.env.user.site_ids
            
            site_list = []
            for site in sites:
                site_list.append({
                    'id': site.id,
                    'name': site.name,
                    'address': site.address,
                    'city': site.city
                })
            
            return {
                'success': True,
                'sites': site_list,
                'total_count': len(site_list)
            }
            
        except Exception as e:
            _logger.error('Get accessible sites error: %s', str(e))
            return {'error': str(e)}

    @http.route('/guardpro/api/incident/categories', type='json', auth='user', methods=['POST'], csrf=False)
    def get_incident_categories(self):
        """Get list of incident categories."""
        try:
            categories = request.env['incident.category'].search([
                ('active', '=', True)
            ], order='sequence, name')
            
            category_list = []
            for category in categories:
                category_list.append({
                    'id': category.id,
                    'name': category.name,
                    'code': category.code,
                    'description': category.description
                })
            
            return {
                'success': True,
                'categories': category_list
            }
            
        except Exception as e:
            _logger.error('Get incident categories error: %s', str(e))
            return {'error': str(e)}

    @http.route('/guardpro/api/incidents/list', type='json', auth='user', methods=['POST'], csrf=False)
    def get_incident_reports(self, limit=50, offset=0, status=None):
        """Get incident reports for the current guard."""
        guard = request.env['guard.profile'].search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found'}
        
        try:
            # Build domain for incident search - show all incidents at guard's assigned sites
            user = request.env.user
            domain = [('site_id', 'in', user.site_ids.ids)]
            
            # Filter by status if provided
            if status:
                domain.append(('status', '=', status))
            
            # Search for incidents
            incidents = request.env['incident.report'].search(
                domain,
                order='incident_datetime desc',
                limit=limit,
                offset=offset
            )
            
            # Format incident data for mobile app
            incident_list = []
            for incident in incidents:
                incident_list.append({
                    'id': incident.id,
                    'incident_number': incident.name,
                    'title': incident.title,
                    'description': incident.description,
                    'severity': incident.severity,
                    'status': incident.status,
                    'incident_datetime': incident.incident_datetime.isoformat() + 'Z' if incident.incident_datetime else None,
                    'reported_datetime': incident.reported_datetime.isoformat() + 'Z' if incident.reported_datetime else None,
                    'site_name': incident.site_id.name if incident.site_id else 'Unknown Site',
                    'location': incident.location,
                    'latitude': incident.latitude,
                    'longitude': incident.longitude,
                    'category': incident.category_id.name if incident.category_id else None,
                    'priority': incident.priority,
                    'escalated': incident.escalated,
                    'has_photos': len(incident.photo_ids) > 0,
                    'photo_count': len(incident.photo_ids),
                    'has_videos': len(incident.video_ids) > 0,
                    'video_count': len(incident.video_ids),
                    'requires_followup': incident.requires_followup,
                    'followup_completed': incident.followup_completed
                })
            
            return {
                'success': True,
                'incidents': incident_list,
                'total_count': len(incident_list),
                'has_more': len(incidents) == limit  # Indicates if there are more records
            }
            
        except Exception as e:
            _logger.error('Get incident reports error: %s', str(e))
            return {'error': str(e)}

    @http.route('/guardpro/api/incidents/detail', type='json', auth='user', methods=['POST'], csrf=False)
    def get_incident_detail(self, incident_id):
        """Single incident with photo/video lists for the mobile app."""
        if not incident_id:
            return {'success': False, 'error': 'incident_id is required'}
        try:
            incident_id = int(incident_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'Invalid incident_id'}

        user = request.env.user
        incident = request.env['incident.report'].search([
            ('id', '=', incident_id),
            ('site_id', 'in', user.site_ids.ids),
        ], limit=1)
        if not incident:
            return {'success': False, 'error': 'Incident not found'}

        photos, videos = self._incident_photos_videos_payload(incident)
        return {
            'success': True,
            'incident': {
                'id': incident.id,
                'incident_number': incident.name,
                'title': incident.title,
                'description': incident.description,
                'severity': incident.severity,
                'status': incident.status,
                'incident_datetime': incident.incident_datetime.isoformat() + 'Z' if incident.incident_datetime else None,
                'reported_datetime': incident.reported_datetime.isoformat() + 'Z' if incident.reported_datetime else None,
                'site_name': incident.site_id.name if incident.site_id else 'Unknown Site',
                'location': incident.location,
                'latitude': incident.latitude,
                'longitude': incident.longitude,
                'category': incident.category_id.name if incident.category_id else None,
                'priority': incident.priority,
                'escalated': incident.escalated,
                'has_photos': len(photos) > 0,
                'photo_count': len(photos),
                'has_videos': len(videos) > 0,
                'video_count': len(videos),
                'photos': photos,
                'videos': videos,
                'requires_followup': incident.requires_followup,
                'followup_completed': incident.followup_completed,
            },
        }

    # --- Compliance audits (supervisor / manager / admin only; not guard portal) ---

    def _compliance_normalize_base64_data(self, payload_data):
        """Normalize JSON attachment data to a base64 string (strip data-URI prefix)."""
        if payload_data is None:
            return None
        if isinstance(payload_data, bytes):
            try:
                return payload_data.decode('ascii')
            except Exception:
                return base64.b64encode(payload_data).decode()
        s = str(payload_data).strip()
        if s.startswith('data:'):
            comma = s.find(',')
            if comma != -1:
                s = s[comma + 1 :].strip()
        return s

    def _compliance_user_is_assigned_auditor(self, audit, user):
        """True if the user is the lead auditor or a member of the audit team."""
        self_auditor = audit.auditor_id and audit.auditor_id.id == user.id
        in_team = user.id in audit.auditor_team_ids.ids
        return bool(self_auditor or in_team)

    def _compliance_api_staff_only(self, user):
        """GuardLink supervisor, manager, or admin."""
        if not user or user._is_public():
            return False
        return (
            user.has_group('guardpro.group_guardpro_supervisor')
            or user.has_group('guardpro.group_guardpro_manager')
            or user.has_group('guardpro.group_guardpro_admin')
        )

    def _compliance_api_staff_denied(self):
        return {
            'success': False,
            'error': 'access_denied',
            'message': 'Compliance is only available for supervisor or manager accounts.',
        }

    def _compliance_user_can_write_audit(self, audit, user):
        """May start, edit checklist, or complete (open states). Mirrors mobile PWA rules."""
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

    def _compliance_item_photo_urls(self, item):
        """Photo metadata for one checklist line (for native app)."""
        photos = []
        for att in item.photo_ids:
            photos.append({
                'id': att.id,
                'name': att.name,
                'mimetype': att.mimetype or 'image/jpeg',
                'url': '/web/image/ir.attachment/%s/datas' % att.id,
            })
        return photos

    def _compliance_create_item_photo_attachments(self, item, photo_payloads):
        """Create image attachments linked to compliance.audit.item; returns new attachment ids."""
        if not photo_payloads:
            return []
        ids = []
        Attachment = request.env['ir.attachment'].sudo()
        for payload in photo_payloads:
            if not payload or not isinstance(payload, dict):
                continue
            if self._is_video_payload(payload):
                _logger.warning(
                    '[Compliance API] Skipping video payload on audit item %s (photos only)',
                    item.id,
                )
                continue
            payload_name = payload.get('name') or 'audit_item_photo.jpg'
            raw = self._compliance_normalize_base64_data(payload.get('data'))
            if not raw:
                continue
            mimetype = (
                payload.get('mimetype')
                or payload.get('content_type')
                or 'image/jpeg'
            )
            att = Attachment.create({
                'name': payload_name,
                'datas': raw,
                'res_model': 'compliance.audit.item',
                'res_id': item.id,
                'mimetype': mimetype,
            })
            ids.append(att.id)
        return ids

    def _compliance_serialize_audit_row(self, audit, user):
        assigned = self._compliance_user_is_assigned_auditor(audit, user)
        can_execute = self._compliance_user_can_write_audit(audit, user)
        return {
            'id': audit.id,
            'name': audit.name,
            'audit_type': audit.audit_type,
            'state': audit.state,
            'audit_date': fields.Date.to_string(audit.audit_date) if audit.audit_date else None,
            'site_id': audit.site_id.id if audit.site_id else None,
            'site_name': audit.site_id.name if audit.site_id else None,
            'template_id': audit.template_id.id if audit.template_id else None,
            'template_name': audit.template_id.name if audit.template_id else None,
            'auditor_id': audit.auditor_id.id if audit.auditor_id else None,
            'auditor_name': audit.auditor_id.name if audit.auditor_id else None,
            'total_items': audit.total_items,
            'passed_items': audit.passed_items,
            'failed_items': audit.failed_items,
            'na_items': audit.na_items,
            'compliance_score': audit.compliance_score,
            'rating': audit.rating,
            'is_assigned_auditor': assigned,
            'can_execute': can_execute,
        }

    def _compliance_serialize_item(self, item):
        return {
            'id': item.id,
            'sequence': item.sequence,
            'name': item.name,
            'description': item.description,
            'category': item.category,
            'regulation_reference': item.regulation_reference,
            'result': item.result,
            'notes': item.notes,
            'requires_action': item.requires_action,
            'severity': item.severity,
            'photo_count': item.photo_count,
            'photos': self._compliance_item_photo_urls(item),
        }

    @rate_limit(max_requests=60, window_seconds=60)
    @http.route('/guardpro/api/compliance/audits/list', type='json', auth='user', methods=['POST'], csrf=False)
    def compliance_audits_list(self, scope='visible', states=None, limit=50, offset=0):
        """List compliance audits (supervisor/manager/admin). Record rules apply."""
        user = request.env.user
        if not self._compliance_api_staff_only(user):
            return self._compliance_api_staff_denied()

        try:
            limit = int(limit or 50)
            offset = int(offset or 0)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'invalid_pagination', 'message': 'Invalid limit or offset'}

        if scope not in ('assigned', 'site', 'visible'):
            scope = 'visible'

        if states is not None and not isinstance(states, (list, tuple)):
            states = None
        if not states:
            if scope == 'site':
                states = ['draft', 'in_progress', 'requires_action', 'completed']
            else:
                states = ['draft', 'in_progress', 'requires_action']

        domain = [('state', 'in', list(states))]
        if scope == 'assigned':
            domain = [
                '&',
                '|',
                ('auditor_id', '=', user.id),
                ('auditor_team_ids', 'in', user.id),
            ] + domain
        elif scope == 'site':
            domain.append(('site_id', 'in', user.site_ids.ids))

        try:
            Audit = request.env['compliance.audit']
            audits = Audit.search(domain, order='audit_date desc, id desc', limit=limit, offset=offset)
            rows = [self._compliance_serialize_audit_row(a, user) for a in audits]
            return {
                'success': True,
                'audits': rows,
                'total_count': len(rows),
                'scope': scope,
            }
        except Exception as e:
            _logger.exception('[Compliance API] List failed')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    @rate_limit(max_requests=60, window_seconds=60)
    @http.route('/guardpro/api/compliance/audit/detail', type='json', auth='user', methods=['POST'], csrf=False)
    def compliance_audit_detail(self, audit_id=None):
        """Full audit with checklist for mobile."""
        user = request.env.user
        if not self._compliance_api_staff_only(user):
            return self._compliance_api_staff_denied()

        if not audit_id:
            return {'success': False, 'error': 'audit_id_required', 'message': 'audit_id is required'}
        try:
            audit_id = int(audit_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'invalid_audit_id', 'message': 'Invalid audit_id'}

        try:
            audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
            if not audit:
                return {'success': False, 'error': 'not_found', 'message': 'Audit not found'}

            row = self._compliance_serialize_audit_row(audit, user)
            items = [
                self._compliance_serialize_item(i)
                for i in audit.checklist_ids
            ]
            return {
                'success': True,
                'audit': row,
                'items': items,
                'notes': audit.notes or '',
                'audit_start_time': audit.audit_start_time.isoformat() if audit.audit_start_time else None,
                'audit_end_time': audit.audit_end_time.isoformat() if audit.audit_end_time else None,
            }
        except Exception as e:
            _logger.exception('[Compliance API] Detail failed')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    @rate_limit(max_requests=30, window_seconds=60)
    @http.route('/guardpro/api/compliance/audit/start', type='json', auth='user', methods=['POST'], csrf=False)
    def compliance_audit_start(self, audit_id=None):
        """Move audit from draft to in_progress."""
        user = request.env.user
        if not self._compliance_api_staff_only(user):
            return self._compliance_api_staff_denied()

        if not audit_id:
            return {'success': False, 'error': 'audit_id_required', 'message': 'audit_id is required'}
        try:
            audit_id = int(audit_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'invalid_audit_id', 'message': 'Invalid audit_id'}

        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit:
            return {'success': False, 'error': 'not_found', 'message': 'Audit not found'}

        if not self._compliance_user_can_write_audit(audit, user):
            return {
                'success': False,
                'error': 'access_denied',
                'message': 'You cannot start this audit',
            }

        try:
            audit.action_start_audit()
            return {
                'success': True,
                'message': 'Audit started',
                'audit': self._compliance_serialize_audit_row(audit, user),
            }
        except UserError as e:
            return {'success': False, 'error': 'user_error', 'message': str(e)}
        except (AccessError, ValidationError) as e:
            _logger.warning('[Compliance API] Start access/validation: %s', e)
            return {'success': False, 'error': 'validation', 'message': str(e)}
        except Exception as e:
            _logger.exception('[Compliance API] Start failed')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    @rate_limit(max_requests=30, window_seconds=60)
    @http.route('/guardpro/api/compliance/audit/complete', type='json', auth='user', methods=['POST'], csrf=False)
    def compliance_audit_complete(self, audit_id=None):
        """Complete audit (all checklist lines must have a result)."""
        user = request.env.user
        if not self._compliance_api_staff_only(user):
            return self._compliance_api_staff_denied()

        if not audit_id:
            return {'success': False, 'error': 'audit_id_required', 'message': 'audit_id is required'}
        try:
            audit_id = int(audit_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'invalid_audit_id', 'message': 'Invalid audit_id'}

        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit:
            return {'success': False, 'error': 'not_found', 'message': 'Audit not found'}

        if not self._compliance_user_can_write_audit(audit, user):
            return {
                'success': False,
                'error': 'access_denied',
                'message': 'You cannot complete this audit',
            }

        try:
            audit.action_complete_audit()
            return {
                'success': True,
                'message': 'Audit completed',
                'audit': self._compliance_serialize_audit_row(audit, user),
            }
        except UserError as e:
            return {'success': False, 'error': 'user_error', 'message': str(e)}
        except (AccessError, ValidationError) as e:
            _logger.warning('[Compliance API] Complete access/validation: %s', e)
            return {'success': False, 'error': 'validation', 'message': str(e)}
        except Exception as e:
            _logger.exception('[Compliance API] Complete failed')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    @rate_limit(max_requests=45, window_seconds=60)
    @http.route('/guardpro/api/compliance/audit/items/save', type='json', auth='user', methods=['POST'], csrf=False)
    def compliance_audit_items_save(self, audit_id=None, items=None):
        """Batch update checklist lines and append photos."""
        user = request.env.user
        if not self._compliance_api_staff_only(user):
            return self._compliance_api_staff_denied()

        if not audit_id:
            return {'success': False, 'error': 'audit_id_required', 'message': 'audit_id is required'}
        try:
            audit_id = int(audit_id)
        except (TypeError, ValueError):
            return {'success': False, 'error': 'invalid_audit_id', 'message': 'Invalid audit_id'}

        items = items or []
        if not isinstance(items, list):
            return {'success': False, 'error': 'invalid_items', 'message': 'items must be a list'}

        audit = request.env['compliance.audit'].search([('id', '=', audit_id)], limit=1)
        if not audit:
            return {'success': False, 'error': 'not_found', 'message': 'Audit not found'}

        if not self._compliance_user_can_write_audit(audit, user):
            return {
                'success': False,
                'error': 'access_denied',
                'message': 'You cannot update this audit',
            }

        if audit.state not in ('draft', 'in_progress', 'requires_action'):
            return {
                'success': False,
                'error': 'invalid_state',
                'message': 'Checklist can only be edited while the audit is open',
            }

        Item = request.env['compliance.audit.item']
        updated = []
        try:
            for entry in items:
                if not isinstance(entry, dict):
                    continue
                raw_id = entry.get('item_id', entry.get('id'))
                if raw_id is None:
                    continue
                try:
                    item_id = int(raw_id)
                except (TypeError, ValueError):
                    return {'success': False, 'error': 'invalid_item_id', 'message': 'Invalid checklist item id'}

                item = Item.search([('id', '=', item_id), ('audit_id', '=', audit.id)], limit=1)
                if not item:
                    return {
                        'success': False,
                        'error': 'item_not_found',
                        'message': 'Checklist item %s not found for this audit' % item_id,
                    }

                vals = {}
                if 'result' in entry:
                    r = entry['result']
                    if r in (False, None, ''):
                        vals['result'] = False
                    elif r in ('pass', 'fail', 'na'):
                        vals['result'] = r
                    else:
                        return {
                            'success': False,
                            'error': 'invalid_result',
                            'message': 'result must be pass, fail, na, or empty',
                        }

                if 'notes' in entry:
                    vals['notes'] = (entry.get('notes') or '') if entry.get('notes') is not None else ''

                if 'requires_action' in entry:
                    vals['requires_action'] = bool(entry.get('requires_action'))

                if 'severity' in entry and entry.get('severity') is not None:
                    sev = entry.get('severity')
                    if sev in (False, '', None):
                        vals['severity'] = False
                    elif sev in ('low', 'medium', 'high', 'critical'):
                        vals['severity'] = sev
                    else:
                        return {
                            'success': False,
                            'error': 'invalid_severity',
                            'message': 'severity must be low, medium, high, critical, or empty',
                        }

                photo_cmds = []
                photo_payloads = entry.get('photos') or []
                if photo_payloads:
                    if not isinstance(photo_payloads, list):
                        return {'success': False, 'error': 'invalid_photos', 'message': 'photos must be a list'}
                    new_ids = self._compliance_create_item_photo_attachments(item, photo_payloads)
                    if new_ids:
                        photo_cmds = [(4, i) for i in new_ids]

                if photo_cmds:
                    vals['photo_ids'] = photo_cmds

                if vals:
                    item.write(vals)
                updated.append(item.id)

            audit.invalidate_recordset()
            return {
                'success': True,
                'message': 'Checklist updated',
                'updated_item_ids': updated,
                'audit': self._compliance_serialize_audit_row(audit, user),
                'items': [
                    self._compliance_serialize_item(i)
                    for i in audit.checklist_ids
                ],
            }
        except (AccessError, ValidationError) as e:
            _logger.warning('[Compliance API] Items save access/validation: %s', e)
            return {'success': False, 'error': 'validation', 'message': str(e)}
        except Exception as e:
            _logger.exception('[Compliance API] Items save failed')
            return {'success': False, 'error': 'unexpected', 'message': str(e)}

    # Debug endpoint removed for production use
    # @http.route('/guardpro/api/debug/user-info', type='json', auth='user', methods=['POST'], csrf=False)
    # def debug_user_info(self):
    #     """Debug endpoint to check user setup."""
    #     pass

    @http.route('/guardpro/api/guard/check_profile', type='json', auth='user', methods=['POST'], csrf=False)
    def check_guard_profile(self):
        """Check if current user has a guard profile and location sharing settings."""
        try:
            # Use sudo() to allow guards to access their own profile
            guard = request.env['guard.profile'].sudo().search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if guard:
                return {
                    'is_guard': True,
                    'guard_id': guard.id,
                    'guard_name': guard.name,
                    'location_sharing_enabled': guard.location_sharing_enabled,
                }
            else:
                return {
                    'is_guard': False,
                }
        except Exception as e:
            _logger.error('[GPS] Error checking guard profile: %s', str(e), exc_info=True)
            return {
                'is_guard': False,
                'error': str(e)
            }

    # Location pings are the single highest-volume endpoint in the
    # system (native LocationService pings every 30 s and the WebView
    # polls on top of that). Cap at 120/min/user - normal usage hits
    # 2-4/min, so this leaves 30x+ headroom for queued offline flush
    # bursts while blocking runaway loops or spoof-at-scale attempts.
    @rate_limit(max_requests=120, window_seconds=60,
                error_code='LOCATION_RATE_LIMITED')
    @http.route('/guardpro/api/location/update', type='json', auth='user', methods=['POST'], csrf=False)
    def update_location(self, latitude, longitude, accuracy=None, speed=None, heading=None, 
                       battery_level=None, device_id=None, device_info=None, **kwargs):
        """Update guard's current GPS location with extended device telemetry."""
        # Reject nonsense coordinates before they hit the DB. A stuck
        # sensor can easily report 0/0 or NaN; a hostile client could
        # spoof (89.9, 179). We want the location history to be usable
        # for geofencing / incident forensics, so filter aggressively.
        #
        # IMPORTANT: on rejection we return ``success=True`` rather
        # than surfacing an error. The native LocationService treats
        # any error response as "queue and retry", which would cause
        # an infinite re-upload loop for a payload the server will
        # keep refusing. We'd rather silently drop the bad fix and
        # let the next real one through.
        import math

        def _drop(reason, **extra):
            _logger.warning(
                '[GPS] Dropping fix from user %s: %s (%s)',
                request.env.user.id, reason, extra,
            )
            return {
                'success': True,
                'dropped': True,
                'drop_reason': reason,
                'timestamp': fields.Datetime.now().isoformat(),
            }

        try:
            lat_f = float(latitude)
            lon_f = float(longitude)
        except (TypeError, ValueError):
            return _drop('bad_coord_type', lat=latitude, lon=longitude)
        if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
            return _drop('non_finite', lat=lat_f, lon=lon_f)
        if not (-90.0 <= lat_f <= 90.0) or not (-180.0 <= lon_f <= 180.0):
            return _drop('out_of_range', lat=lat_f, lon=lon_f)
        # (0,0) is the "null island" sentinel Android's fused provider
        # occasionally returns during cold-start before a real fix is
        # available. Drop it so the guard's path isn't polluted with
        # an imaginary trip to the Atlantic.
        if lat_f == 0.0 and lon_f == 0.0:
            return _drop('null_island')
        # Reject wildly-poor accuracy fixes (> 5 km). A real GPS/cell
        # fix is usually <= 100 m; anything beyond a few hundred metres
        # is cell-tower guesswork and just adds noise to the history.
        if accuracy is not None:
            try:
                acc_f = float(accuracy)
                if math.isfinite(acc_f) and acc_f > 5000.0:
                    return _drop('low_accuracy', accuracy=acc_f)
            except (TypeError, ValueError):
                accuracy = None
        latitude = lat_f
        longitude = lon_f

        # Log the request for debugging
        _logger.info(
            '[GPS] Location update from %s (ID: %s) - lat: %s, lon: %s, acc: %s, bat: %s',
            request.env.user.name,
            request.env.user.id,
            latitude,
            longitude,
            accuracy,
            battery_level
        )
        
        # Use sudo() to allow guards to access and update their own profile
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            _logger.warning('[GPS] Guard profile not found for user %s', request.env.user.name)
            return {'error': 'Guard profile not found'}
        
        try:
            # Prepare update values for guard profile
            update_vals = {}
            if device_id:
                update_vals['device_id'] = device_id
            if device_info:
                update_vals['device_model'] = device_info
            
            # Update device info if provided
            if update_vals:
                guard.write(update_vals)

            # Call model update_location with all telemetry
            # The model's update_location accepts **kwargs and passes them to _save_location_history
            guard.update_location(
                latitude, 
                longitude, 
                accuracy=accuracy,
                speed=speed,
                heading=heading,
                battery_level=battery_level,
                device_info=device_info
            )
            
            return {
                'success': True,
                'guard_id': guard.id,
                'timestamp': fields.Datetime.now().isoformat()
            }
        except Exception as e:
            _logger.error('[GPS] Update failed: %s', str(e), exc_info=True)
            return {'error': str(e)}

    @http.route('/guardpro/api/stats/dashboard', type='json', auth='user', methods=['POST'], csrf=False)
    def get_dashboard_stats(self, guard_id=None):
        """Get dashboard statistics for guard."""
        try:
            # Get guard profile
            # Use sudo() to allow guards to access their own profile regardless of site assignment
            if guard_id:
                guard = request.env['guard.profile'].sudo().browse(guard_id)
            else:
                guard = request.env['guard.profile'].sudo().search([
                    ('user_id', '=', request.env.user.id)
                ], limit=1)
            
            if not guard:
                return {'error': 'Guard profile not found'}
            
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
            
            # Week's date range (last 7 days)
            week_start = today_start - timedelta(days=7)
            
            # PRIVACY FIX: Get stats for THIS GUARD only, not all guards at their sites
            # Use sudo() as guards need to access their own data regardless of site assignment
            # Get today's shifts for THIS guard
            today_shifts = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),  # ✅ Only this guard
                ('start_datetime', '<', today_end),
                ('end_datetime', '>', today_start)
            ])
            
            # Get completed shifts today for THIS guard
            completed_shifts = today_shifts.filtered(lambda s: s.status == 'completed')
            
            # Get available tours from today's shifts (tours that SHOULD be done)
            available_tours = request.env['security.tour'].sudo()
            for shift in today_shifts:
                available_tours |= shift.tour_ids.filtered(lambda t: t.status == 'active')
            
            # Get ONLY TODAY'S tour logs for this guard
            # Only show tours that started today (not old in-progress tours)
            today_tour_logs = request.env['tour.log'].sudo().search([
                ('guard_id', '=', guard.id),  # ✅ Only this guard
                ('start_time', '>=', today_start),  # Started today or later
                ('start_time', '<', today_end)  # But before tomorrow
            ])
            
            # Get open rounds (in progress) - ONLY from today's tour logs
            open_rounds = today_tour_logs.filtered(lambda r: r.status == 'in_progress')
            
            # Get completed rounds today - ONLY from today's tour logs
            completed_rounds = today_tour_logs.filtered(lambda r: r.status == 'completed')
            
            # FIXED: Expected rounds calculation - based on available tours from today's shifts
            # Only count tours that should be done today
            if today_shifts:
                # Tours that should be done based on today's shifts
                expected_rounds_count = len(available_tours)
            else:
                # No shifts today, no expected tours
                expected_rounds_count = 0
            
            # Get incidents reported by THIS guard (not all site incidents)
            open_incidents = request.env['incident.report'].sudo().search([
                ('guard_id', '=', guard.id),  # ✅ Only this guard
                ('status', 'in', ['open', 'investigating', 'pending'])
            ])
            
            # Get weekly performance data for THIS guard
            week_shifts = request.env['guard.shift'].sudo().search([
                ('guard_id', '=', guard.id),  # ✅ Only this guard
                ('start_datetime', '>=', week_start),
                ('end_datetime', '<=', today_end)
            ])
            
            # Calculate hours worked this week
            total_hours = 0
            for shift in week_shifts.filtered(lambda s: s.status == 'completed'):
                if shift.checkin_time and shift.checkout_time:
                    duration = shift.checkout_time - shift.checkin_time
                    total_hours += duration.total_seconds() / 3600
            
            # Calculate performance score (based on completed shifts vs total assigned)
            performance_score = 0
            if week_shifts:
                completed_week = week_shifts.filtered(lambda s: s.status == 'completed')
                performance_score = (len(completed_week) / len(week_shifts)) * 100
            
            # Calculate punctuality (shifts started on time)
            punctual_shifts = 0
            for shift in week_shifts.filtered(lambda s: s.checkin_time):
                # Allow 15 minutes grace period
                if shift.checkin_time <= shift.start_datetime + timedelta(minutes=15):
                    punctual_shifts += 1
            
            punctuality = (punctual_shifts / len(week_shifts)) * 100 if week_shifts else 100
            
            return {
                'shifts_today': len(today_shifts),
                'shifts_completed': len(completed_shifts),
                'completed_security_rounds': len(completed_rounds),
                'incidents_reported': len(open_incidents),
                'hours_worked_week': round(total_hours, 1),
                'performance_score': round(performance_score, 1),
                'punctuality': round(punctuality, 1),
                # FIXED: Rounds data for dashboard - now consistent
                'rounds_today': len(today_tour_logs),  # Total tour logs for today
                'rounds_open': len(open_rounds),  # Currently in progress
                'rounds_completed': len(completed_rounds),  # Completed today
                'rounds_expected': expected_rounds_count,  # Total tour logs (same as rounds_today)
                'rounds_available': len(available_tours)  # Available tours from shifts (for reference)
            }
            
        except Exception as e:
            _logger.error('Dashboard stats error: %s', str(e))
            return {
                'error': str(e),
                'shifts_today': 0,
                'shifts_completed': 0,
                'completed_security_rounds': 0,
                'incidents_reported': 0,
                'hours_worked_week': 0,
                'performance_score': 0,
                'punctuality': 100,
                'rounds_today': 0,
                'rounds_open': 0,
                'rounds_completed': 0,
                'rounds_expected': 0,
                'rounds_available': 0
            }

    @http.route('/guardpro/api/checkpoints/site/<int:site_id>', type='json', auth='user', methods=['POST'], csrf=False)
    def get_site_checkpoints(self, site_id):
        """Get all checkpoints for a site."""
        checkpoints = request.env['checkpoint'].search([
            ('site_id', '=', site_id),
            ('status', '=', 'active')
        ])
        
        return {
            'checkpoints': [{
                'id': cp.id,
                'name': cp.name,
                'code': cp.code,
                'scan_type': cp.scan_type,
                'nfc_tag_id': cp.nfc_tag_id,
                'qr_code': cp.qr_code,
                'latitude': cp.latitude,
                'longitude': cp.longitude,
                'requires_photo': cp.requires_photo,
                'requires_note': cp.requires_note,
                'instructions': cp.instructions
            } for cp in checkpoints]
        }

    @http.route('/guardpro/api/tour/progress', type='json', auth='user', methods=['POST'], csrf=False)
    def get_tour_progress(self, tour_id=None):
        """Get tour progress data for active tour."""
        guard = request.env['guard.profile'].sudo().search([
            ('user_id', '=', request.env.user.id)
        ], limit=1)
        
        if not guard:
            return {'error': 'Guard profile not found'}
        
        try:
            # Get active tour log for this guard
            active_tour_log = request.env['tour.log'].sudo().search([
                ('guard_id', '=', guard.id),
                ('status', '=', 'in_progress')
            ], order='start_time DESC', limit=1)
            
            if not active_tour_log:
                return {'error': 'No active tour found'}
            
            # Get checkpoint scan status
            scanned_checkpoint_ids = active_tour_log.scan_ids.filtered(
                lambda s: s.status == 'verified'
            ).mapped('checkpoint_id').ids
            
            # Get all tour checkpoints with scan status
            tour_checkpoints = []
            for checkpoint in active_tour_log.tour_id.checkpoint_ids:
                is_scanned = checkpoint.id in scanned_checkpoint_ids
                tour_checkpoints.append({
                    'id': checkpoint.id,
                    'name': checkpoint.name,
                    'code': checkpoint.code,
                    'scan_type': checkpoint.scan_type,
                    'latitude': checkpoint.latitude,
                    'longitude': checkpoint.longitude,
                    'qr_code': checkpoint.qr_code if checkpoint.qr_code else '',
                    'nfc_tag_id': checkpoint.nfc_tag_id if checkpoint.nfc_tag_id else '',
                    'status': 'completed' if is_scanned else 'pending',
                    'scanned_at': None,  # Could be enhanced to get actual scan time
                    'notes': checkpoint.notes if checkpoint.notes else ''
                })
            
            return {
                'success': True,
                'tour_id': active_tour_log.tour_id.id,
                'tour_name': active_tour_log.tour_id.name,
                'tour_log_id': active_tour_log.id,
                'start_time': active_tour_log.start_time.isoformat() + 'Z',
                'scanned_checkpoints': active_tour_log.scanned_checkpoints,
                'expected_checkpoints': active_tour_log.expected_checkpoints,
                'completion_percentage': active_tour_log.completion_percentage,
                'tour_estimated_duration': active_tour_log.tour_id.estimated_duration,  # Add estimated duration
                'checkpoints': tour_checkpoints
            }
            
        except Exception as e:
            _logger.error('Tour progress error: %s', str(e))
            return {'error': str(e)}

    @http.route('/guardpro/api/emergency/check', type='json', auth='user', methods=['POST'], csrf=False)
    def check_emergency_broadcasts(self):
        """Check for pending emergency broadcasts for the current guard."""
        # Use acknowledgment records as source of truth for pending broadcasts.
        # This matches the emergency.broadcast send flow and avoids dependence on
        # chatter message formatting/timing.
        pending_ack = request.env['emergency.broadcast.acknowledgment'].sudo().search([
            ('user_id', '=', request.env.user.id),
            ('is_acknowledged', '=', False),
        ], order='create_date desc', limit=1)

        if not pending_ack:
            return {'emergency': False}

        broadcast = pending_ack.broadcast_id
        return {
            'emergency': True,
            'ack_id': pending_ack.id,
            'broadcast_id': broadcast.id,
            'title': broadcast.title or 'EMERGENCY ALERT',
            'message': broadcast.message or 'Emergency notification received',
            'priority': broadcast.priority or 'urgent',
            'sent_date': broadcast.sent_date.isoformat() if broadcast.sent_date else False,
        }

    @http.route('/guardpro/api/patrol_reminders/check', type='json', auth='user', methods=['POST'], csrf=False)
    def check_patrol_reminders(self):
        """Pending patrol reminder for the logged-in guard only (must acknowledge in app)."""
        rem = request.env['tour.patrol.reminder'].get_pending_mobile_reminder(request.env.user)
        if not rem:
            return {'patrol_reminder': False}
        return {
            'patrol_reminder': True,
            'reminder_id': rem.id,
            'tour_name': rem.tour_id.name or '',
            'site_name': rem.shift_id.site_id.name if rem.shift_id.site_id else '',
            'scheduled_start_iso': rem.scheduled_start.isoformat() if rem.scheduled_start else False,
            'minutes_before': rem.reminder_type,
        }

    @http.route(
        '/guardpro/api/patrol_reminders/pending',
        type='http',
        auth='user',
        methods=['GET'],
        csrf=False,
        website=True,
    )
    def get_pending_patrol_reminder(self, **kwargs):
        """Plain JSON endpoint for TWA/mobile reminder polling."""
        try:
            rem = request.env['tour.patrol.reminder'].get_pending_mobile_reminder(request.env.user)
            if not rem:
                return request.make_json_response(
                    {
                        'success': True,
                        'patrol_reminder': False,
                    },
                    headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
                )

            return request.make_json_response(
                {
                    'success': True,
                    'patrol_reminder': True,
                    'reminder_id': rem.id,
                    'tour_name': rem.tour_id.name or '',
                    'site_name': rem.shift_id.site_id.name if rem.shift_id.site_id else '',
                    'scheduled_start_iso': rem.scheduled_start.isoformat() if rem.scheduled_start else False,
                    'minutes_before': rem.reminder_type,
                },
                headers=[('Cache-Control', 'no-store, no-cache, must-revalidate')],
            )
        except Exception as e:
            _logger.error('Patrol reminder pending failed: %s', str(e))
            return request.make_json_response(
                {
                    'success': False,
                    'error': str(e),
                },
                status=500,
            )

    @http.route(
        '/guardpro/api/patrol_reminders/acknowledge',
        type='http',
        auth='user',
        methods=['POST'],
        csrf=False,
        website=True,
    )
    def acknowledge_patrol_reminder(self, **kwargs):
        """Acknowledge a patrol reminder popup (JSON body: reminder_id)."""
        try:
            user = request.env.user
            data = json.loads(request.httprequest.data.decode('utf-8') or '{}')
            reminder_id = data.get('reminder_id')
            if not reminder_id:
                return request.make_json_response({
                    'success': False,
                    'error': 'reminder_id is required',
                }, status=400)
            reminder = request.env['tour.patrol.reminder'].search([
                ('id', '=', int(reminder_id)),
                ('user_id', '=', user.id),
            ], limit=1)
            if not reminder:
                return request.make_json_response({
                    'success': False,
                    'error': 'Reminder not found or not authorized',
                }, status=404)
            reminder.action_acknowledge()
            return request.make_json_response({'success': True})
        except ValueError:
            return request.make_json_response({
                'success': False,
                'error': 'Invalid reminder_id',
            }, status=400)
        except Exception as e:
            _logger.error('Patrol reminder acknowledge failed: %s', str(e))
            return request.make_json_response({
                'success': False,
                'error': str(e),
            }, status=500)

    @http.route('/guardpro/api/buddy/assistance-requests', type='json', auth='user', methods=['POST'], csrf=False)
    def get_assistance_requests(self, **kwargs):
        """Get pending assistance requests for the current guard."""
        try:
            # Get current guard
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'error': 'Guard profile not found'}
            
            # For now, return empty list (this feature can be implemented with a dedicated model later)
            # In a full implementation, you would search for assistance request records
            return {
                'success': True,
                'requests': [],
                'count': 0
            }
            
        except Exception as e:
            _logger.error('Error getting assistance requests: %s', str(e))
            return {'error': 'Failed to get assistance requests'}
    
    @http.route('/guardpro/api/buddy/nearby-guards', type='json', auth='user', methods=['POST'], csrf=False)
    def get_nearby_guards(self):
        """Get nearby guards for buddy system."""
        try:
            # Get current guard
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)
            
            if not guard:
                return {'error': 'Guard profile not found'}, 404
            
            # Get all other guards (excluding current guard)
            nearby_guards = request.env['guard.profile'].search([
                ('id', '!=', guard.id),
                ('status', '=', 'active')
            ])
            
            guards_data = []
            for g in nearby_guards:
                guards_data.append({
                    'id': g.id,
                    'name': g.name,
                    'badge_number': g.badge_number,
                    'phone': g.phone,
                    'status': g.status,
                    'current_site': g.current_site_id.name if g.current_site_id else None,
                    'last_seen': g.last_seen.isoformat() if g.last_seen else None
                })
            
            return {
                'success': True,
                'guards': guards_data,
                'count': len(guards_data)
            }
            
        except Exception as e:
            _logger.error('Error getting nearby guards: %s', str(e))
            return {'error': 'Failed to get nearby guards'}, 500

    # ==========================================
    # Mobile Training API Methods
    # ==========================================

    @http.route('/guardpro/api/training/courses', type='json', auth='user', methods=['POST'], csrf=False)
    def get_training_courses(self):
        """Get list of available training courses for the current guard."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'error': 'Guard profile not found'}, 404

            # Get all guard training courses
            courses = request.env['slide.channel'].sudo().search([
                ('is_guard_training', '=', True)
            ])

            course_data = []
            for course in courses:
                # Get enrollment status
                enrollment = request.env['slide.channel.partner'].sudo().search([
                    ('channel_id', '=', course.id),
                    ('partner_id', '=', request.env.user.partner_id.id)
                ], limit=1)

                # Check if course is mandatory for this guard
                is_mandatory = course.is_mandatory_for_guards

                # If site-specific, check if guard's site requires it
                if course.required_for_sites and guard.current_site_id:
                    is_mandatory = guard.current_site_id in course.required_for_sites

                course_data.append({
                    'id': course.id,
                    'name': course.name,
                    'description': course.description_short or course.description[:200] + '...',
                    'category': course.training_category,
                    'duration': course.total_time,
                    'mandatory': is_mandatory,
                    'enrolled': bool(enrollment),
                    'status': enrollment.member_status if enrollment else 'not_enrolled',
                    'progress': enrollment.completion if enrollment else 0,
                    'passed': enrollment.passed_course if enrollment else False,
                    'certification_status': enrollment.certification_status if enrollment else 'none',
                    'certification_expiry': enrollment.certification_expiry_date.strftime('%Y-%m-%d') if enrollment and enrollment.certification_expiry_date else None,
                })

            return {
                'courses': course_data,
                'total_courses': len(course_data),
                'mandatory_completed': len([c for c in course_data if c['mandatory'] and c['status'] == 'completed' and c['passed']]),
                'mandatory_total': len([c for c in course_data if c['mandatory']]),
            }

        except Exception as e:
            _logger.error('Error getting training courses: %s', str(e))
            return {'error': 'Failed to get training courses'}, 500

    @http.route('/guardpro/api/training/course/<int:course_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_course_details(self, course_id):
        """Get detailed information about a specific course including slides."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return Response(
                    json.dumps({'error': 'Guard profile not found'}),
                    status=404,
                    mimetype='application/json'
                )

            course = request.env['slide.channel'].sudo().browse(course_id)
            if not course.exists() or not course.is_guard_training:
                return Response(
                    json.dumps({'error': 'Course not found'}),
                    status=404,
                    mimetype='application/json'
                )

            # Get enrollment
            enrollment = request.env['slide.channel.partner'].sudo().search([
                ('channel_id', '=', course_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            # Get slides
            slides = course.slide_ids.sorted('sequence')
            slide_data = []

            for slide in slides:
                # Check completion status
                slide_partner = request.env['slide.slide.partner'].sudo().search([
                    ('slide_id', '=', slide.id),
                    ('partner_id', '=', request.env.user.partner_id.id)
                ], limit=1)

                # Unescape HTML content if present
                html_content = None
                if slide.slide_category in ['article', 'infographic']:
                    html_content_raw = slide.html_content or ''
                    if html_content_raw:
                        html_content = html.unescape(html_content_raw)
                
                slide_data.append({
                    'id': slide.id,
                    'name': slide.name,
                    'category': slide.slide_category,
                    'sequence': slide.sequence,
                    'completed': slide_partner.completed if slide_partner else False,
                    'completion_time': slide.completion_time,
                    'html_content': html_content,
                })

            # Check if course is mandatory for this guard
            is_mandatory = course.is_mandatory_for_guards
            if course.required_for_sites and guard.current_site_id:
                is_mandatory = guard.current_site_id in course.required_for_sites

            return Response(
                json.dumps({
                    'course': {
                        'id': course.id,
                        'name': course.name,
                        'description': course.description,
                        'category': course.training_category,
                        'duration': course.total_time,
                        'mandatory': is_mandatory,
                        'passing_score': course.minimum_passing_score,
                        'certification_validity': course.certification_validity_months,
                        'enrolled': bool(enrollment),
                        'status': enrollment.member_status if enrollment else 'not_enrolled',
                        'progress': enrollment.completion if enrollment else 0,
                        'passed': enrollment.passed_course if enrollment else False,
                        'certification_status': enrollment.certification_status if enrollment else 'none',
                        'certification_expiry': enrollment.certification_expiry_date.strftime('%Y-%m-%d') if enrollment and enrollment.certification_expiry_date else None,
                    },
                    'slides': slide_data,
                    'total_slides': len(slide_data),
                    'completed_slides': len([s for s in slide_data if s['completed']]),
                }),
                mimetype='application/json'
            )

        except Exception as e:
            _logger.error('Error getting course details: %s', str(e))
            import traceback
            _logger.error('Error traceback: %s', traceback.format_exc())
            return Response(
                json.dumps({'error': 'Failed to get course details'}),
                status=500,
                mimetype='application/json'
            )

    @http.route('/guardpro/api/training/enroll/<int:course_id>', type='http', auth='user', methods=['POST'], csrf=False)
    def enroll_in_course(self, course_id):
        """Enroll the current guard in a training course."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return Response(
                    json.dumps({'error': 'Guard profile not found'}),
                    status=404,
                    mimetype='application/json'
                )

            course = request.env['slide.channel'].sudo().browse(course_id)
            if not course.exists() or not course.is_guard_training:
                return Response(
                    json.dumps({'error': 'Course not found'}),
                    status=404,
                    mimetype='application/json'
                )

            # Check if already enrolled
            existing_enrollment = request.env['slide.channel.partner'].sudo().search([
                ('channel_id', '=', course_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            if existing_enrollment:
                return Response(
                    json.dumps({'error': 'Already enrolled in this course'}),
                    status=400,
                    mimetype='application/json'
                )

            # Create enrollment
            enrollment = request.env['slide.channel.partner'].sudo().create({
                'channel_id': course_id,
                'partner_id': request.env.user.partner_id.id,
                'member_status': 'joined',
            })

            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Successfully enrolled in course',
                    'enrollment_id': enrollment.id,
                    'status': 'joined',
                    'progress': 0,
                }),
                mimetype='application/json'
            )

        except Exception as e:
            _logger.error('Error enrolling in course: %s', str(e))
            import traceback
            _logger.error('Error traceback: %s', traceback.format_exc())
            return Response(
                json.dumps({'error': 'Failed to enroll in course'}),
                status=500,
                mimetype='application/json'
            )

    @http.route('/guardpro/api/training/slide/<int:slide_id>/complete', type='http', auth='user', methods=['POST'], csrf=False)
    def complete_slide(self, slide_id):
        """Mark a slide as completed."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return Response(
                    json.dumps({'error': 'Guard profile not found'}),
                    status=404,
                    mimetype='application/json'
                )

            slide = request.env['slide.slide'].sudo().browse(slide_id)
            if not slide.exists():
                return Response(
                    json.dumps({'error': 'Slide not found'}),
                    status=404,
                    mimetype='application/json'
                )

            # Get or create slide partner record
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            if not slide_partner:
                slide_partner = request.env['slide.slide.partner'].sudo().create({
                    'slide_id': slide_id,
                    'partner_id': request.env.user.partner_id.id,
                    'channel_id': slide.channel_id.id,
                })

            # Mark as completed
            slide_partner.write({'completed': True})

            # Update enrollment progress
            enrollment = request.env['slide.channel.partner'].sudo().search([
                ('channel_id', '=', slide.channel_id.id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            if enrollment:
                # Recalculate completion percentage
                total_slides = len(slide.channel_id.slide_ids)
                completed_slides = len(slide.channel_id.slide_ids.filtered(
                    lambda s: request.env['slide.slide.partner'].sudo().search([
                        ('slide_id', '=', s.id),
                        ('partner_id', '=', request.env.user.partner_id.id),
                        ('completed', '=', True)
                    ])
                ))

                progress = (completed_slides / total_slides * 100) if total_slides > 0 else 0

                # Check if course is completed
                if progress >= 100:
                    enrollment.write({'member_status': 'completed'})
                    # Trigger final score calculation and certification
                    enrollment._compute_final_score()
                    enrollment._compute_passed_course()
                    enrollment._compute_certification_date()

            return Response(
                json.dumps({
                    'success': True,
                    'message': 'Slide completed successfully',
                    'slide_id': slide_id,
                    'course_progress': progress if 'progress' in locals() else 0,
                }),
                mimetype='application/json'
            )

        except Exception as e:
            _logger.error('Error completing slide: %s', str(e))
            import traceback
            _logger.error('Error traceback: %s', traceback.format_exc())
            return Response(
                json.dumps({'error': 'Failed to complete slide'}),
                status=500,
                mimetype='application/json'
            )

    @http.route('/guardpro/api/training/quiz/<int:slide_id>/submit', type='http', auth='user', methods=['POST'], csrf=False)
    def submit_quiz(self, slide_id, **post):
        """Submit quiz answers and calculate score."""
        try:
            # Parse JSON body safely
            body = request.httprequest.data
            if not body:
                return Response(
                    json.dumps({'error': 'Empty request body'}),
                    status=400,
                    mimetype='application/json'
                )
            
            try:
                data = json.loads(body.decode('utf-8'))
            except Exception as je:
                _logger.error('JSON parse error in submit_quiz: %s', str(je))
                return Response(
                    json.dumps({'error': 'Invalid JSON format'}),
                    status=400,
                    mimetype='application/json'
                )
            
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return Response(
                    json.dumps({'error': 'Guard profile not found'}),
                    status=404,
                    mimetype='application/json'
                )

            slide = request.env['slide.slide'].sudo().browse(slide_id)
            if not slide.exists() or slide.slide_category != 'quiz':
                return Response(
                    json.dumps({'error': 'Quiz not found'}),
                    status=404,
                    mimetype='application/json'
                )

            answers = data.get('answers', {})
            if not answers:
                return Response(
                    json.dumps({'error': 'No answers provided'}),
                    status=400,
                    mimetype='application/json'
                )

            # Process answers and calculate score
            questions = getattr(slide, 'question_ids', request.env['slide.question'])
            correct_answers = 0
            total_questions = len(questions)
            quiz_line_data = []

            for question in questions:
                question_id = str(question.id)
                is_question_correct = False
                answer_vals = {
                    'question_id': question.id,
                }

                if question_id in answers:
                    response_value = answers[question_id]
                    selected_answer_ids = response_value if isinstance(response_value, list) else [response_value]

                    question_type = getattr(question, 'question_type', None) or getattr(question, 'type', None) or 'multiple_choice'

                    # Get answer records
                    answer_records = getattr(question, 'answer_ids', None) or getattr(question, 'option_ids', None) or getattr(question, 'suggested_answer_ids', None) or []

                    correct_answer_ids = []
                    for answer in answer_records:
                        if getattr(answer, 'is_correct', False):
                            correct_answer_ids.append(answer.id)

                    # Handle short answer questions
                    if question_type == 'short_answer':
                        answer_vals['answer_text'] = str(response_value)
                        correct_answer = getattr(question, 'correct_answer', None)
                        if correct_answer:
                            if str(response_value).strip().lower() == str(correct_answer).strip().lower():
                                is_question_correct = True
                        elif str(response_value).strip():
                            is_question_correct = True
                    else:
                        # Multiple choice / True-False
                        clean_ids = [int(i) for i in selected_answer_ids if str(i).isdigit()]
                        answer_vals['answer_ids'] = [(6, 0, clean_ids)]
                        
                        if not correct_answer_ids:
                            if clean_ids:
                                is_question_correct = True
                        elif set(clean_ids) == set(correct_answer_ids):
                            is_question_correct = True
                    
                    if is_question_correct:
                        correct_answers += 1
                    
                    answer_vals['is_correct'] = is_question_correct
                    answer_vals['score'] = 100.0 if is_question_correct else 0.0
                
                quiz_line_data.append((0, 0, answer_vals))

            score = (correct_answers / total_questions * 100) if total_questions > 0 else 0
            
            _logger.info('[Training API] Quiz submitted: slide_id=%s, score=%2.2f%%, questions=%s/%s', 
                        slide_id, score, correct_answers, total_questions)

            # Record quiz attempt
            passing_score = slide.channel_id.minimum_passing_score

            # Get or create slide partner record
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            if not slide_partner:
                slide_partner = request.env['slide.slide.partner'].sudo().create({
                    'slide_id': slide_id,
                    'partner_id': request.env.user.partner_id.id,
                    'channel_id': slide.channel_id.id,
                })

            # Clear old responses for this quiz attempt
            slide_partner.quiz_line_ids.unlink()

            # Update score and responses
            update_vals = {
                'quiz_score': score / 100.0,
                'quiz_line_ids': quiz_line_data
            }
            if total_questions > 0 and score >= passing_score:
                update_vals['completed'] = True
                _logger.info('[Training API] Quiz passed for slide_id=%s', slide_id)
            elif total_questions == 0:
                # If no questions, mark as completed anyway
                update_vals['completed'] = True
                _logger.warning('[Training API] Quiz slide %s has no questions, marking as completed.', slide_id)
            else:
                _logger.info('[Training API] Quiz failed for slide_id=%s (score %s < %s)', 
                            slide_id, score, passing_score)
            
            slide_partner.write(update_vals)

            if update_vals.get('completed'):
                # Update enrollment progress
                enrollment = request.env['slide.channel.partner'].sudo().search([
                    ('channel_id', '=', slide.channel_id.id),
                    ('partner_id', '=', request.env.user.partner_id.id)
                ], limit=1)

                if enrollment:
                    total_slides = len(slide.channel_id.slide_ids)
                    completed_slides = len(slide.channel_id.slide_ids.filtered(
                        lambda s: request.env['slide.slide.partner'].sudo().search([
                            ('slide_id', '=', s.id),
                            ('partner_id', '=', request.env.user.partner_id.id),
                            ('completed', '=', True)
                        ])
                    ))

                    progress = (completed_slides / total_slides * 100) if total_slides > 0 else 0

                    if progress >= 100:
                        enrollment.write({'member_status': 'completed'})
                    
                    # Recalculate everything
                    enrollment._compute_final_score()
                    enrollment._compute_passed_course()
                    enrollment._compute_certification_date()

                return Response(
                    json.dumps({
                        'success': True,
                        'passed': True,
                        'score': score,
                        'correct_answers': correct_answers,
                        'total_questions': total_questions,
                        'course_progress': progress if 'progress' in locals() else 0,
                        'message': 'Quiz passed successfully!',
                    }),
                    mimetype='application/json'
                )
            else:
                return Response(
                    json.dumps({
                        'success': True,
                        'passed': False,
                        'score': score,
                        'correct_answers': correct_answers,
                        'total_questions': total_questions,
                        'message': 'Quiz failed. Please review the material and try again.',
                    }),
                    mimetype='application/json'
                )

        except Exception as e:
            _logger.error('Error submitting quiz: %s', str(e))
            import traceback
            _logger.error('Error traceback: %s', traceback.format_exc())
            return Response(
                json.dumps({'error': 'Failed to submit quiz'}),
                status=500,
                mimetype='application/json'
            )

    @http.route('/guardpro/api/training/certifications', type='json', auth='user', methods=['POST'], csrf=False)
    def get_certifications(self):
        """Get guard's certifications and training status."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return {'error': 'Guard profile not found'}, 404

            # Get all enrollments
            enrollments = request.env['slide.channel.partner'].sudo().search([
                ('partner_id', '=', request.env.user.partner_id.id),
                ('member_status', '=', 'completed')
            ])

            certifications = []
            for enrollment in enrollments:
                if enrollment.passed_course:
                    certifications.append({
                        'course_id': enrollment.channel_id.id,
                        'course_name': enrollment.channel_id.name,
                        'issued_date': enrollment.certification_issued_date.strftime('%Y-%m-%d') if enrollment.certification_issued_date else None,
                        'expiry_date': enrollment.certification_expiry_date.strftime('%Y-%m-%d') if enrollment.certification_expiry_date else None,
                        'status': enrollment.certification_status,
                        'score': enrollment.final_score,
                        'validity_months': enrollment.channel_id.certification_validity_months,
                    })

            # Calculate training statistics
            total_enrollments = len(enrollments)
            passed_courses = len([e for e in enrollments if e.passed_course])
            valid_certifications = len([c for c in certifications if c['status'] == 'valid'])
            expiring_certifications = len([c for c in certifications if c['status'] == 'expiring'])
            expired_certifications = len([c for c in certifications if c['status'] == 'expired'])

            return {
                'certifications': certifications,
                'statistics': {
                    'total_enrollments': total_enrollments,
                    'passed_courses': passed_courses,
                    'valid_certifications': valid_certifications,
                    'expiring_certifications': expiring_certifications,
                    'expired_certifications': expired_certifications,
                }
            }

        except Exception as e:
            _logger.error('Error getting certifications: %s', str(e))
            return {'error': 'Failed to get certifications'}, 500

    @http.route('/guardpro/api/training/slide/<int:slide_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_slide_content(self, slide_id):
        """Get slide content for mobile viewing."""
        try:
            _logger.info('[Training API] Getting slide content for slide_id=%s, user=%s', slide_id, request.env.user.login)
            
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                _logger.warning('[Training API] Guard profile not found for user=%s', request.env.user.login)
                return Response(
                    json.dumps({'error': 'Guard profile not found. Please ensure you are logged in as a guard.'}),
                    status=404,
                    mimetype='application/json'
                )

            slide = request.env['slide.slide'].sudo().browse(slide_id)
            if not slide.exists():
                _logger.warning('[Training API] Slide not found: slide_id=%s', slide_id)
                return Response(
                    json.dumps({'error': 'Slide not found. The training content may have been removed or moved.'}),
                    status=404,
                    mimetype='application/json'
                )
            
            _logger.info('[Training API] Slide found: id=%s, name=%s, category=%s', slide.id, slide.name, slide.slide_category)
            
            # Log available fields for debugging
            _logger.debug('[Training API] Slide fields - html_content: %s, description: %s, content: %s', 
                         bool(getattr(slide, 'html_content', None)),
                         bool(getattr(slide, 'description', None)),
                         bool(getattr(slide, 'content', None)))

            # Check completion status
            slide_partner = request.env['slide.slide.partner'].sudo().search([
                ('slide_id', '=', slide_id),
                ('partner_id', '=', request.env.user.partner_id.id)
            ], limit=1)

            # Get slide category safely (Odoo 19 fallback fields)
            slide_category_raw = getattr(slide, 'slide_category', None) or getattr(slide, 'slide_type', None)
            questions = getattr(slide, 'question_ids', request.env['slide.question'])
            has_quiz = bool(questions) and len(questions) > 0
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
                    # Guard against incorrectly labeled quiz slides
                    slide_category = 'article'
            
            # Handle different slide types
            html_content = ''
            slide_description = getattr(slide, 'description', '') or getattr(slide, 'description_short', '') or ''
            
            if slide_category in ['article', 'infographic']:
                # Get HTML content for article/infographic slides
                html_content_raw = getattr(slide, 'html_content', '') or ''
                
                # Also try 'content' field if html_content is empty
                if not html_content_raw:
                    html_content_raw = getattr(slide, 'content', '') or ''
                
                if html_content_raw:
                    try:
                        # Convert to string if needed
                        if hasattr(html_content_raw, '__html__'):
                            html_content = str(html_content_raw)
                        elif isinstance(html_content_raw, str):
                            html_content = html_content_raw
                        else:
                            html_content = str(html_content_raw) if html_content_raw else ''
                        
                        # Unescape HTML entities so they render properly
                        if html_content:
                            html_content = html.unescape(html_content)
                    except (TypeError, AttributeError) as e:
                        _logger.warning('[Training API] Error processing html_content: %s', str(e))
                        html_content = ''
                
                # If still empty, try to use description or create helpful content
                if not html_content or html_content.strip() == '':
                    slide_name = slide.name or 'Untitled Lesson'
                    
                    # Build content from available fields
                    content_parts = []
                    content_parts.append(f'<div class="alert alert-info">')
                    content_parts.append(f'<h4 class="alert-heading">{slide_name}</h4>')
                    
                    if slide_description:
                        # Convert description to string and unescape
                        try:
                            desc_str = str(slide_description)
                            if hasattr(slide_description, '__html__'):
                                desc_str = str(slide_description)
                            desc_str = html.unescape(desc_str)
                            # Remove HTML tags if it's plain text wrapped in tags
                            if desc_str.strip().startswith('<') and desc_str.strip().endswith('>'):
                                # Might be wrapped in a single tag, try to extract content
                                text_content = re.sub(r'<[^>]+>', '', desc_str)
                                if text_content.strip():
                                    desc_str = text_content
                            content_parts.append(f'<p>{desc_str}</p>')
                        except Exception as e:
                            _logger.warning('[Training API] Error processing description: %s', str(e))
                    
                    content_parts.append('<hr>')
                    content_parts.append('<p class="mb-0"><small><i class="fa fa-info-circle me-1"></i>This lesson content is being prepared for mobile viewing. Please contact your supervisor if you need assistance.</small></p>')
                    content_parts.append('</div>')
                    
                    html_content = ''.join(content_parts)
                else:
                    # Content exists, but add description if available and not already in content
                    if slide_description and slide_description not in html_content:
                        try:
                            desc_str = str(slide_description)
                            if hasattr(slide_description, '__html__'):
                                desc_str = str(slide_description)
                            desc_str = html.unescape(desc_str)
                            # Only add if it's substantial content (more than just a few words)
                            if len(desc_str.strip()) > 20:
                                html_content = f'<div class="mb-3"><p class="lead">{desc_str}</p></div>' + html_content
                        except Exception:
                            pass
            
            elif slide_category == 'quiz':
                # Quiz content is loaded via quiz endpoint
                html_content = '<div class="alert alert-info"><p><strong>Knowledge Check</strong></p><p>Tap "Take Quiz" to start this assessment.</p></div>'
            
            elif slide_category == 'video':
                # Handle video slides
                video_url = getattr(slide, 'video_url', '') or ''
                if video_url:
                    html_content = f'<div class="embed-responsive embed-responsive-16by9"><iframe class="embed-responsive-item" src="{video_url}" allowfullscreen></iframe></div>'
                else:
                    html_content = '<div class="alert alert-warning"><p><strong>Video Lesson: ' + (slide.name or 'Untitled') + '</strong></p><p>The video content is not available at this time. Please try again later or contact your supervisor.</p></div>'
            
            elif slide_category == 'document':
                # Handle document slides
                document_url = getattr(slide, 'document_url', '') or ''
                if document_url:
                    html_content = f'<div class="alert alert-info"><p><strong>Document: ' + (slide.name or 'Untitled') + '</strong></p><p><a href="{document_url}" target="_blank" class="btn btn-primary">Open Document</a></p></div>'
                else:
                    html_content = '<div class="alert alert-warning"><p><strong>Document: ' + (slide.name or 'Untitled') + '</strong></p><p>The document is not available at this time. Please contact your supervisor.</p></div>'
            
            else:
                # Default fallback for other slide types
                html_content = '<div class="alert alert-info"><p><strong>' + (slide.name or 'Untitled') + '</strong></p><p>This content is being prepared. Please try again later.</p></div>'
            
            # Ensure html_content is always a string
            if not isinstance(html_content, str):
                html_content = str(html_content) if html_content else '<p>Content unavailable</p>'
            
            slide_data = {
                'id': slide.id,
                'name': slide.name or 'Untitled Lesson',
                'category': slide_category,
                'html_content': html_content,
                'completed': slide_partner.completed if slide_partner else False,
                'has_quiz': has_quiz,
            }
            
            _logger.info('[Training API] Returning slide data: id=%s, name=%s, content_length=%s', 
                        slide.id, slide.name, len(html_content))
            
            return Response(
                json.dumps({'slide': slide_data}),
                mimetype='application/json'
            )

        except Exception as e:
            _logger.error('[Training API] Error getting slide content: %s', str(e), exc_info=True)
            import traceback
            _logger.error('[Training API] Traceback: %s', traceback.format_exc())
            return Response(
                json.dumps({'error': 'Unable to load slide content. Please try again or contact support if the problem persists.'}),
                status=500,
                mimetype='application/json'
            )

    @http.route('/guardpro/api/training/quiz/<int:slide_id>', type='http', auth='user', methods=['GET'], csrf=False)
    def get_quiz_questions(self, slide_id):
        """Get quiz questions for mobile quiz taking."""
        try:
            guard = request.env['guard.profile'].search([
                ('user_id', '=', request.env.user.id)
            ], limit=1)

            if not guard:
                return Response(
                    json.dumps({'error': 'Guard profile not found'}),
                    status=404,
                    mimetype='application/json'
                )

            slide = request.env['slide.slide'].sudo().browse(slide_id)
            if not slide.exists():
                return Response(
                    json.dumps({'error': 'Quiz not found'}),
                    status=404,
                    mimetype='application/json'
                )

            # Accept quiz if slide is marked as quiz or has questions (Odoo 19 fallback)
            slide_category = getattr(slide, 'slide_category', None) or getattr(slide, 'slide_type', None)
            questions = getattr(slide, 'question_ids', request.env['slide.question'])
            has_questions = bool(questions) and len(questions) > 0
            if slide_category != 'quiz' and not has_questions:
                return Response(
                    json.dumps({'error': 'Quiz not found'}),
                    status=404,
                    mimetype='application/json'
                )

            if not has_questions:
                return Response(
                    json.dumps({'error': 'No quiz questions found'}),
                    status=404,
                    mimetype='application/json'
                )

            questions_data = []
            for question in questions:
                # Get question text safely across versions
                question_text = getattr(question, 'question', None) or getattr(question, 'name', None) or getattr(question, 'text', None) or ''
                question_type = getattr(question, 'question_type', None) or getattr(question, 'type', None) or 'multiple_choice'

                # Get answers/options safely across versions
                answer_records = getattr(question, 'answer_ids', None)
                if not answer_records:
                    answer_records = getattr(question, 'option_ids', None)
                if not answer_records:
                    answer_records = getattr(question, 'suggested_answer_ids', None)
                answer_records = answer_records or []

                answers = []
                for answer in answer_records:
                    answer_text = (
                        getattr(answer, 'text', None)
                        or getattr(answer, 'text_value', None)
                        or getattr(answer, 'answer_content', None)
                        or getattr(answer, 'name', None)
                        or getattr(answer, 'answer', None)
                        or getattr(answer, 'value', None)
                        or ''
                    )
                    answers.append({
                        'id': answer.id,
                        'text': html.unescape(str(answer_text)) if answer_text else '',
                    })

                # Provide default options for true/false if missing
                if not answers and question_type == 'true_false':
                    answers = [
                        {'id': 1, 'text': 'True'},
                        {'id': 0, 'text': 'False'},
                    ]

                # Allow text input for short answers or missing options
                allow_text = question_type == 'short_answer' or not answers

                # Skip empty questions to avoid breaking the quiz UI
                if question_text:
                    questions_data.append({
                        'id': question.id,
                        'text': question_text,
                        'answers': answers,
                        'type': question_type,
                        'allow_text': allow_text,
                    })

            if not questions_data:
                return Response(
                    json.dumps({'error': 'No quiz questions found'}),
                    status=404,
                    mimetype='application/json'
                )

            return Response(
                json.dumps({
                    'slide_name': slide.name,
                    'questions': questions_data,
                }),
                mimetype='application/json'
            )

        except Exception as e:
            _logger.error('Error getting quiz questions: %s', str(e))
            return Response(
                json.dumps({'error': 'Failed to get quiz questions'}),
                status=500,
                mimetype='application/json'
            )


