"""🎪 Promo-circuit names on 🚩 Gajjala's list — chart_maps/gajjala/promo_names.py + its seams (BUILD_SPEC32 D1–D4, D6).

Ajay 2026-10-29, verbatim: "Also I see a some of stocks we see are also in Gajjalas page. Don't see some should we pull
stocks from PROMO circuit by default every day they are having some good catched but I do wanna run them against
Gajjalas strategies". The names the Promo circuit TAGGED on the session's ET date (first or later tag — the page's
"today" rule), read from the stored tags through promo_circuit.prune_shotgun_tags, join the pass's candidates after the
📌 step with the 📌 add check (no change / volume floor for the ADD), ordered by today's % change, cut at
PROMO_NAMES_MAX (over-cap COUNTED); a listed name is TAGGED, never added twice; a 📌+🎪 name keeps both. GG's 1M floor
stays on EVERY push (the 🧠 push of a 🎪 add is HELD under it, GG5 and GG1). An unwired or EMPTY source adds NO key
(the GG5 identity fixture is unchanged). The REAL scanner, bars and detectors run on fixture data. NEGATIVES are
mandatory and named so. INVERTED / UNMEASURED: nothing here claims an edge.
"""
from __future__ import annotations

import copy
import inspect
import json
import re
from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from catalysts import promo_circuit as PC
from chart_maps.gajjala import alerts as AL
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import potential as PT
from chart_maps.gajjala import promo_names as PN
from chart_maps.gajjala import run as RUN
from chart_maps.gajjala import scanner as SC
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tab as GT
from chart_maps.gajjala import trader_names as TN
from chart_maps.gajjala import variant as V
from tests.test_gajjala_run import PREV, PRIOR_1M, Rec, S, at, make_deps, minutes_from_5m, snap_row
from tests.test_gajjala_store import FakeColl, fake_store
from tests.fixtures.gajjala import detector_frames as FX

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
B_WORD = re.compile("b" + "ounc", re.I)
NOW = at(10, 41)
KEY = "algo888"                                         # the flagged 📌 trader (traders/registry.py)
S_ACCT, A_ACCT, B_ACCT = "ShangVXO", "topstockalerts", "PSM_EmpowerTrading"   # roster tiers S / A / B
TYPES = {"GPUS": "CS", "MXCT": "CS", "LOWC": "CS", "HIGH": "CS", "BIGC": "CS", "STALE": "CS", "YDAY": "CS",
         "ZZZ": "CS", "TQQQ": "ETF", "GGA": "CS"}
OK_SEND = {"sent": 1, "failed": 0, "total_targets": 1}
PROMO_ROWS = ("LOWC", "HIGH")


@pytest.fixture(autouse=True)
def _no_override(monkeypatch):
    monkeypatch.delenv("CHEETAH_IGNORE_HOLIDAY", raising=False)


@pytest.fixture(autouse=True)
def _no_1m_spawn(monkeypatch):
    from chart_maps.gajjala import run_1m as R1
    monkeypatch.setattr(R1, "spawn_loop", lambda *a, **k: True)


def tag(ticker, account=S_ACCT, *, first=None, last=None, posts=(), n=1, naive=False):
    """One stored `promo_circuit_tags` doc (promo_circuit.sweep's shape)."""
    first = first or at(8, 30)
    last = last or first

    def st_(t):
        u = t.astimezone(UTC)
        return u.replace(tzinfo=None) if naive else u

    return {"_id": f"{account}:{ticker}", "account": account, "ticker": ticker, "tier": "B",
            "first_tagged_at": st_(first), "last_tagged_at": st_(last), "n_messages": n,
            "posts": [{"id": f"p{i}", "at": st_(t), "body": "x"} for i, t in enumerate(posts)]}


def worked_rows(**extra):
    """S 2026-10-13, 10:41 ET: GPUS GG's qualifier; MXCT a 📌 add (300k, +5%); LOWC (+5%) and HIGH (+20%) under GG's
    floors; BIGC over the band; STALE printed last session; YDAY tagged only yesterday; NOPE absent; ZZZ GG's own
    qualifier, untagged."""
    rows = {"GPUS": snap_row(0.19, 0.15, vol=40_000_000), "MXCT": snap_row(2.10, 2.00, vol=300_000),
            "LOWC": snap_row(2.10, 2.00, vol=300_000), "HIGH": snap_row(4.80, 4.00, vol=500_000),
            "BIGC": snap_row(150.0, 140.0), "STALE": snap_row(1.0, 0.9, when=at(10, 40, d=PREV)),
            "YDAY": snap_row(3.0, 2.9), "ZZZ": snap_row(1.3, 1.0)}
    rows.update(extra)
    return rows


def worked_tags():
    return [tag("GPUS"), tag("MXCT", A_ACCT), tag("LOWC", B_ACCT, first=at(9, 41)), tag("HIGH", first=at(7, 5)),
            tag("BIGC"), tag("STALE"), tag("NOPE"), tag("YDAY", first=at(9, 0, d=PREV))]


def deps_for(rows, tags=None, *, posts=None, http=200, load=None, wired=True):
    d, snap, send, status = make_deps(rows=rows, http=http, load=load)
    d.fetch_types = lambda: (dict(TYPES), True, 1)
    posts = [TN_post("MXCT")] if posts is None else posts
    d.trader_posts = Rec(lambda key: list(posts) if key == KEY else [])
    d.promo_tags = Rec(lambda now: list(worked_tags() if tags is None else tags)) if wired else None
    return d, snap, send, status


def TN_post(*tags_, at_=None):
    return {"id": "st1", "text": "his post", "created_at": (at_ or at(8, 30)).astimezone(UTC).isoformat(),
            "cashtags": list(tags_), "source": "stocktwits"}


# ── constants ─────────────────────────────────────────────────────────────────────────────────────────────────────
def test_the_constants_are_mine_and_the_cap_is_a_cheetah_default():
    from pathlib import Path
    src = Path(GC.__file__).read_text(encoding="utf-8").splitlines()
    for n in ("PROMO_TAG", "PROMO_NAMES_MAX"):
        (line,) = [ln for ln in src if ln.startswith(f"{n} = ")]
        c = line.split("#", 1)[1]
        assert c.strip().startswith("Cheetah default") and "MINE, not GG" in c, n
        assert "GG S" not in line and "GG X" not in line, n
    assert (GC.PROMO_TAG, GC.PROMO_NAMES_MAX) == ("🎪", 25) and "HIS CALL #1" in [
        ln for ln in src if ln.startswith("PROMO_NAMES_MAX = ")][0]
    assert "PROMO_NAMES_MAX" in GC.CHEETAH_DEFAULTS and "PROMO_TAG" not in GC.CHEETAH_DEFAULTS
    # NEGATIVE: GG's scanner numbers and the 📌 numbers are untouched
    assert (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE, GC.SCAN_MIN_VOLUME, GC.SCAN_MIN_CHANGE_PCT) == (0.10, 100.0,
                                                                                                1_000_000, 25.0)
    assert (GC.TRADER_NAMES_MAX, GC.TRADER_NAMES_FRESH_SESSIONS, GC.NO_TRADE_AFTER_OPEN_MIN, GC.PASS_CADENCE_SEC) == (
        10, 2, 15, 300)
    assert PN.SOURCE == "promo" and PN.TAG == GC.PROMO_TAG


# ── names_for (PURE) ──────────────────────────────────────────────────────────────────────────────────────────────
def test_names_for_takes_todays_et_tags_and_names_the_best_tier():
    names = PN.names_for(NOW, S, worked_tags())
    assert [n["symbol"] for n in names] == ["BIGC", "GPUS", "HIGH", "LOWC", "MXCT", "NOPE", "STALE"]
    low = next(n for n in names if n["symbol"] == "LOWC")
    assert (low["account"], low["tier"], low["first_et"]) == (B_ACCT, "B", "09:41")
    assert PN.text_for(low["account"], low["tier"], low["first_et"]) == \
        "🎪 promo · first tag 09:41 ET · @PSM_EmpowerTrading · tier B"


