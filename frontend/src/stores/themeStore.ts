"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { api } from "@/lib/nexus/client";
import { useAuthStore } from "@/stores/authStore";

type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
  applyToDocument: () => void;
  /** Apply a theme fetched from the server without re-PATCHing it back. */
  hydrateFromServer: (t: Theme) => void;
}

/** Best-effort: persist the theme choice server-side too (Profile page's
 *  Appearance tab), so it follows the user across devices instead of only
 *  living in this browser's localStorage. Never blocks the local toggle. */
function persistThemeRemote(theme: Theme) {
  if (!useAuthStore.getState().token) return;
  api.auth.updatePreferences({ theme }).catch(() => {});
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      setTheme: (t) => {
        set({ theme: t });
        get().applyToDocument();
        persistThemeRemote(t);
      },
      toggle: () => {
        const next = get().theme === "dark" ? "light" : "dark";
        set({ theme: next });
        get().applyToDocument();
        persistThemeRemote(next);
      },
      hydrateFromServer: (t) => {
        set({ theme: t });
        get().applyToDocument();
      },
      applyToDocument: () => {
        const t = get().theme;
        if (typeof document !== "undefined") {
          const root = document.documentElement;
          if (t === "dark") root.classList.add("dark");
          else root.classList.remove("dark");
          root.style.colorScheme = t;
        }
      },
    }),
    {
      name: "nexus-theme",
      partialize: (s) => ({ theme: s.theme }),
      onRehydrateStorage: () => (state) => {
        // Apply theme after rehydration
        if (state && typeof document !== "undefined") {
          const root = document.documentElement;
          if (state.theme === "dark") root.classList.add("dark");
          else root.classList.remove("dark");
          root.style.colorScheme = state.theme;
        }
      },
    }
  )
);
