"""📅 Since the report — a FACT column for the 🚀 Explosive Growth and 📈 Bonde boards.

Ajay 2026-09-21, asked and answered: *"Should the boards print a 'since
qualifying filing' column?"* → **Yes**.

WHY IT EXISTS, in his words. The research run of 2026-09-21
(`docs/research/board_growth_2026_09_21.md`) measured both boards against the
date the market learned the number. The typical name on these boards had
already had its run before the board could see it: the growth board's median
member gained +46.40% in the 126 sessions BEFORE its qualifying filing and has
LOST 2.21% since, with only 8 of 20 positive; the visible Bonde board has no
"before" leg worth the name at all (+8.19% against the scan universe's +8.14%)
and its median is −4.41% since. Nothing on either board said so. This column
is that "since" leg, per name, on the surface he actually reads.

WHAT IT IS. A return between two dates. It is not a read, not a signal, not a
score and not a gate: it changes no sort, no filter, no ordering, no threshold
and no alert (Rule #10). It has never been measured forward and it claims
nothing about what the name does next.

THE DATE IS THE REPORT DATE, NOT THE SEC FILING DATE. The anchor comes from
this app's own earnings calendar (`sepa/earnings_watch`, Mongo
`earnings_calendar`, field `last_report.date` — yfinance), which is the date
the company REPORTED. The 2026-09-21 study measured from the SEC 10-Q/10-K
`filed` date. On CRDO the two are one day apart (reported 2026-09-01, filed
2026-09-02): immaterial over a 126-session window, but they are different
dates, and no surface in this package calls them the same thing.

ONE ENGINE PER CONCEPT, and every one of them already existed:
  * the calendar            — `sepa.earnings_watch.last_report_map` (ONE find)
  * the price frames        — `sepa.prices.bulk_cached_frames` (ONE find, and
                              it can NEVER fetch: a cold name is a blank cell)
  * the BMO/AMC anchor rule — `sepa.earnings_picks.reaction_read`
  * the session clock       — `sepa.prices.trade_session` on `EW._today_et()`
  * the freshness label     — `sepa.bonde_picks.SURPRISE_STALE_DAYS` (157 d)
                              and `earnings_watch.REFETCH_AFTER_SEC` (3 d)

O(1) READS PER BOARD. Two bulk queries for the whole board, never a per-name
loop — the AMD lesson of 2026-09-21 (80 tiles × 1 call = 65 s; the fix was one
snapshot per board). Latency is measured in-container and written into
`docs/sepa/since_report_column_2026_09_21.md`; no number here is estimated.

THE IN-PROGRESS BAR. The price cache is NOT closed-bars-only during the
session: `crontab:407` runs `vcp-watch` hourly 09:00–16:00 ET and
`prices.patch_latest_closes` APPENDS today's snapshot bar and rewrites it in
place. Read at 11:00 that bar is a partial print, not a close. So during
`premarket` / `rth` a today-dated last bar is DROPPED here before anything is
measured, exactly the reading `prices.with_today_bar` already applies; after
16:00 it stays. And a window of zero length — the reaction close IS the latest
closed bar — is BLANK, never `+0.0%`, because "unchanged" and "no session has
closed yet" are different facts.

A BLANK IS NEVER A ZERO. Every refusal carries a reason from `REASONS` and the
surface prints it in words. The research artifact itself is NOT read here (it
is research, Rule #10): the served numbers live in `RUN_MEASURED` below and a
test pins them field-for-field against it.
"""
from __future__ import annotations

import logging
import math
from datetime import date
from typing import Optional

from sepa import earnings_watch as EW                       # the ONE calendar
from sepa import prices as P                                # the ONE price cache
from sepa.earnings_picks import reaction_read               # the ONE BMO/AMC rule
from sepa.bonde_picks import SURPRISE_STALE_DAYS            # the app's 157-day label

log = logging.getLogger("sepa.since_report")

MINUS = "−"                       # U+2212, the house minus on every surface

DATE_BASIS = "report"
DATE_BASIS_NOTE = (
    "The date is the REPORT date — the most recent past report on the app's earnings "
    "calendar (yfinance via sepa/earnings_watch, field last_report.date) — NOT the SEC "
    "10-Q/10-K filing date the 2026-09-21 study measured from. On CRDO the two are one "
    "day apart (reported 2026-09-01, filed 2026-09-02); immaterial over 126 sessions, "
    "but they are different dates and no surface here calls them the same thing."
)
DOC = "docs/research/board_growth_2026_09_21.md"
SOURCE = ("yfinance (Yahoo Finance) via sepa.earnings_watch — "
          "verify on EarningsWhispers; dates can shift")

