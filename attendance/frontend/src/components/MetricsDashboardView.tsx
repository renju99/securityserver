import React, { useEffect, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';

type ApiLatencyRow = {
    route: string;
    method: string;
    count: number;
    errors: number;
    avgMs: number;
    maxMs: number;
    minMs: number;
    statusCodes: Record<string, number>;
};

type MetricsResponse = {
    counters: Record<string, number>;
    apiLatency: ApiLatencyRow[];
    generatedAt: string;
};

const cardStyle: React.CSSProperties = {
    background: '#fff',
    border: '1px solid #e2e8f0',
    borderRadius: '12px',
    padding: '1rem',
};

const MetricsDashboardView = () => {
    const user = useAuthStore((state) => state.user);
    const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const loadMetrics = async () => {
        if (!user?.token) return;
        setLoading(true);
        setError('');
        try {
            const res = await fetch('/api/hr/admin/metrics', {
                headers: { Authorization: `Bearer ${user.token}` }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load metrics');
            setMetrics(data);
        } catch (err: any) {
            setError(err.message || 'Failed to load metrics');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadMetrics();
    }, [user?.token]);

    return (
        <div className="management-view animate-fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
                <div>
                    <h2 style={{ margin: 0 }}>System Metrics</h2>
                    <p style={{ margin: '4px 0 0', color: '#64748b' }}>API latency and operational counters</p>
                </div>
                <button className="btn-secondary" onClick={loadMetrics} disabled={loading}>
                    {loading ? 'Refreshing...' : 'Refresh'}
                </button>
            </div>

            {error && <div style={{ color: '#b91c1c', marginBottom: '1rem' }}>{error}</div>}

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem', marginBottom: '1rem' }}>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>HTTP Requests</div>
                    <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{metrics?.counters?.http_requests_total || 0}</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Failed Check-ins</div>
                    <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{metrics?.counters?.failed_checkins_total || 0}</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Geo False Positives</div>
                    <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{metrics?.counters?.geofence_false_positives_total || 0}</div>
                </div>
                <div style={cardStyle}>
                    <div style={{ color: '#64748b', fontSize: '0.8rem' }}>Auto Checkouts</div>
                    <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>{metrics?.counters?.auto_checkout_total || 0}</div>
                </div>
            </div>

            <div className="mgmt-table-container">
                <table className="mgmt-table">
                    <thead>
                        <tr>
                            <th>Route</th>
                            <th>Count</th>
                            <th>Errors</th>
                            <th>Avg (ms)</th>
                            <th>Min (ms)</th>
                            <th>Max (ms)</th>
                        </tr>
                    </thead>
                    <tbody>
                        {(metrics?.apiLatency || []).slice(0, 50).map((row) => (
                            <tr key={`${row.method}-${row.route}`}>
                                <td><code>{row.method} {row.route}</code></td>
                                <td>{row.count}</td>
                                <td>{row.errors}</td>
                                <td>{row.avgMs}</td>
                                <td>{row.minMs}</td>
                                <td>{row.maxMs}</td>
                            </tr>
                        ))}
                        {(!metrics || !metrics.apiLatency || metrics.apiLatency.length === 0) && (
                            <tr>
                                <td colSpan={6} style={{ textAlign: 'center', color: '#94a3b8' }}>
                                    No latency data yet
                                </td>
                            </tr>
                        )}
                    </tbody>
                </table>
            </div>
            {metrics?.generatedAt && (
                <div style={{ marginTop: '0.75rem', color: '#64748b', fontSize: '0.8rem' }}>
                    Snapshot: {new Date(metrics.generatedAt).toLocaleString()}
                </div>
            )}
        </div>
    );
};

export default MetricsDashboardView;
