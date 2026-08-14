# -*- coding: utf-8 -*-
"""Resident Portal Controllers."""

from odoo import http, _
from odoo.http import request
from odoo.addons.portal.controllers.portal import CustomerPortal, pager as portal_pager
from odoo.exceptions import AccessError, MissingError
from odoo.tools import groupby as groupbyelem
from operator import itemgetter


class ResidentPortal(CustomerPortal):
    """Portal controller for resident-specific features."""
    
    def _prepare_home_portal_values(self, counters):
        """Add resident-specific counters to portal home."""
        values = super()._prepare_home_portal_values(counters)
        
        user = request.env.user
        resident = request.env['tenant.resident'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if resident:
            if 'complaint_count' in counters:
                values['complaint_count'] = request.env['resident.complaint'].search_count([
                    ('resident_id', '=', resident.id)
                ])
            
            if 'feedback_count' in counters:
                values['feedback_count'] = request.env['client.feedback'].search_count([
                    ('resident_id', '=', resident.id)
                ])
        
        return values
    
    # ========================================================================
    # RESIDENT COMPLAINTS
    # ========================================================================
    
    @http.route(['/my/complaints', '/my/complaints/page/<int:page>'], type='http', auth="user", website=True)
    def portal_my_complaints(self, page=1, date_begin=None, date_end=None, sortby=None, filterby=None, **kw):
        """List resident's complaints."""
        user = request.env.user
        resident = request.env['tenant.resident'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not resident:
            return request.render('website.403')
        
        Complaint = request.env['resident.complaint']
        
        domain = [('resident_id', '=', resident.id)]
        
        # Sorting
        searchbar_sortings = {
            'date': {'label': _('Newest'), 'order': 'create_date desc'},
            'name': {'label': _('Reference'), 'order': 'name'},
            'status': {'label': _('Status'), 'order': 'status'},
        }
        if not sortby:
            sortby = 'date'
        order = searchbar_sortings[sortby]['order']
        
        # Filtering
        searchbar_filters = {
            'all': {'label': _('All'), 'domain': []},
            'draft': {'label': _('Draft'), 'domain': [('status', '=', 'draft')]},
            'active': {'label': _('Active'), 'domain': [('status', 'in', ['submitted', 'under_review', 'in_progress'])]},
            'resolved': {'label': _('Resolved'), 'domain': [('status', '=', 'resolved')]},
            'closed': {'label': _('Closed'), 'domain': [('status', '=', 'closed')]},
        }
        if not filterby:
            filterby = 'all'
        domain += searchbar_filters[filterby]['domain']
        
        # Count
        complaint_count = Complaint.search_count(domain)
        
        # Pager
        pager = portal_pager(
            url="/my/complaints",
            url_args={'date_begin': date_begin, 'date_end': date_end, 'sortby': sortby, 'filterby': filterby},
            total=complaint_count,
            page=page,
            step=self._items_per_page
        )
        
        # Get complaints
        complaints = Complaint.search(domain, order=order, limit=self._items_per_page, offset=pager['offset'])
        request.session['my_complaints_history'] = complaints.ids[:100]
        
        values = {
            'complaints': complaints,
            'page_name': 'complaint',
            'pager': pager,
            'default_url': '/my/complaints',
            'searchbar_sortings': searchbar_sortings,
            'sortby': sortby,
            'searchbar_filters': searchbar_filters,
            'filterby': filterby,
            'resident': resident,
        }
        
        return request.render("guardpro.portal_my_complaints", values)
    
    @http.route(['/my/complaint/<int:complaint_id>'], type='http', auth="user", website=True)
    def portal_complaint_detail(self, complaint_id=None, access_token=None, **kw):
        """View complaint details."""
        try:
            complaint_sudo = self._document_check_access('resident.complaint', complaint_id, access_token)
        except (AccessError, MissingError):
            return request.redirect('/my')
        
        values = self._complaint_get_page_view_values(complaint_sudo, access_token, **kw)
        return request.render("guardpro.portal_complaint_detail", values)
    
    def _complaint_get_page_view_values(self, complaint, access_token, **kwargs):
        """Get values for complaint detail page."""
        values = {
            'page_name': 'complaint',
            'complaint': complaint,
        }
        return self._get_page_view_values(complaint, access_token, values, 'my_complaints_history', False, **kwargs)
    
    @http.route(['/my/complaint/new'], type='http', auth="user", website=True)
    def portal_create_complaint(self, **post):
        """Create a new complaint."""
        user = request.env.user
        resident = request.env['tenant.resident'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not resident:
            return request.render('website.403')
        
        if request.httprequest.method == 'POST':
            # Create the complaint
            values = {
                'resident_id': resident.id,
                'subject': post.get('subject'),
                'category': post.get('category'),
                'priority': post.get('priority', 'normal'),
                'description': post.get('description'),
                'location': post.get('location'),
            }
            
            complaint = request.env['resident.complaint'].sudo().create(values)
            
            # Auto-submit if requested
            if post.get('submit_now'):
                complaint.action_submit()
            
            return request.redirect('/my/complaint/%s?message=created' % complaint.id)
        
        # Show form
        values = {
            'resident': resident,
            'page_name': 'new_complaint',
        }
        return request.render("guardpro.portal_create_complaint", values)
    
    @http.route(['/my/complaint/<int:complaint_id>/update'], type='http', auth="user", website=True, methods=['POST'])
    def portal_update_complaint(self, complaint_id, **post):
        """Update complaint (add comments, rate satisfaction)."""
        try:
            complaint = request.env['resident.complaint'].browse(complaint_id)
            complaint.check_access_rights('write')
            complaint.check_access_rule('write')
            
            # Add comment if provided
            if post.get('comment'):
                complaint.message_post(
                    body=post.get('comment'),
                    message_type='comment',
                    subtype_xmlid='mail.mt_comment'
                )
            
            # Update satisfaction rating if resolved
            if complaint.status in ['resolved', 'closed'] and post.get('satisfaction_rating'):
                complaint.satisfaction_rating = post.get('satisfaction_rating')
            
            return request.redirect('/my/complaint/%s?message=updated' % complaint_id)
            
        except (AccessError, MissingError):
            return request.redirect('/my')
    
    # ========================================================================
    # RESIDENT FEEDBACK (for guards)
    # ========================================================================
    
    @http.route(['/my/resident/feedback'], type='http', auth="user", website=True)
    def portal_resident_feedback_list(self, **kw):
        """List resident's feedback submissions."""
        user = request.env.user
        resident = request.env['tenant.resident'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not resident:
            return request.render('website.403')
        
        feedbacks = request.env['client.feedback'].search([
            ('resident_id', '=', resident.id)
        ], order='create_date desc')
        
        values = {
            'feedbacks': feedbacks,
            'resident': resident,
            'page_name': 'feedback',
        }
        return request.render("guardpro.portal_resident_feedback_list", values)
    
    @http.route(['/my/resident/feedback/new'], type='http', auth="user", website=True)
    def portal_create_feedback(self, **post):
        """Create general feedback about security services."""
        user = request.env.user
        resident = request.env['tenant.resident'].sudo().search([
            ('user_id', '=', user.id)
        ], limit=1)
        
        if not resident:
            return request.render('website.403')
        
        if request.httprequest.method == 'POST':
            values = {
                'resident_id': resident.id,
                'site_id': resident.site_id.id,
                'client_id': resident.client_id.id,
                'feedback_type': post.get('feedback_type'),
                'overall_rating': post.get('overall_rating'),
                'comments': post.get('comments'),
            }

            # Guard is optional; if provided must cover the resident's site.
            guard_id_raw = post.get('guard_id')
            if guard_id_raw:
                try:
                    guard_id = int(guard_id_raw)
                except (TypeError, ValueError):
                    return request.redirect('/my/resident/feedback/new?error=invalid_guard')
                guard = request.env['guard.profile'].sudo().browse(guard_id)
                site_id = resident.site_id.id if resident.site_id else False
                if (
                    not guard.exists()
                    or not site_id
                    or site_id not in guard.site_ids.ids
                ):
                    return request.redirect('/my/resident/feedback/new?error=invalid_guard')
                values['guard_id'] = guard_id

            # Optional detailed ratings (only relevant if guard specified)
            if post.get('professionalism_rating'):
                values['professionalism_rating'] = post.get('professionalism_rating')
            if post.get('punctuality_rating'):
                values['punctuality_rating'] = post.get('punctuality_rating')
            if post.get('communication_rating'):
                values['communication_rating'] = post.get('communication_rating')
            if post.get('appearance_rating'):
                values['appearance_rating'] = post.get('appearance_rating')

            feedback = request.env['client.feedback'].sudo().create(values)
            return request.redirect('/my/resident/feedback?message=created')

        # Get guards from resident's site (optional)
        guards = request.env['guard.profile'].sudo().search([
            ('site_ids', 'in', [resident.site_id.id]),
        ]) if resident.site_id else request.env['guard.profile'].browse()

        values = {
            'resident': resident,
            'guards': guards,
            'page_name': 'new_feedback',
            'error': request.params.get('error'),
        }
        return request.render("guardpro.portal_create_feedback", values)

