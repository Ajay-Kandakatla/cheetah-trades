"""🧪 Gajjala · Audited — the served blocks (2026-11-01, BUILD_SPEC gg-audited §3.6 / WP-C).

Ajay 2026-11-01: "I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..
Gajjals-Audited. So we can keep track of improvements on this tab".

Covers audited_tab.py (overlay_reads · held_block · audited_block · compare_block) and the seven guarded tab.py edits:
the overlay attaches only on the three conditions (C2), shallow and never mutating (C8); a held A+ is a card, a count,
a legend row and a held row — never hidden, never on the 🎯 banner; GG5 / GG1 serve every byte as before (the GG5 board
golden); the 🏁 compare's arithmetic, recon (C5), the floor as a COUNT (no `measured` key, the UNMEASURED words always
served); JSON-native payload (C13); no "edge" word, no b-word.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest

from catalysts.medical.alerts import SHADOW_CLAIM_PREFIX
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import audited_pass as AP
from chart_maps.gajjala import audited_rules as AUD
from chart_maps.gajjala import audited_tab as AT
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests.test_gajjala_run import S, at
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_variant_gg5_identity import BOARD, board_text, scenario, writes_text

ET = ZoneInfo("America/New_York")
NOW_B = at(10, 42)                                     # the identity board's clock (the 10:41 pass is current)
GGA_OWN = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY)
B_WORD = re.compile("b" + "ounc", re.I)
EDGE = re.compile(r"\bedge\b", re.I)
NEW_KEYS = ("audited", "held", "audited_compare")


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── helpers ───────────────────────────────────────────────────────────────────────────────────────────────────────
def gga_store(shared, docs=None):
    docs = docs or {}
    return ST.GajjalaStore(colls={n: FakeColl(docs.get(n)) for n in GGA_OWN}, variant=V.GGA, shared=shared)


def aplus_of(doc):
    return next(s for s, r in doc["setups"].items() if isinstance(r, dict) and r.get("state") == "aplus")


def entry(read, failed=(), frame="5m"):
    """An overlay entry shaped as audited_pass.run_step writes it (judge's block + the read's own keys)."""
    ids = [r.id for r in AUD.on_rules()]
    fails = [{"id": i, "why": f"why {i}"} for i in failed]
    ok = not fails
    text = (f"audited A+ — {' · '.join(ids)} pass · UNMEASURED" if ok else
            "🚩 A+ on the original, held here by: " + "; ".join(f"{f['id']} — {f['why']}" for f in fails)
            + " · UNMEASURED")
    return {"aplus": ok, "original_aplus": True, "rules": ids, "passed": [i for i in ids if i not in failed],
            "failed": fails, "frame": frame,
            "values": {"G1": {"close": "11.2", "trigger": "11.0", "vol": 1.0, "base_mean_vol": 1.0, "k": 2.0,
                              "base_n": 3, "frame": frame},
                       "G2": {"run": 1, "longest": 1, "max": 3, "mode": "last", "frame": frame},
                       "G4": {"risk_pct": 4.5, "stop_used": "10.5", "frozen": False,
                              "frozen_reason": AUD.FROZEN_REASONS["not_squeeze"], "cap_pct": 10.0}},
            "text": text, "version": AUD.AUDIT_VERSION,
            "entry_bar_t": read.get("entry_bar_t"), "trigger": read.get("trigger"), "stop": read.get("stop"),
            "risk_pct": read.get("risk_pct")}


def plant(gga, doc, setup, ent, *, pass_at=None):
    gga.upsert_overlay(S, doc["symbol"], {"date": S.isoformat(), "symbol": doc["symbol"], "setups": {setup: ent},
                                          "frozen": {}, "pass_at": pass_at or doc["updated_at"], "version": 1},
                       now=pass_at or doc["updated_at"])


def state_ok(gga, st, *, at_=None, ok=True):
    lat = st.latest_pass()
    gga.set_state(AP.LATEST_ID, {"at": at_ or lat["at"], "ok": ok, "n_read": 3, "n_aplus_original": 1,
                                 "n_aplus_audited": 0, "n_held": 1})


@pytest.fixture
def world(monkeypatch):
    st, _out = scenario("shadow", monkeypatch)
    doc = st.get_read(S, "GGA")
    return st, doc, aplus_of(doc)


def tile_of(board, sym):
    return next(t for t in board["tiles"] if t["symbol"] == sym)


def walk(o, path=()):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + (k,), k, v
            yield from walk(v, path + (k,))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, path + (i,))


def strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from strings(v)
    elif isinstance(o, list):
        for v in o:
            yield from strings(v)


# ── the board: a held A+ ──────────────────────────────────────────────────────────────────────────────────────────
def test_a_g1_held_aplus_is_a_card_a_count_a_legend_row_and_a_held_row_never_on_the_banner(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)))
    state_ok(gga, st)
    b = GT.build(setup, now=NOW_B, store=gga, owner=True)
    assert b["tab"] == "gajjala_audited"
    assert b["variant"]["title"] == V.WORDS_GGA["title"]
    assert [r["id"] for r in b["audited"]["registry"]] == ["G1", "G2", "G3", "G4"]
    assert b["audited"]["on_ids"] == ["G1", "G2", "G4"]
    assert b["audited"]["lane_only_text"] and "G3" in b["audited"]["lane_only_text"]
    assert b["audited"]["unmeasured_text"] == V.word("unmeasured", V.GGA, floor=AUD.MEASURE_FLOOR_WEEKS)
    assert b["audited"]["pass"]["text"].startswith("🧪 audit overlay ran on the 10:41 ET pass")
    t = tile_of(b, "GGA")
    g = t["gajjala"]
    assert g["state"] == AUD.HELD_STATE
    assert g["state_label"].startswith("🚩 A+ on the original, held here by: G1")
    assert g["audit"]["failed"][0]["id"] == "G1"
    assert [m["label"] for m in t["markers"]] == [GT.HELD_MARKER_LABEL]
    assert all(not ln["label"].startswith("BUY") for ln in t["lines"])            # a held read is a TRIGGER, never BUY
    assert [r for r in b["enterable"]["rows"] if r["symbol"] == "GGA"] == []       # NEGATIVE: never on the 🎯 banner
    held = b["held"]["rows"]
    assert [(r["symbol"], r["setup"]) for r in held] == [("GGA", setup)]
    assert held[0]["held_by"] == [{"id": "G1", "why": "why G1"}]
    assert held[0]["audit_text"] == g["audit"]["text"]
    assert b["held"]["title"] == V.word("held_title", V.GGA, n=1) and b["held"]["empty_text"] is None
    assert b["counts"][AUD.HELD_STATE] == 1 and b["counts"]["aplus"] == 0
    keys = [r["key"] for r in b["counts_legend"]]
    assert keys[:2] == ["aplus", AUD.HELD_STATE]
    sub = next(s for s in b["subs"] if s["key"] == setup)
    assert sub["count"] >= 1                                                      # counted on the sub chip too


def test_a_passing_audit_keeps_the_aplus_card_and_the_banner_row(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup]))
    state_ok(gga, st)
    b = GT.build(setup, now=NOW_B, store=gga)
    g = tile_of(b, "GGA")["gajjala"]
    assert g["state"] == "aplus" and g["audit"]["text"].startswith("audited A+ — ")
    assert g["state_label"] == GT.state_label({"state": "aplus"})
    assert [r["symbol"] for r in b["enterable"]["rows"]] == ["GGA"]
    assert b["held"]["rows"] == [] and b["held"]["empty_text"] == V.word("held_empty", V.GGA)
    assert b["counts"][AUD.HELD_STATE] == 0 and b["counts"]["aplus"] == 1
    assert b["audited"]["unaudited"] == {"n": 0, "text": None}


def test_the_recap_lists_a_held_aplus_with_the_held_word(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G4",)))
    b = GT.build("postmarket", now=NOW_B, store=gga)
    rows = b["postmarket"]["recap"]["rows"]
    assert any(r["symbol"] == "GGA" and GT.HELD_RECAP_WORD in r["text"] for r in rows)
    assert b["counts"][AUD.HELD_STATE] == 1                                       # the all-setups counts carry it too
    # NEGATIVE: the recap of a non-audited variant never reads the held state
    assert GT.recap([dict(doc, setups={setup: dict(doc["setups"][setup], state=AUD.HELD_STATE)})])["rows"] == []


def test_order_key_puts_a_held_aplus_right_after_the_aplus_and_before_triggered():
    def tile(sym, state, bar, audit=True):
        g = {"state": state, "entry_bar_t": bar}
        if audit:
            g["audit"] = {"aplus": False}
        return {"symbol": sym, "gajjala": g}
    tiles = [tile("TRG", "triggered", "2026-10-13 10:40"), tile("HLD", AUD.HELD_STATE, "2026-10-13 10:40"),
             tile("APL", "aplus", "2026-10-13 10:30", audit=False), tile("HLD2", AUD.HELD_STATE, "2026-10-13 10:45")]
    assert [t["symbol"] for t in sorted(tiles, key=GT.order_key)] == ["APL", "HLD2", "HLD", "TRG"]
    # NEGATIVE: the held word without an audit block (never on a GG5 read) ranks as unknown
    assert GT.order_key(tile("X", AUD.HELD_STATE, "2026-10-13 10:40", audit=False))[0] == 9


def test_the_legend_gains_the_held_row_only_when_audited():
    assert GT.count_legend() == GT.count_legend(audited=False)
    plain = [r["key"] for r in GT.count_legend()]
    aud = GT.count_legend(audited=True)
    assert [r["key"] for r in aud] == plain[:1] + [AUD.HELD_STATE] + plain[1:]
    row = aud[1]
    assert row["text"] == GT.HELD_LEGEND_TEXT and AUD.HELD_STATE not in plain


# ── C2 the three attach conditions ────────────────────────────────────────────────────────────────────────────────
def test_c2a_an_overlay_on_an_older_entry_bar_never_paints_a_fresh_aplus(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, dict(entry(doc["setups"][setup], failed=("G1",)), entry_bar_t="2026-10-13 09:55"))
    state_ok(gga, st)
    b = GT.build(setup, now=NOW_B, store=gga)
    g = tile_of(b, "GGA")["gajjala"]
    assert g["state"] == "aplus" and "audit" not in g
    assert b["audited"]["unaudited"]["n"] == 1
    assert b["audited"]["unaudited"]["text"] == V.word("unaudited_line", V.GGA, n=1)


def test_c2b_an_overlay_one_pass_older_than_the_read_is_not_attached(world):
    st, doc, setup = world
    gga = gga_store(st)
    old = GT._stamp_utc(doc["updated_at"]) - timedelta(seconds=GC.PASS_CADENCE_SEC)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)), pass_at=old)
    b = GT.build(setup, now=NOW_B, store=gga)
    g = tile_of(b, "GGA")["gajjala"]
    assert g["state"] == "aplus" and "audit" not in g
    assert b["audited"]["unaudited"]["n"] == 1


class _Ov:
    def __init__(self, docs):
        self.docs = docs

    def overlays(self, session):
        return self.docs


def _doc(state, bar="2026-10-13 10:40", upd=None):
    upd = upd or datetime(2026, 10, 13, 14, 41, tzinfo=timezone.utc)
    return {"symbol": "ZZZ", "updated_at": upd, "tile": {"bars5": [{"t": bar}]},
            "setups": {"bull_flag": {"state": state, "entry_bar_t": bar, "trigger": 1.0, "stop": 0.9},
                       "kiss_fly": {"state": "forming"}}}


def _ov(bar="2026-10-13 10:40", pass_at=None, failed=("G2",)):
    pass_at = pass_at or datetime(2026, 10, 13, 14, 41, tzinfo=timezone.utc)
    return {"symbol": "ZZZ", "pass_at": pass_at,
            "setups": {"bull_flag": entry({"entry_bar_t": bar, "trigger": 1.0, "stop": 0.9}, failed=failed)}}


def test_c2c_a_triggered_read_with_a_matching_entry_is_never_painted():
    d = _doc("triggered")
    out, stats = AT.overlay_reads({"ZZZ": d}, _Ov([_ov()]), S)
    assert out["ZZZ"] is d and "audit" not in out["ZZZ"]["setups"]["bull_flag"]
    assert stats["n_aplus_original"] == 0 and stats["n_unaudited"] == 0


def test_c2d_all_three_hold_attaches_and_only_the_served_keys_ride():
    d = _doc("aplus")
    out, stats = AT.overlay_reads({"ZZZ": d}, _Ov([_ov()]), S)
    r = out["ZZZ"]["setups"]["bull_flag"]
    assert r["state"] == AUD.HELD_STATE and set(r["audit"]) == set(AUD.AUDIT_SERVED_KEYS)
    assert "entry_bar_t" not in r["audit"] and "trigger" not in r["audit"]
    assert stats == {"n_aplus_original": 1, "n_aplus_audited": 0, "n_held": 1, "n_unaudited": 0,
                     "overlay_at": datetime(2026, 10, 13, 14, 41, tzinfo=timezone.utc)}
    ok, s2 = AT.overlay_reads({"ZZZ": _doc("aplus")}, _Ov([_ov(failed=())]), S)
    assert ok["ZZZ"]["setups"]["bull_flag"]["state"] == "aplus" and s2["n_aplus_audited"] == 1
    # NEGATIVE: an entry with no `aplus` key fails closed (held, never a pass)
    junk = _ov()
    junk["setups"]["bull_flag"].pop("aplus")
    jo, _s = AT.overlay_reads({"ZZZ": _doc("aplus")}, _Ov([junk]), S)
    assert jo["ZZZ"]["setups"]["bull_flag"]["state"] == AUD.HELD_STATE
    # NEGATIVE: no pass_at / no updated_at → never attached
    nop = _ov()
    nop.pop("pass_at")
    no, s3 = AT.overlay_reads({"ZZZ": _doc("aplus")}, _Ov([nop]), S)
    assert "audit" not in no["ZZZ"]["setups"]["bull_flag"] and s3["n_unaudited"] == 1


# ── C8 shallow, never mutating ────────────────────────────────────────────────────────────────────────────────────
def test_c8_the_overlay_copies_nothing_and_mutates_nothing():
    d = _doc("aplus")
    other = dict(_doc("aplus"), symbol="NOV")
    before = json.dumps(d, default=str, sort_keys=True)
    out, _s = AT.overlay_reads({"ZZZ": d, "NOV": other}, _Ov([_ov()]), S)
    assert out["ZZZ"] is not d and out["ZZZ"]["tile"] is d["tile"]
    assert out["ZZZ"]["tile"]["bars5"] is d["tile"]["bars5"]
    assert out["ZZZ"]["setups"]["kiss_fly"] is d["setups"]["kiss_fly"]                 # untouched reads shared
    assert d["setups"]["bull_flag"]["state"] == "aplus" and "audit" not in d["setups"]["bull_flag"]
    assert json.dumps(d, default=str, sort_keys=True) == before
    assert out["NOV"] is other                                                         # no overlay → the SAME doc


def test_c8_build_never_writes_the_held_state_back_to_the_stored_read(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)))
    GT.build(setup, now=NOW_B, store=gga)
    assert st.get_read(S, "GGA")["setups"][setup]["state"] == "aplus"
    assert "audit" not in st.get_read(S, "GGA")["setups"][setup]


# ── NEGATIVE: GG5 / GG1 never carry a byte of it ──────────────────────────────────────────────────────────────────
def _assert_clean(b, where):
    assert not set(NEW_KEYS) & set(b), where
    for path, k, v in walk(b):
        assert k not in ("audit", AUD.HELD_STATE), (where, path)
        if isinstance(v, str):
            assert AUD.HELD_STATE not in v, (where, path)


def test_gg5_and_gg1_serve_no_audit_key_and_the_gg5_board_golden_holds(monkeypatch):
    stores, _t = writes_text(monkeypatch)
    assert board_text(stores) == BOARD.read_text(encoding="utf-8")                   # the GG5 board golden
    st = stores["shadow"]
    doc = st.get_read(S, "GGA")
    setup = aplus_of(doc)
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)))             # an overlay IS on file
    for k in (setup, "postmarket", GC.LEDGER_SUB):
        _assert_clean(GT.build(k, now=NOW_B, store=st), ("GG5", k))
        _assert_clean(GT.build(k, now=NOW_B, store=st, variant=None), ("GG5 None", k))
        g1 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.OWN}, variant=V.GG1, shared=st)
        _assert_clean(GT.build(k, now=NOW_B, store=g1, variant=V.GG1), ("GG1", k))
    assert board_text(stores) == BOARD.read_text(encoding="utf-8")                   # still, after the GGA builds


# ── the strip's stale line ────────────────────────────────────────────────────────────────────────────────────────
def test_the_strip_is_stale_when_the_overlay_state_is_older_missing_or_failed(world):
    st, doc, setup = world
    lat = GT._at_utc(st.latest_pass())
    gga = gga_store(st)
    b = GT.build(setup, now=NOW_B, store=gga)
    assert b["audited"]["stale"] is True and b["audited"]["pass"]["text"] is None          # missing
    assert b["audited"]["stale_text"] == V.word("pass_stale", V.GGA, hhmm="10:41")
    state_ok(gga, st, at_=lat - timedelta(seconds=GC.PASS_CADENCE_SEC))
    assert GT.build(setup, now=NOW_B, store=gga)["audited"]["stale"] is True             # one pass older
    state_ok(gga, st, ok=False)
    assert GT.build(setup, now=NOW_B, store=gga)["audited"]["stale"] is True             # ran and failed
    state_ok(gga, st)
    a = GT.build(setup, now=NOW_B, store=gga)["audited"]
    assert a["stale"] is False and a["stale_text"] is None                                 # equal → fresh
    assert a["pass"]["n_held"] == 1 and a["pass"]["ok"] is True


# ── held_block: the banner's own gates ────────────────────────────────────────────────────────────────────────────
def _held_reads(upd):
    r = {"state": AUD.HELD_STATE, "entry_bar_t": "2026-10-13 10:40", "trigger": 11.0, "stop": 10.5,
         "audit": {"failed": [{"id": "G4", "why": "w"}], "text": "held text", "frame": "5m"}}
    return {"HHH": {"symbol": "HHH", "updated_at": upd, "setups": {"bull_flag": r}}}


def test_held_block_obeys_the_aplus_banner_gates():
    lat = {"date": S.isoformat(), "at": at(10, 41).astimezone(timezone.utc)}
    kw = dict(scan={}, cron=lat, session=S, v=V.GGA)
    fresh = AT.held_block(_held_reads(lat["at"]), lat, NOW_B, in_window=True, **kw)
    assert [r["symbol"] for r in fresh["rows"]] == ["HHH"]
    assert fresh["rows"][0]["held_by"] == [{"id": "G4", "why": "w"}] and fresh["rows"][0]["audit_text"] == "held text"
    # NEGATIVE: a read of an older pass is not listed (the banner's A11)
    older = AT.held_block(_held_reads(lat["at"] - timedelta(seconds=GC.PASS_CADENCE_SEC)), lat, NOW_B,
                          in_window=True, **kw)
    assert older["rows"] == [] and older["empty_text"] == V.word("held_empty", V.GGA)
    # NEGATIVE: outside the window → empty with the banner's own served reason
    closed = AT.held_block(_held_reads(lat["at"]), lat, NOW_B, in_window=False, **kw)
    want = GT.aplus_block({}, lat, NOW_B, in_window=False, scan={}, cron=lat, session=S, v=V.GGA)["empty_text"]
    assert closed["rows"] == [] and closed["empty_text"] == want and "market closed" in want
    # NEGATIVE: a dead cron pass → empty with the banner's reason
    late = NOW_B + timedelta(seconds=V.stale_after_sec(V.GGA) + 60)
    dead = AT.held_block(_held_reads(lat["at"]), lat, late, in_window=True, **kw)
    assert dead["rows"] == [] and dead["empty_text"] == GT.aplus_block(
        {}, lat, late, in_window=True, scan={}, cron=lat, session=S, v=V.GGA)["empty_text"]


# ── 🏁 audited vs original ────────────────────────────────────────────────────────────────────────────────────────
D1 = date(2026, 11, 3)
NOW_C = datetime(2026, 11, 4, 12, 0, tzinfo=ET)
SETUP = "bull_flag"


def _claim(sym, *, variant=None, state="shadow", d=D1, trigger=10.0, stop=9.0):
    ck = AL.claim_key(d, sym, SETUP, variant)
    _id = SHADOW_CLAIM_PREFIX + ck if state == "shadow" else ck
    return {"_id": _id, "state": state, "date": d.isoformat(), "symbol": sym, "setup": SETUP,
            "at": datetime.combine(d, datetime.min.time().replace(hour=15), tzinfo=timezone.utc).isoformat(),
            "trigger": trigger, "stop": stop, "price": trigger}


def _grade(sym, outcome, d=D1):
    g = {"entry": "no_entry"} if outcome == "no_entry" else {"entry": "filled", "outcome": outcome}
    return {"_id": LG.ledger_id(d.isoformat(), sym, SETUP, LG.KINDS[1]), "date": d.isoformat(), "symbol": sym,
            "setup": SETUP, "same": dict(g, version=GC.LEDGER_GRADE_VERSION)}


def _held(sym, ids, d=D1, state=None):
    return {"_id": f"{AL.claim_key(d, sym, SETUP, V.GGA)}#{AUD.HELD_ROW_STATE}", "date": d.isoformat(),
            "symbol": sym, "setup": SETUP, "state": state or AUD.HELD_ROW_STATE,
            "audit": {"failed": [{"id": i, "why": "w"} for i in ids], "passed": [], "version": 1}}


def stores(g5_alerts, g5_ledger, a_alerts, a_ledger):
    g5 = ST.GajjalaStore(colls={n: FakeColl() for n in ST.ALL if n not in (ST.ALERTS, ST.LEDGER)}
                         | {ST.ALERTS: FakeColl(g5_alerts), ST.LEDGER: FakeColl(g5_ledger)})
    return gga_store(g5, {ST.ALERTS: a_alerts, ST.LEDGER: a_ledger})


def base_world(extra_g5=(), extra_g5l=(), extra_a=(), extra_al=()):
    g5a = [_claim("AAA"), _claim("BBB", state="pushed")] + list(extra_g5)
    g5l = [_grade("AAA", "win"), _grade("BBB", "loss")] + list(extra_g5l)
    aa = [_claim("AAA", variant=V.GGA), _held("BBB", ["G4"])] + list(extra_a)
    al = [_grade("AAA", "win")] + list(extra_al)
    return stores(g5a, g5l, aa, al)


def _identity(c):
    o, a = c["sides"]
    r = c["recon"]
    return o["n"] == a["n"] + c["held"]["n"] + r["original_only"] - r["audited_only"] - r["both"]


def test_compare_arithmetic_original_audited_held_by_rule_by_day():
    c = AT.compare_block(base_world(), date(2026, 11, 4), NOW_C, span="5d", is_today=True)
    o, a = c["sides"]
    assert (o["key"], o["n"], o["win"], o["loss"], o["mean_r"], o["win_pct"]) == ("original", 2, 1, 1, 0.0, 50)
    assert (a["key"], a["n"], a["win"], a["loss"], a["mean_r"]) == ("audited", 1, 1, 0, float(GC.LEDGER_R_MULT))
    h = c["held"]
    assert (h["n"], h["loss"], h["win"], h[AT.NO_ORIGINAL]) == (1, 1, 0, 0)
    assert h["rows"][0]["outcome"] == "loss" and h["rows"][0]["held_by"] == ["G4"]
    br = {r["id"]: r for r in c["by_rule"]}
    assert (br["G4"]["n_held"], br["G4"]["loss"]) == (1, 1) and br["G1"]["n_held"] == 0
    assert c["by_rule_note"] == V.word("by_rule_note", V.GGA)
    for k, side in (("original", o), ("audited", a), ("held", h)):
        assert sum(d[k]["n"] for d in c["by_day"]) == side["n"]
        assert sum(d[k]["win"] for d in c["by_day"]) == side["win"]
    assert c["entry_weeks"] == 1 and c["floor_weeks"] == AUD.MEASURE_FLOOR_WEEKS and c["floor_reached"] is False
    assert c["unmeasured_text"] == V.word("unmeasured", V.GGA, floor=AUD.MEASURE_FLOOR_WEEKS)
    assert str(AUD.MEASURE_FLOOR_WEEKS) in c["unmeasured_text"]
    assert c["recon"]["original_only"] == 0 and c["recon"]["audited_only"] == 0 and _identity(c)
    assert c["title"] == V.word("compare_title", V.GGA)


def test_compare_recon_original_only_audited_only_no_original_and_both():
    c1 = AT.compare_block(base_world(extra_g5=[_claim("CCC")], extra_g5l=[_grade("CCC", "win")]),
                          date(2026, 11, 4), NOW_C, span="5d")
    assert c1["recon"]["original_only"] == 1 and _identity(c1)
    assert c1["recon"]["text"] == V.word("compare_recon", V.GGA, original_only=1, audited_only=0)
    # an audited claim whose 🚩 claim settled `failed` (never a 🏁 row)
    c2 = AT.compare_block(base_world(extra_g5=[_claim("DDD", state="failed")],
                                     extra_a=[_claim("DDD", variant=V.GGA)]), date(2026, 11, 4), NOW_C, span="5d")
    assert c2["recon"]["audited_only"] == 1 and c2["sides"][1]["n"] == 2 and _identity(c2)
    # a held row with no original
    c3 = AT.compare_block(base_world(extra_a=[_held("EEE", ["G1", "G2"])]), date(2026, 11, 4), NOW_C, span="5d")
    eee = next(r for r in c3["held"]["rows"] if r["symbol"] == "EEE")
    assert eee["outcome"] == AT.NO_ORIGINAL and eee["outcome_text"] == AT.NO_ORIGINAL_TEXT
    assert c3["held"][AT.NO_ORIGINAL] == 1 and _identity(c3)
    assert c3["recon"]["audited_only"] == 1 and c3["recon"]["both"] == 0   # a held row with no original counts here
    assert c3["recon"]["original_only"] == 0
    br = {r["id"]: r["n_held"] for r in c3["by_rule"]}
    assert br == {"G1": 1, "G2": 1, "G4": 1}                       # one held row counts under every rule it failed
    # held on one pass, audited A+ later the same day
    c4 = AT.compare_block(base_world(extra_g5=[_claim("FFF")], extra_g5l=[_grade("FFF", "win")],
                                     extra_a=[_claim("FFF", variant=V.GGA), _held("FFF", ["G2"])]),
                          date(2026, 11, 4), NOW_C, span="5d")
    assert c4["recon"]["both"] == 1 and _identity(c4)
    assert c4["recon"]["audited_only"] == 0 and c4["recon"]["original_only"] == 0
    r4 = c4["recon"]                                               # NEGATIVE: the identity fails without `both`
    assert c4["sides"][0]["n"] != (c4["sides"][1]["n"] + c4["held"]["n"] + r4["original_only"] - r4["audited_only"])
    assert set(r4) == {"original_only", "audited_only", "both", "text"}


def test_a_hash_held_doc_in_shadow_is_not_held_and_a_gga_shadow_claim_is_a_row():
    bad = _held("GGG", ["G1"], state="shadow")
    c = AT.compare_block(base_world(extra_a=[bad]), date(2026, 11, 4), NOW_C, span="5d")
    assert "GGG" not in {r["symbol"] for r in c["held"]["rows"]} and c["held"]["n"] == 1
    assert c["sides"][1]["n"] == 1                                 # NEGATIVE: never an audited row either
    assert any(r["id"] == LG.ledger_id(D1.isoformat(), "AAA", SETUP, "aplus")
               for r in LG.rows_for([D1], base_world(), variant=V.GGA))


def test_the_floor_is_a_count_and_the_unmeasured_words_stay():
    mondays = [date(2026, 11, 2) + timedelta(weeks=k) for k in range(AUD.MEASURE_FLOOR_WEEKS)]
    aa = [_claim("WK", variant=V.GGA, d=d) for d in mondays]
    al = [_grade("WK", "open", d=d) for d in mondays]
    st = stores([], [], aa, al)
    last = mondays[-1] + timedelta(days=2)
    c = AT.compare_block(st, last, datetime.combine(last, datetime.min.time().replace(hour=12), tzinfo=ET), span="5d")
    assert c["entry_weeks"] == AUD.MEASURE_FLOOR_WEEKS and c["floor_reached"] is True
    assert c["unmeasured_text"] == V.word("floor_reached", V.GGA, n=AUD.MEASURE_FLOOR_WEEKS,
                                          floor=AUD.MEASURE_FLOOR_WEEKS)
    assert "UNMEASURED" in c["unmeasured_text"]
    assert not [p for p, k, _v in walk(c) if k == "measured"]
    # one week short → not reached (the floor counts the whole record, never the span shown)
    st2 = stores([], [], aa[:-1], al[:-1])
    c2 = AT.compare_block(st2, last, datetime.combine(last, datetime.min.time().replace(hour=12), tzinfo=ET),
                          span="5d")
    assert c2["entry_weeks"] == AUD.MEASURE_FLOOR_WEEKS - 1 and c2["floor_reached"] is False


def test_compare_read_fault_raises_and_the_tab_softens_it():
    st = base_world()
    st.shared._injected[ST.LEDGER] = FakeColl(fail=True)
    with pytest.raises(Exception):
        AT.compare_block(st, date(2026, 11, 4), NOW_C, span="5d")
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st)
    assert "audited_compare" in b and b["audited_compare"] is None


def test_the_track_record_sub_serves_the_gga_title_and_the_compare_block():
    st = base_world()
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st, span="5d")
    assert b["tab"] == "gajjala_audited"
    assert b["track_record"]["title"] == V.word("ledger_title", V.GGA)
    assert b["audited_compare"]["sides"][0]["n"] == 2
    # NEGATIVE: the compare block is 🏁 only
    assert "audited_compare" not in GT.build("bull_flag", now=NOW_C, store=st)


# ── C13 JSON-native · words ───────────────────────────────────────────────────────────────────────────────────────
def test_c13_every_audited_payload_dumps_and_carries_no_decimal(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1", "G4")))
    state_ok(gga, st)
    for k in (setup, "postmarket", GC.LEDGER_SUB):
        b = GT.build(k, now=NOW_B, store=gga, owner=True)
        json.dumps(GT._plain(b), allow_nan=False)
        assert not [p for p, _k, v in walk(b) if isinstance(v, Decimal)]
    c = base_world()
    b2 = GT.build(GC.LEDGER_SUB, now=NOW_C, store=c)
    json.dumps(GT._plain(b2), allow_nan=False)
    assert not [p for p, _k, v in walk(b2) if isinstance(v, Decimal)]


def test_no_edge_word_in_the_new_blocks_and_no_b_word_anywhere(world):
    st, doc, setup = world
    gga = gga_store(st)
    plant(gga, doc, setup, entry(doc["setups"][setup], failed=("G1",)))
    b = GT.build(setup, now=NOW_B, store=gga)
    c = GT.build(GC.LEDGER_SUB, now=NOW_C, store=base_world(extra_a=[_held("EEE", ["G1"])]))
    for blob in (b["audited"], b["held"], c["audited_compare"]):
        assert not [s for s in strings(blob) if EDGE.search(s)]
    for whole in (b, c):
        assert not [s for s in strings(whole) if B_WORD.search(s)]
