"""Tape trade eligibility + date stamps (2026-09-27).

Ajay, on the ORCL Tape tab: "Can you add date stamps please to the tape?" then
"this is for oracle hoping this info is accurate". It was not accurate: ORCL
2026-09-25's single closing cross (1,671,248 @ $137.10, $229.1M) was listed
five times as a "buy" (the cross plus four NYSE Official Close re-sends), the
opening cross twice, and the 16:04:10 "BUY FLASH $483.5M" was the close.

The fixture is REAL: tests/fixtures/orcl_tape_2026_09_25.json holds Massive
/v3/trades rows for ORCL 2026-09-25 (the 09:30:10, 14:32:30 and 16:04:10-30
windows, every print >= $10M, every corrected row), pulled read-only by the
tape audit. tests/fixtures/massive_sale_conditions_2026_09_27.json is the
provider's condition reference, trimmed — the exclusion sets are pinned to it.
"""
import inspect
import json
import os
import sys
from datetime import datetime, timezone

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from orderflow import tape as T  # noqa: E402
from orderflow import trade_flash as TF  # noqa: E402
from orderflow import darkpool  # noqa: E402

FX = os.path.join(os.path.dirname(__file__), "fixtures")
CROSS_SIZE = 1_671_248          # ORCL 2026-09-25 closing cross
OPEN_SIZE = 275_822             # ORCL 2026-09-25 opening cross
QCT_SIZE = 700_000              # the 14:32:36 Qualified Contingent Trade


def _raw_rows():
    fx = json.load(open(os.path.join(FX, "orcl_tape_2026_09_25.json")))
    return pd.DataFrame(fx["rows"], columns=fx["columns"])


def _frame(raw):
    """Raw rows → the frame tape.fetch_trades returns (same code path)."""
    df = raw.copy()
    df["ts_utc"] = pd.to_datetime(df["sip_timestamp"], unit="ns", utc=True)
    T.label_kinds(df)
    df["exec_utc"] = pd.to_datetime(df["participant_timestamp"], unit="ns", utc=True)
    keep = ["ts_utc", "price", "size", "exchange", "kind", "exec_utc"]
    return df[keep].sort_values("ts_utc").set_index("ts_utc")


@pytest.fixture(scope="module")
def orcl():
    return _frame(_raw_rows())


@pytest.fixture(scope="module")
def orcl_read(orcl):
    return T.analyze_tape(orcl)


# ── the pin: the sets ARE Massive's own flags ────────────────────────────────
def test_exclusion_sets_equal_the_massive_reference_derivation():
    ref = json.load(open(os.path.join(FX, "massive_sale_conditions_2026_09_27.json")))["results"]
    by_id = {c["id"]: c for c in ref}
    summary = {c["id"] for c in ref if c["consolidated"]["updates_volume"] is False}
    flagged = {c["id"] for c in ref
               if not (c["consolidated"]["updates_high_low"]
                       and c["consolidated"]["updates_open_close"])}
    assert set(T.SUMMARY_CONDITIONS) == summary == {15, 16, 38}
    assert set(T.NON_FLOW_CONDITIONS) == flagged - summary - set(T.KEPT_DESPITE_FLAGS)
    assert set(T.KEPT_DESPITE_FLAGS) == {12, 37}
    assert set(T.KEPT_DESPITE_FLAGS) <= flagged          # they ARE flagged; kept on purpose
    assert set(T.CORRECTION_DROP) == {1, 7, 8, 10, 11}
    names = {i: by_id[i]["name"] for i in (T.AUCTION_OPEN_CONDITIONS | T.AUCTION_CLOSE_CONDITIONS
                                           | T.AUCTION_REOPEN_CONDITIONS)}
    assert names == {17: "Market Center Opening Trade", 25: "Opening Prints",
                     8: "Closing Prints", 19: "Market Center Closing Trade",
                     18: "Market Center Reopening Trade", 28: "Re-Opening Prints"}
    # No set overlaps another — first-match order must never decide a real id.
    sets = [T.SUMMARY_CONDITIONS, T.NON_FLOW_CONDITIONS, T.AUCTION_OPEN_CONDITIONS,
            T.AUCTION_CLOSE_CONDITIONS, T.AUCTION_REOPEN_CONDITIONS, T.KEPT_DESPITE_FLAGS]
    for i, a in enumerate(sets):
        for b in sets[i + 1:]:
            assert not (a & b)


