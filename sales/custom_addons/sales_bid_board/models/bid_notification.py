from odoo import api, fields, models

from .bid_email_layout import render_bid_board_email


class BidNotification(models.Model):
    _name = "bid.notification"
    _description = "Bid Notification"
    _order = "deadline_date asc, id desc"

    project_id = fields.Many2one("bid.project", required=True, ondelete="cascade")
    deadline_date = fields.Date(related="project_id.deadline_date", store=True)
    notify_team = fields.Boolean(default=True)
    last_reminder_at = fields.Datetime()
    state = fields.Selection(
        [("pending", "Pending"), ("sent", "Sent"), ("done", "Done")],
        default="pending",
    )
    note = fields.Text()

    def _deadline_date_for_reminder(self):
        self.ensure_one()
        if self.deadline_date:
            return self.deadline_date
        if self.project_id.deadline_datetime:
            return fields.Date.to_date(self.project_id.deadline_datetime)
        return False

    def _reminder_recipients(self):
        self.ensure_one()
        project = self.project_id
        recipients = []
        if project.project_lead_id and project.project_lead_id.email:
            recipients.append(project.project_lead_id.email.strip())
        if self.notify_team:
            for member in project.team_member_ids:
                email = (member.email or "").strip()
                if not email and member.user_id and member.user_id.email:
                    email = (member.user_id.email or "").strip()
                if email:
                    recipients.append(email)
        return list(dict.fromkeys([email for email in recipients if email]))

    def _append_send_log(self, recipients, reminder_label):
        self.ensure_one()
        now = fields.Datetime.now()
        ts = fields.Datetime.context_timestamp(self, now).strftime("%Y-%m-%d %H:%M:%S")
        recipient_text = ", ".join(recipients)
        line = f"[{ts}] Reminder ({reminder_label}) sent to: {recipient_text}"
        existing = (self.note or "").strip()
        self.note = f"{existing}\n{line}" if existing else line
        self.project_id.message_post(body=f"Bid reminder ({reminder_label}) email sent to: {recipient_text}")

    @api.model
    def _cron_send_deadline_reminders(self):
        today = fields.Date.context_today(self)
        reminder_offsets = {7: "T-7", 3: "T-3", 1: "T-1"}
        notifications = self.search([("state", "!=", "done")])
        for notification in notifications:
            project = notification.project_id
            if project.review_status in ("approved", "declined") or project.state == "declined":
                notification.state = "done"
                continue
            deadline_date = notification._deadline_date_for_reminder()
            if not deadline_date:
                continue
            days_left = (deadline_date - today).days
            reminder_label = reminder_offsets.get(days_left)
            if not reminder_label:
                continue
            if notification.last_reminder_at and fields.Date.to_date(notification.last_reminder_at) == today:
                continue
            recipients = notification._reminder_recipients()
            if not recipients:
                continue
            deadline_value = project.deadline_datetime or project.deadline_date or "N/A"
            base_url = notification.env["ir.config_parameter"].sudo().get_param("web.base.url", "")
            project_link = (
                f"{base_url}/web#id={project.id}&model=bid.project&view_type=form" if base_url else ""
            )
            window_lbl = {"T-7": "7 days", "T-3": "3 days", "T-1": "1 day"}.get(reminder_label, reminder_label)
            body = render_bid_board_email(
                headline=f"Submission deadline ({reminder_label})",
                tagline=project.name,
                intro_lines=[
                    f"The bid submission deadline for this project is in {window_lbl}.",
                    "Ensure documents and pricing are finalized before the cut-off.",
                ],
                detail_pairs=[
                    ("Project", project.name),
                    ("Code", project.code or "N/A"),
                    ("Overall score", f"{project.score_overall:.2f}%"),
                    ("Deadline", str(deadline_value)),
                    ("Reminder", reminder_label),
                ],
                cta_label="Open project in Odoo" if project_link else None,
                cta_url=project_link or None,
            )
            project._send_notification_email(
                recipients=recipients,
                subject=f"[Bid Board] Bid submission deadline {reminder_label}: {project.name}",
                body=body,
                chatter_log=False,
            )
            notification.last_reminder_at = fields.Datetime.now()
            notification.state = "sent"
            notification._append_send_log(recipients, reminder_label)
