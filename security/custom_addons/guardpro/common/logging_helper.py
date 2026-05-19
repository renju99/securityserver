# -*- coding: utf-8 -*-
"""
GuardLink Enhanced Logging Helper
Provides categorized logging for better debugging and audit trail
"""

import logging

# Create category-based loggers
_audit_logger = logging.getLogger('guardpro.audit')
_security_logger = logging.getLogger('guardpro.security')
_performance_logger = logging.getLogger('guardpro.performance')
_integration_logger = logging.getLogger('guardpro.integration')
_business_logger = logging.getLogger('guardpro.business')


class GuardLinkLogger:
    """Enhanced logger with category support."""
    
    @staticmethod
    def audit_info(message, *args, **kwargs):
        """Log audit-related information."""
        _audit_logger.info(message, *args, **kwargs)
    
    @staticmethod
    def audit_warning(message, *args, **kwargs):
        """Log audit warnings."""
        _audit_logger.warning(message, *args, **kwargs)
    
    @staticmethod
    def audit_error(message, *args, **kwargs):
        """Log audit errors."""
        _audit_logger.error(message, *args, **kwargs)
    
    @staticmethod
    def security_info(message, *args, **kwargs):
        """Log security-related information."""
        _security_logger.info(message, *args, **kwargs)
    
    @staticmethod
    def security_warning(message, *args, **kwargs):
        """Log security warnings (potential threats)."""
        _security_logger.warning(message, *args, **kwargs)
    
    @staticmethod
    def security_critical(message, *args, **kwargs):
        """Log critical security events."""
        _security_logger.critical(message, *args, **kwargs)
    
    @staticmethod
    def performance_debug(message, *args, **kwargs):
        """Log performance metrics."""
        _performance_logger.debug(message, *args, **kwargs)
    
    @staticmethod
    def performance_info(message, *args, **kwargs):
        """Log performance information."""
        _performance_logger.info(message, *args, **kwargs)
    
    @staticmethod
    def integration_info(message, *args, **kwargs):
        """Log integration events (API, webhooks, etc.)."""
        _integration_logger.info(message, *args, **kwargs)
    
    @staticmethod
    def integration_error(message, *args, **kwargs):
        """Log integration errors."""
        _integration_logger.error(message, *args, **kwargs)
    
    @staticmethod
    def business_info(message, *args, **kwargs):
        """Log business logic events."""
        _business_logger.info(message, *args, **kwargs)
    
    @staticmethod
    def business_warning(message, *args, **kwargs):
        """Log business logic warnings."""
        _business_logger.warning(message, *args, **kwargs)


# Convenience instance
logger = GuardLinkLogger()

