"""🧮 FLOAT AND SHARE-COUNT SOURCE AUDIT — the nightly AND the re-runnable probe (2026-11-26).

THE ASK (Ajay 2026-11-26 ~21:20 ET, verbatim)
  "Also the Float share count issue and SI discrepancy happened too many times need to do something about it"

What this module is (spec floatguard rev 2 §3.6, package be-audit): once a night, inside the 20:15 ET nightly fence
(chart_maps.gajjala.nightly -> high_si.source_audit_night), it
  1. re-reads the second dated float (Massive's free float) for EVERY checked share-basis name, in bulk
     (share_basis.fetch_mfloats, one GET per SB_MFLOAT_CHUNK names, at most max_refresh() GETs) and stores it
     (share_basis.store_mfloats) — skipped when share_basis.SB_MFLOAT_WHEN is off;
  2. spends ONE budget of max_refresh() outside reads, tonight's names first: a due share-basis refresh for tonight's
     names (share_basis.refresh_symbol — its SEC pacer and 403 / 429 stop are its own), then one splits read for every
     name whose second float is older than the splits window on file (share_basis.widen_splits); the rest `deferred`;
  3. builds every block through THE engine (read.si_map — source_check.compare / apply inside si_block) and one
     source_check.audit_row per name;
  4. writes ONE gajjala_state doc per night (STATE_FMT) + the LATEST_ID pointer, through the store's set_state only.
The three groups: 🩳 = the names the 🩳 sub listed tonight (the 🏁 session doc), 🔭 = the follow-up names
(si_follow.tracked, pins included), 👀 = the Watch names (gajjala_watch.run_rules.watch_names). Each group is read in its
own try: a group that cannot be read is named in `faults` and the others stand.

The dry run (`write=False`, `--dry`) writes NOTHING anywhere: the fetched second floats (and, with `--widen`, the wider
splits reads) are laid over the stored docs IN MEMORY (read.si_map(basis_over=…)) — the same builder share_basis uses
(share_basis.mfloat_sub). It is the re-runnable probe of spec §5.4.

Display only: no rule, gate, sort, push or lane reads this. No division in this file. What two data providers say —
neither was checked against a filing. Not a signal. UNMEASURED. Not advice.
Doc: docs/short_interest/source_audit_2026_11_26.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

from short_interest import basis_math as BM
from short_interest import client as SIC
from short_interest import read as SR
from short_interest import share_basis as SB
from short_interest import source_check as SCK

log = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

STATE_FMT = "si_source_audit|{date}"      # TRANSPORT — one gajjala_state doc per night (chart_maps.gajjala.store.STATE)
LATEST_ID = "si_source_audit_latest"      # TRANSPORT — {"date", "at"}
VERSION = 1
GROUPS = ("listed", "followed", "watch")
GROUP_WORDS = {"listed": "🩳", "followed": "🔭", "watch": "👀"}
SCOPES = ("groups", "all")
BLOCK_KEYS = ("title", "summary_text", "asof_text", "heads", "rows", "shown_text", "rule_label", "rule_text",
              "honesty", "fault_text", "empty_text", "n", "n_differ", "n_contested", "n_window")
HEADS = [["ticker", "Ticker"], ["on", "Listed on"], ["float", "Float we use"], ["other", "Second float"],
         ["apart", "Apart"], ["shares", "Shares out we use"], ["counts", "Share counts on file"], ["word", "Chip word"]]
NIGHT_KEYS = ("session", "names", "rows", "differ", "contested", "held", "window", "float_gets", "refreshed",
              "widened", "deferred", "written", "faults")
COMPARED_STATES = ("compared", "contested")

TITLE = "🧮 Float and share-count sources · checked nightly"
SUMMARY_TEXT = "🧮 Sources · {c} {x} contested · {d} of {n} compared floats differ · {w} not compared yet"
EMPTY_SUMMARY = "🧮 Sources · nothing checked yet"
EMPTY_TEXT = "No audit is on file yet — the {at} ET night writes the first one."
ASOF_TEXT = "checked nightly at {at} ET · last {md}"
SHOWN_TEXT = "Showing the first {lim} rows of {n} — every row is counted above."
RULE_LABEL = "ⓘ how this is checked"
RULE_HEAD = ("Every night at {at} ET the names on the 🩳 list, the 🔭 follow-up and the 👀 Watch are read again: the "
             "float the chip divides by ({y}'s, with its read date) beside {m}'s free float (its effective date), "
             "split-adjusted with the splits on file. A second float dated before the splits on file is not compared "
             "until the splits read reaches back to its date. ")
RULE_TAIL = " At most {cap} outside reads a night; the rest wait for the next night."
HONESTY = ("Counts of two providers differing, read once a night; this table never changes a % on a chip. What two data "
           "providers say — neither was checked against a filing. Not a signal. UNMEASURED. Not advice.")
WORD_CONTESTED = "%s — second float disagrees"
WORD_HELD = "%s — held below %s"
DASH = "—"
NOT_SHOWN_FLOAT = "not shown — float stale"
OTHER_NONE = "none on file"
OTHER_UNREAD = "not read"
NOT_COMPARED = "not compared — %s"
WHY = {"units": "another listing type", "no_splits": "the splits read is not on file",
       "window": "the splits on file start after a float's date", "split_day": "a split on the day of a count"}
WRITES_LINE = "attempted writes: %d"
REFUSED_LINE = "refused: --rows-out must be outside the backend tree (%s)"
WRITE_METHODS = ("update_one", "update_many", "replace_one", "insert_one", "insert_many", "delete_one",
                 "delete_many", "bulk_write", "find_one_and_update", "find_one_and_replace", "find_one_and_delete")


# ───────────────────────────────────────────── the house constants, read at CALL time
def max_refresh() -> int:
    """GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS — this job's OWN instance of the nightly per-run cap."""
    from chart_maps.gajjala import constants as GC
    return int(GC.LEDGER_BACKFILL_MAX_SYMBOL_DAYS)


