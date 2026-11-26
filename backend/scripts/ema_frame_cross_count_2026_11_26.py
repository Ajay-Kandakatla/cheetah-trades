"""ema-verify (2026-11-26) — how many more 9-under-21 down-crosses does the 1-minute chart print than the 5-minute chart?

Ajay, verbatim (2026-11-26): "I am re checking Gajjals video on youtube and noticied that his charts are very clean in
action like the 9 EMA is not crossing over down below 21 as much and also can you verify is we are following this
properly."

The question, fixed BEFORE the run (spec runcharts rev 2 §3.10): on the same minutes, with the same engine, how many more
times does the 9 EMA cross under the 21 on the 1-minute chart (the 👀 Watch's first chart, `gajjala_watch.constants.FRAMES`
[0]) than on the 5-minute chart (GG's, `gajjala.constants.RUN_BASE_FRAME`), per session?

READ-ONLY. Minutes come from the 1-minute cache through `daytrading.data._mongo_get_day` and NOTHING else: never the
fetching loader, never the provider, never a write. A day that is not in the cache is skipped and counted.

One engine per concept, imported, never retyped:
  * sessions kept: `dt_data._filter_sessions(df, True, True)` (pre-market + regular + after-hours);
  * 1m -> N: `supply_demand.timeframes.resample_ohlcv` at each rule of `gajjala_watch.constants.FRAMES`;
  * the 9 / 21 EMA frame: `chart_maps.gajjala.bars.build_frame` over [the market day before, when cached = warm-up] +
    [the day]; a completed day has no forming bar, so no settle cut;
  * THE cross rule: `chart_maps.gajjala.ema_cross.frame_crosses(F)` on the day's own bars (`F.today`), split by
    `EC.DOWN` / `EC.UP`;
  * runners: the 📅 strip's own rule, `gajjala_watch.runners.strip(<day> 23:00 ET)["rows"]`;
  * the placebo: the scanner's names of the SAME day that did not run (`runners.read_day(...)[0]` minus the runners),
    a seeded sample of as many cached names as that day's cached runners;
  * market days: `catalysts.medical.reaction.prev_market_day` / `is_market_day`.

PRIMARY (runners): mean over name-days of down_1m - down_5m, 95% percentile CI from a CLUSTER bootstrap by SYMBOL (all
of a symbol's days travel together). Fewer than MIN_CLUSTERS symbols in a group -> the CI is null and the text says "too
few names", never an interval. Descriptive: a COUNT of crosses, not an edge — no rule, gate or default moves on it.

Known filter (printed with the result): a run day is in the cache only when some pass read the name on a LATER day. The
placebo passes the same filter, so the comparison is like for like.

Run (outside regular hours of a market day; reads the cache only):
  docker exec -i -w /app cheetah-market-app-api-1 python - --json < backend/scripts/ema_frame_cross_count_2026_11_26.py
Render a saved run (reads no cache):
  python scripts/ema_frame_cross_count_2026_11_26.py --markdown scripts/ema_frame_cross_count_2026_11_26.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import date, datetime, timezone
from typing import Callable, Optional
from zoneinfo import ZoneInfo

import pandas as pd

ET = ZoneInfo("America/New_York")

SEED = 20261126; BOOT_N = 10_000; MIN_CLUSTERS = 10            # study parameters — MINE, printed in the output
DEFAULT_SESSIONS = 15                                           # spec §3.10 `--sessions` default — MINE
GROUPS = ("runner", "other")                                    # "other" = the placebo: scanner names that did not run
CI_LEVEL = 0.95
DP = 4                                                          # printed decimals of a point / a bound
TOO_FEW_TEXT = "too few names ({k} symbols < {m}) — no interval"
FILTER_TEXT = ("A run day is in the cache only when some pass read the name on a LATER day; the placebo passes the same "
               "filter, so the comparison is like for like. The runner numbers describe runners that stayed on the "
               "scanner.")
QUESTION = ("On the same minutes, with the same engine, how many more times does the 9 EMA cross under the 21 on the "
            "{a} chart (the Watch's first chart) than on the {b} chart (GG's), per session?")
MARK_BEGIN = "<!-- ema-frame-count:begin -->"
MARK_END = "<!-- ema-frame-count:end -->"


# ── engines (imported at call time so a test can monkeypatch the constant it names) ──────────────────────────────
def _frames() -> tuple:
    from chart_maps.gajjala_watch import constants as WC
    return tuple(WC.FRAMES)


def _tf_names() -> tuple:
    """(first, gg, slow) — the Watch's first frame, GG's frame, the slowest frame — all read BY NAME."""
    from chart_maps.gajjala import constants as GC
    fr = _frames()
    return fr[0][0], GC.RUN_BASE_FRAME, fr[-1][0]


def _prev_market_day(d: date) -> date:
    from catalysts.medical.reaction import prev_market_day
    return prev_market_day(d)


def _is_market_day(d: date) -> bool:
    from catalysts.medical.reaction import is_market_day
    return is_market_day(d)


def _keep_sessions(df):
    """pre-market + regular + after-hours (the loader's own filter), index as naive UTC (build_frame's convention)."""
    from daytrading import data as dt_data
    if df is None or len(df) == 0:
        return None
    df = dt_data._filter_sessions(df, True, True)
    if df is None or len(df) == 0:
        return None
    if getattr(df.index, "tz", None) is not None:
        df = df.copy()
        df.index = df.index.tz_convert("UTC").tz_localize(None)
    return df


# ── the unit: one name-day ───────────────────────────────────────────────────────────────────────────────────────
def frame_for(prev_df, day_df, day_iso: str, tf: str):
    """bars.Frame over [prev (warm-up only)] + [day] at frame `tf` (a key of FRAMES); None when the day has no bar."""
    from chart_maps.gajjala import bars as B
    from supply_demand.timeframes import resample_ohlcv
    rule = dict(_frames())[tf]
    parts = [p for p in (_keep_sessions(prev_df), _keep_sessions(day_df)) if p is not None]
    if not parts:
        return None
    raw = pd.concat(parts).sort_index()
    raw = raw[~raw.index.duplicated(keep="last")]
    res = resample_ohlcv(raw, rule)
    if res is None or res.empty:
        return None
    F = B.build_frame(res, day_iso, rule)
    return F if len(F.today) else None


def counts(F) -> dict:
    """{"bars", "down", "up"} on the day's own bars, through THE cross engine (ema_cross.frame_crosses)."""
    from chart_maps.gajjala import ema_cross as EC
    xs = EC.frame_crosses(F)
    return {"bars": len(F.today) if F is not None else 0,
            "down": sum(1 for x in xs if x.get("dir") == EC.DOWN),
            "up": sum(1 for x in xs if x.get("dir") == EC.UP)}


