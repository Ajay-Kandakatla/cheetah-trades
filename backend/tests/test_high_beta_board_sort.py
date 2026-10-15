"""🎢 High Beta — the header sorts through `board.board` / `GET /chart-maps`
(WP2 hb-board, "2026-10-14 b").

Ajay 2026-10-14, verbatim: "Can you add sort function on the headers and also 5
day and 21 days columns to show how they were reacting in price like hot sectors
and also add sales tab make it like hot sector with some important metrics like
EPS, QUAlity and other colums that show the strength of the stock".

What this file pins (BUILD_SPEC2 §3.5 / §4 WP2, AMENDMENTS2 B5): `hb_dir`
reaches `HB.rank` and every block, the charts follow the SERVER's order (an
in-order subsequence of the rows; the first N rows when nothing is cut), the
three presets keep their old orders byte for byte, the param is tab-scoped,
the membership writer still sees the default page request as default, and the
API threads `hb_dir` (blank -> None). Hermetic: the research-cache read is
`HB._fund_source`, monkeypatched where a ready read is needed; un-patched it
answers ({}, {}) under tests/conftest.py (the not_read case).
"""
from __future__ import annotations

import inspect
import re

import pytest

from chart_maps import board as BOARD
from chart_maps import high_beta_tab as HB
from chart_maps import membership as MEM
from rotation import hottest as HOT

from tests.test_high_beta_tab import (BACKEND, FRI, NOW_NIGHT, UNIVERSE, _FakeDB,  # noqa: F401,E402
                                      _clean, _frame, _frames, _patch_build, _stub_board,
                                      hb_board)
from tests.test_high_beta_table_2026_10_14 import FUND_SOURCE                    # noqa: E402

DEFAULT_ROWS = ["AAA", "THIN", "BBB", "CCC"]          # test_16's pinned default order


@pytest.fixture
def hb_board_fund(monkeypatch):
    """`hb_board` with the Sales view's fundamentals READY (WP1's DEC / EARN)."""
    monkeypatch.setattr(HB, "_fund_source", FUND_SOURCE)
    state = {"snap_calls": [], "db": _FakeDB()}
    fr = _frames()
    fr["THIN"] = _frame(2.4, move=-6.0, volume=100.0)
    _patch_build(monkeypatch, fr, universe=UNIVERSE + ["THIN"])
    _stub_board(monkeypatch, state)
    monkeypatch.setattr(MEM, "_db", lambda db=None: state["db"])
    HB.cached_or_warm("full", now=NOW_NIGHT, sync=True)
    return state


def _syms(items) -> list:
    return [x["symbol"] for x in items]


def _expected(rows: list, col: str, d: str, *, field=None) -> list:
    """Hottest's rule, written out independently: present values by value in
    `d`, exact ties A→Z, every missing value last (A→Z) in BOTH directions."""
    get = field or (lambda r: r.get(col))
    present, missing = [], []
    for r in rows:
        ok, v = HOT._sort_value({col: get(r)}, col)
        (present if ok else missing).append((v, r["symbol"]))
    present.sort(key=lambda p: (p[0] if d == "asc" else -p[0], p[1]))
    return [s for _v, s in present] + sorted(s for _v, s in missing)


def _is_subsequence(small: list, big: list) -> bool:
    it = iter(big)
    return all(any(x == y for y in it) for x in small)


def _sig_defaults(**over) -> dict:
    req = {n: p.default for n, p in inspect.signature(BOARD.board).parameters.items()}
    req.update(over)
    return req


# --------------------------------------------------------------------------
# 1 — a header sort orders the rows AND the cards (the server's order)
# --------------------------------------------------------------------------
def test_01_a_header_sort_orders_rows_and_the_cards_follow(hb_board):
    out = BOARD.board(tab="high_beta", sort="hb_ret_5d", hb_dir="asc", limit=24,
                      hb_all=True, min_tier="any")
    rows = out["rows"]
    assert rows and all(r["ret_5d"] is not None for r in rows)       # closed mode: every leg read
    assert _syms(rows) == _expected(rows, "ret_5d", "asc")
    vals = [r["ret_5d"] for r in rows]
    assert vals == sorted(vals)                                          # ascending, as asked
    # B5: min_tier "any" and every card has bars -> the cards ARE the first N rows
    assert _syms(out["tiles"]) == _syms(rows)[:len(out["tiles"])]
    b = out["high_beta_board"]
    assert b["sort"] == "hb_ret_5d" and b["sort_dir"] == "asc" and b["sort_preset"] is None
    assert out["sort"] == "hb_ret_5d"
    assert len(out["sorts"]) == 3                                        # the preset buttons only
    assert b["order_line"].startswith("Order: ")