def rows_max() -> int:
    from chart_maps.gajjala import constants as GC
    return int(GC.LEDGER_ROWS_MAX)


def _night_at() -> str:
    from chart_maps.gajjala import constants as GC
    return str(GC.LEDGER_GRADE_AT_ET)


def _default_cap() -> int:
    return max_refresh()


def _under_test() -> bool:
    """The share_basis `kick` guard shape: a pytest run that injected nothing reads nothing and calls nothing."""
    return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def _up(symbols) -> list:
    out: list = []
    for s in symbols or []:
        if isinstance(s, str) and s.strip() and s.strip().upper() not in out:
            out.append(s.strip().upper())
    return out


def _utc_iso(now) -> str:
    n = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    n = n if n.tzinfo is not None else n.replace(tzinfo=timezone.utc)
    return n.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _et_day(now):
    n = now if isinstance(now, datetime) else datetime.now(timezone.utc)
    n = n if n.tzinfo is not None else n.replace(tzinfo=timezone.utc)
    return n.astimezone(ET).date()


def _blank() -> dict:
    out = dict.fromkeys(NIGHT_KEYS)
    out.update(names={g: 0 for g in GROUPS}, rows=0, differ=0, contested=0, held=0, window=0, float_gets=0,
               refreshed=0, widened=0, deferred=0, written=False, faults=[])
    return out


# ───────────────────────────────────────────── the dry run's two in-memory views (no write method on either)
class _OverlaidColl:
    """The basis collection seen through the dry run's overlay: `find` answers every stored doc with its overlay laid
    over it (in memory). Reads only."""

    def __init__(self, coll, over: dict):
        self._c, self._over = coll, over

    def find(self, *args, **kw):
        for doc in self._c.find(*args, **kw):
            if isinstance(doc, dict):
                o = self._over.get(doc.get("_id"))
                yield {**doc, **o} if isinstance(o, dict) else doc


class _Overlaid:
    """A READ-ONLY view of the db for the dry run's widen step: only the basis collection is served (overlaid)."""

    def __init__(self, db, over: dict):
        self._db, self._over = db, over

    def __getitem__(self, name):
        if name != SB.SB_COLL:
            raise KeyError(name)
        return _OverlaidColl(self._db[name], self._over)


class _CountColl:
    """Read-through; every write method asked of the collection is counted (the CLI's last line)."""

    def __init__(self, coll, box: list):
        self._c, self._box = coll, box

    def __getattr__(self, name):
        a = getattr(self._c, name)
        if name not in WRITE_METHODS:
            return a

        def counted(*args, **kw):
            self._box[0] += 1
            return a(*args, **kw)
        return counted


class _CountDB:
    def __init__(self, db, box: list):
        self._db, self._box = db, box

    def __getitem__(self, name):
        return _CountColl(self._db[name], self._box)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return self[name]


