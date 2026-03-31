# -*- coding: utf-8 -*-
"""Emergency Broadcast Model."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class EmergencyBroadcast(models.Model):
    """Model to track emergency broadcast messages and their acknowledgments."""

    _name = 'emergency.broadcast'
    _description = 'Emergency Broadcast Message'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'

    # Message Details
    title = fields.Char(
        string='Title',
        required=True,
        tracking=True,
        help='Title of the emergency broadcast'
    )
    message = fields.Text(
        string='Message',
        required=True,
        tracking=True,
        help='Emergency message content'
    )
    priority = fields.Selection([
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], string='Priority', default='urgent', required=True, tracking=True)

    # Broadcast Target
    broadcast_type = fields.Selection([
        ('all', 'All Guards'),
        ('by_site', 'Guards by Site'),
        ('active_only', 'Only Active Guards on Duty')
    ], string='Broadcast To', default='all', required=True)
    
    site_id = fields.Many2one(
        'client.site',
        string='Site',
        help='Specific site (only for by_site broadcast type)'
    )

    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('expired', 'Expired')
    ], string='State', default='draft', tracking=True)

    # Statistics
    total_guards = fields.Integer(
        string='Total Guards',
        compute='_compute_acknowledgment_stats',
        store=True,
        help='Total number of guards who received this message'
    )
    acknowledged_count = fields.Integer(
        string='Acknowledged',
        compute='_compute_acknowledgment_stats',
        store=True,
        help='Number of guards who acknowledged the message'
    )
    pending_count = fields.Integer(
        string='Pending',
        compute='_compute_acknowledgment_stats',
        store=True,
        help='Number of guards who have not yet acknowledged'
    )
    acknowledgment_rate = fields.Float(
        string='Acknowledgment Rate (%)',
        compute='_compute_acknowledgment_stats',
        store=True,
        help='Percentage of guards who acknowledged'
    )

    # Relationships
    acknowledgment_ids = fields.One2many(
        'emergency.broadcast.acknowledgment',
        'broadcast_id',
        string='Acknowledgments'
    )

    # Audit
    sent_by = fields.Many2one(
        'res.users',
        string='Sent By',
        readonly=True,
        help='User who sent this broadcast'
    )
    sent_date = fields.Datetime(
        string='Sent Date',
        readonly=True,
        help='Date and time when the broadcast was sent'
    )

    @api.depends('acknowledgment_ids', 'acknowledgment_ids.is_acknowledged')
    def _compute_acknowledgment_stats(self):
        """Compute acknowledgment statistics."""
        for record in self:
            total = len(record.acknowledgment_ids)
            acknowledged = len(record.acknowledgment_ids.filtered('is_acknowledged'))
            
            record.total_guards = total
            record.acknowledged_count = acknowledged
            record.pending_count = total - acknowledged
            record.acknowledgment_rate = (
                (acknowledged / total * 100) if total > 0 else 0.0
            )

    def _send_broadcast_emails(self, guards):
        """Send email notifications to all target guards."""
        _logger.info(
            'Email notifications are disabled: skipped emergency broadcast emails for %d guards',
            len(guards.filtered('email'))
        )
    
    def action_send_broadcast(self):
        """Send the emergency broadcast to guards."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise ValidationError(_('Only draft broadcasts can be sent.'))

        # Get target guards
        guards = self._get_target_guards()
        
        if not guards:
            raise ValidationError(_('No guards found matching the criteria.'))

        # Create acknowledgment records for each guard
        acknowledgments = []
        for guard in guards:
            if guard.user_id:  # Only send to guards with user accounts
                acknowledgments.append({
                    'broadcast_id': self.id,
                    'guard_id': guard.id,
                    'user_id': guard.user_id.id,
                })
        
        if not acknowledgments:
            raise ValidationError(_('No guards with user accounts found.'))

        # Create acknowledgments
        self.env['emergency.broadcast.acknowledgment'].create(acknowledgments)

        # Send notifications via bus
        for ack in self.acknowledgment_ids:
            self._send_notification(ack)

        # Update state
        self.write({
            'state': 'sent',
            'sent_by': self.env.user.id,
            'sent_date': fields.Datetime.now()
        })

        # Log the broadcast
        self.message_post(
            body=_(
                'Emergency broadcast sent to %d guards. '
                'Priority: %s'
            ) % (len(acknowledgments), self.priority.upper())
        )
        
        # Send email notifications to all target guards
        self._send_broadcast_emails(guards)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Emergency Broadcast Sent'),
                'message': _(
                    'Message sent to %d guards successfully.'
                ) % len(acknowledgments),
                'type': 'success',
                'sticky': False,
            }
        }

    def _get_target_guards(self):
        """Get guards matching the broadcast criteria."""
        domain = [('status', '=', 'active')]

        if self.broadcast_type == 'by_site' and self.site_id:
            domain.append(('site_ids', 'in', [self.site_id.id]))
        elif self.broadcast_type == 'active_only':
            # Get guards currently on duty
            active_shifts = self.env['guard.shift'].search([
                ('status', '=', 'in_progress'),
                ('start_datetime', '<=', fields.Datetime.now()),
                ('end_datetime', '>=', fields.Datetime.now())
            ])
            guard_ids = active_shifts.mapped('guard_id').ids
            if guard_ids:
                domain.append(('id', 'in', guard_ids))
            else:
                return self.env['guard.profile']

        return self.env['guard.profile'].search(domain)

    def _send_notification(self, acknowledgment):
        """Send notification to a guard via the bus."""
        try:
            # Send via Odoo bus - only once when broadcast is sent
            self.env['bus.bus']._sendone(
                acknowledgment.user_id.partner_id,
                'emergency_broadcast',
                {
                    'id': self.id,
                    'ack_id': acknowledgment.id,
                    'title': self.title,
                    'message': self.message,
                    'priority': self.priority,
                    'sent_date': self.sent_date.isoformat() if self.sent_date else False,
                }
            )
            _logger.info(
                'Emergency broadcast sent to user %s (Guard: %s)',
                acknowledgment.user_id.name,
                acknowledgment.guard_id.name
            )
        except Exception as e:
            _logger.error(
                'Failed to send emergency broadcast to user %s: %s',
                acknowledgment.user_id.name,
                str(e)
            )


