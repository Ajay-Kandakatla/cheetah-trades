"""📬 Phone alerts — delivery receipts split per registration, read-only (2026-11-24, spec ggrun rev 2 §4 `phone-diag`).

Ajay, verbatim (2026-11-24): "also i am not getting the alerts on phone".

What it reads (nothing else, never a write): the owner's rows of `push_subscriptions` and the owner's + broadcast rows of
`push_history` for the last DAYS days, both through `push.subs._get_db()`; for Q6 the Watch's cross claims
(`gajjala_watch_alerts`), its tiles' held reasons (`gajjala_watch_tiles`) and its `latest` state doc. Only the
`push.subs.OWNER_KEEP_SET` kinds are counted.

What it prints: per registration (an ORDINAL LETTER by `created_at`, the device word `push.receipts.device_word(label)`,
the registration date — never an endpoint, a key, a hash, a push id or an email) × day × kind: targeted, accepted
(`targets[].ok`), rejected (the push service refused — never "no receipt"), receipts; the first / last receipt; the
receipt delay; and for every iPhone registration an hour-of-day table (ET) of receipts ÷ accepted. A row without
`push_id` is counted "before receipts"; a row that targeted nobody is its own count.

What a receipt proves: frontend/public/sw.js POSTs it only AFTER `showNotification` resolves. A receipt = the device
showed it. NO receipt = the POST did not land — the push may not have arrived, OR it was shown and the POST failed.

  docker exec -i -w /app cheetah-market-app-api-1 python - < backend/scripts/push_receipts_by_device_probe.py
  python -m scripts.push_receipts_by_device_probe [--days 7]          (from backend/)

The connection helper may ensure its two subscription indexes once per process (an index, not a row). UNMEASURED:
counts, not an edge.
"""
from __future__ import annotations

import argparse
import logging
import string
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Optional
from zoneinfo import ZoneInfo

_FILE = globals().get("__file__")
if not __package__ and _FILE and not str(_FILE).startswith("<"):
    _BACKEND = str(Path(_FILE).resolve().parents[1])
    if _BACKEND not in sys.path:
        sys.path[:0] = [_BACKEND]

from push import receipts as R            # noqa: E402
from push import subs as S                # noqa: E402

ET = ZoneInfo("America/New_York")
DAYS = 7                                   # the spec's window ("last 7 days")
MAC_KIND = "mac"                           # push.subs' own exclusion ({"kind": {"$ne": "mac"}}) — no Web Push endpoint; the
                                           # targets list is NOT read through push.subs: its backfill may write a pref
IPHONE_WORD = "iPhone"                     # receipts._OS_WORDS' first word
BEFORE = "before receipts"
SUB_FIELDS = {"label": 1, "created_at": 1, "updated_at": 1, "kind": 1, "prefs": 1, "user_email": 1, "endpoint": 1}
HIST_FIELDS = {"ts": 1, "kind": 1, "total": 1, "sent": 1, "failed": 1, "targets": 1, "receipts": 1, "push_id": 1,
               "user_email": 1, "ticker": 1}


# ── pure helpers ─────────────────────────────────────────────────────────────
def _epoch(v) -> Optional[int]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, datetime):
        return int((v if v.tzinfo else v.replace(tzinfo=timezone.utc)).timestamp())
    return None


def _et(ts: Optional[int]) -> Optional[datetime]:
    return None if ts is None else datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(ET)


def _day(ts) -> str:
    d = _et(_epoch(ts))
    return d.strftime("%m-%d") if d else "?"


def _hm(ts) -> str:
    d = _et(_epoch(ts))
    return d.strftime("%m-%d %H:%M") if d else "—"


def letter(i: int) -> str:
    """0 → A … 25 → Z, 26 → AA (an ordinal, never an id)."""
    s, n = "", i
    while True:
        s = string.ascii_uppercase[n % 26] + s
        n = n // 26 - 1
        if n < 0:
            return s


