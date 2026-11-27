"""🏁 🩳 SI track record — a nightly ledger of what the 🩳 High SI sub's names did (2026-11-26, SPEC sitrack rev 2 §3.7,
WP be-track).

Ajay 2026-11-26, verbatim: "I want us to track these patters for future from SI like a track recprd with in SI stocks
itself".

Descriptive and UNMEASURED: no push, no gate, no sort outside its own table. Every engine is the house one:
  cohort      scanner.listed_symbols + the tab's own listed filter + high_si.evaluate on point-in-time short interest
              (pit_block: the served settlement only when FINRA had published it BEFORE the session, else the prior
              settlement rebuilt through read.si_block, else no row — `no_si`). A listed / short-interest read that
              raises → the session is NOT recorded (retried the next night). Never "every read" as a fallback.
  listing     listed_before = on the list before the session (scanner `since` < session) — the ex-ante flag, NOT the
              house `carried` word (high_si: did not qualify today); qualified_today; listed_at (the scan doc's
              first_qualified_at, ET HH:MM).
  prior close ONE order for EVERY row (prior_close_of): the prior session's last REGULAR 5-minute bar (`s` absent and
              its START before that day's regular close, alerts._closes) from the read doc's own tail (tile.bars5_prior),
              else the prior session's stored read doc (the day after a half day), else the scan doc's last.prev_close.
              The scan doc's own figure is stored beside it (scan_prev_close) and never chosen while bars exist.
  split       ledger._default_split_lookup, memoized per run on (sym, lo, hi): a split in (prior day, session] → no
              outcome numbers; an unreadable check → "split_unread", retried inside LOOKBACK_SESSIONS.
  winner      gajjala_watch.runners.ran_of fed a stand-in scan doc carrying only the ledger's prior close — the SAME
              engine (+WC.RAN_MIN_PCT on the 09:30–20:00 high; premarket never counts). winner_strict = its `counts`;
              winner_scan = the same call on the REAL scan doc (stored, never counted).
  bars        the stored read doc when its pass stamp is at or after the session's extended close (alerts._closes[1]),
              else the 1-minute loader → bars.build_frames / tile_payload → a stand-in read doc → the SAME ran_of.
  ⛔          ssr.payload(…, kick=False) at two clocks built from the SESSION date: SSR_OPEN_AT (on at the open) and
              NIGHT_AT (triggered that day). "on" True · "off" False · anything else None — never False from no record.
  🔒 📄 ✂️    reg_sho.payload(kick=False) and the served share basis, on the session's own night only (a late or
              backfilled day → None): dilution_before / split_before are the pattern values; the 20:15 flags are
              stored, never read as a pattern.
  stats       only rows with listed_before True and a True / False winner; intervals on names AND on days through
              scripts.gajjala_study (cluster_ci / cluster_delta_ci / verdict, imported lazily) plus a within-day
              shuffle (MINE, no cut). Names first listed that day are counted apart (counts only).

Storage: gajjala_state only (store.get_state / set_state) — `si_track|YYYY-MM-DD`, `si_track_index`, `si_track_stats`.
Reads that decide what to write are FAULT-AWARE (state_read: None = a read fault, never "nothing on file"); the index
grows by `$addToSet` only; a session doc saying source "nightly" is never re-recorded (2026-11-26 refix).
Mongo reads + those writes only; the 1-minute loader and the split check are the only outside calls, under MAX_LOADS.
Not advice.
"""
from __future__ import annotations

import logging
import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import high_si as HS
from chart_maps.gajjala_watch import constants as WC
from chart_maps.gajjala_watch import runners as RN
from chart_maps.replays import constants as RC
from daytrading.data import ET_AFTERHOURS_CLOSE, ET_PREMARKET_OPEN, ET_RTH_OPEN
from short_interest import read as SR

log = logging.getLogger("chart_maps.gajjala.si_track")
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

# ── constants (none typed twice) ──────────────────────────────────────────────────────────────────────────────────
STATE_FMT = "si_track|{date}"                    # TRANSPORT — one gajjala_state doc per session
INDEX_ID = "si_track_index"                      # TRANSPORT — {"dates": [iso…] ascending}
STATS_ID = "si_track_stats"                      # TRANSPORT — the stats block
VERSION = 1                                      # TRANSPORT
WIN_PCT = WC.RAN_MIN_PCT                         # his 11-22 answer "+40% vs prior close"
FIRST_HOUR_END = RC.WIN_TIMING_BUCKETS[0][2]     # his 11-22 first hour (09:30–10:30)
NOON_ET = time(12, 0)                            # MINE — the 11-26 study's "noon"
SSR_OPEN_AT = ET_PREMARKET_OPEN                  # the ⛔ "on at the open" as-of clock
NIGHT_AT = GC.LEDGER_GRADE_AT_ET                 # the ⛔ "triggered that day" as-of clock (= the nightly's own clock)
LOOKBACK_SESSIONS = GC.LEDGER_GRADE_LOOKBACK_SESSIONS
MAX_LOADS = GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS
ROWS_MAX = GC.LEDGER_ROWS_MAX
SPAN_SESSIONS = GC.LEDGER_SPAN_SESSIONS_LONG
MIN_NAMES = 20                                   # a typed copy of scripts.gajjala_study.MIN_CLUSTERS (a test pins it)
BASIS_SRCS = ("tail", "prior_read", "scan")
SOURCES = ("nightly", "late", "backfill")
OUTCOME_STATES = ("ok", "no_bars", "no_prev_close", "split", "split_unread")
OUTCOME_RETRY = ("no_bars", "split_unread")
NEXT_STATES = ("pending", "ok", "no_bars", "split")
NEXT_RETRY = ("pending", "no_bars")
VWAP_STATES = ("reclaimed", "under", "never_under", "not_read")
WHERE = ("first_hour", "rth_rest", "ah")
DAY_WHERE = ("pre",) + WHERE
SSR_KEYS = ("ssr_open", "ssr_trig_day", "ssr_trig_on", "ssr_trig_at")
SHO_KEYS = ("regsho_on", "regsho_state", "regsho_day", "regsho_day13", "regsho_start_by", "regsho_past",
            "regsho_list_date")
SHO_PAST_STATES = ("passed", "passed_open")
FILING_KEYS = ("dilution_before", "split_before", "dilution", "split", "flag_shorts")
# 2026-11-26 (spec sishares §3.5, C9): a served filing of these kinds never sets the pattern `dilution_before` — the
# pattern keeps ONE definition for every stored row (rows are never rewritten). Typed once here, pinned equal to
# (basis_math.KIND_FOREIGN_ISSUANCE,) by a test. The 20:15 chip flags (`dilution`, `flag_shorts`) are untouched.
FILING_KINDS_NOT_IN_PATTERN = ("foreign_issuance",)

ROW_KEYS = (
    "date", "symbol",
    "listed_before", "qualified_today", "listed_at",
    "settlement_date", "published_on", "pit", "si_shares", "tier", "float_check", "pct_float", "pct_shares_out",
    "dtc", "dtc_provider", "adv",
    "float_shares", "float_asof", "float_source", "card_float", "card_float_src", "shares_out", "shares_asof",
    "shares_source",
) + SSR_KEYS + SHO_KEYS + FILING_KEYS + (
    "prev_close", "prev_close_src", "scan_prev_close", "open_930", "gap_pct", "gap_up", "pm_vol", "avg_vol_50",
    "pm_vol_ratio", "prev_winner",
    "high", "high_pct", "high_at", "high_where", "day_high_where", "timing", "pm_high_pct", "pm_peak",
    "morning_fade", "low_after_noon", "fade_ramp", "vwap_reclaim_at", "vwap_state", "cross_up_at", "cross_pre",
    "cross_by_first_hour",
    "winner", "winner_strict", "winner_scan", "outcome_state", "next",
    "bars_src", "late", "recorded_at",
)
OUTCOME_KEYS = ("open_930", "gap_pct", "gap_up", "pm_vol", "pm_vol_ratio", "high", "high_pct", "high_at", "high_where",
                "day_high_where", "timing", "pm_high_pct", "pm_peak", "morning_fade", "low_after_noon", "fade_ramp",
                "cross_up_at", "cross_pre", "cross_by_first_hour", "winner", "winner_strict", "winner_scan")

# (key, label, when known) — seven, each known before the open, in this order [C4: gap_up is a SHAPE]
PATTERNS = (
    ("ssr_open", "⛔ SSR on at the open", "the evening before"),
    ("tier_extreme", "🩳 %s (vs %s)" % (SR.TIER_WORDS[SR.TIER_EXTREME], SR.TIER_WORDS[SR.TIER_HIGH]),
     "before the open"),
    ("regsho_on", "🔒 on a Reg SHO list", "the evening before"),
    ("regsho_past", "🔒 past its close-out day", "the evening before"),
    ("dilution_before", "📄 dilution filing dated before the day", "before the open"),
    ("split_before", "✂️ split in force at the open", "at the open"),
    ("prev_winner", "📅 ran the session before", "the evening before"),
)
SHAPES = (
    ("gap_up", "Opened above the prior close"),
    ("ssr_trig_day", "⛔ SSR triggered that day"),
    ("morning_fade", "Under the 09:30 open by noon (MINE)"),
    ("fade_ramp", "Faded by noon, then the high after hours (MINE)"),
    ("vwap_reclaimed", "📈 closed back above VWAP and stayed there (MINE)"),
    ("cross_by_first_hour", "🔀 9 / 21 EMA cross up in the first hour"),
)
WORDS = {"too_few": "too few names or days", "not_shown": "NOT SHOWN",
         "clear": "interval clear of 0 on names and on days — 1 of %d looks, not corrected"}
VERDICT_WORD = {"no_interval": "too_few", "no_signal": "not_shown", "measured_edge": "clear", "inverted": "clear"}

# ── served words (every number filled from a constant at call time) ───────────────────────────────────────────────
TITLE = "🏁 🩳 SI track record · UNMEASURED"
SUMMARY_TEXT = "🏁 SI track record · {w} of {n} ran +{pct:g}%"
EMPTY_SUMMARY = "🏁 SI track record · nothing recorded yet"
EMPTY_TEXT = ("No session is recorded yet — the {at} ET nightly records each session the 🩳 sub listed, and the "
              "backfill reaches the sessions whose stored bars are still on file.")
FAULT_TEXT = HS.SIT_FAULT_TEXT                    # ONE copy — high_si serves it when this module cannot load
BASE_TEXT = ("On the list before the day: {w} of {n} ran +{pct:g}% ({rate}) · {names} names · {days} days{tail}")
BASE_CI_TAIL = " · interval on names {nlo}–{nhi} · on days {dlo}–{dhi}"
BASE_FEW_TAIL = " · too few names or days for an interval"
NEW_TODAY_TEXT = ("First listed that day, not counted above: {w} of {n} ran — {a} of {b} listed before {open} · "
                  "{c} of {d} after")
PATTERN_HEADS = [["label", "Pattern"], ["with", "With it"], ["without", "Without"], ["diff", "Difference"],
                 ["shuffle", "Shuffled"], ["word", "Read"]]
