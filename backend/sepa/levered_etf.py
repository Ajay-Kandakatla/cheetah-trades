"""🔗 Leveraged-ETF tags for the 🎢 High Beta tab (Ajay 2026-10-14).

The ask, verbatim: "Can you add a short tag on these stocks for their Leverage
equivalents like IRE for IREN, VSTL for VST".

THE MAP is built from DATA, never typed: the Massive reference list of every
ACTIVE fund (`FUND_TYPES` — ETF + ETS + ETN + ETV; IRE, his own IREN example,
is filed as ETS, so an ETF-only pull misses it) and every active common stock /
ADR (`STOCK_TYPES`). A fund is tagged to a stock only when its NAME states all
three of: the leverage (a factor above `MIN_FACTOR_EXCLUSIVE`), the direction
(Long / Bull, or Short / Bear / Inverse / a negative factor) and the stock —
either its ticker in the slot beside the direction word ("Tradr 2X Long IREN
Daily ETF", "Direxion Daily SOFI Bull 2X ETF") or, failing that, its exact
company name ("T-REX 2X Long Tesla Daily Target ETF" + "Tesla, Inc."). Never a
prefix, substring or fuzzy match. Every fund that fails a rule is COUNTED under
its reason (`SKIP_REASONS`), never guessed. A tagged fund must also have
printed on the last closed session (one grouped-daily read) — that read is the
tie order too (most traded first).

THE CACHE is ONE atomic Mongo doc (`COLL` / `DOC_ID`). Only a COMPLETE read
(every type, the grouped read, at least one tag) replaces it; a partial read
keeps the previous map and stamps the failure. The refresh runs on its own
daemon thread, at most once per ET day (claimed atomically in Mongo, retried
at most every `RETRY_SEC`), started by `load()` from the tab's warm build —
never on a request path, never blocking a build. The map hides past
`STALE_DAYS`.

Display only: nothing here gates a scan, sorts a list, sizes a position or
enters a lane. Not advice. stdlib-only at import (prices / symbols / Mongo /
the market calendar are imported lazily).
"""
from __future__ import annotations

import argparse
import collections
import json
import logging
import re
import sys
import threading
import time
from datetime import date, datetime, timezone
from typing import Optional

log = logging.getLogger("sepa.levered_etf")

COLL = "levered_etf_map"
DOC_ID = "latest"
REF_URL = "https://api.massive.com/v3/reference/tickers"
GROUPED_URL_FMT = "https://api.massive.com/v2/aggs/grouped/locale/us/market/stocks/{day}"
FUND_TYPES = ("ETF", "ETS", "ETN", "ETV")     # IRE (his IREN example) is ETS — an ETF-only pull misses it
STOCK_TYPES = ("CS", "ADRC")                  # == gajjala SCAN_INSTRUMENT_TYPES (test-pinned)
PAGE_LIMIT = 1000                             # TRANSPORT == gajjala TYPES_PAGE_LIMIT (test-pinned)
MAX_PAGES_PER_TYPE = 12                       # TRANSPORT — ETF 6 pages, CS 6 on 10-14; a cut pull = incomplete
HTTP_TIMEOUT_SEC = 30                         # TRANSPORT (fetch_type_map's)
REFRESH_BUDGET_SEC = 180                      # MINE — a refresh past this stops, incomplete, old map kept
RETRY_SEC = 3600                              # MINE — at most one attempt per hour after a failed one
MAP_MEMO_SEC = 600                            # MINE — in-process re-read of the Mongo doc (freshness, not a rule)
STALE_DAYS = 7                                # HIS CALL #5 default — hide every tag past this age
SHOW_MAX = 3                                  # HIS CALL #4 default — tickers on the chip, then "+n"
INCLUDE_SHORTS = True                         # HIS CALL #2 default — shorts listed after longs
MIN_FACTOR_EXCLUSIVE = 1.0                    # semantic "leveraged" = more than 1x; 1x inverse not tagged (HIS CALL #3)
NO_DIRECTION_LONG_ISSUERS = ()                # HIS CALL #1 — ("Corgi",) would tag Corgi's "X 2x Daily" as 2x long
MARK = "\U0001F517"                           # 🔗 — MINE (HIS CALL #8); never ⚡ / 🔻 (cardLadder rungs)
STAT_KEY = "Leveraged ETFs"                   # card fold stat key == table column head == cardLadder FOLD_KEYS
FACTOR_RE = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*[xX](?!\w)")
LONG_WORDS = frozenset({"long", "bull"})
SHORT_WORDS = frozenset({"short", "bear", "inverse"})
SLOT_AFTER = frozenset({"long", "short", "inverse"})
SLOT_BEFORE = frozenset({"bull", "bear"})
TICKER_TOKEN_RE = re.compile(r"^[A-Z][A-Z0-9]{0,4}(?:\.[A-Z])?$")
TOKEN_STRIP = "(),;:"
# Upper-case grammar words never read as a ticker in the slot (2026-10-14
# executor brief: "AND", "ETF", "DAILY", "LONG", "SHORT", "TARGET", "INVERSE").
# CLOSED and parity-neutral: none is an active CS/ADRC on the 10-14 list. BULL
# (Webull -> BULG) and ETN (Eaton -> ETNG) are REAL tickers tagged by real
# funds, so they are deliberately NOT here (word-like tickers are real).
NEVER_TICKER_WORDS = frozenset({"AND", "ETF", "ETFS", "ETNS", "DAILY", "TARGET", "LONG", "SHORT", "INVERSE"})
# Crypto coins whose symbol or name is ALSO a US stock's ticker / company name
# (2026-10-14 review, against the real CS/ADRC list): LINK = Interlink, TRX =
# TRX Gold, SUI = Sun Communities, LTC = LTC Properties, SEI = Solaris, ATOM =
# Atomera, APT = Alpha Pro Tech, TRON = Tron Inc., BONK = Bonk Inc. (BNKK).
# 21Shares / T-Rex / Defiance list coin funds ("2x Long HYPE"), so a coin fund
# must never put a 2x tag on the stock. CLOSED and FAIL-CLOSED: blocked in the
# ticker slot AND the name slot, counted no_us_underlying (a coin is not a US
# stock). A new colliding coin = a new line here, never a fuzzy rule.
COIN_SYMBOLS = frozenset({"LINK", "TRX", "SUI", "LTC", "SEI", "ATOM", "APT", "TRON", "BONK"})
GRAMMAR_WORDS = frozenset({"daily", "target", "etf", "etfs", "etn", "etns", "shares", "fund", "trust", "bull",
                           "bear", "long", "short", "inverse", "leveraged", "monthly", "quarterly"})
