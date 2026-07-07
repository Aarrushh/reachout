/**
 * Generates src/types/*.d.ts from reachout/shared/schemas/*.schema.json.
 * Run via `npm run gen-types`. Output is never hand-edited (see README.md).
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
const SCHEMAS_DIR = join(HERE, "..", "..", "reachout", "shared", "schemas");
const OUT_DIR = join(HERE, "..", "src", "types");

function toTypeName(schemaFileName: string): string {
  return schemaFileName
    .replace(/\.schema\.json$/, "")
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join("");
}

async function main() {
  mkdirSync(OUT_DIR, { recursive: true });
  const files = readdirSync(SCHEMAS_DIR).filter((f: string) => f.endsWith(".schema.json"));

  for (const file of files) {
    const schema = JSON.parse(readFileSync(join(SCHEMAS_DIR, file), "utf-8"));
    const typeName = toTypeName(basename(file));
    const ts = await compile(schema, typeName, {
      bannerComment:
        `/* eslint-disable */\n` +
        `/**\n * Generated from reachout/shared/schemas/${file} — do not hand-edit.\n * Run \`npm run gen-types\` to regenerate.\n */`,
    });
    writeFileSync(join(OUT_DIR, `${typeName}.d.ts`), ts);
    console.log(`wrote src/types/${typeName}.d.ts`);
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