REASONS = ("no_report", "bad_date", "report_predates_period", "not_traded_yet",
           "no_bars", "before_first_bar", "insufficient_history")

CALENDAR_STALE_SEC = EW.REFETCH_AFTER_SEC     # 3 d — the calendar's own refetch rule

# The 2026-09-21 research run's headline reads, in exactly one place.
# Pinned field-for-field against the research artifact by
# tests/test_since_report.py — never retyped onto a surface.
RUN_MEASURED = {
    "run_date": "2026-09-21",
    "doc": DOC,
    "sessions_before": 126,
    "benchmark": "RSP",
    "growth": {"n": 21, "n_known": 20, "n_positive": 8,
               "pre_median_pct": 46.40, "pre_share_pos": 80.0,
               "since_median_pct": -2.21, "since_share_pos": 40.0},
    "bonde": {"n": 160, "n_known": 152, "n_positive": 57,
              "pre_median_pct": 8.19, "pre_share_pos": 66.4,
              "since_median_pct": -4.41, "since_share_pos": 37.5},
    "universe": {"n": 2090, "n_known": 1656, "n_positive": 514,
                 "pre_median_pct": 8.14, "pre_share_pos": 65.5,
                 "since_median_pct": -4.63, "since_share_pos": 31.0},
}

_ROW_KEYS = ("known", "pct", "report_date", "when", "anchor_date", "anchor_close",
             "as_of", "last_close", "sessions", "report_age_days", "stale_report",
             "calendar_fetched_at", "calendar_stale", "reason")


def _sgn(v, d: int = 2) -> str:
    """'+46.40' / '−2.21' — the same signed, unicode-minus rule `bonde._sgn`
    uses, so one board never prints a hyphen where the other prints a minus."""
    return f"{float(v):+.{d}f}".replace("-", MINUS)


def today_et() -> str:
    """The ET calendar date, from the calendar module's own clock. No second
    clock in this app."""
    return EW._today_et().date().isoformat()


def _iso(v) -> Optional[str]:
    """A real YYYY-MM-DD, or None. Never raises."""
    s = str(v or "")[:10]
    try:
        date.fromisoformat(s)
    except (TypeError, ValueError):
        return None
    return s


def _when(v) -> Optional[str]:
    s = str(v or "").upper().strip()
    return s if s in ("BMO", "AMC") else None


def unknown(reason: str = "no_report", **facts) -> dict:
    """The blank cell, fully shaped. Unknown is NOT zero and NOT "flat": every
    caller gets the same 14 keys so no surface has to guess which are missing."""
    out = {k: None for k in _ROW_KEYS}
    out["known"] = False
    out["reason"] = reason if reason in REASONS else "no_report"
    for k, v in facts.items():
        if k in _ROW_KEYS:
            out[k] = v
    out["known"] = False
    out["pct"] = None
    return out


def _calendar_facts(report: Optional[dict], report_date: Optional[str],
                    today: Optional[str]) -> dict:
    """The four freshness facts every branch carries — a LABEL, never a gate.

    `stale_report` mirrors the surprise leg on the very same calendar doc
    (`bonde_picks`, 157 days, "the label never changes the verdict").
    `calendar_stale` is the calendar's OWN refetch rule (3 days). Both are
    imported by name; neither is a number this module invented."""
    age = None
    if report_date and today:
        try:
            age = (date.fromisoformat(today) - date.fromisoformat(report_date)).days
        except (TypeError, ValueError):                         # pragma: no cover
            age = None
    fetched_at = (report or {}).get("fetched_at")
    fetched_iso = None
    cal_stale = None
    try:
        if fetched_at is not None:
            epoch = float(fetched_at)
            if math.isfinite(epoch) and epoch > 0:
                from datetime import datetime, timezone
                fetched_iso = datetime.fromtimestamp(
                    epoch, tz=timezone.utc).date().isoformat()
                import time as _t
                cal_stale = bool((_t.time() - epoch) > CALENDAR_STALE_SEC)
    except (TypeError, ValueError, OSError, OverflowError):
        fetched_iso, cal_stale = None, None
    return {
        "report_date": report_date,
        "when": _when((report or {}).get("when")),
        "report_age_days": age,
        "stale_report": (age > SURPRISE_STALE_DAYS) if age is not None else None,
        "calendar_fetched_at": fetched_iso,
        "calendar_stale": cal_stale,
    }


