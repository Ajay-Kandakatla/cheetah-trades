"""🚩 His own dated examples through our detectors (WP6 replay, 2026-10-13).

WHAT. Every dated chart in the verified set (STRATEGY_SPEC WP6 list) is replayed through the tab's five detectors
(`detectors.read_all`) on the same 5-minute pass grid the study uses (`gajjala_study.prefix_frame` / `pass_grid`: at a
pass only the bars closed by then exist). For each example and each setting it prints the BEST state the setup reached
that session (aplus > triggered > stopped > broke-not-A+ > forming-ready > forming > partial > invalid > none), the
entry bar, trigger / stop, and the rules missed at that nearest-miss pass. The shipped constants are one setting; each
Round-1 alternative (STRATEGY_SPEC §7 R1-4 … R1-8) is another, applied by patching `constants` for the replay only.
Since 2026-10-14 (run-1 critic M3) each row also carries the LONGEST base / pullback / cycle count a live structure
reached that session and the FIRST rule that failed there (`Longest`), because the best-state order hides how far a
base got (every Horizontal Fade row of run 1 read "base 0 of 6 bars").

EVENT SEEDS, NOT LABELS FOR A BACKTEST. A dozen hand-picked charts say whether our reading of his words matches his own
reading of his own chart — they say nothing about whether the setup pays. That is gajjala_study.py's job.

THE DATES. Several come from a screenshot's "D:" readout, which is the CURSOR's date, not necessarily the move's. Each
date is bar-checked first: the session must reach his scanner (the qualification minute exists — price band, 1M shares,
+25% on the prior close). A date that fails is reported "date unverified" and NOT replayed. A ticker with no bars is
retried under its rename (`sepa.symbols.resolve` / `former_names`) and otherwise reported "no bars" — never skipped
silently. 🎾 has no point-in-time float: its structure is read with the float gate NOT applied (said on every row).

RUN (host or a THROWAWAY container, outside RTH; HTTP into its own file cache, no Mongo):
  cd backend && .venv/bin/python -m scripts.gajjala_examples --cache /tmp/gajjala_examples_cache \\
      --out /tmp/gajjala_examples_out
  replay a captured fixture set without HTTP: --cache tests/fixtures/gajjala_examples --offline
"""
from __future__ import annotations

import argparse
import contextlib
import json
import logging
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from chart_maps.gajjala import constants as GC
from chart_maps.gajjala import detectors as D
from chart_maps.gajjala.bars import build_frames
from scripts import gajjala_study as S
from sepa import symbols

log = logging.getLogger("scripts.gajjala_examples")

# The dated examples of the verified set (STRATEGY_SPEC WP6). label = his own call on the chart.
EXAMPLES = (
    {"ticker": "VCIG", "date": "2023-07-19", "setup": "bull_flag", "label": "valid", "frame": "5m"},
    {"ticker": "SECO", "date": "2023-10-11", "setup": "bull_flag", "label": "valid (after-hours)", "frame": "5m"},
    {"ticker": "OPGN", "date": "2023-10-11", "setup": "bull_flag", "label": "valid", "frame": "5m"},
    {"ticker": "FEMY", "date": "2023-10-20", "setup": "bull_flag", "label": "valid", "frame": "15m"},
    {"ticker": "OCX", "date": "2021-08-12", "setup": "bull_flag", "label": "INVALID (climax first bar)", "frame": "5m"},
    {"ticker": "PALT", "date": "2021-09-29", "setup": "horizontal_fade", "label": "valid", "frame": "5m"},
    {"ticker": "SPRB", "date": "2021-12-17", "setup": "horizontal_fade", "label": "valid", "frame": "5m"},
    {"ticker": "BWV", "date": "2022-05-09", "setup": "horizontal_fade", "label": "INVALID (impatient entry)",
     "frame": "5m"},
    {"ticker": "APLD", "date": "2022-07-25", "setup": "horizontal_fade", "label": "valid", "frame": "15m"},
    {"ticker": "PXMD", "date": "2022-09-12", "setup": "horizontal_fade", "label": "valid", "frame": "5m"},
    {"ticker": "MEGL", "date": "2023-01-05", "setup": "horizontal_fade", "label": "valid", "frame": "5m"},
    {"ticker": "VVOS", "date": "2023-11-29", "setup": "horizontal_fade", "label": "valid", "frame": "15m"},
    {"ticker": "MLGO", "date": "2023-12-06", "setup": "horizontal_fade", "label": "valid", "frame": "5m"},
    {"ticker": "OPTX", "date": "2023-11-17", "setup": "intraday_vcp", "label": "valid", "frame": "5m"},
    {"ticker": "ELEV", "date": "2024-01-16", "setup": "intraday_vcp", "label": "valid (cursor date — bar-check)",
     "frame": "5m"},
    {"ticker": "PSQH", "date": "2023-07-07", "setup": "reversal_squeeze", "label": "valid", "frame": "5m"},
    {"ticker": "TPST", "date": "2023-10-12", "setup": "reversal_squeeze", "label": "valid", "frame": "5m"},
    {"ticker": "POL", "date": "2023-12-20", "setup": "reversal_squeeze", "label": "valid", "frame": "5m"},
    {"ticker": "BACK", "date": "2023-12-26", "setup": "reversal_squeeze", "label": "valid", "frame": "5m"},
    {"ticker": "FFIE", "date": "2024-05-15", "setup": "reversal_squeeze", "label": "valid", "frame": "5m"},
    {"ticker": "ABVC", "date": "2024-01-03", "setup": None, "label": "his loss", "frame": "5m"},
    {"ticker": "DWAC", "date": "2024-01-17", "setup": None, "label": "his B+", "frame": "5m"},
    {"ticker": "PCSA", "date": "2024-01-25", "setup": None, "label": "his trade", "frame": "5m"},
    {"ticker": "NEXI", "date": "2024-01-30", "setup": "kiss_fly", "label": "his A+ (never touched the 9 EMA)",
     "frame": "5m"},
    {"ticker": "NVIV", "date": "2024-02-06", "setup": None, "label": "his trade", "frame": "5m"},
    {"ticker": "EBS", "date": "2024-02-21", "setup": None, "label": "his trade", "frame": "5m"},
    {"ticker": "CGC", "date": "2024-03-26", "setup": None, "label": "classic momentum breakout", "frame": "5m"},
)

