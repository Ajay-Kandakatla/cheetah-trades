"""⛔ SSR — official vs computed agreement for ONE trigger day. READ-ONLY.

Ajay 2026-11-23: "No shorting at the bid (SEC short-sale restriction) Can we check or this for other stocks too?"
This is the re-runnable accuracy table behind any SSR number quoted to him (spec §4 W1 step 6, §5 step 6). It reads
the `ssr_rule_201` collection only (`find_one` / `find`; no write of any kind, no outside call) and prints, for the
trigger day asked:

  * official N (Nasdaq file(D) ∪ file(next market day) rows dated D, ∪ NYSE Group file(D)) · computed N (live trig
    docs of D) · both · official-only (the recall misses, by name) · computed-only
  * recall = both / official and precision = both / computed, each with a Wilson 95% interval — never one figure
  * computed-only split into dividend-or-split names (corp|D) and the rest
  * separately: the void docs (bars_disagree), the `late_print` names of judged|D, the dividend / split names
  * whether each exchange's record of D is complete (Nasdaq needs file(next market day); NYSE needs file(D))

Run it in the api container (after the next morning's Nasdaq file):

    docker exec -i -w /app cheetah-market-app-api-1 python scripts/ssr_agreement.py 2026-11-23
"""
from __future__ import annotations

import math
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from short_interest import client as SIC  # noqa: E402
from short_interest import reg_sho as RS  # noqa: E402
from short_interest import ssr as SSR  # noqa: E402

Z95 = 1.959964                     # the normal 97.5% quantile — a two-sided 95% interval


def wilson(k: int, n: int) -> str:
    if n <= 0:
        return "n/a (n = 0)"
    p = k / n
    den = 1 + Z95 * Z95 / n
    mid = (p + Z95 * Z95 / (2 * n)) / den
    half = Z95 * math.sqrt(p * (1 - p) / n + Z95 * Z95 / (4 * n * n)) / den
    return "%d / %d = %.1f%% (95%% CI %.1f–%.1f%%)" % (k, n, 100 * p, 100 * max(0.0, mid - half),
                                                      100 * min(1.0, mid + half))


def dash(sym: str) -> str:
    norm = RS.norm_symbol(sym)
    return RS.alias_keys(norm)[-1] if norm else ""


def suffixed(sym: str) -> bool:
    """A class / warrant / right / preferred suffix after a separator ("BRK.B", "BIII.WS", "AHT PRD")."""
    return "." in RS.norm_symbol(sym)


def spelling_index(names) -> dict:
    """{spelling: name} over the union of `SSR._spellings` of every name (the first name keeps a spelling)."""
    out: dict = {}
    for n in names:
        for k in SSR._spellings(n):
            out.setdefault(k, n)
    return out


def lookup(sym: str, index: dict):
    """The indexed name `sym` matches on ANY of its spellings, or None — "BIII.WS" finds "BIII-WS"."""
    for k in SSR._spellings(sym):
        if k in index:
            return index[k]
    return None


def one_per_name(syms) -> list:
    """De-duplicate by spelling: two trig docs "BIII.WS" and "BIII-WS" are ONE name (the first sorted kept)."""
    out, idx = [], {}
    for s in sorted(syms):
        if lookup(s, idx) is None:
            out.append(s)
            idx.update(spelling_index([s]))
    return out


