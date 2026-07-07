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

const gazetteer = JSON.parse(readFileSync(GAZETTEER, "utf-8")) as Record<string, unknown>;
const names = Object.keys(gazetteer)
  .filter((k) => !k.startsWith("_"))
  .map(titleCase);

const body =
  `/* eslint-disable */\n` +
  `/**\n` +
  ` * Generated from reachout/data/gazetteer_madrid.json — do not hand-edit.\n` +
  ` * Run \`npm run gen-barrios\` to regenerate. Names only: the \`near\` URL\n` +
  ` * param is resolved to coordinates server-side.\n` +
  ` */\n` +
  `export const BARRIO_NAMES: string[] = ${JSON.stringify(names, null, 2)};\n`;

writeFileSync(OUT, body);
console.log(`wrote src/data/barrios.ts (${names.length} names)`);