BEFORE_STOP = frozenset({"direxion"})
CORP_TAIL = ("american depositary shares", "american depository shares", "ordinary shares", "common stock",
             "capital stock", "class a", "class b", "class c", "inc", "corp", "corporation", "co", "company", "ltd",
             "limited", "plc", "n v", "nv", "s a", "sa", "ag", "se", "ads", "adr")  # trailing tokens ONLY; never "group"/"holdings"/"american"
SKIP_REASONS = ("no_direction", "both_directions", "multi_factor", "one_x", "ambiguous_ticker", "ambiguous_name",
                "no_slot", "no_us_underlying", "no_print")
COUNT_KEYS = ("funds_read", "with_factor", "tagged", "by_ticker", "by_name", "underlyings") + SKIP_REASONS
STATES = ("ready", "stale", "missing", "error")

_MINUS = "−"                             # "−" == high_beta_tab._MINUS (test-pinned)
_TAGGED = {"by_ticker": "ticker", "by_name": "name"}

# ---------------------------------------------------------------------------
# served words (every number from a constant or a count)
# ---------------------------------------------------------------------------
LINE_READY = (f"{MARK} Leveraged-ETF tags: {{n_on:,}} of these {{listed:,}} names have a single-stock leveraged "
              "ETF — {n_etfs:,} funds on {n_under:,} stocks in the Massive reference list as of {as_of_mmdd}, "
              "each traded on {grouped_mmdd}. Tagged only when the fund's name states the leverage (above "
              f"{MIN_FACTOR_EXCLUSIVE:g}×), the direction and the stock; not tagged: {{no_direction:,}} with no "
              f"direction in the name, {{one_x:,}} {MIN_FACTOR_EXCLUSIVE:g}× inverse, {{no_us:,}} index, sector, "
              "coin, unclear or untraded funds — counted, never guessed. Display only — not advice.")
LINE_STALE = (f"{MARK} Leveraged-ETF tags hidden — the Massive reference list was last read {{as_of_mmdd}} "
              f"({{age}} days ago; tags hide past {STALE_DAYS} days).")
LINE_MISSING = (f"{MARK} Leveraged-ETF tags: the Massive reference list has not been read yet — the first read "
                "starts with this build.")
LINE_ERROR = f"{MARK} Leveraged-ETF tags could not be read ({{reason}}) — none shown."
LEGEND = ("Leveraged ETFs that track this stock (Massive reference list as of {as_of_mmdd}): long first, then "
          "leverage, then the most traded on {grouped_mmdd}. Daily-reset funds — over more than one session they "
          "do not deliver the stated multiple of the stock's move. Display only — not advice.")
NO_DB_REASON = "no database"

