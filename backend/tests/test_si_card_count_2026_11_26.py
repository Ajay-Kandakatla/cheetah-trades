"""🩳 SEPA card chip share count + the client.py divisions (floatguard 2026-11-26, spec §3.1 client sites, §3.8).

`short_interest_for` (GET /short/{sym}/interest, RealtimeChips.tsx) gains `shares_source` / `shares_asof`, always.
`SI_CARD_COUNT_FROM = "massive_ref"` (built default) = today's numbers to the digit; `resolver` (built, OFF — his call
#9) takes the 🩳 resolver block's dated count ONLY for the same settlement. Pure — every fetcher is monkeypatched.
"""
from __future__ import annotations

import ast
import inspect

import pytest

from short_interest import client
from short_interest import read as SR

OLD_KEYS = {"symbol", "settlement_date", "short_interest", "avg_daily_volume", "days_to_cover",
            "shares_outstanding", "pct_of_shares", "prev_settlement_date", "si_change_pct", "squeeze"}
NEW_KEYS = {"shares_source", "shares_asof"}

LATEST = "2026-11-13"
PRIOR = "2026-10-31"

# (si, prev_si, shares, dtc) — ints, a zero count, a missing count, a float count, a missing / zero share count.
SWEEP = [
    (1000, 800, 10000, 2.0),
    (0, 800, 10000, 2.0),
    (None, 800, 10000, 6.0),
    (1234.5, 999, 7, 1.0),
    (1000, None, None, 6.0),
    (1000, 0, 0, 1.0),
    (195353, 4766804, 2388212, 0.1),
    (7, 3, 3, 9.0),
]


def _rows(si, prev_si, dtc, latest=LATEST):
    return [{"settlement_date": latest, "short_interest": si, "avg_daily_volume": 500, "days_to_cover": dtc},
            {"settlement_date": PRIOR, "short_interest": prev_si, "avg_daily_volume": 400, "days_to_cover": dtc}]


def _today(si, prev_si, shares, dtc, latest=LATEST):
    """The pre-floatguard body of short_interest_for, verbatim, as the oracle."""
    pct = (si / shares * 100) if (si and shares) else None
    chg = ((si - prev_si) / prev_si * 100) if (si and prev_si) else None
    return {"symbol": "FOO", "settlement_date": latest, "short_interest": si, "avg_daily_volume": 500,
            "days_to_cover": dtc, "shares_outstanding": shares,
            "pct_of_shares": round(pct, 2) if pct is not None else None, "prev_settlement_date": PRIOR,
            "si_change_pct": round(chg, 1) if chg is not None else None,
            "squeeze": client._squeeze_signal(pct, dtc)}


def _boom(*a, **k):
    raise AssertionError("must not be called")


@pytest.fixture
def feed(monkeypatch):
    def set_(si, prev_si, shares, dtc, latest=LATEST):
        monkeypatch.setattr(client, "_fetch_short_interest_rows",
                            lambda s, limit=4: _rows(si, prev_si, dtc, latest))
        monkeypatch.setattr(client, "_shares_outstanding", lambda s: shares)
    return set_


def _block(settlement=LATEST, so=2388212, ps=8.18, asof="2026-11-20", src="SEC cover dei (10-Q)"):
    return {"symbol": "FOO", "settlement_date": settlement, "shares_outstanding": so, "pct_of_shares_out": ps,
            "shares_asof": asof, "shares_source": src}


# ═════════════════════════════════════════════ constants
def test_built_default_is_massive_ref_and_both_modes_are_listed():
    assert client.SI_CARD_COUNT_FROM == "massive_ref"
    assert client.SI_CARD_COUNT_MODES == ("massive_ref", "resolver")
    assert "no as-of date" in client.MASSIVE_REF_SHARES_SOURCE


