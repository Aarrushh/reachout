# constraints.md  (Layer 3: the rules that prevent hallucination)

Non-negotiable. These bind every execution model (Sonnet 5, GLM 5.2, Opus 4.8)
working in this repo. If a task seems to require breaking one, stop and ask.

## 1. The hardcoded / agentic split
Anything that does not need intelligence must not call an AI.
- Hardcoded (pure Python, `scripts/`): geocoding, Overpass queries, distance,
  radius filtering, stock levels, matching, ranking, database writes, pings,
  GeoJSON output. Stages 02, 03, 05 are hardcoded end to end.
- Agentic (`stages/` 01 and 04, optional LLM, deterministic default): parsing a
  vague query; normalising item-name casing.
The test: would a wrong guess here invent a fact about the real world? If yes,
it is hardcoded. "Resolving a location" is Nominatim/gazetteer lookup — data
retrieval, never AI judgment.

## 2. Schema-constrained output — every stage, no exceptions
Each stage's output file is validated against its schema in `shared/schemas/`
by the orchestrator BEFORE the next stage may read it. A failing output is
rejected and the pipeline halts; it is never "fixed up" downstream.
All object schemas use additionalProperties:false.

## 3. Never invent a missing field
An agent processes only the data it is given. A missing/empty required input
yields {"status":"incomplete","missing_fields":[…]} naming every gap. No stage
ever guesses, defaults, or infers a value that was not in its inputs.

## 4. Numbers, names, and coordinates are copied, never generated
Prices, distances, stock counts, coordinates, shop names, and addresses flow
from the database / OSM through to the final list unchanged. The optional LLM
in stage 04 may normalise item-name casing only. address:null stays null.

## 5. The database is the only source of truth for stock
If a row says qty 0, the item does not exist for this pipeline. No stage may
claim availability without a live row (qty >= 1) behind it.

## 6. Real shops, synthetic stock — and the data says so
Shop identity (name, position, category, address) comes only from OSM via
Overpass / cache / Geofabrik. Inventory is simulated: every inventory row
carries synthetic:true. No output may present synthetic stock as verified
retailer data.

## 7. External APIs live in scripts/ only, with fallbacks and manners
Overpass, Nominatim, and OpenRouteService are called only from scripts/, each
with: an explicit timeout, a descriptive User-Agent, Nominatim rate limiting
(max 1 request/second, results cached), and a committed offline fallback
(osm_cache / gazetteer / haversine). Agentic stages never make network calls.
REACHOUT_OFFLINE=1 must run the whole pipeline and test suite with zero
network access.

## 8. Zero matches is a valid answer
Empty results are status:"ok" with empty arrays at stages 03, 04, and 05.
Never an error, never padded, never apologised for with generated text.

## 9. No narrative output — structurally enforced
The pipeline's product is a ranked factual list. There is no community card,
store story, culture tag, review, or editorial text anywhere in the data
model. additionalProperties:false makes any such field fail validation
regardless of its name. UI/visual design is a separate future phase and
nothing in this repo may pre-empt it.

## 10. Coordinate discipline
GeoJSON files: [longitude, latitude] per RFC 7946. Everywhere else: named
lat / lng keys, never positional pairs. Madrid sanity bounds are enforced in
every schema carrying coordinates.

## 11. Every output is a readable file
Each stage writes a plain file under its own output/. Pipeline events append
to data/events.jsonl. If something looks wrong you can see exactly where it
came from.

## 12. TDD and surgical changes
Every scripts/ module is built test-first (superpowers methodology). Diffs
touch only what the task requires (Karpathy rules in CLAUDE.md). Tests run
offline against fixtures; no test may depend on a live API.

## 13. Model escalation
Execution runs on Sonnet 5 or GLM 5.2. If the same stage fails schema
validation twice in a row, stop and escalate that stage to Opus 4.8 rather
than loosening a schema or retrying blindly. Schemas are only ever changed by
explicit human-approved decision, never to make a failing output pass.
