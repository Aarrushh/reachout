import os
import json
import pytest
import jsonschema
from demand.ingest.serpapi_client import SerpApiError, SerpApiHTTPError
from demand.ingest.trends_client import get_provider, FixtureProvider

def load_schema(name):
    schema_path = os.path.join(os.path.dirname(__file__), "..", "shared", "schemas", name)
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)

def test_fixture_provider_round_trips():
    schema = load_schema("trend_snapshot.schema.json")
    series_schema = schema["properties"]["series"]
    region_schema = schema["properties"]["region_breakdown"]

    provider = get_provider("fixture")
    
    # Test interest_over_time
    series_res = provider.interest_over_time(["sneakers"], geo="ES-MD", timeframe="today 3-m")
    assert "sneakers" in series_res
    assert len(series_res["sneakers"]) == 3
    jsonschema.validate(instance=series_res["sneakers"], schema=series_schema)

    # Test interest_by_region
    region_res = provider.interest_by_region("sneakers", geo="ES-MD")
    assert len(region_res) == 2
    jsonschema.validate(instance=region_res, schema=region_schema)

def test_get_provider_factory():
    assert isinstance(get_provider("fixture"), FixtureProvider)

    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("invalid")


# ---------------------------------------------------------------------------
# Batching. Google compares at most five terms per request (verified live
# 2026-08-03: six -> 400 Bad Request). The universe is ~49 terms, so the
# provider must split the request AND put the pieces back on one scale.
# ---------------------------------------------------------------------------

from demand.ingest.trends_client import (  # noqa: E402
    _batch_keywords,
    _rescale_to_anchor,
)


def test_batches_never_exceed_the_google_cap():
    kws = [f"kw{i}" for i in range(49)]
    batches = _batch_keywords(kws, anchor=kws[0])

    assert batches, "49 keywords must produce at least one batch"
    for b in batches:
        # The literal 5 is deliberate. Asserting against
        # MAX_KEYWORDS_PER_REQUEST would only prove the code agrees with
        # itself: raising the constant to 50 leaves such a test green while
        # every live request goes back to 400. 5 is Google's number, not
        # ours, so the test states Google's number.
        assert len(b) <= 5, b
        assert b[0] == kws[0], "every batch carries the anchor first"

    # Every non-anchor keyword appears exactly once across all batches.
    seen = [k for b in batches for k in b[1:]]
    assert sorted(seen) == sorted(kws[1:])
    assert len(seen) == len(set(seen))


def test_batching_is_deterministic():
    kws = [f"kw{i}" for i in range(13)]
    assert _batch_keywords(kws, kws[0]) == _batch_keywords(kws, kws[0])


def test_rescale_puts_a_batch_on_the_reference_scale():
    # This batch's anchor averages 25; the reference batch's anchor averaged
    # 50. Everything in this batch is therefore reading half-scale and must
    # be doubled.
    batch = {
        "anchor": [{"date": "2026-01-01", "value": 20.0},
                   {"date": "2026-01-08", "value": 30.0}],
        "cerveza": [{"date": "2026-01-01", "value": 10.0},
                    {"date": "2026-01-08", "value": 40.0}],
    }
    out = _rescale_to_anchor(batch, anchor="anchor", reference_mean=50.0)

    assert "anchor" not in out, "the anchor is carried, not reported"
    assert [p["value"] for p in out["cerveza"]] == [20.0, 80.0]


def test_a_batch_whose_anchor_reads_zero_is_dropped_not_guessed():
    # No anchor signal means no scale factor. Emitting these values anyway
    # would be publishing a number on an unknown scale.
    batch = {
        "anchor": [{"date": "2026-01-01", "value": 0.0}],
        "cerveza": [{"date": "2026-01-01", "value": 90.0}],
    }
    assert _rescale_to_anchor(batch, anchor="anchor", reference_mean=50.0) == {}


from demand.ingest.trends_client import parse_rising_queries


