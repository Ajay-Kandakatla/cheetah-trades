"""🚩 Gajjala's tab — the payload of GET /chart-maps/gajjala (BUILD_SPEC §3.4.1, 2026-10-13).

WHAT. One served board per sub-tab: the five setups (🚩 💋 ➖ 🌀 🎾), ☀️ Premarket, 🌙 Post-market and 📓 Playbook.
Every sentence the card prints is built here — state labels, the situational strip, the chips, the push mode — so
the frontend types only structural words.

READS MONGO ONLY. `build()` never scans, never fetches a bar and never calls a provider: the 5-minute cron pass
(run.py) writes `gajjala_scan` / `_reads` / `_passes` / `_post` / `_ah_carry` / `_alerts` / `_halts` / `_daily`, and
this module reads them through store.py. The route adds ONE live fan-out for the shown tiles' now-line (the Support
precedent) and, on 🏁 Track record only, ONE 1-minute read of today's alerted names (ledger.today_read, memo
LEDGER_TODAY_MEMO_SEC, never written) that it hands to `build(today=…)`; nothing else. A missing collection is the
documented "no data" answer, never an error.

ORDER. Setup sub-tabs list the listed names whose read is aplus / triggered / forming / partial / stopped, ordered by
his setup state (A+ newest first, then closest to its trigger): BUILD_SPEC §3.4.1 ordering keys, exactly. invalid /
none reads are counted, never tiled. ☀️ = volume first (S8 1:21:56 "I sort by volume"), % change as a toggle, the
carried after-hours movers after today's names. 🌙 = after-hours gain first, plus today's A+ recap (states only).

NOT SEPA. Nothing here imports or cites another method's gate; the tile link is the house ticker page. UNMEASURED:
no study here says these setups win; nothing here trades, enters a lane or sizes a position.

🧠 POTENTIAL · 📈 TRACK (2026-10-15, BUILD_SPEC4 §3.9 / WP-B). Ajay, three messages verbatim: "In Gajjalas setup I
wanna find potential stocks this shows me what has happened I am trying to setup for this tab to act like Gajjalas
brain. So create a potential category in this section." / "In all the sub tab and add a track and alert to show me new
potential is added everyday." / "Give me an alert all continous tracker on these specifically when I get alert I will
jump on to ride the wave". Every setup sub serves a `potential` strip (its own forming reads that `potential.py` calls a
potential); the 🧠 Potential sub rolls them up (one tile per symbol), with the 📈 Track (today's first sightings and the
last session's, read from the tracker docs the pass wrote) and the 👀 watch line. Every rule, word and order comes from
`potential.py` (the ONE engine) — this module re-derives none and types no number. UNMEASURED.

🔄 SCAN ON OPEN · 🎯 A+ (2026-10-15, BUILD_SPEC5 §3.6 / WP-B). Ajay, verbatim: "When ever I open Gajjala's intiate a
new scan of stocks.  In that moment and if there are any enterable stocks on the top which I see in potential i guess".
The pass itself runs elsewhere (chart_maps/gajjala/on_demand.py spawns `python -m chart_maps.gajjala.run --on-demand`);
this module still READS MONGO ONLY and serves two more blocks on every sub: `scan` (the "🔄 scanned on open HH:MM ET ·
bars through HH:MM" / "last pass HH:MM ET" line, "scanning…" while the pass lease is held — closed bars only, never a
newer bar) and `enterable` (🎯 the A+ reads of the LATEST pass — the card's own state `aplus`, traded through the trigger
and the bar closed, DECISIONS5 K1 + AMENDMENTS5 A11 — served only while the 5-minute cron pass is current, A10). `pass`
gains `at` (one stamp, `pass_stamp`, shared with the POST) and `on_demand`; `pass.stale` reads the CRON pass, so opens
alone never hide a dead cron (A10). A card whose read is older than the pass shown carries "read at the HH:MM ET pass".
An open rings no device (both push gates run dry on it, K2). UNMEASURED — not a recommendation.

🏁 TRACK RECORD (2026-10-16, BUILD_SPEC9 §3.7 / WP-B). Ajay, verbatim: "also can you track all Gajjals stocks and keep a
new tab to show wins vs losses. To see a percentage and the ticker." / "We are not looking for winners just in time but
when they got in to our alerts if they made it or not. Like XLAB today was a winner I made good money on it". The tenth
sub, LAST: every alert that rang, graded by GG's trade math — ledger.py owns the rows, the grader and every served
string (`served_block`); this module only routes `?sub=track_record&span=…` to it and serves the chip count
(`count_today`). Operational accounting of the alerts as sent, not a study — UNMEASURED.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, time as dtime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import potential as PT                # 🧠 the ONE potential engine (it imports tab lazily)
from daytrading.data import ET_RTH_OPEN as _RTH_OPEN          # the house session clock, never retyped

log = logging.getLogger("chart_maps.gajjala.tab")

ET = ZoneInfo("America/New_York")
TILE_STATES = ("aplus", "triggered", "forming", "partial", "stopped")
COUNT_STATES = ("aplus", "forming", "partial", "triggered", "stopped", "invalid", "none")
MARKED_STATES = ("aplus", "triggered", "stopped")
SUB_KEYS = tuple(k for k, _e, _l in GC.SUBS)
SUB_META = {k: (e, label) for k, e, label in GC.SUBS}
LIST_SUBS = ("premarket", "postmarket")
TFS = ("5m", "15m")
SORTS_PM = (("volume", "Volume"), ("change", "% change"))
SORT_PM_DEFAULT = "volume"
SESSION_BADGE = {"premarket": "☀️ pre-market", "rth": "RTH", "afterhours": "🌙 after-hours",
                 "closed": "closed · last session"}
BADGE_CLOSED_TODAY = "closed"                   # after the last pass on a session day: today's board, no pass left
OUTSIDE_RTH = {"premarket": "pre-market — he uses limit orders only and less size outside regular hours (S8 1:16:35)",
               "afterhours": "after-hours — he uses limit orders only and less size outside regular hours (S8 1:16:35)"}
UNMEASURED = "UNMEASURED"


# ── small helpers ─────────────────────────────────────────────────────────────────────────────────────────────────
def _f(x) -> Optional[float]:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v and v not in (float("inf"), float("-inf")) else None


def _clock() -> datetime:
    """The wall clock (tests pin it)."""
    return datetime.now(timezone.utc)


def _et(now: Optional[datetime]) -> datetime:
    now = now or _clock()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    return now.astimezone(ET)


def _hhmm(t) -> Optional[str]:
    """"HH:MM" of an ET bar stamp ("YYYY-MM-DD HH:MM") or a datetime (shown in ET)."""
    if isinstance(t, datetime):
        return _et(t).strftime("%H:%M")
    if isinstance(t, str) and len(t) >= 16:
        return t[11:16]
    return None


def _px(x) -> str:
    v = _f(x)
    if v is None:
        return "—"
    return f"{v:.4f}".rstrip("0").rstrip(".") if v < 1 else f"{v:.2f}"


def _compact(n) -> Optional[str]:
    v = _f(n)
    if v is None or v < 0:
        return None
    for div, suf in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if v >= div:
            return f"{v / div:.1f}{suf}"
    return f"{v:.0f}"


def _pct(x, signed: bool = True) -> Optional[str]:
    v = _f(x)
    if v is None:
        return None
    return f"{v:+.1f}%" if signed else f"{v:.1f}%"


def _plain(o):
    """JSON-safe copy: datetimes → ISO strings, dates → ISO, tuples → lists (NaN is _scrub's job)."""
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, date):
        return o.isoformat()
    if isinstance(o, dict):
        return {str(k): _plain(v) for k, v in o.items() if k != "_id"}
    if isinstance(o, (list, tuple)):
        return [_plain(v) for v in o]
    return o


def _text(v) -> Optional[str]:
    if isinstance(v, str):
        return v if v.strip() else None
    if isinstance(v, dict) and isinstance(v.get("text"), str) and v["text"].strip():
        return v["text"]
    return None


def _store(store):
    if store is not None:
        return store
    from chart_maps.gajjala import store as ST
    return ST.default()


def _alerts_find(store, ids: list) -> list:
    try:
        c = store.alerts_coll()
    except Exception:                                               # noqa: BLE001
        c = None
    if c is None or not ids:
        return []
    try:
        return list(c.find({"_id": {"$in": ids}}))
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: alerts read failed: %s", exc)
        return []


# ── the session the board shows ───────────────────────────────────────────────────────────────────────────────────
def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return is_market_day(d)


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _open_et() -> dtime:
    return dtime.fromisoformat(GC.PASS_OPEN_ET)


def _close_et() -> dtime:
    return dtime.fromisoformat(GC.PASS_CLOSE_ET)


def session_for(now: Optional[datetime] = None) -> tuple:
    """(session date, is_today, in_window). Today ET from the first pass time on a market day; before it, or on a
    closed day, the last market day (its reads stay on the board, labelled)."""
    et = _et(now)
    today = et.date()
    if _is_market_day(today) and et.time() >= _open_et():
        return today, True, et.time() <= _close_et()
    return _prev_market_day(today), False, False


def tape_for(now: Optional[datetime], in_window: bool) -> str:
    """The tape the board is on — the pass's own clock (scanner.pass_tape_session), "closed" out of the window."""
    if not in_window:
        return "closed"
    from chart_maps.gajjala.scanner import pass_tape_session
    return pass_tape_session(_et(now))


def first15(now: Optional[datetime], in_window: bool) -> bool:
    """09:30 ≤ now < 09:30 + NO_TRADE_AFTER_OPEN_MIN on a session day (GG S8 14:41)."""
    if not in_window:
        return False
    et = _et(now)
    start = datetime.combine(et.date(), _RTH_OPEN, tzinfo=ET)
    return start <= et < start + timedelta(minutes=GC.NO_TRADE_AFTER_OPEN_MIN)


def first15_text() -> str:
    return f"⏳ first {GC.NO_TRADE_AFTER_OPEN_MIN} min — he doesn't trade it (S8 14:41)"


def _session_block(now, session: date, is_today: bool, in_window: bool) -> dict:
    tape = tape_for(now, in_window)
    badge = (BADGE_CLOSED_TODAY if is_today and tape == "closed"     # 20:05→midnight: "today", not "last session"
             else SESSION_BADGE.get(tape, SESSION_BADGE["closed"]))
    return {"date": session.isoformat(),
            "label": "today" if is_today else f"last session {session.isoformat()}",
            "tape": tape, "badge": badge,
            "first15": first15(now, in_window), "first15_text": first15_text(),
            "refresh_sec": GC.PASS_CADENCE_SEC if in_window else 0}


