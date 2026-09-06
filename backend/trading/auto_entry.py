"""Auto-entry — the engine BUYS Ajay's own SEPA picks (paper first, 2026-06-12).

Candidate funnel (the book lives in the SCANNER, not here):
  sepa.scanner latest scan rows where is_buyable == True (Trend Template p.79
  + Stage 2 + VCP/Power-Play pivot + volume-confirmed breakout, not extended
  past the pivot p.224) AND score >= AUTO_MIN_SCORE AND rs_rank >= AUTO_MIN_RS
  (p.79 criterion 8: "preferably in the 80s or 90s") AND entry_setup.pivot
  exists — all read from a TRUSTED scan only (fresh + market-sized universe,
  see scan_trusted). Sorted by score desc. Risk math (stop/target/size/streak)
  is NOT re-derived here either — every buy flows through
  trading.entries.enter(), which uses trading/risk_rules.py (TLSW pp.291-315,
  page-cited, FROZEN).

Hybrid trigger, two paths per symbol:
  a. INTRADAY        live > pivot, AND the FIRST tick we ever observed
                     live > pivot happened in the first half of the session
                     (cleared_at_frac <= FIRST_HALF_FRACTION, persisted per
                     symbol+ET-day in the auto_entry_state Mongo coll), AND
                     projected RelVol >= AUTO_RELVOL_MIN (sepa.live_gate),
                     AND live <= pivot * (1 + MAX_EXTENSION_PCT/100).
  b. CLOSE-CONFIRM   not entered intraday, prev_day_close > pivot AND
                     live > pivot AND not extended past the same cap ->
                     enter at next-morning ticks. No after-hours machinery.

Safety invariants (same house rules as exit_engine/entries):
  * NEVER places an order at the broker directly — buys flow through
    entries.enter() so armed / sizing / never-average-down / earnings all
    still apply (contract test greps this module for broker order calls).
  * armed=false places NO orders, ever.
  * run() is called from exit_engine.tick() inside try/except — an
    auto-entry crash can never break stop protection.
  * Import-light: no pandas at import time; every sepa import is lazy.

──────────────────────────────────────────────────────────────────────────────
ENGINE PARAMETERS — owner (Ajay) choices for the hybrid trigger, NOT
book-cited numbers. Minervini gives the SETUP and the RISK MATH; he does not
give an entries-per-day cap, a relative-volume floor, a session-half cutoff,
or a dollar cap for a paper trial. These five are engine tuning, locked in
tests/test_trading_contracts.py and documented (with this same honesty note)
in docs/sepa/auto_entry_methodology.md. Changing any of them needs Ajay's
sign-off, not a book page.
──────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import logging
import math
from typing import Optional

from trading import entries
from trading import risk_rules
from trading.broker import get_broker
from trading.exit_engine import (
    _broker_mode, _db, _et_day, _utc_iso, get_config, ledger, update_config)

broker = get_broker()    # module-level so tests can monkeypatch AE.broker

log = logging.getLogger("trading.auto_entry")

# Max auto buys per ET day — observation-friendly pace for the paper week.
MAX_AUTO_ENTRIES_PER_DAY = 2
# Projected full-session relative volume floor for the INTRADAY path
# (sepa.live_gate projects today's pace vs the 50-day average).
AUTO_RELVOL_MIN = 1.5
# Volume-projection TRUST FLOOR (added 2026-07-09 after the failure autopsy;
# raised 60 -> 120 min 2026-07-12, Ajay: "first 1 hour of the day the market
# is still volatile"). TLSW p.229 ("Extrapolating Volume Intraday")
# demonstrates the projection "two hours into the trading day" — minutes into
# the open the denominator is so small that ANY opening print projects as
# huge RelVol, which is exactly how 12 of 18 auto-entries fired at 9:30-9:32
# and 4 of 6 closed trades stopped out. Before this fraction of the session
# has elapsed, a PROJECTED RelVol cannot trigger the intraday path; ACTUAL
# volume already >= the floor (vs the FULL 50-day average) can trigger at any
# time — a true monster open proves itself without projection. 120 min now
# MATCHES the book's own demonstration (honesty note: the book demonstrates
# 2h, it does not mandate a minimum — the floor itself stays an owner rule).
VOL_CONFIRM_MIN_FRAC = round(120.0 / 390.0, 4)  # 0.3077 of the 390-min session
# The first observed pivot-clear must land in the first half of the session
# (session_fraction <= this) for the intraday path; later clears wait for
# the close-confirmation path.
FIRST_HALF_FRACTION = 0.5
# Buy-zone ceiling above the pivot. MIRRORS sepa.scanner.BUYABLE_MAX_EXT_PCT
# (book p.224 "without chasing ... more than a few percentage points" — no
# exact book number; 3% is the user-approved 2026-06-09 house value). Not
# imported because sepa.scanner pulls pandas at import time; the contract
# test cross-locks both source tokens so they cannot drift apart.
MAX_EXTENSION_PCT = 3.0
# "assume you have 5k" — sizing equity is min(Alpaca equity, this cap) for
# ALL entries (Alpaca paper accounts default to $100k).
DEFAULT_EQUITY_CAP = 5000.0
# Funnel score floor — owner choice, raised 70 -> 85 (Ajay 2026-07-09) after
# the failure autopsy: winners scored 87-94, no loser scored above 84, and
# the two lowest-scored entries ever taken (62.2, 60.7) both stopped out.
# n=6 — a HYPOTHESIS being enforced, not a proven law; the `auto_min_score`
# config key overrides it live (data write, no deploy) so it can be tuned
# as the sample grows.
AUTO_MIN_SCORE = 85.0
# Funnel RS floor (added 2026-07-12 after the low-RS audit). Trend Template
# criterion 8 (TLSW p.79): RS "no less than 70, and preferably in the 80s or
# 90s, which will generally be the case with the better selections." The
# scanner's is_buyable enforces the hard 70 floor; an UNATTENDED engine should
# only take the better selections, so its own floor sits at the book's
# preferred band. Evidence (18 auto-entries, 6 closed): both winners were RS
# 87+ (ARM 98 +15%, ILMN 87 +12%); three of four losers were RS <= 82 (UFPT 76
# -8.5%, IRM 79 -6.1%, CACC 82 -6.0%). Small n — the `auto_min_rs` config key
# overrides it live (data write, no deploy). Missing rs_rank fails CLOSED.
AUTO_MIN_RS = 80.0
# Scan-trust guards (added 2026-07-12). rs_rank is a PERCENTILE WITHIN THE
# SCANNED UNIVERSE (sepa.rs_rank.rs_ranks) — a small manual scan (curated
# mode, ~dozens of names) that overwrites latest.json produces distorted
# ranks (EIX read 64-75 across same-day runs). The engine only trades a scan
# that covered a market-sized pool AND is from today or the previous trading
# day (weekday-walk; holidays self-heal because the 16:30 fast-scan cron runs
# Mon-Fri regardless). Both fail CLOSED — a stale/small scan sits out.
MIN_RS_UNIVERSE = 500
# Leaky-pivot suppressor (added 2026-07-12; MOVED to sepa/pivot_leakage.py
# the same day so the SEPA scanner can stamp the identical read on scan
# rows for the Global + general pages). Minervini on X, 2026: "pivot
# leakage" — see the shared module for the full quote, mechanization, and
# the fail-OPEN rationale. The INTRADAY path is suppressed on a leaky
# pivot; the close-confirmation path is exempt (a full close above the
# pivot IS the volatility subsiding). sepa.pivot_leakage is STDLIB-ONLY,
# so this module-level import keeps auto_entry pandas-free.
from sepa.pivot_leakage import (                   # noqa: E402
    PIVOT_LEAK_COOLOFF_DAYS, PIVOT_LEAK_LOOKBACK, PIVOT_LEAK_MAX,
    pivot_leaky)

FUNNEL_CITE = ("funnel: scanner is_buyable (trend template p.79 + stage 2 + "
               "pivot + volume breakout, ext cap p.224) + score floor "
               "(default 85, cfg auto_min_score) + RS floor (default 80, "
               "p.79 'preferably in the 80s or 90s', cfg auto_min_rs) + "
               "p.229 volume gate + fresh market-sized scan; risk "
               "math pp.291-315 via entries/risk_rules")

PYRAMID_CITE = ("pyramid add: held name reads is_buyable again at a NEW "
                "pivot above avg cost -> top up to full size (TTLAC section 3 "
                "'Add and Reduce' + section 5 scale-up; TLSW pp.307-308 "
                "'pilot buys ... larger positions should be added'); same "
                "trigger gates as entries; p.312 ceiling never exceeded; "
                "cfg pyramiding")


# ── Lazy sepa seams (each one monkeypatchable in tests) ─────────────────────

def _latest_scan_rows() -> list:
    """Rows of the latest completed SEPA scan — the SAME reader GET /sepa/scan
    uses (sepa.scanner.load_latest -> ~/.cheetah/scans/latest.json; the scan
    is file-persisted, with a separate Mongo history written by sepa.history).
    all_results carries every analyzed symbol; candidates is the slim list."""
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        return latest.get("all_results") or latest.get("candidates") or []
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: latest scan unavailable: %s", exc)
        return []


def _scan_meta() -> dict:
    """generated_at (epoch) + universe_size of the scan the funnel reads —
    same latest.json _latest_scan_rows loads. Missing file/keys -> {} (the
    trust gate fails closed on it)."""
    try:
        from sepa import scanner
        latest = scanner.load_latest() or {}
        return {"generated_at": latest.get("generated_at"),
                "universe_size": latest.get("universe_size")}
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: scan meta unavailable: %s", exc)
        return {}


def _prev_trading_day(day):
    """Previous weekday (holiday-naive — see MIN_RS_UNIVERSE comment)."""
    from datetime import timedelta
    d = day - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d


def scan_trusted(meta: dict, today=None) -> tuple:
    """Both scan-trust guards as one pure, unit-tested read.

    FRESH:  the scan's ET date is today or the previous trading day —
            the book's evening-scan -> next-day-pivot routine, never older.
    SIZED:  universe_size >= MIN_RS_UNIVERSE so the universe-relative
            rs_rank percentile approximates a market rank.

    Missing generated_at / universe_size fails CLOSED (no trades on a scan
    we cannot date or size). Returns (ok, detail-dict for status/ledger)."""
    from datetime import datetime, date
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    today = today or datetime.now(et).date()
    gen = (meta or {}).get("generated_at")
    size = (meta or {}).get("universe_size")
    scan_day = None
    try:
        if gen:
            scan_day = datetime.fromtimestamp(float(gen), et).date()
    except (TypeError, ValueError, OSError):
        scan_day = None
    fresh = scan_day is not None and scan_day >= _prev_trading_day(today)
    sized = False
    try:
        sized = size is not None and int(size) >= MIN_RS_UNIVERSE
    except (TypeError, ValueError):
        sized = False
    detail = {"scan_date": scan_day.isoformat() if scan_day else None,
              "universe_size": size, "fresh": bool(fresh),
              "sized": bool(sized), "min_universe": MIN_RS_UNIVERSE}
    return bool(fresh and sized), detail


def _bulk_live(symbols: list) -> dict:
    """ONE batched live-quote call for every surviving candidate per tick
    (sepa.prices.bulk_live_prices: {SYM: {price, volume, prev_day_close,...}})."""
    if not symbols:
        return {}
    try:
        from sepa.prices import bulk_live_prices
        return bulk_live_prices(list(symbols)) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: bulk live prices failed: %s", exc)
        return {}


def _session_fraction() -> float:
    """Fraction of the 9:30-16:00 ET session elapsed (sepa.live_gate)."""
    try:
        from sepa.live_gate import session_fraction
        return float(session_fraction())
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: session_fraction failed: %s", exc)
        return 0.0


def _volume_live(symbol: str) -> dict:
    """volume_live block from sepa.live_gate (projected_relvol, today_volume,
    avg_vol_50) — called ONLY for names that already passed every cheap check
    (it reloads daily prices)."""
    try:
        from sepa.live_gate import live_gate
        out = live_gate(symbol) or {}
        return out.get("volume_live") or {}
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: live_gate volume failed %s: %s", symbol, exc)
        return {}


def volume_confirmed(frac: float, vol_live: dict) -> tuple:
    """The TLSW p.229 volume gate for the intraday path. Pure — unit-tested.

    PASS when either:
      a. ACTUAL today's volume already >= AUTO_RELVOL_MIN x the full 50-day
         average — the tape has proven itself, any time of day; or
      b. the session is past VOL_CONFIRM_MIN_FRAC AND the projected
         full-session RelVol >= AUTO_RELVOL_MIN — the p.229 extrapolation,
         trusted only once enough tape exists to extrapolate FROM.

    Missing volume data fails CLOSED (no buy on unknown volume).
    Returns (ok, detail-dict-for-the-checks-snapshot)."""
    proj = vol_live.get("projected_relvol")
    today = vol_live.get("today_volume")
    avg50 = vol_live.get("avg_vol_50")
    actual = None
    try:
        if today and avg50 and float(avg50) > 0:
            actual = round(float(today) / float(avg50), 2)
    except (TypeError, ValueError):
        actual = None
    detail = {"projected_relvol": proj, "actual_relvol": actual,
              "session_frac": round(float(frac), 4),
              "min_frac": VOL_CONFIRM_MIN_FRAC}
    if actual is not None and actual >= AUTO_RELVOL_MIN:
        detail["basis"] = "actual"
        return True, detail
    if float(frac) >= VOL_CONFIRM_MIN_FRAC and proj is not None \
            and float(proj) >= AUTO_RELVOL_MIN:
        detail["basis"] = "projected"
        return True, detail
    detail["basis"] = ("too_early_to_project"
                       if float(frac) < VOL_CONFIRM_MIN_FRAC else "insufficient_volume")
    return False, detail


def _recent_daily_bars(symbol: str, n: int = PIVOT_LEAK_LOOKBACK) -> dict:
    """Last `n` COMPLETED daily bars (today's bar excluded if present) for
    the leaky-pivot read. {} / empty lists when prices are unavailable —
    pivot_leaky fails open on that. Called ONLY for names that already
    passed every cheap check AND the volume gate (at most a handful/tick)."""
    try:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        from sepa.prices import load_prices
        df = load_prices(symbol)
        if df is None or len(df) == 0:
            return {}
        today = datetime.now(ZoneInfo("America/New_York")).date()
        try:
            if df.index[-1].date() >= today:
                df = df.iloc[:-1]
        except (AttributeError, TypeError):
            pass
        tail = df.iloc[-n:]
        return {"highs": [float(v) for v in tail["high"]],
                "closes": [float(v) for v in tail["close"]]}
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: daily bars failed %s: %s", symbol, exc)
        return {}


def _gauge_state() -> str:
    """RAW Market Gauge state ('constructive'|'caution'|'risk_off') — the
    same underlying read exit_engine.regime() maps to normal/difficult, but
    auto-entry vetoes on the raw 'risk_off' verdict itself. Unavailable
    gauge degrades to '' (no veto), matching regime()'s degrade-to-normal."""
    try:
        from sepa.market_gauge import get_gauge
        return str((get_gauge(prefer_persisted=True) or {}).get("state") or "").lower()
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: gauge unavailable: %s", exc)
        return ""


def _earnings_days(symbol: str) -> Optional[int]:
    """Days to the next earnings event — the SAME helper entries.py uses
    (sepa.earnings_watch.next_event). None = no known upcoming event."""
    try:
        from sepa.earnings_watch import next_event
        ev = next_event(symbol)
        return ev.get("days_to") if ev else None
    except Exception as exc:                       # noqa: BLE001
        log.debug("auto_entry: earnings lookup failed %s: %s", symbol, exc)
        return None


def _notify(kind: str, ticker: str, detail: str) -> None:
    """Owner push (push.hooks.notify_autopilot). Failures logged + swallowed."""
    try:
        from push.hooks import notify_autopilot
        notify_autopilot(kind, ticker, detail)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry: push failed (%s %s): %s", kind, ticker, exc)


# ── auto_entry_state (per symbol + ET day) ──────────────────────────────────

def _state_coll():
    db = _db()
    return None if db is None else db.auto_entry_state


def _get_state(symbol: str, day: str) -> dict:
    coll = _state_coll()
    if coll is None:
        return {}
    try:
        return coll.find_one({"symbol": symbol, "date": day}) or {}
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state read failed %s: %s", symbol, exc)
        return {}


def _set_state(symbol: str, day: str, **fields) -> None:
    coll = _state_coll()
    if coll is None:
        return
    fields["updated_at"] = _utc_iso()
    try:
        coll.update_one({"symbol": symbol, "date": day},
                        {"$set": fields}, upsert=True)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state write failed %s: %s", symbol, exc)


def _entries_today(day: str) -> int:
    coll = _state_coll()
    if coll is None:
        return 0
    try:
        return sum(1 for _ in coll.find({"date": day, "entered": True}))
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state count failed: %s", exc)
        return 0


def _today_snapshots(day: str) -> list:
    coll = _state_coll()
    rows = []
    if coll is None:
        return rows
    try:
        for d in coll.find({"date": day}):
            d.pop("_id", None)
            rows.append(d)
    except Exception as exc:                       # noqa: BLE001
        log.warning("auto_entry_state list failed: %s", exc)
    return rows


# ── Funnel + trigger pieces ─────────────────────────────────────────────────

def _min_score(cfg: Optional[dict] = None) -> float:
    """Score floor: `auto_min_score` config override, else AUTO_MIN_SCORE."""
    try:
        v = (cfg or {}).get("auto_min_score")
        return float(v) if v is not None else AUTO_MIN_SCORE
    except (TypeError, ValueError):
        return AUTO_MIN_SCORE


def _min_rs(cfg: Optional[dict] = None) -> float:
    """RS floor: `auto_min_rs` config override, else AUTO_MIN_RS."""
    try:
        v = (cfg or {}).get("auto_min_rs")
        return float(v) if v is not None else AUTO_MIN_RS
    except (TypeError, ValueError):
        return AUTO_MIN_RS


def _pyramiding_enabled(cfg: Optional[dict] = None) -> bool:
    """Pyramid adds (TTLAC §3/§5, TLSW pp.307-308): `pyramiding` config key,
    default ON; only an explicit stored False turns it off."""
    v = (cfg or {}).get("pyramiding")
    return True if v is None else bool(v)


def _candidates(min_score: float = AUTO_MIN_SCORE,
                min_rs: float = AUTO_MIN_RS) -> list:
    """Latest-scan rows passing the funnel, score desc. A row with no
    rs_rank at all is skipped (fail closed), same as rs below the floor."""
    out = []
    for r in _latest_scan_rows():
        try:
            if not r.get("is_buyable"):
                continue
            score = float(r.get("score") or 0)
            rs = r.get("rs_rank")
            pivot = (r.get("entry_setup") or {}).get("pivot")
            if score < min_score or not pivot or float(pivot) <= 0:
                continue
            if rs is None or float(rs) < min_rs:
                continue
            sym = (r.get("symbol") or "").strip().upper()
            if sym:
                out.append(r)
        except (TypeError, ValueError):
            continue
    out.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    return out


def _structural_stop_pct(row: dict, live: float) -> Optional[float]:
    """The scan row's entry_setup.stop as a stop_pct request — passed to
    entries.enter ONLY when it is BETWEEN 1% and risk_rules.DEFAULT_STOP_PCT
    below the live price (structure stop tighter than the band default =
    allowed; wider = ignored, band default applies)."""
    stop = (row.get("entry_setup") or {}).get("stop")
    try:
        stop = float(stop)
    except (TypeError, ValueError):
        return None
    if not live or live <= 0 or stop <= 0 or stop >= live:
        return None
    dist = (live - stop) / live * 100.0
    if 1.0 <= dist <= risk_rules.DEFAULT_STOP_PCT:
        return round(dist, 2)
    return None


def _check(checks: dict, name: str, ok: bool, value=None) -> bool:
    checks[name] = {"pass": bool(ok), "value": value}
    return bool(ok)


def _never_auto_stop() -> bool:
    """Paper/sim: never auto-STOP entries on the daily cap or a risk-off gauge —
    let the engine cycle entries+exits continuously until the user disarms or
    turns auto-entry off (Ajay 2026-06-26: 'never stop auto entry and exit until
    I say so, for paper'). Live keeps BOTH guardrails.

    This lifts only the time/regime auto-stops. Every per-order safety still
    applies in EVERY mode: MAX_POSITIONS capacity, a resting stop, never-average-
    up, the earnings shield, and the per-name pivot/RelVol trigger — so the
    engine keeps cycling but never trades incorrectly."""
    try:
        return _broker_mode() != "live"
    except Exception:                              # noqa: BLE001
        return False                               # fail safe → keep the cap


def entry_cap(never_stop: bool) -> float:
    """Per-day auto-entry ceiling: unlimited in paper/sim, the book cap in live."""
    return math.inf if never_stop else float(MAX_AUTO_ENTRIES_PER_DAY)


def gauge_allows(never_stop: bool, gauge: str) -> bool:
    """Risk-off gauge halts new entries in live; in paper/sim it does not stop them."""
    return bool(never_stop) or gauge != "risk_off"


def _ledger_disabled_once(cfg: dict, gate: dict) -> bool:
    """One auto_entry_disabled ledger row per ET day max (no tick spam)."""
    today = _et_day()
    if cfg.get("last_auto_entry_disabled_day") == today:
        return False
    ledger("auto_entry_disabled",
           detail={"gate": gate,
                   "hint": "needs configured + armed + auto_entry flag + market open"})
    update_config(last_auto_entry_disabled_day=today)
    return True


# ── The per-tick runner (called from exit_engine.tick, AFTER exits) ─────────

def run(broker=None, cfg: Optional[dict] = None) -> dict:
    """Evaluate every funnel candidate once; place at most
    MAX_AUTO_ENTRIES_PER_DAY buys via entries.enter(). Returns a summary.

    The `broker` param shadows the module-level import on purpose (tick()
    passes its own — possibly monkeypatched — reference); the globals()
    fallback resolves the module attribute so test monkeypatching of
    AE.broker works when called with no args."""
    brk = broker if broker is not None else globals()["broker"]
    cfg = cfg or get_config()
    day = _et_day()
    out = {"ok": True, "ran": False, "day": day, "entered": [], "blocked": [],
           "evaluated": 0, "entries_today": 0, "errors": []}

    # Master gate: configured AND armed AND auto_entry flag AND market open.
    gate = {"configured": bool(brk.configured()),
            "armed": bool(cfg.get("armed")),
            "auto_entry": bool(cfg.get("auto_entry")),
            "market_open": False}
    if gate["configured"]:
        try:
            gate["market_open"] = bool(brk.clock().get("is_open"))
        except Exception as exc:                   # noqa: BLE001
            out["errors"].append("clock: %s" % exc)
    if not all(gate.values()):
        _ledger_disabled_once(cfg, gate)
        out["reason"] = "gated"
        out["gate"] = gate
        return out
    out["ran"] = True

    # Scan-trust gate — never trade a stale scan or small-universe RS ranks.
    trusted, scan_detail = scan_trusted(_scan_meta())
    out["scan"] = scan_detail
    if not trusted:
        out["reason"] = "untrusted_scan"
        if cfg.get("last_auto_entry_scan_warn_day") != day:
            ledger("auto_entry_skipped_scan",
                   detail=dict(scan_detail,
                               hint="scan is stale or covered too few names "
                                    "for a trustworthy RS rank — engine sits "
                                    "out until the next broad scan"))
            update_config(last_auto_entry_scan_warn_day=day)
        return out

    cands = _candidates(min_score=_min_score(cfg), min_rs=_min_rs(cfg))
    if not cands:
        out["reason"] = "no_candidates"
        return out

    try:
        positions = brk.positions()
    except Exception as exc:                       # noqa: BLE001
        out["ok"] = False
        out["errors"].append("positions: %s" % exc)
        return out
    pos_count = len(positions)
    entries_today = _entries_today(day)
    gauge = _gauge_state()
    # Paper/sim: lift the daily cap + the risk-off halt so the engine never
    # auto-stops cycling; live keeps both. Per-order gates are untouched.
    never_stop = _never_auto_stop()
    cap_limit = entry_cap(never_stop)

    held_map = {(p.get("symbol") or "").upper(): p for p in positions}

    # Cheap-first pass (no quotes needed) — survivors get ONE batched quote.
    # A HELD symbol that reads is_buyable again is a PYRAMID candidate
    # (TTLAC §3 Add and Reduce / §5 scale-up, TLSW pp.307-308): instead of
    # being skipped it goes through the SAME trigger machinery and, if it
    # fires, tops the position up to full size via entries.enter(top_up=True).
    # Adds require the fresh pivot ABOVE our average cost ("profits finance
    # additional risk") and don't consume a position slot (same slot).
    survivors = []
    for row in cands:
        sym = (row.get("symbol") or "").upper()
        out["evaluated"] += 1
        st = _get_state(sym, day)
        checks = {}
        is_add = sym in held_map
        avg_cost = None
        if is_add:
            try:
                avg_cost = float(held_map[sym].get("avg_entry_price") or 0)
            except (TypeError, ValueError):
                avg_cost = 0.0
            pivot_raw = (row.get("entry_setup") or {}).get("pivot")
            ok = _check(checks, "pyramiding_enabled",
                        _pyramiding_enabled(cfg), bool(_pyramiding_enabled(cfg)))
            ok &= _check(checks, "add_pivot_above_cost",
                         bool(avg_cost and pivot_raw
                              and float(pivot_raw) > avg_cost),
                         {"pivot": pivot_raw, "avg_cost": avg_cost})
        else:
            ok = _check(checks, "not_already_held", True, False)
            ok &= _check(checks, "position_slots",
                         pos_count < risk_rules.MAX_POSITIONS, pos_count)
        ok &= _check(checks, "not_attempted_today",
                     not (st.get("entered") or st.get("attempted")),
                     bool(st.get("entered") or st.get("attempted")))
        ok &= _check(checks, "daily_cap",
                     entries_today < cap_limit, entries_today)
        ok &= _check(checks, "gauge_not_risk_off",
                     gauge_allows(never_stop, gauge), gauge)
        edays = _earnings_days(sym)
        ok &= _check(checks, "earnings_shield",
                     edays is None or edays > entries.EARNINGS_SHIELD_DAYS, edays)
        if ok:
            survivors.append((row, checks, is_add))
        elif not (st.get("entered") or st.get("attempted")):
            # Snapshot the skip — but NEVER overwrite a terminal snapshot
            # (entered / blocked / error): once attempted, the trigger-time
            # eval is the informative one and must survive later ticks.
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": (row.get("entry_setup") or {}).get("pivot"),
                                  "checks": checks, "result": "skipped"})

    quotes = _bulk_live([(r.get("symbol") or "").upper() for r, _, _ in survivors])
    frac = _session_fraction()

    for row, checks, is_add in survivors:
        sym = (row.get("symbol") or "").upper()
        pivot = float((row.get("entry_setup") or {}).get("pivot"))
        q = quotes.get(sym) or {}
        live = q.get("price") or q.get("last_trade_price")
        prev_close = q.get("prev_day_close")
        result = "skipped"

        # Re-check the MUTABLE caps — entries placed earlier in THIS tick
        # consume daily-cap and position slots after the cheap pass ran.
        # An add re-uses its own slot, so only the daily cap applies.
        cap_ok = _check(checks, "daily_cap",
                        entries_today < cap_limit, entries_today)
        slot_ok = is_add or _check(checks, "position_slots",
                                   pos_count < risk_rules.MAX_POSITIONS,
                                   pos_count)
        if not (cap_ok and slot_ok):
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue

        if not _check(checks, "live_quote", bool(live), live):
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue
        live = float(live)

        # First-ever pivot clear today -> persist the session fraction.
        st = _get_state(sym, day)
        cleared_frac = st.get("cleared_at_frac")
        above = live > pivot
        if above and cleared_frac is None:
            cleared_frac = round(frac, 4)
            _set_state(sym, day,
                       cleared_at_frac=cleared_frac)

        extended = live > pivot * (1 + MAX_EXTENSION_PCT / 100.0)
        _check(checks, "live_above_pivot", above,
               {"live": live, "pivot": pivot})
        _check(checks, "not_extended", not extended,
               round((live / pivot - 1) * 100, 2) if pivot else None)

        path = None
        relvol = None
        if above and not extended:
            # path a — intraday: first-half clear + the p.229 volume gate
            # (projection trusted only past VOL_CONFIRM_MIN_FRAC; actual
            # volume >= floor passes any time; missing data fails closed).
            first_half = (cleared_frac is not None
                          and cleared_frac <= FIRST_HALF_FRACTION)
            _check(checks, "cleared_first_half", first_half, cleared_frac)
            if first_half:
                vol_live = _volume_live(sym)
                ok_vol, vol_detail = volume_confirmed(frac, vol_live)
                relvol = vol_detail.get("projected_relvol")
                if _check(checks, "volume_confirmed", ok_vol, vol_detail):
                    # Leaky-pivot suppressor (X-anchored, see constants) —
                    # intraday only; close-confirm below is exempt.
                    bars = _recent_daily_bars(sym)
                    leaky, leak_detail = pivot_leaky(
                        bars.get("highs"), bars.get("closes"), pivot)
                    if _check(checks, "pivot_not_leaky", not leaky,
                              leak_detail):
                        path = "intraday"
            # path b — close-confirmation: prior close already above pivot
            if path is None:
                cc = bool(prev_close) and float(prev_close) > pivot
                _check(checks, "close_confirm", cc, prev_close)
                if cc:
                    path = "close_confirm"

        if path is None:
            _set_state(sym, day,
                       last_eval={"ts": _utc_iso(), "score": row.get("score"),
                                  "pivot": pivot, "checks": checks,
                                  "result": result})
            continue

        # Triggered -> buy through the ONLY buy path (entries.enter applies
        # armed / sizing / equity cap / never-average-down / earnings again;
        # NO earnings override in auto mode).
        trigger = {"path": path, "pivot": pivot, "live": live,
                   "relvol": relvol, "cleared_at_frac": cleared_frac,
                   "prev_day_close": prev_close, "add": bool(is_add)}
        stop_req = _structural_stop_pct(row, live)
        _set_state(sym, day, attempted=True)
        try:
            # Journal lane tag (2026-09-05): the Minervini funnel's ONE buy
            # call names its lane + why, for the journal's by_strategy split.
            res = entries.enter(sym, limit_price=None, stop_pct=stop_req,
                                allow_earnings=False, top_up=is_add,
                                strategy="minervini",
                                reason={"path": path, "pivot": pivot,
                                        "score": row.get("score"),
                                        "rs_rank": row.get("rs_rank"),
                                        "relvol": relvol})
            entries_today += 1
            if not is_add:
                pos_count += 1
            result = "entered"
            out["entered"].append(sym)
            detail = dict(trigger)
            detail.update({"score": row.get("score"),
                           "stop_pct_requested": stop_req, "order": res})
            kind = "auto_pyramid" if is_add else "auto_entry"
            ledger(kind, symbol=sym, detail=detail, dry_run=False,
                   cite=(PYRAMID_CITE if is_add else FUNNEL_CITE))
            _set_state(sym, day, entered=True,
                       path=path)
            _notify(kind, sym,
                    "%s %s (%s): %d sh, pivot %.2f, live %.2f"
                    % ("Pyramid add" if is_add else "Auto-entry", sym, path,
                       (res or {}).get("shares") or 0, pivot, live))
        except ValueError as exc:
            # Otherwise-triggered but vetoed by the entry path — ledger the
            # first veto of the day per symbol (dry_run-style), not every tick.
            result = "blocked"
            out["blocked"].append(sym)
            if not st.get("blocked_ledgered"):
                ledger("auto_entry_blocked", symbol=sym,
                       detail=dict(trigger, reason=str(exc)), dry_run=True,
                       cite=FUNNEL_CITE)
                _set_state(sym, day,
                           blocked_ledgered=True)
        except Exception as exc:                   # noqa: BLE001
            # Unexpected (non-veto) failure — attempted=True already set, so
            # this fires AT MOST once per symbol per ET day (no retry loop)
            # and must be VISIBLE: a broker order may or may not exist, so
            # surface it in the ledger, never just in the tick summary.
            result = "error"
            out["errors"].append("%s: %s" % (sym, exc))
            ledger("auto_entry_error", symbol=sym,
                   detail=dict(trigger, error=str(exc),
                               hint="unexpected failure after trigger — "
                                    "verify at Alpaca whether an order exists"),
                   dry_run=False, cite=FUNNEL_CITE)

        _set_state(sym, day,
                   last_eval={"ts": _utc_iso(), "score": row.get("score"),
                              "pivot": pivot, "checks": checks,
                              "result": result})

    out["entries_today"] = entries_today
    return out


