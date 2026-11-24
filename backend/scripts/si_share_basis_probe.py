"""🩳 % of float — dilution, splits, filings: live probe of the share-basis check (READ-ONLY, re-runnable).

THE ASK (Ajay 2026-11-24, verbatim, in order)
  "Yeah please"
  "Make sure we are looking for Dilution.."
  "Also split related events and filing so we flag them in the right way"

Spec `sidilute` rev 2, §4 probe-docs, §5 step 2. Engine doc: docs/short_interest/float_dilution_split_2026_11_24.md.

What it does (ZERO writes):
  1. `block_writes()` FIRST — every pymongo write method becomes a recorded no-op in this process.
  2. Names = `--symbols`, else the 🩳 sub's stored reads for the session + the 👀 Watch owner list, read from Mongo.
     SMTK is always added (the structural check below needs it).
  3. For each name: the served block with `basis=None` (old) and with the basis doc that
     `share_basis.refresh_symbol(.., store=False)` returns (new) — the REAL worker, never stored.
     `--seed F` (the `share_basis seed` input shape) lays a seed float track over a name whose basis doc holds none,
     in memory only, under the same rule as the CLI seed (the live float must equal the seed's).
  4. Prints one line per name `SYM | old chip | new chip | refused | flags | sources`, a summary by
     `basis_math.FLOAT_STALE_WHEN` mode (all three, the same basis docs), the names whose tier changes, and the names
     whose change % was rebased across a split.
  4b. 2026-11-24 later (Ajay: "Is GMEX float accurate?") — the NEWER-FLOAT section: each name whose basis doc holds a
     Yahoo float dated later than the record's and different from it (`basis_math.newer_float`), with both floats and
     dates, the % of float and tier BEFORE (the same basis doc with that Yahoo float removed and the track re-run on
     the record — what the 11-24 check served) and NOW; the names entering / leaving 🩳 High / EXTREME; and, for every
     name with a stored 🚩 Gajjala read this session, the 🩳 High SI list membership before / now
     (`chart_maps.gajjala.high_si.classify` — the list the 9/21 cross push rings for); the flags each name gains and
     LOSES (fix, same day: the dilution checks keep the replaced float's date, so the lost list must be empty).
  5. Writes `si_share_basis_probe.json` and `si_live_blocks.json` (the shared-fixture shape) for
     SI_LIVE_PAYLOAD=<path>/si_live_blocks.json npx vitest run src/components/ShortInterest.payload.test.tsx

EXIT 1 unless SMTK's new block holds the STRUCTURE (spec C9) — never a dated chip, never a settlement date:
  pct_of_float is None · tier is None · basis.float_refused in ("diluted", "split") · flag keys include
  float_stale and split · shares_source starts "SEC" · pct_of_shares_out == round(si_shares / shares_outstanding
  * 100, 2) · while settlement_date < 2026-11-23: shares_outstanding == 4859369.

Run only in a throwaway container with the worktree mounted (never the live api / cron containers):
  docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default \\
    -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
    -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 --env-file <600-mode key file> \\
    -v <worktree>/backend:/app:ro -v <outdir>:/out -w /out \\
    cheetah-api:latest python -u /app/scripts/si_share_basis_probe.py --symbols SMTK,LABT,KITT

Never prints the key or a request URL; every output is scrubbed of `apiKey=`. Display data only — it measures nothing
about returns.
"""
from __future__ import annotations

import argparse
import collections
import contextlib
import copy
import json
import math
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Callable, Optional

ACCEPT = "SMTK"
ACCEPT_SHARES = 4859369                 # SEC 10-Q cover 2026-11-11 (spec §1.5) — valid until the 11-23 split's side
ACCEPT_SHARES_BEFORE = "2026-11-23"     # the 1-for-5 reverse split's execution date (spec §1.5)
ACCEPT_REFUSALS = ("diluted", "split")
ACCEPT_FLAGS = ("float_stale", "split")
_SCRUB = re.compile(r"apiKey=[^&\s\"']+")


