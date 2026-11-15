"""🔀 The 9/21 EMA blinker on the Gajjala cards (🚩 GG5 / 1-minute / 🧪) — SPEC blinker §3.4, WP-B (2026-11-15).

Ajay, verbatim: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9 crossing over 21
EMA please.." · FRAME "Each chart's own frame" · "Yes and I need some sort of urgency or fast blink for the one are
closer together than approaching with sort also aligned with it" · "Or atleast closing in on other tabs for me".

Pinned (§4 WP-B (a)–(i)):
(a) every card — the five setups, a 🧠 card, a ☀️ row with bars — serves `ema_blink` off its DRAWN frame (the 15m
    toggle reads the 15m curves; the 🎾 wide frame's `t` is today's last bar and a prior-tail cross prints its date);
(b) no bars → `ema_blink: None`;
(c) `?sort=ema_blink` orders by ema_blink.sort_key BEFORE the cut; NEGATIVES: the default order is byte-identical for
    "", "default", "volume", "junk"; the non-blinking cards keep their default relative order under the blink sort;
(d) `sorts` / `sort` / `ema_blink_info` on the five setup subs and 🧠; NEGATIVE: ☀️ keeps SORTS_PM, 🌙 / 📓 / 🏁 / 📋
    serve no blink chips and no info;
(e) `order_note` = ema_blink.order_text() only under the blink sort;
(f) broker_bottom still runs after the blink sort (a 🚫 closing-in name sits last);
(g) the 1-minute and 🧪 builds carry the same keys;
(h) _strip_private leaves `ema_blink`; the payload is NaN-free;
(i) the golden drift pin passes after the BOARD regens (run by the suite, tests/test_gajjala_day_read_wiring_2026_11_15).
Information only — no gate, push, A+ rule or default order reads the block. UNMEASURED.
"""
from __future__ import annotations

import copy
import json

import pytest

from chart_maps import ema_blink as EB
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from tests import test_gajjala_potential_tab as PTT
from tests.test_gajjala_broker_flags import flag
from tests.test_gajjala_fade_ema_rank_2026_11_08 import GGA_OWN
from tests.test_gajjala_store import FakeColl
from tests.test_gajjala_tab import NOW, R, S, PREV, bars, latest, read_doc, scan_doc, store_with

BF, KF, HF, VCP, RS = "bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp", "reversal_squeeze"
FORMING = dict(base={"bars": 0}, reason="waiting")
N = 12                                                               # tests.test_gajjala_tab.bars() default length

# 12-bar 9 / 21 EMA pairs (the slow side flat at 2.0) — one per blinker state
SLOW = [2.0] * N
FLAT = [1.0] * N                                                     # under and not narrowing → none
IMMINENT = [1.0] * 8 + [1.0, 1.3, 1.6, 1.8]                          # gap −1.0 → −0.2 over 3 bars → the next bar
NEAR = [1.0] * 8 + [0.5, 0.9, 1.2, 1.5]                              # gap −1.5 → −0.5 over 3 bars → 2 bars
FRESH = [1.0] * (N - 1) + [3.0]                                      # crossed over on the last bar
UP = [1.0] * 6 + [3.0] * 6                                           # crossed 5 bars ago, still over


def curves(f9, f21=None):
    return [{"tone": "ema9", "label": "9 EMA", "values": list(f9)},
            {"tone": "ema21", "label": "21 EMA", "values": list(f21 if f21 is not None else SLOW)}]


def tile_of(f9, *, f15=None, f1=None):
    b5, b15 = bars(N), bars(4, base=5.0)
    t = {"bars5": b5, "curves5": curves(f9), "vol_avg5": None,
         "bars15": b15, "curves15": curves(f15 or [1.0] * 4, [2.0] * 4), "vol_avg15": None}
    if f1 is not None:
        t.update({"bars1": bars(N), "curves1": curves(f1), "vol_avg1": None})
    return t


