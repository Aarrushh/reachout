import type { Lang } from "../i18n/strings";

export function formatDistance(km: number, lang: Lang): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  const locale = lang === "es" ? "es-ES" : "en-GB";
  return `${km.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`;
}

export function formatPrice(price: number): string {
  return `€${price.toFixed(2)}`;
}
