"""/breakouts: what the board BECOMES with the stage gate OFF and the ranking
driven by quarter-over-quarter income (EPS) + growth (sales) instead of recency.

READ-ONLY measurement. Figures in the report were taken from the 2026-09-12
scan (scan_ts 1789158697, 2,945 scan rows, 2,840 breakout candidates).

MUST RUN INSIDE THE api CONTAINER — the Massive key exists nowhere else, and a
throwaway container silently falls back to Yahoo and produces false negatives:

    cd /Users/ajay/clinet-test/cheetah-market-app \
      && docker compose exec -T api python - < /tmp/scratch/qoq/composition.py

TRAP THIS SCRIPT ALREADY HIT: a first pass at 16 workers "fetched 250 symbols in
1.7s" and reported 0/800 names with fundamentals. Those were unlogged 429s, not
missing data. Every fetch below is status-accounted and retried — if the printed
status counter is not ~all 200, the numbers are garbage, do not quote them.

Sections:
  1  stage composition of the 250 shown rows and the 2,840 pre-cut candidates
  2  stage mix of TOP 20 / TOP 50 under three candidate income+growth rankings
  3  do declining (S3/S4) names with great trailing quarters reach the top?
  4  rows with NO fundamentals — how many, and where they land
  5  does dropping the gate change WHICH names survive the top=250 cut?
  6  how stale is the fundamental that would do the ranking
  7  negative / near-zero base artifacts in the QoQ growth formula
  8  sequential vs YoY — the Minervini seasonality guard he gives up
  9  a protected variant: positive base + YoY agreement
 10  is the recency cut hiding better growers? (sampled, 95% CI)
 11  what ranking on fundamentals costs the "recent breakout" read
"""
from __future__ import annotations

import datetime as dt
import math
import random
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor

import requests

from massive_keys import stocks_key
from sepa import breakout as B, scanner

BASE = "https://api.massive.com/vX/reference/financials"
KEY = stocks_key()
TODAY = dt.date(2026, 9, 12)
_tl = threading.local()
STATUS = Counter()
_lk = threading.Lock()


# ------------------------------------------------------------------ fetch ---
def _sess():
    if not hasattr(_tl, "s"):
        _tl.s = requests.Session()
    return _tl.s


def _iv(rep, key):
    try:
        v = ((rep.get("financials") or {}).get("income_statement") or {}).get(key, {}).get("value")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def _g(cur, prev):
    """Percent change with an abs() denominator — the SAME formula canslim uses
    (_compute_q_eps_growth). Returns (pct, prev_was_negative): with a negative
    base the number is a sign artefact, not a growth rate, so the caller has to
    be told."""
    if cur is None or prev is None or prev == 0:
        return None, False
    return round((cur - prev) / abs(prev) * 100, 2), (prev < 0)


def quarters(sym):
    """8 newest-first quarterly reports for one symbol, straight from Massive.
    Retries 429 with backoff; every status code is counted."""
    q = None
    for attempt in range(5):
        try:
            r = _sess().get(BASE, params={"ticker": sym, "limit": 8,
                                          "timeframe": "quarterly", "apiKey": KEY},
                            timeout=15)
        except Exception:                                       # noqa: BLE001
            with _lk:
                STATUS["exc"] += 1
            time.sleep(1.0 + attempt)
            continue
        with _lk:
            STATUS[r.status_code] += 1
        if r.status_code == 429:
            time.sleep(2.0 + 2 * attempt)
            continue
        if r.status_code != 200:
            return sym, {"ok": False, "http": r.status_code}
        q = (r.json() or {}).get("results") or []
        break
    if q is None:
        return sym, {"ok": False, "http": "429-exhausted"}

    rev = [_iv(x, "revenues") for x in q]
    eps = [_iv(x, "diluted_earnings_per_share") for x in q]
    rq, _ = _g(rev[0], rev[1]) if len(rev) >= 2 else (None, False)
    eq, eneg = _g(eps[0], eps[1]) if len(eps) >= 2 else (None, False)
    ry, _ = _g(rev[0], rev[4]) if len(rev) >= 5 else (None, False)
    ey, _ = _g(eps[0], eps[4]) if len(eps) >= 5 else (None, False)
    return sym, {"ok": True, "n_q": len(q),
                 "period": f"{(q[0] or {}).get('fiscal_period')} {(q[0] or {}).get('fiscal_year')}" if q else None,
                 "end": (q[0] or {}).get("end_date") if q else None,
                 "rev_qoq": rq, "eps_qoq": eq, "rev_yoy": ry, "eps_yoy": ey,
                 "eneg": eneg,
                 "rev_q1": rev[1] if len(rev) > 1 else None,
                 "eps_q1": eps[1] if len(eps) > 1 else None}


