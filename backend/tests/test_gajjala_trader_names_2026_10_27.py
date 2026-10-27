"""📌 Trader names on 🚩 Gajjala's list — chart_maps/gajjala/trader_names.py + its seams (BUILD_SPEC26 §3.3, §4 WP-B, §8 A2).

Ajay 2026-10-27, verbatim: "Can you track this guy please? and his tickers" (stocktwits.com/algo888), then "Add them to
Gajjals, they are pretty good". His fresh, snapshot-resolvable names join the pass's candidate list AFTER his scanner
(scan_rows — byte-identical, never the word "trader") and BEFORE the hold-out + scan write; GG's change and volume
floors are waived for the add only (HIS CALL #1); GG's 1M floor stays on EVERY push (A2 — the 🧠 push is HELD under it,
the A+ is K11). The REAL scanner, bars and detectors run on fixture data (tests/test_gajjala_run.py's helpers); the
StockTwits page is the real 2026-10-27 fixture (tests/fixtures/stocktwits_user_algo888_2026_10_27.json) — never fetched.
NEGATIVES are mandatory and named so. UNMEASURED: nothing here claims an edge.
"""
from __future__ import annotations

import ast
import inspect
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import trader_names as TN
from tests.test_gajjala_run import (PREV, PRIOR_1M, Rec, S, at, make_deps, minutes_from_5m, snap_row)
from tests.test_gajjala_store import FakeColl, fake_store
from tests.fixtures.gajjala import detector_frames as FX

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
FIXTURE = Path(__file__).resolve().parent / "fixtures" / "stocktwits_user_algo888_2026_10_27.json"
B_WORD = re.compile("b" + "ounc", re.I)
KEY = "algo888"                                     # the flagged registry row (traders/registry.py, §3.1)
NOW = at(10, 41)
POST_AT = at(8, 30).astimezone(UTC).isoformat()     # "his posts at 08:30 ET S" (the worked example)
TYPES = {"GPUS": "CS", "MXCT": "CS", "TQQQ": "ETF", "BIGC": "CS", "STALE": "CS", "GGA": "CS", "ZZZ": "CS"}
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}


def post(*tags, at_=POST_AT, pid="st1", text="his post"):
    return {"id": pid, "text": text, "created_at": at_, "cashtags": list(tags), "source": "stocktwits"}


def worked_rows(**extra):
    """§3.3 worked example (S 2026-10-13, 10:41 ET): GPUS a GG qualifier, MXCT under both floors, TQQQ an ETF, BIGC
    over the band, STALE printed last session, NOPE absent."""
    rows = {"GPUS": snap_row(0.19, 0.15, vol=40_000_000), "MXCT": snap_row(2.10, 2.00, vol=300_000),
            "TQQQ": snap_row(80.0, 79.0), "BIGC": snap_row(150.0, 140.0),
            "STALE": snap_row(1.0, 0.9, when=at(10, 40, d=PREV))}
    rows.update(extra)
    return rows


WORKED_POSTS = [post("GPUS", "MXCT", "NOPE", "TQQQ", "BIGC", "STALE")]


def deps_for(rows, posts=None, *, fetch=None, http=200, load=None):
    d, snap, send, status = make_deps(rows=rows, http=http, load=load)
    d.fetch_types = lambda: (dict(TYPES), True, 1)
    d.trader_posts = Rec(lambda key: list(posts if posts is not None else WORKED_POSTS) if key == KEY else [])
    d.trader_fetch = fetch
    return d, snap, send, status


# ── the registry shape this package codes against (§3.1) ──────────────────────────────────────────────────────────
def test_flagged_reads_only_the_gajjala_true_rows():
    keys = [t["key"] for t in TN.flagged()]
    assert keys == [KEY]
    assert all(t.get("gajjala") is True for t in TN.flagged())
    assert TN.text_for(KEY) == f"{GC.TRADER_TAG} algo888"
    assert TN.text_for("nobody") == f"{GC.TRADER_TAG} nobody"                 # an unknown key prints the key
    assert TN.text_for(None) is None and TN.text_for("") is None              # NEGATIVE: no key, no tag


# ── names_for ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _real_posts():
    from traders import feed
    msgs = json.loads(FIXTURE.read_text(encoding="utf-8"))["messages"]
    return feed.parse_stocktwits(msgs, KEY)


def test_the_real_fixture_on_10_27_gives_mxct_then_gpus():
    now = datetime(2026, 10, 27, 10, 0, tzinfo=ET)
    names, over = TN.names_for(now, date(2026, 10, 27), {KEY: _real_posts()})
    assert [n["symbol"] for n in names] == ["MXCT", "GPUS"] and over == []
    assert names[0]["post_id"] == "st667436630" and names[0]["trader"] == KEY      # his newest $MXCT, 09:56 ET
    assert names[1]["post_id"] == "st667435290"                                    # his newest $GPUS, 09:48 ET
    assert names[0]["at"].endswith("+00:00") and names[0]["at"].startswith("2026-10-27T13:56:49")


def test_NEGATIVE_two_sessions_later_nothing_is_fresh():
    posts = {KEY: _real_posts()}
    nxt, _ = TN.names_for(datetime(2026, 10, 28, 10, 0, tzinfo=ET), date(2026, 10, 28), posts)
    assert [n["symbol"] for n in nxt] == ["MXCT", "GPUS"]                 # the previous session still counts
    names, over = TN.names_for(datetime(2026, 10, 29, 10, 0, tzinfo=ET), date(2026, 10, 29), posts)
    assert names == [] and over == []


def test_a_saturday_post_counts_for_monday():
    sat = datetime(2026, 10, 24, 11, 0, tzinfo=ET).astimezone(UTC).isoformat()
    mon = date(2026, 10, 26)
    assert TN.window_start(mon) == datetime(2026, 10, 23, 0, 0, tzinfo=ET)       # 00:00 ET of Friday
    names, _ = TN.names_for(datetime(2026, 10, 26, 9, 0, tzinfo=ET), mon, {KEY: [post("WKND", at_=sat)]})
    assert [n["symbol"] for n in names] == ["WKND"]
    later, _ = TN.names_for(datetime(2026, 10, 27, 9, 0, tzinfo=ET), date(2026, 10, 27),
                            {KEY: [post("WKND", at_=sat)]})
    assert later == []                                                   # NEGATIVE: Tuesday's window starts Monday


def test_NEGATIVE_a_post_after_now_is_ignored():
    future = (NOW + timedelta(minutes=1)).astimezone(UTC).isoformat()
    names, _ = TN.names_for(NOW, S, {KEY: [post("LATE", at_=future), post("ONTIME")]})
    assert [n["symbol"] for n in names] == ["ONTIME"]


def test_NEGATIVE_an_unparseable_created_at_never_counts():
    names, _ = TN.names_for(NOW, S, {KEY: [post("BAD", at_="not a time"), post("NONE", at_=None)]})
    assert names == []


