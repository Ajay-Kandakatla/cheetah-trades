"""WP-DATA 2026-09-29 — a reused ticker's foreign head is cut, curated only.

Ajay's /dual-momentum page ranked WOLF +2,248.76%, BNY +1,435% and SPCX
+474.95% for 12 months. Each cached frame began with ANOTHER security's bars
(Wolfspeed's cancelled pre-Chapter-11 equity, the BlackRock NY Muni fund, the
SPAC ETF). The fix is curated — `sepa.symbols.FIRST_SESSION` and two RENAMES
entries — and applied by `sepa.prices._cut_foreign_head` at fetch AND read
time. Nothing is inferred: a name in neither map comes back as the same object.

Shapes follow the live audit (docs/sepa/dual_momentum_data_audit_2026_09_29.md).
All synthetic. No network, no Mongo.

Tests marked "RENAMES hunk" belong to the BK->BNY / AMRK->GOLD block in
symbols.py (HIS CALL #6); drop them together with that block if he says no to
the one-time refetch.
"""
from __future__ import annotations

import importlib.util
import inspect
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pd = pytest.importorskip("pandas")

from sepa import prices as P  # noqa: E402
from sepa import symbols as S  # noqa: E402


# ---------------------------------------------------------------------------
# Frame builders
# ---------------------------------------------------------------------------
def seg(start=None, end=None, periods=1, px=10.0, first_open=None, step=0.0,
        hour=0):
    """`periods` business-day bars. Close walks by `step`; open = prior close,
    except the first bar's open (`first_open`)."""
    idx = pd.bdate_range(start=start, end=end, periods=periods)
    if hour:
        idx = idx + pd.Timedelta(hours=hour)
    closes = [round(px + step * i, 4) for i in range(periods)]
    opens = [first_open if first_open is not None else closes[0]] + closes[:-1]
    return pd.DataFrame({"open": opens,
                         "high": [max(o, c) for o, c in zip(opens, closes)],
                         "low": [min(o, c) for o, c in zip(opens, closes)],
                         "close": closes, "volume": [100_000.0] * periods},
                        index=idx)


def cat(*parts):
    return pd.concat(parts).sort_index()


def first_day(df):
    return str(pd.Timestamp(df.index[0]).date())


def wolf_cached(hour=0):
    """Old equity ~1.2 to 2025-09-26 (last close 1.21), new equity from
    2025-09-29 at open 18.00 — exactly 252 post-reorg bars."""
    head = seg(end="2025-09-26", periods=250, px=1.5, step=-0.00116, hour=hour)
    head.iloc[-1, head.columns.get_loc("close")] = 1.21
    tail = seg(start="2025-09-29", periods=252, px=22.10, first_open=18.00,
               step=0.025, hour=hour)
    return cat(head, tail)


def spcx_cached():
    """SPAC ETF ~$22 to 2026-04-06, 67-day hole, SpaceX from 2026-06-12."""
    etf = seg(end="2026-04-06", periods=380, px=22.0, step=0.001)
    spacex = seg(start="2026-06-12", periods=75, px=160.95, first_open=150.0,
                 step=-0.2)
    return cat(etf, spacex)


def bny_cached():
    """BlackRock NY Muni fund ~$10 to 2026-02-06 (340 bars), a 104-day hole,
    then BNY Mellon from 2026-05-21 (open 136.46)."""
    fund = seg(end="2026-02-06", periods=340, px=9.6, step=0.001)
    mellon = seg(start="2026-05-21", periods=90, px=137.0, first_open=136.46,
                 step=0.1)
    return cat(fund, mellon)


def bk_bars():
    bk = seg(end="2026-05-20", periods=411, px=60.0, step=0.19)
    bk.iloc[-1, bk.columns.get_loc("close")] = 137.16
    return bk