def _pass_block(latest: Optional[dict], now, session: date, in_window: bool, cron: Optional[dict] = None) -> dict:
    """The `pass` block. `latest` = the pass shown (any source); `cron` = the newest CRON pass (`_cron_ref`). 2026-10-15
    (AMENDMENTS5 A10): `stale` reads the CRON pass — an on-open pass alone never clears it — and the block gains `at`
    (`pass_stamp`, the stamp the POST answers with) and `on_demand`. `cron` None with a non-on-open `latest` = the
    pre-split shape (every pass was a cron pass): judged on `latest`, exactly as before."""
    at = _at_utc(latest)
    this_session = isinstance(latest, dict) and latest.get("date") == session.isoformat()
    as_of = f"{_et(at).strftime('%H:%M')} ET" if isinstance(at, datetime) else None
    if isinstance(at, datetime) and not this_session:
        as_of = f"{_et(at).strftime('%Y-%m-%d %H:%M')} ET"
    if cron is None and isinstance(latest, dict) and not latest.get("on_demand"):
        cron = latest
    c_at = _at_utc(cron)
    c_this = isinstance(cron, dict) and cron.get("date") == session.isoformat() and c_at is not None
    age = (_et(now) - _et(c_at)).total_seconds() if c_this else None
    warming = bool(in_window and not this_session)
    stale = bool(in_window and this_session and (not c_this or (age is not None and age > GC.STALE_AFTER_SEC)))
    out = {"as_of_et": as_of, "stale": stale, "stale_after_sec": GC.STALE_AFTER_SEC, "warming": warming,
           "status": (latest or {}).get("status") if isinstance(latest, dict) else None,
           "at": pass_stamp(latest), "on_demand": bool((latest or {}).get("on_demand")) if isinstance(latest, dict)
           else False}
    cad = GC.PASS_CADENCE_SEC // 60
    if stale and not c_this:
        out["stale_text"] = f"stale — the {cad}-minute pass has not run this session; it runs every {cad} minutes"
    elif stale and cron is latest:
        out["stale_text"] = (f"stale — the last pass was {as_of}, {int(age // 60)} min ago; the pass runs every "
                             f"{cad} minutes")
    elif stale:
        out["stale_text"] = (f"stale — the last {cad}-minute pass was {_et(c_at).strftime('%H:%M')} ET, "
                             f"{int(age // 60)} min ago; the pass runs every {cad} minutes")
    if warming:
        out["warming_text"] = (f"warming — no pass this session yet (the first runs just after {GC.PASS_OPEN_ET} "
                               "ET); the reads shown are older")
    return out


def strip_text(strip: dict) -> Optional[str]:
    """His situational read (S8 43:39–44:37) in words, from the pass's own counts."""
    if not isinstance(strip, dict) or not strip:
        return None
    n100, n80 = strip.get("runners_100") or 0, strip.get("runners_80") or 0
    best, sym, quiet = _f(strip.get("best_change_pct")), strip.get("best_symbol"), strip.get("quiet")
    if best is None or quiet is None:
        return ("no runner in his band yet — nothing has traded his $%.2f–$%g, %s-share line today"
                % (GC.SCAN_MIN_PRICE, GC.SCAN_MAX_PRICE, "{:,}".format(int(GC.SCAN_MIN_VOLUME))))
    head = f"{n100} runner{'s' if n100 != 1 else ''} ≥{GC.SA_BIG_RUNNER_PCT:g}% · {n80} ≥{GC.SA_RUNNER_PCT:g}% · best {sym} {_pct(best)}"
    if quiet:
        return (f"{head} — QUIET: best runner under {GC.SA_QUIET_BEST_PCT:g}% (his bad day: “the maximum runners "
                f"would be 30%–40%”, S8 44:37); on days like this he trades very little")
    return f"{head} — not quiet (his quiet line: best runner under {GC.SA_QUIET_BEST_PCT:g}%, S8 44:37)"


def _strip_block(latest: Optional[dict]) -> dict:
    s = dict((latest or {}).get("strip") or {}) if isinstance(latest, dict) else {}
    return {"runners_100": s.get("runners_100"), "runners_80": s.get("runners_80"),
            "best_change_pct": _f(s.get("best_change_pct")), "best_symbol": s.get("best_symbol"),
            "quiet": s.get("quiet"), "text": strip_text(s)}


# ── 🔄 scan on open · 🎯 A+ (2026-10-15, BUILD_SPEC5 §3.6 / §3.7, AMENDMENTS5 A10 / A11 / A13) ─────────────────────
# Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any
# enterable stocks on the top which I see in potential i guess". Every served sentence below is composed here (the FE
# prints what it is given); every number is a constants.py name. His word stays in his quote: the served copy says
# "A+", the card's own state.
RESCAN_LABEL = "🔄 scan now"                                                                             # W8
ENTRY_QUOTE_TS = "1:40:56–1:41:55"                                       # the 📓 Playbook ENTRY item the note slices
ENTRY_QUOTE_FROM = "I'll enter right at the break"


def _at_utc(doc) -> Optional[datetime]:
    """A pass doc's `at` as an aware UTC datetime (the live Mongo client hands back NAIVE UTC — AMENDMENTS5 A5; a naive
    stamp read as ET would shift every clock four hours, alerts.bar_close_et's trap), else None."""
    at = doc.get("at") if isinstance(doc, dict) else None
    if not isinstance(at, datetime):
        return None
    return at.replace(tzinfo=timezone.utc) if at.tzinfo is None else at.astimezone(timezone.utc)


def pass_stamp(doc: Optional[dict]) -> Optional[str]:
    """ONE stamp for a pass doc — the GET's `pass.at` and the POST's `latest_at` (on_demand.request) are this function,
    so the board can tell "the pass the POST waited for has landed" by string inequality. None when no pass."""
    at = _at_utc(doc)
    return at.isoformat() if at is not None else None


def _stamp_utc(v) -> Optional[datetime]:
    if not isinstance(v, datetime):
        return None
    return v.replace(tzinfo=timezone.utc) if v.tzinfo is None else v.astimezone(timezone.utc)


def _cron_ref(st, latest: Optional[dict]) -> Optional[dict]:
    """The newest CRON pass (AMENDMENTS5 A10): the "latest_cron" pointer; when none is on file (a store from before the
    split), the shown pass when it is not an on-open pass — before the split every pass was a cron pass. None when no
    cron pass is known (an on-open pass alone never stands in for it)."""
    fn = getattr(st, "latest_cron_pass", None)
    lc = None
    if callable(fn):
        try:
            lc = fn()
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: cron pass read failed: %s", exc)
            lc = None
    if isinstance(lc, dict):
        return lc
    if isinstance(latest, dict) and not latest.get("on_demand"):
        return latest
    return None


def _entry_quote() -> Optional[str]:
    """GG's entry sentence, SLICED from the served 📓 Playbook ENTRY item (S8 1:40:56–1:41:55) — never retyped: from
    "I'll enter right at the break" to the end, the trailing "." dropped. None when the item is not found."""
    try:
        from chart_maps.gajjala import playbook as PB
        for it in PB.ENTRY[1]:
            text = it.get("text") if isinstance(it, dict) else None
            if it.get("ts") == ENTRY_QUOTE_TS and isinstance(text, str) and ENTRY_QUOTE_FROM in text:
                return text[text.index(ENTRY_QUOTE_FROM):].rstrip().rstrip(".")
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: entry quote failed: %s", exc)
    return None


def _when(at: Optional[datetime], session: date, *, sec: bool = False) -> Optional[str]:
    """"HH:MM" (or "HH:MM:SS") ET of a stamp; "{date} HH:MM" when it is from another session."""
    if not isinstance(at, datetime):
        return None
    e = _et(at)
    t = e.strftime("%H:%M:%S" if sec else "%H:%M")
    return t if e.date() == session else f"{e.date().isoformat()} {t}"


def scan_block(latest: Optional[dict], lease: dict, now, *, in_window: bool, session: date) -> dict:
    """§3.6 (b) — the 🔄 line, every sub. state "closed" out of the pass window (C6), "scanning" while the pass lease is
    held (a lease claimed LEASE_SEC ago is not held — a crashed holder never shows "scanning" forever), else "idle".
    Closed bars only (C3): the copy says "bars through HH:MM", never a newer bar. Reads its two arguments only."""
    lease = lease if isinstance(lease, dict) else {}
    latest = latest if isinstance(latest, dict) else None
    at = _at_utc(latest)
    this_session = bool(latest) and latest.get("date") == session.isoformat() and at is not None
    on_demand = bool((latest or {}).get("on_demand"))
    bt = (latest or {}).get("bars_through_et")
    bt = bt if isinstance(bt, str) and bt else None
    cad = GC.PASS_CADENCE_SEC // 60
    hhmm = _et(at).strftime("%H:%M") if at is not None else None
    bars = f" · bars through {bt}" if bt else ""
    if not in_window:
        state = "closed"
        as_of = (f"market closed — last pass {hhmm} ET {_et(at).date().isoformat()}" if at is not None
                 else "market closed — no pass on file")                                                  # W3
    else:
        state = "scanning" if lease.get("held") else "idle"
        if this_session and on_demand:
            as_of = f"🔄 scanned on open {hhmm} ET{bars}"                                                   # W1
        elif this_session:
            as_of = f"last pass {hhmm} ET{bars}"                                                            # W2
        elif at is not None:
            as_of = f"last pass {_et(at).date().isoformat()} {hhmm} ET — none yet this session"            # W2b
        else:
            as_of = "no pass on file yet"                                                                   # W2b
    scanning_text = None
    started = None
    if state == "scanning":
        hstart = _stamp_utc(lease.get("holder_started_at")) or _stamp_utc(lease.get("claimed_at"))
        started = _when(hstart, session, sec=True)
        shown = _when(at, session)
        tail = (f"the board below is the {shown} ET read until it lands" if shown
                else "the board fills when it lands")
        when = f" at {started} ET" if started else ""
        if lease.get("held_by") == "on_demand":
            scanning_text = f"scanning… a pass started on open{when} — {tail}"                             # W4
        else:
            scanning_text = f"scanning… the {cad}-minute pass started{when} — {tail}"                      # W5
    elif at is not None:
        started = _when(at, session)
    note = None
    n_l, n_r = (latest or {}).get("n_listed"), (latest or {}).get("n_read")
    if (isinstance(n_l, int) and isinstance(n_r, int) and not isinstance(n_l, bool) and not isinstance(n_r, bool)
            and 0 <= n_r < n_l):
        note = f"{n_l - n_r} of {n_l} names kept their last pass read"                                    # W6 (A13)
    return {"state": state, "on_demand": on_demand, "started_at_et": started, "bars_through_et": bt,
            "as_of_text": as_of, "scanning_text": scanning_text,
            "text": scanning_text if scanning_text else as_of, "note": note,
            "rescan_label": RESCAN_LABEL,
            "rescan_title": (f"Run one pass now — both push gates run dry, so this pass rings no device; the last "
                             f"pass is reused when it finished under {GC.ON_DEMAND_REUSE_SEC} s ago")}    # W9 (A13)


