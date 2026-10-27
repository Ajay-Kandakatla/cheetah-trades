"""🚩 Gajjala's tab — GET /chart-maps/gajjala and `chart_maps.gajjala.tab.build` (BUILD_SPEC §3.4.1, 2026-10-13).

The board reads Mongo ONLY; every test hands `build()` an in-memory store (tests/test_gajjala_store.fake_store) and a
pinned clock. Ajay 2026-10-13: "Name the Tab Gajjala's he has multiple strategies..around this. He is volume and price
action based traded with short squeeze. He also has premarket and post market analysis."
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import date, datetime, time as dtime, timezone
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_store import FakeColl, fake_store

ET = ZoneInfo("America/New_York")
S = date(2026, 10, 13)                         # a Tuesday — a market day
PREV = date(2026, 10, 12)
GONE = date(2026, 10, 8)                       # one market day before the 3-session listed window


def utc(h, m, d=S):
    """An ET wall clock (EDT, −4) as UTC."""
    return datetime(d.year, d.month, d.day, h, m, tzinfo=ET).astimezone(timezone.utc)


NOW = utc(10, 31)


def R(setup, state, **kw):
    r = {"setup": setup, "state": state, "frame": "5m", "ready": False, "broke": False, "trigger": 4.12,
         "stop": 3.95, "risk_pct": 4.13, "entry_bar_t": None, "bars_since_entry": None, "criteria": [],
         "missed": [], "unjudged": [], "reason": "", "grade": None, "variant": None, "red_closes": 0,
         "flag_k": None, "base": None, "meta": {"structure_alive": True}}
    r.update(kw)
    return r


def bars(n=12, base=4.0, day=S):
    out = []
    for i in range(n):
        hh, mm = divmod(9 * 60 + 35 + 5 * i, 60)
        out.append({"t": f"{day.isoformat()} {hh:02d}:{mm:02d}", "o": base, "h": base + 0.1, "l": base - 0.1,
                    "c": base + 0.05, "v": 1000 + i})
    return out


def read_doc(sym, setups, *, ctx=None, day=S, **kw):
    b5, b15 = bars(12, day=day), bars(4, base=5.0, day=day)
    doc = {"_id": f"{day.isoformat()}|{sym}", "date": day.isoformat(), "symbol": sym, "setups": setups,
           "ctx": ctx or {},
           "tile": {"bars5": b5, "bars15": b15,
                    "curves5": [{"tone": "ema9", "label": "9 EMA", "values": [None] * 12},
                                {"tone": "ema21", "label": "21 EMA", "values": [1.0] * 12}],
                    "curves15": [{"tone": "ema9", "label": "9 EMA", "values": [2.0] * 4}],
                    "vol_avg5": {"period": 50, "label": "50-bar avg volume", "values": [100.0] * 12},
                    "vol_avg15": {"period": 50, "label": "50-bar avg volume", "values": [300.0] * 4}},
           "updated_at": NOW, "at": NOW}
    doc.update(kw)
    return doc


def scan_doc(sym, day=S, *, change=40.0, volume=2e6, price=4.05, sessions=None, tape="rth", typ="CS", prev=3.0):
    return {"_id": f"{day.isoformat()}|{sym}", "date": day.isoformat(), "symbol": sym,
            "first_qualified_at": NOW, "last_qualified_at": NOW, "at": NOW,
            "sessions": sessions or {"rth": True},
            "last": {"symbol": sym, "price": price, "prev_close": prev, "change_pct": change, "volume": volume,
                     "vol_src": "min_av",
                     "type": typ, "tape_session": tape}}


def latest(at=NOW, day=S, **kw):
    d = {"_id": "latest", "date": day.isoformat(), "at": at, "status": "ok", "tape_session": "rth",
         "strip": {"runners_100": 2, "runners_80": 4, "best_change_pct": 212.4, "best_symbol": "PFAI",
                   "quiet": False}}
    d.update(kw)
    return d


def store_with(reads=(), scans=(), passes=(), alerts=(), post=(), carry=(), halts=(), daily=()):
    return fake_store(**{ST.READS: FakeColl(list(reads)), ST.SCAN: FakeColl(list(scans)),
                         ST.PASSES: FakeColl(list(passes)), ST.ALERTS: FakeColl(list(alerts)),
                         ST.POST: FakeColl(list(post)), ST.AH_CARRY: FakeColl(list(carry)),
                         ST.HALTS: FakeColl(list(halts)), ST.DAILY: FakeColl(list(daily))})


def run_route(coro):
    """Own the loop and hand a fresh one back: `asyncio.run` CLOSES the loop and on py3.9 a later test that builds
    an asyncio primitive then finds none (the tests/test_bonde_live.py note)."""
    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(coro)
    finally:
        loop.close()
        asyncio.set_event_loop(asyncio.new_event_loop())


def _walk_strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _walk_strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _walk_strings(v)


# ── the ordering fixture (BUILD_SPEC §3.4.1 keys) ─────────────────────────────────────────────────────────────────
BF = "bull_flag"
ORDER_READS = {
    "AAA": R(BF, "aplus", entry_bar_t="2026-10-13 10:25", broke=True),
    "BBB": R(BF, "aplus", entry_bar_t="2026-10-13 10:30", broke=True),          # newer A+ first
    "CCC": R(BF, "triggered", entry_bar_t="2026-10-13 10:10", bars_since_entry=4, broke=True),
    "DDD": R(BF, "forming", ready=True, trigger=4.10),                          # last close 4.05 → 1.2% away
    "EEE": R(BF, "forming", ready=True, trigger=4.50),                          # 11% away
    "FFF": R(BF, "forming", ready=False, base={"bars": 0}, reason="waiting for the pullback bar"),
    "GGG": R(BF, "partial", missed=["k3_vol"], criteria=[{"key": "k3_vol", "label": "K3 pullback volume",
                                                          "ok": False}]),
    "HHH": R(BF, "partial", missed=["k2", "k3_vol"]),
    "III": R(BF, "stopped", entry_bar_t="2026-10-13 10:00", broke=True),
    "JJJ": R(BF, "invalid", reason="pullback longer than 5 bars"),
    "KKK": R(BF, "none", reason="no 2-bar demand leg today"),
}
EXPECTED = ["BBB", "AAA", "CCC", "DDD", "EEE", "FFF", "GGG", "HHH", "III"]


def ordering_store():
    reads = [read_doc(s, {BF: r}) for s, r in ORDER_READS.items()]
    scans = [scan_doc(s) for s in ORDER_READS]
    return store_with(reads=reads, scans=scans, passes=[latest()])


def test_setup_tiles_follow_the_spec_ordering_keys_exactly():
    out = GT.build("bull_flag", now=NOW, store=ordering_store())
    assert [t["symbol"] for t in out["tiles"]] == EXPECTED
    assert out["sub"] == "bull_flag" and out["sub_resolved_from"] == "param" and out["tf"] == "5m"


def test_partial_ties_break_on_change_then_symbol():
    reads = [read_doc("ZZZ", {BF: R(BF, "partial", missed=["k2"])}),
             read_doc("YYY", {BF: R(BF, "partial", missed=["k2"])}),
             read_doc("XXX", {BF: R(BF, "partial", missed=["k2"])})]
    scans = [scan_doc("ZZZ", change=90.0), scan_doc("YYY", change=40.0), scan_doc("XXX", change=40.0)]
    out = GT.build("bull_flag", now=NOW, store=store_with(reads=reads, scans=scans, passes=[latest()]))
    assert [t["symbol"] for t in out["tiles"]] == ["ZZZ", "XXX", "YYY"]


def test_invalid_and_none_reads_are_counted_never_tiled():
    out = GT.build("bull_flag", now=NOW, store=ordering_store())
    syms = {t["symbol"] for t in out["tiles"]}
    assert "JJJ" not in syms and "KKK" not in syms
    c = out["counts"]
    assert c["invalid"] == 1 and c["none"] == 1 and c["aplus"] == 2 and c["forming"] == 3
    assert c["partial"] == 2 and c["stopped"] == 1 and c["triggered"] == 1 and c["listed"] == len(ORDER_READS)
    assert c["awaiting_answer"] == 0
    sub = {s["key"]: s["count"] for s in out["subs"]}
    assert sub["bull_flag"] == len(EXPECTED) and sub["kiss_fly"] == 0 and sub["playbook"] is None
    # WIDENED 2026-10-16 — 🏁 Track record (the tenth sub, LAST) serves an int chip count (ledger.count_today)
    assert isinstance(sub["track_record"], int) and not isinstance(sub["track_record"], bool)
    assert [s["key"] for s in out["subs"]] == [k for k, _e, _l in GC.SUBS]


def test_tile_carries_lines_marker_curves_vol_avg_and_words():
    out = GT.build("bull_flag", now=NOW, store=ordering_store())
    t = out["tiles"][0]
    assert t["href"] == "/sepa/BBB?tab=supply"
    assert t["lines"] == [{"price": 4.12, "label": "BUY > 4.12", "tone": "buy", "text": "4.12"},      # `text` since 2026-10-21 (NUAI)
                          {"price": 3.95, "label": "STOP 3.95", "tone": "stop", "text": "3.95"}]
    assert t["markers"] == [{"date": "2026-10-13 10:30", "kind": "buy", "label": "A+"}]
    assert [c["tone"] for c in t["curves"]] == ["ema9", "ema21"] and len(t["bars"]) == 12
    assert t["vol_avg"]["values"] == [100.0] * 12
    g = t["gajjala"]
    assert g["state_label"].startswith("A+") and "UNMEASURED" in g["state_label"]
    assert "_last" not in g and "_bars_to_go" not in g
    for tile in out["tiles"]:
        assert "UNMEASURED" in tile["gajjala"]["state_label"]
    forming = next(x for x in out["tiles"] if x["symbol"] == "FFF")
    assert forming["markers"] == [] and "waiting for the pullback bar" in forming["gajjala"]["state_label"]


def test_broke_but_missed_says_so_and_unjudged_says_ema_warming():
    reads = [read_doc("MIS", {BF: R(BF, "partial", broke=True, missed=["k2"],
                                    criteria=[{"key": "k2", "label": "K2 leg volume", "ok": False}])}),
             read_doc("UNJ", {BF: R(BF, "partial", broke=True, unjudged=["ema"])})]
    out = GT.build("bull_flag", now=NOW, store=store_with(reads=reads, scans=[scan_doc("MIS"), scan_doc("UNJ")],
                                                          passes=[latest()]))
    by = {t["symbol"]: t["gajjala"]["state_label"] for t in out["tiles"]}
    assert by["MIS"].startswith("broke — not A+ · missed: K2 leg volume")
    assert "not judgeable: 9 EMA warming up" in by["UNJ"]


def test_unknown_sub_serves_the_default():
    out = GT.build("nonsense", now=NOW, store=ordering_store())
    assert out["sub"] == GC.DEFAULT_SUB == "bull_flag" and out["sub_resolved_from"] == "default"


# ── focus resolution (C9 deep links) ──────────────────────────────────────────────────────────────────────────
RS = "reversal_squeeze"


def _focus_store(with_claim=True, extra_alerts=()):
    reads = [read_doc("SQZ", {BF: R(BF, "partial", missed=["k2"]),
                              RS: R(RS, "aplus", entry_bar_t="2026-10-13 10:20", broke=True)})]
    alerts = list(extra_alerts)
    if with_claim:
        alerts.append({"_id": f"GG:{S.isoformat()}|SQZ|{RS}", "state": "pushed",
                       "claimed_at": utc(10, 21)})
    return store_with(reads=reads, scans=[scan_doc("SQZ")], passes=[latest()], alerts=alerts)


def test_focus_with_a_pushed_squeeze_claim_resolves_to_that_setup():
    out = GT.build("", focus="sqz", now=NOW, store=_focus_store())
    assert out["sub"] == "reversal_squeeze" and out["sub_resolved_from"] == "focus_alert"


def test_focus_with_a_shadow_claim_also_resolves():
    alerts = [{"_id": f"SHADOW:GG:{S.isoformat()}|SQZ|{BF}", "state": "shadow", "claimed_at": utc(10, 22)}]
    out = GT.build("", focus="SQZ", now=NOW, store=_focus_store(with_claim=False, extra_alerts=alerts))
    assert out["sub"] == "bull_flag" and out["sub_resolved_from"] == "focus_alert"


def test_focus_suppressed_claim_is_not_a_push():
    alerts = [{"_id": f"GG:{S.isoformat()}|SQZ|{BF}", "state": "suppressed_first15", "claimed_at": utc(9, 40)}]
    out = GT.build("", focus="SQZ", now=NOW, store=_focus_store(with_claim=False, extra_alerts=alerts))
    assert out["sub_resolved_from"] == "focus_read" and out["sub"] == RS     # the A+ read outranks the partial


def test_focus_without_a_claim_takes_the_best_ranked_read():
    out = GT.build("", focus="SQZ", now=NOW, store=_focus_store(with_claim=False))
    assert out["sub"] == RS and out["sub_resolved_from"] == "focus_read"


def test_focus_on_the_premarket_list_only_resolves_to_premarket():
    scans = [scan_doc("PMX", sessions={"premarket": True}, tape="premarket", volume=3e6)]
    out = GT.build("", focus="PMX", now=NOW, store=store_with(scans=scans, passes=[latest()]))
    assert out["sub"] == "premarket" and out["sub_resolved_from"] == "focus_list"


def test_explicit_sub_is_never_overridden_by_focus():
    out = GT.build("kiss_fly", focus="SQZ", now=NOW, store=_focus_store())
    assert out["sub"] == "kiss_fly" and out["sub_resolved_from"] == "param"


def test_empty_sub_and_no_focus_is_the_default():
    out = GT.build("", now=NOW, store=_focus_store())
    assert out["sub"] == "bull_flag" and out["sub_resolved_from"] == "default"


# ── frames ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_tf_15m_serves_the_15_minute_bars_curves_and_average():
    out = GT.build("bull_flag", tf="15m", now=NOW, store=ordering_store())
    t = out["tiles"][0]
    assert out["tf"] == "15m" and len(t["bars"]) == 4 and t["bars"][0]["o"] == 5.0
    assert t["vol_avg"]["values"] == [300.0] * 4 and [c["values"] for c in t["curves"]] == [[2.0] * 4]


def test_the_fade_defaults_to_15m_and_a_bad_tf_falls_back():
    st = store_with(reads=[read_doc("FAD", {"horizontal_fade": R("horizontal_fade", "forming", frame="15m")})],
                    scans=[scan_doc("FAD")], passes=[latest()])
    assert GT.build("horizontal_fade", now=NOW, store=st)["tf"] == "15m"
    assert GT.build("horizontal_fade", tf="5m", now=NOW, store=st)["tf"] == "5m"
    assert GT.build("bull_flag", tf="30m", now=NOW, store=st)["tf"] == "5m"           # NEGATIVE unknown tf


def test_an_empty_frame_falls_back_to_the_other_one():
    doc = read_doc("ONE", {BF: R(BF, "forming")})
    doc["tile"]["bars15"] = []
    out = GT.build("bull_flag", tf="15m", now=NOW, store=store_with(reads=[doc], scans=[scan_doc("ONE")],
                                                                    passes=[latest()]))
    assert len(out["tiles"][0]["bars"]) == 12


# ── session / pass / strip ────────────────────────────────────────────────────────────────────────────────────
def test_warming_when_no_pass_this_session():
    old = latest(at=utc(19, 55, PREV), day=PREV)
    out = GT.build("bull_flag", now=utc(4, 3), store=store_with(passes=[old]))
    assert out["pass"]["warming"] is True and out["pass"]["stale"] is False
    assert "warming" in out["pass"]["warming_text"]
    assert out["session"]["refresh_sec"] == GC.PASS_CADENCE_SEC


def test_stale_after_900_seconds_in_window_not_at_600():
    assert GC.STALE_AFTER_SEC == 900
    st = store_with(passes=[latest(at=utc(10, 15))])
    out = GT.build("bull_flag", now=utc(10, 31), store=st)                 # 16 min old
    assert out["pass"]["stale"] is True and "stale" in out["pass"]["stale_text"]
    out = GT.build("bull_flag", now=utc(10, 25), store=st)                 # NEGATIVE 600 s old
    assert out["pass"]["stale"] is False and "stale_text" not in out["pass"]
    assert out["pass"]["as_of_et"] == "10:15 ET" and out["pass"]["stale_after_sec"] == 900


def test_a_closed_day_shows_the_last_session_and_never_refreshes():
    sat = datetime(2026, 10, 17, 15, 0, tzinfo=timezone.utc)
    friday = date(2026, 10, 16)
    st = store_with(reads=[read_doc("FRI", {BF: R(BF, "aplus", entry_bar_t="2026-10-16 15:50")}, day=friday)],
                    scans=[scan_doc("FRI", day=friday)], passes=[latest(at=utc(20, 1, friday), day=friday)])
    out = GT.build("bull_flag", now=sat, store=st)
    s = out["session"]
    assert s["date"] == "2026-10-16" and s["label"] == "last session 2026-10-16"
    assert s["refresh_sec"] == 0 and s["tape"] == "closed" and s["badge"] == "closed · last session"
    assert out["pass"]["stale"] is False and out["pass"]["warming"] is False       # NEGATIVE: no alarm when closed
    assert [t["symbol"] for t in out["tiles"]] == ["FRI"]


def test_before_the_first_pass_the_board_is_the_last_session():
    out = GT.build("bull_flag", now=utc(3, 30), store=store_with())
    assert out["session"]["date"] == PREV.isoformat() and out["session"]["refresh_sec"] == 0


def test_first15_true_at_0931_false_at_0945_and_0929():
    assert GT.build("bull_flag", now=utc(9, 31), store=store_with())["session"]["first15"] is True
    assert GT.build("bull_flag", now=utc(9, 45), store=store_with())["session"]["first15"] is False
    assert GT.build("bull_flag", now=utc(9, 29), store=store_with())["session"]["first15"] is False
    t = GT.build("bull_flag", now=utc(9, 31), store=store_with())["session"]["first15_text"]
    assert t.startswith("⏳ first %d min" % GC.NO_TRADE_AFTER_OPEN_MIN)


def test_rth_open_pin_equals_the_session_clock():
    from daytrading import data as DTD
    assert GT._RTH_OPEN == DTD.ET_RTH_OPEN


def test_session_badges_follow_the_pass_tape():
    st = store_with(passes=[latest()])
    assert GT.build("bull_flag", now=utc(7, 0), store=st)["session"]["badge"] == "☀️ pre-market"
    assert GT.build("bull_flag", now=utc(12, 0), store=st)["session"]["badge"] == "RTH"
    assert GT.build("bull_flag", now=utc(18, 0), store=st)["session"]["badge"] == "🌙 after-hours"


def test_strip_text_is_served_from_the_pass_counts():
    out = GT.build("bull_flag", now=NOW, store=store_with(passes=[latest()]))
    s = out["strip"]
    assert s["runners_100"] == 2 and s["best_symbol"] == "PFAI" and "not quiet" in s["text"]
    quiet = latest(strip={"runners_100": 0, "runners_80": 0, "best_change_pct": 31.0, "best_symbol": "QQQX",
                          "quiet": True})
    assert "QUIET" in GT.build("bull_flag", now=NOW, store=store_with(passes=[quiet]))["strip"]["text"]
    empty = latest(strip={"quiet": None, "best_change_pct": None})
    assert "no runner" in GT.build("bull_flag", now=NOW, store=store_with(passes=[empty]))["strip"]["text"]


def test_graveyard_lists_only_names_that_dropped_off_today():
    scans = [scan_doc("OLDX", day=GONE), scan_doc("KEEP", day=GONE), scan_doc("KEEP", day=PREV)]
    out = GT.build("bull_flag", now=NOW, store=store_with(scans=scans, passes=[latest()]))
    assert out["graveyard_today"] == ["OLDX"] and "OLDX" in out["graveyard_text"]


# ── ☀️ / 🌙 ───────────────────────────────────────────────────────────────────────────────────────────────────
def _pm_store():
    scans = [scan_doc("BIGV", sessions={"premarket": True, "rth": True}),
             scan_doc("BIGC", sessions={"premarket": True}),
             scan_doc("RTHO", sessions={"rth": True})]                     # RTH-only qualifier: not ☀️
    levels = {"BIGV": {"volume": 9e6, "high": 4.6, "low": 3.2, "last": 4.2},
              "BIGC": {"volume": 2e6, "high": 5.8, "low": 3.1, "last": 5.7},
              "RTHO": {"volume": 9e9, "high": 9.0, "low": 1.0, "last": 5.0}}
    carry = [{"_id": PREV.isoformat(), "date": PREV.isoformat(), "pass_at": utc(20, 1, PREV),
              "names": {"CARY": {"ah_move_pct": 14.0, "ah_last": 2.0, "reg_close": 1.75}}}]
    return store_with(scans=scans, carry=carry, passes=[latest(premarket={"pm_levels": levels})])


def test_premarket_sorts_by_volume_then_change_with_carry_last():
    out = GT.build("premarket", now=NOW, store=_pm_store())
    assert [t["symbol"] for t in out["tiles"]] == ["BIGV", "BIGC", "CARY"]
    assert out["sort"] == "volume" and [s["key"] for s in out["sorts"]] == ["volume", "change"]
    by = {t["symbol"]: t["gajjala"] for t in out["tiles"]}
    assert by["BIGV"]["premarket"]["text"] == "pm volume 9.0M · +40.0%"
    assert by["BIGV"]["premarket"]["off_pm_high_text"] == "-12.0% off the premarket high"
    assert by["CARY"]["premarket"]["carry_text"] == ("🌙 carried from yesterday's after-hours +14.0% "
                                                     "(last after-hours pass 20:01)")
    assert "UNMEASURED" in by["CARY"]["state_label"] and by["CARY"]["setup"] == "premarket"
    out = GT.build("premarket", sort="change", now=NOW, store=_pm_store())
    assert [t["symbol"] for t in out["tiles"]] == ["BIGC", "BIGV", "CARY"] and out["sort"] == "change"
    assert GT.build("premarket", sort="bogus", now=NOW, store=_pm_store())["sort"] == "volume"   # NEGATIVE


def test_premarket_drops_a_name_under_the_k9_volume_floor(monkeypatch):
    monkeypatch.setattr(GC, "K9_PM_MIN_VOLUME", 5_000_000)
    out = GT.build("premarket", now=NOW, store=_pm_store())
    assert [t["symbol"] for t in out["tiles"]] == ["BIGV", "CARY"]


def test_premarket_without_stored_levels_uses_the_scanner_number_while_premarket():
    scans = [scan_doc("EARLY", sessions={"premarket": True}, tape="premarket", volume=3e6),
             scan_doc("LATE", sessions={"premarket": True}, tape="rth", volume=3e6)]     # no 1-min sum, now RTH
    out = GT.build("premarket", now=NOW, store=store_with(scans=scans, passes=[latest()]))
    assert [t["symbol"] for t in out["tiles"]] == ["EARLY"]


ROWS_AH = [{"symbol": "LOWG", "close_pos": 0.9, "ah_volume": 300_000, "ah_gain_pct": 6.0,
            "checked_text": "checked 19:40 ET", "reg_gain_pct": 41.0},
           {"symbol": "HIGG", "close_pos": 0.88, "ah_volume": 410_000, "ah_gain_pct": 8.4,
            "checked_text": "checked 19:46 ET", "reg_gain_pct": None}]


def _post_store(unchecked=12, rows=ROWS_AH):
    reads = [read_doc("PFAI", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:25")}),
             read_doc("STOP", {RS: R(RS, "stopped", entry_bar_t="2026-10-13 11:05")}),
             read_doc("FORM", {BF: R(BF, "forming")})]
    return store_with(reads=reads, scans=[scan_doc(s) for s in ("PFAI", "STOP", "FORM")],
                      passes=[latest(at=utc(19, 56), postmarket={"rows": list(rows), "unchecked_n": unchecked})])


def test_postmarket_orders_by_ah_gain_and_serves_unchecked_and_recap():
    out = GT.build("postmarket", now=utc(19, 58), store=_post_store())
    assert [t["symbol"] for t in out["tiles"]] == ["HIGG", "LOWG"]
    pm = out["postmarket"]
    assert pm["unchecked_n"] == 12 and pm["unchecked_text"] == "12 after-hours gainers not checked yet — next pass"
    g = {t["symbol"]: t["gajjala"]["postmarket"] for t in out["tiles"]}
    assert g["HIGG"]["checked_text"] == "checked 19:46 ET" and "AH +8.4%" in g["HIGG"]["text"]
    assert "top 12%" in g["HIGG"]["text"] and g["HIGG"]["exhaustion_text"] is None
    assert g["LOWG"]["exhaustion_text"] == "regular session +41.0%"
    rows = pm["recap"]["rows"]
    assert [r["symbol"] for r in rows] == ["PFAI", "STOP"]
    assert rows[0]["text"] == "🚩 Bull Flag A+ at 10:25 — broke 4.12, stop 3.95"
    assert "then stopped" in rows[1]["text"] and "UNMEASURED" in pm["recap"]["title"]
    assert out["subs"][[k for k, _e, _l in GC.SUBS].index("postmarket")]["count"] == 2
    # DECISIONS10 D7b (2026-10-16, "same place as other Gajjala rows"): each recap row links its setup card — the A+
    # push url, served; the text is unchanged
    from chart_maps.gajjala import potential as PT
    assert rows[0]["href"] == "/chart-maps?tab=gajjala&sub=bull_flag&focus=PFAI"
    assert rows[1]["href"] == "/chart-maps?tab=gajjala&sub=reversal_squeeze&focus=STOP"
    assert all(r["href"] == PT.deep_link(r["symbol"], r["setup"]) for r in rows)
    # WIDENED 2026-10-17: DECISIONS12 D2 — every recap row carries the 🚫 broker tag key (null for a non-owner, a TAG only)
    # WIDENED 2026-10-27: BUILD_SPEC26 §3.3 — and the 📌 trader tag key (null: no flagged trader posted these names)
    assert all(set(r) == {"symbol", "setup", "text", "href", "broker_text", "trader_text"}
               and r["broker_text"] is None and r["trader_text"] is None for r in rows)
    assert "FORM" not in {r["symbol"] for r in rows}                    # NEGATIVE: a forming read is never a row


def test_postmarket_unchecked_zero_or_junk_prints_nothing():
    out = GT.build("postmarket", now=utc(19, 58), store=_post_store(unchecked=0))
    assert out["postmarket"]["unchecked_n"] == 0 and out["postmarket"]["unchecked_text"] is None
    for junk in (True, -3, "7", None):                                   # NEGATIVE: never a guessed count
        assert GT.postmarket_rows({"postmarket": {"rows": [], "unchecked_n": junk}})[1] == 0


def test_postmarket_with_no_stored_rows_is_empty_not_an_error():
    out = GT.build("postmarket", now=utc(19, 58), store=store_with(passes=[latest()]))
    assert out["tiles"] == [] and out["postmarket"]["unchecked_n"] == 0 and out["empty_note"]
    assert GT.postmarket_rows(None) == ([], 0)


def test_the_last_session_pass_is_read_when_the_latest_pointer_is_older():
    p1 = dict(latest(at=utc(19, 50)), _id=f"{S.isoformat()}|19:50", postmarket={"rows": ROWS_AH[:1]})
    p2 = dict(latest(at=utc(20, 1)), _id=f"{S.isoformat()}|20:01", postmarket={"rows": ROWS_AH})
    st = store_with(passes=[p1, p2, latest(at=utc(20, 1, PREV), day=PREV)])
    assert GT.session_pass(st, st.latest_pass(), S)["_id"].endswith("20:01")


# ── placeholders / push / playbook ────────────────────────────────────────────────────────────────────────────
def test_awaiting_is_served_while_a_placeholder_is_none(monkeypatch):
    monkeypatch.setattr(GC, "HF_LEG_MIN_BARS", None)
    st = store_with(reads=[read_doc("FAD", {"horizontal_fade": R("horizontal_fade", "forming")})],
                    scans=[scan_doc("FAD")], passes=[latest()])
    out = GT.build("horizontal_fade", now=NOW, store=st)
    aw = [a for a in out["awaiting"] if a["setup"] == "horizontal_fade"]
    assert aw and aw[0]["his_call"] == "H3" and "waiting for your number (H3)" in aw[0]["text"]
    assert out["tiles"] == [] and out["counts"]["awaiting_answer"] == 1
    assert "None" not in json.dumps(out["awaiting"])


def test_no_awaiting_when_every_placeholder_is_answered():
    assert GT.build("bull_flag", now=NOW, store=store_with())["awaiting"] == []


def test_push_block_says_live_and_flips_with_the_constant(monkeypatch):
    # WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens") — the shipped block is the
    # live branch; the shadow branch stays (a flip back is one word), so it is pinned through the monkeypatch below
    out = GT.build("bull_flag", now=NOW, store=store_with())
    assert GC.GAJJALA_PUSH_MODE == "live"
    text = out["push"]["text"]
    assert out["push"]["mode"] == "live" and text.startswith("📲 Every A+ rings your phone")
    assert "never the first %d minutes" % GC.NO_TRADE_AFTER_OPEN_MIN in text and "never pre-market" in text
    assert "UNMEASURED" in text and "SHADOW" not in text                # NEGATIVE: no shadow word on the live line
    monkeypatch.setattr(GC, "GAJJALA_PUSH_MODE", "shadow")
    sh = GT.build("bull_flag", now=NOW, store=store_with())["push"]
    assert sh["mode"] == "shadow" and "SHADOW" in sh["text"]
    # WIDENED 2026-10-15 — 🧠 rings live, so the A+ shadow line names A+
    assert "A+ pushes are in SHADOW" in sh["text"] and str(GC.STUDY_SESSIONS) in sh["text"]
    assert "nothing reaches" not in sh["text"]                          # NEGATIVE: never the absolute claim


def test_playbook_sub_serves_the_playbook_and_no_tiles():
    out = GT.build("playbook", now=NOW, store=ordering_store())
    assert out["tiles"] == [] and out["playbook"]["sections"] and out["rules_section"] == "gajjala"
    assert "playbook" not in GT.build("bull_flag", now=NOW, store=ordering_store())


def test_board_note_is_unmeasured_and_quotes_his_decay():
    out = GT.build("bull_flag", now=NOW, store=store_with())
    assert out["note"].startswith("UNMEASURED") and "drastically reduced" in out["note"]


# ── chips ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_chips_red_closes_stopped_earlier_flag_psych_instrument_and_halts():
    doc = read_doc("CHP", {BF: R(BF, "forming", red_closes=GC.RED_CLOSES_WAIT + 1, flag_k=2)},
                   ctx={"float": {"shares": 3_100_000, "src": "float", "text": "Float 3.1M",
                                  "as_of": datetime(2026, 10, 13, 8, 0)}},
                   stopped_today={BF: "2026-10-13 10:05"})
    halts = [{"_id": f"{S.isoformat()}|CHP", "date": S.isoformat(), "symbol": "CHP", "n_halts": 2,
              "reasons": ["LUDP"]}]
    out = GT.build("bull_flag", now=NOW, store=store_with(reads=[doc], halts=halts, passes=[latest()],
                                                          scans=[scan_doc("CHP", price=4.80, typ="unknown",
                                                                          volume=13_020_000)]))
    c = out["tiles"][0]["gajjala"]["chips"]
    assert c["red_closes"].startswith(f"{GC.RED_CLOSES_WAIT + 1} red closes in a row")
    assert c["stopped_earlier"].startswith("stopped earlier today on this setup (entered 10:05, stopped)")
    assert c["flag_k"].startswith("flag #2 today")
    assert c["psych"] == ["🧱 $5 · 4.2% above — his profit-taking / climax level, not an entry"]
    assert c["instrument"] == GC.SCAN_UNKNOWN_TYPE_LABEL and c["halts"] == "⏸ halted ×2 (LUDP)"
    assert c["float"]["text"] == "Float 3.1M" and c["float"]["as_of"] == "2026-10-13T08:00:00"
    assert c["rotation"] == "🔄 float ×4.2" and c["volume"] == 13_020_000 and c["outside_rth"] is None


def test_chips_negative_cases_print_nothing():
    doc = read_doc("QUI", {BF: R(BF, "stopped", red_closes=GC.RED_CLOSES_WAIT, flag_k=None,
                                 entry_bar_t="2026-10-13 10:00")}, stopped_today={BF: "2026-10-13 10:05"})
    out = GT.build("bull_flag", now=NOW, store=store_with(reads=[doc], passes=[latest()],
                                                          scans=[scan_doc("QUI", price=9.0)]))
    c = out["tiles"][0]["gajjala"]["chips"]
    assert c["red_closes"] is None                     # exactly 3 = not "more than 3"
    assert c["stopped_earlier"] is None                # the read itself says stopped
    assert c["flag_k"] is None and c["psych"] == [] and c["instrument"] is None and c["halts"] is None
    assert c["float"] is None and c["rotation"] is None
    assert "squeeze_history" not in c                  # only on 🎾


def test_psych_chip_band_edges():
    assert GT.psych_chips(4.75) == []                                    # 5.26% above > the 5% band
    assert len(GT.psych_chips(4.77)) == 1                                 # 4.82% ≤ 5%
    assert GT.psych_chips(5.0) == [] and GT.psych_chips(None) == [] and GT.psych_chips(0) == []


def test_outside_rth_chip_and_squeeze_history_from_the_daily_doc():
    doc = read_doc("AHX", {RS: R(RS, "forming")})
    daily = [{"_id": f"{S.isoformat()}|AHX", "date": S.isoformat(), "symbol": "AHX",
              "squeeze_history": {"n": 3, "of": 30, "ledger_complete": True}}]
    out = GT.build("reversal_squeeze", now=utc(17, 0),
                   store=store_with(reads=[doc], daily=daily, scans=[scan_doc("AHX")], passes=[latest(at=utc(16, 56))]))
    c = out["tiles"][0]["gajjala"]["chips"]
    assert c["outside_rth"].startswith("after-hours — he uses limit orders only")
    assert c["squeeze_history"] == "🎾 squeeze history: 3 of last 30 sessions (≥50% range or a halt)"


def test_variant_and_grade_labels():
    # the long_flag band is empty since 2026-10-18 — synthetic variant, the mechanism is what is tested
    reads = [read_doc("LNG", {BF: R(BF, "partial", variant="long_flag", missed=["k4"])}),
             read_doc("VCB", {"intraday_vcp": R("intraday_vcp", "partial", grade="B", missed=["k7_ratio"],
                                                criteria=[{"key": "k7_ratio", "label": "K7 contraction",
                                                           "ok": False}])})]
    st = store_with(reads=reads, scans=[scan_doc("LNG"), scan_doc("VCB")], passes=[latest()])
    assert GT.build("bull_flag", now=NOW, store=st)["tiles"][0]["gajjala"]["variant_label"].startswith("long flag")
    g = GT.build("intraday_vcp", now=NOW, store=st)["tiles"][0]["gajjala"]
    assert g["grade_label"].startswith("B — imperfect · missed: K7 contraction")


# ── wording / JSON safety / the route ─────────────────────────────────────────────────────────────────────────
_B = re.compile("b" + "ounc", re.I)


def test_no_bare_reversal_ban_word_and_no_raw_datetime_anywhere():
    for sub in [k for k, _e, _l in GC.SUBS]:
        out = GT.build(sub, now=NOW, store=_post_store() if sub == "postmarket" else ordering_store())
        blob = json.dumps(out, ensure_ascii=False)                     # raises on a datetime
        assert not _B.search(blob), sub
        for s in _walk_strings(out):
            assert "None" != s and "nan" != s.lower()


def test_the_route_coerces_query_objects_scrubs_nan_and_reads_the_store(monkeypatch):
    from chart_maps import api as API
    from chart_maps import board as board_mod
    doc = read_doc("NAN", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:25", risk_pct=float("nan"))})
    st = store_with(reads=[doc], scans=[scan_doc("NAN", change=float("nan"))], passes=[latest()])
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    calls = {}
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: calls.setdefault("live", len(tiles)) and {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: calls.setdefault("now", 1))
    resp = run_route(API.chart_maps_gajjala())                      # every arg is a Query OBJECT here
    body = json.loads(resp.body)
    assert body["sub"] == "bull_flag" and body["tf"] == "5m" and [t["symbol"] for t in body["tiles"]] == ["NAN"]
    assert body["tiles"][0]["gajjala"]["risk_pct"] is None and body["tiles"][0]["gajjala"]["chips"]["change_pct"] is None
    assert calls == {"live": 1, "now": 1}
    assert "NaN" not in resp.body.decode()


def test_the_route_never_scans_or_fetches(monkeypatch):
    """The endpoint reads Mongo only: the scanner / bars / detector entry points are never called."""
    from chart_maps import api as API
    from chart_maps.gajjala import bars as BARS
    from chart_maps.gajjala import scanner as SC
    from sepa import prices
    st = ordering_store()
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)

    def boom(*a, **k):
        raise AssertionError("the endpoint must not scan or fetch")
    for mod, name in ((SC, "scan_rows"), (BARS, "frames_for"), (prices, "market_snapshot")):
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, boom)
    from chart_maps import board as board_mod
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)
    body = json.loads(run_route(API.chart_maps_gajjala(sub="bull_flag", tf="5m", focus="", sort="",
                                                         limit=3)).body)
    assert [t["symbol"] for t in body["tiles"]] == EXPECTED[:3]
    # WIDENED 2026-10-16 — every sub EXCEPT 🏁 track_record: 🏁 reads today's 1-minute bars on its own sub only
    # (ledger.today_read; its own route tests inject the loader — tests/test_gajjala_track_record_tab.py)
    for k in [k for k, _e, _l in GC.SUBS if k != GC.LEDGER_SUB]:
        body = json.loads(run_route(API.chart_maps_gajjala(sub=k, tf="", focus="", sort="", limit=3)).body)
        assert body["sub"] == k, k


def test_limit_caps_the_tiles_and_route_limit_bounds_are_the_board_ones():
    from chart_maps import board as board_mod
    assert GC.TILE_LIMIT_DEFAULT == board_mod.LIMIT_DEFAULT and GC.TILE_LIMIT_MAX == board_mod.LIMIT_MAX
    assert len(GT.build("bull_flag", limit=2, now=NOW, store=ordering_store())["tiles"]) == 2
    assert len(GT.build("bull_flag", limit="x", now=NOW, store=ordering_store())["tiles"]) == len(EXPECTED)


def test_a_dead_store_serves_an_empty_board_not_an_error():
    dead = fake_store(**{n: FakeColl(fail=True) for n in ST.ALL})
    out = GT.build("bull_flag", now=NOW, store=dead)
    assert out["tiles"] == [] and out["pass"]["warming"] is True and out["counts"]["listed"] == 0


# ── WP5a minors (2026-10-13 E2) ───────────────────────────────────────────────────────────────────────────────
HF = "horizontal_fade"


def _fade_store(frame, state="aplus", entry="2026-10-13 10:25"):
    return store_with(reads=[read_doc("FAD", {HF: R(HF, state, frame=frame, entry_bar_t=entry, broke=True)})],
                      scans=[scan_doc("FAD")], passes=[latest()])


def test_a_5m_fallback_fade_read_serves_its_own_5m_bars_when_no_tf_is_asked():
    out = GT.build(HF, now=NOW, store=_fade_store("5m"))
    t = out["tiles"][0]
    assert out["tf"] == "15m"                                          # the sub default is unchanged
    assert t["tf"] == "5m" and len(t["bars"]) == 12 and t["bars"][0]["o"] == 4.0     # NEGATIVE: not the 15m frame
    assert t["vol_avg"]["values"] == [100.0] * 12
    assert t["markers"] == [{"date": "2026-10-13 10:25", "kind": "buy", "label": "A+"}]


def test_a_15m_fade_read_still_serves_15m_bars_when_no_tf_is_asked():
    t = GT.build(HF, now=NOW, store=_fade_store("15m", entry="2026-10-13 09:45"))["tiles"][0]
    assert t["tf"] == "15m" and len(t["bars"]) == 4 and t["bars"][0]["o"] == 5.0
    assert t["markers"] == [{"date": "2026-10-13 09:45", "kind": "buy", "label": "A+"}]


def test_a_read_without_a_frame_takes_the_sub_default():
    st = store_with(reads=[read_doc("FAD", {HF: R(HF, "forming", frame=None)})], scans=[scan_doc("FAD")],
                    passes=[latest()])
    assert GT.build(HF, now=NOW, store=st)["tiles"][0]["tf"] == "15m"
    assert GT.tile_tf({"frame": "30m"}, "", "5m") == "5m"                 # NEGATIVE: an unknown frame is not served


def test_an_explicit_15m_toggle_on_a_5m_read_serves_no_off_bar_marker():
    out = GT.build(HF, tf="15m", now=NOW, store=_fade_store("5m"))
    t = out["tiles"][0]
    assert out["tf"] == "15m" and t["tf"] == "15m" and len(t["bars"]) == 4
    assert "2026-10-13 10:25" not in {b["t"] for b in t["bars"]}
    assert t["markers"] == []                                          # NEGATIVE: the 10:25 A+ has no 15m bar
    assert t["lines"] and t["gajjala"]["entry_bar_t"] == "2026-10-13 10:25"   # the read itself is still served
    t5 = GT.build(HF, tf="5m", now=NOW, store=_fade_store("5m"))["tiles"][0]
    assert t5["markers"] and t5["markers"][0]["date"] == "2026-10-13 10:25"


def test_an_explicit_tf_keeps_a_marker_whose_bar_is_served():
    st = store_with(reads=[read_doc("BBX", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 09:40")})],
                    scans=[scan_doc("BBX")], passes=[latest()])
    t = GT.build("bull_flag", tf="15m", now=NOW, store=st)["tiles"][0]
    assert t["tf"] == "15m" and t["markers"] == [{"date": "2026-10-13 09:40", "kind": "buy", "label": "A+"}]


def test_the_empty_frame_fallback_reports_the_frame_it_served():
    doc = read_doc("ONE", {BF: R(BF, "aplus", entry_bar_t="2026-10-13 10:25")})
    doc["tile"]["bars15"] = []
    t = GT.build("bull_flag", tf="15m", now=NOW, store=store_with(reads=[doc], scans=[scan_doc("ONE")],
                                                                  passes=[latest()]))["tiles"][0]
    assert t["tf"] == "5m" and len(t["bars"]) == 12 and t["markers"][0]["date"] == "2026-10-13 10:25"


def test_quiet_line_is_built_from_the_constant_with_his_words_quoted(monkeypatch):
    quiet = {"runners_100": 0, "runners_80": 0, "best_change_pct": 31.0, "best_symbol": "QQQX", "quiet": True}
    t = GT.strip_text(quiet)
    assert "best runner under %g%%" % GC.SA_QUIET_BEST_PCT in t
    assert "“the maximum runners would be 30%–40%”, S8 44:37" in t
    assert "best runner of 30–40%" not in t                            # NEGATIVE: the old hard-coded band is gone
    monkeypatch.setattr(GC, "SA_QUIET_BEST_PCT", 35.0)
    t2 = GT.strip_text(quiet)
    assert "best runner under 35%" in t2 and "under 40%" not in t2
    assert "under 35%" in GT.strip_text(dict(quiet, quiet=False, best_change_pct=80.0))


def test_tab_source_reuses_the_session_clock_and_no_hard_coded_band():
    import inspect
    from daytrading import data as DTD
    src = inspect.getsource(GT)
    assert GT._RTH_OPEN is DTD.ET_RTH_OPEN
    assert "dtime(9, 30)" not in src and "30–40%" not in src           # NEGATIVE: never retyped


def test_a_held_none_read_counts_as_awaiting_only(monkeypatch):
    monkeypatch.setattr(GC, "HF_LEG_MIN_BARS", None)
    st = store_with(reads=[read_doc("HLD", {HF: R(HF, "none", reason="awaiting your number (H3)")}),
                           read_doc("FRM", {HF: R(HF, "forming")})],
                    scans=[scan_doc("HLD"), scan_doc("FRM")], passes=[latest()])
    c = GT.build(HF, now=NOW, store=st)["counts"]
    assert c["awaiting_answer"] == 2 and c["none"] == 0                # NEGATIVE: never also "none"
    assert c["forming"] == 1


def test_an_awaiting_reason_without_a_held_constant_is_awaiting_not_none():
    st = store_with(reads=[read_doc("AWT", {BF: R(BF, "none", reason="awaiting your number (H1)")}),
                           read_doc("NON", {BF: R(BF, "none", reason="no 2-bar demand leg today")})],
                    scans=[scan_doc("AWT"), scan_doc("NON")], passes=[latest()])
    c = GT.build("bull_flag", now=NOW, store=st)["counts"]
    assert c["awaiting_answer"] == 1 and c["none"] == 1                # the plain none still counts as none


def test_after_the_last_pass_today_the_badge_says_closed_not_last_session():
    st = store_with(passes=[latest(at=utc(20, 1))])
    s = GT.build("bull_flag", now=utc(21, 30), store=st)["session"]
    assert s["label"] == "today" and s["tape"] == "closed" and s["refresh_sec"] == 0
    assert s["badge"] == GT.BADGE_CLOSED_TODAY == "closed" and "last session" not in s["badge"]
    s = GT.build("bull_flag", now=utc(23, 59), store=st)["session"]
    assert s["label"] == "today" and s["badge"] == "closed"
    s = GT.build("bull_flag", now=utc(3, 59, date(2026, 10, 14)), store=st)["session"]   # NEGATIVE: next morning
    assert s["label"] == "last session 2026-10-13" and s["badge"] == "closed · last session"


def test_the_stopped_earlier_chip_names_the_entry_bar_not_the_stop():
    doc = read_doc("STP", {BF: R(BF, "forming")}, stopped_today={BF: "2026-10-13 10:05"})
    st = store_with(reads=[doc], scans=[scan_doc("STP")], passes=[latest()])
    chip = GT.build("bull_flag", now=NOW, store=st)["tiles"][0]["gajjala"]["chips"]["stopped_earlier"]
    assert "(entered 10:05, stopped)" in chip and "(10:05)" not in chip
    nodate = read_doc("STQ", {BF: R(BF, "forming")}, stopped_today={BF: True})
    st = store_with(reads=[nodate], scans=[scan_doc("STQ")], passes=[latest()])
    chip = GT.build("bull_flag", now=NOW, store=st)["tiles"][0]["gajjala"]["chips"]["stopped_earlier"]
    assert chip.startswith("stopped earlier today on this setup — ") and "entered" not in chip   # NEGATIVE: no time


# ── 🎾 lowest float on top (DECISIONS13 D3, Ajay 2026-10-18 "for the float lower the better is what I wanna follow so
#    sort it by lowest on top") ─────────────────────────────────────────────────────────────────────────────────────
def _daily(sym, shares, suspect=None):
    fr = {"shares": shares, "src": "float", "text": None, "as_of": S.isoformat(), "suspect": suspect}
    return {"_id": f"{S.isoformat()}|{sym}", "date": S.isoformat(), "symbol": sym, "float": fr}


def _squeeze_store(reads: dict, floats: dict, suspect=()):
    docs = [read_doc(s, {RS: r}) for s, r in reads.items()]
    daily = [_daily(s, sh, "float_exceeds_shares_out" if s in suspect else None) for s, sh in floats.items()]
    return store_with(reads=docs, daily=daily, scans=[scan_doc(s) for s in reads], passes=[latest()])


def _syms(out):
    return [t["symbol"] for t in out["tiles"]]


def test_squeeze_tiles_order_by_float_ascending_within_state():
    """Three forming squeeze reads, same bars to go: 9M / 2M / unknown → 2M, 9M, unknown (the symbol order is the
    reverse, so the float is what moved them)."""
    reads = {s: R(RS, "forming", base={"bars": 0}) for s in ("AAA", "BBB", "CCC")}
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads, {"AAA": None, "BBB": 9_000_000, "CCC": 2_000_000}))
    assert _syms(out) == ["CCC", "BBB", "AAA"]
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads, {"BBB": 9_000_000, "CCC": 2_000_000}))   # no daily doc
    assert _syms(out) == ["CCC", "BBB", "AAA"]
    reads0 = {s: R(RS, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads0, {"AAA": 0, "BBB": 5_000_000}))     # 0 = unknown, last
    assert _syms(out) == ["BBB", "AAA"]


def test_squeeze_aplus_stays_above_forming_whatever_the_float(monkeypatch):
    """within_state (shipped, MINE): an A+ at 9M stays above a forming name at 2M; GC.RS_FLOAT_SORT "global" (HIS CALL
    Q1) puts the float above the state rank — the forming 2M name first."""
    reads = {"APL": R(RS, "aplus", entry_bar_t="2026-10-13 10:20", broke=True),
             "FRM": R(RS, "forming", base={"bars": 0})}
    floats = {"APL": 9_000_000, "FRM": 2_000_000}
    assert GC.RS_FLOAT_SORT == "within_state"
    assert _syms(GT.build(RS, now=NOW, store=_squeeze_store(reads, floats))) == ["APL", "FRM"]
    monkeypatch.setattr(GC, "RS_FLOAT_SORT", "global")
    assert _syms(GT.build(RS, now=NOW, store=_squeeze_store(reads, floats))) == ["FRM", "APL"]


def test_squeeze_float_ties_keep_todays_tiebreaks():
    """Same state, same float → today's key decides (newest A+ entry first)."""
    reads = {"OLD": R(RS, "aplus", entry_bar_t="2026-10-13 10:00", broke=True),
             "NEW": R(RS, "aplus", entry_bar_t="2026-10-13 10:30", broke=True),
             "LOW": R(RS, "aplus", entry_bar_t="2026-10-13 09:50", broke=True)}
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads, {"OLD": 4_000_000, "NEW": 4_000_000, "LOW": 1_000_000}))
    assert _syms(out) == ["LOW", "NEW", "OLD"]


