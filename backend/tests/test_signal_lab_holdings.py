"""Signals board carries the portfolio by default (Ajay 2026-09-02), and
reports how much of the CAP the stored watchlist actually uses (2026-09-10)."""
from daytrading import signal_lab as sl


def test_merge_keeps_watchlist_order_then_adds_held_names_once():
    out = sl.merge_holdings(["nvda", "VST"], [{"ticker": "vst"}, {"ticker": "UBER"}, {"ticker": ""}, {}])
    assert out["symbols"] == ["NVDA", "VST", "UBER"]
    assert out["held"] == ["UBER", "VST"]


def test_merge_negatives():
    for watch, hold, syms in (([], [], []), (None, None, []),
                              ([" ", "aaoi "], [{"ticker": None}], ["AAOI"])):
        out = sl.merge_holdings(watch, hold)
        assert out["symbols"] == syms
        assert out["held"] == []
        assert out["watch_n"] == len(syms)


# ── watch_n: the only count MAX_SYMBOLS caps ──────────────────────────────
# `symbols` is watchlist ∪ portfolio and is deliberately uncapped, so the UI
# cannot derive the cap usage from it. It used to try, and warned that the
# oldest name would drop when nothing would.
def test_watch_n_counts_the_stored_list_not_the_merged_one():
    out = sl.merge_holdings(["NVDA", "VST"], [{"ticker": "UBER"}, {"ticker": "SU"}])
    assert len(out["symbols"]) == 4          # merged
    assert out["watch_n"] == 2               # stored
    assert out["max_symbols"] == sl.MAX_SYMBOLS


def test_watch_n_counts_a_name_that_is_both_watched_and_held():
    """Subtracting `held` from `symbols` would undercount VST — it is on the
    stored watchlist AND in the book. That is why the server sends the number."""
    out = sl.merge_holdings(["NVDA", "VST"], [{"ticker": "VST"}])
    assert out["symbols"] == ["NVDA", "VST"]
    assert out["held"] == ["VST"]
    assert out["watch_n"] == 2
    assert len(out["symbols"]) - len(out["held"]) == 1      # the wrong answer


def test_watch_n_is_deduped_and_blank_safe():
    out = sl.merge_holdings(["nvda", "NVDA", " ", "", None, "vst"], [])
    assert out["watch_n"] == 2


def test_a_big_portfolio_never_makes_an_empty_watchlist_look_full():
    """NEGATIVE: 20 held names, nothing watched — the cap is untouched."""
    out = sl.merge_holdings([], [{"ticker": "H%d" % i} for i in range(20)])
    assert len(out["symbols"]) == 20
    assert out["watch_n"] == 0
    assert out["watch_n"] < sl.MAX_SYMBOLS


def test_add_symbol_trim_and_watch_n_agree_on_the_cap():
    """The stored list is what gets trimmed, so watch_n can never exceed it."""
    stored = ["S%d" % i for i in range(sl.MAX_SYMBOLS)]
    out = sl.merge_holdings(stored, [{"ticker": "HELD%d" % i} for i in range(5)])
    assert out["watch_n"] == sl.MAX_SYMBOLS
    assert len(out["symbols"]) == sl.MAX_SYMBOLS + 5
