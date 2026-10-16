"""🏁 Track record on Gajjala's tab — the tab branch, the chip and the route (BUILD_SPEC9 §3.6 / §3.7 / WP-B, 2026-10-16).

Ajay 2026-10-16, verbatim: "also can you track all Gajjals stocks and keep a new tab to show wins vs losses. To see a
percentage and the ticker." / "We are not looking for winners just in time but when they got in to our alerts if they
made it or not. Like XLAB today was a winner I made good money on it"

ledger.py owns the rows, the grader and every served string; these tests pin what tab.py / api.py add: the tenth sub
LAST with its chip count, `?sub=track_record&span=…` routed to `ledger.served_block`, the ONE 1-minute "today so far"
read in the route on 🏁 only (never on another sub), and that a raising piece never takes the board down. NEGATIVES are
mandatory. Every route test injects `today_read` or the loaders — the network is never touched.

The fixture day: XLAB's two 🧠 pushes of 2026-10-16 as on file (DECISIONS9 / BUILD_SPEC9 §1.2), graded "today so far" on
the REAL 1-minute tape (tests/fixtures/gajjala/xlab_2026_10_16_1m.json, 04:00–11:10 ET) at 11:11:30 ET — the last
minute the tape holds, so the served "through" never claims more than the fixture read (AMENDMENTS9 E6); the 10-15
XLAB 🌀 15:11 push (trigger 1.22 / stop 1.16, AMENDMENTS9 E1) graded by the REAL nightly step on a SYNTHETIC 10-15 tape;
a 10-15 after-hours push (AHX, same session = 10-16, read on a flat synthetic 10-16 tape under its trigger with no
split — `no_split`); three A+ shadow docs (PMI / TGL / HCAI — synthetic plans on a flat synthetic tape under their
triggers); a pushed potential with no plan; one whose trigger never trades.

GOLDEN: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_track_record_tab.py -k golden` writes the FE fixture
(frontend/src/components/__fixtures__/gajjala_track_record_golden_2026_10_16.json); without the env the test proves the
file IS the served payload, byte for byte. The golden's own store (golden_store) adds ONE live A+ entry (XLAB 🌀 at
09:45 ET, 2026-10-16 polish) so its served `entries_text` is real; the shared `store` fixture never carries it.
"""
from __future__ import annotations

import inspect
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import _walk_strings, run_route

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D16 = date(2026, 10, 16)                        # a Friday — a market day
D15 = date(2026, 10, 15)
NOW = datetime(2026, 10, 16, 11, 11, 30, tzinfo=ET)    # the real tape's last minute (11:10) has closed + settled
TAPE = Path(__file__).resolve().parent / "fixtures" / "gajjala" / "xlab_2026_10_16_1m.json"
GOLDEN = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "__fixtures__" /
          "gajjala_track_record_golden_2026_10_16.json")
RECIPE = "GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_track_record_tab.py -k golden"
B_WORD = re.compile("b" + "ounc", re.I)
NAMES = re.compile(r"\bSEPA\b|minervini|bonde|\bTLSW\b|\bTTLAC\b", re.I)
W1 = "🏁 Track record — every Gajjala alert that rang, graded by GG's trade math · UNMEASURED"
# WIDENED 2026-10-16: Ajay flipped the A+ kind live ("you alert me when that happens") — W3 is the AMENDMENTS10 F3 text
# (the live A+ entries on their own 🎯 line, never pooled with the 🧠 %)
W3 = ("A ledger of the alerts as sent, graded by GG's own trade math — not a backtest of a strategy, and small n early. "
      "A+ rows from the shadow period (never sent) stay out of the %; A+ entries sent live are counted on their own 🎯 "
      "line, not pooled with the 🧠 pushes — an A+ exists only once the trade survived its entry bar. The 2026-10-14 "
      "study of the five setups read NULL — no edge over a matched placebo (docs/gajjala/study_2026_10_13.md); this "
      "record does not change that.")


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    LG._TODAY_MEMO.clear()                      # another test's memoised XLAB tape must never leak in
    LG._TODAY_SPLIT.clear()                     # nor another test's answered split check
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()


# ── the fixture day ──────────────────────────────────────────────────────────────────────────────────────────────
def _et(d, hh, mm, ss=0, us=0):
    return datetime(d.year, d.month, d.day, hh, mm, ss, us, tzinfo=ET)


