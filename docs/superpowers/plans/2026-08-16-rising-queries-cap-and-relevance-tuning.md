# Rising-Queries Cap + Relevance Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make every commercially relevant rising query reachable through the API, stop informational lookups from being labelled `commercial`, and merge near-duplicate phrasings that today split into separate cards.

**Architecture:** Three independent surfaces. (1) `GET /demand/api/rising-queries` gains an `offset` param, its own 1000-row ceiling, and an `X-Total-Count` header carrying the post-tier total, so nothing is silently truncated and the UI can state what it is showing. (2) `demand/api/relevance.py` gains an interrogative-head informational rule (penalised only when no retail modifier is present) and a wider clustering stopword set. (3) The frontend reads the total, pages when needed, and gets shopkeeper-facing copy explaining what the index is and why 3-month and 12-month numbers are not comparable. All scoring stays deterministic pure Python — no AI anywhere near tiering, ranking, or clustering (`CLAUDE.md`).

**Tech Stack:** Python 3 / FastAPI / supabase-py / pytest; React 19 / TanStack Query v5 / ECharts / vitest.

**Spec:** This document. The measurements in "Findings" below were taken against the live Supabase table on 2026-08-16 and are the binding numbers; the predecessor plan is `.claude/plans/recursive-enchanting-snowflake.md`.

## Global Constraints

- The five JSON Schemas in `demand/shared/schemas/` and `demand/data/schema.sql` are **frozen**. No DDL, no migration, no schema edit. `rising_query.schema.json` has `additionalProperties: false` — new per-row fields are forbidden. Headers are not part of the schema and are allowed.
- **Honesty rule:** `is_breakout: true` ⇒ `growth_pct` is `null`. Never substitute a number, including a quantified sibling's inside the same cluster.
- **No AI in scoring, tiering, ranking, or clustering.** Pure deterministic Python only.
- **Order of operations on `/rising-queries` is load-bearing:** DB read (capped at `RISING_QUERIES_READ_CAP = 5000`, ordered by `id`) → `annotate()` **once** over the whole set → tier filter → `offset`/`limit` last. `annotate()` is batch-scoped; paging before it would make a row's `cluster_id` depend on which page it landed on.
- `interest_avg` is a **rescaled relative index with no 100 ceiling** (live max 304.15). Never render it as a percentage and never label an axis "searches".
- `today 3-m` and `today 12-m` are different measurement scales. Refetch on toggle; never reslice client-side.
- Tests must pass with **no API key, no network, no database** (`demand/tests/conftest.py` blocks the network unconditionally).
- No SerpApi search is spent by any task in this plan. Budget stays at 97/250.
- Never weaken `demand/tests/fake_supa.py`'s unknown-schema/table/column guards to make a test pass.
- Baseline suites: **384 Python tests, 98 frontend tests.** Both must be green at every commit.
- `npm run build` must be run **redirected to a file, never in the foreground** — it hangs indefinitely in the foreground in this repo.

---

## Findings (measured live, 2026-08-16, 658 rows)

| Measure | Value |
|---|---|
| Rows in `demand.rising_queries` | 658 |
| Tiered `commercial` / `noise` | 602 / 56 |
| Distinct commercial `cluster_id`s | 503 |
| Rows the 500 response cap hides | **102 commercial** |
| Rows containing "eclipse" | 24, split across **11** clusters |
| Commercial rows starting with an interrogative/modal token | **19**, of which 18 are informational and 1 (`donde comprar gafas para el eclipse`) is genuinely commercial |

**Simulated result of Tasks 3–5 on the same 658 rows:** commercial 602 → 580, noise 56 → 78, commercial clusters 503 → 480, eclipse clusters 11 → 8. 23 rows flip to `noise` (all verified informational), 1 row (`gafas para el eclipse de sol`) is rescued from `noise` to `commercial`. **Zero false positives in the simulation** — these exact counts are the acceptance numbers for the live smoke check at the end.

**Why clustering under-merges.** `cluster_key()` strips `CLUSTER_STOPWORDS` and `CLUSTER_DECORATION_TOKENS`, sorts what is left, and prefixes the first surviving token as the *head*. Three things then split queries a human would group:
1. Function words that are neither stopword nor decoration survive (`se`, `puede`, `puedo`, `un`, `que`, `es`), inflating the token set so no strict-subset merge fires, and becoming the head token.
2. `_merge_subset_keys` requires an **exact head match** — deliberately, to stop `funda para gafas de sol` (a sunglasses *case*) from merging into `gafas de sol`. That guard also blocks legitimate merges like `pack bombillas led` into `bombillas led`. This is the correct failure direction and is **not** changed by this plan.
3. Word order moves the head: `eclipse gafas de sol` heads on `eclipse`, `gafas eclipse` on `gafas`. Neither token set contains the other, so no merge is even considered. Also unchanged — merging these needs a synonym/subject model, not a heuristic.

