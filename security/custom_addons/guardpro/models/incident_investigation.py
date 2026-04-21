# -*- coding: utf-8 -*-
"""Incident Investigation Model - Structured investigation workflow and management."""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigation(models.Model):
    """Incident Investigation Management"""
    
    _name = 'incident.investigation'
    _description = 'Incident Investigation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _rec_name = 'name'
    
    # Basic Information
    name = fields.Char(
        string='Investigation Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        index=True,
        tracking=True
    )
    incident_id = fields.Many2one(
        'incident.report',
        string='Related Incident',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Incident being investigated'
    )
    incident_name = fields.Char(
        related='incident_id.name',
        string='Incident Number',
        store=True
    )
    incident_severity = fields.Selection(
        related='incident_id.severity',
        string='Incident Severity',
        store=True
    )
    site_id = fields.Many2one(
        related='incident_id.site_id',
        string='Site',
        store=True,
        index=True
    )
    
    # Investigation Details
    title = fields.Char(
        string='Investigation Title',
        required=True,
        tracking=True,
        help='Brief title of the investigation'
    )
    description = fields.Html(
        string='Investigation Scope',
        help='What is being investigated and why'
    )
    investigation_type = fields.Selection([
        ('routine', 'Routine Investigation'),
        ('detailed', 'Detailed Investigation'),
        ('formal', 'Formal Investigation'),
        ('root_cause', 'Root Cause Analysis'),
        ('compliance', 'Compliance Investigation'),
        ('internal', 'Internal Investigation'),
        ('external', 'External Investigation')
    ], string='Investigation Type', default='routine', required=True, tracking=True)
    
    # Assignment
    lead_investigator_id = fields.Many2one(
        'res.users',
        string='Lead Investigator',
        required=True,
        tracking=True,
        default=lambda self: self.env.user,
        help='Primary investigator responsible for this investigation'
    )
    investigator_ids = fields.Many2many(
        'res.users',
        'investigation_investigator_rel',
        'investigation_id',
        'user_id',
        string='Investigation Team',
        tracking=True,
        help='Additional team members assisting with investigation'
    )
    
    # Timeline
    start_date = fields.Datetime(
        string='Investigation Start Date',
        default=fields.Datetime.now,
        required=True,
        tracking=True
    )
    target_completion_date = fields.Date(
        string='Target Completion Date',
        tracking=True,
        help='Expected completion date'
    )
    actual_completion_date = fields.Date(
        string='Actual Completion Date',
        readonly=True,
        tracking=True
    )
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True,
        help='Investigation duration in days'
    )
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_is_overdue',
        store=True,
        help='Investigation is past target completion date'
    )
    
    # Status
    status = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active Investigation'),
        ('evidence_collection', 'Evidence Collection'),
        ('analysis', 'Analysis'),
        ('report_writing', 'Report Writing'),
        ('review', 'Under Review'),
        ('completed', 'Completed'),
        ('closed', 'Closed'),
        ('suspended', 'Suspended')
    ], string='Status', default='draft', required=True, tracking=True, index=True)
    
    # Progress
    progress = fields.Float(
        string='Progress (%)',
        default=0.0,
        tracking=True,
        help='Investigation completion percentage (0-100)'
    )
    
    # Priority
    priority = fields.Selection([
        ('0', 'Normal'),
        ('1', 'Low'),
        ('2', 'High'),
        ('3', 'Urgent')
    ], string='Priority', default='0', index=True, tracking=True)
    
    # Related Records
    timeline_ids = fields.One2many(
        'incident.investigation.timeline',
        'investigation_id',
        string='Timeline Entries'
    )
    timeline_count = fields.Integer(
        string='Number of Timeline Entries',
        compute='_compute_counts'
    )
    
    evidence_ids = fields.One2many(
        'incident.investigation.evidence',
        'investigation_id',
        string='Evidence'
    )
    evidence_count = fields.Integer(
        string='Evidence Items',
        compute='_compute_counts'
    )
    
    witness_ids = fields.One2many(
        'incident.investigation.witness',
        'investigation_id',
        string='Witnesses'
    )
    witness_count = fields.Integer(
        string='Number of Witnesses',
        compute='_compute_counts'
    )
    
    finding_ids = fields.One2many(
        'incident.investigation.finding',
        'investigation_id',
        string='Findings'
    )
    finding_count = fields.Integer(
        string='Number of Findings',
        compute='_compute_counts'
    )
    
    # Investigation Report
    template_id = fields.Many2one(
        'incident.investigation.template',
        string='Report Template',
        help='Template to use for investigation report'
    )
    
    # Checklist
    checklist_ids = fields.One2many(
        'incident.investigation.checklist',
        'investigation_id',
        string='Checklist Items'
    )
    
    checklist_count = fields.Integer(
        string='Checklist Items',
        compute='_compute_checklist_stats'
    )
    
    checklist_completed_count = fields.Integer(
        string='Completed Items',
        compute='_compute_checklist_stats'
    )
    
    checklist_progress = fields.Float(
        string='Checklist Progress (%)',
        compute='_compute_checklist_stats',
        store=True,
        help='Percentage of checklist items completed'
    )
    
    checklist_mandatory_incomplete = fields.Integer(
        string='Mandatory Incomplete',
        compute='_compute_checklist_stats',
        help='Number of incomplete mandatory items'
    )
    
    executive_summary = fields.Html(
        string='Executive Summary',
        help='Brief overview of investigation findings'
    )
    detailed_findings = fields.Html(
        string='Detailed Findings',
        help='Complete investigation findings and analysis'
    )
    root_cause = fields.Text(
        string='Root Cause Analysis',
        help='Identified root causes of the incident'
    )
    recommendations = fields.Html(
        string='Recommendations',
        help='Recommended actions to prevent recurrence'
    )
    
    # Corrective Actions
    corrective_actions = fields.Html(
        string='Corrective Actions',
        help='Actions to be taken to address findings'
    )
    preventive_actions = fields.Html(
        string='Preventive Actions',
        help='Actions to prevent similar incidents'
    )
    
    # Review & Approval
    reviewed_by_id = fields.Many2one(
        'res.users',
        string='Reviewed By',
        tracking=True
    )
    review_date = fields.Date(
        string='Review Date',
        tracking=True
    )
    review_notes = fields.Text(
        string='Review Notes'
    )
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        tracking=True
    )
    approval_date = fields.Date(
        string='Approval Date',
        tracking=True
    )
    
    # Confidentiality
    is_confidential = fields.Boolean(
        string='Confidential',
        default=False,
        tracking=True,
        help='Mark investigation as confidential'
    )
    confidentiality_reason = fields.Text(
        string='Confidentiality Reason',
        help='Reason for marking as confidential'
    )
    
    # Tags
    tag_ids = fields.Many2many(
        'incident.investigation.tag',
        'investigation_tag_rel',
        'investigation_id',
        'tag_id',
        string='Tags',
        help='Categorization tags'
    )
    
    # Notes
    notes = fields.Text(
        string='Internal Notes',
        help='Internal notes not included in report'
    )
    
    # Color for kanban view
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    # Active
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    @api.depends('status', 'priority')
    def _compute_color(self):
        """Set color based on status and priority"""
        for record in self:
            if record.status == 'completed':
                record.color = 10  # Green
            elif record.status == 'closed':
                record.color = 8   # Grey
            elif record.status == 'suspended':
                record.color = 7   # Light grey
            elif record.priority == '3':
                record.color = 1   # Dark red (urgent)
            elif record.priority == '2':
                record.color = 2   # Red (high)
            elif record.status in ['active', 'evidence_collection', 'analysis']:
                record.color = 9   # Orange (in progress)
            else:
                record.color = 0   # Default
    
    @api.depends('start_date', 'actual_completion_date', 'status')
    def _compute_duration(self):
        """Calculate investigation duration"""
        for record in self:
            if record.actual_completion_date and record.start_date:
                start = fields.Datetime.to_datetime(record.start_date)
                end = fields.Datetime.to_datetime(record.actual_completion_date)
                record.duration_days = (end - start).days
            elif record.start_date and record.status not in ['completed', 'closed']:
                start = fields.Datetime.to_datetime(record.start_date)
                now = fields.Datetime.now()
                record.duration_days = (now - start).days
            else:
                record.duration_days = 0
    
    @api.depends('target_completion_date', 'status')
    def _compute_is_overdue(self):
        """Check if investigation is overdue"""
        today = fields.Date.today()
        for record in self:
            if record.status not in ['completed', 'closed', 'suspended']:
                if record.target_completion_date and record.target_completion_date < today:
                    record.is_overdue = True
                else:
                    record.is_overdue = False
            else:
                record.is_overdue = False
    
    @api.depends('timeline_ids', 'evidence_ids', 'witness_ids', 'finding_ids')
    def _compute_counts(self):
        """Compute record counts"""
        for record in self:
            record.timeline_count = len(record.timeline_ids)
            record.evidence_count = len(record.evidence_ids)
            record.witness_count = len(record.witness_ids)
            record.finding_count = len(record.finding_ids)
    
    @api.depends('checklist_ids', 'checklist_ids.completed', 'checklist_ids.is_mandatory')
    def _compute_checklist_stats(self):
        """Compute checklist statistics"""
        for record in self:
            total = len(record.checklist_ids)
            completed = len(record.checklist_ids.filtered('completed'))
            mandatory_incomplete = len(record.checklist_ids.filtered(
                lambda c: c.is_mandatory and not c.completed
            ))
            
            record.checklist_count = total
            record.checklist_completed_count = completed
            record.checklist_mandatory_incomplete = mandatory_incomplete
            
            if total > 0:
                record.checklist_progress = (completed / total) * 100
            else:
                record.checklist_progress = 0.0
    
    @api.onchange('template_id')
    def _onchange_template_id(self):
        """Load template content and generate checklist when template is selected"""
        if self.template_id:
            # Load template content
            if self.template_id.executive_summary_template:
                self.executive_summary = self.template_id.executive_summary_template
            if self.template_id.findings_template:
                self.detailed_findings = self.template_id.findings_template
            if self.template_id.root_cause_template:
                self.root_cause = self.template_id.root_cause_template
            if self.template_id.recommendations_template:
                self.recommendations = self.template_id.recommendations_template
            if self.template_id.corrective_actions_template:
                self.corrective_actions = self.template_id.corrective_actions_template
            if self.template_id.preventive_actions_template:
                self.preventive_actions = self.template_id.preventive_actions_template
            
            # Generate checklist items from template
            if self.template_id.checklist_item_ids:
                checklist_items = []
                for item in self.template_id.checklist_item_ids.sorted('sequence'):
                    # Use integer ID to avoid NewId issues in some Odoo versions
                    item_id = item.id.origin if hasattr(item.id, 'origin') else item.id
                    checklist_items.append((0, 0, {
                        'checklist_item_id': item_id,
                        'name': item.name,
                        'description': item.description,
                        'category': item.category,
                        'is_mandatory': item.is_mandatory,
                        'sequence': item.sequence,
                        'icon': item.icon,
                    }))
                self.checklist_ids = checklist_items
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate investigation number sequence"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'incident.investigation'
                ) or _('New')
        
        records = super().create(vals_list)

        # Create initial timeline entry and generate checklist
        for record in records:
            record._create_timeline_entry(
                'investigation_started',
                _('Investigation started by %s') % record.lead_investigator_id.name
            )

            # Generate checklist from template if not already provided (e.g., from UI onchange)
            if record.template_id and record.template_id.checklist_item_ids and not record.checklist_ids:
                record._generate_checklist_from_template()

            record._push_investigation_assignment_notification()

        return records

    def write(self, vals):
        """Track status changes in timeline and handle template changes"""
        assignment_changed = (
            'lead_investigator_id' in vals or 'investigator_ids' in vals
        )

        # Track status changes
        if 'status' in vals:
            old_status = self.status
            new_status = vals['status']

            result = super().write(vals)

            if old_status != new_status:
                status_labels = dict(self._fields['status'].selection)
                self._create_timeline_entry(
                    'status_changed',
                    _('Investigation status changed from %s to %s') % (
                        status_labels.get(old_status, old_status),
                        status_labels.get(new_status, new_status)
                    )
                )

            if assignment_changed:
                for record in self:
                    record._push_investigation_assignment_notification()

            return result

        # Handle template changes
        if 'template_id' in vals and vals['template_id']:
            result = super().write(vals)
            # Generate checklist from new template if not already provided in vals
            if 'checklist_ids' not in vals:
                for record in self:
                    if record.template_id and record.template_id.checklist_item_ids:
                        # Clear existing checklist items and generate new
                        record._generate_checklist_from_template()
            if assignment_changed:
                for record in self:
                    record._push_investigation_assignment_notification()
            return result

        result = super().write(vals)
        if assignment_changed:
            for record in self:
                record._push_investigation_assignment_notification()
        return result

    def _push_investigation_assignment_notification(self):
        """Buzz the phones of the lead + team when an investigation is
        assigned (on create, reassignment, or team change)."""
        self.ensure_one()
        recipients = self.env['res.users']
        if self.lead_investigator_id:
            recipients |= self.lead_investigator_id
        for user in (self.investigator_ids or []):
            recipients |= user
        if not recipients:
            return
        incident = self.incident_id if 'incident_id' in self._fields else False
        title = _('Investigation assigned: %s') % (self.name or '-')
        body_parts = []
        if incident:
            body_parts.append(_('Incident: %s') % incident.name)
        if self.lead_investigator_id:
            body_parts.append(_('Lead: %s') % self.lead_investigator_id.name)
        if self.investigator_ids:
            body_parts.append(_('Team: %s') % ', '.join(
                u.name for u in self.investigator_ids
            ))
        self.env['guardpro.mobile.outbox'].sudo().push(
            user=recipients,
            kind='incident_investigation',
            title=title,
            body='\n'.join(body_parts),
            priority='high',
            res_model='incident.investigation',
            res_id=self.id,
            dedup_key='incident_investigation:%s' % self.id,
        )
    
    def action_start_investigation(self):
        """Start investigation"""
        self.ensure_one()
        
        if self.status != 'draft':
            raise ValidationError(_('Only draft investigations can be started'))
        
        self.write({
            'status': 'active',
            'start_date': fields.Datetime.now()
        })
        
        self._create_timeline_entry(
            'investigation_activated',
            _('Investigation activated and work began')
        )
        
        try:
            self.message_post(
                body=_('Investigation started by %s') % self.env.user.name,
                message_type='notification'
            )
        except Exception:
            _logger.warning('Failed to send start notification for investigation %s', self.name)
        
        return True
    
    def action_collect_evidence(self):
        """Move to evidence collection phase"""
        self.ensure_one()
        self.write({'status': 'evidence_collection'})
        
        self._create_timeline_entry(
            'phase_changed',
            _('Entered evidence collection phase')
        )
        
        return True
    
    def action_analyze(self):
        """Move to analysis phase"""
        self.ensure_one()
        self.write({'status': 'analysis'})
        
        self._create_timeline_entry(
            'phase_changed',
            _('Entered analysis phase')
        )
        
        return True
    
    def action_write_report(self):
        """Move to report writing phase"""
        self.ensure_one()
        self.write({'status': 'report_writing'})
        
        self._create_timeline_entry(
            'phase_changed',
            _('Entered report writing phase')
        )
        
        return True
    
    def action_submit_for_review(self):
        """Submit investigation for review"""
        self.ensure_one()
        
        if not self.executive_summary:
            raise ValidationError(_('Please provide an executive summary before submitting for review'))
        
        if not self.detailed_findings:
            raise ValidationError(_('Please provide detailed findings before submitting for review'))
        
        self.write({'status': 'review'})
        
        self._create_timeline_entry(
            'submitted_for_review',
            _('Investigation submitted for review')
        )
        
        try:
            self.message_post(
                body=_('Investigation submitted for review by %s') % self.env.user.name,
                message_type='notification'
            )
        except Exception:
            _logger.warning('Failed to send review submission notification for investigation %s', self.name)
        
        return True
    
    def action_approve(self):
        """Approve investigation"""
        self.ensure_one()
        
        if self.status != 'review':
            raise ValidationError(_('Only investigations under review can be approved'))
        
        self.write({
            'status': 'completed',
            'approved_by_id': self.env.user.id,
            'approval_date': fields.Date.today(),
            'actual_completion_date': fields.Date.today()
        })
        
        self._create_timeline_entry(
            'investigation_approved',
            _('Investigation approved by %s') % self.env.user.name
        )
        
        try:
            self.message_post(
                body=_('Investigation approved and completed'),
                message_type='notification'
            )
        except Exception:
            _logger.warning('Failed to send approval notification for investigation %s', self.name)
        
        return True
    
    def action_request_revision(self):
        """Request revision of investigation"""
        self.ensure_one()
        
        self.write({'status': 'report_writing'})
        
        self._create_timeline_entry(
            'revision_requested',
            _('Revision requested by %s') % self.env.user.name
        )
        
        return True
    
    def action_suspend(self):
        """Suspend investigation"""
        self.ensure_one()
        
        self.write({'status': 'suspended'})
        
        self._create_timeline_entry(
            'investigation_suspended',
            _('Investigation suspended by %s') % self.env.user.name
        )
        
        return True
    
    def action_resume(self):
        """Resume suspended investigation"""
        self.ensure_one()
        
        if self.status != 'suspended':
            raise ValidationError(_('Only suspended investigations can be resumed'))
        
        self.write({'status': 'active'})
        
        self._create_timeline_entry(
            'investigation_resumed',
            _('Investigation resumed by %s') % self.env.user.name
        )
        
        return True
    
    def action_close(self):
        """Close investigation"""
        self.ensure_one()
        
        if self.status != 'completed':
            raise ValidationError(_('Only completed investigations can be closed'))
        
        self.write({'status': 'closed'})
        
        self._create_timeline_entry(
            'investigation_closed',
            _('Investigation closed by %s') % self.env.user.name
        )
        
        return True
    
    def action_view_timeline(self):
        """View investigation timeline"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investigation Timeline'),
            'res_model': 'incident.investigation.timeline',
            'view_mode': 'list,form',
            'domain': [('investigation_id', '=', self.id)],
            'context': {'default_investigation_id': self.id}
        }
    
    def action_view_evidence(self):
        """View evidence"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Evidence'),
            'res_model': 'incident.investigation.evidence',
            'view_mode': 'kanban,list,form',
            'domain': [('investigation_id', '=', self.id)],
            'context': {'default_investigation_id': self.id}
        }
    
    def action_view_witnesses(self):
        """View witnesses"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Witnesses'),
            'res_model': 'incident.investigation.witness',
            'view_mode': 'list,form',
            'domain': [('investigation_id', '=', self.id)],
            'context': {'default_investigation_id': self.id}
        }
    
    def action_view_findings(self):
        """View findings"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Findings'),
            'res_model': 'incident.investigation.finding',
            'view_mode': 'list,form',
            'domain': [('investigation_id', '=', self.id)],
            'context': {'default_investigation_id': self.id}
        }
    
    def _create_timeline_entry(self, entry_type, description):
        """Helper method to create timeline entries"""
        self.ensure_one()
        
        self.env['incident.investigation.timeline'].create({
            'investigation_id': self.id,
            'entry_type': entry_type,
            'description': description,
            'user_id': self.env.user.id,
            'timestamp': fields.Datetime.now()
        })
    
    def _generate_checklist_from_template(self):
        """Generate checklist items from template"""
        self.ensure_one()
        
        if not self.template_id:
            return
        
        # Clear existing checklist items
        self.checklist_ids.unlink()
        
        # Create new checklist items from template
        for item in self.template_id.checklist_item_ids:
            self.env['incident.investigation.checklist'].create({
                'investigation_id': self.id,
                'checklist_item_id': item.id
            })
        
        _logger.info(
            'Generated %d checklist items for investigation %s from template %s',
            len(self.template_id.checklist_item_ids),
            self.name,
            self.template_id.name
        )
    
    def action_regenerate_checklist(self):
        """Regenerate checklist from template"""
        self.ensure_one()
        
        if not self.template_id:
            raise ValidationError(_('Please select a template first'))
        
        self._generate_checklist_from_template()
        
        self.message_post(
            body=_('Checklist regenerated from template: %s') % self.template_id.name,
            message_type='notification'
        )
        
        return True
    
    def action_view_checklist(self):
        """View investigation checklist"""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Investigation Checklist'),
            'res_model': 'incident.investigation.checklist',
            'view_mode': 'list,form',
            'domain': [('investigation_id', '=', self.id)],
            'context': {'default_investigation_id': self.id}
        }
    
    @api.model
    def check_overdue_investigations(self):
        """Check for overdue investigations and send alerts
        
        Called by scheduled action daily.
        """
        today = fields.Date.today()
        
        overdue = self.search([
            ('status', 'not in', ['completed', 'closed', 'suspended']),
            ('target_completion_date', '<', today)
        ])
        
        if overdue:
            _logger.warning('Found %d overdue investigations', len(overdue))
            
            # Planned activities intentionally disabled for overdue investigations.
        
        return True


class IncidentInvestigationTag(models.Model):
    """Investigation Tags"""
    
    _name = 'incident.investigation.tag'
    _description = 'Investigation Tag'
    _order = 'name'
    
    name = fields.Char(
        string='Tag Name',
        required=True,
        translate=True
    )
    color = fields.Integer(
        string='Color Index'
    )

