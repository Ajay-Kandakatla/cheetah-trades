"""Is sequential quarter-over-quarter growth a seasonality artifact on Ajay's
breakout board?   READ-ONLY measurement.  Nothing in the repo is touched.

RUN (must be inside the api container -- it is the ONLY place the Massive key
lives; a throwaway container silently falls back to Yahoo = false negatives):

    cd /Users/ajay/clinet-test/cheetah-market-app && \
      docker compose exec -T api python - < /tmp/scratch/qoq/seasonality.py

Universe : live breakout board, B.board(top=250, stages=False).
Data     : Massive /vX/reference/financials, timeframe=quarterly.
           canslim._fetch_massive_financials uses limit=8 and DROPS
           fiscal_period, so we call the endpoint directly and keep the period
           labels.  We pull limit=24 (not 8): the latest-report numbers are
           identical either way, but the within-name seasonal test needs
           several observations per fiscal quarter per name.

THREE THINGS THAT BITE, all handled below:
  (a) Index adjacency in the API list is NOT quarter adjacency -- Massive's
      window has real gaps (NVDA is missing Q1 FY2025).  We key on
      fiscal_year*4+q so "prior quarter" is always the true prior quarter.
  (b) Grouping the LATEST report by fiscal quarter is structurally degenerate:
      on any one date ~80% of the board's latest filing is the same calendar
      quarter.  That test has almost no power.  The honest test pools every
      historical quarter (section 1b).
  (c) A full label SHUFFLE is the wrong placebo for seasonality.  A real
      quarterly series is balanced -- one Q1 per year -- so shuffling destroys
      the balance and inflates the null.  The primary placebo here is a
      CIRCULAR ROTATION of the quarter labels (Q1->Q2->Q3->Q4), which keeps
      the design and asks only: is the TRUE alignment special?
"""
from __future__ import annotations

import random
import statistics as st
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import requests
from massive_keys import stocks_key

BASE = "https://api.massive.com/vX/reference/financials"
LIMIT = 24
WORKERS = 6
RETRIES = 3
SEED = 20260912
N_BOOT = 2000
N_PERM = 2000
WINSOR = 200.0            # pct cap, variance decomposition only
QNUM = {"Q1": 1, "Q2": 2, "Q3": 3, "Q4": 4}
INV = {v: k for k, v in QNUM.items()}


# ---------------------------------------------------------------- fetch ------

def fetch(symbol: str, api_key: str):
    """Returns (results, status).  Retries -- at 250 names an 8-wide pool with
    a 20s timeout silently lost 118 names to timeouts on the first pass, and
    fetch() swallowing that produced a fake 92/250 'coverage' number."""
    last = "?"
    for attempt in range(RETRIES):
        try:
            r = requests.get(BASE, params={
                "ticker": symbol.upper(), "limit": LIMIT,
                "timeframe": "quarterly", "apiKey": api_key,
            }, timeout=40)
            last = r.status_code
            if r.status_code == 200:
                return (r.json() or {}).get("results") or [], 200
            if r.status_code in (401, 403):
                return [], r.status_code
        except Exception as exc:
            last = "EXC:" + type(exc).__name__
    return [], last


def fetch_annual(symbol: str, api_key: str):
    """(fiscal_year -> {'rev','eps'}, ok) from the ANNUAL timeframe.  Needed
    only to detect the cumulative-Q4 bug -- see scrub_cumulative_q4.  The `ok`
    flag matters: a silently-failed annual fetch means that name's cumulative
    Q4 rows are NOT scrubbed, i.e. contamination we would not otherwise see."""
    out = {}
    ok = False
    for _ in range(RETRIES):
        try:
            r = requests.get(BASE, params={
                "ticker": symbol.upper(), "limit": 8,
                "timeframe": "annual", "apiKey": api_key}, timeout=40)
            if r.status_code != 200:
                if r.status_code in (401, 403):
                    return out, False
                continue
            for rep in (r.json() or {}).get("results") or []:
                fy = rep.get("fiscal_year")
                try:
                    fy = int(fy)
                except (TypeError, ValueError):
                    continue
                out[fy] = {"rev": _inc(rep, "revenues"),
                           "eps": _inc(rep, "diluted_earnings_per_share")}
            return out, True
        except Exception:
            continue
    return out, ok


