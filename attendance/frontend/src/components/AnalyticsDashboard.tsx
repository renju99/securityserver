import React from 'react';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { exportToCSV, formatDataForExport, formatSitesForExport } from '../utils/exportUtils';

const AnalyticsDashboard = () => {
    const {
        mgmtStats, onlineEmployees, sites, roles, mgmtUsers
    } = useDataStore();
    const { showToast } = useUIStore();

    return (
        <div className="management-view animate-fade-in">
            <div style={{ marginBottom: '2rem' }}>
                <h2 style={{ margin: 0, color: '#1e293b', fontSize: '1.75rem' }}>Analytics Overview</h2>
                <p style={{ margin: '0.5rem 0 0', color: '#64748b' }}>Comprehensive insights into your workforce and site operations</p>
            </div>

            <div className="analytics-modern-grid">
                <div className="analytics-modern-card blue">
                    <div className="card-content">
                        <span className="card-label">Total Staff</span>
                        <span className="card-value">{mgmtStats.total}</span>
                        <span className="card-subtext">Registered Employees</span>
                    </div>
                    <div className="card-decoration"></div>
                </div>

                <div className="analytics-modern-card green">
                    <div className="card-content">
                        <span className="card-label">Active Today</span>
                        <span className="card-value">{Object.keys(onlineEmployees).length}</span>
                        <span className="card-subtext">{Object.keys(onlineEmployees).length} Online Now</span>
                    </div>
                    <div className="card-decoration"></div>
                </div>

                <div className="analytics-modern-card orange">
                    <div className="card-content">
                        <span className="card-label">Total Sites</span>
                        <span className="card-value">{sites.length}</span>
                        <span className="card-subtext">Active Locations</span>
                    </div>
                    <div className="card-decoration"></div>
                </div>

                <div className="analytics-modern-card purple">
                    <div className="card-content">
                        <span className="card-label">Departments</span>
                        <span className="card-value">{new Set(mgmtUsers.map(u => u.department_name)).size}</span>
                        <span className="card-subtext">Functional Groups</span>
                    </div>
                    <div className="card-decoration"></div>
                </div>
            </div>

            <div className="analytics-detailed-sections">
                <div className="distribution-card">
                    <div className="dist-header">
                        <h3>Workforce Composition</h3>
                        <span>By Role</span>
                    </div>
                    <div className="dist-body">
                        {roles.map(role => {
                            const count = mgmtUsers.filter(u => u.role_name === role.name).length;
                            const percentage = mgmtStats.total > 0 ? ((count / mgmtStats.total) * 100).toFixed(1) : 0;
                            return (
                                <div key={role.id} className="dist-row">
                                    <div className="dist-info">
                                        <span className="dist-name">{role.name}</span>
                                        <span className="dist-count">{count}</span>
                                    </div>
                                    <div className="dist-progress-bg">
                                        <div className="dist-progress-fill" style={{ width: `${percentage}%`, background: 'var(--primary-color)' }}></div>
                                    </div>
                                    <span className="dist-percent">{percentage}%</span>
                                </div>
                            );
                        })}
                    </div>
                </div>

                <div className="distribution-card">
                    <div className="dist-header">
                        <h3>Site Allocation</h3>
                        <span>By Location</span>
                    </div>
                    <div className="dist-body">
                        {sites.slice(0, 5).map(site => {
                            const count = mgmtUsers.filter(u => u.site_id === site.id).length;
                            const percentage = mgmtStats.total > 0 ? ((count / mgmtStats.total) * 100).toFixed(1) : 0;
                            return (
                                <div key={site.id} className="dist-row">
                                    <div className="dist-info">
                                        <span className="dist-name">{site.name}</span>
                                        <span className="dist-count">{count}</span>
                                    </div>
                                    <div className="dist-progress-bg">
                                        <div className="dist-progress-fill" style={{ width: `${percentage}%`, background: '#f59e0b' }}></div>
                                    </div>
                                    <span className="dist-percent">{percentage}%</span>
                                </div>
                            );
                        })}
                        <div className="dist-row">
                            <div className="dist-info">
                                <span className="dist-name">Global / Others</span>
                                <span className="dist-count">{mgmtUsers.filter(u => !u.site_id || !sites.slice(0, 5).find(s => s.id === u.site_id)).length}</span>
                            </div>
                            <div className="dist-progress-bg">
                                <div className="dist-progress-fill" style={{ width: '0%', background: '#94a3b8' }}></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <div className="analytics-actions-bar">
                <div className="actions-text">
                    <h4>System Reports</h4>
                    <p>Export latest dataset for offline analysis</p>
                </div>
                <div className="actions-buttons">
                    <button
                        className="modern-action-btn"
                        onClick={() => {
                            const formattedData = formatDataForExport(mgmtUsers);
                            exportToCSV(formattedData, `staff_export_${new Date().toISOString().split('T')[0]}.csv`);
                            showToast('Staff data exported successfully', 'success');
                        }}
                    >
                        Employees CSV
                    </button>
                    <button
                        className="modern-action-btn secondary"
                        onClick={() => {
                            const formattedData = formatSitesForExport(sites);
                            exportToCSV(formattedData, `sites_export_${new Date().toISOString().split('T')[0]}.csv`);
                            showToast('Sites data exported successfully', 'success');
                        }}
                    >
                        Sites CSV
                    </button>
                </div>
            </div>
        </div>
    );
};

export default AnalyticsDashboard;