def test_suspect_ineligible_float_sorts_last(monkeypatch):
    """A float on file above shares out under FLOAT_SUSPECT_POLICY "ineligible" (the context.rotation policy) is
    unknown → last; under "shares_out" the served shares count again (NEGATIVE of the policy)."""
    reads = {s: R(RS, "forming", base={"bars": 0}) for s in ("SUS", "OKK")}
    floats = {"SUS": 1_000_000, "OKK": 8_000_000}
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "ineligible")
    assert _syms(GT.build(RS, now=NOW, store=_squeeze_store(reads, floats, suspect=("SUS",)))) == ["OKK", "SUS"]
    assert GT._float_shares_of({"shares": 1_000_000, "suspect": "float_exceeds_shares_out"}) is None
    monkeypatch.setattr(GC, "FLOAT_SUSPECT_POLICY", "shares_out")
    assert _syms(GT.build(RS, now=NOW, store=_squeeze_store(reads, floats, suspect=("SUS",)))) == ["SUS", "OKK"]


def test_float_shares_of_unknowns():
    assert GT._float_shares_of({"shares": 2_500_000.0, "suspect": None}) == 2_500_000
    for fr in (None, {}, {"shares": None}, {"shares": 0}, {"shares": -5}, {"shares": "x"}, "Float 2M"):
        assert GT._float_shares_of(fr) is None, fr


