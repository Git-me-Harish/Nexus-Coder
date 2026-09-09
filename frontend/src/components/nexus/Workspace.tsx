"use client";

import { useAppStore } from "@/stores/appStore";
import ResponsiveSidebar from "./ResponsiveSidebar";
import TopBar from "./TopBar";
import PhaseStepper from "./PhaseStepper";
import ChatPanel from "./ChatPanel";
import RightPanel from "./RightPanel";

export default function Workspace() {
  const { activeSession, rightPanel } = useAppStore();

  return (
    // h-screen (not min-h-screen) is load-bearing: it caps this container at
    // the viewport so ChatPanel's internal `flex-1 overflow-y-auto` message
    // list has a bounded box to scroll within. min-h-screen let this div
    // (and the whole document) grow past 100vh as messages accumulated, so
    // the BROWSER scrolled the page instead of just the message list --
    // dragging the input bar below the fold. Mirrors the h-screen pattern
    // ResponsiveSidebar/RightPanel already use correctly.
    <div className="flex h-screen overflow-hidden">
      <ResponsiveSidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <TopBar />
        {activeSession?.mode === "development" && <PhaseStepper />}
        <div className="flex-1 flex min-h-0">
          <ChatPanel />
          {rightPanel && <RightPanel />}
        </div>
      </div>
    </div>
  );
}
