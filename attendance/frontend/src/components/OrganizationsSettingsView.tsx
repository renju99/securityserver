import React, { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '../store/useAuthStore';
import { useUIStore } from '../store/useUIStore';

type OrganizationRow = {
    id: number;
    slug: string;
    name: string;
    created_at?: string;
};

const OrganizationsSettingsView: React.FC = () => {
    const { user } = useAuthStore();
    const { showToast } = useUIStore();
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [rows, setRows] = useState<OrganizationRow[]>([]);
    const [slug, setSlug] = useState('');
    const [name, setName] = useState('');
    const [deletingId, setDeletingId] = useState<number | null>(null);

    const load = useCallback(async () => {
        if (!user?.token) return;
        setLoading(true);
        try {
            const res = await fetch('/hr/admin/organizations', {
                headers: { Authorization: `Bearer ${user.token}` },
                credentials: 'same-origin',
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Failed to load');
            setRows(Array.isArray(body.organizations) ? body.organizations : []);
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Load failed', 'error');
        } finally {
            setLoading(false);
        }
    }, [user?.token, showToast]);

    useEffect(() => {
        void load();
    }, [load]);

    const create = async () => {
        if (!user?.token) return;
        setSaving(true);
        try {
            const res = await fetch('/hr/admin/organizations', {
                method: 'POST',
                headers: {
                    Authorization: `Bearer ${user.token}`,
                    'Content-Type': 'application/json',
                },
                credentials: 'same-origin',
                body: JSON.stringify({
                    slug: slug.trim().toLowerCase(),
                    name: name.trim(),
                }),
            });
            const body = await res.json();
            if (!res.ok) throw new Error(body.error || 'Create failed');
            showToast(`Organization “${body.name}” created (slug: ${body.slug})`, 'success');
            setSlug('');
            setName('');
            await load();
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Create failed', 'error');
        } finally {
            setSaving(false);
        }
    };

    const remove = async (r: OrganizationRow) => {
        if (!user?.token) return;
        if (r.slug === 'default') {
            showToast('The default organization cannot be deleted.', 'error');
            return;
        }
        const ok = window.confirm(
            `Permanently delete organization “${r.name}” (${r.slug})?\n\nThis removes all staff, attendance, sites, settings, and integrations for this tenant. This cannot be undone.`
        );
        if (!ok) return;
        setDeletingId(r.id);
        try {
            const res = await fetch(`/hr/admin/organizations/${r.id}`, {
                method: 'DELETE',
                headers: { Authorization: `Bearer ${user.token}` },
                credentials: 'same-origin',
            });
            if (res.status === 204) {
                showToast(`Organization “${r.name}” deleted`, 'success');
                await load();
                return;
            }
            const body = (await res.json().catch(() => ({}))) as { error?: string };
            if (!res.ok) throw new Error(body.error || 'Delete failed');
        } catch (e: unknown) {
            showToast(e instanceof Error ? e.message : 'Delete failed', 'error');
        } finally {
            setDeletingId(null);
        }
    };

    return (
        <div className="management-view animate-fade-in">
            <h2 style={{ margin: 0 }}>Organizations</h2>
            <p style={{ margin: '6px 0 1rem', color: '#64748b', fontSize: '0.9rem', maxWidth: '48rem' }}>
                <strong>HR Admin only.</strong> Create additional companies (tenants). Each has its own sites, staff, attendance, and settings. Extra
                tenants can be removed with <strong>Delete tenant</strong> (not available for the primary &quot;default&quot; organization). Use the{' '}
                <strong>Organization</strong> control in the header to switch after you add an HR account in the new org (same work email as your
                current user, or matching staff ID if email is empty). New orgs get default <strong>Morning</strong> and <strong>Night</strong> shifts.
            </p>

            <div
                style={{
                    marginBottom: '1.25rem',
                    padding: '0.75rem',
                    border: '1px solid #e2e8f0',
                    borderRadius: '8px',
                    background: '#fafafa',
                    maxWidth: '520px',
                }}
            >
                <div style={{ fontWeight: 600, marginBottom: '0.5rem' }}>New organization</div>
                <input
                    className="control-input"
                    placeholder="Slug (e.g. dubai, abu-dhabi)"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                    autoComplete="off"
                />
                <input
                    className="control-input"
                    style={{ marginTop: '0.35rem' }}
                    placeholder="Display name (e.g. Dubai branch)"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                />
                <button type="button" className="hr-btn primary" style={{ marginTop: '0.5rem' }} disabled={saving || !slug.trim() || !name.trim()} onClick={() => void create()}>
                    {saving ? 'Creating…' : 'Create organization'}
                </button>
            </div>

            {loading ? (
                <p style={{ color: '#64748b' }}>Loading…</p>
            ) : (
                <div style={{ maxWidth: 'min(100%, 52rem)' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem', tableLayout: 'fixed' }}>
                        <thead>
                            <tr style={{ textAlign: 'left', borderBottom: '1px solid #e2e8f0' }}>
                                <th style={{ padding: '0.5rem', width: '42%' }}>Name</th>
                                <th style={{ padding: '0.5rem', width: '28%' }}>Slug</th>
                                <th style={{ padding: '0.5rem', width: '10%' }}>ID</th>
                                <th style={{ padding: '0.5rem', width: '20%', textAlign: 'right' }}>Remove</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((r) => (
                                <tr key={r.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                                    <td style={{ padding: '0.5rem', verticalAlign: 'middle' }}>
                                        <div style={{ fontWeight: 600 }}>{r.name}</div>
                                    </td>
                                    <td style={{ padding: '0.5rem', verticalAlign: 'middle' }}>
                                        <code style={{ fontSize: '0.82rem', wordBreak: 'break-all' }}>{r.slug}</code>
                                    </td>
                                    <td style={{ padding: '0.5rem', color: '#64748b', verticalAlign: 'middle' }}>{r.id}</td>
                                    <td style={{ padding: '0.5rem', verticalAlign: 'middle', textAlign: 'right' }}>
                                        {r.slug === 'default' ? (
                                            <span style={{ fontSize: '0.78rem', color: '#94a3b8' }}>Primary</span>
                                        ) : (
                                            <button
                                                type="button"
                                                className="hr-btn danger sm"
                                                style={{ whiteSpace: 'nowrap' }}
                                                disabled={deletingId === r.id}
                                                onClick={() => void remove(r)}
                                            >
                                                {deletingId === r.id ? 'Deleting…' : 'Delete tenant'}
                                            </button>
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    <button type="button" className="hr-btn secondary sm" style={{ marginTop: '0.75rem' }} onClick={() => void load()}>
                        Reload list
                    </button>
                </div>
            )}
        </div>
    );
};

export default OrganizationsSettingsView;
