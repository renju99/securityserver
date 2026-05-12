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
                    const res = await fetch(`/hr/location-logs/${id}`, {
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
                    const res = await fetch('/hr/location-logs', {
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
                    const res = await fetch('/hr/location-logs', {
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
        <div className="logs-container">
            <div className="view-toolbar view-toolbar-spaced">
                <div>
                    <h2 className="location-title">
                        Staff Coordinate Logs
                    </h2>
                    <p className="location-subtitle">
                        {locLogTotal.toLocaleString()} total pings recorded
                    </p>
                </div>
                <div className="location-toolbar-actions">
                    {locLogSelected.length > 0 && user?.role === 'HR Admin' && (
                        <button className="hr-btn danger" onClick={handleBulkDelete}>
                            Delete Selected ({locLogSelected.length})
                        </button>
                    )}
                    {user?.role === 'HR Admin' && (
                        <button className="hr-btn danger-outline" onClick={handleDeleteFiltered}>
                            Clear All Filtered
                        </button>
                    )}
                    <button
                        className="hr-btn secondary"
                        onClick={() => handleFetch(locLogPage)}
                        disabled={locLogLoading}
                    >
                        {locLogLoading ? 'Loading…' : 'Refresh'}
                    </button>
                </div>
            </div>

            <div className="location-filter-panel">
                <div className="location-field">
                    <label>Staff ID / Name</label>
                    <input
                        type="text"
                        placeholder="e.g. ST001"
                        value={pendingSearch}
                        onChange={e => setPendingSearch(e.target.value)}
                        onKeyDown={e => e.key === 'Enter' && handleApply()}
                    />
                </div>

                <div className="location-field location-field-date">
                    <label>Date From</label>
                    <input
                        type="datetime-local"
                        value={pendingStart}
                        onChange={e => setPendingStart(e.target.value)}
                    />
                </div>

                <div className="location-field location-field-date">
                    <label>Date To</label>
                    <input
                        type="datetime-local"
                        value={pendingEnd}
                        onChange={e => setPendingEnd(e.target.value)}
                    />
                </div>

                <div className="location-filter-actions">
                    <button className="hr-btn primary" onClick={handleApply}>
                        Apply
                    </button>
                    <button className="hr-btn secondary" onClick={handleReset}>
                        Reset
                    </button>
                </div>
            </div>

            <div className="view-panel">
                {locLogLoading ? (
                    <div className="location-state">
                        <div className="location-state-mark">..</div>
                        Loading coordinate logs…
                    </div>
                ) : locationLogs.length === 0 ? (
                    <div className="location-state">
                        <div className="location-empty-mark">--</div>
                        <div className="location-empty-title">No logs found</div>
                        <div className="location-empty-sub">Try adjusting the filters above</div>
                    </div>
                ) : (
                    <div className="location-table-wrap">
                        <table className="location-table">
                            <thead>
                                <tr>
                                    {user?.role === 'HR Admin' && (
                                        <th className="compact-center">
                                            <input
                                                type="checkbox"
                                                checked={locLogSelectAll}
                                                onChange={handleSelectAll}
                                                className="control-checkbox"
                                            />
                                        </th>
                                    )}
                                    <th>#</th>
                                    <th>Staff Member</th>
                                    <th>Latitude</th>
                                    <th>Longitude</th>
                                    <th>Timestamp</th>
                                    {user?.role === 'HR Admin' && (
                                        <th className="compact-center">Action</th>
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
                                            className={isSelected ? 'location-row-selected' : idx % 2 === 0 ? '' : 'location-row-alt'}
                                        >
                                            {user?.role === 'HR Admin' && (
                                                <td className="compact-center">
                                                    <input
                                                        type="checkbox"
                                                        checked={isSelected}
                                                        onChange={() => handleSelectRow(log.id)}
                                                        className="control-checkbox"
                                                    />
                                                </td>
                                            )}
                                            <td className="row-number-cell">{rowNum}</td>
                                            <td>
                                                <div className="inline-flex-sm">
                                                    <div className="location-avatar">
                                                        {(log.first_name || log.staff_id || '?')[0].toUpperCase()}
                                                    </div>
                                                    <div>
                                                        <div className="staff-name">
                                                            {log.first_name || log.last_name
                                                                ? `${log.first_name || ''} ${log.last_name || ''}`.trim()
                                                                : 'Unnamed'}
                                                        </div>
                                                        <div className="staff-id-sub">{log.staff_id}</div>
                                                    </div>
                                                </div>
                                            </td>
                                            <td className="mono-cell">
                                                {parseFloat(log.latitude).toFixed(6)}
                                            </td>
                                            <td className="mono-cell">
                                                {parseFloat(log.longitude).toFixed(6)}
                                            </td>
                                            <td>
                                                <div className="inline-flex-sm">
                                                    <button
                                                        onClick={() => handleCopyCoords(
                                                            parseFloat(log.latitude).toFixed(6),
                                                            parseFloat(log.longitude).toFixed(6),
                                                            log.id
                                                        )}
                                                        title="Copy coordinates"
                                                        className={`location-copy-btn ${copied === log.id ? 'copied' : ''}`}
                                                    >
                                                        {copied === log.id ? 'Copied' : 'Copy'}
                                                    </button>
                                                    <span className="location-timestamp">{fmt(log.timestamp)}</span>
                                                </div>
                                            </td>
                                            {user?.role === 'HR Admin' && (
                                                <td className="compact-center">
                                                    <button
                                                        className="hr-btn danger-outline sm"
                                                        onClick={() => handleDeleteSingle(log.id)}
                                                        title="Delete this log"
                                                    >
                                                        Delete
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
                <div className="location-pagination">
                    <span className="location-pagination-text">
                        Showing {((locLogPage - 1) * LOC_LOG_LIMIT) + 1}–{Math.min(locLogPage * LOC_LOG_LIMIT, locLogTotal)} of {locLogTotal.toLocaleString()} entries
                    </span>
                    <div className="location-pagination-actions">
                        <button
                            disabled={locLogPage <= 1}
                            onClick={() => setLocLogPage(locLogPage - 1)}
                            className="hr-btn secondary sm"
                        >
                            ‹ Prev
                        </button>
                        <button
                            disabled={locLogPage >= locLogTotalPages}
                            onClick={() => setLocLogPage(locLogPage + 1)}
                            className="hr-btn secondary sm"
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