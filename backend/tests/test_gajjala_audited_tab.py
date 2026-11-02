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
GGA_OWN = (ST.ALERTS, ST.STATE, ST.LEDGER, ST.OVERLAY, ST.EXITS)
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
    assert [r["id"] for r in b["audited"]["registry"]] == [r.id for r in AUD.REGISTRY]   # WP-A pins the 12 ids
    assert b["audited"]["on_ids"] == [r.id for r in AUD.on_rules()] and "G3" not in b["audited"]["on_ids"]
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


def _claim(sym, *, variant=None, state="shadow", d=D1, trigger=10.0, stop=9.0, bar=None, audit=None, setup=SETUP):
    ck = AL.claim_key(d, sym, setup, variant)
    _id = SHADOW_CLAIM_PREFIX + ck if state == "shadow" else ck
    doc = {"_id": _id, "state": state, "date": d.isoformat(), "symbol": sym, "setup": setup,
           "at": datetime.combine(d, datetime.min.time().replace(hour=15), tzinfo=timezone.utc).isoformat(),
           "trigger": trigger, "stop": stop, "price": trigger}
    if bar is not None:
        doc["entry_bar_t"] = bar
    if audit is not None:
        doc["audit"] = audit
    return doc


def _grade(sym, outcome, d=D1, setup=SETUP):
    g = {"entry": "no_entry"} if outcome == "no_entry" else {"entry": "filled", "outcome": outcome}
    return {"_id": LG.ledger_id(d.isoformat(), sym, setup, LG.KINDS[1]), "date": d.isoformat(), "symbol": sym,
            "setup": setup, "same": dict(g, version=GC.LEDGER_GRADE_VERSION)}


def _held(sym, ids, d=D1, state=None, bar=None, passed=(), tie=None, setup=SETUP):
    a = {"failed": [{"id": i, "why": "w"} for i in ids], "passed": list(passed), "version": 1}
    if tie is not None:
        a["values"] = {"T1": {"tie": tie}}
    doc = {"_id": f"{AL.claim_key(d, sym, setup, V.GGA)}#{AUD.HELD_ROW_STATE}", "date": d.isoformat(),
           "symbol": sym, "setup": setup, "state": state or AUD.HELD_ROW_STATE, "audit": a}
    if bar is not None:
        doc["entry_bar_t"] = bar
    return doc


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
    # REWRITTEN 2026-11-02 (🔁 one count per stock per day, SPEC luk-track §3.2 [C5]): `recon` is id-set arithmetic
    # over ALL ids (untouched) while `n` counts the COUNTED rows — the identity holds in the n + n_dup form
    o, a = c["sides"]
    r, h = c["recon"], c["held"]
    return (o["n"] + o["n_dup"] == a["n"] + a["n_dup"] + h["n"] + h["n_dup"] + r["original_only"] - r["audited_only"]
            - r["both"])


def test_compare_arithmetic_original_audited_held_by_rule_by_day():
    c = AT.compare_block(base_world(), date(2026, 11, 4), NOW_C, span="5d", is_today=True)
    o, a = c["sides"]
    assert (o["key"], o["n"], o["win"], o["loss"], o["mean_r"], o["win_pct"]) == ("original", 2, 1, 1, 0.0, 50)
    assert (a["key"], a["n"], a["win"], a["loss"], a["mean_r"]) == ("audited", 1, 1, 0, float(GC.LEDGER_R_MULT))
    h = c["held"]
    assert (h["n"], h["loss"], h["win"], h[AT.NO_ORIGINAL]) == (1, 1, 0, 0)
    assert h["rows"][0]["outcome"] == "loss" and h["rows"][0]["held_by"] == ["G4"]
    assert "by_rule" not in c                                      # NEGATIVE: the held-only table is gone (§3.4)
    pr = {r["key"]: r for r in c["per_rule"]}
    # BBB's marker failed G4 (its other filters unrecorded) — no bar on either claim → the marker by fallback
    assert (pr["G4"]["other"]["n"], pr["G4"]["other"]["loss"]) == (1, 1) and pr["G1"]["other"]["n"] == 0
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
    pr = {r["key"]: r for r in c3["per_rule"]}                    # EEE has no original: no_original on G1 + G2
    assert {k: pr[k]["other"][AT.NO_ORIGINAL] for k in ("G1", "G2", "G4")} == {"G1": 1, "G2": 1, "G4": 0}
    assert {k: pr[k]["other"]["n"] for k in ("G1", "G2", "G4")} == {"G1": 0, "G2": 0, "G4": 1}
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