class _CountStore:
    def __init__(self, st, box: list):
        self._st, self._box = st, box

    def set_state(self, sid, fields):
        self._box[0] += 1
        return self._st.set_state(sid, fields)

    def __getattr__(self, name):
        return getattr(self._st, name)


# ───────────────────────────────────────────── the three groups
def names(st, db, now) -> dict:
    """{"listed": tonight's 🩳 session-doc symbols, "followed": si_follow.tracked (pins included), "watch":
    run_rules.watch_names, "faults": [group…]} — each group in its OWN try; a group that cannot be read is empty and
    named in faults, the others stand."""
    out = {g: [] for g in GROUPS}
    out["faults"] = []
    try:
        from chart_maps.gajjala import si_track as SIT
        session = SIT.tonight(now)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("si source audit: no session: %s", type(exc).__name__)
        out["faults"] += ["listed", "followed"]
        session = None
    if session is not None:
        try:
            doc = SIT.session_doc(st, session, strict=True)
            rows = doc.get("rows") if isinstance(doc, dict) else None
            if not doc or not isinstance(rows, list):
                # nothing on file (record_night did not write tonight's 🏁 doc): a fault, never "no 🩳 names" (2026-11-27)
                log.warning("si source audit: no 🏁 session doc for %s", session)
                out["faults"].append("listed")
            else:
                out["listed"] = _up(r.get("symbol") for r in rows if isinstance(r, dict))
        except Exception as exc:                               # noqa: BLE001
            log.warning("si source audit: the listed names failed: %s", type(exc).__name__)
            out["faults"].append("listed")
        try:
            from chart_maps.gajjala import si_follow as SF
            out["followed"] = _up(SF.tracked(st, session))
        except Exception as exc:                               # noqa: BLE001
            log.warning("si source audit: the followed names failed: %s", type(exc).__name__)
            out["faults"].append("followed")
    try:
        from chart_maps.gajjala_watch import run_rules as RR
        out["watch"] = _up(RR.watch_names(db, now))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("si source audit: the watch names failed: %s", type(exc).__name__)
        out["faults"].append("watch")
    return out


