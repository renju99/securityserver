from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .bid_email_layout import render_bid_board_email
from .bid_project import BID_INDUSTRY_SELECTION

# Aligned with bid.project contract_type keys; labels match the proposals register / scorecard wording.
BID_PROPOSAL_PROCUREMENT_SELECTION = [
    ("ifm", "IFM"),
    ("bundled", "Bundled Services"),
    ("single", "OSS"),
]


def _many2one_id_from_write_value(value):
    if not value:
        return False
    if isinstance(value, int):
        return value
    return value.id


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
        string="Reference Number",
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
        string="Parent Company",
        tracking=True,
        help="Ultimate parent or holding group above the operating company, if relevant.",
    )
    project_description = fields.Text(
        string="Project Description",
        tracking=True,
        help="Summary of scope, buildings, and what is being tendered.",
    )
    industry = fields.Selection(
        BID_INDUSTRY_SELECTION,
        string="Industry",
        tracking=True,
        help="Sector of the client or site (used for reporting and filtering).",
    )
    city = fields.Char(
        string="City",
        tracking=True,
        help="City or emirate where the work is performed.",
    )
    customer_type = fields.Selection(
        [("new", "New"), ("current", "Current")],
        string="New or current customer?",
        tracking=True,
        help="Whether this is a new relationship or an existing Berkeley client.",
    )
    services_offered = fields.Text(
        string="Services offered",
        tracking=True,
        help="List the services in scope (e.g. cleaning, maintenance, security). Free text or comma-separated.",
    )
    # Scope of work (%): always read from the linked Bid / No-Bid enquiry (not stored on proposal).
    scope_cleaning = fields.Float(
        related="project_id.scope_cleaning",
        string="Cleaning",
        readonly=True,
    )
    scope_maintenance = fields.Float(
        related="project_id.scope_maintenance",
        string="Maintenance",
        readonly=True,
    )
    scope_security = fields.Float(
        related="project_id.scope_security",
        string="Security",
        readonly=True,
    )
    scope_landscaping = fields.Float(
        related="project_id.scope_landscaping",
        string="Landscaping",
        readonly=True,
    )
    scope_laundry = fields.Float(
        related="project_id.scope_laundry",
        string="Laundry",
        readonly=True,
    )
    scope_support = fields.Float(
        related="project_id.scope_support",
        string="Support",
        readonly=True,
    )
    scope_others = fields.Float(
        related="project_id.scope_others",
        string="Others",
        readonly=True,
    )
    # Sum of scope lines (must not be related to project_id.scope_total: that target is computed on
    # bid.project and can prevent the field from registering in some Odoo versions / upgrade orders).
    scope_total = fields.Float(
        string="Scope total",
        compute="_compute_proposal_scope_total",
        store=True,
        readonly=True,
    )
    service_procurement_option = fields.Selection(
        BID_PROPOSAL_PROCUREMENT_SELECTION,
        string="Service Procurement Option",
        tracking=True,
        help="How services are procured (aligned with enquiry contract shape: IFM, bundled, or OSS).",
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
        string="Initial Offer Date",
        tracking=True,
        help="Date the first commercial offer was submitted to the client.",
    )
    revision_date = fields.Date(
        string="Revision Date",
        tracking=True,
        help="Date of the latest revised offer, if the client requested changes.",
    )
    decision_date = fields.Date(
        string="Decision date",
        tracking=True,
        help="Date the client is expected to announce the award (or the actual decision date).",
    )
    deadline_date = fields.Date(
        string="Deadline date",
        tracking=True,
        help="Key deadline for this proposal (e.g. offer due, client reply, or internal milestone). "
        "Drives the proposal deadline calendar and a one-time email to the salesperson 30 days before this date.",
    )
    deadline_one_month_notified_at = fields.Datetime(
        string="30-day deadline reminder sent",
        copy=False,
        help="Set when the salesperson was emailed that the proposal deadline is in 30 days. "
        "Clears when the deadline date changes.",
    )
    expected_start_date = fields.Date(
        string="Expected starting date",
        tracking=True,
        help="Planned contract or mobilisation start date if the bid is won.",
    )

    contract_volume_total = fields.Float(
        string="Total Contract Volume (full duration)",
        tracking=True,
        help="Total contract value over the full term (same currency as your standard, e.g. AED).",
    )
    contract_duration_months = fields.Integer(
        string="Exp. contract duration in months",
        tracking=True,
        help="Expected length of the contract in months (full term, not annualised).",
    )
    contract_start_date = fields.Date(
        string="Contract Start",
        tracking=True,
        help="Date the awarded contract starts (mobilisation or service start).",
    )
    contract_expiry_date = fields.Date(
        string="Expiry Date",
        tracking=True,
        help="Date the awarded contract ends.",
    )
    is_active_contract = fields.Boolean(
        string="Active contract",
        compute="_compute_is_active_contract",
        store=True,
        index=True,
        help="Won proposal with both contract dates set and today within the contract period.",
    )
    gm_percent = fields.Float(
        string="DB P%",
        tracking=True,
        help="DB P% as used on the proposals register (percentage).",
    )
    win_probability = fields.Float(
        string="Probability of winning in %",
        tracking=True,
        help="Your estimate of the chance of winning (0–100). Used for pipeline judgement, not a guarantee.",
    )

    outcome_status = fields.Selection(
        [
            ("open", "Open"),
            ("submitted", "Submitted"),
            ("revision", "Revision"),
            ("won", "Won"),
            ("lost", "Lost"),
        ],
        string="Proposal status",
        default="open",
        required=True,
        tracking=True,
        help="Open → Submitted → Revision (as needed) → Submitted again after each revision cycle → Won or Lost. "
        "Use the status bar or header actions.",
    )
    revision_number = fields.Integer(
        string="Revision number",
        default=0,
        tracking=True,
        help="Increments automatically when the status moves to Revision; you can adjust manually if needed.",
    )

    key_account_name = fields.Char(
        string="Key account Berkeley",
        tracking=True,
        help="Key account / relationship field for Berkeley (name or note as on the register).",
    )
    new_sales_fy = fields.Boolean(
        string="New Sales for the Current Year?",
        tracking=True,
        help="Tick if this opportunity counts as new sales for the current financial year reporting.",
    )

    contract_volume_annual = fields.Float(
        string="Contract volume p.a. in AED (12 months basis)",
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
    proposal_deadline_calendar_start = fields.Datetime(
        string="Deadline (calendar)",
        compute="_compute_proposal_deadline_calendar_start",
        store=True,
        help="Start of the proposal deadline date for calendar views that show only records with a deadline.",
    )
    bid_calendar_start = fields.Datetime(
        string="Calendar date",
        compute="_compute_bid_proposal_calendar",
        store=True,
        help="Deadline date if set, else decision / expected start / initial offer / created on.",
    )
    bid_calendar_color = fields.Integer(
        string="Calendar color",
        compute="_compute_bid_proposal_calendar",
        store=True,
        help="Open pipeline urgency vs won/lost; same palette as enquiries.",
    )

    @api.depends(
        "active",
        "outcome_status",
        "contract_start_date",
        "contract_expiry_date",
    )
    def _compute_is_active_contract(self):
        today = fields.Date.context_today(self)
        for rec in self:
            rec.is_active_contract = bool(
                rec.active
                and rec.outcome_status == "won"
                and rec.contract_start_date
                and rec.contract_expiry_date
                and rec.contract_start_date <= today <= rec.contract_expiry_date
            )

    @api.depends("deadline_date", "active")
    def _compute_proposal_deadline_calendar_start(self):
        for rec in self:
            if rec.active and rec.deadline_date:
                rec.proposal_deadline_calendar_start = fields.Datetime.to_datetime(rec.deadline_date)
            else:
                rec.proposal_deadline_calendar_start = False

    @api.depends(
        "deadline_date",
        "decision_date",
        "expected_start_date",
        "initial_offer_date",
        "create_date",
        "outcome_status",
    )
    def _compute_bid_proposal_calendar(self):
        today = fields.Date.context_today(self)
        for rec in self:
            d = (
                rec.deadline_date
                or rec.decision_date
                or rec.expected_start_date
                or rec.initial_offer_date
            )
            if d:
                rec.bid_calendar_start = fields.Datetime.to_datetime(d)
                anchor_date = d
            elif rec.create_date:
                rec.bid_calendar_start = rec.create_date
                anchor_date = fields.Date.to_date(rec.create_date)
            else:
                rec.bid_calendar_start = False
                rec.bid_calendar_color = 0
                continue
            if rec.outcome_status == "won":
                rec.bid_calendar_color = 10
            elif rec.outcome_status == "lost":
                rec.bid_calendar_color = 11
            elif rec.outcome_status == "revision":
                rec.bid_calendar_color = 7
            elif rec.outcome_status == "submitted":
                rec.bid_calendar_color = 6
            elif anchor_date < today:
                rec.bid_calendar_color = 1
            elif anchor_date <= today + timedelta(days=7):
                rec.bid_calendar_color = 2
            elif anchor_date <= today + timedelta(days=30):
                rec.bid_calendar_color = 3
            else:
                rec.bid_calendar_color = 4

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

    def _proposal_missing_labels_for_won(self, vals=None):
        """Register fields that must be set before outcome can be Won (merged with pending vals on write)."""
        self.ensure_one()
        vals = vals or {}

        def eff(name):
            if name in vals:
                v = vals[name]
                if self._fields[name].type == "many2one":
                    return _many2one_id_from_write_value(v)
                return v
            return self[name]

        missing = []

        if not (eff("partner_company") or "").strip():
            missing.append(_("Company"))
        desc = eff("project_description")
        if not (desc or "").strip():
            missing.append(_("Project Description"))
        if not eff("industry"):
            missing.append(_("Industry"))
        if not (eff("city") or "").strip():
            missing.append(_("City"))
        if not eff("customer_type"):
            missing.append(_("New or current customer?"))
        offered = eff("services_offered")
        if not (offered or "").strip():
            missing.append(_("Services offered"))
        if not eff("service_procurement_option"):
            missing.append(_("Service Procurement Option"))
        if not eff("tender_type"):
            missing.append(_("Type of tender"))

        try:
            vol_ok = float(eff("contract_volume_total") or 0) > 0
        except (TypeError, ValueError):
            vol_ok = False
        if not vol_ok:
            missing.append(_("Total Contract Volume (full duration)"))

        try:
            dur_ok = int(eff("contract_duration_months") or 0) > 0
        except (TypeError, ValueError):
            dur_ok = False
        if not dur_ok:
            missing.append(_("Exp. contract duration in months"))

        if not eff("initial_offer_date"):
            missing.append(_("Initial Offer Date"))
        if not eff("decision_date"):
            missing.append(_("Decision date"))
        if not eff("expected_start_date"):
            missing.append(_("Expected starting date"))

        if not eff("sales_user_id"):
            missing.append(_("Salesperson (raised bid)"))

        return missing

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("reference", "New") == "New":
                vals["reference"] = self.env["ir.sequence"].next_by_code("bid.proposal") or _("New")
            if not vals.get("name") and vals.get("project_id"):
                proj = self.env["bid.project"].browse(vals["project_id"])
                vals["name"] = f"{proj.name} ({vals['reference']})"
            pid = vals.get("project_id")
            if pid and not (vals.get("services_offered") or "").strip():
                proj = self.env["bid.project"].browse(pid)
                vals["services_offered"] = proj._proposal_scope_work_summary()
            if vals.get("outcome_status") == "revision" and not vals.get("revision_number"):
                vals["revision_number"] = 1
            if vals.get("outcome_status") == "won":
                probe = self.new(vals)
                miss = probe._proposal_missing_labels_for_won()
                if miss:
                    raise ValidationError(
                        _("Complete the proposal register before marking it as Won:")
                        + "\n"
                        + "\n".join("• %s" % m for m in miss)
                    )
        return super().create(vals_list)

    @api.onchange("project_id")
    def _onchange_project_id(self):
        if not self.project_id:
            return
        data = self.project_id._prepare_proposal_default_values()
        for fname, value in data.items():
            if fname not in self._fields or fname == "project_id":
                continue
            if fname == "services_offered":
                setattr(self, fname, value)
                continue
            if not getattr(self, fname, None):
                setattr(self, fname, value)

    def write(self, vals):
        vals = dict(vals)
        if "deadline_date" in vals:
            vals["deadline_one_month_notified_at"] = False
        if "project_id" in vals and vals["project_id"]:
            proj = self.env["bid.project"].browse(vals["project_id"])
            if proj.review_status != "approved" or proj.decision_final != "bid":
                raise ValidationError(
                    _("Proposals can only be linked to enquiries that are approved with a Bid decision.")
                )
        sync_scope_text = bool(vals.get("project_id"))
        new_status = vals.get("outcome_status")
        if new_status == "won":
            for rec in self:
                miss = rec._proposal_missing_labels_for_won(vals)
                if miss:
                    raise ValidationError(
                        _("Complete the proposal register before marking it as Won:")
                        + "\n"
                        + "\n".join("• %s" % m for m in miss)
                    )
        if new_status == "revision":
            for rec in self:
                subvals = dict(vals)
                if rec.outcome_status != "revision":
                    subvals["revision_number"] = rec.revision_number + 1
                super(BidProposal, rec).write(subvals)
            return True
        res = super().write(vals)
        if sync_scope_text:
            for rec in self:
                if rec.project_id:
                    super(BidProposal, rec).write(
                        {"services_offered": rec.project_id._proposal_scope_work_summary()}
                    )
        return res

    def _set_outcome_status(self, status):
        allowed = {"open", "submitted", "revision", "won", "lost"}
        if status not in allowed:
            raise ValidationError(_("Invalid proposal status."))
        to_update = self.filtered(lambda r: r.outcome_status != status)
        if to_update:
            to_update.write({"outcome_status": status})
        return True

    def action_proposal_set_outcome_open(self):
        return self._set_outcome_status("open")

    def action_proposal_set_outcome_submitted(self):
        return self._set_outcome_status("submitted")

    def action_proposal_set_outcome_revision(self):
        return self._set_outcome_status("revision")

    def action_proposal_set_outcome_won(self):
        return self._set_outcome_status("won")

    def action_proposal_set_outcome_lost(self):
        return self._set_outcome_status("lost")

    def _proposal_notification_email_from(self):
        self.ensure_one()
        return self.env["bid.board.settings"].sudo().get_singleton().resolve_notification_email_from()

    def _send_proposal_notification_email(self, recipients, subject, body, chatter_log=True):
        self.ensure_one()
        if not recipients:
            return
        email_from = self._proposal_notification_email_from()
        if not email_from:
            self.message_post(
                body=Markup(
                    "<p><b>Bid Board email not sent</b> — set <b>Notification From</b> in Bid Board Settings "
                    "or <b>mail.default.from</b> (Technical → Parameters → System Parameters).</p>"
                    "<p><b>Subject:</b> {}</p>"
                ).format(subject)
                + Markup(body),
                subtype_xmlid="mail.mt_note",
            )
            return
        mail = self.env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": ",".join(recipients),
                "email_from": email_from,
                "auto_delete": False,
                "model": self._name,
                "res_id": self.id,
            }
        )
        mail.send()
        mail.invalidate_recordset(["state", "failure_reason", "failure_type"])
        mail = mail.env["mail.mail"].sudo().browse(mail.id)
        if mail.state == "exception" and chatter_log:
            reason = (mail.failure_reason or "").strip() or _("Unknown error")
            self.message_post(
                body=Markup(
                    "<p><b>Bid Board email delivery failed</b></p>"
                    "<p><b>From:</b> {}</p>"
                    "<p><b>Subject:</b> {}</p>"
                    "<p><b>To:</b> {}</p>"
                    "<p><b>Reason:</b> {}</p>"
                ).format(email_from, subject, ", ".join(recipients), reason),
                subtype_xmlid="mail.mt_note",
                message_type="notification",
            )
            return
        if chatter_log:
            self.message_post(
                body=Markup(
                    "<p><b>Bid Board notification email sent</b></p>"
                    "<p><b>From:</b> {}</p>"
                    "<p><b>Subject:</b> {}</p>"
                    "<p><b>To:</b> {}</p>"
                ).format(email_from, subject, ", ".join(recipients)),
                subtype_xmlid="mail.mt_note",
                message_type="notification",
            )

    @api.model
    def _cron_proposal_deadline_one_month_reminders(self):
        """Email the salesperson when a proposal deadline is 30 days away (≈ one month). Once per deadline date."""
        today = fields.Date.context_today(self)
        horizon = today + timedelta(days=30)
        pipeline = ("open", "submitted", "revision")
        proposals = self.search(
            [
                ("active", "=", True),
                ("deadline_date", "=", horizon),
                ("outcome_status", "in", pipeline),
                ("deadline_one_month_notified_at", "=", False),
            ]
        )
        if not proposals:
            return
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for proposal in proposals:
            user = proposal.sales_user_id
            email = (user.email or user.partner_id.email or "").strip()
            if not email:
                continue
            dline = proposal.deadline_date
            link = (
                f"{base_url}/web#id={proposal.id}&model=bid.proposal&view_type=form" if base_url else ""
            )
            body = render_bid_board_email(
                headline="Proposal deadline in one month",
                tagline=proposal.name,
                intro_lines=[
                    _(
                        "Your proposal has a key deadline in 30 days. Use this time to align pricing, "
                        "documents, and client touchpoints."
                    ),
                ],
                detail_pairs=[
                    (_("Proposal"), proposal.name),
                    (_("Reference"), proposal.reference or "N/A"),
                    (_("Company"), (proposal.partner_company or "").strip() or "—"),
                    (_("Deadline date"), str(dline) if dline else "—"),
                    (_("Enquiry"), proposal.project_id.display_name if proposal.project_id else "—"),
                ],
                cta_label=_("Open proposal in Odoo") if link else None,
                cta_url=link or None,
            )
            proposal._send_proposal_notification_email(
                recipients=[email],
                subject=_("[Bid Board] Proposal deadline in 30 days: %s") % (proposal.reference or proposal.name),
                body=body,
                chatter_log=True,
            )
            proposal.deadline_one_month_notified_at = fields.Datetime.now()
