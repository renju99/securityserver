from odoo import fields, models


class BidDeclineReviewWizard(models.TransientModel):
    _name = "bid.decline.review.wizard"
    _description = "Bid CSO Decline Wizard"

    project_id = fields.Many2one(
        "bid.project",
        required=True,
        help="Enquiry being declined at CSO review.",
    )
    justification = fields.Text(
        string="Justification",
        required=True,
        help="Explain why this enquiry is being declined. This is stored on the record and sent to notified contacts.",
    )

    def action_confirm_decline(self):
        self.ensure_one()
        self.project_id.action_decline_review(self.justification)
        return {"type": "ir.actions.act_window_close"}