def test_01b_desc_flips_and_a_floor_leaves_the_cards_an_in_order_subsequence(hb_board):
    out = BOARD.board(tab="high_beta", sort="hb_ret_5d", hb_dir="desc", limit=24,
                      hb_all=True, min_tier="ok")                       # THIN: a row, no card
    rows = out["rows"]
    assert _syms(rows) == _expected(rows, "ret_5d", "desc")
    assert "THIN" in _syms(rows) and "THIN" not in _syms(out["tiles"])
    # B5: the cards are an in-order SUBSEQUENCE of the rows (not the first N here)
    assert _is_subsequence(_syms(out["tiles"]), _syms(rows))
    assert _syms(out["tiles"]) == [s for s in _syms(rows) if s != "THIN"]
    assert out["high_beta_board"]["sort_dir"] == "desc"


def test_01c_a_fundamentals_sort_puts_every_missing_value_last_both_ways(hb_board_fund):
    for d in ("asc", "desc"):
        out = BOARD.board(tab="high_beta", sort="hb_sales_yoy", hb_dir=d, limit=24,
                          hb_all=True, min_tier="any")
        rows = out["rows"]
        assert out["high_beta_board"]["fundamentals"]["state"] == HB.FUND_READY
        got = _syms(rows)
        assert got == _expected(rows, "sales_yoy", d,
                                field=lambda r: (r.get("fund") or {}).get("sales_yoy"))
        missing = [r["symbol"] for r in rows if (r.get("fund") or {}).get("sales_yoy") is None]
        assert missing and got[-len(missing):] == sorted(missing)       # NEGATIVE: never on top
        assert _syms(out["tiles"]) == got[:len(out["tiles"])]


# --------------------------------------------------------------------------
# 2 — GOLDEN: the three presets keep their old order with or without hb_dir
# --------------------------------------------------------------------------
@pytest.mark.parametrize("sort", ["default", HB.SORT_SWING, HB.SORT_DROP, HB.SORT_VOL])
@pytest.mark.parametrize("green", [False, True])
def test_02_golden_presets_without_hb_dir_equal_their_own_first_direction(hb_board, sort, green):
    srt = HB.resolve_sort(sort)
    a = BOARD.board(tab="high_beta", sort=sort, limit=24, hb_all=green)
    b = BOARD.board(tab="high_beta", sort=sort, limit=24, hb_all=green,
                    hb_dir=HB.PRESET_DIRS[srt])
    assert _syms(a["rows"]) == _syms(b["rows"]) and _syms(a["tiles"]) == _syms(b["tiles"])
    assert a["high_beta_board"]["sort_preset"] == srt == b["high_beta_board"]["sort_preset"]
    assert a["high_beta_board"]["order_line"] == b["high_beta_board"]["order_line"]
    # the legacy `sort_key`, verbatim, over the same memo rows
    entry = HB._memo[(HB.MODE_CLOSED, FRI.isoformat(), "full")]
    legacy = sorted(entry["rows"].values(), key=HB.sort_key(srt))
    legacy = [r["symbol"] for r in legacy if green or HB.is_red(r)]
    assert _syms(a["rows"]) == legacy


def test_02b_golden_the_default_page_keeps_test_16s_order(hb_board):
    out = BOARD.board(tab="high_beta", limit=24)
    assert _syms(out["rows"]) == DEFAULT_ROWS and _syms(out["tiles"]) == DEFAULT_ROWS
    b = out["high_beta_board"]
    assert b["sort"] == HB.SORT_SWING and b["sort_dir"] == "desc" and b["sort_preset"] == HB.SORT_SWING


def test_02c_NEG_a_flipped_preset_is_not_the_preset(hb_board):
    out = BOARD.board(tab="high_beta", sort=HB.SORT_DROP, hb_dir="desc", limit=24, hb_all=True)
    b = out["high_beta_board"]
    assert b["sort"] == HB.SORT_DROP and b["sort_dir"] == "desc" and b["sort_preset"] is None
    rows = out["rows"]
    assert _syms(rows) == _expected(rows, "today", "desc",
                                    field=lambda r: r["move_pct"] if r["state"] == "read" else None)


@pytest.mark.parametrize("junk", ["sideways", "", "  ", "ASC ", 5])
def test_02d_NEG_junk_hb_dir_is_the_columns_first_direction(hb_board, junk):
    out = BOARD.board(tab="high_beta", sort=HB.SORT_VOL, hb_dir=junk, limit=24, hb_all=True)
    base = BOARD.board(tab="high_beta", sort=HB.SORT_VOL, limit=24, hb_all=True)
    if junk == "ASC ":                                       # case / space tolerant -> a real "asc"
        assert out["high_beta_board"]["sort_dir"] == "asc"
        return
    assert out["high_beta_board"]["sort_dir"] == "desc"
    assert _syms(out["rows"]) == _syms(base["rows"])


