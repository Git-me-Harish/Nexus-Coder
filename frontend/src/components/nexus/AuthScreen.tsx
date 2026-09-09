"use client";

import { useState } from "react";
import {
  ArrowRight, ArrowLeft, Loader2, ShieldCheck, GitBranch, Check, Cpu, Workflow,
  Eye, EyeOff, MailCheck, AlertTriangle,
} from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";
import { navigate } from "@/hooks/use-hash-router";
import { api } from "@/lib/nexus/client";
import ThemeToggle from "./ThemeToggle";
import { OutlineText } from "./OutlineText";
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

/**
 * Mirrors backend/app/schemas/auth.py's RegisterRequest.password_strength
 * validator (10-128 chars, must mix letters with numbers/symbols) so the
 * form can reject an invalid password before spending a round-trip on it.
 * Returns null when valid, otherwise the specific unmet requirement.
 */
function passwordIssue(pw: string): string | null {
  if (pw.length < 10) return "At least 10 characters";
  if (pw.length > 128) return "No more than 128 characters";
  if (/^\d+$/.test(pw)) return "Must include a letter, not just numbers";
  if (/^[a-zA-Z]+$/.test(pw)) return "Must include a number or symbol, not just letters";
  return null;
}

interface FieldErrors {
  email?: string;
  password?: string;
  confirmPassword?: string;
  terms?: string;
}

function BrandMark({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick} className="flex items-center gap-2 transition hover:opacity-80" aria-label="Go to Nexus home">
      <img src="/logo.png" alt="" aria-hidden="true" className="w-7 h-7 object-contain shrink-0" />
      <OutlineText className="!text-lg tracking-wide">NEXUS</OutlineText>
    </button>
  );
}

interface AuthScreenProps {
  /** Set when arriving from an emailed reset link (see app/page.tsx). `null`
   *  means the reset route was reached without one -- a bookmark, or a
   *  reload after the token was stripped from the URL. */
  resetToken?: string | null;
}

/** Which panel the left column is showing. `credentials` is the normal
 *  sign-in/create-account form; the rest are the password-recovery path. */
type Screen = "credentials" | "forgot" | "sent" | "reset";

