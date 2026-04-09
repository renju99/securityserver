from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .bid_email_layout import render_bid_board_email


class BidProjectStage(models.Model):
    _name = "bid.project.stage"
    _description = "Bid Project Stage"
    _order = "sequence, id"

    name = fields.Char(
        required=True,
        help="Name of this pipeline stage (e.g. Qualification, Proposal). Shown on enquiries.",
    )
    sequence = fields.Integer(
        default=10,
        help="Order of stages in the pipeline: lower numbers appear first.",
    )
    fold = fields.Boolean(
        default=False,
        help="If enabled, this stage can be collapsed in Kanban-style views to reduce clutter.",
    )


class BidProject(models.Model):
    _name = "bid.project"
    _description = "Bid Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # Standard scorecard rows applied when an enquiry has no lines (create, duplicate, manual action).
    _SCORECARD_TEMPLATE_ROWS = (
        ("strategy", "Strategic importance", "Low", "Medium", "High"),
        ("strategy", "Domain of Berkeley's activities", "<40% alignment", "40%-70% alignment", ">70% alignment"),
        ("strategy", "Potential for additional works", "No plans", "Limited plans", "Clear expansion plans"),
        ("customer", "Strategic customer", "Non-strategic", "Important", "Strategic"),
        ("customer", "Customer size / structure", "Small", "Medium", "Large"),
        ("customer", "Customer track record", "No wins", "Lost at final stage", "Existing client"),
        ("commercial", "Term of contract", "<2 years", "2-3 years", ">3 years"),
        ("commercial", "RFP documents quality", "Insufficient details", "Partial details", "Detailed with asset list"),
        ("commercial", "Competitive advantage", "No advantage", "Equal", "High"),
        ("finance", "Estimated GM", "<10%", "10%-12%", ">12%"),
        ("finance", "Payment terms", ">60 days", "30-60 days", "30 days"),
        ("finance", "Penalties", ">5% value", "<5% value", "No penalty"),
        ("operations", "Condition at contract start", ">10 years", "<10 years", "New/refurbished"),
        ("operations", "Mobilization period", "<4 weeks", "4-8 weeks", ">8 weeks"),
        ("operations", "Similar experience", "Tendered only", "Few contracts", "Numerous contracts"),
    )

    name = fields.Char(
        required=True,
        tracking=True,
        help="Descriptive name of the opportunity or tender (e.g. project or RFP title).",
    )
    code = fields.Char(
        required=True,
        copy=False,
        default="New",
        tracking=True,
        help="Unique enquiry code assigned when the record is first saved.",
    )
    client_name = fields.Char(
        required=True,
        tracking=True,
        help="Client or organisation issuing or receiving the bid.",
    )
    sales_rep = fields.Many2one(
        "res.users",
        tracking=True,
        default=lambda self: self.env.user,
        help="Salesperson accountable for the opportunity and customer contact.",
    )
    project_lead_id = fields.Many2one(
        "res.users",
        tracking=True,
        default=lambda self: self.env.user,
        help="Internal owner coordinating the bid preparation and submission.",
    )
    team_member_ids = fields.Many2many(
        "bid.team.member",
        string="Team Members",
        help="Bid team members (from the configured team list) working on this enquiry.",
    )
    emirate = fields.Selection(
        [
            ("abudhabi", "Abu Dhabi"),
            ("dubai", "Dubai"),
            ("sharjah", "Sharjah"),
            ("ajman", "Ajman"),
            ("rak", "Ras Al Khaimah"),
            ("fujairah", "Fujairah"),
            ("uaq", "Umm Al Quwain"),
        ],
        required=True,
        default="dubai",
        tracking=True,
        help="Emirate where the site or client is primarily located.",
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
        required=True,
        default="real_estate",
        tracking=True,
        help="Industry sector of the client or asset (reporting and filtering).",
    )
    contract_duration = fields.Selection(
        [("1y", "1 year"), ("2y", "2 years"), ("3y", "3 years"), ("3y_plus", "3+ years")],
        required=True,
        default="1y",
        tracking=True,
        help="Expected contract length category used in scoring and planning.",
    )
    contract_value = fields.Float(
        required=True,
        default=0.0,
        tracking=True,
        help="Estimated total contract value (use your standard currency, e.g. AED).",
    )
    deadline_date = fields.Date(
        tracking=True,
        help="Submission or decision date (date only). Can mirror the deadline date part of the datetime.",
    )
    deadline_datetime = fields.Datetime(
        tracking=True,
        help="Full submission deadline including time, for reminders and governance.",
    )
    contract_type = fields.Selection(
        [("ifm", "IFM"), ("bundled", "Bundled Services"), ("single", "Single Service")],
        required=True,
        default="ifm",
        tracking=True,
        help="Contract shape: IFM (integrated), bundled services, or single service line.",
    )
    threshold = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        required=True,
        default="medium",
        tracking=True,
        help="Internal priority or materiality band for management attention.",
    )
    tender_bond = fields.Selection(
        [("none", "Not Required"), ("lt5", "< 5%"), ("5to10", "5% to 10%"), ("gt10", "> 10%")],
        required=True,
        default="none",
        tracking=True,
        help="Bid or tender security (bond) as a percentage of contract value, if required.",
    )
    performance_bond = fields.Selection(
        [("none", "Not Required"), ("lt5", "< 5%"), ("5to10", "5% to 10%"), ("gt10", "> 10%")],
        required=True,
        default="none",
        tracking=True,
        help="Performance security after award, as a percentage of contract value, if applicable.",
    )
    kpi = fields.Selection(
        [("yes", "Yes"), ("partial", "Partial"), ("no", "No")],
        required=True,
        default="yes",
        tracking=True,
        help="Whether the RFP includes clear KPIs: full, partial, or none.",
    )
    scope_cleaning = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to cleaning (use % so all scope lines sum to 100).",
    )
    scope_maintenance = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to maintenance (%).",
    )
    scope_security = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to security (%).",
    )
    scope_landscaping = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to landscaping (%).",
    )
    scope_laundry = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to laundry (%).",
    )
    scope_support = fields.Float(
        default=0.0,
        help="Share of scope or fee attributed to support services (%).",
    )
    scope_others = fields.Float(
        default=0.0,
        help="Share of scope or fee for any other service lines (%).",
    )
    scope_total = fields.Float(
        compute="_compute_scope_total",
        store=True,
        help="Automatic sum of all scope percentage lines (should typically equal 100%).",
    )
    progress = fields.Integer(
        default=30,
        tracking=True,
        help="Rough completion % of bid preparation (0–100), for tracking only.",
    )
    stage_id = fields.Many2one(
        "bid.project.stage",
        required=True,
        tracking=True,
        default=lambda self: self.env["bid.project.stage"].search([], order="sequence", limit=1),
        help="Current stage in your internal bid pipeline.",
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("completed", "Completed"),
            ("declined", "Declined"),
            ("priority", "Priority"),
        ],
        default="active",
        tracking=True,
        help="High-level enquiry state: active work, completed win, declined, or priority flag.",
    )
    description = fields.Text(
        help="Free-text notes: scope summary, risks, links, or anything the team should know.",
    )
    crm_lead_id = fields.Many2one(
        "crm.lead",
        string="Source Lead",
        tracking=True,
        copy=False,
        ondelete="set null",
        index=True,
        help="CRM lead this enquiry was created from, if any.",
    )
    criteria_line_ids = fields.One2many(
        "bid.project.criteria",
        "project_id",
        string="Scorecard",
        help="Bid / no-bid scorecard lines. Scores drive the overall % and CSO recommendation.",
    )

    score_strategy = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Strategy category (computed from scorecard).",
    )
    score_customer = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Customer category.",
    )
    score_commercial = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Commercial category.",
    )
    score_finance = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Finance category.",
    )
    score_operations = fields.Float(
        compute="_compute_scores",
        store=True,
        help="Weighted score for the Operations category.",
    )
    score_overall = fields.Float(
        compute="_compute_scores",
        store=True,
        tracking=True,
        help="Overall scorecard percentage (average of category scores). Feeds Bid vs No Bid recommendation.",
    )

    decision_final = fields.Selection(
        [("bid", "Bid"), ("no_bid", "No Bid")],
        compute="_compute_decisions",
        store=True,
        tracking=True,
        help="System recommendation from the score: Bid if overall score meets the threshold, otherwise No Bid.",
    )
    review_status = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_review", "Pending Review"),
            ("approved", "Approved"),
            ("declined", "Declined"),
            ("change_requested", "Change Requested"),
        ],
        default="draft",
        tracking=True,
        help="CSO workflow: Draft, pending review, approved, declined, or changes requested.",
    )
    recommendation_text = fields.Char(
        compute="_compute_decisions",
        store=True,
        help="Short label for the recommended decision (Bid / No Bid wording).",
    )
    recommendation_note = fields.Char(
        compute="_compute_decisions",
        store=True,
        help="One-line explanation shown with the recommendation.",
    )

    submission_ids = fields.One2many(
        "bid.submission",
        "project_id",
        help="History of submissions to CSO review for this enquiry.",
    )
    notification_ids = fields.One2many(
        "bid.notification",
        "project_id",
        help="Scheduled deadline reminders linked to this enquiry.",
    )
    change_request_ids = fields.One2many(
        "bid.change.request",
        "project_id",
        help="CSO change requests that must be resolved before re-submission.",
    )
    proposal_ids = fields.One2many(
        "bid.proposal",
        "project_id",
        string="Proposals",
        help="Formal proposals created after a Bid approval (see Proposals menu).",
    )
    proposal_count = fields.Integer(
        compute="_compute_proposal_count",
        store=True,
        help="Number of proposal records linked to this enquiry.",
    )
    reviewed_by_id = fields.Many2one(
        "res.users",
        tracking=True,
        help="CSO (or delegate) who last completed an approval, decline, or change request action.",
    )
    reviewed_on = fields.Datetime(
        tracking=True,
        help="Timestamp of that last CSO review action.",
    )
    can_cso_review = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the current user is allowed to approve, decline, or request changes (CSO role).",
    )
    can_non_cso_actions = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when draft-style actions (e.g. save draft) are available for this enquiry and user.",
    )
    can_submit_for_review = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the score meets the minimum required to submit for CSO review.",
    )
    can_show_submit_review_button = fields.Boolean(
        compute="_compute_ui_permissions",
        help="True when the Submit for Review button should be visible (may still show even if score is low).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("bid.project") or "New"
        records = super().create(vals_list)
        records._ensure_default_scorecard()
        return records

    def write(self, vals):
        for project in self:
            if project._is_review_outcome_locked() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    "Approved or declined projects are locked. Only CSO, Bid Board managers, or administrators "
                    "can modify them."
                )
        return super().write(vals)

    def unlink(self):
        for project in self:
            if project._is_review_outcome_locked() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    "Approved or declined projects are locked. Only CSO, Bid Board managers, or administrators "
                    "can delete them."
                )
        return super().unlink()

    def copy(self, default=None):
        """Duplicate starts as a new draft enquiry, not an approved clone."""
        default = dict(default or {})
        if "review_status" not in default:
            default["review_status"] = "draft"
        if "reviewed_by_id" not in default:
            default["reviewed_by_id"] = False
        if "reviewed_on" not in default:
            default["reviewed_on"] = False
        if "state" not in default:
            default["state"] = "active"
        # Do not clone CSO workflow history or reminder rows
        if "submission_ids" not in default:
            default["submission_ids"] = []
        if "notification_ids" not in default:
            default["notification_ids"] = []
        if "change_request_ids" not in default:
            default["change_request_ids"] = []
        if "proposal_ids" not in default:
            default["proposal_ids"] = []
        copied = super().copy(default)
        copied._ensure_default_scorecard()
        return copied

    @api.depends("criteria_line_ids.score", "criteria_line_ids.weight", "criteria_line_ids.category")
    def _compute_scores(self):
        categories = {
            "strategy": "score_strategy",
            "customer": "score_customer",
            "commercial": "score_commercial",
            "finance": "score_finance",
            "operations": "score_operations",
        }
        for project in self:
            score_map = {key: 0.0 for key in categories}
            total_map = {key: 0.0 for key in categories}
            for line in project.criteria_line_ids:
                total_map[line.category] += line.weight
                line_score = float(line.score or 0.0)
                score_map[line.category] += (line_score / 3.0) * 100.0 * line.weight

            category_values = []
            for key, field_name in categories.items():
                value = 0.0
                if total_map[key]:
                    value = score_map[key] / total_map[key]
                setattr(project, field_name, value)
                if total_map[key]:
                    category_values.append(value)

            project.score_overall = sum(category_values) / len(category_values) if category_values else 0.0

    @api.depends("score_overall")
    def _compute_decisions(self):
        for project in self:
            project.decision_final = "bid" if project.score_overall >= 70.0 else "no_bid"
            if project.decision_final == "bid":
                project.recommendation_text = "BID RECOMMENDED"
                project.recommendation_note = "Proceed with Bid"
            else:
                project.recommendation_text = "NO BID RECOMMENDED"
                project.recommendation_note = "Do not proceed with Bid"

    @api.depends("proposal_ids")
    def _compute_proposal_count(self):
        for project in self:
            project.proposal_count = len(project.proposal_ids)

    @api.depends(
        "scope_cleaning",
        "scope_maintenance",
        "scope_security",
        "scope_landscaping",
        "scope_laundry",
        "scope_support",
        "scope_others",
    )
    def _compute_scope_total(self):
        for project in self:
            project.scope_total = (
                project.scope_cleaning
                + project.scope_maintenance
                + project.scope_security
                + project.scope_landscaping
                + project.scope_laundry
                + project.scope_support
                + project.scope_others
            )

    @api.depends(
        "review_status",
        "score_overall",
        "criteria_line_ids",
        "criteria_line_ids.score",
        "criteria_line_ids.weight",
    )
    @api.depends_context("uid")
    def _compute_ui_permissions(self):
        min_score = self._get_submit_review_min_score()
        for project in self:
            is_cso = project._is_cso_user()
            user = project.env.user
            settings_privileged = (
                user.has_group("sales_bid_board.group_bid_board_cso")
                or user.has_group("sales_bid_board.group_bid_board_manager")
                or user.has_group("base.group_system")
            )
            project.can_cso_review = is_cso and project.review_status in (
                "pending_review",
                "change_requested",
            )
            # Save draft: team always; CSO approvers only if also Bid Board manager/admin and still editing.
            project.can_non_cso_actions = (not is_cso) or (
                settings_privileged
                and project.review_status in ("draft", "change_requested")
            )
            project.can_show_submit_review_button = (
                project.review_status in ("draft", "change_requested")
                and ((not is_cso) or settings_privileged)
            )
            # Eligibility including score (e.g. extensions, dashboards); form button uses can_show_submit_review_button.
            project.can_submit_for_review = (
                project.can_show_submit_review_button
                and (project.score_overall >= min_score)
            )

    @api.constrains(
        "scope_cleaning",
        "scope_maintenance",
        "scope_security",
        "scope_landscaping",
        "scope_laundry",
        "scope_support",
        "scope_others",
    )
    def _check_scope_total(self):
        for project in self:
            if project.scope_total > 100.0:
                raise ValidationError("Scope of Work total cannot exceed 100%.")

    @api.onchange("deadline_datetime")
    def _onchange_deadline_datetime(self):
        for project in self:
            if project.deadline_datetime:
                project.deadline_date = fields.Date.to_date(project.deadline_datetime)

    def _ensure_default_scorecard(self):
        commands = [
            (
                0,
                0,
                {
                    "category": category,
                    "name": name,
                    "option_1_text": option_1,
                    "option_2_text": option_2,
                    "option_3_text": option_3,
                    # Default 3/3 so overall score meets the usual submit threshold until users tune lines.
                    "score": "3",
                    "weight": 1.0,
                },
            )
            for category, name, option_1, option_2, option_3 in self._SCORECARD_TEMPLATE_ROWS
        ]
        for project in self:
            if project.criteria_line_ids:
                continue
            project.write({"criteria_line_ids": commands})

    def action_load_default_scorecard(self):
        """Backward-compatible; scorecard is usually added automatically on create/copy."""
        self._ensure_default_scorecard()

    def action_save_draft(self):
        for project in self:
            project.write({"review_status": "draft"})

    def action_submit_for_review(self):
        min_score = self._get_submit_review_min_score()
        user = self.env.user
        for project in self:
            if project._is_cso_user() and not (
                user.has_group("sales_bid_board.group_bid_board_cso")
                or user.has_group("sales_bid_board.group_bid_board_manager")
                or user.has_group("base.group_system")
            ):
                raise ValidationError(
                    _(
                        "CSO approvers (your email is on the approver list) cannot submit for review unless "
                        "you are also a Bid Board manager or administrator."
                    )
                )
            if project.score_overall < min_score:
                raise ValidationError(
                    _(
                        "Submit for Review is allowed only when Overall Score is at least %(min_score).2f%%. "
                        "Current score: %(current_score).2f%%."
                    )
                    % {"min_score": min_score, "current_score": project.score_overall}
                )
            project.write({"review_status": "pending_review"})
            self.env["bid.submission"].create(
                {
                    "name": f"{project.name} - Review Submission",
                    "project_id": project.id,
                    "owner_id": self.env.user.id,
                    "status": "submitted",
                    "notes": "Submitted from Decision Sheet",
                }
            )
            settings = self.env["bid.board.settings"].sudo().get_singleton()
            notify = settings.notify_cso_on_all_submissions or project.score_overall > 80.0
            if not notify:
                continue
            recipients = project._split_emails(settings.cso_approver_emails)
            if not recipients:
                continue
            base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            project_link = (
                f"{base_url}/web#id={project.id}&model=bid.project&view_type=form" if base_url else ""
            )
            body = render_bid_board_email(
                headline="CSO review needed",
                tagline=project.name,
                intro_lines=[
                    "A bid / no-bid project was submitted for your review.",
                    "Please open the record in Odoo and complete the approval workflow.",
                ],
                detail_pairs=[
                    ("Project", project.name),
                    ("Code", project.code or "N/A"),
                    ("Overall score", f"{project.score_overall:.2f}%"),
                    ("Status", "Pending review"),
                ],
                cta_label="Open project in Odoo" if project_link else None,
                cta_url=project_link or None,
            )
            project._send_notification_email(
                recipients=recipients,
                subject=f"[Bid Board] CSO Review Needed: {project.name}",
                body=body,
            )

    def action_approve_review(self):
        self._require_open_cso_review()
        for project in self:
            settings = self.env["bid.board.settings"].sudo().get_singleton()
            next_state = "completed" if project.decision_final == "bid" else "declined"
            project.write(
                {
                    "review_status": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                    "state": next_state,
                }
            )
            pending_changes = project.change_request_ids.filtered(lambda r: not r.resolved)
            pending_changes.write({"resolved": True, "resolved_date": fields.Datetime.now()})
            recipients = []
            recipients += project._split_emails(settings.commercial_manager_email)
            recipients += project._split_emails(settings.bid_manager_email)
            if settings.notify_creator_on_approval and project.create_uid.email:
                recipients.append(project.create_uid.email)
            recipients = list(dict.fromkeys([email for email in recipients if email]))
            if recipients:
                decision = project._selection_display("decision_final")
                body = render_bid_board_email(
                    headline="Project approved",
                    tagline=project.name,
                    intro_lines=[
                        "CSO review is complete and this project has been approved.",
                        "The decision sheet has been updated in Odoo.",
                    ],
                    detail_pairs=[
                        ("Project", project.name),
                        ("Code", project.code or "N/A"),
                        ("Decision", decision),
                        ("Overall score", f"{project.score_overall:.2f}%"),
                    ],
                )
                project._send_notification_email(
                    recipients=recipients,
                    subject=f"[Bid Board] Project Approved: {project.name}",
                    body=body,
                )

    def action_decline_review(self):
        self._require_open_cso_review()
        for project in self:
            project.write(
                {
                    "review_status": "declined",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                    "state": "declined",
                }
            )
            pending_changes = project.change_request_ids.filtered(lambda r: not r.resolved)
            pending_changes.write({"resolved": True, "resolved_date": fields.Datetime.now()})
            settings = self.env["bid.board.settings"].sudo().get_singleton()
            recipients = []
            if project.project_lead_id.email:
                recipients.append(project.project_lead_id.email)
            if project.create_uid.email:
                recipients.append(project.create_uid.email)
            recipients += project._split_emails(settings.commercial_manager_email)
            recipients += project._split_emails(settings.bid_manager_email)
            recipients = list(dict.fromkeys([email for email in recipients if email]))
            if recipients:
                review_date = fields.Datetime.context_timestamp(
                    project, project.reviewed_on
                ).strftime("%Y-%m-%d %H:%M:%S")
                reviewer_name = project.reviewed_by_id.name or "N/A"
                decision = project._selection_display("decision_final")
                body = render_bid_board_email(
                    headline="Project declined",
                    tagline=project.name,
                    intro_lines=[
                        "This bid has been declined at CSO review.",
                        "See Odoo for the full decision sheet and rationale.",
                    ],
                    detail_pairs=[
                        ("Project", project.name),
                        ("Code", project.code or "N/A"),
                        ("Reviewer", reviewer_name),
                        ("Reviewed on", review_date),
                        ("Decision", decision),
                        ("Overall score", f"{project.score_overall:.2f}%"),
                    ],
                )
                project._send_notification_email(
                    recipients=recipients,
                    subject=f"[Bid Board] Project Declined: {project.name}",
                    body=body,
                )

    def _prepare_proposal_default_values(self):
        """Map enquiry fields into proposal defaults (spreadsheet-aligned)."""
        self.ensure_one()
        emirate_labels = dict(self._fields["emirate"].selection)
        city = emirate_labels.get(self.emirate, "")
        duration_months_map = {"1y": 12, "2y": 24, "3y": 36, "3y_plus": 48}
        months = duration_months_map.get(self.contract_duration) or 12
        service_parts = []
        if self.scope_cleaning:
            service_parts.append("Cleaning")
        if self.scope_maintenance:
            service_parts.append("Maintenance")
        if self.scope_security:
            service_parts.append("Security")
        if self.scope_landscaping:
            service_parts.append("Landscaping")
        if self.scope_laundry:
            service_parts.append("Laundry")
        if self.scope_support:
            service_parts.append("Support")
        if self.scope_others:
            service_parts.append("Other")
        annual = 0.0
        if months and self.contract_value:
            annual = (self.contract_value / float(months)) * 12.0
        sales = self.sales_rep
        key_name = (sales.name or "").strip() if sales else ""
        return {
            "project_id": self.id,
            "sales_user_id": sales.id if sales else False,
            "partner_company": self.client_name,
            "project_description": self.description or self.name,
            "industry": self.industry,
            "city": city,
            "services_offered": ", ".join(service_parts) if service_parts else False,
            "contract_volume_total": self.contract_value,
            "contract_duration_months": months,
            "contract_volume_annual": annual,
            "key_account_name": key_name or False,
        }

    def action_create_proposal(self):
        self.ensure_one()
        if not self.env.context.get("from_bid_no_bid"):
            raise ValidationError(
                "Create proposal is only available when the enquiry is opened from Bid / No Bid."
            )
        if self.review_status != "approved" or self.decision_final != "bid":
            raise ValidationError(
                "You can only create a proposal after the enquiry is approved with a Bid decision."
            )
        defaults = self._prepare_proposal_default_values()
        return {
            "type": "ir.actions.act_window",
            "name": _("Proposal"),
            "res_model": "bid.proposal",
            "view_mode": "form",
            "target": "current",
            "context": {"default_%s" % k: v for k, v in defaults.items() if v is not False},
        }

    def action_view_proposals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Proposals"),
            "res_model": "bid.proposal",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {
                "default_project_id": self.id,
                **{
                    "default_%s" % k: v
                    for k, v in self._prepare_proposal_default_values().items()
                    if k != "project_id" and v is not False
                },
            },
        }

    def action_open_change_request_wizard(self):
        self.ensure_one()
        self._require_open_cso_review()
        return {
            "type": "ir.actions.act_window",
            "name": "Request Change",
            "res_model": "bid.change.request.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_project_id": self.id},
        }

    def action_request_change(self, comments, priority="medium"):
        self._require_open_cso_review()
        for project in self:
            reason = (comments or "").strip()
            if not reason:
                raise ValidationError("CSO comments are required for change request.")
            self.env["bid.change.request"].create(
                {
                    "project_id": project.id,
                    "reviewer_id": self.env.user.id,
                    "priority": priority,
                    "comments": reason,
                }
            )
            project.write(
                {
                    "review_status": "change_requested",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                }
            )
            creator_email = (project.create_uid.email or "").strip()
            if creator_email:
                base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
                project_link = (
                    f"{base_url}/web#id={project.id}&model=bid.project&view_type=form" if base_url else ""
                )
                reviewer_name = project.reviewed_by_id.name or "N/A"
                review_date = fields.Datetime.context_timestamp(
                    project, project.reviewed_on
                ).strftime("%Y-%m-%d %H:%M:%S")
                body = render_bid_board_email(
                    headline="Changes requested",
                    tagline=project.name,
                    intro_lines=[
                        "CSO has requested updates to the decision sheet before approval.",
                        "Please review the comments below and resubmit when ready.",
                    ],
                    detail_pairs=[
                        ("Project", project.name),
                        ("Code", project.code or "N/A"),
                        ("Priority", priority.title()),
                        ("Reviewer", reviewer_name),
                        ("Reviewed on", review_date),
                        ("CSO comments", reason),
                    ],
                    cta_label="Open project in Odoo" if project_link else None,
                    cta_url=project_link or None,
                )
                project._send_notification_email(
                    recipients=[creator_email],
                    subject=f"[Bid Board] Change Requested: {project.name}",
                    body=body,
                )

    def _selection_display(self, field_name):
        self.ensure_one()
        field = self._fields[field_name]
        selection = field.selection
        if callable(selection):
            selection = selection(self)
        value = getattr(self, field_name)
        return dict(selection or []).get(value, value or "N/A")

    def _split_emails(self, raw):
        if not raw:
            return []
        return [email.strip().lower() for email in raw.split(",") if email and email.strip()]

    def _is_cso_user(self):
        user = self.env.user
        if user.has_group("sales_bid_board.group_bid_board_cso"):
            return True
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        allowed_emails = set(self._split_emails(settings.cso_approver_emails))
        current_email = (user.email or "").strip().lower()
        return bool(current_email and current_email in allowed_emails)

    def _is_review_outcome_locked(self):
        """CSO has closed the review (approved or declined)."""
        self.ensure_one()
        return self.review_status in ("approved", "declined")

    def _can_bypass_approved_project_lock(self):
        """Who may edit or delete enquiries locked after CSO approval or decline."""
        user = self.env.user
        return (
            user.has_group("sales_bid_board.group_bid_board_cso")
            or user.has_group("sales_bid_board.group_bid_board_manager")
            or user.has_group("base.group_system")
            or self._is_cso_user()
        )

    def _get_submit_review_min_score(self):
        raw_value = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("sales_bid_board.submit_review_min_score", default="70")
        )
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = 70.0
        return max(0.0, min(100.0, value))

    def _require_open_cso_review(self):
        for project in self:
            if not project._is_cso_user():
                raise ValidationError(
                    "Only users in the Bid Board / CSO security group or listed as CSO approver "
                    "emails in Bid Board Settings can perform this action."
                )
            if project.review_status not in ("pending_review", "change_requested"):
                raise ValidationError(
                    "CSO review is already complete. Approve, decline, and request-change are only "
                    "available while the project is pending review or has changes requested."
                )

    def _notification_email_from(self):
        self.ensure_one()
        return self.env["bid.board.settings"].sudo().get_singleton().resolve_notification_email_from()

    def _send_notification_email(self, recipients, subject, body, chatter_log=True):
        self.ensure_one()
        if not recipients:
            return
        email_from = self._notification_email_from()
        if not email_from:
            self.message_post(
                body=Markup(
                    "<p><b>Bid Board email not sent</b> — set <b>Notification From</b> in Bid Board Settings "
                    "or <b>mail.default.from</b> (Technical → Parameters → System Parameters).</p>"
                    "<p>Bid Board does not use the company or user email as a From fallback (avoids placeholder addresses).</p>"
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
                # Keep rows so Inbox/notifications/bounce links do not 404 after send (auto_delete removed mail #32, etc.).
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
            recipient_text = ", ".join(recipients)
            self.message_post(
                body=Markup(
                    "<p><b>Bid Board notification email sent</b></p>"
                    "<p><b>From:</b> {}</p>"
                    "<p><b>Subject:</b> {}</p>"
                    "<p><b>To:</b> {}</p>"
                ).format(email_from, subject, recipient_text),
                subtype_xmlid="mail.mt_note",
                message_type="notification",
            )

    @api.model
    def _cron_send_governance_sla_notifications(self):
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        recipients = self._split_emails(settings.cso_approver_emails)
        recipients = list(dict.fromkeys([email for email in recipients if email]))
        if not recipients:
            return

        today = fields.Date.context_today(self)
        tomorrow = today + timedelta(days=1)
        sla_days = max(int(settings.pending_review_sla_days or 0), 1)
        cutoff_date = today - timedelta(days=sla_days)

        pending_projects = self.search([("review_status", "=", "pending_review")])
        mail_activity_model = self.env["mail.activity"].sudo()

        for project in pending_projects:
            has_due_tomorrow_activity = bool(
                mail_activity_model.search_count(
                    [
                        ("res_model", "=", "bid.project"),
                        ("res_id", "=", project.id),
                        ("date_deadline", "=", tomorrow),
                    ]
                )
            )
            latest_submission = self.env["bid.submission"].sudo().search(
                [("project_id", "=", project.id), ("status", "=", "submitted")],
                order="submitted_date desc, id desc",
                limit=1,
            )
            pending_since = latest_submission.submitted_date or fields.Date.to_date(project.create_date)
            is_pending_beyond_sla = bool(pending_since and pending_since <= cutoff_date)
            if not has_due_tomorrow_activity and not is_pending_beyond_sla:
                continue

            deadline_value = project.deadline_datetime or project.deadline_date or "N/A"
            body = render_bid_board_email(
                headline="Still awaiting review",
                tagline=project.name,
                intro_lines=[
                    "This project remains in pending CSO review past the expected timeline or an upcoming activity deadline.",
                    "Please prioritize the review queue or reassign if needed.",
                ],
                detail_pairs=[
                    ("Project", project.name),
                    ("Code", project.code or "N/A"),
                    ("Overall score", f"{project.score_overall:.2f}%"),
                    ("Submission deadline", str(deadline_value)),
                    ("Review status", "Pending review"),
                ],
            )
            project._send_notification_email(
                recipients=recipients,
                subject=f"[Bid Board] Still Awaiting Review: {project.name}",
                body=body,
            )

class CrmLead(models.Model):
    """Inverse relation for enquiries linked to a CRM lead (optional UI / reporting)."""

    _inherit = "crm.lead"

    bid_project_ids = fields.One2many(
        "bid.project",
        "crm_lead_id",
        string="Bid / No-Bid Enquiries",
    )


class BidChangeRequestWizard(models.TransientModel):
    _name = "bid.change.request.wizard"
    _description = "Bid Change Request Wizard"

    project_id = fields.Many2one(
        "bid.project",
        required=True,
        help="Enquiry the CSO is asking to update before approval.",
    )
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
        help="How urgent the requested changes are for the bid team.",
    )
    comments = fields.Text(
        required=True,
        help="Describe what must change on the decision sheet or supporting information.",
    )

    def action_submit_change_request(self):
        self.ensure_one()
        self.project_id.action_request_change(self.comments, self.priority)
        return {"type": "ir.actions.act_window_close"}


class BidProjectCreateWizard(models.TransientModel):
    _name = "bid.project.create.wizard"
    _description = "Bid Project Create Wizard"

    name = fields.Char(
        required=True,
        help="Working title for the new enquiry.",
    )
    client_name = fields.Char(
        required=True,
        help="Client name as it should appear on the enquiry.",
    )
    project_lead_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        help="Default project lead and sales rep for the new enquiry.",
    )
    team_member_ids = fields.Many2many(
        "bid.team.member",
        string="Team Members",
        help="Optional team members to attach immediately.",
    )
    deadline_datetime = fields.Datetime(
        required=True,
        help="First submission or review deadline (date and time).",
    )
    state = fields.Selection(
        [
            ("active", "Active"),
            ("completed", "Completed"),
            ("declined", "Declined"),
            ("priority", "Priority"),
        ],
        default="active",
        required=True,
        help="Initial status flag for the enquiry after creation.",
    )
    progress = fields.Integer(
        default=30,
        help="Initial % complete for preparation tracking.",
    )

    def action_create_project(self):
        self.ensure_one()
        project = self.env["bid.project"].create(
            {
                "name": self.name,
                "client_name": self.client_name,
                "sales_rep": self.project_lead_id.id,
                "project_lead_id": self.project_lead_id.id,
                "team_member_ids": [(6, 0, self.team_member_ids.ids)],
                "deadline_datetime": self.deadline_datetime,
                "deadline_date": fields.Date.to_date(self.deadline_datetime),
                "contract_value": 0.0,
                "state": self.state,
                "progress": self.progress,
            }
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": "bid.project",
            "res_id": project.id,
            "view_mode": "form",
            "target": "current",
        }