# Settings = the shipped constants plus each Round-1 option (STRATEGY_SPEC §7), as constant overrides. `setups` = the
# setups a setting can move (the replay prints only those rows for it).
SETTINGS = {
    "shipped": {"overrides": {}, "setups": GC.SETUPS},
    "R1-4a flag 1–3 only": {"overrides": {"K4_BF_LONG_FLAG_MAX": None}, "setups": ("bull_flag",)},
    "R1-4b flag 1–5 A+": {"overrides": {"K4_BF_PULL_MAX": GC.K4_BF_LONG_FLAG_MAX, "K4_BF_LONG_FLAG_MAX": None},
                          "setups": ("bull_flag",)},
    "R1-5 first-bar step": {"overrides": {"K2_CHECK_FIRST_BAR": True},
                            "setups": ("bull_flag", "kiss_fly", "horizontal_fade", "intraday_vcp")},
    "R1-6a kiss bar only": {"overrides": {"KF_HONOR_ALL_PULLBACK_CLOSES": False}, "setups": ("kiss_fly",)},
    "R1-6b pullback ≤ 8": {"overrides": {"K4_KF_PULL_MAX": 8}, "setups": ("kiss_fly",)},
    "R1-6b pullback ≤ 12": {"overrides": {"K4_KF_PULL_MAX": 12}, "setups": ("kiss_fly",)},
    "R1-6c no near-kiss": {"overrides": {"KF_ALLOW_NO_TOUCH": False}, "setups": ("kiss_fly",)},
    "R1-7 prior-bar trigger": {"overrides": {"HF_TRIGGER": "prior_bar"}, "setups": ("horizontal_fade",)},
    "R1-8 strict VCP": {"overrides": {"VCP_B_READS": False}, "setups": ("intraday_vcp",)},
    "R1-8 pivots 3": {"overrides": {"VCP_PIVOT_WINDOW": 3}, "setups": ("intraday_vcp",)},
}

STATE_RANK = ("aplus", "triggered", "stopped", "broke_not_aplus", "forming_ready", "forming", "partial", "invalid",
              "none")


@contextlib.contextmanager
def patched(overrides: dict):
    """Apply constant overrides for one replay, always restored. An unknown name is a bug, never a silent no-op."""
    old = {}
    try:
        for k, v in overrides.items():
            if not hasattr(GC, k):
                raise AttributeError(f"constants has no {k}")
            old[k] = getattr(GC, k)
            setattr(GC, k, v)
        yield
    finally:
        for k, v in old.items():
            setattr(GC, k, v)


