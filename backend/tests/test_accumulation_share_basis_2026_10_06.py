"""13F accumulation flow is measured in SHARES, not in price-drifted dollars (2026-10-06).

THE DEFECT. compare_maps subtracted the dollar VALUE of our stored prior-quarter
snapshot from today's. The provider values every holder at the price on the
day it was fetched, so the two pictures sat at two different prices. VST read
-$1,156,781,846 (-6.02%) "distributing" across 8 funds that net BOUGHT
+481,960 shares; Vanguard's share count was unchanged yet its value fell
$3.391B -> $3.174B on the price alone. The Sunday push could fire on that.

THE FIX. Per overlapping fund Δshares; any $ is Δshares at ONE common price
(today's snapshot price). A row with no share count is unknown — never rebuilt
from dollars. Funds joining/leaving the top-10 are list changes, not exits.
"""
from __future__ import annotations

import math
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from supply_demand import accumulation_changes as ac  # noqa: E402
from sepa import position_lens as pl                  # noqa: E402

# --- live VST, 2026-08-23 snapshot (03-31 quarter, dollars only) -------------
VST_PRIOR_USD = {
    "Blackrock Inc.": 4514418695.0,
    "Vanguard Capital Management LLC": 3391156482.0,
    "Vanguard Portfolio Management LLC": 2679170482.0,
    "State Street Corporation": 2658288692.0,
    "FMR, LLC": 2505727102.0,
    "Geode Capital Management, LLC": 1431927140.0,
    "Morgan Stanley": 1308807197.0,
    "JPMORGAN CHASE & CO": 1187185489.0,
    "Lone Pine Capital Llc": 980794064.0,
    "UBS Group AG": 728826418.0,
}
# The price that snapshot was valued at — Vanguard Capital's share count did
# not change between the filings (pct_change 0.0), so its $ / shares is it.
VST_PRIOR_PX = 3391156482.0 / 21393858.0              # $158.51

# --- live VST whales_cache payload, 06-30 quarter, valued at $148.38 ---------
VST_NOW = [
    ("Blackrock Inc.", 29064465.0, 4312585458.0),
    ("Vanguard Capital Management LLC", 21393858.0, 3174420754.0),
    ("Vanguard Portfolio Management LLC", 16939291.0, 2513452081.0),
    ("State Street Corporation", 16850452.0, 2500270150.0),
    ("FMR, LLC", 14160202.0, 2101090841.0),
    ("Geode Capital Management, LLC", 9037395.0, 1340968714.0),
    ("Morgan Stanley", 8880730.0, 1317722760.0),
    ("NORGES BANK", 5811201.0, 862266032.0),
    ("UBS Group AG", 5398501.0, 801029604.0),
    ("Goldman Sachs Group Inc", 4742324.0, 703666058.0),
]


def _vst_now_holders():
    return [{"holder": n, "shares": s, "value": v, "date_reported": "2026-06-30 00:00:00"}
            for n, s, v in VST_NOW]


def _vst_prior_shares():
    return {k: v / VST_PRIOR_PX for k, v in VST_PRIOR_USD.items()}


class _SnapColl:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    def insert_one(self, doc):
        self.docs.append(doc)

    def delete_many(self, *a, **kw):
        pass

    def find_one(self, q, sort=None):
        return self.docs[-1] if self.docs else None


def _payload(holders, q="2026-06-30"):
    return {"holders": holders, "period": {"dominant": q}}