class BidProjectCriteria(models.Model):
    _name = "bid.project.criteria"
    _description = "Bid Project Criteria"
    _order = "category, id"

    project_id = fields.Many2one(
        "bid.project",
        required=True,
        ondelete="cascade",
        help="Parent enquiry this scorecard line belongs to.",
    )
    name = fields.Char(
        required=True,
        help="Criterion text (e.g. from the standard scorecard row).",
    )
    category = fields.Selection(
        [
            ("strategy", "Strategy"),
            ("customer", "Customer"),
            ("commercial", "Commercial"),
            ("finance", "Finance"),
            ("operations", "Operations"),
        ],
        required=True,
        default="strategy",
        help="Scorecard pillar. Category scores are averaged into the overall percentage.",
    )
    score = fields.Selection(
        [("1", "1"), ("2", "2"), ("3", "3")],
        required=True,
        default="2",
        help="Pick 1 (low), 2 (medium), or 3 (high) against the three options shown for this row.",
    )
    option_1_text = fields.Char(
        string="1",
        help="Label for the lowest score option on this row.",
    )
    option_2_text = fields.Char(
        string="2",
        help="Label for the middle score option.",
    )
    option_3_text = fields.Char(
        string="3",
        help="Label for the highest score option.",
    )
    weight = fields.Float(
        default=1.0,
        help="Importance of this row within its category (higher weight counts more in the category score).",
    )
    comment = fields.Char(
        help="Optional note for reviewers (risks, assumptions, or evidence).",
    )
