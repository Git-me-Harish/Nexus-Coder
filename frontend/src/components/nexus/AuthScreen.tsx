"use client";

import { useState } from "react";
import {
  Sparkles, ArrowRight, Loader2, Zap, ShieldCheck, GitBranch, Check, Cpu, Workflow,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";
import { navigate } from "@/hooks/use-hash-router";
import { api } from "@/lib/nexus/client";
import Wordmark from "./Wordmark";
import ThemeToggle from "./ThemeToggle";
import { toast } from "sonner";
import { AnimatedCodeBlock } from "@/components/ui/animated-code-block";

const FETCH_DATA_EXAMPLE = `import { useState, useEffect } from 'react';

function useDataFetching(url) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch(url)
      .then(res => res.json())
      .then(setData)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [url]);

  return { data, loading };
}`;

export default function AuthScreen() {
  const { setSession } = useAuthStore();
  const { setProjects } = useAppStore();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("demo@nexus.dev");
  const [password, setPassword] = useState("nexus");
  const [name, setName] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    try {
      const result = mode === "login"
        ? await api.auth.login(email, password)
        : await api.auth.register(email, password, name);
      setSession({
        user: result.user,
        tenant: result.tenant,
        token: result.token,
        refreshToken: result.refreshToken,
      });
      toast.success(`Welcome${mode === "login" ? " back" : ""}, ${result.user.name ?? result.user.email}!`);
      try {
        const { projects } = await api.projects.list();
        setProjects(projects);
      } catch {}
      // Use replace so the browser back button doesn't take the user back to login
      navigate("dashboard", { replace: true });
    } catch (err: any) {
      toast.error(err?.message ?? "Authentication failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex relative">
      {/* Top bar -- wordmark (clickable to go back to landing) + theme toggle */}
      <button
        onClick={() => navigate("landing")}
        className="absolute top-4 left-4 z-20 transition hover:opacity-80 sm:top-6 sm:left-8 lg:hidden"
      >
        <Wordmark size="md" />
      </button>
      <div className="absolute top-4 sm:top-6 right-4 sm:right-8 z-20">
        <ThemeToggle compact />
      </div>

      {/* ─── Left: Auth form ──────────────────────────────────────────────── */}
      <div className="flex-1 lg:w-[44%] flex items-center justify-center p-4 sm:p-6 lg:p-8 order-2 lg:order-1">
        <div className="w-full max-w-md mt-12 lg:mt-0">
          {/* Mobile hero — hidden on lg+ where the right panel takes over */}
          <div className="text-center mb-6 lg:hidden">
            <div className="inline-flex w-14 h-14 rounded-2xl bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple)] items-center justify-center mb-3 shadow-[0_0_30px_color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]">
              <Sparkles className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-2xl font-bold text-[var(--foreground)] tracking-tight mb-1">
              Your Principal Engineer
            </h1>
            <p className="text-xs text-[var(--muted-foreground)]">
              Brainstorms, debates, plans, specifies — before code.
            </p>
          </div>

          {/* Desktop heading */}
          <div className="hidden lg:block mb-8">
            <button
              onClick={() => navigate("landing")}
              className="mb-5 block transition hover:opacity-80"
              aria-label="Go to Nexus home"
            >
              <Wordmark size="md" />
            </button>
            <h2 className="text-3xl font-bold text-[var(--foreground)] tracking-tight mb-2">
              {mode === "login" ? "Welcome back" : "Create your account"}
            </h2>
            <p className="text-sm text-[var(--muted-foreground)]">
              {mode === "login"
                ? "Sign in to continue building with Nexus."
                : "Start shipping with a Principal Engineer in your browser."}
            </p>
          </div>

          {/* Auth card */}
          <div className="nexus-glass rounded-2xl p-5 sm:p-6">
            {/* Tab toggle */}
            <div className="flex gap-1 p-1 mb-5 rounded-lg bg-[var(--nexus-bg)]/60 border border-[var(--nexus-border)]">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => setMode(m)}
                  className={`flex-1 py-1.5 rounded-md text-xs font-medium transition ${
                    mode === m ? "bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] text-[var(--foreground)] border border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)]" : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
                  }`}
                >
                  {m === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-3">
              {mode === "register" && (
                <div>
                  <label className="block text-[11px] font-medium text-[var(--muted-foreground)] mb-1">Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 rounded-lg bg-[var(--nexus-bg)] border border-[var(--nexus-border)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]"
                    placeholder="Ada Lovelace"
                  />
                </div>
              )}
              <div>
                <label className="block text-[11px] font-medium text-[var(--muted-foreground)] mb-1">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-[var(--nexus-bg)] border border-[var(--nexus-border)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <label className="block text-[11px] font-medium text-[var(--muted-foreground)] mb-1">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  className="w-full px-3 py-2 rounded-lg bg-[var(--nexus-bg)] border border-[var(--nexus-border)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]"
                  placeholder="••••••••"
                />
              </div>
              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white text-sm font-medium hover:opacity-90 transition flex items-center justify-center gap-2 nexus-btn-glow disabled:opacity-50"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    {mode === "login" ? "Sign in" : "Create account"}
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </button>
            </form>

            <div className="my-4 flex items-center gap-2">
              <div className="flex-1 h-px bg-[var(--nexus-border)]" />
              <span className="text-[10px] text-[var(--muted-foreground)]">or</span>
              <div className="flex-1 h-px bg-[var(--nexus-border)]" />
            </div>

            <button
              onClick={() => toast.info("GitHub OAuth — wire up in production.")}
              className="w-full py-2.5 rounded-lg border border-[var(--nexus-border)] text-sm font-medium text-[var(--foreground)] hover:bg-[var(--nexus-surface-2)] transition flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
              Continue with GitHub
            </button>
          </div>
        </div>
      </div>

      {/* ─── Right: Marketing showcase ────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[56%] relative items-center justify-center p-8 overflow-hidden border-l border-[var(--nexus-border)] order-1 lg:order-2">
        {/* Animated gradient background */}
        <div className="absolute inset-0 nexus-animated-gradient" />
        <div className="absolute inset-0 bg-[var(--nexus-bg)]/40" />

        {/* Floating decorative blobs */}
        <div className="absolute top-20 right-20 w-64 h-64 rounded-full bg-[var(--nexus-purple)]/20 blur-3xl nexus-float" />
        <div className="absolute bottom-20 left-20 w-72 h-72 rounded-full bg-[var(--nexus-teal)]/15 blur-3xl nexus-float-delayed" />

        {/* Content */}
        <div className="relative z-10 max-w-lg w-full">
          {/* Headline */}
          <div className="mb-8">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_35%,transparent)] text-[var(--mode-dev-text)] text-[11px] font-medium mb-4">
              <Sparkles className="w-3 h-3" />
              AI Coding Assistant Platform
            </div>
            <h1 className="text-4xl xl:text-5xl font-bold text-[var(--foreground)] tracking-tight mb-4 leading-tight">
              Think like a Principal Engineer.
              <br />
              <span className="bg-gradient-to-r from-[var(--nexus-violet)] to-[var(--nexus-purple)] bg-clip-text text-transparent">
                Ship like a team.
              </span>
            </h1>
            <p className="text-base text-[var(--muted-foreground)] leading-relaxed">
              Nexus brainstorms, debates, plans, and specifies before a single line of code is written.
              Three modes. Six phases. Twelve architectural dimensions. One intelligent agent.
            </p>
          </div>

          {/* Feature highlights */}
          <div className="space-y-2.5 mb-6">
            <FeatureLine icon={<Cpu className="w-4 h-4" />} text="7 models · intelligent phase-aware routing · mid-task switching" />
            <FeatureLine icon={<Workflow className="w-4 h-4" />} text="Orchestrator-Worker agents · Brainstormer → Coder → Reviewer" />
            <FeatureLine icon={<ShieldCheck className="w-4 h-4" />} text="Human-in-the-loop gate · spec must be confirmed before code" />
            <FeatureLine icon={<GitBranch className="w-4 h-4" />} text="Real file tree · live preview · ZIP export · GitHub push" />
          </div>

          {/* Terminal preview replaces the mode and stats cards. */}
          <div className="border-t border-[var(--nexus-border)] pt-6">
            <AnimatedCodeBlock
              code={FETCH_DATA_EXAMPLE}
              theme="dark"
              title="fetch-data.jsx"
              typingSpeed={50}
              showLineNumbers
              autoPlay
              language="typescript"
              highlightLines={[1, 4, 10]}
              loop
            />
          </div>
        </div>
      </div>
    </div>
  );
}

function FeatureLine({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-6 h-6 rounded-md bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] flex items-center justify-center shrink-0 mt-0.5">
        <div className="text-[var(--mode-dev-text)]">{icon}</div>
      </div>
      <span className="text-sm text-[var(--foreground)] leading-relaxed">{text}</span>
    </div>
  );
}