# -*- coding: utf-8 -*-
"""GuardLink mail activity controls."""

from odoo import api, models


class MailActivity(models.Model):
    """Suppress assignment emails for GuardLink activity records."""

    _inherit = 'mail.activity'

    _GUARDPRO_ACTIVITY_PREFIXES = (
        'guard.',
        'geofence.',
        'incident.',
        'tour.',
        'checkpoint.',
        'visitor.',
        'package.',
        'key.',
        'compliance.',
        'daily.activity.',
        'sla.',
        'lost.found',
        'tenant.resident',
        'resident.complaint',
        'emergency.',
        'equipment.',
        'client.site',
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Create activities while suppressing noisy email assignments."""
        created = self.browse()
        model_registry = self.env['ir.model'].sudo()

        for vals in vals_list:
            model_name = False
            res_model_id = vals.get('res_model_id')
            if res_model_id:
                model_name = model_registry.browse(res_model_id).model

            should_suppress = (
                model_name
                and model_name.startswith(self._GUARDPRO_ACTIVITY_PREFIXES)
                and not self.env.context.get('guardpro_allow_activity_email')
            )

            if should_suppress:
                # Odoo 18: only mail_activity_quick_update skips assignment emails
                # (see mail.activity.create — wrong key does nothing).
                rec = super(
                    MailActivity,
                    self.with_context(mail_activity_quick_update=True),
                ).create(vals)
            else:
                rec = super().create(vals)

            created |= rec

        return created
