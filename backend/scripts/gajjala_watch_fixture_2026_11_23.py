"""👀 Gajjala's Watch — the FE fixture of the 1 / 5 / 15 board with 📈 VWAP and 📐 daily zones (spec vwapzones rev 2,
be-watch step 9).

Ajay, verbatim (2026-11-23): "Can you remove 3 mins just add 15 mins instead.. So 1 min, 5 and 15 accross board" · "Add
vwap and supply demand too".

DETERMINISTIC: synthetic 1-minute bars + synthetic closed daily bars → THE engines (`bars.build_frames`, `build.tile_update`
with the VWAP wrapper, `levels.levels_doc` = `zone_store.build_doc`) → the REAL `payload.build` over an in-memory store.
No network, no Mongo: the display-only sidecars that read other stores (🎯 A+, 🏷️ tags, 🔢 float, 🚫 broker, 🗂 sections)
are served as their documented fault values (None). The rows it MUST carry:
  * ZONE   — over $1, zones inside the chart's price range (state ok);
  * PENNY  — under $1, its stored `levels` holds a `lo == hi` band INSIDE the chart range [C3];
  * RETRY  — the daily read returned nothing (state retry);
  * OLDDOC — a doc written by main (frames 1m / 3m / 5m, no `levels`): served 1m + 5m + the 15m placeholder words.

  python -m scripts.gajjala_watch_fixture_2026_11_23            # build + check, print a summary
  python -m scripts.gajjala_watch_fixture_2026_11_23 --write    # … and write the JSON the FE tests read
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ET = ZoneInfo("America/New_York")
S = date(2026, 11, 20)                         # Friday, NYSE open
PREV = date(2026, 11, 19)
NOW = datetime(2026, 11, 20, 11, 0, 30, tzinfo=ET)
OUT = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "components" / "__fixtures__"
       / "gajjala_watch_board_2026_11_23.json")
MAIN_FRAMES = (("1m", "1min"), ("3m", "3min"), ("5m", "5min"))


class Coll:
    """The smallest in-memory collection `payload.build` / `build.write` need (no network, no Mongo)."""

    def __init__(self, docs=None):
        self.docs = {d["_id"]: copy.deepcopy(d) for d in docs or []}

    @staticmethod
    def _match(d, q):
        for k, v in (q or {}).items():
            if isinstance(v, dict) and "$in" in v:
                if d.get(k) not in v["$in"]:
                    return False
            elif d.get(k) != v:
                return False
        return True

    def find(self, q=None, projection=None):
        return [copy.deepcopy(d) for d in self.docs.values() if self._match(d, q)]

    def find_one(self, q=None, projection=None):
        got = self.find(q)
        return got[0] if got else None

    def update_one(self, flt, upd, upsert=False):
        d = self.docs.setdefault(flt["_id"], {"_id": flt["_id"]})
        for k, v in upd.get("$set", {}).items():
            cur = d
            parts = k.split(".")
            for p in parts[:-1]:
                cur = cur.setdefault(p, {})
            cur[parts[-1]] = copy.deepcopy(v)


def minutes(d, center, amp, seed, start=(4, 0), end=(11, 1)):
    """1-minute bars [start, end) ET around `center` (± amp), UTC-naive index, the loader's session tags."""
    t0 = pd.Timestamp(datetime(d.year, d.month, d.day, *start), tz=ET)
    t1 = pd.Timestamp(datetime(d.year, d.month, d.day, *end), tz=ET)
    idx = pd.date_range(t0, t1, freq="1min", inclusive="left")
    rows = []
    for i, ts in enumerate(idx):
        m = ts.hour * 60 + ts.minute
        p = center * (1 + amp * math.sin((i + seed) / 41.0) + amp * 0.3 * math.sin((i + seed) / 9.0))
        w = center * amp * 0.08
        rows.append({"open": p - w * 0.3, "high": p + w, "low": p - w, "close": p,
                     "volume": float(2000 + (i * 53) % 1700),
                     "session": "premarket" if m < 570 else ("rth" if m < 960 else "afterhours")})
    return pd.DataFrame(rows, index=idx.tz_convert("UTC").tz_localize(None))


