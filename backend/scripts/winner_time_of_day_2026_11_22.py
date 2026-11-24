"""Winner time-of-day (prereg.md). Read-only. Re-run: /Users/ajay/clinet-test/cheetah-market-app/backend/.venv/bin/python tod.py

Repo copy (2026-11-24) of /Users/ajay/clinet-test/eod-audits/research/2026-11-22_winner_time_of_day/tod.py — the script
behind backend/chart_maps/gajjala/data/winner_time_of_day_2026_11_22.json (the ⏰ time-window glow,
chart_maps/gajjala/time_windows.py; docs/gajjala/time_window_glow_2026_11_24.md). The study's logic is unchanged; three
kinds of ADDITIVE output per sample so the glow's sentences read every number from the file instead of typing it:
  · "burst_quarter_k" / "peak_quarter_k" — counts per 15-minute slot "HH:MM" (any window share = sum k / n);
  · "first_day" / "last_day" — the sample's date window;
  · "float_max_shares" — the float cap the sample was cut at (FLOAT_MAX_SHARES / FLOAT_LT_1M_SHARES, the study's own
    1e7 / 1e6, now named; None for the reel library, which is not float-cut);
  · "burst_window_min" / "min_high_gain_pct" — the burst window and the W40 rule (BURST_WINDOW_MIN / W40_HIGH_MULT, the
    study's own 30 and 1.4, now named; min_high_gain_pct None for the reel library).
Every original key is byte-for-byte the study's value (checked 2026-11-24 against the study folder's results.json).
Usage: python winner_time_of_day_2026_11_22.py [OUT_JSON]   (default results.json in the current directory, as tod.py)
Reads host-only paths under /Users/ajay/clinet-test/eod-audits (not in the container).
"""
import glob, gzip, json, math, os, sys
from datetime import date, datetime, time as dtime
from zoneinfo import ZoneInfo
import pandas as pd
ET = ZoneInfo("America/New_York")
R = "/Users/ajay/clinet-test/eod-audits/replays"
C = "/Users/ajay/clinet-test/eod-audits/research/2026-11-17_si_cradle_squeeze/out"
SH = "/Users/ajay/clinet-test/eod-audits/research/2026-11-21_lowfloat_rs_si_backtest/out/shares.json"
B = [("first hour 09:30-10:30", 570, 630), ("10:30-12:00", 630, 720), ("12:00-14:00", 720, 840),
     ("last 2h 14:00-16:00", 840, 960), ("after hours 16:00-20:00", 960, 1200)]
FLOAT_MAX_SHARES = 1e7          # the study's W40 universe cut (tod.py `fl > 1e7`)
FLOAT_LT_1M_SHARES = 1e6        # the study's float < 1M sub-sample (tod.py `r["fl"] < 1e6`)
BURST_WINDOW_MIN = 30           # the study's burst window (tod.py `mins[i] - mins[j] >= 30`)
W40_HIGH_MULT = 1.4             # the study's W40 rule (tod.py `ph < 1.4 * d1`): 09:30-20:00 high >= +40 % vs prior close


def wil(k, n, z=1.96):
    if not n:
        return [None, None]
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(100 * (c - h), 1), round(100 * (c + h), 1)]


def bucket(m):
    for name, a, b in B:
        if a <= m < b:
            return name
    return None


def measures(mins, hi, lo, op):
    """mins: minute-of-day list (ET) inside 09:30-20:00; hi/lo lists aligned; op = 09:30 open."""
    if not mins:
        return None
    k = max(range(len(hi)), key=lambda i: hi[i])
    best, bt = -1, None
    j = 0
    for i in range(len(mins)):
        while mins[i] - mins[j] >= BURST_WINDOW_MIN:
            j += 1
        lo_ = min(lo[j:i + 1])
        g = hi[i] / lo_ - 1 if lo_ > 0 else -1
        if g > best:
            best, bt = g, mins[j]
    first25 = next((mins[i] for i in range(len(mins)) if op and hi[i] >= 1.25 * op), None)
    return {"peak": mins[k], "burst": bt, "burst_pct": 100 * best, "first25": first25}


def table(rows, key):
    n = sum(1 for r in rows if r.get(key) is not None)
    out = []
    for name, a, b in B:
        k = sum(1 for r in rows if r.get(key) is not None and a <= r[key] < b)
        out.append({"bucket": name, "k": k, "n": n, "pct": round(100 * k / n, 1) if n else None, "ci": wil(k, n),
                    "null_pct": round(100 * (b - a) / 630, 1)})
    return out


def hourly(rows, key):
    n = sum(1 for r in rows if r.get(key) is not None)
    h = {}
    for r in rows:
        if r.get(key) is not None:
            hh = r[key] // 60
            h[hh] = h.get(hh, 0) + 1
    return {f"{hh:02d}:00": round(100 * v / n, 1) for hh, v in sorted(h.items())}


