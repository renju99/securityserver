# -*- coding: utf-8 -*-
"""Incident Investigation Witness Model - Witness statement management."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationWitness(models.Model):
    """Investigation Witness Management"""
    
    _name = 'incident.investigation.witness'
    _description = 'Investigation Witness'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'interview_date desc, id desc'
    _rec_name = 'witness_name'
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # Witness Information
    witness_name = fields.Char(
        string='Witness Name',
        required=True,
        tracking=True
    )
    witness_type = fields.Selection([
        ('employee', 'Employee'),
        ('guard', 'Security Guard'),
        ('contractor', 'Contractor'),
        ('visitor', 'Visitor'),
        ('resident', 'Resident'),
        ('client', 'Client Representative'),
        ('expert', 'Expert Witness'),
        ('other', 'Other')
    ], string='Witness Type', required=True, tracking=True)
    
    contact_info = fields.Text(
        string='Contact Information',
        help='Phone, email, address'
    )
    position = fields.Char(
        string='Position/Title',
        help='Job title or role'
    )
    company = fields.Char(
        string='Company/Organization'
    )
    
    # Interview Details
    interview_date = fields.Datetime(
        string='Interview Date/Time',
        tracking=True
    )
    interview_location = fields.Char(
        string='Interview Location',
        tracking=True
    )
    interviewer_id = fields.Many2one(
        'res.users',
        string='Interviewer',
        tracking=True,
        help='Person who conducted interview'
    )
    interview_method = fields.Selection([
        ('in_person', 'In Person'),
        ('phone', 'Phone'),
        ('video', 'Video Call'),
        ('written', 'Written Statement'),
        ('email', 'Email')
    ], string='Interview Method', tracking=True)
    
    # Statement
    statement = fields.Html(
        string='Witness Statement',
        required=True,
        help='Complete witness statement or testimony'
    )
    statement_verified = fields.Boolean(
        string='Statement Verified',
        default=False,
        tracking=True,
        help='Witness has reviewed and verified statement'
    )
    verification_date = fields.Date(
        string='Verification Date'
    )
    
    # Relevance
    relevance = fields.Selection([
        ('critical', 'Critical'),
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Relevance', default='medium', tracking=True,
       help='Importance of witness testimony')
    
    credibility_assessment = fields.Selection([
        ('high', 'High Credibility'),
        ('medium', 'Medium Credibility'),
        ('low', 'Low Credibility'),
        ('questionable', 'Questionable')
    ], string='Credibility Assessment', tracking=True)
    
    key_points = fields.Text(
        string='Key Points',
        help='Summary of important points from statement'
    )
    
    # Follow-up
    follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False,
        tracking=True
    )
    follow_up_notes = fields.Text(
        string='Follow-up Notes',
        help='Additional questions or follow-up needed'
    )
    follow_up_completed = fields.Boolean(
        string='Follow-up Completed',
        default=False
    )
    
    # Attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'investigation_witness_attachment_rel',
        'witness_id',
        'attachment_id',
        string='Attachments',
        help='Signed statements, recordings, etc.'
    )
    
    # Confidentiality
    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        tracking=True,
        help='Mark witness statement as confidential'
    )
    
    notes = fields.Text(
        string='Internal Notes',
        help='Investigation notes not shared with witness'
    )
    
    # Color for kanban
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('relevance', 'statement_verified')
    def _compute_color(self):
        """Set color based on relevance"""
        for record in self:
            if not record.statement_verified:
                record.color = 7  # Grey - not verified
            elif record.relevance == 'critical':
                record.color = 1  # Dark red
            elif record.relevance == 'high':
                record.color = 2  # Red
            elif record.relevance == 'medium':
                record.color = 9  # Orange
            else:
                record.color = 3  # Yellow
    
    @api.model_create_multi
    def create(self, vals_list):
        """Create witness record and timeline entry"""
        records = super().create(vals_list)
        
        for record in records:
            # Add timeline entry to investigation
            if record.investigation_id:
                record.investigation_id._create_timeline_entry(
                    'witness_interviewed',
                    _('Witness statement recorded: %s') % record.witness_name
                )
        
        return records
    
    def action_verify_statement(self):
        """Mark statement as verified"""
        self.ensure_one()
        
        self.write({
            'statement_verified': True,
            'verification_date': fields.Date.today()
        })
        
        self.message_post(
            body=_('Statement verified by %s') % self.env.user.name,
            message_type='notification'
        )
        
        return True
    
    def action_request_follow_up(self):
        """Request follow-up interview"""
        self.ensure_one()
        
        self.write({'follow_up_required': True})
        
        # Create activity
        self.activity_schedule(
            'mail.mail_activity_data_todo',
            summary=_('Follow-up Interview: %s') % self.witness_name,
            note=self.follow_up_notes or _('Follow-up interview required'),
            user_id=self.interviewer_id.id or self.env.user.id
        )
        
        return True

