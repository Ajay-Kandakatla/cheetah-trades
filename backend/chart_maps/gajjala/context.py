"""The context reads around the five detectors (spec §3.1.5) — float, rotation, halts, psych levels, the 🎾 squeeze
history, the ☀️ K9 premarket list and the 🌙 K10 post-market confirm.

Nothing here decides a setup. The float feeds ONE gate (🎾, DECISIONS K8, applied by the detector); every other read is
a chip beside the tile. Every number is a constant imported by name (constants.py, or the house constants the float
pacing reuses); every edge is written as the multiplication the tests build (`x >= base * (1 + pct / 100)`).

Float chain (spec C7, HIS CALL 28), cheapest first:
  1. the 7-day `shares_cache` row (yfinance floatShares, else sharesOutstanding — labelled "shares out");
  2. Massive `share_class_shares_outstanding` for a name Yahoo has not answered — called ONCE per (session, symbol),
     the answer kept in `gajjala_daily` so later passes never re-call; shares out ≥ float, so a shares-out ≤ 10M can
     never admit a float > 10M (the conservative side);
  3. a paced Yahoo refinement of at most FLOAT_MAX_NEW_PER_PASS names, 🎾-alive names first. A Yahoo 429 stops the step
     and backs it off ≥ one pass, doubling to the house BACKOFF_MAX_SEC (sepa.moat_backfill's rule); any answer resets it.
The cache side of a 429 (no 7-day null tombstone any more) lives in `sepa.volume_movers.shares_status`.

Runs inside the cron pass and nightly.py only — never on a page load. UNMEASURED: none of these reads is a forecast.
"""
from __future__ import annotations

import logging
import math
import time
from datetime import date, datetime, time as dtime, timezone
from typing import Callable, Iterable, Optional
from zoneinfo import ZoneInfo

from sepa.moat_backfill import BACKOFF_MAX_SEC, DEFAULT_INTERVAL_SEC
from short_interest.read import FLOAT_EXCEEDS_SHARES, _float_suspect, _human_shares

from . import constants as GC

log = logging.getLogger("chart_maps.gajjala.context")

ET = ZoneInfo("America/New_York")

# float pacing — the house Yahoo constants, reused by name (spec §3.2 footnote; keeps constants.py free of sepa.*)
FLOAT_FETCH_INTERVAL_SEC = DEFAULT_INTERVAL_SEC          # moat_backfill: 1 s between Yahoo calls
FLOAT_BACKOFF_START_SEC = GC.PASS_CADENCE_SEC            # a 429 skips Yahoo for at least one pass
FLOAT_BACKOFF_MAX_SEC = BACKOFF_MAX_SEC                  # moat_backfill: doubling stops at 900 s
FLOAT_STATE_ID = "float_backoff"                         # gajjala_state doc {until (epoch s), n}
HALT_BACKFILL_STATE_ID = "halt_backfill"                 # gajjala_state doc {done: [ISO dates read from the dated list]}

# shares_status statuses whose values are usable without a fetch ("stale_served" = a 429 marker stands and the
# expired row is all there is — floats move rarely, and Yahoo cannot be asked anyway)
_USABLE = ("cached", "stale_served", "fetched")
_REFINABLE = ("missing", "stale")                        # no fresh row and no marker → worth a Yahoo call

