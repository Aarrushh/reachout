# ReachOut

A hyperlocal demand router. A shopper searches for an item. Shops within a
radius that have it in live stock get pinged instantly. The shopper sees who
has it, how far, and at what price.

This repo is an MVP. It is built so that the parts that must be exact are
exact, and the AI only handles the parts where language understanding helps.
That split is the whole point. It is how the system avoids inventing stock
that does not exist.

## The idea in one line

You do not browse a store. You say what you need, and nearby stores answer.

## How it is built

The folder structure is the architecture. This follows ICM, the Interpretable
Context Methodology (Van Clief and McDermott, arXiv:2603.16021, 2026). Numbered
stage folders run in order. Each writes a plain file the next one reads.

```
reachout/
  CLAUDE.md            Layer 0. Identity. Read first.
  CONTEXT.md           Layer 1. Stage order.
  _config/             Layer 3. Product, constraints, tech stack.
  shared/schemas/      JSON schemas. The hallucination gate.
  stages/
    01-parse-query/    Agentic. Free text -> structured intent.
    02-match-and-ping/ Hardcoded. Intent + live stock -> matches + pings.
    03-format-results/ Agentic. Matches -> consumer card.
  scripts/             Pure Python. No AI. The deterministic core.
  agent/               Optional LLM adapter plus rule-based fallback.
  data/                Live SQLite store, event log, shop inboxes.
  run_pipeline.py      Orchestrator. Walks the stages.
  demo.py              Live end-to-end demo.
```

## The hardcoded / agentic split

Hardcoded, in `scripts/`, no AI: distance, stock levels, matching, ranking,
database writes, pings. A wrong guess here would invent a real-world fact, so
no AI is allowed near it.

Agentic, in `stages/`, optional LLM: understanding a vague query like
"something for a headache", and phrasing the reply. Even here every output is
checked against a schema before the next stage trusts it.

## Run it

```
pip install -r requirements.txt
python scripts/seed_data.py          # create sample shops and stock
python demo.py                       # live demo: stock moves while you search
```

Single search:

```
python run_pipeline.py "usb c charger" --lat 19.06 --lng 72.83 --radius 5
```

Watch live inventory move in another terminal:

```
python scripts/inventory_simulator.py
# then, elsewhere:
tail -f data/events.jsonl
```

## Optional AI parser

The repo runs fully without any API key, using a rule-based parser. To use an
LLM instead:

```
pip install anthropic
export ANTHROPIC_API_KEY=...
python run_pipeline.py "something for my cold" --use-llm
```

See `agent/llm.py`. The model name there should be checked against the current
docs before you ship, since model names change.

## What is sample versus real

The shops, the starting stock, and the inventory simulator are sample data for
the MVP. In production the simulator is replaced by a real sync from each
shop's point-of-sale or inventory system. The matching engine, the schemas,
and the stage structure stay the same.

## License

MIT. See LICENSE.
