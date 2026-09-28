#!/usr/bin/env python
"""Tape trade eligibility — before / after on one full session. READ-ONLY.

The numbers in docs/sepa/orderflow_methodology.md §"Trade eligibility"
(ORCL 2026-09-25: delta +9,710,852 → −937,106, Big buy $ $1,563.8M → $110.7M,
Big sell $ $118.3M → $119.7M, checks 3/5 → 1/5, tape shares +29.4% → −0.02%
vs the official daily volume) come from this script.

MODEL
    after  = orderflow.tape.analyze_tape on the frame tape.fetch_trades returns
             (every print labelled with `kind` by tape.print_kind).
    before = the SAME frame with the `kind` column dropped — analyze_tape then
             reads every print as a trade, the pre-2026-09-27 behaviour
             (tape.split_by_kind: "A frame with no kind column is all flow").
    Both runs use the same NBBO (orderflow.quotes.fetch_quotes), so the quote
    rule classifies both. The verdict line re-uses signals.delta_check /
    big_buyers_check / composite_verdict; the other three checks are held at
    what ORCL's live 2026-09-25 snapshot read (daily trend FAIL, intraday EMA
    FAIL, zone PASS without caution; the defaults below) so only the two tape
    checks move. Pass --trend/--ema/--zone to change them.

READ-ONLY. Trades, quotes and the daily bar are Massive GETs through the
app's own client; nothing calls orderflow.engine (no _save, no ledger), and
nothing is written anywhere except the optional --out JSON.

OFFLINE. --raw PATH reads a gzipped {"truncated": bool, "rows": [...]} dump of
raw /v3/trades rows (the audit pulled them that way) instead of fetching.
With --offline there is no NBBO (both runs use the tick rule) and no daily
volume; the output says which classifier ran.

RUN (throwaway container, never the live one's /app):
    docker run --rm --network cheetah-market-app_default \
      -e MONGO_URL=mongodb://mongo:27017 -e MONGO_DB=cheetah_tape_scratch \
      -v "$PWD/backend:/app:ro" --env-file backend/.env cheetah-api:latest \
      python scripts/tape_eligibility_before_after_2026_09_27.py ORCL --date 2026-09-25
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
from datetime import date

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from orderflow import signals, tape  # noqa: E402


def frame_from_raw(rows: list, truncated: bool = False) -> pd.DataFrame:
    """Raw /v3/trades rows → the frame tape.fetch_trades returns. Mirrors its
    tail exactly (label_kinds, exec_utc, keep, dropna, positive price/size)."""
    df = pd.DataFrame(rows)
    ts_col = "sip_timestamp" if "sip_timestamp" in df.columns else "participant_timestamp"
    df["ts_utc"] = pd.to_datetime(df[ts_col], unit="ns", utc=True)
    tape.label_kinds(df)
    if "participant_timestamp" in df.columns:
        df["exec_utc"] = pd.to_datetime(df["participant_timestamp"], unit="ns", utc=True)
    keep = (["ts_utc", "price", "size"] + (["exchange"] if "exchange" in df.columns else [])
            + ["kind"] + (["exec_utc"] if "exec_utc" in df.columns else []))
    df = df[keep].dropna(subset=["ts_utc", "price", "size"]).sort_values("ts_utc").set_index("ts_utc")
    df = df[(df["price"] > 0) & (df["size"] > 0)]
    df.attrs["truncated"] = truncated
    return df


def daily_volume(sym: str, day: date):
    """Official consolidated daily volume (unadjusted /v2/aggs day bar)."""
    try:
        import requests
        from massive_keys import stocks_key
        r = requests.get(f"{tape.BASE_URL}/v2/aggs/ticker/{sym}/range/1/day/{day}/{day}",
                         params={"adjusted": "false", "apiKey": stocks_key()}, timeout=20)
        res = (r.json() or {}).get("results") or []
        return int(res[0]["v"]) if res else None
    except Exception:
        return None


def _m(x: float) -> str:
    return f"${x / 1e6:,.1f}M"


def read(R: dict, trend: dict, ema: dict, zone: dict) -> dict:
    dc = signals.delta_check(R["delta"])
    bc = signals.big_buyers_check(R["big_prints"])
    v = signals.composite_verdict(trend, ema, dc, bc, zone)
    bp = R["big_prints"]
    return {
        "classifier": R["classification"]["method"],
        "n_trades": R["delta"]["n_trades"],
        "delta": R["delta"]["delta"],
        "delta_pct": R["delta"]["delta_pct_of_volume"],
        "big_buy": _m(bp["buy_dollars"]), "big_sell": _m(bp["sell_dollars"]),
        "delta_check": bool(dc.get("pass")), "big_buyers_check": bool(bc.get("pass")),
        "verdict": v["verdict"], "checks_passed": v["checks_passed"],
        "bursts": [(b["date_et"], b["time_et"], b["side"], _m(b["dollars"])) for b in R["bursts"]],
        "top_prints": [(p["date_et"], p["time_et"], p.get("kind", "regular"), p["side"],
                        p["size"], p["price"], _m(p["dollars"])) for p in bp["prints"][:10]],
    }


def run(sym: str, day: date, full: pd.DataFrame, quotes, dvol, trend, ema, zone) -> dict:
    before_df = full.drop(columns=["kind"])
    before_df.attrs["truncated"] = full.attrs.get("truncated", False)
    B = tape.analyze_tape(before_df, quotes=quotes)
    A = tape.analyze_tape(full, quotes=quotes)
    all_sh = int(full["size"].sum())
    vol_sh = int(tape.split_by_kind(full)["volume"]["size"].sum())
    kinds = full.assign(d=full["price"] * full["size"]).groupby("kind").agg(
        n=("size", "count"), shares=("size", "sum"), dollars=("d", "sum"))
    return {
        "symbol": sym, "date": str(day), "truncated": bool(full.attrs.get("truncated", False)),
        "rows": int(len(full)),
        "kinds": {k: {"n": int(r.n), "shares": int(r.shares), "dollars": _m(r.dollars)}
                  for k, r in kinds.iterrows()},
        "official_daily_volume": dvol,
        "tape_shares_before": all_sh, "tape_shares_after": vol_sh,
        "vs_daily_before_pct": round(100.0 * (all_sh / dvol - 1), 2) if dvol else None,
        "vs_daily_after_pct": round(100.0 * (vol_sh / dvol - 1), 2) if dvol else None,
        "before": read(B, trend, ema, zone),
        "after": read(A, trend, ema, zone),
        "excluded_note": (A.get("excluded") or {}).get("note"),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("symbol")
    ap.add_argument("--date", required=True, help="ET session date, YYYY-MM-DD")
    ap.add_argument("--raw", help="gzipped raw /v3/trades dump instead of a fetch")
    ap.add_argument("--offline", action="store_true",
                    help="no network: no NBBO (tick rule) and no daily volume")
    ap.add_argument("--trend", choices=("pass", "fail"), default="fail")
    ap.add_argument("--ema", choices=("pass", "fail"), default="fail")
    ap.add_argument("--zone", choices=("pass", "caution", "fail"), default="pass")
    ap.add_argument("--out", help="write the result JSON here")
    a = ap.parse_args(argv)
    sym, day = a.symbol.upper(), date.fromisoformat(a.date)

    if a.raw:
        raw = json.load(gzip.open(a.raw, "rt"))
        full = frame_from_raw(raw["rows"], bool(raw.get("truncated")))
    else:
        full = tape.fetch_trades(sym, day)
    if full is None or not len(full):
        print(f"{sym} {day}: no prints", file=sys.stderr)
        return 1

    quotes = None
    if not a.offline:
        try:
            from orderflow import quotes as quotes_mod
            quotes = quotes_mod.fetch_quotes(sym, day)
        except Exception:
            quotes = None

    trend = {"pass": a.trend == "pass"}
    ema = {"pass": a.ema == "pass"}
    zone = {"pass": a.zone != "fail", "caution": a.zone == "caution"}
    dvol = None if a.offline else daily_volume(sym, day)
    res = run(sym, day, full, quotes, dvol, trend, ema, zone)
    txt = json.dumps(res, indent=1, default=str)
    print(txt)
    if a.out:
        with open(a.out, "w") as f:
            f.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
