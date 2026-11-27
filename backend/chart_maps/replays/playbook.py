"""📚 Playbook learning — the listing engine (spec playbook videos §3.3-§3.4, WP-be, 2026-11-27). Pure disk: no Mongo,
no network, no write.

Ajay 2026-11-27 ~02:15 ET, verbatim: "I loved the video can you move them under our replay tab with a PLaybook learning
and also add it to the playbook tab too with videos".

The host script `eod-audits/research/2026-11-27_gg_film/engine/publish.py` copies the finished film files into
`videos/playbook/<film-slug>/<name>.mp4` + one sidecar `<name>.json` per mp4 (inside the existing read-only bind).

GUARDS: `videos/playbook` must be a REAL directory (`os.lstat` + `stat.S_ISDIR` — a symlink or a regular file lists
nothing); a film folder must be a real directory whose name FULLMATCHES `C.PLAYBOOK_SLUG_RE` (no dot, no slash, no
trailing newline); an mp4 must be a regular file by `os.lstat` (a symlink is refused); the bytes route also checks that
the realpath sits under the REAL videos root + the two literal names.

ACCEPT RULE per `.json` in a film folder (any failure → `skipped_bad`; each card is built inside `except
C.CARD_ERRORS`): a dict · `kind == C.PLAYBOOK_KIND` · `schema == C.PLAYBOOK_SCHEMA` (an int, not a bool) · NO `window`
key (a nightly sidecar is never a playbook film) · `file` = the json's stem + ".mp4", present in the SAME scan, a regular
file · `bytes` == that file's size (a half-updated pair stays hidden until the publisher's second rename) · `film.slug` ==
the folder name · clean texts within the bounds · `role` / `variant` known · a chapter's `nn` / `id` valid · `duration_s`
finite > 0. A second sidecar claiming the same (role, nn, id, variant) → the first by file name wins. The film's title /
description = the FIRST ACCEPTED sidecar by file name; `chapters_total` = the largest served. Every pattern is applied
with fullmatch only. CACHE: per (root, slug) under `store._LOCK`, keyed by `store._scan`. Display only; UNMEASURED.
"""
from __future__ import annotations

import math
import os
import stat
from pathlib import Path
from typing import Optional

from growth.api import _scrub

from . import constants as C
from . import store as ST

_FILM_CACHE: dict = {}          # (root str, slug) -> (key, listing)
_LABELS = dict(C.PLAYBOOK_VARIANTS)


def is_slug(x) -> bool:
    return isinstance(x, str) and C.PLAYBOOK_SLUG_RE.fullmatch(x) is not None


def _playbook_dir(r: Path) -> Path:
    return r / C.VIDEOS_SUB / C.PLAYBOOK_SUB


def _real_dir(p) -> bool:
    """True only for a REAL directory: `os.lstat` never follows a symlink (a symlinked or a regular-file `playbook`)."""
    try:
        return stat.S_ISDIR(os.lstat(p).st_mode)
    except OSError:
        return False


def film_slugs(root=None) -> list:
    pb = _playbook_dir(ST.root_dir(root))
    if not _real_dir(pb):
        return []
    try:
        with os.scandir(pb) as it:
            out = [e.name for e in it if is_slug(e.name) and e.is_dir(follow_symlinks=False)]
    except (FileNotFoundError, NotADirectoryError, PermissionError):
        return []
    return sorted(out, reverse=True)


# ── the accept rule ───────────────────────────────────────────────────────────────────────────────────────────────
def _is_int(x) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def _is_num(x) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _clean(x, cap: Optional[int], required: bool = True):
    """A clean text: a str, printable, within `cap`, non-blank when required. None is allowed only when not required."""
    if x is None and not required:
        return None
    if not isinstance(x, str):
        raise TypeError("text must be a str")
    if cap is not None and len(x) > cap:
        raise ValueError("text too long")
    if required and not x.strip():
        raise ValueError("text is blank")
    if not x.isprintable():
        raise ValueError("text carries a control character")
    return x


