"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { API_BASE_URL } from "@/lib/nexus/client";

interface User {
  id: string;
  email: string;
  name?: string | null;
  avatarUrl?: string | null;
  githubUsername?: string | null;
  bio?: string | null;
  company?: string | null;
  location?: string | null;
  createdAt?: string | null;
  /** False for accounts created through "Continue with GitHub" — the Security
   *  tab offers "set a password" instead of asking for a current one. */
  hasPassword?: boolean;
}

interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  tokenBudget?: number;
}

interface Preferences {
  defaultMode: string;
  defaultModelId?: string | null;
  theme: string;
}

interface AuthState {
  user: User | null;
  tenant: Tenant | null;
  preferences: Preferences | null;
  token: string | null;
  refreshToken: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;

  setSession: (s: { user: User; tenant: Tenant | null; token: string; refreshToken: string; preferences?: Preferences | null }) => void;
  clear: () => void;
  fetchMe: () => Promise<void>;
  updateUser: (patch: Partial<User>) => void;
  updatePreferences: (patch: Partial<Preferences>) => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      tenant: null,
      preferences: null,
      token: null,
      refreshToken: null,
      isLoading: true,
      isAuthenticated: false,

      setSession: ({ user, tenant, token, refreshToken, preferences }) =>
        set({ user, tenant, token, refreshToken, preferences: preferences ?? null, isAuthenticated: true, isLoading: false }),

      clear: () =>
        set({ user: null, tenant: null, preferences: null, token: null, refreshToken: null, isAuthenticated: false, isLoading: false }),

      updateUser: (patch) =>
        set((s) => (s.user ? { user: { ...s.user, ...patch } } : {})),

      updatePreferences: (patch) =>
        set((s) => (s.preferences ? { preferences: { ...s.preferences, ...patch } } : { preferences: patch as Preferences })),

      // NOTE: intentionally uses raw fetch (not the api.* client) to avoid
      // a circular import with client.ts, which itself reads from this store.
      fetchMe: async () => {
        const token = get().token;
        if (!token) {
          set({ isLoading: false });
          return;
        }
        try {
          const res = await fetch(`${API_BASE_URL}/api/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
          });
          if (!res.ok) {
            get().clear();
            return;
          }
          const data = await res.json();
          set({
            user: data.user,
            tenant: data.tenant,
            preferences: data.preferences,
            isAuthenticated: true,
            isLoading: false,
          });
        } catch {
          get().clear();
        }
      },
    }),
    {
      name: "nexus-auth",
      partialize: (s) => ({ token: s.token, refreshToken: s.refreshToken, user: s.user, tenant: s.tenant, preferences: s.preferences, isAuthenticated: s.isAuthenticated }),
    }
  )
);
