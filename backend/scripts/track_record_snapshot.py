"""Track-record row snapshot — host CLI + the merge (spec rec157 WP-3, 2026-11-11). Record only: nothing serves it.

One run = ONE `docker exec` of track_record_snapshot_probe.py (read-only, the served engines) → a deterministic dated
gzip dump → merged into an append-only, versioned store → a manifest. Stdlib only, Python 3.9-safe (the host venv).

Store (`--out`, default /Users/ajay/clinet-test/eod-audits/track-record-snapshots/):
  dumps/<snapshot date>.json.gz   the probe JSON minus `generated_utc`, sorted keys, gzip mtime 0 (same content → same
                                  bytes); a same-date dump with OTHER content is never overwritten → <date>.r2.json.gz …
  merged.jsonl                    one line per VERSION: {key, page, v, snapshot_date, sha, carried, row}
  manifest.json                   {schema, dumps: [...], merged: {lines, bytes, sha256 (of exactly those first bytes),
                                  keys, versions_by_page, never_captured}}
Key = `page|<the engine's row id>` (the id holds date, symbol, setup and — on the GG pages — the kind). The alert time
is IN the row: a re-stamped alert time is a new VERSION of the same key, never a second key.
Merge: an expired TTL block (None now, its source doc gone now) carries the previous value (an expiry is not a change);
equal canonical content → nothing appended; different → version v + 1, the old version stays; a key gone from Mongo is
kept untouched. Every write is temp + os.replace; a killed run finishes on the next one (an unlisted dump is adopted, a
merged tail past the manifest's prefix is accepted); anything else that does not match → exit 2, nothing written.
Exit codes: 0 ok · 1 --verify failed / recoverable · 2 refused (the named reason; never truncated or repaired)."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional

SCHEMA = 1
PAGES = ("gg5", "gg1", "gga", "luk")
CORE_VOLATILE = ()                                   # nothing in the core is clock-relative once a session is closed
TTL_BLOCKS = {"gg5": ("ctx_eod", "audit", "avg_vol_50", "bars"), "gg1": ("ctx_eod", "avg_vol_50", "bars"),
              "gga": ("audit_raw", "audit_cell"), "luk": ("bars", "ctx_eod", "daily")}
# the src_present flag that says whether a block's source doc exists now (default: the block's own name)
SRC_FLAG = {"audit_raw": "audit", "audit_cell": "audit"}
# a field that is read from the SAME source doc as its block and expires with it (carried with it)
TTL_COMPANIONS = {"avg_vol_50": ("avg_vol_50_date",)}
LINE_KEYS = ("key", "page", "v", "snapshot_date", "sha", "carried", "row")
DUMP_KEYS = ("today_et", "constants", "pages", "sessions", "faults")
DEFAULT_OUT = "/Users/ajay/clinet-test/eod-audits/track-record-snapshots"
DEFAULT_CONTAINER = "cheetah-market-app-api-1"
PROBE = Path(__file__).resolve().with_name("track_record_snapshot_probe.py")
DUMP_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:\.r(\d+))?\.json\.gz$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class StoreCorrupt(Exception):
    """The store on disk does not match its manifest (or a line / dump is malformed) → exit 2."""


class DumpRefused(Exception):
    """A probe dump that is not the expected shape (a null or missing page, a row without an id, a duplicate id)."""


# ── pure helpers ──────────────────────────────────────────────────────────────────────────────────────────────────
def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _jline(obj) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def key_of(page: str, row: dict) -> str:
    return f"{page}|{row['id']}"


def canon(row: dict, page: str) -> str:
    """Sorted-key JSON of the row without `src_present` (a source appearing / vanishing is never content)."""
    return _jline({k: v for k, v in row.items() if k != "src_present" and k not in CORE_VOLATILE})


def _src_gone(row: dict, block: str) -> bool:
    sp = row.get("src_present")
    return isinstance(sp, dict) and sp.get(SRC_FLAG.get(block, block)) is False


def merge_row(prev: Optional[dict], row: dict, page: str) -> tuple:
    """(row_to_store, carried, is_new_version). `prev` = the key's latest stored row (None → version 1)."""
    if prev is None:
        return row, [], True
    cmp_row = dict(row)
    carried = []
    for block in TTL_BLOCKS[page]:
        if cmp_row.get(block) is None and _src_gone(row, block) and prev.get(block) is not None:
            cmp_row[block] = prev[block]
            for comp in TTL_COMPANIONS.get(block, ()):
                if comp in prev:
                    cmp_row[comp] = prev[comp]
            carried.append(block)
    if canon(cmp_row, page) == canon(prev, page):
        return prev, carried, False
    return cmp_row, carried, True


