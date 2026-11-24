"""🧨 Divergence sub on 🚩 Gajjala's 5-min tab — the served block, cards and 🏁 fold (SPEC 2026-11-18 §3.6 / §3.7 / §3.10,
WP-B `diverg-tab`).

Ajay 2026-11-18, verbatim: "yes should do a track recird fir the divergence aftger EMA 9 Cross over bullish / Cuz I am
missing A+ i can chase the divergency atleast like in these cases / I would caught a good chunk of returns".

Hermetic: FakeColl stores only (conftest refuses MongoClient). The records are planted in the shape the engine
(chart_maps.gajjala.divergence, WP-A) writes: {date, symbol, window, alert, ring, live, grade, half_day, …}.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import divergence_tab as DVT
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, scan_doc

ET = ZoneInfo("America/New_York")
S = date(2026, 11, 13)                          # a Friday, a market day — OUTSIDE the OOS sessions
PREV = date(2026, 11, 12)
B_WORD = re.compile("b" + "ounc", re.I)
DV = GC.DIVERGENCE_SUB


def at(hh, mm, d=S):
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


NOW = at(10, 45)


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


def bars(day=S, n=12):
    out = []
    for i in range(n):
        hh, mm = divmod(9 * 60 + 35 + 5 * i, 60)
        out.append({"t": f"{day.isoformat()} {hh:02d}:{mm:02d}", "o": 4.0, "h": 4.1, "l": 3.9, "c": 4.05,
                    "v": 1000 + i})
    return out


def read_doc(sym, day=S, *, tile=None):
    """A stored 🚩 read with a 5-min tile whose 9 EMA crosses above the 21 at 09:55 (index 4)."""
    return {"_id": f"{day.isoformat()}|{sym}", "date": day.isoformat(), "symbol": sym, "setups": {}, "ctx": {},
            "tile": tile if tile is not None else {
                "bars5": bars(day), "bars15": [],
                "curves5": [{"tone": "ema9", "label": "9 EMA", "values": [3.9] * 4 + [4.1] * 8},
                            {"tone": "ema21", "label": "21 EMA", "values": [4.0] * 12}],
                "vol_avg5": {"period": 50, "label": "50-bar avg volume", "values": [100.0] * 12}},
            "updated_at": NOW, "at": NOW}


def grade(day=S, *, outcome="win", gross=10.0, net=9.5, reason="downcross", entry_t="10:20", exit_t="10:30",
          entry_px=4.0, exit_px=4.4):
    d = day.isoformat()
    g = {"entry": {"px": entry_px, "t": f"{d} {entry_t}"}, "gross_pct": gross, "net_pct": net, "hold_min": 10,
         "outcome": outcome, "horizon_t": f"{d} 16:00", "recheck_ok": True, "version": GC.DIVERGENCE_GRADE_VERSION,
         "exit": {"px": exit_px, "t": f"{d} {exit_t}", "reason": reason}}
    if outcome == "no_print":
        g.update(entry=None, exit=None, gross_pct=None, net_pct=None)
    return g


def rec(sym, day=S, bar_t="10:15", *, window="rth", kind="aplus", ring_at="09:50", live=None, g=None, r1=0.71,
        half_day=False, _id=None, entry_t="10:20"):
    d = day.isoformat()
    return {"_id": _id or f"{d}|{sym}", "date": d, "symbol": sym, "window": window,
            "alert": {"i": 40, "bar_t": f"{d} {bar_t}", "r1": r1, "ema9": 4.1, "ema21": 4.0, "atr": 0.14,
                      "close": 4.05, "after_over": False,
                      "v2": {"run": [1000.0, 1200.0, 1500.0], "run_mean": 1233.3, "hour_mean": 900.0, "hour_n": 12}},
            "ring": {"kind": kind, "setup": "bull_flag", "at_et": ring_at, "line": "live"},
            "recorded_at": NOW, "source": "pass", "half_day": half_day,
            "live": live if live is not None else {"as_of_bar_t": f"{d} 10:40",
                                                   "entry": {"px": 4.06, "t": f"{d} {entry_t}"}, "exit": None,
                                                   "state": "open", "gap_now_atr": 0.8, "net_pct_now": 1.2},
            "grade": g, "graded_at": None, "version": GC.DIVERGENCE_GRADE_VERSION, "at": NOW}


def store(recs=(), reads=(), *, fail=False, scans=None):
    reads = list(reads)
    return fake_store(**{ST.DIVERGENCE: FakeColl(list(recs), fail=fail), ST.READS: FakeColl(reads),
                         ST.SCAN: FakeColl(list(scans) if scans is not None else
                                           [scan_doc(r["symbol"], day=S) for r in reads])})


def board(st, sub=DV, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, owner=kw.pop("owner", True), **kw)


def tr_rows(out):
    return [r for d in out["divergence"]["track_record"]["days"] for r in d["rows"]]


# ── the panel ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_sub_serves_the_panel_words_from_constants():
    out = board(store([rec("AAA")], [read_doc("AAA")]))
    assert out["sub"] == DV and out["sub_resolved_from"] == "param"
    b = out["divergence"]
    assert b["title"] == DVT.TITLE and b["ask_text"].count("“") == 3
    rth, ah = b["is_line"]["rth"]["text"], b["is_line"]["ah"]["text"]
    assert "−3.09" in rth and "[−6.73, +1.06]" in rth and "NOT SHOWN" in rth and "56 trades" in rth
    assert "LOST MONEY" in ah and "32 trades" in ah and "description only" in ah
    assert b["is_line"]["rth"]["trades"] == GC.DIVERGENCE_IS["rth"]["trades"]
    assert "2026-11-17" in b["oos_text"] and "2026-11-30" in b["oos_text"]
    assert GC.DIVERGENCE_OOS_SPEC_SHA256[:8] in b["oos_text"] and GC.DIVERGENCE_OOS_SEAL_ET in b["oos_text"]
    assert b["oos_sessions"] == list(GC.DIVERGENCE_OOS_SESSIONS) and b["oos_sealed"] is True
    assert b["oos_done_n"] == 0                                         # 11-13: no OOS session has closed yet
    assert b["honesty"] and "did not make money" in b["honesty"] and "24 sessions" in b["honesty"]
    assert b["window_text"] == "reading closed bars" and b["order_note"] == DVT.ORDER_NOTE
    assert b["n_today"] == 1 and b["n_open"] == 1 and b["n_exited"] == 0 and b["empty_text"] is None
    assert "_tiles" not in b and out["empty_note"] is None


def test_rule_text_holds_only_constant_numbers():
    t = DVT.rule_text()
    assert f"{GC.DIVERGENCE_R1_LEVEL:.3f}" in t
    floats = set(re.findall(r"\d+\.\d+", t))
    assert floats == {f"{GC.DIVERGENCE_R1_LEVEL:.3f}", f"{GC.DIVERGENCE_SLIP_USD:.2f}",
                      format(GC.DIVERGENCE_COST_BPS, ".2%").rstrip("%")}, floats
    ints = {int(x) for x in re.findall(r"(?<![\d.:])\d+(?![\d.:])", t)}
    assert ints <= {GC.EMA_FAST, GC.EMA_SLOW, GC.DIVERGENCE_ATR_PERIOD, GC.DIVERGENCE_V2_RUN,
                    GC.DIVERGENCE_V2_HOUR_BARS, 5}, ints                # 5 = the 5-minute frame word
    for _k, lo, hi in GC.DIVERGENCE_WINDOWS:
        assert lo in t and hi in t
    assert "never pre-market" in t


def test_the_numbers_move_with_the_constants(monkeypatch):
    monkeypatch.setattr(GC, "DIVERGENCE_R1_LEVEL", 0.75)
    monkeypatch.setattr(GC, "DIVERGENCE_V2_RUN", 4)
    t = DVT.rule_text()
    assert "0.750 ATRs" in t and "last 4 bars" in t


def test_the_strip_has_twelve_chips_with_the_divergence_count():
    st = store([rec("AAA"), rec("BBB", bar_t="10:25")], [read_doc("AAA"), read_doc("BBB")])
    out = board(st, GC.DEFAULT_SUB)
    keys = [s["key"] for s in out["subs"]]
    assert len(keys) == 14 == len(GC.SUBS)                             # WIDENED 2026-11-18 — 🌱 Diverging after 🧨; WIDENED 2026-11-23 — 🩳 High SI after 🌱
    assert keys[6] == DV and keys[-2] == GC.POTENTIAL_SUB and keys[-1] == GC.LEDGER_SUB
    chip = out["subs"][6]
    assert (chip["emoji"], chip["label"], chip["count"]) == ("🧨", "Divergence", 2)
    assert "divergence" not in out                                      # NEGATIVE: no block on another sub


def test_NEGATIVE_a_read_fault_blanks_the_sub_with_the_fault_note_and_the_chip_prints_no_number():
    out = board(store([rec("AAA")], [read_doc("AAA")], fail=True))
    assert out["divergence"] is None and out["tiles"] == [] and out["empty_note"] == DVT.FAULT_TEXT
    assert out["subs"][6]["count"] is None


def test_NEGATIVE_no_divergence_key_on_any_other_sub():
    st = store([rec("AAA")], [read_doc("AAA")])
    for k, _e, _l in GC.SUBS:
        if k != DV:
            assert "divergence" not in board(st, k), k


@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "gga"])
def test_NEGATIVE_other_pages_fail_open_and_omit_the_chip(variant):
    st = store([rec("AAA")], [read_doc("AAA")])
    out = board(st, variant=variant)
    assert out["sub"] == GC.DEFAULT_SUB and out["sub_resolved_from"] == "default" and "divergence" not in out
    keys = [s["key"] for s in out["subs"]]
    assert DV not in keys
    if variant is V.GGA:
        assert GC.TABLE_SUB not in keys and len(keys) == len(GC.SUBS) - len(GC.GG5_ONLY_SUBS)
    else:                                                               # the 1-minute page keeps 📋 (2026-11-16)
        # WIDENED 2026-11-18 — 🌱 Diverging after 🧨: the 1-minute page omits both GG5-only read subs (🧨 + 🌱)
        # WIDENED 2026-11-23 — 🩳 High SI after 🌱: the 1-minute page omits all three GG5-only read subs (🧨 + 🌱 + 🩳)
        assert keys[0] == GC.TABLE_SUB and len(keys) == len(GC.SUBS) - 3 and GC.DIVERGING_SUB not in keys
        assert GC.HIGH_SI_SUB not in keys


def test_NEGATIVE_resolve_sub_fails_open_off_gg5_only():
    kw = dict(store=store(), session=S, reads_by={}, listed={}, pm_syms=set(), post_syms=set(), potentials=[])
    assert GT.resolve_sub(DV, "", **kw) == (DV, "param")
    assert GT.resolve_sub(DV, "", v=V.GG1, **kw) == (GC.DEFAULT_SUB, "default")
    assert GT.resolve_sub(DV, "", v=V.GGA, **kw) == (GC.DEFAULT_SUB, "default")


def test_NEGATIVE_is_line_never_served_without_honesty_and_no_b_word():
    out = board(store([rec("AAA", g=grade())], [read_doc("AAA")]))
    b = out["divergence"]
    assert b["is_line"] and isinstance(b["honesty"], str) and b["honesty"]
    assert b["track_record"]["honesty"] == b["honesty"]
    for s in _walk_strings(out):
        assert not B_WORD.search(s), s


def test_window_text_by_tape():
    assert DVT.window_text({"tape": "rth"}) == "reading closed bars"
    assert DVT.window_text({"tape": "afterhours"}) == "reading closed bars"
    assert DVT.window_text({"tape": "premarket"}) == "pre-market — nothing lists before 09:35 ET"


def test_empty_day_serves_the_empty_words():
    out = board(store())
    assert out["divergence"]["empty_text"] == DVT.EMPTY_TODAY and out["tiles"] == []
    assert out["divergence"]["track_record"]["counts_text"]["rth"] == "RTH · nothing to total yet"


# ── the cards ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_one_record_one_house_card():
    out = board(store([rec("AAA")], [read_doc("AAA")]))
    assert len(out["tiles"]) == 1
    t = out["tiles"][0]
    g = t["gajjala"]
    assert t["symbol"] == "AAA" and g["setup"] == DV and g["state"] == "divergence"
    assert g["state_label"] == "🧨 listed 10:15 ET · open — no 9/21 down-cross yet"
    assert [c["key"] for c in g["criteria"]] == ["gap", "cross", "volume"] and all(c["ok"] for c in g["criteria"])
    assert g["criteria"][0]["value"] == "0.71 ATRs on the 10:15 ET bar"
    assert g["criteria"][0]["need"] == f"≥ {GC.DIVERGENCE_R1_LEVEL:.3f} ATRs — the first bar over it today"
    assert g["criteria"][1]["value"] == "9 EMA crossed above the 21 at 09:55 ET"     # off the card frame (ema_cross)
    assert g["criteria"][2]["value"].startswith("1.0K → 1.2K → 1.5K · 3-bar mean 1.2K ≥ prior hour 900")
    assert g["plan_text"].startswith("entry 4.06 (next bar's open, 10:20 ET) · exit = first 5-min 9/21 down-cross")
    assert "gap now 0.80 ATRs" in g["plan_text"]
    kinds = {(m["date"][11:], m["kind"]) for m in t["markers"]}
    assert ("10:15", "buy") in kinds and ("09:55", GT.EMA_CROSS_MARK["up"]) in kinds
    assert next(m for m in t["markers"] if m["kind"] == "buy")["label"] == "🧨"
    assert t["href"] == GT.chart_href("AAA", "5m") and t["tf"] == "5m" and "axis" in t
    assert t["lines"] == [{"price": 4.06, "label": "ENTRY 4.06", "tone": "buy", "text": "4.06"}]
    assert {"k": "Gap", "v": "0.71 ATRs"} in t["stats"]
    for k in ("_last", "_bars_to_go", "_float_shares", "_volume"):
        assert k not in g
    assert g["divergence"]["ring_text"] == "🎯 A+ 09:50 ET" and g["divergence"]["window_text"] == "RTH"


def test_an_up_cross_stored_by_the_engine_wins_and_no_cross_reads_already_over():
    r = rec("AAA")
    r["alert"]["up_cross_t"] = f"{S.isoformat()} 09:40"
    assert DVT.criteria(r)[1]["value"] == "9 EMA crossed above the 21 at 09:40 ET"
    r["alert"]["up_cross_t"] = None                                     # the engine read the session: no cross today
    frame_cross = {"crosses": [{"t": f"{S.isoformat()} 09:55", "dir": "up"}]}
    assert DVT.criteria(r, frame_cross)[1]["value"] == "9 EMA already over the 21 EMA at 04:00 — no cross today"
    assert DVT.criteria(rec("AAA"))[1]["value"] == "9 EMA already over the 21 EMA at 04:00 — no cross today"
    assert DVT.criteria(rec("AAA"), frame_cross)[1]["value"] == "9 EMA crossed above the 21 at 09:55 ET"


def test_an_after_close_ring_of_the_prior_session_names_its_date():
    r = rec("AAA", ring_at="16:40")
    r["ring"]["date"] = PREV.isoformat()
    assert DVT.record_words(r)["ring_text"] == f"🎯 A+ 16:40 ET ({PREV.isoformat()})"
    r["ring"]["date"] = S.isoformat()
    assert DVT.record_words(r)["ring_text"] == "🎯 A+ 16:40 ET"


def test_a_graded_record_reads_exited_with_net_and_an_exit_marker():
    out = board(store([rec("AAA", g=grade())], [read_doc("AAA")]))
    g = out["tiles"][0]["gajjala"]
    assert g["state_label"] == "🧨 listed 10:15 ET · exited 10:30 ET (9/21 down-cross) · +9.50% net"
    assert any(m["kind"] == GT.EMA_CROSS_MARK["down"] and m["date"].endswith("10:30") for m in out["tiles"][0]["markers"])
    assert out["divergence"]["n_exited"] == 1 and out["divergence"]["n_open"] == 0
    nop = DVT.state_label(rec("AAA", g=grade(outcome="no_print")))
    assert nop == "🧨 listed 10:15 ET · no print after the listing"


def test_order_open_first_newest_on_top_then_exited_and_his_names_last():
    recs = [rec("OLD", bar_t="10:00"), rec("NEW", bar_t="10:25"), rec("EXA", bar_t="10:20", g=grade()),
            rec("EXB", bar_t="10:05", g=grade(outcome="loss", net=-3.0, gross=-2.5))]
    st = store(recs, [read_doc(s) for s in ("OLD", "NEW", "EXA", "EXB")])
    assert [t["symbol"] for t in board(st)["tiles"]] == ["NEW", "OLD", "EXA", "EXB"]
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": ["NEW"], "removed": []}
    out = board(st)
    assert [t["symbol"] for t in out["tiles"]] == ["OLD", "EXA", "EXB", "NEW"]
    assert out["tiles"][-1]["broker_text"] == GT.BROKER_FLAG_TEXT


def test_NEGATIVE_a_nan_value_prints_a_dash_and_never_leaves_the_block():
    r = rec("AAA", r1=float("nan"))
    r["live"]["gap_now_atr"] = float("nan")
    out = board(store([r], [read_doc("AAA")]))
    json.dumps(out, allow_nan=False)
    g = out["tiles"][0]["gajjala"]
    assert g["criteria"][0]["value"] == "— ATRs on the 10:15 ET bar" and "gap now — ATRs" in g["plan_text"]
    assert {"k": "Gap", "v": "— ATRs"} in out["tiles"][0]["stats"]


def test_chips_tolerate_an_empty_read():
    chips = GT._chips(read_doc("AAA"), DV, {}, {}, {"tape": "rth"}, None, None)
    assert chips["red_closes"] is None and chips["stopped_earlier"] is None and "vol_dried" not in chips


# ── [C7] three fences ───────────────────────────────────────────────────────────────────────────────────────────
def test_C7_a_missing_read_and_a_malformed_tile_are_chartless_and_the_rest_serves():
    recs = [rec("MIS", bar_t="10:05"), rec("BAD", bar_t="10:10"), rec("GOOD", bar_t="10:15")]
    st = store(recs, [read_doc("BAD", tile={"bars5": "junk"}), read_doc("GOOD")])
    out = board(st)
    b = out["divergence"]
    assert [t["symbol"] for t in out["tiles"]] == ["GOOD"] and out["empty_note"] is None
    assert sorted(c["symbol"] for c in b["chartless"]) == ["BAD", "MIS"]
    assert b["faults"] == ["BAD"] and b["faults_text"] == "1 listing(s) could not draw a card — the record still holds them"
    mis = next(c for c in b["chartless"] if c["symbol"] == "MIS")
    assert mis["text"] == "🧨 MIS listed 10:05 ET · chart not stored" and mis["href"] == GT.chart_href("MIS", "5m")
    assert len(tr_rows(out)) == 3


def test_C7_NEGATIVE_no_fault_means_no_faults_text():
    b = board(store([rec("AAA")], [read_doc("AAA")]))["divergence"]
    assert b["chartless"] == [] and b["faults"] == [] and b["faults_text"] is None


def test_C7_a_raising_fold_keeps_the_panel_and_the_cards(monkeypatch):
    monkeypatch.setattr(LG, "_categories", lambda rows: (_ for _ in ()).throw(RuntimeError("boom")))
    out = board(store([rec("AAA")], [read_doc("AAA")]))
    b = out["divergence"]
    assert b["track_record"] is None and b["track_record_fault_text"] == DVT.TRACK_RECORD_FAULT_TEXT
    assert b["title"] == DVT.TITLE and len(out["tiles"]) == 1 and out["empty_note"] is None


# ── the 🏁 fold ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_fold_counts_net_beside_the_win_rate_and_buckets():
    recs = [rec("WIN", bar_t="10:00", g=grade()),
            rec("LOS", bar_t="10:05", g=grade(outcome="loss", gross=-4.0, net=-4.6, reason="close", exit_t="16:00")),
            rec("OPN", bar_t="10:10"),
            rec("NOP", bar_t="10:15", g=grade(outcome="no_print"))]
    out = board(store(recs, [read_doc(r["symbol"]) for r in recs]), span="today")
    tr = out["divergence"]["track_record"]
    c = tr["counts"]["rth"]
    assert (c["n"], c["win"], c["loss"], c["open"], c["no_print"], c["pct"]) == (2, 1, 1, 1, 1, 50)
    assert (c["exit_downcross"], c["exit_close"]) == (1, 1)
    assert c["net_mean"] == pytest.approx((9.5 - 4.6) / 2) and c["sealed_rows"] == 0
    txt = tr["counts_text"]["rth"]
    assert re.search(r"\d+% won.*net [+-]\d", txt), txt
    assert "50% won · net +2.45% per trade" in txt and "1 open · 1 no print" in txt
    assert tr["counts_text"]["ah"] == "AH · nothing to total yet"
    rows = {r["symbol"]: r for r in tr_rows(out)}
    assert rows["OPN"]["bucket"] == "open" and rows["NOP"]["bucket"] == "out" and rows["WIN"]["bucket"] == "win"
    assert rows["WIN"]["flag_text"] == LG.BUCKET_TEXT["win"] and rows["OPN"]["flag_text"] is None
    assert rows["WIN"]["net"] == {"state": "win", "text": "+9.50%"}
    assert rows["LOS"]["exit"]["text"] == "4.40 · 16:00 ET · the 16:00 mark"
    assert rows["OPN"]["exit"]["state"] == "open" and rows["OPN"]["net"]["text"] == "—"
    assert [h["key"] for h in tr["heads"]] == [k for k, _l in DVT.TR_HEADS]
    assert tr["bucket_order"] == list(LG.BUCKETS) and tr["sort_default"] == LG.SORT_KEYS[0]
    assert {x["key"]: x["n"] for x in tr["categories"]}["win"] == 1
    assert tr["today_text"].startswith("Today · listings grade tonight") and tr["is_text"] == DVT.is_lines()["rth"]["text"]
    for r in tr_rows(out):
        assert not [k for k in r if k.startswith("_")], r


def test_NEGATIVE_a_win_rate_never_prints_without_net():
    out = board(store([rec("WIN", g=grade())], [read_doc("WIN")]), span="today")
    txt = out["divergence"]["track_record"]["counts_text"]["rth"]
    assert "% won" in txt and "net +9.50%" in txt


def test_a_legacy_duplicate_is_chipped_and_counted_once():
    a = rec("DUP", bar_t="10:00", g=grade())
    b = rec("DUP", bar_t="10:20", g=grade(), _id=f"{S.isoformat()}|DUP|legacy")
    out = board(store([a, b], [read_doc("DUP")]), span="today")
    tr = out["divergence"]["track_record"]
    rows = tr_rows(out)
    assert len(rows) == 2
    dup = next(r for r in rows if r["dup_of"])
    assert dup["id"].endswith("legacy") and dup["dup_text"] == "🔁 same trade as the 10:00 🧨 ring — not counted"
    assert dup["flag_text"] is None
    assert tr["counts"]["rth"]["n"] == 1 and tr["counts"]["rth"]["dup"] == 1


def test_spans_yesterday_and_all():
    old = date(2026, 11, 3)
    st = store([rec("TOD"), rec("YDA", day=PREV, g=grade(day=PREV)), rec("OLD", day=old, g=grade(day=old))],
               [read_doc("TOD")])
    y = board(st, span="yesterday")["divergence"]["track_record"]
    assert [r["symbol"] for d in y["days"] for r in d["rows"]] == ["YDA"] and y["today_text"] is None
    calls = []
    real = st.divergence_dates
    st.divergence_dates = lambda: calls.append(1) or real()
    a = board(st, span="all")["divergence"]["track_record"]
    assert calls and {r["symbol"] for d in a["days"] for r in d["rows"]} == {"TOD", "YDA", "OLD"}
    assert [d["date"] for d in a["days"]] == [S.isoformat(), PREV.isoformat(), old.isoformat()]   # newest first
    assert a["span"] == "all"


def test_NEGATIVE_an_all_span_dates_fault_is_the_fold_fault_only():
    st = store([rec("TOD")], [read_doc("TOD")])
    st.divergence_dates = lambda: None
    b = board(st, span="all")["divergence"]
    assert b["track_record"] is None and b["track_record_fault_text"] == DVT.TRACK_RECORD_FAULT_TEXT
    assert b["title"] == DVT.TITLE


def test_oos_and_half_day_tags():
    oos, half = date(2026, 11, 17), date(2026, 11, 27)
    st = store([rec("OOS", day=oos, g=grade(day=oos)), rec("HLF", day=half, half_day=True, g=grade(day=half)),
                rec("TOD")], [read_doc("TOD")])
    now = at(10, 45, d=date(2026, 12, 1))
    rows = {r["symbol"]: r for r in tr_rows(board(st, span="all", now=now))}
    assert rows["OOS"]["oos_text"] == "OOS session" and rows["TOD"]["oos_text"] is None
    assert rows["HLF"]["half_day_text"] == "half day · outside the registered read" and rows["OOS"]["half_day_text"] is None
    tr = board(st, span="all", now=now)["divergence"]["track_record"]
    assert tr["counts"]["rth"]["half_day"] == 1 and "1 half-day listing(s) outside the registered read" in \
        tr["counts_text"]["rth"]


# ── [C2] the OOS seal ───────────────────────────────────────────────────────────────────────────────────────────
OOS1, OOS2, ASK = date(2026, 11, 17), date(2026, 11, 18), date(2026, 11, 16)
IN_OOS = at(10, 45, d=date(2026, 11, 20))
AFTER = at(10, 45, d=date(2026, 12, 1))


def _oos_store(with_ask=False):
    recs = [rec("OSA", day=OOS1, g=grade(day=OOS1)), rec("OSB", day=OOS2, g=grade(day=OOS2, outcome="loss", net=-2.0,
                                                                                   gross=-1.5))]
    if with_ask:
        recs.append(rec("ASK", day=ASK, g=grade(day=ASK, net=3.0, gross=3.5)))
    return store(recs)


def test_C2_sealed_inside_the_window_rows_keep_their_cells():
    out = board(_oos_store(), span="all", now=IN_OOS)
    tr = out["divergence"]["track_record"]
    c = tr["counts"]["rth"]
    assert c["n"] == 0 and c["sealed_rows"] == 2
    assert tr["counts_text"]["rth"] == ("RTH · nothing to total yet · 2 OOS listing(s) not totalled until "
                                        "2026-11-30 20:00 ET")
    assert tr["oos_progress_text"] == "OOS session 3 of 8 · sealed read after 2026-11-30 20:00 ET — not this tab"
    assert "oos_counts_text" not in tr and tr["oos_sealed"] is True
    nets = {r["symbol"]: r["net"]["text"] for r in tr_rows(out)}
    assert nets == {"OSA": "+9.50%", "OSB": "-2.00%"}
    assert out["divergence"]["oos_sealed"] is True and out["divergence"]["oos_done_n"] == 3


def test_C2_the_ask_day_is_never_sealed():
    tr = board(_oos_store(with_ask=True), span="all", now=IN_OOS)["divergence"]["track_record"]
    c = tr["counts"]["rth"]
    assert c["n"] == 1 and c["win"] == 1 and c["sealed_rows"] == 2
    assert tr["counts_text"]["rth"].endswith("· 2 OOS listing(s) not totalled until 2026-11-30 20:00 ET")


def test_C2_after_the_seal_every_row_counts_and_the_oos_line_shows():
    st = _oos_store(with_ask=True)
    tr = board(st, span="all", now=AFTER)["divergence"]["track_record"]
    c = tr["counts"]["rth"]
    assert c["n"] == 3 and c["sealed_rows"] == 0 and "not totalled" not in tr["counts_text"]["rth"]
    assert "oos_progress_text" not in tr and tr["oos_sealed"] is False
    assert tr["oos_counts_text"] == ("OOS 8 sessions · RTH 2 graded · net +3.75% (median +3.75%) · no CI under the "
                                     "lab's 30-week rule")
    assert DVT.oos_done_n(AFTER) == len(GC.DIVERGENCE_OOS_SESSIONS)


def test_C2_NEGATIVE_the_seal_clock_is_the_constant():
    seal = datetime(2026, 11, 30, 20, 0, tzinfo=ET)
    assert DVT.oos_sealed(seal.astimezone(timezone.utc).replace(second=0)) is False
    assert DVT.oos_sealed(datetime(2026, 11, 30, 19, 59, tzinfo=ET)) is True


# ── rules_info (§3.10) ──────────────────────────────────────────────────────────────────────────────────────────
def test_rules_info_note_carries_the_divergence_row_from_constants(monkeypatch):
    from supply_demand import rules_info as RI
    line = RI._gg_divergence_clause()
    assert line.startswith(" 🧨 Divergence (record only): listed at the first closed 5-min bar")
    assert "≥ the study's 60th-percentile gap over the 21 EMA in 14-bar ATRs, volume rising 3 bars" in line
    assert "no push, no gate" in line and "0.555" not in line and line in RI._gajjala_section()["note"]
    monkeypatch.setattr(GC, "DIVERGENCE_LEVEL_PCT", 75)
    assert "75th-percentile" in RI._gg_divergence_clause()


def test_NEGATIVE_rules_info_a_missing_constant_drops_only_the_clause(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.delattr(GC, "DIVERGENCE_V2_RUN")
    assert RI._gg_divergence_clause() == ""
    # WIDENED 2026-11-18 — the 🌱 Diverging clause names "the 🧨 cut", so the NEGATIVE reads the 🧨 clause's own head
    assert "🧨 Divergence (record only)" not in RI._gajjala_section()["note"]
