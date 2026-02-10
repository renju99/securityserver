# -*- coding: utf-8 -*-
"""Rate Limiter for API Endpoints - Security Enhancement."""

from odoo import http
from odoo.http import request
from functools import wraps
import time
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple in-memory rate limiter for API endpoints.
    Prevents abuse and DOS attacks on critical endpoints.
    """
    
    # Class-level storage for request tracking
    _requests = defaultdict(list)
    _locked_users = {}
    _violation_count = defaultdict(int)
    
    @classmethod
    def check_rate_limit(cls, user_id, endpoint, max_requests=10, window_seconds=60):
        """
        Check if user exceeded rate limit.
        
        Args:
            user_id (int): User ID making the request
            endpoint (str): API endpoint name
            max_requests (int): Maximum requests allowed in window
            window_seconds (int): Time window in seconds
            
        Returns:
            tuple: (allowed: bool, retry_after: int, message: str)
        """
        key = f"{user_id}:{endpoint}"
        now = time.time()
        
        # Check if user is locked out
        if key in cls._locked_users:
            locked_until = cls._locked_users[key]
            if now < locked_until:
                retry_after = int(locked_until - now)
                _logger.warning(
                    'Rate limit lockout: User %s on endpoint %s (retry in %d seconds)',
                    user_id, endpoint, retry_after
                )
                return False, retry_after, f'Rate limit exceeded. Locked out for {retry_after} seconds.'
            else:
                # Unlock user
                del cls._locked_users[key]
                cls._violation_count[key] = 0
                _logger.info('Rate limit lockout expired for user %s on %s', user_id, endpoint)
        
        # Clean old requests outside the time window
        cls._requests[key] = [
            req_time for req_time in cls._requests[key]
            if now - req_time < window_seconds
        ]
        
        # Check if limit exceeded
        current_count = len(cls._requests[key])
        
        if current_count >= max_requests:
            # Track violations
            cls._violation_count[key] += 1
            violations = cls._violation_count[key]
            
            # Progressive lockout based on violation count
            if violations == 1:
                lockout_duration = 60  # 1 minute for first violation
            elif violations == 2:
                lockout_duration = 300  # 5 minutes for second violation
            elif violations >= 3:
                lockout_duration = 900  # 15 minutes for repeated violations
            else:
                lockout_duration = 60
            
            # Lock user
            cls._locked_users[key] = now + lockout_duration
            
            _logger.warning(
                'RATE LIMIT EXCEEDED: User %s on endpoint %s (violation #%d, locked for %d seconds)',
                user_id, endpoint, violations, lockout_duration
            )
            
            return False, lockout_duration, f'Rate limit exceeded. Too many requests. Locked out for {lockout_duration} seconds.'
        
        # Add current request
        cls._requests[key].append(now)
        
        # Log if approaching limit
        if current_count >= max_requests * 0.8:  # 80% of limit
            _logger.info(
                'Rate limit warning: User %s on %s at %d/%d requests',
                user_id, endpoint, current_count + 1, max_requests
            )
        
        return True, 0, 'OK'
    
    @classmethod
    def reset_user_limit(cls, user_id, endpoint=None):
        """
        Reset rate limit for a user (admin override).
        
        Args:
            user_id (int): User ID
            endpoint (str, optional): Specific endpoint, or None for all
        """
        if endpoint:
            key = f"{user_id}:{endpoint}"
            if key in cls._requests:
                del cls._requests[key]
            if key in cls._locked_users:
                del cls._locked_users[key]
            if key in cls._violation_count:
                del cls._violation_count[key]
            _logger.info('Rate limit reset for user %s on %s', user_id, endpoint)
        else:
            # Reset all endpoints for this user
            keys_to_delete = [k for k in cls._requests.keys() if k.startswith(f"{user_id}:")]
            for key in keys_to_delete:
                if key in cls._requests:
                    del cls._requests[key]
                if key in cls._locked_users:
                    del cls._locked_users[key]
                if key in cls._violation_count:
                    del cls._violation_count[key]
            _logger.info('Rate limit reset for user %s on all endpoints', user_id)
    
    @classmethod
    def get_stats(cls):
        """Get rate limiter statistics for monitoring."""
        return {
            'active_trackers': len(cls._requests),
            'locked_users': len(cls._locked_users),
            'total_violations': sum(cls._violation_count.values())
        }


def rate_limit(max_requests=10, window_seconds=60, error_code='RATE_LIMIT_EXCEEDED'):
    """
    Decorator for rate limiting API endpoints.
    
    Usage:
        @rate_limit(max_requests=5, window_seconds=60)
        @http.route('/api/endpoint', type='json', auth='user')
        def my_api_endpoint(self):
            return {'success': True}
    
    Args:
        max_requests (int): Maximum requests allowed in time window
        window_seconds (int): Time window in seconds
        error_code (str): Error code to return when limit exceeded
        
    Returns:
        Decorated function with rate limiting
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            # Skip rate limiting for admin users (optional)
            if request.env.user.has_group('base.group_system'):
                return func(self, *args, **kwargs)
            
            user_id = request.env.user.id
            endpoint = func.__name__
            
            # Check rate limit
            allowed, retry_after, message = RateLimiter.check_rate_limit(
                user_id, endpoint, max_requests, window_seconds
            )
            
            if not allowed:
                # Return rate limit error
                return {
                    'success': False,
                    'error': message,
                    'error_code': error_code,
                    'retry_after': retry_after,
                    'max_requests': max_requests,
                    'window_seconds': window_seconds
                }
            
            # Proceed with normal request
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# Cleanup function for cron job
def cleanup_old_rate_limit_data():
    """
    Clean up old rate limit data.
    Should be called periodically via cron job.
    """
    now = time.time()
    
    # Clean up unlocked users from more than 1 hour ago
    keys_to_delete = []
    for key, locked_until in RateLimiter._locked_users.items():
        if now > locked_until + 3600:  # 1 hour after unlock
            keys_to_delete.append(key)
    
    for key in keys_to_delete:
        if key in RateLimiter._locked_users:
            del RateLimiter._locked_users[key]
        if key in RateLimiter._violation_count:
            del RateLimiter._violation_count[key]
    
    # Clean up request histories older than 1 hour
    for key in list(RateLimiter._requests.keys()):
        RateLimiter._requests[key] = [
            req_time for req_time in RateLimiter._requests[key]
            if now - req_time < 3600
        ]
        # Remove empty entries
        if not RateLimiter._requests[key]:
            del RateLimiter._requests[key]
    
    _logger.info('Rate limiter cleanup completed. Active trackers: %d', len(RateLimiter._requests))

