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
    Rows with a null filing_date come first (the feed treats null as the 1970
    epoch) and are kept.
  * Each page is written atomically to pages/NNNNNN.json.gz, THEN state.json
    advances. A restart resumes from state.json: no page is re-fetched and
    none is skipped.
  * 410 (brownout), 429, 5xx, timeouts and unreadable bodies are retried on
    the SAME cursor with capped backoff, until the deadline. 400/401/403/404
    stop the crawl (a key or request problem, not a brownout). A cursor that
    points at itself stops the crawl instead of looping.
  * The crawl is only DONE when its last page reaches the feed's newest
    filing_date (probed once at the start). A page with no next_url before
    that is a cut-off answer: the same cursor is asked again.
  * The API key comes from MASSIVE_API_KEY_STOCKS and is never written to disk
    or logs: every stored URL has its apiKey stripped.

What one pass cannot see, and the top-up that catches it (critic 2026-09-30)
  * A 10-K makes the feed add a derived Q4 row with filing_date=null. It sorts
    at the front, behind a cursor that already moved on.
  * Filings newer than the crawl's last page.
  * Rows that tie on the server's cursor key (filing_date, cik, fiscal_year,
    fiscal_period — timeframe is not in it): a page break between two such
    rows could skip one.
  `topup` re-walks the null section, walks the dated tail from the crawl's
  last filing_date, and re-reads every tied CIK by cik=, keeping only rows
  the snapshot lacks (counted per row_key, so true duplicates survive).

Run (host data dir mounted at /out) — crawl, then top up every 12 h until
6 h before the sunset:
    python vx_financials_snapshot.py --out /out --follow
Check the snapshot (page gaps, duplicates, ties, counts -> manifest.json):
    python vx_financials_snapshot.py --out /out --verify
Cross-check tickers or cik:NNNNNNNNNN against a fresh read of the feed:
    python vx_financials_snapshot.py --out /out --crosscheck AAPL,MSFT,cik:0000001750
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import sys
import time
from collections import Counter
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
# The last top-up runs this long before the sunset; top-ups repeat this often.
FOLLOW_STOP_EPOCH = SUNSET_UTC.timestamp() - 6 * 3600
FOLLOW_EVERY_SEC = 12 * 3600
# 410s are random per-request brownouts (~15-30% of GETs on 2026-09-30), not
# long windows: a short first wait is what sets the crawl's speed.
BACKOFF_BASE_SEC = 3.0
BACKOFF_CAP_SEC = 900.0
TIMEOUT_SEC = 90
FATAL_STATUSES = {400, 401, 403, 404}
ROW_KEY_FIELDS = ("cik", "timeframe", "fiscal_year", "fiscal_period",
                  "start_date", "end_date", "filing_date")
CURSOR_KEY_FIELDS = ("filing_date", "cik", "fiscal_year", "fiscal_period")


class Fatal(RuntimeError):
    """The crawl must stop; state.json still holds the resume point."""


class DeadlineReached(RuntimeError):
    """Past the sunset + 1 day; state.json still holds the resume point."""


Log = Callable[[str], None]


def _print(m: str) -> None:
    print(m, flush=True)


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


def newest_url() -> str:
    return f"{BASE}?{urlencode({'sort': 'filing_date', 'order': 'desc', 'limit': '1', 'filing_date.gte': '2000-01-01'})}"


def tail_url(since: str) -> str:
    return f"{BASE}?{urlencode({**FIRST_PARAMS, 'filing_date.gte': since})}"


def cik_url(cik: str) -> str:
    return f"{BASE}?{urlencode({'cik': cik, 'limit': '100'})}"


def ticker_url(ticker: str) -> str:
    return f"{BASE}?{urlencode({'ticker': ticker, 'limit': '100'})}"


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
                "last_filing_date": None, "newest_filing_date": None,
                "started_at": _now_iso(), "retries": 0, "premature_ends": 0,
                "topups": []}
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
               now: Callable[[], float], deadline: float, log: Log) -> Tuple[dict, int]:
    """(body, retries) for `url`. Raises Fatal / DeadlineReached; never skips."""
    attempt = 0
    while True:
        if now() > deadline:
            raise DeadlineReached(f"past the deadline while fetching {strip_key(url)}")
        body, why = None, ""
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