COUNT_TEXT = "{w} of {n} · {rate}"
SHUFFLE_TEXT = "{p}% of within-day shuffles as large"
UNKNOWN_TEXT = "{k} not known"
PATTERN_TITLE = "{label} — known {known}. {unknown}. UNMEASURED."
WHERE_TEXT = ("Where the {open}–{end} high printed — winners: first hour {a} · rest of regular hours {b} · after hours "
              "{c} — the rest: first hour {d} · rest of regular hours {e} · after hours {f}")
SHAPE_COUNT = "{k} of {n}"
SHOWN_TEXT = "Showing the first {lim} rows of {n} — every row is counted above."
PENDING_TEXT = "{k} next-session columns fill the night that session ends"
ASOF_TEXT = "recorded nightly at {at} ET · through {date}"
RULE_LABEL = "ⓘ how this is counted"
NEW_LABEL = "first listed that day — not counted"
# 2026-11-26 refix: a not-counted row that was NOT first listed that day (on the list before it but not graded — bars
# pending, a split, no prior close — or with no listing date on file) is drawn under its own served label, never under
# NEW_LABEL. Row `group` says which part of the day table a row sits in, in DAY_GROUPS order.
OTHER_LABEL = "not counted — not graded, or listing day not on file"
DAY_GROUPS = ("counted", "new", "other")
DASH = "—"
DAY_HEADS = [["ticker", "Ticker"], ["listed", "Listed"], ["si", "SI % float / % shares"], ["tier", "Tier"],
             ["dtc", "DTC"], ["float", "Float (date)"], ["ssr", "⛔"], ["sho", "🔒"], ["flags", "Flags"],
             ["gap", "Gap"], ["pm_vol", "PM vol ×"], ["high", "High %"], ["where", "Where"], ["cross", "9/21"],
             ["vwap", "VWAP"], ["next", "Next open→high / low"]]
WHERE_WORDS = {"pre": "premarket", "first_hour": "first hour", "rth_rest": "rest of regular hours",
               "ah": "after hours"}
VWAP_WORDS = {"reclaimed": "back above {t}", "under": "under", "never_under": "never under", "not_read": "not read"}
SHO_WORDS = {"on": "on", "past": "past close-out"}
BLOCK_KEYS = ("title", "summary_text", "base_text", "new_today_text", "pattern_heads", "patterns", "where_text",
              "shape_rows", "heads", "days", "shown_text", "pending_text", "asof_text", "rule_label", "rule_text",
              "honesty", "fault_text", "empty_text", "n", "n_days", "follow")
NIGHT_KEYS = ("session", "rows", "late", "next_filled", "loads", "split_calls", "deferred_cap", "stats", "faults",
              "follow")
# 2026-11-26 (spec sishares §3.5, C15): the day table's ONE forward column — +LEDGER_SPAN_SESSIONS sessions (si_follow's
# DAY_HORIZON, the same constant by name; a test pins them equal). +1 is the existing `next` column; +10 lives only in
# the follow fold. Its cell is si_follow.cells(row, fwd), a dash when the follow could not be read.
FOLLOW_HEAD = ["f%d" % GC.LEDGER_SPAN_SESSIONS, "+%d sessions" % GC.LEDGER_SPAN_SESSIONS]


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _pos(x) -> Optional[float]:
    v = _f(x)
    return v if v is not None and v > 0 else None


def _d(x) -> Optional[date]:
    if isinstance(x, datetime):
        return x.date()
    if isinstance(x, date):
        return x
    try:
        return date.fromisoformat(str(x)[:10])
    except (TypeError, ValueError):
        return None


def _iso(x) -> str:
    d = _d(x)
    return d.isoformat() if d is not None else str(x)


def _hhmm(t: time) -> str:
    return t.strftime("%H:%M")


def _clock(t) -> time:
    return t if isinstance(t, time) else time.fromisoformat(str(t))


def _utc(v) -> Optional[datetime]:
    """A stored stamp as aware UTC (Mongo hands back naive UTC; an ISO string is parsed); else None."""
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v.strip())
        except ValueError:
            return None
    if not isinstance(v, datetime):
        return None
    return v.replace(tzinfo=UTC) if v.tzinfo is None else v.astimezone(UTC)


def _at(day: date, t) -> datetime:
    """`day` at ET clock `t` as aware UTC."""
    return datetime.combine(day, _clock(t), tzinfo=ET).astimezone(UTC)


def _prev_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _next_day(d: date) -> date:
    from catalysts.medical.reaction import next_market_day
    return next_market_day(d)


def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return bool(is_market_day(d))


def _closes(day: date) -> tuple:
    """(regular close, extended close) — alerts._closes, the house half-day table."""
    from chart_maps.gajjala import alerts as AL
    return AL._closes(day)


def _reg_close(day: date) -> time:
    from chart_maps.gajjala import ledger as LG
    return LG._close_et(day)


def _pct(hi, base) -> Optional[float]:
    return RN._pct(hi, base) if _pos(hi) is not None and _pos(base) is not None else None


def _rate(w: int, n: int) -> Optional[float]:
    return (w / n) if n else None


def _pct_text(r: Optional[float]) -> str:
    return DASH if r is None else "%.1f%%" % (r * 100.0)


def _signed(x: float, unit: str = "") -> str:
    s = "%.1f" % x
    if s in ("-0.0", "0.0"):
        return "0.0" + unit
    return ("+" + s if x > 0 else "−" + s[1:]) + unit


def _num_text(x: float) -> str:
    s = "%.1f" % x
    return "−" + s[1:] if s.startswith("-") and s != "-0.0" else s.replace("-0.0", "0.0")


def blank_row(session, sym: str) -> dict:
    """Every ROW_KEYS key, None (a field that cannot be read is None — never 0, never False)."""
    r = dict.fromkeys(ROW_KEYS)
    r["date"], r["symbol"] = _iso(session), sym
    return r


# ── point in time ─────────────────────────────────────────────────────────────────────────────────────────────────
def pit_block(b, session) -> Optional[dict]:
    """The served block when FINRA published it BEFORE the session (strict); else the PRIOR settlement rebuilt through
    SR.si_block (today = the session, no basis) when that one was published before the session; else None."""
    if not isinstance(b, dict) or b.get("si_shares") is None:
        return None
    s_iso = _iso(session)
    pub = b.get("published_on")
    if isinstance(pub, str) and pub < s_iso:
        return dict(b, pit="latest")
    prev_s, prev_si = b.get("prev_settlement_date"), b.get("prev_si_shares")
    if not isinstance(prev_s, str) or prev_si is None:
        return None
    doc = {"symbol": b.get("symbol"), "v": 2, "short_interest": prev_si, "settlement_date": prev_s,
           "float_shares": b.get("float_shares"), "float_asof": b.get("float_asof"),
           "float_source": b.get("float_source"), "shares_outstanding": b.get("shares_outstanding"),
           "shares_asof": b.get("shares_asof"), "shares_source": b.get("shares_source")}
    pb = SR.si_block(doc, today=_d(session))
    if not isinstance(pb, dict) or not isinstance(pb.get("published_on"), str) or pb["published_on"] >= s_iso:
        return None
    return dict(pb, pit="prev")


def pit_blocks(symbols, session, *, read: Optional[Callable] = None) -> Optional[dict]:
    """{SYM: point-in-time block or None} — `read(symbols)` (default high_si.si_blocks(…, today=session)) mapped
    through pit_block; None when the read could not be made (no Mongo handle)."""
    if read is None:
        def read(syms):
            return HS.si_blocks(syms, today=_d(session))
    raw = read(list(symbols))
    if raw is None:
        return None
    return {str(k).upper(): pit_block(v, session) for k, v in raw.items()}


# ── the cohort ────────────────────────────────────────────────────────────────────────────────────────────────────
def _hhmm_et(v) -> Optional[str]:
    t = _utc(v)
    return t.astimezone(ET).strftime("%H:%M") if t is not None else None


def cohort(st, session, now, *, si_read: Optional[Callable] = None) -> dict:
    """{"rows": [{symbol, read_doc, block, listing, ev_read}], "listed", "scan_by", "excluded", "n_read"} — exactly the
    names the 🩳 sub lists (the tab's listed filter, high_si.evaluate on point-in-time short interest). RAISES when the
    listed read or the short-interest read faults (the session is then not recorded)."""
    from chart_maps.gajjala import scanner as SC
    s_iso = _iso(session)
    listed_raw = SC.listed_symbols(st, _d(session))
    listed = {str(k).upper(): v for k, v in (listed_raw or {}).items()}
    reads_by = {}
    n_read = 0
    for doc in st.reads(_d(session)) or []:
        sym = str((doc or {}).get("symbol") or "").upper()
        if not sym:
            continue
        n_read += 1
        if sym in listed:
            reads_by[sym] = doc
    blocks = pit_blocks(list(reads_by), session, read=si_read)
    if blocks is None:
        raise RuntimeError("short interest unread")
    ev = HS.evaluate(reads_by, scan_row=lambda s: None, session=_d(session), now=now,
                     si_read=lambda syms: blocks, listed=listed)
    if ev.get("faults"):
        log.warning("si track: %d name(s) faulted in the 🩳 read on %s", len(ev["faults"]), s_iso)
    scan_by = {str(d.get("symbol") or "").upper(): d for d in st.scan_docs([_d(session)]) if d.get("symbol")}
    rows = []
    for r in ev.get("rows") or []:
        sym = r["symbol"]
        lrow = listed.get(sym) or {}
        listing = {"listed_before": (lrow.get("since") < s_iso) if isinstance(lrow.get("since"), str) else None,
                   "qualified_today": (lrow.get("last_qualified") == s_iso)
                   if isinstance(lrow.get("last_qualified"), str) else None,
                   "listed_at": _hhmm_et((scan_by.get(sym) or {}).get("first_qualified_at"))}
        rows.append({"symbol": sym, "read_doc": r.get("read_doc"), "block": blocks.get(sym), "listing": listing,
                     "ev_read": r.get("read") or {}})
    rows.sort(key=lambda x: x["symbol"])
    return {"rows": rows, "listed": listed, "scan_by": scan_by, "excluded": dict(ev.get("counts") or {}),
            "n_read": n_read, "faults": list(ev.get("faults") or [])}


# ── prior close + the 📅 grade ─────────────────────────────────────────────────────────────────────────────────────
def _last_regular_close(doc, key: str, day: date) -> Optional[float]:
    tile = doc.get("tile") if isinstance(doc, dict) else None
    raw = tile.get(key) if isinstance(tile, dict) else None
    bars = RN.bars_of({"tile": {"bars5": raw}}, day.isoformat())
    cut = _hhmm(_reg_close(day))
    reg = [b for b in bars if b.get("s") is None and RN._bar_start(b) < cut]
    return _pos(reg[-1]["c"]) if reg else None


def prior_close_of(read_doc, prev_read_doc, scan_doc, session) -> tuple:
    """(value, src) — the prior session's last REGULAR 5-minute close, ONE order for every row: the read doc's tail
    (`tile.bars5_prior`) → the prior session's stored read doc (`tile.bars5`) → the scan doc's `last.prev_close`;
    none → (None, None). A regular bar = `s` absent AND its START before that day's regular close."""
    prior = _prev_day(_d(session))
    v = _last_regular_close(read_doc, "bars5_prior", prior)
    if v is not None:
        return v, BASIS_SRCS[0]
    v = _last_regular_close(prev_read_doc, "bars5", prior)
    if v is not None:
        return v, BASIS_SRCS[1]
    v = _pos(RN._last(scan_doc).get("prev_close"))
    if v is not None:
        return v, BASIS_SRCS[2]
    return None, None


