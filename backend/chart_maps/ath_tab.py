"""🏔️ ATH tab on Chart Maps (Ajay 2026-09-29).

The ask, verbatim: "Can you give me a new tab - for all the stocks that are
reaching all time highs? call it ATH. Once some of them are going below their
ATH or 52 Week Highs.."

TWO GROUPS on the Dual-Momentum-style `sort=` toggle:
  * 🏔️ At ATH (`default`) — the print is through, at, or within the
    `AT_ATH_TOL` band of the all-time high; through-today first, then the
    closest under.
  * ↘️ Slipping (`slipping`) — an all-time or 52-week high set in the last
    `SLIP_LOOKBACK_SESSIONS` closed sessions (or today) and the print now
    outside the same band under it; freshest high first.

HONESTY. "All-time" is claimed ONLY when the history reaches the listing
(`completeness`); every other name says "high since <first bar>" and is
counted. The long history is `chart_maps.ath_history` (monthly bars after the
foreign-head and last-hole cuts), merged here with the cached 2-year closed
daily frame (exact days for recent highs) and today's snapshot high.

ONE ENGINE. Session, closed bars, the one live print, the verify phases and the
52-week high are `supply_demand.key_levels`'s own; the band is
`zone_edge.NEW_HIGH_TOL` (the app's "at the 52w high" constant); the 50-day is
`entry_exit._sma`, the turnover `quick_bounce.avg_dollar_vol`.

THE MEMO is the 🔑 Key Levels tab's (`key_levels_tab`): the closed-bar half is
built once per `levels_session` in a background thread and every request ranks
it against ONE universe snapshot. `MEMO_TTL_SEC` is cache freshness, never a
rule. A background build hands the names still missing history to ONE paced
filler thread (`ath_history.fill`), never on a request.

WRITES NOTHING itself (the filler writes `ath_history` only). UNMEASURED: no
study in this app measures names at an all-time high forward; the order is a
distance and a date, and nothing gates, pushes, sizes or enters on it.
"""
from __future__ import annotations

import logging
import threading
import time
from datetime import date, datetime
from typing import Optional

import numpy as np

from chart_maps import ath_history as AH
from chart_maps import key_levels_tab as KLT
from supply_demand import key_levels as KL
from supply_demand.zone_edge import NEW_HIGH_TOL

log = logging.getLogger("chart_maps.ath_tab")

MARK = "\U0001F3D4️"            # 🏔️ (VS16 — FE literal must match)
SLIP_MARK = "↘️"           # ↘️
MEASURED = False
AT_ATH_TOL = NEW_HIGH_TOL            # HIS CALL #1 — "at" = print >= AT_ATH_TOL x the high
BAND_PCT = round((1.0 - AT_ATH_TOL) * 100.0, 2)   # every sentence prints this, never a typed number
SLIP_LOOKBACK_SESSIONS = 21          # HIS CALL #2 — the lid-break "does not hold" window
SMA_DAYS = 50
MEMO_TTL_SEC = 60 * 60               # cache freshness, NOT a rule
SORT_SLIPPING = "slipping"
AT_ATH_LABEL = f"{MARK} At ATH"
SLIPPING_LABEL = f"{SLIP_MARK} Slipping"
GROUP_AT, GROUP_SLIP = "at_ath", "slipping"
GROUP_52W_ONLY, GROUP_REST = "at_52w_only", "rest"
COUNT_KEYS = ("scanned", "at_ath", "at_ath_proven", "through_today", "slipping",
              "slip_from_ath", "slip_from_high_since", "slip_from_52w", "slip_above_sma50",
              "at_52w_only", "rest", "stale", "no_print", "no_bars", "history_pending",
              "history_short", "split_refetch")
PENDING_STATUSES = ("history_pending", "history_split")

_BASIS = KLT._BASIS

_memo: dict = {}                # (session_iso, ukey) -> entry
_warming: set = set()
_lock = threading.Lock()
_filling = False
_fill_errors: dict = {}         # SYM -> session_iso of the fill pass whose fetch failed


def _band_word() -> str:
    return f"{round((1.0 - AT_ATH_TOL) * 100.0, 2):g}%"


NOTE = (f"{MARK} UNMEASURED — no study in this app says a stock at its all-time high keeps rising "
        "or that one slipping under a recent high comes back. The order is a distance and a date, "
        "not a ranking of setups; nothing here gates a scan, pushes a phone, sizes a position or "
        "enters a lane. All-time means the full listed history: a name whose history starts after "
        "its listing — or that has no listing date on file — says 'high since' its first bar and is "
        "never called all-time. Bars from an earlier listing under the same ticker are cut where "
        "a curated cut (a first session or a rename on file) or a month-long gap in the ticker's "
        "own history proves them; a history that reaches back before the listing date is never "
        "called all-time either.")