# ---------------------------------------------------------------------------
# VST — the live case
# ---------------------------------------------------------------------------
def test_vst_reads_accumulating_on_shares_not_distributing_on_dollars():
    """REGRESSION (VST 2026-10-06). Same 8 funds, both pictures: shares rose
    ~+481,500 (+0.40%). The old dollar subtraction of the SAME pictures printed
    -$1.16B; that number must never come back."""
    now = _vst_now_holders()
    c = ac.compare_maps(_vst_prior_shares(), ac.share_map(now), ac.snapshot_price(now))
    assert c["basis"] == "shares"
    assert c["overlap_funds"] == 8
    assert c["direction"] == "accumulating"
    assert 470_000 < c["net_change_shares"] < 495_000
    assert c["net_change_pct"] == 0.4
    # $ = Δshares × today's ONE price ($148.38), so the sign follows the shares
    assert math.isclose(c["net_change_usd"], c["net_change_shares"] * c["price"], rel_tol=1e-6)
    assert c["net_change_usd"] > 0
    # NEGATIVE: the old dollar read of these very pictures was a large outflow
    both = set(VST_PRIOR_USD) & {n for n, _, _ in VST_NOW}
    dollar_diff = (sum(v for n, _, v in VST_NOW if n in both)
                   - sum(VST_PRIOR_USD[n] for n in both))
    assert round(dollar_diff) == -1_156_781_846
    assert c["net_change_usd"] != round(dollar_diff, 2)


def test_vanguard_unchanged_shares_read_zero_although_its_dollars_fell():
    """Vanguard Capital: 0 shares traded, value $3.391B -> $3.174B."""
    c = ac.compare_maps(
        {"Vanguard": 21393858.0, "B": 10.0, "C": 10.0},
        {"Vanguard": 21393858.0, "B": 10.0, "C": 10.0}, 148.38)
    assert c["net_change_shares"] == 0 and c["net_change_usd"] == 0
    assert c["direction"] == "flat"


def test_a_pure_price_move_is_never_significant():
    """NEGATIVE: the price halves, nobody trades — no flow, no push."""
    hs_then = [{"holder": f"F{i}", "shares": 1_000_000.0, "value": 200_000_000.0}
               for i in range(5)]
    hs_now = [{"holder": f"F{i}", "shares": 1_000_000.0, "value": 100_000_000.0}
              for i in range(5)]
    c = ac.compare_maps(ac.share_map(hs_then), ac.share_map(hs_now), ac.snapshot_price(hs_now))
    c["comparable"] = True
    assert c["net_change_usd"] == 0 and c["net_change_pct"] == 0
    assert ac.is_significant(c) is False


# ---------------------------------------------------------------------------
# unknown share counts — never a dollar fallback
# ---------------------------------------------------------------------------
def test_share_map_keeps_a_missing_share_count_unknown():
    m = ac.share_map([{"holder": "A", "shares": None, "value": 500.0},
                      {"holder": "B", "shares": float("nan"), "value": 500.0},
                      {"holder": "C", "shares": -5, "value": 500.0},
                      {"holder": "D", "shares": 7, "value": 500.0},
                      {"value": 1.0}])
    assert m == {"A": None, "B": None, "C": None, "D": 7.0}


def test_a_fund_without_shares_on_either_side_is_unknown_not_compared():
    c = ac.compare_maps({"A": 100.0, "B": 100.0, "C": 100.0, "D": None},
                        {"A": 110.0, "B": 100.0, "C": None, "D": 9e9}, 2.0)
    assert c["overlap_funds"] == 2
    assert c["unknown_funds"] == ["C", "D"]
    assert c["net_change_shares"] == 10                 # A only
    assert c["net_change_usd"] == 20                    # 10 sh × $2


def test_a_legacy_dollars_only_snapshot_is_not_comparable(monkeypatch):
    """NEGATIVE: every snapshot banked before 2026-10-06 holds dollars only.
    It must read 'not comparable' — never divided back into shares by some
    price, never subtracted as dollars."""
    legacy = {"symbol": "VST", "dominant_quarter": "2026-03-31",
              "taken_at": datetime(2026, 8, 23, tzinfo=timezone.utc),
              "holders": dict(VST_PRIOR_USD), "n_holders": 10}
    monkeypatch.setattr(ac, "_snapshots", lambda: _SnapColl([legacy]))
    c = ac.compare_to_snapshot("VST", _payload(_vst_now_holders()))
    assert c["comparable"] is False
    assert "predates share counts" in c["reason"]
    assert c["overlap_funds"] == 0 and c["net_change_usd"] == 0.0
    assert len(c["unknown_funds"]) == 8
    assert ac.is_significant(c) is False


