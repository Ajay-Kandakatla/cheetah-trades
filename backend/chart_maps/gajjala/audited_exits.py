"""🧪 Gajjala · Audited — the alternative-exit grades of the audited 🏁 rows (BUILD SPEC 2026-11-01 §3.3, WP-C).

Ajay 2026-11-01: "Yes make the changes in audited please" and "But keep a track record too to see the winners and
loster".

Two EXIT rules of the registry (audited_rules.exit_rules()) change the GRADE of an audited A+ row, never the A+ read,
the claim or the push:
  T3  a fixed target on the 🌀 Intraday VCP rows (audited_rules.T3_SETUPS): win when +k R prints before the stop, one
      column per k in audited_rules.T3_R_MULTS — through `ledger.grade(..., r_mult=k)`, the 🏁's ONE trade-math engine
      (the fill rule, the stop touch, a bar with both = loss, the fill minute's high never counts).
  T5  a 21 EMA trail on every setup: after the fill, exit at the first 5-minute CLOSE strictly under the 21 EMA of the
      GG5 5-minute frame (`bars.build_frames(..., variant=GG5)` — the pass's own resampler, the prior session warming
      the EMA, warm-up masked to None = no exit). The walk, per 5-minute close C: first every 1-minute bar starting
      before C not yet seen — `low ≤ stop` → loss at the stop, r = −1 (the stop always wins inside one minute, the
      fill minute counts: `stop_fill_minute`); then a close under the EMA → exit at that close, r = (close − fill) /
      (trigger − stop), win when r > 0 else loss. A close EXACTLY at the EMA is not under. The bucket holding the fill
      minute counts when it closes after the fill. After the last close: the stop check only. Neither by the regular
      close → open (r None; `close_r` = the last 5-minute close's R so far).

COST RULE [C5]: `load_intraday` NEVER caches today and FETCHES a cold past day (daytrading/data.py:241-253). So the exit
grades land ONE night after the session (`deferred_today`), and only when BOTH symbol-days (the row's session and the
market day before it — the EMA warm-up) are already in `intraday_cache` (`is_warm`, a READ of the cache via
`dt_data._mongo_get_day`, never a fetch). A cold row is `deferred_cold`: nothing loaded, never fetched, retried every
night and counted (HIS CALL #21). Loads go through a per-run memo, bounded by GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS
(`deferred_cap`).

Writes ONLY the GGA store's `gajjala_audited_exits` (store.upsert_exits, closed keys EXITS_KEYS + the exit columns) —
never the 🏁 ledger (LEDGER_KEYS is closed and shared with 🚩 / GG1). Counts, never a verdict: UNMEASURED. Never trades,
never rings.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Callable, Optional

from . import audited_rules as AUD
from . import bars as B
from . import constants as GC
from . import context as CX
from . import ledger as LG
from . import variant as V

log = logging.getLogger("chart_maps.gajjala.audited_exits")

UTC = timezone.utc
EXITS_VERSION = 1                                    # TRANSPORT — bump to re-grade every stored exit column
OUTCOMES = ("win", "loss", "open")                   # + the ledger's entry words (no_entry / no_time / no_plan / no_risk)
T5_KEYS = ("entry", "fill_px", "fill_t", "outcome", "exit_t", "exit_px", "r", "reason", "ema_at_exit", "end_t",
           "bars5_n", "version")
STEP_KEYS = ("rows", "graded", "written", "not_due", "deferred_today", "deferred_cold", "deferred_cap",
             "load_failed", "no_bars", "faulted", "loads")
NO_FRAME = "no_frame"                                # the T5 reason when the GG5 frame could not be built


# ── the cache probe + the ONE loader call ─────────────────────────────────────────────────────────────────────────
def is_warm(sym: str, day: date) -> bool:
    """True when `intraday_cache` holds (sym, day) — a READ of the cache (`dt_data._mongo_get_day`), never a fetch."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    try:
        df = dt_data._mongo_get_day(for_massive(sym), day)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala audited exits: cache probe failed for %s %s: %s", sym, day, type(exc).__name__)
        return False
    return df is not None and not df.empty


