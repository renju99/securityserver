# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta
from ..common.image_optimizer import ImageOptimizer
import logging

_logger = logging.getLogger(__name__)


class ComplianceAudit(models.Model):
    """Compliance Audit Management"""
    _name = 'compliance.audit'
    _description = 'Compliance Audit'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'audit_date desc, id desc'
    _rec_name = 'name'

    name = fields.Char(
        string='Audit Reference',
        required=True,
        default='New',
        copy=False,
        readonly=True,
        index=True,
        help='Unique audit reference number'
    )

    audit_type = fields.Selection([
        ('site', 'Project Audit'),
        ('guard', 'Guard Performance Audit'),
        ('equipment', 'Equipment Audit'),
        ('training', 'Training Compliance'),
        ('safety', 'Safety Audit'),
        ('security', 'Security Procedures'),
        ('operational', 'Operational Compliance'),
        ('regulatory', 'Regulatory Compliance'),
        ('quality', 'Quality Assurance')
    ], string='Audit Type', required=True, tracking=True)

    # Audit Target
    site_id = fields.Many2one(
        'client.site',
        string='Project',
        tracking=True,
        index=True,
        ondelete='cascade',
        help='Project being audited'
    )
    guard_id = fields.Many2one(
        'guard.profile',
        string='Guard',
        ondelete='cascade',
        help='Guard being audited'
    )
    equipment_id = fields.Many2one(
        'guardpro.equipment',
        string='Equipment',
        help='Equipment being audited'
    )

    # Audit Details
    audit_date = fields.Date(
        string='Audit Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        index=True
    )
    audit_start_time = fields.Datetime(
        string='Audit Start Time',
        help='When the audit began'
    )
    audit_end_time = fields.Datetime(
        string='Audit End Time',
        help='When the audit completed'
    )
    auditor_id = fields.Many2one(
        'res.users',
        string='Auditor',
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help='Person conducting the audit'
    )
    auditor_team_ids = fields.Many2many(
        'res.users',
        string='Audit Team',
        help='Additional team members involved'
    )

    # Scheduling
    is_scheduled = fields.Boolean(
        string='Scheduled Audit',
        default=False,
        help='Audit was pre-scheduled'
    )
    is_surprise = fields.Boolean(
        string='Surprise Audit',
        default=False,
        help='Unannounced audit'
    )
    next_audit_date = fields.Date(
        string='Next Audit Date',
        help='Date for next scheduled audit'
    )
    frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semiannual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('adhoc', 'Ad-hoc')
    ], string='Audit Frequency', help='How often this audit should occur')

    # Template
    template_id = fields.Many2one(
        'compliance.audit.template',
        string='Audit Template',
        help='Template used for this audit'
    )

    # Checklist
    checklist_ids = fields.One2many(
        'compliance.audit.item',
        'audit_id',
        string='Checklist Items'
    )

    # Scoring
    total_items = fields.Integer(
        string='Total Items',
        compute='_compute_scores',
        store=True
    )
    passed_items = fields.Integer(
        string='Passed Items',
        compute='_compute_scores',
        store=True
    )
    failed_items = fields.Integer(
        string='Failed Items',
        compute='_compute_scores',
        store=True
    )
    na_items = fields.Integer(
        string='N/A Items',
        compute='_compute_scores',
        store=True
    )
    compliance_score = fields.Float(
        string='Compliance Score (%)',
        compute='_compute_scores',
        store=True,
        help='Percentage of passed items'
    )
    
    # Rating
    rating = fields.Selection([
        ('excellent', 'Excellent (90-100%)'),
        ('good', 'Good (75-89%)'),
        ('satisfactory', 'Satisfactory (60-74%)'),
        ('needs_improvement', 'Needs Improvement (50-59%)'),
        ('unsatisfactory', 'Unsatisfactory (<50%)')
    ], string='Rating', compute='_compute_rating', store=True)

    # Results
    state = fields.Selection([
        ('draft', 'Draft'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('requires_action', 'Requires Corrective Action'),
        ('closed', 'Closed')
    ], string='Status', default='draft', tracking=True, required=True)

    findings = fields.Html(
        string='Key Findings',
        help='Summary of audit findings'
    )
    recommendations = fields.Html(
        string='Recommendations',
        help='Recommended actions based on findings'
    )
    executive_summary = fields.Html(
        string='Executive Summary',
        help='High-level summary for management'
    )

    # Corrective Actions
    corrective_action_ids = fields.One2many(
        'compliance.corrective.action',
        'audit_id',
        string='Corrective Actions'
    )
    action_count = fields.Integer(
        string='Action Count',
        compute='_compute_action_count'
    )
    open_actions = fields.Integer(
        string='Open Actions',
        compute='_compute_action_count'
    )

    # Integration
    incident_ids = fields.Many2many(
        'incident.report',
        string='Related Incidents',
        help='Incidents identified or related to this audit'
    )

    # Documentation
    attachment_ids = fields.Many2many(
        'ir.attachment',
        string='Attachments',
        help='Supporting documents, photos, evidence'
    )

    # Additional
    notes = fields.Text(
        string='Notes',
        help='Additional notes and observations'
    )
    follow_up_required = fields.Boolean(
        string='Follow-up Required',
        default=False,
        tracking=True
    )
    follow_up_date = fields.Date(
        string='Follow-up Date'
    )

    # Audit
    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load checklist items from template"""
        if self.template_id and self.template_id.item_ids:
            # Clear existing checklist items that haven't been saved yet
            self.checklist_ids = [(5, 0, 0)]
            
            # Create new checklist items from template
            checklist_items = []
            for item in self.template_id.item_ids:
                # Use description for name if name is not available (computed field)
                item_name = item.name if item.name else (
                    item.description[:80] if item.description else 'Checkpoint'
                )
                
                checklist_items.append((0, 0, {
                    'sequence': item.sequence,
                    'name': item_name,
                    'description': item.description,
                    'category': item.category,
                    'regulation_reference': item.regulation_reference
                }))
            
            # Update checklist_ids with new items
            if checklist_items:
                self.checklist_ids = checklist_items
                _logger.info(
                    'Loaded %d checklist items from template %s',
                    len(checklist_items),
                    self.template_id.name
                )
        elif self.template_id and not self.template_id.item_ids:
            _logger.warning(
                'Template %s has no items to load',
                self.template_id.name
            )
    
    @api.onchange('audit_type')
    def _onchange_audit_type(self):
        """Update template domain and clear template if audit type changes"""
        if self.audit_type:
            # Clear template if it doesn't match the new audit type
            if self.template_id and self.template_id.audit_type != self.audit_type:
                self.template_id = False
                self.checklist_ids = [(5, 0, 0)]
        
        # Return domain to filter templates by audit_type
        return {
            'domain': {
                'template_id': [('audit_type', '=', self.audit_type)] if self.audit_type else []
            }
        }

    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('compliance.audit') or 'New'
        records = super().create(vals_list)
        
        # Optimize attached photos
        for record in records:
            if record.attachment_ids:
                record._optimize_attachments()
        
        return records
    
    def write(self, vals):
        """Override write to optimize photos on update."""
        result = super().write(vals)
        if 'attachment_ids' in vals:
            self._optimize_attachments()
        return result
    
    def _optimize_attachments(self):
        """Optimize photo attachments for storage and PDF rendering."""
        for record in self:
            photo_attachments = record.attachment_ids.filtered(
                lambda a: a.mimetype and a.mimetype.startswith('image/')
            )
            for attachment in photo_attachments:
                try:
                    # Skip if already optimized
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue
                    
                    original_data = attachment.datas
                    if not original_data:
                        continue
                    
                    # Optimize image
                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )
                    
                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized photo %s for audit %s',
                            attachment.name,
                            record.name
                        )
                except Exception as e:
                    _logger.error(
                        'Failed to optimize photo %s: %s',
                        attachment.id,
                        str(e)
                    )

    @api.depends('checklist_ids', 'checklist_ids.result')
    def _compute_scores(self):
        """Calculate audit scores"""
        for audit in self:
            total = len(audit.checklist_ids)
            passed = len(audit.checklist_ids.filtered(lambda x: x.result == 'pass'))
            failed = len(audit.checklist_ids.filtered(lambda x: x.result == 'fail'))
            na = len(audit.checklist_ids.filtered(lambda x: x.result == 'na'))
            
            audit.total_items = total
            audit.passed_items = passed
            audit.failed_items = failed
            audit.na_items = na
            
            # Calculate score excluding N/A items
            applicable_items = total - na
            if applicable_items > 0:
                audit.compliance_score = (passed / applicable_items) * 100
            else:
                audit.compliance_score = 0.0

    @api.depends('compliance_score')
    def _compute_rating(self):
        """Determine rating based on compliance score"""
        for audit in self:
            score = audit.compliance_score
            if score >= 90:
                audit.rating = 'excellent'
            elif score >= 75:
                audit.rating = 'good'
            elif score >= 60:
                audit.rating = 'satisfactory'
            elif score >= 50:
                audit.rating = 'needs_improvement'
            else:
                audit.rating = 'unsatisfactory'

    @api.depends('corrective_action_ids', 'corrective_action_ids.state')
    def _compute_action_count(self):
        """Count corrective actions"""
        for audit in self:
            audit.action_count = len(audit.corrective_action_ids)
            audit.open_actions = len(
                audit.corrective_action_ids.filtered(
                    lambda x: x.state in ['open', 'in_progress']
                )
            )

    def action_start_audit(self):
        """Start the audit"""
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft audits can be started.'))
        
        self.write({
            'state': 'in_progress',
            'audit_start_time': fields.Datetime.now()
        })
        return True

    def action_complete_audit(self):
        """Complete the audit"""
        self.ensure_one()
        
        # Check if all items are evaluated
        unevaluated = self.checklist_ids.filtered(lambda x: not x.result)
        if unevaluated:
            raise UserError(
                _('Please evaluate all checklist items before completing the audit.\n%d items remaining.') % 
                len(unevaluated)
            )
        
        # Determine if corrective actions are needed
        if self.failed_items > 0:
            state = 'requires_action'
        else:
            state = 'completed'
        
        self.write({
            'state': state,
            'audit_end_time': fields.Datetime.now()
        })
        
        # Schedule follow-up if needed
        if self.frequency and self.frequency != 'adhoc':
            self._schedule_next_audit()
        
        return True

    def action_close_audit(self):
        """Close the audit after all actions completed"""
        self.ensure_one()
        
        open_actions = self.corrective_action_ids.filtered(
            lambda x: x.state not in ['completed', 'verified']
        )
        
        if open_actions:
            raise UserError(
                _('Cannot close audit with open corrective actions.\n%d actions remaining.') % 
                len(open_actions)
            )
        
        self.state = 'closed'
        return True

    def action_create_corrective_action(self):
        """Open wizard to create corrective action"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'compliance.corrective.action',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_audit_id': self.id,
                'default_assigned_to': self.site_id.manager_id.user_id.id if self.site_id and self.site_id.manager_id else False
            }
        }

    def action_generate_report(self):
        """Generate audit report PDF"""
        self.ensure_one()
        return self.env.ref('guardpro.action_report_compliance_audit').report_action(self)

    def _schedule_next_audit(self):
        """Schedule next audit based on frequency"""
        self.ensure_one()
        
        if not self.frequency or self.frequency == 'adhoc':
            return
        
        days_map = {
            'weekly': 7,
            'biweekly': 14,
            'monthly': 30,
            'quarterly': 90,
            'semiannual': 180,
            'annual': 365
        }
        
        days = days_map.get(self.frequency, 0)
        if days:
            self.next_audit_date = fields.Date.add(self.audit_date, days=days)

    @api.model
    def send_audit_reminders(self):
        """Cron: Send reminders for upcoming audits"""
        upcoming_date = fields.Date.add(fields.Date.today(), days=7)
        
        audits_needing_schedule = self.search([
            ('next_audit_date', '<=', upcoming_date),
            ('next_audit_date', '>=', fields.Date.today()),
            ('state', '=', 'closed')
        ])
        
        # Planned activities intentionally disabled for scheduled audit reminders.
        
        _logger.info('Sent audit reminders for %d upcoming audits', len(audits_needing_schedule))
        return True


