"use client";

import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";
import { useThemeStore } from "@/stores/themeStore";
import { useHashRouter, navigate } from "@/hooks/use-hash-router";
import { api } from "@/lib/nexus/client";
import AuthScreen from "@/components/nexus/AuthScreen";
import LandingPage from "@/components/nexus/LandingPage";
import Dashboard from "@/components/nexus/Dashboard";
import Workspace from "@/components/nexus/Workspace";
import ResponsiveSidebar from "@/components/nexus/ResponsiveSidebar";
import ProfilePage from "@/components/nexus/ProfilePage";
import Loader from "@/components/nexus/Loader";

export default function Home() {
  const { isAuthenticated, isLoading, token, fetchMe, clear } = useAuthStore();
  const { view, setView } = useAppStore();
  const hydrateThemeFromServer = useThemeStore((s) => s.hydrateFromServer);
  const oauthHandled = useRef(false);
  // Held in memory only: the emailed link's token is taken out of the URL on
  // arrival so it never lingers in the address bar, history, or a screenshot.
  const [resetToken, setResetToken] = useState<string | null>(null);

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

  // Once we know who's signed in, apply their server-stored theme (Profile
  // page's Appearance tab) so it follows them across devices/browsers --
  // localStorage alone only remembers this one browser.
  useEffect(() => {
    if (isLoading || !isAuthenticated) return;
    const serverTheme = useAuthStore.getState().preferences?.theme;
    if (serverTheme === "light" || serverTheme === "dark") {
      hydrateThemeFromServer(serverTheme);
    }
  }, [isAuthenticated, isLoading, hydrateThemeFromServer]);

  useEffect(() => {
    if (isLoading) return;
    if (!isAuthenticated && (view === "dashboard" || view === "session" || view === "profile")) {
      navigate("landing", { replace: true });
    }
  }, [isAuthenticated, isLoading, view]);

  useEffect(() => {
    if (isLoading) return;
    if (isAuthenticated && view === "session" && !useAppStore.getState().activeSession) {
      navigate("dashboard", { replace: true });
    }
  }, [isAuthenticated, isLoading, view]);

  // The GitHub OAuth callback (backend app/api/v1/routes/github.py) redirects
  // the browser back here with a plain query string, since that redirect is
  // a bare browser navigation with no chance to update app state directly.
  // Two different flows land here:
  //   ?github=connected|error      -- account linking, user already signed in
  //   ?auth=github&code=...        -- "Continue with GitHub" sign-in; `code`
  //                                   is a 2-minute, identity-only exchange
  //                                   token, swapped here for a real session
  //                                   so tokens never sit in the URL bar.
  //   ?reset_token=...             -- an emailed password-reset link.
  // Handled once on mount, then stripped from the URL so a refresh doesn't
  // replay it. The ref guard is for StrictMode's double-invoked effects in
  // dev, which would otherwise redeem the same code twice.
  useEffect(() => {
    if (oauthHandled.current) return;
    oauthHandled.current = true;

    const params = new URLSearchParams(window.location.search);
    const github = params.get("github");
    const authFlow = params.get("auth");
    const emailedResetToken = params.get("reset_token");
    if (!github && !authFlow && !emailedResetToken) return;

    function stripQuery() {
      window.history.replaceState(null, "", window.location.pathname + window.location.hash);
    }

    if (emailedResetToken) {
      setResetToken(emailedResetToken);
      stripQuery();
      navigate("reset", { replace: true });
      return;
    }

    if (github === "connected") {
      toast.success("GitHub connected.");
      stripQuery();
    } else if (github === "error") {
      toast.error(params.get("message") || "GitHub connection failed.");
      stripQuery();
    } else if (authFlow === "error") {
      toast.error(params.get("message") || "GitHub sign-in failed.");
      stripQuery();
      navigate("auth", { replace: true });
    } else if (authFlow === "github") {
      const code = params.get("code");
      stripQuery();
      if (!code) {
        toast.error("GitHub sign-in failed.");
        return;
      }
      (async () => {
        try {
          const result = await api.auth.githubExchange(code);
          useAuthStore.getState().setSession({
            user: result.user,
            tenant: result.tenant,
            token: result.token,
            refreshToken: result.refreshToken,
          });
          toast.success(`Welcome, ${result.user.name ?? result.user.email}!`);
          navigate("dashboard", { replace: true });
        } catch (err: any) {
          toast.error(err?.message ?? "GitHub sign-in failed.");
          navigate("auth", { replace: true });
        }
      })();
    }
  }, []);

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
          <Loader />
          <div className="text-xs text-[var(--muted-foreground)]">Booting Nexus...</div>
        </div>
      </div>
    );
  }

  if (view === "auth") {
    return <AuthScreen />;
  }

  // Before the landing fallback below: a reset link is followed while signed
  // out, so `!isAuthenticated` must not bounce it to the marketing page.
  if (view === "reset") {
    return <AuthScreen resetToken={resetToken} />;
  }

  if (view === "landing" || !isAuthenticated) {
    return <LandingPage />;
  }

  if (view === "session") {
    return <Workspace />;
  }

  if (view === "profile") {
    return <ProfilePage />;
  }

  // Default: dashboard
  // h-screen (not min-h-screen), same reasoning as Workspace.tsx: Dashboard's
  // own root is `flex-1 overflow-y-auto`, which only scrolls in place when
  // this ancestor is capped at the viewport instead of free to grow with it.
  return (
    <div className="flex h-screen overflow-hidden">
      <ResponsiveSidebar />
      <div className="flex-1 min-w-0 h-full">
        <Dashboard />
      </div>
    </div>
  );
}