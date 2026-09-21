"""Cross-package pin (2026-09-21): the captured pre-market AMD board the frontend
tests render MUST be the shape the server serves — key for key, sentence for
sentence. The frontend composes none of the pre-market wording; if the
fixture carried a sentence the server never builds, the FE suite would be
green on a board that cannot exist.

Ajay 2026-09-21: "These chips are not working". The fixture is
frontend/src/pages/__fixtures__/chart_maps_amd_premarket_2026_09_21.json.
"""
import json
from pathlib import Path

import pytest

from chart_maps import board as B

_FIXTURE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "pages"
            / "__fixtures__" / "chart_maps_amd_premarket_2026_09_21.json")


@pytest.fixture(scope="module")
def fx():
    if not _FIXTURE.is_file():
        pytest.skip("frontend tree not present — the api image carries backend/ only")
    return json.loads(_FIXTURE.read_text())


def _blocks(fx):
    return {t["symbol"]: t["amd_flight"] for t in fx["tiles"]
            if isinstance(t.get("amd_flight"), dict)}


def _served_scope(fx):
    fs = fx["flight_scope"]
    return B._flight_scope(int(fs["counted"]), _blocks(fx), fx["flight_counts"],
                           fs.get("grades") or [])


def test_the_fixture_scope_is_the_served_scope_key_for_key(fx):
    served = _served_scope(fx)
    assert set(served) == set(fx["flight_scope"])
    assert served == fx["flight_scope"]


def test_the_fixture_reason_is_the_one_constant_verbatim(fx):
    fs = fx["flight_scope"]
    assert fs["reason"] == B.NO_SESSION_LOW_REASON
    assert fs["reason_line"] == ("%d of %d priced names have %s"
                                 % (fs["no_session_low"], fs["priced"],
                                    B.NO_SESSION_LOW_REASON))
    for f in _blocks(fx).values():
        if f.get("state") == B.AMD_FLIGHT_UNKNOWN:
            assert f.get("reason") == B.NO_SESSION_LOW_REASON


def test_the_fixture_cost_note_is_the_served_measured_note(fx):
    assert fx["flight_scope"]["note"] == B.FLIGHT_COST_NOTE
    for k in ("n_default", "s_default", "n_all", "s_all", "date"):
        assert str(B.FLIGHT_COST_MEASURED[k]) in B.FLIGHT_COST_NOTE or k == "date"


def test_every_fixture_flight_block_carries_only_served_keys(fx):
    served_keys = set(B._amd_flight({"base_lo": 52.13},
                                    {"last_trade_price": 53.15, "price": 0, "low": 0}))
    for sym, f in _blocks(fx).items():
        assert set(f) <= served_keys, sym
        if f.get("state") == B.AMD_FLIGHT_UNKNOWN:
            assert set(f) == served_keys, sym
        assert f.get("state") in B.AMD_FLIGHT_STATES + (B.AMD_FLIGHT_UNKNOWN,), sym
        assert f.get("confirmed") is False, sym


def test_the_fixture_counts_sum_to_priced_and_name_every_state(fx):
    fc = fx["flight_counts"]
    assert set(fc) == set(B.AMD_FLIGHT_STATES) | {B.AMD_FLIGHT_UNKNOWN}
    assert sum(fc.values()) == fx["flight_scope"]["priced"] == len(_blocks(fx))
    assert fc[B.AMD_FLIGHT_UNKNOWN] == fx["flight_scope"]["no_session_low"]
    assert fx["tape_session"] == "premarket"


def test_NEGATIVE_a_drifted_sentence_is_caught(fx):
    fs = dict(fx["flight_scope"])
    fs["reason"] = fs["reason"].replace("session low", "day low")
    assert fs["reason"] != B.NO_SESSION_LOW_REASON
    served = _served_scope(fx)
    assert served["reason"] != fs["reason"]


def test_NEGATIVE_the_server_builds_no_reason_when_nothing_is_unknown(fx):
    blocks = {s: dict(f, state="holding", reason=None, low_session="2026-09-21")
              for s, f in _blocks(fx).items()}
    counts = {st: 0 for st in B.AMD_FLIGHT_STATES}
    counts["holding"] = len(blocks); counts[B.AMD_FLIGHT_UNKNOWN] = 0
    served = B._flight_scope(len(blocks), blocks, counts, ["raided"])
    assert served["reason"] is None and served["reason_line"] is None
    assert served["unknowable"] == []
