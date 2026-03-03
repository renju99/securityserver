import React from 'react';
import { NavLink, Routes, Route, Navigate } from 'react-router-dom';
import { LayoutGrid, Globe, MapPin, Users, Calendar, FileText } from 'lucide-react';

import Overview from './admin/Overview';
import Projects from './admin/Projects';
import Washrooms from './admin/Washrooms';
import Staff from './admin/Staff';
import Schedules from './admin/Schedules';
import Reports from './admin/Reports';

const AdminDashboard = () => {
    return (
        <div className="admin-page fade-in">
            <aside className="sidebar glass">
                <div className="sidebar-header">
                    <h2>Admin Hub</h2>
                </div>
                <nav>
                    <NavLink to="/admin/overview" className={({ isActive }) => isActive ? "active" : ""}>
                        <LayoutGrid size={18} /> Overview
                    </NavLink>
                    <NavLink to="/admin/projects" className={({ isActive }) => isActive ? "active" : ""}>
                        <Globe size={18} /> Projects
                    </NavLink>
                    <NavLink to="/admin/washrooms" className={({ isActive }) => isActive ? "active" : ""}>
                        <MapPin size={18} /> Washrooms
                    </NavLink>
                    <NavLink to="/admin/staff" className={({ isActive }) => isActive ? "active" : ""}>
                        <Users size={18} /> Users
                    </NavLink>
                    <NavLink to="/admin/schedules" className={({ isActive }) => isActive ? "active" : ""}>
                        <Calendar size={18} /> Schedules
                    </NavLink>
                    <NavLink to="/admin/reports" className={({ isActive }) => isActive ? "active" : ""}>
                        <FileText size={18} /> Reports
                    </NavLink>
                </nav>
            </aside>

            <main className="admin-content">
                <Routes>
                    <Route path="overview" element={<Overview />} />
                    <Route path="projects" element={<Projects />} />
                    <Route path="washrooms" element={<Washrooms />} />
                    <Route path="staff" element={<Staff />} />
                    <Route path="schedules" element={<Schedules />} />
                    <Route path="reports" element={<Reports />} />
                    <Route path="/" element={<Navigate to="overview" replace />} />
                </Routes>
            </main>
        </div>
    );
};

export default AdminDashboard;
