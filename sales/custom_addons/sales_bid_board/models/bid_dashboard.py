from datetime import timedelta

from odoo import api, fields, models


class SalesBidBoardDashboard(models.Model):
    _name = "sales_bid_board.dashboard"
    _description = "Sales Bid Board Dashboard"

    name = fields.Char(default="Bid Board Analytics", required=True)

    @api.model
    def _sanitize_filter_params(self, filter_params):
        filter_params = filter_params or {}
        allowed = {
            "date_from",
            "date_to",
            "state",
            "review_status",
            "decision_final",
            "sales_rep_id",
            "project_lead_id",
            "industry",
            "emirate",
            "stage_id",
        }
        clean = {}
        for key, value in filter_params.items():
            if key not in allowed or value in (None, "", False):
                continue
            clean[key] = value
        return clean

    @api.model
    def _build_project_domain(self, clean):
        domain = []
        if clean.get("date_from"):
            domain.append(("create_date", ">=", clean["date_from"]))
        if clean.get("date_to"):
            domain.append(("create_date", "<=", clean["date_to"]))
        if clean.get("state"):
            domain.append(("state", "=", clean["state"]))
        if clean.get("review_status"):
            domain.append(("review_status", "=", clean["review_status"]))
        if clean.get("decision_final"):
            domain.append(("decision_final", "=", clean["decision_final"]))
        if clean.get("sales_rep_id"):
            domain.append(("sales_rep", "=", int(clean["sales_rep_id"])))
        if clean.get("project_lead_id"):
            domain.append(("project_lead_id", "=", int(clean["project_lead_id"])))
        if clean.get("industry"):
            domain.append(("industry", "=", clean["industry"]))
        if clean.get("emirate"):
            domain.append(("emirate", "=", clean["emirate"]))
        if clean.get("stage_id"):
            domain.append(("stage_id", "=", int(clean["stage_id"])))
        return domain

    @api.model
    def _previous_period_domain(self, clean, base_domain):
        if not clean.get("date_from") or not clean.get("date_to"):
            return []
        date_from = fields.Datetime.to_datetime(clean["date_from"])
        date_to = fields.Datetime.to_datetime(clean["date_to"])
        delta = date_to - date_from
        prev_from = date_from - delta - timedelta(days=1)
        prev_to = date_from - timedelta(days=1)
        prev_domain = [d for d in base_domain if d[0] not in ("create_date",)]
        prev_domain += [("create_date", ">=", prev_from), ("create_date", "<=", prev_to)]
        return prev_domain

    @api.model
    def _metric_value(self, row, base, agg):
        if not row:
            return 0.0
        for key in (f"{base}_{agg}", f"{base}:{agg}", base):
            if key in row and row[key] not in (None, False):
                return row[key]
        return 0.0

    @api.model
    def _count_value(self, row):
        if not row:
            return 0
        if "__count" in row:
            return row["__count"]
        for key, value in row.items():
            if key.endswith("_count") or key == "id_count":
                return value or 0
        return 0

    @api.model
    def _kpi(self, name, value, previous, icon, color, action, suffix=""):
        return {
            "name": name,
            "value": value,
            "previous_value": previous,
            "icon": icon,
            "color": color,
            "action": action,
            "suffix": suffix,
        }

    @api.model
    def _get_filter_options(self):
        project = self.env["bid.project"]
        users = self.env["res.users"]
        stages = self.env["bid.project.stage"].search([], order="sequence")

        sales_rep_ids = [g["sales_rep"][0] for g in project.read_group([], ["sales_rep"], ["sales_rep"]) if g.get("sales_rep")]
        lead_ids = [g["project_lead_id"][0] for g in project.read_group([], ["project_lead_id"], ["project_lead_id"]) if g.get("project_lead_id")]
        sales_reps = users.browse(sales_rep_ids)
        leads = users.browse(lead_ids)

        return {
            "states": [{"value": k, "label": v} for k, v in dict(project._fields["state"].selection).items()],
            "review_statuses": [{"value": k, "label": v} for k, v in dict(project._fields["review_status"].selection).items()],
            "decisions": [{"value": k, "label": v} for k, v in dict(project._fields["decision_final"].selection).items()],
            "industries": [{"value": k, "label": v} for k, v in dict(project._fields["industry"].selection).items()],
            "emirates": [{"value": k, "label": v} for k, v in dict(project._fields["emirate"].selection).items()],
            "sales_reps": [{"value": user.id, "label": user.name} for user in sales_reps],
            "project_leads": [{"value": user.id, "label": user.name} for user in leads],
            "stages": [{"value": stage.id, "label": stage.name} for stage in stages],
        }

    @api.model
    def get_dashboard_data(self, dashboard_id=None, context=None, filter_params=None):
        clean = self._sanitize_filter_params(filter_params)
        project_model = self.env["bid.project"]
        submission_model = self.env["bid.submission"]
        change_model = self.env["bid.change.request"]
        stage_model = self.env["bid.project.stage"]

        domain = self._build_project_domain(clean)
        prev_domain = self._previous_period_domain(clean, domain)

        total = project_model.search_count(domain)
        pending = project_model.search_count(domain + [("review_status", "=", "pending_review")])
        approved = project_model.search_count(domain + [("review_status", "=", "approved")])
        change_requested = project_model.search_count(domain + [("review_status", "=", "change_requested")])
        bid_count = project_model.search_count(domain + [("decision_final", "=", "bid")])
        no_bid_count = project_model.search_count(domain + [("decision_final", "=", "no_bid")])

        value_group = project_model.read_group(domain, ["contract_value:sum", "score_overall:avg"], [])
        vg_row = value_group[0] if value_group else {}
        total_value = self._metric_value(vg_row, "contract_value", "sum")
        avg_score = self._metric_value(vg_row, "score_overall", "avg")

        if prev_domain:
            prev_total = project_model.search_count(prev_domain)
            prev_pending = project_model.search_count(prev_domain + [("review_status", "=", "pending_review")])
            prev_approved = project_model.search_count(prev_domain + [("review_status", "=", "approved")])
            prev_change = project_model.search_count(prev_domain + [("review_status", "=", "change_requested")])
            prev_bid = project_model.search_count(prev_domain + [("decision_final", "=", "bid")])
            prev_no_bid = project_model.search_count(prev_domain + [("decision_final", "=", "no_bid")])
            prev_value_group = project_model.read_group(prev_domain, ["contract_value:sum", "score_overall:avg"], [])
            pvg_row = prev_value_group[0] if prev_value_group else {}
            prev_total_value = self._metric_value(pvg_row, "contract_value", "sum")
            prev_avg_score = self._metric_value(pvg_row, "score_overall", "avg")
        else:
            prev_total = prev_pending = prev_approved = prev_change = prev_bid = prev_no_bid = 0
            prev_total_value = prev_avg_score = 0.0

        kpis = [
            self._kpi("Total Bids", total, prev_total, "fa-folder-open", "primary", "action_view_projects_all"),
            self._kpi("Pending Review", pending, prev_pending, "fa-hourglass-half", "warning", "action_view_projects_pending_review"),
            self._kpi("Approved", approved, prev_approved, "fa-check-circle", "success", "action_view_projects_approved"),
            self._kpi("Change Requested", change_requested, prev_change, "fa-exclamation-circle", "info", "action_view_projects_change_requested"),
            self._kpi("Bid Recommended", bid_count, prev_bid, "fa-thumbs-up", "success", "action_view_projects_bid"),
            self._kpi("No Bid", no_bid_count, prev_no_bid, "fa-thumbs-down", "danger", "action_view_projects_no_bid"),
            self._kpi("Contract Value", round(total_value, 2), round(prev_total_value, 2), "fa-money", "secondary", "action_view_projects_value", " AED"),
            self._kpi("Avg Score", round(avg_score or 0.0, 2), round(prev_avg_score or 0.0, 2), "fa-line-chart", "primary", "action_view_projects_scored", "%"),
        ]

        review_sel = dict(project_model._fields["review_status"].selection)
        status_groups = project_model.read_group(domain, ["id:count"], ["review_status"])
        status_labels, status_keys, status_values = [], [], []
        for row in status_groups:
            key = row.get("review_status")
            if key:
                status_keys.append(key)
                status_labels.append(review_sel.get(key, key))
                status_values.append(self._count_value(row))

        decision_sel = dict(project_model._fields["decision_final"].selection)
        decision_groups = project_model.read_group(domain, ["id:count"], ["decision_final"])
        decision_labels, decision_keys, decision_values = [], [], []
        for row in decision_groups:
            key = row.get("decision_final")
            if key:
                decision_keys.append(key)
                decision_labels.append(decision_sel.get(key, key))
                decision_values.append(self._count_value(row))

        industry_sel = dict(project_model._fields["industry"].selection)
        industry_groups = project_model.read_group(domain, ["id:count", "score_overall:avg"], ["industry"])
        industry_labels, industry_keys, industry_values, industry_score_values = [], [], [], []
        for row in industry_groups:
            key = row.get("industry")
            if key:
                industry_keys.append(key)
                industry_labels.append(industry_sel.get(key, key))
                industry_values.append(self._count_value(row))
                industry_score_values.append(round(self._metric_value(row, "score_overall", "avg"), 2))

        emirate_sel = dict(project_model._fields["emirate"].selection)
        emirate_groups = project_model.read_group(domain, ["contract_value:sum"], ["emirate"])
        emirate_labels, emirate_keys, emirate_values = [], [], []
        for row in emirate_groups:
            key = row.get("emirate")
            if key:
                emirate_keys.append(key)
                emirate_labels.append(emirate_sel.get(key, key))
                emirate_values.append(round(self._metric_value(row, "contract_value", "sum"), 2))

        stage_map = {s.id: s.name for s in stage_model.search([], order="sequence")}
        stage_groups = project_model.read_group(domain, ["id:count"], ["stage_id"])
        stage_labels, stage_keys, stage_values = [], [], []
        for row in stage_groups:
            stage_data = row.get("stage_id")
            if stage_data:
                stage_id = stage_data[0]
                stage_keys.append(stage_id)
                stage_labels.append(stage_map.get(stage_id, stage_data[1]))
                stage_values.append(self._count_value(row))

        trend_groups = project_model.read_group(domain, ["id:count"], ["create_date:month"])
        trend_labels, trend_keys, trend_values = [], [], []
        for row in trend_groups:
            label = row.get("create_date:month")
            if label:
                label_str = str(label)
                trend_labels.append(label_str)
                trend_keys.append(label_str)
                trend_values.append(self._count_value(row))

        charts = [
            {
                "type": "doughnut",
                "title": "Review Status Distribution",
                "labels": status_labels or ["No Data"],
                "keys": status_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "review_status",
                "action_type": "selection",
                "datasets": [{"label": "Projects", "data": status_values or [0]}],
            },
            {
                "type": "pie",
                "title": "Bid / No Bid Split",
                "labels": decision_labels or ["No Data"],
                "keys": decision_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "decision_final",
                "action_type": "selection",
                "datasets": [{"label": "Projects", "data": decision_values or [0]}],
            },
            {
                "type": "bar",
                "title": "Projects by Industry",
                "labels": industry_labels or ["No Data"],
                "keys": industry_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "industry",
                "action_type": "selection",
                "datasets": [{"label": "Projects", "data": industry_values or [0]}],
            },
            {
                "type": "bar",
                "title": "Average Score by Industry",
                "labels": industry_labels or ["No Data"],
                "keys": industry_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "industry",
                "action_type": "selection",
                "datasets": [{"label": "Score %", "data": industry_score_values or [0]}],
            },
            {
                "type": "bar",
                "title": "Contract Value by Emirate",
                "labels": emirate_labels or ["No Data"],
                "keys": emirate_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "emirate",
                "action_type": "selection",
                "datasets": [{"label": "Contract Value (AED)", "data": emirate_values or [0]}],
            },
            {
                "type": "bar",
                "title": "Projects by Stage",
                "labels": stage_labels or ["No Data"],
                "keys": stage_keys or [0],
                "action_model": "bid.project",
                "action_domain_field": "stage_id",
                "action_type": "many2one",
                "datasets": [{"label": "Projects", "data": stage_values or [0]}],
            },
            {
                "type": "line",
                "title": "Bids Created Trend",
                "labels": trend_labels or ["No Data"],
                "keys": trend_keys or [""],
                "action_model": "bid.project",
                "action_domain_field": "create_date",
                "action_type": "date_period",
                "datasets": [{"label": "Bids", "data": trend_values or [0]}],
            },
        ]

        top_rows = project_model.search_read(
            domain + [("review_status", "in", ("draft", "pending_review", "change_requested"))],
            ["id", "code", "name", "client_name", "sales_rep", "review_status", "score_overall", "contract_value", "deadline_date"],
            limit=10,
            order="deadline_date asc, id desc",
        )
        upcoming_rows = project_model.search_read(
            domain + [("deadline_date", "!=", False)],
            ["id", "code", "name", "deadline_date", "project_lead_id", "decision_final", "review_status"],
            limit=10,
            order="deadline_date asc",
        )
        project_ids = project_model.search(domain).ids
        submission_domain = (
            [("project_id", "in", project_ids)] if project_ids else [("id", "=", False)]
        )
        change_domain = (
            [("resolved", "=", False), ("project_id", "in", project_ids)]
            if project_ids
            else [("id", "=", False)]
        )
        recent_submissions = submission_model.search_read(
            submission_domain,
            ["id", "name", "project_id", "owner_id", "status", "submitted_date"],
            limit=10,
            order="submitted_date desc, id desc",
        )
        open_change_requests = change_model.search_read(
            change_domain,
            ["id", "project_id", "reviewer_id", "priority", "comments", "create_date"],
            limit=10,
            order="create_date desc, id desc",
        )

        submission_status_sel = dict(submission_model._fields["status"].selection)
        tables = [
            {
                "title": "Top Open Bids",
                "res_model": "bid.project",
                "columns": ["Code", "Project", "Client", "Sales Rep", "Review Status", "Score %", "Value (AED)", "Deadline"],
                "rows": [
                    {
                        "id": row["id"],
                        "data": [
                            row.get("code") or "",
                            row.get("name") or "",
                            row.get("client_name") or "",
                            (row.get("sales_rep") and row["sales_rep"][1]) or "",
                            review_sel.get(row.get("review_status"), row.get("review_status") or ""),
                            round(row.get("score_overall") or 0.0, 2),
                            round(row.get("contract_value") or 0.0, 2),
                            row.get("deadline_date") or "",
                        ],
                    }
                    for row in top_rows
                ],
            },
            {
                "title": "Upcoming Deadlines",
                "res_model": "bid.project",
                "columns": ["Code", "Project", "Deadline", "Project Lead", "Decision", "Review Status"],
                "rows": [
                    {
                        "id": row["id"],
                        "data": [
                            row.get("code") or "",
                            row.get("name") or "",
                            row.get("deadline_date") or "",
                            (row.get("project_lead_id") and row["project_lead_id"][1]) or "",
                            decision_sel.get(row.get("decision_final"), row.get("decision_final") or ""),
                            review_sel.get(row.get("review_status"), row.get("review_status") or ""),
                        ],
                    }
                    for row in upcoming_rows
                ],
            },
            {
                "title": "Recent Submissions",
                "res_model": "bid.submission",
                "columns": ["Name", "Project", "Owner", "Status", "Submitted Date"],
                "rows": [
                    {
                        "id": row["id"],
                        "data": [
                            row.get("name") or "",
                            (row.get("project_id") and row["project_id"][1]) or "",
                            (row.get("owner_id") and row["owner_id"][1]) or "",
                            submission_status_sel.get(row.get("status"), row.get("status") or ""),
                            row.get("submitted_date") or "",
                        ],
                    }
                    for row in recent_submissions
                ],
            },
            {
                "title": "Open Change Requests",
                "res_model": "bid.change.request",
                "columns": ["Project", "Reviewer", "Priority", "Comments", "Created On"],
                "rows": [
                    {
                        "id": row["id"],
                        "data": [
                            (row.get("project_id") and row["project_id"][1]) or "",
                            (row.get("reviewer_id") and row["reviewer_id"][1]) or "",
                            row.get("priority") or "",
                            row.get("comments") or "",
                            row.get("create_date") or "",
                        ],
                    }
                    for row in open_change_requests
                ],
            },
        ]

        return {"kpis": kpis, "charts": charts, "tables": tables, "filter_options": self._get_filter_options()}

    @api.model
    def _project_action(self, extra_domain, filter_params=None):
        clean = self._sanitize_filter_params(filter_params or {})
        base_domain = self._build_project_domain(clean)
        return {
            "type": "ir.actions.act_window",
            "name": "Projects",
            "res_model": "bid.project",
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "domain": base_domain + (extra_domain or []),
        }

    @api.model
    def action_view_projects_all(self, filter_params=None):
        return self._project_action([], filter_params=filter_params)

    @api.model
    def action_view_projects_pending_review(self, filter_params=None):
        return self._project_action([("review_status", "=", "pending_review")], filter_params=filter_params)

    @api.model
    def action_view_projects_approved(self, filter_params=None):
        return self._project_action([("review_status", "=", "approved")], filter_params=filter_params)

    @api.model
    def action_view_projects_change_requested(self, filter_params=None):
        return self._project_action([("review_status", "=", "change_requested")], filter_params=filter_params)

    @api.model
    def action_view_projects_bid(self, filter_params=None):
        return self._project_action([("decision_final", "=", "bid")], filter_params=filter_params)

    @api.model
    def action_view_projects_no_bid(self, filter_params=None):
        return self._project_action([("decision_final", "=", "no_bid")], filter_params=filter_params)

    @api.model
    def action_view_projects_value(self, filter_params=None):
        return self._project_action([("contract_value", ">", 0)], filter_params=filter_params)

    @api.model
    def action_view_projects_scored(self, filter_params=None):
        return self._project_action([("score_overall", ">", 0)], filter_params=filter_params)

    @api.model
    def get_report_data(self, filter_params=None):
        dashboard_data = self.get_dashboard_data(dashboard_id=None, context=None, filter_params=dict(filter_params or {}))
        return {
            "kpis": dashboard_data.get("kpis", []),
            "charts": dashboard_data.get("charts", []),
            "tables": dashboard_data.get("tables", []),
        }

    @api.model
    def action_print_dashboard_report(self, filter_params=None):
        dashboard = self.search([], limit=1)
        if not dashboard:
            dashboard = self.create({"name": "Sales Bid Board Dashboard"})
        return self.env.ref("sales_bid_board.action_report_sales_bid_board_dashboard").with_context(
            filter_params=dict(filter_params or {})
        ).report_action(dashboard)
