"""📅 Long Term 🔔 — how often would a 🧭 zone reach ring? (pkzone spec §1.6 / critique C3, 2026-11-12). READ ONLY.

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general".

Replays the push rule over the cached daily bars: today's zones from the saved seed (Pankaj's sheet, applied in
hindsight), the /pankaj pad `constants.PANKAJ_ZONE_PAD_PCT`, a reach counted when the PRIOR session's close sat outside
the zone, once per name / zone / session. Two reads bracket the live pass (which samples the last trade every 5 min):
  close      — the session's close inside the padded zone (lower bound)
  day_range  — the session's low–high range touches the padded zone (upper bound)
Bootstrap 95% CI over sessions. ONE `prices.bulk_cached_frames` find; no provider call, no Mongo write, no push.
A frequency, not an edge claim — no placebo applies.

  python -u scripts/long_term_zone_reach_rate.py --sessions 60 --boot 5000 --seed 7 --out DIR
"""
from __future__ import annotations

import argparse
import collections
import json
import math
import random
import sys
from pathlib import Path

DAYS_PER_WEEK = 5                                   # trading days in a full week (the per-week column)
CAVEAT = ("Zones applied in hindsight: today's sheet over past sessions. The live pass samples the last trade every "
          "5 minutes 09:00–16:30 ET incl. thin pre-/after-hours prints, so the real rate sits between the close and "
          "day-range rows. A frequency, not an edge claim — no placebo applies.")


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def bands(zones: dict, pad_pct: float) -> list:
    """[(zone, lo_padded, hi_padded)] for every readable zone (a None edge or lo > hi is skipped)."""
    out = []
    for zk, pair in (zones or {}).items():
        pair = list(pair or (None, None)) + [None, None]
        lo, hi = _num(pair[0]), _num(pair[1])
        if lo is None or hi is None or lo > hi:
            continue
        out.append((zk, lo * (1 - pad_pct / 100.0), hi * (1 + pad_pct / 100.0)))
    return out


def count_frame(df, zones: dict, pad_pct: float, n_sessions: int):
    """(range Counter by date, close Counter by date, dates seen) for one name's frame tail."""
    rng, cls, seen = collections.Counter(), collections.Counter(), set()
    if df is None or len(df) < 2:
        return rng, cls, seen
    df = df.tail(n_sessions + 1)
    c, h, lo_ = list(df["close"]), list(df["high"]), list(df["low"])
    idx = [str(x)[:10] for x in df.index]
    bs = bands(zones, pad_pct)
    for i in range(1, len(df)):
        seen.add(idx[i])
        pc, ci, hi_i, low_i = _num(c[i - 1]), _num(c[i]), _num(h[i]), _num(lo_[i])
        if pc is None:
            continue
        for _zk, a, b in bs:
            if a <= pc <= b:
                continue
            if hi_i is not None and low_i is not None and low_i <= b and hi_i >= a:
                rng[idx[i]] += 1
            if ci is not None and a <= ci <= b:
                cls[idx[i]] += 1
    return rng, cls, seen


def stats(counter, days: list, boot: int, seed: int) -> dict:
    xs = [counter.get(d, 0) for d in days]
    if not xs:
        return {"mean": None, "ci_lo": None, "ci_hi": None, "per_week": None, "per_week_lo": None,
                "per_week_hi": None, "max_day": None, "zero_days": None}
    m = sum(xs) / len(xs)
    r = random.Random(seed)
    bs = sorted(sum(r.choice(xs) for _ in xs) / len(xs) for _ in range(boot))
    lo, hi = bs[int(boot * 0.025)], bs[min(boot - 1, int(boot * 0.975))]
    return {"mean": round(m, 3), "ci_lo": round(lo, 3), "ci_hi": round(hi, 3),
            "per_week": round(DAYS_PER_WEEK * m, 2), "per_week_lo": round(DAYS_PER_WEEK * lo, 2),
            "per_week_hi": round(DAYS_PER_WEEK * hi, 2), "max_day": max(xs),
            "zero_days": sum(1 for x in xs if x == 0)}


def compute(entries: dict, frames: dict, *, sessions: int, boot: int, seed: int, pad_pct=None) -> dict:
    from long_term_list import constants as C
    pad = C.PANKAJ_ZONE_PAD_PCT if pad_pct is None else pad_pct
    rng_all, cls_all, days, names_rng = collections.Counter(), collections.Counter(), set(), collections.Counter()
    n_frames = 0
    n_zones = 0
    for sym, ent in (entries or {}).items():
        n_zones += len(bands(ent.get("zones") or {}, pad))
        df = (frames or {}).get(sym)
        if df is None:
            continue
        n_frames += 1
        rng, cls, seen = count_frame(df, ent.get("zones") or {}, pad, sessions)
        rng_all.update(rng)
        cls_all.update(cls)
        days |= seen
        names_rng[sym] += sum(rng.values())
    ds = sorted(days)[-sessions:]
    rng_in = collections.Counter({d: rng_all[d] for d in ds if rng_all[d]})
    return {
        "rule": (f"today's zones, {pad:g}% pad, prior close outside the zone, once per name / zone / session"),
        "pad_pct": pad,
        "sessions": {"n": len(ds), "first": ds[0] if ds else None, "last": ds[-1] if ds else None},
        "n_names": len(entries or {}), "n_names_with_frames": n_frames, "n_zones": n_zones,
        "boot": boot, "seed": seed,
        "rows": {"close": stats(cls_all, ds, boot, seed), "day_range": stats(rng_all, ds, boot, seed)},
        "top_days": [[d, n] for d, n in sorted(rng_in.items(), key=lambda t: (-t[1], t[0]))[:5]],
        "top_names": [[s, n] for s, n in names_rng.most_common(8) if n],
        "caveat": CAVEAT,
    }


def table(out: dict) -> str:
    lines = ["| read | per session | 95% CI | per week | max in a day | days with none |", "|---|---|---|---|---|---|"]
    n = out["sessions"]["n"]
    for key, label in (("close", "close inside (lower bound)"), ("day_range", "day range touches (upper bound)")):
        r = out["rows"][key]
        if r["mean"] is None:
            lines.append(f"| {label} | — | — | — | — | — |")
            continue
        lines.append(f"| {label} | {r['mean']:.2f} | {r['ci_lo']:.2f}–{r['ci_hi']:.2f} | {r['per_week']:.1f} "
                     f"({r['per_week_lo']:.1f}–{r['per_week_hi']:.1f}) | {r['max_day']} | {r['zero_days']} of {n} |")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sessions", type=int, default=60)
    ap.add_argument("--boot", type=int, default=5000)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", type=str, default=None)
    a = ap.parse_args(argv)
    from long_term_list import seed as SD
    from sepa import prices
    entries = SD.pankaj_entries(SD.load())
    frames = prices.bulk_cached_frames(sorted(entries))
    out = compute(entries, frames, sessions=a.sessions, boot=a.boot, seed=a.seed)
    print(f"sessions {out['sessions']['n']} {out['sessions']['first']} → {out['sessions']['last']} · names with "
          f"frames {out['n_names_with_frames']}/{out['n_names']} · zones {out['n_zones']}")
    print(table(out))
    print("top days (range):", out["top_days"])
    print("top names (range):", out["top_names"])
    print(out["caveat"])
    if a.out:
        p = Path(a.out)
        p.mkdir(parents=True, exist_ok=True)
        (p / "reach_rate.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
        print("wrote", p / "reach_rate.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
