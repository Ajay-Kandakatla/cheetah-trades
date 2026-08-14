"""Quote-rule classification + off-exchange (dark) print analytics.

Ajay 2026-08-13, asking whether we can trade off the order book. We can't —
there is no L2 endpoint on the subscription — but two things WERE available and
unused: the NBBO stream (upgrades side-classification from the tick rule to the
quote rule) and the venue field on every print (lit vs FINRA TRF).

Measured on CIEN 2026-08-13 while building this: the tick rule agreed with the
quote rule on only **76.4%** of prints and understated net selling by **2.3x**
(-519k vs -1,168k shares). That is why this is not cosmetic.
"""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from orderflow import darkpool as dp
from orderflow import quotes as Q
from orderflow import tape


def _trades(rows):
    """rows = [(ts_seconds, price, size, exchange)]"""
    df = pd.DataFrame(rows, columns=["t", "price", "size", "exchange"])
    df["ts_utc"] = pd.to_datetime(df["t"], unit="s", utc=True)
    return df.drop(columns=["t"]).set_index("ts_utc")


def _quotes(rows):
    df = pd.DataFrame(rows, columns=["t", "bid", "ask"])
    df["ts_utc"] = pd.to_datetime(df["t"], unit="s", utc=True)
    return df.drop(columns=["t"]).set_index("ts_utc")


# ── Lee-Ready, one print at a time ───────────────────────────────────────────
def test_lift_the_offer_is_buyer_aggressive():
    assert Q.classify_against_quote(10.05, bid=10.00, ask=10.05) == 1
    assert Q.classify_against_quote(10.10, bid=10.00, ask=10.05) == 1   # through


def test_hit_the_bid_is_seller_aggressive():
    assert Q.classify_against_quote(10.00, bid=10.00, ask=10.05) == -1
    assert Q.classify_against_quote(9.90, bid=10.00, ask=10.05) == -1


def test_inside_the_spread_uses_the_midpoint():
    assert Q.classify_against_quote(10.04, bid=10.00, ask=10.06) == 1
    assert Q.classify_against_quote(10.02, bid=10.00, ask=10.06) == -1


def test_exactly_at_mid_is_undecidable():
    """The midpoint genuinely carries no directional information — it must
    return 0 so the caller can fall back, not guess."""
    assert Q.classify_against_quote(10.03, bid=10.00, ask=10.06) == 0


def test_degenerate_quotes_classify_nothing():
    assert Q.classify_against_quote(10.0, bid=0, ask=0) == 0
    assert Q.classify_against_quote(10.0, bid=10.05, ask=10.00) == 0   # crossed
    assert Q.classify_against_quote(0, bid=10.0, ask=10.05) == 0


# ── whole-tape classification ────────────────────────────────────────────────
def test_quote_rule_beats_the_tick_rule_on_a_constructed_tape():
    """Three prints at a FALLING price, every one of them lifting the offer.

    The tick rule reads the downticks and calls them selling. The quote rule
    sees each print at the ask and correctly calls them buying. This is the
    disagreement that showed up as 2.3x on real CIEN data."""
    quotes = _quotes([(100, 9.98, 10.00), (200, 9.88, 9.90), (300, 9.78, 9.80)])
    trades = _trades([(150, 10.00, 100, 10), (250, 9.90, 100, 10), (350, 9.80, 100, 10)])

    tick = tape.tick_rule_sides(trades["price"].tolist())
    assert tick.count(-1) == 2                      # tick rule: mostly selling

    out = Q.quote_rule_sides(trades, quotes, fallback_sides=tick)
    assert out["sides"] == [1, 1, 1]                # quote rule: all buying
    assert out["coverage_pct"] == 100.0
    assert out["trustworthy"] is True
    assert out["method"] == "quote"


