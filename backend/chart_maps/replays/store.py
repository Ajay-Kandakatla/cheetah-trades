"""🎬 Replays — the listing engine (replays spec §3.1, WP-BE, 2026-11-17). Pure disk: no Mongo, no network, no write.

Ajay 2026-11-17, verbatim: "Can you store the videos in to the app please". The host folder
`eod-audits/replays/` is bind-mounted READ-ONLY at `ROOT_DEFAULT` (or `$REPLAYS_DIR`): `videos/<YYYY-MM-DD>/<name>.mp4`
+ its sidecar `<name>.json`, and `rs_potentials/ledger.csv`.

ACCEPT RULE per `.json` in a day folder (his 11-16 rule decides the window):
  body is a dict · `window == FULL_DAY_WINDOW` (else `skipped_window`) · `file` is a str matching `FILE_RE`, equal to
  the json's stem + ".mp4", and that `.mp4` is present in the SAME scandir (a render in flight is `<name>.part.mp4`
  with its sidecar already written → not yet listed). Anything else → `skipped_bad`. Every `.mp4` with no accepted
  sidecar → `no_sidecar`, EXCEPT the mp4 paired (by stem) with a window-skipped sidecar: it HAS a sidecar, counted once
  as `skipped_window` (2026-11-17 refix: 11-13 read no_sidecar 10 when only 1 mp4 truly lacked one). Each accepted sidecar becomes its card inside `try … except CARD_ERRORS` — one malformed
  sidecar drops ONE card (`skipped_bad`), never the listing.

GROUPS (`group_of`, in this order): 🎾 plan word or an `rs` list → rs_potentials; `why[0]` starting with the pipeline's
own "biggest mover of" → biggest_mover; `|aplus` + grade W/L → aplus_winners / aplus_losers (a carried after-close
ring too, 2026-11-18); else other. A reel of an EXCLUDED_PAGES page (🚩 1-minute, retired 2026-11-18) → skipped_page.

CACHE: per (root, day) under a lock, keyed by ONE scandir — (dir mtime_ns, n_json, max json mtime_ns, n_mp4); the
jsons are re-parsed only when the key moves (an in-place sidecar rewrite moves the max json mtime). UNMEASURED.
"""
from __future__ import annotations

import csv
import json
import math as _math
import os
import threading
from datetime import date as _date
from pathlib import Path
from typing import Optional

from growth.api import _scrub

from . import constants as C

_LOCK = threading.Lock()
_DAY_CACHE: dict = {}          # (root str, day) -> (key, listing)
_LEDGER_CACHE: dict = {}       # ledger path str -> ((mtime_ns, size), rows, error)


def root_dir(root=None) -> Path:
    if root is not None:
        return Path(root)
    return Path(os.environ.get(C.ROOT_ENV) or C.ROOT_DEFAULT)


def is_date(day) -> bool:
    return isinstance(day, str) and C.DATE_RE.fullmatch(day) is not None


def _is_file_name(name) -> bool:
    return isinstance(name, str) and C.FILE_RE.fullmatch(name) is not None


def _scan(d: Path):
    """ONE scandir → (key, names) or (None, None) when the folder is missing."""
    try:
        dir_mtime = os.stat(d).st_mtime_ns
        n_json = n_mp4 = 0
        max_json = 0
        names = []
        with os.scandir(d) as it:
            for e in it:
                names.append(e.name)
                if e.name.endswith(".json"):
                    n_json += 1
                    try:
                        max_json = max(max_json, e.stat(follow_symlinks=False).st_mtime_ns)
                    except OSError:
                        pass
                elif e.name.endswith(".mp4"):
                    n_mp4 += 1
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return None, None
    return (dir_mtime, n_json, max_json, n_mp4), names


def folder_key(d) -> Optional[tuple]:
    return _scan(Path(d))[0]


def _read_sidecar(p: Path):
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def group_of(side: dict, day: str) -> str:
    if side.get("plan_word") == C.RS_WORD or isinstance(side.get("rs"), list):
        return "rs_potentials"
    if str(side["why"][0]).startswith(C.MOVER_WHY_PREFIX):
        return "biggest_mover"
    ring_id = side["ring_id"]
    if ring_id.endswith(C.APLUS_SUFFIX):                  # a carried after-close A+ files by its grade too (2026-11-18)
        grade = side.get("grade")
        if isinstance(grade, str) and grade.startswith("W"):
            return "aplus_winners"
        if isinstance(grade, str) and grade.startswith("L"):
            return "aplus_losers"
    return "other"


def _potential(side: dict):
    p = side.get("potential")
    if p is None:
        return None
    page, setup = p.get("page"), p.get("setup")
    return {"first_stored_et": p.get("first_stored_et"), "trigger": p.get("trigger"), "stop": p.get("stop"),
            "page_text": C.PAGE_WORDS.get(page, page), "setup_text": C.SETUP_TEXT.get(setup, setup)}


