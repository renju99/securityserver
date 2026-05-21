# -*- coding: utf-8 -*-
"""GuardPro mail template helpers (Odoo 18 inline {{ }} syntax)."""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

INCIDENT_CATEGORY_SUBMIT_SUBJECT = (
    'Incident Submitted: {{ object.name }} - {{ object.title }}'
)
INCIDENT_CATEGORY_SUBMIT_BODY = """<div style="font-family: Arial, sans-serif; padding: 20px;">
    <h2 style="color: #1f4e78; margin: 0 0 12px 0;">Incident Submitted</h2>
    <p style="margin: 0 0 16px 0;">
        A new incident has been submitted and requires review.
    </p>
    <table style="width: 100%; border-collapse: collapse; margin: 12px 0 18px 0;">
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold; width: 32%;">Incident Number</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.name }}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Title</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.title }}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Category</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.category_id.name ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Severity</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.severity ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Site</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.site_id.name ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ddd; font-weight: bold;">Reported By</td>
            <td style="padding: 8px; border: 1px solid #ddd;">{{ object.guard_id.name ||| '' }}</td>
        </tr>
    </table>
    <p style="margin: 0;">
        Incident details are attached as PDF when enabled on the category configuration.
    </p>
</div>"""

INCIDENT_NOTIFICATION_SUBJECT = (
    'New Incident Report: {{ object.name }} - {{ object.title }}'
)
INCIDENT_NOTIFICATION_BODY = """<div style="font-family: Arial, sans-serif; padding: 20px;">
    <h2 style="color: #d32f2f;">Incident Report Notification</h2>
    <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold; width: 30%;">Incident Number:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.name }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Title:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.title }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Severity:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.severity ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Category:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.category_id.name ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Site:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.site_id.name ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Reporting Guard:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.guard_id.name ||| '' }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Date/Time:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ format_datetime(object.incident_datetime, dt_format='medium') }}</td>
        </tr>
        <tr>
            <td style="padding: 10px; border: 1px solid #ddd; font-weight: bold;">Location:</td>
            <td style="padding: 10px; border: 1px solid #ddd;">{{ object.location ||| 'N/A' }}</td>
        </tr>
    </table>
    <h3>Description:</h3>
    <div style="padding: 15px; background: #f5f5f5; border-radius: 5px; margin: 20px 0;">
        {{ object.description }}
    </div>
    <div style="margin-top: 30px; padding: 15px; background: #e3f2fd; border-radius: 5px;">
        <p><strong>This is an automated notification from GuardLink.</strong></p>
        <p>Please review the incident in the system for full details and take appropriate action.</p>
    </div>
</div>"""


class MailTemplate(models.Model):
    _inherit = 'mail.template'

    @api.model
    def _guardpro_template_text_contains(self, value, needle):
        if not value:
            return False
        if isinstance(value, dict):
            return any(needle in (part or '') for part in value.values())
        return needle in (value or '')

    @api.model
    def _guardpro_migrate_odoo18_inline_templates(self):
        """Rewrite legacy ${} Mako mail templates to Odoo 18 {{ }} inline syntax."""
        specs = [
            (
                'guardpro.incident_category_submit_email_template',
                {
                    'subject': INCIDENT_CATEGORY_SUBMIT_SUBJECT,
                    'email_from': '{{ user.email_formatted }}',
                    'body_html': INCIDENT_CATEGORY_SUBMIT_BODY,
                },
            ),
            (
                'guardpro.incident_notification_email',
                {
                    'subject': INCIDENT_NOTIFICATION_SUBJECT,
                    'email_from': '{{ user.email_formatted }}',
                    'email_to': (
                        '{{ object.site_id.site_email or '
                        'object.site_id.client_id.email }}'
                    ),
                    'body_html': INCIDENT_NOTIFICATION_BODY,
                },
            ),
        ]
        for xmlid, vals in specs:
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if not template:
                _logger.warning('GuardPro: mail template %s not found', xmlid)
                continue
            needs_migration = (
                self._guardpro_template_text_contains(template.body_html, '${object')
                or self._guardpro_template_text_contains(template.subject, '${object')
                or self._guardpro_template_text_contains(template.email_from, '${')
            )
            if needs_migration:
                template.write(vals)
                _logger.info(
                    'GuardPro: migrated mail template %s to Odoo 18 syntax', xmlid
                )