def read_one(report: Optional[dict], frame, today: str,
             period_end: Optional[str] = None,
             session: Optional[str] = None) -> dict:
    """PURE. Never raises. One row's cell.

    `report`  — one `last_report_map` value (or None).
    `frame`   — that symbol's cached daily frame (or None).
    `today`   — the ET calendar date, as a string.
    `period_end` — the quarter the board screened on (growth rows carry it;
                   Bonde rows do not, so the check is skipped there).
    `session` — `prices.trade_session` for the same clock, or None. It decides
                ONE thing: whether a today-dated last bar is a close or the
                hourly in-progress patch."""
    try:
        return _read_one(report, frame, today, period_end, session)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("since_report: read failed: %s", exc)
        return unknown("insufficient_history")


def _read_one(report, frame, today, period_end, session) -> dict:
    today = _iso(today)
    raw_date = (report or {}).get("date") if isinstance(report, dict) else None

    # 1. no report on file. Unknown — NOT "did not report", and not 0%.
    if not isinstance(report, dict) or not raw_date:
        return unknown("no_report")

    # 2. a date this app cannot read.
    report_date = _iso(raw_date)
    if not report_date:
        return unknown("bad_date", **_calendar_facts(report, None, today))

    facts = _calendar_facts(report, report_date, today)

    # 3. the calendar's newest report is for an OLDER quarter than the one the
    #    board screened on, so it is not the qualifying report. (Live case
    #    2026-09-21: one growth row's "latest report" was dated 2016-11-09.)
    pe = _iso(period_end)
    if pe and report_date < pe:
        return unknown("report_predates_period", **facts)

    # 4. dated in the future — there is nothing "since" yet.
    if today and report_date > today:
        return unknown("not_traded_yet", **facts)

    # 4b. THE IN-PROGRESS BAR. `crontab:407` patches today's partial bar into
    #     the cache hourly during the session; it is a print, not a close.
    #     The ONLY trim in this module, and it runs BEFORE the empty check so a
    #     frame holding nothing but today's partial reads `no_bars`.
    if frame is not None and len(frame) and today:
        try:
            if (frame.index[-1].date().isoformat() == today
                    and session in ("premarket", "rth")):
                frame = frame.iloc[:-1]
        except Exception as exc:                                # noqa: BLE001
            log.debug("since_report: session trim failed: %s", exc)

    # 5. no cached price history.
    if frame is None or len(frame) == 0:
        return unknown("no_bars", **facts)

    first_bar = frame.index[0].date().isoformat()
    last_bar = frame.index[-1].date().isoformat()

    # 6. the report predates this name's cached history entirely.
    if report_date < first_bar:
        return unknown("before_first_bar", **facts)

    # 7. the app's ONE BMO/AMC anchor rule. min_history=1 — this read wants
    #    `drift_since_pct`, not the 50-day volume leg.
    r = reaction_read(frame, report_date, facts["when"], min_history=1)
    if r is None:
        # Told apart so the tooltip can say WHICH refusal it was: the reaction
        # session simply has not printed yet, or the frame cannot anchor it.
        not_yet = (report_date >= last_bar
                   or (facts["when"] == "AMC" and report_date == last_bar))
        return unknown("not_traded_yet" if not_yet else "insufficient_history",
                       **facts)

    # WHERE the reaction bar sits, by DATE and never by timestamp. The cached
    # bars are not all stamped midnight — a live `price_cache` frame carries
    # 04:00:00 on its older rows (measured in the api container 2026-09-21:
    # CRDO's first bar is `2024-09-20 04:00:00`), so `index.get_loc(Timestamp
    # ('2026-09-02'))` raises KeyError on the real data and would blank the
    # whole board. `reaction_date` came out of `idx[k].date()`, so the
    # normalised index is the exact key.
    import pandas as pd
    try:
        norm = frame.index.normalize()
        want = pd.Timestamp(r["reaction_date"])
        k = int(norm.searchsorted(want, side="left"))
        if k >= len(frame) or norm[k] != want:
            return unknown("insufficient_history", **facts)
    except Exception as exc:                                    # noqa: BLE001
        log.debug("since_report: anchor lookup failed: %s", exc)
        return unknown("insufficient_history", **facts)

    last = len(frame) - 1
    # A ZERO-LENGTH WINDOW IS BLANK. The reaction close IS the latest closed
    # bar, so no session has closed on the number yet. `+0.0%` here would read
    # as "unchanged", which is a different and false statement.
    if k >= last:
        return unknown("not_traded_yet", **facts)

    closes = frame["close"].to_numpy(dtype=float)
    anchor_close = float(closes[k])
    last_close = float(closes[last])
    pct = r.get("drift_since_pct")
    try:
        pct = float(pct)
    except (TypeError, ValueError):
        pct = float("nan")

    # THE GUARD. `_fetch_yfinance` does not filter close > 0 the way
    # `_fetch_massive` does, so a cached frame CAN hold a zero or NaN close,
    # and `closes[k] == 0` gives numpy inf rather than an exception. A served
    # `known: true` with a null or non-finite return would be a lie the API
    # scrub cannot catch — the scrub is a belt, this is the guard.
    if (anchor_close <= 0
            or not math.isfinite(anchor_close)
            or not math.isfinite(last_close)
            or not math.isfinite(pct)):
        return unknown("insufficient_history", **facts)

    out = dict(facts)
    out.update({
        "known": True,
        "pct": pct,
        "anchor_date": r["reaction_date"],
        "anchor_close": round(anchor_close, 4),
        "as_of": last_bar,
        "last_close": round(last_close, 4),
        "sessions": last - k,
        "reason": None,
    })
    return {k2: out.get(k2) for k2 in _ROW_KEYS}


