"""🌀 The AMD column on the 🔥 Hottest board (Ajay 2026-09-22).

    "Add an AMD tag for these. like a column for me to see which one are
     getting manipulated."

WHAT IS PINNED HERE, AND WHY THE NEGATIVES ARE THE POINT
────────────────────────────────────────────────────────
1. A BLANK IS NOT A READ. A name the sweep never saw, a verdict with no grade,
   a verdict graded `"wat"` — none of them may wear `TB.verdict_text`'s
   `or table["none"]` fallback words ("AMD no cycle"), which is a real read's
   sentence.
2. A BROKEN IMPORT MUST NOT 500 THE BOARD. `rotation.api.HA` forced to None,
   and `HA.attach` forced to raise, both still serve 200 and a full board.
3. STALENESS IS MEASURED AGAINST THE LAST DUE SWEEP, ON AN ET CLOCK. The sweep
   writes at 17:20 ET; `board._session_day` has no time-of-day test, so the
   naive comparison is "stale" every weekday morning — exactly when he reads
   the board. Six frozen clocks pin the matrix.
4. EVERY COUNT IS BUILT ON THE REQUEST THAT PRINTS IT, and the sums are
   asserted (`sum(grades) == n_known`, `n_known + n_blank == n`).
5. NOTHING IS RANKED, REORDERED OR GATED. `"amd"` is not in `H.SORT_KEYS`, and
   the board's order is byte-identical before and after `attach`.
6. NO CONSTANT IS RETYPED: the measured figures are pinned against
   `turning_bullish`'s own docstring, the TTL against the endpoint's own
   `_MEMBERS_TTL_SEC`, and the sweep clock against `backend/crontab`.

NOTHING HERE IS MEASURED FORWARD. The AMD read is MEASURED INVERTED on its own
claim (−4.2pp [−6.92, −1.89] like-for-like); this column is a state, not a
ranking, and these tests exist to keep it one.
"""
from __future__ import annotations

import asyncio
import copy
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rotation import api as A                  # noqa: E402
from rotation import hottest as H              # noqa: E402
from rotation import hottest_amd as HA         # noqa: E402
from supply_demand import turning_bullish as TB  # noqa: E402

ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# 2026-09-21 is a Monday (the shipped fixture date on this board).
MON_EVE = datetime(2026, 9, 21, 20, 10, tzinfo=ET)
TUE_AM = datetime(2026, 9, 22, 10, 0, tzinfo=ET)
TUE_PM = datetime(2026, 9, 22, 18, 0, tzinfo=ET)
SAT_AM = datetime(2026, 9, 26, 11, 0, tzinfo=ET)

DEFENSE = ["KRMN", "RCAT", "LASR", "KTOS", "ONDS", "BBAI"]


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------
def _stamp(y, m, d, hh=17, mm=20):
    """The sweep's own stamp: an ET wall clock stored as a UTC datetime, the
    way `turning_bullish.warm` writes it."""
    return datetime(y, m, d, hh, mm, tzinfo=ET).astimezone(UTC)


def _verdict(grade, **kw) -> dict:
    v = {"grade": grade, "base_bars": 14, "phase": "manipulation",
         "in_window": True, "turning": grade == TB.AMD_TURNING}
    if grade in ("raided", "stale"):
        v["raid_bars_ago"] = kw.pop("age", 2 if grade == "raided" else 7)
    elif grade == "failed":
        v["failed_bars_ago"] = kw.pop("age", 3)
    elif grade == "marked_up":
        v["bars_ago"] = kw.pop("age", 5)
    else:
        kw.pop("age", None)
    v.update(kw)
    return v


GRADED = {
    "KRMN": _verdict("raided"),
    "RCAT": _verdict("marked_up"),
    "LASR": _verdict("stale"),
    "KTOS": _verdict("failed"),
    "ONDS": _verdict("basing"),
    "TENB": _verdict("none"),
    "QLYS": _verdict("raided", age=0),
    "NVDA": _verdict("basing"),
}


_UNSET = object()


def _doc(rows=None, built_at=_UNSET, **kw) -> dict:
    rows = GRADED if rows is None else rows
    out = {"_id": "latest",
           "built_at": _stamp(2026, 9, 21) if built_at is _UNSET else built_at,
           "n_scanned": 2693, "n_rows": len(rows),
           "rows": [{"symbol": s, "amd": v, "amd_grade": (v or {}).get("grade")}
                    for s, v in rows.items()]}
    out.update(kw)
    return out


def _payload() -> dict:
    """Three sectors (one with two industries) + two themes, over names from
    his screenshot."""
    members = {
        "KRMN": ("Industrials", "Aerospace & Defense"),
        "RCAT": ("Industrials", "Aerospace & Defense"),
        "LASR": ("Technology", "Semiconductors"),
        "KTOS": ("Industrials", "Aerospace & Defense"),
        "ONDS": ("Technology", "Communication Equipment"),
        "BBAI": ("Technology", "Software - Infrastructure"),
        "TENB": ("Technology", "Software - Infrastructure"),
        "QLYS": ("Technology", "Software - Infrastructure"),
        "XOM": ("Energy", "Oil & Gas Integrated"),
    }
    by = {}
    for i, (s, (sec, ind)) in enumerate(members.items()):
        by[s] = {"last_close": 100.0 + i, "ret_1d": 1.0 + i, "ret_5d": 2.0 + i,
                 "ret_21d": 3.0 + i, "ret_63d": 4.0 + i,
                 "sector": sec, "industry": ind}
    sector_syms: dict = {}
    for s, (sec, _ind) in members.items():
        sector_syms.setdefault(sec, []).append(s)
    return {
        "as_of": "2026-09-18",
        "sectors": [{"group": g, "n": len(v), "rel_1d": -0.5, "rel_5d": 2.0,
                     "rel_21d": -4.27, "pct_positive_1d": 30}
                    for g, v in sector_syms.items()],
        "industries": [], "themes": [], "sampled": {},
        H.T.MEMBERS_KEY: {
            "benchmark": {"symbol": "RSP", "ret_1d": -0.28, "ret_5d": -1.08,
                          "ret_21d": -3.76, "ret_63d": 0.71},
            "by_symbol": by,
            "groups": {
                "sector": {g: {"median_21d": -4.27, "symbols": list(v)}
                           for g, v in sector_syms.items()},
                "theme": {"defense": {"median_21d": -1.0,
                                      "symbols": [s for s in DEFENSE if s in by]},
                          "ai_semis": {"median_21d": -2.0,
                                       "symbols": ["LASR", "TENB", "QLYS"]}},
            },
        },
    }


