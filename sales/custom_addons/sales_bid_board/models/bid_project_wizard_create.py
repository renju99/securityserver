from odoo import fields, models


class BidProjectCreateWizard(models.TransientModel):
    _name = "bid.project.create.wizard"
    _description = "Bid Project Create Wizard"

    name = fields.Char(
        required=True,
        help="Working title for the new enquiry.",
    )
    client_name = fields.Char(
        required=True,
        help="Client name as it should appear on the enquiry.",
    )
    project_lead_id = fields.Many2one(
        "res.users",
        required=True,
        default=lambda self: self.env.user,
        help="Default project lead and sales rep for the new enquiry.",
    )
    team_member_ids = fields.Many2many(
        "bid.team.member",
        string="Team Members",
        help="Optional team members to attach immediately.",
    )
    deadline_datetime = fields.Datetime(
        required=True,
        help="First submission or review deadline (date and time).",
    )
    is_priority = fields.Boolean(
        string="Priority flag",
        default=False,
        help="Mark this new enquiry as high priority.",
    )
    progress = fields.Text(
        help="Optional preparation status copied to the new enquiry (free text).",
    )

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
                "contract_value": 0.0,
                "outcome_status": "open",
                "is_priority": self.is_priority,
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
