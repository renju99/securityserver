import { FormEvent, useEffect, useMemo, useState } from 'react';
import FaceEnrollmentManager from './FaceEnrollmentManager';
import { useAuthStore } from '../store/useAuthStore';

type EmployeeLite = {
    id: number;
    staff_id: string;
    first_name?: string;
    last_name?: string;
    department_name?: string;
    role_name?: string;
    site_name?: string;
    face_enrolled?: boolean;
    face_auth_enabled?: boolean;
    face_enrollment_photo_url?: string;
    photo_url?: string;
};

const HREnrollmentMobile = () => {
    const user = useAuthStore((state) => state.user);
    const login = useAuthStore((state) => state.login);
    const logout = useAuthStore((state) => state.logout);

    const [loginData, setLoginData] = useState({ staffId: '', password: '' });
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState('');

    const [search, setSearch] = useState('');
    const [employees, setEmployees] = useState<EmployeeLite[]>([]);
    const [selected, setSelected] = useState<EmployeeLite | null>(null);

    const isHrAllowed = user?.role === 'HR Admin';

    const selectedLabel = useMemo(() => {
        if (!selected) return '';
        return [selected.first_name, selected.last_name].filter(Boolean).join(' ') || selected.staff_id;
    }, [selected]);

    const isEmployeeRecord = (row: EmployeeLite) => {
        const dept = String(row.department_name || '').trim().toLowerCase();
        const role = String(row.role_name || '').trim().toLowerCase();
        return dept !== 'vehicle' && role !== 'vehicle';
    };

    const fetchEmployees = async (query = '') => {
        if (!user?.token) return;
        setLoading(true);
        setError('');
        try {
            const res = await fetch(`/hr/users?page=1&limit=30&search=${encodeURIComponent(query)}`, {
                headers: { Authorization: `Bearer ${user.token}` }
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Failed to load employees');
            const rows = (Array.isArray(data?.users) ? data.users : []).filter(isEmployeeRecord);
            setEmployees(rows);
            if (!rows.length) {
                setSelected(null);
                return;
            }
            setSelected((prev) => rows.find((r: EmployeeLite) => r.id === prev?.id) || rows[0]);
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Failed to load employees');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        if (user?.token && isHrAllowed) {
            fetchEmployees('');
        }
    }, [user?.token, isHrAllowed]);

    const handleLogin = async (e: FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);
        try {
            const res = await fetch('/auth/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ staffId: loginData.staffId.trim(), password: loginData.password })
            });
            const data = await res.json();
            if (!res.ok) throw new Error(data.error || 'Login failed');
            if (data?.user?.role !== 'HR Admin') {
                throw new Error('Access denied. Only HR Admin can use mobile enrollment.');
            }
            login({ ...data.user, token: data.token });
        } catch (err: unknown) {
            setError(err instanceof Error ? err.message : 'Login failed');
        } finally {
            setLoading(false);
        }
    };

    if (!user) {
        return (
            <div className="setup-screen hr-login">
                <div className="setup-card">
                    <div className="berkeley-logo-small">Berkeley Workforce 360</div>
                    <h2>HR Mobile Enrollment</h2>
                    <p>Sign in with HR Admin credentials.</p>
                    <form onSubmit={handleLogin}>
                        {error && <div className="error-box">{error}</div>}
                        <input
                            type="text"
                            placeholder="HR Staff ID"
                            value={loginData.staffId}
                            onChange={(e) => setLoginData((prev) => ({ ...prev, staffId: e.target.value }))}
                            className="setup-input"
                            required
                        />
                        <input
                            type="password"
                            placeholder="Password"
                            value={loginData.password}
                            onChange={(e) => setLoginData((prev) => ({ ...prev, password: e.target.value }))}
                            className="setup-input"
                            required
                        />
                        <button type="submit" className="btn-primary" disabled={loading}>
                            {loading ? 'Signing in...' : 'Sign In'}
                        </button>
                    </form>
                </div>
            </div>
        );
    }

    if (!isHrAllowed) {
        return (
            <div className="setup-screen">
                <div className="setup-card">
                    <h2>Access Restricted</h2>
                    <p>Only HR Admin can access mobile enrollment.</p>
                    <button type="button" className="btn-secondary" onClick={logout}>Logout</button>
                </div>
            </div>
        );
    }

    return (
        <div className="hr-enroll-mobile">
            <div className="hr-enroll-mobile-header">
                <div>
                    <h2>Face Enrollment</h2>
                    <p>HR-only mobile interface for employee registration</p>
                </div>
                <button type="button" className="btn-secondary" onClick={logout}>Logout</button>
            </div>

            <div className="form-surface">
                <h3>Select Employee</h3>
                <p className="form-help strong" style={{ marginTop: 0, marginBottom: '0.55rem' }}>
                    Only employee profiles are shown here. Vehicle records are excluded.
                </p>
                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    <input
                        className="control-input"
                        placeholder="Search by staff ID or email"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                    <button type="button" className="btn-secondary" onClick={() => fetchEmployees(search)} disabled={loading}>
                        {loading ? 'Loading...' : 'Search'}
                    </button>
                </div>
                {error && <div style={{ color: '#b91c1c', marginTop: '0.5rem', fontSize: '0.85rem' }}>{error}</div>}
                <div className="hr-enroll-mobile-list">
                    {employees.map((emp) => {
                        const selectedRow = selected?.id === emp.id;
                        return (
                            <button
                                key={emp.id}
                                type="button"
                                className={`hr-enroll-mobile-list-item ${selectedRow ? 'selected' : ''}`}
                                onClick={() => setSelected(emp)}
                            >
                                <div>
                                    <div style={{ fontWeight: 700 }}>{emp.staff_id}</div>
                                    <div style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                        {[emp.first_name, emp.last_name].filter(Boolean).join(' ') || 'No name'}
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right', fontSize: '0.75rem', color: '#64748b' }}>
                                    <div>{emp.face_enrolled ? 'Enrolled' : 'Not Enrolled'}</div>
                                    <div>{emp.face_auth_enabled === false ? 'Face Disabled' : 'Face Enabled'}</div>
                                </div>
                            </button>
                        );
                    })}
                    {!employees.length && !loading && <div className="form-help">No employees found for this search.</div>}
                </div>
            </div>

            {selected && (
                <div className="form-surface">
                    <h3>Enroll for {selectedLabel}</h3>
                    <p className="form-help strong" style={{ marginTop: 0 }}>
                        Staff ID: <strong>{selected.staff_id}</strong>
                    </p>
                    <FaceEnrollmentManager
                        token={user.token}
                        userId={selected.id}
                        staffId={selected.staff_id}
                        initialEnrolled={!!selected.face_enrolled}
                        initialEnrollmentImageUrl={selected.face_enrollment_photo_url || ''}
                        fallbackProfilePhotoUrl={selected.photo_url || ''}
                        onStatusChange={(enrolled) => {
                            setSelected((prev) => (prev ? { ...prev, face_enrolled: enrolled } : prev));
                            setEmployees((prev) => prev.map((item) => (item.id === selected.id ? { ...item, face_enrolled: enrolled } : item)));
                        }}
                    />
                </div>
            )}
        </div>
    );
};

export default HREnrollmentMobile;
