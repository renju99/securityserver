/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

class SalesBidBoardDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartInstances = {};

        const today = new Date();
        const last30 = new Date();
        last30.setDate(today.getDate() - 30);

        this.state = useState({
            loading: true,
            error: null,
            kpis: [],
            charts: [],
            tables: [],
            filters: {
                date_from: last30.toISOString().split("T")[0],
                date_to: today.toISOString().split("T")[0],
                state: "",
                review_status: "",
                decision_final: "",
                industry: "",
                emirate: "",
                stage_id: "",
                sales_rep_id: "",
                project_lead_id: "",
            },
            filterOptions: {
                states: [],
                review_statuses: [],
                decisions: [],
                industries: [],
                emirates: [],
                stages: [],
                sales_reps: [],
                project_leads: [],
            },
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.loadData();
        });

        onMounted(() => {
            setTimeout(() => this.renderAllCharts(), 100);
        });
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("sales_bid_board.dashboard", "get_dashboard_data", [false, {}, this.state.filters]);
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            this.state.tables = data.tables || [];
            this.state.filterOptions = data.filter_options || this.state.filterOptions;
        } catch (error) {
            this.state.error = `Failed to load dashboard data: ${error.message || error}`;
        } finally {
            this.state.loading = false;
            setTimeout(() => this.renderAllCharts(), 100);
        }
    }

    onFilterChange(name, value) {
        this.state.filters[name] = value;
        this.loadData();
    }

    onDateChange(name, value) {
        this.state.filters[name] = value;
        this.loadData();
    }

    async exportPDF() {
        try {
            const action = await this.orm.call("sales_bid_board.dashboard", "action_print_dashboard_report", [this.state.filters]);
            if (action) {
                await this.action.doAction(action);
            }
        } catch (error) {
            this.state.error = `PDF export failed: ${error.message || error}`;
        }
    }

    async onKPIClick(actionName) {
        if (!actionName) return;
        const action = await this.orm.call("sales_bid_board.dashboard", actionName, [this.state.filters]);
        if (action) {
            await this.action.doAction(action);
        }
    }

    onRowClick(table, row) {
        if (!table.res_model || !row.id) return;
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: table.res_model,
            res_id: row.id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    renderAllCharts() {
        Object.values(this.chartInstances).forEach((chart) => {
            if (chart && typeof chart.destroy === "function") {
                chart.destroy();
            }
        });
        this.chartInstances = {};
        this.state.charts.forEach((chartData, index) => this.renderChart(index, chartData));
    }

    renderChart(index, chartData) {
        const canvas = document.getElementById(`sbb_chart_${index}`);
        const ChartLib = window.Chart;
        if (!canvas || !ChartLib) return;

        const ctx = canvas.getContext("2d");
        this.chartInstances[index] = new ChartLib(ctx, {
            type: chartData.type,
            data: { labels: chartData.labels, datasets: chartData.datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                onClick: (_, elements) => {
                    if (!elements || !elements.length) return;
                    this.onChartClick(chartData, elements[0].index);
                },
                plugins: { legend: { position: "top" } },
                scales: chartData.type === "pie" || chartData.type === "doughnut" ? {} : { y: { beginAtZero: true } },
            },
        });
    }

    async onChartClick(chartData, pointIndex) {
        if (!chartData.action_model || pointIndex < 0) return;
        const key = chartData.keys ? chartData.keys[pointIndex] : null;
        const domain = [];

        if (chartData.action_type === "many2one") {
            if (key) domain.push([chartData.action_domain_field, "=", parseInt(key, 10)]);
        } else if (chartData.action_type === "selection") {
            if (key) domain.push([chartData.action_domain_field, "=", key]);
        } else if (chartData.action_type === "date_period") {
            if (key) {
                domain.push([chartData.action_domain_field, "ilike", key]);
            }
        }

        const filterDomain = [];
        for (const [k, v] of Object.entries(this.state.filters)) {
            if (!v) continue;
            if (k === "date_from") filterDomain.push(["create_date", ">=", v]);
            else if (k === "date_to") filterDomain.push(["create_date", "<=", v]);
            else if (k === "sales_rep_id") filterDomain.push(["sales_rep", "=", parseInt(v, 10)]);
            else if (k === "project_lead_id") filterDomain.push(["project_lead_id", "=", parseInt(v, 10)]);
            else if (k === "stage_id") filterDomain.push(["stage_id", "=", parseInt(v, 10)]);
            else filterDomain.push([k, "=", v]);
        }

        this.action.doAction({
            type: "ir.actions.act_window",
            name: chartData.title,
            res_model: chartData.action_model,
            view_mode: "list,form",
            views: [[false, "list"], [false, "form"]],
            target: "current",
            domain: filterDomain.concat(domain),
        });
    }

    getVariance(current, previous) {
        if (!previous || previous === 0) return 0;
        return ((current - previous) / previous) * 100;
    }

    clearFilters() {
        const today = new Date();
        const last30 = new Date();
        last30.setDate(today.getDate() - 30);
        this.state.filters = {
            date_from: last30.toISOString().split("T")[0],
            date_to: today.toISOString().split("T")[0],
            state: "",
            review_status: "",
            decision_final: "",
            industry: "",
            emirate: "",
            stage_id: "",
            sales_rep_id: "",
            project_lead_id: "",
        };
        this.loadData();
    }
}

