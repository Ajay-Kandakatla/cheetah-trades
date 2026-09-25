"""Regenerate tests/fixtures/universe/ — the index lists the backend suite runs on.

Run on the host from backend/, with the api container up:

    .venv/bin/python scripts/refresh_universe_test_snapshot.py

Russell 1000 / 3000 / micro-cap are parsed from THIS checkout's iShares exports
in sepa/data, inside the api container, because the host venv has no lxml. Each
export is copied to the container's /tmp (never /app) and removed afterwards.

S&P 500 / 400 / 600 and the Nasdaq-100 are read from the api container's own
cache: what production scans, refreshed weekly by sepa.universe_changes.

Writes the lists and MANIFEST.json. Refuses to write a list outside its size
band in sepa.universe._EXPECTED_COUNTS. Review the diff before committing.
See docs/sepa/universe_test_snapshot.md.
"""
from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
import sys
from pathlib import Path

CONTAINER = "cheetah-market-app-api-1"
BACKEND = Path(__file__).resolve().parents[1]
OUT = BACKEND / "tests" / "fixtures" / "universe"
# Every iShares export the universe module reads. russell2000 is ABSENT until
# Ajay drops the IWM file in (docs/sepa/russell2000_derived.md); from then on
# it is snapshotted like the others and fetch_russell2000 serves it as the
# cache hit production would.
EXPORTS = {
    "russell1000": "sepa/data/iShares-Russell-1000-ETF_fund.xls",
    "russell3000": "sepa/data/iShares-Russell-3000-ETF_fund.xls",
    "microcap": "sepa/data/iShares-Micro-Cap-ETF_fund.xls",
    "russell2000": "sepa/data/iShares-Russell-2000-ETF_fund.xls",
}
FROM_CONTAINER_CACHE = ("sp500", "sp400", "sp600", "nasdaq100")

_PARSE = """
import sys
from pathlib import Path
from sepa import universe as U
print("\\n".join(U._load_ishares_local_xls(Path(sys.argv[1]), source_label=sys.argv[2])))
"""


def _run(*args: str, stdin: str | None = None) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          input=stdin).stdout


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    sys.path.insert(0, str(BACKEND))
    from sepa.universe import _EXPECTED_COUNTS

    lists: dict[str, list[str]] = {}
    for name in FROM_CONTAINER_CACHE:
        lists[name] = _run("docker", "exec", CONTAINER, "cat",
                           f"/root/.cheetah/universe/{name}.txt").split()
    exports = {n: rel for n, rel in EXPORTS.items() if (BACKEND / rel).exists()}
    for name, rel in exports.items():
        tmp = f"/tmp/universe_test_snapshot_{name}.xls"
        _run("docker", "cp", str(BACKEND / rel), f"{CONTAINER}:{tmp}")
        try:
            lists[name] = _run("docker", "exec", "-i", "-w", "/app", CONTAINER,
                               "python", "-", tmp, name, stdin=_PARSE).split()
        finally:
            _run("docker", "exec", CONTAINER, "rm", "-f", tmp)

    bad = []
    for name, syms in lists.items():
        lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
        if not lo <= len(syms) <= hi:
            bad.append("%s: %d names, outside %d-%d" % (name, len(syms), lo, hi))
    if bad:
        print("REFUSED — nothing written:\n  " + "\n  ".join(bad), file=sys.stderr)
        return 1

    manifest_lists = {}
    for name in sorted(lists):
        body = "\n".join(lists[name])
        (OUT / f"{name}.txt").write_text(body)
        manifest_lists[name] = {"count": len(lists[name]), "sha256": _sha(body.encode())}
    manifest = {
        "taken": datetime.date.today().isoformat(),
        "source": ("S&P and Nasdaq-100 lists: the api container cache "
                   "/root/.cheetah/universe (the cheetah-scans volume). Russell "
                   "and micro-cap lists: this checkout's iShares exports, parsed "
                   "in the api container by sepa.universe._load_ishares_local_xls. "
                   "Written by scripts/refresh_universe_test_snapshot.py."),
        "lists": manifest_lists,
        "ishares_exports": {
            name: {"file": rel, "sha256": _sha((BACKEND / rel).read_bytes()),
                   "note": "the list above is this export's parse, same order"}
            for name, rel in exports.items()
        },
        "regenerate": "docs/sepa/universe_test_snapshot.md",
    }
    (OUT / "MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for name, rec in manifest_lists.items():
        print("%-12s %5d" % (name, rec["count"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