def _empty(df) -> bool:
    return df is None or len(df) == 0


def name_day(sym, day, *, get_day) -> Optional[dict]:
    """{"symbol", "day", "warm", "frames": {tf: counts | None}} — None when the day is not in the cache.
    `warm` = the market day before was in the cache too (it warms the EMAs only; its crosses are never counted)."""
    day_df = get_day(sym, day)
    if _empty(day_df):
        return None
    prev_df = get_day(sym, _prev_market_day(day))
    warm = not _empty(_keep_sessions(prev_df))
    iso = day.isoformat()
    frames = {}
    for tf, _rule in _frames():
        F = frame_for(prev_df, day_df, iso, tf)
        frames[tf] = counts(F) if F is not None else None
    return {"symbol": sym, "day": iso, "warm": warm, "frames": frames}


def _norm(names) -> list:
    out = []
    for n in names or []:
        if isinstance(n, str) and n.strip() and n.strip().upper() not in out:
            out.append(n.strip().upper())
    return out


def population(end, sessions, *, runners_of, universe_of, get_day, seed=SEED) -> dict:
    """Walk `sessions` market days back from `end` (inclusive). Per day: every runner whose day is cached, then a
    seeded sample of the day's non-runner scanner names whose day is cached, as many as the cached runners."""
    d = end if _is_market_day(end) else _prev_market_day(end)
    rows, days = [], []
    skipped = {"days_no_runner": 0, "runner_not_cached": 0, "other_not_cached": 0,
               "runner_frame_no_bars": 0, "other_frame_no_bars": 0}
    for _ in range(max(0, int(sessions))):
        iso = d.isoformat()
        runners = _norm(runners_of(d))
        info = {"day": iso, "runners": len(runners), "runners_cached": 0, "others_pool": 0, "others_sampled": 0}
        if not runners:
            skipped["days_no_runner"] += 1
            days.append(info)
            d = _prev_market_day(d)
            continue
        for sym in runners:
            r = name_day(sym, d, get_day=get_day)
            if r is None:
                skipped["runner_not_cached"] += 1
                continue
            skipped["runner_frame_no_bars"] += sum(1 for v in r["frames"].values() if v is None)
            rows.append({**r, "group": GROUPS[0]})
            info["runners_cached"] += 1
        want = info["runners_cached"]
        pool = sorted(set(_norm(universe_of(d))) - set(runners))
        info["others_pool"] = len(pool)
        random.Random(f"{seed}|{iso}").shuffle(pool)
        for sym in pool:
            if info["others_sampled"] >= want:
                break
            r = name_day(sym, d, get_day=get_day)
            if r is None:
                skipped["other_not_cached"] += 1
                continue
            skipped["other_frame_no_bars"] += sum(1 for v in r["frames"].values() if v is None)
            rows.append({**r, "group": GROUPS[1]})
            info["others_sampled"] += 1
        days.append(info)
        d = _prev_market_day(d)
    return {"rows": rows, "skipped": skipped, "days": days}