def bny_spliced():
    """BK head to 2026-05-20 close 137.16, BNY from 2026-05-21 open 136.46."""
    mellon = seg(start="2026-05-21", periods=90, px=137.0, first_open=136.46,
                 step=0.1)
    return cat(bk_bars(), mellon)


def gold_cached():
    """Barrick to 2025-05-08 (close 18.86), 208-day hole, Gold.com from
    2025-12-02 (open 30.13)."""
    barrick = seg(end="2025-05-08", periods=150, px=17.0, step=0.0125)
    barrick.iloc[-1, barrick.columns.get_loc("close")] = 18.86
    goldcom = seg(start="2025-12-02", periods=208, px=30.5, first_open=30.13,
                  step=0.06)
    return cat(barrick, goldcom)


def gold_spliced():
    amrk = seg(end="2025-12-01", periods=300, px=25.0, step=0.0141)
    amrk.iloc[-1, amrk.columns.get_loc("close")] = 29.25
    goldcom = seg(start="2025-12-02", periods=208, px=30.5, first_open=30.13,
                  step=0.06)
    return cat(amrk, goldcom)


def sols_cached():
    otc = seg(start="2025-03-31", periods=2, px=0.0001)
    sol = seg(start="2025-10-30", periods=230, px=48.7, step=0.05)
    return cat(otc, sol)


def real_continuous(periods=503, px=50.0, step=0.1):
    return seg(end="2026-09-29", periods=periods, px=px, step=step)


def mrna_shape():
    """A REAL +177% single day (Moderna 2026-08-19), not in any map."""
    df = real_continuous(px=20.0, step=0.01)
    i = df.index.get_loc(pd.Timestamp("2026-08-19"))
    df.iloc[i:, df.columns.get_loc("close")] *= 2.77
    df.iloc[i:, df.columns.get_loc("open")] *= 2.77
    return df


# ---------------------------------------------------------------------------
# 1. Maps
# ---------------------------------------------------------------------------
def test_first_session_entries_are_iso_dates_with_evidence():
    assert set(S.FIRST_SESSION) == {"WOLF", "SPCX", "SOLS"}
    for sym, (first, why) in S.FIRST_SESSION.items():
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", first), (sym, first)
        pd.Timestamp(first)
        assert len(why) > 40, f"{sym}: evidence too thin to audit"
        assert ("FIGI" in why) or ("list_date" in why), sym


def test_first_session_dates_are_the_audited_ones():
    assert S.first_session("WOLF") == "2025-09-29"
    assert S.first_session("SPCX") == "2026-06-12"
    assert S.first_session("SOLS") == "2025-10-30"
    assert S.first_session(" wolf ") == "2025-09-29"


def test_first_session_is_disjoint_from_renames_keys_and_targets():
    """NEG: a symbol with history to SPLICE is a rename; one without is a
    first session. Both at once would cut a splice the fetch just built."""
    targets = {new for new, _e, _w in S.RENAMES.values()}
    assert not set(S.FIRST_SESSION) & set(S.RENAMES)
    assert not set(S.FIRST_SESSION) & targets
    assert not set(S.FIRST_SESSION) & set(S.DELISTED)


def test_first_session_and_rename_effective_are_none_for_ordinary_names():
    for s in ("NVDA", "MRNA", "", None):
        assert S.first_session(s) is None
        assert S.rename_effective(s) is None


def test_rename_effective_reads_the_new_symbol_only():
    assert S.rename_effective("ECHO") == "2026-06-24"
    assert S.rename_effective("XYZ") == "2025-01-21"
    assert S.rename_effective("SATS") is None, "an OLD symbol's bars are its own"


def test_rename_effective_takes_the_latest_of_several_former_names(monkeypatch):
    monkeypatch.setattr(S, "RENAMES", {"AAA": ("NEW", "2024-01-02", "x" * 50),
                                       "BBB": ("NEW", "2025-06-02", "x" * 50)})
    monkeypatch.setattr(S, "_FORMER", {"NEW": ["AAA", "BBB"]})
    assert S.rename_effective("NEW") == "2025-06-02"


