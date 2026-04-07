from odoo import fields, models


class BidChangeRequest(models.Model):
    _name = "bid.change.request"
    _description = "Bid Change Request"
    _order = "create_date desc, id desc"

    project_id = fields.Many2one("bid.project", required=True, ondelete="cascade")
    reviewer_id = fields.Many2one("res.users", default=lambda self: self.env.user, required=True)
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
    )
    comments = fields.Text(required=True)
    resolved = fields.Boolean(default=False)
    resolved_date = fields.Datetime()