def fetch(syms, workers=6):
    t0 = time.time()
    with ThreadPoolExecutor(max_workers=workers) as ex:
        out = dict(ex.map(quarters, syms))
    ok = sum(1 for v in out.values() if v.get("ok"))
    print("    fetched %d in %.0fs  ok=%d  status=%s"
          % (len(syms), time.time() - t0, ok, dict(STATUS)))
    STATUS.clear()
    return out


def pct_rank(pop, v):
    return None if (v is None or not pop) else sum(1 for x in pop if x < v) / len(pop)


def mix(rs):
    return dict(sorted(Counter(("S%d" % r["stage"]) if r.get("stage") is not None
                               else "unknown" for r in rs).items()))


def wilson(k, n):
    if n == 0:
        return (0.0, 0.0)
    ph, z = k / n, 1.96
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (round(100 * max(0.0, c - h), 1), round(100 * (c + h), 1))


# ==================================================== 1. stage composition ===
print("=" * 82)
print("1. STAGE COMPOSITION — gate OFF")
print("=" * 82)
scan = scanner.load_latest() or {}
cands = []
for r in scan.get("all_results") or []:
    v = r.get("volume") or {}
    bc = v.get("breakout_count")
    if bc is None or int(bc) < 1:
        continue
    st = r.get("stage") or {}
    cands.append({"symbol": (r.get("symbol") or "").upper(),
                  "stage": st.get("stage") if isinstance(st, dict) else None,
                  "dsb": v.get("days_since_breakout")})
print("scan_ts=%s scan_rows=%d  pre-cut candidates (breakout_count>=1)=%d"
      % (scan.get("generated_at"), len(scan.get("all_results") or []), len(cands)))
print("  candidate stage mix:", mix(cands))

off = B.board(top=250, stages=False)
on = B.board(top=250, stages=True)
rows = off["rows"]
print("\nboard(stages=False): n=%d n_all=%d capped=%s" % (off["n"], off["n_all"], off["capped"]))
print("  stage mix of the 250 SHOWN:", mix(rows))
print("board(stages=True):  n=%d n_all=%d n_prestage=%d dropped=%d"
      % (on["n"], on["n_all"], on["n_prestage"], on["n_stage_dropped"]))
print("  stage mix of the 250 SHOWN:", mix(on["rows"]))
print("  -> Stage 4 reaching the board: %d    Stage 3: %d    (S3+S4 = %d of 250)"
      % (sum(1 for r in rows if r.get("stage") == 4),
         sum(1 for r in rows if r.get("stage") == 3),
         sum(1 for r in rows if r.get("stage") in (3, 4))))
print("  ETFs admitted with the gate OFF: %d (%s) — inverse/bear funds included"
      % (sum(1 for r in rows if r.get("is_etf")),
         ", ".join(r["symbol"] for r in rows if r.get("is_etf"))))

# ================================================== fundamentals for the 250 =
print("\n" + "=" * 82)
print("2. THE NEW RANKING — income (EPS QoQ) + growth (sales QoQ)")
print("=" * 82)
print("board 250 fetch:")
fund = fetch([r["symbol"] for r in rows])
for r in rows:
    r["f"] = fund.get(r["symbol"]) or {}
    e = r["f"].get("end")
    if e:
        try:
            lag = (TODAY - dt.date(*map(int, e.split("-")))).days
            if 0 < lag < 2000:
                r["lag"] = lag
        except Exception:                                       # noqa: BLE001
            pass
print("  coverage over the 250: rev_qoq=%d eps_qoq=%d rev_yoy=%d eps_yoy=%d"
      % (sum(1 for r in rows if r["f"].get("rev_qoq") is not None),
         sum(1 for r in rows if r["f"].get("eps_qoq") is not None),
         sum(1 for r in rows if r["f"].get("rev_yoy") is not None),
         sum(1 for r in rows if r["f"].get("eps_yoy") is not None)))

