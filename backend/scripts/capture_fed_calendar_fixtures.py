"""Re-capture the two Federal Reserve calendar fixtures (read-only, re-runnable).

    python scripts/capture_fed_calendar_fixtures.py [OUT_DIR]

GETs federalreserve.gov/json/calendar.json and monetarypolicy/fomccalendars.htm
with fed_schedule.FED_USER_AGENT and writes:

  * fed_fomccalendars_<date>.htm — the page, verbatim.
  * fed_calendar_<date>.json — the real body TRIMMED to a documented filter
    (raw strings unchanged, re-serialised with the leading BOM):
      - types FOMC, Beige and Other with month >= 2025-01;
      - Speeches and Testimony with month 2026-09..2026-12;
      - every Chair-titled Speeches/Testimony row in 2025-2026;
      - the first 5 `Stat` rows and the first 3 undated `events` rows (negatives).

Run it in a throwaway container with the repo mounted read-only and OUT_DIR on
a scratch mount, then copy the output into backend/tests/fixtures/. Writes
nothing to Mongo. Fixture dates are the capture date (ET).
"""
from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import fed_schedule as F                                     # noqa: E402


def _chair_titled(e: dict) -> bool:
    m = F._REMARK_RE.match(str(e.get("title") or ""))
    return bool(m and F._CHAIR_RE.match(m.group(2).strip()))


def trim(body: dict) -> dict:
    kept, n_stat, n_undated = [], 0, 0
    for e in body.get("events") or []:
        if not isinstance(e, dict):
            continue
        typ, month = e.get("type"), str(e.get("month") or "")
        keep = False
        if typ in ("FOMC", "Beige", "Other") and month >= "2025-01":
            keep = True
        elif typ in ("Speeches", "Testimony") and "2026-09" <= month <= "2026-12":
            keep = True
        elif typ in ("Speeches", "Testimony") and "2025-01" <= month <= "2026-12" and _chair_titled(e):
            keep = True
        elif typ == "Stat" and n_stat < 5:
            n_stat += 1
            keep = True
        elif typ == "events" and not month and n_undated < 3:
            n_undated += 1
            keep = True
        if keep:
            kept.append(e)
    return {"events": kept, "announcement": []}


def main(out_dir: str) -> int:
    stamp = F._today_et().isoformat().replace("-", "_")
    os.makedirs(out_dir, exist_ok=True)
    st, text, lm = F._http_get(F.FED_FOMC_CALENDARS_URL, None)
    print(f"fomccalendars.htm HTTP {st} {len(text)} chars last-modified {lm}")
    if st != 200:
        return 1
    with open(os.path.join(out_dir, f"fed_fomccalendars_{stamp}.htm"), "w", encoding="utf-8") as f:
        f.write(text)
    time.sleep(1.0)
    st, text, lm = F._http_get(F.FED_CALENDAR_JSON_URL, None)
    print(f"calendar.json HTTP {st} {len(text)} chars last-modified {lm}")
    if st != 200:
        return 1
    body = json.loads(text.lstrip("﻿"))
    out = trim(body)
    with open(os.path.join(out_dir, f"fed_calendar_{stamp}.json"), "w", encoding="utf-8") as f:
        f.write("﻿" + json.dumps(out, ensure_ascii=False))
    print(f"calendar.json kept {len(out['events'])} of {len(body.get('events') or [])} events")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "/out"))