def _board() -> dict:
    return H.build(_payload())


def _cells(body: dict) -> dict:
    """{symbol: cell} over every NAME row the board carries."""
    out = {}
    for r in HA._name_rows(body):
        out[r["symbol"]] = r[HA.ROW_KEY]
    return out


def _group_rows(body: dict) -> list:
    rows = list(body.get("themes") or [])
    for s in body.get("sectors") or []:
        rows.append(s)
        rows.extend(s.get("industries") or [])
    return rows


@pytest.fixture(autouse=True)
def _clean_cache():
    HA.cache_clear()
    yield
    HA.cache_clear()


# ---------------------------------------------------------------------------
# 1 — every name row gets a cell; group rows get none
# ---------------------------------------------------------------------------
def test_every_name_row_gets_a_cell_and_no_group_row_does():
    body = _board()
    s = HA.attach(body, doc=_doc(), now=TUE_AM)
    cells = _cells(body)
    assert cells and set(cells) == {r["symbol"] for r in HA._name_rows(body)}
    for cell in cells.values():
        assert set(cell) == set(HA._ROW_KEYS)
    for g in _group_rows(body):
        assert HA.ROW_KEY not in g
    assert s["label"] == HA.LABEL and s["available"] is True


# ---------------------------------------------------------------------------
# 2 — NEG a name the sweep never saw
# ---------------------------------------------------------------------------
def test_a_name_the_sweep_never_saw_is_unknown_and_never_reads_as_clean():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    cell = _cells(body)["XOM"]
    assert cell["known"] is False
    assert cell["grade"] is None and cell["text"] is None
    assert cell["reason"] == "not_in_store"
    txt = cell["reason_text"]
    assert txt and txt == HA.REASON_TEXT["not_in_store"]
    low = txt.lower()
    assert "no cycle" not in low and "clean" not in low and "none" not in low
    assert "UNKNOWN" in txt


# ---------------------------------------------------------------------------
# 3 — a stored `none` IS a read
# ---------------------------------------------------------------------------
def test_a_stored_none_grade_is_a_real_read_not_a_blank():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    cell = _cells(body)["TENB"]
    assert cell["known"] is True and cell["grade"] == "none"
    assert cell["text"] == TB.verdict_text("amd", GRADED["TENB"])[0]
    assert cell["reason"] is None and cell["reason_text"] is None


# ---------------------------------------------------------------------------
# 4 — NEG an ungradeable verdict never borrows a real read's words
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad", [
    {"base_bars": 12, "phase": "accumulation"},          # no grade at all
    {"grade": "wat", "base_bars": 12},                   # not a member
    {"grade": None},
    {},
])
def test_an_ungradeable_verdict_is_not_a_read(bad):
    rows = dict(GRADED)
    rows["BBAI"] = bad
    body = _board()
    HA.attach(body, doc=_doc(rows), now=TUE_AM)
    cell = _cells(body)["BBAI"]
    assert cell["known"] is False
    assert cell["reason"] == "no_verdict"
    assert cell["text"] is None and cell["grade"] is None
    assert "AMD no cycle" not in json.dumps(cell, ensure_ascii=False)
    # the fallback the engine WOULD have lent it, proving the gate does work
    assert TB.verdict_text("amd", bad)[0] in ("", "AMD no cycle")


def test_a_verdict_that_is_not_a_dict_is_not_a_read():
    for junk in (None, "raided", 3, []):
        cell = HA.read_one("KRMN", junk)
        assert cell["known"] is False and cell["reason"] == "no_verdict"
        assert set(cell) == set(HA._ROW_KEYS)


# ---------------------------------------------------------------------------
# 5 — NEG an empty document
# ---------------------------------------------------------------------------
def test_an_empty_document_blanks_every_row_and_changes_nothing_else():
    before = _board()
    body = copy.deepcopy(before)
    s = HA.attach(body, doc={}, now=TUE_AM)
    assert s["available"] is False
    assert s["unavailable_note"] == HA.UNAVAILABLE_NOTE and s["unavailable_note"]
    cells = _cells(body)
    assert cells
    for cell in cells.values():
        assert cell["known"] is False and cell["reason"] == "store_unavailable"
    stripped = copy.deepcopy(body)
    for r in HA._name_rows(stripped):
        r.pop(HA.ROW_KEY)
    assert stripped == before
    assert s["n_known"] == 0 and s["n_blank"] == s["n"] and s["n"] > 0


# ---------------------------------------------------------------------------
# 6 — NEG a `stored` that RAISES
# ---------------------------------------------------------------------------
def test_a_store_that_raises_is_the_same_as_a_missing_one(monkeypatch):
    def _boom(*a, **kw):
        raise RuntimeError("mongo is on fire")

    monkeypatch.setattr(HA.TB, "stored", _boom)
    body = _board()
    s = HA.attach(body, now=TUE_AM)
    assert s["available"] is False and s["unavailable_note"]
    assert all(c["reason"] == "store_unavailable" for c in _cells(body).values())


def test_unavailable_is_a_full_summary_and_never_raises():
    s = HA.unavailable()
    assert s["available"] is False and s["sortable"] is False
    assert s["coloured"] is False and s["unavailable_note"] == HA.UNAVAILABLE_NOTE
    assert s["n"] == 0 and s["n_known"] == 0 and s["n_blank"] == 0
    assert s["grade_order"] == list(TB.AMD_GRADES)
    assert json.dumps(s, ensure_ascii=False)
    assert HA.unavailable("junk-reason")["available"] is False


# ---------------------------------------------------------------------------
# 7 — NEG the import guard: a broken module must not 500 the board
# ---------------------------------------------------------------------------
def _call_endpoint(monkeypatch, **kw):
    """The real handler, with the member table injected and the live legs
    replaced by the PURE build — no Mongo, no network."""
    monkeypatch.setattr(A, "_members_table",
                        lambda: (_payload()[H.T.MEMBERS_KEY], {"source": "scan"}))
    monkeypatch.setattr(A, "_members_payload", _payload)
    monkeypatch.setattr(A.H, "build_live", lambda payload, **k: H.build(
        payload, sort=k.get("sort", H.DEFAULT_SORT),
        direction=k.get("direction", H.DEFAULT_DIR),
        names_per_group=k.get("names_per_group", H.NAMES_PER_GROUP)))

    import rotation as _pkg

    class _NoTags:
        @staticmethod
        def latest_within(*a, **k):
            return {}

        @staticmethod
        def attach(payload, tags=None):
            return payload

    monkeypatch.setattr(_pkg, "sector_news_tags", _NoTags, raising=False)
    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(A.rotation_hottest(**kw))
    finally:
        loop.close()
    return resp, json.loads(bytes(resp.body).decode())


