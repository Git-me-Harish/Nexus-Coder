"use client";

import { cn } from "@/lib/utils";
import type { Mode } from "@/lib/nexus/constants";

interface ModeBadgeProps {
  mode: Mode;
  className?: string;
}

const MAP: Record<Mode, { label: string; cls: string }> = {
  development:     { label: "Development",     cls: "mode-chip-dev" },
  problem_solving: { label: "Problem Solving", cls: "mode-chip-problem" },
  learning:        { label: "Learning",        cls: "mode-chip-learning" },
};

export default function ModeBadge({ mode, className }: ModeBadgeProps) {
  const m = MAP[mode];
  return (
    <span className={cn("inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium", m.cls, className)}>
      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-80" />
      {m.label}
    </span>
  );
}
