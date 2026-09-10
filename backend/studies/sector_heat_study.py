"""Does the heat of a name's SECTOR change what happens when it lands in a
demand zone?

Ajay 2026-09-09 (verbatim):

    "So when we are looking at newly stocks getting dropped in to demand zone
     they might be too late. What we are looking for hot sectors in demand
     zone ... Becuz when money is moved from a sector its just sitting there
     stock is not reversing quick."

That is a FALSIFIABLE claim with two halves, and they are measured separately:

  (a) does a demand-zone arrival in a hot group WIN more often?
  (b) does it turn FASTER — "not reversing quick" is a clock claim, and a
      clock claim can be true while the win claim is false.

METHOD, and why it is stated this way
─────────────────────────────────────
* Events are bounce_quality_study.py's replayed table: one row per demand-band
  arrival, carrying `symbol`, `date`, `R` and `why` (target | stop | clock).
* HEAT IS COMPUTED AS OF THE EVENT BAR. For every symbol a full trailing
  21-session return series is built once; a group's heat on date D is the
  MEDIAN of its members' r21 on D minus the benchmark's r21 on D — the same
  definition rotation.tracker.build uses for rel_21d, evaluated at D instead
  of at the last bar. Closes up to and including D are known at the decision
  point (the entry IS that bar's close), so there is no lookahead.
* HOT/COLD ARE RANKS ON THAT DATE'S OWN CROSS-SECTION, pooled across grains,
  exactly as rotation.heat does live: top third hot, bottom third cold. A
  fixed magnitude would drift with the market's own drawdown.
* LEAD ON WIN RATE AND STOP-OUT RATE, not mean R. Established on this cohort
  2026-09-09: the top 1% of events carry 86.6% of total R and the median R is
  -1.000 in every arm. Mean R is a tail statistic here; win and stop are
  binomials.
* INTERVALS RESAMPLE WHOLE DATES. Events cluster hard on dates (design effect
  16.75 measured on this table); an i.i.d. interval is too narrow by
  construction and that error invalidated an earlier study's flags.

KNOWN CAVEAT, STATED NOT HIDDEN: cohort MEMBERSHIP is today's (the scan's
sector/industry labels). A name that changed industry inside the window is
labelled with today's. This biases nothing toward the hypothesis, but it is
survivorship in the labels and the reader should know.

Re-run:
  docker run --rm --network cheetah-market-app_default \\
    -e MONGO_URL="mongodb://mongo:27017" -e PYTHONPATH=/app \\
    -v <repo>/backend:/app:ro -w /app \\
    -v cheetah-market-app_cheetah-scans:/root/.cheetah:ro \\
    -v <scratch>:/scratch cheetah-api:latest \\
    python -u /app/studies/sector_heat_study.py --events /scratch/bq_events.csv
"""
from __future__ import annotations

import argparse
import numpy as np
import pandas as pd

WINDOW = 21              # rotation.tracker.WINDOW_SHORT
BENCH = "RSP"
BENCH_ALT = "SPY"
MIN_N = 8                # rotation.tracker.MIN_COHORT_N
HOT_PCTL = 66.7          # rotation.heat.HOT_PCTL
COLD_PCTL = 33.3         # rotation.heat.COLD_PCTL
BOOT_DRAWS = 1500
SAMPLE_PER_GROUP = 25    # rotation.tracker.COHORT_SAMPLE


def labels() -> dict:
    """{SYMBOL: (sector, industry)} from the latest scan — the same source
    rotation.tracker._sector_members reads."""
    from sepa import scanner
    rows = (scanner.load_latest() or {}).get("all_results") or []
    out = {}
    for r in rows:
        sym = (r.get("symbol") or "").upper()
        if sym:
            out[sym] = (r.get("sector"), r.get("industry"))
    return out


def cohorts(lab: dict, sample: int = SAMPLE_PER_GROUP) -> dict:
    """{(grain, name): [members]} for industry and sector, same floor and the
    same deterministic stride as the tracker."""
    from sepa import universe as U
    pools: dict = {}
    for sym, (sec, ind) in lab.items():
        if ind:
            pools.setdefault(("industry", str(ind)), set()).add(sym)
        if sec:
            pools.setdefault(("sector", str(sec)), set()).add(sym)
        try:
            th = U.theme_for(sym)
        except Exception:
            th = None
        if th:
            pools.setdefault(("theme", str(th)), set()).add(sym)
    out = {}
    for key, syms in pools.items():
        members = sorted(syms)
        if len(members) < MIN_N:
            continue
        if len(members) > sample:
            step = len(members) / sample
            members = [members[int(i * step)] for i in range(sample)]
        out[key] = members
    return out


