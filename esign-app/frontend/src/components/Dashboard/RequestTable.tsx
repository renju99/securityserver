import React, { useState } from 'react';
import { DocumentRequest } from '../../types';

interface RequestTableProps {
    requests: DocumentRequest[];
    requestSubTab: 'pending' | 'signed';
    isRequestVisible: (req: DocumentRequest, tab: 'pending' | 'signed') => boolean;
    selectedRequestIds: number[];
    setSelectedRequestIds: (ids: number[]) => void;
    handleOpenRequestDetail: (id: number) => void;
    handleSubmit: (id: number) => void;
    handleViewRequestDoc: (req: DocumentRequest) => void;
    getDisplayStatus: (req: DocumentRequest) => string;
    userRole?: string;
}

const RequestTable: React.FC<RequestTableProps> = ({
    requests,
    requestSubTab,
    isRequestVisible,
    selectedRequestIds,
    setSelectedRequestIds,
    handleOpenRequestDetail,
    handleSubmit,
    handleViewRequestDoc,
    getDisplayStatus,
    userRole
}) => {
    const [searchTerm, setSearchTerm] = useState('');

    const filteredRequests = requests
        .filter(req => isRequestVisible(req, requestSubTab))
        .filter(req => {
            const searchStr = (req.id + ' ' + req.template_name + ' ' + req.requester_name + ' ' + req.department).toLowerCase();
            return searchStr.includes(searchTerm.toLowerCase());
        });

    const allVisibleIds = filteredRequests.map(r => r.id);
    const isAllSelected = allVisibleIds.length > 0 && allVisibleIds.every(id => selectedRequestIds.includes(id));

    return (
        <div className="space-y-4">
            {/* Search Bar */}
            <div className="relative max-w-md">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                    </svg>
                </span>
                <input
                    type="text"
                    placeholder="Filter current view..."
                    className="w-full pl-10 pr-4 py-2 bg-white border border-gray-200 rounded-xl text-sm focus:ring-2 focus:ring-indigo-500 focus:border-transparent outline-none transition-all shadow-sm"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                />
            </div>

            {filteredRequests.length === 0 ? (
                <div className="text-center py-24 bg-white rounded-2xl border border-dashed border-gray-200 shadow-inner">
                    <p className="text-gray-400 text-lg">No {requestSubTab} requests found matching your filter.</p>
                </div>
            ) : (
                <div className="overflow-x-auto bg-white rounded-2xl shadow-sm border border-gray-100">
                    <table className="w-full text-base text-left text-gray-600">
                        <thead className="text-xs text-gray-400 uppercase bg-gray-50/50 border-b border-gray-100 font-bold">
                            <tr>
                                <th className="hidden sm:table-cell px-6 py-4 w-12 text-center">
                                    {userRole === 'Admin' && (
                                        <input
                                            type="checkbox"
                                            className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                                            checked={isAllSelected}
                                            onChange={(e) => {
                                                if (e.target.checked) {
                                                    const combined = [...selectedRequestIds, ...allVisibleIds];
                                                    setSelectedRequestIds(Array.from(new Set(combined)));
                                                } else {
                                                    setSelectedRequestIds(selectedRequestIds.filter(id => !allVisibleIds.includes(id)));
                                                }
                                            }}
                                        />
                                    )}
                                </th>
                                <th className="hidden sm:table-cell px-2 py-4 text-indigo-600 font-black">ID</th>
                                <th className="px-6 py-4 font-black">Document Details</th>
                                <th className="px-6 py-4 font-black text-center">Current Status</th>
                                <th className="hidden lg:table-cell px-6 py-4 font-black">Date Created</th>
                                <th className="px-6 py-4 text-right font-black">Actions</th>
                            </tr>
                        </thead>
                        <tbody className="divide-y divide-gray-100">
                            {filteredRequests.map(req => (
                                <tr key={req.id} className={`bg-white border-b hover:bg-gray-50 transition-colors align-middle ${selectedRequestIds.includes(req.id) ? 'bg-indigo-50/30' : ''}`}>
                                    <td className="hidden sm:table-cell px-6 py-4 text-center">
                                        {userRole === 'Admin' && (
                                            <input
                                                type="checkbox"
                                                className="w-4 h-4 rounded border-gray-300 text-indigo-600 focus:ring-indigo-500 cursor-pointer"
                                                checked={selectedRequestIds.includes(req.id)}
                                                onChange={(e) => {
                                                    if (e.target.checked) {
                                                        setSelectedRequestIds([...selectedRequestIds, req.id]);
                                                    } else {
                                                        setSelectedRequestIds(selectedRequestIds.filter(id => id !== req.id));
                                                    }
                                                }}
                                            />
                                        )}
                                    </td>
                                    <td className="hidden sm:table-cell px-2 py-4 font-bold text-indigo-600 text-xs">#{req.id}</td>
                                    <td className="px-6 py-4 min-w-0">
                                        <span className="font-bold text-gray-900 text-sm block truncate max-w-[150px] sm:max-w-none" title={req.template_name}>
                                            {req.template_name}
                                        </span>
                                        <span className="text-[11px] text-gray-400 block mt-0.5">
                                            {req.department} · {req.doc_type}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 text-center">
                                        <span
                                            className={`inline-flex px-3 py-1 rounded-full text-[10px] uppercase tracking-wider font-bold border-2
                        ${req.status === 'Draft' ? 'bg-gray-50 text-gray-500 border-gray-100' :
                                                    req.status === 'Pending Approval' ? 'bg-amber-50 text-amber-600 border-amber-100' :
                                                        req.status === 'Approved' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                                                            'bg-red-50 text-red-600 border-red-100'}`}
                                        >
                                            {getDisplayStatus(req)}
                                        </span>
                                    </td>
                                    <td className="hidden lg:table-cell px-6 py-4 text-xs font-medium text-gray-400">
                                        {new Date(req.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })}
                                    </td>
                                    <td className="px-6 py-4 text-right">
                                        <div className="flex justify-end items-center space-x-2">
                                            <button
                                                onClick={() => handleOpenRequestDetail(req.id)}
                                                className="bg-white border border-indigo-100 text-indigo-600 px-4 py-1.5 rounded-lg text-xs font-bold hover:bg-indigo-600 hover:text-white hover:border-indigo-600 transition-all shadow-sm"
                                            >
                                                Details
                                            </button>
                                            {req.status === 'Draft' ? (
                                                <button
                                                    onClick={() => handleSubmit(req.id)}
                                                    className="px-4 py-1.5 bg-indigo-600 text-white rounded-lg text-xs font-bold hover:bg-indigo-700 transition-all shadow-md shadow-indigo-100"
                                                >
                                                    Submit
                                                </button>
                                            ) : (
                                                <button
                                                    onClick={() => handleViewRequestDoc(req)}
                                                    className="p-2 bg-slate-50 border border-slate-200 text-slate-400 rounded-lg hover:text-indigo-600 hover:border-indigo-200 hover:bg-indigo-50 transition-all"
                                                    title="View Document"
                                                >
                                                    <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M7 21h10a2 2 0 002-2V9.414a1 1 0 00-.293-.707l-5.414-5.414A1 1 0 0012.707 3H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
                                                    </svg>
                                                </button>
                                            )}
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

export default RequestTable;