def doc_of(sym, setups, f9, **kw):
    return read_doc(sym, setups, tile=tile_of(f9, **kw))


def card(doc, setup, tf="5m", v=None):
    return GT.setup_tile(doc, setup, tf, scan_row={}, sess={}, listed=None, v=v)


def drawn_block(doc, setup, tf, v=None):
    fr = GT._tile_frame(doc, tf, V.of(v), wide=setup == RS)
    return EB.block_from_curves(fr["curves"], fr["bars"], tf=fr["tf"])


def syms(out):
    return [t["symbol"] for t in out["tiles"]]


def board_store(docs, vols, v=None):
    scans = [scan_doc(d["symbol"], volume=vols.get(d["symbol"], 2e6)) for d in docs]
    shared = store_with(reads=docs, scans=scans, passes=[latest()])
    if v is V.GG1:
        own = {n: FakeColl() for n in ST.OWN}
        own[ST.READS] = FakeColl(copy.deepcopy(docs))
        own[ST.PASSES] = FakeColl([latest()])
        return ST.GajjalaStore(colls=own, variant=V.GG1, shared=shared)
    if v is V.GGA:
        return ST.GajjalaStore(colls={n: FakeColl() for n in GGA_OWN}, variant=V.GGA, shared=shared)
    return shared


def ladder(n=25, blinkers=None, setup=BF):
    """`n` forming cards on `setup`, volume strictly descending A00 → A{n-1} (the default order), FLAT curves except
    `blinkers` = {index: f9}."""
    blinkers = blinkers or {}
    docs, vols = [], {}
    for k in range(n):
        sym = f"A{k:02d}"
        docs.append(doc_of(sym, {setup: R(setup, "forming", **FORMING)}, blinkers.get(k, FLAT),
                           f1=blinkers.get(k, FLAT)))
        vols[sym] = 9e6 - k * 1e5
    return docs, vols


def build(sub, st, **kw):
    return GT.build(sub, now=NOW, store=st, **kw)


# ── (a) every card carries the block of its DRAWN frame ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_every_setup_card_serves_the_block_of_its_drawn_frame(setup):
    doc = doc_of("OMH", {setup: R(setup, "forming", **FORMING)}, IMMINENT)
    t = card(doc, setup)
    assert "ema_blink" in t
    assert t["ema_blink"] == drawn_block(doc, setup, "5m") and t["ema_blink"] is not None
    assert t["ema_blink"]["tf"] == t["tf"] == "5m"
    assert t["ema_blink"]["state"] == "closing_in" and t["ema_blink"]["blink"] is True
    assert t["ema_blink"]["t"] == t["bars"][-1]["t"]                  # the latest drawn (closed) bar


def test_the_fifteen_minute_toggle_reads_the_fifteen_minute_curves():
    doc = doc_of("OMH", {HF: R(HF, "forming", **FORMING)}, FLAT, f15=[1.0, 1.0, 1.0, 3.0])
    t5, t15 = card(doc, HF, "5m"), card(doc, HF, "15m")
    assert t15["tf"] == "15m" and t15["ema_blink"]["tf"] == "15m"
    assert t15["ema_blink"]["state"] == "crossed_up" and t15["ema_blink"]["tier"] == "fresh"
    assert t15["ema_blink"] == EB.block_from_curves(doc["tile"]["curves15"], doc["tile"]["bars15"], tf="15m")
    assert t5["ema_blink"]["state"] == "none" and t5["ema_blink"]["blink"] is False   # NEGATIVE: never the other frame


