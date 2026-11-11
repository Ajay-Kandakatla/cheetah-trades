"""🏁 Not traded on the 🚩 lane (2026-11-11) — trading/gajjala_untraded.py + the tab_payload wiring.

Ajay 2026-11-11 ~12:00 ET, verbatim: "Maintain a track record when Alpaca is blocked please, Like we do in Gajjals so I
know how our strategies are working"

Locks: the join (lane `_id` → raw `GG:` alert → alert_of → ledger id), the 🏁's own cell words verbatim (no R, no $),
the reasons and their order, byte parity with the 🏁 served_block (cells, 🔁, counts), the memo-only provisional read
(parity with today_read, never a fetch), the lane window rule, the "out" rows apart from the total, the comparison line,
and the NEGATIVES N1–N14 (nothing summed into the journal, nothing written, faults soft, today's not-seen rows never
counted). Every store and tape here is SYNTHETIC; the network is never touched. UNMEASURED — accounting, not a study.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, time as dtime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

import trading.gajjala_entry as GL
import trading.gajjala_untraded as GU
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from tests.test_gajjala_lane import DAY as LDAY, _at, alert as lane_alert, lane, seed  # noqa: F401 — `lane` fixture
from tests.test_gajjala_ledger import HF_AT, NOW_1225, VCP_AT, D16, Clock, xlab_bars
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_trading_engine import _position

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D = date(2026, 11, 10)                                   # a Tuesday, a full session
HALF = date(2026, 11, 27)                                # supply_demand.timeframes.HALF_DAYS
SRC = Path(GU.__file__).read_text(encoding="utf-8")
B_WORD = re.compile("b" + "ounc", re.I)
R_FIGURE = re.compile(r"[+\-−]?\d+(?:\.\d+)?R\b")


@pytest.fixture(autouse=True)
def _clean_memo():
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


# ── SYNTHETIC builders ───────────────────────────────────────────────────────────────────────────────────────────
def et(d, hh, mm) -> datetime:
    return datetime(d.year, d.month, d.day, hh, mm, tzinfo=ET)


def raw(sym, setup, d=D, hm=(10, 0), trig=2.0, stop=1.8):
    """A live A+ claim as the 🚩 pass stores it (`GG:` id, state pushed)."""
    return {"_id": f"GG:{d.isoformat()}|{sym}|{setup}", "date": d.isoformat(), "symbol": sym, "setup": setup,
            "state": "pushed", "at": et(d, *hm).astimezone(UTC).isoformat(), "trigger": trig, "stop": stop,
            "frame": "5m", "kind": GC.PUSH_KIND, "mode": "live"}


def tape(d, trig, stop, outcome, fill=(10, 30), exit_=(10, 40), end=(15, 59), gap=False) -> list:
    """SYNTHETIC 1-minute bars: under the trigger until `fill`, the fill minute at the trigger, then a WIN (+2R high),
    a LOSS (the stop, or `gap` far through it) at `exit_`, "open" (never decided) or "no_entry" (never the trigger)."""
    R = trig - stop
    mid = round(stop + R / 2, 4)
    out, t, last = [], et(d, 9, 30), et(d, *end)
    f_t, x_t = et(d, *fill), et(d, *exit_)
    px = (mid,) * 4
    while t <= last:
        if outcome == "no_entry" or t < f_t:
            px = (mid,) * 4
        elif t == f_t:
            px = (trig,) * 4
        elif outcome == "open" or t < x_t:
            px = (trig,) * 4
        elif t == x_t:
            if outcome == "win":
                px = (trig, round(trig + 2 * R, 4), trig, trig)
            else:
                lo = round(stop - 3 * R, 4) if gap else stop
                px = (lo, lo, lo, lo) if gap else (trig, trig, lo, lo)
        else:
            px = (px[3],) * 4
        out.append((t.astimezone(UTC), *map(float, px)))
        t += timedelta(minutes=1)
    return out


def ledger_doc(r, outcome, *, with_same=True, **kw):
    row = LG.alert_of(r, "aplus")
    b = LG.session_bounds(row["date"], row["at_utc"])
    doc = {"_id": row["id"], "date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": "aplus",
           "line": "live", "version": GC.LEDGER_GRADE_VERSION}
    if with_same:
        doc["same"] = LG.grade(row, tape(b["same_date"], row["trigger"], row["stop"], outcome, **kw), b, "same")
    return doc


def lane_doc(r, state, skip_kind=None, **kw):
    d = {"_id": r["_id"], "date": r["date"], "symbol": r["symbol"], "setup": r["setup"], "state": state,
         "skip_kind": skip_kind, "why": "synthetic"}
    d.update(kw)
    return d


def store_of(raws=(), ledger=()):
    return fake_store(**{ST.ALERTS: FakeColl(list(raws)), ST.LEDGER: FakeColl(list(ledger))})


def run(docs, st, *, day=D, now=None, **kw):
    return GU.read(docs, day=day.isoformat(), now=now or et(day, 20, 0), store=st, **kw)


def lines_of(block):
    return {ln["key"]: ln for ln in block["lines"]}


def cell_of(st, r, now, session=D):
    """The 🏁's own cell for this alert, through the 🏁 functions only."""
    row = LG.alert_of(r, "aplus")
    led = st.coll(ST.LEDGER).find({"_id": row["id"]})
    same = (led[0] if led else {}).get("same")
    return LG._cell(row, "same", same, False, LG._aware(now), session, True)


def base_text(cell):
    return f"{GU.TRACK_LEAD} {cell['text']}" + (f" — {cell['sub_text']}" if cell["sub_text"] else "")


def strip_counts(c):
    return {k: v for k, v in c.items() if k != "pct"}


