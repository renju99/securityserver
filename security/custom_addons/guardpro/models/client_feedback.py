# -*- coding: utf-8 -*-
"""Client Feedback & Rating System."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class ClientFeedback(models.Model):
    """Client feedback and ratings for guards and shifts."""
    
    _name = 'client.feedback'
    _description = 'Client Feedback'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Reference',
        required=True,
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
        tracking=True
    )
    
    client_id = fields.Many2one(
        'res.partner',
        string='Client',
        domain=[('is_company', '=', True)],
        tracking=True
    )
    
    # Feedback is an audit record. Required FKs use RESTRICT so the target
    # cannot be silently deleted while feedback is attached; optional FKs
    # use SET NULL so the feedback body survives archival of peripheral
    # records (guards rotate, shifts close, residents move out).
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        ondelete='restrict'
    )
    
    # Resident/Tenant Support
    resident_id = fields.Many2one(
        'tenant.resident',
        string='Resident/Tenant',
        tracking=True,
        ondelete='set null',
        help='Resident who submitted this feedback (for community projects)'
    )
    
    feedback_source = fields.Selection([
        ('client', 'Client/Management'),
        ('resident', 'Resident/Tenant')
    ], string='Feedback Source', compute='_compute_feedback_source', store=True)
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=False,
        tracking=True,
        ondelete='set null',
        help='Optional: Leave blank for general service feedback'
    )
    
    shift_id = fields.Many2one(
        'guard.shift',
        string='Related Shift',
        tracking=True,
        ondelete='set null'
    )
    
    feedback_date = fields.Date(
        string='Feedback Date',
        default=fields.Date.today,
        required=True,
        tracking=True
    )
    
    feedback_type = fields.Selection([
        ('positive', 'Positive/Compliment'),
        ('negative', 'Negative/Concern'),
        ('neutral', 'Neutral/General'),
        ('suggestion', 'Suggestion'),
        ('service_quality', 'Service Quality')
    ], string='Type', required=True, default='neutral', tracking=True)
    
    # Ratings
    overall_rating = fields.Selection([
        ('1', '1 - Poor'),
        ('2', '2 - Below Average'),
        ('3', '3 - Average'),
        ('4', '4 - Good'),
        ('5', '5 - Excellent')
    ], string='Overall Rating', required=True, tracking=True)
    
    professionalism_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Professionalism')
    
    punctuality_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Punctuality')
    
    communication_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Communication')
    
    appearance_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Appearance')
    
    responsiveness_rating = fields.Selection([
        ('1', '1'), ('2', '2'), ('3', '3'), ('4', '4'), ('5', '5')
    ], string='Responsiveness')
    
    # Feedback content
    comments = fields.Text(
        string='Comments',
        required=True,
        tracking=True
    )
    
    suggestions = fields.Text(
        string='Suggestions',
        help='Suggestions for improvement'
    )
    
    # Management Tracking
    action_taken = fields.Text(
        string='Action Taken',
        groups='guardpro.group_guardpro_manager',
        help='Internal notes on actions taken following this feedback'
    )
    
    follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False,
        groups='guardpro.group_guardpro_manager'
    )
    
    follow_up_notes = fields.Text(
        string='Follow-up Notes',
        groups='guardpro.group_guardpro_manager'
    )
    
    # Preferences
    request_same_guard = fields.Boolean(
        string='Request Same Guard',
        help='Client would like this guard assigned again'
    )
    
    request_different_guard = fields.Boolean(
        string='Request Different Guard',
        help='Client prefers a different guard in future'
    )
    
    # Response
    management_response = fields.Text(
        string='Management Response',
        groups='guardpro.group_guardpro_manager'
    )
    
    response_date = fields.Date(
        string='Response Date',
        groups='guardpro.group_guardpro_manager'
    )
    
    responded_by_id = fields.Many2one(
        'res.users',
        string='Responded By',
        groups='guardpro.group_guardpro_manager'
    )
    
    # Status
    status = fields.Selection([
        ('new', 'New'),
        ('reviewed', 'Reviewed'),
        ('responded', 'Responded'),
        ('closed', 'Closed')
    ], string='Status', default='new', required=True, tracking=True)
    
    # Visibility
    shared_with_guard = fields.Boolean(
        string='Shared with Guard',
        default=False,
        help='Whether this feedback has been shared with the guard'
    )
    
    # Public visibility for portal users
    visible_to_residents = fields.Boolean(
        string='Visible to Residents',
        default=False,
        help='Make this feedback visible to other residents (anonymized)'
    )
    
    @api.depends('resident_id', 'client_id')
    def _compute_feedback_source(self):
        """Compute feedback source."""
        for record in self:
            if record.resident_id:
                record.feedback_source = 'resident'
            else:
                record.feedback_source = 'client'
    
    @api.onchange('resident_id')
    def _onchange_resident_id(self):
        """Auto-fill site and client from resident."""
        if self.resident_id:
            self.site_id = self.resident_id.site_id
            self.client_id = self.resident_id.client_id

    @api.constrains('guard_id', 'site_id')
    def _check_guard_belongs_to_site(self):
        """Reject feedback naming a guard who is not assigned to the site."""
        for record in self:
            if not record.guard_id or not record.site_id:
                continue
            if record.site_id.id not in record.guard_id.site_ids.ids:
                raise ValidationError(_(
                    'Guard "%(guard)s" is not assigned to site "%(site)s".'
                ) % {
                    'guard': record.guard_id.display_name,
                    'site': record.site_id.display_name,
                })
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence on create."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('client.feedback') or _('New')
        
        records = super().create(vals_list)
        
        # Notify management of new feedback
        for record in records:
            if record.feedback_type == 'complaint':
                record._notify_management_complaint()
        
        return records
    
    def _notify_management_complaint(self):
        """Notify management AND the subject guard (so they can respond)
        of a new complaint."""
        self.ensure_one()

        title = _('New client complaint')
        body = _('From: %s\nGuard: %s\nSite: %s') % (
            self.client_id.name if self.client_id else '-',
            self.guard_id.name if self.guard_id else '-',
            self.site_id.name if self.site_id else '-',
        )
        if self.comments:
            body += '\n\n' + self.comments[:1000]

        try:
            manager_group = self.env.ref('guardpro.group_guardpro_manager')
            managers = self.env['res.users'].search([('groups_id', 'in', manager_group.id)])

            if managers:
                self.message_post(
                    body=_('New complaint received from %s about guard %s at %s') % (
                        self.client_id.name,
                        self.guard_id.name,
                        self.site_id.name
                    ),
                    partner_ids=managers.mapped('partner_id').ids,
                    message_type='notification'
                )
                self.env['guardpro.mobile.outbox'].sudo().push(
                    user=managers,
                    kind='complaint_received',
                    title=title,
                    body=body,
                    priority='high',
                    res_model='client.feedback',
                    res_id=self.id,
                    dedup_key='complaint_mgr:%s' % self.id,
                )
        except Exception as e:
            _logger.warning('Could not send complaint notification: %s', str(e))

        # Ping the subject guard directly so they know.
        if self.guard_id and self.guard_id.user_id:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=self.guard_id.user_id,
                kind='complaint_received',
                title=_('Client complaint recorded'),
                body=body,
                priority='high',
                res_model='client.feedback',
                res_id=self.id,
                dedup_key='complaint_guard:%s' % self.id,
            )
    
    def action_respond(self):
        """Mark as responded."""
        self.ensure_one()
        
        if not self.management_response:
            raise ValidationError(_('Please provide a response before marking as responded.'))
        
        self.write({
            'status': 'responded',
            'response_date': fields.Date.today(),
            'responded_by_id': self.env.user.id
        })
        
        # Notify client
        if self.client_id:
            try:
                self.message_post(
                    body=_('Thank you for your feedback. We have reviewed and responded to your comments.'),
                    partner_ids=self.client_id.ids,
                    message_type='notification'
                )
            except Exception as e:
                _logger.warning('Could not send response notification to client: %s', str(e))
    
    def action_share_with_guard(self):
        """Share positive feedback with guard."""
        self.ensure_one()
        
        if int(self.overall_rating) < 4:
            raise ValidationError(_('Only positive feedback (rating 4-5) should be shared with guards.'))
        
        if self.guard_id and self.guard_id.user_id:
            try:
                self.message_post(
                    body=Markup('You have received positive feedback from %s:<br/>%s') % (
                        Markup.escape(self.client_id.name or ''),
                        Markup.escape(self.comments or '')
                    ),
                    partner_ids=self.guard_id.user_id.partner_id.ids,
                    message_type='notification'
                )
                self.env['guardpro.mobile.outbox'].sudo().push(
                    user=self.guard_id.user_id,
                    kind='feedback_received',
                    title=_('Positive feedback from %s') % (
                        self.client_id.name if self.client_id else 'a client'
                    ),
                    body=self.comments or _('(no comment)'),
                    priority='normal',
                    res_model='client.feedback',
                    res_id=self.id,
                    dedup_key='feedback_share:%s' % self.id,
                )
                self.shared_with_guard = True
            except Exception as e:
                _logger.warning('Could not send feedback notification to guard: %s', str(e))
                # Still mark as shared in the UI if we tried to share it
                self.shared_with_guard = True
    
    def action_close(self):
        """Close feedback."""
        self.status = 'closed'


class GuardProfile(models.Model):
    """Extend guard profile with feedback stats."""
    
    _inherit = 'guard.profile'
    
    feedback_count = fields.Integer(
        string='Feedback Count',
        compute='_compute_feedback_stats'
    )
    
    average_rating = fields.Float(
        string='Average Rating',
        compute='_compute_feedback_stats',
        digits=(3, 2)
    )
    
    compliment_count = fields.Integer(
        string='Compliments',
        compute='_compute_feedback_stats'
    )
    
    complaint_count = fields.Integer(
        string='Complaints',
        compute='_compute_feedback_stats'
    )
    
    def _compute_feedback_stats(self):
        """Compute feedback statistics."""
        for record in self:
            feedbacks = self.env['client.feedback'].search([
                ('guard_id', '=', record.id)
            ])
            
            record.feedback_count = len(feedbacks)
            record.compliment_count = len(feedbacks.filtered(lambda f: f.feedback_type == 'compliment'))
            record.complaint_count = len(feedbacks.filtered(lambda f: f.feedback_type == 'complaint'))
            
            if feedbacks:
                total_rating = sum(int(f.overall_rating) for f in feedbacks)
                record.average_rating = total_rating / len(feedbacks)
            else:
                record.average_rating = 0.0
    
    def action_view_feedback(self):
        """View feedback for this guard."""
        self.ensure_one()
        return {
            'name': _('Feedback: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'client.feedback',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.id)],
            'context': {'default_guard_id': self.id}
        }

