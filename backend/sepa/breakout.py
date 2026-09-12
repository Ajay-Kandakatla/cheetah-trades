"""Breakout COUNT board + per-symbol read — "how often does this name actually
break out, and on what ACTUAL volume?" (Ajay 2026-06-13).

Display-only. Reads `volume.analyze()`'s `breakout_count` (distinct
volume-confirmed breakouts over the trailing ~year, book p.203 definition:
volume > 1.5× the 50-day average AND a close above the prior 21-bar high) plus
the actual `last_vol` / `avg_vol_50` so the UI can show real share counts, not
just a "2.4×" ratio. Never feeds the score.
"""
from __future__ import annotations

import logging
from typing import Optional

log = logging.getLogger("sepa.breakout")


def _row(symbol: Optional[str], vol: Optional[dict],
         last_close=None, name=None) -> Optional[dict]:
    if not symbol or not vol:
        return None
    bc = vol.get("breakout_count")
    if bc is None:
        return None
    return {
        "symbol":              str(symbol).upper(),
        "name":                name,
        "breakout_count":      int(bc),
        "window_bars":         int(vol.get("breakout_window_bars") or 0),
        "last_vol":            vol.get("last_vol"),
        "avg_vol_50":          vol.get("avg_vol_50"),
        "days_since_breakout": vol.get("days_since_breakout"),
        "high_vol_breakout":   bool(vol.get("high_vol_breakout")),
        "last_close":          last_close,
    }


def _setup_note(r: dict) -> Optional[dict]:
    """Why a SETUP-but-not-buyable row is held out of the buy tier — so the page
    can say "extended, wait for a pullback" instead of a bare SETUP badge
    (Ajay 2026-06-22: "explicitly say wait for the pullback since it's past the
    pivot").

    EXTENDED case: a volume-confirmed breakout that closed more than
    ``scanner.BUYABLE_MAX_EXT_PCT`` past the pivot it cleared is too far to chase
    (Minervini, TLSW p.224) — ``_is_buyable`` drops it, and the disciplined play is
    to wait for a pullback toward the pivot. Reuses the SAME extension function +
    threshold as the gate, so the note fires for exactly the names dropped for
    extension. Returns ``{"kind": "extended", "ext_pct", "pivot"}`` or None.
    Distribution (institutions selling) is its own read — surfaced via
    ``distribution_selling`` — so it's excluded here."""
    if not (r.get("setup_ready") and not r.get("is_buyable")):
        return None
    if r.get("distribution_selling"):
        return None
    try:
        from sepa import scanner
        ext = scanner.ext_from_pivot_pct(r.get("entry_setup") or {},
                                         r.get("volume") or {}, r.get("last_close"))
        cap = scanner.BUYABLE_MAX_EXT_PCT
    except Exception:                                   # noqa: BLE001
        return None
    if ext is None or ext <= cap:
        return None
    vol = r.get("volume") or {}
    pivot = vol.get("recent_high") or (r.get("entry_setup") or {}).get("pivot")
    return {"kind": "extended", "ext_pct": round(float(ext), 1),
            "pivot": round(float(pivot), 2) if pivot else None}


def leaders(top: int = 30) -> dict:
    """Top names by breakout count from the latest scan — the Leaderboard board."""
    from sepa import scanner
    scan = scanner.load_latest() or {}
    rows = []
    for r in scan.get("all_results") or []:
        row = _row(r.get("symbol"), r.get("volume"), r.get("last_close"), r.get("name"))
        if row:
            rows.append(row)
    rows.sort(key=lambda x: (-x["breakout_count"], x["symbol"]))
    return {"rows": rows[:top], "scan_ts": scan.get("generated_at"), "n": len(rows)}


def _verdict_for(r: dict) -> Optional[dict]:
    """The row's Minervini+Bonde verdict — CONFIRMED even when the persisted scan
    didn't annotate it (e.g. a scan written by an older worker). The scan row
    always carries the price-side fields buyable_verdict.compute() needs
    (is_candidate / is_buyable / stage), so we recompute on the fly rather than
    show "verdict pending". ETFs get no Minervini verdict (the page says so)."""
    bv = r.get("buy_verdict")
    if bv is not None:
        return bv
    if r.get("is_etf"):
        return None
    try:
        from sepa import buyable_verdict
        return buyable_verdict.compute(r)
    except Exception:                               # noqa: BLE001
        return None