def daily(base, seed, n=300, vol=0.01, wave=0.12):
    """Closed daily bars ending the session before S — a deterministic swinging series (the zone engine needs swings)."""
    rng = np.random.default_rng(seed)
    idx = pd.bdate_range(end=PREV, periods=n)
    i = np.arange(n)
    c = base * (1 + wave * np.sin(i / 11.0) + 0.04 * np.sin(i / 3.3)) * np.exp(np.cumsum(rng.normal(0, vol, n)) * 0.3)
    return pd.DataFrame({"open": c * 0.995, "high": c * 1.03, "low": c * 0.97, "close": c,
                         "volume": 1e6 + (i % 7) * 1e5}, index=idx)


def frames_of(sym, center, amp, seed, rules):
    from chart_maps.gajjala import bars as B
    return B.build_frames(sym, S, NOW, minutes(PREV, center, amp, seed, end=(20, 0)),
                          minutes(S, center, amp, seed + 7), rules=rules)


def tile_doc(sym, fr, levels=None):
    from chart_maps.gajjala_watch import build as BLD
    _f, upd = BLD.tile_update(sym, fr, S, NOW, "loaded")
    doc = {"_id": sym, **upd["$set"]}
    if levels is not None:
        doc["levels"] = levels
    return doc


def chart_range(doc):
    bars = doc["frames"]["1m"]["bars"]
    return min(b["l"] for b in bars), max(b["h"] for b in bars)


def pick_band(lv, pred):
    for b in lv.get("bands") or []:
        if pred(b):
            return b
    raise SystemExit(f"fixture: no band matches in {lv.get('bands')}")


def build_db():
    from chart_maps.gajjala_watch import constants as C
    from chart_maps.gajjala_watch import levels as LV
    at = NOW.astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

    # ZONE (> $1): read its daily zones first, then centre the day on its nearest demand band
    zl = LV.levels_doc("ZONE", daily(6.0, 1), S, NOW)
    assert zl["state"] == "ok", zl
    zb = pick_band(zl, lambda b: b["kind"] == "demand" and b["hi"] > b["lo"])
    zone = tile_doc("ZONE", frames_of("ZONE", (zb["lo"] + zb["hi"]) / 2, 0.04, 3.0, C.FRAMES), zl)

    # PENNY (< $1): the cent rounding gives a zero-width band — the day sits on it [C3]
    pl = None
    for seed in range(1, 60):
        cand = LV.levels_doc("PENNY", daily(0.12, seed, vol=0.02, wave=0.02), S, NOW)
        if cand["state"] == "ok" and any(b["lo"] == b["hi"] for b in cand["bands"]):
            pl = cand
            break
    assert pl is not None, "no zero-width band on any seed"
    pb = pick_band(pl, lambda b: b["lo"] == b["hi"])
    penny = tile_doc("PENNY", frames_of("PENNY", pb["lo"], 0.05, 5.0, C.FRAMES), pl)

    # RETRY: the daily read returned nothing → retry, tried once
    retry = tile_doc("RETRY", frames_of("RETRY", 3.4, 0.03, 9.0, C.FRAMES), LV.levels_doc("RETRY", None, S, NOW))

    # OLDDOC: written by main — frames 1m / 3m / 5m, no VWAP, no levels
    saved = (C.FRAMES, C.FRAME_WORDS, C.VWAP_ON)
    try:
        C.FRAMES, C.FRAME_WORDS, C.VWAP_ON = MAIN_FRAMES, {"1m": "1-min", "3m": "3-min", "5m": "5-min"}, False
        old = tile_doc("OLDDOC", frames_of("OLDDOC", 2.2, 0.03, 11.0, MAIN_FRAMES))
    finally:
        C.FRAMES, C.FRAME_WORDS, C.VWAP_ON = saved

    for d in (zone, penny, retry, old):
        d.update(symbol=d["_id"], at=at, loaded_at=at)
    syms = ["ZONE", "PENNY", "RETRY", "OLDDOC"]
    added = {s: (at - timedelta(minutes=10 * (i + 1))).isoformat() + "+00:00" for i, s in enumerate(syms)}
    db = {C.COLL_LIST: Coll([{"_id": C.LIST_DOC_ID, "symbols": syms, "added": added}]),
          C.COLL_TILES: Coll([zone, penny, retry, old]), C.COLL_ALERTS: Coll(),
          C.COLL_STATE: Coll([{"_id": C.STATE_LATEST_ID, "at": at - timedelta(seconds=30), "n_names": 4,
                               "n_read": 4}])}
    return db, {"zone_band": zb, "penny_band": pb}


