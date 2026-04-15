/** @odoo-module **/

import { _t } from "@web/core/l10n/translation";
import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";
import { Layout } from "@web/search/layout";
import { useSetupAction } from "@web/search/action_hook";
import { standardActionServiceProps } from "@web/webclient/actions/action_service";

const TABS = [
    { key: "leads", label: "Leads" },
    { key: "enquiries", label: "Enquiries" },
    { key: "by_rep", label: "By sales rep" },
    { key: "proposals", label: "Proposals" },
    { key: "activity", label: "Activity & reminders" },
];

class BidBoardUnifiedAnalytics extends Component {
    static template = "sales_bid_board.BidBoardUnifiedAnalytics";
    static components = { Layout };
    static props = { ...standardActionServiceProps };

    setup() {
        useSetupAction({});
        this.env.config.setDisplayName(this.props.action.name || _t("Bid Board Analytics"));
        this.layoutDisplay = {
            controlPanel: false,
            searchPanel: false,
        };

        this.orm = useService("orm");
        this.action = useService("action");
        this.chartInstances = {};

        const today = new Date();
        const last30 = new Date();
        last30.setDate(today.getDate() - 30);

        this.state = useState({
            tabDefs: TABS,
            activeTab: "enquiries",
            loading: true,
            error: null,
            tabPayload: null,
            globalFilters: {
                date_from: last30.toISOString().split("T")[0],
                date_to: today.toISOString().split("T")[0],
                sales_rep_id: "",
                team_id: "",
                industry: "",
                emirate: "",
            },
            enquiryFilters: {
                outcome_status: "",
                review_status: "",
                decision_final: "",
                industry: "",
                emirate: "",
                stage_id: "",
                sales_rep_id: "",
                project_lead_id: "",
            },
            filterOptions: {
                teams: [],
                industries: [],
                emirates: [],
                outcome_statuses: [],
                review_statuses: [],
                decisions: [],
                stages: [],
                sales_reps: [],
                project_leads: [],
            },
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadActiveTab();
        });

        onMounted(() => {
            setTimeout(() => this.renderCharts(), 80);
        });
    }

    buildRpcParams() {
        const g = this.state.globalFilters;
        const e = this.state.enquiryFilters;
        const tab = this.state.activeTab;
        const base = {
            date_from: g.date_from,
            date_to: g.date_to,
        };
        if (g.sales_rep_id) {
            base.sales_rep_id = g.sales_rep_id;
        }
        if (tab === "leads") {
            if (g.team_id) {
                base.team_id = g.team_id;
            }
        }
        if (tab === "proposals") {
            if (g.industry) {
                base.industry = g.industry;
            }
            if (g.emirate) {
                base.emirate = g.emirate;
            }
        }
        if (tab === "enquiries") {
            Object.assign(base, {
                outcome_status: e.outcome_status,
                review_status: e.review_status,
                decision_final: e.decision_final,
                industry: e.industry,
                emirate: e.emirate,
                stage_id: e.stage_id,
                sales_rep_id: e.sales_rep_id || g.sales_rep_id,
                project_lead_id: e.project_lead_id,
            });
        }
        if (tab === "by_rep") {
            Object.assign(base, {
                industry: e.industry || g.industry,
                emirate: e.emirate || g.emirate,
                outcome_status: e.outcome_status,
                sales_rep_id: e.sales_rep_id || g.sales_rep_id,
            });
        }
        return Object.fromEntries(Object.entries(base).filter(([, v]) => v !== "" && v != null && v !== false));
    }

    mergeFilterOptions(incoming) {
        if (!incoming) {
            return;
        }
        const fo = this.state.filterOptions;
        for (const key of Object.keys(incoming)) {
            if (incoming[key] && incoming[key].length) {
                fo[key] = incoming[key];
            }
        }
    }

