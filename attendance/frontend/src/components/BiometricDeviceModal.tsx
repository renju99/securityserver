import React, { useCallback, useEffect, useMemo, useState } from 'react';
import type { Site } from '../types';
import {
    BIOMETRIC_DEVICE_PRESETS,
    getBiometricPreset,
    mergePresetDefaults,
    type BiometricConfigField,
} from '../config/biometricDevicePresets';
import './BiometricDeviceModal.css';

export type BiometricFormState = {
    id?: number;
    name: string;
    deviceKey: string;
    siteId: string | number | '';
    type: string;
    ipAddress: string;
    port: string | number | '';
    config: Record<string, string | number | boolean | ''>;
};

function normalizeFromApi(row: any): BiometricFormState {
    let cfg = row.config;
    if (typeof cfg === 'string') {
        try {
            cfg = JSON.parse(cfg);
        } catch {
            cfg = {};
        }
    }
    if (!cfg || typeof cfg !== 'object' || Array.isArray(cfg)) cfg = {};

    const type = row.type || 'RA08';
    return {
        id: row.id,
        name: row.name || '',
        deviceKey: row.deviceKey ?? row.device_key ?? '',
        siteId: row.siteId ?? row.site_id ?? '',
        type,
        ipAddress: row.ipAddress ?? row.ip_address ?? '',
        port: row.port ?? '',
        config: mergePresetDefaults(type, cfg as Record<string, string | number | boolean>),
    };
}

function defaultNewForm(): BiometricFormState {
    const t = 'RA08';
    return {
        name: '',
        deviceKey: '',
        siteId: '',
        type: t,
        ipAddress: '',
        port: '',
        config: mergePresetDefaults(t, {}),
    };
}

type BioTab = 'type' | 'details' | 'integration' | 'test' | 'review';

const WIZARD_TABS: BioTab[] = ['type', 'details', 'integration', 'test', 'review'];

export type BiometricConnectionCheck = {
    id: string;
    label: string;
    ok: boolean;
    detail: string;
    severity?: string;
};

interface BiometricDeviceModalProps {
    open: boolean;
    onClose: () => void;
    initial: any | null;
    sites: Site[];
    authToken: string;
    onSaved: () => void;
    showToast: (message: string, type: 'success' | 'error' | 'info' | 'warning') => void;
}

function usePortalOrigin(): string {
    if (typeof window === 'undefined') return '';
    return `${window.location.protocol}//${window.location.host}`;
}

