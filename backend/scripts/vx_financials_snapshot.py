"""Snapshot Massive's deprecated /vX/reference/financials before its sunset.

Ajay 2026-09-30, on "save a copy of Massive's old financials feed before it
shuts down?": "yes please".

The endpoint answers `Deprecation: true`, `Sunset: 2026-10-09` and is already in
410 brownouts. It is the only Massive feed that carries each filing's ORIGINAL
`filing_date` (the v1 successor stamps restated dates and drops delisted
names), which a point-in-time backtest of the 🏷️ vs-peers view needs.

How the crawl stays complete
  * ONE unfiltered cursor crawl (sort=filing_date asc, limit=100). No date,
    ticker or timeframe partitions, so no row can fall between two filters.
    Rows with a null filing_date come first and are kept.
  * Each page is written atomically to pages/NNNNNN.json.gz, THEN state.json
    advances. A restart resumes from state.json: no page is re-fetched and
    none is skipped.
  * 410 (brownout), 429, 5xx, timeouts and unreadable bodies are retried on
    the SAME cursor with capped backoff, until the deadline. 401/403 stop the
    crawl (a key problem, not a brownout). A cursor that points at itself
    stops the crawl instead of looping.
  * The API key comes from MASSIVE_API_KEY_STOCKS and is never written to disk
    or logs: every stored URL has its apiKey stripped.

Run (host data dir mounted at /out):
    python vx_financials_snapshot.py --out /out
Check the finished snapshot (page gaps, duplicates, counts -> manifest.json):
    python vx_financials_snapshot.py --out /out --verify
Cross-check named tickers against a fresh per-ticker read of the feed:
    python vx_financials_snapshot.py --out /out --crosscheck AAPL,MSFT,AIR
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import sys
import time
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE = "https://api.massive.com/vX/reference/financials"
FIRST_PARAMS = {"sort": "filing_date", "order": "asc", "limit": "100"}
KEY_ENV = "MASSIVE_API_KEY_STOCKS"
# The endpoint's own `Sunset` header on 2026-09-30. Keep retrying through
# brownouts until a day past it, then stop with the resume point saved.
SUNSET_UTC = datetime(2026, 10, 9, tzinfo=timezone.utc)
DEADLINE_EPOCH = SUNSET_UTC.timestamp() + 86400
BACKOFF_BASE_SEC = 15.0
BACKOFF_CAP_SEC = 900.0
TIMEOUT_SEC = 90
RETRY_STATUSES = {408, 410, 425, 429, 500, 502, 503, 504}
FATAL_STATUSES = {400, 401, 403, 404}
ROW_KEY_FIELDS = ("cik", "timeframe", "fiscal_year", "fiscal_period",
                  "start_date", "end_date", "filing_date")


class Fatal(RuntimeError):
    """The crawl must stop; state.json still holds the resume point."""


class DeadlineReached(RuntimeError):
    """Past the sunset + 1 day; state.json still holds the resume point."""


# ---------------------------------------------------------------------------
# URLs — the key is added per request and stripped before anything is stored
# ---------------------------------------------------------------------------
def strip_key(url: str) -> str:
    parts = urlsplit(url)
    q = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
         if k.lower() != "apikey"]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def with_key(url: str, key: str) -> str:
    parts = urlsplit(strip_key(url))
    q = parse_qsl(parts.query, keep_blank_values=True) + [("apiKey", key)]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment))


def first_url() -> str:
    return f"{BASE}?{urlencode(FIRST_PARAMS)}"


def backoff(attempt: int) -> float:
    return min(BACKOFF_CAP_SEC, BACKOFF_BASE_SEC * (2 ** max(0, attempt)))


# ---------------------------------------------------------------------------
# files
# ---------------------------------------------------------------------------
def _atomic_write(path: str, data: bytes) -> None:
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def page_path(out: str, n: int) -> str:
    return os.path.join(out, "pages", f"{n:06d}.json.gz")


def load_state(out: str) -> dict:
    p = os.path.join(out, "state.json")
    if not os.path.exists(p):
        return {"next_url": first_url(), "pages": 0, "rows": 0, "done": False,
                "null_filing_date_rows": 0, "first_filing_date": None,
                "last_filing_date": None, "started_at": _now_iso(), "retries": 0}
    with open(p) as fh:
        return json.load(fh)


def save_state(out: str, state: dict) -> None:
    state["updated_at"] = _now_iso()
    _atomic_write(os.path.join(out, "state.json"),
                  json.dumps(state, indent=1, sort_keys=True).encode())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# fetch — one page, retried on the SAME cursor until it answers
# ---------------------------------------------------------------------------
def fetch_page(session, url: str, key: str, *, sleep: Callable[[float], None],
               now: Callable[[], float], deadline: float,
               log: Callable[[str], None]) -> Tuple[dict, int]:
    """(body, retries) for `url`. Raises Fatal / DeadlineReached; never skips."""
    attempt = 0
    while True:
        if now() > deadline:
            raise DeadlineReached(f"past the deadline while fetching {strip_key(url)}")
        status, body, why = None, None, ""
        try:
            r = session.get(with_key(url, key), timeout=TIMEOUT_SEC)
            status = r.status_code
            if status == 200:
                body = r.json()
                if not isinstance(body, dict):
                    body, why = None, "body is not a JSON object"
                elif str(body.get("status") or "OK").upper() not in ("OK", "DELAYED"):
                    why = f"body status {body.get('status')!r}"
                    body = None
            elif status in FATAL_STATUSES:
                raise Fatal(f"HTTP {status} on {strip_key(url)} — check the key/plan")
            else:
                why = f"HTTP {status}"
        except Fatal:
            raise
        except Exception as exc:                               # noqa: BLE001
            body, why = None, f"{type(exc).__name__}"
        if body is not None:
            return body, attempt
        wait = backoff(attempt)
        log(f"retry {attempt + 1} in {wait:.0f}s ({why}) on {strip_key(url)}")
        sleep(wait)
        attempt += 1


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------
def crawl(out: str, session, key: str, *, sleep: Callable[[float], None] = time.sleep,
          now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
          max_pages: Optional[int] = None,
          log: Callable[[str], None] = lambda m: print(m, flush=True)) -> dict:
    if not key:
        raise Fatal(f"{KEY_ENV} is not set")
    os.makedirs(os.path.join(out, "pages"), exist_ok=True)
    state = load_state(out)
    fetched = 0
    while not state.get("done"):
        if max_pages is not None and fetched >= max_pages:
            break
        url = state["next_url"]
        body, retries = fetch_page(session, url, key, sleep=sleep, now=now,
                                   deadline=deadline, log=log)
        results = body.get("results") or []
        n = int(state["pages"])
        record = {"page": n, "url": strip_key(url), "request_id": body.get("request_id"),
                  "fetched_at": _now_iso(), "results": results}
        _atomic_write(page_path(out, n), gzip.compress(json.dumps(record).encode()))
        nxt = body.get("next_url")
        if nxt and strip_key(nxt) == strip_key(url):
            save_state(out, state)
            raise Fatal(f"next_url points at itself on page {n}: {strip_key(url)}")
        dates = [r.get("filing_date") for r in results if isinstance(r, dict)]
        real = sorted(d for d in dates if d)
        state["pages"] = n + 1
        state["rows"] = int(state["rows"]) + len(results)
        state["null_filing_date_rows"] = int(state.get("null_filing_date_rows") or 0) + \
            sum(1 for d in dates if not d)
        state["retries"] = int(state.get("retries") or 0) + retries
        if real:
            state["first_filing_date"] = state.get("first_filing_date") or real[0]
            state["last_filing_date"] = real[-1]
        state["next_url"] = strip_key(nxt) if nxt else None
        state["done"] = not nxt
        save_state(out, state)
        fetched += 1
        if state["pages"] % 50 == 0 or state["done"]:
            log(f"page {state['pages']} rows {state['rows']} last filing "
                f"{state.get('last_filing_date')} retries {state['retries']}")
    return state


# ---------------------------------------------------------------------------
# verify — every page present, rows counted, duplicates named
# ---------------------------------------------------------------------------
def row_key(r: dict) -> tuple:
    return tuple(str(r.get(f)) for f in ROW_KEY_FIELDS)


def iter_pages(out: str) -> Iterable[Tuple[int, dict]]:
    d = os.path.join(out, "pages")
    names = sorted(f for f in os.listdir(d) if f.endswith(".json.gz"))
    for name in names:
        with gzip.open(os.path.join(d, name)) as fh:
            yield int(name.split(".")[0]), json.load(fh)


def verify(out: str) -> dict:
    state = load_state(out)
    seen: Dict[tuple, int] = {}
    pages: List[int] = []
    rows = dup = null_fd = 0
    by_year: Dict[str, int] = {}
    by_tf: Dict[str, int] = {}
    ciks = set()
    for n, rec in iter_pages(out):
        pages.append(n)
        for r in rec.get("results") or []:
            rows += 1
            k = row_key(r)
            if k in seen:
                dup += 1
            seen[k] = seen.get(k, 0) + 1
            fd = r.get("filing_date")
            if not fd:
                null_fd += 1
            yr = (fd or "null")[:4]
            by_year[yr] = by_year.get(yr, 0) + 1
            tf = str(r.get("timeframe"))
            by_tf[tf] = by_tf.get(tf, 0) + 1
            if r.get("cik"):
                ciks.add(r["cik"])
    expected = int(state.get("pages") or 0)
    gaps = sorted(set(range(expected)) - set(pages))
    extra = sorted(set(pages) - set(range(expected)))
    ok = bool(state.get("done")) and not gaps and not extra and rows == int(state.get("rows") or 0)
    manifest = {"verified_at": _now_iso(), "ok": ok, "done": bool(state.get("done")),
                "pages": len(pages), "state_pages": expected, "gaps": gaps[:50],
                "gap_count": len(gaps), "extra_pages": extra[:50], "rows": rows,
                "state_rows": state.get("rows"), "unique_rows": len(seen),
                "duplicate_rows": dup, "null_filing_date_rows": null_fd,
                "ciks": len(ciks), "by_filing_year": dict(sorted(by_year.items())),
                "by_timeframe": dict(sorted(by_tf.items())),
                "row_key_fields": list(ROW_KEY_FIELDS), "sunset": SUNSET_UTC.date().isoformat()}
    _atomic_write(os.path.join(out, "manifest.json"),
                  json.dumps(manifest, indent=1).encode())
    return manifest


def crosscheck(out: str, session, key: str, tickers: List[str], *,
               sleep: Callable[[float], None] = time.sleep,
               now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
               log: Callable[[str], None] = lambda m: print(m, flush=True)) -> dict:
    """Every row a fresh per-ticker read returns must already be in the snapshot."""
    have = set()
    for _, rec in iter_pages(out):
        for r in rec.get("results") or []:
            have.add(row_key(r))
    report = {}
    for t in tickers:
        url = f"{BASE}?{urlencode({'ticker': t, 'limit': '100'})}"
        fresh: List[dict] = []
        while url:
            body, _ = fetch_page(session, url, key, sleep=sleep, now=now,
                                 deadline=deadline, log=log)
            fresh.extend(body.get("results") or [])
            nxt = body.get("next_url")
            url = strip_key(nxt) if nxt and strip_key(nxt) != strip_key(url) else None
        missing = [row_key(r) for r in fresh if row_key(r) not in have]
        report[t] = {"fresh_rows": len(fresh), "missing": len(missing),
                     "missing_sample": [list(m) for m in missing[:5]]}
        log(f"crosscheck {t}: {len(fresh)} rows, {len(missing)} missing")
    return report


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--crosscheck", default="")
    ap.add_argument("--max-pages", type=int, default=None)
    a = ap.parse_args(argv)
    if a.verify:
        m = verify(a.out)
        print(json.dumps({k: v for k, v in m.items() if k != "by_filing_year"}, indent=1))
        return 0 if m["ok"] else 1
    import requests
    key = os.environ.get(KEY_ENV, "")
    session = requests.Session()
    if a.crosscheck:
        rep = crosscheck(a.out, session, key, [t.strip().upper() for t in a.crosscheck.split(",") if t.strip()])
        _atomic_write(os.path.join(a.out, "crosscheck.json"), json.dumps(rep, indent=1).encode())
        return 0 if all(v["missing"] == 0 for v in rep.values()) else 1
    try:
        st = crawl(a.out, session, key, max_pages=a.max_pages)
    except DeadlineReached as exc:
        print(f"STOPPED: {exc}", flush=True)
        return 2
    print(f"{'DONE' if st.get('done') else 'PAUSED'}: {st['pages']} pages, {st['rows']} rows",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