Task 4 fixes cause (1) only. It is the only one of the three where a merge is unambiguously safe.

---

### Task 1: `/rising-queries` — offset, own ceiling, total-count header

**Files:**
- Modify: `demand/api/app.py:168-175` (constants), `demand/api/app.py:852-920` (endpoint)
- Test: `demand/tests/test_api_rising_queries.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `GET /demand/api/rising-queries?limit=<1..1000>&offset=<0..>` returning a bare JSON array plus response header `X-Total-Count: <int>` = the number of rows surviving the tier filter, before `offset`/`limit`. Task 2 consumes both.

- [ ] **Step 1: Write the failing tests**

Append to `demand/tests/test_api_rising_queries.py`:

```python
def test_limit_above_500_is_allowed_up_to_the_route_ceiling(test_client):
    response = test_client.get("/demand/api/rising-queries?limit=1000")
    assert response.status_code == 200


def test_limit_above_the_route_ceiling_is_a_422(test_client):
    response = test_client.get("/demand/api/rising-queries?limit=1001")
    assert response.status_code == 422


def test_total_count_header_reports_the_full_filtered_size(test_client):
    response = test_client.get("/demand/api/rising-queries?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1
    # The header counts every commercial row, not the page.
    assert int(response.headers["X-Total-Count"]) >= 1
    unpaged = test_client.get("/demand/api/rising-queries")
    assert int(response.headers["X-Total-Count"]) == len(unpaged.json())


def test_offset_pages_without_overlap_or_loss(test_client):
    everything = test_client.get("/demand/api/rising-queries").json()
    assert len(everything) >= 2
    first = test_client.get("/demand/api/rising-queries?limit=1&offset=0").json()
    second = test_client.get("/demand/api/rising-queries?limit=1&offset=1").json()
    assert first == everything[:1]
    assert second == everything[1:2]


def test_offset_does_not_change_cluster_ids(test_client):
    """cluster_id must come from annotate() over the whole set, never a page."""
    everything = test_client.get("/demand/api/rising-queries").json()
    paged = test_client.get("/demand/api/rising-queries?limit=1&offset=1").json()
    assert paged[0]["cluster_id"] == everything[1]["cluster_id"]


def test_negative_offset_is_a_422(test_client):
    assert test_client.get("/demand/api/rising-queries?offset=-1").status_code == 422
```

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m pytest demand/tests/test_api_rising_queries.py -v -k "ceiling or total_count or offset"`
Expected: FAIL — `limit=1000` returns 422, `X-Total-Count` raises `KeyError`, `offset` is rejected as an unknown param or ignored.

- [ ] **Step 3: Add the constant**

In `demand/api/app.py`, directly after `RISING_QUERIES_READ_CAP = 5000`:

```python
#: /rising-queries has its own caller-facing ceiling, above the shared
#: MAX_PAGE_SIZE = 500 the three list endpoints use. Reason: this route's
#: rows are not a page of a browsable table, they are the input to a
#: client-side clustering render -- 602 of the 658 live rows tier
#: `commercial`, so a 500 cap silently hid 102 of them behind a caption
#: that read like a complete list. The other endpoints keep MAX_PAGE_SIZE;
#: raising that shared constant would loosen three unrelated routes.
#: Above this ceiling the answer is still a 422, never a silent clamp --
#: and X-Total-Count tells the caller what it is missing either way.
RISING_QUERIES_MAX_LIMIT = 1000
```

- [ ] **Step 4: Add `Response` to the FastAPI import**

`demand/api/app.py:45`:

```python
from fastapi import FastAPI, HTTPException, Query, Response
```

- [ ] **Step 5: Change the endpoint signature**

```python
async def get_rising_queries(
    response: Response,
    parent_keyword: Optional[str] = None,
    include: str = "commercial",
    limit: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=RISING_QUERIES_MAX_LIMIT),
    offset: int = Query(0, ge=0),
):
```

- [ ] **Step 6: Set the header and apply offset before limit**

Replace `annotated = annotated[:limit]` with:

```python
    # Set BEFORE slicing: X-Total-Count is the size of the tier-filtered
    # set, which is exactly what the caller needs to know it is looking at
    # a page. Counting after the slice would report the page size and make
    # the header useless. It is a header and not a body field on purpose --
    # rising_query.schema.json is frozen with additionalProperties: false,
    # and the response is a bare array with nowhere to put an envelope.
    response.headers["X-Total-Count"] = str(len(annotated))
    response.headers["Access-Control-Expose-Headers"] = "X-Total-Count"

    annotated = annotated[offset:offset + limit]
```

`Access-Control-Expose-Headers` is required: the browser cannot read a non-safelisted response header cross-origin without it, and the frontend runs on a different port from the API.

- [ ] **Step 7: Extend the endpoint docstring**

Amend step 4 of the numbered list in the docstring:

```
    4. Apply `offset` then `limit` LAST, after tiering, as a plain slice of
       the already-annotated, already-filtered list. Both bound what the
       caller sees, never the clustering input. `X-Total-Count` is set from
       the pre-slice length, so a caller can always tell whether it holds
       the whole filtered set or one page of it, and page the rest with
       `offset` without any row's `cluster_id` changing underneath it.
```

- [ ] **Step 8: Run the whole Python suite**

Run: `python3 -m pytest demand/tests/ -q`
Expected: PASS, 384 + 6 = 390 tests.

- [ ] **Step 9: Commit**

```bash
git add demand/api/app.py demand/tests/test_api_rising_queries.py
git commit -m "fix(demand): page /rising-queries past 500 with offset and X-Total-Count"
```

---

### Task 2: Frontend reads the total and stops guessing

**Files:**
- Modify: `frontend/src/api/client.ts:115-140`, `frontend/src/components/retail/RisingQueriesPanel.tsx:1-70`, `frontend/src/i18n/strings.ts:105-106`
- Test: `frontend/src/components/retail/RisingQueriesPanel.test.tsx`

**Interfaces:**
- Consumes: `X-Total-Count` header and `offset`/`limit` params from Task 1.
- Produces: `fetchRisingQueries(params) => Promise<{ rows: RisingQuery[]; total: number }>` — a **breaking change** to the existing `Promise<RisingQuery[]>` signature. `RisingQueriesPanel` is its only caller (`grep -rn fetchRisingQueries frontend/src` to confirm before editing).

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/components/retail/RisingQueriesPanel.test.tsx`, following the file's existing fetch-mock helper:

```tsx
it("requests the route ceiling, not the old 500 cap", async () => {
  const fetchMock = respondWith({ rows: [beerRow], total: 1 });
  render(<RisingQueriesPanel lang="en" />, { wrapper });
  await screen.findByText(/comprar cerveza barata/i);
  const url = String(fetchMock.mock.calls[0][0]);
  expect(url).toContain("limit=1000");
});

it("says how many of the total it is showing when the total is larger", async () => {
  respondWith({ rows: [beerRow], total: 1200 });
  render(<RisingQueriesPanel lang="en" />, { wrapper });
  expect(await screen.findByText(/showing 1 of 1200/i)).toBeInTheDocument();
});

it("does not say 'of N' when it holds every row", async () => {
  respondWith({ rows: [beerRow], total: 1 });
  render(<RisingQueriesPanel lang="en" />, { wrapper });
  expect(await screen.findByText(/^showing 1 rising searches?\.$/i)).toBeInTheDocument();
});
```

`respondWith` must be updated in this file to return the header — the existing helper builds a `Response`; add `{ headers: { "X-Total-Count": String(total) } }` to its init object.

- [ ] **Step 2: Run them and watch them fail**

Run (from `frontend/`): `npx vitest run src/components/retail/RisingQueriesPanel.test.tsx`
Expected: FAIL — `limit=500` in the URL, and no "of 1200" text node.

- [ ] **Step 3: Change the client**

In `frontend/src/api/client.ts`, replace the body of `fetchRisingQueries`:

```ts
export interface RisingQueriesPage {
  rows: RisingQuery[];
  /**
   * `X-Total-Count`: how many rows survived the server's tier filter,
   * before `offset`/`limit`. Larger than `rows.length` means the panel is
   * holding one page, not the whole set. Falls back to `rows.length` when
   * the header is absent or unparseable — an under-count is safe (the UI
   * simply omits the "of N"), an invented larger number would not be.
   */
  total: number;
}

export async function fetchRisingQueries(
  params: RisingQueriesParams = {},
): Promise<RisingQueriesPage> {
  const usp = new URLSearchParams();
  if (params.parentKeyword) usp.set("parent_keyword", params.parentKeyword);
  if (params.include) usp.set("include", params.include);
  if (params.limit !== undefined) usp.set("limit", String(params.limit));
  if (params.offset !== undefined) usp.set("offset", String(params.offset));
  const qs = usp.toString();
  const res = await fetch(`${DEMAND_API_BASE}/demand/api/rising-queries${qs ? `?${qs}` : ""}`);
  if (!res.ok) {
    throw new ApiError(`GET /demand/api/rising-queries failed: ${res.status}`, res.status);
  }
  const rows: RisingQuery[] = await res.json();
  const header = Number(res.headers.get("X-Total-Count"));
  return { rows, total: Number.isFinite(header) && header >= rows.length ? header : rows.length };
}
```

Add `offset?: number;` to `RisingQueriesParams` with the comment `/** Row offset for paging; cluster ids are stable across pages. */`.

- [ ] **Step 4: Change the panel**

In `RisingQueriesPanel.tsx`, replace the `RISING_QUERIES_LIMIT` block and the `useQuery`/count lines:

```tsx
/**
 * Mirrors `RISING_QUERIES_MAX_LIMIT` in `demand/api/app.py` — this route's
 * own ceiling, deliberately above the shared `MAX_PAGE_SIZE = 500` the
 * other list endpoints use. 602 of the 658 live rows tier `commercial`, so
 * the old 500 hid 102 of them. When the table outgrows 1000, the server's
 * `X-Total-Count` says so and the caption below reports it honestly
 * instead of implying completeness.
 */
const RISING_QUERIES_LIMIT = 1000;
```

```tsx
  const rising = useQuery({
    queryKey: ["rising-queries", RISING_QUERIES_LIMIT],
    queryFn: () => fetchRisingQueries({ limit: RISING_QUERIES_LIMIT }),
  });
```

```tsx
  const rowCount = rising.data.rows.length;
  const total = rising.data.total;
  const partial = total > rowCount;
  const clusters = groupRisingQueries(rising.data.rows);
```

```tsx
      <p className="rising-queries__count-line">
        {partial
          ? t(lang, "retail.risingQueries.shownPartial", { count: rowCount, total })
          : t(lang, "retail.risingQueries.shown", { count: rowCount })}
      </p>
```

- [ ] **Step 5: Replace the at-cap string**

In `frontend/src/i18n/strings.ts`, delete the `retail.risingQueries.shownAtCap` entry (it described a cap that no longer exists) and add:

```ts
  "retail.risingQueries.shownPartial": { es: "Mostrando {count} de {total} búsquedas en alza.", en: "Showing {count} of {total} rising searches." },
```

- [ ] **Step 6: Run the frontend suite and typecheck**

Run (from `frontend/`): `npx vitest run && npx tsc --noEmit`
Expected: PASS, 98 + 3 = 101 tests, tsc exit 0.

- [ ] **Step 7: Build (redirected — never in the foreground)**

```bash
cd frontend && npx vite build > /tmp/vite-build.log 2>&1; echo "EXIT=$?" >> /tmp/vite-build.log; tail -3 /tmp/vite-build.log
```
Expected: `EXIT=0`. The 2.29 MB echarts chunk warning is pre-existing.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/api/client.ts frontend/src/components/retail/RisingQueriesPanel.tsx frontend/src/components/retail/RisingQueriesPanel.test.tsx frontend/src/i18n/strings.ts
git commit -m "feat(frontend): show all rising queries and report the true total"
```

---

### Task 3: The informational filter

**Files:**
- Modify: `demand/api/relevance.py:136-139` (add constant below `INFORMATIONAL_MARKERS`), `demand/api/relevance.py:282-352` (`score_query`)
- Test: `demand/tests/test_relevance.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `INFORMATIONAL_HEAD_TOKENS: frozenset[str]`; a new `relevance_reasons` entry of the form `"informational_head:<token>"`. `score_query`'s signature and return shape are unchanged.

**The rule, stated precisely.** A query is informational when its **first** token is an interrogative or modal *and* the query carries **no retail modifier**. The modifier exemption is what the whole rule rests on: of the 19 live commercial rows with an interrogative head, exactly one — `donde comprar gafas para el eclipse` — is a real purchase intent, and the thing that distinguishes it is `comprar`. Head-position matters too: `como` in `como agua para chocolate` (a film title) is at the head and correctly caught, while a `que` buried mid-phrase is not evidence of anything. The penalty is applied **at most once** per row: a query that already matched a phrase in `INFORMATIONAL_MARKERS` (`donde tirar bombillas` matches both `"donde tirar"` and head `donde`) must not be penalised twice, or a single signal would count double.

- [ ] **Step 1: Write the failing tests**

Append to `demand/tests/test_relevance.py`:

```python
# ---------------------------------------------------------------------------
# Informational heads. All eight query strings below are verbatim live rows
# from demand.rising_queries; the first seven tiered `commercial` before this
# rule existed.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("query,parent", [
    ("se puede ver el eclipse con gafas de sol normales", "gafas de sol"),
    ("puedo mirar el eclipse con gafas de sol", "gafas de sol"),
    ("cuantos huevos puedo comer al dia", "huevos"),
    ("cuanto duran los huevos cocidos en la nevera", "huevos"),
    ("como hacer huevos cocidos", "huevos"),
    ("para que sirve el te matcha", "te"),
    ("quien invento la cerveza", "cerveza"),
])
def test_interrogative_head_tiers_as_noise(query, parent):
    result = score_query(query, parent)
    assert result["tier"] == "noise", result
    assert any(r.startswith("informational_head:") for r in result["reasons"])


