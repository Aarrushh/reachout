# `components/retail/charts/` — the only place a chart library exists

Built by task **U3** (2026-08-04).

## D11 scaffold note (2026-08-17)

This folder is mid-migration from ECharts to **Bklit UI** (decision D11,
successor to D9 below — see `docs/IMPLEMENTATION_PLAN_V3.md` §1, §3.1). This
task (A0) only laid groundwork: `bklit/` now holds a scoped Tailwind v4
substrate (`bklit/bklit.css`) that Bklit's vendored components will read
`--chart-*` custom properties from, defined additively in
`../../../styles/tokens.css`. **Nothing imports `bklit.css` yet** — that is
expected and correct until Bklit's components land (task A1) and the three
charts below are rewritten against them (task A2).

Why Tailwind is in this repository at all: Bklit's install path is a shadcn
registry that requires it. D11 draws the exception as narrowly as this
directory — utilities-only, **no preflight/reset import** (a reset must never
leak into consumer CSS), and `bklit.css`'s `@source "../"` restricts class
scanning to this charts tree only. The containment check:

```sh
git grep -n 'tailwindcss' src | grep -v retail/charts
```

must always print nothing. If it doesn't, the scope leaked.

The containment rule immediately below (D9) still describes today's ECharts
reality verbatim; it will be rewritten to describe Bklit's D9→D11 handoff
once task A2 lands.

## The containment rule

`EChart.tsx` is the **only file in the repository** that imports
`echarts-for-react`. Decision D9 admitted ECharts as the single exception to
the frontend's no-component-library convention, on one condition: reversing
it must be a rewrite of this folder and nothing else. That condition holds
only while the import stays in one file, so:

- New charts import `EChart`, never `echarts-for-react`.
- Option objects are built in `options.ts`, never inline in a component.
- Nothing outside `components/retail/` imports anything from here.

Checking it is one command:

```sh
grep -rn echarts src/ | grep -v components/retail/charts/ | grep -v '\.test\.'
```

It should print nothing. Test files are excluded because `vi.mock` has to
name the real module to replace it — `AppShell.test.tsx` and
`RetailDashboard.test.tsx` both stub it, since ECharts draws into a canvas
jsdom does not implement. Those are stubs, not usages: neither file imports
the library.

## The arithmetic rule

`options.ts` performs **no arithmetic**. Every value it puts on an axis —
`delta_pct`, `share_pct`, `risk_pct`, `interest_avg` — is a field the demand
service already computed and validated against
`demand/shared/schemas/analytics_response.schema.json`.

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