def test_a_broken_import_drops_the_column_and_still_serves_the_board(monkeypatch):
    monkeypatch.setattr(A, "HA", None)
    resp, body = _call_endpoint(monkeypatch, sort=H.DEFAULT_SORT,
                                dir=H.DEFAULT_DIR, names=25, basis=H.D1_CLOSE)
    assert resp.status_code == 200
    assert "amd_summary" not in body
    assert body["sectors"] and body["sectors"][0]["names"]


def test_an_attach_that_raises_serves_the_unavailable_block_not_a_500(monkeypatch):
    def _boom(*a, **kw):
        raise ValueError("attach exploded")

    monkeypatch.setattr(A.HA, "attach", _boom)
    resp, body = _call_endpoint(monkeypatch, sort=H.DEFAULT_SORT,
                                dir=H.DEFAULT_DIR, names=25, basis=H.D1_CLOSE)
    assert resp.status_code == 200
    assert body["amd_summary"]["available"] is False
    assert body["amd_summary"]["unavailable_note"]
    assert body["sectors"] and body["sectors"][0]["names"]


# ---------------------------------------------------------------------------
# 8 — the words come from the ONE wording table
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("grade", list(TB.AMD_GRADES))
def test_text_and_tone_are_the_engines_own_for_every_grade(grade):
    v = _verdict(grade)
    cell = HA.read_one("KRMN", v)
    text, tone = TB.verdict_text("amd", v)
    assert cell["known"] is True
    assert cell["text"] == text and cell["tone"] == tone
    assert cell["title"].startswith("KRMN: %s. " % text)
    assert HA.HONESTY in cell["title"]
    if grade in ("basing", "none"):
        assert "d ago" not in text and "today" not in text
        assert cell["bars_ago"] is None
    else:
        assert cell["bars_ago"] is not None


def test_the_age_comes_off_the_same_branch_the_wording_table_uses():
    assert HA.read_one("X", _verdict("raided", age=2))["bars_ago"] == 2
    assert HA.read_one("X", _verdict("stale", age=9))["bars_ago"] == 9
    assert HA.read_one("X", _verdict("failed", age=4))["bars_ago"] == 4
    assert HA.read_one("X", _verdict("marked_up", age=6))["bars_ago"] == 6
    # `marked_up` must NOT read a raid's age, and a raid must not read a markup's
    mixed = _verdict("marked_up", age=6, raid_bars_ago=99, failed_bars_ago=88)
    assert HA.read_one("X", mixed)["bars_ago"] == 6


# ---------------------------------------------------------------------------
# 9 — every measured figure is the engine's own
# ---------------------------------------------------------------------------
def test_every_measured_figure_appears_verbatim_in_the_engines_docstring():
    doc = " ".join((TB.__doc__ or "").split())
    for key in ("date", "population", "fire_rate", "forward", "claim",
                "buckets", "fresh_cut"):
        assert HA.AMD_MEASURED[key] in doc, key
    assert Path(__file__).resolve().parents[2].joinpath(
        HA.AMD_MEASURED["script"]).exists()


# ---------------------------------------------------------------------------
# 10 — the honesty sentence says what it must
# ---------------------------------------------------------------------------
def test_the_honesty_sentence_refuses_to_sell_the_read():
    for bit in ("INVERTED", HA.AMD_MEASURED["claim"], "not a ranking",
                "gates nothing", "colours nothing",
                HA.AMD_MEASURED["script"], HA.AMD_MEASURED["doc"]):
        assert bit in HA.HONESTY, bit
    assert HA.AMD_MEASURED["claim"] in HA.NO_COLOUR_REASON
    assert HA.AMD_MEASURED["claim"] in HA.NO_SORT_REASON
    assert HA.HONESTY in HA.HEAD_TITLE
    assert "{" not in HA.HONESTY and "}" not in HA.HONESTY


def test_the_group_note_says_why_a_group_row_is_blank():
    body = _board()
    s = HA.attach(body, doc=_doc(), now=TUE_AM)
    assert s["group_note"] == HA.GROUP_NOTE
    assert "median" in HA.GROUP_NOTE and "full membership" in HA.GROUP_NOTE
    assert s["sortable"] is False and s["coloured"] is False


# ---------------------------------------------------------------------------
# 11 — NEG NaN / inf never reach the payload
# ---------------------------------------------------------------------------
def test_a_nan_age_and_an_infinite_base_serve_none_and_survive_json():
    rows = dict(GRADED)
    rows["KRMN"] = _verdict("raided", raid_bars_ago=float("nan"),
                            base_bars=float("inf"))
    body = _board()
    body["amd_summary"] = HA.attach(body, doc=_doc(rows), now=TUE_AM)
    cell = _cells(body)["KRMN"]
    assert cell["bars_ago"] is None and cell["base_bars"] is None
    assert cell["known"] is True and "ago" not in cell["text"]
    blob = json.dumps(A._scrub(body), ensure_ascii=False)
    assert "NaN" not in blob and "Infinity" not in blob


@pytest.mark.parametrize("raw,want", [
    (float("nan"), None), (float("inf"), None), (float("-inf"), None),
    (3, 3), (2.5, 2.5), (None, None), ("x", None), (True, None),
])
def test_the_scrub_is_the_boards_own_rule(raw, want):
    assert HA._num(raw) == want or (HA._num(raw) is None and want is None)


# ---------------------------------------------------------------------------
# 12 — a BSON datetime never reaches the wire
# ---------------------------------------------------------------------------
def test_built_at_serves_as_iso_strings_on_both_clocks():
    body = _board()
    s = HA.attach(body, doc=_doc(), now=TUE_AM)
    assert isinstance(s["built_at"], str) and isinstance(s["built_at_et"], str)
    assert isinstance(s["built_at_date"], str)
    assert not isinstance(s["built_at"], datetime)
    json.dumps(s, ensure_ascii=False)        # a datetime here is a 500, not a gap
    assert s["n_scanned"] == 2693 and s["n_rows"] == len(GRADED)


# ---------------------------------------------------------------------------
# 13 — staleness on frozen clocks
# ---------------------------------------------------------------------------
def test_a_weekday_morning_read_of_last_nights_sweep_is_not_stale():
    s = HA.attach(_board(), doc=_doc(built_at=_stamp(2026, 9, 21)), now=TUE_AM)
    assert s["last_session"] == "2026-09-22"
    assert s["due_session"] == "2026-09-21"      # before 17:20 -> the PREVIOUS one
    assert s["built_at_date"] == "2026-09-21"
    assert s["stale"] is False