# ── print_kind ───────────────────────────────────────────────────────────────
@pytest.mark.parametrize("cid", sorted(T.SUMMARY_CONDITIONS))
def test_every_summary_condition_is_summary(cid):
    assert T.print_kind([cid]) == "summary"


@pytest.mark.parametrize("cid", sorted(T.NON_FLOW_CONDITIONS))
def test_every_non_flow_condition_is_non_flow(cid):
    assert T.print_kind([cid, 41]) == "non_flow"


@pytest.mark.parametrize("cid,kind", [(c, "auction_open") for c in sorted(T.AUCTION_OPEN_CONDITIONS)]
                         + [(c, "auction_close") for c in sorted(T.AUCTION_CLOSE_CONDITIONS)]
                         + [(c, "auction_reopen") for c in sorted(T.AUCTION_REOPEN_CONDITIONS)])
def test_every_auction_condition_is_its_auction(cid, kind):
    assert T.print_kind([cid, 41]) == kind


@pytest.mark.parametrize("corr", sorted(T.CORRECTION_DROP))
def test_every_dropped_correction_is_busted_whatever_the_conditions(corr):
    assert T.print_kind([], corr) == "busted"
    assert T.print_kind([17, 41], float(corr)) == "busted"       # JSON gives floats


def test_first_match_wins():
    assert T.print_kind([8, 15]) == "summary"                    # never an auction row
    assert T.print_kind([17, 2]) == "non_flow"
    assert T.print_kind([15], 8) == "busted"


@pytest.mark.parametrize("conds", [None, [], [14], [41], [9], [12], [37], [12, 41],
                                   [14, 41], [9, 41], ["x"], "garbage"])
def test_NEGATIVE_regular_iso_odd_lot_form_t_cross_trade_stay_regular(conds):
    assert T.print_kind(conds) == "regular"


@pytest.mark.parametrize("corr", [None, 0, 0.0, 12, float("nan"), "abc"])
def test_NEGATIVE_kept_corrections_and_junk_never_exclude(corr):
    assert T.print_kind([14], corr) == "regular"


# ── the real ORCL tape ───────────────────────────────────────────────────────
def test_the_five_close_rows_are_one_cross_and_four_re_reports(orcl):
    rows = orcl[orcl["size"] == CROSS_SIZE]
    assert len(rows) == 5
    assert sorted(rows["kind"]) == ["auction_close", "summary", "summary", "summary", "summary"]
    opens = orcl[orcl["size"] == OPEN_SIZE]
    assert sorted(opens["kind"]) == ["auction_open", "summary"]


def test_REGRESSION_unfiltered_tape_lists_the_cross_as_buying(orcl):
    """The bug, reproduced on the real rows: with no `kind` every re-send is a
    print, and the cross dominates the list."""
    old = T.analyze_tape(orcl[["price", "size", "exchange"]])
    n_cross = sum(1 for p in old["big_prints"]["prints"] if p["size"] == CROSS_SIZE)
    assert n_cross == 5
    assert max(b["dollars"] for b in old["bursts"]) > 400e6


def test_the_close_collapses_to_one_row_with_no_side(orcl_read):
    prints = orcl_read["big_prints"]["prints"]
    close = [p for p in prints if p["size"] == CROSS_SIZE]
    assert len(close) == 1
    assert close[0]["kind"] == "auction_close"
    assert close[0]["side"] is None
    assert (close[0]["date_et"], close[0]["time_et"]) == ("2026-09-25", "16:04:14")


def test_the_opening_cross_has_no_side(orcl_read):
    opens = [p for p in orcl_read["big_prints"]["prints"] if p["size"] == OPEN_SIZE]
    assert len(opens) == 1
    assert opens[0]["kind"] == "auction_open" and opens[0]["side"] is None
    assert opens[0]["time_et"] == "09:30:14"            # off the bell — a clock filter misses it


