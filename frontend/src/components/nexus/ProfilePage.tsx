"use client";

import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft, Sun, Moon, KeyRound, Check, Loader2, Trash2, ShieldCheck,
  ExternalLink, AlertTriangle, Github, Unlink, LogOut, Sparkles,
  User as UserIcon, Palette, Link2, Save, Lock, Unlock, Upload, Eye, EyeOff,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useThemeStore } from "@/stores/themeStore";
import { useSudoStore } from "@/stores/sudoStore";
import { navigate } from "@/hooks/use-hash-router";
import { api, ApiError } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { OutlineText } from "./OutlineText";
import Avatar, { initialsFor } from "./Avatar";

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

const TABS = [
  { id: "general", label: "General", icon: UserIcon, blurb: "Name, photo, bio" },
  { id: "security", label: "Security", icon: Lock, blurb: "Password & sessions" },
  { id: "appearance", label: "Appearance", icon: Palette, blurb: "Theme" },
  { id: "connections", label: "Connections", icon: Link2, blurb: "GitHub" },
  { id: "keys", label: "API Keys", icon: KeyRound, blurb: "Model providers" },
  { id: "account", label: "Account", icon: LogOut, blurb: "Workspace & sign out" },
] as const;

type TabId = (typeof TABS)[number]["id"];

/**
 * Mirrors backend/app/schemas/auth.py's shared _check_password_strength
 * (10-128 chars, must mix letters with numbers/symbols), so the form can
 * reject a weak password before spending a round-trip on it.
 */
function passwordIssue(pw: string): string | null {
  if (pw.length < 10) return "At least 10 characters";
  if (pw.length > 128) return "No more than 128 characters";
  if (/^\d+$/.test(pw)) return "Must include a letter, not just numbers";
  if (/^[a-zA-Z]+$/.test(pw)) return "Must include a number or symbol, not just letters";
  return null;
}

export default function ProfilePage() {
  const [tab, setTab] = useState<TabId>("general");
  const { user } = useAuthStore();

  return (
    <div className="h-screen overflow-hidden bg-[var(--nexus-bg)] flex flex-col">
      <header className="h-14 shrink-0 bg-[var(--nexus-bg)]/85 backdrop-blur-xl border-b border-[var(--nexus-border)] flex items-center gap-3 px-4 sm:px-6">
        <button
          onClick={() => navigate("dashboard")}
          className="flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
        >
          <ArrowLeft className="h-4 w-4" />
          Dashboard
        </button>
        <div className="h-5 w-px bg-[var(--nexus-border)]" />
        <div className="flex items-center gap-1.5">
          <img src="/logo.png" alt="" aria-hidden="true" className="w-5 h-5 object-contain" />
          <OutlineText className="!text-sm tracking-wide">NEXUS</OutlineText>
        </div>
        <span className="ml-auto hidden text-[11px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] sm:inline">
          Settings
        </span>
      </header>

      {/* Mobile tab bar */}
      <div className="md:hidden shrink-0 border-b border-[var(--nexus-border)] overflow-x-auto">
        <div className="flex px-2 py-1.5 gap-1 min-w-max">
          {TABS.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={cn(
                "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition whitespace-nowrap",
                tab === t.id
                  ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] text-[var(--mode-dev-text)]"
                  : "text-[var(--muted-foreground)] hover:text-[var(--foreground)]"
              )}
            >
              <t.icon className="h-3.5 w-3.5" />
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 min-h-0 flex">
        {/* Sticky desktop side nav */}
        <nav className="hidden md:flex w-64 shrink-0 flex-col border-r border-[var(--nexus-border)] py-5 px-3 overflow-y-auto">
          <div className="flex items-center gap-3 px-2 pb-5 mb-3 border-b border-[var(--nexus-border)]">
            <Avatar src={user?.avatarUrl} name={user?.name ?? user?.email} className="h-11 w-11" textClassName="text-sm" />
            <div className="min-w-0">
              <div className="truncate text-sm font-medium text-[var(--foreground)]">{user?.name ?? "Account"}</div>
              <div className="truncate text-[11px] text-[var(--muted-foreground)]">{user?.email}</div>
            </div>
          </div>
          <div className="space-y-0.5">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={cn(
                  "w-full flex items-start gap-2.5 px-3 py-2 rounded-lg text-sm transition text-left",
                  tab === t.id
                    ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] text-[var(--mode-dev-text)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]"
                    : "text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] border border-transparent"
                )}
              >
                <t.icon className="h-4 w-4 mt-0.5 shrink-0" />
                <span className="min-w-0">
                  <span className="block leading-tight">{t.label}</span>
                  <span className="block text-[10px] opacity-70 leading-tight mt-0.5">{t.blurb}</span>
                </span>
              </button>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="flex-1 min-w-0 overflow-y-auto">
          <div className="mx-auto max-w-2xl px-4 py-8 sm:px-8 sm:py-10">
            {tab === "general" && <GeneralTab />}
            {tab === "security" && <SecurityTab />}
            {tab === "appearance" && <AppearanceTab />}
            {tab === "connections" && <ConnectionsTab />}
            {tab === "keys" && <ApiKeysTab />}
            {tab === "account" && <AccountTab />}
          </div>
        </div>
      </div>
    </div>
  );
}

function TabHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold text-[var(--foreground)]">{title}</h1>
      {description && <p className="mt-1 text-sm text-[var(--muted-foreground)]">{description}</p>}
    </div>
  );
}

function Card({ title, description, children, className }: { title?: string; description?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("rounded-xl border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/40 p-4 sm:p-5", className)}>
      {title && (
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-[var(--foreground)]">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-[var(--muted-foreground)]">{description}</p>}
        </div>
      )}
      {children}
    </section>
  );
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between gap-2">
        <label className="block text-[11px] font-medium uppercase tracking-wider text-[var(--muted-foreground)]">{label}</label>
        {hint && <span className="text-[10px] text-[var(--muted-foreground)]">{hint}</span>}
      </div>
      {children}
    </div>
  );
}

const inputCls = "w-full px-3 py-2 rounded-lg bg-[var(--nexus-surface)] border border-[var(--nexus-border)] text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] focus:border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]";
const primaryBtn = "flex items-center gap-2 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] px-4 py-2.5 text-sm text-white transition hover:opacity-90 disabled:opacity-40";
const ghostBtn = "flex items-center gap-2 rounded-lg border border-[var(--nexus-border)] px-3 py-2 text-xs text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] disabled:opacity-50";

function GeneralTab() {
  const { user, tenant, updateUser } = useAuthStore();
  const [name, setName] = useState(user?.name ?? "");
  const [bio, setBio] = useState(user?.bio ?? "");
  const [company, setCompany] = useState(user?.company ?? "");
  const [location, setLocation] = useState(user?.location ?? "");
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const dirty = name !== (user?.name ?? "") || bio !== (user?.bio ?? "")
    || company !== (user?.company ?? "") || location !== (user?.location ?? "");

  async function save() {
    setSaving(true);
    try {
      const updated = await api.auth.updateProfile({ name, bio, company, location });
      updateUser(updated);
      toast.success("Profile updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to update profile");
    } finally {
      setSaving(false);
    }
  }

  async function pickAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    // Reset immediately so re-picking the SAME file still fires onChange.
    e.target.value = "";
    if (!file) return;

    setUploading(true);
    try {
      const { avatarUrl } = await api.auth.uploadAvatar(file);
      updateUser({ avatarUrl });
      toast.success("Photo updated");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Couldn't upload that photo");
    } finally {
      setUploading(false);
    }
  }

  async function removeAvatar() {
    setUploading(true);
    try {
      await api.auth.deleteAvatar();
      updateUser({ avatarUrl: null });
      toast.success("Photo removed");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't remove that photo");
    } finally {
      setUploading(false);
    }
  }

  const memberSince = user?.createdAt
    ? new Date(user.createdAt).toLocaleDateString(undefined, { month: "long", year: "numeric" })
    : null;

  return (
    <div>
      <TabHeader title="General" description="Your identity across Nexus." />

      <div className="space-y-4">
        <Card title="Profile photo" description="PNG, JPEG, GIF or WebP. Up to 2 MB.">
          <div className="flex items-center gap-4">
            <Avatar src={user?.avatarUrl} name={name || user?.email} className="h-20 w-20" textClassName="text-2xl" />
            <div className="flex flex-col gap-2">
              <div className="flex flex-wrap gap-2">
                <button onClick={() => fileRef.current?.click()} disabled={uploading} className={ghostBtn}>
                  {uploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                  {user?.avatarUrl ? "Change photo" : "Upload photo"}
                </button>
                {user?.avatarUrl && (
                  <button onClick={removeAvatar} disabled={uploading} className={cn(ghostBtn, "hover:border-[color-mix(in_srgb,var(--nexus-amber)_50%,transparent)] hover:text-[var(--mode-problem-text)]")}>
                    <Trash2 className="h-3.5 w-3.5" />
                    Remove
                  </button>
                )}
              </div>
              {!user?.avatarUrl && (
                <p className="text-[11px] text-[var(--muted-foreground)]">
                  Without a photo we show your initials ({initialsFor(name || user?.email)}).
                </p>
              )}
            </div>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/gif,image/webp" onChange={pickAvatar} className="hidden" />
          </div>
        </Card>

        <Card title="Details">
          <div className="space-y-4">
            <Field label="Name">
              <input value={name} onChange={(e) => setName(e.target.value)} maxLength={80} className={inputCls} placeholder="Your name" />
            </Field>
            <Field label="Email" hint="Sign-in address — contact support to change">
              <input value={user?.email ?? ""} disabled className={cn(inputCls, "opacity-60 cursor-not-allowed")} />
            </Field>
            <Field label="Bio" hint={`${bio.length}/280`}>
              <textarea
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={3}
                maxLength={280}
                className={cn(inputCls, "resize-none")}
                placeholder="What are you building with Nexus?"
              />
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Company">
                <input value={company} onChange={(e) => setCompany(e.target.value)} maxLength={80} className={inputCls} placeholder="Optional" />
              </Field>
              <Field label="Location">
                <input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={80} className={inputCls} placeholder="Optional" />
              </Field>
            </div>

            <div className="flex items-center gap-3 pt-1">
              <button onClick={save} disabled={!dirty || saving} className={primaryBtn}>
                {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save changes
              </button>
              {dirty && <span className="text-xs text-[var(--muted-foreground)]">Unsaved changes</span>}
            </div>
          </div>
        </Card>

        <Card title="Account details">
          <dl className="space-y-2.5 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[var(--muted-foreground)]">Workspace</dt>
              <dd className="text-[var(--foreground)]">{tenant?.name ?? "—"}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[var(--muted-foreground)]">Plan</dt>
              <dd>
                <span className="inline-flex items-center gap-1 rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-[var(--mode-dev-text)]">
                  <Sparkles className="h-3 w-3" /> {tenant?.plan ?? "free"}
                </span>
              </dd>
            </div>
            {memberSince && (
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted-foreground)]">Member since</dt>
                <dd className="text-[var(--foreground)]">{memberSince}</dd>
              </div>
            )}
            {user?.githubUsername && (
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted-foreground)]">GitHub</dt>
                <dd className="flex items-center gap-1.5 text-[var(--foreground)]">
                  <Github className="h-3.5 w-3.5" /> {user.githubUsername}
                </dd>
              </div>
            )}
          </dl>
        </Card>
      </div>
    </div>
  );
}