def test_cap_keeps_the_newest_and_skips_the_rest_as_over_cap():
    n = GC.TRADER_NAMES_MAX + 2
    posts = [post(f"N{i:02d}", at_=at(8, i).astimezone(UTC).isoformat(), pid=f"st{i}") for i in range(n)]
    names, over = TN.names_for(NOW, S, {KEY: posts})
    assert len(names) == GC.TRADER_NAMES_MAX
    assert [x["symbol"] for x in names] == [f"N{i:02d}" for i in range(n - 1, 1, -1)]   # newest first
    assert over == [{"symbol": "N01", "trader": KEY, "reason": "over_cap"},
                    {"symbol": "N00", "trader": KEY, "reason": "over_cap"}]


def test_dedupe_newest_mention_wins_and_ties_sort_by_symbol():
    posts = [post("AAA", at_=at(8, 0).astimezone(UTC).isoformat(), pid="st1"),
             post("AAA", "CCC", at_=at(9, 0).astimezone(UTC).isoformat(), pid="st2", text="later"),
             post("BBB", at_=at(9, 0).astimezone(UTC).isoformat(), pid="st3")]
    names, _ = TN.names_for(NOW, S, {KEY: posts})
    assert [x["symbol"] for x in names] == ["AAA", "BBB", "CCC"]
    assert names[0]["post_id"] == "st2" and names[0]["text"] == "later"        # ONE name per symbol, the newest


def test_NEGATIVE_market_tickers_never_join():
    from traders.feed import MARKET_TICKERS
    names, _ = TN.names_for(NOW, S, {KEY: [post("SPY", "QQQ", "VIX", "GPUS")]})
    assert [x["symbol"] for x in names] == ["GPUS"]
    assert {"SPY", "QQQ", "VIX"} <= MARKET_TICKERS


def test_NEGATIVE_an_unflagged_trader_never_adds():
    names, over = TN.names_for(NOW, S, {"gnt": [post("NVDA")], "martinluk": [post("PLTR")]})
    assert names == [] and over == []
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    d.trader_posts = Rec(lambda key: [post("MXCT")])                   # every key "posts" MXCT
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert [a[0][0] for a in d.trader_posts.calls] == [KEY]            # only the flagged account is read
    assert out["trader"]["added"] == ["MXCT"]


# ── resolve ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _name(sym):
    return {"symbol": sym, "trader": KEY, "at": POST_AT, "post_id": "st1", "text": ""}


def _one(sym, rows, types=None, qualifiers=None):
    return TN.resolve([_name(sym)], rows, S, TYPES if types is None else types, qualifiers or [])


@pytest.mark.parametrize("sym,rows,reason", [
    ("NOPE", {}, "not_in_snapshot"),
    ("STALE", {"STALE": snap_row(1.0, 0.9, when=at(10, 40, d=PREV))}, "not_dated_session"),
    ("ZERO", {"ZERO": snap_row(1.0, 0.0)}, "no_prev_close"),
    ("TQQQ", {"TQQQ": snap_row(80.0, 79.0)}, "type_out"),
    ("BIGC", {"BIGC": snap_row(150.0, 140.0)}, "out_of_band"),
    ("PENNY", {"PENNY": snap_row(0.05, 0.04)}, "out_of_band"),
], ids=["not_in_snapshot", "not_dated_session", "no_prev_close", "type_out", "over_band", "under_band"])
def test_NEGATIVE_each_skip_reason(sym, rows, reason):
    res = _one(sym, rows, types=dict(TYPES, ZERO="CS", PENNY="CS"))
    assert res["added"] == [] and res["tagged"] == []
    assert res["skips"] == [{"symbol": sym, "trader": KEY, "reason": reason}]
    assert reason in TN.SKIP_REASONS and TN.SKIP_TEXT[reason]


def test_a_below_floor_name_is_added_with_the_tag():
    res = _one("MXCT", {"MXCT": snap_row(2.10, 2.00, vol=300_000)})
    (r,) = res["added"]
    assert r["symbol"] == "MXCT" and r["source"] == TN.SOURCE == "trader" and r["trader"] == KEY
    assert r["trader_text"] == f"{GC.TRADER_TAG} algo888"
    assert r["volume"] < GC.SCAN_MIN_VOLUME and r["change_pct"] < GC.SCAN_MIN_CHANGE_PCT   # HIS CALL #1: no floors


def test_an_unknown_type_follows_his_instrument_rule(monkeypatch):
    rows = {"NEWB": snap_row(3.0, 2.9)}
    assert _one("NEWB", rows, types={})["added"][0]["type"] == GC.SCAN_UNKNOWN_TYPE        # "list" policy
    monkeypatch.setattr(GC, "SCAN_UNKNOWN_TYPE_POLICY", "drop")
    assert _one("NEWB", rows, types={})["skips"][0]["reason"] == "type_out"                # NEGATIVE under "drop"