def validate_dump(dump) -> None:
    """Raise DumpRefused unless `dump` is the probe's shape with four non-null pages of rows with unique ids."""
    if not isinstance(dump, dict):
        raise DumpRefused("the dump is not a JSON object")
    for k in DUMP_KEYS:
        if k not in dump:
            raise DumpRefused(f"the dump has no {k!r}")
    if not isinstance(dump.get("today_et"), str) or not DATE_RE.match(dump["today_et"]):
        raise DumpRefused("today_et is not a date")
    pages = dump.get("pages")
    if not isinstance(pages, dict):
        raise DumpRefused("pages is not an object")
    for page in PAGES:
        if page not in pages:
            raise DumpRefused(f"page {page} is missing")
        if pages[page] is None:
            raise DumpRefused(f"page {page} is null (the probe could not read it)")
        if not isinstance(pages[page], list):
            raise DumpRefused(f"page {page} is not a list")
        seen, dup = set(), []
        for row in pages[page]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not row.get("id"):
                raise DumpRefused(f"page {page} holds a row without an id")
            if not isinstance(row.get("src_present"), dict):
                raise DumpRefused(f"page {page} row {row['id']} has no src_present")
            if row["id"] in seen:
                dup.append(row["id"])
            seen.add(row["id"])
        if dup:
            raise DumpRefused(f"page {page} holds duplicate ids: {', '.join(sorted(set(dup)))}")
    extra = sorted(set(pages) - set(PAGES))
    if extra:
        raise DumpRefused(f"unknown pages: {', '.join(extra)}")


def _latest_map(store_lines: list) -> dict:
    out = {}
    for ln in store_lines:
        cur = out.get(ln["key"])
        if cur is None or ln["v"] > cur["v"]:
            out[ln["key"]] = ln
    return out


def merge(store_lines: list, dump: dict, snapshot_date: str, sha: Optional[str] = None) -> list:
    """The lines to APPEND for this dump (may be empty). `store_lines` = parsed store lines (file order)."""
    validate_dump(dump)
    latest = _latest_map(store_lines)
    out = []
    for page in PAGES:
        for row in dump["pages"][page]:
            k = key_of(page, row)
            prev_line = latest.get(k)
            prev = prev_line["row"] if prev_line else None
            stored, carried, new = merge_row(prev, row, page)
            if not new:
                continue
            ln = {"key": k, "page": page, "v": (prev_line["v"] + 1) if prev_line else 1,
                  "snapshot_date": snapshot_date, "sha": sha, "carried": carried, "row": stored}
            out.append(ln)
            latest[k] = ln
    return out


def null_counts(dump: dict) -> dict:
    """{page: {block: [n_null, n_rows]}} over the TTL blocks of each page."""
    out = {}
    for page in PAGES:
        rows = (dump.get("pages") or {}).get(page) or []
        out[page] = {b: [sum(1 for r in rows if r.get(b) is None), len(rows)] for b in TTL_BLOCKS[page]}
    return out