# ---------------------------------------------------------------------------
# module state (the load memo + the in-process refresh flag)
# ---------------------------------------------------------------------------
_memo: dict = {}
_memo_lock = threading.Lock()
_flag_lock = threading.Lock()
_refreshing = {"on": False}


def _reset_for_tests() -> None:
    with _memo_lock:
        _memo.clear()
    with _flag_lock:
        _refreshing["on"] = False


# ---------------------------------------------------------------------------
# the rules (PURE) — ported rule for rule from the planner's reference trial
# ---------------------------------------------------------------------------
def clean(s) -> str:
    """Lowercase, every non-word character a space, whitespace collapsed."""
    return " ".join(re.sub(r"[^\w\s]", " ", str(s or "").lower()).split())


def core_name(name) -> str:
    """`clean(name)`, then ONE trailing `CORP_TAIL` token stripped at a time
    while one matches: "Tesla, Inc. Common Stock" -> "tesla"."""
    s = clean(name)
    changed = True
    while changed and s:
        changed = False
        for t in CORP_TAIL:
            if s == t:
                s, changed = "", True
                break
            if s.endswith(" " + t):
                s, changed = s[: -len(t) - 1].strip(), True
                break
    return s


def parse_name(etf: str, name, stock_tickers, by_core) -> tuple:
    """(status, row | None). The first rule that fires decides; status is
    "no_factor" (not a leveraged fund — never counted as a skip), "by_ticker"
    / "by_name" (a row), or a `SKIP_REASONS` reason."""
    name = str(name or "")
    facs = FACTOR_RE.findall(name)
    if not facs:
        return "no_factor", None
    mags = {abs(float(x)) for x in facs}
    if len(mags) != 1:
        return "multi_factor", None
    factor = mags.pop()
    words = [w.strip(TOKEN_STRIP) for w in name.split()]
    words = [w for w in words if w]
    lw = [w.lower() for w in words]
    neg = any(x.startswith("-") for x in facs)
    dirs = set()
    if any(w in LONG_WORDS for w in lw):
        dirs.add("long")
    if any(w in SHORT_WORDS for w in lw) or neg:
        dirs.add("short")
    issuer_at = None                  # HIS CALL #1: the slot right after a no-direction issuer's name
    if not dirs:
        for iss in NO_DIRECTION_LONG_ISSUERS:
            iw = str(iss or "").lower().split()
            if iw and lw[:len(iw)] == iw:
                issuer_at = len(iw)
                dirs.add("long")
                break
        if not dirs:
            return "no_direction", None
    if len(dirs) > 1:
        return "both_directions", None
    direction = dirs.pop()
    if factor <= MIN_FACTOR_EXCLUSIVE:
        return "one_x", None
    all_caps = not any(c.islower() for c in name)
    cands = set()
    if not all_caps:
        for i, w in enumerate(words):
            wl = w.lower()
            nxt = words[i + 1] if i + 1 < len(words) else None
            prv = words[i - 1] if i > 0 else None
            for tok, ok in ((nxt, wl in SLOT_AFTER), (prv, wl in SLOT_BEFORE),
                            (w, issuer_at is not None and i == issuer_at)):
                if (ok and tok and TICKER_TOKEN_RE.match(tok) and tok != etf and tok not in NEVER_TICKER_WORDS
                        and tok not in COIN_SYMBOLS and tok in stock_tickers):
                    cands.add(tok)
    if len(cands) > 1:
        return "ambiguous_ticker", None
    if len(cands) == 1:
        return "by_ticker", {"etf": etf, "underlying": cands.pop(), "factor": factor,
                             "direction": direction, "rule": "ticker"}
    phrase = None
    starts = [i + 1 for i, w in enumerate(lw) if w in SLOT_AFTER] + ([issuer_at] if issuer_at is not None else [])
    for start in starts:
        ph, j = [], start
        while j < len(words) and lw[j] not in GRAMMAR_WORDS and not FACTOR_RE.fullmatch(words[j]):
            ph.append(words[j])
            j += 1
        if ph:
            phrase = " ".join(ph)
            break
    if phrase is None:
        for i, w in enumerate(lw):
            if w in SLOT_BEFORE:
                ph, j = [], i - 1
                while j >= 0 and lw[j] not in GRAMMAR_WORDS and lw[j] not in BEFORE_STOP:
                    ph.insert(0, words[j])
                    j -= 1
                if ph:
                    phrase = " ".join(ph)
                    break
    if phrase is None:
        return "no_slot", None
    if clean(phrase).upper() in NEVER_TICKER_WORDS or clean(phrase).upper() in COIN_SYMBOLS:
        return "no_us_underlying", None
    hits = {t for t in (by_core.get(clean(phrase)) or ()) if t != etf}
    if len(hits) > 1:
        return "ambiguous_name", None
    if len(hits) == 1:
        return "by_name", {"etf": etf, "underlying": next(iter(hits)), "factor": factor,
                           "direction": direction, "rule": "name"}
    return "no_us_underlying", None