def test_NEGATIVE_a_tag_yesterday_is_out_and_a_later_tag_today_is_in():
    yday = tag("OLD", first=at(15, 0, d=PREV))
    retag = tag("RET", first=at(15, 0, d=PREV), last=at(9, 50))           # first tag yesterday, a LATER tag today
    names = PN.names_for(NOW, S, [yday, retag])
    assert [n["symbol"] for n in names] == ["RET"] and names[0]["first_et"] == "09:50"
    post = tag("PST", first=at(15, 0, d=PREV), last=at(10, 30), posts=[at(15, 0, d=PREV), at(9, 12), at(10, 30)])
    (p,) = PN.names_for(NOW, S, [post])
    assert p["first_et"] == "09:12"                                       # the earliest tag OF THE DAY
    # NEGATIVE: the ET date, not the UTC date — 20:30 ET yesterday is 00:30 UTC today
    late = tag("UTCX", first=datetime(2026, 10, 12, 20, 30, tzinfo=ET))
    assert late["first_tagged_at"].date() == S and PN.names_for(NOW, S, [late]) == []


def test_NEGATIVE_a_tag_after_now_is_ignored_and_naive_stamps_are_utc():
    future = tag("LATE", first=NOW + timedelta(minutes=5))
    assert PN.names_for(NOW, S, [future]) == []
    naive = tag("NAIV", first=at(9, 1), naive=True)
    (n,) = PN.names_for(NOW, S, [naive])
    assert n["first_et"] == "09:01"


def test_NEGATIVE_an_off_roster_account_never_adds():
    assert PN.names_for(NOW, S, [tag("XXX", "somebody_else")]) == []
    assert PN.names_for(NOW, S, [tag("XXX", "somebody_else")], roster={"somebody_else": {"tier": "A"}})[0][
        "tier"] == "A"


def test_shotgun_one_offs_are_pruned_over_the_window_not_todays_slice():
    """An account tagging > SHOTGUN_DISTINCT_TAGS tickers in the 14-day window keeps only repeats (n ≥ 2) — the
    window decides: its ONE tag today is dropped although today alone it tagged one name."""
    old = [tag(f"W{i:02d}", B_ACCT, first=at(9, 0, d=date(2026, 10, 5))) for i in range(PC.SHOTGUN_DISTINCT_TAGS)]
    today_one = tag("ONEOFF", B_ACCT, first=at(9, 30))
    today_rep = tag("REPEAT", B_ACCT, first=at(9, 31), n=2)
    names = [n["symbol"] for n in PN.names_for(NOW, S, old + [today_one, today_rep])]
    assert names == ["REPEAT"]
    assert [n["symbol"] for n in PN.names_for(NOW, S, [today_one])] == ["ONEOFF"]   # a focused account keeps all
    # NEGATIVE: a doc past the page's 14-day window neither counts toward the shotgun nor joins
    stale = [tag(f"Q{i:02d}", B_ACCT, first=NOW - timedelta(days=PC.TAG_WINDOW_DAYS + 1))
             for i in range(PC.SHOTGUN_DISTINCT_TAGS)]
    assert [n["symbol"] for n in PN.names_for(NOW, S, stale + [today_one])] == ["ONEOFF"]


def test_one_name_per_ticker_best_tier_then_earliest_and_every_account_listed():
    docs = [tag("DUP", B_ACCT, first=at(8, 0)), tag("DUP", A_ACCT, first=at(9, 0)), tag("DUP", "beppels",
                                                                                       first=at(8, 30))]
    (n,) = PN.names_for(NOW, S, docs)
    assert (n["account"], n["tier"]) == ("beppels", "A")                 # tier A beats B; the earlier A wins
    assert n["first_et"] == "08:00" and n["accounts"] == sorted([B_ACCT, A_ACCT, "beppels"])


# ── resolve: the add check, band, dated snapshot, the cap, the order, tagged-not-added ────────────────────────────
def _names(*syms, account=S_ACCT):
    return [{"symbol": s, "account": account, "tier": "S", "first_et": "09:30", "accounts": [account]} for s in syms]


@pytest.mark.parametrize("sym,rows,reason", [
    ("NOPE", {}, "not_in_snapshot"),
    ("STALE", {"STALE": snap_row(1.0, 0.9, when=at(10, 40, d=PREV))}, "not_dated_session"),
    ("ZERO", {"ZERO": snap_row(1.0, 0.0)}, "no_prev_close"),
    ("TQQQ", {"TQQQ": snap_row(80.0, 79.0)}, "type_out"),
    ("BIGC", {"BIGC": snap_row(150.0, 140.0)}, "out_of_band"),
    ("PENNY", {"PENNY": snap_row(0.05, 0.04)}, "out_of_band"),
], ids=["not_in_snapshot", "not_dated_session", "no_prev_close", "type_out", "over_band", "under_band"])
def test_NEGATIVE_each_skip_reason(sym, rows, reason):
    res = PN.resolve(_names(sym), rows, S, dict(TYPES, ZERO="CS", PENNY="CS"), [])
    assert res["added"] == [] and res["tagged"] == [] and res["skips"] == {reason: [sym]}
    assert reason in PN.SKIP_REASONS and PN.SKIP_WORDS[reason]


def test_a_below_floor_name_is_added_with_the_tag_and_the_row_is_gg_s_row():
    rows = {"LOWC": snap_row(2.10, 2.00, vol=300_000)}
    (r,) = PN.resolve(_names("LOWC"), rows, S, TYPES, [])["added"]
    assert r["source"] == PN.SOURCE == "promo" and r["promo"] is True
    assert r["promo_text"] == "🎪 promo · first tag 09:30 ET · @ShangVXO · tier S"
    assert r["volume"] < GC.SCAN_MIN_VOLUME and r["change_pct"] < GC.SCAN_MIN_CHANGE_PCT    # no floors for the ADD
    gg_shape, _ = TN.candidate_row("LOWC", rows, S.isoformat(), TYPES)
    assert {k: v for k, v in r.items() if k not in ("source", "promo", "promo_text")} == gg_shape
    assert "trader" not in r                                             # NEGATIVE: never a 📌 field


def test_order_by_todays_change_and_the_cap_counts_over_cap(monkeypatch):
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 2)
    rows = {"AAA": snap_row(2.2, 2.0), "BBB": snap_row(3.0, 2.0), "CCC": snap_row(2.1, 2.0),
            "DDD": snap_row(2.6, 2.0), "EEE": snap_row(2.6, 2.0)}
    types = {s: "CS" for s in rows}
    res = PN.resolve(_names("AAA", "BBB", "CCC", "DDD", "EEE"), rows, S, types, [])
    assert [r["symbol"] for r in res["added"]] == ["BBB", "DDD"]          # +50%, then +30% (tie → symbol)
    assert res["skips"] == {"over_cap": ["EEE", "AAA", "CCC"]}           # counted, highest change first
    blk = {"added": ["BBB", "DDD"], "tagged": [], "skips": res["skips"], "names": 5}
    assert PN.skip_text(blk).startswith("🎪 not on the list: 3 past the ")


def test_NEGATIVE_a_listed_name_is_tagged_never_added_and_never_counts_against_the_cap(monkeypatch):
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 1)
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    trader_add = dict(TN.candidate_row("MXCT", {"MXCT": snap_row(2.1, 2.0, vol=300_000)}, S.isoformat(), TYPES)[0],
                      source="trader", trader=KEY, trader_text=f"{GC.TRADER_TAG} algo888")
    quals = q + [trader_add]
    rows = {"GPUS": snap_row(0.19, 0.15, vol=40_000_000), "MXCT": snap_row(2.1, 2.0, vol=300_000),
            "LOWC": snap_row(2.1, 2.0, vol=300_000)}
    res = PN.resolve(_names("GPUS", "MXCT", "LOWC"), rows, S, TYPES, quals)
    assert res["tagged"] == ["GPUS", "MXCT"] and [r["symbol"] for r in res["added"]] == ["LOWC"]
    assert res["skips"] == {}
    assert quals[0]["promo"] is True and "source" not in quals[0]        # GG's row: tagged in place
    # precedence: a 📌 add keeps its trader fields AND gains the 🎪 tag (two chips)
    assert quals[1]["source"] == "trader" and quals[1]["trader"] == KEY and quals[1]["promo"] is True
    assert quals[1]["trader_text"] == f"{GC.TRADER_TAG} algo888" and quals[1]["promo_text"].startswith("🎪 promo")


