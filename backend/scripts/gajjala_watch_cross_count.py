"""👀 Gajjala's Watch — how often a 9 / 21 EMA up cross happens on his tickers (read-only counts, 2026-11-15, WP-B).

For the linked HIS CALL #3 / #4 / #5 (and #16) of docs/gajjala/watch_cross_alerts_2026_11_15.md: per name-session and
frame (1 / 3 / 5-min), using `cross_alerts.watch_crosses` — exactly the crosses the chart marks [C1.5]:
  * up crosses, and how many fall pre-market / in the first NO_TRADE_AFTER_OPEN_MIN minutes / after the extended close
    (alerts.window_reason — the push window);
  * how many pass K5 (a) on the cross frame at the cross bar, (b) on the 5-min frame at its last bar ≤ the cross;
  * the LATCH LOSS: sessions with a later in-window up cross after the first one (under the default once-a-session
    latch the later one is drawn, never rung);
  * the BURST: sessions where ≥ 2 names' first in-window 1-min up cross (= the default ring) fall in the same minute,
    and the same for any in-window 1-min up cross.
Output: n names, n sessions, per frame median / p90 / total per name-session. FREQUENCY ONLY — not an edge, not a win
rate; nothing here is measured against what follows a cross (UNMEASURED).

Read-only: the minute bars come through `run._dry_load_day` (Massive, no cache write); nothing is written anywhere.

  docker exec -i -w /app <a scratch api container> python -m scripts.gajjala_watch_cross_count \
      --symbols OMH,NVDA,AMD --sessions 5 --end 2026-11-13 --json
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import date, datetime, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _p90(xs: list) -> Optional[float]:
    if not xs:
        return None
    s = sorted(xs)
    k = max(0, min(len(s) - 1, int(round(0.9 * (len(s) - 1)))))
    return float(s[k])


def _stat(xs: list) -> dict:
    return {"median": (float(statistics.median(xs)) if xs else None), "p90": _p90(xs), "total": int(sum(xs)),
            "n": len(xs)}


def _window(x: dict, session, tf: str) -> Optional[str]:
    """alerts.window_reason on the bar's START: a `tf` bar stamped at its close starts `tf` minutes earlier; judged as
    the 1-minute bar that starts at the same minute (alerts.FRAME_MINUTES has no 3m — never added here)."""
    import pandas as pd
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala_watch import constants as C
    close = AL.bar_close_et(x["ts"])
    if close is None:
        return "suppressed_window"
    start = close - pd.Timedelta(dict(C.FRAMES)[tf]).to_pytimedelta()
    one = (start + timedelta(minutes=AL.FRAME_MINUTES["1m"])).strftime("%Y-%m-%d %H:%M")
    return AL.window_reason(one, session, "1m")


def count_session(frames_by_sym: dict, session) -> dict:
    """{per: {sym: {tf: {...}}}, burst_first, burst_any} for one session's frames ({SYM: bars.Frames})."""
    from chart_maps.gajjala_watch import build as BLD
    from chart_maps.gajjala_watch import constants as C
    from chart_maps.gajjala_watch import cross_alerts as XA
    from chart_maps.gajjala import ema_cross as EX
    iso = session.isoformat() if isinstance(session, date) else str(session)[:10]
    per: dict = {}
    first_ring: dict = {}
    any_ring: dict = {}
    for sym, fr in (frames_by_sym or {}).items():
        if fr is None:
            continue
        per[sym] = {}
        for tf, _r in C.FRAMES:
            F = (getattr(fr, "by", {}) or {}).get(tf)
            if F is None:
                continue
            ups = [x for x in EX.session_crosses(XA.watch_crosses(F), iso) if x["dir"] == EX.UP]
            wins = [(x, _window(x, session, tf)) for x in ups]
            ok = [x for x, w in wins if w is None]
            per[sym][tf] = {
                "up": len(ups),
                "premarket": sum(1 for _x, w in wins if w == "suppressed_premarket"),
                "first15": sum(1 for _x, w in wins if w == "suppressed_first15"),
                "after_close": sum(1 for _x, w in wins if w == "suppressed_window"),
                "in_window": len(ok),
                "k5_cross": sum(1 for x in ups if BLD.k5(F, x["i"]) is True),
                "k5_5m": sum(1 for x in ups if XA.k5_5m_at(fr, x["ts"]) is True),
                "k5_cross_in_window": sum(1 for x in ok if BLD.k5(F, x["i"]) is True),
                "k5_5m_in_window": sum(1 for x in ok if XA.k5_5m_at(fr, x["ts"]) is True),
                "latch_loss": len(ok) >= 2,
            }
            if tf == C.PUSH_FRAMES[0] and ok:
                first_ring.setdefault(ok[0]["ts"], set()).add(sym)
                for x in ok:
                    any_ring.setdefault(x["ts"], set()).add(sym)
    return {"per": per, "burst_first": any(len(v) >= 2 for v in first_ring.values()),
            "burst_any": any(len(v) >= 2 for v in any_ring.values()),
            "burst_first_max": max((len(v) for v in first_ring.values()), default=0)}


