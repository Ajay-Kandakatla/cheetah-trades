"""CLI for the growth tracker cron.

  python -m growth build     rebuild the 100/100 board  (weekly)
  python -m growth alerts    one demand-alert pass      (market days)
  python -m growth show      print the board, send nothing
  python -m growth earnings  refresh THIS BOARD's earnings dates, send nothing
  python -m growth quality   one capital-quality-upgrade pass (market days)
"""
from __future__ import annotations

import json
import logging
import sys

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    cmd = (argv[0] if argv else "build").lower()

    if cmd == "build":
        from growth import tracker as T
        doc = T.build()
        print("growth board rebuilt: %d names" % doc["n"])
        for r in doc["rows"][:40]:
            print("  %-6s sales %+8.1f%%  qEPS %+9.1f%%  %s"
                  % (r["symbol"], r.get("sales_growth_pct") or 0,
                     r.get("q_eps_growth_pct") or 0,
                     " ".join(r.get("warnings") or []) or "ok"))
        return 0

    if cmd == "alerts":
        from growth import alerts as A
        dry = "--dry-run" in argv
        print(json.dumps(A.run(dry_run=dry)))
        return 0

    if cmd == "quality":
        # 💎 Ajay 2026-09-22: "Filter and have alerts and new look out for such
        # companies where whcih have very high quality."
        #
        # Fires ONLY on a definitional capital-quality component crossing
        # FAIL -> PASS on a NEW fiscal quarter — an accounting event, never the
        # state "this name is high quality". The kind ships OFF
        # (push.subs.default_prefs); he turns it on at /notifications.
        from growth import quality_alerts as QA
        print(json.dumps(QA.run(dry_run="--dry-run" in argv), default=str))
        return 0

    if cmd == "show":
        from growth import tracker as T
        print(json.dumps({"n": (T.board() or {}).get("n"),
                          "rows": [r["symbol"] for r in
                                   ((T.board() or {}).get("rows") or [])]}))
        return 0

    if cmd == "earnings":
        # Ajay 2026-09-17: "make a remindder ro scan explosive growth of new
        # earnings stocks and high light them to me in explosive growth tab".
        #
        # THE REMINDER IS DATA, NOT A MESSAGE. This job re-fetches the earnings
        # calendar for the board's own symbols so the "just reported" badge on
        # the tab is fresh. IT SENDS NOTHING — no message of any kind leaves
        # this branch, and his phone's keep-set is untouched.
        #
        # It does NOT rebuild the board (that stays Sunday 09:00 ET).
        from growth import earnings_fresh as EFresh
        from growth import tracker as T
        res = EFresh.refresh_board_calendar()
        summary = EFresh.attach((T.board() or {}).get("rows") or [])
        print(json.dumps({"refresh": res, "summary": summary}))
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
