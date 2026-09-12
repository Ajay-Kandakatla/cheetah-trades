"""CLI for the growth tracker cron.

  python -m growth build     rebuild the 100/100 board  (weekly)
  python -m growth alerts    one demand-alert pass      (market days)
  python -m growth show      print the board, send nothing
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

    if cmd == "show":
        from growth import tracker as T
        print(json.dumps({"n": (T.board() or {}).get("n"),
                          "rows": [r["symbol"] for r in
                                   ((T.board() or {}).get("rows") or [])]}))
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
