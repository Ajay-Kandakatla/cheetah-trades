"""🥇 Luk's tab — the served board (BUILD SPEC luk-tab §3.10 / WP-C, 2026-11-01).

Ajay 2026-11-01, verbatim: "look at other winners of US stocks champion ship and pic the next best one like Gajjala.
Implement their strategy please if they have online resources. ... I need something like Gajjlala that is exposed".

`luk.tab.build` over a fixture LukStore (FakeColl per `luk_*` collection, no Mongo, no provider): the payload keys, the
words verbatim, every served number in a template a constants name, the b-word / "edge" guard over every sub, the sub
pick (unknown → DEFAULT_SUB, focus picks), the strip folded, a sub's `n` equal to its rows, the served order, the
listing counts and the golden. NEGATIVES: a `listed` card keeps trigger / stop / R, a `none` read is never carded, GG's
first-15-minutes quote is never served, an empty store serves the zero board, a raising block never takes the board
down.

2026-11-11 (not-re-read cards, ORDER_VARIANT A): the four order / tag templates join the no-digit list; every fixture
read carries PASS_AT, so no fixture card is tagged and no order moves (the cases live in
tests/test_luk_not_reread_2026_11_11.py).

The golden `tests/fixtures/luk/luk_board_golden_2026_11_01.json` is regenerated ONLY by an explicit command:
    LUK_WRITE_GOLDEN=1 .venv/bin/python -m pytest tests/test_luk_tab.py -q -k golden -p no:cacheprovider
"""
from __future__ import annotations

import json
import os
import re
import string
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from chart_maps.gajjala import alerts as GA
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import variant as V
from chart_maps.luk import constants as LC
from chart_maps.luk import detectors as DT
from chart_maps.luk import ledger as LG
from chart_maps.luk import market_state as MS
from chart_maps.luk import playbook as PB
from chart_maps.luk import screens as SC
from chart_maps.luk import store as LS
from chart_maps.luk import tab as T
from chart_maps.luk.variant import LUK
from tests.test_gajjala_store import FakeColl

S = date(2026, 11, 3)                                                   # a Tuesday, a market day
NOW = datetime(2026, 11, 3, 15, 12, tzinfo=timezone.utc)                # 10:12 ET
PASS_AT = datetime(2026, 11, 3, 15, 11, 7, tzinfo=timezone.utc)         # 10:11 ET
GOLDEN = Path(__file__).parent / "fixtures" / "luk" / "luk_board_golden_2026_11_01.json"
BWORD = re.compile("b" + "ounc", re.I)                                 # the house guard (test_gajjala_source_guard.py:28)
EDGE = re.compile(r"\bedge\b", re.I)


# ── the fixture store ──────────────────────────────────────────────────────────────────────────────────────────────
def _crit(key, ok=True):
    return {"key": key, "label": key.replace("_", " "), "ok": ok, "value": f"{key} value", "need": f"{key} need"}


def _read(setup, state, **kw):
    r = {"setup": setup, "state": state, "reason": "", "frame": kw.get("frame", "5m"), "trigger": kw.get("trigger"),
         "stop": kw.get("stop"), "stop_src": kw.get("stop_src", DT.SRC_LOD), "risk_pct": kw.get("risk_pct"),
         "r_usd": kw.get("r_usd"), "entry_bar_t": kw.get("entry_bar_t"), "as_of_bar_t": "2026-11-03 10:10",
         "lod": kw.get("lod"), "criteria": kw.get("criteria", [_crit("trigger_break")]),
         "facts": {"flush_depth_pct": kw.get("depth"), "touch_bar_t": kw.get("touch"), "below_21": False,
                   "confluence_n": 1, "confluence_text": "1 of his levels touched today: 9 EMA · " + DT.CONFLUENCE_TAIL,
                   "window_text": "his candle window: 1-minute candles to 09:45 ET, then 5-minute to 10:30 ET",
                   "frame_text": "5-minute candle"},
         "listed_why": kw.get("listed_why")}
    if state == "none":
        r["reason"] = "no flush into the hourly 9 EMA today"
    return r


def _bars():
    return [{"t": f"2026-11-03 {h}", "o": 12.0, "h": 12.5, "l": 11.9, "c": 12.3, "v": 1000}
            for h in ("09:35", "09:40", "09:45", "09:50")]


def _read_doc(sym, setups, **kw):
    return {"_id": f"{S.isoformat()}|{sym}", "date": S.isoformat(), "symbol": sym, "at": PASS_AT,
            "updated_at": PASS_AT, "as_of_bar_t5": "2026-11-03 10:10", "setups": setups,
            "facts": {"adr20_pct": kw.get("adr", 6.2), "tier": kw.get("tier", "lead")},
            "tile": {"bars5": _bars(), "curves5": [], "vol_avg5": None},
            "screens_rank": kw.get("rank", {}), "tier": kw.get("tier", "lead"), "cap_text": kw.get("cap_text", "$1.2B")}