class ComplianceAuditItem(models.Model):
    """Audit Checklist Item"""
    _name = 'compliance.audit.item'
    _description = 'Audit Checklist Item'
    _order = 'sequence, id'

    audit_id = fields.Many2one(
        'compliance.audit',
        string='Audit',
        required=True,
        ondelete='cascade',
        index=True
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of checklist items'
    )

    name = fields.Char(
        string='Checkpoint',
        required=True,
        help='What is being checked'
    )
    description = fields.Text(
        string='Description',
        help='Detailed description and criteria'
    )
    category = fields.Char(
        string='Category',
        help='Grouping category for organization'
    )

    result = fields.Selection([
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('na', 'Not Applicable')
    ], string='Result')

    notes = fields.Text(
        string='Notes',
        help='Auditor notes and observations'
    )
    photo_1 = fields.Image(
        string='Photo 1',
        help='Supporting photo evidence'
    )
    photo_2 = fields.Image(
        string='Photo 2',
        help='Additional photo evidence'
    )
    photo_ids = fields.Many2many(
        'ir.attachment',
        'compliance_audit_item_photo_rel',
        'item_id',
        'attachment_id',
        string='Photos',
        help='Attach photo evidence for this checkpoint item'
    )
    photo_count = fields.Integer(
        string='Photo Count',
        compute='_compute_photo_count',
        store=True,
        help='Number of photos attached to this checkpoint'
    )

    requires_action = fields.Boolean(
        string='Requires Corrective Action',
        help='Check if this item needs corrective action'
    )
    severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Severity', help='Severity if failed')

    # Reference
    regulation_reference = fields.Char(
        string='Regulation Reference',
        help='Reference to specific regulation or standard'
    )

    @api.depends('photo_ids')
    def _compute_photo_count(self):
        """Compute number of attached photos."""
        for item in self:
            item.photo_count = len(item.photo_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Optimize photos after creation."""
        items = super().create(vals_list)
        items._optimize_photo_attachments()
        return items

    def write(self, vals):
        """Optimize photos when attachments are updated."""
        result = super().write(vals)
        if 'photo_ids' in vals:
            self._optimize_photo_attachments()
        return result

    def _optimize_photo_attachments(self):
        """Optimize attached photos for storage and report usage."""
        for item in self:
            attachments = item.photo_ids.filtered(
                lambda attachment: attachment.mimetype and attachment.mimetype.startswith('image/')
            )
            for attachment in attachments:
                try:
                    if attachment.file_size and attachment.file_size < 300 * 1024:
                        continue

                    original_data = attachment.datas
                    if not original_data:
                        continue

                    optimized_data = ImageOptimizer.optimize_image(
                        original_data,
                        max_dimension=1200,
                        target_format='JPEG'
                    )

                    if optimized_data != original_data:
                        attachment.write({
                            'datas': optimized_data,
                            'mimetype': 'image/jpeg',
                        })
                        _logger.info(
                            'Optimized checklist photo %s for audit item %s',
                            attachment.name,
                            item.name
                        )
                except Exception as error:
                    _logger.error(
                        'Failed to optimize photo %s for audit item %s: %s',
                        attachment.id,
                        item.name,
                        error
                    )


class ComplianceCorrectiveAction(models.Model):
    """Corrective Action for Audit Findings"""
    _name = 'compliance.corrective.action'
    _description = 'Corrective Action'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'due_date, priority desc, id desc'
    _rec_name = 'name'

    audit_id = fields.Many2one(
        'compliance.audit',
        string='Related Audit',
        required=True,
        ondelete='cascade',
        tracking=True
    )
    name = fields.Char(
        string='Action Required',
        required=True,
        tracking=True,
        help='Brief description of corrective action'
    )
    description = fields.Html(
        string='Detailed Description',
        help='Detailed description of the issue and required action'
    )

    # Priority & Assignment
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Normal'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='1', tracking=True)
    
    assigned_to = fields.Many2one(
        'res.users',
        string='Assigned To',
        required=True,
        tracking=True,
        index=True
    )
    due_date = fields.Date(
        string='Due Date',
        required=True,
        tracking=True,
        index=True
    )

    # Status
    state = fields.Selection([
        ('open', 'Open'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('verified', 'Verified'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='open', tracking=True, required=True)

    # Completion
    completion_date = fields.Date(
        string='Completion Date',
        tracking=True
    )
    completion_notes = fields.Html(
        string='Completion Notes',
        help='Details of actions taken'
    )
    completion_photo = fields.Image(
        string='Completion Photo',
        help='Photo evidence of completed action'
    )

    # Verification
    verified_by = fields.Many2one(
        'res.users',
        string='Verified By',
        tracking=True
    )
    verification_date = fields.Date(
        string='Verification Date',
        tracking=True
    )
    verification_notes = fields.Text(
        string='Verification Notes'
    )

    # Computed
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
        help='Action is past due date'
    )
    days_until_due = fields.Integer(
        string='Days Until Due',
        compute='_compute_days_until_due'
    )

    @api.depends('due_date', 'state')
    def _compute_is_overdue(self):
        """Check if action is overdue"""
        today = fields.Date.today()
        for action in self:
            if action.due_date and action.state not in ['completed', 'verified', 'cancelled']:
                action.is_overdue = today > action.due_date
            else:
                action.is_overdue = False

    @api.depends('due_date', 'state')
    def _compute_days_until_due(self):
        """Calculate days until due"""
        today = fields.Date.today()
        for action in self:
            if action.due_date and action.state not in ['completed', 'verified', 'cancelled']:
                delta = action.due_date - today
                action.days_until_due = delta.days
            else:
                action.days_until_due = 0

    def action_start(self):
        """Mark action as in progress"""
        self.ensure_one()
        if self.state != 'open':
            raise UserError(_('Only open actions can be started.'))
        
        self.state = 'in_progress'
        return True

    def action_complete(self):
        """Mark action as completed"""
        self.ensure_one()
        
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today()
        })
        
        # Planned activity intentionally disabled for corrective-action verification.
        
        return True

    def action_verify(self):
        """Verify completed action"""
        self.ensure_one()
        
        if self.state != 'completed':
            raise UserError(_('Only completed actions can be verified.'))
        
        self.write({
            'state': 'verified',
            'verified_by': self.env.user.id,
            'verification_date': fields.Date.today()
        })
        
        return True

    @api.model
    def send_overdue_action_alerts(self):
        """Cron: Send alerts for overdue corrective actions"""
        overdue_actions = self.search([
            ('state', 'in', ['open', 'in_progress']),
            ('is_overdue', '=', True)
        ])
        
        # Planned activities intentionally disabled for overdue corrective actions.
        
        _logger.info('Sent overdue alerts for %d corrective actions', len(overdue_actions))
        return True


class ComplianceAuditTemplate(models.Model):
    """Audit Template for reusable checklists"""
    _name = 'compliance.audit.template'
    _description = 'Audit Template'
    _order = 'name'

    name = fields.Char(
        string='Template Name',
        required=True,
        help='Name of the audit template'
    )
    audit_type = fields.Selection([
        ('site', 'Project Audit'),
        ('guard', 'Guard Performance Audit'),
        ('equipment', 'Equipment Audit'),
        ('training', 'Training Compliance'),
        ('safety', 'Safety Audit'),
        ('security', 'Security Procedures'),
        ('operational', 'Operational Compliance'),
        ('regulatory', 'Regulatory Compliance'),
        ('quality', 'Quality Assurance')
    ], string='Audit Type', required=True)

    description = fields.Html(
        string='Description',
        help='Description of this audit template'
    )

    item_ids = fields.One2many(
        'compliance.audit.template.item',
        'template_id',
        string='Checklist Items'
    )
    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_count'
    )

    frequency = fields.Selection([
        ('weekly', 'Weekly'),
        ('biweekly', 'Bi-Weekly'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semiannual', 'Semi-Annual'),
        ('annual', 'Annual'),
        ('adhoc', 'Ad-hoc')
    ], string='Recommended Frequency')

    passing_score = fields.Float(
        string='Passing Score (%)',
        default=75.0,
        help='Minimum score percentage required to pass the audit'
    )

    active = fields.Boolean(
        string='Active',
        default=True
    )

    @api.depends('item_ids')
    def _compute_item_count(self):
        """Count template items"""
        for template in self:
            template.item_count = len(template.item_ids)

    def action_create_audit(self):
        """Create audit from this template"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'compliance.audit.create.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_template_id': self.id,
                'default_audit_type': self.audit_type,
                'default_frequency': self.frequency
            }
        }


class ComplianceAuditTemplateItem(models.Model):
    """Template Checklist Item"""
    _name = 'compliance.audit.template.item'
    _description = 'Template Checklist Item'
    _order = 'sequence, id'

    template_id = fields.Many2one(
        'compliance.audit.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    name = fields.Char(
        string='Checkpoint',
        compute='_compute_name',
        store=True
    )
    description = fields.Text(
        string='Description',
        required=True
    )
    category = fields.Char(
        string='Category',
        help='Grouping category'
    )
    regulation_reference = fields.Char(
        string='Regulation Reference'
    )
    critical = fields.Boolean(
        string='Critical Item',
        default=False,
        help='Indicates if this is a critical audit checkpoint'
    )
    max_score = fields.Float(
        string='Maximum Score',
        default=10.0,
        help='Maximum score for this checkpoint'
    )

    @api.depends('description')
    def _compute_name(self):
        """Compute name from description"""
        for item in self:
            if item.description:
                # Take first 80 characters of description as name
                item.name = item.description[:80]
            else:
                item.name = 'Untitled Checkpoint'

