# -*- coding: utf-8 -*-
"""GPS Tracking Diagnostic Tool.

This module helps diagnose GPS tracking issues for guards.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class GPSDiagnostic(models.TransientModel):
    """GPS Tracking Diagnostic Wizard."""
    
    _name = 'gps.diagnostic'
    _description = 'GPS Tracking Diagnostic'
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True
    )
    
    # Diagnostic Results
    has_user_account = fields.Boolean(
        string='Has User Account',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='User Account',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    has_location_data = fields.Boolean(
        string='Has Location Data',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    last_location_update = fields.Datetime(
        string='Last Location Update',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    current_latitude = fields.Float(
        string='Current Latitude',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    current_longitude = fields.Float(
        string='Current Longitude',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    location_history_count = fields.Integer(
        string='Location History Count',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    last_history_record = fields.Datetime(
        string='Last History Record',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    diagnostic_message = fields.Html(
        string='Diagnostic Results',
        compute='_compute_diagnostics',
        readonly=True
    )
    
    @api.depends('guard_id')
    def _compute_diagnostics(self):
        """Run diagnostic checks."""
        for record in self:
            if not record.guard_id:
                record.has_user_account = False
                record.user_id = False
                record.has_location_data = False
                record.last_location_update = False
                record.current_latitude = 0.0
                record.current_longitude = 0.0
                record.location_history_count = 0
                record.last_history_record = False
                record.diagnostic_message = '<p>No guard selected.</p>'
                continue
            
            guard = record.guard_id
            messages = []
            
            # Check 1: User Account
            if guard.user_id:
                record.has_user_account = True
                record.user_id = guard.user_id
                messages.append(
                    f'<p style="color: green;">✓ <strong>User Account:</strong> '
                    f'{guard.user_id.name} (ID: {guard.user_id.id})</p>'
                )
            else:
                record.has_user_account = False
                record.user_id = False
                messages.append(
                    '<p style="color: red;">✗ <strong>User Account:</strong> '
                    'No user account linked! This is the problem - guard cannot login.</p>'
                    '<p><strong>Solution:</strong> Link a user account to this guard profile.</p>'
                )
            
            # Check 2: Location Data on Guard Profile
            if guard.current_latitude and guard.current_longitude:
                record.has_location_data = True
                record.current_latitude = guard.current_latitude
                record.current_longitude = guard.current_longitude
                record.last_location_update = guard.last_location_update
                messages.append(
                    f'<p style="color: green;">✓ <strong>Location Data:</strong> '
                    f'Lat {guard.current_latitude:.6f}, Lon {guard.current_longitude:.6f}</p>'
                )
                if guard.last_location_update:
                    delta = fields.Datetime.now() - guard.last_location_update
                    minutes_ago = int(delta.total_seconds() / 60)
                    if minutes_ago < 10:
                        messages.append(
                            f'<p style="color: green;">✓ <strong>Last Update:</strong> '
                            f'{minutes_ago} minutes ago (recent!)</p>'
                        )
                    elif minutes_ago < 60:
                        messages.append(
                            f'<p style="color: orange;">⚠ <strong>Last Update:</strong> '
                            f'{minutes_ago} minutes ago (somewhat stale)</p>'
                        )
                    else:
                        hours_ago = int(minutes_ago / 60)
                        messages.append(
                            f'<p style="color: red;">✗ <strong>Last Update:</strong> '
                            f'{hours_ago} hours ago (very stale!)</p>'
                        )
            else:
                record.has_location_data = False
                record.current_latitude = 0.0
                record.current_longitude = 0.0
                record.last_location_update = False
                messages.append(
                    '<p style="color: red;">✗ <strong>Location Data:</strong> '
                    'No location data available.</p>'
                )
            
            # Check 3: Location History
            history_count = self.env['guard.location.history'].search_count([
                ('guard_id', '=', guard.id)
            ])
            record.location_history_count = history_count
            
            if history_count > 0:
                last_history = self.env['guard.location.history'].search([
                    ('guard_id', '=', guard.id)
                ], limit=1, order='timestamp desc')
                record.last_history_record = last_history.timestamp
                messages.append(
                    f'<p style="color: green;">✓ <strong>Location History:</strong> '
                    f'{history_count} records found</p>'
                )
                if last_history:
                    delta = fields.Datetime.now() - last_history.timestamp
                    minutes_ago = int(delta.total_seconds() / 60)
                    messages.append(
                        f'<p style="color: green;">✓ <strong>Last History Record:</strong> '
                        f'{minutes_ago} minutes ago</p>'
                    )
            else:
                record.last_history_record = False
                messages.append(
                    '<p style="color: red;">✗ <strong>Location History:</strong> '
                    'No location history records found.</p>'
                )
            
            # Check 4: Active Attendance
            active_attendance = self.env['guard.attendance'].search([
                ('guard_id', '=', guard.id),
                ('checkout_time', '=', False)
            ], limit=1, order='checkin_time desc')
            
            if active_attendance:
                messages.append(
                    f'<p style="color: green;">✓ <strong>Active Attendance:</strong> '
                    f'Checked in at {active_attendance.site_id.name if active_attendance.site_id else "Unknown Project"}</p>'
                )
            else:
                messages.append(
                    '<p style="color: orange;">⚠ <strong>Active Attendance:</strong> '
                    'Guard is not currently checked in.</p>'
                )
            
            # Summary and Recommendations
            messages.append('<hr/>')
            messages.append('<h4>Summary & Recommendations:</h4>')
            
            if not record.has_user_account:
                messages.append(
                    '<p style="color: red; font-weight: bold;">🔴 CRITICAL: '
                    'Guard has no user account! This must be fixed first.</p>'
                    '<p><strong>Action:</strong> Create or link a user account '
                    'for this guard in the User Account field.</p>'
                )
            elif not record.has_location_data:
                messages.append(
                    '<p style="color: orange; font-weight: bold;">⚠️ WARNING: '
                    'Guard has user account but no GPS data is being recorded.</p>'
                    '<p><strong>Possible causes:</strong></p>'
                    '<ul>'
                    '<li>Guard has not granted location permission on mobile device</li>'
                    '<li>Guard is not using the mobile interface (/guardpro/mobile)</li>'
                    '<li>GPS tracking JavaScript is not loading properly</li>'
                    '<li>Network connectivity issues preventing location updates</li>'
                    '</ul>'
                    '<p><strong>Action:</strong> Ask guard to:</p>'
                    '<ol>'
                    '<li>Login to mobile interface at /guardpro/mobile</li>'
                    '<li>Click "Enable Location Tracking" banner when prompted</li>'
                    '<li>Grant location permission when browser asks</li>'
                    '<li>Verify green "Location tracking enabled" message appears</li>'
                    '</ol>'
                )
            elif record.location_history_count == 0:
                messages.append(
                    '<p style="color: orange; font-weight: bold;">⚠️ WARNING: '
                    'Current location exists but no history is being saved.</p>'
                    '<p>This might indicate a database or permission issue.</p>'
                )
            else:
                messages.append(
                    '<p style="color: green; font-weight: bold;">✓ GPS tracking '
                    'appears to be working correctly!</p>'
                )
            
            record.diagnostic_message = ''.join(messages)
    
    def action_test_location_update(self):
        """Test location update with dummy coordinates."""
        self.ensure_one()
        
        if not self.guard_id:
            raise UserError(_('Please select a guard first.'))
        
        if not self.guard_id.user_id:
            raise UserError(_(
                'Guard has no user account! Please create or link a user account first.'
            ))
        
        # Test with dummy coordinates (London, UK)
        test_lat = 51.5074
        test_lon = -0.1278
        
        try:
            self.guard_id.update_location(test_lat, test_lon, accuracy=10.0, is_manual=True)
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Success!'),
                    'message': _(
                        'Test location update successful! '
                        'Guard can now update location via mobile app.'
                    ),
                    'type': 'success',
                    'sticky': False,
                }
            }
        except Exception as e:
            raise UserError(_(
                'Location update failed: %s\n\n'
                'This indicates a deeper issue with the guard profile or database.'
            ) % str(e))
    
    def action_open_guard_profile(self):
        """Open guard profile form."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'guard.profile',
            'res_id': self.guard_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_view_location_history(self):
        """View location history for this guard."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Location History - %s') % self.guard_id.name,
            'res_model': 'guard.location.history',
            'view_mode': 'list,form',
            'domain': [('guard_id', '=', self.guard_id.id)],
            'context': {'default_guard_id': self.guard_id.id},
        }