def pot_doc(d, sym, setup, at, *, trigger, stop, px, kind="building", mode="normal", state="pushed"):
    """A 🧠 tracker doc as potential.track() + the claim/settle leave it (BUILD_SPEC9 §1.1 / §1.2 field list)."""
    at_et = at.astimezone(ET).strftime("%H:%M")
    bar = at.astimezone(ET).replace(second=0, microsecond=0) - timedelta(minutes=1)
    return {"_id": ST.potential_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "frame": "5m", "first_seen": at.astimezone(UTC).replace(tzinfo=None), "first_seen_et": at_et,
            "first_seen_mode": mode, "first_kind": kind, "first_px": px, "first_trigger": trigger,
            "first_stop": stop, "first_risk_pct": None, "first_bar_t": bar.strftime("%Y-%m-%d %H:%M"),
            "last": {"px": px, "trigger": trigger, "stop": stop, "state": "forming", "at_et": at_et},
            "push": {"state": state, "at": at.astimezone(UTC).isoformat(), "at_et": at_et, "kind_at_push": kind,
                     "result": {"sent": 1, "failed": 0, "total_targets": 1}}}


def shadow_doc(d, sym, setup, at, *, trigger, stop, price):
    """An A+ SHADOW claim as alerts.py writes it (BUILD_SPEC9 §1.1): `would_push` = the payload dict, never sent."""
    from chart_maps.gajjala import alerts as AL
    return {"_id": AL.shadow_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup,
            "mode": "shadow", "entry_bar_t": at.astimezone(ET).strftime("%Y-%m-%d %H:%M"), "frame": "5m",
            "trigger": trigger, "stop": stop, "risk_pct": round((trigger - stop) / trigger * 100, 2), "price": price,
            "state": "shadow", "would_push": {"title": f"{sym} A+"}, "at": at.astimezone(UTC).isoformat()}


POTS = (
    pot_doc(D16, "XLAB", "horizontal_fade", datetime(2026, 10, 16, 12, 51, 0, 771870, tzinfo=UTC),
            trigger=1.81, stop=1.70, px=1.73),
    pot_doc(D16, "XLAB", "intraday_vcp", datetime(2026, 10, 16, 13, 1, 0, 983961, tzinfo=UTC),
            trigger=1.85, stop=1.75, px=1.7901),
    pot_doc(D16, "NPLN", "bull_flag", _et(D16, 10, 2), trigger=None, stop=None, px=3.10),          # no plan
    pot_doc(D16, "NOEN", "kiss_fly", _et(D16, 10, 12), trigger=9.99, stop=9.50, px=9.70),         # never trades
    pot_doc(D16, "JOIN", "bull_flag", _et(D16, 10, 22), trigger=4.0, stop=3.8, px=3.9, mode=ST.JOINED_MODE),
    pot_doc(D16, "NOTG", "bull_flag", _et(D16, 10, 32), trigger=4.0, stop=3.8, px=3.9, state="no_target"),
    pot_doc(D15, "XLAB", "intraday_vcp", _et(D15, 15, 11), trigger=1.22, stop=1.16, px=1.20),     # E1 replay row
    pot_doc(D15, "AHX", "horizontal_fade", _et(D15, 17, 30), trigger=6.10, stop=5.80, px=6.00),   # rang AH
)
SHADOWS = (
    shadow_doc(D16, "PMI", "bull_flag", _et(D16, 10, 36), trigger=2.40, stop=2.20, price=2.35),
    shadow_doc(D16, "TGL", "kiss_fly", _et(D16, 10, 46), trigger=5.60, stop=5.30, price=5.50),
    shadow_doc(D16, "HCAI", "intraday_vcp", _et(D16, 11, 6), trigger=3.30, stop=3.10, price=3.25),
)
FLAT = {"NOEN": 5.00, "PMI": 2.10, "TGL": 5.10, "HCAI": 3.00,   # SYNTHETIC flat tapes, under every trigger
        "AHX": 6.00}                                            # = its alert px; read on 10-16 (its same session)


def _real_tape() -> list:
    raw = json.loads(TAPE.read_text(encoding="utf-8"))["bars"]
    return [(datetime.fromisoformat(b["ts_utc"]).replace(tzinfo=UTC), b["open"], b["high"], b["low"], b["close"])
            for b in raw]


def _flat(d, px, start=(4, 0), end=(20, 0)) -> list:
    t, stop = _et(d, *start), _et(d, *end)
    out = []
    while t < stop:
        out.append((t.astimezone(UTC), px, px, px, px))
        t += timedelta(minutes=1)
    return out