def _for_yahoo(sym: str) -> str:
    from sepa import symbols
    return symbols.for_yahoo(sym)


def stocks_from(rows) -> dict:
    """{RAW_TICKER: name} over `STOCK_TYPES` (a row without a type is taken as
    the caller's stock list)."""
    out = {}
    for r in rows or []:
        if not isinstance(r, dict):
            continue
        t = str(r.get("ticker") or "").strip()
        if t and (r.get("type") is None or r.get("type") in STOCK_TYPES):
            out[t] = str(r.get("name") or "")
    return out


def build_rows(funds, stocks: dict, grouped: dict) -> tuple:
    """(rows, counts). `funds` = [{ticker, name, type}] (only `FUND_TYPES`
    are read), `stocks` = {RAW_TICKER: name} over `STOCK_TYPES`, `grouped` =
    {TICKER: [v, vw, c]} of the last closed session. A parsed fund with no
    grouped row or `v` <= 0 is `no_print` (never served)."""
    stocks = dict(stocks or {})
    grouped = grouped if isinstance(grouped, dict) else {}
    by_core: dict = collections.defaultdict(set)
    for t, n in stocks.items():
        c = core_name(n)
        if c:
            by_core[c].add(t)
    counts = {k: 0 for k in COUNT_KEYS}
    rows = []
    fund_types = tuple(FUND_TYPES)
    for f in funds or []:
        if not isinstance(f, dict) or f.get("type") not in fund_types:
            continue
        tk = str(f.get("ticker") or "").strip()
        if not tk:
            continue
        counts["funds_read"] += 1
        st, row = parse_name(tk, f.get("name"), stocks, by_core)
        if st == "no_factor":
            continue
        counts["with_factor"] += 1
        if row is None:
            counts[st] += 1
            continue
        g = grouped.get(tk)
        v = None
        try:
            v = float(g[0]) if g else None
        except (TypeError, ValueError, IndexError):
            v = None
        if not v or v <= 0:
            counts["no_print"] += 1
            continue
        counts[st] += 1
        try:
            px = float(g[1] or (g[2] if len(g) > 2 else 0) or 0)
        except (TypeError, ValueError, IndexError):
            px = 0.0
        row.update(etf=_for_yahoo(tk), underlying=_for_yahoo(row["underlying"]), name=f.get("name"),
                   type=f.get("type"), dollar_vol=round(v * px))
        rows.append(row)
    counts["tagged"] = len(rows)
    counts["underlyings"] = len({x["underlying"] for x in rows})
    return rows, counts


def order(items) -> list:
    """Long first, then factor desc, then last-session $ volume desc, then ticker."""
    return sorted([x for x in (items or []) if isinstance(x, dict)],
                  key=lambda x: (x.get("direction") != "long", -float(x.get("factor") or 0),
                                 -float(x.get("dollar_vol") or 0), str(x.get("etf") or "")))


def by_underlying(rows) -> dict:
    out: dict = collections.defaultdict(list)
    for r in rows or []:
        if isinstance(r, dict) and r.get("underlying") and r.get("etf"):
            out[str(r["underlying"]).upper()].append(r)
    return {k: order(v) for k, v in out.items()}


# ---------------------------------------------------------------------------
# served words (PURE)
# ---------------------------------------------------------------------------
def factor_text(f, direction="long") -> str:
    """'2×', '1.25×', '−2×' (U+2212 when short)."""
    txt = f"{float(f):g}×"
    return (_MINUS + txt) if direction == "short" else txt


def _kept(items) -> list:
    out = [x for x in (items or []) if isinstance(x, dict) and x.get("etf")]
    return out if INCLUDE_SHORTS else [x for x in out if x.get("direction") == "long"]


def chip(items) -> Optional[dict]:
    """The short tag: at most `SHOW_MAX` tickers, then "+n" (its title = the
    rest). None when there is no item. Every etf part carries the fund name
    as its title when known."""
    items = _kept(items)
    if not items:
        return None
    shown, rest = items[:SHOW_MAX], items[SHOW_MAX:]
    parts: list = [{"text": f"{MARK} "}]
    prev = None
    for it in shown:
        g = (it.get("direction"), float(it.get("factor") or 0))
        lbl = factor_text(it.get("factor") or 0, it.get("direction"))
        if prev is None:
            parts.append({"text": f"{lbl} "})
        elif g != prev:
            parts.append({"text": f" · {lbl} "})
        else:
            parts.append({"text": " · "})
        part = {"etf": str(it["etf"])}
        if it.get("name"):
            part["title"] = str(it["name"])
        parts.append(part)
        prev = g
    rest_txt = (" · ".join(f"{x['etf']} {factor_text(x.get('factor') or 0, x.get('direction'))}" for x in rest)
                if rest else None)
    if rest:
        parts.append({"text": f" +{len(rest)}", "title": rest_txt})
    text = "".join(p["text"] if "text" in p else p["etf"] for p in parts)
    return {"text": text, "parts": parts, "shown": [str(x["etf"]) for x in shown], "more": len(rest),
            "rest": rest_txt}