def grade(read_doc, prior_close, session) -> Optional[dict]:
    """runners.ran_of on a stand-in scan doc carrying only the ledger's prior close — no rule of its own."""
    if _pos(prior_close) is None:
        return None
    return RN.ran_of({"last": {"prev_close": prior_close}}, read_doc, _d(session))


def _where(start: str, s, reg_cut: str) -> str:
    if s == WC.BAR_PRE:
        return DAY_WHERE[0]
    if s == WC.BAR_AH or start >= reg_cut:
        return WHERE[2]
    return WHERE[0] if start < FIRST_HOUR_END else WHERE[1]


def _cross_facts(bars5, curves5, reg_open: str) -> dict:
    out = {"cross_up_at": None, "cross_pre": None, "cross_by_first_hour": None}
    tones = {c.get("tone") for c in curves5 or [] if isinstance(c, dict)}
    from chart_maps.gajjala import bars as B
    if not all(t in tones for t, _l, _p in B.EMA_TONES):
        return out
    from chart_maps.gajjala import tab as GT
    blk = GT.ema_cross_block({"tf": "5m", "bars": bars5, "curves": curves5})
    by_t = {b.get("t"): b for b in bars5 or [] if isinstance(b, dict)}
    out.update(cross_pre=False, cross_by_first_hour=False)
    for x in (blk or {}).get("crosses") or []:
        if x.get("dir") != "up" or x.get("t") not in by_t:
            continue
        b = by_t[x["t"]]
        start = RN._bar_start(b)
        if b.get("s") == WC.BAR_PRE or start < reg_open:
            out["cross_pre"] = True
            continue
        if out["cross_up_at"] is None:
            out["cross_up_at"] = start
    out["cross_by_first_hour"] = out["cross_up_at"] is not None and out["cross_up_at"] < FIRST_HOUR_END
    return out


def session_facts(bars5, curves5, prev_close, day, *, reg_close, avg_vol_50=None) -> dict:
    """PURE — the open, the day and the outcome of one name-day from its 5-minute bars (right-labelled; every clock is
    a bar START). `ran` = the 📅 engine's answer on the stand-in scan doc (None → no 09:30–20:00 bars)."""
    d = _d(day)
    iso = d.isoformat()
    doc = {"tile": {"bars5": bars5}}
    bars = RN.bars_of(doc, iso)
    reg_cut = _hhmm(_clock(reg_close))
    rth_open = _hhmm(ET_RTH_OPEN)
    noon = _hhmm(NOON_ET)
    out = dict.fromkeys(OUTCOME_KEYS)
    out["ran"] = None
    ran = grade(doc, prev_close, d)
    if ran is None:
        return out
    out["ran"] = ran
    pc = _pos(prev_close)
    first = next((b for b in bars if RN._bar_start(b) >= rth_open), None)
    o = _pos(first["o"]) if first else None
    out["open_930"] = o
    out["gap_pct"] = _pct(o, pc)
    out["gap_up"] = (out["gap_pct"] > 0) if out["gap_pct"] is not None else None
    pre = [b for b in bars if b.get("s") == WC.BAR_PRE]
    vols = [_f(b.get("v")) for b in pre]
    out["pm_vol"] = sum(v for v in vols if v is not None) if pre and any(v is not None for v in vols) else None
    av = _pos(avg_vol_50)
    out["pm_vol_ratio"] = (out["pm_vol"] / av) if out["pm_vol"] is not None and av is not None else None
    out["high"], out["high_pct"], out["high_at"] = ran.get("high"), ran.get("run_pct"), ran.get("peak_et")
    pk = next((b for b in bars if (b.get("s") is None or b.get("s") == WC.BAR_AH) and RN._bar_start(b) == ran["peak_et"]
               and _f(b.get("h")) == ran.get("high")), None)
    out["high_where"] = _where(ran["peak_et"], pk.get("s") if pk else None, reg_cut)
    top = max(float(b["h"]) for b in bars)
    dk = next(b for b in bars if float(b["h"]) == top)
    out["day_high_where"] = _where(RN._bar_start(dk), dk.get("s"), reg_cut)
    out["timing"] = ran.get("timing")
    out["pm_high_pct"], out["pm_peak"] = ran.get("pm_high_pct"), ran.get("premarket_peak")
    regular = [b for b in bars if b.get("s") is None and rth_open <= RN._bar_start(b) < reg_cut]
    by_noon = [b for b in regular if b["t"][11:16] <= noon]
    out["morning_fade"] = (float(by_noon[-1]["c"]) < o) if (by_noon and o is not None) else None
    if regular:
        lo = min(float(b["l"]) for b in regular)
        lb = next(b for b in regular if float(b["l"]) == lo)
        out["low_after_noon"] = RN._bar_start(lb) >= noon
    out["fade_ramp"] = (out["morning_fade"] and out["high_where"] == WHERE[2]) if out["morning_fade"] is not None \
        else None
    out.update(_cross_facts(bars5, curves5, rth_open))
    out["winner"] = (ran["run_pct"] >= WIN_PCT) if ran.get("run_pct") is not None else None
    out["winner_strict"] = ran.get("counts")
    return out


def minute_facts(raw_1m, day, *, reg_close) -> dict:
    """{vwap_reclaim_at, vwap_state} on the 1-minute frame through gajjala_watch.vwap.minute_vwap (WC.VWAP_SESSIONS,
    the regular close as the half-day cut). MINE: the start of the last 1-minute close that went from at-or-under VWAP
    to above it with no later close at or under it. "not_read" when the frame or the VWAP is missing."""
    out = {"vwap_reclaim_at": None, "vwap_state": VWAP_STATES[3]}
    try:
        import pandas as pd
        from chart_maps.gajjala_watch import vwap as VW
        sets = VW.sessions()
        if raw_1m is None or not len(raw_1m) or not sets or "close" not in raw_1m.columns:
            return out
        d = _d(day)
        cut = pd.Timestamp(_at(d, reg_close)).tz_convert("UTC").tz_localize(None)
        vw = VW.minute_vwap(raw_1m, d.isoformat(), sessions=sets, rth_close=cut)
        if vw is None:
            return out
        idx = raw_1m.index
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        close = pd.to_numeric(pd.Series(raw_1m["close"].to_numpy(), index=idx), errors="coerce")
        pts = [(ts, float(c), float(v)) for ts, c, v in zip(idx, close.reindex(vw.index).to_numpy(), vw.to_numpy())
               if v == v and c == c and math.isfinite(float(v)) and math.isfinite(float(c))]
        if not pts:
            return out
        last_under = max((i for i, (_t, c, v) in enumerate(pts) if c <= v), default=None)
        if last_under is None:
            out["vwap_state"] = VWAP_STATES[2]
        elif last_under == len(pts) - 1:
            out["vwap_state"] = VWAP_STATES[1]
        else:
            ts = pd.Timestamp(pts[last_under + 1][0]).tz_localize("UTC").tz_convert("America/New_York")
            out.update(vwap_state=VWAP_STATES[0], vwap_reclaim_at=ts.strftime("%H:%M"))
    except Exception as exc:                                    # noqa: BLE001 — never costs the row
        log.warning("si track: minute VWAP failed: %s", type(exc).__name__)
        return {"vwap_reclaim_at": None, "vwap_state": VWAP_STATES[3]}
    return out


# ── ⛔ 🔒 📄 ✂️ (PURE) ─────────────────────────────────────────────────────────────────────────────────────────────
def _ssr_state(read, sym: str) -> Optional[bool]:
    if not isinstance(read, dict) or read.get("status") != "ok":
        return None
    s = (read.get("states") or {}).get(sym)
    return True if s == "on" else (False if s == "off" else None)


def ssr_facts(open_read, night_read, sym) -> dict:
    """The two SSR.payload answers → {ssr_open, ssr_trig_day, ssr_trig_on, ssr_trig_at}. "on" True · "off" False ·
    "unknown" / a status other than "ok" / no read → None (never False from no record)."""
    out = dict.fromkeys(SSR_KEYS)
    out["ssr_open"] = _ssr_state(open_read, sym)
    out["ssr_trig_day"] = _ssr_state(night_read, sym)
    if out["ssr_trig_day"] is True:
        it = ((night_read.get("items") or {}).get(sym)) or {}
        out["ssr_trig_on"] = it.get("triggered_on") if isinstance(it.get("triggered_on"), str) else None
        out["ssr_trig_at"] = it.get("triggered_at_et") if isinstance(it.get("triggered_at_et"), str) else None
    return out


def sho_facts(payload, sym) -> dict:
    """reg_sho.payload(kick=False) → the 🔒 fields. Not on any list → False only when every list was read
    (`complete`), else None."""
    out = dict.fromkeys(SHO_KEYS)
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), dict):
        return out
    it = payload["items"].get(sym)
    if not isinstance(it, dict) or it.get("state") != "on":
        if payload.get("complete") is True:
            out["regsho_on"], out["regsho_past"] = False, False
        return out
    run = it.get("run") if isinstance(it.get("run"), dict) else {}
    st = run.get("state") if isinstance(run.get("state"), str) else None
    days = run.get("days")
    out.update(regsho_on=True, regsho_state=st,
               regsho_day=days if isinstance(days, int) and not isinstance(days, bool) else None,
               regsho_day13=run.get("day13") if isinstance(run.get("day13"), str) else None,
               regsho_start_by=run.get("start_by") if isinstance(run.get("start_by"), str) else None,
               regsho_past=(st in SHO_PAST_STATES) if st is not None else None,
               regsho_list_date=it.get("as_of") if isinstance(it.get("as_of"), str) else None)
    return out


def filing_facts(b, session) -> dict:
    """The served share basis → {dilution_before, split_before, dilution, split, flag_shorts}. dilution_before = a
    served dilution filing dated BEFORE the session (strict), None unless the SEC read landed; split_before = an
    executed split dated on or before the session, None unless the splits read landed. dilution / split = the 20:15
    flags (stored, never a pattern). A served filing whose kind is in FILING_KINDS_NOT_IN_PATTERN (a full-text-search 6-K, 2026-11-26) never
    sets dilution_before."""
    from short_interest import basis_math as BM
    out = dict.fromkeys(FILING_KEYS)
    basis = b.get("basis") if isinstance(b, dict) and isinstance(b.get("basis"), dict) else None
    if basis is None:
        return out
    s_iso = _iso(session)
    src = basis.get("sources") if isinstance(basis.get("sources"), dict) else {}
    filings = [f for f in basis.get("filings") or [] if isinstance(f, dict) and isinstance(f.get("filed"), str)]
    if src.get("sec") in ("ok", "none", "units"):
        out["dilution_before"] = any(f["filed"][:10] < s_iso for f in filings
                                     if f.get("kind") not in FILING_KINDS_NOT_IN_PATTERN)
    splits = [s for s in basis.get("splits") or [] if isinstance(s, dict)]
    if src.get("splits") == "ok":
        out["split_before"] = any(s.get("when") == "executed" and isinstance(s.get("execution_date"), str)
                                  and s["execution_date"][:10] <= s_iso for s in splits)
    flags = [f for f in basis.get("flags") or [] if isinstance(f, dict)]
    out["dilution"] = any(f.get("key") == BM.FLAG_FILING for f in flags)
    out["split"] = any(f.get("key") == BM.FLAG_SPLIT for f in flags)
    out["flag_shorts"] = [f["short"] for f in flags if isinstance(f.get("short"), str) and f["short"].strip()]
    return out


