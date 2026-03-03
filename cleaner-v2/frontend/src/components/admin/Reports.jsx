import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Filter, Eye, RefreshCw } from 'lucide-react';
import Modal from './Modal';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

const Reports = () => {
    const [reports, setReports] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filter, setFilter] = useState({ status: '', search: '' });
    const [showFilter, setShowFilter] = useState(false);
    const [detailReport, setDetailReport] = useState(null);
    const [detailLoading, setDetailLoading] = useState(false);

    const fetchReports = async () => {
        setLoading(true);
        try {
            const res = await axios.get('/api/reports', { headers: authHeader() });
            setReports(res.data);
        } catch (err) {
            console.error('Error fetching reports:', err);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchReports(); }, []);

    const filtered = reports.filter(r => {
        if (filter.status && r.status !== filter.status) return false;
        if (filter.search) {
            const q = filter.search.toLowerCase();
            if (!(r.washroom_name || '').toLowerCase().includes(q) &&
                !(r.employee_name || '').toLowerCase().includes(q) &&
                !(r.checklist_type || '').toLowerCase().includes(q)) return false;
        }
        return true;
    });

    const handleExportCsv = () => {
        const headers = ['Date', 'Washroom', 'Checklist Type', 'Staff', 'Completed', 'Total', 'Status'];
        const rows = filtered.map(r => [
            r.date ? new Date(r.date).toLocaleString() : '',
            r.washroom_name || '',
            r.checklist_type || '',
            r.employee_name || '',
            r.items_completed ?? '',
            r.items_total ?? '',
            r.status || ''
        ]);
        const csv = [headers.join(','), ...rows.map(row => row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `reports-${new Date().toISOString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    };

    const handleViewDetail = async (id) => {
        setDetailLoading(true);
        setDetailReport(null);
        try {
            const res = await axios.get(`/api/reports/${id}`, { headers: authHeader() });
            setDetailReport(res.data);
        } catch (err) {
            console.error('Error fetching report detail:', err);
        } finally {
            setDetailLoading(false);
        }
    };

    const handleExportOne = (r) => {
        const headers = ['Date', 'Washroom', 'Checklist Type', 'Staff', 'Completed', 'Total', 'Status'];
        const row = [r.date ? new Date(r.date).toLocaleString() : '', r.washroom_name || '', r.checklist_type || '', r.employee_name || '', r.items_completed ?? '', r.items_total ?? '', r.status || ''];
        const csv = [headers.join(','), row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `report-${r.id}-${(r.date || '').toString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    };

    return (
        <div className="fade-in">
            <header className="content-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <h1>Reports & Logs</h1>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <button className="btn btn-secondary" onClick={() => setShowFilter(!showFilter)} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Filter size={18} /> Filter
                    </button>
                    <button className="btn btn-secondary" onClick={fetchReports} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <RefreshCw size={18} /> Refresh
                    </button>
                    <button className="btn btn-primary" onClick={handleExportCsv} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                        <Download size={18} /> Export CSV
                    </button>
                </div>
            </header>

            {showFilter && (
                <div className="card glass" style={{ marginBottom: '1.5rem', padding: '1rem', display: 'flex', flexWrap: 'wrap', gap: '1rem', alignItems: 'flex-end' }}>
                    <div>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>Status</label>
                        <select value={filter.status} onChange={e => setFilter(f => ({ ...f, status: e.target.value }))} style={{ padding: '0.5rem 0.8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'white' }}>
                            <option value="">All</option>
                            <option value="completed">Completed</option>
                            <option value="pending">Pending</option>
                        </select>
                    </div>
                    <div>
                        <label style={{ fontSize: '0.8rem', color: 'var(--text-muted)', display: 'block', marginBottom: '0.3rem' }}>Search (location / staff)</label>
                        <input type="text" placeholder="Search..." value={filter.search} onChange={e => setFilter(f => ({ ...f, search: e.target.value }))} style={{ padding: '0.5rem 0.8rem', borderRadius: '8px', background: 'rgba(255,255,255,0.07)', border: '1px solid rgba(255,255,255,0.12)', color: 'white', minWidth: '180px' }} />
                    </div>
                </div>
            )}

            <div className="table-wrapper card glass shadow" style={{ padding: '0', overflowX: 'auto' }}>
                {loading ? (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading reports...</div>
                ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                        <thead>
                            <tr style={{ background: 'rgba(255, 255, 255, 0.05)' }}>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Date</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Washroom</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Checklist Type</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Staff</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Done</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Status</th>
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Actions</th>
                            </tr>
                        </thead>
                        <tbody>
                            {filtered.map(item => (
                                <tr key={item.id} style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.05)' }}>
                                    <td style={{ padding: '1rem' }}>{item.date ? new Date(item.date).toLocaleString() : '—'}</td>
                                    <td style={{ padding: '1rem' }}>{item.washroom_name || '—'}</td>
                                    <td style={{ padding: '1rem' }}><span style={{ color: 'var(--primary)', fontWeight: '600' }}>{item.checklist_type || '—'}</span></td>
                                    <td style={{ padding: '1rem' }}>{item.employee_name || '—'}</td>
                                    <td style={{ padding: '1rem' }}>{item.items_completed ?? 0}/{item.items_total ?? 0}</td>
                                    <td style={{ padding: '1rem' }}>
                                        <span style={{ background: item.status === 'completed' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)', color: item.status === 'completed' ? 'var(--success)' : 'var(--warning)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                                            {item.status || '—'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem', display: 'flex', gap: '0.5rem' }}>
                                        <button type="button" className="btn btn-secondary" style={{ padding: '0.5rem' }} title="View detail" onClick={() => handleViewDetail(item.id)}><Eye size={14} /></button>
                                        <button type="button" className="btn btn-secondary" style={{ padding: '0.5rem' }} title="Export row" onClick={() => handleExportOne(item)}><Download size={14} /></button>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                )}
                {!loading && filtered.length === 0 && (
                    <div style={{ padding: '3rem', textAlign: 'center', color: 'var(--text-muted)' }}>No reports match your criteria.</div>
                )}
            </div>

            <Modal
                show={detailReport !== null || detailLoading}
                onClose={() => setDetailReport(null)}
                maxWidth={520}
            >
                {detailLoading ? (
                    <div style={{ padding: '2rem', textAlign: 'center', color: 'var(--text-muted)' }}>Loading...</div>
                ) : detailReport ? (
                    <>
                        <h2 style={{ marginBottom: '1rem' }}>Report #{detailReport.id}</h2>
                        <p style={{ color: 'var(--text-muted)', fontSize: '0.9rem', marginBottom: '1rem' }}>
                            {detailReport.washroom_name} · {detailReport.employee_name} · {detailReport.date ? new Date(detailReport.date).toLocaleString() : ''}
                        </p>
                        <p style={{ marginBottom: '1rem' }}><strong>Checklist:</strong> {detailReport.checklist_type}</p>
                        {detailReport.lines?.length > 0 && (
                            <div style={{ marginTop: '1rem' }}>
                                <div style={{ fontSize: '0.75rem', fontWeight: '700', color: 'var(--text-muted)', marginBottom: '0.5rem' }}>Items</div>
                                <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                                    {detailReport.lines.map((line, i) => (
                                        <li key={i} style={{ padding: '0.4rem 0', borderBottom: '1px solid rgba(255,255,255,0.06)', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                                            {line.checked ? <span style={{ color: 'var(--success)' }}>✓</span> : <span style={{ color: 'var(--text-muted)' }}>○</span>}
                                            {line.item_name || line.category}
                                        </li>
                                    ))}
                                </ul>
                            </div>
                        )}
                    </>
                ) : null}
            </Modal>
        </div>
    );
};

export default Reports;