def state_key(read: dict) -> str:
    st = read.get("state") or "none"
    if st == "partial" and read.get("broke"):
        return "broke_not_aplus"
    if st == "forming" and read.get("ready"):
        return "forming_ready"
    return st if st in STATE_RANK else "none"


# Run-1 critic M3 (2026-10-14): the best-state order ranks forming above partial / invalid, so a Fade whose base
# reached 3 of 6 and then failed printed "base 0 of 6 bars". The replay now also reports, per setup, the LONGEST base /
# pullback / cycle count any live structure reached that session and the FIRST rule that failed at that point.
COUNT_UNIT = {"bull_flag": "pullback bars", "kiss_fly": "pullback bars", "horizontal_fade": "base bars",
              "intraday_vcp": "cycles", "reversal_squeeze": "base bars"}
# An `invalid` read names its failure only in prose — the rule key each detector reason belongs to.
INVALID_RULE = (("stopped before the break", "entry"), ("pullback longer than", "k4"), ("base longer than", "k4"),
                ("pulled back more than half", "k3_depth"), ("base sank below half", "k3_depth"),
                ("did not honor it", "k5a_honor"), ("base wider than", "k6_tight"),
                ("no pullback in the last cycle", "k4_cycles"), ("lower low", "k7_higher_lows"),
                ("cycle low under the 21 EMA", "k7_ema21"))
DEAD_STATES = ("none", "invalid")
BROKE_STATES = ("aplus", "triggered", "stopped", "broke_not_aplus")
# How a structure with NO failing rule ended (critic round 2, 2026-10-14): it broke; its last read was the session's
# final pass (alive at the close); or a new leg replaced it before the close without a rule failing (superseded).
END_TEXT = {"broke": "none (broke)", "alive_at_close": "none (alive at the close)",
            "superseded": "none (superseded by a new leg)"}


def read_count(setup: str, r: dict) -> Optional[int]:
    """The structure's length on one read: the VCP's cycle count (its k4_cycles criterion), else the base / pullback
    bars. None = no structure (no leg)."""
    if not r.get("leg"):
        return None
    if setup == "intraday_vcp":
        c = next((c for c in r.get("criteria") or [] if c.get("key") == "k4_cycles"), None)
        m = re.match(r"\s*(\d+)", str((c or {}).get("value") or ""))
        return int(m.group(1)) if m else 0
    return int((r.get("base") or {}).get("bars") or 0)


def first_failing_rule(r: dict) -> Optional[str]:
    """The first missed rule of a read (criteria order); for an `invalid` read the rule its reason names."""
    if r.get("missed"):
        return r["missed"][0]
    if r.get("state") == "invalid":
        why = str(r.get("reason") or "")
        return next((k for frag, k in INVALID_RULE if frag in why), f"invalid: {why}" if why else "invalid")
    return None


class Longest:
    """Per setup: every structure (frame, leg start) seen at a pass; the longest count any LIVE read of it reached
    (first pass to reach it), and the first rule that failed at that read or at a later read of the same structure.
    `next_pass()` once per pass lets `result` say how a structure with no failing rule ended (`END_TEXT`)."""

    def __init__(self):
        self.structs: dict = {}
        self.n_pass = 0

    def next_pass(self) -> None:
        self.n_pass += 1

    def see(self, setup: str, r: dict) -> None:
        cnt = read_count(setup, r)
        if cnt is None:
            return
        key = (setup, r.get("frame"), (r.get("leg") or {}).get("s_t"))
        alive = r.get("state") not in DEAD_STATES
        fail = first_failing_rule(r)
        st = self.structs.get(key)
        if alive and (st is None or cnt > st["count"]):
            broke = st["broke"] if st is not None else False
            st = self.structs[key] = {"count": cnt, "at": r.get("as_of_bar_t"), "frame": r.get("frame"),
                                      "fail": fail, "state": state_key(r), "broke": broke}
        elif st is None:
            st = self.structs[key] = {"count": 0, "at": r.get("as_of_bar_t"), "frame": r.get("frame"), "fail": fail,
                                      "state": state_key(r), "broke": False}
        elif st["fail"] is None and fail:
            st["fail"] = fail
        st["broke"] = st["broke"] or state_key(r) in BROKE_STATES
        st["last_pass"] = self.n_pass

    def _end(self, st: dict) -> Optional[str]:
        if st["fail"]:
            return None
        if st["broke"]:
            return "broke"
        return "alive_at_close" if st.get("last_pass") == self.n_pass else "superseded"

    def result(self) -> dict:
        """Per setup the structure with the highest count; on a tie the one with a recorded failing rule, then the
        LATEST seen (a first-seen structure that a new leg replaced never wins a tie by arriving first)."""
        out: dict = {}
        best: dict = {}
        for (setup, _f, _s), st in self.structs.items():            # insertion order = first seen
            rank = (st["count"], st["fail"] is not None)
            if setup not in best or rank >= best[setup]:
                best[setup] = rank
                out[setup] = {"longest": st["count"], "longest_unit": COUNT_UNIT.get(setup, "bars"),
                              "longest_at": st["at"], "longest_frame": st["frame"], "first_fail": st["fail"] or "",
                              "longest_state": st["state"], "longest_end": self._end(st)}
        return out


