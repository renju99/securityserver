# -*- coding: utf-8 -*-
"""GuardPro mail template helpers (Odoo 18 QWeb body + inline syntax)."""

import logging

from odoo import api, models

_logger = logging.getLogger(__name__)

_INCIDENT_CATEGORY_SUBMIT_SUBJECT = (
    'Incident Submitted: {{ object.name }} - {{ object.title }}'
)
_INCIDENT_CATEGORY_SUBMIT_BODY = """<div style="background-color: #f4f6f8; padding: 24px 12px; font-family: Arial, Helvetica, sans-serif;">
    <table align="center" width="600" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-collapse: collapse;">
        <tr>
            <td style="background: linear-gradient(135deg, #1a237e 0%, #283593 100%); padding: 28px 32px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">GuardLink</h1>
                <p style="color: #ffffff; margin: 6px 0 0; font-size: 14px;">Incident Notification</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 32px 32px 20px;">
                <h2 style="color: #1a237e; margin: 0 0 10px; font-size: 22px;">Incident Submitted</h2>
                <p style="color: #555555; margin: 0; font-size: 15px; line-height: 1.6;">
                    A new incident has been submitted and requires review. A PDF report is attached to this email.
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 24px;">
                <table width="100%" style="border-collapse: collapse; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; width: 35%; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Incident Number</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Title</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.title or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Category</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.category_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Severity</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">
                            <t t-if="object.severity">
                                <span t-attf-style="display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; text-transform: uppercase; background-color: {{ {'critical':'#d32f2f','high':'#f57c00','medium':'#fbc02d','low':'#388e3c'}.get(object.severity, '#757575') }}; color: #ffffff;">
                                    <t t-out="object.severity.upper()"/>
                                </span>
                            </t>
                            <t t-else=""/>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Project</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.site_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #f5f7fa; font-weight: 600; color: #333333; font-size: 14px;">Reported By</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px;"><t t-out="object.guard_id.name or ''"/></td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 28px;">
                <h3 style="color: #1a237e; margin: 0 0 10px; font-size: 16px;">Description</h3>
                <div style="padding: 16px; background-color: #f8f9fa; border-left: 4px solid #1a237e; border-radius: 6px; color: #444444; font-size: 14px; line-height: 1.6;">
                    <t t-out="object.description or 'No description provided.'"/>
                </div>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 32px; text-align: center;">
                <a t-attf-href="/guardpro/mobile/incident/{{ object.id }}" style="display: inline-block; padding: 14px 32px; background-color: #1a237e; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px;">View Incident</a>
            </td>
        </tr>
        <tr>
            <td style="background-color: #f4f6f8; padding: 20px 32px; text-align: center; border-top: 1px solid #e0e0e0;">
                <p style="margin: 0; color: #777777; font-size: 12px; line-height: 1.5;">
                    This is an automated notification from GuardLink.<br/>Please do not reply directly to this email.
                </p>
            </td>
        </tr>
    </table>
</div>"""

