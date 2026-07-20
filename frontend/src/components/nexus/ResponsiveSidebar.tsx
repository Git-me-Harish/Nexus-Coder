"use client";

import { Menu, X } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import Sidebar from "./Sidebar";
import ModelConfigModal from "./ModelConfigModal";
import { cn } from "@/lib/utils";

export default function ResponsiveSidebar() {
  const { mobileSidebarOpen, setMobileSidebarOpen } = useAppStore();

  return (
    <>
      {/* Desktop sidebar — static, in-flow */}
      <aside className="hidden md:flex w-[260px] shrink-0 h-screen sticky top-0 bg-[var(--nexus-surface)]/95 border-r border-[var(--nexus-border)] backdrop-blur-xl">
        <div className="w-full">
          <Sidebar />
        </div>
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

      <ModelConfigModal />
    </>
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