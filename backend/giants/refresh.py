"""Cron entrypoint: `python -m giants.refresh`.

Daily run is cheap — filings are immutable and cached forever, so outside the
quarterly filing windows (mid-Feb / May / Aug / Nov) this is ~38 submissions
checks and a re-aggregation. During filing season it picks up each giant's new
13F the day it lands and the leaderboard timeline gains the new quarter.
"""
from __future__ import annotations

import logging
import sys

from giants import flows

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("giants.refresh")


def main() -> int:
    doc = flows.rebuild()
    log.info("giants flows rebuilt: %s funds with data, latest quarter %s, "
             "%s inflow rows / %s outflow rows",
             doc.get("n_funds_with_data"), doc.get("latest_quarter"),
             len(doc.get("rows_in") or []), len(doc.get("rows_out") or []))
    return 0


if __name__ == "__main__":
    sys.exit(main())