def r21_series(symbols: list, window: int = WINDOW) -> pd.DataFrame:
    """DataFrame indexed by ISO date, one column per symbol: the trailing
    `window`-session percent return AS OF that date. PURE given the loader."""
    from sepa import prices
    cols = {}
    for i, sym in enumerate(symbols):
        try:
            df = prices.load_prices(sym, period="2y")
        except Exception:
            continue
        if df is None or len(df) < window + 2:
            continue
        d = df.copy()
        idx = pd.to_datetime(d["date"] if "date" in d.columns else d.index).strftime("%Y-%m-%d")
        c = pd.to_numeric(d["close"] if "close" in d.columns else d["Close"], errors="coerce")
        s = pd.Series(c.values, index=idx)
        s = s[~s.index.duplicated(keep="last")]
        cols[sym] = (s / s.shift(window) - 1.0) * 100.0
        if (i + 1) % 200 == 0:
            print("  r21 %d/%d" % (i + 1, len(symbols)), flush=True)
    return pd.DataFrame(cols)


def heat_panel(coh: dict, r21: pd.DataFrame) -> pd.DataFrame:
    """DataFrame indexed by date, one column per "grain::name": the group's
    median member r21 minus the benchmark's r21 on that date."""
    bench_col = BENCH if BENCH in r21.columns else (BENCH_ALT if BENCH_ALT in r21.columns else None)
    if bench_col is None:
        raise SystemExit("no benchmark series (%s / %s)" % (BENCH, BENCH_ALT))
    b = r21[bench_col]
    out = {}
    for (grain, name), members in coh.items():
        have = [m for m in members if m in r21.columns]
        if len(have) < MIN_N:
            continue
        med = r21[have].median(axis=1, skipna=True)
        out["%s::%s" % (grain, name)] = med - b
    return pd.DataFrame(out)


def tone_panel(panel: pd.DataFrame) -> pd.DataFrame:
    """Same shape, values in {hot, neutral, cold, ''} — the POOLED percentile
    rank across every group on that date, exactly as rotation.heat scores it
    live. Rows with fewer than 3 live groups score nothing."""
    ranks = panel.rank(axis=1, pct=True, na_option="keep") * 100.0
    live = panel.notna().sum(axis=1)
    tone = pd.DataFrame("", index=panel.index, columns=panel.columns)
    tone = tone.mask(ranks >= HOT_PCTL, "hot")
    tone = tone.mask((ranks > COLD_PCTL) & (ranks < HOT_PCTL), "neutral")
    tone = tone.mask(ranks <= COLD_PCTL, "cold")
    tone = tone.mask(panel.isna(), "")
    tone.loc[live < 3, :] = ""
    return tone


def annotate(E: pd.DataFrame, lab: dict, tone: pd.DataFrame,
             panel: pd.DataFrame) -> pd.DataFrame:
    """Attach `heat_tone`, `heat_rel` and `heat_grain` to every event, resolving
    industry -> sector exactly like rotation.heat.read."""
    E = E.copy()
    E["date"] = E["date"].astype(str).str[:10]
    tones, rels, grains = [], [], []
    for sym, d in zip(E["symbol"].astype(str).str.upper(), E["date"]):
        sec, ind = lab.get(sym, (None, None))
        t, rel, g = "", np.nan, ""
        for grain, name in (("industry", ind), ("sector", sec)):
            if not name:
                continue
            col = "%s::%s" % (grain, name)
            if col not in tone.columns or d not in tone.index:
                continue
            v = tone.at[d, col]
            if v:
                t, rel, g = v, float(panel.at[d, col]), grain
                break
        tones.append(t); rels.append(rel); grains.append(g)
    E["heat_tone"] = tones
    E["heat_rel"] = rels
    E["heat_grain"] = grains
    return E


def _boot_diff(E: pd.DataFrame, mask, col_fn, draws: int = BOOT_DRAWS):
    """95% interval on (arm - rest) for a per-event boolean, resampling WHOLE
    DATES. Returns (lo, hi)."""
    dates = E["date"].unique()
    rng = np.random.default_rng(7)
    by = {d: g for d, g in E.groupby("date")}
    out = []
    for _ in range(draws):
        pick = rng.choice(dates, size=len(dates), replace=True)
        S = pd.concat([by[d] for d in pick], ignore_index=True)
        a, b = S[mask(S)], S[~mask(S)]
        if len(a) < 30 or len(b) < 30:
            continue
        out.append(col_fn(a) - col_fn(b))
    if not out:
        return (float("nan"), float("nan"))
    return (float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)))