    async loadActiveTab() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const params = this.buildRpcParams();
            const data = await this.orm.call(
                "sales_bid_board.unified.analytics",
                "get_tab_data",
                [this.state.activeTab, params]
            );
            this.state.tabPayload = data;
            this.mergeFilterOptions(data.filter_options);
        } catch (err) {
            this.state.error = err.message || String(err);
            this.state.tabPayload = null;
        } finally {
            this.state.loading = false;
            setTimeout(() => this.renderCharts(), 80);
        }
    }

    async selectTab(key) {
        if (this.state.activeTab === key) {
            return;
        }
        this.state.activeTab = key;
        await this.loadActiveTab();
    }

    onGlobalChange(name, value) {
        this.state.globalFilters[name] = value;
        this.loadActiveTab();
    }

    onEnquiryChange(name, value) {
        this.state.enquiryFilters[name] = value;
        if (this.state.activeTab === "enquiries" || this.state.activeTab === "by_rep") {
            this.loadActiveTab();
        }
    }

    clearFilters() {
        const today = new Date();
        const last30 = new Date();
        last30.setDate(today.getDate() - 30);
        this.state.globalFilters = {
            date_from: last30.toISOString().split("T")[0],
            date_to: today.toISOString().split("T")[0],
            sales_rep_id: "",
            team_id: "",
            industry: "",
            emirate: "",
        };
        this.state.enquiryFilters = {
            outcome_status: "",
            review_status: "",
            decision_final: "",
            industry: "",
            emirate: "",
            stage_id: "",
            sales_rep_id: "",
            project_lead_id: "",
        };
        this.loadActiveTab();
    }

    async exportPdf() {
        if (this.state.activeTab !== "enquiries") {
            return;
        }
        try {
            const action = await this.orm.call(
                "sales_bid_board.unified.analytics",
                "action_print_enquiries_pdf",
                [this.buildRpcParams()]
            );
            if (action) {
                await this.action.doAction(action);
            }
        } catch (err) {
            this.state.error = err.message || String(err);
        }
    }

    async onKpiClick(kpi) {
        if (!kpi || !kpi.action) {
            return;
        }
        const params = this.buildRpcParams();
        const model = kpi.rpc_model || "sales_bid_board.dashboard";
        const action = await this.orm.call(model, kpi.action, [params]);
        if (action) {
            await this.action.doAction(action);
        }
    }

    onRowClick(table, row) {
        if (!row.id) {
            return;
        }
        if (table.list_drill) {
            const ld = table.list_drill;
            const params = this.buildRpcParams();
            const domain = [[ld.field, "=", row.id]];
            if (ld.model === "bid.project") {
                if (params.date_from) {
                    domain.push(["create_date", ">=", params.date_from]);
                }
                if (params.date_to) {
                    domain.push(["create_date", "<=", params.date_to]);
                }
                if (params.industry) {
                    domain.push(["industry", "=", params.industry]);
                }
                if (params.emirate) {
                    domain.push(["emirate", "=", params.emirate]);
                }
                if (params.outcome_status) {
                    domain.push(["outcome_status", "=", params.outcome_status]);
                }
            }
            this.action.doAction({
                type: "ir.actions.act_window",
                name: table.title,
                res_model: ld.model,
                view_mode: "list,form",
                views: [[false, "list"], [false, "form"]],
                target: "current",
                domain,
            });
            return;
        }
        if (!table.res_model) {
            return;
        }
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: table.res_model,
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    renderCharts() {
        Object.values(this.chartInstances).forEach((c) => c && c.destroy && c.destroy());
        this.chartInstances = {};
        const ChartLib = window.Chart;
        const payload = this.state.tabPayload;
        if (!ChartLib || !payload || !payload.charts) {
            return;
        }
        const tab = this.state.activeTab;
        payload.charts.forEach((chartData, index) => {
            const canvas = document.getElementById(`sbb_u_${tab}_${index}`);
            if (!canvas) {
                return;
            }
            const ctx = canvas.getContext("2d");
            this.chartInstances[index] = new ChartLib(ctx, {
                type: chartData.type,
                data: { labels: chartData.labels, datasets: chartData.datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (_, elements) => {
                        if (!elements || !elements.length) {
                            return;
                        }
                        this.onChartClick(chartData, elements[0].index);
                    },
                    plugins: { legend: { position: "top" } },
                    scales:
                        chartData.type === "pie" || chartData.type === "doughnut"
                            ? {}
                            : { y: { beginAtZero: true } },
                },
            });
        });
    }

    async onChartClick(chartData, pointIndex) {
        if (!chartData.action_model || pointIndex < 0) {
            return;
        }
        const key = chartData.keys ? chartData.keys[pointIndex] : null;
        const domain = [...(chartData.extra_domain || [])];
        if (chartData.action_type === "many2one") {
            if (key) {
                domain.push([chartData.action_domain_field, "=", parseInt(key, 10)]);
            }
        } else if (chartData.action_type === "selection") {
            if (key) {
                domain.push([chartData.action_domain_field, "=", key]);
            }
        } else if (chartData.action_type === "date_period") {
            const periods = chartData.period_domains;
            if (periods && periods[pointIndex] && periods[pointIndex].length) {
                for (const term of periods[pointIndex]) {
                    domain.push(term);
                }
            } else if (key) {
                domain.push([chartData.action_domain_field, "ilike", key]);
            }
        }
        const params = this.buildRpcParams();
        const fd = [];
        if (params.date_from) {
            if (chartData.action_model === "bid.submission") {
                fd.push(["submitted_date", ">=", params.date_from]);
            } else {
                fd.push(["create_date", ">=", `${params.date_from} 00:00:00`]);
            }
        }
        if (params.date_to) {
            if (chartData.action_model === "bid.submission") {
                fd.push(["submitted_date", "<=", params.date_to]);
            } else {
                fd.push(["create_date", "<=", `${params.date_to} 23:59:59`]);
            }
        }
        if (chartData.action_model === "crm.lead") {
            fd.push(["type", "=", "lead"]);
        }
        if (params.team_id && chartData.action_model === "crm.lead") {
            fd.push(["team_id", "=", parseInt(params.team_id, 10)]);
        }
        if (params.sales_rep_id && chartData.action_model === "crm.lead") {
            fd.push(["user_id", "=", parseInt(params.sales_rep_id, 10)]);
        }
        if (params.sales_rep_id && chartData.action_model === "bid.proposal") {
            fd.push(["sales_user_id", "=", parseInt(params.sales_rep_id, 10)]);
        }
        if (params.industry && chartData.action_model === "bid.proposal") {
            fd.push(["project_id.industry", "=", params.industry]);
        }
        if (params.emirate && chartData.action_model === "bid.proposal") {
            fd.push(["project_id.emirate", "=", params.emirate]);
        }
        if (chartData.action_model === "bid.project") {
            if (params.industry) {
                fd.push(["industry", "=", params.industry]);
            }
            if (params.emirate) {
                fd.push(["emirate", "=", params.emirate]);
            }
            if (params.outcome_status) {
                fd.push(["outcome_status", "=", params.outcome_status]);
            }
            if (params.sales_rep_id) {
                fd.push(["sales_rep", "=", parseInt(params.sales_rep_id, 10)]);
            }
        }
        if (this.state.activeTab === "enquiries" && chartData.action_model === "bid.project") {
            const e = this.state.enquiryFilters;
            if (e.outcome_status) {
                fd.push(["outcome_status", "=", e.outcome_status]);
            }
            if (e.review_status) {
                fd.push(["review_status", "=", e.review_status]);
            }
            if (e.decision_final) {
                fd.push(["decision_final", "=", e.decision_final]);
            }
            if (e.industry) {
                fd.push(["industry", "=", e.industry]);
            }
            if (e.emirate) {
                fd.push(["emirate", "=", e.emirate]);
            }
            if (e.stage_id) {
                fd.push(["stage_id", "=", parseInt(e.stage_id, 10)]);
            }
            if (e.sales_rep_id) {
                fd.push(["sales_rep", "=", parseInt(e.sales_rep_id, 10)]);
            }
            if (e.project_lead_id) {
                fd.push(["project_lead_id", "=", parseInt(e.project_lead_id, 10)]);
            }
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            name: chartData.title,
            res_model: chartData.action_model,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: fd.concat(domain),
        });
    }

    getVariance(current, previous) {
        if (!previous || previous === 0) {
            return 0;
        }
        return ((current - previous) / previous) * 100;
    }
}

registry.category("actions").add("sales_bid_board_unified_analytics", BidBoardUnifiedAnalytics);