function SecurityTab() {
  const { user, updateUser } = useAuthStore();
  // Accounts created through "Continue with GitHub" have no password yet, so
  // this same form doubles as "set a password" for them.
  const hasPassword = user?.hasPassword !== false;

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showCurrent, setShowCurrent] = useState(false);
  const [showNew, setShowNew] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const issue = newPassword ? passwordIssue(newPassword) : null;
  const mismatch = confirmPassword.length > 0 && confirmPassword !== newPassword;
  const canSubmit = !!newPassword && !issue && !mismatch && confirmPassword.length > 0
    && (!hasPassword || currentPassword.length > 0);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!canSubmit) return;

    setSaving(true);
    try {
      const result = await api.auth.changePassword({
        currentPassword: hasPassword ? currentPassword : undefined,
        newPassword,
      });
      // The change revoked every refresh token, this session's included, so
      // adopt the fresh pair the server just issued or the next refresh 401s.
      useAuthStore.getState().setSession({
        user: result.user,
        tenant: result.tenant,
        token: result.token,
        refreshToken: result.refreshToken,
      });
      updateUser({ hasPassword: true });
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      toast.success(hasPassword ? "Password changed — other sessions signed out" : "Password set");
    } catch (err) {
      const message = err instanceof Error ? err.message : "Couldn't change your password";
      setError(message);
      toast.error(message);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div>
      <TabHeader
        title="Security"
        description={hasPassword
          ? "Change your password. Signing in elsewhere will be required again afterwards."
          : "You signed up with GitHub, so this account has no password yet. Set one to also sign in with email."}
      />

      <Card title={hasPassword ? "Change password" : "Set a password"}>
        <form onSubmit={submit} className="space-y-4">
          {hasPassword && (
            <Field label="Current password">
              <div className="relative">
                <input
                  type={showCurrent ? "text" : "password"}
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  autoComplete="current-password"
                  className={cn(inputCls, "pr-9")}
                  placeholder="••••••••"
                />
                <button
                  type="button"
                  onClick={() => setShowCurrent((v) => !v)}
                  tabIndex={-1}
                  aria-label={showCurrent ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] transition hover:text-[var(--foreground)]"
                >
                  {showCurrent ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>
            </Field>
          )}

          <Field label="New password">
            <div className="relative">
              <input
                type={showNew ? "text" : "password"}
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoComplete="new-password"
                className={cn(inputCls, "pr-9")}
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowNew((v) => !v)}
                tabIndex={-1}
                aria-label={showNew ? "Hide password" : "Show password"}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] transition hover:text-[var(--foreground)]"
              >
                {showNew ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
              </button>
            </div>
            <p className={cn("mt-1.5 text-[10px]", newPassword && !issue ? "text-[var(--nexus-success)]" : "text-[var(--muted-foreground)]")}>
              {newPassword && !issue ? (
                <span className="flex items-center gap-1"><Check className="h-3 w-3" /> Meets password requirements</span>
              ) : (
                issue ?? "10+ characters, mixing letters with numbers or symbols"
              )}
            </p>
          </Field>

          <Field label="Confirm new password">
            <input
              type={showNew ? "text" : "password"}
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              autoComplete="new-password"
              className={cn(inputCls, mismatch && "border-[var(--nexus-error)]")}
              placeholder="••••••••"
            />
            {mismatch && <p className="mt-1.5 text-[10px] text-[var(--nexus-error)]">Passwords don&apos;t match</p>}
          </Field>

          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-[color-mix(in_srgb,var(--nexus-error)_40%,transparent)] bg-[color-mix(in_srgb,var(--nexus-error)_10%,transparent)] p-3 text-xs text-[var(--nexus-error)]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
              {error}
            </div>
          )}

          <button type="submit" disabled={!canSubmit || saving} className={primaryBtn}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Lock className="h-4 w-4" />}
            {hasPassword ? "Change password" : "Set password"}
          </button>
        </form>
      </Card>

      <div className="mt-4 flex items-start gap-2 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface-2)] p-3 text-xs text-[var(--muted-foreground)]">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p>
          Passwords are hashed with Argon2id and never stored in readable form. Changing yours
          immediately signs out every other device by revoking their refresh tokens.
        </p>
      </div>
    </div>
  );
}

