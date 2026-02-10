# -*- coding: utf-8 -*-
"""Website Model Fix for REQUEST_URI KeyError.

This module fixes a bug in Odoo 18 where the website module's _is_canonical_url
method tries to access request.httprequest.environ['REQUEST_URI'] which may not
exist in certain request contexts (e.g., longpolling requests).
"""

from odoo import models
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)


class Website(models.Model):
    """Extend website model to fix REQUEST_URI KeyError."""

    _inherit = 'website'

    def _is_canonical_url(self):
        """Override to handle missing REQUEST_URI in request environment.
        
        The original method assumes REQUEST_URI is always present in the
        request environment, but this is not true for all request types
        (e.g., longpolling requests).
        
        Returns:
            bool: True if the current request URL is canonical, False otherwise
        """
        self.ensure_one()
        try:
            # Try to get REQUEST_URI from environment
            if request and hasattr(request, 'httprequest') and request.httprequest:
                environ = getattr(request.httprequest, 'environ', {})
                request_uri = environ.get('REQUEST_URI')
                
                if request_uri:
                    # Original logic: construct current URL
                    current_url = request.httprequest.url_root[:-1] + request_uri
                else:
                    # Fallback: use path_info if available
                    path_info = environ.get('PATH_INFO', '')
                    if path_info:
                        current_url = request.httprequest.url_root[:-1] + path_info
                        # Also check query string if present
                        query_string = environ.get('QUERY_STRING', '')
                        if query_string:
                            current_url += '?' + query_string
                    else:
                        # Last resort: use request URL if available
                        if hasattr(request.httprequest, 'url'):
                            current_url = request.httprequest.url
                        else:
                            # If we can't determine, assume it's canonical to avoid errors
                            _logger.debug(
                                "Could not determine current URL - REQUEST_URI, "
                                "PATH_INFO, and request.url not available. "
                                "Assuming canonical."
                            )
                            return True
                
                # Compare with canonical URL (original logic)
                # Check if request.lang is available
                if hasattr(request, 'lang') and request.lang:
                    lang_code = request.lang.code
                else:
                    # Fallback to default language
                    lang_code = self.env['res.lang']._get_data(
                        id=self._get_cached('default_lang_id')
                    ).code
                
                canonical_url = self.env['ir.http']._url_localized(
                    lang_code=lang_code,
                    canonical_domain=self.get_base_url()
                )
                return current_url == canonical_url
            else:
                # No request object available, assume canonical
                _logger.debug(
                    "No request object available for canonical URL check. "
                    "Assuming canonical."
                )
                return True
        except (KeyError, AttributeError, TypeError) as e:
            # Catch any errors and log them, then return True to avoid breaking
            # the page rendering
            _logger.warning(
                "Error checking canonical URL: %s. Assuming canonical to "
                "prevent page rendering errors.",
                str(e)
            )
            return True








