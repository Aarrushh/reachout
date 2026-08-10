"""Seed Supabase with 50 Madrid stores + ~3,800 products with pgvector embeddings.

Usage:  python data/seed_inventory.py [--reset] [--min-per-store 70] [--max-per-store 80]

Design (see docs/DECISIONS_V2.md):
- Embeddings are computed once per UNIQUE catalog item (name/description/category
  is what gets embedded; per-store rows only vary price/stock) and reused across
  stores, requested via batchEmbedContents in chunks of 100 — a handful of API
  calls instead of thousands. Vectors are L2-normalized in api/gemini.py.
- schema.sql cannot be applied through the sb_secret REST key. ensure_schema()
  verifies the tables+RPC exist and, if not, applies schema.sql itself when
  SUPABASE_DB_URL or SUPABASE_ACCESS_TOKEN is set — otherwise prints the
  one-time SQL-editor instruction and exits 2.
"""

import argparse
import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from faker import Faker

DATA_DIR = Path(__file__).resolve().parent
REACHOUT_DIR = DATA_DIR.parent
REPO_ROOT = REACHOUT_DIR.parent
sys.path.insert(0, str(REACHOUT_DIR))

load_dotenv(REACHOUT_DIR / ".env")

from api import gemini  # noqa: E402
from api.madrid import BARRIOS  # noqa: E402
from api.supa import get_client  # noqa: E402

RNG = random.Random(42)  # deterministic store/product composition
fake = Faker("es_ES")
Faker.seed(42)

# stores per category (sums to 50)
CATEGORY_STORE_COUNTS = {
    "grocery": 14, "pharmacy": 10, "hardware": 9, "electronics": 9, "stationery": 8
}

STORE_NAME_PREFIXES = {
    "pharmacy": ["Farmacia", "Parafarmacia"],
    "grocery": ["Ultramarinos", "Alimentación", "Supermercado", "Frutería"],
    "hardware": ["Ferretería", "Bricolaje", "Ferretería Industrial"],
    "electronics": ["Electrónica", "TecnoHogar", "Móviles"],
    "stationery": ["Papelería", "Librería"],
}

# DummyJSON category -> reachout category (unmapped categories are skipped)
DJ_CATEGORY_MAP = {
    "groceries": "grocery",
    "kitchen-accessories": "hardware",
    "home-decoration": "hardware",
    "furniture": "hardware",
    "smartphones": "electronics",
    "mobile-accessories": "electronics",
    "laptops": "electronics",
    "tablets": "electronics",
    "mens-watches": "electronics",
    "womens-watches": "electronics",
    "beauty": "pharmacy",
    "fragrances": "pharmacy",
    "skin-care": "pharmacy",
}

# pack/size variants used to widen thin categories (unique name => own embedding)
VARIANT_SUFFIXES = ["pack 2 unidades", "formato ahorro", "tamaño viaje", "edición premium"]
MIN_POOL_PER_CATEGORY = 70

DESC_BLURBS = {
    "pharmacy": "Producto de parafarmacia de venta libre. Consulta a tu farmacéutico de confianza.",
    "grocery": "Producto fresco de alimentación, reposición diaria en tienda de barrio.",
    "hardware": "Artículo de ferretería y hogar, calidad profesional para el día a día.",
    "electronics": "Electrónica de consumo con garantía. Pruébalo en tienda antes de llevártelo.",
    "stationery": "Material de papelería para oficina, escuela y dibujo.",
}


def _tags(name: str, category: str, extra: list[str] | None = None) -> list[str]:
    words = [w.lower() for w in re.findall(r"[A-Za-zÁÉÍÓÚáéíóúñÑ]{4,}", name)][:4]
    tags = [category] + words + [t.lower() for t in (extra or [])]
    seen, out = set(), []
    for t in tags:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:8]


