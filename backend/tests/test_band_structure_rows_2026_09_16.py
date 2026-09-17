"""🪜 The band-structure read on BOUNCE-ROOM ROWS (2026-09-16).

Ajay's ask was "Now in all chartmaps tabs, can you prioritize stock by the
thinnest over head or Supply zone where ever is applicable" — and ten Chart
Maps tabs (session, hot_pullback, patterns, signals, overnight, hot_sectors,
bonde, gnt, growth, catalysts) are ROW boards built from
POST /supply-demand/bounce-room, not from `chart_maps/board.board()` tiles.
Until this change they carried nothing at all: no chip, and no line saying
why — unlike the six `n/a` tabs, which say so out loud.

What is pinned here, and NOT pinned here
----------------------------------------
PINNED  the row carries `band_structure` the way it carries `enterable`;
        the payload carries `band_structure_study` + `band_structure_coverage`;
        a row the store has no bands for carries NULL, never a fabricated
        "clear ceiling"; a pending / unavailable row carries no key at all;
        a board where NOT ONE row came back with a read gets the SERVED
        sentence rather than silence; nothing claims a measurement.

NOT PINNED  any row ORDERING. The read is a read; re-ranking a row board is
        HIS call and no key is applied on this path.

Host-runnable (py3.9):
    cd backend && PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest \
        tests/test_band_structure_rows_2026_09_16.py -q -p no:cacheprovider
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import band_structure as BS      # noqa: E402
from supply_demand import bounce_room as BR         # noqa: E402

ET = ZoneInfo("America/New_York")
ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 16, 11, 0, tzinfo=ET)       # Wednesday, in RTH
STORE_DAY = "2026-09-16"

# His own reference name, his own numbers (brief 2026-09-16): CRDO at 162.76
# with demand 161.92–167.68 over 146.34–151.55 ("his 149"), supply far above.
CRDO_BANDS = [
    {"kind": "demand", "lo": 161.92, "hi": 167.68, "touches": 1, "strength": 20.0},
    {"kind": "demand", "lo": 146.34, "hi": 151.55, "touches": 1, "strength": 20.0},
    {"kind": "supply", "lo": 193.50, "hi": 198.97, "touches": 3, "strength": 45.0},
]


def _doc(bands, *, symbol="CRDO", day=STORE_DAY, prev_close=160.0, **extra):
    d = {"_id": f"{symbol}:{day}", "symbol": symbol, "date": day, "geom": "board",
         "bands": list(bands), "atr14": 4.0, "prev_close": prev_close,
         "high_252": 205.0, "recent": [], "computed_at": f"{day}T09:20:00-04:00"}
    d.update(extra)
    return d


def _snap(last, *, low=None, day=STORE_DAY, now=NOW, age_sec=30, prev_close=160.0):
    import pandas as pd
    ts_ns = int((now - timedelta(seconds=age_sec)).timestamp() * 1e9)
    lo = last - 2.0 if low is None else low
    return {"open": lo + 1, "high": last + 1, "low": lo, "close": last,
            "volume": 1e6, "date": pd.Timestamp(day), "change_pct": 0.5,
            "prev_day_close": prev_close,
            "last_trade_price": last, "last_trade_ts_ms": ts_ns}


@pytest.fixture(autouse=True)
def _reset_module_state():
    BR._mem.clear()
    BR._resp_cache.clear()
    yield
    BR._mem.clear()
    BR._resp_cache.clear()


# ── the row read ─────────────────────────────────────────────────────────────
def test_row_carries_the_served_band_structure_read_the_way_it_carries_enterable():
    """The chip on the ten row boards prints `row.band_structure.stat`. If the
    row does not carry it, every one of those boards shows nothing forever."""
    row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), _snap(162.76), NOW)
    read = row["band_structure"]
    assert read is not None
    assert read["applicable"] is True
    assert read["symbol"] == "CRDO"
    assert isinstance(read["stat"], str) and read["stat"]
    assert read["ceiling"] is not None and read["floor"] is not None
    assert json.dumps(row), "the whole row still serializes"


def test_the_row_read_is_the_SAME_engine_no_second_copy():
    """One engine per concept. The row must be byte-for-byte what
    `band_structure.read` answers for the same doc and the same print, so a
    row board and a Chart Maps tile can never disagree about a name."""
    doc, snap = _doc(CRDO_BANDS), _snap(162.76)
    row = BR.read_symbol("CRDO", doc, snap, NOW)
    direct = BS.read(doc=doc, px=row["print"], symbol="CRDO",
                     print_source="live" if row["fresh"] else "scan")
    assert row["band_structure"] == direct


def test_the_row_read_reproduces_his_CRDO_layering_numbers():
    """Brief 2026-09-16: "Something like CRDO had at 149. It has another one
    right below it" — the gap between 161.92's floor and 146.34's top is 6.4%
    of the print. If this number moves, the read stopped answering his ask."""
    row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), _snap(162.76), NOW)
    floor = row["band_structure"]["floor"]
    assert floor["second"] is not None, "the second catch under his 149 band"
    assert floor["second"]["lo"] == pytest.approx(146.34)
    assert floor["gap_pct"] == pytest.approx(6.37, abs=0.05)
    assert floor["bands_below"] == 2
    # 2026-09-17: the clause names the band it measures. "2nd band" left
    # this sentence because the Deep Demand tile used it for another band.
    assert "next demand band 6.4% below it" in row["band_structure"]["stat"]


def test_the_row_read_reads_the_SAME_print_the_rest_of_the_row_read():
    """A ceiling "0.5% up" measured off a different price than the row's own
    print would be a second answer on one card."""
    row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), _snap(162.76), NOW)
    assert row["print"] == pytest.approx(162.76)
    assert BS.read(doc=_doc(CRDO_BANDS), px=162.76, symbol="CRDO",
                   print_source="live") == row["band_structure"]


# ── WHICH print the row read (critique M3, 2026-09-16) ───────────────────────
def test_the_row_says_the_print_is_LIVE_when_the_trade_is_fresh():
    """`print_of` already decided whether this price is a FRESH trade or the
    stored close it fell back to — one line above, the 🎯 read is handed that
    answer. This read was not, so every one of the ten row boards served
    `{"source": None}` and could only print the generic "live when fresh,
    stored close when not" line over a number that might be either."""
    row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), _snap(162.76, age_sec=30), NOW)
    assert row["fresh"] is True
    assert row["band_structure"]["print"] == {"px": pytest.approx(162.76),
                                              "source": "live"}