# ── 🧪 the per-rule table (SPEC gg-audited-mods §3.4 / WP-D, 2026-11-01) ─────────────────────────────────────────────
# Ajay 2026-11-01: "Yes make the changes in audited please" · "But keep a track record too to see the winners and loster"
B1040, B0805, B1115 = "2026-11-03 10:40", "2026-11-03 08:05", "2026-11-03 11:15"
UN_MEASURED = re.compile(r"(?<!un)measured", re.I)
VCP = AUD.T3_SETUPS[0]
KEYS_12 = ["G1", "G2", "G4", "T1", "T2", "A1", "H1", "T4", "A2", "T3_2R", "T3_3R", "T5"]


def _filters():
    return [r.id for r in AUD.filter_rules()]


def _aud(failed=(), *, t1=True, tie=None):
    """A claim / marker audit block as audited_pass stores it: `passed` = every other filter rule (T1 only when it was
    judged — a read another rule held carries no T1)."""
    ids = [i for i in _filters() if t1 or i != "T1"]
    a = {"passed": [i for i in ids if i not in failed], "failed": [{"id": i, "why": "w"} for i in failed],
         "rules": ids, "values": {}, "version": AUD.AUDIT_VERSION, "frame": "5m"}
    if tie is not None:
        a["values"]["T1"] = {"tie": tie}
    return a


def _mk(sym, *, gg5_bar=B1040, outcome="win", setup=SETUP, claim=None, marker=None, gga_outcome=None):
    """(g5 claim, g5 grade, gga docs, gga grades) for one name: `claim` = (bar, audit|None), `marker` = (bar, audit)."""
    g5 = [_claim(sym, bar=gg5_bar, setup=setup)]
    g5l = [_grade(sym, outcome, setup=setup)]
    a, al = [], []
    if claim is not None:
        a.append(_claim(sym, variant=V.GGA, bar=claim[0], audit=claim[1], setup=setup))
        if gga_outcome is not None:
            al.append(_grade(sym, gga_outcome, setup=setup))
    if marker is not None:
        m = _held(sym, [], bar=marker[0], setup=setup)
        m["audit"] = marker[1]
        a.append(m)
    return g5, g5l, a, al


def _world(*names, exits=()):
    g5, g5l, a, al = [], [], [], []
    for n in names:
        g5 += n[0]
        g5l += n[1]
        a += n[2]
        al += n[3]
    st = stores(g5, g5l, a, al)
    st._injected[ST.EXITS] = FakeColl(list(exits))
    return st


def _pr(st):
    c = AT.compare_block(st, date(2026, 11, 4), NOW_C, span="5d")
    return c, {r["key"]: r for r in c["per_rule"]}


def _no_orig(row):
    return row["with"][AT.NO_ORIGINAL] + row["other"][AT.NO_ORIGINAL]


