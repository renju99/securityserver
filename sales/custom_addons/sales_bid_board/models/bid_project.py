from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .bid_email_layout import render_bid_board_email


class BidProjectStage(models.Model):
    _name = "bid.project.stage"
    _description = "Bid Project Stage"
    _order = "sequence, id"

    name = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    fold = fields.Boolean(default=False)


class BidProject(models.Model):
    _name = "bid.project"
    _description = "Bid Project"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    name = fields.Char(required=True, tracking=True)
    code = fields.Char(required=True, copy=False, default="New", tracking=True)
    client_name = fields.Char(required=True, tracking=True)
    sales_rep = fields.Many2one("res.users", tracking=True, default=lambda self: self.env.user)
    project_lead_id = fields.Many2one("res.users", tracking=True, default=lambda self: self.env.user)
    team_member_ids = fields.Many2many("bid.team.member", string="Team Members")
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
    )
    contract_duration = fields.Selection(
        [("1y", "1 year"), ("2y", "2 years"), ("3y", "3 years"), ("3y_plus", "3+ years")],
        required=True,
        default="1y",
        tracking=True,
    )
    contract_value = fields.Float(required=True, default=0.0, tracking=True)
    deadline_date = fields.Date(tracking=True)
    deadline_datetime = fields.Datetime(tracking=True)
    contract_type = fields.Selection(
        [("ifm", "IFM"), ("bundled", "Bundled Services"), ("single", "Single Service")],
        required=True,
        default="ifm",
        tracking=True,
    )
    threshold = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        required=True,
        default="medium",
        tracking=True,
    )
    tender_bond = fields.Selection(
        [("none", "Not Required"), ("lt5", "< 5%"), ("5to10", "5% to 10%"), ("gt10", "> 10%")],
        required=True,
        default="none",
        tracking=True,
    )
    performance_bond = fields.Selection(
        [("none", "Not Required"), ("lt5", "< 5%"), ("5to10", "5% to 10%"), ("gt10", "> 10%")],
        required=True,
        default="none",
        tracking=True,
    )
    kpi = fields.Selection(
        [("yes", "Yes"), ("partial", "Partial"), ("no", "No")],
        required=True,
        default="yes",
        tracking=True,
    )
    scope_cleaning = fields.Float(default=0.0)
    scope_maintenance = fields.Float(default=0.0)
    scope_security = fields.Float(default=0.0)
    scope_landscaping = fields.Float(default=0.0)
    scope_laundry = fields.Float(default=0.0)
    scope_support = fields.Float(default=0.0)
    scope_others = fields.Float(default=0.0)
    scope_total = fields.Float(compute="_compute_scope_total", store=True)
    progress = fields.Integer(default=30, tracking=True)
    stage_id = fields.Many2one(
        "bid.project.stage",
        required=True,
        tracking=True,
        default=lambda self: self.env["bid.project.stage"].search([], order="sequence", limit=1),
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
    )
    description = fields.Text()
    criteria_line_ids = fields.One2many("bid.project.criteria", "project_id", string="Scorecard")

    score_strategy = fields.Float(compute="_compute_scores", store=True)
    score_customer = fields.Float(compute="_compute_scores", store=True)
    score_commercial = fields.Float(compute="_compute_scores", store=True)
    score_finance = fields.Float(compute="_compute_scores", store=True)
    score_operations = fields.Float(compute="_compute_scores", store=True)
    score_overall = fields.Float(compute="_compute_scores", store=True, tracking=True)

    decision_auto = fields.Selection(
        [("bid", "Bid"), ("no_bid", "No Bid")], compute="_compute_decisions", store=True
    )
    decision_override = fields.Selection([("bid", "Bid"), ("no_bid", "No Bid")])
    decision_final = fields.Selection(
        [("bid", "Bid"), ("no_bid", "No Bid")], compute="_compute_decisions", store=True, tracking=True
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
    )
    recommendation_text = fields.Char(compute="_compute_decisions", store=True)
    recommendation_note = fields.Char(compute="_compute_decisions", store=True)
    override_reason = fields.Text()

    submission_ids = fields.One2many("bid.submission", "project_id")
    notification_ids = fields.One2many("bid.notification", "project_id")
    change_request_ids = fields.One2many("bid.change.request", "project_id")
    reviewed_by_id = fields.Many2one("res.users", tracking=True)
    reviewed_on = fields.Datetime(tracking=True)
    can_cso_review = fields.Boolean(compute="_compute_ui_permissions")
    can_non_cso_actions = fields.Boolean(compute="_compute_ui_permissions")
    can_submit_for_review = fields.Boolean(compute="_compute_ui_permissions")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "New") == "New":
                vals["code"] = self.env["ir.sequence"].next_by_code("bid.project") or "New"
        return super().create(vals_list)

    def write(self, vals):
        for project in self:
            if project.review_status == "approved" and not project._is_cso_user():
                raise ValidationError("Approved projects are locked. Only CSO can modify them.")
        return super().write(vals)

    def unlink(self):
        for project in self:
            if project.review_status == "approved" and not project._is_cso_user():
                raise ValidationError("Approved projects are locked. Only CSO can delete them.")
        return super().unlink()

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

    @api.depends("score_overall", "decision_override")
    def _compute_decisions(self):
        for project in self:
            project.decision_auto = "bid" if project.score_overall >= 70.0 else "no_bid"
            project.decision_final = project.decision_override or project.decision_auto
            if project.decision_final == "bid":
                project.recommendation_text = "BID RECOMMENDED"
                project.recommendation_note = "Proceed with Bid"
            else:
                project.recommendation_text = "NO BID RECOMMENDED"
                project.recommendation_note = "Do not proceed with Bid"

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

    @api.depends("review_status", "score_overall")
    @api.depends_context("uid")
    def _compute_ui_permissions(self):
        min_score = self._get_submit_review_min_score()
        for project in self:
            is_cso = project._is_cso_user()
            project.can_cso_review = is_cso and project.review_status in (
                "pending_review",
                "change_requested",
            )
            project.can_non_cso_actions = not is_cso
            project.can_submit_for_review = (not is_cso) and (project.score_overall >= min_score)

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

    def action_load_default_scorecard(self):
        default_lines = [
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
        ]
        for project in self:
            if project.criteria_line_ids:
                continue
            project.criteria_line_ids = [
                (
                    0,
                    0,
                    {
                        "category": category,
                        "name": name,
                        "option_1_text": option_1,
                        "option_2_text": option_2,
                        "option_3_text": option_3,
                        "score": "2",
                        "weight": 1.0,
                    },
                )
                for category, name, option_1, option_2, option_3 in default_lines
            ]

    def action_save_draft(self):
        for project in self:
            project.write({"review_status": "draft"})

    def action_submit_for_review(self):
        min_score = self._get_submit_review_min_score()
        for project in self:
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
        return [email.strip() for email in raw.split(",") if email.strip()]

    def _is_cso_user(self):
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        allowed_emails = set(self._split_emails(settings.cso_approver_emails))
        current_email = (self.env.user.email or "").strip()
        return bool(current_email and current_email in allowed_emails)

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
                    "Only configured CSO/CFO approver email(s) can perform this action. "
                    "Please update Bid Board Settings if needed."
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