def test_NEGATIVE_a_STALE_snapshot_is_served_as_scan_never_as_live():
    """The whole point. Outside the session (and any time the last trade is
    older than `STALE_PRINT_SEC`) the distances in this read are measured off a
    closed-bar price, and the row must say so rather than let a surface imply a
    live print."""
    stale = _snap(162.76, age_sec=BR.STALE_PRINT_SEC + 60)
    row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), stale, NOW)
    assert row["fresh"] is False
    assert row["band_structure"]["print"]["source"] == "scan"
    assert row["band_structure"]["print"]["source"] != "live"


def test_the_row_read_says_the_SAME_print_source_the_ENTERABLE_read_does():
    """One row, one answer about which price it is. The two reads sit on
    consecutive lines and must never disagree."""
    for age in (30, BR.STALE_PRINT_SEC + 60):
        row = BR.read_symbol("CRDO", _doc(CRDO_BANDS), _snap(162.76, age_sec=age), NOW)
        assert (row["band_structure"]["print"]["source"]
                == (row["enterable"] or {}).get("print", {}).get("source")), age


# ── NEGATIVES ────────────────────────────────────────────────────────────────
def test_NEGATIVE_a_doc_with_no_bands_reads_None_never_a_clear_ceiling():
    """`room_read` answers CLEAR for a doc with no bands — correctly, for its
    own question. Carrying that into this read would put a name the engine
    could not cluster at the top of a board that ranks thin ceilings."""
    row = BR.read_symbol("XYZ", _doc([]), _snap(162.76), NOW)
    assert row["band_structure"] is None
    assert json.dumps(row)


def test_NEGATIVE_a_legacy_doc_shape_still_serializes_and_reads_None():
    """Docs written before the band engine existed have no `bands` key at all.
    The row must survive them — every board polls this route."""
    legacy = {"_id": "OLD:2026-09-16", "symbol": "OLD", "date": STORE_DAY,
              "prev_close": 160.0, "recent": []}
    row = BR.read_symbol("OLD", legacy, _snap(162.76), NOW)
    assert row["band_structure"] is None
    assert json.dumps(row)


def test_NEGATIVE_pending_unavailable_and_no_print_rows_carry_no_key_at_all():
    """A null under a key a board reads as "no ceiling" is worse than no key.
    The 🧨 / 🎯 precedent: these rows return before the read ever runs."""
    pending = BR.read_symbol("abc", None, None, NOW)
    tomb = {"_id": "ABC:2026-09-16", "symbol": "ABC", "date": STORE_DAY,
            "error": BR.NO_DATA_ERROR}
    unavail = BR.read_symbol("ABC", tomb, _snap(162.76), NOW)
    noprint = BR.read_symbol("CRDO", _doc(CRDO_BANDS), None, NOW)
    for row in (pending, unavail, noprint):
        assert "band_structure" not in row
    assert pending == {"symbol": "ABC", "coverage": "pending"}


def test_NEGATIVE_the_row_path_adds_no_owner_setting():
    """Rule #1. The read is built from bands the store already drew; it must
    not smuggle a threshold onto the payload the page calls PARAMS."""
    before = dict(BR.PARAMS)
    payload = BR.build_payload(["CRDO"], docs={"CRDO": _doc(CRDO_BANDS)},
                               snapshot={"CRDO": _snap(162.76)}, now=NOW,
                               store_date=STORE_DAY, pending=[])
    assert payload["params"] == before
    assert "band_structure" not in payload["params"]


