import { create } from 'zustand';

interface User {
    id: number;
    staff_id: string;
    email: string;
    role: string;
    token: string;
}

interface AuthState {
    user: User | null;
    login: (userData: User) => void;
    logout: () => void;
    setUser: (userData: User | null) => void;
}

export const useAuthStore = create<AuthState>((set) => ({
    user: (() => {
        try {
            const stored = localStorage.getItem('hrUser');
            return stored && stored !== 'undefined' ? JSON.parse(stored) : null;
        } catch (e) {
            return null;
        }
    })(),

    login: (userData) => {
        localStorage.setItem('hrUser', JSON.stringify(userData));
        set({ user: userData });
    },

    logout: () => {
        localStorage.removeItem('hrUser');
        set({ user: null });
        window.location.href = '/';
    },

    setUser: (userData) => {
        if (userData) {
            localStorage.setItem('hrUser', JSON.stringify(userData));
        } else {
            localStorage.removeItem('hrUser');
        }
        set({ user: userData });
    }
}));
