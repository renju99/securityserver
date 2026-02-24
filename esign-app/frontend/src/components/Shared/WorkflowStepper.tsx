import React from 'react';
import { Approval } from '../../types';

interface WorkflowStepperProps {
    approvals: Approval[];
    currentStatus: string;
}

const WorkflowStepper: React.FC<WorkflowStepperProps> = ({ approvals, currentStatus }) => {
    const sortedApprovals = [...approvals].sort((a, b) => a.step_number - b.step_number);

    return (
        <div className="w-full py-6">
            <div className="flex items-center">
                {sortedApprovals.map((approval, index) => (
                    <React.Fragment key={approval.id}>
                        {/* Step Circle */}
                        <div className="flex flex-col items-center relative min-w-[100px]">
                            <div
                                className={`w-10 h-10 rounded-full border-2 flex items-center justify-center font-bold text-sm transition-all duration-300
                  ${approval.status === 'Signed'
                                        ? 'bg-green-600 border-green-600 text-white shadow-lg'
                                        : approval.status === 'Rejected'
                                            ? 'bg-red-600 border-red-600 text-white'
                                            : 'bg-white border-gray-300 text-gray-500'}`}
                            >
                                {approval.status === 'Signed' ? (
                                    <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="3" d="M5 13l4 4L19 7" />
                                    </svg>
                                ) : (
                                    approval.step_number
                                )}
                            </div>
                            <div className="mt-2 text-xs font-semibold text-gray-700 text-center max-w-[120px]">
                                {approval.role}
                            </div>
                            <div className="text-[10px] text-gray-400">
                                {approval.status}
                            </div>
                        </div>

                        {/* Connector Line */}
                        {index < sortedApprovals.length - 1 && (
                            <div className="flex-auto border-t-2 border-dashed border-gray-300 mx-2 -mt-10 self-center"></div>
                        )}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

export default WorkflowStepper;