# ── constants ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_constants_are_subsets_of_the_lane_and_every_skip_kind_has_a_line():
    assert set(GU.UNTRADED_STATES) <= set(GL.STATES)
    assert set(GU.TRADED_STATES) <= set(GL._DAY_STATES)
    assert set(GU.REASON_ORDER) >= set(GL.SKIP_KINDS) | set(GL.LEGACY_SKIP_KINDS)    # a future skip kind fails here
    assert set(GU.OUT_OF_TOTAL) <= set(GU.REASON_ORDER) and GU.REASON_ORDER[-1] == "other"
    assert GU.REASON_ORDER[-1 - len(GU.OUT_OF_TOTAL):-1] == GU.OUT_OF_TOTAL
    assert set(GU.REASON_TEXT) == set(GU.REASON_ORDER) and len(set(GU.REASON_ORDER)) == len(GU.REASON_ORDER)
    assert GL.ROW_KEYS[-len(GU.ROW_TRACK_KEYS):] == GU.ROW_TRACK_KEYS
    assert set(GU.STOP_TAIL) <= set(GU.REASON_ORDER) - set(GU.OUT_OF_TOTAL)


# ── P1 join ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_P1_the_lane_row_gets_the_cell_of_its_own_alert_never_another_setup_or_day():
    a = raw("AAA", "bull_flag")
    other_setup = raw("AAA", "kiss_fly", hm=(13, 0), trig=3.0, stop=2.5)
    prev_day = raw("AAA", "bull_flag", d=date(2026, 11, 9))
    led = [ledger_doc(a, "win"), ledger_doc(other_setup, "loss", fill=(13, 30), exit_=(13, 40)),
           ledger_doc(prev_day, "loss")]
    st = store_of([a, other_setup], led)
    out = run([lane_doc(a, "skipped", "floor")], st)
    now = et(D, 20, 0)
    want = cell_of(st, a, now)
    assert want["state"] == "win"
    assert out["rows"][a["_id"]] == {"track_state": "win", "track_text": base_text(want)}
    # NEGATIVE: the other setup's LOSS and the prior day's LOSS are never read into this row
    assert "LOSS" not in out["rows"][a["_id"]]["track_text"]
    assert lines_of(out["block"])["floor"]["counts"]["win"] == 1 and lines_of(out["block"])["floor"]["counts"]["loss"] == 0