def test_auctions_never_count_as_big_buy_or_sell_dollars(orcl_read):
    bp = orcl_read["big_prints"]
    assert bp["buy_dollars"] + bp["sell_dollars"] < 38e6
    sided = sum(p["dollars"] for p in bp["prints"] if p["side"] in ("buy", "sell"))
    assert sided <= bp["buy_dollars"] + bp["sell_dollars"] + 1


def test_a_regular_block_is_still_counted(orcl_read):
    bp = orcl_read["big_prints"]
    blk = [p for p in bp["prints"] if p["size"] == 36_725 and p["price"] == 137.96]
    assert len(blk) == 1
    assert blk[0]["kind"] == "regular" and blk[0]["side"] in ("buy", "sell")
    assert blk[0]["time_et"] == "15:12:15"
    pool = bp["buy_dollars"] if blk[0]["side"] == "buy" else bp["sell_dollars"]
    assert pool >= blk[0]["dollars"]


def test_excluded_prints_never_enter_big_prints_bursts_or_delta(orcl, orcl_read):
    listed = {p["size"] for p in orcl_read["big_prints"]["prints"]}
    assert QCT_SIZE not in listed                       # the 700k QCT
    assert 522_453 not in listed and 150_000 not in listed   # prior-ref / avg-price TRF
    assert all(b["dollars"] < 38e6 for b in orcl_read["bursts"])
    assert orcl_read["delta"]["n_trades"] == int((orcl["kind"] == "regular").sum())


def test_venues_keep_real_volume_but_drop_re_reports_and_busts(orcl, orcl_read):
    v = orcl_read["venues"]
    real = orcl[orcl["kind"].isin(["regular", "non_flow", "auction_open", "auction_close"])]
    assert v["total_shares"] == int(real["size"].sum())
    assert v["total_shares"] < int(orcl["size"].sum()) - 4 * CROSS_SIZE


def test_every_row_carries_its_date(orcl_read):
    assert orcl_read["big_prints"]["prints"]
    for p in orcl_read["big_prints"]["prints"]:
        assert p["date_et"] == "2026-09-25"
    for b in orcl_read["venues"]["blocks"]:
        assert b["date_et"] == "2026-09-25" and "kind" in b


def test_the_excluded_note_counts_what_was_held_out(orcl_read):
    ex = orcl_read["excluded"]
    assert ex["auctions"]["open"] == 1 and ex["auctions"]["close"] == 1
    assert ex["summary"]["n"] == 5 and ex["busted"]["n"] == 8
    assert ex["note"].startswith("Not counted as buying or selling: 1 open + 1 close auction")
    assert "5 official open/close re-reports" in ex["note"]
    assert "8 cancelled or busted prints" in ex["note"]


# ── synthetic edges ──────────────────────────────────────────────────────────
def _tape(rows, start=datetime(2026, 9, 25, 14, 0, tzinfo=timezone.utc), step_ms=200):
    idx = [start + pd.Timedelta(milliseconds=i * step_ms) for i in range(len(rows))]
    return pd.DataFrame({"price": [r[0] for r in rows], "size": [r[1] for r in rows],
                         "kind": [r[2] for r in rows]},
                        index=pd.DatetimeIndex(idx, name="ts_utc"))


def test_NEGATIVE_an_excluded_print_changes_nothing_in_flow():
    base = [(50.0 + 0.01 * (i % 5), 300, "regular") for i in range(400)]
    with_bad = base[:200] + [(49.0, 2_000_000, "non_flow")] + base[200:]
    a, b = T.analyze_tape(_tape(base)), T.analyze_tape(_tape(with_bad))
    assert a["delta"]["delta"] == b["delta"]["delta"]
    assert a["bursts"] == b["bursts"]
    assert all(p["size"] != 2_000_000 for p in b["big_prints"]["prints"])
    assert a["big_prints"]["buy_dollars"] == b["big_prints"]["buy_dollars"]


