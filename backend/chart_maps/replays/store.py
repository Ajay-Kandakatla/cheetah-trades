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
import os
import threading
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