def test_existing_no_chain_rule_still_holds():
    for old, (new, _e, _w) in S.RENAMES.items():
        assert new not in S.RENAMES, f"{old}->{new} chains; write it direct"


# --- RENAMES hunk (HIS CALL #6) ---
def test_renames_hunk_bk_to_bny_carries_figi_and_boundary():
    new, eff, why = S.RENAMES["BK"]
    assert (new, eff) == ("BNY", "2026-05-21")
    for needle in ("BBG000BD8PN9", "137.16", "136.46", "2026-05-20",
                   "BBG000BZF6G2"):
        assert needle in why, needle
    assert S.resolve("BK") == "BNY"
    assert S.former_names("BNY") == ["BK"]


def test_renames_hunk_amrk_to_gold_carries_figi_and_boundary():
    new, eff, why = S.RENAMES["AMRK"]
    assert (new, eff) == ("GOLD", "2025-12-02")
    for needle in ("BBG005ZVDK48", "29.25", "30.13", "2025-12-01", "2025-05-08"):
        assert needle in why, needle
    assert S.former_names("GOLD") == ["AMRK"]


def test_renames_hunk_is_one_contiguous_block():
    """The main session must be able to drop BK/AMRK without touching
    FIRST_SESSION: both entries sit between two marker lines."""
    src = (ROOT / "sepa" / "symbols.py").read_text()
    start = src.index("2026-09-29 Dual Momentum data audit: TICKER REUSE")
    end = src.index("end 2026-09-29 RENAMES block")
    block = src[start:end]
    assert '"BK": ("BNY"' in block and '"AMRK": ("GOLD"' in block
    assert "FIRST_SESSION: dict" not in block and '"WOLF"' not in block
    assert src.index("FIRST_SESSION: dict") > end


# ---------------------------------------------------------------------------
# 2. The cut on the audited shapes
# ---------------------------------------------------------------------------
def test_wolf_starts_at_the_reorg():
    out = P._cut_foreign_head(wolf_cached(), "WOLF")
    assert first_day(out) == "2025-09-29"
    assert len(out) == 252
    assert float(out["open"].iloc[0]) == pytest.approx(18.00)


def test_wolf_cut_works_on_massive_utc_stamps():
    """Massive stamps daily bars at 04:00 UTC, not midnight."""
    out = P._cut_foreign_head(wolf_cached(hour=4), "WOLF")
    assert first_day(out) == "2025-09-29" and len(out) == 252


def test_wolf_cut_works_on_a_tz_aware_yahoo_frame():
    df = wolf_cached()
    df.index = df.index.tz_localize("America/New_York")
    out = P._cut_foreign_head(df, "WOLF")
    assert first_day(out) == "2025-09-29" and len(out) == 252


def test_spcx_starts_at_the_spacex_listing():
    out = P._cut_foreign_head(spcx_cached(), "SPCX")
    assert first_day(out) == "2026-06-12"
    assert len(out) == 75


def test_sols_starts_at_solstice():
    out = P._cut_foreign_head(sols_cached(), "SOLS")
    assert first_day(out) == "2025-10-30"
    assert float(out["close"].min()) > 1.0


def test_renames_hunk_bny_cached_shape_drops_the_muni_fund():
    out = P._cut_foreign_head(bny_cached(), "BNY")
    assert first_day(out) == "2026-05-21"
    assert len(out) == 90
    assert float(out["close"].min()) > 100.0, "no fund bars (~$10) survive"


def test_renames_hunk_bny_spliced_shape_is_kept_whole():
    """After the refetch: BK head, 1-day gap, ratio 1.005 → a clean splice."""
    df = bny_spliced()
    assert P._cut_foreign_head(df, "BNY") is df