def quarter_k(rows, key):
    """ADDED 2026-11-24 — counts (not shares) per 15-minute slot, keyed by the slot's start "HH:MM"."""
    h = {}
    for r in rows:
        if r.get(key) is not None:
            q = (r[key] // 15) * 15
            h[q] = h.get(q, 0) + 1
    return {f"{q // 60:02d}:{q % 60:02d}": v for q, v in sorted(h.items())}


A = []
for f in sorted(glob.glob(os.path.join(R, "videos/winners/*_45x.json"))):
    j = json.load(open(f))
    p = os.path.join(R, "_bars/winners", f"min_{j['symbol']}_{j['base_day']}_{j['day']}.pkl.gz")
    if not os.path.exists(p):
        continue
    m = pd.read_pickle(p)
    idx = m.index if m.index.tz is not None else m.index.tz_localize("UTC")
    m = m.set_axis(idx.tz_convert(ET))
    m = m[m.index.date == date.fromisoformat(j["day"])]
    mm = [t.hour * 60 + t.minute for t in m.index]
    keep = [i for i, x in enumerate(mm) if 570 <= x < 1200]
    if not keep:
        continue
    r = measures([mm[i] for i in keep], [float(m["high"].iloc[i]) for i in keep], [float(m["low"].iloc[i]) for i in keep], j.get("open"))
    r.update(sym=j["symbol"], day=j["day"])
    A.append(r)

ev = json.load(open(os.path.join(C, "events.json")))
sh = json.load(open(SH))
cache, Bd = {}, []
for e in ev:
    if "day" not in e or not (e.get("h") or {}).get("d1_close"):
        continue
    s = e["symbol"]; fl = (sh.get(s) or {}).get("float_shares")
    if not fl or fl > FLOAT_MAX_SHARES:
        continue
    if s not in cache:
        p = os.path.join(C, "bars", s + ".json.gz")
        cache[s] = json.load(gzip.open(p))["days"] if os.path.exists(p) else None
    v = cache[s] and cache[s].get(e["date"])
    if not v or not v["high"]:
        continue
    d1 = e["h"]["d1_close"]
    mm = [datetime.fromtimestamp(t / 1000, ET) for t in v["t"]]
    mi = [x.hour * 60 + x.minute for x in mm]
    keep = [i for i in range(len(mi)) if 570 <= mi[i] < 1200]
    pm = [v["high"][i] for i in range(len(mi)) if 240 <= mi[i] < 570]
    if not keep:
        continue
    ph = max(v["high"][i] for i in keep)
    if ph < W40_HIGH_MULT * d1 or (pm and max(pm) > ph):
        continue
    op = v["open"][keep[0]] if mi[keep[0]] < 575 else None
    r = measures([mi[i] for i in keep], [v["high"][i] for i in keep], [v["low"][i] for i in keep], op)
    r.update(sym=s, day=e["date"], fl=fl)
    Bd.append(r)

res = {}
for name, rows, fcap in (("A_library_301", A, None), ("B_w40_universe", Bd, FLOAT_MAX_SHARES),
                         ("B_w40_float_lt_1M", [r for r in Bd if r["fl"] < FLOAT_LT_1M_SHARES], FLOAT_LT_1M_SHARES)):
    days = sorted(r["day"] for r in rows)
    res[name] = {"n_days": len(rows), "symbols": len({r["sym"] for r in rows}),
                 "peak": table(rows, "peak"), "burst": table(rows, "burst"), "first25": table(rows, "first25"),
                 "peak_hourly": hourly(rows, "peak"), "burst_hourly": hourly(rows, "burst"),
                 "burst_quarter_k": quarter_k(rows, "burst"), "peak_quarter_k": quarter_k(rows, "peak"),
                 "first_day": days[0] if days else None, "last_day": days[-1] if days else None,
                 "float_max_shares": fcap, "burst_window_min": BURST_WINDOW_MIN,
                 "min_high_gain_pct": round(100 * (W40_HIGH_MULT - 1)) if fcap is not None else None}
json.dump(res, open(sys.argv[1] if len(sys.argv) > 1 else "results.json", "w"), indent=1)
for name, r in res.items():
    print(f"\n=== {name}  days {r['n_days']}  symbols {r['symbols']}")
    for key in ("peak", "burst", "first25"):
        print(" --", key)
        for t in r[key]:
            print(f"   {t['bucket']:26s} {t['k']:4d}/{t['n']:4d} = {t['pct']:5}% {t['ci']}  (share of the day {t['null_pct']}%)")
    print("   peak by hour:", r["peak_hourly"])
    print("   burst by hour:", r["burst_hourly"])
