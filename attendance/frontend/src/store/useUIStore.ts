import { create } from 'zustand';

interface Toast {
    id: number;
    message: string;
    type: string;
}

interface ConfirmDialog {
    isOpen: boolean;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    type?: 'danger' | 'warning' | 'info';
    onConfirm: (() => void) | null;
}

interface UIState {
    toasts: Toast[];
    confirmDialog: ConfirmDialog;
    showToast: (message: string, type?: string) => void;
    removeToast: (id: number) => void;
    openConfirm: (options: Omit<ConfirmDialog, 'isOpen'>) => void;
    closeConfirm: () => void;
}

export const useUIStore = create<UIState>((set) => ({
    toasts: [],
    confirmDialog: {
        isOpen: false,
        title: '',
        message: '',
        onConfirm: null
    },
    showToast: (message, type = 'info') => {
        const id = Date.now();
        set((state) => ({
            toasts: [...state.toasts, { id, message, type }]
        }));
    },
    removeToast: (id) => {
        set((state) => ({
            toasts: state.toasts.filter(t => t.id !== id)
        }));
    },
    openConfirm: (options) => {
        set({
            confirmDialog: {
                ...options,
                isOpen: true
            }
        });
    },
    closeConfirm: () => {
        set((state) => ({
            confirmDialog: {
                ...state.confirmDialog,
                isOpen: false
            }
        }));
    }
}));
