"""📅 Long Term — the weekly read's SOURCES (spec §3.8, WP-DATA, 2026-11-12).

Ajay 2026-11-12: "Save this entire list for me. In a New tab - Long Term -
Remember this analays criteria I am asking you to for this tab and keep
updating it from all the other tabs info.."

Every source is read IN-PROCESS from the engine the source tab itself serves —
never an HTTP call to another endpoint, never a provider fetch:

  scan        `scanner.load_latest()`               (🚀 💎 📈, sectors)
  undervalue  `undervalue_peers._load_inputs()` + `build()` (🏷️)
  fallen      `fallen_tab.cached_or_warm()` + `board.fallen_pool()` (📉)
              + `fill_fallen_from_bars` (a saved name back above the line)
  hottest     `rotation.api` member table + `hottest._build(live=None)` (🔥)
  longterm    `longterm.stored()` (🌱) + `_sector_map()` (sector fallback)
  research    `research.decision_snapshot` + `research.sales_snapshot`
  frames      `prices.bulk_cached_frames` — ONE find, NEVER a fetch
  caps        `promo_circuit.market_caps_for(..., cap=0)` — cache only
  growth_board `growth.api._board_payload()` — the 💎 grade on 🚀 (display)

Each read is FENCED: a failure comes back `{"ok": False, "reason": ...}` and
the categories built on it read "not read" — never an empty pass, never a
zero. `pankaj_closes` is the ONE request-time read (the owner's GET of the
tab): cached closes for the 🧭 names, closed bars only.

Bar reads (stage, 52-week distance, 50-day $ volume) run on the frame trimmed
by the `scanner.as_of_close` rule — a bar dated today before the 16:30 ET
re-rate is the hourly in-progress patch and is dropped.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import datetime
from typing import Optional
from zoneinfo import ZoneInfo

from long_term_list import constants as C

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

SOURCE_KEYS = ("scan", "undervalue", "fallen", "hottest", "longterm", "research",
               "frames", "caps", "growth_board")
MIN_STAGE_BARS = 220                 # = stage / trend_template's own floor (len < 220 -> None)
LIQ_PERIOD = 50                      # = adr.liquidity_check's default period


# ---------------------------------------------------------------------------
# small pure helpers
# ---------------------------------------------------------------------------
def _f(v) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _sym(s) -> str:
    return str(s or "").strip().upper()


def _et_iso(epoch) -> Optional[str]:
    x = _f(epoch)
    if x is None:
        return None
    try:
        return datetime.fromtimestamp(x, tz=ET).isoformat(timespec="seconds")
    except (OverflowError, OSError, ValueError):
        return None


def _et_date(epoch) -> Optional[str]:
    iso = _et_iso(epoch)
    return iso[:10] if iso else None


def fail(reason: str) -> dict:
    """A source that could not be read. Never an empty pass."""
    return {"ok": False, "reason": str(reason), "as_of": None, "n": 0}


def _ok(as_of, n: int, **data) -> dict:
    return {"ok": True, "reason": None, "as_of": as_of, "n": int(n), **data}


def _fenced(key: str, fn, *a, **kw) -> dict:
    try:
        out = fn(*a, **kw)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("long_term_list: source %s failed: %s", key, exc)
        return fail(f"{key} read failed: {type(exc).__name__}")
    if not isinstance(out, dict) or "ok" not in out:
        return fail(f"{key} read returned nothing")
    return out


# ---------------------------------------------------------------------------
# closed bars — the scanner.as_of_close rule
# ---------------------------------------------------------------------------
def closed_frame(df, now):
    """The frame cut to CLOSED bars: a last bar `scanner.as_of_close` will not
    vouch for (dated today before SEPA_RERATE_ET while the session is not
    closed, or dated after today) is dropped. None when nothing is left."""
    from sepa import scanner as SC
    if df is None or len(df) == 0:
        return None
    if SC.as_of_close(df, now) is not None:
        return df
    cut = df.iloc[:-1]
    if len(cut) == 0 or SC.as_of_close(cut, now) is None:
        return None
    return cut


def bar_read(df, now) -> dict:
    """{close, close_date, stage, stage_label, stage_bar_date, pct_below_high,
    pct_above_low, dollar_vol_50, n_bars} from one cached frame, closed bars
    only. Stage = `stage.classify(df, vol=volume.analyze(df))` (the scanner's
    call); 52-week distance = `trend_template.evaluate`; 50-day $ volume =
    `adr.liquidity_check`. Fewer bars than an engine needs -> that field None
    (never zero)."""
    from sepa import adr, stage, trend_template, volume
    out = {"close": None, "close_date": None, "stage": None, "stage_label": None,
           "stage_bar_date": None, "pct_below_high": None, "pct_above_low": None,
           "dollar_vol_50": None, "n_bars": 0}
    d = closed_frame(df, now)
    if d is None:
        return out
    out["n_bars"] = int(len(d))
    out["close"] = _f(d["close"].iloc[-1])
    out["close_date"] = str(d.index[-1])[:10]
    if len(d) >= MIN_STAGE_BARS:
        try:
            st = stage.classify(d, vol=volume.analyze(d)) or {}
            if st.get("stage") is not None:
                out["stage"] = int(st["stage"])
                out["stage_label"] = st.get("label")
                out["stage_bar_date"] = out["close_date"]
        except Exception as exc:                                # noqa: BLE001
            log.debug("long_term_list: stage failed: %s", exc)
        try:
            tt = trend_template.evaluate("", d)
            if tt is not None:
                out["pct_below_high"] = _f(tt.pct_below_high)
                out["pct_above_low"] = _f(tt.pct_above_low)
        except Exception as exc:                                # noqa: BLE001
            log.debug("long_term_list: trend_template failed: %s", exc)
    if len(d) >= LIQ_PERIOD:
        liq = adr.liquidity_check(d) or {}
        out["dollar_vol_50"] = _f(liq.get("avg_dollar_vol"))
    return out


# ---------------------------------------------------------------------------
# the sources
# ---------------------------------------------------------------------------
SCAN_KEEP = ("symbol", "name", "sector", "industry", "score", "rs_rank", "stage",
             "qualifier", "is_candidate", "last_close", "as_of_close", "liquidity",
             "fundamentals", "moat", "buy_verdict")


def _slim_scan_row(r: dict) -> dict:
    out = {k: r.get(k) for k in SCAN_KEEP if k in r}
    f = r.get("fundamentals") or {}
    out["fundamentals"] = {k: f.get(k) for k in ("sales", "checks", "q_eps_growth_pct",
                                                 "rev_growth_q_pct")}
    bv = r.get("buy_verdict") or {}
    out["buy_verdict"] = {"bonde": bv.get("bonde")}
    m = r.get("moat") or {}
    out["moat"] = {"score": m.get("score"), "components": m.get("components")}
    return out


def read_scan() -> dict:
    from sepa import scanner as SC
    doc = SC.load_latest()
    if not isinstance(doc, dict) or not doc.get("all_results"):
        return fail("no scan doc")
    rows = {}
    for r in doc.get("all_results") or []:
        if isinstance(r, dict) and _sym(r.get("symbol")):
            rows[_sym(r["symbol"])] = _slim_scan_row(r)
    cands = []
    for r in doc.get("candidates") or []:
        if isinstance(r, dict) and r.get("is_candidate") and _sym(r.get("symbol")):
            s = _sym(r["symbol"])
            cands.append(s)
            rows.setdefault(s, _slim_scan_row(r))
    return _ok(_et_iso(doc.get("generated_at")), len(rows), rows=rows, candidates=cands,
               generated_at=doc.get("generated_at"))


def read_undervalue(saved: set) -> dict:
    from chart_maps import board as B
    from chart_maps import undervalue_peers as UVP
    inputs = UVP._load_inputs()
    base = UVP.build(**inputs)
    err = UVP.build_failure(base.get("counts"))
    if err:
        return fail(err)
    passed = []
    for p in base.get("passed") or []:
        m = B.tile_metrics(p.get("scan_row") or {})
        passed.append({"symbol": p["symbol"], "sector": p.get("sector"),
                       "ratio": _f(p.get("ratio")), "discount_pct": _f(p.get("discount_pct")),
                       "ttm_revenue": _f(p.get("ttm_revenue")),
                       "q_yoy_pct": _f(p.get("q_yoy_pct")),
                       "ttm_growth_pct": _f(p.get("ttm_growth_pct")),
                       "floor_ok": bool(B.passes_liquidity(m.get("avg_turnover"), C.FLOOR_TIER))})
    snaps = inputs.get("snaps") or {}
    saved_snaps = {s: snaps[s] for s in saved if s in snaps}
    return _ok(_et_date(inputs.get("scan_generated_at")), len(passed), passed=passed,
               snaps=saved_snaps)


def read_fallen(now, saved: set) -> dict:
    from chart_maps import board as B
    from chart_maps import fallen_tab as FAL
    got = FAL.cached_or_warm("full", now=now, sync=True)
    if got.get("state") != "ready" or not isinstance(got.get("entry"), dict):
        return fail(f"📉 list not ready: {got.get('state')} {got.get('reason') or ''}".strip())
    entry = got["entry"]
    kept, _counts, _thin, _no_t = B.fallen_pool(entry, sort=C.FALLEN_SORT,
                                                depth=int(C.FALLEN_MIN_PCT_BELOW),
                                                min_tier=C.FLOOR_TIER)
    pool = [r["symbol"] for r, _m in kept[:C.FALLEN_PAGE]]
    # the same floor at ANY depth (one engine): a saved name above the 📉 line
    # still gets its own floor verdict, never a fail by absence.
    floored, *_ = B.fallen_pool(entry, sort=C.FALLEN_SORT, depth=0, min_tier=C.FLOOR_TIER)
    floor = {r["symbol"]: True for r, _m in floored}
    in_pool = set(pool)
    rows = {}
    for sym, r in (entry.get("rows") or {}).items():
        s = _sym(sym)
        if s not in in_pool and s not in saved:
            continue
        rows[s] = {"symbol": s, "name": r.get("name"), "pct_below": _f(r.get("pct_below")),
                   "pct_above_low": _f(r.get("pct_above_low")),
                   "close": _f(r.get("close")), "close_date": r.get("close_date"),
                   "sector": r.get("sector"), "sales": FAL.sales_block(r),
                   "in_served_pool": s in in_pool,
                   "floor_ok": (bool(floor.get(s)) if r.get("pct_below") is not None else None)}
    return _ok(entry.get("as_of"), len(pool), rows=rows, pool=pool,
               session=entry.get("session"))


def fill_fallen_from_bars(fallen_src: dict, saved, reads: dict, research_rows: dict) -> dict:
    """A saved name the 📉 list holds no row for gets its 📉 values from its own
    closed-bar read. `fallen_tab` stores only names whose status is "fallen"
    (THRESHOLD_PCT or more under the high), so a saved 📉 name that climbed back
    has no row — without this its legs all read "unknown" and the week says
    "not read" instead of the neutral `moved` line (refix 2026-11-12).

    pct_below / pct_above_low = `bar_read`'s `trend_template` distances; sales =
    the research cache's own sales block through `FAL.sales_block`;
    `in_served_pool` False (never a top-strip candidate); `floor_ok` None (the
    floor is read only on 📉 rows -> "unknown", never a fail by absence). A name
    whose bar read has no 52-week distance (short frame, no frame) is left out:
    it stays "not read", never a zero. PURE: returns a new source dict; a source
    that is not ok comes back unchanged."""
    from chart_maps import fallen_tab as FAL
    if not isinstance(fallen_src, dict) or fallen_src.get("ok") is not True:
        return fallen_src
    rows = dict(fallen_src.get("rows") or {})
    filled = []
    for s in sorted({_sym(x) for x in (saved or []) if _sym(x)}):
        if s in rows:
            continue
        b = (reads or {}).get(s) or {}
        below, above = _f(b.get("pct_below_high")), _f(b.get("pct_above_low"))
        if below is None and above is None:
            continue
        sales = ((research_rows or {}).get(s) or {}).get("sales")
        rows[s] = {"symbol": s, "name": None, "pct_below": below, "pct_above_low": above,
                   "close": _f(b.get("close")), "close_date": b.get("close_date"),
                   "sector": None, "sales": FAL.sales_block(sales if isinstance(sales, dict) else {}),
                   "in_served_pool": False, "floor_ok": None, "read_from": "frames"}
        filled.append(s)
    return {**fallen_src, "rows": rows, "filled_from_frames": filled}


def read_hottest() -> dict:
    from rotation import api as RA
    from rotation import hottest as H
    from rotation import tracker as T
    table, meta = RA._members_table()
    if table is None:
        return fail((meta or {}).get("reason") or "member table unavailable")
    payload = dict(RA._members_payload() or {})
    payload[T.MEMBERS_KEY] = table
    syms = list((table.get("by_symbol") or {}).keys())
    if not syms:
        return fail("member table empty")
    out = H._build(payload, sort=C.HOT_SORT, direction=H.DEFAULT_DIR,
                   names_per_group=len(syms), decisions=H._decision_map(syms),
                   earnings=H._earnings_map(syms), live=None, pre=H._idle_pre())
    rows = {}
    for sec in out.get("sectors") or []:
        group = sec.get("group")
        for i, n in enumerate(sec.get("names") or []):
            s = _sym(n.get("symbol"))
            if not s or s in rows:
                continue
            rows[s] = {"symbol": s, "group": group, "sales_tier": n.get("sales_tier"),
                       "q_eps_yoy": _f(n.get("q_eps_yoy")), "ret_21d": _f(n.get("ret_21d")),
                       "rank_in_group": i + 1, "served": i < C.HOT_PAGE}
    if not rows:
        return fail("Hottest built no sector rows")
    return _ok(out.get("as_of") or (meta or {}).get("built_at_iso"),
               sum(1 for r in rows.values() if r["served"]), rows=rows)


def read_longterm() -> dict:
    from sepa import longterm as LT
    doc = LT.stored()
    if not isinstance(doc, dict) or not doc.get("rows"):
        return fail("no long-term doc")
    try:
        sector_map = LT._sector_map()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("long_term_list: companies sector map failed: %s", exc)
        sector_map = {}
    rows = {_sym(k): v for k, v in (doc.get("rows") or {}).items() if isinstance(v, dict)}
    return _ok(doc.get("built_at_iso"), len(rows), rows=rows, sector_map=sector_map)


def read_research(saved: set, universe: list) -> dict:
    from sepa import research
    if research._get_cache() is None:
        return fail("research cache unreachable")
    dec = research.decision_snapshot(sorted(saved)) if saved else {}
    snap = research.sales_snapshot(sorted(set(universe) | set(saved))) if (universe or saved) else {}
    rows: dict = {}
    for s, v in snap.items():
        rows[_sym(s)] = {"sales": (v or {}).get("sales"), "cached_at": (v or {}).get("cached_at")}
    for s, v in dec.items():
        rows[_sym(s)] = dict(v or {})
    if not rows:
        return fail("research cache returned no names")
    return _ok(None, len(rows), rows=rows)


def read_frames(symbols, now) -> dict:
    from sepa import prices
    syms = sorted({_sym(s) for s in symbols if _sym(s)})
    frames = prices.bulk_cached_frames(syms)
    if not frames:
        return fail("price cache returned no frames")
    reads = {s: bar_read(df, now) for s, df in frames.items()}
    closed = {s: closed_frame(df, now) for s, df in frames.items()}
    bench = reads.get(C.BENCHMARK) or {}
    dates = [r["close_date"] for r in reads.values() if r.get("close_date")]
    as_of = bench.get("close_date") or (max(dates) if dates else None)
    return _ok(as_of, len(frames), reads=reads,
               frames={s: d for s, d in closed.items() if d is not None})


def read_caps(symbols, closes: dict) -> dict:
    from catalysts.promo_circuit import market_caps_for
    syms = sorted({_sym(s) for s in symbols if _sym(s)})
    if not syms:
        return fail("no names to price")
    caps = market_caps_for(syms, closes, cap=0)
    if not caps:
        return fail("shares cache returned no caps")
    return _ok(None, sum(1 for v in caps.values() if v), caps=caps)


def read_growth_board() -> dict:
    from growth import api as GA
    rows = (GA._board_payload() or {}).get("rows") or []
    grades = {}
    for r in rows:
        s = _sym(r.get("symbol"))
        g = (r.get("capital_quality") or {}).get("grade")
        if s and g:
            grades[s] = g
    if not rows:
        return fail("growth board has no rows")
    return _ok(None, len(grades), grades=grades)


# ---------------------------------------------------------------------------
# pre-candidates (cheap pre-filters on constants by name; criteria decides)
# ---------------------------------------------------------------------------
def quiet_pre(longterm_src: dict) -> list:
    """🌱 names worth a bar read: long-term rows ranked at or over
    QUIET_MIN_SCORE (every other 🌱 leg is decided by `criteria`)."""
    out = []
    for s, r in ((longterm_src or {}).get("rows") or {}).items():
        sc = r.get("score") or {}
        v = _f(sc.get("score"))
        if sc.get("ranked") and v is not None and v >= C.QUIET_MIN_SCORE:
            out.append(s)
    return sorted(out)


def accel_pre(research_src: dict) -> list:
    """🔄 names worth a bar read and a cap: sales tier in ACCEL_SALES_TIERS,
    accelerating, prior y/y over ACCEL_MIN_PRIOR_YOY_PCT."""
    out = []
    for s, r in ((research_src or {}).get("rows") or {}).items():
        sa = (r or {}).get("sales") or {}
        prior = _f(sa.get("prior_yoy_pct"))
        if (sa.get("tier") in C.ACCEL_SALES_TIERS and sa.get("accelerating") is True
                and prior is not None and prior > C.ACCEL_MIN_PRIOR_YOY_PCT):
            out.append(s)
    return sorted(out)


def load_all(now, *, saved, seed=None) -> dict:
    """Every source of one weekly read, each fenced. `saved` = the 109 seed
    symbols. Returns {"session", "now", <key>: {ok, reason, as_of, n, ...}}."""
    from sepa.universe import load_universe
    now = (now or datetime.now(ET))
    now = (now if now.tzinfo else now.replace(tzinfo=ET)).astimezone(ET)
    saved = {_sym(s) for s in (saved or []) if _sym(s)}
    t0 = time.time()
    out: dict = {"now": now.isoformat(timespec="seconds")}
    out["scan"] = _fenced("scan", read_scan)
    out["undervalue"] = _fenced("undervalue", read_undervalue, saved)
    out["fallen"] = _fenced("fallen", read_fallen, now, saved)
    out["hottest"] = _fenced("hottest", read_hottest)
    out["longterm"] = _fenced("longterm", read_longterm)
    try:
        universe = list(load_universe(C.ACCEL_UNIVERSE) or [])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("long_term_list: universe read failed: %s", exc)
        universe = []
    out["research"] = _fenced("research", read_research, saved, universe)
    pre = set(quiet_pre(out["longterm"])) | set(accel_pre(out["research"]))
    out["frames"] = _fenced("frames", read_frames,
                            saved | pre | {C.BENCHMARK, C.BENCHMARK_ALT}, now)
    out["fallen"] = fill_fallen_from_bars(out["fallen"], saved, out["frames"].get("reads") or {},
                                          out["research"].get("rows") or {})
    closes = {s: r["close"] for s, r in (out["frames"].get("reads") or {}).items()
              if r.get("close") is not None}
    out["caps"] = _fenced("caps", read_caps, set(accel_pre(out["research"])) | saved, closes)
    out["growth_board"] = _fenced("growth_board", read_growth_board)
    out["session"] = out["frames"].get("as_of")
    out["duration_s"] = round(time.time() - t0, 2)
    return out


# ---------------------------------------------------------------------------
# the ONE request-time read (owner GET only)
# ---------------------------------------------------------------------------
def pankaj_closes(symbols, now=None) -> dict:
    """{SYM: {"close", "date"}} of the latest CLOSED cached bar for the 🧭
    names — `prices.bulk_cached_frames` (one find, never a fetch), a bar dated
    today before the 16:30 ET re-rate dropped. A symbol the cache does not hold
    is simply absent (never a zero). Never `load_prices`. Never raises."""
    from sepa import prices
    now = (now or datetime.now(ET))
    now = (now if now.tzinfo else now.replace(tzinfo=ET)).astimezone(ET)
    try:
        frames = prices.bulk_cached_frames([_sym(s) for s in symbols or [] if _sym(s)])
    except Exception as exc:                                    # noqa: BLE001
        log.warning("long_term_list: pankaj_closes read failed: %s", exc)
        return {}
    out = {}
    for s, df in (frames or {}).items():
        d = closed_frame(df, now)
        if d is None:
            continue
        px = _f(d["close"].iloc[-1])
        if px is None:
            continue
        out[_sym(s)] = {"close": px, "date": str(d.index[-1])[:10]}
    return out