def video_payload(side: dict, day: str) -> dict:
    """The served card. Raises one of CARD_ERRORS on a malformed sidecar (the caller counts it skipped_bad)."""
    why = side["why"]
    if not isinstance(why, list) or not why:
        raise ValueError("why must be a non-empty list")
    if not all(isinstance(w, str) for w in why):
        raise TypeError("why lines must be strings")
    file = side["file"]
    ring_id = side["ring_id"]
    ring_day = ring_id.split("|")[0]
    speed, minutes = side["speed"], side["minutes"]
    setup, page = side.get("setup"), side.get("page")
    group = group_of(side, day)
    return {
        "file": file, "src": f"{C.API_PATH}/video/{day}/{file}",
        "symbol": side.get("symbol"),
        "setup": setup, "setup_text": C.SETUP_TEXT.get(setup, setup),
        "page": page, "page_text": C.PAGE_WORDS.get(page, page),
        "grade": side.get("grade"), "why": list(why), "story": side.get("story"),
        "ring_id": ring_id, "ring_day": ring_day, "carried": ring_day != day,
        "speed": speed, "speed_text": f"{speed:g}x",
        "minutes": minutes, "length_text": f"{minutes:.0f} min",
        "move_pct": side.get("move_pct"), "move_base": side.get("move_base"), "trig_pct": side.get("trig_pct"),
        "fill_px": side.get("fill_px"), "no_risk": side.get("no_risk"), "window": side.get("window"),
        "plan_word": side.get("plan_word"), "potential": _potential(side),
        "group": group,
    }


def _empty_counts() -> dict:
    return {"videos": 0, "skipped_window": 0, "no_sidecar": 0, "skipped_bad": 0, "skipped_page": 0}


def _parse_day(d: Path, day: str, names) -> dict:
    present = set(names)
    counts = _empty_counts()
    videos, files, window_skipped = [], set(), set()
    for name in sorted(names):
        if not name.endswith(".json"):
            continue
        try:
            body = _read_sidecar(d / name)
        except (OSError, ValueError, UnicodeDecodeError):
            counts["skipped_bad"] += 1
            continue
        if not isinstance(body, dict):
            counts["skipped_bad"] += 1
            continue
        if body.get("window") != C.FULL_DAY_WINDOW:
            counts["skipped_window"] += 1
            wf = body.get("file")
            if _is_file_name(wf) and wf == name[: -len(".json")] + ".mp4":
                window_skipped.add(wf)
            continue
        f = body.get("file")
        if not _is_file_name(f) or f != name[: -len(".json")] + ".mp4" or f not in present:
            counts["skipped_bad"] += 1
            continue
        if body.get("page") in C.EXCLUDED_PAGES:             # 🚩 1-minute page retired 2026-11-18 — has a sidecar, never listed
            counts["skipped_page"] += 1
            window_skipped.add(f)
            continue
        try:
            card = video_payload(body, day)
        except C.CARD_ERRORS:
            counts["skipped_bad"] += 1
            continue
        videos.append(card)
        files.add(f)
    counts["no_sidecar"] = sum(1 for n in names if n.endswith(".mp4") and n not in files and n not in window_skipped)
    counts["videos"] = len(videos)
    return {"date": day, "videos": videos, "files": frozenset(files), "counts": counts}


def _empty_listing(day) -> dict:
    return {"date": day, "videos": [], "files": frozenset(), "counts": _empty_counts()}


def read_day(day: str, root=None) -> dict:
    r = root_dir(root)
    ck = (str(r), day)
    if not is_date(day):
        return _empty_listing(day)
    d = r / C.VIDEOS_SUB / day
    key, names = _scan(d)
    with _LOCK:
        if key is None:
            _DAY_CACHE.pop(ck, None)
            return _empty_listing(day)
        hit = _DAY_CACHE.get(ck)
        if hit is not None and hit[0] == key:
            return hit[1]
    listing = _parse_day(d, day, names)
    with _LOCK:
        _DAY_CACHE[ck] = (key, listing)
    return listing


def dates(root=None) -> list:
    r = root_dir(root)
    out = []
    try:
        with os.scandir(r / C.VIDEOS_SUB) as it:
            cands = [e.name for e in it if is_date(e.name) and e.is_dir(follow_symlinks=False)]
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []
    for day in cands:
        if read_day(day, r)["videos"]:
            out.append(day)
    return sorted(out, reverse=True)


