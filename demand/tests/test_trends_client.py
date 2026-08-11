import os
import json
import pytest
import jsonschema
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