def summarize(by_session: dict) -> dict:
    """{session: count_session(...)} → n names, n sessions, per frame median / p90 / total, latch-loss and burst counts."""
    from chart_maps.gajjala_watch import constants as C
    keys = ("up", "premarket", "first15", "after_close", "in_window", "k5_cross", "k5_5m", "k5_cross_in_window",
            "k5_5m_in_window")
    names = sorted({s for v in by_session.values() for s in v["per"]})
    out: dict = {"n_names": len(names), "n_sessions": len(by_session), "frames": {},
                 "burst_sessions_first_ring": sum(1 for v in by_session.values() if v["burst_first"]),
                 "burst_sessions_any_cross": sum(1 for v in by_session.values() if v["burst_any"]),
                 "burst_first_ring_max_names": max((v["burst_first_max"] for v in by_session.values()), default=0),
                 "note": "frequency only — not an edge; UNMEASURED"}
    for tf, _r in C.FRAMES:
        rows = [v["per"][s][tf] for v in by_session.values() for s in v["per"] if tf in v["per"][s]]
        out["frames"][tf] = {k: _stat([r[k] for r in rows]) for k in keys}
        out["frames"][tf]["latch_loss_name_sessions"] = sum(1 for r in rows if r["latch_loss"])
        out["frames"][tf]["name_sessions"] = len(rows)
    return out


def _sessions(n: int, end: Optional[date]) -> list:
    from catalysts.medical.reaction import is_market_day, prev_market_day
    d = end if (end is not None and is_market_day(end)) else prev_market_day(end or datetime.now(ET).date())
    out = []
    while len(out) < max(1, int(n)):
        out.append(d)
        d = prev_market_day(d)
    return sorted(out)


def run(symbols: list, sessions: list, load_day=None) -> dict:
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import run as RUN
    from chart_maps.gajjala_watch import build as BLD
    load = load_day or RUN._dry_load_day
    by_session: dict = {}
    stats_all: dict = {}
    for s in sessions:
        _rth, ext = AL._closes(s)
        now = datetime.combine(s, ext, tzinfo=ET) + timedelta(minutes=1)
        st: dict = {}
        fr = BLD.frames(symbols, s, now, load_day=load, budget_sec=10 ** 6, stats=st)
        by_session[s.isoformat()] = count_session(fr, s)
        for k, v in st.items():
            stats_all[k] = stats_all.get(k, 0) + v
    out = summarize(by_session)
    out["bars"] = stats_all
    out["sessions"] = [s.isoformat() for s in sessions]
    out["symbols"] = list(symbols)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_watch_cross_count", description=__doc__.split("\n")[0])
    ap.add_argument("--symbols", required=True, help="comma list")
    ap.add_argument("--sessions", type=int, default=5, help="the last N market sessions (default 5)")
    ap.add_argument("--end", help="the last session, YYYY-MM-DD (default: the last complete market session)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    syms = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]
    end = date.fromisoformat(args.end) if args.end else None
    out = run(syms, _sessions(args.sessions, end))
    if args.json:
        print(json.dumps(out, default=str))
    else:
        print(f"{out['n_names']} names × {out['n_sessions']} sessions ({', '.join(out['sessions'])}) — "
              f"{out['note']}")
        for tf, row in out["frames"].items():
            print(f"  {tf}: " + " · ".join(f"{k} med {v['median']} p90 {v['p90']} tot {v['total']}"
                                           for k, v in row.items() if isinstance(v, dict))
                  + f" · latch loss {row['latch_loss_name_sessions']}/{row['name_sessions']}")
        print(f"  burst (≥2 names, first ring same minute): {out['burst_sessions_first_ring']} sessions; "
              f"any in-window 1m cross: {out['burst_sessions_any_cross']}; bars {out['bars']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
