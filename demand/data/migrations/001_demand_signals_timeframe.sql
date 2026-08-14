-- ReachOut demand service — migration 001
-- Adds `timeframe` to demand.demand_signals and puts it in the dedupe key.
--
-- WHY THIS IS A SEPARATE FILE AND NOT AN EDIT TO schema.sql ALONE
-- ---------------------------------------------------------------------------
-- schema.sql is written with `create table if not exists`. Re-pasting it
-- against a database where demand.demand_signals ALREADY EXISTS is a no-op:
-- Postgres sees the table, skips the statement, and reports success while
-- changing nothing. The 686 rows already in the table would keep the old
-- shape and the old unique index, and the run that follows would still
-- overwrite them. So the live database needs this ALTER, and schema.sql
-- needs the matching edit so that a rebuild from scratch lands in the same
-- place. Both. Neither one alone is sufficient.
--
-- Apply once, by hand, in the Supabase SQL editor (the project's key cannot
-- run DDL). Idempotent: safe to run twice.
--
-- WHAT IT FIXES
-- ---------------------------------------------------------------------------
-- demand_signals dedupes on (keyword, geo, window_start, window_end), with no
-- timeframe. trend_snapshots DOES carry timeframe in its key, so captures at
-- `today 3-m` and `today 12-m` sit safely side by side. Their derived signals
-- do not: for every overlapping weekly window they collide on one row and the
-- later write wins.
--
-- Those two rows are not the same measurement. Google returns a 0-100 index
-- scaled to the requested window, and this pipeline additionally rescales each
-- batch onto a shared anchor, so the same keyword in the same calendar week
-- legitimately reads differently at 3-m and at 12-m. Merging them silently
-- produces a demand history whose values are not comparable to each other and
-- which carries no column saying so.
--
-- This is the same defect, and the same fix, as putting `gprop` into the
-- rising_queries natural key: a discriminator that changes what a row MEANS
-- belongs in the key, or rows that mean different things merge.

-- Step 1: add the column nullable. It cannot be added NOT NULL in one shot --
-- the 686 existing rows have no value for it and the statement would fail.
alter table demand.demand_signals
    add column if not exists timeframe text;

-- Step 2: backfill. Every signal row in the table today was derived from a
-- `today 3-m` capture -- verified against demand.trend_snapshots, where all 49
-- rows read timeframe = 'today 3-m'. This is a statement of recorded fact, not
-- a default: if that query ever stops returning only 'today 3-m', stop and
-- work out which rows came from where instead of running this.
update demand.demand_signals
   set timeframe = 'today 3-m'
 where timeframe is null;

-- Step 3: now the column can carry the constraint that makes it part of a key.
alter table demand.demand_signals
    alter column timeframe set not null;

-- Step 4: the new dedupe key. Created BEFORE the old one is dropped so that if
-- it fails on unexpected duplicates, the table is left with its old index
-- intact rather than with none at all. It cannot fail on today's data:
-- timeframe is uniform after step 2, so the new key partitions the rows
-- exactly as the old one did.
create unique index if not exists demand_signals_dedupe_tf_idx
    on demand.demand_signals (keyword, geo, timeframe, window_start, window_end);

-- Step 5: retire the old key. Leaving it in place would keep enforcing the
-- collision this migration exists to remove -- the 12-m backfill would still
-- be rejected or still overwrite, and the new index would look like it had
-- worked.
drop index if exists demand.demand_signals_dedupe_idx;
