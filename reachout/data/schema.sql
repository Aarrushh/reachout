-- ReachOut backend v2 — Supabase schema (idempotent: safe to run repeatedly).
-- Apply once in the Supabase SQL editor, or let data/seed_inventory.py apply it
-- via SUPABASE_DB_URL / SUPABASE_ACCESS_TOKEN if either is set in .env.

create extension if not exists vector;

-- ---------------------------------------------------------------------------
-- stores: 50 local shops across real Madrid barrios
-- ---------------------------------------------------------------------------
create table if not exists stores (
    id                uuid primary key default gen_random_uuid(),
    name              text not null,
    neighbourhood     text not null,
    avg_delivery_mins int  not null default 30,
    is_open           boolean not null default true,
    rating            float not null default 4.0
);

-- ---------------------------------------------------------------------------
-- products: 3000-5000 rows, one embedding per row (vector(768),
-- gemini-embedding-001 with outputDimensionality=768, L2-normalized client-side)
-- ---------------------------------------------------------------------------
create table if not exists products (
    id            uuid primary key default gen_random_uuid(),
    name          text not null,
    description   text,
    category      text not null,
    price         numeric(10, 2) not null,
    stock_qty     int not null default 0,
    store_id      uuid not null references stores (id) on delete cascade,
    neighbourhood text not null,
    tags          text[] not null default '{}',
    image_url     text,
    embedding     vector(768)
);

-- ivfflat wants data present when it picks centroids; with a few thousand rows
-- this is still fine to create up-front — recall at this scale is a non-issue.
create index if not exists products_embedding_idx
    on products using ivfflat (embedding vector_cosine_ops) with (lists = 100);

create index if not exists products_neighbourhood_idx on products (neighbourhood);
create index if not exists products_category_idx      on products (category);
create index if not exists products_store_id_idx      on products (store_id);
create index if not exists stores_neighbourhood_idx   on stores (neighbourhood);

-- Dev mode: RLS stays OFF (plan decision). The API talks to Supabase with the
-- secret key only. Do NOT ship an anon-key client until RLS is enabled.
alter table stores   disable row level security;
alter table products disable row level security;

-- ---------------------------------------------------------------------------
-- match_products: cosine top-K with optional neighbourhood filter.
-- PostgREST cannot ORDER BY `embedding <=> $q` on a plain table read, so
-- vector search is exposed as an RPC.
-- ---------------------------------------------------------------------------
create or replace function match_products(
    query_embedding vector(768),
    match_count     int  default 20,
    p_neighbourhood text default null
)
returns table (
    id            uuid,
    name          text,
    description   text,
    category      text,
    price         numeric,
    stock_qty     int,
    store_id      uuid,
    neighbourhood text,
    tags          text[],
    image_url     text,
    similarity    float
)
language sql stable
as $$
    select p.id, p.name, p.description, p.category, p.price, p.stock_qty,
           p.store_id, p.neighbourhood, p.tags, p.image_url,
           1 - (p.embedding <=> query_embedding) as similarity
    from products p
    where p.embedding is not null
      and (p_neighbourhood is null or p.neighbourhood = p_neighbourhood)
    order by p.embedding <=> query_embedding
    limit match_count;
$$;