def report(E: pd.DataFrame, draws: int = BOOT_DRAWS) -> None:
    E = E[E["heat_tone"] != ""].copy()
    E["win"] = E["R"] > 0
    E["stop"] = E["why"] == "stop"
    E["tgt"] = E["why"] == "target"
    # The table simulates every event at FOUR clocks (5 / 10 / 20 / 60
    # sessions), which is a sharper instrument for his claim than a single
    # bars-to-exit number: "not reversing quick" predicts that hot beats cold
    # MOST at the short clock and that the gap closes as the clock lengthens.
    CLOCKS = [(c, "why%s" % c, "R%s" % c) for c in ("5", "10", "20", "60")
              if "why%s" % c in E.columns and "R%s" % c in E.columns]

    print("=" * 108)
    print("SECTOR HEAT AT THE DEMAND-ZONE ARRIVAL   n=%d events, %d dates, %d names"
          % (len(E), E["date"].nunique(), E["symbol"].nunique()))
    print("  heat resolved at: %s" % E["heat_grain"].value_counts().to_dict())
    print("=" * 108)
    base_w = 100.0 * E["win"].mean()
    base_s = 100.0 * E["stop"].mean()
    base_t = 100.0 * E["tgt"].mean()
    print("  %-10s %7s %8s %9s %9s %9s %9s" %
          ("arm", "n", "share", "win%", "stop%", "target%", "med R"))
    print("  %-10s %7d %8s %9.1f %9.1f %9.1f %9.3f"
          % ("ALL (placebo)", len(E), "100%", base_w, base_s, base_t, E["R"].median()))
    for arm in ("hot", "neutral", "cold"):
        S = E[E["heat_tone"] == arm]
        if S.empty:
            continue
        print("  %-10s %7d %7.1f%% %9.1f %9.1f %9.1f %9.3f"
              % (arm, len(S), 100.0 * len(S) / len(E), 100.0 * S["win"].mean(),
                 100.0 * S["stop"].mean(), 100.0 * S["tgt"].mean(), S["R"].median()))
    print()
    for arm in ("hot", "cold"):
        m = (lambda S, a=arm: S["heat_tone"] == a)
        for label, fn in (("win rate", lambda S: 100.0 * S["win"].mean()),
                          ("stop-out rate", lambda S: 100.0 * S["stop"].mean())):
            S = E[E["heat_tone"] == arm]
            rest = E[E["heat_tone"] != arm]
            if S.empty or rest.empty:
                continue
            d = fn(S) - fn(rest)
            lo, hi = _boot_diff(E, m, fn, draws)
            flag = "" if (lo <= 0 <= hi) else "   <-- interval excludes zero"
            print("  %-5s %-14s  %+6.2f pp   95%% [%+.2f, %+.2f]  (whole-date bootstrap)%s"
                  % (arm, label, d, lo, hi, flag))
    print()
    if CLOCKS:
        print("  HIS CLOCK CLAIM - \"when money is moved from a sector its just sitting")
        print("  there, stock is not reversing quick\". If that is true, HOT beats COLD by")
        print("  MORE at the short clock, and the edge decays as the clock lengthens.")
        print()
        print("    %-9s %10s %10s %10s %12s" % ("clock", "hot win%", "cold win%", "hot-cold", "hot target%"))
        for c, wcol, rcol in CLOCKS:
            H = E[E["heat_tone"] == "hot"]
            C = E[E["heat_tone"] == "cold"]
            if len(H) < 30 or len(C) < 30:
                continue
            hw = 100.0 * (H[rcol] > 0).mean()
            cw = 100.0 * (C[rcol] > 0).mean()
            ht = 100.0 * (H[wcol] == "target").mean()
            print("    %-9s %9.1f%% %9.1f%% %+9.2f pp %11.1f%%"
                  % (c + "d", hw, cw, hw - cw, ht))
        print()
        # The same difference with an interval, at the SHORTEST clock - that is
        # where his claim lives.
        c, wcol, rcol = CLOCKS[0]
        fn = lambda S, col=rcol: 100.0 * (S[col] > 0).mean()
        H = E[E["heat_tone"] == "hot"]
        rest = E[E["heat_tone"] == "cold"]
        sub = E[E["heat_tone"].isin(["hot", "cold"])]
        d = fn(H) - fn(rest)
        lo, hi = _boot_diff(sub, lambda S: S["heat_tone"] == "hot", fn, draws)
        flag = "" if (lo <= 0 <= hi) else "   <-- interval excludes zero"
        print("    hot vs cold at %sd: %+.2f pp   95%% [%+.2f, %+.2f]%s"
              % (c, d, lo, hi, flag))
    else:
        print("  (no clock columns in the event table - clock claim not measurable here)")
    print("=" * 108)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--events", required=True)
    ap.add_argument("--draws", type=int, default=BOOT_DRAWS)
    ap.add_argument("--out", default=None, help="write the annotated table here")
    a = ap.parse_args()

    E = pd.read_csv(a.events)
    print("events %d rows, %d dates" % (len(E), E["date"].astype(str).str[:10].nunique()))
    lab = labels()
    coh = cohorts(lab)
    print("cohorts: %d (industry %d, sector %d, theme %d)"
          % (len(coh), *[sum(1 for k in coh if k[0] == g) for g in ("industry", "sector", "theme")]))
    need = sorted({m for ms in coh.values() for m in ms} | {BENCH, BENCH_ALT})
    print("loading %d series..." % len(need), flush=True)
    r21 = r21_series(need)
    print("r21 panel %s" % (r21.shape,))
    panel = heat_panel(coh, r21)
    print("heat panel %s" % (panel.shape,))
    tone = tone_panel(panel)
    A = annotate(E, lab, tone, panel)
    if a.out:
        A.to_csv(a.out, index=False)
        print("wrote %s" % a.out)
    report(A, a.draws)
