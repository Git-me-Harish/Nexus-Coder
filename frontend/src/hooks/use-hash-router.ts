"use client";

import { useEffect, useRef } from "react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";

/**
 * Hash-based router for the Nexus single-page app.
 *
 * Routes:
 *   #/            -> landing (public)
 *   #/login       -> auth screen (public)
 *   #/dashboard   -> dashboard (protected — requires auth)
 *   #/session     -> workspace with active session (protected)
 *
 * This hook syncs the browser URL (hash) with the Zustand `view` state.
 * It pushes to history when the view changes (so back/forward works)
 * and listens to `popstate` to update the view when the user navigates.
 */

type Route = "landing" | "auth" | "dashboard" | "session";

const HASH_TO_VIEW: Record<string, Route> = {
  "": "landing",
  "#/": "landing",
  "#/login": "auth",
  "#/dashboard": "dashboard",
  "#/session": "session",
};

const VIEW_TO_HASH: Record<Route, string> = {
  landing: "#/",
  auth: "#/login",
  dashboard: "#/dashboard",
  session: "#/session",
};

function getHash(): string {
  if (typeof window === "undefined") return "#/";
  return window.location.hash || "#/";
}

function hashToView(hash: string): Route {
  return HASH_TO_VIEW[hash] ?? "landing";
}

function viewToHash(view: Route): string {
  return VIEW_TO_HASH[view] ?? "#/";
}

export function useHashRouter() {
  const { view, setView, activeSession } = useAppStore();
  const { isAuthenticated } = useAuthStore();
  const skipPushRef = useRef(false);

  // On mount: read the hash and set the initial view
  useEffect(() => {
    const initialHash = getHash();
    const initialView = hashToView(initialHash);
    skipPushRef.current = true;
    setView(initialView);
  }, [setView]);

  // Listen to popstate (back/forward button)
  useEffect(() => {
    const handlePopState = () => {
      const hash = getHash();
      const newView = hashToView(hash);
      skipPushRef.current = true;
      setView(newView);
    };
    window.addEventListener("popstate", handlePopState);
    return () => window.removeEventListener("popstate", handlePopState);
  }, [setView]);

  // When the view changes (from store), push to history
  // unless this change came from a popstate event (skipPushRef)
  useEffect(() => {
    if (skipPushRef.current) {
      skipPushRef.current = false;
      return;
    }
    const currentView = view as Route;
    if (!currentView) return;

    const targetHash = viewToHash(currentView);
    const currentHash = getHash();

    if (targetHash !== currentHash) {
      window.history.pushState({ view: currentView }, "", targetHash);
    }
  }, [view]);

  // Auth guard: if the user lands on a protected route without auth,
  // redirect to login. If they're on login/landing but already authenticated,
  // redirect to dashboard.
  useEffect(() => {
    if (!isAuthenticated) return;
    // Authenticated user on landing or login -> go to dashboard
    if (view === "landing" || view === "auth") {
      setView("dashboard");
    }
  }, [isAuthenticated, view, setView]);
}

/**
 * Navigate to a view, with the option to replace (not push) history.
 * Use replace for auth transitions (login -> dashboard) so back doesn't
 * take the user back to the login form.
 */
export function navigate(view: Route, options?: { replace?: boolean }) {
  const hash = viewToHash(view);
  if (options?.replace) {
    window.history.replaceState({ view }, "", hash);
  } else {
    window.history.pushState({ view }, "", hash);
  }
  // Dispatch a popstate event so the hook picks it up
  window.dispatchEvent(new PopStateEvent("popstate"));
}
