# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardVaccination(models.Model):
    """Guard vaccination records"""
    _name = 'guard.vaccination'
    _description = 'Guard Vaccination Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'vaccination_date desc, guard_id'
    _rec_name = 'display_name'

    # Basic Information
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    reference_number = fields.Char(
        string='Record Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True
    )
    
    # Vaccine Details
    vaccine_type = fields.Selection([
        ('covid19', 'COVID-19'),
        ('hepatitis_b', 'Hepatitis B'),
        ('influenza', 'Influenza (Flu)'),
        ('tetanus', 'Tetanus'),
        ('measles', 'Measles'),
        ('mumps', 'Mumps'),
        ('rubella', 'Rubella'),
        ('tuberculosis', 'Tuberculosis (TB)'),
        ('yellow_fever', 'Yellow Fever'),
        ('other', 'Other')
    ], string='Vaccine Type', required=True, tracking=True)
    
    vaccine_name = fields.Char(
        string='Vaccine Name',
        help='Brand/manufacturer name (e.g., Pfizer, Moderna)'
    )
    
    other_vaccine = fields.Char(
        string='Other Vaccine',
        help='Specify if vaccine type is "Other"'
    )
    
    # Dosage Information
    dose_number = fields.Integer(
        string='Dose Number',
        default=1,
        help='Which dose in the series (1st, 2nd, booster, etc.)'
    )
    
    total_doses_required = fields.Integer(
        string='Total Doses Required',
        default=1,
        help='Total doses needed for full vaccination'
    )
    
    is_series_complete = fields.Boolean(
        string='Series Complete',
        compute='_compute_series_complete',
        store=True,
        help='All required doses completed'
    )
    
    lot_number = fields.Char(
        string='Lot/Batch Number',
        help='Vaccine lot/batch number for tracking'
    )
    
    # Dates
    vaccination_date = fields.Date(
        string='Vaccination Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    
    expiry_date = fields.Date(
        string='Immunity Expiry Date',
        help='When immunity expires or booster is needed',
        tracking=True
    )
    
    next_dose_date = fields.Date(
        string='Next Dose Due',
        help='Scheduled date for next dose (if applicable)'
    )
    
    # Administration Details
    administered_by = fields.Char(
        string='Administered By',
        help='Healthcare provider who administered the vaccine'
    )
    
    facility_name = fields.Char(
        string='Facility Name',
        help='Hospital, clinic, or pharmacy where vaccine was given'
    )
    
    facility_address = fields.Text(string='Facility Address')
    
    site_of_administration = fields.Selection([
        ('left_arm', 'Left Arm'),
        ('right_arm', 'Right Arm'),
        ('left_thigh', 'Left Thigh'),
        ('right_thigh', 'Right Thigh'),
        ('other', 'Other')
    ], string='Site of Administration', default='left_arm')
    
    # Status and Verification
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('administered', 'Administered'),
        ('verified', 'Verified'),
        ('expired', 'Expired'),
        ('declined', 'Declined by Guard'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='scheduled', required=True, tracking=True)
    
    verified_by_id = fields.Many2one(
        'res.users',
        string='Verified By',
        tracking=True
    )
    
    verification_date = fields.Date(string='Verification Date')
    
    verification_notes = fields.Text(string='Verification Notes')
    
    # Compliance
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=False,
        help='Is this vaccination mandatory for employment?'
    )
    
    exemption_granted = fields.Boolean(
        string='Exemption Granted',
        tracking=True,
        help='Medical or religious exemption granted'
    )
    
    exemption_type = fields.Selection([
        ('medical', 'Medical Exemption'),
        ('religious', 'Religious Exemption'),
        ('philosophical', 'Philosophical Exemption'),
        ('other', 'Other')
    ], string='Exemption Type')
    
    exemption_reason = fields.Text(string='Exemption Reason')
    
    exemption_expiry = fields.Date(
        string='Exemption Valid Until',
        help='Some exemptions may have expiry dates'
    )
    
    # Side Effects/Reactions
    adverse_reaction = fields.Boolean(
        string='Adverse Reaction',
        tracking=True,
        help='Did guard experience adverse reaction?'
    )
    
    reaction_details = fields.Text(
        string='Reaction Details',
        help='Description of any adverse reactions'
    )
    
    medical_attention_required = fields.Boolean(
        string='Medical Attention Required',
        help='Did reaction require medical attention?'
    )
    
    # Related Fields
    guard_name = fields.Char(
        related='guard_id.name',
        string='Guard Name',
        store=True,
        readonly=True
    )
    
    guard_employee_number = fields.Char(
        related='guard_id.badge_number',
        string='Employee Number',
        readonly=True
    )
    
    # Attachments
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count'
    )
    
    notes = fields.Text(string='Additional Notes')
    
    active = fields.Boolean(default=True)
    
    @api.depends('guard_id', 'vaccine_type', 'vaccination_date')
    def _compute_display_name(self):
        """Compute display name"""
        for record in self:
            if record.guard_id:
                vaccine_name = dict(self._fields['vaccine_type'].selection).get(record.vaccine_type, '')
                if record.vaccine_type == 'other' and record.other_vaccine:
                    vaccine_name = record.other_vaccine
                record.display_name = f"{record.guard_id.name} - {vaccine_name} (Dose {record.dose_number})"
            else:
                record.display_name = record.reference_number or 'New Vaccination Record'
    
    @api.depends('dose_number', 'total_doses_required')
    def _compute_series_complete(self):
        """Check if vaccination series is complete"""
        for record in self:
            record.is_series_complete = record.dose_number >= record.total_doses_required
    
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = self.env['ir.attachment'].search_count([
                ('res_model', '=', self._name),
                ('res_id', '=', record.id)
            ])
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference number on create"""
        for vals in vals_list:
            if vals.get('reference_number', _('New')) == _('New'):
                vals['reference_number'] = self.env['ir.sequence'].next_by_code(
                    'guard.vaccination'
                ) or _('New')
        return super().create(vals_list)
    
    @api.constrains('vaccination_date', 'expiry_date', 'next_dose_date')
    def _check_dates(self):
        """Validate dates"""
        for record in self:
            if record.expiry_date and record.vaccination_date:
                if record.expiry_date <= record.vaccination_date:
                    raise ValidationError(_('Expiry date must be after vaccination date!'))
            if record.next_dose_date and record.vaccination_date:
                if record.next_dose_date <= record.vaccination_date:
                    raise ValidationError(_('Next dose date must be after vaccination date!'))
    
    @api.constrains('dose_number', 'total_doses_required')
    def _check_doses(self):
        """Validate dose numbers"""
        for record in self:
            if record.dose_number < 1:
                raise ValidationError(_('Dose number must be at least 1!'))
            if record.total_doses_required < 1:
                raise ValidationError(_('Total doses required must be at least 1!'))
            if record.dose_number > record.total_doses_required:
                raise ValidationError(_('Dose number cannot exceed total doses required!'))
    
    def action_verify(self):
        """Verify vaccination record"""
        self.ensure_one()
        self.write({
            'status': 'verified',
            'verified_by_id': self.env.user.id,
            'verification_date': fields.Date.today()
        })
        self.message_post(
            body=_('Vaccination record verified by %s') % self.env.user.name,
            subtype_xmlid='mail.mt_note'
        )
    
    def action_report_reaction(self):
        """Report adverse reaction"""
        self.ensure_one()
        self.adverse_reaction = True
        self.message_post(
            body=_('Adverse reaction reported'),
            subtype_xmlid='mail.mt_comment'
        )
        # Create activity for supervisor
        self.activity_schedule(
            'mail.mail_activity_data_warning',
            summary=_('Adverse Vaccine Reaction Reported'),
            note=_('Guard %s reported adverse reaction to %s vaccine') % (
                self.guard_id.name,
                dict(self._fields['vaccine_type'].selection).get(self.vaccine_type, '')
            ),
            user_id=self.guard_id.supervisor_id.id if self.guard_id.supervisor_id else self.env.user.id
        )
    
    def action_schedule_next_dose(self):
        """Create record for next dose"""
        self.ensure_one()
        if self.is_series_complete:
            raise ValidationError(_('Vaccination series is already complete!'))
        
        next_dose = self.copy({
            'dose_number': self.dose_number + 1,
            'vaccination_date': self.next_dose_date or fields.Date.today(),
            'status': 'scheduled',
            'reference_number': _('New')
        })
        
        self.message_post(
            body=_('Next dose scheduled: %s') % next_dose.display_name,
            subtype_xmlid='mail.mt_note'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': next_dose.id,
            'view_mode': 'form',
            'target': 'current'
        }
    
    def action_view_attachments(self):
        """View attachments"""
        self.ensure_one()
        return {
            'name': _('Vaccination Documents'),
            'type': 'ir.actions.act_window',
            'res_model': 'ir.attachment',
            'view_mode': 'list,form',
            'domain': [('res_model', '=', self._name), ('res_id', '=', self.id)],
            'context': {
                'default_res_model': self._name,
                'default_res_id': self.id
            }
        }
    
    @api.model
    def _cron_check_expiring_vaccinations(self):
        """Check for expiring vaccinations and upcoming doses"""
        today = fields.Date.today()
        
        # Check expiring immunity
        expiring = self.search([
            ('status', '=', 'verified'),
            ('expiry_date', '!=', False),
            ('expiry_date', '<=', fields.Date.add(today, days=30)),
            ('expiry_date', '>=', today)
        ])
        
        for vaccination in expiring:
            vaccination.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Vaccination Immunity Expiring'),
                note=_('Vaccination immunity expires on %s. Booster may be needed.') % vaccination.expiry_date,
                user_id=vaccination.guard_id.user_id.id if vaccination.guard_id.user_id else self.env.user.id
            )
        
        # Mark expired vaccinations
        expired = self.search([
            ('status', '=', 'verified'),
            ('expiry_date', '<', today)
        ])
        
        for vaccination in expired:
            vaccination.status = 'expired'
            vaccination.message_post(
                body=_('Vaccination immunity has expired!'),
                subtype_xmlid='mail.mt_comment'
            )
        
        # Check upcoming next doses
        upcoming_doses = self.search([
            ('status', '=', 'verified'),
            ('next_dose_date', '!=', False),
            ('next_dose_date', '<=', fields.Date.add(today, days=7)),
            ('next_dose_date', '>=', today),
            ('is_series_complete', '=', False)
        ])
        
        for vaccination in upcoming_doses:
            vaccination.activity_schedule(
                'mail.mail_activity_data_todo',
                summary=_('Next Vaccine Dose Due'),
                note=_('Next dose of %s due on %s') % (
                    dict(self._fields['vaccine_type'].selection).get(vaccination.vaccine_type, ''),
                    vaccination.next_dose_date
                ),
                user_id=vaccination.guard_id.user_id.id if vaccination.guard_id.user_id else self.env.user.id
            )
        
        return True