def _hash_of(sub: dict) -> str:
    """The stored form of a registration (receipts.endpoint_hash) — used to join, never printed."""
    if sub.get("sub"):
        return str(sub["sub"])
    return R.endpoint_hash(sub.get("endpoint"))


def registrations(subscription_rows: list) -> list:
    """His Web Push registrations, ordered by created_at (then label), each named "A · iPhone · reg 10-08"."""
    rows = [r for r in (subscription_rows or []) if isinstance(r, dict) and r.get("kind") != MAC_KIND]
    rows.sort(key=lambda r: (_epoch(r.get("created_at")) is None, _epoch(r.get("created_at")) or 0,
                             str(r.get("label") or "")))
    out = []
    for i, r in enumerate(rows):
        word = R.device_word(r.get("label"))
        name = f"{letter(i)} · {word} · reg {_day(r.get('created_at'))}"
        out.append({"letter": letter(i), "word": word, "name": name, "hash": _hash_of(r),
                    "created": _epoch(r.get("created_at")), "prefs_at": _epoch(r.get("updated_at")),
                    "prefs": dict(r.get("prefs") or {})})
    return out


def history_filter(owner: str, since: int) -> dict:
    """The ONE push_history filter: his rows or a broadcast (None) — never another user's."""
    return {"ts": {"$gte": int(since)}, "$or": [{"user_email": (owner or "").lower()}, {"user_email": None}]}


def subs_filter(owner: str) -> dict:
    return {"user_email": (owner or "").lower()}


def _cell():
    return {"targeted": 0, "accepted": 0, "rejected": 0, "receipts": 0}