def walk(session, url: str, key: str, on_page: Callable[[List[dict]], bool], *,
         sleep: Callable[[float], None], now: Callable[[], float], deadline: float,
         log: Log) -> int:
    """Hand each page's rows to `on_page` through the next_urls (nothing is
    held in memory); `on_page` returning True ends the walk. Returns pages."""
    pages = 0
    while url:
        body, _ = fetch_page(session, url, key, sleep=sleep, now=now, deadline=deadline, log=log)
        pages += 1
        if on_page([r for r in (body.get("results") or []) if isinstance(r, dict)]):
            break
        nxt = body.get("next_url")
        if nxt and strip_key(nxt) == strip_key(url):
            raise Fatal(f"next_url points at itself: {strip_key(url)}")
        url = strip_key(nxt) if nxt else ""
    return pages


def probe_newest(session, key: str, **kw) -> str:
    body, _ = fetch_page(session, newest_url(), key, **kw)
    rows = body.get("results") or []
    d = rows[0].get("filing_date") if rows and isinstance(rows[0], dict) else None
    if not d:
        raise Fatal("could not read the feed's newest filing_date")
    return str(d)


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------
def crawl(out: str, session, key: str, *, sleep: Callable[[float], None] = time.sleep,
          now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
          max_pages: Optional[int] = None, log: Log = _print) -> dict:
    if not key:
        raise Fatal(f"{KEY_ENV} is not set")
    os.makedirs(os.path.join(out, "pages"), exist_ok=True)
    state = load_state(out)
    kw = dict(sleep=sleep, now=now, deadline=deadline, log=log)
    if not state.get("done") and not state.get("newest_filing_date"):
        state["newest_filing_date"] = probe_newest(session, key, **kw)
        save_state(out, state)
        log(f"feed's newest filing_date {state['newest_filing_date']}")
    fetched = 0
    cut_offs = 0
    while not state.get("done"):
        if max_pages is not None and fetched >= max_pages:
            break
        url = state["next_url"]
        body, retries = fetch_page(session, url, key, **kw)
        results = body.get("results") or []
        nxt = body.get("next_url")
        if nxt and strip_key(nxt) == strip_key(url):
            raise Fatal(f"next_url points at itself on page {state['pages']}: {strip_key(url)}")
        dates = [r.get("filing_date") for r in results if isinstance(r, dict)]
        real = sorted(d for d in dates if d)
        last = real[-1] if real else state.get("last_filing_date")
        if not nxt and (last or "") < state["newest_filing_date"]:
            # No next_url before the newest filing: a cut-off answer, not the
            # end. Nothing is recorded; the same cursor is asked again.
            state["premature_ends"] = int(state.get("premature_ends") or 0) + 1
            save_state(out, state)
            wait = backoff(cut_offs)
            log(f"cut-off page (no next_url, last filing {last} < newest "
                f"{state['newest_filing_date']}); asking again in {wait:.0f}s")
            sleep(wait)
            cut_offs += 1
            continue
        cut_offs = 0
        n = int(state["pages"])
        record = {"page": n, "url": strip_key(url), "request_id": body.get("request_id"),
                  "fetched_at": _now_iso(), "results": results}
        _atomic_write(page_path(out, n), gzip.compress(json.dumps(record).encode()))
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
# rows — keys are hashed (12 bytes) so ~1M rows index in ~150 MB, not GBs
# ---------------------------------------------------------------------------
def row_key(r: dict) -> tuple:
    return tuple(str(r.get(f)) for f in ROW_KEY_FIELDS)


def cursor_key(r: dict) -> tuple:
    return tuple(str(r.get(f)) for f in CURSOR_KEY_FIELDS)


def _h(t: tuple) -> bytes:
    return hashlib.blake2b("\x1f".join(t).encode(), digest_size=12).digest()


def iter_pages(out: str) -> Iterable[Tuple[int, dict]]:
    d = os.path.join(out, "pages")
    names = sorted(f for f in os.listdir(d) if f.endswith(".json.gz"))
    for name in names:
        with gzip.open(os.path.join(d, name)) as fh:
            yield int(name.split(".")[0]), json.load(fh)


def iter_topups(out: str) -> Iterable[dict]:
    d = os.path.join(out, "topup")
    if not os.path.isdir(d):
        return
    for name in sorted(f for f in os.listdir(d) if f.endswith(".json.gz")):
        with gzip.open(os.path.join(d, name)) as fh:
            yield json.load(fh)


def iter_all_rows(out: str) -> Iterable[dict]:
    for _, rec in iter_pages(out):
        for r in rec.get("results") or []:
            yield r
    for rec in iter_topups(out):
        for r in rec.get("results") or []:
            yield r


