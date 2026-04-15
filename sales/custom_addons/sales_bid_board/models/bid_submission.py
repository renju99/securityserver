from odoo import api, fields, models


class BidSubmission(models.Model):
    _name = "bid.submission"
    _description = "Bid Submission"
    _order = "submitted_date desc, id desc"

    name = fields.Char(required=True)
    project_id = fields.Many2one("bid.project", required=True, ondelete="cascade")
    owner_id = fields.Many2one("res.users", default=lambda self: self.env.user)
    submitted_date = fields.Date(default=fields.Date.today)
    status = fields.Selection(
        [("draft", "Draft"), ("submitted", "Submitted"), ("won", "Won"), ("lost", "Lost")],
        default="draft",
    )
    notes = fields.Text()
    bid_calendar_start = fields.Datetime(
        string="Calendar date",
        compute="_compute_bid_submission_calendar",
        store=True,
        help="Submitted-for-review date (start of day) for calendar views.",
    )
    bid_calendar_color = fields.Integer(
        string="Calendar color",
        compute="_compute_bid_submission_calendar",
        store=True,
        help="Tied to enquiry review status after submission.",
    )

    @api.depends("submitted_date", "project_id", "project_id.review_status")
    def _compute_bid_submission_calendar(self):
        status_colors = {
            "pending_review": 2,
            "change_requested": 3,
            "approved": 10,
            "declined": 11,
            "draft": 5,
        }
        for rec in self:
            if rec.submitted_date:
                rec.bid_calendar_start = fields.Datetime.to_datetime(rec.submitted_date)
            else:
                rec.bid_calendar_start = False
            p = rec.project_id
            rec.bid_calendar_color = status_colors.get(p.review_status, 8) if p else 0