SalesBidBoardDashboard.template = xml`
<div class="o_sales_bid_dashboard p-3" style="height: calc(100vh - 110px); overflow-y: auto; overflow-x: hidden;">
    <div class="d-flex justify-content-between align-items-center mb-3 bg-primary text-white rounded p-3">
        <div>
            <h2 class="mb-1 text-white"><i class="fa fa-line-chart me-2"/>Sales Analytics Dashboard</h2>
            <div class="text-white" style="font-size: 13px; opacity: 0.9;">Executive insights across bid pipeline, value, outcomes, and delivery risk</div>
        </div>
        <div>
            <button class="btn btn-outline-light me-2" t-on-click="exportPDF" t-att-disabled="state.loading">
                <i class="fa fa-file-pdf-o me-1"/>Export PDF
            </button>
            <button class="btn btn-outline-light me-2" t-on-click="clearFilters" t-att-disabled="state.loading">
                <i class="fa fa-eraser me-1"/>Reset
            </button>
            <button class="btn btn-outline-light" t-on-click="loadData" t-att-disabled="state.loading">
                <i class="fa fa-refresh me-1"/>Refresh
            </button>
        </div>
    </div>
    <div class="card mb-3 shadow-sm">
        <div class="card-header"><i class="fa fa-filter me-2"/>Global Filters</div>
        <div class="card-body">
            <div class="row g-2">
                <div class="col-lg-2 col-md-4"><label class="form-label small">From</label><input type="date" class="form-control form-control-sm" t-att-value="state.filters.date_from" t-on-change="(ev) => this.onDateChange('date_from', ev.target.value)"/></div>
                <div class="col-lg-2 col-md-4"><label class="form-label small">To</label><input type="date" class="form-control form-control-sm" t-att-value="state.filters.date_to" t-on-change="(ev) => this.onDateChange('date_to', ev.target.value)"/></div>
                <div class="col-lg-2 col-md-4"><label class="form-label small">State</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('state', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.states" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.state === o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-3 col-md-6"><label class="form-label small">Review Status</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('review_status', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.review_statuses" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.review_status === o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-3 col-md-6"><label class="form-label small">Decision</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('decision_final', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.decisions" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.decision_final === o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-2 col-md-4"><label class="form-label small">Industry</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('industry', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.industries" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.industry === o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-2 col-md-4"><label class="form-label small">Emirate</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('emirate', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.emirates" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.emirate === o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-2 col-md-4"><label class="form-label small">Stage</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('stage_id', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.stages" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.stage_id == o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-3 col-md-6"><label class="form-label small">Sales Rep</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('sales_rep_id', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.sales_reps" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.sales_rep_id == o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-lg-3 col-md-6"><label class="form-label small">Project Lead</label><select class="form-select form-select-sm" t-on-change="(ev) => this.onFilterChange('project_lead_id', ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.project_leads" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.project_lead_id == o.value"><t t-esc="o.label"/></option></t></select></div>
            </div>
        </div>
    </div>
    <div t-if="state.loading" class="text-center py-5"><i class="fa fa-spinner fa-spin fa-3x text-primary"/></div>
    <div t-if="state.error and !state.loading" class="alert alert-danger"><t t-esc="state.error"/></div>
    <div t-if="!state.loading and !state.error">
        <div class="row g-3 mb-3">
            <t t-foreach="state.kpis" t-as="kpi" t-key="kpi.name">
                <div class="col-lg-2 col-md-4 col-sm-6">
                    <div class="card h-100 shadow-sm" t-on-click="() => kpi.action ? this.onKPIClick(kpi.action) : undefined">
                        <div class="card-body">
                            <div class="small text-muted mb-1"><t t-esc="kpi.name"/></div>
                            <div class="h4 mb-0"><t t-esc="kpi.value"/><t t-esc="kpi.suffix || ''"/></div>
                            <div class="small mt-1" t-att-class="this.getVariance(kpi.value, kpi.previous_value) >= 0 ? 'text-success' : 'text-danger'">
                                <i t-att-class="this.getVariance(kpi.value, kpi.previous_value) >= 0 ? 'fa fa-arrow-up me-1' : 'fa fa-arrow-down me-1'"/>
                                <t t-esc="Math.abs(this.getVariance(kpi.value, kpi.previous_value)).toFixed(1)"/>% vs previous
                            </div>
                        </div>
                    </div>
                </div>
            </t>
        </div>
        <div class="row g-3 mb-3">
            <t t-foreach="state.charts" t-as="chart" t-key="chart.title">
                <div class="col-lg-6">
                    <div class="card shadow-sm">
                        <div class="card-header bg-light"><t t-esc="chart.title"/></div>
                        <div class="card-body">
                            <div style="position: relative; height: 260px;">
                                <canvas t-attf-id="sbb_chart_{{chart_index}}"/>
                            </div>
                        </div>
                    </div>
                </div>
            </t>
        </div>
        <div class="row g-3">
            <t t-foreach="state.tables" t-as="table" t-key="table.title">
                <div class="col-12">
                    <div class="card shadow-sm">
                        <div class="card-header bg-light"><t t-esc="table.title"/></div>
                        <div class="card-body p-0">
                            <div class="table-responsive">
                                <table class="table table-sm table-hover mb-0">
                                    <thead class="table-light">
                                        <tr>
                                            <t t-foreach="table.columns" t-as="col" t-key="col"><th><t t-esc="col"/></th></t>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        <t t-if="table.rows and table.rows.length">
                                            <t t-foreach="table.rows" t-as="row" t-key="row.id">
                                                <tr t-on-click="() => this.onRowClick(table, row)" t-att-class="table.res_model ? 'cursor-pointer' : ''">
                                                    <t t-foreach="row.data" t-as="cell" t-key="cell_index"><td><t t-esc="cell"/></td></t>
                                                </tr>
                                            </t>
                                        </t>
                                        <t t-else=""><tr><td t-att-colspan="table.columns.length" class="text-center text-muted py-3">No data available</td></tr></t>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                </div>
            </t>
        </div>
    </div>
</div>`;
registry.category("actions").add("sales_bid_board_dashboard", SalesBidBoardDashboard);
