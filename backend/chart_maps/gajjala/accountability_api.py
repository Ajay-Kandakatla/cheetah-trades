"""🧾 My trades vs GG — the routes (spec accountability §3.5, WP-BE1, 2026-11-23).

Ajay 2026-11-23, verbatim: "I think I am going outside Gajjalas now.. Please create a rule to warn me to not over trade
and hold me accountable if I am missing out any gajjalas rules".

  * `GET  /chart-maps/gajjala/my-trades[?date=YYYY-MM-DD]` — PRIMARY OWNER ONLY through `maybe_current_user` +
    `_is_owner` (the 👀 Watch pattern). Anyone else — another email, no email, or a direct call that receives the
    `Depends` OBJECT — gets exactly `owner_only_payload()` (HTTP 200) and nothing is read. The owner's body is built and
    scrubbed inside ONE `asyncio.to_thread`. It READS ONLY: his log (accountability_store), the day's live `GG:` A+
    claims (gajjala_alerts), the latest pass's quiet strip, and the 🏁 `same` cell of each matched alert (the stored
    nightly cell, or the 🏁's own memo-only provisional — never a bar fetch). It never writes.
  * `POST /chart-maps/gajjala/my-trades` — `require_primary_admin` (404 for anyone else, resolved BEFORE the body: the
    body is read inside the handler, so a non-owner's malformed JSON is a 404 too). Body {sym, entry, stop?, stop_src,
    shares?, grade, why_b?, patience, discipline} → 422 on a bad body (nothing stored); 409 on a closed day (nothing
    stored); else ONE insert and {doc, checks, verdict_text, warn_lines}.
  * `POST …/{id}/exit` {exit_px, exit_note?} — 422 bad body / exit_px ≤ 0; 404 unknown id; 409 a second exit.
  * `POST …/{id}/void` — the doc is kept, `void` True; 404 unknown id; 409 already voided.

Nothing here trades, calls a broker, Plaid or a push sender, hides a ticker or changes a gate. Times are HIS TAP times
(the server's clock at the tap), never fill times. The admin email never appears in an answer.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse

from auth import maybe_current_user
from ollama_chat.api import require_primary_admin

from chart_maps.gajjala import accountability as AC
from chart_maps.gajjala import accountability_store as S
from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import ledger as LG

log = logging.getLogger("chart_maps.gajjala.accountability_api")
ET = ZoneInfo("America/New_York")
UTC = timezone.utc

API_PATH = "/chart-maps/gajjala/my-trades"
API_EXIT_PATH = API_PATH + "/{trade_id}/exit"
API_VOID_PATH = API_PATH + "/{trade_id}/void"
BODY_KEYS = ("sym", "entry", "stop", "stop_src", "shares", "grade", "why_b", "patience", "discipline")
EXIT_KEYS = ("exit_px", "exit_note")
TEXT_MAX = 500                                                  # TRANSPORT — longest why_b / exit_note stored
READ_FAULT_TEXT = "your journal could not be read — nothing logged"
WRITE_FAULT_TEXT = "your journal could not be written — nothing logged"
NOT_FOUND_TEXT = "no such trade in your journal"
EXIT_TWICE_TEXT = "an exit is already logged for this trade"
VOIDED_TEXT = "this trade is voided"
VOID_TWICE_TEXT = "this trade is already voided"
NO_ALERT_STOP_TEXT = "no app 🎯 A+ stop to use for this name — type your stop"
BAD_DATE_TEXT = "date must be YYYY-MM-DD"

router = APIRouter(tags=["chart-maps"])


def _is_owner(email) -> bool:
    if not isinstance(email, str) or not email.strip():
        return False
    from ollama_chat.api import is_primary_admin                 # lazy: tests monkeypatch it
    try:
        return bool(is_primary_admin(email))
    except Exception:                                           # noqa: BLE001
        return False


def owner_only_payload() -> dict:
    """Exactly the 👀 Watch's owner-only answer (one shape for every owner-only Gajjala route)."""
    from chart_maps.gajjala_watch.payload import owner_only_payload as _oo
    return _oo()


def _now() -> datetime:
    return datetime.now(UTC)


def _gstore():
    """The 🚩 GG5 store (alerts + passes + the 🏁 ledger) — tests inject a GajjalaStore(colls=…)."""
    from chart_maps.gajjala import store as ST
    return ST.GajjalaStore()


def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return bool(is_market_day(d))


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _jsonable(o: Any) -> Any:
    if isinstance(o, dict):
        return {k: _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, datetime):
        return LG._aware(o).isoformat()
    if isinstance(o, date):
        return o.isoformat()
    return o


def _scrubbed(o: Any) -> Any:
    from growth.api import _scrub
    return _scrub(_jsonable(o))


