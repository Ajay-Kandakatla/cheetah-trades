"""🚩 card display fixes 2026-11-27 (SPEC sicheck rev 2 §3.6 D4 + B3, package gg-display-be).

D4: `chips.row_asof` = {"text": "as of HH:MM"} when the card's scan row was last qualified on an EARLIER pass than the
one shown (by ≥ tab.READ_AT_MIN_LAG_SEC); the key is ABSENT otherwise. Change / Volume / the 📊 key / card order never
move with it (the number stays the older row's — HIS CALL #15).
B3: a "stale_served" float says "(stale, read {date})" — the READ date of the shares_cache row, same date string.
Docs: docs/gajjala/chart_display_fixes_2026_11_27.md.
"""
from __future__ import annotations

import copy
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import context as CX
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_context import Massive, Yahoo
from tests.test_gajjala_potential_tab import day_store
from tests.test_gajjala_store import fake_store
from tests.test_gajjala_tab import R, read_doc

ET = ZoneInfo("America/New_York")
D = date(2026, 11, 27)                                   # Fri — the NXAT morning
BF = "bull_flag"


def et(h, m, s=0, d=D):
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=ET)


def nxat_row(sym="NXAT", *, volume=771_509.0, change=38.0, lte="2026-11-27 08:21:07"):
    r = {"symbol": sym, "price": 2.15, "prev_close": 1.56, "change_pct": change, "volume": volume,
         "vol_src": "min_av", "type": "CS", "tape_session": "premarket"}
    if lte is not None:
        r["last_trade_et"] = lte
    return r


def world(qualified_at, pass_at, rows=None, reads=None, requal_at=None):
    """Every collection written by its own writer: record_qualifiers at `qualified_at` (again at `requal_at` when
    given — the same rows re-qualified on a later pass), the read, the pass."""
    st = fake_store()
    rows = rows or [nxat_row()]
    st.record_qualifiers(D, qualified_at, rows, "premarket")
    if requal_at is not None:
        st.record_qualifiers(D, requal_at, rows, "premarket")
    for r in rows:
        sym = r["symbol"]
        setups = (reads or {}).get(sym) or {BF: R(BF, "forming", ready=True, trigger=2.30)}
        st.upsert_read(D, sym, read_doc(sym, setups, day=D, updated_at=pass_at, at=pass_at), now=pass_at)
    st.record_pass(D, pass_at, {"status": "ok", "tape_session": "premarket",
                                "strip": {"runners_100": 0, "runners_80": 0, "best_change_pct": 38.0,
                                          "best_symbol": rows[0]["symbol"], "quiet": False}})
    return st


def board(st, now):
    return GT.build(BF, now=now, store=st)


def tiles_by(out):
    return {t["symbol"]: t for t in out["tiles"]}


# ── D4 the constants ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_named_constants():
    assert GT.READ_AT_MIN_LAG_SEC == 1                                 # the literal _read_at_text always used
    assert GT.ROW_ASOF_TEXT.format(hhmm="08:21") == "as of 08:21"


def test_both_rules_read_the_one_named_lag(monkeypatch):
    pa = et(8, 40)
    doc = {"last_qualified_at": pa - timedelta(seconds=30), "last": {"last_trade_et": "2026-11-27 08:39:50"}}
    rd = {"updated_at": pa - timedelta(seconds=30)}
    assert GT._row_asof(doc, pa) and GT._read_at_text(rd, pa)
    monkeypatch.setattr(GT, "READ_AT_MIN_LAG_SEC", 60)                 # NEGATIVE: one name moves both rules
    assert GT._row_asof(doc, pa) is None and GT._read_at_text(rd, pa) is None


# ── D4 the stamp on a served card ────────────────────────────────────────────────────────────────────────────────
def test_nxat_shape_a_row_from_an_earlier_pass_is_stamped():
    st = world(et(8, 21, 30), et(8, 40))
    t = tiles_by(board(st, et(8, 41)))["NXAT"]
    assert t["gajjala"]["chips"]["row_asof"] == {"text": "as of 08:21"}
    assert t["gajjala"]["chips"]["volume"] == 771_509.0                # the number stays the older row's (HIS CALL #15)


