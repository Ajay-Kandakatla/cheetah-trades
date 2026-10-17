"""⏪ Gajjala replay — today's detectors re-run on a past session that has NO record (2026-10-16 night, DECISIONS11 D4 /
D6 / D10, BUILD_SPEC11 §3.12 / §3.13, AMENDMENTS11 F10 / F11 / F18).

THE ASK (Ajay 2026-10-16 ~22:30 ET, verbatim):
  "Would you be able to back test for the past week from his alerts any way to do so? build a pre historic timeline or so?"

WHAT IT IS. An OFFLINE, one-shot, by-hand script (the nightly never runs it). For each session asked it rebuilds the
study's same-day universe from the study cache (`gajjala_study.superset`), replays every name through the tab's own
detectors on the 5-minute pass grid (`gajjala_study.study_symbol_day`, method v2, no placebo pool), keeps the A+ breaks
the live push would have recorded (entry_class aplus, no variant, no grade, inside `window_reason`), and grades each one
with the 🏁 ledger's OWN trade math (`ledger.grade` over `ledger.session_bounds`) on the cache's as-printed minute bars:
the same column, and the next column when the next session's minutes are cached (or fetched ONCE through the study's
own as-printed fetcher, never written; `--offline` never fetches). The 5-minute tape (`tape.bars5`) rides on each row.

WHAT IT IS NOT. Not a measurement: these rows NEVER rang, sit on their own ⏪ line, never enter a count or a % of sent
alerts (live / shadow / entry), and the nightly grade step never touches them. The 2026-10-14 study read NULL and this
changes nothing. No win rate, no expectancy, no verdict is computed or written (replay.json carries counts only).

REFUSALS (each listed in replay.json, never replayed):
  * 09:30–16:00 ET on a weekday — before anything is read (no override);
  * `--write` without a 7–40 hex `--sha` (the container has no git: the main session passes the worktree's HEAD);
  * a session that is not a market day, or not completed yet (`gajjala_study.default_end`);
  * an NYSE half day the calendar does not list (`gajjala_study.half_day_unlisted`);
  * a session with ANY gajjala_alerts / gajjala_scan doc on file (the record stands), or whose records cannot be read;
  * a session whose grouped-daily file (or its prior session's) is not in the cache.
The study cache is opened with `offline=True` ALWAYS (it is mounted read-only; offline never writes). A directory
without the study's layout marker is refused (the cache would otherwise write one).

WRITES. Files under `--out` (events.csv — every event seen, kept or not; replay.json — counts only). Mongo ONLY with
`--write`: one `store.upsert_replay(doc)` per kept event into the NEW `gajjala_replay` collection (§3.12 doc; re-runs
replace — idempotent). Nothing else is ever written.

WHAT A REPLAY CANNOT KNOW: `ledger.REPLAY_CAVEATS` (stored on every doc, in order).

RUN (the main session, a throwaway api container, outside 09:30–16:00 ET; outputs under /replay_out — AMENDMENTS11 F18):
  docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/dry
  docker exec -i -w /app cheetah-tmp-gr-api python -m scripts.gajjala_replay --sessions 2026-10-09 2026-10-12 --cache /cache --out /replay_out/write --write --sha <the worktree HEAD>
  smoke (cache only, never a fetch): add --offline --types none

EXIT: 0 when at least one session was replayed · 2 refused before reading (RTH, --sha, the cache) · 3 every session refused.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

from chart_maps.gajjala import ledger as LG
from chart_maps.gajjala import store as ST
from chart_maps.gajjala import tape as TP
from daytrading.data import ET_PREMARKET_OPEN
from scripts import gajjala_study as S

log = logging.getLogger("scripts.gajjala_replay")

ET = ZoneInfo("America/New_York")
UTC = timezone.utc
ONE_MIN = pd.Timedelta(minutes=1)
UNIVERSE = "study same-day q"                    # BUILD_SPEC11 §3.12 — the frozen doc value
SHA_RE = re.compile(r"^[0-9a-fA-F]{7,40}$")      # BUILD_SPEC11 §3.13 step 2: a 7–40 hex git sha
DROP_KEYS = ("not_aplus", "variant", "grade", "window")
GRADE_COLS = ("entry", "outcome", "reason", "fill_px", "fill_t", "exit_t", "best_pct", "close_pct")
EVENT_COLS = (("date", "symbol", "setup", "frame", "entry_bar_t", "pass_t", "trigger", "stop", "risk_pct", "kept",
               "why_dropped")
              + tuple(f"same_{k}" for k in GRADE_COLS) + tuple(f"next_{k}" for k in GRADE_COLS) + ("bars5_n",))
WHY_NOT_COMPLETED = "not a completed session"
WHY_HALF_DAY = "an NYSE half day the calendar does not list (the study skips it)"
WHY_RECORDS_UNREAD = "records unreadable"
WHY_RECORDS = "{n} gajjala_alerts / gajjala_scan docs on file — the record stands, never replayed"
WHY_GROUPED = "grouped not cached"


def _f(x) -> Optional[float]:
    """A plain float (BSON / JSON safe) or None."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if v == v else None