def _out_doc(doc: dict) -> dict:
    d = dict(doc or {})
    d["id"] = d.pop("_id", None)
    d.pop("owner", None)                                        # the admin email never leaves the server
    return d


# ── reads ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _claims(st, days: list) -> tuple:
    """({date: [claim]}, {key: alert_of row}) of the live `GG:` 🎯 A+ claims of these days — ({}, {}) when none,
    (None, {}) on a read fault (A1 then reads unknown, never "no A+")."""
    try:
        raw = st.alert_rows(days)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("my-trades: claims read failed: %s", type(exc).__name__)
        raw = None
    if raw is None:
        return None, {}
    by_day: dict = {d: [] for d in days}
    rows: dict = {}
    for doc in raw:
        try:
            a = LG.alert_of(doc, LG.KINDS[1])
        except Exception:                                       # noqa: BLE001
            a = None
        key = str((doc or {}).get("_id") or "")
        if a is None or a.get("line") != LG.LINES[0] or a.get("date") not in by_day:
            continue
        if not key.startswith(AC.claim_prefix(a["date"], a["symbol"])):
            continue
        by_day[a["date"]].append({"sym": a["symbol"], "setup": a["setup"], "at_utc": a.get("at_utc"),
                                  "trigger": a.get("trigger"), "stop": a.get("stop"), "key": key})
        rows[key] = a
    return by_day, rows


def _quiet(st) -> Optional[bool]:
    """The latest GG5 pass's strip `quiet` — True / False, or None (no pass yet, or a read fault)."""
    try:
        latest = st.latest_pass()
    except Exception as exc:                                    # noqa: BLE001
        log.warning("my-trades: latest pass read failed: %s", type(exc).__name__)
        return None
    strip = (latest or {}).get("strip") if isinstance(latest, dict) else None
    q = strip.get("quiet") if isinstance(strip, dict) else None
    return q if isinstance(q, bool) else None


def _same_cells(st, rows: dict, keys: list, now: datetime, session: date, is_today: bool) -> dict:
    """{claim key: {state, text}} — the 🏁 `same` cell of each matched alert (the trading.gajjala_untraded join: claim →
    ledger.alert_of → ledger row → the stored nightly cell, else the 🏁's memo-only provisional). {} on a fault."""
    want = {k: rows[k] for k in keys if k in rows}
    if not want:
        return {}
    try:
        from chart_maps.gajjala import store as ST
        from trading import gajjala_untraded as GU
        led = st._find_or_none(ST.LEDGER, {"_id": {"$in": [a["id"] for a in want.values()]}})
        if led is None:
            return {}
        stored = {x.get("_id"): x for x in led if isinstance(x, dict)}
        out = {}
        for k, row in want.items():
            doc = stored.get(row["id"]) or {}
            same = doc.get("same") if isinstance(doc.get("same"), dict) else None
            prov = False
            if same is None and is_today:
                same = GU.provisional_same(row, session, now)
                prov = same is not None
            cell = LG._cell(row, "same", same, prov, now, session, is_today)
            out[k] = {"state": cell.get("state"), "text": cell.get("text")}
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("my-trades: 🏁 join failed: %s", type(exc).__name__)
        return {}


def _sessions(d: date) -> list:
    """The day and the market days before it — GC.LEDGER_SPAN_SESSIONS_LONG sessions (the 🏁 "10d" span), newest first."""
    out = [d]
    while len(out) < GC.LEDGER_SPAN_SESSIONS_LONG:
        out.append(_prev_market_day(out[-1]))
    return out


def build_get(owner: str, day: date, now: datetime) -> dict:
    """The owner's GET body. Reads only."""
    full = S.all_for(owner)
    if full is None:
        return {"state": "error", "text": READ_FAULT_TEXT}
    now = LG._aware(now)
    today = now.astimezone(ET).date()
    is_today = day == today
    sessions = _sessions(day)
    iso = [s.isoformat() for s in sessions]
    st = _gstore()
    claims, rows = _claims(st, iso)
    quiet = _quiet(st) if is_today else None
    di = day.isoformat()

    def ctx_of(s_iso):
        return {"aplus_claims": (claims.get(s_iso, []) if claims is not None else None), "quiet_at_tap": None,
                "now": now, "date": s_iso}

    keys = sorted({t.get("alert_id") for t in full if isinstance(t, dict) and t.get("date") == di
                   and isinstance(t.get("alert_id"), str)})
    cells = _same_cells(st, rows, keys, now, day, is_today)
    rec = AC.record(full, ctx_of(di), cells)
    graded = list(rec["trades"])
    for s_iso in iso[1:]:
        graded += AC.record(full, ctx_of(s_iso), {})["trades"]
    my_day = None
    if is_today:
        yday = _prev_market_day(day).isoformat()
        my_day = AC.my_day([t for t in full if isinstance(t, dict) and t.get("date") == di],
                           [t for t in full if isinstance(t, dict) and t.get("date") == yday],
                           {"aplus_claims": ctx_of(di)["aplus_claims"], "quiet_at_tap": quiet, "now": now,
                            "date": di, "market_day": _is_market_day(day), "history": full})
    aplus_today = [{"sym": c["sym"], "setup": c["setup"], "trigger": c.get("trigger"), "stop": c.get("stop")}
                   for c in (claims or {}).get(di, [])]
    return {"state": "ok", "date": di, "my_day": my_day, "trades": rec["trades"], "voided": rec["voided"],
            "totals": rec["totals"], "kept_text": rec["kept_text"], "week": AC.week_block(full, di),
            "tally_10d": AC.tally_10d(graded), "aplus_today": aplus_today}


