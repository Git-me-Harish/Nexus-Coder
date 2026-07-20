"use client";

import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { X, KeyRound, Check, Loader2, Trash2, ShieldCheck, ExternalLink, AlertTriangle } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { api, ApiError } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

interface Credential {
  provider: string;
  keyPreview: string;
  isValid: boolean | null;
  lastValidatedAt: string | null;
  lastValidationError: string | null;
  updatedAt: string;
}

const PROVIDER_META: Record<string, { label: string; helpUrl: string; placeholder: string }> = {
  anthropic: { label: "Anthropic", helpUrl: "https://console.anthropic.com/settings/keys", placeholder: "sk-ant-..." },
  openai:    { label: "OpenAI",    helpUrl: "https://platform.openai.com/api-keys",         placeholder: "sk-..." },
  groq:      { label: "Groq",      helpUrl: "https://console.groq.com/keys",                placeholder: "gsk_..." },
  gemini:    { label: "Google Gemini", helpUrl: "https://aistudio.google.com/apikey",        placeholder: "AIza..." },
};

const PROVIDER_ORDER = ["anthropic", "openai", "groq", "gemini"];

export default function ModelConfigModal() {
  const { showModelConfig, setShowModelConfig } = useAppStore();
  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loading, setLoading] = useState(false);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [busyProvider, setBusyProvider] = useState<string | null>(null);

  useEffect(() => {
    if (!showModelConfig) return;
    refresh();
  }, [showModelConfig]);

  async function refresh() {
    setLoading(true);
    try {
      const { credentials } = await api.credentials.list();
      setCredentials(credentials);
    } catch (err) {
      if (!(err instanceof ApiError && err.status === 401)) {
        toast.error("Couldn't load your configured models");
      }
    } finally {
      setLoading(false);
    }
  }

  async function saveKey(provider: string) {
    const apiKey = inputs[provider]?.trim();
    if (!apiKey) return;
    setBusyProvider(provider);
    try {
      const { credential } = await api.credentials.save(provider, apiKey);
      setCredentials((prev) => [...prev.filter((c) => c.provider !== provider), credential]);
      setInputs((prev) => ({ ...prev, [provider]: "" }));
      if (credential.isValid) {
        toast.success(`${PROVIDER_META[provider]?.label ?? provider} key saved and verified`);
      } else {
        toast.warning(`Key saved, but couldn't be verified: ${credential.lastValidationError ?? "unknown error"}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save key");
    } finally {
      setBusyProvider(null);
    }
  }

  async function revalidate(provider: string) {
    setBusyProvider(provider);
    try {
      const { credential } = await api.credentials.validate(provider);
      setCredentials((prev) => [...prev.filter((c) => c.provider !== provider), credential]);
      toast[credential.isValid ? "success" : "error"](
        credential.isValid ? "Key is valid" : (credential.lastValidationError ?? "Key is invalid")
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Validation failed");
    } finally {
      setBusyProvider(null);
    }
  }

  async function removeKey(provider: string) {
    setBusyProvider(provider);
    try {
      await api.credentials.remove(provider);
      setCredentials((prev) => prev.filter((c) => c.provider !== provider));
      toast.success(`${PROVIDER_META[provider]?.label ?? provider} key removed`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to remove key");
    } finally {
      setBusyProvider(null);
    }
  }

  if (!showModelConfig || typeof document === "undefined") return null;

  return createPortal(
    <div
      className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm sm:p-6"
      onClick={() => setShowModelConfig(false)}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="configure-models-title"
        className="nexus-glass flex max-h-[calc(100dvh-1.5rem)] w-full max-w-xl flex-col overflow-hidden rounded-2xl shadow-2xl sm:max-h-[calc(100dvh-3rem)]"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-4 border-b border-[var(--nexus-border)] p-4 sm:p-6">
          <div className="flex items-start gap-3">
            <div className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]">
              <KeyRound className="h-4 w-4 text-[var(--mode-dev-text)]" />
            </div>
            <div>
              <h2 id="configure-models-title" className="text-lg font-semibold text-[var(--foreground)]">Configure Models</h2>
              <p className="mt-1 text-sm text-[var(--muted-foreground)]">
                Add your own provider API keys to unlock each model. Keys are encrypted at rest
                and never shown again after saving.
              </p>
            </div>
          </div>
          <button
            onClick={() => setShowModelConfig(false)}
            className="shrink-0 rounded-md p-1.5 text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 sm:p-6">
          <div className="space-y-4">
            {PROVIDER_ORDER.map((provider) => {
              const meta = PROVIDER_META[provider];
              const existing = credentials.find((c) => c.provider === provider);
              const busy = busyProvider === provider;

              return (
                <div key={provider} className="rounded-xl border border-[var(--nexus-border)] p-4">
                  <div className="mb-3 flex items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-[var(--foreground)]">{meta.label}</span>
                      {existing && (
                        existing.isValid ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-success)_15%,transparent)] px-2 py-0.5 text-[10px] font-medium text-[var(--mode-learning-text)]">
                            <ShieldCheck className="h-3 w-3" /> Verified
                          </span>
                        ) : existing.isValid === false ? (
                          <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-amber)_15%,transparent)] px-2 py-0.5 text-[10px] font-medium text-[var(--mode-problem-text)]">
                            <AlertTriangle className="h-3 w-3" /> Needs attention
                          </span>
                        ) : null
                      )}
                    </div>
                    <a
                      href={meta.helpUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-[11px] text-[var(--muted-foreground)] transition hover:text-[var(--foreground)]"
                    >
                      Get a key <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>

                  {existing ? (
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate font-mono text-sm text-[var(--foreground)]">{existing.keyPreview}</div>
                        {existing.lastValidationError && existing.isValid === false && (
                          <div className="mt-0.5 text-xs text-[var(--mode-problem-text)]">{existing.lastValidationError}</div>
                        )}
                      </div>
                      <div className="flex shrink-0 items-center gap-1.5">
                        <button
                          onClick={() => revalidate(provider)}
                          disabled={busy}
                          className="rounded-md border border-[var(--nexus-border)] px-2.5 py-1.5 text-xs text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] disabled:opacity-50"
                        >
                          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Re-check"}
                        </button>
                        <button
                          onClick={() => removeKey(provider)}
                          disabled={busy}
                          className="rounded-md border border-[var(--nexus-border)] p-1.5 text-[var(--muted-foreground)] transition hover:border-[color-mix(in_srgb,var(--nexus-amber)_50%,transparent)] hover:text-[var(--mode-problem-text)] disabled:opacity-50"
                          aria-label={`Remove ${meta.label} key`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <input
                        type="password"
                        placeholder={meta.placeholder}
                        value={inputs[provider] ?? ""}
                        onChange={(e) => setInputs((prev) => ({ ...prev, [provider]: e.target.value }))}
                        onKeyDown={(e) => { if (e.key === "Enter") saveKey(provider); }}
                        className="min-w-0 flex-1 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-bg)] px-3 py-2 font-mono text-sm text-[var(--foreground)] placeholder:font-sans placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]"
                      />
                      <button
                        onClick={() => saveKey(provider)}
                        disabled={busy || !inputs[provider]?.trim()}
                        className="flex shrink-0 items-center gap-1.5 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] px-3 py-2 text-sm text-white transition hover:opacity-90 disabled:opacity-40"
                      >
                        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
                        Save
                      </button>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="mt-5 flex items-start gap-2 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface-2)] p-3 text-xs text-[var(--muted-foreground)]">
            <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>
              Keys are encrypted at rest and only decrypted in memory when a request is made — no
              route ever returns your raw key back, including this screen after you save it.
            </p>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
}