import React, { useState, useEffect, useCallback } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';

const LOC_LOG_LIMIT = 50;

const LocationLogsView = () => {
    const { user } = useAuthStore();
    const {
        locationLogs, setLocationLogs,
        locLogSearch, setLocLogSearch,
        locLogStartDate, setLocLogStartDate,
        locLogEndDate, setLocLogEndDate,
        locLogPage, setLocLogPage,
        locLogTotal, setLocLogTotal,
        locLogTotalPages, setLocLogTotalPages,
        locLogLoading, setLocLogLoading,
        locLogSelected, setLocLogSelected,
        locLogSelectAll, setLocLogSelectAll,
        fetchLocationLogs
    } = useDataStore();
    const { showToast, openConfirm, closeConfirm } = useUIStore();

    const [pendingSearch, setPendingSearch] = useState(locLogSearch);
    const [pendingStart, setPendingStart] = useState(locLogStartDate);
    const [pendingEnd, setPendingEnd] = useState(locLogEndDate);
    const [copied, setCopied] = useState<string | number | null>(null);

    const token = user?.token;

    const handleFetch = useCallback((page: number) => {
        if (!token) return;
        fetchLocationLogs(token, {
            page,
            limit: LOC_LOG_LIMIT,
            staffId: locLogSearch,
            startDate: locLogStartDate,
            endDate: locLogEndDate
        });
    }, [token, locLogSearch, locLogStartDate, locLogEndDate, fetchLocationLogs]);

    useEffect(() => {
        handleFetch(locLogPage);
    }, [locLogPage, handleFetch]);

    const handleApply = () => {
        setLocLogSearch(pendingSearch);
        setLocLogStartDate(pendingStart);
        setLocLogEndDate(pendingEnd);
        if (locLogPage === 1) {
            if (!token) return;
            fetchLocationLogs(token, {
                page: 1,
                limit: LOC_LOG_LIMIT,
                staffId: pendingSearch,
                startDate: pendingStart,
                endDate: pendingEnd
            });
        } else {
            setLocLogPage(1);
        }
    };

    const handleReset = () => {
        setPendingSearch(''); setLocLogSearch('');
        setPendingStart(''); setLocLogStartDate('');
        setPendingEnd(''); setLocLogEndDate('');
        if (locLogPage === 1) {
            if (!token) return;
            fetchLocationLogs(token, {
                page: 1,
                limit: LOC_LOG_LIMIT,
                staffId: '',
                startDate: '',
                endDate: ''
            });
        } else {
            setLocLogPage(1);
        }
    };

    const handleSelectAll = () => {
        if (locLogSelectAll) {
            setLocLogSelected([]);
            setLocLogSelectAll(false);
        } else {
            setLocLogSelected(locationLogs.map(l => l.id));
            setLocLogSelectAll(true);
        }
    };

    const handleSelectRow = (id: string | number) => {
        setLocLogSelected(prev =>
            (typeof prev === 'function' ? (prev as any)(locLogSelected) : prev).includes(id)
                ? (typeof prev === 'function' ? (prev as any)(locLogSelected) : prev).filter((x: any) => x !== id)
                : [...(typeof prev === 'function' ? (prev as any)(locLogSelected) : prev), id]
        );
        setLocLogSelectAll(false);
    };

    const handleDeleteSingle = (id: string | number) => {
        openConfirm({
            title: 'Delete Log Entry',
            message: 'Are you sure you want to delete this coordinate log? This cannot be undone.',
            confirmText: 'Delete',
            type: 'danger',
            onConfirm: async () => {
                if (!token) return;
                try {
                    const res = await fetch(`/api/hr/location-logs/${id}`, {
                        method: 'DELETE',
                        headers: { 'Authorization': `Bearer ${token}` }
                    });
                    if (res.ok) {
                        showToast('Log entry deleted', 'success');
                        handleFetch(locLogPage);
                        closeConfirm();
                    } else {
                        showToast('Failed to delete log', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    const handleBulkDelete = () => {
        if (locLogSelected.length === 0) { showToast('No rows selected', 'warning'); return; }
        openConfirm({
            title: `Delete ${locLogSelected.length} Log(s)`,
            message: `This will permanently delete ${locLogSelected.length} coordinate log entry(ies). Are you sure?`,
            confirmText: 'Delete All',
            type: 'danger',
            onConfirm: async () => {
                if (!token) return;
                try {
                    const res = await fetch('/api/hr/location-logs', {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({ ids: locLogSelected })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message, 'success');
                        handleFetch(locLogPage);
                        closeConfirm();
                    } else {
                        showToast(data.error || 'Failed to delete', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    const handleDeleteFiltered = () => {
        const filtersActive = locLogSearch || locLogStartDate || locLogEndDate;
        const msg = filtersActive
            ? `This will delete ALL location logs matching your current filters. Are you sure?`
            : `This will delete ALL location logs currently in the system. Are you sure?`;

        openConfirm({
            title: 'Delete All Filtered Logs',
            message: msg,
            confirmText: 'Delete Everything',
            type: 'danger',
            onConfirm: async () => {
                if (!token) return;
                try {
                    const res = await fetch('/api/hr/location-logs', {
                        method: 'DELETE',
                        headers: {
                            'Authorization': `Bearer ${token}`,
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            staffId: locLogSearch,
                            startDate: locLogStartDate,
                            endDate: locLogEndDate
                        })
                    });
                    const data = await res.json();
                    if (res.ok) {
                        showToast(data.message, 'success');
                        handleFetch(1);
                        closeConfirm();
                    } else {
                        showToast(data.error || 'Failed to delete', 'error');
                    }
                } catch {
                    showToast('Network error', 'error');
                }
            }
        });
    };

    const handleCopyCoords = (lat: string, lng: string, id: string | number) => {
        navigator.clipboard.writeText(`${lat}, ${lng}`).then(() => {
            setCopied(id);
            setTimeout(() => setCopied(null), 1500);
        });
    };

    const fmt = (ts: string) => {
        if (!ts) return '—';
        const d = new Date(ts);
        return `${d.toLocaleDateString()} ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}`;
    };

    return (
        <div className="logs-container" style={{ padding: '1.5rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1.25rem', flexWrap: 'wrap', gap: '0.75rem' }}>
                <div>
                    <h2 style={{ margin: 0, fontSize: '1.5rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        📍 Staff Coordinate Logs
                    </h2>
                    <p style={{ margin: '0.2rem 0 0', color: '#64748b', fontSize: '0.875rem' }}>
                        {locLogTotal.toLocaleString()} total pings recorded
                    </p>
                </div>
                <div style={{ display: 'flex', gap: '0.75rem', alignItems: 'center' }}>
                    {locLogSelected.length > 0 && user?.role === 'HR Admin' && (
                        <button className="hr-btn danger" onClick={handleBulkDelete}>
                            🗑 Delete Selected ({locLogSelected.length})
                        </button>
                    )}
                    {user?.role === 'HR Admin' && (
                        <button className="hr-btn danger-outline" onClick={handleDeleteFiltered}>
                            🧹 Clear All Filtered
                        </button>
                    )}
                    <button
                        className="hr-btn secondary"
                        onClick={() => handleFetch(locLogPage)}
                        disabled={locLogLoading}
                    >
                        {locLogLoading ? '⏳ Loading…' : '🔄 Refresh'}
                    </button>
                </div>
            </div>

            <div style={{
                background: '#f8fafc', borderRadius: '12px', border: '1px solid #e2e8f0',
                padding: '1rem 1.25rem', marginBottom: '1.25rem',
                display: 'flex', flexWrap: 'wrap', gap: '0.75rem', alignItems: 'flex-end'
            }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 180px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Staff ID / Name</label>
                    <input
                        type="text"
                        placeholder="e.g. ST001"
                        value={pendingSearch}
                        onChange={e => setPendingSearch(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleApply()}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 160px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Date From</label>
                    <input
                        type="datetime-local"
                        value={pendingStart}
                        onChange={e => setPendingStart(e.target.value)}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', flex: '1 1 160px' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#475569' }}>Date To</label>
                    <input
                        type="datetime-local"
                        value={pendingEnd}
                        onChange={e => setPendingEnd(e.target.value)}
                        style={{
                            padding: '0.5rem 0.75rem', borderRadius: '8px',
                            border: '1px solid #cbd5e1', fontSize: '0.875rem',
                            outline: 'none', background: '#fff'
                        }}
                    />
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', paddingBottom: '1px' }}>
                    <button className="hr-btn primary" onClick={handleApply}>
                        Apply
                    </button>
                    <button className="hr-btn secondary" onClick={handleReset}>
                        Reset
                    </button>
                </div>
            </div>

            <div style={{
                background: '#fff', borderRadius: '12px', border: '1px solid #e2e8f0',
                overflow: 'hidden', boxShadow: '0 1px 3px rgba(0,0,0,0.06)'
            }}>
                {locLogLoading ? (
                    <div style={{ padding: '4rem', textAlign: 'center', color: '#94a3b8' }}>
                        <div style={{ fontSize: '2rem', marginBottom: '0.75rem' }}>⏳</div>
                        Loading coordinate logs…
                    </div>
                ) : locationLogs.length === 0 ? (
                    <div style={{ padding: '4rem', textAlign: 'center', color: '#94a3b8' }}>
                        <div style={{ fontSize: '2.5rem', marginBottom: '0.75rem' }}>📭</div>
                        <div style={{ fontWeight: 600, color: '#475569' }}>No logs found</div>
                        <div style={{ fontSize: '0.875rem', marginTop: '0.25rem' }}>Try adjusting the filters above</div>
                    </div>
                ) : (
                    <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                            <thead>
                                <tr style={{ background: '#f1f5f9', borderBottom: '1px solid #e2e8f0' }}>
                                    {user?.role === 'HR Admin' && (
                                        <th style={{ padding: '0.75rem 1rem', textAlign: 'center', width: '40px' }}>
                                            <input
                                                type="checkbox"
                                                checked={locLogSelectAll}
                                                onChange={handleSelectAll}
                                                style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                                            />
                                        </th>
                                    )}
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>#</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Staff Member</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Latitude</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Longitude</th>
                                    <th style={{ padding: '0.75rem 1rem', textAlign: 'left', fontWeight: 700, color: '#334155' }}>Timestamp</th>
                                    {user?.role === 'HR Admin' && (
                                        <th style={{ padding: '0.75rem 1rem', textAlign: 'center', fontWeight: 700, color: '#334155' }}>Action</th>
                                    )}
                                </tr>
                            </thead>
                            <tbody>
                                {locationLogs.map((log, idx) => {
                                    const isSelected = locLogSelected.includes(log.id);
                                    const rowNum = (locLogPage - 1) * LOC_LOG_LIMIT + idx + 1;
                                    return (
                                        <tr
                                            key={log.id}
                                            style={{
                                                borderBottom: '1px solid #f1f5f9',
                                                background: isSelected ? '#eff6ff' : (idx % 2 === 0 ? '#fff' : '#fafafa'),
                                                transition: 'background 0.15s'
                                            }}
                                        >
                                            {user?.role === 'HR Admin' && (
                                                <td style={{ padding: '0.65rem 1rem', textAlign: 'center' }}>
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => handleSelectRow(log.id)}
                                                        style={{ width: '16px', height: '16px', cursor: 'pointer' }}
                                                    />
                                                </td>
                                            )}
                                            <td style={{ padding: '0.65rem 1rem', color: '#94a3b8', fontVariantNumeric: 'tabular-nums' }}>{rowNum}</td>
                                            <td style={{ padding: '0.65rem 1rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <div style={{
                                                        width: '30px', height: '30px', borderRadius: '50%',
                                                        background: 'linear-gradient(135deg,#3b82f6,#2563eb)',
                                                        color: '#fff', display: 'flex', alignItems: 'center',
                                                        justifyContent: 'center', fontWeight: 700, fontSize: '0.75rem',
                                                        flexShrink: 0
                                                    }}>
                                                        {(log.first_name || log.staff_id || '?')[0].toUpperCase()}
                                                    </div>
                                                    <div>
                                                        <div style={{ fontWeight: 600, color: '#1e293b' }}>
                                                            {log.first_name || log.last_name
                                                                ? `${log.first_name || ''} ${log.last_name || ''}`.trim()
                                                                : 'Unnamed'}
                                                        </div>
                                                        <div style={{ fontSize: '0.75rem', color: '#64748b' }}>{log.staff_id}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem', fontFamily: 'monospace', color: '#0f172a' }}>
                                                {parseFloat(log.latitude).toFixed(6)}
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem', fontFamily: 'monospace', color: '#0f172a' }}>
                                                {parseFloat(log.longitude).toFixed(6)}
                                            </td>
                                            <td style={{ padding: '0.65rem 1rem' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                                    <button
                                                        onClick={() => handleCopyCoords(
                                                            parseFloat(log.latitude).toFixed(6),
                                                            parseFloat(log.longitude).toFixed(6),
                                                            log.id
                                                        )}
                                                        title="Copy coordinates"
                                                        style={{
                                                            background: 'none', border: 'none', cursor: 'pointer',
                                                            padding: '2px 4px', borderRadius: '4px',
                                                            color: copied === log.id ? '#10b981' : '#94a3b8',
                                                            fontSize: '0.85rem', flexShrink: 0
                                                        }}
                                                    >
                                                        {copied === log.id ? '✓' : '⎘'}
                                                    </button>
                                                    <span style={{ color: '#475569' }}>{fmt(log.timestamp)}</span>
                                                </div>
                                            </td>
                                            {user?.role === 'HR Admin' && (
                                                <td style={{ padding: '0.65rem 1rem', textAlign: 'center' }}>
                                                    <button
                                                        className="hr-btn danger-outline sm"
                                                        onClick={() => handleDeleteSingle(log.id)}
                                                        title="Delete this log"
                                                    >
                                                        🗑 Delete
                                                    </button>
                                                </td>
                                            )}
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>

            {locLogTotalPages > 1 && (
                <div style={{
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                    marginTop: '1rem', flexWrap: 'wrap', gap: '0.5rem'
                }}>
                    <span style={{ fontSize: '0.875rem', color: '#64748b' }}>
                        Showing {((locLogPage - 1) * LOC_LOG_LIMIT) + 1}–{Math.min(locLogPage * LOC_LOG_LIMIT, locLogTotal)} of {locLogTotal.toLocaleString()} entries
                    </span>
                    <div style={{ display: 'flex', gap: '0.4rem' }}>
                        <button
                            disabled={locLogPage <= 1}
                            onClick={() => setLocLogPage(locLogPage - 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0', background: locLogPage <= 1 ? '#f1f5f9' : '#fff',
                                color: locLogPage <= 1 ? '#94a3b8' : '#334155',
                                cursor: locLogPage <= 1 ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >
                            ‹ Prev
                        </button>
                        <button
                            disabled={locLogPage >= locLogTotalPages}
                            onClick={() => setLocLogPage(locLogPage + 1)}
                            style={{
                                padding: '0.4rem 0.9rem', borderRadius: '6px',
                                border: '1px solid #e2e8f0', background: locLogPage >= locLogTotalPages ? '#f1f5f9' : '#fff',
                                color: locLogPage >= locLogTotalPages ? '#94a3b8' : '#334155',
                                cursor: locLogPage >= locLogTotalPages ? 'not-allowed' : 'pointer',
                                fontWeight: 600, fontSize: '0.875rem'
                            }}
                        >
                            Next ›
                        </button>
                    </div>
                </div>
            )}
        </div>
    );
};

export default LocationLogsView;