def test_renames_hunk_gold_cached_shape_drops_barrick():
    out = P._cut_foreign_head(gold_cached(), "GOLD")
    assert first_day(out) == "2025-12-02"
    assert len(out) == 208


def test_renames_hunk_gold_spliced_shape_is_kept_whole():
    df = gold_spliced()
    assert P._cut_foreign_head(df, "GOLD") is df


def test_renames_hunk_a_jump_at_effective_without_a_hole_is_cut():
    """A consecutive session but a > SPLICE_MAX_JUMP_RATIO boundary is not a
    relabelling either (splice_history's second test)."""
    head = seg(end="2026-05-20", periods=50, px=10.0)
    tail = seg(start="2026-05-21", periods=20, px=137.0, first_open=136.46)
    out = P._cut_foreign_head(cat(head, tail), "BNY")
    assert first_day(out) == "2026-05-21" and len(out) == 20


# ---------------------------------------------------------------------------
# 3. Negatives — no inference, no damage
# ---------------------------------------------------------------------------
def test_a_symbol_in_neither_map_is_the_same_object():
    df = real_continuous()
    assert P._cut_foreign_head(df, "NVDA") is df


def test_a_real_177pct_day_not_in_any_map_is_untouched():
    """MRNA 2026-08-19 +177% was REAL (the audit checked it). No inference."""
    df = mrna_shape()
    assert P._cut_foreign_head(df, "MRNA") is df


def test_a_wolf_shaped_frame_under_another_symbol_is_untouched():
    df = wolf_cached()
    assert P._cut_foreign_head(df, "CTRL") is df


@pytest.mark.parametrize("new,head,tail", [
    # the five existing renames with their real boundary bars
    ("ECHO", (["2026-06-22", "2026-06-23"], [106.40, 103.915], None),
             (["2026-06-24", "2026-06-25"], [99.86, 97.19], [101.16, 100.275])),
    ("XYZ", (["2025-01-16", "2025-01-17"], [86.38, 86.96], None),
            (["2025-01-21", "2025-01-22"], [89.50, 87.48], [88.06, 90.20])),
    ("DOO", (["2025-12-04", "2025-12-05"], [75.9, 76.66], None),
            (["2025-12-08", "2025-12-09"], [81.0, 81.5], [81.67, 81.0])),
    ("PPLI", (["2026-06-02", "2026-06-03"], [41.8, 42.24], None),
             (["2026-06-04", "2026-06-05"], [42.9, 43.0], [42.72, 42.9])),
])
def test_existing_renames_with_real_boundaries_are_unchanged(new, head, tail):
    def fr(d, c, o):
        o = o or c
        return pd.DataFrame({"open": o, "high": c, "low": c, "close": c,
                             "volume": [1_000] * len(c)}, index=pd.to_datetime(d))
    df = P.splice_history(fr(*head), fr(*tail), "x")
    assert len(df) == 4, "precondition: splice_history joined them"
    assert P._cut_foreign_head(df, new) is df


def test_gtm_frame_starting_at_effective_is_unchanged():
    df = seg(start="2025-05-13", periods=300, px=10.0, step=0.01)
    assert P._cut_foreign_head(df, "GTM") is df


def test_a_continuous_yahoo_backfill_under_the_new_symbol_is_kept():
    """Yahoo serves a renamed ticker's FULL history under the new symbol:
    continuous bars, no hole, no jump at `effective`. That head is the same
    company and must survive."""
    df = seg(end="2026-09-29", periods=503, px=60.0, step=0.08)
    df.index = df.index.tz_localize("America/New_York")
    assert P._cut_foreign_head(df, "ECHO") is df


@pytest.mark.parametrize("sym,maker", [
    ("WOLF", wolf_cached), ("SPCX", spcx_cached), ("SOLS", sols_cached),
    ("BNY", bny_cached), ("BNY", bny_spliced), ("GOLD", gold_cached),
    ("GOLD", gold_spliced), ("MRNA", mrna_shape), ("NVDA", real_continuous),
])
def test_output_is_a_subset_and_never_grows(sym, maker):
    df = maker()
    out = P._cut_foreign_head(df, sym)
    assert len(out) <= len(df)
    assert set(out.index) <= set(df.index)
    assert list(out.index) == sorted(out.index)
    pd.testing.assert_frame_equal(out, df.loc[out.index])