def stat_value(items) -> Optional[str]:
    items = _kept(items)
    if not items:
        return None
    return " · ".join(f"{x['etf']} {factor_text(x.get('factor') or 0, x.get('direction'))}" for x in items)


LINE_SPLIT = ("no_direction", "one_x")                 # printed alone; every other SKIP_REASONS count -> {no_us}


def untagged_other(counts) -> int:
    """Every `SKIP_REASONS` count not printed alone in `LINE_READY` (no_us_underlying,
    no_slot, ambiguous_*, multi_factor, both_directions, no_print), so the line's
    three untagged parts sum to with_factor - tagged."""
    c = counts if isinstance(counts, dict) else {}
    return sum(int(c.get(k) or 0) for k in SKIP_REASONS if k not in LINE_SPLIT)


def _mmdd(iso) -> str:
    from supply_demand import key_levels as KL
    return KL._day_mmdd(iso)


def status_block(state: dict, *, n_on: int, listed: int) -> dict:
    """The board's `levered` block: {state, as_of, age_days, grouped_day,
    n_etfs, n_underlyings, n_on, line, legend}. Never raises."""
    s = state if isinstance(state, dict) else {}
    st = s.get("state") if s.get("state") in STATES else "error"
    c = s.get("counts") if isinstance(s.get("counts"), dict) else {}
    out = {"state": st, "as_of": s.get("as_of"), "age_days": s.get("age_days"),
           "grouped_day": s.get("grouped_day"), "n_etfs": None, "n_underlyings": None,
           "n_on": int(n_on or 0) if st == "ready" else 0, "line": None, "legend": None}
    try:
        if st == "ready":
            out.update(n_etfs=int(c.get("tagged") or 0), n_underlyings=int(c.get("underlyings") or 0))
            out["line"] = LINE_READY.format(
                n_on=int(n_on or 0), listed=int(listed or 0), n_etfs=out["n_etfs"], n_under=out["n_underlyings"],
                as_of_mmdd=_mmdd(s.get("as_of")), grouped_mmdd=_mmdd(s.get("grouped_day")),
                no_direction=int(c.get("no_direction") or 0), one_x=int(c.get("one_x") or 0),
                no_us=untagged_other(c))
            out["legend"] = LEGEND.format(as_of_mmdd=_mmdd(s.get("as_of")),
                                          grouped_mmdd=_mmdd(s.get("grouped_day")))
        elif st == "stale":
            out["line"] = LINE_STALE.format(as_of_mmdd=_mmdd(s.get("as_of")), age=int(s.get("age_days") or 0))
        elif st == "missing" and s.get("reason") != NO_DB_REASON:
            out["line"] = LINE_MISSING
        else:
            out["line"] = LINE_ERROR.format(reason=str(s.get("reason") or "unknown"))
    except Exception as exc:                                    # noqa: BLE001
        out.update(state="error", n_on=0, legend=None,
                   line=LINE_ERROR.format(reason=type(exc).__name__))
    return out


# ---------------------------------------------------------------------------
# I/O — never raises; the key never reaches a log, an exception text or the doc
# ---------------------------------------------------------------------------
def _scrub(exc, key=None) -> str:
    try:
        from sepa import prices
        msg = prices._scrub_key(exc)
    except Exception:                                           # noqa: BLE001
        msg = re.sub(r"(apiKey=)[A-Za-z0-9_-]+", r"\1<redacted>", str(exc))
    if key:
        msg = msg.replace(str(key), "<redacted>")
    return msg


def _key(key):
    if key is not None:
        return key
    try:
        from massive_keys import stocks_key
        return stocks_key()
    except Exception:                                           # noqa: BLE001
        return ""


def _http_for(http):
    if http is not None:
        return http
    from sepa import prices
    return prices._http()