WIDE_WHY = "stop too wide by his rule — 6.2% > 5% of the trigger"


def _reads():
    pr, orh, idp = LC.SETUPS
    return [
        _read_doc("AAA", {
            pr: _read(pr, "aplus", frame="1m", trigger=12.40, stop=11.98, risk_pct=3.39, r_usd=0.42, lod=11.98,
                      entry_bar_t="2026-11-03 09:42", depth=1.3, touch="2026-11-03 09:40"),
            orh: _read(orh, "forming", trigger=12.60, stop=11.98, risk_pct=4.9, r_usd=0.62),
            idp: _read(idp, "none")}, rank={"premarket": 1, "potent": 3}),
        _read_doc("BBB", {
            pr: _read(pr, "listed", trigger=20.0, stop=19.2, risk_pct=4.0, r_usd=0.8, lod=19.2,
                      entry_bar_t="2026-11-03 09:50", listed_why=DT.chase_why(), touch="2026-11-03 09:45"),
            orh: _read(orh, "listed", trigger=20.5, stop=19.6, risk_pct=4.4, r_usd=0.9,
                       entry_bar_t="2026-11-03 10:35", listed_why=DT.window_why()),
            idp: _read(idp, "none")}, adr=3.1, tier="mediocre", cap_text=SC.CAP_UNKNOWN_TEXT),
        _read_doc("CCC", {
            pr: _read(pr, "listed", trigger=50.0, stop=46.9, risk_pct=6.2, r_usd=3.1, lod=45.0,
                      stop_src=DT.SRC_ENTRY_5M, entry_bar_t="2026-11-03 09:55", listed_why=WIDE_WHY),
            orh: _read(orh, "stopped", frame="1m", trigger=51.0, stop=50.1, risk_pct=1.8, r_usd=0.9,
                       entry_bar_t="2026-11-03 09:33"),
            idp: _read(idp, "triggered", trigger=49.0, stop=48.0, risk_pct=2.0, r_usd=1.0,
                       entry_bar_t="2026-11-03 09:45")}),
        _read_doc("DDD", {s: _read(s, "none") for s in LC.SETUPS}),
    ]


def _screen_row(sym, rank, cap, **kw):
    r = {"symbol": sym, "rank": rank, "price": kw.get("price", 12.3), "pm_chg_pct": kw.get("pm", 4.2),
         "chg_pct": kw.get("chg", 3.3), "perf_1m_pct": kw.get("perf", 21.0), "chg_from_open_pct": 1.1,
         "cap": cap, "cap_text": SC.money(cap) if cap is not None else SC.CAP_UNKNOWN_TEXT,
         "avg_vol_10d": 2_400_000, "px_vol": 80_000_000, "px_vol_1w": 400_000_000, "vol_1w_pct": 5.1,
         "adr20_pct": 6.2, "tier": "lead", "tier_text": "Lead — 9 EMA > 21 EMA > 50 EMA",
         "small_cap_text": None, "pending_text": None}
    r["criteria"] = SC.criteria("premarket", r)
    return r


def _screens_doc():
    return {"_id": S.isoformat(), "date": S.isoformat(), "at": PASS_AT,
            "premarket": [_screen_row("AAA", 1, 1_200_000_000), _screen_row("EEE", 2, None)],
            "leader": [_screen_row("FFF", 1, 9_000_000_000)],
            "potent": [_screen_row("GGG", 1, 300_000_000), _screen_row("AAA", 2, 1_200_000_000),
                       _screen_row("BBB", 3, None)],
            "counts": {"premarket_n": 2, "leader_n": 1, "potent_n": 3, "screened_n": 1200, "not_screened_n": 37}}


