import asyncio
import json
import os
import sys
import uuid

import pytest

# Setting this before anything gets imported
os.environ["DEMAND_TRENDS_PROVIDER"] = "fixture"

from demand.tests.fake_supa import FakeSupabase
from demand.api import app
from demand.scripts.run_ingest import INGEST_TIMEFRAME, run_chain, snapshot_id
import demand.scripts.run_ingest


def make_client(products):
    """A fake shaped like production: the client is bound to `demand`.

    `get_client()` builds the real client with
    `ClientOptions(schema="demand")`, so only the three tables in
    `demand/data/schema.sql` are reachable unqualified. `products` is a
    `public` table and must be asked for by name -- declaring it here in
    the default schema is exactly the fixture-shaped blindness that let
    three `client.table("products")` calls ship: against real Supabase they
    resolve to `demand.products`, which does not exist.
    """
    return FakeSupabase(
        default_schema="demand",
        tables={
            'trend_snapshots': [],
            'demand_signals': [],
            'recommendations': [],
            'rising_queries': [],
        },
        schemas={"public": {"products": products}},
    )


@pytest.fixture
def fake_client(tmp_path):
    # Set up some dummy categories that the fixture keywords will resolve to.
    # The fixture keywords in interest_over_time.json (sneakers, coffee, etc.)
    products_data = [
        {"category": "sneakers", "store_id": str(uuid.uuid4()), "stock_qty": 5},
        {"category": "coffee", "store_id": str(uuid.uuid4()), "stock_qty": 5}
    ]

    # Needs to match the format of keywords seed file
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(["sneakers", "coffee"]))

    return make_client(products_data), seed_file


class EchoProvider:
    """Returns the same weekly series for every keyword it is handed, with
    the keyword's casing preserved exactly as the universe spelled it.

    The canned `fixture` provider only knows two lower-case keywords, so it
    cannot exercise the universe -> category-map -> lookup casing path or a
    series long enough to reach the `high` tier.
    """

    def __init__(self, series):
        self.series = series
        self.requested_keywords = None
        self.requested_timeframe = None
        self.requested_geo = None

    def interest_over_time(self, keywords, geo, timeframe):
        self.requested_keywords = list(keywords)
        self.requested_timeframe = timeframe
        self.requested_geo = geo
        return {kw: [dict(pt) for pt in self.series] for kw in keywords}

    def interest_by_region(self, keyword, geo):
        return []

    def rising_queries(self, keyword, geo, date, gprop):
        return []


def weekly_series(values, first_monday="2023-10-02"):
    from datetime import date, timedelta
    start = date.fromisoformat(first_monday)
    return [
        {"date": (start + timedelta(weeks=i)).isoformat(), "value": float(v)}
        for i, v in enumerate(values)
    ]


class DiscoveryProvider:
    """A provider whose discovery half actually answers.

    `EchoProvider.rising_queries` returns `[]` unconditionally, so the entire
    discovery pass in `run_chain` -- parent selection, `build_rows`,
    `store_rising_queries`, the counters -- never ran its body in any test.
    That is precisely how the parent-selection defect survived to the end of
    the branch: the newest code, and the only code that spends money, was the
    only code with no integration test.
    """

    def __init__(self, series_by_keyword, rising_by_keyword=None):
        self.series_by_keyword = series_by_keyword
        self.rising_by_keyword = rising_by_keyword or {}
        self.rising_calls = []
        self.requested_keywords = None

    def interest_over_time(self, keywords, geo, timeframe):
        self.requested_keywords = list(keywords)
        return {kw: [dict(pt) for pt in self.series_by_keyword.get(kw, [])]
                for kw in keywords}

    def interest_by_region(self, keyword, geo):
        return []

    def rising_queries(self, keyword, geo, date, gprop):
        # Recorded, not counted: one search per entry, and a duplicate entry
        # is a duplicate charge.
        self.rising_calls.append((keyword, geo, date, gprop))
        return [dict(r) for r in self.rising_by_keyword.get(keyword, [])]