# ── P2 no R, no $ ────────────────────────────────────────────────────────────────────────────────────────────────
def test_P2_the_row_is_the_cell_words_verbatim_a_gap_loss_prints_no_R_and_no_money(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the not-traded block priced a trade")
    monkeypatch.setattr(GL, "r_multiple", boom)
    monkeypatch.setattr(GL, "pnl_of", boom)
    g = raw("GAP", "reversal_squeeze")
    w = raw("WIN", "intraday_vcp")
    st = store_of([g, w], [ledger_doc(g, "loss", gap=True), ledger_doc(w, "win")])
    out = run([lane_doc(g, "skipped", "floor"), lane_doc(w, "skipped", "earnings")], st)
    now = et(D, 20, 0)
    gc = cell_of(st, g, now)
    assert gc["state"] == "loss" and gc["text"].startswith("LOSS · ")
    gap_text = out["rows"][g["_id"]]["track_text"]
    assert gap_text == base_text(gc)
    assert gap_text[len(GU.TRACK_LEAD) + 1:] == gc["text"] + " — " + gc["sub_text"]
    assert not R_FIGURE.search(gap_text), gap_text                      # NEGATIVE: no "−1R" on a gap through the stop
    assert out["rows"][w["_id"]]["track_text"] == base_text(cell_of(st, w, now))
    for r in out["rows"].values():
        assert "$" not in r["track_text"]
    for ln in out["block"]["lines"] + [out["block"]["total"], out["block"]["traded"]]:
        assert "$" not in ln["text"][len(ln["label"]):], ln["text"]       # the served words after the label
        assert not R_FIGURE.search(ln["text"][len(ln["label"]):]), ln["text"]


# ── P3 reasons ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_P3_lines_follow_the_reason_order_zero_lines_are_dropped_unknown_goes_to_other_last():
    rs = [raw(s, "bull_flag", hm=(10, i)) for i, s in enumerate(("U1", "U2", "U3", "U4", "U5"))]
    docs = [lane_doc(rs[0], "skipped", "brand_new_kind"), lane_doc(rs[1], "skipped", "held"),
            lane_doc(rs[2], "skipped", "broker_gap"), lane_doc(rs[3], "unfilled"),
            lane_doc(rs[4], "dry_run")]
    out = run(docs, store_of(rs, [ledger_doc(r, "win") for r in rs]))
    keys = [ln["key"] for ln in out["block"]["lines"]]
    assert keys == ["broker_gap", "unfilled", "held", "disarmed", "other"]
    assert keys == sorted(keys, key=GU.REASON_ORDER.index)
    for ln in out["block"]["lines"]:
        assert set(ln) == set(GU.LINE_KEYS) and ln["n"] == 1 and ln["label"] == GU.REASON_TEXT[ln["key"]]
        assert ln["text"].startswith(f"{ln['label']}: 1 · ")
    assert set(out["block"]) == set(GU.BLOCK_KEYS)
    assert GU.reason_of({"state": "unfilled", "skip_kind": "blocked"}) == "blocked"
    assert GU.reason_of({"state": "unfilled", "skip_kind": "never_triggered"}) == "never_triggered"
    assert GU.reason_of({"state": "skipped"}) == "other"                 # NEGATIVE: a skipped row without a kind


# ── P4 parity with the 🏁 ────────────────────────────────────────────────────────────────────────────────────────
def test_P4_cells_dup_and_counts_are_byte_equal_to_the_track_record_served_block():
    a1 = raw("AAA", "bull_flag", hm=(10, 0))
    a2 = raw("AAA", "kiss_fly", hm=(10, 5))                             # the same trigger + stop → 🔁 (b)
    b1 = raw("BBB", "intraday_vcp", hm=(10, 10), trig=5.0, stop=4.5)
    led = [ledger_doc(a1, "win"), ledger_doc(a2, "win"), ledger_doc(b1, "loss", fill=(11, 0), exit_=(11, 20))]
    st = store_of([a1, a2, b1], led)
    docs = [lane_doc(a1, "closed"), lane_doc(a2, "skipped", "held"), lane_doc(b1, "skipped", "floor")]
    now = et(D, 17, 0)
    out = run(docs, st, now=now)
    served = LG.served_block(st, D, now, span="all", is_today=True)
    srows = {r["id"]: r for d in served["days"] for r in d["rows"]}
    for r in (a2, b1):
        lid = LG.alert_of(r, "aplus")["id"]
        s = srows[lid]
        mine = out["rows"][r["_id"]]
        assert mine["track_state"] == s["same"]["state"]
        tail = f" · {s['dup_text']}" if s["dup_text"] else ""
        assert mine["track_text"] == base_text(s["same"]) + tail
    a2_id = LG.alert_of(a2, "aplus")["id"]
    assert srows[a2_id]["dup_of"] == LG.alert_of(a1, "aplus")["id"] and srows[a2_id]["dup_text"]
    assert srows[a2_id]["dup_text"] in out["rows"][a2["_id"]]["track_text"]
    blk = out["block"]
    summed = LG._counts_blank("same")
    dup = 0
    for ln in blk["lines"] + [blk["traded"]]:
        dup += ln["dup"]
        for k, v in strip_counts(ln["counts"]).items():
            summed[k] += v
    assert strip_counts(summed) == strip_counts(served["counts"]["entry"]["same"])
    assert dup == served["dup_counts"]["entry"] == 1
    assert blk["traded"]["counts"]["win"] == 1 and blk["traded"]["n"] == 1
    assert a1["_id"] not in out["rows"]                                 # the traded row gets no track_*


# ── P5 provisional parity ────────────────────────────────────────────────────────────────────────────────────────
def test_P5_provisional_same_equals_today_read_byte_for_byte_from_the_shared_memo():
    raws = [raw("XLAB", "horizontal_fade", d=D16, trig=1.81, stop=1.70),
            raw("XLAB", "intraday_vcp", d=D16, trig=1.85, stop=1.75)]
    raws[0]["at"], raws[1]["at"] = HF_AT, VCP_AT
    st = store_of(raws)
    clk = Clock()
    out = LG.today_read(NOW_1225, span="today", store=st, load_frames=lambda s, d: (xlab_bars(), False), clock=clk)
    calls = []

    def memo_only(sym, day, *, now=None, load="unset"):
        calls.append(load)
        return LG.today_bars(sym, day, clock=clk, now=now, load=load)
    rows = [LG.alert_of(r, "aplus") for r in raws]
    assert {r["id"] for r in rows} <= set(out["grades"])
    for row in rows:
        assert GU.provisional_same(row, D16, NOW_1225, today_bars=memo_only) == out["grades"][row["id"]]
    assert calls and all(c is None for c in calls)                      # MEMO-ONLY, never a loader
    # NEGATIVE: another session's row, or a no-plan row, never reads a provisional grade
    assert GU.provisional_same(rows[0], date(2026, 10, 15), NOW_1225, today_bars=memo_only) is None
    assert GU.provisional_same(dict(rows[0], plan="no_plan"), D16, NOW_1225, today_bars=memo_only) is None


# ── P6 the lane window ───────────────────────────────────────────────────────────────────────────────────────────
def _one(d, hm, fill, exit_, outcome="win", state=("skipped", "floor"), now=None):
    r = raw("WIN", "bull_flag", d=d, hm=hm)
    end = (12, 59) if d == HALF else (15, 59)
    st = store_of([r], [ledger_doc(r, outcome, fill=fill, exit_=exit_, end=end)])
    out = run([lane_doc(r, state[0], state[1])], st, day=d, now=now)
    return out, r


def test_P6_a_fill_at_the_cut_off_is_late_one_minute_before_is_counted():
    cut = GL.cutoff_et(D)
    late, r = _one(D, (10, 0), (cut.hour, cut.minute), (cut.hour, cut.minute + 2))
    ln = lines_of(late["block"])["floor"]
    assert ln["late"] == 1 and ln["counts"]["win"] == 0 and GU.LATE_TAIL in ln["text"]
    assert late["block"]["total"]["late"] == 1 and late["block"]["total"]["counts"]["win"] == 0
    assert f"after the lane's {GL._hhmm(cut)} ET cut-off — not counted" in late["rows"][r["_id"]]["track_text"]
    ok, _r = _one(D, (10, 0), (cut.hour, cut.minute - 1), (cut.hour, cut.minute + 2))
    ln = lines_of(ok["block"])["floor"]
    assert ln["late"] == 0 and ln["counts"]["win"] == 1 and GU.LATE_TAIL not in ln["text"]   # NEGATIVE


def test_P6_an_exit_at_the_flatten_is_late_one_minute_before_is_counted():
    fl = GL.flatten_et(D)
    late, r = _one(D, (10, 0), (15, 0), (fl.hour, fl.minute))
    assert lines_of(late["block"])["floor"]["late"] == 1
    assert f"after the lane's {GL._hhmm(fl)} ET flatten — not counted" in late["rows"][r["_id"]]["track_text"]
    ok, _r = _one(D, (10, 0), (15, 0), (fl.hour, fl.minute - 1))
    assert lines_of(ok["block"])["floor"]["late"] == 0 and lines_of(ok["block"])["floor"]["counts"]["win"] == 1


def test_P6_an_after_close_alert_filled_the_next_session_is_other_session():
    r = raw("AHX", "bull_flag", hm=(16, 5))
    led = ledger_doc(r, "win")
    assert LG._parse_at(led["same"]["fill_t"]).astimezone(ET).date() != D
    out = run([lane_doc(r, "skipped", "missed")], store_of([r], [led]), now=et(D + timedelta(days=2), 20, 0))
    assert GU.lane_window_miss(D.isoformat(), led["same"]) == "other_session"
    assert lines_of(out["block"])["missed"]["late"] == 1
    assert "the 🏁 filled on a session the lane never trades — not counted" in out["rows"][r["_id"]]["track_text"]


def test_P6_a_half_day_uses_its_own_cut_off_never_the_full_day_one():
    cut = GL.cutoff_et(HALF)
    assert cut == dtime(12, 30) != GL.cutoff_et(D)
    late, _r = _one(HALF, (10, 0), (12, 30), (12, 40))
    assert lines_of(late["block"])["floor"]["late"] == 1
    ok, _r = _one(HALF, (10, 0), (12, 29), (12, 40))
    assert lines_of(ok["block"])["floor"]["late"] == 0
    full, _r = _one(D, (10, 0), (12, 30), (12, 40))                         # NEGATIVE: a full day is open at 12:30
    assert lines_of(full["block"])["floor"]["late"] == 0 and lines_of(full["block"])["floor"]["counts"]["win"] == 1
    assert "12:30" in GU.honesty_text(HALF.isoformat()) and GL._hhmm(GL.cutoff_et(D)) in GU.honesty_text(D.isoformat())


def test_P6_lane_window_miss_is_none_for_anything_not_filled():
    assert GU.lane_window_miss(D.isoformat(), None) is None
    assert GU.lane_window_miss(D.isoformat(), {"entry": "no_entry"}) is None
    assert GU.lane_window_miss(D.isoformat(), {"entry": "filled", "fill_t": None}) is None


# ── P7 words ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_P7_every_number_in_the_words_is_a_constant_value():
    allowed = {"%g" % GL.GAJJALA_MAX_ROUND_R_PCT, "%g" % GL.GAJJALA_MISSED_R, "%d" % GL.GAJJALA_MAX_OPEN,
               "%.2f" % GL.MIN_STOP_GAP_USD, "%d" % GL.GG_TRAIL_EMA, LG._m(), LG._t(GC.LEDGER_FILL_FROM_ET),
               "0"}                                                     # "0 shares fit the size": a count, not a number
    for d in (D, HALF):
        allowed |= {GL._hhmm(GL.cutoff_et(d)), GL._hhmm(GL.flatten_et(d))}
    body = " ".join([GU.honesty_text(D.isoformat()), GU.honesty_text(HALF.isoformat())]
                    + list(GU.REASON_TEXT.values()) + list(GU.STOP_TAIL.values()))
    body = body.replace("v1 ", " ")                                     # the v1 lane's name, not a number
    tokens = re.findall(r"\d{1,2}:\d{2}|\d+(?:\.\d+)?", body)
    assert [t for t in tokens if t not in allowed] == []


def test_P7_the_words_move_with_the_constants_never_typed(monkeypatch):
    monkeypatch.setattr(GL, "GG_TRAIL_EMA", 13)
    assert "the 13 EMA trail" in GU.honesty_text(D.isoformat())
    rs = [raw("OLD", "bull_flag", d=date(2026, 11, 9)), raw("NEW", "bull_flag")]
    out = run([lane_doc(r, "skipped", "floor") for r in rs], store_of(rs), shown_ids={rs[1]["_id"]})
    assert out["block"]["span_text"] == (
        f"Every lane row without a fill since 2026-11-09 — 2 rows · the 🏁 same-session column · one count per stock "
        f"per day · the table shows today and the last {GL.RECENT_MAX}")
    monkeypatch.setattr(GL, "RECENT_MAX", 7)
    out = run([lane_doc(r, "skipped", "floor") for r in rs], store_of(rs), shown_ids={rs[1]["_id"]})
    assert out["block"]["span_text"].endswith("the last 7")
    shown_all = run([lane_doc(r, "skipped", "floor") for r in rs], store_of(rs), shown_ids={r["_id"] for r in rs})
    assert "the table shows" not in shown_all["block"]["span_text"]     # NEGATIVE: every row shown → no tail


def test_P7_no_bword_the_lead_leads_and_blocked_never_says_refused():
    rs = [raw(s, "bull_flag", hm=(10, i)) for i, s in enumerate(("P1", "P2", "P3"))]
    out = run([lane_doc(rs[0], "unfilled", "blocked"), lane_doc(rs[1], "skipped", "broker_gap"),
               lane_doc(rs[2], "unfilled", "never_triggered")], store_of(rs, [ledger_doc(rs[0], "loss")]))
    for r in out["rows"].values():
        assert r["track_text"].startswith(GU.TRACK_LEAD + " ")
    assert "refused" not in GU.REASON_TEXT["blocked"] and GU.REASON_TEXT["blocked"] == \
        "the order never reached the broker"
    text = json.dumps(out, ensure_ascii=False) + SRC + GU.honesty_text(D.isoformat())
    assert not B_WORD.search(text)


# ── P8 out of the total ──────────────────────────────────────────────────────────────────────────────────────────
def test_P8_never_triggered_and_dead_are_apart_broker_gap_is_in_with_the_stop_tail():
    nt, dead, gap = raw("SDA", "bull_flag", hm=(10, 0)), raw("PLAG", "kiss_fly", hm=(10, 1)), raw("DBGI", "bull_flag",
                                                                                                    hm=(10, 2))
    st = store_of([nt, dead, gap], [ledger_doc(nt, "win"), ledger_doc(dead, "win"), ledger_doc(gap, "win")])
    out = run([lane_doc(nt, "unfilled", "never_triggered"), lane_doc(dead, "skipped", "dead"),
               lane_doc(gap, "skipped", "broker_gap")], st)
    ls, total = lines_of(out["block"]), out["block"]["total"]
    for k in ("never_triggered", "dead"):
        assert ls[k]["in_total"] is False and ls[k]["counts"]["win"] == 1 and ls[k]["text"].endswith(GU.OUT_TAIL)
    assert ls["broker_gap"]["in_total"] is True and GU.OUT_TAIL not in ls["broker_gap"]["text"]
    assert (total["n"], total["counts"]["win"], total["counts"]["pct"]) == (1, 1, 100)
    assert total["text"].startswith(f"{GU.TOTAL_LABEL}: 1 · 1 win · 0 losses · 100% won")
    assert out["rows"][nt["_id"]]["track_text"].endswith(" · " + GU.OUT_TAIL)
    assert out["rows"][gap["_id"]]["track_text"].endswith(" · " + GU.STOP_TAIL["broker_gap"])
    assert GU.STOP_TAIL["broker_gap"] not in out["rows"][nt["_id"]]["track_text"]


def test_P8_NEGATIVE_the_stop_tail_only_on_a_decided_cell():
    gap = raw("DBGI", "bull_flag")
    out = run([lane_doc(gap, "skipped", "broker_gap")], store_of([gap], [ledger_doc(gap, "no_entry")]))
    assert out["rows"][gap["_id"]]["track_state"] == "no_entry"
    assert GU.STOP_TAIL["broker_gap"] not in out["rows"][gap["_id"]]["track_text"]


# ── P9 the comparison line ───────────────────────────────────────────────────────────────────────────────────────
def test_P9_fills_count_on_traded_only_in_flight_rows_count_nowhere():
    states = ("closed", "open", "closing", "waiting", "ordering", "ordered", "skipped")
    rs = [raw(f"S{i}", "bull_flag", hm=(10, i)) for i in range(len(states))]
    st = store_of(rs, [ledger_doc(r, "win") for r in rs])
    docs = [lane_doc(r, s, "floor" if s == "skipped" else None) for r, s in zip(rs, states)]
    out = run(docs, st)
    tr = out["block"]["traded"]
    assert (tr["n"], tr["counts"]["win"], tr["key"], tr["label"], tr["in_total"]) == (3, 3, "traded", GU.TRADED_LABEL,
                                                                                        False)
    assert tr["text"] == f"{GU.TRADED_LABEL}: 3 · 3 wins · 0 losses · 100% won" and GU.OUT_TAIL not in tr["text"]
    assert [ln["key"] for ln in out["block"]["lines"]] == ["floor"] and out["block"]["total"]["n"] == 1
    assert set(out["rows"]) == {rs[-1]["_id"]}                          # N1: only the row without a fill


# ── NEGATIVES ────────────────────────────────────────────────────────────────────────────────────────────────────
def _payload_scene(lane, monkeypatch):
    """A lane day (LDAY) at 15:45 ET: one row in every state + an alert after the cut-off (not seen) + one in flight."""
    names = (("WAIT", "waiting"), ("ORDG", "ordering"), ("ORDD", "ordered"), ("OPEN", "open"), ("CLSG", "closing"),
             ("CLSD", "closed"), ("SKIP", "skipped"), ("UNFL", "unfilled"))
    raws, docs = [], []
    for i, (sym, state) in enumerate(names):
        a = lane_alert(sym, "bull_flag", 2.0, 1.8, hm=(10, 10 + i))
        raws.append(a)
        extra = {"fill_px": 2.0, "fill_qty": 100, "qty": 100} if state in ("open", "closing", "closed") else {}
        if state == "closed":
            extra.update(exit_px=2.2, pnl_usd=20.0, r_mult=1.0, exit_kind="stop", exit_et="11:00")
        docs.append(seed(_id=a["_id"], symbol=sym, setup="bull_flag", alert_et=f"10:{10 + i}", trigger=2.0, stop=1.8,
                         state=state, skip_kind="floor" if state == "skipped" else None, **extra))
    late = lane_alert("LATE", "bull_flag", 2.0, 1.8, hm=(15, 40))
    newx = lane_alert("NEWX", "kiss_fly", 2.0, 1.8, hm=(10, 56))
    raws += [late, newx]
    s = lane(alerts=raws, docs=docs, now=_at(LDAY, 15, 45), positions=[_position("OPEN", 100, 2.0, 2.1)])
    d = date.fromisoformat(LDAY)
    led = [ledger_doc(a, "win", fill=(10, 30), exit_=(10, 40)) for a in raws if a["symbol"] not in ("LATE", "NEWX")]
    st = store_of(raws, led)
    monkeypatch.setattr(GU, "_store", lambda: st)
    return s, st, d


def test_N1_rows_with_a_fill_or_in_flight_carry_no_track_and_their_words_are_unchanged(lane, monkeypatch):
    s, st, _d = _payload_scene(lane, monkeypatch)
    p = GL.tab_payload()
    rows = {r["symbol"]: r for r in p["today"]}
    for sym in ("WAIT", "ORDG", "ORDD", "OPEN", "CLSG", "CLSD", "NEWX"):
        assert rows[sym]["track_state"] is None and rows[sym]["track_text"] is None, sym
    for sym in ("SKIP", "UNFL", "LATE"):
        assert rows[sym]["track_text"].startswith(GU.TRACK_LEAD), sym
    assert rows["NEWX"]["state"] == "not_seen"                          # N9: in flight → no track_*
    monkeypatch.setattr(GU, "read", lambda *a, **k: {"rows": {}, "block": None})
    q = GL.tab_payload()
    qrows = {r["symbol"]: r for r in q["today"]}
    for sym, r in rows.items():
        for k in GL.ROW_KEYS:
            if k not in GU.ROW_TRACK_KEYS:
                assert r[k] == qrows[sym][k], (sym, k)
    assert rows["CLSD"]["pnl_text"] == "+$20.00 · +1.00R" and rows["OPEN"]["pnl_text"].startswith("+$")


def test_N2_the_journal_and_status_never_move_with_the_block(lane, monkeypatch):
    s, st, _d = _payload_scene(lane, monkeypatch)
    base = GL.tab_payload()
    huge = {"rows": {r["id"]: {"track_state": "win", "track_text": "not traded · 🏁 WIN · best +999%"}
                     for r in base["today"]},
            "block": {"title": GU.TITLE, "total": {"counts": {"win": 10 ** 6}}, "lines": [], "traded": None,
                      "span_text": None, "honesty": None, "fault_text": None}}
    monkeypatch.setattr(GU, "read", lambda *a, **k: huge)
    big = GL.tab_payload()
    monkeypatch.setattr(GU, "read", lambda *a, **k: {"rows": {}, "block": None})
    empty = GL.tab_payload()
    assert base["journal"] == big["journal"] == empty["journal"]
    assert base["status"] == big["status"] == empty["status"]
    root = Path(GL.__file__).parent
    for name in ("journal.py", "exit_engine.py"):
        assert "gajjala_untraded" not in (root / name).read_text(encoding="utf-8"), name
    assert "track_" not in GL.journal_block.__code__.co_names and "untraded" not in \
        " ".join(GL.journal_block.__code__.co_names)


def test_N3_the_module_writes_nothing_and_names_no_order_path():
    rs = [raw("W1", "bull_flag"), raw("W2", "kiss_fly", hm=(11, 0), trig=3.0, stop=2.5)]
    st = store_of(rs, [ledger_doc(rs[0], "win")])
    run([lane_doc(rs[0], "skipped", "floor"), lane_doc(rs[1], "closed")], st)
    assert all(st.coll(n).writes == 0 for n in ST.ALL)
    code = SRC.split('"""', 2)[2]                                        # the module's code, after its docstring
    for pat in (r"\binsert", r"\.update\(", r"\bupdate_one\b", r"\breplace", r"\bdelete", r"\bsubmit",
                r"\bcancel_order\b", r"\bclose_position\b", r"\bflatten\(", r"trading\.broker", r"import broker",
                r"\bentries\b", r"exit_engine", r"\bEE\.", r"\bTE\."):
        assert not re.search(pat, code), pat


def test_N4_no_ledger_doc_today_is_pending_graded_tonight_never_a_loss():
    r = raw("PND", "bull_flag")
    out = run([lane_doc(r, "skipped", "floor")], store_of([r]), now=et(D, 11, 0))
    row = out["rows"][r["_id"]]
    assert row["track_state"] == "pending"
    assert row["track_text"] == f"{GU.TRACK_LEAD} not read yet — graded tonight {GC.LEDGER_GRADE_AT_ET} ET"
    c = lines_of(out["block"])["floor"]["counts"]
    assert (c["pending"], c["loss"], c["win"], c["pct"]) == (1, 0, 0, None)


def test_N5_a_memo_miss_never_fetches(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("the lane GET fetched bars")
    monkeypatch.setattr(LG, "_today_load", boom)
    from daytrading import data as DTD
    monkeypatch.setattr(DTD, "load_intraday", boom)
    calls = []

    def stub(sym, day, *, now=None, load="unset"):
        calls.append((sym, day, load))
        return LG.today_bars(sym, day, now=now, load=load)
    r = raw("MISS", "bull_flag")
    out = run([lane_doc(r, "skipped", "floor")], store_of([r]), now=et(D, 11, 0), today_bars=stub)
    assert calls == [("MISS", D, None)] and out["rows"][r["_id"]]["track_state"] == "pending"
    out = run([lane_doc(r, "skipped", "floor")], store_of([r]), now=et(D, 11, 0))      # the default seam, too
    assert out["rows"][r["_id"]]["track_state"] == "pending" and out["block"]["fault_text"] is None


def test_N5_a_memo_hit_reads_a_provisional_cell_marked_not_final():
    r = raw("HIT", "bull_flag")
    LG.today_bars("HIT", D, load=lambda s, d: (tape(D, 2.0, 1.8, "win"), False), now=et(D, 11, 0))
    out = run([lane_doc(r, "skipped", "floor")], store_of([r]), now=et(D, 11, 0))
    row = out["rows"][r["_id"]]
    assert row["track_state"] == "win" and "not final" in row["track_text"]
    ln = lines_of(out["block"])["floor"]
    assert ln["provisional"] is True and ln["text"].endswith(" · today not final")


@pytest.mark.parametrize("fault", ["alerts_none", "ledger_none", "alerts_raise", "ledger_raise"])
def test_N6_a_read_fault_serves_the_fault_and_no_track(fault, monkeypatch):
    r = raw("FLT", "bull_flag")
    st = store_of([r], [ledger_doc(r, "win")])
    if fault == "alerts_none":
        monkeypatch.setattr(st, "alert_rows", lambda days: None)
    elif fault == "ledger_none":
        st._injected[ST.LEDGER] = FakeColl([], fail=True)
    elif fault == "alerts_raise":
        monkeypatch.setattr(st, "alert_rows", lambda days: (_ for _ in ()).throw(RuntimeError("down")))
    else:
        monkeypatch.setattr(st, "_find_or_none", lambda name, q: (_ for _ in ()).throw(RuntimeError("down")))
    out = run([lane_doc(r, "skipped", "floor")], st)
    assert out["rows"] == {}
    b = out["block"]
    assert b["fault_text"] == GU.FAULT_TEXT and b["lines"] == [] and b["total"] is None and b["traded"] is None
    assert set(b) == set(GU.BLOCK_KEYS)


def test_N6_through_the_payload_today_and_recent_are_unchanged(lane, monkeypatch):
    s, st, _d = _payload_scene(lane, monkeypatch)
    st._injected[ST.LEDGER] = FakeColl([], fail=True)
    p = GL.tab_payload()
    assert p["untraded"]["fault_text"] == GU.FAULT_TEXT
    assert all(r["track_text"] is None and r["track_state"] is None for r in p["today"] + p["recent"])
    monkeypatch.setattr(GU, "read", lambda *a, **k: {"rows": {}, "block": None})
    q = GL.tab_payload()
    assert p["today"] == q["today"] and p["recent"] == q["recent"] and p["journal"] == q["journal"]

    def boom(*a, **k):
        raise RuntimeError("the module itself failed")
    monkeypatch.setattr(GU, "read", boom)
    r = GL.tab_payload()
    assert r["untraded"] is None and r["today"] == q["today"]
    assert set(r) == {"date", "armed", "mode", "as_of", "status", "today", "recent", "journal", "untraded"}


def test_N7_a_thin_r_row_is_out_of_w_l_counted_under_thin():
    r = raw("THN", "bull_flag", trig=2.0, stop=1.995)
    assert LG.alert_of(r, "aplus")["thin"] is True
    out = run([lane_doc(r, "skipped", "floor")], store_of([r], [ledger_doc(r, "win")]))
    c = lines_of(out["block"])["floor"]["counts"]
    assert (c["thin"], c["win"], c["pct"]) == (1, 0, None)
    assert out["rows"][r["_id"]]["track_text"].endswith(f" · {LG.THIN_TEXT} (not in the counts)")
    assert f"1 {LG.THIN_TEXT} (not in the %)" in lines_of(out["block"])["floor"]["text"]


def test_N8_a_duplicate_is_listed_with_the_tail_and_out_of_the_counts():
    a1 = raw("DUP", "bull_flag", hm=(10, 0))
    a2 = raw("DUP", "kiss_fly", hm=(10, 5))
    st = store_of([a1, a2], [ledger_doc(a1, "win"), ledger_doc(a2, "win")])
    out = run([lane_doc(a1, "skipped", "floor"), lane_doc(a2, "skipped", "floor")], st)
    ln = lines_of(out["block"])["floor"]
    assert (ln["n"], ln["dup"], ln["counts"]["win"]) == (2, 1, 1)
    assert ln["text"].endswith(LG._dup_tail(1))
    e, label = AL.SETUP_META["bull_flag"]
    want = LG.DUP_TEXT.format(at="10:00", setup=f"{e} {label}")
    assert out["rows"][a2["_id"]]["track_text"].endswith(" · " + want)
    assert want not in out["rows"][a1["_id"]]["track_text"]             # NEGATIVE: the first ring counts


def test_N9_N10_an_in_flight_not_seen_row_gets_nothing_a_row_without_a_ledger_row_says_so():
    r = raw("NOW", "bull_flag")
    in_flight = dict(lane_doc(r, "not_seen"), not_seen=None)
    out = run([in_flight], store_of([r], [ledger_doc(r, "win")]))
    assert out["rows"] == {} and out["block"]["lines"] == [] and out["block"]["span_text"] == GU.EMPTY_TEXT
    assert out["block"]["total"] is None and out["block"]["traded"]["n"] == 0
    orphan = {"_id": f"GG:{D}|ORPH|bull_flag", "date": D.isoformat(), "symbol": "ORPH", "setup": "bull_flag",
              "state": "skipped", "skip_kind": "floor"}
    out = run([orphan], store_of())
    assert out["rows"][orphan["_id"]] == {"track_state": "no_row",
                                          "track_text": f"{GU.TRACK_LEAD} {GU.NO_ROW_TEXT}"}
    ln = lines_of(out["block"])["floor"]
    assert ln["no_row"] == 1 and strip_counts(ln["counts"]) == strip_counts(LG._counts_blank("same"))
    assert ln["text"].endswith(" · 1 without a 🏁 row")


def test_N11_no_money_sign_in_any_track_text():
    rs = [raw(f"M{i}", s, hm=(10, i)) for i, s in enumerate(("bull_flag", "kiss_fly", "intraday_vcp"))]
    st = store_of(rs, [ledger_doc(rs[0], "win"), ledger_doc(rs[1], "loss", gap=True), ledger_doc(rs[2], "open")])
    out = run([lane_doc(rs[0], "skipped", "broker_gap"), lane_doc(rs[1], "skipped", "rounding"),
               lane_doc(rs[2], "unfilled")], st)
    assert len(out["rows"]) == 3 and all("$" not in r["track_text"] for r in out["rows"].values())


def test_N12_one_alert_read_and_one_ledger_find_by_ids_only(monkeypatch):
    rs = [raw("Q1", "bull_flag"), raw("Q2", "kiss_fly", d=date(2026, 11, 9))]
    st = store_of(rs, [ledger_doc(rs[0], "win")])
    calls = {"alerts": [], "finds": []}
    real_alerts, real_find = st.alert_rows, st._find_or_none
    monkeypatch.setattr(st, "alert_rows", lambda days: calls["alerts"].append(list(days)) or real_alerts(days))
    monkeypatch.setattr(st, "_find_or_none", lambda name, q: calls["finds"].append((name, q)) or real_find(name, q))
    monkeypatch.setattr(st, "ledger_docs", lambda *a, **k: (_ for _ in ()).throw(AssertionError("ledger_docs")))
    out = run([lane_doc(rs[0], "skipped", "floor"), lane_doc(rs[1], "closed")], st)
    assert calls["alerts"] == [["2026-11-09", D.isoformat()]]
    ids = sorted(LG.alert_of(r, "aplus")["id"] for r in rs)
    led_finds = [q for name, q in calls["finds"] if name == ST.LEDGER]   # alert_rows itself reads ALERTS through it
    assert len(led_finds) == 1 and [n for n, _q in calls["finds"]] == [ST.ALERTS, ST.LEDGER]
    assert set(led_finds[0]) == {"_id"} and sorted(led_finds[0]["_id"]["$in"]) == ids
    assert out["block"]["fault_text"] is None
    empty = store_of()                                                   # no live alert on that day → no ids
    seen = []
    monkeypatch.setattr(empty, "_find_or_none", lambda name, q: seen.append((name, q)) or [])
    out = run([lane_doc(raw("NONE", "bull_flag"), "skipped", "floor")], empty)
    assert [n for n, _q in seen] == [ST.ALERTS] and out["rows"][f"GG:{D}|NONE|bull_flag"]["track_state"] == "no_row"


def test_N13_no_ledger_doc_and_a_ledger_doc_without_same_read_pending_never_a_fault():
    a, b = raw("NOL", "bull_flag"), raw("NOS", "kiss_fly", hm=(11, 0), trig=3.0, stop=2.5)
    st = store_of([a, b], [ledger_doc(b, "win", with_same=False)])
    out = run([lane_doc(a, "skipped", "floor"), lane_doc(b, "skipped", "floor")], st, now=et(D, 11, 30))
    assert out["block"]["fault_text"] is None
    assert {r["track_state"] for r in out["rows"].values()} == {"pending"}
    assert lines_of(out["block"])["floor"]["counts"]["pending"] == 2


@pytest.mark.parametrize("why", ["after_cutoff", "off"])
def test_N14_todays_not_seen_rows_get_the_cell_and_are_never_counted(why):
    a, late = raw("CNT", "bull_flag"), raw("LATE", "kiss_fly", hm=(15, 40), trig=3.0, stop=2.5)
    st = store_of([a, late], [ledger_doc(a, "win"), ledger_doc(late, "win", fill=(15, 45), exit_=(15, 50))])
    docs = [lane_doc(a, "skipped", "floor")]
    synth = dict(lane_doc(late, "not_seen"), not_seen=why)
    without = run(docs, st)
    with_ = run(docs + [synth], st)
    assert with_["rows"][late["_id"]]["track_text"].startswith(GU.TRACK_LEAD + " WIN")
    assert with_["block"]["lines"] == without["block"]["lines"]
    assert with_["block"]["total"] == without["block"]["total"]
    assert with_["block"]["span_text"] == without["block"]["span_text"]


# ── the wiring ───────────────────────────────────────────────────────────────────────────────────────────────────
def test_wiring_the_payload_serves_the_block_and_the_row_cells(lane, monkeypatch):
    s, st, _d = _payload_scene(lane, monkeypatch)
    p = GL.tab_payload()
    blk = p["untraded"]
    assert set(blk) == set(GU.BLOCK_KEYS) and blk["fault_text"] is None and blk["title"] == GU.TITLE
    keys = [ln["key"] for ln in blk["lines"]]
    assert keys == ["unfilled", "floor"]
    assert blk["traded"]["n"] == 3 and blk["total"]["n"] == 2
    assert blk["honesty"] == GU.honesty_text(LDAY)
    assert list(p)[-1] == "untraded" and list(p)[-2] == "journal"
    json.dumps(p, allow_nan=False)


# ── 2026-11-11 review fixes (critic_ut items 2 + 4; item 1 pinned as the spec's P2) ─────────────────────────────────
def test_fix_open_reads_the_flags_own_word_never_open_at_the_close():
    o = raw("OPN", "bull_flag")
    st = store_of([o], [ledger_doc(o, "open")])
    for now in (et(D, 11, 0), et(D, 20, 0)):                          # intraday AND after the close
        ln = lines_of(run([lane_doc(o, "skipped", "floor")], st, now=now)["block"])["floor"]
        assert ln["counts"]["open"] == 1
        assert " · 1 open" in ln["text"], ln["text"]
        assert "open at the close" not in ln["text"]                    # NEGATIVE: never a close word before the close
        flag = LG._counts_text(ln["counts"], "same", False)               # the 🏁's own wording of the same counts
        assert f" · {ln['counts']['open']} open" in flag


def test_fix_each_date_reads_only_its_own_alerts_and_the_join_is_unchanged(monkeypatch):
    days = [date(2026, 11, 6), date(2026, 11, 9), D]
    rs = [raw(f"S{i}{j}", "bull_flag", d=d, hm=(10, j)) for i, d in enumerate(days) for j in range(3)]
    junk = [{"_id": "GG:nodate|X|bull_flag", "symbol": "X", "setup": "bull_flag", "state": "pushed"},
            {"_id": "GG:intdate|Y|bull_flag", "date": 20261110, "symbol": "Y", "setup": "bull_flag", "state": "pushed"}]
    st = store_of(rs + junk, [ledger_doc(r, "win") for r in rs])
    docs = [lane_doc(r, "skipped", "floor") for r in rs]
    real = GL._live_alerts
    seen = []

    def spy(d, al):
        seen.append((d, [x.get("date") for x in al]))
        return real(d, al)
    monkeypatch.setattr(GL, "_live_alerts", spy)
    out = run(docs, st)
    assert [d for d, _ in seen] == sorted(x.isoformat() for x in days)
    for d, got in seen:
        assert got and set(got) == {d}                                  # NEGATIVE: never another date's alerts
    monkeypatch.setattr(GL, "_live_alerts", real)
    isos = sorted(x.isoformat() for x in days)
    whole = {raw_["_id"]: a for d in isos for a, raw_ in real(d, st.alert_rows(isos))}   # the pre-fix join, every alert per date
    assert set(out["rows"]) == set(whole) == {r["_id"] for r in rs}
    assert lines_of(out["block"])["floor"]["counts"]["win"] == len(rs)


def test_P2_a_win_rows_R_is_only_the_flags_own_cell_words():
    w = raw("WR", "intraday_vcp")
    st = store_of([w], [ledger_doc(w, "win")])
    text = run([lane_doc(w, "skipped", "floor")], st)["rows"][w["_id"]]["track_text"]
    c = cell_of(st, w, et(D, 20, 0))
    words = c["text"] + (" — " + c["sub_text"] if c["sub_text"] else "")
    assert R_FIGURE.findall(text) == R_FIGURE.findall(words)          # any R printed is the 🏁's own, none added
