from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .bid_email_layout import render_bid_board_email


class ResPartner(models.Model):
    _inherit = "res.partner"

    cso_contact_approval_state = fields.Selection(
        [
            ("not_required", "Not required"),
            ("pending", "Pending CSO approval"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        string="CSO Contact Approval",
        default="not_required",
        copy=False,
        tracking=True,
        help="Company contacts require CSO approval before they can be treated as approved contacts.",
    )
    cso_contact_approved_by_id = fields.Many2one(
        "res.users",
        string="CSO Approved By",
        copy=False,
        tracking=True,
    )
    cso_contact_approved_on = fields.Datetime(
        string="CSO Approved On",
        copy=False,
        tracking=True,
    )
    cso_contact_rejected_reason = fields.Text(
        string="CSO Rejection Reason",
        copy=False,
        tracking=True,
    )
    cso_contact_is_company_contact = fields.Boolean(
        string="Is Company Contact",
        compute="_compute_cso_contact_is_company_contact",
    )
    cso_contact_can_review = fields.Boolean(
        string="Can CSO Review",
        compute="_compute_cso_contact_can_review",
    )

    @api.depends("is_company", "parent_id")
    def _compute_cso_contact_is_company_contact(self):
        for partner in self:
            partner.cso_contact_is_company_contact = bool(partner.is_company or partner.parent_id)

    @api.depends_context("uid")
    def _compute_cso_contact_can_review(self):
        can_review = self._is_cso_contact_reviewer_user()
        for partner in self:
            partner.cso_contact_can_review = can_review

    def _is_cso_contact_reviewer_user(self):
        user = self.env.user
        if (
            user.has_group("sales_bid_board.group_bid_board_cso")
            or user.has_group("sales_bid_board.group_bid_board_manager")
            or user.has_group("base.group_system")
        ):
            return True
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        configured = self.env["bid.project"]._split_emails(settings.cso_approver_emails)
        user_email = (user.email or "").strip().lower()
        return bool(user_email and user_email in configured)

    @api.model
    def _requires_cso_contact_approval(self, vals):
        company_type = vals.get("company_type")
        if company_type is not None:
            return company_type == "company" or bool(vals.get("parent_id"))
        is_company = vals.get("is_company")
        if is_company is None:
            is_company = False
        parent_id = vals.get("parent_id")
        return bool(is_company or parent_id)

    @api.model_create_multi
    def create(self, vals_list):
        self._require_sales_manager_for_contact_creation()
        can_bypass = self.env.user.has_group("sales_bid_board.group_bid_board_cso") or self.env.user.has_group(
            "sales_bid_board.group_bid_board_manager"
        ) or self.env.user.has_group("base.group_system")
        patched_vals_list = []
        for vals in vals_list:
            vals = dict(vals)
            if self._requires_cso_contact_approval(vals):
                if can_bypass:
                    vals.setdefault("cso_contact_approval_state", "approved")
                    vals.setdefault("cso_contact_approved_by_id", self.env.user.id)
                    vals.setdefault("cso_contact_approved_on", fields.Datetime.now())
                else:
                    vals["cso_contact_approval_state"] = "pending"
                    vals["cso_contact_approved_by_id"] = False
                    vals["cso_contact_approved_on"] = False
                    vals["cso_contact_rejected_reason"] = False
            patched_vals_list.append(vals)
        partners = super().create(patched_vals_list)
        partners.filtered(
            lambda p: p.cso_contact_is_company_contact and p.cso_contact_approval_state == "pending"
        )._notify_cso_contact_pending_approval()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if self.env.context.get("bid_board_contact_approval_sync"):
            return res
        can_bypass = self.env.user.has_group("sales_bid_board.group_bid_board_cso") or self.env.user.has_group(
            "sales_bid_board.group_bid_board_manager"
        ) or self.env.user.has_group("base.group_system")
        if can_bypass:
            return res
        for partner in self:
            if not partner.cso_contact_is_company_contact:
                if partner.cso_contact_approval_state != "not_required":
                    partner.with_context(bid_board_contact_approval_sync=True).write(
                        {
                            "cso_contact_approval_state": "not_required",
                            "cso_contact_approved_by_id": False,
                            "cso_contact_approved_on": False,
                            "cso_contact_rejected_reason": False,
                        }
                    )
                continue
            if partner.cso_contact_approval_state in ("pending", "approved"):
                continue
            partner.with_context(bid_board_contact_approval_sync=True).write(
                {
                    "cso_contact_approval_state": "pending",
                    "cso_contact_approved_by_id": False,
                    "cso_contact_approved_on": False,
                    "cso_contact_rejected_reason": False,
                }
            )
            partner._notify_cso_contact_pending_approval()
        return res

    def _require_sales_manager_for_contact_creation(self):
        if self.env.su:
            return
        user = self.env.user
        allowed = user.has_group("sales_bid_board.group_bid_board_sales_manager") or user.has_group(
            "base.group_system"
        )
        if not allowed:
            raise ValidationError(_("Only Sales Managers can create contacts."))

    def action_cso_approve_company_contact(self):
        self._require_cso_contact_reviewer()
        for partner in self:
            if not partner.cso_contact_is_company_contact:
                continue
            partner.write(
                {
                    "cso_contact_approval_state": "approved",
                    "cso_contact_approved_by_id": self.env.user.id,
                    "cso_contact_approved_on": fields.Datetime.now(),
                    "cso_contact_rejected_reason": False,
                }
            )

    def action_cso_reject_company_contact(self):
        self._require_cso_contact_reviewer()
        for partner in self:
            if not partner.cso_contact_is_company_contact:
                continue
            partner.write(
                {
                    "cso_contact_approval_state": "rejected",
                    "cso_contact_approved_by_id": False,
                    "cso_contact_approved_on": False,
                }
            )

    def action_cso_submit_company_contact_for_approval(self):
        for partner in self:
            if not partner.cso_contact_is_company_contact:
                continue
            partner.write(
                {
                    "cso_contact_approval_state": "pending",
                    "cso_contact_approved_by_id": False,
                    "cso_contact_approved_on": False,
                    "cso_contact_rejected_reason": False,
                }
            )
            partner._notify_cso_contact_pending_approval()

    def _require_cso_contact_reviewer(self):
        if not self._is_cso_contact_reviewer_user():
            raise ValidationError(
                _("Only CSO, Bid Board administrators, or system administrators can review company contacts.")
            )

    def _validate_cso_contact_approved_for_sales(self):
        for partner in self:
            if not partner.cso_contact_is_company_contact:
                continue
            if partner.cso_contact_approval_state == "approved":
                continue
            if partner.cso_contact_approval_state == "pending":
                raise ValidationError(
                    _(
                        "The selected contact '%(contact)s' is pending CSO approval and cannot be used in sales workflows yet."
                    )
                    % {"contact": partner.display_name}
                )
            if partner.cso_contact_approval_state == "rejected":
                raise ValidationError(
                    _(
                        "The selected contact '%(contact)s' was rejected by CSO and cannot be used in sales workflows."
                    )
                    % {"contact": partner.display_name}
                )
            raise ValidationError(
                _(
                    "The selected contact '%(contact)s' must be approved by CSO before it can be used in sales workflows."
                )
                % {"contact": partner.display_name}
            )

    def _notify_cso_contact_pending_approval(self):
        settings = self.env["bid.board.settings"].sudo().get_singleton()
        recipients = self.env["bid.project"]._split_emails(settings.cso_approver_emails)
        recipients = list(dict.fromkeys([email for email in recipients if email]))
        approver_users = self._get_cso_approver_users_from_emails(recipients)
        base_url = self.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
        for partner in self:
            if not recipients:
                partner.message_post(
                    body=_(
                        "CSO approval is pending, but no CSO approver emails are configured in Bid Board Settings."
                    )
                )
                continue
            partner_link = (
                f"{base_url}/web#id={partner.id}&model=res.partner&view_type=form" if base_url else ""
            )
            body = render_bid_board_email(
                headline="Company contact approval needed",
                tagline=partner.name or _("Unnamed Contact"),
                intro_lines=[
                    "A new company contact was created and is waiting for CSO approval.",
                    "Please review the contact in Odoo and approve or reject it.",
                ],
                detail_pairs=[
                    ("Contact", partner.name or "N/A"),
                    ("Company", partner.parent_id.name or "N/A"),
                    ("Email", partner.email or "N/A"),
                    ("Phone", partner.phone or "N/A"),
                    ("Status", "Pending CSO approval"),
                ],
                cta_label="Open contact in Odoo" if partner_link else None,
                cta_url=partner_link or None,
            )
            email_from = settings.resolve_notification_email_from()
            if not email_from:
                partner.message_post(
                    body=_(
                        "CSO approval is pending, but email was not sent because Notification From is not configured."
                    )
                )
            else:
                self.env["mail.mail"].sudo().create(
                    {
                        "subject": f"[Bid Board] Company Contact Approval Needed: {partner.name or 'Contact'}",
                        "body_html": body,
                        "email_to": ",".join(recipients),
                        "email_from": email_from,
                        "auto_delete": False,
                        "model": "res.partner",
                        "res_id": partner.id,
                    }
                ).send()
                partner.message_post(
                    body=_("Submitted for CSO approval. Notification sent to: %s") % ", ".join(recipients)
                )
            partner._create_cso_approval_activities(approver_users)

    def _get_cso_approver_users_from_emails(self, recipients):
        if not recipients:
            return self.env["res.users"]
        normalized = {email.strip().lower() for email in recipients if email and email.strip()}
        if not normalized:
            return self.env["res.users"]
        users = self.env["res.users"].sudo().search([])
        matched = users.filtered(
            lambda u: (
                ((u.email or "").strip().lower() in normalized)
                or ((u.partner_id.email or "").strip().lower() in normalized)
                or ((u.login or "").strip().lower() in normalized)
            )
        )
        return matched

    def _create_cso_approval_activities(self, approver_users):
        if not approver_users:
            self.message_post(
                body=_(
                    "CSO approval activity was not created because no internal users match the configured CSO emails."
                )
            )
            return
        todo_type = self.env.ref("mail.mail_activity_data_todo", raise_if_not_found=False)
        if not todo_type:
            return
        summary = _("CSO approval needed for customer/contact")
        for partner in self:
            for user in approver_users:
                existing = self.env["mail.activity"].sudo().search_count(
                    [
                        ("res_model", "=", "res.partner"),
                        ("res_id", "=", partner.id),
                        ("user_id", "=", user.id),
                        ("summary", "=", summary),
                        ("activity_type_id", "=", todo_type.id),
                    ]
                )
                if existing:
                    continue
                self.env["mail.activity"].sudo().create(
                    {
                        "activity_type_id": todo_type.id,
                        "summary": summary,
                        "note": _(
                            "Please review this customer/contact and approve or reject CSO contact approval status."
                        ),
                        "res_model_id": self.env["ir.model"]._get_id("res.partner"),
                        "res_id": partner.id,
                        "user_id": user.id,
                        "date_deadline": fields.Date.context_today(self),
                    }
                )
