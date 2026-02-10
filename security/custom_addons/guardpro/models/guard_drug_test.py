# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class GuardDrugTest(models.Model):
    """Drug and alcohol testing logs"""
    _name = 'guard.drug.test'
    _description = 'Guard Drug/Alcohol Test'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'test_date desc, guard_id'
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
        string='Test Reference',
        required=True,
        copy=False,
        default=lambda self: _('New'),
        tracking=True
    )
    
    # Test Details
    test_type = fields.Selection([
        ('pre_employment', 'Pre-Employment'),
        ('random', 'Random'),
        ('post_incident', 'Post-Incident'),
        ('reasonable_suspicion', 'Reasonable Suspicion'),
        ('return_to_duty', 'Return to Duty'),
        ('follow_up', 'Follow-Up'),
        ('annual', 'Annual'),
        ('other', 'Other')
    ], string='Test Type', required=True, default='random', tracking=True)
    
    test_category = fields.Selection([
        ('drug', 'Drug Test'),
        ('alcohol', 'Alcohol Test'),
        ('both', 'Drug & Alcohol Test')
    ], string='Test Category', required=True, default='drug', tracking=True)
    
    test_date = fields.Datetime(
        string='Test Date & Time',
        required=True,
        default=fields.Datetime.now,
        tracking=True
    )
    
    collection_method = fields.Selection([
        ('urine', 'Urine Sample'),
        ('blood', 'Blood Sample'),
        ('saliva', 'Saliva/Oral Fluid'),
        ('breath', 'Breath (Alcohol)'),
        ('hair', 'Hair Follicle'),
        ('other', 'Other')
    ], string='Collection Method', required=True, default='urine', tracking=True)
    
    # Testing Facility
    testing_facility = fields.Char(
        string='Testing Facility',
        required=True,
        tracking=True
    )
    
    facility_contact = fields.Char(string='Facility Contact')
    
    lab_name = fields.Char(
        string='Laboratory',
        help='Lab that performed the analysis'
    )
    
    # Results
    result_date = fields.Date(
        string='Result Date',
        tracking=True
    )
    
    status = fields.Selection([
        ('scheduled', 'Scheduled'),
        ('sample_collected', 'Sample Collected'),
        ('pending', 'Pending Results'),
        ('negative', 'Negative (Pass)'),
        ('positive', 'Positive (Fail)'),
        ('dilute', 'Dilute - Retest Required'),
        ('cancelled', 'Cancelled'),
        ('refused', 'Refused by Guard')
    ], string='Status', default='scheduled', required=True, tracking=True)
    
    substances_tested = fields.Text(
        string='Substances Tested',
        help='List of substances tested (e.g., THC, Cocaine, Amphetamines, etc.)'
    )
    
    positive_substances = fields.Text(
        string='Positive Results',
        help='Substances that tested positive'
    )
    
    bac_level = fields.Float(
        string='BAC Level (%)',
        help='Blood Alcohol Content level for alcohol tests',
        digits=(5, 3)
    )
    
    # Chain of Custody
    collector_name = fields.Char(
        string='Sample Collector',
        help='Person who collected the sample'
    )
    
    witness_name = fields.Char(
        string='Witness',
        help='Witness present during collection'
    )
    
    chain_of_custody_maintained = fields.Boolean(
        string='Chain of Custody Maintained',
        default=True,
        tracking=True
    )
    
    # Medical Review Officer
    mro_name = fields.Char(
        string='MRO Name',
        help='Medical Review Officer who reviewed results'
    )
    
    mro_review_date = fields.Date(string='MRO Review Date')
    
    mro_notes = fields.Text(string='MRO Notes')
    
    # Actions Taken
    action_taken = fields.Selection([
        ('none', 'No Action Required'),
        ('counseling', 'Counseling'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination'),
        ('retest', 'Retest Scheduled'),
        ('treatment_referral', 'Treatment Program Referral'),
        ('other', 'Other')
    ], string='Action Taken', tracking=True)
    
    action_notes = fields.Text(string='Action Notes')
    
    # Cost
    cost = fields.Monetary(
        string='Cost',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
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
    
    @api.depends('guard_id', 'test_type', 'test_date')
    def _compute_display_name(self):
        """Compute display name"""
        for record in self:
            if record.guard_id:
                test_type_name = dict(self._fields['test_type'].selection).get(record.test_type, '')
                record.display_name = f"{record.guard_id.name} - {test_type_name} ({fields.Date.to_string(record.test_date)})"
            else:
                record.display_name = record.reference_number or 'New Drug Test'
    
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
                    'guard.drug.test'
                ) or _('New')
        return super().create(vals_list)
    
    @api.constrains('test_date', 'result_date')
    def _check_dates(self):
        """Validate dates"""
        for record in self:
            if record.result_date and record.test_date:
                if record.result_date < record.test_date.date():
                    raise ValidationError(_('Result date cannot be before test date!'))
    
    @api.constrains('bac_level')
    def _check_bac_level(self):
        """Validate BAC level"""
        for record in self:
            if record.bac_level < 0 or record.bac_level > 1:
                raise ValidationError(_('BAC level must be between 0 and 1 (0-100%)'))
    
    def action_mark_negative(self):
        """Mark test as negative (pass)"""
        self.ensure_one()
        self.write({
            'status': 'negative',
            'result_date': fields.Date.today(),
            'action_taken': 'none'
        })
        self.message_post(
            body=_('Test result: NEGATIVE (Pass)'),
            subtype_xmlid='mail.mt_note'
        )
    
    def action_mark_positive(self):
        """Mark test as positive (fail)"""
        self.ensure_one()
        self.write({
            'status': 'positive',
            'result_date': fields.Date.today()
        })
        self.message_post(
            body=_('Test result: POSITIVE (Fail) - Action Required!'),
            subtype_xmlid='mail.mt_comment'
        )
        # Create activity for supervisor
        self.activity_schedule(
            'mail.mail_activity_data_warning',
            summary=_('Positive Drug Test - Action Required'),
            note=_('Guard %s tested positive. Immediate action required!') % self.guard_id.name,
            user_id=self.guard_id.supervisor_id.id if self.guard_id.supervisor_id else self.env.user.id
        )
    
    def action_schedule_retest(self):
        """Schedule a retest"""
        self.ensure_one()
        self.write({
            'status': 'dilute',
            'action_taken': 'retest'
        })
        self.message_post(
            body=_('Retest scheduled'),
            subtype_xmlid='mail.mt_note'
        )
    
    def action_view_attachments(self):
        """View attachments"""
        self.ensure_one()
        return {
            'name': _('Test Documents'),
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
    def _cron_send_random_test_notifications(self):
        """Send notifications for scheduled random tests"""
        # This could be used to notify guards selected for random testing
        # Implementation depends on your random selection process
        return True

