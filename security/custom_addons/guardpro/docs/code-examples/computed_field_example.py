# -*- coding: utf-8 -*-
"""
Example: Creating Computed Fields in GuardPro

This example demonstrates different types of computed fields and
how to use @api.depends decorator correctly.
"""

from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GuardProfileComputed(models.Model):
    """Examples of computed fields in Guard Profile."""
    
    _inherit = 'guard.profile'
    
    # ========================================
    # Example 1: Simple Computed Field
    # ========================================
    
    full_name_with_badge = fields.Char(
        string='Full Name with Badge',
        compute='_compute_full_name_with_badge',
        store=False,  # Not stored in database, computed on-the-fly
    )
    
    @api.depends('name', 'badge_number')
    def _compute_full_name_with_badge(self):
        """Compute full name with badge number."""
        for guard in self:
            if guard.badge_number:
                guard.full_name_with_badge = f"{guard.name} ({guard.badge_number})"
            else:
                guard.full_name_with_badge = guard.name or ''
    
    # ========================================
    # Example 2: Stored Computed Field
    # ========================================
    
    total_certifications = fields.Integer(
        string='Total Certifications',
        compute='_compute_total_certifications',
        store=True,  # Stored in database for performance
    )
    
    @api.depends('certification_ids')
    def _compute_total_certifications(self):
        """Count total certifications."""
        for guard in self:
            guard.total_certifications = len(guard.certification_ids)
    
    # ========================================
    # Example 3: Complex Computed Field with Related Data
    # ========================================
    
    active_shifts_count = fields.Integer(
        string='Active Shifts',
        compute='_compute_active_shifts_count',
        store=False,
    )
    
    @api.depends('employee_id')  # Depends on employee_id to trigger recompute
    def _compute_active_shifts_count(self):
        """Count active shifts for this guard."""
        for guard in self:
            # Search for active shifts
            shifts = self.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('state', 'in', ['draft', 'confirmed', 'in_progress']),
            ])
            guard.active_shifts_count = len(shifts)
    
    # ========================================
    # Example 4: Computed Field with Date Calculations
    # ========================================
    
    days_until_cert_expiry = fields.Integer(
        string='Days Until Cert Expiry',
        compute='_compute_days_until_cert_expiry',
        store=False,
        help='Days until next certification expires'
    )
    
    next_expiring_cert_name = fields.Char(
        string='Next Expiring Certification',
        compute='_compute_days_until_cert_expiry',
        store=False,
    )
    
    @api.depends('certification_ids.expiry_date')
    def _compute_days_until_cert_expiry(self):
        """Calculate days until next certification expiry."""
        for guard in self:
            # Find certifications that haven't expired yet
            future_certs = guard.certification_ids.filtered(
                lambda c: c.expiry_date and c.expiry_date >= fields.Date.today()
            )
            
            if future_certs:
                # Sort by expiry date and get the earliest
                next_expiring = min(future_certs, key=lambda c: c.expiry_date)
                delta = next_expiring.expiry_date - fields.Date.today()
                guard.days_until_cert_expiry = delta.days
                guard.next_expiring_cert_name = next_expiring.name
            else:
                guard.days_until_cert_expiry = 0
                guard.next_expiring_cert_name = 'No valid certifications'
    
    # ========================================
    # Example 5: Computed Field with Aggregation
    # ========================================
    
    total_hours_this_month = fields.Float(
        string='Hours This Month',
        compute='_compute_total_hours_this_month',
        store=False,
    )
    
    def _compute_total_hours_this_month(self):
        """Calculate total hours worked this month."""
        for guard in self:
            # Get first and last day of current month
            today = datetime.today()
            first_day = today.replace(day=1)
            if today.month == 12:
                last_day = today.replace(day=31)
            else:
                last_day = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
            
            # Search for shifts in current month
            shifts = self.env['guard.shift'].search([
                ('guard_id', '=', guard.id),
                ('start_datetime', '>=', first_day),
                ('start_datetime', '<=', last_day),
                ('state', '=', 'completed'),
            ])
            
            # Sum up hours
            total_hours = sum(shift.duration for shift in shifts)
            guard.total_hours_this_month = total_hours
    
    # ========================================
    # Example 6: Selection Computed Field
    # ========================================
    
    performance_rating = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('average', 'Average'),
        ('poor', 'Poor'),
    ], string='Performance Rating', compute='_compute_performance_rating', store=True)
    
    @api.depends('total_hours_this_month', 'active_shifts_count')
    def _compute_performance_rating(self):
        """Compute performance rating based on various factors."""
        for guard in self:
            # Simple rating based on hours worked
            if guard.total_hours_this_month >= 160:
                guard.performance_rating = 'excellent'
            elif guard.total_hours_this_month >= 120:
                guard.performance_rating = 'good'
            elif guard.total_hours_this_month >= 80:
                guard.performance_rating = 'average'
            else:
                guard.performance_rating = 'poor'
    
    # ========================================
    # Example 7: Boolean Computed Field
    # ========================================
    
    has_expired_certifications = fields.Boolean(
        string='Has Expired Certifications',
        compute='_compute_has_expired_certifications',
        store=True,
        help='Whether this guard has any expired certifications'
    )
    
    @api.depends('certification_ids.expiry_date')
    def _compute_has_expired_certifications(self):
        """Check if guard has any expired certifications."""
        for guard in self:
            expired = guard.certification_ids.filtered(
                lambda c: c.expiry_date and c.expiry_date < fields.Date.today()
            )
            guard.has_expired_certifications = bool(expired)