# --------------------------------------------------------------------------
# 3 — tab-scoped
# --------------------------------------------------------------------------
def test_03_NEG_hb_dir_and_the_header_keys_are_tab_scoped(hb_board):
    z = BOARD.board(tab="zones", limit=24, hb_dir="asc")
    assert "high_beta_board" not in z
    z0 = BOARD.board(tab="zones", limit=24)
    assert _syms(z.get("tiles") or []) == _syms(z0.get("tiles") or [])
    d = BOARD.board(tab="drop10", sort="hb_ret_5d")
    assert d["sort"] == "default"
    v = BOARD.board(tab="vcp", sort="hb_beta", hb_dir="asc")
    assert v["sort"] == "default" and "high_beta_board" not in v
    assert not set(HB.TAB_SORTS) & set(BOARD.SORTS)


# --------------------------------------------------------------------------
# 4 — membership (the 2026-10-14 trap, twice): hb_dir in the hook AND default
# --------------------------------------------------------------------------
def test_04_membership_default_page_writes_and_a_header_sort_writes_nothing(hb_board):
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX)
    doc = hb_board["db"].coll.docs.get("high_beta")
    assert doc and doc["symbols"] == DEFAULT_ROWS
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX, hb_dir="desc")
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX, sort="hb_beta")
    BOARD.board(tab="high_beta", limit=BOARD.LIMIT_MAX, sort="hb_ret_5d", hb_dir="asc")
    assert hb_board["db"].coll.writes == 1                   # NEGATIVE: header sorts write nothing


def test_04b_is_default_request_reads_hb_dir_off_the_signature():
    sig = inspect.signature(BOARD.board).parameters
    assert "hb_dir" in sig and sig["hb_dir"].default is None
    assert MEM.is_default_request(**_sig_defaults(limit=BOARD.LIMIT_MAX)) is True
    assert MEM.is_default_request(**_sig_defaults(limit=BOARD.LIMIT_MAX, tab="high_beta")) is True
    for off in ("x", "asc", "desc"):                         # NEGATIVE: any hb_dir is off-default
        assert MEM.is_default_request(**_sig_defaults(limit=BOARD.LIMIT_MAX, tab="high_beta",
                                                      hb_dir=off)) is False


def test_04c_hb_dir_is_in_the_hook_dict_and_the_hook_equals_the_signature():
    src = (BACKEND / "chart_maps" / "board.py").read_text(encoding="utf-8")
    m = re.search(r"_MB\.record_board\(t, out, request=\{(.*?)\}\)", src, re.S)
    assert m, "the membership hook is missing from board()"
    keys = set(re.findall(r'"([a-z_]+)":', m.group(1)))
    assert '"hb_dir": hb_dir' in m.group(1)
    assert keys == set(inspect.signature(BOARD.board).parameters)


def test_04d_board_threads_hb_dir_to_the_tab_and_every_block():
    src = inspect.getsource(BOARD.board)
    assert "hb_dir=hb_dir if isinstance(hb_dir, str) else None" in src
    tiles = inspect.getsource(BOARD.high_beta_tiles)
    assert "direction=hb_dir" in tiles and tiles.count("direction=hb_dir") == 4   # rank + 3 blocks
    # the UnboundLocalError trap: no `HB.` reference in CODE above the local import
    head, _sep, _tail = tiles.partition("from chart_maps import high_beta_tab as HB")
    assert _sep and head.count('"""') == 2
    assert "HB." not in head.split('"""')[-1]


# --------------------------------------------------------------------------
# 5 — API
# --------------------------------------------------------------------------
def _client():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from chart_maps import api as A
    app = FastAPI()
    app.include_router(A.router)
    return TestClient(app)


def test_05_api_hands_board_hb_dir_and_blank_is_none(monkeypatch):
    from chart_maps import api as A
    params = set(inspect.signature(BOARD.board).parameters)            # before the stub
    seen = []
    monkeypatch.setattr(A.board_mod, "board", lambda **kw: seen.append(kw) or {"tiles": []})
    c = _client()
    assert c.get("/chart-maps?tab=high_beta&sort=hb_rel_21d&hb_dir=asc").status_code == 200
    assert seen[-1]["hb_dir"] == "asc" and seen[-1]["sort"] == "hb_rel_21d"
    for q in ("&hb_dir=", "&hb_dir=%20%20", ""):              # NEGATIVE: blank / spaces / absent
        assert c.get("/chart-maps?tab=high_beta" + q).status_code == 200
        assert seen[-1]["hb_dir"] is None, q
    assert set(seen[-1]) == params                            # every board() param, by name