def test_NEGATIVE_a_qualifier_is_tagged_never_duplicated():
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    assert [x["symbol"] for x in q] == ["GPUS"]
    res = TN.resolve([_name("GPUS")], {"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, S, TYPES, q)
    assert res == {"added": [], "tagged": ["GPUS"], "skips": []}
    assert q[0]["trader"] == KEY and q[0]["trader_text"] == f"{GC.TRADER_TAG} algo888"
    assert "source" not in q[0]                                          # a GG qualifier is never a 📌 add


def test_the_added_row_equals_the_row_scan_rows_builds():
    rows = {"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}
    gg = SC.scan_rows(rows, NOW, S, types=TYPES)["qualifiers"][0]
    (mine,) = TN.resolve([_name("GPUS")], rows, S, TYPES, [])["added"]
    assert {k: v for k, v in mine.items() if k not in ("source", "trader", "trader_text")} == gg


def test_class_share_spelling_resolves():
    rows = {"BRK-B": snap_row(1.5, 1.4)}
    res = TN.resolve([_name("BRK.B")], rows, S, {"BRK-B": "CS"}, [])
    assert [r["symbol"] for r in res["added"]] == ["BRK-B"]


# ── scan_rows stays GG's (byte-identical, never the word trader) ──────────────────────────────────────────────────
def scan_fixture():
    """Every branch of scan_rows: a qualifier, under the change / volume floors, out of band, a type out, a type
    unknown, a stale print, no prior close, a non-dict, and an after-hours pass with a carry + K10 name."""
    rth = {"GGA": snap_row(11.2, 8.0), "NOPE": snap_row(1.0, 0.95), "LOWV": snap_row(3.0, 2.0, vol=900_000),
           "BIG": snap_row(150.0, 100.0), "TQQQ": snap_row(80.0, 60.0), "UNK": snap_row(4.0, 3.0),
           "STALE": snap_row(1.3, 1.0, when=at(10, 40, d=PREV)), "ZERO": snap_row(1.3, 0.0), "JUNK": "x"}
    ah_at = at(17, 29)
    ah = {"AHC": snap_row(13.0, 9.0, when=ah_at, close=11.0), "AHK": snap_row(11.7, 9.0, when=ah_at, close=11.0),
          "AHQ": snap_row(11.1, 9.0, when=ah_at, close=11.0)}
    types = {"GGA": "CS", "NOPE": "CS", "LOWV": "CS", "BIG": "CS", "TQQQ": "ETF", "STALE": "CS", "ZERO": "ADRC",
             "AHC": "CS", "AHK": "CS", "AHQ": "CS"}
    return [(rth, NOW, types), (ah, at(17, 31), types)]


# Produced by the PRE-2026-10-27 scanner.scan_rows (origin/main 807fcace, before type_verdict / build_row were
# extracted) on scan_fixture(), json.dumps(sort_keys=True) — the extraction must not move one byte.
SCAN_BEFORE = (
    "[{\"ah_carry\": null, \"counts\": {\"ah_close_eq_last\": 0, \"ah_rows\": 0, \"band_ok\": 4, \"change_ok\": 2, \"d"
    "ated_session\": 6, \"held_split\": 0, \"qualifiers\": 2, \"rows\": 9, \"split_failed\": 0, \"type_ok\": 5, \"typ"
    "e_out\": 1, \"type_unknown\": 1, \"vol_ok\": 3}, \"k10_candidates\": [], \"qualifiers\": [{\"change_pct\": 40.0"
    ", \"day_c\": 11.2, \"day_h\": 11.2, \"day_l\": 8.0, \"day_o\": 8.0, \"last_trade_et\": \"2026-10-13 10:40:00\", "
    "\"prev_close\": 8.0, \"price\": 11.2, \"symbol\": \"GGA\", \"tape_session\": \"rth\", \"type\": \"CS\", \"vol_src\": \""
    "min_av\", \"volume\": 3000000.0}, {\"change_pct\": 33.3333, \"day_c\": 4.0, \"day_h\": 4.0, \"day_l\": 3.0, \"da"
    "y_o\": 3.0, \"last_trade_et\": \"2026-10-13 10:40:00\", \"prev_close\": 3.0, \"price\": 4.0, \"symbol\": \"UNK\","
    " \"tape_session\": \"rth\", \"type\": \"unknown\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}], \"session\": \"2"
    "026-10-13\", \"strip\": {\"best_change_pct\": 40.0, \"best_symbol\": \"GGA\", \"n_population\": 3, \"quiet\": fal"
    "se, \"runners_100\": 0, \"runners_80\": 0}, \"tape_session\": \"rth\"}, {\"ah_carry\": [{\"ah_move_pct\": 18.181"
    "8, \"change_pct\": 44.4444, \"day_c\": 11.0, \"day_h\": 13.0, \"day_l\": 9.0, \"day_o\": 9.0, \"last_trade_et\":"
    " \"2026-10-13 17:29:00\", \"prev_close\": 9.0, \"price\": 13.0, \"symbol\": \"AHC\", \"tape_session\": \"afterhou"
    "rs\", \"type\": \"CS\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}], \"counts\": {\"ah_close_eq_last\": 0, \"ah"
    "_rows\": 3, \"band_ok\": 3, \"change_ok\": 2, \"dated_session\": 3, \"held_split\": 0, \"qualifiers\": 2, \"rows"
    "\": 3, \"split_failed\": 0, \"type_ok\": 3, \"type_out\": 0, \"type_unknown\": 0, \"vol_ok\": 3}, \"k10_candidat"
    "es\": [{\"ah_move_pct\": 18.1818, \"change_pct\": 44.4444, \"day_c\": 11.0, \"day_h\": 13.0, \"day_l\": 9.0, \"d"
    "ay_o\": 9.0, \"last_trade_et\": \"2026-10-13 17:29:00\", \"prev_close\": 9.0, \"price\": 13.0, \"symbol\": \"AHC"
    "\", \"tape_session\": \"afterhours\", \"type\": \"CS\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}, {\"ah_move_"
    "pct\": 6.3636, \"change_pct\": 30.0, \"day_c\": 11.0, \"day_h\": 11.7, \"day_l\": 9.0, \"day_o\": 9.0, \"last_tr"
    "ade_et\": \"2026-10-13 17:29:00\", \"prev_close\": 9.0, \"price\": 11.7, \"symbol\": \"AHK\", \"tape_session\": \""
    "afterhours\", \"type\": \"CS\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}], \"qualifiers\": [{\"ah_move_pct\""
    ": 18.1818, \"change_pct\": 44.4444, \"day_c\": 11.0, \"day_h\": 13.0, \"day_l\": 9.0, \"day_o\": 9.0, \"last_tr"
    "ade_et\": \"2026-10-13 17:29:00\", \"prev_close\": 9.0, \"price\": 13.0, \"symbol\": \"AHC\", \"tape_session\": \""
    "afterhours\", \"type\": \"CS\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}, {\"ah_move_pct\": 6.3636, \"chang"
    "e_pct\": 30.0, \"day_c\": 11.0, \"day_h\": 11.7, \"day_l\": 9.0, \"day_o\": 9.0, \"last_trade_et\": \"2026-10-13"
    " 17:29:00\", \"prev_close\": 9.0, \"price\": 11.7, \"symbol\": \"AHK\", \"tape_session\": \"afterhours\", \"type\":"
    " \"CS\", \"vol_src\": \"min_av\", \"volume\": 3000000.0}], \"session\": \"2026-10-13\", \"strip\": {\"best_change_p"
    "ct\": 44.4444, \"best_symbol\": \"AHC\", \"n_population\": 3, \"quiet\": false, \"runners_100\": 0, \"runners_80"
    "\": 0}, \"tape_session\": \"afterhours\"}]"
)


def test_NEGATIVE_scan_rows_is_byte_identical_and_never_says_trader():
    got = json.dumps([SC.scan_rows(r, now, S, types=t) for r, now, t in scan_fixture()], sort_keys=True)
    assert got == SCAN_BEFORE
    fn = next(n for n in ast.parse(Path(SC.__file__).read_text(encoding="utf-8")).body
              if isinstance(n, ast.FunctionDef) and n.name == "scan_rows")
    assert "trader" not in ast.unparse(fn).lower()
    assert "build_row(" in ast.unparse(fn) and "type_verdict(" in ast.unparse(fn)


def test_recount_keeps_qualifiers_gg_only():
    result = {"qualifiers": [{"symbol": "A"}, {"symbol": "B", "trader": KEY}, {"symbol": "C", "source": "trader"}],
              "counts": {"qualifiers": 3}}
    TN.recount(result)
    assert result["counts"]["qualifiers"] == 2 and result["counts"]["trader_added"] == 1


# ── the pass (run.py) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_pass_lists_reads_and_stores_the_added_name_with_trader():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["errors"] == []
    c = out["counts"]
    assert (c["qualifiers"], c["trader_added"], c["trader_tagged"], c["trader_skipped"]) == (1, 1, 1, 4)
    blk = out["trader"]
    assert blk["added"] == ["MXCT"] and blk["tagged"] == ["GPUS"] and blk["who"] == ["algo888"]
    assert {s["symbol"]: s["reason"] for s in blk["skips"]} == {"NOPE": "not_in_snapshot", "TQQQ": "type_out",
                                                               "BIGC": "out_of_band", "STALE": "not_dated_session"}
    assert TN.strip_text(blk).startswith(f"{GC.TRADER_TAG} 2 of algo888's posted names on this pass's list — ")
    docs = {d_["symbol"]: d_ for d_ in st.scan_docs([S])}
    assert docs["MXCT"]["last"]["source"] == "trader" and docs["MXCT"]["last"]["trader"] == KEY
    assert docs["GPUS"]["last"]["trader"] == KEY and "source" not in docs["GPUS"]["last"]
    assert set(docs) == {"GPUS", "MXCT"}                                  # NEGATIVE: no skipped name is written
    assert out["n_listed"] == 2 and out["n_read"] == 2
    for sym in ("GPUS", "MXCT"):
        ctx = st.get_read(S, sym)["ctx"]
        assert ctx["trader"] == KEY and ctx["trader_text"] == f"{GC.TRADER_TAG} algo888"
    assert st.latest_pass()["trader"]["added"] == ["MXCT"]                # the pass doc carries the block


def test_NEGATIVE_an_untagged_read_doc_is_byte_unchanged():
    st = fake_store()
    d, *_ = deps_for(worked_rows(ZZZ=snap_row(1.3, 1.0)))
    RUN.run_pass(NOW, store=st, deps=d)
    ctx = st.get_read(S, "ZZZ")["ctx"]
    assert "trader" not in ctx and "trader_text" not in ctx


def test_NEGATIVE_a_below_floor_name_never_rings_an_aplus_k11():
    from chart_maps.gajjala import detectors as D
    st = fake_store()
    d, _snap, send, _st = deps_for(worked_rows())
    out = RUN.run_pass(NOW, store=st, deps=d)
    r = st.get_read(S, "MXCT")["setups"]["bull_flag"]
    k11 = next(c for c in r["criteria"] if c["key"] == D.K11_KEY)
    assert r["state"] != "aplus" and k11["ok"] is False and "300,000 < 1,000,000" in k11["label"]
    assert "MXCT:bull_flag" not in out["aplus"]
    assert not any(a[1]["ticker"] == "MXCT" for a, _k in send.calls)
    assert "GG:2026-10-13|MXCT|bull_flag" not in st.alerts_coll().docs


def test_a_tagged_aplus_push_carries_the_tag_and_the_title_is_unchanged():
    st = fake_store()
    d, _snap, send, _st = deps_for(worked_rows(GGA=snap_row(11.2, 8.0)), posts=[post("GGA")])
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert "GGA:bull_flag" in out["aplus"]
    (payload,) = [a[1] for a, _k in send.calls if a[1]["ticker"] == "GGA"]
    assert f"{GC.TRADER_TAG} algo888" in payload["body"]
    plain = AL.compose(st.get_read(S, "GGA")["setups"]["bull_flag"], "GGA", {}, session=S)
    assert payload["title"] == plain["title"] and GC.TRADER_TAG not in payload["title"]   # HIS CALL #4
    body = payload["body"].split(" · ")
    assert body.index(f"{GC.TRADER_TAG} algo888") == body.index(AL.UNMEASURED_TAIL) - 1    # before the tail
    assert st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]["trader"] == KEY


def test_NEGATIVE_an_untagged_aplus_push_and_claim_are_unchanged():
    st = fake_store()
    d, _snap, send, _st = deps_for({"GGA": snap_row(11.2, 8.0)}, posts=[])
    RUN.run_pass(NOW, store=st, deps=d)
    (payload,) = [a[1] for a, _k in send.calls]
    assert GC.TRADER_TAG not in payload["body"] and "trader" not in st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]


def test_the_refresh_memo_fetches_once_per_900_s():
    assert GC.TRADER_REFRESH_SEC == 900 == GC.PASS_CADENCE_SEC * 3
    st = fake_store()
    fetch = Rec({"ok": True, "stored": 3})
    d, *_ = deps_for(worked_rows(), fetch=fetch)
    for k in range(4):                                                   # 10:41, 10:46, 10:51, 10:56
        RUN.run_pass(NOW + timedelta(seconds=GC.PASS_CADENCE_SEC * k), store=st, deps=d)
    assert [a[0] for a, _k in fetch.calls] == [KEY, KEY]                 # 10:41 and 10:56 (900 s later)
    memo = st.get_state(TN.STATE_ID)
    assert memo["ok"] is True and memo["stored"] == 3


def test_NEGATIVE_a_raising_fetch_never_fails_the_pass():
    st = fake_store()
    d, *_ = deps_for(worked_rows(), fetch=Rec(lambda key: (_ for _ in ()).throw(RuntimeError("dark"))))
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["errors"] == []
    assert out["trader"]["added"] == ["MXCT"] and out["trader"]["refresh"]["ok"] is False   # stored posts still used
    assert st.get_state(TN.STATE_ID)["ok"] is False


def test_NEGATIVE_an_x_sourced_account_is_never_fetched(monkeypatch):
    rows = [{"key": "gnt", "handle": "GnT_Trades", "source": "x", "gajjala": True},
            {"key": KEY, "handle": "algo888", "source": "stocktwits", "gajjala": True}]
    monkeypatch.setattr(TN, "_traders", lambda: rows)
    fetch = Rec({"ok": True, "stored": 1})
    memo = TN.maybe_refresh(fake_store(), NOW, fetch)
    assert [a for a, _k in fetch.calls] == [(KEY,)] and memo["stored"] == 1


def test_NEGATIVE_dry_and_on_open_never_fetch():
    fetch = Rec({"ok": True, "stored": 0})
    st = fake_store()
    st.dry = True
    d, *_ = deps_for(worked_rows(), fetch=fetch)
    out = RUN.run_pass(NOW, store=st, deps=d, dry=True)
    assert out["trader"]["refresh"] is None and out["trader"]["added"] == ["MXCT"]
    st2 = fake_store()
    d2, *_ = deps_for(worked_rows(), fetch=fetch)
    o2 = RUN.run_on_demand(NOW, store=st2, deps=d2)
    assert o2["ran"] and o2["trader"]["refresh"] is None
    assert fetch.calls == [] and st2.get_state(TN.STATE_ID) == {}


def test_NEGATIVE_a_failed_snapshot_adds_nothing_and_says_nothing():
    st = fake_store()
    fetch = Rec({"ok": True, "stored": 0})
    d, *_ = deps_for(worked_rows(), http=500, fetch=fetch)
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["trader"] == {"skipped": "snapshot"} and fetch.calls == [] and d.trader_posts.calls == []
    assert "trader_added" not in out["counts"] or out["counts"]["trader_added"] == 0
    assert TN.strip_text(out["trader"]) is None and TN.skip_text(out["trader"]) is None
    assert {x["symbol"] for x in st.scan_docs([S])} == {"GPUS"}          # his scanner's rows only, as before
    assert "trader" not in st.scan_docs([S])[0]["last"]


def test_NEGATIVE_a_raising_step_leaves_the_scan_untouched(monkeypatch):
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    monkeypatch.setattr(TN, "resolve", lambda *a, **k: (_ for _ in ()).throw(KeyError("boom")))
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["trader"] == {"error": "KeyError"} and out["status"] == "ok"
    assert out["qualifiers"] == ["GPUS"] and {x["symbol"] for x in st.scan_docs([S])} == {"GPUS"}
    assert "trader" not in st.scan_docs([S])[0]["last"]
    assert TN.strip_text(out["trader"]) is None and TN.skip_text(out["trader"]) is None


def test_NEGATIVE_default_deps_never_fetch_and_main_passes_default_fetch():
    dd = RUN.Deps()
    assert dd.trader_fetch is None and dd.trader_posts is None
    src = inspect.getsource(RUN.main)
    assert "run_pass(now, store=st, deps=Deps(trader_fetch=TN.default_fetch), symbols=syms)" in src
    assert "run_on_demand(now, store=st, deps=Deps())" in src                     # the open never re-reads
    assert "dry_deps()" in src and "trader_fetch" not in inspect.getsource(RUN.dry_deps)
    body = inspect.getsource(RUN.run_pass)
    i, j, k = body.index("SC.scan_rows("), body.index("TN.run_step("), body.index("SC.record_scan(")
    assert i < j < k and body.index("TN.recount(result)") > k
    assert "refresh=(not dry and not on_demand and deps.trader_fetch is not None)" in body


def test_default_fetch_and_posts_go_through_the_feed(monkeypatch):
    from traders import feed
    seen = []
    monkeypatch.setattr(feed, "refresh", lambda **k: seen.append(("refresh", k)) or {"ok": True, "stored": 0})
    monkeypatch.setattr(feed, "stored", lambda **k: seen.append(("stored", k)) or [])
    TN.default_fetch(KEY)
    TN.default_posts(KEY)
    assert seen == [("refresh", {"trader": KEY, "pages": GC.TRADER_FETCH_PAGES,
                                 "timeout": GC.TRADER_FETCH_TIMEOUT_SEC}), ("stored", {"trader": KEY})]


def test_out_qualifiers_stay_gg_only():
    st = fake_store()
    d, _snap, _send, status = deps_for(worked_rows())
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["qualifiers"] == ["GPUS"]                                    # MXCT is listed and read, not GG's
    (counts, _n, _r), _ = status.calls[0]
    assert counts["qualifiers"] == 1 and counts["listed"] == 2


# ── the tab ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _board(sub="bull_flag", rows=None, posts=None):
    st = fake_store()
    d, *_ = deps_for(rows or worked_rows(ZZZ=snap_row(1.3, 1.0)), posts=posts)
    RUN.run_pass(NOW, store=st, deps=d)
    return GT.build(sub, now=at(10, 42), store=st), st


def test_strip_serves_the_trader_line_and_skip_line():
    out, _st = _board()
    s = out["strip"]
    assert s["trader_text"] == (f"{GC.TRADER_TAG} 2 of algo888's posted names on this pass's list — your call "
                                "2026-10-27; GG's rules decide every read and every A+, and no push rings on one "
                                f"until today's volume clears GG's {GC.SCAN_MIN_VOLUME // 1_000_000}M floor")
    assert s["trader_skip_text"] == (
        f"{GC.TRADER_TAG} not on the list: BIGC — outside GG's $0.10–$100 band; NOPE — not in today's market snapshot "
        "(OTC, or no trade yet); STALE — no print dated today yet; TQQQ — not common stock or an ADR (your instrument "
        "rule)")                                                         # one post: the names in symbol order


def test_NEGATIVE_no_trader_name_means_no_strip_line():
    out, _st = _board(posts=[])
    assert out["strip"]["trader_text"] is None and out["strip"]["trader_skip_text"] is None
    assert TN.strip_text(None) is None and TN.strip_text({"added": [], "tagged": [], "who": ["x"]}) is None


def test_NEGATIVE_every_number_in_the_strip_line_is_a_served_count():
    block = {"added": ["A", "B", "C"], "tagged": ["D"], "skips": [], "who": ["algo888"], "refresh": None}
    text = TN.strip_text(block).replace("algo888", "").replace("2026-10-27", "")
    floor = str(GC.SCAN_MIN_VOLUME // 1_000_000)
    assert re.findall(r"\d+", text) == ["4", floor]                     # n, then GG's floor (the constant)
    assert not B_WORD.search(TN.strip_text(block))


def test_legend_has_trader_last():
    leg = GT.count_legend()
    assert leg[-1] == TN.legend_row() and leg[-1]["key"] == "trader" == GT.LEGEND_KEYS[-1]
    t = leg[-1]["text"]
    assert f"the last {GC.TRADER_NAMES_FRESH_SESSIONS} market sessions" in t and "without GG's change and volume" in t
    assert t.endswith(TN.FLOOR_CLAUSE) and "(K11)" not in t                # A2: the floor sentence, not K11-only


def test_tiles_and_rows_carry_trader_text_and_untagged_rows_none():
    out, _st = _board()
    tag = f"{GC.TRADER_TAG} algo888"
    tiles = {t["symbol"]: t for t in out["tiles"]}
    assert {"GPUS", "MXCT", "ZZZ"} <= set(tiles)
    assert tiles["GPUS"]["trader_text"] == tag and tiles["MXCT"]["trader_text"] == tag
    assert tiles["ZZZ"]["trader_text"] is None                              # NEGATIVE: untagged → None, key present
    rows = {r["symbol"]: r for r in (out["enterable"] or {}).get("rows") or []}
    assert rows["GPUS"]["trader_text"] == tag and rows["ZZZ"]["trader_text"] is None
    walked = GT._trader_tag
    probe = {"tiles": [{"symbol": "MXCT"}], "potential": {"rows": [{"symbol": "ZZZ"}]},
             "track": {"today": {"rows": [{"symbol": "MXCT"}]}, "yesterday": {"rows": [{"symbol": "X"}]}},
             "watch": {"symbols": [{"symbol": "MXCT"}]}, "postmarket": {"recap": {"rows": [{"symbol": "MXCT"}]}},
             "enterable": {"rows": [{"symbol": "MXCT"}]}}
    walked(probe, {"MXCT": {"trader": KEY, "trader_text": tag}})
    assert probe["tiles"][0]["trader_text"] == tag and probe["potential"]["rows"][0]["trader_text"] is None
    assert probe["track"]["today"]["rows"][0]["trader_text"] == tag
    assert probe["track"]["yesterday"]["rows"][0]["trader_text"] is None
    assert probe["watch"]["symbols"][0]["trader_text"] == tag
    assert probe["postmarket"]["recap"]["rows"][0]["trader_text"] == tag
    assert probe["enterable"]["rows"][0]["trader_text"] == tag


def test_NEGATIVE_the_tag_is_served_to_every_viewer_not_only_the_owner():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    RUN.run_pass(NOW, store=st, deps=d)
    for owner in (False, True):
        tiles = {t["symbol"]: t for t in GT.build("bull_flag", now=at(10, 42), store=st, owner=owner)["tiles"]}
        assert tiles["MXCT"]["trader_text"] == f"{GC.TRADER_TAG} algo888", owner


def test_tag_map_newest_doc_wins_and_rows_override():
    docs = [{"symbol": "AAA", "date": "2026-10-12", "last": {"trader": KEY}},
            {"symbol": "AAA", "date": "2026-10-13", "last": {}},
            {"symbol": "BBB", "date": "2026-10-09", "last": {"trader": KEY}}]
    m = TN.tag_map(docs)
    assert set(m) == {"BBB"} and m["BBB"] == {"trader": KEY, "trader_text": f"{GC.TRADER_TAG} algo888"}
    assert set(TN.tag_map(docs, [{"symbol": "AAA", "trader": KEY}, {"symbol": "BBB"}])) == {"AAA"}


# ── 🧠 potential (compose, doc, A2 hold) ──────────────────────────────────────────────────────────────────────────
def test_potential_compose_and_doc_carry_the_tag():
    from tests.test_gajjala_potential import bf_armed
    r = bf_armed()
    kind = PT.potential_kind(r)
    tag = f"{GC.TRADER_TAG} algo888"
    p = PT.compose("MXCT", "bull_flag", r, kind, {}, first_seen_et="10:36", tape="rth", trader_text=tag,
                   broker_text="🚫 x")
    plain = PT.compose("MXCT", "bull_flag", r, kind, {}, first_seen_et="10:36", tape="rth", broker_text="🚫 x")
    bits = p["body"].split(" · ")
    assert bits.index(tag) == bits.index("🚫 x") - 1 and p["title"] == plain["title"]
    assert PT.compose("MXCT", "bull_flag", r, kind, {}, first_seen_et=None, tape="rth", trader_text="")["body"] == \
        PT.compose("MXCT", "bull_flag", r, kind, {}, first_seen_et=None, tape="rth")["body"]     # NEGATIVE: "" = none
    st = fake_store()
    doc, new = PT.track(st, S, "MXCT", "bull_flag", r, kind, at(10, 36), px=2.1, values={}, trader=KEY)
    assert new and st.get_potential(S, "MXCT", "bull_flag")["trader"] == KEY
    doc2, _ = PT.track(st, S, "ZZZ", "bull_flag", r, kind, at(10, 36), px=2.1, values={})
    assert "trader" not in st.get_potential(S, "ZZZ", "bull_flag")                       # NEGATIVE: untagged


def _pot_pass(st, now, sym, *, hold, ctx=None, send=None):
    from tests.test_gajjala_potential import bf_armed, frame_at
    send = send or Rec(OK_SEND)
    out = PT.run_pass({sym: {"bull_flag": bf_armed()}}, {sym: frame_at(now)}, now, S, store=st,
                      ctx={sym: ctx or {"trader": KEY, "trader_text": f"{GC.TRADER_TAG} algo888"}},
                      rows={sym: {"volume": hold.get(sym), "price": 2.1}}, send=send, owner="owner@example.com",
                      tape="rth", trader_hold=hold)
    return out, send


def test_NEGATIVE_a_below_floor_trader_name_never_rings_the_potential_push():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    out, send = _pot_pass(st, at(10, 36), "MXCT", hold={"MXCT": 300_000})
    assert send.calls == [] and out["trader_held"] == 1 and out["pushed"] == 0
    doc = st.get_potential(S, "MXCT", "bull_flag")
    assert "push" not in doc and [h["reason"] for h in doc["held"]] == list(PT.TRADER_HELD)
    assert GT._track_row(doc)["push_text"] == TN.TRADER_HOLD_TEXT
    assert TN.TRADER_HOLD_TEXT == (f"held: {GC.TRADER_TAG} under GG's {GC.SCAN_MIN_VOLUME // 1_000_000}M volume "
                                   "floor — listed and read, not rung")
    assert doc["trader"] == KEY
    out2, send2 = _pot_pass(st, at(10, 41), "MXCT", hold={"MXCT": None})      # an unknown volume: fail closed
    assert send2.calls == [] and out2["pushed"] == 0


def test_the_hold_clears_when_the_session_volume_crosses_the_floor():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    _pot_pass(st, at(10, 36), "MXCT", hold={"MXCT": 300_000}, send=send)
    assert send.calls == []
    out, _ = _pot_pass(st, at(10, 41), "MXCT", hold={"MXCT": 1_200_000}, send=send)
    assert out["pushed"] == 1 and len(send.calls) == 1
    assert f"{GC.TRADER_TAG} algo888" in send.calls[0][0][1]["body"]
    out3, _ = _pot_pass(st, at(10, 46), "MXCT", hold={"MXCT": 2_000_000}, send=send)
    assert len(send.calls) == 1 and out3["pushed"] == 0                 # NEGATIVE: never a re-ring (K3)


def test_NEGATIVE_a_gg_qualifier_with_the_tag_is_never_held():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    out, send = _pot_pass(st, at(10, 36), "GPUS", hold={})                # tagged, not an add → not in the hold map
    assert out["pushed"] == 1 and out["trader_held"] == 0 and len(send.calls) == 1
    assert TN.added_symbols([], [{"symbol": "GPUS", "trader": KEY}]) == set()
    assert TN.added_symbols([{"symbol": "MXCT", "date": "2026-10-12", "last": {"source": "trader"}}]) == {"MXCT"}
    assert TN.added_symbols([{"symbol": "MXCT", "date": "2026-10-12", "last": {"source": "trader"}}],
                            [{"symbol": "MXCT"}]) == set()                # a GG row of this pass decides


def test_the_pass_holds_the_added_potential_and_rings_the_tagged_one():
    """End to end: forming bull flags (no entry bar) on every listed name; MXCT (a 300k 📌 add) is held, GPUS (a GG
    qualifier carrying the tag) rings."""
    from tests.test_gajjala_potential import seed
    today = minutes_from_5m(FX.bf_bars(entry=None), S, "10:00")
    st = fake_store()
    seed(st)
    d, *_ = deps_for(worked_rows(), load=lambda sym, day: PRIOR_1M.copy() if day == PREV else today.copy())
    out = RUN.run_pass(at(10, 36), store=st, deps=d)
    pushed = [a[1]["ticker"] for a, _k in d.send_potential.calls]
    assert set(pushed) == {"GPUS"} and pushed and "MXCT" not in pushed
    assert out["potential"]["trader_held"] >= 1 and out["potential"]["pushed"] == len(pushed)
    assert [h["reason"] for h in st.get_potential(S, "MXCT", "bull_flag")["held"]] == list(PT.TRADER_HELD)


def test_NEGATIVE_the_trader_hold_is_not_a_held_words_key():
    """The /alerts page words every HELD_WORDS key (contracts.mjs) — the 📌 hold keeps its OWN frozen words."""
    assert not set(PT.TRADER_HELD) & set(PT.HELD_WORDS) and PT.COUNT_KEYS[-1] == "trader_held"


# ── 🏁 ledger ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_ledger_row_serves_trader_text_from_the_claim_doc():
    from tests.test_gajjala_track_record_tab import D16, NOW as TR_NOW, _et, pot_doc
    tagged = dict(pot_doc(D16, "MXCT", "bull_flag", _et(D16, 10, 2), trigger=2.2, stop=2.0, px=2.1), trader=KEY)
    plain = pot_doc(D16, "ZZZ", "bull_flag", _et(D16, 10, 12), trigger=2.2, stop=2.0, px=2.1)
    assert LG.alert_of(tagged, "potential")["trader"] == KEY and LG.alert_of(plain, "potential")["trader"] is None
    claim = {"_id": "GG:2026-10-16|GGA|bull_flag", "date": "2026-10-16", "symbol": "GGA", "setup": "bull_flag",
             "state": "pushed", "trigger": 4.12, "stop": 3.95, "at": _et(D16, 10, 31).isoformat(), "trader": KEY}
    assert LG.alert_of(claim, "aplus")["trader"] == KEY
    st = fake_store(**{ST.POTENTIALS: FakeColl([tagged, plain])})
    out = GT.build(GC.LEDGER_SUB, span="today", now=TR_NOW, store=st, today=None)
    rows = {r["symbol"]: r for d_ in out["track_record"]["days"] for r in d_["rows"]}
    assert rows["MXCT"]["trader_text"] == f"{GC.TRADER_TAG} algo888" and rows["ZZZ"]["trader_text"] is None


def test_NEGATIVE_a_replayed_row_has_none():
    from tests.test_gajjala_ledger_replay import replay_doc
    doc = replay_doc(trader=KEY)
    row = LG.alert_of(doc, "aplus")
    assert row is not None and row["line"] == LG.LINES[2] and row["trader"] is None


# ── ℹ️ rules ──────────────────────────────────────────────────────────────────────────────────────────────────────
def test_rules_info_scanner_pick_carries_the_trader_clause_and_picks_stay_eight():
    from supply_demand import rules_info as RI
    sec = RI.sections()["gajjala"]
    assert len(sec["picks"]) == 8
    assert sec["picks"][0].startswith("Scanner (his numbers)") and sec["picks"][0].endswith(" " + TN.rules_clause())
    clause = TN.rules_clause()
    assert "algo888" in clause and f"every {GC.TRADER_REFRESH_SEC // 60} minutes" in clause
    assert f"at most {GC.TRADER_NAMES_MAX} a pass" in clause and TN.FLOOR_CLAUSE in clause
    assert "Cheetah defaults (yours, not GG's)" in clause and not B_WORD.search(clause)


def test_NEGATIVE_no_flagged_trader_means_no_clause(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(TN, "_traders", lambda: [{"key": "gnt", "handle": "GnT_Trades", "gajjala": False}])
    assert TN.rules_clause() == "" and RI._gg_trader_clause() == ""
    assert RI.sections()["gajjala"]["picks"][0].endswith("(his read).")
    monkeypatch.setattr(TN, "rules_clause", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert RI._gg_trader_clause() == ""                                  # NEGATIVE: never breaks the panel


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_new_constants_are_tagged_mine():
    src = Path(GC.__file__).read_text(encoding="utf-8").splitlines()
    names = ("TRADER_TAG", "TRADER_NAMES_FRESH_SESSIONS", "TRADER_NAMES_MAX", "TRADER_REFRESH_SEC",
             "TRADER_FETCH_PAGES", "TRADER_FETCH_TIMEOUT_SEC")
    for n in names:
        (line,) = [ln for ln in src if ln.startswith(f"{n} = ")]
        assert "MINE" in line.split("#", 1)[1], n
        assert "GG S" not in line and "GG X" not in line, n
    assert (GC.TRADER_NAMES_FRESH_SESSIONS, GC.TRADER_NAMES_MAX, GC.TRADER_FETCH_PAGES,
            GC.TRADER_FETCH_TIMEOUT_SEC, GC.TRADER_TAG) == (2, 10, 1, 5.0, "📌")
    assert not set(names) & set(GC.CHEETAH_DEFAULTS)                     # NEGATIVE: never on the ℹ️ defaults tuple
    # NEGATIVE: GG's scanner numbers are untouched
    assert (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE, GC.SCAN_MIN_VOLUME, GC.SCAN_MIN_CHANGE_PCT) == (0.10, 100.0,
                                                                                                1_000_000, 25.0)


def test_NEGATIVE_no_b_word_and_no_edge_claim_in_any_served_string():
    texts = [TN.STRIP_TEXT, TN.SKIP_HEAD, TN.TRADER_HOLD_TEXT, TN.rules_clause(), TN.legend_row()["text"],
             *TN.SKIP_TEXT.values()]
    src = Path(TN.__file__).read_text(encoding="utf-8")
    assert not B_WORD.search(src)
    for t in texts:
        assert not B_WORD.search(t) and "edge" not in t.lower() and "will " not in t.lower(), t


# ── 2026-10-27 critic round (F1 split hold-out, F2 /alerts words, F3 the doc probe, F6 the fence) ──────────────────
def _split_on(sym_held):
    return lambda sym, since: ([{"execution_date": S.isoformat()}] if sym == sym_held else [])


def test_NEGATIVE_a_split_held_add_is_never_counted_on_the_strip():
    """F1: MXCT (a 📌 add) reverse-splits today — the hold-out drops it, so the block, the counts and the strip line
    never claim it."""
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    d.fetch_splits = _split_on("MXCT")
    out = RUN.run_pass(NOW, store=st, deps=d)
    blk, c = out["trader"], out["counts"]
    assert blk["added"] == [] and blk["tagged"] == ["GPUS"]
    assert (c["qualifiers"], c["trader_added"], c["trader_tagged"], c["held_split"]) == (1, 0, 1, 1)
    assert TN.strip_text(blk).startswith(f"{GC.TRADER_TAG} 1 of algo888's posted names on this pass's list — ")
    assert sorted(x["symbol"] for x in st.scan_docs([S])) == ["GPUS"]   # the listed docs: his qualifier only
    assert st.latest_pass()["trader"]["added"] == []                    # the stored pass doc carries the trimmed block


def test_NEGATIVE_a_split_held_tagged_qualifier_leaves_the_block():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    d.fetch_splits = _split_on("GPUS")
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["trader"]["tagged"] == [] and out["trader"]["added"] == ["MXCT"]
    assert out["counts"]["trader_tagged"] == 0 and out["counts"]["trader_added"] == 1
    assert TN.strip_text(out["trader"]).startswith(f"{GC.TRADER_TAG} 1 of algo888's")


def test_trim_block_keeps_listed_names_and_leaves_a_skipped_or_failed_block_alone():
    result = {"qualifiers": [{"symbol": "A"}, {"symbol": "B", "source": "trader"}], "counts": {"trader_tagged": 2}}
    blk = {"added": ["B", "GONE"], "tagged": ["A", "HELD"], "skips": [], "who": ["algo888"], "refresh": None}
    TN.trim_block(blk, result)
    assert blk["added"] == ["B"] and blk["tagged"] == ["A"] and result["counts"]["trader_tagged"] == 1
    for b in ({"skipped": "snapshot"}, {"error": "KeyError"}, None):     # NEGATIVE: nothing to trim, nothing invented
        before = json.dumps(b)
        TN.trim_block(b, result)
        assert json.dumps(b) == before
    assert inspect.getsource(RUN.run_pass).index("TN.trim_block(") > inspect.getsource(RUN.run_pass).index(
        "TN.recount(result)")


def test_NEGATIVE_a_raising_resolve_never_tags_gg_rows(monkeypatch):
    """F6: the tag lands on GG's row only after resolve finished — a raise mid-walk leaves his rows as he built them."""
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    real, calls = TN.text_for, []

    def boom(key):
        calls.append(key)
        if len(calls) == 2:
            raise RuntimeError("boom")
        return real(key)

    monkeypatch.setattr(TN, "text_for", boom)
    with pytest.raises(RuntimeError):
        TN.resolve([_name("GPUS"), _name("MXCT")], {"MXCT": snap_row(2.10, 2.00, vol=300_000)}, S, TYPES, q)
    assert "trader" not in q[0] and "trader_text" not in q[0]


def test_NEGATIVE_a_step_that_raises_after_a_match_stores_no_tag(monkeypatch):
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    real, calls = TN.text_for, []

    def boom(key):
        calls.append(key)
        if len(calls) == 3:                                             # BIGC, GPUS (a qualifier), then MXCT raises
            raise RuntimeError("boom")
        return real(key)

    monkeypatch.setattr(TN, "text_for", boom)
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["trader"] == {"error": "RuntimeError"} and out["qualifiers"] == ["GPUS"]
    assert "trader" not in st.scan_docs([S])[0]["last"]


def test_the_trader_hold_words_are_served_on_alerts_rows_and_the_chip():
    """F2: /alerts prints the 📌 hold's words as SERVED (trader_names.TRADER_HOLD_TEXT), on the 🧠 row and the
    trader_held chip; every other row / pass keeps its shape."""
    from supply_demand import alert_status as AS
    from tests.test_gajjala_potential_kind import NOW as PK_NOW, PassColl, TrackerColl, _doc
    assert PT.TRADER_HELD == (TN.HOLD_REASON,) and TN.held_text(TN.HOLD_REASON) == TN.TRADER_HOLD_TEXT
    c = TrackerColl([_doc("MXCT", "bull_flag", held=[{"at_et": "09:41", "reason": TN.HOLD_REASON}]),
                     _doc("GGB", "kiss_fly", held=[{"at_et": "09:36", "reason": "muted"}])])
    items = {i["symbol"]: i for i in AS.read_gajjala_potentials(c, PK_NOW)}
    assert items["MXCT"]["held"] == TN.HOLD_REASON and items["MXCT"]["held_text"] == TN.TRADER_HOLD_TEXT
    assert "held_text" not in items["GGB"]                              # NEGATIVE: an older hold keeps its shape
    pc = PassColl()
    AS.record_pass("gajjala_potential", {"potential": 1, "trader_held": 2}, PK_NOW, coll=pc)
    row = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=PK_NOW, potential_coll=c)["passes"][
        "gajjala_potential"]
    assert row["trader_held_text"] == TN.TRADER_HOLD_TEXT


@pytest.mark.parametrize("counts", [{"potential": 1, "trader_held": 0}, {"potential": 1}, {}])
def test_NEGATIVE_no_trader_hold_means_no_served_chip_words(counts):
    from supply_demand import alert_status as AS
    from tests.test_gajjala_potential_kind import NOW as PK_NOW, PassColl, TrackerColl
    pc = PassColl()
    if counts:
        AS.record_pass("gajjala_potential", counts, PK_NOW, coll=pc)
    row = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=PK_NOW, potential_coll=TrackerColl())["passes"][
        "gajjala_potential"]
    assert "trader_held_text" not in row
    assert TN.held_text("muted") is None and TN.held_text(None) is None and TN.held_text("") is None


DOC = Path(__file__).resolve().parents[2] / "docs" / "gajjala" / "trader_names_2026_10_27.md"


def _doc_probe() -> str:
    text = DOC.read_text(encoding="utf-8")
    a = text.index("cheetah-market-app-cron-1 python - <<'EOF'\n") + len("cheetah-market-app-cron-1 python - <<'EOF'\n")
    return text[a:text.index("\nEOF\n", a)]


def test_the_doc_probe_equals_the_repo_on_the_fixture_and_the_worked_example():
    """F3: the pre-deploy probe re-implements parse / names / resolve on what origin/main already has; on the real
    2026-10-27 page and on the §3.3 worked example it gives exactly what the repo gives."""
    import stocktwits_client as STC
    from traders import feed
    ns: dict = {"__name__": "doc_probe"}                                # its __main__ block (the I/O) never runs here
    exec(compile(_doc_probe(), str(DOC), "exec"), ns)
    assert (ns["FRESH"], ns["MAX"]) == (GC.TRADER_NAMES_FRESH_SESSIONS, GC.TRADER_NAMES_MAX)
    assert ns["URL"] == STC.USER_URL.format(username=KEY) and ns["WHO"] == KEY
    msgs = json.loads(FIXTURE.read_text(encoding="utf-8"))["messages"]
    repo = feed.parse_stocktwits(msgs, KEY)
    mine = ns["parse"](msgs, KEY)
    assert [(p["id"], p["created_at"], p["cashtags"]) for p in mine] == \
        [(p["id"], p["created_at"], p["cashtags"]) for p in repo]
    for now, sess in ((datetime(2026, 10, 27, 10, 0, tzinfo=ET), date(2026, 10, 27)),
                      (datetime(2026, 10, 29, 10, 0, tzinfo=ET), date(2026, 10, 29))):
        names, over = TN.names_for(now, sess, {KEY: repo})
        assert ns["names"](now, sess, mine) == ([n["symbol"] for n in names], [o["symbol"] for o in over])
    syms = [n["symbol"] for n in TN.names_for(NOW, S, {KEY: WORKED_POSTS})[0]]
    rows = worked_rows()
    quals = SC.scan_rows(rows, NOW, S, types=TYPES)["qualifiers"]
    res = TN.resolve(TN.names_for(NOW, S, {KEY: WORKED_POSTS})[0], rows, S, TYPES, [dict(q) for q in quals])
    added, tagged, skips = ns["resolve"](syms, rows, S, TYPES, quals)
    assert [(r["symbol"], r["price"], r["volume"]) for r in res["added"]] == added
    assert res["tagged"] == tagged and [(s["symbol"], s["reason"]) for s in res["skips"]] == skips


def test_NEGATIVE_the_doc_probe_never_needs_this_branch():
    """F3: the cron container runs origin/main — the probe may not import what only this branch ships."""
    probe = _doc_probe()
    for absent in ("trader_names", "fetch_user_stream", "parse_stocktwits", "type_verdict", "build_row", "TRADER_"):
        assert absent not in probe, absent
    assert "_get_page(" in probe and "market_snapshot_with_meta(include_otc=False)" in probe
    assert not [ln for ln in probe.splitlines() if ln.lstrip().startswith("#")]   # no '#' lines in a shell block
    assert "insert" not in probe and "replace_one" not in probe and "send" not in probe.lower()   # reads only