def build_catalog_pool() -> dict[str, list[dict]]:
    """Merge sku_catalog + dummyjson into per-category pools of unique items."""
    pool: dict[str, list[dict]] = {c: [] for c in CATEGORY_STORE_COUNTS}

    sku = json.loads((DATA_DIR / "sku_catalog.json").read_text(encoding="utf-8"))
    for category, items in sku.items():
        if category.startswith("_"):
            continue
        for it in items:
            pool[category].append({
                "name": it["name"],
                "description": f"{it['name']}. {DESC_BLURBS[category]}",
                "category": category,
                "base_price": float(it["base_price_eur"]),
                "tags": _tags(it["name"], category),
                "image_url": f"https://picsum.photos/seed/{it['sku']}/400/300",
            })

    dj = json.loads((DATA_DIR / "dummyjson_cache" / "products.json").read_text(encoding="utf-8"))
    seen = {c: {it["name"] for it in items} for c, items in pool.items()}
    for p in (dj["products"] if isinstance(dj, dict) else dj):
        category = DJ_CATEGORY_MAP.get(p["category"])
        # the cache contains duplicate entries (overlapping fetch pages) —
        # keep first occurrence only
        if not category or p["title"] in seen[category]:
            continue
        seen[category].add(p["title"])
        pool[category].append({
            "name": p["title"],
            "description": (p.get("description") or "").strip()[:400],
            "category": category,
            "base_price": max(0.5, float(p["price"])),
            "tags": _tags(p["title"], category, p.get("tags")),
            "image_url": p.get("thumbnail") or f"https://picsum.photos/seed/dj{p['id']}/400/300",
        })

    # widen thin categories with pack/size variants of existing items.
    # i is bounded by every possible (base, suffix) pair: a category with few
    # base items (stationery: 10) simply tops out below MIN_POOL_PER_CATEGORY
    # instead of looping forever on duplicate names.
    for category, items in pool.items():
        base = list(items)
        i = 0
        while len(items) < MIN_POOL_PER_CATEGORY and i < len(base) * len(VARIANT_SUFFIXES):
            src = base[i % len(base)]
            suffix = VARIANT_SUFFIXES[(i // len(base)) % len(VARIANT_SUFFIXES)]
            i += 1
            name = f"{src['name']} ({suffix})"
            if any(x["name"] == name for x in items):
                continue
            mult = {"pack 2 unidades": 1.9, "formato ahorro": 1.45,
                    "tamaño viaje": 0.6, "edición premium": 1.8}[suffix]
            items.append({**src, "name": name,
                          "base_price": round(src["base_price"] * mult, 2),
                          "tags": src["tags"],
                          "image_url": src["image_url"]})
    return pool


def generate_stores() -> list[dict]:
    stores = []
    for category, count in CATEGORY_STORE_COUNTS.items():
        for _ in range(count):
            prefix = RNG.choice(STORE_NAME_PREFIXES[category])
            stores.append({
                "name": f"{prefix} {fake.last_name()}",
                "neighbourhood": RNG.choice(BARRIOS),
                "avg_delivery_mins": RNG.randint(12, 45),
                "is_open": RNG.random() < 0.85,
                "rating": round(RNG.uniform(3.6, 4.9), 1),
                "_category": category,  # stripped before insert
            })
    RNG.shuffle(stores)
    return stores


def embed_pool(pool: dict[str, list[dict]]) -> None:
    """Attach an embedding to every unique catalog item, in-place."""
    items = [it for cat_items in pool.values() for it in cat_items]
    texts = [f"{it['name']}. {it['description']} Categoría: {it['category']}. "
             f"Etiquetas: {', '.join(it['tags'])}" for it in items]
    print(f"[embed] {len(texts)} unique catalog items "
          f"-> {(len(texts) + 99) // 100} batchEmbedContents calls")
    t0 = time.time()
    vectors = gemini.embed_texts(texts, task_type="RETRIEVAL_DOCUMENT", pause=15.0)
    for it, vec in zip(items, vectors):
        it["embedding"] = vec
    print(f"[embed] done in {time.time() - t0:.1f}s")


# ---------------------------------------------------------------------------
# schema handling
# ---------------------------------------------------------------------------

def _schema_present(sb) -> bool:
    try:
        sb.table("stores").select("id").limit(1).execute()
        sb.table("products").select("id").limit(1).execute()
        sb.rpc("match_products",
               {"query_embedding": [0.0] * 768, "match_count": 1}).execute()
        return True
    except Exception as e:
        print(f"[schema] probe failed ({str(e)[:120]}) — schema not (fully) applied")
        return False


def _apply_via_db_url(sql: str, db_url: str) -> bool:
    try:
        import psycopg
    except ImportError:
        print("[schema] SUPABASE_DB_URL is set but psycopg is not installed "
              "(pip install 'psycopg[binary]')")
        return False
    print("[schema] applying schema.sql over direct Postgres connection...")
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(sql)
    return True


def _apply_via_mgmt_api(sql: str, token: str) -> bool:
    ref = os.environ["SUPABASE_URL"].split("//")[1].split(".")[0]
    print("[schema] applying schema.sql via Supabase Management API...")
    resp = requests.post(
        f"https://api.supabase.com/v1/projects/{ref}/database/query",
        json={"query": sql},
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    )
    if resp.status_code >= 300:
        print(f"[schema] management API refused: HTTP {resp.status_code} {resp.text[:200]}")
        return False
    return True


def ensure_schema(sb) -> None:
    if _schema_present(sb):
        print("[schema] tables + match_products RPC present")
        return
    sql = (DATA_DIR / "schema.sql").read_text(encoding="utf-8")
    applied = False
    if os.environ.get("SUPABASE_DB_URL"):
        applied = _apply_via_db_url(sql, os.environ["SUPABASE_DB_URL"])
    if not applied and os.environ.get("SUPABASE_ACCESS_TOKEN"):
        applied = _apply_via_mgmt_api(sql, os.environ["SUPABASE_ACCESS_TOKEN"])
    if applied and _schema_present(sb):
        print("[schema] applied and verified")
        return
    print(
        "\n[schema] BLOCKED: the sb_secret API key cannot run DDL.\n"
        "Fix (once): open the Supabase dashboard -> SQL editor and run\n"
        f"  {DATA_DIR / 'schema.sql'}\n"
        "or set SUPABASE_DB_URL (or SUPABASE_ACCESS_TOKEN) in reachout/.env\n"
        "and re-run this script.\n"
    )
    sys.exit(2)


# ---------------------------------------------------------------------------
# seeding
# ---------------------------------------------------------------------------

def reset(sb) -> None:
    print("[reset] deleting existing products + stores...")
    sb.table("products").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()
    sb.table("stores").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()


def seed(min_per_store: int, max_per_store: int, do_reset: bool) -> None:
    sb = get_client()
    ensure_schema(sb)

    existing = sb.table("products").select("id", count="exact").limit(1).execute().count or 0
    if existing and not do_reset:
        print(f"[seed] products table already has {existing} rows — "
              "re-run with --reset to reseed from scratch")
        sys.exit(0)
    if do_reset:
        reset(sb)

    pool = build_catalog_pool()
    for category, items in pool.items():
        print(f"[pool] {category}: {len(items)} unique items")
    embed_pool(pool)

    stores = generate_stores()
    rows = [{k: v for k, v in s.items() if not k.startswith("_")} for s in stores]
    inserted = sb.table("stores").insert(rows).execute().data
    for store, row in zip(stores, inserted):
        store["id"] = row["id"]
    print(f"[stores] inserted {len(inserted)} stores across "
          f"{len({s['neighbourhood'] for s in stores})} barrios")

    products = []
    for store in stores:
        items = pool[store["_category"]]
        n = min(RNG.randint(min_per_store, max_per_store), len(items))
        for it in RNG.sample(items, n):
            products.append({
                "name": it["name"],
                "description": it["description"],
                "category": it["category"],
                "price": round(it["base_price"] * RNG.uniform(0.85, 1.15), 2),
                "stock_qty": 0 if RNG.random() < 0.12 else RNG.randint(1, 40),
                "store_id": store["id"],
                "neighbourhood": store["neighbourhood"],
                "tags": it["tags"],
                "image_url": it["image_url"],
                "embedding": it["embedding"],
            })

    print(f"[products] inserting {len(products)} rows in chunks of 100...")
    for i in range(0, len(products), 100):
        chunk = products[i:i + 100]
        for attempt in range(5):
            try:
                sb.table("products").insert(chunk).execute()
                break
            except Exception as e:
                if attempt == 4:
                    raise
                wait = 2 ** attempt
                print(f"[products] chunk {i // 100} failed ({str(e)[:120]}), retry in {wait}s")
                time.sleep(wait)
        done = min(i + 100, len(products))
        if done % 500 == 0 or done == len(products):
            print(f"[products] {done}/{len(products)}")

    store_count = sb.table("stores").select("id", count="exact").limit(1).execute().count
    product_count = sb.table("products").select("id", count="exact").limit(1).execute().count
    print(f"[verify] Supabase now holds {store_count} stores / {product_count} products")
    if not store_count or not product_count or product_count < len(products):
        print("[verify] FAILED — counts do not match what was inserted")
        sys.exit(1)

    contract = REPO_ROOT / "SHARED_CONTRACT.md"
    text = contract.read_text(encoding="utf-8")
    text = text.replace("# [ ] PHASE_1_DB_READY", "# [x] PHASE_1_DB_READY")
    contract.write_text(text, encoding="utf-8")
    print("[done] PHASE_1_DB_READY ticked in SHARED_CONTRACT.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="wipe stores/products first")
    ap.add_argument("--min-per-store", type=int, default=70)
    ap.add_argument("--max-per-store", type=int, default=80)
    args = ap.parse_args()
    seed(args.min_per_store, args.max_per_store, args.reset)
