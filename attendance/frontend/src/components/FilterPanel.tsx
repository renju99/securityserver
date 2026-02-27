import React, { useState, useRef, useEffect } from 'react';
import { useDataStore } from '../store/useDataStore';
import './FilterPanel.css';

const FilterPanel = () => {
    const {
        roles, sites, shifts,
        selectedRoles, setSelectedRoles,
        selectedSites, setSelectedSites,
        selectedShifts, setSelectedShifts
    } = useDataStore();

    // Sites Dropdown State
    const [siteSearchTerm, setSiteSearchTerm] = useState('');
    const [isSiteDropdownOpen, setIsSiteDropdownOpen] = useState(false);
    const siteDropdownRef = useRef<HTMLDivElement>(null);

    // Roles Dropdown State
    const [roleSearchTerm, setRoleSearchTerm] = useState('');
    const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
    const roleDropdownRef = useRef<HTMLDivElement>(null);

    // Shifts Dropdown State
    const [shiftSearchTerm, setShiftSearchTerm] = useState('');
    const [isShiftDropdownOpen, setIsShiftDropdownOpen] = useState(false);
    const shiftDropdownRef = useRef<HTMLDivElement>(null);

    // Handle click outside to close dropdowns
    useEffect(() => {
        const handleClickOutside = (event: MouseEvent) => {
            if (siteDropdownRef.current && !siteDropdownRef.current.contains(event.target as Node)) {
                setIsSiteDropdownOpen(false);
            }
            if (roleDropdownRef.current && !roleDropdownRef.current.contains(event.target as Node)) {
                setIsRoleDropdownOpen(false);
            }
            if (shiftDropdownRef.current && !shiftDropdownRef.current.contains(event.target as Node)) {
                setIsShiftDropdownOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handleRoleToggle = (roleId: number | string) => {
        const id = Number(roleId);
        if (selectedRoles.includes(id)) {
            setSelectedRoles(selectedRoles.filter(item => item !== id));
        } else {
            setSelectedRoles([...selectedRoles, id]);
        }
    };

    const handleSiteToggle = (siteId: number | string) => {
        if (selectedSites.includes(siteId)) {
            setSelectedSites(selectedSites.filter(id => id !== siteId));
        } else {
            setSelectedSites([...selectedSites, siteId]);
        }
    };

    const handleShiftToggle = (shiftId: number | string) => {
        if (selectedShifts.includes(shiftId)) {
            setSelectedShifts(selectedShifts.filter(id => id !== shiftId));
        } else {
            setSelectedShifts([...selectedShifts, shiftId]);
        }
    };

    const onClear = () => {
        setSelectedRoles([]);
        setSelectedSites([]);
        setSelectedShifts([]);
    };

    const hasFilters = selectedRoles.length > 0 || selectedSites.length > 0 || selectedShifts.length > 0;

    // Combine all site options including Global
    const allSiteOptions = [
        { id: -1, name: 'Global / Unassigned' },
        ...sites
    ];

    // Filter sites based on search term
    const filteredSites = allSiteOptions.filter(site =>
        site.name.toLowerCase().includes(siteSearchTerm.toLowerCase())
    );

    // Filter roles based on search term
    const filteredRoles = roles.filter(role =>
        role.name.toLowerCase().includes(roleSearchTerm.toLowerCase())
    );

    // Filter shifts based on search term
    const filteredShifts = shifts.filter(shift =>
        shift.name.toLowerCase().includes(shiftSearchTerm.toLowerCase())
    );

    return (
        <div className="filter-panel">
            <div className="filter-header">
                <div className="filter-title">
                    <span>🔍</span> Filters
                    {hasFilters && <span className="filter-count">{selectedRoles.length + selectedSites.length + selectedShifts.length}</span>}
                </div>
                {hasFilters && (
                    <button className="clear-filters-btn" onClick={onClear}>
                        Clear All
                    </button>
                )}
            </div>

            <div className="filter-grid">
                {/* Roles Filter */}
                <div className="filter-section">
                    <label className="filter-label">Roles</label>
                    <div className="dropdown-container" ref={roleDropdownRef}>
                        <button
                            className={`dropdown-trigger ${selectedRoles.length > 0 ? 'has-selection' : ''}`}
                            onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
                        >
                            {selectedRoles.length === 0
                                ? 'All Roles'
                                : `${selectedRoles.length} Role${selectedRoles.length > 1 ? 's' : ''} Selected`}
                            <span className={`dropdown-arrow ${isRoleDropdownOpen ? 'open' : ''}`}>▼</span>
                        </button>

                        {isRoleDropdownOpen && (
                            <div className="dropdown-menu">
                                <div className="dropdown-search">
                                    <input
                                        type="text"
                                        placeholder="Search roles..."
                                        value={roleSearchTerm}
                                        onChange={(e) => setRoleSearchTerm(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        autoFocus
                                    />
                                </div>
                                <div className="dropdown-list">
                                    {filteredRoles.length > 0 ? (
                                        filteredRoles.map(role => (
                                            <label key={role.id} className="filter-checkbox" onClick={(e) => e.stopPropagation()}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedRoles.includes(role.id)}
                                                    onChange={() => handleRoleToggle(role.id)}
                                                />
                                                <span>{role.name}</span>
                                            </label>
                                        ))
                                    ) : (
                                        <div className="no-results">No roles found</div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Sites Filter */}
                <div className="filter-section">
                    <label className="filter-label">Sites</label>
                    <div className="dropdown-container" ref={siteDropdownRef}>
                        <button
                            className={`dropdown-trigger ${selectedSites.length > 0 ? 'has-selection' : ''}`}
                            onClick={() => setIsSiteDropdownOpen(!isSiteDropdownOpen)}
                        >
                            {selectedSites.length === 0
                                ? 'All Sites'
                                : `${selectedSites.length} Site${selectedSites.length > 1 ? 's' : ''} Selected`}
                            <span className={`dropdown-arrow ${isSiteDropdownOpen ? 'open' : ''}`}>▼</span>
                        </button>

                        {isSiteDropdownOpen && (
                            <div className="dropdown-menu">
                                <div className="dropdown-search">
                                    <input
                                        type="text"
                                        placeholder="Search sites..."
                                        value={siteSearchTerm}
                                        onChange={(e) => setSiteSearchTerm(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        autoFocus
                                    />
                                </div>
                                <div className="dropdown-list">
                                    {filteredSites.length > 0 ? (
                                        filteredSites.map(site => (
                                            <label key={site.id} className="filter-checkbox" onClick={(e) => e.stopPropagation()}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedSites.includes(site.id)}
                                                    onChange={() => handleSiteToggle(site.id)}
                                                />
                                                <span>{site.name}</span>
                                            </label>
                                        ))
                                    ) : (
                                        <div className="no-results">No sites found</div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>

                {/* Shifts Filter */}
                <div className="filter-section">
                    <label className="filter-label">Shifts</label>
                    <div className="dropdown-container" ref={shiftDropdownRef}>
                        <button
                            className={`dropdown-trigger ${selectedShifts.length > 0 ? 'has-selection' : ''}`}
                            onClick={() => setIsShiftDropdownOpen(!isShiftDropdownOpen)}
                        >
                            {selectedShifts.length === 0
                                ? 'All Shifts'
                                : `${selectedShifts.length} Shift${selectedShifts.length > 1 ? 's' : ''} Selected`}
                            <span className={`dropdown-arrow ${isShiftDropdownOpen ? 'open' : ''}`}>▼</span>
                        </button>

                        {isShiftDropdownOpen && (
                            <div className="dropdown-menu">
                                <div className="dropdown-search">
                                    <input
                                        type="text"
                                        placeholder="Search shifts..."
                                        value={shiftSearchTerm}
                                        onChange={(e) => setShiftSearchTerm(e.target.value)}
                                        onClick={(e) => e.stopPropagation()}
                                        autoFocus
                                    />
                                </div>
                                <div className="dropdown-list">
                                    {filteredShifts.length > 0 ? (
                                        filteredShifts.map(shift => (
                                            <label key={shift.id} className="filter-checkbox" onClick={(e) => e.stopPropagation()}>
                                                <input
                                                    type="checkbox"
                                                    checked={selectedShifts.includes(shift.id)}
                                                    onChange={() => handleShiftToggle(shift.id)}
                                                />
                                                <span>{shift.name} ({shift.start_time} - {shift.end_time})</span>
                                            </label>
                                        ))
                                    ) : (
                                        <div className="no-results">No shifts found</div>
                                    )}
                                </div>
                            </div>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
};

export default FilterPanel;
