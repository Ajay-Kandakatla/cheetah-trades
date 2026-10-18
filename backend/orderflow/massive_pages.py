"""Windowed, parallel paging of Massive /v3/trades and /v3/quotes (DECISIONS14 D1–D7, D11, D12).

Ajay 2026-10-18: "I see a big lag in Tap reading its 30 secs this feature. Can we make it fast."

WHY (measured 2026-10-18, docs/orderflow/parallel_fetch_2026_10_18.md): one 50k-row page costs
~2 s of Massive server latency and the serial pager paid it page after page, because page N+1
waits on page N's `next_url`. Bandwidth and JSON parsing are noise. So the day is cut into
disjoint time windows and the windows are paged at the same time.

D1 — one shared pager. The ET day is split into contiguous, exclusive `[gte, lt)` nanosecond
windows; each window follows its own `next_url` chain; the windows run in a ThreadPoolExecutor;
page frames come back in WINDOW order (ascending time) and the callers' existing
`sort_values("ts_utc")` runs unchanged. `tape.fetch_trades` and `quotes.fetch_quotes` both call
`fetch_windowed`. HTTP stays `requests.get`, looked up at call time.

D2 — window edges (MINE): short windows at the open and the close where the tape is dense,
hourly midday, one window each for pre- and post-market. A half day yields empty afternoon
windows. Trades use the 13 windows over 04:00–20:00, quotes the 11 inside 09:30–16:00 (the 12
edges inside the session bound 11 windows).

D3 — FETCH_WORKERS (MINE) windows in flight per pull. The 429 path stays: sleep, retry.

D4 / D12 — the page cap is per WINDOW (the callers own the numbers). A window that hits its cap
is `truncated`: a heavy tape loses the tail of THAT window, not the whole afternoon.

D5 — `covered`: per window, the span actually held. A window that completed ("ok") is fully KNOWN
whatever its row count — zero NBBO updates means the prior quote stayed prevailing — so its END is
`lt`; a window that stopped early ends at `last_ts + 1 ns`; a window that did not complete and held
no rows adds nothing. Its START is `gte` for the first window or when the previous window's span
reached that window's `lt` (it completed, and itself started from known ground); otherwise its OWN
first timestamp (critic LOW 2026-10-18, widened): the gap after a capped / failed window is not
held, and a completed window with no rows right after such a gap has no first quote to start from,
so it adds nothing and the gap carries on to the next window. The quote rule classifies only inside covered spans (orderflow/quotes.covered_mask).

D6 — 429s: `max_429=None` retries without a cap (every caller but tape_control). With `max_429`
set, a window's (max_429 + 1)-th 429 sets a shared stop event; every other window ends after its
in-flight request ("stopped") and the pull's `fault` is "rate_limited". Workers never touch a
thread-local: the CALLER thread reads `fault` and owns any per-thread state.

D7 — errors are reported per window (status "http" / "error" / "stopped", counted in `failed`)
with the pages that window held; each fetcher decides what a failure means (trades: the pull is
None; quotes: the other windows stand and `covered` tells the truth).

D11 — every page is compacted as it arrives: the caller's `compact(results) -> DataFrame` turns
the page's raw list of dicts (≈ 700 B/row as Python objects) into a small frame and the list is
dropped, so a pull holds frames, never the whole day as dicts. `PullResult.frames` (window order)
is what the fetchers concat.

Pure transport: no Mongo, no clock. Never logs the API key (exceptions go through
sepa.prices._scrub_key).
"""
from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional

import pandas as pd

_log = logging.getLogger("orderflow.massive_pages")

WINDOW_EDGES_ET = ("04:00", "09:30", "09:45", "10:00", "10:30", "11:00", "12:00", "13:00",
                   "14:00", "15:00", "15:30", "15:45", "16:00", "20:00")   # MINE (DECISIONS14 D2)
