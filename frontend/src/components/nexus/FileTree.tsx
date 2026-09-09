"use client";

import { useState } from "react";
import { FileText, Folder, ChevronRight, ChevronDown, Download, Github, RefreshCw, FileCode2, ExternalLink } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import { api } from "@/lib/nexus/client";
import { cn } from "@/lib/utils";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import { toast } from "sonner";

interface TreeNode {
  name: string;
  path: string;
  children?: TreeNode[];
  isFile?: boolean;
  language?: string;
}

function buildTree(files: { filePath: string; language?: string | null }[]): TreeNode {
  const root: TreeNode = { name: "root", path: "", children: [] };
  for (const f of files) {
    const parts = f.filePath.split("/").filter(Boolean);
    let cur = root;
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;
      const path = parts.slice(0, i + 1).join("/");
      let next = cur.children?.find((c) => c.name === part);
      if (!next) {
        next = { name: part, path, isFile, language: isFile ? f.language ?? undefined : undefined, children: isFile ? undefined : [] };
        cur.children?.push(next);
      }
      cur = next;
    }
  }
  // Sort: folders first, then alphabetical
  const sort = (n: TreeNode) => {
    if (n.children) {
      n.children.sort((a, b) => (a.isFile === b.isFile ? a.name.localeCompare(b.name) : a.isFile ? 1 : -1));
      n.children.forEach(sort);
    }
  };
  sort(root);
  return root;
}