WARMING_NOTE = (f"{MARK} Reading every name's highs from the cached daily bars — the charts appear "
                "here as soon as it lands; you don't need to refresh.")
EMPTY_NOTE_AT = (f"{MARK} No name trades at, or within {BAND_PCT:g}% of, its all-time high (or "
                 "the high since its first bar) right now — the line above says where they went.")
EMPTY_NOTE_SLIP = (f"{SLIP_MARK} No name set a high on record or a 52-week high in the last "
                   f"{SLIP_LOOKBACK_SESSIONS} sessions and trades more than {BAND_PCT:g}% under it "
                   "right now.")


def session_for(now: datetime) -> date:
    return KL.levels_session(now)


def _ukey(universe) -> str:
    return KLT._ukey(universe)


# ---------------------------------------------------------------------------
# completeness — may this name say "ATH"?
# ---------------------------------------------------------------------------
def completeness(first_bar: Optional[str], first_is_month: bool, listed: Optional[str]) -> str:
    """"complete" | "history_short" | "bars_before_listing" | "no_listing_date".
    PURE. The first bar must sit on the listing, within `ipo.BAR_SLACK_DAYS`
    (a monthly first bar: anywhere from the listing month's first day).

    "complete" here is necessary, NOT sufficient: `closed_read` calls a name
    proven all-time only when the stored monthly history (`ath_history`) is
    read and good too — the 2-year daily frame alone never proves it (a frame
    that starts on the listing date could still be a cache that simply begins
    there)."""
    from datetime import timedelta
    from chart_maps.ipo import BAR_SLACK_DAYS
    if not listed:
        return "no_listing_date"
    try:
        L = date.fromisoformat(str(listed)[:10])
        F = date.fromisoformat(str(first_bar)[:10])
    except (TypeError, ValueError):
        return "no_listing_date" if not first_bar else "history_short"
    hi = L + timedelta(days=BAR_SLACK_DAYS)
    lo = L.replace(day=1) if first_is_month else L - timedelta(days=BAR_SLACK_DAYS)
    if F > hi:
        return "history_short"
    if F < lo:
        return "bars_before_listing"
    return "complete"


def monthly_reaches_listing(sym: str, doc_first: Optional[str], listed: Optional[str]) -> bool:
    """Does the stored MONTHLY history itself reach the listing? PURE.
    `completeness(doc_first, True, listed) == "complete"`, or — for a curated
    `symbols.first_session` only — the monthly history starts the month right
    after the listing month: `prices._cut_foreign_head` drops the listing
    month's own monthly bar by construction (its stamp, the 1st, precedes a
    mid-month first session), and the daily frame covers those days."""
    from sepa import symbols
    if not doc_first or not listed:
        return False
    if completeness(doc_first, True, listed) == "complete":
        return True
    fs = symbols.first_session(sym)
    if not fs or str(fs)[:10] != str(listed)[:10]:
        return False
    try:
        L = date.fromisoformat(str(listed)[:10])
    except ValueError:
        return False
    nxt = date(L.year + (L.month == 12), (L.month % 12) + 1, 1)
    return str(doc_first)[:7] == nxt.isoformat()[:7]


def since_text(first_bar: Optional[str], first_is_month: bool) -> str:
    fb = str(first_bar or "")
    return fb[:7] if first_is_month else fb[:10]


def listed_for(sym: str, listing_map: Optional[dict]) -> Optional[str]:
    """The listing of THIS security: the curated `symbols.first_session`
    (WOLF post-reorg, SPCX, SOLS) else the profile listing date."""
    from sepa import symbols
    fs = symbols.first_session(sym)
    if fs:
        return fs
    v = (listing_map or {}).get(sym)
    return str(v)[:10] if v else None


# ---------------------------------------------------------------------------
# closed_read — the closed half for one name (PURE)
# ---------------------------------------------------------------------------
def _sessions_after(days, iso: Optional[str]) -> Optional[int]:
    if not iso or len(iso) < 10:
        return None
    try:
        d = date.fromisoformat(iso[:10])
    except ValueError:
        return None
    return int(sum(1 for x in days if x > d))


