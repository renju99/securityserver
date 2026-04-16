from odoo import fields, models


class BidTeamMember(models.Model):
    _name = "bid.team.member"
    _description = "Bid Team Member"
    _order = "department, role, id"

    name = fields.Char(required=True)
    user_id = fields.Many2one("res.users")
    project_ids = fields.Many2many(
        "bid.project",
        "bid_project_bid_team_member_rel",
        "bid_team_member_id",
        "bid_project_id",
        string="Enquiries",
        readonly=True,
        help="Enquiries this team member is assigned to.",
    )
    email = fields.Char()
    department = fields.Selection(
        [("sales", "Sales"), ("commercial", "Commercial"), ("technical", "Technical")],
        required=True,
        default="sales",
    )
    role = fields.Char(required=True)
    active = fields.Boolean(default=True)