pe = [r["f"]["eps_qoq"] for r in rows if r["f"].get("eps_qoq") is not None]
prv = [r["f"]["rev_qoq"] for r in rows if r["f"].get("rev_qoq") is not None]
for r in rows:
    a, b = pct_rank(pe, r["f"].get("eps_qoq")), pct_rank(prv, r["f"].get("rev_qoq"))
    # percentile blend: 50% income, 50% sales. Missing EITHER leg => UNRANKED,
    # sorts LAST. An unknown must never win a sort.
    r["blend"] = None if (a is None or b is None) else 0.5 * a + 0.5 * b
    v = [x for x in (r["f"].get("eps_qoq"), r["f"].get("rev_qoq")) if x is not None]
    r["raw"] = sum(v) / len(v) if v else None       # the naive blend a shipper reaches for

ranked = sorted([r for r in rows if r["blend"] is not None], key=lambda r: -r["blend"])
unranked = [r for r in rows if r["blend"] is None]
order = ranked + unranked
raw_order = (sorted([r for r in rows if r["raw"] is not None], key=lambda r: -r["raw"])
             + [r for r in rows if r["raw"] is None])
inc_order = (sorted([r for r in rows if r["f"].get("eps_qoq") is not None],
                    key=lambda r: -r["f"]["eps_qoq"])
             + [r for r in rows if r["f"].get("eps_qoq") is None])
RK = {r["symbol"]: i + 1 for i, r in enumerate(order)}
RR = {r["symbol"]: i + 1 for i, r in enumerate(raw_order)}
RI = {r["symbol"]: i + 1 for i, r in enumerate(inc_order)}

print("  ranked (both legs)=%d   unranked=%d" % (len(ranked), len(unranked)))
for nm, O in (("percentile blend", order), ("naive raw average", raw_order),
              ("income (EPS QoQ) only", inc_order)):
    print("  %-22s TOP20=%s  TOP50=%s" % (nm, mix(O[:20]), mix(O[:50])))


def show(rs, n, title):
    print("\n" + title)
    print("%3s %-7s %4s %10s %9s %10s %9s %4s %8s  flags"
          % ("#", "sym", "stg", "epsQoQ%", "revQoQ%", "epsYoY%", "revYoY%", "dsb", "quarter"))
    for i, r in enumerate(rs[:n], 1):
        f = r["f"]
        fm = lambda v: ("%.1f" % v) if v is not None else "--"       # noqa: E731
        fl = []
        if f.get("eneg"):
            fl.append("PRIOR-Q-EPS<0")
        if r.get("stage") in (3, 4):
            fl.append("STAGE-%d" % r["stage"])
        if r.get("decision") in ("AVOID", "CUT"):
            fl.append(r["decision"])
        print("%3d %-7s %4s %10s %9s %10s %9s %4s %8s  %s"
              % (i, r["symbol"], r.get("stage"), fm(f.get("eps_qoq")), fm(f.get("rev_qoq")),
                 fm(f.get("eps_yoy")), fm(f.get("rev_yoy")),
                 r.get("days_since_breakout"), f.get("period"), " ".join(fl)))


show(order, 25, "TOP 25 under the percentile income+growth QoQ blend")

# ================================================= 3. the Stage-4 question ===
print("\n" + "=" * 82)
print("3. DO DECLINING NAMES WITH GREAT TRAILING QUARTERS REACH THE TOP?")
print("=" * 82)
for cut in (20, 50, 100):
    seg = order[:cut]
    print("  top %3d: S3+S4=%d (%.0f%%)  S4 alone=%d"
          % (cut, sum(1 for r in seg if r.get("stage") in (3, 4)),
             100 * sum(1 for r in seg if r.get("stage") in (3, 4)) / cut,
             sum(1 for r in seg if r.get("stage") == 4)))

print("\n  EVERY Stage-4 row on the board and where it ranks under each ordering:")
print("  %-7s %6s %6s %6s %10s %9s %10s %9s %4s %8s %-11s"
      % ("sym", "blend", "raw", "inc", "epsQoQ%", "revQoQ%", "epsYoY%", "revYoY%",
         "rs", "decision", "quarter-end"))