def _xlab_15_synthetic() -> list:
    """SYNTHETIC 10-15 XLAB tape (AMENDMENTS9 E1 replay facts): flat 1.20, 15:21 trades 1.23 (fill at the trigger
    1.22), 15:22 high 1.28 = fill + 1R (a WIN on an EQUAL high — the Decimal compare), then flat 1.25."""
    out = []
    for b in _flat(D15, 1.20, end=(16, 0)):
        et = b[0].astimezone(ET)
        if (et.hour, et.minute) == (15, 21):
            b = (b[0], 1.21, 1.23, 1.20, 1.22)
        elif (et.hour, et.minute) == (15, 22):
            b = (b[0], 1.22, 1.28, 1.21, 1.26)
        elif et >= _et(D15, 15, 23):
            b = (b[0], 1.25, 1.25, 1.25, 1.25)
        out.append(b)
    return out


def tape_loader(log=None):
    """load_frames / load_day: (bars, provider_failed) — the real XLAB tape on 10-16, the synthetic ones elsewhere."""
    def load(sym, day):
        if log is not None:
            log.append((sym, day))
        if sym == "XLAB":
            return (_real_tape() if day == D16 else _xlab_15_synthetic() if day == D15 else []), False
        return (_flat(day, FLAT[sym]) if sym in FLAT else []), False
    return load


def ledger_store(*, graded_16=False):
    """The fixture store; the 10-15 ledger docs are the REAL nightly step's output (never typed)."""
    st = fake_store(**{ST.POTENTIALS: FakeColl(list(POTS)), ST.ALERTS: FakeColl(list(SHADOWS))})
    out = LG.grade_step(st, _et(D15, 20, 15, 30), load_day=tape_loader(), split_lookup=lambda *a: False)
    assert out["read_fault"] is False and out["same"] >= 1 and out["written"] >= 1, out
    if graded_16:                                   # tonight's step, run early on purpose: one 10-16 row graded
        st.upsert_ledger(LG.ledger_id("2026-10-16", "XLAB", "horizontal_fade", "potential"),
                         {"date": "2026-10-16", "symbol": "XLAB", "setup": "horizontal_fade", "kind": "potential",
                          "line": "live", "same": {"horizon": "same", "entry": "no_entry", "reason": "no_entry",
                                                   "version": GC.LEDGER_GRADE_VERSION},
                          "version": GC.LEDGER_GRADE_VERSION})
    return st


def no_split(sym, alert_date, today):
    """The fixture's split check: no split in (alert day, today] for any name — the same answer the 10-15 nightly
    step above is given. Injected so the after-close AHX row's default check (fetch_splits_strict) never touches the
    network (refused in the hermetic run → "not read"); the default lookup's own paths are pinned in the ledger's tests."""
    return False


def today_of(st, span=""):
    return LG.today_read(NOW, span=span, store=st, load_frames=tape_loader(), split_lookup=no_split)


def board(st, span="", **kw):
    today = kw.pop("today", "read")
    if today == "read":
        today = today_of(st, span)
    return GT.build(GC.LEDGER_SUB, span=span, now=kw.pop("now", NOW), store=st, today=today, **kw)


@pytest.fixture(scope="module")
def store():
    return ledger_store()


def _rows(tr):
    return {r["id"]: r for d in tr["days"] for r in d["rows"]}


# ── the sub, the chip, the block ─────────────────────────────────────────────────────────────────────────────────
def test_build_serves_the_track_record_block_on_its_own_sub(store):
    out = board(store)
    tr = out["track_record"]
    assert out["sub"] == GC.LEDGER_SUB and out["sub_resolved_from"] == "param"
    assert tr["title"] == W1 and tr["honesty"] == W3 and tr["rule_label"] == "ⓘ how each alert is graded"
    assert tr["rule_text"] == LG.rule_text()
    assert tr["rule_text"].startswith("GG's trade math (your answer, 2026-10-16). Entry = the trigger the alert gave")
    assert f"+{GC.LEDGER_R_MULT:g}R" in tr["rule_text"] and GC.LEDGER_FILL_FROM_ET.strftime("%H:%M") in tr["rule_text"]
    assert out["tiles"] == [] and out["empty_note"] is None and tr["span"] == GC.LEDGER_SPAN_DEFAULT
    assert [h["key"] for h in tr["heads"]] == ["symbol", "setup", "at", "kind", "plan", "same", "next"]
    assert tr["grade_at_et"] == GC.LEDGER_GRADE_AT_ET
    for k in ("scan", "enterable", "pass", "session", "push", "subs"):              # the board around it is intact
        assert k in out, k


def test_the_track_record_chip_is_last_and_counts_todays_graded_rows(store):
    out = board(store)
    chip = out["subs"][-1]
    assert {k: chip[k] for k in ("key", "emoji", "label")} == {"key": "track_record", "emoji": "🏁",
                                                               "label": "Track record"}
    pots = store.potentials(D16)
    assert chip["count"] == LG.count_today(pots, store.ledger_docs([D16])) == 0       # nothing graded tonight yet
    st = ledger_store(graded_16=True)
    assert board(st)["subs"][-1]["count"] == 1 == LG.count_today(st.potentials(D16), st.ledger_docs([D16]))
    for k in (GC.SETUPS[0], "playbook", GC.POTENTIAL_SUB):                            # the chip rides every sub
        assert GT.build(k, now=NOW, store=st)["subs"][-1]["count"] == 1, k


