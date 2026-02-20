/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

class GuardProToursDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.chartInstances = {}; // Store chart instances to destroy them later

        // Initialize filters with defaults
        const today = new Date();
        const last30Days = new Date();
        last30Days.setDate(today.getDate() - 30);

        this.state = useState({
            kpis: [],
            charts: [],
            tables: [],
            loading: true,
            error: null,
            filters: {
                date_from: last30Days.toISOString().split('T')[0],
                date_to: today.toISOString().split('T')[0],
                site_ids: [],
                guard_ids: [],
                period: 'last_30_days'
            },
            filterOptions: {
                sites: [],
                guards: [],
                allGuards: [] // Store all guards for cascading filter
            }
        });

        onWillStart(async () => {
            // Load Chart.js bundle before loading data
            await loadBundle("web.chartjs_lib");
            // Wait for Chart to be available
            await this.waitForChart();
            await this.loadFilterOptions();
            await this.loadData();
        });

        onMounted(() => {
            // Schedule chart rendering after DOM is fully ready
            setTimeout(() => {
                if (this.state.charts.length > 0) {
                    this.renderAllCharts();
                }
            }, 300);
        });
    }

    async waitForChart() {
        // Wait for Chart.js to be available (Odoo's bundle makes it global)
        let attempts = 0;
        const maxAttempts = 50; // 5 seconds max wait

        while (typeof window.Chart === 'undefined' && attempts < maxAttempts) {
            await new Promise(resolve => setTimeout(resolve, 100));
            attempts++;
        }

        if (typeof window.Chart === 'undefined') {
            console.error('Chart.js library failed to load after waiting');
            throw new Error('Chart.js library not available');
        }
    }

    async loadFilterOptions() {
        try {
            // Load sites
            const sites = await this.orm.searchRead(
                'client.site',
                [['status', '=', 'active']],
                ['id', 'name', 'code'],
                { limit: 1000 }
            );
            this.state.filterOptions.sites = sites || [];

            // Load guards
            const guards = await this.orm.searchRead(
                'guard.profile',
                [['status', '=', 'active']],
                ['id', 'name', 'badge_number', 'site_ids'],
                { limit: 1000 }
            );

            // Process guards to ensure site_ids is an array
            const processedGuards = (guards || []).map(guard => ({
                ...guard,
                site_ids: Array.isArray(guard.site_ids) ? guard.site_ids : []
            }));

            this.state.filterOptions.allGuards = processedGuards;
            this.state.filterOptions.guards = processedGuards;
        } catch (error) {
            console.error("Error loading filter options:", error);
        }
    }

    async loadData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            const filterParams = {
                date_from: this.state.filters.date_from,
                date_to: this.state.filters.date_to,
                site_ids: this.state.filters.site_ids,
                guard_ids: this.state.filters.guard_ids,
                period: this.state.filters.period
            };

            const data = await this.orm.call(
                'guardpro.tours.dashboard',
                'get_dashboard_data',
                [null, {}, filterParams]
            );

            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            this.state.tables = data.tables || [];

            if (data.error) {
                this.state.error = data.error;
            }
        } catch (error) {
            console.error("Dashboard error:", error);
            this.state.error = _t("Failed to load dashboard data. Please try again.");
        } finally {
            this.state.loading = false;
            // Re-render charts after loading completes
            if (this.state.charts.length > 0) {
                requestAnimationFrame(() => {
                    setTimeout(() => {
                        this.renderAllCharts();
                    }, 200);
                });
            }
        }
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;

        if (filterName === 'period' && value !== 'custom') {
            const today = new Date();
            let dateFrom = new Date();

            switch (value) {
                case 'today':
                    dateFrom = new Date(today);
                    this.state.filters.date_to = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    break;
                case 'yesterday':
                    dateFrom.setDate(today.getDate() - 1);
                    this.state.filters.date_to = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    break;
                case 'this_week':
                    const dayOfWeek = today.getDay();
                    dateFrom.setDate(today.getDate() - dayOfWeek);
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_to = today.toISOString().split('T')[0];
                    break;
                case 'this_month':
                    dateFrom = new Date(today.getFullYear(), today.getMonth(), 1);
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_to = today.toISOString().split('T')[0];
                    break;
                case 'last_30_days':
                    dateFrom.setDate(today.getDate() - 30);
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_to = today.toISOString().split('T')[0];
                    break;
                case 'last_7_days':
                    dateFrom.setDate(today.getDate() - 7);
                    this.state.filters.date_from = dateFrom.toISOString().split('T')[0];
                    this.state.filters.date_to = today.toISOString().split('T')[0];
                    break;
            }
        }

        this.loadData();
    }

    onDateRangeChange(dateFrom, dateTo) {
        this.state.filters.date_from = dateFrom;
        this.state.filters.date_to = dateTo;
        this.state.filters.period = 'custom';
        this.loadData();
    }

    async exportPDF() {
        try {
            this.state.loading = true;
            // Prepare filter parameters
            const filterParams = {
                date_from: this.state.filters.date_from,
                date_to: this.state.filters.date_to,
                site_ids: this.state.filters.site_ids,
                guard_ids: this.state.filters.guard_ids,
                period: this.state.filters.period
            };

            // Get or create dashboard record
            const userId = this.env.user ? this.env.user.userId : 1;
            const userName = this.env.user ? this.env.user.name : 'User';

            let dashboard = await this.orm.searchRead(
                'guardpro.tours.dashboard',
                [['user_id', '=', userId]],
                ['id'],
                { limit: 1 }
            );

            let dashboardId;
            if (!dashboard || dashboard.length === 0) {
                dashboardId = await this.orm.create(
                    'guardpro.tours.dashboard',
                    {
                        name: 'Tours Dashboard - ' + userName,
                        user_id: userId
                    }
                );
            } else {
                dashboardId = dashboard[0].id;
            }

            // Call the report action
            const reportAction = {
                type: 'ir.actions.report',
                report_name: 'guardpro.report_tours_dashboard_pdf',
                report_type: 'qweb-pdf',
                res_ids: [dashboardId],
                context: {
                    active_id: dashboardId,
                    active_ids: [dashboardId],
                    filter_params: filterParams
                },
                data: {
                    filters: filterParams
                }
            };

            await this.action.doAction(reportAction);
            this.state.loading = false;
        } catch (error) {
            this.state.loading = false;
            console.error("Error exporting PDF:", error);
            alert("Failed to export PDF: " + (error.message || error));
        }
    }

    onMultiSelectChange(filterName, selectedIds) {
        const filteredIds = selectedIds
            .filter(id => id && id !== '' && !isNaN(id))
            .map(id => parseInt(id));
        this.state.filters[filterName] = filteredIds.length > 0 ? filteredIds : [];

        // Cascading filter: sites -> guards
        if (filterName === 'site_ids') {
            if (filteredIds.length > 0) {
                const allGuards = this.state.filterOptions.allGuards || [];
                const filteredGuards = allGuards.filter(guard => {
                    if (!guard.site_ids || guard.site_ids.length === 0) return false;
                    return guard.site_ids.some(siteId => filteredIds.includes(siteId));
                });
                this.state.filterOptions.guards = filteredGuards;

                // Clear selected guards if they are no longer in the list
                const filteredGuardIds = filteredGuards.map(g => g.id);
                this.state.filters.guard_ids = this.state.filters.guard_ids.filter(id =>
                    filteredGuardIds.includes(id)
                );
            } else {
                this.state.filterOptions.guards = this.state.filterOptions.allGuards || [];
            }
        }

        this.loadData();
    }

    clearFilters() {
        const today = new Date();
        const last30Days = new Date();
        last30Days.setDate(today.getDate() - 30);

        this.state.filters = {
            date_from: last30Days.toISOString().split('T')[0],
            date_to: today.toISOString().split('T')[0],
            site_ids: [],
            guard_ids: [],
            period: 'last_30_days'
        };

        this.state.filterOptions.guards = this.state.filterOptions.allGuards || [];
        this.loadData();
    }

    hasActiveFilters() {
        return this.state.filters.site_ids.length > 0 ||
            this.state.filters.guard_ids.length > 0 ||
            this.state.filters.period !== 'last_30_days';
    }

    renderAllCharts() {
        // Destroy existing
        Object.values(this.chartInstances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                try { chart.destroy(); } catch (e) { }
            }
        });
        this.chartInstances = {};

        this.state.charts.forEach((chartData, index) => {
            this.renderChart(index, chartData);
        });
    }

    renderChart(index, chartData) {
        const canvas = document.getElementById(`tour_chart_${index}`);
        if (!canvas) return false;

        const ctx = canvas.getContext('2d');
        const ChartLib = window.Chart || (typeof Chart !== 'undefined' ? Chart : null);
        if (!ChartLib) return false;

        const self = this;

        try {
            this.chartInstances[index] = new ChartLib(ctx, {
                type: chartData.type,
                data: {
                    labels: chartData.labels,
                    datasets: chartData.datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    onClick: (e, elements) => {
                        if (elements && elements.length > 0) {
                            const dataIndex = elements[0].index;
                            self.onChartClick(chartData, dataIndex);
                        }
                    },
                    onHover: (event, chartElement) => {
                        event.native.target.style.cursor = chartElement[0] ? 'pointer' : 'default';
                    },
                    plugins: {
                        legend: { position: 'top' }
                    },
                    scales: (chartData.type === 'pie' || chartData.type === 'doughnut') ? {} : {
                        y: { beginAtZero: true }
                    }
                }
            });
            return true;
        } catch (e) {
            console.error(`Error rendering chart ${index}:`, e);
            return false;
        }
    }

    async onChartClick(chartData, index) {
        if (!chartData.action_model) return;

        let domain = [];

        // Add existing filters to domain
        if (this.state.filters.site_ids.length > 0) {
            domain.push(['site_id', 'in', this.state.filters.site_ids]);
        }
        if (this.state.filters.guard_ids.length > 0) {
            domain.push(['guard_id', 'in', this.state.filters.guard_ids]);
        }

        // Add chart-specific drill-down domain
        if (chartData.action_type === 'date_range' && chartData.keys && chartData.keys[index]) {
            // For date range charts (Trend Line)
            const dateRange = chartData.keys[index];
            if (dateRange && dateRange.start && dateRange.end) {
                domain.push(['start_time', '>=', dateRange.start]);
                domain.push(['start_time', '<=', dateRange.end]);
            }
        } else if (chartData.action_domain_field && chartData.keys && chartData.keys[index] !== undefined) {
            // For categorical charts (Pie, Doughnut, Bar)
            domain.push([chartData.action_domain_field, '=', chartData.keys[index]]);
        }

        // Execute action
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: chartData.action_model,
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
            domain: domain,
            name: `${chartData.title} - ${chartData.labels[index]}`
        });
    }

    onRowClick(resModel, resId) {
        if (!resModel || !resId) return;

        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: resModel,
            res_id: resId,
            views: [[false, 'form']],
            target: 'current'
        });
    }

    async onKPIClick(actionName) {
        if (!actionName) return;
        try {
            const action = await this.orm.call(
                'guardpro.tours.dashboard',
                actionName,
                []
            );
            if (action) this.action.doAction(action);
        } catch (error) {
            console.error("Action error:", error);
        }
    }

    async onRefresh() {
        await this.loadData();
    }

    getVariance(current, previous) {
        if (!previous || previous === 0) return 0;
        return ((current - previous) / previous * 100).toFixed(1);
    }

    getVarianceClass(current, previous) {
        const variance = parseFloat(this.getVariance(current, previous));
        if (variance === 0) return 'text-muted';
        return variance >= 0 ? 'text-success' : 'text-danger';
    }

    getVarianceIcon(current, previous) {
        const variance = parseFloat(this.getVariance(current, previous));
        if (variance === 0) return 'fa-minus';
        return variance >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
    }

    willUnmount() {
        Object.values(this.chartInstances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                try { chart.destroy(); } catch (e) { }
            }
        });
    }
}

GuardProToursDashboard.template = "guardpro.ToursDashboardClient";

registry.category("actions").add("guardpro_tours_dashboard", GuardProToursDashboard);
