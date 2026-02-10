/** @odoo-module **/

import { Component, useState, onWillStart, onMounted, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { loadBundle } from "@web/core/assets";

/**
 * KPI Card Widget Component
 */
export class KPICardWidget extends Component {
    static template = "guardpro.KPICardWidget";
    static props = {
        data: Object,
        onCardClick: { type: Function, optional: true }
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
    }

    get variance() {
        const current = this.props.data.value;
        const previous = this.props.data.previous_value;
        if (!previous || previous === 0) return 0;
        return ((current - previous) / previous * 100).toFixed(1);
    }

    get varianceClass() {
        const variance = parseFloat(this.variance);
        if (variance === 0) return 'text-muted';
        return variance >= 0 ? 'text-success' : 'text-danger';
    }

    get varianceIcon() {
        const variance = parseFloat(this.variance);
        if (variance === 0) return 'fa-minus';
        return variance >= 0 ? 'fa-arrow-up' : 'fa-arrow-down';
    }

    async onCardClick() {
        if (this.props.data.action && this.props.onCardClick) {
            await this.props.onCardClick(this.props.data.action);
        }
    }
}

/**
 * Chart Widget Component using Chart.js
 */
export class ChartWidget extends Component {
    static template = "guardpro.ChartWidget";
    static props = {
        data: Object
    };

    setup() {
        this.chartRef = useRef("chart");
        this.chartInstance = null;

        onWillStart(async () => {
            // Load Chart.js bundle before rendering
            await loadBundle("web.chartjs_lib");
            // Wait for Chart to be available
            await this.waitForChart();
        });

        onMounted(() => {
            this.renderChart();
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

    renderChart() {
        if (!this.chartRef.el) return;
        
        const ctx = this.chartRef.el.getContext('2d');
        
        // Ensure Chart.js is loaded
        const ChartLib = window.Chart || (typeof Chart !== 'undefined' ? Chart : null);
        if (!ChartLib) {
            console.error('Chart.js library not loaded');
            return;
        }
        
        // Destroy existing chart if any
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }

        // Create new chart
        this.chartInstance = new ChartLib(ctx, {
            type: this.props.data.type,
            data: {
                labels: this.props.data.labels,
                datasets: this.props.data.datasets
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: {
                            usePointStyle: true,
                            padding: 15
                        }
                    },
                    title: {
                        display: false
                    },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                    }
                },
                scales: this.props.data.type === 'pie' || this.props.data.type === 'doughnut' ? {} : {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            precision: 0
                        }
                    }
                }
            }
        });
    }

    willUnmount() {
        if (this.chartInstance) {
            this.chartInstance.destroy();
        }
    }
}

/**
 * Table Widget Component
 */
export class TableWidget extends Component {
    static template = "guardpro.TableWidget";
    static props = {
        data: Object
    };
}

/**
 * Main GuardPro Analytics Dashboard Controller
 */
export class GuardProAnalyticsDashboard extends Component {
    static template = "guardpro.DashboardView";
    static components = { KPICardWidget, ChartWidget, TableWidget };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        // Initialize filters with defaults
        const today = new Date();
        const last30Days = new Date();
        last30Days.setDate(today.getDate() - 30);
        
        this.state = useState({
            data: {
                kpis: [],
                charts: [],
                tables: []
            },
            loading: true,
            error: null,
            filters: {
                date_from: last30Days.toISOString().split('T')[0],
                date_to: today.toISOString().split('T')[0],
                site_ids: [],
                guard_ids: [],
                client_ids: [],
                period: 'last_30_days' // last_30_days, this_month, this_week, custom
            },
            filterOptions: {
                sites: [],
                guards: [],
                clients: []
            }
        });

        onWillStart(async () => {
            await this.loadFilterOptions();
            await this.loadDashboardData();
        });

        onMounted(() => {
            // Auto-refresh every 5 minutes
            this.refreshInterval = setInterval(() => {
                this.onRefresh();
            }, 300000); // 5 minutes
        });
    }

    async loadFilterOptions() {
        try {
            // Load sites
            const sites = await this.orm.searchRead(
                'client.site',
                [['status', '=', 'active']],
                { fields: ['id', 'name', 'code'], limit: 1000 }
            );
            this.state.filterOptions.sites = sites;

            // Load guards
            const guards = await this.orm.searchRead(
                'guard.profile',
                [['status', '=', 'active']],
                { fields: ['id', 'name', 'badge_number'], limit: 1000 }
            );
            this.state.filterOptions.guards = guards;

            // Load clients
            const clients = await this.orm.searchRead(
                'res.partner',
                [['is_company', '=', true]],
                { fields: ['id', 'name'], limit: 1000 }
            );
            this.state.filterOptions.clients = clients;
        } catch (error) {
            console.error("Error loading filter options:", error);
        }
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;
        
        try {
            const filterParams = {
                date_from: this.state.filters.date_from,
                date_to: this.state.filters.date_to,
                site_ids: this.state.filters.site_ids,
                guard_ids: this.state.filters.guard_ids,
                client_ids: this.state.filters.client_ids,
                period: this.state.filters.period
            };

            const data = await this.orm.call(
                'guardpro.analytics.dashboard',
                'get_dashboard_data',
                [],
                { filter_params: filterParams }
            );
            
            this.state.data = data;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.error = _t("Failed to load dashboard data. Please try again.");
        } finally {
            this.state.loading = false;
        }
    }

    onFilterChange(filterName, value) {
        this.state.filters[filterName] = value;
        
        // Auto-update date range based on period selection
        if (filterName === 'period' && value !== 'custom') {
            const today = new Date();
            let dateFrom = new Date();
            
            switch(value) {
                case 'today':
                    dateFrom = new Date(today);
                    break;
                case 'yesterday':
                    dateFrom = new Date(today);
                    dateFrom.setDate(dateFrom.getDate() - 1);
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
        
        // Reload dashboard data with new filters
        this.loadDashboardData();
    }

    onDateRangeChange(dateFrom, dateTo) {
        this.state.filters.date_from = dateFrom;
        this.state.filters.date_to = dateTo;
        this.state.filters.period = 'custom';
        this.loadDashboardData();
    }

    onMultiSelectChange(filterName, selectedIds) {
        // Filter out empty values and convert to integers
        const filteredIds = selectedIds
            .filter(id => id && id !== '' && !isNaN(id))
            .map(id => parseInt(id));
        
        // If no specific selection, clear the filter
        this.state.filters[filterName] = filteredIds.length > 0 ? filteredIds : [];
        this.loadDashboardData();
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
            client_ids: [],
            period: 'last_30_days'
        };
        
        this.loadDashboardData();
    }

    hasActiveFilters() {
        return this.state.filters.site_ids.length > 0 ||
               this.state.filters.guard_ids.length > 0 ||
               this.state.filters.client_ids.length > 0 ||
               this.state.filters.period !== 'last_30_days';
    }

    async onRefresh() {
        await this.loadDashboardData();
    }

    async onKPICardClick(actionName) {
        try {
            const action = await this.orm.call(
                'guardpro.analytics.dashboard',
                actionName,
                [[]]
            );
            
            if (action) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("Error executing action:", error);
        }
    }

    willUnmount() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }
}

/**
 * Register Dashboard as a Form Controller Extension
 */
export const guardProAnalyticsDashboard = {
    component: GuardProAnalyticsDashboard,
};

// Auto-initialize dashboard when form view loads
registry.category("public_components").add("GuardProAnalyticsDashboard", GuardProAnalyticsDashboard);