def test_NEGATIVE_a_joined_or_unsent_potential_never_counts_on_the_chip():
    st = fake_store(**{ST.POTENTIALS: FakeColl([POTS[4], POTS[5]])})
    for p in (POTS[4], POTS[5]):
        st.upsert_ledger(LG.ledger_id("2026-10-16", p["symbol"], p["setup"], "potential"),
                         {"date": "2026-10-16", "symbol": p["symbol"], "setup": p["setup"], "kind": "potential",
                          "line": "live", "same": {"horizon": "same", "entry": "no_entry"}})
    assert GT.build(GC.SETUPS[0], now=NOW, store=st)["subs"][-1]["count"] == 0


@pytest.mark.parametrize("span", list(GC.LEDGER_SPANS))
def test_every_span_is_served_as_asked(store, span):
    tr = board(store, span)["track_record"]
    assert tr["span"] == span
    assert [s["key"] for s in tr["spans"]] == list(GC.LEDGER_SPANS)
    assert [s["label"] for s in tr["spans"]] == ["Today", "Yesterday", f"Last {GC.LEDGER_SPAN_SESSIONS} sessions",
                                                 "All"]


@pytest.mark.parametrize("junk", ["", "zzz", "TODAY ", None, 5, ["5d"]])
def test_NEGATIVE_an_unknown_or_junk_span_serves_the_default(store, junk):
    out = GT.build(GC.LEDGER_SUB, span=junk, now=NOW, store=store, today=None)
    assert out["track_record"]["span"] == GC.LEDGER_SPAN_DEFAULT == "5d"


def test_spans_pick_their_days(store):
    days = {k: [d["date"] for d in board(store, k)["track_record"]["days"]] for k in GC.LEDGER_SPANS}
    assert days["today"] == ["2026-10-16"] and days["yesterday"] == ["2026-10-15"]
    assert days["5d"] == ["2026-10-16", "2026-10-15"] and days["all"] == ["2026-10-16", "2026-10-15"]


@pytest.mark.parametrize("sub", [k for k, _e, _l in GC.SUBS if k != GC.LEDGER_SUB])
def test_NEGATIVE_span_on_another_sub_adds_no_track_record_block(store, sub):
    out = GT.build(sub, span="today", now=NOW, store=store, today={"grades": {}})
    assert "track_record" not in out and out["sub"] == sub


def test_NEGATIVE_a_focus_link_never_resolves_to_the_track_record(store):
    out = GT.build("", focus="XLAB", now=NOW, store=store)
    assert out["sub"] != GC.LEDGER_SUB and out["sub"] in GC.SETUPS and "track_record" not in out
    assert out["sub_resolved_from"] == "focus_potential"
    for focus in ("PMI", "NOEN", "ZZZZ", ""):
        assert GT.build("", focus=focus, now=NOW, store=store)["sub"] != GC.LEDGER_SUB, focus


def test_an_explicit_param_any_case_lands_on_the_track_record(store):
    out = GT.build(" Track_Record ", now=NOW, store=store, today=None)
    assert (out["sub"], out["sub_resolved_from"]) == (GC.LEDGER_SUB, "param") and out["track_record"]


# ── what the rows say (the ledger's engine through the tab) ─────────────────────────────────────────────────────
def test_xlab_today_on_the_real_tape_fills_at_0945_and_wins_so_far(store):
    """AMENDMENTS9 E1 replay: both 10-16 XLAB pushes rang pre-market, fill at 09:45 @1.89 (GG's no-trade first 15
    minutes) and reach +1R before any stop — provisional, today not final."""
    tr = board(store, "today")["track_record"]
    rows = _rows(tr)
    for setup in ("horizontal_fade", "intraday_vcp"):
        r = rows[f"2026-10-16|XLAB|{setup}|potential"]
        assert r["line"] == "live" and r["kind_text"] == "🧠 live" and r["rang_text"] == "rang pre"
        assert r["same"]["state"] == "win" and r["same"]["provisional"] is True
        assert r["same"]["text"].startswith("WIN · best +") and r["same"]["text"].endswith(" so far")
        assert "fill 1.89 at 09:45" in r["plan_text"], r["plan_text"]
        assert r["next"]["state"] == "pending" and r["next"]["provisional"] is False
    assert "today not final" in tr["counts_text"]["same"]
    assert tr["today_text"] == "Today · through 11:11 ET · not final"


