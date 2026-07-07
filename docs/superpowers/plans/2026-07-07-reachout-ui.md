# ReachOut UI (Madrid MVP) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full visual UI for ReachOut's entry + results flow (split-view map/cards with staggered "ping" animation) on top of the existing architecture-only frontend skeleton, plus one read-only backend endpoint for the all-shops network layer.

**Architecture:** URL-as-state routing and TanStack Query (already in place) stay untouched; UI components consume the two existing queries plus a new static `GET /api/shops.geojson`. Pings are client-side presentation state (`usePingSequence`). Plain CSS with design tokens as custom properties; MapLibre GL over Carto Dark Matter tiles.

**Tech Stack:** React 19, Vite 6, TypeScript 5.7, MapLibre GL JS 4, TanStack Query 5, react-router-dom 7, FastAPI (backend), vitest + @testing-library/react (new, frontend logic tests), @fontsource (self-hosted fonts).

## Global Constraints

- Spec of record: `docs/superpowers/specs/2026-07-07-reachout-ui-design.md`. Colors, type scale, spacing, and copy come from §5 verbatim.
- Schema-first rule: any new API field/endpoint gets a JSON schema in `reachout/shared/schemas/` first, backend second, `npm run gen-types` third. The frontend never invents data fields.
- `pinged` is NEVER a data field — it is client presentation state only (spec D1).
- All numeric UI text (prices, distances, qty, ranks, timestamps) renders in IBM Plex Mono.
- Default language `es`; `lang` URL param; data fields (item/shop names, addresses) never translated.
- Radius: km, range 0.5–5, default 2.0, written to `radius` URL param debounced 400 ms.
- All pulse/loop animation must honor `prefers-reduced-motion: reduce`.
- Dark theme only. Palette tokens from spec §5.1 exactly.
- Backend tests run from `reachout/tests/` with `pytest`; frontend checks: `npm run build` (tsc + vite) and `npx vitest run`.
- Commit after every task (conventional commits).

## File Structure

```
reachout/shared/schemas/shops_geojson.schema.json    NEW  (Task 1)
reachout/api/server.py                               MOD  (Task 1)
reachout/tests/test_api.py                           MOD  (Task 1)

frontend/
├── package.json                MOD (Task 2: vitest, testing-library, fontsource)
├── vitest.config.ts            NEW (Task 2)
├── index.html                  MOD (Task 2: title, lang)
└── src/
    ├── styles/tokens.css       NEW (Task 2)  design tokens + base styles
    ├── i18n/strings.ts         NEW (Task 2)  dictionary + t()
    ├── hooks/useLang.ts        NEW (Task 2)  lang URL param hook
    ├── data/barrios.ts         NEW (Task 2)  static barrio list
    ├── api/client.ts           MOD (Task 2)  + fetchAllShops
    ├── types/ShopsGeojson.d.ts GEN (Task 1)  via npm run gen-types
    ├── lib/format.ts           NEW (Task 2)  formatDistance/formatPrice
    ├── routes/search.tsx       MOD (Task 3)  entry screen
    ├── components/entry.css    NEW (Task 3)
    ├── components/BarrioCombobox.tsx      NEW (Task 3)
    ├── routes/results.tsx      MOD (Task 4)  screen assembly
    ├── components/TopBar.tsx   NEW (Task 4)  (Wordmark, RadiusSlider, LangToggle inside)
    ├── components/SearchInput.tsx          NEW (Task 3, reused Task 4)
    ├── components/ResultsPanel.tsx         NEW (Task 4)  (meta, empty, error, skeleton inside)
    ├── components/ShopCard.tsx MOD-NEW (Task 4)
    ├── components/results.css  NEW (Task 4)
    ├── hooks/usePingSequence.ts NEW (Task 5)
    ├── hooks/usePingSequence.test.ts NEW (Task 5)
    ├── components/MapPanel.tsx NEW (Task 6)
    ├── map/map-layers.ts       NEW (Task 6)  layer/source management (pure fns)
    └── map/geojson-source.ts   EXISTS        adapter, unchanged
```

---

### Task 1: `GET /api/shops.geojson` — schema, endpoint, test

**Files:**
- Create: `reachout/shared/schemas/shops_geojson.schema.json`
- Modify: `reachout/api/server.py`
- Test: `reachout/tests/test_api.py` (append)

**Interfaces:**
- Produces: `GET /api/shops.geojson` → `{type:"FeatureCollection", metadata:{shop_count}, features:[{type,geometry:{type:"Point",coordinates:[lng,lat]},properties:{shop_id,shop_name,category}}]}` and generated TS type `ShopsGeoJSON` (title `ShopsGeoJSON`) consumed by Task 2's `fetchAllShops`.

- [ ] **Step 1: Write the failing test** — append to `reachout/tests/test_api.py`:

```python
def test_all_shops_geojson_lists_every_shop(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    resp = client.get("/api/shops.geojson")
    assert resp.status_code == 200
    body = resp.json()
    ok, err = v.validate(body, "shops_geojson.schema.json")
    assert ok, err
    assert body["metadata"]["shop_count"] == 1
    props = body["features"][0]["properties"]
    assert props == {"shop_id": "osm:node:1001", "shop_name": "Farmacia Malasaña",
                     "category": "pharmacy"}
    assert body["features"][0]["geometry"]["coordinates"] == [-3.7035, 40.4270]
```

- [ ] **Step 2: Run to verify it fails** — `cd reachout/tests && python -m pytest test_api.py::test_all_shops_geojson_lists_every_shop -v`. Expected: FAIL (404 or validate error: schema file missing).