def fetch_reference(type_: str, *, http=None, key=None, max_pages: int = MAX_PAGES_PER_TYPE) -> tuple:
    """(rows [{ticker, name, type}], complete, calls) — `fetch_type_map`'s
    transport: `next_url` cursor, the key re-sent alone, at most `max_pages`
    calls; any non-200, exception or the page cap -> complete False."""
    key = _key(key)
    if not key:
        return [], False, 0
    http = _http_for(http)
    rows: list = []
    url: Optional[str] = REF_URL
    params: dict = {"type": type_, "market": "stocks", "active": "true", "limit": PAGE_LIMIT, "apiKey": key}
    calls = 0
    while url and calls < max_pages:
        calls += 1
        try:
            r = http.get(url, params=params, timeout=HTTP_TIMEOUT_SEC)
        except Exception as exc:                                # noqa: BLE001
            log.warning("levered_etf reference %s: %s", type_, _scrub(exc, key))
            return rows, False, calls
        if getattr(r, "status_code", None) != 200:
            log.warning("levered_etf reference %s: HTTP %s", type_, getattr(r, "status_code", None))
            return rows, False, calls
        try:
            body = r.json() or {}
        except Exception as exc:                                # noqa: BLE001
            log.warning("levered_etf reference %s: bad body %s", type_, type(exc).__name__)
            return rows, False, calls
        for it in body.get("results") or []:
            it = it if isinstance(it, dict) else {}
            tk = str(it.get("ticker") or "").strip().upper()
            if tk and it.get("active", True) is not False:
                rows.append({"ticker": tk, "name": str(it.get("name") or ""), "type": str(it.get("type") or type_)})
        url = body.get("next_url")
        params = {"apiKey": key}                                # next_url carries its own cursor
    return rows, url is None, calls


def fetch_grouped(day, *, http=None, key=None) -> tuple:
    """({TICKER: [v, vw, c]}, ok) — ONE grouped-daily read of `day`. An empty
    result, a non-200 or an exception -> ok False."""
    key = _key(key)
    if not key:
        return {}, False
    http = _http_for(http)
    iso = day.isoformat() if isinstance(day, date) else str(day)
    try:
        r = http.get(GROUPED_URL_FMT.format(day=iso), params={"adjusted": "true", "apiKey": key},
                     timeout=HTTP_TIMEOUT_SEC)
    except Exception as exc:                                    # noqa: BLE001
        log.warning("levered_etf grouped %s: %s", iso, _scrub(exc, key))
        return {}, False
    if getattr(r, "status_code", None) != 200:
        log.warning("levered_etf grouped %s: HTTP %s", iso, getattr(r, "status_code", None))
        return {}, False
    try:
        body = r.json() or {}
    except Exception as exc:                                    # noqa: BLE001
        log.warning("levered_etf grouped %s: bad body %s", iso, type(exc).__name__)
        return {}, False
    out = {}
    for it in body.get("results") or []:
        it = it if isinstance(it, dict) else {}
        tk = str(it.get("T") or "").strip().upper()
        if tk:
            out[tk] = [it.get("v"), it.get("vw"), it.get("c")]
    return out, bool(out)


def _db(db=None):
    """The `chart_maps/membership.py` pattern: `portfolio.store._get_db`
    (None when Mongo is unreachable — and under the hermetic test stub)."""
    if db is not None:
        return db
    try:
        from portfolio.store import _get_db
        return _get_db()
    except Exception as exc:                                    # noqa: BLE001
        log.debug("levered_etf: no mongo: %s", exc)
        return None


def _et_today(now: Optional[datetime]) -> date:
    from supply_demand import key_levels as KL
    n = now or datetime.now(timezone.utc)
    if n.tzinfo is None:
        n = n.replace(tzinfo=timezone.utc)
    return n.astimezone(KL.ET).date()