def test_retail_modifier_exempts_an_interrogative_head():
    """`donde comprar ...` is a purchase, not a lookup -- the one live row
    the head rule would otherwise destroy."""
    result = score_query("donde comprar gafas para el eclipse", "gafas de sol")
    assert result["tier"] == "commercial", result
    assert not any(r.startswith("informational_head:") for r in result["reasons"])


def test_informational_penalty_is_applied_at_most_once():
    """`donde tirar bombillas` matches the phrase marker AND the head token;
    it must be charged once, not twice."""
    result = score_query("donde tirar bombillas", "bombillas")
    assert result["score"] == pytest.approx(-2.0)
    assert not any(r.startswith("informational_head:") for r in result["reasons"])
```

`test_informational_penalty_is_applied_at_most_once` asserts the exact pre-existing score of that row: `+1.0` token-count-range `-3.0` informational marker `= -2.0`. If the current value differs, run `score_query("donde tirar bombillas", "bombillas")` once and use the real number — the point of the test is that the number does not *change*.

- [ ] **Step 2: Run them and watch them fail**

Run: `python3 -m pytest demand/tests/test_relevance.py -v -k "interrogative or exempts or at_most_once"`
Expected: FAIL — the seven parametrised rows tier `commercial`.

- [ ] **Step 3: Add the constant**

In `demand/api/relevance.py`, directly below `INFORMATIONAL_MARKERS`:

```python
#: Interrogative and modal words that mean "I am looking something up",
#: but ONLY in head position and ONLY when no retail modifier is present.
#:
#: Head position, because a `que` or `como` buried mid-phrase is grammar,
#: not intent ("gafas de sol para ver el eclipse" is a purchase); at the
#: head it is the whole point of the query ("como hacer huevos cocidos").
#:
#: The retail-modifier exemption is load-bearing and measured: of the 19
#: live rows with an interrogative head that tiered `commercial`, exactly
#: one is a genuine purchase -- `donde comprar gafas para el eclipse` --
#: and `comprar` is the only thing that separates it from the other 18.
#: Remove the exemption and this rule deletes a real, dated demand spike.
#:
#: `para` is here for `para que sirve el te matcha` (4 live rows); it is
#: harmless in head position because a query genuinely starting with
#: `para` and meaning a purchase would carry a modifier and be exempt.
#: Accents are omitted deliberately -- these are matched against _tokenize
#: output, which is already accent-folded (see INFORMATIONAL_MARKERS).
INFORMATIONAL_HEAD_TOKENS = frozenset({
    "que", "como", "cuando", "cuanto", "cuantos", "cuantas",
    "donde", "quien", "quienes", "cual", "cuales", "se", "puedo",
    "por", "para",
})
```

- [ ] **Step 4: Apply it in `score_query`**

Replace the existing informational-marker block:

```python
    marker_hits = sorted(m for m in INFORMATIONAL_MARKERS if m in normalized_query)
    if marker_hits:
        score += INFORMATIONAL_MARKER_PENALTY
        reasons.append("informational_marker:" + ",".join(marker_hits))
    elif tokens and tokens[0] in INFORMATIONAL_HEAD_TOKENS and not modifier_hits:
        # `elif`, not a second `if`: the phrase list and the head list
        # overlap ("donde tirar bombillas" matches both), and the same
        # single signal must never be charged twice.
        score += INFORMATIONAL_MARKER_PENALTY
        reasons.append("informational_head:" + tokens[0])
