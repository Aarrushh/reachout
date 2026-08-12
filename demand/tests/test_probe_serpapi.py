"""The probe is live-fire, and it is finished.

`python -m demand.scripts.probe_serpapi` used to spend 5 searches the moment
it was typed: no flag, no confirmation, no dry run. It printed "[Probe]
Spending 5 searches" and then spent them. That was defensible while the probe
was the thing standing between the plan and a guessed response shape; it is
pure footgun now that the gate is answered and the captures are committed --
and a re-run OVERWRITES `timeseries_web_5kw.json`, which
`test_serpapi_provider.py` asserts against.

Every test here is an assertion that no search happened.
"""

import json
import sys

import pytest

import demand.scripts.probe_serpapi as probe


@pytest.fixture
def isolated_probe(tmp_path, monkeypatch):
    """Point the probe at a scratch directory and disarm the transport.

    `load_dotenv` is stubbed too. The real one reads `reachout/.env` and would
    put the live `SERPAPI_API_KEY` back into `os.environ` for the rest of the
    session -- undoing the deletion `conftest.block_network` performs for
    exactly the reason this file exists.
    """
    monkeypatch.setattr(probe, "CAPTURE_DIR", tmp_path)
    monkeypatch.setattr(probe, "load_dotenv",
                        lambda *a, **kw: pytest.fail(
                            "loaded real credentials"))
    monkeypatch.setattr(probe, "fetch",
                        lambda *a, **kw: pytest.fail("spent a search"))
    monkeypatch.setenv("SERPAPI_API_KEY", "not-a-real-key")
    return tmp_path


def _run(monkeypatch, *args):
    monkeypatch.setattr(sys, "argv", ["probe_serpapi", *args])
    return probe.main()


def test_the_probe_spends_nothing_without_the_spend_flag(isolated_probe,
                                                         monkeypatch, capsys):
    assert _run(monkeypatch) == 0
    out = capsys.readouterr().out
    assert "--spend" in out
    assert list(isolated_probe.iterdir()) == []


def test_the_refusal_happens_before_the_key_is_ever_loaded(isolated_probe,
                                                           monkeypatch):
    # `load_dotenv` fails the test if called. Refusing first means a run that
    # was never authorised does not even open the credentials file.
    _run(monkeypatch)


def test_the_probe_says_what_it_would_cost(isolated_probe, monkeypatch,
                                            capsys):
    _run(monkeypatch)
    out = capsys.readouterr().out
    assert "5" in out
    assert "250" in out


def test_the_probe_refuses_to_clobber_a_committed_capture(isolated_probe,
                                                          monkeypatch, capsys):
    """The captures are test fixtures now, not scratch output."""
    (isolated_probe / "timeseries_web_5kw.json").write_text(
        json.dumps({"interest_over_time": {}}), encoding="utf-8")

    # `load_dotenv` and `fetch` both fail the test if reached: the refusal
    # must land before either.
    assert _run(monkeypatch, "--spend") == 1
    out = capsys.readouterr().out
    assert "--overwrite" in out
    # The existing capture is untouched.
    assert json.loads(
        (isolated_probe / "timeseries_web_5kw.json").read_text(
            encoding="utf-8")) == {"interest_over_time": {}}


def test_overwrite_plus_spend_is_what_actually_runs_it(isolated_probe,
                                                       monkeypatch):
    (isolated_probe / "timeseries_web_5kw.json").write_text("{}",
                                                            encoding="utf-8")
    calls = []
    monkeypatch.setattr(probe, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(probe, "build_params", lambda **kw: kw)
    monkeypatch.setattr(probe, "fetch",
                        lambda params: calls.append(params) or
                        {"search_metadata": {"id": "x"},
                         "search_parameters": {"api_key": "SECRET"},
                         "interest_over_time": {}})

    assert _run(monkeypatch, "--spend", "--overwrite") == 0
    assert len(calls) == 5


def test_the_probe_does_not_claim_a_remaining_balance_it_cannot_know(
        isolated_probe, monkeypatch, capsys):
    """It used to sign off "245 remain this month".

    That number was hardcoded, and it was already wrong -- 8 searches had been
    spent by then, not 5. A count the script cannot observe must not be
    printed as if it had been.
    """
    monkeypatch.setattr(probe, "load_dotenv", lambda *a, **kw: None)
    monkeypatch.setattr(probe, "build_params", lambda **kw: kw)
    monkeypatch.setattr(probe, "fetch", lambda params: {"related_queries": {}})

    _run(monkeypatch, "--spend", "--overwrite")

    assert "245" not in capsys.readouterr().out