def refresh(*, now: Optional[datetime] = None, db=None, http=None, key=None, dry_run: bool = False) -> dict:
    """One reference read. Only a COMPLETE read (every type complete, the
    grouped read ok, at least one tag) replaces the doc; a partial read keeps
    the old rows / `as_of` and stamps `last_error_at` + `last_partial`.
    `dry_run` writes nothing and returns the would-be doc under "doc". Never
    raises; always clears the `load` memo."""
    from supply_demand import key_levels as KL
    t0 = time.monotonic()
    today = _et_today(now)
    today_iso = today.isoformat()
    grouped_day = KL.prev_market_day(today)
    key = _key(key)
    out = {"ok": False, "complete": False, "counts": {k: 0 for k in COUNT_KEYS}, "secs": 0.0, "calls": 0,
           "as_of": None}
    try:
        if not key:
            out["reason"] = "no Massive key"
            return out
        http = _http_for(http)
        calls = 0
        incomplete: list = []
        funds: list = []
        stocks: dict = {}
        for t in tuple(FUND_TYPES) + tuple(STOCK_TYPES):
            if time.monotonic() - t0 > REFRESH_BUDGET_SEC:
                incomplete.append(t)
                continue
            rows, complete, c = fetch_reference(t, http=http, key=key)
            calls += c
            if not complete:
                incomplete.append(t)
            if t in STOCK_TYPES:
                stocks.update({r["ticker"]: r["name"] for r in rows})
            else:
                funds.extend({**r, "type": t} for r in rows)
        grouped, gok = {}, False
        if time.monotonic() - t0 <= REFRESH_BUDGET_SEC:
            grouped, gok = fetch_grouped(grouped_day, http=http, key=key)
            calls += 1
        rows, counts = build_rows(funds, stocks, grouped)
        secs = round(time.monotonic() - t0, 1)
        over = secs > REFRESH_BUDGET_SEC
        complete = (not incomplete) and gok and counts["tagged"] > 0 and not over
        now_ts = time.time()
        fetched_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        out.update(counts=counts, secs=secs, calls=calls, complete=complete)
        doc = {"_id": DOC_ID, "as_of": today_iso, "grouped_day": grouped_day.isoformat(), "fetched_at": fetched_at,
               "complete": True, "secs": secs, "calls": calls, "counts": counts, "rows": rows,
               "attempted_on": today_iso, "attempted_at": now_ts}
        partial = {"types_incomplete": incomplete, "grouped_ok": gok, "calls": calls, "over_budget": over,
                   "tagged": counts["tagged"]}
        if dry_run:
            out.update(ok=complete, as_of=today_iso if complete else None,
                       doc=doc if complete else {"last_partial": partial})
            return out
        d = _db(db)
        if d is None:
            out["reason"] = NO_DB_REASON
            return out
        coll = d[COLL]
        if complete:
            coll.replace_one({"_id": DOC_ID}, doc, upsert=True)
            out.update(ok=True, as_of=today_iso)
        else:
            coll.update_one({"_id": DOC_ID}, {"$set": {"last_error_at": fetched_at, "last_partial": partial}},
                            upsert=True)
            prev = coll.find_one({"_id": DOC_ID}) or {}
            out.update(as_of=prev.get("as_of"), reason="incomplete read")
            log.warning("levered_etf: INCOMPLETE read (%s types cut, grouped ok %s, %d tagged, %d calls) — kept "
                        "the %s map", ",".join(incomplete) or "no", gok, counts["tagged"], calls,
                        prev.get("as_of") or "empty")
        return out
    except Exception as exc:                                    # noqa: BLE001
        log.warning("levered_etf refresh failed: %s", _scrub(exc, key))
        out["reason"] = type(exc).__name__
        return out
    finally:
        out["secs"] = out.get("secs") or round(time.monotonic() - t0, 1)
        with _memo_lock:
            _memo.clear()


def claim(db, *, today_iso: str, now_ts: float) -> bool:
    """Atomic, multi-process safe: True for exactly one caller per ET day
    (and at most once per `RETRY_SEC` after a failed attempt)."""
    try:
        coll = db[COLL]
        res = coll.update_one(
            {"_id": DOC_ID, "as_of": {"$ne": today_iso},
             "$or": [{"attempted_at": {"$exists": False}}, {"attempted_at": {"$lt": now_ts - RETRY_SEC}}]},
            {"$set": {"attempted_at": now_ts, "attempted_on": today_iso}})
        if int(getattr(res, "modified_count", 0) or 0) == 1:
            return True
        if coll.find_one({"_id": DOC_ID}) is not None:
            return False
        coll.insert_one({"_id": DOC_ID, "attempted_at": now_ts, "attempted_on": today_iso,
                         "complete": False, "rows": []})
        return True
    except Exception as exc:                                    # noqa: BLE001  (DuplicateKeyError = lost the race)
        log.debug("levered_etf claim: %s", type(exc).__name__)
        return False


def _spawn(target, name: str) -> None:
    threading.Thread(target=target, name=name, daemon=True).start()


_UNSET = object()


def ensure_async(*, now: Optional[datetime] = None, db=None, spawn=None, as_of=_UNSET) -> bool:
    """Start ONE background refresh when the map is not today's. Nothing when
    there is no database (the hermetic tests' case) or `as_of` is today. Never
    raises; never blocks."""
    try:
        d = _db(db)
        if d is None:
            return False
        today_iso = _et_today(now).isoformat()
        if as_of is _UNSET:
            doc = d[COLL].find_one({"_id": DOC_ID}, {"as_of": 1}) or {}
            as_of = doc.get("as_of")
        if as_of == today_iso:
            return False
        with _flag_lock:
            if _refreshing["on"]:
                return False
            if not claim(d, today_iso=today_iso, now_ts=time.time()):
                return False
            _refreshing["on"] = True

        def _work():
            try:
                refresh(now=now, db=d)
            finally:
                with _flag_lock:
                    _refreshing["on"] = False

        (spawn or _spawn)(_work, f"levered-etf-refresh-{today_iso}")
        return True
    except Exception as exc:                                    # noqa: BLE001
        log.debug("levered_etf ensure_async: %s", type(exc).__name__)
        with _flag_lock:
            _refreshing["on"] = False
        return False