def test_per_rule_rows_are_one_per_on_rule_in_registry_order_and_by_rule_is_gone():
    c, pr = _pr(_world())
    assert [r["key"] for r in c["per_rule"]] == KEYS_12 and "G3" not in pr          # G3 lane-only: never a row
    assert [r["key"] for r in c["per_rule"]] == [k for r in AUD.on_rules() for k in (
        [AUD.exit_col_key(r.id, m) for m in AUD.T3_R_MULTS] if r.id == "T3" else
        [AUD.exit_col_key(r.id)] if r.kind == AUD.KIND_EXIT else [r.id])]
    assert c["per_rule_title"] == V.word("per_rule_title", V.GGA)
    assert c["by_rule_note"] == V.word("by_rule_note", V.GGA)
    assert "by_rule" not in c                                                          # NEGATIVE
    assert {r["kind"] for r in c["per_rule"]} == {AUD.KIND_FILTER, AT.KIND_CAP, AUD.KIND_EXIT}
    assert pr["T1"]["kind"] == AT.KIND_CAP and pr["T5"]["kind"] == AUD.KIND_EXIT and pr["G1"]["kind"] == "filter"
    for r in c["per_rule"]:
        assert set(r) == {"key", "id", "name", "kind", "label", "with", "other", "not_judged", "fired_alone",
                          "tie_held", "delta_text", "text"}
        for side in ("with", "other"):
            assert set(r[side]) == {"label", "n", "n_dup", "win", "loss", "unfilled", "open_flat", "pending",
                                    AT.NO_ORIGINAL, "mean_r", "text"}           # n_dup: 🔁 2026-11-02
        assert r["text"] == (f"{r['label']} · {r['with']['text']} · {r['other']['text']} · {r['delta_text']} · "
                             f"{GT.UNMEASURED}")
    # an empty record: every filter row says so in words, the T4 row still names its fire counts
    assert pr["G1"]["delta_text"] == V.word("per_rule_no_rows", V.GGA)
    assert V.word("per_rule_t4_fired", V.GGA, fired=0, alone=0) in pr["T4"]["other"]["text"]
    assert pr["T5"]["delta_text"] == V.word("per_rule_no_rows", V.GGA)


def test_a_filter_row_counts_the_originals_outcome_with_and_held():
    st = _world(_mk("AAA", outcome="win", claim=(B1040, _aud())),
                _mk("BBB", outcome="loss", marker=(B1040, _aud(("G4",), t1=False))))
    _c, pr = _pr(st)
    g4 = pr["G4"]
    assert (g4["with"]["n"], g4["with"]["win"], g4["other"]["n"], g4["other"]["loss"]) == (1, 1, 1, 1)
    assert g4["delta_text"] == V.word("per_rule_delta_filter", V.GGA, w="0 winners", l="1 loser", u=0)
    assert g4["with"]["label"] == V.word("per_rule_with", V.GGA)
    assert g4["other"]["label"] == V.word("per_rule_held", V.GGA)
    assert g4["not_judged"] == 0 and g4["fired_alone"] is None and g4["tie_held"] is None
    assert (pr["G1"]["with"]["n"], pr["G1"]["other"]["n"]) == (2, 0)                  # BBB passed G1 (held by G4)
    assert pr["G1"]["delta_text"] == V.word("per_rule_delta_filter", V.GGA, w="0 winners", l="0 losers", u=0)
    # a held read carries no T1 → T1 judged AAA only; BBB is not_judged on T1, never with / held
    t1 = pr["T1"]
    assert (t1["with"]["n"], t1["other"]["n"], t1["not_judged"]) == (1, 0, 1)
    assert t1["delta_text"].endswith(V.word("per_rule_not_judged", V.GGA, n=1))
    assert t1["other"]["label"] == V.word("per_rule_cap_held", V.GGA)


def test_c1_the_gapper_a_premarket_marker_never_scores_the_rth_original():
    """🚩 rang CCC on 10:40; a legacy 08:05 marker (failed T2 + H1) and the 10:40 audited claim (passed) share its id."""
    st = _world(_mk("CCC", outcome="win", claim=(B1040, _aud()), marker=(B0805, _aud(("T2", "H1"), t1=False))))
    _c, pr = _pr(st)
    t2 = pr["T2"]
    assert (t2["with"]["n"], t2["with"]["win"], t2["other"]["n"]) == (1, 1, 0)        # the 10:40 record scores it
    assert t2["other"][AT.NO_ORIGINAL] == 1 and _no_orig(t2) == 1                      # the 08:05 marker lands ONCE
    assert pr["H1"]["other"]["n"] == 0 and pr["H1"]["other"][AT.NO_ORIGINAL] == 1
    assert pr["G1"]["with"]["n"] == 1 and _no_orig(pr["G1"]) == 1                      # once on every rule it judged
    assert "1 no original row" in t2["other"]["text"]
    assert pr["T1"]["with"]["n"] == 1 and _no_orig(pr["T1"]) == 0                      # the marker never judged T1


