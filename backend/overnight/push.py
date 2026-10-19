"""overnight/push — 🌙 the one morning push off the overnight session read.

Ajay 2026-10-19 (verbatim): "Can you do an over night scan for all the stocks
they are all growing over night". He asked for a SCAN, not an alert, so this
kind (`overnight_movers`) ships OFF: False in push.subs.default_prefs and NOT in
OWNER_KEEP_SET (BUILD_SPEC16 D8, AMENDMENTS16 A2 — HIS CALL #1). The pass still
runs every trading morning: with the toggle off the send targets zero devices,
push_history keeps a total-0 row listing every name that passed, and /alerts
records why the phone was quiet.

One push per overnight session, at SLOT_ET on the trade date (the crontab line
`45 6 * * 1-5 … market_hours.gate overnight.push`), never before it and never
after the regular open (daytrading.data.ET_RTH_OPEN). It reports the session that
ended at 04:00 ET — its last stored read (overnight.scan.load_latest), timed in
the push. The gate (gate_rows): up overnight, price at least the house floor
(trading.safety_floor.MIN_SHARE_PRICE), at least PUSH_MIN_ON_DOLLAR traded
overnight, and not a leveraged or inverse ETF — a name whose leverage could
not be read is left out too (fail-closed). No name passes → no push.

Overnight trades on Alpaca's feed are indicative and delayed (~15 min); a line
priced off one says so. UNMEASURED — what moved overnight, not what to buy.
Not advice.
"""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, time as dtime
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from trading.safety_floor import MIN_SHARE_PRICE, _f

log = logging.getLogger("overnight.push")

ET = ZoneInfo("America/New_York")

KIND = "overnight_movers"
SLOT_ET = "06:45"                 # MINE — HIS CALL #2; == the crontab push line (test + contract)
PUSH_TOP_N = 5                    # brief
PUSH_MIN_PRICE = MIN_SHARE_PRICE  # house $2, by name
PUSH_MIN_ON_DOLLAR = 250_000      # MINE — HIS CALL #3
ITEMS_MAX = 25                    # MINE — names logged on the /alerts row
CLAIM_COLL = "overnight_push"     # _id = trade date; {claimed_at, state claimed|pushed|no_target|failed, read_id, names, result}
URL = "/chart-maps?tab=overnight&on_sub=session"

COUNT_KEYS = ("candidates", "passed", "pushed", "skipped_price", "skipped_thin", "skipped_leveraged",
              "skipped_lev_unknown", "skipped_not_up", "no_target")

TAIL = "UNMEASURED — what moved overnight, not what to buy. Not advice."
TRADE_MARK = " · delayed indicative trade"     # AMENDMENTS16 A4: every trade-based price says so
QUOTE_MARK = " · q"                            # the bid/ask midpoint (the board's q chip)


# ── clock ────────────────────────────────────────────────────────────────────
def _et(now: Optional[datetime] = None) -> datetime:
    """An aware ET instant. A naive `now` is the ET wall clock (the hottest
    `_now_et` rule), never UTC."""
    if now is None:
        return datetime.now(ET)
    return now.astimezone(ET) if now.tzinfo is not None else now.replace(tzinfo=ET)


def _slot() -> dtime:
    """SLOT_ET as a time — read at call time, so a moved slot moves the window."""
    return datetime.strptime(SLOT_ET, "%H:%M").time()


def _hm(t: dtime) -> str:
    return f"{t.hour}:{t.minute:02d}"


def window_reason(now) -> Optional[str]:
    """Why the push may not go now, or None. The ONE market calendar
    (market_hours.gate.closed_reason) first; then never before SLOT_ET and
    never once the regular session has opened (daytrading.data.ET_RTH_OPEN)."""
    from market_hours import gate                      # lazy: gate → reminder → push stack
    from daytrading.data import ET_RTH_OPEN            # lazy: pulls pandas
    et = _et(now)
    closed = gate.closed_reason(et)
    if closed:
        return closed
    t = et.time()
    if t < _slot():
        return f"before {SLOT_ET} ET"
    if t >= ET_RTH_OPEN:
        return f"the regular session opened at {_hm(ET_RTH_OPEN)} ET"
    return None