def load_day_df(sym: str, day: date) -> tuple:
    """(df | None, provider_failed) — `dt_data.load_intraday` with NO force (the call ledger._default_load_day makes),
    keeping the DataFrame (volume included — the 5-minute frame needs it). Called ONLY after `is_warm` answered True
    for both days of the row, so it reads the cache."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    try:
        dt_data.clear_fetch_failed()
        df = dt_data.load_intraday(for_massive(sym), day, include_premarket=True, include_afterhours=True)
        return df, bool(df is None and dt_data.last_fetch_failed())
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala audited exits: 1-minute load failed for %s %s: %s", sym, day, type(exc).__name__)
        return None, True


# ── the graders (pure) ────────────────────────────────────────────────────────────────────────────────────────────
def t3_grade(row: dict, bars_1m: list, bounds: Optional[dict], r_mult) -> dict:
    """T3: `ledger.grade(row, bars_1m, bounds, "same", r_mult=r_mult)` + {r: +r_mult on a win, −1.0 on a loss, None
    otherwise; r_mult; version}."""
    g = LG.grade(row, bars_1m, bounds, GC.LEDGER_HORIZONS[0], r_mult=r_mult)
    oc = g.get("outcome")
    r = float(r_mult) if oc == OUTCOMES[0] else (-1.0 if oc == OUTCOMES[1] else None)
    return dict(g, r=r, r_mult=float(r_mult), version=EXITS_VERSION)


def _t5_blank() -> dict:
    out = {k: None for k in T5_KEYS}
    out["bars5_n"] = 0
    out["version"] = EXITS_VERSION
    return out


def no_frame_col() -> dict:
    """The T5 column when the GG5 5-minute frame could not be built (written, not retried at this EXITS_VERSION)."""
    return dict(_t5_blank(), reason=NO_FRAME)


def t5_grade(row: dict, bars_1m: list, bounds: Optional[dict], frame5) -> dict:
    """T5: the 21 EMA trail on the 5-minute frame (`frame5` = a bars.Frame, its `ema21` masked) — the module docstring
    states the walk. The fill is the 🏁's own (`ledger.grade(..., "same")`); not filled → the entry word."""
    out = _t5_blank()
    g = LG.grade(row, bars_1m, bounds, GC.LEDGER_HORIZONS[0])
    out["entry"], out["end_t"] = g.get("entry"), g.get("end_t")
    if g.get("entry") != LG.ENTRIES[0]:
        out["reason"] = g.get("reason")
        return out
    if frame5 is None:
        return dict(out, entry=None, reason=NO_FRAME)
    fill = LG._D(g["fill_px"])
    trig, stop = LG._D(row["trigger"]), LG._D(row["stop"])
    risk = trig - stop
    end = bounds["same_end"]
    elig = [b for b in bars_1m or [] if bounds["fill_from"] <= b[0] < end]      # the bars grade walked
    k = next(i for i, b in enumerate(elig) if LG._iso_t(b[0]) == g["fill_t"])
    fill_t = elig[k][0]
    out.update(fill_px=float(fill), fill_t=g["fill_t"])
    from . import alerts as AL
    closes5 = []
    for j in frame5.today:
        ce = AL.bar_close_et(frame5.t[j])
        if ce is None:
            continue
        cu = ce.astimezone(UTC)
        if fill_t < cu <= end:
            closes5.append((cu, frame5.c[j], frame5.ema21[j]))
    out["bars5_n"] = len(closes5)
    pos = [k]

    def stop_hit(limit) -> Optional[int]:
        """Walk the unseen 1-minute bars starting before `limit` (None = to the end): the first stop touch, or None."""
        i = pos[0]
        while i < len(elig) and (limit is None or elig[i][0] < limit):
            if LG._D(elig[i][3]) <= stop:
                pos[0] = i + 1
                return i
            i += 1
        pos[0] = i
        return None

    def stopped(i: int) -> dict:
        return dict(out, outcome=OUTCOMES[1], r=-1.0, exit_px=float(stop), exit_t=LG._iso_t(elig[i][0]),
                    reason=("stop_fill_minute" if i == k else "stop"))

    for cu, c, e in closes5:
        hit = stop_hit(cu)
        if hit is not None:
            return stopped(hit)
        if e is not None and LG._D(c) < LG._D(e):
            r = float((LG._D(c) - fill) / risk)
            return dict(out, outcome=(OUTCOMES[0] if r > 0 else OUTCOMES[1]), r=r, exit_px=float(c),
                        exit_t=LG._iso_t(cu), reason="ema21_close", ema_at_exit=float(e))
    hit = stop_hit(None)
    if hit is not None:
        return stopped(hit)
    close_r = float((LG._D(closes5[-1][1]) - fill) / risk) if closes5 else None
    return dict(out, outcome=OUTCOMES[2], r=None, reason="horizon_end", close_r=close_r)


# ── the nightly step ──────────────────────────────────────────────────────────────────────────────────────────────
def _current(doc: dict, col: str) -> bool:
    c = (doc or {}).get(col)
    return isinstance(c, dict) and c.get("version") == EXITS_VERSION


def _cols() -> tuple:
    """({T3 col: r_mult}, T5 col) — built from the registry (audited_rules.exit_col_key / T3_R_MULTS), never typed."""
    t3 = {AUD.exit_col_key(AUD.T3.id, k): k for k in AUD.T3_R_MULTS}
    return t3, AUD.exit_col_key(AUD.T5.id)


