import type { Lang } from "../i18n/strings";

export function formatDistance(km: number, lang: Lang): string {
  const meters = Math.round(km * 1000);
  if (meters < 1000) return `${meters} m`;
  const locale = lang === "es" ? "es-ES" : "en-GB";
  return `${km.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`;
}

export function formatPrice(price: number): string {
  return `€${price.toFixed(2)}`;
}
