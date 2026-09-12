"""negbase.py — the negative-base problem on the /breakouts board, MEASURED.

RUN (the Massive key exists ONLY in the api container; a throwaway container
silently falls back to Yahoo and prints false negatives):

    cd /Users/ajay/clinet-test/cheetah-market-app && \
      docker compose exec -T api python - < /tmp/scratch/qoq/negbase.py

What it does
------------
1. Pulls the LIVE /breakouts board (stages=False so every stage shows, which is
   what Ajay asked for on 2026-09-12).
2. For every name, fetches the same 8-quarter Massive financials the CANSLIM
   layer already fetches (canslim._fetch_massive_financials) and keeps the
   quarterly series that `_from_hybrid` currently throws away:
       rev_q_series / eps_q_series / ni_q_series   (newest-first, index 0 = Q0)
3. Counts the sign of the PRIOR quarter (Q1) — the denominator of any sequential
   QoQ percentage — for EPS, net income and revenue.
4. Ranks the board on the raw sequential % and reports how much of the top 20 is
   bought by a non-positive / near-zero base.
5. Scores the candidate rules and prints a bootstrap CI on the headline rates.

Read-only. Writes nothing outside /tmp.
"""
from __future__ import annotations

import json
import math
import os
import random
from concurrent.futures import ThreadPoolExecutor

CACHE = "/tmp/qoq_series_cache.json"
TOP_N = 20
random.seed(20260912)


# ── 1. the live board ────────────────────────────────────────────────────────
def board_rows():
    from sepa import breakout
    b = breakout.board(top=250, min_count=1, stages=False)
    return b["rows"]


# ── 2. the quarterly series the research cache does not keep ─────────────────
def fetch_series(sym: str):
    from sepa import canslim
    try:
        m = canslim._fetch_massive_financials(sym) or {}
    except Exception as exc:                                    # noqa: BLE001
        return {"err": repr(exc)}
    return {
        "rev": m.get("rev_q_series") or [],
        "eps": m.get("eps_q_series") or [],
        "ni":  m.get("ni_q_series") or [],
        "rev_yoy": m.get("rev_growth_q_pct"),
        "eps_yoy": m.get("q_eps_growth_pct"),
    }


def load_series(syms):
    cache = {}
    if os.path.exists(CACHE):
        try:
            cache = json.load(open(CACHE))
        except Exception:                                       # noqa: BLE001
            cache = {}
    todo = [s for s in syms if s not in cache]
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for s, r in zip(todo, ex.map(fetch_series, todo)):
                cache[s] = r
        json.dump(cache, open(CACHE, "w"))
    return cache


# ── helpers ──────────────────────────────────────────────────────────────────
def pair(series):
    """(Q0, Q1) when both are real numbers, else None."""
    if not series or len(series) < 2:
        return None
    a, b = series[0], series[1]
    if a is None or b is None:
        return None
    try:
        return float(a), float(b)
    except (TypeError, ValueError):
        return None


def raw_pct(p):
    """The naive sequential % every ranking would use: (Q0-Q1)/|Q1|."""
    if p is None:
        return None
    q0, q1 = p
    if q1 == 0:
        return None
    return (q0 - q1) / abs(q1) * 100.0


def sign_bucket(p):
    if p is None:
        return "n/a"
    q1 = p[1]
    if q1 < 0:
        return "neg"
    if q1 == 0:
        return "zero"
    return "pos"


def fmt(x, nd=2):
    return "—" if x is None else f"{x:,.{nd}f}"


def boot_ci(hits, n, reps=4000):
    """Bootstrap 95% CI on a proportion — the house rule is that no rate on a
    board he trades ships as a bare point estimate."""
    if n == 0:
        return (None, None)
    data = [1] * hits + [0] * (n - hits)
    out = []
    for _ in range(reps):
        out.append(sum(random.choice(data) for _ in range(n)) / n)
    out.sort()
    return (out[int(.025 * reps)] * 100, out[int(.975 * reps)] * 100)


