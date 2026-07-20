"use client";

// ─── Brand logos as inline SVG with accurate brand colors ──────────────────
// Each logo uses the real brand colors so they're instantly recognizable.
// Monochrome brands (OpenAI, Anthropic, Vercel, Together) use currentColor
// so they adapt to light/dark theme. Colored brands keep their brand palette.

interface LogoProps {
  className?: string;
}

/** Renders the supplied, official partner artwork from /public. */
function AssetLogo({ src, className }: LogoProps & { src: string }) {
  return (
    <img
      src={src}
      alt=""
      aria-hidden="true"
      className={`${className ?? ""} object-contain`}
    />
  );
}

export function OpenAILogo({ className }: LogoProps) {
  // OpenAI flower mark — monochrome, inherits currentColor
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.504 4.504 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.667zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.459a.7948.7948 0 0 0-.3927.6813zm1.0976-2.3654l2.602-1.4998 2.6069 1.4998v2.9994l-2.5974 1.4997-2.6067-1.4997Z"/>
    </svg>
  );
}

export function AnthropicLogo({ className }: LogoProps) {
  // Anthropic "A" wordmark — coral/clay color (#D97757)
  return (
    <svg viewBox="0 0 24 24" className={className} fill="#D97757" aria-hidden="true">
      <path d="M7.307 6.428L11.598 17.572H8.922L8.098 15.064H3.662L2.838 17.572H0.234L4.525 6.428H7.307ZM5.866 8.791L4.425 12.964H7.307L5.866 8.791Z M17.111 6.428L21.402 17.572H18.726L17.902 15.064H13.466L12.642 17.572H10.038L14.329 6.428H17.111ZM15.67 8.791L14.229 12.964H17.111L15.67 8.791Z M24 6.428V17.572H21.6V6.428H24Z"/>
    </svg>
  );
}

export function GoogleLogo({ className }: LogoProps) {
  // Google "G" — multicolor (blue/red/yellow/green)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  );
}

export function GroqLogo({ className }: LogoProps) {
  // Groq lightning bolt — orange/red (#F55036)
  return (
    <svg viewBox="0 0 24 24" className={className} fill="#F55036" aria-hidden="true">
      <path d="M13.5 2L4 13.5h6.5L9 22l10.5-12.5H13L13.5 2z"/>
    </svg>
  );
}

export function MetaLogo({ className }: LogoProps) {
  // Meta infinity loop — blue (#0082FB)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#0082FB" d="M24 9.34c0-3.97-2.32-6.67-5.67-6.67-1.97 0-3.42 1.05-4.86 3.37l-.93 1.52-2.1 3.43-1.5 2.45c-.78 1.28-1.53 2.02-2.73 2.02-.4 0-.78-.1-1.12-.28C4.3 17.7 4.6 14.5 5.2 12.4c.32-1.12 1.1-2.53 2.2-2.53.73 0 1.2.5 1.2 1.3 0 .6-.22 1.1-.5 1.6-.2.37-.3.67-.3 1 0 .9.7 1.7 1.7 1.7 1.4 0 2.3-1.2 2.3-3 0-2.2-1.6-3.8-3.9-3.8-2.8 0-4.8 2.4-5.4 5.2-.4 1.8-.9 4.7.5 6.5.7.9 1.8 1.4 3.1 1.4 1.8 0 3.1-.9 4.3-2.8l1.5-2.4 2.1-3.4.9-1.5c.9-1.5 1.6-2.2 2.8-2.2.4 0 .8.1 1.1.3 1.96.93 1.66 4.13 1.06 6.23-.32 1.12-1.1 2.53-2.2 2.53-.73 0-1.2-.5-1.2-1.3 0-.6.22-1.1.5-1.6.2-.37.3-.67.3-1 0-.9-.7-1.7-1.7-1.7-1.4 0-2.3 1.2-2.3 3 0 2.2 1.6 3.8 3.9 3.8 2.8 0 4.8-2.4 5.4-5.2.4-1.8.9-4.7-.5-6.5-.7-.9-1.8-1.4-3.1-1.4z"/>
    </svg>
  );
}

export function MistralLogo({ className }: LogoProps) {
  // Mistral AI — layered gradient blocks (brand-accurate)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect x="0" y="0" width="6" height="3" fill="#FFD700"/>
      <rect x="6" y="0" width="6" height="3" fill="#FFD700"/>
      <rect x="12" y="0" width="6" height="3" fill="#FFD700"/>
      <rect x="18" y="0" width="6" height="3" fill="#FFD700"/>
      <rect x="0" y="3" width="6" height="3" fill="#FF6B35"/>
      <rect x="6" y="3" width="6" height="3" fill="#FFD700"/>
      <rect x="12" y="3" width="6" height="3" fill="#FFD700"/>
      <rect x="18" y="3" width="6" height="3" fill="#FF6B35"/>
      <rect x="0" y="6" width="6" height="3" fill="#F41320"/>
      <rect x="6" y="6" width="6" height="3" fill="#FF6B35"/>
      <rect x="12" y="6" width="6" height="3" fill="#FF6B35"/>
      <rect x="18" y="6" width="6" height="3" fill="#F41320"/>
      <rect x="0" y="9" width="24" height="3" fill="#F41320"/>
      <rect x="6" y="12" width="12" height="3" fill="#F41320"/>
      <rect x="12" y="15" width="6" height="3" fill="#FF6B35"/>
      <rect x="12" y="18" width="6" height="3" fill="#FFD700"/>
    </svg>
  );
}

