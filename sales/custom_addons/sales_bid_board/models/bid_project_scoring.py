from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class BidProjectScoring(models.Model):
    _inherit = "bid.project"

    @api.model
    def _default_scorecard_line_commands(self):
        """(0, 0, vals) x-2-m commands for the standard scorecard (new form + post-create)."""
        return [
            (
                0,
                0,
                {
                    "category": category,
                    "name": name,
                    "option_1_text": option_1,
                    "option_2_text": option_2,
                    "option_3_text": option_3,
                    "score": "3",
                    "weight": 1.0,
                },
            )
            for category, name, option_1, option_2, option_3 in self._SCORECARD_TEMPLATE_ROWS
        ]

    def _ensure_default_scorecard(self):
        commands = self._default_scorecard_line_commands()
        for project in self:
            if project.criteria_line_ids:
                continue
            project.write({"criteria_line_ids": commands})

    def action_load_default_scorecard(self):
        """Backward-compatible; scorecard is usually added automatically on create/copy."""
        self._ensure_default_scorecard()

    @api.depends(
        "criteria_line_ids",
        "criteria_line_ids.score",
        "criteria_line_ids.weight",
        "criteria_line_ids.category",
    )
    def _compute_scores(self):
        categories = {
            "strategy": "score_strategy",
            "customer": "score_customer",
            "commercial": "score_commercial",
            "finance": "score_finance",
            "operations": "score_operations",
        }
        for project in self:
            score_map = {key: 0.0 for key in categories}
            total_map = {key: 0.0 for key in categories}
            for line in project.criteria_line_ids:
                total_map[line.category] += line.weight
                line_score = float(line.score or 0.0)
                score_map[line.category] += (line_score / 3.0) * 100.0 * line.weight

            category_values = []
            for key, field_name in categories.items():
                value = 0.0
                if total_map[key]:
                    value = score_map[key] / total_map[key]
                setattr(project, field_name, value)
                if total_map[key]:
                    category_values.append(value)

            project.score_overall = sum(category_values) / len(category_values) if category_values else 0.0

    @api.depends("score_overall")
    def _compute_decisions(self):
        threshold = self.env["bid.project"]._get_submit_review_min_score()
        for project in self:
            project.decision_final = "bid" if project.score_overall >= threshold else "no_bid"
            if project.decision_final == "bid":
                project.recommendation_text = "BID RECOMMENDED"
                project.recommendation_note = "Proceed with Bid"
            else:
                project.recommendation_text = "NO BID RECOMMENDED"
                project.recommendation_note = "Do not proceed with Bid"


class BidProjectCriteria(models.Model):
    _name = "bid.project.criteria"
    _description = "Bid Project Criteria"
    _order = "category, id"

    project_id = fields.Many2one(
        "bid.project",
        required=True,
        ondelete="cascade",
        help="Parent enquiry this scorecard line belongs to.",
    )
    name = fields.Char(
        required=True,
        help="Criterion text (e.g. from the standard scorecard row).",
    )
    category = fields.Selection(
        [
            ("strategy", "Strategy"),
            ("customer", "Customer"),
            ("commercial", "Commercial"),
            ("finance", "Finance"),
            ("operations", "Operations"),
        ],
        required=True,
        default="strategy",
        help="Scorecard pillar. Category scores are averaged into the overall percentage.",
    )
    score = fields.Selection(
        [("1", "1"), ("2", "2"), ("3", "3")],
        required=True,
        default="2",
        help="Pick 1 (low), 2 (medium), or 3 (high) against the three options shown for this row.",
    )
    option_1_text = fields.Char(
        string="1",
        help="Label for the lowest score option on this row.",
    )
    option_2_text = fields.Char(
        string="2",
        help="Label for the middle score option.",
    )
    option_3_text = fields.Char(
        string="3",
        help="Label for the highest score option.",
    )
    weight = fields.Float(
        default=1.0,
        help="Importance of this row within its category (higher weight counts more in the category score).",
    )
    comment = fields.Char(
        help="Optional note for reviewers (risks, assumptions, or evidence).",
    )

    def _bid_board_check_parent_editable(self, project):
        if (
            project
            and project._bid_board_locked_for_record_edit()
            and not project._can_bypass_approved_project_lock()
        ):
            raise ValidationError(
                _(
                    "The scorecard cannot be changed while the enquiry is pending CSO review, "
                    "or after CSO approval or decline. Only CSO approvers, Bid Board managers, "
                    "or administrators can change it."
                )
            )

    @api.model_create_multi
    def create(self, vals_list):
        Project = self.env["bid.project"]
        for vals in vals_list:
            pid = vals.get("project_id") or self.env.context.get("default_project_id")
            if pid:
                self._bid_board_check_parent_editable(Project.browse(pid))
        return super().create(vals_list)

    def write(self, vals):
        for line in self:
            self._bid_board_check_parent_editable(line.project_id)
        return super().write(vals)

    def unlink(self):
        for line in self:
            self._bid_board_check_parent_editable(line.project_id)
        return super().unlink()
