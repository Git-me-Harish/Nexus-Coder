"use client";

import {
  Sparkles, ArrowRight, Layers, Brain, GraduationCap,
  ShieldCheck, Cpu, GitBranch, Zap, Workflow, FileCheck2, Activity,
  Users, Star,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { navigate } from "@/hooks/use-hash-router";
import Wordmark from "./Wordmark";
import ThemeToggle from "./ThemeToggle";
import PartnersMarquee from "./PartnersMarquee";
import { cn } from "@/lib/utils";

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();

  function goToLogin() {
    navigate("auth");
  }

  function goToDashboard() {
    navigate("dashboard");
  }

  return (
    <div className="min-h-screen relative overflow-x-hidden">
      {/* Top nav */}
      <header className="sticky top-0 z-40 backdrop-blur-xl bg-[var(--nexus-bg)]/70 border-b border-[var(--nexus-border)]/60">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-14 flex items-center justify-between">
          <Wordmark size="sm" />
          <div className="flex items-center gap-2">
            <ThemeToggle compact />
            <button
              onClick={isAuthenticated ? goToDashboard : goToLogin}
              className="px-3 sm:px-4 py-1.5 rounded-lg text-xs font-medium border border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--nexus-surface-2)] transition"
            >
              {isAuthenticated ? "Dashboard" : "Sign in"}
            </button>
            {!isAuthenticated && (
              <button
                onClick={goToLogin}
                className="px-3 sm:px-4 py-1.5 rounded-lg text-xs font-medium bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white hover:opacity-90 transition flex items-center gap-1.5 nexus-btn-glow"
              >
                <Sparkles className="w-3.5 h-3.5" />
                Get started
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative pt-12 sm:pt-20 lg:pt-24 pb-12 sm:pb-16 overflow-hidden">
        {/* Mesh blobs */}
        <div className="nexus-mesh-blob w-[500px] h-[500px] top-[-200px] left-[-100px] bg-[var(--nexus-purple)]" />
        <div className="nexus-mesh-blob w-[400px] h-[400px] top-[-100px] right-[-100px] bg-[var(--nexus-violet)]" style={{ animationDelay: "6s" }} />
        <div className="nexus-mesh-blob w-[300px] h-[300px] bottom-[-100px] left-[40%] bg-[var(--nexus-teal)]" style={{ animationDelay: "3s" }} />

        {/* Floating particles */}
        {Array.from({ length: 12 }).map((_, i) => (
          <div
            key={i}
            className="nexus-particle"
            style={{
              left: `${(i * 8.3) % 100}%`,
              bottom: "0",
              animationDelay: `${i * 1.2}s`,
              animationDuration: `${10 + (i % 4) * 2}s`,
              background: i % 3 === 0 ? "var(--nexus-teal)" : i % 3 === 1 ? "var(--nexus-violet)" : "var(--nexus-purple)",
            }}
          />
        ))}

        <div className="relative max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center">
            {/* Badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] text-[var(--mode-dev-text)] text-[11px] font-medium mb-5">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--nexus-success)] nexus-pulse" />
              AI Coding Assistant Platform
            </div>

            {/* Headline */}
            <h1 className="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-bold tracking-tight mb-4 sm:mb-6 leading-[1.1]">
              <span className="text-[var(--foreground)]">Your Principal</span>
              <br />
              <span className="text-[var(--foreground)]">Engineer</span>{" "}
              <span className="nexus-text-gradient">in the browser.</span>
            </h1>

            <p className="text-sm sm:text-base lg:text-lg text-[var(--muted-foreground)] mb-6 sm:mb-8 max-w-xl mx-auto leading-relaxed">
              Nexus brainstorms, debates, plans, and specifies before a single line of code is written.
              Three modes. Six phases. Twelve architectural dimensions. One intelligent agent.
            </p>

            {/* CTAs */}
            <div className="flex flex-col sm:flex-row gap-2.5 sm:gap-3 justify-center mb-8">
              <button
                onClick={isAuthenticated ? goToDashboard : goToLogin}
                className="px-5 py-3 rounded-xl bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white text-sm font-medium hover:opacity-90 transition flex items-center justify-center gap-2 nexus-btn-glow"
              >
                <Sparkles className="w-4 h-4" />
                {isAuthenticated ? "Go to dashboard" : "Start building free"}
                <ArrowRight className="w-4 h-4" />
              </button>
              <button
                onClick={goToLogin}
                className="px-5 py-3 rounded-xl border border-[var(--nexus-border)] text-[var(--foreground)] text-sm font-medium hover:bg-[var(--nexus-surface-2)] transition flex items-center justify-center gap-2"
              >
                <Layers className="w-4 h-4" />
                Sign in
              </button>
            </div>

            {/* Trust indicators */}
            <div className="flex items-center gap-4 sm:gap-6 justify-center text-[10px] sm:text-[11px] text-[var(--muted-foreground)]">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-3.5 h-3.5 text-[var(--nexus-success)]" />
                <span>Spec-confirmed builds</span>
              </div>
              <div className="flex items-center gap-1.5">
                <Cpu className="w-3.5 h-3.5 text-[var(--mode-dev-text)]" />
                <span>7 LLM providers</span>
              </div>
              <div className="flex items-center gap-1.5">
                <GitBranch className="w-3.5 h-3.5 text-[var(--mode-learning-text)]" />
                <span>Real file output</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Mode cards */}
      <section className="nexus-section">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-8 sm:mb-10">
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-[var(--foreground)] mb-2">
              Three modes. <span className="nexus-text-gradient">Three workflows.</span>
            </h2>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)] max-w-xl mx-auto">
              Not skins on one engine -- each mode has a genuinely different state graph.
            </p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4">
            <ModeShowcaseCard
              icon={<Layers className="w-5 h-5" />}
              title="Build something"
              tagline="Phase-gated build pipeline"
              desc="Ideation -> Planning -> Specification -> Implementation -> Debug -> Review. Nothing ships without an approved spec."
              features={["6-phase engine", "12-dimension spec", "Live file preview", "GitHub push"]}
              accent="dev"
            />
            <ModeShowcaseCard
              icon={<Brain className="w-5 h-5" />}
              title="Think something through"
              tagline="Free-form debate"
              desc="No phases, no gates. The agent argues multiple sides, proposes competing approaches, produces a decision document."
              features={["Phase-less debate", "Multi-approach", "Decision-doc export", "Adaptive depth"]}
              accent="problem"
            />
            <ModeShowcaseCard
              icon={<GraduationCap className="w-5 h-5" />}
              title="Learn something"
              tagline="Adaptive mastery loop"
              desc="Explain -> Practice -> Quiz. Difficulty adapts to your mastery score. Tracks a long-term knowledge profile."
              features={["3-stage loop", "Mastery scoring", "Adaptive difficulty", "30+ topics"]}
              accent="learning"
            />
          </div>
        </div>
      </section>

      {/* Feature grid */}
      <section className="nexus-section pt-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-6 sm:mb-8">
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-[var(--foreground)] mb-1">
              A complete <span className="nexus-text-gradient">engineering system</span>
            </h2>
            <p className="text-xs sm:text-sm text-[var(--muted-foreground)]">
              Every domain -- from agent topology to token budget.
            </p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2.5 sm:gap-3">
            {[
              { icon: <Users className="w-4 h-4" />, title: "Identity", desc: "JWT + GitHub OAuth, refresh-token rotation with family detection, RBAC per tenant." },
              { icon: <Layers className="w-4 h-4" />, title: "Mode & Phase", desc: "Mode-aware state machine: gated 6-phase dev, phase-less debate, 3-stage learning loop." },
              { icon: <FileCheck2 className="w-4 h-4" />, title: "Spec Builder", desc: "12 architectural dimensions, 3 curated options each + custom. JSONB versioned specs." },
              { icon: <Workflow className="w-4 h-4" />, title: "Agent Orchestrator", desc: "LangGraph orchestrator-worker, max 20 iterations, 50 tool calls, 120s timeout." },
              { icon: <Cpu className="w-4 h-4" />, title: "Model Gateway", desc: "Provider routing, prompt cache, token tracking, circuit breaker, fallback chain." },
              { icon: <Activity className="w-4 h-4" />, title: "Observability", desc: "OpenTelemetry traces, Langfuse agent metrics, Sentry errors, structured JSON logs." },
            ].map((card) => (
              <div key={card.title} className="group relative p-3 sm:p-4 rounded-xl bg-[var(--nexus-surface)]/50 border border-[var(--nexus-border)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] hover:bg-[var(--nexus-surface-2)]/60 transition-all duration-200 cursor-default overflow-hidden">
                <div className="absolute -top-12 -right-12 w-24 h-24 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] blur-2xl opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
                <div className="relative">
                  <div className="w-8 h-8 sm:w-9 sm:h-9 rounded-lg bg-gradient-to-br from-[color-mix(in_srgb,var(--nexus-violet)_20%,transparent)] to-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] flex items-center justify-center mb-2.5 text-[var(--mode-dev-text)] group-hover:scale-110 transition-transform duration-200">
                    {card.icon}
                  </div>
                  <div className="text-xs sm:text-sm font-semibold text-[var(--foreground)] mb-1">{card.title}</div>
                  <div className="text-[10px] sm:text-[11px] text-[var(--muted-foreground)] leading-relaxed line-clamp-3">{card.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Partners marquee */}
      <section className="nexus-section pt-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <PartnersMarquee />
        </div>
      </section>

      {/* Final CTA */}
      <section className="nexus-section pt-0">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="relative rounded-2xl sm:rounded-3xl overflow-hidden p-8 sm:p-12 lg:p-16 text-center nexus-glass-strong">
            <div className="absolute inset-0 nexus-animated-gradient opacity-30" />
            <div className="absolute -top-20 -left-20 w-60 h-60 rounded-full bg-[var(--nexus-purple)] blur-3xl opacity-30" />
            <div className="absolute -bottom-20 -right-20 w-60 h-60 rounded-full bg-[var(--nexus-teal)] blur-3xl opacity-20" />

            <div className="relative">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] text-[var(--mode-dev-text)] text-[11px] font-medium mb-4">
                <Sparkles className="w-3 h-3" />
                Ready when you are
              </div>
              <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-[var(--foreground)] mb-3 leading-tight">
                Stop prompting. <span className="nexus-text-gradient">Start engineering.</span>
              </h2>
              <p className="text-sm sm:text-base text-[var(--muted-foreground)] mb-6 max-w-lg mx-auto">
                Nexus thinks before it builds. Pick a mode, lock your spec, watch your application assemble itself.
              </p>
              <div className="flex flex-col sm:flex-row gap-2.5 justify-center">
                <button
                  onClick={isAuthenticated ? goToDashboard : goToLogin}
                  className="px-6 py-3 rounded-xl bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white text-sm font-medium hover:opacity-90 transition flex items-center justify-center gap-2 nexus-btn-glow"
                >
                  <Sparkles className="w-4 h-4" />
                  {isAuthenticated ? "Go to dashboard" : "Get started free"}
                  <ArrowRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-[var(--nexus-border)] py-6 sm:py-8">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[var(--muted-foreground)]">
            <Wordmark size="sm" />
            <span className="opacity-60">-</span>
            <span>AI Coding Assistant Platform</span>
          </div>
          <div className="flex items-center gap-4 text-[11px] text-[var(--muted-foreground)]">
            <span className="flex items-center gap-1.5">
              <Star className="w-3 h-3" />
              v1.0
            </span>
            <span>Built with Next.js + Prisma + LangGraph</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function ModeShowcaseCard({
  icon, title, tagline, desc, features, accent,
}: {
  icon: React.ReactNode;
  title: string;
  tagline: string;
  desc: string;
  features: string[];
  accent: "dev" | "problem" | "learning";
}) {
  const badgeCls =
    accent === "dev" ? "mode-chip-dev" :
    accent === "problem" ? "mode-chip-problem" :
    "mode-chip-learning";

  return (
    <div className="nexus-bento p-4 sm:p-5 flex flex-col group">
      <div className="flex items-start justify-between mb-3">
        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[color-mix(in_srgb,var(--nexus-violet)_20%,transparent)] to-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] flex items-center justify-center text-[var(--mode-dev-text)] group-hover:scale-110 transition-transform">
          {icon}
        </div>
        <span className={cn("inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium", badgeCls)}>
          {accent === "dev" ? "Development" : accent === "problem" ? "Problem Solving" : "Learning"}
        </span>
      </div>
      <h3 className="text-base sm:text-lg font-semibold text-[var(--foreground)] mb-1">{title}</h3>
      <p className="text-xs text-[var(--mode-dev-text)] mb-3">{tagline}</p>
      <p className="text-xs text-[var(--muted-foreground)] leading-relaxed mb-4 flex-1">{desc}</p>
      <div className="flex flex-wrap gap-1 mb-4">
        {features.map((f) => (
          <span key={f} className="px-1.5 py-0.5 rounded text-[9px] font-medium border border-[var(--nexus-border)] text-[var(--muted-foreground)] bg-[var(--nexus-surface)]/50">
            {f}
          </span>
        ))}
      </div>
    </div>
  );
}