def test_NEGATIVE_a_raising_walk_never_tags_listed_rows(monkeypatch):
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    monkeypatch.setattr(TN, "candidate_row", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    with pytest.raises(RuntimeError):
        PN.resolve(_names("GPUS", "LOWC"), {"LOWC": snap_row(2.1, 2.0)}, S, TYPES, q)
    assert "promo" not in q[0] and "promo_text" not in q[0]


def test_the_trader_add_check_is_unchanged_by_the_shared_helper():
    """trader_names.resolve now calls candidate_row — its reasons and its Row are byte for byte as before."""
    rows = {"MXCT": snap_row(2.10, 2.00, vol=300_000), "BIGC": snap_row(150.0, 140.0)}
    names = [{"symbol": s, "trader": KEY, "at": "x", "post_id": "st1", "text": ""} for s in ("MXCT", "BIGC", "NOPE")]
    res = TN.resolve(names, rows, S, TYPES, [])
    assert [r["symbol"] for r in res["added"]] == ["MXCT"]
    assert res["skips"] == [{"symbol": "BIGC", "trader": KEY, "reason": "out_of_band"},
                            {"symbol": "NOPE", "trader": KEY, "reason": "not_in_snapshot"}]
    assert "candidate_row(" in inspect.getsource(TN.resolve) and "candidate_row(" in inspect.getsource(PN.resolve)


# ── the pass (run.py) ─────────────────────────────────────────────────────────────────────────────────────────────
def test_the_pass_lists_the_promo_names_and_counts_them():
    st = fake_store()
    d, _snap, _send, status = deps_for(worked_rows())
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["errors"] == []
    c = out["counts"]
    assert (c["qualifiers"], c["trader_added"], c["trader_tagged"]) == (2, 1, 0)
    assert {k: c[k] for k in PN.COUNT_KEYS} == {"promo_added": 2, "promo_tagged": 2, "promo_skipped": 3,
                                                "promo_over_cap": 0, "promo_failed": 0}
    blk = out["promo"]
    assert blk["added"] == ["HIGH", "LOWC"] and blk["tagged"] == ["GPUS", "MXCT"] and blk["names"] == 7
    assert blk["skips"] == {"not_in_snapshot": ["NOPE"], "not_dated_session": ["STALE"], "out_of_band": ["BIGC"]}
    docs = {x["symbol"]: x["last"] for x in st.scan_docs([S])}
    assert set(docs) == {"GPUS", "ZZZ", "MXCT", "HIGH", "LOWC"}          # NEGATIVE: YDAY / skipped names never written
    assert docs["LOWC"]["source"] == "promo" and docs["LOWC"]["promo"] is True
    assert docs["GPUS"]["promo"] is True and "source" not in docs["GPUS"]
    assert docs["MXCT"]["source"] == "trader" and docs["MXCT"]["trader"] == KEY and docs["MXCT"]["promo"] is True
    assert sorted(out["qualifiers"]) == ["GPUS", "ZZZ"] and out["n_listed"] == 5  # GG's own list stays GG's
    assert "promo" not in docs["ZZZ"] and "promo_text" not in docs["ZZZ"]   # NEGATIVE: an untagged row, byte as before
    ctx = st.get_read(S, "LOWC")["ctx"]
    assert ctx["promo"] is True and ctx["promo_text"] == "🎪 promo · first tag 09:41 ET · @PSM_EmpowerTrading · tier B"
    assert "promo" not in st.get_read(S, "ZZZ")["ctx"] and "promo_text" not in st.get_read(S, "ZZZ")["ctx"]
    assert st.latest_pass()["promo"]["added"] == ["HIGH", "LOWC"]         # the pass doc carries the block
    assert st.latest_pass()["counts"]["promo_added"] == 2
    (counts, _n, _r), _ = status.calls[0]
    assert counts["promo_added"] == 2 and counts["qualifiers"] == 2      # the /alerts row's count


def _pass_doc(d, st=None):
    st = st or fake_store()
    RUN.run_pass(NOW, store=st, deps=d)
    doc = copy.deepcopy(st.latest_pass())
    doc.pop("lease", None)
    scan = sorted((x["symbol"], json.dumps(x["last"], sort_keys=True, default=str)) for x in st.scan_docs([S]))
    reads = sorted((x["symbol"], json.dumps(x.get("ctx"), sort_keys=True, default=str)) for x in st.reads(S))
    return json.dumps(doc, sort_keys=True, default=str), scan, reads


@pytest.mark.parametrize("tags", [[], [tag("YDAY", first=at(9, 0, d=PREV))], [tag("XXX", "not_on_roster")]],
                         ids=["no_tags", "only_yesterday", "off_roster"])
def test_NEGATIVE_an_empty_source_is_byte_identical_to_an_unwired_one(tags):
    """D2: an empty Promo source adds NO key — the pass doc, the scan docs and the read docs are byte for byte the
    pass without the source."""
    base = _pass_doc(deps_for(worked_rows(), wired=False)[0])
    got = _pass_doc(deps_for(worked_rows(), tags)[0])
    assert got == base
    assert '"promo' not in base[0] and "promo_held" not in base[0]


def test_NEGATIVE_a_failed_snapshot_reads_nothing_and_adds_no_key():
    st = fake_store()
    d, *_ = deps_for(worked_rows(), http=500)
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert "promo" not in out and d.promo_tags.calls == []
    assert not any(k.startswith("promo_") for k in out.get("counts") or {})


def test_NEGATIVE_a_raising_reader_adds_nothing_and_counts_promo_failed():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    d.promo_tags = Rec(lambda now: (_ for _ in ()).throw(RuntimeError("mongo down")))
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["status"] == "ok" and out["errors"] == [] and out["promo"] == {"error": "RuntimeError"}
    assert {k: out["counts"][k] for k in PN.COUNT_KEYS} == {"promo_added": 0, "promo_tagged": 0, "promo_skipped": 0,
                                                             "promo_over_cap": 0, "promo_failed": 1}
    assert {x["symbol"] for x in st.scan_docs([S])} == {"GPUS", "ZZZ", "MXCT"}   # GG's + the 📌 add, as before
    assert not any("promo" in x["last"] for x in st.scan_docs([S]))
    assert PN.strip_text(out["promo"]) is None and PN.skip_text(out["promo"]) is None


def test_NEGATIVE_a_raising_resolve_leaves_the_scan_untouched(monkeypatch):
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    monkeypatch.setattr(PN, "resolve", lambda *a, **k: (_ for _ in ()).throw(KeyError("boom")))
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["promo"] == {"error": "KeyError"} and out["counts"]["promo_failed"] == 1
    assert sorted(out["qualifiers"]) == ["GPUS", "ZZZ"] and not any("promo" in x["last"] for x in st.scan_docs([S]))


def test_a_split_held_add_leaves_the_block_and_the_counts():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    d.fetch_splits = lambda sym, since: ([{"execution_date": S.isoformat()}] if sym == "LOWC" else [])
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert out["promo"]["added"] == ["HIGH"] and out["counts"]["promo_added"] == 1
    assert out["counts"]["qualifiers"] == 2 and "LOWC" not in {x["symbol"] for x in st.scan_docs([S])}


def test_recount_and_trim_are_no_ops_without_the_source():
    r = {"qualifiers": [{"symbol": "A"}, {"symbol": "B", "source": "trader"}], "counts": {"qualifiers": 1}}
    before = json.dumps(r, sort_keys=True)
    PN.recount(r)
    assert json.dumps(r, sort_keys=True) == before                        # NEGATIVE: no promo key invented
    r2 = {"qualifiers": [{"symbol": "A"}, {"symbol": "B", "source": "trader"}, {"symbol": "C", "source": "promo"}],
          "counts": {"qualifiers": 2, "promo_added": 9}}
    PN.recount(r2)
    assert r2["counts"] == {"qualifiers": 1, "promo_added": 1}
    for b in ({"error": "KeyError"}, None):
        snap = json.dumps(b)
        PN.trim_block(b, r2)
        assert json.dumps(b) == snap


def test_main_wires_the_stored_reader_and_default_deps_never_do():
    assert RUN.Deps().promo_tags is None and "promo_tags" not in inspect.getsource(RUN.dry_deps)
    src = inspect.getsource(RUN.main)
    assert "promo_tags=PN.default_tags" in src and src.count("promo_tags=PN.default_tags") == 2
    body = inspect.getsource(RUN.run_pass)
    i, j, k = body.index("TN.run_step("), body.index("PN.run_step("), body.index("SC.record_scan(")
    assert i < j < k and body.index("PN.recount(result)") > body.index("TN.recount(result)") > k


def test_default_tags_is_one_stored_read_never_a_sweep(monkeypatch):
    seen = []

    class Coll:
        def find(self, q):
            seen.append(q)
            return [tag("AAA")]

    monkeypatch.setattr(PC, "_tags_coll", lambda: Coll())
    monkeypatch.setattr(PC, "sweep", lambda *a, **k: pytest.fail("the pass never sweeps"))
    monkeypatch.setattr(PC, "_fetch_user_stream", lambda *a, **k: pytest.fail("the pass never fetches"))
    assert [d["ticker"] for d in PN.default_tags(NOW)] == ["AAA"]
    assert seen == [{"last_tagged_at": {"$gte": NOW.astimezone(UTC) - timedelta(days=PC.TAG_WINDOW_DAYS)}}]
    monkeypatch.setattr(PC, "_tags_coll", lambda: None)
    with pytest.raises(RuntimeError):                                    # NEGATIVE: a dead store is a failure, counted
        PN.default_tags(NOW)


# ── 🧠 the 1M hold on a 🎪 add (GG5 and GG1) ──────────────────────────────────────────────────────────────────────
def _pot(st, now, sym, *, hold, frames=None, send=None, promo=True):
    from tests.test_gajjala_potential import bf_armed, frame_at
    send = send or Rec(OK_SEND)
    ctx = {"promo": True, "promo_text": "🎪 promo · first tag 09:30 ET · @ShangVXO · tier S"} if promo else {}
    out = PT.run_pass({sym: {"bull_flag": bf_armed()}}, frames or {sym: frame_at(now)}, now, S, store=st,
                      ctx={sym: ctx}, rows={sym: {"volume": (hold or {}).get(sym), "price": 2.1}}, send=send,
                      owner="owner@example.com", tape="rth", promo_hold=hold)
    return out, send


def test_NEGATIVE_a_below_floor_promo_add_never_rings_the_potential_push_gg5():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    out, send = _pot(st, at(10, 36), "LOWC", hold={"LOWC": 300_000})
    assert send.calls == [] and out["promo_held"] == 1 and out["pushed"] == 0 and out["trader_held"] == 0
    assert list(out)[-1] == "promo_held" and tuple(out)[:len(PT.COUNT_KEYS)] == PT.COUNT_KEYS
    doc = st.get_potential(S, "LOWC", "bull_flag")
    assert "push" not in doc and [h["reason"] for h in doc["held"]] == list(PT.PROMO_HELD)
    assert doc["promo"] is True and doc["promo_text"].startswith("🎪 promo")
    assert GT._track_row(doc)["push_text"] == PN.PROMO_HOLD_TEXT == (
        f"held: 🎪 under GG's {GC.SCAN_MIN_VOLUME // 1_000_000}M volume floor — listed and read, not rung")
    out2, send2 = _pot(st, at(10, 41), "LOWC", hold={"LOWC": None})       # an unknown volume: fail closed
    assert send2.calls == [] and out2["pushed"] == 0


def test_the_same_promo_add_over_the_floor_pushes_with_the_tag_gg5():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    send = Rec(OK_SEND)
    _pot(st, at(10, 36), "LOWC", hold={"LOWC": 300_000}, send=send)
    out, _ = _pot(st, at(10, 41), "LOWC", hold={"LOWC": 1_200_000}, send=send)
    assert out["pushed"] == 1 and len(send.calls) == 1 and out["promo_held"] == 0
    body = send.calls[0][0][1]["body"]
    assert "🎪 promo · first tag 09:30 ET" in body
    from tests.test_gajjala_potential import bf_armed
    plain = PT.compose("LOWC", "bull_flag", bf_armed(), "armed", {}, first_seen_et="10:36", tape="rth")
    assert send.calls[0][0][1]["title"] == plain["title"]                 # the title is UNCHANGED


def test_NEGATIVE_no_promo_map_means_no_count_key_and_a_trader_add_keeps_its_own_hold():
    from tests.test_gajjala_potential import bf_armed, frame_at, seed
    st = fake_store()
    seed(st)
    out = PT.run_pass({"MXCT": {"bull_flag": bf_armed()}}, {"MXCT": frame_at(at(10, 36))}, at(10, 36), S, store=st,
                      ctx={"MXCT": {"trader": KEY, "promo": True}}, rows={}, send=Rec(OK_SEND),
                      owner="owner@example.com", tape="rth", trader_hold={"MXCT": 300_000})
    assert tuple(out) == PT.COUNT_KEYS and out["trader_held"] == 1        # no promo_held key; 📌 decides a 📌 add
    assert [h["reason"] for h in st.get_potential(S, "MXCT", "bull_flag")["held"]] == list(PT.TRADER_HELD)
    assert PT.ADD_HELD == PT.TRADER_HELD + PT.PROMO_HELD and PT.PROMO_HELD == (PN.HOLD_REASON,)
    assert not set(PT.PROMO_HELD) & set(PT.HELD_WORDS) and PT.COUNT_KEYS[-1] == "trader_held"


def test_NEGATIVE_a_promo_tagged_gg_qualifier_is_never_held():
    from tests.test_gajjala_potential import seed
    st = fake_store()
    seed(st)
    out, send = _pot(st, at(10, 36), "GPUS", hold={})                     # tagged, not an add → not in the map
    assert out["pushed"] == 1 and out["promo_held"] == 0 and len(send.calls) == 1
    assert PN.added_symbols([], [{"symbol": "GPUS", "promo": True}]) == set()
    assert PN.added_symbols([{"symbol": "LOWC", "date": "2026-10-12", "last": {"source": "promo"}}]) == {"LOWC"}
    assert PN.added_symbols([{"symbol": "LOWC", "date": "2026-10-12", "last": {"source": "promo"}}],
                            [{"symbol": "LOWC"}]) == set()                # a GG row of this pass decides


def _gg1():
    from tests.test_gajjala_variant_2026_10_27 import gg1_store
    return gg1_store()[0]


def _frame_1m(now):
    stamp = (now.astimezone(ET) - timedelta(seconds=60)).strftime("%Y-%m-%d %H:%M")
    return SimpleNamespace(as_of_bar_t={"1m": stamp, "5m": stamp}, f5=SimpleNamespace(c=[2.1]))


def test_NEGATIVE_a_below_floor_promo_add_never_rings_on_gg1_and_over_the_floor_it_does():
    from tests.test_gajjala_potential import seed
    assert V.push_mode(V.GG1) == "live"
    st = _gg1()
    seed(st)
    send = Rec(OK_SEND)
    now = at(10, 6)
    out, _ = _pot(st, now, "LOWC", hold={"LOWC": 300_000}, frames={"LOWC": _frame_1m(now)}, send=send)
    assert send.calls == [] and out["promo_held"] == 1 and out["pushed"] == 0
    assert [h["reason"] for h in st.get_potential(S, "LOWC", "bull_flag")["held"]] == list(PT.PROMO_HELD)
    later = now + timedelta(minutes=1)
    out2, _ = _pot(st, later, "LOWC", hold={"LOWC": 1_500_000}, frames={"LOWC": _frame_1m(later)}, send=send)
    assert out2["pushed"] == 1 and len(send.calls) == 1
    assert send.calls[0][0][1]["kind"] == V.GG1.push_kind_potential and "🎪 promo" in send.calls[0][0][1]["body"]


def test_gg1_iteration_hands_its_promo_adds_to_the_hold_and_the_tag_to_the_a_plus(monkeypatch):
    """run_1m reads the 🎪 adds off the shared scan docs (the GG5 list it inherits via listed_symbols) and copies the
    stored 🎪 ctx onto the A+ ctx — nothing recomputed."""
    from chart_maps.gajjala import run_1m as R1
    from tests import test_gajjala_run_1m_2026_10_27 as T1
    monkeypatch.setattr(R1, "_PREV_MEMO", {})
    monkeypatch.setattr(ST, "_VARIANT_STORES", {})
    db, shared, st = T1.world(monkeypatch)
    shared.record_qualifiers(S, T1.at(10, 6), [{"symbol": "GGA", "price": 11.2, "prev_close": 8.0, "change_pct": 40.0,
                                             "volume": 300_000, "source": "promo", "promo": True,
                                             "promo_text": "🎪 promo · x"}], "rth")
    shared.upsert_read(S, "GGA", {"ctx": dict(T1.CTX, promo=True, promo_text="🎪 promo · x"), "setups": {}},
                       now=T1.at(10, 6, 5))
    seen = {}
    real_pt, real_al = PT.run_pass, AL.run_pass
    monkeypatch.setattr(PT, "run_pass", lambda *a, **k: seen.setdefault("pt", k) and real_pt(*a, **k))
    monkeypatch.setattr(AL, "run_pass", lambda *a, **k: seen.setdefault("al", k) and real_al(*a, **k))
    out = R1.run_iteration(T1.NOW, store=st, deps=T1.deps())
    assert out["status"] == "ok"
    assert set(seen["pt"]["promo_hold"]) == {"GGA"} and seen["pt"]["trader_hold"] == {}
    assert seen["al"]["ctx"]["GGA"]["promo"] is True and seen["al"]["ctx"]["GGA"]["promo_text"] == "🎪 promo · x"
    # NEGATIVE: no 🎪 add on the list → promo_hold None (no count key)
    db2, shared2, st2 = T1.world(monkeypatch)
    seen.clear()
    R1.run_iteration(T1.NOW, store=st2, deps=T1.deps())
    assert seen["pt"]["promo_hold"] is None


def test_the_gg5_pass_holds_the_promo_add_and_rings_the_tagged_qualifier():
    """End to end: forming bull flags on every listed name; LOWC / HIGH (🎪 adds under 1M) are held; GPUS (GG's
    qualifier, 🎪-tagged) rings."""
    from tests.test_gajjala_potential import seed
    today = minutes_from_5m(FX.bf_bars(entry=None), S, "10:00")
    st = fake_store()
    seed(st)
    d, *_ = deps_for(worked_rows(), load=lambda sym, day: PRIOR_1M.copy() if day == PREV else today.copy())
    out = RUN.run_pass(at(10, 36), store=st, deps=d)
    pushed = [a[1]["ticker"] for a, _k in d.send_potential.calls]
    assert "GPUS" in pushed and not set(PROMO_ROWS) & set(pushed)
    assert out["potential"]["promo_held"] >= 1
    assert [h["reason"] for h in st.get_potential(S, "LOWC", "bull_flag")["held"]] == list(PT.PROMO_HELD)
    assert st.latest_pass()["potential"]["promo_held"] == out["potential"]["promo_held"]


# ── A+ claim + 🏁 ledger stamp ────────────────────────────────────────────────────────────────────────────────────
def test_a_tagged_aplus_push_and_claim_carry_promo_and_the_title_is_unchanged():
    st = fake_store()
    d, _snap, send, _st = deps_for({"GGA": snap_row(11.2, 8.0)}, tags=[tag("GGA")], posts=[])
    out = RUN.run_pass(NOW, store=st, deps=d)
    assert "GGA:bull_flag" in out["aplus"] and out["promo"]["tagged"] == ["GGA"]
    (payload,) = [a[1] for a, _k in send.calls if a[1]["ticker"] == "GGA"]
    assert "🎪 promo · first tag 08:30 ET · @ShangVXO · tier S" in payload["body"]
    plain = AL.compose(st.get_read(S, "GGA")["setups"]["bull_flag"], "GGA", {}, session=S)
    assert payload["title"] == plain["title"] and GC.PROMO_TAG not in payload["title"]
    claim = st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"]
    assert claim["promo"] is True and claim["promo_text"].startswith("🎪 promo") and "trader" not in claim


def test_NEGATIVE_an_untagged_aplus_claim_has_no_promo_key():
    st = fake_store()
    d, _snap, send, _st = deps_for({"GGA": snap_row(11.2, 8.0)}, tags=[], posts=[])
    RUN.run_pass(NOW, store=st, deps=d)
    (payload,) = [a[1] for a, _k in send.calls]
    assert GC.PROMO_TAG not in payload["body"]
    assert not {"promo", "promo_text"} & set(st.alerts_coll().docs["GG:2026-10-13|GGA|bull_flag"])


def test_ledger_row_stamps_promo_and_serves_promo_text_only_when_tagged():
    from tests.test_gajjala_track_record_tab import D16, NOW as TR_NOW, _et, pot_doc
    txt = "🎪 promo · first tag 09:30 ET · @ShangVXO · tier S"
    tagged = dict(pot_doc(D16, "LOWC", "bull_flag", _et(D16, 10, 2), trigger=2.2, stop=2.0, px=2.1), promo=True,
                  promo_text=txt)
    plain = pot_doc(D16, "ZZZ", "bull_flag", _et(D16, 10, 12), trigger=2.2, stop=2.0, px=2.1)
    r = LG.alert_of(tagged, "potential")
    assert r["promo"] is True and r["promo_text"] == txt and r["trader"] is None
    assert not {"promo", "promo_text"} & set(LG.alert_of(plain, "potential"))   # NEGATIVE: the row shape of before
    claim = {"_id": "GG:2026-10-16|GGA|bull_flag", "date": "2026-10-16", "symbol": "GGA", "setup": "bull_flag",
             "state": "pushed", "trigger": 4.12, "stop": 3.95, "at": _et(D16, 10, 31).isoformat(), "promo": True,
             "promo_text": txt}
    assert LG.alert_of(claim, "aplus")["promo_text"] == txt
    st = fake_store(**{ST.POTENTIALS: FakeColl([tagged, plain])})
    out = GT.build(GC.LEDGER_SUB, span="today", now=TR_NOW, store=st, today=None)
    rows = {x["symbol"]: x for d_ in out["track_record"]["days"] for x in d_["rows"]}
    assert rows["LOWC"]["promo_text"] == txt and "promo_text" not in rows["ZZZ"]


def test_NEGATIVE_a_replayed_row_never_carries_promo():
    from tests.test_gajjala_ledger_replay import replay_doc
    doc = dict(replay_doc(), promo=True, promo_text="x")
    row = LG.alert_of(doc, "aplus")
    assert row is not None and row["line"] == LG.LINES[2] and "promo" not in row


# ── the tab: strip, chips, legend ─────────────────────────────────────────────────────────────────────────────────
def _board(sub="bull_flag", tags=None, wired=True):
    st = fake_store()
    d, *_ = deps_for(worked_rows(), tags, wired=wired)
    RUN.run_pass(NOW, store=st, deps=d)
    return GT.build(sub, now=at(10, 42), store=st), st


def test_strip_serves_the_promo_line_and_the_counted_skip_line():
    out, _st = _board()
    s = out["strip"]
    assert s["promo_text"] == (
        "🎪 4 of today's 7 Promo-circuit names on this pass's list (2 added, 2 already listed) — your call 2026-10-29; "
        "the Promo circuit's first tags read INVERTED in this app's study — a watchlist for GG's rules, not an edge; "
        "UNMEASURED on his setups; GG's rules decide every read and every A+, and " + TN.FLOOR_CLAUSE)
    assert s["promo_skip_text"] == ("🎪 not on the list: 1 not in today's market snapshot; 1 no print dated today yet; "
                                    "1 outside GG's $0.10–$100 band")
    assert s["trader_text"] and s["trader_text"].startswith(GC.TRADER_TAG)   # the 📌 line is untouched


def test_NEGATIVE_no_source_means_no_strip_key_no_chip_and_no_legend_row():
    out, _st = _board(wired=False)
    assert "promo_text" not in out["strip"] and "promo_skip_text" not in out["strip"]
    assert all("promo_text" not in t for t in out["tiles"])
    assert out["counts_legend"] == GT.count_legend() and out["counts_legend"][-1]["key"] == "trader"
    empty, _ = _board(tags=[])
    assert "promo_text" not in empty["strip"] and empty["counts_legend"] == GT.count_legend()


def test_tiles_and_rows_carry_promo_text_and_untagged_rows_have_no_key():
    out, _st = _board()
    tiles = {t["symbol"]: t for t in out["tiles"]}
    assert {"GPUS", "LOWC", "HIGH", "MXCT", "ZZZ"} <= set(tiles)
    assert tiles["LOWC"]["promo_text"] == "🎪 promo · first tag 09:41 ET · @PSM_EmpowerTrading · tier B"
    assert tiles["GPUS"]["promo_text"].startswith("🎪 promo")
    assert tiles["MXCT"]["promo_text"].startswith("🎪 promo") and tiles["MXCT"]["trader_text"] == \
        f"{GC.TRADER_TAG} algo888"                                         # two chips on a 📌+🎪 name
    assert "promo_text" not in tiles["ZZZ"] and tiles["ZZZ"]["trader_text"] is None   # NEGATIVE: untagged → no key
    probe = {"tiles": [{"symbol": "LOWC"}, {"symbol": "ZZZ"}], "potential": {"rows": [{"symbol": "LOWC"}]},
             "track": {"today": {"rows": [{"symbol": "LOWC"}]}, "yesterday": {"rows": [{"symbol": "X"}]}},
             "watch": {"symbols": [{"symbol": "LOWC"}]}, "postmarket": {"recap": {"rows": [{"symbol": "LOWC"}]}},
             "enterable": {"rows": [{"symbol": "LOWC"}]}}
    GT._promo_tag(probe, {"LOWC": {"promo": True, "promo_text": "🎪 promo · y"}})
    assert probe["tiles"][0]["promo_text"] == "🎪 promo · y" and "promo_text" not in probe["tiles"][1]
    for got in (probe["potential"]["rows"][0], probe["track"]["today"]["rows"][0], probe["watch"]["symbols"][0],
                probe["postmarket"]["recap"]["rows"][0], probe["enterable"]["rows"][0]):
        assert got["promo_text"] == "🎪 promo · y"
    assert "promo_text" not in probe["track"]["yesterday"]["rows"][0]


def test_the_tag_is_served_to_every_viewer():
    st = fake_store()
    d, *_ = deps_for(worked_rows())
    RUN.run_pass(NOW, store=st, deps=d)
    for owner in (False, True):
        tiles = {t["symbol"]: t for t in GT.build("bull_flag", now=at(10, 42), store=st, owner=owner)["tiles"]}
        assert tiles["LOWC"]["promo_text"].startswith("🎪 promo"), owner


def test_legend_gains_the_promo_row_last_only_when_the_source_ran():
    leg = GT.count_legend(promo=True)
    assert [r["key"] for r in leg] == list(GT.LEGEND_KEYS_PROMO) and GT.LEGEND_KEYS_PROMO[-1] == "promo"
    assert leg[-1] == PN.legend_row() and leg[-2] == TN.legend_row() and leg[:-1] == GT.count_legend()
    t = leg[-1]["text"]
    assert "INVERTED" in t and "UNMEASURED" in t and f"at most {GC.PROMO_NAMES_MAX} a session" in t
    assert t.endswith(TN.FLOOR_CLAUSE)
    out, _st = _board()
    assert out["counts_legend"] == leg                                    # the board that ran it serves it
    assert GT.LEGEND_KEYS[-1] == "trader"                                 # NEGATIVE: the base legend keeps its keys


def test_tag_map_newest_doc_wins_and_rows_override():
    docs = [{"symbol": "AAA", "date": "2026-10-12", "last": {"promo": True, "promo_text": "🎪 a"}},
            {"symbol": "AAA", "date": "2026-10-13", "last": {}},
            {"symbol": "BBB", "date": "2026-10-09", "last": {"promo": True, "promo_text": "🎪 b"}},
            {"symbol": "CCC", "date": "2026-10-13", "last": {"promo": "yes"}}]
    m = PN.tag_map(docs)
    assert m == {"BBB": {"promo": True, "promo_text": "🎪 b"}}           # NEGATIVE: a truthy non-bool is no tag
    assert set(PN.tag_map(docs, [{"symbol": "AAA", "promo": True}, {"symbol": "BBB"}])) == {"AAA"}


# ── ℹ️ rules + /alerts/status ─────────────────────────────────────────────────────────────────────────────────────
def test_rules_note_carries_the_promo_clause_built_from_the_module():
    from supply_demand import rules_info as RI
    sec = RI._gajjala_section()
    clause = PN.rules_clause()
    assert (" " + clause) in sec["note"] and sec["note"].endswith("Not advice.")
    assert len(sec["picks"]) == 8 and sec["picks"][0].endswith(" " + TN.rules_clause())   # the 📌 pick untouched
    assert f"at most {GC.PROMO_NAMES_MAX} a session" in clause and "INVERTED" in clause and "UNMEASURED" in clause
    assert f"{PC.TAG_WINDOW_DAYS}-day window" in clause and TN.FLOOR_CLAUSE in clause
    assert "Cheetah defaults (yours, not GG's)" in clause and not B_WORD.search(clause)
    assert sec["note"].index(clause) < sec["note"].index("-minute page")  # before the one-minute clause


def test_NEGATIVE_a_broken_module_never_breaks_the_panel(monkeypatch):
    from supply_demand import rules_info as RI
    monkeypatch.setattr(PN, "rules_clause", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    assert RI._gg_promo_clause() == ""
    assert "Promo names" not in RI._gajjala_section()["note"]


def test_alerts_status_serves_the_promo_hold_words_on_rows_and_the_chip():
    from supply_demand import alert_status as AS
    from tests.test_gajjala_potential_kind import NOW as PK_NOW, PassColl, TrackerColl, _doc
    c = TrackerColl([_doc("LOWC", "bull_flag", held=[{"at_et": "09:41", "reason": PN.HOLD_REASON}]),
                     _doc("MXCT", "bull_flag", held=[{"at_et": "09:41", "reason": TN.HOLD_REASON}]),
                     _doc("GGB", "kiss_fly", held=[{"at_et": "09:36", "reason": "muted"}])])
    items = {i["symbol"]: i for i in AS.read_gajjala_potentials(c, PK_NOW)}
    assert items["LOWC"]["held_text"] == PN.PROMO_HOLD_TEXT and items["MXCT"]["held_text"] == TN.TRADER_HOLD_TEXT
    assert "held_text" not in items["GGB"]
    pc = PassColl()
    AS.record_pass("gajjala_potential", {"potential": 1, "trader_held": 0, "promo_held": 2}, PK_NOW, coll=pc)
    row = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=PK_NOW, potential_coll=c)["passes"][
        "gajjala_potential"]
    assert row["promo_held_text"] == PN.PROMO_HOLD_TEXT and row["counts"]["promo_held"] == 2
    assert "trader_held_text" not in row


@pytest.mark.parametrize("counts", [{"potential": 1, "promo_held": 0}, {"potential": 1}, {}])
def test_NEGATIVE_no_promo_hold_means_no_served_chip_words(counts):
    from supply_demand import alert_status as AS
    from tests.test_gajjala_potential_kind import NOW as PK_NOW, PassColl, TrackerColl
    pc = PassColl()
    if counts:
        AS.record_pass("gajjala_potential", counts, PK_NOW, coll=pc)
    row = AS.status_payload(pass_coll=pc, latest_coll=PassColl(), now=PK_NOW, potential_coll=TrackerColl())["passes"][
        "gajjala_potential"]
    assert "promo_held_text" not in row
    assert PN.held_text("muted") is None and PN.held_text(None) is None and PN.held_text(TN.HOLD_REASON) is None


# ── words ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def test_NEGATIVE_no_b_word_no_edge_claim_and_the_caveat_on_every_served_line():
    from pathlib import Path
    blk = {"added": ["A"], "tagged": [], "skips": {"over_cap": ["B"]}, "names": 2}
    texts = [PN.strip_text(blk), PN.skip_text(blk), PN.PROMO_HOLD_TEXT, PN.rules_clause(), PN.legend_row()["text"],
             *PN.SKIP_WORDS.values()]
    assert not B_WORD.search(Path(PN.__file__).read_text(encoding="utf-8"))
    for t in texts:
        assert not B_WORD.search(t) and "will " not in t.lower(), t
        low = t.lower()
        assert "edge" not in low or "not an edge" in low, t
    for t in (PN.strip_text(blk), PN.rules_clause(), PN.legend_row()["text"]):
        assert "INVERTED" in t and "UNMEASURED" in t, t


def test_the_doc_carries_his_words_the_caveat_and_the_his_calls():
    from pathlib import Path
    doc = (Path(__file__).resolve().parents[2] / "docs" / "gajjala" / "promo_names_2026_10_29.md").read_text(
        encoding="utf-8")
    assert ("should we pull stocks from PROMO circuit by default every day they are having some good catched but\n"
            "I do wanna run them against Gajjalas strategies") in doc or (
        "should we pull stocks from PROMO circuit by default every day they are having some good catched but I do "
        "wanna run them against Gajjalas strategies") in doc
    assert "INVERTED" in doc and "UNMEASURED" in doc and "GG1M_MAX_NAMES" in doc
    for n in range(1, 7):
        assert f"HIS CALL #{n}" in doc, n
    assert not B_WORD.search(doc)
    trader_doc = (Path(__file__).resolve().parents[2] / "docs" / "gajjala" / "trader_names_2026_10_27.md").read_text(
        encoding="utf-8")
    assert "promo_names_2026_10_29.md" in trader_doc


# ── critic F3 (2026-10-29): the cap bounds the SESSION's listed 🎪 adds; GG's names load first; /alerts rows ────────
def _two_passes(monkeypatch, cap=1):
    """Pass 1 (10:31): HIGH +20% outranks LOWC +5%. Pass 2 (10:41): LOWC +100% outranks HIGH +2.5%."""
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", cap)
    st = fake_store()
    tags = [tag("LOWC", B_ACCT, first=at(9, 41)), tag("HIGH", first=at(7, 5))]
    r1 = worked_rows(LOWC=snap_row(2.10, 2.00, vol=300_000, when=at(10, 30)),
                     HIGH=snap_row(4.80, 4.00, vol=500_000, when=at(10, 30)))
    o1 = RUN.run_pass(at(10, 31), store=st, deps=deps_for(r1, tags)[0])
    r2 = worked_rows(LOWC=snap_row(4.0, 2.00, vol=300_000), HIGH=snap_row(4.10, 4.00, vol=500_000))
    o2 = RUN.run_pass(NOW, store=st, deps=deps_for(r2, tags)[0])
    return st, o1, o2


def test_NEGATIVE_the_cap_bounds_the_sessions_listed_promo_names_not_each_pass(monkeypatch):
    """The critic's churn: with a cap of 1, a later pass that ranks another name higher must NOT list a second 🎪 add —
    the name an earlier pass added keeps its slot (re-read), the newcomer is over the cap and never written."""
    st, o1, o2 = _two_passes(monkeypatch)
    assert o1["promo"]["added"] == ["HIGH"] and o1["promo"]["skips"] == {"over_cap": ["LOWC"]}
    assert o2["promo"]["added"] == ["HIGH"] and o2["promo"]["skips"] == {"over_cap": ["LOWC"]}
    assert o2["promo"]["kept"] == []
    listed = SC.listed_symbols(st, S)
    assert "LOWC" not in listed and "HIGH" in listed                     # NEGATIVE: the newcomer is never listed
    assert PN.added_symbols(st.scan_docs(SC._window(S))) == {"HIGH"}
    assert PN.listed_today(st.scan_docs([S])) == {"HIGH"}
    assert o2["n_listed"] == o1["n_listed"] == 4
    assert {k: o2["counts"][k] for k in ("promo_added", "promo_over_cap")} == {"promo_added": 1, "promo_over_cap": 1}
    # the served words match the list: the over-cap name is the one NOT listed, the strip counts what is listed
    assert PN.skip_text(o2["promo"]) == "🎪 not on the list: 1 " + PN.SKIP_WORDS["over_cap"]   # words built at import
    assert PN.strip_text(o2["promo"]).startswith(
        "🎪 1 of today's 2 Promo-circuit names on this pass's list (1 added, 0 already listed)")


def test_with_room_a_later_pass_adds_the_newcomer_and_the_kept_name_stays(monkeypatch):
    st, _o1, o2 = _two_passes(monkeypatch, cap=2)
    assert o2["promo"]["added"] == ["LOWC", "HIGH"] and "over_cap" not in o2["promo"]["skips"]
    assert PN.listed_today(st.scan_docs([S])) == {"HIGH", "LOWC"}


def test_NEGATIVE_a_kept_name_that_fails_the_recheck_is_kept_never_a_skip_or_over_cap(monkeypatch):
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 1)
    rows = {"NEWC": snap_row(3.0, 2.0)}                                   # HIGH (kept) has no snapshot row this pass
    res = PN.resolve(_names("HIGH", "NEWC"), rows, S, dict(TYPES, NEWC="CS"), [], kept={"HIGH"})
    assert res["added"] == [] and res["kept"] == ["HIGH"]
    assert res["skips"] == {"over_cap": ["NEWC"]}                         # the kept slot leaves no room
    blk = {"added": [], "tagged": [], "kept": ["HIGH"], "skips": res["skips"], "names": 2}
    assert PN.strip_text(blk).startswith("🎪 1 of today's 2 Promo-circuit names on this pass's list (1 added, 0 ")
    assert "not in today's market snapshot" not in (PN.skip_text(blk) or "")