for r in sorted([x for x in rows if x.get("stage") == 4], key=lambda x: RK[x["symbol"]]):
    f = r["f"]
    fm = lambda v: ("%.1f" % v) if v is not None else "--"           # noqa: E731
    print("  %-7s %6d %6d %6d %10s %9s %10s %9s %4s %8s %-11s%s"
          % (r["symbol"], RK[r["symbol"]], RR[r["symbol"]], RI[r["symbol"]],
             fm(f.get("eps_qoq")), fm(f.get("rev_qoq")), fm(f.get("eps_yoy")),
             fm(f.get("rev_yoy")), r.get("rs_rank"), r.get("decision"), f.get("end"),
             "  PRIOR-Q-EPS<0" if f.get("eneg") else ""))
print("\n  best Stage-4 rank:  percentile blend #%d   naive raw avg #%d   income-only #%d"
      % (min(RK[r["symbol"]] for r in rows if r.get("stage") == 4),
         min(RR[r["symbol"]] for r in rows if r.get("stage") == 4),
         min(RI[r["symbol"]] for r in rows if r.get("stage") == 4)))

bad = [r for r in order[:50] if r.get("stage") in (3, 4)]
print("\n  S3/S4 inside the new TOP 50: %d — is_buyable=True among them: %d; "
      "already decision AVOID/CUT: %d"
      % (len(bad), sum(1 for r in bad if r.get("is_buyable")),
         sum(1 for r in bad if r.get("decision") in ("AVOID", "CUT"))))
print("  ", [(r["symbol"], r["stage"], r.get("decision"), RK[r["symbol"]]) for r in bad])
print("  across all 250: %d S3/S4 rows, of which is_buyable=%d"
      % (sum(1 for r in rows if r.get("stage") in (3, 4)),
         sum(1 for r in rows if r.get("stage") in (3, 4) and r.get("is_buyable"))))

# ======================================================== 4. the unknowns ====
print("\n" + "=" * 82)
print("4. ROWS WITH NO FUNDAMENTALS — WHERE DO THEY LAND?")
print("=" * 82)
none_at_all = [r for r in rows if r["raw"] is None]
print("  no QoQ number at all:     %d / %d" % (len(none_at_all), len(rows)))
print("  missing at least one leg: %d / %d  -> under None-last they occupy ranks %d..%d"
      % (len(unranked), len(rows), len(ranked) + 1, len(rows)))
print("  stage mix of the unranked:", mix(unranked))
print("  unranked that are Stage 2: %d      unranked that are is_buyable=True: %d"
      % (sum(1 for r in unranked if r.get("stage") == 2),
         sum(1 for r in unranked if r.get("is_buyable"))))
print("  unranked that are ETFs (no quarters by construction): %d"
      % sum(1 for r in unranked if r.get("is_etf")))
zero20 = sorted(rows, key=lambda r: -((r.get("raw") or 0)))[:20]
print("  if a shipper writes `(x.get('blend') or 0)`: %d unknowns land in the top 20"
      % sum(1 for r in zero20 if r["raw"] is None))
asc = sorted(rows, key=lambda r: (r["raw"] is None, r["raw"] or 0))
print("  if the None-last tuple is kept but the sort direction is wrong: #1 = %s (%.1f)"
      % (asc[0]["symbol"], asc[0]["raw"] or 0))

# ============================================== 5. does the cut membership move
print("\n" + "=" * 82)
print("5. DOES DROPPING THE STAGE GATE CHANGE WHO SURVIVES THE top=250 CUT?")
print("=" * 82)
son, soff = {r["symbol"] for r in on["rows"]}, {r["symbol"] for r in rows}
print("  gate ON : 250 shown, n_all=%d qualifying of %d candidates (%.0f%% of qualifiers shown)"
      % (on["n_all"], on["n_prestage"], 100 * 250 / max(on["n_all"], 1)))
print("  gate OFF: 250 shown, n_all=%d candidates (%.0f%% shown)"
      % (off["n_all"], 100 * 250 / max(off["n_all"], 1)))
print("  overlap=%d   only-with-gate=%d   only-without=%d  -> flipping the gate replaces %.0f%% of the board"
      % (len(son & soff), len(son - soff), len(soff - son), 100 * len(son - soff) / 250))
print("  pushed OUT (visible only because the gate freed slots):", sorted(son - soff)[:15])
print("  pushed IN :", sorted(soff - son)[:15])
print("\n  STRUCTURAL: the cut still runs on RECENCY over %d candidates and the\n"
      "  fundamentals are joined AFTER it, so an income+growth ranking only ever\n"
      "  reorders the %d most-recent breakouts (%.0f%% of the pool)."
      % (off["n_all"], len(rows), 100 * len(rows) / max(off["n_all"], 1)))