def test_thin_known_overlap_names_the_unknowns(monkeypatch):
    prior = {"symbol": "X", "dominant_quarter": "2026-03-31",
             "shares": {"A": 10.0, "B": 10.0, "C": None, "D": None}}
    monkeypatch.setattr(ac, "_snapshots", lambda: _SnapColl([prior]))
    now = [{"holder": k, "shares": 20.0, "value": 40.0} for k in "ABCD"]
    c = ac.compare_to_snapshot("X", _payload(now))
    assert c["comparable"] is False
    assert "share count" in c["reason"] and "2 unknown" in c["reason"]


# ---------------------------------------------------------------------------
# share-bearing snapshot → the Sunday comparison
# ---------------------------------------------------------------------------
def test_share_bearing_snapshot_compares_on_shares(monkeypatch):
    prior = {"symbol": "VST", "dominant_quarter": "2026-03-31",
             "taken_at": datetime(2026, 8, 23, tzinfo=timezone.utc),
             "holders": dict(VST_PRIOR_USD), "shares": _vst_prior_shares()}
    monkeypatch.setattr(ac, "_snapshots", lambda: _SnapColl([prior]))
    monkeypatch.setattr(ac, "_splits_since", lambda s, since: [])      # no split
    c = ac.compare_to_snapshot("VST", _payload(_vst_now_holders()))
    assert c["comparable"] is True and c["basis"] == "shares"
    assert c["direction"] == "accumulating"
    assert math.isclose(c["price"], 148.38, abs_tol=0.01)
    assert "price move alone reads zero" in c["caveat"]
    assert "may not have sold" in c["caveat"]


def test_snapshot_banks_shares_and_its_price(monkeypatch):
    coll = _SnapColl()
    monkeypatch.setattr(ac, "_snapshots", lambda: coll)
    ac.take_snapshot("VST", _payload(_vst_now_holders()))
    d = coll.docs[0]
    assert d["shares"]["Blackrock Inc."] == 29064465.0
    assert math.isclose(d["price"], 148.38, abs_tol=0.01)
    assert d["holders"]["Blackrock Inc."] == 4312585458.0     # display $ kept


def test_snapshot_price_is_the_median_and_none_without_shares():
    assert ac.snapshot_price([{"shares": 1, "value": 10}, {"shares": 2, "value": 20},
                              {"shares": 1, "value": 99}]) == 10
    assert ac.snapshot_price([{"shares": 0, "value": 10},
                              {"shares": None, "value": 20}]) is None
    assert ac.snapshot_price([]) is None


def test_no_common_price_prints_no_dollars_but_keeps_shares():
    c = ac.compare_maps({"A": 1.0, "B": 1.0, "C": 1.0}, {"A": 5.0, "B": 1.0, "C": 1.0}, None)
    assert c["net_change_shares"] == 4 and c["net_change_usd"] is None
    c["comparable"] = True
    assert ac.is_significant(c) is True          # +133% by the % floor alone


# ---------------------------------------------------------------------------
# top-10 list changes valued at the common price
# ---------------------------------------------------------------------------
def test_list_changes_are_valued_at_the_common_price_not_their_old_dollars():
    c = ac.compare_maps({"A": 1.0, "B": 1.0, "C": 1.0, "Leaver": 1000.0},
                        {"A": 1.0, "B": 1.0, "C": 1.0, "Joiner": 300.0}, 50.0)
    assert c["exit_usd"] == 50_000.0 and c["new_buyer_usd"] == 15_000.0
    assert c["net_change_shares"] == 0          # never folded in
    assert "not proven buys or exits" in c["list_change_note"]


def test_a_leaver_with_no_share_count_has_unknown_dollars():
    c = ac.compare_maps({"A": 1.0, "B": 1.0, "C": 1.0, "Leaver": None},
                        {"A": 1.0, "B": 1.0, "C": 1.0}, 50.0)
    assert c["exits"] == ["Leaver"] and c["exit_usd"] is None


# ---------------------------------------------------------------------------
# the push decision
# ---------------------------------------------------------------------------
def test_a_dollar_basis_comparison_never_decides_a_push():
    """NEGATIVE: a dict without basis='shares' (the old dollar read) is refused
    however large its dollar figure."""
    assert ac.is_significant({"comparable": True, "net_change_usd": -1_156_781_846,
                              "net_change_pct": -6.02}) is False
    assert ac.is_significant({"comparable": True, "basis": "usd",
                              "net_change_usd": -1e12, "net_change_pct": -90}) is False


