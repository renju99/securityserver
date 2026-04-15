"""Bid / No-Bid enquiry outcome (Open / Won / Lost / Closed) and priority flag.

Kept in a separate file so `bid.project` always picks up these fields even if a stale or
partial `bid_project.py` is deployed; views and dashboards depend on `outcome_status`.
"""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BidProjectBidStatus(models.Model):
    _inherit = "bid.project"

    outcome_status = fields.Selection(
        [
            ("open", "Open"),
            ("won", "Won"),
            ("lost", "Lost"),
            ("closed", "Closed"),
        ],
        string="Bid status",
        default="open",
        required=True,
        tracking=True,
        help="Tender outcome for this enquiry (like proposal status): Open while in play, then Won, Lost, or Closed.",
    )
    is_priority = fields.Boolean(
        string="Priority",
        default=False,
        tracking=True,
        help="Flag this enquiry as high priority (replaces the old Priority state).",
    )

    @api.constrains("outcome_status", "review_status", "decision_final")
    def _check_bid_outcome_status(self):
        for rec in self:
            if rec.outcome_status in ("won", "lost") and rec.review_status != "approved":
                raise ValidationError(
                    _("Bid status Won or Lost is only allowed after CSO approval.")
                )
            if rec.outcome_status == "won" and rec.decision_final != "bid":
                raise ValidationError(_("Bid status Won requires the enquiry decision to be Bid."))