def replay_day(symbol: str, session, raw_prev, raw_today, *, setups=GC.SETUPS) -> dict:
    """{setup: best read of the session} — see `replay_day_full`."""
    return replay_day_full(symbol, session, raw_prev, raw_today, setups=setups)[0]


def replay_day_full(symbol: str, session, raw_prev, raw_today, *, setups=GC.SETUPS) -> tuple:
    """({setup: best read of the session}, {setup: longest-structure diagnostics}) on the 5-minute pass grid from the
    first bar (no q gate — his chart, not his scanner, picked the name). The best read keeps the FIRST pass that
    reached its rank; the diagnostics are `Longest.result()`."""
    d = S._as_date(session)
    today = S.day_minutes(raw_today, d)
    if today is None or len(today) == 0:
        return {}, {}
    prev = raw_prev
    if prev is not None and len(prev) and "session" in prev.columns:
        prev = prev[prev["session"].isin(S.LIVE_SESSIONS)]
    everything = S.utc_naive(S.session_bounds(d)["ah_close"]) + pd.Timedelta(days=1)
    fr = build_frames(symbol, d, everything, prev, today)
    if fr is None:
        return {}, {}
    f5, f15 = fr.f5, fr.f15
    lab5, lab15 = f5.df.index, f15.df.index
    ctx = {"symbol": symbol, "float_read": S.STUDY_FLOAT}
    best: dict = {}
    longest = Longest()
    last_n = None
    first_minute = today.index[0]
    for L in S.pass_grid(d, first_minute - S.ONE_MIN):
        n5, n15 = int(lab5.searchsorted(L, side="right")), int(lab15.searchsorted(L, side="right"))
        if n5 == 0 or (n5, n15) == last_n:
            continue
        last_n = (n5, n15)
        longest.next_pass()
        frames = {"5m": S.prefix_frame(f5, n5), "15m": S.prefix_frame(f15, n15) if n15 else None}
        for setup, r in D.read_all(frames, ctx).items():
            if setup not in setups:
                continue
            longest.see(setup, r)
            k = STATE_RANK.index(state_key(r))
            if setup not in best or k < best[setup][0]:
                best[setup] = (k, r)
    return {s: r for s, (_k, r) in best.items()}, longest.result()


def _bars_for(cache, ticker: str, d: date) -> tuple:
    """(symbol used, raw_today, raw_prev, prev_close, tried) — the ticker as given, then its rename / former names."""
    tried = []
    for sym in dict.fromkeys([ticker, symbols.resolve(ticker)] + symbols.former_names(ticker)):
        tried.append(sym)
        daily = cache.daily_bars(sym, d) or []
        rows = [(datetime.fromtimestamp(int(b["t"]) / 1000, tz=S.ET).date(), b)
                for b in daily if b.get("t") is not None]
        before = [(dd, b) for dd, b in rows if dd < d]
        raw_today = cache.minutes(sym, d)
        if raw_today is None or len(raw_today) == 0 or not before:
            continue
        prev_day, prev_bar = before[-1]
        return sym, raw_today, cache.minutes(sym, prev_day), float(prev_bar["c"]), tried
    return None, None, None, None, tried


def _row(ex: dict, setting: str, setup: str, r: Optional[dict], *, status: str, sym: Optional[str] = None,
         diag: Optional[dict] = None) -> dict:
    r = r or {}
    g = diag or {}
    return {"ticker": ex["ticker"], "symbol": sym, "date": ex["date"], "his_setup": ex["setup"],
            "longest": g.get("longest"), "longest_unit": g.get("longest_unit"), "longest_at": g.get("longest_at"),
            "longest_frame": g.get("longest_frame"), "first_fail": g.get("first_fail"),
            "longest_end": g.get("longest_end"),
            "his_label": ex["label"], "his_frame": ex["frame"], "status": status, "setting": setting, "setup": setup,
            "best_state": state_key(r) if r else None, "frame": r.get("frame"), "entry_bar_t": r.get("entry_bar_t"),
            "as_of_bar_t": r.get("as_of_bar_t"), "trigger": r.get("trigger"), "stop": r.get("stop"),
            "missed": ",".join(r.get("missed") or []), "unjudged": ",".join(r.get("unjudged") or []),
            "reason": r.get("reason") or "", "variant": r.get("variant"), "grade": r.get("grade"),
            "float_gate": ("not applied" if setup == "reversal_squeeze" else "")}