# ── the outside calls (one budget a night) ────────────────────────────────────────────────────────────────────────
class Budget:
    """1-minute loads AND outside split lookups share ONE cap a night (MAX_LOADS)."""

    def __init__(self, cap: int = MAX_LOADS):
        self.cap = int(cap)
        self.loads = 0
        self.split_calls = 0
        self.deferred = 0

    def take(self, kind: str) -> bool:
        if self.loads + self.split_calls >= self.cap:
            self.deferred += 1
            return False
        if kind == "load":
            self.loads += 1
        else:
            self.split_calls += 1
        return True


class Ctx:
    """One run's seams + the split memo (one lookup per (sym, lo, hi) per run)."""

    def __init__(self, st, now, *, load_1m=None, split_lookup=None, ssr_read=None, sho_read=None, si_read=None,
                 budget: Optional[Budget] = None):
        self.st = st
        self.now = now
        self.load_1m = load_1m or default_load_1m
        self._split = split_lookup
        self.ssr_read = ssr_read or default_ssr_read
        self.sho_read = sho_read or default_sho_read
        self.si_read = si_read
        self.budget = budget or Budget()
        self.memo: dict = {}
        self.raw: dict = {}
        self._scans: dict = {}
        self.faults: list = []

    def split(self, sym: str, lo: date, hi: date):
        """True / iso date (a split in (lo, hi]) / False / None (unread or the budget is spent — retried)."""
        k = (sym, lo.isoformat(), hi.isoformat())
        if k in self.memo:
            return self.memo[k]
        if not self.budget.take("split"):
            return None
        if self._split is None:
            from chart_maps.gajjala import ledger as LG
            self._split = LG._default_split_lookup(self.st)
        try:
            v = self._split(sym, lo, hi)
        except Exception as exc:                                # noqa: BLE001
            log.warning("si track: split check %s failed: %s", sym, type(exc).__name__)
            v = None
        self.memo[k] = v
        return v

    def scan_doc(self, sym: str, day: date) -> Optional[dict]:
        """The day's non-held scan doc of `sym` (ONE scan read per day per run), else None."""
        k = day.isoformat()
        if k not in self._scans:
            self._scans[k] = {str(x.get("symbol") or "").upper(): x for x in self.st.scan_docs([day])
                              if x.get("symbol")}
        return self._scans[k].get(sym)

    def load(self, sym: str, day: date):
        """The raw 1-minute frame (memoized per run) or None; a spent budget → None (the row stays in its retry state)."""
        k = (sym, day.isoformat())
        if k in self.raw:
            return self.raw[k]
        if not self.budget.take("load"):
            return None
        try:
            df = self.load_1m(sym, day)
        except Exception as exc:                                # noqa: BLE001
            log.warning("si track: 1-minute load %s %s failed: %s", sym, day, type(exc).__name__)
            df = None
        self.raw[k] = df
        return df


def default_load_1m(sym: str, day: date):
    """daytrading.data.load_intraday in Massive's spelling, 04:00–20:00 ET (as ledger._default_load_day calls it)."""
    from daytrading import data as dt_data
    from sepa.symbols import for_massive
    return dt_data.load_intraday(for_massive(sym), day, include_premarket=True, include_afterhours=True)


def default_ssr_read(symbols, at):
    from short_interest import ssr as SSR
    return SSR.payload(symbols, now=at, kick=False)


def default_sho_read(now):
    from short_interest import reg_sho as RSH
    return RSH.payload(kick=False, now=now)


def ssr_clocks(session) -> tuple:
    """(open clock, night clock) — both built from the SESSION date, never the wall clock."""
    d = _d(session)
    return _at(d, SSR_OPEN_AT), _at(d, NIGHT_AT)


def _ssr_reads(ctx: Ctx, symbols, at, tag: str):
    """{SYM: …} merged over chunks of SR.MAP_MAX_SYMBOLS → one envelope {"status", "states", "items"}; a raise or
    a non-ok chunk leaves its names out (None) and names the fault."""
    syms = list(dict.fromkeys(symbols))
    out = {"status": "ok", "states": {}, "items": {}}
    step = int(SR.MAP_MAX_SYMBOLS)
    for i in range(0, len(syms), step):
        try:
            ans = ctx.ssr_read(syms[i:i + step], at)
        except Exception as exc:                                # noqa: BLE001
            log.warning("si track: the SSR read (%s) failed: %s", tag, type(exc).__name__)
            ctx.faults.append("ssr_" + tag)
            continue
        if not isinstance(ans, dict) or ans.get("status") != "ok":
            continue
        out["states"].update(ans.get("states") or {})
        out["items"].update(ans.get("items") or {})
    return out


def ssr_rows(ctx: Ctx, session, symbols) -> dict:
    """{SYM: ssr_facts} at the two session-built clocks."""
    if not symbols:
        return {}
    at_open, at_night = ssr_clocks(session)
    o = _ssr_reads(ctx, symbols, at_open, "open")
    n = _ssr_reads(ctx, symbols, at_night, "night")
    return {s: ssr_facts(o, n, s) for s in symbols}


# ── the bars of one name-day ──────────────────────────────────────────────────────────────────────────────────────
def complete(read_doc, day: date) -> bool:
    """The stored read doc holds the whole extended session: its pass stamp is at or after the session's extended
    close (alerts._closes[1] — 20:00; 17:00 on a half day)."""
    at = _utc((read_doc or {}).get("at")) if isinstance(read_doc, dict) else None
    return at is not None and at >= _at(day, _closes(day)[1])


def standin_read(sym: str, day: date, raw_prev, raw_today, now) -> Optional[dict]:
    """A read doc built from the 1-minute frames by the house resampler (bars.build_frames / tile_payload /
    tile_prior_payload) — the shape run.py stores."""
    from chart_maps.gajjala import bars as B
    fr = B.build_frames(sym, day, now, raw_prev, raw_today)
    if fr is None:
        return None
    p = B.tile_payload(fr, "5m")
    q = B.tile_prior_payload(fr, "5m", from_et=GC.RS_TILE_PRIOR_FROM_ET)
    return {"symbol": sym, "date": day.isoformat(), "tile": {"bars5": p["bars"], "curves5": p["curves"],
                                                             "bars5_prior": q["bars"]}}


def day_read(ctx: Ctx, sym: str, day: date, stored) -> tuple:
    """(read doc, bars_src) — the stored doc when complete, else the 1-minute stand-in, else (None, None)."""
    if complete(stored, day):
        return stored, "reads"
    raw = ctx.load(sym, day)
    if raw is None or not len(raw):
        return None, None
    prev = ctx.load(sym, _prev_day(day))
    try:
        doc = standin_read(sym, day, prev, raw, ctx.now)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si track: stand-in read %s %s failed: %s", sym, day, type(exc).__name__)
        doc = None
    return (doc, "minutes") if doc is not None else (None, None)


def _tile(doc, key):
    tile = doc.get("tile") if isinstance(doc, dict) else None
    v = tile.get(key) if isinstance(tile, dict) else None
    return v if isinstance(v, list) else []


# ── 2026-11-26 (spec sishares §3.5): the bar readers the 🏁 follow-up (si_follow) uses — the house engines, named here
# only, so the follow module names no other package for them ───────────────────────────────────────────────────────
def day_bars(doc, day) -> list:
    """The day's 5-minute bars of a read doc (runners.bars_of — finite o/h/l/c > 0, time order)."""
    return RN.bars_of(doc, _iso(day))


def bar_start(b: dict) -> str:
    """A right-labelled 5-minute bar's START, ET HH:MM (runners._bar_start)."""
    return RN._bar_start(b)


def extended_bars(bars: list) -> list:
    """The 09:30–20:00 bars — `s` absent or after hours (runners._ext, fill_next's own filter)."""
    return RN._ext(bars)


def clock_words() -> dict:
    """runners.clock_words — {open, end, …}, every clock built."""
    return RN.clock_words()


def outcome(ctx: Ctx, sym: str, session: date, *, read_doc, prev_read_doc, scan_doc, avg_vol_50) -> dict:
    """The prior close, the split guard, the bars and the day's facts — the outcome group of one row."""
    out = dict.fromkeys(OUTCOME_KEYS)
    pc, src = prior_close_of(read_doc, prev_read_doc, scan_doc, session)
    out.update(prev_close=pc, prev_close_src=src,
               scan_prev_close=_pos(RN._last(scan_doc).get("prev_close")) if isinstance(scan_doc, dict) else None,
               bars_src=None)
    if pc is None:
        out["outcome_state"] = "no_prev_close"
        return out
    sp = ctx.split(sym, _prev_day(session), session)
    if sp is None:
        out["outcome_state"] = "split_unread"
        return out
    if sp is not False:
        out["outcome_state"] = "split"
        return out
    doc, bsrc = day_read(ctx, sym, session, read_doc)
    if doc is None:
        out["outcome_state"] = "no_bars"
        return out
    f = session_facts(_tile(doc, "bars5"), _tile(doc, "curves5"), pc, session, reg_close=_reg_close(session),
                      avg_vol_50=avg_vol_50)
    ran = f.pop("ran")
    if ran is None:
        out["outcome_state"] = "no_bars"
        return out
    out.update(f)
    if isinstance(scan_doc, dict) and _pos(RN._last(scan_doc).get("prev_close")) is not None:
        real = RN.ran_of(scan_doc, doc, session)
        out["winner_scan"] = (real["run_pct"] >= WIN_PCT) if real and real.get("run_pct") is not None else None
    out["bars_src"] = bsrc
    out["outcome_state"] = "ok"
    return out


def vwap_of(ctx: Ctx, sym: str, session: date) -> dict:
    raw = ctx.load(sym, session)
    return minute_facts(raw, session, reg_close=_reg_close(session))


def prev_winner_of(ctx: Ctx, sym: str, session: date, prev_doc: Optional[dict]) -> Optional[bool]:
    """The name's `winner` in the prior session's stored si_track doc; else ran_of on the prior session's stored reads
    on the same prior-close order (only when that read doc is complete and no split sits in the window); else None."""
    prev = _prev_day(session)
    row = next((r for r in (prev_doc or {}).get("rows") or [] if isinstance(r, dict) and r.get("symbol") == sym), None)
    if row is not None and isinstance(row.get("winner"), bool):
        return row["winner"]
    st = ctx.st
    rd = st.get_read(prev, sym)
    if not complete(rd, prev):
        return None
    pp = _prev_day(prev)
    pc, _src = prior_close_of(rd, st.get_read(pp, sym), ctx.scan_doc(sym, prev), prev)
    if pc is None:
        return None
    if ctx.split(sym, pp, prev) is not False:
        return None
    g = grade(rd, pc, prev)
    return (g["run_pct"] >= WIN_PCT) if g and g.get("run_pct") is not None else None


