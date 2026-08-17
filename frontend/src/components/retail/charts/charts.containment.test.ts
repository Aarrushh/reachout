import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

/**
 * Executable replacement for the README's old library-grep check
 * (D9 → D11 handoff). Runs against the source tree itself rather than a
 * mock of it, so a future import that violates one of these rules fails a
 * test instead of only a code-review glance.
 *
 * Four rules, each named in the task-3 brief's deliverable 8:
 * 1. Nothing outside `charts/` imports the vendored `./bklit` barrel.
 * 2. Nothing outside `charts/` and `consumer/reactbits/` imports `motion` or
 *    `@visx/*` — the two libraries D11/D12 admitted as scoped exceptions.
 * 3. Every `<Bar` / `<PieSlice` usage inside `charts/` carries
 *    `animate={false}` (C19: charts never animate on refetch).
 * 4. No `reactbits/` import inside `charts/`, and no `bklit` import inside
 *    `consumer/` — the two D-record leak checks from the guardrail
 *    checklist, keeping the two vendored surfaces from bleeding into
 *    each other.
 */

const SRC_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..", "..");
const CHARTS_DIR = join(SRC_ROOT, "components", "retail", "charts");
const BKLIT_DIR = join(CHARTS_DIR, "bklit");
const CONSUMER_DIR = join(SRC_ROOT, "components", "consumer");
const REACTBITS_DIR = join(CONSUMER_DIR, "reactbits");

const CODE_FILE = /\.(ts|tsx)$/;
const IMPORT_SPECIFIER = /(?:from\s+|require\()\s*["']([^"']+)["']/g;

function listSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const info = statSync(full);
    if (info.isDirectory()) {
      out.push(...listSourceFiles(full));
    } else if (CODE_FILE.test(entry)) {
      out.push(full);
    }
  }
  return out;
}

interface FileImport {
  file: string;
  specifier: string;
  /** Absolute path the specifier resolves to, for relative (`./`, `../`) specifiers only. */
  resolved: string | null;
}

function collectImports(files: string[]): FileImport[] {
  const imports: FileImport[] = [];
  for (const file of files) {
    const source = readFileSync(file, "utf-8");
    for (const match of source.matchAll(IMPORT_SPECIFIER)) {
      const specifier = match[1];
      const resolved = specifier.startsWith(".") ? resolve(dirname(file), specifier) : null;
      imports.push({ file, specifier, resolved });
    }
  }
  return imports;
}

/** True when `path` names `dir` itself, or a file/directory nested under it. */
function isWithin(path: string, dir: string): boolean {
  const rel = relative(dir, path);
  return rel === "" || !rel.startsWith("..");
}

const ALL_FILES = listSourceFiles(SRC_ROOT);
const CHARTS_FILES = ALL_FILES.filter((f) => isWithin(f, CHARTS_DIR));
const NON_BKLIT_CHART_FILES = CHARTS_FILES.filter((f) => !isWithin(f, BKLIT_DIR));
const FILES_OUTSIDE_CHARTS = ALL_FILES.filter((f) => !isWithin(f, CHARTS_DIR));
const CONSUMER_FILES = ALL_FILES.filter((f) => isWithin(f, CONSUMER_DIR));

function shortName(path: string): string {
  return relative(SRC_ROOT, path);
}

describe("charts containment (D9 -> D11 handoff, replaces the README grep)", () => {
  it("imports nothing from ./bklit outside components/retail/charts/", () => {
    const violations = collectImports(FILES_OUTSIDE_CHARTS).filter(
      (imp) => imp.resolved !== null && isWithin(imp.resolved, BKLIT_DIR),
    );
    expect(violations.map((v) => `${shortName(v.file)} -> ${v.specifier}`)).toEqual([]);
  });

  it("imports motion / @visx only inside charts/ and consumer/reactbits/", () => {
    const allowedDirs = [CHARTS_DIR, REACTBITS_DIR];
    const filesToCheck = ALL_FILES.filter((f) => !allowedDirs.some((dir) => isWithin(f, dir)));
    const violations = collectImports(filesToCheck).filter(
      (imp) => imp.specifier === "motion" || imp.specifier.startsWith("motion/") || imp.specifier.startsWith("@visx/"),
    );
    expect(violations.map((v) => `${shortName(v.file)} -> ${v.specifier}`)).toEqual([]);
  });

  it("gives every <Bar / <PieSlice usage in charts/ animate={false} (C19)", () => {
    const violations: string[] = [];
    for (const file of NON_BKLIT_CHART_FILES) {
      const source = readFileSync(file, "utf-8");
      for (const tagName of ["Bar", "PieSlice"]) {
        const tagRe = new RegExp(`<${tagName}(?=[\\s/>])[\\s\\S]*?>`, "g");
        for (const tag of source.match(tagRe) ?? []) {
          if (!tag.includes("animate={false}")) {
            violations.push(`${shortName(file)}: ${tag.replace(/\s+/g, " ")}`);
          }
        }
      }
    }
    expect(violations).toEqual([]);
  });

  it("keeps reactbits/ out of charts/ and bklit out of consumer/", () => {
    const reactbitsInCharts = collectImports(CHARTS_FILES).filter((imp) => imp.specifier.includes("reactbits/"));
    expect(reactbitsInCharts.map((v) => `${shortName(v.file)} -> ${v.specifier}`)).toEqual([]);

    const bklitInConsumer = collectImports(CONSUMER_FILES).filter(
      (imp) =>
        imp.specifier.toLowerCase().includes("bklit") ||
        (imp.resolved !== null && isWithin(imp.resolved, BKLIT_DIR)),
    );
    expect(bklitInConsumer.map((v) => `${shortName(v.file)} -> ${v.specifier}`)).toEqual([]);
  });
});