```

- [ ] **Step 5: Run the full Python suite**

Run: `python3 -m pytest demand/tests/ -q`
Expected: PASS, 390 + 9 = 399. If `test_disposal_lookup_tiers_below_commercial` or either eclipse guard fails, the `elif` was written as an `if` — fix that rather than the test.

- [ ] **Step 6: Commit**

```bash
git add demand/api/relevance.py demand/tests/test_relevance.py
git commit -m "feat(demand): tier interrogative-head lookups as noise unless buying"
```

---

### Task 4: Widen the clustering stopwords

**Files:**
- Modify: `demand/api/relevance.py:221-223` (`CLUSTER_STOPWORDS`)
- Test: `demand/tests/test_relevance.py`

**Interfaces:**
- Consumes: nothing from earlier tasks. `cluster_key()`'s signature and purity are unchanged; only the set it strips grows.
- Produces: no new public names.

**Scope, stated as a limit.** This task adds pure function words — copulas, articles, indefinite determiners, the reflexive `se`, and prepositions with no product meaning. It does **not** touch the head-match rule in `_merge_subset_keys` and does **not** add content words. Adding a noun or an adjective here would merge products that differ (`gafas de sol` vs `gafas de sol homologadas` is a real distinction to a shopper); the rule stays: when unsure, split.

- [ ] **Step 1: Write the failing test**

Append to `demand/tests/test_relevance.py`:

```python
def test_function_words_do_not_split_a_cluster():
    """These three live rows are one demand story; `se`/`un` must not head
    three separate cards."""
    keys = {
        cluster_key("se puede ver el eclipse solar con gafas de sol"),
        cluster_key("se puede ver un eclipse con gafas de sol"),
    }
    assert len(keys) == 1, keys


