"use client";

import { Check, ChevronRight, Lock } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import {
  DEV_PHASES, PHASE_META, nextPhase, requiresApproval,
  type Phase,
} from "@/lib/nexus/constants";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useState } from "react";

export default function PhaseStepper() {
  const { activeSession, specs, updateActiveSession } = useAppStore();
  const [advancing, setAdvancing] = useState(false);

  if (!activeSession || activeSession.mode !== "development") return null;

  const currentPhase = activeSession.currentPhase as Phase;
  const currentIdx = DEV_PHASES.indexOf(currentPhase as any);
  const confirmed = specs.find((s) => s.isCurrent)?.confirmedAt != null;

  async function advance() {
    if (!activeSession) return;
    const target = nextPhase(currentPhase as Phase);
    if (!target) return;

    if (requiresApproval(currentPhase, target) && !confirmed) {
      toast.error("Specification must be confirmed before Implementation.");
      return;
    }

    setAdvancing(true);
    try {
      const { session } = await api.sessions.advancePhase(activeSession.id, target);
      updateActiveSession({ currentPhase: session.currentPhase as Phase });
      toast.success(`Phase: ${PHASE_META[session.currentPhase as Phase].label}`);
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to advance phase");
    } finally {
      setAdvancing(false);
    }
  }

  return (
    <div className="px-3 sm:px-6 py-3 border-b border-[var(--nexus-border)] bg-[var(--nexus-bg)]/40">
      <div className="phase-stepper-track flex items-center gap-1">
        {DEV_PHASES.map((phase, idx) => {
          const meta = PHASE_META[phase];
          const isCurrent = phase === currentPhase;
          const isCompleted = currentIdx > idx || currentPhase === "completed";
          const isLocked = idx > currentIdx && requiresApproval(DEV_PHASES[idx - 1] as Phase, phase) && !confirmed;
          const icon = meta.icon;

          return (
            <div key={phase} className="flex items-center shrink-0">
              <button
                onClick={() => isCompleted && advance()}
                disabled={!isCompleted || advancing}
                className={cn(
                  "flex items-center gap-1.5 sm:gap-2 px-2 sm:px-3 py-1.5 rounded-md transition group whitespace-nowrap",
                  isCurrent && "phase-pill-active",
                  isCompleted && !isCurrent && "phase-pill-completed",
                  !isCurrent && !isCompleted && "phase-pill",
                )}
                title={isLocked ? "Locked — confirm spec first" : meta.tagline}
              >
                <span className={cn(
                  "w-5 h-5 rounded-full flex items-center justify-center text-[10px] font-semibold shrink-0",
                  isCurrent && "bg-[var(--nexus-purple)] text-white",
                  isCompleted && !isCurrent && "bg-[var(--nexus-success)] text-white",
                  !isCurrent && !isCompleted && "bg-[var(--nexus-surface-2)] text-[var(--muted-foreground)]",
                )}>
                  {isCompleted && !isCurrent ? <Check className="w-3 h-3" /> : isLocked ? <Lock className="w-2.5 h-2.5" /> : idx + 1}
                </span>
                <span className="text-xs font-medium whitespace-nowrap">{meta.label}</span>
              </button>
              {idx < DEV_PHASES.length - 1 && (
                <div className={cn(
                  "flex-1 min-w-[8px] sm:min-w-[24px] h-px mx-1 sm:mx-2 transition shrink-0",
                  isCompleted ? "bg-gradient-to-r from-[var(--nexus-success)] to-[var(--nexus-purple)]" : "bg-[var(--nexus-border)]"
                )} />
              )}
            </div>
          );
        })}

        {/* Advance button */}
        {currentPhase !== "completed" && (
          <button
            onClick={advance}
            disabled={advancing || (requiresApproval(currentPhase, nextPhase(currentPhase) as Phase) && !confirmed)}
            className="ml-2 sm:ml-3 shrink-0 px-2 sm:px-3 py-1.5 rounded-md text-xs font-medium bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white hover:opacity-90 transition disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1.5 whitespace-nowrap"
            title={requiresApproval(currentPhase, nextPhase(currentPhase) as Phase) && !confirmed ? "Confirm spec to unlock" : "Advance to next phase"}
          >
            <span className="hidden sm:inline">{advancing ? "Advancing…" : `Advance to ${PHASE_META[nextPhase(currentPhase) as Phase]?.label ?? "next"}`}</span>
            <span className="sm:hidden">{advancing ? "…" : "Next"}</span>
            <ChevronRight className="w-3.5 h-3.5" />
          </button>
        )}
      </div>
      {requiresApproval(currentPhase, nextPhase(currentPhase) as Phase) && !confirmed && (
        <div className="mt-2 px-3 py-1.5 rounded-md bg-[color-mix(in_srgb,var(--nexus-amber)_10%,transparent)] border border-[color-mix(in_srgb,var(--nexus-amber)_30%,transparent)] text-[var(--mode-problem-text)] text-xs flex items-center gap-2">
          <Lock className="w-3 h-3 shrink-0" />
          <span>The Specification must be confirmed before advancing to Implementation.</span>
        </div>
      )}
    </div>
  );
}