def _split_ok(closed, days_idx, doc: dict) -> bool:
    """The closed frame's max high inside `doc.check_month` equals
    `doc.check_high` to the cent; passes when the frame has no bar there."""
    cm = str(doc.get("check_month") or "")
    ch = KL._f(doc.get("check_high"))
    if not cm or ch is None:
        return False
    mask = np.asarray([d.strftime("%Y-%m") == cm for d in days_idx])
    if not mask.any():
        return True
    fh = KL._f(closed["high"][mask].max())
    return fh is not None and abs(fh - ch) <= KL._HALF_CENT


def closed_read(sym: str, df, doc: Optional[dict], listed: Optional[str], session: date,
                *, now_ts: Optional[float] = None) -> Optional[dict]:
    """The closed-bar half for one name. None = no closed bars (`no_bars`)."""
    from sepa import entry_exit, symbols
    from supply_demand import quick_bounce as QB
    sym = str(sym or "").upper()
    now_ts = float(time.time() if now_ts is None else now_ts)
    closed = KL.closed_frame(df, session) if df is not None else None
    if closed is None or len(closed) == 0:
        return None

    # 2 — the stored summary's state
    first_frame = KL._norm_index(closed)[0].date().isoformat()
    refetch = AH.needs_fetch(doc, sym, now=now_ts, frame_first=first_frame)
    if refetch is not None:
        doc_state = "pending"
    elif doc.get("status") == "empty":
        doc_state = "empty"
    elif doc.get("status") != "ok":
        doc_state, refetch = "pending", "missing"
    elif AH.no_overlap(doc, first_frame):
        # the doc's check month ends before the frame starts: unverifiable, so
        # frame-only; refetched once older than REFETCH_MIN_AGE_SEC
        doc_state = "pending"
    else:
        idx0 = KL._norm_index(closed)
        if _split_ok(closed, idx0, doc):
            doc_state = "ok"
        else:
            doc_state = "split"
            age = now_ts - float(doc.get("fetched_at") or 0.0)
            refetch = "split" if age >= AH.REFETCH_MIN_AGE_SEC else None
    ok = doc_state == "ok"

    # 3 — the last-hole cut reaches the daily frame too (never a spliced rename)
    if ok and doc.get("cut_from") and not symbols.former_names(sym):
        import pandas as pd
        keep = np.asarray(KL._norm_index(closed).normalize() >= pd.Timestamp(str(doc["cut_from"])))
        closed = closed[keep]
        if len(closed) == 0:
            return None

    idx = KL._norm_index(closed)
    days = [d.date() for d in idx]
    highs = closed["high"].to_numpy(dtype=float)
    if not np.isfinite(highs).any():
        return None
    i_hi = int(np.nanargmax(highs))
    frame_hi = float(highs[i_hi])
    frame_hi_date = days[i_hi].isoformat()

    # 5 — the higher of the frame and the stored history
    doc_hi = KL._f(doc.get("hi")) if ok else None
    if doc_hi is not None and frame_hi < doc_hi - KL._HALF_CENT:
        hi_closed, hi_date, hi_is_month = doc_hi, str(doc.get("hi_month") or ""), True
    else:
        hi_closed, hi_date, hi_is_month = max(frame_hi, doc_hi or 0.0), frame_hi_date, False

    # 6 — how far back the history reaches
    first_daily = days[0].isoformat()
    if ok and doc.get("first_bar") and str(doc["first_bar"])[:10] <= first_daily:
        first_bar, first_is_month = str(doc["first_bar"])[:10], True
    else:
        first_bar, first_is_month = first_daily, False
    status = completeness(first_bar, first_is_month, listed)
    if ok and status == "complete" and not monthly_reaches_listing(sym, doc.get("first_bar"),
                                                                    listed):
        # the daily frame reaches the listing but the monthly history does not:
        # never proven from the 2-year frame (critic 2026-09-29)
        status = "history_short"
    if not ok:
        # NEVER proven from the 2-year daily frame alone: proof needs the
        # monthly history read and good (critic 2026-09-29).
        status = "history_split" if doc_state == "split" else "history_pending"
    proven = status == "complete"
    since = since_text(first_bar, first_is_month)

    # 7 — the 52-week high (omitted under YEAR_BARS)
    w52 = None
    for m in KL.period_levels(closed, session, ("year",)):
        if m.get("kind") == "high":
            w52 = {"price": float(m["price"]), "set_on": m.get("set_on")}

    # 8 — 50-day, turnover, the last close
    sma50 = entry_exit._sma(closed, SMA_DAYS)
    adv50 = QB.avg_dollar_vol(closed)
    ref_close = KL._f(closed["close"].iloc[-1])
    last_d = days[-1]
    stale_note = None
    need = KL.prev_market_day(session)
    if last_d < need:
        stale_note = (f"ATH needs bars through {need.isoformat()}; cached bars end "
                      f"{last_d.isoformat()}")

    # 9 — the look-back window, on closed sessions
    n = len(days)
    lookback_start = (days[-SLIP_LOOKBACK_SESSIONS] if n >= SLIP_LOOKBACK_SESSIONS
                      else days[0]).isoformat()
    return {"symbol": sym, "hi_closed": float(hi_closed), "hi_date": hi_date,
            "hi_date_is_month": hi_is_month, "first_bar": first_bar,
            "first_is_month": first_is_month, "since": since, "listed": listed,
            "status": status, "proven": proven,
            "label": "ATH" if proven else f"High since {since}",
            "w52": w52,
            "w52_sessions_ago": _sessions_after(days, (w52 or {}).get("set_on")),
            "hi_sessions_ago": None if hi_is_month else _sessions_after(days, hi_date),
            "sma50": sma50, "adv50": adv50, "ref_close": ref_close,
            "last_date": last_d.isoformat(), "stale_note": stale_note,
            "lookback_start": lookback_start, "doc_state": doc_state, "refetch": refetch}