def test_a_kept_name_now_on_gg_s_own_list_frees_its_slot(monkeypatch):
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 1)
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    rows = {"GPUS": snap_row(0.19, 0.15, vol=40_000_000), "LOWC": snap_row(2.1, 2.0, vol=300_000)}
    res = PN.resolve(_names("GPUS", "LOWC"), rows, S, TYPES, q, kept={"GPUS"})
    assert res["tagged"] == ["GPUS"] and [r["symbol"] for r in res["added"]] == ["LOWC"] and res["skips"] == {}
    # NEGATIVE: with no kept set the per-session rule changes nothing for a first pass
    assert [r["symbol"] for r in PN.resolve(_names("LOWC"), rows, S, TYPES, [])["added"]] == ["LOWC"]


def test_NEGATIVE_flip_back_name_is_kept_never_over_cap_and_cap_holds(monkeypatch):
    """Verifier L1 (2026-10-29), cap 1. Pass 1: HIGH is the 🎪 add, LOWC over the cap. Pass 2: HIGH at +30% / 40M is
    GG's own name → tagged, its slot freed, LOWC added. Pass 3: HIGH back at +2.5% / 500k is off GG's list but still
    LISTED (scanner.listed_symbols): it stays listed off its stored doc — never a candidate, never over_cap, and the
    skip line never says a listed name is "not on the list"; the session lists one 🎪 add beyond GG's own names."""
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 1)
    st = fake_store()
    tags = [tag("LOWC", B_ACCT, first=at(9, 41)), tag("HIGH", first=at(7, 5))]
    r1 = worked_rows(LOWC=snap_row(2.10, 2.00, vol=300_000, when=at(10, 30)),
                     HIGH=snap_row(4.80, 4.00, vol=500_000, when=at(10, 30)))
    o1 = RUN.run_pass(at(10, 31), store=st, deps=deps_for(r1, tags)[0])
    r2 = worked_rows(LOWC=snap_row(2.10, 2.00, vol=300_000, when=at(10, 35)),
                     HIGH=snap_row(5.20, 4.00, vol=40_000_000, when=at(10, 35)))
    o2 = RUN.run_pass(at(10, 36), store=st, deps=deps_for(r2, tags)[0])
    r3 = worked_rows(LOWC=snap_row(2.10, 2.00, vol=300_000), HIGH=snap_row(4.10, 4.00, vol=500_000))
    o3 = RUN.run_pass(NOW, store=st, deps=deps_for(r3, tags)[0])
    assert o1["promo"]["added"] == ["HIGH"] and o1["promo"]["skips"] == {"over_cap": ["LOWC"]}
    assert o2["promo"]["tagged"] == ["HIGH"] and o2["promo"]["added"] == ["LOWC"]
    blk = o3["promo"]
    listed = sorted(SC.listed_symbols(st, S))
    assert listed == ["GPUS", "HIGH", "LOWC", "MXCT", "ZZZ"]
    assert "over_cap" not in blk["skips"] and not any("HIGH" in v for v in blk["skips"].values())
    assert blk["added"] == ["LOWC"] and blk["kept"] == ["HIGH"] and o3["counts"]["promo_over_cap"] == 0
    for sym in listed:                                                    # no listed name is ever "not on the list"
        assert not any(sym in v for v in blk["skips"].values()), sym
    assert PN.skip_text(blk) is None
    adds = PN.added_symbols(st.scan_docs(SC._window(S)))
    assert adds == {"LOWC"} and len(adds) <= GC.PROMO_NAMES_MAX           # the cap holds: one 🎪 add a session
    assert PN.listed_today(st.scan_docs([S])) == {"LOWC"}


