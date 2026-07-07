import { BARRIO_NAMES } from "../data/barrios";

/** Accent- and case-insensitive substring match over the generated list. */
export function matchBarrios(input: string): string[] {
  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const q = norm(input.trim());
  if (!q) return BARRIO_NAMES;
  return BARRIO_NAMES.filter((name) => norm(name).includes(q));
}
