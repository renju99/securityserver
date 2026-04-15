from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from .bid_email_layout import render_bid_board_email


class BidBoardSettings(models.Model):
    _name = "bid.board.settings"
    _description = "Bid Board Settings"
    _order = "id"

    name = fields.Char(default="Default Settings", required=True)
    notification_email_from = fields.Char(
        string="Notification From",
        default='"Berkeley UAE" <noreply@berkeleyuae.com>',
        help="RFC From address for all Bid Board notification emails "
        '(e.g. "Berkeley UAE" <noreply@berkeleyuae.com>). '
        "If empty, the system parameter mail.default.from is used (Outgoing Mail Servers / real senders only — "
        "company or demo placeholder emails are not used as fallbacks).",
    )
    cso_approver_emails = fields.Char(
        string="CSO (Email Approvers)",
        help="Comma-separated addresses that receive CSO review notifications and governance SLA reminders. "
        "This does not grant Approve / Decline / Request change in Odoo — assign the Bid Board / CSO "
        "security group to users who may perform those actions. "
        "Submit-for-review emails follow “Notify CSO on every submission” below.",
    )
    notify_cso_on_all_submissions = fields.Boolean(
        string="Notify CSO on Every Submission",
        default=True,
        help="If enabled, CSO approvers receive an email every time a project is submitted "
        "for review (when CSO emails are set). If disabled, they are notified only when the overall score is above 80%.",
    )
    commercial_manager_email = fields.Char(string="Commercial Manager Email")
    bid_manager_email = fields.Char(string="Bid Manager Email")
    notify_creator_on_approval = fields.Boolean(default=True)
    submit_review_min_score = fields.Float(
        string="Minimum Overall Score for Submit",
        compute="_compute_submit_review_min_score",
        inverse="_inverse_submit_review_min_score",
        readonly=False,
        help="Submit for Review is available only when Overall Score is at or above this percentage.",
    )
    pending_review_sla_days = fields.Integer(
        string="Pending Review SLA Days",
        default=3,
        help="Escalate to CSO approvers when a project remains pending review longer than this number of days.",
    )
    test_notification_recipient = fields.Char(
        string="Test email recipient",
        default="ranjith.krishnan@berkeleyuae.com",
        help="Address used by “Send test email” (Bid Board notification path).",
    )

    @api.model_create_multi
    def create(self, vals_list):
        if self.sudo().search_count([]) >= 1:
            raise ValidationError(
                _(
                    "Bid Board settings already exist. Open the existing configuration (do not create a new record), "
                    "or contact an administrator if you see duplicates in the list."
                )
            )
        return super().create(vals_list)

    @api.model
    def _merge_duplicate_settings_records(self):
        """Keep one row and recover field values from extras (fixes blank UI after duplicate rows)."""
        all_recs = self.sudo().search([], order="id asc")
        if len(all_recs) <= 1:
            return all_recs[:1]
        with_cso = all_recs.filtered(lambda r: (r.cso_approver_emails or "").strip())
        primary = (with_cso[:1] or all_recs[:1]).sudo()
        others = all_recs - primary
        char_fields = [
            "name",
            "notification_email_from",
            "cso_approver_emails",
            "commercial_manager_email",
            "bid_manager_email",
            "test_notification_recipient",
        ]
        vals = {}
        for fname in char_fields:
            current = getattr(primary, fname) or ""
            if isinstance(current, str) and current.strip():
                continue
            for other in others:
                oth = getattr(other, fname) or ""
                if isinstance(oth, str) and oth.strip():
                    vals[fname] = oth
                    break
        if vals:
            primary.write(vals)
        others.sudo().unlink()
        return primary

    @api.model
    def get_singleton(self):
        if self.sudo().search_count([]) > 1:
            self._merge_duplicate_settings_records()
        settings = self.sudo().search([], order="id asc", limit=1)
        if not settings:
            settings = self.sudo().create({"name": "Default Settings"})
        return settings

    def _compute_submit_review_min_score(self):
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            raw = icp.get_param("sales_bid_board.submit_review_min_score", default="70")
            try:
                value = float(raw)
            except (TypeError, ValueError):
                value = 70.0
            rec.submit_review_min_score = max(0.0, min(100.0, value))

    def _inverse_submit_review_min_score(self):
        icp = self.env["ir.config_parameter"].sudo()
        for rec in self:
            value = float(rec.submit_review_min_score or 0.0)
            if value < 0.0 or value > 100.0:
                raise ValidationError(_("Minimum Overall Score for Submit must be between 0 and 100."))
            icp.set_param("sales_bid_board.submit_review_min_score", f"{value:.2f}")

    def resolve_notification_email_from(self):
        self.ensure_one()
        configured = (self.notification_email_from or "").strip()
        if configured:
            return configured
        icp = self.env["ir.config_parameter"].sudo()
        default_from = (icp.get_param("mail.default.from") or "").strip()
        if default_from:
            return default_from
        return False

    def action_send_test_notification_email(self):
        self.ensure_one()
        to_addr = (self.test_notification_recipient or "").strip()
        if not to_addr:
            raise UserError(_("Set a test recipient email address."))
        email_from = self.resolve_notification_email_from()
        if not email_from:
            raise UserError(
                _("Set Notification From here or configure the mail.default.from system parameter before testing.")
            )
        subject = "[Bid Board] Test notification email"
        user = self.env.user
        body = render_bid_board_email(
            headline="Test email",
            tagline="Bid Board notifications",
            intro_lines=[
                "This is a test message using the same HTML layout as live Bid Board emails.",
                "If it looks correct in your inbox, submission and review notifications will match this style.",
            ],
            detail_pairs=[
                ("To", to_addr),
                ("From", email_from),
                ("Sent by (Odoo user)", user.name or ""),
            ],
            footer_hint=(
                "Test only — no action required. Configure Notification From and SMTP under Odoo settings if delivery fails."
            ),
        )
        mail = self.env["mail.mail"].sudo().create(
            {
                "subject": subject,
                "body_html": body,
                "email_to": to_addr,
                "email_from": email_from,
                "auto_delete": False,
                "model": self._name,
                "res_id": self.id,
            }
        )
        mail.send()
        mail.invalidate_recordset(["state", "failure_reason"])
        mail = mail.env["mail.mail"].sudo().browse(mail.id)
        if mail.state == "exception":
            raise UserError(mail.failure_reason or _("Email delivery failed."))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Test email"),
                "message": _("Sent to %s — check inbox (and spam).") % to_addr,
                "type": "success",
                "sticky": False,
            },
        }