# ───────────────────────────────────────────── the night
def audit_night(now, *, store=None, db=None, names_fn=None, fetch=None, refresh=None, widen=None, sleep=time.sleep,
                max_refresh=None, write=True, outside=True, scope="groups", widen_dry=False,
                sink: Optional[dict] = None) -> dict:
    """One audit night (spec §3.6 steps 1-7). -> NIGHT_KEYS (counts; `names` = per-group counts). Never raises.
    `fetch(symbols)` / `refresh(sym, db)` / `widen(sym, db, now=, store=)` are the seams (default: share_basis's own);
    under pytest a seam left None makes no call. `write=False` writes nothing anywhere (overlay in memory);
    `outside=False` makes no outside call. `sink` (a dict) receives every built row, the counts texts and the doc."""
    out = _blank()
    try:
        if (store is None or db is None) and _under_test():
            out["faults"].append("no_store")
            return out
        from chart_maps.gajjala import si_track as SIT
        from chart_maps.gajjala import store as ST
        st = store if store is not None else ST.default()
        d = db if db is not None else SIC._get_db()
        if st is None or d is None or st.coll(ST.STATE) is None:
            out["faults"].append("no_store")
            return out
        cap = int(max_refresh) if isinstance(max_refresh, int) and not isinstance(max_refresh, bool) else _default_cap()
        scope = scope if scope in SCOPES else SCOPES[0]
        session = SIT.tonight(now)
        s_iso = session.isoformat()
        out["session"] = s_iso
        faults = out["faults"]

        # 2. the names: the three groups (each fenced), then (scope "all") every other checked name
        try:
            nm = (names_fn or names)(st, d, now) or {}
        except Exception as exc:                               # noqa: BLE001
            log.warning("si source audit: names failed: %s", type(exc).__name__)
            nm = {"faults": list(GROUPS)}
        faults += [f for f in (nm.get("faults") or []) if isinstance(f, str)]
        groups_of: dict = {}
        tonight: list = []
        by_group: dict = {}
        for g in GROUPS:
            by_group[g] = _up(nm.get(g))
            out["names"][g] = len(by_group[g])
            for s in by_group[g]:
                groups_of.setdefault(s, []).append(g)
                if s not in tonight:
                    tonight.append(s)
        checked = SB.checked_symbols(d)
        rest = [s for s in checked if s not in groups_of]
        row_names = tonight + (rest if scope == "all" else [])
        docs = SB.load(_up(tonight + checked), d)
        overlay: dict = {}

        def _doc(s):
            doc = docs.get(s)
            if not isinstance(doc, dict):
                return None
            return {**doc, **overlay[s]} if s in overlay else doc

        # 3. the second float for every checked name, in bulk
        if outside and SB.mfloat_on() and checked and not (fetch is None and _under_test()):
            f = fetch or SB.fetch_mfloats
            got: dict = {}
            step = int(SB.SB_MFLOAT_CHUNK)
            for i in range(0, len(checked), step):
                if out["float_gets"] >= cap:
                    faults.append("float_cap")
                    break
                if out["float_gets"]:
                    sleep(SIC.SI_BULK_SLEEP_SEC)
                out["float_gets"] += 1
                try:
                    ans = f(checked[i:i + step]) or {}
                except Exception as exc:                       # noqa: BLE001
                    log.warning("si source audit: float read failed: %s", type(exc).__name__)
                    faults.append("float_read")
                    ans = {}
                if isinstance(ans, dict):
                    got.update({str(k).strip().upper(): v for k, v in ans.items() if isinstance(k, str)})
            if write:
                SB.store_mfloats(d, got, now)
                docs = SB.load(_up(tonight + checked), d)
            else:
                for s, g in got.items():
                    held = docs.get(s)
                    if isinstance(held, dict):
                        overlay[s] = {"mfloat": SB.mfloat_sub(held.get("mfloat"), g, now)}

        # 4. ONE budget of outside reads, tonight's names first; `deferred` counts NAMES (a name past the budget for
        #    both its refresh and its splits read is one name — 2026-11-27)
        used = 0
        deferred: list = []
        if outside:
            recs = SIC.short_interest_map(tonight, db=d) if (write and tonight) else {}
            order = tonight + [s for s in checked if s not in groups_of]
            for s in order:
                if write and s in groups_of and not (refresh is None and _under_test()):
                    if SB.is_due(docs.get(s), recs.get(s), now):
                        if used >= cap:
                            deferred.append(s)
                        else:
                            if used:
                                sleep(SIC.SI_BULK_SLEEP_SEC)
                            used += 1
                            try:
                                (refresh or SB.refresh_symbol)(s, d)
                                out["refreshed"] += 1
                            except Exception as exc:           # noqa: BLE001
                                log.warning("si source audit: %s refresh failed: %s", s, type(exc).__name__)
                                faults.append("refresh:" + s)
                            docs.update(SB.load([s], d))
                doc = _doc(s)
                if doc is None or not SB.needs_window(doc) or not (write or widen_dry):
                    continue
                if widen is None and _under_test():
                    continue
                if used >= cap:
                    deferred.append(s)
                    continue
                if used:
                    sleep(SIC.SI_BULK_SLEEP_SEC)
                used += 1
                try:
                    res = (widen or SB.widen_splits)(s, d if write else _Overlaid(d, overlay), now=now, store=write)
                except Exception as exc:                       # noqa: BLE001
                    log.warning("si source audit: %s widen failed: %s", s, type(exc).__name__)
                    res = {"status": "failed", "splits": None}
                res = res if isinstance(res, dict) else {}
                if res.get("status") == "widened":
                    out["widened"] += 1
                    if not write and isinstance(res.get("splits"), dict):
                        overlay.setdefault(s, {})["splits"] = res["splits"]
                if write:
                    docs.update(SB.load([s], d))
            out["deferred"] = len(set(deferred))

        # 5. the blocks through THE engine (stored docs, + the overlay under a dry run)
        blocks: dict = {}
        today = _et_day(now)
        step = int(SR.MAP_MAX_SYMBOLS)
        for i in range(0, len(row_names), step):
            try:
                blocks.update(SR.si_map(row_names[i:i + step], d, today, basis_over=overlay or None) or {})
            except Exception as exc:                           # noqa: BLE001
                log.warning("si source audit: block read failed: %s", type(exc).__name__)
                faults.append("blocks")
        bdocs = {s: _doc(s) for s in row_names}

        # 6. one row per name
        rows, texts = [], {}
        for s in row_names:
            r = SCK.audit_row(blocks.get(s), bdocs.get(s), groups_of.get(s, []))
            r["symbol"] = s
            rows.append(r)
            texts[s] = BM.share_counts_text(r["counts"], bdocs.get(s)) if r["counts"] else None
        out["rows"] = len(rows)
        cnt = _counts(rows)
        for k in ("differ", "contested", "held", "window"):
            out[k] = cnt[k]
        mine = [r for r in rows if r["groups"]]
        doc = {"date": s_iso, "at": _utc_iso(now), "version": VERSION, "names": by_group, "rows": mine,
               "texts": {r["symbol"]: texts.get(r["symbol"]) for r in mine}, "counts": _counts(mine),
               "calls": {"float_gets": out["float_gets"], "refreshed": out["refreshed"], "widened": out["widened"],
                         "deferred": out["deferred"]},
               "modes": modes(), "faults": list(dict.fromkeys(faults))}
        if isinstance(sink, dict):
            sink.update(rows=rows, texts=texts, doc=doc)

        # 7. ONE write + the pointer (a failed write is a fault and the pointer is not moved)
        if write:
            if _set_verified(st, STATE_FMT.format(date=s_iso), doc):
                if _set_verified(st, LATEST_ID, {"date": s_iso, "at": doc["at"]}):
                    out["written"] = True
                else:
                    faults.append("write:latest")
            else:
                faults.append("write")
        out["faults"] = list(dict.fromkeys(faults))
    except Exception as exc:                                   # noqa: BLE001
        log.warning("si source audit: night failed: %s", type(exc).__name__)
        out["faults"] = list(dict.fromkeys(list(out.get("faults") or []) + ["night:" + type(exc).__name__]))
    return out