def test_full_chain_upserts(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))

    # Mock the get_client to return our fake client
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain not in dry run
    run_chain(provider_name="fixture", dry_run=False)

    snapshots = client.table('trend_snapshots')._data
    assert len(snapshots) > 0
    assert all("id" in s for s in snapshots)

    signals = client.table('demand_signals')._data
    assert len(signals) > 0
    assert all("id" in s for s in signals)

    recommendations = client.table('recommendations')._data
    assert len(recommendations) > 0
    assert all("id" in r for r in recommendations)
    assert all("store_id" in r for r in recommendations)
    assert all("signal_id" in r for r in recommendations)

def test_dry_run_writes_nothing(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))

    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain in dry run
    run_chain(provider_name="fixture", dry_run=True)

    assert len(client.table('trend_snapshots')._data) == 0
    assert len(client.table('demand_signals')._data) == 0
    assert len(client.table('recommendations')._data) == 0

def test_idempotent_rerun(fake_client, monkeypatch):
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))

    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    # Run the chain first time
    run_chain(provider_name="fixture", dry_run=False)

    snap_count = len(client.table('trend_snapshots')._data)
    sig_count = len(client.table('demand_signals')._data)
    rec_count = len(client.table('recommendations')._data)

    snap_ids = sorted(r["id"] for r in client.table('trend_snapshots')._data)
    sig_ids = sorted(r["id"] for r in client.table('demand_signals')._data)
    rec_ids = sorted(r["id"] for r in client.table('recommendations')._data)

    assert snap_count > 0

    # Run again
    run_chain(provider_name="fixture", dry_run=False)

    # The counts should be the same
    assert len(client.table('trend_snapshots')._data) == snap_count
    assert len(client.table('demand_signals')._data) == sig_count
    assert len(client.table('recommendations')._data) == rec_count

    # ...and so should the IDENTITIES. A stable row count with churning ids
    # is not idempotency: every FK pointing at a signal or a recommendation
    # would have been invalidated by the re-run.
    assert sorted(r["id"] for r in client.table('trend_snapshots')._data) == snap_ids
    assert sorted(r["id"] for r in client.table('demand_signals')._data) == sig_ids
    assert sorted(r["id"] for r in client.table('recommendations')._data) == rec_ids


def test_category_resolves_through_the_real_universe_to_map_to_lookup_path(tmp_path, monkeypatch):
    """Finding 1, end to end: the universe carries the DB's original casing
    ("Zapatillas"), the category map is keyed by the normalised keyword, and
    the lookup inside compute_signals normalises the same way. An
    exact-match lookup against a lower-cased map key stamps every row
    `category: None` -- which is what production was doing.
    """
    store_id = "aaaaaaaa-0000-4000-8000-000000000001"
    # Capital Z: the category as the retailer typed it.
    client = make_client([{"category": "Zapatillas", "store_id": store_id, "stock_qty": 5}])

    # No seed keywords, so the universe is exactly the DB category and keeps
    # its original casing on the way to the provider.
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps([]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    provider = EchoProvider(weekly_series([20, 24, 29, 35, 42, 50, 60, 72]))
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_provider', lambda name: provider)

    run_chain(provider_name="stub", dry_run=False)

    assert provider.requested_keywords == ["Zapatillas"]

    signals = client.table('demand_signals')._data
    assert signals, "the chain must produce signals"
    assert {s["category"] for s in signals} == {"Zapatillas"}
    assert all(s["category"] is not None for s in signals)

    # And the category join downstream is no longer starved.
    recommendations = client.table('recommendations')._data
    assert recommendations
    assert all(r["store_id"] == store_id for r in recommendations)


def test_ingest_window_makes_high_confidence_reachable(tmp_path, monkeypatch):
    """Finding 3: the threshold (>= 8 weekly windows) is the spec, so the
    ingest window is the side that had to move. `today 1-m` is ~4 windows
    and no production signal could ever be labelled `high`."""
    client = make_client(
        [{"category": "zapatillas", "store_id": "aaaaaaaa-0000-4000-8000-000000000001", "stock_qty": 5}]
    )
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps([]))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    provider = EchoProvider(weekly_series([20, 24, 29, 35, 42, 50, 60, 72]))
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_provider', lambda name: provider)

    run_chain(provider_name="stub", dry_run=False)

    assert INGEST_TIMEFRAME == "today 3-m"
    assert provider.requested_timeframe == INGEST_TIMEFRAME
    assert provider.requested_geo == "ES-MD"

    snapshots = client.table('trend_snapshots')._data
    assert all(s["timeframe"] == INGEST_TIMEFRAME for s in snapshots)

    signals = client.table('demand_signals')._data
    assert any(s["confidence"] == "high" for s in signals), (
        "the configured ingest window must be able to cover HIGH_MIN_WINDOWS"
    )