# ---------------------------------------------------------------------------
# classify — per request (PURE)
# ---------------------------------------------------------------------------
def _pct(a, b) -> Optional[float]:
    try:
        v = round((float(a) / float(b) - 1.0) * 100.0, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    return v if np.isfinite(v) else None


def _word(kind: str, read: dict) -> str:
    if kind == "52w":
        return "52-week high"
    return "all-time high" if read.get("proven") else f"high since {read.get('since')}"


def classify(read: dict, row: Optional[dict], *, now: datetime, session: date) -> tuple:
    """(group, detail). group in GROUP_AT / GROUP_SLIP / GROUP_52W_ONLY /
    GROUP_REST; detail is the served `tile.ath` block (+ `hi_prior`)."""
    now_et = KL._et(now)
    px, basis, tape = KL.anchor_read(row, now_et, session, read.get("ref_close"))
    ph = KL.phase(now_et, session)
    day_hi = KL._pos((row or {}).get("high")) if ph in ("rth", "close") else None
    hi_prior = float(read["hi_closed"])
    hi_live = max(hi_prior, day_hi or 0.0, px)
    high_today = hi_live > hi_prior + KL._HALF_CENT
    through = px > hi_prior + KL._HALF_CENT
    session_iso = session.isoformat()
    kind_of_ath = "ath" if read.get("proven") else "high"

    w52 = read.get("w52")
    w52_live = w52_today = w52_set = None
    if w52:
        w52_live = max(float(w52["price"]), day_hi or 0.0)
        w52_today = day_hi is not None and day_hi > float(w52["price"]) + KL._HALF_CENT
        w52_set = session_iso if w52_today else w52.get("set_on")

    group = None
    ref = None
    if through or px >= AT_ATH_TOL * hi_live:
        group = GROUP_AT
    else:
        if high_today:
            ref = (kind_of_ath, hi_live, session_iso, 0)
        elif w52:
            if w52_today or (w52_set and w52_set >= read["lookback_start"]):
                kind = kind_of_ath if abs(w52_live - hi_live) <= KL._HALF_CENT else "52w"
                ref = (kind, w52_live, w52_set, 0 if w52_today else read.get("w52_sessions_ago"))
        elif not read.get("hi_date_is_month") and str(read.get("hi_date")) >= read["lookback_start"]:
            ref = (kind_of_ath, hi_prior, read["hi_date"], read.get("hi_sessions_ago"))
        if ref and px < AT_ATH_TOL * ref[1]:
            group = GROUP_SLIP
        elif ref:
            group = GROUP_52W_ONLY
        else:
            group = GROUP_REST

    sma50 = read.get("sma50")
    slip = None
    if group == GROUP_SLIP:
        slip = {"from": ref[0], "price": round(float(ref[1]), 4), "date": ref[2],
                "sessions_ago": ref[3], "pct": _pct(px, ref[1])}
    detail = {
        "group": group, "proven": bool(read.get("proven")), "status": read.get("status"),
        "label": read.get("label"), "since": read.get("since"), "listed": read.get("listed"),
        "high": round(hi_live, 4),
        "high_date": session_iso if high_today else read.get("hi_date"),
        "high_date_is_month": False if high_today else bool(read.get("hi_date_is_month")),
        "high_today": bool(high_today),
        "hi_prior": round(hi_prior, 4), "prior_date": read.get("hi_date"),
        "pct_from_high": _pct(px, hi_live),
        "through_prior_pct": _pct(px, hi_prior) if through else None,
        "w52": (None if not w52 else {"price": round(w52_live, 4), "date": w52_set,
                                      "today": bool(w52_today)}),
        "pct_from_52w": _pct(px, w52_live) if w52 else None,
        "sma50": None if sma50 is None else round(float(sma50), 4),
        "above_sma50": None if sma50 is None else bool(px > sma50),
        "px": round(float(px), 4), "basis": basis, "tape": tape, "slip": slip,
    }
    detail["text"] = _badge_text(detail)
    return group, detail


def _badge_text(a: dict) -> str:
    word = "all-time high" if a["proven"] else f"high since {a['since']}"
    tail = "" if a["proven"] else " — not proven all-time"
    if a["group"] == GROUP_SLIP and a.get("slip"):
        s = a["slip"]
        sw = "52-week high" if s["from"] == "52w" else word
        when = "set today" if s.get("sessions_ago") == 0 else (
            f"set {s['date']} ({s['sessions_ago']} sessions ago)")
        return (f"{SLIP_MARK} {abs(s['pct'] or 0.0):.2f}% under the {sw} "
                f"{s['price']:.2f} {when}" + ("" if s["from"] == "52w" else tail))
    if a.get("through_prior_pct") is not None:
        return (f"{MARK} new {word} today · {a['through_prior_pct']:+.2f}% over "
                f"{a['hi_prior']:.2f} ({a['prior_date']})" + tail)
    return (f"{MARK} {abs(a['pct_from_high'] or 0.0):.2f}% under the {word} "
            f"{a['high']:.2f} ({a['high_date']})" + tail)


# ---------------------------------------------------------------------------
# order + rank
# ---------------------------------------------------------------------------
def at_key(r) -> tuple:
    a = r["ath"]
    return (-(a["px"] / a["hi_prior"] - 1.0), r["symbol"])


def slip_key(r) -> tuple:
    s = r["ath"]["slip"]
    return (-date.fromisoformat(str(s["date"])[:10]).toordinal(), abs(s["pct"] or 0.0),
            r["symbol"])


def rank(entry: dict, raw_snaps: dict, *, now: datetime, group: str) -> tuple:
    """(rows of `group`, counts). PURE. First match wins: no read -> no_bars;
    stale note / no ref_close -> stale; no snapshot row -> no_print; verify
    mismatch -> stale; unverifiable -> no_print; no anchor -> no_print; then
    `classify`. scanned == at_ath + slipping + at_52w_only + rest + stale +
    no_print + no_bars."""
    now_et = KL._et(now)
    session = date.fromisoformat(str(entry["session"]))
    raw_snaps = raw_snaps if isinstance(raw_snaps, dict) else {}
    counts = {k: 0 for k in COUNT_KEYS}
    rows: list = []
    reads = entry.get("reads") or {}
    for sym in entry.get("syms") or []:
        counts["scanned"] += 1
        rd = reads.get(sym)
        if not rd:
            counts["no_bars"] += 1
            continue
        if rd.get("refetch") == "split":
            counts["split_refetch"] += 1
        if rd.get("stale_note") or rd.get("ref_close") is None:
            counts["stale"] += 1
            continue
        row = KL.row_or_none(raw_snaps.get(sym))
        if row is None:
            counts["no_print"] += 1
            continue
        sentence, verified = KL.verify_last(rd["ref_close"], rd.get("last_date"), row)
        if sentence:
            counts["stale"] += 1
            continue
        if not verified:
            counts["no_print"] += 1
            continue
        px, _basis, _tape = KL.anchor_read(row, now_et, session, rd["ref_close"])
        if px is None:
            counts["no_print"] += 1
            continue
        g, a = classify(rd, row, now=now_et, session=session)
        counts[g] += 1
        if rd.get("status") in PENDING_STATUSES:
            counts["history_pending"] += 1
        elif rd.get("status") == "history_short":
            counts["history_short"] += 1
        if g == GROUP_AT:
            counts["at_ath_proven"] += int(a["proven"])
            counts["through_today"] += int(a["through_prior_pct"] is not None)
        elif g == GROUP_SLIP:
            frm = a["slip"]["from"]
            if frm == "52w":
                counts["slip_from_52w"] += 1
            elif frm == "ath":                  # proven all-time only
                counts["slip_from_ath"] += 1
            else:                               # "high": the high since the first bar
                counts["slip_from_high_since"] += 1
            counts["slip_above_sma50"] += int(bool(a["above_sma50"]))
        if g == group:
            rows.append({"symbol": sym, "ref_close": rd["ref_close"], "adv50": rd.get("adv50"),
                         "ath": a})
    rows.sort(key=slip_key if group == GROUP_SLIP else at_key)
    return rows, counts


# ---------------------------------------------------------------------------
# words
# ---------------------------------------------------------------------------
def _n(x) -> str:
    return f"{int(x or 0):,}"


def header_text(counts: dict, *, group: str, ph, history: Optional[dict]) -> str:
    """The served line above the grid. A proven all-time high and a 'high
    since the first bar' are ALWAYS counted apart — the group total never
    calls an unproven name all-time (critic 2026-09-29)."""
    c = counts or {}
    basis = _BASIS.get(ph, _BASIS[None])
    band = _band_word()
    at, proven = int(c.get("at_ath") or 0), int(c.get("at_ath_proven") or 0)
    tail = (f"{_n(c.get('dropped_thin'))} under the liquidity floor, {_n(c.get('no_turnover'))} "
            f"with no turnover to check; showing {_n(c.get('shown'))}.")
    if group == GROUP_SLIP:
        text = (f"{SLIP_MARK} {_n(c.get('slipping'))} names set a high on record or a 52-week "
                f"high in the last {SLIP_LOOKBACK_SESSIONS} sessions and now trade more than "
                f"{band} under it — freshest high first, smallest drop breaks ties, on the "
                f"{basis}. {_n(c.get('slip_from_ath'))} slipped from a proven all-time high "
                f"(full listed history), {_n(c.get('slip_from_high_since'))} from the high since "
                f"their first bar (not proven all-time), {_n(c.get('slip_from_52w'))} from a "
                f"52-week high only; {_n(c.get('slip_above_sma50'))} still above the "
                f"{SMA_DAYS}-day average. Not listed here: {_n(at)} at their high "
                f"({AT_ATH_LABEL}: {_n(proven)} proven all-time, {_n(at - proven)} high since "
                f"their first bar), {_n(c.get('at_52w_only'))} within {band} of a 52-week high, "
                f"{_n(c.get('rest'))} further from both, {_n(c.get('stale'))} with daily bars "
                f"behind, {_n(c.get('no_print'))} with no snapshot print to check. " + tail)
    else:
        text = (f"{MARK} {_n(at)} names trade at, or within {band} of, their high — "
                f"{_n(proven)} at a proven all-time high (full listed history), "
                f"{_n(at - proven)} at the high since their first bar (not proven all-time); "
                f"{_n(c.get('through_today'))} through it today. Ordered by % from the prior "
                f"high on the {basis}, through-today first. Not listed here: "
                f"{_n(c.get('slipping'))} slipping under a high set in the last "
                f"{SLIP_LOOKBACK_SESSIONS} sessions ({SLIPPING_LABEL}), "
                f"{_n(c.get('at_52w_only'))} at a 52-week high that is not their high on "
                f"record, {_n(c.get('rest'))} further from both, "
                f"{_n(c.get('stale'))} with daily bars behind, {_n(c.get('no_print'))} with no "
                f"snapshot print to check. " + tail)
    h = history or {}
    if int(h.get("pending") or 0) > 0:
        n_wait = int(h.get("pending") or 0)
        text += (f" {_n(n_wait)} {'name' if n_wait == 1 else 'names'} waiting for history"
                 f"{' (loading in the background now)' if h.get('filling') else ''} — full "
                 f"history read for {_n(h.get('read'))} of {_n(c.get('scanned'))}; until it "
                 "lands they read 'high since' their cached bars and are never called all-time.")
    return text


def ready_block(counts: dict, *, now: datetime, session: date, ph, group: str, built_at,
                history: Optional[dict]) -> dict:
    return {"state": "ready", "session": session.isoformat(), "phase": ph, "group": group,
            "counts": dict(counts),
            "header": header_text(counts, group=group, ph=ph, history=history),
            "note": NOTE, "built_at": None if built_at is None else str(built_at),
            "measured": MEASURED, "band_pct": BAND_PCT,
            "lookback_sessions": SLIP_LOOKBACK_SESSIONS,
            "history": {"read": int((history or {}).get("read") or 0),
                        "pending": int((history or {}).get("pending") or 0),
                        "filling": bool((history or {}).get("filling"))}}


def warming_block(*, now: datetime, group: str) -> dict:
    session = session_for(now)
    return {"state": "warming", "session": session.isoformat(),
            "phase": KL.phase(KL._et(now), session), "group": group, "counts": None,
            "header": WARMING_NOTE, "note": NOTE, "built_at": None, "measured": MEASURED,
            "band_pct": BAND_PCT, "lookback_sessions": SLIP_LOOKBACK_SESSIONS,
            "history": {"read": None, "pending": None, "filling": bool(_filling)}}


# ---------------------------------------------------------------------------
# tile words (served; the FE prints them verbatim)
# ---------------------------------------------------------------------------
def tile_badge(r: dict) -> dict:
    a = r["ath"]
    return {"text": a["text"], "tone": "warn" if a["group"] == GROUP_SLIP else "good"}


def _pct_txt(v) -> str:
    return "—" if v is None else f"{v:+.2f}%"


def tile_stats(r: dict) -> list:
    a = r["ath"]
    w = a.get("w52")
    stats = [{"k": a["label"], "v": f"{a['high']:.2f} · {a['high_date']} · "
                                    f"{_pct_txt(a['pct_from_high'])}"},
             {"k": "52w high", "v": "—" if not w else
              f"{w['price']:.2f} · {w['date']} · {_pct_txt(a['pct_from_52w'])}"}]
    sma = a.get("sma50")
    if sma is None:
        sv = "—"
    else:
        side = "above" if a["above_sma50"] else "below"
        sv = f"{side} {sma:.2f} ({_pct_txt(_pct(a['px'], sma))})"
    stats.append({"k": f"{SMA_DAYS}-day", "v": sv})
    if a["proven"]:
        hv = f"since listing {a['listed']}"
    elif a["status"] in PENDING_STATUSES:
        hv = f"since {a['since']} · full history not read yet"
    elif not a.get("listed"):
        hv = f"since {a['since']} (no listing date)"
    else:
        hv = f"since {a['since']} (listed {a['listed']})"
    stats.append({"k": "History", "v": hv})
    return stats


def tile_lines(r: dict) -> list:
    """ONE line: the reference high (so an old far-away ATH never squashes a
    chart). `neutral` — unowned, always drawn."""
    a = r["ath"]
    ath_label = "ATH" if a["proven"] else f"HIGH SINCE {a['since']}"
    if a["group"] == GROUP_SLIP and a.get("slip"):
        s = a["slip"]
        return [{"price": float(s["price"]), "label": "52W" if s["from"] == "52w" else ath_label,
                 "tone": "neutral"}]
    return [{"price": float(a["high"]), "label": ath_label, "tone": "neutral"}]


def why_text(r: dict) -> str:
    a = r["ath"]
    badge = a["text"]
    for m in (MARK, SLIP_MARK):
        if badge.startswith(m):
            badge = badge[len(m):].strip()
    w = a.get("w52")
    w_txt = "52w —" if not w else f"52w {w['price']:.2f} ({_pct_txt(a['pct_from_52w'])})"
    if a.get("above_sma50") is None:
        s_txt = f"no {SMA_DAYS}-day"
    else:
        s_txt = f"{'above' if a['above_sma50'] else 'below'} the {SMA_DAYS}-day"
    return f"{a['px']:.2f} · {badge} · {w_txt} · {s_txt}"


# ---------------------------------------------------------------------------
# memo — a copy of key_levels_tab's, same guards
# ---------------------------------------------------------------------------
def build(universe: str, session: date, *, universe_fn=None, frames_fn=None, history_fn=None,
          listing_fn=None) -> dict:
    """entry = {syms, reads: {SYM: closed_read}, pending: [(sym, reason)],
    history: {read, pending}, built_ts, built_at, session, ukey}. ONE cached
    frames read, ONE history read, ONE listing read."""
    ukey = _ukey(universe)
    if universe_fn is None:
        from supply_demand import demand_reentry as D
        syms_raw = D._resolve_universe(ukey)[0]
    else:
        syms_raw = universe_fn(ukey)
    syms: list = []
    seen: set = set()
    for s in syms_raw or []:
        s = str(s or "").strip().upper()
        if s and s not in seen:
            seen.add(s)
            syms.append(s)
    if frames_fn is None:
        from sepa import prices
        frames_fn = prices.bulk_cached_frames
    frames = frames_fn(syms) or {}
    if syms and not frames:
        raise RuntimeError(f"ath tab: the price-cache read returned no frames for "
                           f"{len(syms):,} names — not memoising an empty read")
    docs = (history_fn or AH.read_many)(syms) or {}
    if listing_fn is None:
        from sepa import ipo_age
        listing_fn = ipo_age.listing_dates_map
    listing = listing_fn(syms) or {}
    now_ts = time.time()
    reads: dict = {}
    pending: list = []
    n_ok = 0
    for sym in syms:
        df = frames.get(sym)
        if df is None:
            continue
        try:
            rd = closed_read(sym, df, docs.get(sym), listed_for(sym, listing), session,
                             now_ts=now_ts)
        except Exception as exc:                                # noqa: BLE001
            log.debug("ath tab: %s build failed: %s", sym, exc)
            continue
        if rd is None:
            continue
        reads[sym] = rd
        n_ok += int(rd["doc_state"] == "ok")
        if rd.get("refetch"):
            pending.append((sym, rd["refetch"]))
    return {"syms": syms, "reads": reads, "pending": pending,
            "history": {"read": n_ok, "pending": len(pending)},
            "built_ts": now_ts,
            "built_at": datetime.fromtimestamp(now_ts, tz=KL.ET).isoformat(timespec="seconds"),
            "session": session.isoformat(), "ukey": ukey}


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


def _invalidate(_n_done=None) -> None:
    """The filler's progress hook: the next request serves the held entry plus
    ONE background rebuild."""
    with _lock:
        for e in _memo.values():
            e["built_ts"] = 0


def _maybe_fill(pending, *, session_iso: Optional[str] = None) -> bool:
    """Hand the names still missing history to ONE module-wide filler thread.
    A name whose fetch failed in this session's pass waits for the next
    session (so a provider that has nothing never loops a rebuild)."""
    global _filling
    names = [s for s, _r in (pending or [])
             if not (session_iso and _fill_errors.get(s) == session_iso)]
    if not names:
        return False
    with _lock:
        if _filling:
            return False
        _filling = True

    def _work():
        global _filling
        try:
            counts = AH.fill(names, now=datetime.now(KL.ET), on_progress=_invalidate)
            for s in counts.get("error_symbols") or []:
                _fill_errors[s] = session_iso
            log.info("ath tab: history fill %s", {k: v for k, v in counts.items()
                                                  if k != "error_symbols"})
        except Exception as exc:                                # noqa: BLE001
            log.warning("ath tab: history fill failed: %s", exc)
        finally:
            with _lock:
                _filling = False

    _spawn(_work, "ath-history-fill")
    return True


def filling() -> bool:
    return bool(_filling)


def _warm(key: tuple, universe: str, session: date) -> None:
    def _work():
        try:
            entry = build(universe, session)
            with _lock:
                newest = max((k[0] for k in _memo), default=key[0])
                if key[0] < newest:
                    log.info("ath tab: dropped a late %s build (memo holds %s)", key[0], newest)
                    return
                for k in [k for k in _memo if k[0] < key[0]]:
                    _memo.pop(k, None)
                _memo[key] = entry
            _maybe_fill(entry.get("pending"), session_iso=key[0])
        except Exception as exc:                                # noqa: BLE001
            log.warning("ath tab: build failed for %s: %s", key, exc)
        finally:
            with _lock:
                _warming.discard(key)

    with _lock:
        if key in _warming:
            return
        _warming.add(key)
    _spawn(_work, f"ath-tab-{key[0]}-{key[1]}")


def cached_or_warm(universe, *, now: datetime, sync: bool = False) -> dict:
    """{"state": "ready"|"warming", "entry"} — `key_levels_tab.cached_or_warm`'s
    semantics. `sync=True` builds inline and never starts the filler."""
    session = KL.levels_session(now)
    ukey = _ukey(universe)
    key = (session.isoformat(), ukey)
    with _lock:
        entry = _memo.get(key)
    fresh = entry is not None and (time.time() - float(entry.get("built_ts") or 0)) < MEMO_TTL_SEC
    if fresh:
        return {"state": "ready", "entry": entry}
    if sync:
        entry = build(ukey, session)
        with _lock:
            _memo[key] = entry
        return {"state": "ready", "entry": entry}
    _warm(key, ukey, session)
    if entry is not None:
        return {"state": "ready", "entry": entry}
    return {"state": "warming", "entry": None}
