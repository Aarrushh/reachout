# constraints.md  (Layer 3: the rules that prevent hallucination)

These rules hold across every stage. They are the reason ReachOut can trust
its own output.

## 1. The hardcoded / agentic split

Anything that does not need intelligence must not call an AI.

- Hardcoded (pure Python, `scripts/`): distance, stock levels, matching,
  ranking, database writes, pings.
- Agentic (`stages/`, optional LLM): understanding a vague query, phrasing
  a reply.

If you are unsure which side a task belongs to, ask one question: would a
wrong guess here invent a fact about the real world? If yes, it is hardcoded.

## 2. Schema-constrained output

Every structured AI output is validated against a JSON Schema in
`shared/schemas/` before the next stage uses it. A bad output is rejected,
not passed forward. See `scripts/validate.py`.

## 3. Grounded prompts only

An agent processes only the data it is given. It never invents a missing
field. If a field is missing it says so rather than filling the gap.

## 4. Numbers are copied, never generated

Prices, distances, stock counts, and shop names flow from the database
through to the final card unchanged. An LLM in Stage 03 may reword text. It
may not alter a number.

## 5. The database is the only source of truth for stock

If the store says zero, the answer is zero. No stage may claim an item is
available unless a live row says so.

## 6. Every output is a readable file

Each stage writes a plain file you can open and check. If something looks
wrong, you can see exactly where it came from.
