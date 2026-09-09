"use client";

import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";

export function initialsFor(nameOrEmail?: string | null): string {
  return (nameOrEmail || "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
}

interface AvatarProps {
  src?: string | null;
  name?: string | null;
  className?: string;
  /** Font size for the initials fallback; the gradient circle is sized by `className`. */
  textClassName?: string;
}

/**
 * Profile picture with an initials fallback. The fallback is not only for
 * "no avatar set" -- an avatar_url can also be a GitHub CDN link copied at
 * sign-in, or a file that has since been deleted, so a load error has to fall
 * back too rather than leaving a broken-image icon in the sidebar.
 */
export default function Avatar({ src, name, className, textClassName }: AvatarProps) {
  const [failed, setFailed] = useState(false);

  // A new src deserves a fresh attempt -- otherwise replacing a broken avatar
  // with a working one would keep showing initials until a remount.
  useEffect(() => setFailed(false), [src]);

  const base = "shrink-0 rounded-full overflow-hidden flex items-center justify-center";

  if (src && !failed) {
    return (
      <img
        src={src}
        alt=""
        onError={() => setFailed(true)}
        className={cn(base, "object-cover bg-[var(--nexus-surface-2)]", className)}
      />
    );
  }

  return (
    <div
      className={cn(
        base,
        "bg-gradient-to-br from-[var(--nexus-violet)] to-[var(--nexus-purple-dim)] font-semibold text-white",
        textClassName,
        className
      )}
      aria-hidden="true"
    >
      {initialsFor(name)}
    </div>
  );
}