# ── the payload ──────────────────────────────────────────────────────────────
def _payload(rows_docs, snaps):
    return BR.build_payload(list(rows_docs), docs=dict(rows_docs), snapshot=dict(snaps),
                            now=NOW, store_date=STORE_DAY, pending=[])


def test_payload_carries_the_study_verdict_and_an_honest_coverage_block():
    p = _payload({"CRDO": _doc(CRDO_BANDS)}, {"CRDO": _snap(162.76)})
    assert p["band_structure_study"] == BS.measured_verdict()
    cov = p["band_structure_coverage"]
    assert cov["rows_with_read"] == 1 and cov["rows_without_read"] == 0
    assert cov["note"] is None, "at least one row has a read — no board-level note"
    assert p["rows"]["CRDO"]["band_structure"]["applicable"] is True
    assert json.dumps(p)


def test_NEGATIVE_a_board_where_no_row_has_a_read_gets_the_SERVED_sentence():
    """The whole point of the change. A board with no chip anywhere and no
    line reads as a board where the read silently stopped — the thing the
    🎯 n/a tabs exist to prevent."""
    p = _payload({"A": _doc([], symbol="A"), "B": _doc([], symbol="B")},
                 {"A": _snap(162.76), "B": _snap(162.76)})
    cov = p["band_structure_coverage"]
    assert cov["rows_with_read"] == 0 and cov["rows_without_read"] == 2
    assert cov["note"] == BR.BAND_STRUCTURE_NO_READ
    assert "No band read" in cov["note"]
    assert "reversal" in cov["note"] or "bounc" not in cov["note"].lower(), \
        "no served sentence says 'bounce' (2026-09-09 rule)"


def test_NEGATIVE_an_empty_request_has_nothing_to_explain():
    """Zero rows is not "no band read for these names" — there are no names."""
    p = BR.build_payload([], docs={}, snapshot={}, now=NOW, store_date=STORE_DAY, pending=[])
    cov = p["band_structure_coverage"]
    assert cov["rows_with_read"] == 0 and cov["rows_without_read"] == 0
    assert cov["note"] is None


def test_NEGATIVE_pending_rows_are_counted_as_without_a_read_not_hidden():
    """A row the worker has not built yet is honestly "without a read"; it is
    never counted as covered, and it never suppresses the note on its own."""
    p = BR.build_payload(["CRDO", "NEW"], docs={"CRDO": _doc(CRDO_BANDS)},
                         snapshot={"CRDO": _snap(162.76)}, now=NOW,
                         store_date=STORE_DAY, pending=["NEW"])
    cov = p["band_structure_coverage"]
    assert cov["rows_with_read"] == 1 and cov["rows_without_read"] == 1
    assert cov["note"] is None, "one row HAS a read — the board is not blank"
    assert "band_structure" not in p["rows"]["NEW"]


def test_nothing_on_this_path_claims_a_measurement():
    """The 2026-09-16 study ran and came back `no_signal` on BOTH asks, so
    every served copy of it must say NO SIGNAL SEPARATES — on the row, on the
    payload, everywhere — and still carry no score and no lift."""
    p = _payload({"CRDO": _doc(CRDO_BANDS)}, {"CRDO": _snap(162.76)})
    assert BS.status() == BS.STATUS_NO_SIGNAL
    assert p["band_structure_study"].get("status") in (BS.STATUS_NO_SIGNAL, None)
    head = p["band_structure_study"]["headline"]
    assert "NO SIGNAL SEPARATES" in head
    assert "pending" not in head.lower()
    read = p["rows"]["CRDO"]["band_structure"]
    assert read["measured"]["status"] == "no_signal"
    assert read["score"] is None, "no score outside the `separates` branch"
    assert read["measured"]["oos_lift"] is None and read["measured"]["oos_ci"] is None


# ── the route ────────────────────────────────────────────────────────────────
def test_the_route_actually_serves_the_field(monkeypatch):
    """Through FastAPI, the way the ten boards fetch it."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from supply_demand.api import router

    monkeypatch.setattr(BR, "api_payload",
                        lambda symbols: _payload({"CRDO": _doc(CRDO_BANDS)},
                                                 {"CRDO": _snap(162.76)}))
    app = FastAPI()
    app.include_router(router)
    c = TestClient(app)
    j = c.post("/supply-demand/bounce-room", json={"symbols": ["CRDO"]}).json()
    assert j["rows"]["CRDO"]["band_structure"]["stat"]
    assert j["band_structure_study"]["headline"]
    assert j["band_structure_coverage"]["note"] is None


# ── the ordering is NOT wired here (his call) ────────────────────────────────
def test_NEGATIVE_the_row_path_applies_no_ordering():
    """Ordering on row boards is HIS call. `bounce_room_key` — the one key this
    module sorts by — must be untouched by the band read, so nobody can claim a
    ranking he never asked for shipped by accident."""
    src = (ROOT / "backend/supply_demand/bounce_room.py").read_text()
    head = src[src.index("def bounce_room_key"):]
    assert "band_structure" not in head[:1500]
    assert "band_structure_key" not in src, \
        "the ordering key is not applied on the row path — his call"
