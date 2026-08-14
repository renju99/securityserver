# -*- coding: utf-8 -*-
"""Resident Complaint and Issue Tracking System."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from ..common.image_optimizer import ImageOptimizer
from markupsafe import Markup
import logging
import uuid

_logger = logging.getLogger(__name__)


class ResidentComplaint(models.Model):
    """Complaints and issues raised by residents."""
    
    _name = 'resident.complaint'
    _description = 'Resident Complaint'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Reference',
        required=True,
        default=lambda self: _('New'),
        copy=False,
        readonly=True,
        tracking=True
    )
    
    # Complaints are regulatory-audit records. Keep them even if a resident
    # moves out or a site is archived - force the admin to archive/merge
    # the related record rather than silently destroy the complaint trail.
    resident_id = fields.Many2one(
        'tenant.resident',
        string='Resident',
        required=True,
        tracking=True,
        ondelete='restrict',
        index=True
    )
    
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        required=True,
        tracking=True,
        ondelete='restrict',
        related='resident_id.site_id',
        store=True,
        readonly=True
    )
    
    client_id = fields.Many2one(
        'res.partner',
        string='Client/Owner',
        related='site_id.client_id',
        store=True,
        readonly=True
    )
    
    subject = fields.Char(
        string='Subject',
        required=True,
        tracking=True
    )
    
    category = fields.Selection([
        ('security', 'Security Issue'),
        ('guard_behavior', 'Guard Behavior'),
        ('access_control', 'Access Control'),
        ('noise', 'Noise Complaint'),
        ('safety', 'Safety Concern'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other')
    ], string='Category', required=True, default='other', tracking=True)
    
    priority = fields.Selection([
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='normal', required=True, tracking=True)
    
    description = fields.Html(
        string='Description',
        required=True
    )
    
    # Location information
    location = fields.Char(
        string='Location',
        help='Specific location where the issue occurred'
    )
    
    building = fields.Char(
        string='Building',
        related='resident_id.building',
        store=True
    )
    
    unit_number = fields.Char(
        string='Unit',
        related='resident_id.unit_number',
        store=True
    )
    
    # Status and assignment
    status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('in_progress', 'In Progress'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    assigned_to_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        domain=[('groups_id', 'in', [])],  # Will be filtered in onchange
        tracking=True
    )
    
    # Timeline
    submitted_date = fields.Datetime(
        string='Submitted Date',
        readonly=True,
        tracking=True
    )
    
    reviewed_date = fields.Datetime(
        string='Reviewed Date',
        readonly=True,
        tracking=True
    )
    
    resolved_date = fields.Datetime(
        string='Resolved Date',
        readonly=True,
        tracking=True
    )
    
    closed_date = fields.Datetime(
        string='Closed Date',
        readonly=True,
        tracking=True
    )
    
    # Response
    management_response = fields.Html(
        string='Management Response',
        tracking=True
    )
    
    resolution_notes = fields.Html(
        string='Resolution Notes'
    )
    
    # Attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        help='Photos, documents, or other evidence'
    )
    
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True
    )
    
    @api.depends('attachment_ids')
    def _compute_photo_count(self):
        """Compute number of photo attachments."""
        for record in self:
            photo_attachments = record.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            )
            record.photo_count = len(photo_attachments)
    
    # Ratings
    satisfaction_rating = fields.Selection([
        ('1', '1 - Very Unsatisfied'),
        ('2', '2 - Unsatisfied'),
        ('3', '3 - Neutral'),
        ('4', '4 - Satisfied'),
        ('5', '5 - Very Satisfied')
    ], string='Resolution Satisfaction', help='How satisfied are you with the resolution?')
    
    # Portal access
    access_token = fields.Char(
        'Access Token',
        copy=False
    )
    
    @api.model
    def _get_default_access_token(self):
        """Generate access token."""
        return str(uuid.uuid4())
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence and handle submission."""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('resident.complaint') or _('New')
        
        records = super().create(vals_list)
        
        # Optimize attached photos
        for record in records:
            if record.attachment_ids:
                record._optimize_attachments()
        
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'attachment_ids' in vals:
            self._optimize_attachments()
        return result
    
    def _optimize_attachments(self):
        """Optimize photo attachments for storage and PDF rendering."""
        for record in self:
            photo_attachments = record.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            )
            for attachment in photo_attachments:
                try:
                    # Skip if already optimized (small enough)
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    # Optimize image
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for complaint %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )
    
    def action_submit(self):
        """Submit the complaint."""
        self.ensure_one()
        
        if not self.description:
            raise ValidationError(_('Please provide a description before submitting.'))
        
        self.write({
            'status': 'submitted',
            'submitted_date': fields.Datetime.now()
        })
        
        # Notify management
        self._notify_management()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Complaint Submitted'),
                'message': _('Your complaint has been submitted. Reference: %s') % self.name,
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_under_review(self):
        """Mark as under review."""
        self.ensure_one()
        self.write({
            'status': 'under_review',
            'reviewed_date': fields.Datetime.now()
        })
        
        # Notify resident
        self._notify_resident_status_change('under review')
    
    def action_in_progress(self):
        """Mark as in progress."""
        self.ensure_one()
        self.status = 'in_progress'
        
        self._notify_resident_status_change('in progress')
    
    def action_resolve(self):
        """Mark as resolved."""
        self.ensure_one()
        
        if not self.resolution_notes:
            raise ValidationError(_('Please provide resolution notes before marking as resolved.'))
        
        self.write({
            'status': 'resolved',
            'resolved_date': fields.Datetime.now()
        })
        
        self._notify_resident_status_change('resolved')
    
    def action_close(self):
        """Close the complaint."""
        self.ensure_one()
        self.write({
            'status': 'closed',
            'closed_date': fields.Datetime.now()
        })
    
    def action_reopen(self):
        """Reopen the complaint."""
        self.ensure_one()
        self.status = 'submitted'
    
    def _notify_management(self):
        """Notify management of new complaint."""
        self.ensure_one()
        
        try:
            manager_group = self.env.ref('guardpro.group_guardpro_manager')
            managers = self.env['res.users'].search([('groups_id', 'in', manager_group.id)])
            
            if managers:
                priority_label = dict(self._fields['priority'].selection).get(self.priority)
                category_label = dict(self._fields['category'].selection).get(self.category)
                
                message = Markup(
                    '<strong>New Resident Complaint</strong><br/>'
                    '<strong>Reference:</strong> %s<br/>'
                    '<strong>Resident:</strong> %s (%s)<br/>'
                    '<strong>Category:</strong> %s<br/>'
                    '<strong>Priority:</strong> %s<br/>'
                    '<strong>Subject:</strong> %s'
                ) % (
                    self.name,
                    self.resident_id.name,
                    self.resident_id.unit_number or 'N/A',
                    category_label,
                    priority_label,
                    self.subject
                )
                
                self.message_post(
                    body=message,
                    partner_ids=managers.mapped('partner_id').ids,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
                self.env['guardpro.mobile.outbox'].sudo().push(
                    user=managers,
                    kind='complaint_received',
                    title=_('New resident complaint: %s') % self.name,
                    body=_('Resident: %s\nCategory: %s\nPriority: %s\nSubject: %s') % (
                        self.resident_id.name if self.resident_id else '-',
                        dict(self._fields['category'].selection).get(self.category) or '-',
                        dict(self._fields['priority'].selection).get(self.priority) or '-',
                        self.subject or '-',
                    ),
                    priority='high' if self.priority in ('high', 'urgent') else 'normal',
                    res_model='resident.complaint',
                    res_id=self.id,
                    dedup_key='resident_complaint:%s' % self.id,
                )
        except Exception as e:
            _logger.warning('Could not send complaint notification: %s', str(e))

        # Also ping the assigned guard/supervisor if the complaint
        # already has an owner (on re-submit, this covers that case).
        if self.assigned_to_id:
            self.env['guardpro.mobile.outbox'].sudo().push(
                user=self.assigned_to_id,
                kind='complaint_received',
                title=_('Resident complaint assigned: %s') % self.name,
                body=self.subject or self.description or '-',
                priority='high',
                res_model='resident.complaint',
                res_id=self.id,
                dedup_key='resident_complaint_assigned:%s:%s' % (self.id, self.assigned_to_id.id),
            )
    
    def _notify_resident_status_change(self, new_status):
        """Notify resident of status change."""
        self.ensure_one()
        
        if self.resident_id and self.resident_id.partner_id:
            message = Markup(
                'Your complaint <strong>%s</strong> is now <strong>%s</strong>.'
            ) % (self.name, new_status)
            
            if self.management_response:
                message += Markup('<br/><br/><strong>Response:</strong><br/>%s') % Markup(self.management_response)
            
            try:
                self.message_post(
                    body=message,
                    partner_ids=self.resident_id.partner_id.ids,
                    message_type='notification',
                    subtype_xmlid='mail.mt_comment'
                )
            except Exception as e:
                _logger.warning('Could not send status change notification to resident: %s', str(e))
    
    def _compute_access_url(self):
        """Compute portal access URL."""
        super()._compute_access_url()
        for record in self:
            record.access_url = '/my/complaint/%s' % record.id


class TenantResident(models.Model):
    """Extend tenant resident with complaint tracking."""
    
    _inherit = 'tenant.resident'
    
    complaint_count = fields.Integer(
        string='Complaints',
        compute='_compute_complaint_count'
    )
    
    def _compute_complaint_count(self):
        """Compute number of complaints."""
        for record in self:
            record.complaint_count = self.env['resident.complaint'].search_count([
                ('resident_id', '=', record.id)
            ])
    
    def action_view_complaints(self):
        """View complaints for this resident."""
        self.ensure_one()
        return {
            'name': _('Complaints: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'resident.complaint',
            'view_mode': 'list,form',
            'domain': [('resident_id', '=', self.id)],
            'context': {'default_resident_id': self.id}
        }

