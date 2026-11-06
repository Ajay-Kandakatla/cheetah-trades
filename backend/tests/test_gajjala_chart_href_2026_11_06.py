"""🚩 The card's href carries his frame (spec gg-chart §3.1–§3.2, WP-A, 2026-11-06).

Ajay 2026-11-06, verbatim: "If I click on Gajjalas tab stocks show me "Gajjalas chart" in supply and demand of his view
by default mainly.. / Like if he looks at 24 hours or 2 week or anything else that is what I would like to see"

The served 🚩 tile href = the house ticker link (chart_maps.board._href, unchanged for every other board) + `&tf=<key>`,
the Support-tab frame KEY of the frame the card is DRAWN on, read off supply_demand.timeframes BY NAME
(GC.CHART_FRAME_KEY_CONST) in ONE helper, tab.chart_href. GG5 "5m" → 5m_today, "15m" → 15m, the 1-minute page "1m" →
1min. Never the bare "5m" (the Support tab's alias for 24h), never "1m" (its one-month window), never a `window=`.
The chart under his frame draws the house averages (9 EMA / 20 SMA / 200 SMA), not his 21 EMA — HIS CALL #7.
UNMEASURED — a link target, not a signal.
"""
from __future__ import annotations

import inspect
import json
import re
from pathlib import Path

import pytest

from chart_maps import board as board_mod
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import variant as V
from supply_demand import timeframes as TF
from tests.test_gajjala_1m_page_2026_10_27 import _clean, board, stores  # noqa: F401 — pytest fixtures
from tests.test_gajjala_audited_tab import gga_store
from tests.test_gajjala_tab import (BF, NOW, ROWS_AH, R, _pm_store, _post_store, bars, latest, ordering_store,
                                    read_doc, scan_doc, store_with, utc)

ROOT = Path(__file__).resolve().parents[2]
GOLDENS = (ROOT / "backend" / "tests" / "fixtures" / "gajjala" / "gg5_board_2026_10_27.json",
           ROOT / "frontend" / "src" / "components" / "__fixtures__" / "gajjala_on_open_golden_2026_10_15.json",
           ROOT / "frontend" / "src" / "components" / "__fixtures__" / "gajjala_potential_golden_2026_10_15.json",
           ROOT / "frontend" / "src" / "components" / "__fixtures__" / "gajjala_1m_board_2026_10_27.json")
SUB_KEYS = tuple(k for k, _e, _l in GC.SUBS)
SEPA_RE = re.compile(r"^/sepa/[A-Z.\-]+\?tab=supply&tf=(1min|5m_today|15m)$")
BARE_RE = re.compile(r"[?&]tf=(5m|1m|24h)(&|$)")
HF = "horizontal_fade"


