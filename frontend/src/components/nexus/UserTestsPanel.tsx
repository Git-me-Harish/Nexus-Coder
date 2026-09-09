"use client";

import { useState } from "react";
import { FlaskConical, Play, Check, X as XIcon, RefreshCw } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";

interface RunRecord {
  id: string;
  name: string;
  filePath: string;
  passed: boolean;
  exitCode: number;
  output: string;
}

/**
 * The Debug phase's "you can write test cases too" affordance --
 * POST /sessions/{id}/tests writes the code to the workspace and runs it
 * for real in the same sandbox the agent's own run_command uses (see
 * backend/app/api/v1/routes/tests.py). Nothing here is simulated: a
 * passing/failing result is the actual pytest exit code.
 */
export default function UserTestsPanel() {
  const { activeSession } = useAppStore();
  const [name, setName] = useState("");
  const [code, setCode] = useState("def test_example():\n    assert True\n");
  const [running, setRunning] = useState(false);
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [expanded, setExpanded] = useState<string | null>(null);

  if (!activeSession) return null;

  async function run() {
    if (!activeSession || !name.trim() || !code.trim() || running) return;
    setRunning(true);
    try {
      const { result } = await api.tests.run(activeSession.id, name.trim(), code);
      const record: RunRecord = { id: `${Date.now()}`, name: name.trim(), ...result };
      setRuns((r) => [record, ...r]);
      setExpanded(record.id);
    } catch (e: any) {
      setRuns((r) => [
        { id: `${Date.now()}`, name: name.trim(), filePath: "", passed: false, exitCode: -1, output: e?.message ?? "Failed to run" },
        ...r,
      ]);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]/60">
        <h3 className="text-sm font-semibold text-[var(--foreground)]">Your Test Cases</h3>
        <p className="text-[11px] text-[var(--muted-foreground)]">Write a pytest test and run it for real, alongside the agent's own.</p>
      </div>

      <div className="px-3 py-3 border-b border-[var(--nexus-border)]/60 space-y-2">
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Test name, e.g. 'negative numbers'"
          className="w-full px-2.5 py-1.5 rounded-md bg-[var(--nexus-surface)] border border-[var(--nexus-border)] text-xs text-[var(--foreground)] placeholder:text-[var(--muted-foreground)]"
        />
        <textarea
          value={code}
          onChange={(e) => setCode(e.target.value)}
          rows={6}
          spellCheck={false}
          className="w-full px-2.5 py-2 rounded-md bg-[var(--nexus-surface)] border border-[var(--nexus-border)] font-mono text-[11px] text-[var(--foreground)] resize-none"
        />
        <button
          onClick={run}
          disabled={running || !name.trim() || !code.trim()}
          className="w-full flex items-center justify-center gap-1.5 rounded-md bg-[var(--nexus-purple)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-40"
        >
          {running ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          {running ? "Running…" : "Run test"}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-2 space-y-1.5">
        {runs.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
            <FlaskConical className="w-6 h-6 mx-auto mb-2 opacity-40" />
            No test runs yet.
          </div>
        )}
        {runs.map((r) => (
          <div key={r.id} className="rounded-md border border-[var(--nexus-border)] bg-[var(--nexus-surface)]/50 text-xs">
            <button
              onClick={() => setExpanded(expanded === r.id ? null : r.id)}
              className="flex w-full items-center gap-2 px-2.5 py-2 text-left hover:bg-[var(--nexus-surface-2)] transition"
            >
              {r.passed ? (
                <Check className="w-3.5 h-3.5 shrink-0 text-[var(--nexus-success)]" />
              ) : (
                <XIcon className="w-3.5 h-3.5 shrink-0 text-[var(--nexus-error)]" />
              )}
              <span className="truncate font-medium text-[var(--foreground)]">{r.name}</span>
              <span className={cn("ml-auto shrink-0 text-[10px]", r.passed ? "text-[var(--nexus-success)]" : "text-[var(--nexus-error)]")}>
                {r.passed ? "passed" : "failed"}
              </span>
            </button>
            {expanded === r.id && (
              <pre className="max-h-56 overflow-auto whitespace-pre-wrap break-words border-t border-[var(--nexus-border)] px-2.5 py-1.5 font-mono text-[10px] leading-relaxed text-[var(--muted-foreground)]">
                {r.output}
              </pre>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