# ── record one session ────────────────────────────────────────────────────────────────────────────────────────────
def _stamp(now) -> str:
    t = _utc(now) or datetime.now(UTC)
    return t.isoformat()


def _avg_vol(st, session: date, sym: str) -> Optional[float]:
    try:
        return _pos((st.get_daily(session, sym) or {}).get("avg_vol_50"))
    except Exception:                                           # noqa: BLE001
        return None


def _next_blank(session: date) -> dict:
    return {"date": _next_day(session).isoformat(), "state": NEXT_STATES[0], "open": None, "high_pct": None,
            "low_pct": None}


class ReadFault(RuntimeError):
    """A gajjala_state read that FAILED (no handle, or the find raised) — never read as "nothing on file"."""


class OnFile(RuntimeError):
    """record_session refused: the session doc on file says source "nightly" — its 🔒 📄 ✂️ fields are point in time
    and cannot be rebuilt, so it is never re-recorded (whatever the index says)."""


def state_read(st, sid: str) -> Optional[dict]:
    """FAULT-AWARE gajjala_state read (2026-11-26 refix): None = a READ FAULT, {} = nothing on file. Through the
    store's `_find_or_none` (store.get_state swallows a raised find into {}); a store without it falls back to
    get_state, a raise there → None."""
    from chart_maps.gajjala import store as ST
    fon = getattr(st, "_find_or_none", None)
    try:
        if callable(fon):
            docs = fon(ST.STATE, {"_id": sid})
            if docs is None:
                return None
            return next((d for d in docs if isinstance(d, dict)), None) or {}
        d = st.get_state(sid)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si track: state read of %s failed: %s", sid, type(exc).__name__)
        return None
    return d if isinstance(d, dict) else {}


def index_dates(st) -> list:
    """The recorded sessions, ascending. RAISES ReadFault on a read fault — a faulted read is never an empty index."""
    doc = state_read(st, INDEX_ID)
    if doc is None:
        raise ReadFault(INDEX_ID)
    d = doc.get("dates")
    return sorted({x for x in d if isinstance(x, str)}) if isinstance(d, list) else []


class WriteFault(RuntimeError):
    """The session doc did not land — record_night logs `record:<date>` and the next night retries it."""


def _write_session(st, sid: str, doc: dict) -> None:
    """ONE `$set` upsert straight on the collection (store._upsert logs and swallows a raise, which would index a
    session that was never stored). No collection or a raised write -> WriteFault, and the date is NOT indexed."""
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.STATE)
    if c is None:
        raise WriteFault("no state collection")
    try:
        c.update_one({"_id": sid}, {"$set": dict(doc)}, upsert=True)
    except Exception as exc:                                    # noqa: BLE001
        raise WriteFault("%s: %s" % (sid, type(exc).__name__)) from exc


def _index_add(st, iso: str) -> bool:
    """ONE `$addToSet` on the index doc — no read-then-write, so a faulted read can never truncate the index."""
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.STATE)
    if c is None:
        return False
    try:
        c.update_one({"_id": INDEX_ID}, {"$addToSet": {"dates": iso}}, upsert=True)
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si track: index write of %s failed: %s", iso, type(exc).__name__)
        return False


def session_doc(st, session, *, strict: bool = False) -> dict:
    """The stored session doc ({} when none). strict: a read fault RAISES ReadFault instead of reading as {}."""
    sid = STATE_FMT.format(date=_iso(session))
    if not strict:
        return st.get_state(sid) or {}
    doc = state_read(st, sid)
    if doc is None:
        raise ReadFault(sid)
    return doc


def _ladder_tier(b):
    """The tier the house ladder gave BEFORE any second-float hold (basis.extreme_contest.from), else the block's own:
    the 🏁 'EXTREME vs High' pattern keeps ONE definition under every EXTREME_CONTEST mode (🧮 2026-11-26, spec
    floatguard §3.7 [C5]). Under the built default `from == to == tier`: no row changes."""
    basis = b.get("basis") if isinstance(b, dict) and isinstance(b.get("basis"), dict) else {}
    ec = basis.get("extreme_contest")
    frm = ec.get("from") if isinstance(ec, dict) else None
    if isinstance(frm, str) and frm in SR.TIER_ORDER:
        return frm
    return b.get("tier") if isinstance(b, dict) else None


def record_session(st, session, now, *, source: str = "nightly", load_1m=None, si_read=None, ssr_read=None,
                   sho_read=None, split_lookup=None, ctx: Optional[Ctx] = None, write: bool = True) -> dict:
    """Record one session: the cohort, every row's fields, the doc + the index. RAISES on a listed / short-interest
    read fault (nothing written); with `write`, RAISES OnFile when the doc on file says source "nightly" and ReadFault
    when that doc cannot be read (nothing computed, nothing written). -> {"session", "rows", "doc", "loads", "split_calls", "deferred_cap", "faults"}."""
    if source not in SOURCES:
        raise ValueError("source")
    d = _d(session)
    s_iso = d.isoformat()
    if write and session_doc(st, d, strict=True).get("source") == SOURCES[0]:
        raise OnFile(s_iso)                                     # a nightly doc is never re-recorded (a fault raises too)
    ctx = ctx or Ctx(st, now, load_1m=load_1m, split_lookup=split_lookup, ssr_read=ssr_read, sho_read=sho_read,
                     si_read=si_read)
    c = cohort(st, d, now, si_read=si_read if si_read is not None else ctx.si_read)
    stamp = _stamp(now)
    own = source == "nightly"
    syms = [r["symbol"] for r in c["rows"]]
    ssr = ssr_rows(ctx, d, syms)
    sho_pay = None
    if own and syms:
        try:
            sho_pay = ctx.sho_read(now)
        except Exception as exc:                                # noqa: BLE001
            log.warning("si track: the Reg SHO read failed: %s", type(exc).__name__)
            ctx.faults.append("sho")
    prev_doc = session_doc(st, _prev_day(d))
    rows = []
    for r in c["rows"]:
        sym = r["symbol"]
        b = r["block"] or {}
        ev = r["ev_read"]
        row = blank_row(d, sym)
        row.update(r["listing"])
        rctx = (r["read_doc"] or {}).get("ctx") if isinstance(r["read_doc"], dict) else None
        fr = rctx.get("float") if isinstance(rctx, dict) and isinstance(rctx.get("float"), dict) else None
        dtc_fn = getattr(SR, "dtc_computed", None)
        try:
            dtc = dtc_fn(b) if callable(dtc_fn) else None
        except Exception:                                       # noqa: BLE001
            dtc = None
        row.update(settlement_date=b.get("settlement_date"), published_on=b.get("published_on"), pit=b.get("pit"),
                   si_shares=b.get("si_shares"), tier=_ladder_tier(b), float_check=b.get("float_check"),
                   pct_float=_f(b.get("pct_of_float")), pct_shares_out=_f(b.get("pct_of_shares_out")),
                   dtc=_f(dtc), dtc_provider=_f(b.get("days_to_cover")), adv=b.get("avg_daily_volume"),
                   float_shares=b.get("float_shares"), float_asof=b.get("float_asof"),
                   float_source=b.get("float_source"), card_float=ev.get("float_shares"),
                   card_float_src=fr.get("src") if fr is not None else None,
                   shares_out=b.get("shares_outstanding"), shares_asof=b.get("shares_asof"),
                   shares_source=b.get("shares_source"))
        row.update(ssr.get(sym) or {})
        if own:
            row.update(sho_facts(sho_pay, sym))
            row.update(filing_facts(b, d))
        prev_rd = st.get_read(_prev_day(d), sym)
        av = _avg_vol(st, d, sym)
        row["avg_vol_50"] = av
        row.update(outcome(ctx, sym, d, read_doc=r["read_doc"], prev_read_doc=prev_rd,
                           scan_doc=c["scan_by"].get(sym), avg_vol_50=av))
        if row["outcome_state"] == "ok":
            row.update(vwap_of(ctx, sym, d))
        else:
            row["vwap_state"] = VWAP_STATES[3]
        row["prev_winner"] = prev_winner_of(ctx, sym, d, prev_doc)
        row["next"] = _next_blank(d)
        row["late"] = not own
        row["recorded_at"] = stamp
        rows.append({k: row.get(k) for k in ROW_KEYS})
    doc = {"date": s_iso, "rows": rows, "excluded": c["excluded"], "n": len(rows), "source": source,
           "recorded_at": stamp, "version": VERSION}
    if write:
        _write_session(st, STATE_FMT.format(date=s_iso), doc)
        _index_add(st, s_iso)
    return {"session": s_iso, "rows": len(rows), "doc": doc, "loads": ctx.budget.loads,
            "split_calls": ctx.budget.split_calls, "deferred_cap": ctx.budget.deferred,
            "faults": list(dict.fromkeys(ctx.faults))}


# ── later nights: retry-state rows, ⛔ still None, next columns ────────────────────────────────────────────────────
def _ended(day: date, now) -> bool:
    t = _utc(now)
    return t is not None and t >= _at(day, _closes(day)[1])


def retry_session(ctx: Ctx, session) -> dict:
    """Fill a stored session's retry-state rows (outcome no_bars / split_unread, VWAP not_read) and its ⛔ fields still
    None. A True / False once stored is never overwritten; the ex-ante fields are never re-read."""
    st = ctx.st
    d = _d(session)
    doc = session_doc(st, d)
    rows = [r for r in doc.get("rows") or [] if isinstance(r, dict)]
    out = {"outcome": 0, "vwap": 0, "ssr": 0}
    if not rows:
        return out
    changed = False
    need_ssr = [r["symbol"] for r in rows if r.get("ssr_open") is None or r.get("ssr_trig_day") is None]
    ssr = ssr_rows(ctx, d, need_ssr) if need_ssr else {}
    for r in rows:
        sym = r.get("symbol")
        got = ssr.get(sym)
        if got:
            for k in ("ssr_open", "ssr_trig_day"):
                if r.get(k) is None and got.get(k) is not None:
                    r[k] = got[k]
                    changed = True
                    out["ssr"] += 1
                    if k == "ssr_trig_day" and got[k] is True:
                        r["ssr_trig_on"], r["ssr_trig_at"] = got.get("ssr_trig_on"), got.get("ssr_trig_at")
        if r.get("outcome_state") in OUTCOME_RETRY:
            o = outcome(ctx, sym, d, read_doc=st.get_read(d, sym), prev_read_doc=st.get_read(_prev_day(d), sym),
                        scan_doc=ctx.scan_doc(sym, d), avg_vol_50=r.get("avg_vol_50"))
            if o.get("outcome_state") != r.get("outcome_state") or o.get("outcome_state") == "ok":
                r.update(o)
                changed = True
                if o.get("outcome_state") == "ok":
                    out["outcome"] += 1
        if r.get("outcome_state") == "ok" and r.get("vwap_state") == VWAP_STATES[3]:
            v = vwap_of(ctx, sym, d)
            if v["vwap_state"] != VWAP_STATES[3]:
                r.update(v)
                changed = True
                out["vwap"] += 1
    if changed:
        st.set_state(STATE_FMT.format(date=d.isoformat()), dict(doc, rows=rows))
    return out


