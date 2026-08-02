import json
import os
from typing import Any

# Use absolute path resolving relative to this file's location to find seed_keywords.json
# since this is in demand/ingest/ and we want demand/_config/seed_keywords.json
CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), '_config', 'seed_keywords.json')


def normalize_keyword(keyword: Any) -> str:
    """THE canonical casing rule for the whole demand chain: strip, lower.

    One rule, three stages, no exceptions:

    - `build_universe()` dedupes on it (the universe still carries each
      keyword's ORIGINAL casing -- that is what gets sent to the trends
      provider, and Trends is case-sensitive about what it echoes back).
    - `run_ingest.run_chain()` keys the category map with it.
    - `compute_signals()` looks the category up through it.

    Before this existed the map was keyed lower-case and the lookup was an
    exact match against the original casing, so in production the lookup
    missed on every keyword whose category was not already lower-case and
    every signal row was written with `category: None`. Anything that
    joins a keyword to a category must go through this function.
    """
    return str(keyword).strip().lower()


def build_universe(supa_client: Any) -> list[str]:
    """
    Builds the keyword universe from seed keywords and distinct non-empty
    products.category values from the database.

    `products` is read through `.schema("public")` EXPLICITLY. The client
    this runs on is built with `ClientOptions(schema="demand")`
    (`demand/api/app.py`), so a bare `.table("products")` resolves to
    `demand.products`, which does not exist -- `demand/data/schema.sql`
    creates exactly three tables and `products` is not one of them. Every
    cross-schema read in this service names its schema.
    """
    if not os.path.exists(CONFIG_PATH):
        raise FileNotFoundError(f"Seed file not found at {CONFIG_PATH}")

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        seed_keywords = json.load(f)

    # Get products from DB (public schema -- see the docstring)
    result = supa_client.schema('public').table('products').select('category').execute()
    db_categories = []
    if hasattr(result, 'data') and result.data:
        db_categories = [
            row.get('category') 
            for row in result.data 
            if row.get('category') and str(row.get('category')).strip()
        ]
        
    # Dedupe case-insensitively, seed keywords win ties
    # Dicts maintain insertion order since Python 3.7, but we don't strictly need it 
    # since we'll sort anyway. We just need to ensure seed wins ties for casing.
    unique_keywords = {}
    
    for kw in seed_keywords:
        lower_kw = normalize_keyword(kw)
        if lower_kw and lower_kw not in unique_keywords:
            unique_keywords[lower_kw] = kw

    for cat in db_categories:
        lower_cat = normalize_keyword(cat)
        if lower_cat and lower_cat not in unique_keywords:
            unique_keywords[lower_cat] = cat

    # Deterministically sort alphabetically
    sorted_keywords = sorted(unique_keywords.values(), key=normalize_keyword)
    
    # Cap at 100 elements
    return sorted_keywords[:100]