def _pass_body():
    return {"ran": True, "dry": False, "errors": [], "n_read": 4, "status": "ok", "wall_s": 41.2,
            "screens": {"premarket_n": 2, "leader_n": 1, "potent_n": 3, "screened_n": 1200, "not_screened_n": 37},
            "shortlist": {"n": 6, "capped_n": 0, "symbols": ["AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]},
            "bars_through": {"t1_et": "10:10", "t5_et": "10:10"},
            "market_state": MS.block({"QQQ": {"ema9": 500.0, "ema21": 495.0, "close": 505.0},
                                      "IWM": {"ema9": 210.0, "ema21": 212.0, "close": 208.0}}),
            "calls": {"snapshot": 1, "daily_fetch": 3, "minute_today": 6, "minute_prior": 12, "index": 2, "caps": 1}}


def _alert(sym, setup, trigger, stop):
    return {"_id": GA.shadow_key(S, sym, setup, LUK), "state": "shadow", "symbol": sym, "setup": setup,
            "date": S.isoformat(), "at": datetime(2026, 11, 3, 14, 47, tzinfo=timezone.utc).isoformat(),
            "trigger": trigger, "stop": stop}


def fixture_store(*, reads=True, screens=True, passes=True, alerts=True) -> LS.LukStore:
    colls = {n: FakeColl() for n in LS.LOGICAL}
    colls[LS.SCREENS_KEY] = FakeColl()
    st = LS.LukStore(colls=colls)
    if passes:
        st.record_pass(S, PASS_AT, _pass_body())
    if reads:
        for d in _reads():
            colls[GS_READS()].docs[d["_id"]] = d
    if screens:
        d = _screens_doc()
        colls[LS.SCREENS_KEY].docs[d["_id"]] = d
    if alerts:
        a = _alert("AAA", "pullback_reversal", 12.40, 11.98)
        st.alerts_coll().docs[a["_id"]] = a
    return st


def GS_READS():
    from chart_maps.gajjala import store as GS
    return GS.READS


def _build(sub="", **kw):
    st = kw.pop("store", None) or fixture_store()
    return T.build(sub, now=NOW, store=st, **kw)


def _walk(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for v in o.values():
            yield from _walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from _walk(v)


def _tile(out, sym):
    return next(t for t in out["tiles"] if t["symbol"] == sym)


# ── the payload ────────────────────────────────────────────────────────────────────────────────────────────────────
def test_payload_keys_and_the_variant_block():
    out = _build()
    assert set(out) == set(T.PAYLOAD_KEYS)
    assert out["tab"] == LC.LUK_TAB == "luk" and out["label"] == LC.LUK_TAB_LABEL
    v = out["variant"]
    assert v == {"key": "luk", "tab": "luk", "label": LC.LUK_TAB_LABEL, "api_base": "/chart-maps/luk",
                 "record_from": LC.LUK_RECORD_FROM, "push_mode": "live", "tfs": ["1m", "5m", "60m"],
                 "primary": "5m"}                         # FLIPPED 2026-11-01: "Lets make it live. also alerts too."
    assert out["fault"] is False and out["fault_text"] is None


def test_NEGATIVE_the_variant_block_follows_the_patched_shadow_fallback(monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    assert _build()["variant"]["push_mode"] == "shadow"
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "LIVE")                    # junk → shadow (fail closed)
    assert T.variant_block()["push_mode"] == "shadow"


def test_title_and_honesty_are_the_spec_words_verbatim():
    out = _build()
    assert out["title"] == ("🥇 Luk's — Martin Luk's published pullback / opening-range method, built from his own "
                            "words · UNMEASURED")
    # FLIPPED 2026-11-01 (go-live): the one mode sentence quotes LUK_LIVE_WORDS by name
    assert out["honesty"] == (
        "2025 US Investing Championship winner (+969.8%, $20k+ stock division; 2026 leader +785.8% through Sep 30). He "
        "sells nothing; every rule here is his own words in free sources, cited line by line on the 📓 Playbook; his "
        "selling and exposure are discretionary by his own admission, so what is computed here is the entry, the stop "
        "and one exit he stated. Every alert here rings your phone since " + LC.LUK_LIVE_SINCE + " by your call (\""
        + LC.LUK_LIVE_WORDS + "\"). Nothing here is measured, trades, sizes or enters a lane.")
    assert "never sent" not in out["honesty"]                          # NEGATIVE: false while live
    assert T.fault_payload()["honesty"] == out["honesty"]


def test_the_shadow_twin_of_the_honesty_line(monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    out = _build()
    assert out["honesty"] == (
        "2025 US Investing Championship winner (+969.8%, $20k+ stock division; 2026 leader +785.8% through Sep 30). He "
        "sells nothing; every rule here is his own words in free sources, cited line by line on the 📓 Playbook; his "
        "selling and exposure are discretionary by his own admission, so what is computed here is the entry, the stop "
        "and one exit he stated. Every alert is recorded in shadow, never sent. Nothing here is measured, trades, "
        "sizes or enters a lane.")
    assert LC.LUK_LIVE_WORDS not in out["honesty"] and "rings" not in out["honesty"]
    assert T.fault_payload()["honesty"] == out["honesty"]


def test_every_served_text_is_non_empty_for_the_fixture_store():
    out = _build()
    must = [out["title"], out["honesty"], out["counts_text"], out["order_note"], out["pass"]["text"],
            out["pass"]["latency_text"], out["session"]["label"], out["session"]["badge"]]
    must += [out["strip"][k] for k in ("push_text", "record_text", "external_text", "cost_text", "latency_text")]
    must += [r["text"] for r in out["strip"]["market_state"]["rows"]] + [out["strip"]["market_state"]["note"]]
    must += [s["title"] for s in out["subs"]] + [s["label"] for s in out["subs"]]
    must += [x["text"] for x in out["counts_legend"]] + [x["word"] for x in out["counts_legend"]]
    for t in out["tiles"]:
        must += [t["state_label"], t["trigger_text"], t["frame_text"] or "5-minute", t["read_at_text"]]
        must += [v for v in t["chips"].values() if v is not None]
    for key in T.SCREEN_SUBS:
        sc = _build(key)["screens"]
        must += [sc["title"], sc["sorted_by_text"], sc["not_screened_text"], sc["considerations_text"], sc["honesty"]]
        must += [h["label"] for h in sc["heads"]]
    tr = _build(T.TRACK_SUB)["track_record"]
    must += [tr["title"], tr["rule_text"], tr["honesty"], tr["counts_text"]]
    pb = _build(T.PLAYBOOK_SUB)["playbook"]
    must += [pb["title"]] + [s["title"] for s in pb["sections"]]
    bad = [m for m in must if not (isinstance(m, str) and m.strip())]
    assert bad == []


# ── numbers: every number in a template is a constants name ───────────────────────────────────────────────────────
def _allowed_numbers() -> set:
    allowed = set()
    for mod in (LC, GC):
        for name in dir(mod):
            if name.startswith("_"):
                continue
            v = getattr(mod, name)
            vals = v if isinstance(v, (tuple, list, frozenset, set)) else (v,)
            for x in vals:
                if isinstance(x, (int, float)) and not isinstance(x, bool):
                    allowed |= {"%g" % x, "%d" % x if float(x).is_integer() else "%g" % x, "%.2f" % x, "%.1f" % x,
                                "{:,}".format(int(x)), "%g" % (x * 100)}
                elif isinstance(x, str):
                    allowed |= set(re.findall(r"\d{1,2}:\d{2}|\d+(?:\.\d+)?", x))
    allowed |= {"%g" % (V.cadence_sec(LUK) / 60), "%g" % GC.BAR_SETTLE_SEC}
    allowed |= {str(V.frame_minutes(tf, LUK)) for tf in LUK.tfs}
    allowed |= {"%g" % LC.MEASURE_FLOOR_WEEKS}
    return allowed


CITE = re.compile(r"\b[A-Za-z0-9_-]{11} \d{1,2}:\d{2}(?::\d{2})?(?:[–-]\d{1,2}:\d{2}(?::\d{2})?)?|HIS CALL #\d+")


def _numbers(text: str) -> list:
    """The numbers of a served line, its source cites stripped ("VKNEJA5r8zw 2:29:17", "HIS CALL #29" are
    references, not numbers)."""
    text = CITE.sub("", text)
    return re.findall(r"\d{1,2}:\d{2}|\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?", text)


def test_every_number_in_the_text_is_a_constant_value():
    """counts_text / rule_text / the pass and strip lines: each number is a constants value or a count the fixture
    put there (never a typed literal)."""
    out = _build()
    tr = _build(T.TRACK_SUB)["track_record"]
    c = out["counts"]
    data = {str(v) for v in c.values() if isinstance(v, int)} | {str(v) for v in tr["counts"].values()
                                                                    if isinstance(v, int)}
    data |= {"10:11", "10:10", "4", "6", "1200", "37", "1", "3", "12", "2"}            # the fixture pass doc's values
    # WIDENED 2026-11-02 (🏁 like 🚩's): the served charts block's counts and every chart cell's numbers are counts too
    ch = tr.get("charts") or {}
    data |= {str(v) for c in (ch.get("counts") or {}).values() for v in c.values() if isinstance(v, int)}
    for chart in ch.get("charts") or []:
        for cell in (chart.get("bars") or []) + [g.get("exit") for g in (chart.get("rows") or [])
                                                 + (chart.get("cols") or [])]:
            data |= {str(cell[k]) for k in ("pct", "decided", "total", "loss_pct")
                     if isinstance((cell or {}).get(k), int)}
    allowed = _allowed_numbers() | data
    for text in (out["counts_text"], tr["rule_text"], tr["counts_text"], out["pass"]["text"],
                 out["pass"]["latency_text"], out["strip"]["cost_text"], out["strip"]["record_text"]):
        bad = [n for n in _numbers(text) if n not in allowed]
        assert bad == [], (text, bad)


def test_NEGATIVE_no_template_types_a_digit_outside_its_fields():
    """The templates themselves carry no number: every digit lives inside a {field} filled from a constant / count."""
    fmt = string.Formatter()
    for name in ("COUNTS_TEXT", "PASS_TEXT", "PASS_NONE_TEXT", "LATENCY_TEXT", "COST_TEXT", "COST_LAST_TEXT",
                 "RECORD_TEXT", "NOT_SCREENED_TEXT", "STOP_TEXT", "STOP_SWITCH_TAIL", "ADR_OVER_TEXT",
                 "ADR_UNDER_TEXT", "FLUSH_TEXT", "FLUSH_NONE_TEXT", "FLUSH_TOUCH_TEXT", "READ_AT_TEXT",
                 "TRIGGER_TEXT", "TRIGGER_BROKE_TEXT", "LEVEL_TEXT",
                 "NOT_REREAD_TEXT", "REREAD_ORDER_TEXT", "STATE_ORDER_TEXT", "ORDER_NOTE"):   # + 2026-11-11
        tpl = getattr(T, name)
        literal = "".join(lit for lit, _f, _s, _c in fmt.parse(tpl))
        assert not re.search(r"\d", literal), (name, literal)


def test_the_latency_fact_is_served_from_the_cadence():
    out = _build()
    cad = V.cadence_sec(LUK) // 60
    want = (f"a 1-minute trigger is read on the next {cad}-minute pass — up to {cad} minutes after its bar closed — "
            "and still rings when no later bar touched the stop")
    assert out["pass"]["latency_text"] == want == out["strip"]["latency_text"] == T.latency_text()


def test_the_pass_line_reads_the_session_pass_doc():
    out = _build()
    assert out["pass"]["text"] == ("pass 10:11 ET · bars through 10:10 · 4 read of 6 shortlisted · 1200 screened · 37 "
                                   "not screened yet")
    assert out["pass"]["bars_through_et"] == "10:10" and out["pass"]["wall_s"] == pytest.approx(41.2)
    assert out["pass"]["stale"] is False


# ── words ──────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("sub", list(T.SUB_KEYS))
def test_NEGATIVE_no_b_word_and_no_edge_anywhere_in_the_payload(sub):
    out = _build(sub)
    bad = [s for s in _walk(out) if BWORD.search(s) or EDGE.search(s)]
    assert bad == []


def test_NEGATIVE_the_word_guard_catches_a_planted_word(monkeypatch):
    monkeypatch.setattr(T, "ORDER_NOTE", "the edge comes first")
    assert any(EDGE.search(s) for s in _walk(_build()))


def test_NEGATIVE_ggs_first_fifteen_minutes_quote_is_never_served():
    out = _build()
    assert "first15" not in out["session"] and "first15_text" not in out["session"]
    assert not any("doesn't trade it" in s for s in _walk(out))


# ── the sub ────────────────────────────────────────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw", ["", "nope", "bull_flag", "PLAYBOOKS", None])
def test_an_unknown_or_empty_sub_serves_the_default(raw):
    assert _build(raw)["sub"] == LC.DEFAULT_SUB == "pullback_reversal"


@pytest.mark.parametrize("key", list(T.SUB_KEYS))
def test_every_known_sub_is_served_as_asked(key):
    assert _build(key)["sub"] == key
    assert _build(key.upper())["sub"] == key


def test_focus_picks_the_sub_of_the_best_card():
    assert _build("", focus="ccc")["sub"] == "inside_day_pdh"                 # triggered beats listed and stopped
    assert _build("", focus="AAA")["sub"] == "pullback_reversal"              # A+
    assert _build("", focus="FFF")["sub"] == "leader"                         # a screen-only name
    assert _build("", focus="ZZZ")["sub"] == LC.DEFAULT_SUB
    assert _build("potent", focus="CCC")["sub"] == "potent"                   # NEGATIVE: an asked sub wins


def test_the_focused_card_comes_first_and_is_never_cut():
    out = _build("pullback_reversal", focus="CCC", limit=1)
    assert [t["symbol"] for t in out["tiles"]] == ["CCC"]
    assert out["focus"] == "CCC"


def test_subs_are_the_eight_in_order_and_n_equals_the_rows():
    subs = _build()["subs"]
    assert [(s["key"], s["emoji"], s["label"]) for s in subs] == [tuple(x) for x in LC.SUBS]
    n = {s["key"]: s["n"] for s in subs}
    for k in T.SETUP_SUBS:
        assert n[k] == len(_build(k)["tiles"]), k
    for k in T.SCREEN_SUBS:
        assert n[k] == len(_build(k)["screens"]["rows"]), k
    pb = _build(T.PLAYBOOK_SUB)["playbook"]
    assert n[T.PLAYBOOK_SUB] == sum(len(s["items"]) for s in pb["sections"]) == len(PB.all_items()) > 0
    tr = _build(T.TRACK_SUB)["track_record"]
    # RESTATED 2026-11-02 (🏁 like 🚩's, spec §3.3.6): n_rows = the rows ON THE SPAN (== counts.n; == the rows listed
    # under the LUK_LEDGER_ROWS_MAX cap — this fixture is under it)
    assert n[T.TRACK_SUB] == tr["n_rows"] == tr["counts"]["n"] == sum(len(d["rows"]) for d in tr["days"]) == 1
    assert tr["more_text"] is None
    assert n == {"pullback_reversal": 3, "opening_range_high": 3, "inside_day_pdh": 1, "premarket": 2, "leader": 1,
                 "potent": 3, "playbook": n[T.PLAYBOOK_SUB], "track_record": 1}


def test_only_the_asked_subs_body_is_served():
    out = _build("premarket")
    assert out["tiles"] == [] and out["playbook"] is None and out["track_record"] is None
    assert out["screens"]["key"] == "premarket"
    out = _build(T.PLAYBOOK_SUB)
    assert out["screens"] is None and out["tiles"] == [] and out["playbook"]["title"] == PB.TITLE
    out = _build(T.TRACK_SUB, span="all")
    assert out["track_record"]["span"] == "all" and out["screens"] is None
    assert _build(T.TRACK_SUB, span="bogus")["track_record"]["span"] == LC.LUK_LEDGER_SPAN_DEFAULT


# ── the cards ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_cards_follow_the_served_order():
    out = _build("pullback_reversal")
    assert [(t["symbol"], t["state"]) for t in out["tiles"]] == [("AAA", "aplus"), ("CCC", "listed"),
                                                                  ("BBB", "listed")]   # listed: newest break first
    o2 = _build("opening_range_high")
    assert [t["state"] for t in o2["tiles"]] == ["forming", "listed", "stopped"]
    assert out["order_note"] == T.ORDER_NOTE


def test_NEGATIVE_a_none_read_is_never_carded():
    for k in T.SETUP_SUBS:
        out = _build(k)
        assert "DDD" not in {t["symbol"] for t in out["tiles"]}
        assert all(t["state"] in T.TILE_STATES for t in out["tiles"])
    assert all(t["symbol"] != "AAA" for t in _build("inside_day_pdh")["tiles"])     # AAA's inside-day read is none


def test_NEGATIVE_a_listed_card_keeps_trigger_stop_and_r():
    out = _build("pullback_reversal")
    bbb, ccc = _tile(out, "BBB"), _tile(out, "CCC")
    assert bbb["state"] == "listed" and bbb["listed_why"] == DT.chase_why()
    assert bbb["state_label"] == "listed — " + DT.chase_why()
    assert bbb["trigger"] == 20.0 and bbb["stop"] == 19.2 and bbb["r_usd"] == pytest.approx(0.8)
    assert bbb["trigger_text"] == "trigger 20.00 · broke on the 5-minute candle closing 09:50 ET"
    assert bbb["stop_text"] == "stop 19.20 (−4.0%) · R $0.80"
    assert ccc["listed_why"] == WIDE_WHY and ccc["stop_text"].startswith("stop 46.90 (−6.2%) · R $3.10")
    assert ccc["stop_text"].endswith(" · stop = the 5-minute entry candle low (entry-to-LOD > 5%)")
    assert any(ln["tone"] == "stop" for ln in ccc["lines"]) and any(ln["tone"] == "buy" for ln in ccc["lines"])


def test_the_aplus_card_in_words_and_the_tile_shape_patternchart_draws():
    a = _tile(_build(), "AAA")
    assert a["state_label"] == "A+ — every rule met, the trigger bar traded through and closed"
    assert a["frame_text"] == "1-minute candle"
    assert a["trigger_text"] == "trigger 12.40 · broke on the 1-minute candle closing 09:42 ET"
    assert a["stop_text"] == "stop 11.98 (−3.4%) · R $0.42"
    assert a["href"].startswith("/sepa/AAA")
    for k in ("symbol", "href", "tf", "bars", "curves", "vol_avg", "lines", "markers", "bands", "badges", "stats"):
        assert k in a, k
    assert a["bars"] == a["bars5"] and len(a["bars"]) == 4 and a["tf"] == "5m"
    assert a["gajjala"] == {"setup": "pullback_reversal", "state": "aplus"}
    assert a["markers"] == []                                              # a 1-minute stamp has no 5-minute bar
    ch = a["chips"]
    assert ch["tier_text"] == "Lead — 9 EMA > 21 EMA > 50 EMA"
    assert ch["adr_text"] == ">5% ADR (6.2%) — his preference, not a hard rule"
    assert ch["flush_text"] == "flushed 1.3% below the hourly 9 EMA at 09:40"
    assert ch["screens_text"] == "☀️ #1 · ⚡ #3"
    assert ch["cap_text"] == "$1.2B" and ch["small_cap_text"] == "small cap (<$5B) — his second list"
    assert a["read_at_text"] == "read at 10:11 ET"
    assert a["criteria"][0] == {"key": "trigger_break", "label": "trigger break", "ok": True,
                                "value": "trigger_break value", "need": "trigger_break need"}


def test_the_marker_sits_on_a_served_five_minute_bar():
    ccc = _tile(_build("inside_day_pdh"), "CCC")
    assert ccc["markers"] == [{"date": "2026-11-03 09:45", "kind": "buy", "label": "A+"}]


def test_forming_and_the_adr_under_preference_words():
    f = _tile(_build("opening_range_high"), "AAA")
    assert f["state_label"] == "forming — trigger 12.60 armed" and f["trigger_text"] == "trigger 12.60"
    assert f["chips"]["flush_text"] is None                               # the flush is the pullback's fact only
    b = _tile(_build("pullback_reversal"), "BBB")
    assert b["chips"]["adr_text"] == "ADR 3.1% — under his 5% preference (not a rule)"
    assert b["chips"]["cap_text"] == SC.CAP_UNKNOWN_TEXT and b["chips"]["small_cap_text"] is None
    assert b["chips"]["flush_text"] == "touched the hourly 9 EMA at 09:45"


# ── counts ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_counts_and_the_listing_split():
    out = _build()
    c = out["counts"]
    assert c == {"aplus": 1, "triggered": 1, "forming": 1, "listed": 3, "stopped": 1, "none": 5,
                 "listed_chase": 1, "listed_stop_wide": 1, "listed_window": 1, "screened": 1200, "shortlist": 6}
    assert out["counts_text"] == ("1 A+ · 1 triggered earlier · 1 forming · 3 listed · 1 stopped — over 6 shortlisted "
                                  "of 1200 screened")
    assert [x["key"] for x in out["counts_legend"]] == list(T.COUNT_STATES)


# ── the strip ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_strip_is_folded_and_carries_the_index_words():
    s = _build()["strip"]
    assert s["folded"] is True
    rows = {r["symbol"]: r for r in s["market_state"]["rows"]}
    assert list(rows) == list(LC.LUK_INDEX_SYMBOLS)
    assert rows["QQQ"]["text"] == MS.WORD_OVER.format(sym="QQQ")
    assert rows["IWM"]["text"] == MS.WORD_UNDER.format(sym="IWM")
    # FLIPPED 2026-11-01 (go-live): the push line quotes him by name and serves the cadence fact, never a typed number
    assert s["push_text"] == T.push_text()
    assert LC.LUK_LIVE_SINCE in s["push_text"] and f'("{LC.LUK_LIVE_WORDS}")' in s["push_text"]
    assert "UNMEASURED" in s["push_text"] and f"up to {T._cad_min()} minutes" in s["push_text"]
    assert s["push_text"].startswith("📲 Every 🥇 A+ rings your phone since ")
    assert "never sent" not in s["push_text"] and "{" not in s["push_text"]          # NEGATIVE: false while live
    assert s["latency_text"] == T.latency_text()                                      # the tab keeps the latency fact
    assert LC.LUK_RECORD_FROM in s["record_text"] and "EXTERNAL, not re-run here" in s["external_text"]
    assert s["cost_text"].endswith(" Last pass: snapshot 1 · daily 3 · minute today 6 · minute prior 12 · index 2 · "
                                   "caps 1.")


# ── screens ────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_screen_block_rows_in_served_order_with_the_cap_unknown_row():
    sc = _build("premarket")["screens"]
    assert sc["title"] == SC.title("premarket") and sc["sorted_by_text"] == "sorted by pre-market % change"
    assert [r["symbol"] for r in sc["rows"]] == ["AAA", "EEE"] and [r["rank"] for r in sc["rows"]] == [1, 2]
    eee = sc["rows"][1]
    assert eee["cap_text"] == SC.CAP_UNKNOWN_TEXT == "cap unknown — not filtered"
    cap = next(c for c in eee["criteria"] if c["key"] == "cap")
    assert cap == {"key": "cap", "label": "Market cap", "ok": None, "value": None, "need": SC.CAP_UNKNOWN_TEXT}
    assert all(set(c) == {"key", "label", "ok", "value", "need"} for r in sc["rows"] for c in r["criteria"])
    assert sc["considerations_text"] == ("He is considering a $100M dollar-volume floor and filtering biotechs and "
                                         "buyouts/mergers out (iMBI3ZcQ6sU 1:17:58–1:18:43) — listed, not applied: "
                                         "HIS CALL")
    assert sc["not_screened_text"].startswith("37 names not screened yet")
    assert [h["key"] for h in sc["heads"]][:4] == ["rank", "symbol", "price_text", "pm_chg_text"]


# ── empty and faulty stores ────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_an_empty_store_serves_the_zero_board():
    st = fixture_store(reads=False, screens=False, passes=False, alerts=False)
    out = T.build("", now=NOW, store=st)
    assert out["tiles"] == [] and all(s["n"] == 0 for s in out["subs"] if s["key"] != T.PLAYBOOK_SUB)
    assert out["pass"]["text"] == T.PASS_NONE_TEXT.format(cad=V.cadence_sec(LUK) // 60, open=LC.LUK_PASS_OPEN_ET,
                                                          close=LC.LUK_PASS_CLOSE_ET)
    assert all(r["text"] == MS.WORD_NONE.format(sym=r["symbol"]) for r in out["strip"]["market_state"]["rows"])
    assert "Last pass" not in out["strip"]["cost_text"]
    assert out["counts"]["aplus"] == 0 and out["counts_text"].startswith("0 A+")
    sc = T.build("leader", now=NOW, store=st)["screens"]
    assert sc["rows"] == [] and sc["not_screened_text"] == T.NOT_SCREENED_NONE_TEXT


def test_NEGATIVE_a_raising_block_never_takes_the_board_down(monkeypatch):
    st = fixture_store()
    monkeypatch.setattr(st, "reads", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("mongo down")))
    monkeypatch.setattr(LG, "served_block", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = T.build(T.TRACK_SUB, now=NOW, store=st)
    assert out["fault"] is False and out["tiles"] == [] and out["track_record"] is None
    assert {s["key"]: s["n"] for s in out["subs"]}[T.TRACK_SUB] == 0


def test_a_previous_session_pass_is_not_this_sessions_line():
    st = fixture_store()
    out = T.build("", now=datetime(2026, 11, 4, 15, 0, tzinfo=timezone.utc), store=st)   # next day, no pass yet
    assert out["session"]["date"] == "2026-11-04"
    assert out["pass"]["text"].startswith("no 🥇 pass on file")
    assert out["tiles"] == []                                                # yesterday's reads are not today's


def test_fault_payload_shape():
    f = T.fault_payload("nope")
    assert set(f) == set(T.PAYLOAD_KEYS) and f["fault"] is True and f["fault_text"] == T.FAULT_TEXT
    assert f["sub"] == LC.DEFAULT_SUB and T.fault_payload("leader")["sub"] == "leader"


# ── the golden ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _golden_text() -> str:
    out = {"default": _build(), "premarket": _build("premarket"), "track_record": _build(T.TRACK_SUB, span="all")}
    return json.dumps(out, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def test_golden_board():
    text = _golden_text()
    if os.environ.get("LUK_WRITE_GOLDEN") == "1":
        GOLDEN.parent.mkdir(parents=True, exist_ok=True)
        GOLDEN.write_text(text, encoding="utf-8")
    assert GOLDEN.exists(), "missing golden — see the module docstring for the regen command"
    assert GOLDEN.read_text(encoding="utf-8") == text


# ── 2026-11-01 refix: the click target is the house one (chart_maps.board._href), never a parallel spelling ─────────
def test_tile_and_screen_row_href_is_the_house_supply_tab_link():
    from chart_maps import board as board_mod
    a = _tile(_build(), "AAA")
    assert a["href"] == board_mod._href("AAA") == "/sepa/AAA?tab=supply"
    row = T.screen_row(_screen_row("aaa", 1, 1_200_000_000))
    assert row["symbol"] == "AAA" and row["href"] == board_mod._href("AAA") == "/sepa/AAA?tab=supply"


def test_NEGATIVE_no_luk_href_is_bare_or_lowercase():
    out = _build()
    hrefs = [t["href"] for t in out["tiles"]]
    for key in ("premarket", "leader", "potent"):
        hrefs += [r["href"] for r in (_build(key)["screens"] or {}).get("rows") or []]
    assert hrefs, "the fixture serves tiles and screen rows"
    for h in hrefs:
        sym = h.split("/sepa/", 1)[1].split("?", 1)[0]
        assert h == f"/sepa/{sym}?tab=supply" and sym == sym.upper(), h


# ── 2026-11-01 go-live (Ajay: "Lets make it live. also alerts too.") — the shadow twin of the push line ───────────────
def test_the_shadow_twin_of_the_push_line(monkeypatch):
    monkeypatch.setattr(LC, "LUK_PUSH_MODE", "shadow")
    s = _build()["strip"]
    assert s["push_text"] == T.PUSH_TEXT_SHADOW == "📵 Every 🥇 A+ is recorded in shadow, never sent, until you say so. UNMEASURED."
    assert "rings" not in s["push_text"] and LC.LUK_LIVE_WORDS not in s["push_text"]


def test_NEGATIVE_the_shadow_line_never_claims_no_kind_or_no_sender():
    """The old "no push kind, no sender, keep-set unchanged" clause is false after the go-live even in shadow."""
    for t in (T.PUSH_TEXT_SHADOW, T.PUSH_TEXT_LIVE, T.HONESTY_SHADOW, T.HONESTY_LIVE):
        assert "no push kind" not in t and "no sender" not in t and "keep-set is unchanged" not in t


def test_NEGATIVE_the_push_line_types_no_number_but_the_served_cadence():
    live = T.PUSH_TEXT_LIVE.replace("1-minute trigger", "")                # the frame's name, not a number
    nums = set(re.findall(r"\d+", live)) | set(re.findall(r"\d+", T.PUSH_TEXT_SHADOW))
    assert nums == set()                                                    # every number is a {name}
    assert str(T._cad_min()) == str(V.cadence_sec(LUK) // 60)