# ── Status block (rides in GET /trading/status) ─────────────────────────────

def rules_list(cfg: Optional[dict] = None) -> list:
    """Every rule the engine enforces, as data — the FE ⓘ panel renders THIS
    list, so the page can never drift from what the code actually does
    (Ajay 2026-07-12: 'create a list of rules as info on the page'). Values
    are read live from config/constants; `source` is the book page or the
    owner-rule honesty note."""
    cfg = cfg or get_config()
    return [
        {"rule": "Only scanner-buyable setups: all 8 Trend Template checks, "
                 "Stage 2, a VCP/Power-Play base with a pivot, and a same-day "
                 "volume-confirmed breakout",
         "value": "is_buyable",
         "source": "TLSW pp.79-83, 198-203"},
        {"rule": "RS rank floor — the book demands at least 70 and prefers "
                 "'the 80s or 90s'; the engine only takes the preferred band",
         "value": "RS >= %g" % _min_rs(cfg),
         "source": "TLSW p.79 criterion 8 (floor is owner-tightened; "
                   "cfg auto_min_rs)"},
        {"rule": "SEPA score floor — winners scored 87-94, no loser above 84 "
                 "in the July 2026 autopsy",
         "value": "score >= %g" % _min_score(cfg),
         "source": "owner rule 2026-07-09 (cfg auto_min_score)"},
        {"rule": "Buy zone — never chase more than a few percent past the "
                 "pivot",
         "value": "<= %g%% above pivot" % MAX_EXTENSION_PCT,
         "source": "TLSW p.224 (3% is the owner-approved number)"},
        {"rule": "Same-day entries only when the pivot first cleared in the "
                 "first half of the session; later clears wait for next "
                 "morning's close-confirmation",
         "value": "clear <= %g of session" % FIRST_HALF_FRACTION,
         "source": "owner rule (hybrid trigger)"},
        {"rule": "Volume gate — projected full-day RelVol counts only after "
                 "the first hour (early projections lie); ACTUAL volume "
                 "already >= the floor triggers any time; missing volume "
                 "data never buys",
         "value": "RelVol >= %gx (projection trusted after %d min)"
                  % (AUTO_RELVOL_MIN, round(VOL_CONFIRM_MIN_FRAC * 390)),
         "source": "TLSW p.229 volume extrapolation"},
        {"rule": "Scan trust — the scan must be from today or the previous "
                 "trading day AND cover a market-sized universe, or the "
                 "engine sits out (RS ranks from small scans are distorted)",
         "value": ">= %d names, <= 1 trading day old" % MIN_RS_UNIVERSE,
         "source": "owner rule 2026-07-12"},
        {"rule": "Leaky pivots wait — a pivot poked above but closed back "
                 "below %d+ times in the last %d days (latest within %d) is "
                 "skipped for same-day entry until the leaks age out; a "
                 "full close above the pivot clears it"
                 % (PIVOT_LEAK_MAX, PIVOT_LEAK_LOOKBACK,
                    PIVOT_LEAK_COOLOFF_DAYS),
         "value": "right side must be quiet",
         "source": "Minervini on X, 2026: volatility 'often starts as "
                   "pivot leakage'"},
        {"rule": "Progressive exposure — every buy is pilot-sized (half) "
                 "until the last 5 closed trades are profitable on "
                 "balance; then full size. Composes with the losing-streak "
                 "governor (the stricter one wins)",
         "value": "pilot 0.5x -> 1.0x when proven",
         "source": "TLSW pp.307-308 pilot buys + Minervini on X: 'are "
                   "your last 4 or 5 stocks profitable on balance' "
                   "(cfg progressive_exposure)"},
        {"rule": "Pyramid adds — a held name that sets up AGAIN at a new "
                 "pivot above our cost gets topped up to full size through "
                 "the same trigger gates; adds only complete the position, "
                 "never exceed the 25% ceiling, never average down",
         "value": "top-up to full at the next valid buy point",
         "source": "TTLAC §3 'Add and Reduce' + §5 scale-up; TLSW "
                   "pp.307-308 (cfg pyramiding)"},
        {"rule": "No entries within a week of earnings, never average down, "
                 "never more than %d positions, at most %d auto-buys a day "
                 "in live mode (paper cycles freely), risk-off Market Gauge "
                 "halts live entries" % (risk_rules.MAX_POSITIONS,
                                         MAX_AUTO_ENTRIES_PER_DAY),
         "value": "earnings shield %dd" % entries.EARNINGS_SHIELD_DAYS,
         "source": "house safety rails"},
        {"rule": "Every buy flows through the same sized-and-stopped path: "
                 "default stop %g%% below entry, structural stop honored "
                 "when tighter, size halves after %d straight losses"
                 % (risk_rules.DEFAULT_STOP_PCT, risk_rules.STREAK_HALVE_AFTER),
         "value": "risk_rules FROZEN",
         "source": "TLSW pp.291-315, p.304"},
    ]


def status_block(cfg: Optional[dict] = None) -> dict:
    cfg = cfg or get_config()
    day = _et_day()
    trusted, scan_detail = scan_trusted(_scan_meta())
    return {"enabled": bool(cfg.get("auto_entry")),
            "equity_cap": cfg.get("equity_cap"),
            "entries_today": _entries_today(day),
            "max_per_day": MAX_AUTO_ENTRIES_PER_DAY,
            "min_score": _min_score(cfg),
            "min_rs": _min_rs(cfg),
            "pyramiding": _pyramiding_enabled(cfg),
            "scan": dict(scan_detail, trusted=trusted),
            "rules": rules_list(cfg),
            "candidates": _today_snapshots(day)}
