"use client";

import { Moon, Sun, Monitor } from "lucide-react";
import { useThemeStore } from "@/stores/themeStore";
import { cn } from "@/lib/utils";

interface Props {
  className?: string;
  compact?: boolean;
}

export default function ThemeToggle({ className, compact }: Props) {
  const { theme, toggle } = useThemeStore();
  const isDark = theme === "dark";

  return (
    <button
      onClick={toggle}
      className={cn(
        "inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-md border text-xs transition",
        "border-[var(--nexus-border)] bg-[var(--nexus-surface)] hover:bg-[var(--nexus-surface-2)]",
        "text-[var(--foreground)]",
        compact && "px-2 py-1.5",
        className
      )}
      title={isDark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label="Toggle theme"
    >
      {isDark ? <Sun className="w-3.5 h-3.5 text-[var(--nexus-amber)]" /> : <Moon className="w-3.5 h-3.5 text-[var(--nexus-purple)]" />}
      {!compact && <span>{isDark ? "Light" : "Dark"}</span>}
    </button>
  );
}
