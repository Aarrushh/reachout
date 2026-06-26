# CLAUDE.md  (Layer 0: Where am I?)

This is a ReachOut workspace. It follows ICM (Interpretable Context
Methodology): folder structure is the architecture. One agent reads the
right files at the right moment. There is no orchestration framework.

Reference: Van Clief and McDermott, "Interpretable Context Methodology:
Folder Structure as Agentic Architecture", arXiv:2603.16021 (2026), MIT
licensed. The method inside the paper is called the Model Workspace
Protocol (MWP).

## What ReachOut is

A shopper searches for an item. The search is broadcast to shops within a
radius that have it in live stock. Matched shops are pinged instantly. See
`_config/product.md` for the full description.

## The one rule that matters most

Some work needs intelligence. Most does not. Keep them apart.

- Stock levels, distance, ranking, database writes: pure Python in
  `scripts/`. An AI never touches these. This is where a hallucination
  would be most dangerous, so no AI is allowed near it.
- Understanding a vague query, phrasing a friendly reply: the agent stages
  in `stages/`. Even there, every output is checked against a schema in
  `shared/schemas/` before the next stage trusts it.

## How to move through this workspace

1. Read this file. (You are here.)
2. Read `CONTEXT.md` (Layer 1) to see the stage order.
3. Enter a stage folder and read its `CONTEXT.md` (Layer 2) for the contract.
4. Load only the references and inputs that contract names. Nothing else.

## Layers

```
Layer 0  CLAUDE.md            this file. Always read first.
Layer 1  CONTEXT.md           stage routing.
Layer 2  stages/*/CONTEXT.md  the contract for one stage.
Layer 3  _config/, shared/    stable rules and schemas. The factory.
Layer 4  stages/*/output/     working files for this run. The product.
```