def test_widened_stopwords_do_not_merge_distinct_products():
    """Guard the other direction: a genuine content word still splits."""
    assert cluster_key("gafas de sol") != cluster_key("gafas de sol homologadas")
    assert cluster_key("funda para gafas de sol") != cluster_key("gafas de sol")
```

- [ ] **Step 2: Run it and watch it fail**

Run: `python3 -m pytest demand/tests/test_relevance.py -v -k "function_words or widened"`
Expected: FAIL — `test_function_words_do_not_split_a_cluster` yields two keys (`se:..._un_...` vs `se:..._solar_...` differ by `un`/`solar`, and `un` is the one that should not have counted).

- [ ] **Step 3: Widen the set**

```python
CLUSTER_STOPWORDS = frozenset({
    "de", "la", "el", "para", "con", "en", "los", "las", "del", "al", "y",
    # Widened 2026-08-16. Function words only -- copulas, indefinite
    # determiners, the reflexive `se`, possessives, and prepositions that
    # carry no product meaning. Measured effect on the 658 live rows:
    # commercial clusters 503 -> 480, eclipse clusters 11 -> 8.
    #
    # Nothing that could name or qualify a product belongs here. `solar`,
    # `homologadas`, `normales` and the like stay OUT on purpose: they are
    # genuine content, and merging on them would tell a shopkeeper to stock
    # a product Madrid did not search for. Under-merging costs redundancy;
    # over-merging costs a wrong stocking decision. Split when unsure.
    "se", "un", "una", "unos", "unas", "que", "a", "o",
    "mi", "su", "tu", "por", "sin", "sobre", "es", "son", "lo",
})
```

- [ ] **Step 4: Run the full Python suite**

Run: `python3 -m pytest demand/tests/ -q`
Expected: PASS, 399 + 2 = 401. `test_all_five_eclipse_variants_share_one_cluster_id`, `test_accessory_and_product_get_different_cluster_ids` and `test_cluster_merge_is_order_independent` must all still pass — they are the guards this task must not break.

- [ ] **Step 5: Commit**

```bash
git add demand/api/relevance.py demand/tests/test_relevance.py
git commit -m "fix(demand): stop function words splitting rising-query clusters"
```

---

### Task 5: Rescue scattered parent-keyword matches

**Files:**
- Modify: `demand/api/relevance.py:157-162` (points constants), `demand/api/relevance.py:282-352` (`score_query`)
- Test: `demand/tests/test_relevance.py`

**Interfaces:**
- Consumes: `INFORMATIONAL_HEAD_TOKENS` from Task 3 (must not fire on the same rows).
- Produces: `PARENT_SCATTERED_POINTS = 1.0`; reason string `"contains_parent_tokens_scattered"`.

**Why.** `gafas para el eclipse de sol` — parent `gafas de sol`, six tokens, obviously commercial — tiers `noise` today: the containment signal requires a **contiguous** run, and six tokens falls outside the 2–5 band, so it scores 0.0. Every parent token is present, just not adjacent. A weaker, non-contiguous signal worth 1.0 (exactly the `COMMERCIAL_THRESHOLD`) rescues it. Measured on the 658 live rows this flips **exactly one** row, `noise` → `commercial`, with no other change — a small win, included because that one row belongs to the eclipse cluster this whole heuristic exists to protect.

- [ ] **Step 1: Write the failing test**

```python
def test_scattered_parent_tokens_still_reach_commercial():
    result = score_query("gafas para el eclipse de sol", "gafas de sol")
    assert result["tier"] == "commercial", result
    assert "contains_parent_tokens_scattered" in result["reasons"]


