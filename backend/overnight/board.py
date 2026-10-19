"""🌙 Overnight session board payload (BUILD_SPEC16 §3.4, 2026-10-19).

`GET /overnight/session` serves the newest stored `overnight_reads` doc (Mongo
only — the cron container's `overnight.scan` is the only writer; this module
never calls Alpaca or Massive). Every word the board prints is built here from
the enforcing constants (the FE composes none). UNMEASURED — what moved
overnight, never what to buy. Not advice.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional

from chart_maps.drop10_tab import CLOSED_TTL_SEC as _DROP10_CLOSED_TTL_SEC

from . import scan
from . import session as S

SORTS = (("gainers", "📈 Top gainers"), ("losers", "📉 Top losers"), ("dollar", "💵 Most $ traded overnight"))
DEFAULT_SORT = "gainers"
REFRESH_OPEN_SEC = 300                          # MINE
REFRESH_CLOSED_SEC = _DROP10_CLOSED_TTL_SEC     # == drop10_tab.CLOSED_TTL_SEC by name (chart_maps/drop10_tab.py:78)
STALE_SEC = 2 * scan.CADENCE_SEC + 300          # MINE

LINE_OPEN = ("🌙 Overnight session open — {open_wd} {open_hhmm} → {close_wd} {close_hhmm} ET "
             "(trade date {td_wd} {td_mmdd}). Read every {cadence_min} minutes.")
LINE_CLOSED = "🌙 Overnight session closed — the next one opens {next_wd} {next_hhmm} ET."
LINE_LAST = "Last read {as_of_et}."
LINE_LAST_STALE = ("Last read {as_of_et} — late: the next was due by {due_et} "
                   "(host asleep or the job failed).")
LINE_READ_OLD = "Showing the {td_wd} {td_mmdd} session's last read ({as_of_et})."
LINE_COUNTS = ("{universe:,} names (last regular close ≥ ${min_px:g} on ≥ {min_dv} traded) · "
               "{priced:,} priced this session ({on_trade:,} on a trade, {on_quote:,} on the quote, marked q) · "
               "{listed:,} with ≥ {board_floor} traded overnight listed · {thin:,} thinner, counted · "
               "{not_priced:,} not priced.")
# AMENDMENTS16 A1: the live quote midpoint prices first, the delayed indicative trade second.
# CHANGED 2026-10-19 (coordinator): the trade-age clause names how many priced names it covers
# (counts.on_trade of counts.priced) so a median over thin names never reads as the whole board's age.
LINE_PRICE = ("Now = the live bid/ask midpoint (marked q) when the quote printed this session, is at most "
              "{quote_fresh_min:g} minutes old and its spread is at most {spread_max_pct:g}% of the midpoint; "
              "else the latest overnight trade if it printed this session (marked t — Alpaca's indicative "
              "Blue Ocean feed, delayed; {n_trade:,} of the {n_priced:,} priced names come from such a print, "
              "a median {age_min} minutes old). "
              "Overnight % is against the {base_wd} {base_mmdd} regular-session close (Massive) and includes "
              "that evening's after-hours move.")
LINE_LEV = ("Leveraged and inverse ETFs are tagged from the fund's own name in the Massive reference list "
            "(a stated multiple above 1×, Ultra / UltraPro / UltraShort, Bear, Inverse, ProShares Short): "
            "{tagged:,} tagged{unknown_tail}.")
LEV_UNKNOWN_TAIL = "; the reference list could not be read, so leverage is unknown on every row"
LINE_UNMEASURED = "UNMEASURED — this says what moved overnight, never what to buy. Not advice."
LINE_EMPTY = "No overnight read stored yet — the first pass runs at {open_hhmm} ET on a session night."
# CHANGED 2026-10-19 (critic finding 3): a failed pass says so, and the empty line stops promising a first pass.
LINE_LAST_FAILED = "Last pass {as_of_et} failed — {reason}"
LINE_EMPTY_FAILED = "No overnight read stored yet — the last pass ({as_of_et}) failed."
DISCLAIMER = ("Overnight prices: Alpaca's overnight feed (Blue Ocean ATS). Base close: Massive. "
              "Not advice.")

_SORT_KEYS = {k for k, _ in SORTS}


# ---------------------------------------------------------------------------
# PURE
# ---------------------------------------------------------------------------
def _usd_short(v) -> str:
    """$25K / $1M / $1.5B from a constant (never typed twice)."""
    v = float(v)
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(v) >= div:
            return f"${v / div:g}{suf}"
    return f"${v:g}"


def _hhmm(dt: datetime) -> str:
    return dt.astimezone(S.ET).strftime("%H:%M")


def _wd(d) -> str:
    return d.strftime("%a")


def _mmdd(d) -> str:
    return d.strftime("%m-%d")


def _date(s):
    try:
        return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return None


def _clean(o):
    """NaN / inf → None, recursively (the payload must pass allow_nan=False)."""
    if isinstance(o, float):
        return None if (o != o or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items() if k != "_id"}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    return o


def _num(v) -> float:
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) and v == v else 0.0


def order_rows(rows: list, sort: str) -> list:
    """gainers (-pct, symbol) · losers (pct, symbol) · dollar (-on_dollar, symbol);
    an unknown sort → DEFAULT_SORT."""
    sort = sort if sort in _SORT_KEYS else DEFAULT_SORT
    rows = list(rows or [])
    if sort == "losers":
        return sorted(rows, key=lambda r: (_num(r.get("pct")), str(r.get("symbol") or "")))
    if sort == "dollar":
        return sorted(rows, key=lambda r: (-_num(r.get("on_dollar")), str(r.get("symbol") or "")))
    return sorted(rows, key=lambda r: (-_num(r.get("pct")), str(r.get("symbol") or "")))


def _session_block(sess: dict) -> dict:
    if sess["open"]:
        oa, ca, td = sess["opens_at"], sess["closes_at"], sess["trade_date"]
        line = LINE_OPEN.format(open_wd=_wd(oa), open_hhmm=_hhmm(oa), close_wd=_wd(ca),
                                close_hhmm=_hhmm(ca), td_wd=_wd(td), td_mmdd=_mmdd(td),
                                cadence_min=scan.CADENCE_SEC // 60)
    else:
        na = sess["next_open"]
        line = LINE_CLOSED.format(next_wd=_wd(na), next_hhmm=_hhmm(na))
    return {
        "open": bool(sess["open"]),
        "trade_date": sess["trade_date"].isoformat() if sess.get("trade_date") else None,
        "opens_at": sess["opens_at"].isoformat() if sess.get("opens_at") else None,
        "closes_at": sess["closes_at"].isoformat() if sess.get("closes_at") else None,
        "next_open": sess["next_open"].isoformat() if sess.get("next_open") else None,
        "line": line,
    }


def _counts_line(c: dict) -> str:
    g = lambda k: int(c.get(k) or 0)                            # noqa: E731
    return LINE_COUNTS.format(
        universe=g("universe"), min_px=float(scan.UNIVERSE_MIN_PRICE),
        min_dv=_usd_short(scan.UNIVERSE_MIN_DOLLAR_VOL), priced=g("priced"),
        on_trade=g("on_trade"), on_quote=g("on_quote"), listed=g("listed"),
        board_floor=_usd_short(scan.BOARD_MIN_ON_DOLLAR), thin=g("thin"),
        not_priced=max(0, g("universe") - g("priced")))


def _price_line(read: dict) -> str:
    c = read.get("counts") or {}
    age = c.get("trade_age_median_sec")
    age_min = str(int(round(age / 60))) if isinstance(age, (int, float)) and age == age else "—"
    bd = _date(read.get("base_date"))
    return LINE_PRICE.format(n_trade=int(c.get("on_trade") or 0), n_priced=int(c.get("priced") or 0),
                             quote_fresh_min=scan.QUOTE_FRESH_SEC / 60,
                             spread_max_pct=round(scan.QUOTE_SPREAD_MAX * 100, 6), age_min=age_min,
                             base_wd=_wd(bd) if bd else "—", base_mmdd=_mmdd(bd) if bd else "—")


def _lev_line(c: dict) -> str:
    return LINE_LEV.format(tagged=int(c.get("leveraged_tagged") or 0),
                           unknown_tail="" if c.get("ref_complete") else LEV_UNKNOWN_TAIL)


def _last_pass(p: Optional[dict], sess: dict, now_et: datetime) -> Optional[dict]:
    if not p:
        return None
    ts = p.get("as_of_ts")
    stale = False
    due_et = None
    if sess["open"] and isinstance(ts, (int, float)):
        ref_ts = max(float(ts), sess["opens_at"].timestamp())
        stale = (now_et.timestamp() - ref_ts) > STALE_SEC
        due_et = scan._et_words(datetime.fromtimestamp(ref_ts + scan.CADENCE_SEC, S.ET))
    as_of_et = p.get("as_of_et") or "—"
    if not p.get("ok"):
        line = LINE_LAST_FAILED.format(as_of_et=as_of_et, reason=p.get("reason") or "no reason recorded")
    elif stale:
        line = LINE_LAST_STALE.format(as_of_et=as_of_et, due_et=due_et)
    else:
        line = LINE_LAST.format(as_of_et=as_of_et)
    return {"as_of": p.get("as_of"), "as_of_et": p.get("as_of_et"), "ok": bool(p.get("ok")),
            "reason": p.get("reason"), "stale": stale, "line": line}


def board_payload(*, sort=None, hide_lev=False, now=None, reads_coll=None, pass_coll=None) -> dict:
    now_et = S.et_now(now)
    sess = S.session_for(now_et)
    sort = sort if sort in _SORT_KEYS else DEFAULT_SORT
    doc = scan.load_latest(None, coll=reads_coll)
    lines = {"counts": None, "price_rule": None, "leveraged": None,
             "unmeasured": LINE_UNMEASURED, "empty": None, "read_old": None}
    read = None
    if doc:
        doc = _clean(doc)
        current = bool(sess["open"] and sess.get("trade_date")
                       and doc.get("trade_date") == sess["trade_date"].isoformat())
        rows = list(doc.get("rows") or [])
        n_hidden = 0
        if hide_lev:
            kept = [r for r in rows if r.get("leveraged") is not True]
            n_hidden = len(rows) - len(kept)
            rows = kept
        by = {r.get("symbol"): r for r in (doc.get("refs") or [])}
        refs = [by[s] for s in scan.REF_SYMBOLS if s in by]
        rows = order_rows(rows, sort)
        counts = doc.get("counts") or {}
        read = {
            "trade_date": doc.get("trade_date"), "base_date": doc.get("base_date"),
            "as_of": doc.get("as_of"), "as_of_et": doc.get("as_of_et"), "current": current,
            "complete": bool(doc.get("complete")), "reason": doc.get("reason"), "counts": counts,
            "refs": refs, "rows": rows, "sort": sort, "hide_leveraged": bool(hide_lev),
            "n_hidden_leveraged": n_hidden, "n_listed": len(rows),
        }
        lines["counts"] = _counts_line(counts)
        lines["price_rule"] = _price_line(doc)
        lines["leveraged"] = _lev_line(counts)
        if not current:
            td = _date(doc.get("trade_date"))
            lines["read_old"] = LINE_READ_OLD.format(td_wd=_wd(td) if td else "—",
                                                     td_mmdd=_mmdd(td) if td else "—",
                                                     as_of_et=doc.get("as_of_et") or "—")
    p = scan.load_pass(coll=pass_coll)
    if not doc:
        if p and not p.get("ok"):
            lines["empty"] = LINE_EMPTY_FAILED.format(as_of_et=p.get("as_of_et") or "—")
        else:
            lines["empty"] = LINE_EMPTY.format(open_hhmm=S.SESSION_OPEN_ET.strftime("%H:%M"))
    return _clean({
        "session": _session_block(sess),
        "read": read,
        "last_pass": _last_pass(_clean(p) if p else None, sess, now_et),
        "sorts": [{"key": k, "label": lab} for k, lab in SORTS],
        "lines": lines,
        "refresh_sec": REFRESH_OPEN_SEC if sess["open"] else REFRESH_CLOSED_SEC,
        "disclaimer": DISCLAIMER,
    })