def test_every_table_is_read_from_the_right_schema(fake_client, monkeypatch):
    """The whole chain, one client: `products` from `public`, the three
    demand tables from `demand`. The client `run_chain` gets is built with
    `ClientOptions(schema="demand")`, so an unqualified `products` read
    resolves to `demand.products` -- a table `demand/data/schema.sql` never
    creates. Three call sites shipped with exactly that bug."""
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    accesses = []
    original_schema = client.schema

    def recording_schema(schema_name):
        view = original_schema(schema_name)
        original_table = view.table

        def recording_table(table_name):
            accesses.append((schema_name, table_name))
            return original_table(table_name)

        view.table = recording_table
        return view

    monkeypatch.setattr(client, "schema", recording_schema)

    run_chain(provider_name="fixture", dry_run=False)

    product_reads = [a for a in accesses if a[1] == "products"]
    # keywords.build_universe, run_chain's category map, recommend's join.
    assert len(product_reads) >= 3
    assert all(schema == "public" for schema, _ in product_reads)

    for schema, table in accesses:
        if table in ("trend_snapshots", "demand_signals", "recommendations"):
            assert schema == "demand"


def test_snapshot_ids_are_uuid5_of_the_natural_key(fake_client, monkeypatch):
    """The last uuid4 in the chain. The id is now a function of the same
    (keyword, geo, timeframe, captured_date) tuple
    `trend_snapshots_dedupe_idx` uses, so nothing has to read the table
    back to keep ids stable -- and the `snapshot_ids` provenance column of
    every derived signal stops churning with it."""
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    run_chain(provider_name="fixture", dry_run=False)

    snapshots = client.table('trend_snapshots')._data
    assert snapshots
    for snap in snapshots:
        expected = str(uuid.uuid5(
            uuid.uuid5(uuid.NAMESPACE_DNS, "demand.reachout"),
            "|".join(["trend_snapshot", snap["keyword"], snap["geo"],
                      snap["timeframe"], snap["captured_date"]]),
        ))
        assert snap["id"] == expected
        assert snap["id"] == snapshot_id(
            snap["keyword"], snap["geo"], snap["timeframe"], snap["captured_date"]
        )
        assert uuid.UUID(snap["id"]).version == 5

    # Provenance in the derived signals points at those same stable ids.
    known = {s["id"] for s in snapshots}
    signals = client.table('demand_signals')._data
    assert signals
    for sig in signals:
        assert sig["snapshot_ids"]
        assert set(sig["snapshot_ids"]) <= known


def test_snapshot_ids_survive_an_empty_table_with_no_round_trip(fake_client, monkeypatch):
    """Two runs against a client whose trend_snapshots reads always come
    back empty still produce the same ids: nothing is being copied forward
    from the previous run."""
    client, seed_file = fake_client
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    run_chain(provider_name="fixture", dry_run=False)
    first = sorted(r["id"] for r in client.table('trend_snapshots')._data)

    # Wipe the table between runs: with the old uuid4 + read-back-and-copy
    # scheme the second run would mint brand new ids here.
    client.schemas["demand"]["trend_snapshots"].clear()
    run_chain(provider_name="fixture", dry_run=False)

    assert sorted(r["id"] for r in client.table('trend_snapshots')._data) == first


class RecordingScheduler:
    """Stands in for AsyncIOScheduler so the cron gate can be asserted on."""

    instances = []

    def __init__(self, *args, **kwargs):
        self.jobs = []
        self.started = False
        self.stopped = False
        RecordingScheduler.instances.append(self)

    def add_job(self, func, trigger=None, **kwargs):
        self.jobs.append({"func": func, "trigger": trigger, "kwargs": kwargs})

    def start(self):
        self.started = True

    def shutdown(self, *args, **kwargs):
        self.stopped = True


