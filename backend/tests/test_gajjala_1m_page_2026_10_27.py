"""🚩 Gajjala's 1-minute page — the served surface + the two kinds (BUILD_SPEC27 §3.7 / §4 WP-C, 2026-10-27).

Ajay 2026-10-27, verbatim: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min
candles please." / "do everything and also add the track record for it from today..".

The fixture day (2026-10-27 — the record's first session, GC.GG1M_RECORD_FROM): a REAL 🚩 5-minute pass
(run.run_pass) lists GGA and GGB on the shared GG5 store; then ONE 1-minute iteration runs the engines run_1m calls, in
its order (§3.6) — the REAL run_1m.run_iteration since 2026-10-27 (critic finding 3): bars.frames_for(variant=GG1) →
detectors.read_all(primary "1m", slow "5m", ctx = GG5's stored ctx, K11 = bars.session_volume) → upsert_read (tile on
bars1 / bars5, ≤ GG1M_TILE_BARS_MAX) → alerts.run_pass → potential.run_pass → the pass doc (GG5's strip / premarket /
postmarket copied, `from_pass`). GGA's Bull Flag is A+ on
the 10:08 1-minute bar (recorded in SHADOW — the senders raise if reached); GGB's is forming (a 🧠 potential, settled
"shadow"). The served boards are tab.build(…, variant=GG1).

GOLDEN: `GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_1m_page_2026_10_27.py -k golden` writes
frontend/src/components/__fixtures__/gajjala_1m_board_2026_10_27.json (the potential / bull_flag / track_record boards,
owner=True) — the FE test renders it through the real GajjalaBoard. Without the env the test proves the file IS the
served payload, byte for byte.

GG5 (today's tab) keeps every byte: its three goldens + tests/test_gajjala_variant_gg5_identity.py run beside this
file; here the NEGATIVES pin that a GG5 payload never carries `variant` and that every 🚩 route calls with no variant.
UNMEASURED — nothing here measures a 1-minute read.
"""
from __future__ import annotations

import copy
import inspect
import json
import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import run_1m as R1
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import variant as V
from tests.fixtures.gajjala import detector_frames as FX
from tests.test_gajjala_run import make_deps, snap_row
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import _walk_strings, run_route

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
D27 = date(2026, 10, 27)                    # a Tuesday — the 1-minute record's first session
D26 = date(2026, 10, 26)
GG1 = V.GG1
GOLDEN = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "__fixtures__" /
          "gajjala_1m_board_2026_10_27.json")
RECIPE = "GG_WRITE_GOLDEN=1 python -m pytest tests/test_gajjala_1m_page_2026_10_27.py -k golden"
SUB_KEYS = tuple(k for k, _e, _l in GC.SUBS)
BANNED = ("5-minute pass", "5-minute bar", "every 5 minutes", "tab=gajjala&")


def at(hh, mm, ss=0, d=D27):
    return datetime(d.year, d.month, d.day, hh, mm, ss, tzinfo=ET)


NOW = at(10, 8, 40)                         # the 10:08 1-minute bar has settled (BAR_SETTLE_SEC)
PREV_ITER = at(10, 7, 40)                   # the iteration before (its potential block: the D9 join rule stays out


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    TP._MEMO.clear()
    R1._PREV_MEMO.clear()
    yield
    LG._TODAY_MEMO.clear()
    LG._TODAY_SPLIT.clear()
    TP._MEMO.clear()
    R1._PREV_MEMO.clear()


# ── the fixture day ──────────────────────────────────────────────────────────────────────────────────────────────
def minutes(bars, day: date, start: str, session: str = "rth") -> pd.DataFrame:
    """Each (o, h, l, c, v) as ONE 1-minute bar (naive-UTC index = the minute START, daytrading.data's shape)."""
    t0 = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), tzinfo=ET)
    idx, rows = [], []
    for k, (o, h, l, c, v) in enumerate(bars):
        idx.append(pd.Timestamp((t0 + timedelta(minutes=k)).astimezone(UTC).replace(tzinfo=None)))
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": v, "session": session})
    return pd.DataFrame(rows, index=pd.DatetimeIndex(idx))


PRIOR = minutes(FX.warm(), D26, "15:30")
RAW = {"GGA": minutes(FX.bf_bars(), D27, "10:00"),                                   # breaks P2 on the 10:07 minute
       "GGB": minutes(FX.bf_bars(pull=[FX.P1, FX.P2, FX.P3], entry=None), D27, "10:00")}   # still forming


def load(sym, day):
    return PRIOR.copy() if day == D26 else RAW[sym].copy()


class Boom:
    """A sender that must never be reached (every 1-minute alert is SHADOW)."""

    def __init__(self):
        self.calls = []

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        raise AssertionError("a 1-minute alert reached a sender")


def gg5_store():
    st = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL})
    deps, _snap, _send, _status = make_deps(rows={"GGA": snap_row(11.2, 8.0, when=at(10, 8)),
                                                  "GGB": snap_row(10.9, 8.0, when=at(10, 8))}, load=load)
    out = RUN.run_pass(NOW, store=st, deps=deps)
    assert out["status"] == "ok" and out["n_listed"] == 2, out
    return st