def summarize(history_rows: list, subscription_rows: list, now, *, owner: Optional[str] = None,
              kinds=None, days: int = DAYS, last_receipt_any: Optional[dict] = None) -> dict:
    """The whole read, pure. `now` = epoch seconds or an aware datetime. `last_receipt_any` = {hash: ts} of the newest
    receipt each registration ever posted (main reads it; optional)."""
    now_ts = _epoch(now) if _epoch(now) is not None else int(time.time())
    keep = tuple(sorted(kinds if kinds is not None else S.OWNER_KEEP_SET))
    regs = registrations(subscription_rows)
    by_hash = {g["hash"]: g for g in regs}
    since = now_ts - int(days) * 86400
    own = (owner or "").lower() if owner is not None else None

    cells = defaultdict(_cell)                         # (letter, day, kind)
    kind_tot = defaultdict(_cell)                      # (letter, kind)
    hours = defaultdict(_cell)                         # (letter, hour)
    reg_tot = {g["letter"]: dict(_cell(), first=None, last=None, delays=[], last_accepted=None) for g in regs}
    rows_dk = defaultdict(lambda: {"rows": 0, BEFORE: 0, "zero_target": 0, "nobody_showed": 0, "sent": 0, "total": 0})
    gone = defaultdict(lambda: {"accepted": 0, "rejected": 0, "receipts": 0})   # device word → targets not his now
    skipped_other_user = 0
    today = _et(now_ts).strftime("%m-%d")
    today_kinds = defaultdict(int)
    last_row = {}

    for d in history_rows or []:
        if not isinstance(d, dict):
            continue
        kind = d.get("kind")
        ts = _epoch(d.get("ts"))
        if kind not in keep or ts is None or ts < since or ts > now_ts + 60:
            continue
        if own is not None and d.get("user_email") is not None and str(d.get("user_email")).lower() != own:
            skipped_other_user += 1                    # defensive: the Mongo filter already refuses these
            continue
        day = _day(ts)
        rk = rows_dk[(day, kind)]
        rk["rows"] += 1
        rk["sent"] += int(d.get("sent") or 0)
        rk["total"] += int(d.get("total") or 0)
        if day == today:
            today_kinds[kind] += 1
        if kind not in last_row or ts > last_row[kind]:
            last_row[kind] = ts
        if not d.get("push_id"):
            rk[BEFORE] += 1                            # never "nobody showed it"
            continue
        targets = [t for t in (d.get("targets") or []) if isinstance(t, dict)]
        if int(d.get("total") or 0) <= 0 or not targets:
            rk["zero_target"] += 1
            continue
        recs = {}
        for rc in d.get("receipts") or []:
            if isinstance(rc, dict) and rc.get("sub") and rc["sub"] not in recs:
                recs[rc["sub"]] = rc
        if not recs:
            rk["nobody_showed"] += 1
        hour = _et(ts).hour
        for t in targets:
            h = t.get("sub")
            g = by_hash.get(h)
            ok = bool(t.get("ok"))
            if g is None:
                w = gone[str(t.get("device") or R.DEFAULT_DEVICE_WORD)]
                w["accepted" if ok else "rejected"] += 1
                w["receipts"] += int(h in recs)
                continue
            L = g["letter"]
            for c in (cells[(L, day, kind)], kind_tot[(L, kind)], reg_tot[L]):
                c["targeted"] += 1
                if not ok:
                    c["rejected"] += 1                 # the service refused: never counted as "no receipt"
                    continue
                c["accepted"] += 1
                c["receipts"] += int(h in recs)
            if not ok:
                continue
            rt = reg_tot[L]
            rt["last_accepted"] = max(rt["last_accepted"] or 0, ts)
            rt.setdefault("accepted_ts", []).append(ts)
            hc = hours[(L, hour)]
            hc["targeted"] += 1
            hc["accepted"] += 1
            if h in recs:
                hc["receipts"] += 1
                rt["last_row_with_receipt"] = max(rt.get("last_row_with_receipt") or 0, ts)
                rc = recs[h]
                at = R._shown_at(rc.get("shown_at")) or _epoch(rc.get("at"))
                if at is not None:
                    rt["first"] = at if rt["first"] is None else min(rt["first"], at)
                    rt["last"] = at if rt["last"] is None else max(rt["last"], at)
                    rt["delays"].append(max(0, at - ts))

    for g in regs:
        rt = reg_tot[g["letter"]]
        cut = rt.pop("last_row_with_receipt", None)
        acc = rt.pop("accepted_ts", [])
        rt["accepted_after_last_receipt"] = sum(1 for t in acc if cut is None or t > cut)
        rt["delay_median_s"] = int(median(rt["delays"])) if rt["delays"] else None
        rt["delay_max_s"] = max(rt["delays"]) if rt["delays"] else None
        rt["last_receipt_any"] = _epoch((last_receipt_any or {}).get(g["hash"]))
        g["keep_off"] = [k for k in keep if g["prefs"].get(k) is not True]
        g["quiet"] = bool(g["prefs"].get("quiet_hours_enabled"))
    targetable = {k: sum(1 for g in regs if g["prefs"].get(k) is True) for k in keep}
    return {"now": now_ts, "days": int(days), "kinds": keep, "regs": regs, "cells": dict(cells),
            "kind_tot": dict(kind_tot), "hours": dict(hours), "reg_tot": reg_tot, "rows": dict(rows_dk),
            "gone": dict(gone), "skipped_other_user": skipped_other_user, "today": today,
            "today_kinds": dict(today_kinds), "last_row": last_row, "targetable": targetable}


def summarize_watch(claims: list, tiles: list, session_iso: Optional[str], *, held_reasons=(), states=()) -> dict:
    """Q6 — the Watch's 1-minute cross pushes for one session: claims by state; tiles' held reasons on that session."""
    by_state = defaultdict(int)
    for c in claims or []:
        if isinstance(c, dict) and (session_iso is None or str(c.get("date") or "")[:10] == session_iso):
            by_state[str(c.get("state") or "?")] += 1
    held = defaultdict(int)
    older = 0
    for t in tiles or []:
        for _tf, h in ((t or {}).get("held") or {}).items():
            if not isinstance(h, dict):
                continue
            bt = h.get("bar_t")
            bday = (str(bt)[:10] if isinstance(bt, str) else
                    (_et(_epoch(bt)).strftime("%Y-%m-%d") if _epoch(bt) is not None else ""))
            if session_iso and bday != session_iso:
                older += 1
                continue
            held[str(h.get("reason") or "?")] += 1
    order = list(states) + sorted(k for k in by_state if k not in states)
    horder = list(held_reasons) + sorted(k for k in held if k not in held_reasons)
    return {"session": session_iso, "claims": {k: by_state.get(k, 0) for k in order},
            "held": {k: held.get(k, 0) for k in horder if held.get(k, 0)}, "held_older_sessions": older}