class EmergencyBroadcastAcknowledgment(models.Model):
    """Track individual guard acknowledgments of emergency broadcasts."""

    _name = 'emergency.broadcast.acknowledgment'
    _description = 'Emergency Broadcast Acknowledgment'
    _order = 'acknowledged_date desc'

    broadcast_id = fields.Many2one(
        'emergency.broadcast',
        string='Broadcast',
        required=True,
        ondelete='cascade',
        index=True
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        index=True
    )
    is_acknowledged = fields.Boolean(
        string='Acknowledged',
        default=False,
        index=True
    )
    acknowledged_date = fields.Datetime(
        string='Acknowledged Date',
        readonly=True
    )

    _sql_constraints = [
        ('unique_broadcast_user', 
         'UNIQUE(broadcast_id, user_id)',
         'Each user can only acknowledge a broadcast once.')
    ]

    def action_acknowledge(self):
        """Mark the broadcast as acknowledged by the user."""
        for record in self:
            if not record.is_acknowledged:
                record.write({
                    'is_acknowledged': True,
                    'acknowledged_date': fields.Datetime.now()
                })
                _logger.info(
                    'Emergency broadcast %s acknowledged by %s',
                    record.broadcast_id.title,
                    record.user_id.name
                )

    def get_pending_broadcasts(self, user_id):
        """Get all pending (unacknowledged) broadcasts for a user."""
        return self.search([
            ('user_id', '=', user_id),
            ('is_acknowledged', '=', False)
        ])

