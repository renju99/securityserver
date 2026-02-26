import React, { useState } from 'react';
import jsPDF from 'jspdf';
import autoTable from 'jspdf-autotable';
import FilterPanel from './FilterPanel';
import { LoadingSpinner } from './LoadingSpinner';
import { exportToCSV } from '../utils/exportUtils';

const ReportsView = ({ user, sites, roles, showToast }) => {
    // Default to current month
    const now = new Date();
    const firstDay = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split('T')[0];
    const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split('T')[0];

    const [startDate, setStartDate] = useState(firstDay);
    const [endDate, setEndDate] = useState(lastDay);

    // Filters
    const [selectedRole, setSelectedRole] = useState([]); // FilterPanel uses arrays
    const [selectedSite, setSelectedSite] = useState([]);
    const [department, setDepartment] = useState('');
    const [dataSource, setDataSource] = useState('app'); // 'app' or 'biometric'

    const [reportData, setReportData] = useState(null);
    const [isLoading, setIsLoading] = useState(false);

    const fetchReport = async () => {
        setIsLoading(true);
        try {
            const query = new URLSearchParams({
                startDate,
                endDate,
                ...(selectedRole.length > 0 && { roleId: selectedRole[0] }), // Simple single filter for now or backend needs array
                ...(selectedSite.length > 0 && { siteId: selectedSite[0] }),
                ...(department && { department })
            });

            // My backend implementation used single value for now: e.role_id = $1. 
            // So let's stick to single value or pick first.

            const endpoint = dataSource === 'biometric' ? '/api/hr/reports/biometrics' : '/api/hr/reports/attendance';
            const res = await fetch(`${endpoint}?${query}`, {
                headers: { 'Authorization': `Bearer ${user.token}` }
            });

            if (!res.ok) throw new Error('Failed to fetch report');

            const data = await res.json();
            setReportData(data);
            showToast('Report generated successfully', 'success');
        } catch (err) {
            console.error(err);
            showToast('Error generating report', 'error');
        } finally {
            setIsLoading(false);
        }
    };

    const generatePDF = () => {
        if (!reportData || !reportData.employees.length) return;

        const doc = new jsPDF('l', 'mm', 'a3'); // Landscape A3 for more space

        // Title
        doc.setFontSize(18);
        doc.text('Biometric Attendance Report', 14, 15);

        // Metadata
        doc.setFontSize(10);
        doc.text(`Period: ${startDate} to ${endDate}`, 14, 22);

        // Prepare Table Data (Matrix)
        const start = new Date(startDate);
        const end = new Date(endDate);
        const dates = [];
        let curr = new Date(start);
        while (curr <= end) {
            dates.push(new Date(curr));
            curr.setDate(curr.getDate() + 1);
        }

        // Header
        const dateHeaders = dates.map(d => `${d.getMonth() + 1}/${d.getDate()}`);
        const head = [['Staff ID', 'Name', 'Dept', ...dateHeaders, 'Total P', 'Total A']];

        const body = reportData.employees.map(emp => {
            const empLogs = reportData.attendance[emp.id] || [];

            let presentCount = 0;
            let absentCount = 0;
            const empName = emp.first_name || emp.last_name ? `${emp.first_name || ''} ${emp.last_name || ''}`.trim() : '-';

            const days = dates.map(date => {
                const dateStr = date.toISOString().split('T')[0];
                const dayLogs = empLogs.filter(log => {
                    return new Date(log.check_in_time).toISOString().split('T')[0] === dateStr;
                });

                if (dayLogs.length > 0) {
                    presentCount++;
                    if (dataSource === 'biometric') {
                        const inTime = new Date(dayLogs[0].check_in_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        const outTime = dayLogs[0].check_out_time ? new Date(dayLogs[0].check_out_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '--:--';
                        return `${inTime}\n${outTime}`;
                    }
                    return 'P';
                } else {
                    absentCount++;
                    return 'A';
                }
            });

            return [emp.staff_id, empName, emp.department_name || '-', ...days, presentCount, absentCount];
        });

        autoTable(doc, {
            head: head,
            body: body,
            startY: 25,
            styles: { fontSize: 8, cellPadding: 1, halign: 'center' },
            headStyles: { fillColor: [66, 133, 244] },
            columnStyles: {
                0: { cellWidth: 20, halign: 'left' }, // ID
                1: { cellWidth: 30, halign: 'left' }, // Name
                2: { cellWidth: 25, halign: 'left' }, // Dept
            },
            didParseCell: (data) => {
                const colIdx = data.column.index;
                if (data.section === 'body' && colIdx >= 3 && colIdx < (3 + dates.length)) {
                    if (data.cell.raw === 'P') {
                        data.cell.styles.textColor = [0, 128, 0]; // Green
                    } else if (data.cell.raw === 'A') {
                        data.cell.styles.textColor = [200, 0, 0]; // Red
                    } else if (typeof data.cell.raw === 'string' && data.cell.raw.includes('\n')) {
                        data.cell.styles.fontSize = 6;
                        data.cell.styles.textColor = [0, 0, 0];
                    }
                }
            }
        });

        doc.save(`attendance_report_${startDate}_${endDate}.pdf`);
    };

    const generateExcel = () => {
        if (!reportData || !reportData.employees.length) return;

        const start = new Date(startDate);
        const end = new Date(endDate);
        const dates = [];
        let curr = new Date(start);
        while (curr <= end) {
            dates.push(new Date(curr));
            curr.setDate(curr.getDate() + 1);
        }

        const dateHeaders = dates.map(d => `${d.getMonth() + 1}/${d.getDate()}`);

        const exportRows = reportData.employees.map(emp => {
            const empLogs = reportData.attendance[emp.id] || [];
            let presentCount = 0;
            let absentCount = 0;
            const empName = emp.first_name || emp.last_name ? `${emp.first_name || ''} ${emp.last_name || ''}`.trim() : '-';

            const row = {
                'Staff ID': emp.staff_id,
                'Name': empName,
                'Department': emp.department_name || '-'
            };

            dates.forEach((date, index) => {
                const dateHeader = dateHeaders[index];
                const dateStr = date.toISOString().split('T')[0];
                const dayLogs = empLogs.filter(log => {
                    return new Date(log.check_in_time).toISOString().split('T')[0] === dateStr;
                });

                if (dayLogs.length > 0) {
                    presentCount++;
                    if (dataSource === 'biometric') {
                        const inTimeStr = new Date(dayLogs[0].check_in_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        let outTimeStr = '--:--';
                        if (dayLogs[0].check_out_time) {
                            outTimeStr = new Date(dayLogs[0].check_out_time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                        }
                        row[dateHeader] = `${inTimeStr} - ${outTimeStr}`;
                    } else {
                        row[dateHeader] = 'P';
                    }
                } else {
                    absentCount++;
                    row[dateHeader] = 'A';
                }
            });

            row['Total Present'] = presentCount;
            row['Total Absent'] = absentCount;
            return row;
        });

        exportToCSV(exportRows, `attendance_report_${startDate}_${endDate}.csv`);
    };

    return (
        <div className="reports-container">
            <div className="reports-card" style={{ flexShrink: 0 }}>
                <div className="reports-header">
                    <div>
                        <h2>Attendance Reports</h2>
                        <p style={{ margin: '4px 0 0', opacity: 0.8, fontSize: '0.9rem' }}>
                            Generate biometric attendance sheets for payroll and management
                        </p>
                    </div>
                    {isLoading && <LoadingSpinner size="small" />}
                </div>

                <div className="reports-body">
                    <div className="reports-grid">
                        <div className="report-config-section">
                            <h3 className="section-title">📅 Date Range</h3>
                            <div style={{ display: 'grid', gap: '1rem' }}>
                                <div className="report-form-group">
                                    <label>Start Date</label>
                                    <input
                                        type="date"
                                        className="control-input"
                                        value={startDate}
                                        onChange={(e) => setStartDate(e.target.value)}
                                    />
                                </div>
                                <div className="report-form-group">
                                    <label>End Date</label>
                                    <input
                                        type="date"
                                        className="control-input"
                                        value={endDate}
                                        onChange={(e) => setEndDate(e.target.value)}
                                    />
                                </div>

                                <div style={{ marginTop: '0.5rem' }}>
                                    <h3 className="section-title">📡 Data Source</h3>
                                    <div className="report-form-group" style={{ display: 'flex', gap: '1rem', marginTop: '0.5rem' }}>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: dataSource === 'app' ? 'bold' : 'normal' }}>
                                            <input
                                                type="radio"
                                                name="dataSource"
                                                value="app"
                                                checked={dataSource === 'app'}
                                                onChange={() => setDataSource('app')}
                                            />
                                            📱 Mobile App & NFC
                                        </label>
                                        <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', cursor: 'pointer', fontWeight: dataSource === 'biometric' ? 'bold' : 'normal' }}>
                                            <input
                                                type="radio"
                                                name="dataSource"
                                                value="biometric"
                                                checked={dataSource === 'biometric'}
                                                onChange={() => setDataSource('biometric')}
                                            />
                                            👤 Biometric Terminal
                                        </label>
                                    </div>
                                </div>

                                <div style={{ marginTop: '0.5rem' }}>
                                    <h3 className="section-title">🏢 Organization</h3>
                                    <div className="report-form-group">
                                        <label>Department Name</label>
                                        <input
                                            type="text"
                                            placeholder="e.g. Operations"
                                            className="control-input"
                                            value={department}
                                            onChange={(e) => setDepartment(e.target.value)}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                        <div className="report-filter-section">
                            <h3 className="section-title">🔍 Refine Results</h3>
                            <div style={{ background: '#f8fafc', padding: '1.5rem', borderRadius: '12px', border: '1px solid #edf2f7' }}>
                                <FilterPanel
                                    roles={roles}
                                    sites={sites}
                                    selectedRoles={selectedRole}
                                    selectedSites={selectedSite}
                                    onRoleChange={setSelectedRole}
                                    onSiteChange={setSelectedSite}
                                    onClear={() => { setSelectedRole([]); setSelectedSite([]); setDepartment(''); }}
                                />
                                <p style={{ fontSize: '0.75rem', color: '#94a3b8', marginTop: '1rem' }}>
                                    * Select multiple roles or sites to narrow down the report data.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>

                <div className="reports-footer">
                    <div style={{ color: '#64748b', fontSize: '0.9rem' }}>
                        {reportData ? `✅ Loaded ${reportData.employees.length} records` : 'Ready to generate report'}
                    </div>
                    <div className="reports-actions">
                        {reportData && (
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                                <button onClick={generateExcel} className="btn-report secondary" style={{ background: '#10b981', color: 'white', borderColor: '#10b981' }}>
                                    📊 Download Excel
                                </button>
                                <button onClick={generatePDF} className="btn-report secondary">
                                    📄 Download PDF
                                </button>
                            </div>
                        )}
                        <button
                            onClick={fetchReport}
                            className="btn-report primary"
                            disabled={isLoading}
                        >
                            {isLoading ? 'Generating...' : '🔍 View Report'}
                        </button>
                    </div>
                </div>
            </div>

            {reportData && (
                <div className="preview-section">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
                        <h3 style={{ margin: 0, fontSize: '1.25rem', color: '#1e293b' }}>📄 Report Preview</h3>
                        <span style={{ fontSize: '0.85rem', background: '#e0f2fe', color: '#0369a1', padding: '4px 12px', borderRadius: '20px', fontWeight: 600 }}>
                            {reportData.employees.length} Employees
                        </span>
                    </div>

                    <div className="mgmt-table-container">
                        <table className="mgmt-table">
                            <thead>
                                <tr>
                                    <th>Staff ID</th>
                                    <th>Staff Name</th>
                                    <th>Role</th>
                                    <th>Dept</th>
                                    <th>Site</th>
                                    <th style={{ textAlign: 'center' }}>Present Days</th>
                                </tr>
                            </thead>
                            <tbody>
                                {reportData.employees.map(emp => {
                                    const logs = reportData.attendance[emp.id] || [];
                                    return (
                                        <tr key={emp.id}>
                                            <td><strong>{emp.staff_id}</strong></td>
                                            <td>{emp.first_name || emp.last_name ? `${emp.first_name || ''} ${emp.last_name || ''}`.trim() : '-'}</td>
                                            <td><span className="role-tag">{emp.role_name || '-'}</span></td>
                                            <td>{emp.department_name || '-'}</td>
                                            <td>{emp.site_name || '-'}</td>
                                            <td style={{ textAlign: 'center', fontWeight: 'bold', color: logs.length > 0 ? '#16a34a' : '#ef4444' }}>
                                                {logs.length} Days
                                            </td>
                                        </tr>
                                    );
                                })}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}
        </div>
    );
};

export default ReportsView;
