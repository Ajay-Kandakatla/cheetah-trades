"""💧 How often the "Armed, volume dried" push WOULD have rung — READ-ONLY, an UPPER bound, frequency only (2026-11-24).

Ajay, verbatim (2026-11-24): "Can you track something for me how many times have the stocks bumped right after volume
dried up.. I noticed that the best entries so far have been after volume dried up.. after all the other rules. Can you
send me notification of volume dried please.."

UPPER bound — cannot replay vol_row, K11 or stale tape (the tracker stores none). FREQUENCY ONLY — NOT AN EDGE, not a
win rate, not a forecast. Per stored session (the newest `--sessions N` dates of gajjala_potentials), per tracker doc:

  * every turn into "trigger armed" — entry_marks.ready_since on each PREFIX of the doc's state_path
    (`dict(doc, state_path=path[:i+1])`), the SAME function the ring calls (a joined doc's first entry is None there);
  * the first-arms by band of the ET clock: pre (before the regular open), muted (the open … + his first
    NO_TRADE_AFTER_OPEN_MIN minutes), RTH (to the regular close), after-close;
  * would-ring = the first turn potential.window_reason admits (the 🧠 window, the mute) — a re-arm after a muted /
    outside first arm counts here, so this may read above the planner's probe;
  * of those, the ones on the SAME pass as a 🧠 claim of that name and setup (the doc's `push.at` == the stamp).

What it CANNOT replay (the losses named): the card's own K3 row (vol_row), GG's K11 1M session floor, a print in the
bar that just closed, the closed-day gate. The live "GGD:" records are the only exact count of what rang.
Mongo reads only: no fetch, no write, no index build.

    docker exec -i -w /app <scratch container on the branch> python -m scripts.gajjala_vol_dried_count --sessions 8 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

HEADER = "UPPER bound — cannot replay vol_row, K11 or stale tape (the tracker stores none)"
BANDS = ("pre", "muted", "rth", "after_close")


def turns(doc: dict) -> list:
    """Every stamp at which the doc turned (forming, armed): ready_since on each prefix of state_path, in order."""
    from chart_maps.gajjala import entry_marks as EM
    if not isinstance(doc, dict):
        return []
    path = doc.get("state_path")
    if not isinstance(path, list):
        return []
    out = []
    for i in range(len(path)):
        at = EM.ready_since(dict(doc, state_path=path[:i + 1]))
        if at is not None:
            out.append(at)
    return out


def band(at: datetime, session) -> str:
    """pre / muted / rth / after_close on the ET clock of the session (half days per the house table)."""
    from daytrading.data import ET_RTH_OPEN
    from chart_maps.gajjala import alerts as AL
    from chart_maps.gajjala import potential as PT
    t = PT._et(at).time().replace(tzinfo=None)
    rth_close = AL._closes(session)[0]
    mute_end = (datetime.combine(date.min, ET_RTH_OPEN) + timedelta(minutes=_mute_min())).time()
    if t < ET_RTH_OPEN:
        return BANDS[0]
    if t < mute_end:
        return BANDS[1]
    if t < rth_close:
        return BANDS[2]
    return BANDS[3]


def _mute_min() -> int:
    from chart_maps.gajjala import constants as GC
    return GC.NO_TRADE_AFTER_OPEN_MIN


def count_doc(doc: dict, session) -> dict:
    """{"first_band": band | None, "would_ring": stamp | None, "same_pass": bool} for one tracker doc."""
    from chart_maps.gajjala import entry_marks as EM
    from chart_maps.gajjala import potential as PT
    ts = turns(doc)
    if not ts:
        return {"first_band": None, "would_ring": None, "same_pass": False}
    ring = next((t for t in ts if PT.window_reason(t, session) is None), None)
    push = doc.get("push") if isinstance(doc.get("push"), dict) else {}
    pat = EM._utc(push.get("at"))
    return {"first_band": band(ts[0], session), "would_ring": ring,
            "same_pass": ring is not None and pat is not None and pat == ring}


def count_session(docs: list, session) -> dict:
    bands: Counter = Counter()
    ring = same = 0
    for doc in docs or []:
        c = count_doc(doc, session)
        if c["first_band"] is None:
            continue
        bands[c["first_band"]] += 1
        if c["would_ring"] is not None:
            ring += 1
            same += 1 if c["same_pass"] else 0
    return {"first_arms": sum(bands.values()), "bands": {b: bands.get(b, 0) for b in BANDS}, "would_ring": ring,
            "same_pass_as_potential_claim": same}


def run(st, sessions: int) -> dict:
    from chart_maps.gajjala import store as ST
    c = st.coll(ST.POTENTIALS)
    if c is None:
        raise RuntimeError("no gajjala_potentials handle")
    days = sorted({str(d)[:10] for d in c.distinct("date") if d})[-int(sessions):]
    out = {"header": HEADER, "sessions": {}}
    tot = Counter()
    for d in days:
        docs = list(c.find({"date": d}, {"state_path": 1, "push": 1, "first_seen_mode": 1}))
        row = count_session(docs, date.fromisoformat(d))
        out["sessions"][d] = row
        tot.update({"first_arms": row["first_arms"], "would_ring": row["would_ring"],
                    "same_pass_as_potential_claim": row["same_pass_as_potential_claim"]})
        tot.update({f"band_{b}": n for b, n in row["bands"].items()})
    out["total"] = dict(tot)
    return out


def main(argv: Optional[list] = None) -> int:
    ap = argparse.ArgumentParser(prog="scripts.gajjala_vol_dried_count", description=HEADER)
    ap.add_argument("--sessions", type=int, default=8)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    from chart_maps.gajjala import store as ST
    res = run(ST.default(), a.sessions)
    if a.json:
        print(json.dumps(res, default=str))
        return 0
    print(HEADER)
    print("session     first-arms  pre  muted  rth  after-close  would-ring  same-pass-as-🧠")
    for d, r in res["sessions"].items():
        b = r["bands"]
        print(f"{d}  {r['first_arms']:>10}  {b['pre']:>3}  {b['muted']:>5}  {b['rth']:>3}  {b['after_close']:>11}  "
              f"{r['would_ring']:>10}  {r['same_pass_as_potential_claim']:>15}")
    print("total", res["total"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