# ── gate ─────────────────────────────────────────────────────────────────────
def gate_rows(rows: list) -> tuple:
    """(passed, counts). Passed = up overnight, price >= PUSH_MIN_PRICE,
    on_dollar >= PUSH_MIN_ON_DOLLAR, `leveraged is False` (None — leverage not
    read — fails closed), ordered (-pct, symbol). Each failing row is counted
    once, under the first gate it fails in that order."""
    counts = {"candidates": 0, "skipped_not_up": 0, "skipped_price": 0, "skipped_thin": 0,
              "skipped_leveraged": 0, "skipped_lev_unknown": 0}
    passed = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("symbol"):
            continue
        counts["candidates"] += 1
        pct, price, on_dollar = _f(r.get("pct")), _f(r.get("price")), _f(r.get("on_dollar"))
        lev = r.get("leveraged")
        if pct is None or pct <= 0:
            counts["skipped_not_up"] += 1
        elif price is None or price < PUSH_MIN_PRICE:
            counts["skipped_price"] += 1
        elif on_dollar is None or on_dollar < PUSH_MIN_ON_DOLLAR:
            counts["skipped_thin"] += 1
        elif lev is True:
            counts["skipped_leveraged"] += 1
        elif lev is not False:
            counts["skipped_lev_unknown"] += 1
        else:
            passed.append(r)
    passed.sort(key=lambda r: (-_f(r.get("pct")), str(r.get("symbol"))))
    counts["passed"] = len(passed)
    return passed, counts


# ── payload ──────────────────────────────────────────────────────────────────
def _ref_symbols() -> tuple:
    """overnight.scan.REF_SYMBOLS, never retyped (lazy: the scan pulls the
    Massive / Alpaca stack, and alert_status imports this module)."""
    from overnight import scan
    return tuple(scan.REF_SYMBOLS)


def _usd_short(x) -> str:
    v = _f(x)
    if v is None:
        return "—"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:.1f}B"
    if a >= 1e6:
        return f"${v / 1e6:.1f}M"
    if a >= 1e3:
        return f"${v / 1e3:.0f}K"
    return f"${v:,.0f}"