# ═════════════════════════════════════════════ massive_ref (built default) = today to the digit
@pytest.mark.parametrize("si,prev_si,shares,dtc", SWEEP)
def test_massive_ref_is_todays_numbers_to_the_digit_plus_two_keys(feed, monkeypatch, si, prev_si, shares, dtc):
    feed(si, prev_si, shares, dtc)
    monkeypatch.setattr(SR, "si_map", _boom)          # the built default never reads the resolver
    d = client.short_interest_for("foo")
    assert set(d) == OLD_KEYS | NEW_KEYS
    assert {k: d[k] for k in OLD_KEYS} == _today(si, prev_si, shares, dtc)
    assert d["shares_source"] == client.MASSIVE_REF_SHARES_SOURCE and d["shares_asof"] is None


def test_massive_ref_zero_count_is_None_not_zero(feed):
    feed(0, 800, 10000, 2.0)
    d = client.short_interest_for("FOO")
    assert d["pct_of_shares"] is None and d["squeeze"] == "low"


def test_massive_ref_missing_count_is_None(feed):
    feed(None, 800, 10000, 6.0)
    d = client.short_interest_for("FOO")
    assert d["pct_of_shares"] is None and d["squeeze"] == "elevated"


def test_NEGATIVE_no_record_is_still_None(monkeypatch):
    monkeypatch.setattr(client, "_fetch_short_interest_rows", lambda s, limit=4: [])
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")
    monkeypatch.setattr(SR, "si_map", _boom)
    assert client.short_interest_for("FOO") is None


# ═════════════════════════════════════════════ resolver (built, OFF)
def test_resolver_uses_the_blocks_dated_count_on_the_same_settlement(feed, monkeypatch):
    feed(195353, 4766804, None, 0.1)
    monkeypatch.setattr(client, "_shares_outstanding", _boom)     # no Massive reference call when the block serves
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")
    seen = []
    monkeypatch.setattr(SR, "si_map", lambda syms, *a, **k: seen.append(list(syms)) or {"FOO": _block()})
    d = client.short_interest_for("foo")
    assert seen == [["foo"]]
    assert set(d) == OLD_KEYS | NEW_KEYS
    assert d["shares_outstanding"] == 2388212 and d["pct_of_shares"] == 8.18
    assert d["shares_source"] == "SEC cover dei (10-Q)" and d["shares_asof"] == "2026-11-20"
    assert d["squeeze"] == client._squeeze_signal(8.18, 0.1)
    # ...and every field that is not the share count stays today's.
    base = _today(195353, 4766804, None, 0.1)
    for k in ("settlement_date", "short_interest", "avg_daily_volume", "days_to_cover",
              "prev_settlement_date", "si_change_pct", "symbol"):
        assert d[k] == base[k], k


def test_resolver_squeeze_reads_the_blocks_percent(feed, monkeypatch):
    feed(1000, 800, 10**9, 1.0)                       # Massive's count would read 0.0001% -> "low"
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")
    monkeypatch.setattr(SR, "si_map", lambda syms, *a, **k: {"FOO": _block(ps=25.0)})
    assert client.short_interest_for("FOO")["squeeze"] == "high"


@pytest.mark.parametrize("answer", [
    {"FOO": _block(settlement=PRIOR)},                # another settlement
    {"FOO": _block(settlement=None)},                 # no settlement on the block
    {},                                               # no block
    {"BAR": _block()},                                # a block for another name
    {"FOO": _block(ps=None)},                         # a block with no % of shares outstanding
    {"FOO": "not a dict"},
    None,
])
@pytest.mark.parametrize("si,prev_si,shares,dtc", SWEEP[:4])
def test_NEGATIVE_resolver_falls_back_to_todays_numbers(feed, monkeypatch, answer, si, prev_si, shares, dtc):
    feed(si, prev_si, shares, dtc)
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")
    monkeypatch.setattr(SR, "si_map", lambda syms, *a, **k: answer)
    d = client.short_interest_for("FOO")
    assert {k: d[k] for k in OLD_KEYS} == _today(si, prev_si, shares, dtc)
    assert d["shares_source"] == client.MASSIVE_REF_SHARES_SOURCE and d["shares_asof"] is None