def test_scattered_signal_does_not_double_count_a_contiguous_match():
    result = score_query("gafas eclipse carrefour", "gafas de sol")
    assert "contains_parent_tokens_scattered" not in result["reasons"]


def test_scattered_signal_does_not_rescue_an_informational_row():
    result = score_query("se puede ver el eclipse con gafas de sol normales", "gafas de sol")
    assert result["tier"] == "noise", result
```

- [ ] **Step 2: Run and watch it fail**

Run: `python3 -m pytest demand/tests/test_relevance.py -v -k scattered`
Expected: FAIL — first test tiers `noise`.

- [ ] **Step 3: Add the constant**

Below `PARENT_CONTAINMENT_POINTS`:

```python
#: Every parent token present but NOT as a contiguous run ("gafas para el
#: eclipse de sol" against parent "gafas de sol"). Half the contiguous
#: signal's weight, because scattered tokens are weaker evidence -- and
#: exactly COMMERCIAL_THRESHOLD, so it rescues a row that has no other
#: signal (six tokens puts it outside the token-count band) without
#: rescuing one that is also carrying a penalty. That is the intended
#: asymmetry: it can lift a 0.0 row to commercial, and can never lift an
#: informational row (which sits at -3.0 before this fires) past the bar.
PARENT_SCATTERED_POINTS = 1.0
```

- [ ] **Step 4: Apply it in `score_query`**

Replace the containment block:

```python
    if parent_tokens and _contains_contiguous_run(tokens, parent_tokens):
        score += PARENT_CONTAINMENT_POINTS
        reasons.append("contains_parent_keyword")
    elif parent_tokens and set(parent_tokens) <= set(tokens):
        # `elif`: contiguous already implies scattered, so a contiguous
        # match must never collect both.
        score += PARENT_SCATTERED_POINTS
        reasons.append("contains_parent_tokens_scattered")
