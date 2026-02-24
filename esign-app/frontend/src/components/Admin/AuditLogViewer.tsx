import React, { useEffect, useState } from 'react';
import { AuditLog, EmailLog } from '../../types';

interface AuditLogViewerProps {
    fetchEmailLogs?: () => void;
    emailLogs?: EmailLog[];
}

const AuditLogViewer: React.FC<AuditLogViewerProps> = ({ fetchEmailLogs, emailLogs = [] }) => {
    const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
    const [loading, setLoading] = useState(true);
    const [activeSubTab, setActiveSubTab] = useState<'system' | 'email'>('system');

    const fetchAuditLogs = async () => {
        try {
            const res = await fetch('/api/admin/audit-logs');
            if (res.ok) {
                const data = await res.json();
                setAuditLogs(data);
            }
        } catch (e) {
            console.error("Failed to fetch audit logs", e);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchAuditLogs();
        if (fetchEmailLogs) fetchEmailLogs();
    }, []);

    const refreshAll = () => {
        setLoading(true);
        fetchAuditLogs();
        if (fetchEmailLogs) fetchEmailLogs();
    };

    return (
        <div className="bg-white rounded-[2rem] shadow-xl border border-gray-100 overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="px-8 py-6 border-b border-gray-100 flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-gray-50/30">
                <div>
                    <h3 className="text-xl font-black text-gray-900 tracking-tight">Operation Intelligence</h3>
                    <div className="flex gap-4 mt-2">
                        <button
                            onClick={() => setActiveSubTab('system')}
                            className={`text-[10px] font-black uppercase tracking-widest pb-1 border-b-2 transition-all ${activeSubTab === 'system' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'}`}
                        >
                            System Audit
                        </button>
                        <button
                            onClick={() => setActiveSubTab('email')}
                            className={`text-[10px] font-black uppercase tracking-widest pb-1 border-b-2 transition-all ${activeSubTab === 'email' ? 'border-indigo-600 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'}`}
                        >
                            Email Traffic
                        </button>
                    </div>
                </div>
                <button
                    onClick={refreshAll}
                    className="group flex items-center gap-2 bg-white border-2 border-indigo-50 px-4 py-2 rounded-xl text-xs font-black text-indigo-600 hover:bg-indigo-600 hover:text-white transition-all shadow-sm"
                >
                    <svg className={`w-4 h-4 ${loading ? 'animate-spin' : 'group-hover:rotate-180 transition-transform duration-500'}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                    Refresh Logs
                </button>
            </div>

            <div className="overflow-x-auto">
                <table className="w-full text-left text-sm border-collapse">
                    {activeSubTab === 'system' ? (
                        <>
                            <thead className="bg-gray-50 text-gray-400 uppercase text-[10px] font-black tracking-widest">
                                <tr>
                                    <th className="px-8 py-4">Timeline</th>
                                    <th className="px-8 py-4">Executive</th>
                                    <th className="px-8 py-4">Action</th>
                                    <th className="px-8 py-4">Resource Info</th>
                                    <th className="px-8 py-4">Client IP</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {auditLogs.map((log) => (
                                    <tr key={log.id} className="hover:bg-indigo-50/20 transition-colors group">
                                        <td className="px-8 py-5 text-gray-400 font-medium tabular-nums text-xs">
                                            {new Date(log.timestamp).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                        </td>
                                        <td className="px-8 py-5">
                                            <div className="font-bold text-gray-900">{log.user_email.split('@')[0]}</div>
                                            <div className="text-[10px] text-gray-400 lowercase">{log.user_email}</div>
                                        </td>
                                        <td className="px-8 py-5">
                                            <span className={`px-2.5 py-1 rounded-lg text-[9px] font-black tracking-widest uppercase border
                                          ${log.action.includes('SUCCESS') || log.action.includes('SIGN') || log.action.includes('CREATE') ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                                                    log.action.includes('FAILED') || log.action.includes('REJECT') || log.action.includes('DELETE') ? 'bg-red-50 text-red-600 border-red-100' :
                                                        'bg-indigo-50 text-indigo-700 border-indigo-100'}`}>
                                                {log.action}
                                            </span>
                                        </td>
                                        <td className="px-8 py-5">
                                            <div className="flex items-center gap-2">
                                                <span className="text-gray-500 font-bold text-xs">{log.resource_type}</span>
                                                {log.resource_id && <span className="px-1.5 py-0.5 bg-gray-100 text-gray-400 rounded-md text-[9px] font-bold">#{log.resource_id}</span>}
                                            </div>
                                        </td>
                                        <td className="px-8 py-5 tabular-nums text-gray-400 text-xs font-medium">
                                            {log.ip_address || '---.---.---.---'}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </>
                    ) : (
                        <>
                            <thead className="bg-gray-50 text-gray-400 uppercase text-[10px] font-black tracking-widest">
                                <tr>
                                    <th className="px-8 py-4">Status</th>
                                    <th className="px-8 py-4">Recipient</th>
                                    <th className="px-8 py-4">Subject</th>
                                    <th className="px-8 py-4">Timeline</th>
                                    <th className="px-8 py-4 text-right">Req ID</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-gray-50">
                                {emailLogs.map((log) => (
                                    <tr key={log.id} className="hover:bg-indigo-50/20 transition-colors">
                                        <td className="px-8 py-5">
                                            <span className={`px-2.5 py-1 rounded-lg text-[9px] font-black uppercase tracking-widest border ${log.status === 'Sent' ? 'bg-green-50 text-green-700 border-green-100' : 'bg-red-50 text-red-700 border-red-100'}`}>
                                                {log.status}
                                            </span>
                                        </td>
                                        <td className="px-8 py-5 font-bold text-gray-900 text-xs">{log.recipient}</td>
                                        <td className="px-8 py-5 text-gray-500 text-xs italic">"{log.subject}"</td>
                                        <td className="px-8 py-5 text-gray-400 text-xs tabular-nums">{new Date(log.sent_at).toLocaleString()}</td>
                                        <td className="px-8 py-5 text-right font-black text-indigo-400 text-xs">#{log.request_id}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </>
                    )}
                </table>

                {((activeSubTab === 'system' && auditLogs.length === 0) || (activeSubTab === 'email' && emailLogs.length === 0)) && !loading && (
                    <div className="px-8 py-20 text-center">
                        <div className="w-16 h-16 bg-gray-50 rounded-2xl flex items-center justify-center mx-auto mb-4 border border-dashed border-gray-200">
                            <svg className="w-8 h-8 text-gray-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M4 7v10c0 2 1 3 3 3h10c2 0 3-1 3-3V7c0-2-1-3-3-3H7c-2 0-3 1-3 3z M12 12m-3 0a3 3 0 1 0 6 0a3 3 0 1 0 -6 0" /></svg>
                        </div>
                        <p className="text-gray-400 font-bold uppercase text-[10px] tracking-widest">No activity captured in this segment.</p>
                    </div>
                )}
            </div>
        </div>
    );
};

export default AuditLogViewer;