- [ ] **Step 3: Write the schema** `reachout/shared/schemas/shops_geojson.schema.json`:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ShopsGeoJSON",
  "description": "RFC 7946 FeatureCollection of ALL known shops (no inventory, no ranking) for the map's always-on network layer. Facts only: id, name, category, position. Same coordinate-order guard as map_geojson.schema.json.",
  "type": "object",
  "additionalProperties": false,
  "required": ["type", "metadata", "features"],
  "properties": {
    "type": { "const": "FeatureCollection" },
    "metadata": {
      "type": "object",
      "additionalProperties": false,
      "required": ["shop_count"],
      "properties": { "shop_count": { "type": "integer", "minimum": 0 } }
    },
    "features": {
      "type": "array",
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": ["type", "geometry", "properties"],
        "properties": {
          "type": { "const": "Feature" },
          "geometry": {
            "type": "object",
            "additionalProperties": false,
            "required": ["type", "coordinates"],
            "properties": {
              "type": { "const": "Point" },
              "coordinates": {
                "type": "array", "minItems": 2, "maxItems": 2,
                "items": [
                  { "type": "number", "minimum": -4.0, "maximum": -3.4 },
                  { "type": "number", "minimum": 40.2, "maximum": 40.7 }
                ]
              }
            }
          },
          "properties": {
            "type": "object",
            "additionalProperties": false,
            "required": ["shop_id", "shop_name", "category"],
            "properties": {
              "shop_id": { "type": "string", "pattern": "^osm:(node|way|relation):[0-9]+$" },
              "shop_name": { "type": "string", "minLength": 1 },
              "category": { "enum": ["pharmacy", "grocery", "hardware", "electronics", "stationery"] }
            }
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: Add endpoint** to `reachout/api/server.py` (after `search_geojson`; add `import db` next to `import run_pipeline`):

```python
@app.get("/api/shops.geojson")
def shops_geojson():
    """All known shops, no inventory: the map's network layer. Pure read."""
    conn = db.connect(DB_PATH)
    try:
        shops = db.all_shops(conn)
    finally:
        conn.close()
    return {
        "type": "FeatureCollection",
        "metadata": {"shop_count": len(shops)},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [s["lng"], s["lat"]]},
                "properties": {
                    "shop_id": s["shop_id"],
                    "shop_name": s["name"],
                    "category": s["categories"][0],
                },
            }
            for s in shops
        ],
    }
```

Note: `db.connect(DB_PATH)` — `db.connect(None)` already falls back to the real DB, matching the test monkeypatch pattern.

- [ ] **Step 5: Run tests** — `python -m pytest test_api.py -v`. Expected: all PASS (existing 6 + new 1).

- [ ] **Step 6: Generate the TS type** — `cd frontend && npm run gen-types`. Expected: `src/types/ShopsGeojson.d.ts` appears exporting `ShopsGeoJSON`. (If gen-types script filters schemas by name, extend its list to include `shops_geojson.schema.json`.)

- [ ] **Step 7: Commit** — `git add reachout/shared/schemas/shops_geojson.schema.json reachout/api/server.py reachout/tests/test_api.py frontend/src/types/ && git commit -m "feat(api): all-shops geojson endpoint for map network layer"`

---

### Task 2: Frontend foundation — tokens, fonts, i18n, barrios, fetcher, formatters, vitest

**Files:**
- Modify: `frontend/package.json`, `frontend/index.html`, `frontend/src/main.tsx`, `frontend/src/api/client.ts`
- Create: `frontend/vitest.config.ts`, `frontend/src/styles/tokens.css`, `frontend/src/i18n/strings.ts`, `frontend/src/hooks/useLang.ts`, `frontend/src/data/barrios.ts`, `frontend/src/lib/format.ts`
- Test: `frontend/src/i18n/strings.test.ts`, `frontend/src/lib/format.test.ts`

**Interfaces:**
- Produces:
  - `t(lang: Lang, key: StringKey): string`, `type Lang = "es" | "en"`
  - `useLang(): [Lang, (l: Lang) => void]` (reads/writes `lang` URL param)
  - `BARRIOS: { name: string; lat: number; lng: number }[]` (display-cased)
  - `fetchAllShops(): Promise<ShopsGeoJSON>`
  - `formatDistance(km: number, lang: Lang): string` — `0.412 → "412 m"`, `1.2 → "1,2 km"` (es) / `"1.2 km"` (en)
  - `formatPrice(price: number): string` — `3.85 → "€3.85"`
  - CSS custom props `--ink-900/-800/-700/-600, --terracotta, --terracotta-hot, --sand, --sand-dim, --gold, --navy-line, --cat-pharmacy, --cat-grocery, --cat-hardware, --cat-electronics, --cat-stationery, --err` and utility classes `.mono`, `.microcaps`.

- [ ] **Step 1: Install deps** —
  `npm i @fontsource/space-grotesk @fontsource/ibm-plex-mono @fontsource/inter`
  `npm i -D vitest @testing-library/react jsdom`
  Add to `package.json` scripts: `"test": "vitest run"`.

- [ ] **Step 2: vitest config** `frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
export default defineConfig({ test: { environment: "jsdom" } });
```

- [ ] **Step 3: Failing tests** — `src/i18n/strings.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { t } from "./strings";

describe("i18n", () => {
  it("returns Spanish by default keys", () => {
    expect(t("es", "search.placeholder")).toContain("dolor de cabeza");
  });
  it("returns English variants", () => {
    expect(t("en", "entry.headline")).toBe("Where are you in Madrid?");
  });
});
```

`src/lib/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { formatDistance, formatPrice } from "./format";

describe("format", () => {
  it("shows meters under 1 km", () => {
    expect(formatDistance(0.412, "en")).toBe("412 m");
  });
  it("uses locale decimal for km", () => {
    expect(formatDistance(1.24, "es")).toBe("1,2 km");
    expect(formatDistance(1.24, "en")).toBe("1.2 km");
  });
  it("formats euros", () => {
    expect(formatPrice(3.8)).toBe("€3.80");
  });
});
```

- [ ] **Step 4: Run tests, expect FAIL** — `npx vitest run`. Expected: module-not-found failures.

- [ ] **Step 5: Implement** — `src/i18n/strings.ts` (complete dictionary; components added later must NOT hardcode copy — every string goes here):

```ts
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
```

`src/hooks/useLang.ts`:

```ts
import { useSearchParams } from "react-router-dom";
import type { Lang } from "../i18n/strings";

export function useLang(): [Lang, (l: Lang) => void] {
  const [searchParams, setSearchParams] = useSearchParams();
  const lang: Lang = searchParams.get("lang") === "en" ? "en" : "es";
  const setLang = (l: Lang) => {
    const next = new URLSearchParams(searchParams);
    if (l === "es") next.delete("lang"); else next.set("lang", l);
    setSearchParams(next, { replace: true });
  };
  return [lang, setLang];
}
```

`src/lib/format.ts`:

```ts
import type { Lang } from "../i18n/strings";

export function formatDistance(km: number, lang: Lang): string {
  if (km < 1) return `${Math.round(km * 1000)} m`;
  const locale = lang === "es" ? "es-ES" : "en-GB";
  return `${km.toLocaleString(locale, { minimumFractionDigits: 1, maximumFractionDigits: 1 })} km`;
}

export function formatPrice(price: number): string {
  return `€${price.toFixed(2)}`;
}
```

`src/data/barrios.ts` — display-cased copy of `reachout/data/gazetteer_madrid.json` (drop the duplicate aliases "puerta del sol" and "barrio de las letras"; keep "Sol" and "Huertas"):

```ts
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

/** Accent- and case-insensitive prefix/substring match. */
export function matchBarrios(input: string): Barrio[] {
  const norm = (s: string) => s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
  const q = norm(input.trim());
  if (!q) return BARRIOS;
  return BARRIOS.filter((b) => norm(b.name).includes(q));
}
```

Append to `src/api/client.ts`:

```ts
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

export async function fetchAllShops(): Promise<ShopsGeoJSON> {
  const res = await fetch(`${API_BASE}/api/shops.geojson`);
  if (!res.ok) throw new Error(`GET /api/shops.geojson failed: ${res.status}`);
  return res.json();
}
```

- [ ] **Step 6: tokens.css** — `src/styles/tokens.css` (imported once in `main.tsx` together with the three fontsource imports: `@fontsource/space-grotesk/600.css`, `@fontsource/ibm-plex-mono/500.css`, `@fontsource/inter/400.css`, `@fontsource/inter/500.css`):

```css
:root {
  --ink-900: #0c1220; --ink-800: #111a2c; --ink-700: #18233a; --ink-600: #22304c;
  --terracotta: #e2725b; --terracotta-hot: #ff8a66;
  --sand: #ead9bd; --sand-dim: #9aa3b5; --gold: #d9a441; --navy-line: #3a4e78;
  --cat-pharmacy: #7fb069; --cat-grocery: #b8d97e; --cat-hardware: #f4a259;
  --cat-electronics: #5bc0eb; --cat-stationery: #c77dff; --err: #e45858;
  --font-display: "Space Grotesk", sans-serif;
  --font-mono: "IBM Plex Mono", monospace;
  --font-ui: "Inter", sans-serif;
}
* { box-sizing: border-box; }
html, body, #root { height: 100%; margin: 0; }
body {
  background: var(--ink-900); color: var(--sand);
  font-family: var(--font-ui); font-size: 13px; line-height: 1.4;
}
.mono { font-family: var(--font-mono); font-weight: 500; }
.microcaps {
  font-family: var(--font-mono); font-size: 11px; font-weight: 500;
  text-transform: uppercase; letter-spacing: 0.08em;
}
button, input { font: inherit; color: inherit; }
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```

Also set `index.html`: `<html lang="es">`, `<title>ReachOut — Madrid</title>`.

- [ ] **Step 7: Run checks** — `npx vitest run` → PASS; `npm run build` → clean. Expected: PASS/exit 0.

- [ ] **Step 8: Commit** — `git commit -m "feat(frontend): design tokens, fonts, i18n, barrios, formatters, all-shops fetcher"`

---

### Task 3: Entry screen

**Files:**
- Modify: `frontend/src/routes/search.tsx`
- Create: `frontend/src/components/SearchInput.tsx`, `frontend/src/components/BarrioCombobox.tsx`, `frontend/src/components/entry.css`

**Interfaces:**
- Consumes: `t`, `useLang`, `matchBarrios`, `BARRIOS`
- Produces: `<SearchInput value onChange onSubmit lang autoFocus?>` reused by Task 4's TopBar. Navigation contract on submit: `/results?q=…&(near=<Name>|lat=…&lng=…)&radius=2[&lang=en]`.

- [ ] **Step 1: SearchInput** — `src/components/SearchInput.tsx`:

```tsx
import { type FormEvent } from "react";
import { t, type Lang } from "../i18n/strings";

interface Props {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  lang: Lang;
  disabled?: boolean;
  autoFocus?: boolean;
}

export default function SearchInput({ value, onChange, onSubmit, lang, disabled, autoFocus }: Props) {
  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (value.trim()) onSubmit();
  }
  return (
    <form className="search-input" onSubmit={handleSubmit}>
      <input
        name="q"
        value={value}
        autoFocus={autoFocus}
        placeholder={t(lang, "search.placeholder")}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t(lang, "search.submit")}
      />
      <button type="submit" disabled={disabled || !value.trim()}>
        {t(lang, "search.submit")}
      </button>
    </form>
  );
}
```

- [ ] **Step 2: BarrioCombobox** — `src/components/BarrioCombobox.tsx` (listbox pattern, keyboard up/down/enter/escape):

```tsx
import { useMemo, useRef, useState } from "react";
import { matchBarrios, type Barrio } from "../data/barrios";
import { t, type Lang } from "../i18n/strings";

interface Props {
  selected: Barrio | null;
  onSelect: (b: Barrio | null) => void;
  lang: Lang;
}

export default function BarrioCombobox({ selected, onSelect, lang }: Props) {
  const [input, setInput] = useState(selected?.name ?? "");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const blurTimer = useRef<number>(undefined);
  const options = useMemo(() => matchBarrios(input), [input]);

  function pick(b: Barrio) {
    onSelect(b);
    setInput(b.name);
    setOpen(false);
  }

  return (
    <div className="barrio-combobox" role="combobox" aria-expanded={open} aria-haspopup="listbox">
      <input
        value={input}
        placeholder={t(lang, "entry.barrioPlaceholder")}
        onChange={(e) => { setInput(e.target.value); setOpen(true); setActive(0); onSelect(null); }}
        onFocus={() => setOpen(true)}
        onBlur={() => { blurTimer.current = window.setTimeout(() => setOpen(false), 120); }}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown") { setActive((a) => Math.min(a + 1, options.length - 1)); e.preventDefault(); }
          else if (e.key === "ArrowUp") { setActive((a) => Math.max(a - 1, 0)); e.preventDefault(); }
          else if (e.key === "Enter" && open && options[active]) { pick(options[active]); e.preventDefault(); }
          else if (e.key === "Escape") setOpen(false);
        }}
      />
      {open && options.length > 0 && (
        <ul role="listbox">
          {options.map((b, i) => (
            <li
              key={b.name}
              role="option"
              aria-selected={i === active}
              className={i === active ? "active" : ""}
              onMouseDown={() => { window.clearTimeout(blurTimer.current); pick(b); }}
              onMouseEnter={() => setActive(i)}
            >
              {b.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Entry screen** — rewrite `src/routes/search.tsx`:

```tsx
/** Entry: full-screen location prompt + bilingual search. Submits to /results. */
import { useState } from "react";
import { useNavigate } from "react-router-dom";

import BarrioCombobox from "../components/BarrioCombobox";
import SearchInput from "../components/SearchInput";
import { type Barrio } from "../data/barrios";
import { useLang } from "../hooks/useLang";
import { t } from "../i18n/strings";
import "../components/entry.css";

type Loc = { kind: "barrio"; barrio: Barrio } | { kind: "geo"; lat: number; lng: number };

export default function SearchRoute() {
  const navigate = useNavigate();
  const [lang, setLang] = useLang();
  const [q, setQ] = useState("");
  const [loc, setLoc] = useState<Loc | null>(null);
  const [geoError, setGeoError] = useState(false);
  const [locating, setLocating] = useState(false);

  function submit() {
    if (!loc || !q.trim()) return;
    const params = new URLSearchParams({ q: q.trim(), radius: "2" });
    if (loc.kind === "barrio") params.set("near", loc.barrio.name);
    else { params.set("lat", String(loc.lat)); params.set("lng", String(loc.lng)); }
    if (lang === "en") params.set("lang", "en");
    navigate(`/results?${params.toString()}`);
  }

  function useMyLocation() {
    setLocating(true);
    setGeoError(false);
    navigator.geolocation.getCurrentPosition(
      (pos) => { setLoc({ kind: "geo", lat: pos.coords.latitude, lng: pos.coords.longitude }); setLocating(false); },
      () => { setGeoError(true); setLocating(false); },
      { timeout: 8000 },
    );
  }

  return (
    <div className="entry">
      <div className="entry-lang microcaps">
        <button className={lang === "es" ? "on" : ""} onClick={() => setLang("es")}>ES</button>
        <button className={lang === "en" ? "on" : ""} onClick={() => setLang("en")}>EN</button>
      </div>
      <main className="entry-card">
        <span className="entry-wordmark microcaps">ReachOut · Madrid</span>
        <h1>{t(lang, "entry.headline")}</h1>
        <div className="entry-loc">
          <BarrioCombobox lang={lang} selected={loc?.kind === "barrio" ? loc.barrio : null}
            onSelect={(b) => setLoc(b ? { kind: "barrio", barrio: b } : null)} />
          <button className="entry-geo microcaps" onClick={useMyLocation} disabled={locating}>
            ◎ {t(lang, "entry.useLocation")}{loc?.kind === "geo" ? " ✓" : ""}
          </button>
        </div>
        {geoError && <p className="entry-geo-error">{t(lang, "entry.locationDenied")}</p>}
        <SearchInput value={q} onChange={setQ} onSubmit={submit} lang={lang} disabled={!loc} autoFocus />
      </main>
    </div>
  );
}
```

- [ ] **Step 4: entry.css** — `src/components/entry.css` (spec §3/§5: centered column on ink-900 with a radial terracotta-tinted glow standing in for the network backdrop; NetworkBackdrop map is Task 6 Step 7):

```css
.entry {
  height: 100%; display: grid; place-items: center; position: relative;
  background:
    radial-gradient(ellipse 70% 50% at 50% 40%, rgba(226, 114, 91, 0.08), transparent),
    var(--ink-900);
}
.entry-lang { position: absolute; top: 16px; right: 16px; display: flex; gap: 4px; }
.entry-lang button, .lang-toggle button {
  background: none; border: 1px solid rgba(34, 48, 76, 0.6); border-radius: 4px;
  color: var(--sand-dim); padding: 4px 8px; cursor: pointer;
}
.entry-lang button.on, .lang-toggle button.on { color: var(--terracotta); border-color: var(--terracotta); }
.entry-card { width: min(520px, 90vw); display: flex; flex-direction: column; gap: 16px; }
.entry-wordmark { color: var(--terracotta); }
.entry h1 { font-family: var(--font-display); font-weight: 600; font-size: 40px; line-height: 1.1; margin: 0; }
.entry-loc { display: flex; gap: 8px; }
.barrio-combobox { position: relative; flex: 1; }
.barrio-combobox input, .search-input input {
  width: 100%; background: var(--ink-700); border: 1px solid rgba(34, 48, 76, 0.6);
  border-radius: 6px; padding: 12px; color: var(--sand);
}
.barrio-combobox input:focus, .search-input input:focus { outline: none; border-color: var(--terracotta); }
.barrio-combobox ul {
  position: absolute; top: calc(100% + 4px); left: 0; right: 0; z-index: 10;
  background: var(--ink-700); border: 1px solid var(--ink-600); border-radius: 6px;
  margin: 0; padding: 4px; list-style: none; max-height: 240px; overflow-y: auto;
}
.barrio-combobox li { padding: 8px 12px; border-radius: 4px; cursor: pointer; }
.barrio-combobox li.active { background: var(--ink-600); }
.entry-geo {
  background: var(--ink-700); border: 1px solid rgba(34, 48, 76, 0.6); border-radius: 6px;
  padding: 0 12px; cursor: pointer; color: var(--sand-dim); white-space: nowrap;
}
.entry-geo:hover { color: var(--terracotta); border-color: var(--terracotta); }
.entry-geo-error { color: var(--err); margin: 0; font-size: 13px; }
.search-input { display: flex; gap: 8px; }
.search-input button {
  background: var(--terracotta); border: none; border-radius: 6px; padding: 0 20px;
  color: var(--ink-900); font-weight: 600; cursor: pointer;
}
.search-input button:disabled { opacity: 0.4; cursor: not-allowed; }
```

- [ ] **Step 5: Verify** — `npm run build` → exit 0. `npm run dev`, open `/`: headline renders, combobox filters "mala" → Malasaña (accent-insensitive), submit disabled until location + query set, submit navigates to `/results?q=…&near=Malasaña&radius=2`.

- [ ] **Step 6: Commit** — `git commit -m "feat(frontend): entry screen with barrio autocomplete and geolocation"`

---

### Task 4: Results layout — TopBar + ResultsPanel (no map yet)

**Files:**
- Modify: `frontend/src/routes/results.tsx`
- Create: `frontend/src/components/TopBar.tsx`, `frontend/src/components/ResultsPanel.tsx`, `frontend/src/components/ShopCard.tsx`, `frontend/src/components/results.css`

**Interfaces:**
- Consumes: existing queries in `results.tsx`, `SearchInput`, `useLang`, `t`, `formatDistance`, `formatPrice`.
- Produces (consumed by Tasks 5–6):
  - `type RankedResult = NonNullable<RankedShops["results"]>[number]`  (exported from `results.tsx`)
  - `<ShopCard result pinged={boolean} selected={boolean} onSelect={(id: string) => void} lang />`
  - `<ResultsPanel>` props: `{ query: UseQueryResult<RankedShops>, pingedIds: Set<string>, selectedShopId: string | null, onSelect: (id: string | null) => void, lang: Lang, onWiden: () => void, onRetry: () => void }`
  - `results.tsx` holds `const [selectedShopId, setSelectedShopId] = useState<string | null>(null)` shared with the map. Until Task 5, `pingedIds` is `new Set(results.map(r => r.shop_id))` (all pinged, no stagger); Task 5 replaces it with `usePingSequence`. `<MapPanel>` slot renders `<div className="map-panel" />` placeholder until Task 6.
  - `CATEGORY_ICONS: Record<string, string>` exported from `ShopCard.tsx`: `{ pharmacy: "⚕", grocery: "⛁", hardware: "⚒", electronics: "⚡", stationery: "✎" }`.

- [ ] **Step 1: ShopCard** — `src/components/ShopCard.tsx` (anatomy from spec §5.4):

```tsx
import { formatDistance, formatPrice } from "../lib/format";
import { t, type Lang } from "../i18n/strings";
import type { RankedResult } from "../routes/results";

export const CATEGORY_ICONS: Record<string, string> = {
  pharmacy: "⚕", grocery: "⛁", hardware: "⚒", electronics: "⚡", stationery: "✎",
};

interface Props {
  result: RankedResult;
  pinged: boolean;
  selected: boolean;
  onSelect: (shopId: string | null) => void;
  lang: Lang;
}

export default function ShopCard({ result: r, pinged, selected, onSelect, lang }: Props) {
  const lowStock = r.stock_qty <= 3;
  return (
    <article
      className={`shop-card cat-${r.category}${selected ? " selected" : ""}${pinged ? " pinged" : ""}`}
      onClick={() => onSelect(r.shop_id)}
      onMouseEnter={() => onSelect(r.shop_id)}
      onMouseLeave={() => onSelect(null)}
    >
      <header>
        <span className="mono rank">#{r.rank}</span>
        <span className="cat-icon" aria-label={r.category}>{CATEGORY_ICONS[r.category]}</span>
        <h3>{r.shop_name}</h3>
        {pinged && <span className="ping-badge microcaps"><span className="ping-dot" /> {t(lang, "results.ping")}</span>}
        <span className="mono distance">{formatDistance(r.distance_km, lang)}</span>
      </header>
      <p className="item-name">{r.item_name}</p>
      <p className="data-row">
        <span className="mono price">{formatPrice(r.price)}</span>
        <span className="dot-sep">·</span>
        <span className={`mono stock${lowStock ? " low" : ""}`}>
          {lowStock ? t(lang, "results.lowStock", { n: r.stock_qty }) : `${t(lang, "results.stock")} ${r.stock_qty}`}
        </span>
        {r.address && (<><span className="dot-sep">·</span><span className="address">{r.address}</span></>)}
      </p>
    </article>
  );
}
```

- [ ] **Step 2: ResultsPanel** — `src/components/ResultsPanel.tsx`:

```tsx
import type { UseQueryResult } from "@tanstack/react-query";

import ShopCard from "./ShopCard";
import { t, type Lang } from "../i18n/strings";
import type { RankedShops } from "../types/RankedShops";
import type { RankedResult } from "../routes/results";

interface Props {
  query: UseQueryResult<RankedShops>;
  pingedIds: Set<string>;
  selectedShopId: string | null;
  onSelect: (id: string | null) => void;
  lang: Lang;
  radiusKm: number;
  onWiden: () => void;
  onRetry: () => void;
}

export default function ResultsPanel({ query, pingedIds, selectedShopId, onSelect, lang, radiusKm, onWiden, onRetry }: Props) {
  const { data, isPending, isError, error } = query;

  if (isPending) {
    return (
      <div className="results-panel">
        <p className="results-meta microcaps">{t(lang, "results.loading")}</p>
        {Array.from({ length: 5 }, (_, i) => <div key={i} className="skeleton-card" />)}
      </div>
    );
  }

  if (isError || data.status !== "ok") {
    const detail = isError ? (error as Error).message : JSON.stringify(data.error ?? data.missing_fields);
    return (
      <div className="results-panel state">
        <p>{t(lang, "results.error")}</p>
        <p className="mono error-detail">{detail}</p>
        <button className="cta" onClick={onRetry}>{t(lang, "results.retry")}</button>
      </div>
    );
  }

  const results: RankedResult[] = data.results ?? [];
  if (results.length === 0) {
    return (
      <div className="results-panel state">
        <p>{t(lang, "results.empty", { r: radiusKm })}</p>
        {radiusKm < 5 && <button className="cta" onClick={onWiden}>{t(lang, "results.widen")}</button>}
      </div>
    );
  }

  const generatedAt = data.generated_at ? new Date(data.generated_at).toLocaleTimeString("es-ES") : "";
  return (
    <div className="results-panel">
      <p className="results-meta microcaps">
        {results.length} {t(lang, results.length === 1 ? "results.shop" : "results.shops")} · {radiusKm} km · <span className="mono">{generatedAt}</span>
      </p>
      {results.map((r) => (
        <ShopCard key={r.shop_id} result={r} lang={lang}
          pinged={pingedIds.has(r.shop_id)}
          selected={selectedShopId === r.shop_id}
          onSelect={onSelect} />
      ))}
    </div>
  );
}
```

- [ ] **Step 3: TopBar** — `src/components/TopBar.tsx` (RadiusSlider + LangToggle inline; slider debounces 400 ms then writes URL):

```tsx
import { useEffect, useRef, useState } from "react";

import SearchInput from "./SearchInput";
import { t, type Lang } from "../i18n/strings";

interface Props {
  q: string;
  near: string | null;
  radiusKm: number;
  lang: Lang;
  onSearch: (q: string) => void;
  onRadius: (km: number) => void;
  onLang: (l: Lang) => void;
}

export default function TopBar({ q, near, radiusKm, lang, onSearch, onRadius, onLang }: Props) {
  const [draft, setDraft] = useState(q);
  const [radiusDraft, setRadiusDraft] = useState(radiusKm);
  const timer = useRef<number>(undefined);
  useEffect(() => setDraft(q), [q]);
  useEffect(() => setRadiusDraft(radiusKm), [radiusKm]);

  function handleRadius(km: number) {
    setRadiusDraft(km);
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => onRadius(km), 400);
  }

  return (
    <header className="top-bar">
      <a className="wordmark" href="/">Reach<span>Out</span></a>
      {near && <span className="barrio-chip microcaps">{near}</span>}
      <SearchInput value={draft} onChange={setDraft} onSubmit={() => onSearch(draft)} lang={lang} />
      <label className="radius-slider microcaps">
        {t(lang, "topbar.radius")}
        <input type="range" min={0.5} max={5} step={0.5} value={radiusDraft}
          onChange={(e) => handleRadius(Number(e.target.value))} />
        <span className="mono">{radiusDraft.toFixed(1)} km</span>
      </label>
      <div className="lang-toggle microcaps">
        <button className={lang === "es" ? "on" : ""} onClick={() => onLang("es")}>ES</button>
        <button className={lang === "en" ? "on" : ""} onClick={() => onLang("en")}>EN</button>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Rewrite `src/routes/results.tsx`** — keep both existing queries verbatim; add the all-shops query, layout, shared selection, URL mutators:

```tsx
/** Results: split view. URL stays the state of record; this file only adds
 * presentation state (selection, ping sequence) on top of the two queries. */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { fetchAllShops, fetchRankedShops, fetchShopsGeoJSON, type SearchParams } from "../api/client";
import ResultsPanel from "../components/ResultsPanel";
import TopBar from "../components/TopBar";
import { useLang } from "../hooks/useLang";
import type { RankedShops } from "../types/RankedShops";
import "../components/results.css";

export type RankedResult = NonNullable<RankedShops["results"]>[number];

function paramsFromUrl(searchParams: URLSearchParams): SearchParams {
  const lat = searchParams.get("lat");
  const lng = searchParams.get("lng");
  const radius = searchParams.get("radius");
  return {
    q: searchParams.get("q") ?? "",
    near: searchParams.get("near") ?? undefined,
    lat: lat !== null ? Number(lat) : undefined,
    lng: lng !== null ? Number(lng) : undefined,
    radius: radius !== null ? Number(radius) : undefined,
  };
}

export default function ResultsRoute() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [lang, setLang] = useLang();
  const [selectedShopId, setSelectedShopId] = useState<string | null>(null);
  const params = paramsFromUrl(searchParams);
  const radiusKm = params.radius ?? 2;
  const enabled = params.q.length > 0;

  const rankedShops = useQuery({
    queryKey: ["ranked-shops", params],
    queryFn: () => fetchRankedShops(params),
    enabled,
  });

  const shopsGeoJSON = useQuery({
    queryKey: ["shops-geojson", params],
    queryFn: () => fetchShopsGeoJSON(params),
    enabled,
  });

  const allShops = useQuery({
    queryKey: ["all-shops"],
    queryFn: fetchAllShops,
    staleTime: Infinity,
  });

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(searchParams);
    next.set(key, value);
    setSearchParams(next);
  }

  const results = rankedShops.data?.status === "ok" ? rankedShops.data.results ?? [] : [];
  const pingedIds = new Set(results.map((r) => r.shop_id)); // Task 5 replaces with usePingSequence

  return (
    <div className="results-screen">
      <TopBar q={params.q} near={params.near ?? null} radiusKm={radiusKm} lang={lang}
        onSearch={(q) => setParam("q", q)}
        onRadius={(km) => setParam("radius", String(km))}
        onLang={setLang} />
      <div className="split">
        <ResultsPanel query={rankedShops} pingedIds={pingedIds}
          selectedShopId={selectedShopId} onSelect={setSelectedShopId}
          lang={lang} radiusKm={radiusKm}
          onWiden={() => setParam("radius", "5")}
          onRetry={() => { void rankedShops.refetch(); void shopsGeoJSON.refetch(); }} />
        <div className="map-panel" data-allshops={allShops.status} />
      </div>
    </div>
  );
}
```

- [ ] **Step 5: results.css** — `src/components/results.css` (layout + card + top bar + states; 4 px grid, 420 px panel, 56 px bar; card entrance animation is added in Task 5's CSS step, only base styles here):

```css
.results-screen { height: 100%; display: flex; flex-direction: column; }
.split { flex: 1; display: flex; min-height: 0; }
.results-panel { width: 420px; min-width: 360px; overflow-y: auto; background: var(--ink-800); padding: 8px; }
.map-panel { flex: 1; position: relative; background: var(--ink-900); }
@media (max-width: 900px) {
  .split { flex-direction: column-reverse; }
  .results-panel { width: 100%; flex: 1; }
  .map-panel { height: 45vh; flex: none; }
}

.top-bar {
  height: 56px; flex: none; display: flex; align-items: center; gap: 16px;
  padding: 0 16px; background: var(--ink-700); border-bottom: 1px solid rgba(34, 48, 76, 0.6);
}
.wordmark { font-family: var(--font-display); font-weight: 600; font-size: 22px; color: var(--sand); text-decoration: none; }
.wordmark span { color: var(--terracotta); }
.barrio-chip { border: 1px solid var(--navy-line); border-radius: 999px; padding: 3px 10px; color: var(--sand-dim); }
.top-bar .search-input { flex: 1; max-width: 480px; }
.top-bar .search-input input { padding: 8px 12px; }
.top-bar .search-input button { padding: 0 14px; }
.radius-slider { display: flex; align-items: center; gap: 8px; color: var(--sand-dim); }
.radius-slider input { accent-color: var(--terracotta); width: 120px; }
.radius-slider .mono { color: var(--sand); min-width: 52px; }
.lang-toggle { display: flex; gap: 4px; }

.results-meta { color: var(--sand-dim); padding: 8px 12px; margin: 0; }
.results-meta .mono { color: var(--sand-dim); }

.shop-card {
  padding: 12px; border-radius: 6px; cursor: pointer;
  border-left: 2px solid transparent;
  border-bottom: 1px solid rgba(34, 48, 76, 0.6);
  background: var(--ink-800);
}
.shop-card:hover, .shop-card.selected { background: var(--ink-600); }
.shop-card.cat-pharmacy { --cat: var(--cat-pharmacy); }
.shop-card.cat-grocery { --cat: var(--cat-grocery); }
.shop-card.cat-hardware { --cat: var(--cat-hardware); }
.shop-card.cat-electronics { --cat: var(--cat-electronics); }
.shop-card.cat-stationery { --cat: var(--cat-stationery); }
.shop-card:hover, .shop-card.selected { border-left-color: var(--cat); }
.shop-card header { display: flex; align-items: baseline; gap: 8px; }
.shop-card .rank { color: var(--sand-dim); font-size: 13px; }
.shop-card .cat-icon { color: var(--cat); font-size: 15px; }
.shop-card h3 { font-family: var(--font-display); font-size: 14px; font-weight: 600; margin: 0; flex: 1; }
.shop-card .distance { margin-left: auto; color: var(--sand-dim); }
.shop-card .item-name { margin: 4px 0 0 0; color: var(--sand); }
.shop-card .data-row { margin: 4px 0 0 0; display: flex; gap: 8px; align-items: baseline; color: var(--sand-dim); }
.shop-card .price { color: var(--gold); }
.shop-card .stock.low { color: var(--cat-hardware); }
.shop-card .address { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.dot-sep { color: var(--navy-line); }

.ping-badge { color: var(--terracotta-hot); display: inline-flex; align-items: center; gap: 4px; }
.ping-dot { width: 6px; height: 6px; border-radius: 50%; background: var(--terracotta-hot); }

.skeleton-card {
  height: 92px; border-radius: 6px; margin-bottom: 8px;
  background: linear-gradient(100deg, var(--ink-700) 40%, var(--ink-600) 50%, var(--ink-700) 60%);
  background-size: 200% 100%; animation: shimmer 1.4s infinite linear;
}
@keyframes shimmer { to { background-position: -200% 0; } }

.results-panel.state { display: flex; flex-direction: column; gap: 12px; padding: 32px 24px; }
.error-detail { color: var(--err); font-size: 12px; word-break: break-word; }
.cta {
  align-self: flex-start; background: var(--terracotta); color: var(--ink-900);
  border: none; border-radius: 6px; padding: 10px 16px; font-weight: 600; cursor: pointer;
}
```

- [ ] **Step 6: Verify** — `npm run build` → exit 0. With backend running (`uvicorn server:app --port 8000` from `reachout/api/`), search "paracetamol" near Malasaña: cards render with rank/icon/name/PING/distance/item/price/stock; radius slider updates URL after 400 ms and refetches; ES/EN toggle flips copy; empty + error states reachable (query gibberish → 422 → error state).

- [ ] **Step 7: Commit** — `git commit -m "feat(frontend): results split layout, top bar, shop cards, states"`

---

### Task 5: `usePingSequence` — staggered ping state (TDD)

**Files:**
- Create: `frontend/src/hooks/usePingSequence.ts`
- Test: `frontend/src/hooks/usePingSequence.test.ts`
- Modify: `frontend/src/routes/results.tsx` (swap the all-at-once `pingedIds`), `frontend/src/components/results.css` (ping pulse + card entrance)

**Interfaces:**
- Consumes: `RankedResult[]` (rank-ordered as delivered).
- Produces: `usePingSequence(results: RankedResult[] | undefined, searchKey: string): Set<string>` — returns the ids pinged *so far*; restarts when `searchKey` changes; stagger = min(120, 2500/N) ms per shop; empty/undefined input → empty set. Honors reduced motion by pinging everything immediately.

- [ ] **Step 1: Failing test** — `src/hooks/usePingSequence.test.ts`:

```ts
import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { usePingSequence } from "./usePingSequence";
import type { RankedResult } from "../routes/results";

const mk = (id: string, rank: number): RankedResult => ({
  rank, shop_id: id, shop_name: id, category: "pharmacy", address: null,
  distance_km: 0.5, item_name: "x", sku: "PHA-0001", price: 1, currency: "EUR",
  stock_qty: 2, lat: 40.4, lng: -3.7,
});

describe("usePingSequence", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("pings shops one by one, 120ms apart, in rank order", () => {
    const results = [mk("osm:node:1", 1), mk("osm:node:2", 2), mk("osm:node:3", 3)];
    const { result } = renderHook(() => usePingSequence(results, "k1"));
    expect(result.current.size).toBe(0);
    act(() => vi.advanceTimersByTime(120));
    expect([...result.current]).toEqual(["osm:node:1"]);
    act(() => vi.advanceTimersByTime(240));
    expect(result.current.size).toBe(3);
  });

  it("restarts when the search key changes", () => {
    const results = [mk("osm:node:1", 1)];
    const { result, rerender } = renderHook(({ k }) => usePingSequence(results, k), { initialProps: { k: "a" } });
    act(() => vi.advanceTimersByTime(120));
    expect(result.current.size).toBe(1);
    rerender({ k: "b" });
    expect(result.current.size).toBe(0);
  });

  it("caps total sequence at 2.5s for long lists", () => {
    const results = Array.from({ length: 50 }, (_, i) => mk(`osm:node:${i}`, i + 1));
    const { result } = renderHook(() => usePingSequence(results, "k"));
    act(() => vi.advanceTimersByTime(2500));
    expect(result.current.size).toBe(50);
  });
});
```

- [ ] **Step 2: Run, expect FAIL** — `npx vitest run src/hooks/usePingSequence.test.ts`. Expected: module not found.

- [ ] **Step 3: Implement** — `src/hooks/usePingSequence.ts`:

```ts
/** Ping timing is presentation, not data (spec D1): every matched shop IS
 * pinged; this hook only staggers when each one lights up. */
import { useEffect, useRef, useState } from "react";
import type { RankedResult } from "../routes/results";

const STEP_MS = 120;
const TOTAL_CAP_MS = 2500;

export function usePingSequence(results: RankedResult[] | undefined, searchKey: string): Set<string> {
  const [pinged, setPinged] = useState<Set<string>>(new Set());
  const ids = (results ?? []).map((r) => r.shop_id).join(",");
  const idsRef = useRef(ids);
  idsRef.current = ids;

  useEffect(() => {
    setPinged(new Set());
    const shopIds = idsRef.current ? idsRef.current.split(",") : [];
    if (shopIds.length === 0) return;

    const reduced = typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduced) {
      setPinged(new Set(shopIds));
      return;
    }

    const step = Math.min(STEP_MS, TOTAL_CAP_MS / shopIds.length);
    const timers = shopIds.map((id, i) =>
      window.setTimeout(() => setPinged((prev) => new Set(prev).add(id)), Math.round(step * (i + 1))),
    );
    return () => timers.forEach(clearTimeout);
  }, [searchKey, ids]);

  return pinged;
}
```

- [ ] **Step 4: Run, expect PASS** — `npx vitest run`. Expected: all green.

- [ ] **Step 5: Wire into results.tsx** — replace the `pingedIds` line:

```tsx
import { usePingSequence } from "../hooks/usePingSequence";
// …
const searchKey = searchParams.toString();
const pingedIds = usePingSequence(rankedShops.data?.status === "ok" ? rankedShops.data.results : undefined, searchKey);
```

- [ ] **Step 6: Motion CSS** — append to `results.css` (card entrance synced to ping; pre-ping cards sit dim; badge dot pulses 3× then settles — reduced-motion is already globally disabled in tokens.css):

```css
.shop-card { opacity: 0.35; transition: opacity 0.3s; }
.shop-card.pinged { opacity: 1; animation: card-in 0.3s ease-out; }
@keyframes card-in { from { transform: translateY(12px); opacity: 0.35; } to { transform: none; opacity: 1; } }
.shop-card.pinged .ping-dot { animation: ping-pulse 0.4s ease-out 3; }
@keyframes ping-pulse { 50% { box-shadow: 0 0 0 5px rgba(255, 138, 102, 0.35); } }
@media (prefers-reduced-motion: reduce) { .shop-card { opacity: 1; } }
```

- [ ] **Step 7: Verify + commit** — `npm run build && npx vitest run` → clean; in the browser cards light up in rank order. `git commit -m "feat(frontend): staggered ping sequence hook and card motion"`

---

### Task 6: MapPanel — MapLibre, network layer, pins, pings, lines, popup

**Files:**
- Create: `frontend/src/components/MapPanel.tsx`, `frontend/src/map/map-layers.ts`
- Modify: `frontend/src/routes/results.tsx` (replace placeholder div), `frontend/src/components/results.css` (popup + marker styles), `frontend/src/routes/search.tsx` + `entry.css` (network backdrop, Step 7)
- Test: `frontend/src/map/map-layers.test.ts`

**Interfaces:**
- Consumes: `shopsGeoJSON.data` (`ShopMapGeoJSON`), `allShops.data` (`ShopsGeoJSON`), `pingedIds`, `selectedShopId`, `onSelect`, user center (from geojson metadata), `radiusKm`, `CATEGORY_ICONS`.
- Produces:
  - `<MapPanel matched={ShopMapGeoJSON | undefined} network={ShopsGeoJSON | undefined} pingedIds selectedShopId onSelect lang />`
  - Pure helpers in `map-layers.ts`: `pingLinesFC(center: {lat,lng}, matched: ShopMapGeoJSON, pingedIds: Set<string>): GeoJSON.FeatureCollection` and `radiusRingFC(center: {lat,lng}, radiusKm: number): GeoJSON.FeatureCollection` (64-segment circle polygon line).

- [ ] **Step 1: Failing tests for the pure helpers** — `src/map/map-layers.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { pingLinesFC, radiusRingFC } from "./map-layers";

const matched = {
  type: "FeatureCollection",
  metadata: { query: "x", generated_at: "", result_count: 1, center: { lat: 40.42, lng: -3.70 }, radius_km: 2 },
  features: [{
    type: "Feature",
    geometry: { type: "Point", coordinates: [-3.7035, 40.427] },
    properties: { shop_id: "osm:node:1", shop_name: "F", rank: 1, category: "pharmacy",
      address: null, distance_km: 0.4, item_name: "p", price: 1, currency: "EUR", stock_qty: 2 },
  }],
} as never;

describe("map-layers", () => {
  it("draws one line per pinged shop, user first", () => {
    const fc = pingLinesFC({ lat: 40.42, lng: -3.7 }, matched, new Set(["osm:node:1"]));
    expect(fc.features).toHaveLength(1);
    expect((fc.features[0].geometry as GeoJSON.LineString).coordinates[0]).toEqual([-3.7, 40.42]);
  });
  it("skips unpinged shops", () => {
    const fc = pingLinesFC({ lat: 40.42, lng: -3.7 }, matched, new Set());
    expect(fc.features).toHaveLength(0);
  });
  it("builds a closed 64-segment ring", () => {
    const fc = radiusRingFC({ lat: 40.42, lng: -3.7 }, 2);
    const coords = (fc.features[0].geometry as GeoJSON.LineString).coordinates;
    expect(coords).toHaveLength(65);
    expect(coords[0]).toEqual(coords[64]);
  });
});
```

- [ ] **Step 2: Run, expect FAIL**, then implement `src/map/map-layers.ts`:

```ts
/** Pure GeoJSON builders for the map's derived layers. No maplibre imports —
 * unit-testable in jsdom. */
import type { ShopMapGeoJSON } from "../types/MapGeojson";

export interface Center { lat: number; lng: number }

export function pingLinesFC(center: Center, matched: ShopMapGeoJSON, pingedIds: Set<string>): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: matched.features
      .filter((f) => pingedIds.has(f.properties.shop_id))
      .map((f) => ({
        type: "Feature" as const,
        geometry: {
          type: "LineString" as const,
          coordinates: [[center.lng, center.lat], f.geometry.coordinates as [number, number]],
        },
        properties: { shop_id: f.properties.shop_id },
      })),
  };
}

export function radiusRingFC(center: Center, radiusKm: number): GeoJSON.FeatureCollection {
  const R = 6371;
  const dLat = (radiusKm / R) * (180 / Math.PI);
  const dLng = dLat / Math.cos((center.lat * Math.PI) / 180);
  const coords: [number, number][] = Array.from({ length: 65 }, (_, i) => {
    const a = (i % 64) * ((2 * Math.PI) / 64);
    return [center.lng + dLng * Math.cos(a), center.lat + dLat * Math.sin(a)];
  });
  return {
    type: "FeatureCollection",
    features: [{ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} }],
  };
}
```

Run `npx vitest run src/map/map-layers.test.ts` → PASS.

- [ ] **Step 3: MapPanel** — `src/components/MapPanel.tsx`. One map instance per mount; sources created on `load`; data pushed via `setData` in effects. Complete code:

```tsx
import maplibregl, { Map as MLMap, Popup } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";

import { pingLinesFC, radiusRingFC, type Center } from "../map/map-layers";
import { formatDistance, formatPrice } from "../lib/format";
import { CATEGORY_ICONS } from "./ShopCard";
import { t, type Lang } from "../i18n/strings";
import type { ShopMapGeoJSON } from "../types/MapGeojson";
import type { ShopsGeoJSON } from "../types/ShopsGeojson";

const STYLE_URL = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";
const MADRID: [number, number] = [-3.7038, 40.4168];
const EMPTY: GeoJSON.FeatureCollection = { type: "FeatureCollection", features: [] };
const CAT_COLOR: maplibregl.ExpressionSpecification = [
  "match", ["get", "category"],
  "pharmacy", "#7fb069", "grocery", "#b8d97e", "hardware", "#f4a259",
  "electronics", "#5bc0eb", "stationery", "#c77dff", "#e2725b",
];

interface Props {
  matched: ShopMapGeoJSON | undefined;
  network: ShopsGeoJSON | undefined;
  pingedIds: Set<string>;
  selectedShopId: string | null;
  onSelect: (id: string | null) => void;
  lang: Lang;
}

function setData(map: MLMap, id: string, fc: GeoJSON.FeatureCollection) {
  const src = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  src?.setData(fc);
}

export default function MapPanel({ matched, network, pingedIds, selectedShopId, onSelect, lang }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MLMap | null>(null);
  const loadedRef = useRef(false);
  const popupRef = useRef<Popup | null>(null);
  const userMarkerRef = useRef<maplibregl.Marker | null>(null);

  useEffect(() => {
    const map = new maplibregl.Map({
      container: container.current!, style: STYLE_URL, center: MADRID, zoom: 13, attributionControl: { compact: true },
    });
    mapRef.current = map;

    map.on("load", () => {
      for (const id of ["network", "ring", "lines", "matched"]) {
        map.addSource(id, { type: "geojson", data: EMPTY });
      }
      map.addLayer({ id: "network-shops", source: "network", type: "circle",
        paint: { "circle-radius": 3, "circle-color": "#3a4e78", "circle-opacity": 0.55 } });
      map.addLayer({ id: "radius-ring", source: "ring", type: "line",
        paint: { "line-color": "#e2725b", "line-opacity": 0.25, "line-width": 1.5, "line-dasharray": [2, 3] } });
      map.addLayer({ id: "ping-lines", source: "lines", type: "line",
        paint: { "line-color": "#e2725b", "line-opacity": 0.4, "line-width": 1 } });
      map.addLayer({ id: "matched-shops", source: "matched", type: "circle",
        paint: {
          "circle-radius": ["+", 6, ["*", 2, ["sqrt", ["get", "stock_qty"]]]],
          "circle-color": CAT_COLOR,
          "circle-stroke-width": ["case", ["boolean", ["feature-state", "selected"], false], 3, 1.5],
          "circle-stroke-color": ["case", ["boolean", ["feature-state", "selected"], false], "#ff8a66", "#ead9bd"],
          "circle-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0],
          "circle-stroke-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0],
        } });
      map.addLayer({ id: "rank-labels", source: "matched", type: "symbol",
        filter: ["<=", ["get", "rank"], 10],
        layout: { "text-field": ["concat", "#", ["to-string", ["get", "rank"]]],
          "text-size": 11, "text-offset": [0, -1.6], "text-font": ["Open Sans Bold"] },
        paint: { "text-color": "#ead9bd",
          "text-opacity": ["case", ["boolean", ["feature-state", "pinged"], false], 1, 0] } });

      map.on("mouseenter", "matched-shops", () => { map.getCanvas().style.cursor = "pointer"; });
      map.on("mouseleave", "matched-shops", () => { map.getCanvas().style.cursor = ""; });
      map.on("click", "matched-shops", (e) => {
        const f = e.features?.[0];
        if (f?.properties) onSelectRef.current(String(f.properties.shop_id));
      });

      loadedRef.current = true;
      setLoaded((n) => n + 1); // re-run data effects now that sources exist
    });

    return () => { loadedRef.current = false; map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Track a render counter so data effects re-fire after `load`.
  const [, setLoaded] = useReducerCounter();
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Network layer (static).
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || !network) return;
    setData(map, "network", network as unknown as GeoJSON.FeatureCollection);
  });

  // Matched shops + ring + user dot + camera, when a new result set arrives.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || !matched) return;
    const center: Center = matched.metadata.center;
    setData(map, "matched", withIds(matched));
    setData(map, "ring", radiusRingFC(center, matched.metadata.radius_km));

    userMarkerRef.current?.remove();
    const el = document.createElement("div");
    el.className = "user-dot";
    el.title = t(lang, "map.you");
    userMarkerRef.current = new maplibregl.Marker({ element: el }).setLngLat([center.lng, center.lat]).addTo(map);

    const bounds = new maplibregl.LngLatBounds([center.lng, center.lat], [center.lng, center.lat]);
    for (const f of matched.features) bounds.extend(f.geometry.coordinates as [number, number]);
    map.fitBounds(bounds, { padding: 60, duration: 600, maxZoom: 16 });
  });

  // Ping state → feature-state + lines.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current || !matched) return;
    for (const f of matched.features) {
      map.setFeatureState({ source: "matched", id: fid(f.properties.shop_id) },
        { pinged: pingedIds.has(f.properties.shop_id), selected: f.properties.shop_id === selectedShopId });
    }
    setData(map, "lines", pingLinesFC(matched.metadata.center, matched, pingedIds));
  });

  // Popup follows selection.
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !loadedRef.current) return;
    popupRef.current?.remove();
    const f = matched?.features.find((x) => x.properties.shop_id === selectedShopId);
    if (!f) return;
    const p = f.properties;
    popupRef.current = new Popup({ closeButton: false, offset: 14, className: "shop-popup" })
      .setLngLat(f.geometry.coordinates as [number, number])
      .setHTML(
        `<strong>${CATEGORY_ICONS[p.category]} ${esc(p.shop_name)}</strong>` +
        `<div>${esc(p.item_name)}</div>` +
        `<div class="mono">${formatPrice(p.price)} · ${t(lang, "results.stock")} ${p.stock_qty} · ${formatDistance(p.distance_km, lang)}</div>`,
      )
      .addTo(map);
  });

  return <div ref={container} className="map-panel" />;
}

/** Numeric feature ids are required for setFeatureState; derive from osm id. */
function fid(shopId: string): number {
  return Number(shopId.split(":")[2]);
}

function withIds(matched: ShopMapGeoJSON): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: matched.features.map((f) => ({ ...(f as unknown as GeoJSON.Feature), id: fid(f.properties.shop_id) })),
  };
}

function esc(s: string): string {
  return s.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);
}

import { useState } from "react";
function useReducerCounter(): [number, (fn: (n: number) => number) => void] {
  return useState(0);
}
```

(Implementer note: hoist the `useState` import to the top with the other imports and inline `useState(0)` instead of the `useReducerCounter` indirection if it reads cleaner — the behavior contract is only "data effects re-run after map load". Effects intentionally have no dep arrays: they run every render and early-return until the map is loaded; each is idempotent.)

- [ ] **Step 4: Wire into results.tsx** — replace `<div className="map-panel" … />` with:

```tsx
<MapPanel matched={shopsGeoJSON.data} network={allShops.data}
  pingedIds={pingedIds} selectedShopId={selectedShopId} onSelect={setSelectedShopId} lang={lang} />
```

- [ ] **Step 5: Map CSS** — append to `results.css`:

```css
.user-dot {
  width: 10px; height: 10px; border-radius: 50%; background: var(--sand);
  box-shadow: 0 0 0 4px rgba(234, 217, 189, 0.2);
  animation: breathe 2s ease-in-out infinite;
}
@keyframes breathe { 50% { box-shadow: 0 0 0 9px rgba(234, 217, 189, 0.08); } }
.shop-popup .maplibregl-popup-content {
  background: var(--ink-700); color: var(--sand); border: 1px solid var(--ink-600);
  border-radius: 6px; padding: 10px 12px; font-family: var(--font-ui); font-size: 13px;
}
.shop-popup .maplibregl-popup-tip { border-top-color: var(--ink-700); }
.shop-popup .mono { color: var(--gold); font-family: var(--font-mono); font-size: 12px; }
```

- [ ] **Step 6: Verify interactions** — build clean; in browser: network dots visible pre-results; search → pins appear as their ping fires, lines draw user→shop and persist, radius ring dashed; card hover rings its pin; pin click selects card + popup; rank labels on top 10.

- [ ] **Step 7: Entry backdrop** — in `search.tsx`, fetch all shops with the same `useQuery({ queryKey: ["all-shops"], queryFn: fetchAllShops, staleTime: Infinity })` and render absolutely-positioned dots behind the card (no MapLibre on entry — cheap SVG projection):

```tsx
{allShops.data && (
  <svg className="entry-net" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid slice" aria-hidden>
    {allShops.data.features.map((f, i) => {
      const [lng, lat] = f.geometry.coordinates;
      const x = ((lng - -3.78) / 0.16) * 100;
      const y = ((40.48 - lat) / 0.12) * 100;
      return <circle key={f.properties.shop_id} cx={x} cy={y} r={0.35}
        style={{ animationDelay: `${(i % 20) * 0.3}s` }} />;
    })}
  </svg>
)}
```

CSS append to `entry.css`:

```css
.entry-net { position: absolute; inset: 0; width: 100%; height: 100%; }
.entry-net circle { fill: var(--navy-line); opacity: 0.5; animation: net-pulse 6s ease-in-out infinite; }
@keyframes net-pulse { 50% { opacity: 0.15; } }
.entry-card { position: relative; z-index: 1; }
```

- [ ] **Step 8: Full check + commit** — `npm run build && npx vitest run` → clean; `cd reachout/tests && python -m pytest test_api.py -v` → PASS. `git commit -m "feat(frontend): maplibre map with network layer, pings, lines, popup, entry backdrop"`

---

### Task 7: End-to-end verification pass

**Files:** none new — fixes only, wherever the walkthrough finds them.

- [ ] **Step 1: Start backend** — `cd reachout/api && uvicorn server:app --port 8000` (env `REACHOUT_OFFLINE=1` if Overpass/Nominatim unreachable).
- [ ] **Step 2: Start frontend** — `cd frontend && npm run dev`.
- [ ] **Step 3: Walk the spec's flow diagram (§3)** end to end, both languages, checking every edge: geolocation denial notice, empty state + widen CTA (radius jumps to 5 and refetches), error state on gibberish query, back button returns to entry, URL shareable (paste `/results?...` into a fresh tab reproduces the view), reduced-motion (DevTools emulation) shows static pins/cards.
- [ ] **Step 4: Fix anything broken**, re-run `npm run build && npx vitest run` + backend pytest, commit fixes as `fix(frontend): …`.
