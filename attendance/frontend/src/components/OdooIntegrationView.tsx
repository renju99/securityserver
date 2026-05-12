import React, { useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';

type OdooInstance = {
    instance_code: string;
    name: string;
    base_url: string;
    db_name: string;
    username: string;
    employee_lookup_field: 'code' | 'barcode';
    is_active: boolean;
};

type StaffRouting = {
    staff_id: string;
    instance_code: string;
    is_active: boolean;
    notes?: string;
    first_name?: string;
    last_name?: string;
};

type CsvRejectedRow = {
    sourceRow?: number | null;
    staffId: string;
    instanceCode: string;
    reason: string;
};

type BulkRoutingRow = {
    staffId: string;
    instanceCode: string;
    notes?: string;
    isActive: boolean;
    sourceRow?: number;
};

type SiteLite = {
    id: number;
    name: string;
};

type KioskDevice = {
    id: number;
    name: string;
    site_id: number;
    site_name?: string;
    device_key: string;
    is_active: boolean;
    notes?: string;
    last_seen_at?: string;
};

type OperationsHealth = {
    generatedAt: string;
    processCounters: { counters: Record<string, number>; apiLatency: unknown[]; generatedAt: string } | null;
    biometricQueue: { counts: Record<string, number>; oldestPending: string | null };
    odooOutbox: { oldestRetryAt: string | null; actionableCount: number };
};

const OdooIntegrationView = () => {
    const user = useAuthStore((state) => state.user);
    const token = user?.token;
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');
    const [instances, setInstances] = useState<OdooInstance[]>([]);
    const [routingRows, setRoutingRows] = useState<StaffRouting[]>([]);
    const [search, setSearch] = useState('');
    const [syncStatus, setSyncStatus] = useState<any>(null);

    const [instanceForm, setInstanceForm] = useState({
        instanceCode: 'dxb',
        name: '',
        baseUrl: '',
        dbName: 'odoo',
        username: '',
        password: '',
        employeeLookupField: 'code' as 'code' | 'barcode',
        isActive: true,
    });
    const [routingForm, setRoutingForm] = useState({
        staffId: '',
        instanceCode: 'dxb',
        notes: '',
        isActive: true,
    });
    const [bulkRows, setBulkRows] = useState<BulkRoutingRow[]>([]);
    const [bulkReplace, setBulkReplace] = useState(false);
    const [bulkResult, setBulkResult] = useState<any>(null);
    const [parseRejectedRows, setParseRejectedRows] = useState<CsvRejectedRow[]>([]);
    const [importRejectedRows, setImportRejectedRows] = useState<CsvRejectedRow[]>([]);
    const [sites, setSites] = useState<SiteLite[]>([]);
    const [kioskDevices, setKioskDevices] = useState<KioskDevice[]>([]);
    const [operationsHealth, setOperationsHealth] = useState<OperationsHealth | null>(null);
    const [kioskForm, setKioskForm] = useState({
        name: '',
        siteId: '',
        deviceKey: '',
        notes: '',
        isActive: true,
    });

    const request = async (url: string, options: RequestInit = {}) => {
        const res = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}`,
                ...(options.headers || {}),
            },
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'Request failed');
        return data;
    };

    const loadData = async () => {
        if (!token) return;
        setLoading(true);
        setError('');
        try {
            const [instancesData, routingData, statusData, sitesData, kioskData, healthData] = await Promise.all([
                request('/hr/integrations/odoo-instances'),
                request(`/hr/integrations/staff-routing?search=${encodeURIComponent(search)}`),
                request('/hr/integrations/odoo-sync/status'),
                request('/hr/sites'),
                request('/hr/integrations/kiosk-devices'),
                request('/hr/integrations/operations-health'),
            ]);
            setInstances(instancesData || []);
            setRoutingRows(routingData || []);
            setSyncStatus(statusData || null);
            setSites(Array.isArray(sitesData) ? sitesData : []);
            setKioskDevices(Array.isArray(kioskData) ? kioskData : []);
            setOperationsHealth(healthData || null);
        } catch (err: any) {
            setError(err.message || 'Failed to load integration data');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        loadData();
    }, [token]);

    const saveInstance = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        try {
            await request('/hr/integrations/odoo-instances', {
                method: 'POST',
                body: JSON.stringify(instanceForm),
            });
            await loadData();
            setInstanceForm((prev) => ({ ...prev, password: '' }));
        } catch (err: any) {
            setError(err.message || 'Failed to save Odoo instance');
        }
    };

    const saveRouting = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        try {
            await request(`/hr/integrations/staff-routing/${encodeURIComponent(routingForm.staffId.trim())}`, {
                method: 'PUT',
                body: JSON.stringify({
                    instanceCode: routingForm.instanceCode,
                    notes: routingForm.notes,
                    isActive: routingForm.isActive,
                }),
            });
            await loadData();
            setRoutingForm((prev) => ({ ...prev, staffId: '', notes: '' }));
        } catch (err: any) {
            setError(err.message || 'Failed to save staff routing');
        }
    };

    const runSyncNow = async () => {
        setError('');
        try {
            await request('/hr/integrations/odoo-sync/run', { method: 'POST', body: JSON.stringify({}) });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to trigger sync');
        }
    };

    const requeueOdooDeadLetter = async () => {
        if (!window.confirm('Re-queue up to 100 dead-letter Odoo sync rows? This resets attempts and runs the sync worker.')) return;
        setError('');
        try {
            await request('/hr/integrations/odoo-sync/requeue', {
                method: 'POST',
                body: JSON.stringify({ scope: 'dead_letter', limit: 100, confirm: true }),
            });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Re-queue failed');
        }
    };

    const reprocessBiometricFailed = async () => {
        if (!window.confirm('Re-process up to 100 failed biometric punch rows?')) return;
        setError('');
        try {
            await request('/hr/integrations/biometric-logs/reprocess', {
                method: 'POST',
                body: JSON.stringify({ scope: 'failed', limit: 100, confirm: true }),
            });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Reprocess failed');
        }
    };

    const deleteRouting = async (staffId: string) => {
        setError('');
        try {
            await request(`/hr/integrations/staff-routing/${encodeURIComponent(staffId)}`, { method: 'DELETE' });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to delete routing');
        }
    };

    const saveKioskDevice = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!kioskForm.name.trim()) {
            setError('Kiosk device name is required');
            return;
        }
        if (!kioskForm.siteId) {
            setError('Please select a site for kiosk device');
            return;
        }
        setError('');
        try {
            await request('/hr/integrations/kiosk-devices', {
                method: 'POST',
                body: JSON.stringify({
                    name: kioskForm.name.trim(),
                    siteId: Number(kioskForm.siteId),
                    deviceKey: kioskForm.deviceKey.trim() || undefined,
                    notes: kioskForm.notes.trim() || null,
                    isActive: kioskForm.isActive,
                }),
            });
            setKioskForm({ name: '', siteId: '', deviceKey: '', notes: '', isActive: true });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to save kiosk device');
        }
    };

    const updateKioskDevice = async (id: number, patch: Partial<KioskDevice>) => {
        setError('');
        try {
            await request(`/hr/integrations/kiosk-devices/${id}`, {
                method: 'PATCH',
                body: JSON.stringify({
                    name: patch.name,
                    siteId: patch.site_id,
                    deviceKey: patch.device_key,
                    notes: patch.notes,
                    isActive: patch.is_active,
                }),
            });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to update kiosk device');
        }
    };

    const deleteKioskDevice = async (id: number) => {
        setError('');
        try {
            await request(`/hr/integrations/kiosk-devices/${id}`, { method: 'DELETE' });
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to delete kiosk device');
        }
    };

    const parseCsvFile = async (file: File) => {
        const text = await file.text();
        const lines = text
            .split(/\r?\n/)
            .map((line) => line.trim())
            .filter((line) => line.length > 0);
        if (lines.length === 0) {
            throw new Error('CSV file is empty');
        }

        const parsed: Array<{ staffId: string; instanceCode: string; notes?: string; isActive: boolean; sourceRow: number }> = [];
        const rejected: CsvRejectedRow[] = [];
        const startIdx = /^staff_id\s*,\s*instance_code/i.test(lines[0]) ? 1 : 0;
        for (let i = startIdx; i < lines.length; i += 1) {
            const cols = lines[i].split(',').map((c) => c.trim());
            const staffId = cols[0];
            const instanceCode = (cols[1] || '').toLowerCase();
            const notes = cols[2] || '';
            const activeRaw = (cols[3] || '').toLowerCase();
            const isActive = !(activeRaw === 'false' || activeRaw === '0' || activeRaw === 'no');
            const sourceRow = i + 1;
            if (!staffId || !instanceCode) {
                rejected.push({
                    sourceRow,
                    staffId: staffId || '',
                    instanceCode: instanceCode || '',
                    reason: 'Missing staff_id or instance_code',
                });
                continue;
            }
            if (!['dxb', 'auh'].includes(instanceCode)) {
                rejected.push({
                    sourceRow,
                    staffId,
                    instanceCode,
                    reason: 'instance_code must be dxb or auh',
                });
                continue;
            }
            parsed.push({ staffId, instanceCode, notes, isActive, sourceRow });
        }
        if (parsed.length === 0) throw new Error('No valid rows found in CSV. Expected: staff_id,instance_code[,notes,is_active]');
        setBulkRows(parsed);
        setParseRejectedRows(rejected);
        setImportRejectedRows([]);
        setBulkResult(null);
    };

    const uploadBulkRouting = async () => {
        if (!cleanedValidRows.length) {
            setError('Choose a CSV file first.');
            return;
        }
        setError('');
        try {
            const data = await request('/hr/integrations/staff-routing/bulk', {
                method: 'POST',
                body: JSON.stringify({
                    mappings: cleanedValidRows.map((r) => ({
                        staffId: r.staffId,
                        instanceCode: r.instanceCode,
                        notes: r.notes || null,
                        isActive: r.isActive,
                        sourceRow: r.sourceRow,
                    })),
                    replaceExisting: bulkReplace,
                }),
            });
            setBulkResult(data);
            setImportRejectedRows((data?.rejectedRows || []) as CsvRejectedRow[]);
            await loadData();
        } catch (err: any) {
            setError(err.message || 'Failed to import CSV');
        }
    };

    const cleanedValidRows = useMemo(() => {
        const deduped = new Map<string, BulkRoutingRow>();
        for (const row of bulkRows) {
            const normalizedStaffId = String(row.staffId || '').trim().toUpperCase();
            const normalizedInstanceCode = String(row.instanceCode || '').trim().toLowerCase();
            if (!normalizedStaffId || !normalizedInstanceCode) continue;
            deduped.set(normalizedStaffId, {
                ...row,
                staffId: normalizedStaffId,
                instanceCode: normalizedInstanceCode,
                notes: String(row.notes || '').trim(),
            });
        }
        return Array.from(deduped.values());
    }, [bulkRows]);

    const duplicateCount = Math.max(bulkRows.length - cleanedValidRows.length, 0);

    const downloadCsv = (filename: string, rows: string[]) => {
        const blob = new Blob([rows.join('\n')], { type: 'text/csv;charset=utf-8;' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.setAttribute('href', url);
        link.setAttribute('download', filename);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    };

    const downloadTemplate = () => {
        downloadCsv('staff_routing_template.csv', [
            'staff_id,instance_code,notes,is_active',
            'ST100,dxb,Dubai employee,true',
            'ST220,auh,Abu Dhabi employee,true',
        ]);
    };

    const downloadCleanedValidRows = () => {
        if (!cleanedValidRows.length) return;
        const lines = ['staff_id,instance_code,notes,is_active'];
        cleanedValidRows.forEach((r) => {
            const escapedNotes = String(r.notes || '').replace(/"/g, '""');
            lines.push(`${r.staffId},${r.instanceCode},"${escapedNotes}",${r.isActive ? 'true' : 'false'}`);
        });
        downloadCsv('staff_routing_cleaned_valid_rows.csv', lines);
    };

    const downloadRejectedRows = (rows: CsvRejectedRow[], filename = 'staff_routing_rejected_rows.csv') => {
        if (!rows.length) return;
        const lines = ['source_row,staff_id,instance_code,reason'];
        rows.forEach((r) => {
            lines.push(`${r.sourceRow || ''},${r.staffId || ''},${r.instanceCode || ''},"${String(r.reason || '').replace(/"/g, '""')}"`);
        });
        downloadCsv(filename, lines);
    };

    const inferredLookup = useMemo(() => {
        if (instanceForm.instanceCode.toLowerCase() === 'dxb') return 'code';
        if (instanceForm.instanceCode.toLowerCase() === 'auh') return 'barcode';
        return instanceForm.employeeLookupField;
    }, [instanceForm.instanceCode, instanceForm.employeeLookupField]);

    return (
        <div className="management-view animate-fade-in">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '1rem', marginBottom: '1rem', flexWrap: 'wrap' }}>
                <div>
                    <h2 style={{ margin: 0 }}>Odoo Integrations</h2>
                    <p className="form-help">Staff-ID routing to Dubai and Abu Dhabi Odoo instances.</p>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button className="hr-btn secondary sm" onClick={loadData} disabled={loading}>{loading ? 'Loading...' : 'Refresh'}</button>
                    <button className="hr-btn primary sm" onClick={runSyncNow}>Run Sync Now</button>
                </div>
            </div>

            {error && <div style={{ color: '#b91c1c', marginBottom: '0.75rem' }}>{error}</div>}

            <div className="kpi-grid" style={{ marginBottom: '1rem' }}>
                {['pending', 'failed', 'processing', 'succeeded', 'dead_letter'].map((k) => (
                    <div key={k} className="kpi-card">
                        <div className="kpi-label" style={{ textTransform: 'capitalize' }}>{k.replace('_', ' ')}</div>
                        <div className="kpi-value">{syncStatus?.counts?.[k] || 0}</div>
                    </div>
                ))}
            </div>

            <div className="form-surface" style={{ marginBottom: '1rem' }}>
                <h3>Operations health and replay</h3>
                <p className="form-help" style={{ marginTop: 0 }}>
                    Live counters (this API instance), biometric punch queue, and Odoo outbox backlog. Use replay when fixes are deployed or routing was corrected.
                </p>
                <div className="kpi-grid" style={{ marginBottom: '0.75rem' }}>
                    <div className="kpi-card">
                        <div className="kpi-label">Odoo actionable outbox</div>
                        <div className="kpi-value">{operationsHealth?.odooOutbox?.actionableCount ?? '—'}</div>
                    </div>
                    <div className="kpi-card">
                        <div className="kpi-label">Biometric pending</div>
                        <div className="kpi-value">{operationsHealth?.biometricQueue?.counts?.pending ?? 0}</div>
                    </div>
                    <div className="kpi-card">
                        <div className="kpi-label">Biometric failed</div>
                        <div className="kpi-value">{operationsHealth?.biometricQueue?.counts?.failed ?? 0}</div>
                    </div>
                    <div className="kpi-card">
                        <div className="kpi-label">ZK ATTLOG lines (ok, this instance)</div>
                        <div className="kpi-value">
                            {operationsHealth?.processCounters?.counters?.zk_iclock_attlog_records_ok_total ?? 0}
                        </div>
                    </div>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <button className="hr-btn secondary sm" type="button" onClick={requeueOdooDeadLetter}>
                        Re-queue dead-letter (Odoo)
                    </button>
                    <button className="hr-btn secondary sm" type="button" onClick={reprocessBiometricFailed}>
                        Re-process failed punches
                    </button>
                </div>
            </div>

            <div className="form-surface" style={{ marginBottom: '1rem' }}>
                <h3>Odoo Instance Config</h3>
                <p className="form-help strong" style={{ marginTop: 0, marginBottom: '0.7rem' }}>
                    Configure each Odoo endpoint once. Use <code>dxb</code> for Dubai and <code>auh</code> for Abu Dhabi.
                </p>
                <form onSubmit={saveInstance} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.75rem' }}>
                    <div className="form-group">
                        <label>Instance Code</label>
                        <input className="control-input" placeholder="dxb or auh" value={instanceForm.instanceCode} onChange={(e) => setInstanceForm({ ...instanceForm, instanceCode: e.target.value.toLowerCase() })} />
                    </div>
                    <div className="form-group">
                        <label>Display Name</label>
                        <input className="control-input" placeholder="Dubai Odoo" value={instanceForm.name} onChange={(e) => setInstanceForm({ ...instanceForm, name: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Base URL</label>
                        <input className="control-input" placeholder="https://ops.dxb.berkeleyuae.com" value={instanceForm.baseUrl} onChange={(e) => setInstanceForm({ ...instanceForm, baseUrl: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Database Name</label>
                        <input className="control-input" placeholder="odoo" value={instanceForm.dbName} onChange={(e) => setInstanceForm({ ...instanceForm, dbName: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Username</label>
                        <input className="control-input" placeholder="integration@berkeleyuae.com" value={instanceForm.username} onChange={(e) => setInstanceForm({ ...instanceForm, username: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Password</label>
                        <input className="control-input" type="password" placeholder="Required for create/update" value={instanceForm.password} onChange={(e) => setInstanceForm({ ...instanceForm, password: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Employee Lookup Field</label>
                        <select className="control-input" value={instanceForm.employeeLookupField} onChange={(e) => setInstanceForm({ ...instanceForm, employeeLookupField: e.target.value as 'code' | 'barcode' })}>
                            <option value="code">code</option>
                            <option value="barcode">barcode</option>
                        </select>
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: '1.5rem' }}>
                        <input type="checkbox" checked={instanceForm.isActive} onChange={(e) => setInstanceForm({ ...instanceForm, isActive: e.target.checked })} />
                        Active instance
                    </label>
                    <button className="hr-btn primary sm" type="submit" style={{ justifySelf: "start" }}>Save Instance</button>
                </form>
                <div className="form-help">
                    Suggested lookup for `{instanceForm.instanceCode}`: <strong>{inferredLookup}</strong>
                </div>
            </div>

            <div className="mgmt-table-container" style={{ marginBottom: '1rem' }}>
                <table className="mgmt-table">
                    <thead>
                        <tr>
                            <th>Instance</th>
                            <th>URL</th>
                            <th>DB</th>
                            <th>User</th>
                            <th>Lookup</th>
                            <th>Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {instances.map((it) => (
                            <tr key={it.instance_code}>
                                <td><strong>{it.instance_code}</strong> - {it.name}</td>
                                <td>{it.base_url}</td>
                                <td>{it.db_name}</td>
                                <td>{it.username}</td>
                                <td>{it.employee_lookup_field}</td>
                                <td>{it.is_active ? 'Active' : 'Inactive'}</td>
                            </tr>
                        ))}
                        {instances.length === 0 && (
                            <tr><td colSpan={6} style={{ textAlign: 'center', color: '#94a3b8' }}>No Odoo instance configured yet.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            <div className="form-surface" style={{ marginBottom: '1rem' }}>
                <h3>Staff Routing</h3>
                <p className="form-help strong" style={{ marginTop: 0, marginBottom: '0.7rem' }}>
                    Map each employee staff ID to exactly one Odoo instance.
                </p>
                <form onSubmit={saveRouting} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem', alignItems: 'center' }}>
                    <div className="form-group">
                        <label>Staff ID</label>
                        <input className="control-input" placeholder="e.g. ST374" value={routingForm.staffId} onChange={(e) => setRoutingForm({ ...routingForm, staffId: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Instance</label>
                        <select className="control-input" value={routingForm.instanceCode} onChange={(e) => setRoutingForm({ ...routingForm, instanceCode: e.target.value })}>
                            <option value="dxb">dxb</option>
                            <option value="auh">auh</option>
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Notes</label>
                        <input className="control-input" placeholder="Optional internal remark" value={routingForm.notes} onChange={(e) => setRoutingForm({ ...routingForm, notes: e.target.value })} />
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: '1.4rem' }}>
                        <input type="checkbox" checked={routingForm.isActive} onChange={(e) => setRoutingForm({ ...routingForm, isActive: e.target.checked })} />
                        Active
                    </label>
                    <button className="hr-btn primary sm" type="submit" style={{ justifySelf: "start" }}>Save Routing</button>
                </form>
            </div>

            <div className="form-surface" style={{ marginBottom: '1rem' }}>
                <h3>Bulk CSV Import</h3>
                <p className="form-help" style={{ marginTop: 0 }}>
                    Upload CSV with columns: <code>staff_id,instance_code</code> (optional: <code>notes,is_active</code>).
                </p>
                <div style={{ display: 'flex', gap: '0.45rem', flexWrap: 'wrap', marginBottom: '0.55rem' }}>
                    <span className="inline-chip">1. Download template</span>
                    <span className="inline-chip">2. Fill staff mappings</span>
                    <span className="inline-chip">3. Import and review rejects</span>
                </div>
                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                    <button className="hr-btn secondary sm" type="button" onClick={downloadTemplate}>
                        Download Template
                    </button>
                    <input
                        type="file"
                        accept=".csv,text/csv"
                        onChange={async (e) => {
                            const file = e.target.files?.[0];
                            if (!file) return;
                            try {
                                await parseCsvFile(file);
                            } catch (err: any) {
                                setError(err.message || 'Failed to parse CSV');
                            }
                        }}
                    />
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <input type="checkbox" checked={bulkReplace} onChange={(e) => setBulkReplace(e.target.checked)} />
                        Replace all existing mappings
                    </label>
                    <button className="hr-btn primary sm" type="button" onClick={uploadBulkRouting} disabled={!cleanedValidRows.length}>
                        {cleanedValidRows.length ? `Import ${cleanedValidRows.length} Cleaned Rows` : 'Import CSV'}
                    </button>
                    <button
                        className="hr-btn secondary sm"
                        type="button"
                        onClick={() => {
                            setBulkRows([]);
                            setParseRejectedRows([]);
                            setImportRejectedRows([]);
                            setBulkResult(null);
                        }}
                        disabled={!bulkRows.length && !parseRejectedRows.length && !importRejectedRows.length}
                    >
                        Clear Parsed Data
                    </button>
                </div>
                {bulkRows.length > 0 && (
                    <div className="form-help" style={{ marginTop: '0.6rem', color: '#334155' }}>
                        Parsed {bulkRows.length} row(s), cleaned valid rows {cleanedValidRows.length}
                        {duplicateCount > 0 ? ` (deduplicated ${duplicateCount})` : ''}. Preview first 5:
                        <div style={{ marginTop: '0.3rem', fontFamily: 'monospace', whiteSpace: 'pre-wrap', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.5rem' }}>
                            {cleanedValidRows.slice(0, 5).map((r) => `${r.staffId},${r.instanceCode},${r.notes || ''},${r.isActive}`).join('\n')}
                        </div>
                        <button
                            className="hr-btn secondary sm"
                            type="button"
                            style={{ marginTop: '0.45rem' }}
                            onClick={downloadCleanedValidRows}
                        >
                            Export cleaned valid CSV
                        </button>
                    </div>
                )}
                {parseRejectedRows.length > 0 && (
                    <div className="form-help" style={{ marginTop: '0.6rem', color: '#b45309' }}>
                        Skipped during parsing: {parseRejectedRows.length} row(s).
                        <button
                            className="hr-btn secondary sm"
                            type="button"
                            style={{ marginLeft: '0.5rem' }}
                            onClick={() => downloadRejectedRows(parseRejectedRows, 'staff_routing_parse_rejected.csv')}
                        >
                            Export parse errors CSV
                        </button>
                    </div>
                )}
                {bulkResult && (
                    <div className="form-help" style={{ marginTop: '0.6rem', color: '#166534' }}>
                        Imported: {bulkResult.insertedOrUpdated} rows (received {bulkResult.totalReceived}, processed {bulkResult.totalProcessed}, valid {bulkResult.totalValid}, rejected {bulkResult.totalRejected}).
                    </div>
                )}
                {importRejectedRows.length > 0 && (
                    <div className="form-help" style={{ marginTop: '0.6rem', color: '#b91c1c' }}>
                        Rejected by server: {importRejectedRows.length} row(s).
                        <button
                            className="hr-btn secondary sm"
                            type="button"
                            style={{ marginLeft: '0.5rem' }}
                            onClick={() => downloadRejectedRows(importRejectedRows, 'staff_routing_server_rejected.csv')}
                        >
                            Export server rejected CSV
                        </button>
                    </div>
                )}
            </div>

            <div className="form-surface" style={{ marginBottom: '1rem' }}>
                <h3>Kiosk Device Management</h3>
                <p className="form-help strong" style={{ marginTop: 0, marginBottom: '0.7rem' }}>
                    Register kiosk devices and assign each device key to a specific site.
                </p>
                <form onSubmit={saveKioskDevice} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(170px, 1fr))', gap: '0.5rem', alignItems: 'center' }}>
                    <div className="form-group">
                        <label>Device Name</label>
                        <input className="control-input" placeholder="Main gate kiosk" value={kioskForm.name} onChange={(e) => setKioskForm({ ...kioskForm, name: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Assigned Site</label>
                        <select className="control-input" value={kioskForm.siteId} onChange={(e) => setKioskForm({ ...kioskForm, siteId: e.target.value })}>
                            <option value="">Select site</option>
                            {sites.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                        </select>
                    </div>
                    <div className="form-group">
                        <label>Device Key (optional)</label>
                        <input className="control-input" placeholder="Auto-generated if blank" value={kioskForm.deviceKey} onChange={(e) => setKioskForm({ ...kioskForm, deviceKey: e.target.value })} />
                    </div>
                    <div className="form-group">
                        <label>Notes</label>
                        <input className="control-input" placeholder="Optional note" value={kioskForm.notes} onChange={(e) => setKioskForm({ ...kioskForm, notes: e.target.value })} />
                    </div>
                    <label style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: '1.4rem' }}>
                        <input type="checkbox" checked={kioskForm.isActive} onChange={(e) => setKioskForm({ ...kioskForm, isActive: e.target.checked })} />
                        Active
                    </label>
                    <button className="hr-btn primary sm" type="submit" style={{ justifySelf: "start" }}>Add Kiosk Device</button>
                </form>
                <div className="mgmt-table-container" style={{ marginTop: '0.75rem' }}>
                    <table className="mgmt-table">
                        <thead>
                            <tr>
                                <th>Name</th>
                                <th>Site</th>
                                <th>Device Key</th>
                                <th>Status</th>
                                <th>Last Seen</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {kioskDevices.map((d) => (
                                <tr key={d.id}>
                                    <td>{d.name}</td>
                                    <td>{d.site_name || d.site_id}</td>
                                    <td><code>{d.device_key}</code></td>
                                    <td>{d.is_active ? 'Active' : 'Disabled'}</td>
                                    <td>{d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : '-'}</td>
                                    <td style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
                                        <button
                                            className="hr-btn secondary sm"
                                            type="button"
                                            onClick={() => updateKioskDevice(d.id, { is_active: !d.is_active })}
                                        >
                                            {d.is_active ? 'Disable' : 'Enable'}
                                        </button>
                                        <button
                                            className="hr-btn secondary sm"
                                            type="button"
                                            onClick={() => deleteKioskDevice(d.id)}
                                        >
                                            Remove
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {kioskDevices.length === 0 && (
                                <tr><td colSpan={6} style={{ textAlign: 'center', color: '#94a3b8' }}>No kiosk devices registered.</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            </div>

            <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', background: '#fff', padding: '0.6rem', borderRadius: 10, border: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                <input className="control-input" placeholder="Search routing by staff/name..." value={search} onChange={(e) => setSearch(e.target.value)} />
                <button className="hr-btn secondary sm" onClick={loadData}>Search Routing</button>
            </div>
            <div className="mgmt-table-container">
                <table className="mgmt-table">
                    <thead>
                        <tr>
                            <th>Staff ID</th>
                            <th>Name</th>
                            <th>Instance</th>
                            <th>Notes</th>
                            <th>Status</th>
                            <th>Action</th>
                        </tr>
                    </thead>
                    <tbody>
                        {routingRows.map((row) => (
                            <tr key={row.staff_id}>
                                <td><strong>{row.staff_id}</strong></td>
                                <td>{[row.first_name, row.last_name].filter(Boolean).join(' ') || '-'}</td>
                                <td>{row.instance_code}</td>
                                <td>{row.notes || '-'}</td>
                                <td>{row.is_active ? 'Active' : 'Disabled'}</td>
                                <td>
                                    <button className="hr-btn secondary sm" onClick={() => deleteRouting(row.staff_id)}>
                                        Remove
                                    </button>
                                </td>
                            </tr>
                        ))}
                        {routingRows.length === 0 && (
                            <tr><td colSpan={6} style={{ textAlign: 'center', color: '#94a3b8' }}>No staff routing found.</td></tr>
                        )}
                    </tbody>
                </table>
            </div>

            {(syncStatus?.deadSamples || []).length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                    <h3 style={{ marginBottom: '0.5rem' }}>Dead Letter Samples</h3>
                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th>ID</th>
                                    <th>Attendance</th>
                                    <th>Staff</th>
                                    <th>Event</th>
                                    <th>Attempts</th>
                                    <th>Error</th>
                                </tr>
                            </thead>
                            <tbody>
                                {syncStatus.deadSamples.map((row: any) => (
                                    <tr key={row.id}>
                                        <td>{row.id}</td>
                                        <td>{row.attendance_id}</td>
                                        <td>{row.staff_id}</td>
                                        <td>{row.event_type}</td>
                                        <td>{row.attempts}</td>
                                        <td style={{ maxWidth: 360, whiteSpace: 'normal' }}>{row.last_error || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

export default OdooIntegrationView;
