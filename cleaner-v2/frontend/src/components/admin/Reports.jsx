import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Download, Filter, Eye, RefreshCw, FileText } from 'lucide-react';
import Modal from './Modal';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

// Labels matching backend checklist types (same as schedule options)
const CHECKLIST_TYPE_LABELS = {
    high_risk_hourly: 'High Risk – High Risk Checklist (Hourly)',
    daily_moderate: 'Moderate Risk – 24 Hour Checklist (Daily)',
    daily_low: 'Low Risk – 24 Hour Checklist (Daily)',
    daily_minimal: 'Minimal Risk – 24 Hour Checklist (Daily)',
    weekly_minimal: 'Minimal Risk – Weekly Checklist (Weekly)',
    weekly_moderate_residential: 'Moderate Risk – Residential (Weekend) Checklist (Weekly)',
};

const getChecklistTitle = (type) => CHECKLIST_TYPE_LABELS[type] || type || 'Cleaning Report';

const openPrintReport = (report) => {
    const title = getChecklistTitle(report.checklist_type);
    const dateStr = report.date ? new Date(report.date).toLocaleString('en-GB', { dateStyle: 'medium', timeStyle: 'short' }) : '';
    const lines = (report.lines || []).map((l) => ({
        name: l.item_name || l.category || 'Item',
        checked: !!l.checked,
        notes: l.notes || '',
    }));
    const html = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>${title}</title>
  <style>
    body { font-family: 'Segoe UI', system-ui, sans-serif; max-width: 800px; margin: 2rem auto; padding: 1rem; color: #1e293b; }
    h1 { font-size: 1.25rem; margin-bottom: 0.5rem; border-bottom: 2px solid #6366f1; padding-bottom: 0.5rem; }
    .meta { font-size: 0.875rem; color: #64748b; margin-bottom: 1.5rem; }
    .meta p { margin: 0.25rem 0; }
    table { width: 100%; border-collapse: collapse; margin-top: 1rem; }
    th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid #e2e8f0; }
    th { font-size: 0.75rem; color: #64748b; font-weight: 600; }
    .checked { color: #16a34a; }
    .unchecked { color: #94a3b8; }
    .notes { font-size: 0.8rem; color: #64748b; margin-left: 1.5rem; }
    @media print { body { margin: 1rem; } }
  </style>
</head>
<body>
  <h1>${title}</h1>
  <div class="meta">
    <p><strong>Location:</strong> ${report.location_name || '—'}</p>
    <p><strong>Date & time:</strong> ${dateStr}</p>
    <p><strong>Staff:</strong> ${report.employee_name || '—'}</p>
    ${report.notes ? `<p><strong>Notes:</strong> ${report.notes}</p>` : ''}
  </div>
  <table>
    <thead><tr><th>#</th><th>Task</th><th>Done</th><th>Notes</th></tr></thead>
    <tbody>
      ${lines.map((l, i) => `
        <tr>
          <td>${i + 1}</td>
          <td>${l.name}</td>
          <td class="${l.checked ? 'checked' : 'unchecked'}">${l.checked ? '✓ Yes' : '○ No'}</td>
          <td>${l.notes}</td>
        </tr>
      `).join('')}
    </tbody>
  </table>
  <p style="margin-top: 1.5rem; font-size: 0.75rem; color: #94a3b8;">Report #${report.id} · Generated from Cleaner Attendance</p>
</body>
</html>`;
    const w = window.open('', '_blank', 'noopener');
    if (w) {
        w.document.write(html);
        w.document.close();
        w.focus();
        w.onload = () => setTimeout(() => w.print(), 300);
    } else {
        alert('Please allow pop-ups to generate the report.');
    }
};

const Reports = () => {
    const [reports, setReports] = useState([]);
    const [completedAttendances, setCompletedAttendances] = useState([]);
    const [loading, setLoading] = useState(true);
    const [completedLoading, setCompletedLoading] = useState(true);
    const [creatingId, setCreatingId] = useState(null);
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
            if (err.response?.status === 403) setReports([]);
            console.error('Error fetching reports:', err);
        } finally {
            setLoading(false);
        }
    };

    const fetchCompletedAttendances = async () => {
        setCompletedLoading(true);
        try {
            const res = await axios.get('/api/reports/completed-attendances', { headers: authHeader() });
            setCompletedAttendances(res.data);
        } catch (err) {
            if (err.response?.status === 403) setCompletedAttendances([]);
        } finally {
            setCompletedLoading(false);
        }
    };

    useEffect(() => {
        fetchReports();
        fetchCompletedAttendances();
    }, []);

    const handleCreateReport = async (attendanceId) => {
        setCreatingId(attendanceId);
        try {
            await axios.post('/api/reports', { attendance_id: attendanceId }, { headers: authHeader() });
            await fetchReports();
            await fetchCompletedAttendances();
        } catch (err) {
            alert('Could not create report: ' + (err.response?.data?.error || err.message));
        } finally {
            setCreatingId(null);
        }
    };

    const filtered = reports.filter(r => {
        if (filter.status && r.status !== filter.status) return false;
        if (filter.search) {
            const q = filter.search.toLowerCase();
            if (!(r.location_name || '').toLowerCase().includes(q) &&
                !(r.employee_name || '').toLowerCase().includes(q) &&
                !(r.checklist_type || '').toLowerCase().includes(q)) return false;
        }
        return true;
    });

    const handleExportCsv = () => {
        const headers = ['Date', 'Location', 'Checklist Type', 'Staff', 'Completed', 'Total', 'Status'];
        const rows = filtered.map(r => [
            r.date ? new Date(r.date).toLocaleString() : '',
            r.location_name || '',
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
        const headers = ['Date', 'Location', 'Checklist Type', 'Staff', 'Completed', 'Total', 'Status'];
        const row = [r.date ? new Date(r.date).toLocaleString() : '', r.location_name || '', r.checklist_type || '', r.employee_name || '', r.items_completed ?? '', r.items_total ?? '', r.status || ''];
        const csv = [headers.join(','), row.map(cell => `"${String(cell).replace(/"/g, '""')}"`).join(',')].join('\n');
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `report-${r.id}-${(r.date || '').toString().slice(0, 10)}.csv`;
        link.click();
        URL.revokeObjectURL(link.href);
    };

    const handleGenerateReport = async (id) => {
        try {
            const res = await axios.get(`/api/reports/${id}`, { headers: authHeader() });
            openPrintReport(res.data);
        } catch (err) {
            alert('Could not load report: ' + (err.response?.data?.error || err.message));
        }
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

            {completedAttendances.length > 0 && (
                <div className="card glass" style={{ marginBottom: '1.5rem', padding: '1rem' }}>
                    <h3 style={{ marginBottom: '0.75rem', fontSize: '1rem' }}>Create report from completed cleaning</h3>
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', marginBottom: '1rem' }}>Select a completed cleaning to create an official report (checklist type from schedule).</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                        {completedAttendances.map((att) => (
                            <div key={att.id} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.6rem 0.8rem', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                                <span style={{ fontSize: '0.9rem' }}>
                                    {att.location_name || 'Location'} · {att.employee_name || 'Staff'} · {att.check_out ? new Date(att.check_out).toLocaleString() : ''}
                                    {att.checklist_type && <span style={{ color: 'var(--primary)', marginLeft: '0.5rem' }}>({att.checklist_type})</span>}
                                </span>
                                <button type="button" className="btn btn-primary" disabled={creatingId !== null} style={{ padding: '0.4rem 0.8rem' }} onClick={() => handleCreateReport(att.id)}>
                                    {creatingId === att.id ? 'Creating…' : 'Create report'}
                                </button>
                            </div>
                        ))}
                    </div>
                </div>
            )}

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
                                <th style={{ textAlign: 'left', padding: '1rem', color: 'var(--text-muted)' }}>Location</th>
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
                                    <td style={{ padding: '1rem' }}>{item.location_name || '—'}</td>
                                    <td style={{ padding: '1rem' }}><span style={{ color: 'var(--primary)', fontWeight: '600' }}>{item.checklist_type || '—'}</span></td>
                                    <td style={{ padding: '1rem' }}>{item.employee_name || '—'}</td>
                                    <td style={{ padding: '1rem' }}>{item.items_completed ?? 0}/{item.items_total ?? 0}</td>
                                    <td style={{ padding: '1rem' }}>
                                        <span style={{ background: item.status === 'completed' ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)', color: item.status === 'completed' ? 'var(--success)' : 'var(--warning)', padding: '2px 8px', borderRadius: '4px', fontSize: '0.75rem' }}>
                                            {item.status || '—'}
                                        </span>
                                    </td>
                                    <td style={{ padding: '1rem', display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                                        <button type="button" className="btn btn-secondary" style={{ padding: '0.5rem' }} title="View detail" onClick={() => handleViewDetail(item.id)}><Eye size={14} /></button>
                                        <button type="button" className="btn btn-primary" style={{ padding: '0.5rem' }} title="Generate / Print report" onClick={() => handleGenerateReport(item.id)}><FileText size={14} /></button>
                                        <button type="button" className="btn btn-secondary" style={{ padding: '0.5rem' }} title="Export CSV" onClick={() => handleExportOne(item)}><Download size={14} /></button>
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
                            {detailReport.location_name} · {detailReport.employee_name} · {detailReport.date ? new Date(detailReport.date).toLocaleString() : ''}
                        </p>
                        <p style={{ marginBottom: '1rem' }}><strong>Checklist:</strong> {getChecklistTitle(detailReport.checklist_type)}</p>
                        <div style={{ marginBottom: '1rem' }}>
                            <button type="button" className="btn btn-primary" onClick={() => { openPrintReport(detailReport); }} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
                                <FileText size={16} /> Generate / Print report
                            </button>
                        </div>
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