def test_parse_rising_queries_extracts_percentage():
    payload = {"related_queries": {"rising": [
        {"query": "leche sin lactosa", "value": "+4,200%",
         "extracted_value": 4200},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche sin lactosa", "growth_pct": 4200.0,
         "is_breakout": False},
    ]


def test_parse_rising_queries_flags_breakout_without_inventing_a_number():
    # Google refuses to quantify Breakout. Assigning it 5000 -- or max+1, or
    # anything -- fabricates a figure the source declined to give. The same
    # refusal _rescale_to_anchor already makes when it drops an unreconcilable
    # batch rather than emit it on a guessed scale.
    payload = {"related_queries": {"rising": [
        {"query": "leche de avena", "value": "Breakout"},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche de avena", "growth_pct": None, "is_breakout": True},
    ]


def test_parse_rising_queries_ignores_the_top_list():
    # `top` is all-time popularity, not growth. Mixing it into a "rising"
    # panel would present steady bestsellers as new demand.
    payload = {"related_queries": {
        "rising": [{"query": "a", "value": "+10%", "extracted_value": 10}],
        "top": [{"query": "b", "value": "100", "extracted_value": 100}],
    }}
    assert [row["query"] for row in parse_rising_queries(payload)] == ["a"]


def test_parse_rising_queries_handles_empty_response():
    assert parse_rising_queries({"related_queries": {}}) == []
    assert parse_rising_queries({}) == []


def test_parse_rising_queries_skips_rows_without_a_query():
    payload = {"related_queries": {"rising": [
        {"value": "+10%", "extracted_value": 10},
        {"query": "válido", "value": "+20%", "extracted_value": 20},
    ]}}
    assert [row["query"] for row in parse_rising_queries(payload)] == ["válido"]


def test_fixture_provider_rising_queries_returns_empty_when_no_capture(tmp_path):
    from demand.ingest.trends_client import FixtureProvider

    provider = FixtureProvider(fixtures_dir=str(tmp_path))
    assert provider.rising_queries("café", geo="ES-MD", date="today 1-m",
                                   gprop="froogle") == []


def test_fixture_provider_rising_queries_replays_capture(tmp_path):
    import json
    from demand.ingest.trends_client import FixtureProvider

    captured = tmp_path / "captured"
    captured.mkdir()
    (captured / "related_queries_froogle_café.json").write_text(
        json.dumps({"related_queries": {"rising": [
            {"query": "café soluble", "value": "+150%", "extracted_value": 150},
        ]}}), encoding="utf-8",
    )

    provider = FixtureProvider(fixtures_dir=str(tmp_path))
    rows = provider.rising_queries("café", geo="ES-MD", date="today 1-m",
                                   gprop="froogle")
    assert rows == [{"query": "café soluble", "growth_pct": 150.0,
                     "is_breakout": False}]


def test_parse_rising_queries_against_the_real_capture():
    """The two synthetic tests above prove the branches. This one proves the
    branches match what Google actually sent on 2026-08-10 -- 24 rising rows
    for `café` in ES-MD, 16 of them Breakout."""
    import json
    import os

    from demand.ingest.trends_client import parse_rising_queries

    path = os.path.join(os.path.dirname(__file__), "fixtures", "trends",
                        "captured", "related_queries_web_café.json")
    with open(path, encoding="utf-8") as fh:
        rows = parse_rising_queries(json.load(fh))

    assert len(rows) == 24
    breakouts = [r for r in rows if r["is_breakout"]]
    assert len(breakouts) == 16
    # The honesty rule, asserted against real data: every Breakout row stores
    # no growth number, even though SerpApi supplied one (89800, 91000, ...).
    assert all(r["growth_pct"] is None for r in breakouts)
    assert all(r["growth_pct"] is not None for r in rows if not r["is_breakout"])


# ---------------------------------------------------------------------------
# The no-fabrication rule must not depend on one English string.
#
# `is_breakout` used to be `value == "Breakout"`. That is correct only while
# `hl="en"` reaches the parser. At `hl="es"` the identical rows read "Aumento
# puntual", the match fails, and `extracted_value` -- 91000 in the committed
# capture -- gets stored as `growth_pct = 91000.0`: a number Google explicitly
# refused to give, published on a shopkeeper's dashboard.
#
# `SerpApiProvider.rising_queries` pins `hl="en"` and a test pins that. But
# `parse_rising_queries` is a public function: `FixtureProvider` calls it on
# whatever JSON is on disk, `serpapi_client.build_params` defaults to
# `hl="es"`, and a re-capture or a Google label change routes around the pin.
# So the parser defends itself: a growth number is stored only when the label
# is a QUANTIFIED PERCENTAGE. Anything else is a refusal.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("label", [
    "Breakout",          # en
    "Aumento puntual",   # es -- what hl=es actually returns
    "Ausbruch",          # de
    "Percée",            # fr
    "急上昇",              # ja
    "",                  # label dropped entirely
    " %",                # digitless junk -- a % sign alone is not a number
    ",%",                # separators without digits, likewise
])
def test_breakout_is_detected_in_any_locale(label):
    payload = {"related_queries": {"rising": [
        {"query": "leche de avena", "value": label, "extracted_value": 91000},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche de avena", "growth_pct": None, "is_breakout": True},
    ]


def test_an_absent_value_is_a_refusal_not_a_number():
    # No label at all. `extracted_value` alone is not permission to quantify.
    payload = {"related_queries": {"rising": [
        {"query": "leche de avena", "extracted_value": 91000},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "leche de avena", "growth_pct": None, "is_breakout": True},
    ]


@pytest.mark.parametrize("label,expected", [
    ("+150%", 150.0),
    ("+4,200%", 4200.0),      # en thousands separator
    ("+4.200 %", 4200.0),     # es thousands separator, spaced sign
    ("+1 500 %", 1500.0),   # fr, non-breaking spaces
    ("150%", 150.0),
])
def test_a_quantified_percentage_is_still_read_in_any_locale(label, expected):
    payload = {"related_queries": {"rising": [
        {"query": "q", "value": label, "extracted_value": expected},
    ]}}
    rows = parse_rising_queries(payload)
    assert rows[0]["is_breakout"] is False
    assert rows[0]["growth_pct"] == expected


def test_a_quantified_label_with_no_extracted_value_stores_no_number():
    # The label says quantified, the payload supplies nothing to quantify
    # with. Inventing one from the string is the fabrication this avoids.
    payload = {"related_queries": {"rising": [
        {"query": "q", "value": "+150%"},
    ]}}
    assert parse_rising_queries(payload) == [
        {"query": "q", "growth_pct": None, "is_breakout": False},
    ]


# ---------------------------------------------------------------------------
# The anchor is the one slot cross-batch comparability depends on.
#
# Every batch carries the anchor so the batches can be rescaled onto a common
# level. `anchor = keywords[0]` made that an alphabetical accident:
# `build_universe` sorts, so the anchor was `abanico` -- measured mean 11.16 in
# ES-MD over 3 months, with probe companions at 0.57, 0.011 and 0.14. Google
# renormalises every request so its own peak term is 100 and rounds to
# integers, so batching `abanico` against `café`, `cerveza` or `pan` rounds
# `abanico` to 0 across the window. `_rescale_to_anchor` then correctly refuses
# to scale -- and the caller used to swallow that silently, storing four
# keywords with an empty series for one paid search.
# ---------------------------------------------------------------------------

from demand.ingest.trends_client import pick_anchor  # noqa: E402


def test_pick_anchor_prefers_measured_volume_over_the_alphabet():
    signals = [
        {"keyword": "abanico", "interest_avg": 11.16,
         "window_start": "2026-08-03"},
        {"keyword": "café", "interest_avg": 78.0,
         "window_start": "2026-08-03"},
    ]
    assert pick_anchor(signals, ["abanico", "café", "pan"]) == "café"


def test_pick_anchor_falls_back_to_alphabetical_on_a_cold_start():
    # No previous run. This is the old behaviour, and it is the right
    # fallback: it is what the run would have done anyway.
    assert pick_anchor([], ["abanico", "café"]) == "abanico"


def test_pick_anchor_ignores_signals_no_longer_in_the_universe():
    # A keyword can leave the universe between runs. Anchoring on a term that
    # is not being requested would put nothing in the batches at all.
    signals = [{"keyword": "descatalogado", "interest_avg": 99.0,
                "window_start": "2026-08-03"}]
    assert pick_anchor(signals, ["abanico", "café"]) == "abanico"


def test_pick_anchor_reads_the_newest_window():
    signals = [
        {"keyword": "café", "interest_avg": 90.0,
         "window_start": "2026-07-27"},
        {"keyword": "pan", "interest_avg": 20.0,
         "window_start": "2026-08-03"},
    ]
    assert pick_anchor(signals, ["café", "pan"]) == "pan"


def test_pick_anchor_breaks_ties_deterministically():
    # Two runs over the same signals must pick the same anchor, or the two
    # runs are not comparable to each other either.
    signals = [
        {"keyword": "pan", "interest_avg": 50.0, "window_start": "2026-08-03"},
        {"keyword": "café", "interest_avg": 50.0, "window_start": "2026-08-03"},
    ]
    assert pick_anchor(signals, ["pan", "café"]) == "café"
    assert pick_anchor(list(reversed(signals)), ["pan", "café"]) == "café"


def test_pick_anchor_tolerates_a_signal_with_no_measurement():
    signals = [
        {"keyword": "café", "interest_avg": None, "window_start": "2026-08-03"},
        {"keyword": "pan", "interest_avg": 20.0, "window_start": "2026-08-03"},
    ]
    assert pick_anchor(signals, ["café", "pan"]) == "pan"


def test_pick_anchor_handles_an_empty_universe():
    assert pick_anchor([], []) == ""


def _stub_transport(monkeypatch, anchor_reads_zero_in_second_batch=True):
    """Two batches of a 9-keyword universe, driven through the real provider."""
    import demand.ingest.trends_client as tc

    monkeypatch.setattr(tc, "build_params", lambda **kw: kw["q"])

    def fake_fetch(batch):
        first_batch = batch[1] == "kw1"
        if first_batch or not anchor_reads_zero_in_second_batch:
            anchor_value = 50
        else:
            anchor_value = 0
        values = [{"query": kw,
                   "extracted_value": anchor_value if kw == "ancla" else 70}
                  for kw in batch]
        return {"interest_over_time": {"timeline_data": [
            {"timestamp": "1783296000", "values": values},
        ]}}

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    return tc


def test_a_dropped_batch_is_announced(monkeypatch, capsys):
    tc = _stub_transport(monkeypatch)
    keywords = ["ancla"] + [f"kw{i}" for i in range(1, 9)]

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        keywords, anchor="ancla")

    out = capsys.readouterr().out
    assert "dropped" in out
    assert "ancla" in out
    # The four keywords in the dropped batch are named, so the operator can
    # tell "no data" apart from "we paid for this and got nothing".
    for kw in ("kw5", "kw6", "kw7", "kw8"):
        assert kw in out
        assert result[kw] == []
    # The healthy batch is untouched.
    assert result["kw1"] != []


def test_a_healthy_batch_is_not_announced(monkeypatch, capsys):
    tc = _stub_transport(monkeypatch, anchor_reads_zero_in_second_batch=False)
    keywords = ["ancla"] + [f"kw{i}" for i in range(1, 9)]

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        keywords, anchor="ancla")

    assert "dropped" not in capsys.readouterr().out
    assert result["kw5"] != []


def test_an_anchor_outside_the_universe_falls_back_to_the_first_keyword(
        monkeypatch):
    tc = _stub_transport(monkeypatch, anchor_reads_zero_in_second_batch=False)
    keywords = ["ancla"] + [f"kw{i}" for i in range(1, 9)]

    # "no-such-term" cannot anchor anything; the provider must not build
    # batches around a keyword it is not requesting.
    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        keywords, anchor="no-such-term")

    assert result["kw1"] != []


# ---------------------------------------------------------------------------
# Error tolerance in the batch loop.
#
# The universe is 12 batches. An unguarded loop means a 502 on batch 9 throws
# out of `interest_over_time` before `store_snapshots` is ever reached, so 9
# already-billed searches -- 4% of the month -- produce zero rows and there is
# no way to resume. The codebase learned this exact lesson once already, in
# `run_ingest.py`'s `interest_by_region` guard, and wrote the reasoning down.
# ---------------------------------------------------------------------------


def _failing_transport(monkeypatch, failures):
    """`failures` maps batch index -> exception to raise (once per attempt).

    Values may be a single exception or a list consumed one per attempt, which
    is how a retry that succeeds on the second try gets expressed.
    """
    import demand.ingest.trends_client as tc

    monkeypatch.setattr(tc, "build_params", lambda **kw: kw["q"])
    monkeypatch.setattr(tc, "sleep", lambda seconds: None)

    calls = []

    def fake_fetch(batch):
        index = (int(batch[1][2:]) - 1) // tc.KEYWORDS_PER_BATCH
        calls.append(index)
        planned = failures.get(index)
        if isinstance(planned, list):
            if planned:
                raise planned.pop(0)
        elif planned is not None:
            raise planned
        values = [{"query": kw,
                   "extracted_value": 50 if kw == "ancla" else 70}
                  for kw in batch]
        return {"interest_over_time": {"timeline_data": [
            {"timestamp": "1783296000", "values": values},
        ]}}

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    return tc, calls


UNIVERSE = ["ancla"] + [f"kw{i}" for i in range(1, 13)]  # anchor + 12 = 3 batches


def test_one_failed_batch_does_not_forfeit_the_searches_already_spent(
        monkeypatch, capsys):
    tc, calls = _failing_transport(
        monkeypatch, {1: SerpApiHTTPError(502)})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    # Every batch was attempted -- the loop did not unwind on the first error.
    assert set(calls) == {0, 1, 2}
    # The batches that answered still carry their data all the way out.
    assert result["kw1"] != []
    assert result["kw12"] != []
    # ...and only the failed batch's keywords are empty.
    assert result["kw5"] == []
    out = capsys.readouterr().out
    assert "1 of 3 batches failed" in out
    assert "502" in out


def test_a_failed_first_batch_does_not_take_the_reference_scale_with_it(
        monkeypatch):
    """Batch 0 sets `reference_mean`. Losing it must not void the whole run.

    With the reference pinned to batch 0 by index, a 502 there left
    `reference_mean` at 0.0, `_rescale_to_anchor` correctly refused to scale
    against nothing, and all 11 remaining paid searches were discarded on top
    of the one that failed.
    """
    tc, calls = _failing_transport(monkeypatch, {0: SerpApiHTTPError(503)})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert set(calls) == {0, 1, 2}
    assert result["kw5"] != []
    assert result["kw12"] != []


def test_a_transient_failure_is_retried_before_the_batch_is_given_up(
        monkeypatch):
    tc, calls = _failing_transport(
        monkeypatch, {1: [SerpApiHTTPError(502)]})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    # Batch 1 was attempted twice and answered on the retry.
    assert calls.count(1) == 2
    assert result["kw5"] != []


def test_a_batch_is_not_retried_forever(monkeypatch):
    tc, calls = _failing_transport(monkeypatch, {1: SerpApiHTTPError(502)})

    tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert calls.count(1) == 1 + tc.BATCH_RETRIES


def test_a_429_stops_the_run_instead_of_retrying_into_an_empty_budget(
        monkeypatch, capsys):
    """429 is "the 250/month budget is gone", not "try again in a second".

    Retrying it -- which is what a generic transient-error backoff would do --
    hammers an account that has already said no, and every remaining batch
    would answer the same way. Stop, and say why, keeping whatever the
    earlier batches paid for.
    """
    tc, calls = _failing_transport(monkeypatch, {1: SerpApiHTTPError(429)})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert calls.count(1) == 1          # not retried
    assert 2 not in calls               # and batch 2 never attempted
    assert result["kw1"] != []          # batch 0's search is still banked
    assert "budget" in capsys.readouterr().out.lower()


def test_a_401_stops_the_run_too(monkeypatch):
    """A rejected key is not transient and is not per-batch."""
    tc, calls = _failing_transport(monkeypatch, {1: SerpApiHTTPError(401)})

    tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert calls.count(1) == 1
    assert 2 not in calls


def test_an_empty_answer_for_a_batch_is_data_not_a_failure(monkeypatch):
    """HTTP 200 with an `error` field means Google had nothing. Keep going."""
    tc, calls = _failing_transport(
        monkeypatch, {1: SerpApiError("Google hasn't returned any results")})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert calls.count(1) == 1          # a refusal is not retried
    assert set(calls) == {0, 1, 2}
    assert result["kw5"] == []
    assert result["kw12"] != []


def test_a_fully_healthy_run_says_nothing_about_failures(monkeypatch, capsys):
    tc, _ = _failing_transport(monkeypatch, {})
    tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")
    assert "failed" not in capsys.readouterr().out


# ---------------------------------------------------------------------------
# The reference scale itself.
#
# "The anchor came back" and "the anchor was measured" are different facts.
# Google renormalises every request so its own peak term is 100 and rounds to
# integers, so a low-volume anchor next to a high-volume staple comes back as a
# full series of ZEROS -- `parse_timeseries` keeps every one of them, because
# `extracted_value` is `0`, not `None`. A non-empty `anchor_points` whose mean
# is 0.0 is therefore a routine answer, not a freak one.
#
# Accepting that batch as the reference is the worst of the three possible
# outcomes: it publishes that batch's keywords raw, leaves `reference_mean` at
# 0.0 so the NEXT batch becomes a second reference on its own normalisation,
# and never prints the drop announcement. Two incomparable scales then get
# ranked against each other by `compute_signals` with nothing saying so.
# ---------------------------------------------------------------------------


def _anchor_transport(monkeypatch, anchor_by_batch):
    """`anchor_by_batch` maps batch index -> the anchor's value in that batch.

    Non-anchor keywords always read 70, so a batch that gets published raw is
    trivially distinguishable from one that got rescaled.
    """
    import demand.ingest.trends_client as tc

    monkeypatch.setattr(tc, "build_params", lambda **kw: kw["q"])

    def fake_fetch(batch):
        index = (int(batch[1][2:]) - 1) // tc.KEYWORDS_PER_BATCH
        anchor_value = anchor_by_batch.get(index, 50)
        values = [{"query": kw,
                   "extracted_value": anchor_value if kw == "ancla" else 70}
                  for kw in batch]
        return {"interest_over_time": {"timeline_data": [
            {"timestamp": "1783296000", "values": values},
        ]}}

    monkeypatch.setattr(tc, "fetch", fake_fetch)
    return tc


def test_a_zero_reading_anchor_never_becomes_the_reference_scale(
        monkeypatch, capsys):
    """Batch 0 measured the anchor at 0 for every point in the window.

    It has no scale to offer, so it must take the existing drop-and-announce
    path -- not set `reference_mean = 0.0` and publish its four keywords on
    Google's per-request normalisation as though they were comparable.
    """
    tc = _anchor_transport(monkeypatch, {0: 0})
    keywords = ["ancla"] + [f"kw{i}" for i in range(1, 9)]

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        keywords, anchor="ancla")

    for kw in ("kw1", "kw2", "kw3", "kw4"):
        assert result[kw] == []
    out = capsys.readouterr().out
    assert "dropped" in out
    assert "kw1" in out
    # Batch 1 did measure the anchor, so it sets the reference and survives.
    assert result["kw5"] != []