# ── statistics ───────────────────────────────────────────────────────────────────────────────────────────────────
def _pct(sorted_vals: list, q: float) -> float:
    """Linear-interpolation percentile of an ascending list (numpy's default rule)."""
    k = (len(sorted_vals) - 1) * q
    lo = math.floor(k)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def _interval(draws: list) -> Optional[tuple]:
    vals = sorted(x for x in draws if x is not None and math.isfinite(x))
    if not vals:
        return None
    a = (1 - CI_LEVEL) / 2
    return (_pct(vals, a), _pct(vals, 1 - a))


def boot_ci(by_symbol: dict, stat, *, n=BOOT_N, seed=SEED):
    """95% percentile CI of `stat(rows)` under a CLUSTER bootstrap: draw len(by_symbol) symbols with replacement, every
    row of a drawn symbol travels with it. Fewer than MIN_CLUSTERS symbols -> None (never an interval)."""
    keys = sorted(by_symbol)
    if len(keys) < MIN_CLUSTERS:
        return None
    rng = random.Random(seed)
    draws = []
    for _ in range(int(n)):
        rows = []
        for k in rng.choices(keys, k=len(keys)):
            rows.extend(by_symbol[k])
        draws.append(stat(rows))
    return _interval(draws)


def _boot_diff(a_by: dict, b_by: dict, stat, *, n=BOOT_N, seed=SEED):
    """CI of stat(a) - stat(b) under ONE cluster bootstrap over the UNION of the two groups' symbols: each draw picks
    len(union) symbols with replacement, and a drawn symbol brings ALL its rows of BOTH groups — a symbol that sits in
    both groups (on different days) is one cluster, never two independent ones. Either group under MIN_CLUSTERS
    symbols -> None (never an interval). A draw that leaves a group empty is dropped (stat None)."""
    ka, kb = sorted(a_by), sorted(b_by)
    if len(ka) < MIN_CLUSTERS or len(kb) < MIN_CLUSTERS:
        return None
    keys = sorted(set(ka) | set(kb))
    rng = random.Random(seed)
    draws = []
    for _ in range(int(n)):
        ra, rb = [], []
        for k in rng.choices(keys, k=len(keys)):
            ra.extend(a_by.get(k, ()))
            rb.extend(b_by.get(k, ()))
        x, y = stat(ra), stat(rb)
        draws.append(None if x is None or y is None else x - y)
    return _interval(draws)