export default function AuthScreen({ resetToken }: AuthScreenProps = {}) {
  const { setSession } = useAuthStore();
  const { setProjects } = useAppStore();
  const [screen, setScreen] = useState<Screen>(resetToken !== undefined ? "reset" : "credentials");
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [name, setName] = useState("");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [githubLoading, setGithubLoading] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [resetError, setResetError] = useState<string | null>(null);
  // Reported by the API so this never contradicts PASSWORD_RESET_TTL_MINUTES.
  const [resetTtlMinutes, setResetTtlMinutes] = useState(30);

  const pwIssue = mode === "register" ? passwordIssue(password) : null;

  /** Back to the sign-in form, clearing anything the recovery path collected. */
  function backToSignIn() {
    setScreen("credentials");
    setMode("login");
    setPassword("");
    setConfirmPassword("");
    setErrors({});
    setResetError(null);
    if (resetToken !== undefined) navigate("auth", { replace: true });
  }

  async function requestReset(e: React.FormEvent) {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const { expiresInMinutes } = await api.auth.forgotPassword(email.trim());
      if (expiresInMinutes) setResetTtlMinutes(expiresInMinutes);
      // The API deliberately doesn't say whether that address exists, so
      // neither does this screen.
      setScreen("sent");
    } catch (err: any) {
      toast.error(err?.message ?? "Couldn't send a reset link right now");
    } finally {
      setLoading(false);
    }
  }

  async function submitReset(e: React.FormEvent) {
    e.preventDefault();
    setResetError(null);

    const issue = passwordIssue(password);
    if (issue) {
      setErrors({ password: issue });
      return;
    }
    if (password !== confirmPassword) {
      setErrors({ confirmPassword: "Passwords don't match" });
      return;
    }
    setErrors({});

    if (!resetToken) {
      setResetError("This reset link is missing its token. Request a new link to try again.");
      return;
    }

    setLoading(true);
    try {
      // A successful reset revokes every prior session and returns a new one,
      // so the user lands straight in the app rather than signing in again.
      const result = await api.auth.resetPassword(resetToken, password);
      setSession({
        user: result.user,
        tenant: result.tenant,
        token: result.token,
        refreshToken: result.refreshToken,
      });
      toast.success("Password updated — you're signed in.");
      try {
        const { projects } = await api.projects.list();
        setProjects(projects);
      } catch {}
      navigate("dashboard", { replace: true });
    } catch (err: any) {
      setResetError(err?.message ?? "Couldn't reset your password.");
    } finally {
      setLoading(false);
    }
  }

  function validate(): boolean {
    const next: FieldErrors = {};
    if (mode === "register") {
      if (password && pwIssue) next.password = pwIssue;
      if (confirmPassword !== password) next.confirmPassword = "Passwords don't match";
      if (!agreedToTerms) next.terms = "You must accept the Terms and Privacy Policy";
    }
    setErrors(next);
    return Object.keys(next).length === 0;
  }

  /** Hands off to github.com; the callback comes back to app/page.tsx as
   *  ?auth=github&code=..., which exchanges it for a session. */
  async function continueWithGithub() {
    setGithubLoading(true);
    try {
      const { url } = await api.auth.githubAuthorizeUrl();
      window.location.href = url;
    } catch (err: any) {
      toast.error(err?.message ?? "Couldn't start GitHub sign-in");
      setGithubLoading(false);
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!validate()) return;
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
    <div className="ed-page min-h-screen flex relative">
      {/* Top bar -- wordmark (clickable to go back to landing) + theme toggle */}
      <div className="absolute top-4 left-4 z-20 sm:top-6 sm:left-8 lg:hidden">
        <BrandMark onClick={() => navigate("landing")} />
      </div>
      <div className="absolute top-4 sm:top-6 right-4 sm:right-8 z-20">
        <ThemeToggle compact />
      </div>

      {/* ─── Left: Auth form ──────────────────────────────────────────────── */}
      <div className="flex-1 lg:w-[44%] flex items-center justify-center p-4 sm:p-6 lg:p-8 order-2 lg:order-1">
        <div className="w-full max-w-md mt-12 lg:mt-0">
          {/* Mobile hero — hidden on lg+ where the right panel takes over */}
          <div className="text-center mb-6 lg:hidden">
            <div className="ed-label mb-2">Agentic Engineering Platform</div>
            <h1 className="text-2xl font-bold text-[var(--ed-fg)] tracking-tight mb-1">
              Your Principal Engineer
            </h1>
            <p className="text-xs text-[var(--ed-muted)]">
              Brainstorms, debates, plans, specifies — before code.
            </p>
          </div>

          {/* Desktop heading */}
          <div className="hidden lg:block mb-8">
            <div className="mb-5">
              <BrandMark onClick={() => navigate("landing")} />
            </div>
            <h2 className="text-3xl font-bold text-[var(--ed-fg)] tracking-tight mb-2">
              {screen === "forgot" ? "Reset your password"
                : screen === "sent" ? "Check your email"
                : screen === "reset" ? "Choose a new password"
                : mode === "login" ? "Welcome back"
                : "Create your account"}
            </h2>
            <p className="text-sm text-[var(--ed-muted)]">
              {screen === "forgot" ? "We'll email you a link to set a new one."
                : screen === "sent" ? `The link expires in ${resetTtlMinutes} minutes and can only be used once.`
                : screen === "reset" ? "Setting it signs you out everywhere else."
                : mode === "login" ? "Sign in to continue building with Nexus."
                : "Start shipping with a Principal Engineer in your browser."}
            </p>
          </div>

          {/* Auth card */}
          <div className="border ed-hairline p-5 sm:p-6">
            {screen === "forgot" && (
              <ForgotPanel
                email={email}
                setEmail={setEmail}
                loading={loading}
                onSubmit={requestReset}
                onBack={backToSignIn}
              />
            )}

            {screen === "sent" && (
              <SentPanel
                email={email}
                ttlMinutes={resetTtlMinutes}
                onBack={backToSignIn}
                onResend={() => setScreen("forgot")}
              />
            )}

            {screen === "reset" && (
              <ResetPanel
                token={resetToken ?? null}
                password={password}
                setPassword={setPassword}
                confirmPassword={confirmPassword}
                setConfirmPassword={setConfirmPassword}
                showPassword={showPassword}
                setShowPassword={setShowPassword}
                errors={errors}
                resetError={resetError}
                loading={loading}
                onSubmit={submitReset}
                onBack={backToSignIn}
              />
            )}

            {screen === "credentials" && (
              <>
            {/* Tab toggle */}
            <div className="flex mb-6 border-b ed-hairline">
              {(["login", "register"] as const).map((m) => (
                <button
                  key={m}
                  onClick={() => { setMode(m); setErrors({}); }}
                  className={`flex-1 pb-2.5 text-xs font-semibold uppercase tracking-wider transition border-b-2 -mb-px ${
                    mode === m
                      ? "text-[var(--ed-fg)] border-[var(--ed-accent)]"
                      : "text-[var(--ed-muted)] border-transparent hover:text-[var(--ed-fg)]"
                  }`}
                >
                  {m === "login" ? "Sign in" : "Create account"}
                </button>
              ))}
            </div>

            <form onSubmit={submit} className="space-y-4">
              {mode === "register" && (
                <div>
                  <label className="ed-label block mb-1.5">Name</label>
                  <input
                    type="text"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                    className="w-full px-3 py-2 bg-transparent border ed-hairline text-sm text-[var(--ed-fg)] placeholder:text-[var(--ed-muted)] focus:outline-none focus:border-[var(--ed-accent)]"
                    placeholder="Ada Lovelace"
                  />
                </div>
              )}
              <div>
                <label className="ed-label block mb-1.5">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="w-full px-3 py-2 bg-transparent border ed-hairline text-sm text-[var(--ed-fg)] placeholder:text-[var(--ed-muted)] focus:outline-none focus:border-[var(--ed-accent)]"
                  placeholder="you@company.com"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="ed-label">Password</label>
                  {mode === "login" && (
                    <button
                      type="button"
                      onClick={() => { setScreen("forgot"); setErrors({}); }}
                      className="text-[11px] text-[var(--ed-accent)] hover:underline"
                    >
                      Forgot password?
                    </button>
                  )}
                </div>
                <div className="relative">
                  <input
                    type={showPassword ? "text" : "password"}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    className={`w-full px-3 py-2 pr-9 bg-transparent border text-sm text-[var(--ed-fg)] placeholder:text-[var(--ed-muted)] focus:outline-none ${
                      errors.password ? "border-[var(--nexus-error)]" : "ed-hairline focus:border-[var(--ed-accent)]"
                    }`}
                    placeholder="••••••••"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((v) => !v)}
                    className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ed-muted)] hover:text-[var(--ed-fg)] transition"
                    tabIndex={-1}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                  </button>
                </div>
                {mode === "register" && (
                  <p className={`mt-1.5 text-[10px] ${password && !pwIssue ? "text-[var(--nexus-success)]" : "text-[var(--ed-muted)]"}`}>
                    {password && !pwIssue ? (
                      <span className="flex items-center gap-1"><Check className="w-3 h-3" /> Meets password requirements</span>
                    ) : (
                      "10+ characters, mixing letters with numbers or symbols"
                    )}
                  </p>
                )}
                {errors.password && <p className="mt-1.5 text-[10px] text-[var(--nexus-error)]">{errors.password}</p>}
              </div>

              {mode === "register" && (
                <div>
                  <label className="ed-label block mb-1.5">Confirm password</label>
                  <div className="relative">
                    <input
                      type={showConfirmPassword ? "text" : "password"}
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      required
                      className={`w-full px-3 py-2 pr-9 bg-transparent border text-sm text-[var(--ed-fg)] placeholder:text-[var(--ed-muted)] focus:outline-none ${
                        errors.confirmPassword ? "border-[var(--nexus-error)]" : "ed-hairline focus:border-[var(--ed-accent)]"
                      }`}
                      placeholder="••••••••"
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword((v) => !v)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ed-muted)] hover:text-[var(--ed-fg)] transition"
                      tabIndex={-1}
                      aria-label={showConfirmPassword ? "Hide password" : "Show password"}
                    >
                      {showConfirmPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                  </div>
                  {errors.confirmPassword && <p className="mt-1.5 text-[10px] text-[var(--nexus-error)]">{errors.confirmPassword}</p>}
                </div>
              )}

              {mode === "register" && (
                <div>
                  <label className="flex items-start gap-2 cursor-pointer select-none">
                    <input
                      type="checkbox"
                      checked={agreedToTerms}
                      onChange={(e) => setAgreedToTerms(e.target.checked)}
                      className="mt-0.5 w-3.5 h-3.5 border-[var(--ed-line)] text-[var(--ed-accent)] focus:ring-[var(--ed-accent)] shrink-0"
                    />
                    <span className="text-[11px] text-[var(--ed-muted)] leading-snug">
                      I agree to the{" "}
                      <button
                        type="button"
                        onClick={() => toast.info("Terms of Service — coming soon.")}
                        className="text-[var(--ed-accent)] hover:underline"
                      >
                        Terms of Service
                      </button>{" "}
                      and{" "}
                      <button
                        type="button"
                        onClick={() => toast.info("Privacy Policy — coming soon.")}
                        className="text-[var(--ed-accent)] hover:underline"
                      >
                        Privacy Policy
                      </button>
                    </span>
                  </label>
                  {errors.terms && <p className="mt-1.5 text-[10px] text-[var(--nexus-error)]">{errors.terms}</p>}
                </div>
              )}

              <button
                type="submit"
                disabled={loading}
                className="w-full py-2.5 rounded-full bg-[var(--ed-fg)] text-[var(--ed-bg)] text-xs font-semibold uppercase tracking-wider hover:opacity-85 transition flex items-center justify-center gap-2 disabled:opacity-50"
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

            <div className="my-5 flex items-center gap-2">
              <div className="flex-1 h-px bg-[var(--ed-line)]" />
              <span className="ed-label">or</span>
              <div className="flex-1 h-px bg-[var(--ed-line)]" />
            </div>

            <button
              onClick={continueWithGithub}
              disabled={githubLoading}
              className="w-full py-2.5 border ed-hairline text-sm font-medium text-[var(--ed-fg)] hover:bg-[var(--ed-surface)] transition flex items-center justify-center gap-2 disabled:opacity-50"
            >
              {githubLoading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z"/></svg>
              )}
              Continue with GitHub
            </button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ─── Right: Marketing showcase ────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-[56%] relative items-center justify-center p-8 overflow-hidden border-l ed-hairline order-1 lg:order-2">
        <div className="ed-grid-lines opacity-40">
          {Array.from({ length: 4 }).map((_, i) => <div key={i} />)}
        </div>

        {/* Content */}
        <div className="relative z-10 max-w-lg w-full">
          {/* Headline */}
          <div className="mb-8">
            <div className="ed-label mb-4">Agentic Engineering Platform</div>
            <h1 className="text-4xl xl:text-5xl font-bold text-[var(--ed-fg)] tracking-tight mb-4 leading-tight">
              Think like a Principal Engineer.
              <br />
              <span className="italic font-serif font-normal">Ship like a team.</span>
            </h1>
            <p className="text-base text-[var(--ed-muted)] leading-relaxed">
              Nexus brainstorms, debates, plans, and specifies before a single line of code is written.
              Three modes. Six phases. Twelve architectural dimensions. One intelligent agent.
            </p>
          </div>

          {/* Feature highlights */}
          <div className="space-y-3 mb-6 border-t ed-hairline pt-5">
            <FeatureLine icon={<Cpu className="w-4 h-4" />} text="7 models · intelligent phase-aware routing · mid-task switching" />
            <FeatureLine icon={<Workflow className="w-4 h-4" />} text="Orchestrator-Worker agents · Brainstormer → Coder → Reviewer" />
            <FeatureLine icon={<ShieldCheck className="w-4 h-4" />} text="Human-in-the-loop gate · spec must be confirmed before code" />
            <FeatureLine icon={<GitBranch className="w-4 h-4" />} text="Real file tree · live preview · ZIP export · GitHub push" />
          </div>

          {/* Terminal preview replaces the mode and stats cards. */}
          <div className="border-t ed-hairline pt-6">
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