def test_empty_and_none_frames_pass_through():
    assert P._cut_foreign_head(None, "WOLF") is None
    empty = real_continuous().iloc[0:0]
    assert P._cut_foreign_head(empty, "WOLF") is empty
    df = real_continuous()
    assert P._cut_foreign_head(df, "") is df


# ---------------------------------------------------------------------------
# 4. _fetch — cut BEFORE the splice
# ---------------------------------------------------------------------------
def test_renames_hunk_fetch_gives_a_continuous_bk_to_bny_frame(monkeypatch):
    frames = {"BNY": bny_cached(), "BK": bk_bars()}
    monkeypatch.setattr(P, "_fetch_one", lambda s, period: frames.get(s))
    out = P._fetch("BNY", "2y")
    assert first_day(out) == first_day(frames["BK"])
    assert len(out) == 411 + 90
    assert float(out["close"].min()) > 50.0, "no fund bars"
    assert not out.index.duplicated().any()
    gaps = pd.Series(out.index).diff().dt.days.dropna()
    assert gaps.max() <= P.SPLICE_MAX_GAP_DAYS


def test_renames_hunk_fetch_still_refuses_a_jumpy_splice(monkeypatch):
    """NEG: a boundary over SPLICE_MAX_JUMP_RATIO still refuses the splice —
    and the fund head is gone too, so BNY's own tail stands alone."""
    bny = bny_cached()
    bny.iloc[340, bny.columns.get_loc("open")] = 200.0      # 200/137.16 = 1.46x
    frames = {"BNY": bny, "BK": bk_bars()}
    monkeypatch.setattr(P, "_fetch_one", lambda s, period: frames.get(s))
    out = P._fetch("BNY", "2y")
    assert first_day(out) == "2026-05-21"
    assert len(out) == 90


def test_fetch_cuts_a_first_session_symbol(monkeypatch):
    monkeypatch.setattr(P, "_fetch_one", lambda s, period: wolf_cached())
    out = P._fetch("WOLF", "2y")
    assert first_day(out) == "2025-09-29"


def test_fetch_of_an_ordinary_symbol_is_the_provider_frame(monkeypatch):
    df = real_continuous()
    monkeypatch.setattr(P, "_fetch_one", lambda s, period: df)
    assert P._fetch("NVDA", "2y") is df


# ---------------------------------------------------------------------------
# 5. Every read path applies the cut
# ---------------------------------------------------------------------------
def _no_writes(monkeypatch):
    monkeypatch.setattr(P, "_mongo_put", lambda *a, **k: None)
    monkeypatch.setattr(P, "_parquet_put", lambda *a, **k: None)


def test_load_prices_mongo_path_cuts(monkeypatch):
    _no_writes(monkeypatch)
    monkeypatch.setattr(P, "_mongo_get", lambda s: wolf_cached(hour=4))
    out = P.load_prices("WOLF")
    assert first_day(out) == "2025-09-29" and len(out) == 252


def test_load_prices_parquet_path_cuts(monkeypatch):
    _no_writes(monkeypatch)
    monkeypatch.setattr(P, "_mongo_get", lambda s: None)
    monkeypatch.setattr(P, "_parquet_get", lambda s: spcx_cached())
    out = P.load_prices("SPCX")
    assert first_day(out) == "2026-06-12" and len(out) == 75