# ── main ─────────────────────────────────────────────────────────────────────
def main():
    rows = board_rows()
    syms = [r["symbol"] for r in rows]
    by_sym = {r["symbol"]: r for r in rows}
    print(f"live /breakouts board (stages=False): {len(syms)} names\n")

    ser = load_series(syms)
    have = [s for s in syms if ser.get(s) and not ser[s].get("err")]
    print(f"Massive financials returned for {len(have)}/{len(syms)}\n")

    rec = {}
    for s in have:
        d = ser[s]
        rec[s] = {
            "rev": pair(d["rev"]), "eps": pair(d["eps"]), "ni": pair(d["ni"]),
            "rev_yoy": d.get("rev_yoy"), "eps_yoy": d.get("eps_yoy"),
            "rev_series": d["rev"], "eps_series": d["eps"], "ni_series": d["ni"],
            "cap": by_sym[s].get("market_cap"),
            "stage": by_sym[s].get("stage"),
            "explosive": by_sym[s].get("explosive"),
            "price": by_sym[s].get("price") or by_sym[s].get("last"),
        }

    # ---- Q1: sign of the prior-quarter base -------------------------------
    print("=" * 78)
    print("Q1  SIGN OF THE PRIOR QUARTER (Q1) — the denominator of sequential %")
    print("=" * 78)
    print(f"{'metric':<10}{'neg':>7}{'zero':>7}{'pos':>7}{'n/a':>7}{'covered':>9}"
          f"{'%non-pos of covered':>22}")
    for key, label in (("eps", "EPS"), ("ni", "net income"), ("rev", "revenue")):
        b = {"neg": 0, "zero": 0, "pos": 0, "n/a": 0}
        for s in have:
            b[sign_bucket(rec[s][key])] += 1
        cov = b["neg"] + b["zero"] + b["pos"]
        share = (b["neg"] + b["zero"]) / cov * 100 if cov else 0
        lo, hi = boot_ci(b["neg"] + b["zero"], cov)
        print(f"{label:<10}{b['neg']:>7}{b['zero']:>7}{b['pos']:>7}{b['n/a']:>7}"
              f"{cov:>9}{share:>13.1f}%  [{lo:.1f},{hi:.1f}]")

    # near-zero bases blow up too even when positive
    print("\nNEAR-ZERO positive bases (|Q1| small enough to explode the ratio):")
    for key, label, thr in (("eps", "EPS", 0.10), ("eps", "EPS", 0.05)):
        n = sum(1 for s in have
                if rec[s][key] and rec[s][key][1] > 0 and abs(rec[s][key][1]) < thr)
        print(f"  {label} with 0 < Q1 < ${thr:.2f}: {n}")

    # ---- Q2/Q3: who wins a raw sequential ranking? ------------------------
    for key, label, unit in (("eps", "EPS", "$/sh"), ("ni", "NET INCOME", "$")):
        print()
        print("=" * 78)
        print(f"Q{'2' if key=='eps' else '3'}  TOP {TOP_N} RANKED ON RAW SEQUENTIAL {label} % — (Q0-Q1)/|Q1|")
        print("=" * 78)
        scored = [(s, raw_pct(rec[s][key])) for s in have if raw_pct(rec[s][key]) is not None]
        scored.sort(key=lambda t: -t[1])
        top = scored[:TOP_N]
        nbad = 0
        div = 1e6 if key == "ni" else 1.0
        sfx = "M" if key == "ni" else ""
        print(f"{'#':<4}{'sym':<7}{'raw %':>12}  {'Q1':>12}  {'Q0':>12}  base  "
              f"{label.lower()} yoy   stage")
        for i, (s, p) in enumerate(top, 1):
            q0, q1 = rec[s][key]
            bk = sign_bucket(rec[s][key])
            tiny = bk == "pos" and abs(q1) < 0.10 and key == "eps"
            flag = {"neg": "NEG", "zero": "ZERO", "pos": "pos"}[bk] + ("*tiny" if tiny else "")
            if bk in ("neg", "zero") or tiny:
                nbad += 1
            yoy = rec[s]["eps_yoy"] if key == "eps" else None
            print(f"{i:<4}{s:<7}{p:>12,.1f}  {q1/div:>11,.2f}{sfx}  {q0/div:>11,.2f}{sfx}  "
                  f"{flag:<10}{fmt(yoy,1):>9}   {rec[s]['stage']}")
        lo, hi = boot_ci(nbad, TOP_N)
        print(f"\n  -> {nbad}/{TOP_N} of the top {TOP_N} are bought by a "
              f"non-positive (or near-zero) base  [{lo:.0f}%,{hi:.0f}% CI]")

        # what a profitable-grower ranking looks like for contrast
        clean = [(s, p) for s, p in scored if sign_bucket(rec[s][key]) == "pos"
                 and not (key == "eps" and abs(rec[s][key][1]) < 0.10)]
        print(f"  -> best RAW % among positive-base names: "
              + ", ".join(f"{s} {p:,.1f}%" for s, p in clean[:5]))
        print(f"  -> median raw % among positive-base names: "
              f"{sorted(p for _, p in clean)[len(clean)//2]:,.1f}%  (n={len(clean)})")

    # ---- Q4: are the negative-base winners real turnarounds? --------------
    print()
    print("=" * 78)
    print("Q4  WHAT THE NEGATIVE-BASE WINNERS ACTUALLY LOOK LIKE (full EPS series,")
    print("    newest-first Q0..Q7) — real turnaround vs noise")
    print("=" * 78)
    scored = [(s, raw_pct(rec[s]["eps"])) for s in have if raw_pct(rec[s]["eps"]) is not None]
    scored.sort(key=lambda t: -t[1])
    shown = 0
    for s, p in scored:
        if sign_bucket(rec[s]["eps"]) == "pos" and abs(rec[s]["eps"][1]) >= 0.10:
            continue
        q0, q1 = rec[s]["eps"]
        eq = rec[s]["eps_series"][:8]
        ni = rec[s]["ni_series"][:4]
        rv = rec[s]["rev_series"][:4]
        n_neg = sum(1 for v in eq if v is not None and v < 0)
        verdict = []
        verdict.append("Q0>0" if q0 > 0 else "Q0 STILL NEGATIVE")
        verdict.append(f"{n_neg}/{len([v for v in eq if v is not None])} qtrs negative")
        if rv and rv[0] is not None and len(rv) > 1 and rv[1]:
            verdict.append(f"rev qoq {(rv[0]-rv[1])/abs(rv[1])*100:+.1f}%")
        # scaled alternative: absolute EPS change as a share of |Q0 revenue/share|
        print(f"\n  {s}  raw sequential EPS {p:+,.1f}%   base={sign_bucket(rec[s]['eps'])}")
        print(f"      EPS Q0..Q7 : " + ", ".join(fmt(v) for v in eq))
        print(f"      NI  Q0..Q3 : " + ", ".join(fmt(v/1e6, 1) + 'M' if v is not None else '—' for v in ni))
        print(f"      REV Q0..Q3 : " + ", ".join(fmt(v/1e6, 1) + 'M' if v is not None else '—' for v in rv))
        print(f"      read       : " + "; ".join(verdict))
        shown += 1
        if shown >= 8:
            break

    # ---- how the candidate rules re-order the board -----------------------
    print()
    print("=" * 78)
    print("RULE BAKE-OFF — top 10 under each candidate")
    print("=" * 78)

    def r_raw(s, key="eps"):
        return raw_pct(rec[s][key])

    def r_posbase(s, key="eps"):
        """A: % only when Q1 > 0; everything else is NOT-COMPARABLE (own lane)."""
        p = rec[s][key]
        if p is None or p[1] <= 0:
            return None
        return raw_pct(p)

    def r_latest_positive(s, key="eps"):
        """C: turnaround credit only once Q0 itself is positive."""
        p = rec[s][key]
        if p is None or p[0] <= 0:
            return None
        return raw_pct(p) if p[1] > 0 else None

    def r_margin_delta(s):
        """D: net-margin change in POINTS — defined at any sign, bounded, and
        comparable across a profitable grower and a turnaround."""
        ni, rv = rec[s]["ni"], rec[s]["rev"]
        if ni is None or rv is None or rv[0] <= 0 or rv[1] <= 0:
            return None
        return (ni[0] / rv[0] - ni[1] / rv[1]) * 100.0

    def r_capped(s, key="eps", cap=100.0):
        p = raw_pct(rec[s][key])
        return None if p is None else max(-cap, min(cap, p))

    for name, fn in (("A raw %", lambda s: r_raw(s)),
                     ("B positive-base only", r_posbase),
                     ("C Q0>0 required", r_latest_positive),
                     ("D net-margin Δ (pts)", r_margin_delta),
                     ("E capped at ±100%", r_capped)):
        sc = [(s, fn(s)) for s in have]
        sc = [(s, v) for s, v in sc if v is not None]
        sc.sort(key=lambda t: -t[1])
        bad = sum(1 for s, _ in sc[:10]
                  if rec[s]["eps"] and (rec[s]["eps"][1] <= 0 or abs(rec[s]["eps"][1]) < 0.10))
        print(f"\n  {name:<24} n={len(sc):<4} neg/tiny-base in top10: {bad}/10")
        print("    " + "  ".join(f"{s}:{v:,.1f}" for s, v in sc[:10]))

    # ---- the recommended composite, shown end to end ----------------------
    print()
    print("=" * 78)
    print("RECOMMENDED RULE, APPLIED — positive-base lane vs TURNAROUND lane")
    print("=" * 78)
    main_lane, turn, notcomp = [], [], []
    for s in have:
        e = rec[s]["eps"]
        if e is None:
            notcomp.append((s, "no 2 quarters"))
        elif e[1] > 0 and abs(e[1]) >= 0.10:
            main_lane.append((s, raw_pct(e)))
        elif e[0] > 0 >= e[1]:
            turn.append((s, e))
        else:
            notcomp.append((s, f"Q1={fmt(e[1])} Q0={fmt(e[0])}"))
    main_lane.sort(key=lambda t: -t[1])
    print(f"  RANKED lane (Q1>0, |Q1|>=$0.10): n={len(main_lane)}")
    print("    " + "  ".join(f"{s}:{v:,.1f}%" for s, v in main_lane[:12]))
    print(f"\n  TURNAROUND lane (Q1<=0 AND Q0>0 — flagged, never ranked on %): n={len(turn)}")
    print("    " + "  ".join(f"{s}({fmt(e[1])}->{fmt(e[0])})" for s, e in turn[:12]))
    print(f"\n  NOT COMPARABLE (no credit, sorts LAST): n={len(notcomp)}")
    print("    " + "  ".join(f"{s}" for s, _ in notcomp[:20]))