FETCH_WORKERS = 8                 # MINE (DECISIONS14 D3) — windows in flight per pull
RETRY_429_SLEEP_SEC = 2           # unchanged from the serial pager

_NS = 1_000_000_000


def _et_zone():
    from zoneinfo import ZoneInfo
    return ZoneInfo("America/New_York")


def _hm(edge) -> tuple[int, int]:
    if isinstance(edge, str):
        h, m = edge.split(":")
        return int(h), int(m)
    h, m = edge
    return int(h), int(m)


def _ns(day, hm: tuple[int, int], et) -> int:
    dt = datetime(day.year, day.month, day.day, hm[0], hm[1], tzinfo=et)
    return int(dt.timestamp()) * _NS


def windows_for(day, start_hm: tuple[int, int], end_hm: tuple[int, int],
                edges=None) -> list[tuple[int, int]]:
    """Contiguous exclusive [gte_ns, lt_ns) windows for one ET day, clipped to [start_hm, end_hm).

    Edges strictly inside the span split it; start/end always appear; result sorted, no gaps,
    no overlap. `edges` None reads WINDOW_EDGES_ET at CALL time (tests narrow it). PURE."""
    edges = WINDOW_EDGES_ET if edges is None else edges
    et = _et_zone()
    start, end = _ns(day, _hm(start_hm), et), _ns(day, _hm(end_hm), et)
    if end <= start:
        return []
    inner = {_ns(day, _hm(e), et) for e in edges}
    points = sorted({start, end} | {p for p in inner if start < p < end})
    return list(zip(points[:-1], points[1:]))


@dataclass
class WindowResult:
    gte_ns: int
    lt_ns: int
    frames: list = field(default_factory=list)   # compacted page frames (D11), in page order
    n_rows: int = 0
    pages: int = 0
    truncated: bool = False
    first_ts_ns: Optional[int] = None  # min timestamp held (sip, else participant); None if no rows
    last_ts_ns: Optional[int] = None   # max timestamp held (sip, else participant); None if no rows
    status: str = "ok"                 # "ok" | "truncated" | "http" | "error" | "rate_limited" | "stopped"
    n_429: int = 0


@dataclass
class PullResult:
    frames: list                      # every window's page frames, in window order (flat)
    n_rows: int                       # rows across all frames
    truncated: bool                   # any window status == "truncated"
    covered: list                     # [(start_ns, end_ns)] actually held per window (see D5)
    fault: Optional[str]              # "rate_limited" when a window exceeded max_429, else None
    failed: int                       # windows with status http | error | stopped
    windows: list                     # [WindowResult] in window order


def _ts_bounds(frame) -> tuple[Optional[int], Optional[int]]:
    """(min, max) of a page frame's sip_timestamp (else participant_timestamp), one pass each."""
    col = ("sip_timestamp" if "sip_timestamp" in frame.columns
           else "participant_timestamp" if "participant_timestamp" in frame.columns else None)
    if col is None or not len(frame):
        return None, None
    lo, hi = frame[col].min(), frame[col].max()
    if pd.isna(lo) or pd.isna(hi):
        return None, None
    return int(lo), int(hi)


def _scrub(exc) -> str:
    try:
        from sepa.prices import _scrub_key
        return _scrub_key(exc)
    except Exception:
        return type(exc).__name__