def official_rows(coll, d: date) -> tuple:
    """({dash symbol: [source]}, completeness notes)."""
    from catalysts.medical.reaction import next_market_day
    iso, nxt = d.isoformat(), next_market_day(d).isoformat()
    out: dict = {}
    notes = []
    for src, fdate in (("nasdaq", iso), ("nasdaq", nxt), ("nyse", iso)):
        doc = coll.find_one({"_id": "list|%s|%s" % (src, fdate)})
        notes.append("%s file %s: %s" % (src, fdate, ("held, stamp %s, %s rows" % (doc.get("stamp"), doc.get("n")))
                                         if doc else "NOT held"))
        for r in (doc or {}).get("rows") or []:
            if len(r) >= 2 and str(r[1]) == iso:
                out.setdefault(dash(r[0]), set()).add(src)
    complete = (coll.find_one({"_id": "list|nasdaq|%s" % nxt}) is not None
                and coll.find_one({"_id": "list|nyse|%s" % iso}) is not None)
    return out, notes, complete


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: python scripts/ssr_agreement.py YYYY-MM-DD")
        return 2
    d = date.fromisoformat(argv[1])
    iso = d.isoformat()
    db = SIC._get_db()
    if db is None:
        print("Mongo is not reachable (MONGO_URL=%s)" % os.getenv("MONGO_URL", "mongodb://localhost:27017"))
        return 1
    coll = db["ssr_rule_201"]
    off, notes, complete = official_rows(coll, d)
    trigs = list(coll.find({"kind": "trig", "date": iso}))
    live = {t["symbol"] for t in trigs if t.get("symbol") and not t.get("void")}
    void = sorted(t["symbol"] for t in trigs if t.get("symbol") and t.get("void"))
    by_basis: dict = {}
    for t in trigs:
        if t.get("symbol") and not t.get("void"):
            by_basis[t.get("basis")] = by_basis.get(t.get("basis"), 0) + 1
    judged = coll.find_one({"_id": "judged|%s" % iso}) or {}
    late = sorted(s for s, w in (judged.get("unjudged") or {}).items() if w == "late_print")
    corp = coll.find_one({"_id": "corp|%s" % iso})
    divs = {str(r[0]) for r in (corp or {}).get("dividends") or [] if r}
    splits = {str(r[0]) for r in (corp or {}).get("splits") or [] if r}
    offic = set(off)
    live_names = one_per_name(live)
    off_idx = spelling_index(sorted(offic))
    match = {s: lookup(s, off_idx) for s in live_names}          # computed name → its official name, or None
    both = {o for o in match.values() if o is not None}           # official names a computed name matched
    off_only = sorted(offic - both)
    comp_only = sorted(s for s in live_names if match[s] is None)
    corp_idx = spelling_index(sorted(divs | splits))
    comp_only_corp = [s for s in comp_only if lookup(s, corp_idx) is not None]
    comp_only_rest = [s for s in comp_only if lookup(s, corp_idx) is None]

    print("⛔ SSR agreement for trigger day %s (READ-ONLY)" % iso)
    for n in notes:
        print("  " + n)
    print("  both exchange records of %s complete: %s" % (iso, "yes" if complete else "NO — numbers are provisional"))
    print("  corporate actions of %s: %s" % (iso, ("read — %d dividend names, %d split names" % (len(divs), len(splits)))
                                            if corp else "NOT read"))
    print()
    print("| official | computed | both | official-only | computed-only |")
    print("|---|---|---|---|---|")
    print("| %d | %d | %d | %d | %d |" % (len(offic), len(live_names), len(both), len(off_only), len(comp_only)))
    print()
    print("names match on ANY spelling (BIII.WS = BIII-WS = BIII WS); computed counts names, not docs (%d live docs)"
          % len(live))
    print("computed by basis: %s" % (", ".join("%s %d" % (k, v) for k, v in sorted(by_basis.items(), key=str)) or "—"))
    print("recall    (official names the computed read caught): %s" % wilson(len(both), len(offic)))
    print("precision (computed names on an official list):      %s" % wilson(len(both), len(live_names)))
    print()
    print("| symbols | official | computed | both | official-only | computed-only |")
    print("|---|---|---|---|---|---|")
    for label, want in (("plain", False), ("suffixed", True)):
        o_n = sum(1 for o in offic if suffixed(o) == want)
        c_n = sum(1 for s in live_names if suffixed(s) == want)
        b_n = sum(1 for o in both if suffixed(o) == want)
        print("| %s | %d | %d | %d | %d | %d |" % (label, o_n, c_n, b_n, o_n - b_n,
                                                 sum(1 for s in comp_only if suffixed(s) == want)))
    for label, want in (("plain", False), ("suffixed", True)):
        o_n = sum(1 for o in offic if suffixed(o) == want)
        c_n = sum(1 for s in live_names if suffixed(s) == want)
        b_o = sum(1 for o in both if suffixed(o) == want)
        b_c = sum(1 for s in live_names if match[s] is not None and suffixed(s) == want)
        print("%-8s recall %s · precision %s" % (label, wilson(b_o, o_n), wilson(b_c, c_n)))
    print()
    print("official-only (recall misses, %d): %s" % (len(off_only), " ".join(off_only) or "—"))
    print("computed-only, dividend or split names (%d): %s" % (len(comp_only_corp), " ".join(comp_only_corp) or "—"))
    print("computed-only, the rest (%d): %s" % (len(comp_only_rest), " ".join(comp_only_rest) or "—"))
    print("void docs (bars_disagree, %d): %s" % (len(void), " ".join(void) or "—"))
    print("late_print names (%d): %s" % (len(late), " ".join(late) or "—"))
    print("dividend names (%d) · split names (%d): %s | %s" % (len(divs), len(splits), " ".join(sorted(divs)) or "—",
                                                             " ".join(sorted(splits)) or "—"))
    print()
    print("One trigger day; the listing exchange decides. UNMEASURED beyond the days this script has been run on.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