def test_after_the_sweep_hour_last_nights_document_is_stale():
    s = HA.attach(_board(), doc=_doc(built_at=_stamp(2026, 9, 21)), now=TUE_PM)
    assert s["due_session"] == "2026-09-22" and s["stale"] is True
    assert "2026-09-21" in s["stale_note"] and "2026-09-22" in s["stale_note"]


def test_a_sweep_that_skipped_a_session_is_stale_even_in_the_morning():
    s = HA.attach(_board(), doc=_doc(built_at=_stamp(2026, 9, 18)), now=TUE_AM)
    assert s["built_at_date"] == "2026-09-18"
    assert s["due_session"] == "2026-09-21" and s["stale"] is True


def test_a_weekend_read_of_fridays_sweep_is_not_stale():
    s = HA.attach(_board(), doc=_doc(built_at=_stamp(2026, 9, 25)), now=SAT_AM)
    assert s["last_session"] == "2026-09-25" and s["due_session"] == "2026-09-25"
    assert s["stale"] is False
    assert "2026-09-25" in s["stale_note"]


def test_a_utc_stamp_past_midnight_is_dated_on_his_clock_not_on_utcs():
    # 2026-09-22T00:10Z is still Monday evening in ET. A UTC comparison would
    # print a date that has not happened in his timezone.
    stamp = datetime(2026, 9, 22, 0, 10, tzinfo=UTC)
    s = HA.attach(_board(), doc=_doc(built_at=stamp), now=MON_EVE)
    assert s["last_session"] == "2026-09-21"
    assert s["built_at_date"] == "2026-09-21"
    assert s["built_at"].startswith("2026-09-22T00:10")     # UTC, as stored
    assert s["built_at_et"].startswith("2026-09-21T20:10")  # ET, as read
    assert s["stale"] is False
    assert "2026-09-22" not in s["stale_note"]


def test_without_the_session_calendar_staleness_is_unknown_never_guessed(monkeypatch):
    def _boom():
        raise ImportError("chart_maps.board is gone")

    monkeypatch.setattr(HA, "_board", _boom)
    s = HA.attach(_board(), doc=_doc(), now=TUE_AM)
    assert s["last_session"] is None and s["due_session"] is None
    assert s["stale"] is None and s["stale_note"] is None
    assert s["available"] is True         # the column still draws


# ---------------------------------------------------------------------------
# 14 — arithmetic invariants, over THIS board's unique names
# ---------------------------------------------------------------------------
def test_the_counts_add_up_and_count_each_symbol_once():
    body = _board()
    s = HA.attach(body, doc=_doc(), now=TUE_AM)
    assert sum(s["grades"].values()) == s["n_known"]
    assert s["n_known"] + s["n_blank"] == s["n"]
    assert sum(s["blank_reasons"].values()) == s["n_blank"]
    # every symbol appears at least twice in the payload (sector + industry,
    # and some also in a theme) and is counted exactly once
    rows = list(HA._name_rows(body))
    syms = [r["symbol"] for r in rows]
    assert len(rows) > len(set(syms))
    assert s["n"] == len(set(syms))


def test_the_counts_describe_the_board_not_the_store():
    """Ten rows in the store, three of them on the board."""
    rows = {s: _verdict("raided") for s in
            ["KRMN", "RCAT", "LASR", "ZZA", "ZZB", "ZZC", "ZZD", "ZZE", "ZZF", "ZZG"]}
    body = _board()
    s = HA.attach(body, doc=_doc(rows), now=TUE_AM)
    assert s["n_known"] == 3 and s["grades"]["raided"] == 3
    assert s["n_rows"] == 10                 # the sweep's own total, unchanged
    assert s["n_known"] + s["n_blank"] == s["n"]


# ---------------------------------------------------------------------------
# 15 — NEG the column is not a sort key
# ---------------------------------------------------------------------------
def test_amd_is_not_a_sort_key_and_an_amd_sort_is_demoted(monkeypatch):
    assert "amd" not in H.SORT_KEYS
    assert HA.ROW_KEY not in H.SORT_KEYS
    resp, body = _call_endpoint(monkeypatch, sort="amd", dir=H.DEFAULT_DIR,
                                names=25, basis=H.D1_CLOSE)
    assert resp.status_code == 200
    assert body["sorted_by"] == H.DEFAULT_SORT
    assert "amd" not in body["sortable"]


def test_with_no_member_table_the_column_simply_does_not_draw(monkeypatch):
    monkeypatch.setattr(A, "_members_table",
                        lambda: (None, {"reason": "no persisted rotation build yet"}))
    loop = asyncio.new_event_loop()
    try:
        resp = loop.run_until_complete(A.rotation_hottest(
            sort="amd", dir=H.DEFAULT_DIR, names=25, basis=H.D1_CLOSE))
    finally:
        loop.close()
    body = json.loads(bytes(resp.body).decode())
    assert resp.status_code == 200
    assert body["sectors"] == []
    assert "amd_summary" not in body        # no em-dash furniture on an empty board
    assert body["sorted_by"] == "amd"       # the raw echo, uncoerced, as it always was


# ---------------------------------------------------------------------------
# 16 — the coverage sentence is built, never typed
# ---------------------------------------------------------------------------
def test_the_coverage_sentence_is_built_from_this_requests_own_counts():
    body = _board()
    s = HA.attach(body, doc=_doc(), now=TUE_AM)
    note = s["coverage_note"]
    assert note.startswith(HA.LABEL)
    assert "%d of %d names" % (s["n_known"], s["n"]) in note
    assert "(%d not in the nightly sweep)" % s["n_blank"] in note
    for g, c in s["grades"].items():
        label = (TB.AMD_TEXT[g][0])[4:]
        if c:
            assert "%s %d" % (label, c) in note
        else:
            assert "%s %d" % (label, 0) not in note      # zeros are dropped
    assert HA.AMD_MEASURED["claim"] in note and "INVERTED" in note
    assert "ET" in note


def test_the_grade_labels_come_from_the_engines_table():
    for g in TB.AMD_GRADES:
        assert HA._grade_label(g) == TB.AMD_TEXT[g][0][4:]
    assert HA._grade_label("marked_up") == "marked up"