def _v(r: dict, tf: str, key: str):
    c = (r.get("frames") or {}).get(tf)
    return None if c is None else c.get(key)


def _mean_diff(a: str, b: str, key: str) -> Callable:
    def f(rows):
        xs = [_v(r, a, key) - _v(r, b, key) for r in rows if _v(r, a, key) is not None and _v(r, b, key) is not None]
        return sum(xs) / len(xs) if xs else None
    return f


def _mean(tf: str, key: str) -> Callable:
    def f(rows):
        xs = [_v(r, tf, key) for r in rows if _v(r, tf, key) is not None]
        return sum(xs) / len(xs) if xs else None
    return f


def _ratio(a: str, b: str, key: str) -> Callable:
    """sum(key on a) / sum(key on b) over rows holding both frames; None when the denominator is 0."""
    def f(rows):
        ok = [r for r in rows if _v(r, a, key) is not None and _v(r, b, key) is not None]
        den = sum(_v(r, b, key) for r in ok)
        return sum(_v(r, a, key) for r in ok) / den if ok and den else None
    return f


def _per100(tf: str) -> Callable:
    def f(rows):
        ok = [r for r in rows if _v(r, tf, "bars") is not None]
        den = sum(_v(r, tf, "bars") for r in ok)
        return 100.0 * sum(_v(r, tf, "down") for r in ok) / den if den else None
    return f


def _by_symbol(rows) -> dict:
    out: dict = {}
    for r in rows:
        out.setdefault(r["symbol"], []).append(r)
    return out


def _rnd(x):
    return None if x is None else round(float(x), DP)


def _stat_block(rows, stat, *, n, seed) -> dict:
    by = _by_symbol(rows)
    ci = boot_ci(by, stat, n=n, seed=seed) if rows else None
    return {"point": _rnd(stat(rows)) if rows else None,
            "ci": [_rnd(ci[0]), _rnd(ci[1])] if ci is not None else None,
            "ci_text": None if ci is not None else TOO_FEW_TEXT.format(k=len(by), m=MIN_CLUSTERS),
            "n_name_days": len(rows), "n_symbols": len(by)}


def _stats(first: str, gg: str, slow: str, frames: list) -> list:
    """(key, label, stat) — every number of the summary, in print order."""
    out = [("primary", f"mean(down_{first} − down_{gg}) per name-day", _mean_diff(first, gg, "down")),
           ("ratio_down", f"Σdown_{first} / Σdown_{gg}", _ratio(first, gg, "down")),
           ("diff_down_gg_slow", f"mean(down_{gg} − down_{slow}) per name-day", _mean_diff(gg, slow, "down"))]
    out += [(f"mean_down_{tf}", f"mean down-crosses per name-day, {tf}", _mean(tf, "down")) for tf in frames]
    out += [(f"down_per_100_bars_{tf}", f"down-crosses per 100 bars, {tf}", _per100(tf)) for tf in frames]
    out += [("up_diff", f"mean(up_{first} − up_{gg}) per name-day", _mean_diff(first, gg, "up")),
            ("ratio_up", f"Σup_{first} / Σup_{gg}", _ratio(first, gg, "up"))]
    return out


