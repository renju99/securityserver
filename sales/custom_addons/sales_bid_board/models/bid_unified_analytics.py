from datetime import date as date_cls
from datetime import timedelta

from odoo import api, fields, models


class SalesBidBoardUnifiedAnalytics(models.TransientModel):
    _name = "sales_bid_board.unified.analytics"
    _description = "Bid Board unified analytics (tabbed)"

    name = fields.Char(default="Analytics", required=True)

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
        domain = [("type", "=", "lead")] + self._domain_create_date(filter_params)
        if filter_params.get("sales_rep_id"):
            try:
                domain.append(("user_id", "=", int(filter_params["sales_rep_id"])))
            except (TypeError, ValueError):
                pass
        if filter_params.get("team_id"):
            try:
                domain.append(("team_id", "=", int(filter_params["team_id"])))
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
        project_with_lead = self.env["bid.project"].search([("crm_lead_id", "!=", False)])
        linked_ids = project_with_lead.mapped("crm_lead_id").ids
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
            "Open proposals", "bid.proposal", self._proposal_domain(fp) + [("outcome_status", "=", "open")]
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
        domain = list(self._domain_create_date(filter_params))
        if filter_params.get("industry"):
            domain.append(("project_id.industry", "=", filter_params["industry"]))
        if filter_params.get("emirate"):
            domain.append(("project_id.emirate", "=", filter_params["emirate"]))
        if filter_params.get("sales_rep_id"):
            try:
                domain.append(("sales_user_id", "=", int(filter_params["sales_rep_id"])))
            except (TypeError, ValueError):
                pass
        return domain

    @api.model
    def _submission_domain(self, filter_params):
        domain = []
        if filter_params.get("date_from"):
            domain.append(("submitted_date", ">=", filter_params["date_from"]))
        if filter_params.get("date_to"):
            domain.append(("submitted_date", "<=", filter_params["date_to"]))
        return domain

    @api.model
    def _change_domain(self, filter_params):
        return list(self._domain_create_date(filter_params))

    @api.model
    def _tab_leads(self, filter_params):
        Lead = self.env["crm.lead"]
        domain = self._crm_lead_leads_domain(filter_params)

        total = Lead.search_count(domain)
        unassigned = Lead.search_count(domain + [("user_id", "=", False)])

        project_with_lead = self.env["bid.project"].search([("crm_lead_id", "!=", False)])
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
        open_c = Proposal.search_count(domain + [("outcome_status", "=", "open")])
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
                    "name": "Open",
                    "value": open_c,
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
        Sub = self.env["bid.submission"]
        Chg = self.env["bid.change.request"]
        Notif = self.env["bid.notification"]

        sub_dom = []
        if filter_params.get("date_from"):
            sub_dom.append(("submitted_date", ">=", filter_params["date_from"]))
        if filter_params.get("date_to"):
            sub_dom.append(("submitted_date", "<=", filter_params["date_to"]))

        chg_dom = self._domain_create_date(filter_params)
        notif_dom = self._domain_create_date(filter_params)

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
    def get_tab_data(self, tab, filter_params=None):
        """Return one tab payload: kpis, charts, tables, filter_options (optional)."""
        fp = dict(filter_params or {})
        tab = (tab or "enquiries").strip()
        if tab == "enquiries":
            return self.env["sales_bid_board.dashboard"].get_dashboard_data(False, {}, fp)
        if tab == "by_rep":
            rep_fp = {
                k: fp[k]
                for k in ("date_from", "date_to", "industry", "emirate", "state", "sales_rep_id")
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

    @api.model
    def action_print_enquiries_pdf(self, filter_params=None):
        """PDF remains enquiry-centric (existing report)."""
        return self.env["sales_bid_board.dashboard"].action_print_dashboard_report(filter_params or {})
