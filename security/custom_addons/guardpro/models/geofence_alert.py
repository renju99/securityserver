# -*- coding: utf-8 -*-
"""Geofence Alert Model."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class GeofenceAlert(models.Model):
    """Geofence violation alerts."""

    _name = 'geofence.alert'
    _description = 'Geofence Alert'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'alert_datetime desc'
    _rec_name = 'guard_id'

    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        index=True
    )
    site_id = fields.Many2one(
        'client.site',
        string='Expected Site',
        ondelete='set null',
        help='Site the guard was supposed to be at'
    )
    shift_id = fields.Many2one(
        'guard.shift',
        string='Shift',
        ondelete='cascade',
        help='Shift during which the violation occurred'
    )
    
    alert_type = fields.Selection([
        ('outside_geofence', 'Outside Geofence'),
        ('wrong_site', 'At Wrong Site'),
        ('no_location', 'Location Not Updating')
    ], string='Alert Type', required=True, index=True)
    
    alert_datetime = fields.Datetime(
        string='Alert Time',
        required=True,
        default=fields.Datetime.now,
        index=True
    )
    
    latitude = fields.Float(
        string='Latitude',
        digits=(10, 7),
        help='Guard location when alert triggered'
    )
    longitude = fields.Float(
        string='Longitude',
        digits=(10, 7),
        help='Guard location when alert triggered'
    )
    
    distance_from_site = fields.Float(
        string='Distance from Site (km)',
        help='Distance from expected site'
    )
    
    status = fields.Selection([
        ('new', 'New'),
        ('acknowledged', 'Acknowledged'),
        ('resolved', 'Resolved'),
        ('false_alarm', 'False Alarm')
    ], string='Status', default='new', required=True, tracking=True)
    
    acknowledged_by = fields.Many2one(
        'res.users',
        string='Acknowledged By',
        readonly=True
    )
    acknowledged_date = fields.Datetime(
        string='Acknowledged Date',
        readonly=True
    )
    
    resolved_by = fields.Many2one(
        'res.users',
        string='Resolved By',
        readonly=True
    )
    resolved_date = fields.Datetime(
        string='Resolved Date',
        readonly=True
    )
    
    notes = fields.Text(string='Notes')
    
    notification_sent = fields.Boolean(
        string='Notification Sent',
        default=False,
        help='Whether notification has been sent for this alert'
    )
    
    def action_acknowledge(self):
        """Mark alert as acknowledged."""
        self.ensure_one()
        self.write({
            'status': 'acknowledged',
            'acknowledged_by': self.env.user.id,
            'acknowledged_date': fields.Datetime.now()
        })
    
    def action_resolve(self):
        """Mark alert as resolved."""
        self.ensure_one()
        self.write({
            'status': 'resolved',
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now()
        })
    
    def action_mark_false_alarm(self):
        """Mark alert as false alarm."""
        self.ensure_one()
        self.write({
            'status': 'false_alarm',
            'resolved_by': self.env.user.id,
            'resolved_date': fields.Datetime.now()
        })
    
    @api.model
    def _check_alert_sent_today(self, guard_id, alert_type, site_id=None):
        """Check if an alert has already been sent today for the same guard and type.
        
        Args:
            guard_id: ID of the guard
            alert_type: Type of alert
            site_id: Optional site ID for more specific checking
            
        Returns:
            True if alert was already sent today, False otherwise
        """
        today_start = fields.Datetime.today()
        
        domain = [
            ('guard_id', '=', guard_id),
            ('alert_type', '=', alert_type),
            ('alert_datetime', '>=', today_start),
            ('notification_sent', '=', True)
        ]
        
        if site_id:
            domain.append(('site_id', '=', site_id))
        
        existing_alert = self.search(domain, limit=1)
        
        if existing_alert:
            _logger.info(
                'Alert rate limit: Skipping alert for guard %s (type: %s) - '
                'already sent today at %s',
                guard_id, alert_type, existing_alert.alert_datetime
            )
            return True
        
        return False

    @api.model
    def create_alert(self, guard_id, alert_type, **kwargs):
        """Create a new geofence alert and send notification.
        
        Rate limited to 1 alert per day per guard per alert type.
        
        Args:
            guard_id: ID of the guard
            alert_type: Type of alert
            **kwargs: Additional fields (site_id, shift_id, latitude, longitude, etc.)
            
        Returns:
            Created alert record or existing alert if rate limited
        """
        site_id = kwargs.get('site_id')
        
        # Check if alert was already sent today
        if self._check_alert_sent_today(guard_id, alert_type, site_id):
            # Return the existing alert from today
            today_start = fields.Datetime.today()
            domain = [
                ('guard_id', '=', guard_id),
                ('alert_type', '=', alert_type),
                ('alert_datetime', '>=', today_start),
                ('notification_sent', '=', True)
            ]
            if site_id:
                domain.append(('site_id', '=', site_id))
            return self.search(domain, limit=1, order='alert_datetime desc')
        
        # Create new alert
        values = {
            'guard_id': guard_id,
            'alert_type': alert_type,
        }
        values.update(kwargs)
        
        alert = self.create(values)
        
        # Send notification
        alert._send_notification()
        
        _logger.info(
            'New geofence alert created for guard %s (type: %s)',
            guard_id, alert_type
        )
        
        return alert
    
    def _send_notification(self):
        """Send notification for this alert."""
        self.ensure_one()
        
        if self.notification_sent:
            return
        
        # Get users to notify (managers and supervisors)
        users = self.env['res.users'].search([
            '|',
            ('groups_id', 'in', self.env.ref('guardpro.group_guardpro_manager').id),
            ('groups_id', 'in', self.env.ref('guardpro.group_guardpro_supervisor').id)
        ])
        
        # Prepare notification message
        if self.alert_type == 'outside_geofence':
            message = _('Guard %s is outside the geofence of %s') % (
                self.guard_id.name,
                self.site_id.name if self.site_id else 'assigned site'
            )
        elif self.alert_type == 'wrong_site':
            message = _('Guard %s is at wrong location (expected at %s)') % (
                self.guard_id.name,
                self.site_id.name if self.site_id else 'assigned site'
            )
        else:
            message = _('Guard %s location not updating') % self.guard_id.name
        
        # Create activity for each user
        for user in users:
            self.env['mail.activity'].create({
                'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                'summary': _('Geofence Alert'),
                'note': message,
                'user_id': user.id,
                'res_id': self.id,
                'res_model_id': self.env['ir.model']._get('geofence.alert').id,
            })
        
        # Send Odoo notification
        self.env['bus.bus']._sendone(
            users,
            'simple_notification',
            {
                'title': _('Geofence Alert'),
                'message': message,
                'sticky': False,
                'warning': True
            }
        )
        
        self.notification_sent = True
        _logger.info('Geofence alert notification sent for guard %s', self.guard_id.name)

