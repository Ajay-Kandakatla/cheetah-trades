"""🩳 6-K issuance phrase recall — the ship gate of the SEC full-text reader (READ-ONLY, re-runnable).

THE ASK (Ajay 2026-11-26, verbatim)
  "Fix the POM chip and the 6-K dilution check."

Spec `sishares` rev 2, §3.3 + §5.2b [C7]. Engine: backend/short_interest/sec_fts.py; doc:
docs/short_interest/sixk_issuance_2026_11_26.md.

The nine issuance phrases (`sec_fts.FTS_ISSUANCE_PHRASES`) were checked on ONE issuer (POM). This probe asks them of
every stored share-basis doc that is a foreign issuer with an offering on file — its `sec.filings` holds an F-
registration (F-1, F-3, …) or a 424B prospectus row — and prints, per name:
  the offering filings on file · the 6-Ks of the doc's own window (`sec.since` → today) · the 6-Ks the phrases hit;
then `asked / with a hit / with none` and the names with none. No window, tolerance or pass mark is invented: the
table goes to him as it reads.

Per name: ONE submissions GET (data.sec.gov) + ONE phrase query (efts.sec.gov), both through
`share_basis._sec_get` (the one pacer, the house's generic User-Agent — no contact, no e-mail). A name with no 6-K in
its window is listed and NOT asked. A 403 / 429 stops the probe (nothing is stored). Writes NOTHING (no Mongo write,
no file).

  --max N        required — how many names to read this run (a probe size, never a rule)
  --symbols A,B  only these names

Run only in a throwaway container with the worktree mounted (never the live api / cron containers):
  docker run --rm --cpus 2 --memory 3g --network cheetah-market-app_default \\
    -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah -e TZ=America/New_York \\
    -e PYTHONPATH=/app -e PYTHONDONTWRITEBYTECODE=1 \\
    -v <worktree>/backend:/app:ro -w /app \\
    cheetah-api:latest python -u /app/scripts/si_fts_recall_probe.py --max 40
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from typing import Optional

from short_interest import sec_fts as SF
from short_interest import share_basis as SB


def _base(form) -> str:
    b = form.strip().upper() if isinstance(form, str) else ""
    return b[:-2].strip() if b.endswith("/A") else b


def offerings(doc) -> list:
    """The F- registration / 424B rows of a stored basis doc's `sec.filings` ([(form, filed)], as stored)."""
    sec = doc.get("sec") if isinstance(doc, dict) and isinstance(doc.get("sec"), dict) else {}
    out = []
    for f in sec.get("filings") or []:
        if not isinstance(f, dict) or not isinstance(f.get("form"), str):
            continue
        b = _base(f["form"])
        if b.startswith("F-") or b.startswith("424B"):
            out.append((f["form"].strip(), f.get("filed")))
    return out


def candidates(docs) -> list:
    """[(sym, cik10, since, offerings)] A–Z: a stored doc with a CIK, a window and an offering row on file."""
    out = []
    for d in docs:
        if not isinstance(d, dict) or not isinstance(d.get("_id"), str) or d["_id"].startswith("state|"):
            continue
        ref = d.get("ref") if isinstance(d.get("ref"), dict) else {}
        cik = SB._cik10(ref.get("cik"))
        since = SB._day((d.get("sec") or {}).get("since")) if isinstance(d.get("sec"), dict) else None
        offs = offerings(d)
        if cik and since and offs:
            out.append((d["_id"].upper(), cik, since, offs))
    return sorted(out)


def _docs(db, symbols) -> list:
    if symbols:
        return list(SB.load(symbols, db).values())
    return list(db[SB.SB_COLL].find({}))


def run(db, *, max_names: int, symbols=None, http=None, now: Optional[datetime] = None, out=print) -> dict:
    now = SB._now(now)
    today = SF.et_day(now)
    get = (lambda url: SB._sec_get(url, http))
    names = candidates(_docs(db, SB._clean(symbols) if symbols else None))[:max_names]
    res = {"read": 0, "asked": 0, "hit": [], "none": [], "no_6k": [], "failed": [], "stopped": None}
    out("probe %s ET · %d names (of the stored docs with an F- / 424B row on file; --max %d)"
        % (today, len(names), max_names))
    for sym, cik, since, offs in names:
        res["read"] += 1
        got = SB.fetch_filings(cik, since, http=http, kind_fn=lambda form, items: None)
        if got.get("status") != "ok":
            res["failed"].append(sym)
            out("%-6s | submissions %s" % (sym, got.get("error")))
            if got.get("blocked"):
                res["stopped"] = got.get("error")
                break
            continue
        reports = got.get("reports") or []
        off_txt = ", ".join("%s %s" % (f, d) for f, d in offs)
        if not reports:
            res["no_6k"].append(sym)
            out("%-6s | offerings %s | 6-Ks since %s: none — not asked" % (sym, off_txt, since))
            continue
        r = SF.read_issuance(cik, since, today, reports, get=get)
        res["asked"] += 1
        if r.get("status") != "ok":
            res["failed"].append(sym)
            out("%-6s | offerings %s | %d 6-Ks since %s | full-text %s" % (sym, off_txt, len(reports), since,
                                                                          r.get("error")))
            if r.get("code") in SB.SEC_BLOCK_HTTP:
                res["stopped"] = r.get("error")
                break
            continue
        hits = r.get("issuance") or []
        (res["hit"] if hits else res["none"]).append(sym)
        out("%-6s | offerings %s | 6-Ks since %s: %s | phrases hit: %s%s" % (
            sym, off_txt, since, ", ".join(x["filed"] for x in reports),
            ", ".join("%s %s" % (x["form"], x["filed"]) for x in hits) or "none",
            " (answer capped at %d rows)" % r["cap"] if r.get("cap") else ""))
    out("asked %d / with a hit %d / with none %d · no 6-K in window %d · failed %d%s"
        % (res["asked"], len(res["hit"]), len(res["none"]), len(res["no_6k"]), len(res["failed"]),
           (" · STOPPED on %s" % res["stopped"]) if res["stopped"] else ""))
    out("names with none: %s" % (", ".join(res["none"]) or "—"))
    return res


def main(argv=None, *, db=None, http=None, now=None) -> int:
    ap = argparse.ArgumentParser(prog="si_fts_recall_probe.py", description="6-K issuance phrase recall (read-only).")
    ap.add_argument("--max", type=int, required=True, dest="max_names")
    ap.add_argument("--symbols")
    a = ap.parse_args(argv)
    if a.max_names <= 0:
        print("--max must be a positive number of names")
        return 2
    d = db if db is not None else SB._default_db()
    if d is None:
        print("no database")
        return 2
    syms = a.symbols.split(",") if a.symbols else None
    run(d, max_names=a.max_names, symbols=syms, http=http, now=now or datetime.now(timezone.utc))
    return 0


if __name__ == "__main__":                                     # pragma: no cover
    sys.exit(main())
