# -*- coding: utf-8 -*-
"""Incident Status Update Model for Real-Time Client Portal Updates."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from markupsafe import Markup
import logging

_logger = logging.getLogger(__name__)


class IncidentStatusUpdate(models.Model):
    """Real-time status updates for incidents - visible in client portal."""
    
    _name = 'incident.status.update'
    _description = 'Incident Status Update'
    _order = 'update_datetime desc'
    _rec_name = 'title'
    
    incident_id = fields.Many2one(
        'incident.report',
        string='Incident',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    title = fields.Char(
        string='Update Title',
        required=True,
        help='Brief title for this update'
    )
    
    description = fields.Text(
        string='Update Description',
        required=True,
        help='Detailed description of the status update'
    )
    
    update_datetime = fields.Datetime(
        string='Update Time',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    
    update_type = fields.Selection([
        ('status_change', 'Status Change'),
        ('progress', 'Progress Update'),
        ('escalation', 'Escalation'),
        ('resolution', 'Resolution'),
        ('information', 'Additional Information')
    ], string='Update Type', required=True, default='progress')
    
    old_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='Previous Status')
    
    new_status = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_review', 'Under Review'),
        ('investigating', 'Investigating'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed')
    ], string='New Status')
    
    updated_by_id = fields.Many2one(
        'res.users',
        string='Updated By',
        default=lambda self: self.env.user,
        required=True
    )
    
    # Visibility
    visible_to_client = fields.Boolean(
        string='Visible to Client',
        default=True,
        help='Make this update visible in the client portal'
    )
    
    visible_to_residents = fields.Boolean(
        string='Visible to Residents',
        default=False,
        help='Make this update visible to residents (for community projects)'
    )
    
    # Notification
    notify_client = fields.Boolean(
        string='Notify Client',
        default=False,
        help='Send notification email to client'
    )
    
    notification_sent = fields.Boolean(
        string='Notification Sent',
        default=False,
        readonly=True
    )
    
    # Related fields for easy access
    site_id = fields.Many2one(
        'client.site',
        related='incident_id.site_id',
        store=True,
        readonly=True
    )
    
    client_id = fields.Many2one(
        'res.partner',
        related='site_id.client_id',
        store=True,
        readonly=True
    )
    
    severity = fields.Selection(
        related='incident_id.severity',
        readonly=True
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create update and send notifications."""
        records = super().create(vals_list)
        
        for record in records:
            if record.notify_client and record.visible_to_client:
                record._send_client_notification()
        
        return records
    
    def _send_client_notification(self):
        """Send notification to client."""
        self.ensure_one()
        
        try:
            # Post message to incident
            self.incident_id.message_post(
                body=Markup('<b>Status Update:</b> %s<br/><br/>%s') % (
                    Markup.escape(self.title),
                    Markup.escape(self.description)
                ),
                subject=_('Incident Update: %s') % self.incident_id.name,
                message_type='notification',
                partner_ids=self.client_id.ids if self.client_id else []
            )
            
            self.notification_sent = True
            
            _logger.info(
                'Sent incident update notification for incident %s to client %s',
                self.incident_id.name,
                self.client_id.name if self.client_id else 'N/A'
            )
        except Exception as e:
            _logger.error('Failed to send incident update notification: %s', str(e))


class IncidentReport(models.Model):
    """Extend incident report with status updates."""
    
    _inherit = 'incident.report'
    
    status_update_ids = fields.One2many(
        'incident.status.update',
        'incident_id',
        string='Status Updates'
    )
    
    status_update_count = fields.Integer(
        string='Update Count',
        compute='_compute_status_update_count'
    )
    
    last_update_datetime = fields.Datetime(
        string='Last Update',
        compute='_compute_last_update'
    )
    
    last_update_description = fields.Text(
        string='Latest Update',
        compute='_compute_last_update'
    )
    
    # Portal visibility
    visible_to_client = fields.Boolean(
        string='Visible to Client Portal',
        default=True,
        tracking=True,
        help='Make this incident visible in the client portal'
    )
    
    @api.depends('status_update_ids')
    def _compute_status_update_count(self):
        """Compute update count."""
        for record in self:
            record.status_update_count = len(record.status_update_ids)
    
    @api.depends('status_update_ids', 'status_update_ids.update_datetime')
    def _compute_last_update(self):
        """Compute last update info."""
        for record in self:
            latest = record.status_update_ids.sorted('update_datetime', reverse=True)[:1]
            if latest:
                record.last_update_datetime = latest.update_datetime
                record.last_update_description = latest.description
            else:
                record.last_update_datetime = False
                record.last_update_description = False
    
    def action_add_status_update(self):
        """Open wizard to add status update."""
        self.ensure_one()
        
        return {
            'name': _('Add Status Update'),
            'type': 'ir.actions.act_window',
            'res_model': 'incident.status.update',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_incident_id': self.id,
                'default_old_status': self.status,
            }
        }
    
    def action_view_status_updates(self):
        """View all status updates."""
        self.ensure_one()
        
        return {
            'name': _('Status Updates: %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'incident.status.update',
            'view_mode': 'list,form',
            'domain': [('incident_id', '=', self.id)],
            'context': {'default_incident_id': self.id}
        }
    
    def write(self, vals):
        """Auto-create status update when status changes."""
        result = super().write(vals)
        
        if 'status' in vals:
            for record in self:
                # Get old status from database
                old_record = self.browse(record.id)
                old_status = old_record.status if hasattr(old_record, 'status') else False
                
                # Create automatic status update
                if old_status and old_status != vals['status']:
                    self.env['incident.status.update'].create({
                        'incident_id': record.id,
                        'title': _('Status Changed'),
                        'description': _('Incident status changed from %s to %s') % (
                            dict(self._fields['status'].selection).get(old_status),
                            dict(self._fields['status'].selection).get(vals['status'])
                        ),
                        'update_type': 'status_change',
                        'old_status': old_status,
                        'new_status': vals['status'],
                        'visible_to_client': True,
                        'notify_client': record.severity in ['high', 'critical'],
                    })
        
        return result

