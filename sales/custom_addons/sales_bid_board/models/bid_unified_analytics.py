from collections import Counter, defaultdict
from datetime import date as date_cls
from datetime import timedelta

from odoo import api, fields, models


class SalesBidBoardUnifiedAnalytics(models.TransientModel):
    _name = "sales_bid_board.unified.analytics"
    _description = "Bid Board unified analytics (tabbed)"

    name = fields.Char(default="Analytics", required=True)

    @api.model
    def analytics_is_sales_manager_or_above(self):
        """Bid Board / Sales Manager (or any implied higher role) sees org-wide analytics."""
        return self.env.user.has_group("sales_bid_board.group_bid_board_sales_manager")

    @api.model
    def analytics_clamp_filter_params_for_salesperson(self, filter_params):
        """Salesperson-only users cannot scope analytics to another rep (RPC / UI tampering)."""
        fp = dict(filter_params or {})
        if self.analytics_is_sales_manager_or_above():
            return fp
        uid = self.env.uid
        srid = fp.get("sales_rep_id")
        if srid not in (None, "", False):
            try:
                if int(srid) != uid:
                    fp["sales_rep_id"] = uid
            except (TypeError, ValueError):
                fp.pop("sales_rep_id", None)
        return fp

    @api.model
    def analytics_extra_domain_bid_project(self):
        """AND with bid.project queries; matches ir.rule salesperson scope."""
        if self.analytics_is_sales_manager_or_above():
            return []
        u = self.env.uid
        return ["|", ("create_uid", "=", u), ("sales_rep", "=", u)]

    @api.model
    def analytics_extra_domain_project_m2o(self, field="project_id"):
        """AND on models linked to bid.project; matches bid_* ir.rule salesperson scope."""
        if self.analytics_is_sales_manager_or_above():
            return []
        u = self.env.uid
        return ["|", (f"{field}.create_uid", "=", u), (f"{field}.sales_rep", "=", u)]

    @api.model
    def analytics_extra_domain_crm_lead(self):
        """AND on crm.lead analytics — overrides OR of conflicting CRM group rules."""
        if self.analytics_is_sales_manager_or_above():
            return []
        u = self.env.uid
        return ["|", ("user_id", "=", u), ("create_uid", "=", u)]

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
    def _metric_value(self, row, base, agg):
        if not row:
            return 0.0
        for key in (f"{base}_{agg}", f"{base}:{agg}", base):
            if key in row and row[key] not in (None, False):
                return row[key]
        return 0.0

    @api.model
    def _datetime_start(self, date_str):
        if not date_str:
            return False
        d = fields.Date.to_date(fields.Date.from_string(date_str))
        return fields.Datetime.to_datetime(d)

    @api.model
    def _datetime_end(self, date_str):
        if not date_str:
            return False
        d = fields.Date.to_date(fields.Date.from_string(date_str))
        return fields.Datetime.to_datetime(d) + timedelta(hours=23, minutes=59, seconds=59)

    @api.model
    def _domain_create_date(self, filter_params, field="create_date"):
        domain = []
        df = filter_params.get("date_from")
        dt = filter_params.get("date_to")
        if df:
            domain.append((field, ">=", self._datetime_start(df)))
        if dt:
            domain.append((field, "<=", self._datetime_end(dt)))
        return domain

    @api.model
    def _month_domain_from_bucket(self, bucket_value, ranged_field="create_date"):
        """Exact month range for read_group create_date:month buckets (chart drill-down)."""
        if bucket_value in (None, False):
            return []
        try:
            if isinstance(bucket_value, date_cls):
                first = bucket_value.replace(day=1)
            else:
                ds = str(bucket_value).strip().split()[0][:10]
                parsed = fields.Date.to_date(fields.Date.from_string(ds))
                first = parsed.replace(day=1)
        except (ValueError, TypeError, AttributeError):
            return []
        if first.month == 12:
            next_first = first.replace(year=first.year + 1, month=1, day=1)
        else:
            next_first = first.replace(month=first.month + 1, day=1)
        start_dt = fields.Datetime.to_datetime(first)
        end_dt = fields.Datetime.to_datetime(next_first)
        return [(ranged_field, ">=", start_dt), (ranged_field, "<", end_dt)]

    @api.model
    def _crm_lead_leads_domain(self, filter_params):
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        domain = (
            [("type", "=", "lead")]
            + self._domain_create_date(fp)
            + self.analytics_extra_domain_crm_lead()
        )
        if fp.get("sales_rep_id"):
            try:
                domain.append(("user_id", "=", int(fp["sales_rep_id"])))
            except (TypeError, ValueError):
                pass
        if fp.get("team_id"):
            try:
                domain.append(("team_id", "=", int(fp["team_id"])))
            except (TypeError, ValueError):
                pass
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
    def action_kpi_leads_total(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list("Leads", "crm.lead", self._crm_lead_leads_domain(fp))

    @api.model
    def action_kpi_leads_unassigned(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Unassigned leads", "crm.lead", self._crm_lead_leads_domain(fp) + [("user_id", "=", False)]
        )

    @api.model
    def action_kpi_leads_linked_enquiry(self, filter_params=None):
        fp = dict(filter_params or {})
        domain = self._crm_lead_leads_domain(fp)
        project_domain = [("crm_lead_id", "!=", False)] + self.analytics_extra_domain_bid_project()
        linked_ids = self.env["bid.project"].search(project_domain).mapped("crm_lead_id").ids
        linked_ids = list(set(linked_ids))
        if not linked_ids:
            domain.append(("id", "=", False))
        else:
            domain.append(("id", "in", linked_ids))
        return self._act_window_list("Leads linked to enquiry", "crm.lead", domain)

    @api.model
    def action_kpi_proposals_total(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list("Proposals", "bid.proposal", self._proposal_domain(fp))

    @api.model
    def action_kpi_proposals_open(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Pipeline proposals",
            "bid.proposal",
            self._proposal_domain(fp)
            + [("outcome_status", "in", ("open", "submitted", "revision"))],
        )

    @api.model
    def action_kpi_proposals_won(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Won proposals", "bid.proposal", self._proposal_domain(fp) + [("outcome_status", "=", "won")]
        )

    @api.model
    def action_kpi_proposals_lost(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Lost proposals", "bid.proposal", self._proposal_domain(fp) + [("outcome_status", "=", "lost")]
        )

    @api.model
    def action_kpi_proposals_pipeline_value(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Proposals with volume",
            "bid.proposal",
            self._proposal_domain(fp) + [("contract_volume_total", ">", 0)],
        )

    @api.model
    def action_kpi_activity_submissions(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list("Submissions", "bid.submission", self._submission_domain(fp))

    @api.model
    def action_kpi_activity_open_changes(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list(
            "Open change requests",
            "bid.change.request",
            self._change_domain(fp) + [("resolved", "=", False)],
        )

    @api.model
    def action_kpi_activity_changes_period(self, filter_params=None):
        fp = dict(filter_params or {})
        return self._act_window_list("Change requests", "bid.change.request", self._change_domain(fp))

    @api.model
    def _proposal_domain(self, filter_params):
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        domain = list(self._domain_create_date(fp)) + self.analytics_extra_domain_project_m2o("project_id")
        if fp.get("industry"):
            domain.append(("project_id.industry", "=", fp["industry"]))
        if fp.get("emirate"):
            domain.append(("project_id.emirate", "=", fp["emirate"]))
        if fp.get("sales_rep_id"):
            try:
                domain.append(("sales_user_id", "=", int(fp["sales_rep_id"])))
            except (TypeError, ValueError):
                pass
        return domain

    @api.model
    def _submission_domain(self, filter_params):
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        domain = list(self.analytics_extra_domain_project_m2o("project_id"))
        if fp.get("date_from"):
            domain.append(("submitted_date", ">=", fp["date_from"]))
        if fp.get("date_to"):
            domain.append(("submitted_date", "<=", fp["date_to"]))
        return domain

    @api.model
    def _change_domain(self, filter_params):
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        return list(self._domain_create_date(fp)) + self.analytics_extra_domain_project_m2o("project_id")

    @api.model
    def _tab_leads(self, filter_params):
        Lead = self.env["crm.lead"]
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        domain = self._crm_lead_leads_domain(fp)

        total = Lead.search_count(domain)
        unassigned = Lead.search_count(domain + [("user_id", "=", False)])

        project_with_lead = self.env["bid.project"].search(
            [("crm_lead_id", "!=", False)] + self.analytics_extra_domain_bid_project()
        )
        linked_ids = project_with_lead.mapped("crm_lead_id").ids
        with_enquiry = Lead.search_count(domain + [("id", "in", linked_ids)])

        stage_groups = Lead.read_group(domain, ["id:count"], ["stage_id"], lazy=False)
        stage_labels, stage_keys, stage_values = [], [], []
        for row in stage_groups:
            st = row.get("stage_id")
            if st:
                stage_keys.append(st[0])
                stage_labels.append(st[1])
                stage_values.append(self._count_value(row))

        trend_groups = Lead.read_group(domain, ["id:count"], ["create_date:month"], lazy=False)
        trend_labels, trend_keys, trend_values, trend_period_domains = [], [], [], []
        for row in trend_groups:
            label = row.get("create_date:month")
            if label:
                ls = str(label)
                trend_labels.append(ls)
                trend_keys.append(ls)
                trend_values.append(self._count_value(row))
                trend_period_domains.append(self._month_domain_from_bucket(label, "create_date"))

        team_groups = Lead.read_group(domain, ["id:count"], ["team_id"], lazy=False)
        team_labels, team_keys, team_values = [], [], []
        for row in team_groups:
            tm = row.get("team_id")
            if tm:
                team_keys.append(tm[0])
                team_labels.append(tm[1])
                team_values.append(self._count_value(row))

        recent = Lead.search_read(
            domain,
            ["name", "partner_name", "contact_name", "user_id", "team_id", "create_date", "bid_intake_status"],
            limit=12,
            order="create_date desc, id desc",
        )
        table_rows = []
        for row in recent:
            table_rows.append(
                {
                    "id": row["id"],
                    "data": [
                        row.get("name") or "",
                        row.get("partner_name") or "",
                        row.get("contact_name") or "",
                        (row.get("user_id") and row["user_id"][1]) or "",
                        (row.get("team_id") and row["team_id"][1]) or "",
                        str(row.get("create_date") or ""),
                        row.get("bid_intake_status") or "",
                    ],
                }
            )

        teams = self.env["crm.team"].search([], order="name")
        return {
            "kpis": [
                {
                    "name": "Total leads",
                    "value": total,
                    "icon": "fa-user-plus",
                    "action": "action_kpi_leads_total",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Unassigned",
                    "value": unassigned,
                    "icon": "fa-user-times",
                    "action": "action_kpi_leads_unassigned",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Linked to enquiry",
                    "value": with_enquiry,
                    "icon": "fa-link",
                    "action": "action_kpi_leads_linked_enquiry",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
            ],
            "charts": [
                {
                    "type": "doughnut",
                    "title": "Leads by stage",
                    "labels": stage_labels or ["No data"],
                    "keys": stage_keys or [""],
                    "action_model": "crm.lead",
                    "action_domain_field": "stage_id",
                    "action_type": "many2one",
                    "extra_domain": [("type", "=", "lead")],
                    "datasets": [{"label": "Leads", "data": stage_values or [0]}],
                },
                {
                    "type": "bar",
                    "title": "Leads by sales team",
                    "labels": team_labels or ["No data"],
                    "keys": team_keys or [""],
                    "action_model": "crm.lead",
                    "action_domain_field": "team_id",
                    "action_type": "many2one",
                    "extra_domain": [("type", "=", "lead")],
                    "datasets": [{"label": "Leads", "data": team_values or [0]}],
                },
                {
                    "type": "line",
                    "title": "New leads trend",
                    "labels": trend_labels or ["No data"],
                    "keys": trend_keys or [""],
                    "action_model": "crm.lead",
                    "action_domain_field": "create_date",
                    "action_type": "date_period",
                    "extra_domain": [("type", "=", "lead")],
                    "period_domains": trend_period_domains,
                    "datasets": [{"label": "Leads", "data": trend_values or [0]}],
                },
            ],
            "tables": [
                {
                    "title": "Recent leads",
                    "res_model": "crm.lead",
                    "columns": ["Name", "Customer", "Contact", "Salesperson", "Team", "Created", "Intake status"],
                    "rows": table_rows,
                }
            ],
            "filter_options": {
                "teams": [{"value": t.id, "label": t.name} for t in teams],
            },
        }

    @api.model
    def _tab_proposals(self, filter_params):
        Proposal = self.env["bid.proposal"]
        domain = self._proposal_domain(filter_params)

        total = Proposal.search_count(domain)
        pipeline_c = Proposal.search_count(
            domain + [("outcome_status", "in", ("open", "submitted", "revision"))]
        )
        won_c = Proposal.search_count(domain + [("outcome_status", "=", "won")])
        lost_c = Proposal.search_count(domain + [("outcome_status", "=", "lost")])

        vol_row = Proposal.read_group(domain, ["contract_volume_total:sum"], [])
        vol_row = vol_row[0] if vol_row else {}
        pipeline_value = self._metric_value(vol_row, "contract_volume_total", "sum")

        outcome_groups = Proposal.read_group(domain, ["id:count"], ["outcome_status"], lazy=False)
        out_sel = dict(Proposal._fields["outcome_status"].selection)
        ol, ok, ov = [], [], []
        for row in outcome_groups:
            key = row.get("outcome_status")
            if key:
                ok.append(key)
                ol.append(out_sel.get(key, key))
                ov.append(self._count_value(row))

        ind_groups = Proposal.read_group(domain, ["id:count"], ["industry"], lazy=False)
        ind_sel = dict(Proposal._fields["industry"].selection)
        il, ik, iv = [], [], []
        for row in ind_groups:
            key = row.get("industry")
            if key:
                ik.append(key)
                il.append(ind_sel.get(key, key))
                iv.append(self._count_value(row))

        trend_groups = Proposal.read_group(domain, ["id:count"], ["create_date:month"], lazy=False)
        tl, tk, tv, trend_period_domains = [], [], [], []
        for row in trend_groups:
            label = row.get("create_date:month")
            if label:
                ls = str(label)
                tl.append(ls)
                tk.append(ls)
                tv.append(self._count_value(row))
                trend_period_domains.append(self._month_domain_from_bucket(label, "create_date"))

        recent = Proposal.search_read(
            domain,
            [
                "reference",
                "name",
                "project_id",
                "sales_user_id",
                "outcome_status",
                "contract_volume_total",
                "create_date",
            ],
            limit=12,
            order="create_date desc, id desc",
        )
        rows = []
        for row in recent:
            rows.append(
                {
                    "id": row["id"],
                    "data": [
                        row.get("reference") or "",
                        row.get("name") or "",
                        (row.get("project_id") and row["project_id"][1]) or "",
                        (row.get("sales_user_id") and row["sales_user_id"][1]) or "",
                        out_sel.get(row.get("outcome_status"), row.get("outcome_status") or ""),
                        round(row.get("contract_volume_total") or 0.0, 2),
                        str(row.get("create_date") or ""),
                    ],
                }
            )

        return {
            "kpis": [
                {
                    "name": "Proposals",
                    "value": total,
                    "icon": "fa-file-text",
                    "action": "action_kpi_proposals_total",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Pipeline",
                    "value": pipeline_c,
                    "icon": "fa-folder-open",
                    "action": "action_kpi_proposals_open",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Won",
                    "value": won_c,
                    "icon": "fa-trophy",
                    "color": "success",
                    "action": "action_kpi_proposals_won",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Lost",
                    "value": lost_c,
                    "icon": "fa-times-circle",
                    "action": "action_kpi_proposals_lost",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Pipeline value",
                    "value": round(pipeline_value, 2),
                    "suffix": " AED",
                    "icon": "fa-money",
                    "action": "action_kpi_proposals_pipeline_value",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
            ],
            "charts": [
                {
                    "type": "doughnut",
                    "title": "By outcome",
                    "labels": ol or ["No data"],
                    "keys": ok or [""],
                    "action_model": "bid.proposal",
                    "action_domain_field": "outcome_status",
                    "action_type": "selection",
                    "datasets": [{"label": "Proposals", "data": ov or [0]}],
                },
                {
                    "type": "bar",
                    "title": "By industry",
                    "labels": il or ["No data"],
                    "keys": ik or [""],
                    "action_model": "bid.proposal",
                    "action_domain_field": "industry",
                    "action_type": "selection",
                    "datasets": [{"label": "Count", "data": iv or [0]}],
                },
                {
                    "type": "line",
                    "title": "Created trend",
                    "labels": tl or ["No data"],
                    "keys": tk or [""],
                    "action_model": "bid.proposal",
                    "action_domain_field": "create_date",
                    "action_type": "date_period",
                    "period_domains": trend_period_domains,
                    "datasets": [{"label": "Proposals", "data": tv or [0]}],
                },
            ],
            "tables": [
                {
                    "title": "Recent proposals",
                    "res_model": "bid.proposal",
                    "columns": ["Ref", "Title", "Enquiry", "Sales", "Outcome", "Volume", "Created"],
                    "rows": rows,
                }
            ],
            "filter_options": {
                "industries": [
                    {"value": k, "label": v}
                    for k, v in dict(self.env["bid.project"]._fields["industry"].selection).items()
                ],
                "emirates": [
                    {"value": k, "label": v}
                    for k, v in dict(self.env["bid.project"]._fields["emirate"].selection).items()
                ],
            },
        }

    @api.model
    def _tab_activity(self, filter_params):
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        Sub = self.env["bid.submission"]
        Chg = self.env["bid.change.request"]
        Notif = self.env["bid.notification"]

        sub_dom = self._submission_domain(fp)

        chg_dom = self._change_domain(fp)

        notif_dom = list(self._domain_create_date(fp)) + self.analytics_extra_domain_project_m2o("project_id")

        sub_total = Sub.search_count(sub_dom)
        status_groups = Sub.read_group(sub_dom, ["id:count"], ["status"], lazy=False)
        st_sel = dict(Sub._fields["status"].selection)
        sl, sk, sv = [], [], []
        for row in status_groups:
            key = row.get("status")
            if key:
                sk.append(key)
                sl.append(st_sel.get(key, key))
                sv.append(self._count_value(row))

        open_chg = Chg.search_count(chg_dom + [("resolved", "=", False)])
        chg_total = Chg.search_count(chg_dom)

        notif_groups = Notif.read_group(notif_dom, ["id:count"], ["state"], lazy=False)
        nst_sel = dict(Notif._fields["state"].selection)
        nl, nk, nv = [], [], []
        for row in notif_groups:
            key = row.get("state")
            if key:
                nk.append(key)
                nl.append(nst_sel.get(key, key))
                nv.append(self._count_value(row))

        recent_sub = Sub.search_read(
            sub_dom,
            ["name", "project_id", "owner_id", "status", "submitted_date"],
            limit=10,
            order="submitted_date desc, id desc",
        )
        sub_rows = []
        for row in recent_sub:
            sub_rows.append(
                {
                    "id": row["id"],
                    "data": [
                        row.get("name") or "",
                        (row.get("project_id") and row["project_id"][1]) or "",
                        (row.get("owner_id") and row["owner_id"][1]) or "",
                        st_sel.get(row.get("status"), row.get("status") or ""),
                        row.get("submitted_date") or "",
                    ],
                }
            )

        open_chg_rows_raw = Chg.search_read(
            chg_dom + [("resolved", "=", False)],
            ["project_id", "reviewer_id", "priority", "comments", "create_date"],
            limit=10,
            order="create_date desc",
        )
        chg_rows = []
        for row in open_chg_rows_raw:
            chg_rows.append(
                {
                    "id": row["id"],
                    "data": [
                        (row.get("project_id") and row["project_id"][1]) or "",
                        (row.get("reviewer_id") and row["reviewer_id"][1]) or "",
                        row.get("priority") or "",
                        (row.get("comments") or "")[:80],
                        str(row.get("create_date") or ""),
                    ],
                }
            )

        recent_notif = Notif.search_read(
            notif_dom,
            ["project_id", "state", "deadline_date", "create_date"],
            limit=10,
            order="create_date desc, id desc",
        )
        not_rows = []
        for row in recent_notif:
            not_rows.append(
                {
                    "id": row["id"],
                    "data": [
                        (row.get("project_id") and row["project_id"][1]) or "",
                        nst_sel.get(row.get("state"), row.get("state") or ""),
                        row.get("deadline_date") or "",
                        str(row.get("create_date") or ""),
                    ],
                }
            )

        return {
            "kpis": [
                {
                    "name": "Submissions",
                    "value": sub_total,
                    "icon": "fa-paper-plane",
                    "action": "action_kpi_activity_submissions",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Open change requests",
                    "value": open_chg,
                    "icon": "fa-exchange",
                    "action": "action_kpi_activity_open_changes",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
                {
                    "name": "Change requests (period)",
                    "value": chg_total,
                    "icon": "fa-list",
                    "action": "action_kpi_activity_changes_period",
                    "rpc_model": "sales_bid_board.unified.analytics",
                },
            ],
            "charts": [
                {
                    "type": "bar",
                    "title": "Submissions by status",
                    "labels": sl or ["No data"],
                    "keys": sk or [""],
                    "action_model": "bid.submission",
                    "action_domain_field": "status",
                    "action_type": "selection",
                    "datasets": [{"label": "Count", "data": sv or [0]}],
                },
                {
                    "type": "doughnut",
                    "title": "Reminder notifications by state",
                    "labels": nl or ["No data"],
                    "keys": nk or [""],
                    "action_model": "bid.notification",
                    "action_domain_field": "state",
                    "action_type": "selection",
                    "datasets": [{"label": "Count", "data": nv or [0]}],
                },
            ],
            "tables": [
                {
                    "title": "Recent submissions",
                    "res_model": "bid.submission",
                    "columns": ["Name", "Project", "Owner", "Status", "Submitted"],
                    "rows": sub_rows,
                },
                {
                    "title": "Open change requests",
                    "res_model": "bid.change.request",
                    "columns": ["Project", "Reviewer", "Priority", "Comments", "Created"],
                    "rows": chg_rows,
                },
                {
                    "title": "Recent deadline reminders",
                    "res_model": "bid.notification",
                    "columns": ["Project", "State", "Deadline", "Created"],
                    "rows": not_rows,
                },
            ],
            "filter_options": {},
        }

    @api.model
    def _pdf_chart_bar(self, title, labels, keys, values, dataset_label="Count", **chart_meta):
        """Bar chart dict compatible with the Bid Board analytics PDF QWeb renderer."""
        chart = {
            "type": "bar",
            "title": title,
            "labels": labels or ["No data"],
            "keys": keys or [""],
            "datasets": [{"label": dataset_label, "data": values or [0]}],
        }
        chart.update({k: v for k, v in chart_meta.items() if v is not None})
        return chart

    @api.model
    def _pdf_chart_doughnut(self, title, labels, keys, values, dataset_label="Count", **chart_meta):
        chart = {
            "type": "doughnut",
            "title": title,
            "labels": labels or ["No data"],
            "keys": keys or [""],
            "datasets": [{"label": dataset_label, "data": values or [0]}],
        }
        chart.update({k: v for k, v in chart_meta.items() if v is not None})
        return chart

    @api.model
    def _pdf_enrichment_proposals(self, fp):
        """Extra charts/tables for the Proposals analytics PDF (beyond the on-screen tab)."""
        Proposal = self.env["bid.proposal"]
        domain = self._proposal_domain(fp)
        out_sel = dict(Proposal._fields["outcome_status"].selection)
        ind_sel = dict(Proposal._fields["industry"].selection)
        cust_sel = dict(Proposal._fields["customer_type"].selection)
        proc_sel = dict(Proposal._fields["service_procurement_option"].selection)
        Project = self.env["bid.project"]
        em_sel = dict(Project._fields["emirate"].selection)

        total = Proposal.search_count(domain)
        won_c = Proposal.search_count(domain + [("outcome_status", "=", "won")])
        lost_c = Proposal.search_count(domain + [("outcome_status", "=", "lost")])
        pipeline_c = Proposal.search_count(
            domain + [("outcome_status", "in", ("open", "submitted", "revision"))]
        )
        decided = won_c + lost_c
        win_rate = round((won_c / decided * 100.0), 2) if decided else 0.0

        vol_all = Proposal.read_group(domain, ["contract_volume_total:sum"], [])
        vol_all = vol_all[0] if vol_all else {}
        total_vol = round(self._metric_value(vol_all, "contract_volume_total", "sum"), 2)
        avg_vol = round(total_vol / total, 2) if total else 0.0

        def _sum_volume(extra_dom):
            rows = Proposal.read_group(domain + extra_dom, ["contract_volume_total:sum"], [])
            row = rows[0] if rows else {}
            return round(self._metric_value(row, "contract_volume_total", "sum"), 2)

        won_vol = _sum_volume([("outcome_status", "=", "won")])
        lost_vol = _sum_volume([("outcome_status", "=", "lost")])
        pipe_vol = _sum_volume([("outcome_status", "in", ("open", "submitted", "revision"))])

        vol_by_out = Proposal.read_group(
            domain, ["contract_volume_total:sum", "id:count"], ["outcome_status"], lazy=False
        )
        vol_labels, vol_keys, vol_sums, vol_counts = [], [], [], []
        for row in vol_by_out:
            key = row.get("outcome_status")
            if not key:
                continue
            vol_keys.append(key)
            vol_labels.append(out_sel.get(key, key))
            vol_sums.append(round(self._metric_value(row, "contract_volume_total", "sum"), 2))
            vol_counts.append(self._count_value(row))

        rep_groups = Proposal.read_group(domain, ["id:count"], ["sales_user_id"], lazy=False)
        rep_rows = [r for r in rep_groups if r.get("sales_user_id")]
        rep_rows.sort(key=lambda r: self._count_value(r), reverse=True)
        rep_rows = rep_rows[:18]
        rl, rk, rv = [], [], []
        for row in rep_rows:
            su = row["sales_user_id"]
            rk.append(su[0])
            rl.append(su[1])
            rv.append(self._count_value(row))

        ind_vol = Proposal.read_group(
            domain, ["contract_volume_total:sum"], ["industry"], lazy=False
        )
        il, ik, iv = [], [], []
        for row in ind_vol:
            key = row.get("industry")
            if not key:
                continue
            ik.append(key)
            il.append(ind_sel.get(key, key))
            iv.append(round(self._metric_value(row, "contract_volume_total", "sum"), 2))
        pairs = sorted(zip(il, ik, iv), key=lambda x: x[2], reverse=True)
        pairs = pairs[:12]
        if pairs:
            il, ik, iv = [p[0] for p in pairs], [p[1] for p in pairs], [p[2] for p in pairs]
        else:
            il, ik, iv = [], [], []

        emirate_counter = Counter()
        proj_groups = Proposal.read_group(domain, ["id:count"], ["project_id"], lazy=False)
        proj_buckets = [r for r in proj_groups if r.get("project_id")]
        if proj_buckets:
            pids = list({r["project_id"][0] for r in proj_buckets})
            em_by_pid = {
                d["id"]: d.get("emirate")
                for d in self.env["bid.project"].browse(pids).read(["emirate"])
            }
            for row in proj_buckets:
                pid = row["project_id"][0]
                em = em_by_pid.get(pid)
                if em:
                    emirate_counter[em] += self._count_value(row)
        em_rows = sorted(
            ((em, em_sel.get(em, em), emirate_counter[em]) for em in emirate_counter if em),
            key=lambda x: x[2],
            reverse=True,
        )[:14]
        em_labels = [x[1] for x in em_rows]
        em_keys = [x[0] for x in em_rows]
        em_vals = [x[2] for x in em_rows]

        cust_groups = Proposal.read_group(domain, ["id:count"], ["customer_type"], lazy=False)
        cl, ck, cv = [], [], []
        for row in cust_groups:
            key = row.get("customer_type")
            if key:
                ck.append(key)
                cl.append(cust_sel.get(key, key))
                cv.append(self._count_value(row))

        proc_groups = Proposal.read_group(domain, ["id:count"], ["service_procurement_option"], lazy=False)
        pl, pk, pv = [], [], []
        for row in proc_groups:
            key = row.get("service_procurement_option")
            if key:
                pk.append(key)
                pl.append(proc_sel.get(key, key))
                pv.append(self._count_value(row))

        em_vol_totals = defaultdict(float)
        vol_proj_groups = Proposal.read_group(
            domain, ["contract_volume_total:sum"], ["project_id"], lazy=False
        )
        vpj = [r for r in vol_proj_groups if r.get("project_id")]
        if vpj:
            vpids = list({r["project_id"][0] for r in vpj})
            emread_vp = {d["id"]: d.get("emirate") for d in self.env["bid.project"].browse(vpids).read(["emirate"])}
            for row in vpj:
                pid = row["project_id"][0]
                em = emread_vp.get(pid)
                if em:
                    em_vol_totals[em] += self._metric_value(row, "contract_volume_total", "sum")
        emv_ord = sorted(
            ((em, em_sel.get(em, em), round(em_vol_totals[em], 2)) for em in em_vol_totals if em),
            key=lambda x: x[2],
            reverse=True,
        )[:14]
        emv_labels = [x[1] for x in emv_ord]
        emv_keys = [x[0] for x in emv_ord]
        emv_vals = [x[2] for x in emv_ord]

        charts = [
            self._pdf_chart_bar(
                "Contract volume (AED) by outcome",
                vol_labels,
                vol_keys,
                vol_sums,
                dataset_label="Volume (AED)",
                action_model="bid.proposal",
                action_domain_field="outcome_status",
                action_type="selection",
            ),
            self._pdf_chart_bar(
                "Proposal count by salesperson",
                rl,
                rk,
                rv,
                action_model="bid.proposal",
                action_domain_field="sales_user_id",
                action_type="many2one",
            ),
            self._pdf_chart_bar(
                "Contract volume (AED) by industry",
                il,
                ik,
                iv,
                dataset_label="Volume (AED)",
                action_model="bid.proposal",
                action_domain_field="industry",
                action_type="selection",
            ),
        ]
        if em_labels:
            charts.append(
                self._pdf_chart_bar(
                    "Proposals by enquiry emirate",
                    em_labels,
                    em_keys,
                    em_vals,
                    action_model="bid.proposal",
                    action_domain_field="project_id.emirate",
                    action_type="selection",
                )
            )
        if emv_labels:
            charts.append(
                self._pdf_chart_bar(
                    "Contract volume (AED) by enquiry emirate",
                    emv_labels,
                    emv_keys,
                    emv_vals,
                    dataset_label="Volume (AED)",
                    action_model="bid.proposal",
                    action_domain_field="project_id.emirate",
                    action_type="selection",
                )
            )
        if cl:
            charts.append(
                self._pdf_chart_bar(
                    "Proposals by customer type",
                    cl,
                    ck,
                    cv,
                    action_model="bid.proposal",
                    action_domain_field="customer_type",
                    action_type="selection",
                )
            )
        if pl:
            charts.append(
                self._pdf_chart_bar(
                    "Proposals by procurement model",
                    pl,
                    pk,
                    pv,
                    action_model="bid.proposal",
                    action_domain_field="service_procurement_option",
                    action_type="selection",
                )
            )

        tender_sel = dict(Proposal._fields["tender_type"].selection)
        tender_groups = Proposal.read_group(domain, ["id:count"], ["tender_type"], lazy=False)
        ttl, ttk, ttv = [], [], []
        for row in tender_groups:
            key = row.get("tender_type")
            if key:
                ttk.append(key)
                ttl.append(tender_sel.get(key, key))
                ttv.append(self._count_value(row))
        if ttl:
            charts.append(
                self._pdf_chart_bar(
                    "Proposals by tender type",
                    ttl,
                    ttk,
                    ttv,
                    action_model="bid.proposal",
                    action_domain_field="tender_type",
                    action_type="selection",
                )
            )

        dec_dom = domain + [("decision_date", "!=", False)]
        dec_trend = Proposal.read_group(dec_dom, ["id:count"], ["decision_date:month"], lazy=False)
        dtl, dtk, dtv = [], [], []
        for row in dec_trend:
            label = row.get("decision_date:month")
            if label:
                ls = str(label)
                dtl.append(ls)
                dtk.append(ls)
                dtv.append(self._count_value(row))
        if dtl:
            charts.append(
                self._pdf_chart_bar(
                    "Client decision dates by month (count)",
                    dtl,
                    dtk,
                    dtv,
                    action_model="bid.proposal",
                    action_domain_field="decision_date",
                    action_type="date_period",
                )
            )

        pipe_dom = domain + [("outcome_status", "in", ("open", "submitted", "revision"))]
        gm_row = Proposal.read_group(pipe_dom, ["gm_percent:avg", "win_probability:avg"], [])
        gm_row = gm_row[0] if gm_row else {}
        avg_gm = round(self._metric_value(gm_row, "gm_percent", "avg"), 2)
        avg_winp = round(self._metric_value(gm_row, "win_probability", "avg"), 2)
        no_deadline_pipe = Proposal.search_count(
            pipe_dom + [("deadline_date", "=", False)]
        )

        ann_rows = Proposal.read_group(domain, ["contract_volume_annual:sum"], [])
        ann_row = ann_rows[0] if ann_rows else {}
        total_ann = round(self._metric_value(ann_row, "contract_volume_annual", "sum"), 2)

        summary_rows = [
            {"id": 0, "data": ["Total proposals", str(total)]},
            {"id": 0, "data": ["Pipeline count (open / submitted / revision)", str(pipeline_c)]},
            {"id": 0, "data": ["Won count", str(won_c)]},
            {"id": 0, "data": ["Lost count", str(lost_c)]},
            {"id": 0, "data": ["Win rate (won / decided)", f"{win_rate} %"]},
            {"id": 0, "data": ["Total contract volume (AED)", str(total_vol)]},
            {"id": 0, "data": ["Average volume per proposal (AED)", str(avg_vol)]},
            {"id": 0, "data": ["Won volume (AED)", str(won_vol)]},
            {"id": 0, "data": ["Lost volume (AED)", str(lost_vol)]},
            {"id": 0, "data": ["Pipeline volume — active outcomes (AED)", str(pipe_vol)]},
            {"id": 0, "data": ["Pipeline — avg DB P% (open / submitted / revision)", str(avg_gm)]},
            {"id": 0, "data": ["Pipeline — avg win probability %", str(avg_winp)]},
            {"id": 0, "data": ["Pipeline proposals missing a deadline date", str(no_deadline_pipe)]},
            {"id": 0, "data": ["Total annualised contract volume (AED)", str(total_ann)]},
        ]

        outcome_detail = []
        for i, lab in enumerate(vol_labels):
            outcome_detail.append(
                {
                    "id": i,
                    "data": [
                        lab,
                        vol_counts[i] if i < len(vol_counts) else 0,
                        vol_sums[i] if i < len(vol_sums) else 0.0,
                    ],
                }
            )

        top_vol = Proposal.search_read(
            domain,
            [
                "reference",
                "name",
                "project_id",
                "sales_user_id",
                "outcome_status",
                "contract_volume_total",
                "customer_type",
                "industry",
            ],
            limit=22,
            order="contract_volume_total desc, id desc",
        )
        top_rows = []
        for row in top_vol:
            top_rows.append(
                {
                    "id": row["id"],
                    "data": [
                        row.get("reference") or "",
                        row.get("name") or "",
                        (row.get("project_id") and row["project_id"][1]) or "",
                        ind_sel.get(row.get("industry"), row.get("industry") or ""),
                        (row.get("sales_user_id") and row["sales_user_id"][1]) or "",
                        out_sel.get(row.get("outcome_status"), row.get("outcome_status") or ""),
                        round(row.get("contract_volume_total") or 0.0, 2),
                        cust_sel.get(row.get("customer_type"), row.get("customer_type") or ""),
                    ],
                }
            )

        vol_den = total_vol if total_vol else 1.0
        ind_fin_rows = []
        for i, row in enumerate(
            sorted(
                [
                    r
                    for r in Proposal.read_group(
                        domain, ["id:count", "contract_volume_total:sum"], ["industry"], lazy=False
                    )
                    if r.get("industry")
                ],
                key=lambda r: self._metric_value(r, "contract_volume_total", "sum"),
                reverse=True,
            )
        ):
            key = row["industry"]
            cnt = self._count_value(row)
            v = round(self._metric_value(row, "contract_volume_total", "sum"), 2)
            av = round(v / cnt, 2) if cnt else 0.0
            pct = round((v / vol_den) * 100.0, 2) if vol_den else 0.0
            ind_fin_rows.append(
                {
                    "id": i,
                    "data": [ind_sel.get(key, key), cnt, v, av, f"{pct} %"],
                }
            )

        tables = [
            {
                "title": "Proposal analytics summary",
                "res_model": "bid.proposal",
                "columns": ["Metric", "Value"],
                "rows": summary_rows,
            },
            {
                "title": "Outcome breakdown — count & volume",
                "res_model": "bid.proposal",
                "columns": ["Outcome", "Count", "Volume (AED)"],
                "rows": outcome_detail,
            },
            {
                "title": "Highest-value proposals (top 22 in filter)",
                "res_model": "bid.proposal",
                "columns": [
                    "Ref",
                    "Title",
                    "Enquiry",
                    "Industry",
                    "Sales",
                    "Outcome",
                    "Volume (AED)",
                    "Customer type",
                ],
                "rows": top_rows,
            },
            {
                "title": "Industry — proposal count & contract volume",
                "res_model": "bid.proposal",
                "columns": [
                    "Industry",
                    "Proposals",
                    "Total volume (AED)",
                    "Avg volume (AED)",
                    "Share of total volume",
                ],
                "rows": ind_fin_rows,
            },
        ]
        return {"charts": charts, "tables": tables}

    @api.model
    def _pdf_enrichment_leads(self, fp):
        Lead = self.env["crm.lead"]
        domain = self._crm_lead_leads_domain(fp)
        total = Lead.search_count(domain)
        unassigned = Lead.search_count(domain + [("user_id", "=", False)])

        user_groups = Lead.read_group(domain, ["id:count"], ["user_id"], lazy=False)
        urows = [r for r in user_groups if r.get("user_id")]
        urows.sort(key=lambda r: self._count_value(r), reverse=True)
        urows = urows[:18]
        ul, uk, uv = [], [], []
        for row in urows:
            u = row["user_id"]
            uk.append(u[0])
            ul.append(u[1])
            uv.append(self._count_value(row))

        intake_groups = Lead.read_group(domain, ["id:count"], ["bid_intake_status"], lazy=False)
        il, ik, iv = [], [], []
        for row in intake_groups:
            key = row.get("bid_intake_status")
            if key:
                ik.append(key)
                il.append(str(key))
                iv.append(self._count_value(row))

        scope_sel = dict(Lead._fields["bid_intake_scope_of_work"].selection)
        scope_groups = Lead.read_group(domain, ["id:count"], ["bid_intake_scope_of_work"], lazy=False)
        sl, sk, sv = [], [], []
        for row in scope_groups:
            key = row.get("bid_intake_scope_of_work")
            if key:
                sk.append(key)
                sl.append(scope_sel.get(key, key))
                sv.append(self._count_value(row))

        charts = [
            self._pdf_chart_bar(
                "Leads by salesperson",
                ul,
                uk,
                uv,
                action_model="crm.lead",
                action_domain_field="user_id",
                action_type="many2one",
                extra_domain=[("type", "=", "lead")],
            ),
            self._pdf_chart_bar(
                "Leads by intake status",
                il,
                ik,
                iv,
                action_model="crm.lead",
                action_domain_field="bid_intake_status",
                action_type="selection",
                extra_domain=[("type", "=", "lead")],
            ),
        ]
        if sl:
            charts.append(
                self._pdf_chart_bar(
                    "Leads by scope of work (intake)",
                    sl,
                    sk,
                    sv,
                    action_model="crm.lead",
                    action_domain_field="bid_intake_scope_of_work",
                    action_type="selection",
                    extra_domain=[("type", "=", "lead")],
                )
            )

        if "medium_id" in Lead._fields:
            med_groups = Lead.read_group(domain, ["id:count"], ["medium_id"], lazy=False)
            mrows = [r for r in med_groups if r.get("medium_id")]
            mrows.sort(key=lambda r: self._count_value(r), reverse=True)
            mrows = mrows[:14]
            ml, mk, mv = [], [], []
            for row in mrows:
                m = row["medium_id"]
                mk.append(m[0])
                ml.append(m[1])
                mv.append(self._count_value(row))
            if ml:
                charts.append(
                    self._pdf_chart_bar(
                        "Leads by source / medium",
                        ml,
                        mk,
                        mv,
                        action_model="crm.lead",
                        action_domain_field="medium_id",
                        action_type="many2one",
                        extra_domain=[("type", "=", "lead")],
                    )
                )

        ind_rev_rows = []
        if "industry_id" in Lead._fields and "expected_revenue" in Lead._fields:
            ig = Lead.read_group(domain, ["id:count", "expected_revenue:sum"], ["industry_id"], lazy=False)
            irows = [r for r in ig if r.get("industry_id")]
            irows.sort(key=lambda r: self._metric_value(r, "expected_revenue", "sum"), reverse=True)
            irows = irows[:16]
            ilb, iky, ivl = [], [], []
            tot_rev = sum(self._metric_value(r, "expected_revenue", "sum") for r in irows) or 0.0
            den_rev = tot_rev if tot_rev else 1.0
            for i, row in enumerate(irows):
                ind = row["industry_id"]
                cnt = self._count_value(row)
                rev = round(self._metric_value(row, "expected_revenue", "sum"), 2)
                ilb.append(ind[1])
                iky.append(ind[0])
                ivl.append(rev)
                ind_rev_rows.append(
                    {
                        "id": i,
                        "data": [
                            ind[1],
                            cnt,
                            rev,
                            round(rev / cnt, 2) if cnt else 0.0,
                            f"{round(rev / den_rev * 100.0, 2)} %",
                        ],
                    }
                )
            if ilb:
                charts.append(
                    self._pdf_chart_bar(
                        "Expected revenue by industry (CRM)",
                        ilb,
                        iky,
                        ivl,
                        dataset_label="Expected revenue",
                        action_model="crm.lead",
                        action_domain_field="industry_id",
                        action_type="many2one",
                        extra_domain=[("type", "=", "lead")],
                    )
                )

        project_with_lead = self.env["bid.project"].search(
            [("crm_lead_id", "!=", False)] + self.analytics_extra_domain_bid_project()
        )
        linked_ids = set(project_with_lead.mapped("crm_lead_id").ids)
        with_enquiry = Lead.search_count(domain + [("id", "in", list(linked_ids))]) if linked_ids else 0

        pct_un = round((unassigned / total * 100.0), 2) if total else 0.0
        pct_link = round((with_enquiry / total * 100.0), 2) if total else 0.0

        summary_rows = [
            {"id": 0, "data": ["Total leads", str(total)]},
            {"id": 0, "data": ["Unassigned", str(unassigned)]},
            {"id": 0, "data": ["Unassigned share", f"{pct_un} %"]},
            {"id": 0, "data": ["Linked to an enquiry", str(with_enquiry)]},
            {"id": 0, "data": ["Linked share", f"{pct_link} %"]},
        ]
        if "expected_revenue" in Lead._fields:
            rev_agg = Lead.read_group(domain, ["expected_revenue:sum"], [])
            ra = rev_agg[0] if rev_agg else {}
            sum_er = round(self._metric_value(ra, "expected_revenue", "sum"), 2)
            avg_er = round(sum_er / total, 2) if total else 0.0
            summary_rows.append({"id": 0, "data": ["Total expected revenue (CRM)", str(sum_er)]})
            summary_rows.append({"id": 0, "data": ["Average expected revenue per lead", str(avg_er)]})

        tables = [
            {
                "title": "Lead funnel summary",
                "res_model": "crm.lead",
                "columns": ["Metric", "Value"],
                "rows": summary_rows,
            }
        ]
        if "industry_id" in Lead._fields and "expected_revenue" in Lead._fields and ind_rev_rows:
            tables.append(
                {
                    "title": "Industry — lead count & expected revenue",
                    "res_model": "crm.lead",
                    "columns": [
                        "Industry",
                        "Leads",
                        "Expected revenue",
                        "Avg per lead",
                        "Share of revenue",
                    ],
                    "rows": ind_rev_rows,
                }
            )
        return {"charts": charts, "tables": tables}

    @api.model
    def _pdf_enrichment_activity(self, fp):
        Sub = self.env["bid.submission"]
        Chg = self.env["bid.change.request"]
        sub_dom = self._submission_domain(fp)
        chg_dom = self._change_domain(fp)

        own_groups = Sub.read_group(sub_dom, ["id:count"], ["owner_id"], lazy=False)
        orows = [r for r in own_groups if r.get("owner_id")]
        orows.sort(key=lambda r: self._count_value(r), reverse=True)
        orows = orows[:18]
        ol, ok, ov = [], [], []
        for row in orows:
            o = row["owner_id"]
            ok.append(o[0])
            ol.append(o[1])
            ov.append(self._count_value(row))

        rev_groups = Chg.read_group(chg_dom, ["id:count"], ["reviewer_id"], lazy=False)
        rrows = [r for r in rev_groups if r.get("reviewer_id")]
        rrows.sort(key=lambda r: self._count_value(r), reverse=True)
        rrows = rrows[:18]
        rl, rk, rv = [], [], []
        for row in rrows:
            rvv = row["reviewer_id"]
            rk.append(rvv[0])
            rl.append(rvv[1])
            rv.append(self._count_value(row))

        proj_sub = Sub.read_group(sub_dom, ["id:count"], ["project_id"], lazy=False)
        prows = [r for r in proj_sub if r.get("project_id")]
        prows.sort(key=lambda r: self._count_value(r), reverse=True)
        prows = prows[:15]
        pl, pk, pv = [], [], []
        for row in prows:
            p = row["project_id"]
            pk.append(p[0])
            pl.append(p[1])
            pv.append(self._count_value(row))

        charts = [
            self._pdf_chart_bar(
                "Submissions by owner",
                ol,
                ok,
                ov,
                action_model="bid.submission",
                action_domain_field="owner_id",
                action_type="many2one",
            ),
            self._pdf_chart_bar(
                "Change requests by reviewer (period)",
                rl,
                rk,
                rv,
                action_model="bid.change.request",
                action_domain_field="reviewer_id",
                action_type="many2one",
            ),
            self._pdf_chart_bar(
                "Submission activity by project",
                pl,
                pk,
                pv,
                action_model="bid.submission",
                action_domain_field="project_id",
                action_type="many2one",
            ),
        ]

        sub_month = Sub.read_group(sub_dom, ["id:count"], ["submitted_date:month"], lazy=False)
        sml, smk, smv = [], [], []
        for row in sub_month:
            label = row.get("submitted_date:month")
            if label:
                ls = str(label)
                sml.append(ls)
                smk.append(ls)
                smv.append(self._count_value(row))
        if sml:
            charts.append(
                self._pdf_chart_bar(
                    "Submissions by month (submitted date)",
                    sml,
                    smk,
                    smv,
                    action_model="bid.submission",
                    action_domain_field="submitted_date",
                    action_type="date_period",
                )
            )

        chg_month = Chg.read_group(chg_dom, ["id:count"], ["create_date:month"], lazy=False)
        cml, cmk, cmv = [], [], []
        for row in chg_month:
            label = row.get("create_date:month")
            if label:
                ls = str(label)
                cml.append(ls)
                cmk.append(ls)
                cmv.append(self._count_value(row))
        if cml:
            charts.append(
                self._pdf_chart_bar(
                    "Change requests by month (created)",
                    cml,
                    cmk,
                    cmv,
                    action_model="bid.change.request",
                    action_domain_field="create_date",
                    action_type="date_period",
                )
            )

        Project = self.env["bid.project"]
        ind_sel_a = dict(Project._fields["industry"].selection)
        em_sel_a = dict(Project._fields["emirate"].selection)
        touch_projects = Sub.search(sub_dom).mapped("project_id") | Chg.search(chg_dom).mapped(
            "project_id"
        )
        uniq_projects = Project.browse(list({p.id for p in touch_projects if p}))
        ind_act = defaultdict(lambda: {"n": 0, "v": 0.0, "sc_w": 0.0, "sc_c": 0})
        em_act = defaultdict(lambda: {"n": 0, "v": 0.0})
        portfolio_val = 0.0
        for p in uniq_projects:
            cv = float(p.contract_value or 0.0)
            portfolio_val += cv
            if p.industry:
                ind_act[p.industry]["n"] += 1
                ind_act[p.industry]["v"] += cv
                if p.score_overall:
                    ind_act[p.industry]["sc_w"] += float(p.score_overall)
                    ind_act[p.industry]["sc_c"] += 1
            if p.emirate:
                em_act[p.emirate]["n"] += 1
                em_act[p.emirate]["v"] += cv
        den_act = portfolio_val if portfolio_val else 1.0

        ial, iak, iav = [], [], []
        for ind_k, d in sorted(ind_act.items(), key=lambda x: x[1]["v"], reverse=True)[:14]:
            ial.append(ind_sel_a.get(ind_k, ind_k))
            iak.append(ind_k)
            iav.append(round(d["v"], 2))
        if ial:
            charts.append(
                self._pdf_chart_bar(
                    "Linked enquiries — contract value by industry (unique projects in period)",
                    ial,
                    iak,
                    iav,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="industry",
                    action_type="selection",
                )
            )

        eal, eak, eav = [], [], []
        for em_key, d in sorted(em_act.items(), key=lambda x: x[1]["v"], reverse=True)[:14]:
            eal.append(em_sel_a.get(em_key, em_key))
            eak.append(em_key)
            eav.append(round(d["v"], 2))
        if eal:
            charts.append(
                self._pdf_chart_bar(
                    "Linked enquiries — contract value by emirate (unique projects in period)",
                    eal,
                    eak,
                    eav,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="emirate",
                    action_type="selection",
                )
            )

        act_ind_rows = []
        for i, (ind_k, d) in enumerate(sorted(ind_act.items(), key=lambda x: x[1]["v"], reverse=True)):
            v = round(d["v"], 2)
            cnt = d["n"]
            avv = round(v / cnt, 2) if cnt else 0.0
            avg_sc = round(d["sc_w"] / d["sc_c"], 2) if d["sc_c"] else 0.0
            pct = round((v / den_act) * 100.0, 2) if den_act else 0.0
            act_ind_rows.append(
                {
                    "id": i,
                    "data": [ind_sel_a.get(ind_k, ind_k), cnt, v, avv, avg_sc, f"{pct} %"],
                }
            )

        act_em_rows = []
        for i, (em_key, d) in enumerate(sorted(em_act.items(), key=lambda x: x[1]["v"], reverse=True)):
            v = round(d["v"], 2)
            cnt = d["n"]
            avv = round(v / cnt, 2) if cnt else 0.0
            pct = round((v / den_act) * 100.0, 2) if den_act else 0.0
            act_em_rows.append(
                {
                    "id": i,
                    "data": [em_sel_a.get(em_key, em_key), cnt, v, avv, f"{pct} %"],
                }
            )

        chg_res = Chg.read_group(chg_dom, ["id:count"], ["resolved"], lazy=False)
        summary_rows = []
        for row in chg_res:
            res_key = row.get("resolved")
            label = "Open" if res_key is False else ("Resolved" if res_key else "Unknown")
            summary_rows.append({"id": 0, "data": [label, str(self._count_value(row))]})

        tables = [
            {
                "title": "Change requests in period — open vs resolved",
                "res_model": "bid.change.request",
                "columns": ["Resolution", "Count"],
                "rows": summary_rows or [{"id": 0, "data": ["No change requests in period", "0"]}],
            },
            {
                "title": "Financial snapshot — linked enquiries by industry (unique projects touched)",
                "res_model": "bid.project",
                "columns": [
                    "Industry",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Avg score %",
                    "Share of touched portfolio",
                ],
                "rows": act_ind_rows,
            },
            {
                "title": "Financial snapshot — linked enquiries by emirate (unique projects touched)",
                "res_model": "bid.project",
                "columns": [
                    "Emirate",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Share of touched portfolio",
                ],
                "rows": act_em_rows,
            },
        ]
        return {"charts": charts, "tables": tables}

    @api.model
    def _pdf_enrichment_by_rep(self, fp):
        SPD = self.env["sales_bid_board.salesperson.dashboard"]
        clean = SPD._sanitize(fp)
        project = self.env["bid.project"]
        domain = SPD._domain(clean)

        decision_sel = dict(project._fields["decision_final"].selection)
        dec_groups = project.read_group(domain, ["id:count"], ["decision_final"], lazy=False)
        dl, dk, dv = [], [], []
        for row in dec_groups:
            key = row.get("decision_final")
            if key:
                dk.append(key)
                dl.append(decision_sel.get(key, key))
                dv.append(self._count_value(row))

        ind_sel = dict(project._fields["industry"].selection)
        ind_groups = project.read_group(domain, ["id:count"], ["industry"], lazy=False)
        il, ik, iv = [], [], []
        for row in ind_groups:
            key = row.get("industry")
            if key:
                ik.append(key)
                il.append(ind_sel.get(key, key))
                iv.append(self._count_value(row))
        pairs = sorted(zip(il, ik, iv), key=lambda x: x[2], reverse=True)
        pairs = pairs[:14]
        if pairs:
            il, ik, iv = [p[0] for p in pairs], [p[1] for p in pairs], [p[2] for p in pairs]

        out_sel = dict(project._fields["outcome_status"].selection)
        out_groups = project.read_group(domain, ["id:count"], ["outcome_status"], lazy=False)
        ool, ook, oov = [], [], []
        for row in out_groups:
            key = row.get("outcome_status")
            if key:
                ook.append(key)
                ool.append(out_sel.get(key, key))
                oov.append(self._count_value(row))

        charts = [
            self._pdf_chart_doughnut(
                "Bid decision mix (filtered enquiries)",
                dl,
                dk,
                dv,
                dataset_label="Projects",
                action_model="bid.project",
                action_domain_field="decision_final",
                action_type="selection",
            ),
            self._pdf_chart_bar(
                "Enquiry count by industry (filtered)",
                il,
                ik,
                iv,
                action_model="bid.project",
                action_domain_field="industry",
                action_type="selection",
            ),
        ]
        if ool:
            charts.append(
                self._pdf_chart_doughnut(
                    "Enquiry outcome status (filtered)",
                    ool,
                    ook,
                    oov,
                    dataset_label="Projects",
                    action_model="bid.project",
                    action_domain_field="outcome_status",
                    action_type="selection",
                )
            )
        agg = project.read_group(domain, ["id:count", "contract_value:sum", "score_overall:avg"], [])
        agg = agg[0] if agg else {}
        total_p = self._count_value(agg)
        tot_val = round(self._metric_value(agg, "contract_value", "sum"), 2)
        avg_sc = round(self._metric_value(agg, "score_overall", "avg"), 2)
        active_reps = len([r for r in project.read_group(domain, ["id:count"], ["sales_rep"], lazy=False) if r.get("sales_rep")])

        den_v = tot_val if tot_val else 1.0
        em_sel_br = dict(project._fields["emirate"].selection)
        ind_mix_br = project.read_group(
            domain, ["id:count", "contract_value:sum", "score_overall:avg"], ["industry"], lazy=False
        )
        ibl, ibk, ibv = [], [], []
        for row in sorted(
            [r for r in ind_mix_br if r.get("industry")],
            key=lambda r: self._metric_value(r, "contract_value", "sum"),
            reverse=True,
        )[:14]:
            k = row["industry"]
            ibk.append(k)
            ibl.append(ind_sel.get(k, k))
            ibv.append(round(self._metric_value(row, "contract_value", "sum"), 2))
        if ibl:
            charts.append(
                self._pdf_chart_bar(
                    "Contract value (AED) by industry (filtered)",
                    ibl,
                    ibk,
                    ibv,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="industry",
                    action_type="selection",
                )
            )

        ind_tbl_br = []
        for i, row in enumerate(
            sorted(
                [r for r in ind_mix_br if r.get("industry")],
                key=lambda r: self._metric_value(r, "contract_value", "sum"),
                reverse=True,
            )
        ):
            key = row["industry"]
            cnt = self._count_value(row)
            v = round(self._metric_value(row, "contract_value", "sum"), 2)
            avv = round(v / cnt, 2) if cnt else 0.0
            sc = round(self._metric_value(row, "score_overall", "avg"), 2)
            pct = round((v / den_v) * 100.0, 2) if den_v else 0.0
            ind_tbl_br.append(
                {
                    "id": i,
                    "data": [ind_sel.get(key, key), cnt, v, avv, sc, f"{pct} %"],
                }
            )

        em_mix_br = project.read_group(domain, ["id:count", "contract_value:sum"], ["emirate"], lazy=False)
        ebl, ebk, ebv = [], [], []
        for row in sorted(
            [r for r in em_mix_br if r.get("emirate")],
            key=lambda r: self._metric_value(r, "contract_value", "sum"),
            reverse=True,
        )[:14]:
            k = row["emirate"]
            ebk.append(k)
            ebl.append(em_sel_br.get(k, k))
            ebv.append(round(self._metric_value(row, "contract_value", "sum"), 2))
        if ebl:
            charts.append(
                self._pdf_chart_bar(
                    "Contract value (AED) by emirate (filtered)",
                    ebl,
                    ebk,
                    ebv,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="emirate",
                    action_type="selection",
                )
            )

        em_tbl_br = []
        for i, row in enumerate(
            sorted(
                [r for r in em_mix_br if r.get("emirate")],
                key=lambda r: self._metric_value(r, "contract_value", "sum"),
                reverse=True,
            )
        ):
            key = row["emirate"]
            cnt = self._count_value(row)
            v = round(self._metric_value(row, "contract_value", "sum"), 2)
            avv = round(v / cnt, 2) if cnt else 0.0
            pct = round((v / den_v) * 100.0, 2) if den_v else 0.0
            em_tbl_br.append(
                {"id": i, "data": [em_sel_br.get(key, key), cnt, v, avv, f"{pct} %"]}
            )

        tables = [
            {
                "title": "Team snapshot (same filters as chart)",
                "res_model": "bid.project",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"id": 0, "data": ["Active sales reps (with ≥1 enquiry)", str(active_reps)]},
                    {"id": 0, "data": ["Total enquiries in filter", str(total_p)]},
                    {"id": 0, "data": ["Total contract value (AED)", str(tot_val)]},
                    {"id": 0, "data": ["Average enquiry score (%)", str(avg_sc)]},
                ],
            },
            {
                "title": "Industry — enquiries, value & scores (filtered)",
                "res_model": "bid.project",
                "columns": [
                    "Industry",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Avg score %",
                    "Share of portfolio value",
                ],
                "rows": ind_tbl_br,
            },
            {
                "title": "Emirate — enquiries & contract value (filtered)",
                "res_model": "bid.project",
                "columns": [
                    "Emirate",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Share of portfolio value",
                ],
                "rows": em_tbl_br,
            },
        ]
        return {"charts": charts, "tables": tables}

    @api.model
    def _pdf_enrichment_enquiries(self, fp):
        Dash = self.env["sales_bid_board.dashboard"]
        clean = Dash._sanitize_filter_params(fp)
        domain = Dash._build_project_domain(clean)
        project = self.env["bid.project"]

        out_sel = dict(project._fields["outcome_status"].selection)
        og = project.read_group(domain, ["id:count"], ["outcome_status"], lazy=False)
        ol, ok, ov = [], [], []
        for row in og:
            key = row.get("outcome_status")
            if key:
                ok.append(key)
                ol.append(out_sel.get(key, key))
                ov.append(self._count_value(row))

        rep_groups = project.read_group(domain, ["id:count"], ["sales_rep"], lazy=False)
        rrows = [r for r in rep_groups if r.get("sales_rep")]
        rrows.sort(key=lambda r: self._count_value(r), reverse=True)
        rrows = rrows[:18]
        rl, rk, rv = [], [], []
        for row in rrows:
            s = row["sales_rep"]
            rk.append(s[0])
            rl.append(s[1])
            rv.append(self._count_value(row))

        charts = [
            self._pdf_chart_doughnut(
                "Enquiries by pipeline outcome",
                ol,
                ok,
                ov,
                dataset_label="Enquiries",
                action_model="bid.project",
                action_domain_field="outcome_status",
                action_type="selection",
            ),
            self._pdf_chart_bar(
                "Enquiry load by sales rep (top 18)",
                rl,
                rk,
                rv,
                action_model="bid.project",
                action_domain_field="sales_rep",
                action_type="many2one",
            ),
        ]

        val_by_out = project.read_group(domain, ["contract_value:sum"], ["outcome_status"], lazy=False)
        vl, vk, vv = [], [], []
        for row in val_by_out:
            key = row.get("outcome_status")
            if key:
                vk.append(key)
                vl.append(out_sel.get(key, key))
                vv.append(round(Dash._metric_value(row, "contract_value", "sum"), 2))
        if vl:
            charts.append(
                self._pdf_chart_bar(
                    "Contract value (AED) by enquiry outcome",
                    vl,
                    vk,
                    vv,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="outcome_status",
                    action_type="selection",
                )
            )

        ind_sel = dict(project._fields["industry"].selection)
        em_sel = dict(project._fields["emirate"].selection)
        agg_pre = project.read_group(domain, ["contract_value:sum", "score_overall:avg"], [])
        agg_pre = agg_pre[0] if agg_pre else {}
        val_sum_pre = round(self._metric_value(agg_pre, "contract_value", "sum"), 2)
        val_den_pf = val_sum_pre if val_sum_pre else 1.0

        ind_mix = project.read_group(
            domain, ["id:count", "contract_value:sum", "score_overall:avg"], ["industry"], lazy=False
        )
        iri, irk, irv = [], [], []
        for row in sorted(
            [r for r in ind_mix if r.get("industry")],
            key=lambda r: self._metric_value(r, "contract_value", "sum"),
            reverse=True,
        )[:14]:
            k = row["industry"]
            irk.append(k)
            iri.append(ind_sel.get(k, k))
            irv.append(round(self._metric_value(row, "contract_value", "sum"), 2))
        if iri:
            charts.append(
                self._pdf_chart_bar(
                    "Contract value (AED) by industry",
                    iri,
                    irk,
                    irv,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="industry",
                    action_type="selection",
                )
            )

        em_mix = project.read_group(domain, ["id:count", "contract_value:sum"], ["emirate"], lazy=False)
        emi, emk, emv = [], [], []
        for row in sorted(
            [r for r in em_mix if r.get("emirate")],
            key=lambda r: self._metric_value(r, "contract_value", "sum"),
            reverse=True,
        )[:14]:
            k = row["emirate"]
            emk.append(k)
            emi.append(em_sel.get(k, k))
            emv.append(round(self._metric_value(row, "contract_value", "sum"), 2))
        if emi:
            charts.append(
                self._pdf_chart_bar(
                    "Contract value (AED) by emirate",
                    emi,
                    emk,
                    emv,
                    dataset_label="Value (AED)",
                    action_model="bid.project",
                    action_domain_field="emirate",
                    action_type="selection",
                )
            )

        ind_table = []
        for i, row in enumerate(
            sorted(
                [r for r in ind_mix if r.get("industry")],
                key=lambda r: self._metric_value(r, "contract_value", "sum"),
                reverse=True,
            )
        ):
            key = row["industry"]
            cnt = self._count_value(row)
            v = round(self._metric_value(row, "contract_value", "sum"), 2)
            avv = round(v / cnt, 2) if cnt else 0.0
            sc = round(self._metric_value(row, "score_overall", "avg"), 2)
            pct = round((v / val_den_pf) * 100.0, 2) if val_den_pf else 0.0
            ind_table.append(
                {
                    "id": i,
                    "data": [ind_sel.get(key, key), cnt, v, avv, sc, f"{pct} %"],
                }
            )

        em_table = []
        for i, row in enumerate(
            sorted(
                [r for r in em_mix if r.get("emirate")],
                key=lambda r: self._metric_value(r, "contract_value", "sum"),
                reverse=True,
            )
        ):
            key = row["emirate"]
            cnt = self._count_value(row)
            v = round(self._metric_value(row, "contract_value", "sum"), 2)
            avv = round(v / cnt, 2) if cnt else 0.0
            pct = round((v / val_den_pf) * 100.0, 2) if val_den_pf else 0.0
            em_table.append(
                {"id": i, "data": [em_sel.get(key, key), cnt, v, avv, f"{pct} %"]}
            )

        total = project.search_count(domain)
        agg = agg_pre
        val_sum = val_sum_pre
        avg_score = round(self._metric_value(agg, "score_overall", "avg"), 2)
        pending = project.search_count(domain + [("review_status", "=", "pending_review")])
        approved = project.search_count(domain + [("review_status", "=", "approved")])

        tables = [
            {
                "title": "Enquiry register summary",
                "res_model": "bid.project",
                "columns": ["Metric", "Value"],
                "rows": [
                    {"id": 0, "data": ["Enquiries in filter", str(total)]},
                    {"id": 0, "data": ["Pending review", str(pending)]},
                    {"id": 0, "data": ["Approved", str(approved)]},
                    {"id": 0, "data": ["Total contract value (AED)", str(val_sum)]},
                    {"id": 0, "data": ["Average score (%)", str(avg_score)]},
                ],
            },
            {
                "title": "Industry — enquiries, contract value & scores",
                "res_model": "bid.project",
                "columns": [
                    "Industry",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Avg score %",
                    "Share of portfolio value",
                ],
                "rows": ind_table,
            },
            {
                "title": "Emirate — enquiries & contract value",
                "res_model": "bid.project",
                "columns": [
                    "Emirate",
                    "Enquiries",
                    "Contract value (AED)",
                    "Avg value (AED)",
                    "Share of portfolio value",
                ],
                "rows": em_table,
            },
        ]
        return {"charts": charts, "tables": tables}

    @api.model
    def _pdf_enrichment_for_tab(self, tab, fp):
        tab = (tab or "enquiries").strip()
        if tab == "proposals":
            return self._pdf_enrichment_proposals(fp)
        if tab == "leads":
            return self._pdf_enrichment_leads(fp)
        if tab == "activity":
            return self._pdf_enrichment_activity(fp)
        if tab == "by_rep":
            return self._pdf_enrichment_by_rep(fp)
        if tab == "enquiries":
            return self._pdf_enrichment_enquiries(fp)
        return {"charts": [], "tables": []}

    @api.model
    def get_tab_data(self, tab, filter_params=None):
        """Return one tab payload: kpis, charts, tables, filter_options (optional)."""
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        tab = (tab or "enquiries").strip()
        if tab == "enquiries":
            return self.env["sales_bid_board.dashboard"].get_dashboard_data(False, {}, fp)
        if tab == "by_rep":
            rep_fp = {
                k: fp[k]
                for k in ("date_from", "date_to", "industry", "emirate", "outcome_status", "sales_rep_id")
                if k in fp and fp[k] not in (None, "", False)
            }
            return self.env["sales_bid_board.salesperson.dashboard"].get_dashboard_data(False, {}, rep_fp)
        if tab == "leads":
            return self._tab_leads(fp)
        if tab == "proposals":
            return self._tab_proposals(fp)
        if tab == "activity":
            return self._tab_activity(fp)
        return {}

    _PDF_TAB_TITLES = {
        "enquiries": "Bid Board Analytics — Enquiries",
        "leads": "Bid Board Analytics — Leads",
        "by_rep": "Bid Board Analytics — By sales rep",
        "proposals": "Bid Board Analytics — Proposals",
        "activity": "Bid Board Analytics — Activity & reminders",
    }

    @api.model
    def get_pdf_report_payload(self, tab, filter_params=None):
        """KPI/chart/table payload for the shared QWeb PDF (matches on-screen analytics tabs)."""
        fp = self.analytics_clamp_filter_params_for_salesperson(dict(filter_params or {}))
        tab = (tab or "enquiries").strip()
        if tab == "enquiries":
            data = self.env["sales_bid_board.dashboard"].get_dashboard_data(False, {}, fp)
        elif tab == "by_rep":
            rep_fp = {
                k: fp[k]
                for k in ("date_from", "date_to", "industry", "emirate", "outcome_status", "sales_rep_id")
                if k in fp and fp[k] not in (None, "", False)
            }
            data = self.env["sales_bid_board.salesperson.dashboard"].get_dashboard_data(False, {}, rep_fp)
        elif tab == "leads":
            data = self._tab_leads(fp)
        elif tab == "proposals":
            data = self._tab_proposals(fp)
        elif tab == "activity":
            data = self._tab_activity(fp)
        else:
            data = {}
        extra = self._pdf_enrichment_for_tab(tab, fp)
        charts = list(data.get("charts") or []) + list(extra.get("charts") or [])
        tables = list(data.get("tables") or []) + list(extra.get("tables") or [])
        return {
            "kpis": data.get("kpis", []),
            "charts": charts,
            "tables": tables,
        }

    @api.model
    def action_print_enquiries_pdf(self, filter_params=None):
        """Print the analytics PDF for the tab named in ``analytics_tab`` (default: enquiries).

        Uses this long-standing RPC name so multi-worker Odoo reloads stay consistent
        (avoid adding a second public ``call_kw`` entry point for the same feature).
        """
        fp = dict(filter_params or {})
        raw_tab = fp.pop("analytics_tab", None) or fp.pop("_analytics_tab", None)
        if isinstance(raw_tab, str):
            tab_key = (raw_tab.strip() or "enquiries")
        else:
            tab_key = "enquiries"
        title = self._PDF_TAB_TITLES.get(tab_key, "Bid Board Analytics")
        Dashboard = self.env["sales_bid_board.dashboard"]
        dashboard = Dashboard.search([], limit=1)
        if not dashboard:
            dashboard = Dashboard.create({"name": "Sales Bid Board Dashboard"})
        return self.env.ref("sales_bid_board.action_report_sales_bid_board_dashboard").with_context(
            filter_params=fp,
            bid_board_analytics_tab=tab_key,
            bid_board_analytics_report_title=title,
        ).report_action(dashboard)