def replay_examples(cache, examples=EXAMPLES, settings=SETTINGS) -> list:
    """Every example × every setting that can move its setup → rows (see `_row`)."""
    rows = []
    for ex in examples:
        d = date.fromisoformat(ex["date"])
        sym, raw_today, raw_prev, prev_close, tried = _bars_for(cache, ex["ticker"], d)
        if sym is None:
            why = "not in the cache (offline run)" if getattr(cache, "offline", False) else "no bars"
            rows.append(_row(ex, "—", ex["setup"] or "—", None, status=f"{why} (tried {', '.join(tried)})"))
            continue
        q = S.qualification_minute(S.day_minutes(raw_today, d), prev_close)
        if q is None:
            rows.append(_row(ex, "—", ex["setup"] or "—", None, sym=sym,
                             status="date unverified — his scanner did not list it that session"))
            continue
        setups = (ex["setup"],) if ex["setup"] else GC.SETUPS
        for name, cfg in settings.items():
            moved = [s for s in setups if s in cfg["setups"]]
            if not moved:
                continue
            with patched(cfg["overrides"]):
                best, diag = replay_day_full(sym, d, raw_prev, raw_today, setups=tuple(moved))
            for s in moved:
                rows.append(_row(ex, name, s, best.get(s), sym=sym, status="replayed", diag=diag.get(s)))
    return rows


def _longest_cell(r: dict) -> str:
    if r.get("longest") is None:
        return "—"
    at = f" @ {r['longest_at']}" if r.get("longest_at") else ""
    fr = f" ({r['longest_frame']})" if r.get("longest_frame") else ""
    return f"{r['longest']} {r['longest_unit']}{fr}{at}"


def render_md(rows: list) -> str:
    head = ("| ticker | date | his label | setting | setup | our best state | entry bar | trigger | stop | "
            "missed (nearest miss) | longest reached | first failing rule there | note |")
    out = [head, "|" + "---|" * 13]
    for r in rows:
        note = r["status"] if r["status"] != "replayed" else (r["reason"] or "")
        if r["float_gate"]:
            note = (note + " · float gate not applied").strip(" ·")
        ff = r.get("first_fail")
        ff = "—" if ff is None else (ff or END_TEXT.get(r.get("longest_end"), "none"))
        out.append(f"| {r['ticker']} | {r['date']} | {r['his_label']} | {r['setting']} | {r['setup']} | "
                   f"{r['best_state'] or '—'} | {r['entry_bar_t'] or '—'} | {r['trigger'] or '—'} | "
                   f"{r['stop'] or '—'} | {r['missed'] or '—'} | {_longest_cell(r)} | {ff} | {note} |")
    return "\n".join(out)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Replay his dated examples through the Gajjala detectors (event seeds).")
    ap.add_argument("--cache", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--offline", action="store_true", help="cache only, no HTTP")
    ap.add_argument("--only", default="", help="comma list of tickers")
    ap.add_argument("--force", action="store_true", help="run inside 09:30–16:00 ET anyway")
    a = ap.parse_args(argv)
    now_et = datetime.now(S.ET)
    if S.refused_window(now_et) and not a.force:
        print(f"refused: {now_et:%H:%M} ET is inside the regular session — run after 16:00 ET or pass --force",
              file=sys.stderr)
        return 2
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    only = {t.strip().upper() for t in a.only.split(",") if t.strip()}
    exs = [e for e in EXAMPLES if not only or e["ticker"] in only]
    try:
        cache = S.Cache(a.cache, offline=a.offline)                # as-printed bars only (S.CACHE_LAYOUT)
    except S.StaleCache as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2
    rows = replay_examples(cache, exs)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "examples.json").write_text(json.dumps(rows, indent=1, default=str))
    md = ("EVENT SEEDS, NOT LABELS FOR A BACKTEST — his own charts through our detectors.\n\n" + render_md(rows))
    (out / "examples.md").write_text(md + "\n")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
