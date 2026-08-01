# CLAUDE.md  (Layer 0: Where am I?)

This is a ReachOut workspace: the **demand service**. It follows ICM
(Interpretable Context Methodology): folder structure is the architecture.
One agent reads the right files at the right moment. There is no
orchestration framework.

Reference: Van Clief and McDermott, "Interpretable Context Methodology:
Folder Structure as Agentic Architecture", arXiv:2603.16021 (2026), MIT
licensed. The method inside the paper is called the Model Workspace
Protocol (MWP).

## What the demand service is

A separate backend root from `reachout/` (the shopper search app). It
batch-ingests Google Trends interest data for a curated set of Madrid
retail search terms, turns those captures into per-keyword demand signals
(rising / falling / flat, with a deterministic confidence label), composes
those signals against store/product stock to produce retailer-facing
recommendations, and serves all three — trends, signals, recommendations —
over its own public FastAPI app. It is read by the retail dashboard half of
the frontend. See `docs/IMPLEMENTATION_PLAN_V2.md` for the full plan.

## The one rule that matters most

Some work needs intelligence. Most does not. Keep them apart — and in this
workspace specifically, no work needs intelligence.

- Stock levels, trend math, thresholds, rankings, confidence labels,
  database writes: pure Python in `ingest/` and `scripts/`. An AI never
  touches these. This is where a hallucination would be most dangerous, so
  no AI is allowed near it.
- Retailer-facing copy (headline/body text): fixed Python string templates,
  not generated language. **There are no agentic stages in `demand/`.**
  Every payload that crosses a module boundary is still checked against a
  schema in `shared/schemas/` before the next module trusts it — the
  schema discipline applies even though nothing here is AI-authored.

## How to move through this workspace

1. Read this file. (You are here.)
2. Read `CONTEXT.md` (Layer 1) to see the ingest -> signals -> recommend ->
   api chain and which files exist vs. are still planned.
3. Load only the references, schemas, and fixtures that chain names.
   Nothing else.

## Layers

```
Layer 0  CLAUDE.md            this file. Always read first.
Layer 1  CONTEXT.md           chain routing: ingest -> signals -> recommend -> api.
Layer 2  (none yet)           this workspace has no per-stage subfolders.
Layer 3  _config/, shared/    stable rules and schemas. The factory.
Layer 4  data/                snapshot/signal/recommendation tables. The product.
```