def summary(rows, *, n=BOOT_N, seed=SEED) -> dict:
    """Every number of §3.10 per group (runner / other), the warm-only sensitivity and runner ratio − placebo ratio."""
    first, gg, slow = _tf_names()
    frames = [tf for tf, _r in _frames()]
    stats = _stats(first, gg, slow, frames)
    out = {"frames": frames, "first": first, "gg": gg, "slow": slow, "labels": {k: lab for k, lab, _s in stats},
           "groups": {}}
    by_group = {g: [r for r in rows if r.get("group") == g] for g in GROUPS}
    for g, grows in by_group.items():
        block = {k: _stat_block(grows, s, n=n, seed=seed) for k, _lab, s in stats}
        warm = [r for r in grows if r.get("warm")]
        block["warm_only"] = {k: _stat_block(warm, s, n=n, seed=seed) for k, _lab, s in stats[:2]}
        block["n_name_days"] = len(grows)
        block["n_symbols"] = len(_by_symbol(grows))
        block["n_warm"] = len(warm)
        out["groups"][g] = block
    ra, rb = _by_symbol(by_group[GROUPS[0]]), _by_symbol(by_group[GROUPS[1]])
    rat = _ratio(first, gg, "down")
    px, py = rat(by_group[GROUPS[0]]), rat(by_group[GROUPS[1]])
    ci = _boot_diff(ra, rb, rat, n=n, seed=seed)
    out["runner_minus_other_ratio_down"] = {
        "point": None if px is None or py is None else _rnd(px - py),
        "ci": [_rnd(ci[0]), _rnd(ci[1])] if ci is not None else None,
        "ci_text": None if ci is not None else TOO_FEW_TEXT.format(k=min(len(ra), len(rb)), m=MIN_CLUSTERS)}
    return out


# ── the doc's table, GENERATED ───────────────────────────────────────────────────────────────────────────────────
def _num(x) -> str:
    return "—" if x is None else f"{x:.2f}"


def _ci(b: dict) -> str:
    if b.get("ci") is None:
        return b.get("ci_text") or "—"
    lo, hi = b["ci"]
    return f"[{_num(lo)}, {_num(hi)}]"


def render_markdown(out: dict) -> str:
    """The doc's table from a saved run — never typed. A NOT RUN file renders one honest line."""
    if out.get("not_run"):
        return "**NOT RUN** — " + str(out.get("reason") or "no run was made") + ". No number is shown."
    s, p = out["summary"], out["params"]
    G = s["groups"]
    r, o = G.get(GROUPS[0], {}), G.get(GROUPS[1], {})
    lines = [f"Run {out.get('generated_at', '—')} · sessions {p['sessions']} ending {p['end']} · frames "
             f"{', '.join(s['frames'])} (Watch first = {s['first']}, GG = {s['gg']}) · EMA {p['ema_fast']} / "
             f"{p['ema_slow']} · cluster bootstrap by symbol, {p['boot_n']:,} draws, seed {p['seed']}, "
             f"CI {int(p['ci_level'] * 100)}% · fewer than {p['min_clusters']} symbols → no interval.", "",
             f"| Number | Runners (point) | Runners {int(p['ci_level'] * 100)}% CI | Placebo (point) | "
             f"Placebo {int(p['ci_level'] * 100)}% CI |", "|---|---|---|---|---|"]
    for k, lab in s["labels"].items():
        a, b = r.get(k) or {}, o.get(k) or {}
        name = f"**PRIMARY — {lab}**" if k == "primary" else lab
        lines.append(f"| {name} | {_num(a.get('point'))} | {_ci(a)} | {_num(b.get('point'))} | {_ci(b)} |")
    for k in ("primary", "ratio_down"):
        a, b = (r.get("warm_only") or {}).get(k) or {}, (o.get("warm_only") or {}).get(k) or {}
        lines.append(f"| warm-only: {s['labels'][k]} | {_num(a.get('point'))} | {_ci(a)} | {_num(b.get('point'))} | "
                     f"{_ci(b)} |")
    d = s.get("runner_minus_other_ratio_down") or {}
    lines += ["", f"Runner ratio − placebo ratio (Σdown_{s['first']} / Σdown_{s['gg']}): **{_num(d.get('point'))}** "
                  f"{_ci(d)}.", ""]
    days = out.get("days") or []
    with_r = [x["day"] for x in days if x.get("runners")]
    sk = out.get("skipped") or {}
    lines += [f"n — runners: {r.get('n_name_days', 0)} name-days / {r.get('n_symbols', 0)} symbols "
              f"({r.get('n_warm', 0)} warm) · placebo: {o.get('n_name_days', 0)} name-days / {o.get('n_symbols', 0)} "
              f"symbols ({o.get('n_warm', 0)} warm).",
              f"Days walked: {len(days)} ({days[-1]['day'] if days else '—'} → {days[0]['day'] if days else '—'}); "
              f"with a runner: {len(with_r)} ({min(with_r) if with_r else '—'} → {max(with_r) if with_r else '—'}).",
              "Skipped (counted): " + " · ".join(f"{k} {v}" for k, v in sk.items()) + ".",
              f"Known filter: {out.get('filter_text', FILTER_TEXT)}"]
    return "\n".join(lines)


