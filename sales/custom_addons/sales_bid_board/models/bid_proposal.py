from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BidProposal(models.Model):
    _name = "bid.proposal"
    _description = "Proposal (post approved Bid)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc, id desc"

    name = fields.Char(
        required=True,
        tracking=True,
        help="Short title for this proposal. Shown in lists and on printouts.",
    )
    reference = fields.Char(
        string="Reference number",
        copy=False,
        readonly=True,
        default="New",
        tracking=True,
        help="System proposal reference (e.g. PROP-00001). Assigned automatically when the record is saved.",
    )
    project_id = fields.Many2one(
        "bid.project",
        string="Source enquiry",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        help="Bid Board enquiry this proposal belongs to. Must be CSO-approved with a Bid decision.",
    )
    enquiry_code = fields.Char(
        related="project_id.code",
        string="Enquiry code",
        store=True,
        readonly=True,
        help="Code of the linked enquiry for quick cross-reference.",
    )
    sales_user_id = fields.Many2one(
        "res.users",
        string="Salesperson (raised bid)",
        required=True,
        tracking=True,
        default=lambda self: self.env.user,
        help="Sales owner for this proposal—typically the person who raised the bid on the enquiry.",
    )

    partner_company = fields.Char(
        string="Company",
        tracking=True,
        help="Client or end-customer name for this opportunity (as on the tender).",
    )
    parent_company = fields.Char(
        tracking=True,
        help="Ultimate parent or holding group above the operating company, if relevant.",
    )
    project_description = fields.Text(
        string="Project description",
        tracking=True,
        help="Summary of scope, buildings, and what is being tendered.",
    )
    industry = fields.Selection(
        [
            ("real_estate", "Real Estate"),
            ("hospitality", "Hospitality"),
            ("retail", "Retail"),
            ("healthcare", "Healthcare"),
            ("education", "Education"),
            ("government", "Government"),
            ("other", "Other"),
        ],
        tracking=True,
        help="Sector of the client or site (used for reporting and filtering).",
    )
    city = fields.Char(
        tracking=True,
        help="City or emirate where the work is performed.",
    )
    customer_type = fields.Selection(
        [("new", "New customer"), ("current", "Current customer")],
        string="New or current customer",
        tracking=True,
        help="Whether this is a new relationship or an existing Berkeley client.",
    )
    services_offered = fields.Text(
        string="Services offered",
        tracking=True,
        help="List the services in scope (e.g. cleaning, maintenance, security). Free text or comma-separated.",
    )
    # Scope of work (%): same as the linked Bid / No Bid enquiry; stored related fields stay in sync when the enquiry changes.
    scope_cleaning = fields.Float(
        related="project_id.scope_cleaning",
        string="Cleaning",
        readonly=True,
        store=True,
    )
    scope_maintenance = fields.Float(
        related="project_id.scope_maintenance",
        string="Maintenance",
        readonly=True,
        store=True,
    )
    scope_security = fields.Float(
        related="project_id.scope_security",
        string="Security",
        readonly=True,
        store=True,
    )
    scope_landscaping = fields.Float(
        related="project_id.scope_landscaping",
        string="Landscaping",
        readonly=True,
        store=True,
    )
    scope_laundry = fields.Float(
        related="project_id.scope_laundry",
        string="Laundry",
        readonly=True,
        store=True,
    )
    scope_support = fields.Float(
        related="project_id.scope_support",
        string="Support",
        readonly=True,
        store=True,
    )
    scope_others = fields.Float(
        related="project_id.scope_others",
        string="Others",
        readonly=True,
        store=True,
    )
    # Sum of scope lines (must not be related to project_id.scope_total: that target is computed on
    # bid.project and can prevent the field from registering in some Odoo versions / upgrade orders).
    scope_total = fields.Float(
        string="Scope total",
        compute="_compute_proposal_scope_total",
        store=True,
        readonly=True,
    )
    tender_type = fields.Selection(
        [
            ("new_contract", "New contract"),
            ("renewal", "Renewal"),
            ("extension", "Extension"),
            ("other", "Other"),
        ],
        string="Type of tender",
        tracking=True,
        help="Nature of the procurement: new award, renewal, extension, or other.",
    )

    initial_offer_date = fields.Date(
        string="Initial offer date",
        tracking=True,
        help="Date the first commercial offer was submitted to the client.",
    )
    revision_date = fields.Date(
        tracking=True,
        help="Date of the latest revised offer, if the client requested changes.",
    )
    decision_date = fields.Date(
        string="Decision date",
        tracking=True,
        help="Date the client is expected to announce the award (or the actual decision date).",
    )
    expected_start_date = fields.Date(
        string="Expected starting date",
        tracking=True,
        help="Planned contract or mobilisation start date if the bid is won.",
    )

    contract_volume_total = fields.Float(
        string="Total contract volume (full duration)",
        tracking=True,
        help="Total contract value over the full term (same currency as your standard, e.g. AED).",
    )
    contract_duration_months = fields.Integer(
        string="Expected contract duration (months)",
        tracking=True,
        help="Expected length of the contract in months (full term, not annualised).",
    )
    gm_percent = fields.Float(
        string="GM %",
        tracking=True,
        help="Expected gross margin as a percentage of revenue (e.g. 12 means 12%). "
        "Roughly: (revenue minus direct delivery cost) ÷ revenue × 100.",
    )
    win_probability = fields.Float(
        string="Probability % of winning",
        tracking=True,
        help="Your estimate of the chance of winning (0–100). Used for pipeline judgement, not a guarantee.",
    )

    outcome_status = fields.Selection(
        [("open", "Open"), ("won", "Won"), ("lost", "Lost")],
        string="Status",
        default="open",
        required=True,
        tracking=True,
        help="Pipeline outcome: Open (still competing), Won (awarded), or Lost (not awarded). "
        "Use the header buttons or status bar to change it.",
    )

    key_account_name = fields.Char(
        string="Key account name",
        tracking=True,
        help="Named account manager or key relationship owner for this client, if applicable.",
    )
    new_sales_fy = fields.Boolean(
        string="New sales (FY)",
        tracking=True,
        help="Tick if this win would count as new revenue for the current financial year reporting.",
    )

    contract_volume_annual = fields.Float(
        string="Contract volume p.a. (12 months, AED)",
        tracking=True,
        help="Annualised value on a 12-month basis (often used for budgeting and comparisons).",
    )
    offer_month = fields.Char(
        tracking=True,
        help="Month/year of the main offer (free text, e.g. 5-2024) for spreadsheet-style reporting.",
    )
    decision_month = fields.Char(
        tracking=True,
        help="Month/year when the client decision is due or was taken (free text).",
    )
    starting_month = fields.Char(
        tracking=True,
        help="Month/year when work is expected to start (free text).",
    )

    active = fields.Boolean(
        default=True,
        help="Uncheck to archive the proposal. It stays in the database but is hidden from normal lists.",
    )

    @api.depends(
        "project_id",
        "project_id.scope_cleaning",
        "project_id.scope_maintenance",
        "project_id.scope_security",
        "project_id.scope_landscaping",
        "project_id.scope_laundry",
        "project_id.scope_support",
        "project_id.scope_others",
    )
    def _compute_proposal_scope_total(self):
        """Mirror enquiry total; depend on project fields (not related copies) so stored values stay correct."""
        for rec in self:
            p = rec.project_id
            rec.scope_total = float(p.scope_total) if p else 0.0

    @api.constrains("project_id")
    def _check_project_bid_approved(self):
        for rec in self:
            p = rec.project_id
            if not p:
                continue
            if p.review_status != "approved" or p.decision_final != "bid":
                raise ValidationError(
                    _("Proposals can only be linked to enquiries that are approved with a Bid decision.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", "New") == "New":
                vals["reference"] = self.env["ir.sequence"].next_by_code("bid.proposal") or _("New")
            if not vals.get("name") and vals.get("project_id"):
                proj = self.env["bid.project"].browse(vals["project_id"])
                vals["name"] = f"{proj.name} ({vals['reference']})"
        return super().create(vals_list)

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if not self.project_id:
            return
        data = self.project_id._prepare_proposal_default_values()
        for fname, value in data.items():
            if fname in self._fields and not getattr(self, fname, None):
                setattr(self, fname, value)

    def write(self, vals):
        if "project_id" in vals and vals["project_id"]:
            proj = self.env["bid.project"].browse(vals["project_id"])
            if proj.review_status != "approved" or proj.decision_final != "bid":
                raise ValidationError(
                    _("Proposals can only be linked to enquiries that are approved with a Bid decision.")
                )
        return super().write(vals)

    def _set_outcome_status(self, status):
        allowed = {"open", "won", "lost"}
        if status not in allowed:
            raise ValidationError(_("Invalid proposal status."))
        to_update = self.filtered(lambda r: r.outcome_status != status)
        if to_update:
            to_update.write({"outcome_status": status})
        return True

    def action_proposal_set_outcome_open(self):
        return self._set_outcome_status("open")

    def action_proposal_set_outcome_won(self):
        return self._set_outcome_status("won")

    def action_proposal_set_outcome_lost(self):
        return self._set_outcome_status("lost")
