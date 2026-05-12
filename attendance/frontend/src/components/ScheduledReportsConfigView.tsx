import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';

const PRESETS = [
    { value: 'last_7_days', label: 'Last 7 days' },
    { value: 'last_30_days', label: 'Last 30 days' },
    { value: 'last_calendar_month', label: 'Previous calendar month' },
    { value: 'month_to_date', label: 'Month to date' },
] as const;

const FORMATS = [
    { value: 'csv', label: 'CSV' },
    { value: 'xlsx', label: 'Excel (.xlsx)' },
    { value: 'fixed_width', label: 'Fixed-width (.txt)' },
] as const;

const TIMEZONES = [
    'UTC',
    'Asia/Dubai',
    'Asia/Riyadh',
    'Asia/Kolkata',
    'Europe/London',
    'America/New_York',
    'America/Los_Angeles',
];

type PresetValue = (typeof PRESETS)[number]['value'];
type FormatValue = (typeof FORMATS)[number]['value'];
type ScheduleMode = 'interval' | 'cron' | 'daily_at';

type ScheduledExportRow = {
    id: number;
    name: string;
    enabled: boolean;
    runEveryMinutes: number;
    dataSource: string;
    roleIds: unknown;
    siteIds: unknown;
    shiftIds: unknown;
    department: string | null;
    dateRangePreset: string;
    exportFormat: string;
    deliveryEmails: string | null;
    deliveryCcEmails?: string | null;
    deliveryBccEmails?: string | null;
    replyTo?: string | null;
    emailSubject?: string | null;
    emailBodyText?: string | null;
    sendHtml?: boolean;
    scheduleTimezone?: string | null;
    scheduleMode?: ScheduleMode | string;
    cronExpression?: string | null;
    dailyAtTime?: string | null;
    pauseUntil?: string | null;
    maxExportRows?: number | null;
    webhookUrl?: string | null;
    webhookSecretSet?: boolean;
    webhookSigningHeader?: string | null;
    sftpUpload: boolean;
    s3Upload?: boolean;
    alertEmailsOnFailure?: string | null;
    retryBackoffMinutes?: number;
    consecutiveFailures?: number;
    encryptAttachmentPgp?: boolean;
    nextRunAt: string | null;
    lastRunAt: string | null;
    lastError: string | null;
};

type RunRow = {
    id: number;
    triggeredBy: string;
    startedAt: string;
    finishedAt: string | null;
    status: string;
    rowCount: number | null;
    truncated: boolean;
    fileName: string | null;
    emailOk: boolean | null;
    sftpOk: boolean | null;
    s3Ok: boolean | null;
    webhookOk: boolean | null;
    errorMessage: string | null;
};

type AuditRow = {
    id: number;
    employeeId: number | null;
    scheduledExportId: number | null;
    action: string;
    payload: Record<string, unknown>;
    createdAt: string;
};

type TemplateRow = { id: number; name: string; definition: Record<string, unknown> };

type FormState = {
    name: string;
    enabled: boolean;
    emails: string;
    ccEmails: string;
    bccEmails: string;
    replyTo: string;
    emailSubject: string;
    emailBodyText: string;
    sendHtml: boolean;
    runEveryMinutes: number;
    scheduleMode: ScheduleMode;
    cronExpression: string;
    dailyAtTime: string;
    scheduleTimezone: string;
    pauseUntil: string;
    dataSource: 'app' | 'biometrics';
    preset: PresetValue;
    format: FormatValue;
    department: string;
    maxExportRows: string;
    sftp: boolean;
    s3: boolean;
    webhookUrl: string;
    webhookSecret: string;
    webhookSigningHeader: string;
    alertEmails: string;
    retryBackoffMinutes: number;
    pgp: boolean;
    roleIds: number[];
    siteIds: number[];
    shiftIds: number[];
};

const emptyForm = (): FormState => ({
    name: '',
    enabled: true,
    emails: '',
    ccEmails: '',
    bccEmails: '',
    replyTo: '',
    emailSubject: '',
    emailBodyText: '',
    sendHtml: true,
    runEveryMinutes: 1440,
    scheduleMode: 'interval',
    cronExpression: '0 7 * * *',
    dailyAtTime: '07:00',
    scheduleTimezone: 'Asia/Dubai',
    pauseUntil: '',
    dataSource: 'app',
    preset: 'last_30_days',
    format: 'csv',
    department: '',
    maxExportRows: '',
    sftp: false,
    s3: false,
    webhookUrl: '',
    webhookSecret: '',
    webhookSigningHeader: 'X-Webhook-Signature',
    alertEmails: '',
    retryBackoffMinutes: 15,
    pgp: false,
    roleIds: [],
    siteIds: [],
    shiftIds: [],
});

function asIntArray(v: unknown): number[] {
    if (v == null) return [];
    if (Array.isArray(v)) return v.map((x) => Number(x)).filter((n) => Number.isFinite(n));
    if (typeof v === 'string') {
        try {
            const j = JSON.parse(v);
            return Array.isArray(j) ? j.map((x) => Number(x)).filter((n) => Number.isFinite(n)) : [];
        } catch {
            return [];
        }
    }
    return [];
}