def _ledger_all(root=None):
    """(rows, error) for the whole ledger; cached by (mtime_ns, size). Every cell stays a str."""
    p = root_dir(root) / C.RS_SUB / C.LEDGER_FILE
    try:
        st = os.stat(p)
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        with _LOCK:
            _LEDGER_CACHE.pop(str(p), None)
        return [], False
    key = (st.st_mtime_ns, st.st_size)
    with _LOCK:
        hit = _LEDGER_CACHE.get(str(p))
        if hit is not None and hit[0] == key:
            return hit[1], hit[2]
    try:
        with open(p, "r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f, strict=True))
        err = False
    except (csv.Error, OSError, UnicodeDecodeError):
        rows, err = [], True
    with _LOCK:
        _LEDGER_CACHE[str(p)] = (key, rows, err)
    return rows, err


def _cell(key: str, v) -> str:
    if not isinstance(v, str) or v == "":
        return C.RS_EMPTY_CELL
    if key == "page":
        return C.PAGE_WORDS.get(v, v)
    return v


def ledger_read(day: str, root=None):
    rows, err = _ledger_all(root)
    out = [{"cells": {k: _cell(k, row.get(k)) for k, _ in C.RS_COLUMNS}} for row in rows
           if row.get("date") == day and row.get("page") not in C.EXCLUDED_PAGES]
    return out, err


def ledger_rows(day: str, root=None) -> list:
    return ledger_read(day, root)[0]


def _num_desc(v):
    ok = isinstance(v, (int, float)) and not isinstance(v, bool) and v == v
    return (0, -v) if ok else (1, 0)


def _order(group: str, videos: list) -> list:
    if group == "rs_potentials":
        def k(v):
            fs = (v.get("potential") or {}).get("first_stored_et")
            return (0 if isinstance(fs, str) else 1, fs if isinstance(fs, str) else "", str(v.get("symbol") or ""))
    else:
        def k(v):
            return (_num_desc(v.get("move_pct")), str(v.get("symbol") or ""), str(v.get("page") or ""))
    return sorted(videos, key=k)


def _rs_block(day, root) -> tuple:
    rows, err = ledger_read(day, root) if day else ([], False)
    return ({"title": C.RS_TITLE, "note": C.RS_NOTE,
             "columns": [{"key": k, "label": l} for k, l in C.RS_COLUMNS],
             "rows": rows, "text": None if rows else C.RS_EMPTY_TEXT}, err)


def payload(day: Optional[str] = None, root=None) -> dict:
    r = root_dir(root)
    base = {"title": C.TITLE, "tab": C.TAB}
    if not (r / C.VIDEOS_SUB).is_dir():
        return _scrub({**base, "state": "no_folder", "text": C.NO_FOLDER_TEXT, "dates": [], "date": None})
    ds = dates(r)
    date = day if is_date(day) else (ds[0] if ds else None)   # an asked, well-formed day is kept (URL stays truthful)
    listing = read_day(date, r) if date else _empty_listing(None)
    counts = dict(listing["counts"])
    rs, err = _rs_block(date, r)
    if err:
        counts["ledger_error"] = True
    common = {**base, "date": date, "dates": ds, "window": C.FULL_DAY_WINDOW, "window_note": C.WINDOW_NOTE,
              "counts": counts, "rs": rs}
    if not listing["videos"]:
        return _scrub({**common, "state": "empty", "text": C.EMPTY_DAY_TEXT, "groups": []})
    groups = []
    for key, label in C.GROUPS:
        vids = [v for v in listing["videos"] if v["group"] == key]
        if vids:
            groups.append({"key": key, "label": label, "videos": _order(key, vids)})
    groups = _tag_day_groups(groups, date, r)                # 🏆 past-winner tag (2026-11-22): additive key only
    return _scrub({**common, "state": "ready", "groups": groups})


def resolve_video(day: str, name: str, root=None) -> Optional[Path]:
    """The listed file's path, or None (→ 404). Only a name the listing accepted, only inside root/videos."""
    if not is_date(day) or not _is_file_name(name):
        return None
    r = root_dir(root)
    if name not in read_day(day, r)["files"]:
        return None
    p = r / C.VIDEOS_SUB / day / name
    base = os.path.realpath(r / C.VIDEOS_SUB) + os.sep
    real = os.path.realpath(p)
    if not real.startswith(base) or not os.path.isfile(real):
        return None
    return p


# ── 🏆 Past winners (spec pastwinners §3.5, WP-APP, 2026-11-18) ───────────────────────────────────────────────────────
# Ajay 2026-11-18 ~21:45 ET, verbatim: "can you work on todays videos and also..  Winners in general from the past".
# `videos/winners/` (single-day winner reels) and `videos/multiday/` (multi-day runner reels) — NON-recursive (the
# multiday `phone/` copies are never listed). The accept rule is `_parse_day`'s with `winner_window_ok` deciding the
# window; the kind comes from the FOLDER (C.WINNER_SUBS), never from sidecar text. The card is composed from constants +
# sidecar NUMBERS only: `gain_pct` (HIGH-based in the multiday sidecars), `label`, `ask`, `why`, `category`, `forced`
# TEXT are never served. Descriptive, UNMEASURED, not a signal. The day listing above is untouched (a golden pins it).
_WIN_CACHE: dict = {}          # (root str, sub) -> (key, listing)
_SUB_KIND = {s: (k, t) for s, k, t in C.WINNER_SUBS}


def winner_window_ok(sub: str, window) -> bool:
    kind = _SUB_KIND.get(sub, (None, None))[0]
    if kind == "single_day":
        return window == C.FULL_DAY_WINDOW
    if kind == "multi_day":
        return isinstance(window, str) and window.startswith(C.MULTI_WINDOW_PREFIX)
    return False


def _signed_pct(x) -> str:
    return f"{x:+.0f}%".replace("-", "−")


def _finite(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and _math.isfinite(x)


def _day_str(x) -> str:
    if not is_date(x):
        raise ValueError("not a YYYY-MM-DD day")
    return x


_NO_SETUP = {"setup": None, "setup_text": None, "setup_class": None, "setup_class_text": None, "setup_chips": [],
             "setup_chips_text": [], "stopped_before_peak": False, "stopped_text": None}
_NO_TIMING = {"timing": None, "timing_text": None}


def _setup_fields(lab) -> tuple:
    """The labeller's `setups` dict → (served fields, bad). Absent (None / missing) → no label, not bad. Anything the
    house does not know (a setup key, a class, a primary/class mix, a non-bool flag) → no label, bad=1 (skipped_label)."""
    if lab is None:
        return _NO_SETUP, 0
    if not isinstance(lab, dict):
        return _NO_SETUP, 1
    prim, cls, chips, stopped = lab.get("primary"), lab.get("class"), lab.get("chips", []), lab.get("stopped_before_peak", False)
    if prim is not None and prim not in C.WIN_SETUP_ORDER:
        return _NO_SETUP, 1
    if not isinstance(cls, str) or cls not in C.WIN_CLASS_WORDS:
        return _NO_SETUP, 1
    if (prim is None) != (cls in C.WIN_CLASSES_NO_SETUP):     # a 🎾 primary on a float-gated reel never counts as 🎾
        return _NO_SETUP, 1
    if not isinstance(chips, list) or not all(isinstance(c, str) and c in C.WIN_SETUP_ORDER for c in chips):
        return _NO_SETUP, 1
    if prim is None and chips:                                # a no-setup class carries no chip (never a 🎾 count)
        return _NO_SETUP, 1
    if not isinstance(stopped, bool):
        return _NO_SETUP, 1
    if prim is None and stopped:                              # review fix (c): no read → nothing to be stopped
        return _NO_SETUP, 1
    key = prim if prim is not None else C.WIN_SETUP_NONE
    served_chips = [c for c in C.WIN_SETUP_ORDER if c in chips]
    return {"setup": key, "setup_text": C.WIN_SETUP_WORDS[key], "setup_class": cls,
            "setup_class_text": C.WIN_CLASS_WORDS[cls], "setup_chips": served_chips,
            "setup_chips_text": [C.WIN_CHIP_WORDS.format(words=C.WIN_SETUP_WORDS[c]) for c in served_chips if c != prim],
            "stopped_before_peak": stopped, "stopped_text": C.WIN_STOPPED_WORDS if stopped else None}, 0


def bucket_of(peak_t) -> Optional[str]:
    """The labeller's bucket rule (C.WIN_TIMING_BUCKETS == label_winners.TIMING_BUCKETS): lower bound inclusive, upper
    exclusive; None outside 09:30–20:00. Here it CHECKS a served bucket; 👀 Watch's 📅 read (gajjala_watch.runners,
    2026-11-22) ASSIGNS one with it — the peak bar's start — so both surfaces share this one rule."""
    for name, lo, hi in C.WIN_TIMING_BUCKETS:
        if lo <= peak_t < hi:
            return name
    return None


def _timing_fields(lab) -> tuple:
    """The labeller's `timing` dict → (served fields, bad). Absent, or a labelled `bucket: null` (no 09:30–20:00 bars) →
    no timing (sorted LAST), not bad. An unknown bucket or a bucket without an HH:MM peak minute → no timing, bad=1."""
    if lab is None:
        return _NO_TIMING, 0
    if not isinstance(lab, dict):
        return _NO_TIMING, 1
    b, t = lab.get("bucket"), lab.get("peak_t")
    if b is None:
        return _NO_TIMING, 0
    if not isinstance(b, str) or b not in C.WIN_TIMING_WORDS or not isinstance(t, str) or not C.HHMM_RE.fullmatch(t):
        return _NO_TIMING, 1
    if bucket_of(t) != b:                                     # review fix (c): the bucket must agree with its peak minute
        return _NO_TIMING, 1
    return {"timing": b, "timing_text": C.WIN_TIMING_TEXT.format(words=C.WIN_TIMING_WORDS[b], t=t)}, 0


def winner_labels(side: dict, kind: str) -> tuple:
    """(served setup + timing fields, n bad labels). Single-day reels only (the labeller writes no multi-day label)."""
    if kind != "single_day":
        s, t, bad = _NO_SETUP, _NO_TIMING, 0
    else:
        s, bs = _setup_fields(side.get("setups"))
        t, bt = _timing_fields(side.get("timing"))
        bad = bs + bt
    return {**s, "setup_chips": list(s["setup_chips"]), "setup_chips_text": list(s["setup_chips_text"]), **t}, bad


# ── 🏆 chip → jump to that win's replay at its peak (2026-11-22) ───────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "New feature when I click on this past winner tag take me to that video so change the date
# and focus me on that video at that. time". The clock → video-second mapping is the renderer's own schedule
# (eod-audits/replays/replay_multiday.py Plan.times + render): frame j shows clock 04:00 + (j + 1) * speed / fps, a
# minute is drawn once the frame clock is PAST its start (bisect_left), the only extra frames are the END hold. Served
# second = the MIDDLE of the first frame inside the labelled peak minute. Bounded arithmetic only (never a `while`);
# every arithmetic raise is caught here (C.CARD_ERRORS is not widened). Navigation only — UNMEASURED.
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _seek_step(speed, fps) -> Optional[float]:
    """Clock seconds per frame (speed / fps), or None: speed finite > 0, fps an int > 0 (bool refused), the step finite > 0.
    May raise OverflowError on an absurd int — callers catch ArithmeticError."""
    if not _finite(speed) or speed <= 0 or not _is_int(fps) or fps <= 0:
        return None
    step = speed / fps
    if not _finite(step) or step <= 0:
        return None
    return step


def session_frames(speed, fps) -> Optional[int]:
    """Frames of ONE 04:00→20:00 session in the renderer's schedule (replay_multiday.Plan.times): n = int(S // step),
    +1 (the frame at t1) only when n * step < S - C.SEEK_EPS. None on any bad input. NEVER raises."""
    try:
        step = _seek_step(speed, fps)
        if step is None:
            return None
        n = int(C.SEEK_SESSION_SEC // step)
        return n + (1 if n * step < C.SEEK_SESSION_SEC - C.SEEK_EPS else 0)
    except (ArithmeticError,) + C.CARD_ERRORS:
        return None


def _seek_frame(c, step) -> Optional[int]:
    """The FIRST frame whose clock (n + 1) * step is PAST second c of the session — the renderer's own rule
    (bisect_left: a minute is drawn once the frame clock is past its start). None when the bracket cannot be proved."""
    n = int(c // step)                                   # float floor-division can sit one frame early (36x / 10 fps: 09:30 → 5499, not 5500)
    for _ in range(2):
        if (n + 1) * step <= c + C.SEEK_EPS:
            n += 1
    for _ in range(2):
        if n > 0 and n * step > c + C.SEEK_EPS:
            n -= 1
    return n if n * step <= c + C.SEEK_EPS < (n + 1) * step else None


def _hhmm_min(t: str) -> int:
    return int(t[:2]) * 60 + int(t[3:])


def seek_seconds(side: dict, kind: str) -> Optional[float]:
    """Clock → video second of the reel's labelled PEAK MINUTE, or None. Never a guessed time. NEVER raises."""
    try:
        if kind != "single_day":
            return None
        if _timing_fields(side.get("timing"))[0]["timing"] is None:
            return None
        if side.get("window") != C.FULL_DAY_WINDOW:
            return None
        speed, fps, frames, days = side.get("speed"), side.get("fps"), side.get("frames"), side.get("days")
        step = _seek_step(speed, fps)
        if step is None or not _is_int(frames) or frames <= 0 or not isinstance(days, list) or len(days) != 1:
            return None
        per = session_frames(speed, fps)
        if per is None:
            return None
        hold = max(1, int(round(C.SEEK_HOLD_SEC * fps)))
        if frames != per + hold:
            return None
        c = (_hhmm_min(side["timing"]["peak_t"]) - _hhmm_min(C.WINDOW_T0)) * 60
        if not 0 <= c < C.SEEK_SESSION_SEC:
            return None
        n = _seek_frame(c, step)
        if n is None or n >= per:
            return None
        return round((n + 0.5) / fps, 3)
    except (ArithmeticError,) + C.CARD_ERRORS:
        return None


def winner_card(side: dict, sub: str, tally: Optional[dict] = None) -> dict:
    """The served 🏆 card. Raises one of CARD_ERRORS on a malformed sidecar (the caller counts it skipped_bad). A bad
    setup / timing LABEL never drops the card: it is served unlabelled and counted in `tally["skipped_label"]`."""
    kind, kind_text = _SUB_KIND[sub]
    file = side["file"]
    symbol = side["symbol"]
    if not isinstance(symbol, str) or not symbol:
        raise ValueError("symbol must be a non-empty str")
    day = _day_str(side["day"])
    days = side["days"]
    if not isinstance(days, list) or not days:
        raise ValueError("days must be a non-empty list")
    days = [_day_str(d) for d in days]
    speed, minutes = side["speed"], side["minutes"]
    if not _finite(speed) or not _finite(minutes):
        raise TypeError("speed / minutes must be finite numbers")
    cg = side["close_gain_pct"]
    if not _finite(cg):
        raise TypeError("close_gain_pct must be a finite number")
    spike = side["spike_print"]
    if not isinstance(spike, bool):
        raise TypeError("spike_print must be a bool")
    spike_text = None
    if spike:
        sx = side.get("spike_x")
        if not _finite(sx) or sx <= 0:
            raise ValueError("spike_x must be a finite number > 0 when spike_print is true")
        spike_text = C.SPIKE_WORDS.format(x=sx)
    pick_text = None
    if kind == "single_day":
        pick = side.get("pick")
        if pick not in C.WINNER_PICKS:
            raise ValueError("pick must be one of WINNER_PICKS")
        if pick == "today_top":
            n = side.get("today_n")
            if not isinstance(n, int) or isinstance(n, bool) or n <= 0:
                raise ValueError("today_n must be a positive int on a today_top reel")
            pick_text = C.TODAY_TOP_WORDS.format(n=n, pct=C.GC.SA_BIG_RUNNER_PCT)
    else:
        forced = side.get("forced")
        if forced is True or (isinstance(forced, str) and forced.strip()):
            pick_text = C.FORCED_WORDS.format(pct=C.GC.SA_BIG_RUNNER_PCT)
    hp = side.get("high_pct")
    high_pct = hp if _finite(hp) else None
    d0 = _date.fromisoformat(day)
    days_text = day if kind == "single_day" else f"{days[0]} → {days[-1]} · {len(days)} sessions"
    labels, bad = winner_labels(side, kind)
    if tally is not None:
        tally["skipped_label"] = tally.get("skipped_label", 0) + bad
    seek = seek_seconds(side, kind)                         # 🏆 jump (2026-11-22): the peak minute's video second, or None
    return {
        "file": file, "sub": sub, "src": f"{C.WINNERS_API_PATH}/video/{sub}/{file}",
        "symbol": symbol, "kind": kind, "kind_text": kind_text,
        "date": day, "label_date": f"{d0:%a %Y-%m-%d}",
        "days": days, "days_text": days_text,
        "close_gain_pct": cg, "gain_text": f"{_signed_pct(cg)} {C.GAIN_WORDS[kind]}",
        "high_pct": high_pct,
        "high_text": f"{_signed_pct(high_pct)} {C.HIGH_WORDS[kind]}" if high_pct is not None else None,
        "spike_print": spike, "spike_text": spike_text, "pick_text": pick_text,
        "speed": speed, "speed_text": f"{speed:g}x",
        "minutes": minutes, "length_text": f"{minutes:.0f} min",
        **labels,
        "seek_s": seek,
        "seek_text": C.SEEK_WORDS.format(t=side["timing"]["peak_t"]) if seek is not None else C.SEEK_NONE_WORDS,
    }


def _empty_win_counts() -> dict:
    return {"videos": 0, "skipped_window": 0, "skipped_bad": 0, "no_sidecar": 0, "skipped_label": 0}


def _parse_winner_sub(d: Path, sub: str, names) -> dict:
    present = set(names)
    counts = _empty_win_counts()
    videos, files, window_skipped = [], set(), set()
    for name in sorted(names):
        if not name.endswith(".json") or name in C.NON_SIDECAR_JSON:
            continue
        try:
            body = _read_sidecar(d / name)
        except (OSError, ValueError, UnicodeDecodeError):
            counts["skipped_bad"] += 1
            continue
        if not isinstance(body, dict):
            counts["skipped_bad"] += 1
            continue
        if not winner_window_ok(sub, body.get("window")):
            counts["skipped_window"] += 1
            wf = body.get("file")
            if _is_file_name(wf) and wf == name[: -len(".json")] + ".mp4":
                window_skipped.add(wf)
            continue
        f = body.get("file")
        if not _is_file_name(f) or f != name[: -len(".json")] + ".mp4" or f not in present:
            counts["skipped_bad"] += 1
            continue
        tally = {"skipped_label": 0}
        try:
            card = winner_card(body, sub, tally)
        except C.CARD_ERRORS:
            counts["skipped_bad"] += 1
            continue
        counts["skipped_label"] += tally["skipped_label"]
        videos.append(card)
        files.add(f)
    counts["no_sidecar"] = sum(1 for n in names if n.endswith(".mp4") and n not in files and n not in window_skipped)
    counts["videos"] = len(videos)
    return {"sub": sub, "videos": videos, "files": frozenset(files), "counts": counts}


def _empty_sub(sub) -> dict:
    return {"sub": sub, "videos": [], "files": frozenset(), "counts": _empty_win_counts()}


def read_winner_sub(sub: str, root=None) -> dict:
    if sub not in C.WINNER_SUB_KEYS:
        return _empty_sub(sub)
    r = root_dir(root)
    ck = (str(r), sub)
    d = r / C.VIDEOS_SUB / sub
    key, names = _scan(d)
    with _LOCK:
        if key is None:
            _WIN_CACHE.pop(ck, None)
            return _empty_sub(sub)
        hit = _WIN_CACHE.get(ck)
        if hit is not None and hit[0] == key:
            return hit[1]
    listing = _parse_winner_sub(d, sub, names)
    with _LOCK:
        _WIN_CACHE[ck] = (key, listing)
    return listing


def winners_payload(root=None) -> dict:
    r = root_dir(root)
    counts = {"videos": 0, "single_day": 0, "multi_day": 0, "skipped_window": 0, "skipped_bad": 0, "no_sidecar": 0,
              "skipped_label": 0}
    base = {"title": C.WINNERS_TITLE, "tab": C.TAB, "note": C.WINNERS_NOTE, "window": C.FULL_DAY_WINDOW,
            "window_note": C.WINNERS_WINDOW_NOTE, "jump_missing_text": C.JUMP_MISSING_WORDS}   # 🏆 jump (2026-11-22)
    if not (r / C.VIDEOS_SUB).is_dir():
        return _scrub({**base, "state": "no_folder", "text": C.NO_FOLDER_TEXT, "summary_text": None,
                       "counts": counts, "setups": setup_filter([]), "rows": []})
    videos = []
    for sub, kind, _t in C.WINNER_SUBS:
        lst = read_winner_sub(sub, r)
        videos.extend(lst["videos"])
        counts[kind] += len(lst["videos"])
        for k in ("skipped_window", "skipped_bad", "no_sidecar", "skipped_label"):
            counts[k] += lst["counts"][k]
    counts["videos"] = len(videos)
    summary = f"{counts['videos']} videos · {counts['single_day']} single-day · {counts['multi_day']} multi-day"
    if not videos:
        return _scrub({**base, "state": "empty", "text": C.WINNERS_EMPTY_TEXT, "summary_text": summary,
                       "counts": counts, "setups": setup_filter([]), "rows": []})
    idx = past_winner_index(videos)                         # 🏆 "won before" (2026-11-22): EARLIER wins, same symbol
    tagged = []
    for v in videos:
        tag = past_wins_before(idx, v["symbol"], v["days"][0], C.PAST_WIN_BEFORE_WORDS)
        tagged.append({**v, **tag} if tag else v)
    rows = winner_rows(tagged, idx)
    return _scrub({**base, "state": "ready", "text": None, "summary_text": summary, "counts": counts,
                   "setups": setup_filter(rows), "rows": rows})


def _timing_rank(t) -> int:
    return C.WIN_TIMING_ORDER.index(t) if t in C.WIN_TIMING_ORDER else len(C.WIN_TIMING_ORDER)


def _date_desc(day: str) -> int:
    return -_date.fromisoformat(day).toordinal()


def card_filter_keys(v) -> set:
    """The setup filter keys a served card passes: its served `setup` (a primary, or "none") plus a 🎾 SECONDARY chip
    (C.WIN_CHIP_MATCH, review fix (a)). An unlabelled card or a multi-day reel passes none (only 'All')."""
    keys = set()
    if v.get("setup") in C.WIN_SETUP_FILTER_KEYS:
        keys.add(v["setup"])
    keys.update(c for c in (v.get("setup_chips") or ()) if c in C.WIN_CHIP_MATCH)
    return keys


def _reel_order(v) -> tuple:
    """Inside a row: newest first by the reel's LAST session; a same-day tie → the multi-day run first, then the higher
    close gain, then sub / file."""
    return (_date_desc(v["days"][-1]), 0 if v["kind"] == "multi_day" else 1, _num_desc(v["close_gain_pct"]),
            v["sub"], v["file"])


def winner_rows(cards: list, index: Optional[dict] = None) -> list:
    """2026-11-22 (Ajay: "when ever a stock has multiday group it in the same role for past winners" · "CLRO another
    example add all the videos may be click them together"): ONE row per symbol (exact) holding every accepted reel of
    that symbol, newest first. `wins` = the past-winner index's one-per-run count (a multi-day run absorbs the single-day
    reels on its days; a later separate single day is another win). Row order: the newest single-day reel's timing
    (eod → intraday → first_hour → unknown; a row with no single-day reel → unknown — the labeller writes no multi-day
    timing), then the newest win's day desc, then the best close gain desc, then the symbol. Pure; the FE never reorders."""
    idx = index if index is not None else past_winner_index(cards)
    by_sym: dict = {}
    for v in cards:
        by_sym.setdefault(v["symbol"], []).append(v)
    rows = []
    for sym, vids in by_sym.items():
        vids = sorted(vids, key=_reel_order)
        wins = _one_per_run(idx.get(sym, []))
        singles = [v for v in vids if v["kind"] == "single_day"]
        newest_single = min(singles, key=lambda v: (_date_desc(v["date"]), _num_desc(v["close_gain_pct"]), v["file"]),
                            default=None)
        timing = newest_single.get("timing") if newest_single else None
        timing_text = newest_single.get("timing_text") if newest_single else None
        keys = set().union(*(card_filter_keys(v) for v in vids))
        filter_keys = [k for k in C.WIN_SETUP_FILTER_KEYS if k in keys]
        best = filter_keys[0] if filter_keys else None
        newest = wins[0]["day"] if wins else vids[0]["days"][-1]
        best_cg = max((v["close_gain_pct"] for v in vids if _finite(v["close_gain_pct"])), default=None)
        n = len(wins)
        rows.append({
            "key": f"sym-{sym}", "symbol": sym,
            "wins": n, "wins_text": C.WIN_ROW_WINS_WORDS[0 if n == 1 else 1].format(n=n),
            "newest_date": newest, "newest_text": C.WIN_ROW_NEWEST_WORDS.format(d=f"{_date.fromisoformat(newest):%a %Y-%m-%d}"),
            "setup": best, "setup_text": C.WIN_SETUP_WORDS[best] if best else None,
            "timing": timing if timing in C.WIN_TIMING_ORDER else None,
            "timing_text": timing_text if timing in C.WIN_TIMING_ORDER else None,
            "best_close_gain_pct": best_cg, "filter_keys": filter_keys, "videos": vids,
        })
    rows.sort(key=lambda r: (_timing_rank(r["timing"]), _date_desc(r["newest_date"]),
                             _num_desc(r["best_close_gain_pct"]), r["symbol"]))
    return rows


def setup_filter(rows: list) -> list:
    """The served 🏆 filter row over the ROWS (2026-11-22): 'All' (every row), then 🎾 first and the ask's setup order,
    then 'no Gajjala setup'. A count = the rows with at least one reel passing that key (`filter_keys`) — a 🎾 float-gated
    reel is a 'none' and carries no chip, so it never makes a 🎾 count."""
    out = [{"key": C.WIN_SETUP_ALL, "label": C.WIN_SETUP_ALL_WORDS, "count": len(rows)}]
    for k in C.WIN_SETUP_FILTER_KEYS:
        out.append({"key": k, "label": C.WIN_SETUP_WORDS[k],
                    "count": sum(1 for r in rows if k in (r.get("filter_keys") or ()))})
    return out


# ── 🏆 past-winner tag (2026-11-22) ─────────────────────────────────────────────────────────────────────────────────
# Ajay 2026-11-22, verbatim: "MEDS was a part winner that went up after hours.. Please actually add a past winner tag in
# our new ones looks for past winnings please if found again.." ONE pure index over the ACCEPTED 🏆 cards (the
# `read_winner_sub` listings — the same accept rule, no second reader): symbol (exact) → wins, newest first. A win's
# `day` is the session it ENDED (single-day: its day; multi-day: the run's last session), so a card is tagged only by a
# win that was complete before its own session — never the same day, never later. Cached by the identity of the two
# cached sub listings (they change only when a folder key moves). A tag only: no gate, no push, no rank.
_PW_CACHE: dict = {}           # root str -> (tuple of sub listings, index)


_PW_SERVED = ("day", "kind", "close_gain_pct", "file", "sub")     # the served entry keys (`days` stays internal)


def _pw_order(w) -> tuple:
    """Newest first by the run's LAST day; a same-day tie by the higher close gain (2026-11-22 fix #3; the renderer's
    replay_video.past_wins sorts by the same key)."""
    return (w["day"], w["close_gain_pct"], w["kind"], w["file"])


def past_winner_index(cards) -> dict:
    """Pure: accepted 🏆 cards → {symbol: [{day, kind, close_gain_pct, file, sub, days}, …] newest first}."""
    out: dict = {}
    for v in cards:
        out.setdefault(v["symbol"], []).append({"day": v["days"][-1], "kind": v["kind"],
                                                "close_gain_pct": v["close_gain_pct"], "file": v["file"],
                                                "sub": v["sub"], "days": tuple(v["days"])})
    for wins in out.values():
        wins.sort(key=_pw_order, reverse=True)
    return out


def _one_per_run(wins: list) -> list:
    """2026-11-22 fix #2: one entry per run. A single-day win whose day falls inside a LISTED multi-day run's days (same
    symbol — `wins` is one symbol's list) is that run's move, so only the run is listed; the same reel twice (same kind,
    same days) is listed once. `wins` is already filtered to the card's past and sorted newest first."""
    covered = {d for w in wins if w["kind"] == "multi_day" for d in w["days"]}
    seen, out = set(), []
    for w in wins:
        key = (w["kind"], w["days"])
        if (w["kind"] == "single_day" and w["day"] in covered) or key in seen:
            continue
        seen.add(key)
        out.append(w)
    return out


def _pw_date(win_day: str, card_day: str) -> str:
    """MM-DD, or YYYY-MM-DD when the win is from another calendar year than the card's day (2026-11-22 fix #3)."""
    return win_day[5:] if win_day[:4] == card_day[:4] else win_day


def _past_index(r: Path) -> dict:
    lists = tuple(read_winner_sub(sub, r) for sub in C.WINNER_SUB_KEYS)
    ck = str(r)
    with _LOCK:
        hit = _PW_CACHE.get(ck)
        if hit is not None and len(hit[0]) == len(lists) and all(a is b for a, b in zip(hit[0], lists)):
            return hit[1]
    idx = past_winner_index([v for lst in lists for v in lst["videos"]])
    with _LOCK:
        _PW_CACHE[ck] = (lists, idx)
    return idx


def past_wins_before(index: dict, symbol, day, words: str) -> Optional[dict]:
    """The served tag fields for a card of `symbol` on session `day`: only wins that ENDED strictly before `day`, one
    entry per run (`_one_per_run`; the count counts runs). None when there is none (the card then carries no tag key)."""
    if not isinstance(symbol, str) or not is_date(day):
        return None
    wins = _one_per_run([w for w in index.get(symbol, ()) if w["day"] < day])
    if not wins:
        return None
    shown = []
    for w in wins[: C.PAST_WIN_MAX]:
        kind_word = "" if w["kind"] == "single_day" else f" {_SUB_KIND[w['sub']][1]}"
        shown.append({**{k: w[k] for k in _PW_SERVED},
                      "text": f"{words} {_pw_date(w['day'], day)} {_signed_pct(w['close_gain_pct'])}{kind_word}"})
    more = len(wins) - len(shown)
    return {"past_winner": shown, "past_winner_count": len(wins),
            "past_winner_more_text": C.PAST_WIN_MORE_WORDS.format(n=more) if more > 0 else None}


def _tag_day_groups(groups: list, day, r: Path) -> list:
    idx = _past_index(r)
    if not idx:
        return groups
    out = []
    for g in groups:
        vids = []
        for v in g["videos"]:
            tag = past_wins_before(idx, v.get("symbol"), day, C.PAST_WIN_DAY_WORDS)
            vids.append({**v, **tag} if tag else v)
        out.append({**g, "videos": vids})
    return out


def resolve_winner_video(sub: str, name: str, root=None) -> Optional[Path]:
    """The listed 🏆 file's path, or None (→ 404). Only a listed name, only inside root/videos/<sub>."""
    if not isinstance(sub, str) or sub not in C.WINNER_SUB_KEYS or not _is_file_name(name):
        return None
    r = root_dir(root)
    if name not in read_winner_sub(sub, r)["files"]:
        return None
    p = r / C.VIDEOS_SUB / sub / name
    base = os.path.realpath(r / C.VIDEOS_SUB / sub) + os.sep
    real = os.path.realpath(p)
    if not real.startswith(base) or not os.path.isfile(real):
        return None
    return p
