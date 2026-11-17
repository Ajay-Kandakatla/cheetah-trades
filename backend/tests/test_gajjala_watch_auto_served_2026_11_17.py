"""🤖 Gajjala's Watch — the served auto section: payload rows / board block + the DELETE route (spec ggwauto §3.4-3.5,
WP-B, 2026-11-17).

Ajay 2026-11-17, verbatim: "Can you add more stocks in to watch list basically I need portentials from Gajjals's 1 min
and regular and also Audited potentials with good volume to Watchlist on an interval.. Remove as they are not
progressing"

The auto ENGINE (WP-A, `chart_maps.gajjala_watch.auto`) is injected as a stub through sys.modules — the WP-A/WP-B seam
is the §3.2 signatures `read_doc(cs)`, `dismiss(symbol, *, by)`, `rules_line()`. Until WP-A lands its constants, the
`consts` fixture fills ONLY the missing `C.AUTO_*` names from the spec §3.1 definitions (by name off GC / variant);
once they exist the fixture changes nothing.

NEGATIVES: a stored order is never re-sorted (neither alphabetical nor by volume); his rows carry `auto: null`; an
unknown volume source serves no volume words; `leaving_text` null while `dropped_since` is null; an unlisted `?symbols=`
name is still never read; another session's doc serves no auto row; an unreadable / raising / missing engine serves
`unreadable` + his rows — never `error`, never an empty board; auto names never fill his ➕ cap; a fold-duplicate of his
name is his; a non-owner GET reads nothing; a non-owner DELETE touches neither list; a raising dismiss keeps the store's
answer; no digit typed in a served word; the admin email never appears.
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
import types
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala_watch import api as API
from chart_maps.gajjala_watch import colls as CO
from chart_maps.gajjala_watch import constants as C
from chart_maps.gajjala_watch import payload as PL
from chart_maps.gajjala_watch import store as ST
from tests.test_gajjala_watch_api_2026_11_15 import (FRI_IN, OTHER, OWNER, SESSION, SUN, RecColl, _doc, _strict)

AUTO_MOD = "chart_maps.gajjala_watch.auto"
AUTO_STUB = "STUB-AUTO-RULES-LINE"
YESTERDAY = "2026-11-12"


def _spec_constants() -> dict:
    """Spec §3.1 by NAME (only used for a name WP-A has not landed yet)."""
    from chart_maps.gajjala import variant as V
    cap = GC.GG_WATCH_N
    return {"AUTO_DOC_ID": "auto", "AUTO_MAX_SYMBOLS": cap,
            "AUTO_SOURCES": (V.GG5.key, V.GG1.key, V.GGA.key),
            "AUTO_SOURCE_WORDS": {V.GG5.key: "🚩 5-min", V.GG1.key: "🚩 1-min", V.GGA.key: "🧪"},
            "AUTO_READ_SOURCES": (V.GG5.key, V.GG1.key),
            "AUTO_MIN_VOLUME": GC.K11_MIN_SESSION_VOLUME, "AUTO_VOLUME_SOURCES": ("scan", "tracker"),
            "AUTO_DROP_GRACE_SEC": GC.PASS_CADENCE_SEC, "AUTO_REMOVED_SHOWN": cap,
            "AUTO_PUSH_MODES": GC.FADE_CROSS_PUSH_MODES, "AUTO_PUSH_MODE": GC.FADE_CROSS_PUSH_MODES[0],
            "AUTO_HELD_REASON": "suppressed_auto", "AUTO_TAG": "🤖"}


@pytest.fixture(autouse=True)
def consts(monkeypatch):
    for name, v in _spec_constants().items():
        if not hasattr(C, name):
            monkeypatch.setattr(C, name, v, raising=False)
    if C.AUTO_HELD_REASON not in C.HELD_REASONS:
        monkeypatch.setattr(C, "HELD_REASONS", tuple(C.HELD_REASONS) + (C.AUTO_HELD_REASON,))


class StubAuto(types.SimpleNamespace):
    """The WP-A engine stub: `read_doc` reads `_id = C.AUTO_DOC_ID` off the list collection ({} missing, None on a
    fault); `dismiss` records its calls and answers like §3.2 (dismissed when the name is an entry, else absent)."""

    def __init__(self):
        super().__init__(calls=[], reads=0, raise_read=False, raise_dismiss=False)

    def read_doc(self, cs):
        self.reads += 1
        if self.raise_read:
            raise RuntimeError("engine blew up")
        try:
            return cs["list"].find_one({"_id": C.AUTO_DOC_ID}) or {}
        except Exception:                                      # noqa: BLE001
            return None

    def dismiss(self, symbol, *, by=None, db=None, now=None):
        self.calls.append((symbol, by))
        if self.raise_dismiss:
            raise RuntimeError("dismiss blew up")
        sym = ST.normalize(symbol)
        if sym is None:
            return {"state": "absent", "symbols": CO.owner_symbols(db), "symbol": None,
                    "text": PL.store_text("absent", None)}
        cs = CO.colls(db)
        adoc = cs["list"].find_one({"_id": C.AUTO_DOC_ID}) or {}
        ents = [e for e in adoc.get("entries", []) if CO.fold(e.get("symbol")) != CO.fold(sym)]
        state = "dismissed" if len(ents) != len(adoc.get("entries", [])) else "absent"
        if adoc:
            adoc["entries"] = ents
            cs["list"].docs[C.AUTO_DOC_ID] = adoc
        return {"state": state, "symbols": CO.owner_symbols(db), "symbol": sym, "text": PL.store_text(state, sym)}

    def rules_line(self):
        return AUTO_STUB


@pytest.fixture(autouse=True)
def stubs(monkeypatch):
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.build",
                        types.SimpleNamespace(uptrend_rule=lambda: "STUB-UPTREND-RULE"))
    monkeypatch.setitem(sys.modules, "chart_maps.gajjala_watch.cross_alerts",
                        types.SimpleNamespace(rules_line=lambda: "STUB-PUSH-TEXT"))
    eng = StubAuto()
    monkeypatch.setitem(sys.modules, AUTO_MOD, eng)
    return eng


def _entry(sym, *, sources=("gajjala", "gga"), setup="kiss_fly", kind="building", volume=2_000_000.0,
           volume_source="scan", added_et="10:05", dropped_since=None):
    return {"symbol": sym, "sources": list(sources), "setup": setup, "kind": kind, "volume": volume,
            "volume_source": volume_source, "float_shares": 5_000_000.0,
            "added_at": datetime(2026, 11, 13, 15, 5), "added_et": added_et, "dropped_since": dropped_since}


def _removal(i, *, reason="not_progressing", text="✖️ stop printed", at_et=None):
    return {"symbol": f"R{chr(65 + i % 26)}{chr(65 + i // 26)}", "at": datetime(2026, 11, 13, 14, i),
            "at_et": at_et if at_et is not None else f"09:{i:02d}", "reason": reason, "state": "stop_printed",
            "source": "gajjala", "text": text}


def _db(manual, entries=(), *, session=SESSION, removed=(), auto=True):
    lst = [{"_id": C.LIST_DOC_ID, "symbols": list(manual)}]
    if auto:
        lst.append({"_id": C.AUTO_DOC_ID, "session": session, "rev": 4, "entries": list(entries),
                    "removed": list(removed), "dismissed": []})
    return {C.COLL_LIST: RecColl(lst), C.COLL_TILES: RecColl(), C.COLL_ALERTS: RecColl(), C.COLL_STATE: RecColl()}


def _route_session() -> str:
    """The session the ROUTE serves (it builds at the wall clock) — the auto doc must carry it."""
    from zoneinfo import ZoneInfo
    return PL._session_of(datetime.now(ZoneInfo("America/New_York")))[0].isoformat()[:10]


def _syms(out):
    return [r["symbol"] for r in out["rows"]]


# ── rows: his first, then the auto rows in the STORED order ──────────────────────────────────────────────────────
def test_rows_are_his_then_auto_in_the_stored_order_never_resorted():
    stored = [_entry("MMM", volume=1_500_000.0), _entry("ZZT", volume=9_000_000.0), _entry("AAA", volume=3_000_000.0)]
    out = PL.build(FRI_IN, db=_db(["OMH", "NVDA"], stored))
    assert _syms(out) == ["OMH", "NVDA", "MMM", "ZZT", "AAA"]
    autos = _syms(out)[2:]
    assert autos != sorted(autos)                                                     # NEG: not alphabetical
    by_vol = [e["symbol"] for e in sorted(stored, key=lambda e: -e["volume"])]
    assert autos != by_vol                                                            # NEG: not by volume
    assert out["symbols"] == ["OMH", "NVDA"]                                          # `symbols` = HIS list
    assert out["auto"]["symbols"] == ["MMM", "ZZT", "AAA"] and out["auto"]["n"] == 3


def test_a_manual_row_has_auto_null_an_auto_row_the_full_block():
    db = _db(["OMH"], [_entry("XXII", sources=("gajjala", "gga"), kind="armed")])
    db[C.COLL_TILES].docs["XXII"] = _doc("XXII")
    out = PL.build(FRI_IN, db=db)
    his, auto = out["rows"]
    assert his["auto"] is None
    a = auto["auto"]
    assert set(a) == {"tag", "sources", "source_words", "text", "volume_text", "volume_source", "added_et",
                      "added_text", "leaving_text", "remove_title"}
    assert a["tag"] == C.AUTO_TAG and a["sources"] == ["gajjala", "gga"]
    assert a["source_words"] == [C.AUTO_SOURCE_WORDS["gajjala"], C.AUTO_SOURCE_WORDS["gga"]]
    from chart_maps.gajjala import potential as PT
    assert a["text"] == PL.AUTO_ROW_TEXT.format(tag=C.AUTO_TAG, sources=" · ".join(a["source_words"]),
                                                setup="💋 EMA Kiss & Fly", kind=PT.KIND_LABEL["armed"])
    assert a["added_et"] == "10:05" and a["added_text"] == PL.AUTO_ADDED_TEXT.format(at_et="10:05")
    assert a["remove_title"] == PL.AUTO_REMOVE_TITLE.format(sym="XXII")
    assert a["leaving_text"] is None
    for k in ("tag", "text", "volume_text", "volume_source", "added_et", "added_text", "remove_title"):
        assert isinstance(a[k], str) and a[k].strip(), k
    assert auto["state"] == "ok" and len(auto["frames"]) == 3                         # the same tile row as his


def test_the_row_text_for_a_one_minute_only_potential():
    out = PL.build(FRI_IN, db=_db([], [_entry("LGHL", sources=("gajjala_1m",), setup="horizontal_fade")]))
    a = out["rows"][0]["auto"]
    assert a["sources"] == ["gajjala_1m"] and a["source_words"] == [C.AUTO_SOURCE_WORDS["gajjala_1m"]]
    assert "➖ Horizontal Fade" in a["text"] and a["text"].startswith(C.AUTO_TAG + " auto · ")


def test_NEGATIVE_an_unknown_source_is_not_served():
    a = PL.build(FRI_IN, db=_db([], [_entry("ABC", sources=("gajjala", "made_up"))]))["rows"][0]["auto"]
    assert a["sources"] == ["gajjala"] and "made_up" not in json.dumps(a)


def test_volume_words_by_volume_source():
    from chart_maps.gajjala import tab
    rows = PL.build(FRI_IN, db=_db([], [_entry("SCN", volume=2_000_000.0, volume_source="scan"),
                                        _entry("TRK", volume=1_123_834.0, volume_source="tracker"),
                                        _entry("UNK", volume=3_000_000.0, volume_source="rvol"),
                                        _entry("NOV", volume=None, volume_source="scan")]))["rows"]
    a = {r["symbol"]: r["auto"] for r in rows}
    assert a["SCN"]["volume_text"] == PL.AUTO_VOL_TEXT["scan"].format(vol=tab._compact(2_000_000.0)) == "vol 2.0M"
    assert a["TRK"]["volume_text"] == PL.AUTO_VOL_TEXT["tracker"].format(vol=tab._compact(1_123_834.0))
    assert a["TRK"]["volume_text"].endswith("(pass number)") and a["TRK"]["volume_source"] == "tracker"
    assert a["SCN"]["volume_text"] != a["TRK"]["volume_text"].replace("1.1M", "2.0M")    # the two wordings differ
    assert a["UNK"]["volume_text"] is None and a["UNK"]["volume_source"] is None       # NEG: unknown source
    assert a["NOV"]["volume_text"] is None                                             # NEG: no number, no words


def test_leaving_text_only_while_dropped_since_is_set():
    since = datetime(2026, 11, 13, 15, 22)                                             # naive = UTC = 10:22 ET
    rows = PL.build(FRI_IN, db=_db([], [_entry("KEEP"), _entry("LEAV", dropped_since=since)]))["rows"]
    assert rows[0]["auto"]["leaving_text"] is None                                     # NEG: dropped_since null
    assert rows[1]["auto"]["leaving_text"] == PL.AUTO_LEAVING_TEXT.format(since_et="10:22")


def test_added_et_falls_back_to_the_stored_stamp():
    e = _entry("ABC", added_et=None)
    a = PL.build(FRI_IN, db=_db([], [e]))["rows"][0]["auto"]
    assert a["added_et"] == "10:05" and a["added_text"] == "added 10:05 ET"


# ── the pending poll / `only` ─────────────────────────────────────────────────────────────────────────────────────
def test_the_symbols_poll_serves_an_auto_name_and_still_drops_an_unlisted_one():
    db = _db(["OMH"], [_entry("XXII")])
    out = PL.build(FRI_IN, db=db, only=["XXII", "ZZZZ"])
    assert _syms(out) == ["XXII"] and out["rows"][0]["auto"]["tag"] == C.AUTO_TAG
    assert db[C.COLL_TILES].finds == [{"_id": {"$in": ["XXII"]}}]
    assert "ZZZZ" not in json.dumps(db[C.COLL_TILES].finds)                            # NEG: never read


def test_a_pending_auto_row_turns_the_poll_keys_on():
    db = _db(["OMH"], [_entry("XXII")])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    out = PL.build(FRI_IN, db=db)
    assert out["rows"][1]["state"] == "pending" and out["pending_poll_sec"] == GC.ON_DEMAND_POLL_SEC


def test_the_route_poll_includes_auto_names(monkeypatch):
    db = _db(["OMH"], [_entry("XXII")], session=_route_session())
    c = _client(monkeypatch, db)
    body = _strict(c.get(C.API_PATH + "?symbols=xxii,ZZZZ", headers={"X-User-Email": OWNER}).text)
    assert [r["symbol"] for r in body["rows"]] == ["XXII"] and body["symbols"] == ["OMH"]


# ── session / fault handling ──────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_an_auto_doc_of_another_session_serves_no_auto_row():
    removed = [_removal(i) for i in range(3)]
    out = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")], session=YESTERDAY, removed=removed))
    assert _syms(out) == ["OMH"]
    a = out["auto"]
    assert a["state"] == "ok" and a["n"] == 0 and a["symbols"] == [] and a["removed"] == [] and a["removed_total"] == 0


def test_no_auto_doc_is_an_empty_ok_section():
    out = PL.build(FRI_IN, db=_db(["OMH"], auto=False))
    assert _syms(out) == ["OMH"] and out["auto"]["state"] == "ok" and out["auto"]["n"] == 0


@pytest.mark.parametrize("how", ["fault", "raise", "missing_module"])
def test_NEGATIVE_an_unreadable_auto_doc_is_unreadable_never_error_never_empty(stubs, monkeypatch, how):
    db = _db(["OMH", "NVDA"], [_entry("XXII")])
    db[C.COLL_TILES].docs["OMH"] = _doc("OMH")
    if how == "fault":
        monkeypatch.setattr(stubs, "read_doc", lambda cs: None)
    elif how == "raise":
        stubs.raise_read = True
    else:
        monkeypatch.setitem(sys.modules, AUTO_MOD, None)                              # import → ImportError
    out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok" and out["state"] != "error"
    assert _syms(out) == ["OMH", "NVDA"] and out["rows"][0]["state"] == "ok"          # his rows intact
    a = out["auto"]
    assert a["state"] == "unreadable" and a["text"] == PL.AUTO_UNREADABLE_TEXT and a["n"] == 0
    assert a["empty_text"] is None                                                    # NEG: not "no potentials"
    assert out["empty_text"] == PL.empty_text() and out["symbols"] == ["OMH", "NVDA"]


def test_NEGATIVE_a_list_fault_on_the_auto_read_alone_keeps_his_board(stubs, monkeypatch):
    db = _db(["OMH"], [_entry("XXII")])
    calls = {"n": 0}
    real = db[C.COLL_LIST].find_one

    def _second_fails(q=None, projection=None):
        calls["n"] += 1
        if q == {"_id": C.AUTO_DOC_ID}:
            raise RuntimeError("mongo blip")
        return real(q, projection)
    monkeypatch.setattr(db[C.COLL_LIST], "find_one", _second_fails)
    out = PL.build(FRI_IN, db=db)
    assert out["state"] == "ok" and _syms(out) == ["OMH"] and out["auto"]["state"] == "unreadable"


def test_empty_text_only_when_none_and_in_window():
    assert PL.build(FRI_IN, db=_db(["OMH"]))["auto"]["empty_text"] == \
        PL.AUTO_EMPTY_TEXT.format(floor=int(C.AUTO_MIN_VOLUME))
    assert PL.build(SUN, db=_db(["OMH"]))["auto"]["empty_text"] is None                 # NEG: out of window
    assert PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")]))["auto"]["empty_text"] is None   # NEG: n > 0


def test_NEGATIVE_a_fold_duplicate_of_his_name_is_his():
    out = PL.build(FRI_IN, db=_db(["BRK.B"], [_entry("BRK-B"), _entry("XXII"), _entry("xxii")]))
    assert _syms(out) == ["BRK.B", "XXII"]
    assert out["rows"][0]["auto"] is None and out["rows"][1]["auto"]["tag"] == C.AUTO_TAG
    assert out["auto"]["n"] == 1 and out["auto"]["symbols"] == ["XXII"]


# ── the board's auto block ────────────────────────────────────────────────────────────────────────────────────────
def test_board_block_words_and_numbers_from_the_constants():
    out = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII"), _entry("LGHL", sources=("gajjala_1m",))]))
    a = out["auto"]
    assert set(a) == {"state", "cap", "n", "symbols", "title", "hint", "empty_text", "text", "removed",
                      "removed_total", "removed_title", "push_mode"}
    assert a["cap"] == C.AUTO_MAX_SYMBOLS and a["n"] == 2 and a["push_mode"] == C.AUTO_PUSH_MODE
    assert a["title"] == PL.AUTO_TITLE_TEXT.format(n=2, cap=C.AUTO_MAX_SYMBOLS)
    h = a["hint"]
    assert f"{int(C.AUTO_MIN_VOLUME):,}" in h and f"up to {C.AUTO_MAX_SYMBOLS}." in h
    assert f"for {int(C.AUTO_DROP_GRACE_SEC) // 60} minutes" in h
    for k in C.AUTO_SOURCES:
        assert C.AUTO_SOURCE_WORDS[k] in h
    assert "{" not in h and "}" not in h and h.endswith("UNMEASURED.")
    assert a["text"] is None and a["state"] == "ok"


def test_removed_strip_serves_the_newest_cap_newest_first_with_the_total():
    removed = [_removal(i, text=f"✖️ stop printed #{i}") for i in range(25)]
    out = PL.build(FRI_IN, db=_db(["OMH"], [_entry("XXII")], removed=removed))
    a = out["auto"]
    assert a["removed_total"] == 25 and len(a["removed"]) == C.AUTO_REMOVED_SHOWN == 18
    want = list(reversed(removed))[:C.AUTO_REMOVED_SHOWN]
    assert [r["symbol"] for r in a["removed"]] == [r["symbol"] for r in want]          # newest first
    assert a["removed"][0]["at_et"] == "09:24" and a["removed"][-1]["at_et"] == "09:07"
    for r, src in zip(a["removed"], want):
        assert set(r) == {"symbol", "at_et", "reason", "state", "text", "text_full"}
        assert r["text"] == src["text"]
        assert r["text_full"] == PL.AUTO_REMOVED_TEXT.format(symbol=src["symbol"], at_et=src["at_et"], text=src["text"])
    assert a["removed_title"] == PL.AUTO_REMOVED_TITLE.format(n=25) and "25" in a["removed_title"]


def test_NEGATIVE_a_short_removed_list_is_served_whole():
    out = PL.build(FRI_IN, db=_db([], [], removed=[_removal(0), _removal(1)]))
    assert out["auto"]["removed_total"] == 2 and [r["at_et"] for r in out["auto"]["removed"]] == ["09:01", "09:00"]


def test_removed_text_falls_back_by_reason_and_at_et_from_the_stamp():
    removed = [_removal(0, reason="on_your_list", text=None, at_et=""), _removal(1, reason="dismissed", text="  ")]
    out = PL.build(FRI_IN, db=_db([], [], removed=removed))["auto"]["removed"]
    assert out[0]["text"] == PL.AUTO_DISMISSED_TEXT
    assert out[1]["text"] == PL.AUTO_ON_LIST_TEXT and out[1]["at_et"] == "09:00"       # 14:00 UTC → 09:00 ET
    assert out[1]["text_full"].endswith(PL.AUTO_ON_LIST_TEXT)


@pytest.mark.parametrize("n_manual,full", [(C.MAX_SYMBOLS, True), (C.MAX_SYMBOLS - 1, False)])
def test_NEGATIVE_full_is_his_cap_only_auto_names_never_fill_it(n_manual, full):
    manual = [f"M{chr(65 + i)}" for i in range(n_manual)]
    out = PL.build(FRI_IN, db=_db(manual, [_entry(f"Z{chr(65 + i)}") for i in range(5)]))
    assert out["full"] is full and len(out["rows"]) == n_manual + 5 and out["auto"]["n"] == 5
    assert out["symbols"] == manual and out["max_symbols"] == C.MAX_SYMBOLS


def test_held_text_for_the_auto_reason_has_words():
    assert C.AUTO_HELD_REASON in PL.HELD_TEXT
    t = PL.held_text(C.AUTO_HELD_REASON)
    assert isinstance(t, str) and t.startswith("🔕") and "auto" in t
    assert set(PL.HELD_TEXT) == set(C.HELD_REASONS)


def test_info_auto_text_served_once():
    db = _db(["OMH"], [_entry("XXII"), _entry("LGHL")])
    out = PL.build(FRI_IN, db=db)
    assert out["info"]["auto_text"] == AUTO_STUB
    assert json.dumps(out, default=str).count(AUTO_STUB) == 1                         # NEG: never per row


def test_NEGATIVE_a_raising_rules_line_is_none_and_the_board_answers(stubs, monkeypatch):
    monkeypatch.setattr(stubs, "rules_line", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    out = PL.build(FRI_IN, db=_db(["OMH"]))
    assert out["state"] == "ok" and out["info"]["auto_text"] is None


def test_store_text_dismissed():
    assert PL.store_text("dismissed", "XXII") == "🤖 XXII removed — not added again today"


def test_source_guard_no_digit_typed_in_the_auto_words():
    bad = []
    for name, v in vars(PL).items():
        if not (name.startswith("AUTO_") or name == "_REMOVED_FALLBACK") or not isinstance(v, (str, dict)):
            continue
        for s in (v.values() if isinstance(v, dict) else [v]):
            words = re.sub(r"\{[^}]*\}", "", s)
            words = re.sub(r"\bK[0-9]+\b", "", words)
            if re.search(r"[0-9]", words):
                bad.append((name, s))
    assert bad == []
    assert PL.HELD_TEXT["suppressed_auto"] and not re.search(r"[0-9]", PL.HELD_TEXT["suppressed_auto"])


# ── routes ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _client(monkeypatch, db):
    import ollama_chat.api as OA
    monkeypatch.setattr(OA, "is_primary_admin", lambda e: (e or "").strip().lower() == OWNER)
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)                      # no build child
    monkeypatch.setenv(C.ENV_ENABLED, "1")
    app = FastAPI()
    app.include_router(API.router)
    return TestClient(app)


def test_delete_on_an_auto_name_answers_dismissed_with_his_symbols(monkeypatch, stubs):
    db = _db(["OMH", "NVDA"], [_entry("XXII")])
    c = _client(monkeypatch, db)
    r = c.delete(C.API_PATH + "/symbols/xxii", headers={"X-User-Email": OWNER})
    out = r.json()
    assert r.status_code == 200 and out["state"] == "dismissed" and out["symbol"] == "XXII"
    assert out["symbols"] == ["OMH", "NVDA"] and set(out) == {"state", "symbols", "symbol", "text"}
    assert out["text"] == PL.store_text("dismissed", "XXII")
    assert stubs.calls == [("xxii", OWNER)]
    assert db[C.COLL_LIST].docs[C.LIST_DOC_ID]["symbols"] == ["OMH", "NVDA"]           # his list untouched


def test_delete_on_his_name_removes_and_still_calls_dismiss(monkeypatch, stubs):
    db = _db(["OMH", "NVDA"], [_entry("XXII")])
    c = _client(monkeypatch, db)
    out = c.delete(C.API_PATH + "/symbols/OMH", headers={"X-User-Email": OWNER}).json()
    assert out["state"] == "removed" and out["symbols"] == ["NVDA"]
    assert stubs.calls == [("OMH", OWNER)]                                            # blocks a re-add today


def test_NEGATIVE_delete_of_a_non_ticker_is_the_store_answer_and_dismiss_absent(monkeypatch, stubs):
    db = _db(["OMH"], [_entry("XXII")])
    c = _client(monkeypatch, db)
    out = c.delete(C.API_PATH + "/symbols/$$BAD", headers={"X-User-Email": OWNER}).json()
    assert out == ST.remove("$$BAD", by=OWNER, db=db)
    assert out["state"] == "absent" and out["symbol"] is None
    assert stubs.calls == [("$$BAD", OWNER)]
    assert stubs.dismiss("$$BAD", by=OWNER, db=db)["state"] == "absent"


def test_NEGATIVE_a_raising_dismiss_keeps_the_store_answer(monkeypatch, stubs):
    stubs.raise_dismiss = True
    db = _db(["OMH"], [_entry("XXII")])
    c = _client(monkeypatch, db)
    r1 = c.delete(C.API_PATH + "/symbols/OMH", headers={"X-User-Email": OWNER})
    r2 = c.delete(C.API_PATH + "/symbols/XXII", headers={"X-User-Email": OWNER})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["state"] == "removed" and r2.json()["state"] == "absent"


def test_NEGATIVE_a_missing_engine_keeps_the_store_answer(monkeypatch):
    monkeypatch.setitem(sys.modules, AUTO_MOD, None)
    c = _client(monkeypatch, _db(["OMH"], [_entry("XXII")]))
    assert c.delete(C.API_PATH + "/symbols/OMH", headers={"X-User-Email": OWNER}).json()["state"] == "removed"


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_NEGATIVE_delete_from_anyone_else_touches_neither_list(monkeypatch, stubs, headers):
    db = _db(["OMH"], [_entry("XXII")])
    before = json.dumps(db[C.COLL_LIST].docs, default=str, sort_keys=True)
    c = _client(monkeypatch, db)
    for sym in ("OMH", "XXII"):
        r = c.delete(C.API_PATH + f"/symbols/{sym}", headers=headers)
        assert r.status_code in (401, 404) and r.status_code != 200
        if headers:
            assert r.status_code == 404
    assert stubs.calls == [] and db[C.COLL_LIST].writes == 0
    assert json.dumps(db[C.COLL_LIST].docs, default=str, sort_keys=True) == before


@pytest.mark.parametrize("headers", [{"X-User-Email": OTHER}, {}])
def test_NEGATIVE_get_from_anyone_else_is_owner_only_and_reads_no_auto_doc(monkeypatch, stubs, headers):
    db = _db(["OMH"], [_entry("XXII")])
    c = _client(monkeypatch, db)
    r = c.get(C.API_PATH, headers=headers)
    assert _strict(r.text) == PL.owner_only_payload()
    assert stubs.reads == 0 and "XXII" not in r.text


def test_owner_get_serves_the_auto_section(monkeypatch, stubs):
    db = _db(["OMH"], [_entry("XXII")], session=_route_session())
    c = _client(monkeypatch, db)
    body = _strict(c.get(C.API_PATH, headers={"X-User-Email": OWNER}).text)
    assert [r["symbol"] for r in body["rows"]] == ["OMH", "XXII"] and body["auto"]["n"] == 1
    assert stubs.reads == 1                                                           # ONE auto doc read per GET


def test_NEGATIVE_the_admin_email_never_appears(monkeypatch, stubs):
    from ollama_chat.api import PRIMARY_ADMIN_EMAIL
    db = _db(["OMH"], [_entry("XXII")], session=_route_session(), removed=[_removal(0)])
    monkeypatch.setattr(CO, "_db", lambda: db)
    monkeypatch.setattr(CO, "loop_reads_soon", lambda now: True)
    app = FastAPI()
    app.include_router(API.router)
    c = TestClient(app)
    h = {"X-User-Email": PRIMARY_ADMIN_EMAIL}
    texts = [c.get(C.API_PATH, headers=h).text, c.delete(C.API_PATH + "/symbols/XXII", headers=h).text,
             json.dumps(PL.build(db=db), default=str)]
    assert _strict(texts[0])["auto"]["n"] == 1 and _strict(texts[1])["state"] == "dismissed"
    for t in texts:
        assert PRIMARY_ADMIN_EMAIL not in t


def test_the_route_imports_the_engine_lazily():
    import inspect
    src = inspect.getsource(API)
    assert "from . import auto" not in src and "import_module(PL.AUTO_MODULE)" in src
    assert PL.AUTO_MODULE == AUTO_MOD
    psrc = inspect.getsource(PL)
    assert "from . import auto" not in psrc and "chart_maps.gajjala_watch.auto import" not in psrc


def test_direct_call_of_the_delete_route_runs_store_then_dismiss(monkeypatch, stubs):
    db = _db(["OMH"], [_entry("XXII")])
    order = []
    real_remove = ST.remove
    monkeypatch.setattr(ST, "remove", lambda s, by, db=None: order.append("store") or real_remove(s, by=by, db=db))
    monkeypatch.setattr(CO, "_db", lambda: db)
    real_dismiss = stubs.dismiss
    monkeypatch.setattr(stubs, "dismiss", lambda s, by=None: order.append("auto") or real_dismiss(s, by=by))
    out = asyncio.run(API.gajjala_watch_remove("XXII", email=OWNER))
    assert order == ["store", "auto"] and out["state"] == "dismissed"


def test_hint_push_sentence_follows_push_mode(monkeypatch):
    """The hint's push sentence is picked from auto.push_mode() — NEGATIVE: never the 'do not ring' words when live."""
    from chart_maps.gajjala_watch import auto as AU, constants as C, payload as PL
    monkeypatch.setattr(PL, "_auto_mod", lambda: AU)
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "off")
    off = PL.auto_hint()
    assert "do not ring" in off
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "live")
    live = PL.auto_hint()
    assert "do not ring" not in live and "ring the" in live
    monkeypatch.setattr(C, "AUTO_PUSH_MODE", "junk")
    assert "do not ring" in PL.auto_hint()


def test_empty_text_says_at_or_over():
    from chart_maps.gajjala_watch import payload as PL
    assert "at or over" in PL.AUTO_EMPTY_TEXT