def test_a_sweep_with_no_date_says_so_rather_than_inventing_one():
    s = HA.attach(_board(), doc=_doc(built_at=None), now=TUE_AM)
    assert s["built_at"] is None and s["built_at_et"] is None
    assert s["stale"] is None
    assert "sweep date unknown" in s["coverage_note"]


# ---------------------------------------------------------------------------
# 17 — NEG the board's order is untouched
# ---------------------------------------------------------------------------
def test_attach_reorders_nothing():
    before = _board()
    after = copy.deepcopy(before)
    HA.attach(after, doc=_doc(), now=TUE_AM)
    assert [s["group"] for s in after["sectors"]] == \
           [s["group"] for s in before["sectors"]]
    assert [t["group"] for t in after["themes"]] == \
           [t["group"] for t in before["themes"]]
    for a, b in zip(after["sectors"], before["sectors"]):
        assert [i["group"] for i in a["industries"]] == \
               [i["group"] for i in b["industries"]]
        assert [r["symbol"] for r in a["names"]] == [r["symbol"] for r in b["names"]]
    for r in HA._name_rows(after):
        r.pop(HA.ROW_KEY)
    assert after == before


# ---------------------------------------------------------------------------
# 18 — ONE store read per attach, and the TTL cache holds it
# ---------------------------------------------------------------------------
def test_one_store_read_per_attach_and_one_per_ttl_window(monkeypatch):
    calls = {"n": 0}

    def _fake(db=None):
        calls["n"] += 1
        return _doc()

    monkeypatch.setattr(HA.TB, "stored", _fake)
    body = _board()
    assert len(body["sectors"]) == 3 and len(body["themes"]) == 2

    HA.attach(body, now=TUE_AM)
    assert calls["n"] == 1                       # ONE read for the whole board
    HA.attach(_board(), now=TUE_AM)
    assert calls["n"] == 1                       # inside the TTL: no second read
    HA.cache_clear()
    HA.attach(_board(), now=TUE_AM)
    assert calls["n"] == 2
    HA.attach(_board(), doc=_doc(), now=TUE_AM)
    assert calls["n"] == 2                       # `doc=` never touches the cache


def test_an_expired_entry_is_re_read(monkeypatch):
    calls = {"n": 0}
    monkeypatch.setattr(HA.TB, "stored",
                        lambda db=None: (calls.__setitem__("n", calls["n"] + 1)
                                         or _doc()))
    HA.attach(_board(), now=TUE_AM)
    assert calls["n"] == 1
    # The cache holds ONE whole entry under "entry" (rebound atomically), so
    # ageing it means rebinding that entry, not poking a top-level key.
    aged = dict(HA._index_cache["entry"])
    aged["ts"] = aged["ts"] - HA._AMD_TTL_SEC - 1
    HA._index_cache["entry"] = aged
    HA.attach(_board(), now=TUE_AM)
    assert calls["n"] == 2


def test_a_failed_read_is_never_cached(monkeypatch):
    """The `_members_table` rule: a Mongo blip must not blank the column for
    five minutes when the document is sitting right there."""
    calls = {"n": 0}

    def _fake(db=None):
        calls["n"] += 1
        return {} if calls["n"] == 1 else _doc()

    monkeypatch.setattr(HA.TB, "stored", _fake)
    s1 = HA.attach(_board(), now=TUE_AM)
    assert s1["available"] is False
    s2 = HA.attach(_board(), now=TUE_AM)
    assert calls["n"] == 2 and s2["available"] is True


# ---------------------------------------------------------------------------
# 19 / 20 — no invented number: the TTL and the sweep clock are the shipped ones
# ---------------------------------------------------------------------------
def test_the_cache_window_is_the_endpoints_own():
    assert HA._AMD_TTL_SEC == A._MEMBERS_TTL_SEC


def test_the_sweep_clock_is_read_off_the_shipped_crontab():
    cron = Path(__file__).resolve().parents[1] / "crontab"
    line = next(l for l in cron.read_text().splitlines()
                if "turning_bullish" in l and " warm" in l
                and not l.lstrip().startswith("#"))
    minute, hour = line.split()[0], line.split()[1]
    assert (int(hour), int(minute)) == (HA.SWEEP_ET_HOUR, HA.SWEEP_ET_MINUTE)
    assert re.search(r"\b1-5\b", line)          # weekdays only, as CRON_NOTE says
    assert "17:20" in HA.CRON_NOTE and "Mon-Fri" in HA.CRON_NOTE


# ---------------------------------------------------------------------------
# 21 — NEG symbol fates: a rename must not masquerade as a miss
# ---------------------------------------------------------------------------
def test_a_sweep_row_stored_under_a_former_ticker_still_reads():
    from sepa import symbols as SY
    old, (new, _eff, _why) = next(iter(SY.RENAMES.items()))
    assert SY.resolve(old) == new

    payload = _payload()
    by = payload[H.T.MEMBERS_KEY]["by_symbol"]
    by[new] = dict(by["KRMN"], sector="Energy", industry="Oil & Gas Integrated")
    payload[H.T.MEMBERS_KEY]["groups"]["sector"]["Energy"]["symbols"].append(new)
    body = H.build(payload)

    rows = {old: _verdict("raided"), "ZZZZ": _verdict("basing")}
    HA.attach(body, doc=_doc(rows), now=TUE_AM)
    cells = _cells(body)
    assert cells[new]["known"] is True and cells[new]["grade"] == "raided"
    assert cells["XOM"]["known"] is False              # a genuine miss still blanks
    assert cells["XOM"]["reason"] == "not_in_store"


def test_the_alias_never_overwrites_a_direct_hit():
    from sepa import symbols as SY
    old, (new, _eff, _why) = next(iter(SY.RENAMES.items()))
    ix = HA._index(_doc({new: _verdict("failed"), old: _verdict("raided")}))
    assert ix[new]["grade"] == "failed"         # the direct row wins
    assert ix[old]["grade"] == "raided"


def test_a_board_symbol_resolves_forward_too():
    from sepa import symbols as SY
    old, (new, _eff, _why) = next(iter(SY.RENAMES.items()))
    ix = {new: _verdict("stale")}
    assert HA._lookup(ix, old)["grade"] == "stale"
    assert HA._lookup(ix, "NOPE") is HA._MISS
    assert HA._lookup(ix, None) is HA._MISS


