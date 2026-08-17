# IMPLEMENTATION_PLAN_V4 — chat that answers, and a dashboard that looks finished

*Written 2026-08-17, against `main` at `958080a`. Every claim below carries a file:line
and was checked in the tree, not recalled. Supersedes nothing — V3 shipped and merged;
this plan covers what V3 left behind plus the two problems the user named:
**the retailer chat doesn't respond**, and **the aesthetics**.*

Each phase is executable in a fresh chat context with no memory of the others. Tickets are
open at `github.com/Aarrushh/reachout/issues` so they are reachable from any machine.

---

## Phase 0 — Established facts and allowed APIs

**Read this before any phase. Do not re-derive it, and do not assume anything not listed.**

### The chat contract that already exists

`POST /api/chat` is real, mounted, and called by nothing.

| Fact | Location |
|---|---|
| Route definition | `reachout/api/chat.py:101` |
| Mounted on the **consumer** API (:8000) — the demand API (:8001) has no chat route | `reachout/api/server.py:95` |
| CORS allows `http://localhost:5173` only | `server.py:76-82` |
| Request shape `{store_id: str, message: str, history: [{role, content}]}` | `chat.py:36-39` |
| Response shape `{reply: str, suggested_items: [...]}` | `chat.py:135` |
| The frontend TypeScript type **already matches** this contract | `frontend/src/chat/shopkeeper.ts:11-23` |
| 502 "Database connection failed" when Supabase is unset | `chat.py:119`, `supa.py:15-19` |
| 502 "LLM unavailable" when `GEMINI_API_KEY` is unset | `chat.py:132-133`, `gemini.py:36-39` |
| `gemini.py` loads exactly one env file: `reachout/.env` | `gemini.py:18` (`parents[1]/.env`) |

### Frontend patterns to copy, not invent