function AppearanceTab() {
  const { theme, setTheme } = useThemeStore();
  return (
    <div>
      <TabHeader title="Appearance" description="Applies across the whole app and follows you to any device you sign in on." />
      <Card title="Theme">
        <div className="flex gap-2 max-w-sm">
          <button
            onClick={() => setTheme("light")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition",
              theme === "light"
                ? "border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] text-[var(--foreground)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)]"
            )}
          >
            <Sun className="h-4 w-4" /> Light
          </button>
          <button
            onClick={() => setTheme("dark")}
            className={cn(
              "flex flex-1 items-center justify-center gap-2 rounded-lg border px-3 py-2.5 text-sm transition",
              theme === "dark"
                ? "border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)] text-[var(--foreground)]"
                : "border-[var(--nexus-border)] text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)]"
            )}
          >
            <Moon className="h-4 w-4" /> Dark
          </button>
        </div>
      </Card>
    </div>
  );
}

function ConnectionsTab() {
  const { user } = useAuthStore();
  const [githubConnected, setGithubConnected] = useState<boolean | null>(null);
  const [githubLogin, setGithubLogin] = useState<string | null>(null);
  const [githubBusy, setGithubBusy] = useState(false);

  useEffect(() => { refreshGithub(); }, []);

  async function refreshGithub() {
    try {
      const status = await api.github.status();
      setGithubConnected(status.connected);
      setGithubLogin(status.githubLogin);
    } catch {
      setGithubConnected(null);
    }
  }

  async function connectGithub() {
    setGithubBusy(true);
    try {
      const { url } = await api.github.authorizeUrl();
      window.location.href = url;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't start GitHub connect");
      setGithubBusy(false);
    }
  }

  async function disconnectGithub() {
    setGithubBusy(true);
    try {
      await api.github.disconnect();
      setGithubConnected(false);
      setGithubLogin(null);
      toast.success("GitHub disconnected");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't disconnect GitHub");
    } finally {
      setGithubBusy(false);
    }
  }

  return (
    <div>
      <TabHeader title="Connections" description="Link external accounts used by the Review phase." />
      <Card
        title="GitHub"
        description="Grants repo access so Nexus can create a repository and push a session's workspace to it."
      >
        {githubConnected === null ? (
          <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Checking connection…
          </div>
        ) : githubConnected ? (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-sm text-[var(--foreground)]">
              <ShieldCheck className="h-4 w-4 text-[var(--nexus-success)]" />
              Connected as <span className="font-medium">{githubLogin}</span>
            </div>
            <button onClick={disconnectGithub} disabled={githubBusy} className={cn(ghostBtn, "hover:border-[color-mix(in_srgb,var(--nexus-amber)_50%,transparent)] hover:text-[var(--mode-problem-text)]")}>
              {githubBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Unlink className="h-3.5 w-3.5" />}
              Disconnect
            </button>
          </div>
        ) : (
          <button onClick={connectGithub} disabled={githubBusy} className={primaryBtn}>
            {githubBusy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Github className="h-4 w-4" />}
            Connect GitHub
          </button>
        )}

        {user?.githubUsername && !githubConnected && (
          <p className="mt-3 text-[11px] text-[var(--muted-foreground)]">
            You sign in with GitHub as <span className="font-medium">{user.githubUsername}</span>. Pushing code
            needs the broader repo permission above, which sign-in deliberately does not request.
          </p>
        )}
      </Card>
    </div>
  );
}