def test_the_sweep_records_the_share_basis(monkeypatch):
    class _C:
        def __init__(self):
            self.docs = []

        def find_one(self, *a, **kw):
            return None

        def insert_one(self, d):
            self.docs.append(d)

    class _DB:
        accumulation_changes = _C()

    db = _DB()
    monkeypatch.setattr(ac, "_db", lambda: db)
    monkeypatch.setattr(ac, "for_symbol", lambda s, **kw: {
        "symbol": s, "comparable": True, "significant": True, "basis": "shares",
        "new_quarter": "2026-06-30", "net_change_shares": 481_494.0,
        "net_change_usd": 71_444_130.0, "net_change_pct": 0.4, "price": 148.38,
        "direction": "accumulating", "new_buyers": [], "exits": []})
    ac.sweep(["VST"])
    d = db.accumulation_changes.docs[0]
    assert d["basis"] == "shares" and d["net_change_shares"] == 481_494.0
    assert d["price"] == 148.38


def test_alert_line_carries_shares_and_says_top10_not_exit():
    line = ac.alert_line({
        "symbol": "VST", "direction": "accumulating", "net_change_shares": 481_494.0,
        "net_change_usd": 71_444_130.0, "net_change_pct": 0.4,
        "new_buyers": ["N", "G"], "exits": ["J", "L"],
        "prev_quarter": "2026-03-31", "new_quarter": "2026-06-30"})
    assert "🟢 VST +$71M +481K sh" in line
    assert "2 left top-10" in line and "2 joined top-10" in line
    assert "exit" not in line.lower() and " out" not in line
    assert len(line) < 120


def test_alert_line_flat_is_not_red_and_unknown_dollars_print_no_dollar():
    line = ac.alert_line({"symbol": "X", "direction": "flat", "net_change_shares": 0.0,
                          "net_change_usd": None, "net_change_pct": 0.0,
                          "prev_quarter": "Q1", "new_quarter": "Q2"})
    assert "🔴" not in line and "$" not in line and "+0 sh" in line


# ---------------------------------------------------------------------------
# position lens — top_sell is a trim, not an exit
# ---------------------------------------------------------------------------
def test_position_lens_names_the_top_seller_as_a_trim():
    t = pl._whales_distribution_trigger({"signal": "distributing", "n_selling": 5,
                                         "n_buying": 1, "top_sell": "FMR, LLC"})
    assert t["verdict"] == "TIGHTEN_STOP" and t["rule"] == "institutional_distribution"
    assert "Top seller (trim): FMR, LLC" in t["msg"]
    assert "exit" not in t["msg"].lower()


def test_position_lens_no_trigger_unless_distributing():
    assert pl._whales_distribution_trigger(None) is None
    assert pl._whales_distribution_trigger({"signal": "balanced"}) is None
    assert pl._whales_distribution_trigger({"signal": "accumulating"}) is None


def test_position_lens_evaluate_carries_the_trim_wording(monkeypatch):
    """evaluate() itself must append the 13F trigger — not just the helper.
    NEGATIVE: the text never says 'exit' for a fund that is still holding."""
    import pymongo
    from sepa import scanner, prices
    from supply_demand import whales as whales_mod, accumulation as acc_mod

    monkeypatch.setattr(scanner, "load_latest", lambda: {"all_results": [
        {"symbol": "XYZ", "last_close": 100.0, "stage": {"stage": 2},
         "trade_plan": {}, "sell_signals": {}}]})
    monkeypatch.setattr(prices, "load_prices", lambda *a, **k: None)
    monkeypatch.setattr(whales_mod, "get_whales", lambda s: {"moves": {
        "net_signal": "distributing", "n_buying": 1, "n_selling": 5,
        "notable_sells": [{"holder": "FMR, LLC", "pct_change": -0.31}]}})
    monkeypatch.setattr(acc_mod, "get_accumulation_scores", lambda syms: {})

    def _no_mongo(*a, **k):
        raise RuntimeError("no mongo in tests")
    monkeypatch.setattr(pymongo, "MongoClient", _no_mongo)
    monkeypatch.setattr(pl, "_market_posture",
                        lambda: {"posture": "constructive", "drivers": []})

    out = pl.evaluate("XYZ", 95.0)
    t = [x for x in out["triggers"] if x["rule"] == "institutional_distribution"]
    assert len(t) == 1 and t[0]["verdict"] == "TIGHTEN_STOP"
    assert "Top seller (trim): FMR, LLC" in t[0]["msg"]
    assert "exit" not in t[0]["msg"].lower()
    assert out["verdict"] == "TIGHTEN_STOP"


