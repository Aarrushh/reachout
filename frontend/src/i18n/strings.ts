/**
 * The only place UI copy lives. Components never hardcode user-facing text.
 * Data fields (item names, shop names, addresses) come from the API and are
 * never translated.
 */
export type Lang = "es" | "en";

const STRINGS = {
  "entry.headline":        { es: "¿Dónde estás en Madrid?", en: "Where are you in Madrid?" },
  "entry.useLocation":     { es: "Usar mi ubicación", en: "Use my location" },
  "entry.locationDenied":  { es: "Ubicación no disponible — elige un barrio", en: "Location unavailable — pick a neighbourhood" },
  "entry.barrioPlaceholder": { es: "Barrio (Malasaña, Lavapiés…)", en: "Neighbourhood (Malasaña, Lavapiés…)" },
  "search.placeholder":    { es: "algo para el dolor de cabeza / usb c charger", en: "algo para el dolor de cabeza / usb c charger" },
  "search.submit":         { es: "Buscar", en: "Search" },
  "results.shops":         { es: "tiendas", en: "shops" },
  "results.shop":          { es: "tienda", en: "shop" },
  "results.stock":         { es: "stock", en: "stock" },
  "results.lowStock":      { es: "¡quedan {n}!", en: "only {n} left" },
  "results.ping":          { es: "PING", en: "PING" },
  "results.empty":         { es: "Ninguna tienda en {r} km lo tiene ahora mismo.", en: "No shop within {r} km has it right now." },
  "results.widen":         { es: "Ampliar a 5 km", en: "Widen to 5 km" },
  "results.retry":         { es: "Reintentar", en: "Retry" },
  "results.error":         { es: "La búsqueda ha fallado", en: "Search failed" },
  "results.loading":       { es: "Enviando pings…", en: "Sending pings…" },
  "topbar.radius":         { es: "radio", en: "radius" },
  "map.you":               { es: "Estás aquí", en: "You are here" },
} as const;

export type StringKey = keyof typeof STRINGS;

export function t(lang: Lang, key: StringKey, vars?: Record<string, string | number>): string {
  let s: string = STRINGS[key][lang];
  if (vars) for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, String(v));
  return s;
}