def _scrub(text: str, key: str = "") -> str:
    if key:
        text = text.replace(key, "***")
    return _SCRUB.sub("apiKey=***", text)


# ───────────────────────────────────────────── the structural check (C9)
def smtk_check(block) -> list:
    """The failures of SMTK's new block against the structure of spec §4 (an empty list = it holds)."""
    if not isinstance(block, dict):
        return ["no block"]
    bad = []
    basis = block.get("basis") if isinstance(block.get("basis"), dict) else {}
    if block.get("pct_of_float") is not None:
        bad.append("pct_of_float is %r, not None" % (block.get("pct_of_float"),))
    if block.get("tier") is not None:
        bad.append("tier is %r, not None" % (block.get("tier"),))
    if basis.get("float_refused") not in ACCEPT_REFUSALS:
        bad.append("basis.float_refused is %r" % (basis.get("float_refused"),))
    keys = [f.get("key") for f in (basis.get("flags") or []) if isinstance(f, dict)]
    for k in ACCEPT_FLAGS:
        if k not in keys:
            bad.append("flag %s missing (flags %s)" % (k, keys))
    src = block.get("shares_source")
    if not (isinstance(src, str) and src.startswith("SEC")):
        bad.append("shares_source is %r" % (src,))
    si, so, ps = block.get("si_shares"), block.get("shares_outstanding"), block.get("pct_of_shares_out")
    if not (isinstance(si, (int, float)) and isinstance(so, (int, float)) and so > 0
            and ps == round(si / so * 100.0, 2)):
        bad.append("pct_of_shares_out %r != round(%r / %r * 100, 2)" % (ps, si, so))
    s = block.get("settlement_date")
    if isinstance(s, str) and s < ACCEPT_SHARES_BEFORE and so != ACCEPT_SHARES:
        bad.append("shares_outstanding %r != %d (settlement %s)" % (so, ACCEPT_SHARES, s))
    return bad


# ───────────────────────────────────────────── a seed track laid over the basis read, in memory only
class _OverlayColl:
    """The basis collection with seed tracks laid over names that hold none. Reads only; a write raises."""

    def __init__(self, coll, overlay: dict):
        self._c = coll
        self._o = overlay

    def _lay(self, doc, sym):
        seed = self._o.get(sym)
        if seed is None:
            return doc
        if doc is None:
            return {"_id": sym, "v": 1, "float_track": copy.deepcopy(seed)}
        if not doc.get("float_track"):
            d = dict(doc)
            d["float_track"] = copy.deepcopy(seed)
            return d
        return doc

    def find_one(self, flt=None, *a, **k):
        doc = self._c.find_one(flt, *a, **k) if self._c is not None else None
        sym = (flt or {}).get("_id") if isinstance(flt, dict) else None
        return self._lay(doc, sym) if isinstance(sym, str) else doc

    def find(self, flt=None, *a, **k):
        got = list(self._c.find(flt, *a, **k)) if self._c is not None else []
        ids = ((flt or {}).get("_id") or {}).get("$in") if isinstance((flt or {}).get("_id"), dict) else None
        seen = set()
        out = []
        for d in got:
            seen.add(d.get("_id"))
            out.append(self._lay(d, d.get("_id")))
        for sym in ids or []:
            if sym not in seen and sym in self._o:
                out.append(self._lay(None, sym))
        return out

    def __getattr__(self, name):
        if name in ("replace_one", "update_one", "insert_one", "insert_many", "update_many", "delete_one",
                    "delete_many", "bulk_write", "find_one_and_update"):
            raise RuntimeError("the probe never writes")
        return getattr(self._c, name)


class _OverlayDB:
    def __init__(self, db, coll_name: str, overlay: dict):
        self._db = db
        self._name = coll_name
        self._overlay = overlay

    def __getitem__(self, name):
        if name == self._name:
            return _OverlayColl(self._db[name] if self._db is not None else None, self._overlay)
        return self._db[name]

    def __getattr__(self, name):
        return getattr(self._db, name)