def gg1_store(shared):
    return ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=GG1, shared=shared)


def gg1_iteration(st, now, *, send=None):
    """ONE REAL 1-minute iteration: run_1m.run_iteration on the GG1 store (2026-10-27, critic finding 3 — the fixture
    is what the loop writes, never a hand-written copy of its pipeline). The fixture loader stands in for Massive; both
    senders raise if reached; the /alerts rows are recorders; the budget clock is frozen (wall_s 0.0)."""
    send = send or Boom()
    send_potential = Boom()
    status, status_potential = [], []

    def load_day(sym, day_, force=False, include_premarket=True, include_afterhours=False):
        return load(sym, day_)

    deps = R1.Deps1m(load_day=load_day, send=send, send_potential=send_potential, owner="owner@example.com",
                     record_status=lambda counts, now_, reason=None: (status.append((counts, reason)), True)[1],
                     record_potential_status=lambda counts, now_, reason=None: (
                         status_potential.append((counts, reason)), True)[1],
                     clock=lambda: 0.0, wall=lambda: now, sleep=lambda _s: None)
    res = R1.run_iteration(now, store=st, deps=deps)
    assert res["ran"] and res["status"] == "ok" and res["errors"] == [], res
    assert len(status) == 1 and len(status_potential) == 1        # the two /alerts rows (a cron iteration)
    send.calls.extend(send_potential.calls)
    return res["alerts"], res["potential"], send


def day():
    """(GG5 store, GG1 store, the iteration's A+ counts, its 🧠 counts, the sender).
    2026-10-29: the fixture day (2026-10-27) WAS a shadow day — GAJJALA_1M_PUSH_MODE read "shadow" until Ajay's
    "Only give me Gajjalas chart notifications from both tabs" — so its iteration runs under "shadow" (restored after);
    the boards are then served with the constant as shipped ("live"): yesterday's shadow rows on today's live page."""
    g5 = gg5_store()
    g1 = gg1_store(g5)
    g1.record_pass(D27, PREV_ITER, {"status": "ok", "potential": {"tracked_today": 0, "joined": 0}},
                   hhmm=PREV_ITER.strftime("%H:%M:%S"))
    old = GC.GAJJALA_1M_PUSH_MODE
    GC.GAJJALA_1M_PUSH_MODE = "shadow"
    try:
        al, pot, send = gg1_iteration(g1, NOW)
    finally:
        GC.GAJJALA_1M_PUSH_MODE = old
    return g5, g1, al, pot, send


@pytest.fixture(scope="module")
def stores():
    return day()


def ledger_tuples(sym, day_):
    return LG.bars_from_frame(load(sym, day_)), False


def no_split(*_a):
    return False


def today_of(st, span="today", now=NOW):
    return LG.today_read(now, span=span, store=st, load_frames=ledger_tuples, split_lookup=no_split)


def board(st, sub, *, variant=GG1, span="", now=NOW, **kw):
    today = today_of(st, span) if sub == GC.LEDGER_SUB else None
    return GT.build(sub, span=span, now=now, store=st, today=today, variant=variant, **kw)


