from datetime import timedelta

from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import html_escape

from .bid_email_layout import render_bid_board_email


class BidProjectWorkflow(models.Model):
    _inherit = "bid.project"

    def write(self, vals):
        for project in self:
            if project._bid_board_locked_for_record_edit() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    _(
                        "This enquiry is locked while it is pending CSO review, or after CSO approval or decline. "
                        "Only CSO approvers, Bid Board managers, or administrators can change it."
                    )
                )
        return super().write(vals)

    def unlink(self):
        for project in self:
            if project._bid_board_locked_for_record_edit() and not project._can_bypass_approved_project_lock():
                raise ValidationError(
                    _(
                        "This enquiry is locked while it is pending CSO review, or after CSO approval or decline. "
                        "Only CSO approvers, Bid Board managers, or administrators can delete it."
                    )
                )
        return super().unlink()

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
            team_edit_phase = project.review_status in ("draft", "change_requested")
            project.can_non_cso_actions = team_edit_phase and ((not is_cso) or settings_privileged)
            project.can_show_submit_review_button = project.review_status in ("draft", "change_requested") and (
                (not is_cso) or settings_privileged
            )
            project.can_submit_for_review = project.can_show_submit_review_button and (
                project.score_overall >= min_score
            )

    def action_save_draft(self):
        for project in self:
            if project.review_status not in ("draft", "change_requested"):
                raise ValidationError(
                    _("Save Draft is only available while the enquiry is in Draft or Change requested.")
                )
            project.write({"review_status": "draft"})

    def _acquire_submit_for_review_lock(self):
        self.ensure_one()
        self.env.cr.execute(
            f"SELECT id FROM {self._table} WHERE id = %s FOR UPDATE",
            (self.id,),
        )

    def action_submit_for_review(self):
        min_score = self._get_submit_review_min_score()
        for project in self:
            project._acquire_submit_for_review_lock()
            project.invalidate_recordset()
            project = project.browse(project.id)
            if project.review_status == "pending_review":
                continue
            if project.review_status not in ("draft", "change_requested"):
                raise ValidationError(
                    _(
                        "This enquiry is no longer in Draft or Change requested and cannot be submitted "
                        "from here."
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
            next_outcome = "open" if project.decision_final == "bid" else "closed"
            project.write(
                {
                    "review_status": "approved",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                    "outcome_status": next_outcome,
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

    def action_open_decline_review_wizard(self):
        self.ensure_one()
        self._require_open_cso_review()
        return {
            "type": "ir.actions.act_window",
            "name": _("Decline"),
            "res_model": "bid.decline.review.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_project_id": self.id},
        }

    def action_decline_review(self, justification=None):
        self._require_open_cso_review()
        reason = (justification or "").strip()
        if not reason:
            raise ValidationError(_("You must enter a justification to decline this enquiry."))
        for project in self:
            project.write(
                {
                    "review_status": "declined",
                    "reviewed_by_id": self.env.user.id,
                    "reviewed_on": fields.Datetime.now(),
                    "outcome_status": "closed",
                    "cso_decline_justification": reason,
                }
            )
            pending_changes = project.change_request_ids.filtered(lambda r: not r.resolved)
            pending_changes.write({"resolved": True, "resolved_date": fields.Datetime.now()})
            esc = html_escape(reason)
            esc_lines = Markup(esc.replace("\n", "<br/>"))
            project.message_post(
                body=Markup("<p><strong>%s</strong></p><p>%s</p>")
                % (html_escape(_("CSO decline justification")), esc_lines),
            )
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
                review_date = fields.Datetime.context_timestamp(project, project.reviewed_on).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                reviewer_name = project.reviewed_by_id.name or "N/A"
                decision = project._selection_display("decision_final")
                body = render_bid_board_email(
                    headline="Project declined",
                    tagline=project.name,
                    intro_lines=[
                        "This bid has been declined at CSO review.",
                        "The justification below was recorded by the reviewer.",
                    ],
                    detail_pairs=[
                        ("Project", project.name),
                        ("Code", project.code or "N/A"),
                        ("Reviewer", reviewer_name),
                        ("Reviewed on", review_date),
                        ("Decision", decision),
                        ("Overall score", f"{project.score_overall:.2f}%"),
                        (_("CSO justification"), reason),
                    ],
                )
                project._send_notification_email(
                    recipients=recipients,
                    subject=f"[Bid Board] Project Declined: {project.name}",
                    body=body,
                )

    def _proposal_scope_work_summary(self):
        self.ensure_one()

        def pct(val):
            v = float(val or 0.0)
            return f"{v:g}%" if v == int(v) else f"{v:.2f}%"

        pairs = [
            (_("Cleaning"), self.scope_cleaning),
            (_("Maintenance"), self.scope_maintenance),
            (_("Security"), self.scope_security),
            (_("Landscaping"), self.scope_landscaping),
            (_("Laundry"), self.scope_laundry),
            (_("Support"), self.scope_support),
            (_("Others"), self.scope_others),
        ]
        details = "; ".join(f"{label} {pct(val)}" for label, val in pairs)
        total = pct(self.scope_total)
        return _("Scope of work from Bid / No-Bid: %s (total %s)") % (details, total)

    def _prepare_proposal_default_values(self):
        self.ensure_one()
        emirate_labels = dict(self._fields["emirate"].selection)
        city = emirate_labels.get(self.emirate, "")
        duration_months_map = {"1y": 12, "2y": 24, "3y": 36, "4y": 48, "5y": 60, "6y": 72}
        months = duration_months_map.get(self.contract_duration) or 12
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
            "services_offered": self._proposal_scope_work_summary(),
            "service_procurement_option": self.contract_type or False,
            "contract_volume_total": self.contract_value,
            "contract_duration_months": months,
            "contract_volume_annual": annual,
            "key_account_name": key_name or False,
            "deadline_date": fields.Date.to_date(self.deadline_datetime) if self.deadline_datetime else False,
        }

    def action_create_proposal(self):
        self.ensure_one()
        if self.review_status != "approved" or self.decision_final != "bid":
            raise ValidationError(_("You can only create a proposal after CSO approval with a Bid decision."))
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
                review_date = fields.Datetime.context_timestamp(project, project.reviewed_on).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
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
        return user.has_group("sales_bid_board.group_bid_board_cso") or user.has_group("base.group_system")

    def _is_review_outcome_locked(self):
        self.ensure_one()
        return self.review_status in ("approved", "declined")

    def _bid_board_locked_for_record_edit(self):
        self.ensure_one()
        return self.review_status in ("pending_review", "approved", "declined")

    def _can_bypass_approved_project_lock(self):
        user = self.env.user
        return (
            user.has_group("sales_bid_board.group_bid_board_cso")
            or user.has_group("sales_bid_board.group_bid_board_manager")
            or user.has_group("base.group_system")
            or self._is_cso_user()
        )

    def _require_open_cso_review(self):
        for project in self:
            if not project._is_cso_user():
                raise ValidationError(
                    _(
                        "Only users in the Bid Board CSO security group (or administrators) can "
                        "approve, decline, or request changes."
                    )
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

            deadline_value = project.deadline_datetime or "N/A"
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