# ---------------------------------------------------------------------------
# 22 — the endpoint actually attaches it
# ---------------------------------------------------------------------------
def test_the_endpoint_attaches_the_amd_block(monkeypatch):
    monkeypatch.setattr(HA.TB, "stored", lambda db=None: _doc())
    resp, body = _call_endpoint(monkeypatch, sort=H.DEFAULT_SORT,
                                dir=H.DEFAULT_DIR, names=25, basis=H.D1_CLOSE)
    assert resp.status_code == 200
    s = body["amd_summary"]
    assert s["available"] is True and s["label"] == HA.LABEL
    assert s["sortable"] is False and s["coloured"] is False
    assert s["n_known"] + s["n_blank"] == s["n"]
    named = {r["symbol"]: r for sec in body["sectors"] for r in sec["names"]}
    assert named["KRMN"]["amd"]["text"].startswith("AMD raided")
    # what the BOARD cell prints, off the real endpoint: the same sentence
    # without the "AMD " the column header already says (Ajay 2026-09-22)
    assert named["KRMN"]["amd"]["short"] == "raided · 2d ago"
    assert s["grade_labels"]["raided"] == "raided"
    assert "NaN" not in json.dumps(body, ensure_ascii=False)


# ── the cache entry is rebound WHOLE, never cleared then refilled ───────────
def test_the_index_cache_holds_one_entry_that_is_rebound_atomically(monkeypatch):
    """clear()-then-update() left a window where a concurrent request saw an
    empty cache and paid for a second `TB.stored()`. One rebinding closes it."""
    HA.cache_clear()
    monkeypatch.setattr(HA.TB, "stored", lambda db=None: _doc())
    HA.attach(_board(), now=TUE_AM)
    assert set(HA._index_cache) == {"entry"}, "exactly one key, rebound whole"
    entry = HA._index_cache["entry"]
    for key in ("ts", "built_at", "ix", "meta"):
        assert key in entry


def test_NEGATIVE_a_store_MISS_is_never_cached(monkeypatch):
    HA.cache_clear()
    monkeypatch.setattr(HA.TB, "stored", lambda db=None: {})
    HA.attach(_board(), now=TUE_AM)
    assert HA._index_cache.get("entry") is None, (
        "a Mongo blip must not blank the column for the whole TTL"
    )


# ── the coverage sentence is BUILT from blank_reasons ───────────────────────
def test_the_coverage_sentence_names_the_refusal_it_counted():
    note = HA._coverage_note(10, 7, 3, {"raided": 7}, "2026-09-21T21:20",
                             {"not_in_store": 3, "no_verdict": 0,
                              "store_unavailable": 0})
    assert "3 not in the nightly sweep" in note


def test_NEGATIVE_a_swept_name_with_no_cycle_is_not_called_UNSWEPT():
    """The first version hardcoded "not in the nightly sweep" for every blank.
    That is a lie the first morning a swept name fails to produce a cycle."""
    note = HA._coverage_note(10, 7, 3, {"raided": 7}, "2026-09-21T21:20",
                             {"not_in_store": 0, "no_verdict": 3,
                              "store_unavailable": 0})
    assert "not in the nightly sweep" not in note
    assert "swept but the cycle could not be read" in note


def test_a_MIXED_blank_set_names_every_refusal():
    note = HA._coverage_note(10, 6, 4, {"raided": 6}, "2026-09-21T21:20",
                             {"not_in_store": 3, "no_verdict": 1,
                              "store_unavailable": 0})
    assert "3 not in the nightly sweep" in note
    assert "1 swept but the cycle could not be read" in note


def test_NEGATIVE_no_reason_breakdown_states_the_count_and_invents_nothing():
    note = HA._coverage_note(10, 7, 3, {"raided": 7}, "2026-09-21T21:20", {})
    assert "(3 blank)" in note
    assert "nightly sweep" not in note.split("(3 blank)")[0][-40:]


def test_a_board_with_no_blanks_carries_no_parenthetical():
    note = HA._coverage_note(10, 10, 0, {"raided": 10}, "2026-09-21T21:20",
                             {"not_in_store": 0, "no_verdict": 0,
                              "store_unavailable": 0})
    assert "(" not in note.split(" \u00b7 ")[0]


def test_every_REASON_has_a_phrase_for_the_sentence():
    """A new refusal cannot be added without deciding how it reads to him."""
    for reason in HA.REASONS:
        assert reason in HA._BLANK_PHRASE, reason
        assert HA._BLANK_PHRASE[reason].strip()


def test_the_built_at_stamp_declares_its_zone():
    meta = HA._doc_meta({"built_at": "2026-09-21T21:20:16.344000"})
    assert meta["built_at_utc"] is True, (
        "the raw stamp is naive UTC; without the marker a consumer reads it as local"
    )


def test_the_zone_marker_rides_WITH_the_raw_stamp_on_the_SERVED_block():
    """Verified live 2026-09-22: `_doc_meta` carried the marker but `summary()`
    dropped it, so the served block published a naive UTC `built_at` with no
    zone beside it. The surface reads `built_at_et`, but anything reading the
    raw stamp must find the marker in the same dict."""
    out = HA.attach(_board(), doc=_doc(), now=TUE_AM)
    assert out["built_at"], "the raw stamp is served for provenance"
    assert out["built_at_utc"] is True, (
        "the served block must carry the zone marker beside the raw stamp, "
        "not only on the internal meta dict"
    )


def test_NEGATIVE_the_marker_is_never_asserted_when_there_is_no_document():
    """An absent document must not publish a stamp that claims a zone."""
    out = HA.attach(_board(), doc={}, now=TUE_AM)
    assert out["built_at"] is None
    assert not out["built_at_utc"], (
        "no stamp, no zone claim \u2014 a bare True here would read as "
        "'we know when this was swept'"
    )


def test_the_frontend_fixture_carries_the_SENTENCE_THE_BOARD_SERVES():
    """The FE unit test hand-writes the blank sentence to assert on it. If the
    backend rewords a refusal and the fixture does not follow, the FE proves a
    sentence nobody ships. Pin them together."""
    import re
    root = Path(__file__).resolve().parents[2]
    fe = (root / "frontend" / "src" / "lib" / "hottestAmd.test.ts").read_text()
    block = fe.split("const notInStore", 1)[1].split("};", 1)[0]
    pieces = re.findall(r"'((?:[^'\\]|\\.)*)'", block.split("reason_text:", 1)[1])
    fixture = "".join(pieces)
    assert fixture == HA.REASON_TEXT["not_in_store"], (
        "the frontend fixture drifted from REASON_TEXT['not_in_store']"
    )