```

- [ ] **Step 5: Run the full Python suite**

Run: `python3 -m pytest demand/tests/ -q`
Expected: PASS, 401 + 3 = 404.

- [ ] **Step 6: Commit**

```bash
git add demand/api/relevance.py demand/tests/test_relevance.py
git commit -m "feat(demand): score scattered parent-keyword matches"
```

---

### Task 6: Shopkeeper-facing copy for the index and the timeframe

**Files:**
- Modify: `frontend/src/i18n/strings.ts`, `frontend/src/components/retail/TimeframeToggle.tsx`
- Test: `frontend/src/components/retail/RetailDashboard.test.tsx`

**Interfaces:**
- Consumes: nothing. Copy only — no data path changes.
- Produces: i18n keys `retail.timeframe.explainer`, `retail.index.explainer`.

**Why this is a task and not a comment.** Every number on this dashboard is a *relative index*, and a shopkeeper reading it as "customers" or "percent" will make a stocking decision on a misreading. The two sentences below are the entire defence. They must be visible on the page, not in a tooltip.

- [ ] **Step 1: Write the failing test**

```tsx
it("tells the shopkeeper the two timeframes are not comparable", async () => {
  render(<RetailDashboard lang="en" />, { wrapper });
  expect(
    await screen.findByText(/cannot be compared with each other/i),
  ).toBeInTheDocument();
});
```

- [ ] **Step 2: Run and watch it fail**

Run (from `frontend/`): `npx vitest run src/components/retail/RetailDashboard.test.tsx -t "not comparable"`
Expected: FAIL — no such text.

- [ ] **Step 3: Add the strings**

```ts
  "retail.timeframe.explainer": { es: "Las dos vistas son mediciones distintas y no se pueden comparar entre sí: cada una se mide contra su propio periodo. Un número más alto en 12 meses no significa más búsquedas que en 3 meses.", en: "The two views are separate measurements and cannot be compared with each other: each is measured against its own period. A higher number over 12 months does not mean more searches than over 3 months." },
  "retail.index.explainer": { es: "Estos números son un índice relativo de interés de búsqueda, no un recuento de clientes ni un porcentaje. Sirven para comparar productos entre sí en la misma vista, no para estimar ventas.", en: "These numbers are a relative search-interest index, not a customer count and not a percentage. Use them to compare products against each other within one view, not to estimate sales." },
