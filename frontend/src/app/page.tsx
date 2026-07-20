"use client";

import { useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";
import { useHashRouter, navigate } from "@/hooks/use-hash-router";
import AuthScreen from "@/components/nexus/AuthScreen";
import LandingPage from "@/components/nexus/LandingPage";
import Dashboard from "@/components/nexus/Dashboard";
import Workspace from "@/components/nexus/Workspace";
import ResponsiveSidebar from "@/components/nexus/ResponsiveSidebar";

export default function Home() {
  const { isAuthenticated, isLoading, token, fetchMe, clear } = useAuthStore();
  const { view, setView } = useAppStore();

  // Activate the hash-based router (syncs browser URL with view state)
  useHashRouter();

  // Bootstrap auth state from stored token
  useEffect(() => {
    if (token && isLoading) {
      fetchMe();
    } else if (!token && isLoading) {
      useAuthStore.setState({ isLoading: false });
    }
  }, [token, isLoading, fetchMe]);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated && (view === "dashboard" || view === "session")) {
      navigate("landing", { replace: true });
    }
  }, [isAuthenticated, isLoading, view]);

  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated && view === "session" && !useAppStore.getState().activeSession) {
      navigate("dashboard", { replace: true });
    }
  }, [isAuthenticated, isLoading, view]);

  // Listen for global logout events (fired by Sidebar sign-out + API 401s)
  useEffect(() => {
    const handleLogout = () => {
      clear();
      navigate("landing", { replace: true });
    };
    window.addEventListener("nexus:logout", handleLogout);
    return () => window.removeEventListener("nexus:logout", handleLogout);
  }, [clear]);

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple)] animate-pulse shadow-[0_0_30px_color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]" />
          <div className="text-xs text-[var(--muted-foreground)]">Booting Nexus...</div>
        </div>
      </div>
    );
  }

  if (view === "auth") {
    return <AuthScreen />;
  }

  if (view === "landing" || !isAuthenticated) {
    return <LandingPage />;
  }

  if (view === "session") {
    return <Workspace />;
  }

  // Default: dashboard
  return (
    <div className="flex min-h-screen">
      <ResponsiveSidebar />
      <div className="flex-1 min-w-0">
        <Dashboard />
      </div>
    </div>
  );
}