class _CaptureColl:
    """The basis collection for `share_basis.seed`: reads pass through, the seed's `$set.float_track` lands in a dict."""

    def __init__(self, coll, into: dict):
        self._c = coll
        self._into = into

    def find(self, *a, **k):
        return self._c.find(*a, **k) if self._c is not None else []

    def update_one(self, flt, upd, upsert=False):
        track = ((upd or {}).get("$set") or {}).get("float_track")
        if isinstance(flt, dict) and isinstance(flt.get("_id"), str) and isinstance(track, dict):
            self._into[flt["_id"]] = copy.deepcopy(track)

    def __getattr__(self, name):
        raise RuntimeError("the probe never writes (%s)" % name)


class _CaptureDB:
    def __init__(self, db, coll_name: str, into: dict):
        self._db = db
        self._name = coll_name
        self._into = into

    def __getitem__(self, name):
        if name == self._name:
            return _CaptureColl(self._db[name] if self._db is not None else None, self._into)
        return self._db[name]


def seed_tracks(seed: dict, symbols, db) -> dict:
    """{SYM: float_track} the REAL `share_basis.seed` would write for these names (its own rule: the live float equals
    the seed's, no earlier `since` held) — captured in memory, never written."""
    from short_interest import share_basis as SB
    rows = (seed or {}).get("rows") if isinstance(seed, dict) else None
    want = {str(s).upper() for s in symbols or []}
    rows = {str(k).upper(): v for k, v in (rows or {}).items() if str(k).upper() in want}
    out: dict = {}
    if rows:
        SB.seed(rows, db=_CaptureDB(db, SB.SB_COLL, out))
    return out


# ───────────────────────────────────────────── the run (injectable: the integration test drives it over a FakeDB)
@contextlib.contextmanager
def _mode(BM, mode: str):
    prior = BM.FLOAT_STALE_WHEN
    BM.FLOAT_STALE_WHEN = mode
    try:
        yield
    finally:
        BM.FLOAT_STALE_WHEN = prior


def _flag_keys(block) -> list:
    b = (block or {}).get("basis") if isinstance((block or {}).get("basis"), dict) else {}
    return [f.get("key") for f in (b.get("flags") or []) if isinstance(f, dict)]


def _refused(block):
    b = (block or {}).get("basis") if isinstance((block or {}).get("basis"), dict) else {}
    return b.get("float_refused")


def _clean(rec: dict, sym: str) -> dict:
    d = dict(rec)
    d.pop("age_days", None)
    d.pop("stale", None)
    d.setdefault("_id", sym)
    d.setdefault("symbol", sym)
    return d


def without_newer_float(bdoc: dict, rec: dict, held_track) -> dict:
    """The basis doc as the 11-24 check judged it: Yahoo's float removed (so `newer_float` finds none) and the track
    re-run on the SI record from the HELD track — the shape `share_basis.refresh_symbol` stored before 11-24 later."""
    from short_interest import basis_math as BM
    d = copy.deepcopy(bdoc)
    y = d.get("yahoo")
    if isinstance(y, dict):
        d["yahoo"] = dict(y, float_shares=None)
    sp = d.get("splits") if isinstance(d.get("splits"), dict) else {}
    rows = sp.get("rows") if sp.get("status") == "ok" else None
    try:
        d["float_track"] = BM.track_update(held_track, dict(rec), rows)
    except Exception:                                          # noqa: BLE001 — keep what is held
        d["float_track"] = held_track
    return d


def _listed(block, read_doc):
    """(listed, reason) on the 🩳 High SI sub's ONE membership function, or None with no stored read."""
    if not isinstance(read_doc, dict):
        return None
    from chart_maps.gajjala import high_si as HS
    from chart_maps.gajjala import tab as GT
    c = HS.classify(block, GT._float_read(read_doc, None))
    return [bool(c.get("listed")), c.get("reason")]