export default function FileTree() {
  const { files, activeSession, updateActiveSession } = useAppStore();
  const [selected, setSelected] = useState<string | null>(files[0]?.filePath ?? null);
  const [expanded, setExpanded] = useState<Set<string>>(new Set([""]));
  const [exporting, setExporting] = useState(false);
  const [pushing, setPushing] = useState(false);

  if (!activeSession) return null;

  const tree = buildTree(files);
  const selectedFile = files.find((f) => f.filePath === selected);

  function toggle(path: string) {
    setExpanded((s) => {
      const next = new Set(s);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }

  /** Fetch-and-download rather than a plain <a href> -- the export endpoint
   *  requires the same bearer auth every other API call uses, and a bare
   *  navigation/anchor click can't attach an Authorization header. */
  async function exportZip() {
    if (!activeSession || exporting) return;
    setExporting(true);
    try {
      const res = await fetch(api.files.exportZipUrl(activeSession.id), {
        headers: { Authorization: `Bearer ${useAuthStore.getState().token ?? ""}` },
      });
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        throw new Error(body?.error?.message ?? `Export failed (HTTP ${res.status})`);
      }
      const blob = await res.blob();
      const disposition = res.headers.get("Content-Disposition") ?? "";
      const filename = disposition.match(/filename="([^"]+)"/)?.[1] ?? "project.zip";

      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
      toast.success(`Downloaded ${filename}`);
    } catch (e: any) {
      toast.error(e?.message ?? "Export failed");
    } finally {
      setExporting(false);
    }
  }

  async function pushGithub() {
    if (!activeSession || pushing) return;
    setPushing(true);
    try {
      const status = await api.github.status();
      if (!status.connected) {
        const { url } = await api.github.authorizeUrl();
        window.location.href = url;
        return;
      }
      toast.info("Pushing to GitHub…");
      const { repoUrl } = await api.github.push(activeSession.id);
      updateActiveSession({ githubRepoUrl: repoUrl });
      toast.success("Pushed to GitHub", {
        description: repoUrl,
        action: { label: "Open", onClick: () => window.open(repoUrl, "_blank") },
      });
    } catch (e: any) {
      toast.error(e?.message ?? "GitHub push failed");
    } finally {
      setPushing(false);
    }
  }

  return (
    <div className="h-full flex flex-col">
      <div className="px-4 py-3 border-b border-[var(--nexus-border)]/60 flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-[var(--foreground)]">File Tree</h3>
          <p className="text-[11px] text-[var(--muted-foreground)]">{files.length} files · sandbox: {activeSession.sandboxStatus ?? "none"}</p>
        </div>
        <div className="flex items-center gap-1">
          {activeSession.githubRepoUrl && (
            <button
              onClick={() => window.open(activeSession.githubRepoUrl!, "_blank")}
              className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:text-white hover:bg-[var(--nexus-surface-2)] transition"
              title="View on GitHub"
            >
              <ExternalLink className="w-3.5 h-3.5" />
            </button>
          )}
          <button
            onClick={exportZip}
            disabled={exporting || files.length === 0}
            className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:text-white hover:bg-[var(--nexus-surface-2)] transition disabled:opacity-30"
            title="Export ZIP"
          >
            {exporting ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
          </button>
          <button
            onClick={pushGithub}
            disabled={pushing || files.length === 0}
            className="p-1.5 rounded-md text-[var(--muted-foreground)] hover:text-white hover:bg-[var(--nexus-surface-2)] transition disabled:opacity-30"
            title={activeSession.githubRepoUrl ? "Push updates to GitHub" : "Push to GitHub"}
          >
            {pushing ? <RefreshCw className="w-3.5 h-3.5 animate-spin" /> : <Github className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      <div className="flex-1 flex flex-col min-h-0">
        {/* Tree */}
        <div className="px-2 py-2 overflow-y-auto max-h-[40%] border-b border-[var(--nexus-border)]/60">
          {files.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
              <FileCode2 className="w-6 h-6 mx-auto mb-2 opacity-40" />
              No files yet. Files appear as the Coder agent writes them in Implementation phase.
            </div>
          ) : (
            <TreeNodes nodes={tree.children ?? []} expanded={expanded} toggle={toggle} selected={selected} setSelected={setSelected} depth={0} />
          )}
        </div>

        {/* Selected file preview */}
        <div className="flex-1 min-h-0 overflow-auto">
          {selectedFile ? (
            <div className="h-full flex flex-col">
              <div className="px-3 py-2 border-b border-[var(--nexus-border)]/60 flex items-center justify-between bg-[var(--nexus-bg)]/60">
                <span className="text-[11px] font-mono text-[var(--muted-foreground)] truncate">{selectedFile.filePath}</span>
                <span className="text-[10px] text-[var(--muted-foreground)]">v{selectedFile.version}</span>
              </div>
              <SyntaxHighlighter
                language={selectedFile.language ?? "text"}
                style={vscDarkPlus}
                customStyle={{
                  margin: 0,
                  background: "var(--nexus-bg)",
                  fontSize: "12px",
                  padding: "12px 14px",
                  minHeight: "100%",
                }}
              >
                {selectedFile.content}
              </SyntaxHighlighter>
            </div>
          ) : (
            <div className="px-3 py-6 text-center text-xs text-[var(--muted-foreground)]">
              Select a file to preview.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function TreeNodes({
  nodes, expanded, toggle, selected, setSelected, depth,
}: {
  nodes: TreeNode[];
  expanded: Set<string>;
  toggle: (p: string) => void;
  selected: string | null;
  setSelected: (p: string) => void;
  depth: number;
}) {
  return (
    <>
      {nodes.map((n) => {
        const isExpanded = expanded.has(n.path);
        if (n.isFile) {
          return (
            <button
              key={n.path}
              onClick={() => setSelected(n.path)}
              className={cn(
                "w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-xs transition",
                selected === n.path ? "bg-[var(--nexus-purple)]/15 text-[var(--mode-dev-text)] border border-[var(--nexus-purple)]/30" : "text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] border border-transparent"
              )}
              style={{ paddingLeft: depth * 12 + 8 }}
            >
              <FileText className="w-3 h-3 opacity-60 shrink-0" />
              <span className="truncate">{n.name}</span>
            </button>
          );
        }
        return (
          <div key={n.path}>
            <button
              onClick={() => toggle(n.path)}
              className="w-full flex items-center gap-1.5 px-2 py-1 rounded-md text-xs text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] transition"
              style={{ paddingLeft: depth * 12 + 4 }}
            >
              {isExpanded ? <ChevronDown className="w-3 h-3 shrink-0" /> : <ChevronRight className="w-3 h-3 shrink-0" />}
              <Folder className="w-3 h-3 text-[var(--nexus-purple)]/70 shrink-0" />
              <span className="truncate">{n.name}</span>
            </button>
            {isExpanded && n.children && (
              <TreeNodes nodes={n.children} expanded={expanded} toggle={toggle} selected={selected} setSelected={setSelected} depth={depth + 1} />
            )}
          </div>
        );
      })}
    </>
  );
}
