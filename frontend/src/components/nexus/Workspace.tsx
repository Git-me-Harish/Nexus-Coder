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
    <div className="flex min-h-screen">
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