def _pull_window(url: str, key: str, gte: int, lt: int, *, limit: int, timeout: float,
                 pages_per_window: int, max_429: Optional[int], stop: threading.Event,
                 compact: Callable, label: str, log) -> WindowResult:
    import requests

    w = WindowResult(gte_ns=gte, lt_ns=lt)
    next_url = url
    params = {"timestamp.gte": gte, "timestamp.lt": lt, "order": "asc", "sort": "timestamp",
              "limit": limit, "apiKey": key}
    while True:
        if stop.is_set():
            w.status = "stopped"
            break
        try:
            r = requests.get(next_url, params=params, timeout=timeout)
            code = r.status_code
            if code == 429:
                w.n_429 += 1
                if max_429 is not None and w.n_429 > max_429:
                    stop.set()
                    log.warning("%s -> HTTP 429 x%d: gave up (max_429=%d)", label, w.n_429, max_429)
                    w.status = "rate_limited"
                    break
                time.sleep(RETRY_429_SLEEP_SEC)
                continue
            if code != 200:
                log.warning("%s -> HTTP %s: %s", label, code, (getattr(r, "text", "") or "")[:200])
                w.status = "http"
                break
            body = r.json() or {}
            nxt = body.get("next_url")
            frame = compact(body.get("results") or [])   # D11: the raw list is dropped right here
            del body
        except Exception as exc:
            log.warning("%s fetch failed (page %d): %s", label, w.pages, _scrub(exc))
            w.status = "error"
            break
        if frame is not None and len(frame):
            w.frames.append(frame)
            w.n_rows += len(frame)
            lo, hi = _ts_bounds(frame)
            if lo is not None:
                w.first_ts_ns = lo if w.first_ts_ns is None else min(w.first_ts_ns, lo)
                w.last_ts_ns = hi if w.last_ts_ns is None else max(w.last_ts_ns, hi)
        if not nxt:
            w.status = "ok"
            break
        w.pages += 1
        if w.pages >= pages_per_window:
            w.status = "truncated"
            w.truncated = True
            break
        next_url = nxt
        params = {"apiKey": key}          # next_url carries its own cursor params
    return w


def fetch_windowed(url: str, key: str, *, windows, limit: int, timeout: float, pages_per_window: int,
                   compact: Callable, max_429: Optional[int] = None, workers: int = FETCH_WORKERS,
                   label: str = "massive", log=None) -> PullResult:
    """Page every `[gte, lt)` window of `windows` in parallel; see the module docstring (D1–D7, D11).

    `compact(results: list[dict]) -> DataFrame` is REQUIRED: it runs on every page as it arrives."""
    if not callable(compact):
        raise TypeError("fetch_windowed needs compact(results) -> DataFrame (DECISIONS14 D11)")
    log = log or _log
    windows = list(windows)
    if not windows:
        return PullResult(frames=[], n_rows=0, truncated=False, covered=[], fault=None, failed=0,
                          windows=[])
    stop = threading.Event()
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(windows)))) as pool:
        futs = [pool.submit(_pull_window, url, key, gte, lt, limit=limit, timeout=timeout,
                            pages_per_window=max(1, int(pages_per_window)), max_429=max_429,
                            stop=stop, compact=compact, label=label, log=log)
                for gte, lt in windows]
        results = [f.result() for f in futs]          # WINDOW order, not completion order

    frames: list = []
    covered: list = []
    known_to_start = True             # the first window starts at its gte
    for w in results:
        frames.extend(w.frames)
        # START: `gte` for the first window or when the previous span reached its window's `lt`;
        # otherwise this window's own first row (None when it has none). END: `lt` when "ok" —
        # rows or not, a completed window is known — else last_ts + 1 ns; nothing when a window
        # did not complete and held no rows. This window's own status never moves its start.
        start = w.gte_ns if known_to_start else w.first_ts_ns
        reached_lt = False
        if start is not None:
            if w.status == "ok":
                covered.append((start, w.lt_ns))
                reached_lt = True
            elif w.n_rows and w.last_ts_ns is not None:
                covered.append((start, min(w.last_ts_ns + 1, w.lt_ns)))
        known_to_start = reached_lt
    return PullResult(
        frames=frames,
        n_rows=sum(w.n_rows for w in results),
        truncated=any(w.status == "truncated" for w in results),
        covered=covered,
        fault="rate_limited" if any(w.status == "rate_limited" for w in results) else None,
        failed=sum(1 for w in results if w.status in ("http", "error", "stopped")),
        windows=results,
    )
