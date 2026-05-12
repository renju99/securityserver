import React from 'react';
import './ConfirmDialog.css';

const ConfirmDialog = ({
    isOpen,
    title,
    message,
    confirmText = 'Confirm',
    cancelText = 'Cancel',
    onConfirm,
    onCancel,
    type = 'danger' // 'danger', 'warning', 'info'
}) => {
    if (!isOpen) return null;

    return (
        <div className="confirm-overlay" onClick={onCancel} role="presentation">
            <div
                className="confirm-dialog"
                role="alertdialog"
                aria-modal="true"
                aria-labelledby="confirm-dialog-title"
                aria-describedby="confirm-dialog-desc"
                onClick={(e) => e.stopPropagation()}
            >
                <h3 id="confirm-dialog-title" className="confirm-title">{title}</h3>
                <p id="confirm-dialog-desc" className="confirm-message">{message}</p>
                <div className="confirm-actions">
                    <button
                        type="button"
                        className="btn-confirm-cancel"
                        onClick={onCancel}
                    >
                        {cancelText}
                    </button>
                    <button
                        type="button"
                        className={`btn-confirm-action btn-confirm-${type}`}
                        onClick={onConfirm}
                    >
                        {confirmText}
                    </button>
                </div>
            </div>
        </div>
    );
};

export default ConfirmDialog;
