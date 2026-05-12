import React, { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';

type OutboundMode = 'none' | 'sendgrid' | 'smtp';

type EmailSettingsPublic = {
    outboundMode: OutboundMode;
    sendgridFromEmail: string;
    hasSendgridApiKey: boolean;
    smtpHost: string;
    smtpPort: number;
    smtpSecure: boolean;
    smtpUser: string;
    hasSmtpPass: boolean;
    smtpFrom: string;
    imapEnabled: boolean;
    imapHost: string;
    imapPort: number;
    imapSecure: boolean;
    imapUser: string;
    hasImapPass: boolean;
    imapMailbox: string;
};

const emptyModel = (): EmailSettingsPublic & { sendgridApiKey: string; smtpPass: string; imapPass: string } => ({
    outboundMode: 'none',
    sendgridFromEmail: '',
    hasSendgridApiKey: false,
    sendgridApiKey: '',
    smtpHost: '',
    smtpPort: 587,
    smtpSecure: false,
    smtpUser: '',
    hasSmtpPass: false,
    smtpPass: '',
    smtpFrom: '',
    imapEnabled: false,
    imapHost: '',
    imapPort: 993,
    imapSecure: true,
    imapUser: '',
    hasImapPass: false,
    imapPass: '',
    imapMailbox: 'INBOX',
});

const EmailMessagingSettingsView: React.FC = () => {
    const { user } = useAuthStore();
    const { showToast } = useUIStore();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [m, setM] = useState(() => emptyModel());
    const [clearSg, setClearSg] = useState(false);
    const [clearSmtp, setClearSmtp] = useState(false);
    const [clearImap, setClearImap] = useState(false);
    const [testTo, setTestTo] = useState('');

    const load = useCallback(async () => {
        if (!user?.token) return;
        setLoading(true);
        try {
            const res = await fetch('/hr/admin/email-settings', { headers: { Authorization: `Bearer ${user.token}` } });
            const body = (await res.json()) as EmailSettingsPublic & { outboundMode?: string };
            if (!res.ok) throw new Error((body as { error?: string }).error || 'Failed to load');
            const outboundMode: OutboundMode =
                body.outboundMode === 'sendgrid' || body.outboundMode === 'smtp' ? body.outboundMode : 'none';
            setM({
                ...emptyModel(),
                ...body,
                outboundMode,
                sendgridApiKey: '',
                smtpPass: '',
                imapPass: '',
            });
            setClearSg(false);
            setClearSmtp(false);
            setClearImap(false);
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Load failed', 'error');
        } finally {
            setLoading(false);
        }
    }, [user?.token, showToast]);

    useEffect(() => {
        void load();
    }, [load]);

    const save = async () => {
        if (!user?.token) return;
        setSaving(true);
        try {
            const payload: Record<string, unknown> = {
                outboundMode: m.outboundMode,
                sendgridFromEmail: m.sendgridFromEmail.trim() || undefined,
                smtpHost: m.smtpHost.trim() || undefined,
                smtpPort: m.smtpPort,
                smtpSecure: m.smtpSecure,
                smtpUser: m.smtpUser.trim() || undefined,
                smtpFrom: m.smtpFrom.trim() || undefined,
                imapEnabled: m.imapEnabled,
                imapHost: m.imapHost.trim() || undefined,
                imapPort: m.imapPort,
                imapSecure: m.imapSecure,
                imapUser: m.imapUser.trim() || undefined,
                imapMailbox: m.imapMailbox.trim() || undefined,
                clearSendgridApiKey: clearSg,
                clearSmtpPass: clearSmtp,
                clearImapPass: clearImap,
            };
            if (m.sendgridApiKey.trim()) payload.sendgridApiKey = m.sendgridApiKey.trim();
            if (m.smtpPass.trim()) payload.smtpPass = m.smtpPass.trim();
            if (m.imapPass.trim()) payload.imapPass = m.imapPass.trim();

            const res = await fetch('/hr/admin/email-settings', {
                method: 'PUT',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Save failed');
            showToast('Email settings saved', 'success');
            setM({
                ...emptyModel(),
                ...(body as EmailSettingsPublic),
                sendgridApiKey: '',
                smtpPass: '',
                imapPass: '',
            });
            setClearSg(false);
            setClearSmtp(false);
            setClearImap(false);
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Save failed', 'error');
        } finally {
            setSaving(false);
        }
    };

    const sendTest = async () => {
        if (!user?.token) return;
        try {
            const res = await fetch('/hr/admin/email-settings/test-outbound', {
                method: 'POST',
                headers: { Authorization: `Bearer ${user.token}`, 'Content-Type': 'application/json' },
                body: JSON.stringify({ to: testTo.trim() || undefined }),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Test failed');
            showToast(`Test email sent to ${body.to}`, 'success');
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Test failed', 'error');
        }
    };

    return (
        <div className="management-view animate-fade-in">
            <h2 style={{ margin: 0 }}>Email &amp; messaging</h2>
            <p style={{ margin: '6px 0 1rem', color: '#64748b', fontSize: '0.9rem', maxWidth: '48rem' }}>
                Configure outbound email for <strong>this organization</strong>. Approval emails, scheduled report attachments, and digests use only what you save here (the API host’s <code style={{ fontSize: '0.8rem' }}>.env</code> is not used for SendGrid/SMTP). SendGrid uses SMTP (
                <code style={{ fontSize: '0.8rem' }}>smtp.sendgrid.net</code>, user <code style={{ fontSize: '0.8rem' }}>apikey</code>) with your API key as the password. IMAP is stored for reference and future inbox features (not used to send mail yet).
            </p>

            {loading ? (
                <p style={{ color: '#64748b' }}>Loading…</p>
            ) : (
                <>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxWidth: '520px' }}>
                        <label style={{ fontSize: '0.8rem', color: '#475569', fontWeight: 600 }}>
                            Outbound mode
                            <select className="control-input" value={m.outboundMode} onChange={(e) => setM((x) => ({ ...x, outboundMode: e.target.value as OutboundMode }))}>
                                <option value="none">Off (no outbound email for this org)</option>
                                <option value="sendgrid">SendGrid (SMTP relay with API key)</option>
                                <option value="smtp">Custom SMTP</option>
                            </select>
                        </label>

                        {m.outboundMode === 'sendgrid' && (
                            <div style={{ padding: '0.75rem', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fafafa' }}>
                                <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>SendGrid (per org)</div>
                                <input className="control-input" placeholder="From address (verified sender)" value={m.sendgridFromEmail} onChange={(e) => setM((x) => ({ ...x, sendgridFromEmail: e.target.value }))} />
                                <p style={{ fontSize: '0.72rem', color: '#64748b', margin: '0.35rem 0' }}>
                                    API key: {m.hasSendgridApiKey ? 'saved on server' : 'not set'}
                                </p>
                                <input className="control-input" placeholder={m.hasSendgridApiKey ? 'New API key (optional)' : 'SendGrid API key'} value={m.sendgridApiKey} onChange={(e) => setM((x) => ({ ...x, sendgridApiKey: e.target.value }))} type="password" autoComplete="new-password" />
                                {m.hasSendgridApiKey && (
                                    <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.35rem' }}>
                                        <input type="checkbox" checked={clearSg} onChange={(e) => setClearSg(e.target.checked)} />
                                        Remove stored API key
                                    </label>
                                )}
                            </div>
                        )}

                        {m.outboundMode === 'smtp' && (
                            <div style={{ padding: '0.75rem', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fafafa' }}>
                                <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>SMTP (per org)</div>
                                <input className="control-input" placeholder="Host" value={m.smtpHost} onChange={(e) => setM((x) => ({ ...x, smtpHost: e.target.value }))} />
                                <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.35rem' }}>
                                    <input className="control-input" style={{ width: '100px' }} type="number" placeholder="Port" value={m.smtpPort} onChange={(e) => setM((x) => ({ ...x, smtpPort: Number(e.target.value) || 587 }))} />
                                    <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                        <input type="checkbox" checked={m.smtpSecure} onChange={(e) => setM((x) => ({ ...x, smtpSecure: e.target.checked }))} />
                                        TLS/SSL
                                    </label>
                                </div>
                                <input className="control-input" style={{ marginTop: '0.35rem' }} placeholder="Username" value={m.smtpUser} onChange={(e) => setM((x) => ({ ...x, smtpUser: e.target.value }))} />
                                <p style={{ fontSize: '0.72rem', color: '#64748b', margin: '0.35rem 0 0' }}>Password: {m.hasSmtpPass ? 'saved' : 'not set'}</p>
                                <input className="control-input" placeholder={m.hasSmtpPass ? 'New password (optional)' : 'Password'} value={m.smtpPass} onChange={(e) => setM((x) => ({ ...x, smtpPass: e.target.value }))} type="password" autoComplete="new-password" />
                                {m.hasSmtpPass && (
                                    <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.35rem' }}>
                                        <input type="checkbox" checked={clearSmtp} onChange={(e) => setClearSmtp(e.target.checked)} />
                                        Remove stored SMTP password
                                    </label>
                                )}
                                <input className="control-input" style={{ marginTop: '0.35rem' }} placeholder='From / envelope "From"' value={m.smtpFrom} onChange={(e) => setM((x) => ({ ...x, smtpFrom: e.target.value }))} />
                            </div>
                        )}

                        <div style={{ padding: '0.75rem', border: '1px solid #e2e8f0', borderRadius: '8px', background: '#fff' }}>
                            <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>IMAP (optional — stored for admin / future use)</div>
                            <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginBottom: '0.35rem' }}>
                                <input type="checkbox" checked={m.imapEnabled} onChange={(e) => setM((x) => ({ ...x, imapEnabled: e.target.checked }))} />
                                Enable IMAP section (credentials stored encrypted-at-rest only if your database is encrypted)
                            </label>
                            {m.imapEnabled && (
                                <>
                                    <input className="control-input" placeholder="IMAP host" value={m.imapHost} onChange={(e) => setM((x) => ({ ...x, imapHost: e.target.value }))} />
                                    <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.35rem' }}>
                                        <input className="control-input" style={{ width: '100px' }} type="number" value={m.imapPort} onChange={(e) => setM((x) => ({ ...x, imapPort: Number(e.target.value) || 993 }))} />
                                        <label style={{ fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
                                            <input type="checkbox" checked={m.imapSecure} onChange={(e) => setM((x) => ({ ...x, imapSecure: e.target.checked }))} />
                                            TLS (993)
                                        </label>
                                    </div>
                                    <input className="control-input" style={{ marginTop: '0.35rem' }} placeholder="IMAP username" value={m.imapUser} onChange={(e) => setM((x) => ({ ...x, imapUser: e.target.value }))} />
                                    <p style={{ fontSize: '0.72rem', color: '#64748b', margin: '0.35rem 0 0' }}>Password: {m.hasImapPass ? 'saved' : 'not set'}</p>
                                    <input className="control-input" placeholder={m.hasImapPass ? 'New IMAP password (optional)' : 'IMAP password'} value={m.imapPass} onChange={(e) => setM((x) => ({ ...x, imapPass: e.target.value }))} type="password" autoComplete="new-password" />
                                    {m.hasImapPass && (
                                        <label style={{ fontSize: '0.78rem', display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.35rem' }}>
                                            <input type="checkbox" checked={clearImap} onChange={(e) => setClearImap(e.target.checked)} />
                                            Remove stored IMAP password
                                        </label>
                                    )}
                                    <input className="control-input" style={{ marginTop: '0.35rem' }} placeholder="Mailbox (default INBOX)" value={m.imapMailbox} onChange={(e) => setM((x) => ({ ...x, imapMailbox: e.target.value }))} />
                                </>
                            )}
                        </div>

                        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                            <button type="button" className="hr-btn primary" onClick={() => void save()} disabled={saving}>
                                {saving ? 'Saving…' : 'Save settings'}
                            </button>
                            <button type="button" className="hr-btn secondary" onClick={() => void load()}>
                                Reload
                            </button>
                        </div>

                        <div style={{ marginTop: '0.5rem', paddingTop: '0.75rem', borderTop: '1px solid #e2e8f0' }}>
                            <div style={{ fontWeight: 600, marginBottom: '0.35rem' }}>Send test email</div>
                            <p style={{ fontSize: '0.78rem', color: '#64748b', margin: '0 0 0.35rem' }}>Uses the saved org settings above. Leave recipient blank to use your HR profile email.</p>
                            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', alignItems: 'center' }}>
                                <input className="control-input" style={{ minWidth: '220px' }} placeholder="Recipient (optional)" value={testTo} onChange={(e) => setTestTo(e.target.value)} />
                                <button type="button" className="hr-btn secondary" onClick={() => void sendTest()}>
                                    Send test
                                </button>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
};

export default EmailMessagingSettingsView;