def test_a_late_report_from_a_prior_day_shows_its_own_date():
    """A regular Form T print executed in the prior evening's overnight session
    and reported at 04:00: the row keeps its SIP date and also carries the
    EXECUTION date. Synthetic (ORCL 09-25 had none cross midnight)."""
    sip = pd.Timestamp("2026-09-25 04:00:00.1", tz="America/New_York").tz_convert("UTC")
    exe = pd.Timestamp("2026-09-24 22:10:03", tz="America/New_York").tz_convert("UTC")
    df = pd.DataFrame({"price": [137.0, 137.1], "size": [100, 900_000],
                       "kind": ["regular", "regular"], "exec_utc": [sip, exe]},
                      index=pd.DatetimeIndex([sip, sip + pd.Timedelta(seconds=1)], name="ts_utc"))
    df["side"] = T.tick_rule_sides(df["price"].tolist())
    row = next(p for p in T.find_big_prints(df)["prints"] if p["size"] == 900_000)
    assert row["date_et"] == "2026-09-25"
    assert (row["exec_date_et"], row["exec_time_et"]) == ("2026-09-24", "22:10:03")


def test_NEGATIVE_a_tape_without_kind_degrades_to_the_old_read():
    rows = [(30.0 + 0.01 * (i % 7), 300) for i in range(500)]
    df = pd.DataFrame({"price": [r[0] for r in rows], "size": [r[1] for r in rows]},
                      index=pd.DatetimeIndex([datetime(2026, 7, 2, 14, 0, tzinfo=timezone.utc)
                                              + pd.Timedelta(milliseconds=200 * i)
                                              for i in range(500)], name="ts_utc"))
    out = T.analyze_tape(df)
    assert out["excluded"] is None
    assert out["delta"]["n_trades"] == 500
    assert all(p["kind"] == "regular" and "exec_date_et" not in p
               for p in out["big_prints"]["prints"])


def test_NEGATIVE_a_tape_of_only_re_reports_does_not_crash():
    df = _tape([(137.1, CROSS_SIZE, "summary")] * 3)
    out = T.analyze_tape(df)
    assert out["delta"]["n_trades"] == 0 and out["delta"]["delta"] == 0
    assert out["big_prints"]["prints"] == [] and out["bursts"] == []
    assert out["last_price"] == 137.1
    assert out["venues"]["total_shares"] == 0


def _sided(df):
    out = df.copy()
    out["side"] = T.tick_rule_sides(out["price"].tolist())
    return out


def test_bursts_carry_a_date():
    rows = [(20.0, 100, "regular")] + [(20.0 + 0.01 * i, 1_000, "regular") for i in range(1, 30)]
    bursts = T.find_bursts(_sided(_tape(rows, step_ms=300)))
    assert bursts and all(b["date_et"] == "2026-09-25" for b in bursts)


def test_dark_blocks_without_kind_stay_the_old_shape_plus_date():
    idx = pd.DatetimeIndex([datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc)], name="ts_utc")
    df = pd.DataFrame({"price": [50.0], "size": [20_000], "exchange": [4]}, index=idx)
    b = darkpool.dark_blocks(df)
    assert b == [{"time": "11:00:00", "price": 50.0, "size": 20_000, "dollars": 1_000_000,
                  "date_et": "2026-09-25"}]


# ── trade_flash: the push path uses the same rule ────────────────────────────
def _fake_get(rows):
    class R:
        status_code = 200

        def json(self):
            return {"results": rows}
    return lambda *a, **k: R()


def test_trade_flash_tail_drops_the_crosses_and_re_reports(monkeypatch):
    raw = _raw_rows()
    win = raw[(raw["sip_timestamp"] >= 1790343010000000000)
              & (raw["sip_timestamp"] < 1790343020000000000)]      # 09:30:10-20 ET
    rows = [dict(zip(win.columns, [None if (isinstance(v, float) and v != v) else v for v in r]))
            for r in win.itertuples(index=False)][::-1]            # desc, like the poll
    import massive_keys
    import requests
    monkeypatch.setattr(massive_keys, "stocks_key", lambda: "k")
    monkeypatch.setattr(requests, "get", _fake_get(rows))
    df = TF.fetch_recent_trades("ORCL")
    assert df is not None and df.index.is_monotonic_increasing
    assert OPEN_SIZE not in set(df["size"])
    sided = df.copy()
    sided["side"] = T.tick_rule_sides(sided["price"].tolist())
    assert all(b["dollars"] < 38e6 for b in T.find_bursts(sided))
    assert len(df) == int(sum(T.print_kind(c, k) == "regular" and sz > 0
                              for c, k, sz in zip(win["conditions"], win["correction"],
                                                  win["size"])))


