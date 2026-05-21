# -*- coding: utf-8 -*-
"""Facility / maintenance issues reported from patrol checkpoint scans."""

from markupsafe import Markup, escape

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError

import logging

_logger = logging.getLogger(__name__)

FACILITY_ISSUE_TYPES = [
    ('lighting', 'Lighting'),
    ('hvac', 'HVAC / AC'),
    ('plumbing', 'Plumbing / Leak'),
    ('access_door', 'Door / Access'),
    ('cleanliness', 'Cleanliness'),
    ('damage_safety', 'Damage / Safety'),
    ('elevator', 'Elevator / Lift'),
    ('landscape', 'Landscaping'),
    ('other', 'Other'),
]

FACILITY_ISSUE_SEVERITY = {
    'damage_safety': 'high',
    'access_door': 'high',
    'plumbing': 'high',
    'elevator': 'medium',
    'hvac': 'medium',
    'lighting': 'low',
    'cleanliness': 'low',
    'landscape': 'low',
    'other': 'low',
}

FACILITY_ISSUE_PRIORITY = {
    'high': '2',
    'medium': '1',
    'low': '0',
    'critical': '3',
}


class CheckpointScan(models.Model):
    _inherit = 'checkpoint.scan'

    facility_issue_type = fields.Selection(
        selection=FACILITY_ISSUE_TYPES,
        string='Facility Issue Type',
        tracking=True,
    )
    facility_incident_id = fields.Many2one(
        'incident.report',
        string='Facility Work Order',
        copy=False,
        ondelete='set null',
        index=True,
    )

    @api.model
    def _facility_issue_type_label(self, issue_type):
        labels = dict(FACILITY_ISSUE_TYPES)
        return labels.get(issue_type, issue_type or _('Other'))

    def _sync_facility_issue_fields(self, issues_found, issue_type, issue_description):
        """Normalize issue flags from mobile / backend."""
        issues_found = bool(issues_found)
        issue_type = (issue_type or '').strip() or False
        issue_description = (issue_description or '').strip()
        if issues_found:
            if not issue_description or len(issue_description) < 10:
                raise ValidationError(
                    _('Please describe the facility issue (at least 10 characters).')
                )
            if not issue_type:
                raise ValidationError(_('Please select a facility issue type.'))
        else:
            issue_type = False
            issue_description = False
        return issues_found, issue_type, issue_description

    @api.model
    def _coerce_bool(self, value):
        """Parse booleans from JSON/mobile payloads reliably."""
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ('1', 'true', 'yes', 'on')
        if isinstance(value, (int, float)):
            return bool(value)
        return bool(value)

    def append_post_scan_evidence(
        self,
        photos_payload=None,
        videos_payload=None,
        observations_text=None,
        issues_found=None,
        facility_issue_type=None,
        issue_description=None,
    ):
        """Attach media/notes and optionally create or update a facility incident."""
        self.ensure_one()
        update_issue_fields = (
            issues_found is not None
            or facility_issue_type is not None
            or issue_description is not None
        )
        if update_issue_fields:
            issues_found, facility_issue_type, issue_description = (
                self._sync_facility_issue_fields(
                    self._coerce_bool(issues_found),
                    facility_issue_type or False,
                    issue_description or False,
                )
            )
        else:
            issues_found = bool(self.issues_found)
            facility_issue_type = self.facility_issue_type
            issue_description = self.issue_description

        photo_ids_new = self._photo_attachment_ids_from_payloads(photos_payload or [])
        video_ids_new = self._video_attachment_ids_from_payloads(videos_payload or [])
        obs = (observations_text or '').strip()
        vals = {}
        if photo_ids_new:
            vals['photo_ids'] = [(4, i) for i in photo_ids_new]
        if video_ids_new:
            vals['video_ids'] = [(4, i) for i in video_ids_new]
        if obs:
            if self.observations:
                vals['observations'] = (self.observations or '') + '\n' + obs
            else:
                vals['observations'] = obs
        if update_issue_fields:
            vals['issues_found'] = issues_found
            vals['facility_issue_type'] = facility_issue_type
            vals['issue_description'] = issue_description
        if vals:
            self.write(vals)

        facility_warning = None
        if issues_found:
            try:
                self._create_or_update_facility_incident()
            except Exception as exc:
                _logger.exception(
                    'Facility incident failed for checkpoint scan %s', self.id
                )
                facility_warning = str(exc)
        elif update_issue_fields and self.facility_incident_id:
            self.write({'facility_incident_id': False})

        return facility_warning

    def _create_or_update_facility_incident(self):
        """Create or update incident.report for FM follow-up."""
        self.ensure_one()
        if not self.issues_found:
            return self.env['incident.report']

        category = self.env['incident.report']._get_facility_patrol_category()
        if not category:
            raise ValidationError(
                _('Facility patrol category (FACILITY) is not configured. '
                  'Contact your administrator.')
            )

        issue_label = self._facility_issue_type_label(self.facility_issue_type)
        site_name = self.site_id.name or _('Site')
        cp_name = self.checkpoint_id.name or _('Checkpoint')
        title = '[FACILITY] %s – %s – %s' % (issue_label, cp_name, site_name)

        tour_ref = self.tour_log_id.name if self.tour_log_id else _('N/A')
        desc_lines = [
            '<p><strong>%s</strong></p>' % escape(self.issue_description or ''),
            '<p>%s: %s</p>' % (escape(_('Checkpoint')), escape(cp_name)),
            '<p>%s: %s</p>' % (escape(_('Site')), escape(site_name)),
            '<p>%s: %s</p>' % (escape(_('Tour log')), escape(tour_ref)),
            '<p>%s: %s</p>' % (
                escape(_('Scan time')),
                escape(fields.Datetime.to_string(self.scan_time) or ''),
            ),
            '<p>%s: %s</p>' % (escape(_('Guard')), escape(self.guard_id.name or '')),
        ]
        if self.observations:
            desc_lines.append(
                '<p>%s: %s</p>' % (
                    escape(_('Additional notes')),
                    escape(self.observations),
                )
            )
        description = Markup(''.join(desc_lines))

        severity = FACILITY_ISSUE_SEVERITY.get(self.facility_issue_type, 'low')
        priority = FACILITY_ISSUE_PRIORITY.get(severity, '0')

        incident_vals = {
            'title': title[:200],
            'description': description,
            'category_id': category.id,
            'site_id': self.site_id.id,
            'checkpoint_id': self.checkpoint_id.id,
            'guard_id': self.guard_id.id,
            'shift_id': self.shift_id.id or (
                self.tour_log_id.shift_id.id if self.tour_log_id else False
            ),
            'tour_log_id': self.tour_log_id.id if self.tour_log_id else False,
            'checkpoint_scan_id': self.id,
            'source': 'patrol_checkpoint',
            'incident_datetime': self.scan_time or fields.Datetime.now(),
            'severity': severity,
            'priority': priority,
            'location': cp_name,
            'latitude': self.latitude or self.checkpoint_id.latitude,
            'longitude': self.longitude or self.checkpoint_id.longitude,
            'status': 'submitted',
            'reported_datetime': fields.Datetime.now(),
        }
        Incident = self.env['incident.report'].sudo()
        if self.facility_incident_id:
            update_vals = {k: v for k, v in incident_vals.items() if k != 'status'}
            self.facility_incident_id.write(update_vals)
            incident = self.facility_incident_id
            self._link_scan_media_to_incident(incident)
            _logger.info(
                'Updated facility incident %s for checkpoint scan %s',
                incident.name, self.id,
            )
        else:
            incident = Incident.create(incident_vals)
            self.write({'facility_incident_id': incident.id})
            self._link_scan_media_to_incident(incident)
            _logger.info(
                'Created facility incident %s for checkpoint scan %s',
                incident.name, self.id,
            )
            try:
                incident._send_incident_notification()
            except Exception as exc:
                _logger.warning(
                    'Facility incident %s created but email failed: %s',
                    incident.name, exc,
                )
        return incident

    def _link_scan_media_to_incident(self, incident):
        """Copy scan attachments onto the incident (avoid res_model conflicts)."""
        Attachment = self.env['ir.attachment'].sudo()
        photo_cmds = []
        video_cmds = []
        for att in self.photo_ids:
            copy_att = Attachment.create({
                'name': att.name,
                'datas': att.datas,
                'res_model': 'incident.report',
                'res_id': incident.id,
                'mimetype': att.mimetype or 'image/jpeg',
            })
            photo_cmds.append(copy_att.id)
        for att in self.video_ids:
            copy_att = Attachment.create({
                'name': att.name,
                'datas': att.datas,
                'res_model': 'incident.report',
                'res_id': incident.id,
                'mimetype': att.mimetype or 'video/mp4',
            })
            video_cmds.append(copy_att.id)
        link_vals = {}
        if photo_cmds:
            link_vals['photo_ids'] = [(6, 0, photo_cmds)]
        if video_cmds:
            link_vals['video_ids'] = [(6, 0, video_cmds)]
        if link_vals:
            incident.write(link_vals)