function rowToForm(r: ScheduledExportRow): FormState {
    const mode = (['interval', 'cron', 'daily_at'].includes(String(r.scheduleMode)) ? r.scheduleMode : 'interval') as ScheduleMode;
    return {
        name: r.name,
        enabled: r.enabled !== false,
        emails: r.deliveryEmails || '',
        ccEmails: r.deliveryCcEmails || '',
        bccEmails: r.deliveryBccEmails || '',
        replyTo: r.replyTo || '',
        emailSubject: r.emailSubject || '',
        emailBodyText: r.emailBodyText || '',
        sendHtml: r.sendHtml !== false,
        runEveryMinutes: r.runEveryMinutes,
        scheduleMode: mode,
        cronExpression: r.cronExpression || '0 7 * * *',
        dailyAtTime: r.dailyAtTime || '07:00',
        scheduleTimezone: r.scheduleTimezone || 'Asia/Dubai',
        pauseUntil: r.pauseUntil ? r.pauseUntil.slice(0, 16) : '',
        dataSource: r.dataSource === 'biometrics' ? 'biometrics' : 'app',
        preset: (PRESETS.some((p) => p.value === r.dateRangePreset) ? r.dateRangePreset : 'last_30_days') as PresetValue,
        format: (FORMATS.some((f) => f.value === r.exportFormat) ? r.exportFormat : 'csv') as FormatValue,
        department: r.department || '',
        maxExportRows: r.maxExportRows != null ? String(r.maxExportRows) : '',
        sftp: !!r.sftpUpload,
        s3: !!r.s3Upload,
        webhookUrl: r.webhookUrl || '',
        webhookSecret: '',
        webhookSigningHeader: r.webhookSigningHeader || 'X-Webhook-Signature',
        alertEmails: r.alertEmailsOnFailure || '',
        retryBackoffMinutes: r.retryBackoffMinutes ?? 15,
        pgp: !!r.encryptAttachmentPgp,
        roleIds: asIntArray(r.roleIds),
        siteIds: asIntArray(r.siteIds),
        shiftIds: asIntArray(r.shiftIds),
    };
}

function formToPayload(f: FormState): Record<string, unknown> {
    const maxRaw = f.maxExportRows.trim();
    return {
        name: f.name.trim(),
        enabled: f.enabled,
        runEveryMinutes: f.runEveryMinutes,
        dataSource: f.dataSource,
        roleIds: f.roleIds,
        siteIds: f.siteIds,
        shiftIds: f.shiftIds,
        department: f.department.trim() || null,
        dateRangePreset: f.preset,
        exportFormat: f.format,
        deliveryEmails: f.emails.trim() || null,
        deliveryCcEmails: f.ccEmails.trim() || null,
        deliveryBccEmails: f.bccEmails.trim() || null,
        replyTo: f.replyTo.trim() || null,
        emailSubject: f.emailSubject.trim() || null,
        emailBodyText: f.emailBodyText.trim() || null,
        sendHtml: f.sendHtml,
        scheduleTimezone: f.scheduleTimezone,
        scheduleMode: f.scheduleMode,
        cronExpression: f.scheduleMode === 'cron' ? f.cronExpression.trim() || null : null,
        dailyAtTime: f.scheduleMode === 'daily_at' ? f.dailyAtTime.trim() || null : null,
        pauseUntil: f.pauseUntil ? new Date(f.pauseUntil).toISOString() : null,
        maxExportRows: maxRaw ? parseInt(maxRaw, 10) : null,
        webhookUrl: f.webhookUrl.trim() || null,
        webhookSecret: f.webhookSecret.trim() || null,
        webhookSigningHeader: f.webhookSigningHeader.trim() || 'X-Webhook-Signature',
        sftpUpload: f.sftp,
        s3Upload: f.s3,
        alertEmailsOnFailure: f.alertEmails.trim() || null,
        retryBackoffMinutes: f.retryBackoffMinutes,
        encryptAttachmentPgp: f.pgp,
    };
}

function filterSummary(r: ScheduledExportRow, roleNames: Map<number, string>, siteNames: Map<number, string>, shiftNames: Map<number, string>): string {
    const ri = asIntArray(r.roleIds);
    const si = asIntArray(r.siteIds);
    const shi = asIntArray(r.shiftIds);
    const dep = (r.department || '').trim();
    const parts: string[] = [];
    if (dep) parts.push(`Dept “${dep}”`);
    if (ri.length) parts.push(`Roles: ${ri.map((id) => roleNames.get(id) || id).join(', ')}`);
    if (si.length) parts.push(`Sites: ${si.map((id) => (id === -1 ? 'Global' : siteNames.get(id) || id)).join(', ')}`);
    if (shi.length) parts.push(`Shifts: ${shi.map((id) => shiftNames.get(id) || id).join(', ')}`);
    const mode = r.scheduleMode || 'interval';
    parts.push(`Schedule: ${mode}`);
    return parts.length ? parts.join(' · ') : `Schedule: ${mode}`;
}