def honesty_line(board: str) -> str:
    """The board's own honesty sentence, built ONLY from `RUN_MEASURED`.

    Every number is formatted out of the dict — nothing is typed into the
    string but the words. A re-run that moves a figure moves the sentence."""
    m = RUN_MEASURED
    b = m["growth"] if board == "growth" else m["bonde"]
    head = (f"MEASURED {m['run_date']} — the typical name on this board had "
            f"already had its run before the board could see it")
    tail = (f"This column is that ‘since’ leg per name, from the REPORT "
            f"date on the earnings calendar; the study measured from the SEC "
            f"filing date. A fact between two dates: it changes no order, no "
            f"filter and no gate. {m['doc']}")
    if board == "growth":
        return (f"{head}. The growth board's median member gained "
                f"{_sgn(b['pre_median_pct'])}% in the {m['sessions_before']} "
                f"sessions before its qualifying filing and is "
                f"{_sgn(b['since_median_pct'])}% since "
                f"({b['n_positive']} of {b['n_known']} positive). {tail}")
    # The universe leg is the SCAN UNIVERSE's own pre-filing median, not an RSP
    # read — the RSP-relative numbers live elsewhere in the artifact and are
    # not served here. Never call it "the market".
    u = m["universe"]
    return (f"{head}, and here it ran no harder than the scan universe: the "
            f"visible Bonde board's median member gained "
            f"{_sgn(b['pre_median_pct'])}% in the {m['sessions_before']} "
            f"sessions before its qualifying filing (scan universe "
            f"{_sgn(u['pre_median_pct'])}%) and is "
            f"{_sgn(b['since_median_pct'])}% since "
            f"({b['n_positive']} of {b['n_known']} positive). {tail}")


def frames_for(symbols) -> dict:
    """ONE price-cache read for a whole board. Never fetches, never raises."""
    try:
        return P.bulk_cached_frames(symbols) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("since_report: frames read failed: %s", exc)
        return {}


def _reports_for(symbols) -> dict:
    """ONE calendar read for a whole board. Never raises."""
    try:
        return EW.last_report_map(symbols) or {}
    except Exception as exc:                                    # noqa: BLE001
        log.debug("since_report: calendar read failed: %s", exc)
        return {}