def all_null(nulls: dict) -> list:
    """[[page, block]] where the block is None on EVERY row of a page that has rows (named, nothing else judged)."""
    return [[p, b] for p in PAGES for b in TTL_BLOCKS[p]
            if (nulls.get(p) or {}).get(b) and nulls[p][b][1] > 0 and nulls[p][b][0] == nulls[p][b][1]]


def never_captured(store_lines: list) -> dict:
    """{page: {block: n}} — keys whose EVERY stored version holds None for that TTL block."""
    held = {}
    pages_of = {}
    for ln in store_lines:
        pages_of[ln["key"]] = ln["page"]
        for b in TTL_BLOCKS.get(ln["page"], ()):
            if ln["row"].get(b) is not None:
                held.setdefault(ln["key"], set()).add(b)
    out = {p: {b: 0 for b in TTL_BLOCKS[p]} for p in PAGES}
    for k, p in pages_of.items():
        for b in TTL_BLOCKS.get(p, ()):
            if b not in held.get(k, set()):
                out[p][b] += 1
    return out


def latest_rows(store_lines: list, keys=None) -> dict:
    """key → the latest stored row (TTL blocks as carried). `keys` (e.g. a dump's keys) → only those keys; a key kept
    only in the store (its Mongo source gone) is left out."""
    lm = _latest_map(store_lines)
    if keys is None:
        return {k: ln["row"] for k, ln in lm.items()}
    return {k: lm[k]["row"] for k in keys if k in lm}


def dump_keys(dump: dict) -> list:
    return [key_of(p, r) for p in PAGES for r in dump["pages"][p]]


def rows_by_session(dump: dict) -> dict:
    out = {}
    for page in PAGES:
        c = {}
        for r in dump["pages"][page]:
            d = str(r.get("date"))
            c[d] = c.get(d, 0) + 1
        out[page] = dict(sorted(c.items()))
    return out


def dump_bytes(dump: dict) -> bytes:
    """The deterministic gzip of the dump minus `generated_utc` (sorted keys, mtime 0, no file name)."""
    body = {k: v for k, v in dump.items() if k != "generated_utc"}
    raw = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    buf = io.BytesIO()
    with gzip.GzipFile(filename="", mode="wb", fileobj=buf, mtime=0, compresslevel=9) as gz:
        gz.write(raw)
    return buf.getvalue()


def _gunzip_json(b: bytes):
    return json.loads(gzip.decompress(b).decode("utf-8"))


# ── store on disk ─────────────────────────────────────────────────────────────────────────────────────────────────
def _paths(out_dir) -> tuple:
    o = Path(out_dir)
    return o, o / "dumps", o / "merged.jsonl", o / "manifest.json"


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def _parse_lines(raw: bytes) -> list:
    if not raw:
        return []
    if not raw.endswith(b"\n"):
        raise StoreCorrupt("merged.jsonl: the last line is torn (no newline)")
    out = []
    for i, ln in enumerate(raw.split(b"\n")[:-1], 1):
        try:
            obj = json.loads(ln.decode("utf-8"))
        except Exception:                                       # noqa: BLE001
            raise StoreCorrupt(f"merged.jsonl line {i} does not parse")
        if (not isinstance(obj, dict) or set(obj) != set(LINE_KEYS) or obj.get("page") not in PAGES
                or not isinstance(obj.get("v"), int) or not isinstance(obj.get("row"), dict)
                or not isinstance(obj.get("carried"), list)
                or obj.get("key") != f"{obj.get('page')}|{obj['row'].get('id')}"):
            raise StoreCorrupt(f"merged.jsonl line {i} is not the line shape")
        out.append(obj)
    last = {}
    for i, obj in enumerate(out, 1):
        want = last.get(obj["key"], 0) + 1
        if obj["v"] != want:
            raise StoreCorrupt(f"merged.jsonl line {i}: v {obj['v']} of {obj['key']} is not contiguous (want {want})")
        last[obj["key"]] = obj["v"]
    return out