def _state(state: str, *, reason=None, doc=None, age=None, rows=None) -> dict:
    doc = doc or {}
    counts = doc.get("counts") if isinstance(doc.get("counts"), dict) else {}
    return {"state": state, "as_of": doc.get("as_of"), "age_days": age, "grouped_day": doc.get("grouped_day"),
            "counts": {k: int(counts.get(k) or 0) for k in COUNT_KEYS},
            "by_underlying": by_underlying(rows) if rows else {}, "reason": reason}


def load(*, now: Optional[datetime] = None, db=None, ensure: bool = True) -> dict:
    """{state ready|stale|missing|error, as_of, age_days, grouped_day, counts,
    by_underlying {SYM: ordered items}, reason}. Reads ONE Mongo doc (memoised
    `MAP_MEMO_SEC` on the default database), starts the day's background
    refresh when the doc is not today's. Never raises, never fetches."""
    try:
        today = _et_today(now)
    except Exception as exc:                                    # noqa: BLE001
        return _state("error", reason=type(exc).__name__)
    today_iso = today.isoformat()
    memo_ok = db is None
    if memo_ok:
        with _memo_lock:
            m = _memo.get("v")
            if m and m["day"] == today_iso and (time.time() - m["ts"]) < MAP_MEMO_SEC:
                return m["val"]
    d = _db(db)
    if d is None:
        return _state("missing", reason=NO_DB_REASON)
    doc, read_ok = None, False
    try:
        doc = d[COLL].find_one({"_id": DOC_ID})
        doc = doc if isinstance(doc, dict) else None
        read_ok = True
        if not doc or not doc.get("as_of") or not doc.get("rows"):
            val = _state("missing", reason="not read yet", doc=doc)
        else:
            age = (today - date.fromisoformat(str(doc["as_of"])[:10])).days
            if age > STALE_DAYS:
                val = _state("stale", reason=f"{age} days old", doc=doc, age=age)
            else:
                val = _state("ready", doc=doc, age=age, rows=doc.get("rows"))
    except Exception as exc:                                    # noqa: BLE001
        val = _state("error", reason=_scrub(exc) or type(exc).__name__)
    if ensure and (doc is None or doc.get("as_of") != today_iso):
        ensure_async(now=now, db=d, as_of=(doc or {}).get("as_of") if read_ok else _UNSET)
    # memoise only a map that exists: a "missing" / "error" read pinned for MAP_MEMO_SEC
    # (per uvicorn worker) hid the first map of the day for 10 minutes on 2026-10-14
    if memo_ok and val.get("state") in ("ready", "stale"):
        with _memo_lock:
            _memo["v"] = {"day": today_iso, "ts": time.time(), "val": val}
    return val


def items_for(state: dict, symbol) -> list:
    """The full ordered items (etf, factor, direction, name, dollar_vol…) for
    one stock — [] unless the map is `ready`; shorts dropped when not
    `INCLUDE_SHORTS`."""
    s = state if isinstance(state, dict) else {}
    if s.get("state") != "ready":
        return []
    items = (s.get("by_underlying") or {}).get(str(symbol or "").upper()) or []
    return [dict(x) for x in _kept(items)]


def for_symbol(state: dict, symbol) -> list:
    """[{etf, factor, direction}] in the served order (see `items_for`)."""
    return [{"etf": x["etf"], "factor": float(x.get("factor") or 0), "direction": x.get("direction")}
            for x in items_for(state, symbol)]


# ---------------------------------------------------------------------------
# CLI — `python -m sepa.levered_etf refresh [--dry-run] [--json PATH]`
# ---------------------------------------------------------------------------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m sepa.levered_etf")
    ap.add_argument("cmd", choices=("refresh",))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args(argv)
    res = refresh(dry_run=a.dry_run)
    doc = res.pop("doc", None)
    print(json.dumps({k: v for k, v in res.items()}, default=str))
    rows = (doc or {}).get("rows") or []
    by = by_underlying(rows)
    for u in ("IREN", "VST", "NBIS"):
        c = chip(by.get(u) or [])
        print(u, (c or {}).get("text") or "(none)")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"result": res, "doc": doc}, fh, default=str, indent=1)
    return 0 if res.get("complete") else 1


if __name__ == "__main__":                                      # pragma: no cover
    sys.exit(main())
