# -*- coding: utf-8 -*-
"""Knowledge Base & SOPs Repository - UAE/SIRA Standards."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class KnowledgeArticle(models.Model):
    """Knowledge base articles and SOPs with UAE/SIRA standards."""
    
    _name = 'knowledge.article'
    _description = 'Knowledge Article'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Title',
        required=True,
        translate=True,
        tracking=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    article_type = fields.Selection([
        ('sop', 'Standard Operating Procedure'),
        ('guide', 'Guide / How-To'),
        ('policy', 'Policy'),
        ('faq', 'FAQ'),
        ('training', 'Training Material'),
        ('regulation', 'UAE Regulation'),
        ('sira', 'SIRA Certification')
    ], string='Type', required=True, default='guide', tracking=True)
    
    category_id = fields.Many2one(
        'knowledge.category',
        string='Category',
        tracking=True
    )
    
    content = fields.Html(
        string='Content',
        translate=True,
        required=True
    )
    
    summary = fields.Text(
        string='Summary',
        translate=True,
        help='Brief overview of the article'
    )
    
    # UAE/SIRA Specific Fields
    is_uae_standard = fields.Boolean(
        string='UAE Standard',
        default=False,
        help='Based on UAE government regulations'
    )
    
    is_sira_requirement = fields.Boolean(
        string='SIRA Requirement',
        default=False,
        help='Required by SIRA certification'
    )
    
    sira_reference = fields.Char(
        string='SIRA Reference',
        help='SIRA regulation reference number'
    )
    
    compliance_level = fields.Selection([
        ('mandatory', 'Mandatory'),
        ('recommended', 'Recommended'),
        ('optional', 'Optional')
    ], string='Compliance Level', default='recommended')
    
    applicable_roles = fields.Many2many(
        'knowledge.guard.role',
        string='Applicable Guard Roles',
        help='Which guard roles this applies to'
    )
    
    # Versioning
    version = fields.Char(
        string='Version',
        default='1.0',
        tracking=True
    )
    
    revision_date = fields.Date(
        string='Last Revised',
        default=fields.Date.today,
        tracking=True
    )
    
    effective_date = fields.Date(
        string='Effective Date',
        help='When this article/SOP becomes effective'
    )
    
    expiry_date = fields.Date(
        string='Review/Expiry Date',
        help='When this article should be reviewed or expires'
    )
    
    # Site-specific
    site_ids = fields.Many2many(
        'client.site',
        string='Applicable Sites',
        help='Leave empty for all sites'
    )
    
    # Attachments
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments'
    )
    
    # Tags
    tag_ids = fields.Many2many(
        'knowledge.tag',
        string='Tags'
    )
    
    # Related SOPs
    sop_ids = fields.One2many(
        'knowledge.sop',
        'article_id',
        string='Related Procedures'
    )
    
    sop_count = fields.Integer(
        string='# Procedures',
        compute='_compute_sop_count'
    )
    
    # Access
    is_published = fields.Boolean(
        string='Published',
        default=True,
        tracking=True
    )
    
    access_level = fields.Selection([
        ('all', 'All Guards'),
        ('supervisors', 'Supervisors & Above'),
        ('managers', 'Managers & Above'),
        ('admin', 'Administrators Only')
    ], string='Access Level', default='all', required=True)
    
    # Statistics
    view_count = fields.Integer(
        string='Views',
        readonly=True,
        default=0
    )
    
    acknowledgment_required = fields.Boolean(
        string='Require Acknowledgment',
        help='Guards must confirm they have read and understood this article'
    )
    
    acknowledgment_ids = fields.One2many(
        'knowledge.acknowledgment',
        'article_id',
        string='Acknowledgments'
    )
    
    acknowledgment_count = fields.Integer(
        string='# Acknowledgments',
        compute='_compute_acknowledgment_count'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('acknowledgment_ids')
    def _compute_acknowledgment_count(self):
        """Count acknowledgments."""
        for record in self:
            record.acknowledgment_count = len(record.acknowledgment_ids)
    
    @api.depends('sop_ids')
    def _compute_sop_count(self):
        """Count related SOPs."""
        for record in self:
            record.sop_count = len(record.sop_ids)
    
    def action_view_article(self):
        """Increment view count."""
        self.sudo().write({'view_count': self.view_count + 1})
    
    def action_new_version(self):
        """Create a new version."""
        self.ensure_one()
        
        # Parse version number
        try:
            parts = self.version.split('.')
            major = int(parts[0])
            minor = int(parts[1]) if len(parts) > 1 else 0
            new_version = f"{major}.{minor + 1}"
        except:
            new_version = "1.1"
        
        self.write({
            'version': new_version,
            'revision_date': fields.Date.today()
        })
        
        # Notify users who have acknowledged previous version
        if self.acknowledgment_required:
            self._reset_acknowledgments()
    
    def _reset_acknowledgments(self):
        """Reset acknowledgments for new version."""
        self.acknowledgment_ids.write({'needs_reacknowledgment': True})
    
    def action_view_sops(self):
        """View related SOPs."""
        self.ensure_one()
        return {
            'name': _('Procedures - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'knowledge.sop',
            'view_mode': 'list,form',
            'domain': [('article_id', '=', self.id)],
            'context': {'default_article_id': self.id}
        }


class KnowledgeCategory(models.Model):
    """Knowledge categories."""
    
    _name = 'knowledge.category'
    _description = 'Knowledge Category'
    _order = 'name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True
    )
    
    parent_id = fields.Many2one(
        'knowledge.category',
        string='Parent Category'
    )
    
    color = fields.Integer(
        string='Color Index'
    )
    
    article_count = fields.Integer(
        string='Articles',
        compute='_compute_article_count'
    )
    
    def _compute_article_count(self):
        """Count articles in category."""
        for record in self:
            record.article_count = self.env['knowledge.article'].search_count([
                ('category_id', '=', record.id)
            ])


class KnowledgeTag(models.Model):
    """Knowledge tags."""
    
    _name = 'knowledge.tag'
    _description = 'Knowledge Tag'
    _order = 'name'
    
    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True
    )
    
    color = fields.Integer(
        string='Color Index'
    )


class KnowledgeAcknowledgment(models.Model):
    """Track article acknowledgments."""
    
    _name = 'knowledge.acknowledgment'
    _description = 'Knowledge Acknowledgment'
    _order = 'acknowledged_date desc'
    
    article_id = fields.Many2one(
        'knowledge.article',
        string='Article',
        required=True,
        ondelete='cascade'
    )
    
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        required=True
    )
    
    acknowledged_date = fields.Datetime(
        string='Acknowledged On',
        default=fields.Datetime.now,
        required=True
    )
    
    article_version = fields.Char(
        string='Version',
        related='article_id.version',
        store=True
    )
    
    needs_reacknowledgment = fields.Boolean(
        string='Needs Re-acknowledgment',
        default=False,
        help='Article has been updated since last acknowledgment'
    )
    
    _sql_constraints = [
        ('article_guard_unique', 'unique(article_id, guard_id)',
         'Guard has already acknowledged this article!'),
    ]


class KnowledgeSOP(models.Model):
    """Standard Operating Procedures with detailed steps."""
    
    _name = 'knowledge.sop'
    _description = 'Standard Operating Procedure'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Procedure Name',
        required=True,
        translate=True,
        tracking=True
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    article_id = fields.Many2one(
        'knowledge.article',
        string='Related Article',
        ondelete='cascade'
    )
    
    code = fields.Char(
        string='SOP Code',
        help='Unique identifier for this procedure'
    )
    
    description = fields.Html(
        string='Description',
        translate=True
    )
    
    objective = fields.Text(
        string='Objective',
        translate=True,
        help='What this procedure aims to achieve'
    )
    
    scope = fields.Text(
        string='Scope',
        translate=True,
        help='When and where this procedure applies'
    )
    
    # UAE/SIRA Fields
    is_sira_compliant = fields.Boolean(
        string='SIRA Compliant',
        default=False
    )
    
    sira_category = fields.Selection([
        ('access_control', 'Access Control'),
        ('patrol', 'Patrol & Monitoring'),
        ('incident', 'Incident Response'),
        ('emergency', 'Emergency Procedures'),
        ('reporting', 'Reporting Requirements'),
        ('customer_service', 'Customer Service'),
        ('equipment', 'Equipment Handling'),
        ('communication', 'Communication Protocols')
    ], string='SIRA Category')
    
    risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical')
    ], string='Risk Level', default='low')
    
    # Steps
    step_ids = fields.One2many(
        'knowledge.sop.step',
        'sop_id',
        string='Procedure Steps',
        copy=True
    )
    
    step_count = fields.Integer(
        string='# Steps',
        compute='_compute_step_count'
    )
    
    # Checklist
    checklist_ids = fields.One2many(
        'knowledge.sop.checklist',
        'sop_id',
        string='Checklist Items',
        copy=True
    )
    
    checklist_count = fields.Integer(
        string='# Checklist Items',
        compute='_compute_checklist_count'
    )
    
    # Related Documents
    related_doc_ids = fields.Many2many(
        'knowledge.article',
        'sop_related_article_rel',
        'sop_id',
        'article_id',
        string='Related Documents'
    )
    
    # Training
    requires_training = fields.Boolean(
        string='Requires Training',
        default=False
    )
    
    training_duration = fields.Float(
        string='Training Duration (hours)',
        help='Estimated time to learn this procedure'
    )
    
    # Status
    state = fields.Selection([
        ('draft', 'Draft'),
        ('review', 'Under Review'),
        ('approved', 'Approved'),
        ('archived', 'Archived')
    ], string='Status', default='draft', tracking=True)
    
    approved_by = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True
    )
    
    approved_date = fields.Date(
        string='Approved Date',
        readonly=True
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('step_ids')
    def _compute_step_count(self):
        """Count procedure steps."""
        for record in self:
            record.step_count = len(record.step_ids)
    
    @api.depends('checklist_ids')
    def _compute_checklist_count(self):
        """Count checklist items."""
        for record in self:
            record.checklist_count = len(record.checklist_ids)
    
    def action_submit_review(self):
        """Submit for review."""
        self.write({'state': 'review'})
    
    def action_approve(self):
        """Approve SOP."""
        self.write({
            'state': 'approved',
            'approved_by': self.env.user.id,
            'approved_date': fields.Date.today()
        })
    
    def action_archive_sop(self):
        """Archive SOP."""
        self.write({'state': 'archived', 'active': False})


class KnowledgeSOPStep(models.Model):
    """Individual steps within an SOP."""
    
    _name = 'knowledge.sop.step'
    _description = 'SOP Step'
    _order = 'sop_id, sequence, id'
    
    sop_id = fields.Many2one(
        'knowledge.sop',
        string='SOP',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Step Number',
        required=True,
        default=10
    )
    
    name = fields.Char(
        string='Step Title',
        required=True,
        translate=True
    )
    
    description = fields.Html(
        string='Instructions',
        translate=True,
        required=True
    )
    
    expected_duration = fields.Float(
        string='Expected Duration (minutes)',
        help='How long this step should take'
    )
    
    is_critical = fields.Boolean(
        string='Critical Step',
        default=False,
        help='Failure to complete this step has serious consequences'
    )
    
    safety_note = fields.Text(
        string='Safety Notes',
        translate=True,
        help='Important safety considerations'
    )
    
    image = fields.Binary(
        string='Reference Image',
        help='Visual aid for this step'
    )
    
    image_filename = fields.Char(
        string='Image Filename'
    )


class KnowledgeSOPChecklist(models.Model):
    """Checklist items for SOPs."""
    
    _name = 'knowledge.sop.checklist'
    _description = 'SOP Checklist Item'
    _order = 'sop_id, sequence, id'
    
    sop_id = fields.Many2one(
        'knowledge.sop',
        string='SOP',
        required=True,
        ondelete='cascade'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    name = fields.Char(
        string='Checklist Item',
        required=True,
        translate=True
    )
    
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Must be completed'
    )
    
    category = fields.Selection([
        ('preparation', 'Preparation'),
        ('execution', 'Execution'),
        ('completion', 'Completion'),
        ('safety', 'Safety Check'),
        ('documentation', 'Documentation')
    ], string='Category', default='execution')


class KnowledgeGuardRole(models.Model):
    """Guard roles for knowledge articles."""
    
    _name = 'knowledge.guard.role'
    _description = 'Guard Role'
    _order = 'name'
    
    name = fields.Char(
        string='Role Name',
        required=True,
        translate=True
    )
    
    code = fields.Char(
        string='Code',
        help='Short code for this role'
    )
    
    description = fields.Text(
        string='Description',
        translate=True
    )
    
    sira_level = fields.Selection([
        ('grade1', 'SIRA Grade 1 - Security Guard'),
        ('grade2', 'SIRA Grade 2 - Senior Security Guard'),
        ('grade3', 'SIRA Grade 3 - Security Supervisor'),
        ('grade4', 'SIRA Grade 4 - Security Manager'),
        ('other', 'Other Role')
    ], string='SIRA Grade')
    
    active = fields.Boolean(
        string='Active',
        default=True
    )