_INCIDENT_NOTIFICATION_SUBJECT = (
    'New Incident Report: {{ object.name }} - {{ object.title }}'
)
_INCIDENT_NOTIFICATION_BODY = """<div style="background-color: #f4f6f8; padding: 24px 12px; font-family: Arial, Helvetica, sans-serif;">
    <table align="center" width="600" style="max-width: 600px; width: 100%; background-color: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(0,0,0,0.08); border-collapse: collapse;">
        <tr>
            <td style="background: linear-gradient(135deg, #d32f2f 0%, #b71c1c 100%); padding: 28px 32px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">GuardLink</h1>
                <p style="color: #ffffff; margin: 6px 0 0; font-size: 14px;">Incident Alert</p>
            </td>
        </tr>
        <tr>
            <td style="padding: 32px 32px 20px;">
                <h2 style="color: #d32f2f; margin: 0 0 10px; font-size: 22px;">New Incident Report</h2>
                <p style="color: #555555; margin: 0; font-size: 15px; line-height: 1.6;">
                    A new incident has been reported and requires your attention.
                </p>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 24px;">
                <table width="100%" style="border-collapse: collapse; border: 1px solid #e0e0e0; border-radius: 8px; overflow: hidden;">
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; width: 35%; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Incident Number</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Title</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.title or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Severity</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">
                            <t t-if="object.severity">
                                <span t-attf-style="display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; text-transform: uppercase; background-color: {{ {'critical':'#d32f2f','high':'#f57c00','medium':'#fbc02d','low':'#388e3c'}.get(object.severity, '#757575') }}; color: #ffffff;">
                                    <t t-out="object.severity.upper()"/>
                                </span>
                            </t>
                            <t t-else=""/>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Category</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.category_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Site</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.site_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Reporting Guard</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="object.guard_id.name or ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;">Date / Time</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px; border-bottom: 1px solid #e0e0e0;"><t t-out="format_datetime(object.incident_datetime, dt_format='medium') if object.incident_datetime else ''"/></td>
                    </tr>
                    <tr>
                        <td style="padding: 12px 16px; background-color: #fff3f3; font-weight: 600; color: #333333; font-size: 14px;">Location</td>
                        <td style="padding: 12px 16px; color: #333333; font-size: 14px;"><t t-out="object.location or 'N/A'"/></td>
                    </tr>
                </table>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 28px;">
                <h3 style="color: #d32f2f; margin: 0 0 10px; font-size: 16px;">Description</h3>
                <div style="padding: 16px; background-color: #fff8f8; border-left: 4px solid #d32f2f; border-radius: 6px; color: #444444; font-size: 14px; line-height: 1.6;">
                    <t t-out="object.description or 'No description provided.'"/>
                </div>
            </td>
        </tr>
        <tr>
            <td style="padding: 0 32px 32px; text-align: center;">
                <a t-attf-href="/guardpro/mobile/incident/{{ object.id }}" style="display: inline-block; padding: 14px 32px; background-color: #d32f2f; color: #ffffff; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 15px;">View Incident</a>
            </td>
        </tr>
        <tr>
            <td style="background-color: #f4f6f8; padding: 20px 32px; text-align: center; border-top: 1px solid #e0e0e0;">
                <p style="margin: 0; color: #777777; font-size: 12px; line-height: 1.5;">
                    This is an automated notification from GuardLink.<br/>Please do not reply directly to this email.
                </p>
            </td>
        </tr>
    </table>
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
    def _guardpro_template_needs_migration(self, template):
        """Detect legacy Mako (${}) or broken inline (|||) syntax."""
        fields = (template.subject, template.email_from, template.email_to, template.body_html)
        text = '\n'.join(
            ' '.join(v.values()) if isinstance(v, dict) else (v or '')
            for v in fields
        )
        return (
            '${' in text
            or '|||' in text
            or (
                '{{ object' in text
                and '<t t-out' not in text
            )
        )

    @api.model
    def _guardpro_clean_email_fields(self):
        """Remove nested JSON wrappers, |safe filters, and whitespace from email headers."""
        import json
        import re

        self.env.cr.execute("""
            SELECT imd.name, imd.res_id
            FROM ir_model_data imd
            WHERE imd.model = 'mail.template' AND imd.module = 'guardpro'
        """)
        for name, res_id in self.env.cr.fetchall():
            template = self.browse(res_id)
            if not template.exists():
                continue
            vals = {}
            for field_name in ('email_from', 'email_to', 'reply_to'):
                original = getattr(template, field_name)
                value = original
                if not value or value == 'null':
                    continue
                # unwrap translation dicts and nested JSON strings
                while True:
                    if isinstance(value, dict):
                        value = value.get('en_US', '')
                    elif isinstance(value, str):
                        value = value.strip()
                        if value.startswith('{"en_US"'):
                            try:
                                value = json.loads(value).get('en_US', '')
                            except Exception:
                                break
                        else:
                            break
                    else:
                        break
                    if not value or value == 'null':
                        break
                if not value or value == 'null':
                    if original not in (False, None, ''):
                        vals[field_name] = False
                    continue
                # Jinja |safe is not valid in inline expressions
                value = re.sub(r'\s*\|\s*safe', '', value)
                if value != original:
                    vals[field_name] = value
            if vals:
                template.write(vals)
                _logger.info('GuardPro: cleaned email fields for %s', name)

    @api.model
    def _guardpro_migrate_odoo18_inline_templates(self):
        """Rewrite legacy/broken mail templates to Odoo 18 QWeb + inline syntax."""
        report_action = self.env.ref('guardpro.action_report_incident', raise_if_not_found=False)
        report_id = report_action.id if report_action else False
        specs = [
            (
                'guardpro.incident_category_submit_email_template',
                {
                    'subject': _INCIDENT_CATEGORY_SUBMIT_SUBJECT,
                    'email_from': '{{ user.email_formatted }}',
                    'body_html': _INCIDENT_CATEGORY_SUBMIT_BODY,
                },
            ),
            (
                'guardpro.incident_notification_email',
                {
                    'subject': _INCIDENT_NOTIFICATION_SUBJECT,
                    'email_from': '{{ user.email_formatted }}',
                    'email_to': (
                        '{{ object.site_id.site_email or '
                        'object.site_id.client_id.email }}'
                    ),
                    'body_html': _INCIDENT_NOTIFICATION_BODY,
                },
            ),
        ]
        if report_id:
            for xmlid, vals in specs:
                vals['report_template_ids'] = [(4, report_id)]
        for xmlid, vals in specs:
            template = self.env.ref(xmlid, raise_if_not_found=False)
            if not template:
                _logger.warning('GuardPro: mail template %s not found', xmlid)
                continue
            if self._guardpro_template_needs_migration(template):
                template.write(vals)
                _logger.info(
                    'GuardPro: migrated mail template %s to Odoo 18 syntax', xmlid
                )
        self._guardpro_clean_email_fields()