def scrub_cumulative_q4(ser, annual):
    """DATA BUG, verified on ORCL 2026-09-12: Massive's derived Q4 rows (the
    ones with filing_date=None, 23% of all rows) carry the FULL-YEAR figure
    instead of the discrete fourth quarter for older fiscal years.

        ORCL Q4 FY2020 rev = $39.068B  (FY2020 total = $39.068B)  -> seq +298.8%
        ORCL Q4 FY2023 rev = $13.836B  (FY2023 total = $50.0B)    -> seq  +11.6%

    Left in, every affected name prints a fake ~+300% Q4 followed by a fake
    ~-76% Q1 -- which is precisely the Q1-low/Q4-high 'seasonality' this study
    is trying to measure.  Any Q4 whose value is within 2% of that fiscal
    year's annual total is dropped outright.  Returns (series, n_dropped).
    """
    dropped = fallback = 0
    for idx in list(ser):
        rec = ser[idx]
        if rec["fp"] != "Q4":
            continue
        fy = annual.get(rec["fy"]) or {}
        hit = False
        for field in ("rev", "eps"):
            q, a = rec.get(field), fy.get(field)
            if q is None or a is None or a == 0:
                continue
            if abs(q - a) / abs(a) < 0.02:
                hit = True
        if not hit and not rec["filing_date"] and rec.get("rev"):
            # Fallback for names whose ANNUAL fetch failed: a DERIVED Q4 more
            # than 2.2x the best of that year's other three quarters is a
            # full-year total, not a quarter.  GME's real holiday Q4 is 1.66x
            # its Q3, so a genuine seasonal peak stays in.
            sibs = [ser[j]["rev"] for j in (idx - 3, idx - 2, idx - 1)
                    if j in ser and ser[j].get("rev") and ser[j]["rev"] > 0]
            if len(sibs) == 3 and rec["rev"] > 2.2 * max(sibs):
                hit = True
                fallback += 1
        if hit:
            del ser[idx]
            dropped += 1
    return ser, dropped, fallback


def _inc(rep, key):
    try:
        v = ((rep.get("financials") or {}).get("income_statement") or {}).get(key, {}).get("value")
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def to_series(reports):
    """abs quarter index -> record.  idx = fiscal_year*4 + (q-1), so the true
    prior fiscal quarter is always idx-1 and the year-ago quarter idx-4."""
    out = {}
    for rep in reports:
        fp, fy = rep.get("fiscal_period"), rep.get("fiscal_year")
        if fp not in QNUM or fy is None:
            continue
        try:
            fy = int(fy)
        except (TypeError, ValueError):
            continue
        idx = fy * 4 + (QNUM[fp] - 1)
        rec = {"fp": fp, "fy": fy,
               "rev": _inc(rep, "revenues"),
               "eps": _inc(rep, "diluted_earnings_per_share"),
               "end_date": rep.get("end_date"),
               "filing_date": rep.get("filing_date"),
               "acc": rep.get("acceptance_datetime") or ""}
        prev = out.get(idx)
        if prev is None or (rec["acc"] or "") > (prev["acc"] or ""):
            out[idx] = rec
    return out


def cal_q(end_date):
    """Calendar quarter of the period END -- the real-world seasonality axis.
    fiscal_period is the company's own label and is offset for off-calendar
    fiscal years (NVDA's 'Q2 FY2027' ends in July)."""
    s = str(end_date or "")
    if len(s) < 7:
        return None
    try:
        return f"CQ{(int(s[5:7]) - 1) // 3 + 1}"
    except ValueError:
        return None


# ------------------------------------------------------------- growth --------

def pct(cur, prior):
    if cur is None or prior is None or prior == 0:
        return None
    return (cur - prior) / abs(prior) * 100.0


def ttm_at(ser, idx, field):
    vals = []
    for k in range(idx - 3, idx + 1):
        v = (ser.get(k) or {}).get(field)
        if v is None:
            return None
        vals.append(v)
    return sum(vals)


def build_obs(ser, field):
    """Every quarter -> dict of the four growth flavours at that quarter,
    plus whether the DENOMINATOR was non-positive (a % change off a negative
    or ~zero base is not a growth rate; for EPS that is ~half the board)."""
    out = {}
    for idx in sorted(ser):
        prior = (ser.get(idx - 1) or {}).get(field)
        yrago = (ser.get(idx - 4) or {}).get(field)
        cur = ser[idx].get(field)
        out[idx] = {
            "fp": ser[idx]["fp"], "cq": cal_q(ser[idx]["end_date"]),
            "seq": pct(cur, prior),
            "yoy": pct(cur, yrago),
            "ttm_seq": pct(ttm_at(ser, idx, field), ttm_at(ser, idx - 1, field)),
            "seq_base_ok": (prior is not None and prior > 0),
            "yoy_base_ok": (yrago is not None and yrago > 0),
        }
    return out


