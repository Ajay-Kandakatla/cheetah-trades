"""📅 Long Term — the served payload of `GET /chart-maps/long-term` (spec §3.10). Pure.

`build_payload(seed, baseline, runs, forward_docs, zone_closes, *, now, owner)`:
  owner False -> exactly {state: "owner_only", reason, title} (critique C10);
  no run yet  -> "seed_only": every saved row from the at-save baseline;
  else        -> "ready": the latest weekly run doc.
The 🧭 zone column is the ONE request-time read (`zone_closes`, cache-only,
built by sources.pankaj_closes). The 🔔 block `zones.alert` (2026-11-12, pkzone
spec §3.7) reads the zone pass's stored session doc handed in by the API
(`zone_day`, `zone_live` = `zone_watch.serve_state`) — this module reads nothing. Every sentence comes from words.py; NaN / inf
are scrubbed by `growth.api._scrub`. His sheet's "Possible Action" column is
never served (HIS CALL §7 #22).
"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from . import constants as C
from . import criteria as CR
from . import forward as FW
from . import notices as N
from . import seed as SD
from . import words as W

TOP_KEYS = ("state", "reason", "title", "saved_on", "measured", "note", "not_a_signal", "his_words", "as_of",
            "digest", "zones", "started_moving", "changed", "categories", "forward", "history", "rules", "caveats")


def _scrub(o):
    from growth.api import _scrub as scrub
    return scrub(o)


def owner_only_payload() -> dict:
    return {"state": "owner_only", "reason": W.OWNER_ONLY_TEXT, "title": C.TITLE}


def error_payload(reason: str) -> dict:
    return {"state": "error", "reason": str(reason), "title": C.TITLE, "saved_on": C.SAVED_ON,
            "measured": C.MEASURED, "note": W.NOTE, "not_a_signal": W.NOT_A_SIGNAL}


def _leg_fields(cat, legs) -> list:
    out = []
    for lg in legs or []:
        if isinstance(lg, CR.Leg):
            d = lg.to_dict()
        elif isinstance(lg, dict):
            d = lg
        else:
            continue
        key = d.get("key")
        out.append({"category": cat, "key": key, "label": d.get("label") or W.leg_label(key),
                    "kind": d.get("kind") or CR.LEG_KINDS.get(cat, {}).get(key),
                    "text": d.get("text") or W.DASH, "verdict": d.get("verdict") or CR.UNKNOWN})
    return out


def _now_et(now) -> dt.datetime:
    if isinstance(now, dt.datetime):
        if now.tzinfo is not None:
            try:
                from zoneinfo import ZoneInfo
                return now.astimezone(ZoneInfo("America/New_York")).replace(tzinfo=None)
            except Exception:                                   # noqa: BLE001
                return now.replace(tzinfo=None)
        return now
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.now(ZoneInfo("America/New_York")).replace(tzinfo=None)
    except Exception:                                           # noqa: BLE001
        return dt.datetime.now()


def next_run_date(now, *, ran_this_week: bool = False, is_open=None) -> Optional[dt.date]:
    """The next weekly read: the last trading day of this ISO week if it is still ahead
    (before RUN_AFTER_ET on that day), else the next week's."""
    n = _now_et(now)
    rh, rm = (int(x) for x in C.RUN_AFTER_ET.split(":"))
    d = n.date()
    for wk in range(4):
        probe = d + dt.timedelta(days=7 * wk)
        ltd = FW.last_trading_day_of_week(probe, is_open)
        if not ltd:
            continue
        ltd_d = dt.date.fromisoformat(ltd)
        if wk == 0:
            if ran_this_week or ltd_d < d:
                continue
            if ltd_d == d and (n.hour, n.minute) >= (rh, rm):
                continue
        return ltd_d
    return None


