# -*- coding: utf-8 -*-
"""Incident Investigation Timeline Model - Track investigation activities and events."""

from odoo import models, fields, api, _
import logging

_logger = logging.getLogger(__name__)


class IncidentInvestigationTimeline(models.Model):
    """Investigation Timeline Tracking"""
    
    _name = 'incident.investigation.timeline'
    _description = 'Investigation Timeline'
    _order = 'timestamp desc, id desc'
    _rec_name = 'description'
    
    investigation_id = fields.Many2one(
        'incident.investigation',
        string='Investigation',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    timestamp = fields.Datetime(
        string='Date/Time',
        default=fields.Datetime.now,
        required=True,
        index=True
    )
    
    entry_type = fields.Selection([
        ('investigation_started', 'Investigation Started'),
        ('investigation_activated', 'Investigation Activated'),
        ('status_changed', 'Status Changed'),
        ('phase_changed', 'Phase Changed'),
        ('evidence_added', 'Evidence Added'),
        ('witness_interviewed', 'Witness Interviewed'),
        ('finding_added', 'Finding Added'),
        ('document_uploaded', 'Document Uploaded'),
        ('note_added', 'Note Added'),
        ('review_requested', 'Review Requested'),
        ('submitted_for_review', 'Submitted for Review'),
        ('revision_requested', 'Revision Requested'),
        ('investigation_approved', 'Investigation Approved'),
        ('investigation_suspended', 'Investigation Suspended'),
        ('investigation_resumed', 'Investigation Resumed'),
        ('investigation_closed', 'Investigation Closed'),
        ('meeting_held', 'Meeting Held'),
        ('site_visit', 'Site Visit'),
        ('expert_consulted', 'Expert Consulted'),
        ('other', 'Other')
    ], string='Entry Type', required=True, index=True)
    
    description = fields.Text(
        string='Description',
        required=True,
        help='Description of timeline event'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Recorded By',
        default=lambda self: self.env.user,
        required=True
    )
    
    # Optional references
    evidence_id = fields.Many2one(
        'incident.investigation.evidence',
        string='Related Evidence',
        ondelete='set null'
    )
    witness_id = fields.Many2one(
        'incident.investigation.witness',
        string='Related Witness',
        ondelete='set null'
    )
    finding_id = fields.Many2one(
        'incident.investigation.finding',
        string='Related Finding',
        ondelete='set null'
    )
    
    # Additional details
    location = fields.Char(
        string='Location',
        help='Location where event occurred'
    )
    attendees = fields.Char(
        string='Attendees',
        help='People present for this event'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'investigation_timeline_attachment_rel',
        'timeline_id',
        'attachment_id',
        string='Attachments'
    )
    
    notes = fields.Text(
        string='Additional Notes'
    )
    
    # Color for visual distinction
    color = fields.Integer(
        string='Color Index',
        compute='_compute_color'
    )
    
    @api.depends('entry_type')
    def _compute_color(self):
        """Set color based on entry type"""
        color_map = {
            'investigation_started': 4,      # Blue
            'investigation_activated': 4,     # Blue
            'investigation_approved': 10,     # Green
            'investigation_closed': 10,       # Green
            'investigation_suspended': 7,     # Grey
            'revision_requested': 2,          # Red
            'evidence_added': 9,              # Orange
            'witness_interviewed': 9,         # Orange
            'finding_added': 3,               # Yellow
            'phase_changed': 8,               # Purple
            'status_changed': 8,              # Purple
        }
        for record in self:
            record.color = color_map.get(record.entry_type, 0)