def fill_next(st, session, now, *, load_1m=None, split_lookup=None, ctx: Optional[Ctx] = None) -> dict:
    """The `next` column of a stored session, once the next session has ended: the 09:30 open, the 09:30–20:00 high /
    low vs that open; a split in (D, N] → "split". Pending until that night; a spent budget leaves it pending."""
    ctx = ctx or Ctx(st, now, load_1m=load_1m, split_lookup=split_lookup)
    d = _d(session)
    n_day = _next_day(d)
    out = {"filled": 0, "pending": 0}
    doc = session_doc(st, d)
    rows = [r for r in doc.get("rows") or [] if isinstance(r, dict)]
    if not rows:
        return out
    if not _ended(n_day, now):
        out["pending"] = sum(1 for r in rows if (r.get("next") or {}).get("state") in NEXT_RETRY)
        return out
    changed = False
    rth_open = _hhmm(ET_RTH_OPEN)
    for r in rows:
        nx = dict(r.get("next") or _next_blank(d))
        if nx.get("state") not in NEXT_RETRY:
            continue
        sym = r.get("symbol")
        sp = ctx.split(sym, d, n_day)
        if sp is None:
            out["pending"] += 1
            continue
        if sp is not False:
            nx.update(state="split", open=None, high_pct=None, low_pct=None)
        else:
            rd, _src = day_read(ctx, sym, n_day, st.get_read(n_day, sym))
            bars = RN.bars_of(rd, n_day.isoformat()) if rd is not None else []
            ext = [b for b in bars if (b.get("s") is None or b.get("s") == WC.BAR_AH)]
            first = next((b for b in ext if RN._bar_start(b) >= rth_open), None)
            o = _pos(first["o"]) if first else None
            if o is None:
                nx.update(state="no_bars")
            else:
                tail = [b for b in ext if RN._bar_start(b) >= rth_open]
                nx.update(state="ok", open=o, high_pct=RN._pct(max(float(b["h"]) for b in tail), o),
                          low_pct=RN._pct(min(float(b["l"]) for b in tail), o))
        r["next"] = nx
        changed = True
        out["filled"] += 1
    if changed:
        st.set_state(STATE_FMT.format(date=d.isoformat()), dict(doc, rows=rows))
    return out


# ── stats ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def shuffle_share(flags, wins, days, *, draws, seed) -> Optional[float]:
    """PURE — the within-day placebo (MINE). Inside each day the True / False labels are shuffled among that day's
    rows (the day's count of True kept); the share of `draws` shuffles whose absolute difference in win rate is at
    least the observed one. None when a side is empty."""
    import numpy as np
    fl = np.array([bool(x) for x in flags])
    wn = np.array([1.0 if x else 0.0 for x in wins])
    if len(fl) != len(wn) or len(fl) != len(list(days)):
        return None
    n_t = int(fl.sum())
    n_f = len(fl) - n_t
    if n_t == 0 or n_f == 0:
        return None

    def diff(f):
        return abs(wn[f].mean() - wn[~f].mean())
    obs = diff(fl)
    groups: dict = {}
    for i, dd in enumerate(days):
        groups.setdefault(dd, []).append(i)
    idx = [np.array(v) for _k, v in sorted(groups.items())]
    rng = np.random.default_rng(seed)
    hit = 0
    for _ in range(int(draws)):
        f = fl.copy()
        for g in idx:
            if len(g) > 1:
                f[g] = fl[g][rng.permutation(len(g))]
        if diff(f) >= obs - 1e-12:
            hit += 1
    return hit / float(draws)


def _study():
    try:
        from scripts import gajjala_study as GS
        return GS
    except Exception as exc:                                    # noqa: BLE001 — the stats then carry no interval
        log.warning("si track: the bootstrap is unavailable: %s", type(exc).__name__)
        return None


def _pattern_value(row: dict, key: str) -> Optional[bool]:
    if key == "tier_extreme":
        t = row.get("tier")
        return (t == SR.TIER_EXTREME) if t in (SR.TIER_HIGH, SR.TIER_EXTREME) else None
    v = row.get(key)
    return v if isinstance(v, bool) else None


def _shape_value(row: dict, key: str) -> Optional[bool]:
    if key == "vwap_reclaimed":
        s = row.get("vwap_state")
        return None if s not in VWAP_STATES or s == VWAP_STATES[3] else (s == VWAP_STATES[0])
    v = row.get(key)
    return v if isinstance(v, bool) else None


def counted(rows) -> list:
    """The counted cohort: rows on the list BEFORE the day with a True / False winner."""
    return [r for r in rows if isinstance(r, dict) and r.get("listed_before") is True
            and isinstance(r.get("winner"), bool)]


def _ci_pp(ci) -> Optional[list]:
    return [ci[0] * 100.0, ci[1] * 100.0] if ci is not None else None


def stats(rows) -> dict:
    """PURE but for the lazy bootstrap import — the counted cohort's base, the first-listed-that-day counts, the seven
    patterns (names AND days intervals, the house verdict, the within-day shuffle) and the day-shape counts."""
    GS = _study()
    rows = [r for r in rows or [] if isinstance(r, dict)]
    cnt = counted(rows)
    vals = [1.0 if r["winner"] else 0.0 for r in cnt]
    syms = [r["symbol"] for r in cnt]
    dates = [r["date"] for r in cnt]
    w = int(sum(vals))
    base = {"n": len(cnt), "names": len(set(syms)), "days": len(set(dates)), "winners": w,
            "rate": _rate(w, len(cnt)), "ci_names": None, "ci_days": None}
    if GS is not None and cnt:
        base["ci_names"] = GS.cluster_ci(vals, syms) if len(set(syms)) >= MIN_NAMES else None
        base["ci_days"] = GS.cluster_ci(vals, dates) if len(set(dates)) >= MIN_NAMES else None
    new = [r for r in rows if r.get("listed_before") is False and isinstance(r.get("winner"), bool)]
    rth = _hhmm(ET_RTH_OPEN)
    bo = [r for r in new if isinstance(r.get("listed_at"), str) and r["listed_at"] < rth]
    ao = [r for r in new if isinstance(r.get("listed_at"), str) and r["listed_at"] >= rth]
    new_today = {"n": len(new), "winners": sum(1 for r in new if r["winner"]),
                 "before_open": {"n": len(bo), "winners": sum(1 for r in bo if r["winner"])},
                 "after_open": {"n": len(ao), "winners": sum(1 for r in ao if r["winner"])}}
    pats = []
    for key, _label, _known in PATTERNS:
        wv, ws, wd, ov, os_, od = [], [], [], [], [], []
        flags, wins, days = [], [], []
        unknown = 0
        for r in cnt:
            v = _pattern_value(r, key)
            if v is None:
                unknown += 1
                continue
            x = 1.0 if r["winner"] else 0.0
            (wv if v else ov).append(x)
            (ws if v else os_).append(r["symbol"])
            (wd if v else od).append(r["date"])
            flags.append(v)
            wins.append(r["winner"])
            days.append(r["date"])
        rw, ro = _rate(int(sum(wv)), len(wv)), _rate(int(sum(ov)), len(ov))
        p = {"key": key, "n_with": len(wv), "w_with": int(sum(wv)), "rate_with": rw, "n_without": len(ov),
             "w_without": int(sum(ov)), "rate_without": ro,
             "diff_pp": ((rw - ro) * 100.0) if rw is not None and ro is not None else None,
             "ci_names_pp": None, "ci_days_pp": None, "shuffle_share": None, "names_with": len(set(ws)),
             "names_without": len(set(os_)), "days_with": len(set(wd)), "days_without": len(set(od)),
             "unknown": unknown, "verdict": "no_interval"}
        if GS is not None:
            if p["names_with"] >= MIN_NAMES and p["names_without"] >= MIN_NAMES:
                p["ci_names_pp"] = _ci_pp(GS.cluster_delta_ci(wv, ws, ov, os_))
            if p["days_with"] >= MIN_NAMES and p["days_without"] >= MIN_NAMES:
                p["ci_days_pp"] = _ci_pp(GS.cluster_delta_ci(wv, wd, ov, od))
            p["verdict"] = GS.verdict(p["ci_days_pp"], p["ci_names_pp"])
            if p["verdict"] != "no_interval":
                p["shuffle_share"] = shuffle_share(flags, wins, days, draws=GS.BOOT_DRAWS, seed=GS.BOOT_SEED)
        wk = VERDICT_WORD.get(p["verdict"], "too_few")
        p["word"] = WORDS[wk] % len(PATTERNS) if wk == "clear" else WORDS[wk]
        pats.append(p)
    win, rest = [r for r in cnt if r["winner"]], [r for r in cnt if not r["winner"]]
    where = {"winners": {k: sum(1 for r in win if r.get("high_where") == k) for k in WHERE},
             "rest": {k: sum(1 for r in rest if r.get("high_where") == k) for k in WHERE}}
    shapes = []
    for key, _label in SHAPES:
        def side(rs):
            vv = [_shape_value(r, key) for r in rs]
            return {"k": sum(1 for v in vv if v is True), "n": sum(1 for v in vv if v is not None)}
        shapes.append({"key": key, "winners": side(win), "rest": side(rest)})
    return {"base": base, "new_today": new_today, "patterns": pats, "where": where, "shapes": shapes,
            "interval_ok": GS is not None, "version": VERSION}


def all_rows(st) -> list:
    out = []
    for iso in index_dates(st):
        out.extend(r for r in session_doc(st, iso, strict=True).get("rows") or [] if isinstance(r, dict))
    return out


def write_stats(st, now) -> dict:
    """RAISES ReadFault on an index / session read fault — never stores the stats of a faulted read."""
    dates = index_dates(st)
    rows = all_rows(st)
    s = stats(rows)
    s.update(computed_at=_stamp(now), through=dates[-1] if dates else None, version=VERSION)
    s["follow"], s["names"], s["pinned"] = None, None, None
    try:                                                        # 2026-11-26 the follow-up counts, in their own try
        from chart_maps.gajjala import si_follow as SF
        facts = SF.read_facts(st, SF.fact_days(dates, now))
        s["follow"] = SF.follow_stats(rows, facts, now)
        s["names"] = SF.names(rows, facts)
        s["pinned"] = SF.pinned(SF.pins(st), rows, facts)
    except Exception as exc:                                    # noqa: BLE001 — never costs the ledger's stats
        log.warning("si track: the follow-up stats failed: %s", type(exc).__name__)
        s["follow"], s["names"], s["pinned"] = None, None, None
    st.set_state(STATS_ID, s)
    return s


# ── the nightly entry ─────────────────────────────────────────────────────────────────────────────────────────────
def tonight(now) -> date:
    et = (_utc(now) or datetime.now(UTC)).astimezone(ET).date()
    return et if _is_market_day(et) else _prev_day(et)


def lookback(session: date) -> list:
    """LOOKBACK_SESSIONS market days ending AT `session`, oldest first."""
    out = [session]
    while len(out) < LOOKBACK_SESSIONS:
        out.append(_prev_day(out[-1]))
    return sorted(out)


