# -*- coding: utf-8 -*-
"""Enhanced Incident Reporting with Templates and Witness Management."""

from odoo import models, fields, api
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class IncidentTemplate(models.Model):
    """Templates for common incident types."""
    
    _name = 'incident.template'
    _description = 'Incident Report Template'
    _order = 'sequence, name'

    name = fields.Char(
        string='Template Name',
        required=True,
        index=True
    )
    code = fields.Char(
        string='Template Code',
        required=True,
        index=True,
        help='Unique code for the template (e.g., THEFT, MEDICAL, FIRE)'
    )
    description = fields.Html(
        string='Template Description'
    )
    
    incident_type = fields.Selection([
        ('security_breach', 'Security Breach'),
        ('theft', 'Theft'),
        ('vandalism', 'Vandalism'),
        ('medical_emergency', 'Medical Emergency'),
        ('fire', 'Fire'),
        ('suspicious_activity', 'Suspicious Activity'),
        ('trespassing', 'Trespassing'),
        ('equipment_malfunction', 'Equipment Malfunction'),
        ('safety_hazard', 'Safety Hazard'),
        ('noise_complaint', 'Noise Complaint'),
        ('other', 'Other')
    ], string='Incident Type', required=True)
    
    default_severity = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical')
    ], string='Default Severity', default='medium')
    
    description_template = fields.Html(
        string='Description Template',
        help='Pre-filled description text with placeholders'
    )
    
    required_fields = fields.Many2many(
        'ir.model.fields',
        string='Required Fields',
        help='Fields that must be filled when using this template'
    )
    
    checklist_item_ids = fields.One2many(
        'incident.template.checklist',
        'template_id',
        string='Checklist Items'
    )
    
    requires_photos = fields.Boolean(
        string='Requires Photos',
        default=False
    )
    min_photos = fields.Integer(
        string='Minimum Photos',
        default=1
    )
    
    requires_witness = fields.Boolean(
        string='Requires Witness Information',
        default=False
    )
    
    requires_video = fields.Boolean(
        string='Requires Video Evidence',
        default=False
    )
    
    auto_notify_authorities = fields.Boolean(
        string='Auto-Notify Authorities',
        default=False,
        help='Automatically notify police/fire/medical based on type'
    )
    
    notification_emails = fields.Char(
        string='Notification Emails',
        help='Comma-separated email addresses for automatic notification'
    )
    
    icon = fields.Selection([
        ('fa-exclamation-triangle', 'Warning Triangle'),
        ('fa-fire', 'Fire'),
        ('fa-user-injured', 'Medical'),
        ('fa-key', 'Security'),
        ('fa-car-crash', 'Accident'),
        ('fa-shield-alt', 'Protection'),
        ('fa-tools', 'Maintenance')
    ], string='Icon', default='fa-exclamation-triangle')
    
    color = fields.Char(
        string='Color',
        default='#3498db',
        help='Hex color for template button'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    usage_count = fields.Integer(
        string='Usage Count',
        compute='_compute_usage_count',
        store=True
    )
    
    @api.depends('incident_report_ids')
    def _compute_usage_count(self):
        """Count how many times template has been used."""
        for record in self:
            record.usage_count = len(record.incident_report_ids)
    
    incident_report_ids = fields.One2many(
        'incident.report',
        'template_id',
        string='Incidents Using Template'
    )


class IncidentTemplateChecklist(models.Model):
    """Checklist items for incident templates."""
    
    _name = 'incident.template.checklist'
    _description = 'Incident Template Checklist'
    _order = 'sequence, name'

    template_id = fields.Many2one(
        'incident.template',
        string='Template',
        required=True,
        ondelete='cascade'
    )
    name = fields.Char(
        string='Checklist Item',
        required=True
    )
    description = fields.Text(
        string='Description/Instructions'
    )
    is_mandatory = fields.Boolean(
        string='Mandatory',
        default=True
    )
    requires_photo = fields.Boolean(
        string='Requires Photo',
        default=False
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )


class IncidentWitness(models.Model):
    """Witness information for incidents."""
    
    _name = 'incident.witness'
    _description = 'Incident Witness'
    _order = 'sequence'

    incident_id = fields.Many2one(
        'incident.report',
        string='Incident',
        required=True,
        ondelete='cascade',
        index=True
    )
    name = fields.Char(
        string='Witness Name',
        required=True
    )
    contact_phone = fields.Char(
        string='Contact Phone'
    )
    contact_email = fields.Char(
        string='Contact Email'
    )
    id_number = fields.Char(
        string='ID Number',
        help='National ID or passport number'
    )
    statement = fields.Text(
        string='Witness Statement',
        required=True
    )
    statement_voice = fields.Binary(
        string='Voice Statement',
        help='Audio recording of witness statement'
    )
    photo = fields.Binary(
        string='Witness Photo',
        help='Photo of witness (with consent)'
    )
    consent_given = fields.Boolean(
        string='Consent Given',
        default=False,
        help='Witness gave consent for information collection'
    )
    consent_signature = fields.Binary(
        string='Consent Signature',
        help='Digital signature for consent'
    )
    witness_type = fields.Selection([
        ('involved', 'Directly Involved'),
        ('eyewitness', 'Eyewitness'),
        ('reported_by', 'Reported By'),
        ('other', 'Other')
    ], string='Witness Type', default='eyewitness')
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    @api.constrains('consent_given', 'photo')
    def _check_photo_consent(self):
        """Ensure consent is given before storing photo."""
        for record in self:
            if record.photo and not record.consent_given:
                raise ValidationError('Cannot store witness photo without consent')


class IncidentMediaAnnotation(models.Model):
    """Media annotations for incident photos/videos."""
    
    _name = 'incident.media.annotation'
    _description = 'Incident Media Annotation'

    incident_id = fields.Many2one(
        'incident.report',
        string='Incident',
        required=True,
        ondelete='cascade',
        index=True
    )
    media_type = fields.Selection([
        ('photo', 'Photo'),
        ('video', 'Video')
    ], string='Media Type', required=True)
    
    original_media = fields.Binary(
        string='Original Media',
        required=True
    )
    annotated_media = fields.Binary(
        string='Annotated Media',
        help='Media with annotations applied'
    )
    annotation_data = fields.Text(
        string='Annotation JSON',
        help='JSON data of annotations (arrows, circles, text, blur)'
    )
    
    description = fields.Char(
        string='Description'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    
    created_at = fields.Datetime(
        string='Created At',
        default=fields.Datetime.now
    )


# Extend incident.report model
class IncidentReport(models.Model):
    """Extend incident.report with template and witness features."""
    
    _inherit = 'incident.report'

    template_id = fields.Many2one(
        'incident.template',
        string='Template Used',
        help='Template used to create this incident'
    )
    
    witness_ids = fields.One2many(
        'incident.witness',
        'incident_id',
        string='Witness List'
    )
    
    media_annotation_ids = fields.One2many(
        'incident.media.annotation',
        'incident_id',
        string='Annotated Media'
    )
    
    witness_count = fields.Integer(
        string='Number of Witnesses',
        compute='_compute_witness_count',
        store=True
    )
    
    has_annotated_media = fields.Boolean(
        string='Has Annotated Media',
        compute='_compute_has_annotated_media',
        store=True
    )
    
    video_evidence = fields.Binary(
        string='Video Evidence',
        help='Video recording of incident scene'
    )
    
    video_duration = fields.Integer(
        string='Video Duration (seconds)'
    )
    
    @api.depends('witness_ids')
    def _compute_witness_count(self):
        """Compute number of witnesses."""
        for record in self:
            record.witness_count = len(record.witness_ids)
    
    @api.depends('media_annotation_ids')
    def _compute_has_annotated_media(self):
        """Check if incident has annotated media."""
        for record in self:
            record.has_annotated_media = bool(record.media_annotation_ids)