# ---------------------------------------------------------------------------
# splits — raw share counts straddle them (critic 2026-10-06)
# ---------------------------------------------------------------------------
SPLIT_PRIOR = {"A": 1_000_000.0, "B": 2_000_000.0, "C": 3_000_000.0}


def _split_case(monkeypatch, ratio, splits):
    """The same three funds, zero trading, the share counts scaled by `ratio`
    and valued at the post-split price."""
    prior = {"symbol": "SPLT", "dominant_quarter": "2026-03-31",
             "taken_at": datetime(2026, 8, 23, tzinfo=timezone.utc),
             "shares": dict(SPLIT_PRIOR)}
    monkeypatch.setattr(ac, "_snapshots", lambda: _SnapColl([prior]))
    seen = {}

    def _fake(sym, since):
        seen["since"] = since
        return splits
    monkeypatch.setattr(ac, "_splits_since", _fake, raising=False)
    px = 15.0 / ratio
    now = [{"holder": k, "shares": v * ratio, "value": v * ratio * px,
            "date_reported": "2026-06-30"} for k, v in SPLIT_PRIOR.items()]
    c = ac.compare_to_snapshot("SPLT", _payload(now))
    c["symbol"] = "SPLT"
    return c, seen


def test_a_forward_split_with_no_trading_is_not_a_flow(monkeypatch):
    """REGRESSION: 10-for-1, nobody traded — read +900% 'accumulating'."""
    c, seen = _split_case(monkeypatch, 10.0, [
        {"execution_date": "2026-07-15", "split_from": 1.0, "split_to": 10.0}])
    assert c["comparable"] is False and ac.is_significant(c) is False
    assert "split on 2026-07-15 (10-for-1)" in c["reason"]
    # NEGATIVE: the split ratio never leaks out as a flow figure
    assert c["net_change_pct"] is None and c["net_change_shares"] is None
    assert c["net_change_usd"] is None and c["direction"] == "unknown"
    assert seen["since"] == "2026-03-31"          # from the prior quarter end


def test_a_reverse_split_never_reads_as_a_sell_off(monkeypatch):
    """NEGATIVE: 1-for-10 on a small cap read -90% 'distributing' — a false
    sell signal. Not comparable, not significant, no red line."""
    c, _ = _split_case(monkeypatch, 0.1, [
        {"execution_date": "2026-07-15", "split_from": 10.0, "split_to": 1.0}])
    assert c["comparable"] is False and ac.is_significant(c) is False
    assert "1-for-10" in c["reason"]
    assert c["direction"] != "distributing"
    assert "🔴" not in ac.alert_line(c)


def test_a_failed_split_lookup_never_falls_back_to_unadjusted_shares(monkeypatch):
    """NEGATIVE: lookup failure = split status unknown, not 'no split'."""
    c, _ = _split_case(monkeypatch, 10.0, None)
    assert c["comparable"] is False and ac.is_significant(c) is False
    assert "split status unknown" in c["reason"]
    assert c["net_change_pct"] is None


def test_no_split_since_the_prior_picture_still_compares(monkeypatch):
    c, _ = _split_case(monkeypatch, 1.0, [])
    assert c["comparable"] is True and c["net_change_shares"] == 0
    assert c["direction"] == "flat"


