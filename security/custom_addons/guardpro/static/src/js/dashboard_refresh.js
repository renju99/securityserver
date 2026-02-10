/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * GuardPro Dashboard Auto-Refresh Component
 * Provides real-time data updates for the dashboard
 */
class DashboardRefresh extends Component {
    static props = {
        "*": true,  // Accept any props (flexible component)
    };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        
        // Auto-refresh every 30 seconds
        this.refreshInterval = setInterval(() => {
            this.refreshDashboard();
        }, 30000);
        
        // Cleanup on unmount
        this.onWillUnmount(() => {
            if (this.refreshInterval) {
                clearInterval(this.refreshInterval);
            }
        });
    }
    
    async refreshDashboard() {
        try {
            // Reload the current view to get fresh data
            await this.action.doAction({
                type: 'ir.actions.client',
                tag: 'reload',
            });
        } catch (error) {
            console.error('Dashboard refresh failed:', error);
        }
    }
    
    async manualRefresh() {
        this.notification.add("Refreshing dashboard...", {
            type: "info",
        });
        
        await this.refreshDashboard();
        
        this.notification.add("Dashboard refreshed successfully!", {
            type: "success",
        });
    }
}

DashboardRefresh.template = "guardpro.DashboardRefresh";

registry.category("actions").add("guardpro_dashboard_refresh", DashboardRefresh);