def _wd_mmdd(iso) -> str:
    """'Fri 10-16' (the key_levels._day_mmdd house form); the raw text when unparsable."""
    try:
        d = datetime.strptime(str(iso)[:10], "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return str(iso or "—")
    return d.strftime("%a %m-%d")


def _pct(x, fmt: str) -> Optional[str]:
    v = _f(x)
    return None if v is None else format(v, fmt) + "%"


def name_line(r: dict) -> str:
    sym = str(r.get("symbol"))
    price = _f(r.get("price"))
    prior = _pct(r.get("prior_pct"), "+.1f")
    line = (f"{sym} {_pct(r.get('pct'), '+.1f')} · "
            f"{'$' + format(price, ',.2f') if price is not None else '—'} · "
            f"{_usd_short(r.get('on_dollar'))} overnight · prior session {prior or '—'}")
    src = r.get("src")
    if src == "q":
        line += QUOTE_MARK
    elif src == "t":
        line += TRADE_MARK
    return line


def index_line(read: dict) -> str:
    refs = {str(r.get("symbol")): r for r in (read.get("refs") or []) if isinstance(r, dict)}
    parts = []
    for s in _ref_symbols():
        p = _pct((refs.get(s) or {}).get("pct"), "+.2f")
        parts.append(f"{s} {p}" if p is not None else f"{s} —")
    return (" · ".join(parts) + f" · vs {_wd_mmdd(read.get('base_date'))} close"
            + f" · read {read.get('as_of_et') or '—'}")


def compose(read: dict, passed: list) -> dict:
    """The push. Title names the first 3, body the index line then the top
    PUSH_TOP_N; `items` logs every passed name up to ITEMS_MAX (never sent)."""
    read = read or {}
    n = len(passed)
    head = [f"{r.get('symbol')} {_pct(r.get('pct'), '+.1f')}" for r in passed[:3]]
    title = "🌙 Overnight movers — " + ", ".join(head) + (f" +{n - 3} more" if n > 3 else "")
    top = passed[:PUSH_TOP_N]
    lines = [index_line(read)] + [name_line(r) for r in top]
    if n > PUSH_TOP_N:
        lines.append(f"+{n - PUSH_TOP_N} more on the board")
    lines.append(TAIL)
    td = read.get("trade_date")
    return {"title": title, "body": "\n".join(lines), "url": URL, "kind": KIND,
            "tag": f"{KIND}:{td}", "ticker": None,
            "tickers": [str(r.get("symbol")) for r in top],
            "items": [{"symbol": str(r.get("symbol")), "text": name_line(r)} for r in passed[:ITEMS_MAX]]}


# ── the pass ─────────────────────────────────────────────────────────────────
def _claim_coll():
    try:
        from portfolio.store import _get_db
        db = _get_db()
        return db[CLAIM_COLL] if db is not None else None
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: no mongo for %s: %s", CLAIM_COLL, exc)
        return None


def _default_send(*, owner: str, payload: dict) -> dict:
    from push import hooks
    return hooks.notify_overnight_movers(owner=owner, payload=payload)


def _default_load(trade_date: str):
    from overnight import scan
    return scan.load_latest(trade_date)


def _record(result: dict, now: datetime, pass_coll) -> None:
    try:
        from supply_demand import alert_status as AS
        AS.record_result(KIND, result, now, coll=pass_coll)
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: status record failed: %s", exc)


def run_pass(now=None, *, claim_coll=None, pass_coll=None, load: Optional[Callable] = None,
             send: Optional[Callable] = None, dry_run: bool = False) -> dict:
    """One morning pass. `dry_run` composes and returns the payload; it sends,
    claims and records nothing."""
    et = _et(now)
    td = et.date().isoformat()
    counts = {k: 0 for k in COUNT_KEYS}
    out = {"kind": KIND, "ran": False, "date": td, **counts}
    if dry_run:
        out["dry_run"] = True

    why = window_reason(et)
    if why:
        out["reason"] = why
        log.info("OVERNIGHT-PUSH: %s — not run", why)
        return out

    def _finish(reason: Optional[str] = None) -> dict:
        out.update(counts)
        out["ran"] = True
        if reason:
            out["reason"] = reason
        if not dry_run:
            _record({k: v for k, v in out.items() if k != "dry_run"}, et, pass_coll)
        log.info("OVERNIGHT-PUSH: %s", {k: v for k, v in out.items() if k != "payload"})
        return out

    loader = load if load is not None else _default_load
    try:
        read = loader(td)
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: read failed: %s", exc)
        read = None
    if not isinstance(read, dict):
        return _finish(f"no overnight read stored for the {td} session")
    read_td = str(read.get("trade_date") or "")
    if read_td != td:
        return _finish(f"the latest overnight read is for the {read_td or 'unknown'} session, not {td}")
    out["read_id"] = read.get("_id")

    passed, gcounts = gate_rows(read.get("rows") or [])
    counts.update(gcounts)
    if not passed:
        return _finish("no name passed the gate")

    payload = compose(read, passed)
    if dry_run:
        out["payload"] = payload
        return _finish()

    coll = claim_coll if claim_coll is not None else _claim_coll()
    if coll is None:
        return _finish("claim store unreachable — not sent")
    names = [i["symbol"] for i in payload["items"]]
    try:
        from pymongo.errors import DuplicateKeyError
    except Exception:                                         # pragma: no cover - pymongo is in the image
        DuplicateKeyError = ()                                # type: ignore[assignment]
    try:
        coll.insert_one({"_id": td, "claimed_at": et.isoformat(), "state": "claimed",
                         "read_id": read.get("_id"), "names": names, "result": None})
    except DuplicateKeyError:                                 # type: ignore[misc]
        out["ran"] = True
        out["reason"] = f"already pushed for the {td} session"
        log.info("OVERNIGHT-PUSH: %s", out["reason"])
        return out
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: claim failed: %s", exc)
        return _finish("claim store unreachable — not sent")

    from push import subs
    sender_fn = send if send is not None else _default_send
    reason = None
    try:
        res = sender_fn(owner=subs._owner_email(), payload=payload) or {}
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: send failed: %s", exc)
        res = {"sent": 0, "failed": 0, "error": type(exc).__name__}
    sent = int(_f(res.get("sent")) or 0)
    if sent > 0:
        state = "pushed"
        counts["pushed"] = 1
    elif "total_targets" in res and int(_f(res.get("total_targets")) or 0) == 0:
        state = "no_target"
        counts["no_target"] = 1
    else:
        state = "failed"
        reason = "send failed"
    try:
        coll.update_one({"_id": td}, {"$set": {"state": state, "result": dict(res)}})
    except Exception as exc:                                  # noqa: BLE001
        log.warning("overnight.push: claim update failed: %s", exc)
    out["state"] = state
    return _finish(reason)


def main(argv: Optional[list] = None) -> int:
    """python -m overnight.push [--dry-run] [--json]"""
    argv = list(sys.argv[1:] if argv is None else argv)
    res = run_pass(dry_run="--dry-run" in argv)
    if "--json" in argv:
        print(json.dumps(res, default=str, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({k: v for k, v in res.items() if k != "payload"}, default=str, ensure_ascii=False))
    return 0


__all__ = ["KIND", "SLOT_ET", "PUSH_TOP_N", "PUSH_MIN_PRICE", "PUSH_MIN_ON_DOLLAR", "ITEMS_MAX", "CLAIM_COLL",
           "URL", "COUNT_KEYS", "window_reason", "gate_rows", "compose", "name_line", "index_line", "run_pass",
           "main"]


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