def _detectors_sha256() -> Optional[str]:
    try:
        return hashlib.sha256(Path(S.D.__file__).read_bytes()).hexdigest()
    except OSError:
        return None


def _parse(argv) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="⏪ Gajjala replay — today's detectors on a past session with no record "
                                             "(offline, one-shot; DECISIONS11 D4).")
    ap.add_argument("--sessions", nargs="+", type=date.fromisoformat, required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--write", action="store_true", help="upsert one gajjala_replay doc per kept event")
    ap.add_argument("--sha", default=None, help="git HEAD of the worktree (required with --write)")
    ap.add_argument("--offline", action="store_true", help="never fetch a missing next-session day")
    ap.add_argument("--types", choices=("store", "none"), default="store")
    ap.add_argument("--symbols", default="", help="comma list — a smoke run only")
    return ap.parse_args(argv)


def _refusal(d: date, now_et: datetime, store, cache) -> tuple:
    """-> (why | None, prev_session, rows, prev_rows) — §3.13 step 4, in order."""
    if not S.is_market_day(d) or d > S.default_end(now_et):
        return WHY_NOT_COMPLETED, None, None, None
    if S.half_day_unlisted(d):
        return WHY_HALF_DAY, None, None, None
    try:
        n = store.records_on(d)
    except Exception as exc:                                        # noqa: BLE001 — an unreadable record is no "none"
        log.warning("records_on %s raised: %s", d, type(exc).__name__)
        n = None
    if n is None:
        return WHY_RECORDS_UNREAD, None, None, None
    if n > 0:
        return WHY_RECORDS.format(n=n), None, None, None
    days = S.sessions_back(d, 1, cache)
    if len(days) < 2 or days[-1][0] != d:
        return WHY_GROUPED, None, None, None
    (prev, prev_rows), (_d, rows) = days[-2], days[-1]
    return None, prev, rows, prev_rows


def _blank_session() -> dict:
    return {"state": "replayed", "why": None, "superset": 0, "listed": 0, "events": 0, "kept": 0,
            "dropped": {k: 0 for k in DROP_KEYS}, "same_graded": 0, "next_graded": 0, "next_not_cached": 0,
            "same_not_cached": 0, "split": 0, "split_unread": 0, "no_bars": 0, "failed": 0, "type_unknown_kept": 0}


def _why_dropped(ev: dict, d: date) -> Optional[str]:
    """§3.13 step 6: keep an event iff aplus, no variant, no grade, inside the push window."""
    if ev.get("entry_class") != "aplus":
        return DROP_KEYS[0]
    if ev.get("variant"):
        return DROP_KEYS[1]
    if ev.get("grade"):
        return DROP_KEYS[2]
    try:
        bt = S.parse_bar_t(ev["entry_bar_t"])
        why = S.window_reason(bt, d, ev["frame"])
    except Exception:                                               # noqa: BLE001 — an unreadable bar is not in window
        why = "unreadable"
    return DROP_KEYS[3] if why is not None else None


def _split_cell(h: str, sp, b: dict, same: Optional[dict]) -> dict:
    """The ledger's split cell (grade_step's shapes): never graded, the bars across a split are not comparable."""
    if h == "same":
        return dict(LG._blank(h), reason="split",
                    split_on=sp if isinstance(sp, str) else b["same_date"].isoformat(),
                    end_t=LG._iso_t(b["same_end"]), end_date=b["same_date"].isoformat())
    return dict(LG._blank(h), entry=(same or {}).get("entry"), outcome=None, reason="split",
                split_on=sp if isinstance(sp, str) else None,
                end_t=LG._iso_t(b["next_end"]), end_date=b["next_date"].isoformat())


def _guard(split: Optional[Callable], sym: str, d: date, end_d: date):
    """True / iso = a split on file in (d, end_d] · False = none · None = the check was not read (no lookup)."""
    if split is None:
        return None
    try:
        return split(sym, d, end_d)
    except Exception as exc:                                        # noqa: BLE001
        log.warning("split check %s %s→%s raised: %s", sym, d, end_d, type(exc).__name__)
        return None


def _bars(frames: dict, days: list) -> list:
    return LG._merge(*(LG.bars_from_frame(frames[x]) for x in days))


def _grade_event(ev: dict, d: date, sym: str, frames_of: Callable, split: Optional[Callable], cnt: dict) -> tuple:
    """-> (alert block, same | None, next | None, bars5). §3.13 steps 7–9."""
    at = datetime.strptime(ev["pass_t"], "%Y-%m-%d %H:%M").replace(tzinfo=ET).astimezone(UTC)
    trig, stop = _f(ev.get("trigger")), _f(ev.get("stop"))
    row = {"symbol": sym, "date": d.isoformat(), "at_utc": at, "trigger": trig, "stop": stop,
           "plan": LG.plan_of(trig, stop)[0]}
    b = LG.session_bounds(d, at)
    days = [d] + ([b["same_date"]] if b["same_date"] != d else []) + [b["next_date"]]
    frames = frames_of(sym, days)                                   # {day: frame} — present days only
    same_days = [x for x in days if x <= b["same_date"]]
    same = None
    if all(x in frames for x in same_days):
        if b["same_date"] != d:                                     # E1: an after-close alert grades on the next day
            sp0 = _guard(split, sym, d, b["same_date"])
            if sp0 is None:
                cnt["split_unread"] += 1
            elif sp0:
                same = _split_cell("same", sp0, b, None)
                cnt["split"] += 1
            else:
                same = LG.grade(row, _bars(frames, same_days), b, "same")
                cnt["same_graded"] += 1
        else:
            same = LG.grade(row, _bars(frames, same_days), b, "same")
            cnt["same_graded"] += 1
    else:
        cnt["same_not_cached"] += 1
    nxt = None
    if all(x in frames for x in days):
        sp = _guard(split, sym, d, b["next_date"])
        if sp is None:
            cnt["split_unread"] += 1
        elif sp:
            nxt = _split_cell("next", sp, b, same)
            cnt["split"] += 1
        else:
            nxt = LG.grade(row, _bars(frames, days), b, "next")
            cnt["next_graded"] += 1
    else:
        cnt["next_not_cached"] += 1
    bars = []
    if frames:
        f = pd.concat([frames[x] for x in days if x in frames]).sort_index()
        f = f[~f.index.duplicated(keep="last")]
        lo = datetime.combine(d, ET_PREMARKET_OPEN, tzinfo=ET).astimezone(UTC).replace(tzinfo=None)
        hi = b["next_end"].astimezone(UTC).replace(tzinfo=None)
        f = f[(f.index >= lo) & (f.index + ONE_MIN <= hi)]
        bars = TP.bars5(f)
    alert = {"date": d.isoformat(), "symbol": sym, "setup": ev["setup"], "entry_bar_t": ev.get("entry_bar_t"),
             "frame": ev.get("frame"), "trigger": trig, "stop": stop, "risk_pct": _f(ev.get("risk_pct")),
             "pass_t": ev.get("pass_t"), "q_t": ev.get("q_t"), "at": at.isoformat()}
    return alert, same, nxt, bars


def _csv_row(ev: dict, d: date, kept: bool, why: Optional[str], same, nxt, bars5_n) -> dict:
    out = {"date": d.isoformat(), "symbol": ev.get("symbol"), "setup": ev.get("setup"), "frame": ev.get("frame"),
           "entry_bar_t": ev.get("entry_bar_t"), "pass_t": ev.get("pass_t"), "trigger": _f(ev.get("trigger")),
           "stop": _f(ev.get("stop")), "risk_pct": _f(ev.get("risk_pct")), "kept": kept, "why_dropped": why,
           "bars5_n": bars5_n}
    for pre, g in (("same", same), ("next", nxt)):
        for k in GRADE_COLS:
            out[f"{pre}_{k}"] = (g or {}).get(k) if isinstance(g, dict) else None
    return out


def main(argv=None, *, now: Optional[datetime] = None, store=None, fetch_minutes: Optional[Callable] = None,
         split_lookup: Optional[Callable] = None) -> int:
    a = _parse(argv)
    now_et = (now or datetime.now(ET)).astimezone(ET)
    # 1. RTH — refused before anything is read (no override)
    if S.refused_window(now_et):
        print(f"refused: {now_et:%H:%M} ET is inside the regular session — the replay runs after 16:00 ET",
              file=sys.stderr)
        return 2
    # 2. a write names the detectors' commit
    if a.write and not (a.sha and SHA_RE.match(a.sha)):
        print("refused: --write needs --sha <7–40 hex git sha of the worktree>", file=sys.stderr)
        return 2
    # 3. the study cache, offline ALWAYS (read-only mount: offline never writes; no marker → the Cache would write one)
    if not (Path(a.cache) / S.CACHE_MARKER).is_file():
        print(f"refused: {a.cache} holds no study cache ({S.CACHE_MARKER} missing)", file=sys.stderr)
        return 2
    try:
        cache = S.Cache(a.cache, offline=True)
    except S.StaleCache as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    store = store if store is not None else ST.default()
    types, types_src = None, "none"
    if a.types == "store":
        try:
            types = (store.types_map() or {}).get("types") or None
            types_src = "store" if types else "store (empty)"
        except Exception as exc:                                    # noqa: BLE001
            log.warning("types_map raised: %s", type(exc).__name__)
            types, types_src = None, "store (unreadable)"
    split = split_lookup or (None if a.offline else LG._default_split_lookup(store))
    fetch = fetch_minutes or cache._fm
    only = {s.strip().upper() for s in a.symbols.split(",") if s.strip()} or None
    fetched: dict = {}                                              # {(SYM, day): frame | None} — ONE fetch, never written

    def extra_day(sym: str, day: date):
        got = cache.minutes(sym, day)
        if got is not None:                                         # a cached empty file is an answer: no prints
            return got if len(got) else None
        if a.offline:
            return None
        key = (sym, day)
        if key not in fetched:
            try:
                fetched[key] = fetch(sym, day)
            except Exception as exc:                                # noqa: BLE001 — one name never sinks the run
                log.warning("minutes fetch %s %s raised: %s", sym, day, type(exc).__name__)
                fetched[key] = None
            # a frame (an empty one = no prints, an answer) counts as fetched-unwritten; None (the HTTP loader's
            # failed / cut / no-key answer) or a raise counts as failed
            cache.stats["minutes_fetch_unwritten" if fetched[key] is not None else "minutes_fetch_failed"] += 1
        got = fetched[key]
        return got if got is not None and len(got) else None

    sessions: dict = {}
    csv_rows: list = []
    docs: list = []
    replayed_at = now_et.astimezone(UTC).isoformat()
    sha256 = _detectors_sha256()
    for d in a.sessions:
        why, prev, rows, prev_rows = _refusal(d, now_et, store, cache)
        if why is not None:
            sessions[d.isoformat()] = {"state": "refused", "why": why}
            continue
        cnt = _blank_session()
        unk: set = set()
        names = S.superset(rows, prev_rows, types, resolve=lambda s, _d=d: cache.ticker_type(s, _d), unknown=unk)
        cnt["superset"] = len(names)
        cnt["type_unknown_kept"] = len(unk)
        today_frames: dict = {}

        def frames_of(sym: str, days: list, _d=d, _tf=today_frames) -> dict:
            out = {}
            for x in days:
                f = _tf[sym] if x == _d else extra_day(sym, x)
                if f is not None and len(f):
                    out[x] = f
            return out

        for sym, prev_close in names:
            if only and sym not in only:
                continue
            raw_today = cache.minutes(sym, d)
            if raw_today is None or len(raw_today) == 0:
                cnt["no_bars"] += 1
                continue
            raw_prev = cache.minutes(sym, prev)
            try:
                res = S.study_symbol_day(sym, d, raw_prev, raw_today, prev_close, scope="live", with_pool=False,
                                         method="v2")
            except Exception as exc:                                # noqa: BLE001 — one name never sinks the run
                log.warning("study %s %s failed: %s", sym, d, type(exc).__name__)
                cnt["failed"] += 1
                continue
            if res.get("q_t") is None:
                continue
            cnt["listed"] += 1
            today_frames[sym] = raw_today
            for ev in res.get("events") or []:
                cnt["events"] += 1
                why_d = _why_dropped(ev, d)
                if why_d is not None:
                    cnt["dropped"][why_d] += 1
                    csv_rows.append(_csv_row(ev, d, False, why_d, None, None, None))
                    continue
                c2 = Counter()
                try:
                    alert, same, nxt, bars = _grade_event(ev, d, sym, frames_of, split, c2)
                except Exception as exc:                            # noqa: BLE001
                    log.warning("grading %s %s %s failed: %s", sym, d, ev.get("setup"), type(exc).__name__)
                    cnt["failed"] += 1
                    continue
                for k, v in c2.items():
                    cnt[k] += v
                cnt["kept"] += 1
                csv_rows.append(_csv_row(ev, d, True, None, same, nxt, len(bars)))
                docs.append({"_id": LG.replay_id(d.isoformat(), sym, ev["setup"]), "date": d.isoformat(),
                             "symbol": sym.upper(), "setup": ev["setup"], "kind": LG.KINDS[1],
                             "state": LG.REPLAY_STATE, "alert": alert, "same": same, "next": nxt, "bars5": bars,
                             "universe": UNIVERSE, "float_gate": False, "detectors_sha": a.sha,
                             "detectors_sha256": sha256, "replayed_at": replayed_at,
                             "caveats": list(LG.REPLAY_CAVEATS)})
        sessions[d.isoformat()] = cnt
    written = 0
    if a.write:
        for doc in docs:
            written += bool(store.upsert_replay(doc))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "events.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(EVENT_COLS))
        w.writeheader()
        for r in csv_rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in EVENT_COLS})
    summary = {"argv": list(argv) if argv is not None else sys.argv[1:], "run_at": now_et.isoformat(),
               "detectors_sha": a.sha, "detectors_sha256": sha256, "types": types_src,
               "sessions": sessions, "written": written, "caveats": list(LG.REPLAY_CAVEATS),
               "cache_stats": dict(cache.stats)}
    (out / "replay.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=str) + "\n")
    print(json.dumps({"sessions": {k: {kk: v.get(kk) for kk in ("state", "why", "kept")} for k, v in sessions.items()},
                      "written": written}, ensure_ascii=False, default=str))
    return 0 if any(v.get("state") == "replayed" for v in sessions.values()) else 3


if __name__ == "__main__":
    sys.exit(main())