def test_NEGATIVE_a_listed_name_off_this_pass_s_rows_is_kept_and_takes_no_slot(monkeypatch):
    monkeypatch.setattr(GC, "PROMO_NAMES_MAX", 1)
    rows = {"HIGH": snap_row(4.10, 4.00, vol=500_000), "NEWC": snap_row(3.0, 2.0)}
    types = dict(TYPES, NEWC="CS")
    res = PN.resolve(_names("HIGH", "NEWC"), rows, S, types, [], kept=(), listed={"high"})
    assert res["kept"] == ["HIGH"] and [r["symbol"] for r in res["added"]] == ["NEWC"] and res["skips"] == {}
    # NEGATIVE: unlisted, HIGH is a candidate again and the cap counts the lower one over_cap
    res = PN.resolve(_names("HIGH", "NEWC"), rows, S, types, [])
    assert [r["symbol"] for r in res["added"]] == ["NEWC"] and res["skips"] == {"over_cap": ["HIGH"]}
    # a kept (today's 🎪 add) name in the listed set still holds its slot; a qualifier is still tagged
    res = PN.resolve(_names("HIGH", "NEWC"), rows, S, types, [], kept={"HIGH"}, listed={"HIGH"})
    assert [r["symbol"] for r in res["added"]] == ["HIGH"] and res["skips"] == {"over_cap": ["NEWC"]}
    q = SC.scan_rows({"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, NOW, S, types=TYPES)["qualifiers"]
    res = PN.resolve(_names("GPUS"), {"GPUS": snap_row(0.19, 0.15, vol=40_000_000)}, S, TYPES, q, listed={"GPUS"})
    assert res["tagged"] == ["GPUS"] and res["kept"] == [] and q[0]["promo"] is True


def test_listed_today_reads_only_the_promo_adds():
    docs = [{"symbol": "aaa", "last": {"source": "promo"}}, {"symbol": "BBB", "last": {"source": "trader"}},
            {"symbol": "CCC", "last": {"promo": True}}, {"symbol": "DDD"}, {"last": {"source": "promo"}}, None]
    assert PN.listed_today(docs) == {"AAA"}
    assert PN.listed_today(None) == set()


def _frames_order(monkeypatch, d, st):
    from chart_maps.gajjala import bars as B
    seen = []
    real = B.frames_for

    def spy(symbols, *a, **k):
        seen.append(list(symbols))
        return real(symbols, *a, **k)

    monkeypatch.setattr(B, "frames_for", spy)
    out = RUN.run_pass(NOW, store=st, deps=d)
    return seen[0], out


def test_gg_s_own_names_are_loaded_before_the_adds(monkeypatch):
    st = fake_store()
    order, out = _frames_order(monkeypatch, deps_for(worked_rows())[0], st)
    assert order == ["GPUS", "ZZZ", "HIGH", "LOWC", "MXCT"]               # GG's first, then the 📌 / 🎪 adds
    listed = sorted(SC.listed_symbols(st, S))
    assert sorted(order) == listed and out["n_listed"] == len(listed)


def test_NEGATIVE_without_an_add_the_load_order_is_sorted_listed(monkeypatch):
    st = fake_store()
    order, _out = _frames_order(monkeypatch, deps_for(worked_rows(), [], posts=[])[0], st)
    assert order == sorted(SC.listed_symbols(st, S)) == ["GPUS", "ZZZ"]


def test_NEGATIVE_the_load_order_never_reorders_what_the_pass_writes(monkeypatch):
    """Only the load order moves: the read docs (and every later step) iterate in sorted(listed) order."""
    st = fake_store()
    calls = []
    real = st.upsert_read
    monkeypatch.setattr(st, "upsert_read", lambda session, sym, *a, **k: (calls.append(sym), real(session, sym, *a,
                                                                                                    **k))[1])
    RUN.run_pass(NOW, store=st, deps=deps_for(worked_rows())[0])
    assert calls == sorted(calls) and "LOWC" in calls


def test_alerts_status_rows_serve_the_promo_tag_only_on_a_tagged_doc():
    from supply_demand import alert_status as AS
    from tests.test_gajjala_potential_kind import NOW as PK_NOW, TrackerColl, _doc
    words = "🎪 promo · first tag 09:41 ET · @PSM_EmpowerTrading · tier B"
    c = TrackerColl([_doc("LOWC", "bull_flag", promo=True, promo_text=words), _doc("GGB", "kiss_fly"),
                     _doc("BARE", "bull_flag", promo=True), _doc("FAKE", "bull_flag", promo="yes", promo_text=words)])
    items = {i["symbol"]: i for i in AS.read_gajjala_potentials(c, PK_NOW)}
    assert items["LOWC"]["promo"] is True and items["LOWC"]["promo_text"] == words
    assert "promo" not in items["GGB"] and "promo_text" not in items["GGB"]          # NEGATIVE: untagged → no key
    assert items["BARE"]["promo"] is True and "promo_text" not in items["BARE"]      # a tag without words
    assert "promo" not in items["FAKE"] and "promo_text" not in items["FAKE"]        # NEGATIVE: a truthy non-bool
    day = PK_NOW.date().isoformat()

    def claim(sym, **kw):
        return dict({"_id": f"SHADOW:{day}:{sym}", "date": day, "state": "shadow", "symbol": sym, "setup": "bull_flag",
                     "at": PK_NOW, "would_push": {"title": "t", "items": [{"text": f"{sym} · line"}]}}, **kw)

    sh = {i["symbol"]: i for i in AS.read_gajjala_shadow(TrackerColl([claim("LOWC", promo=True, promo_text=words),
                                                                      claim("GGB")]), PK_NOW)}
    assert sh["LOWC"]["promo"] is True and sh["LOWC"]["promo_text"] == words
    assert "promo" not in sh["GGB"] and "promo_text" not in sh["GGB"]