def test_NEGATIVE_trade_flash_rows_without_conditions_are_kept():
    df = pd.DataFrame({"ts_utc": pd.to_datetime([1, 2], unit="s", utc=True),
                       "price": [10.0, 10.1], "size": [100, 200]})
    assert len(TF.regular_only(df)) == 2


# ── source guards ────────────────────────────────────────────────────────────
def test_SOURCE_GUARD_every_tape_path_classifies_before_it_sides():
    assert "label_kinds(df)" in inspect.getsource(T.fetch_trades)
    assert "print_kind" in inspect.getsource(T.label_kinds)
    assert "regular_only(df)" in inspect.getsource(TF.fetch_recent_trades)
    assert "print_kind" in inspect.getsource(TF.regular_only)
    src = inspect.getsource(T.analyze_tape)
    assert "split_by_kind(trades)" in src
    assert 'auctions=views["auctions"]' in src
    assert "darkpool.split_venues(vol_df)" in src and "darkpool.dark_blocks(vol_df)" in src
    assert 'retail_mod.identify(df, quotes,\n' in src
    assert 'total_volume=int(vol_df["size"].sum())' in src
    # The clock backstop stays.
    assert TF.AUCTION_CROSS_ET == frozenset({"09:30:00", "16:00:00"})


# ── fix round 2026-09-27 ─────────────────────────────────────────────────────
from orderflow import engine as E  # noqa: E402
from orderflow import history as H  # noqa: E402
from orderflow import retail as RT  # noqa: E402

SUNDAY_NOON = datetime(2026, 9, 27, 12, 0)


def _snap(tape_read):
    return {"symbol": "ORCL", "et_date": "2026-09-25",
            "as_of_utc": datetime.utcnow().isoformat() + "Z", "tape": tape_read}


@pytest.fixture
def sunday(monkeypatch):
    from zoneinfo import ZoneInfo
    monkeypatch.setattr(E, "_now_et", lambda: SUNDAY_NOON.replace(tzinfo=ZoneInfo("America/New_York")))


def test_a_pre_rule_snapshot_is_stale_even_from_the_last_session(sunday):
    """The live ORCL doc (critic probe): et_date 09-25 read on Sunday, no
    `excluded` — it served the five BUY rows as fresh."""
    assert E._last_session_date() == "2026-09-25"
    assert E._is_stale(_snap({"delta": {}, "big_prints": {}})) is True
    assert E._is_stale(_snap(None)) is True
    assert E._is_stale({"et_date": "2026-09-25"}) is True


def test_NEGATIVE_a_post_rule_snapshot_from_the_last_session_is_fresh(sunday, orcl_read):
    assert E._is_stale(_snap(orcl_read)) is False
    assert E._is_stale(_snap({"excluded": None})) is False      # classified, nothing held out


def test_NEGATIVE_a_post_rule_snapshot_from_an_older_session_is_still_stale(sunday, orcl_read):
    old = {**_snap(orcl_read), "et_date": "2026-09-24"}
    assert E._is_stale(old) is True


def test_the_ledger_tags_which_rule_made_the_verdict(orcl_read, monkeypatch):
    assert H.tape_method(_snap(orcl_read)) == T.ELIGIBILITY_METHOD == "eligibility_2026_09_27"
    assert H.tape_method(_snap({"delta": {}})) == T.LEGACY_METHOD == "all_prints"
    assert H.tape_method({}) == T.LEGACY_METHOD

    seen = {}

    class Coll:
        def update_one(self, q, u, upsert=False):
            seen.update(u["$setOnInsert"])

            class R:
                upserted_id = q["_id"]
            return R()
    monkeypatch.setattr(H, "_coll", lambda: Coll())
    assert H.record({**_snap(orcl_read), "verdict": "AVOID", "checks_passed": 1})
    assert seen["method"] == "eligibility_2026_09_27" and seen["checks_passed"] == 1
    seen.clear()
    assert H.record({**_snap({"delta": {}}), "verdict": "AVOID", "checks_passed": 3})
    assert seen["method"] == "all_prints"