def _parse_day(raw, now: datetime) -> Optional[date]:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return LG._aware(now).astimezone(ET).date()
    if not isinstance(raw, str):
        return None
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


@router.get(API_PATH)
async def my_trades(email: Optional[str] = Depends(maybe_current_user), date: Optional[str] = Query(None)):
    """🧾 the owner's journal, graded. A direct call (container smoke test) receives the Depends OBJECT → owner_only."""
    if not _is_owner(email):
        return owner_only_payload()
    now = _now()
    day = _parse_day(date, now)
    if day is None:
        return JSONResponse({"detail": BAD_DATE_TEXT}, status_code=422)

    def _work():
        try:
            return _scrubbed(build_get(email, day, now))
        except Exception as exc:                                # noqa: BLE001
            log.warning("my-trades: GET failed: %s", type(exc).__name__)
            return {"state": "error", "text": READ_FAULT_TEXT}
    return await asyncio.to_thread(_work)


# ── writes ───────────────────────────────────────────────────────────────────────────────────────────────────────
def _parse_json(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        return None


def _text_or_none(v, key: str) -> tuple:
    if v is None:
        return None, None
    if not isinstance(v, str):
        return None, f"{key} must be text"
    v = v.strip()
    if len(v) > TEXT_MAX:
        return None, f"{key} is too long"
    return (v or None), None


def parse_trade(payload: Any) -> tuple:
    """(fields, None) or (None, why). Pure — the 422 words name the field, never a value."""
    if not isinstance(payload, dict):
        return None, "the body must be a JSON object"
    extra = set(payload) - set(BODY_KEYS)
    if extra:
        return None, "unknown field: " + ", ".join(sorted(extra))
    from chart_maps.gajjala_watch.store import normalize
    sym = normalize(payload.get("sym"))
    if not sym:
        return None, "sym must be a ticker"
    entry = AC._pos(payload.get("entry"))
    if entry is None:
        return None, "entry is required (a price above 0)"
    src = payload.get("stop_src")
    if src not in AC.STOP_SRCS:
        return None, "stop_src must be one of " + ", ".join(AC.STOP_SRCS)
    raw_stop = payload.get("stop")
    stop = None
    if raw_stop is not None:
        stop = AC._num(raw_stop)
        if stop is None or stop < 0:
            return None, "stop must be a price"
    if src == AC.TYPED and stop is None:
        return None, "a typed stop needs a stop price"
    if src == AC.NONE:
        stop = None
    shares = None
    if payload.get("shares") is not None:
        sh = payload.get("shares")
        if isinstance(sh, bool) or not isinstance(sh, (int, float)) or AC._pos(sh) is None or float(sh) != int(sh):
            return None, "shares must be a whole number above 0"
        shares = int(sh)
    grade = payload.get("grade")
    if grade not in AC.GRADES:
        return None, "grade must be A+ or B"
    why, bad = _text_or_none(payload.get("why_b"), "why_b")
    if bad:
        return None, bad
    if payload.get("patience") not in AC.PATIENCE:
        return None, "patience must be patient or impulse"
    if payload.get("discipline") not in AC.DISCIPLINE:
        return None, "discipline must be kept or broke"
    return {"sym": sym, "entry": entry, "stop": stop, "stop_src": src, "shares": shares, "grade": grade,
            "why_b": why, "patience": payload["patience"], "discipline": payload["discipline"]}, None


def post_trade(owner: str, fields: dict, now: datetime) -> tuple:
    """(status, body). The ONE insert of a tap; nothing stored on any refusal."""
    now = LG._aware(now)
    d = now.astimezone(ET).date()
    if not _is_market_day(d):
        return 409, {"detail": GC.MY_CLOSED_TEXT.format(date=d.isoformat())}
    full = S.all_for(owner)
    if full is None:
        return 503, {"detail": READ_FAULT_TEXT}
    di = d.isoformat()
    st = _gstore()
    claims, _rows = _claims(st, [di])
    day_claims = claims.get(di, []) if claims is not None else None
    quiet = _quiet(st)
    probe = {"sym": fields["sym"], "date": di, "tap_ts": now}
    claim = AC.aplus_claim(probe, day_claims)
    stop = fields["stop"]
    if fields["stop_src"] == AC.ALERT and stop is None:
        stop = AC._num((claim or {}).get("stop"))
        if stop is None:
            return 422, {"detail": NO_ALERT_STOP_TEXT}
    doc = {"_id": S.new_id(), "owner": owner, "date": di, "sym": fields["sym"],
           "alert_id": (claim or {}).get("key"), "entry": fields["entry"], "stop": stop,
           "stop_src": fields["stop_src"], "shares": fields["shares"], "grade": fields["grade"],
           "why_b": fields["why_b"], "patience": fields["patience"], "discipline": fields["discipline"],
           "tap_ts": now, "quiet_at_tap": quiet, "add_to": AC.add_parent(fields["sym"], full, di),
           "warned_at_tap": [], "exit_px": None, "exit_ts": None, "exit_note": None, "void": False, "void_ts": None}
    items = AC.checks(doc, list(full) + [doc], {"aplus_claims": day_claims, "quiet_at_tap": quiet, "now": now,
                                                 "date": di})
    doc["warned_at_tap"] = AC.warn_ids(items)
    if not S.insert(doc):
        return 503, {"detail": WRITE_FAULT_TEXT}
    return 200, {"doc": _out_doc(doc), "checks": items, "verdict_text": AC.verdict_text(doc, items),
                 "warn_lines": AC.warn_lines(items)}


def _respond(status: int, body: dict):
    body = _scrubbed(body)
    return body if status == 200 else JSONResponse(body, status_code=status)


@router.post(API_PATH)
async def my_trades_post(request: Request, email: str = Depends(require_primary_admin)):
    """🧾 one tap. The body is read HERE, after the owner gate (a declared body would be parsed before it)."""
    fields, why = parse_trade(_parse_json(await request.body()))
    if fields is None:
        return JSONResponse({"detail": why}, status_code=422)
    now = _now()
    status, body = await asyncio.to_thread(post_trade, email, fields, now)
    return _respond(status, body)


def parse_exit(payload: Any) -> tuple:
    if not isinstance(payload, dict):
        return None, "the body must be a JSON object"
    extra = set(payload) - set(EXIT_KEYS)
    if extra:
        return None, "unknown field: " + ", ".join(sorted(extra))
    px = AC._pos(payload.get("exit_px"))
    if px is None:
        return None, "exit_px must be a price above 0"
    note, bad = _text_or_none(payload.get("exit_note"), "exit_note")
    if bad:
        return None, bad
    return {"exit_px": px, "exit_note": note}, None


def post_exit(owner: str, trade_id: str, fields: dict, now: datetime) -> tuple:
    res = S.set_exit(owner, trade_id, fields["exit_px"], LG._aware(now), fields["exit_note"])
    if res == "absent":
        return 404, {"detail": NOT_FOUND_TEXT}
    if res == "already":
        return 409, {"detail": EXIT_TWICE_TEXT}
    if res == "void":
        return 409, {"detail": VOIDED_TEXT}
    if res != "ok":
        return 503, {"detail": WRITE_FAULT_TEXT}
    return 200, {"state": "ok", "doc": _out_doc(S.get(owner, trade_id) or {"_id": trade_id})}


@router.post(API_EXIT_PATH)
async def my_trades_exit(trade_id: str, request: Request, email: str = Depends(require_primary_admin)):
    fields, why = parse_exit(_parse_json(await request.body()))
    if fields is None:
        return JSONResponse({"detail": why}, status_code=422)
    status, body = await asyncio.to_thread(post_exit, email, trade_id, fields, _now())
    return _respond(status, body)


def post_void(owner: str, trade_id: str, now: datetime) -> tuple:
    res = S.set_void(owner, trade_id, LG._aware(now))
    if res == "absent":
        return 404, {"detail": NOT_FOUND_TEXT}
    if res == "already":
        return 409, {"detail": VOID_TWICE_TEXT}
    if res != "ok":
        return 503, {"detail": WRITE_FAULT_TEXT}
    return 200, {"state": "ok", "id": trade_id}


@router.post(API_VOID_PATH)
async def my_trades_void(trade_id: str, email: str = Depends(require_primary_admin)):
    status, body = await asyncio.to_thread(post_void, email, trade_id, _now())
    return _respond(status, body)
