"""🎬 Replays — the listing, printed (replays spec §3.1 / §5.2, 2026-11-17). READ ONLY: disk reads only; no write,
no Mongo, no network, no HTTP.

Prints `chart_maps.replays.store.payload(date)` — the SAME function `GET /chart-maps/replays` serves — as the dates,
the per-date group sizes and the skipped counts, so the pre-deploy proof against the real host folder and the page
never differ.

RUN (host venv, against the real folder):
  cd /Users/ajay/clinet-test/.wt-replaytab/backend
  REPLAYS_DIR=/Users/ajay/clinet-test/eod-audits/replays .venv/bin/python scripts/replays_probe.py 2026-11-17
  REPLAYS_DIR=/Users/ajay/clinet-test/eod-audits/replays .venv/bin/python scripts/replays_probe.py --all
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from chart_maps.replays import store as ST  # noqa: E402


def line(p: dict) -> str:
    groups = {g["key"]: len(g["videos"]) for g in p.get("groups", [])}
    n = sum(groups.values())
    rs = p.get("rs") or {}
    return f"{p.get('date')} state={p.get('state')} videos={n} groups={groups} counts={p.get('counts')} rs_rows={len(rs.get('rows') or [])}"


def main(argv) -> int:
    root = ST.root_dir()
    first = ST.payload(None, root)
    print(f"root: {root}")
    print(f"state: {first['state']}")
    if first["state"] == "no_folder":
        print(first["text"])
        return 0
    print(f"dates ({len(first['dates'])}): {', '.join(first['dates'])}")
    days = first["dates"] if "--all" in argv else ([a for a in argv if not a.startswith("--")] or [first["date"]])
    for d in days:
        if d:
            print(line(ST.payload(d, root)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
