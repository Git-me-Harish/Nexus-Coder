"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";

type Theme = "light" | "dark";

interface ThemeState {
  theme: Theme;
  setTheme: (t: Theme) => void;
  toggle: () => void;
  applyToDocument: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      theme: "dark",
      setTheme: (t) => {
        set({ theme: t });
        get().applyToDocument();
      },
      toggle: () => {
        const next = get().theme === "dark" ? "light" : "dark";
        set({ theme: next });
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