def test_yesterdays_xlab_is_the_nightly_grade_and_its_next_column_waits(store):
    tr = board(store, "yesterday")["track_record"]
    r = _rows(tr)["2026-10-15|XLAB|intraday_vcp|potential"]
    assert r["same"]["state"] == "win" and r["same"]["provisional"] is False and r["rang_text"] == "rang RTH"
    assert "fill 1.22 at 15:21" in r["plan_text"] and "+1R 1.28" in r["plan_text"]
    assert r["same"]["sub_text"].startswith("+1R at 15:22")
    assert r["next"]["state"] == "pending" and r["next"]["text"] == "after today's close"
    ah = _rows(tr)["2026-10-15|AHX|horizontal_fade|potential"]
    assert ah["rang_text"] == "rang AH" and ah["same"]["state"] == "pending"          # its same session is 10-16
    assert tr["today_text"] is None                                                  # yesterday: no today read


def test_NEGATIVE_the_shadow_line_never_moves_the_live_percentage(store):
    tr = board(store, "today")["track_record"]
    rows = _rows(tr)
    live = [r for r in rows.values() if r["line"] == "live"]
    shadow = [r for r in rows.values() if r["line"] == "shadow"]
    assert {r["symbol"] for r in shadow} == {"PMI", "TGL", "HCAI"} and all(r["kind_text"] == "A+ shadow — never sent"
                                                                           for r in shadow)
    c = tr["counts"]["live"]["same"]
    assert sum(c[k] for k in c if k != "pct") == len(live)
    assert tr["counts"]["shadow"]["same"]["no_entry"] == 3 and tr["shadow_text"].startswith("A+ shadow (never sent")
    assert c["win"] == 2 and c["pct"] == 100 and c["no_plan"] == 1 and c["no_entry"] == 1


def live_entry_doc(d, sym, setup, at, *, trigger, stop, price):
    """A live A+ claim as alerts.py's live branch leaves it (state pushed on the plain `GG:` id, 2026-10-16)."""
    from chart_maps.gajjala import alerts as AL
    return {"_id": AL.claim_key(d, sym, setup), "date": d.isoformat(), "symbol": sym, "setup": setup, "mode": "live",
            "entry_bar_t": at.astimezone(ET).strftime("%Y-%m-%d %H:%M"), "frame": "5m", "trigger": trigger,
            "stop": stop, "risk_pct": round((trigger - stop) / trigger * 100, 2), "price": price, "kind": GC.PUSH_KIND,
            "state": "pushed", "result": {"sent": 1, "failed": 0, "total_targets": 1, "skipped": 0},
            "at": at.astimezone(UTC).isoformat()}


def test_a_live_aplus_entry_row_on_the_tab():
    """DECISIONS10 D3 / AMENDMENTS10 F3 on a COPY of the fixture store (the shared `store` fixture's counts are pinned
    above): one pushed `GG:` claim is a "🎯 A+ entry" row, counted under counts["entry"] and `entries_text`, and the
    🧠 headline counts are byte-for-byte the fixture's (NEGATIVE: the % never moves)."""
    base = board(ledger_store(), "today")["track_record"]
    st = ledger_store()
    doc = live_entry_doc(D16, "PMI", "kiss_fly", _et(D16, 10, 56), trigger=2.40, stop=2.20, price=2.35)
    st.coll(ST.ALERTS).docs[doc["_id"]] = doc
    tr = board(st, "today")["track_record"]
    r = _rows(tr)["2026-10-16|PMI|kiss_fly|aplus"]
    assert (r["line"], r["kind_text"], r["at_text"]) == ("live", "🎯 A+ entry", "10:56 ET")
    assert r["href"] == "/chart-maps?tab=gajjala&sub=kiss_fly&focus=PMI"
    assert r["same"]["state"] == "no_entry"                     # the flat 2.10 tape never trades its 2.40 trigger
    assert tr["counts"]["entry"]["same"]["no_entry"] == 1
    assert tr["counts"]["live"] == base["counts"]["live"] and tr["counts_text"] == base["counts_text"]
    assert tr["entries_text"].startswith("🎯 A+ entries sent (their own line, not pooled with the 🧠 %)")
    assert base["entries_text"] is None                         # NEGATIVE: the fixture has no live entry
    assert tr["shadow_text"] == base["shadow_text"]             # the shadow line is untouched
    shadow = [x for x in _rows(tr).values() if x["line"] == "shadow"]
    assert {x["symbol"] for x in shadow} == {"PMI", "TGL", "HCAI"}   # the PMI bull_flag shadow row stays shadow


