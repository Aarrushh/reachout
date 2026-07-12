import type { ReactNode } from "react";

/** Wraps every number inside a translated sentence in the .mono class, so
 * copy with embedded counts ("{n} resultados…") keeps the numerals in
 * IBM Plex Mono without splitting the i18n strings. */
export function monoNums(s: string): ReactNode[] {
  return s.split(/(\d+(?:[.,]\d+)?)/).map((part, i) =>
    /^\d/.test(part) ? <span key={i} className="mono">{part}</span> : part,
  );
}