def _aplus_text(sym: str, setup: str, r: dict, since: Optional[str], extra: list) -> str:
    """W16 — "{SYM} · {e} {label} · trigger {T} · stop {S} (−r%) · A+ since HH:MM ET" (+ the card's own variant / grade
    words, + " (15-min bar)")."""
    bits = [sym, _setup_label(setup)] + [x for x in extra if x]
    trig, stop, risk = _f(r.get("trigger")), _f(r.get("stop")), _f(r.get("risk_pct"))
    if trig is not None:
        bits.append(f"trigger {_px(trig)}")
    if stop is not None:
        bits.append(f"stop {_px(stop)}" + (f" (−{abs(risk):.1f}%)" if risk is not None else ""))
    text = " · ".join(bits)
    if since:
        text += f" · A+ since {since} ET"
    if (r.get("frame") or "5m") == "15m":
        text += " (15-min bar)"
    return text


def _aplus_note(cad: int) -> str:
    """W19 (AMENDMENTS5 A11 wording: the banner lists what the cards call A+, while the latest pass reads it A+)."""
    q = _entry_quote()
    gg = f" — GG: “{q}” (S8 {ENTRY_QUOTE_TS})" if q else ""
    return (f"A+ = every rule of the setup met, price traded through the trigger and the bar closed{gg}. Listed while "
            f"the latest pass reads the card A+ and the {cad}-minute pass is current; an entry that printed earlier and "
            "a potential still forming are not listed (your K1 answer). Opening the tab rings no device: both alerts "
            f"stay on the {cad}-minute pass. Closed bars only — an open between passes adds new scanner names, not a "
            "newer bar. UNMEASURED — the study of his A+ setups read no edge (2026-10-14); not a recommendation.")


def aplus_block(reads_by: dict, latest: Optional[dict], now, *, in_window: bool, scan: dict,
                cron: Optional[dict] = None, session: Optional[date] = None) -> dict:
    """§3.6 (c) — the 🎯 banner, every sub (DECISIONS5 K1 / K3, AMENDMENTS5 A10 / A11). Rows = every listed read OF THE
    LATEST PASS (its `updated_at` is that pass's clock — a name the pass did not re-read keeps an older read and is not
    listed) whose card state is `aplus`, a variant / grade read included with the card's own words; ordered newest
    entry bar first, then SETUPS order, then the symbol. NOT listed: triggered (the entry printed earlier, K1), forming
    / armed potentials, partial, stopped, any read of an older pass. Served only while the newest CRON pass (`cron`) is
    within STALE_AFTER_SEC (A10: opens alone never stand in for a dead cron) and only inside the pass window (C6)."""
    from chart_maps.gajjala import alerts as AL                      # bar_close_et: the A+ gate's own clock
    scan = scan if isinstance(scan, dict) else {}
    latest = latest if isinstance(latest, dict) else None
    at = _at_utc(latest)
    session = session or _et(now).date()
    cad = GC.PASS_CADENCE_SEC // 60
    if cron is None and latest is not None and not latest.get("on_demand"):
        cron = latest                                                # pre-split: every pass was a cron pass
    c_at = _at_utc(cron)
    c_age = (_et(now) - _et(c_at)).total_seconds() if c_at is not None else None
    cron_ok = c_age is not None and c_age <= GC.STALE_AFTER_SEC
    this_session = latest is not None and at is not None and latest.get("date") == session.isoformat()
    rows: list = []
    if in_window and this_session and cron_ok:
        keyed = []
        for sym, doc in (reads_by or {}).items():
            if not isinstance(doc, dict):
                continue
            upd = _stamp_utc(doc.get("updated_at"))
            if upd is None or (at - upd).total_seconds() >= 1:       # a read of an older pass (A11 NEGATIVE)
                continue
            setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
            for setup in GC.SETUPS:
                r = setups.get(setup)
                if not isinstance(r, dict) or r.get("state") != "aplus":
                    continue
                sym_u = str(sym or doc.get("symbol") or "").upper()
                close = AL.bar_close_et(r.get("entry_bar_t"))
                since = close.strftime("%H:%M") if close is not None else None
                frame = r.get("frame") if r.get("frame") in TFS else "5m"
                extra = [variant_label(r), grade_label(r)]
                keyed.append(((order_key({"symbol": sym_u, "gajjala": {"state": "aplus",
                                                                       "entry_bar_t": r.get("entry_bar_t")}})[:2],
                               GC.SETUPS.index(setup), sym_u),
                              {"symbol": sym_u, "setup": setup, "setup_label": _setup_label(setup), "frame": frame,
                               "trigger": _f(r.get("trigger")), "stop": _f(r.get("stop")),
                               "risk_pct": _f(r.get("risk_pct")), "since_et": since,
                               "variant_label": extra[0], "grade_label": extra[1],
                               "href": PT.deep_link(sym_u, setup),
                               "text": _aplus_text(sym_u, setup, r, since, extra)}))
        keyed.sort(key=lambda kv: kv[0])
        rows = [row for _k, row in keyed]
    empty = None
    if not rows:
        hhmm = _et(at).strftime("%H:%M") if at is not None else None
        if not in_window:
            empty = (f"🎯 No A+ · market closed — last pass {hhmm} ET {_et(at).date().isoformat()} · {UNMEASURED}"
                     if at is not None else f"🎯 No A+ · market closed — no pass on file · {UNMEASURED}")        # W18
        elif not this_session:
            empty = f"🎯 No A+ right now · no pass this session yet · {UNMEASURED}"                              # W17b
        elif not cron_ok:
            since = _when(c_at, session)
            empty = ((f"🎯 No A+ shown · the {cad}-minute pass has not run since {since} ET" if since else
                      f"🎯 No A+ shown · the {cad}-minute pass has not run this session")
                     + f" — no alert can ring without it; the banner waits for it · {UNMEASURED}")              # W17c
        elif scan.get("on_demand") or latest.get("on_demand"):
            empty = f"🎯 No A+ right now · scanned on open {hhmm} ET · {UNMEASURED}"                            # W17
        else:
            empty = f"🎯 No A+ right now · last pass {hhmm} ET · {UNMEASURED}"                                  # W17
    title = (f"🎯 A+ — traded through the trigger and the bar closed (GG's entry) · {len(rows)} · {UNMEASURED}"
             if rows else None)                                                                                 # W15
    return {"title": title, "rows": rows, "empty_text": empty, "note": _aplus_note(cad)}


def push_block() -> dict:
    mode = GC.GAJJALA_PUSH_MODE
    if mode == "live":
        text = ("📲 Every A+ rings your phone — every rule met and the entry bar closed; never the first "
                f"{GC.NO_TRADE_AFTER_OPEN_MIN} minutes, never pre-market, once per name, setup and day. {UNMEASURED}.")
    else:
        # NARROWED to A+ 2026-10-15 (BUILD_SPEC4 W20): 🧠 potentials ring live right under this line
        # (`push_potential`), so the shadow sentence names A+ instead of saying nothing reaches a phone.
        text = ("A+ pushes are in SHADOW — every A+ is recorded on /alerts as “shadow — not sent”; no A+ reaches "
                f"your phone until the {GC.STUDY_SESSIONS}-session study reads and you flip it to live. {UNMEASURED}.")
    return {"mode": mode, "text": text}


def push_potential_block(session: date) -> dict:
    """🧠 the LIVE potential push line (BUILD_SPEC4 W15, 2026-10-15 msg 3 "Give me an alert … I will jump on to ride
    the wave"): served beside `push` on every sub; the words are potential.push_note's."""
    return {"mode": "live", "text": PT.push_note(session)}


def board_note() -> str:
    from chart_maps.gajjala import playbook as PB
    note = "UNMEASURED — his rules as he described them, not a forecast."
    d = PB.decay()
    if d:
        note += " He wrote on %s: “%s”" % (d.get("date"), d.get("quote"))
    return note + " Nothing here trades or enters a lane. Not advice."


# ── reads → state words ───────────────────────────────────────────────────────────────────────────────────────────
def _criteria_labels(read: dict, keys: list) -> str:
    by = {c.get("key"): c.get("label") or c.get("key") for c in read.get("criteria") or [] if isinstance(c, dict)}
    return ", ".join(by.get(k, k) for k in keys)


def state_label(read: dict) -> str:
    """The served pill. Every label says UNMEASURED; a break that missed a rule says so (HIS CALL 21)."""
    st = read.get("state")
    trig, stop = read.get("trigger"), read.get("stop")
    if st == "aplus":
        return f"A+ — every rule met, entry bar closed · {UNMEASURED}"
    if st == "triggered":
        n = read.get("bars_since_entry")
        ago = f"{n} bar{'s' if n != 1 else ''} ago" if isinstance(n, int) else "earlier"
        return f"triggered {ago} — A+ on the {_hhmm(read.get('entry_bar_t')) or '—'} bar · {UNMEASURED}"
    if st == "stopped":
        return f"stopped — broke {_px(trig)}, then traded under {_px(stop)} · {UNMEASURED}"
    if st == "forming":
        if read.get("ready"):
            return f"forming — ready: the next bar over {_px(trig)} · {UNMEASURED}"
        why = read.get("reason") or "not long enough yet"
        return f"forming — {why} · {UNMEASURED}"
    if st == "partial":
        missed, unjudged = read.get("missed") or [], read.get("unjudged") or []
        head = "broke — not A+" if read.get("broke") else "partial"
        bits = []
        if missed:
            bits.append("missed: " + _criteria_labels(read, missed))
        if unjudged:
            bits.append("not judgeable: 9 EMA warming up")
        return " · ".join([head] + bits + [UNMEASURED])
    if st == "invalid":
        return f"invalid — {read.get('reason') or 'the structure died'} · {UNMEASURED}"
    return f"none — {read.get('reason') or 'no setup today'} · {UNMEASURED}"