# --------------------------------------------------------------- stats -------

def median(xs):
    return st.median(xs) if xs else None


def q1q3(xs):
    if len(xs) < 4:
        return (None, None)
    s = sorted(xs)
    return (st.median(s[: len(s) // 2]), st.median(s[(len(s) + 1) // 2:]))


def boot_median_ci(xs, n=N_BOOT, seed=SEED):
    if len(xs) < 8:
        return (None, None)
    r = random.Random(seed)
    N = len(xs)
    meds = sorted(st.median([xs[r.randrange(N)] for _ in range(N)]) for _ in range(n))
    return (round(meds[int(0.025 * n)], 2), round(meds[int(0.975 * n)], 2))


def spread_of_medians(groups, min_n):
    meds = [median(v) for v in groups.values() if len(v) >= min_n]
    meds = [m for m in meds if m is not None]
    return (max(meds) - min(meds)) if len(meds) >= 2 else None


def rotate(lab, r):
    """Rotate a quarter label by r, for either axis: Q1->Q2 or CQ1->CQ2."""
    pre, n = lab[:-1], int(lab[-1])
    return f"{pre}{((n - 1 + r) % 4) + 1}"


def pooled_quarter_test(recs, min_n=25, n=N_PERM, seed=SEED):
    """recs = [(sym, fp, value)].  Observed spread of the four quarter medians
    vs a ROTATION placebo: each NAME's quarter labels are rotated by a random
    1..3, preserving the balanced one-Q1-per-year design."""
    g = defaultdict(list)
    for _, fp, v in recs:
        g[fp].append(v)
    obs = spread_of_medians(g, min_n)
    if obs is None:
        return None, None, None, g
    r = random.Random(seed)
    by_sym = defaultdict(list)
    for sym, fp, v in recs:
        by_sym[sym].append((fp, v))
    nulls = []
    for _ in range(n):
        gg = defaultdict(list)
        for sym, items in by_sym.items():
            rot = r.randint(1, 3)
            for fp, v in items:
                gg[rotate(fp, rot)].append(v)
        s = spread_of_medians(gg, min_n)
        if s is not None:
            nulls.append(s)
    if not nulls:
        return obs, None, None, g
    p = (sum(1 for s in nulls if s >= obs) + 1) / (len(nulls) + 1)
    return obs, median(nulls), p, g


def eta_sq(labels, values):
    """SS_between / SS_total, groups = which fiscal quarter the observation is.
    1.0 = the quarter label explains the name's whole sequential series."""
    if len(values) < 4:
        return None
    grand = sum(values) / len(values)
    sst = sum((v - grand) ** 2 for v in values)
    if sst <= 0:
        return None
    g = defaultdict(list)
    for lab, v in zip(labels, values):
        g[lab].append(v)
    if len(g) < 2:
        return None
    ssb = sum(len(vs) * ((sum(vs) / len(vs)) - grand) ** 2 for vs in g.values())
    return ssb / sst


def eta_with_shift_null(labels, values):
    """Observed eta^2 plus a CIRCULAR PHASE-SHIFT null.

    Rotating a single name's quarter labels (Q1->Q2->...) is a no-op for
    eta^2 -- it only RENAMES the groups, the partition is identical, so the
    first version of this returned obs == null for every name.  The correct
    within-name null slides the VALUE series against the calendar by k
    positions, keeping the time-ordering (and therefore the serial
    correlation and any trend) intact while breaking the value<->quarter
    alignment.  Shifts that reproduce the same partition are skipped.

    Returns (observed, mean null, 95th-pct null, n valid shifts).
    """
    obs = eta_sq(labels, values)
    if obs is None:
        return None, None, None, 0
    n = len(values)
    nulls = []
    for k in range(1, n):
        if all(labels[(j - k) % n] == labels[j] for j in range(n)):
            continue                      # identical partition -- no-op
        e = eta_sq(labels, values[k:] + values[:k])
        if e is not None:
            nulls.append(e)
    if not nulls:
        return obs, None, None, 0
    nulls.sort()
    return (obs, sum(nulls) / len(nulls),
            nulls[min(len(nulls) - 1, int(0.95 * len(nulls)))], len(nulls))


def winsor(xs, cap=WINSOR):
    return [max(-cap, min(cap, x)) for x in xs]


def spearman(pairs):
    if len(pairs) < 5:
        return None
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        rk = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1
            for k in range(i, j + 1):
                rk[order[k]] = avg
            i = j + 1
        return rk
    a = rank([p[0] for p in pairs]); b = rank([p[1] for p in pairs])
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = (sum((x - ma) ** 2 for x in a) * sum((y - mb) ** 2 for y in b)) ** 0.5
    return num / den if den else None


def f(v, nd=1):
    return "n/a" if v is None else f"{v:+.{nd}f}"


# ---------------------------------------------------------------- main -------

def main():
    key = stocks_key()
    assert key, "no Massive key -- you are NOT in the api container"
    from sepa import breakout as B
    board = B.board(top=250, stages=False)
    syms = [r["symbol"] for r in board["rows"] if r.get("symbol")]
    print(f"BOARD  n={len(syms)}  scan_ts={board.get('scan_ts')}  board_n_all={board.get('n_all')}")

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        got = dict(zip(syms, ex.map(lambda s: fetch(s, key), syms)))
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        annres = dict(zip(syms, ex.map(lambda s: fetch_annual(s, key), syms)))
    ann = {k: v[0] for k, v in annres.items()}
    ann_fail = [k for k, v in annres.items() if not v[1]]
    etf = {r["symbol"]: bool(r.get("is_etf")) for r in board["rows"] if r.get("symbol")}
    bad = {s: v[1] for s, v in got.items() if v[1] != 200}
    empty = [s for s, v in got.items() if v[1] == 200 and not v[0]]
    data, derived_q4, rows, cum_dropped, cum_names, cum_fb = {}, 0, 0, 0, 0, 0
    for s, (reps, _) in got.items():
        ser = to_series(reps)
        ser, nd, nfb = scrub_cumulative_q4(ser, ann.get(s) or {})
        cum_dropped += nd
        cum_fb += nfb
        cum_names += 1 if nd else 0
        if ser:
            data[s] = ser
            for rec in ser.values():
                rows += 1
                if rec["fp"] == "Q4" and not rec["filing_date"]:
                    derived_q4 += 1
    print(f"FETCH  non-200/error: {len(bad)} {list(bad.items())[:6]}")
    print(f"       200-but-empty (ETFs, foreign 20-F filers): {len(empty)}  e.g. {empty[:10]}")
    print(f"       USABLE names: {len(data)}/{len(syms)}   labelled quarter-rows: {rows}")
    print(f"       Q4 rows with NO filing_date (Massive-derived): "
          f"{derived_q4} ({100.0*derived_q4/max(rows,1):.0f}% of surviving rows)")
    print(f"       *** CUMULATIVE-Q4 ROWS SCRUBBED (Q4 value == that FY's annual "
          f"total): {cum_dropped} rows across {cum_names} names "
          f"({cum_fb} caught by the 2.2x fallback, annual fetch unavailable) ***")
    print(f"       annual-timeframe fetch failed for {len(ann_fail)} names "
          f"{ann_fail[:8]}")
    print(f"       ETFs/commodity trusts on the board (revenue is meaningless "
          f"for these): {sum(1 for s in data if etf.get(s))}")
    nq = [len(v) for v in data.values()]
    print(f"       quarters/name: median {median(nq):.0f}, >=8: {sum(1 for n in nq if n>=8)}, "
          f">=12: {sum(1 for n in nq if n>=12)}")

    obs_rev = {s: build_obs(ser, "rev") for s, ser in data.items()}
    obs_eps = {s: build_obs(ser, "eps") for s, ser in data.items()}

    # =====================================================================
    print("\n" + "=" * 78)
    print("1a. AS SPECIFIED: latest report only, grouped by fiscal_period")
    print("=" * 78)
    latest = {s: max(ser) for s, ser in data.items()}
    for nm, ob, mk in (("revenue SEQ", obs_rev, "seq"), ("revenue YoY", obs_rev, "yoy"),
                       ("EPS SEQ", obs_eps, "seq"), ("EPS YoY", obs_eps, "yoy")):
        g = defaultdict(list)
        for s, idx in latest.items():
            d = ob[s].get(idx) or {}
            if d.get(mk) is not None:
                g[d["fp"]].append(d[mk])
        tot = sum(len(v) for v in g.values())
        line = "  ".join(f"{k} n={len(g[k]):3d} med {f(median(g[k])):>8}" for k in sorted(g))
        print(f"  {nm:<12} n={tot:3d}   {line}")
    cqc = defaultdict(int)
    for s, idx in latest.items():
        cqc[(obs_rev[s].get(idx) or {}).get("cq")] += 1
    print(f"\n  >> WHY THIS TEST IS DEAD: calendar quarter of the latest filing across the")
    print(f"     board = {dict(sorted(cqc.items(), key=lambda x: str(x[0])))}.")
    print("     Every name reports the SAME calendar quarter at the same time, so the")
    print("     'quarter groups' here are just off-calendar fiscal years (n=3..8 cells).")
    print("     Section 1b pools all history instead. That is the real test.")

    # =====================================================================
    print("\n" + "=" * 78)
    print("1b. POOLED OVER ALL HISTORY -- every (name, quarter) observation,")
    print("    grouped by fiscal quarter.  'demeaned' = each name's own median")
    print("    subtracted first, so name-level scale cannot masquerade as season.")
    print("=" * 78)

    def collect(ob, mk, axis="fp", base_gate=None, demean=False):
        recs = []
        for s, per in ob.items():
            vals = [(idx, d) for idx, d in per.items()
                    if d.get(mk) is not None and d.get(axis)
                    and (base_gate is None or d.get(base_gate))]
            if not vals:
                continue
            med = median([d[mk] for _, d in vals]) if demean else 0.0
            for idx, d in vals:
                recs.append((s, d[axis], d[mk] - med))
        return recs

    specs = [
        ("revenue SEQUENTIAL", obs_rev, "seq", None),
        ("revenue YoY (ctrl)", obs_rev, "yoy", None),
        ("revenue TTM-SEQ   ", obs_rev, "ttm_seq", None),
        ("EPS SEQUENTIAL    ", obs_eps, "seq", "seq_base_ok"),
        ("EPS YoY (ctrl)    ", obs_eps, "yoy", "yoy_base_ok"),
        ("EPS TTM-SEQ       ", obs_eps, "ttm_seq", None),
    ]
    headline = {}
    for axis, aname in (("fp", "FISCAL quarter"), ("cq", "CALENDAR quarter of period end")):
        print(f"\n--- axis: {aname} ---")
        for nm, ob, mk, gate in specs:
            for dm in (False, True):
                recs = collect(ob, mk, axis, gate, demean=dm)
                o, nullmed, p, g = pooled_quarter_test(recs)
                if o is None:
                    continue
                tag = "demeaned" if dm else "raw     "
                cells = "  ".join(
                    f"{k} n={len(g[k]):4d} med {f(median(g[k])):>7}" for k in sorted(g))
                print(f"  {nm} {tag} | {cells}")
                print(f"      spread {o:5.1f}pp   rotation-placebo {nullmed:5.1f}pp   "
                      f"p={p:.4f}   n_obs={sum(len(v) for v in g.values())}")
                if axis == "fp" and dm:
                    headline[nm.strip()] = (o, nullmed, p, sum(len(v) for v in g.values()))
                    for k in sorted(g):
                        lo, hi = boot_median_ci(g[k])
                        print(f"        {k} median 95%CI [{lo}, {hi}]")

    print("\n--- SENSITIVITY: fiscal axis, demeaned, |value| > 150% dropped ---")
    for nm, ob, mk, gate in specs:
        recs = [(sy, fp, v) for sy, fp, v in collect(ob, mk, "fp", gate, demean=True)
                if abs(v) <= 150.0]
        o, nullmed, p, g = pooled_quarter_test(recs)
        if o is None:
            continue
        cells = "  ".join(f"{k} n={len(g[k]):4d} med {f(median(g[k])):>7}" for k in sorted(g))
        print(f"  {nm} | {cells}")
        print(f"      spread {o:5.1f}pp  placebo {nullmed:5.1f}pp  p={p:.4f}  "
              f"n_obs={sum(len(v) for v in g.values())}")

    # =====================================================================
    print("\n" + "=" * 78)
    print("2. WITHIN-NAME variance decomposition -- eta^2 = SS_between/SS_total")
    print(f"   over a name's OWN series, groups = fiscal quarter.  Winsorized +/-{WINSOR:.0f}%.")
    print("   Placebo = the value series CIRCULARLY SHIFTED against the calendar.")
    print("=" * 78)
    eta_store = {}
    for nm, ob, mk, gate in specs:
        obs_l, null_l, beat, per_name = [], [], 0, {}
        for s, per in ob.items():
            pts = [(idx, d) for idx, d in sorted(per.items())
                   if d.get(mk) is not None and (gate is None or d.get(gate))]
            if len(pts) < 8:
                continue
            labs = [d["fp"] for _, d in pts]
            vals = winsor([d[mk] for _, d in pts])
            if len(set(labs)) < 4:
                continue
            o, nmean, n95, nk = eta_with_shift_null(labs, vals)
            if o is None or nmean is None:
                continue
            obs_l.append(o); null_l.append(nmean)
            per_name[s] = (o, n95, len(pts))
            if n95 is not None and o > n95:
                beat += 1
        eta_store[nm.strip()] = per_name
        if not obs_l:
            print(f"\n  {nm}: no name with >=8 obs across all 4 quarters")
            continue
        lo, hi = boot_median_ci(obs_l)
        mo, mn = median(obs_l), median(null_l)
        print(f"\n  {nm}   names n={len(obs_l)} (>=8 obs, all 4 quarters present)")
        print(f"      median eta^2 OBSERVED = {mo:.3f}  95%CI [{lo}, {hi}]")
        print(f"      median eta^2 SHIFT-NULL = {mn:.3f}   lift = {mo-mn:+.3f}")
        print(f"      names above their OWN 95th-pct shift null: {beat}/{len(obs_l)} "
              f"= {100.0*beat/len(obs_l):.0f}%   (chance = 5%)")

    # =====================================================================
    print("\n" + "=" * 78)
    print("3. MITIGATION HEAD-TO-HEAD (fiscal-quarter axis, demeaned pooled)")
    print("=" * 78)
    print(f"  {'metric':<22}{'spread pp':>11}{'placebo':>10}{'p':>8}{'n_obs':>8}"
          f"{'eta^2':>9}{'eta null':>9}")
    for nm, ob, mk, gate in specs:
        h = headline.get(nm.strip())
        pn = eta_store.get(nm.strip(), {})
        etas = [v[0] for v in pn.values()]
        rots = [v[1] for v in pn.values() if v[1] is not None]
        if not h:
            continue
        o, npl, p, nobs = h
        print(f"  {nm:<22}{o:>11.1f}{npl:>10.1f}{p:>8.3f}{nobs:>8d}"
              f"{(median(etas) if etas else float('nan')):>9.3f}"
              f"{(median(rots) if rots else float('nan')):>9.3f}")

    # =====================================================================
    print("\n" + "=" * 78)
    print("4. NAMED TICKERS  --  seasonal adjustment:")
    print("     adj = latest sequential  -  that name's OWN mean sequential in the")
    print("           SAME fiscal quarter in prior years (n>=2 prior observations)")
    print("=" * 78)
    ex_rows = []
    for s, ser in data.items():
        if etf.get(s):
            continue      # USO/DBA/DBC file 10-Qs but "revenue" is not revenue
        idx = max(ser)
        d = obs_rev[s].get(idx) or {}
        if d.get("seq") is None:
            continue
        hist = [x["seq"] for i, x in obs_rev[s].items()
                if i != idx and x["fp"] == d["fp"] and x["seq"] is not None
                and x.get("seq_base_ok")]
        # MEDIAN, not mean: one near-zero-revenue quarter in a name's history
        # produced a +4,824% "typical Q2" for ATRC on the first pass and threw
        # the whole adjustment. Median is immune to that.
        hm = median(winsor(hist, 300.0)) if hist else None
        ex_rows.append({
            "sym": s, "fp": d["fp"], "end": ser[idx]["end_date"],
            "seq": d["seq"], "yoy": d.get("yoy"), "ttm": d.get("ttm_seq"),
            "hn": len(hist), "hm": hm,
            "adj": (d["seq"] - hm) if hm is not None else None,
            "eta": (eta_store.get("revenue SEQUENTIAL", {}).get(s) or (None,))[0],
        })

    def show(r):
        return (f"   {r['sym']:<6}{r['fp']} end {str(r['end'])[:10]}  seq {f(r['seq']):>8}%"
                f"  own-{r['fp']} hist(n={r['hn']}) {f(r['hm']):>8}%"
                f"  ADJ {f(r['adj']):>8}%  yoy {f(r['yoy']):>8}%"
                f"  eta^2 {('%.2f'%r['eta']) if r['eta'] is not None else 'n/a'}")

    art = [r for r in ex_rows if r["adj"] is not None and r["hn"] >= 3
           and abs(r["seq"]) >= 8
           and (abs(r["adj"]) <= 0.40 * abs(r["seq"]) or r["adj"] * r["seq"] < 0)]
    art.sort(key=lambda r: -(abs(r["seq"]) - abs(r["adj"])))
    print(f"\n (a) SEQUENTIAL IS MOSTLY THE CALENDAR  (n={len(art)} qualify)")
    for r in art[:8]:
        print(show(r))

    gen = [r for r in ex_rows if r["adj"] is not None and r["hn"] >= 3
           and abs(r["adj"]) >= 10
           and (r["yoy"] is None or r["adj"] * r["yoy"] < 0
                or abs(r["adj"] - r["yoy"]) >= 25)]
    gen.sort(key=lambda r: -abs(r["adj"] - (r["yoy"] or 0.0)))
    print(f"\n (b) SEQUENTIAL SURVIVES SEASONAL ADJ AND YoY DISAGREES  (n={len(gen)} qualify)")
    for r in gen[:8]:
        print(show(r))

    print("\n (c) names called out in the brief:")
    for r in sorted([x for x in ex_rows if x["sym"] in ("JFB","NFE","GOLD","META","DELL","GME")],
                    key=lambda r: r["sym"]):
        print(show(r))

    # ---- does the seasonal component actually move his RANKING? ------------
    rk = [r for r in ex_rows if r["adj"] is not None and r["hn"] >= 3]
    pairs = [(r["seq"], r["adj"]) for r in rk]
    rho = spearman(pairs)
    by_seq = sorted(rk, key=lambda r: -r["seq"])
    by_adj = sorted(rk, key=lambda r: -r["adj"])
    pos = {r["sym"]: i for i, r in enumerate(by_seq)}
    moves = sorted(((abs(pos[r["sym"]] - i), r["sym"]) for i, r in enumerate(by_adj)), reverse=True)
    n = len(rk)
    big = sum(1 for m, _ in moves if m >= max(5, n // 10))
    top20_seq = {r["sym"] for r in by_seq[:20]}
    top20_adj = {r["sym"] for r in by_adj[:20]}
    print("\n" + "=" * 78)
    print("5. DOES IT MOVE HIS BOARD?  rank by raw sequential vs season-adjusted")
    print("=" * 78)
    print(f"   names rankable (>=3 prior same-quarter obs): {n}/{len(ex_rows)}")
    print(f"   Spearman raw-vs-adjusted = {rho:.3f}" if rho is not None else "   rho n/a")
    print(f"   names moving >= {max(5, n//10)} rank slots: {big}/{n} = {100.0*big/max(n,1):.0f}%")
    print(f"   top-20 overlap: {len(top20_seq & top20_adj)}/20   "
          f"dropped out on adjustment: {sorted(top20_seq - top20_adj)}")
    print(f"   biggest rank movers: {[(s, m) for m, s in moves[:8]]}")

    # How much of the CROSS-SECTIONAL spread he would be ranking on is the
    # calendar?   seq = (name's typical same-quarter move) + (this quarter's
    # surprise).  Winsorized so one blowup name does not own the variance.
    W = 150.0
    seqs = winsor([r["seq"] for r in rk], W)
    hms  = winsor([r["hm"]  for r in rk], W)
    adjs = winsor([r["adj"] for r in rk], W)
    def var(x):
        m = sum(x) / len(x)
        return sum((v - m) ** 2 for v in x) / (len(x) - 1)
    vs, vh, va = var(seqs), var(hms), var(adjs)
    print(f"\n   VARIANCE SHARE of the raw sequential ranking signal (winsorized "
          f"+/-{W:.0f}%, n={len(rk)}):")
    print(f"     var(raw sequential)          = {vs:9.1f}")
    print(f"     var(name's seasonal norm)    = {vh:9.1f}   = {100.0*vh/vs:4.1f}% of it")
    print(f"     var(season-adjusted surprise)= {va:9.1f}   = {100.0*va/vs:4.1f}% of it")
    print(f"     (the two shares need not sum to 100% -- they covary)")


if __name__ == "__main__":
    main()