def test_c1_NEGATIVE_marker_on_the_bar_wins_and_a_later_claim_is_no_original():
    st = _world(_mk("DDD", outcome="loss", marker=(B1040, _aud(("G2",), t1=False)), claim=(B1115, _aud())))
    _c, pr = _pr(st)
    g2 = pr["G2"]
    assert (g2["other"]["n"], g2["other"]["loss"], g2["with"]["n"]) == (1, 1, 0)
    assert g2["with"][AT.NO_ORIGINAL] == 1 and _no_orig(g2) == 1                       # the 11:15 claim
    assert g2["delta_text"] == V.word("per_rule_delta_filter", V.GGA, w="0 winners", l="1 loser", u=0)


def test_c1_an_original_with_no_bar_falls_back_to_the_marker_then_the_claim():
    st = _world(_mk("EEE", gg5_bar=None, outcome="loss", marker=(B0805, _aud(("G1",), t1=False)),
                    claim=(B1040, _aud())),
                _mk("FFF", gg5_bar=None, outcome="win", claim=(B1040, _aud())))
    _c, pr = _pr(st)
    g1 = pr["G1"]
    assert (g1["other"]["n"], g1["other"]["loss"]) == (1, 1)                           # EEE: the marker first
    assert (g1["with"]["n"], g1["with"]["win"]) == (1, 1)                              # FFF: the claim
    assert g1["with"][AT.NO_ORIGINAL] == 1                                             # EEE's claim was not taken


def test_c1_NEGATIVE_a_record_on_a_different_bar_never_scores_and_a_claim_without_audit_is_not_judged():
    st = _world(_mk("GGG", outcome="win", claim=(B1115, _aud(("G4",)))),              # wrong bar → no record
                _mk("HHH", outcome="loss", claim=(B1040, None)))                       # recorded before the audit
    _c, pr = _pr(st)
    for k in _filters():
        r = pr[k]
        assert (r["with"]["n"], r["other"]["n"], r["not_judged"]) == (0, 0, 2), k
    assert pr["G4"]["other"][AT.NO_ORIGINAL] == 1 and pr["G1"]["with"][AT.NO_ORIGINAL] == 1
    assert _no_orig(pr["G2"]) == 1                                                     # HHH (no audit) never counts
    assert pr["G1"]["delta_text"] == (V.word("per_rule_no_rows", V.GGA) + " · "
                                      + V.word("per_rule_not_judged", V.GGA, n=2))


def test_c2_the_t4_row_serves_fired_and_fired_alone():
    st = _world(_mk("T4A", outcome="win", marker=(B1040, _aud(("T4",), t1=False))),
                _mk("T4B", outcome="loss", marker=(B1040, _aud(("T4",), t1=False))),
                _mk("T4C", outcome="no_entry", marker=(B1040, _aud(("T4", "G2"), t1=False))))
    c, pr = _pr(st)
    t4 = pr["T4"]
    assert t4["other"]["n"] == 3 and t4["fired_alone"] == 2
    assert V.word("per_rule_t4_fired", V.GGA, fired=3, alone=2) in t4["other"]["text"]
    assert t4["delta_text"] == V.word("per_rule_delta_filter", V.GGA, w="1 winner", l="1 loser", u=1)
    assert [r["key"] for r in c["per_rule"] if r["fired_alone"] is not None] == ["T4"]  # NEGATIVE: T4 only
    assert pr["G2"]["fired_alone"] is None and "fired on" not in pr["G2"]["other"]["text"]


