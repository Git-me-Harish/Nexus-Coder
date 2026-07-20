"use client";

import { useEffect, useMemo, useState } from "react";

interface AnimatedCodeBlockProps {
  code: string;
  title?: string;
  typingSpeed?: number;
  showLineNumbers?: boolean;
  autoPlay?: boolean;
  highlightLines?: number[];
  loop?: boolean;
  theme?: "dark" | "light";
  language?: string;
}

export function AnimatedCodeBlock({
  code,
  title = "untitled.ts",
  typingSpeed = 35,
  showLineNumbers = true,
  autoPlay = true,
  highlightLines = [],
  loop = false,
  theme = "dark",
  language,
}: AnimatedCodeBlockProps) {
  const [visibleLength, setVisibleLength] = useState(autoPlay ? 0 : code.length);
  const lines = useMemo(() => code.split("\n"), [code]);
  const visibleCode = code.slice(0, visibleLength);
  const isDark = theme === "dark";

  useEffect(() => {
    if (!autoPlay) return;

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) {
      const revealTimer = setTimeout(() => setVisibleLength(code.length), 0);
      return () => clearTimeout(revealTimer);
    }

    let timer: ReturnType<typeof setTimeout>;
    let restartTimer: ReturnType<typeof setTimeout>;
    const typeNext = () => {
      setVisibleLength((current) => {
        if (current < code.length) {
          timer = setTimeout(typeNext, typingSpeed);
          return current + 1;
        }
        if (loop) {
          restartTimer = setTimeout(() => {
            setVisibleLength(0);
            timer = setTimeout(typeNext, typingSpeed);
          }, 2400);
        }
        return current;
      });
    };

    timer = setTimeout(typeNext, typingSpeed);
    return () => {
      clearTimeout(timer);
      clearTimeout(restartTimer);
    };
  }, [autoPlay, code, loop, typingSpeed]);

  const visibleLines = visibleCode.split("\n");

  return (
    <div className={`overflow-hidden rounded-xl border shadow-2xl ${isDark ? "border-white/10 bg-[#10111b] text-[#d9ddff]" : "border-[var(--nexus-border)] bg-[var(--nexus-surface)] text-[var(--foreground)]"}`}>
      <div className={`flex items-center gap-2 border-b px-3 py-2.5 ${isDark ? "border-white/10 bg-white/[0.03]" : "border-[var(--nexus-border)]"}`}>
        <div className="flex gap-1.5" aria-hidden="true">
          <span className="h-2.5 w-2.5 rounded-full bg-[#ff5f57]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#febc2e]" />
          <span className="h-2.5 w-2.5 rounded-full bg-[#28c840]" />
        </div>
        <span className="ml-1 min-w-0 flex-1 truncate font-mono text-[11px] text-white/65">{title}</span>
        {language && <span className="font-mono text-[10px] uppercase tracking-wider text-white/35">{language}</span>}
      </div>
      <pre className="max-h-[340px] overflow-auto p-3.5 font-mono text-[11px] leading-5 sm:p-4 sm:text-xs">
        <code>
          {lines.map((line, index) => {
            const lineNumber = index + 1;
            const visibleLine = visibleLines[index] ?? "";
            const isVisible = index < visibleLines.length;
            return (
              <span
                key={`${lineNumber}-${line}`}
                className={`flex min-h-5 rounded px-1 ${highlightLines.includes(lineNumber) ? "bg-violet-400/10" : ""}`}
              >
                {showLineNumbers && <span className="w-7 shrink-0 select-none text-right pr-3 text-white/25">{lineNumber}</span>}
                <span className="whitespace-pre-wrap break-words">{isVisible ? visibleLine : ""}{lineNumber === visibleLines.length && visibleLength < code.length && <span className="ml-0.5 inline-block h-3.5 w-1 animate-pulse bg-violet-300 align-[-2px]" />}</span>
              </span>
            );
          })}
        </code>
      </pre>
    </div>
  );
}