const inputCls = "w-full px-3 py-2 bg-transparent border ed-hairline text-sm text-[var(--ed-fg)] placeholder:text-[var(--ed-muted)] focus:outline-none focus:border-[var(--ed-accent)]";
const submitCls = "w-full py-2.5 rounded-full bg-[var(--ed-fg)] text-[var(--ed-bg)] text-xs font-semibold uppercase tracking-wider hover:opacity-85 transition flex items-center justify-center gap-2 disabled:opacity-50";
const backCls = "w-full flex items-center justify-center gap-1.5 text-xs text-[var(--ed-muted)] hover:text-[var(--ed-fg)] transition";

/** Step 1: ask for the address. */
function ForgotPanel({
  email, setEmail, loading, onSubmit, onBack,
}: {
  email: string;
  setEmail: (v: string) => void;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onBack: () => void;
}) {
  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <p className="text-sm text-[var(--ed-muted)] lg:hidden">
        Enter your email and we&apos;ll send a link to set a new password.
      </p>
      <div>
        <label className="ed-label block mb-1.5">Email</label>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          autoFocus
          autoComplete="email"
          className={inputCls}
          placeholder="you@company.com"
        />
      </div>
      <button type="submit" disabled={loading || !email.trim()} className={submitCls}>
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Send reset link <ArrowRight className="w-4 h-4" /></>}
      </button>
      <button type="button" onClick={onBack} className={backCls}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
      </button>
    </form>
  );
}