def _pct(k: int, n: int) -> str:
    return f"{k}/{n}" + (f" ({100 * k / n:.0f}%)" if n else "")


def render(summary: dict, watch: Optional[dict] = None, state: Optional[dict] = None) -> str:
    """The printed text. Carries no endpoint, key, hash, push id or email by construction (only letters, device
    words, dates, kinds, counts)."""
    s = summary
    L = [f"push receipts by registration — window {s['days']} days to {_hm(s['now'])} ET · keep-set kinds {len(s['kinds'])}"]
    L.append("")
    L.append("REGISTRATIONS (Web Push only; ordinal by created_at)")
    for g in s["regs"]:
        rt = s["reg_tot"][g["letter"]]
        L.append(f"  {g['name']} | prefs last written {_hm(g['prefs_at'])} | keep-set OFF: "
                 f"{', '.join(g['keep_off']) or 'none'} | quiet hours {'ON' if g['quiet'] else 'off'}")
        L.append(f"      targeted {rt['targeted']} · accepted {rt['accepted']} · rejected {rt['rejected']} · "
                 f"receipts {_pct(rt['receipts'], rt['accepted'])} · first receipt {_hm(rt['first'])} · "
                 f"last receipt {_hm(rt['last'])} · last accepted {_hm(rt['last_accepted'])} · newest receipt ever "
                 f"{_hm(rt['last_receipt_any'])} · accepted after the last receipt {rt['accepted_after_last_receipt']} · delay median {rt['delay_median_s']} s max {rt['delay_max_s']} s")
    L.append("")
    L.append("TARGETABLE NOW per keep-set kind (pref true; quiet hours shown above)")
    L.append("  " + " · ".join(f"{k} {n}" for k, n in s["targetable"].items()))
    L.append("")
    L.append("ROWS per day × kind (rows · before receipts · zero-target · rows nobody showed · sent/total)")
    for (day, kind), r in sorted(s["rows"].items()):
        L.append(f"  {day} {kind}: {r['rows']} · {r[BEFORE]} · {r['zero_target']} · {r['nobody_showed']} · "
                 f"{r['sent']}/{r['total']}")
    L.append("")
    L.append("RECEIPTS ÷ ACCEPTED per registration × kind (window)")
    for g in s["regs"]:
        parts = [f"{k} {_pct(c['receipts'], c['accepted'])}" + (f" rej {c['rejected']}" if c["rejected"] else "")
                 for (Lt, k), c in sorted(s["kind_tot"].items()) if Lt == g["letter"]]
        L.append(f"  {g['letter']} {g['word']}: " + (" · ".join(parts) or "no targets"))
    L.append("")
    L.append("RECEIPTS ÷ ACCEPTED per registration × day (all keep-set kinds)")
    days = sorted({d for (_l, d, _k) in s["cells"]})
    for g in s["regs"]:
        parts = []
        for d in days:
            a = sum(c["accepted"] for (Lt, dd, _k), c in s["cells"].items() if Lt == g["letter"] and dd == d)
            k = sum(c["receipts"] for (Lt, dd, _k), c in s["cells"].items() if Lt == g["letter"] and dd == d)
            if a:
                parts.append(f"{d} {k}/{a}")
        L.append(f"  {g['letter']} {g['word']}: " + (" · ".join(parts) or "none"))
    L.append("")
    L.append("PER DAY × KIND × REGISTRATION (receipts/accepted)")
    for d in days:
        for k in s["kinds"]:
            row = [f"{g['letter']} {s['cells'][(g['letter'], d, k)]['receipts']}/{s['cells'][(g['letter'], d, k)]['accepted']}"
                   for g in s["regs"] if (g["letter"], d, k) in s["cells"]]
            if row:
                L.append(f"  {d} {k}: " + " · ".join(row))
    for g in s["regs"]:
        if IPHONE_WORD not in g["word"]:
            continue
        L.append("")
        L.append(f"HOUR OF DAY (ET) — {g['name']} (receipts/accepted)")
        hs = sorted(h for (Lt, h) in s["hours"] if Lt == g["letter"])
        L.append("  " + (" · ".join(f"{h:02d}h {s['hours'][(g['letter'], h)]['receipts']}/"
                                    f"{s['hours'][(g['letter'], h)]['accepted']}" for h in hs) or "no accepted targets"))
    L.append("")
    L.append("TARGETS NOT ON A CURRENT REGISTRATION OF HIS (removed since, or another user's on a broadcast)")
    L.append("  " + (" · ".join(f"{w}: accepted {c['accepted']} rejected {c['rejected']} receipts {c['receipts']}"
                                for w, c in sorted(s["gone"].items())) or "none"))
    L.append(f"  other users' rows skipped by the pure filter: {s['skipped_other_user']}")
    L.append("")
    L.append(f"TODAY {s['today']} keep-set rows: " +
             (" · ".join(f"{k} {n}" for k, n in sorted(s["today_kinds"].items())) or "none"))
    L.append("LAST keep-set row per kind: " +
             (" · ".join(f"{k} {_hm(t)}" for k, t in sorted(s["last_row"].items())) or "none"))
    if watch is not None:
        L.append("")
        L.append(f"WATCH 1-min cross pushes — session {watch['session']}: claims by state "
                 + " · ".join(f"{k} {n}" for k, n in watch["claims"].items()))
        L.append("  tiles' held reasons that session: " +
                 (" · ".join(f"{k} {n}" for k, n in watch["held"].items()) or "none") +
                 f" · held marks from older sessions {watch['held_older_sessions']}")
    if state is not None:
        L.append(f"WATCH loop latest: at {_hm(state.get('at'))} · session {state.get('session')} · names "
                 f"{state.get('n_names')} · reason {state.get('reason')}")
    return "\n".join(L)