if __name__ == "__main__":
    main()


# ─────────────────────────────────────────────────────────────────────────────
# PART 2 — materiality, ETF contamination, and the scaled alternatives.
# Appended after the first run: the headline finding was that requiring a
# POSITIVE base does not fix the ranking (a $0.01–$0.09 base explodes it just as
# hard), so the base has to be material, not merely positive.
# ─────────────────────────────────────────────────────────────────────────────
def part2():
    rows = board_rows()
    syms = [r["symbol"] for r in rows]
    by = {r["symbol"]: r for r in rows}
    ser = load_series(syms)
    have = [s for s in syms if ser.get(s) and not ser[s].get("err")]

    P = {}
    for s in have:
        d = ser[s]
        P[s] = {"rev": pair(d["rev"]), "eps": pair(d["eps"]), "ni": pair(d["ni"]),
                "etf": bool(by[s].get("is_etf")), "px": by[s].get("last_close"),
                "stage": by[s].get("stage"), "rev_series": d["rev"]}

    print("\n" + "=" * 78)
    print("P2-a  WHO IS IN THE NON-POSITIVE REVENUE BUCKET")
    print("=" * 78)
    neg_rev = [s for s in have if P[s]["rev"] and P[s]["rev"][1] < 0]
    zero_rev = [s for s in have if P[s]["rev"] and P[s]["rev"][1] == 0]
    na_rev = [s for s in have if P[s]["rev"] is None]
    print(f"  revenue Q1 < 0 : {len(neg_rev)}  {neg_rev}")
    print(f"  revenue Q1 = 0 : {len(zero_rev)}  {zero_rev}")
    print(f"  revenue n/a    : {len(na_rev)}  ETFs among them: "
          f"{sum(1 for s in na_rev if P[s]['etf'])}")
    print(f"  ETFs on the board overall: {sum(1 for s in have if P[s]['etf'])}/{len(have)}")
    print(f"  EPS n/a that are ETFs: "
          f"{sum(1 for s in have if P[s]['eps'] is None and P[s]['etf'])}"
          f" of {sum(1 for s in have if P[s]['eps'] is None)}")

    print("\n" + "=" * 78)
    print("P2-b  MATERIALITY SWEEP — |Q1 EPS| floor vs junk in the top 20")
    print("=" * 78)
    print(f"{'rule':<34}{'n ranked':>10}{'top20 w/ |Q1|<$0.10':>22}{'max %':>12}")
    for label, keep in (
        ("Q1 != 0 (raw)",            lambda p: p[1] != 0),
        ("Q1 > 0",                   lambda p: p[1] > 0),
        ("Q1 > 0 and |Q1| >= $0.05", lambda p: p[1] >= 0.05),
        ("Q1 > 0 and |Q1| >= $0.10", lambda p: p[1] >= 0.10),
        ("Q1 > 0 and |Q1| >= $0.25", lambda p: p[1] >= 0.25),
        ("Q1 > 0 and |Q1| >= 0.5% px", lambda p: p[1] > 0),   # px handled below
    ):
        sc = []
        for s in have:
            p = P[s]["eps"]
            if p is None:
                continue
            if label.endswith("0.5% px"):
                px = P[s]["px"]
                if not px or p[1] < 0.005 * px:
                    continue
            elif not keep(p):
                continue
            v = raw_pct(p)
            if v is not None:
                sc.append((s, v))
        sc.sort(key=lambda t: -t[1])
        tiny = sum(1 for s, _ in sc[:20] if abs(P[s]["eps"][1]) < 0.10)
        mx = sc[0][1] if sc else float("nan")
        print(f"{label:<34}{len(sc):>10}{tiny:>22}{mx:>12,.0f}")

    print("\n" + "=" * 78)
    print("P2-c  SCALED ALTERNATIVES — defined at ANY sign, no denominator blow-up")
    print("=" * 78)

    def d_eps_yield(s):
        """ΔEPS / price, in percentage points of quarterly earnings yield.
        Sign-agnostic: works from -0.50 -> -0.05 and from 2.00 -> 2.40 alike."""
        p, px = P[s]["eps"], P[s]["px"]
        if p is None or not px or px <= 0:
            return None
        return (p[0] - p[1]) / px * 100.0

    def d_margin(s):
        """Δ net margin in points, denominator = Q1 revenue (needs real revenue)."""
        ni, rv = P[s]["ni"], P[s]["rev"]
        if ni is None or rv is None or rv[0] <= 0 or rv[1] <= 0:
            return None
        return (ni[0] / rv[0] - ni[1] / rv[1]) * 100.0

    def d_ni_over_rev(s):
        """ΔNI / Q1 revenue — same denominator both sides, bounded by revenue."""
        ni, rv = P[s]["ni"], P[s]["rev"]
        if ni is None or rv is None or rv[1] <= 0:
            return None
        return (ni[0] - ni[1]) / rv[1] * 100.0

    for nm, fn in (("ΔEPS / price (pts)", d_eps_yield),
                   ("Δ net margin (pts)", d_margin),
                   ("ΔNI / Q1 revenue (pts)", d_ni_over_rev)):
        sc = [(s, fn(s)) for s in have]
        sc = [(s, v) for s, v in sc if v is not None]
        sc.sort(key=lambda t: -t[1])
        negb = sum(1 for s, _ in sc[:15] if P[s]["eps"] and P[s]["eps"][1] <= 0)
        etfs = sum(1 for s, _ in sc[:15] if P[s]["etf"])
        print(f"\n  {nm:<26} n={len(sc):<4} top15: neg-base {negb}, ETF {etfs}")
        print("    " + "  ".join(f"{s}:{v:,.1f}" for s, v in sc[:15]))

    print("\n" + "=" * 78)
    print("P2-d  RECOMMENDED RULE — three lanes, materiality floor on the base")
    print("=" * 78)
    FLOOR = 0.10          # $/share; ALSO require |Q1| >= 0.25% of price
    ranked, turn, notcomp = [], [], []
    for s in have:
        e, px = P[s]["eps"], P[s]["px"]
        floor = max(FLOOR, 0.0025 * px) if px else FLOOR
        if e is None:
            notcomp.append((s, "fewer than 2 filed quarters" + (" (ETF)" if P[s]["etf"] else "")))
        elif e[1] >= floor:
            ranked.append((s, raw_pct(e)))
        elif e[0] > 0 and e[1] <= 0:
            turn.append((s, e))
        else:
            notcomp.append((s, f"base immaterial Q1={fmt(e[1])} (floor {floor:.2f})"))
    ranked.sort(key=lambda t: -t[1])
    print(f"  LANE 1 RANKED  n={len(ranked)}  (Q1 >= max($0.10, 0.25% of price))")
    for i, (s, v) in enumerate(ranked[:20], 1):
        e = P[s]["eps"]
        print(f"    {i:>2} {s:<6} {v:>9,.1f}%   {e[1]:>7.2f} -> {e[0]:>7.2f}   stage {P[s]['stage']}")
    print(f"\n  LANE 2 TURNAROUND (flagged 🔄, never ranked on %)  n={len(turn)}")
    for s, e in sorted(turn, key=lambda t: -(t[1][0])):
        print(f"       {s:<6} {e[1]:>7.2f} -> {e[0]:>7.2f}")
    print(f"\n  LANE 3 NOT COMPARABLE (sorts LAST, prints —)  n={len(notcomp)}")
    from collections import Counter
    c = Counter("ETF / no filings" if "ETF" in r else
                ("no 2 quarters" if "quarters" in r else "immaterial base")
                for _, r in notcomp)
    print(f"       {dict(c)}")
    print("       immaterial-base names: " +
          ", ".join(s for s, r in notcomp if "immaterial" in r)[:400])

    # stability: does the ranked lane's order survive a one-quarter shift?
    print("\n" + "=" * 78)
    print("P2-e  STABILITY — same rule one quarter back (Q1 vs Q2), overlap of top 20")
    print("=" * 78)
    prev = []
    for s in have:
        d = ser[s]["eps"]
        if not d or len(d) < 3 or d[1] is None or d[2] is None:
            continue
        px = P[s]["px"]
        floor = max(FLOOR, 0.0025 * px) if px else FLOOR
        if float(d[2]) < floor:
            continue
        prev.append((s, (float(d[1]) - float(d[2])) / abs(float(d[2])) * 100))
    prev.sort(key=lambda t: -t[1])
    a = {s for s, _ in ranked[:20]}
    b = {s for s, _ in prev[:20]}
    print(f"  top20 now n={len(a)}, top20 one quarter back n={len(b)}, overlap={len(a & b)}")
    print(f"  carried over: {sorted(a & b)}")

    # raw-% equivalent stability, for contrast
    raw_now = sorted(((s, raw_pct(P[s]['eps'])) for s in have if raw_pct(P[s]['eps']) is not None),
                     key=lambda t: -t[1])[:20]
    raw_prev = []
    for s in have:
        d = ser[s]["eps"]
        if not d or len(d) < 3 or d[1] is None or d[2] is None or float(d[2]) == 0:
            continue
        raw_prev.append((s, (float(d[1]) - float(d[2])) / abs(float(d[2])) * 100))
    raw_prev.sort(key=lambda t: -t[1])
    ra, rb = {s for s, _ in raw_now}, {s for s, _ in raw_prev[:20]}
    print(f"  RAW %% top20 overlap quarter-to-quarter: {len(ra & rb)}  -> {sorted(ra & rb)}")


