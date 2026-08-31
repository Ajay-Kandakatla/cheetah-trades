"""Session board — ORB / FVG / SMC / market mood for every name already on the
demand boards.

Ajay 2026-08-31: *"Can you create a tab for ORB/ FVG/ Bullish sentiment or
bearish for all the onces in demand zone. and deep demand zones. You have this
logic for on demand of a ticket in Support levels tab .. I will use this tab
after market open to figure out market sentiment."*

WHAT THIS IS. The Back in Demand and Deep Demand boards answer *which names*,
on DAILY structure. That question is settled before the bell. This board asks
the next one: **now that the session is running, is the tape confirming or
rejecting the daily level that put the name on the list?** Same analytics that
already exist per-ticker on the Support tab (`chart_maps.support`), run across
the union of the two boards instead of one symbol at a time.

WHY THIS DOES NOT REOPEN THE 2026-08-29 DECISION. Ajay's earlier correction —
*"I do not need these on scans but on demand in the support levels"* — is
locked by `test_the_scan_boards_do_not_take_a_timeframe`, and that lock still
holds: `chart_maps.board` still takes no `tf`, and the daily boards are
untouched. This is a SEPARATE surface with its own explicitly intraday
contract, not a timeframe knob bolted onto a daily board. The cost objection
recorded in the docs ("intraday bars for ~1,700 symbols per refresh") also does
not apply: the input here is the ~99 names the two boards already selected.

COST. One 1-minute fetch per symbol per refresh, reused for every read below —
which is why `patterns.opening_range_from_bars` exists. Completed days are
Mongo-cached by `daytrading.data`; only TODAY is re-fetched, so a warm refresh
during the session is ~1s a name, not the ~12s a cold pass costs. Measured
2026-08-31: 99 symbols, cold ≈ 12s each, warm ≈ 1s each.

NEVER BLOCKS. Same rule as `demand_reentry.cached_or_warm` and for the same
reason — Cloudflare cuts the connection at ~100s (the 524 of 2026-08-14). The
request path serves what it has and warms in a thread.

SOURCE STATUS. Mood, FVG and SMC are CONVENTION, not book methods; ORB is
Crabel (1990) / Raschke (1995). The composite `session_score` below is this
app's own ranking and is labelled `cited: false` everywhere it appears. See
docs/supply_demand/session_board.md.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Optional

log = logging.getLogger("supply_demand.session_board")

# ── knobs ──────────────────────────────────────────────────────────────────
CACHE_TTL_SEC = 180          # intraday: stale fast, but not once per keystroke
WORKERS = 8                  # 10 drew Massive read timeouts on 2026-08-31
MAX_SYMBOLS = 140            # backstop; the union runs ~99 today
ANALYSIS_TFS = ("15m", "60m")
DEFAULT_TF = "15m"

# `session_score` weights — CONVENTION, this app's ranking, not a book method.
# Deliberately a SUM OF NAMED PARTS rather than a fitted blend: every point on
# a row can be traced to the fact that produced it, which is the only way a
# ranking like this stays arguable instead of magic.
W_MOOD = 1.0                 # mood score is already -100..+100
W_SMC_SETUP = 25.0           # a COMPLETE sweep->BOS->OB->FVG sequence
W_ORB_ABOVE = 10.0           # holding above the session's first agreed value
W_ORB_BELOW = -10.0
W_FVG_SESSION = 5.0          # an unfilled gap left by THIS session's impulse
W_AT_BAND = 15.0             # price actually AT the daily band that listed it
CITED = False


# ── which names ────────────────────────────────────────────────────────────
def board_symbols(universe: str = "full", limit: int = MAX_SYMBOLS) -> list[dict]:
    """Union of the Back in Demand + Deep Demand boards. PURE-ish read.

    Reads the ONE `demand_reentry` cache both tabs already read, so this costs
    no extra scan and can never disagree with what the tabs show. Rows carry
    the DAILY band that put them on the list — that band is the level the
    intraday read is asked to confirm, so it has to travel with the symbol.

    Returns [] (not an exception) when the demand scan is still warming: the
    caller reports "warming", exactly like the two boards do.
    """
    from chart_maps import board as B

    out: dict[str, dict] = {}
    for tab, tag in (("zones", "demand"), ("deep_demand", "deep")):
        try:
            data = B.board(tab=tab, limit=B.LIMIT_MAX, universe=universe)
        except Exception as exc:
            log.warning("session_board: %s tiles failed: %s", tab, exc)
            continue
        if data.get("warming"):
            return []
        for tile in (data.get("tiles") or []):
            sym = (tile.get("symbol") or "").upper()
            if not sym:
                continue
            rec = out.setdefault(sym, {
                "symbol": sym, "name": tile.get("name") or sym,
                "sources": [], "theme": tile.get("theme"), "band": None,
            })
            if tag not in rec["sources"]:
                rec["sources"].append(tag)
            if rec["band"] is None:
                rec["band"] = _band_from_tile(tile)
    rows = sorted(out.values(), key=lambda r: r["symbol"])
    return rows[:max(1, int(limit))]


def _band_from_tile(tile: dict) -> Optional[dict]:
    """The demand band a board tile drew, as a plain {lo, hi}.

    Tiles carry their bands for the sparkline; reusing them means this board
    and the tab it came from are quoting the same numbers by construction
    rather than by two computations agreeing.
    """
    for b in (tile.get("bands") or []):
        kind = (b.get("kind") or "").lower()
        if "demand" in kind or kind in ("entry", "zone", "buy"):
            lo, hi = b.get("lo"), b.get("hi")
            if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and hi > lo:
                return {"kind": "demand", "lo": float(lo), "hi": float(hi),
                        "mid": round((float(lo) + float(hi)) / 2.0, 4)}
    return None


# ── one symbol ─────────────────────────────────────────────────────────────
def read_symbol(sym: str, band: Optional[dict] = None, *,
                tf: str = DEFAULT_TF, orb_minutes: int = 15) -> dict:
    """The full session read for one name. Always answers a dict.

    Never raises: a board that drops a row on one bad symbol is a board that
    silently lies about coverage. Failures land in `unavailable` with a reason
    and the row still renders.
    """
    from supply_demand import mood as mood_mod
    from supply_demand import patterns as pat
    from supply_demand import smc as smc_mod
    from supply_demand import timeframes as TF

    out = {
        "symbol": sym, "tf": tf, "unavailable": [], "cited": CITED,
        "last_price": None, "band": band, "at_band": False,
        "mood": None, "orb": None, "orb_state": None,
        "fair_value_gaps": [], "session_gaps": [], "smc": None,
        "signal": None, "bias": "unknown", "session_score": None,
        "session": None, "as_of": None, "bars": 0,
    }

    # ONE fetch, used for both the structural frame and the opening range.
    raw = TF.intraday_raw(sym, tf)
    df, meta = TF.frame_for(sym, tf, raw=raw)
    out["tf_label"] = meta.get("label")
    out["as_of"] = meta.get("as_of")
    out["bars"] = meta.get("bars") or 0
    if df is None or not meta.get("available"):
        out["unavailable"].append(meta.get("reason") or "no intraday bars")
        return out

    try:
        last = float(df["close"].iloc[-1])
    except Exception:
        out["unavailable"].append("unreadable frame")
        return out
    out["last_price"] = round(last, 4)

    # ORB comes off the RAW minute bars for the latest session — the same ones
    # the frame was built from, never a second fetch.
    if raw is not None and not raw.empty:
        orb = pat.opening_range_from_bars(raw, orb_minutes)
        out["orb"] = orb
        out["orb_state"] = pat.orb_state(orb, last)
        if orb:
            out["session"] = orb.get("session")
    else:
        out["unavailable"].append("no minute bars for the opening range")

    m = mood_mod.mood(df, closed_only=True)
    out["mood"] = m
    if m.get("label") == "unavailable":
        out["unavailable"].extend(m.get("unavailable") or ["mood unavailable"])

    gaps = pat.fair_value_gaps(df, last)
    out["fair_value_gaps"] = gaps[:6]
    out["session_gaps"] = [g for g in gaps if _is_session_gap(g, out["session"])][:4]

    setups = smc_mod.find_setups(df, last_price=last, direction="bullish")
    # `find_setups` stamps the graded quality under "score", NOT "grade".
    # Reading the wrong key returned 0 for every setup on 2026-08-31 — a chip
    # reading "SMC setup - 0" says the sequence graded worst-possible when it
    # had actually graded 60+. None when a setup carries no score at all;
    # zero is a real grade and must not stand in for a missing one.
    grades = [s.get("score") for s in setups
              if isinstance(s.get("score"), (int, float))]
    out["smc"] = {
        "setups": setups[:2],
        "count": len(setups),
        "best_grade": max(grades) if grades else None,
        "cited": getattr(smc_mod, "CITED", False),
    }

    # The BUY/SELL read is anchored to the DAILY band that listed the name.
    # Mood without a level is a weather report: no level, no stop, no size.
    bands = [band] if band else []
    out["signal"] = mood_mod.signal(df, bands, m, last_price=last)
    if band:
        out["at_band"] = bool(band["lo"] <= last <= band["hi"])

    out["bias"] = _bias(out)
    out["session_score"] = _session_score(out)
    return out


def _is_session_gap(gap: dict, session: Optional[str]) -> bool:
    """Was this imbalance left by the session being shown?

    Ajay asked specifically for *"FVG in the first few mins of the session"*.
    Without a session stamp this returns False rather than guessing — an
    unattributed gap must not be presented as today's.
    """
    if not session:
        return False
    at = gap.get("at")
    return bool(at and str(at).startswith(str(session)))


def _bias(row: dict) -> str:
    """bullish | bearish | neutral | unknown — the headline Ajay asked for.

    This is the MOOD label, not a new blend. Mood is already a bounded
    six-component read; inventing a second sentiment number on top of it would
    make two numbers disagree on the same card with no way to say which is
    right. ORB state and SMC ride alongside as CONFIRMATIONS, reported
    separately so a reader can see the parts disagree when they do.
    """
    m = row.get("mood") or {}
    label = m.get("label")
    if not label or label == "unavailable":
        return "unknown"
    score = m.get("score")
    if not isinstance(score, (int, float)):
        return "unknown"
    if score >= mood_buy():
        return "bullish"
    if score <= mood_sell():
        return "bearish"
    return "neutral"


def mood_buy() -> float:
    from supply_demand.mood import MOOD_BUY
    return float(MOOD_BUY)


def mood_sell() -> float:
    from supply_demand.mood import MOOD_SELL
    return float(MOOD_SELL)


def _session_score(row: dict) -> Optional[float]:
    """Ranking only — CONVENTION, never a probability and never advice.

    A sum of named parts (see the W_* constants). Returns None when mood is
    unavailable: a row we could not read must sort as unknown, not as zero,
    because zero is a real neutral reading that some rows legitimately have.
    """
    m = row.get("mood") or {}
    base = m.get("score")
    if not isinstance(base, (int, float)):
        return None
    total = W_MOOD * float(base)
    smc = row.get("smc") or {}
    if (smc.get("count") or 0) > 0:
        total += W_SMC_SETUP
    # Only a COMPLETE opening range moves the ranking. At 09:31 the window
    # holds one bar; scoring +/-10 on which side of a single minute price sits
    # would rank the board on noise for the first quarter hour — precisely the
    # window Ajay opens this tab in. The state is still REPORTED, so he can see
    # the forming range; it just does not vote yet.
    orb = row.get("orb") or {}
    st = row.get("orb_state")
    if orb.get("complete"):
        if st == "above":
            total += W_ORB_ABOVE
        elif st == "below":
            total += W_ORB_BELOW
    if row.get("session_gaps"):
        total += W_FVG_SESSION
    if row.get("at_band"):
        total += W_AT_BAND
    return round(total, 1)


# ── the board ──────────────────────────────────────────────────────────────
_cache: dict = {}
_warm_lock = threading.Lock()
_warming: set = set()
_progress: dict = {}


def _key(universe: str, tf: str) -> str:
    return f"{universe}:{tf}"


def scan(universe: str = "full", tf: str = DEFAULT_TF, *,
         limit: int = MAX_SYMBOLS, orb_minutes: int = 15) -> dict:
    """Run the session read across the union of the two demand boards."""
    from concurrent.futures import ThreadPoolExecutor

    tf = tf if tf in ANALYSIS_TFS else DEFAULT_TF
    k = _key(universe, tf)
    syms = board_symbols(universe, limit=limit)
    started = time.time()
    if not syms:
        _progress[k] = {"phase": "warming_source", "current": 0, "total": 0,
                        "running": False}
        return {"rows": [], "warming": True, "tf": tf,
                "note": "the demand scan is still warming — this board reads it",
                "as_of": None, "count": 0}

    total = len(syms)
    _progress[k] = {"phase": "reading", "current": 0, "total": total,
                    "running": True, "started_at": started}
    rows: list = []
    done = 0

    def _one(rec):
        return read_symbol(rec["symbol"], rec.get("band"), tf=tf,
                           orb_minutes=orb_minutes)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        for rec, read in zip(syms, ex.map(_one, syms)):
            done += 1
            _progress[k].update({"current": done,
                                 "elapsed_sec": round(time.time() - started, 1)})
            if read is None:
                continue
            read.update({"name": rec.get("name"), "sources": rec.get("sources"),
                         "theme": rec.get("theme")})
            rows.append(read)

    # Unknown-mood rows sort LAST but are kept and counted. Dropping them would
    # make a thin-data day look like a calm one.
    rows.sort(key=lambda r: (r.get("session_score") is None,
                             -(r.get("session_score") or 0)))
    unreadable = sum(1 for r in rows if r.get("session_score") is None)
    sessions = {r.get("session") for r in rows if r.get("session")}
    out = {
        "rows": rows,
        "count": len(rows),
        "unreadable": unreadable,
        "tf": tf,
        "tf_options": [{"key": t, "label": ("15 min" if t == "15m" else "1 hour")}
                       for t in ANALYSIS_TFS],
        "session": sorted(sessions)[-1] if sessions else None,
        "live": _is_rth_now(),
        "orb_minutes": orb_minutes,
        "as_of": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "elapsed_sec": round(time.time() - started, 1),
        "warming": False,
        "weights": {"mood": W_MOOD, "smc_setup": W_SMC_SETUP,
                    "orb_above": W_ORB_ABOVE, "orb_below": W_ORB_BELOW,
                    "session_fvg": W_FVG_SESSION, "at_band": W_AT_BAND},
        "cited": CITED,
        "disclaimer": ("Session read on intraday bars. Mood, fair-value gaps and "
                       "the SMC sequence are convention, not book methods; the "
                       "ranking is this app's own. Decision-support only — not "
                       "investment advice."),
    }
    _cache[k] = {"ts": time.time(), "data": out}
    _progress[k] = {"phase": "idle", "current": total, "total": total,
                    "running": False,
                    "elapsed_sec": round(time.time() - started, 1)}
    return out


def _is_rth_now() -> bool:
    """Is the US cash session open right now? Used only to LABEL the board.

    A weekend or pre-open read is legitimate — it shows the last session and
    says which — so this never gates the scan, it only tells the page whether
    "session" means today or the one that just closed.
    """
    try:
        from zoneinfo import ZoneInfo
        now = datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        return False
    if now.weekday() >= 5:
        return False
    mins = now.hour * 60 + now.minute
    return (9 * 60 + 30) <= mins <= (16 * 60)


def cached_or_warm(universe: str = "full", tf: str = DEFAULT_TF, *,
                   limit: int = MAX_SYMBOLS, orb_minutes: int = 15) -> dict:
    """Serve the cache, or start a background pass and say so — never block."""
    tf = tf if tf in ANALYSIS_TFS else DEFAULT_TF
    k = _key(universe, tf)
    c = _cache.get(k)
    if c and (time.time() - c["ts"]) < CACHE_TTL_SEC:
        return {**c["data"], "cached": True, "warming": False,
                "age_sec": round(time.time() - c["ts"], 1)}

    with _warm_lock:
        already = k in _warming
        if not already:
            _warming.add(k)

    if not already:
        def _work():
            try:
                scan(universe, tf, limit=limit, orb_minutes=orb_minutes)
            except Exception as exc:
                log.warning("session_board: warm failed for %s: %s", k, exc)
                _progress[k] = {"phase": "error", "running": False,
                                "error": str(exc)}
            finally:
                with _warm_lock:
                    _warming.discard(k)
        threading.Thread(target=_work, daemon=True).start()

    stale = c["data"] if c else None
    if stale:
        return {**stale, "cached": True, "warming": True,
                "age_sec": round(time.time() - c["ts"], 1)}
    return {"rows": [], "count": 0, "tf": tf, "warming": True,
            "session": None, "live": _is_rth_now(), "as_of": None,
            "note": "reading the session — this takes a minute on a cold cache",
            "disclaimer": "Decision-support only — not investment advice."}


def progress_for(universe: str = "full", tf: str = DEFAULT_TF) -> dict:
    """What the running pass is doing. Always answers, `phase: idle` when not."""
    k = _key(universe, tf)
    p = dict(_progress.get(k) or {"phase": "idle", "current": 0, "total": 0,
                                  "running": False})
    tot, cur = p.get("total") or 0, p.get("current") or 0
    p["pct"] = round(100.0 * cur / tot, 1) if tot else 0.0
    p["universe_key"] = universe
    p["tf"] = tf
    return p