def modes() -> dict:
    return {"contest": SCK.contest_mode(), "contest_by": SCK.contest_by(), "min_rel": SCK.CONTEST_MIN_REL,
            "mfloat": SB.SB_MFLOAT_WHEN}


def _counts(rows) -> dict:
    rs = [r for r in rows or [] if isinstance(r, dict)]
    states: dict = {}
    for r in rs:
        states[r.get("state")] = states.get(r.get("state"), 0) + 1
    return {"n": len(rs), "compared": sum(1 for r in rs if r.get("state") in COMPARED_STATES),
            "differ": sum(1 for r in rs if r.get("differ")), "contested": sum(1 for r in rs if r.get("contested")),
            "held": sum(1 for r in rs if r.get("held")), "window": sum(1 for r in rs if r.get("state") == "window"),
            "states": {str(k): v for k, v in states.items()}}


def _set_verified(st, sid: str, fields: dict) -> bool:
    """ONE st.set_state, then a fault-aware read-back (the store's upsert logs and swallows a raise): True only when the
    doc on file carries this write's `at`."""
    from chart_maps.gajjala import si_track as SIT
    try:
        st.set_state(sid, fields)
    except Exception as exc:                                   # noqa: BLE001
        log.warning("si source audit: write of %s failed: %s", sid, type(exc).__name__)
        return False
    back = SIT.state_read(st, sid)
    return isinstance(back, dict) and back.get("at") == fields.get("at")


# ───────────────────────────────────────────── the served 🧮 fold
def stored_rows(st) -> tuple:
    """(the latest night's doc | None, fault: bool) through si_track.state_read — a read fault is never "nothing"."""
    from chart_maps.gajjala import si_track as SIT
    ptr = SIT.state_read(st, LATEST_ID)
    if ptr is None:
        return None, True
    day = ptr.get("date")
    if not isinstance(day, str) or not day:
        return None, False
    doc = SIT.state_read(st, STATE_FMT.format(date=day))
    if doc is None:
        return None, True
    return (doc if doc else None), False


def fault_block() -> dict:
    from chart_maps.gajjala import high_si as HS
    return {"fault_text": HS.SIA_FAULT_TEXT}


def _n(v) -> Optional[str]:
    return format(int(v), ",") if isinstance(v, (int, float)) and not isinstance(v, bool) and v > 0 else None