def test_the_squeeze_wide_frame_reads_today_last_bar_and_dates_a_prior_tail_cross():
    prior = [{"t": f"{PREV.isoformat()} 15:{30 + 5 * k:02d}", "o": 4, "h": 4.1, "l": 3.9, "c": 4.0, "v": 900}
             for k in range(6)]
    doc = doc_of("SQZ", {RS: R(RS, "forming", **FORMING)}, [3.0] * N)
    doc["tile"].update({"bars5_prior": prior, "curves5_prior": curves([1.0, 1.0, 1.0, 3.0, 3.0, 3.0], [2.0] * 6)})
    t = card(doc, RS)
    b = t["ema_blink"]
    assert len(t["bars"]) == 6 + N                                   # the wide frame is the drawn one
    assert b == drawn_block(doc, RS, "5m")
    assert b["t"] == doc["tile"]["bars5"][-1]["t"] and b["t"].startswith(S.isoformat())
    assert b["state"] == "crossed_up" and b["tier"] == "up" and b["bars_since_cross"] == 2 + N
    assert b["cross_t"] == f"{PREV.isoformat()} 15:45"
    assert f"{PREV.isoformat()} 15:45 ET" in b["text"]               # [C7] the prior session's cross keeps its date


def test_a_premarket_row_with_bars_serves_the_block_and_without_a_doc_none():
    doc = doc_of("PMX", {}, FRESH)
    extra = {"state_label": "x"}
    row = GT._list_tile("PMX", "premarket", doc, "5m", scan_row={}, sess={}, listed=None, extra=dict(extra))
    assert row["ema_blink"] == drawn_block(doc, "premarket", "5m")
    assert row["ema_blink"]["state"] == "crossed_up" and row["ema_blink"]["tier"] == "fresh"
    none = GT._list_tile("NODOC", "premarket", None, "5m", scan_row={}, sess={}, listed=None, extra=dict(extra))
    assert "ema_blink" in none and none["ema_blink"] is None         # NEGATIVE (b): no bars → None


# ── (b) no bars → None ─────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("setup", GC.SETUPS)
def test_NEGATIVE_a_card_with_no_bars_serves_none(setup):
    doc = read_doc("NOB", {setup: R(setup, "forming", **FORMING)}, tile={})
    t = card(doc, setup)
    assert t["bars"] == [] and "ema_blink" in t and t["ema_blink"] is None