def test_05b_api_source_spells_the_pass_through_and_quotes_the_ask():
    src = (BACKEND / "chart_maps" / "api.py").read_text(encoding="utf-8")
    assert "hb_dir=(hb_dir if isinstance(hb_dir, str) and hb_dir.strip() else None)," in src
    q = src[src.index("hb_dir: str = Query"):src.index("min_tier: Optional[str] = Query")]
    assert "Ajay 2026-10-14: 'Can you " in q and "add sort function on the headers" in q
    # test_13f's slice (hb: … min_tier:) holds the new Query and stays clean
    sl = src[src.index("hb: str = Query"):src.index("min_tier: Optional[str] = Query")]
    assert "hb_dir: str = Query" in sl
    for w in ("bounce",) + tuple(HB.FORBIDDEN_WORDS):
        assert w not in sl.lower(), w


def test_05c_the_default_page_through_http_stays_default_and_hb_dir_does_not(monkeypatch, hb_board):
    seen = []
    monkeypatch.setattr(MEM, "record_board",
                        lambda tab, out, *, request, db=None:
                        seen.append(MEM.is_default_request(**request)) or True)
    c = _client()
    assert c.get(f"/chart-maps?tab=high_beta&limit={BOARD.LIMIT_MAX}").status_code == 200
    assert seen == [True]
    assert c.get(f"/chart-maps?tab=high_beta&limit={BOARD.LIMIT_MAX}&hb_dir=").status_code == 200
    assert seen == [True, True]                               # a blank hb_dir is the default page
    r = c.get(f"/chart-maps?tab=high_beta&limit={BOARD.LIMIT_MAX}&sort=hb_beta&hb_dir=asc")
    assert r.status_code == 200 and seen == [True, True, False]
    hb = r.json()["high_beta_board"]
    assert hb["sort"] == "hb_beta" and hb["sort_dir"] == "asc"


# --------------------------------------------------------------------------
# 6 — fundamentals not read: the Sales sorts fall to A→Z and say so
# --------------------------------------------------------------------------
@pytest.mark.parametrize("d", [None, "asc", "desc"])
def test_06_NEG_a_sales_sort_with_fundamentals_not_read_is_a_to_z(hb_board, d):
    out = BOARD.board(tab="high_beta", sort="hb_q_eps_yoy", hb_dir=d, limit=24, hb_all=True)
    b = out["high_beta_board"]
    assert b["fundamentals"]["state"] == HB.FUND_NOT_READ
    assert all(r["fund"] is None for r in out["rows"])                 # never a zero
    assert _syms(out["rows"]) == sorted(_syms(out["rows"]))
    assert _syms(out["tiles"]) == _syms(out["rows"])[:len(out["tiles"])]
    assert b["order_line"].endswith(HB.ORDER_NONE)
    assert b["counts"]["sort_present"] == 0 and b["counts"]["sort_missing"] == len(out["rows"])


def test_06b_NEG_a_ready_read_never_says_order_none(hb_board_fund):
    out = BOARD.board(tab="high_beta", sort="hb_q_eps_yoy", limit=24, hb_all=True)
    assert out["high_beta_board"]["fundamentals"]["state"] == HB.FUND_READY
    assert not out["high_beta_board"]["order_line"].endswith(HB.ORDER_NONE)


# --------------------------------------------------------------------------
# 7 — the memo rows are never mutated by a header-sort request
# --------------------------------------------------------------------------
def test_07_NEG_memo_rows_untouched_by_a_sales_tier_sort(hb_board_fund):
    key = (HB.MODE_CLOSED, FRI.isoformat(), "full")
    before = repr(HB._memo[key]["rows"])
    before_order = list(HB._memo[key]["rows"])
    out = BOARD.board(tab="high_beta", sort="hb_sales_tier", hb_dir="asc", limit=24, hb_all=True)
    assert repr(HB._memo[key]["rows"]) == before
    assert list(HB._memo[key]["rows"]) == before_order                 # the dict's own order too
    rows = out["rows"]
    assert _syms(rows) == _expected(rows, "sales_tier", "asc",
                                    field=lambda r: (r.get("fund") or {}).get("sales_tier"))
    # a served row's fund is a copy: editing it never reaches the memo
    rows[0]["fund"]["sales_tier"] = "edited"
    assert repr(HB._memo[key]["rows"]) == before