def _dump_entry(name: str, b: bytes, dump: dict, generated_utc=None) -> dict:
    m = DUMP_NAME.match(name)
    return {"file": name, "sha256": _sha(b), "bytes": len(b), "snapshot_date": m.group(1) if m else None,
            "generated_utc": generated_utc, "rows": rows_by_session(dump), "nulls": null_counts(dump)}


def open_store(out_dir) -> dict:
    """{"lines", "raw", "manifest", "tail", "unlisted_dumps"} — raises StoreCorrupt on anything that does not match.
    `tail` = whole lines past the manifest's prefix (a run killed after the merged write); `unlisted_dumps` = dump files
    the manifest does not list (a run killed after the dump write), each validated: [(name, bytes, dump)]."""
    o, dd, mp, fp = _paths(out_dir)
    manifest = None
    if fp.exists():
        try:
            manifest = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:                                       # noqa: BLE001
            raise StoreCorrupt("manifest.json does not parse")
        if (not isinstance(manifest, dict) or manifest.get("schema") != SCHEMA
                or not isinstance(manifest.get("dumps"), list) or not isinstance(manifest.get("merged"), dict)):
            raise StoreCorrupt("manifest.json is not the manifest shape")
    raw = mp.read_bytes() if mp.exists() else b""
    pre_bytes = int((manifest or {}).get("merged", {}).get("bytes") or 0)
    if len(raw) < pre_bytes:
        raise StoreCorrupt("merged.jsonl is shorter than the manifest's prefix")
    if manifest is not None and _sha(raw[:pre_bytes]) != manifest["merged"].get("sha256"):
        raise StoreCorrupt("merged.jsonl: the prefix sha does not match the manifest")
    if pre_bytes and raw[pre_bytes - 1:pre_bytes] != b"\n":
        raise StoreCorrupt("merged.jsonl: the manifest's prefix does not end on a line")
    lines = _parse_lines(raw)
    n_pre = raw[:pre_bytes].count(b"\n")
    if manifest is not None and n_pre != int(manifest["merged"].get("lines") or 0):
        raise StoreCorrupt("merged.jsonl: the prefix line count does not match the manifest")
    listed = {}
    for e in (manifest or {}).get("dumps") or []:
        if not isinstance(e, dict) or not isinstance(e.get("file"), str):
            raise StoreCorrupt("manifest.json lists a dump without a file name")
        p = dd / e["file"]
        if not p.exists():
            raise StoreCorrupt(f"listed dump {e['file']} is missing")
        if _sha(p.read_bytes()) != e.get("sha256"):
            raise StoreCorrupt(f"listed dump {e['file']}: its sha moved")
        listed[e["file"]] = e
    unlisted = []
    if dd.exists():
        for p in sorted(dd.iterdir()):
            if p.name.startswith(".") or p.name in listed:
                continue
            if not DUMP_NAME.match(p.name):
                raise StoreCorrupt(f"unlisted file dumps/{p.name} is not a dump name")
            b = p.read_bytes()
            try:
                d = _gunzip_json(b)
            except Exception:                                   # noqa: BLE001
                raise StoreCorrupt(f"unlisted dump {p.name} does not gunzip / parse")
            try:
                validate_dump(d)
            except DumpRefused as exc:
                raise StoreCorrupt(f"unlisted dump {p.name} is not the dump shape: {exc}")
            unlisted.append((p.name, b, d))
    return {"lines": lines, "raw": raw, "manifest": manifest, "tail": len(lines) - n_pre,
            "unlisted_dumps": unlisted}


def _manifest(dump_entries: list, raw: bytes, lines: list) -> dict:
    vbp = {p: 0 for p in PAGES}
    for ln in lines:
        vbp[ln["page"]] += 1
    return {"schema": SCHEMA, "dumps": dump_entries,
            "merged": {"lines": len(lines), "bytes": len(raw), "sha256": _sha(raw),
                       "keys": len({ln["key"] for ln in lines}), "versions_by_page": vbp,
                       "never_captured": never_captured(lines)}}