def variant_label(read: dict) -> Optional[str]:
    v = read.get("variant")
    if v == "long_flag":
        return "long flag — listed, never A+, never pushed"
    if v == GC.KF_NO_TOUCH_VARIANT:
        return "near-kiss — listed, never A+, never pushed"
    return None


def grade_label(read: dict) -> Optional[str]:
    if read.get("grade") == GC.VCP_B_GRADE:
        miss = _criteria_labels(read, read.get("missed") or [])
        return f"B — imperfect{(' · missed: ' + miss) if miss else ''} — listed, never pushed"
    return None


# ── chips ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _psych_text(chip) -> Optional[str]:
    """context.psych_chips row → "🧱 $5 · 4.2% above — his profit-taking / climax level, not an entry"."""
    t = _text(chip)
    if not t:
        return None
    why = chip.get("why") if isinstance(chip, dict) else None
    return f"{t} — {why}" if why and why not in t else t


def psych_chips(price) -> list:
    """🧱 his profit-taking / climax levels within PSY_NEAR_PCT above the price — WP2's engine
    (`context.psych_chips`), worded for the card."""
    from chart_maps.gajjala import context as CX
    return [t for t in (_psych_text(c) for c in CX.psych_chips(price)) if t]


def _psych_from_ctx(v, price) -> list:
    if isinstance(v, list):
        return [t for t in (_psych_text(x) for x in v) if t]
    return psych_chips(price)


def _rotation_text(v, volume, float_read) -> Optional[str]:
    t = _text(v)
    if t:
        return t
    from chart_maps.gajjala import context as CX
    return _text(CX.rotation(volume, float_read if isinstance(float_read, dict) else None))


def _halts_text(v, halt_doc: Optional[dict]) -> Optional[str]:
    """The pass's own ⏸ chip (context.halts_chip, stored in ctx) — else the same words off today's halt ledger row."""
    t = _text(v)
    if t:
        return t
    src = v if isinstance(v, dict) else halt_doc
    if not isinstance(src, dict):
        return None
    n = src.get("n_halts", src.get("n"))
    if not isinstance(n, int) or n <= 0:
        return None
    reasons = src.get("reasons") or []
    rs = ", ".join(str(r) for r in reasons if r) if isinstance(reasons, (list, tuple)) else str(reasons)
    return f"⏸ halted ×{n}{f' ({rs})' if rs else ''}"


def _squeeze_text(v) -> Optional[str]:
    t = _text(v)
    if t:
        return t
    if not isinstance(v, dict) or not isinstance(v.get("n"), int):
        return None
    of = v.get("of") or GC.K8_HISTORY_SESSIONS
    out = (f"🎾 squeeze history: {v['n']} of last {of} sessions (≥{GC.K8_HISTORY_RANGE_PCT:g}% range or a halt)")
    if v.get("ledger_complete") is False and v.get("ledger_from"):
        out += f" · halt list from {v['ledger_from']}"
    return out


def _float_chip(fr) -> Optional[dict]:
    if not isinstance(fr, dict):
        return None
    text = _text(fr)
    shares = _f(fr.get("shares"))
    if not text:
        if shares is None:
            text = "float unknown"
        else:
            word = {"float": "Float", "shares_out_yf": "shares out",
                    "shares_out_massive": "shares out"}.get(fr.get("src"), "Float")
            text = f"{word} {_compact(shares)}" + (" (Massive)" if fr.get("src") == "shares_out_massive" else "")
    return {"shares": shares, "src": fr.get("src"), "text": text,
            "as_of": _plain(fr.get("as_of")), "suspect": bool(fr.get("suspect"))}


def _float_suspect_text(ctx: dict, fr) -> Optional[str]:
    t = _text(ctx.get("float_suspect")) or (_text(fr.get("suspect_text")) if isinstance(fr, dict) else None)
    if t:
        return t
    if isinstance(fr, dict) and fr.get("suspect"):
        tail = ("treated as unknown" if GC.FLOAT_SUSPECT_POLICY == "ineligible" else "using shares out")
        return f"float on file exceeds shares out — {tail}"
    return None


def _red_text(read: dict) -> Optional[str]:
    """WP2's chip (`context.red_closes_chip`, DECISIONS R2-5: a chip, never a rule)."""
    from chart_maps.gajjala import context as CX
    return _text(CX.red_closes_chip(read.get("red_closes")))


def _stopped_text(doc: dict, setup: str, read: dict) -> Optional[str]:
    if read.get("state") == "stopped":
        return None
    hit = (doc.get("stopped_today") or {}).get(setup) if isinstance(doc.get("stopped_today"), dict) else None
    if not hit:
        return None
    at = _hhmm(hit) if isinstance(hit, (str, datetime)) else None     # run.py stores the ENTRY bar, not the stop
    return (f"stopped earlier today on this setup{f' (entered {at}, stopped)' if at else ''} — “Mostly pass and wait "
            "more” (his X post, 2024-01-25)")


def _flag_text(setup: str, read: dict) -> Optional[str]:
    k = read.get("flag_k")
    if setup != "bull_flag" or not isinstance(k, int) or k <= 0:
        return None
    return (f"flag #{k} today · Business Insider: he plays the first and second, usually skips the third (one "
            "third-party source)")


def _read_at_text(doc: dict, pass_at: Optional[datetime]) -> Optional[str]:
    """W7 (2026-10-15): "read at the HH:MM ET pass" when the card's read doc is older than the pass shown by ≥ 1 s —
    a name an on-open pass did not re-read (its budget ran out) or whose bars failed on a pass keeps an earlier read,
    and says so. None when the read is the shown pass's own (or either stamp is missing)."""
    upd = _stamp_utc(doc.get("updated_at")) if isinstance(doc, dict) else None
    pa = _stamp_utc(pass_at)
    if upd is None or pa is None or (pa - upd).total_seconds() < 1:
        return None
    return f"read at the {_et(upd).strftime('%H:%M')} ET pass"


def _chips(doc: dict, setup: str, read: dict, scan_row: dict, sess: dict, halt_doc, daily: Optional[dict],
           pass_at: Optional[datetime] = None) -> dict:
    ctx = doc.get("ctx") if isinstance(doc.get("ctx"), dict) else {}
    daily = daily or {}
    fr = ctx.get("float") if isinstance(ctx.get("float"), dict) else daily.get("float")
    price = scan_row.get("price")
    tape = sess.get("tape")
    out = {
        "float": _float_chip(fr),
        "float_suspect": _float_suspect_text(ctx, fr),
        "rotation": _rotation_text(ctx.get("rotation"), scan_row.get("volume"), fr),
        "halts": _halts_text(ctx.get("halts"), halt_doc),
        "psych": _psych_from_ctx(ctx.get("psych"), price) if "psych" in ctx else psych_chips(price),
        "change_pct": _f(scan_row.get("change_pct")),
        "volume": _f(scan_row.get("volume")),
        "vol_src": scan_row.get("vol_src"),
        "session_badge": sess.get("badge"),
        "first15": bool(sess.get("first15")),
        "red_closes": _red_text(read),
        "stopped_earlier": _stopped_text(doc, setup, read),
        "flag_k": _flag_text(setup, read),
        "instrument": GC.SCAN_UNKNOWN_TYPE_LABEL if scan_row.get("type") == GC.SCAN_UNKNOWN_TYPE else None,
        "outside_rth": OUTSIDE_RTH.get(tape),
        "read_at": _read_at_text(doc, pass_at),
    }
    if setup == "reversal_squeeze":
        out["squeeze_history"] = _squeeze_text(ctx.get("squeeze_history") or daily.get("squeeze_history"))
    return out


def _listed_block(info: Optional[dict]) -> Optional[dict]:
    if not isinstance(info, dict):
        return None
    out = {k: info.get(k) for k in ("since", "last_qualified", "day_n", "of")}
    if isinstance(out.get("day_n"), int):
        of = f"/{out['of']}" if isinstance(out.get("of"), int) else ""
        out["text"] = f"listed day {out['day_n']}{of}" + (f" · since {out['since']}" if out.get("since") else "")
    return out


# ── tiles ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _tile_frame(doc: dict, tf: str) -> dict:
    tile = doc.get("tile") if isinstance(doc.get("tile"), dict) else {}
    suf = "15" if tf == "15m" else "5"
    return {"tf": "15m" if suf == "15" else "5m", "bars": list(tile.get(f"bars{suf}") or []),
            "curves": list(tile.get(f"curves{suf}") or []), "vol_avg": tile.get(f"vol_avg{suf}")}


def _last_close(doc: dict, frame: str) -> Optional[float]:
    bars = _tile_frame(doc, frame).get("bars") or []
    for b in reversed(bars):
        c = _f(b.get("c")) if isinstance(b, dict) else None
        if c is not None:
            return c
    return None


def _bars_to_go(read: dict) -> Optional[int]:
    """forming (not ready): bars still missing to the setup's minimum length (None = unknown, sorts last)."""
    if isinstance(read.get("bars_to_go"), int):
        return read["bars_to_go"]
    have = (read.get("base") or {}).get("bars") if isinstance(read.get("base"), dict) else None
    have = have if isinstance(have, int) else 0
    need = {"bull_flag": GC.K4_BF_PULL_MIN, "horizontal_fade": GC.K4_HF_BASE_MIN,
            "reversal_squeeze": GC.RS_BASE_MIN_BARS}.get(read.get("setup"))
    if read.get("setup") == "intraday_vcp":
        cyc = (read.get("meta") or {}).get("cycles") if isinstance(read.get("meta"), dict) else None
        if isinstance(cyc, int):
            return max(0, GC.K4_VCP_MIN_CYCLES - cyc)
        return None
    if not isinstance(need, int):
        return None
    return max(0, need - have)


def order_key(t: dict) -> tuple:
    """BUILD_SPEC §3.4.1 ordering keys: state rank; A+/triggered/stopped newest entry first; ready forming nearest
    its trigger; forming by bars to go; partial by fewest misses, then biggest change; final tie the symbol."""
    g = t.get("gajjala") or {}
    st = g.get("state")
    sym = t.get("symbol") or ""
    big = float("inf")
    if st in MARKED_STATES:
        rank = {"aplus": 0, "triggered": 1, "stopped": 5}[st]
        digits = "".join(ch for ch in str(g.get("entry_bar_t") or "") if ch.isdigit())
        return (rank, -float(digits) if digits else big, 0.0, sym)      # newest entry bar first
    if st == "forming" and g.get("ready"):
        trig, last = _f(g.get("trigger")), _f(g.get("_last"))
        return (2, (trig - last) / last if (trig is not None and last) else big, 0.0, sym)
    if st == "forming":
        n = g.get("_bars_to_go")
        return (3, float(n) if isinstance(n, int) else big, 0.0, sym)
    if st == "partial":
        ch = _f((g.get("chips") or {}).get("change_pct"))
        return (4, float(len(g.get("missed") or [])), -ch if ch is not None else big, sym)
    return (9, big, 0.0, sym)


