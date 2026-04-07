/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, onMounted, useState, xml } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

class SalespersonDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.charts = {};
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
                industry: "",
                emirate: "",
                state: "",
                sales_rep_id: "",
            },
            filterOptions: { industries: [], emirates: [], states: [], sales_reps: [] },
        });

        onWillStart(async () => {
            await loadBundle("web.chartjs_lib");
            await this.load();
        });
        onMounted(() => setTimeout(() => this.renderCharts(), 100));
    }

    async load() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("sales_bid_board.salesperson.dashboard", "get_dashboard_data", [false, {}, this.state.filters]);
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            this.state.tables = data.tables || [];
            this.state.filterOptions = data.filter_options || this.state.filterOptions;
        } catch (e) {
            this.state.error = e.message || String(e);
        } finally {
            this.state.loading = false;
            setTimeout(() => this.renderCharts(), 100);
        }
    }

    onFilter(name, value) {
        this.state.filters[name] = value;
        this.load();
    }

    renderCharts() {
        Object.values(this.charts).forEach((c) => c && c.destroy && c.destroy());
        this.charts = {};
        const ChartLib = window.Chart;
        if (!ChartLib) return;
        this.state.charts.forEach((cfg, i) => {
            const el = document.getElementById(`srep_chart_${i}`);
            if (!el) return;
            this.charts[i] = new ChartLib(el.getContext("2d"), {
                type: cfg.type,
                data: { labels: cfg.labels, datasets: cfg.datasets },
                options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { position: "top" } } },
            });
        });
    }
}

SalespersonDashboard.template = xml`
<div class="p-3" style="height: calc(100vh - 110px); overflow-y: auto;">
    <div class="d-flex justify-content-between align-items-center mb-3 bg-primary text-white rounded p-3">
        <div>
            <h2 class="mb-1 text-white"><i class="fa fa-user-circle me-2"/>Sales Person Analytics</h2>
            <div class="text-white" style="font-size:13px;opacity:0.9;">Performance, pipeline value, conversion trends by sales representative</div>
        </div>
        <button class="btn btn-outline-light" t-on-click="load" t-att-disabled="state.loading"><i class="fa fa-refresh me-1"/>Refresh</button>
    </div>

    <div class="card mb-3 shadow-sm">
        <div class="card-header"><i class="fa fa-filter me-2"/>Filters</div>
        <div class="card-body">
            <div class="row g-2">
                <div class="col-md-2"><label class="form-label small">From</label><input type="date" class="form-control form-control-sm" t-att-value="state.filters.date_from" t-on-change="(ev)=>this.onFilter('date_from',ev.target.value)"/></div>
                <div class="col-md-2"><label class="form-label small">To</label><input type="date" class="form-control form-control-sm" t-att-value="state.filters.date_to" t-on-change="(ev)=>this.onFilter('date_to',ev.target.value)"/></div>
                <div class="col-md-3"><label class="form-label small">Industry</label><select class="form-select form-select-sm" t-on-change="(ev)=>this.onFilter('industry',ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.industries" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.industry == o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-md-3"><label class="form-label small">Emirate</label><select class="form-select form-select-sm" t-on-change="(ev)=>this.onFilter('emirate',ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.emirates" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.emirate == o.value"><t t-esc="o.label"/></option></t></select></div>
                <div class="col-md-2"><label class="form-label small">State</label><select class="form-select form-select-sm" t-on-change="(ev)=>this.onFilter('state',ev.target.value)"><option value="">All</option><t t-foreach="state.filterOptions.states" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.state == o.value"><t t-esc="o.label"/></option></t></select></div>
            </div>
            <div class="row g-2 mt-2">
                <div class="col-md-6 col-lg-4"><label class="form-label small">Sales Rep</label><select class="form-select form-select-sm" t-on-change="(ev)=>this.onFilter('sales_rep_id',ev.target.value)"><option value="">All sales reps</option><t t-foreach="state.filterOptions.sales_reps" t-as="o" t-key="o.value"><option t-att-value="o.value" t-att-selected="state.filters.sales_rep_id == o.value"><t t-esc="o.label"/></option></t></select></div>
            </div>
        </div>
    </div>

    <div t-if="state.loading" class="text-center py-5"><i class="fa fa-spinner fa-spin fa-3x text-primary"/></div>
    <div t-if="state.error and !state.loading" class="alert alert-danger"><t t-esc="state.error"/></div>

    <div t-if="!state.loading and !state.error">
        <div class="row g-3 mb-3">
            <t t-foreach="state.kpis" t-as="kpi" t-key="kpi.name">
                <div class="col-lg-3 col-md-6"><div class="card shadow-sm"><div class="card-body"><div class="small text-muted"><t t-esc="kpi.name"/></div><div class="h4"><t t-esc="kpi.value"/><t t-esc="kpi.suffix || ''"/></div></div></div></div>
            </t>
        </div>
        <div class="row g-3 mb-3">
            <t t-foreach="state.charts" t-as="ch" t-key="ch.title">
                <div class="col-lg-6">
                    <div class="card shadow-sm">
                        <div class="card-header bg-light"><t t-esc="ch.title"/></div>
                        <div class="card-body"><div style="position:relative;height:280px;"><canvas t-attf-id="srep_chart_{{ch_index}}"/></div></div>
                    </div>
                </div>
            </t>
        </div>
        <t t-foreach="state.tables" t-as="tb" t-key="tb.title">
            <div class="card shadow-sm mb-3">
                <div class="card-header bg-light"><t t-esc="tb.title"/></div>
                <div class="table-responsive">
                    <table class="table table-sm table-hover mb-0">
                        <thead class="table-light"><tr><t t-foreach="tb.columns" t-as="c" t-key="c"><th><t t-esc="c"/></th></t></tr></thead>
                        <tbody><t t-foreach="tb.rows" t-as="r" t-key="r.id"><tr><t t-foreach="r.data" t-as="v" t-key="v_index"><td><t t-esc="v"/></td></t></tr></t></tbody>
                    </table>
                </div>
            </div>
        </t>
    </div>
</div>`;

registry.category("actions").add("sales_bid_board_salesperson_dashboard", SalespersonDashboard);
