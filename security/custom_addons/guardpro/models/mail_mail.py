# -*- coding: utf-8 -*-
"""mail.mail retention — auto-remove old email queue rows (not chatter)."""

from datetime import timedelta
import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class MailMail(models.Model):
    """Purge old mail.mail records after configurable retention (default 365 days)."""

    _inherit = 'mail.mail'

    @api.model
    def guardpro_cron_purge_old_records(self):
        """Delete ``mail.mail`` rows older than retention days.

        * **Removes:** rows in the ``mail_mail`` table (outgoing/sent/exception queue).
        * **Does not remove:** ``mail.message`` chatter / document history — that audit trail stays.

        Retention is controlled by ``guardpro.mail_mail_retention_days`` (default **365**).
        """
        param = self.env['ir.config_parameter'].sudo().get_param(
            'guardpro.mail_mail_retention_days', '365'
        )
        try:
            days = max(int(param or 365), 1)
        except (TypeError, ValueError):
            days = 365

        cutoff = fields.Datetime.now() - timedelta(days=days)
        domain = [('create_date', '<', cutoff)]

        total = 0
        batch_size = 3000
        while True:
            batch = self.sudo().search(domain, limit=batch_size, order='id')
            if not batch:
                break
            n = len(batch)
            batch.unlink()
            total += n

        if total:
            _logger.info(
                'GuardLink mail.mail retention: removed %s record(s) with create_date before %s '
                '(retention %s days)',
                total,
                cutoff,
                days,
            )
        return True