def test_NEGATIVE_resolver_a_raising_si_map_is_todays_numbers(feed, monkeypatch):
    feed(1000, 800, 10000, 2.0)
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")

    def raise_(*a, **k):
        raise RuntimeError("mongo down")

    monkeypatch.setattr(SR, "si_map", raise_)
    d = client.short_interest_for("FOO")
    assert {k: d[k] for k in OLD_KEYS} == _today(1000, 800, 10000, 2.0)
    assert d["shares_source"] == client.MASSIVE_REF_SHARES_SOURCE


def test_NEGATIVE_resolver_with_no_settlement_on_the_row_never_reads(feed, monkeypatch):
    feed(1000, 800, 10000, 2.0, latest=None)
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", "resolver")
    monkeypatch.setattr(SR, "si_map", _boom)
    d = client.short_interest_for("FOO")
    assert {k: d[k] for k in OLD_KEYS} == _today(1000, 800, 10000, 2.0, latest=None)


@pytest.mark.parametrize("word", ["RESOLVER", "on", "", "off", None, "Resolver "])
def test_NEGATIVE_an_unknown_mode_word_is_massive_ref(feed, monkeypatch, word):
    feed(1000, 800, 10000, 2.0)
    monkeypatch.setattr(client, "SI_CARD_COUNT_FROM", word)
    monkeypatch.setattr(SR, "si_map", _boom)
    d = client.short_interest_for("FOO")
    assert {k: d[k] for k in OLD_KEYS} == _today(1000, 800, 10000, 2.0)
    assert d["shares_source"] == client.MASSIVE_REF_SHARES_SOURCE and d["shares_asof"] is None


# ═════════════════════════════════════════════ _build_doc stores the same % as before
@pytest.mark.parametrize("si", [0, 1, 1000, 195353, 111323398])
@pytest.mark.parametrize("fl,so", [(None, None), (10000, 20000), (531210, 2388212), (0, 7), (3, None), (None, 1)])
def test_build_doc_stores_the_same_pct_of_float_and_shares_as_before(si, fl, so):
    doc = client._build_doc("foo", {"short_interest": si, "days_to_cover": 1.5, "avg_daily_volume": 10},
                            {"short_interest": 800},
                            {"float_shares": fl, "shares_outstanding": so, "as_of_iso": "2026-11-20"},
                            latest=LATEST, prior=PRIOR, fetched_at=1.0)
    fl_ = fl if fl else None
    so_ = so if so else None
    assert doc["pct_of_float"] == (round(si / fl_ * 100.0, 2) if fl_ else None)
    assert doc["pct_of_shares"] == (round(si / so_ * 100.0, 2) if so_ else None)
    assert doc["si_change_pct"] == round((si - 800) / 800 * 100.0, 1)
    assert doc["squeeze"] == client._squeeze_signal(doc["pct_of_shares"], 1.5)


def test_NEGATIVE_build_doc_with_no_denominators_stores_no_percent():
    doc = client._build_doc("FOO", {"short_interest": 5}, None, {}, latest=LATEST, prior=None, fetched_at=1.0)
    assert doc["shares_source"] is None and doc["shares_asof"] is None
    assert doc["pct_of_float"] is None and doc["pct_of_shares"] is None and doc["si_change_pct"] is None


# ═════════════════════════════════════════════ the change-% lines are NOT routed through pct_of
def _assign_src(fn, target: str) -> list:
    tree = ast.parse(inspect.getsource(fn).lstrip())
    return [ast.unparse(n.value) for n in ast.walk(tree)
            if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == target for t in n.targets)]


@pytest.mark.parametrize("fn", [client.short_interest_for, client._build_doc])
def test_the_change_percent_lines_are_not_routed_through_pct_of(fn):
    (src,) = _assign_src(fn, "chg")
    assert "pct_of" not in src
    assert "prev_si" in src and "100" in src             # still the change across settlements, own division


