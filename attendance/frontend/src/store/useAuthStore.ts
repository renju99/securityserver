import { create } from 'zustand';

interface User {
    id?: number;
    staff_id?: string;
    staffId?: string;
    email?: string | null;
    role: string;
    token: string;
    siteId?: number | null;
    siteName?: string | null;
    firstName?: string | null;
    lastName?: string | null;
    organizationId?: number;
    /** Same as organizationId; kept for API payloads that use snake_case. */
    organization_id?: number;
    organizationSlug?: string | null;
    organizationName?: string | null;
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
        void (async () => {
            try {
                let r = await fetch('/auth/logout', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                });
                if (r.status === 404) {
                    await fetch('/api/auth/logout', {
                        method: 'POST',
                        credentials: 'same-origin',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({}),
                    });
                }
            } catch {
                await fetch('/api/auth/logout', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({}),
                }).catch(() => {});
            }
        })();
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
        const tryRefresh = async (url: string) => {
            const res = await fetch(url, {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}),
            });
            return res;
        };
        try {
            let res = await tryRefresh('/auth/refresh');
            if (res.status === 404) {
                res = await tryRefresh('/api/auth/refresh');
            }
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