@pytest.mark.parametrize("reason", HA.REASONS)
def test_NEGATIVE_no_refusal_sentence_wears_the_words_of_a_REAL_read(reason):
    """"AMD no cycle" is what `TB.AMD_TEXT["none"]` lends a graded row. A blank
    must not wear those words even inside a denial \u2014 a hover skimmed at speed
    reads the words, not the negation."""
    text = HA.REASON_TEXT[reason].lower()
    assert "no cycle" not in text, reason
    assert "clean" not in text, reason


# ---------------------------------------------------------------------------
# 23 — the SHORT form the board cell prints (Ajay 2026-09-22)
# ---------------------------------------------------------------------------
# *"last column is hidded"* — he photographed the 🌀 AMD column clipped off the
# right edge of the 🔥 board, header reading "🌀 A" and cells reading "AM".
# Measured on that payload: 1,922 visible cells, EVERY ONE opening with the
# literal "AMD " that the column header already says, longest 26 characters.
# The cell now prints `short` and the hover keeps `text`. These tests exist to
# prove the short is the SAME sentence out of the SAME table — not a second
# wording engine, and not the frontend stripping a prefix.
def test_every_known_cell_serves_BOTH_forms_and_the_short_is_the_engines():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    known = {s: c for s, c in _cells(body).items() if c["known"]}
    assert known
    for sym, cell in known.items():
        assert set(cell) == set(HA._ROW_KEYS)
        assert cell["short"] == TB.verdict_short("amd", GRADED[sym])[0]
        assert cell["text"] == TB.verdict_text("amd", GRADED[sym])[0]
        # the LONG form is untouched: the hover and the 🌀 tab read it
        assert cell["title"].startswith("%s: %s." % (sym, cell["text"]))


def test_the_short_is_the_long_one_minus_the_word_the_header_already_prints():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    for cell in _cells(body).values():
        if not cell["known"]:
            continue
        assert cell["text"] == "AMD " + cell["short"]
        assert "AMD " not in cell["short"]
        assert len(cell["short"]) < len(cell["text"])


def test_EVERY_grade_produces_a_short_and_none_of_them_invents_a_word():
    """The guard: a grade added to `TB.AMD_GRADES` with no row in `AMD_TEXT`
    reaches the board wearing the fallback's words, so it must fail here."""
    for g in TB.AMD_GRADES:
        cell = HA.read_one("ZZZ", _verdict(g))
        assert cell["known"] is True and cell["grade"] == g
        short, text = cell["short"], cell["text"]
        assert short, g
        assert "AMD " not in short, g
        assert text == "AMD " + short, g
        # no vocabulary the long form does not already use
        for word in short.split():
            assert word in text.split(), (g, word)
        # and it is the ONE table's own word, not a second copy
        assert short.split(" · ")[0] == TB.AMD_TEXT[g][0][len("AMD "):], g


def test_the_short_carries_the_SAME_age_as_the_long_form_never_a_different_one():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    cells = _cells(body)
    assert cells["KRMN"]["short"] == "raided · 2d ago"
    assert cells["QLYS"]["short"] == "raided · today"
    assert cells["LASR"]["short"] == "raid stale · 7d ago"
    assert cells["KTOS"]["short"] == "base failed · 3d ago"
    assert cells["RCAT"]["short"] == "marked up · 5d ago"
    # a bare base and "no cycle" carry NO age in either form
    assert cells["ONDS"]["short"] == "basing"
    assert cells["TENB"]["short"] == "no cycle"


@pytest.mark.parametrize("reason", HA.REASONS)
def test_NEGATIVE_a_blank_cell_has_NO_short_and_still_serves_its_refusal(reason):
    """A refusal has no wording of its own to shorten. `short` is None, the
    board prints the em-dash, and the served reason is what he reads."""
    cell = HA.blank(reason)
    assert set(cell) == set(HA._ROW_KEYS)
    assert cell["short"] is None and cell["text"] is None
    assert cell["reason"] == reason
    assert cell["reason_text"] == HA.REASON_TEXT[reason]


def test_NEGATIVE_the_blanks_on_a_real_board_carry_no_short_either():
    body = _board()
    HA.attach(body, doc=_doc(), now=TUE_AM)
    blanks = [c for c in _cells(body).values() if not c["known"]]
    assert blanks, "this board must contain a name the sweep never saw"
    for cell in blanks:
        assert cell["short"] is None
        low = json.dumps(cell, ensure_ascii=False).lower()
        assert "no cycle" not in low and "clean" not in low


def test_NEGATIVE_an_ungradeable_verdict_has_no_short_to_borrow():
    """`TB.verdict_short` falls back to the table's "none" row exactly as
    `verdict_text` does — so "no cycle" is a real read's word, and the gate in
    `read_one` is what keeps it off an ungradeable row. Prove both halves."""
    assert TB.verdict_short("amd", {"grade": "wat"})[0] == "no cycle"
    for bad in ({"grade": "wat"}, {"grade": None}, {}, {"base_bars": 3}):
        cell = HA.read_one("BBAI", bad)
        assert cell["known"] is False and cell["short"] is None
        assert "no cycle" not in json.dumps(cell, ensure_ascii=False)


def test_an_empty_document_blanks_the_short_on_every_row():
    body = _board()
    HA.attach(body, doc={}, now=TUE_AM)
    for cell in _cells(body).values():
        assert cell["short"] is None and cell["known"] is False
        assert cell["reason"] == "store_unavailable"


def test_the_summary_SERVES_the_short_wording_so_nobody_types_it_twice():
    s = HA.attach(_board(), doc=_doc(), now=TUE_AM)
    labels = s["grade_labels"]
    assert list(labels) == list(TB.AMD_GRADES)
    assert labels == {"marked_up": "marked up", "raided": "raided",
                      "stale": "raid stale", "failed": "base failed",
                      "basing": "basing", "none": "no cycle"}
    for g, label in labels.items():
        # the same word the cell prints, and the same word the histogram counts
        assert HA.read_one("ZZZ", _verdict(g))["short"].startswith(label)
        if s["grades"].get(g):
            assert "%s %d" % (label, s["grades"][g]) in s["coverage_note"]


def test_the_unavailable_block_still_carries_the_wording_table():
    """`unavailable()` runs when everything else already failed. A consumer
    reading `grade_labels` must not meet a missing key there."""
    s = HA.unavailable()
    assert s["available"] is False
    assert s["grade_labels"] == {g: HA._grade_label(g) for g in TB.AMD_GRADES}


