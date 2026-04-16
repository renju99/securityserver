from odoo import fields, models


class BidChangeRequestWizard(models.TransientModel):
    _name = "bid.change.request.wizard"
    _description = "Bid Change Request Wizard"

    project_id = fields.Many2one(
        "bid.project",
        required=True,
        help="Enquiry the CSO is asking to update before approval.",
    )
    priority = fields.Selection(
        [("low", "Low"), ("medium", "Medium"), ("high", "High")],
        default="medium",
        required=True,
        help="How urgent the requested changes are for the bid team.",
    )
    comments = fields.Text(
        required=True,
        help="Describe what must change on the decision sheet or supporting information.",
    )

    def action_submit_change_request(self):
        self.ensure_one()
        self.project_id.action_request_change(self.comments, self.priority)
        return {"type": "ir.actions.act_window_close"}