class BidChangeRequestWizard(models.TransientModel):
    _name = "bid.change.request.wizard"
    _description = "Bid Change Request Wizard"

    project_id = fields.Many2one("bid.project", required=True)
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
    )
    comments = fields.Text(required=True)

    def action_submit_change_request(self):
        self.ensure_one()
        self.project_id.action_request_change(self.comments, self.priority)
        return {"type": "ir.actions.act_window_close"}


class BidProjectCreateWizard(models.TransientModel):
    _name = "bid.project.create.wizard"
    _description = "Bid Project Create Wizard"

    name = fields.Char(required=True)
    client_name = fields.Char(required=True)
    project_lead_id = fields.Many2one("res.users", required=True, default=lambda self: self.env.user)
    team_member_ids = fields.Many2many("bid.team.member", string="Team Members")
    deadline_datetime = fields.Datetime(required=True)
    state = fields.Selection(
        [
            ("active", "Active"),
            ("completed", "Completed"),
            ("declined", "Declined"),
            ("priority", "Priority"),
        ],
        default="active",
        required=True,
    )
    progress = fields.Integer(default=30)

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

    project_id = fields.Many2one("bid.project", required=True, ondelete="cascade")
    name = fields.Char(required=True)
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
    )
    score = fields.Selection([("1", "1"), ("2", "2"), ("3", "3")], required=True, default="2")
    option_1_text = fields.Char(string="1")
    option_2_text = fields.Char(string="2")
    option_3_text = fields.Char(string="3")
    weight = fields.Float(default=1.0)
    comment = fields.Char()