if __name__ == "__main__":
    part2()


# ─────────────────────────────────────────────────────────────────────────────
# PART 3 — is a flat $0.10 floor share-count-biased?  Does a NI floor do better?
# And how persistent is ANY sequential ranking quarter to quarter?
# ─────────────────────────────────────────────────────────────────────────────
def part3():
    rows = board_rows()
    syms = [r["symbol"] for r in rows]
    by = {r["symbol"]: r for r in rows}
    ser = load_series(syms)
    have = [s for s in syms if ser.get(s) and not ser[s].get("err")]

    def g(s, k):
        return pair(ser[s][k])

    print("\n" + "=" * 78)
    print("P3-a  THE 17 LEGIT-BUT-SUB-$0.10 POSITIVE EPS BASES — real or micro-profit?")
    print("=" * 78)
    print(f"{'sym':<7}{'Q1 eps':>9}{'Q0 eps':>9}{'raw %':>11}{'Q1 NI':>12}{'Q1 rev':>12}  etf")
    n_big = 0
    for s in have:
        e = g(s, "eps")
        if not e or not (0 < e[1] < 0.10):
            continue
        ni, rv = g(s, "ni"), g(s, "rev")
        ni1 = ni[1] / 1e6 if ni else None
        rv1 = rv[1] / 1e6 if rv else None
        if ni1 is not None and abs(ni1) >= 50:
            n_big += 1
        print(f"{s:<7}{e[1]:>9.2f}{e[0]:>9.2f}{raw_pct(e):>11,.0f}"
              f"{fmt(ni1,1) + 'M':>12}{fmt(rv1,1) + 'M':>12}  {by[s].get('is_etf')}")
    print(f"\n  of these, {n_big} have |Q1 net income| >= $50M  ->  a sub-$0.10 EPS base "
          f"on a large-NI name is a SHARE-COUNT artifact, not a small business")

    print("\n" + "=" * 78)
    print("P3-b  NET-INCOME MATERIALITY FLOOR (size-relative, share-count immune)")
    print("=" * 78)
    print(f"{'rule':<40}{'n ranked':>10}{'max %':>12}{'top5':>8}")
    def ni_rank(keep):
        sc = []
        for s in have:
            ni, rv = g(s, "ni"), g(s, "rev")
            if ni is None:
                continue
            if not keep(ni, rv):
                continue
            v = raw_pct(ni)
            if v is not None:
                sc.append((s, v))
        sc.sort(key=lambda t: -t[1])
        return sc
    for label, keep in (
        ("NI Q1 != 0 (raw)",              lambda ni, rv: ni[1] != 0),
        ("NI Q1 > 0",                     lambda ni, rv: ni[1] > 0),
        ("NI Q1 > 0 and >= 1% of Q1 rev", lambda ni, rv: ni[1] > 0 and rv and rv[1] > 0 and ni[1] >= .01 * rv[1]),
        ("NI Q1 > 0 and >= 2% of Q1 rev", lambda ni, rv: ni[1] > 0 and rv and rv[1] > 0 and ni[1] >= .02 * rv[1]),
        ("NI Q1 > 0 and >= 5% of Q1 rev", lambda ni, rv: ni[1] > 0 and rv and rv[1] > 0 and ni[1] >= .05 * rv[1]),
    ):
        sc = ni_rank(keep)
        print(f"{label:<40}{len(sc):>10}{(sc[0][1] if sc else float('nan')):>12,.0f}   "
              + ", ".join(s for s, _ in sc[:5]))

    print("\n" + "=" * 78)
    print("P3-c  PERSISTENCE — does a sequential ranking mean anything next quarter?")
    print("     (rank on Q1-vs-Q2, then look at where those names land on Q0-vs-Q1)")
    print("=" * 78)

    def seq(s, i, j, floor=0.0):
        d = ser[s]["eps"]
        if not d or len(d) <= j or d[i] is None or d[j] is None:
            return None
        a, b = float(d[i]), float(d[j])
        if b <= floor or b == 0:
            return None
        return (a - b) / abs(b) * 100

    for lbl, fl in (("raw (any non-zero base)", None), ("base >= $0.10", 0.10)):
        prev = [(s, seq(s, 1, 2, fl if fl else -1e18)) for s in have]
        prev = [(s, v) for s, v in prev if v is not None]
        now = {s: seq(s, 0, 1, fl if fl else -1e18) for s in have}
        prev.sort(key=lambda t: -t[1])
        topq = [s for s, _ in prev[:20]]
        follow = [now[s] for s in topq if now.get(s) is not None]
        rest = [v for s, v in ((s, now[s]) for s in have)
                if v is not None and s not in set(topq)]
        med_f = sorted(follow)[len(follow) // 2] if follow else float("nan")
        med_r = sorted(rest)[len(rest) // 2] if rest else float("nan")
        up = sum(1 for v in follow if v > 0)
        up_r = sum(1 for v in rest if v > 0)
        lo, hi = boot_ci(up, len(follow)) if follow else (0, 0)
        lo2, hi2 = boot_ci(up_r, len(rest)) if rest else (0, 0)
        print(f"\n  {lbl}")
        print(f"    last quarter's top-20 -> this quarter median seq %: {med_f:,.1f}  "
              f"(n={len(follow)});  still positive {up}/{len(follow)} = "
              f"{up/len(follow)*100:.0f}%  [{lo:.0f},{hi:.0f}]")
        print(f"    PLACEBO everyone else -> median seq %: {med_r:,.1f}  (n={len(rest)});  "
              f"still positive {up_r}/{len(rest)} = {up_r/len(rest)*100:.0f}%  [{lo2:.0f},{hi2:.0f}]")

    print("\n" + "=" * 78)
    print("P3-d  DOES THE $0.10 FLOOR COST THE AI-SECTOR NAMES HE RANKS FIRST?")
    print("=" * 78)
    ai = [s for s in have if by[s].get("ai_sector")]
    keptai = [s for s in ai if g(s, "eps") and g(s, "eps")[1] >= 0.10]
    print(f"  AI-sector names on the board: {len(ai)}")
    print(f"  ... with a material (>= $0.10) positive EPS base: {len(keptai)}")
    print(f"  ... dropped to turnaround/not-comparable: "
          + ", ".join(s for s in ai if s not in keptai)[:500])


if __name__ == "__main__":
    part3()


# ─────────────────────────────────────────────────────────────────────────────
# PART 4 — SEASONALITY.  Minervini uses Q-vs-same-Q-prior-year specifically to
# neutralise it.  Does sequential QoQ actually carry a calendar signature on
# THIS board?  Test: correlate a name's sequential % at step t with the SAME
# fiscal transition one year earlier (t+4) vs the ADJACENT transition (t+1).
# If sequential is a calendar effect, t~t+4 correlates and t~t+1 does not.
# ─────────────────────────────────────────────────────────────────────────────
FP_CACHE = "/tmp/qoq_fp_cache.json"


def fetch_fp(sym):
    import requests
    from massive_keys import stocks_key
    try:
        r = requests.get("https://api.massive.com/vX/reference/financials",
                         params={"ticker": sym.upper(), "limit": 12,
                                 "timeframe": "quarterly", "apiKey": stocks_key()},
                         timeout=15)
        if r.status_code != 200:
            return {"err": r.status_code}
        res = r.json().get("results") or []
        out = []
        for q in res:
            fin = (q.get("financials") or {}).get("income_statement") or {}
            def val(k):
                try:
                    v = fin.get(k, {}).get("value")
                    return float(v) if v is not None else None
                except (TypeError, ValueError):
                    return None
            out.append({"fp": q.get("fiscal_period"), "fy": q.get("fiscal_year"),
                        "end": q.get("end_date"),
                        "eps": val("diluted_earnings_per_share"),
                        "rev": val("revenues")})
        return {"q": out}
    except Exception as exc:                                    # noqa: BLE001
        return {"err": repr(exc)}


def part4():
    rows = board_rows()
    syms = [r["symbol"] for r in rows]
    cache = {}
    if os.path.exists(FP_CACHE):
        try:
            cache = json.load(open(FP_CACHE))
        except Exception:                                       # noqa: BLE001
            cache = {}
    todo = [s for s in syms if s not in cache]
    if todo:
        with ThreadPoolExecutor(max_workers=8) as ex:
            for s, r in zip(todo, ex.map(fetch_fp, todo)):
                cache[s] = r
        json.dump(cache, open(FP_CACHE, "w"))

    ok = [s for s in syms if cache.get(s) and cache[s].get("q")]
    print("\n" + "=" * 78)
    print("P4  SEASONALITY — is sequential QoQ a calendar effect?")
    print("=" * 78)
    print(f"  names with >=12 quarters of filings: "
          f"{sum(1 for s in ok if len(cache[s]['q']) >= 12)}")

    def seqs(s, key):
        q = cache[s]["q"]
        out = []
        for i in range(len(q) - 1):
            a, b = q[i].get(key), q[i + 1].get(key)
            if a is None or b is None or b <= 0:
                out.append(None)
            else:
                out.append((a - b) / abs(b) * 100)
        return out

    def spear(xs, ys):
        pts = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
        n = len(pts)
        if n < 12:
            return None, n
        def ranks(v):
            order = sorted(range(len(v)), key=lambda i: v[i])
            r = [0.0] * len(v)
            for pos, i in enumerate(order):
                r[i] = pos + 1
            return r
        rx, ry = ranks([p[0] for p in pts]), ranks([p[1] for p in pts])
        mx, my = sum(rx) / n, sum(ry) / n
        num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
        return (num / den if den else None), n

    for key, lbl in (("eps", "EPS"), ("rev", "REVENUE")):
        same_x, same_y, adj_x, adj_y = [], [], [], []
        for s in ok:
            sq = seqs(s, key)
            if len(sq) >= 9:
                if sq[0] is not None and sq[4] is not None:      # same fiscal transition, 1yr back
                    same_x.append(sq[0]); same_y.append(sq[4])
                if sq[0] is not None and sq[1] is not None:      # adjacent transition
                    adj_x.append(sq[0]); adj_y.append(sq[1])
        rs, ns = spear(same_x, same_y)
        ra, na = spear(adj_x, adj_y)
        print(f"\n  {lbl} sequential %:")
        print(f"    Spearman(this transition, SAME transition 1yr earlier) = "
              f"{fmt(rs,3)}  (n={ns})")
        print(f"    Spearman(this transition, ADJACENT transition)          = "
              f"{fmt(ra,3)}  (n={na})")

    # median sequential % by fiscal-period transition — the calendar signature
    print("\n  Median sequential % by fiscal-period transition (all names, all steps):")
    from collections import defaultdict
    buck = defaultdict(list)
    for s in ok:
        q = cache[s]["q"]
        for i in range(len(q) - 1):
            a, b = q[i].get("rev"), q[i + 1].get("rev")
            fp0, fp1 = q[i].get("fp"), q[i + 1].get("fp")
            if a is None or b is None or b <= 0 or not fp0 or not fp1:
                continue
            buck[f"{fp1}->{fp0}"].append((a - b) / abs(b) * 100)
    print(f"    {'transition':<14}{'n':>6}{'median rev seq %':>20}{'%negative':>12}")
    for k in sorted(buck, key=lambda k: -len(buck[k]))[:8]:
        v = sorted(buck[k])
        if len(v) < 20:
            continue
        neg = sum(1 for x in v if x < 0) / len(v) * 100
        print(f"    {k:<14}{len(v):>6}{v[len(v)//2]:>20,.1f}{neg:>11.0f}%")
    print("\n    ^ if these medians differ materially by transition, the sequential %"
          "\n      is partly a CALENDAR read, which is exactly what Minervini's"
          "\n      quarter-vs-same-quarter-prior-year construction removes.")


if __name__ == "__main__":
    part4()


# ─────────────────────────────────────────────────────────────────────────────
# PART 5 — the recommended rule, final form, with the calendar handicap sized.
# ─────────────────────────────────────────────────────────────────────────────
def part5():
    rows = board_rows()
    syms = [r["symbol"] for r in rows]
    by = {r["symbol"]: r for r in rows}
    cache = json.load(open(FP_CACHE))
    ser = load_series(syms)
    ok = [s for s in syms if cache.get(s) and cache[s].get("q") and len(cache[s]["q"]) >= 2]

    print("\n" + "=" * 78)
    print("P5-a  WHICH FISCAL TRANSITION IS EACH BOARD NAME CURRENTLY REPORTING?")
    print("     (the calendar handicap, applied to the LIVE board)")
    print("=" * 78)
    from collections import Counter, defaultdict
    tr = {}
    for s in ok:
        q = cache[s]["q"]
        if q[0].get("fp") and q[1].get("fp"):
            tr[s] = f"{q[1]['fp']}->{q[0]['fp']}"
    c = Counter(tr.values())
    seqrev = {}
    for s in ok:
        q = cache[s]["q"]
        a, b = q[0].get("rev"), q[1].get("rev")
        if a is not None and b is not None and b > 0:
            seqrev[s] = (a - b) / abs(b) * 100
    print(f"    {'transition':<12}{'names':>7}{'median live rev seq %':>24}")
    for k, n in c.most_common(6):
        v = sorted(seqrev[s] for s in tr if tr[s] == k and s in seqrev)
        if not v:
            continue
        print(f"    {k:<12}{n:>7}{v[len(v)//2]:>24,.1f}")
    print("\n    -> names in a seasonally weak transition are penalised by the sort"
          "\n       for a reason that has nothing to do with the business.")

    print("\n" + "=" * 78)
    print("P5-b  FINAL RECOMMENDED SHAPE — EPS, flat $0.10 material-base floor")
    print("=" * 78)
    ranked, turn, notcomp = [], [], []
    for s in syms:
        d = ser.get(s) or {}
        e = pair(d.get("eps") or [])
        if e is None:
            notcomp.append((s, "ETF / <2 filed quarters" if by[s].get("is_etf") else "<2 filed quarters"))
        elif e[1] >= 0.10:
            ranked.append((s, raw_pct(e), e))
        elif e[0] > 0 and e[1] <= 0:
            turn.append((s, e))
        else:
            notcomp.append((s, f"immaterial base Q1={fmt(e[1])}"))
    ranked.sort(key=lambda t: -t[1])
    print(f"  LANE 1  RANKED        n={len(ranked)}")
    print(f"  LANE 2  TURNAROUND 🔄  n={len(turn)}   (Q1<=0 AND Q0>0; shown, never % -ranked)")
    print(f"  LANE 3  NOT COMPARABLE n={len(notcomp)}  (prints —, sorts LAST)")
    print(f"\n  {'#':<4}{'sym':<7}{'seq %':>9}{'Q1':>8}{'Q0':>8}{'yoy eps %':>12}"
          f"{'transition':>12}  stage")
    for i, (s, v, e) in enumerate(ranked[:20], 1):
        print(f"  {i:<4}{s:<7}{v:>9,.1f}{e[1]:>8.2f}{e[0]:>8.2f}"
              f"{fmt((ser[s] or {}).get('eps_yoy'),1):>12}{tr.get(s,'—'):>12}  {by[s].get('stage')}")
    both = [s for s, _, _ in ranked[:20] if (ser[s] or {}).get("eps_yoy") is not None]
    agree = [s for s in both if (ser[s]["eps_yoy"] or 0) > 0]
    lo, hi = boot_ci(len(agree), len(both))
    print(f"\n  of the top 20 ranked names, {len(agree)}/{len(both)} ALSO have positive YoY EPS"
          f"  [{lo:.0f}%,{hi:.0f}% CI]  -> the two reads mostly agree at the top;"
          f"\n  the disagreements are where the negative/immaterial base was hiding.")

    print(f"\n  LANE 2 detail ({len(turn)}):")
    for s, e in sorted(turn, key=lambda t: -t[1][0]):
        yy = (ser[s] or {}).get("eps_yoy")
        print(f"    {s:<6} {e[1]:>7.2f} -> {e[0]:>7.2f}   yoy eps {fmt(yy,1):>9}   "
              f"stage {by[s].get('stage')}")


if __name__ == "__main__":
    part5()


# ═════════════════════════════════════════════════════════════════════════════
# HEADLINE RESULTS — live /breakouts board, 250 names, 2026-09-12
# (board refreshes hourly; re-run before quoting any of these)
#
#  BASE SIGN (covered names)
#    EPS         73 neg /  6 zero / 138 pos /  33 n/a  -> 36.4% non-positive [30.4,42.9]
#    net income  83 neg /  0 zero / 150 pos /  17 n/a  -> 35.6% non-positive [29.2,42.1]
#    revenue      0 neg /  5 zero / 226 pos /  19 n/a  ->  2.2% non-positive [0.4,4.3]
#    ALSO: 19 names have 0 < Q1 EPS < $0.10  (13 under $0.05)
#
#  RAW SEQUENTIAL EPS TOP 20 -> 11/20 bought by a non-positive OR sub-$0.10 base
#    [35,75] CI.  9 of those 11 are tiny-POSITIVE, not negative.
#    Median raw % among material positive-base names: +20.6% (n=119).
#
#  RAW SEQUENTIAL NET INCOME TOP 20 -> only 1/20 negative-base [0,15], BUT the
#    tiny-base blow-up is WORSE in dollars: DBRG +11,652% off $2.02M,
#    ATRC +8,192% off $0.11M, MNTK +4,420% off $0.01M.
#
#  RULE BAKE-OFF (top-10 contamination)
#    raw %                 7/10   |  Q1>0 only            7/10  (top-10 IDENTICAL)
#    Q0>0 required         7/10   |  net-margin Δ         9/10  (crypto treasuries)
#    cap ±100%             4/10   (and 10-way tie at 100.0 -> order falls through)
#    Q1 >= $0.10           0/20   max drops 4,040% -> 968%, 119 names survive
#
#  PERSISTENCE (the reason this is a column, not a sort key)
#    last quarter's sequential top-20 -> this quarter: median +0.4%, 50% still
#    positive [25,70];  PLACEBO everyone else: median +24.0%, 70% positive [61,79].
#
#  SEASONALITY (the Minervini tension, measured)
#    revenue seq % vs SAME fiscal transition 1yr earlier  rho=0.376 (n=148)
#    revenue seq % vs ADJACENT transition                 rho=0.023 (n=144)
#    EPS seq % vs ADJACENT transition                     rho=-0.477 (n=61)  [mean reversion]
#    median revenue seq % by transition: Q1->Q2 +5.3% (31% neg) vs
#      Q4->Q1 -4.0% (63% neg)  -> ~9pp handicap from the calendar alone.
# ═════════════════════════════════════════════════════════════════════════════
