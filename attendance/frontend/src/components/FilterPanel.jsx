import React, { useState, useRef, useEffect } from 'react';
import './FilterPanel.css';

const FilterPanel = ({
    roles,
    sites,
    selectedRoles,
    selectedSites,
    onRoleChange,
    onSiteChange,
    onClear
}) => {
    // Sites Dropdown State
    const [siteSearchTerm, setSiteSearchTerm] = useState('');
    const [isSiteDropdownOpen, setIsSiteDropdownOpen] = useState(false);
    const siteDropdownRef = useRef(null);

    // Roles Dropdown State
    const [roleSearchTerm, setRoleSearchTerm] = useState('');
    const [isRoleDropdownOpen, setIsRoleDropdownOpen] = useState(false);
    const roleDropdownRef = useRef(null);

    // Handle click outside to close dropdowns
    useEffect(() => {
        const handleClickOutside = (event) => {
            if (siteDropdownRef.current && !siteDropdownRef.current.contains(event.target)) {
                setIsSiteDropdownOpen(false);
            }
            if (roleDropdownRef.current && !roleDropdownRef.current.contains(event.target)) {
                setIsRoleDropdownOpen(false);
            }
        };

        document.addEventListener('mousedown', handleClickOutside);
        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
    }, []);

    const handleRoleToggle = (roleId) => {
        if (selectedRoles.includes(roleId)) {
            onRoleChange(selectedRoles.filter(id => id !== roleId));
        } else {
            onRoleChange([...selectedRoles, roleId]);
        }
    };

    const handleSiteToggle = (siteId) => {
        if (selectedSites.includes(siteId)) {
            onSiteChange(selectedSites.filter(id => id !== siteId));
        } else {
            onSiteChange([...selectedSites, siteId]);
        }
    };

    const hasFilters = selectedRoles.length > 0 || selectedSites.length > 0;

    // Combine all site options including Global
    const allSiteOptions = [
        { id: 'global', name: 'Global / Unassigned' },
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

    return (
        <div className="filter-panel">
            <div className="filter-header">
                <h4>Filters</h4>
                {hasFilters && (
                    <button className="filter-clear-btn" onClick={onClear}>
                        Clear All
                    </button>
                )}
            </div>

            <div className="filter-section">
                <label className="filter-label">Roles</label>
                <div className="dropdown-container" ref={roleDropdownRef}>
                    <button
                        className="dropdown-trigger"
                        onClick={() => setIsRoleDropdownOpen(!isRoleDropdownOpen)}
                        aria-expanded={isRoleDropdownOpen}
                    >
                        <span>
                            {selectedRoles.length === 0
                                ? 'Select Roles...'
                                : `${selectedRoles.length} Role${selectedRoles.length > 1 ? 's' : ''} Selected`}
                        </span>
                        <svg
                            className="dropdown-arrow"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>

                    {isRoleDropdownOpen && (
                        <div className="dropdown-menu">
                            <div className="dropdown-search">
                                <input
                                    type="text"
                                    placeholder="Search roles..."
                                    value={roleSearchTerm}
                                    onChange={(e) => setRoleSearchTerm(e.target.value)}
                                    autoFocus
                                    onClick={(e) => e.stopPropagation()}
                                />
                            </div>
                            <div className="dropdown-list">
                                {filteredRoles.length > 0 ? (
                                    filteredRoles.map(role => (
                                        <label key={role.id} className="filter-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={selectedRoles.includes(role.id)}
                                                onChange={() => handleRoleToggle(role.id)}
                                            />
                                            <span>{role.name}</span>
                                        </label>
                                    ))
                                ) : (
                                    <div style={{ padding: '0.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>
                                        No roles found
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>

            <div className="filter-section">
                <label className="filter-label">Sites</label>
                <div className="dropdown-container" ref={siteDropdownRef}>
                    <button
                        className="dropdown-trigger"
                        onClick={() => setIsSiteDropdownOpen(!isSiteDropdownOpen)}
                        aria-expanded={isSiteDropdownOpen}
                    >
                        <span>
                            {selectedSites.length === 0
                                ? 'Select Sites...'
                                : `${selectedSites.length} Site${selectedSites.length > 1 ? 's' : ''} Selected`}
                        </span>
                        <svg
                            className="dropdown-arrow"
                            width="16"
                            height="16"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                        >
                            <polyline points="6 9 12 15 18 9"></polyline>
                        </svg>
                    </button>

                    {isSiteDropdownOpen && (
                        <div className="dropdown-menu">
                            <div className="dropdown-search">
                                <input
                                    type="text"
                                    placeholder="Search sites..."
                                    value={siteSearchTerm}
                                    onChange={(e) => setSiteSearchTerm(e.target.value)}
                                    autoFocus
                                    onClick={(e) => e.stopPropagation()}
                                />
                            </div>
                            <div className="dropdown-list">
                                {filteredSites.length > 0 ? (
                                    filteredSites.map(site => (
                                        <label key={site.id} className="filter-checkbox">
                                            <input
                                                type="checkbox"
                                                checked={selectedSites.includes(site.id)}
                                                onChange={() => handleSiteToggle(site.id)}
                                            />
                                            <span>{site.name}</span>
                                        </label>
                                    ))
                                ) : (
                                    <div style={{ padding: '0.5rem', textAlign: 'center', color: '#64748b', fontSize: '0.875rem' }}>
                                        No sites found
                                    </div>
                                )}
                            </div>
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
};

export default FilterPanel;