const BiometricDeviceModal: React.FC<BiometricDeviceModalProps> = ({
    open,
    onClose,
    initial,
    sites,
    authToken,
    onSaved,
    showToast,
}) => {
    const [form, setForm] = useState<BiometricFormState>(defaultNewForm);
    const [saving, setSaving] = useState(false);
    const [tab, setTab] = useState<BioTab>('type');
    const [presetSearch, setPresetSearch] = useState('');
    const [testLoading, setTestLoading] = useState(false);
    const [testResult, setTestResult] = useState<{ ok: boolean; checks: BiometricConnectionCheck[] } | null>(null);

    const portalOrigin = usePortalOrigin();

    useEffect(() => {
        if (!open) return;
        const isEdit = !!(initial?.id || initial?.device_key || initial?.deviceKey);
        setForm(isEdit ? normalizeFromApi(initial) : defaultNewForm());
        setTab(isEdit ? 'details' : 'type');
        setPresetSearch('');
        setTestResult(null);
        setTestLoading(false);
    }, [open, initial?.id, initial?.device_key, initial?.deviceKey]);

    const preset = useMemo(() => getBiometricPreset(form.type), [form.type]);

    const filteredPresets = useMemo(() => {
        const q = presetSearch.trim().toLowerCase();
        if (!q) return BIOMETRIC_DEVICE_PRESETS;
        return BIOMETRIC_DEVICE_PRESETS.filter(
            (p) =>
                p.label.toLowerCase().includes(q) ||
                p.manufacturer.toLowerCase().includes(q) ||
                p.type.toLowerCase().includes(q) ||
                p.description.toLowerCase().includes(q)
        );
    }, [presetSearch]);

    const setConfigField = (key: string, value: string | number | boolean | '') => {
        setForm((prev) => ({
            ...prev,
            config: { ...prev.config, [key]: value },
        }));
    };

    const selectPreset = (nextType: string) => {
        setForm((prev) => ({
            ...prev,
            type: nextType,
            config: mergePresetDefaults(nextType, prev.config),
        }));
    };

    const copyText = useCallback(
        async (label: string, text: string) => {
            try {
                await navigator.clipboard.writeText(text);
                showToast(`${label} copied`, 'success');
            } catch {
                showToast('Could not copy — select the text manually', 'warning');
            }
        },
        [showToast]
    );

    const validateIdentityForLaterSteps = () => {
        if (!form.name.trim()) {
            showToast('Add a display name on step 2.', 'warning');
            setTab('details');
            return false;
        }
        if (!form.deviceKey.trim()) {
            showToast('Add the device key or serial on step 2.', 'warning');
            setTab('details');
            return false;
        }
        if (!form.id && form.deviceKey.trim().length < 4) {
            showToast('Device key must be at least 4 characters.', 'warning');
            setTab('details');
            return false;
        }
        return true;
    };

    const runConnectionTests = useCallback(async () => {
        if (!authToken) return;
        if (!validateIdentityForLaterSteps()) return;
        setTestLoading(true);
        try {
            const portVal = form.port === '' || form.port === undefined ? null : String(form.port);
            const cfg: Record<string, string | number | boolean> = {};
            for (const [k, v] of Object.entries(form.config)) {
                if (v === '') continue;
                if (typeof v === 'number' && !Number.isFinite(v)) continue;
                cfg[k] = v as string | number | boolean;
            }
            const res = await fetch('/hr/biometrics/devices/connection-test', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${authToken}`,
                },
                body: JSON.stringify({
                    type: form.type,
                    deviceKey: form.deviceKey.trim(),
                    ipAddress: form.ipAddress.trim() || null,
                    port: portVal,
                    config: cfg,
                    excludeDeviceId: form.id ?? null,
                }),
            });
            const data = (await res.json().catch(() => ({}))) as { ok?: boolean; checks?: BiometricConnectionCheck[]; error?: string };
            if (!res.ok) {
                showToast(data.error || 'Connection test failed', 'error');
                setTestResult(null);
                return;
            }
            const payload = { ok: !!data.ok, checks: Array.isArray(data.checks) ? data.checks : [] };
            setTestResult(payload);
            showToast(
                payload.ok ? 'Connection tests finished' : 'Tests finished — resolve duplicate key before saving',
                payload.ok ? 'success' : 'warning'
            );
        } catch {
            showToast('Network error running tests', 'error');
            setTestResult(null);
        } finally {
            setTestLoading(false);
        }
    }, [authToken, form, showToast]);

    const goBack = () => {
        const i = WIZARD_TABS.indexOf(tab);
        if (i <= 0) return;
        setTab(WIZARD_TABS[i - 1]);
    };

    const goNext = () => {
        const i = WIZARD_TABS.indexOf(tab);
        if (i < 0 || i >= WIZARD_TABS.length - 1) return;
        const next = WIZARD_TABS[i + 1];
        if (next === 'integration' || next === 'test') {
            if (!validateIdentityForLaterSteps()) return;
        }
        setTab(next);
    };

    const renderField = (field: BiometricConfigField) => {
        const raw = form.config[field.key];
        const value =
            raw === undefined || raw === null
                ? ''
                : typeof raw === 'boolean'
                  ? String(raw)
                  : String(raw);

        if (field.type === 'textarea') {
            return (
                <textarea
                    key={field.key}
                    className="bio-textarea-wide"
                    value={value}
                    required={field.required}
                    placeholder={field.placeholder}
                    onChange={(e) => setConfigField(field.key, e.target.value)}
                    rows={3}
                />
            );
        }

        if (field.type === 'select' && field.options) {
            return (
                <select
                    key={field.key}
                    className="bio-input-wide"
                    value={value}
                    required={field.required}
                    onChange={(e) => setConfigField(field.key, e.target.value)}
                >
                    {field.options.map((o) => (
                        <option key={o.value} value={o.value}>
                            {o.label}
                        </option>
                    ))}
                </select>
            );
        }

        const inputType =
            field.type === 'password' ? 'password' : field.type === 'number' ? 'number' : field.type === 'url' ? 'url' : 'text';

        return (
            <input
                key={field.key}
                className="bio-input-wide"
                type={inputType}
                value={value}
                required={field.required}
                placeholder={field.placeholder}
                onChange={(e) => {
                    const v = e.target.value;
                    if (field.type === 'number') {
                        if (v === '') setConfigField(field.key, '');
                        else {
                            const n = parseFloat(v);
                            setConfigField(field.key, Number.isFinite(n) ? n : 0);
                        }
                    } else {
                        setConfigField(field.key, v);
                    }
                }}
            />
        );
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (tab !== 'review') return;
        if (!authToken) return;
        const dupBlocking = testResult?.checks.some((c) => c.id === 'device_key_unique' && c.ok === false);
        if (dupBlocking) {
            showToast('Duplicate device key — go back to step 2 or run tests on step 4.', 'error');
            setTab('test');
            return;
        }
        if (!form.name.trim()) {
            showToast('Add a display name on step 2.', 'warning');
            setTab('details');
            return;
        }
        if (!form.deviceKey.trim()) {
            showToast('Add the device key or serial on step 2.', 'warning');
            setTab('details');
            return;
        }
        setSaving(true);
        try {
            const method = form.id ? 'PATCH' : 'POST';
            const url = form.id ? `/hr/biometrics/devices/${form.id}` : '/hr/biometrics/devices';
            const portVal = form.port === '' || form.port === undefined ? null : String(form.port);
            const cfg: Record<string, string | number | boolean> = {};
            for (const [k, v] of Object.entries(form.config)) {
                if (v === '') continue;
                if (typeof v === 'number' && !Number.isFinite(v)) continue;
                cfg[k] = v as string | number | boolean;
            }

            const payload: Record<string, unknown> = {
                name: form.name.trim(),
                deviceKey: form.deviceKey.trim(),
                siteId: form.siteId === '' ? null : form.siteId,
                type: form.type,
                ipAddress: form.ipAddress.trim() || null,
                port: portVal,
                config: cfg,
            };

            const res = await fetch(url, {
                method,
                headers: {
                    'Content-Type': 'application/json',
                    Authorization: `Bearer ${authToken}`,
                },
                body: JSON.stringify(payload),
            });

            if (res.ok) {
                showToast(form.id ? 'Device updated' : 'Device registered', 'success');
                onSaved();
                onClose();
            } else {
                const err = await res.json().catch(() => ({}));
                const msg = (err as { error?: string }).error || 'Failed to save device';
                showToast(msg, 'error');
                if (res.status === 409) {
                    setTab('details');
                }
            }
        } catch {
            showToast('Network error', 'error');
        } finally {
            setSaving(false);
        }
    };

    const iclockBase = portalOrigin ? `${portalOrigin}/iclock/` : '';
    const snExample = form.deviceKey.trim() || 'YOUR_DEVICE_SN';
    const showZkIclockUrls = form.type === 'ZKTeco_ADMS';

    if (!open) return null;

    const deviceKeyLabel = preset.deviceKeyLabel || 'Device key / identifier';
    const siteLabel =
        form.siteId === '' || form.siteId === undefined
            ? 'All sites'
            : sites.find((s) => String(s.id) === String(form.siteId))?.name || '—';
    const stepNum = WIZARD_TABS.indexOf(tab) + 1;

    return (
        <div className="modal-overlay">
            <div className={`modal-content bio-modal-shell`}>
                <h3>{form.id ? 'Edit terminal (wizard)' : 'Add terminal — admin wizard'}</h3>
                <p className="bio-modal-lead">
                    Step {stepNum} of {WIZARD_TABS.length}: choose the device family, identity, reachability and URLs, run
                    server-side connection checks, then review and save. Supported ingest paths (RA08 HTTP, ZKTeco iClock
                    ATTLOG, etc.) are enforced on the API automatically.
                </p>

                <form onSubmit={handleSubmit}>
                    <div className="bio-modal-body">
                    <div className="bio-tabs" role="tablist" aria-label="Configuration steps">
                        {WIZARD_TABS.map((t) => {
                            const labels: Record<BioTab, string> = {
                                type: '1. Type',
                                details: '2. Identity',
                                integration: '3. Network',
                                test: '4. Test',
                                review: '5. Review',
                            };
                            return (
                                <button
                                    key={t}
                                    type="button"
                                    role="tab"
                                    aria-selected={tab === t}
                                    className={`bio-tab ${tab === t ? 'active' : ''}`}
                                    onClick={() => setTab(t)}
                                >
                                    {labels[t]}
                                </button>
                            );
                        })}
                    </div>

                    {tab === 'type' && (
                        <div>
                            <p className="bio-section-title" style={{ marginBottom: '0.5rem' }}>
                                Search or tap a card
                            </p>
                            <input
                                type="search"
                                className="bio-preset-search"
                                placeholder="Filter by brand or model…"
                                value={presetSearch}
                                onChange={(e) => setPresetSearch(e.target.value)}
                                aria-label="Filter device types"
                            />
                            {filteredPresets.length === 0 ? (
                                <p className="bio-muted">No matches — clear the search box to see all types.</p>
                            ) : (
                                <div className="bio-preset-grid">
                                    {filteredPresets.map((p) => (
                                        <button
                                            key={p.type}
                                            type="button"
                                            className={`bio-preset-card ${form.type === p.type ? 'selected' : ''}`}
                                            onClick={() => selectPreset(p.type)}
                                        >
                                            <div className="bio-preset-manuf">{p.manufacturer}</div>
                                            <div className="bio-preset-title">{p.label}</div>
                                        </button>
                                    ))}
                                </div>
                            )}
                            <p className="bio-desc" style={{ marginTop: '1rem' }}>
                                {preset.description}
                            </p>
                            {preset.uaeNotes ? (
                                <p className="bio-callout">
                                    <strong>UAE:</strong> {preset.uaeNotes}
                                </p>
                            ) : null}
                        </div>
                    )}

                    {tab === 'details' && (
                        <div>
                            <div className="form-group">
                                <label>Terminal display name *</label>
                                <input
                                    type="text"
                                    className="bio-input-wide"
                                    value={form.name}
                                    onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                                    placeholder="e.g. Main gate — Horus"
                                />
                                <p className="bio-muted">Shown in logs and on device cards in this dashboard.</p>
                            </div>

                            <div className="form-group">
                                <label>{form.id ? `${deviceKeyLabel} (locked)` : `${deviceKeyLabel} *`}</label>
                                <input
                                    type="text"
                                    className="bio-input-wide"
                                    value={form.deviceKey}
                                    onChange={(e) => setForm((p) => ({ ...p, deviceKey: e.target.value }))}
                                    disabled={!!form.id}
                                    placeholder={preset.deviceKeyHint}
                                />
                                <p className="bio-muted">{preset.deviceKeyHint}</p>
                            </div>

                            <div className="form-group">
                                <label>Site</label>
                                <select
                                    className="bio-input-wide"
                                    value={form.siteId === '' || form.siteId === undefined ? '' : String(form.siteId)}
                                    onChange={(e) => setForm((p) => ({ ...p, siteId: e.target.value === '' ? '' : e.target.value }))}
                                >
                                    <option value="">All sites / not linked to one site</option>
                                    {sites.map((s) => (
                                        <option key={s.id} value={s.id}>
                                            {s.name}
                                        </option>
                                    ))}
                                </select>
                                <p className="bio-muted">Optional — helps supervisors filter by location.</p>
                            </div>
                        </div>
                    )}

                    {tab === 'integration' && (
                        <div>
                            <div className="bio-section">
                                <h4 className="bio-section-title">How to reach this terminal (optional)</h4>
                                <p className="bio-desc">
                                    Many sites do <strong>not</strong> have a static public IP on the device. Enter the
                                    hostname your <strong>DynDNS</strong> (or No-IP, DuckDNS, router DDNS, etc.) client
                                    keeps updated — pollers and your team use the same name even when the ISP changes the
                                    address. A private LAN IP is fine too. This is only for display and ops notes;{' '}
                                    <strong>ZKTeco ADMS push</strong> uses your portal URLs below, not this field.
                                </p>
                                <p className="bio-callout">
                                    <strong>DynDNS:</strong> put the FQDN the device updates (for example{' '}
                                    <span className="bio-code">gate-office.dyndns.org</span>) in the host field; keep the
                                    port your integrator uses (often <span className="bio-code">4370</span> for ZK TCP).
                                </p>
                                <div style={{ display: 'grid', gridTemplateColumns: '1fr 120px', gap: '0.75rem' }}>
                                    <div className="form-group" style={{ marginBottom: 0 }}>
                                        <label>Hostname (DynDNS) or IP</label>
                                        <input
                                            type="text"
                                            className="bio-input-wide"
                                            value={form.ipAddress}
                                            onChange={(e) => setForm((p) => ({ ...p, ipAddress: e.target.value }))}
                                            placeholder="e.g. zk-main.dyndns.org or 192.168.1.50"
                                        />
                                    </div>
                                    <div className="form-group" style={{ marginBottom: 0 }}>
                                        <label>Port</label>
                                        <input
                                            type="text"
                                            className="bio-input-wide"
                                            value={form.port === undefined || form.port === null ? '' : String(form.port)}
                                            onChange={(e) => setForm((p) => ({ ...p, port: e.target.value }))}
                                            placeholder="4370"
                                        />
                                    </div>
                                </div>
                            </div>

                            {showZkIclockUrls && portalOrigin ? (
                                <div className="bio-section">
                                    <h4 className="bio-section-title">URLs for the device (copy for installer)</h4>
                                    <p className="bio-desc">
                                        Point the terminal <strong>push / ADMS server</strong> at this site. The device
                                        serial (<span className="bio-code">SN</span>) must match{' '}
                                        <span className="bio-code">{deviceKeyLabel}</span> above. Only{' '}
                                        <strong>text attendance</strong> (ATTLOG) is stored; photo push is ignored.
                                    </p>
                                    <div className="bio-url-panel">
                                        <div className="bio-url-panel-title">iClock base path</div>
                                        <div className="bio-url-row">
                                            <input className="bio-url-input" readOnly value={iclockBase} aria-label="iClock base URL" />
                                            <button
                                                type="button"
                                                className="bio-copy-btn"
                                                onClick={() => copyText('Base URL', iclockBase)}
                                            >
                                                Copy
                                            </button>
                                        </div>
                                    </div>
                                    <div className="bio-url-panel">
                                        <div className="bio-url-panel-title">Example — device check (GET)</div>
                                        <div className="bio-url-row">
                                            <input
                                                className="bio-url-input"
                                                readOnly
                                                value={`${portalOrigin}/iclock/getrequest?SN=${encodeURIComponent(snExample)}`}
                                                aria-label="Sample getrequest URL"
                                            />
                                            <button
                                                type="button"
                                                className="bio-copy-btn"
                                                onClick={() =>
                                                    copyText(
                                                        'Sample GET URL',
                                                        `${portalOrigin}/iclock/getrequest?SN=${encodeURIComponent(snExample)}`
                                                    )
                                                }
                                            >
                                                Copy
                                            </button>
                                        </div>
                                    </div>
                                    <div className="bio-url-panel">
                                        <div className="bio-url-panel-title">Attendance push (POST path)</div>
                                        <div className="bio-url-row">
                                            <input
                                                className="bio-url-input"
                                                readOnly
                                                value={`${portalOrigin}/iclock/cdata?SN=${encodeURIComponent(snExample)}&table=ATTLOG`}
                                                aria-label="Sample cdata URL"
                                            />
                                            <button
                                                type="button"
                                                className="bio-copy-btn"
                                                onClick={() =>
                                                    copyText(
                                                        'Sample POST query',
                                                        `${portalOrigin}/iclock/cdata?SN=${encodeURIComponent(snExample)}&table=ATTLOG`
                                                    )
                                                }
                                            >
                                                Copy
                                            </button>
                                        </div>
                                        <p className="bio-muted" style={{ marginTop: '0.5rem' }}>
                                            Staff punches use the user ID from the device — set each employee&apos;s{' '}
                                            <span className="bio-code">staff_id</span> in HR to match that ID (or set env{' '}
                                            <span className="bio-code">ZK_ATTLOG_STAFF_PREFIX</span> on the server).
                                        </p>
                                    </div>
                                </div>
                            ) : null}

                            {form.type === 'RA08' ? (
                                <div className="bio-section">
                                    <h4 className="bio-section-title">RA08 listener</h4>
                                    <p className="bio-desc">
                                        The Docker <span className="bio-code">ra08-listener</span> must POST to{' '}
                                        <span className="bio-code">/api/biometrics/log</span> with header{' '}
                                        <span className="bio-code">Authorization: Bearer …</span> using the same secret as{' '}
                                        <span className="bio-code">BIOMETRIC_INGEST_TOKEN</span> on the API.
                                    </p>
                                </div>
                            ) : null}

                            {form.type === 'GENERIC_HTTP' ? (
                                <div className="bio-section">
                                    <h4 className="bio-section-title">Generic HTTP</h4>
                                    <p className="bio-desc">
                                        Your bridge should POST JSON to <span className="bio-code">/api/biometrics/log</span>{' '}
                                        with the shared ingest token. Map fields in the notes below.
                                    </p>
                                </div>
                            ) : null}

                            {preset.fields.length > 0 ? (
                                <div className="bio-section">
                                    <h4 className="bio-section-title">Saved vendor / installer notes</h4>
                                    <p className="bio-desc">
                                        These values are stored with the terminal so your team has a single place for ports,
                                        middleware hostnames, and other settings (the server does not auto-connect using them
                                        yet, except ZKTeco iClock paths above).
                                    </p>
                                    {preset.fields.map((field) => (
                                        <div className="form-group" key={field.key}>
                                            <label>{field.label}</label>
                                            {renderField(field)}
                                            {field.hint ? <p className="bio-field-hint">{field.hint}</p> : null}
                                        </div>
                                    ))}
                                </div>
                            ) : null}
                        </div>
                    )}

                    {tab === 'test' && (
                        <div>
                            <h4 className="bio-section-title">Connection test (server-side)</h4>
                            <p className="bio-desc">
                                The API runs checks for this device type: duplicate device key in the directory, DNS/TCP
                                when a host is set, iClock ping for ZKTeco ADMS, ingest route for RA08 / generic HTTP, and
                                ingest token warnings. This does not replace a full ZK SDK handshake.
                            </p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', marginBottom: '1rem' }}>
                                <button
                                    type="button"
                                    className="btn-primary"
                                    onClick={() => void runConnectionTests()}
                                    disabled={testLoading}
                                >
                                    {testLoading ? 'Running tests…' : 'Run connection tests'}
                                </button>
                            </div>
                            {testResult ? (
                                <ul className="bio-check-list" aria-label="Test results">
                                    {testResult.checks.map((c) => (
                                        <li
                                            key={c.id}
                                            className={`bio-check-row ${c.ok ? 'bio-check-pass' : c.severity === 'error' ? 'bio-check-fail' : 'bio-check-warn'}`}
                                        >
                                            <span className="bio-check-badge">{c.ok ? 'OK' : '!'}</span>
                                            <div>
                                                <div className="bio-check-label">{c.label}</div>
                                                <div className="bio-check-detail">{c.detail}</div>
                                            </div>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p className="bio-muted">Run tests above, then go to Review. You can continue without running if you accept the risk.</p>
                            )}
                            {testResult && !testResult.ok ? (
                                <p className="bio-callout" style={{ marginTop: '1rem' }}>
                                    <strong>Blocking:</strong> duplicate device key must be fixed before save. Warnings (TCP,
                                    iClock reachability) are advisory — firewalls and proxies often block the API from seeing
                                    the same path browsers use.
                                </p>
                            ) : null}
                        </div>
                    )}

                    {tab === 'review' && (
                        <div>
                            <h4 className="bio-section-title">Review &amp; save</h4>
                            {!testResult ? (
                                <p className="bio-callout">
                                    Connection tests were not run in step 4 — recommended for first-time registration.
                                </p>
                            ) : null}
                            <dl className="bio-review-dl">
                                <dt>Device type</dt>
                                <dd>{preset.label}</dd>
                                <dt>Display name</dt>
                                <dd>{form.name.trim() || '—'}</dd>
                                <dt>{deviceKeyLabel}</dt>
                                <dd style={{ fontFamily: 'ui-monospace, monospace' }}>{form.deviceKey.trim() || '—'}</dd>
                                <dt>Site</dt>
                                <dd>{siteLabel}</dd>
                                <dt>Hostname / IP</dt>
                                <dd>{form.ipAddress.trim() || '—'}</dd>
                                <dt>Port</dt>
                                <dd>{form.port === '' || form.port === undefined ? '—' : String(form.port)}</dd>
                            </dl>
                            <p className="bio-muted" style={{ marginTop: '0.75rem' }}>
                                Vendor fields from step 3 are included in the saved JSON config.
                            </p>
                        </div>
                    )}
                    </div>

                    <div className="modal-footer" style={{ flexShrink: 0 }}>
                        <button type="button" className="btn-secondary" onClick={onClose}>
                            Cancel
                        </button>
                        <div>
                            {tab !== 'type' ? (
                                <button type="button" className="btn-secondary" onClick={goBack}>
                                    Back
                                </button>
                            ) : null}
                            {tab !== 'review' ? (
                                <button type="button" className="btn-secondary" onClick={goNext}>
                                    Next
                                </button>
                            ) : null}
                            {tab === 'review' ? (
                                <button type="submit" className="btn-primary" disabled={saving}>
                                    {saving ? 'Saving…' : form.id ? 'Save changes' : 'Save terminal'}
                                </button>
                            ) : null}
                        </div>
                    </div>
                </form>
            </div>
        </div>
    );
};

export default BiometricDeviceModal;