def _dump_name_for(dd: Path, snapshot_date: str, b: bytes) -> tuple:
    """(file name, is_new) — an existing same-date file with the same CONTENT is reused; else the next free name."""
    want = gzip.decompress(b)
    n = 1
    while True:
        name = f"{snapshot_date}.json.gz" if n == 1 else f"{snapshot_date}.r{n}.json.gz"
        p = dd / name
        if not p.exists():
            return name, True
        cur = p.read_bytes()
        try:
            if gzip.decompress(cur) == want:
                return name, False
        except Exception:                                       # noqa: BLE001
            pass
        n += 1


def run(dump: dict, out_dir, snapshot_date: Optional[str] = None, *, dry_run: bool = False) -> tuple:
    """A plain run on a probe dump → (exit code, summary). Every check runs before the first write."""
    summary = {"snapshot_date": None, "dump_file": None, "appended": {p: 0 for p in PAGES},
               "recovered": {"dumps": [], "lines": 0}, "nulls": None, "all_null": [], "exit": 2}
    o, dd, mp, fp = _paths(out_dir)
    try:
        validate_dump(dump)
        sd = snapshot_date or dump["today_et"]
        if not DATE_RE.match(str(sd)):
            raise DumpRefused(f"snapshot date {sd!r} is not a date")
        if sd > dump["today_et"]:
            raise DumpRefused(f"snapshot date {sd} is after the probe's session {dump['today_et']}")
        st = open_store(out_dir)
    except (StoreCorrupt, DumpRefused) as exc:
        summary["refused"] = str(exc)
        return 2, summary
    summary["snapshot_date"] = sd
    lines = list(st["lines"])
    entries = list((st["manifest"] or {}).get("dumps") or [])
    appended = []
    try:
        for name, b, d in st["unlisted_dumps"]:
            new = merge(lines, d, DUMP_NAME.match(name).group(1), _sha(b))
            lines += new
            appended += new
            entries.append(_dump_entry(name, b, d))
            summary["recovered"]["dumps"].append(name)
        b = dump_bytes(dump)
        name, is_new = _dump_name_for(dd, sd, b)
        if is_new:
            sha = _sha(b)
        else:
            sha = _sha((dd / name).read_bytes())
        new = merge(lines, dump, sd, sha)
    except DumpRefused as exc:
        summary["refused"] = str(exc)
        return 2, summary
    lines += new
    appended += new
    if is_new:
        entries.append(_dump_entry(name, b, dump, dump.get("generated_utc")))
    summary["recovered"]["lines"] = st["tail"]
    summary["dump_file"] = f"dumps/{name}"
    for ln in appended:
        summary["appended"][ln["page"]] += 1
    nulls = null_counts(dump)
    summary["nulls"] = nulls
    summary["all_null"] = all_null(nulls)
    summary["exit"] = 0
    raw_new = st["raw"] + "".join(_jline(ln) + "\n" for ln in appended).encode("utf-8")
    need_manifest = (st["manifest"] is None and (raw_new or entries)) or is_new or appended or st["tail"] \
        or st["unlisted_dumps"]
    if dry_run:
        summary["dry_run"] = True
        return 0, summary
    if is_new:
        _atomic_write(dd / name, b)
    if appended:
        _atomic_write(mp, raw_new)
    if need_manifest:
        man = _manifest(entries, raw_new, lines)
        _atomic_write(fp, (json.dumps(man, sort_keys=True, indent=1) + "\n").encode("utf-8"))
    return 0, summary