/** Step 2: confirmation. Worded to match what the API actually promises --
 *  it never says whether that address has an account, so neither can this. */
function SentPanel({ email, ttlMinutes, onBack, onResend }: { email: string; ttlMinutes: number; onBack: () => void; onResend: () => void }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="w-9 h-9 shrink-0 border ed-hairline flex items-center justify-center text-[var(--ed-accent)]">
          <MailCheck className="w-4 h-4" />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-[var(--ed-fg)]">
            If an account exists for <span className="font-medium break-all">{email}</span>, a reset link is on its way.
          </p>
          <p className="mt-1.5 text-xs text-[var(--ed-muted)]">
            It expires in {ttlMinutes} minutes and works once. Check your spam folder if it doesn&apos;t arrive.
          </p>
        </div>
      </div>
      <button type="button" onClick={onResend} className="w-full py-2.5 border ed-hairline text-sm font-medium text-[var(--ed-fg)] hover:bg-[var(--ed-surface)] transition">
        Use a different email
      </button>
      <button type="button" onClick={onBack} className={backCls}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
      </button>
    </div>
  );
}

/** Step 3: reached from the emailed link. */
function ResetPanel({
  token, password, setPassword, confirmPassword, setConfirmPassword,
  showPassword, setShowPassword, errors, resetError, loading, onSubmit, onBack,
}: {
  token: string | null;
  password: string;
  setPassword: (v: string) => void;
  confirmPassword: string;
  setConfirmPassword: (v: string) => void;
  showPassword: boolean;
  setShowPassword: (fn: (v: boolean) => boolean) => void;
  errors: FieldErrors;
  resetError: string | null;
  loading: boolean;
  onSubmit: (e: React.FormEvent) => void;
  onBack: () => void;
}) {
  const issue = password ? passwordIssue(password) : null;

  // No token at all -- a bookmarked #/reset-password, or a reload after the
  // token was stripped from the URL. Say so instead of showing a form that
  // cannot possibly succeed.
  if (!token) {
    return (
      <div className="space-y-4">
        <div className="flex items-start gap-2 border ed-hairline p-3 text-xs text-[var(--ed-muted)]">
          <AlertTriangle className="mt-0.5 w-3.5 h-3.5 shrink-0 text-[var(--nexus-amber)]" />
          <p>
            This page needs a reset link to work. Open the most recent link from your email,
            or request a new one — links expire after a short while and can only be used once.
          </p>
        </div>
        <button type="button" onClick={onBack} className={submitCls}>
          Back to sign in
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} className="space-y-4">
      <div>
        <label className="ed-label block mb-1.5">New password</label>
        <div className="relative">
          <input
            type={showPassword ? "text" : "password"}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            autoFocus
            autoComplete="new-password"
            className={`${inputCls} pr-9 ${errors.password ? "!border-[var(--nexus-error)]" : ""}`}
            placeholder="••••••••"
          />
          <button
            type="button"
            onClick={() => setShowPassword((v) => !v)}
            tabIndex={-1}
            aria-label={showPassword ? "Hide password" : "Show password"}
            className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--ed-muted)] hover:text-[var(--ed-fg)] transition"
          >
            {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
          </button>
        </div>
        <p className={`mt-1.5 text-[10px] ${password && !issue ? "text-[var(--nexus-success)]" : "text-[var(--ed-muted)]"}`}>
          {password && !issue ? (
            <span className="flex items-center gap-1"><Check className="w-3 h-3" /> Meets password requirements</span>
          ) : (
            issue ?? "10+ characters, mixing letters with numbers or symbols"
          )}
        </p>
        {errors.password && <p className="mt-1 text-[10px] text-[var(--nexus-error)]">{errors.password}</p>}
      </div>

      <div>
        <label className="ed-label block mb-1.5">Confirm new password</label>
        <input
          type={showPassword ? "text" : "password"}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          autoComplete="new-password"
          className={`${inputCls} ${errors.confirmPassword ? "!border-[var(--nexus-error)]" : ""}`}
          placeholder="••••••••"
        />
        {errors.confirmPassword && <p className="mt-1 text-[10px] text-[var(--nexus-error)]">{errors.confirmPassword}</p>}
      </div>

      {resetError && (
        <div className="flex items-start gap-2 border border-[var(--nexus-error)] p-3 text-xs text-[var(--nexus-error)]">
          <AlertTriangle className="mt-0.5 w-3.5 h-3.5 shrink-0" />
          {resetError}
        </div>
      )}

      <button type="submit" disabled={loading} className={submitCls}>
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <>Set new password <ArrowRight className="w-4 h-4" /></>}
      </button>
      <button type="button" onClick={onBack} className={backCls}>
        <ArrowLeft className="w-3.5 h-3.5" /> Back to sign in
      </button>
    </form>
  );
}

function FeatureLine({ icon, text }: { icon: React.ReactNode; text: string }) {
  return (
    <div className="flex items-start gap-2.5">
      <div className="w-6 h-6 border ed-hairline flex items-center justify-center shrink-0 mt-0.5 text-[var(--ed-accent)]">
        {icon}
      </div>
      <span className="text-sm text-[var(--ed-fg)] leading-relaxed">{text}</span>
    </div>
  );
}