const ScheduledReportsConfigView: React.FC = () => {
    const { user } = useAuthStore();
    const { showToast } = useUIStore();
    const roles = useDataStore((s) => s.roles);
    const sites = useDataStore((s) => s.sites);
    const shifts = useDataStore((s) => s.shifts);
    const fetchRoles = useDataStore((s) => s.fetchRoles);
    const fetchSites = useDataStore((s) => s.fetchSites);
    const fetchShifts = useDataStore((s) => s.fetchShifts);

    const [rows, setRows] = useState<ScheduledExportRow[]>([]);
    const [loading, setLoading] = useState(false);
    const [createForm, setCreateForm] = useState<FormState>(() => emptyForm());
    const [editingId, setEditingId] = useState<number | null>(null);
    const [editForm, setEditForm] = useState<FormState>(() => emptyForm());
    const [runForId, setRunForId] = useState<number | null>(null);
    const [runs, setRuns] = useState<RunRow[]>([]);
    const [audit, setAudit] = useState<AuditRow[]>([]);
    const [templates, setTemplates] = useState<TemplateRow[]>([]);
    const [templateName, setTemplateName] = useState('');

    const roleNames = useMemo(() => new Map((roles || []).map((r) => [Number(r.id), r.name])), [roles]);
    const siteNames = useMemo(() => new Map((sites || []).map((s) => [Number(s.id), s.name])), [sites]);
    const shiftNames = useMemo(() => new Map((shifts || []).map((s) => [Number(s.id), s.name])), [shifts]);
    const siteOptions = useMemo(() => [{ id: -1, name: 'Global / Unassigned' }, ...(Array.isArray(sites) ? sites : [])], [sites]);

    useEffect(() => {
        if (!user?.token) return;
        if (!roles.length) void fetchRoles(user.token);
        if (!sites.length) void fetchSites(user.token);
        if (!shifts.length) void fetchShifts(user.token);
    }, [user?.token, roles.length, sites.length, shifts.length, fetchRoles, fetchSites, fetchShifts]);

    const load = useCallback(async () => {
        if (!user?.token) return;
        setLoading(true);
        try {
            const res = await fetch('/hr/scheduled-exports', { headers: { Authorization: `Bearer ${user.token}` } });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed to load');
            setRows(Array.isArray(body) ? body : []);
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Load failed', 'error');
        } finally {
            setLoading(false);
        }
    }, [user?.token, showToast]);

    const loadAudit = useCallback(async () => {
        if (!user?.token) return;
        try {
            const res = await fetch('/hr/scheduled-export-audit?limit=100', { headers: { Authorization: `Bearer ${user.token}` } });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed');
            setAudit(Array.isArray(body) ? body : []);
        } catch {
            /* ignore */
        }
    }, [user?.token]);

    const loadTemplates = useCallback(async () => {
        if (!user?.token) return;
        try {
            const res = await fetch('/hr/scheduled-export-templates', { headers: { Authorization: `Bearer ${user.token}` } });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed');
            setTemplates(Array.isArray(body) ? body : []);
        } catch {
            /* ignore */
        }
    }, [user?.token]);

    const loadRuns = useCallback(
        async (id: number) => {
            if (!user?.token) return;
            const res = await fetch(`/hr/scheduled-exports/${id}/runs?limit=50`, { headers: { Authorization: `Bearer ${user.token}` } });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed');
            setRuns(Array.isArray(body) ? body : []);
        },
        [user?.token]
    );

    useEffect(() => {
        void load();
        void loadAudit();
        void loadTemplates();
    }, [load, loadAudit, loadTemplates]);

    useEffect(() => {
        if (runForId != null) void loadRuns(runForId).catch((e) => showToast(e instanceof Error ? e.message : 'Runs failed', 'error'));
    }, [runForId, loadRuns, showToast]);

    const create = async () => {
        if (!user?.token) return;
        if (!createForm.name.trim()) {
            showToast('Enter a schedule name', 'warning');
            return;
        }
        try {
            const res = await fetch('/hr/scheduled-exports', {
                method: 'POST',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(formToPayload(createForm)),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Create failed');
            showToast('Schedule created', 'success');
            setCreateForm(emptyForm());
            await load();
            void loadAudit();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Create failed', 'error');
        }
    };

    const saveEdit = async () => {
        if (!user?.token || editingId == null) return;
        if (!editForm.name.trim()) {
            showToast('Enter a schedule name', 'warning');
            return;
        }
        try {
            const payload = formToPayload(editForm);
            const row = rows.find((r) => r.id === editingId);
            if (row?.webhookSecretSet && !String(payload.webhookSecret || '').trim()) {
                delete payload.webhookSecret;
            }
            const res = await fetch(`/hr/scheduled-exports/${editingId}`, {
                method: 'PATCH',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Update failed');
            showToast('Schedule updated', 'success');
            setEditingId(null);
            await load();
            void loadAudit();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Update failed', 'error');
        }
    };

    const toggle = async (r: ScheduledExportRow) => {
        if (!user?.token) return;
        try {
            const res = await fetch(`/hr/scheduled-exports/${r.id}`, {
                method: 'PATCH',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled: !r.enabled }),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Update failed');
            await load();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Update failed', 'error');
        }
    };

    const remove = async (id: number) => {
        if (!user?.token) return;
        if (!window.confirm('Delete this scheduled export?')) return;
        try {
            const res = await fetch(`/hr/scheduled-exports/${id}`, { method: 'DELETE', headers: { Authorization: `Bearer ${user.token}` } });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Delete failed');
            await load();
            void loadAudit();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Delete failed', 'error');
        }
    };

    const duplicate = async (r: ScheduledExportRow) => {
        if (!user?.token) return;
        try {
            const res = await fetch(`/hr/scheduled-exports/${r.id}/duplicate`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Duplicate failed');
            showToast('Duplicated', 'success');
            await load();
            void loadAudit();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Duplicate failed', 'error');
        }
    };

    const testRun = async (id: number, dryRun: boolean) => {
        if (!user?.token) return;
        try {
            const res = await fetch(`/hr/scheduled-exports/${id}/test-run`, {
                method: 'POST',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ dryRun }),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Test failed');
            showToast(dryRun ? `Dry run OK (${body.rowCount ?? 0} rows)` : 'Test run completed', 'success');
            await load();
            void loadAudit();
            if (runForId === id) void loadRuns(id);
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Test failed', 'error');
        }
    };

    const exportJson = async (r: ScheduledExportRow) => {
        if (!user?.token) return;
        const res = await fetch(`/hr/scheduled-exports/${r.id}/export-json`, { headers: { Authorization: `Bearer ${user.token}` } });
        const body = await res.json();
        if (!res.ok) {
            showToast(body.error || 'Export failed', 'error');
            return;
        }
        const blob = new Blob([JSON.stringify(body, null, 2)], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `schedule_${r.id}.json`;
        a.click();
        URL.revokeObjectURL(a.href);
    };

    const importFile = (file: File | null) => {
        if (!file || !user?.token) return;
        const reader = new FileReader();
        reader.onload = async () => {
            try {
                const text = String(reader.result || '');
                const json = JSON.parse(text) as { schedule?: Record<string, unknown> };
                const schedule = json.schedule || json;
                const res = await fetch('/hr/scheduled-exports/import', {
                    method: 'POST',
                    headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                    body: JSON.stringify({ schedule }),
                });
                const body = await res.json();
                if (!res.ok) throw new Error(body.error || 'Import failed');
                showToast('Imported schedule', 'success');
                await load();
                void loadAudit();
            } catch (e: unknown) {
                showToast(e instanceof Error ? e.message : 'Import failed', 'error');
            }
        };
        reader.readAsText(file);
    };

    const saveTemplate = async () => {
        if (!user?.token) return;
        const name = templateName.trim();
        if (!name) {
            showToast('Template name', 'warning');
            return;
        }
        try {
            const def = { ...formToPayload(createForm), name: createForm.name };
            const res = await fetch('/hr/scheduled-export-templates', {
                method: 'POST',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ name, definition: def }),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Save template failed');
            showToast('Template saved', 'success');
            setTemplateName('');
            void loadTemplates();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Save failed', 'error');
        }
    };

    const applyTemplate = (t: TemplateRow) => {
        const d = t.definition as Record<string, unknown>;
        const f = emptyForm();
        const merge = (k: keyof FormState, v: unknown) => {
            if (v === undefined || v === null) return;
            (f as Record<string, unknown>)[k] = v;
        };
        merge('name', String(d.name || t.name || ''));
        merge('enabled', d.enabled !== false);
        merge('emails', d.deliveryEmails);
        merge('ccEmails', d.deliveryCcEmails);
        merge('bccEmails', d.deliveryBccEmails);
        merge('replyTo', d.replyTo);
        merge('emailSubject', d.emailSubject);
        merge('emailBodyText', d.emailBodyText);
        merge('sendHtml', d.sendHtml !== false);
        merge('runEveryMinutes', d.runEveryMinutes ?? 1440);
        merge('scheduleMode', d.scheduleMode || 'interval');
        merge('cronExpression', d.cronExpression || f.cronExpression);
        merge('dailyAtTime', d.dailyAtTime || f.dailyAtTime);
        merge('scheduleTimezone', d.scheduleTimezone || f.scheduleTimezone);
        merge('dataSource', d.dataSource || 'app');
        merge('preset', d.dateRangePreset || f.preset);
        merge('format', d.exportFormat || f.format);
        merge('department', d.department || '');
        merge('maxExportRows', d.maxExportRows != null ? String(d.maxExportRows) : '');
        merge('sftp', !!d.sftpUpload);
        merge('s3', !!d.s3Upload);
        merge('webhookUrl', d.webhookUrl || '');
        merge('webhookSigningHeader', d.webhookSigningHeader || f.webhookSigningHeader);
        merge('alertEmails', d.alertEmailsOnFailure || '');
        merge('retryBackoffMinutes', d.retryBackoffMinutes ?? 15);
        merge('pgp', !!d.encryptAttachmentPgp);
        if (Array.isArray(d.roleIds)) f.roleIds = d.roleIds.map(Number).filter((n) => Number.isFinite(n));
        if (Array.isArray(d.siteIds)) f.siteIds = d.siteIds.map(Number).filter((n) => Number.isFinite(n));
        if (Array.isArray(d.shiftIds)) f.shiftIds = d.shiftIds.map(Number).filter((n) => Number.isFinite(n));
        setCreateForm(f);
        showToast(`Applied template “${t.name}”`, 'info');
    };

    const openEdit = (r: ScheduledExportRow) => {
        setEditingId(r.id);
        setEditForm(rowToForm(r));
    };

    const copyPageLink = async () => {
        try {
            const href = typeof window !== 'undefined' ? window.location.href : '';
            if (href && navigator.clipboard?.writeText) {
                await navigator.clipboard.writeText(href);
                showToast('Link copied to clipboard', 'success');
            } else {
                showToast('Clipboard not available', 'warning');
            }
        } catch {
            showToast('Could not copy link', 'error');
        }
    };

    const toggleId = (field: 'roleIds' | 'siteIds' | 'shiftIds', id: number, setForm: React.Dispatch<React.SetStateAction<FormState>>) => {
        setForm((prev) => {
            const arr = prev[field];
            const next = arr.includes(id) ? arr.filter((x) => x !== id) : [...arr, id];
            return { ...prev, [field]: next };
        });
    };

    const renderFilterPickers = (form: FormState, setForm: React.Dispatch<React.SetStateAction<FormState>>) => (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.75rem', marginTop: '0.5rem' }}>
            <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', marginBottom: '0.35rem' }}>Roles</div>
                <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.35rem', background: '#fff' }}>
                    {(roles || []).map((role) => (
                        <label key={role.id} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', padding: '0.1rem 0' }}>
                            <input type="checkbox" checked={form.roleIds.includes(Number(role.id))} onChange={() => toggleId('roleIds', Number(role.id), setForm)} />
                            {role.name}
                        </label>
                    ))}
                </div>
            </div>
            <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', marginBottom: '0.35rem' }}>Sites</div>
                <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.35rem', background: '#fff' }}>
                    {siteOptions.map((site) => (
                        <label key={String(site.id)} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', padding: '0.1rem 0' }}>
                            <input type="checkbox" checked={form.siteIds.includes(Number(site.id))} onChange={() => toggleId('siteIds', Number(site.id), setForm)} />
                            {site.name}
                        </label>
                    ))}
                </div>
            </div>
            <div>
                <div style={{ fontSize: '0.75rem', fontWeight: 600, color: '#64748b', marginBottom: '0.35rem' }}>Shifts</div>
                <div style={{ maxHeight: 120, overflowY: 'auto', border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.35rem', background: '#fff' }}>
                    {(shifts || []).map((shift) => (
                        <label key={shift.id} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.78rem', padding: '0.1rem 0' }}>
                            <input type="checkbox" checked={form.shiftIds.includes(Number(shift.id))} onChange={() => toggleId('shiftIds', Number(shift.id), setForm)} />
                            {shift.name}
                        </label>
                    ))}
                </div>
            </div>
        </div>
    );

    const formFields = (form: FormState, setForm: React.Dispatch<React.SetStateAction<FormState>>, isEdit: boolean) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155' }}>1) Basic details</div>
            <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <input type="checkbox" checked={form.enabled} onChange={(e) => setForm((f) => ({ ...f, enabled: e.target.checked }))} />
                Schedule is enabled
            </label>
            <input className="control-input" placeholder="Schedule name" value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} />
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '0.5rem' }}>
                <input className="control-input" placeholder="To (comma-separated)" value={form.emails} onChange={(e) => setForm((f) => ({ ...f, emails: e.target.value }))} />
                <input className="control-input" placeholder="CC (optional)" value={form.ccEmails} onChange={(e) => setForm((f) => ({ ...f, ccEmails: e.target.value }))} />
                <input className="control-input" placeholder="BCC (optional)" value={form.bccEmails} onChange={(e) => setForm((f) => ({ ...f, bccEmails: e.target.value }))} />
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.5rem' }}>
                <input className="control-input" placeholder="Reply-To" value={form.replyTo} onChange={(e) => setForm((f) => ({ ...f, replyTo: e.target.value }))} />
                <input className="control-input" placeholder="Subject override" value={form.emailSubject} onChange={(e) => setForm((f) => ({ ...f, emailSubject: e.target.value }))} />
            </div>
            <textarea className="control-input" placeholder="Email body (plain text, optional)" rows={2} value={form.emailBodyText} onChange={(e) => setForm((f) => ({ ...f, emailBodyText: e.target.value }))} />
            <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                <input type="checkbox" checked={form.sendHtml} onChange={(e) => setForm((f) => ({ ...f, sendHtml: e.target.checked }))} />
                Wrap body in simple HTML (better for SendGrid inbox rendering)
            </label>

            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginTop: '0.2rem' }}>2) Schedule timing</div>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(160px, 1fr))', gap: '0.5rem', alignItems: 'end' }}>
                <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    Schedule mode
                    <select className="control-input" value={form.scheduleMode} onChange={(e) => setForm((f) => ({ ...f, scheduleMode: e.target.value as ScheduleMode }))}>
                        <option value="interval">Every N minutes</option>
                        <option value="cron">Cron (server tz)</option>
                        <option value="daily_at">Daily at (wall clock)</option>
                    </select>
                </label>
                <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                    Timezone (cron / daily_at)
                    <select className="control-input" value={form.scheduleTimezone} onChange={(e) => setForm((f) => ({ ...f, scheduleTimezone: e.target.value }))}>
                        {TIMEZONES.map((z) => (
                            <option key={z} value={z}>
                                {z}
                            </option>
                        ))}
                    </select>
                </label>
            </div>
            {form.scheduleMode === 'interval' && (
                <label style={{ fontSize: '0.8rem', color: '#475569' }}>
                    Run every (minutes){' '}
                    <input type="number" className="control-input" style={{ width: '100px' }} min={15} max={10080} value={form.runEveryMinutes} onChange={(e) => setForm((f) => ({ ...f, runEveryMinutes: Number(e.target.value) || 1440 }))} />
                    <span style={{ marginLeft: '0.35rem', display: 'inline-flex', flexWrap: 'wrap', gap: '0.25rem' }}>
                        {[60, 360, 1440, 10080].map((m) => (
                            <button key={m} type="button" className="hr-btn secondary sm" onClick={() => setForm((f) => ({ ...f, runEveryMinutes: m }))}>
                                {m === 60 ? 'Hourly' : m === 360 ? '6h' : m === 1440 ? 'Daily' : 'Weekly'}
                            </button>
                        ))}
                    </span>
                </label>
            )}
            {form.scheduleMode === 'cron' && (
                <input className="control-input" placeholder="Cron e.g. 0 7 * * * (7:00 daily)" value={form.cronExpression} onChange={(e) => setForm((f) => ({ ...f, cronExpression: e.target.value }))} />
            )}
            {form.scheduleMode === 'daily_at' && (
                <label style={{ fontSize: '0.8rem', color: '#475569' }}>
                    Local time (HH:mm){' '}
                    <input className="control-input" style={{ width: '120px' }} value={form.dailyAtTime} onChange={(e) => setForm((f) => ({ ...f, dailyAtTime: e.target.value }))} />
                </label>
            )}
            <label style={{ fontSize: '0.78rem', color: '#64748b' }}>
                Pause until (optional, local)
                <input type="datetime-local" className="control-input" value={form.pauseUntil} onChange={(e) => setForm((f) => ({ ...f, pauseUntil: e.target.value }))} />
            </label>

            <div style={{ fontSize: '0.82rem', fontWeight: 700, color: '#334155', marginTop: '0.2rem' }}>3) Data and filters</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                <select className="control-input" value={form.dataSource} onChange={(e) => setForm((f) => ({ ...f, dataSource: e.target.value as 'app' | 'biometrics' }))}>
                    <option value="app">App attendance</option>
                    <option value="biometrics">Biometrics</option>
                </select>
                <select className="control-input" value={form.preset} onChange={(e) => setForm((f) => ({ ...f, preset: e.target.value as PresetValue }))}>
                    {PRESETS.map((p) => (
                        <option key={p.value} value={p.value}>
                            {p.label}
                        </option>
                    ))}
                </select>
                <select className="control-input" value={form.format} onChange={(e) => setForm((f) => ({ ...f, format: e.target.value as FormatValue }))}>
                    {FORMATS.map((p) => (
                        <option key={p.value} value={p.value}>
                            {p.label}
                        </option>
                    ))}
                </select>
            </div>
            <input className="control-input" placeholder="Department contains" value={form.department} onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))} />
            <label style={{ fontSize: '0.8rem', color: '#475569' }}>
                Max export rows (optional cap){' '}
                <input className="control-input" style={{ width: '120px' }} value={form.maxExportRows} onChange={(e) => setForm((f) => ({ ...f, maxExportRows: e.target.value }))} placeholder="unlimited" />
            </label>
            {renderFilterPickers(form, setForm)}
            <details style={{ borderTop: '1px solid #e2e8f0', paddingTop: '0.55rem', marginTop: '0.25rem' }}>
                <summary style={{ fontWeight: 700, fontSize: '0.82rem', color: '#334155', cursor: 'pointer' }}>
                    4) Advanced delivery options
                </summary>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', marginTop: '0.55rem' }}>
                    <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <input type="checkbox" checked={form.sftp} onChange={(e) => setForm((f) => ({ ...f, sftp: e.target.checked }))} />
                        SFTP upload (server-wide connection)
                    </label>
                    <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <input type="checkbox" checked={form.s3} onChange={(e) => setForm((f) => ({ ...f, s3: e.target.checked }))} />
                        S3 upload (server-wide bucket)
                    </label>
                    <input className="control-input" placeholder="Webhook URL (POST raw file)" value={form.webhookUrl} onChange={(e) => setForm((f) => ({ ...f, webhookUrl: e.target.value }))} />
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                        <input
                            className="control-input"
                            placeholder={isEdit ? 'Webhook secret (leave blank to keep)' : 'Webhook secret (HMAC-SHA256)'}
                            value={form.webhookSecret}
                            onChange={(e) => setForm((f) => ({ ...f, webhookSecret: e.target.value }))}
                        />
                        <input className="control-input" placeholder="Signing header name" value={form.webhookSigningHeader} onChange={(e) => setForm((f) => ({ ...f, webhookSigningHeader: e.target.value }))} />
                    </div>
                    <input className="control-input" placeholder="Alert emails on failure (comma-separated)" value={form.alertEmails} onChange={(e) => setForm((f) => ({ ...f, alertEmails: e.target.value }))} />
                    <label style={{ fontSize: '0.8rem', color: '#475569' }}>
                        Retry backoff (minutes, cron failures only){' '}
                        <input type="number" className="control-input" style={{ width: '90px' }} min={5} max={1440} value={form.retryBackoffMinutes} onChange={(e) => setForm((f) => ({ ...f, retryBackoffMinutes: Number(e.target.value) || 15 }))} />
                    </label>
                    <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
                        <input type="checkbox" checked={form.pgp} onChange={(e) => setForm((f) => ({ ...f, pgp: e.target.checked }))} />
                        PGP-encrypt attachment (server-wide public key)
                    </label>
                </div>
            </details>
            <button type="button" className="hr-btn secondary sm" onClick={() => setForm((f) => ({ ...f, roleIds: [], siteIds: [], shiftIds: [], department: '' }))}>
                Clear scope filters
            </button>
        </div>
    );

    return (
        <div className="management-view animate-fade-in">
            <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'space-between', gap: '0.75rem' }}>
                <h2 style={{ margin: 0 }}>Scheduled emails &amp; reports</h2>
                <button type="button" className="hr-btn secondary sm" onClick={() => void copyPageLink()}>
                    Copy page link
                </button>
            </div>
            <p style={{ margin: '6px 0 1rem', color: '#64748b', fontSize: '0.9rem', maxWidth: '56rem' }}>
                Create report schedules in four simple steps: set recipients, choose timing, choose data filters, then save.
                Use <strong>Dry run</strong> first to verify results without sending emails.
            </p>

            <div style={{ marginBottom: '1rem', padding: '0.75rem', border: '1px solid #e2e8f0', borderRadius: '10px', background: '#fafafa' }}>
                <strong style={{ fontSize: '0.85rem' }}>Templates &amp; import</strong>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginTop: '0.5rem', alignItems: 'center' }}>
                    <input className="control-input" style={{ maxWidth: '200px' }} placeholder="Template name" value={templateName} onChange={(e) => setTemplateName(e.target.value)} />
                    <button type="button" className="hr-btn secondary sm" onClick={() => void saveTemplate()}>
                        Save current as template
                    </button>
                    <label className="hr-btn secondary sm" style={{ cursor: 'pointer', margin: 0 }}>
                        Import JSON
                        <input type="file" accept="application/json,.json" style={{ display: 'none' }} onChange={(e) => importFile(e.target.files?.[0] || null)} />
                    </label>
                    {templates.map((t) => (
                        <button key={t.id} type="button" className="hr-btn secondary sm" onClick={() => applyTemplate(t)}>
                            Apply: {t.name}
                        </button>
                    ))}
                </div>
            </div>

            <div
                style={{
                    display: 'grid',
                    gridTemplateColumns: 'minmax(300px, 420px) 1fr',
                    gap: '1.25rem',
                    alignItems: 'start',
                }}
                className="scheduled-reports-grid"
            >
                <div style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '10px', background: '#fafafa' }}>
                    <h3 style={{ margin: '0 0 0.3rem', fontSize: '1rem' }}>New schedule</h3>
                    <p style={{ margin: '0 0 0.65rem', fontSize: '0.8rem', color: '#64748b' }}>
                        Tip: start with required fields only. Advanced options are optional.
                    </p>
                    {formFields(createForm, setCreateForm, false)}
                    <button type="button" className="hr-btn primary" style={{ marginTop: '0.75rem' }} onClick={() => void create()}>
                        Add schedule
                    </button>
                </div>

                <div style={{ padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '10px', background: '#fff', minWidth: 0 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '0.75rem' }}>
                        <h3 style={{ margin: 0, fontSize: '1rem' }}>Configured schedules</h3>
                        <button type="button" className="hr-btn secondary sm" onClick={() => void load()} disabled={loading}>
                            {loading ? 'Refreshing…' : 'Refresh'}
                        </button>
                    </div>
                    <div className="mgmt-table-container" style={{ overflowX: 'auto' }}>
                        <table className="mgmt-table" style={{ fontSize: '0.72rem' }}>
                            <thead>
                                <tr>
                                    <th>Name</th>
                                    <th>Status</th>
                                    <th>Mode</th>
                                    <th>Next</th>
                                    <th>Last</th>
                                    <th>Fail#</th>
                                    <th style={{ minWidth: 200 }}>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {rows.map((r) => (
                                    <tr key={r.id}>
                                        <td>
                                            <strong>{r.name}</strong>
                                            {r.lastError ? <div style={{ color: '#b91c1c', fontSize: '0.65rem', marginTop: 2 }}>{r.lastError}</div> : null}
                                            <div style={{ color: '#64748b', fontSize: '0.65rem', marginTop: 2 }}>{filterSummary(r, roleNames, siteNames, shiftNames)}</div>
                                        </td>
                                        <td>
                                            <span
                                                style={{
                                                    fontSize: '0.7rem',
                                                    fontWeight: 700,
                                                    borderRadius: '999px',
                                                    padding: '0.15rem 0.5rem',
                                                    color: r.enabled ? '#166534' : '#64748b',
                                                    background: r.enabled ? '#dcfce7' : '#e2e8f0',
                                                }}
                                            >
                                                {r.enabled ? 'Active' : 'Paused'}
                                            </span>
                                        </td>
                                        <td>{r.scheduleMode || 'interval'}</td>
                                        <td>{r.nextRunAt ? new Date(r.nextRunAt).toLocaleString() : '—'}</td>
                                        <td>{r.lastRunAt ? new Date(r.lastRunAt).toLocaleString() : '—'}</td>
                                        <td>{r.consecutiveFailures ?? 0}</td>
                                        <td style={{ whiteSpace: 'normal' }}>
                                            <button type="button" className="hr-btn secondary sm" onClick={() => openEdit(r)}>
                                                Edit
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void toggle(r)}>
                                                {r.enabled ? 'Pause' : 'Resume'}
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => setRunForId(r.id)}>
                                                Run history
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void duplicate(r)}>
                                                Duplicate
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void testRun(r.id, true)}>
                                                Dry run
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void testRun(r.id, false)}>
                                                Send test
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void exportJson(r)}>
                                                Export JSON
                                            </button>{' '}
                                            <button type="button" className="hr-btn secondary sm" onClick={() => void remove(r.id)}>
                                                Delete
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                    {rows.length === 0 && !loading && <p style={{ fontSize: '0.85rem', color: '#94a3b8', marginTop: '0.5rem' }}>No schedules yet.</p>}
                </div>
            </div>

            <div style={{ marginTop: '1.25rem', padding: '1rem', border: '1px solid #e2e8f0', borderRadius: '10px', background: '#fff' }}>
                <h3 style={{ margin: '0 0 0.5rem', fontSize: '1rem' }}>Audit log</h3>
                <div className="mgmt-table-container" style={{ maxHeight: 240, overflow: 'auto' }}>
                    <table className="mgmt-table" style={{ fontSize: '0.72rem' }}>
                        <thead>
                            <tr>
                                <th>When</th>
                                <th>Action</th>
                                <th>Schedule</th>
                                <th>Payload</th>
                            </tr>
                        </thead>
                        <tbody>
                            {audit.map((a) => (
                                <tr key={a.id}>
                                    <td>{new Date(a.createdAt).toLocaleString()}</td>
                                    <td>{a.action}</td>
                                    <td>{a.scheduledExportId ?? '—'}</td>
                                    <td style={{ maxWidth: 360, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{JSON.stringify(a.payload)}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                {audit.length === 0 && <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>No audit entries yet.</p>}
            </div>

            {editingId !== null && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        zIndex: 2100,
                        background: 'rgba(15,23,42,0.45)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '1rem',
                    }}
                    role="dialog"
                    aria-modal="true"
                    aria-labelledby="sched-edit-title"
                    onClick={() => setEditingId(null)}
                >
                    <div
                        style={{
                            background: '#fff',
                            borderRadius: '12px',
                            maxWidth: '720px',
                            width: '100%',
                            maxHeight: '92vh',
                            overflow: 'auto',
                            padding: '1.25rem',
                            boxShadow: '0 20px 50px rgba(0,0,0,0.2)',
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <h3 id="sched-edit-title" style={{ margin: '0 0 0.75rem' }}>
                            Edit schedule
                        </h3>
                        {formFields(editForm, setEditForm, true)}
                        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
                            <button type="button" className="hr-btn secondary" onClick={() => setEditingId(null)}>
                                Cancel
                            </button>
                            <button type="button" className="hr-btn primary" onClick={() => void saveEdit()}>
                                Save changes
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {runForId !== null && (
                <div
                    style={{
                        position: 'fixed',
                        inset: 0,
                        zIndex: 2100,
                        background: 'rgba(15,23,42,0.45)',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        padding: '1rem',
                    }}
                    role="dialog"
                    aria-modal="true"
                    onClick={() => setRunForId(null)}
                >
                    <div
                        style={{
                            background: '#fff',
                            borderRadius: '12px',
                            maxWidth: '800px',
                            width: '100%',
                            maxHeight: '85vh',
                            overflow: 'auto',
                            padding: '1.25rem',
                        }}
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
                            <h3 style={{ margin: 0 }}>Run history #{runForId}</h3>
                            <button type="button" className="hr-btn secondary sm" onClick={() => setRunForId(null)}>
                                Close
                            </button>
                        </div>
                        <table className="mgmt-table" style={{ fontSize: '0.72rem' }}>
                            <thead>
                                <tr>
                                    <th>Started</th>
                                    <th>Status</th>
                                    <th>Rows</th>
                                    <th>Email</th>
                                    <th>SFTP</th>
                                    <th>S3</th>
                                    <th>Hook</th>
                                    <th>Error</th>
                                </tr>
                            </thead>
                            <tbody>
                                {runs.map((x) => (
                                    <tr key={x.id}>
                                        <td>{new Date(x.startedAt).toLocaleString()}</td>
                                        <td>{x.status}</td>
                                        <td>
                                            {x.rowCount ?? '—'}
                                            {x.truncated ? ' (cap)' : ''}
                                        </td>
                                        <td>{x.emailOk == null ? '—' : x.emailOk ? 'Y' : 'N'}</td>
                                        <td>{x.sftpOk == null ? '—' : x.sftpOk ? 'Y' : 'N'}</td>
                                        <td>{x.s3Ok == null ? '—' : x.s3Ok ? 'Y' : 'N'}</td>
                                        <td>{x.webhookOk == null ? '—' : x.webhookOk ? 'Y' : 'N'}</td>
                                        <td style={{ maxWidth: 200, wordBreak: 'break-word' }}>{x.errorMessage || '—'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                        {runs.length === 0 && <p style={{ fontSize: '0.8rem', color: '#94a3b8' }}>No runs yet.</p>}
                    </div>
                </div>
            )}

            <style>{`
                @media (max-width: 960px) {
                    .scheduled-reports-grid {
                        grid-template-columns: 1fr !important;
                    }
                }
            `}</style>
        </div>
    );
};

export default ScheduledReportsConfigView;
