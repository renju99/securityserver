import React, { useState, useEffect, useMemo } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';

const isSameLocalDay = (iso: string | undefined | null, dayStr: string) => {
    if (!iso || !dayStr) return false;
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return false;
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}` === dayStr;
};

const localTodayStr = () => {
    const d = new Date();
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
};

export type GeoFenceAlertsViewProps = {
    onOpenMap?: (lat: number, lng: number, staffId: string) => void;
};

const GeoFenceAlertsView: React.FC<GeoFenceAlertsViewProps> = ({ onOpenMap }) => {
    const { user } = useAuthStore();
    const {
        sites, geoFenceAlerts, fetchAlerts,
        gfPage, setGfPage, gfTotal, gfTotalPages,
        gfLoading, gfSearch, setGfSearch,
        gfSiteFilter, setGfSiteFilter,
        gfStatusFilter, setGfStatusFilter,
        gfStartDate, setGfStartDate,
        gfEndDate, setGfEndDate,
        GF_LIMIT
    } = useDataStore();
    const { showToast } = useUIStore();

    const [selectedAlerts, setSelectedAlerts] = useState<number[]>([]);
    const [selectAll, setSelectAll] = useState(false);

    useEffect(() => {
        if (user?.token) {
            fetchAlerts(user.token, gfPage);
        }
    }, [gfPage, gfStatusFilter, gfSiteFilter, user?.token]);

    const handleSearch = () => {
        if (user?.token) {
            setGfPage(1);
            fetchAlerts(user.token, 1);
        }
    };

    const handleResolve = async (alertId: number) => {
        if (!user?.token) return;
        try {
            const res = await fetch(`/hr/alerts/${alertId}/resolve`, {
                method: 'PATCH',
                headers: { 'Authorization': `Bearer ${user.token}` }
            });
            if (!res.ok) throw new Error();
            showToast('Alert marked as resolved', 'success');
            fetchAlerts(user.token, gfPage);
        } catch {
            showToast('Failed to resolve alert', 'error');
        }
    };

    const handleBulkResolve = async () => {
        if (selectedAlerts.length === 0 || !user?.token) return;
        try {
            const res = await fetch('/hr/alerts/bulk-resolve', {
                method: 'PATCH',
                headers: {
                    'Authorization': `Bearer ${user.token}`,
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ ids: selectedAlerts })
            });
            if (!res.ok) throw new Error();
            showToast(`${selectedAlerts.length} alerts resolved`, 'success');
            setSelectedAlerts([]);
            setSelectAll(false);
            fetchAlerts(user.token, gfPage);
        } catch {
            showToast('Failed to bulk resolve alerts', 'error');
        }
    };

    const handleToggleAll = () => {
        if (selectAll) {
            setSelectedAlerts([]);
            setSelectAll(false);
        } else {
            setSelectedAlerts(geoFenceAlerts.map(a => a.id));
            setSelectAll(true);
        }
    };

    const handleToggleRow = (id: number) => {
        setSelectedAlerts(prev =>
            prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
        );
        setSelectAll(false);
    };

    const exportCSV = () => {
        if (geoFenceAlerts.length === 0) return;
        const rows = [
            ['Staff ID', 'Name', 'Site', 'Coordinates', 'Message', 'Time', 'Status'].join(',')
        ];
        geoFenceAlerts.forEach(a => {
            rows.push([
                a.staff_id,
                `"${a.first_name || ''} ${a.last_name || ''}"`,
                `"${a.site_name || ''}"`,
                `"${a.latitude}, ${a.longitude}"`,
                `"${a.message || ''}"`,
                new Date(a.created_at).toLocaleString(),
                a.status
            ].join(','));
        });
        const blob = new Blob([rows.join('\n')], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `GeoFence_Alerts_${new Date().toISOString().split('T')[0]}.csv`;
        link.click();
    };

    const unresolvedCount = geoFenceAlerts.filter(a => a.status === 'active').length;
    const formatDateTime = (ts: string) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
    };

    const todayStr = localTodayStr();
    const todayActiveSorted = useMemo(() => {
        return geoFenceAlerts
            .filter((a) => a.status === 'active' && isSameLocalDay(a.created_at, todayStr))
            .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
    }, [geoFenceAlerts, todayStr]);

    const applyTodayFilter = () => {
        setGfStartDate(todayStr);
        setGfEndDate(todayStr);
        setGfStatusFilter('active');
        setGfPage(1);
        if (user?.token) fetchAlerts(user.token, 1);
    };

    return (
        <div className="management-view" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.5rem', flexWrap: 'wrap', gap: '1rem' }}>
                <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem', marginBottom: '0.25rem' }}>
                        <h2 style={{ margin: 0, fontSize: '1.4rem', fontWeight: 700, color: '#1e293b' }}>Geo Fence Alerts</h2>
                        {unresolvedCount > 0 && (
                            <span style={{
                                background: '#FF5E89', color: '#fff', borderRadius: '999px',
                                padding: '0.15rem 0.6rem', fontSize: '0.75rem', fontWeight: 700
                            }}>{unresolvedCount} active</span>
                        )}
                    </div>
                    <p style={{ margin: 0, color: '#64748b', fontSize: '0.875rem' }}>
                        Staff detected outside their assigned site geofence. {gfTotal > 0 ? `${gfTotal} total alerts.` : ''}
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem' }}>
                    {selectedAlerts.length > 0 && (
                        <button className="hr-btn success" onClick={handleBulkResolve}>
                            ✔ Resolve Selected ({selectedAlerts.length})
                        </button>
                    )}
                    <button className="hr-btn secondary" onClick={exportCSV}>↓ Export CSV</button>
                </div>
            </div>

            {todayActiveSorted.length > 0 && (
                <div style={{
                    marginBottom: '1rem',
                    padding: '1rem 1.1rem',
                    borderRadius: '12px',
                    border: '1px solid #fecaca',
                    background: 'linear-gradient(135deg, #fff1f2 0%, #fff 100%)',
                }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
                        <div>
                            <strong style={{ color: '#9f1239' }}>Today’s active exceptions ({todayActiveSorted.length})</strong>
                            <div style={{ fontSize: '0.82rem', color: '#64748b', marginTop: '4px' }}>
                                Same-day open alerts — handle these first, then review the full list below.
                            </div>
                        </div>
                        <button type="button" className="hr-btn secondary sm" onClick={applyTodayFilter}>
                            Filter list to today (active)
                        </button>
                    </div>
                    <div style={{ marginTop: '0.75rem', display: 'grid', gap: '0.5rem' }}>
                        {todayActiveSorted.slice(0, 6).map((alert) => (
                            <div key={`td-${alert.id}`} style={{
                                display: 'flex', flexWrap: 'wrap', alignItems: 'center', justifyContent: 'space-between',
                                gap: '0.5rem', padding: '0.5rem 0.65rem', background: '#fff', borderRadius: '8px', border: '1px solid #fecdd3',
                                fontSize: '0.82rem'
                            }}>
                                <span><strong>{alert.staff_id}</strong>{(alert.first_name || alert.last_name) ? ` · ${[alert.first_name, alert.last_name].filter(Boolean).join(' ')}` : ''} · {alert.site_name || 'Site'}</span>
                                <span style={{ color: '#64748b' }}>{formatDateTime(alert.created_at)}</span>
                                <div style={{ display: 'flex', gap: '0.35rem', flexWrap: 'wrap' }}>
                                    {onOpenMap && alert.latitude != null && alert.longitude != null && (
                                        <button
                                            type="button"
                                            className="hr-btn secondary sm"
                                            onClick={() => onOpenMap(Number(alert.latitude), Number(alert.longitude), String(alert.staff_id))}
                                        >
                                            Live Map
                                        </button>
                                    )}
                                    {alert.status !== 'resolved' && (
                                        <button type="button" className="hr-btn success sm" onClick={() => handleResolve(alert.id)}>Resolve</button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            <div style={{
                display: 'flex', flexWrap: 'wrap', gap: '0.75rem',
                background: '#fff', border: '1px solid #e2e8f0',
                borderRadius: '10px', padding: '1rem', marginBottom: '1.25rem'
            }}>
                <input
                    placeholder="Search by Staff ID…"
                    value={gfSearch}
                    onChange={e => setGfSearch(e.target.value)}
                    onKeyDown={e => e.key === 'Enter' && handleSearch()}
                    style={{ flex: '1 1 160px', padding: '0.5rem 0.75rem', borderRadius: '7px', border: '1px solid #e2e8f0', fontSize: '0.875rem' }}
                />
                {user?.role === 'HR Admin' && (
                    <select
                        value={gfSiteFilter}
                        onChange={e => setGfSiteFilter(e.target.value)}
                        style={{ flex: '1 1 160px', padding: '0.5rem 0.75rem', borderRadius: '7px', border: '1px solid #e2e8f0', fontSize: '0.875rem' }}
                    >
                        <option value="">All Sites</option>
                        {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                )}
                <select
                    value={gfStatusFilter}
                    onChange={e => setGfStatusFilter(e.target.value)}
                    style={{ flex: '1 1 130px', padding: '0.5rem 0.75rem', borderRadius: '7px', border: '1px solid #e2e8f0', fontSize: '0.875rem' }}
                >
                    <option value="">All Statuses</option>
                    <option value="active">Active</option>
                    <option value="resolved">Resolved</option>
                </select>
                <input type="date" value={gfStartDate} onChange={e => setGfStartDate(e.target.value)} style={{ flex: '1 1 140px', padding: '0.5rem 0.75rem', borderRadius: '7px', border: '1px solid #e2e8f0', fontSize: '0.875rem' }} />
                <input type="date" value={gfEndDate} onChange={e => setGfEndDate(e.target.value)} style={{ flex: '1 1 140px', padding: '0.5rem 0.75rem', borderRadius: '7px', border: '1px solid #e2e8f0', fontSize: '0.875rem' }} />
                <button className="hr-btn primary" onClick={handleSearch}>Search</button>
                <button
                    className="hr-btn secondary"
                    onClick={() => {
                        setGfSearch(''); setGfSiteFilter(''); setGfStatusFilter('');
                        setGfStartDate(''); setGfEndDate('');
                        setGfPage(1);
                        if (user?.token) fetchAlerts(user.token, 1);
                    }}
                >Clear</button>
            </div>

            <div style={{ background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0', overflow: 'hidden' }}>
                {gfLoading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: '#94a3b8' }}>Loading alerts…</div>
                ) : geoFenceAlerts.length === 0 ? (
                    <div style={{ padding: '3rem', textAlign: 'center' }}>
                        <div style={{ fontSize: '2.5rem', marginBottom: '0.5rem' }}>—</div>
                        <div style={{ fontWeight: 600, color: '#334155' }}>No geo-fence alerts match your filters</div>
                        <div style={{ color: '#94a3b8', fontSize: '0.875rem', marginTop: '0.35rem', maxWidth: '420px', margin: '0.35rem auto 0' }}>
                            {user?.role === 'Site Supervisor'
                                ? 'Try clearing dates to see the full history for your site, or check back after shift start when geofence monitoring is active.'
                                : 'Try widening the date range or clearing filters. When everyone stays inside their sites, this list stays empty.'}
                        </div>
                    </div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
                                <th style={{ padding: '0.75rem 1rem', width: '40px' }}><input type="checkbox" checked={selectAll} onChange={handleToggleAll} /></th>
                                {['Staff', 'Site', 'Coordinates', 'Message', 'Time', 'Status', 'Action'].map(h => (
                                    <th key={h} style={{ padding: '0.75rem 1rem', textAlign: 'left', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.06em', textTransform: 'uppercase', color: '#64748b' }}>{h}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {geoFenceAlerts.map((alert) => (
                                <tr key={alert.id} style={{ borderBottom: '1px solid #f1f5f9', background: selectedAlerts.includes(alert.id) ? '#f0f7ff' : (alert.status === 'resolved' ? '#fafafa' : '#fff') }}>
                                    <td style={{ padding: '0.75rem 1rem' }}>
                                        <input type="checkbox" checked={selectedAlerts.includes(alert.id)} onChange={() => handleToggleRow(alert.id)} />
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        <div style={{ fontWeight: 600, color: '#1e293b', fontSize: '0.875rem' }}>{alert.staff_id}</div>
                                        {(alert.first_name || alert.last_name) && <div style={{ color: '#64748b', fontSize: '0.78rem' }}>{[alert.first_name, alert.last_name].filter(Boolean).join(' ')}</div>}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#334155', fontSize: '0.875rem' }}>{alert.site_name || '—'}</td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#64748b', fontSize: '0.78rem', fontFamily: 'monospace' }}>
                                        {alert.latitude && alert.longitude ? `${parseFloat(String(alert.latitude)).toFixed(5)}, ${parseFloat(String(alert.longitude)).toFixed(5)}` : '—'}
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#475569', fontSize: '0.82rem', maxWidth: '280px' }}>{alert.message}</td>
                                    <td style={{ padding: '0.85rem 1rem', color: '#64748b', fontSize: '0.82rem', whiteSpace: 'nowrap' }}>{formatDateTime(alert.created_at)}</td>
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        <span style={{
                                            display: 'inline-block', padding: '0.2rem 0.6rem', borderRadius: '999px', fontSize: '0.72rem', fontWeight: 700,
                                            background: alert.status === 'resolved' ? '#dcfce7' : '#fee2e2', color: alert.status === 'resolved' ? '#16a34a' : '#dc2626'
                                        }}>{alert.status === 'resolved' ? 'Resolved' : 'Active'}</span>
                                    </td>
                                    <td style={{ padding: '0.85rem 1rem' }}>
                                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.35rem' }}>
                                            {onOpenMap && alert.latitude != null && alert.longitude != null && (
                                                <button
                                                    type="button"
                                                    className="hr-btn secondary sm"
                                                    onClick={() => onOpenMap(Number(alert.latitude), Number(alert.longitude), String(alert.staff_id))}
                                                >
                                                    Live Map
                                                </button>
                                            )}
                                            {alert.status !== 'resolved' && <button className="hr-btn success sm" onClick={() => handleResolve(alert.id)}>Resolve</button>}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
            </div>

            {gfTotalPages > 1 && (
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b' }}>Showing {((gfPage - 1) * GF_LIMIT) + 1}–{Math.min(gfPage * GF_LIMIT, gfTotal)} of {gfTotal.toLocaleString()} alerts</span>
                    <div className="mgmt-pagination" style={{ justifyContent: 'flex-end' }}>
                        <button className="hr-btn secondary sm" disabled={gfPage <= 1} onClick={() => setGfPage(p => p - 1)}>‹ Prev</button>
                        <span style={{ padding: '0.35rem 0.75rem', borderRadius: '6px', background: 'var(--primary)', color: '#fff', fontWeight: 700, fontSize: '0.8125rem' }}>{gfPage} / {gfTotalPages}</span>
                        <button className="hr-btn secondary sm" disabled={gfPage >= gfTotalPages} onClick={() => setGfPage(p => p + 1)}>Next ›</button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default GeoFenceAlertsView;
