# -*- coding: utf-8 -*-
"""
Example: Adding Constraints and Validations to GuardPro

This example demonstrates different types of constraints:
- Python constraints (@api.constrains)
- SQL constraints (_sql_constraints)
- Onchange validations (@api.onchange)
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import datetime, timedelta
import re


class GuardProfileConstraints(models.Model):
    """Examples of constraints in Guard Profile."""
    
    _inherit = 'guard.profile'
    
    # ========================================
    # SQL Constraints (Database Level)
    # ========================================
    
    # SQL constraints are enforced at database level
    # Syntax: (constraint_name, sql_definition, error_message)
    
    _sql_constraints = [
        ('badge_number_unique', 
         'UNIQUE(badge_number)', 
         'Badge number must be unique! This badge is already assigned to another guard.'),
        
        ('custom_employee_id_unique',
         'UNIQUE(custom_employee_id)',
         'Employee ID must be unique!'),
    ]
    
    # ========================================
    # Example 1: Simple Field Validation
    # ========================================
    
    @api.constrains('badge_number')
    def _check_badge_number_format(self):
        """Validate badge number format (e.g., G-001, G-999)."""
        for guard in self:
            if guard.badge_number:
                # Check format: Letter-Number (e.g., G-001)
                pattern = r'^[A-Z]-\d{3}$'
                if not re.match(pattern, guard.badge_number):
                    raise ValidationError(_(
                        'Badge number must follow format: LETTER-###\n'
                        'Examples: G-001, S-100, M-999'
                    ))
    
    # ========================================
    # Example 2: Date Validation
    # ========================================
    
    @api.constrains('date_of_birth')
    def _check_minimum_age(self):
        """Ensure guard is at least 18 years old."""
        minimum_age = 18
        
        for guard in self:
            if guard.date_of_birth:
                today = fields.Date.today()
                age_delta = today - guard.date_of_birth
                age_years = age_delta.days / 365.25
                
                if age_years < minimum_age:
                    raise ValidationError(_(
                        'Guard must be at least %s years old. '
                        'Current age: %.1f years.'
                    ) % (minimum_age, age_years))
    
    # ========================================
    # Example 3: Cross-Field Validation
    # ========================================
    
    @api.constrains('clearance_expiry_date', 'security_clearance_level')
    def _check_clearance_expiry(self):
        """Validate clearance has expiry date if level is set."""
        for guard in self:
            if guard.security_clearance_level and guard.security_clearance_level != 'level1':
                if not guard.clearance_expiry_date:
                    raise ValidationError(_(
                        'Security clearance level %s requires an expiry date.'
                    ) % guard.security_clearance_level)
                
                # Check expiry date is in the future
                if guard.clearance_expiry_date < fields.Date.today():
                    raise ValidationError(_(
                        'Security clearance has expired! '
                        'Please renew before assigning to shifts.'
                    ))
    
    # ========================================
    # Example 4: Multi-Field Validation
    # ========================================
    
    @api.constrains('is_armed_guard', 'weapon_permit_number', 'weapon_permit_expiry')
    def _check_weapon_permit(self):
        """Validate weapon permit for armed guards."""
        for guard in self:
            if guard.is_armed_guard:
                # Armed guard must have permit number
                if not guard.weapon_permit_number:
                    raise ValidationError(_(
                        'Armed guards must have a weapon permit number.'
                    ))
                
                # Must have expiry date
                if not guard.weapon_permit_expiry:
                    raise ValidationError(_(
                        'Weapon permit must have an expiry date.'
                    ))
                
                # Check permit hasn't expired
                if guard.weapon_permit_expiry < fields.Date.today():
                    raise ValidationError(_(
                        'Weapon permit has expired on %s. '
                        'Guard cannot be assigned to armed positions.'
                    ) % guard.weapon_permit_expiry)
                
                # Warn if expiring soon (within 30 days)
                expiry_warning_days = 30
                warning_date = fields.Date.today() + timedelta(days=expiry_warning_days)
                if guard.weapon_permit_expiry <= warning_date:
                    # This is a warning, not an error, so we use message_post instead
                    guard.message_post(
                        body=_(
                            'Warning: Weapon permit expires soon (%s). '
                            'Please renew within %s days.'
                        ) % (guard.weapon_permit_expiry, expiry_warning_days),
                        subject='Weapon Permit Expiring Soon',
                    )
    
    # ========================================
    # Example 5: Numeric Range Validation
    # ========================================
    
    @api.constrains('years_of_experience')
    def _check_years_of_experience(self):
        """Validate years of experience is reasonable."""
        for guard in self:
            if guard.years_of_experience:
                if guard.years_of_experience < 0:
                    raise ValidationError(_(
                        'Years of experience cannot be negative.'
                    ))
                
                if guard.years_of_experience > 60:
                    raise ValidationError(_(
                        'Years of experience seems unrealistic (%s years). '
                        'Please verify.'
                    ) % guard.years_of_experience)
    
    # ========================================
    # Example 6: Relational Field Validation
    # ========================================
    
    @api.constrains('certification_ids')
    def _check_required_certifications(self):
        """Ensure guard has minimum required certifications."""
        required_cert_names = ['First Aid', 'CPR']
        
        for guard in self:
            if guard.status == 'active':
                guard_cert_names = guard.certification_ids.mapped('name')
                
                missing_certs = set(required_cert_names) - set(guard_cert_names)
                
                if missing_certs:
                    raise ValidationError(_(
                        'Active guards must have the following certifications:\n%s\n\n'
                        'Missing: %s'
                    ) % (', '.join(required_cert_names), ', '.join(missing_certs)))


class GuardShiftConstraints(models.Model):
    """Examples of constraints in Guard Shift."""
    
    _inherit = 'guard.shift'
    
    # ========================================
    # SQL Constraints
    # ========================================
    
    _sql_constraints = [
        ('start_before_end',
         'CHECK(end_datetime > start_datetime)',
         'Shift end time must be after start time!'),
    ]
    
    # ========================================
    # Example 7: Date Range Validation
    # ========================================
    
    @api.constrains('start_datetime', 'end_datetime')
    def _check_shift_duration(self):
        """Validate shift duration is reasonable."""
        min_duration_hours = 2
        max_duration_hours = 16
        
        for shift in self:
            if shift.start_datetime and shift.end_datetime:
                duration = shift.end_datetime - shift.start_datetime
                hours = duration.total_seconds() / 3600
                
                if hours < min_duration_hours:
                    raise ValidationError(_(
                        'Shift duration must be at least %s hours. '
                        'Current duration: %.1f hours.'
                    ) % (min_duration_hours, hours))
                
                if hours > max_duration_hours:
                    raise ValidationError(_(
                        'Shift duration cannot exceed %s hours. '
                        'Current duration: %.1f hours.\n'
                        'Please split into multiple shifts.'
                    ) % (max_duration_hours, hours))
    
    # ========================================
    # Example 8: Prevent Overlapping Records
    # ========================================
    
    @api.constrains('guard_id', 'start_datetime', 'end_datetime', 'state')
    def _check_no_overlapping_shifts(self):
        """Prevent guard from being assigned to overlapping shifts."""
        for shift in self:
            if shift.state in ['confirmed', 'in_progress'] and shift.guard_id:
                # Search for overlapping shifts
                overlapping = self.search([
                    ('id', '!=', shift.id),
                    ('guard_id', '=', shift.guard_id.id),
                    ('state', 'in', ['confirmed', 'in_progress']),
                    '|',
                    '&', ('start_datetime', '<=', shift.start_datetime),
                         ('end_datetime', '>', shift.start_datetime),
                    '&', ('start_datetime', '<', shift.end_datetime),
                         ('end_datetime', '>=', shift.end_datetime),
                ])
                
                if overlapping:
                    raise ValidationError(_(
                        'Guard %s is already assigned to another shift during this time:\n'
                        'Conflicting shift: %s to %s at %s'
                    ) % (
                        shift.guard_id.name,
                        overlapping[0].start_datetime,
                        overlapping[0].end_datetime,
                        overlapping[0].site_id.name
                    ))
    
    # ========================================
    # Example 9: State-Dependent Validation
    # ========================================
    
    @api.constrains('state', 'guard_id')
    def _check_confirmed_shift_requirements(self):
        """Ensure confirmed shifts have all required data."""
        for shift in self:
            if shift.state in ['confirmed', 'in_progress']:
                # Must have guard assigned
                if not shift.guard_id:
                    raise ValidationError(_(
                        'Cannot confirm shift without assigning a guard.'
                    ))
                
                # Must have site assigned
                if not shift.site_id:
                    raise ValidationError(_(
                        'Cannot confirm shift without assigning a site.'
                    ))
                
                # Guard must be active
                if shift.guard_id.status != 'active':
                    raise ValidationError(_(
                        'Cannot assign shift to inactive guard: %s'
                    ) % shift.guard_id.name)
    
    # ========================================
    # Example 10: Business Rule Validation
    # ========================================
    
    @api.constrains('guard_id', 'site_id')
    def _check_guard_clearance_for_site(self):
        """Ensure guard has required clearance level for site."""
        for shift in self:
            if shift.guard_id and shift.site_id:
                site_required_level = shift.site_id.required_clearance_level or 'level1'
                guard_level = shift.guard_id.security_clearance_level or 'level1'
                
                # Convert to numeric for comparison
                level_map = {'level1': 1, 'level2': 2, 'level3': 3, 'level4': 4}
                
                if level_map[guard_level] < level_map[site_required_level]:
                    raise ValidationError(_(
                        'Guard %s has clearance level %s but site %s requires level %s or higher.'
                    ) % (
                        shift.guard_id.name,
                        guard_level,
                        shift.site_id.name,
                        site_required_level
                    ))


class IncidentReportConstraints(models.Model):
    """Examples of constraints in Incident Report."""
    
    _inherit = 'incident.report'
    
    # ========================================
    # Example 11: Conditional Required Fields
    # ========================================
    
    @api.constrains('priority', 'description')
    def _check_critical_incident_details(self):
        """Critical incidents must have detailed description."""
        min_description_length = 100
        
        for incident in self:
            if incident.priority == 'critical':
                if not incident.description or len(incident.description) < min_description_length:
                    raise ValidationError(_(
                        'Critical incidents require a detailed description '
                        '(minimum %s characters).\n'
                        'Current length: %s characters.'
                    ) % (min_description_length, len(incident.description or '')))
    
    # ========================================
    # Example 12: File/Attachment Validation
    # ========================================
    
    @api.constrains('photo_ids', 'priority')
    def _check_photo_required_for_critical(self):
        """Critical incidents must have photo evidence."""
        for incident in self:
            if incident.priority == 'critical' and incident.state != 'draft':
                if not incident.photo_ids:
                    raise ValidationError(_(
                        'Critical incidents must include photo evidence.\n'
                        'Please attach at least one photo before submitting.'
                    ))
    
    # ========================================
    # Example 13: State Transition Validation
    # ========================================
    
    @api.constrains('state', 'resolution_notes')
    def _check_resolution_notes(self):
        """Resolved incidents must have resolution notes."""
        for incident in self:
            if incident.state == 'resolved':
                if not incident.resolution_notes:
                    raise ValidationError(_(
                        'Please provide resolution notes before marking incident as resolved.'
                    ))


# ========================================
# ONCHANGE VALIDATIONS
# ========================================

class GuardProfileOnchange(models.Model):
    """Examples of onchange validations (warnings, not hard errors)."""
    
    _inherit = 'guard.profile'
    
    @api.onchange('date_of_birth')
    def _onchange_date_of_birth(self):
        """Warn if guard seems too young or too old."""
        if self.date_of_birth:
            today = fields.Date.today()
            age = (today - self.date_of_birth).days / 365.25
            
            if age < 18:
                return {
                    'warning': {
                        'title': _('Age Warning'),
                        'message': _(
                            'Guard appears to be under 18 years old (%.1f years). '
                            'Please verify date of birth.' % age
                        )
                    }
                }
            elif age > 70:
                return {
                    'warning': {
                        'title': _('Age Notice'),
                        'message': _(
                            'Guard appears to be over 70 years old (%.1f years). '
                            'Please verify date of birth.' % age
                        )
                    }
                }
    
    @api.onchange('is_armed_guard')
    def _onchange_is_armed_guard(self):
        """Clear weapon permit fields if unarmed."""
        if not self.is_armed_guard:
            self.weapon_permit_number = False
            self.weapon_permit_expiry = False


class GuardShiftOnchange(models.Model):
    """Examples of onchange validations in Guard Shift."""
    
    _inherit = 'guard.shift'
    
    @api.onchange('guard_id')
    def _onchange_guard_id(self):
        """Warn if guard has expired certifications."""
        if self.guard_id:
            expired_certs = self.guard_id.certification_ids.filtered(
                lambda c: c.expiry_date and c.expiry_date < fields.Date.today()
            )
            
            if expired_certs:
                cert_names = ', '.join(expired_certs.mapped('name'))
                return {
                    'warning': {
                        'title': _('Expired Certifications'),
                        'message': _(
                            'Warning: Guard %s has expired certifications:\n%s\n\n'
                            'Please renew before assigning to shifts.'
                        ) % (self.guard_id.name, cert_names)
                    }
                }
    
    @api.onchange('start_datetime', 'end_datetime')
    def _onchange_shift_times(self):
        """Warn if shift is during unusual hours."""
        if self.start_datetime and self.end_datetime:
            # Check if shift is very long
            duration = (self.end_datetime - self.start_datetime).total_seconds() / 3600
            if duration > 12:
                return {
                    'warning': {
                        'title': _('Long Shift'),
                        'message': _(
                            'This shift is %.1f hours long. '
                            'Consider splitting into multiple shifts for guard safety.'
                        ) % duration
                    }
                }


# ========================================
# TIPS FOR CONSTRAINTS
# ========================================

"""
1. SQL Constraints vs Python Constraints:
   - SQL: Faster, enforced at database level, simple checks
   - Python: More flexible, can check related records, better error messages
   - Use SQL for simple uniqueness, check constraints
   - Use Python for complex business logic

2. When to Use @api.constrains:
   - Data validation (format, range, etc.)
   - Cross-field validation
   - Business rule enforcement
   - Prevent invalid state transitions

3. When to Use @api.onchange:
   - User warnings (not errors)
   - Auto-fill related fields
   - Clear dependent fields
   - Provide helpful suggestions

4. Performance Tips:
   - Keep constraint checks fast
   - Avoid expensive database queries
   - Use search_count() instead of len(search())
   - Cache frequently used data

5. Error Messages:
   - Be specific and helpful
   - Explain what's wrong
   - Suggest how to fix it
   - Use _() for translation

6. Testing Constraints:
   # This should raise ValidationError
   with self.assertRaises(ValidationError):
       guard.write({'badge_number': 'INVALID'})

7. Common Pitfalls:
   - Forgetting to iterate: for record in self:
   - Not handling empty/False values
   - Circular constraint dependencies
   - Constraints that prevent valid data entry

"""