def run(symbols, *, db, now: datetime, today: date, seed: Optional[dict] = None,
        refresh: Optional[Callable] = None, reads: Optional[dict] = None) -> dict:
    """The probe's body: no write, no print. Returns the out dict (`smtk_failures` empty = the check holds).
    `reads` = {SYM: stored 🚩 Gajjala read doc} for the 🩳 High SI list membership before / now (optional)."""
    from short_interest import basis_math as BM
    from short_interest import client as C
    from short_interest import read as SR
    from short_interest import share_basis as SB

    syms = []
    for s in list(symbols or []) + [ACCEPT]:
        s = str(s or "").strip().upper()
        if s and s not in syms:
            syms.append(s)
    records = C.short_interest_map(syms, db=db) or {}
    tracks = seed_tracks(seed, syms, db) if seed else {}
    use_db = _OverlayDB(db, SB.SB_COLL, tracks) if tracks else db
    refresh = refresh or SB.refresh_symbol
    try:
        held_docs = SB.load(syms, use_db) or {}
    except Exception:                                          # noqa: BLE001
        held_docs = {}
    hi = (SR.TIER_HIGH, SR.TIER_EXTREME)

    lines, cases, per, newer = [], [], {}, {}
    for sym in syms:
        rec = records.get(sym)
        if rec is None:
            per[sym] = {"skipped": "no short-interest record"}
            continue
        doc = _clean(rec, sym)
        old = SR.si_block(copy.deepcopy(doc), today)
        try:
            bdoc = refresh(sym, use_db, now, store=False)
        except Exception as exc:                               # noqa: BLE001
            per[sym] = {"old": old, "error": type(exc).__name__}
            continue
        if not isinstance(bdoc, dict) or bdoc.get("skipped"):
            per[sym] = {"old": old, "skipped": (bdoc or {}).get("skipped") if isinstance(bdoc, dict) else "none"}
            continue
        new = SR.si_block(copy.deepcopy(doc), today, basis=bdoc)
        by_mode = {}
        for m in BM.FLOAT_STALE_MODES:
            with _mode(BM, m):
                bm = SR.si_block(copy.deepcopy(doc), today, basis=bdoc)
            by_mode[m] = {"refused": _refused(bm), "tier": (bm or {}).get("tier"), "chip": (bm or {}).get("chip")}
        basis = (new or {}).get("basis") or {}
        per[sym] = {"old": old, "new": new, "basis_doc": bdoc, "by_mode": by_mode}
        fu = basis.get("float_update")
        if isinstance(fu, dict):
            held_track = (held_docs.get(sym) or {}).get("float_track")
            before = SR.si_block(copy.deepcopy(doc), today, basis=without_newer_float(bdoc, doc, held_track))
            rd = (reads or {}).get(sym)
            newer[sym] = {"float_before": [fu.get("replaced_shares"), fu.get("replaced_asof")],
                          "float_now": [fu.get("shares"), fu.get("as_of")],
                          "pct_before": (before or {}).get("pct_of_float"), "pct_now": (new or {}).get("pct_of_float"),
                          "tier_before": (before or {}).get("tier"), "tier_now": (new or {}).get("tier"),
                          "refused_before": _refused(before), "refused_now": _refused(new),
                          "chip_before": (before or {}).get("chip"), "chip_now": (new or {}).get("chip"),
                          "high_before": (before or {}).get("tier") in hi, "high_now": (new or {}).get("tier") in hi,
                          "list_before": _listed(before, rd), "list_now": _listed(new, rd),
                          "flags_gained": sorted(set(_flag_keys(new)) - set(_flag_keys(before))),
                          "flags_lost": sorted(set(_flag_keys(before)) - set(_flag_keys(new)))}
        lines.append(" | ".join([sym, str((old or {}).get("chip")), str((new or {}).get("chip")),
                                 str(_refused(new)), ",".join(str(k) for k in _flag_keys(new)) or "-",
                                 json.dumps(basis.get("sources"), sort_keys=True, default=str)]))
        cases.append({"name": "%s_no_basis" % sym.lower(), "doc": doc, "block": old})
        cases.append({"name": "%s_basis" % sym.lower(), "doc": doc, "block": new})

    modes = {}
    for m in BM.FLOAT_STALE_MODES:
        refused = sorted(s for s, p in per.items() if (p.get("by_mode") or {}).get(m, {}).get("refused"))
        modes[m] = {"refused_n": len(refused), "refused": refused,
                    "untiered": sorted(s for s in refused if (per[s]["old"] or {}).get("tier")
                                       and not per[s]["by_mode"][m]["tier"])}
    tier_moves = {s: [(p["old"] or {}).get("tier"), (p["new"] or {}).get("tier")] for s, p in per.items()
                  if p.get("new") is not None and (p["old"] or {}).get("tier") != (p["new"] or {}).get("tier")}
    rebased = {}
    for s, p in per.items():
        ch = (((p.get("new") or {}).get("basis") or {}).get("change"))
        if isinstance(ch, dict):
            rebased[s] = {"served_before": (p["old"] or {}).get("si_change_pct"),
                          "now": (p["new"] or {}).get("si_change_pct"), "same_day": ch.get("same_day")}
    smtk = (per.get(ACCEPT) or {}).get("new")
    return {"run_at": now.astimezone(timezone.utc).isoformat(timespec="seconds"), "today": today.isoformat(),
            "built_mode": BM.FLOAT_STALE_WHEN, "names_n": len(syms), "seeded": sorted(tracks),
            "lines": lines, "by_mode": modes, "tier_changes": tier_moves, "change_rebased": rebased,
            "newer_float": newer,
            "newer_float_tier_changes": {s: [n["tier_before"], n["tier_now"]] for s, n in newer.items()
                                         if n["tier_before"] != n["tier_now"]},
            "newer_float_high": {"entering": sorted(s for s, n in newer.items() if n["high_now"] and not n["high_before"]),
                                 "leaving": sorted(s for s, n in newer.items() if n["high_before"] and not n["high_now"])},
            "newer_float_list": {s: [n["list_before"], n["list_now"]] for s, n in newer.items()
                                 if n["list_before"] is not None and n["list_before"] != n["list_now"]},
            "newer_float_flags_lost": {s: n["flags_lost"] for s, n in newer.items() if n["flags_lost"]},
            "smtk_failures": smtk_check(smtk), "per_name": per,
            "payload": {"today": today.isoformat(), "cases": cases}}