def _pankaj_reads(seed, zone_closes) -> dict:
    order = SD.zone_order(seed)
    out = {}
    for sym, ent in SD.pankaj_entries(seed).items():
        c = (zone_closes or {}).get(sym) or {}
        out[sym] = CR.zone_read(ent["zones"], c.get("close"), c.get("date"), order)
    return out


def _pankaj_block(ent, read, order) -> dict:
    return {"tier_text": W.pankaj_tier_text(ent.get("tier"), ent.get("zt")),
            "zones_text": W.pankaj_zones_text(ent.get("zones") or {}, order),
            "zone_text": W.zone_text(read, ent.get("zones"))}


def _zones_section(seed, reads, zone_closes) -> dict:
    order = SD.zone_order(seed)
    ents = SD.pankaj_entries(seed)
    at_zone = []
    for zk in order:
        for sym, ent in ents.items():
            r = reads.get(sym) or {}
            if (r.get("in") or [None])[0] == zk:
                at_zone.append({"symbol": sym, "his_symbol": ent.get("sheet_symbol") or sym,
                                "zone_text": W.zone_text(r, ent.get("zones"))})
    dates = sorted(str(v.get("date")) for v in (zone_closes or {}).values() if v and v.get("date"))
    as_of = W.zones_strip_title(dates[-1]) if dates else "🧭 No cached closes for Pankaj's names"
    return {"as_of_text": as_of, "at_zone": at_zone, "rows_note": W.ZONES_ROWS_NOTE}


def _alert_now(seed, zone_closes, zone_live) -> list:
    """Who sits inside a zone now: the live pass's rows (per-row basis) or the closed-bar read; zone order, then seed
    order; one line per name (its first zone in `order`)."""
    order = SD.zone_order(seed)
    ents = SD.pankaj_entries(seed)
    if zone_live:
        rows = zone_live.get("rows") or {}
    else:
        rows = {sym: {"basis": "close", "price": r.get("close"), "date": r.get("close_date"), "in": r.get("in") or []}
                for sym, r in _pankaj_reads(seed, zone_closes).items()}
    out = []
    for zk in order:
        for sym, ent in ents.items():
            r = rows.get(sym) or {}
            if (r.get("in") or [None])[0] != zk:
                continue
            lo, hi = (list((ent.get("zones") or {}).get(zk) or (None, None)) + [None, None])[:2]
            if r.get("basis") == "live":
                when = _hhmm(r.get("at_epoch")) or (zone_live or {}).get("as_of_hhmm")
                text = W.zone_now_text("live", r.get("price"), when, zk, lo, hi, ent.get("tier"))
            else:
                text = W.zone_now_text("close", r.get("price"), r.get("date"), zk, lo, hi, ent.get("tier"))
            out.append({"symbol": sym, "his_symbol": ent.get("sheet_symbol") or sym, "zone": zk, "text": text})
    return out


def _hhmm(epoch) -> Optional[str]:
    """The ET wall time of a print stamp (the time the price printed), or None."""
    x = CR._num(epoch)
    if x is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        return dt.datetime.fromtimestamp(x, tz=ZoneInfo("America/New_York")).strftime("%H:%M")
    except (OverflowError, OSError, ValueError):
        return None


def _alert_log(seed, zone_day) -> list:
    """The session's reaches (first write wins on the state doc), sorted by time, zone order, seed order."""
    order = list(SD.zone_order(seed))
    seq = list(SD.pankaj_entries(seed))
    reaches = (zone_day or {}).get("reaches") or {}
    results = (zone_day or {}).get("results") or {}
    rows = []
    for rkey, rec in reaches.items():
        if not isinstance(rec, dict):
            continue
        sym, zk = rec.get("symbol"), rec.get("zone")
        res = results.get(rkey) if isinstance(results.get(rkey), dict) else {}
        rows.append(((str(rec.get("at_iso") or ""), order.index(zk) if zk in order else 99,
                      seq.index(sym) if sym in seq else 999),
                     {"symbol": sym, "his_symbol": rec.get("his_symbol") or sym, "zone": zk,
                      "at_text": f"{rec.get('at_hhmm') or W.DASH} ET",
                      "text": W.zone_log_text(rec.get("price"), zk, rec.get("lo"), rec.get("hi"), rec.get("tier")),
                      "push_text": W.zone_log_push_text(res.get("state"), rec.get("push_reason"))}))
    rows.sort(key=lambda t: t[0])
    return [r for _, r in rows]


