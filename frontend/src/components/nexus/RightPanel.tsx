"use client";

import { X } from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import SpecBuilder from "./SpecBuilder";
import FileTree from "./FileTree";
import UsagePanel from "./UsagePanel";
import LearningPanel from "./LearningPanel";

export default function RightPanel() {
  const { activeSession, rightPanel, setRightPanel, mobileRightPanelOpen, setMobileRightPanelOpen } = useAppStore();

  if (!rightPanel) return null;

  const content = (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-end px-2 py-1 border-b border-[var(--nexus-border)]">
        <button
          onClick={() => {
            setRightPanel(null);
            setMobileRightPanelOpen(false);
          }}
          className="p-1 rounded-md text-[var(--muted-foreground)] hover:text-[var(--foreground)] hover:bg-[var(--nexus-surface-2)] transition"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      </div>
      <div className="flex-1 min-h-0">
        {rightPanel === "spec" && <SpecBuilder />}
        {rightPanel === "files" && <FileTree />}
        {rightPanel === "usage" && <UsagePanel />}
        {rightPanel === "learning" && <LearningPanel />}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop: static column */}
      <aside className="hidden lg:flex w-[360px] shrink-0 h-screen sticky top-0 bg-[var(--nexus-surface)]/95 border-l border-[var(--nexus-border)] backdrop-blur-xl">
        <div className="w-full">{content}</div>
      </aside>

      {/* Mobile/tablet: slide-over drawer */}
      {(mobileRightPanelOpen || (typeof window !== "undefined" && window.innerWidth >= 1024)) && (
        <div className="lg:hidden fixed inset-0 z-50 flex justify-end">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm nexus-fade-in"
            onClick={() => { setRightPanel(null); setMobileRightPanelOpen(false); }}
          />
          <aside className="relative w-[340px] max-w-[85vw] h-full bg-[var(--nexus-surface)] border-l border-[var(--nexus-border)] nexus-drawer-right-enter safe-bottom">
            {content}
          </aside>
        </div>
      )}
    </>
  );
}