def _is_pct(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and v == v


def _src_row_text(r, with_pct=True) -> Optional[str]:
    if not isinstance(r, dict) or _n(r.get("shares")) is None:
        return None
    kind = "read" if r.get("date_kind") == "read" else "as of"
    s = "%s · %s, %s %s" % (_n(r["shares"]), r.get("label") or "", kind, BM._md(r.get("as_of")))
    if with_pct and _is_pct(r.get("pct")):
        s += " · " + SR._pct_tier(r["pct"])
    return s


def _shares_text(cu) -> Optional[str]:
    if not isinstance(cu, dict) or _n(cu.get("shares")) is None:
        return None
    src = str(cu.get("source") or "")
    low = src.lower()
    if "yfinance" in low or "yahoo" in low:
        who, kind = SCK.SOURCE_WORDS[SCK.SRC_YAHOO], "read"
    elif src.startswith("SEC"):
        who, kind = "SEC cover", "as of"
    else:
        who, kind = (src or DASH), "as of"
    return "%s · %s, %s %s" % (_n(cu["shares"]), who, kind, BM._md(cu.get("as_of")))


def _word(r) -> str:
    t = r.get("tier")
    w = SR.TIER_WORDS.get(t) if t in SR.TIER_WORDS else None
    if r.get("held") and w:
        return WORD_HELD % (w, SR.TIER_WORDS[SR.TIER_EXTREME])
    if r.get("contested") and w:
        return WORD_CONTESTED % w
    return w or DASH


def cells(r, counts_text=None) -> dict:
    """The served cells of ONE stored audit row (head key -> str | None). A `no_si` row carries no numbers."""
    st = r.get("state")
    out = dict.fromkeys(k for k, _ in HEADS)
    out["ticker"] = r.get("symbol")
    out["on"] = " ".join(GROUP_WORDS[g] for g in r.get("groups") or [] if g in GROUP_WORDS) or None
    if st == SCK.STATE_NO_SI:
        return out
    used, other = r.get("used"), r.get("other")
    out["float"] = _src_row_text(used) if used else (NOT_SHOWN_FLOAT if st == "no_float" else None)
    if st in COMPARED_STATES:
        out["other"] = _src_row_text(other)
        sw = SCK.spread_words(r.get("float_rel"))
        out["apart"] = sw[:-len(" apart")] if sw.endswith(" apart") else (sw or None)
    elif st == "none":
        out["other"] = OTHER_NONE
    elif st == "unread":
        out["other"] = OTHER_UNREAD
    elif st == "no_float":
        out["other"] = _src_row_text(dict(other or {}, shares=(other or {}).get("published")), with_pct=False)
    elif st in WHY:
        out["other"] = NOT_COMPARED % WHY[st]
    out["shares"] = _shares_text(r.get("count_used"))
    out["counts"] = counts_text if isinstance(counts_text, str) and counts_text else None
    out["word"] = _word(r)
    return out


def _sort_key(r):
    rel = r.get("float_rel")
    return (0 if r.get("contested") else 1, 0 if _is_pct(rel) else 1, -(rel if _is_pct(rel) else 0),
            str(r.get("symbol") or ""))


def _href(sym) -> Optional[str]:
    try:
        from chart_maps.gajjala import tab as GT
        return GT.chart_href(sym, "5m")
    except Exception as exc:                                   # noqa: BLE001
        log.warning("si source audit: href failed: %s", type(exc).__name__)
        return None


def rule_text() -> str:
    return (RULE_HEAD.format(at=_night_at(), y=SCK.SOURCE_WORDS[SCK.SRC_YAHOO], m=SCK.SOURCE_WORDS[SCK.SRC_MASSIVE])
            + SCK.rules_sentence() + RULE_TAIL.format(cap=max_refresh()))


def served_block(st, session, now) -> dict:
    """The 🩳 fold's `si_audit` block (BLOCK_KEYS). Mongo reads only (the pointer + the latest night's doc). No doc ->
    the empty block (not a fault). RAISES on a read fault (high_si serves its SIA_FAULT_TEXT)."""
    from chart_maps.gajjala import si_track as SIT
    if st is None:
        from chart_maps.gajjala import store as ST
        st = ST.default()
    doc, fault = stored_rows(st)
    if fault:
        raise SIT.ReadFault(LATEST_ID)
    out = dict.fromkeys(BLOCK_KEYS)
    out.update(title=TITLE, heads=[list(h) for h in HEADS], rule_label=RULE_LABEL, rule_text=rule_text(),
               honesty=HONESTY, rows=[], n=0, n_differ=0, n_contested=0, n_window=0)
    if not doc:
        out.update(summary_text=EMPTY_SUMMARY, empty_text=EMPTY_TEXT.format(at=_night_at()))
        return out
    rows = sorted([r for r in doc.get("rows") or [] if isinstance(r, dict) and isinstance(r.get("symbol"), str)],
                  key=_sort_key)
    texts = doc.get("texts") if isinstance(doc.get("texts"), dict) else {}
    c = _counts(rows)
    lim = rows_max()
    shown = []
    for r in rows[:lim]:
        shown.append({"symbol": r["symbol"], "href": _href(r["symbol"]), "contested": bool(r.get("contested")),
                      "held": bool(r.get("held")), "differ": bool(r.get("differ")),
                      "cells": cells(r, texts.get(r["symbol"]))})
    out.update(summary_text=SUMMARY_TEXT.format(c=c["contested"], x=SR.TIER_WORDS[SR.TIER_EXTREME], d=c["differ"],
                                                n=c["compared"], w=c["window"]),
               asof_text=ASOF_TEXT.format(at=_night_at(), md=BM._md(doc.get("date"))), rows=shown,
               shown_text=SHOWN_TEXT.format(lim=lim, n=len(rows)) if len(rows) > lim else None,
               n=c["n"], n_differ=c["differ"], n_contested=c["contested"], n_window=c["window"],
               empty_text=None if rows else EMPTY_TEXT.format(at=_night_at()))
    return out


# ───────────────────────────────────────────── the CLI (the re-runnable probe)
def table_text(rows, texts=None) -> str:
    """The CLI's plain table: one line per row, the served cells joined by ' | ' (an empty cell prints a dash)."""
    texts = texts if isinstance(texts, dict) else {}
    lines = [" | ".join(label for _, label in HEADS) + " | State"]
    for r in sorted([r for r in rows or [] if isinstance(r, dict)], key=_sort_key):
        c = cells(r, texts.get(r.get("symbol")))
        lines.append(" | ".join(str(c.get(k) or DASH) for k, _ in HEADS) + " | " + str(r.get("state")))
    return "\n".join(lines)


def _refused(path: str) -> bool:
    """A --rows-out path inside the module's own (backend) tree is refused."""
    try:
        p = Path(path).expanduser().resolve()
        tree = Path(__file__).resolve().parents[1]
        return p == tree or tree in p.parents
    except Exception:                                          # noqa: BLE001
        return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="short_interest.source_audit", description=__doc__.split("\n")[0])
    mode = ap.add_mutually_exclusive_group()
    mode.add_argument("--dry", action="store_true", help="outside reads, NOTHING written (overlay in memory)")
    mode.add_argument("--stored", action="store_true", help="no outside call, nothing written: the stored docs")
    ap.add_argument("--all", action="store_true", help="every checked name, not only the three groups")
    ap.add_argument("--widen", action="store_true", help="with --dry: the wider splits reads too (in memory)")
    ap.add_argument("--symbols", help="comma list: narrows the rows printed, not the reads")
    ap.add_argument("--cuts", action="store_true", help="print source_check.cut_table after the table")
    ap.add_argument("--rows-out", help="write the rows as JSON here (never inside the backend tree)")
    args = ap.parse_args(argv)
    if args.rows_out and _refused(args.rows_out):
        print(REFUSED_LINE % args.rows_out)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    from chart_maps.gajjala import store as ST
    box = [0]
    st, d = ST.default(), SIC._get_db()
    st = _CountStore(st, box) if st is not None else None
    d = _CountDB(d, box) if d is not None else None
    write = not (args.dry or args.stored)
    sink: dict = {}
    now = datetime.now(timezone.utc)
    res = audit_night(now, store=st, db=d, write=write, outside=not args.stored,
                      scope=SCOPES[1] if args.all else SCOPES[0], widen_dry=bool(args.widen and args.dry), sink=sink)
    rows = sink.get("rows") or []
    want = set(_up((args.symbols or "").split(","))) if args.symbols else None
    shown = [r for r in rows if want is None or r.get("symbol") in want]
    print(table_text(shown, sink.get("texts")))
    if args.cuts:
        print(json.dumps(SCK.cut_table(rows), default=str))
    if args.rows_out:
        with open(args.rows_out, "w", encoding="utf-8") as fh:
            json.dump({"at": _utc_iso(now), "scope": SCOPES[1] if args.all else SCOPES[0], "modes": modes(),
                       "rows": rows}, fh, default=str, ensure_ascii=False)
    print(json.dumps({k: res.get(k) for k in NIGHT_KEYS}, default=str))
    print(WRITES_LINE % box[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