def grade_exits(gga, now: datetime, *, load_df: Optional[Callable] = None, warm: Optional[Callable] = None,
                max_loads: Optional[int] = None, dry: bool = False) -> dict:
    """🧪 The exit grades of every audited A+ row of the grade window (ledger.grade_step's sessions, clipped to the GGA
    record): T5 on every row, the T3 columns on the T3_SETUPS rows; a column stored at EXITS_VERSION is skipped. A row
    with no plan / no alert time gets its entry word (no load). Then: not ended → `not_due`; its session is today →
    `deferred_today` (graded the next night — today is never cached); either symbol-day cold → `deferred_cold` (nothing
    loaded); over the load cap → `deferred_cap`; a provider failure → `load_failed`; no minute of the session →
    `no_bars` — each retried next night, nothing written. -> the step summary (STEP_KEYS + read_fault, dry, sessions)."""
    from . import nightly as NG
    now = LG._aware(now)
    today = NG.default_session(now)
    sessions = LG._clip(CX.history_window(LG._next_market_day(today), GC.LEDGER_GRADE_LOOKBACK_SESSIONS), V.GGA)
    out: dict = {"sessions": [d.isoformat() for d in sessions], "read_fault": False, "dry": bool(dry)}
    out.update({k: 0 for k in STEP_KEYS})
    try:
        rows = [r for r in LG.rows_for(sessions, gga, variant=V.GGA) if r["kind"] == LG.KINDS[1]]
    except LG.LedgerReadError:
        out["read_fault"] = True
        return out
    stored = gga.exits_docs(sessions)
    if stored is None:
        out["read_fault"] = True
        return out
    docs = {d.get("_id"): d for d in stored if isinstance(d, dict) and d.get("_id")}
    out["rows"] = len(rows)
    cap = int(max_loads) if max_loads is not None else int(GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS)
    load = load_df or load_day_df
    probe = warm or is_warm
    t3_cols, t5_col = _cols()
    memo: dict = {}
    warm_memo: dict = {}
    cold_ids: list = []
    stamp = now.isoformat()

    def warm_of(sym: str, d: date) -> bool:
        if (sym, d) not in warm_memo:
            try:
                warm_memo[(sym, d)] = bool(probe(sym, d))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala audited exits: warm probe raised for %s %s: %s", sym, d, type(exc).__name__)
                warm_memo[(sym, d)] = False
        return warm_memo[(sym, d)]

    def days_for(sym: str, days: list) -> tuple:
        """-> (status, {day: df}) — status ok | deferred_cap | load_failed."""
        miss = [d for d in days if (sym, d) not in memo]
        if out["loads"] + len(miss) > cap:
            return "deferred_cap", {}
        for d in miss:
            out["loads"] += 1
            try:
                res = load(sym, d)
                df, failed = (res if isinstance(res, tuple) else (res, False))
            except Exception as exc:                            # noqa: BLE001
                log.warning("gajjala audited exits: load raised for %s %s: %s", sym, d, type(exc).__name__)
                df, failed = None, True
            memo[(sym, d)] = (df, bool(failed))
        if any(memo[(sym, d)][1] for d in days):
            return "load_failed", {}
        return "ok", {d: memo[(sym, d)][0] for d in days}

    for row in rows:
        try:
            rid = row["id"]
            doc = docs.get(rid) or {}
            want = [t5_col] + (list(t3_cols) if row.get("setup") in AUD.T3_SETUPS else [])
            want = [c for c in want if not _current(doc, c)]
            if not want:
                continue
            b = LG._bounds_of(row)
            cols: dict = {}
            if row.get("plan") != LG.PLANS[0] or b is None:
                for c in want:                                  # the entry word, once — no load
                    cols[c] = t3_grade(row, [], b, t3_cols[c]) if c in t3_cols else t5_grade(row, [], b, None)
            else:
                if now < b["same_end"] + LG.SETTLE:
                    out["not_due"] += 1
                    continue
                if b["same_date"] >= today:
                    out["deferred_today"] += 1
                    continue
                sym = row["symbol"]
                prev = LG._prev_market_day(b["same_date"])
                if not (warm_of(sym, b["same_date"]) and warm_of(sym, prev)):
                    out["deferred_cold"] += 1
                    cold_ids.append(rid)
                    continue
                status, by_day = days_for(sym, [b["same_date"], prev])
                if status != "ok":
                    out[status] += 1
                    continue
                df_same, df_prev = by_day[b["same_date"]], by_day[prev]
                bars_1m = LG.bars_from_frame(df_same)
                if not bars_1m:
                    out["no_bars"] += 1
                    continue
                for c in want:
                    if c in t3_cols:
                        cols[c] = t3_grade(row, bars_1m, b, t3_cols[c])
                if t5_col in want:
                    frames = B.build_frames(sym, b["same_date"], b["same_end"] + LG.SETTLE, df_prev, df_same,
                                            variant=V.GG5)
                    cols[t5_col] = (t5_grade(row, bars_1m, b, frames.frame(AUD.T5_FRAME)) if frames is not None
                                    else no_frame_col())
            out["graded"] += 1
            if dry:
                continue
            body = {"date": row["date"], "symbol": row["symbol"], "setup": row["setup"], "kind": row["kind"],
                    "alert": LG._alert_block(row), "graded_at": stamp, "version": EXITS_VERSION}
            body.update(cols)
            if gga.upsert_exits(rid, body, cols=AUD.EXIT_COLS):
                out["written"] += 1
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala audited exits: grading %s failed: %s", row.get("id"), type(exc).__name__)
            out["faulted"] += 1
    if cold_ids:
        log.info("gajjala audited exits: deferred_cold (never fetched, HIS CALL #21): %s", ", ".join(cold_ids))
    return out
