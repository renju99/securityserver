import React from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

/**
 * Viewport-safe modal: dialog is positioned with inline styles so it never crops
 * (avoids cached CSS or parent transform/scroll issues).
 */
const OVERLAY_STYLE = {
    position: 'fixed',
    inset: 0,
    zIndex: 9999,
    background: 'rgba(0, 0, 0, 0.7)',
    boxSizing: 'border-box',
};

const DIALOG_STYLE = {
    position: 'fixed',
    top: '1.5rem',
    bottom: '1.5rem',
    left: '50%',
    transform: 'translateX(-50%)',
    width: 'calc(100% - 2rem)',
    maxWidth: 480,
    overflowY: 'auto',
    boxSizing: 'border-box',
    padding: '2rem',
};

const Modal = ({ show, onClose, children, title, maxWidth = 480, className = '' }) => {
    if (!show) return null;
    const dialogStyle = { ...DIALOG_STYLE, maxWidth: maxWidth };
    return createPortal(
        <div
            className={`modal-overlay ${className}`.trim()}
            style={OVERLAY_STYLE}
            onClick={(e) => e.target === e.currentTarget && onClose?.()}
        >
            <div
                className="card glass modal-dialog"
                style={dialogStyle}
                onClick={(e) => e.stopPropagation()}
            >
                <button
                    type="button"
                    onClick={onClose}
                    style={{
                        position: 'absolute',
                        top: '1rem',
                        right: '1rem',
                        background: 'none',
                        border: 'none',
                        color: 'var(--text-muted)',
                        cursor: 'pointer',
                    }}
                    aria-label="Close"
                >
                    <X size={20} />
                </button>
                {title && <h2 style={{ marginBottom: '1.5rem' }}>{title}</h2>}
                {children}
            </div>
        </div>,
        document.body
    );
};

export default Modal;
