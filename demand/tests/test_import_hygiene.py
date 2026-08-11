"""Every module in this workspace must have exactly ONE importable name.

This is a spend guard, not a style rule.

`demand/tests`, `demand/ingest`, `demand/scripts` and `demand/api` all carry an
`__init__.py`. If `demand/` itself does not, pytest's default "prepend" import
mode walks up from a test file to the first parent WITHOUT an `__init__.py` --
`demand/` -- and puts that directory on `sys.path`. Every module underneath is
then reachable under two names, `ingest.trends_client` and
`demand.ingest.trends_client`, and Python loads those as two distinct module
objects holding two distinct `SerpApiProvider` classes.

`test_serpapi_provider.py` monkeypatches `fetch` on the `demand.ingest.*` copy.
Any code path that reached the `ingest.*` copy kept the real one. That is a
live, billed SerpApi call out of a 250/month budget, wearing the costume of a
mocked test. `demand/__init__.py` and the single-entry `sys.path` in
`conftest.py` are what close it; these tests keep them closed.
"""

import importlib
import sys

import pytest

#: Every bare name that resolved back when demand/ and its subdirectories were
#: on sys.path. None of them may resolve now.
BARE_NAMES = [
    "ingest.trends_client",
    "ingest.serpapi_client",
    "scripts.run_ingest",
    "api.app",
    "tests.fake_supa",
    "fake_supa",
    "trends_client",
]


@pytest.mark.parametrize("name", BARE_NAMES)
def test_module_is_not_reachable_by_a_bare_name(name):
    sys.modules.pop(name, None)
    try:
        importlib.import_module(name)
    except ImportError:
        return
    pytest.fail(
        f"{name!r} is importable. Something has put demand/ or one of its "
        f"subdirectories back on sys.path, so this module now has two names "
        f"and two module objects. Monkeypatching one leaves the other holding "
        f"the real, billed fetch. Import via the 'demand.' path only."
    )


def test_the_paid_client_is_a_single_module_object():
    import demand.ingest.trends_client as canonical

    assert sys.modules["demand.ingest.trends_client"] is canonical
    assert "ingest.trends_client" not in sys.modules


def test_the_only_workspace_path_entry_is_the_repo_root():
    import os

    offenders = []
    for entry in sys.path:
        if not entry:
            continue
        resolved = os.path.abspath(entry)
        base = os.path.basename(resolved)
        if base in {"demand", "ingest", "scripts", "api", "tests"}:
            offenders.append(resolved)
    assert offenders == [], (
        f"these sys.path entries re-open the double-import hole: {offenders}"
    )