def test_NEGATIVE_a_row_qualified_on_the_shown_pass_has_no_key():
    st = world(et(8, 40), et(8, 40))
    chips = tiles_by(board(st, et(8, 41)))["NXAT"]["gajjala"]["chips"]
    assert "row_asof" not in chips


def test_NEGATIVE_under_the_lag_no_key_and_at_the_lag_the_key():
    pa = et(8, 40)
    doc = {"last_qualified_at": pa - timedelta(seconds=0.5), "last": nxat_row()}
    assert GT._row_asof(doc, pa) is None
    doc["last_qualified_at"] = pa - timedelta(seconds=GT.READ_AT_MIN_LAG_SEC)
    assert GT._row_asof(doc, pa) == {"text": "as of 08:21"}
    doc["last_qualified_at"] = pa + timedelta(seconds=30)               # NEGATIVE: a row NEWER than the pass
    assert GT._row_asof(doc, pa) is None


@pytest.mark.parametrize("doc,pa", [
    (None, et(8, 40)),                                                 # no scan doc
    ({}, et(8, 40)),
    ({"last": nxat_row()}, et(8, 40)),                                 # no qualify stamp
    ({"last_qualified_at": "2026-11-27T13:21:00Z", "last": nxat_row()}, et(8, 40)),   # a string, not a datetime
    ({"last_qualified_at": et(8, 21), "last": nxat_row()}, None),      # no pass stamp
    ({"last_qualified_at": et(8, 21), "last": nxat_row()}, "08:40"),
    ("junk", et(8, 40)),
])
def test_NEGATIVE_no_stamp_or_no_doc_no_key(doc, pa):
    assert GT._row_asof(doc, pa) is None


def test_NEGATIVE_no_pass_on_file_no_key_on_any_card():
    st = fake_store()
    st.record_qualifiers(D, et(8, 21), [nxat_row()], "premarket")
    st.upsert_read(D, "NXAT", read_doc("NXAT", {BF: R(BF, "forming")}, day=D), now=et(8, 21))
    out = board(st, et(8, 41))
    assert all("row_asof" not in t["gajjala"]["chips"] for t in out["tiles"])


def test_hhmm_falls_back_to_the_qualify_stamp_in_et():
    pa = et(8, 40)
    lq = datetime(2026, 11, 27, 13, 21, 30)                            # NAIVE UTC, as the live Mongo client hands it
    for last in ({}, {"last_trade_et": None}, {"last_trade_et": "2026-11-27"}, {"last_trade_et": "garbage-garbage-xx"},
                 {"last_trade_et": 1764250867}, None):
        assert GT._row_asof({"last_qualified_at": lq, "last": last}, pa) == {"text": "as of 08:21"}, last


def test_NEGATIVE_the_chips_key_only_when_given():
    base = GT._chips({}, BF, {}, nxat_row(), {}, None, None)
    assert "row_asof" not in base
    for junk in (None, {}):
        assert GT._chips({}, BF, {}, nxat_row(), {}, None, None, row_asof=junk) == base
    got = GT._chips({}, BF, {}, nxat_row(), {}, None, None, row_asof={"text": "as of 08:21"})
    assert got.pop("row_asof") == {"text": "as of 08:21"} and got == base


# ── D4 NEGATIVE nothing else moves ───────────────────────────────────────────────────────────────────────────────
def _strip(o):
    o = copy.deepcopy(o)
    for t in o.get("tiles") or []:
        t["gajjala"]["chips"].pop("row_asof", None)
    return o


def test_NEGATIVE_setup_tile_identical_with_and_without_the_stamp():
    doc = read_doc("NXAT", {BF: R(BF, "forming", ready=True)}, day=D)
    kw = dict(scan_row=nxat_row(), sess={}, listed=None, kf_rank=True)
    a = GT.setup_tile(doc, BF, "5m", **kw)
    b = GT.setup_tile(doc, BF, "5m", row_asof={"text": "as of 08:21"}, **kw)
    assert "row_asof" not in a["gajjala"]["chips"] and b["gajjala"]["chips"]["row_asof"] == {"text": "as of 08:21"}
    assert a["gajjala"]["_volume"] == b["gajjala"]["_volume"] == 771_509.0         # the 📊 key
    for k in ("change_pct", "volume"):
        assert a["gajjala"]["chips"][k] == b["gajjala"]["chips"][k]
    assert a["stats"] == b["stats"]
    b["gajjala"]["chips"].pop("row_asof")
    assert a == b


