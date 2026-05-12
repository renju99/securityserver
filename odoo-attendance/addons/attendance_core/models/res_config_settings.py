# -*- coding: utf-8 -*-
from odoo import api, fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    bw_legacy_migration_html = fields.Html(
        string='Legacy attendance app (JWT / org switcher)',
        compute='_compute_bw_legacy_migration_html',
        sanitize=False,
    )

    @api.depends('company_id')
    def _compute_bw_legacy_migration_html(self):
        body = """
        <div class="o_form_sheet">
            <p><strong>Organisations and authentication</strong></p>
            <p>The standalone Node/React “Workforce Attendance” app used per-organisation JWT logins.
            In Odoo this is replaced by <strong>Companies</strong> (multi-company) and standard
            <strong>Users</strong> with access rights and groups.</p>
            <ul>
                <li>Enable <strong>Multi companies</strong> under Settings → General Settings if you need several orgs.</li>
                <li>Create one <strong>company</strong> per legacy organisation and assign users to the right company.</li>
                <li>Use <strong>HR → Employees / Users</strong> instead of the legacy HR user API.</li>
            </ul>
            <p><strong>Odoo → Odoo attendance replication</strong> is configured under
            <em>Berkeley Workforce → Odoo → Odoo sync</em>
            (target instances, per-employee routing, replication queue).</p>
        </div>
        """
        for rec in self:
            rec.bw_legacy_migration_html = body