def test_NEGATIVE_joined_and_unsent_potentials_are_not_rows(store):
    syms = {r["symbol"] for d in board(store, "all")["track_record"]["days"] for r in d["rows"]}
    assert "JOIN" not in syms and "NOTG" not in syms
    assert {"XLAB", "NPLN", "NOEN", "AHX", "PMI", "TGL", "HCAI"} == syms


def test_no_plan_and_no_entry_rows_are_listed_never_counted(store):
    rows = _rows(board(store, "today")["track_record"])
    np = rows["2026-10-16|NPLN|bull_flag|potential"]
    assert np["same"]["state"] == "no_plan" and np["plan_text"] == "no trigger or stop on the alert"
    ne = rows["2026-10-16|NOEN|kiss_fly|potential"]
    assert ne["same"]["state"] == "no_entry" and ne["same"]["text"] == "no entry yet"


def test_NEGATIVE_without_a_today_read_todays_rows_say_so(store):
    tr = GT.build(GC.LEDGER_SUB, span="today", now=NOW, store=store, today=None)["track_record"]
    assert tr["today_text"] == f"Today · not read on this open — graded tonight {GC.LEDGER_GRADE_AT_ET} ET"
    r = _rows(tr)["2026-10-16|XLAB|horizontal_fade|potential"]
    assert r["same"]["state"] == "pending" and r["same"]["provisional"] is False
    assert "today not final" not in tr["counts_text"]["same"]


def test_NEGATIVE_a_junk_today_value_is_ignored_not_trusted(store):
    for junk in ("x", ["grades"], 3):
        tr = GT.build(GC.LEDGER_SUB, span="today", now=NOW, store=store, today=junk)["track_record"]
        assert tr["today_text"].startswith("Today · not read on this open"), junk


# ── soft: a raising piece never takes the board down ─────────────────────────────────────────────────────────────
def test_NEGATIVE_a_failing_ledger_read_serves_the_fault_note_and_every_other_sub():
    good = ledger_store()
    st = fake_store(**{n: (FakeColl(fail=True) if n == ST.LEDGER else good.coll(n)) for n in ST.ALL})
    out = GT.build(GC.LEDGER_SUB, span="today", now=NOW, store=st, today=None)
    assert out["track_record"] is None and out["empty_note"] == GT.TRACK_RECORD_FAULT
    assert GT.TRACK_RECORD_FAULT == "🏁 The alert record could not be read this time — the next re-read tries again."
    assert out["subs"][-1]["count"] is None                 # the chip's ledger read faulted: unknown, never a 0
    for k, _e, _l in GC.SUBS:
        assert GT.build(k, now=NOW, store=st)["sub"] == k, k


def test_NEGATIVE_a_raising_served_block_or_count_or_import_never_raises(store, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("ledger down")
    monkeypatch.setattr(LG, "served_block", boom)
    out = GT.build(GC.LEDGER_SUB, now=NOW, store=store)
    assert out["track_record"] is None and out["empty_note"] == GT.TRACK_RECORD_FAULT
    monkeypatch.setattr(LG, "count_today", boom)
    assert GT.build(GC.SETUPS[0], now=NOW, store=store)["subs"][-1]["count"] is None
    monkeypatch.setattr(GT, "_ledger", lambda: None)
    out = GT.build(GC.LEDGER_SUB, now=NOW, store=store)
    assert out["track_record"] is None and out["subs"][-1]["count"] is None and out["tiles"] == []


def test_NEGATIVE_a_potentials_read_fault_leaves_the_chip_count_None_never_0(monkeypatch):
    """Critic LOW 2026-10-16: `_ledger_count` reads `st.potentials` itself — a tracker read fault (None) is an
    unknown count, never the 0 that `_safe_list`'s [] would serve; every other sub (and 🏁's own block) still serves."""
    st = ledger_store(graded_16=True)
    assert GT.build(GC.SETUPS[0], now=NOW, store=st)["subs"][-1]["count"] == 1       # control: the read works
    monkeypatch.setattr(st, "potentials", lambda session: None)                    # the store's read-fault answer
    for k, _e, _l in GC.SUBS:
        out = GT.build(k, now=NOW, store=st, today=None)
        assert out["sub"] == k and out["subs"][-1]["key"] == GC.LEDGER_SUB, k
        assert out["subs"][-1]["count"] is None, k
    tr = GT.build(GC.LEDGER_SUB, span="today", now=NOW, store=st, today=None)["track_record"]
    assert tr and tr["days"], "the 🏁 block reads potential_pushes, not the chip's tracker read"


def test_NEGATIVE_a_failing_potentials_collection_leaves_the_chip_None_and_serves_every_sub():
    good = ledger_store(graded_16=True)
    st = fake_store(**{n: (FakeColl(fail=True) if n == ST.POTENTIALS else good.coll(n)) for n in ST.ALL})
    assert st.potentials(D16) is None
    for k, _e, _l in GC.SUBS:
        out = GT.build(k, now=NOW, store=st, today=None)
        assert out["sub"] == k and out["subs"][-1]["count"] is None, k


# ── the route ───────────────────────────────────────────────────────────────────────────────────────────────────
def _route_env(monkeypatch, st):
    from chart_maps import board as board_mod
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)