@pytest.fixture
def recording_scheduler(monkeypatch):
    RecordingScheduler.instances = []
    monkeypatch.setattr(app, "AsyncIOScheduler", RecordingScheduler)
    return RecordingScheduler


def test_lifespan_starts_no_scheduler_without_the_env_gate(monkeypatch, recording_scheduler):
    monkeypatch.delenv("DEMAND_INGEST_CRON", raising=False)

    async def run_without_cron():
        async with app.lifespan(app.app):
            # Asserted INSIDE the context: after it exits a started
            # scheduler would have been shut down again and the difference
            # would be invisible.
            assert recording_scheduler.instances == []

    asyncio.run(run_without_cron())

    assert recording_scheduler.instances == []


def test_lifespan_starts_the_weekly_job_with_the_env_gate(monkeypatch, recording_scheduler):
    monkeypatch.setenv("DEMAND_INGEST_CRON", "1")

    async def run_with_cron():
        async with app.lifespan(app.app):
            assert len(recording_scheduler.instances) == 1
            scheduler = recording_scheduler.instances[0]
            assert scheduler.started is True
            assert len(scheduler.jobs) == 1
            job = scheduler.jobs[0]
            assert job["trigger"] == "cron"
            assert job["kwargs"] == {"day_of_week": "mon", "hour": 0, "minute": 0}
            assert scheduler.stopped is False

    asyncio.run(run_with_cron())

    # ...and the lifespan shuts it down again on the way out.
    assert recording_scheduler.instances[0].stopped is True


def test_lifespan_ignores_a_non_1_env_value(monkeypatch, recording_scheduler):
    monkeypatch.setenv("DEMAND_INGEST_CRON", "0")

    async def run_with_zero():
        async with app.lifespan(app.app):
            assert recording_scheduler.instances == []

    asyncio.run(run_with_zero())


# ---------------------------------------------------------------------------
# The discovery pass, end to end through `run_chain`.
#
# Ten RELATED_QUERIES searches per run is 4% of the monthly budget and cannot
# be batched, so every assertion below is really an assertion about money.
# ---------------------------------------------------------------------------

#: Last window per keyword, and what it makes each keyword worth:
#:   alfa      30.0, delta +200  -> best mover, selected first
#:   beta      20.0, delta +100  -> selected, and answers with nothing
#:   delta_kw  12.0, delta  +20  -> selected last
#:   gamma      0.14, delta +100 -> noise: same delta as `beta` off one day
#:                                  rounded to 1. Must NOT buy a search.
DISCOVERY_KEYWORDS = ["alfa", "beta", "delta_kw", "gamma"]


def _discovery_setup(tmp_path, monkeypatch, rising=None):
    client = make_client([{"category": "alfa",
                           "store_id": "aaaaaaaa-0000-4000-8000-000000000001",
                           "stock_qty": 5}])
    seed_file = tmp_path / "seed_keywords.json"
    seed_file.write_text(json.dumps(DISCOVERY_KEYWORDS))
    monkeypatch.setattr('demand.ingest.keywords.CONFIG_PATH', str(seed_file))
    monkeypatch.setattr(app, 'get_client', lambda: client)
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_client', lambda: client)

    flat = [10] * 7
    provider = DiscoveryProvider(
        series_by_keyword={
            "alfa": weekly_series(flat + [30]),
            "beta": weekly_series(flat + [20]),
            "delta_kw": weekly_series(flat + [12]),
            "gamma": weekly_series([0] * 7 + [0.14]),
        },
        rising_by_keyword=rising or {},
    )
    monkeypatch.setattr(demand.scripts.run_ingest, 'get_provider',
                        lambda name: provider)
    return client, provider


def test_discovery_spends_one_search_per_distinct_eligible_parent(tmp_path, monkeypatch):
    client, provider = _discovery_setup(tmp_path, monkeypatch)

    run_chain(provider_name="stub", dry_run=False)

    parents = [call[0] for call in provider.rising_calls]
    # (a) No keyword pays twice. Signals carry one row per keyword per WEEKLY
    # WINDOW, so ranking them raw let a single keyword take five of ten slots
    # -- and a repeat search upserts over the rows the first one wrote.
    assert len(parents) == len(set(parents))
    # (b) Exactly the eligible movers, best first, and the noise term excluded.
    assert parents == ["alfa", "beta", "delta_kw"]
    assert "gamma" not in parents
    # (c) A quiet week under-spends instead of padding back up to ten.
    assert len(parents) < demand.scripts.run_ingest.DISCOVERY_TOP_N