def _markers(raw, duration: float) -> list:
    """Kept entries: finite 0 <= start_s < duration and a clean non-empty title; a bad entry is dropped."""
    if not isinstance(raw, list):
        return []
    out = []
    for m in raw:
        if not isinstance(m, dict):
            continue
        s = m.get("start_s")
        if not _is_num(s) or not (0 <= s < duration):
            continue
        try:
            title = _clean(m.get("title"), None)
        except C.CARD_ERRORS:
            continue
        out.append({"start_s": s, "title": title})
    return sorted(out, key=lambda m: m["start_s"])


def _card(body, name: str, slug: str, d: Path, present: set) -> dict:
    """One accepted sidecar → its card. Raises one of C.CARD_ERRORS on anything the accept rule refuses."""
    if not isinstance(body, dict):
        raise TypeError("sidecar must be a dict")
    if body.get("kind") != C.PLAYBOOK_KIND:
        raise ValueError("not a playbook sidecar")
    sch = body.get("schema")
    if not _is_int(sch) or sch != C.PLAYBOOK_SCHEMA:
        raise ValueError("unknown schema")
    if "window" in body:
        raise ValueError("a nightly sidecar is never a playbook film")
    f = body.get("file")
    if not ST._is_file_name(f) or f != name[: -len(".json")] + ".mp4" or f not in present:
        raise ValueError("file is not this sidecar's mp4")
    try:
        st = os.lstat(d / f)
    except OSError as e:
        raise ValueError("mp4 vanished") from e
    if not stat.S_ISREG(st.st_mode):
        raise ValueError("mp4 must be a regular file (no symlink)")
    nb = body.get("bytes")
    if not _is_int(nb) or nb <= 0 or nb != st.st_size:
        raise ValueError("bytes != the file size")
    film = body["film"]
    if not isinstance(film, dict):
        raise TypeError("film must be a dict")
    if film.get("slug") != slug:
        raise ValueError("film.slug != the folder")
    total = film.get("chapters_total")
    if total is not None and (not _is_int(total) or total < 1):
        raise ValueError("bad chapters_total")
    film_words = {"title": _clean(film.get("title"), C.PLAYBOOK_TITLE_MAX),
                  "description": _clean(film.get("description"), C.PLAYBOOK_DESCRIPTION_MAX, required=False),
                  "chapters_total": total}
    role, variant = body.get("role"), body.get("variant")
    if not isinstance(role, str) or role not in C.PLAYBOOK_ROLES:
        raise ValueError("unknown role")
    if not isinstance(variant, str) or variant not in C.PLAYBOOK_VARIANT_KEYS:
        raise ValueError("unknown variant")
    dur = body.get("duration_s")
    if not _is_num(dur) or dur <= 0:
        raise ValueError("duration_s must be finite > 0")
    height = body.get("height")
    if height is not None and (not _is_int(height) or height <= 0):
        raise ValueError("bad height")
    chapter, markers = None, []
    if role == "chapter":
        ch = body["chapter"]
        if not isinstance(ch, dict):
            raise TypeError("chapter must be a dict")
        nn, cid = ch.get("nn"), ch.get("id")
        if not _is_int(nn) or not (0 <= nn <= C.PLAYBOOK_NN_MAX):
            raise ValueError("bad nn")
        if not isinstance(cid, str) or C.PLAYBOOK_CHAPTER_ID_RE.fullmatch(cid) is None:
            raise ValueError("bad chapter id")
        chapter = {"nn": nn, "id": cid, "title": _clean(ch.get("title"), C.PLAYBOOK_TITLE_MAX),
                   "subtitle": _clean(ch.get("subtitle"), C.PLAYBOOK_SUBTITLE_MAX, required=False)}
    else:
        markers = _markers(body.get("markers"), dur)
    return {"file": f, "role": role, "variant": variant, "chapter": chapter, "markers": markers,
            "duration_s": dur, "bytes": nb, "height": height, "film": film_words}