def _hrefs(o):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "href" and isinstance(v, str):
                yield v
            else:
                yield from _hrefs(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from _hrefs(v)


def _tile(doc, setup, tf, v=None):
    return GT.setup_tile(doc, setup, tf, scan_row={}, sess={}, listed=None, v=v)


def _assert_clean_hrefs(payload, where):
    hs = list(_hrefs(payload))
    for h in hs:
        assert "window=" not in h, (where, h)
        assert not BARE_RE.search(h), (where, h)
        if h.startswith("/sepa/"):
            assert SEPA_RE.match(h), (where, h)
        if h.startswith("/chart-maps?"):
            assert "tf=" not in h, (where, h)                    # PT.deep_link rows / 👀 watch: untouched
    return hs


# ── the map ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_every_mapped_name_is_a_live_timeframes_key_whose_bars_are_the_frames_minutes():
    keys = {t["key"] for t in TF.TIMEFRAMES}
    assert set(GC.CHART_FRAME_KEY_CONST) == {t for v in V.VARIANTS for t in v.tfs}
    for v in V.VARIANTS:
        for frame in v.tfs:
            key = getattr(TF, GC.CHART_FRAME_KEY_CONST[frame])
            assert key in keys and key not in TF.RETIRED, (v.key, frame, key)
            assert TF.tf_spec(key)["bar_label"] == f"{V.frame_minutes(frame, v)}-minute", (v.key, frame, key)
    assert GC.CHART_TF_PARAM == "tf"


def test_the_map_resolves_to_the_three_keys_and_never_an_alias():
    got = {f: getattr(TF, n) for f, n in GC.CHART_FRAME_KEY_CONST.items()}
    assert got == {"1m": TF.M1_TODAY, "5m": TF.M5_TODAY, "15m": TF.M15} == {"1m": "1min", "5m": "5m_today",
                                                                            "15m": "15m"}
    # NEGATIVE: the bare frame words the alias table bends — "5m" is the 24-hour frame, "1m" is not a frame at all
    assert TF.parse_tf("5m") == TF.H24 != got["5m"]
    for v in got.values():
        assert TF.parse_tf(v) == v                               # the key parses to itself
        assert v not in ("5m", "1m", TF.H24)


def test_constants_import_nothing_from_supply_demand_and_carry_no_gg_tag():
    src = Path(GC.__file__).read_text(encoding="utf-8")
    imports = [ln for ln in src.splitlines() if ln.startswith(("from ", "import "))]
    assert imports and not any("supply_demand" in ln for ln in imports), imports
    for ln in src.splitlines():
        if ln.startswith(("CHART_FRAME_KEY_CONST", "CHART_TF_PARAM")):
            assert not re.search(r"#\s*GG ", ln), ln            # not a Playbook-linked GG constant


# ── the helper ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_chart_href_is_the_house_link_plus_the_frame_key():
    assert GT.chart_href("bbb", "5m") == board_mod._href("BBB") + "&tf=" + TF.M5_TODAY == "/sepa/BBB?tab=supply&tf=5m_today"
    assert GT.chart_href("BBB", "15m") == "/sepa/BBB?tab=supply&tf=15m"
    assert GT.chart_href("BBB", "1m", V.GG1) == "/sepa/BBB?tab=supply&tf=1min"
    assert GT.chart_href("BBB", "5m", V.GG1) == "/sepa/BBB?tab=supply&tf=5m_today"
    assert GT.chart_href("BBB", "5m", V.GGA) == "/sepa/BBB?tab=supply&tf=5m_today"
    assert GT.chart_href("BBB", "15m", V.GGA) == "/sepa/BBB?tab=supply&tf=15m"


def test_NEGATIVE_a_frame_outside_the_variant_opens_its_primary():
    assert GT.chart_href("BBB", "1m") == GT.chart_href("BBB", None) == "/sepa/BBB?tab=supply&tf=5m_today"
    assert GT.chart_href("BBB", "garbage") == "/sepa/BBB?tab=supply&tf=5m_today"
    assert GT.chart_href("BBB", "15m", V.GG1) == GT.chart_href("BBB", None, V.GG1) == "/sepa/BBB?tab=supply&tf=1min"


def test_the_module_holds_exactly_one_href_call_inside_chart_href():
    """[C1] The ONE `board_mod._href(sym)` lives in chart_href; the tile builders call chart_href; no parallel
    `/sepa/` spelling (the Luk refix rule, tests/test_luk_tab.py)."""
    call = "board_mod._href(sym)"
    mod = inspect.getsource(GT)
    helper = inspect.getsource(GT.chart_href)
    assert mod.count(call) == 1 and helper.count(call) == 1
    for fn in (GT.setup_tile, GT._list_tile):
        s = inspect.getsource(fn)
        assert call not in s and "chart_href(sym" in s, fn.__name__
    assert '"/sepa/' not in mod and "'/sepa/" not in mod and 'f"/sepa/' not in mod


def test_NEGATIVE_the_house_href_and_luk_hrefs_are_unchanged():
    assert board_mod._href("X") == "/sepa/X?tab=supply"
    from tests.test_luk_tab import _build as luk_build
    out = luk_build()
    assert out["tiles"], "the Luk fixture serves tiles"
    for t in out["tiles"]:
        assert t["href"] == board_mod._href(t["symbol"]) and "tf=" not in t["href"], t["href"]


# ── GG5 builds ──────────────────────────────────────────────────────────────────────────────────────────────────
def test_gg5_bull_flag_cards_open_today_on_5_minutes():
    out = GT.build(BF, now=NOW, store=ordering_store())
    t = out["tiles"][0]
    assert t["tf"] == "5m" and t["href"] == "/sepa/BBB?tab=supply&tf=5m_today"
    assert all(x["href"] == GT.chart_href(x["symbol"], x["tf"]) for x in out["tiles"])


def test_gg5_a_15m_ask_with_15m_bars_opens_the_two_week_frame():
    out = GT.build(BF, tf="15m", now=NOW, store=ordering_store())
    assert out["tiles"] and all(t["tf"] == "15m" and t["href"].endswith("&tf=15m") for t in out["tiles"])


def test_gg5_a_15m_ask_with_no_15m_bars_opens_the_frame_the_card_is_drawn_on():
    """HIS CALL #2: the frame = the frame the card is DRAWN on (the setup_tile fallback to the other frame)."""
    doc = read_doc("NOFT", {BF: R(BF, "forming")})
    doc["tile"]["bars15"] = []
    st = store_with(reads=[doc], scans=[scan_doc("NOFT")], passes=[latest()])
    (t,) = GT.build(BF, tf="15m", now=NOW, store=st)["tiles"]
    assert t["tf"] == "5m" and t["href"] == "/sepa/NOFT?tab=supply&tf=5m_today"
    t2 = _tile(doc, BF, "15m")
    assert t2["tf"] == "5m" and t2["href"].endswith("&tf=5m_today")      # NEGATIVE: never the asked 15m


def test_gg5_fade_card_drawn_on_15m_opens_15m():
    doc = read_doc("FADE", {HF: R(HF, "forming", frame="15m")})
    t = _tile(doc, HF, GT.tile_tf(doc["setups"][HF], "", "15m"))
    assert t["tf"] == "15m" and t["href"] == "/sepa/FADE?tab=supply&tf=15m"


# ── ☀️ / 🌙 ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_bar_less_movers_tiles_open_the_primary_frame():
    """HIS CALL #3: a bar-less ☀️/🌙 tile opens the variant's primary frame."""
    pm = GT.build("premarket", now=NOW, store=_pm_store())["tiles"]
    post = GT.build("postmarket", now=utc(19, 58), store=_post_store())["tiles"]
    assert pm and post
    for t in pm + post:
        assert t["bars"] == [] and t["href"] == f"/sepa/{t['symbol']}?tab=supply&tf=5m_today", t["href"]
    assert GT._list_tile("ZZZ", "postmarket", None, "15m", scan_row={}, sess={}, listed=None,
                         extra={"state_label": "x"})["href"] == "/sepa/ZZZ?tab=supply&tf=5m_today"
    assert GT._list_tile("ZZZ", "postmarket", None, "5m", scan_row={}, sess={}, listed=None,
                         extra={"state_label": "x"}, v=V.GG1)["href"] == "/sepa/ZZZ?tab=supply&tf=1min"


def test_a_movers_tile_with_bars_opens_its_drawn_frame():
    rows = [dict(ROWS_AH[0], symbol="PFAI")]
    for tf, key, n in (("", "5m_today", 12), ("15m", "15m", 4)):
        out = GT.build("postmarket", tf=tf, now=utc(19, 58), store=_post_store(rows=rows))
        (t,) = out["tiles"]
        assert len(t["bars"]) == n and t["href"] == f"/sepa/PFAI?tab=supply&tf={key}", (tf, t["href"])


# ── GG1 (the 1-minute page) / GGA (🧪 audited) ───────────────────────────────────────────────────────────────
def _gg1_doc(sym="ONEM"):
    return {"symbol": sym, "setups": {BF: R(BF, "forming", frame="1m"), HF: R(HF, "forming", frame="5m")},
            "tile": {"bars1": bars(10), "bars5": bars(4)}}


def test_gg1_cards_open_1min_and_the_fade_default_opens_5m_today(stores):
    _g5, g1, *_ = stores
    out = board(g1, BF)
    assert out["tiles"] and all(t["tf"] == "1m" and t["href"] == f"/sepa/{t['symbol']}?tab=supply&tf=1min"
                                for t in out["tiles"])
    fade = board(g1, HF)
    assert fade["tf"] == "5m"                                    # the slow frame is the Fade default on GG1
    assert all(t["href"].endswith("&tf=5m_today") for t in fade["tiles"] if t.get("tf") == "5m")
    doc = _gg1_doc()
    assert _tile(doc, BF, "1m", V.GG1)["href"] == "/sepa/ONEM?tab=supply&tf=1min"
    assert _tile(doc, HF, fade["tf"], V.GG1)["href"] == "/sepa/ONEM?tab=supply&tf=5m_today"
    # NEGATIVE: a 15m ask on the 1-minute page is not one of its frames → its primary
    assert _tile(doc, BF, "15m", V.GG1)["href"] == "/sepa/ONEM?tab=supply&tf=1min"
    for sub in SUB_KEYS:
        _assert_clean_hrefs(board(g1, sub), ("GG1", sub))


def test_gga_cards_open_today_on_5_minutes():
    gga = gga_store(ordering_store())
    out = GT.build(BF, now=NOW, store=gga)
    assert out["tiles"] and all(t["href"] == f"/sepa/{t['symbol']}?tab=supply&tf=5m_today" for t in out["tiles"])
    assert _tile(read_doc("AUD", {BF: R(BF, "forming")}), BF, "5m", V.GGA)["href"] == "/sepa/AUD?tab=supply&tf=5m_today"
    for sub in SUB_KEYS:
        _assert_clean_hrefs(GT.build(sub, now=NOW, store=gga), ("GGA", sub))


# ── NEGATIVES over every sub and every golden ────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sub", SUB_KEYS)
def test_NEGATIVE_no_gg5_href_is_bare_windowed_or_off_pattern(sub):
    for st in (ordering_store(), _pm_store(), _post_store()):
        for tf in ("", "5m", "15m"):
            _assert_clean_hrefs(GT.build(sub, tf=tf, now=NOW, store=st, owner=True), (sub, tf))


@pytest.mark.parametrize("path", GOLDENS, ids=lambda p: p.name)
def test_NEGATIVE_every_golden_href_is_on_pattern(path):
    hs = _assert_clean_hrefs(json.loads(path.read_text(encoding="utf-8")), path.name)
    sepa = [h for h in hs if h.startswith("/sepa/")]
    assert sepa, f"{path.name} serves at least one card href"
    assert all("&tf=" in h for h in sepa)
