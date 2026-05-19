/**
 * GuardLink Dashboard Statistics Widget
 * Enhanced statistics and metrics for guards
 */

class DashboardStats {
    constructor(guardId) {
        this.guardId = guardId;
        this.stats = null;
        this.refreshInterval = null;
    }

    /**
     * Initialize dashboard stats
     */
    async init(container) {
        this.container = container;
        await this.loadStats();
        this.render();
        this.startAutoRefresh();
    }

    /**
     * Load statistics from server
     */
    async loadStats() {
        try {
            const response = await fetch('/guardpro/api/stats/dashboard', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    jsonrpc: '2.0',
                    method: 'call',
                    params: {
                        guard_id: this.guardId
                    }
                })
            });

            const result = await response.json();
            
            if (result.result && !result.result.error) {
                this.stats = result.result;
            } else {
                console.error('Dashboard stats API error:', result.result?.error || 'Unknown error');
                // Default stats if API fails
                this.stats = {
                    shifts_today: 0,
                    shifts_completed: 0,
                    completed_security_rounds: 0,
                    incidents_reported: 0,
                    hours_worked_week: 0,
                    performance_score: 0,
                    rounds_today: 0,
                    rounds_open: 0,
                    rounds_completed: 0,
                    rounds_expected: 0,
                    rounds_available: 0
                };
            }
        } catch (error) {
            console.error('Failed to load stats:', error);
            this.stats = {
                shifts_today: 0,
                shifts_completed: 0,
                completed_security_rounds: 0,
                incidents_reported: 0,
                hours_worked_week: 0,
                performance_score: 0,
                rounds_today: 0,
                rounds_open: 0,
                rounds_completed: 0,
                rounds_expected: 0,
                rounds_available: 0
            };
        }
    }

    /**
     * Render statistics grid
     */
    render() {
        if (!this.container || !this.stats) return;

        // Calculate progress percentage
        const roundsExpected = this.stats.rounds_expected || 0;
        const roundsCompleted = this.stats.rounds_completed || 0;
        const roundsOpen = this.stats.rounds_open || 0;
        const progressPercent = roundsExpected > 0 ? Math.round((roundsCompleted / roundsExpected) * 100) : 0;
        
        // Status color based on progress
        let progressColor = '#f44336'; // red
        if (progressPercent >= 80) progressColor = '#4caf50'; // green
        else if (progressPercent >= 50) progressColor = '#ff9800'; // orange
        
        const html = `
            <div class="rounds-overview-card">
                <h4 class="rounds-overview-title">
                    <i class="fa fa-map-signs"></i> Security Tours/Rounds Today
                </h4>
                <div class="rounds-progress-summary">
                    <div class="rounds-progress-bar-container">
                        <div class="rounds-progress-bar-fill" style="width: ${progressPercent}%; background-color: ${progressColor};">
                            ${progressPercent > 10 ? progressPercent + '%' : ''}
                        </div>
                        ${progressPercent <= 10 ? '<span class="rounds-progress-text">' + progressPercent + '%</span>' : ''}
                    </div>
                    <div class="rounds-summary-text">
                        <strong>${roundsCompleted}</strong> of <strong>${roundsExpected}</strong> tours completed
                        ${roundsOpen > 0 ? ` • <span class="text-info"><strong>${roundsOpen}</strong> tours in progress</span>` : ''}
                    </div>
                </div>
            </div>

            <div class="stats-grid">
                <div class="stat-box ${roundsExpected > 0 ? 'warning' : 'secondary'}">
                    <div class="stat-box-icon">
                        <i class="fa fa-clipboard-list"></i>
                    </div>
                    <div class="stat-box-value">${roundsExpected}</div>
                    <div class="stat-box-label">Tours Assigned</div>
                </div>

                <div class="stat-box ${roundsOpen > 0 ? 'info' : 'secondary'}">
                    <div class="stat-box-icon">
                        <i class="fa fa-map-signs"></i>
                    </div>
                    <div class="stat-box-value">${roundsOpen}</div>
                    <div class="stat-box-label">Tours In Progress</div>
                </div>

                <div class="stat-box ${roundsCompleted > 0 ? 'success' : 'secondary'}">
                    <div class="stat-box-icon">
                        <i class="fa fa-check-circle"></i>
                    </div>
                    <div class="stat-box-value">${roundsCompleted}</div>
                    <div class="stat-box-label">Tours Completed</div>
                </div>

                <div class="stat-box ${this.stats.incidents_reported > 0 ? 'danger' : 'secondary'}">
                    <div class="stat-box-icon">
                        <i class="fa fa-exclamation-triangle"></i>
                    </div>
                    <div class="stat-box-value">${this.stats.incidents_reported || 0}</div>
                    <div class="stat-box-label">Incidents</div>
                </div>
            </div>

            <div class="performance-widget">
                <h4><i class="fa fa-line-chart"></i> This Week's Performance</h4>
                <div class="performance-metrics">
                    <div class="performance-metric">
                        <span class="performance-metric-value">${this.stats.hours_worked_week || 0}</span>
                        <span class="performance-metric-label">Hours</span>
                    </div>
                    <div class="performance-metric">
                        <span class="performance-metric-value">${this.stats.performance_score || 0}%</span>
                        <span class="performance-metric-label">Score</span>
                    </div>
                    <div class="performance-metric">
                        <span class="performance-metric-value">${this.stats.punctuality || 100}%</span>
                        <span class="performance-metric-label">On-Time</span>
                    </div>
                </div>
            </div>
        `;

        this.container.innerHTML = html;
    }

    /**
     * Start auto-refresh every 5 minutes
     */
    startAutoRefresh() {
        // Clear existing interval if any
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        // Refresh every 5 minutes
        this.refreshInterval = setInterval(async () => {
            await this.loadStats();
            this.render();
        }, 5 * 60 * 1000);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Manual refresh
     */
    async refresh() {
        await this.loadStats();
        this.render();
    }

    /**
     * Force immediate refresh (e.g., after creating incident)
     */
    async forceRefresh() {
        console.log('Force refreshing dashboard stats...');
        await this.loadStats();
        this.render();
        
        // Dispatch event to notify other components
        window.dispatchEvent(new CustomEvent('dashboard-refreshed', {
            detail: { stats: this.stats }
        }));
    }
}

// Make available globally
window.DashboardStats = DashboardStats;