def _zone_alert(seed, zone_closes, zone_live, zone_day, log_session) -> dict:
    """`zones.alert` (pkzone spec §3.7): who is inside a zone now + today's log of reaches."""
    live = bool(zone_live)
    dates = sorted(str(v.get("date")) for v in (zone_closes or {}).values()
                   if isinstance(v, dict) and v.get("date"))
    last_close = dates[-1] if dates else None
    now_rows = _alert_now(seed, zone_closes, zone_live if live else None)
    log_rows = _alert_log(seed, zone_day)
    day = log_session or last_close
    zl = zone_live or {}
    return {
        "title": W.ZONE_ALERT_TITLE,
        "live": live,
        "as_of_text": W.zone_alert_as_of(live, zl.get("as_of_hhmm"), last_close),
        "now": now_rows,
        "empty_text": W.ZONE_NOW_EMPTY if not now_rows else None,
        "reason": W.zone_reason_text(zl.get("reason"), zl.get("as_of_hhmm")) if live else None,
        "stale_text": W.zone_stale_text(zl.get("n_stale"), zl.get("n_names"), zl.get("prev_session")) if live else None,
        "push_text": W.zone_push_text(),
        "log_title": W.zone_log_title(day),
        "log": log_rows,
        "log_empty_text": W.zone_log_empty(day) if not log_rows else None,
    }


def _run_session(run) -> str:
    return str((run or {}).get("session") or "")


def _events_by_symbol(runs) -> dict:
    out: dict = {}
    for run in runs:
        for e in run.get("events") or []:
            out.setdefault(str(e.get("symbol")), []).append(
                {"date": e.get("date") or _run_session(run), "kind": e.get("kind"), "text": e.get("text")})
    for sym in out:
        out[sym].sort(key=lambda e: N.KIND_ORDER.index(e["kind"]) if e["kind"] in N.KIND_ORDER else 99)
        out[sym].sort(key=lambda e: str(e["date"]), reverse=True)
    return out


def _sources_list(run) -> list:
    out = []
    for key, s in ((run or {}).get("sources") or {}).items():
        s = s or {}
        ok = bool(s.get("ok"))
        if ok:
            txt = f"read {s.get('as_of')}" if s.get("as_of") else "read"
        else:
            txt = f"not read — {s.get('reason') or 'no data'}"
        out.append({"key": key, "label": W.SOURCE_LABELS.get(key, key), "as_of_text": txt, "ok": ok})
    return out


def _caveats(seed) -> list:
    allowed = W.NOT_A_SIGNAL.rstrip(".")
    out = []
    for c in seed.get("caveats") or []:
        if not isinstance(c, str):
            continue
        out.append(W.NOT_A_SIGNAL if c.strip().rstrip(".") == allowed else c)
    return out


def build_payload(seed, baseline, runs, forward_docs, zone_closes, *, now=None, owner: bool, zone_live=None,
                  zone_day=None, log_session=None) -> dict:
    """The served dict (already NaN-scrubbed). Never raises: a failure is state "error" + reason.
    zone_live / zone_day / log_session: the 🔔 zone pass's stored doc (None = no pass read)."""
    if not owner:
        return owner_only_payload()
    try:
        if seed is None:
            try:
                seed = SD.load()
            except SD.SeedChanged as exc:
                return error_payload(f"The saved list file changed: {exc}")
            except OSError as exc:
                return error_payload(f"The saved list file could not be read: {exc}")
        out = _build(seed, baseline or {}, list(runs or []), list(forward_docs or []), zone_closes or {}, now)
        out["zones"]["alert"] = _zone_alert(seed, zone_closes or {}, zone_live, zone_day, log_session)
        return _scrub(out)
    except Exception as exc:                                    # noqa: BLE001
        return error_payload(f"The Long Term list could not be built: {exc}")


