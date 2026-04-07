from odoo import fields, models


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