def test_split_window_starts_at_the_earlier_of_quarter_end_and_bank_day():
    ts = datetime(2026, 8, 23, tzinfo=timezone.utc)
    assert ac._split_window_start({"dominant_quarter": "2026-03-31", "taken_at": ts}) == "2026-03-31"
    assert ac._split_window_start({"dominant_quarter": "2026-09-30", "taken_at": ts}) == "2026-08-23"
    assert ac._split_window_start({"taken_at": ts}) == "2026-08-23"
    assert ac._split_window_start({}) is None


def test_split_lookup_tells_failure_from_no_splits(monkeypatch):
    from portfolio import corporate_actions as ca
    replies = {}
    monkeypatch.setattr(ca, "_massive_get", lambda path, params: replies["r"])
    replies["r"] = {}                                       # no key / non-200
    assert ac._splits_since("X", "2026-03-31") is None
    replies["r"] = {"status": "ERROR"}
    assert ac._splits_since("X", "2026-03-31") is None
    replies["r"] = {"status": "OK", "results": []}
    assert ac._splits_since("X", "2026-03-31") == []
    replies["r"] = {"status": "OK"}                         # empty page, no key
    assert ac._splits_since("X", "2026-03-31") == []
    replies["r"] = {"status": "OK", "results": [
        {"execution_date": "2026-07-15", "split_from": 1, "split_to": 10},
        {"execution_date": "2026-07-16", "split_from": 1, "split_to": 1}]}
    assert ac._splits_since("X", "2026-03-31") == [
        {"execution_date": "2026-07-15", "split_from": 1.0, "split_to": 10.0}]

    def _boom(*a, **k):
        raise RuntimeError("down")
    monkeypatch.setattr(ca, "_massive_get", _boom)
    assert ac._splits_since("X", "2026-03-31") is None


def test_a_dollars_only_snapshot_spends_no_split_lookup(monkeypatch):
    """Already not comparable — no Massive call for it."""
    legacy = {"symbol": "VST", "dominant_quarter": "2026-03-31",
              "holders": dict(VST_PRIOR_USD)}
    monkeypatch.setattr(ac, "_snapshots", lambda: _SnapColl([legacy]))

    def _never(*a, **k):
        raise AssertionError("split lookup on a non-comparable pair")
    monkeypatch.setattr(ac, "_splits_since", _never)
    assert ac.compare_to_snapshot("VST", _payload(_vst_now_holders()))["comparable"] is False


# ---------------------------------------------------------------------------
# recent() — legacy dollar rows are labelled
# ---------------------------------------------------------------------------
def test_recent_tags_rows_without_a_basis_as_legacy_dollars(monkeypatch):
    rows = [
        {"symbol": "AVGO", "net_change_usd": -108.7e9, "direction": "distributing",
         "detected_at": datetime(2026, 8, 30, tzinfo=timezone.utc)},
        {"symbol": "VST", "basis": "shares", "net_change_shares": 481_494.0,
         "detected_at": datetime(2026, 10, 11, tzinfo=timezone.utc)},
    ]

    class _Cur:
        def __init__(self, r):
            self.r = r

        def sort(self, *a):
            return self

        def limit(self, n):
            return [dict(x) for x in self.r]

    class _DB:
        class accumulation_changes:
            @staticmethod
            def find(*a, **k):
                return _Cur(rows)

    monkeypatch.setattr(ac, "_db", lambda: _DB())
    out = {r["symbol"]: r for r in ac.recent()}
    assert out["AVGO"]["basis"] == "dollars_legacy"
    assert "not a measured flow" in out["AVGO"]["legacy_note"]
    # NEGATIVE: a share-basis row is never relabelled
    assert out["VST"]["basis"] == "shares" and "legacy_note" not in out["VST"]


def test_cli_entry_installs_log_redaction():
    """The Sunday cron runs `python -m supply_demand.accumulation_changes`; a
    CLI has no app startup, so it must install the redaction filter itself
    before the split lookup can log a requests exception carrying the key."""
    src = (Path(__file__).resolve().parents[1] / "supply_demand" / "accumulation_changes.py").read_text()
    main = src[src.index('if __name__ == "__main__":'):]
    assert "install_redaction()" in main
    assert main.index("install_redaction()") < main.index("sweep(notify=True)")