def test_load_prices_fetch_path_cuts(monkeypatch):
    _no_writes(monkeypatch)
    monkeypatch.setattr(P, "_mongo_get", lambda s: None)
    monkeypatch.setattr(P, "_parquet_get", lambda s: None)
    monkeypatch.setattr(P, "_fetch_one", lambda s, period: sols_cached())
    out = P.load_prices("SOLS", force=True)
    assert first_day(out) == "2025-10-30"


def test_load_prices_leaves_an_ordinary_name_alone(monkeypatch):
    _no_writes(monkeypatch)
    df = real_continuous()
    monkeypatch.setattr(P, "_mongo_get", lambda s: df)
    out = P.load_prices("NVDA")
    pd.testing.assert_frame_equal(out, df)


def test_load_prices_still_drops_a_phantom_tail_after_the_cut(monkeypatch):
    _no_writes(monkeypatch)
    df = wolf_cached()
    ph = df.iloc[[-1]].copy()
    ph.index = [df.index[-1] + pd.Timedelta(days=1)]
    df = pd.concat([df, ph])
    monkeypatch.setattr(P, "_mongo_get", lambda s: df)
    out = P.load_prices("WOLF")
    assert len(out) == 252 and first_day(out) == "2025-09-29"


class _Coll:
    def __init__(self, frames):
        self.frames = frames
        self.calls = []

    def find(self, query, projection=None):
        self.calls.append(query)
        wanted = set((query or {}).get("symbol", {}).get("$in", self.frames))
        for sym, df in self.frames.items():
            if sym not in wanted:
                continue
            yield {"symbol": sym, "bars": [
                {"date": pd.Timestamp(i).to_pydatetime(), "open": float(r.open),
                 "high": float(r.high), "low": float(r.low),
                 "close": float(r.close), "volume": float(r.volume)}
                for i, r in df.iterrows()]}


def test_bulk_cached_frames_cuts(monkeypatch):
    coll = _Coll({"WOLF": wolf_cached(hour=4), "NVDA": real_continuous()})
    monkeypatch.setattr(P, "_get_mongo", lambda: coll)
    got = P.bulk_cached_frames(["WOLF", "NVDA"])
    assert first_day(got["WOLF"]) == "2025-09-29" and len(got["WOLF"]) == 252
    assert len(got["NVDA"]) == 503, "NEG: an ordinary name keeps every bar"


def test_source_guard_every_read_path_calls_the_cut():
    load_src = inspect.getsource(P.load_prices)
    assert load_src.count("_drop_phantom_tail(_cut_foreign_head(df, symbol))") == 3
    assert len(re.findall(r"^\s+return ", load_src, re.M)) == 4, \
        "3 frame returns + the None return"
    assert "_cut_foreign_head(df, sym)" in inspect.getsource(P.bulk_cached_frames)
    fetch_src = inspect.getsource(P._fetch)
    assert fetch_src.index("_cut_foreign_head(") < fetch_src.index("splice_history(")


def test_source_guard_cut_reuses_the_splice_constants():
    src = inspect.getsource(P._cut_foreign_head)
    assert "SPLICE_MAX_GAP_DAYS" in src and "SPLICE_MAX_JUMP_RATIO" in src
    assert not re.search(r"(?<![\w.])(1\.35|10)(?![\w.])", src), \
        "no retyped thresholds"


