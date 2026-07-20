"use client";

import { useEffect } from "react";
import { useThemeStore } from "@/stores/themeStore";

/**
 * Applies the persisted theme to <html> on mount.
 * Renders nothing — purely a side-effect.
 */
export default function ThemeApplier() {
  const applyToDocument = useThemeStore((s) => s.applyToDocument);
  useEffect(() => {
    applyToDocument();
  }, [applyToDocument]);
  return null;
}