def _retail_tape():
    """Two sub-penny TRF prints (retail), a lit regular print, a big TRF
    average-price print (non_flow) and an official-close re-report (summary)."""
    rows = [(50.0037, 100, 4, "regular"), (50.0062, 300, 4, "regular"),
            (50.01, 600, 10, "regular"), (50.00, 1_000, 4, "non_flow"),
            (50.00, 50_000, 10, "summary")]
    idx = [datetime(2026, 9, 25, 15, 0, tzinfo=timezone.utc) + pd.Timedelta(seconds=i)
           for i in range(len(rows))]
    return pd.DataFrame({"price": [r[0] for r in rows], "size": [r[1] for r in rows],
                         "exchange": [r[2] for r in rows], "kind": [r[3] for r in rows]},
                        index=pd.DatetimeIndex(idx, name="ts_utc"))


def test_retail_pct_divides_by_real_volume_not_the_regular_prints():
    r = T.analyze_tape(_retail_tape())["retail"]
    assert r["retail_shares"] == 400 and r["retail_trades"] == 2
    # 400 / (100 + 300 + 600 + 1,000 non_flow) — the summary re-report is out.
    assert r["retail_pct_of_volume"] == 20.0


def test_NEGATIVE_a_non_flow_sub_penny_print_is_never_retail():
    df = _retail_tape()
    df.iloc[3, df.columns.get_loc("price")] = 50.0041        # sub-penny, TRF, average-price
    r = T.analyze_tape(df)["retail"]
    assert r["retail_shares"] == 400 and r["retail_pct_of_volume"] == 20.0


def test_NEGATIVE_identify_without_total_volume_keeps_the_old_divisor():
    df = _retail_tape()
    r = RT.identify(df)                                      # Back in Demand's call
    assert r["retail_pct_of_volume"] == round(100.0 * 400 / int(df["size"].sum()), 1)
    assert RT.identify(df, total_volume=0)["retail_pct_of_volume"] is None


def test_retail_pct_on_the_real_orcl_rows(orcl, orcl_read):
    vol = orcl[orcl["kind"].isin(T.VOLUME_KINDS)]
    r = orcl_read["retail"]
    if r["retail_shares"]:
        assert r["retail_pct_of_volume"] == round(100.0 * r["retail_shares"] / int(vol["size"].sum()), 1)


# ── the before/after script behind the doc's numbers ─────────────────────────
def _script():
    import importlib.util
    path = os.path.join(os.path.dirname(__file__), "..", "scripts",
                        "tape_eligibility_before_after_2026_09_27.py")
    spec = importlib.util.spec_from_file_location("tape_before_after", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_before_after_script_builds_the_fetch_frame_and_splits_the_two_reads(orcl):
    S = _script()
    raw = _raw_rows()
    rows = [dict(zip(raw.columns, r)) for r in raw.itertuples(index=False)]
    full = S.frame_from_raw(rows)
    fetched = orcl[(orcl["price"] > 0) & (orcl["size"] > 0)]     # fetch_trades' own filter
    pd.testing.assert_frame_equal(full[["price", "size", "exchange", "kind"]],
                                  fetched[["price", "size", "exchange", "kind"]])
    res = S.run("ORCL", datetime(2026, 9, 25).date(), full, None, None,
                {"pass": False}, {"pass": False}, {"pass": True, "caution": False})
    before = [p for p in res["before"]["top_prints"] if p[4] == CROSS_SIZE]
    after = [p for p in res["after"]["top_prints"] if p[4] == CROSS_SIZE]
    assert len(before) == 5 and all(p[3] in ("buy", "sell") for p in before)
    assert after == [("2026-09-25", "16:04:14", "auction_close", None, CROSS_SIZE, 137.1, "$229.1M")]
    assert res["tape_shares_after"] < res["tape_shares_before"]
    assert res["vs_daily_after_pct"] is None                  # no daily bar offline


def test_SOURCE_GUARD_stale_and_ledger_share_one_rule():
    assert "tape_method(doc)" in inspect.getsource(E._is_stale)
    assert '"method": tape_method(snap)' in inspect.getsource(H.record)
