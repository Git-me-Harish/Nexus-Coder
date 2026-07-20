"use client";

import { useEffect, useState } from "react";
import {
  Sparkles, MessageSquare, GraduationCap, ArrowRight,
  Zap, Shield, Layers, GitBranch,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { navigate } from "@/hooks/use-hash-router";
import Wordmark from "./Wordmark";
import ModeBadge from "./ModeBadge";
import PartnersMarquee from "./PartnersMarquee";
import { api } from "@/lib/nexus/client";
import type { Mode } from "@/lib/nexus/constants";
import { toast } from "sonner";

export default function Dashboard() {
  const { user, tenant } = useAuthStore();
  const { setProjects, setActiveProject, setSessions, setActiveSession } = useAppStore();
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const { projects } = await api.projects.list();
        setProjects(projects);
      } catch {}
      setLoading(false);
    })();
  }, []);

  async function startWithMode(mode: Mode) {
    try {
      const name = mode === "development" ? "New Build" : mode === "problem_solving" ? "Open Debate" : "New Lesson";
      const { project } = await api.projects.create({ name, mode });
      const { session } = await api.sessions.create({ projectId: project.id, mode, title: name });
      const { projects: ps } = await api.projects.list();
      setProjects(ps);
      setActiveProject(project);
      const { sessions: list } = await api.sessions.list(project.id);
      setSessions(list);
      setActiveSession(session);
      navigate("session");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to start session");
    }
  }

  const firstName = (user?.name ?? user?.email ?? "").split(" ")[0].split("@")[0];

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 lg:py-10">
        {/* Header */}
        <div className="mb-6 sm:mb-8 lg:mb-10">
          <div className="flex items-center gap-2 mb-3">
            <Sparkles className="w-5 h-5 text-[var(--nexus-purple)]" />
            <span className="text-xs uppercase tracking-wider text-[var(--muted-foreground)]">Welcome back</span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold text-[var(--foreground)] tracking-tight mb-2">
            {firstName ? `Hey ${firstName}, what are we building?` : "What are we building?"}
          </h1>
          <p className="text-sm text-[var(--muted-foreground)] max-w-2xl">
            Nexus is your Principal Engineer in the browser. Pick a mode — each one has its own workflow,
            its own agent graph, and its own output shape.
          </p>
          {tenant && (
            <div className="mt-3 inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)] text-xs text-[var(--muted-foreground)]">
              <span className="w-1.5 h-1.5 rounded-full bg-[var(--nexus-success)]" />
              Workspace: <span className="text-[var(--foreground)]">{tenant.name}</span>
              <span className="text-[var(--muted-foreground)]">·</span>
              <span className="text-[var(--mode-dev-text)] capitalize">{tenant.plan}</span>
            </div>
          )}
        </div>

        {/* Mode cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 mb-8 sm:mb-10">
          <ModeCard
            mode="development"
            icon={<Layers className="w-5 h-5" />}
            title="Build something"
            tagline="Phase-gated build pipeline"
            description="Ideation → Planning → Specification → Implementation → Debug → Review. Nothing gets implemented without an approved spec. Output: a real, file-by-file application."
            features={["6-phase engine", "12-dimension spec builder", "Live sandbox preview", "GitHub push"]}
            cta="Start a build"
            onClick={() => startWithMode("development")}
          />
          <ModeCard
            mode="problem_solving"
            icon={<MessageSquare className="w-5 h-5" />}
            title="Think something through"
            tagline="Free-form debate"
            description="No phases, no gates. The agent argues multiple sides, proposes competing approaches, and produces a structured decision document. Pure reasoning artifact."
            features={["Phase-less debate", "Multi-approach comparison", "Decision-doc export", "Adaptive depth"]}
            cta="Open a debate"
            onClick={() => startWithMode("problem_solving")}
          />
          <ModeCard
            mode="learning"
            icon={<GraduationCap className="w-5 h-5" />}
            title="Learn something"
            tagline="Adaptive mastery loop"
            description="Explain → Practice → Quiz. Difficulty adapts to your mastery score over time. Tracks a long-term knowledge profile across topics."
            features={["Three-stage loop", "Mastery scoring", "Adaptive difficulty", "Knowledge profile"]}
            cta="Start a lesson"
            onClick={() => startWithMode("learning")}
          />
        </div>

        {/* Feature highlights */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-3 mb-6 sm:mb-8 lg:mb-10">
          <FeatureHighlight
            icon={<Zap className="w-4 h-4 text-[var(--nexus-purple)]" />}
            title="Intelligent Model Router"
            description="Phase-aware routing across Anthropic, OpenAI, Groq, Gemini. Fallback chains + mid-task model switching."
          />
          <FeatureHighlight
            icon={<Shield className="w-4 h-4 text-[var(--nexus-success)]" />}
            title="Human-in-the-loop gate"
            description="Spec confirmation required before implementation. The agent can't write code without your sign-off."
          />
          <FeatureHighlight
            icon={<GitBranch className="w-4 h-4 text-[var(--nexus-violet)]" />}
            title="Real file tree"
            description="Files live in PostgreSQL as data, not on a container disk. ZIP export, GitHub push, live preview — all renderers."
          />
          <FeatureHighlight
            icon={<Sparkles className="w-4 h-4 text-[var(--nexus-amber)]" />}
            title="Orchestrator-Worker"
            description="Brainstormer, Planner, Coder, Debugger, Reviewer — LangGraph-managed, with checkpointing and resumption."
          />
        </div>

        {/* Recent activity placeholder */}
        <div className="nexus-glass-subtle rounded-xl sm:rounded-2xl p-4 sm:p-6">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-base font-semibold text-[var(--foreground)]">Architecture at a glance</h2>
            <span className="text-[10px] text-[var(--muted-foreground)] uppercase tracking-wider hidden sm:inline">From the system design doc</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 sm:gap-4 text-sm">
            <ArchPillar title="Identity" desc="JWT + GitHub OAuth, refresh-token rotation with family detection, RBAC per tenant." />
            <ArchPillar title="Mode & Phase" desc="Mode-aware state machine: gated 6-phase dev, phase-less debate, 3-stage learning loop." />
            <ArchPillar title="Spec Builder" desc="12 architectural dimensions, 3 curated options each + custom. JSONB versioned specs." />
            <ArchPillar title="Agent Orchestrator" desc="LangGraph orchestrator-worker, max 20 iterations, 50 tool calls, 120s timeout." />
            <ArchPillar title="Model Gateway" desc="Provider routing, prompt cache, token tracking, circuit breaker, fallback chain." />
            <ArchPillar title="Observability" desc="OpenTelemetry traces, Langfuse agent metrics, Sentry errors, structured JSON logs." />
          </div>
        </div>

        {/* Partners marquee */}
        <PartnersMarquee />
      </div>
    </div>
  );
}

