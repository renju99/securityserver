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

export default function VehiclesManager({
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

    // Filter ONLY Vehicles from the Directory
    const vehicleUsers = useMemo(() => {
        return (mgmtUsers || []).filter(u => u.department_name === 'Vehicle');
    }, [mgmtUsers]);

    const filteredUsers = useMemo(() => {
        let base = vehicleUsers;
        if (mgmtSearch) {
            const low = mgmtSearch.toLowerCase();
            base = base.filter(u =>
                (u.staff_id && u.staff_id.toLowerCase().includes(low)) ||
                (u.first_name && u.first_name.toLowerCase().includes(low)) ||
                (u.last_name && u.last_name.toLowerCase().includes(low))
            );
        }
        return applySorting(applyFilters(base));
    }, [vehicleUsers, mgmtSearch, applyFilters, applySorting]);

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
            const res = await fetch('/hr/users/bulk-update', {
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
                    className={`subtab-btn active`}
                    onClick={() => setMgmtSubTab('staff')}
                >
                    Vehicles Directory
                </button>
            </div>

            {mgmtSubTab === 'staff' ? (
                <>
                    <div className="mgmt-header">
                        <div className="mgmt-actions">
                            <input
                                type="text"
                                placeholder="Search by Plate Number, Make..."
                                className="mgmt-search"
                                value={mgmtSearch}
                                onChange={(e) => { setMgmtSearch(e.target.value); setMgmtPage(1); }}
                            />
                            <button
                                className="btn-primary"
                                onClick={() => {
                                    setCurrentUser({ staffId: '', email: '', password: '', roleId: 4, siteId: '', departmentName: 'Vehicle' });
                                    setShowUserModal(true);
                                }}>
                                + Add New Vehicle
                            </button>
                            <button
                                className="btn-secondary"
                                onClick={() => {
                                    const formattedData = formatDataForExport(mgmtUsers);
                                    exportToCSV(formattedData, `staff_export_${new Date().toISOString().split('T')[0]}.csv`);
                                    showToast('Staff data exported successfully', 'success');
                                }}
                            >
                                Export CSV
                            </button>
                            <button
                                className={`btn-secondary ${showFilters ? 'active' : ''}`}
                                onClick={() => setShowFilters(!showFilters)}
                            >
                                Filters {(selectedRoles.length + selectedSites.length) > 0 && `(${selectedRoles.length + selectedSites.length})`}
                            </button>
                        </div>
                    </div>

                    {selectedUsers.length > 0 && (
                        <div className="bulk-actions-panel">
                            <div className="bulk-actions-header">
                                <div className="bulk-actions-selected">
                                    <span className="bulk-selected-pill">
                                        {selectedUsers.length}
                                    </span>
                                    <span className="bulk-selected-label">User(s) Selected</span>
                                </div>
                                <div className="bulk-actions-buttons">
                                    <button className="btn-secondary bulk-btn-sm" onClick={handleBulkExport}>Export</button>
                                    <button className="btn-secondary bulk-btn-sm bulk-btn-archive" onClick={handleBulkArchive}>Archive</button>
                                    <button className="btn-secondary bulk-btn-sm bulk-btn-delete" onClick={handleBulkDelete}>Delete</button>
                                    <button className="btn-secondary bulk-btn-sm" onClick={() => { setSelectedUsers([]); setSelectAll(false); }}>Clear</button>
                                </div>
                            </div>

                            <div className="bulk-actions-grid">
                                {/* Bulk Shift */}
                                <div className="bulk-action-group">
                                    <select
                                        value={bulkShiftId}
                                        onChange={(e) => setBulkShiftId(e.target.value)}
                                    >
                                        <option value="">Select Shift...</option>
                                        {shifts.map(s => <option key={s.id} value={s.id}>{s.name} ({s.start_time} - {s.end_time})</option>)}
                                    </select>
                                    <button className="btn-secondary bulk-btn-sm" onClick={() => handleBulkUpdate('shift')}>Apply Shift</button>
                                </div>

                                {/* Bulk Site */}
                                <div className="bulk-action-group">
                                    <select
                                        value={bulkSiteId}
                                        onChange={(e) => setBulkSiteId(e.target.value)}
                                    >
                                        <option value="">Select Site...</option>
                                        <option value="-1">Global / Remotely (No Site)</option>
                                        {sites.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                                    </select>
                                    <button className="btn-secondary bulk-btn-sm" onClick={() => handleBulkUpdate('site')}>Apply Site</button>
                                </div>

                                {/* Bulk Department */}
                                <div className="bulk-action-group">
                                    <input
                                        type="text"
                                        placeholder="Dept Name..."
                                        value={bulkDeptName}
                                        onChange={(e) => setBulkDeptName(e.target.value)}
                                    />
                                    <button className="btn-secondary bulk-btn-sm" onClick={() => handleBulkUpdate('dept')}>Apply Dept</button>
                                </div>

                                {/* Tracking Flags */}
                                <div className="bulk-action-group">
                                    <button className="btn-secondary bulk-btn-sm bulk-btn-enable" onClick={() => handleBulkUpdate('tracking-on')}>Enable Tracking</button>
                                    <button className="btn-secondary bulk-btn-sm bulk-btn-disable" onClick={() => handleBulkUpdate('tracking-off')}>Disable Tracking</button>
                                </div>
                            </div>
                        </div>
                    )}

                    {showFilters && (
                        <div className="filter-panel-wrap">
                            <FilterPanel />
                        </div>
                    )}

                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th className="table-col-check">
                                        <input
                                            type="checkbox"
                                            checked={selectAll}
                                            onChange={handleSelectAll}
                                            className="user-checkbox"
                                        />
                                    </th>
                                    <th className="table-col-photo">Photo</th>
                                    <th
                                        onClick={() => {
                                            if (sortField === 'staff_id') {
                                                setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
                                            } else {
                                                setSortField('staff_id');
                                                setSortDirection('asc');
                                            }
                                        }}
                                        className="sortable-header"
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
                                        className="sortable-header"
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
                                        className="sortable-header"
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
                                        className="sortable-header"
                                    >
                                        Department {sortField === 'department_name' && (sortDirection === 'asc' ? '↑' : '↓')}
                                    </th>
                                    <th>Actions</th>
                                </tr>
                            </thead>
                            <tbody>
                                {isMgmtLoading ? (
                                    <tr>
                                        <td colSpan={9} className="table-cell-clean">
                                            <LoadingSpinner size="medium" text="Loading staff..." />
                                        </td>
                                    </tr>
                                ) : filteredUsers.length === 0 ? (
                                    <tr>
                                        <td colSpan={11} className="table-cell-clean">
                                            <div className="empty-state">
                                                <div className="empty-state-icon">--</div>
                                                <h3 className="empty-state-title">No Vehicles Found</h3>
                                                <p className="empty-state-message">
                                                    {mgmtSearch ? 'Try adjusting your search' : 'Get started by adding your first vehicle'}
                                                </p>
                                            </div>
                                        </td>
                                    </tr>
                                ) : (
                                    filteredUsers.filter(u => u.department_name === 'Vehicle').map(u => (
                                        <tr key={u.id} className={selectedUsers.includes(u.id) ? 'table-row-selected' : ''}>
                                            <td>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedUsers.includes(u.id)}
                                                    onChange={() => handleSelectUser(u.id)}
                                                    className="user-checkbox"
                                                />
                                            </td>
                                            <td>
                                                <div className="user-cell">
                                                    <div className="user-avatar avatar-vehicle">
                                                        VH
                                                    </div>
                                                </div>
                                            </td>
                                            <td><strong>{u.staff_id}</strong></td>
                                            <td>
                                                <span className="role-badge role-badge-neutral">
                                                    {u.first_name || 'N/A'}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="vehicle-meta-chip">
                                                    {u.last_name || 'N/A'}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="site-badge site-badge-primary">
                                                    {u.role_name}
                                                </span>
                                            </td>
                                            <td>
                                                <span className="site-badge">
                                                    {u.site_name || 'All Sites'}
                                                </span>
                                            </td>
                                            <td className="mono-muted">
                                                {u.id}
                                            </td>
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
            ) : null}
        </div>
    );
}