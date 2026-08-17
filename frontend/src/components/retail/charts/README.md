# `components/retail/charts/` — the only place a chart library exists

Built by task **U3** (2026-08-04). Migrated from ECharts to **Bklit UI**
across tasks A0–A2 (2026-08-17, decision D11, successor to D9 below — see
`docs/IMPLEMENTATION_PLAN_V3.md` §1, §3.1–§3.6). The migration is complete:
`EChart.tsx` is gone, the ECharts npm packages are no longer dependencies,
and every chart renders through the vendored Bklit components in `bklit/`.

## The Tailwind scope (D11)

Bklit's install path is a shadcn registry that requires Tailwind. D11 draws
that exception as narrowly as this directory — utilities-only, **no
preflight/reset import** (a reset must never leak into consumer CSS), and
`bklit/bklit.css`'s `@source "../"` restricts class scanning to this charts
tree only. The containment check:

```sh
git grep -n 'tailwindcss' src | grep -v retail/charts
```

must always print nothing. If it doesn't, the scope leaked.

## The containment rule

The ECharts npm packages are gone from the tree entirely — the old manual
source grep this section used to describe is retired along with them. In
its place, `charts.containment.test.ts` runs
four rules as executable assertions against the source tree itself, so a
future violation fails a test instead of only a code-review glance:

1. Nothing outside `components/retail/charts/` imports the vendored
   `./bklit` barrel. Bklit is vendored source, not a published package —
   reversing D11 must stay a rewrite of this one folder.
2. Nothing outside `charts/` and `consumer/reactbits/` imports `motion` or
   `@visx/*` — the two libraries D11/D12 admitted as scoped exceptions to
   the frontend's no-component-library convention, each confined to its own
   vendored surface.
3. Every `<Bar` / `<PieSlice` usage inside `charts/` carries
   `animate={false}` (C19: charts must never animate on refetch — an
   animated redraw draws the eye to motion rather than to the number).
4. No `reactbits/` import inside `charts/`, and no `bklit` import inside
   `consumer/` — the two vendored surfaces stay on their own sides.

Two more rules from the ECharts era still hold, enforced by convention
rather than by the containment test:

- Option objects are built in `options.ts`, never inline in a component.
- Nothing outside `components/retail/` imports anything from here.

`AppShell.test.tsx` and `RetailDashboard.test.tsx` both mock
`./charts/BklitFrame` rather than importing the real one, since jsdom has no
`ResizeObserver` for Bklit's `@visx/responsive` sizing to measure against.
Those are stubs, not usages: neither test file imports Bklit itself.

## The arithmetic rule

`options.ts` performs **no arithmetic**. Every value it puts on an axis —
`delta_pct`, `share_pct`, `risk_pct` — is a field the demand service already
computed and validated against
`demand/shared/schemas/analytics_response.schema.json`.

`interest_avg` is deliberately absent from that list. It is a normalised index,
not a count, so charting it would invite a reader to treat it as a number of
searches. It must never reach an axis.

`options.test.ts` asserts against the **literal** numbers from the payload
rather than expressions over them. That is deliberate: a test that recomputed
the expected value would prove only that the chart agrees with the test's
arithmetic, which is the arithmetic that is forbidden in the first place.

Two mutations this suite catches, both of which look like harmless tidying:

- colouring a top mover by `delta_pct >= 0` instead of the server's
  `direction` — the two can disagree, since direction is a windowed judgement
  and the sign is not;
- deriving `risk_pct` from `at_risk_count / total_count` instead of reading
  it — same number today, a silent divergence the first time the service
  changes how risk is defined.

## The honesty rule

`ChartPanel` always renders the confidence chip and the caveat caption as
text in the flow, including when a segment is empty. Neither is ever a
`title` tooltip: a phone cannot hover, and a number whose honesty label costs
a hover is a number presented as more certain than it is.

The caveat is printed **verbatim** from the response. It is a schema-required
field of a validated payload, so rewording or translating it here would put a
sentence on screen that the backend never approved — which is why it stays
Spanish even under `?lang=en`. If it should be bilingual, the schema gains
the second string and the service supplies it.

`RetailDashboard` labels a `generated_from: "fixture"` response as practice
data. Fixture and live responses are byte-identical in shape by design, so
this field is the only thing standing between canned numbers and a
shopkeeper who thinks they are looking at their own shop.