function ModeCard({
  mode, icon, title, tagline, description, features, cta, onClick,
}: {
  mode: Mode;
  icon: React.ReactNode;
  title: string;
  tagline: string;
  description: string;
  features: string[];
  cta: string;
  onClick: () => void;
}) {
  return (
    <div className="nexus-glass rounded-xl sm:rounded-2xl p-4 sm:p-5 flex flex-col group hover:border-[color-mix(in_srgb,var(--nexus-purple)_40%,transparent)] transition cursor-pointer" onClick={onClick}>
      <div className="flex items-start justify-between mb-3">
        <div className="w-9 h-9 sm:w-10 sm:h-10 rounded-xl bg-gradient-to-br from-[color-mix(in_srgb,var(--nexus-violet)_20%,transparent)] to-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] flex items-center justify-center">
          {icon}
        </div>
        <ModeBadge mode={mode} />
      </div>
      <h3 className="text-base sm:text-lg font-semibold text-[var(--foreground)] mb-1">{title}</h3>
      <p className="text-xs text-[var(--mode-dev-text)] mb-3">{tagline}</p>
      <p className="text-xs text-[var(--muted-foreground)] leading-relaxed mb-4 flex-1">{description}</p>
      <ul className="space-y-1 mb-4">
        {features.map((f) => (
          <li key={f} className="flex items-center gap-1.5 text-[11px] text-[var(--muted-foreground)]">
            <span className="w-1 h-1 rounded-full bg-[var(--nexus-purple)]" />
            {f}
          </li>
        ))}
      </ul>
      <button className="w-full py-2 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white text-xs font-medium hover:opacity-90 transition flex items-center justify-center gap-1.5 nexus-btn-glow">
        {cta}
        <ArrowRight className="w-3.5 h-3.5" />
      </button>
    </div>
  );
}

function FeatureHighlight({ icon, title, description }: { icon: React.ReactNode; title: string; description: string }) {
  return (
    <div className="px-2.5 sm:px-3 py-2 sm:py-2.5 rounded-lg bg-[var(--nexus-surface)]/40 border border-[var(--nexus-border)]">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[11px] sm:text-xs font-medium text-[var(--foreground)]">{title}</span>
      </div>
      <p className="text-[9px] sm:text-[10px] text-[var(--muted-foreground)] leading-relaxed line-clamp-3">{description}</p>
    </div>
  );
}

function ArchPillar({ title, desc }: { title: string; desc: string }) {
  return (
    <div className="px-3 py-2 rounded-lg bg-[var(--nexus-bg)]/40 border border-[var(--nexus-border)]">
      <div className="text-xs font-semibold text-[var(--mode-dev-text)] mb-1">{title}</div>
      <div className="text-[11px] text-[var(--muted-foreground)] leading-relaxed">{desc}</div>
    </div>
  );
}
