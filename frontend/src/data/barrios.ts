/** Synced by hand from reachout/data/gazetteer_madrid.json (fallback-quality
 * centroids). Autocomplete only — the `near` param is resolved server-side. */
export interface Barrio { name: string; lat: number; lng: number }

export const BARRIOS: Barrio[] = [
  { name: "Malasaña", lat: 40.4267, lng: -3.7038 },
  { name: "Lavapiés", lat: 40.4088, lng: -3.7005 },
  { name: "Chueca", lat: 40.4223, lng: -3.6973 },
  { name: "La Latina", lat: 40.4123, lng: -3.7093 },
  { name: "Sol", lat: 40.4168, lng: -3.7038 },
  { name: "Huertas", lat: 40.414, lng: -3.698 },
  { name: "Ópera", lat: 40.418, lng: -3.711 },
  { name: "Chamberí", lat: 40.434, lng: -3.7043 },
  { name: "Salamanca", lat: 40.4278, lng: -3.6795 },
  { name: "Retiro", lat: 40.411, lng: -3.676 },
  { name: "Argüelles", lat: 40.43, lng: -3.716 },
  { name: "Moncloa", lat: 40.435, lng: -3.719 },
  { name: "Embajadores", lat: 40.405, lng: -3.702 },
  { name: "Tetuán", lat: 40.46, lng: -3.698 },
  { name: "Cuatro Caminos", lat: 40.447, lng: -3.704 },
  { name: "Prosperidad", lat: 40.444, lng: -3.674 },
  { name: "Usera", lat: 40.383, lng: -3.706 },
  { name: "Carabanchel", lat: 40.383, lng: -3.728 },
  { name: "Puente de Vallecas", lat: 40.398, lng: -3.669 },
  { name: "Legazpi", lat: 40.391, lng: -3.695 },
  { name: "Príncipe Pío", lat: 40.421, lng: -3.72 },
  { name: "Atocha", lat: 40.407, lng: -3.689 },
];

/** Accent- and case-insensitive substring match. */
export function matchBarrios(input: string): Barrio[] {
  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const q = norm(input.trim());
  if (!q) return BARRIOS;
  return BARRIOS.filter((b) => norm(b.name).includes(q));
}
