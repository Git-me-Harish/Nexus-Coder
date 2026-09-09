"use client";

import { Menu, X, ChevronsLeft, ChevronsRight, FolderGit2, Plus, LogOut } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { useAuthStore } from "@/stores/authStore";
import Sidebar from "./Sidebar";
import Wordmark from "./Wordmark";
import Avatar from "./Avatar";
import { navigate } from "@/hooks/use-hash-router";
import { cn } from "@/lib/utils";

export default function ResponsiveSidebar() {
  const { mobileSidebarOpen, setMobileSidebarOpen, sidebarCollapsed, setSidebarCollapsed } = useAppStore();

  return (
    <>
      {/* Desktop sidebar — static, in-flow. Collapsed renders a compact
          icon-only rail instead of threading a `collapsed` prop through
          Sidebar's ~600 lines of interactive project/session UI (dropdowns,
          inline rename, delete confirmation) -- same visible outcome, far
          smaller surface for that state to leak into. */}
      <aside
        className={cn(
          "hidden md:flex shrink-0 h-screen sticky top-0 bg-[var(--nexus-surface)]/95 border-r border-[var(--nexus-border)] backdrop-blur-xl transition-[width] duration-150",
          sidebarCollapsed ? "w-[68px]" : "w-[260px]"
        )}
      >
        {sidebarCollapsed ? (
          <CollapsedRail onExpand={() => setSidebarCollapsed(false)} />
        ) : (
          <div className="w-full min-w-0 h-full flex flex-col">
            <div className="flex-1 min-h-0">
              <Sidebar />
            </div>
            <button
              onClick={() => setSidebarCollapsed(true)}
              className="mx-3 mb-3 flex items-center gap-2 rounded-lg border border-[var(--nexus-border)] px-3 py-1.5 text-xs text-[var(--muted-foreground)] transition hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)]"
              aria-label="Collapse sidebar"
            >
              <ChevronsLeft className="h-3.5 w-3.5" />
              Collapse
            </button>
          </div>
        )}
      </aside>

      {/* Mobile drawer */}
      {mobileSidebarOpen && (
        <div className="md:hidden fixed inset-0 z-50 flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm nexus-fade-in"
            onClick={() => setMobileSidebarOpen(false)}
          />
          {/* Drawer */}
          <aside className="relative w-[280px] max-w-[80vw] h-full bg-[var(--nexus-surface)] border-r border-[var(--nexus-border)] nexus-drawer-enter safe-bottom">
            <button
              onClick={() => setMobileSidebarOpen(false)}
              className="absolute top-3 right-3 z-10 p-1.5 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)]"
              aria-label="Close sidebar"
            >
              <X className="w-4 h-4" />
            </button>
            <Sidebar onNavigate={() => setMobileSidebarOpen(false)} />
          </aside>
        </div>
      )}
    </>
  );
}

function CollapsedRail({ onExpand }: { onExpand: () => void }) {
  const { projects, activeProject, setActiveSession, setSessions, setMessages, setFiles, setSpecs } = useAppStore();
  const { user } = useAuthStore();

  async function pickProject(p: (typeof projects)[number]) {
    // Mirrors Sidebar.pickProject's minimum viable path (load + enter dashboard);
    // full session picking/rename/etc. requires expanding the rail.
    setActiveSession(null);
    setMessages([]);
    setFiles([]);
    setSpecs([]);
    setSessions([]);
    useAppStore.setState({ activeProject: p });
    navigate("dashboard");
  }

  return (
    <div className="w-full h-full flex flex-col items-center py-4">
      <button
        onClick={() => navigate("dashboard")}
        className="mb-4 hover:opacity-80 transition"
        aria-label="Go to dashboard"
      >
        <Wordmark size="sm" className="[&>span]:hidden" />
      </button>

      <button
        onClick={onExpand}
        className="mb-3 p-2 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] transition"
        aria-label="Expand sidebar"
        title="Expand sidebar"
      >
        <ChevronsRight className="w-4 h-4" />
      </button>

      <button
        onClick={() => navigate("dashboard")}
        className="mb-3 p-2 rounded-lg bg-gradient-to-r from-[var(--nexus-purple)] to-[var(--nexus-purple-dim)] text-white hover:opacity-90 transition nexus-btn-glow"
        aria-label="New project"
        title="New project"
      >
        <Plus className="w-4 h-4" />
      </button>

      <div className="flex-1 min-h-0 w-full overflow-y-auto flex flex-col items-center gap-1 px-1.5">
        {projects.map((p) => (
          <button
            key={p.id}
            onClick={() => pickProject(p)}
            title={p.name}
            className={cn(
              "w-9 h-9 shrink-0 rounded-lg flex items-center justify-center transition",
              activeProject?.id === p.id
                ? "bg-[var(--nexus-surface-2)] text-[var(--foreground)]"
                : "text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface)] hover:text-[var(--foreground)]"
            )}
          >
            <FolderGit2 className="w-4 h-4" />
          </button>
        ))}
      </div>

      <button
        onClick={() => navigate("profile")}
        className="mt-3 rounded-full transition hover:opacity-90"
        aria-label="Profile & settings"
        title="Profile & settings"
      >
        <Avatar src={user?.avatarUrl} name={user?.name ?? user?.email} className="h-8 w-8" textClassName="text-[10px]" />
      </button>
      <button
        onClick={() => window.dispatchEvent(new Event("nexus:logout"))}
        className="mt-1 p-2 rounded-lg text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] transition"
        aria-label="Sign out"
        title="Sign out"
      >
        <LogOut className="w-4 h-4" />
      </button>
    </div>
  );
}

export function MobileSidebarTrigger() {
  const { setMobileSidebarOpen, mobileSidebarOpen } = useAppStore();
  return (
    <button
      onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
      className="md:hidden p-2 -ml-1 rounded-md text-[var(--muted-foreground)] hover:bg-[var(--nexus-surface-2)] hover:text-[var(--foreground)] transition"
      aria-label="Toggle sidebar"
    >
      <Menu className="w-5 h-5" />
    </button>
  );
}