# tech_stack.md  (Layer 3: what this MVP uses)

Kept deliberately small so the repo runs with almost nothing installed.

## This MVP

| Part | Choice | Why |
|------|--------|-----|
| Language | Python 3 | standard library covers most of it |
| Live store | SQLite (stdlib, WAL mode) | concurrent read while the simulator writes |
| Event log | plain JSONL | readable, tail-able, observable |
| Schema checks | `jsonschema` | the one required dependency |
| Optional AI | `anthropic` SDK | only for the query parser, opt-in |

Only `jsonschema` is required. `anthropic` is optional.

## A realistic production version (not built here)

This is for direction, not a promise. Verify each choice before relying on it.

| Part | Likely choice |
|------|---------------|
| Live store | Postgres with a realtime layer |
| Retailer sync | POS or inventory API webhooks into the store |
| Ping delivery | push notifications, SMS, or websockets |
| Consumer app | a web or mobile front end on top of the same matches API |
| Geosearch | a spatial index rather than scanning every shop |

The architecture does not change. The deterministic core stays
deterministic. Only the parts behind each script get swapped for
production services.
