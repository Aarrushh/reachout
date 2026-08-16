# `components/consumer/reactbits/` — the only place ReactBits exists

Scaffolded by task **A0**, vendored by task **B3** (`docs/IMPLEMENTATION_PLAN_V3.md`
§4.3). This directory is empty until B3 lands — it exists now only so the
containment rule below has a home from the start.

## D12: ReactBits, scoped

Exactly two components are vendored here, both `TS-CSS` variants (no
Tailwind dependency, keeping the consumer side clean of the D11 Tailwind
exception scoped to `components/retail/charts/`):

- **`BlurText`** — wraps the landing `<h1>` copy. Same i18n string in, same
  text out; only the reveal is animated.
- **`ClickSpark`** — wraps the search-submit button. A one-shot canvas burst
  at the moment of broadcast, deterministic and scoped to that click.

Both are locally patched to respect `prefers-reduced-motion` — upstream
ReactBits does not handle it. The patch (`/* D12 local patch R1 … */`) adds:

```ts
const prefersReducedMotion =
  typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
```

`BlurText` renders the plain, fully-visible text and skips all `motion.span`
animation when it matches. `ClickSpark`'s click handler returns before
spawning sparks. Content and interactivity are unaffected either way — only
the motion is gated.

**Importable only from consumer files.** Nothing under `components/retail/`
or `components/` proper may import from this folder — these are landing/
search-page flourishes, not shared UI.

## Rejected candidates

- **`ShinyText`** — drives `background-position` from `useAnimationFrame`, a
  per-frame repaint loop. That is the exact pathology Part B of this redesign
  removes from `results.css`'s keyframes; adding a new instance of it here
  would contradict the reason this workstream exists.
- **`AnimatedContent`** / **`FadeContent`** — both require `gsap`, which would
  be a second animation runtime running alongside `motion` (already pulled in
  by Bklit on the retail side, and by `BlurText` here) for no capability
  `motion`/plain CSS doesn't already cover.

## What belongs here

Nothing yet. B3 vendors `BlurText.tsx` and `ClickSpark.tsx` (plus their
patches and tests) directly into this folder — no subfolders, no other
components added later without a new decision record.