# ---------------------------------------------------------------------------
# 6. The Dual Momentum engine end to end (real load_prices, stubbed cache)
# ---------------------------------------------------------------------------
def test_engine_drops_wolf_and_spcx_and_keeps_a_real_control(monkeypatch):
    from sepa import dual_momentum as DM
    _no_writes(monkeypatch)
    frames = {"SPY": real_continuous(px=500.0, step=0.2),
              "WOLF": wolf_cached(hour=4),
              "SPCX": spcx_cached(),
              "CTRL": wolf_cached(hour=4),     # same shape, NOT in any map
              "REAL": real_continuous(px=20.0, step=0.1)}
    monkeypatch.setattr(P, "_mongo_get", lambda s: frames.get(s))
    monkeypatch.setattr(P, "_parquet_get", lambda s: None)
    monkeypatch.setattr(P, "_fetch", lambda s, period: None)
    rows = [{"symbol": s, "name": s, "rs_rank": 90, "stage": {"stage": 2}}
            for s in ("WOLF", "SPCX", "CTRL", "REAL")]
    monkeypatch.setattr(DM.sepa_scanner, "load_latest",
                        lambda: {"all_results": rows, "generated_at": 1})
    out = DM.compute(top_n=15)
    by = {r["symbol"]: r for r in out["rows"]}
    picks = [p["symbol"] for p in out["picks"]]
    assert by["WOLF"]["return_12m"] is None
    assert "WOLF" not in picks
    assert "SPCX" not in picks
    assert by["SPCX"]["return_12m"] is None
    # NEG: no inference — the same shape under an unmapped symbol keeps its
    # (fake-looking) return; only a curated entry removes it.
    assert by["CTRL"]["return_12m"] is not None and by["CTRL"]["return_12m"] > 1000
    assert "CTRL" in picks and "REAL" in picks


# ---------------------------------------------------------------------------
# 7. The audit script — read-only, finds the shapes, spares the real ones
# ---------------------------------------------------------------------------
SCRIPT = ROOT / "scripts" / "dm_frame_audit.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("dm_frame_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_audit_script_source_is_read_only():
    src = SCRIPT.read_text().lower()
    for bad in ("insert", "update", "replace", "delete", "force=true",
                "_get_mongo", "load_prices", "bulk_write", "drop("):
        assert bad not in src, bad
    assert ".find(" in src


def test_audit_script_reuses_the_house_constants():
    src = SCRIPT.read_text()
    assert "P._is_scale_glitch" in src
    assert 'LOOKBACKS["return_12m"]' in src
    assert "P._cut_foreign_head" in src
    mod = _load_script()
    assert mod.HOLE_REPORT_DAYS == 20
    assert mod.WINDOW_BARS == 253


def test_audit_reports_the_artefacts_and_not_the_real_shapes():
    mod = _load_script()
    coll = _Coll({"WOLF": wolf_cached(hour=4), "BNY": bny_cached(),
                  "SPCX": spcx_cached(), "GOLD": gold_cached(),
                  "MRNA": mrna_shape(), "NVDA": real_continuous(),
                  "ECHO": real_continuous(px=100.0)})
    rows = mod.audit(coll)
    by = {r["symbol"]: r for r in rows}
    assert {"WOLF", "BNY", "SPCX", "GOLD"} <= set(by)
    assert not {"MRNA", "NVDA", "ECHO"} & set(by), "REAL shapes are not reported"
    assert by["WOLF"]["curated"] == "FIRST_SESSION" and by["WOLF"]["healed"]
    assert by["SPCX"]["healed"]
    assert by["BNY"]["curated"] == "RENAMES" and by["BNY"]["healed"]
    assert by["BNY"]["hole_days"] > mod.HOLE_REPORT_DAYS
    assert by["WOLF"]["max_ratio"] >= P._SCALE_GLITCH_RATIO
    assert len(coll.calls) == 1, "ONE find"


def test_audit_flags_an_uncurated_suspect_as_not_healed():
    """NEG: the tool reports a suspect nobody has curated, and says so — it
    never heals it by itself."""
    mod = _load_script()
    rows = mod.audit(_Coll({"CTRL": wolf_cached()}))
    assert len(rows) == 1
    assert rows[0]["curated"] is None and rows[0]["healed"] is False


def test_audit_symbol_filter_is_one_find(monkeypatch):
    mod = _load_script()
    coll = _Coll({"WOLF": wolf_cached(), "NVDA": real_continuous()})
    rows = mod.audit(coll, ["wolf"])
    assert [r["symbol"] for r in rows] == ["WOLF"]
    assert coll.calls == [{"symbol": {"$in": ["WOLF"]}}]