def test_trades_before_the_first_quote_fall_back_and_are_counted():
    quotes = _quotes([(500, 9.98, 10.00)])
    trades = _trades([(100, 10.00, 100, 10), (600, 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[-1, -1])
    assert out["sides"][0] == -1                    # no quote yet → fallback
    assert out["sides"][1] == 1                     # quoted → lifted the offer
    assert out["n_fallback"] == 1
    assert out["coverage_pct"] == 50.0


def test_midpoint_prints_fall_back_to_the_tick_rule():
    quotes = _quotes([(100, 10.00, 10.06)])
    trades = _trades([(150, 10.03, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[1])
    assert out["n_at_mid"] == 1
    assert out["sides"] == [1]                      # tick rule decided it


def test_no_quotes_degrades_to_tick_and_says_so():
    """The failure that must never be silent: no NBBO → we report the tick
    rule AS the tick rule, not as a quote-rule delta."""
    trades = _trades([(150, 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, None, fallback_sides=[-1])
    assert out["method"] == "tick"
    assert out["trustworthy"] is False
    assert out["coverage_pct"] == 0.0
    assert out["sides"] == [-1]


def test_thin_coverage_is_labelled_mixed_not_quote():
    quotes = _quotes([(900, 9.98, 10.00)])
    trades = _trades([(i, 10.00, 100, 10) for i in range(100, 900, 100)]
                     + [(950, 10.00, 100, 10)])
    out = Q.quote_rule_sides(trades, quotes, fallback_sides=[0] * 9)
    assert out["coverage_pct"] < Q.MIN_USEFUL_COVERAGE_PCT
    assert out["method"] == "mixed"
    assert out["trustworthy"] is False


def test_empty_tape_is_handled():
    out = Q.quote_rule_sides(_trades([]).iloc[0:0], None)
    assert out["method"] == "none"
    assert out["sides"] == []


def test_agreement_measures_only_decided_prints():
    assert Q.agreement([1, -1, 1, 0], [1, 1, 1, 1]) == pytest.approx(66.7, abs=0.1)
    assert Q.agreement([0, 0], [0, 0]) is None


# ── venue split ──────────────────────────────────────────────────────────────
def test_exchange_4_is_off_exchange_everything_else_is_lit():
    """Verified against /v3/reference/exchanges: id 4 = FINRA ADF, type=TRF,
    and it is the only id on which prints carry a trf_id."""
    assert dp.is_off_exchange(4) is True
    assert dp.is_off_exchange(10) is False          # NYSE
    assert dp.is_off_exchange(12) is False          # Nasdaq
    assert dp.is_off_exchange(None) is False
    assert dp.is_off_exchange("nonsense") is False


def test_split_venues_shares_and_percentage():
    df = _trades([(1, 10.0, 600, 4), (2, 10.0, 400, 10)])
    out = dp.split_venues(df)
    assert out["available"] is True
    assert out["dark_shares"] == 600 and out["lit_shares"] == 400
    assert out["dark_pct"] == 60.0
    assert out["is_heavy"] is True                  # 60 >= DARK_HEAVY_PCT


def test_normal_venue_mix_is_not_flagged_heavy():
    df = _trades([(1, 10.0, 390, 4), (2, 10.0, 610, 10)])   # 39% — the CIEN case
    assert dp.split_venues(df)["is_heavy"] is False


def test_venue_split_unavailable_without_the_exchange_column():
    """Older cached tapes have no venue data. We must report unavailable, not
    silently claim 0% dark."""
    df = _trades([(1, 10.0, 100, 4)]).drop(columns=["exchange"])
    out = dp.split_venues(df)
    assert out["available"] is False
    assert out["dark_pct"] is None


def test_dark_blocks_keep_only_large_off_exchange_prints():
    df = _trades([
        (1, 10.0, 50_000, 4),      # big + dark  -> block
        (2, 10.0, 50_000, 10),     # big but LIT -> not a dark block
        (3, 10.0, 100, 4),         # dark but small -> not a block
        (4, 900.0, 500, 4),        # small share count, $450k notional -> block
    ])
    blocks = dp.dark_blocks(df)
    assert len(blocks) == 2
    assert blocks[0]["dollars"] >= blocks[1]["dollars"]      # sorted by notional
    assert all(b["size"] > 0 for b in blocks)


def test_dark_in_band_only_counts_prints_inside_the_band():
    df = _trades([(1, 10.0, 300, 4), (2, 10.0, 200, 10), (3, 50.0, 900, 4)])
    out = dp.dark_in_band(df, lo=9.0, hi=11.0)
    assert out["dark_shares"] == 300
    assert out["total_shares"] == 500
    assert out["dark_pct"] == 60.0


def test_dark_in_band_reports_zero_honestly_when_nothing_traded_there():
    """A band price has not visited today has no prints. It must read as
    available-but-empty, never as 'no dark interest'."""
    df = _trades([(1, 50.0, 900, 4)])
    out = dp.dark_in_band(df, lo=9.0, hi=11.0)
    assert out["available"] is True
    assert out["total_shares"] == 0
    assert out["dark_pct"] is None


def test_dark_in_band_rejects_degenerate_bands():
    df = _trades([(1, 10.0, 300, 4)])
    assert dp.dark_in_band(df, lo=0, hi=0)["available"] is False
    assert dp.dark_in_band(df, lo=11.0, hi=9.0)["available"] is False


def test_read_never_claims_institutional_intent():
    """The bucket mixes dark-pool crossing with retail internalization. The
    copy must not call it institutional accumulation."""
    txt = dp.read(dp.split_venues(_trades([(1, 10.0, 600, 4), (2, 10.0, 400, 10)])))
    assert "off-exchange" in txt
    low = txt.lower()
    assert "institutional accumulation" not in low
    assert "smart money" not in low


# ── analyze_tape wiring ──────────────────────────────────────────────────────
def test_analyze_tape_reports_classification_and_venues():
    trades = _trades([(100, 10.00, 100, 4), (200, 10.05, 200, 10), (300, 10.02, 150, 4)])
    quotes = _quotes([(50, 9.98, 10.00), (150, 10.03, 10.05), (250, 10.00, 10.04)])
    out = tape.analyze_tape(trades, quotes=quotes)
    assert out["classification"]["method"] in ("quote", "mixed")
    assert out["venues"]["available"] is True
    assert out["venues"]["dark_pct"] is not None
    assert "read" in out["venues"]


def test_analyze_tape_without_quotes_still_works_and_flags_tick():
    """REGRESSION: analyze_tape gained an optional quotes arg. Every existing
    caller passes one positional frame and must keep working."""
    trades = _trades([(100, 10.00, 100, 4), (200, 10.05, 200, 10)])
    out = tape.analyze_tape(trades)
    assert out["classification"]["method"] == "tick"
    assert out["classification"]["trustworthy"] is False
    assert out["delta"]["n_trades"] == 2


# ── retail flow (BJZZ + the Barber midpoint correction) ──────────────────────
def test_subpenny_detection_excludes_penny_and_half_penny_prints():
    from orderflow import retail
    assert retail.is_subpenny(10.0034) is True
    assert retail.is_subpenny(10.0071) is True
    assert retail.is_subpenny(10.00) is False      # on the penny
    assert retail.is_subpenny(10.005) is False     # half cent
    assert retail.is_subpenny(0) is False


def test_retail_is_signed_on_the_midpoint_not_the_subpenny_direction():
    """Barber et al. (2024) validated the original sub-penny signing against
    85,000 known retail trades: it mis-signs 28%. Measured on SWKS 2026-08-14
    the two methods disagreed on DIRECTION (-8.1% vs +15.7%)."""
    from orderflow import retail
    # price ABOVE the midpoint -> retail buy, regardless of the sub-penny digit
    trades = _trades([(100, 10.0034, 500, 4)])
    quotes = _quotes([(50, 10.00, 10.006)])        # mid 10.003
    out = retail.identify(trades, quotes)
    assert out["signed"] is True
    assert out["buy_shares"] == 500 and out["sell_shares"] == 0


def test_retail_refuses_to_sign_without_nbbo():
    """An unsigned count is honest; a wrongly-signed one is worse than none."""
    from orderflow import retail
    out = retail.identify(_trades([(100, 10.0034, 500, 4)]), None)
    assert out["available"] is True
    assert out["signed"] is False
    assert out["imbalance_pct"] is None
    assert "unsigned" in out["read"].lower()


def test_lit_exchange_subpenny_is_not_retail():
    """The method is off-exchange AND sub-penny. A lit print is not wholesaler
    internalisation whatever its price."""
    from orderflow import retail
    out = retail.identify(_trades([(100, 10.0034, 500, 10)]), None)
    assert out["retail_trades"] == 0


def test_divergence_takes_the_block_LIST_not_a_count():
    """REGRESSION 2026-08-14: the caller passed len(blocks) and divergence did
    len() on an int, so the retail read silently died on every row that HAD
    blocks — precisely the interesting rows."""
    from orderflow import retail
    rt = {"signed": True, "lean": "buying"}
    d = retail.divergence(rt, [{"dollars": 5_000_000}, {"dollars": 3_000_000}])
    assert d["block_count"] == 2 and d["block_dollars"] == 8_000_000
    assert retail.divergence(rt, []) is None
    assert retail.divergence({"signed": False}, [{"dollars": 1}]) is None


def test_divergence_never_claims_to_know_the_block_side():
    from orderflow import retail
    d = retail.divergence({"signed": True, "lean": "selling"}, [{"dollars": 1e6}])
    assert "not knowable" in d["note"]