def test_discovery_asks_with_the_configured_window_and_property(tmp_path, monkeypatch):
    _, provider = _discovery_setup(tmp_path, monkeypatch)
    run_chain(provider_name="stub", dry_run=False)

    for _, geo, date, gprop in provider.rising_calls:
        assert geo == "ES-MD"
        assert date == demand.scripts.run_ingest.DISCOVERY_TIMEFRAME
        assert gprop == demand.scripts.run_ingest.DISCOVERY_GPROP


def test_discovery_rows_reach_the_database(tmp_path, monkeypatch):
    client, provider = _discovery_setup(tmp_path, monkeypatch, rising={
        "alfa": [
            {"query": "alfa barata", "growth_pct": 150.0, "is_breakout": False},
            {"query": "alfa premium", "growth_pct": None, "is_breakout": True},
        ],
        # `beta` answers with nothing. Sparse is the expected case for a
        # region-scoped Spanish term, not a failure.
        "delta_kw": [
            {"query": "delta grande", "growth_pct": 42.0, "is_breakout": False},
        ],
    })

    run_chain(provider_name="stub", dry_run=False)

    rows = client.table('rising_queries')._data
    assert len(rows) == 3
    assert {r["query"] for r in rows} == {
        "alfa barata", "alfa premium", "delta grande"}
    assert {r["parent_keyword"] for r in rows} == {"alfa", "delta_kw"}
    assert all(r["geo"] == "ES-MD" for r in rows)
    assert all(r["gprop"] == demand.scripts.run_ingest.DISCOVERY_GPROP
               for r in rows)
    assert all(uuid.UUID(r["id"]).version == 5 for r in rows)

    # The refusal survives the round trip. Google said "Breakout" and gave no
    # number, so no number is stored -- `extracted_value` is not promoted.
    breakout = next(r for r in rows if r["query"] == "alfa premium")
    assert breakout["is_breakout"] is True
    assert breakout["growth_pct"] is None

    # Both passes of the run share one timestamp.
    snapshot_at = client.table('trend_snapshots')._data[0]["captured_at"]
    assert all(r["captured_at"] == snapshot_at for r in rows)
    assert all(r["captured_date"] == snapshot_at[:10] for r in rows)


def test_discovery_is_idempotent_across_a_re_run(tmp_path, monkeypatch):
    """Re-running the same day upserts over the same ids, it does not double."""
    client, _ = _discovery_setup(tmp_path, monkeypatch, rising={
        "alfa": [{"query": "alfa barata", "growth_pct": 150.0,
                  "is_breakout": False}],
    })

    run_chain(provider_name="stub", dry_run=False)
    first = sorted(r["id"] for r in client.table('rising_queries')._data)
    run_chain(provider_name="stub", dry_run=False)

    assert sorted(r["id"] for r in client.table('rising_queries')._data) == first
    assert len(client.table('rising_queries')._data) == 1


def test_discovery_writes_nothing_in_dry_run(tmp_path, monkeypatch):
    client, provider = _discovery_setup(tmp_path, monkeypatch, rising={
        "alfa": [{"query": "alfa barata", "growth_pct": 150.0,
                  "is_breakout": False}],
    })

    run_chain(provider_name="stub", dry_run=True)

    assert client.table('rising_queries')._data == []
    # ...but the searches still happened. `--dry-run` skips DATABASE writes,
    # it does not make the run free. See the `--spend` guard in `main()`.
    assert provider.rising_calls != []


def test_discovery_survives_a_run_where_every_parent_is_empty(tmp_path, monkeypatch):
    client, provider = _discovery_setup(tmp_path, monkeypatch, rising={})
    run_chain(provider_name="stub", dry_run=False)
    assert provider.rising_calls != []
    assert client.table('rising_queries')._data == []