def test_a_run_whose_anchor_never_reads_publishes_nothing_rather_than_raw(
        monkeypatch, capsys):
    """Every batch reads the anchor at 0: there is no common scale anywhere.

    Honest-but-empty is the correct outcome. Publishing both batches raw --
    each on its own request's normalisation -- hands `compute_signals` two
    universes to rank against each other and calls the result a rank.
    """
    tc = _anchor_transport(monkeypatch, {0: 0, 1: 0})
    keywords = ["ancla"] + [f"kw{i}" for i in range(1, 9)]

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        keywords, anchor="ancla")

    assert all(result[kw] == [] for kw in keywords if kw != "ancla")
    # Both losses are announced. Silence here is indistinguishable from
    # Google simply having had no data.
    assert capsys.readouterr().out.count("dropped") == 2


def test_the_reference_scale_survives_a_zero_reading_first_batch(monkeypatch):
    """The reference is the first batch that MEASURED the anchor, still.

    Skipping batch 0 for reading zero must not also skip batch 1 for it, which
    is what pinning the reference back to `i == 0` would do.
    """
    tc = _anchor_transport(monkeypatch, {0: 0, 1: 50, 2: 25})
    universe = ["ancla"] + [f"kw{i}" for i in range(1, 13)]

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        universe, anchor="ancla")

    assert result["kw1"] == []
    # Batch 1 is the reference: published on its own scale, 70 as measured.
    assert [p["value"] for p in result["kw5"]] == [70.0]
    # Batch 2 read the anchor at half batch 1's level, so its values double.
    assert [p["value"] for p in result["kw9"]] == [140.0]


