"""📅 Long Term 🔔 — read-only probe of the zone pass on real data (pkzone spec §5.4, 2026-11-12).

Ajay 2026-11-12, verbatim: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long
term tabs in general".

Runs `zone_watch.run_pass(now, dry=True)`: ONE `prices.bulk_snapshot` of the 40 names + ONE
`sources.pankaj_closes(..., before=session)` cache read; writes NOTHING to Mongo, sends NOTHING. Then builds the owner
payload the GET would serve with the dry pass as the live read (one more cache read: the GET's own closed-bar closes).
Writes `zone_reads.json` + `payload.json` into --out and prints names / live / stale / previous session / in a zone /
would reach / seconds / RSS. Never starts a stream client.

  PYTHONPATH=/app python -u /app/scripts/long_term_zone_probe.py --out /out
"""
from __future__ import annotations

import argparse
import json
import resource
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ET = ZoneInfo("America/New_York")


def _rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / (1024 * 1024) if sys.platform == "darwin" else r / 1024, 1)


def state_shape(res: dict, now: datetime) -> dict:
    """The stored session doc shape a real pass would `$set` (the payload's `zone_live`)."""
    return {"session": res.get("session"), "as_of_iso": now.isoformat(timespec="seconds"),
            "as_of_hhmm": now.strftime("%H:%M"), "rows": res.get("reads") or {}, "reason": res.get("reason"),
            "n_names": res.get("n_names"), "n_live": res.get("n_live"), "n_stale": res.get("n_stale"),
            "prev_session": res.get("prev_session")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="read-only zone pass probe")
    ap.add_argument("--out", type=str, required=True)
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    from long_term_list import constants as C                            # noqa: F401 — timed import
    t_const = time.time()
    from supply_demand import key_levels                                  # noqa: F401 — timed (prev_session)
    t_kl = time.time()
    from long_term_list import payload as P
    from long_term_list import seed as SD
    from long_term_list import sources as SRC
    from long_term_list import zone_watch as ZW
    t_imp = time.time()

    now = datetime.now(ET)
    res = ZW.run_pass(now, dry=True)
    t_pass = time.time()
    (out / "zone_reads.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")

    seed = SD.load()
    syms = sorted(SD.pankaj_entries(seed))
    closes = SRC.pankaj_closes(syms, now)
    live = ZW.serve_state(state_shape(res, now), now) if res.get("ran") else None
    payload = P.build_payload(seed, SD.load_baseline(), [], [], closes, now=now, owner=True, zone_live=live,
                              zone_day={}, log_session=ZW.log_session(now))
    (out / "payload.json").write_text(json.dumps(payload, indent=1, allow_nan=False), encoding="utf-8")
    t_end = time.time()

    reads = res.get("reads") or {}
    print(f"ran={res.get('ran')} reason={res.get('reason')} session={res.get('session')} "
          f"prev_session={res.get('prev_session')}")
    print(f"names={res.get('n_names')} live={res.get('n_live')} stale={res.get('n_stale')} in={res.get('n_in')}")
    print("in a zone:", {s: r["in"] for s, r in reads.items() if r.get("in")})
    print("would reach:", res.get("reached"))
    print("served alert:", json.dumps((payload.get("zones") or {}).get("alert"), ensure_ascii=False)[:1500])
    print(f"seconds: import constants {t_const - t0:.2f} · key_levels {t_kl - t_const:.2f} · rest {t_imp - t_kl:.2f} "
          f"· pass {t_pass - t_imp:.2f} · payload {t_end - t_pass:.2f} · RSS {_rss_mb()} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