def _no_network(monkeypatch):
    from chart_maps.gajjala import bars as BARS
    from daytrading import data as dt_data

    def boom(*a, **k):
        raise AssertionError("no bar fetch on this GET")
    monkeypatch.setattr(BARS, "frames_for", boom)
    monkeypatch.setattr(dt_data, "load_intraday", boom)


class Rec:
    def __init__(self, ret=None, exc=None):
        self.calls, self.ret, self.exc = [], ret, exc

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        if self.exc:
            raise self.exc
        return self.ret


def test_route_calls_today_read_once_and_hands_its_dict_to_build(store, monkeypatch):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    today = today_of(store, "today")
    rec = Rec(ret=today)
    monkeypatch.setattr(LG, "today_read", rec)
    seen = []
    real = GT.build
    monkeypatch.setattr(GT, "build", lambda *a, **k: seen.append(k) or real(*a, now=NOW, store=store, **k))
    resp = run_route(API.chart_maps_gajjala(sub="track_record", tf="", focus="", sort="", limit=3, span="today"))
    assert resp.status_code == 200 and len(rec.calls) == 1
    assert rec.calls[0] == ((None,), {"span": "today"})
    assert seen[0]["today"] is today and seen[0]["span"] == "today"
    body = json.loads(resp.body)
    assert body["sub"] == GC.LEDGER_SUB and body["track_record"]["today_text"] == "Today · through 11:11 ET · not final"


def test_route_coerces_the_span_query_object_to_the_default(store, monkeypatch):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    rec = Rec(ret=None)
    monkeypatch.setattr(LG, "today_read", rec)
    resp = run_route(API.chart_maps_gajjala(sub="track_record"))           # every other arg is a Query OBJECT
    body = json.loads(resp.body)
    assert body["track_record"]["span"] == GC.LEDGER_SPAN_DEFAULT and rec.calls == [((None,), {"span": ""})]
    desc = inspect.signature(API.chart_maps_gajjala).parameters["span"].default.description
    assert "today | yesterday | 5d (default) | all" in desc
    sub_desc = inspect.signature(API.chart_maps_gajjala).parameters["sub"].default.description
    assert "| track_record" in sub_desc


@pytest.mark.parametrize("sub", [k for k, _e, _l in GC.SUBS if k != GC.LEDGER_SUB] + ["", "junk"])
def test_NEGATIVE_no_other_sub_ever_calls_the_today_read(store, monkeypatch, sub):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    _no_network(monkeypatch)
    rec = Rec(ret={"grades": {}})
    monkeypatch.setattr(LG, "today_read", rec)
    resp = run_route(API.chart_maps_gajjala(sub=sub, tf="", focus="", sort="", limit=3, span="today"))
    assert resp.status_code == 200 and rec.calls == [], sub
    assert "track_record" not in json.loads(resp.body)


def test_NEGATIVE_span_yesterday_reads_no_bar_at_all(store, monkeypatch):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    _no_network(monkeypatch)
    assert LG.today_read(NOW, span="yesterday", store=store) is None
    resp = run_route(API.chart_maps_gajjala(sub="track_record", tf="", focus="", sort="", limit=3,
                                            span="yesterday"))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["track_record"]["span"] == "yesterday"
    assert body["track_record"]["today_text"] is None


def test_NEGATIVE_a_raising_today_read_still_serves_the_board(store, monkeypatch):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    monkeypatch.setattr(LG, "today_read", Rec(exc=RuntimeError("massive down")))
    resp = run_route(API.chart_maps_gajjala(sub="track_record", tf="", focus="", sort="", limit=3, span="today"))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["track_record"]["today_text"].startswith("Today · not read on this open")


def test_route_scrubs_nan_out_of_the_track_record_block(store, monkeypatch):
    from chart_maps import api as API
    _route_env(monkeypatch, store)
    monkeypatch.setattr(LG, "today_read", Rec(ret=None))
    monkeypatch.setattr(LG, "served_block", lambda *a, **k: {"title": W1, "counts": {"pct": float("nan")},
                                                             "days": [{"rows": [{"fill_px": float("inf")}]}]})
    resp = run_route(API.chart_maps_gajjala(sub="track_record", tf="", focus="", sort="", limit=3, span="today"))
    text = resp.body.decode()
    assert "NaN" not in text and "Infinity" not in text
    body = json.loads(text)
    assert body["track_record"]["counts"]["pct"] is None and body["track_record"]["days"][0]["rows"][0]["fill_px"] is None


