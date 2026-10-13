#!/usr/bin/env python
"""Gajjala's tab — does Nasdaq Trader's halt feed serve a PAST session? (spec §1.6, WP2)

READ-ONLY. One GET of `rss.aspx?feed=tradehalts&haltdate=MMDDYYYY` per `--date` (or a saved copy with `--file`);
writes nothing anywhere. Prints, per date: HTTP status, item count, the HaltDate values the items carry (a past date
must come back as ONLY that date — the 🎾 30-session halt backfill in chart_maps/gajjala/nightly.py depends on it),
the Mkt counts, the ticker count, and what `catalysts.halts.get_halts_for_date` parses out of the same body.

Measured 2026-10-13 ~09:12 EDT (re-run before quoting — memory feedback_ship_the_backtest):
    --date 2026-10-09  → 72 items, every HaltDate 10/09/2026 (Mkt Q 69, N 3)
    --date 2026-09-02  → 28 items, every HaltDate 09/02/2026 (Q 25, Z 3)

    backend/.venv/bin/python backend/scripts/gajjala_halts_history_probe.py --date 2026-10-09 --date 2026-09-02
    backend/.venv/bin/python backend/scripts/gajjala_halts_history_probe.py --file backend/tests/fixtures/gajjala/halts_10092026.xml --date 2026-10-09
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))


def summarize(xml: str, d: date) -> dict:
    """The raw-item read (independent of the app's parser) beside the app's own parse of the same body."""
    from catalysts import halts as H
    items = re.findall(r"<item>(.*?)</item>", xml, re.S)
    dates = Counter(m.strip() for m in re.findall(r"<ndaq:HaltDate>([^<]*)</ndaq:HaltDate>", xml))
    mkts = Counter(m.strip() for m in re.findall(r"<ndaq:Mkt>([^<]*)</ndaq:Mkt>", xml))
    by = H._group_by_ticker(H._parse_halts_xml(xml), d)
    return {"items": len(items), "halt_dates": dict(dates), "mkt": dict(mkts),
            "only_that_date": set(dates) == {d.strftime("%m/%d/%Y")},
            "parsed_halts": sum(v["n_halts"] for v in by.values()), "parsed_tickers": len(by)}


def fetch(d: date) -> tuple:
    import requests
    from catalysts import halts as H
    url = H._HALT_FEED_URL + "&haltdate=" + d.strftime("%m%d%Y")
    r = requests.get(url, headers=H._HEADERS, timeout=15)
    return r.status_code, r.text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Nasdaq Trader dated halt list — read-only probe")
    ap.add_argument("--date", action="append", required=True, help="YYYY-MM-DD (repeatable)")
    ap.add_argument("--file", help="read this saved feed body instead of fetching (one --date)")
    args = ap.parse_args(argv)
    for raw in args.date:
        d = date.fromisoformat(raw)
        if args.file:
            with open(args.file, encoding="utf-8-sig") as fh:
                status, body = 200, fh.read()
        else:
            status, body = fetch(d)
        if status != 200:
            print(f"{d}  HTTP {status}")
            continue
        s = summarize(body, d)
        print(f"{d}  HTTP {status}  items {s['items']}  only {d.strftime('%m/%d/%Y')}: {s['only_that_date']}  "
              f"dates {s['halt_dates']}  Mkt {s['mkt']}  parsed {s['parsed_halts']} halts / "
              f"{s['parsed_tickers']} tickers")
    return 0


if __name__ == "__main__":
    sys.exit(main())