/**
 * The unlock prompt shown before API keys are revealed. This is the visible
 * half of the protection -- the enforcing half is server-side (every
 * credential route answers 403 SUDO_REQUIRED without a live elevation), so
 * this screen is a courtesy, not the lock itself.
 */
function SudoGate({ onUnlocked }: { onUnlocked: () => void }) {
  const { user } = useAuthStore();
  const unlock = useSudoStore((s) => s.unlock);
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const noPassword = user?.hasPassword === false;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const { token, expiresInMinutes } = await api.auth.sudo(password);
      unlock(token, expiresInMinutes);
      setPassword("");
      onUnlocked();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't confirm your password");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <TabHeader title="API Keys" description="Protected area — confirm it's you before these are shown." />
      <Card>
        <div className="flex flex-col items-center text-center py-4">
          <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]">
            <Lock className="h-5 w-5 text-[var(--mode-dev-text)]" />
          </div>
          <h2 className="text-base font-semibold text-[var(--foreground)]">Confirm your password</h2>
          <p className="mt-1 mb-5 max-w-sm text-sm text-[var(--muted-foreground)]">
            Being signed in isn&apos;t enough to view or change provider keys. Re-enter your
            password to unlock this section for a few minutes.
          </p>

          {noPassword ? (
            <div className="flex items-start gap-2 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface-2)] p-3 text-left text-xs text-[var(--muted-foreground)]">
              <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[var(--nexus-amber)]" />
              <p>
                This account signs in with GitHub and has no password yet. Set one under{" "}
                <span className="font-medium text-[var(--foreground)]">Security</span>, then come back here.
              </p>
            </div>
          ) : (
            <form onSubmit={submit} className="w-full max-w-sm space-y-3">
              <div className="relative">
                <input
                  type={show ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoFocus
                  autoComplete="current-password"
                  placeholder="Your password"
                  className={cn(inputCls, "pr-9 text-center")}
                />
                <button
                  type="button"
                  onClick={() => setShow((v) => !v)}
                  tabIndex={-1}
                  aria-label={show ? "Hide password" : "Show password"}
                  className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--muted-foreground)] transition hover:text-[var(--foreground)]"
                >
                  {show ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
                </button>
              </div>

              {error && (
                <div className="flex items-start gap-2 rounded-lg border border-[color-mix(in_srgb,var(--nexus-error)_40%,transparent)] bg-[color-mix(in_srgb,var(--nexus-error)_10%,transparent)] p-2.5 text-left text-xs text-[var(--nexus-error)]">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  {error}
                </div>
              )}

              <button type="submit" disabled={busy || !password} className={cn(primaryBtn, "w-full justify-center")}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Unlock className="h-4 w-4" />}
                Unlock
              </button>
            </form>
          )}
        </div>
      </Card>
    </div>
  );
}