def test_order_key_is_byte_identical_off_the_squeeze_sub():
    """NEGATIVE: the float slot exists only on a squeeze card built by setup_tile; other setups (and the cross-setup
    focus pick, which never stashes `_float_shares`) keep today's 4-tuple."""
    g = {"setup": BF, "state": "aplus", "entry_bar_t": "2026-10-13 10:30", "_float_shares": 1}
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (0, -202610131030.0, 0.0, "X")
    g = {"setup": RS, "state": "aplus", "entry_bar_t": "2026-10-13 10:30"}
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (0, -202610131030.0, 0.0, "X")
    g = dict(g, _float_shares=3_000_000)
    assert GT.order_key({"symbol": "X", "gajjala": g}) == (0, 3_000_000.0, -202610131030.0, 0.0, "X")
    assert GT.order_key({"symbol": "X", "gajjala": dict(g, _float_shares=None)})[1] == float("inf")


def test_NEGATIVE_bull_flag_ordering_is_unchanged_with_floats_on_file():
    """The bull-flag EXPECTED order holds even when every read carries a float (the float never sorts another sub)."""
    floats = {s: 1_000_000 * (len(ORDER_READS) - i) for i, s in enumerate(ORDER_READS)}
    reads = [read_doc(s, {BF: r}, ctx={"float": {"shares": floats[s], "src": "float", "suspect": None}})
             for s, r in ORDER_READS.items()]
    st = store_with(reads=reads, scans=[scan_doc(s) for s in ORDER_READS], passes=[latest()])
    assert _syms(GT.build(BF, now=NOW, store=st)) == EXPECTED
    assert _syms(GT.build(BF, now=NOW, store=ordering_store())) == EXPECTED