def _ident(card: dict) -> tuple:
    ch = card["chapter"] or {}
    return (card["role"], ch.get("nn"), ch.get("id"), card["variant"])


def _empty_counts() -> dict:
    return {"videos": 0, "skipped_bad": 0, "no_sidecar": 0}


def _parse_film(d: Path, slug: str, names) -> dict:
    present = set(names)
    counts = _empty_counts()
    cards, files, seen = [], set(), set()
    for name in sorted(names):
        if not name.endswith(".json"):
            continue
        try:
            body = ST._read_sidecar(d / name)
        except (OSError, ValueError, UnicodeDecodeError):
            counts["skipped_bad"] += 1
            continue
        try:
            card = _card(body, name, slug, d, present)
        except C.CARD_ERRORS:
            counts["skipped_bad"] += 1
            continue
        ident = _ident(card)
        if ident in seen:                                    # the first by file name wins
            counts["skipped_bad"] += 1
            continue
        seen.add(ident)
        cards.append(card)
        files.add(card["file"])
    stems = {n[: -len(".json")] for n in names if n.endswith(".json")}
    counts["no_sidecar"] = sum(1 for n in names if n.endswith(".mp4") and n[: -len(".mp4")] not in stems)
    counts["videos"] = len(cards)
    film = None
    if cards:
        totals = [c["film"]["chapters_total"] for c in cards if c["film"]["chapters_total"] is not None]
        film = {"title": cards[0]["film"]["title"], "description": cards[0]["film"]["description"],
                "chapters_total": max(totals) if totals else None}
    return {"slug": slug, "cards": cards, "files": frozenset(files), "counts": counts, "film": film}


def _empty_film(slug) -> dict:
    return {"slug": slug, "cards": [], "files": frozenset(), "counts": _empty_counts(), "film": None}


def read_film(slug: str, root=None) -> dict:
    if not is_slug(slug):
        return _empty_film(slug)
    r = ST.root_dir(root)
    ck = (str(r), slug)
    d = _playbook_dir(r) / slug
    key, names = ST._scan(d)
    with ST._LOCK:
        if key is None:
            _FILM_CACHE.pop(ck, None)
            return _empty_film(slug)
        hit = _FILM_CACHE.get(ck)
        if hit is not None and hit[0] == key:
            return hit[1]
    listing = _parse_film(d, slug, names)
    with ST._LOCK:
        _FILM_CACHE[ck] = (key, listing)
    return listing


# ── the served words ──────────────────────────────────────────────────────────────────────────────────────────────
def length_text(sec) -> str:
    s = int(round(sec))
    h, rem = divmod(s, 3600)
    m, ss = divmod(rem, 60)
    return f"{h}:{m:02d}:{ss:02d}" if h else f"{m}:{ss:02d}"


def size_text(nbytes) -> str:
    return f"{nbytes / 1e6:.0f} MB" if nbytes < 1e9 else f"{nbytes / 1e9:.1f} GB"


def _vrank(card: dict) -> int:
    return C.PLAYBOOK_VARIANT_KEYS.index(card["variant"])


def _variants(slug: str, cards: list) -> list:
    out = []
    for c in sorted(cards, key=_vrank):
        h = c["height"]
        out.append({"key": c["variant"], "label": _LABELS[c["variant"]], "file": c["file"],
                    "src": C.PLAYBOOK_VIDEO_PATH.format(film=slug, name=c["file"]),
                    "duration_s": c["duration_s"], "length_text": length_text(c["duration_s"]),
                    "bytes": c["bytes"], "size_text": size_text(c["bytes"]),
                    "height": h, "quality_text": f"{h}p" if h is not None else None})
    return out


