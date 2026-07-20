"use client";

import ReactMarkdown from "react-markdown";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark, oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { Copy, Check, Terminal } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/utils";
import { useThemeStore } from "@/stores/themeStore";

interface Props {
  content: string;
  className?: string;
}

export default function MarkdownRenderer({ content, className }: Props) {
  return (
    <div className={cn("nexus-prose text-sm text-[var(--foreground)]", className)}>
      <ReactMarkdown
        components={{
          code({ node, className: cls, children, ...props }: any) {
            const match = /language-(\w+)/.exec(cls || "");
            const isInline = !cls && !String(children).includes("\n");
            if (isInline) {
              return <code className="nexus-inline-code" {...props}>{children}</code>;
            }
            const code = String(children).replace(/\n$/, "");
            return <CodeBlock language={match?.[1] ?? "text"} code={code} />;
          },
          a: ({ node, ...props }: any) => <a target="_blank" rel="noopener noreferrer" {...props} />,
          // Wrap headings, lists, etc. with clearer styling
          h1: ({ node, ...props }: any) => <h1 className="nexus-h1" {...props} />,
          h2: ({ node, ...props }: any) => <h2 className="nexus-h2" {...props} />,
          h3: ({ node, ...props }: any) => <h3 className="nexus-h3" {...props} />,
          h4: ({ node, ...props }: any) => <h4 className="nexus-h4" {...props} />,
          p: ({ node, ...props }: any) => <p className="nexus-p" {...props} />,
          ul: ({ node, ...props }: any) => <ul className="nexus-ul" {...props} />,
          ol: ({ node, ...props }: any) => <ol className="nexus-ol" {...props} />,
          li: ({ node, ...props }: any) => <li className="nexus-li" {...props} />,
          blockquote: ({ node, ...props }: any) => <blockquote className="nexus-quote" {...props} />,
          strong: ({ node, ...props }: any) => <strong className="nexus-strong" {...props} />,
          em: ({ node, ...props }: any) => <em className="nexus-em" {...props} />,
          hr: ({ node, ...props }: any) => <hr className="nexus-hr" {...props} />,
          table: ({ node, ...props }: any) => <div className="nexus-table-wrap"><table className="nexus-table" {...props} /></div>,
          th: ({ node, ...props }: any) => <th className="nexus-th" {...props} />,
          td: ({ node, ...props }: any) => <td className="nexus-td" {...props} />,
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}

function CodeBlock({ language, code }: { language: string; code: string }) {
  const [copied, setCopied] = useState(false);
  const theme = useThemeStore((s) => s.theme);
  const isDark = theme === "dark";

  // Extract path from first-line comment if present
  let displayCode = code;
  let path: string | null = null;
  const firstLine = code.split("\n")[0];
  const pathMatch = firstLine.match(/^\/\/\s*(.+?\.\w+)\s*$/);
  if (pathMatch) {
    path = pathMatch[1];
    displayCode = code.split("\n").slice(1).join("\n");
  }

  function copy() {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  return (
    <div className="nexus-code-block group my-3">
      <div className="nexus-code-header">
        <div className="flex items-center gap-1.5 min-w-0">
          <Terminal className="w-3 h-3 text-[var(--muted-foreground)] shrink-0" />
          <span className="nexus-code-lang">
            {path ?? language}
          </span>
        </div>
        <button
          onClick={copy}
          className="nexus-code-copy"
          title="Copy code"
        >
          {copied ? <Check className="w-3 h-3 text-[var(--nexus-success)]" /> : <Copy className="w-3 h-3" />}
          <span className="hidden sm:inline">{copied ? "Copied" : "Copy"}</span>
        </button>
      </div>
      <SyntaxHighlighter
        language={language}
        style={isDark ? oneDark : oneLight}
        customStyle={{
          margin: 0,
          background: "transparent",
          borderRadius: "0 0 8px 8px",
          fontSize: "12.5px",
          padding: "12px 14px",
        }}
        codeTagProps={{
          style: {
            fontFamily: "var(--font-mono), monospace",
          },
        }}
      >
        {displayCode}
      </SyntaxHighlighter>
    </div>
  );
}
