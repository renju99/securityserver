import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Users, CheckCircle, Clock, FileText, RefreshCw } from 'lucide-react';

const authHeader = () => ({ Authorization: `Bearer ${localStorage.getItem('token')}` });

const Overview = () => {
    const [stats, setStats] = useState({ totalCheckins: 0, activeStaff: 0, completedToday: 0, pendingReports: 0 });
    const [recentActivity, setRecentActivity] = useState([]);
    const [chartData, setChartData] = useState([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => { fetchAll(); }, []);

    const fetchAll = async () => {
        setLoading(true);
        try {
            const [staffRes, reportsRes] = await Promise.all([
                axios.get('/api/staff', { headers: authHeader() }),
                axios.get('/api/reports', { headers: authHeader() }),
            ]);

            const staff = staffRes.data;
            const reports = reportsRes.data;

            // Build weekly chart data from reports
            const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            const dayCounts = [0, 0, 0, 0, 0, 0, 0];
            reports.forEach(r => {
                const d = new Date(r.date).getDay();
                dayCounts[d]++;
            });
            const chartArr = days.map((name, i) => ({ name, count: dayCounts[i] }));
            // Rotate so Mon is first
            const rotated = [...chartArr.slice(1), chartArr[0]];

            setStats({
                totalCheckins: reports.length,
                activeStaff: staff.filter(s => s.active).length,
                completedToday: reports.filter(r => {
                    const d = new Date(r.date);
                    const today = new Date();
                    return d.toDateString() === today.toDateString();
                }).length,
                pendingReports: 0
            });
            setChartData(rotated);
            setRecentActivity(reports.slice(0, 8));
        } catch (err) {
            console.error('Overview fetch error:', err);
        } finally {
            setLoading(false);
        }
    };

    const statCards = [
        { label: 'Total Check-ins', value: stats.totalCheckins, icon: <CheckCircle />, color: 'var(--primary)', bg: 'rgba(99,102,241,0.15)' },
        { label: 'Active Staff', value: stats.activeStaff, icon: <Users />, color: 'var(--secondary)', bg: 'rgba(236,72,153,0.15)' },
        { label: 'Completed Today', value: stats.completedToday, icon: <Clock />, color: 'var(--success)', bg: 'rgba(34,197,94,0.15)' },
        { label: 'Reports This Month', value: stats.totalCheckins, icon: <FileText />, color: 'var(--warning)', bg: 'rgba(245,158,11,0.15)' },
    ];

    return (
        <div className="fade-in">
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
                <h1>Analytics Overview</h1>
                <button className="btn btn-secondary" onClick={fetchAll} style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                    <RefreshCw size={16} className={loading ? 'spin' : ''} /> Refresh
                </button>
            </header>

            <section style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1.5rem', marginBottom: '2rem' }}>
                {statCards.map((card, i) => (
                    <div key={i} className="card glass" style={{ display: 'flex', alignItems: 'center', gap: '1.2rem' }}>
                        <div style={{ width: '52px', height: '52px', borderRadius: '14px', background: card.bg, color: card.color, display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
                            {card.icon}
                        </div>
                        <div>
                            <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem', marginBottom: '4px' }}>{card.label}</p>
                            <h3 style={{ fontSize: '1.75rem', fontWeight: '700' }}>{loading ? '…' : card.value}</h3>
                        </div>
                    </div>
                ))}
            </section>

            <section style={{ display: 'grid', gridTemplateColumns: '3fr 2fr', gap: '1.5rem' }}>
                <div className="card glass">
                    <h4 style={{ marginBottom: '1.5rem', color: 'var(--text-muted)', fontWeight: '600' }}>Attendance Trends (This Week)</h4>
                    <ResponsiveContainer width="100%" height={250}>
                        <BarChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.07)" />
                            <XAxis dataKey="name" stroke="#94a3b8" tick={{ fontSize: 12 }} />
                            <YAxis stroke="#94a3b8" tick={{ fontSize: 12 }} />
                            <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px' }} itemStyle={{ color: '#fff' }} />
                            <Bar dataKey="count" fill="var(--primary)" radius={[6, 6, 0, 0]} />
                        </BarChart>
                    </ResponsiveContainer>
                </div>

                <div className="card glass">
                    <h4 style={{ marginBottom: '1.5rem', color: 'var(--text-muted)', fontWeight: '600' }}>Recent Reports</h4>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        {recentActivity.length === 0 && <p style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>No reports yet.</p>}
                        {recentActivity.map(item => (
                            <div key={item.report_id || item.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.6rem 0', borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                                <div>
                                    <div style={{ fontSize: '0.85rem', fontWeight: '600' }}>{item.washroom_name || 'Washroom'}</div>
                                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{item.employee_name || 'Staff'}</div>
                                </div>
                                <span style={{ fontSize: '0.75rem', background: 'rgba(34,197,94,0.15)', color: 'var(--success)', padding: '2px 8px', borderRadius: '20px' }}>
                                    {item.items_completed || 0}/{item.items_total || 0}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            </section>
        </div>
    );
};

export default Overview;