def sidecars_off():
    """The display-only sidecars that read OTHER stores → their documented fault values (no network, no Mongo)."""
    from chart_maps.gajjala_watch import payload as PL

    def broker_off(out, state_doc, siso):
        for r in out.get("rows") or []:
            r["broker_text"] = None
        out["broker"] = None

    def sections_off(rows, raw, added, session):
        for r in rows:
            r["org"] = None
        return rows, None
    PL.aplus_section = lambda names, siso, **k: {}
    PL._tags_section = lambda names, session, is_today: {}
    PL._float_section = lambda names, session, now, tags_by: {}
    PL._broker_section = broker_off
    PL._sections = sections_off


def build_payload() -> tuple:
    sys.dont_write_bytecode = True
    from chart_maps.gajjala_watch import payload as PL
    sidecars_off()
    db, picked = build_db()
    out = PL.build(NOW, db=db)
    return json.loads(json.dumps(out, default=str, allow_nan=False)), picked, db


def check(out: dict, picked: dict) -> list:
    """The fixture's own contract — every MUST of spec step 9. Returns the problems (empty = good)."""
    bad = []
    txt = json.dumps(out, ensure_ascii=False)
    if out.get("state") != "ok":
        bad.append(f"state {out.get('state')}")
    if '"3m"' in txt or "3-min" in txt:
        bad.append("a 3m frame / word is served")
    rows = {r["symbol"]: r for r in out.get("rows") or []}
    for sym in ("ZONE", "PENNY", "RETRY", "OLDDOC"):
        r = rows.get(sym)
        if r is None:
            bad.append(f"{sym} missing")
            continue
        if [f["tf"] for f in r["frames"]] != ["1m", "5m", "15m"]:
            bad.append(f"{sym} frames {[f['tf'] for f in r['frames']]}")
    for sym, key in (("ZONE", "zone_band"), ("PENNY", "penny_band")):
        r = rows.get(sym) or {}
        if (r.get("levels") or {}).get("state") != "ok":
            bad.append(f"{sym} levels {r.get('levels')}")
        b = picked[key]
        one = (r.get("frames") or [{}])[0].get("tile", {})
        lo = min(x["l"] for x in one.get("bars") or [{"l": 1e9}])
        hi = max(x["h"] for x in one.get("bars") or [{"h": -1e9}])
        if not (lo <= b["lo"] <= hi and lo <= b["hi"] <= hi):
            bad.append(f"{sym} band {b['lo']}–{b['hi']} outside the chart {lo}–{hi}")
        if not any(x["lo"] == b["lo"] and x["hi"] == b["hi"] for x in one.get("bands") or []):
            bad.append(f"{sym} band not served on the 1m tile")
        if not any(c.get("tone") == "vwap" for c in one.get("curves") or []):
            bad.append(f"{sym} no VWAP curve")
    if not any(x["lo"] == x["hi"] for x in rows["PENNY"]["frames"][0]["tile"]["bands"]):
        bad.append("PENNY carries no lo == hi band")
    if (rows["RETRY"].get("levels") or {}).get("state") != "retry":
        bad.append(f"RETRY levels {rows['RETRY'].get('levels')}")
    old = rows["OLDDOC"]
    if not old["frames"][2].get("empty_text") or old["frames"][2]["tile"]["bars"]:
        bad.append("OLDDOC 15m is not the placeholder")
    if (old.get("levels") or {}).get("state") != "pending":
        bad.append(f"OLDDOC levels {old.get('levels')}")
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_watch_fixture_2026_11_23", description=__doc__.split("\n")[0])
    ap.add_argument("--write", action="store_true", help=f"write {OUT.name} for the FE tests")
    args = ap.parse_args(argv)
    out, picked, _db = build_payload()
    bad = check(out, picked)
    for r in out["rows"]:
        lv = r.get("levels") or {}
        print(r["symbol"], [f["tf"] for f in r["frames"]], lv.get("state"), lv.get("text"))
    print("zone band", picked["zone_band"]["lo"], picked["zone_band"]["hi"],
          "· penny band", picked["penny_band"]["lo"], picked["penny_band"]["hi"])
    if bad:
        print("FIXTURE PROBLEMS:", *bad, sep="\n  ")
        return 1
    if args.write:
        OUT.write_text(json.dumps(out, ensure_ascii=False) + "\n", encoding="utf-8")
        print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