def _fnum(v):
    """float, or None for anything that is not a finite number. A blank must
    print as an em-dash and must never win a sort as a zero."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


STAGE_KEEP = (2,)                 # the only advancing stage
STAGE_EXCEPTION = (1, 3)          # allowed WHEN the name is an explosive grower
STAGE_NEVER = (4,)                # a decline is a decline — never excepted


def _stage_ok(x: dict) -> bool:
    """His rule, in one place. A row with NO stage is UNKNOWN and is kept:
    dropping a name because the classifier could not answer would hide it for a
    reason that has nothing to do with the stock."""
    st = x.get("stage")
    if st is None:
        return True
    if st in STAGE_NEVER:
        return False
    if st in STAGE_KEEP:
        return True
    return st in STAGE_EXCEPTION and bool(x.get("explosive"))


def board(top: int = 250, min_count: int = 1, stages: bool = True) -> dict:
    """Rich breakout-ranked board for the dedicated /breakouts page (Ajay
    2026-06-16: "a page to track only breakouts and # of breakouts, highest
    first ... some passing Minervinis and some not, and Bonde, but mainly around
    breakouts").

    Every name in the latest scan that has actually broken out (>= ``min_count``
    volume-confirmed breakouts over the trailing year), ranked by breakout COUNT
    descending, each carrying the Minervini+Bonde ``buy_verdict`` (see
    sepa/buyable_verdict.py) plus RS / stage / day-change context so the page can
    slice "passing Minervinis vs not" without another fetch. Display-only.
    """
    from sepa import scanner
    scan = scanner.load_latest() or {}
    rows = []
    for r in scan.get("all_results") or []:
        base = _row(r.get("symbol"), r.get("volume"), r.get("last_close"), r.get("name"))
        if not base or base["breakout_count"] < min_count:
            continue
        stage = r.get("stage") or {}
        # R1/R2 = the trade-plan R-multiple targets (entry + 1R / +2R, see
        # analysis/trade_plan._targets) — the overhead levels a breakout is
        # "marching toward". Carried so the page can show distance-to-target
        # without re-fetching the full plan (Ajay 2026-06-16: "if they are s2
        # and if they marching towards r1 or r2"). None when no usable plan.
        targets = (r.get("trade_plan") or {}).get("targets") or {}
        rows.append({
            **base,
            "broke_out_today": base.get("days_since_breakout") == 0,
            "day_change_pct":  r.get("day_change_pct"),
            "rs_rank":         r.get("rs_rank"),
            "stage":           stage.get("stage") if isinstance(stage, dict) else None,
            "stage_label":     stage.get("label") if isinstance(stage, dict) else None,
            "r1":              targets.get("r1"),
            "r2":              targets.get("r2"),
            "industry":        r.get("industry"),
            "is_etf":          bool(r.get("is_etf")),
            # Strict Minervini buy-now gate (scanner._is_buyable, pp.79-83/198-203)
            # + the setup-ready tier — lifted straight from the scan row so the
            # Breakouts page shows the SAME `is_buyable` the SEPA scan does, not
            # just the Trend-Template qualifier (buy_verdict.minervini).
            "is_buyable":      bool(r.get("is_buyable")),
            "setup_ready":     bool(r.get("setup_ready")),
            # Entry-setup type (VCP / POWER_PLAY / POCKET_PIVOT / BREAKOUT) so the
            # board can filter to real-base setups, hiding bare breakouts that have
            # no detected base (Ajay 2026-06-22).
            "setup_type":      (r.get("entry_setup") or {}).get("type"),
            # Why a SETUP row isn't buyable — "extended, wait for a pullback"
            # (Ajay 2026-06-22). None for clean setups; distribution shown via
            # distribution_selling below.
            "setup_note":      _setup_note(r),
            "distribution_selling": bool(r.get("distribution_selling")),
            # Momentum-led conviction rank (sepa.conviction) — the new default
            # sort key for the board (Ajay 2026-06-22). conviction_detail carries
            # the legs + climax suppression for the hover tooltip.
            "conviction":      r.get("conviction"),
            "conviction_detail": r.get("conviction_detail"),
            # Climax-aware ENTER/WATCH/AVOID verdict — so a climax breakout
            # (AMAT-class) reads AVOID on the board, not a buy.
            "decision":        (r.get("entry_exit") or {}).get("decision"),
            "decision_color":  (r.get("entry_exit") or {}).get("decision_color"),
            "buy_verdict":     _verdict_for(r),
        })
    # AI-ecosystem sector tag + priority rank (Ajay 2026-06-25: breakout lists
    # lead with AI-sector winners — chips/energy/nuclear/water-cooling/grid/…).
    # Lazy + fenced: a sector-map failure must never blank the board.
    #
    # RUNS BEFORE THE SORT (moved 2026-09-12). The recency sort uses
    # `ai_sector_rank` as its within-the-day tiebreak; tagging afterwards would
    # have left every rank reading as the 99 default and silently dropped his
    # standing AI-first rule while still looking like it applied.
    try:
        from supply_demand.sectors import ai_sector_for_ticker
        for x in rows:
            ais = ai_sector_for_ticker(x["symbol"])
            x["ai_sector"] = ais["label"] if ais else None
            x["ai_sector_id"] = ais["id"] if ais else None
            x["ai_sector_etf"] = ais["etf"] if ais else None
            x["ai_sector_rank"] = ais["rank"] if ais else None
    except Exception as exc:                            # noqa: BLE001
        log.debug("board: ai-sector tag failed: %s", exc)

    # ── Stage gate (Ajay 2026-09-12) ───────────────────────────────────────
    # "From the breakout remove any S3. Only S2 stocks and if thy have explosive
    # growth its ok to have s1 and s3. If they are newly found explosive growth"
    #
    # Stage 2 is the only advancing stage and the only one Minervini calls
    # buyable; 1 is basing, 3 is topping, 4 is decline. So the board keeps S2 —
    # PLUS an explosive grower at stage 1 or 3, because a 100%-sales/100%-EPS
    # name basing or consolidating is a different proposition from a tired one.
    # Stage 4 is never excepted: he named 1 and 3, and a decline is a decline.
    #
    # THIS RUNS BEFORE THE SORT AND THE CUT, and that is the point. Filtering
    # the already-cut 250 would leave ~80 rows drawn from a 250-name window
    # while 2,840 candidates existed — the same mistake the count-ranked cut
    # made with recency. Gating first means the 250 he sees are 250 QUALIFYING
    # names.
    #
    # The `explosive` tag therefore has to be attached here too. It is a cheap
    # dict lookup against the ~29-row growth board; the sales/EPS columns stay
    # after the cut because that snapshot is a real query.
    try:
        from growth import tracker as _gt
        grows = {r["symbol"]: r for r in ((_gt.board() or {}).get("rows") or [])
                 if r.get("symbol")}
        fresh = _gt.newly_found()
    except Exception as exc:                                # noqa: BLE001
        log.debug("board: growth board unavailable: %s", exc)
        grows, fresh = {}, set()
    for x in rows:
        g = grows.get(x["symbol"])
        # `explosive` is membership of the 🚀 board; `explosive_refused` carries
        # its ⛔ so good sales never make a name the engine will refuse look
        # clean; `explosive_new` says it ARRIVED there recently.
        x["explosive"] = bool(g)
        x["explosive_refused"] = bool(g) and any(
            str(w).startswith("⛔") for w in (g.get("warnings") or []))
        x["explosive_new"] = x["symbol"] in fresh

    n_prestage = len(rows)
    if stages:
        rows = [x for x in rows if _stage_ok(x)]

    # ── RECENCY first (Ajay 2026-09-12) ────────────────────────────────────
    # "Sort it by recent breakout instead of # of breakouts."
    #
    # THIS HAD TO MOVE TO THE SERVER, and that is the whole point of the change.
    # The board sorted by COUNT and only then cut to `top`, so the cut itself was
    # count-biased: on the 2026-09-12 scan, 47 names that broke out THAT DAY were
    # thrown away before the browser ever saw them — HPQ, HPE, QRVO, SWKS, SFL,
    # TNK, FEIM, INSP among them — while the names it kept at the head (AXTI 19,
    # BELFA 18, QUIK 18) had `days_since_breakout = None`, i.e. no recent
    # breakout at all. Re-sorting those 250 in the browser would have reordered a
    # list that had already discarded the answer.
    #
    # A name with NO recorded last-breakout date sorts LAST, not first: `None` is
    # unknown, and an unknown must never take the top of a board that now claims
    # to be ordered by recency.
    #
    # AI-sector rank breaks the tie, which keeps Ajay's 2026-06-25 standing rule
    # intact WITHIN a day rather than in place of recency: "any breakout list
    # puts AI-ecosystem sector winners on top". Count is demoted to the third
    # key — still a column, no longer the ranking.
    def _recency_key(x):
        d = x.get("days_since_breakout")
        return (d is None, d if d is not None else 0,
                x.get("ai_sector_rank") if x.get("ai_sector_rank") is not None else 99,
                -x["breakout_count"], -(x.get("rs_rank") or 0), x["symbol"])
    rows.sort(key=_recency_key)
    n_all = len(rows)
    rows = rows[:top]

    # Beta (1y daily vs SPY) for the displayed names only — the volatility
    # column + "sort by low volatility" on the page. Computed here (≤top names,
    # SPY loaded once, per-symbol day-cache) so it doesn't touch the scan hot
    # path. Display-only; None on any failure (never blocks the board).
    try:
        from sepa import beta as _beta
        _betas = _beta.betas_for([x["symbol"] for x in rows])
    except Exception as exc:                        # noqa: BLE001
        log.debug("board: beta batch failed: %s", exc)
        _betas = {}
    for x in rows:
        x["beta"] = _betas.get(x["symbol"])

    # ── EPS + explosive-growth overlay (Ajay 2026-09-12) ───────────────────
    # "update the breakout page with EPS and explosive growth logic we created."
    #
    # Both halves REUSE their existing owners rather than re-deriving anything:
    #   • sales / EPS come from `research.decision_snapshot`, the SAME cache the
    #     🔥 Hottest board reads, so the two boards cannot print different
    #     numbers for one name;
    #   • `explosive` is a POINTER to the 🚀 Growth board's own membership
    #     (100% sales AND 100% quarterly EPS, with the prior quarter also
    #     growing), never a second copy of that screen — that is the same rule
    #     the 🚀 chip follows everywhere else in the app.
    #
    # Fenced and display-only: a cache miss costs the columns, never the board,
    # and a missing number stays None so the page prints an em-dash rather than
    # a zero and it never wins a sort.
    try:
        from sepa import research
        snap = research.decision_snapshot([x["symbol"] for x in rows]) or {}
    except Exception as exc:                            # noqa: BLE001
        log.debug("board: fundamentals snapshot failed: %s", exc)
        snap = {}
    for x in rows:
        # TRAP: `decision_snapshot` returns a FLAT dict per symbol — the
        # fundamentals are already unwrapped. Reading a "fundamentals" key here
        # yields {} for every name and a silently 100%-blank column that reads
        # like "we have no data", exactly the shape of the earnings_calendar
        # keyed-by-_id trap next door in rotation/hottest.py. Caught by checking
        # the live fill rate, not by a test passing.
        f = snap.get(x["symbol"]) or {}
        sales = f.get("sales") or {}
        x["sales_yoy"] = _fnum(f.get("rev_growth_q_pct"))
        x["q_eps_yoy"] = _fnum(f.get("q_eps_growth_pct"))
        x["sales_tier"] = sales.get("tier") or None
        x["fundamentals_as_of"] = f.get("cached_at")

    def _mp(x):
        return ((x.get("buy_verdict") or {}).get("minervini") or {}).get("passed")

    def _bp(x):
        return ((x.get("buy_verdict") or {}).get("bonde") or {}).get("passed")

    summary = {
        "total":           len(rows),
        "broke_out_today": sum(1 for x in rows if x["broke_out_today"]),
        "buyable":         sum(1 for x in rows if x.get("is_buyable")),
        "minervini_pass":  sum(1 for x in rows if _mp(x) is True),
        "minervini_fail":  sum(1 for x in rows if _mp(x) is False),
        "bonde_pass":      sum(1 for x in rows if _bp(x) is True),
        "bonde_fail":      sum(1 for x in rows if _bp(x) is False),
        "both_pass":       sum(1 for x in rows if (x.get("buy_verdict") or {}).get("both_pass")),
    }
    return {"rows": rows, "scan_ts": scan.get("generated_at"), "n": len(rows),
            # The cut is now RECENCY-ranked, so what it drops is the oldest
            # breakouts rather than (as before) 47 of the day's freshest. Said
            # in the payload anyway: a cap the reader cannot see is how a
            # truncated list reads as a complete one.
            "n_all": n_all, "capped": n_all > len(rows), "top": top,
            # What the stage gate removed, so a filtered board can never read
            # as the whole market breaking out.
            "stage_filter": bool(stages), "n_prestage": n_prestage,
            "n_stage_dropped": n_prestage - n_all,
            "summary": summary}


def for_symbol(symbol: str) -> dict:
    """Per-symbol breakout read — used by the Portfolio holding chip, since a held
    name isn't always in the latest scan. Loads its prices + runs volume.analyze."""
    sym = (symbol or "").upper().strip()
    try:
        from sepa import prices, volume
        df = prices.load_prices(sym)
        if df is None or len(df) == 0:
            return {"ok": False, "symbol": sym}
        vol = volume.analyze(df)
        row = _row(sym, vol, float(df["close"].iloc[-1]))
        if row:
            return {"ok": True, **row}
    except Exception as exc:                           # noqa: BLE001
        log.debug("breakout.for_symbol(%s) failed: %s", sym, exc)
    return {"ok": False, "symbol": sym}


def history_for_symbol(symbol: str) -> dict:
    """Per-symbol breakout HISTORY for the drill chart — "where did each breakout
    actually fire?" (Ajay 2026-06-15). Returns the trailing-year close/volume
    series PLUS the breakout markers (same definition as the count, via
    volume.breakout_points), so the modal can plot the line and pin a 🚀 at
    every breakout bar:

        {ok, symbol, last_close, breakout_count, window_bars, avg_vol_50,
         series:    [{date, close, volume}, ...],   # oldest -> newest
         breakouts: [{date, close, volume, vol_ratio, footprint}, ...],
         emerging:  {emerging, distance_to_high_pct, pivot_price, hands, ...}}

    Each breakout marker now carries a ``footprint`` (volume.breakout_footprint)
    answering "whose hands fired it?" — institutional accumulation vs churn
    (TTLAC p.186) — and ``emerging`` flags a breakout SETTING UP right now.

    Display-only. Soft-fails to {ok: False, symbol}."""
    sym = (symbol or "").upper().strip()
    try:
        from sepa import prices, volume
        df = prices.load_prices(sym)
        if df is None or len(df) == 0:
            return {"ok": False, "symbol": sym}
        window = df.iloc[-volume.BREAKOUT_COUNT_LOOKBACK:]
        series = [
            {
                "date":   volume._date_str(idx),
                "close":  round(float(prow["close"]), 4),
                "volume": int(prow["volume"]),
            }
            for idx, prow in window.iterrows()
        ]
        vol = volume.analyze(df) or {}
        # Climax-top institutional-distribution read (TTLAC p.186-188) — the
        # mirror of the accumulation footprint: who's SELLING the run.
        try:
            from sepa import climax_distribution, base_count
            bc = base_count.count_bases(df)
            climax = climax_distribution.detect(df, bc)
        except Exception:
            climax = None
        return {
            "ok":             True,
            "symbol":         sym,
            "last_close":     round(float(df["close"].iloc[-1]), 4),
            "breakout_count": vol.get("breakout_count"),
            "window_bars":    int(len(window)),
            "avg_vol_50":     vol.get("avg_vol_50"),
            "series":         series,
            "breakouts":      volume.breakout_points(df),
            # Forward read — a breakout SETTING UP now + whose hands (book p.203
            # pivot / VCP). {"emerging": False} when nothing is coiling.
            "emerging":       volume.emerging_breakout(df),
            # Climax-top distribution — institutions selling into the run
            # (TTLAC p.186-188). {"read": "none"} when not climaxing.
            "climax_distribution": climax,
        }
    except Exception as exc:                           # noqa: BLE001
        log.debug("breakout.history_for_symbol(%s) failed: %s", sym, exc)
    return {"ok": False, "symbol": sym}
