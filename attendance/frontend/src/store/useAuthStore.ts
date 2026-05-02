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
    /** Uses httpOnly refresh cookie; returns true if a new access token was stored. */
    refreshAccessToken: () => Promise<boolean>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
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
        void fetch('/api/auth/logout', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({}),
        });
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
    },

    refreshAccessToken: async () => {
        try {
            const res = await fetch('/api/auth/refresh', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            if (!res.ok) return false;
            const data = (await res.json()) as { token?: string };
            if (!data?.token) return false;
            const cur = get().user;
            if (!cur) return false;
            const next = { ...cur, token: data.token };
            localStorage.setItem('hrUser', JSON.stringify(next));
            set({ user: next });
            return true;
        } catch {
            return false;
        }
    },
}));