class IncidentReport(models.Model):
    _inherit = 'incident.report'

    checkpoint_scan_id = fields.Many2one(
        'checkpoint.scan',
        string='Checkpoint Scan',
        ondelete='set null',
        index=True,
    )
    source = fields.Selection(
        [
            ('manual', 'Manual'),
            ('patrol_checkpoint', 'Patrol Checkpoint'),
            ('mobile', 'Mobile App'),
        ],
        string='Source',
        default='manual',
        index=True,
    )
    resolved_datetime = fields.Datetime(
        string='Resolved On',
        tracking=True,
        index=True,
    )
    facility_issue_type = fields.Selection(
        related='checkpoint_scan_id.facility_issue_type',
        string='Facility Issue Type',
        store=True,
        readonly=True,
    )
    is_facility_patrol = fields.Boolean(
        compute='_compute_is_facility_patrol',
        store=True,
        index=True,
    )

    @api.depends('category_id', 'category_id.code', 'source')
    def _compute_is_facility_patrol(self):
        for record in self:
            record.is_facility_patrol = (
                record.source == 'patrol_checkpoint'
                or (record.category_id.code == 'FACILITY')
            )

    @api.model
    def _get_facility_patrol_category(self):
        cat = self.env.ref(
            'guardpro.incident_cat_facility_patrol',
            raise_if_not_found=False,
        )
        if cat:
            return cat
        return self.env['incident.category'].search(
            [('code', '=', 'FACILITY')], limit=1
        )

    def write(self, vals):
        res = super().write(vals)
        if vals.get('status') in ('resolved', 'closed'):
            to_stamp = self.filtered(
                lambda r: r.is_facility_patrol and not r.resolved_datetime
            )
            if to_stamp:
                super(IncidentReport, to_stamp).write({
                    'resolved_datetime': fields.Datetime.now(),
                })
        return res

    def action_resolve(self):
        res = super().action_resolve()
        self.filtered(
            lambda i: i.is_facility_patrol and not i.resolved_datetime
        ).write({'resolved_datetime': fields.Datetime.now()})
        return res

    def action_close(self):
        res = super().action_close()
        self.filtered(
            lambda i: i.is_facility_patrol and not i.resolved_datetime
        ).write({'resolved_datetime': fields.Datetime.now()})
        return res
