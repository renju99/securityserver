from odoo import fields, models


class BidTeamMember(models.Model):
    _name = "bid.team.member"
    _description = "Bid Team Member"
    _order = "department, role, id"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users")
    email = fields.Char()
    department = fields.Selection(
        [("sales", "Sales"), ("commercial", "Commercial"), ("technical", "Technical")],
        required=True,
        default="sales",
    )
    role = fields.Char(required=True)
    active = fields.Boolean(default=True)
