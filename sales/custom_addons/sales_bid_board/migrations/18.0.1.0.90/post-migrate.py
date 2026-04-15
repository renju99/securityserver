"""Replace legacy 15-row default scorecard with the full Berkeley template."""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)

_LEGACY_DEFAULT_NAMES = (
    "Strategic importance",
    "Domain of Berkeley's activities",
    "Potential for additional works",
    "Strategic customer",
    "Customer size / structure",
    "Customer track record",
    "Term of contract",
    "RFP documents quality",
    "Competitive advantage",
    "Estimated GM",
    "Payment terms",
    "Penalties",
    "Condition at contract start",
    "Mobilization period",
    "Similar experience",
)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    Project = env["bid.project"]
    updated = 0
    for project in Project.search([]):
        lines = project.criteria_line_ids
        if len(lines) != len(_LEGACY_DEFAULT_NAMES):
            continue
        names = tuple(lines.sorted("id").mapped("name"))
        if names != _LEGACY_DEFAULT_NAMES:
            continue
        lines.unlink()
        project._ensure_default_scorecard()
        updated += 1
    if updated:
        _logger.info(
            "sales_bid_board: refreshed default scorecard on %s bid.project record(s)",
            updated,
        )