# ── the run ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _default_readers():
    from chart_maps.gajjala_watch import runners as RN
    from daytrading import data as dt_data
    from sepa.symbols import for_massive

    def get_day(s, d):
        return dt_data._mongo_get_day(for_massive(s), d)

    def runners_of(d):
        return [r["symbol"] for r in RN.strip(datetime(d.year, d.month, d.day, 23, 0, tzinfo=ET)).get("rows") or []]

    def universe_of(d):
        return list(RN.read_day(RN._store(), d.isoformat())[0])

    return get_day, runners_of, universe_of


def run(end: date, sessions: int, *, get_day, runners_of, universe_of, n=BOOT_N, seed=SEED) -> dict:
    from chart_maps.gajjala import constants as GC
    pop = population(end, sessions, runners_of=runners_of, universe_of=universe_of, get_day=get_day, seed=seed)
    first, gg, _slow = _tf_names()
    return {"study": "ema_frame_cross_count_2026_11_26", "not_run": False,
            "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "question": QUESTION.format(a=first, b=gg),
            "params": {"seed": seed, "boot_n": int(n), "min_clusters": MIN_CLUSTERS, "ci_level": CI_LEVEL,
                       "sessions": int(sessions), "end": end.isoformat(), "ema_fast": GC.EMA_FAST,
                       "ema_slow": GC.EMA_SLOW, "frames": [list(x) for x in _frames()]},
            "filter_text": FILTER_TEXT, "days": pop["days"], "skipped": pop["skipped"],
            "summary": summary(pop["rows"], n=n, seed=seed), "rows": pop["rows"]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="ema-verify: 9-under-21 down-crosses per session at 1 / 5 / 15-min")
    ap.add_argument("--sessions", type=int, default=DEFAULT_SESSIONS)
    ap.add_argument("--end", type=str, default=None, help="YYYY-MM-DD (default: the last completed session)")
    ap.add_argument("--json", action="store_true", help="print the run's JSON on stdout")
    ap.add_argument("--markdown", type=str, default=None, help="render a saved JSON file (reads no cache)")
    a = ap.parse_args(argv)
    if a.markdown:
        with open(a.markdown, encoding="utf-8") as fh:
            sys.stdout.write(render_markdown(json.load(fh)) + "\n")
        return 0
    end = (date.fromisoformat(a.end) if a.end
           else _prev_market_day(datetime.now(ET).date()))
    get_day, runners_of, universe_of = _default_readers()
    out = run(end, a.sessions, get_day=get_day, runners_of=runners_of, universe_of=universe_of)
    if a.json:
        sys.stdout.write(json.dumps(out, indent=1, allow_nan=False) + "\n")
    else:
        sys.stdout.write(render_markdown(out) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