class Index:
    """How many copies of each row_key the snapshot holds, and which CIKs
    have rows that tie on the server's cursor key."""

    def __init__(self) -> None:
        self.have: Counter = Counter()
        self._cur: Counter = Counter()
        self.tie_ciks: set = set()

    def add(self, r: dict) -> None:
        self.have[_h(row_key(r))] += 1
        c = _h(cursor_key(r))
        self._cur[c] += 1
        if self._cur[c] == 2 and r.get("cik"):
            self.tie_ciks.add(str(r["cik"]))


def build_index(out: str) -> Index:
    idx = Index()
    for r in iter_all_rows(out):
        idx.add(r)
    return idx


class Missing:
    """Streams one fresh read; keeps a row when its n-th copy in the read
    exceeds the copies the snapshot holds (so true duplicates survive)."""

    def __init__(self, idx: Index) -> None:
        self.idx = idx
        self.seen: Counter = Counter()
        self.rows: List[dict] = []
        self.fresh = 0

    def feed(self, rows: List[dict]) -> None:
        for r in rows:
            self.fresh += 1
            k = _h(row_key(r))
            self.seen[k] += 1
            if self.seen[k] > self.idx.have.get(k, 0):
                self.rows.append(r)

    def commit(self) -> List[dict]:
        for r in self.rows:
            self.idx.add(r)
        return self.rows


def missing_rows(fresh: List[dict], idx: Index) -> List[dict]:
    m = Missing(idx)
    m.feed(fresh)
    return m.rows


# ---------------------------------------------------------------------------
# top-up — rows one forward pass cannot see
# ---------------------------------------------------------------------------
def topup(out: str, session, key: str, *, sleep: Callable[[float], None] = time.sleep,
          now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
          log: Log = _print) -> dict:
    if not key:
        raise Fatal(f"{KEY_ENV} is not set")
    state = load_state(out)
    if not state.get("done"):
        raise Fatal("top-up runs only after the main crawl is done")
    kw = dict(sleep=sleep, now=now, deadline=deadline, log=log)
    idx = build_index(out)
    added: Dict[str, List[dict]] = {}

    m = Missing(idx)

    def _nulls(page: List[dict]) -> bool:
        m.feed([r for r in page if not r.get("filing_date")])
        return any(r.get("filing_date") for r in page)
    walk(session, first_url(), key, _nulls, **kw)
    added["null_section"] = m.commit()

    since = state.get("last_filing_date") or "2000-01-01"
    m = Missing(idx)
    walk(session, tail_url(since), key, lambda page: m.feed(page) or False, **kw)
    added["tail"] = m.commit()

    ties = sorted(idx.tie_ciks)
    added["ties"] = []
    for cik in ties:
        m = Missing(idx)
        walk(session, cik_url(cik), key, lambda page: m.feed(page) or False, **kw)
        added["ties"].extend(m.commit())

    run = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    counts = {k: len(v) for k, v in added.items()}
    rows = [r for v in added.values() for r in v]
    if rows:
        os.makedirs(os.path.join(out, "topup"), exist_ok=True)
        _atomic_write(os.path.join(out, "topup", f"{run}.json.gz"),
                      gzip.compress(json.dumps({"run": run, "added": counts,
                                                "tail_since": since, "tied_ciks": ties,
                                                "results": rows}).encode()))
    state = load_state(out)
    state.setdefault("topups", []).append({"run": run, "added": counts,
                                           "tail_since": since, "tied_ciks": len(ties)})
    save_state(out, state)
    log(f"top-up {run}: {counts} (tied CIKs re-read: {len(ties)})")
    return {"run": run, "added": counts, "tied_ciks": ties}


