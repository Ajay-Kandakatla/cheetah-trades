"""🔴 Gajjala cards live — the served live-vs-levels words (BUILD_SPEC20 D2 / D6 / D7, 2026-10-21).

Ajay 2026-10-21: "Are we not real time SAIQ already broke the EMA" / "I see it on Stock Twitz" / "If something is
Potential add min on min for pricing and other updates to make them more realtime and give us a better edge".

`POST /chart-maps/live` takes an OPTIONAL `levels` {SYM: {trigger, stop, tf}} (the numbers the 🚩 tab already served)
and `live_card.compose` adds a display-only `vs` {kind, text} per quote. Synthetic frames + snapshot rows (the
test_chart_maps_live_card fixtures), a fixed ET clock, no network. NEGATIVES: bad levels ignored (never a 422), no now
price / no levels → no `vs` key, the quote block unchanged, and the import guard (no module under chart_maps/gajjala or
trading imports live_card — `vs` never becomes a read).
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from chart_maps import live_card as LC                     # noqa: E402
from chart_maps.gajjala import constants as GC             # noqa: E402
from chart_maps.gajjala import tab as GT                   # noqa: E402

from test_chart_maps_live_card import RTH_SNAP, _at, _client, _wire   # noqa: E402
from test_prices_today_bar import _frame                   # noqa: E402

BACKEND = Path(__file__).resolve().parents[1]
FE_CARD_LIVE = BACKEND.parent / "frontend" / "src" / "lib" / "cardLive.ts"
NOW = _at(2026, 9, 3, 14, 0, 30)          # RTH_SNAP's print is 9.12 at 14:00:00 ET


def _compose(monkeypatch, levels, syms=("XLAB",), now=NOW):
    _wire(monkeypatch, {"XLAB": RTH_SNAP, "NVDA": RTH_SNAP}, {"XLAB": _frame(), "NVDA": _frame()})
    return LC.compose(list(syms), levels=levels, now=now)


# ── the three kinds, verbatim ────────────────────────────────────────────────
def test_over_trigger_text_verbatim(monkeypatch):
    q = _compose(monkeypatch, {"XLAB": {"trigger": 9.0, "stop": 8.5, "tf": "5m"}})["quotes"]["XLAB"]
    assert q["now"]["price"] == 9.12
    assert q["vs"] == {"kind": "over_trigger",
                       "text": "🔴 9.12 over the trigger 9.00 on the live bar — the read moves when the 5-minute bar "
                               "closes (14:05 ET)"}


def test_under_stop_text_verbatim(monkeypatch):
    q = _compose(monkeypatch, {"XLAB": {"trigger": 9.5, "stop": 9.2, "tf": "5m"}})["quotes"]["XLAB"]
    assert q["vs"] == {"kind": "under_stop",
                       "text": "🔴 9.12 under the stop 9.20 on the live bar — the read moves when the 5-minute bar "
                               "closes (14:05 ET)"}


def test_between_text_verbatim(monkeypatch):
    q = _compose(monkeypatch, {"XLAB": {"trigger": 9.5, "stop": 9.0, "tf": "5m"}})["quotes"]["XLAB"]
    assert q["vs"] == {"kind": "between", "text": "🔴 9.12 · between the stop 9.00 and the trigger 9.50"}


def test_text_is_built_from_the_vs_text_constants():
    assert set(LC.VS_TEXT) == {"over_trigger", "under_stop", "between"}
    assert LC.VS_KINDS == ("over_trigger", "under_stop", "between", "none")
    v = LC.live_vs(9.12, {"trigger": 9.0, "stop": 8.5}, NOW)
    assert v["text"] == LC.VS_TEXT["over_trigger"].format(px="9.12", trigger="9.00", stop="8.50", tf=5,
                                                          next_close="14:05")


# ── the boundaries: px ≥ trigger → over, px ≤ stop → under (both equalities pinned) ─────────────────────────────
def test_equality_px_equal_trigger_is_over_trigger():
    assert LC.live_vs(9.12, {"trigger": 9.12, "stop": 9.0}, NOW)["kind"] == "over_trigger"
    assert LC.live_vs(9.1199, {"trigger": 9.12, "stop": 9.0}, NOW)["kind"] == "over_trigger", "same grid price"
    assert LC.live_vs(9.11, {"trigger": 9.12, "stop": 9.0}, NOW)["kind"] == "between"


def test_equality_px_equal_stop_is_under_stop():
    assert LC.live_vs(9.0, {"trigger": 9.12, "stop": 9.0}, NOW)["kind"] == "under_stop"
    assert LC.live_vs(9.01, {"trigger": 9.12, "stop": 9.0}, NOW)["kind"] == "between"


def test_trigger_equal_stop_reads_over_first():
    # a no-risk read (trigger = stop) at that price: the spec's order — over_trigger is checked first
    assert LC.live_vs(5.63, {"trigger": 5.63, "stop": 5.63}, NOW)["kind"] == "over_trigger"
    assert LC.live_vs(5.62, {"trigger": 5.63, "stop": 5.63}, NOW)["kind"] == "under_stop"


def test_one_sided_levels():
    assert LC.live_vs(9.12, {"trigger": 9.0}, NOW)["kind"] == "over_trigger"
    assert LC.live_vs(9.12, {"stop": 9.2}, NOW)["kind"] == "under_stop"
    # NEGATIVE: one level and the price on the other side → nothing to say (no "between" without both)
    assert LC.live_vs(9.12, {"trigger": 9.5}, NOW) is None
    assert LC.live_vs(9.12, {"stop": 9.0, "trigger": None}, NOW) is None


# ── grid rounding under $1 (the tab's own `_px`) ─────────────────────────────
def test_grid_rounding_under_a_dollar():
    v = LC.live_vs(0.58765, {"trigger": 0.65, "stop": 0.6012}, NOW)
    assert v["kind"] == "under_stop"
    assert v["text"].startswith("🔴 0.5877 under the stop 0.6012 on the live bar")
    assert GT._px(0.58765) == "0.5877"
    b = LC.live_vs(0.62, {"trigger": 0.65, "stop": 0.6}, NOW)
    assert b["text"] == "🔴 0.62 · between the stop 0.6 and the trigger 0.65", "trailing zeros dropped under $1"
    # compared on the grid: 0.60124 prints 0.6012 = the stop → under_stop (never "between" beside an equal print)
    assert LC.live_vs(0.60124, {"trigger": 0.65, "stop": 0.6012}, NOW)["kind"] == "under_stop"


# ── tf + next_close (frozen clock) ───────────────────────────────────────────
def test_tf_15_says_15_minute_and_the_15_minute_boundary(monkeypatch):
    q = _compose(monkeypatch, {"XLAB": {"trigger": 9.0, "stop": 8.5, "tf": "15m"}})["quotes"]["XLAB"]
    assert "the 15-minute bar closes (14:15 ET)" in q["vs"]["text"]
    for tf in (15, "15"):
        assert "15-minute" in LC.live_vs(9.12, {"trigger": 9.0, "tf": tf}, NOW)["text"]


def test_negative_any_other_tf_reads_as_5():
    # WIDENED 2026-10-27 (BUILD_SPEC27 §3.7 — 🚩 1-minute page inserted, Ajay "do the same logic of Gajjalas but on 1
    # min candles"): "1m" is now a variant frame and reads as 1 (pinned in test_gajjala_1m_page_2026_10_27.py); every
    # other junk value still reads as 5, and vs_tf_minutes() stays GG5's TFS.
    for tf in (None, 7, "abc", True, 15.0, [15], {"m": 15}):
        t = LC.live_vs(9.12, {"trigger": 9.0, "tf": tf}, NOW)["text"]
        assert "the 5-minute bar closes (14:05 ET)" in t, tf
    assert LC.vs_tf_minutes() == tuple(int(s.rstrip("m")) for s in GT.TFS) == (5, 15)


def test_next_close_on_the_tf_boundary():
    assert LC.next_close(_at(2026, 10, 21, 11, 40, 0), 5) == "11:45", "on a boundary → the bar that just opened"
    assert LC.next_close(_at(2026, 10, 21, 11, 40, 15), 5) == "11:45"
    assert LC.next_close(_at(2026, 10, 21, 11, 44, 59), 5) == "11:45"
    assert LC.next_close(_at(2026, 10, 21, 11, 45, 0), 5) == "11:50"
    assert LC.next_close(_at(2026, 10, 21, 11, 40, 0), 15) == "11:45"
    assert LC.next_close(_at(2026, 10, 21, 11, 45, 0), 15) == "12:00"
    assert LC.next_close(_at(2026, 10, 21, 19, 58, 0), 5) == "20:00"
    assert LC.next_close(_at(2026, 10, 21, 23, 58, 0), 5) == "00:00"


def test_saiq_worked_example_f4():
    # F4: 11:40 the live bar traded 5.58 under the 🧠 Potential stop 5.63 while the card said "BUY > 5.85 / STOP 5.63"
    v = LC.live_vs(5.58, {"trigger": 5.85, "stop": 5.63, "tf": "5m"}, _at(2026, 10, 21, 11, 40, 15))
    assert v == {"kind": "under_stop",
                 "text": "🔴 5.58 under the stop 5.63 on the live bar — the read moves when the 5-minute bar closes "
                         "(11:45 ET)"}


# ── NEGATIVES: no `vs` key ───────────────────────────────────────────────────
def test_negative_no_levels_no_vs_key(monkeypatch):
    for levels in (None, {}):
        a = _compose(monkeypatch, levels)
        assert "vs" not in a["quotes"]["XLAB"], levels
    _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    a = LC.compose(["XLAB"], now=NOW)
    assert "vs" not in a["quotes"]["XLAB"], "the old call shape (no levels kwarg) never gains the key"


def test_negative_no_now_price_no_vs(monkeypatch):
    monkeypatch.setattr(LC, "card_now", lambda probe, snap: None)
    q = _compose(monkeypatch, {"XLAB": {"trigger": 9.0, "stop": 8.5}})["quotes"]["XLAB"]
    assert q["bar"] is not None and q["now"] is None
    assert "vs" not in q
    assert LC.live_vs(None, {"trigger": 9.0}, NOW) is None


def test_negative_bad_levels_are_ignored_per_symbol(monkeypatch):
    base = _compose(monkeypatch, None, syms=("XLAB", "NVDA"))["quotes"]
    bad = ("abc", [1, 2], 5, {"XLAB": "x"}, {"XLAB": [9.0]}, {"XLAB": {"trigger": "9.0"}},
           {"XLAB": {"trigger": True}}, {"XLAB": {"trigger": float("nan")}}, {"XLAB": {"stop": float("inf")}},
           {"XLAB": {"trigger": -1}}, {"XLAB": {"trigger": 0}}, {"XLAB": {}}, {"XLAB": {"tf": "5m"}},
           {"ZZZZQ": {"trigger": 1.0}}, {5: {"trigger": 1.0}},
           {"XLAB": {"trigger": 9.0, "stop": "8.5"}})
    for levels in bad:
        a = _compose(monkeypatch, levels, syms=("XLAB", "NVDA"))
        assert a["quotes"] == base, levels
        json.dumps(a, allow_nan=False)
    # one symbol's bad levels never touch another symbol's good ones
    a = _compose(monkeypatch, {"XLAB": {"trigger": "x"}, "NVDA": {"trigger": 9.0}}, syms=("XLAB", "NVDA"))
    assert "vs" not in a["quotes"]["XLAB"] and a["quotes"]["NVDA"]["vs"]["kind"] == "over_trigger"


def test_levels_keys_normalize_like_symbols(monkeypatch):
    a = _compose(monkeypatch, {" xlab ": {"trigger": 9.0}})
    assert a["quotes"]["XLAB"]["vs"]["kind"] == "over_trigger"


def test_negative_bad_levels_through_the_route_never_a_422(monkeypatch):
    _wire(monkeypatch, {"XLAB": RTH_SNAP}, {"XLAB": _frame()})
    c = _client()
    ref = c.post("/chart-maps/live", json={"symbols": ["XLAB"]}).json()["quotes"]
    for levels in ("abc", [1], 5, None, {"XLAB": "x"}, {"XLAB": {"trigger": "9.0"}}, {"XLAB": {"trigger": True}},
                   {"NVDA": {"trigger": 1.0}}):
        r = c.post("/chart-maps/live", json={"symbols": ["XLAB"], "levels": levels})
        assert r.status_code == 200, levels
        assert r.json()["quotes"] == ref, levels
    good = c.post("/chart-maps/live", json={"symbols": ["XLAB"], "levels": {"XLAB": {"trigger": 9.5, "stop": 9.0}}})
    assert good.status_code == 200 and good.json()["quotes"]["XLAB"]["vs"]["kind"] == "between"


def test_negative_route_422_and_413_unchanged_with_levels(monkeypatch):
    calls = _wire(monkeypatch, {}, {})
    c = _client()
    lv = {"XLAB": {"trigger": 9.0}}
    for body in ({"levels": lv}, {"symbols": "XLAB", "levels": lv}, {"symbols": None, "levels": lv}):
        r = c.post("/chart-maps/live", json=body)
        assert r.status_code == 422 and r.json() == {"detail": LC.BAD_BODY_TEXT}, body
    syms = [f"S{i:03d}" for i in range(251)]
    r = c.post("/chart-maps/live", json={"symbols": syms, "levels": {s: {"trigger": 1.0} for s in syms}})
    assert r.status_code == 413 and r.json() == {"detail": "up to 250 symbols per live read — 251 sent"}
    assert calls["snap"] == []


def test_the_quote_block_is_unchanged_by_levels(monkeypatch):
    plain = _compose(monkeypatch, None)
    lv = _compose(monkeypatch, {"XLAB": {"trigger": 9.0, "stop": 8.5}})
    q = dict(lv["quotes"]["XLAB"])
    assert set(q) == set(plain["quotes"]["XLAB"]) | {"vs"}
    q.pop("vs")
    assert q == plain["quotes"]["XLAB"]
    assert {k: v for k, v in lv.items() if k != "quotes"} == {k: v for k, v in plain.items() if k != "quotes"}


def test_negative_a_vs_fault_never_fails_the_quote(monkeypatch):
    def boom(*a, **k):
        raise ValueError("bad level")
    monkeypatch.setattr(LC, "live_vs", boom)
    a = _compose(monkeypatch, {"XLAB": {"trigger": 9.0}})
    assert a["served"] == 1 and a["faults"] == {} and "vs" not in a["quotes"]["XLAB"]


# ── the cap fits the tab ─────────────────────────────────────────────────────
def test_the_gajjala_tile_limit_fits_one_live_read():
    assert GC.TILE_LIMIT_MAX <= LC.cap(), "the tab's largest page never meets the 413"


# ── the ℹ️ line + the FE cadence mirror ──────────────────────────────────────
def test_card_live_sec_mirrors_the_fe_constant():
    src = FE_CARD_LIVE.read_text()
    m = re.search(r"export const CARD_LIVE_MS = ([\d_]+);", src)
    assert m, "CARD_LIVE_MS moved"
    assert int(m.group(1).replace("_", "")) == LC.CARD_LIVE_SEC * 1000


def test_rules_info_line_is_built_from_the_constants(monkeypatch):
    from supply_demand import rules_info as RI
    want = ("🔴 Live on the card: price and the live-bar relation refresh every %d s; the read moves at the %d-minute "
            "bar close" % (LC.CARD_LIVE_SEC, LC.vs_tf_minutes()[0]))
    stops = RI._gajjala_section()["stops"]
    assert sum(1 for s in stops if s.startswith(want)) == 1
    monkeypatch.setattr(LC, "CARD_LIVE_SEC", 10)
    moved = RI._gajjala_section()["stops"]
    assert any("refresh every 10 s" in s for s in moved) and not any("every 30 s" in s for s in moved)


def test_rules_line_names_the_15_minute_close_from_tfs(monkeypatch):
    """Critic 2026-10-21: a ➖ fade read on 15-minute bars moves at the 15-minute close — the line words both TFS."""
    from supply_demand import rules_info as RI
    t5, t15 = LC.vs_tf_minutes()
    line = next(s for s in RI._gajjala_section()["stops"] if s.startswith("🔴 Live on the card"))
    assert "the %d-minute bar close (the %d-minute close for a read on %d-minute bars)" % (t5, t15, t15) in line
    monkeypatch.setattr(LC, "vs_tf_minutes", lambda: (5, 30))
    moved = next(s for s in RI._gajjala_section()["stops"] if s.startswith("🔴 Live on the card"))
    assert "the 30-minute close for a read on 30-minute bars" in moved and "15-minute" not in moved


def test_no_edge_claim_and_no_ban_word_in_the_words():
    words = " ".join(LC.VS_TEXT.values())
    assert not re.search("b" + "ounc", words, re.I)
    assert not re.search(r"\bedge\b|\bwin\b|\bbuy now\b", words, re.I)


# ── the import guard: `vs` is display only ───────────────────────────────────
# 2026-10-21 critic fix: push/ (hooks.py, recent.py carry the Gajjala pushes) and the gajjala_* scripts read too
_GUARDED = (BACKEND / "chart_maps" / "gajjala", BACKEND / "trading", BACKEND / "push")
_GUARDED_SCRIPTS = "gajjala_*.py"


def _guarded_files() -> list:
    return [p for d in _GUARDED for p in d.rglob("*.py")] + sorted((BACKEND / "scripts").glob(_GUARDED_SCRIPTS))


def _imports_live_card(src: str) -> bool:
    tree = ast.parse(src)
    for n in ast.walk(tree):
        if isinstance(n, ast.Import) and any(a.name.split(".")[-1] == "live_card" or ".live_card" in a.name
                                             for a in n.names):
            return True
        if isinstance(n, ast.ImportFrom):
            mod = n.module or ""
            if mod.split(".")[-1] == "live_card" or ".live_card" in mod:
                return True
            if any(a.name == "live_card" for a in n.names):
                return True
    return "live_card" in src or "live_vs" in src


def test_negative_import_guard_no_reader_imports_live_card():
    files = _guarded_files()
    assert len(files) > 10, "the guard walks real trees"
    rel = {str(p.relative_to(BACKEND)) for p in files}
    assert {"push/hooks.py", "push/recent.py", "scripts/gajjala_replay.py"} <= rel, "push/ and the gajjala scripts"
    hits = [str(p.relative_to(BACKEND)) for p in files if _imports_live_card(p.read_text())]
    assert hits == [], hits


@pytest.mark.parametrize("probe", [
    "from chart_maps import live_card",
    "from chart_maps import live_card as LC",
    "from .. import live_card",
    "import chart_maps.live_card",
    "from chart_maps.live_card import compose",
    "x = q.get('live_vs')",
])
def test_the_import_guard_bites(probe):
    assert _imports_live_card(probe)


def test_the_import_guard_passes_a_clean_module():
    assert not _imports_live_card("from chart_maps import board\nfrom sepa import prices\n")