def test_NEGATIVE_the_board_order_and_numbers_identical_with_and_without_the_stamp():
    rows = [nxat_row("NXAT", volume=771_509.0, change=38.0), nxat_row("BBBB", volume=2.5e6, change=12.0),
            nxat_row("CCCC", volume=1.1e6, change=55.0, lte=None)]
    stale = board(world(et(8, 21, 30), et(8, 40), rows=rows), et(8, 41))
    fresh = board(world(et(8, 21, 30), et(8, 40), rows=rows, requal_at=et(8, 40)), et(8, 41))   # same first sighting
    assert [t["symbol"] for t in stale["tiles"]] == [t["symbol"] for t in fresh["tiles"]] == ["BBBB", "CCCC", "NXAT"]
    assert {s: t["gajjala"]["chips"].get("row_asof") for s, t in tiles_by(stale).items()} == {
        "NXAT": {"text": "as of 08:21"}, "BBBB": {"text": "as of 08:21"}, "CCCC": {"text": "as of 08:21"}}
    assert all("row_asof" not in t["gajjala"]["chips"] for t in fresh["tiles"])
    for s in ("NXAT", "BBBB", "CCCC"):
        a, b = tiles_by(stale)[s], tiles_by(fresh)[s]
        for k in ("change_pct", "volume"):
            assert a["gajjala"]["chips"][k] == b["gajjala"]["chips"][k]
        assert a["stats"] == b["stats"]
    assert _strip(stale)["tiles"] == _strip(fresh)["tiles"]


def test_the_potential_tiles_call_site_hands_the_stamp_too():
    """🧠 cards: the fixture day's rows were last qualified at 09:21 ET (no last_trade_et), the shown pass is 10:31."""
    out = GT.build(GC.POTENTIAL_SUB, now=datetime(2026, 10, 13, 10, 31, tzinfo=ET), store=day_store())
    assert out["tiles"]
    assert {t["gajjala"]["chips"].get("row_asof", {}).get("text") for t in out["tiles"]} == {"as of 09:21"}


# ── B3 the float read date ───────────────────────────────────────────────────────────────────────────────────────
NOW = datetime(2026, 10, 13, 14, 1, tzinfo=timezone.utc)


def _floats(cache):
    return CX.floats_for(["AAA"], status_lookup=Yahoo(cache=cache), massive_lookup=Massive(), now=NOW,
                         sleep=lambda s: None, refine=False)["AAA"]


def test_stale_float_says_read_with_the_same_date_string():
    old = NOW - timedelta(days=9)
    r = _floats({"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000, "as_of": int(old.timestamp())},
                         "stale_served")})
    assert r["text"] == f"Float 3.1M (stale, read {r['as_of'][:10]})" == "Float 3.1M (stale, read 2026-10-04)"
    assert "as of" not in r["text"]                                    # NEGATIVE: the old word is gone


def test_stale_shares_out_says_read_too():
    old = NOW - timedelta(days=9)
    r = _floats({"AAA": ({"shares_outstanding": 8_100_000, "as_of": int(old.timestamp())}, "stale_served")})
    assert r["text"].endswith("(stale, read 2026-10-04)") and r["text"].startswith("shares out")


def test_NEGATIVE_a_fresh_row_text_unchanged():
    row = int((NOW - timedelta(days=2)).timestamp())
    r = _floats({"AAA": ({"float_shares": 3_100_000, "shares_outstanding": 8_100_000, "as_of": row}, "cached")})
    assert r["text"] == "Float 3.1M"


def test_the_row_as_of_docstring_says_read_time():
    doc = CX._row_as_of.__doc__ or ""
    assert "READ time" in doc and "NOT the age of the float value" in doc
