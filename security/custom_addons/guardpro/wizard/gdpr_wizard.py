# -*- coding: utf-8 -*-
"""GDPR Compliance Tools."""

from odoo import models, fields, api, _
from odoo.exceptions import UserError
import json
import base64
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)


class GDPRDataExportWizard(models.TransientModel):
    """Export guard personal data for GDPR compliance."""
    
    _name = 'gdpr.data.export.wizard'
    _description = 'GDPR Data Export'
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True
    )
    
    export_format = fields.Selection([
        ('json', 'JSON'),
        ('xml', 'XML'),
        ('pdf', 'PDF Report')
    ], string='Export Format', required=True, default='json')
    
    include_shifts = fields.Boolean(
        string='Include Shift History',
        default=True
    )
    
    include_attendance = fields.Boolean(
        string='Include Attendance Records',
        default=True
    )
    
    include_incidents = fields.Boolean(
        string='Include Incident Reports',
        default=True
    )
    
    include_feedback = fields.Boolean(
        string='Include Client Feedback',
        default=True
    )
    
    include_location = fields.Boolean(
        string='Include Location History',
        default=False,
        help='Warning: This may generate large files'
    )
    
    export_file = fields.Binary(
        string='Export File',
        readonly=True
    )
    
    export_filename = fields.Char(
        string='Filename',
        readonly=True
    )
    
    def action_export(self):
        """Export guard data."""
        self.ensure_one()
        
        guard = self.guard_id
        
        # Collect data
        data = {
            'export_date': fields.Datetime.now().isoformat(),
            'guard_information': {
                'name': guard.name,
                'badge_number': guard.badge_number,
                'email': guard.user_id.email if guard.user_id else '',
                'phone': guard.phone,
                'mobile': guard.mobile,
                'address': guard.address,
                'emergency_contact': guard.emergency_contact_name,
                'emergency_phone': guard.emergency_contact_phone,
                'date_of_birth': guard.birthday.isoformat() if guard.birthday else None,
                'hire_date': guard.date_of_joining.isoformat() if guard.date_of_joining else None,
                'status': guard.status,
            }
        }
        
        # Add shift history
        if self.include_shifts:
            shifts = self.env['guard.shift'].search([('guard_id', '=', guard.id)])
            data['shifts'] = [{
                'site': shift.site_id.name,
                'start': shift.start_datetime.isoformat(),
                'end': shift.end_datetime.isoformat(),
                'status': shift.status
            } for shift in shifts]
        
        # Add attendance
        if self.include_attendance:
            attendance = self.env['guard.attendance'].search([('guard_id', '=', guard.id)])
            data['attendance'] = [{
                'site': att.site_id.name,
                'checkin': att.checkin_time.isoformat(),
                'checkout': att.checkout_time.isoformat() if att.checkout_time else None,
                'duration': att.duration
            } for att in attendance]
        
        # Add incidents
        if self.include_incidents:
            incidents = self.env['incident.report'].search([('guard_id', '=', guard.id)])
            data['incident_reports'] = [{
                'reference': inc.name,
                'date': inc.incident_datetime.isoformat(),
                'site': inc.site_id.name,
                'type': inc.category_id.name if inc.category_id else 'N/A',
                'severity': inc.severity
            } for inc in incidents]
        
        # Add feedback
        if self.include_feedback:
            feedback = self.env['client.feedback'].search([('guard_id', '=', guard.id)])
            data['client_feedback'] = [{
                'date': fb.feedback_date.isoformat(),
                'client': fb.client_id.name,
                'rating': fb.overall_rating,
                'type': fb.feedback_type
            } for fb in feedback]
        
        # Add location history (if requested)
        if self.include_location:
            location = self.env['guard.location.history'].search([
                ('guard_id', '=', guard.id)
            ], limit=1000, order='timestamp desc')
            data['location_history'] = [{
                'timestamp': loc.timestamp.isoformat(),
                'latitude': loc.latitude,
                'longitude': loc.longitude,
                'site': loc.site_id.name if loc.site_id else None
            } for loc in location]
        
        # Generate export based on format
        if self.export_format == 'json':
            content = json.dumps(data, indent=2, ensure_ascii=False)
            filename = f'guard_data_{guard.badge_number}_{datetime.now().strftime("%Y%m%d")}.json'
        elif self.export_format == 'xml':
            content = self._dict_to_xml(data)
            filename = f'guard_data_{guard.badge_number}_{datetime.now().strftime("%Y%m%d")}.xml'
        else:  # PDF
            # TODO: Generate PDF report
            content = json.dumps(data, indent=2)
            filename = f'guard_data_{guard.badge_number}_{datetime.now().strftime("%Y%m%d")}.json'
        
        self.write({
            'export_file': base64.b64encode(content.encode('utf-8')),
            'export_filename': filename
        })
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'gdpr.data.export.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _dict_to_xml(self, data, root_tag='guard_data'):
        """Convert dict to XML."""
        import xml.etree.ElementTree as ET
        
        def dict_to_elem(d, parent):
            for key, value in d.items():
                child = ET.SubElement(parent, key)
                if isinstance(value, dict):
                    dict_to_elem(value, child)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            item_elem = ET.SubElement(child, 'item')
                            dict_to_elem(item, item_elem)
                        else:
                            item_elem = ET.SubElement(child, 'item')
                            item_elem.text = str(item)
                else:
                    child.text = str(value) if value is not None else ''
        
        root = ET.Element(root_tag)
        dict_to_elem(data, root)
        return ET.tostring(root, encoding='unicode')


class GDPRAnonymizationWizard(models.TransientModel):
    """Anonymize departed guard data for GDPR compliance."""
    
    _name = 'gdpr.anonymization.wizard'
    _description = 'GDPR Data Anonymization'
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        domain=[('status', '=', 'terminated')]
    )
    
    anonymize_personal_info = fields.Boolean(
        string='Anonymize Personal Information',
        default=True
    )
    
    anonymize_contact_info = fields.Boolean(
        string='Anonymize Contact Information',
        default=True
    )
    
    delete_location_history = fields.Boolean(
        string='Delete Location History',
        default=True
    )
    
    confirmation = fields.Boolean(
        string='I confirm this action cannot be undone',
        required=True
    )
    
    def action_anonymize(self):
        """Anonymize guard data."""
        self.ensure_one()
        
        if not self.confirmation:
            raise UserError(_('You must confirm to proceed with anonymization.'))
        
        guard = self.guard_id
        
        if guard.status != 'terminated':
            raise UserError(_('Can only anonymize data for terminated guards.'))
        
        # Anonymize personal info
        if self.anonymize_personal_info:
            guard.write({
                'name': f'ANONYMIZED_{guard.id}',
                'birthday': False,
                'identification_number': False,
                'address': False,
                'emergency_contact_name': False,
                'emergency_contact_phone': False,
            })
        
        # Anonymize contact info
        if self.anonymize_contact_info:
            guard.write({
                'phone': False,
                'mobile': False,
            })
            if guard.user_id:
                guard.user_id.write({
                    'email': f'anonymized_{guard.id}@example.com',
                    'active': False
                })
        
        # Delete location history
        if self.delete_location_history:
            location_records = self.env['guard.location.history'].search([
                ('guard_id', '=', guard.id)
            ])
            location_records.unlink()
        
        _logger.info('GDPR: Anonymized data for guard %s (ID: %d)', guard.name, guard.id)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Guard data has been anonymized successfully.'),
                'type': 'success',
                'sticky': False,
            }
        }

