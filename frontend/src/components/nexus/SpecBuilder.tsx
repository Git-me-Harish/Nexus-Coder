"use client";

import { useState } from "react";
import {
  Palette, Server, Database, Route, ShieldCheck, Sparkles,
  Zap, Gauge, Users, FileWarning, Workflow, GaugeCircle,
  Check, Lock, FileText, RefreshCw,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { SPEC_DIMENSIONS, type SpecDimension } from "@/lib/nexus/constants";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const ICONS: Record<string, any> = {
  Palette, Server, Database, Route, ShieldCheck, Sparkles,
  Zap, Gauge, Users, FileWarning, Workflow, GaugeCircle,
};

export default function SpecBuilder() {
  const { activeSession, specs, setSpecs } = useAppStore();
  const [openDim, setOpenDim] = useState<string | null>(SPEC_DIMENSIONS[0].slug);
  const [selected, setSelected] = useState<Record<string, string>>(() => {
    const cur = specs.find((s) => s.isCurrent);
    if (!cur) return {};
    const dims = cur.dimensions as Record<string, any>;
    const out: Record<string, string> = {};
    for (const d of SPEC_DIMENSIONS) {
      const v = dims[d.slug];
      if (typeof v === "string") out[d.slug] = v;
      else if (v && typeof v === "object" && v.optionId) out[d.slug] = v.optionId;
    }
    return out;
  });
  const [customText, setCustomText] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);

  if (!activeSession) return null;

  const current = specs.find((s) => s.isCurrent);
  const confirmed = current?.confirmedAt != null;
  const filledCount = Object.keys(selected).length;
  const totalCount = SPEC_DIMENSIONS.length;

  function pick(dim: SpecDimension, optionId: string) {
    setSelected((s) => ({ ...s, [dim.slug]: optionId }));
    setCustomText((c) => ({ ...c, [dim.slug]: "" }));
  }

  function setCustom(dim: SpecDimension, text: string) {
    setCustomText((c) => ({ ...c, [dim.slug]: text }));
    setSelected((s) => ({ ...s, [dim.slug]: `custom:${text.slice(0, 40)}` }));
  }

  async function save() {
    if (!activeSession) return;
    setSaving(true);
    try {
      const dimensions: Record<string, any> = {};
      for (const dim of SPEC_DIMENSIONS) {
        const sel = selected[dim.slug];
        if (!sel) continue;
        if (sel.startsWith("custom:")) {
          dimensions[dim.slug] = { optionId: "custom", label: "Custom", rationale: sel.slice(7), configPayload: { custom: true, text: sel.slice(7) } };
        } else {
          const opt = dim.options.find((o) => o.id === sel);
          if (opt) dimensions[dim.slug] = { optionId: opt.id, label: opt.label, rationale: opt.rationale, configPayload: opt.configPayload };
        }
      }
      const { spec } = await api.spec.save(activeSession.id, dimensions);
      const { specs: list } = await api.spec.get(activeSession.id);
      setSpecs(list);
      toast.success(`Spec v${spec.version} saved`);
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to save spec");
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    if (!activeSession) return;
    try {
      await api.spec.confirm(activeSession.id);
      const { specs: list } = await api.spec.get(activeSession.id);
      setSpecs(list);
      toast.success("Spec confirmed — Implementation unlocked.");
    } catch (err: any) {
      toast.error(err?.message ?? "Failed to confirm spec");
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]/60 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--foreground)]">Specification</h3>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            {filledCount}/{totalCount} dimensions · v{current?.version ?? 0}
          </p>
        </div>
        {confirmed && (
          <span className="px-2 py-0.5 rounded-full bg-[var(--nexus-success)]/15 border border-[var(--nexus-success)]/40 text-[var(--mode-learning-text)] text-[10px] font-medium flex items-center gap-1">
            <Check className="w-3 h-3" /> Confirmed
          </span>
        )}
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1">
        {SPEC_DIMENSIONS.map((dim) => {
          const Icon = ICONS[dim.icon] ?? FileText;
          const isOpen = openDim === dim.slug;
          const sel = selected[dim.slug];
          const selOpt = dim.options.find((o) => o.id === sel);
          const isCustom = sel?.startsWith("custom:");

          return (
            <div key={dim.slug} className="rounded-lg border border-[var(--nexus-border)]/60 overflow-hidden">
              <button
                onClick={() => setOpenDim(isOpen ? null : dim.slug)}
                className="w-full px-3 py-2.5 flex items-center gap-2 hover:bg-[var(--nexus-surface-2)]/50 transition"
              >
                <Icon className={cn("w-4 h-4 shrink-0", sel ? "text-[var(--nexus-purple)]" : "text-[var(--muted-foreground)]")} />
                <div className="flex-1 text-left min-w-0">
                  <div className="text-xs font-medium text-[var(--foreground)]">{dim.label}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)] truncate">
                    {selOpt?.label ?? (isCustom ? "Custom" : "Not set")}
                  </div>
                </div>
                {sel && <Check className="w-3 h-3 text-[var(--nexus-success)]" />}
              </button>
              {isOpen && (
                <div className="px-3 pb-3 space-y-1.5 bg-[var(--nexus-bg)]/40">
                  <p className="text-[10px] text-[var(--muted-foreground)] italic pt-1">{dim.description}</p>
                  {dim.options.map((opt) => (
                    <button
                      key={opt.id}
                      onClick={() => pick(dim, opt.id)}
                      className={cn(
                        "w-full text-left px-2.5 py-2 rounded-md border text-xs transition",
                        sel === opt.id
                          ? "border-[var(--nexus-purple)]/50 bg-[var(--nexus-purple)]/10"
                          : "border-[var(--nexus-border)] hover:border-[var(--nexus-purple)]/30 bg-[var(--nexus-surface)]/40"
                      )}
                    >
                      <div className="font-medium text-[var(--foreground)] mb-0.5">{opt.label}</div>
                      <div className="text-[10px] text-[var(--muted-foreground)] leading-snug">{opt.rationale}</div>
                    </button>
                  ))}
                  <div className={cn(
                    "px-2.5 py-2 rounded-md border text-xs transition",
                    isCustom ? "border-[var(--nexus-purple)]/50 bg-[var(--nexus-purple)]/10" : "border-[var(--nexus-border)] bg-[var(--nexus-surface)]/40"
                  )}>
                    <div className="font-medium text-[var(--foreground)] mb-1">Describe your need</div>
                    <textarea
                      value={customText[dim.slug] ?? ""}
                      onChange={(e) => setCustom(dim, e.target.value)}
                      placeholder="Type a custom requirement…"
                      rows={2}
                      className="w-full bg-transparent text-[11px] text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] resize-none focus:outline-none"
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="px-3 py-3 border-t border-[var(--nexus-border)]/60 space-y-2">
        <button
          onClick={save}
          disabled={saving || filledCount === 0}
          className="w-full px-3 py-2 rounded-lg text-xs font-medium bg-[var(--nexus-surface-2)] border border-[var(--nexus-border)] hover:border-[var(--nexus-purple)]/40 text-white disabled:opacity-40 transition flex items-center justify-center gap-2"
        >
          {saving ? <RefreshCw className="w-3 h-3 animate-spin" /> : <FileText className="w-3 h-3" />}
          Save spec (v{(current?.version ?? 0) + 1})
        </button>
        <button
          onClick={confirm}
          disabled={!current || confirmed}
          className="w-full px-3 py-2 rounded-lg text-xs font-medium bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white disabled:opacity-30 hover:from-[var(--nexus-violet)] hover:to-[var(--nexus-violet)] transition flex items-center justify-center gap-2"
        >
          {confirmed ? <Lock className="w-3 h-3" /> : <Check className="w-3 h-3" />}
          {confirmed ? "Confirmed" : "Confirm for implementation"}
        </button>
      </div>
    </div>
  );
}
