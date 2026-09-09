"use client";

import { create } from "zustand";

/**
 * Step-up ("sudo") elevation for the API-keys screen.
 *
 * Deliberately NOT persisted — no `persist` middleware here, unlike
 * authStore. The whole point of re-confirming a password is that the
 * elevation is short-lived and tied to the moment: writing it to
 * localStorage would let it survive reloads and quietly become permanent,
 * which is exactly the property step-up auth exists to avoid.
 *
 * The server is the real gate (app/api/deps.require_sudo); this only tracks
 * what the UI should show and which header to attach.
 */
interface SudoState {
  token: string | null;
  /** Epoch ms. The server's expiry is authoritative — this is for the UI. */
  expiresAt: number | null;
  unlock: (token: string, expiresInMinutes: number) => void;
  lock: () => void;
  /** Valid right now? Also used to decide whether to send the header. */
  isUnlocked: () => boolean;
}

export const useSudoStore = create<SudoState>((set, get) => ({
  token: null,
  expiresAt: null,

  unlock: (token, expiresInMinutes) =>
    set({ token, expiresAt: Date.now() + expiresInMinutes * 60_000 }),

  lock: () => set({ token: null, expiresAt: null }),

  isUnlocked: () => {
    const { token, expiresAt } = get();
    return !!token && !!expiresAt && Date.now() < expiresAt;
  },
}));

/** The header to attach to credential requests, or nothing when locked. */
export function sudoHeader(): Record<string, string> {
  const { token, isUnlocked } = useSudoStore.getState();
  return isUnlocked() && token ? { "X-Sudo-Token": token } : {};
}