# ---------------------------------------------------------------------------
# 24 — the WIDTH story: no estimated number, and no column of his is written
#      off by an agent (review findings 2/3/4, 2026-09-22)
# ---------------------------------------------------------------------------
# The change that moved this column out of last place shipped with an
# arithmetic width model — a table "floor", an overflow, a saving, a per-column
# width for Next ER — computed from measured CHARACTER counts and ASSUMED
# per-character advances, with no browser ever opened. Rule #1 does not take a
# model for a measurement. Worse, the same paragraph used those numbers to
# decide that Next ER was the column he could afford to lose; which of HIS
# columns gives way on a narrow window is a board decision, not a reviewer's.
#
# These guards pin the correction so it cannot quietly come back: no estimated
# px figure on either page or in the component, no doc deciding one of his
# columns is expendable, the two real questions OPEN on the his-call list, and
# the phone layout left un-picked in the CSS.

_ROOT = Path(__file__).resolve().parents[2]
_DOC_FE = _ROOT / "docs" / "rotation" / "hottest_expand_all_2026_09_22.md"
_DOC_BE = _ROOT / "docs" / "rotation" / "hottest_amd_column_2026_09_22.md"
_TSX = _ROOT / "frontend" / "src" / "components" / "HottestSectors.tsx"
_CSS = _ROOT / "frontend" / "src" / "styles.css"

# Every figure the arithmetic model produced. None was measured; none may be
# printed, not even inside a sentence that disowns it — a skimmer reads the
# number, not the disclaimer.
_MODELLED_FIGURES = ("1,074px", "1074px", "943px", "131px", "107px",
                     "176px", "151px", "~25px", "19% of the deficit")

# Sentences that hand one of HIS columns to the bin.
_VERDICTS_ON_HIS_COLUMNS = ("right one to sacrifice", "one to sacrifice",
                            "look up on the ticker page", "second-widest",
                            "takes the clip")


def _media_720_block() -> str:
    """The `@media (max-width: 720px)` block that owns the 🔥 table."""
    css = _CSS.read_text(encoding="utf-8")
    anchor = css.index(".hs-table { min-width: 760px")
    start = css.rindex("@media (max-width: 720px) {", 0, anchor)
    depth, i = 0, start
    while i < len(css):
        if css[i] == "{":
            depth += 1
        elif css[i] == "}":
            depth -= 1
            if depth == 0:
                return css[start:i + 1]
        i += 1
    raise AssertionError("the 720px media block is unterminated")


@pytest.mark.parametrize("path", [_DOC_FE, _DOC_BE, _TSX])
def test_SOURCE_GUARD_no_MODELLED_px_figure_survives_on_any_surface(path):
    """Rule #1: a number nobody measured does not get to be printed with a
    tilde in front of it. The character counts stay — those came off the live
    payload — but every px figure in the width model is gone."""
    text = path.read_text(encoding="utf-8")
    for fig in _MODELLED_FIGURES:
        assert fig not in text, "%s still quotes the modelled %s" % (
            path.name, fig)


@pytest.mark.parametrize("path", [_DOC_FE, _DOC_BE, _TSX])
def test_SOURCE_GUARD_nothing_here_decides_which_of_HIS_columns_is_expendable(
        path):
    text = path.read_text(encoding="utf-8").lower()
    for phrase in _VERDICTS_ON_HIS_COLUMNS:
        assert phrase not in text, "%s still writes off a column: %r" % (
            path.name, phrase)


def test_the_width_question_is_OPEN_on_the_his_call_list_as_a_board_decision():
    doc = _DOC_FE.read_text(encoding="utf-8")
    # one line, so a wrapped sentence still reads as the sentence it is
    block = " ".join(doc.split("## 4. His call, in one list", 1)[1].split())
    assert "Which column gives way" in block
    assert "OPEN" in block and "board decision" in block
    # named as candidates for HIM to pick from, never as a decision taken
    assert "Next ER" in block
    # and the move is described for what it changed: the position, not the fit
    assert "scroll POSITION" in block or "**scroll position**" in doc
    assert "does not make the table fit" in doc


def test_the_docs_name_the_PRE_OPEN_day_header_as_the_WIDEST_state():
    """The model that was here never accounted for the day column's non-live
    header, which is the state this board is in every time he opens it before
    the open — `d1.live` false on every closed-session path, the ☀️
    `basis=premarket` board included. Both pages have to say so, or the next
    person measures the narrow case and calls it the answer."""
    for path in (_DOC_FE, _DOC_BE):
        doc = path.read_text(encoding="utf-8")
        assert "Last close YYYY-MM-DD" in doc, path.name
        assert "d1.live" in doc, path.name
        assert "premarket" in doc, path.name


def test_the_PRE_OPEN_header_claim_is_TRUE_of_the_code_it_cites():
    """A doc sentence about `d1Label` is worth nothing if `d1Label` changed.
    Pin the two halves the sentence rests on."""
    tsx = _TSX.read_text(encoding="utf-8")
    assert "Last close ${day}" in tsx and "'Last close'" in tsx
    assert "if (d?.d1?.live) return 'Today';" in tsx
    hot = (_ROOT / "backend" / "rotation" / "hottest.py").read_text(
        encoding="utf-8")
    assert '"live": False' in hot or "'live': False" in hot


def test_the_PHONE_question_is_OPEN_and_names_BOTH_options():
    block = " ".join(_DOC_FE.read_text(encoding="utf-8").split(
        "## 4. His call, in one list", 1)[1].split())
    assert "What a phone shows" in block and "OPEN" in block
    # (a) wrap it there, (b) do not draw it there — both named, neither taken
    assert "white-space: normal" in block
    assert "do not draw the column on a phone" in block
    assert "Shipped as neither" in block


def test_NEGATIVE_the_phone_layout_was_NOT_picked_silently_in_the_CSS():
    """The 🌀 column sits between the name and the ranked legs now, so on a
    phone every leg is one column further right. Which columns a phone shows is
    HIS call (item 9) — so the 720px block may adjust the cell's SIZE and
    nothing else. A `display: none` or a `white-space: normal` landing here
    without item 9 being answered is the silent pick this guard exists to
    catch."""
    block = _media_720_block()
    assert ".hs-amd { font-size: 0.70rem; }" in block
    amd_rules = re.findall(r"\.hs-amd[^{]*\{([^}]*)\}", block)
    assert amd_rules, "the 720px block no longer carries a .hs-amd rule"
    for body in amd_rules:
        low = body.lower()
        assert "display" not in low, body
        assert "white-space" not in low, body
        assert "visibility" not in low, body


def test_NEGATIVE_the_720px_block_hides_no_column_of_the_HOTTEST_table():
    block = _media_720_block()
    assert "display: none" not in block and "display:none" not in block