| Need | Copy from |
|---|---|
| Resolve a CSS custom property in JS | `cssVar()` helper, `MapPanel.tsx:20` — `getComputedStyle`-based |
| Category colour by name | `MapPanel.tsx:27-31` |
| Elevation | the single existing token `--shadow-card`, `tokens.css:30` |
| Light floating surface | map popup, `results.css:312-315` |
| Hover treatment | `.shop-card:hover`, `results.css:176` |
| Focus ring | `--focus-ring` + `:focus-visible`, `shell.css:66-67` (the app's only `:focus-visible`) |

### Anti-patterns — do NOT do these

- **Do not rename colour tokens.** `MapPanel.tsx` resolves them by name at runtime via `getComputedStyle`. The `tokens.css:1-11` header explains this. Adding scales is in scope; renaming is not.
- **Do not pass `var(--x)` into a canvas API.** Canvas 2D cannot resolve custom properties; the assignment is silently ignored and you get `#000000`. This is exactly bug #19.
- **Do not run `npm run build` in the foreground.** It hangs forever; redirect to a file and it finishes in ~5 s.
- **Do not point a browser at `127.0.0.1`.** Both APIs restrict CORS to `localhost:5173`; `vite preview` on `:4173` is blocked outright.
- **Do not start the consumer API without `PYTHONPATH=..`** when `REACHOUT_SIM=1`. Every endpoint still returns 200 while the simulator tick raises `ModuleNotFoundError: No module named 'reachout'` forever, visible only in the log.
- **Do not commit any `.env` value.** This repo is public.
- **Do not invent chart APIs.** Bklit is vendored under `frontend/src/components/retail/charts/bklit/` — read the actual component before calling it.

### Running it

Three processes, fixed ports — see `README.md` §"Running it locally". Python suites run
**from the repo root** (694 tests collect); from inside `demand/` seven import-hygiene
tests fail by design.

---

## Phase A — Context transfer to the new machine (#28)

**Independent of every other phase. Do this first if the machine move is imminent.**

Full runbook: `docs/MIGRATION_NEW_MACHINE.md`. The short version:

1. Nothing is uncommitted — a fresh clone loses zero source code.
2. Move ~1 MB of markdown from `.superpowers/` (98 files), the orphan plan at
   `~/.claude/plans/recursive-enchanting-snowflake.md`, and 6 memory files. Skip the 47
   review `.diff` files — they regenerate from commit ranges already on `origin/main`.
3. Re-issue credentials by hand. Never through this repo — it is public.
4. Rebuild the 410 MB of `node_modules` / `.venv` / DB from README commands.

**Verification:** on the new machine, `pytest reachout/tests demand/tests` collects 694;
`npm test` passes; `npm run build` (redirected) exits 0; the three services answer on
5173 / 8000 / 8001.

---

## Phase 1 — Make the retailer chat actually respond (#4, #5, #6, #7)

**This is the user's stated top problem, and the diagnosis is not what the symptom
suggests.** The chat is not broken. It was never wired. `sendChatMessage`
(`shopkeeper.ts:81-91`) is a client-side template engine: five regexes
(`shopkeeper.ts:25-29`) over hardcoded strings, resolved through a `setTimeout`. There is
no `fetch` in that path — `grep -rn "api/chat" frontend/src/` finds three comments and
zero call sites. Its own header (`shopkeeper.ts:3`) admits it: *"today `sendChatMessage`
is a local mock because the endpoint doesn't exist yet."* The endpoint now exists.

**Order matters — #5 first, or you will be debugging a 502 you already understand.**

1. **#5 — the key.** `gemini.py:18` loads `reachout/.env`, which defines no
   `GEMINI_API_KEY`. A Gemini key exists on the old dev machine under a *different name*
   (`GEMINI_FLASH_LITE_API_KEY`) in the *repo-root* `.env`, which `gemini.py` never
   reads. Pick one name, one file, document it in `reachout/.env.example`.
2. **#4 — the wire.** Replace the mock body of `sendChatMessage` with a POST to
   `/api/chat` on the consumer API base. The response type already matches
   (`shopkeeper.ts:11-23`). Replace `SAMPLE_CONTEXT` (`RetailChatPane.tsx:18-24`, which
   hardcodes `shopId: "sample"`, `stockQty: 12`) with the real shop in scope.
3. **#7 — the failure path.** `ChatPanel.tsx:65` has no `.catch`. Harmless against a mock
   that never rejects; against a real fetch it leaves `typing` stuck `true` forever —
   which presents as *"the chat stopped responding."* Fix this in the same change as #4,
   not after.
4. **#6 — the dead button.** `AiAnalystButton.tsx:21-29` is `disabled` with no handler,
   deliberately (`07f09da`). Decide: wire it, or delete it from the header. A permanently
   greyed-out control is doing real damage to how finished the dashboard looks.

**Verification**
- [ ] `curl` the endpoint directly first; confirm 200 and a real `reply` before touching the frontend
- [ ] Typing a question in the retail chat produces a model answer, not a template
- [ ] Killing the API mid-request shows an error state and a usable input, not a spinner
- [ ] `RetailChatPane.test.tsx:36` — currently titled *"answers a question from the mock, with no backend"* — is rewritten. It asserts the broken state.
- [ ] `AiAnalystButton.test.tsx:26-35` — asserts the DOM is unchanged after a click — is rewritten or deleted with the button.

**Anti-pattern guard:** the tests currently encode "no AI" as the requirement. Changing
them is the point, not a violation. Do not preserve their assertions.

---

## Phase 2 — The design substrate (#18, #12, #13, #15)

The audit's systemic finding: `tokens.css` is a **colour file that never grew into a
design system** — 34 colour tokens, 3 font families, 1 shadow, and nothing else. With no
scale to snap to, every component invented its own: 13 distinct font sizes, 39 distinct
padding declarations (including `6px 12px`, `8px 12px`, `9px 12px`, `10px 12px`), 6 radii,
4 unshared breakpoints. Fix the substrate before the surfaces, or Phase 3 will invent a
sixth radius.

1. **#18** — add spacing, type, radius and breakpoint scales as tokens. **Add only.**
   Colour token names stay frozen (runtime `getComputedStyle` lookup depends on them),
   even the ones that now lie: `--ink-900` is white, `--sand` is near-black,
   `--stock-amber` is red.
2. **#12** — the app's entire emphasis vocabulary is faux bold. `main.tsx:4-7` loads Inter
   400 and 500; `font-weight: 600` is requested 13 times. Three display headings set no
   weight at all, so UA default 700 hits a 600-only file. Either load the cuts or stop
   asking for them — decide once, apply everywhere, and record it next to the imports so
   the next subsetting pass cannot silently undo it.
3. **#13** — `#ff9900` on `#f7f8f8` is ≈2.1:1, and it is the *geolocation error message*,
   the one line a blocked user must read. The confidence chip is ≈3.0:1. Note the
   `tokens.css:8-10` audit header lists ratios for five token groups and omits both brand
   oranges — the only two that fail.
4. **#15** — one `:focus-visible` in the entire app, four mutually inconsistent `:focus`
   rules, and `ShopCard.tsx:60-62` is a clickable `<article>` with no `tabIndex` and no
   `role`, so the primary result is unreachable by keyboard.

**Verification**
- [ ] `grep -c 'font-size' across src/**/*.css` trends down; new values come from the scale
- [ ] No faux bold: every `font-weight` requested has a loaded cut
- [ ] Contrast checker confirms ≥4.5:1 on error text and chips
- [ ] Tab through landing → results → dashboard: every interactive element shows one consistent ring, and `ShopCard` is reachable

---

## Phase 3 — The retail dashboard (#8, #9, #10, #11, #14, #16, #21)

The audit's second systemic finding: **Bklit was vendored with containment engineered but
not assimilation.** The D11 patch was meticulous about scope leakage (`bklit.css:20-28`,
rescoping `:root` → `.chart-panel`) and stopped there. What arrived is a foreign design
system quarantined inside panels that themselves have no elevation, no hover states, no
max-width and one breakpoint. The dashboard is *honest* and *unfinished-looking*, and a
shopkeeper reads the second before the first.

- **#8** — `.chart-panel` background is `--ink-900` = `#ffffff` = the body background (`retail.css:108-114`, `tokens.css:56`). Zero `box-shadow` in 313 lines.
- **#9** — two colour systems inside one panel: `bklit.css:29-55` oklch (hue 260-286) vs `tokens.css:41-51` hex. `--chart-axis-text` is dead (one grep hit, its own definition). `bklit.css:57-85` ships an unreachable `.dark` palette.
- **#10** — the tooltip is dark blurred glass (`tooltip-box.tsx:179-183`, `bklit.css:42`), the only dark surface in the product.
- **#11** — the donut keys colour by array index (`options.ts:86`) while the map keys by name (`MapPanel.tsx:27-31`), breaking the "visual rhyme" that `tokens.css:38-39` explicitly promises.
- **#14** — three charts, three heights: `CategoryMixChart.tsx:39,43` pins 240px while the two bar charts use `aspectRatio="5 / 4"` and grow to ~390px. Their insets also disagree (`left: 80` vs `left: 8`), so gridlines don't align.
- **#16** — zero `:hover` in `retail.css` and `bklit.css`. `.timeframe-toggle__button` declares `cursor: pointer` and then does nothing.
- **#21** — `--foreground` referenced three times, defined zero times, so a Y-axis hover transition silently no-ops. Plus a hardcoded fuchsia `#e879f9` at `pattern-preset.tsx:179`.

**Verification**
- [ ] Screenshot the dashboard before and after, at 1280px, side by side
- [ ] `grep -c ':hover' retail.css` > 0
- [ ] `grep -rn -- '--foreground' src/` resolves or is gone
- [ ] Pharmacy is the same colour in the donut, on the map and on a shop card

**Anti-pattern guard:** keep the containment discipline that D11 established. Assimilating
Bklit's *appearance* into the app's tokens is the goal; letting its `:root` variables leak
back out is not.

---

## Phase 4 — Consumer surface (#17, #19, #20, #22)

- **#17** — the five landing category glyphs (`ShopCard.tsx:7`, and `search.tsx:31-33`) are `U+2695 U+26C1 U+2692 U+26A1 U+270E`. None exist in the latin subset of Inter, which is the entire point of `ff1b7f3`. On macOS/Windows `⚕` and `⚡` become full-colour emoji and ignore their category tint; `⛁` and `✎` render as hairline outlines. **This is a regression from the performance work** — a symptom of the audit's third root cause: performance work outran design work.
- **#19** — `sparkColor="var(--terracotta)"` reaches `ctx.strokeStyle` (`ClickSpark.tsx:120`) and is silently ignored: black sparks off an orange button. `cssVar()` at `MapPanel.tsx:20` already solves this.
- **#20** — no `max-width` on `.card-column` or `.retail-split__dash`, so a shop card reaches ~1050px on a 2560px display; and a *second* `.shop-card` block at `results.css:265` silently overrides the first 93 lines earlier with `opacity: 0.35`, leaving the results list washed out for up to 2.5 s (`usePingSequence.ts:7-8`).
- **#22** — the tile grid jumps 5 columns → 2 at one breakpoint, crushing tiles to ~105-130px between 641px and 900px while the glyph circle alone is a fixed 64px.

**Verification**
- [ ] Landing tiles render identically on macOS Chrome, Windows Chrome and Firefox
- [ ] Sparks are orange
- [ ] Results are legible on first paint; no >1000px measure at 2560px

---

## Phase 5 — Judgement calls and V3 debt (#23, #24, #25, #26, #27)

**#23 is a gate, not a chore.** Six findings cannot be settled from source: how the glyphs
actually render, the dashboard between 721px and ~1100px, Y-axis label legibility (oklch
0.45 at `opacity: 0.7` over white at 12px — estimated ≈3.0:1, but opacity compositing plus
oklch→sRGB is not worth asserting from arithmetic), whether the 35% ping-in reads as
intentional, three nested scroll contexts on one screen (`retail.css:305` and siblings),
and the maplibre control chrome against the token palette — never rendered during the
audit. Run the app, take screenshots, attach them to the individual tickets.

**#24-#27** are the V3 ledger's post-merge follow-ups, promoted to GitHub so they survive
independently of a git-ignored file: integration tests for `ResultsPanel` and
`routes/search.tsx` (the branch's weakest coverage, pre-existing); `BlurText` rendering
`<p>` inside `<h1>`; ClickSpark's `!important` wrapper selector; and stubbing `getContext`
in `ClickSpark.test.tsx`.

---

## Ticket index

| # | Title | Phase |
|---|---|---|
| [#4](https://github.com/Aarrushh/reachout/issues/4) | Retailer chat answers from a client-side mock, never calls the backend | 1 |
| [#5](https://github.com/Aarrushh/reachout/issues/5) | POST /api/chat 502s: gemini.py reads GEMINI_API_KEY, which reachout/.env does not define | 1 |
| [#6](https://github.com/Aarrushh/reachout/issues/6) | AiAnalystButton is hard-disabled with no handler | 1 |
| [#7](https://github.com/Aarrushh/reachout/issues/7) | ChatPanel send has no .catch | 1 |
| [#8](https://github.com/Aarrushh/reachout/issues/8) | Retail dashboard is flat: no elevation on chart panels | 3 |
| [#9](https://github.com/Aarrushh/reachout/issues/9) | Two competing colour systems inside chart panels | 3 |
| [#10](https://github.com/Aarrushh/reachout/issues/10) | Chart tooltip is dark blurred glass | 3 |
| [#11](https://github.com/Aarrushh/reachout/issues/11) | Donut colours keyed by index, don't match the map | 3 |
| [#12](https://github.com/Aarrushh/reachout/issues/12) | Faux bold across the whole app | 2 |
| [#13](https://github.com/Aarrushh/reachout/issues/13) | Brand orange as body text fails contrast | 2 |
| [#14](https://github.com/Aarrushh/reachout/issues/14) | Three charts, three heights, misaligned plot areas | 3 |
| [#15](https://github.com/Aarrushh/reachout/issues/15) | Focus states inconsistent; ShopCard unfocusable | 2 |
| [#16](https://github.com/Aarrushh/reachout/issues/16) | Retail dashboard has zero hover states | 3 |
| [#17](https://github.com/Aarrushh/reachout/issues/17) | Category glyphs fall outside the latin font subset | 4 |
| [#18](https://github.com/Aarrushh/reachout/issues/18) | tokens.css is colour-only: no spacing/type/radius/breakpoint scale | 2 |
| [#19](https://github.com/Aarrushh/reachout/issues/19) | ClickSpark passes a CSS var to canvas strokeStyle | 4 |
| [#20](https://github.com/Aarrushh/reachout/issues/20) | No max-width on wide screens; results at 35% opacity | 4 |
| [#21](https://github.com/Aarrushh/reachout/issues/21) | Orphaned shadcn `--foreground` | 3 |
| [#22](https://github.com/Aarrushh/reachout/issues/22) | Landing tiles cramped 641-900px | 4 |
| [#23](https://github.com/Aarrushh/reachout/issues/23) | Human visual pass on localhost | 5 |
| [#24](https://github.com/Aarrushh/reachout/issues/24) | V3: integration tests for ResultsPanel and search.tsx | 5 |
| [#25](https://github.com/Aarrushh/reachout/issues/25) | V3: BlurText renders `<p>` inside `<h1>` | 5 |
| [#26](https://github.com/Aarrushh/reachout/issues/26) | V3: ClickSpark wrapper class, drop !important | 5 |
| [#27](https://github.com/Aarrushh/reachout/issues/27) | V3: stub getContext in ClickSpark.test.tsx | 5 |
| [#28](https://github.com/Aarrushh/reachout/issues/28) | Transfer working context to the new work computer | A |

## The three root causes, in one place

Worth keeping in view, because fixing the 20 symptoms without them invites all three back.

1. **`tokens.css` froze as a colour file.** The reason names are immutable is real
   (runtime lookup). It froze the whole file rather than just the names, so there is no
   spacing, type, radius or breakpoint scale to snap to.
2. **Bklit was contained, not assimilated.** Scope leakage was engineered against
   carefully; visual coherence was not addressed at all.
3. **Performance work outran design work.** Latin subsetting and lazy-loading were correct
   engineering, never followed back through the visuals — which is how the icon set broke
   (#17) and how every bold weight in the app became synthetic (#12).