class GuardShiftComputed(models.Model):
    """Examples of computed fields in Guard Shift."""
    
    _inherit = 'guard.shift'
    
    # ========================================
    # Example 8: Duration Calculation
    # ========================================
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Shift duration in hours'
    )
    
    duration_display = fields.Char(
        string='Duration',
        compute='_compute_duration',
        store=False,
        help='Human-readable duration (e.g., "8h 30m")'
    )
    
    @api.depends('start_datetime', 'end_datetime')
    def _compute_duration(self):
        """Calculate shift duration."""
        for shift in self:
            if shift.start_datetime and shift.end_datetime:
                delta = shift.end_datetime - shift.start_datetime
                hours = delta.total_seconds() / 3600
                shift.duration_hours = hours
                
                # Format as "Xh Ym"
                hours_int = int(hours)
                minutes = int((hours - hours_int) * 60)
                shift.duration_display = f"{hours_int}h {minutes}m"
            else:
                shift.duration_hours = 0.0
                shift.duration_display = '0h 0m'
    
    # ========================================
    # Example 9: Status Badge Color
    # ========================================
    
    status_color = fields.Selection([
        ('success', 'Green'),
        ('warning', 'Yellow'),
        ('danger', 'Red'),
        ('info', 'Blue'),
    ], string='Status Color', compute='_compute_status_color', store=False)
    
    @api.depends('state')
    def _compute_status_color(self):
        """Determine badge color based on state."""
        color_map = {
            'draft': 'info',
            'confirmed': 'success',
            'in_progress': 'warning',
            'completed': 'success',
            'cancelled': 'danger',
        }
        for shift in self:
            shift.status_color = color_map.get(shift.state, 'info')
    
    # ========================================
    # Example 10: Computed Field with Search Method
    # ========================================
    
    is_overtime = fields.Boolean(
        string='Overtime Shift',
        compute='_compute_is_overtime',
        search='_search_is_overtime',
        store=False,
    )
    
    @api.depends('duration_hours')
    def _compute_is_overtime(self):
        """Determine if shift qualifies as overtime (>8 hours)."""
        for shift in self:
            shift.is_overtime = shift.duration_hours > 8.0
    
    def _search_is_overtime(self, operator, value):
        """
        Enable searching for overtime shifts.
        
        Usage: self.env['guard.shift'].search([('is_overtime', '=', True)])
        """
        shifts = self.search([])
        overtime_shift_ids = shifts.filtered(lambda s: s.is_overtime).ids
        
        if (operator == '=' and value) or (operator == '!=' and not value):
            return [('id', 'in', overtime_shift_ids)]
        else:
            return [('id', 'not in', overtime_shift_ids)]
    
    # ========================================
    # Example 11: Related Computed Field
    # ========================================
    
    site_client_name = fields.Char(
        string='Client Name',
        compute='_compute_site_client_name',
        store=True,
        help='Client name from assigned site'
    )
    
    @api.depends('site_id.client_id.name')
    def _compute_site_client_name(self):
        """Get client name from site."""
        for shift in self:
            shift.site_client_name = shift.site_id.client_id.name if shift.site_id and shift.site_id.client_id else ''
    
    # NOTE: For simple related fields, you can also use:
    # site_client_name_simple = fields.Char(
    #     related='site_id.client_id.name',
    #     string='Client Name',
    #     store=True,
    # )


