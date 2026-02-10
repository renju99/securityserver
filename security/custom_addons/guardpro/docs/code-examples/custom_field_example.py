# -*- coding: utf-8 -*-
"""
Example: Adding Custom Fields to GuardPro Models

This example shows how to add custom fields to existing GuardPro models
using Odoo's inheritance mechanism.
"""

from odoo import models, fields, api


class GuardProfileCustom(models.Model):
    """Extend Guard Profile with custom fields."""
    
    # Inherit the existing guard.profile model
    _inherit = 'guard.profile'
    
    # Add custom fields
    custom_employee_id = fields.Char(
        string='Company Employee ID',
        help='Internal company employee ID number'
    )
    
    security_clearance_level = fields.Selection([
        ('level1', 'Level 1 - Basic'),
        ('level2', 'Level 2 - Intermediate'),
        ('level3', 'Level 3 - Advanced'),
        ('level4', 'Level 4 - Top Secret'),
    ], string='Security Clearance', default='level1')
    
    clearance_expiry_date = fields.Date(
        string='Clearance Expiry Date',
        help='Date when security clearance expires'
    )
    
    uniform_size = fields.Selection([
        ('xs', 'Extra Small'),
        ('s', 'Small'),
        ('m', 'Medium'),
        ('l', 'Large'),
        ('xl', 'Extra Large'),
        ('xxl', 'XX Large'),
    ], string='Uniform Size')
    
    emergency_contact_name = fields.Char(string='Emergency Contact Name')
    emergency_contact_phone = fields.Char(string='Emergency Contact Phone')
    emergency_contact_relation = fields.Char(string='Relation')
    
    is_armed_guard = fields.Boolean(
        string='Armed Guard',
        default=False,
        help='Whether this guard is authorized to carry weapons'
    )
    
    weapon_permit_number = fields.Char(
        string='Weapon Permit Number',
        help='Firearm license/permit number'
    )
    
    weapon_permit_expiry = fields.Date(string='Permit Expiry Date')
    
    years_of_experience = fields.Integer(
        string='Years of Experience',
        help='Total years of security experience'
    )
    
    previous_employer = fields.Char(string='Previous Employer')
    
    # Computed field example
    clearance_status = fields.Selection([
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('none', 'No Clearance'),
    ], string='Clearance Status', compute='_compute_clearance_status', store=True)
    
    @api.depends('clearance_expiry_date')
    def _compute_clearance_status(self):
        """Compute the clearance status based on expiry date."""
        from datetime import datetime, timedelta
        
        for guard in self:
            if not guard.clearance_expiry_date:
                guard.clearance_status = 'none'
            elif guard.clearance_expiry_date < fields.Date.today():
                guard.clearance_status = 'expired'
            elif guard.clearance_expiry_date < fields.Date.today() + timedelta(days=30):
                guard.clearance_status = 'expiring_soon'
            else:
                guard.clearance_status = 'valid'


class ClientSiteCustom(models.Model):
    """Extend Client Site with custom fields."""
    
    _inherit = 'client.site'
    
    # Add site-specific custom fields
    site_code = fields.Char(
        string='Site Code',
        help='Internal site reference code'
    )
    
    contract_number = fields.Char(string='Contract Number')
    
    contract_start_date = fields.Date(string='Contract Start')
    contract_end_date = fields.Date(string='Contract End')
    
    monthly_hours = fields.Float(
        string='Monthly Hours',
        help='Total hours per month contracted'
    )
    
    billing_rate = fields.Float(string='Hourly Billing Rate')
    
    site_manager_name = fields.Char(string='Site Manager Name')
    site_manager_phone = fields.Char(string='Site Manager Phone')
    site_manager_email = fields.Char(string='Site Manager Email')
    
    has_cctv = fields.Boolean(string='Has CCTV System', default=False)
    has_alarm_system = fields.Boolean(string='Has Alarm System', default=False)
    has_access_control = fields.Boolean(string='Has Access Control', default=False)
    
    alarm_code = fields.Char(
        string='Alarm Code',
        help='Site alarm system code (encrypted in production!)'
    )
    
    special_instructions = fields.Text(
        string='Special Site Instructions',
        help='Any special procedures or instructions for this site'
    )


class IncidentReportCustom(models.Model):
    """Extend Incident Report with custom fields."""
    
    _inherit = 'incident.report'
    
    # Add custom incident fields
    police_notified = fields.Boolean(
        string='Police Notified',
        default=False
    )
    
    police_report_number = fields.Char(string='Police Report Number')
    
    fire_department_notified = fields.Boolean(
        string='Fire Department Notified',
        default=False
    )
    
    ambulance_called = fields.Boolean(
        string='Ambulance Called',
        default=False
    )
    
    injuries_reported = fields.Boolean(
        string='Injuries Reported',
        default=False
    )
    
    property_damage = fields.Boolean(
        string='Property Damage',
        default=False
    )
    
    estimated_damage_cost = fields.Monetary(
        string='Estimated Damage Cost',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    insurance_claim_filed = fields.Boolean(
        string='Insurance Claim Filed',
        default=False
    )
    
    insurance_claim_number = fields.Char(string='Claim Number')
    
    follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False
    )
    
    follow_up_date = fields.Date(string='Follow-up Date')
    
    client_notified_date = fields.Datetime(
        string='Client Notification Time',
        help='When the client was notified of this incident'
    )


# Example: How to use these custom fields in code
class ExampleUsage(models.Model):
    """Examples of using custom fields in business logic."""
    
    _name = 'example.usage'
    _description = 'Example Usage'
    
    def example_guard_clearance_check(self):
        """Example: Find guards with expiring clearances."""
        from datetime import datetime, timedelta
        
        # Find guards whose clearance expires in the next 30 days
        expiring_soon_date = fields.Date.today() + timedelta(days=30)
        
        guards = self.env['guard.profile'].search([
            ('clearance_expiry_date', '<=', expiring_soon_date),
            ('clearance_expiry_date', '>=', fields.Date.today()),
        ])
        
        # Send reminder emails
        for guard in guards:
            # Send email notification
            guard.message_post(
                body=f"Your security clearance expires on {guard.clearance_expiry_date}. "
                     f"Please renew it before expiry.",
                subject="Security Clearance Expiring Soon",
                subtype_xmlid='mail.mt_comment',
            )
        
        return guards
    
    def example_site_contract_check(self):
        """Example: Find sites with contracts ending soon."""
        from datetime import datetime, timedelta
        
        # Find contracts ending in next 60 days
        ending_soon_date = fields.Date.today() + timedelta(days=60)
        
        sites = self.env['client.site'].search([
            ('contract_end_date', '<=', ending_soon_date),
            ('contract_end_date', '>=', fields.Date.today()),
        ])
        
        # Notify management
        for site in sites:
            print(f"Contract for {site.name} ending on {site.contract_end_date}")
        
        return sites
    
    def example_incident_with_damage(self):
        """Example: Find incidents with property damage."""
        
        incidents = self.env['incident.report'].search([
            ('property_damage', '=', True),
            ('insurance_claim_filed', '=', False),
        ])
        
        # These incidents have damage but no insurance claim filed yet
        return incidents


# To use these customizations:
# 1. Create a new module that depends on 'guardpro'
# 2. Add this file to your module's models/ directory
# 3. Update views to show the new fields (see view_inheritance_example.xml)
# 4. Install or upgrade your custom module