```

- [ ] **Step 4: Render them**

In `TimeframeToggle.tsx`, below the existing caption:

```tsx
      <p className="retail-dash__explainer">{t(lang, "retail.timeframe.explainer")}</p>
      <p className="retail-dash__explainer">{t(lang, "retail.index.explainer")}</p>
```

- [ ] **Step 5: Style it**

In `frontend/src/styles/retail.css`, beside the existing caption rule:

```css
.retail-dash__explainer {
  margin: 0.25rem 0 0;
  font-size: 0.8125rem;
  line-height: 1.4;
  color: var(--text-muted, #5c5c5c);
}
```

- [ ] **Step 6: Run the frontend suite, typecheck, redirected build**

Run (from `frontend/`): `npx vitest run && npx tsc --noEmit`
Then: `npx vite build > /tmp/vite-build.log 2>&1; echo "EXIT=$?" >> /tmp/vite-build.log; tail -3 /tmp/vite-build.log`
Expected: PASS, 101 + 1 = 102 tests; tsc exit 0; `EXIT=0`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/i18n/strings.ts frontend/src/components/retail/TimeframeToggle.tsx frontend/src/components/retail/RetailDashboard.test.tsx frontend/src/styles/retail.css
git commit -m "feat(frontend): explain the relative index and the timeframe split"
```

---

### Task 7: Live verification against the real table

**Files:**
- Create: none. This task only reads.
- Modify: `demand/CONTEXT.md` (the row/tier counts it quotes go stale with Task 3)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Start the API against live data**

```bash
cd /Users/rajeshgupta/Desktop/reachout && DEMAND_ANALYTICS_SOURCE=live \
  python3 -m uvicorn demand.api.app:app --port 8001 > /tmp/demand-api.log 2>&1 &
```

- [ ] **Step 2: Confirm nothing is hidden any more**

```bash
curl -s -D- -o /tmp/rq.json 'http://127.0.0.1:8001/demand/api/rising-queries?limit=1000' | grep -i x-total-count
python3 -c "import json;d=json.load(open('/tmp/rq.json'));print(len(d), len({r['cluster_id'] for r in d}))"
```
Expected: `X-Total-Count: 580`, and `580 480` from the second command — the post-Task-3/4/5 numbers from Findings. Row count equals the header: nothing truncated.

- [ ] **Step 3: Confirm the honesty rule survived**

```bash
python3 -c "import json;d=json.load(open('/tmp/rq.json'));print(sum(1 for r in d if r['is_breakout'] and r['growth_pct'] is not None))"
```
Expected: `0`.

- [ ] **Step 4: Spot-check the tier flips**

```bash
python3 -c "
import json;d=json.load(open('/tmp/rq.json'))
qs={r['query'] for r in d}
assert 'gafas para el eclipse de sol' in qs, 'Task 5 rescue missing'
assert 'donde comprar gafas para el eclipse' in qs, 'modifier exemption broken'
assert not any(q.startswith('como hacer') for q in qs), 'informational row still commercial'
print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Update the stale counts in `demand/CONTEXT.md`**

Replace the quoted rising-queries figures with: 658 rows total, 580 `commercial`, 78 `noise`, 480 distinct commercial clusters, measured 2026-08-16.

- [ ] **Step 6: Stop the server and commit**

```bash
kill %1
git add demand/CONTEXT.md
git commit -m "docs(demand): refresh rising-query counts after relevance tuning"
```

---

## Self-review

**Spec coverage.** Cap (Tasks 1–2, both ends of the wire). Under-merge (Task 4, with the two causes it deliberately does *not* fix stated in Findings). Informational filter (Task 3, the rule named and its one exemption measured). Shopkeeper explanation (Task 6). Live proof (Task 7). The one item raised in conversation and **not** planned: merging `eclipse gafas de sol` with `gafas eclipse` across a head-token difference — it needs a subject model, not a heuristic, and the accessory guard exists precisely to refuse that class of merge.

**Placeholders.** None. Every step carries the code to write or the command to run.

**Type consistency.** `fetchRisingQueries` returns `RisingQueriesPage` in Task 2 and is consumed as `rising.data.rows` / `rising.data.total` in the same task; `RisingQueriesPanel` is its only caller. `INFORMATIONAL_HEAD_TOKENS` (Task 3) and `PARENT_SCATTERED_POINTS` (Task 5) are read only inside `score_query`. `RISING_QUERIES_MAX_LIMIT` (Task 1, server) and `RISING_QUERIES_LIMIT` (Task 2, client) are different names for the same 1000 by design — the client comment names the server constant it mirrors.

**Ordering.** Tasks 1→2 and 3→4→5 are each sequential (same files). The two chains are independent of each other. Task 6 is independent of everything. Task 7 is last.