export function CohereLogo({ className }: LogoProps) {
  // Cohere — stylized "C" mark, dark teal/forest (#39594D)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#39594D" d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10c3.31 0 6.27-1.62 8.08-4.1l-2.42-1.45C16.45 18.45 14.36 19.5 12 19.5c-4.14 0-7.5-3.36-7.5-7.5S7.86 4.5 12 4.5c2.36 0 4.45 1.05 5.66 2.55l2.42-1.45C18.27 3.62 15.31 2 12 2z"/>
      <circle cx="12" cy="12" r="2.5" fill="#39594D"/>
    </svg>
  );
}

export function AI21Logo({ className }: LogoProps) {
  // AI21 Labs — "21" mark, purple (#6B46C1)
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <rect x="2" y="2" width="20" height="20" rx="4" fill="#6B46C1"/>
      <text x="12" y="16" textAnchor="middle" fill="white" fontSize="10" fontWeight="bold" fontFamily="Arial, sans-serif">21</text>
    </svg>
  );
}

export function TogetherLogo({ className }: LogoProps) {
  // Together AI — monochrome, inherits currentColor
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <circle cx="9" cy="12" r="6" opacity="0.7"/>
      <circle cx="15" cy="12" r="6" opacity="0.7"/>
    </svg>
  );
}

export function HuggingFaceLogo({ className }: LogoProps) {
  // Hugging Face smiley — yellow face, dark features
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <circle cx="12" cy="12" r="10" fill="#FFD21E"/>
      <circle cx="8.5" cy="10" r="1.2" fill="#1A1A1A"/>
      <circle cx="15.5" cy="10" r="1.2" fill="#1A1A1A"/>
      <path d="M7 14c1.5 2 8.5 2 10 0" stroke="#1A1A1A" strokeWidth="1.5" fill="none" strokeLinecap="round"/>
      <circle cx="6" cy="14" r="1.5" fill="#FF6F00" opacity="0.4"/>
      <circle cx="18" cy="14" r="1.5" fill="#FF6F00" opacity="0.4"/>
    </svg>
  );
}

export function LangChainLogo({ className }: LogoProps) {
  // LangChain — lizard/chain, dark green (#1C3C3C) with green accent
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden="true">
      <path fill="#1C3C3C" d="M10 2a8 8 0 0 0-8 8 8 8 0 0 0 8 8 8 8 0 0 0 4-1.1l3.5 3.5a2 2 0 1 0 2.8-2.8L18.8 14A8 8 0 0 0 20 10a8 8 0 0 0-8-8 8 8 0 0 0-2 0zm0 3a5 5 0 0 1 5 5 5 5 0 0 1-5 5 5 5 0 0 1-5-5 5 5 0 0 1 5-5z"/>
    </svg>
  );
}

export function VercelLogo({ className }: LogoProps) {
  // Vercel triangle — monochrome, inherits currentColor
  return (
    <svg viewBox="0 0 24 24" className={className} fill="currentColor" aria-hidden="true">
      <path d="M12 2L22 20H2L12 2z"/>
    </svg>
  );
}

// ─── Partner registry ───────────────────────────────────────────────────────

interface Partner {
  name: string;
  blurb: string;
  Logo?: React.FC<LogoProps>;
  logoSrc?: string;
}

const PARTNERS: Partner[] = [
  { name: "OpenAI",       blurb: "GPT-4o",          Logo: OpenAILogo },
  { name: "Anthropic",    blurb: "Claude",          logoSrc: "/anthropic.png" },
  { name: "Google",       blurb: "Gemini",          Logo: GoogleLogo },
  { name: "Groq",         blurb: "Llama 3 70B",     logoSrc: "/groq.png" },
  { name: "Meta",         blurb: "Llama",           logoSrc: "/meta.png" },
  { name: "Mistral AI",   blurb: "Mistral",         logoSrc: "/mistral.png" },
  { name: "Cohere",       blurb: "Command R+",      logoSrc: "/cohere.png" },
  { name: "AI21 Labs",    blurb: "Jamba",           logoSrc: "/AI21-Labs.png" },
  { name: "Together AI",  blurb: "Open models",     logoSrc: "/together-ai.png" },
  { name: "Hugging Face", blurb: "Model hub",       logoSrc: "/hugging-face.png" },
  { name: "LangChain",    blurb: "Agent framework", logoSrc: "/langchain.png" },
  { name: "Vercel",       blurb: "AI SDK",          Logo: VercelLogo },
];

export default function PartnersMarquee() {
  // Duplicate the list so the marquee can loop seamlessly (-50% translateX)
  const doubled = [...PARTNERS, ...PARTNERS];

  return (
    <div className="mt-8 sm:mt-10">
      <div className="text-center mb-5">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[var(--nexus-surface)] border border-[var(--nexus-border)] text-[10px] font-medium uppercase tracking-wider text-[var(--muted-foreground)] mb-2">
          <span className="w-1.5 h-1.5 rounded-full bg-[var(--nexus-success)] nexus-pulse" />
          Powered by the best
        </div>
        <h3 className="text-base sm:text-lg font-semibold text-[var(--foreground)]">
          Routing across every major LLM provider
        </h3>
        <p className="text-xs text-[var(--muted-foreground)] mt-1">
          Intelligent model router picks the best model per phase, with fallback chains.
        </p>
      </div>

      <div className="nexus-marquee py-4">
        <div className="nexus-marquee-track">
          {doubled.map((p, i) => {
            return (
              <div key={`${p.name}-${i}`} className="nexus-marquee-item">
                <div className="nexus-marquee-item-icon">
                  {p.logoSrc ? (
                    <AssetLogo src={p.logoSrc} className="w-5 h-5" />
                  ) : p.Logo ? (
                    <p.Logo className="w-5 h-5" />
                  ) : null}
                </div>
                <div className="flex flex-col leading-tight">
                  <span className="text-sm font-semibold text-[var(--foreground)]">{p.name}</span>
                  <span className="text-[10px] text-[var(--muted-foreground)]">{p.blurb}</span>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}