def _tile_lines(read: dict) -> list:
    out = []
    if _f(read.get("trigger")) is not None:
        out.append({"price": _f(read["trigger"]), "label": f"BUY > {_px(read['trigger'])}", "tone": "buy"})
    if _f(read.get("stop")) is not None:
        out.append({"price": _f(read["stop"]), "label": f"STOP {_px(read['stop'])}", "tone": "stop"})
    return out


def tile_tf(read: dict, tf: str, sub_default: str) -> str:
    """The frame a card draws: the asked tf when the URL carries one, else the frame its own read was taken on (the
    ➖ Fade reads 15-minute first but falls back to a 5-minute read), else the sub's default."""
    if tf in TFS:
        return tf
    f = read.get("frame")
    return f if f in TFS else sub_default


def _on_bars(markers: list, bars: list) -> list:
    """Only the markers whose stamp is a served bar — an A+ stamped on the other frame has no bar to sit on."""
    stamps = {b.get("t") for b in bars if isinstance(b, dict)}
    return [m for m in markers if m.get("date") in stamps]


def setup_tile(doc: dict, setup: str, tf: str, *, scan_row: dict, sess: dict, listed: Optional[dict],
               halt_doc=None, daily=None, pass_at: Optional[datetime] = None) -> dict:
    """One card: bars + 9/21 EMA + served volume average of `tf` (tile_tf), BUY/STOP lines, the A+ marker when its bar
    is served, and the read in words (state pill, criteria, chips; `pass_at` = the shown pass's clock → the
    "read at …" chip, 2026-10-15)."""
    from chart_maps import board as board_mod
    read = dict((doc.get("setups") or {}).get(setup) or {})
    sym = (doc.get("symbol") or "").upper()
    fr = _tile_frame(doc, tf)
    if not fr["bars"]:                                               # the asked frame is empty → the other one
        other = "5m" if tf == "15m" else "15m"
        alt = _tile_frame(doc, other)
        if alt["bars"]:
            fr = alt
    markers = _on_bars([{"date": read.get("entry_bar_t"), "kind": "buy", "label": "A+"}]
                       if read.get("state") in MARKED_STATES and read.get("entry_bar_t") else [], fr["bars"])
    chips = _chips(doc, setup, read, scan_row, sess, halt_doc, daily, pass_at=pass_at)
    stats = [s for s in ({"k": "Change", "v": _pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": _compact(scan_row.get("volume"))}) if s["v"]]
    g = {k: read.get(k) for k in ("setup", "state", "frame", "ready", "broke", "trigger", "stop", "risk_pct",
                                  "entry_bar_t", "bars_since_entry", "criteria", "missed", "unjudged", "grade",
                                  "variant", "red_closes", "flag_k", "reason")}
    g.update({"setup": setup, "state_label": state_label(read), "variant_label": variant_label(read),
              "grade_label": grade_label(read), "chips": chips, "listed": _listed_block(listed),
              "_last": _last_close(doc, read.get("frame") or "5m") or _f(scan_row.get("price")),
              "_bars_to_go": _bars_to_go(read)})
    vol_avg = fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None
    return {"symbol": sym, "name": doc.get("name"), "href": board_mod._href(sym), "tf": fr["tf"], "bars": fr["bars"],
            "vol_avg": vol_avg, "bands": [], "lines": _tile_lines(read), "markers": markers, "stats": stats,
            "why": read.get("reason") or "", "badges": [], "curves": fr["curves"], "gajjala": g}


def _strip_private(tiles: list) -> None:
    for t in tiles:
        g = t.get("gajjala")
        if isinstance(g, dict):
            g.pop("_last", None)
            g.pop("_bars_to_go", None)


def _list_tile(sym: str, sub: str, doc: Optional[dict], tf: str, *, scan_row: dict, sess: dict,
               listed: Optional[dict], halt_doc=None, daily=None, extra: dict) -> dict:
    """A ☀️ / 🌙 row: the name's bars when it is listed (its read doc), its list facts in words, no setup lines."""
    from chart_maps import board as board_mod
    doc = doc or {}
    fr = _tile_frame(doc, tf) if doc else {"bars": [], "curves": [], "vol_avg": None}
    read = {"setup": sub, "state": "forming"}
    chips = _chips(doc, sub, read, scan_row, sess, halt_doc, daily)
    g = {"setup": sub, "state": "forming", "state_label": extra.pop("state_label"), "chips": chips,
         "listed": _listed_block(listed), "criteria": [], "missed": [], "unjudged": []}
    g.update(extra)
    stats = [s for s in ({"k": "Change", "v": _pct(scan_row.get("change_pct"))},
                         {"k": "Volume", "v": _compact(scan_row.get("volume"))}) if s["v"]]
    return {"symbol": sym, "name": doc.get("name"), "href": board_mod._href(sym), "bars": fr["bars"],
            "vol_avg": fr.get("vol_avg") if isinstance(fr.get("vol_avg"), dict) else None, "bands": [],
            "lines": [], "markers": [], "stats": stats, "why": "", "badges": [], "curves": fr["curves"],
            "gajjala": g}


# ── ☀️ Premarket (K9) / 🌙 Post-market (K10) — WP2's engines over what the pass stored ─────────────────────────────
def session_pass(store, latest: Optional[dict], session: date) -> Optional[dict]:
    """The newest pass doc of `session`: the "latest" pointer when it is this session's, else the session's last."""
    if isinstance(latest, dict) and latest.get("date") == session.isoformat():
        return latest
    docs = [d for d in store.passes(session) if isinstance(d, dict)]
    if not docs:
        return None

    def _at(d):
        a = d.get("at")
        return _et(a).isoformat() if isinstance(a, datetime) else str(a or "")
    return max(docs, key=_at)


def premarket_rows(store, session: date, scan_docs: list, pass_doc: Optional[dict], sort: str) -> list:
    """☀️ = `context.premarket_list` (DECISIONS K9, WP2): today's premarket qualifiers by volume (his ToS sort) or
    change, then the previous session's after-hours carry (the set the LAST after-hours pass wrote). The premarket
    volume is the 1-minute sum the pass stored (`pass.premarket.pm_levels`), else the scanner's own number."""
    from chart_maps.gajjala import context as CX
    pm = (pass_doc or {}).get("premarket") if isinstance(pass_doc, dict) else None
    levels = pm.get("pm_levels") if isinstance(pm, dict) and isinstance(pm.get("pm_levels"), dict) else None
    carry = store.ah_carry(_prev_market_day(session))
    return CX.premarket_list(scan_docs, carry, pm_levels=levels, sort=sort)


def _pm_extra(row: dict) -> dict:
    if row.get("carry"):
        return {"state_label": f"carried from the last session's after-hours · {UNMEASURED}",
                "premarket": {"carry_text": row.get("text")}}
    bits = [f"pm volume {_compact(row.get('pm_volume'))}" if _f(row.get("pm_volume")) is not None else None,
            _pct(row.get("pm_change_pct"))]
    off = _f(row.get("off_pm_high_pct"))
    carried = row.get("carried") if isinstance(row.get("carried"), dict) else None
    return {"state_label": f"premarket mover · {UNMEASURED}",
            "premarket": {"text": " · ".join(b for b in bits if b) or None,
                          "carry_text": carried.get("text") if carried else None,
                          "off_pm_high_text": (f"{off:+.1f}% off the premarket high" if off is not None else None)}}


def postmarket_rows(pass_doc: Optional[dict]) -> tuple:
    """🌙 = the rows `context.postmarket_confirm` returned to the session's last pass (DECISIONS K10 — the pass judges
    the CURRENT after-hours gain off the snapshot, which only the pass holds) + its unchecked count. ([], 0) when the
    pass stored none."""
    pm = (pass_doc or {}).get("postmarket") if isinstance(pass_doc, dict) else None
    pm = pm if isinstance(pm, dict) else {}
    rows = [r for r in pm.get("rows") or [] if isinstance(r, dict) and r.get("symbol")]
    rows.sort(key=lambda r: (_f(r.get("ah_gain_pct")) is None, -(_f(r.get("ah_gain_pct")) or 0.0),
                             str(r.get("symbol"))))
    un = pm.get("unchecked_n")
    return rows, (un if isinstance(un, int) and not isinstance(un, bool) and un >= 0 else 0)


def _post_extra(d: dict) -> dict:
    pos = _f(d.get("close_pos"))
    bits = [f"close in the top {max(0.0, (1 - pos) * 100):.0f}% of the range" if pos is not None else None,
            f"AH volume {_compact(d.get('ah_volume'))}" if _f(d.get("ah_volume")) is not None else None,
            f"AH {_pct(d.get('ah_gain_pct'))}" if _f(d.get("ah_gain_pct")) is not None else None]
    at = _hhmm(d.get("checked_at")) if isinstance(d.get("checked_at"), datetime) else None
    reg = _f(d.get("reg_gain_pct"))
    return {"state_label": f"after-hours mover · {UNMEASURED}",
            "postmarket": {"text": " · ".join(b for b in bits if b) or None,
                           "checked_text": d.get("checked_text") or (f"checked {at} ET" if at else None),
                           "exhaustion_text": f"regular session {reg:+.1f}%" if reg is not None else None}}


def recap(reads: list) -> dict:
    """🌙 today's A+ recap (DECISIONS R2-7): which reads went A+ / triggered / stopped — states only, no win/loss
    maths. Ordered by the entry bar."""
    rows = []
    for doc in reads:
        sym = (doc.get("symbol") or "").upper()
        for setup in GC.SETUPS:
            r = (doc.get("setups") or {}).get(setup) or {}
            if r.get("state") not in MARKED_STATES:
                continue
            e, label = SUB_META[setup]
            word = {"aplus": "A+", "triggered": "A+ (triggered)", "stopped": "A+, then stopped"}[r["state"]]
            rows.append((r.get("entry_bar_t") or "", sym, setup,
                         f"{e} {label} {word} at {_hhmm(r.get('entry_bar_t')) or '—'} — broke {_px(r.get('trigger'))}"
                         f", stop {_px(r.get('stop'))}"))
    rows.sort()
    return {"title": f"Today's A+ recap — states only, no win/loss maths · {UNMEASURED}",
            "rows": [{"symbol": sym, "setup": setup, "text": text} for _t, sym, setup, text in rows]}


# ── sub resolution (C9 deep links) ────────────────────────────────────────────────────────────────────────────────
def _pushed_potential_setup(potentials, sym: str, day: str) -> Optional[str]:
    """🧠 step of resolve_sub (BUILD_SPEC4 §3.9 (d), 2026-10-15): the setup of the session's newest PUSHED tracker
    doc of `sym` (tie → SETUPS order). The push-history link carries no setup (push.recent.item_url), so this opens
    the sub that rang. Held / unpushed docs and other sessions never count. Never raises."""
    try:
        order = {s: i for i, s in enumerate(GC.SETUPS)}
        hits = []
        for d in potentials or []:
            push = d.get("push") if isinstance(d, dict) else None
            if not isinstance(push, dict) or push.get("state") != "pushed":
                continue
            if str(d.get("symbol") or "").upper() != sym or d.get("date") != day or d.get("setup") not in order:
                continue
            at = push.get("at")
            if isinstance(at, str):
                try:
                    at = datetime.fromisoformat(at)
                except ValueError:
                    at = None
            when = _et(at).isoformat() if isinstance(at, datetime) else ""
            hits.append((when, -order[d["setup"]], d["setup"]))
        return max(hits)[2] if hits else None
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential focus read failed: %s", exc)
        return None


def resolve_sub(sub: str, focus: str, *, store, session: date, reads_by: dict, listed: dict,
                pm_syms: set, post_syms: set, potentials: Optional[list] = None) -> tuple:
    """(sub, resolved_from). An explicit known sub wins; an unknown one → DEFAULT_SUB (fail open). Empty sub + a
    focus symbol → the setup of today's newest pushed (or shadow-recorded) claim, else (2026-10-15) the setup of
    today's newest PUSHED 🧠 potential ("focus_potential"; `potentials` = the tracker docs `build` already read, None →
    store.potentials(session), a failure → none), else the best-ranked read's setup, else ☀️ / 🌙 when the name is
    on that list, else the default."""
    s = (sub or "").strip().lower()
    if s:
        return (s, "param") if s in SUB_KEYS else (GC.DEFAULT_SUB, "default")
    sym = (focus or "").strip().upper()
    if not sym:
        return GC.DEFAULT_SUB, "default"
    day = session.isoformat()
    ids = [f"{p}GG:{day}|{sym}|{st}" for st in GC.SETUPS for p in ("", "SHADOW:")]
    claims = [d for d in _alerts_find(store, ids) if d.get("state") in ("pushed", "shadow")]
    if claims:
        def _when(d):
            v = d.get("claimed_at")
            return _et(v).isoformat() if isinstance(v, datetime) else str(v or "")
        newest = max(claims, key=lambda d: (_when(d), str(d.get("_id"))))
        setup = str(newest.get("_id")).rsplit("|", 1)[-1]
        if setup in GC.SETUPS:
            return setup, "focus_alert"
    if potentials is None:
        try:
            potentials = store.potentials(session) or []            # None = a read fault (2026-10-15): soft here
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: potentials read failed: %s", exc)
            potentials = []
    pot_setup = _pushed_potential_setup(potentials, sym, day)
    if pot_setup:
        return pot_setup, "focus_potential"
    doc = reads_by.get(sym)
    if doc:
        best = None
        for i, setup in enumerate(GC.SETUPS):
            r = (doc.get("setups") or {}).get(setup) or {}
            if r.get("state") not in TILE_STATES:
                continue
            t = {"symbol": sym, "gajjala": dict(r, _last=_last_close(doc, r.get("frame") or "5m"),
                                                _bars_to_go=_bars_to_go(r))}
            k = (order_key(t), i)
            if best is None or k < best[0]:
                best = (k, setup)
        if best:
            return best[1], "focus_read"
    if sym in pm_syms:
        return "premarket", "focus_list"
    if sym in post_syms:
        return "postmarket", "focus_list"
    return GC.DEFAULT_SUB, "default"


# ── 🧠 potential · 📈 track (BUILD_SPEC4 §3.9, 2026-10-15) ──────────────────────────────────────────────────────────
# Ajay 2026-10-15: "In Gajjalas setup I wanna find potential stocks … So create a potential category in this section."
# / "In all the sub tab and add a track and alert to show me new potential is added everyday." Every rule, word and
# order below is potential.py's (potential_kind / tell_values / tells / order_key / row_text / state_word / HELD_WORDS);
# this section only assembles the served shapes. No number is typed here.
WATCH_HEAD = ("👀 On his watch list, no structure yet — “if it's making some noise in pre-market I put them in my watch "
              "list … after hours moves from the past day, I'll keep them as well” (S8 13:21–14:34): ")    # W14
TRACK_UNMEASURED = ("UNMEASURED — what each potential did after it was first seen, recorded pass by pass; not a "
                    "forecast. No study has read this record yet.")                                        # W13b
TRACK_RECORD_FAULT = "🏁 The alert record could not be read this time — the next re-read tries again."    # W16
PUSH_TEXT = {"no_target": "📲 no device took it (toggle off, quiet hours or none registered)",
             "failed": "📲 send failed",
             "claimed": "📲 sending"}           # W19's /alerts word for a claimed doc (a pass died before the settle)


def _soft(what: str, fn, *a, default=None, **kw):
    """D1 on the read path: a raising 🧠 potential / 📈 track piece logs and serves `default`; it never takes down the
    A+ board of any sub."""
    try:
        return fn(*a, **kw)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: %s failed: %s", what, exc)
        return default


def _safe_list(fn, *a) -> list:
    """A store read that may be missing (an older store) or fail: [] — the documented "no data" answer."""
    try:
        out = fn(*a)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential read failed: %s", exc)
        return []
    return [d for d in out or [] if isinstance(d, dict)]


def _setup_label(setup: str) -> str:
    e, label = SUB_META.get(setup, ("🧠", setup))
    return f"{e} {label}"


def _potential_reads(reads_by: dict, scan_by: dict, *, trackers: dict, trackers_prev: set, ah_prev, prev_scan_by: dict,
                     setup: Optional[str] = None) -> list:
    """Every (symbol, setup) potential of the board's listed reads — `setup` given: that setup only — as
    [(order_key, PotRow, read_doc, read)] in potential.order_key order (one order everywhere). `trackers` =
    {(SYM, setup): today's tracker doc} (first_seen_et); `trackers_prev` = {(SYM, setup)} of the session before (↻)."""
    out = []
    for sym, doc in reads_by.items():
        setups = doc.get("setups") if isinstance(doc.get("setups"), dict) else {}
        kinds = {s: PT.potential_kind(setups.get(s)) for s in GC.SETUPS}
        also = [s for s in GC.SETUPS if kinds[s]]
        for s in GC.SETUPS:
            kind = kinds[s]
            if not kind or (setup is not None and s != setup):
                continue
            read = setups.get(s) or {}
            again = (sym, s) in trackers_prev
            values = PT.tell_values(sym, s, ctx=doc.get("ctx"), scan_row=(scan_by.get(sym) or {}).get("last"),
                                    ah_prev=ah_prev, prev_scan=prev_scan_by.get(sym), also=also, again=again)
            tdoc = trackers.get((sym, s)) or {}
            first = tdoc.get("first_seen_et") if isinstance(tdoc.get("first_seen_et"), str) else None
            reason = read.get("reason") if isinstance(read.get("reason"), str) and read.get("reason") else None
            row = {"symbol": sym, "setup": s, "kind": kind, "kind_label": PT.KIND_LABEL[kind],
                   "trigger": _f(read.get("trigger")), "stop": _f(read.get("stop")), "risk_pct": _f(read.get("risk_pct")),
                   "reason": reason, "first_seen_et": first, "again": again, "tells": PT.tells(values),
                   "href": PT.deep_link(sym, s), "text": PT.row_text(sym, s, read, kind, first)}
            out.append((PT.order_key(kind, values, s, sym), row, doc, read))
    out.sort(key=lambda x: x[0])
    return out


def _potential_strip(setup: str, pots: list, today_n: int, *, sess: dict, in_window: bool) -> dict:
    """§3.9 (a) — the 🧠 strip of one setup sub (W6 title, W7 text, W8 empty), ALL of its potentials (a compact list,
    never cut by `limit`)."""
    rows = [p[1] for p in pots]
    a = sum(1 for r in rows if r["kind"] == GC.POTENTIAL_KINDS[0])
    b = sum(1 for r in rows if r["kind"] == GC.POTENTIAL_KINDS[1])
    concept, ts = PT.CONCEPT
    defaults = PT.defaults_sentence()
    text = ("Forming, not triggered: the demand leg is in and the quiet sideways part has started (“building”) or is "
            "complete (“trigger armed”); the reclaim of the highs has not printed. "
            f"His words: “{concept}” ({ts}). " + (f"{defaults} " if defaults else "") + "A potential, not an entry.")
    e, label = SUB_META[setup]
    empty = None
    if not rows:
        empty = (f"No {e} {label} forming right now — the next pass is at most {GC.PASS_CADENCE_SEC // 60} minutes "
                 "away." if in_window else f"No {e} {label} was forming at the last pass ({sess['label']}).")
    return {"title": f"🧠 Potential — {a} trigger armed · {b} building · {today_n} first seen {sess['label']} · "
                     f"{UNMEASURED}",
            "text": text, "counts": {"armed": a, "building": b, "today": today_n}, "rows": rows, "empty_text": empty}


def _potential_tiles(pots: list, *, st, session: date, tf_ask: str, scan_row, sess: dict, listed: dict,
                     halts_by: dict, pass_at: Optional[datetime] = None) -> list:
    """§3.9 (b) — one tile per SYMBOL: the existing `setup_tile` card of its PRIMARY potential (the first by
    potential.order_key), with `gajjala.potential` (W12) and the 🧩 other setups forming on it (GG S9 1:59:01)."""
    by_sym: dict = {}
    for p in pots:
        by_sym.setdefault(p[1]["symbol"], []).append(p)
    tiles = []
    for sym, items in sorted(by_sym.items(), key=lambda kv: kv[1][0][0]):
        _k, row, doc, read = items[0]
        setup = row["setup"]
        daily = st.get_daily(session, sym) if setup == "reversal_squeeze" else None
        tile = setup_tile(doc, setup, tile_tf(read, tf_ask, "5m"), scan_row=scan_row(sym), sess=sess,
                          listed=listed.get(sym), halt_doc=halts_by.get(sym), daily=daily, pass_at=pass_at)
        first = row["first_seen_et"]
        tile["gajjala"]["potential"] = {
            "kind": row["kind"], "kind_label": row["kind_label"], "setup": setup, "setup_label": _setup_label(setup),
            "first_seen_et": first, "again": row["again"], "tells": row["tells"],
            "also": [{"setup": p[1]["setup"], "label": _setup_label(p[1]["setup"])} for p in items[1:]],
            "text": f"🧠 {row['kind_label']} · {_setup_label(setup)}" + (f" · first seen {first} ET" if first else "")}
        tiles.append(tile)
    return tiles


def _track_row(doc: dict) -> dict:
    """One 📈 Track row from a tracker doc (W13) — the doc's own prices (the pass wrote them, AMENDMENTS4 D2: the
    5-minute frame's closed close first), never recomputed here; states and prices only, no win/loss maths."""
    sym = str(doc.get("symbol") or "").upper()
    setup = str(doc.get("setup") or "")
    last = doc.get("last") if isinstance(doc.get("last"), dict) else {}
    path = [e for e in doc.get("state_path") or [] if isinstance(e, dict)]
    grave = doc.get("graveyard_on") if isinstance(doc.get("graveyard_on"), str) else None
    if last:
        last_state, last_kind = last.get("state"), last.get("kind")
    else:
        last_state, last_kind = (path[-1].get("state"), path[-1].get("kind")) if path else (None, None)
    last_text = PT.state_word(last_state, last_kind)
    p0, p1, t0 = _f(doc.get("first_px")), _f(last.get("px")), _f(doc.get("first_trigger"))
    m, v = _f(doc.get("move_pct")), _f(doc.get("vs_trigger_pct"))
    move_text = f"{_px(p0)} → {_px(p1)} ({m:+.1f}%) since first seen" if m is not None and p0 and p1 else None
    vs_text = f"{v:+.1f}% vs the trigger at first sight ({_px(t0)})" if v is not None and t0 else None
    push = doc.get("push") if isinstance(doc.get("push"), dict) else None
    push_text = None
    if push:
        ps = push.get("state")
        if ps == "pushed":
            push_text = "📲 sent" + (f" {push['at_et']} ET" if isinstance(push.get("at_et"), str) else "")
        else:
            push_text = PUSH_TEXT.get(ps)
    else:
        held = [h.get("reason") for h in doc.get("held") or [] if isinstance(h, dict) and h.get("reason") in PT.HELD_WORDS]
        if not held and doc.get("first_seen_mode") == PT.FIRST_SEEN_MODES[1]:
            held = [PT.JOIN_HELD[0]]                                # D9: a joined doc whose hold write was lost
        if held:
            push_text = f"held: {PT.HELD_WORDS[held[-1]]}"
    timeline = []
    for e in path:
        at_et = e.get("at_et") if isinstance(e.get("at_et"), str) else None
        word = PT.state_word(e.get("state"), e.get("kind"), on=grave if e.get("state") == "graveyard" else None)
        timeline.append({"at_et": at_et, "text": f"{at_et} {word}" if at_et else word})
    first = doc.get("first_seen_et") if isinstance(doc.get("first_seen_et"), str) else None
    fk = doc.get("first_kind")
    fkl = PT.KIND_LABEL.get(fk)
    bits = [f"{sym} · {_setup_label(setup)}", (f"first seen {first} ET" + (f" {fkl}" if fkl else "")) if first else fkl,
            f"now {last_text}", move_text]
    url = doc.get("url")
    href = url if isinstance(url, str) and url.startswith("/") and not url.startswith("//") else PT.deep_link(sym, setup)
    return {"symbol": sym, "setup": setup, "setup_label": _setup_label(setup), "first_seen_et": first,
            "first_kind": fk, "first_kind_label": fkl, "first_px": p0, "first_trigger": t0,
            "first_stop": _f(doc.get("first_stop")), "last_state": last_state, "last_state_text": last_text,
            "last_px": p1, "move_pct": m, "move_text": move_text, "vs_trigger_pct": v, "vs_trigger_text": vs_text,
            "push_text": push_text, "graveyard_on": grave, "timeline": timeline,
            "text": " · ".join(b for b in bits if b), "href": href}


def _first_seen_key(doc: dict) -> str:
    v = doc.get("first_seen")
    if isinstance(v, str):
        try:
            v = datetime.fromisoformat(v)
        except ValueError:
            v = None
    return _et(v).isoformat() if isinstance(v, datetime) else str(doc.get("first_seen_et") or "")


def _capped(rows: list) -> dict:
    out = {"rows": rows[:GC.TILE_LIMIT_MAX]}
    if len(rows) > GC.TILE_LIMIT_MAX:
        out["more_n"] = len(rows) - GC.TILE_LIMIT_MAX
    return out


def _track_block(today_docs: list, prev_docs: list, *, session: date, prev: date, sess: dict) -> dict:
    """§3.9 (b) `track` — today's first sightings newest first, the session before chronological (no outcome
    ranking), each row's timeline in potential.state_word's words; rows capped at TILE_LIMIT_MAX (`more_n`)."""
    order = {s: i for i, s in enumerate(GC.SETUPS)}

    def tie(d):
        return (str(d.get("symbol") or ""), order.get(d.get("setup"), len(order)))
    today = sorted(today_docs, key=tie)
    today = sorted(today, key=_first_seen_key, reverse=True)
    yday = sorted(sorted(prev_docs, key=tie), key=_first_seen_key)
    n = len(today)
    first, last = PT.pass_times(session)
    return {"title": f"📈 Track — {n} potentials first seen {sess['label']} · {UNMEASURED}",
            "unmeasured": TRACK_UNMEASURED,
            "empty_today": (f"No potential first seen yet this session — the pass runs every "
                            f"{GC.PASS_CADENCE_SEC // 60} minutes from {first} to {last} ET."),
            "today": dict({"date": session.isoformat(), "label": sess["label"], "n": n,
                           "armed_n": sum(1 for d in today if d.get("first_kind") == GC.POTENTIAL_KINDS[0]),
                           "building_n": sum(1 for d in today if d.get("first_kind") == GC.POTENTIAL_KINDS[1]),
                           "pushed_n": sum(1 for d in today if isinstance(d.get("push"), dict)
                                           and d["push"].get("state") == "pushed")},
                          **_capped([_track_row(d) for d in today])),
            "yesterday": dict({"date": prev.isoformat(),
                               "title": (f"Last session ({prev.isoformat()}) — {len(yday)} potentials and how each "
                                         "ended: states and prices only, no win/loss maths"),
                               "n": len(yday)}, **_capped([_track_row(d) for d in yday]))}


def _watch_block(pm_rows: list, post_list: list, exclude: set) -> Optional[dict]:
    """W14 — ☀️ / 🌙 list names with NO structure yet (GG S8 13:21–14:34): `exclude` = every name with a potential
    in any setup PLUS every name whose read shows a card in any setup sub (a TILE_STATES read — A+, triggered,
    partial, stopped, forming), so the line's own words "no structure yet" stay true. Display only: never pushed,
    never tracked (HIS CALL P9). None when there is none."""
    syms, seen = [], set(exclude)
    for rows, sub in ((pm_rows, "premarket"), (post_list, "postmarket")):
        for r in rows or []:
            sym = str((r or {}).get("symbol") or "").upper()
            if sym and sym not in seen:
                seen.add(sym)
                syms.append({"symbol": sym, "href": f"/chart-maps?tab=gajjala&sub={sub}&focus={sym}"})
    if not syms:
        return None
    return {"text": WATCH_HEAD + ", ".join(s["symbol"] for s in syms), "symbols": syms}


# ── the payload ───────────────────────────────────────────────────────────────────────────────────────────────────
def _awaiting(setup: str) -> Optional[dict]:
    from chart_maps.gajjala import detectors as D
    text = D._awaiting(setup)
    if not text:
        return None
    h = next((h for h in GC.PLACEHOLDER_BY_SETUP.get(setup, ())
              if any(getattr(GC, n, None) is None for n in GC.PLACEHOLDERS.get(h, ()))),
             (GC.PLACEHOLDER_BY_SETUP.get(setup) or ("?",))[0])
    e, label = SUB_META[setup]
    return {"setup": setup, "his_call": h,
            "text": f"{e} {label}: waiting for your number ({h}) — it reads nothing until you answer"}


def _ledger():
    """🏁 ledger.py, imported lazily (it imports this module's neighbours); None when it cannot load — the other subs
    still serve and the 🏁 sub serves TRACK_RECORD_FAULT."""
    try:
        from chart_maps.gajjala import ledger as LG
        return LG
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: ledger import failed: %s", exc)
        return None


def _ledger_count(st, session: date) -> Optional[int]:
    """🏁 chip: ledger.count_today over today's tracker docs and today's ledger docs; None when the ledger cannot load
    or EITHER read faulted (an unknown count is never served as 0). The tracker is read here with `st.potentials`
    directly, never through `_safe_list` (which turns a read fault into [] — a chip of 0; critic LOW 2026-10-16)."""
    LG = _ledger()
    if LG is None:
        return None
    pots = st.potentials(session)
    if pots is None:
        return None
    docs = st.ledger_docs([session])
    if docs is None:
        return None
    return LG.count_today([d for d in pots if isinstance(d, dict) and d.get("symbol") and d.get("setup")], docs)


def build(sub: str = "", *, tf: str = "", focus: str = "", limit: int = GC.TILE_LIMIT_DEFAULT, sort: str = "",
          span: str = "", now: Optional[datetime] = None, store=None, today: Optional[dict] = None) -> dict:
    """The served board. Reads Mongo only (BUILD_SPEC §3.4.1). `span` = the 🏁 Track record day picker (ignored on
    every other sub); `today` = the route's ledger.today_read answer (🏁 only, None = not read on this open)."""
    st = _store(store)
    now = now or _clock()
    session, is_today, in_window = session_for(now)
    try:
        lim = max(1, min(int(limit), GC.TILE_LIMIT_MAX))
    except (TypeError, ValueError):
        lim = GC.TILE_LIMIT_DEFAULT
    from chart_maps.gajjala import scanner as SC
    try:
        listed = SC.listed_symbols(st, session)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: listed read failed: %s", exc)
        listed = {}
    reads = [d for d in st.reads(session) if d.get("symbol")]
    if listed:
        reads = [d for d in reads if d["symbol"].upper() in listed]
    reads_by = {d["symbol"].upper(): d for d in reads}
    scan_docs = [d for d in st.scan_docs([session]) if d.get("symbol")]
    scan_by = {d["symbol"].upper(): d for d in scan_docs}
    halts_by = {d["symbol"].upper(): d for d in st.halts(session) if d.get("symbol")}
    latest = st.latest_pass()
    spass = session_pass(st, latest, session)
    # 🔄 / 🎯 (2026-10-15): the shown pass, the newest CRON pass (A10) and the lease — Mongo reads, each soft
    pass_doc = spass or latest
    pass_at = _at_utc(pass_doc)
    cron = _soft("cron pass read", _cron_ref, st, pass_doc, default=None)
    lease = _soft("lease read", st.lease_state, now, default={}) or {}
    sk = (sort or "").strip().lower() if isinstance(sort, str) else ""
    sk = sk if sk in dict(SORTS_PM) else SORT_PM_DEFAULT
    try:
        pm_rows = premarket_rows(st, session, scan_docs, spass, sk)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: premarket list failed: %s", exc)
        pm_rows = []
    post_list, unchecked = postmarket_rows(spass)
    # 🧠 the tracker + the previous session's tells, read ONCE and BEFORE resolve_sub (BUILD_SPEC4 WP-B)
    prev = _prev_market_day(session)
    pot_docs = [d for d in _safe_list(st.potentials, session) if d.get("symbol") and d.get("setup")]
    pot_prev = [d for d in _safe_list(st.potentials, prev) if d.get("symbol") and d.get("setup")]
    pot_ok = True                       # D1 on the read path: a raising potential layer never silences the A+ board
    try:
        trackers_today = {(str(d["symbol"]).upper(), d["setup"]): d for d in pot_docs}
        trackers_prev = {(str(d["symbol"]).upper(), d["setup"]) for d in pot_prev}
        try:
            ah_prev = st.ah_carry(prev)
        except Exception as exc:                                    # noqa: BLE001
            log.warning("gajjala tab: carry read failed: %s", exc)
            ah_prev = None
        prev_scan_by = {str(d["symbol"]).upper(): d for d in _safe_list(st.scan_docs, [prev]) if d.get("symbol")}
        pots = _potential_reads(reads_by, scan_by, trackers=trackers_today, trackers_prev=trackers_prev,
                                ah_prev=ah_prev, prev_scan_by=prev_scan_by)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: potential assembly failed: %s", exc)
        pot_ok, trackers_today, pots = False, {}, []
    pot_syms = {p[1]["symbol"] for p in pots}
    sub_k, resolved = resolve_sub(sub, focus, store=st, session=session, reads_by=reads_by, listed=listed,
                                  pm_syms={str(r.get("symbol")).upper() for r in pm_rows},
                                  post_syms={str(r.get("symbol")).upper() for r in post_list},
                                  potentials=pot_docs)
    tf_ask = (tf or "").strip().lower() if isinstance(tf, str) else ""
    tf_ask = tf_ask if tf_ask in TFS else ""                        # no / unknown tf → each card its read's frame
    tf_k = tf_ask or ("15m" if sub_k == "horizontal_fade" else "5m")
    sess = _session_block(now, session, is_today, in_window)

    def _row(sym):
        return dict(((scan_by.get(sym) or {}).get("last") or {}))

    # every setup's tiles — the counts on the strip, the tiles of the shown sub
    per_setup: dict = {}
    counts_by: dict = {}
    n_tiles: dict = {}
    tile_syms: set = set()                                          # names with a card in any setup sub (W14)
    for setup in GC.SETUPS:
        tiles, c = [], {k: 0 for k in COUNT_STATES}
        c["awaiting_answer"] = 0
        held = _awaiting(setup)
        for sym, doc in reads_by.items():
            r = (doc.get("setups") or {}).get(setup) or {}
            state = r.get("state") or "none"
            state = state if state in c else "none"
            awaiting = held is not None or (state == "none" and str(r.get("reason") or "").startswith("awaiting"))
            if not (awaiting and state == "none"):                     # a held read is "awaiting", never also "none"
                c[state] += 1
            if awaiting:
                c["awaiting_answer"] += 1
                continue
            if state in TILE_STATES:
                n_tiles[setup] = n_tiles.get(setup, 0) + 1
                tile_syms.add(sym)
                if setup == sub_k:                                      # only the shown sub builds its cards
                    daily = st.get_daily(session, sym) if setup == "reversal_squeeze" else None
                    tiles.append(setup_tile(doc, setup, tile_tf(r, tf_ask, tf_k), scan_row=_row(sym), sess=sess,
                                            listed=listed.get(sym), halt_doc=halts_by.get(sym), daily=daily,
                                            pass_at=pass_at))
        tiles.sort(key=order_key)
        c["listed"] = len(listed) if listed else len(reads_by)
        per_setup[setup], counts_by[setup] = tiles, c

    subs = []
    for key, e, label in GC.SUBS:
        if key == GC.LEDGER_SUB:                # 🏁 today's rows graded so far (ledger.count_today, AMENDMENTS9 E5)
            n = _soft("track record count", _ledger_count, st, session, default=None)
        else:
            n = (n_tiles.get(key, 0) if key in per_setup else len(pm_rows) if key == "premarket"
                 else len(post_list) if key == "postmarket" else len(pot_syms) if key == GC.POTENTIAL_SUB else None)
        subs.append({"key": key, "emoji": e, "label": label, "count": n})

    if sub_k in per_setup:
        counts = counts_by[sub_k]
    else:
        counts = {k: sum(c[k] for c in counts_by.values()) for k in list(COUNT_STATES) + ["awaiting_answer"]}
        counts["listed"] = len(listed) if listed else len(reads_by)
    out = {"tab": "gajjala", "sub": sub_k, "sub_resolved_from": resolved, "tf": tf_k, "subs": subs,
           "session": sess, "pass": _pass_block(pass_doc, now, session, in_window, cron=cron),
           "strip": _strip_block(spass),
           "counts": counts, "tiles": [], "graveyard_today": [], "note": board_note(),
           "empty_note": None, "rules_section": "gajjala", "push": push_block(),
           "push_potential": _soft("potential push line", push_potential_block, session),
           "awaiting": [a for a in (_awaiting(s) for s in GC.SETUPS) if a]}
    out["scan"] = _soft("scan line", scan_block, pass_doc, lease, now, in_window=in_window, session=session,
                        default=None)
    out["enterable"] = _soft("A+ banner", aplus_block, reads_by, pass_doc, now, in_window=in_window,
                             scan=out["scan"] or {}, cron=cron, session=session, default=None)
    try:
        out["graveyard_today"] = SC.graveyard_today(st, session)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("gajjala tab: graveyard read failed: %s", exc)
    if out["graveyard_today"]:
        out["graveyard_text"] = "🪦 moved to the graveyard today: " + ", ".join(out["graveyard_today"])

    if sub_k in per_setup:
        out["tiles"] = per_setup[sub_k][:lim]
        e, label = SUB_META[sub_k]
        out["empty_note"] = (f"No {e} {label} on his list right now — the next pass is at most "
                             f"{GC.PASS_CADENCE_SEC // 60} minutes away." if in_window else
                             f"No {e} {label} on the {sess['label']} list.")
        today_n = sum(1 for (_s, setup) in trackers_today if setup == sub_k)
        out["potential"] = _soft("potential strip", _potential_strip, sub_k,
                                 [p for p in pots if p[1]["setup"] == sub_k], today_n, sess=sess,
                                 in_window=in_window) if pot_ok else None
    elif sub_k == GC.POTENTIAL_SUB:
        out["tiles"] = (_soft("potential tiles", _potential_tiles, pots, st=st, session=session, tf_ask=tf_ask,
                              scan_row=_row, sess=sess, listed=listed, halts_by=halts_by, pass_at=pass_at,
                              default=[])
                        if pot_ok else [])[:lim]
        out["track"] = _soft("potential track", _track_block, pot_docs, pot_prev, session=session, prev=prev,
                             sess=sess) if pot_ok else None
        out["watch"] = _soft("potential watch line", _watch_block, pm_rows, post_list, pot_syms | tile_syms)
        out["empty_note"] = ("Nothing forming on his list right now — the next pass is at most "
                             f"{GC.PASS_CADENCE_SEC // 60} minutes away." if in_window else
                             f"Nothing was forming at the last pass ({sess['label']}).")
    elif sub_k == "premarket":
        tiles = []
        for r in pm_rows:                                           # the engine's order (today's, then the carry)
            sym = str(r["symbol"]).upper()
            tiles.append(_list_tile(sym, "premarket", reads_by.get(sym), tf_k, scan_row=_row(sym), sess=sess,
                                    listed=listed.get(sym), halt_doc=halts_by.get(sym), extra=_pm_extra(r)))
        out.update({"tiles": tiles[:lim], "sorts": [{"key": k, "label": lb} for k, lb in SORTS_PM], "sort": sk,
                    "empty_note": "No pre-market mover on his list and no after-hours carry from the last session."})
    elif sub_k == "postmarket":
        from chart_maps.gajjala import context as CX
        tiles = [_list_tile(str(d["symbol"]).upper(), "postmarket", reads_by.get(str(d["symbol"]).upper()), tf_k,
                            scan_row=_row(str(d["symbol"]).upper()), sess=sess,
                            listed=listed.get(str(d["symbol"]).upper()),
                            halt_doc=halts_by.get(str(d["symbol"]).upper()), extra=_post_extra(d))
                 for d in post_list]
        out.update({"tiles": tiles[:lim],
                    "postmarket": {"unchecked_n": unchecked, "unchecked_text": CX.unchecked_text(unchecked),
                                   "recap": recap(reads)},
                    "empty_note": "No after-hours mover has passed his three after-hours checks yet."})
    elif sub_k == "playbook":
        from chart_maps.gajjala import playbook as PB
        out["playbook"] = PB.playbook()
        out["empty_note"] = None
    elif sub_k == GC.LEDGER_SUB:
        LG = _ledger()
        span_s = span if isinstance(span, str) else ""
        out["track_record"] = (_soft("track record", LG.served_block, st, session, now, span=span_s,
                                     is_today=is_today, today=today if isinstance(today, dict) else None,
                                     default=None) if LG else None)
        out["empty_note"] = None if out["track_record"] else TRACK_RECORD_FAULT      # W16
    _strip_private(out["tiles"])
    return _plain(out)


__all__ = ["build", "resolve_sub", "order_key", "state_label", "strip_text", "session_for", "first15",
           "psych_chips", "recap", "premarket_rows", "postmarket_rows", "session_pass", "push_block",
           "push_potential_block", "board_note", "scan_block", "aplus_block", "pass_stamp", "TRACK_RECORD_FAULT"]