# ── NEGATIVES over everything served ─────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_none_nan_forecast_word_sepa_name_or_b_word_in_any_span(store):
    from chart_maps.high_beta_tab import FORBIDDEN_WORDS
    for span in GC.LEDGER_SPANS:
        out = board(store, span)
        blob = json.dumps(out, ensure_ascii=False, allow_nan=False)
        assert not B_WORD.search(blob) and "fake" not in blob.lower(), span
        for s in _walk_strings(out["track_record"]):
            low = s.lower()
            assert s not in ("None", "nan", "NaN", "undefined", "null"), (span, s)
            assert "None" not in s.split() and "NaN" not in s and "undefined" not in low, (span, s)
            assert not any(w in low for w in FORBIDDEN_WORDS), (span, s)
            assert not NAMES.search(s), (span, s)


# ── GOLDEN: the FE fixture IS the served payload ─────────────────────────────────────────────────────────────────
def golden_entry_doc() -> dict:
    """The ONE live A+ entry the 🏁 golden carries (2026-10-16 polish, AMENDMENTS10 F3) — on the golden's OWN fresh store,
    never the shared `store` fixture (its counts are pinned above). XLAB 🌀 on the 🧠 push's own plan (trigger 1.85 /
    stop 1.75): the 09:40 5m bar closed 1.8801 on the REAL 10-16 tape, the A+ rang at 09:45 ET; graded like the shadow
    rows (today_read on the tape — no stored ledger doc): fill 1.85 on 09:46, +1R 1.95 on 09:47 before any stop = WIN."""
    return live_entry_doc(D16, "XLAB", "intraday_vcp", _et(D16, 9, 45), trigger=1.85, stop=1.75, price=1.8801)


def golden_store():
    st = ledger_store()                             # a fresh instance — never the module `store` fixture
    doc = golden_entry_doc()
    st.coll(ST.ALERTS).docs[doc["_id"]] = doc
    return st


def golden_payload() -> str:
    st = golden_store()
    boards = {}
    for span in ("today", "5d", "yesterday"):
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        boards[span] = board(st, span)
    doc = {"_recipe": RECIPE, "boards": boards}
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def test_golden_fixture_is_the_served_payload():
    text = golden_payload()
    if os.environ.get("GG_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), f"missing {GOLDEN.name} — run: {RECIPE}"
    assert GOLDEN.read_text(encoding="utf-8") == text, f"the golden fixture drifted — run: {RECIPE}"
    boards = json.loads(text)["boards"]
    assert set(boards) == {"today", "5d", "yesterday"}
    assert all(b["sub"] == GC.LEDGER_SUB and b["track_record"]["days"] for b in boards.values())
    assert boards["today"]["track_record"]["today_text"] and boards["yesterday"]["track_record"]["today_text"] is None
    for span in ("today", "5d"):                    # the after-close AHX row is read on 10-16's open, never held out
        assert "not read on this open" not in boards[span]["track_record"]["today_text"], span
    # 2026-10-16 polish: the golden's live A+ entry is a real served 🎯 line + row (AMENDMENTS10 F3)
    for span in ("today", "5d"):
        tr = boards[span]["track_record"]
        assert tr["entries_text"].startswith("🎯 A+ entries sent"), span
        assert tr["counts"]["entry"]["same"]["win"] == 1, span
        r = _rows(tr)["2026-10-16|XLAB|intraday_vcp|aplus"]
        assert (r["kind_text"], r["line"], r["same"]["state"]) == ("🎯 A+ entry", "live", "win"), span
    assert boards["yesterday"]["track_record"]["entries_text"] is None          # NEGATIVE: no entry on 10-15


def test_NEGATIVE_the_golden_entry_never_moves_the_headline_counts():
    """F3 NEGATIVE on the golden recipe: with vs without its live A+ entry, the 🧠 headline (counts["live"],
    counts_text) is byte-for-byte the same on every span — the entry rides its own 🎯 line only."""
    with_e, without = golden_store(), ledger_store()
    for span in ("today", "5d", "yesterday"):
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        a = board(with_e, span)["track_record"]
        LG._TODAY_MEMO.clear()
        LG._TODAY_SPLIT.clear()
        b = board(without, span)["track_record"]
        assert a["counts"]["live"] == b["counts"]["live"] and a["counts_text"] == b["counts_text"], span
        assert b["entries_text"] is None, span