# ── the iteration itself (the fixture is what the page reads) ────────────────────────────────────────────────────
def test_the_iteration_records_in_shadow_and_never_reaches_a_sender(stores):
    _g5, g1, al, pot, send = stores
    assert send.calls == [], "NEGATIVE: a raising sender is never reached"
    assert al["shadow"] == 1 and al["pushed"] == 0, al
    assert pot["shadow"] >= 1 and pot.get("pushed", 0) == 0, pot
    pushed = [d for d in g1.potentials(D27) if isinstance(d.get("push"), dict)]
    assert len(pushed) == pot["shadow"] and {d["push"]["state"] for d in pushed} == {"shadow"}
    ids = [d["_id"] for d in g1.coll(ST.ALERTS).find({})]
    assert ids == ["SHADOW:GG1:2026-10-27|GGA|bull_flag"]
    (doc,) = [d for d in g1.potentials(D27) if d["symbol"] == "GGB" and d["setup"] == "bull_flag"]
    assert doc["push"]["state"] == "shadow" and doc["push"]["result"]["would_push"]["kind"] == GG1.push_kind_potential
    assert doc["url"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGB"


def test_the_fixture_is_the_real_iteration_pass_doc(stores):
    """2026-10-27 (critic finding 3): the GG1 pass doc carries every key run_1m writes — the lease, the slot, the bar
    stats, finished_at — and GG5's latest pass id as `from_pass`. NEGATIVE: the hand-written copy wrote none of
    lease / slot / bars / finished_at; the GG5 store holds no GG1 pass."""
    g5, g1, *_ = stores
    doc = g1.latest_pass()
    assert doc is not None and set(R1.PASS_KEYS) <= set(doc), sorted(doc or {})
    assert doc["lease"]["why"] and doc["slot"]["i"] is None and doc["on_demand"] is False
    assert doc["bars"]["loaded"] == 2 and doc["bars"]["over_budget"] == 0 and doc["wall_s"] == 0.0
    assert doc.get("finished_at") is not None
    assert doc["from_pass"] == (g5.latest_pass() or {}).get("pass_id")
    assert doc["bars_through_et"] == "10:08"
    assert (g5.latest_pass() or {}).get("variant") is None and "slot" not in (g5.latest_pass() or {})


# ── the board ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_gg1_board_identity_tab_tf_and_the_served_variant_block(stores):
    _g5, g1, *_ = stores
    out = board(g1, "bull_flag", owner=True)
    assert out["tab"] == "gajjala_1m" and out["tf"] == "1m" and out["rules_section"] == "gajjala"
    vb = out["variant"]
    assert vb == V.served_block(GG1) and vb["tfs"] == ["1m", "5m"]
    assert vb["title"] == V.word("title", GG1) and vb["honesty"] == V.word("honesty", GG1)
    assert vb["record_from"] == GC.GG1M_RECORD_FROM == D27.isoformat()
    # WIDENED 2026-10-29 — LIVE (Ajay "Only give me Gajjalas chart notifications from both tabs"): the push lines read
    # the shipped mode at call time; the fixture day's rows stay shadow (below)
    assert out["push"] == {"mode": "live", "text": V.word("push", GG1)}
    assert out["push_potential"]["mode"] == "live" and out["push_potential"]["text"] == PT.push_note(D27, GG1)
    assert "rings your phone since 2026-10-29" in out["push"]["text"]
    assert out["broker_flags"] is not None, "the owner's 🚫 strip (ONE list, read through the shared store)"


def test_tiles_are_drawn_on_bars1_capped_and_the_aplus_card_is_gga(stores):
    _g5, g1, *_ = stores
    out = board(g1, "bull_flag")
    by = {t["symbol"]: t for t in out["tiles"]}
    assert by["GGA"]["gajjala"]["state"] == "aplus" and by["GGA"]["gajjala"]["frame"] == "1m"
    stored = g1.get_read(D27, "GGA")["tile"]
    for t in out["tiles"]:
        assert t["tf"] == "1m" and 0 < len(t["bars"]) <= GC.GG1M_TILE_BARS_MAX
    assert by["GGA"]["bars"] == stored["bars1"]
    assert [m["date"] for m in by["GGA"]["markers"]] == ["2026-10-27 10:08"]
    assert out["enterable"]["rows"][0]["symbol"] == "GGA"
    assert out["enterable"]["rows"][0]["href"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGA"


def test_the_fade_sub_defaults_to_the_slow_frame_5m(stores):
    g5, g1, *_ = stores
    assert board(g1, "horizontal_fade")["tf"] == "5m"
    assert board(g1, "horizontal_fade", tf="1m")["tf"] == "1m"
    # NEGATIVE: GG5's Fade still defaults to 15m; a 15m ask on the 1-minute page is not one of its frames
    assert board(g5, "horizontal_fade", variant=None)["tf"] == "15m"
    assert board(g1, "bull_flag", tf="15m")["tf"] == "1m"


def test_NEGATIVE_the_tile_frame_falls_back_to_the_primary_never_15():
    doc = {"tile": {"bars1": [{"t": "a"}], "bars5": [{"t": "b"}], "bars15": [{"t": "c"}]}}
    assert GT._tile_frame(doc, "15m", GG1)["bars"] == [{"t": "a"}]
    assert GT._tile_frame(doc, "5m", GG1)["bars"] == [{"t": "b"}]
    assert GT._tile_frame(doc, "15m")["bars"] == [{"t": "c"}] and GT._tile_frame(doc, "1m")["bars"] == [{"t": "b"}]


def test_cadence_and_stale_words_are_the_1_minute_pass(stores):
    _g5, g1, *_ = stores
    out = board(g1, "bull_flag")
    assert out["session"]["refresh_sec"] == GC.GG1M_CADENCE_SEC
    assert out["pass"]["stale"] is False and out["pass"]["stale_after_sec"] == GC.GG1M_STALE_AFTER_SEC
    assert "the 1-minute pass is current" in out["enterable"]["note"]
    assert out["empty_note"].endswith("the next pass is at most 1 minute away.")
    late = board(g1, "bull_flag", now=NOW + timedelta(seconds=GC.GG1M_STALE_AFTER_SEC + 61))
    assert late["pass"]["stale"] is True and "the pass runs every 1 minute" in late["pass"]["stale_text"]
    assert late["enterable"]["rows"] == [] and "the 1-minute pass has not run since" in late["enterable"]["empty_text"]


def test_hrefs_open_the_1_minute_tab(stores):
    _g5, g1, *_ = stores
    pot = board(g1, GC.POTENTIAL_SUB)
    assert pot["tiles"] and pot["track"]["today"]["rows"]
    hrefs = [r["href"] for r in pot["track"]["today"]["rows"]] + [r["href"] for r in pot["enterable"]["rows"]]
    hrefs += [r["href"] for r in board(g1, "bull_flag")["potential"]["rows"]]
    assert hrefs and all(h.startswith("/chart-maps?tab=gajjala_1m&sub=") for h in hrefs), hrefs


def test_a_focus_link_resolves_off_the_gg1_claim(stores):
    _g5, g1, *_ = stores
    out = board(g1, "", focus="GGA")
    assert (out["sub"], out["sub_resolved_from"]) == ("bull_flag", "focus_alert")


def test_NEGATIVE_served_words_sweep_no_5_minute_word_or_gg5_link_on_any_gg1_sub(stores):
    _g5, g1, *_ = stores
    honesty = V.word("honesty", GG1)
    for sub in SUB_KEYS:
        out = board(g1, sub, owner=True)
        # 📓 the Playbook is GG's own sourced material, served the same on both pages ("his 21-period EMA on 5-minute
        # bars" is a fact about HIS trading) — not a cadence or frame word of this page
        out.pop("playbook", None)
        for s in _walk_strings(out):
            if s == honesty:                      # the ONE allowed "5-minute bars" — GG trades on them
                continue
            for b in BANNED:
                assert b not in s, (sub, b, s)
    # the slow frame's own marker is the only other 5-minute word: " (5-min bar)" on a Fade read on 5m
    assert GT._aplus_text("X", "horizontal_fade", {"frame": "5m"}, None, [], GG1).endswith(" (5-min bar)")
    assert not GT._aplus_text("X", "bull_flag", {"frame": "1m"}, None, [], GG1).endswith("bar)")


def test_NEGATIVE_a_gg5_payload_has_no_variant_key_on_any_sub(stores):
    g5, g1, *_ = stores
    for sub in SUB_KEYS:
        out = board(g5, sub, variant=None)
        assert "variant" not in out and out["tab"] == "gajjala", sub
    assert board(g1, "bull_flag", variant=None)["tab"] == "gajjala_1m", "a GG1 store serves its own variant"
    assert GT.push_block() == GT.push_block(V.GG5) and GT._aplus_text("X", "bull_flag", {"frame": "15m"}, None,
                                                                       []).endswith(" (15-min bar)")


# ── 🏁 Track record ──────────────────────────────────────────────────────────────────────────────────────────────
def _rows(tr):
    return {r["id"]: r for d in tr["days"] for r in d["rows"]}


def test_ledger_rows_are_the_shadow_potential_and_the_shadow_aplus_with_the_1m_words(stores):
    _g5, g1, *_ = stores
    tr = board(g1, GC.LEDGER_SUB, span="today")["track_record"]
    rows = _rows(tr)
    pot = rows[LG.ledger_id("2026-10-27", "GGB", "bull_flag", "potential")]
    ap = rows[LG.ledger_id("2026-10-27", "GGA", "bull_flag", "aplus")]
    # WIDENED 2026-10-29: the 🧠 kind word is read off the row's OWN push state (this fixture day was shadow)
    assert pot["kind_text"] == V.word("ledger_kind_potential_shadow", GG1) == "🧠 shadow — never sent"
    assert pot["line"] == "live"
    assert ap["kind_text"] == "A+ shadow — never sent" and ap["line"] == "shadow"
    assert pot["href"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGB"
    assert ap["href"] == "/chart-maps?tab=gajjala_1m&sub=bull_flag&focus=GGA"
    assert tr["title"] == V.word("ledger_title", GG1) and tr["honesty"] == V.word("ledger_honesty", GG1)
    lead = V.word("ledger_counts_lead_shadow", GG1) + " · "                   # every 🧠 row of the span is shadow
    assert tr["counts_text"]["same"].startswith(lead) and tr["counts_text"]["next"].startswith(lead)
    assert tr["shadow_text"] and tr["aplus"]["total"] == 1 and tr["aplus"]["n_shadow"] == 1
    assert tr["today_text"].startswith("Today · through")
    assert board(g1, "bull_flag")["subs"][-1]["key"] == GC.LEDGER_SUB


def test_the_empty_span_serves_the_1m_empty_word_and_reads_no_session_before_the_record(stores):
    _g5, g1, *_ = stores
    tr = board(g1, GC.LEDGER_SUB, span="yesterday")["track_record"]
    assert tr["days"] == [] and tr["empty_text"] == V.word("ledger_empty", GG1)
    assert "2026-10-27" in tr["empty_text"]


def test_NEGATIVE_gg5_alert_of_drops_a_shadow_potential(stores):
    _g5, g1, *_ = stores
    (doc,) = [d for d in g1.potentials(D27) if d["symbol"] == "GGB" and d["setup"] == "bull_flag"]
    assert LG.alert_of(doc, "potential") is None
    assert LG.alert_of(doc, "potential", variant=GG1)["line"] == "live"
    assert LG.count_today([doc], [{"_id": LG.ledger_id("2026-10-27", "GGB", "bull_flag", "potential"),
                                   "same": {}}]) == 0
    assert LG.count_today([doc], [{"_id": LG.ledger_id("2026-10-27", "GGB", "bull_flag", "potential"),
                                   "same": {}}], variant=GG1) == 1


def test_NEGATIVE_a_2026_10_26_doc_planted_in_the_1m_collections_is_not_a_row():
    g5, g1, *_ = day()
    pot = copy.deepcopy([d for d in g1.potentials(D27) if d["symbol"] == "GGB" and d["setup"] == "bull_flag"][0])
    pot.update({"_id": ST.potential_key(D26, "OLD", "bull_flag"), "date": D26.isoformat(), "symbol": "OLD"})
    g1.coll(ST.POTENTIALS).docs[pot["_id"]] = pot
    a = copy.deepcopy(g1.coll(ST.ALERTS).find({})[0])
    a.update({"_id": "SHADOW:GG1:2026-10-26|OLDA|bull_flag", "date": D26.isoformat(), "symbol": "OLDA"})
    g1.coll(ST.ALERTS).docs[a["_id"]] = a
    for span in ("5d", "10d", "all"):
        tr = board(g1, GC.LEDGER_SUB, span=span)["track_record"]
        syms = {r["symbol"] for r in _rows(tr).values()}
        assert "OLD" not in syms and "OLDA" not in syms and {"GGA", "GGB"} <= syms, (span, syms)
    rows = LG.rows_for([D26, D27], g1)
    assert {r["symbol"] for r in rows} == {"GGA", "GGB"}
    # control: the same 10-26 shadow A+ claim IS a row of a GG5-shaped store (only the 1-minute record starts today)
    g5.coll(ST.ALERTS).docs["SHADOW:GG:2026-10-26|OLDA|bull_flag"] = dict(a, _id="SHADOW:GG:2026-10-26|OLDA|bull_flag")
    assert "OLDA" in {r["symbol"] for r in LG.rows_for([D26], g5)}


def test_NEGATIVE_no_replay_line_on_the_1m_page():
    _g5, g1, *_ = day()
    rid = LG.replay_id("2026-10-27", "RPL", "bull_flag")
    g1.coll(ST.REPLAY).docs[rid] = {"_id": rid, "date": "2026-10-27", "symbol": "RPL", "setup": "bull_flag",
                                    "kind": "aplus", "state": LG.REPLAY_STATE,
                                    "alert": {"at": at(10, 5).astimezone(UTC).isoformat(), "trigger": 2.0,
                                              "stop": 1.9, "price": 1.95}}
    for span in ("today", "all"):
        tr = board(g1, GC.LEDGER_SUB, span=span)["track_record"]
        assert tr["replayed_text"] is None and tr["replayed_note"] is None
        assert "RPL" not in {r["symbol"] for r in _rows(tr).values()}
        assert all(r["line"] != LG.LINES[2] for r in _rows(tr).values())


# ── 🕰️ the entry tape ────────────────────────────────────────────────────────────────────────────────────────────
APLUS_ID = LG.ledger_id("2026-10-27", "GGA", "bull_flag", "aplus")


def _today_bars(sym, day_, **_k):
    return LG.bars_from_frame(load(sym, day_)), NOW.astimezone(UTC)


def test_the_gg1_tape_draws_1_minute_bars_with_its_own_words(stores):
    _g5, g1, *_ = stores
    p = TP.entry_tape(APLUS_ID, now=NOW, store=g1, today_bars=_today_bars, load_day=lambda s, d: None)
    assert p["tf"] == TP.ENTRY_TAPE_WORDS["tf"].format(n=GC.GG1M_TAPE_TF_MIN)
    assert "1-minute closes" in p["legend"] and "1-minute tape" in p["aria"]
    ts = [b["t"] for b in p["bars"]]
    assert len(ts) >= 2 and {b - a for a, b in zip(ts, ts[1:])} == {60_000}
    assert p["n_bars"] == len(RAW["GGA"]) <= GC.GG1M_TAPE_BARS_MAX == 2880


def test_the_gg1_tape_cap_is_its_constant(stores, monkeypatch):
    _g5, g1, *_ = stores
    monkeypatch.setattr(GC, "GG1M_TAPE_BARS_MAX", 3)
    p = TP.entry_tape(APLUS_ID, now=NOW, store=g1, today_bars=_today_bars, load_day=lambda s, d: None)
    assert p["n_bars"] == 3


def test_NEGATIVE_a_gg5_memo_entry_for_the_same_id_never_answers_gg1(stores):
    g5, g1, *_ = stores
    sentinel = {"id": APLUS_ID, "note": "a GG5 tape"}
    TP._MEMO[(APLUS_ID, "full")] = (0.0, sentinel)
    clock = lambda: 1.0                                                       # noqa: E731 — inside the memo window
    assert TP.entry_tape(APLUS_ID, now=NOW, store=g5, clock=clock) is sentinel   # control: GG5's key answers GG5
    p = TP.entry_tape(APLUS_ID, now=NOW, store=g1, clock=clock, today_bars=_today_bars, load_day=lambda s, d: None)
    assert p is not sentinel and p["bars"] and p["tf"].startswith("1min")
    assert (GG1.key, APLUS_ID, "full") in TP._MEMO and (GG1.key, APLUS_ID, "lite") in TP._MEMO
    assert TP.tape_bars(None, 1) == [] and TP.bars5(None) == []


# ── the routes ───────────────────────────────────────────────────────────────────────────────────────────────────
class Rec:
    def __init__(self, ret=None):
        self.calls, self.ret = [], ret

    def __call__(self, *a, **k):
        self.calls.append((a, k))
        return self.ret(*a, **k) if callable(self.ret) else self.ret


def _route_env(monkeypatch, g5, g1):
    from chart_maps import board as board_mod
    monkeypatch.setattr(ST, "default", lambda: g5)
    monkeypatch.setattr(ST, "for_variant", lambda v=None: g5 if V.is_gg5(v) else g1)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", lambda tiles: {})
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)


def test_the_three_1m_routes_resolve_gg1(stores, monkeypatch):
    from chart_maps import api as API
    from chart_maps.gajjala import on_demand as OD
    import auth
    g5, g1, *_ = stores
    _route_env(monkeypatch, g5, g1)
    tr = Rec(ret=None)
    monkeypatch.setattr(LG, "today_read", tr)
    real = GT.build
    seen = []
    monkeypatch.setattr(GT, "build", lambda *a, **k: seen.append(k) or real(*a, now=NOW, **k))
    body = json.loads(run_route(API.chart_maps_gajjala_1m(sub="track_record", tf="", focus="", sort="", limit=3,
                                                          span="today")).body)
    assert seen[-1]["variant"] is GG1 and body["tab"] == "gajjala_1m" and body["variant"]["tfs"] == ["1m", "5m"]
    assert tr.calls == [((None,), {"span": "today", "store": g1})]
    run_route(API.chart_maps_gajjala_1m(sub="bull_flag", tf="", focus="", sort="", limit=3, span=""))
    assert len(tr.calls) == 1, "NEGATIVE: no other sub reads today's bars"
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == "owner@example.com")
    od = Rec(ret={"state": "started", "eta_sec": float("nan")})
    monkeypatch.setattr(OD, "request", od)
    ans = json.loads(run_route(API.chart_maps_gajjala_1m_scan(email="owner@example.com")).body)
    assert od.calls == [((), {"variant": GG1})] and ans == {"state": "started", "eta_sec": None}
    tp = Rec(ret={"id": "x", "bars": []})
    monkeypatch.setattr(TP, "entry_tape", tp)
    resp = run_route(API.chart_maps_gajjala_1m_entry_tape(id=APLUS_ID, lite=1))
    assert resp.status_code == 200 and tp.calls == [((APLUS_ID,), {"lite": True, "store": g1})]
    paths = {getattr(r, "path", ""): r.methods for r in API.router.routes}
    assert paths[GG1.api_base] == {"GET"} and paths[GG1.api_base + "/scan"] == {"POST"}
    assert paths[GG1.api_base + "/entry-tape"] == {"GET"}
    assert V.for_api_base(GG1.api_base + "/scan") is GG1


def test_NEGATIVE_the_5m_routes_call_with_no_variant_and_answer_as_before(stores, monkeypatch):
    from chart_maps import api as API
    from chart_maps.gajjala import on_demand as OD
    import auth
    g5, g1, *_ = stores
    _route_env(monkeypatch, g5, g1)
    tr = Rec(ret=None)
    monkeypatch.setattr(LG, "today_read", tr)
    real = GT.build
    seen = []
    monkeypatch.setattr(GT, "build", lambda *a, **k: seen.append(k) or real(*a, now=NOW, **k))
    body = json.loads(run_route(API.chart_maps_gajjala(sub="track_record", tf="", focus="", sort="", limit=3,
                                                       span="today")).body)
    assert "variant" not in seen[-1] and body["tab"] == "gajjala" and "variant" not in body
    assert tr.calls == [((None,), {"span": "today"})]
    monkeypatch.setattr(auth, "is_admin_email", lambda e: e == "owner@example.com")
    od = Rec(ret={"state": "started"})
    monkeypatch.setattr(OD, "request", od)
    run_route(API.chart_maps_gajjala_scan(email="owner@example.com"))
    assert od.calls == [((), {})]
    tp = Rec(ret={"id": "x"})
    monkeypatch.setattr(TP, "entry_tape", tp)
    run_route(API.chart_maps_gajjala_entry_tape(id=APLUS_ID, lite=0))
    assert tp.calls == [((APLUS_ID,), {"lite": False})]
    for fn in (API.chart_maps_gajjala, API.chart_maps_gajjala_scan, API.chart_maps_gajjala_entry_tape):
        assert "GG1" not in inspect.getsource(fn) and "variant" not in inspect.getsource(fn), fn.__name__


def test_NEGATIVE_the_1m_post_stealth_404s_a_non_owner(monkeypatch):
    import auth
    from fastapi import HTTPException
    from chart_maps import api as API
    from chart_maps.gajjala import on_demand as OD
    monkeypatch.setattr(auth, "is_admin_email", lambda e: False)
    calls = []
    monkeypatch.setattr(OD, "request", lambda *a, **k: calls.append(1) or {})
    for email in ("someone@example.com", None):
        with pytest.raises(HTTPException) as e:
            run_route(API.chart_maps_gajjala_1m_scan(email=email) if email else API.chart_maps_gajjala_1m_scan())
        assert e.value.status_code == 404
    assert calls == []


def test_NEGATIVE_an_unknown_1m_tape_id_404s_and_a_raising_build_serves_the_fault(stores, monkeypatch):
    from chart_maps import api as API
    g5, g1, *_ = stores
    _route_env(monkeypatch, g5, g1)
    assert run_route(API.chart_maps_gajjala_1m_entry_tape(id="junk", lite=0)).status_code == 404

    def boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(TP, "entry_tape", boom)
    resp = run_route(API.chart_maps_gajjala_1m_entry_tape(id=APLUS_ID, lite=0))
    body = json.loads(resp.body)
    assert resp.status_code == 200 and body["note"] == TP.ENTRY_TAPE_WORDS["fault"]
    assert body["tf"] == TP.ENTRY_TAPE_WORDS["tf"].format(n=GC.GG1M_TAPE_TF_MIN)


# ── 🔴 live card ─────────────────────────────────────────────────────────────────────────────────────────────────
def test_live_card_1m_reads_the_next_1_minute_close():
    from chart_maps import live_card as LC
    now = datetime(2026, 10, 27, 14, 0, 30, tzinfo=ET)
    for tf in ("1m", 1, "1"):
        assert "the 1-minute bar closes (14:01 ET)" in LC.live_vs(9.12, {"trigger": 9.0, "tf": tf}, now)["text"], tf
    assert "the 5-minute bar closes (14:05 ET)" in LC.live_vs(9.12, {"trigger": 9.0, "tf": "5m"}, now)["text"]
    # NEGATIVE: junk still reads as GG5's default; vs_tf_minutes() is GG5's TFS, unchanged
    for tf in ("abc", 7, None, "2m"):
        assert "the 5-minute bar closes (14:05 ET)" in LC.live_vs(9.12, {"trigger": 9.0, "tf": tf}, now)["text"], tf
    assert LC.vs_tf_minutes() == (5, 15) and LC._vs_sizes() == (5, 15, 1)


# ── the two kinds ────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_two_kinds_are_the_variant_strings_and_registered_everywhere():
    from market_hours import gate
    from push import hooks, recent as R, subs
    from supply_demand import alert_status as AS
    assert (AS.GAJJALA_1M_KIND, AS.GAJJALA_1M_POTENTIAL_KIND) == (GG1.push_kind_setup, GG1.push_kind_potential)
    i = AS.PASS_KINDS.index(AS.GAJJALA_POTENTIAL_KIND)
    assert AS.PASS_KINDS[i + 1:i + 3] == (AS.GAJJALA_1M_KIND, AS.GAJJALA_1M_POTENTIAL_KIND)
    for k in (AS.GAJJALA_1M_KIND, AS.GAJJALA_1M_POTENTIAL_KIND):
        assert AS.CADENCE_SEC[k] == GC.GG1M_CADENCE_SEC and k not in AS.DAILY_PASS_KINDS
        assert k in gate.MARKET_ALERT_KINDS and k not in gate.PERSONAL_KINDS
        assert R.item_url(k, "GGB") == "/chart-maps?tab=gajjala_1m&focus=GGB"
        assert R.ITEM_URL_BY_KIND[k].startswith(f"/chart-maps?tab={GG1.tab}&")
        assert subs.default_prefs()[k] is False
    for fn, kind in ((GG1.send_setup, GG1.push_kind_setup), (GG1.send_potential, GG1.push_kind_potential)):
        seen = []
        orig = hooks.sender.send_to_user
        hooks.sender.send_to_user = lambda owner, payload, kind=None: seen.append((owner, kind)) or {"sent": 0}
        try:
            getattr(hooks, fn)(owner="o@x", payload={"title": "t"})
        finally:
            hooks.sender.send_to_user = orig
        assert seen == [("o@x", kind)], fn


def test_the_1m_kinds_reach_the_owner_only_and_are_not_retired():
    """WIDENED 2026-10-29 — Ajay: "Only give me Gajjalas chart notifications from both tabs": both kinds joined the
    owner keep-set (was: NOT in it, shadow). NEGATIVE: still False for everyone else, never retired."""
    from push import subs
    for k in (GG1.push_kind_setup, GG1.push_kind_potential):
        assert k in subs.OWNER_KEEP_SET and subs.owner_prefs()[k] is True
        assert subs.default_prefs()[k] is False
        assert k not in subs.DISABLED_ALERT_KINDS


def test_the_alerts_status_page_carries_both_1m_passes_with_a_60s_cadence():
    from supply_demand import alert_status as AS
    from tests.test_alert_status import FakeColl as AFake
    p = AS.status_payload(pass_coll=AFake(), latest_coll=AFake(), now=NOW)
    for k in (AS.GAJJALA_1M_KIND, AS.GAJJALA_1M_POTENTIAL_KIND):
        assert p["passes"][k] == {"as_of": None, "date": None, "counts": {}, "cadence_sec": 60}
    assert set(p["passes"]) == set(AS.PASS_KINDS)


# ── ℹ️ Rules panel ───────────────────────────────────────────────────────────────────────────────────────────────
def test_the_rules_clause_rides_the_section_note_built_from_the_variant(monkeypatch):
    from supply_demand import rules_info as RI
    # UPDATED 2026-10-29 (BUILD_SPEC29 critic F2 — Ajay "Only give me Gajjalas chart notifications from both tabs,"):
    # GAJJALA_1M_PUSH_MODE is "live", so the push half says the alerts ring his phone since V.LIVE_SINCE_1M and names
    # the shadow days before it. The shadow sentence is pinned by the NEGATIVE below.
    assert V.push_mode(GG1) == "live"
    want = (f"🚩 {V.frame_minutes(GG1.primary, GG1)}-minute page: the same rules on CLOSED "
            f"{V.frame_minutes(GG1.primary, GG1)}-minute bars (the Fade on {V.frame_minutes(GG1.slow, GG1)}-minute "
            f"first), about once a minute over the same list — a Cheetah variant by your call "
            f"({GC.GG1M_RECORD_FROM}); its alerts ring your phone since {V.LIVE_SINCE_1M} by your call; from "
            f"{GC.GG1M_RECORD_FROM} until then they were recorded in shadow, never sent.")
    sec = RI._gajjala_section()
    assert (" " + want + " UNMEASURED — no study here says these setups win. Not advice.") in sec["note"]
    assert sec["note"].endswith("Not advice.")
    # NEGATIVE: picks stay 8, the stops and the alerts unchanged in number; the clause is said once
    assert len(sec["picks"]) == 8 and len(sec["stops"]) <= 6
    text = " ".join(sec["picks"] + sec["stops"] + sec["alerts"] + [sec["note"]])
    assert text.count("-minute page") == 1 and not re.search("b" + "ounc", text, re.I)
    monkeypatch.setattr(GC, "GG1M_RECORD_FROM", "2026-11-02")
    assert "by your call (2026-11-02)" in RI._gajjala_section()["note"]


def test_NEGATIVE_the_rules_clause_never_says_never_sent_while_live_nor_rings_while_shadow(monkeypatch):
    """2026-10-29 (critic F2): the clause follows the mode at call time — live never reads "are recorded in shadow,
    never sent."; a mutated copy in shadow never reads "ring your phone"; junk in the constant reads shadow."""
    from supply_demand import rules_info as RI
    live = RI._gg_one_minute_clause()
    assert "ring your phone since " + V.LIVE_SINCE_1M in live
    assert "its alerts are recorded in shadow, never sent." not in live
    for mode in ("shadow", "LIVE", None):
        monkeypatch.setattr(GC, GG1.push_mode_const, mode)
        sh = RI._gg_one_minute_clause()
        assert sh.endswith("its alerts are recorded in shadow, never sent."), mode
        assert "ring your phone" not in sh and V.LIVE_SINCE_1M not in sh, mode


def test_NEGATIVE_a_broken_variant_module_drops_only_the_clause(monkeypatch):
    from supply_demand import rules_info as RI
    import builtins
    real = builtins.__import__

    def fake(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "chart_maps.gajjala" and fromlist and "variant" in fromlist:
            raise ImportError("no variant module")
        return real(name, globals, locals, fromlist, level)
    monkeypatch.setattr(builtins, "__import__", fake)
    assert RI._gg_one_minute_clause() == ""
    assert "-minute page" not in RI._gajjala_section()["note"]


def test_NEGATIVE_no_typed_1_minute_digit_in_the_gajjala_rules_source():
    """The clause's digits come from the variant's frames (the format), never typed: no "1-minute" / "5-minute" in
    the 🚩 section's source (its functions: _gajjala* / _gg_*)."""
    from supply_demand import rules_info as RI
    fns = [fn for name, fn in vars(RI).items() if name.startswith(("_gajjala", "_gg_")) and callable(fn)]
    assert RI._gg_one_minute_clause in fns
    for fn in fns:
        src = inspect.getsource(fn)
        assert not re.search(r"\b1-min", src), fn.__name__
    assert not re.search(r"\b\d+-minute", inspect.getsource(RI._gg_one_minute_clause))


# ── GOLDEN: the FE fixture IS the served payload ─────────────────────────────────────────────────────────────────
def golden_payload() -> str:
    _g5, g1, *_ = day()
    doc = {"_recipe": RECIPE,
           "boards": {"potential": board(g1, GC.POTENTIAL_SUB, owner=True),
                      "bull_flag": board(g1, "bull_flag", owner=True),
                      "track_record": board(g1, GC.LEDGER_SUB, span="today", owner=True)}}
    return json.dumps(doc, indent=1, ensure_ascii=False, sort_keys=True, allow_nan=False) + "\n"


def test_golden_fixture_is_the_served_payload():
    text = golden_payload()
    if os.environ.get("GG_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), f"missing {GOLDEN.name} — run: {RECIPE}"
    assert GOLDEN.read_text(encoding="utf-8") == text, f"the golden fixture drifted — run: {RECIPE}"
    boards = json.loads(text)["boards"]
    for k, b in boards.items():
        assert b["tab"] == "gajjala_1m" and b["variant"]["tfs"] == ["1m", "5m"], k
    assert boards["bull_flag"]["tiles"] and boards["potential"]["track"]["today"]["rows"]
    assert boards["track_record"]["track_record"]["days"]
