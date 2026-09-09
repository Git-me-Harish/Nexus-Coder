/**
 * The app's standard loading indicator -- two blurred, blended squares
 * orbiting and merging into a liquid "blob" shape. Ported from a supplied
 * styled-components design to plain CSS (`.nexus-blob-loader` in
 * globals.css): this app has no styled-components dependency and every
 * other animation already lives as a `.nexus-*` class on the existing
 * brand tokens, so this follows that convention instead of adding a second
 * styling system for one component.
 *
 * Sized via the CSS custom property `--blob-size` rather than a `size` prop
 * -- pass it through `style` when a caller needs something other than the
 * default (e.g. `style={{ "--blob-size": "16px" } as React.CSSProperties}`
 * for an inline/small usage).
 */
export default function Loader({ className = "" }: { className?: string }) {
  return <div className={`nexus-blob-loader ${className}`} role="status" aria-label="Loading" />;
}
