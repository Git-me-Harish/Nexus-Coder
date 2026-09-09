"use client";

import { useState } from "react";
import { createPortal } from "react-dom";
import {
  Plus, FolderGit2, MessageSquare, GraduationCap, Settings,
  LogOut, ChevronRight, Sparkles, History, Search, MoreVertical,
  Star, Pin, Pencil, Trash2, X, Menu, Check,
} from "lucide-react";
import Wordmark from "./Wordmark";
import ModeBadge from "./ModeBadge";
import Avatar from "./Avatar";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore, type Session, type Project } from "@/stores/appStore";
import { navigate } from "@/hooks/use-hash-router";
import { cn } from "@/lib/utils";
import { ApiError, api } from "@/lib/nexus/client";
import { toast } from "sonner";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription,
  AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";

interface SidebarProps {
  /** On mobile, the sidebar is rendered inside a drawer; close handler */
  onNavigate?: () => void;
}

export default function Sidebar({ onNavigate }: SidebarProps) {
  const { user, tenant, clear } = useAuthStore();
  const {
    projects, activeProject, setActiveProject,
    sessions, activeSession, setActiveSession,
    setSessions, setMessages, setFiles, setSpecs,
    setProjects, updateProject, removeProject, updateSession, removeSession,
  } = useAppStore();

  const [showNew, setShowNew] = useState(false);
  const [newName, setNewName] = useState("");
  const [newMode, setNewMode] = useState<"development" | "problem_solving" | "learning">("development");
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [renameKind, setRenameKind] = useState<"project" | "session">("project");
  const [deleteTarget, setDeleteTarget] = useState<{ id: string; kind: "project" | "session"; name: string } | null>(null);

  async function loadSessions(projectId: string) {
    try {
      const { sessions: list } = await api.sessions.list(projectId);
      setSessions(sortSessions(list));
    } catch {
      setSessions([]);
    }
  }

  async function pickProject(p: Project) {
    setActiveProject(p);
    setActiveSession(null);
    setMessages([]);
    setFiles([]);
    setSpecs([]);
    if (p) await loadSessions(p.id);
    onNavigate?.();
  }

  async function pickSession(s: Session) {
    setActiveSession(s);
    try {
      const [{ session }, { messages }, { files }, { specs }] = await Promise.all([
        api.sessions.get(s.id),
        api.messages.list(s.id),
        api.files.list(s.id),
        api.spec.get(s.id),
      ]);
      setActiveSession(session);
      setMessages(messages);
      setFiles(files);
      setSpecs(specs);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return;
      console.error("Failed to load session", err);
    }
    // Sidebar history is available on the dashboard too, so selecting a
    // session must explicitly enter the workspace after loading its state.
    navigate("session");
    onNavigate?.();
  }

  async function createProject() {
    if (!newName.trim()) return;
    try {
      const { project } = await api.projects.create({ name: newName, mode: newMode });
      const { projects: ps } = await api.projects.list();
      setProjects(ps);
      setActiveProject(project);
      await loadSessions(project.id);
      const { session } = await api.sessions.create({
        projectId: project.id,
        mode: newMode,
        title: newName,
      });
      const { sessions: slist } = await api.sessions.list(project.id);
      setSessions(sortSessions(slist));
      await pickSession(session);
      setShowNew(false);
      setNewName("");
      navigate("session");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return;
      console.error(err);
    }
  }

  async function startNewSession() {
    if (!activeProject) return;
    try {
      const { session } = await api.sessions.create({
        projectId: activeProject.id,
        mode: activeProject.mode as any,
        title: `Session ${sessions.length + 1}`,
      });
      const { sessions: list } = await api.sessions.list(activeProject.id);
      setSessions(sortSessions(list));
      await pickSession(session);
    } catch (err) {
      console.error(err);
    }
  }

  // Project actions
  async function toggleProjectStar(p: Project, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const { project } = await api.projects.update(p.id, { starred: !p.starred });
      updateProject(p.id, { starred: project.starred });
      const { projects: ps } = await api.projects.list();
      setProjects(sortProjects(ps));
    } catch { toast.error("Failed to update project"); }
  }

  async function toggleProjectPin(p: Project, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const { project } = await api.projects.update(p.id, { pinned: !p.pinned });
      updateProject(p.id, { pinned: project.pinned });
      const { projects: ps } = await api.projects.list();
      setProjects(sortProjects(ps));
    } catch { toast.error("Failed to update project"); }
  }

  function startProjectRename(p: Project) {
    setRenamingId(p.id);
    setRenameKind("project");
    setRenameValue(p.name);
  }

  async function commitRename() {
    if (!renamingId || !renameValue.trim()) {
      setRenamingId(null);
      return;
    }
    try {
      if (renameKind === "project") {
        const { project } = await api.projects.update(renamingId, { name: renameValue.trim() });
        updateProject(renamingId, { name: project.name });
      } else {
        const { session } = await api.sessions.update(renamingId, { title: renameValue.trim() });
        updateSession(renamingId, { title: session.title });
      }
      toast.success("Renamed");
    } catch {
      toast.error("Failed to rename");
    } finally {
      setRenamingId(null);
      setRenameValue("");
    }
  }

  async function confirmDelete() {
    if (!deleteTarget) return;
    try {
      if (deleteTarget.kind === "project") {
        await api.projects.delete(deleteTarget.id);
        removeProject(deleteTarget.id);
        toast.success("Project deleted");
      } else {
        await api.sessions.delete(deleteTarget.id);
        removeSession(deleteTarget.id);
        toast.success("Session deleted");
      }
    } catch {
      toast.error("Failed to delete");
    } finally {
      setDeleteTarget(null);
    }
  }

  // Session actions
  async function toggleSessionStar(s: Session, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const { session } = await api.sessions.update(s.id, { starred: !s.starred });
      updateSession(s.id, { starred: session.starred });
      if (activeProject) {
        const { sessions: list } = await api.sessions.list(activeProject.id);
        setSessions(sortSessions(list));
      }
    } catch { toast.error("Failed to update session"); }
  }

  async function toggleSessionPin(s: Session, e: React.MouseEvent) {
    e.stopPropagation();
    try {
      const { session } = await api.sessions.update(s.id, { pinned: !s.pinned });
      updateSession(s.id, { pinned: session.pinned });
      if (activeProject) {
        const { sessions: list } = await api.sessions.list(activeProject.id);
        setSessions(sortSessions(list));
      }
    } catch { toast.error("Failed to update session"); }
  }

  function startSessionRename(s: Session) {
    setRenamingId(s.id);
    setRenameKind("session");
    setRenameValue(s.title ?? "");
  }

  // Sort: pinned first, then starred, then by updatedAt desc
  const sortedProjects = sortProjects(projects);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-4 py-4 border-b border-[var(--nexus-border)] flex items-center justify-between">
        <button
          onClick={() => { navigate("dashboard"); onNavigate?.(); }}
          className="flex items-center gap-2 hover:opacity-80 transition"
        >
          <Wordmark size="sm" />
        </button>
      </div>

      {/* New project */}
      <div className="px-3 py-3">
        <button
          onClick={() => setShowNew(true)}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] hover:opacity-90 text-white text-sm font-medium transition nexus-btn-glow"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">New Project</span>
          <span className="sm:hidden">New</span>
        </button>
      </div>

      {/* Projects list */}
      <div className="px-3 flex-1 overflow-y-auto">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-[var(--muted-foreground)] px-2 mb-1.5 mt-2">
          Projects
        </div>
        <div className="space-y-0.5">
          {sortedProjects.length === 0 && (
            <div className="px-2 py-2 text-xs text-[var(--muted-foreground)] italic">No projects yet</div>
          )}
          {sortedProjects.map((p) => {
            const isRenaming = renamingId === p.id && renameKind === "project";
            return (
              <div key={p.id}>
                {isRenaming ? (
                  <div className="flex items-center gap-1 px-1 py-1">
                    <input
                      type="text"
                      value={renameValue}
                      onChange={(e) => setRenameValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === "Enter") commitRename();
                        if (e.key === "Escape") setRenamingId(null);
                      }}
                      autoFocus
                      className="flex-1 px-2 py-1 text-sm bg-[var(--nexus-bg)] border border-[var(--nexus-purple)] rounded text-[var(--foreground)] focus:outline-none"
                    />
                    <button onClick={commitRename} className="p-1 rounded hover:bg-[var(--nexus-surface-2)]">
                      <Check className="w-3.5 h-3.5 text-[var(--nexus-success)]" />
                    </button>
                    <button onClick={() => setRenamingId(null)} className="p-1 rounded hover:bg-[var(--nexus-surface-2)]">
                      <X className="w-3.5 h-3.5 text-[var(--muted-foreground)]" />
                    </button>
                  </div>
                ) : (
                  <div className="group relative">
                    <button
                      onClick={() => pickProject(p)}
                      className={cn(
                        "w-full text-left px-2.5 py-2 pr-8 rounded-md text-sm transition flex items-center gap-2",
                        activeProject?.id === p.id
                          ? "bg-[var(--nexus-surface-2)] text-[var(--foreground)]"
                          : "text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface)] hover:text-[var(--foreground)]"
                      )}
                    >
                      <FolderGit2 className="w-3.5 h-3.5 opacity-70 shrink-0" />
                      <span className="truncate flex-1">{p.name}</span>
                      {p.pinned && <Pin className="w-3 h-3 text-[var(--nexus-purple)] fill-current shrink-0" />}
                      {p.starred && <Star className="w-3 h-3 text-[var(--nexus-amber)] fill-current shrink-0" />}
                      {activeProject?.id === p.id && (
                        <ChevronRight className="w-3.5 h-3.5 opacity-70 shrink-0" />
                      )}
                    </button>
                    {/* Hover quick actions */}
                    <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover:opacity-100 transition">
                      <button
                        onClick={(e) => toggleProjectStar(p, e)}
                        className={cn(
                          "p-1 rounded hover:bg-[var(--nexus-surface-2)]",
                          p.starred ? "text-[var(--nexus-amber)]" : "text-[var(--muted-foreground)]"
                        )}
                        title="Star"
                      >
                        <Star className={cn("w-3 h-3", p.starred && "fill-current")} />
                      </button>
                      <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                          <button
                            onClick={(e) => e.stopPropagation()}
                            className="p-1 rounded hover:bg-[var(--nexus-surface-2)] text-[var(--muted-foreground)]"
                            title="More"
                          >
                            <MoreVertical className="w-3 h-3" />
                          </button>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end" className="w-44">
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleProjectPin(p, e as any); }}>
                            <Pin className="w-3.5 h-3.5 mr-2" />
                            {p.pinned ? "Unpin" : "Pin"}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleProjectStar(p, e as any); }}>
                            <Star className={cn("w-3.5 h-3.5 mr-2", p.starred && "fill-current")} />
                            {p.starred ? "Unstar" : "Star"}
                          </DropdownMenuItem>
                          <DropdownMenuItem onClick={() => startProjectRename(p)}>
                            <Pencil className="w-3.5 h-3.5 mr-2" />
                            Rename
                          </DropdownMenuItem>
                          <DropdownMenuSeparator />
                          <DropdownMenuItem
                            className="text-[var(--nexus-error)] focus:text-[var(--nexus-error)]"
                            onClick={() => setDeleteTarget({ id: p.id, kind: "project", name: p.name })}
                          >
                            <Trash2 className="w-3.5 h-3.5 mr-2" />
                            Delete
                          </DropdownMenuItem>
                        </DropdownMenuContent>
                      </DropdownMenu>
                    </div>
                  </div>
                )}
                {activeProject?.id === p.id && sessions.length > 0 && (
                  <div className="ml-4 mt-0.5 space-y-0.5 border-l border-[var(--nexus-border)] pl-2">
                    {sessions.map((s) => {
                      const isSRenaming = renamingId === s.id && renameKind === "session";
                      if (isSRenaming) {
                        return (
                          <div key={s.id} className="flex items-center gap-1 px-1 py-1">
                            <input
                              type="text"
                              value={renameValue}
                              onChange={(e) => setRenameValue(e.target.value)}
                              onKeyDown={(e) => {
                                if (e.key === "Enter") commitRename();
                                if (e.key === "Escape") setRenamingId(null);
                              }}
                              autoFocus
                              className="flex-1 px-2 py-1 text-xs bg-[var(--nexus-bg)] border border-[var(--nexus-purple)] rounded text-[var(--foreground)] focus:outline-none"
                            />
                            <button onClick={commitRename} className="p-0.5 rounded hover:bg-[var(--nexus-surface-2)]">
                              <Check className="w-3 h-3 text-[var(--nexus-success)]" />
                            </button>
                            <button onClick={() => setRenamingId(null)} className="p-0.5 rounded hover:bg-[var(--nexus-surface-2)]">
                              <X className="w-3 h-3 text-[var(--muted-foreground)]" />
                            </button>
                          </div>
                        );
                      }
                      return (
                        <div key={s.id} className="group/s relative">
                          <button
                            onClick={() => pickSession(s)}
                            className={cn(
                              "w-full text-left px-2 py-1.5 pr-7 rounded-md text-xs transition flex items-center gap-2 border",
                              activeSession?.id === s.id
                                ? "bg-[color-mix(in_srgb,var(--nexus-purple)_15%,transparent)] text-[var(--mode-dev-text)] border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]"
                                : "text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface)] hover:text-[var(--foreground)] border-transparent"
                            )}
                          >
                            {s.mode === "development" ? <MessageSquare className="w-3 h-3 shrink-0" /> :
                             s.mode === "learning" ? <GraduationCap className="w-3 h-3 shrink-0" /> :
                             <Sparkles className="w-3 h-3 shrink-0" />}
                            <span className="truncate flex-1">{s.title ?? s.id.slice(0, 8)}</span>
                            {s.pinned && <Pin className="w-2.5 h-2.5 text-[var(--nexus-purple)] fill-current shrink-0" />}
                            {s.starred && <Star className="w-2.5 h-2.5 text-[var(--nexus-amber)] fill-current shrink-0" />}
                          </button>
                          <div className="absolute right-1 top-1/2 -translate-y-1/2 flex items-center opacity-0 group-hover/s:opacity-100 transition">
                            <button
                              onClick={(e) => toggleSessionStar(s, e)}
                              className={cn(
                                "p-0.5 rounded hover:bg-[var(--nexus-surface-2)]",
                                s.starred ? "text-[var(--nexus-amber)]" : "text-[var(--muted-foreground)]"
                              )}
                              title="Star"
                            >
                              <Star className={cn("w-2.5 h-2.5", s.starred && "fill-current")} />
                            </button>
                            <DropdownMenu>
                              <DropdownMenuTrigger asChild>
                                <button
                                  onClick={(e) => e.stopPropagation()}
                                  className="p-0.5 rounded hover:bg-[var(--nexus-surface-2)] text-[var(--muted-foreground)]"
                                  title="More"
                                >
                                  <MoreVertical className="w-2.5 h-2.5" />
                                </button>
                              </DropdownMenuTrigger>
                              <DropdownMenuContent align="end" className="w-40">
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleSessionPin(s, e as any); }}>
                                  <Pin className="w-3 h-3 mr-2" />
                                  {s.pinned ? "Unpin" : "Pin"}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={(e) => { e.stopPropagation(); toggleSessionStar(s, e as any); }}>
                                  <Star className={cn("w-3 h-3 mr-2", s.starred && "fill-current")} />
                                  {s.starred ? "Unstar" : "Star"}
                                </DropdownMenuItem>
                                <DropdownMenuItem onClick={() => startSessionRename(s)}>
                                  <Pencil className="w-3 h-3 mr-2" />
                                  Rename
                                </DropdownMenuItem>
                                <DropdownMenuSeparator />
                                <DropdownMenuItem
                                  className="text-[var(--nexus-error)] focus:text-[var(--nexus-error)]"
                                  onClick={() => setDeleteTarget({ id: s.id, kind: "session", name: s.title ?? s.id.slice(0, 8) })}
                                >
                                  <Trash2 className="w-3 h-3 mr-2" />
                                  Delete
                                </DropdownMenuItem>
                              </DropdownMenuContent>
                            </DropdownMenu>
                          </div>
                        </div>
                      );
                    })}
                    <button
                      onClick={startNewSession}
                      className="w-full text-left px-2 py-1.5 rounded-md text-xs text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--nexus-surface)] transition flex items-center gap-2"
                    >
                      <Plus className="w-3 h-3" />
                      New session
                    </button>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Upgrade promo */}
      <div className="m-3 p-3 rounded-xl bg-gradient-to-br from-[var(--nexus-surface-2)] to-[var(--nexus-surface)] border border-[var(--nexus-border)]">
        <div className="flex items-center gap-2 mb-1">
          <Sparkles className="w-3.5 h-3.5 text-[var(--nexus-purple)]" />
          <span className="text-xs font-semibold text-[var(--foreground)]">{tenant?.plan ?? "free"} plan</span>
        </div>
        <p className="text-[11px] text-[var(--muted-foreground)] leading-relaxed mb-2">
          {tenant?.plan === "pro" ? "You're on Pro — 50M tokens/mo." : "Upgrade for higher token limits & sandbox minutes."}
        </p>
        <button className="w-full text-xs px-2 py-1.5 rounded-md bg-[color-mix(in_srgb,var(--nexus-purple)_20%,transparent)] hover:bg-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] text-[var(--mode-dev-text)] border border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)] transition">
          Manage plan
        </button>
      </div>

      {/* User footer — click through to the full profile page (theme,
          API keys, GitHub connection all live there now, not a popup). */}
      <button
        onClick={() => { navigate("profile"); onNavigate?.(); }}
        className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-[var(--nexus-border)] px-3 py-2.5 text-left transition hover:bg-[var(--nexus-surface-2)]"
      >
        <Avatar src={user?.avatarUrl} name={user?.name ?? user?.email} className="w-8 h-8" textClassName="text-xs" />
        <div className="flex-1 min-w-0">
          <div className="text-xs font-medium text-[var(--foreground)] truncate">{user?.name ?? user?.email}</div>
          <div className="text-[10px] text-[var(--muted-foreground)] truncate">{user?.email}</div>
        </div>
        <Settings className="w-3.5 h-3.5 text-[var(--muted-foreground)] shrink-0" />
      </button>

      <button
        onClick={() => { window.dispatchEvent(new Event("nexus:logout")); }}
        className="mx-3 mb-3 flex items-center gap-2 rounded-lg px-3 py-1.5 text-xs text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
      >
        <LogOut className="w-3.5 h-3.5" />
        Sign out
      </button>

      {/* Keep this dialog at the document level: the desktop sidebar's backdrop
          filter otherwise traps fixed children inside the 260px column. */}
      {showNew && typeof document !== "undefined" && createPortal(
        <div
          className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-3 backdrop-blur-sm sm:p-6"
          onClick={() => setShowNew(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="new-project-title"
            className="nexus-glass w-full max-w-lg max-h-[calc(100dvh-1.5rem)] overflow-y-auto rounded-2xl p-4 shadow-2xl sm:max-h-[calc(100dvh-3rem)] sm:p-6"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-5 flex items-start justify-between gap-4">
              <div>
                <h2 id="new-project-title" className="text-lg font-semibold text-[var(--foreground)]">New Project</h2>
                <p className="mt-1 text-sm text-[var(--muted-foreground)]">Choose a name and workflow to get started.</p>
              </div>
              <button
                onClick={() => setShowNew(false)}
                className="rounded-md p-1.5 text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
                aria-label="Close new project dialog"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <input
              type="text"
              placeholder="Project name"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mb-4 w-full rounded-lg border border-[var(--nexus-border)] bg-[var(--nexus-bg)] px-3 py-2.5 text-sm text-[var(--foreground)] placeholder:text-[var(--muted-foreground)] focus:outline-none focus:ring-2 focus:ring-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)]"
              autoFocus
            />
            <div className="mb-5 space-y-2">
              {([
                { v: "development",     label: "Development",     desc: "Phase-gated build pipeline" },
                { v: "problem_solving", label: "Problem Solving", desc: "Open debate, decision doc" },
                { v: "learning",        label: "Learning",        desc: "Explain → Practice → Quiz" },
              ] as const).map((opt) => (
                <button
                  key={opt.v}
                  onClick={() => setNewMode(opt.v)}
                  className={cn(
                    "flex w-full items-start gap-3 rounded-lg border px-3 py-3 text-left transition",
                    newMode === opt.v
                      ? "border-[color-mix(in_srgb,var(--nexus-purple)_50%,transparent)] bg-[color-mix(in_srgb,var(--nexus-purple)_10%,transparent)]"
                      : "border-[var(--nexus-border)] hover:border-[color-mix(in_srgb,var(--nexus-purple)_30%,transparent)]"
                  )}
                >
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-medium text-[var(--foreground)]">{opt.label}</div>
                    <div className="text-xs text-[var(--muted-foreground)]">{opt.desc}</div>
                  </div>
                  <ModeBadge mode={opt.v} />
                </button>
              ))}
            </div>
            <div className="flex flex-col-reverse gap-2 sm:flex-row">
              <button
                onClick={() => setShowNew(false)}
                className="flex-1 rounded-lg border border-[var(--nexus-border)] px-3 py-2.5 text-sm text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)]"
              >
                Cancel
              </button>
              <button
                onClick={createProject}
                disabled={!newName.trim()}
                className="flex-1 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] px-3 py-2.5 text-sm text-white transition hover:opacity-90 disabled:opacity-40"
              >
                Create
              </button>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* Delete confirmation */}
      <AlertDialog open={!!deleteTarget} onOpenChange={(o) => !o && setDeleteTarget(null)}>
        <AlertDialogContent className="nexus-glass">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-[var(--foreground)]">Delete {deleteTarget?.kind}?</AlertDialogTitle>
            <AlertDialogDescription className="text-[var(--muted-foreground)]">
              <span className="font-medium text-[var(--foreground)]">{deleteTarget?.name}</span> will be permanently deleted.
              {deleteTarget?.kind === "project" && " All sessions, messages, and files inside this project will also be removed."}
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="border-[var(--nexus-border)] text-[var(--muted-foreground)]">Cancel</AlertDialogCancel>
            <AlertDialogAction
              onClick={confirmDelete}
              className="bg-[var(--nexus-error)] text-white hover:bg-[var(--nexus-error)]/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

// Sorting helpers
function sortProjects(list: Project[]): Project[] {
  return [...list].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    if (!!a.starred !== !!b.starred) return a.starred ? -1 : 1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}

function sortSessions(list: Session[]): Session[] {
  return [...list].sort((a, b) => {
    if (!!a.pinned !== !!b.pinned) return a.pinned ? -1 : 1;
    if (!!a.starred !== !!b.starred) return a.starred ? -1 : 1;
    return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime();
  });
}