"""The orchestrator. One agent, reading the right files in order.

This is the ICM idea in code: the folder numbering is the execution order.
We walk the stages, passing each stage's output to the next. No framework,
just a loop and the filesystem.

Stage 01  parse-query     AGENTIC   free text  -> SearchIntent (validated)
Stage 02  match-and-ping  HARDCODED SearchIntent -> ranked matches + pings
Stage 03  format-results  AGENTIC   matches    -> consumer card (optional AI)

Usage:
    python run_pipeline.py "something for a headache" --lat 19.11 --lng 72.85
    python run_pipeline.py "usb c charger" --radius 5 --use-llm
"""

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "scripts"))
sys.path.insert(0, os.path.join(HERE, "agent"))

from query_parser import parse_query           # stage 01
from search_engine import search               # stage 02
import validate as v


def _write_output(stage_folder, filename, data):
    out_dir = os.path.join(HERE, "stages", stage_folder, "output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, filename)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    return path


def format_card(result, use_llm=False):
    """Stage 03. Default is a plain deterministic card. AI is optional and
    only rephrases. It is never allowed to change numbers or stock."""
    lines = []
    if result["match_count"] == 0:
        lines.append(f"No shops within {result['radius_km']} km have '{result['query']}' in stock right now.")
    else:
        lines.append(f"Found '{result['query']}' at {result['match_count']} nearby shop(s):")
        for m in result["matches"]:
            top = min(m["items"], key=lambda i: i["price"])
            lines.append(f"  - {m['shop_name']} ({m['distance_km']} km): "
                         f"{top['name']} at Rs {top['price']:.0f}, {top['qty']} in stock")
    card = {"query": result["query"], "match_count": result["match_count"],
            "matches": result["matches"], "display_text": "\n".join(lines)}
    return card


def run(query, lat, lng, radius_km=5.0, use_llm=False):
    print(f"\nStage 01  parse-query   : '{query}'")
    intent = parse_query(query, use_llm=use_llm)
    _write_output("01-parse-query", "intent.json", intent)
    print("           keywords      :", intent["keywords"])

    print("Stage 02  match-and-ping : searching live inventory and pinging shops")
    result = search(intent, lat, lng, radius_km=radius_km, do_ping=True)
    _write_output("02-match-and-ping", "matches.json", result)
    print(f"           matches       : {result['match_count']}")

    print("Stage 03  format-results : building consumer card")
    card = format_card(result, use_llm=use_llm)
    ok, err = v.validate(card, "shop_match.schema.json")
    if not ok:
        print("           [WARN] card failed schema:", err)
    _write_output("03-format-results", "card.json", card)

    print("\n" + card["display_text"] + "\n")
    return card


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("query")
    p.add_argument("--lat", type=float, default=19.11)
    p.add_argument("--lng", type=float, default=72.85)
    p.add_argument("--radius", type=float, default=5.0)
    p.add_argument("--use-llm", action="store_true", help="use the LLM parser if a key is set")
    args = p.parse_args()
    run(args.query, args.lat, args.lng, radius_km=args.radius, use_llm=args.use_llm)
