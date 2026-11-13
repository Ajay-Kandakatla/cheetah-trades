"""📋 All strategies — the ranked table on 🚩 Gajjala's tab (SPEC 2026-11-13 REV 2 §3.2–§3.4, WP-A, tests T1–T16).

Ajay 2026-11-13, verbatim: "Hey can you build be a table like track record on Gajjals landing page.. Call all strategies.
I want this table to rank based how gajjals sees them.. He watches 18 stocks simultaneously … So A+'s on top and potental
next and others close to strategies next liek EMA near kiss first, horizontal fade 9 EM Anad 25 EMA merge second and VCP
next reversal potental next with categories showing in the table"

chart_maps/gajjala/all_table.py builds the `table` block from the setup subs' OWN cards; tab.build serves it on
GC.TABLE_SUB (GG5 only); the route adds ONE live fan-out over its rows. DISPLAY ORDER ONLY — NEGATIVES are mandatory:
the cut-then-partition invariant (C3), today's spark only (C4), the three session words (C2), the long-flag word (C7),
GG1 / 🧪 fail-open, no fetch, no private key, NaN, faults.
(T17 / T18 are the re-pinned strip counts in test_gajjala_counts_legend_2026_10_18.py and
test_gajjala_variant_gg5_identity.py.)

GOLDENS regenerated 2026-11-13 with the recipe (GG_WRITE_GOLDEN=1 … -k golden / -k board), key-for-key diff checked by
dropping the 📋 `subs` entry and the identity file's `all_strategies` boards — IDENTICAL after that on all four:
  backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json   22 paths: `subs` + the all_strategies board per mode (6 rows)
  frontend/…/gajjala_potential_golden_2026_10_15.json          2 paths: `subs` (the 📋 entry first)
  frontend/…/gajjala_on_open_golden_2026_10_15.json            3 paths: `subs`
  frontend/…/gajjala_track_record_golden_2026_10_16.json       3 paths: `subs`
The WRITES golden (gg5_writes_2026_10_27.json) did NOT move.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

import pytest

from chart_maps.gajjala import all_table as TBL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import entry_marks as EM
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import promo_names as PN
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import tape as TP
from chart_maps.gajjala import trader_names as TN
from chart_maps.gajjala import variant as V
from tests.test_gajjala_store import FakeColl, fake_store
from tests.test_gajjala_tab import NOW, PREV, S, R, bars, latest, read_doc, run_route, scan_doc, utc

BF, KF, HF, VC, RS = "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
OLD = utc(4, 5)
B_WORD = re.compile("b" + "ounc", re.I)
OWNER = "ajaykandakatla@gmail.com"


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


# ── fixtures ─────────────────────────────────────────────────────────────────────────────────────────────────────
def scan(sym, *, volume=2e6, change=40.0, first=OLD):
    d = scan_doc(sym, volume=volume, change=change)
    d["first_qualified_at"] = first
    return d


def store(docs, *, scans=None, trackers=(), at=NOW):
    return fake_store(**{ST.READS: FakeColl(list(docs)),
                         ST.SCAN: FakeColl(list(scans) if scans is not None else [scan(d["symbol"]) for d in docs]),
                         ST.PASSES: FakeColl([latest(at=at)]), ST.POTENTIALS: FakeColl(list(trackers))})


def flag(st, *syms):
    st.coll(ST.STATE).docs[ST.BROKER_STATE_ID] = {"_id": ST.BROKER_STATE_ID, "added": list(syms), "removed": []}
    return st


def kiss(rvol):
    return {"rvol": {"rvol": rvol, "basis": "actual"}}


def gap(pct):
    return [{"key": "k6_merge", "label": "K6 EMAs merging", "value": f"EMAs {pct:.2f}% apart", "ok": True}]


def t1_docs():
    """T1 — one name per read: 🚩 A+ (10:05), 💋 triggered (09:50), 🌀 armed potential, 🎾 building potential, two 💋
    forming (rel volume 3 vs 5), ➖ forming + ➖ partial with gaps, a 🚩 forming, a 🎾 stopped."""
    return [
        read_doc("A1", {BF: R(BF, "aplus", broke=True, entry_bar_t="2026-10-13 10:05")}),
        read_doc("K1", {KF: R(KF, "triggered", broke=True, entry_bar_t="2026-10-13 09:50", bars_since_entry=8)}),
        read_doc("V1", {VC: R(VC, "forming", ready=True, base={"bars": 2})}),
        read_doc("S1", {RS: R(RS, "forming", ready=False, base={"bars": 2})}),
        read_doc("K2", {KF: R(KF, "forming", base={"bars": 0})}, ctx=kiss(3.0)),
        read_doc("K3", {KF: R(KF, "forming", base={"bars": 0})}, ctx=kiss(5.0)),
        read_doc("H1", {HF: R(HF, "forming", base={"bars": 0}, criteria=gap(0.5))}),
        read_doc("H2", {HF: R(HF, "partial", missed=["k6_merge"], criteria=gap(0.2))}),
        read_doc("B2", {BF: R(BF, "forming", base={"bars": 0})}),
        read_doc("S2", {RS: R(RS, "stopped", broke=True, entry_bar_t="2026-10-13 10:00")}),
    ]


T1_ORDER = [("A1", BF, 1), ("K1", KF, 1), ("V1", VC, 2), ("S1", RS, 2), ("K3", KF, 3), ("K2", KF, 3), ("H1", HF, 3),
            ("B2", BF, 3), ("H2", HF, 4), ("S2", RS, 4)]


def board(st, sub=GC.TABLE_SUB, **kw):
    return GT.build(sub, now=kw.pop("now", NOW), store=st, **kw)


def table(st, **kw):
    return board(st, **kw)["table"]


def rows_of(t):
    return [(r["symbol"], r["setup"], r["tier"], r["rank"]) for r in t["rows"]]


def fake_tile(sym, setup=BF, state="forming"):
    """A setup-sub card as tab.setup_tile leaves it (named keys only) — for the block-level cap tests."""
    return {"symbol": sym, "name": None, "href": GT.chart_href(sym, "5m"), "tf": "5m", "stats": [],
            "gajjala": {"setup": setup, "state": state, "trigger": 4.12, "stop": 3.95, "risk_pct": 4.1,
                        "state_label": "forming", "plan_text": "trigger 4.12", "chips": {"volume": 2e6},
                        "variant_label": None, "grade_label": None, "_last": 4.05}}


def block_of(syms, *, flags=frozenset(), setup=BF):
    tiles = [fake_tile(s, setup) for s in syms]
    reads = {s: {"symbol": s, "setups": {setup: {"setup": setup, "state": "forming"}}} for s in syms}
    return TBL.block({setup: tiles}, [], reads_by=reads, flags=flags, sess={"label": "today"}, in_window=True,
                     now=NOW, v=None, scan_row=lambda s: {}, cad_min=5)


def _walk_keys(o, path="$"):
    if isinstance(o, dict):
        for k, v in o.items():
            yield f"{path}.{k}", k
            yield from _walk_keys(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk_keys(v, f"{path}[{i}]")


def _strings(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            yield str(k)
            yield from _strings(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _strings(v)


# ── T1 ordering end to end ───────────────────────────────────────────────────────────────────────────────────────
def test_T1_rank_tiers_and_his_setup_order_end_to_end():
    t = table(store(t1_docs()))
    assert [(s, su, tr) for s, su, tr, _r in rows_of(t)] == T1_ORDER
    assert [r["rank"] for r in t["rows"]] == list(range(1, len(T1_ORDER) + 1))
    by = {r["symbol"]: r for r in t["rows"]}
    assert by["A1"]["state"] == "aplus" and by["K1"]["state"] == "triggered"          # aplus before triggered
    assert by["V1"]["kind"] == GC.POTENTIAL_KINDS[0] and by["S1"]["kind"] == GC.POTENTIAL_KINDS[1]   # armed › building
    tier3 = [r["setup"] for r in t["rows"] if r["tier"] == 3]
    assert tier3 == sorted(tier3, key=GC.TABLE_SETUP_ORDER.index)                       # his setup order
    assert [r["symbol"] for r in t["rows"] if r["setup"] == KF and r["tier"] == 3] == ["K3", "K2"]   # rel volume ↓
    assert by["H2"]["tier"] == 4 and by["H2"]["rank"] > max(r["rank"] for r in t["rows"] if r["tier"] == 3)
    assert t["n"] == len(T1_ORDER) and t["more_n"] == 0 and t["more_text"] is None and t["faults_n"] == 0


def test_T1_NEGATIVE_tiers_never_decrease_and_the_board_serves_no_cards():
    out = board(store(t1_docs()))
    tiers = [r["tier"] for r in out["table"]["rows"]]
    assert tiers == sorted(tiers)
    assert out["tiles"] == [] and "focus" not in out and "order_note" not in out and "potential" not in out
    assert out["sub"] == GC.TABLE_SUB and out["sub_resolved_from"] == "param" and out["empty_note"] is None


# ── T2 ONE engine ────────────────────────────────────────────────────────────────────────────────────────────────
def test_T2_each_setups_rows_keep_their_own_subs_served_order():
    st = store(t1_docs())
    t = table(st)
    for setup in GC.SETUPS:
        sub_order = [x["symbol"] for x in board(st, setup)["tiles"]]
        for tier in (3, 4):
            mine = [r["symbol"] for r in t["rows"] if r["setup"] == setup and r["tier"] == tier]
            assert mine == [s for s in sub_order if s in mine], (setup, tier)
        assert sorted(r["symbol"] for r in t["rows"] if r["setup"] == setup) == sorted(sub_order), setup


# ── T3 🚫 ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_T3_his_names_sit_last_in_their_tier_count_unchanged():
    t = table(flag(store(t1_docs()), "A1", "K3"))
    got = [(s, tr) for s, _su, tr, _r in rows_of(t)]
    assert got[:2] == [("K1", 1), ("A1", 1)]
    assert [s for s, tr in got if tr == 3] == ["K2", "H1", "B2", "K3"]
    assert len(got) == len(T1_ORDER) and [r["rank"] for r in t["rows"]] == list(range(1, len(T1_ORDER) + 1))


def test_T3_NEGATIVE_no_list_keeps_the_order_and_owner_minus_tags_equals_non_owner():
    plain = table(store(t1_docs()))
    assert [(s, su, tr) for s, su, tr, _r in rows_of(plain)] == T1_ORDER
    own = board(flag(store(t1_docs()), "A1"), owner=True)["table"]
    other = board(flag(store(t1_docs()), "A1"), owner=False)["table"]
    assert {r["symbol"]: r["broker_text"] for r in own["rows"]}["A1"] == GT.BROKER_FLAG_TEXT
    assert all(r["broker_text"] is None for r in other["rows"])
    strip = lambda tb: [{k: v for k, v in r.items() if k != "broker_text"} for r in tb["rows"]]   # noqa: E731
    assert strip(own) == strip(other)                                                # the order follows every viewer


# ── T4 GG's 18 ───────────────────────────────────────────────────────────────────────────────────────────────────
def _twenty():
    syms = [f"N{i:02d}" for i in range(20)]
    docs = [read_doc(s, {BF: R(BF, "forming", base={"bars": 0})}) for s in syms]
    docs[0]["setups"][KF] = R(KF, "forming", base={"bars": 0})                      # N00 on two setups
    scans = [scan(s, volume=1e7 - i * 1e5) for i, s in enumerate(syms)]
    return store(docs, scans=scans)


def test_T4_the_first_18_distinct_names_are_in_watch():
    t = table(_twenty())
    assert len(t["rows"]) == 21
    distinct = list(dict.fromkeys(r["symbol"] for r in t["rows"]))
    first18 = set(distinct[:GC.GG_WATCH_N])
    assert all(r["in_watch"] == (r["symbol"] in first18) for r in t["rows"])
    assert sum(r["in_watch"] for r in t["rows"]) == 19 == t["watch"]["rows"]
    assert t["watch"]["n"] == GC.GG_WATCH_N == 18
    assert "GG's 18" in t["watch"]["text"] and "(19 rows;" in t["watch"]["text"]
    assert [r["in_watch"] for r in t["rows"]][-2:] == [False, False]


def test_T4_NEGATIVE_five_names_are_all_in_watch():
    docs = [read_doc(f"F{i}", {BF: R(BF, "forming", base={"bars": 0})}) for i in range(5)]
    t = table(store(docs))
    assert all(r["in_watch"] for r in t["rows"]) and t["watch"]["rows"] == 5


# ── T5 the cap (C3) ──────────────────────────────────────────────────────────────────────────────────────────────
def test_T5_cap_serves_tile_limit_max_and_says_how_many_more():
    syms = [f"C{i:03d}" for i in range(GC.TILE_LIMIT_MAX + 3)]
    b = block_of(syms)
    assert len(b["rows"]) == GC.TILE_LIMIT_MAX and b["n"] == len(syms) and b["more_n"] == 3
    assert b["more_text"] == TBL.MORE_TEXT.format(n=3, cap=GC.TILE_LIMIT_MAX)


def test_T5_NEGATIVE_C3_a_flagged_name_inside_the_cut_is_never_pushed_past_it():
    syms = [f"C{i:03d}" for i in range(GC.TILE_LIMIT_MAX + 1)]                       # 81 rows
    flagged = syms[GC.TILE_LIMIT_MAX - 1]                                            # un-partitioned rank 80
    b = block_of(syms, flags=frozenset({flagged}))
    served = [r["symbol"] for r in b["rows"]]
    assert flagged in served and served[-1] == flagged                              # last in its tier, still served
    assert syms[GC.TILE_LIMIT_MAX] not in served                                    # the rank-81 row is the one cut
    assert set(served) == set(r["symbol"] for r in block_of(syms)["rows"])          # same set as without the list
    mid = syms[40]
    b2 = block_of(syms, flags=frozenset({mid}))
    assert mid in [r["symbol"] for r in b2["rows"]] and b2["rows"][-1]["symbol"] == mid


def test_T5_NEGATIVE_route_limit_never_cuts_the_table(monkeypatch):
    body = _get(monkeypatch, store(t1_docs()), limit=1)
    assert len(body["table"]["rows"]) == len(T1_ORDER)


# ── T6 NaN ───────────────────────────────────────────────────────────────────────────────────────────────────────
def test_T6_nan_never_reaches_the_json():
    doc = read_doc("NAN", {BF: R(BF, "aplus", broke=True, entry_bar_t="2026-10-13 10:25", risk_pct=float("nan"))})
    doc["tile"]["bars5"][3]["c"] = float("nan")
    t = table(store([doc], scans=[scan_doc("NAN", change=float("nan"))]))
    json.dumps(t, allow_nan=False)
    r = t["rows"][0]
    assert r["change_text"] is None and r["change_pct"] is None and r["risk_pct"] is None
    assert r["spark"]["n_bars"] == 11                                               # the NaN bar dropped


# ── T7 empty ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_T7_empty_serves_the_open_words_and_the_watch_block():
    t = table(store([]))
    assert t["rows"] == [] and t["n"] == 0 and t["watch"]["rows"] == 0
    assert t["empty_text"] == TBL.EMPTY_TEXT_OPEN.format(mins="5 minutes")


def test_T7_NEGATIVE_closed_wording_by_in_window():
    b = TBL.block({}, [], reads_by={}, flags=None, sess={"label": "Fri Nov 13"}, in_window=False, now=NOW,
                  scan_row=lambda s: {}, cad_min=5)
    assert b["empty_text"] == "No card on any of his five setups on the Fri Nov 13 list."
    assert block_of(["X1"])["empty_text"] is None


# ── T8 faults ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_T8_one_raising_row_is_skipped_and_counted(monkeypatch):
    real = TBL.row_of

    def row_of(tile, **kw):
        if tile.get("symbol") == "K2":
            raise RuntimeError("boom")
        return real(tile, **kw)
    monkeypatch.setattr(TBL, "row_of", row_of)
    t = table(store(t1_docs()))
    assert "K2" not in [r["symbol"] for r in t["rows"]] and len(t["rows"]) == len(T1_ORDER) - 1
    assert t["faults_n"] == 1 and t["fault_text"] == TBL.FAULT_TEXT.format(n=1)
    assert [r["rank"] for r in t["rows"]] == list(range(1, len(T1_ORDER)))


def test_T8_NEGATIVE_a_raising_block_serves_the_fault_sentence(monkeypatch):
    monkeypatch.setattr(TBL, "block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = board(store(t1_docs()))
    assert out["table"] is None and out["empty_note"] == GT.TABLE_FAULT_TEXT
    assert out["subs"][0]["key"] == GC.TABLE_SUB                                    # the strip still serves


# ── T9 GG5 only ──────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("variant", [V.GG1, V.GGA], ids=["gg1", "gga"])
def test_T9_other_pages_fail_open_and_never_list_it(variant):
    out = board(store(t1_docs()), variant=variant)
    assert out["sub"] == GC.DEFAULT_SUB and out["sub_resolved_from"] == "default"
    assert "table" not in out and GC.TABLE_SUB not in [s["key"] for s in out["subs"]]
    assert len(out["subs"]) == len(GC.SUBS) - 1
    for sub in (BF, GC.POTENTIAL_SUB):
        assert GC.TABLE_SUB not in [s["key"] for s in board(store(t1_docs()), sub, variant=variant)["subs"]]


def test_T9_NEGATIVE_gg5_serves_it_first_with_the_card_count():
    out = board(store(t1_docs()))
    first = out["subs"][0]
    assert first["key"] == GC.TABLE_SUB and first["emoji"] == "📋" and first["title"] is None
    counts = {s["key"]: s["count"] for s in out["subs"]}
    assert first["count"] == sum(counts[s] for s in GC.SETUPS) == len(T1_ORDER)
    assert board(store(t1_docs()), BF)["subs"][0]["count"] == len(T1_ORDER)        # every sub serves the same chip
    assert "table" not in board(store(t1_docs()), BF)                               # NEGATIVE: only on its own sub


# ── T10 no fetch · T14 live ──────────────────────────────────────────────────────────────────────────────────────
def _get(monkeypatch, st, live=None, **kw):
    from chart_maps import api as API
    from chart_maps import board as board_mod
    monkeypatch.setattr(ST, "default", lambda: st)
    monkeypatch.setattr(GT, "_clock", lambda: NOW)
    monkeypatch.setattr(board_mod, "_live_snapshot", live or (lambda tiles: {}))
    monkeypatch.setattr(board_mod, "attach_live_now", lambda tiles, out, live=None: None)
    kw.setdefault("sub", GC.TABLE_SUB)
    for k in ("tf", "focus", "sort", "span"):
        kw.setdefault(k, "")
    kw.setdefault("limit", GC.TILE_LIMIT_DEFAULT)
    return json.loads(run_route(API.chart_maps_gajjala(**kw)).body)


def test_T10_the_route_never_scans_or_fetches_on_the_table(monkeypatch):
    from chart_maps.gajjala import bars as BARS
    from chart_maps.gajjala import scanner as SC
    from sepa import prices

    def boom(*a, **k):
        raise AssertionError("the table must not scan or fetch")
    for mod, name in ((SC, "scan_rows"), (BARS, "frames_for"), (prices, "market_snapshot")):
        if hasattr(mod, name):
            monkeypatch.setattr(mod, name, boom)
    body = _get(monkeypatch, store(t1_docs()))
    assert body["sub"] == GC.TABLE_SUB and len(body["table"]["rows"]) == len(T1_ORDER)


def test_T14_the_live_print_rides_its_row_only(monkeypatch):
    seen = {}

    def live(rows):
        seen["syms"] = sorted(r["symbol"] for r in rows)
        return {"A1": {"last_trade_price": 4.2, "price": 4.1}}
    body = _get(monkeypatch, store(t1_docs()), live=live)
    by = {r["symbol"]: r for r in body["table"]["rows"]}
    assert seen["syms"] == sorted(s for s, _su, _t in T1_ORDER)
    assert by["A1"]["live_price"] == 4.2 and by["A1"]["live_price_text"] == "4.20"
    assert all("live_price" not in r for s, r in by.items() if s != "A1")


def test_T14_NEGATIVE_a_raising_snapshot_leaves_the_rows(monkeypatch):
    def live(rows):
        raise RuntimeError("tape down")
    body = _get(monkeypatch, store(t1_docs()), live=live)
    assert [r["symbol"] for r in body["table"]["rows"]] == [s for s, _su, _t in T1_ORDER]
    assert all("live_price" not in r for r in body["table"]["rows"])


def test_T14_attach_live_ignores_a_zero_print():
    rows = [{"symbol": "A1"}, {"symbol": "B1"}]
    TBL.attach_live(rows, {"A1": {"last_trade_price": 0, "price": 0}, "B1": None})
    assert rows == [{"symbol": "A1"}, {"symbol": "B1"}]
    TBL.attach_live(None, None)                                                     # never raises


# ── T11 private keys ─────────────────────────────────────────────────────────────────────────────────────────────
def test_T11_no_private_key_and_no_bars_or_curves_on_a_row():
    t = table(store(t1_docs()))
    assert not [p for p, k in _walk_keys(t) if k.startswith("_")]
    for r in t["rows"]:
        assert "bars" not in r and "curves" not in r and "gajjala" not in r and "lines" not in r
        assert set(TP.LITE_KEYS) == set(r["spark"])


# ── T12 the spark (C2, C4) ───────────────────────────────────────────────────────────────────────────────────────
def test_T12_spark_is_todays_frame_strided_with_the_et_parse():
    t = table(store(t1_docs()))
    r = next(x for x in t["rows"] if x["symbol"] == "A1")
    sp = r["spark"]
    first_ms = int(datetime(2026, 10, 13, 13, 35, tzinfo=timezone.utc).timestamp() * 1000)   # 09:35 ET (EDT)
    full = [{"t": first_ms + i * 300_000, "c": 4.05, "s": "rth"} for i in range(12)]
    assert sp["bars"] == [b for i, b in enumerate(full) if i % 3 == 0] + [full[-1]]
    assert sp["bars"][0]["t"] == first_ms and sp["n_bars"] == 12
    assert sp["id"] == "A1|bull_flag" and sp["ticker"] == "A1" and sp["lite"] is True
    assert sp["tf"] == TP._w("tf", n=5) and sp["aria"] == TP._w("aria", sym="A1", n=5) and sp["note"] is None
    assert sp["title"] == f"{r['category_text']} · {r['state_label']}"


def test_T12_C2_all_three_session_words():
    doc = read_doc("SES", {BF: R(BF, "forming", base={"bars": 0})})
    b = bars(3)
    b[0]["s"], b[2]["s"] = "pre", "ah"
    doc["tile"]["bars5"] = b
    assert [x["s"] for x in TBL.spark_bars(doc, "5m")] == ["premarket", "rth", "afterhours"]
    assert TBL.SPARK_SESSION == {"pre": "premarket", "ah": "afterhours"} and TBL.SPARK_RTH == "rth"


def test_T12_C4_NEGATIVE_the_squeeze_spark_never_carries_the_prior_session():
    doc = read_doc("SQZ", {RS: R(RS, "forming", base={"bars": 0})})
    doc["tile"]["bars5_prior"] = bars(4, day=PREV)
    st = store([doc])
    card = board(st, RS)["tiles"][0]
    assert card["bars"][0]["t"].startswith(PREV.isoformat())                        # the card keeps its wide frame
    sp = table(st)["rows"][0]["spark"]
    days = {datetime.fromtimestamp(b["t"] / 1000, tz=TBL.ET).date() for b in sp["bars"]}
    assert days == {S} and sp["n_bars"] == 12


def test_T12_rules_only_on_a_break_and_the_tone_vs_the_trigger():
    t = table(store(t1_docs()))
    by = {r["symbol"]: r["spark"] for r in t["rows"]}
    a = by["A1"]["rules"]
    assert len(a) == 1 and a[0]["key"] == "alert" and a[0]["at"] == "2026-10-13T10:05:00-04:00"
    assert a[0]["label"] == TP._w("alert", hhmm="10:05")
    assert len(by["K1"]["rules"]) == 1                                              # triggered = the same break
    for s in ("V1", "S1", "K2", "K3", "H1", "H2", "B2", "S2"):
        assert by[s]["rules"] == [], s                                              # NEGATIVE: no break, no rule
    assert by["A1"]["tone"] == "dn"                                                 # 4.05 < 4.12
    doc = read_doc("UP", {BF: R(BF, "forming", base={"bars": 0}, trigger=4.0)})
    no = read_doc("NOT", {BF: R(BF, "forming", base={"bars": 0}, trigger=None)})
    tb = {r["symbol"]: r["spark"]["tone"] for r in table(store([doc, no]))["rows"]}
    assert tb == {"UP": "up", "NOT": None}


def test_T12_NEGATIVE_no_bars_serves_an_empty_spark():
    doc = read_doc("NOB", {BF: R(BF, "forming", base={"bars": 0})})
    doc["tile"]["bars5"], doc["tile"]["bars15"] = [], []
    sp = table(store([doc]))["rows"][0]["spark"]
    assert sp["bars"] == [] and sp["n_bars"] == 0 and sp["tone"] is None


# ── T13 words (C7) ───────────────────────────────────────────────────────────────────────────────────────────────
def test_T13_category_tier_and_head_words():
    t = table(store(t1_docs()))
    assert t["heads"] == [{"key": k, "label": lb} for k, lb in TBL.HEADS]
    assert t["title"] == TBL.TITLE and t["order_text"] == TBL.ORDER_TEXT and t["honesty"] == TBL.HONESTY
    assert t["tape_head"] == TP.TAPE_HEAD
    for r in t["rows"]:
        e, label = GT.SUB_META[r["setup"]]
        assert r["category_text"] == f"{e} {label} · {r['state_word']}"
        assert r["tier_label"] == TBL.TIER_WORDS[r["tier_key"]] and r["tier"] == TBL.TIERS.index(r["tier_key"]) + 1
        assert r["href"] == GT.chart_href(r["symbol"], r["tf"]) and r["card_href"] == PT.deep_link(r["symbol"], r["setup"])
    by = {r["symbol"]: r for r in t["rows"]}
    assert by["H1"]["tf"] == "5m"                                                   # its read's frame first
    assert by["A1"]["plan_text"] == GT.plan_text(R(BF, "aplus")) and by["A1"]["entry_plan"] is True
    assert by["A1"]["price_text"] == "4.05" and by["A1"]["dist_text"] == "+1.7%" and by["A1"]["volume_text"] == "2.0M"
    assert by["K3"]["rvol_text"] == "5.00× so far — the session is not over" and by["A1"]["rvol_text"] is None


def test_T13_C7_a_long_flag_and_a_b_grade_print_their_own_label():
    lf = R(BF, "forming", base={"bars": 2}, variant="long_flag")
    vb = R(VC, "partial", grade=GC.VCP_B_GRADE, missed=["k2"])
    t = table(store([read_doc("LF", {BF: lf}), read_doc("VB", {VC: vb})]))
    by = {r["symbol"]: r for r in t["rows"]}
    assert by["LF"]["state_word"] == GT.variant_label(lf) and by["LF"]["tier"] == 3 and by["LF"]["kind"] is None
    assert by["VB"]["state_word"] == GT.grade_label(vb)
    assert by["LF"]["state_word"] != PT.FORMING_NOT_POTENTIAL


def test_T13_NEGATIVE_a_plain_base_zero_forming_read_keeps_the_potential_engines_word():
    t = table(store([read_doc("PL", {BF: R(BF, "forming", base={"bars": 0})})]))
    assert t["rows"][0]["state_word"] == PT.FORMING_NOT_POTENTIAL


def test_T13_NEGATIVE_no_banned_word_anywhere():
    out = board(store(t1_docs()))
    assert not [s for s in _strings(out["table"]) if B_WORD.search(s)]
    for w in (TBL.TITLE, TBL.ORDER_TEXT, TBL.WATCH_TEXT, TBL.HONESTY, *TBL.TIER_WORDS.values()):
        assert not B_WORD.search(w)


def test_tier_of_truth_table():
    assert TBL.tier_of({"state": "aplus"}, False) == "aplus" == TBL.tier_of({"state": "triggered"}, True)
    assert TBL.tier_of({"state": "forming"}, True) == "potential"
    assert TBL.tier_of({"state": "forming"}, False) == "forming"
    for st in ("partial", "stopped", None):
        assert TBL.tier_of({"state": st}, False) == "rest"                          # NEGATIVE


# ── T15 marks ────────────────────────────────────────────────────────────────────────────────────────────────────
def _marks_store(**kw):
    docs = [read_doc("NEW", {BF: R(BF, "aplus", broke=True, entry_bar_t="2026-10-13 10:30")}),
            read_doc("ARM", {BF: R(BF, "forming", ready=True, base={"bars": 2})})]
    step = {"at": utc(10, 21).isoformat(), "at_et": "10:21", "state": "forming", "kind": "armed", "bar_t": None}
    trk = {"_id": ST.potential_key(S, "ARM", BF), "date": S.isoformat(), "symbol": "ARM", "setup": BF,
           "first_seen": OLD, "first_seen_et": GT._hhmm(OLD), "first_seen_mode": "normal", "state_path": [step]}
    return store(docs, trackers=[trk], **kw)


def test_T15_a_fresh_aplus_row_carries_its_mark():
    t = table(_marks_store())
    by = {r["symbol"]: r for r in t["rows"]}
    assert by["NEW"]["new_mark"]["kind"] == "aplus"


def test_T15_a_brain_row_takes_the_potential_mark_when_the_setup_has_none(monkeypatch):
    monkeypatch.setattr(EM, "mark_of", lambda *a, **k: None)
    by = {r["symbol"]: r for r in table(_marks_store())["rows"]}
    assert by["ARM"]["new_mark"]["kind"] == "armed" and "new_mark" not in by["NEW"]


def test_T15_NEGATIVE_a_broker_name_gets_no_mark_and_the_chips_do_not_move():
    by = {r["symbol"]: r for r in table(flag(_marks_store(), "NEW"))["rows"]}
    assert "new_mark" not in by["NEW"]
    assert board(_marks_store())["entry_marks"] == board(_marks_store(), BF)["entry_marks"]


# ── T16 tags ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_T16_trader_and_promo_tags_ride_the_rows(monkeypatch):
    monkeypatch.setattr(TN, "tag_map", lambda docs: {"A1": {"trader_text": "📌 algo888"}})
    monkeypatch.setattr(PN, "tag_map", lambda docs: {"A1": {"promo_text": "🎪 promo circuit"}})
    by = {r["symbol"]: r for r in table(store(t1_docs()))["rows"]}
    assert by["A1"]["trader_text"] == "📌 algo888" and by["A1"]["promo_text"] == "🎪 promo circuit"
    assert by["K1"]["trader_text"] is None and "promo_text" not in by["K1"]        # NEGATIVE: untagged rows
