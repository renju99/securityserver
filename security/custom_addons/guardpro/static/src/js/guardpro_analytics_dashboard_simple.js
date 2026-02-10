/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";
import { loadBundle } from "@web/core/assets";

class GuardProAnalyticsDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        // Try to get user service, but don't fail if it's not available
        this.user = null;
        try {
            this.user = useService("user");
        } catch (e) {
            console.warn("User service not available, will use fallback for PDF export");
        }
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
                client_ids: [],
                period: 'last_30_days'
            },
            filterOptions: {
                sites: [],
                guards: [],
                clients: [],
                allGuards: [] // Store all guards for cascading filter
            }
        });

        onWillStart(async () => {
            // Load Chart.js bundle before loading data
            await loadBundle("web.chartjs_lib");
            // Wait for Chart to be available (Odoo's bundle makes it global)
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
        
        // Make Chart available in current scope
        if (typeof Chart === 'undefined') {
            window.Chart = window.Chart;
        }
    }

    async exportPDF() {
        try {
            // Prepare filter parameters
            const filterParams = {
                date_from: this.state.filters.date_from,
                date_to: this.state.filters.date_to,
                site_ids: this.state.filters.site_ids,
                guard_ids: this.state.filters.guard_ids,
                client_ids: this.state.filters.client_ids,
                period: this.state.filters.period
            };

            // Get or create dashboard - ensure we have at least one dashboard record
            let dashboard = [];
            
            // Try to get current user's dashboard first
            dashboard = await this.orm.searchRead(
                'guardpro.analytics.dashboard',
                [],
                ['id'],
                { limit: 1 }
            );
            
            // If no dashboard exists, create one
            let dashboardId;
            if (!dashboard || dashboard.length === 0) {
                const newDashboardId = await this.orm.create(
                    'guardpro.analytics.dashboard',
                    {
                        name: 'Sentry Analytics',
                    }
                );
                // Odoo ORM create returns the ID directly
                dashboardId = newDashboardId;
            } else {
                dashboardId = dashboard[0].id;
            }
            
            // Get site names for display in PDF
            let siteNames = [];
            if (filterParams.site_ids && filterParams.site_ids.length > 0) {
                try {
                    const sites = await this.orm.searchRead(
                        'client.site',
                        [['id', 'in', filterParams.site_ids]],
                        ['name']
                    );
                    siteNames = sites.map(s => s.name);
                } catch (e) {
                    console.warn("Could not fetch site names:", e);
                }
            }
            
            // Store filter params in dashboard record for PDF generation
            await this.orm.write(
                'guardpro.analytics.dashboard',
                [dashboardId],
                {
                    date_from: filterParams.date_from,
                    date_to: filterParams.date_to
                }
            );
            
            // Call the report action with proper data structure
            // Pass filters via context which is accessible in QWeb templates
            const reportAction = {
                type: 'ir.actions.report',
                report_name: 'guardpro.report_analytics_dashboard_pdf',
                report_type: 'qweb-pdf',
                res_ids: [dashboardId],
                context: {
                    active_id: dashboardId,
                    active_ids: [dashboardId],
                    filter_params: filterParams,
                    filters: {
                        ...filterParams,
                        site_names: siteNames
                    }
                },
                data: {
                    filters: {
                        ...filterParams,
                        site_names: siteNames
                    }
                }
            };
            
            await this.action.doAction(reportAction);
        } catch (error) {
            console.error("Error exporting PDF:", error);
            alert("Failed to export PDF: " + (error.message || error));
        }
    }

    async loadFilterOptions() {
        try {
            console.log("Loading filter options...");
            // Load sites - try without status filter first
            let sites = [];
            try {
                sites = await this.orm.searchRead(
                    'client.site',
                    [],
                    ['id', 'name', 'code'],
                    { limit: 1000 }
                );
                console.log("Sites search result (no filter):", sites ? sites.length : 0, sites);
            } catch (e) {
                console.error("Error searching sites without filter:", e);
            }
            // If no results, try with active status
            if (!sites || sites.length === 0) {
                try {
                    sites = await this.orm.searchRead(
                        'client.site',
                        [['status', '=', 'active']],
                        ['id', 'name', 'code'],
                        { limit: 1000 }
                    );
                    console.log("Sites search result (active filter):", sites ? sites.length : 0);
                } catch (e) {
                    console.error("Error searching sites with active filter:", e);
                }
            }
            this.state.filterOptions.sites = sites || [];
            console.log("Loaded sites:", sites ? sites.length : 0, sites);
            // Force reactivity update by reassigning
            this.state.filterOptions = {
                ...this.state.filterOptions,
                sites: sites || []
            };
            if (!sites || sites.length === 0) {
                console.warn("WARNING: No sites loaded. Check database and access rights.");
            }

            // Load all guards - try without status filter first
            let guards = [];
            try {
                guards = await this.orm.searchRead(
                    'guard.profile',
                    [],
                    ['id', 'name', 'badge_number', 'site_ids', 'user_id'],
                    { limit: 1000 }
                );
                console.log("Guards search result (no filter):", guards ? guards.length : 0);
            } catch (e) {
                console.error("Error searching guards without filter:", e);
            }
            // If no results, try with active status
            if (!guards || guards.length === 0) {
                try {
                    guards = await this.orm.searchRead(
                        'guard.profile',
                        [['status', '=', 'active']],
                        ['id', 'name', 'badge_number', 'site_ids', 'user_id'],
                        { limit: 1000 }
                    );
                    console.log("Guards search result (active filter):", guards ? guards.length : 0);
                } catch (e) {
                    console.error("Error searching guards with active filter:", e);
                }
            }
            
            // Process guards to ensure site_ids is an array
            if (guards) {
                guards = guards.map(guard => ({
                    ...guard,
                    site_ids: Array.isArray(guard.site_ids) ? guard.site_ids : []
                }));
            }
            
            const processedGuards = guards || [];
            console.log("Loaded guards:", processedGuards.length, processedGuards);
            if (processedGuards.length > 0) {
                console.log("Sample guard:", processedGuards[0]);
            } else {
                console.warn("WARNING: No guards loaded. Check database and access rights.");
                // Try alternative search without status filter
                console.log("Attempting alternative guard search...");
                try {
                    const altGuards = await this.orm.searchRead(
                        'guard.profile',
                        [],
                        ['id', 'name', 'badge_number'],
                        { limit: 10 }
                    );
                    console.log("Alternative search found:", altGuards ? altGuards.length : 0, altGuards);
                    if (altGuards && altGuards.length > 0) {
                        processedGuards.push(...altGuards);
                    }
                } catch (e) {
                    console.error("Alternative search failed:", e);
                }
            }
            
            // Force reactivity update by reassigning
            this.state.filterOptions = {
                ...this.state.filterOptions,
                allGuards: processedGuards,
                guards: processedGuards
            };

            // Load clients
            let clients = [];
            try {
                clients = await this.orm.searchRead(
                    'res.partner',
                    [['is_company', '=', true]],
                    ['id', 'name'],
                    { limit: 1000 }
                );
                console.log("Clients search result:", clients ? clients.length : 0);
            } catch (e) {
                console.error("Error searching clients:", e);
            }
            const processedClients = clients || [];
            console.log("Loaded clients:", processedClients.length, processedClients);
            if (processedClients.length === 0) {
                console.warn("WARNING: No clients loaded. Check database and access rights.");
            }
            
            // Force reactivity update by reassigning
            this.state.filterOptions = {
                ...this.state.filterOptions,
                clients: processedClients
            };
        } catch (error) {
            console.error("Error loading filter options:", error);
            console.error("Error details:", error);
            this.state.error = "Failed to load filter options: " + (error.message || error);
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
                client_ids: this.state.filters.client_ids,
                period: this.state.filters.period
            };

            const data = await this.orm.call(
                'guardpro.analytics.dashboard',
                'get_dashboard_data',
                [null, {}, filterParams]
            );
            
            this.state.kpis = data.kpis || [];
            this.state.charts = data.charts || [];
            this.state.tables = data.tables || [];
            
            // Check for backend errors
            if (data.error) {
                console.error("Backend error:", data.error);
                this.state.error = "Backend error: " + data.error;
            }
        } catch (error) {
            console.error("Dashboard error:", error);
            this.state.error = "Failed to load dashboard data: " + (error.message || error);
        } finally {
            this.state.loading = false;
            // Re-render charts after loading completes and DOM updates
            if (this.state.charts.length > 0) {
                // Use requestAnimationFrame to ensure DOM is updated
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
            
            switch(value) {
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

    onMultiSelectChange(filterName, selectedIds) {
        const filteredIds = selectedIds
            .filter(id => id && id !== '' && !isNaN(id))
            .map(id => parseInt(id));
        this.state.filters[filterName] = filteredIds.length > 0 ? filteredIds : [];
        
        // Cascading filter: if sites are selected, filter guards to those sites
        if (filterName === 'site_ids') {
            if (filteredIds.length > 0) {
                this.updateGuardsBySites(filteredIds);
                // Clear guard filter if selected guards don't match filtered guards
                const filteredGuardIds = (this.state.filterOptions.guards || []).map(g => g.id);
                this.state.filters.guard_ids = this.state.filters.guard_ids.filter(id => 
                    filteredGuardIds.includes(id)
                );
            } else {
                // Reset guards when no sites selected
                this.state.filterOptions.guards = this.state.filterOptions.allGuards || [];
            }
        }
        
        this.loadData();
    }
    
    updateGuardsBySites(siteIds) {
        // Filter guards to only show those assigned to selected sites
        const allGuards = this.state.filterOptions.allGuards || [];
        const filteredGuards = allGuards.filter(guard => {
            if (!guard.site_ids || guard.site_ids.length === 0) {
                return false; // Guards without sites are filtered out
            }
            // Check if guard has any of the selected sites
            return guard.site_ids.some(siteId => siteIds.includes(siteId));
        });
        this.state.filterOptions.guards = filteredGuards;
        console.log(`Filtered guards: ${filteredGuards.length} out of ${allGuards.length} for sites:`, siteIds);
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
        
        // Reset guard options to show all guards
        this.state.filterOptions.guards = this.state.filterOptions.allGuards || [];
        
        this.loadData();
    }

    hasActiveFilters() {
        return this.state.filters.site_ids.length > 0 ||
               this.state.filters.guard_ids.length > 0 ||
               this.state.filters.client_ids.length > 0 ||
               this.state.filters.period !== 'last_30_days';
    }

    renderAllCharts() {
        // Destroy existing charts first
        Object.values(this.chartInstances).forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                try {
                    chart.destroy();
                } catch (e) {
                    console.warn("Error destroying chart:", e);
                }
            }
        });
        this.chartInstances = {};
        
        // Render charts immediately
        let renderedCount = 0;
        this.state.charts.forEach((chartData, index) => {
            if (this.renderChart(index, chartData)) {
                renderedCount++;
            }
        });
        
        // If some charts failed, retry with increasing delays
        if (renderedCount < this.state.charts.length) {
            console.log(`Only ${renderedCount} of ${this.state.charts.length} charts rendered. Retrying...`);
            
            // First retry after 300ms
            setTimeout(() => {
                this.state.charts.forEach((chartData, index) => {
                    if (!this.chartInstances[index]) {
                        this.renderChart(index, chartData);
                    }
                });
            }, 300);
            
            // Second retry after 600ms
            setTimeout(() => {
                this.state.charts.forEach((chartData, index) => {
                    if (!this.chartInstances[index]) {
                        this.renderChart(index, chartData);
                    }
                });
            }, 600);
        }
    }

    renderChart(index, chartData) {
        const canvas = document.getElementById(`chart_${index}`);
        if (!canvas) {
            console.warn(`Canvas chart_${index} not found in DOM - will retry later`);
            return false;
        }

        // Skip if already rendered
        if (this.chartInstances[index]) {
            console.log(`Chart ${index} already rendered, skipping`);
            return true;
        }

        const ctx = canvas.getContext('2d');
        
        // Ensure Chart.js is loaded (check both window.Chart and global Chart)
        const ChartLib = window.Chart || (typeof Chart !== 'undefined' ? Chart : null);
        if (!ChartLib) {
            console.error('Chart.js library not loaded');
            return false;
        }
        
        // Store chart instance
        try {
            const ChartLib = window.Chart || Chart;
            this.chartInstances[index] = new ChartLib(ctx, {
                type: chartData.type,
                data: {
                    labels: chartData.labels,
                    datasets: chartData.datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                        }
                    },
                    scales: (chartData.type === 'pie' || chartData.type === 'doughnut') ? {} : {
                        y: {
                            beginAtZero: true
                        }
                    }
                }
            });
            console.log(`Successfully rendered chart ${index} (${chartData.title})`);
            return true;
        } catch (e) {
            console.error(`Error rendering chart ${index}:`, e);
            return false;
        }
    }

    async onKPIClick(actionName) {
        if (!actionName) return;
        
        try {
            const action = await this.orm.call(
                'guardpro.analytics.dashboard',
                actionName,
                []
            );
            
            if (action && action.type) {
                this.action.doAction(action);
            }
        } catch (error) {
            console.error("Action error:", error);
        }
    }

    async onRefresh() {
        await this.loadData();
        if (!this.state.loading) {
            setTimeout(() => {
            this.renderAllCharts();
            }, 100);
        }
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
}

GuardProAnalyticsDashboard.template = "guardpro.AnalyticsDashboardClient";

registry.category("actions").add("guardpro_analytics_dashboard", GuardProAnalyticsDashboard);