# ========================================================== 6. staleness =====
print("\n" + "=" * 82)
print("6. STALENESS OF THE FUNDAMENTAL THAT WOULD DO THE RANKING")
print("=" * 82)
lags = sorted(r["lag"] for r in rows if r.get("lag"))
print("  quarter-end lag (days) n=%d: min=%d p25=%d median=%d p75=%d max=%d"
      % (len(lags), lags[0], lags[len(lags) // 4], lags[len(lags) // 2],
         lags[3 * len(lags) // 4], lags[-1]))
print("  >70 days stale: %d/%d (%.0f%%)    >100 days: %d (%.0f%%)"
      % (sum(1 for l in lags if l > 70), len(lags),
         100 * sum(1 for l in lags if l > 70) / len(lags),
         sum(1 for l in lags if l > 100), 100 * sum(1 for l in lags if l > 100) / len(lags)))
print("  TOP-20 lags:", sorted(r["lag"] for r in order[:20] if r.get("lag")))

# ================================================ 7. negative-base artefact ==
print("\n" + "=" * 82)
print("7. NEGATIVE / NEAR-ZERO BASE ARTEFACTS IN THE QoQ FORMULA")
print("=" * 82)
print("  prior-quarter EPS < 0: %d/250 (%.0f%%)   of the %d ranked: %d"
      % (sum(1 for r in rows if r["f"].get("eneg")),
         100 * sum(1 for r in rows if r["f"].get("eneg")) / 250,
         len(ranked), sum(1 for r in ranked if r["f"].get("eneg"))))
print("  inside the new TOP 20: %d      TOP 50: %d"
      % (sum(1 for r in order[:20] if r["f"].get("eneg")),
         sum(1 for r in order[:50] if r["f"].get("eneg"))))
print("  |prior-Q EPS| < $0.05 (a rounding base) among the ranked: %d"
      % sum(1 for r in ranked if r["f"].get("eps_q1") is not None and abs(r["f"]["eps_q1"]) < 0.05))
print("  revQoQ > +1000% inside the top 60 (near-zero prior revenue):",
      [(r["symbol"], r["f"].get("rev_qoq")) for r in order[:60] if (r["f"].get("rev_qoq") or 0) > 1000])

# ================================================ 8. sequential vs YoY =======
print("\n" + "=" * 82)
print("8. SEQUENTIAL vs YoY — the Minervini seasonality guard he gives up")
print("=" * 82)


def spearman(pairs):
    n = len(pairs)
    if n < 3:
        return None
    xs = sorted(range(n), key=lambda i: pairs[i][0])
    ys = sorted(range(n), key=lambda i: pairs[i][1])
    rx, ry = [0] * n, [0] * n
    for k, i in enumerate(xs):
        rx[i] = k
    for k, i in enumerate(ys):
        ry[i] = k
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    den = math.sqrt(sum((rx[i] - mx) ** 2 for i in range(n))
                    * sum((ry[i] - my) ** 2 for i in range(n)))
    return round(num / den, 3) if den else None


be = [r for r in rows if r["f"].get("eps_qoq") is not None and r["f"].get("eps_yoy") is not None]
br = [r for r in rows if r["f"].get("rev_qoq") is not None and r["f"].get("rev_yoy") is not None]
print("  EPS   seq-vs-YoY  n=%d  Spearman rho=%s"
      % (len(be), spearman([(r["f"]["eps_qoq"], r["f"]["eps_yoy"]) for r in be])))
print("  SALES seq-vs-YoY  n=%d  Spearman rho=%s"
      % (len(br), spearman([(r["f"]["rev_qoq"], r["f"]["rev_yoy"]) for r in br])))
pey = [r["f"]["eps_yoy"] for r in rows if r["f"].get("eps_yoy") is not None]
pry = [r["f"]["rev_yoy"] for r in rows if r["f"].get("rev_yoy") is not None]
yr = sorted([r for r in rows if r["f"].get("eps_yoy") is not None and r["f"].get("rev_yoy") is not None],
            key=lambda r: -(0.5 * pct_rank(pey, r["f"]["eps_yoy"])
                            + 0.5 * pct_rank(pry, r["f"]["rev_yoy"])))
y50 = {r["symbol"] for r in yr[:50]}
missing = [r["symbol"] for r in order[:20] if r["symbol"] not in y50]
print("  QoQ TOP-20 names absent from the YoY top-50: %d -> %s" % (len(missing), missing))
print("  YoY TOP-20 stage mix:", mix(yr[:20]), "   QoQ TOP-20 stage mix:", mix(order[:20]))

# ================================================ 9. protected variant =======
print("\n" + "=" * 82)
print("9. PROTECTED VARIANT — positive base AND YoY must agree")
print("=" * 82)


def clean(r):
    f = r["f"]
    return ((not f.get("eneg")) and (f.get("eps_q1") or 0) >= 0.05
            and f.get("eps_yoy") is not None and f.get("eps_yoy") > 0
            and f.get("rev_yoy") is not None and f.get("rev_yoy") > 0)


safe = [r for r in ranked if clean(r)]
print("  survivors of (prior-Q EPS >= $0.05, YoY EPS > 0, YoY sales > 0): %d of %d ranked"
      % (len(safe), len(ranked)))
print("  TOP 20 stage mix:", mix(safe[:20]), "  S4 in top 20:",
      sum(1 for r in safe[:20] if r.get("stage") == 4))
print("  %-7s %4s %10s %9s %10s %9s" % ("sym", "stg", "epsQoQ%", "revQoQ%", "epsYoY%", "revYoY%"))
for r in safe[:20]:
    f = r["f"]
    print("  %-7s %4s %10.1f %9.1f %10.1f %9.1f"
          % (r["symbol"], r.get("stage"), f["eps_qoq"], f["rev_qoq"], f["eps_yoy"], f["rev_yoy"]))

# =============================== 10. is the recency cut hiding better growers?
print("\n" + "=" * 82)
print("10. IS THE RECENCY CUT HIDING BETTER GROWERS?")
print("=" * 82)
shown = {r["symbol"] for r in rows}
pool = [c for c in cands if c["symbol"] not in shown]
random.seed(7)
samp = random.sample(pool, 400)
print("  sampling %d of %d hidden candidates" % (len(samp), len(pool)))
f2 = fetch([p["symbol"] for p in samp])
thr20, thr50 = ranked[19]["blend"], ranked[49]["blend"]
elig = hit20 = hit50 = 0
for p in samp:
    f = f2.get(p["symbol"]) or {}
    a, b = pct_rank(pe, f.get("eps_qoq")), pct_rank(prv, f.get("rev_qoq"))
    if a is None or b is None:
        continue
    elig += 1
    p["blend"] = 0.5 * a + 0.5 * b
    hit20 += p["blend"] >= thr20
    hit50 += p["blend"] >= thr50
print("  %d/%d sampled have both QoQ legs (%.0f%%)" % (elig, len(samp), 100 * elig / len(samp)))
for lbl, h in (("#20", hit20), ("#50", hit50)):
    lo, hi = wilson(h, len(samp))
    print("  beat today's %s blend: %d/%d = %.1f%%  95%%CI %.1f..%.1f%%  -> ~%d of %d hidden (CI %d..%d)"
          % (lbl, h, len(samp), 100 * h / len(samp), lo, hi,
             int(len(pool) * h / len(samp)), len(pool),
             int(len(pool) * lo / 100), int(len(pool) * hi / 100)))
beat = [p for p in samp if p.get("blend") is not None and p["blend"] >= thr20]
print("  stage mix of hidden would-be-top-20:", mix(beat))
print("  their tickers:", sorted(p["symbol"] for p in beat)[:25])

# ============================================ 11. what recency-ranking costs ==
print("\n" + "=" * 82)
print("11. WHAT RANKING ON FUNDAMENTALS COSTS THE 'RECENT BREAKOUT' READ")
print("=" * 82)
fresh = [r for r in rows if r.get("days_since_breakout") == 0]
rk = sorted(RK[r["symbol"]] for r in fresh)
print("  broke out TODAY: %d rows; their ranks under the new sort: %s" % (len(fresh), rk))
print("  of today's breakouts in the new top 20: %d    top 50: %d"
      % (sum(1 for x in rk if x <= 20), sum(1 for x in rk if x <= 50)))
print("  today's breakouts that are UNRANKED (a data gap, not a verdict): %d"
      % sum(1 for r in fresh if r["blend"] is None))
