import React, { useMemo, useCallback } from 'react';
import FilterPanel from './FilterPanel';
import { LoadingSpinner } from './LoadingSpinner';
import { useAuthStore } from '../store/useAuthStore';
import { useDataStore } from '../store/useDataStore';
import { useUIStore } from '../store/useUIStore';
import { useMapStore } from '../store/useMapStore';
import { Employee, Site } from '../types';
import { exportToCSV, formatDataForExport } from '../utils/exportUtils';

interface StaffManagerProps {
    onEditUser?: (user: Employee) => void;
    setCurrentUser: (user: any) => void;
    setShowUserModal: (val: boolean) => void;
    handleBulkExport: () => void;
    handleBulkArchive: () => void;
    handleBulkDelete: () => void;
    handleFocusSite: (site: Site) => void;
    setCurrentSite: (site: any) => void;
    setShowSiteModal: (val: boolean) => void;
    setCurrentShift: (shift: any) => void;
    setShowShiftModal: (val: boolean) => void;
    currentShift: any;
    setValidationErrors: (errors: any) => void;
    showShiftModal: boolean;
}

export default function StaffManager({
    onEditUser,
    setCurrentUser, setShowUserModal,
    handleBulkExport, handleBulkArchive, handleBulkDelete, handleFocusSite,
    setCurrentSite, setShowSiteModal,
    setCurrentShift, setShowShiftModal, currentShift,
    setValidationErrors, showShiftModal
}: StaffManagerProps) {
    const { user } = useAuthStore();
    const {
        mgmtSubTab, setMgmtSubTab, mgmtSearch, setMgmtSearch, mgmtPage, setMgmtPage,
        mgmtUsers, mgmtStats, sites, roles, shifts, isMgmtLoading,
        selectedRoles, setSelectedRoles, selectedSites, setSelectedSites,
        selectedUsers, setSelectedUsers, selectAll, setSelectAll,
        showFilters, setShowFilters, sortField, setSortField,
        sortDirection, setSortDirection, setShifts,
        selectedShifts, setSelectedShifts,
        bulkShiftId, setBulkShiftId,
        bulkSiteId, setBulkSiteId,
        bulkDeptName, setBulkDeptName,
    } = useDataStore();
    const { showToast } = useUIStore();

    const { setMapCenter, setZoom } = useMapStore();

    const applyFilters = useCallback((users: Employee[]) => {
        let filtered = [...users];
        if (selectedRoles.length > 0) {
            filtered = filtered.filter(u => selectedRoles.includes(u.role_id));
        }
        if (selectedSites.length > 0) {
            filtered = filtered.filter(u => {
                if (selectedSites.includes(-1 as any)) {
                    return !u.site_id || selectedSites.includes(u.site_id as any);
                }
                return !!u.site_id && selectedSites.includes(u.site_id as any);
            });
        }
        if (selectedShifts.length > 0) {
            filtered = filtered.filter(u => !!u.shift_id && selectedShifts.includes(u.shift_id as any));
        }
        return filtered;
    }, [selectedRoles, selectedSites, selectedShifts]);

    const applySorting = useCallback((users: Employee[]) => {
        return [...users].sort((a, b) => {
            let aVal = (a as any)[sortField];
            let bVal = (b as any)[sortField];

            if (aVal === null || aVal === undefined) aVal = '';
            if (bVal === null || bVal === undefined) bVal = '';

            aVal = String(aVal).toLowerCase();
            bVal = String(bVal).toLowerCase();

            if (sortDirection === 'asc') {
                return aVal > bVal ? 1 : aVal < bVal ? -1 : 0;
            } else {
                return aVal < bVal ? 1 : aVal > bVal ? -1 : 0;
            }
        });
    }, [sortField, sortDirection]);

    const handleSelectUser = (userId: number | string) => {
        if (selectedUsers.includes(userId)) {
            setSelectedUsers((prev: any) => (Array.isArray(prev) ? prev : []).filter((id: any) => id !== userId));
            setSelectAll(false);
        } else {
            setSelectedUsers((prev: any) => [...(Array.isArray(prev) ? prev : []), userId]);
        }
    };

    // Filter out Vehicles from the general Staff Directory
    const nonVehicleUsers = useMemo(() => {
        return (mgmtUsers || []).filter(u => u.department_name !== 'Vehicle');
    }, [mgmtUsers]);

    const filteredUsers = useMemo(() => {
        let base = nonVehicleUsers;
        if (mgmtSearch) {
            const low = mgmtSearch.toLowerCase();
            base = base.filter(u =>
                (u.staff_id && u.staff_id.toLowerCase().includes(low)) ||
                (u.email && u.email.toLowerCase().includes(low)) ||
                (u.first_name && u.first_name.toLowerCase().includes(low)) ||
                (u.last_name && u.last_name.toLowerCase().includes(low))
            );
        }
        return applySorting(applyFilters(base));
    }, [nonVehicleUsers, mgmtSearch, applyFilters, applySorting]);

    const handleSelectAll = () => {
        if (selectAll) {
            setSelectedUsers([]);
            setSelectAll(false);
        } else {
            setSelectedUsers(filteredUsers.map(u => u.id));
            setSelectAll(true);
        }
    };

    const handleBulkUpdate = async (type: string) => {
        if (selectedUsers.length === 0) return;

        let payload: any = { userIds: selectedUsers };
        if (type === 'shift') {
            if (!bulkShiftId) return showToast('Please select a shift first', 'error');
            payload.shiftId = bulkShiftId;
        } else if (type === 'site') {
            if (!bulkSiteId) return showToast('Please select a site first', 'error');
            payload.siteId = bulkSiteId;
        } else if (type === 'dept') {
            if (!bulkDeptName) return showToast('Please enter department name', 'error');
            payload.departmentName = bulkDeptName;
        } else if (type === 'tracking-on') {
            payload.isTrackingEnabled = true;
        } else if (type === 'tracking-off') {
            payload.isTrackingEnabled = false;
        } else {
            return;
        }

        try {
            const res = await fetch('/api/hr/users/bulk-update', {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${user?.token}` },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                showToast(`Successfully updated ${selectedUsers.length} users`, 'success');
                setSelectedUsers([]);
                setSelectAll(false);
                useDataStore.getState().fetchManagementUsers(user?.token || '', mgmtPage, mgmtSearch);
            } else {
                showToast('Failed to update users', 'error');
            }
        } catch (err) {
            console.error('Bulk update error', err);
            showToast('Network error during bulk update', 'error');
        }
    };

    return (
        <div className="management-view">
            <div className="mgmt-subtabs">
                <button
                    className={`subtab-btn ${mgmtSubTab === 'staff' ? 'active' : ''}`}
                    onClick={() => setMgmtSubTab('staff')}
                >
                    Staff Directory
                </button>
                <button
                    className={`subtab-btn ${mgmtSubTab === 'sites' ? 'active' : ''}`}
                    onClick={() => setMgmtSubTab('sites')}
                >
                    Site Locations
                </button>
                <button
                    className={`subtab-btn ${mgmtSubTab === 'shifts' ? 'active' : ''}`}
                    onClick={() => setMgmtSubTab('shifts')}
                >
                    Shift Schedules
                </button>
            </div>

            {mgmtSubTab === 'staff' ? (
                <>
                    <div className="mgmt-header">
                        <div className="mgmt-actions">
                            <input
                                type="text"
                                placeholder="Search by ID or Email..."
                                className="mgmt-search"
                                value={mgmtSearch}
                                onChange={(e) => { setMgmtSearch(e.target.value); setMgmtPage(1); }}
                            />
                            <button
                                className="btn-primary"
                                onClick={() => {
                                    setCurrentUser({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: 'Operations' });
                                    setShowUserModal(true);
                                }}>
                                + Add New Staff
                            </button>
                            <button
                                className="btn-secondary"
                                onClick={() => {
                                    const formattedData = formatDataForExport(mgmtUsers);
                                    exportToCSV(formattedData, `staff_export_${new Date().toISOString().split('T')[0]}.csv`);
                                    showToast('Staff data exported successfully', 'success');
                                }}
                            >
                                📥 Export CSV
                            </button>
                            <button
                                className={`btn-secondary ${showFilters ? 'active' : ''}`}
                                onClick={() => setShowFilters(!showFilters)}
                                style={{ background: showFilters ? '#2563eb' : '', color: showFilters ? 'white' : '' }}
                            >
                                🔍 Filters {(selectedRoles.length + selectedSites.length) > 0 && `(${selectedRoles.length + selectedSites.length})`}
                            </button>
                        </div>
                    </div>

                    {selectedUsers.length > 0 && (
                        <div className="bulk-actions-panel" style={{
                            background: '#f8fafc',
                            padding: '1.25rem',
                            borderRadius: '12px',
                            marginBottom: '1.5rem',
                            border: '1px solid #e2e8f0',
                            boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.05)'
                        }}>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '1rem', borderBottom: '1px solid #e2e8f0', paddingBottom: '0.75rem' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                                    <span style={{ background: '#2563eb', color: 'white', padding: '0.25rem 0.6rem', borderRadius: '6px', fontSize: '0.85rem', fontWeight: 'bold' }}>
                                        {selectedUsers.length}
                                    </span>
                                    <span style={{ color: '#1e293b', fontWeight: '600' }}>User(s) Selected</span>
                                </div>
                                <div style={{ display: 'flex', gap: '0.5rem' }}>
                                    <button className="btn-secondary" onClick={handleBulkExport} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>📥 Export</button>
                                    <button className="btn-secondary" onClick={handleBulkArchive} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', background: '#fef3c7', color: '#b45309', border: '1px solid #fde68a' }}>📦 Archive</button>
                                    <button className="btn-secondary" onClick={handleBulkDelete} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem', background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' }}>🗑️ Delete</button>
                                    <button className="btn-secondary" onClick={() => { setSelectedUsers([]); setSelectAll(false); }} style={{ fontSize: '0.8rem', padding: '0.4rem 0.8rem' }}>✕ Clear</button>
                                </div>
                            </div>

                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '1rem' }}>
                                {/* Bulk Shift */}
                                <div className="bulk-action-group" style={{ display: 'flex', gap: '0.5rem' }}>
                                    <select
                                        value={bulkShiftId}
                                        onChange={(e) => setBulkShiftId(e.target.value)}
                                        style={{ flex: 1, padding: '0.4rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                                    >
                                        <option value="">Select Shift...</option>
                                        {shifts.map(s => <option key={s.id} value={s.id}>{s.name} ({s.start_time} - {s.end_time})</option>)}
                                    </select>
                                    <button className="btn-secondary" onClick={() => handleBulkUpdate('shift')} style={{ whiteSpace: 'nowrap', padding: '0.4rem 0.8rem' }}>Apply Shift</button>
                                </div>

                                {/* Bulk Site */}
                                <div className="bulk-action-group" style={{ display: 'flex', gap: '0.5rem' }}>
                                    <select
                                        value={bulkSiteId}
                                        onChange={(e) => setBulkSiteId(e.target.value)}
                                        style={{ flex: 1, padding: '0.4rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                                    >
                                        <option value="">Select Site...</option>
                                        <option value="-1">Global / Remotely (No Site)</option>
                                        {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                                    </select>
                                    <button className="btn-secondary" onClick={() => handleBulkUpdate('site')} style={{ whiteSpace: 'nowrap', padding: '0.4rem 0.8rem' }}>Apply Site</button>
                                </div>

                                {/* Bulk Department */}
                                <div className="bulk-action-group" style={{ display: 'flex', gap: '0.5rem' }}>
                                    <input
                                        type="text"
                                        placeholder="Dept Name..."
                                        value={bulkDeptName}
                                        onChange={(e) => setBulkDeptName(e.target.value)}
                                        style={{ flex: 1, padding: '0.4rem', borderRadius: '6px', border: '1px solid #cbd5e1' }}
                                    />
                                    <button className="btn-secondary" onClick={() => handleBulkUpdate('dept')} style={{ whiteSpace: 'nowrap', padding: '0.4rem 0.8rem' }}>Apply Dept</button>
                                </div>

                                {/* Tracking Flags */}
                                <div className="bulk-action-group" style={{ display: 'flex', gap: '0.5rem' }}>
                                    <button className="btn-secondary" onClick={() => handleBulkUpdate('tracking-on')} style={{ flex: 1, padding: '0.4rem 0.8rem', background: '#dcfce7', color: '#166534', border: '1px solid #bbf7d0' }}>Enable Tracking</button>
                                    <button className="btn-secondary" onClick={() => handleBulkUpdate('tracking-off')} style={{ flex: 1, padding: '0.4rem 0.8rem', background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca' }}>Disable Tracking</button>
                                </div>
                            </div>
                        </div>
                    )}

                    {showFilters && (
                        <div style={{ marginBottom: '1rem' }}>
                            <FilterPanel />
                        </div>
                    )}

                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th style={{ width: '40px' }}>
                                        <input
                                            type="checkbox"
                                            checked={selectAll}
                                            onChange={handleSelectAll}
                                            style={{ cursor: 'pointer' }}
                                        />
                                    </th>
                                    <th style={{ width: '60px' }}>Photo</th>
                                    <th
                                        onClick={() => {
                                            if (sortField === 'staff_id') {
                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                            } else {
                                                setSortField('staff_id');
                                                setSortDirection('asc');
                                            }
                                        }}
                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                    >
                                        Staff ID {sortField === 'staff_id' && (sortDirection === 'asc' ? '↑' : '↓')}
                                    </th>
                                    <th>Staff Name</th>
                                    <th
                                        onClick={() => {
                                            if (sortField === 'email') {
                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                            } else {
                                                setSortField('email');
                                                setSortDirection('asc');
                                            }
                                        }}
                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                    >
                                        Email {sortField === 'email' && (sortDirection === 'asc' ? '↑' : '↓')}
                                    </th>
                                    <th
                                        onClick={() => {
                                            if (sortField === 'role_name') {
                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                            } else {
                                                setSortField('role_name');
                                                setSortDirection('asc');
                                            }
                                        }}
                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                    >
                                        Role {sortField === 'role_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                                    </th>
                                    <th>Site</th>
                                    <th
                                        onClick={() => {
                                            if (sortField === 'department_name') {
                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                            } else {
                                                setSortField('department_name');
                                                setSortDirection('asc');
                                            }
                                        }}
                                        style={{ cursor: 'pointer', userSelect: 'none' }}
                                    >
                                        Department {sortField === 'department_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                                    </th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isMgmtLoading ? (
                                    <tr>
                                        <td colSpan={9} style={{ padding: 0, border: 'none' }}>
                                            <LoadingSpinner size="medium" text="Loading staff..." />
                                        </td>
                                    </tr>
                                ) : filteredUsers.length === 0 ? (
                                    <tr>
                                        <td colSpan={9} style={{ padding: 0, border: 'none' }}>
                                            <div className="empty-state">
                                                <div className="empty-state-icon">👥</div>
                                                <h3 className="empty-state-title">No Staff Found</h3>
                                                <p className="empty-state-message">
                                                    {mgmtSearch ? 'Try adjusting your search' : 'Get started by adding your first staff member'}
                                                </p>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    filteredUsers.map(u => (
                                        <tr key={u.id} style={{ background: selectedUsers.includes(u.id) ? '#eff6ff' : '' }}>
                                            <td>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedUsers.includes(u.id)}
                                                    onChange={() => handleSelectUser(u.id)}
                                                    style={{ cursor: 'pointer' }}
                                                />
                                            </td>
                                            <td>
                                                {u.photo_url ? (
                                                    <img src={u.photo_url} alt="" style={{ width: '32px', height: '32px', borderRadius: '50%', objectFit: 'cover' }} />
                                                ) : (
                                                    <div style={{ width: '32px', height: '32px', borderRadius: '50%', background: '#f1f5f9', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px', color: '#94a3b8' }}>
                                                        NO IMG
                                                    </div>
                                                )}
                                            </td>
                                            <td><strong>{u.staff_id}</strong></td>
                                            <td>{u.first_name || u.last_name ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : '-'}</td>
                                            <td>{u.email || '-'}</td>
                                            <td><span className="role-tag">{u.role_name}</span></td>
                                            <td>{u.site_name || 'Global'}</td>
                                            <td>{u.department_name}</td>
                                            <td>
                                                <button className="btn-edit" onClick={() => {
                                                    onEditUser?.(u);
                                                    setValidationErrors({});
                                                }}>Edit</button>
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>

                    <div className="mgmt-pagination">
                        <button disabled={mgmtPage === 1} onClick={() => setMgmtPage(p => p - 1)}>Previous</button>
                        <span>Page {mgmtPage} of {mgmtStats.totalPages}</span>
                        <button disabled={mgmtPage === mgmtStats.totalPages} onClick={() => setMgmtPage(p => p + 1)}>Next</button>
                    </div>
                </>
            ) : mgmtSubTab === 'sites' ? (
                <div className="site-management">
                    <div className="mgmt-header">
                        <div className="mgmt-actions">
                            <button className="btn-primary" onClick={() => {
                                setCurrentSite({
                                    name: '',
                                    location: '',
                                    latitude: '',
                                    longitude: '',
                                    radiusMeters: 100,
                                    geofenceType: 'CIRCLE',
                                    geofenceData: null
                                });
                                setShowSiteModal(true);
                            }}>
                                + Add New Site
                            </button>
                        </div>
                    </div>
                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th>Site ID</th>
                                    <th>Name</th>
                                    <th>Location/Description</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sites.map(s => (
                                    <tr key={s.id}>
                                        <td><strong>#{s.id}</strong></td>
                                        <td>
                                            <div><strong>{s.name}</strong></div>
                                            {s.latitude && <small style={{ color: '#64748b' }}>{parseFloat(s.latitude).toFixed(4)}, {parseFloat(s.longitude).toFixed(4)}</small>}
                                        </td>
                                        <td>{s.location || '-'}</td>
                                        <td>
                                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                                <button className="btn-edit" onClick={() => {
                                                    setCurrentSite({
                                                        ...s,
                                                        radiusMeters: (s as any).radius_meters || 100,
                                                        geofenceType: (s as any).geofence_type || 'CIRCLE',
                                                        geofenceData: (s as any).geofence_data,
                                                        geofenceEnabled: (s as any).geofence_enabled !== false
                                                    });
                                                    setShowSiteModal(true);
                                                }}>Edit</button>
                                                <button
                                                    className="btn-secondary"
                                                    style={{ padding: '0.4rem 0.8rem', fontSize: '0.75rem' }}
                                                    onClick={() => handleFocusSite(s)}
                                                >
                                                    🌐 View on Map
                                                </button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                </div>
            ) : (
                <div className="site-management">
                    <div className="mgmt-header">
                        <div className="mgmt-actions">
                            <button className="btn-primary" onClick={() => {
                                setCurrentShift({ name: '', startTime: '', endTime: '' });
                                setShowShiftModal(true);
                            }}>
                                + Create New Shift
                            </button>
                        </div>
                    </div>
                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th>Shift Name</th>
                                    <th>Start Time</th>
                                    <th>End Time</th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {shifts.map(s => (
                                    <tr key={s.id}>
                                        <td><strong>{s.name}</strong></td>
                                        <td>{s.start_time}</td>
                                        <td>{s.end_time}</td>
                                        <td>
                                            <button className="btn-edit" onClick={() => {
                                                setCurrentShift({
                                                    id: s.id,
                                                    name: s.name,
                                                    startTime: s.start_time,
                                                    endTime: s.end_time
                                                });
                                                setShowShiftModal(true);
                                            }}>Edit</button>
                                        </td>
                                    </tr>
                                ))}
                                {shifts.length === 0 && (
                                    <tr><td colSpan={4} style={{ textAlign: 'center', padding: '2rem' }}>No shifts defined</td></tr>
                                )}
                            </tbody>
                        </table>
                    </div>

                    {showShiftModal && (
                        <div className="modal-overlay">
                            <div className="modal-content">
                                <h3>{currentShift.id ? 'Edit' : 'Create'} Shift Schedule</h3>
                                <form onSubmit={async (e) => {
                                    e.preventDefault();
                                    try {
                                        const url = currentShift.id ? `/api/hr/shifts/${currentShift.id}` : '/api/hr/shifts';
                                        const method = currentShift.id ? 'PUT' : 'POST';

                                        const res = await fetch(url, {
                                            method: method,
                                            headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${user?.token}` },
                                            body: JSON.stringify(currentShift)
                                        });

                                        if (res.ok) {
                                            setShowShiftModal(false);
                                            fetch('/api/hr/shifts', { headers: { 'Authorization': `Bearer ${user?.token}` } })
                                                .then(r => r.json()).then(setShifts);
                                            showToast(currentShift.id ? 'Shift updated' : 'Shift created', 'success');
                                        } else {
                                            showToast('Operation failed', 'error');
                                        }
                                    } catch (err) { showToast('Error saving shift', 'error'); }
                                }}>
                                    <div className="form-group">
                                        <label>Shift Name</label>
                                        <input required type="text" value={currentShift.name} onChange={e => setCurrentShift({ ...currentShift, name: e.target.value })} placeholder="e.g. Morning Shift" />
                                    </div>
                                    <div className="form-grid">
                                        <div className="form-group">
                                            <label>Start Time</label>
                                            <input required type="time" value={currentShift.startTime} onChange={e => setCurrentShift({ ...currentShift, startTime: e.target.value })} />
                                        </div>
                                        <div className="form-group">
                                            <label>End Time</label>
                                            <input required type="time" value={currentShift.endTime} onChange={e => setCurrentShift({ ...currentShift, endTime: e.target.value })} />
                                        </div>
                                    </div>
                                    <div className="modal-footer">
                                        <button type="button" className="btn-secondary" onClick={() => setShowShiftModal(false)}>Cancel</button>
                                        <button type="submit" className="btn-primary">{currentShift.id ? 'Save Changes' : 'Create Shift'}</button>
                                    </div>
                                </form>
                            </div>
                        </div>
                    )}
                </div>
            )}
        </div>
    );
}