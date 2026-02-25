import React, { useState } from 'react';
import { DocumentRequest, User } from '../../types';
import WorkflowStepper from '../Shared/WorkflowStepper';

interface RequestDetailModalProps {
    request: DocumentRequest;
    user: User | null;
    onClose: () => void;
    onRefresh: () => void;
    onViewDoc: (req: DocumentRequest) => void;
    onViewAttachment: (reqId: number, name: string, url: string) => void;
}

const RequestDetailModal: React.FC<RequestDetailModalProps> = ({
    request, user, onClose, onRefresh, onViewDoc, onViewAttachment
}) => {
    const [rejectComment, setRejectComment] = useState('');
    const [showRejectForm, setShowRejectForm] = useState(false);
    const [isProcessing, setIsProcessing] = useState(false);

    const canSign = (approval: any) => {
        if (approval.status !== 'Pending') return false;
        if (!user) return false;

        // Check if it's this user's turn
        const priorPending = request.approvals?.some(a => a.step_number < approval.step_number && a.status !== 'Signed');
        if (priorPending) return false;

        // Direct email match or role match
        const userRole = user.role.toLowerCase();
        const appRole = approval.role.toLowerCase();
        const userEmail = user.email.toLowerCase();

        return userRole === appRole || userEmail === appRole || user.role === 'Admin';
    };

    const currentPendingApproval = request.approvals?.find(canSign);

    const handleSign = async (approvalId: number) => {
        if (!user) return;
        setIsProcessing(true);
        try {
            const res = await fetch(`/api/approvals/${approvalId}/sign`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    user_email: user.email,
                    sig_type: 'signature',
                    use_saved: true, // Default to saved signature for speed
                    comment: 'Approved via Portal'
                })
            });

            if (res.ok) {
                onRefresh();
            } else {
                const err = await res.json();
                alert(`Signing failed: ${err.detail || 'Unknown error'}`);
            }
        } catch (e) {
            console.error(e);
            alert('Network error during signing');
        } finally {
            setIsProcessing(false);
        }
    };

    const handleReject = async () => {
        if (!user) return;
        setIsProcessing(true);
        try {
            const res = await fetch(`/api/requests/${request.id}/reject`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    comment: rejectComment,
                    user_email: user.email
                })
            });

            if (res.ok) {
                onRefresh();
                setShowRejectForm(false);
            } else {
                alert('Rejection failed');
            }
        } catch (e) {
            console.error(e);
            alert('Network error during rejection');
        } finally {
            setIsProcessing(false);
        }
    };

    return (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-md z-50 flex items-center justify-center p-4 overflow-y-auto animate-in fade-in duration-300">
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col overflow-hidden transform transition-all animate-in zoom-in-95 duration-300">
                {/* Header */}
                <div className="px-8 py-6 border-b border-gray-100 flex justify-between items-center bg-white">
                    <div>
                        <div className="flex items-center gap-3 mb-1">
                            <h2 className="text-2xl font-black text-gray-900 tracking-tight">Request Details</h2>
                            <span className="px-3 py-1 bg-indigo-50 text-indigo-700 rounded-full text-[10px] font-black uppercase tracking-widest">#{request.id}</span>
                        </div>
                        <p className="text-sm text-gray-500 font-medium">{request.doc_type} <span className="mx-2 text-gray-200">|</span> {request.department}</p>
                    </div>
                    <button onClick={onClose} className="p-3 hover:bg-gray-100 rounded-2xl transition-all group">
                        <svg className="w-6 h-6 text-gray-400 group-hover:text-gray-900" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                {/* Content */}
                <div className="flex-1 overflow-y-auto p-8 lg:p-10 space-y-12">
                    {/* Status Tracker */}
                    <section>
                        <div className="flex justify-between items-end mb-8">
                            <h3 className="text-xs font-black text-gray-400 uppercase tracking-[0.2em]">Live Approval Pipeline</h3>
                            <div className={`px-4 py-1.5 rounded-xl text-xs font-black uppercase tracking-wider shadow-sm border-2
                ${request.status === 'Approved' ? 'bg-emerald-50 text-emerald-600 border-emerald-100' :
                                    request.status === 'Rejected' ? 'bg-red-50 text-red-600 border-red-100' :
                                        'bg-amber-50 text-amber-600 border-amber-100'}`}>
                                {request.status}
                            </div>
                        </div>
                        <WorkflowStepper approvals={request.approvals} currentStatus={request.status} />
                    </section>

                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-10">
                        {/* Left/Main Column */}
                        <div className="lg:col-span-2 space-y-10">
                            <div className="bg-slate-50 rounded-[2rem] p-8 border border-slate-100/50">
                                <h4 className="font-black text-gray-900 mb-6 flex items-center gap-2">
                                    <svg className="w-5 h-5 text-indigo-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                                    Submission Intelligence
                                </h4>
                                <div className="grid grid-cols-1 sm:grid-cols-2 gap-8 text-sm">
                                    <div className="space-y-4">
                                        <div>
                                            <span className="text-gray-400 font-bold uppercase text-[10px] tracking-widest block mb-1">Initiator Name</span>
                                            <span className="font-bold text-gray-900 text-base">{request.requester_name}</span>
                                        </div>
                                        <div>
                                            <span className="text-gray-400 font-bold uppercase text-[10px] tracking-widest block mb-1">Digital Identity</span>
                                            <span className="font-medium text-gray-700">{request.requester_email}</span>
                                        </div>
                                    </div>
                                    <div className="space-y-4">
                                        <div>
                                            <span className="text-gray-400 font-bold uppercase text-[10px] tracking-widest block mb-1">Time Captured</span>
                                            <span className="font-medium text-gray-700">{new Date(request.created_at).toLocaleString()}</span>
                                        </div>
                                        {request.supporting_documents && request.supporting_documents.length > 0 && (
                                            <div>
                                                <span className="text-gray-400 font-bold uppercase text-[10px] tracking-widest block mb-1">Attachments</span>
                                                <div className="flex flex-wrap gap-2 mt-2">
                                                    {request.supporting_documents.map((doc, i) => (
                                                        <button
                                                            key={i}
                                                            onClick={() => onViewAttachment(request.id, doc.name, doc.url)}
                                                            className="px-3 py-1 bg-white border border-gray-200 rounded-lg text-xs font-bold text-indigo-600 hover:border-indigo-600 transition-all flex items-center gap-1 shadow-sm"
                                                        >
                                                            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.414a4 4 0 00-5.656-5.656l-6.415 6.415a6 6 0 108.486 8.486L20.5 13" /></svg>
                                                            {doc.name}
                                                        </button>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                </div>
                            </div>

                            <div>
                                <h4 className="font-black text-gray-900 mb-6 text-sm tracking-tight">Granular Audit Chain</h4>
                                <div className="space-y-4">
                                    {request.approvals?.sort((a, b) => a.step_number - b.step_number).map((app) => (
                                        <div key={app.id} className={`flex items-center justify-between p-6 rounded-2xl border-2 transition-all ${app.status === 'Signed' ? 'bg-emerald-50/30 border-emerald-100' : 'bg-white border-gray-50'}`}>
                                            <div className="flex items-center gap-5">
                                                <div className={`w-12 h-12 rounded-2xl flex items-center justify-center text-sm font-black shadow-inner ${app.status === 'Signed' ? 'bg-emerald-500 text-white' : 'bg-gray-100 text-gray-400'}`}>
                                                    {app.step_number}
                                                </div>
                                                <div>
                                                    <div className="text-base font-black text-gray-900">{app.role}</div>
                                                    <div className="flex items-center gap-2 mt-0.5">
                                                        <span className={`text-[10px] font-black uppercase tracking-widest ${app.status === 'Signed' ? 'text-emerald-600' : 'text-gray-400'}`}>{app.status}</span>
                                                        {app.signed_at && <span className="text-[10px] text-gray-300 font-bold underline">Validated {new Date(app.signed_at).toLocaleDateString()}</span>}
                                                    </div>
                                                </div>
                                            </div>

                                            {canSign(app) && !isProcessing && (
                                                <div className="flex gap-3">
                                                    <button
                                                        onClick={() => handleSign(app.id)}
                                                        className="bg-indigo-600 hover:bg-indigo-700 text-white px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all shadow-lg shadow-indigo-200"
                                                    >
                                                        Adopt & Sign
                                                    </button>
                                                    <button
                                                        onClick={() => setShowRejectForm(true)}
                                                        className="bg-white border border-red-100 text-red-500 hover:bg-red-50 px-6 py-2.5 rounded-xl text-xs font-black uppercase tracking-widest transition-all"
                                                    >
                                                        Reject
                                                    </button>
                                                </div>
                                            )}

                                            {isProcessing && canSign(app) && (
                                                <div className="flex items-center gap-2 text-indigo-600 font-bold text-xs">
                                                    <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                                                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none"></circle>
                                                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                                                    </svg>
                                                    Securing...
                                                </div>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Right Side / Preview */}
                        <div className="space-y-8">
                            <div className="sticky top-0">
                                <div className="bg-indigo-900 rounded-[2.5rem] p-8 border border-white/10 flex flex-col items-center justify-center text-center space-y-6 shadow-2xl overflow-hidden group">
                                    <div className="absolute top-0 right-0 w-32 h-32 bg-white/5 rounded-full -mr-16 -mt-16 pointer-events-none transition-transform group-hover:scale-110"></div>
                                    <div className="p-6 bg-white/10 rounded-3xl backdrop-blur-md border border-white/20 transform group-hover:rotate-6 transition-transform">
                                        <svg className="w-16 h-16 text-indigo-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                                        </svg>
                                    </div>
                                    <div>
                                        <h4 className="font-black text-white text-xl tracking-tight">Interactive Review</h4>
                                        <p className="text-sm text-indigo-200/60 max-w-[200px] mt-2 font-medium">Verify all fields and attachments before granting authorization.</p>
                                    </div>
                                    <button
                                        onClick={() => onViewDoc(request)}
                                        className="w-full bg-white text-indigo-900 py-4 rounded-2xl font-black text-xs uppercase tracking-[0.2em] flex items-center justify-center gap-3 hover:bg-indigo-50 transition-all shadow-xl"
                                    >
                                        View Secure PDF
                                    </button>
                                </div>

                                {request.form_data?.rejection_reason && (
                                    <div className="mt-8 bg-red-50 border-2 border-red-100 rounded-[2rem] p-6 animate-in slide-in-from-top-4">
                                        <div className="flex items-center gap-2 mb-3">
                                            <svg className="w-5 h-5 text-red-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>
                                            <h4 className="text-xs font-black text-red-600 uppercase tracking-widest">Rejection Trace</h4>
                                        </div>
                                        <p className="text-sm text-red-800 font-medium leading-relaxed italic">"{request.form_data.rejection_reason}"</p>
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Footer */}
                <div className="px-8 py-6 bg-slate-50 border-t border-slate-100 flex justify-end gap-4">
                    <button onClick={onClose} className="px-8 py-3 text-xs font-black text-slate-400 uppercase tracking-widest hover:text-indigo-600 transition-colors">Dismiss</button>
                </div>

                {/* Rejection Overlay */}
                {showRejectForm && (
                    <div className="absolute inset-0 bg-white/95 backdrop-blur-xl flex items-center justify-center p-8 z-[60] animate-in fade-in duration-300">
                        <div className="w-full max-w-lg space-y-8 text-center">
                            <div className="w-20 h-20 bg-red-100 rounded-3xl flex items-center justify-center mx-auto mb-4">
                                <svg className="w-10 h-10 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M6 18L18 6M6 6l12 12" /></svg>
                            </div>
                            <div>
                                <h3 className="text-3xl font-black text-gray-900 tracking-tight">Reject Request</h3>
                                <p className="text-gray-500 font-medium mt-2">Provide reason for audit and feedback.</p>
                            </div>
                            <textarea
                                className="w-full border-2 border-gray-100 rounded-[2rem] p-6 min-h-[160px] outline-none focus:ring-4 focus:ring-red-500/10 focus:border-red-500 transition-all font-medium text-gray-700 bg-white shadow-inner"
                                placeholder="Ex: Missing documentation, incorrect amount, wrong template used..."
                                value={rejectComment}
                                onChange={(e) => setRejectComment(e.target.value)}
                            />
                            <div className="flex gap-4">
                                <button
                                    onClick={() => setShowRejectForm(false)}
                                    className="flex-1 py-4 text-xs font-black text-gray-400 uppercase tracking-widest hover:bg-gray-100 rounded-2xl transition-all"
                                >
                                    Go Back
                                </button>
                                <button
                                    onClick={handleReject}
                                    disabled={!rejectComment || isProcessing}
                                    className="flex-1 py-4 text-xs font-black text-white bg-red-600 hover:bg-red-700 disabled:opacity-50 rounded-2xl transition-all shadow-xl shadow-red-200 tracking-widest uppercase"
                                >
                                    {isProcessing ? 'Processing...' : 'Confirm Rejection'}
                                </button>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    );
};

export default RequestDetailModal;
