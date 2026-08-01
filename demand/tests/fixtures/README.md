# Fixture spec — demand practice data (S3)

This is the binding spec for the canned data TASK 69 commits under
`demand/tests/fixtures/trends/` and that every later chain step (TASK 71-73,
77) is built and tested against. It fixes the S3 decision
(`docs/IMPLEMENTATION_PLAN_V2.md` §0.2): **8 weeks × 100 SKUs**, a founder
override of the 12×200 default.

## Shape

- **8 weeks** of `demand.trend_snapshots` captures per tracked keyword —
  one weekly `series` point per week, i.e. exactly at the `high`-confidence
  tier's floor (§5.6: `high` requires ≥8 weeks). Fewer than 8 weeks for any
  keyword means that keyword can never reach `high`.
- **100 SKUs** worth of underlying product/category coverage backing the
  keyword universe (TASK 70's union of `public.products.category` and
  `_config/seed_keywords.json`), sized so `category_mix` and
  `stock_out_risk` (TASK 77's analytics segments) have a realistic spread
  to compute over.
- `geo` is `ES-MD` throughout. No barrio field anywhere in the fixtures —
  Google Trends does not resolve below Madrid-community scope, and nothing
  in this fixture set may pretend otherwise.

## The mandatory high-confidence keyword (binding, S3)

Confidence rules (`docs/IMPLEMENTATION_PLAN.md` §3.3 /
`docs/IMPLEMENTATION_PLAN_V2.md` §5.6, deterministic, in
`compute_signals.py`, never model-assigned):

- **`high`** = ≥8 weeks of data **and** `interest_avg ≥ 20` **and**
  direction stable across the last 3 windows.
- **`medium`** = ≥4 weeks **and** `interest_avg ≥ 10`.
- **`low`** = everything else, including any series with provider gaps.

At *exactly* 8 weeks, the `high` tier is only marginally exercisable: a
naively generated fixture set can easily produce zero `high` rows, and the
tier would go untested while the suite stays green. **This fixture set
must therefore include at least one keyword deliberately constructed to
satisfy all three `high` conditions** — 8 full weeks of data, an
`interest_avg` of 20 or above, and a direction (rising/falling/flat) that
does not change across the last 3 weekly windows.

`demand/tests/test_compute_signals.py` (TASK 72) **must assert that a
`high`-confidence row is produced** from this fixture set. A fixture
regeneration that silently drops the deliberate high-confidence keyword is
a test failure, not a passing edge case.

## Canonical caveat string

Every recommendation and every analytics response fixture that reaches the
API layer carries this exact caveat text (`docs/IMPLEMENTATION_PLAN.md`
§3.3, required and non-empty at the schema layer in
`recommendation.schema.json`, `recommendations_response.schema.json`, and
`analytics_response.schema.json`):

```
Basado en interés de búsqueda en Madrid, no en compras reales.
```

A fixture (or a live-computed payload) missing this string, or supplying
an empty one, must fail schema validation — that is the point of the
`minLength: 1`/required constraint, not an accident to work around.

## Reversing S3

Widening to the 12×200 default is a fixture-only change: regenerate under
`demand/tests/fixtures/trends/` (and TASK 72's golden expected-signal
files) with the new window and SKU count. No code or schema changes are
required — `trend_snapshot.schema.json` and `demand_signal.schema.json`
place no upper bound on series length or keyword count.
