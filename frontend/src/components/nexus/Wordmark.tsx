"use client";

import { cn } from "@/lib/utils";

interface WordmarkProps {
  size?: "sm" | "md" | "lg";
  className?: string;
}

export default function Wordmark({ size = "md", className }: WordmarkProps) {
  const text =
    size === "lg" ? "text-3xl font-bold" :
    size === "sm" ? "text-base font-semibold" :
    "text-xl font-semibold";
  const logo = size === "lg" ? "h-9 w-9" : size === "sm" ? "h-5 w-5" : "h-6 w-6";

  return (
    <div className={cn("flex items-center gap-2 tracking-tight", text, className)}>
      <img src="/logo.png" alt="" aria-hidden="true" className={cn("shrink-0 object-contain", logo)} />
      <span>Nexus</span>
    </div>
  );
}