def attach(rows: list, *, reports: Optional[dict] = None,
           frames: Optional[dict] = None, today: Optional[str] = None,
           session: Optional[str] = None, board: str = "growth") -> dict:
    """Give every row `r["since_report"]`; return the board-level summary.

    Mutates in place and NEVER adds, drops, reorders or re-sorts a row, and
    never touches any other row key. Visits each DISTINCT dict ONCE: a ⚡ pivot
    row on the Bonde board is one object appended to two sections
    (`bonde.py:601/605/609`), so dedupe is by `id(row)` — never by symbol —
    and both section references then carry the identical cell.

    Never raises. On any failure every row still gets a shaped blank and a
    summary still comes back: a dead calendar must not blank his board."""
    rows = rows if isinstance(rows, list) else []
    try:
        day = _iso(today) or today_et()
    except Exception as exc:                                    # noqa: BLE001
        log.debug("since_report: clock read failed: %s", exc)
        day = None
    sess = session
    if sess is None:
        try:
            sess = P.trade_session(EW._today_et())
        except Exception as exc:                                # noqa: BLE001
            log.debug("since_report: session read failed: %s", exc)
            sess = None

    seen: set = set()
    distinct: list = []
    for r in rows:
        if not isinstance(r, dict) or id(r) in seen:
            continue
        seen.add(id(r))
        distinct.append(r)

    syms = []
    for r in distinct:
        s = str(r.get("symbol") or "").strip().upper()
        if s and s not in syms:
            syms.append(s)

    reps = reports if reports is not None else _reports_for(syms)
    frs = frames if frames is not None else frames_for(syms)

    n = n_known = n_positive = n_stale = n_cal_stale = 0
    blank_reasons: dict = {}
    as_of = None
    for r in distinct:
        n += 1
        sym = str(r.get("symbol") or "").strip().upper()
        try:
            rep = reps.get(sym) if hasattr(reps, "get") else None
        except Exception as exc:                                # noqa: BLE001
            log.debug("since_report: report lookup failed %s: %s", sym, exc)
            rep = None
        try:
            frame = frs.get(sym) if hasattr(frs, "get") else None
        except Exception as exc:                                # noqa: BLE001
            log.debug("since_report: frame lookup failed %s: %s", sym, exc)
            frame = None
        cell = (read_one(rep, frame, day, r.get("period_end"), sess) if day
                else unknown("no_report"))
        r["since_report"] = cell
        if cell.get("known"):
            n_known += 1
            if (cell.get("pct") or 0) > 0:
                n_positive += 1
            if cell.get("as_of") and (as_of is None or cell["as_of"] > as_of):
                as_of = cell["as_of"]
        else:
            reason = cell.get("reason") or "no_report"
            blank_reasons[reason] = blank_reasons.get(reason, 0) + 1
        if cell.get("stale_report"):
            n_stale += 1
        if cell.get("calendar_stale"):
            n_cal_stale += 1

    key = "growth" if board == "growth" else "bonde"
    return {
        "n": n, "n_known": n_known, "n_positive": n_positive,
        "n_blank": n - n_known, "blank_reasons": blank_reasons,
        "n_stale_report": n_stale, "n_calendar_stale": n_cal_stale,
        "as_of": as_of,
        "date_basis": DATE_BASIS, "date_basis_note": DATE_BASIS_NOTE,
        "measured": {
            "run_date": RUN_MEASURED["run_date"], "doc": RUN_MEASURED["doc"],
            "sessions_before": RUN_MEASURED["sessions_before"],
            "benchmark": RUN_MEASURED["benchmark"],
            "board": dict(RUN_MEASURED[key]),
            "universe": dict(RUN_MEASURED["universe"]),
        },
        "honesty": honesty_line(key),
        "source": SOURCE,
    }


def attach_growth(rows: list) -> dict:
    """🚀 Explosive Growth: ONE calendar read + ONE price-cache read."""
    return attach(rows, board="growth")


def attach_bonde(payload: dict) -> dict:
    """📈 Bonde: the same join over every DISTINCT row dict on the board.

    A ⚡ pivot row is ONE object appended to `sections['pivot']` AND to its
    tier section, so the rows are flattened and de-duplicated by identity —
    counted once, computed once, and both references carry the same cell."""
    if not isinstance(payload, dict):
        return payload
    rows: list = []
    seen: set = set()
    for _key, section in (payload.get("sections") or {}).items():
        for r in section or []:
            if isinstance(r, dict) and id(r) not in seen:
                seen.add(id(r))
                rows.append(r)
    payload["since_report_summary"] = attach(rows, board="bonde")
    return payload