def _build(seed, baseline, runs, forward_docs, zone_closes, now) -> dict:
    runs = sorted(runs, key=lambda r: (_run_session(r), str(r.get("_id") or "")), reverse=True)
    latest = runs[0] if runs else None
    state = "ready" if latest else "seed_only"
    chips = SD.chips(seed)
    order = SD.zone_order(seed)
    pk = SD.pankaj_entries(seed)
    reads = _pankaj_reads(seed, zone_closes)
    b_names = baseline.get("names") or {}
    b_cats = baseline.get("categories") or {}
    ev_by_sym = _events_by_symbol(runs)
    session = _run_session(latest) if latest else None
    nxt = next_run_date(now, ran_this_week=bool(latest and latest.get("iso_week") and _iso_week(now)
                                                 == latest.get("iso_week")))
    nxt_iso = nxt.isoformat() if nxt else None

    rows_by_cat: dict = {c["key"]: [] for c in SD.categories(seed)}
    changed, started = [], []
    for sym, cats in chips.items():
        save = N.at_save(sym, baseline)
        bn = b_names.get(sym) or {}
        cur = ((latest or {}).get("names") or {}).get(sym) or {} if latest else {}
        src = cur if latest else bn
        fields = []
        for cat in cats:
            if cat == C.PANKAJ_KEY:
                continue
            if latest:
                legs = (cur.get("legs") or {}).get(cat)
            else:
                brow = (b_cats.get(cat) or {}).get(sym) or {}
                legs = brow.get("legs")
                if legs is None and brow.get("values") is not None:
                    legs = CR.legs(cat, brow["values"])
            fields.extend(_leg_fields(cat, legs))
        if latest:
            section = N.section_for(cur.get("flags"), cur, session)
            status = {"key": section, "text": W.STATUS_TEXTS[section]}
        else:
            section = "saved"
            status = {"key": "saved", "text": W.seed_only_status(nxt_iso)}
        stage_now = src.get("stage")
        row = {
            "symbol": sym,
            "name": src.get("name") or bn.get("name") or W.DASH,
            "sector": src.get("sector") or bn.get("sector") or W.DASH,
            "chips": [{"key": c, "label": W.CATEGORY_LABELS.get(c, c)} for c in cats],
            "stage": {"now": stage_now, "label": W.stage_label(stage_now, src.get("stage_label")) or None,
                      "at_save": save.get("stage"),
                      "text": W.stage_text(stage_now, src.get("stage_label"), save.get("stage"))},
            "sales": {"tier": src.get("sales_tier"), "at_save": save.get("sales_tier"),
                      "text": W.sales_text(src.get("sales_yoy_pct"), src.get("sales_tier"),
                                           src.get("sales_q_end"), src.get("sales_read_on"))},
            "status": status,
            "fields": fields,
            "events": ev_by_sym.get(sym, []),
            "pankaj": _pankaj_block(pk[sym], reads.get(sym), order) if sym in pk else None,
            "caveat_tag": W.CAVEAT_TAGS.get(cats[0], "UNMEASURED"),
        }
        if section == "changed":
            warn_dates = [e["date"] for e in row["events"] if e["kind"] in ("stage_drop", "sales_drop", "fundamental")]
            changed.append((max(warn_dates) if warn_dates else "", sym, row))
        else:
            rows_by_cat.setdefault(cats[0], []).append(row)
        if section == "started_moving":
            ev = next((e for e in row["events"] if e["kind"] == "started_moving"), None)
            started.append({"symbol": sym, "date": (cur.get("flags") or {}).get("started_moving_on") or session,
                            "text": ev["text"] if ev else W.started_moving_text(sym, src.get("stage_label"))})
    changed.sort(key=lambda t: t[1])
    changed.sort(key=lambda t: t[0], reverse=True)

    moved_by_cat: dict = {}
    for e in (latest or {}).get("events") or []:
        if e.get("kind") == "moved":
            for cat in e.get("categories") or []:
                moved_by_cat.setdefault(cat, []).append(e.get("text"))

    categories = []
    for cdoc in SD.categories(seed):
        key = cdoc["key"]
        if key == C.PANKAJ_KEY:
            top, top_text = [], None
        elif latest:
            top = [{"symbol": t.get("symbol"), "name": t.get("name") or W.DASH, "sector": t.get("sector") or W.DASH,
                    "rank_text": t.get("rank_text") or W.DASH, "new": bool(t.get("new"))}
                   for t in ((latest.get("top") or {}).get(key) or [])]
            top_text = W.top_text(key, len(top))
        else:
            top, top_text = [], W.TOP_PENDING_TEXT
        moved = moved_by_cat.get(key)
        categories.append({
            "key": key, "label": W.CATEGORY_LABELS.get(key, cdoc.get("label") or key),
            "source_tab": W.SOURCE_TABS.get(key, W.DASH), "criteria_text": W.criteria_text(key),
            "caveat": W.caveat(key), "caveat_tag": W.CAVEAT_TAGS.get(key, "UNMEASURED"),
            "also_text": W.also_text(cdoc), "rows": rows_by_cat.get(key, []),
            "moved_text": "; ".join(moved) if moved else None, "top": top, "top_text": top_text,
        })

    base = next((d for d in forward_docs if d.get("_id") == "base"), None)
    points = [d for d in forward_docs if d.get("_id") != "base"]
    fwd = FW.block(points, session, base=base, n_headline=len(SD.screened_names(seed)))
    fwd["series"] = list(W.FORWARD_SERIES)

    digest = None
    if latest and latest.get("digest"):
        d = latest["digest"]
        digest = {"title": d.get("title"), "lines": list(d.get("lines") or []),
                  "items": [{"symbol": i.get("symbol"), "kind": i.get("kind"), "text": i.get("text")}
                            for i in d.get("items") or []],
                  "pushed_text": W.pushed_text(rings=d.get("rings"))}

    history = []
    for run in runs:
        d = run.get("digest") or {}
        n_events: dict = {}
        for e in run.get("events") or []:
            n_events[e.get("kind")] = n_events.get(e.get("kind"), 0) + 1
        history.append({"week": run.get("iso_week") or run.get("_id"), "session": _run_session(run),
                        "text": d.get("title") or W.DASH, "n_events": n_events,
                        "n_new_in_top": int(d.get("n_new_in_top") or 0)})

    return {
        "state": state,
        "reason": None,
        "title": C.TITLE,
        "saved_on": C.SAVED_ON,
        "measured": C.MEASURED,
        "note": W.NOTE,
        "not_a_signal": W.NOT_A_SIGNAL,
        "his_words": SD.his_words(seed),
        "as_of": {"week": (latest or {}).get("iso_week") or (latest or {}).get("_id"),
                  "session": session or C.SAVED_ON,
                  "built_at_iso": (latest or {}).get("built_at_iso"),
                  "next_run_text": W.next_run_text(nxt) if nxt else W.next_run_text(None),
                  "sources": _sources_list(latest)},
        "digest": digest,
        "zones": _zones_section(seed, reads, zone_closes),
        "started_moving": sorted(started, key=lambda s: s["symbol"]),
        "changed": [t[2] for t in changed],
        "categories": categories,
        "forward": fwd,
        "history": history,
        "rules": W.rules_lines(include_pankaj=True),
        "caveats": _caveats(seed),
    }


def _iso_week(now) -> Optional[str]:
    try:
        y, w, _ = _now_et(now).date().isocalendar()
        return f"{y}-W{w:02d}"
    except Exception:                                           # noqa: BLE001
        return None
