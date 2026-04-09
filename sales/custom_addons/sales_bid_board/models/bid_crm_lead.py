from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmLead(models.Model):
    _inherit = "crm.lead"

    bid_intake_scope_of_work = fields.Selection(
        [
            ("ifm", "IFM"),
            ("cleaning", "Cleaning"),
            ("maintenance", "Maintenance"),
            ("landscape", "Landscape"),
            ("laundry", "Laundry"),
            ("security", "Security"),
        ],
        string="Scope of Work",
        tracking=True,
    )
    bid_intake_location = fields.Char(string="Location", tracking=True)
    bid_intake_comments_source = fields.Text(string="Comments / Source", tracking=True)
    bid_intake_opportunity_date = fields.Date(
        string="Date of Opportunity",
        default=fields.Date.context_today,
        tracking=True,
    )
    bid_intake_opportunity_month = fields.Char(
        string="Month of Opportunity",
        compute="_compute_bid_intake_opportunity_month",
        store=True,
        readonly=True,
    )
    bid_intake_details_remarks = fields.Text(string="Details / Remarks", tracking=True)
    bid_intake_status = fields.Char(string="Status", tracking=True)

    @api.depends("bid_intake_opportunity_date")
    def _compute_bid_intake_opportunity_month(self):
        for lead in self:
            d = lead.bid_intake_opportunity_date
            if d:
                dt = fields.Date.to_date(d)
                lead.bid_intake_opportunity_month = dt.strftime("%B %Y")
            else:
                lead.bid_intake_opportunity_month = False

    @api.model
    def _bid_board_effective_type_from_vals(self, vals):
        if vals.get("type"):
            return vals["type"]
        return self.env.context.get("default_type")

    @api.model
    def _bid_board_prepare_lead_vals(self, vals):
        """Fill company / contact text from partner when missing (quick-create, imports)."""
        vals = dict(vals)
        if self._bid_board_effective_type_from_vals(vals) != "lead":
            return vals
        pid = vals.get("partner_id")
        if not pid:
            return vals
        partner_id = pid if isinstance(pid, int) else None
        if not partner_id:
            return vals
        partner = self.env["res.partner"].browse(partner_id)
        if not partner.exists():
            return vals
        if not (vals.get("partner_name") or "").strip():
            vals["partner_name"] = partner.commercial_partner_id.name or partner.name or ""
        if not (vals.get("contact_name") or "").strip() and not partner.is_company:
            vals["contact_name"] = partner.name or ""
        return vals

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._bid_board_prepare_lead_vals(v) for v in vals_list]
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("bid_board_lead_sync"):
            return res
        to_patch = self.filtered(lambda l: l.type == "lead")
        for lead in to_patch:
            patch = {}
            if lead.partner_id:
                if not (lead.partner_name or "").strip():
                    patch["partner_name"] = (
                        lead.partner_id.commercial_partner_id.name or lead.partner_id.name or ""
                    )
                if not (lead.contact_name or "").strip() and not lead.partner_id.is_company:
                    patch["contact_name"] = lead.partner_id.name or ""
            if patch:
                lead.with_context(bid_board_lead_sync=True).write(patch)
        return res

    @api.depends_context("uid")
    @api.depends("partner_id", "type")
    def _compute_is_partner_visible(self):
        """Show Customer (partner) on lead forms — required for FM intake."""
        is_debug_mode = self.env.user.has_group("base.group_no_one")
        for lead in self:
            if lead.type == "lead":
                lead.is_partner_visible = True
            else:
                lead.is_partner_visible = bool(
                    lead.type == "opportunity" or lead.partner_id or is_debug_mode
                )

    @api.constrains("partner_id", "partner_name", "contact_name", "type")
    def _bid_board_check_lead_customer_mandatory(self):
        for lead in self:
            if lead.type != "lead":
                continue
            if not lead.partner_id:
                raise ValidationError(_("Customer is required on leads."))
            if not (lead.partner_name or "").strip():
                raise ValidationError(_("Customer Name is required on leads."))
            if not (lead.contact_name or "").strip():
                raise ValidationError(_("Contact Name is required on leads."))