@pytest.mark.parametrize("si,prev_si", [(1000, 800), (800, 1000), (5, 0), (0, 5), (None, 5), (5, None)])
def test_NEGATIVE_change_percent_is_todays_to_the_digit(feed, si, prev_si):
    feed(si, prev_si, 10000, 2.0)
    assert client.short_interest_for("FOO")["si_change_pct"] == _today(si, prev_si, 10000, 2.0)["si_change_pct"]


def test_NEGATIVE_the_warm_doc_stores_no_new_key(monkeypatch):
    """The per-name warm writes an explicit key list: the two served keys never reach `short_interest_latest`."""
    src = inspect.getsource(client.warm_short_interest)
    assert '"shares_source"' not in src and '"shares_asof"' not in src


# ═════════════════════════════════════════════ the three client.py % sites go through read.pct_of (spec §3.1)
def _pct_calls(fn) -> int:
    tree = ast.parse(inspect.getsource(fn).lstrip())
    return sum(1 for n in ast.walk(tree) if isinstance(n, ast.Call)
               and ((isinstance(n.func, ast.Attribute) and n.func.attr == "pct_of")
                    or (isinstance(n.func, ast.Name) and n.func.id == "pct_of")))


def test_client_calls_pct_of_exactly_three_times():
    tree = ast.parse(inspect.getsource(client))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "pct_of"]
    assert len(calls) == 3
    assert _pct_calls(client.short_interest_for) == 1 and _pct_calls(client._build_doc) == 2


@pytest.mark.parametrize("fn,target", [(client.short_interest_for, "pct"), (client._build_doc, "pf"),
                                       (client._build_doc, "ps")])
def test_percent_of_shares_sites_hold_no_division_of_their_own(fn, target):
    (src,) = _assign_src(fn, target)
    assert "SR.pct_of(" in src
    node = ast.parse(src)
    assert not any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div) for n in ast.walk(node))


def test_short_interest_for_and_build_doc_each_reach_pct_of(feed, monkeypatch):
    seen = []
    real = SR.pct_of

    def spy(count, shares, digits=2):
        seen.append((count, shares, digits))
        return real(count, shares, digits)

    monkeypatch.setattr(SR, "pct_of", spy)
    feed(1000, 800, 10000, 2.0)
    assert client.short_interest_for("FOO")["pct_of_shares"] == 10.0
    assert seen == [(1000, 10000, None)]
    seen.clear()
    doc = client._build_doc("FOO", {"short_interest": 1000}, None,
                            {"float_shares": 4000, "shares_outstanding": 10000}, latest=LATEST, prior=None,
                            fetched_at=1.0)
    assert (doc["pct_of_float"], doc["pct_of_shares"]) == (25.0, 10.0)
    assert seen == [(1000, 4000, 2), (1000, 10000, 2)]


@pytest.mark.parametrize("si,shares", [(0, 10000), (None, 10000), (1000, None), (1000, 0)])
def test_NEGATIVE_short_interest_for_guard_stays_before_pct_of(feed, monkeypatch, si, shares):
    monkeypatch.setattr(SR, "pct_of", _boom)
    feed(si, 800, shares, 2.0)
    d = client.short_interest_for("FOO")
    assert d["pct_of_shares"] is None and d["squeeze"] == _today(si, 800, shares, 2.0)["squeeze"]


def test_NEGATIVE_build_doc_guard_stays_before_pct_of(monkeypatch):
    monkeypatch.setattr(SR, "pct_of", _boom)
    doc = client._build_doc("FOO", {"short_interest": 9}, None, {"float_shares": 0, "shares_outstanding": None},
                            latest=LATEST, prior=None, fetched_at=1.0)
    assert doc["pct_of_float"] is None and doc["pct_of_shares"] is None


def test_NEGATIVE_a_broken_pct_of_breaks_the_card_so_the_old_division_is_gone(feed, monkeypatch):
    monkeypatch.setattr(SR, "pct_of", lambda *a, **k: 123.456)
    feed(1000, 800, 10000, 2.0)
    assert client.short_interest_for("FOO")["pct_of_shares"] == 123.46
