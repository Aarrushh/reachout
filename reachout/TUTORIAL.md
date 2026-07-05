# Building the ReachOut MVP

A step-by-step tutorial. By the end you have a working hyperlocal search
that pings shops, a live-updating inventory, and a repo you can push to
GitHub. The whole thing runs locally with one dependency.

This tutorial uses ICM, the Interpretable Context Methodology, where the
folder structure is the architecture (Van Clief and McDermott,
arXiv:2603.16021, 2026, MIT licensed). The method described in the paper is
called the Model Workspace Protocol. The version in your earlier notes
called it "the MWP paper". The correct paper title is "Interpretable Context
Methodology: Folder Structure as Agentic Architecture", and it has two
authors. The folder convention also differs slightly from your notes. The
real spec uses one `CONTEXT.md` per stage with Inputs, Process, and Outputs.
This repo follows the real spec.

---

## The one principle

Some work needs intelligence. Most does not. Keep them apart.

Ask one question of every task: would a wrong guess here invent a fact about
the real world? If yes, it must be plain code, not AI. Stock counts and
distances are facts. An AI must never guess them. Understanding that
"something for a headache" means pain relief is language, and that is where
AI earns its place.

That single split is what stops hallucination. It is not a clever prompt. It
is keeping the AI away from the numbers.

---

## What you are building

A shopper types what they need. The system finds shops within a radius that
have it in live stock, ranks them, and pings each one. The shopper sees who
has it, how far, and the price.

Three stages run in order:

```
01 parse-query     Agentic    free text        -> structured intent
02 match-and-ping  Hardcoded  intent + stock   -> ranked matches + pings
03 format-results  Agentic    matches          -> consumer card
```

Stage 02, the part that must be exact, is plain Python. Stages 01 and 03,
the language parts, are agentic and schema-checked.

---

## Step 0: prerequisites

You need Python 3.9 or newer. Check with `python --version`.

You do not need an API key. The repo runs end to end with a rule-based
parser. The LLM is optional and comes later.

---

## Step 1: the folder skeleton

Make the structure first. The numbers in the stage folders are the run
order. That is the ICM idea: the filesystem does the work a framework would
otherwise do in code.

```
reachout/
  CLAUDE.md
  CONTEXT.md
  _config/
  shared/schemas/
  stages/
    01-parse-query/output/
    02-match-and-ping/output/
    03-format-results/output/
  scripts/
  agent/
  data/notifications/
  run_pipeline.py
  demo.py
```

`CLAUDE.md` is the identity file an agent reads first. `CONTEXT.md` lists the
stage order. `_config/` holds the stable rules. `shared/schemas/` holds the
JSON schemas that catch bad data. Everything in `scripts/` is plain code.

---

## Step 2: build the deterministic core first

This is the heart of the MVP, and it has no AI in it at all. Build it before
anything else, because everything else depends on it being correct.

There are five small scripts in `scripts/`:

`geo.py` is pure math. It returns the distance between two points. Distance
is never something to guess, so it lives here.

`db.py` is the live inventory store. It uses SQLite in WAL mode so the
simulator can write while a search reads at the same time. Two tables: shops
and inventory.

`seed_data.py` creates the sample data: eight shops around Mumbai across four
categories, each with a few items in stock. This is fixed, known data. No AI
invents it.

`search_engine.py` is the matching engine. It filters shops by radius, reads
each one's live stock, keeps the items that match the keywords, ranks them,
and pings the matches. Whole-word matching, so the letter "c" does not match
"sachet".

`ping.py` is the broadcast. When a search matches a shop, that shop gets a
line written to its inbox and a printed alert. In production this is where a
push notification or SMS would go. The interface stays the same.

Seed the data and test the engine:

```
pip install -r requirements.txt
python scripts/seed_data.py
python scripts/search_engine.py
```

You should see a ping print for a paracetamol search. The core works.

---

## Step 3: the live inventory

`inventory_simulator.py` is the "constantly updated" part you asked for. On a
timer it picks random shops and does real movements. It sells units, so stock
drops and can hit zero. It restocks. It adds new items the shop did not carry
before. Every movement is written to the database and appended to
`data/events.jsonl`.

Run it and watch the stream:

```
python scripts/inventory_simulator.py
```

In a second terminal:

```
tail -f data/events.jsonl
```

You will see stock move in real time. This stands in for a real retailer
sync. When you go to production, you replace this one file with a feed from
each shop's point-of-sale system. Nothing else changes.

---

## Step 4: the schemas, your hallucination gate

In `shared/schemas/` there are three JSON schemas. They define exactly what
valid data looks like. `validate.py` checks any structured output against
them.

This matters because of the agentic stages. When an AI produces a search
intent, the schema checks it before the next stage trusts it. If the AI
invents a field or drops a required one, validation fails and the pipeline
stops. A bad output is rejected, not passed forward.

The schema for a search intent is strict on purpose. It allows only the
user's own words as keywords and only the four known categories. It does not
let the AI add anything the user did not say.

---

## Step 5: the agentic stages

Now the language parts, in `agent/`.

`query_parser.py` turns messy text into a clean intent. By default it uses
plain rules: strip filler words, expand a few everyday phrasings, keep
product terms. No AI needed. The whole repo runs on this alone.

`llm.py` is the optional upgrade. If you set an API key and pass `--use-llm`,
the parser calls a model to handle vaguer queries. The output still passes
through the schema. The model is told to put the user's exact text in
`raw_query` and never invent a product.

Either way, the parser only produces keywords. It never decides what is in
stock. That is Stage 02's job, and Stage 02 has no AI.

Test the parser:

```
python agent/query_parser.py
```

---

## Step 6: wire it together

`run_pipeline.py` is the orchestrator. It is not a framework. It is a short
loop that walks the stages in order and passes each one's output to the next.
Stage 01 writes `intent.json`. Stage 02 reads it, searches, and writes
`matches.json`. Stage 03 reads that and writes `card.json`.

Run a single search:

```
python run_pipeline.py "something for a headache" --lat 19.06 --lng 72.83
```

You see each stage run, the pings land, and a clean card at the end. Open the
files in each stage's `output/` folder to see exactly what was passed along.
That is the ICM payoff. The whole system state is just files you can read.

---

## Step 7: the live demo

`demo.py` ties it all together. It starts the inventory simulator in the
background, then fires several searches a couple of seconds apart. You watch
stock change between searches and pings arrive at shops in real time.

```
python demo.py
```

This is the product in miniature: live inventory on one side, a shopper on
the other, and an instant ping connecting them.

---

## Step 8: push to GitHub

The repo already has a `.gitignore` that keeps runtime data out of version
control. The live database, event log, shop inboxes, and stage outputs are
all regenerated, so they are ignored.

```
cd reachout
git init
git add .
git commit -m "ReachOut MVP: hyperlocal demand router"
```

Make a new empty repo on GitHub, then:

```
git remote add origin https://github.com/<your-username>/reachout.git
git branch -M main
git push -u origin main
```

Anyone who clones it runs `pip install -r requirements.txt`, then `python
demo.py`, and sees the same thing you see. The workspace is portable because
it is just a folder.

---

## Why this resists hallucination, in plain terms

Three things do the work.

First, the AI never touches a number. Stock and distance come from the
database and from math. The AI handles words, not facts.

Second, every AI output is schema-checked before anyone trusts it. Invented
fields get caught at the gate.

Third, every stage writes a readable file. If a result looks wrong, you open
the file and see exactly where it came from. There is no hidden state.

You do not prevent hallucination by asking the model nicely. You prevent it
by not giving the model anything it could hallucinate about.

---

## Where to go next

The MVP is intentionally narrow. Sensible next steps, in rough order:

A consumer front end. A simple web page that calls the same matches the
pipeline produces. The Blinkit-style interface sits on top of this engine.

A retailer dashboard. A screen where a shop sees incoming pings from its
inbox and replies with pickup or delivery.

A real inventory sync. Replace the simulator with a feed from a real
point-of-sale system for a few pilot shops.

A spatial index. Right now the engine checks every shop. With many shops you
would index by location so search stays fast.

Start with one city and a few categories. Get inventory accuracy right before
anything else. That is the part that makes or breaks the whole idea.

---

ReachOut MVP. Built on ICM (arXiv:2603.16021). MIT licensed.