def test_c3_the_t1_row_counts_the_tie_held():
    st = _world(_mk("TIE", outcome="win", marker=(B1040, _aud(("T1",), tie=True))),
                _mk("NOT", outcome="loss", marker=(B1040, _aud(("T1",), tie=False))),
                _mk("INN", outcome="win", claim=(B1040, _aud())))
    c, pr = _pr(st)
    t1 = pr["T1"]
    assert (t1["with"]["n"], t1["other"]["n"], t1["tie_held"]) == (1, 2, 1)
    assert V.word("per_rule_t1_tie", V.GGA, n=1) in t1["other"]["text"]
    assert t1["other"]["label"] == V.word("per_rule_cap_held", V.GGA)
    assert t1["delta_text"] == V.word("per_rule_delta_filter", V.GGA, w="1 winner", l="1 loser", u=0)
    assert [r["key"] for r in c["per_rule"] if r["tie_held"] is not None] == ["T1"]    # NEGATIVE: T1 only
    # NEGATIVE: no tie → the tie words never print
    _c2, pr2 = _pr(_world(_mk("NOT", outcome="loss", marker=(B1040, _aud(("T1",), tie=False)))))
    assert pr2["T1"]["tie_held"] == 0 and "tied bar" not in pr2["T1"]["other"]["text"]


def _exit_doc(sym, setup, cols):
    return {"_id": LG.ledger_id(D1.isoformat(), sym, setup, LG.KINDS[1]), "date": D1.isoformat(), "symbol": sym,
            "setup": setup, "kind": LG.KINDS[1], "version": 1, **cols}


def test_exit_rows_score_the_exit_grade_beside_ggs_math_on_the_same_rows():
    win2 = {"entry": "filled", "outcome": "win", "r": 2.0, "r_mult": 2.0}
    t5 = {"entry": "filled", "outcome": "loss", "r": -0.4, "reason": "ema21_close"}
    st = _world(_mk("VCP", setup=VCP, claim=(B1040, _aud()), gga_outcome="win"),
                _mk("BFL", claim=(B1040, _aud()), gga_outcome="loss"),
                exits=[_exit_doc("VCP", VCP, {AUD.exit_col_key("T3", AUD.T3_R_MULTS[0]): win2,
                                              AUD.exit_col_key("T5"): t5})])
    _c, pr = _pr(st)
    k2, k3 = (AUD.exit_col_key("T3", m) for m in AUD.T3_R_MULTS)
    r2 = pr[k2]
    assert (r2["with"]["n"], r2["with"]["win"], r2["with"]["mean_r"]) == (1, 1, 2.0)   # NEGATIVE: bull flag not in T3
    assert (r2["other"]["n"], r2["other"]["win"]) == (1, 1)                            # GG's math, the same row
    assert r2["other"]["label"] == V.word("per_rule_gg_math", V.GGA) and r2["kind"] == AUD.KIND_EXIT
    assert r2["delta_text"] == V.word("per_rule_delta_exit", V.GGA, rule=r2["label"], ww=1, wl=0, gw=1, gl=0, n=1)
    assert f"+{AUD.T3_R_MULTS[0]:g}R" in r2["label"] and GT._setup_label(VCP) in r2["label"]
    r3 = pr[k3]
    assert r3["with"]["pending"] == 1 and r3["delta_text"] == V.word("per_rule_not_graded", V.GGA)
    assert "1 not graded yet" in r3["with"]["text"]
    t5r = pr["T5"]
    assert t5r["with"]["n"] == 2 and t5r["with"]["loss"] == 1 and t5r["with"]["pending"] == 1
    assert t5r["with"]["mean_r"] == -0.4                                               # the stored R, not ±1
    assert (t5r["other"]["n"], t5r["other"]["win"], t5r["other"]["loss"]) == (2, 1, 1)
    assert t5r["not_judged"] == 0 and t5r["fired_alone"] is None and t5r["tie_held"] is None