# ---------------------------------------------------------------------------
# verify — every page present, rows counted, duplicates and ties named
# ---------------------------------------------------------------------------
def verify(out: str) -> dict:
    state = load_state(out)
    pages: List[int] = []
    page_rows = 0
    for n, rec in iter_pages(out):
        pages.append(n)
        page_rows += len(rec.get("results") or [])
    idx = Index()
    null_fd = 0
    by_year: Dict[str, int] = {}
    by_tf: Dict[str, int] = {}
    ciks = set()
    for r in iter_all_rows(out):
        idx.add(r)
        fd = r.get("filing_date")
        if not fd:
            null_fd += 1
        yr = (fd or "null")[:4]
        by_year[yr] = by_year.get(yr, 0) + 1
        tf = str(r.get("timeframe"))
        by_tf[tf] = by_tf.get(tf, 0) + 1
        if r.get("cik"):
            ciks.add(r["cik"])
    total = sum(idx.have.values())
    ties = sorted(idx.tie_ciks)
    expected = int(state.get("pages") or 0)
    gaps = sorted(set(range(expected)) - set(pages))
    extra = sorted(set(pages) - set(range(expected)))
    newest = state.get("newest_filing_date")
    reached = bool(newest) and (state.get("last_filing_date") or "") >= newest
    ok = (bool(state.get("done")) and reached and not gaps and not extra
          and page_rows == int(state.get("rows") or 0))
    manifest = {"verified_at": _now_iso(), "ok": ok, "done": bool(state.get("done")),
                "reached_newest_filing": reached, "newest_filing_date": newest,
                "last_filing_date": state.get("last_filing_date"),
                "pages": len(pages), "state_pages": expected, "gaps": gaps[:50],
                "gap_count": len(gaps), "extra_pages": extra[:50],
                "page_rows": page_rows, "state_rows": state.get("rows"),
                "topup_rows": total - page_rows, "rows": total,
                "unique_rows": len(idx.have), "duplicate_rows": total - len(idx.have),
                "null_filing_date_rows": null_fd, "ciks": len(ciks),
                "cursor_key_tie_ciks": len(ties), "cursor_key_tie_sample": ties[:50],
                "premature_ends": state.get("premature_ends", 0),
                "topups": state.get("topups", []),
                "by_filing_year": dict(sorted(by_year.items())),
                "by_timeframe": dict(sorted(by_tf.items())),
                "row_key_fields": list(ROW_KEY_FIELDS), "sunset": SUNSET_UTC.date().isoformat()}
    _atomic_write(os.path.join(out, "manifest.json"),
                  json.dumps(manifest, indent=1).encode())
    return manifest


def crosscheck(out: str, session, key: str, names: List[str], *,
               sleep: Callable[[float], None] = time.sleep,
               now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
               log: Log = _print) -> dict:
    """Every row a fresh read returns (ticker, or cik:NNNNNNNNNN) must already
    be in the snapshot — counted per row_key, not as a set."""
    idx = build_index(out)
    report = {}
    for name in names:
        url = cik_url(name[4:]) if name.lower().startswith("cik:") else ticker_url(name)
        m = Missing(idx)
        walk(session, url, key, lambda page: m.feed(page) or False,
             sleep=sleep, now=now, deadline=deadline, log=log)
        report[name] = {"fresh_rows": m.fresh, "missing": len(m.rows),
                        "missing_sample": [list(row_key(r)) for r in m.rows[:5]]}
        log(f"crosscheck {name}: {m.fresh} rows, {len(m.rows)} missing")
    return report


def follow(out: str, session, key: str, *, sleep: Callable[[float], None] = time.sleep,
           now: Callable[[], float] = time.time, deadline: float = DEADLINE_EPOCH,
           stop_at: float = FOLLOW_STOP_EPOCH, every_sec: float = FOLLOW_EVERY_SEC,
           log: Log = _print) -> dict:
    """Crawl to the end, then top up every `every_sec` until `stop_at`."""
    kw = dict(sleep=sleep, now=now, deadline=deadline, log=log)
    crawl(out, session, key, **kw)
    while True:
        topup(out, session, key, **kw)
        m = verify(out)
        log(f"verify ok={m['ok']} rows={m['rows']} unique={m['unique_rows']} "
            f"tie CIKs={m['cursor_key_tie_ciks']}")
        if now() >= stop_at:
            return m
        sleep(min(every_sec, max(0.0, stop_at - now())))


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--verify", action="store_true")
    ap.add_argument("--follow", action="store_true")
    ap.add_argument("--topup", action="store_true")
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
    try:
        if a.crosscheck:
            names = [t.strip() for t in a.crosscheck.split(",") if t.strip()]
            names = [n if n.lower().startswith("cik:") else n.upper() for n in names]
            rep = crosscheck(a.out, session, key, names)
            _atomic_write(os.path.join(a.out, "crosscheck.json"),
                          json.dumps(rep, indent=1).encode())
            return 0 if all(v["missing"] == 0 for v in rep.values()) else 1
        if a.topup:
            topup(a.out, session, key)
            return 0
        if a.follow:
            m = follow(a.out, session, key)
            return 0 if m["ok"] else 1
        st = crawl(a.out, session, key, max_pages=a.max_pages)
    except DeadlineReached as exc:
        print(f"STOPPED: {exc}", flush=True)
        return 2
    print(f"{'DONE' if st.get('done') else 'PAUSED'}: {st['pages']} pages, {st['rows']} rows",
          flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