def test_order_note_served_on_the_squeeze_sub_only():
    """The ordering word is served (tab.RS_ORDER_TEXT), the FE types none; null on every other setup sub (NEGATIVE)
    and absent off the setup subs."""
    assert GT.RS_ORDER_TEXT == "🎾 lowest float on top"
    reads = {"AAA": R(RS, "forming", base={"bars": 0})}
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads, {"AAA": 2_000_000}))
    assert out["order_note"] == GT.RS_ORDER_TEXT
    for sub in GC.SETUPS:
        if sub != RS:
            out = GT.build(sub, now=NOW, store=ordering_store())
            assert "order_note" in out and out["order_note"] is None, sub
    for sub in ("premarket", "postmarket", "playbook"):
        assert GT.build(sub, now=NOW, store=ordering_store()).get("order_note") is None, sub


def test_no_private_key_reaches_the_served_squeeze_tiles():
    """`_strip_private` pops `_float_shares` (with `_last` / `_bars_to_go`): no `_`-key in any served tile's JSON."""
    reads = {s: R(RS, "forming", base={"bars": 0}) for s in ("AAA", "BBB")}
    out = GT.build(RS, now=NOW, store=_squeeze_store(reads, {"AAA": 9_000_000, "BBB": 2_000_000}))
    assert out["tiles"]
    for t in out["tiles"]:
        blob = json.dumps(t)
        assert "_float_shares" not in blob and '"_last"' not in blob and '"_bars_to_go"' not in blob
        assert not [k for k in t["gajjala"] if k.startswith("_")]