def test_NEGATIVE_a_raising_engine_serves_none_and_the_card_stands(monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("engine down")
    monkeypatch.setattr(EB, "block_from_curves", boom)
    t = card(doc_of("OMH", {BF: R(BF, "forming", **FORMING)}, IMMINENT), BF)
    assert t["ema_blink"] is None and t["bars"] and t["gajjala"]["state"] == "forming"


def test_NEGATIVE_the_block_is_information_only_order_key_ignores_it():
    a = card(doc_of("OMH", {BF: R(BF, "forming", **FORMING)}, FRESH), BF)
    b = card(doc_of("OMH", {BF: R(BF, "forming", **FORMING)}, FLAT), BF)
    assert a["ema_blink"]["blink"] is True and b["ema_blink"]["blink"] is False
    assert GT.order_key(a) == GT.order_key(b)


# ── (c) the opt-in sort, BEFORE the cut, stable ────────────────────────────────────────────────────────────────────
def test_the_blink_sort_shows_a_closing_in_card_past_the_cut():
    docs, vols = ladder(25, {24: IMMINENT, 3: NEAR, 10: FRESH, 7: UP})
    st = board_store(docs, vols)
    default = build(BF, st)
    assert len(default["tiles"]) == GC.TILE_LIMIT_DEFAULT == 24
    assert "A24" not in syms(default)                                # the default cut hides the 25th card
    out = build(BF, st, sort=GC.BLINK_SORT_KEY)
    assert syms(out)[:4] == ["A10", "A24", "A03", "A07"]             # fresh → imminent → near → up
    assert len(out["tiles"]) == 24 and "A24" in syms(out)
    full = build(BF, st, limit=GC.TILE_LIMIT_MAX)
    want = sorted(full["tiles"], key=EB.sort_key)[:24]               # THE ordering over the whole default list
    assert syms(out) == [t["symbol"] for t in want]


def test_NEGATIVE_the_non_blinking_tail_keeps_the_default_relative_order():
    docs, vols = ladder(25, {24: IMMINENT, 3: NEAR, 10: FRESH, 7: UP})
    st = board_store(docs, vols)
    full = syms(build(BF, st, limit=GC.TILE_LIMIT_MAX))
    out = build(BF, st, sort=GC.BLINK_SORT_KEY, limit=GC.TILE_LIMIT_MAX)
    blinking = {t["symbol"] for t in out["tiles"] if (t["ema_blink"] or {}).get("blink")}
    assert blinking == {"A24", "A03", "A10", "A07"}
    assert [s for s in syms(out) if s not in blinking] == [s for s in full if s not in blinking]
    assert syms(out)[len(blinking):] == [s for s in full if s not in blinking]


def _dump(o):
    return json.dumps(o, sort_keys=True, ensure_ascii=False, allow_nan=False, default=str)


@pytest.mark.parametrize("sort", ["", "default", "volume", "junk", "change", None, 7])
def test_NEGATIVE_any_other_sort_value_serves_the_default_board_byte_for_byte(sort):
    docs, vols = ladder(25, {24: IMMINENT, 3: NEAR, 10: FRESH})
    st = board_store(docs, vols)
    base = build(BF, st)
    assert _dump(build(BF, st, sort=sort)) == _dump(base)
    assert base["sort"] == "default"


def test_the_sort_value_is_read_case_and_space_blind():
    docs, vols = ladder(5, {4: IMMINENT})
    st = board_store(docs, vols)
    assert build(BF, st, sort="  EMA_Blink ")["sort"] == GC.BLINK_SORT_KEY
    assert syms(build(BF, st, sort=" ema_blink"))[0] == "A04"


def test_the_potential_sub_sorts_before_the_cut():
    st = PTT.day_store()
    default = build(GC.POTENTIAL_SUB, st, limit=2)
    order = syms(build(GC.POTENTIAL_SUB, st))
    last = order[-1]
    for d in st.coll(ST.READS).docs.values():                        # every 🧠 card flat; the default LAST one imminent
        d["tile"]["curves5"] = curves(IMMINENT if d["symbol"] == last else FLAT)
    assert last not in syms(build(GC.POTENTIAL_SUB, st, limit=2))
    out = build(GC.POTENTIAL_SUB, st, limit=2, sort=GC.BLINK_SORT_KEY)
    assert syms(out)[0] == last and len(out["tiles"]) == 2
    assert out["tiles"][0]["ema_blink"]["tier"] == "imminent"
    assert syms(out)[1] == order[0]                                  # NEGATIVE: the tail keeps the 🧠 order
    assert out["sort"] == GC.BLINK_SORT_KEY and default["sort"] == "default"
    full = build(GC.POTENTIAL_SUB, st, sort=GC.BLINK_SORT_KEY)
    assert all("ema_blink" in t for t in full["tiles"])              # (a) every 🧠 card carries the key


def test_a_premarket_board_row_carries_the_block_and_the_blink_sort_never_reaches_it():
    st = PTT.day_store()
    for d in st.coll(ST.READS).docs.values():
        d["tile"]["curves5"] = curves(FRESH)
    pm = build("premarket", st)
    pm_blink = build("premarket", st, sort=GC.BLINK_SORT_KEY)
    assert pm["tiles"] and all("ema_blink" in t for t in pm["tiles"])
    with_bars = [t for t in pm["tiles"] if t["bars"]]
    assert with_bars and all(t["ema_blink"]["state"] == "crossed_up" for t in with_bars)
    assert all(t["ema_blink"] is None for t in pm["tiles"] if not t["bars"])
    assert syms(pm_blink) == syms(pm)                                # NEGATIVE: ☀️ never re-orders on the blink
    assert pm_blink["sort"] == GT.SORT_PM_DEFAULT


# ── (d) / (e) the served chips, sort, info and note ────────────────────────────────────────────────────────────────
def _setup_store():
    docs = [doc_of(f"S{k}", {s: R(s, "forming", **FORMING, cycles=2)}, IMMINENT if k == 1 else FLAT)
            for k, s in enumerate(GC.SETUPS)]
    docs += [doc_of(f"T{k}", {s: R(s, "forming", **FORMING, cycles=2)}, FRESH) for k, s in enumerate(GC.SETUPS)]
    return board_store(docs, {})


@pytest.mark.parametrize("sub", GC.SETUPS)
def test_the_five_setup_subs_serve_the_chips_sort_and_info_once(sub):
    st = _setup_store()
    out = build(sub, st)
    assert out["sorts"] == [{"key": "default", "label": EB.SORT_DEFAULT_LABEL},
                            {"key": GC.BLINK_SORT_KEY, "label": EB.sort_label()}]
    assert out["sort"] == "default" and out["ema_blink_info"] == EB.info()
    assert out["order_note"] != EB.order_text()                      # (e) NEGATIVE: the sub's own note by default
    blink = build(sub, st, sort=GC.BLINK_SORT_KEY)
    assert blink["sort"] == GC.BLINK_SORT_KEY and blink["order_note"] == EB.order_text()
    assert blink["sorts"] == out["sorts"] and blink["ema_blink_info"] == EB.info()
    text = _dump(blink)
    assert text.count(json.dumps(EB.info(), ensure_ascii=False)) == 1   # [C8] the long words ONCE per payload


def test_the_default_order_note_is_unchanged_per_sub():
    st = _setup_store()
    assert build(BF, st)["order_note"] == GT.VOL_ORDER_TEXT
    assert build(RS, st)["order_note"] == GT.RS_ORDER_TEXT
    assert build(HF, st)["order_note"] == GT.HF_ORDER_TEXT
    assert build(GC.POTENTIAL_SUB, PTT.day_store())["order_note"] == GT.POT_ORDER_TEXT


def test_the_potential_sub_serves_the_chips_and_its_note_only_under_the_blink():
    st = PTT.day_store()
    out = build(GC.POTENTIAL_SUB, st)
    assert out["sort"] == "default" and out["ema_blink_info"] == EB.info()
    assert [s["key"] for s in out["sorts"]] == ["default", GC.BLINK_SORT_KEY]
    assert build(GC.POTENTIAL_SUB, st, sort=GC.BLINK_SORT_KEY)["order_note"] == EB.order_text()


def test_NEGATIVE_premarket_keeps_its_own_sorts_and_no_info():
    st = PTT.day_store()
    for sort in ("", GC.BLINK_SORT_KEY):
        pm = build("premarket", st, sort=sort)
        assert [s["key"] for s in pm["sorts"]] == [k for k, _l in GT.SORTS_PM]
        assert GC.BLINK_SORT_KEY not in dict(GT.SORTS_PM) and pm["sort"] == GT.SORT_PM_DEFAULT
        assert "ema_blink_info" not in pm


@pytest.mark.parametrize("sub", ["postmarket", "playbook", GC.LEDGER_SUB, GC.TABLE_SUB])
def test_NEGATIVE_the_other_subs_serve_no_blink_chips_and_no_info(sub):
    st = _setup_store()
    for sort in ("", GC.BLINK_SORT_KEY):
        out = build(sub, st, sort=sort)
        assert out["sub"] == sub
        assert "sorts" not in out and "sort" not in out and "ema_blink_info" not in out
        assert out.get("order_note") != EB.order_text()


def test_NEGATIVE_the_table_is_untouched_by_the_blink_sort():
    st = _setup_store()
    a, b = build(GC.TABLE_SUB, st), build(GC.TABLE_SUB, st, sort=GC.BLINK_SORT_KEY)
    assert _dump(a) == _dump(b)
    assert "ema_blink" not in _dump(a["table"])                      # the table's rows carry their own keys only


# ── (f) his 🚫 names still last ────────────────────────────────────────────────────────────────────────────────────
def test_the_broker_partition_runs_after_the_blink_sort():
    docs, vols = ladder(6, {5: IMMINENT, 2: FRESH})
    st = flag(board_store(docs, vols), "A05")
    out = build(BF, st, sort=GC.BLINK_SORT_KEY, owner=True)
    assert syms(out)[-1] == "A05" and syms(out)[0] == "A02"          # the 🚫 imminent name sits LAST
    assert syms(build(BF, st, sort=GC.BLINK_SORT_KEY)) == syms(out)  # the ORDER follows his list for every viewer


# ── (g) the 1-minute page and 🧪 ───────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("v", [V.GG1, V.GGA])
def test_the_variant_builds_carry_the_same_keys(v):
    docs, vols = ladder(25, {24: IMMINENT, 3: NEAR})
    st = board_store(docs, vols, v=v)
    out = build(BF, st, variant=v)
    assert out["tab"] == v.tab and out["sort"] == "default" and out["ema_blink_info"] == EB.info()
    assert [s["key"] for s in out["sorts"]] == ["default", GC.BLINK_SORT_KEY]
    assert all("ema_blink" in t for t in out["tiles"])
    assert all(t["ema_blink"]["tf"] == t["tf"] and t["tf"] in v.tfs for t in out["tiles"])   # the DRAWN frame
    blink = build(BF, st, variant=v, sort=GC.BLINK_SORT_KEY)
    assert syms(blink)[:2] == ["A24", "A03"] and blink["order_note"] == EB.order_text()


# ── (h) public key, NaN-free ───────────────────────────────────────────────────────────────────────────────────────
def test_strip_private_leaves_the_block_and_the_payload_is_nan_free():
    docs, vols = ladder(6, {5: IMMINENT, 2: FRESH, 1: NEAR})
    out = build(BF, board_store(docs, vols), sort=GC.BLINK_SORT_KEY)
    tiles = copy.deepcopy(out["tiles"])
    GT._strip_private(tiles)
    assert [t["ema_blink"] for t in tiles] == [t["ema_blink"] for t in out["tiles"]]
    assert all(not str(k).startswith("_") for t in out["tiles"] for k in (t["ema_blink"] or {}))
    json.dumps(out, allow_nan=False, default=str)                    # raises on a NaN / inf
    assert GT.BLINK_SORT_DEFAULT == "default" and GT.is_blink_sort(GC.BLINK_SORT_KEY)
    assert not GT.is_blink_sort(None) and not GT.is_blink_sort("ema") and not GT.is_blink_sort(["ema_blink"])


def test_NEGATIVE_a_raising_sort_key_keeps_the_board_order(monkeypatch):
    docs, vols = ladder(6, {5: IMMINENT})
    st = board_store(docs, vols)
    base = syms(build(BF, st))

    def boom(_t):
        raise RuntimeError("key down")
    monkeypatch.setattr(EB, "sort_key", boom)
    assert syms(build(BF, st, sort=GC.BLINK_SORT_KEY)) == base


# ── (f2) the 🧠 cut-then-partition shape the pre-commit contract reads (contracts.mjs, 2026-11-09 critic) ──────────────
def test_the_potential_sub_keeps_the_contract_shape_cut_first_then_partition():
    import inspect
    import re
    src = inspect.getsource(GT.build)
    assert re.search(r"if pot_ok else \[\]\)\[:lim\], order_flags\)", src)       # the literal contracts.mjs reads
    assert re.search(r"pot_order = blink_sorted if blink_sort else list", src)     # 🔀 inside the cut, opt-in only
    assert len(re.findall(r"broker_bottom\(", src)) >= 4


def test_NEGATIVE_no_partition_before_the_limit_cut_anywhere_in_build():
    import inspect
    import re
    src = inspect.getsource(GT.build)
    assert not re.search(r"order_flags\)\[:lim\]", src)
    assert not re.search(r"tiles = broker_bottom\(tiles, order_flags\)", src)
    assert "pot_tiles" not in src                                                   # no separate sorted list to cut
