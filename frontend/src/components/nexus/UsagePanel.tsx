"use client";

import { useEffect, useState } from "react";
import { Zap, TrendingUp, Clock, DollarSign, Activity } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { api } from "@/lib/nexus/client";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

interface UsageData {
  summary: {
    totalUsed: number;
    totalBudget: number;
    percentUsed: number;
    sessions: number;
  };
  byModel: Array<{ modelId: string; tokensIn: number; tokensOut: number; costUsd: number; calls: number }>;
  sessions: Array<{
    id: string; tokensUsed: number; tokensBudget: number; baseModelId: string;
    mode: string; currentPhase: string; title?: string | null; updatedAt: string;
  }>;
}

export default function UsagePanel() {
  const { activeSession } = useAppStore();
  const { token } = useAuthStore();
  const [data, setData] = useState<UsageData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!token) return;
    let cancelled = false;
    api.usage.summary(activeSession?.id).then((d) => {
      if (!cancelled) setData(d as any);
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [token, activeSession?.id]);

  if (loading) {
    return <div className="p-4 text-xs text-[var(--muted-foreground)]">Loading usage…</div>;
  }
  if (!data) return null;

  return (
    <div className="h-full flex flex-col overflow-y-auto">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]/60">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">Usage & Cost</h3>
        <p className="text-[11px] text-[var(--muted-foreground)]">{activeSession ? "Current session" : "Tenant aggregate"}</p>
      </div>

      <div className="px-4 py-4 space-y-4">
        {/* Summary cards */}
        <div className="grid grid-cols-2 gap-2">
          <StatCard
            icon={<Zap className="w-4 h-4 text-[var(--nexus-purple)]" />}
            label="Tokens used"
            value={`${(data.summary.totalUsed / 1000).toFixed(1)}k`}
            sub={`${data.summary.percentUsed.toFixed(1)}% of budget`}
            tone={data.summary.percentUsed >= 80 ? "warn" : "ok"}
          />
          <StatCard
            icon={<Activity className="w-4 h-4 text-[var(--nexus-violet)]" />}
            label="Sessions"
            value={`${data.summary.sessions}`}
            sub="active + recent"
          />
          <StatCard
            icon={<TrendingUp className="w-4 h-4 text-[var(--nexus-success)]" />}
            label="Tokens in"
            value={`${(data.byModel.reduce((a, b) => a + b.tokensIn, 0) / 1000).toFixed(1)}k`}
          />
          <StatCard
            icon={<DollarSign className="w-4 h-4 text-[var(--nexus-amber)]" />}
            label="Est. cost"
            value={`$${data.byModel.reduce((a, b) => a + b.costUsd, 0).toFixed(4)}`}
          />
        </div>

        {/* Per-model breakdown */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
            By Model
          </div>
          <div className="space-y-1.5">
            {data.byModel.length === 0 && (
              <div className="text-xs text-[var(--muted-foreground)] italic px-2 py-2">No usage recorded yet.</div>
            )}
            {data.byModel.map((m) => (
              <div key={m.modelId} className="px-3 py-2 rounded-md bg-[var(--nexus-surface)]/60 border border-[var(--nexus-border)]/60">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-[var(--foreground)]">{m.modelId}</span>
                  <span className="text-[10px] text-[var(--muted-foreground)]">{m.calls} calls</span>
                </div>
                <div className="flex items-center gap-3 text-[10px] text-[var(--muted-foreground)]">
                  <span>In: {(m.tokensIn / 1000).toFixed(1)}k</span>
                  <span>Out: {(m.tokensOut / 1000).toFixed(1)}k</span>
                  <span>Cost: ${m.costUsd.toFixed(4)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Recent sessions */}
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
            Recent Sessions
          </div>
          <div className="space-y-1">
            {data.sessions.slice(0, 8).map((s) => {
              const pct = (s.tokensUsed / s.tokensBudget) * 100;
              return (
                <div key={s.id} className="px-2.5 py-1.5 rounded-md bg-[var(--nexus-surface)]/40 hover:bg-[var(--nexus-surface-2)]/60 transition">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-xs text-[var(--foreground)] truncate flex-1">{s.title ?? s.id.slice(0, 8)}</span>
                    <span className="text-[10px] text-[var(--muted-foreground)]">{s.mode}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1 rounded-full bg-[var(--nexus-surface-2)] overflow-hidden">
                      <div
                        className={cn(
                          "h-full",
                          pct >= 95 ? "bg-[var(--nexus-error)]" : pct >= 80 ? "bg-[var(--nexus-amber)]" : "bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-violet)]"
                        )}
                        style={{ width: `${Math.min(100, pct)}%` }}
                      />
                    </div>
                    <span className="text-[9px] text-[var(--muted-foreground)] tabular-nums">
                      {(s.tokensUsed / 1000).toFixed(1)}k
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
}

function StatCard({ icon, label, value, sub, tone }: { icon: React.ReactNode; label: string; value: string; sub?: string; tone?: "ok" | "warn" }) {
  return (
    <div className="px-3 py-2.5 rounded-lg bg-[var(--nexus-surface)]/60 border border-[var(--nexus-border)]/60">
      <div className="flex items-center gap-1.5 mb-1">
        {icon}
        <span className="text-[10px] uppercase tracking-wider text-[var(--muted-foreground)]">{label}</span>
      </div>
      <div className="text-lg font-semibold text-[var(--foreground)] tabular-nums">{value}</div>
      {sub && (
        <div className={cn("text-[10px]", tone === "warn" ? "text-[var(--nexus-amber)]" : "text-[var(--muted-foreground)]")}>{sub}</div>
      )}
    </div>
  );
}