class IncidentReportComputed(models.Model):
    """Examples of computed fields in Incident Report."""
    
    _inherit = 'incident.report'
    
    # ========================================
    # Example 12: Time-based Computed Field
    # ========================================
    
    response_time_minutes = fields.Integer(
        string='Response Time (min)',
        compute='_compute_response_time',
        store=True,
        help='Minutes from creation to first response'
    )
    
    response_status = fields.Selection([
        ('excellent', 'Excellent (<15 min)'),
        ('good', 'Good (15-30 min)'),
        ('acceptable', 'Acceptable (30-60 min)'),
        ('poor', 'Poor (>60 min)'),
    ], string='Response Status', compute='_compute_response_time', store=True)
    
    @api.depends('create_date', 'date_submitted')
    def _compute_response_time(self):
        """Calculate incident response time."""
        for incident in self:
            if incident.create_date and incident.date_submitted:
                delta = incident.date_submitted - incident.create_date
                minutes = int(delta.total_seconds() / 60)
                incident.response_time_minutes = minutes
                
                # Determine status
                if minutes < 15:
                    incident.response_status = 'excellent'
                elif minutes < 30:
                    incident.response_status = 'good'
                elif minutes < 60:
                    incident.response_status = 'acceptable'
                else:
                    incident.response_status = 'poor'
            else:
                incident.response_time_minutes = 0
                incident.response_status = False
    
    # ========================================
    # Example 13: Multi-field Concatenation
    # ========================================
    
    incident_summary = fields.Text(
        string='Incident Summary',
        compute='_compute_incident_summary',
        store=False,
    )
    
    @api.depends('title', 'incident_type_id', 'priority', 'location', 'description')
    def _compute_incident_summary(self):
        """Generate incident summary text."""
        for incident in self:
            summary_parts = []
            
            if incident.title:
                summary_parts.append(f"Title: {incident.title}")
            if incident.incident_type_id:
                summary_parts.append(f"Type: {incident.incident_type_id.name}")
            if incident.priority:
                summary_parts.append(f"Priority: {dict(incident._fields['priority'].selection).get(incident.priority)}")
            if incident.location:
                summary_parts.append(f"Location: {incident.location}")
            if incident.description:
                summary_parts.append(f"Description: {incident.description[:100]}...")
            
            incident.incident_summary = "\n".join(summary_parts)


# ========================================
# TIPS FOR COMPUTED FIELDS
# ========================================

"""
1. ALWAYS use @api.depends():
   - List all fields that trigger recomputation
   - Include related fields (e.g., 'field_id.subfield')
   - Missing dependencies = stale data!

2. Store vs Not Store:
   - store=True: Saves in database, better performance for reads
   - store=False: Computed on-demand, always up-to-date
   - Use store=True for frequently accessed fields
   - Use store=False for rarely accessed or complex calculations

3. Performance Considerations:
   - Avoid expensive operations in compute methods
   - Don't make database queries in loops
   - Use search_count() instead of len(search())
   - Consider using SQL queries for complex aggregations

4. Batch Processing:
   - Compute methods receive recordsets (multiple records)
   - Always iterate: for record in self:
   - Don't assume self is a single record

5. Inverse and Search:
   - Add inverse= for writable computed fields
   - Add search= to enable searching on computed fields
   - See Example 10 above

6. Common Pitfalls:
   - Forgetting @api.depends() -> field doesn't update
   - Missing 'store=True' on searchable fields
   - Expensive queries in compute methods -> slow performance
   - Not handling empty/False values -> errors

7. Testing Computed Fields:
   # Test in Python code
   guard = self.env['guard.profile'].browse(guard_id)
   print(guard.total_certifications)  # Triggers compute

   # Force recomputation
   guard._compute_total_certifications()

"""

