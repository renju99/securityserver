import React, { useState, useEffect } from 'react';
import { NavLink } from 'react-router-dom';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts';
import { Users, MapPin, CheckCircle, Clock } from 'lucide-react';

const AdminDashboard = () => {
    const [stats, setStats] = useState({
        totalCheckins: 142,
        activeCleaners: 12,
        onTimeRate: '94%',
        pendingReports: 5
    });

    const [recentAttendance, setRecentAttendance] = useState([
        { id: 1, employee: 'John Doe', location: 'Main Lobby', time: '10:15 AM', status: 'on_time' },
        { id: 2, employee: 'Jane Smith', location: 'Conf Room A', time: '09:45 AM', status: 'late' },
        { id: 3, employee: 'Mike Ross', location: 'Gymnasium', time: '09:00 AM', status: 'on_time' },
    ]);

    const chartData = [
        { name: 'Mon', count: 40 },
        { name: 'Tue', count: 35 },
        { name: 'Wed', count: 55 },
        { name: 'Thu', count: 48 },
        { name: 'Fri', count: 62 },
        { name: 'Sat', count: 20 },
        { name: 'Sun', count: 18 },
    ];

    return (
        <div className="admin-page fade-in">
            <aside className="sidebar glass">
                <div className="sidebar-header">
                    <h2>Admin Hub</h2>
                </div>
                <nav>
                    <NavLink to="/admin" className={({ isActive }) => isActive ? "active" : ""}>Overview</NavLink>
                    <NavLink to="/admin/projects" className={({ isActive }) => isActive ? "active" : ""}>Projects</NavLink>
                    <NavLink to="/admin/washrooms" className={({ isActive }) => isActive ? "active" : ""}>Washrooms</NavLink>
                    <NavLink to="/admin/staff" className={({ isActive }) => isActive ? "active" : ""}>Staff</NavLink>
                    <NavLink to="/admin/schedules" className={({ isActive }) => isActive ? "active" : ""}>Schedules</NavLink>
                    <NavLink to="/admin/reports" className={({ isActive }) => isActive ? "active" : ""}>Reports</NavLink>
                </nav>
            </aside>

            <main className="admin-content">
                <header className="content-header">
                    <h1>Analytics Overview</h1>
                    <button className="btn btn-primary">Generate Report</button>
                </header>

                <section className="stats-grid">
                    <div className="stat-card card glass">
                        <div className="icon-box primary"><CheckCircle /></div>
                        <div>
                            <p>Total Check-ins</p>
                            <h3>{stats.totalCheckins}</h3>
                        </div>
                    </div>
                    <div className="stat-card card glass">
                        <div className="icon-box secondary"><Users /></div>
                        <div>
                            <p>Active Staff</p>
                            <h3>{stats.activeCleaners}</h3>
                        </div>
                    </div>
                    <div className="stat-card card glass">
                        <div className="icon-box warning"><Clock /></div>
                        <div>
                            <p>On-Time Rate</p>
                            <h3>{stats.onTimeRate}</h3>
                        </div>
                    </div>
                </section>

                <section className="charts-grid">
                    <div className="chart-container card glass">
                        <h4>Attendance Trends</h4>
                        <ResponsiveContainer width="100%" height={250}>
                            <BarChart data={chartData}>
                                <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
                                <XAxis dataKey="name" stroke="#94a3b8" />
                                <YAxis stroke="#94a3b8" />
                                <Tooltip
                                    contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }}
                                    itemStyle={{ color: '#fff' }}
                                />
                                <Bar dataKey="count" fill="var(--primary)" radius={[4, 4, 0, 0]} />
                            </BarChart>
                        </ResponsiveContainer>
                    </div>

                    <div className="recent-list card glass">
                        <h4>Recent Activity</h4>
                        <div className="table-wrapper">
                            <table>
                                <thead>
                                    <tr>
                                        <th>Staff</th>
                                        <th>Location</th>
                                        <th>Time</th>
                                        <th>Status</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {recentAttendance.map(item => (
                                        <tr key={item.id}>
                                            <td>{item.employee}</td>
                                            <td>{item.location}</td>
                                            <td>{item.time}</td>
                                            <td>
                                                <span className={`status-tag ${item.status}`}>
                                                    {item.status.replace('_', ' ')}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </section>
            </main>

            <style jsx>{`
        .admin-page {
          display: flex;
          min-height: 100vh;
        }
        .sidebar {
          width: 260px;
          height: 100vh;
          position: sticky;
          top: 0;
          padding: 2rem 1.5rem;
          display: flex;
          flex-direction: column;
          gap: 2rem;
          border-radius: 0;
          border-left: none;
          border-top: none;
          border-bottom: none;
        }
        .sidebar-header h2 { font-size: 1.5rem; color: var(--primary); }
        nav { display: flex; flex-direction: column; gap: 0.5rem; }
        nav a {
          padding: 0.75rem 1rem;
          border-radius: 8px;
          color: var(--text-muted);
          text-decoration: none;
          transition: all 0.2s;
        }
        nav a:hover, nav a.active {
          background: rgba(99, 102, 241, 0.1);
          color: var(--primary);
        }
        .admin-content {
          flex: 1;
          padding: 2rem;
          display: flex;
          flex-direction: column;
          gap: 2rem;
        }
        .content-header {
          display: flex;
          justify-content: space-between;
          align-items: center;
        }
        .stats-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
          gap: 1.5rem;
        }
        .stat-card {
          display: flex;
          align-items: center;
          gap: 1.5rem;
        }
        .icon-box {
          width: 48px;
          height: 48px;
          border-radius: 12px;
          display: flex;
          align-items: center;
          justify-content: center;
          color: white;
        }
        .icon-box.primary { background: var(--primary); }
        .icon-box.secondary { background: var(--secondary); }
        .icon-box.warning { background: var(--warning); }
        .stat-card p { color: var(--text-muted); font-size: 0.9rem; }
        .stat-card h3 { font-size: 1.75rem; }
        
        .charts-grid {
          display: grid;
          grid-template-columns: 3fr 2fr;
          gap: 1.5rem;
        }
        .chart-container h4, .recent-list h4 { margin-bottom: 1.5rem; color: var(--text-muted); }
        
        .table-wrapper { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; }
        th { text-align: left; color: var(--text-muted); font-size: 0.8rem; padding: 0.75rem; border-bottom: 1px solid rgba(255,255,255,0.05); }
        td { padding: 0.75rem; font-size: 0.9rem; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .status-tag {
          padding: 2px 8px;
          border-radius: 4px;
          font-size: 0.75rem;
          text-transform: capitalize;
        }
        .status-tag.on_time { background: rgba(34, 197, 94, 0.2); color: var(--success); }
        .status-tag.late { background: rgba(245, 158, 11, 0.2); color: var(--warning); }
      `}</style>
        </div>
    );
};

export default AdminDashboard;
