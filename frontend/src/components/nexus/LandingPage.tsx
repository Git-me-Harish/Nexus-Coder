"use client";

import {
  Sparkles, ArrowRight, ArrowUpRight, Layers, Brain, GraduationCap,
  ShieldCheck, Cpu, GitBranch, Workflow, FileCheck2, Activity, Users,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { navigate } from "@/hooks/use-hash-router";
import PartnersMarquee from "./PartnersMarquee";
import ThemeToggle from "./ThemeToggle";
import { OutlineText } from "./OutlineText";

const CAPABILITIES = [
  { icon: <Users className="w-4 h-4" />, title: "Identity", desc: "JWT + GitHub OAuth, refresh-token rotation with family detection, RBAC per tenant." },
  { icon: <Layers className="w-4 h-4" />, title: "Mode & Phase", desc: "Mode-aware state machine: gated 6-phase dev, phase-less debate, 3-stage learning loop." },
  { icon: <FileCheck2 className="w-4 h-4" />, title: "Spec Builder", desc: "12 architectural dimensions, 3 curated options each + custom. JSONB versioned specs." },
  { icon: <Workflow className="w-4 h-4" />, title: "Agent Orchestrator", desc: "LangGraph plan -> ReAct-execute -> critique loop, real tool calls, sandboxed execution." },
  { icon: <Cpu className="w-4 h-4" />, title: "Model Gateway", desc: "Provider routing, prompt cache, token tracking, circuit breaker, fallback chain." },
  { icon: <Activity className="w-4 h-4" />, title: "Observability", desc: "OpenTelemetry traces, Langfuse agent metrics, Sentry errors, structured JSON logs." },
];

const TICKER_ITEMS = ["Ideation", "Planning", "Specification", "Implementation", "Debug", "Review"];

export default function LandingPage() {
  const { isAuthenticated } = useAuthStore();

  function goToLogin() {
    navigate("auth");
  }

  function goToDashboard() {
    navigate("dashboard");
  }

  const primaryAction = isAuthenticated ? goToDashboard : goToLogin;

  return (
    <div className="ed-page min-h-screen relative overflow-x-hidden">
      {/* Top nav */}
      <header className="sticky top-0 z-40 border-b ed-hairline bg-[var(--ed-bg)]/90 backdrop-blur-md">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src="/logo.png" alt="" aria-hidden="true" className="w-7 h-7 object-contain shrink-0" />
            <OutlineText className="!text-lg md:!text-lg tracking-wide">NEXUS</OutlineText>
          </div>

          <nav className="hidden md:flex items-center gap-8 ed-label">
            <a href="#modes" className="hover:text-[var(--ed-fg)] transition">00 Modes</a>
            <a href="#capabilities" className="hover:text-[var(--ed-fg)] transition">01 Capabilities</a>
            <a href="#providers" className="hover:text-[var(--ed-fg)] transition">02 Providers</a>
          </nav>

          <div className="flex items-center gap-3">
            <ThemeToggle compact />
            {!isAuthenticated && (
              <button
                onClick={goToLogin}
                className="hidden sm:inline text-xs font-medium text-[var(--ed-muted)] hover:text-[var(--ed-fg)] transition"
              >
                Sign in
              </button>
            )}
            <button
              onClick={primaryAction}
              className="inline-flex items-center gap-1.5 px-4 py-2 rounded-full bg-[var(--ed-fg)] text-[var(--ed-bg)] text-xs font-semibold uppercase tracking-wider hover:opacity-85 transition"
            >
              {isAuthenticated ? "Dashboard" : "Get started"}
              <ArrowUpRight className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Meta strip */}
        <div className="border-t ed-hairline">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-8 flex items-center justify-between ed-label !text-[9px]">
            <span>Agentic Engineering Platform</span>
            <span className="hidden sm:inline">Nexus — v1.0 · Folio/01</span>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="relative border-b ed-hairline">
        <div className="ed-grid-lines opacity-60">
          {Array.from({ length: 6 }).map((_, i) => <div key={i} />)}
        </div>

        <div className="relative max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24 lg:py-32">
          <div className="flex items-center gap-4 sm:gap-6 mb-6">
            <img src="/logo.png" alt="" aria-hidden="true" className="w-10 h-10 sm:w-14 sm:h-14 object-contain shrink-0" />
            <h1 className="text-5xl sm:text-7xl lg:text-8xl font-bold tracking-tight text-[var(--ed-fg)]">
              Nexus.
            </h1>
          </div>
          <p className="max-w-xl text-base sm:text-lg italic text-[var(--ed-muted)] leading-relaxed ml-[3.25rem] sm:ml-[4.75rem]">
            Reasons before it writes a line of code — and keeps working long after the plan is confirmed.
          </p>
        </div>

        {/* 4-column meta row */}
        <div className="border-t ed-hairline">
          <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-2 md:grid-cols-4 gap-6 py-6">
            {[
              { n: "01", label: "Modes", value: "Development · Problem Solving · Learning" },
              { n: "02", label: "Engine", value: "LangGraph plan → act → critique" },
              { n: "03", label: "Access", value: "Open · bring your own key" },
              { n: "04", label: "Providers", value: "7 LLM providers, auto-routed" },
            ].map((m) => (
              <div key={m.n}>
                <div className="ed-label mb-1.5">[{m.n}] {m.label}</div>
                <div className="text-xs sm:text-sm font-medium text-[var(--ed-fg)] leading-snug">{m.value}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Ticker */}
      <div className="bg-[var(--ed-fg)] py-3 overflow-hidden">
        <div className="ed-ticker-track">
          {[...TICKER_ITEMS, ...TICKER_ITEMS, ...TICKER_ITEMS, ...TICKER_ITEMS].map((t, i) => (
            <span key={i} className="flex items-center shrink-0 px-4 text-xs font-semibold uppercase tracking-wider text-[var(--ed-bg)]">
              {t} <span className="ml-4 opacity-50">•</span>
            </span>
          ))}
        </div>
      </div>

      {/* About + image */}
      <section className="border-b ed-hairline">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 sm:py-20">
          <h2 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-[var(--ed-fg)] mb-10 sm:mb-14 max-w-2xl leading-tight">
            One agent. <span className="italic font-serif font-normal">Built around reasoning,</span> run like a system.
          </h2>

          <div className="grid grid-cols-1 lg:grid-cols-5 gap-8 lg:gap-10">
            <div className="lg:col-span-2">
              <div className="ed-label mb-3">[01/03] About</div>
              <p className="text-sm text-[var(--ed-fg)] leading-relaxed mb-6">
                Nexus plans before it answers and reviews its own drafts before it hands them back —
                a real ReAct loop over a sandboxed workspace, not a single confident-sounding completion.
                Every build runs against an approved spec; every phase gate is a real decision, not a formality.
              </p>
              <div className="grid grid-cols-3 gap-4 pt-4 border-t ed-hairline">
                {[
                  { v: "6", l: "Phases" },
                  { v: "12", l: "Spec dims" },
                  { v: "7", l: "Providers" },
                ].map((s) => (
                  <div key={s.l}>
                    <div className="text-xl sm:text-2xl font-bold text-[var(--ed-fg)]">{s.v}</div>
                    <div className="ed-label mt-0.5">{s.l}</div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-3 relative border ed-hairline overflow-hidden bg-[var(--ed-surface)]">
              <img
                src="/human-robot-interaction.png"
                alt="Human and robot hands reaching toward each other, representing human-AI collaboration"
                className="w-full h-full object-cover aspect-[4/3] lg:aspect-auto"
              />
              <span className="absolute top-3 right-3 px-2 py-1 bg-[var(--ed-bg)]/90 ed-label !text-[9px] border ed-hairline">
                [ Nexus ]
              </span>
            </div>
          </div>
        </div>
      </section>

      {/* Modes */}
      <section id="modes" className="border-b ed-hairline">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 sm:py-20">
          <div className="flex items-end justify-between mb-8 sm:mb-10 gap-4">
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-[var(--ed-fg)]">
              Three modes. <span className="italic font-serif font-normal">Three workflows.</span>
            </h2>
            <p className="hidden sm:block ed-label max-w-xs text-right">Not skins on one engine — each mode runs a genuinely different state graph.</p>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 border-t border-l ed-hairline">
            <EdModeCard
              n="01"
              icon={<Layers className="w-4 h-4" />}
              title="Build something"
              tagline="Phase-gated build pipeline"
              desc="Ideation → Planning → Specification → Implementation → Debug → Review. Nothing ships without an approved spec."
            />
            <EdModeCard
              n="02"
              icon={<Brain className="w-4 h-4" />}
              title="Think something through"
              tagline="Free-form debate"
              desc="No phases, no gates. The agent argues multiple sides and produces a decision document."
            />
            <EdModeCard
              n="03"
              icon={<GraduationCap className="w-4 h-4" />}
              title="Learn something"
              tagline="Adaptive mastery loop"
              desc="Explain → Practice → Quiz. Difficulty adapts to your mastery score across 30+ topics."
            />
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section id="capabilities" className="border-b ed-hairline">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 sm:py-20">
          <div className="flex items-end justify-between mb-8 sm:mb-10 gap-4">
            <h2 className="text-xl sm:text-2xl lg:text-3xl font-bold text-[var(--ed-fg)]">
              Selected <span className="italic font-serif font-normal">capabilities.</span>
            </h2>
            <p className="hidden sm:block ed-label max-w-xs text-right">Every domain, from agent topology to token budget.</p>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 border-t border-l ed-hairline">
            {CAPABILITIES.map((c, i) => (
              <div key={c.title} className="border-r border-b ed-hairline p-4 sm:p-5">
                <div className="flex items-center justify-between mb-4">
                  <div className="text-[var(--ed-accent)]">{c.icon}</div>
                  <span className="ed-label">{String(i + 1).padStart(2, "0")}</span>
                </div>
                <div className="text-sm font-semibold text-[var(--ed-fg)] mb-1.5">{c.title}</div>
                <div className="text-[11px] text-[var(--ed-muted)] leading-relaxed">{c.desc}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Providers */}
      <section id="providers" className="border-b ed-hairline">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-14 sm:py-20">
          <PartnersMarquee />
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-[var(--ed-fg)]">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-16 sm:py-24 text-center">
          <div className="ed-label !text-[var(--ed-bg)]/60 mb-4">Ready when you are</div>
          <h2 className="text-2xl sm:text-3xl lg:text-5xl font-bold text-[var(--ed-bg)] mb-6 leading-tight">
            Stop prompting. <span className="italic font-serif font-normal">Start engineering.</span>
          </h2>
          <p className="text-sm sm:text-base text-[var(--ed-bg)]/70 mb-8 max-w-lg mx-auto">
            Pick a mode, lock your spec, watch your application assemble itself.
          </p>
          <button
            onClick={primaryAction}
            className="inline-flex items-center gap-2 px-6 py-3 rounded-full bg-[var(--ed-bg)] text-[var(--ed-fg)] text-sm font-semibold hover:opacity-90 transition"
          >
            <Sparkles className="w-4 h-4" />
            {isAuthenticated ? "Go to dashboard" : "Get started free"}
            <ArrowRight className="w-4 h-4" />
          </button>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-6 sm:py-8">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-2 text-xs text-[var(--ed-muted)]">
            <img src="/logo.png" alt="" aria-hidden="true" className="w-4 h-4 object-contain shrink-0" />
            <span className="font-semibold text-[var(--ed-fg)]">Nexus</span>
            <span className="opacity-60">—</span>
            <span>AI Coding Assistant Platform</span>
          </div>
          <div className="flex items-center gap-4 ed-label">
            <span className="flex items-center gap-1.5"><ShieldCheck className="w-3 h-3" /> Spec-confirmed builds</span>
            <span className="flex items-center gap-1.5"><GitBranch className="w-3 h-3" /> Real file output</span>
          </div>
        </div>
      </footer>
    </div>
  );
}

function EdModeCard({
  n, icon, title, tagline, desc,
}: {
  n: string;
  icon: React.ReactNode;
  title: string;
  tagline: string;
  desc: string;
}) {
  return (
    <div className="border-r border-b ed-hairline p-5 sm:p-6 group hover:bg-[var(--ed-surface)] transition-colors">
      <div className="flex items-center justify-between mb-6">
        <div className="w-9 h-9 rounded-full border ed-hairline flex items-center justify-center text-[var(--ed-accent)] group-hover:scale-110 transition-transform">
          {icon}
        </div>
        <span className="ed-label">{n}</span>
      </div>
      <h3 className="text-base font-semibold text-[var(--ed-fg)] mb-1">{title}</h3>
      <p className="text-xs text-[var(--ed-accent)] mb-3">{tagline}</p>
      <p className="text-xs text-[var(--ed-muted)] leading-relaxed">{desc}</p>
    </div>
  );
}
