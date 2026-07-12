/**
 * Generates src/data/barrios.ts from reachout/data/gazetteer_madrid.json so
 * the autocomplete list can never drift from what the backend resolves.
 * Run via `npm run gen-barrios`. Output is never hand-edited.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
const GAZETTEER = join(HERE, "..", "..", "reachout", "data", "gazetteer_madrid.json");
const OUT = join(HERE, "..", "src", "data", "barrios.ts");

// Spanish connectives stay lowercase except at the start of the name.
const STOPWORDS = new Set(["de", "del", "la", "las", "los", "el", "y"]);

function titleCase(name: string): string {
  return name
    .split(" ")
    .map((w, i) => (i > 0 && STOPWORDS.has(w) ? w : w.charAt(0).toUpperCase() + w.slice(1)))
    .join(" ");
}

const gazetteer = JSON.parse(readFileSync(GAZETTEER, "utf-8")) as Record<
  string,
  { lat: number; lng: number } | string
>;
const barrios = Object.entries(gazetteer)
  .filter(([k, v]) => !k.startsWith("_") && typeof v === "object")
  .map(([k, v]) => {
    const { lat, lng } = v as { lat: number; lng: number };
    return { name: titleCase(k), lat, lng };
  });
const names = barrios.map((b) => b.name);

const body =
  `/* eslint-disable */\n` +
  `/**\n` +
  ` * Generated from reachout/data/gazetteer_madrid.json — do not hand-edit.\n` +
  ` * Run \`npm run gen-barrios\` to regenerate. The \`near\` URL param is still\n` +
  ` * resolved to coordinates server-side; centroids here are fallback-quality,\n` +
  ` * used only for map camera fly-to.\n` +
  ` */\n` +
  `export interface Barrio {\n  name: string;\n  lat: number;\n  lng: number;\n}\n\n` +
  `export const BARRIOS: Barrio[] = ${JSON.stringify(barrios, null, 2)};\n\n` +
  `export const BARRIO_NAMES: string[] = BARRIOS.map((b) => b.name);\n`;

writeFileSync(OUT, body);
console.log(`wrote src/data/barrios.ts (${names.length} barrios with centroids)`);
