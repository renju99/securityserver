# -*- coding: utf-8 -*-
"""Incident Investigation Evidence Model - Evidence collection and tracking."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationEvidence(models.Model):
    """Investigation Evidence Management"""
    
    _name = 'incident.investigation.evidence'
    _description = 'Investigation Evidence'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'collection_date desc, id desc'
    _rec_name = 'display_name'
    
    display_name = fields.Char(
        string='Name',
        compute='_compute_display_name',
        store=True
    )
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    # Evidence Details
    evidence_number = fields.Char(
        string='Evidence Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True
    )
    
    evidence_type = fields.Selection([
        ('physical', 'Physical Evidence'),
        ('document', 'Document/Record'),
        ('photo', 'Photograph'),
        ('video', 'Video Recording'),
        ('audio', 'Audio Recording'),
        ('digital', 'Digital Evidence'),
        ('testimony', 'Testimony/Statement'),
        ('forensic', 'Forensic Evidence'),
        ('other', 'Other')
    ], string='Evidence Type', required=True, tracking=True)
    
    description = fields.Text(
        string='Description',
        required=True,
        tracking=True,
        help='Detailed description of evidence'
    )
    
    # Collection Information
    collection_date = fields.Datetime(
        string='Collection Date/Time',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    collected_by_id = fields.Many2one(
        'res.users',
        string='Collected By',
        default=lambda self: self.env.user,
        required=True,
        tracking=True
    )
    collection_location = fields.Char(
        string='Collection Location',
        tracking=True,
        help='Where evidence was collected'
    )
    collection_method = fields.Text(
        string='Collection Method',
        help='How evidence was collected'
    )
    
    # Chain of Custody
    custodian_id = fields.Many2one(
        'res.users',
        string='Current Custodian',
        default=lambda self: self.env.user,
        tracking=True,
        help='Person currently responsible for evidence'
    )
    storage_location = fields.Char(
        string='Storage Location',
        tracking=True,
        help='Where evidence is stored'
    )
    chain_of_custody_ids = fields.One2many(
        'incident.investigation.evidence.custody',
        'evidence_id',
        string='Chain of Custody'
    )
    
    # Status
    status = fields.Selection([
        ('collected', 'Collected'),
        ('analyzed', 'Analyzed'),
        ('stored', 'Stored'),
        ('returned', 'Returned'),
        ('disposed', 'Disposed')
    ], string='Status', default='collected', required=True, tracking=True)
    
    # Analysis
    analysis_required = fields.Boolean(
        string='Analysis Required',
        default=False,
        tracking=True
    )
    analysis_type = fields.Char(
        string='Analysis Type',
        help='Type of analysis needed'
    )
    analyzed_by = fields.Char(
        string='Analyzed By',
        help='Person/lab who analyzed evidence'
    )
    analysis_date = fields.Date(
        string='Analysis Date'
    )
    analysis_results = fields.Text(
        string='Analysis Results',
        help='Results of evidence analysis'
    )
    
    # Significance
    relevance = fields.Selection([
        ('high', 'High'),
        ('medium', 'Medium'),
        ('low', 'Low')
    ], string='Relevance', default='medium', tracking=True,
       help='Relevance to investigation')
    
    significance_notes = fields.Text(
        string='Significance Notes',
        help='Why this evidence is significant'
    )
    
    # Files & Attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'investigation_evidence_attachment_rel',
        'evidence_id',
        'attachment_id',
        string='Attachments',
        help='Photos, documents, or other files related to evidence'
    )
    attachment_count = fields.Integer(
        string='Number of Attachments',
        compute='_compute_attachment_count'
    )
    
    # Tags
    tag_ids = fields.Many2many(
        'incident.investigation.evidence.tag',
        'inv_evidence_tag_rel',
        'evidence_id',
        'tag_id',
        string='Tags'
    )
    
    notes = fields.Text(
        string='Additional Notes'
    )
    
    # Color for kanban
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('evidence_number', 'evidence_type')
    def _compute_display_name(self):
        """Generate display name"""
        for record in self:
            type_label = dict(record._fields['evidence_type'].selection).get(
                record.evidence_type, record.evidence_type
            )
            record.display_name = '%s - %s' % (record.evidence_number, type_label)
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    @api.depends('relevance', 'status')
    def _compute_color(self):
        """Set color based on relevance and status"""
        for record in self:
            if record.status == 'disposed':
                record.color = 8  # Grey
            elif record.relevance == 'high':
                record.color = 2  # Red
            elif record.relevance == 'medium':
                record.color = 9  # Orange
            else:
                record.color = 3  # Yellow
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate evidence number sequence"""
        for vals in vals_list:
            if vals.get('evidence_number', _('New')) == _('New'):
                vals['evidence_number'] = self.env['ir.sequence'].next_by_code(
                    'incident.investigation.evidence'
                ) or _('New')
        
        records = super().create(vals_list)
        
        # Create initial chain of custody entry
        for record in records:
            record._create_custody_entry('collected', _('Evidence collected'))
            
            # Add timeline entry to investigation
            if record.investigation_id:
                record.investigation_id._create_timeline_entry(
                    'evidence_added',
                    _('Evidence added: %s') % record.display_name
                )
        
        return records
    
    def action_analyze(self):
        """Mark evidence as analyzed"""
        self.ensure_one()
        
        if not self.analysis_results:
            raise ValidationError(_('Please provide analysis results'))
        
        self.write({
            'status': 'analyzed',
            'analysis_date': fields.Date.today()
        })
        
        self._create_custody_entry('analyzed', _('Evidence analyzed'))
        
        return True
    
    def action_store(self):
        """Mark evidence as stored"""
        self.ensure_one()
        
        if not self.storage_location:
            raise ValidationError(_('Please specify storage location'))
        
        self.write({'status': 'stored'})
        self._create_custody_entry('stored', _('Evidence stored'))
        
        return True
    
    def action_transfer_custody(self):
        """Open wizard to transfer custody"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Transfer Custody'),
            'res_model': 'incident.investigation.evidence.custody.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_evidence_id': self.id}
        }
    
    def _create_custody_entry(self, entry_type, notes=''):
        """Helper to create chain of custody entry"""
        self.ensure_one()
        
        self.env['incident.investigation.evidence.custody'].create({
            'evidence_id': self.id,
            'entry_type': entry_type,
            'from_user_id': self.custodian_id.id,
            'to_user_id': self.env.user.id,
            'notes': notes,
            'timestamp': fields.Datetime.now()
        })


class IncidentInvestigationEvidenceCustody(models.Model):
    """Chain of Custody Tracking"""
    
    _name = 'incident.investigation.evidence.custody'
    _description = 'Evidence Chain of Custody'
    _order = 'timestamp desc'
    
    evidence_id = fields.Many2one(
        'incident.investigation.evidence',
        string='Evidence',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    timestamp = fields.Datetime(
        string='Date/Time',
        default=fields.Datetime.now,
        required=True
    )
    
    entry_type = fields.Selection([
        ('collected', 'Collected'),
        ('transferred', 'Transferred'),
        ('analyzed', 'Analyzed'),
        ('stored', 'Stored'),
        ('accessed', 'Accessed'),
        ('returned', 'Returned'),
        ('disposed', 'Disposed')
    ], string='Entry Type', required=True)
    
    from_user_id = fields.Many2one(
        'res.users',
        string='From'
    )
    to_user_id = fields.Many2one(
        'res.users',
        string='To',
        required=True
    )
    
    location = fields.Char(
        string='Location'
    )
    
    notes = fields.Text(
        string='Notes'
    )


class IncidentInvestigationEvidenceTag(models.Model):
    """Evidence Tags"""
    
    _name = 'incident.investigation.evidence.tag'
    _description = 'Evidence Tag'
    _order = 'name'
    
    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True
    )
    color = fields.Integer(
        string='Color Index'
    )