# ---------------------------------------------------------------------------
# Exception tolerance, by category rather than by name.
#
# `_fetch_batch` named exactly two exception types. `fetch` can fail as
# neither: an HTTP 200 carrying an HTML maintenance page raises
# `json.JSONDecodeError` out of `response.json()`, straight through the batch
# loop and out of `run_chain` before `store_snapshots`, forfeiting every search
# the earlier batches already paid for. Naming types is a denylist, and a
# denylist here goes stale in the direction that costs money.
# ---------------------------------------------------------------------------


def test_a_non_json_response_body_only_costs_the_batch_that_hit_it(
        monkeypatch, capsys):
    import demand.ingest.serpapi_client as sc

    tc, calls = _failing_transport(
        monkeypatch, {1: sc.SerpApiMalformedResponseError(200)})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert set(calls) == {0, 1, 2}
    assert result["kw1"] != []
    assert result["kw12"] != []
    assert result["kw5"] == []
    out = capsys.readouterr().out
    assert "1 of 3 batches failed" in out


def test_an_unnamed_exception_still_only_costs_one_batch(monkeypatch, capsys):
    """The catch-all clause. Whatever it is, it is one batch, not the run."""
    tc, calls = _failing_transport(monkeypatch, {1: RuntimeError("boom")})

    result = tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert set(calls) == {0, 1, 2}
    assert result["kw1"] != []
    assert result["kw12"] != []
    assert result["kw5"] == []
    out = capsys.readouterr().out
    # The TYPE is reported, never `str(exc)`. An arbitrary exception's message
    # is arbitrary text of unknown provenance going to stdout, and the one
    # thing this codebase will not put there is anything derived from the
    # request -- SerpApi takes the API key as a query parameter.
    assert "RuntimeError" in out
    assert "boom" not in out


def test_an_unnamed_exception_is_not_retried_at_full_price(monkeypatch):
    """One unexplained failure, one search. Not three."""
    tc, calls = _failing_transport(monkeypatch, {1: RuntimeError("boom")})

    tc.SerpApiProvider(api_key="KEY").interest_over_time(
        UNIVERSE, anchor="ancla")

    assert calls.count(1) == 1