def _has_reads(st, d: date) -> bool:
    try:
        return bool(st.reads(d))
    except Exception:                                           # noqa: BLE001
        return False


def record_night(now, *, store=None, **seams) -> dict:
    """Tonight's session, then the late sessions of the look-back, the next columns and the retry-state rows, then
    the follow-up facts (si_follow.fill_night — its OWN MAX_LOADS budget, its own fence; 2026-11-26), then the stats.
    One MAX_LOADS budget for the ledger's 1-minute loads and outside split lookups. Never raises."""
    out = {"session": None, "rows": 0, "late": [], "next_filled": 0, "loads": 0, "split_calls": 0,
           "deferred_cap": 0, "stats": False, "faults": [], "follow": None}
    try:
        from chart_maps.gajjala import store as ST
        st = store if store is not None else ST.default()
        if st.coll(ST.STATE) is None:
            out["faults"].append("no_store")
            return out
        ctx = Ctx(st, now, load_1m=seams.get("load_1m"), split_lookup=seams.get("split_lookup"),
                  ssr_read=seams.get("ssr_read"), sho_read=seams.get("sho_read"), si_read=seams.get("si_read"),
                  budget=Budget(seams.get("max_loads", MAX_LOADS)))
        s = tonight(now)
        out["session"] = s.isoformat()
        try:
            have = set(index_dates(st))
        except ReadFault:                                       # never "nothing on file": the night is skipped
            out["faults"].append("index_read")
            return out
        win = [d for d in lookback(s) if _ended(d, now)]
        et_today = (_utc(now) or datetime.now(UTC)).astimezone(ET).date()
        for d in sorted(win, key=lambda x: (x != s, x)):          # tonight first, then the late ones oldest first
            if d.isoformat() in have:
                continue
            if not _has_reads(st, d):
                continue
            src = "nightly" if d == et_today else "late"
            try:
                if not _listed_ok(st, d):
                    out["faults"].append("listed_empty:" + d.isoformat())
                    continue
                res = record_session(st, d, now, source=src, ctx=ctx)
                if d == s:
                    out["rows"] = res["rows"]
                else:
                    out["late"].append(d.isoformat())
            except OnFile:                                      # a nightly doc the index lost: put it back, keep it
                _index_add(st, d.isoformat())
                out["faults"].append("on_file:" + d.isoformat())
            except Exception as exc:                            # noqa: BLE001 — not recorded, retried next night
                log.warning("si track: %s not recorded: %s", d, type(exc).__name__)
                out["faults"].append("record:%s:%s" % (d.isoformat(), type(exc).__name__))
        try:
            have = set(index_dates(st))
        except ReadFault:
            out["faults"].append("index_read")
            have = set()
        for d in win:
            if d.isoformat() not in have:
                continue
            try:
                retry_session(ctx, d)
                out["next_filled"] += fill_next(st, d, now, ctx=ctx)["filled"]
            except Exception as exc:                            # noqa: BLE001
                log.warning("si track: retry of %s failed: %s", d, type(exc).__name__)
                out["faults"].append("retry:%s:%s" % (d.isoformat(), type(exc).__name__))
        try:                                                    # 2026-11-26 the follow-up: its OWN budget, own fence
            from chart_maps.gajjala import si_follow as SF
            out["follow"] = SF.fill_night(st, now, load_1m=seams.get("load_1m"),
                                          split_lookup=seams.get("split_lookup"), max_loads=seams.get("max_loads"),
                                          share=ctx)
        except Exception as exc:                                # noqa: BLE001 — never costs the ledger
            log.warning("si track: the follow-up failed: %s", type(exc).__name__)
            out["faults"].append("follow:%s" % type(exc).__name__)
        try:
            if "index_read" in out["faults"]:
                raise ReadFault(INDEX_ID)
            write_stats(st, now)
            out["stats"] = True
        except Exception as exc:                                # noqa: BLE001
            log.warning("si track: stats failed: %s", type(exc).__name__)
            out["faults"].append("stats:%s" % type(exc).__name__)
        out.update(loads=ctx.budget.loads, split_calls=ctx.budget.split_calls, deferred_cap=ctx.budget.deferred)
        out["faults"] = list(dict.fromkeys(out["faults"] + ctx.faults))
    except Exception as exc:                                    # noqa: BLE001
        log.exception("si track: the night failed")
        out["faults"].append("night:%s" % type(exc).__name__)
    return out


def _listed_ok(st, d: date) -> bool:
    """False when the session has stored reads but the listed read came back empty (a fault the store swallowed) —
    the ledger never falls back to every read; the session is retried the next night."""
    from chart_maps.gajjala import scanner as SC
    return bool(SC.listed_symbols(st, d))


# ── the served block ──────────────────────────────────────────────────────────────────────────────────────────────
def rule_text() -> str:
    """Every number read from a constant at CALL time — no date typed."""
    from chart_maps.gajjala_watch import runners as _R
    w = _R.clock_words()
    return ("A name is counted when it was on the 🩳 list before the session — listed by his scanner on one of the "
            "%d market days before it. It ran when its %s–%s high was at least +%g%% over the prior session's last "
            "regular 5-minute close; premarket never counts. Short interest is the settlement FINRA had published "
            "before the day (%d business days after settlement); a name with none is not recorded. ⛔ is the SSR "
            "record as of %s ET that day (on at the open) and as of %s ET (triggered that day); a day with no record "
            "reads not known. A pattern reads only with at least %d names and %d days on each side; the interval is "
            "drawn on names and on days and must clear 0 on both. Recorded at %s ET; a missed day, a later bar read "
            "and the next-session columns are filled within %d market days. Names first listed that day are shown "
            "apart and never counted."
            % (GC.STAY_LISTED_SESSIONS, w["open"], w["end"], WIN_PCT, SR.FINRA_PUBLICATION_BDAYS,
               _hhmm(SSR_OPEN_AT), NIGHT_AT, MIN_NAMES, MIN_NAMES, GC.LEDGER_GRADE_AT_ET, LOOKBACK_SESSIONS))


def honesty() -> str:
    return ("A ledger of what happened, not a test: only names on the list before the day are counted; the sample is "
            "small, one market regime, the same name repeats across days and the days share one market; the "
            "patterns were chosen after looking at this kind of data. The prior close is the last regular 5-minute "
            "bar, not the exchange's closing print, so a ✅ here can differ from the 📅 chip near the line. The "
            "noon fade, the after-hours ramp, the VWAP reclaim and the within-day shuffle are MINE. Days recorded "
            "late carry no 🔒 📄 ✂️ fields, and ⛔ reads not known where the SSR record was never read. UNMEASURED. "
            "Not advice.")


def rules_line() -> str:
    return "🏁 🩳 SI track record: " + rule_text()


def _rows_for_days(st, dates: list) -> list:
    return [(iso, [r for r in session_doc(st, iso, strict=True).get("rows") or [] if isinstance(r, dict)])
            for iso in dates]


def _bool_cell(v, yes: str, no: str = "") -> str:
    return yes if v is True else (no if v is False else DASH)


def _pct_cell(v, signed: bool = True) -> str:
    x = _f(v)
    if x is None:
        return DASH
    return (_signed(x, "%") if signed else "%.1f%%" % x)


def _cells(r: dict) -> dict:
    nx = r.get("next") if isinstance(r.get("next"), dict) else {}
    si = "%s / %s" % (_pct_cell(r.get("pct_float"), False), _pct_cell(r.get("pct_shares_out"), False))
    fl = _compact(r.get("float_shares"))
    fl = DASH if fl is None else (fl + (" (%s)" % r["float_asof"][5:] if isinstance(r.get("float_asof"), str) else ""))
    ssr = []
    if r.get("ssr_open") is True:
        ssr.append("on at open")
    if r.get("ssr_trig_day") is True:
        ssr.append("triggered" + (" " + r["ssr_trig_at"] if isinstance(r.get("ssr_trig_at"), str) else ""))
    if not ssr:
        ssr = [DASH if (r.get("ssr_open") is None or r.get("ssr_trig_day") is None) else "off"]
    sho = DASH
    if r.get("regsho_on") is True:
        sho = SHO_WORDS["past"] if r.get("regsho_past") is True else (
            "day %d" % r["regsho_day"] if isinstance(r.get("regsho_day"), int) else SHO_WORDS["on"])
    elif r.get("regsho_on") is False:
        sho = ""
    flags = " · ".join(r["flag_shorts"]) if isinstance(r.get("flag_shorts"), list) and r["flag_shorts"] else (
        DASH if r.get("flag_shorts") is None else "")
    st = r.get("outcome_state")
    high = (_pct_cell(r.get("high_pct")) + (" at " + r["high_at"] if isinstance(r.get("high_at"), str) else "")) \
        if st == "ok" else {"split": "split — not graded", "split_unread": "split check pending",
                            "no_bars": "bars pending", "no_prev_close": "no prior close"}.get(st, DASH)
    vw = r.get("vwap_state")
    vwap = VWAP_WORDS.get(vw, DASH).format(t=r.get("vwap_reclaim_at") or "") if vw in VWAP_WORDS else DASH
    cross = r["cross_up_at"] if isinstance(r.get("cross_up_at"), str) else (
        "premarket only" if r.get("cross_pre") is True else (DASH if r.get("cross_pre") is None else "none"))
    nst = nx.get("state")
    if nst == "ok":
        nxt = "%s → %s / %s" % (_px(nx.get("open")), _pct_cell(nx.get("high_pct")), _pct_cell(nx.get("low_pct")))
    else:
        nxt = {"pending": "pending", "split": "split", "no_bars": "no bars"}.get(nst, DASH)
    listed = "before" if r.get("listed_before") is True else (r.get("listed_at") or DASH)
    return {"ticker": r.get("symbol") or DASH, "listed": listed, "si": si,
            "tier": SR.TIER_WORDS.get(r.get("tier"), DASH), "dtc": ("%.2f" % r["dtc"]) if _f(r.get("dtc")) is not None
            else DASH, "float": fl, "ssr": " · ".join(ssr), "sho": sho, "flags": flags,
            "gap": _pct_cell(r.get("gap_pct")), "pm_vol": ("%.2f×" % r["pm_vol_ratio"])
            if _f(r.get("pm_vol_ratio")) is not None else DASH, "high": high,
            "where": WHERE_WORDS.get(r.get("high_where"), DASH), "cross": cross, "vwap": vwap, "next": nxt}


def _px(v) -> str:
    x = _f(v)
    return DASH if x is None else ("%g" % x)


def _compact(n) -> Optional[str]:
    from chart_maps.gajjala import tab as GT
    return GT._compact(n)


def _href(sym: str) -> Optional[str]:
    try:
        from chart_maps.gajjala import tab as GT
        return GT.chart_href(sym, "5m")
    except Exception:                                           # noqa: BLE001
        return None


def _row_group(r: dict) -> str:
    """DAY_GROUPS: "counted" (listed before the day, graded True / False) · "new" (first listed that day) · "other"
    (listed before the day but not graded, or no listing date on file)."""
    if r.get("listed_before") is True and isinstance(r.get("winner"), bool):
        return "counted"
    return "new" if r.get("listed_before") is False else "other"