def _film_payload(slug: str, lst: dict) -> dict:
    by_ch: dict = {}
    fulls = []
    for c in lst["cards"]:
        if c["role"] == "chapter":
            by_ch.setdefault((c["chapter"]["nn"], c["chapter"]["id"]), []).append(c)
        else:
            fulls.append(c)
    chapters = []
    for nn, cid in sorted(by_ch):
        cs = sorted(by_ch[(nn, cid)], key=_vrank)
        head = cs[0]["chapter"]
        chapters.append({"key": f"{nn:02d}_{cid}", "nn": nn, "nn_text": f"{nn:02d}", "id": cid,
                         "title": head["title"], "subtitle": head["subtitle"], "variants": _variants(slug, cs)})
    full = None
    if fulls:
        marks = sorted(fulls, key=_vrank)[0]["markers"]
        n = len(marks)
        full = {"key": "full", "title": C.PLAYBOOK_FULL_TITLE,
                "subtitle": C.PLAYBOOK_FULL_SUB_WORDS[0 if n == 1 else 1].format(n=n) if n else None,
                "variants": _variants(slug, fulls),
                "markers": [{"start_s": m["start_s"], "text": f"{length_text(m['start_s'])} {m['title']}"}
                            for m in marks]}
    n = len(chapters)
    total = lst["film"]["chapters_total"]
    m = round(sum(ch["variants"][0]["duration_s"] for ch in chapters) / 60)
    if total is not None and n < total:
        summary = C.PLAYBOOK_SUMMARY_PARTIAL.format(n=n, total=total, m=m)
    else:
        summary = C.PLAYBOOK_SUMMARY_ALL[0 if n == 1 else 1].format(n=n, m=m)
    return {"slug": slug, "title": lst["film"]["title"], "description": lst["film"]["description"],
            "summary_text": summary, "chapters": chapters, "full": full}


def payload(root=None) -> dict:
    r = ST.root_dir(root)
    base = {"title": C.PLAYBOOK_TITLE, "tab": C.TAB, "note": C.PLAYBOOK_NOTE}
    counts = {"films": 0, "chapters": 0, "videos": 0, "skipped_bad": 0, "no_sidecar": 0}
    if not (r / C.VIDEOS_SUB).is_dir():
        return _scrub({**base, "state": "no_folder", "text": C.NO_FOLDER_TEXT, "variant_options": [],
                       "counts": counts, "films": []})
    films = []
    for slug in film_slugs(r):
        lst = read_film(slug, r)
        counts["skipped_bad"] += lst["counts"]["skipped_bad"]
        counts["no_sidecar"] += lst["counts"]["no_sidecar"]
        if not lst["cards"]:
            continue
        film = _film_payload(slug, lst)
        films.append(film)
        counts["films"] += 1
        counts["chapters"] += len(film["chapters"])
        counts["videos"] += lst["counts"]["videos"]
    if not films:
        return _scrub({**base, "state": "empty", "text": C.PLAYBOOK_EMPTY_TEXT, "variant_options": [],
                       "counts": counts, "films": []})
    keys = {v["key"] for f in films for row in f["chapters"] + ([f["full"]] if f["full"] else [])
            for v in row["variants"]}
    options = [{"key": k, "label": lab} for k, lab in C.PLAYBOOK_VARIANTS if k in keys]
    return _scrub({**base, "state": "ready", "text": None, "variant_options": options, "counts": counts,
                   "films": films})


def resolve_video(film: str, name: str, root=None) -> Optional[Path]:
    """The listed file's path, or None (→ 404). A slug + a listed name only; the realpath must sit under the REAL
    videos root + `playbook/<film>/` (a symlinked `playbook` or film folder resolves elsewhere and fails)."""
    if not is_slug(film) or not ST._is_file_name(name):
        return None
    r = ST.root_dir(root)
    if film not in film_slugs(r):
        return None
    if name not in read_film(film, r)["files"]:
        return None
    p = _playbook_dir(r) / film / name
    base = os.path.join(os.path.realpath(r / C.VIDEOS_SUB), C.PLAYBOOK_SUB, film) + os.sep
    real = os.path.realpath(p)
    if not real.startswith(base) or not os.path.isfile(real):
        return None
    return p