def session_reads(session: Optional[date] = None) -> dict:
    """{SYM: the 🩳 sub's stored read doc} for the session ({} on any fault) — the High SI list's input."""
    try:
        from chart_maps.gajjala import store as GS
        from chart_maps.gajjala import tab as GT
        sess = session or GT.session_for()[0]
        return {str(d.get("symbol")).upper(): d for d in GS.GajjalaStore().reads(sess) if d.get("symbol")}
    except Exception as exc:                                   # noqa: BLE001
        print("gajjala reads unavailable: %s" % type(exc).__name__, file=sys.stderr)
        return {}


def default_names(session: Optional[date] = None) -> list:
    """The 🩳 sub's stored reads for the session + the 👀 Watch owner list ([] on any fault)."""
    out = []
    try:
        from chart_maps.gajjala import store as GS
        from chart_maps.gajjala import tab as GT
        sess = session or GT.session_for()[0]
        out += [str(d.get("symbol")).upper() for d in GS.GajjalaStore().reads(sess) if d.get("symbol")]
    except Exception as exc:                                   # noqa: BLE001
        print("gajjala reads unavailable: %s" % type(exc).__name__, file=sys.stderr)
    try:
        from chart_maps.gajjala_watch import colls as WC
        doc = WC.owner_doc() or {}
        out += [str(s).upper() for s in (doc.get("symbols") or []) if s]
    except Exception as exc:                                   # noqa: BLE001
        print("watch list unavailable: %s" % type(exc).__name__, file=sys.stderr)
    seen = []
    for s in out:
        if s not in seen:
            seen.append(s)
    return seen