# ── main (read-only) ─────────────────────────────────────────────────────────
def main(argv=None) -> int:
    logging.disable(logging.CRITICAL)
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=DAYS)
    a = ap.parse_args(argv)
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala_watch import constants as WC
    db = S._get_db()
    if db is None:
        print("store unavailable")
        return 1
    owner = S._owner_email()
    now = int(time.time())
    subs_rows = list(db.push_subscriptions.find(subs_filter(owner), SUB_FIELDS))
    hist = list(db.push_history.find(history_filter(owner, now - a.days * 86400), HIST_FIELDS))
    last_any = {}
    for r in subs_rows:
        h = _hash_of(r)
        doc = next(iter(db.push_history.find({"receipts.sub": h, "$or": [{"user_email": owner}, {"user_email": None}]},
                                             {"ts": 1}).sort("ts", -1).limit(1)), None)
        if doc:
            last_any[h] = doc.get("ts")
    summ = summarize(hist, subs_rows, now, owner=owner, days=a.days, last_receipt_any=last_any)
    claims_coll = db[WC.COLL_ALERTS]
    last = next(iter(claims_coll.find({}, {"date": 1}).sort("date", -1).limit(1)), None)
    session_iso = str((last or {}).get("date") or "")[:10] or None
    claims = list(claims_coll.find({"date": session_iso}, {"date": 1, "state": 1})) if session_iso else []
    tiles = list(db[WC.COLL_TILES].find({}, {"held": 1}))
    watch = summarize_watch(claims, tiles, session_iso, held_reasons=WC.HELD_REASONS, states=AL.FADE_CROSS_STATES)
    state = db[WC.COLL_STATE].find_one({"_id": WC.STATE_LATEST_ID}, {"at": 1, "session": 1, "n_names": 1, "reason": 1})
    print(render(summ, watch, state or {}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