PSY_WHY = "his profit-taking / climax level, not an entry"   # GG S9 1:09:11 / 1:21:19 (STRATEGY_SPEC §3.4 wording)
RED_CLOSES_QUOTE = "more than 3 red closes is red flag to me"   # GG X 1733882105204011109, verbatim


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _num(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pos(x) -> Optional[float]:
    v = _num(x)
    return v if v is not None and v > 0 else None


def _utc(now) -> datetime:
    if now is None:
        return datetime.now(timezone.utc)
    return now if now.tzinfo is not None else now.replace(tzinfo=timezone.utc)


def _iso(d) -> str:
    return d.isoformat() if isinstance(d, (date, datetime)) else str(d)


def _as_date(d) -> date:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.fromisoformat(str(d))


def _at_least(x: float, base: float, pct: float) -> bool:
    """x is at least `pct`% above `base` — the multiplication, edge-exact (the scanner's own form)."""
    return x >= base * (1 + pct / 100)


def _hhmm_et(at) -> Optional[str]:
    if not isinstance(at, datetime):
        return None
    return _utc(at).astimezone(ET).strftime("%H:%M")


def _shares2(n) -> str:
    """Two decimals for the float-vs-shares-out sentence (1,314,047 vs 1,299,391 must not both read "1.3M")."""
    f = _num(n)
    if f is None:
        return "—"
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(f) >= div:
            return "%.2f%s" % (f / div, suf)
    return "%d" % int(round(f))


# ── float chain (spec §3.1.5, C7) ─────────────────────────────────────────────────────────────────────────────────
def _yf_read(vals: Optional[dict], status: str, now: datetime) -> Optional[dict]:
    """FloatRead from a yfinance `shares_cache` row, or None when the row has neither number.

    A float on file LARGER than shares outstanding (FCHL 2026-10-13: 1,314,047 > 1,299,391, trap T10) is flagged with
    the house check (`short_interest.read._float_suspect` — no short-interest number exists on this path, so only its
    float-exceeds-shares branch can fire). FLOAT_SUSPECT_POLICY: "ineligible" keeps the float and the flag (the 🎾
    gate then reads it as unknown); "shares_out" serves shares outstanding instead."""
    if not vals:
        return None
    fl, so = _pos(vals.get("float_shares")), _pos(vals.get("shares_outstanding"))
    if fl is None and so is None:
        return None
    suspect = _float_suspect(0, fl, so) if (fl and so) else None
    base = {"as_of": _row_as_of(vals, now), "status": status, "refined": status == "fetched",
            "suspect": suspect, "suspect_text": None}
    if suspect == FLOAT_EXCEEDS_SHARES:
        base["suspect_text"] = (f"float on file {_shares2(fl)} exceeds shares out {_shares2(so)} — "
                                + ("using shares out" if GC.FLOAT_SUSPECT_POLICY == "shares_out"
                                   else "treated as unknown"))
        if GC.FLOAT_SUSPECT_POLICY == "shares_out":
            return _staled(dict(base, shares=int(so), src="shares_out_yf",
                                text=f"shares out {_human_shares(so)} (float on file exceeds it)"))
    if fl is not None:
        return _staled(dict(base, shares=int(fl), src="float", text=f"Float {_human_shares(fl)}"))
    return _staled(dict(base, shares=int(so), src="shares_out_yf", text=f"shares out {_human_shares(so)}"))


def _row_as_of(vals: dict, now: datetime) -> str:
    """The DATA's age — the `shares_cache` row's `as_of` (epoch s, served by volume_movers.shares_status), not the
    pass time (2026-10-13 review: a week-old "stale_served" row read as fresh). No stamp on the row → `now`."""
    ts = _num((vals or {}).get("as_of"))
    if ts is None or ts <= 0:
        return _utc(now).isoformat()
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _staled(r: dict) -> dict:
    """A "stale_served" read says so on the chip: the expired row Yahoo could not refresh (a 429 marker stands)."""
    if r.get("status") == "stale_served":
        r["text"] = f"{r['text']} (stale, as of {r['as_of'][:10]})"
    return r


def _massive_read(shares, now: datetime) -> dict:
    v = _pos(shares)
    if v is None:
        return unknown_float(now)
    return {"shares": int(v), "src": "shares_out_massive", "text": f"shares out {_human_shares(v)} (Massive)",
            "as_of": _utc(now).isoformat(), "status": "massive", "refined": False, "suspect": None,
            "suspect_text": None}


def unknown_float(now=None) -> dict:
    return {"shares": None, "src": None, "text": "float unknown", "as_of": _utc(now).isoformat(),
            "status": "unknown", "refined": False, "suspect": None, "suspect_text": None}


def _massive_once(sym: str, massive_lookup: Callable, store, session, now: datetime):
    """Massive shares out, at most ONCE per (session, symbol): the answer (even None) is kept in `gajjala_daily`
    `float_massive`. A raised lookup is remembered for the PASS only (`{failed_at}`, honoured for PASS_CADENCE_SEC —
    run.py calls floats_for twice a pass with the same `now`, and used to call a failing Massive twice); the next
    pass may try again."""
    if store is not None and session is not None:
        doc = store.get_daily(session, sym) or {}
        memo = doc.get("float_massive")
        if isinstance(memo, dict):
            failed_at = _num(memo.get("failed_at"))
            if failed_at is None:
                return memo.get("shares"), False
            if 0 <= _utc(now).timestamp() - failed_at < GC.PASS_CADENCE_SEC:
                return None, False
    try:
        shares = massive_lookup(sym)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("gajjala float: Massive shares-out failed for %s: %s", sym, type(exc).__name__)
        if store is not None and session is not None:
            store.upsert_daily(session, sym, {"float_massive": {"failed_at": _utc(now).timestamp()}}, now=now)
        return None, True
    if store is not None and session is not None:
        store.upsert_daily(session, sym, {"float_massive": {"shares": _pos(shares), "at": _utc(now).isoformat()}},
                           now=now)
    return shares, True


def refine_order(candidates: Iterable[str], reads: dict, priority: Optional[dict]) -> list:
    """Yahoo refinement order (spec §3.1.5 step 3): (a) names whose 🎾 structure is alive this pass with the float
    unknown or a Massive shares-out above K8_MAX_FLOAT (a yfinance float could admit them), then (b) the rest; each
    group by change_pct DESC, ties by symbol."""
    pr = priority or {}

    def info(s):
        p = pr.get(s) or {}
        return bool(p.get("structure_alive")), (_num(p.get("change_pct")) or 0.0)

    def group(s):
        alive, _ = info(s)
        r = reads.get(s) or {}
        could_admit = r.get("shares") is None or (r.get("src") == "shares_out_massive"
                                                 and r["shares"] > GC.K8_MAX_FLOAT)
        return 0 if (alive and could_admit) else 1

    return sorted(dict.fromkeys(candidates), key=lambda s: (group(s), -info(s)[1], s))


def floats_for(symbols: Iterable[str], *, priority: Optional[dict] = None, state: Optional[dict] = None,
               now: Optional[datetime] = None, status_lookup: Optional[Callable] = None,
               massive_lookup: Optional[Callable] = None, sleep: Callable = time.sleep, store=None, session=None,
               max_new: int = GC.FLOAT_MAX_NEW_PER_PASS, refine: bool = True) -> dict:
    """{SYM: FloatRead} for every symbol. FloatRead = {shares, src ("float" | "shares_out_yf" | "shares_out_massive" |
    None), text ("Float 3.1M" | "shares out 8.1M" | "shares out 8.1M (Massive)" | "float unknown"), as_of, status,
    refined (a Yahoo answer this call — the pass re-runs ONLY the 🎾 detector for those), suspect, suspect_text}.

    `priority` = {SYM: {"structure_alive": bool, "change_pct": float}} (the 🎾 read's meta + the scanner row);
    `state` = the `gajjala_state` "float_backoff" doc {until (epoch s), n}, mutated in place — loaded from / saved to
    `store` when one is given (`state["yahoo"]` = this call's Yahoo step {attempted, fetched, rate_limited,
    skipped_backoff}, not persisted). `max_new` caps the Yahoo calls (the pass: FLOAT_MAX_NEW_PER_PASS; nightly: every name,
    still paced and still stopped by the first 429). `refine=False` = steps 1–2 only (no Yahoo call at all)."""
    status_lookup = status_lookup or _default_status_lookup
    massive_lookup = massive_lookup or _default_massive_lookup
    now = _utc(now)
    now_ts = now.timestamp()
    if state is None:
        state = dict(store.get_state(FLOAT_STATE_ID)) if store is not None else {}
        state.pop("_id", None)
    syms = list(dict.fromkeys((s or "").upper().strip() for s in symbols or [] if s))
    reads: dict = {}
    yf_status: dict = {}
    # 1. the cache, every name, no fetch
    for s in syms:
        try:
            vals, st = status_lookup(s, fetch=False)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala float: cache read failed for %s: %s", s, exc)
            vals, st = None, "error"
        yf_status[s] = st
        r = _yf_read(vals, st, now) if st in _USABLE else None
        if r:
            reads[s] = r
    # 2. Massive shares out for every name Yahoo has not answered — runs during a Yahoo back-off too
    for s in syms:
        if s not in reads:
            shares, _called = _massive_once(s, massive_lookup, store, session, now)
            reads[s] = _massive_read(shares, now)
    # 3. paced Yahoo refinement
    yahoo = {"attempted": 0, "fetched": 0, "rate_limited": False, "skipped_backoff": False}
    if refine and max_new > 0:
        until = _num(state.get("until")) or 0.0
        if now_ts < until:
            yahoo["skipped_backoff"] = True
        else:
            todo = refine_order([s for s in syms if yf_status.get(s) in _REFINABLE], reads, priority)
            for s in todo:
                if yahoo["attempted"] >= max_new:
                    break
                if yahoo["attempted"]:
                    sleep(FLOAT_FETCH_INTERVAL_SEC)
                yahoo["attempted"] += 1
                try:
                    vals, st = status_lookup(s, fetch=True)
                except Exception as exc:                        # noqa: BLE001
                    log.warning("gajjala float: Yahoo read failed for %s: %s", s, exc)
                    continue
                if st == "rate_limited":
                    n = int(_num(state.get("n")) or 0) + 1
                    state["n"] = n
                    state["until"] = now_ts + min(FLOAT_BACKOFF_START_SEC * 2 ** (n - 1), FLOAT_BACKOFF_MAX_SEC)
                    yahoo["rate_limited"] = True
                    break
                if st == "fetched":
                    state["n"] = 0
                    yahoo["fetched"] += 1
                    r = _yf_read(vals, st, now)
                    if r:
                        reads[s] = r
                        if store is not None and session is not None:
                            store.upsert_daily(session, s, {"float": {k: r[k] for k in ("shares", "src", "as_of")}},
                                               now=now)
            if store is not None:
                store.set_state(FLOAT_STATE_ID, {"until": _num(state.get("until")) or 0.0,
                                                 "n": int(_num(state.get("n")) or 0)})
    state["yahoo"] = yahoo                                      # this call's Yahoo step, for the pass's counts
    return reads


def _default_status_lookup(sym, *, fetch=True):
    from sepa.volume_movers import shares_status
    return shares_status(sym, fetch=fetch)


def _default_massive_lookup(sym):
    from short_interest.client import _shares_outstanding
    return _shares_outstanding(sym)


def rotation(volume, float_read: Optional[dict]) -> Optional[dict]:
    """Float rotation = the scanner's shares today ÷ the float read (GG S8 1:15:24 "the float is rotating"). The label
    follows the source ("float" vs "shares out"). None when the float is unknown, 0, or treated as unknown."""
    fr = float_read or {}
    if fr.get("suspect") and GC.FLOAT_SUSPECT_POLICY == "ineligible":
        return None
    shares, vol = _pos(fr.get("shares")), _num(volume)
    if shares is None or vol is None or vol < 0:
        return None
    x = vol / shares
    label = "float" if fr.get("src") == "float" else "shares out"
    return {"x": round(x, 1), "text": f"🔄 {label} ×{x:.1f}"}


# ── halts (catalysts/halts.py; ⏸ chip + the 🎾 halt leg) ──────────────────────────────────────────────────────────
def _feed_keys(sym: str) -> list:
    s = (sym or "").upper()
    return list(dict.fromkeys((s, s.replace("-", "."), s.replace("-", ""))))


def _our_symbol(ticker: str) -> str:
    """The feed spells classes with a dot (BRK.B); the app's keys use the dash."""
    return (ticker or "").upper().strip().replace(".", "-")


def _clean_time(t) -> Optional[str]:
    """The feed pads HaltTime ("09:31:22                      .756") — keep HH:MM:SS."""
    if not t:
        return None
    s = "".join(str(t).split())
    return s[:8] if len(s) >= 8 else s


def last_resume_et(rec: Optional[dict]) -> Optional[str]:
    """The latest ResumptionDate + ResumptionTradeTime of a ticker's halts, as an ET ISO stamp; None when the feed has
    no resume time yet (still halted) or it does not parse (STRATEGY_SPEC D-HALT field — no push reads it while
    HALT_CALM_BARS is off)."""
    best = None
    for h in (rec or {}).get("halts") or []:
        d, t = (h.get("resume_date") or "").strip(), _clean_time(h.get("resume_time"))
        if not d or not t:
            continue
        try:
            dt = datetime.strptime(f"{d} {t}", "%m/%d/%Y %H:%M:%S").replace(tzinfo=ET)
        except ValueError:
            continue
        best = dt if best is None or dt > best else best
    return best.isoformat() if best else None


def _halt_rec(sym: str, halts: Optional[dict]) -> Optional[dict]:
    by = (halts or {}).get("by_ticker") or {}
    for k in _feed_keys(sym):
        if k in by:
            return by[k]
    return None


def halts_chip(sym: str, halts: Optional[dict]) -> Optional[dict]:
    """"⏸ halted ×N (LUDP, T1)" from `halts.get_today_halts()` (DECISIONS: a chip, never a criterion); None when the
    symbol has no halt today."""
    rec = _halt_rec(sym, halts)
    n = int(_num((rec or {}).get("n_halts")) or 0)
    if not rec or n <= 0:
        return None
    reasons = [r for r in rec.get("reasons") or [] if r]
    times = sorted(t for t in (_clean_time(h.get("halt_time")) for h in rec.get("halts") or []) if t)
    return {"n": n, "reasons": reasons, "text": f"⏸ halted ×{n}" + (f" ({', '.join(reasons)})" if reasons else ""),
            "first_halt_time": times[0] if times else None, "last_resume_et": last_resume_et(rec)}


def record_halts(store, session, payload: Optional[dict], *, source: str) -> int:
    """Upsert one `gajjala_halts` row per halted ticker of `session` ({n_halts, reasons, first_halt_time,
    last_resume_et, source "live" | "history"}). Returns the rows written. An empty / failed payload writes nothing."""
    if store is None or not payload:
        return 0
    n = 0
    for ticker, rec in (payload.get("by_ticker") or {}).items():
        chip = halts_chip(ticker, {"by_ticker": {ticker: rec}})
        if not chip:
            continue
        store.upsert_halt(session, _our_symbol(ticker), {
            "n_halts": chip["n"], "reasons": chip["reasons"], "first_halt_time": chip["first_halt_time"],
            "last_resume_et": chip["last_resume_et"], "source": source})
        n += 1
    return n


def record_live_halts(store, session, halts: Optional[dict]) -> int:
    """The pass's step: today's halted tickers into the ledger — only when the feed's ET date IS the pass's session."""
    if not halts or halts.get("session_date") != _iso(session):
        return 0
    return record_halts(store, session, halts, source="live")


def halt_ledger_dates(store) -> set:
    """Sessions the halt ledger covers: any row on file, or read in full from the dated list by nightly.py."""
    if store is None:
        return set()
    done = (store.get_state(HALT_BACKFILL_STATE_ID) or {}).get("done") or []
    return set(store.halt_sessions()) | {d for d in done if d}


# ── psychological levels / red closes (chips only) ──────────────────────────────────────────────────────────────
def psych_chips(price) -> list:
    """🧱 chips for $1 / $5 / $10 (GG S9 1:09:11, 1:21:19, 1:39:13 — his sell / climax levels) within PSY_NEAR_PCT
    ABOVE the price (the band is a Cheetah default, Ajay's number). A level at or under the price is no chip."""
    p = _pos(price)
    if p is None:
        return []
    out = []
    for lvl in GC.PSY_LEVELS:
        if lvl > p and lvl <= p * (1 + GC.PSY_NEAR_PCT / 100):
            pct = (lvl - p) / p * 100
            out.append({"level": lvl, "pct": round(pct, 1), "text": f"🧱 ${lvl:g} · {pct:.1f}% above",
                        "why": PSY_WHY})
    return out


def red_closes_chip(n) -> Optional[dict]:
    """"4 red closes in a row — he waits" when a read's pullback / base shows MORE than RED_CLOSES_WAIT consecutive red
    closes (the detector's `red_closes` count). A chip only (Ajay round C); None under RED_CLOSES_MODE "off"."""
    k = int(_num(n) or 0)
    if GC.RED_CLOSES_MODE == "off" or k <= GC.RED_CLOSES_WAIT:
        return None
    return {"n": k, "text": f"{k} red closes in a row — he waits (“{RED_CLOSES_QUOTE}”)"}


# ── 🎾 squeeze history (DECISIONS K8 chip, never a criterion) ─────────────────────────────────────────────────────
def history_window(session, sessions: int = GC.K8_HISTORY_SESSIONS) -> list:
    """The `sessions` market days BEFORE `session`, oldest first (the house calendar the scanner uses)."""
    from catalysts.medical.reaction import prev_market_day
    d = _as_date(session)
    out = []
    for _ in range(int(sessions)):
        d = prev_market_day(d)
        out.append(d)
    return sorted(out)


def _daily_ranges(daily_df, session: date) -> dict:
    """{ISO date: (high, low)} for rows dated BEFORE `session` — today's (partial) bar never counts."""
    out: dict = {}
    if daily_df is None or getattr(daily_df, "empty", True):
        return out
    for ts, row in daily_df.iterrows():
        try:
            d = ts.date() if hasattr(ts, "date") else _as_date(ts)
        except Exception:                                       # noqa: BLE001
            continue
        if d >= session:
            continue
        hi, lo = _num(row.get("high")), _pos(row.get("low"))
        if hi is not None and lo is not None:
            out[d.isoformat()] = (hi, lo)
    return out


def squeeze_history(daily_df, halt_dates, *, session=None, sessions: int = GC.K8_HISTORY_SESSIONS,
                    ledger_dates: Optional[set] = None) -> dict:
    """"🎾 squeeze history: N of last 30 sessions (≥50% range or a halt)". A session counts when its daily
    (high − low)/low ≥ K8_HISTORY_RANGE_PCT (written high ≥ low × 1.5) OR the halt ledger has a halt that date.
    `session` = the day the chip is shown (rows dated on/after it never count); `ledger_dates` = sessions the halt
    ledger covers — while it misses part of the window the text says where the halt list starts."""
    session = _as_date(session) if session is not None else datetime.now(ET).date()
    window = history_window(session, sessions)
    ranges = _daily_ranges(daily_df, session)
    halts = {_iso(d) for d in halt_dates or []}
    range_days, halt_days, hits = [], [], []
    for d in window:
        iso = d.isoformat()
        hl = ranges.get(iso)
        r_hit = hl is not None and _at_least(hl[0], hl[1], GC.K8_HISTORY_RANGE_PCT)
        h_hit = iso in halts
        if r_hit:
            range_days.append(iso)
        if h_hit:
            halt_days.append(iso)
        if r_hit or h_hit:
            hits.append(iso)
    text = (f"🎾 squeeze history: {len(hits)} of last {len(window)} sessions "
            f"(≥{GC.K8_HISTORY_RANGE_PCT:g}% range or a halt)")
    daily_ok = bool(ranges)
    if not daily_ok:
        text += " · no daily bars — halts only"
    complete, ledger_from = None, None
    if ledger_dates is not None:
        covered = sorted(d.isoformat() for d in window if d.isoformat() in ledger_dates)
        complete = len(covered) == len(window)
        ledger_from = covered[0] if covered else None
        if not complete:
            text += f" · halt list from {ledger_from}" if ledger_from else " · no halt list yet"
    return {"n": len(hits), "of": len(window), "sessions": hits, "range_days": range_days, "halt_days": halt_days,
            "daily_ok": daily_ok, "ledger_complete": complete, "ledger_from": ledger_from, "text": text}


def _default_daily_loader(sym, *, now=None):
    from sepa.prices import closed_daily_frame
    return closed_daily_frame(sym, now=now)


def warm_squeeze_history(symbols: Iterable[str], session, store, *, cap: Optional[int] = None,
                         loader: Optional[Callable] = None, force: bool = False) -> dict:
    """The chip for each symbol on `session`, from `gajjala_daily` when already computed, else computed (the daily
    frame via `prices.closed_daily_frame` — never a cache write, trap T5) and stored. `cap` bounds the NEW computes
    (the pass: DAILY_MAX_NEW_PER_PASS; nightly: None = all). -> {chips: {SYM: chip}, computed, cached, deferred}."""
    loader = loader or _default_daily_loader
    sess = _as_date(session)
    as_of = datetime.combine(sess, dtime(0, 0))               # naive = ET midnight: rows dated before the session
    ledger = halt_ledger_dates(store)
    out = {"chips": {}, "computed": 0, "cached": 0, "deferred": 0}
    for s in dict.fromkeys((x or "").upper() for x in symbols or [] if x):
        doc = (store.get_daily(sess, s) if store is not None else None) or {}
        if not force and isinstance(doc.get("squeeze_history"), dict):
            out["chips"][s] = doc["squeeze_history"]
            out["cached"] += 1
            continue
        if cap is not None and out["computed"] >= cap:
            out["deferred"] += 1
            continue
        try:
            df = loader(s, now=as_of)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala squeeze history: daily read failed for %s: %s", s, type(exc).__name__)
            df = None
        chip = squeeze_history(df, store.halt_dates(s) if store is not None else set(), session=sess,
                               ledger_dates=ledger if store is not None else None)
        out["chips"][s] = chip
        out["computed"] += 1
        if store is not None:
            store.upsert_daily(sess, s, {"squeeze_history": chip})
    return out


# ── ☀️ K9 premarket list ──────────────────────────────────────────────────────────────────────────────────────────
def pm_levels_for(raw_1min, session) -> Optional[dict]:
    """Today's premarket high / low / volume / last from the 1-minute frame (`daytrading.indicators.premarket_levels`
    + the last premarket close); None when the frame has no premarket bars dated `session`."""
    from daytrading.indicators import premarket_levels
    lv = premarket_levels(raw_1min)
    if not lv or lv.get("et_date") != _iso(session):
        return None
    try:
        pre = raw_1min[raw_1min["session"] == "premarket"]
        idx = pre.index.tz_localize("UTC") if pre.index.tz is None else pre.index
        et = idx.tz_convert(ET)
        today = pre[[d.isoformat() == _iso(session) for d in et.date]]
        lv["last"] = float(today["close"].iloc[-1]) if len(today) else None
    except Exception:                                           # noqa: BLE001
        lv["last"] = None
    return lv


def premarket_list(scan_today: Iterable[dict], carry_prev: Optional[dict], *, pm_levels: Optional[dict] = None,
                   sort: str = "volume") -> list:
    """☀️ rows (DECISIONS K9): today's qualifiers first seen in a premarket pass whose accumulated premarket volume is
    ≥ K9_PM_MIN_VOLUME, sorted by volume DESC (GG S8 1:21:56 "I sort by volume"; `sort="change"` = the served toggle),
    then the previous session's after-hours carry set (`store.ah_carry(prev_market_day(session))` — the set the LAST
    after-hours pass wrote), by its after-hours move DESC. A carried name that also qualifies today is listed once,
    with today's row marked `carried`.

    Premarket volume = the 1-minute premarket sum (`pm_levels[SYM]`, from `pm_levels_for`) when the frame is loaded,
    else the scanner's own number while its last print is still premarket; a name with neither is not listed."""
    today_rows: list = []
    seen: set = set()
    for doc in scan_today or []:
        sym = (doc.get("symbol") or "").upper()
        if not sym or sym in seen or not (doc.get("sessions") or {}).get("premarket"):
            continue
        last = doc.get("last") or {}
        lv = (pm_levels or {}).get(sym)
        if lv and _num(lv.get("volume")) is not None:
            pm_vol, pm_src = _num(lv["volume"]), "1min"
        elif last.get("tape_session") == "premarket" and _num(last.get("volume")) is not None:
            pm_vol, pm_src = _num(last["volume"]), last.get("vol_src") or "scanner"
        else:
            continue
        if pm_vol < GC.K9_PM_MIN_VOLUME:
            continue
        seen.add(sym)
        prev = _pos(last.get("prev_close"))
        price = _pos(last.get("price"))
        pm_last = _pos((lv or {}).get("last")) or (price if last.get("tape_session") == "premarket" else None)
        pm_high = _pos((lv or {}).get("high"))
        today_rows.append({
            "symbol": sym, "carry": False, "pm_volume": pm_vol, "pm_volume_src": pm_src,
            "pm_change_pct": round((pm_last / prev - 1) * 100, 2) if (pm_last and prev) else None,
            "pm_high": pm_high, "pm_low": _pos((lv or {}).get("low")),
            "price": price, "change_pct": _num(last.get("change_pct")),
            # STRATEGY_SPEC D-PM: a display stat only — his "huge sell-off" rule has no number, so no threshold
            "off_pm_high_pct": round((price / pm_high - 1) * 100, 2) if (price and pm_high) else None,
            "first_qualified_at": doc.get("first_qualified_at"),
        })
    if sort == "change":
        today_rows.sort(key=lambda r: (-(r["pm_change_pct"] if r["pm_change_pct"] is not None
                                         else (r["change_pct"] or 0.0)), r["symbol"]))
    else:
        today_rows.sort(key=lambda r: (-r["pm_volume"], r["symbol"]))
    carry_rows: list = []
    names = (carry_prev or {}).get("names") or {}
    decided = _hhmm_et((carry_prev or {}).get("pass_at"))
    by_sym = {r["symbol"]: r for r in today_rows}
    for sym, c in names.items():
        sym = (sym or "").upper()
        move = _num((c or {}).get("ah_move_pct"))
        info = {"ah_move_pct": move, "ah_last": _num((c or {}).get("ah_last")),
                "reg_close": _num((c or {}).get("reg_close")), "decided_at_et": decided,
                "text": (f"🌙 carried from yesterday's after-hours {move:+.1f}%" if move is not None
                         else "🌙 carried from yesterday's after-hours")
                        + (f" (last after-hours pass {decided})" if decided else "")}
        if sym in by_sym:
            by_sym[sym]["carried"] = info
            continue
        carry_rows.append(dict(info, symbol=sym, carry=True))
    carry_rows.sort(key=lambda r: (-(r["ah_move_pct"] or 0.0), r["symbol"]))
    return today_rows + carry_rows


# ── 🌙 K10 post-market confirm ────────────────────────────────────────────────────────────────────────────────────
_RTH_FIRST, _RTH_LAST = dtime(9, 30), dtime(15, 59)            # minute STARTS inside the regular session
_AH_FIRST, _AH_END = dtime(16, 1), dtime(20, 0)                # 16:00 = the closing-cross minute (T7) — EXCLUDED


def _post_minutes(minutes, session) -> Optional[dict]:
    """RTH high / low, the 15:59 minute's close and the after-hours volume of `session` from a 1-minute frame (naive
    UTC index = the bar START, daytrading.data). None when the frame has no RTH minute that day."""
    if minutes is None or getattr(minutes, "empty", True):
        return None
    idx = minutes.index.tz_localize("UTC") if minutes.index.tz is None else minutes.index
    et = idx.tz_convert(ET)
    sess = _as_date(session)
    hi = lo = c1559 = None
    ah_vol = 0.0
    for k, ts in enumerate(et):
        if ts.date() != sess:
            continue
        t = ts.time().replace(second=0, microsecond=0)
        row = minutes.iloc[k]
        if _RTH_FIRST <= t <= _RTH_LAST:
            h, low = _num(row.get("high")), _num(row.get("low"))
            if h is not None:
                hi = h if hi is None else max(hi, h)
            if low is not None:
                lo = low if lo is None else min(lo, low)
            if t == _RTH_LAST:
                c1559 = _num(row.get("close"))
        elif _AH_FIRST <= t < _AH_END:
            ah_vol += _num(row.get("volume")) or 0.0
    if hi is None or lo is None:
        return None
    return {"rth_high": hi, "rth_low": lo, "close_1559": c1559, "ah_volume": ah_vol}


def postmarket_confirm(candidates: Iterable[dict], checked: Optional[dict], minutes_loader: Callable,
                       snapshot_rows: Optional[dict] = None, *, cap: int = GC.AH_CONFIRM_MAX_PER_PASS,
                       session=None, now: Optional[datetime] = None, store=None) -> tuple:
    """-> (rows listed on 🌙, unchecked_n). DECISIONS K10: regular close in the top K10_CLOSE_TOP_FRAC of the day's
    range AND after-hours volume ≥ K10_AH_MIN_VOLUME AND after-hours gain ≥ K10_AH_MIN_GAIN_PCT vs the regular close.

    `candidates` = this pass's scanner prefilter rows (k10_candidates); `checked` = {SYM: gajjala_post doc} from earlier
    passes. Rotation (spec §3.1.5): never-checked names first (after-hours gain DESC), then the oldest `checked_at`; at
    most `cap` names get a 1-minute read per pass. Regular close = the snapshot's day.c, else the 15:59 minute (flagged);
    `close_pos` is fixed after 16:00 — computed once and kept; after-hours volume = minutes starting 16:01–19:59 (the
    16:00 closing-cross minute excluded, trap T7); the gain is always the CURRENT snapshot's. Every name checked this
    pass is written to `gajjala_post` when `store` is given (that is what the next pass's rotation reads). A name not
    reached — or whose minutes failed — counts in `unchecked_n` ("N after-hours gainers not checked yet — next pass")."""
    now = _utc(now)
    checked = {k.upper(): v for k, v in (checked or {}).items()}
    cur = {k.upper(): v for k, v in (snapshot_rows or {}).items()}
    cands: dict = {}
    for c in candidates or []:
        sym = (c.get("symbol") or "").upper()
        if sym and sym not in cands:
            cands[sym] = cur.get(sym) or c
    never = sorted((s for s in cands if s not in checked),
                   key=lambda s: (-(_num(cands[s].get("ah_move_pct")) or 0.0), s))
    old = sorted((s for s in cands if s in checked),
                 key=lambda s: (_utc(checked[s]["checked_at"]).timestamp()
                                if isinstance(checked[s].get("checked_at"), datetime) else 0.0, s))
    todo = (never + old)[:max(0, int(cap))]
    unchecked = [s for s in never if s not in todo]
    results: dict = {}
    failed: list = []
    for s in todo:
        row = cands[s]
        try:
            m = _post_minutes(minutes_loader(s), session)
        except Exception as exc:                                # noqa: BLE001
            log.warning("gajjala post-market: minutes failed for %s: %s", s, type(exc).__name__)
            m = None
        prior = checked.get(s) or {}
        if m is None:
            if s not in checked:
                failed.append(s)
            else:
                results[s] = dict(prior)
            continue
        if _num(prior.get("close_pos")) is not None:            # fixed after 16:00 — kept
            fixed = {k: prior.get(k) for k in ("close_pos", "reg_close", "reg_close_src", "rth_high", "rth_low")}
        else:
            reg, src = _pos(row.get("day_c")), "snapshot_day_c"
            if reg is None:
                reg, src = _pos(m["close_1559"]), "minute_1559"
            hi, lo = m["rth_high"], m["rth_low"]
            fixed = {"close_pos": round((reg - lo) / (hi - lo), 6) if (reg is not None and hi > lo) else None,
                     "reg_close": reg, "reg_close_src": src, "rth_high": hi, "rth_low": lo}
        doc = dict(fixed, checked_at=now, ah_volume=m["ah_volume"], passes=int(_num(prior.get("passes")) or 0) + 1)
        results[s] = doc
        if store is not None and session is not None:
            store.upsert_post(session, s, doc, now=now)
    for s in cands:
        if s not in results and s in checked:
            results[s] = dict(checked[s])
    rows = []
    for s, d in results.items():
        row = cands[s]
        reg, hi, lo = _pos(d.get("reg_close")), _num(d.get("rth_high")), _num(d.get("rth_low"))
        price, ah_vol = _pos(row.get("price")), _num(d.get("ah_volume"))
        if None in (reg, hi, lo, price, ah_vol) or not hi > lo:
            continue
        top_ok = (reg - lo) >= (1 - GC.K10_CLOSE_TOP_FRAC) * (hi - lo)
        vol_ok = ah_vol >= GC.K10_AH_MIN_VOLUME
        gain_ok = _at_least(price, reg, GC.K10_AH_MIN_GAIN_PCT)
        if not (top_ok and vol_ok and gain_ok):
            continue
        prev = _pos(row.get("prev_close"))
        at = d.get("checked_at")
        rows.append({
            "symbol": s, "price": price, "reg_close": reg, "reg_close_src": d.get("reg_close_src"),
            "rth_high": hi, "rth_low": lo, "close_pos": d.get("close_pos"), "ah_volume": ah_vol,
            "ah_gain_pct": round((price / reg - 1) * 100, 2),
            # STRATEGY_SPEC D-AH: the regular-session gain, shown only (AH_EXHAUSTION_MAX_PCT is off)
            "reg_gain_pct": round((reg / prev - 1) * 100, 2) if prev else None,
            "checked_at": at, "checked_text": f"checked {_hhmm_et(at)} ET" if _hhmm_et(at) else None,
        })
    rows.sort(key=lambda r: (-r["ah_gain_pct"], r["symbol"]))
    return rows, len(unchecked) + len(failed)


def unchecked_text(n: int) -> Optional[str]:
    return f"{n} after-hours gainers not checked yet — next pass" if n else None


__all__ = ["floats_for", "refine_order", "unknown_float", "rotation", "halts_chip", "last_resume_et",
           "record_halts", "record_live_halts", "halt_ledger_dates", "psych_chips", "red_closes_chip",
           "history_window", "squeeze_history", "warm_squeeze_history", "pm_levels_for", "premarket_list",
           "postmarket_confirm", "unchecked_text", "FLOAT_FETCH_INTERVAL_SEC", "FLOAT_BACKOFF_START_SEC",
           "FLOAT_BACKOFF_MAX_SEC"]
