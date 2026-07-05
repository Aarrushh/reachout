# CONTEXT.md  (Layer 1: Where do I go?)

This routes a search through three stages. The folder numbers are the
order. Each stage reads the previous stage's `output/`.

## Pipeline

| Stage | Folder | Kind | Reads | Writes |
|-------|--------|------|-------|--------|
| 01 | `stages/01-parse-query/` | Agentic | the user's free text | `output/intent.json` |
| 02 | `stages/02-match-and-ping/` | Hardcoded | `01/output/intent.json` + live DB | `output/matches.json` + pings |
| 03 | `stages/03-format-results/` | Agentic | `02/output/matches.json` | `output/card.json` |

## Run it

```
python run_pipeline.py "something for a headache" --lat 19.06 --lng 72.83
```

The orchestrator walks these stages in order. To see it live with stock
moving in the background, run `python demo.py`.

## Stage kinds

Agentic stages may use an LLM but default to deterministic logic and always
validate output against a schema. Hardcoded stages are pure Python and never
call an AI. Stage 02 is hardcoded on purpose: it is the part that must never
be guessed.
