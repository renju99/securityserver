from odoo import api, fields, models


class SalesBidBoardSalespersonDashboard(models.Model):
    _name = "sales_bid_board.salesperson.dashboard"
    _description = "Salesperson Analytics Dashboard"

    name = fields.Char(default="Salesperson Analytics", required=True)

    @api.model
    def _metric_value(self, row, base, agg):
        """Match Odoo read_group keys across versions (e.g. Odoo 18 uses base name, not base_agg)."""
        if not row:
            return 0.0
        for key in (f"{base}_{agg}", f"{base}:{agg}", base):
            if key in row and row[key] not in (None, False):
                return row[key]
        return 0.0

    @api.model
    def _sanitize(self, filter_params):
        filter_params = self.env["sales_bid_board.unified.analytics"].analytics_clamp_filter_params_for_salesperson(
            filter_params or {}
        )
        clean = {}
        for key in ("date_from", "date_to", "industry", "emirate", "outcome_status"):
            if filter_params.get(key):
                clean[key] = filter_params[key]
        raw_rep = filter_params.get("sales_rep_id")
        if raw_rep not in (None, "", False):
            try:
                clean["sales_rep_id"] = int(raw_rep)
            except (TypeError, ValueError):
                pass
        return clean

    @api.model
    def _domain(self, clean):
        domain = []
        if clean.get("date_from"):
            domain.append(("create_date", ">=", clean["date_from"]))
        if clean.get("date_to"):
            domain.append(("create_date", "<=", clean["date_to"]))
        if clean.get("industry"):
            domain.append(("industry", "=", clean["industry"]))
        if clean.get("emirate"):
            domain.append(("emirate", "=", clean["emirate"]))
        if clean.get("outcome_status"):
            domain.append(("outcome_status", "=", clean["outcome_status"]))
        if clean.get("sales_rep_id"):
            domain.append(("sales_rep", "=", clean["sales_rep_id"]))
        domain += self.env["sales_bid_board.unified.analytics"].analytics_extra_domain_bid_project()
        return domain

    @api.model
    def _act_window_list(self, name, res_model, domain):
        return {
            "type": "ir.actions.act_window",
            "name": name,
            "res_model": res_model,
            "view_mode": "list,form",
            "views": [[False, "list"], [False, "form"]],
            "target": "current",
            "domain": domain,
        }

    @api.model
    def action_kpi_rep_active_reps(self, filter_params=None):
        """Users who are sales rep on at least one project in the current filters."""
        clean = self._sanitize(filter_params or {})
        project = self.env["bid.project"]
        domain = self._domain(clean)
        rep_groups = project.read_group(domain, ["id:count"], ["sales_rep"], lazy=False)
        user_ids = [r["sales_rep"][0] for r in rep_groups if r.get("sales_rep")]
        if not user_ids:
            udom = [("id", "=", False)]
        else:
            udom = [("id", "in", user_ids)]
        return self._act_window_list("Active sales reps", "res.users", udom)

    @api.model
    def action_kpi_rep_total_projects(self, filter_params=None):
        clean = self._sanitize(filter_params or {})
        return self._act_window_list("Projects", "bid.project", self._domain(clean))

    @api.model
    def action_kpi_rep_pipeline_value(self, filter_params=None):
        clean = self._sanitize(filter_params or {})
        return self._act_window_list(
            "Projects with contract value",
            "bid.project",
            self._domain(clean) + [("contract_value", ">", 0)],
        )

    @api.model
    def action_kpi_rep_avg_score(self, filter_params=None):
        clean = self._sanitize(filter_params or {})
        return self._act_window_list(
            "Scored projects",
            "bid.project",
            self._domain(clean) + [("score_overall", ">", 0)],
        )

    @api.model
    def get_dashboard_data(self, dashboard_id=None, context=None, filter_params=None):
        clean = self._sanitize(filter_params)
        project = self.env["bid.project"]
        domain = self._domain(clean)

        reps = project.read_group(
            domain,
            ["id:count", "contract_value:sum", "score_overall:avg", "sales_rep"],
            ["sales_rep"],
            lazy=False,
        )
        rows = [r for r in reps if r.get("sales_rep")]

        top_by_count = sorted(rows, key=lambda r: r.get("__count", 0), reverse=True)[:10]
        top_by_value = sorted(
            rows, key=lambda r: self._metric_value(r, "contract_value", "sum"), reverse=True
        )[:10]
        top_by_score = sorted(
            rows, key=lambda r: self._metric_value(r, "score_overall", "avg"), reverse=True
        )[:10]

        total_projects = project.search_count(domain)
        agg_row = project.read_group(domain, ["contract_value:sum", "score_overall:avg"], [])
        agg_row = agg_row[0] if agg_row else {}
        total_value = self._metric_value(agg_row, "contract_value", "sum")
        avg_score = self._metric_value(agg_row, "score_overall", "avg")
        active_reps = len(rows)

        rep_chart_meta = {
            "action_model": "bid.project",
            "action_domain_field": "sales_rep",
            "action_type": "many2one",
        }
        charts = [
            {
                "type": "bar",
                "title": "Top Sales Reps by Project Count",
                "labels": [r["sales_rep"][1] for r in top_by_count] or ["No Data"],
                "keys": [r["sales_rep"][0] for r in top_by_count] or [0],
                "datasets": [{"label": "Projects", "data": [r.get("__count", 0) for r in top_by_count] or [0]}],
                **rep_chart_meta,
            },
            {
                "type": "bar",
                "title": "Top Sales Reps by Contract Value (AED)",
                "labels": [r["sales_rep"][1] for r in top_by_value] or ["No Data"],
                "keys": [r["sales_rep"][0] for r in top_by_value] or [0],
                "datasets": [
                    {
                        "label": "Value",
                        "data": [round(self._metric_value(r, "contract_value", "sum"), 2) for r in top_by_value]
                        or [0],
                    }
                ],
                **rep_chart_meta,
            },
            {
                "type": "bar",
                "title": "Top Sales Reps by Average Score",
                "labels": [r["sales_rep"][1] for r in top_by_score] or ["No Data"],
                "keys": [r["sales_rep"][0] for r in top_by_score] or [0],
                "datasets": [
                    {
                        "label": "Score %",
                        "data": [round(self._metric_value(r, "score_overall", "avg"), 2) for r in top_by_score]
                        or [0],
                    }
                ],
                **rep_chart_meta,
            },
        ]

        table_rows = []
        for r in sorted(rows, key=lambda x: x.get("__count", 0), reverse=True):
            rep_id = r["sales_rep"][0]
            rep_domain = domain + [("sales_rep", "=", rep_id)]
            bid_count = project.search_count(rep_domain + [("decision_final", "=", "bid")])
            no_bid_count = project.search_count(rep_domain + [("decision_final", "=", "no_bid")])
            approved_count = project.search_count(rep_domain + [("review_status", "=", "approved")])
            pending_count = project.search_count(rep_domain + [("review_status", "=", "pending_review")])
            total_count = r.get("__count", 0) or 0
            bid_rate = (bid_count / total_count * 100.0) if total_count else 0.0
            table_rows.append(
                {
                    "id": rep_id,
                    "data": [
                        r["sales_rep"][1],
                        total_count,
                        bid_count,
                        no_bid_count,
                        approved_count,
                        pending_count,
                        round(bid_rate, 2),
                        round(self._metric_value(r, "contract_value", "sum"), 2),
                        round(self._metric_value(r, "score_overall", "avg"), 2),
                    ],
                }
            )

        return {
            "kpis": [
                {
                    "name": "Active Sales Reps",
                    "value": active_reps,
                    "icon": "fa-users",
                    "action": "action_kpi_rep_active_reps",
                    "rpc_model": "sales_bid_board.salesperson.dashboard",
                },
                {
                    "name": "Total Projects",
                    "value": total_projects,
                    "icon": "fa-folder-open",
                    "action": "action_kpi_rep_total_projects",
                    "rpc_model": "sales_bid_board.salesperson.dashboard",
                },
                {
                    "name": "Total Pipeline Value",
                    "value": round(total_value, 2),
                    "suffix": " AED",
                    "icon": "fa-money",
                    "action": "action_kpi_rep_pipeline_value",
                    "rpc_model": "sales_bid_board.salesperson.dashboard",
                },
                {
                    "name": "Team Avg Score",
                    "value": round(avg_score, 2),
                    "suffix": "%",
                    "icon": "fa-line-chart",
                    "action": "action_kpi_rep_avg_score",
                    "rpc_model": "sales_bid_board.salesperson.dashboard",
                },
            ],
            "charts": charts,
            "tables": [
                {
                    "title": "Sales Rep Performance Breakdown",
                    "columns": ["Sales Rep", "Projects", "Bid", "No Bid", "Approved", "Pending", "Bid Rate %", "Value (AED)", "Avg Score %"],
                    "rows": table_rows,
                    "list_drill": {"model": "bid.project", "field": "sales_rep"},
                }
            ],
            "filter_options": {
                "industries": [{"value": k, "label": v} for k, v in dict(project._fields["industry"].selection).items()],
                "emirates": [{"value": k, "label": v} for k, v in dict(project._fields["emirate"].selection).items()],
                "outcome_statuses": [
                    {"value": k, "label": v} for k, v in dict(project._fields["outcome_status"].selection).items()
                ],
                "sales_reps": [
                    {"value": user.id, "label": user.name}
                    for user in self.env["res.users"].browse(
                        [
                            g["sales_rep"][0]
                            for g in project.read_group(
                                self.env["sales_bid_board.unified.analytics"].analytics_extra_domain_bid_project(),
                                ["sales_rep"],
                                ["sales_rep"],
                            )
                            if g.get("sales_rep")
                        ]
                    )
                ],
            },
        }