def _finite_json(o):
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {k: _finite_json(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_finite_json(v) for v in o]
    return o


def main(argv=None) -> int:
    from scripts.resiliency_study import ATTEMPTED, block_writes
    block_writes()                                   # FIRST: no write can land

    ap = argparse.ArgumentParser(description="Share-basis probe (read-only).")
    ap.add_argument("--symbols", default="", help="comma-separated; default = the 🩳 sub's reads + the 👀 Watch list")
    ap.add_argument("--seed", default=None, help="a `share_basis seed` input file, laid over in memory only")
    ap.add_argument("--out", default=".", help="output directory")
    args = ap.parse_args(argv)

    from massive_keys import stocks_key
    from short_interest import client as C

    key = stocks_key() or ""
    db = C._get_db()
    if db is None:
        print("no database", file=sys.stderr)
        return 1
    syms = [s for s in args.symbols.split(",") if s.strip()] or default_names()
    seed = json.loads(Path(args.seed).read_text(encoding="utf-8")) if args.seed else None
    now = datetime.now(timezone.utc)
    from chart_maps.gajjala import tab as GT
    today = GT._et(now).date()

    out = run(syms, db=db, now=now, today=today, seed=seed, reads=session_reads())
    out["attempted_writes"] = len(ATTEMPTED)
    out["attempted_write_methods"] = dict(collections.Counter(ATTEMPTED))
    payload = out.pop("payload")
    od = Path(args.out)
    od.mkdir(parents=True, exist_ok=True)
    (od / "si_share_basis_probe.json").write_text(
        _scrub(json.dumps(_finite_json(out), indent=1, ensure_ascii=False, default=str), key), encoding="utf-8")
    (od / "si_live_blocks.json").write_text(
        _scrub(json.dumps(_finite_json(payload), indent=1, ensure_ascii=False, default=str), key), encoding="utf-8")

    print(_scrub("SYM | old chip | new chip | refused | flags | sources", key))
    for ln in out["lines"]:
        print(_scrub(ln, key))
    print("\nbuilt mode: %s" % out["built_mode"])
    for m, s in out["by_mode"].items():
        print(_scrub("mode %-20s refused %3d: %s" % (m, s["refused_n"], " ".join(s["refused"])), key))
    print(_scrub("tier changes: %s" % json.dumps(out["tier_changes"], ensure_ascii=False), key))
    print(_scrub("change rebased across a split: %s" % json.dumps(out["change_rebased"], ensure_ascii=False), key))
    print("\nnewer Yahoo float (basis_math.newer_float): %d name(s)" % len(out["newer_float"]))
    for s, n in out["newer_float"].items():
        print(_scrub("%s | float %s (%s) -> %s (%s) | %% of float %s -> %s | tier %s -> %s | refused %s -> %s | "
                     "High SI list %s -> %s | %s" % (
                         s, n["float_before"][0], n["float_before"][1], n["float_now"][0], n["float_now"][1],
                         n["pct_before"], n["pct_now"], n["tier_before"], n["tier_now"], n["refused_before"],
                         n["refused_now"], n["list_before"], n["list_now"], n["chip_now"]), key))
    print(_scrub("newer-float tier changes: %s" % json.dumps(out["newer_float_tier_changes"], ensure_ascii=False), key))
    print(_scrub("newer-float High/EXTREME entering: %s · leaving: %s" % (
        " ".join(out["newer_float_high"]["entering"]) or "-", " ".join(out["newer_float_high"]["leaving"]) or "-"), key))
    print(_scrub("newer-float High SI list changes: %s" % json.dumps(out["newer_float_list"], ensure_ascii=False), key))
    print(_scrub("newer-float flags LOST (must be empty): %s" % json.dumps(out["newer_float_flags_lost"],
                                                                           ensure_ascii=False), key))
    print("attempted writes: %d" % out["attempted_writes"])
    if out["smtk_failures"]:
        print(_scrub("SMTK STRUCTURAL CHECK FAILED: %s" % "; ".join(out["smtk_failures"]), key))
        return 1
    print("SMTK structural check: holds")
    return 0


if __name__ == "__main__":                                  # pragma: no cover
    raise SystemExit(main())