def verify(store_lines: Optional[list], dump: dict, manifest: Optional[dict], out_dir) -> dict:
    """Writes nothing. Passes (ok True) only when the store opens clean with nothing to recover, every dump sha and the
    merged prefix sha match the manifest, and a dry merge of `dump` would append NOTHING."""
    res = {"covered": {p: 0 for p in PAGES}, "not_covered": [], "kept_not_in_mongo": {p: 0 for p in PAGES},
           "nulls": None, "all_null": [], "never_captured": None, "integrity": "ok", "ok": False}
    try:
        validate_dump(dump)
    except DumpRefused as exc:
        res["integrity"] = f"dump refused: {exc}"
        return res
    res["nulls"] = null_counts(dump)
    res["all_null"] = all_null(res["nulls"])
    try:
        st = open_store(out_dir)
    except StoreCorrupt as exc:
        res["integrity"] = str(exc)
        return res
    lines = st["lines"] if store_lines is None else store_lines
    man = st["manifest"] if manifest is None else manifest
    res["never_captured"] = never_captured(lines)
    todo = []
    if st["manifest"] is None and (st["raw"] or st["unlisted_dumps"]):
        todo.append("no manifest")
    if st["tail"]:
        todo.append(f"{st['tail']} merged line(s) past the manifest")
    if st["unlisted_dumps"]:
        todo.append("unlisted dump(s) " + ", ".join(n for n, _, _ in st["unlisted_dumps"]))
    if todo:
        res["integrity"] = "recoverable: " + "; ".join(todo)
    if man is None and not lines:
        res["integrity"] = res["integrity"] if todo else "empty store"
    new = merge(lines, dump, dump["today_et"])
    new_keys = {ln["key"] for ln in new}
    res["not_covered"] = sorted(new_keys)
    dk = set()
    for p in PAGES:
        for r in dump["pages"][p]:
            k = key_of(p, r)
            dk.add(k)
            if k not in new_keys:
                res["covered"][p] += 1
    for k, ln in _latest_map(lines).items():
        if k not in dk:
            res["kept_not_in_mongo"][ln["page"]] += 1
    res["ok"] = res["integrity"] == "ok" and not new
    return res


# ── the probe ─────────────────────────────────────────────────────────────────────────────────────────────────────
def probe(container: str) -> dict:
    """ONE `docker exec` of the probe (stdin) → its JSON. Raises DumpRefused on a failed exec or unparseable output."""
    src = PROBE.read_bytes()
    try:
        cp = subprocess.run(["docker", "exec", "-i", "-w", "/app", container, "python", "-"], input=src,
                            capture_output=True, check=False)
    except Exception as exc:                                    # noqa: BLE001
        raise DumpRefused(f"docker exec failed: {type(exc).__name__}")
    if cp.returncode != 0:
        tail = cp.stderr.decode("utf-8", "replace").strip().splitlines()[-1:] or [""]
        raise DumpRefused(f"the probe exited {cp.returncode}: {tail[0][:300]}")
    try:
        return json.loads(cp.stdout.decode("utf-8"))
    except Exception:                                           # noqa: BLE001
        raise DumpRefused("the probe output does not parse")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Track-record row snapshot (record only, read-only probe).")
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--from-json", dest="from_json", default=None)
    ap.add_argument("--container", default=DEFAULT_CONTAINER)
    ap.add_argument("--snapshot-date", dest="snapshot_date", default=None)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--dry-run", dest="dry_run", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.from_json:
            dump = json.loads(Path(a.from_json).read_text(encoding="utf-8"))
        else:
            dump = probe(a.container)
    except DumpRefused as exc:
        print(_jline({"exit": 1 if a.verify else 2, "refused": str(exc)}))
        return 1 if a.verify else 2
    except Exception as exc:                                    # noqa: BLE001
        print(_jline({"exit": 1 if a.verify else 2, "refused": f"the dump could not be read: {type(exc).__name__}"}))
        return 1 if a.verify else 2
    if a.verify:
        res = verify(None, dump, None, a.out)
        code = 0 if res.pop("ok") else 1
        res["exit"] = code
        print(json.dumps(res, sort_keys=True, ensure_ascii=False))
        return code
    code, summary = run(dump, a.out, a.snapshot_date, dry_run=a.dry_run)
    print(json.dumps(summary, sort_keys=True, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