def _follow_cell(r: dict, fwd_by) -> dict:
    """{FOLLOW_HEAD key: text} — si_follow.cells on the row's forward read; a dash when the follow was not read."""
    key = FOLLOW_HEAD[0]
    if not isinstance(fwd_by, dict):
        return {key: DASH}
    try:
        from chart_maps.gajjala import si_follow as SF
        got = SF.cells(r, fwd_by.get((r.get("date"), r.get("symbol"))))
        return {key: got.get(key, DASH) if isinstance(got, dict) else DASH}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("si track: the follow cell failed: %s", type(exc).__name__)
        return {key: DASH}


def _day_rows(rows: list, fwd_by=None) -> list:
    """Inside a day: the counted rows, then the first-listed-that-day rows, then the other not-counted rows; each part
    winners first, then high_pct DESC. The flags print ONCE, in the Flags column (`cells.flags`): `chips` is served
    empty (2026-11-26 refix — the Ticker cell printed every flag a second time). 2026-11-26 (sishares): `cells` gains
    the ONE follow-up column (FOLLOW_HEAD) from `fwd_by` {(date, symbol): forward}."""
    def k(r):
        return (0 if r.get("winner") is True else 1, -(_f(r.get("high_pct")) or -1e18), r.get("symbol") or "")
    out = []
    for g in DAY_GROUPS:
        for r in sorted([r for r in rows if _row_group(r) == g], key=k):
            out.append({"symbol": r.get("symbol"), "href": _href(r.get("symbol") or ""),
                        "win": "✅" if r.get("winner") is True else "", "counted": g == "counted", "group": g,
                        "cells": dict(_cells(r), **_follow_cell(r, fwd_by)), "chips": [],
                        "title": "%s · %s · %s" % (r.get("symbol"), r.get("date"), UNMEASURED_WORD)})
    return out


UNMEASURED_WORD = "UNMEASURED"


def _day_label(iso: str) -> str:
    d = _d(iso)
    return d.strftime("%a %m-%d") if d else iso


def _ci_text(ci) -> str:
    return "[%s, %s]" % (_num_text(ci[0]), _num_text(ci[1]))


def _pattern_rows(st_doc: dict) -> list:
    out = []
    by = {p.get("key"): p for p in st_doc.get("patterns") or [] if isinstance(p, dict)}
    for key, label, known in PATTERNS:
        p = by.get(key) or {"n_with": 0, "w_with": 0, "rate_with": None, "n_without": 0, "w_without": 0,
                            "rate_without": None, "diff_pp": None, "unknown": 0, "word": WORDS["too_few"]}
        d = _f(p.get("diff_pp"))
        if d is None:
            diff = DASH
        else:
            diff = _signed(d, " pp")
            if p.get("ci_names_pp"):
                diff += " · names " + _ci_text(p["ci_names_pp"])
            if p.get("ci_days_pp"):
                diff += " · days " + _ci_text(p["ci_days_pp"])
        sh = _f(p.get("shuffle_share"))
        unk = UNKNOWN_TEXT.format(k=int(p.get("unknown") or 0))
        out.append({"key": key, "label": label, "known_text": known,
                    "with_text": COUNT_TEXT.format(w=int(p.get("w_with") or 0), n=int(p.get("n_with") or 0),
                                                   rate=_pct_text(p.get("rate_with"))),
                    "without_text": COUNT_TEXT.format(w=int(p.get("w_without") or 0), n=int(p.get("n_without") or 0),
                                                      rate=_pct_text(p.get("rate_without"))),
                    "diff_text": diff,
                    "shuffle_text": SHUFFLE_TEXT.format(p="%.0f" % (sh * 100.0)) if sh is not None else DASH,
                    "word": p.get("word") if isinstance(p.get("word"), str) else WORDS["too_few"],
                    "unknown_text": unk, "title": PATTERN_TITLE.format(label=label, known=known, unknown=unk)})
    return out


def day_heads() -> list:
    """DAY_HEADS + the ONE follow-up column (2026-11-26, C15)."""
    return [list(h) for h in DAY_HEADS] + [list(FOLLOW_HEAD)]


def _empty_block() -> dict:
    out = dict.fromkeys(BLOCK_KEYS)
    out.update(title=TITLE, summary_text=EMPTY_SUMMARY, empty_text=EMPTY_TEXT.format(at=GC.LEDGER_GRADE_AT_ET),
               pattern_heads=PATTERN_HEADS, patterns=[], shape_rows=[], heads=day_heads(), days=[],
               rule_label=RULE_LABEL, rule_text=rule_text(), honesty=honesty(), n=0, n_days=0)
    return out


def served_block(st, session, now) -> Optional[dict]:
    """The 🩳 block's `si_track` key. Mongo reads only (the index, the stats doc, the last SPAN_SESSIONS session docs).
    No stored doc → the empty block (not a fault). RAISES on a read fault (ReadFault on the index or a session doc;
    high_si serves FAULT_TEXT). 2026-11-26 (sishares): `follow` = si_follow.served and the day table's ONE follow-up
    column, in their own fence — a fault there serves `follow` None and a dash in that column, the rest unchanged."""
    if st is None:
        from chart_maps.gajjala import store as ST
        st = ST.default()
    dates = index_dates(st)
    if not dates:
        return _empty_block()
    sd = st.get_state(STATS_ID) or {}
    if not sd.get("base"):
        sd = stats(all_rows(st))
    b = sd.get("base") or {}
    n, w = int(b.get("n") or 0), int(b.get("winners") or 0)
    rate = _pct_text(b.get("rate"))
    if b.get("ci_names") and b.get("ci_days"):
        cn, cd = b["ci_names"], b["ci_days"]
        tail = BASE_CI_TAIL.format(nlo=_pct_text(cn[0]), nhi=_pct_text(cn[1]), dlo=_pct_text(cd[0]),
                                   dhi=_pct_text(cd[1]))
    else:
        tail = BASE_FEW_TAIL
    out = dict.fromkeys(BLOCK_KEYS)
    nt = sd.get("new_today") or {}
    bo, ao = nt.get("before_open") or {}, nt.get("after_open") or {}
    wh = sd.get("where") or {}
    ww, wr = wh.get("winners") or {}, wh.get("rest") or {}
    w_ = RN.clock_words()
    shapes = {s.get("key"): s for s in sd.get("shapes") or [] if isinstance(s, dict)}
    shape_rows = []
    for key, label in SHAPES:
        s = shapes.get(key) or {}
        a, z = s.get("winners") or {}, s.get("rest") or {}
        shape_rows.append({"label": label, "win_text": SHAPE_COUNT.format(k=int(a.get("k") or 0), n=int(a.get("n") or 0)),
                           "rest_text": SHAPE_COUNT.format(k=int(z.get("k") or 0), n=int(z.get("n") or 0))})
    recent = sorted(dates)[-SPAN_SESSIONS:][::-1]
    by_day = _rows_for_days(st, recent)
    fwd_by, follow = None, None
    try:                                                        # 2026-11-26 the follow-up — its own fence
        from chart_maps.gajjala import si_follow as SF
        cf = SF.cell_facts(st, by_day, now)                     # the follow facts read ONCE for this build
        fwd_by = SF.forwards(st, by_day, now, facts=cf)
        follow = SF.served(st, dates, by_day, now, facts=cf)
    except Exception as exc:                                    # noqa: BLE001 — the ledger block stands without it
        log.warning("si track: the follow-up block failed: %s", type(exc).__name__)
        fwd_by, follow = None, None
    days, total, pend = [], 0, 0
    for iso, rows in by_day:
        pend += sum(1 for r in rows if (r.get("next") or {}).get("state") in NEXT_RETRY)
        drows = _day_rows(rows, fwd_by)
        if total + len(drows) > ROWS_MAX:
            drows = drows[:max(0, ROWS_MAX - total)]
        total += len(drows)
        days.append({"date": iso, "label": _day_label(iso), "rows": drows, "new_label": NEW_LABEL,
                     "other_label": OTHER_LABEL})
    n_rows = sum(len(rows) for _iso, rows in by_day)
    out.update(
        title=TITLE, summary_text=SUMMARY_TEXT.format(w=w, n=n, pct=WIN_PCT),
        base_text=BASE_TEXT.format(w=w, n=n, pct=WIN_PCT, rate=rate, names=int(b.get("names") or 0),
                                   days=int(b.get("days") or 0), tail=tail),
        new_today_text=NEW_TODAY_TEXT.format(w=int(nt.get("winners") or 0), n=int(nt.get("n") or 0),
                                             a=int(bo.get("winners") or 0), b=int(bo.get("n") or 0),
                                             c=int(ao.get("winners") or 0), d=int(ao.get("n") or 0),
                                             open=_hhmm(ET_RTH_OPEN)),
        pattern_heads=PATTERN_HEADS, patterns=_pattern_rows(sd),
        where_text=WHERE_TEXT.format(open=w_["open"], end=w_["end"], a=int(ww.get(WHERE[0]) or 0),
                                     b=int(ww.get(WHERE[1]) or 0), c=int(ww.get(WHERE[2]) or 0),
                                     d=int(wr.get(WHERE[0]) or 0), e=int(wr.get(WHERE[1]) or 0),
                                     f=int(wr.get(WHERE[2]) or 0)),
        shape_rows=shape_rows, heads=day_heads(), days=days,
        shown_text=SHOWN_TEXT.format(lim=ROWS_MAX, n=n_rows) if n_rows > ROWS_MAX else None,
        pending_text=PENDING_TEXT.format(k=pend) if pend else None,
        asof_text=ASOF_TEXT.format(at=GC.LEDGER_GRADE_AT_ET, date=dates[-1]),
        rule_label=RULE_LABEL, rule_text=rule_text(), honesty=honesty(), fault_text=None, empty_text=None,
        n=n, n_days=len(dates), follow=follow)
    return out


def fault_block() -> dict:
    return {"fault_text": FAULT_TEXT}


__all__ = ["STATE_FMT", "INDEX_ID", "STATS_ID", "VERSION", "WIN_PCT", "FIRST_HOUR_END", "NOON_ET", "SSR_OPEN_AT",
           "NIGHT_AT", "LOOKBACK_SESSIONS", "MAX_LOADS", "ROWS_MAX", "SPAN_SESSIONS", "MIN_NAMES", "BASIS_SRCS",
           "PATTERNS", "SHAPES", "WORDS", "ROW_KEYS", "BLOCK_KEYS", "FAULT_TEXT", "EMPTY_SUMMARY", "EMPTY_TEXT",
           "NEW_LABEL", "OTHER_LABEL", "DAY_GROUPS", "FILING_KINDS_NOT_IN_PATTERN", "FOLLOW_HEAD", "day_heads",
           "day_bars", "bar_start", "extended_bars", "clock_words",
           "ReadFault", "OnFile", "state_read", "index_dates", "session_doc",
           "pit_block", "pit_blocks", "cohort", "prior_close_of", "grade", "session_facts", "minute_facts",
           "ssr_facts", "sho_facts", "filing_facts", "record_session", "fill_next", "retry_session", "shuffle_share",
           "stats", "record_night", "served_block", "fault_block", "rule_text", "honesty", "rules_line", "Budget",
           "Ctx", "ssr_clocks", "complete", "standin_read"]