def test_exit_rows_entry_words_and_unfilled():
    st = _world(_mk("NOE", setup=VCP, claim=(B1040, _aud()), gga_outcome="no_entry"),
                exits=[_exit_doc("NOE", VCP, {AUD.exit_col_key("T5"): {"entry": "no_entry", "outcome": None,
                                                                        "r": None},
                                              AUD.exit_col_key("T3", AUD.T3_R_MULTS[0]): {"entry": None,
                                                                                           "reason": "no_frame"}})])
    _c, pr = _pr(st)
    assert pr["T5"]["with"]["unfilled"] == 1 and pr["T5"]["with"]["mean_r"] is None
    k2 = AUD.exit_col_key("T3", AUD.T3_R_MULTS[0])
    assert pr[k2]["with"]["pending"] == 1 and pr[k2]["delta_text"] == V.word("per_rule_not_graded", V.GGA)


def test_per_rule_read_faults_raise_and_the_tab_softens_them():
    st = _world(_mk("AAA", claim=(B1040, _aud())))
    st._injected[ST.EXITS] = FakeColl(fail=True)
    with pytest.raises(LG.LedgerReadError):
        AT.compare_block(st, date(2026, 11, 4), NOW_C, span="5d")
    assert GT.build(GC.LEDGER_SUB, now=NOW_C, store=st)["audited_compare"] is None

    class _None:
        def alert_rows(self, sessions):
            return None
    with pytest.raises(LG.LedgerReadError):
        AT._original_bars(_None(), [D1])
    with pytest.raises(LG.LedgerReadError):
        AT._claim_audits(_None(), [D1])


def test_the_claim_readers_take_only_their_own_claims():
    st = _world(_mk("AAA", claim=(B1040, _aud()), marker=(B0805, _aud(("G1",), t1=False))))
    ca = AT._claim_audits(st, [D1])
    rid = LG.ledger_id(D1.isoformat(), "AAA", SETUP, LG.KINDS[1])
    assert list(ca) == [rid] and ca[rid]["entry_bar_t"] == B1040                        # NEGATIVE: never the `#held`
    assert ca[rid]["audit"]["passed"] == _filters()
    ob = AT._original_bars(st.shared, [D1])
    assert ob == {rid: B1040}
    # NEGATIVE: a 🚩 GG1 / GGA claim planted in the GG5 collection is never an original's bar
    stray = _claim("ZZZ", variant=V.GG1, bar=B1040)
    st.shared._injected[ST.ALERTS].docs[stray["_id"]] = stray
    assert AT._original_bars(st.shared, [D1]) == {rid: B1040}


def test_per_rule_is_json_native_and_free_of_the_forbidden_words():
    st = _world(_mk("AAA", outcome="win", claim=(B1040, _aud())),
                _mk("T4A", outcome="loss", marker=(B1040, _aud(("T4",), t1=False))),
                _mk("TIE", outcome="no_entry", marker=(B1040, _aud(("T1",), tie=True))),
                _mk("VCP", setup=VCP, claim=(B1040, _aud()), gga_outcome="win"),
                exits=[_exit_doc("VCP", VCP, {AUD.exit_col_key("T5"): {"entry": "filled", "outcome": "win",
                                                                        "r": 0.6667}})])
    c, _rows = _pr(st)
    json.dumps(c["per_rule"], allow_nan=False)                                         # no default= — JSON-native
    assert not [p for p, _k, v in walk(c) if isinstance(v, Decimal)]
    for s in strings({"t": c["per_rule_title"], "r": c["per_rule"]}):
        assert "None" not in s and not EDGE.search(s) and not B_WORD.search(s), s
        assert not UN_MEASURED.search(s), s
    b = GT.build(GC.LEDGER_SUB, now=NOW_C, store=st)
    assert [r["key"] for r in b["audited_compare"]["per_rule"]] == KEYS_12
    assert "by_rule" not in b["audited_compare"]
    json.dumps(GT._plain(b), allow_nan=False)