function ApiKeysTab() {
  const isUnlocked = useSudoStore((s) => s.isUnlocked);
  const expiresAt = useSudoStore((s) => s.expiresAt);
  const lock = useSudoStore((s) => s.lock);
  // Re-render on unlock/expiry rather than reading the store imperatively.
  const [unlocked, setUnlocked] = useState(() => isUnlocked());

  const [credentials, setCredentials] = useState<Credential[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(false);
  const [inputs, setInputs] = useState<Record<string, string>>({});
  const [busyProvider, setBusyProvider] = useState<string | null>(null);

  // Re-lock the moment the elevation lapses, so the screen can't sit there
  // showing keys backed by a token the server would now reject.
  useEffect(() => {
    if (!unlocked || !expiresAt) return;
    const ms = expiresAt - Date.now();
    if (ms <= 0) {
      relock();
      return;
    }
    const timer = setTimeout(relock, ms);
    return () => clearTimeout(timer);
  }, [unlocked, expiresAt]);

  useEffect(() => {
    if (unlocked) refreshKeys();
  }, [unlocked]);

  function relock() {
    lock();
    setUnlocked(false);
    setCredentials([]);
    setInputs({});
  }

  /** A 403 means the server no longer accepts our elevation -- drop back to
   *  the gate instead of leaving a dead screen up. */
  function handleSudoExpiry(err: unknown): boolean {
    if (err instanceof ApiError && err.status === 403) {
      relock();
      toast.info("Confirmation expired — please confirm your password again.");
      return true;
    }
    return false;
  }

  if (!unlocked) {
    return <SudoGate onUnlocked={() => setUnlocked(true)} />;
  }

  async function refreshKeys() {
    setLoadingKeys(true);
    try {
      const { credentials } = await api.credentials.list();
      setCredentials(credentials);
    } catch (err) {
      if (handleSudoExpiry(err)) return;
      if (!(err instanceof ApiError && err.status === 401)) {
        toast.error("Couldn't load your configured models");
      }
    } finally {
      setLoadingKeys(false);
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
      if (handleSudoExpiry(err)) return;
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
      if (handleSudoExpiry(err)) return;
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
      if (handleSudoExpiry(err)) return;
      toast.error(err instanceof Error ? err.message : "Failed to remove key");
    } finally {
      setBusyProvider(null);
    }
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold text-[var(--foreground)]">API Keys</h1>
          <p className="mt-1 text-sm text-[var(--muted-foreground)]">
            Bring your own provider keys to unlock each model. Encrypted at rest, never shown again after saving.
          </p>
        </div>
        <button
          onClick={relock}
          className={cn(ghostBtn, "shrink-0")}
          title="Lock this section now"
        >
          <Lock className="h-3.5 w-3.5" />
          Lock
        </button>
      </div>

      <div className="mb-4 flex items-center gap-2 rounded-lg border border-[color-mix(in_srgb,var(--nexus-success)_30%,transparent)] bg-[color-mix(in_srgb,var(--nexus-success)_10%,transparent)] px-3 py-2 text-xs text-[var(--muted-foreground)]">
        <Unlock className="h-3.5 w-3.5 shrink-0 text-[var(--nexus-success)]" />
        <span>
          Unlocked{expiresAt ? ` — re-locks ${new Date(expiresAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}` : ""}
        </span>
      </div>

      {loadingKeys && credentials.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-[var(--muted-foreground)]">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-4">
          {PROVIDER_ORDER.map((provider) => {
            const meta = PROVIDER_META[provider];
            const existing = credentials.find((c) => c.provider === provider);
            const busy = busyProvider === provider;

            return (
              <div key={provider} className="rounded-xl border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/40 p-4">
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
                      <button onClick={() => revalidate(provider)} disabled={busy} className={ghostBtn}>
                        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Re-check"}
                      </button>
                      <button
                        onClick={() => removeKey(provider)}
                        disabled={busy}
                        className="rounded-md border border-[var(--nexus-border)] p-2 text-[var(--muted-foreground)] transition hover:border-[color-mix(in_srgb,var(--nexus-amber)_50%,transparent)] hover:text-[var(--mode-problem-text)] disabled:opacity-50"
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
                      className={cn(inputCls, "font-mono placeholder:font-sans")}
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
      )}
      <div className="mt-5 flex items-start gap-2 rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-surface-2)] p-3 text-xs text-[var(--muted-foreground)]">
        <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <p>
          Keys are encrypted at rest and only decrypted in memory when a request is made — no
          route ever returns your raw key back, including this screen after you save it.
        </p>
      </div>
    </div>
  );
}

function AccountTab() {
  const { tenant, user } = useAuthStore();
  return (
    <div>
      <TabHeader title="Account" description="Workspace and session." />
      <div className="space-y-4">
        <Card title="Workspace">
          <dl className="space-y-2.5 text-sm">
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[var(--muted-foreground)]">Name</dt>
              <dd className="text-[var(--foreground)]">{tenant?.name ?? "—"}</dd>
            </div>
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[var(--muted-foreground)]">Plan</dt>
              <dd className="text-[var(--foreground)] capitalize">{tenant?.plan ?? "free"}</dd>
            </div>
            {tenant?.tokenBudget != null && (
              <div className="flex items-center justify-between gap-3">
                <dt className="text-[var(--muted-foreground)]">Token budget</dt>
                <dd className="text-[var(--foreground)] tabular-nums">{(tenant.tokenBudget / 1000).toFixed(0)}k / month</dd>
              </div>
            )}
            <div className="flex items-center justify-between gap-3">
              <dt className="text-[var(--muted-foreground)]">Signed in as</dt>
              <dd className="truncate text-[var(--foreground)]">{user?.email}</dd>
            </div>
          </dl>
        </Card>

        <Card title="Session">
          <button
            onClick={() => window.dispatchEvent(new Event("nexus:logout"))}
            className="flex items-center gap-2 rounded-lg border border-[var(--nexus-border)] px-4 py-2.5 text-sm text-[var(--muted-foreground)] transition hover:border-[color-mix(in_srgb,var(--nexus-amber)_50%,transparent)] hover:text-[var(--mode-problem-text)]"
          >
            <LogOut className="h-4 w-4" />
            Sign out
          </button>
        </Card>
      </div>
    </div>
  );
}