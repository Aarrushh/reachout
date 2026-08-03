/**
 * Generates src/types/*.d.ts from the JSON Schemas of BOTH backends —
 * reachout/shared/schemas/ (the shopper API) and demand/shared/schemas/ (the
 * retail demand service). Run via `npm run gen-types`. Output is never
 * hand-edited (see README.md).
 *
 * Both roots are walked because the frontend is one app over two services:
 * U3's charts are typed from demand's analytics_response.schema.json. A file
 * name appearing in both roots is a collision, not a merge — the second one
 * would silently overwrite the first, so it aborts instead.
 */
import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { compile } from "json-schema-to-typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = join(HERE, "..", "..");
const SCHEMA_ROOTS = [
  join("reachout", "shared", "schemas"),
  join("demand", "shared", "schemas"),
];
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
  const seen = new Map<string, string>();

  for (const root of SCHEMA_ROOTS) {
    const dir = join(REPO_ROOT, root);
    const files = readdirSync(dir).filter((f: string) => f.endsWith(".schema.json"));

    for (const file of files) {
      const typeName = toTypeName(basename(file));
      const previous = seen.get(typeName);
      if (previous) {
        throw new Error(
          `${root}/${file} and ${previous} both generate ${typeName}.d.ts. ` +
            `Rename one schema — silently overwriting would type one service ` +
            `with the other's contract.`,
        );
      }
      seen.set(typeName, `${root}/${file}`);

      const schema = JSON.parse(readFileSync(join(dir, file), "utf-8"));
      const ts = await compile(schema, typeName, {
        bannerComment:
          `/* eslint-disable */\n` +
          `/**\n * Generated from ${root}/${file} — do not hand-edit.\n * Run \`npm run gen-types\` to regenerate.\n */`,
      });
      writeFileSync(join(OUT_DIR, `${typeName}.d.ts`), ts);
      console.log(`wrote src/types/${typeName}.d.ts`);
    }
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
