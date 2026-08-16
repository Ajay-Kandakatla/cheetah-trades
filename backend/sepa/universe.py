"""Scanning universe — tickers we run SEPA against.

Three modes, selected via the `SEPA_UNIVERSE_MODE` env var or argument:

  - "curated"  (default) — the hand-picked ~130-name list below. Fast scans,
                           biased toward growth-friendly sectors.
  - "sp500"    — full S&P 500 (~503 names) fetched from Wikipedia (with an
                 explicit User-Agent — see fetch_sp500) or the datahub CSV
                 mirror, cached 30 days under ~/.cheetah/universe/sp500.txt.
  - "russell1000" — Russell 1000 holdings (~1000 names) fetched from iShares
                    IWB ETF holdings CSV. Cached 30 days.
  - "russell3000" — Russell 3000 holdings (~3000 names) fetched from iShares
                    IWV ETF holdings CSV. Cached 30 days. Opt-in only —
                    set SEPA_UNIVERSE_MODE=russell3000.
  - "expanded" — curated ∪ sp500 union (deduped).

You can also point SEPA_UNIVERSE_FILE at any text file (one ticker per line)
or set SEPA_UNIVERSE to a comma-separated override.
"""
from __future__ import annotations

import functools
import logging
import os
from massive_keys import stocks_key
import time
from pathlib import Path

log = logging.getLogger("sepa.universe")
UNIV_CACHE_DIR = Path.home() / ".cheetah" / "universe"
UNIV_CACHE_DIR.mkdir(parents=True, exist_ok=True)
UNIV_CACHE_TTL_SEC = 30 * 24 * 3600  # 30 days

# Liquid growth + momentum names. Edit freely.
UNIVERSE: list[str] = [
    # Mega-cap tech
    "NVDA", "MSFT", "AAPL", "META", "GOOGL", "AMZN", "TSLA", "AVGO", "ORCL", "NFLX",
    # Semis / AI infra
    "AMD", "ASML", "TSM", "MU", "ARM", "MRVL", "LRCX", "AMAT", "KLAC", "SMCI",
    "CRDO", "ALAB", "ANET", "CRWV", "NBIS",
    # Software / cloud
    "CRM", "NOW", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "MDB", "PLTR",
    "SHOP", "TEAM", "WDAY", "HUBS", "CFLT", "SMAR", "TOST",
    # Consumer growth
    "ABNB", "UBER", "DASH", "BKNG", "CMG", "LULU", "DECK", "COST", "WMT",
    # Health / biotech leaders
    "LLY", "UNH", "ISRG", "VRTX", "REGN", "BMRN", "RMD", "BSX",
    # Fintech / payments
    "V", "MA", "PYPL", "AXP", "COIN", "HOOD", "SQ", "SOFI", "NU", "MELI",
    # Energy / industrials / materials
    "CEG", "VST", "GEV", "ETN", "PH", "CAT", "DE", "FSLR", "ENPH",
    # China ADR growth
    "BABA", "PDD", "JD", "NIO", "LI", "XPEV",
    # Canada (US-listed) — Canadian companies are excluded from the US Russell
    # indices, so they only reach the scan via this curated list.
    "BB", "AEM", "BMO", "BN", "BNS", "BTE", "CCJ", "CM", "CNI", "CNQ",
    "CP", "CVE", "DOOO", "ENB", "FNV", "GIB", "IMO", "KGC", "LSPD", "MFC",
    "NTR", "OGI", "OTEX", "RY", "SLF", "SU", "TD", "TECK", "TLRY", "TRI",
    "TRP", "WCN", "WPM",
    # Foreign tech / semis (US-listed ADRs) — ASML / TSM / ARM are above.
    "SAP", "SE", "STM", "UMC", "ASX", "HIMX", "SONY", "INFY", "WIT",
    "BIDU", "NTES", "TCOM", "GRAB",
    # Small/mid momentum movers (edit freely)
    "RKLB", "ACHR", "JOBY", "SERV", "OKLO", "LUNR", "ASTS", "AEHR", "IONQ",
    "RGTI", "QBTS", "BBAI", "SOUN", "TEM", "HIMS", "DUOL", "RBLX", "DKNG",
    "SPOT", "RDDT", "APP", "APPN", "PATH", "BILL", "DOCN",
    # Anchor / benchmarks (not traded but used for RS math)
    "SPY", "QQQ", "IWM",
]


# ---------------------------------------------------------------------------
# Theme rosters — the 2025-26 build-out names the S&P indices cannot hold.
#
# Ajay 2026-08-15: "make sure the new companies like Quantum based and Power
# based and robotics based and then Semis all are considered."
#
# WHY THIS EXISTS AS A SEPARATE LIST. S&P's index committee requires positive
# GAAP earnings and US domicile, so no quantum name is in any S&P tier, OKLO /
# SMR / NNE are pre-revenue, and ARM is a UK-domiciled ADR — structurally
# excluded from every S&P *and* Russell list. Measured 2026-08-15: sp1500
# resolves to 1,506 names and misses 12 of the 22 theme tickers Ajay named.
# That is not a bug in the fetchers to be fixed; it is what an index IS. So
# the names arrive by hand, tagged with the theme that earned them a slot.
#
# These are riskier than the index layers by construction — pre-profit, thin,
# high-beta. Nothing here bypasses a gate: they enter the same trend, knife and
# liquidity filters as every other name. This list only decides who gets LOOKED
# at, never who passes.
# ---------------------------------------------------------------------------
# Ajay 2026-08-16: "I do want us to give priority to Space technology, Quantum,
# Semis" and "Fiber optics, and Robotic components or any potential bottlenecks
# for AI that are going to be the next big thing.. after Semis and HBM."
#
# Every ticker below was probed against our own price feed before it was added
# (260 daily bars + 50-day dollar volume). Nothing here is from memory or a
# list off the internet. Names that resolved but are too thin to chart or trade
# were dropped on purpose, and the floor is noted per roster.
THEME_UNIVERSE: dict[str, list[str]] = {
    # Space technology — launch, satellites, imagery, satcom. Deliberately NOT
    # the defence primes (LMT/NOC/RTX/BA): they are conglomerates where space is
    # a segment, so tagging them "space" would put a defence budget story at the
    # top of the board. Dropped: SPCE ($3.32), MNTS ($4.84) — broken businesses;
    # SPIR ($17M/day) — too thin to chart honestly; ATRO/TDG/HEI — aerostructures
    # and aftermarket parts, not space technology.
    "space":     ["RKLB", "ASTS", "LUNR", "RDW", "PL", "BKSY",
                  "IRDM", "GSAT", "SATS", "VSAT"],
    "quantum":   ["IONQ", "RGTI", "QBTS", "QUBT", "ARQQ"],
    # Semis incl. the HBM/storage layer Ajay named. MU is the HBM name; SNDK,
    # WDC and STX are the AI-storage bottleneck; ONTO/NVMI/CAMT are the
    # metrology tools that gate HBM stacking yield.
    "ai_semis":  ["ARM", "ALAB", "CRDO", "NVDA", "AVGO", "AMD", "MU", "MRVL",
                  "TSM", "LRCX", "AMAT", "KLAC",
                  "SNDK", "WDC", "STX", "ONTO", "NVMI", "CAMT"],
    # Fibre optics / optical interconnect — the bottleneck once compute is no
    # longer the constraint. Transceivers and lasers (COHR/LITE/AAOI/FN/POET),
    # optical networking (CIEN/MTSI), the fibre and glass itself (GLW), and the
    # connectors that carry it (APH/TEL). Contract manufacturers went to
    # ai_infra instead — they assemble the racks, they do not make the optics.
    "optical":   ["COHR", "LITE", "AAOI", "CIEN", "FN", "GLW", "MTSI", "POET",
                  "APH", "TEL"],
    # Robotic components / physical AI. Beyond the platform names: machine
    # vision (CGNX), perception (MBLY, OUST), motion and precision dispensing
    # (EMR, AME, NDSN, HON), and TSLA for humanoid/physical AI. Dropped as too
    # thin to chart: LAZR $18M, ATS $5M, KRNT $4M, INVZ $2M ($0.37 a share).
    "robotics":  ["SERV", "RR", "SYM", "TER", "ROK", "PATH", "ISRG",
                  "CGNX", "MBLY", "OUST", "EMR", "AME", "NDSN", "HON", "TSLA"],
    # Power, cooling and the racks themselves.
    "ai_infra":  ["VRT", "MOD", "APLD", "CRWV", "NBIS", "SMCI", "ANET", "ETN",
                  "PWR", "GEV", "NVT", "HUBB", "POWL", "AAON", "CLS", "FLEX"],
    "nuclear":   ["OKLO", "SMR", "NNE", "LEU", "BWXT", "TLN", "VST", "CEG"],
}

# Ordering BETWEEN themes, most-wanted first — Ajay's stated priority, then the
# bottlenecks he expects to matter next. Before this, every theme scored the
# same and the board could only answer "theme or not", never "which theme".
# A theme missing from this map sorts last but still ahead of untagged names.
THEME_PRIORITY: dict[str, int] = {
    "space":     0,
    "quantum":   1,
    "ai_semis":  2,
    "optical":   3,
    "robotics":  4,
    "ai_infra":  5,
    "nuclear":   6,
}

# Rank used for a tagged theme that is not in THEME_PRIORITY — still ahead of
# every untagged name, which is what UNTAGGED_RANK guarantees.
UNKNOWN_THEME_RANK = 50
UNTAGGED_RANK = 99

# Reverse map, built once — a linear scan over the rosters per ticker is fine
# for a card and wasteful for a 1,500-row board.
#
# A ticker must live in exactly ONE roster: this dict is last-wins, so a
# duplicate would silently retag the name and change its priority. NVDA is the
# obvious temptation (it is the physical-AI platform as much as it is a semi) —
# it stays in ai_semis. `_assert_themes_disjoint()` below makes the rule fail
# loudly at import instead of quietly at sort time.
THEME_BY_TICKER: dict[str, str] = {
    t: theme for theme, names in THEME_UNIVERSE.items() for t in names
}


def _assert_themes_disjoint() -> None:
    seen: dict[str, str] = {}
    dupes: list[str] = []
    for theme, names in THEME_UNIVERSE.items():
        for t in names:
            if t in seen:
                dupes.append(f"{t} in both {seen[t]} and {theme}")
            seen[t] = theme
    if dupes:
        raise ValueError("THEME_UNIVERSE tickers must be unique: " + "; ".join(dupes))


_assert_themes_disjoint()


def theme_for(symbol: str) -> str | None:
    """Which build-out theme a ticker belongs to, or None. PURE."""
    if not isinstance(symbol, str):
        return None
    return THEME_BY_TICKER.get(symbol.strip().upper())


def theme_rank(theme: str | None) -> int:
    """Sort rank for a theme — lower leads. Untagged names sort last. PURE."""
    if not theme:
        return UNTAGGED_RANK
    return THEME_PRIORITY.get(theme, UNKNOWN_THEME_RANK)


def fetch_themes() -> list[str]:
    """Every theme name, deduped, order-stable. No network — hand-curated."""
    out: list[str] = []
    seen: set[str] = set()
    for names in THEME_UNIVERSE.values():
        for t in names:
            if t not in seen:
                seen.add(t)
                out.append(t)
    return out


# ---------------------------------------------------------------------------
# Remote-list fetchers (cached to disk for 30 days)
# ---------------------------------------------------------------------------
def _cache_path(name: str) -> Path:
    return UNIV_CACHE_DIR / f"{name}.txt"


def _read_cached(name: str) -> list[str] | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    if (time.time() - path.stat().st_mtime) >= UNIV_CACHE_TTL_SEC:
        return None
    return [ln.strip().upper() for ln in path.read_text().splitlines() if ln.strip()]


def _read_cached_stale(name: str) -> list[str] | None:
    """Read a cached list IGNORING the TTL. Only for use as a last-resort
    fallback when the live fetch fails — an out-of-date real index beats a
    fresh list of the wrong universe. Returns None if no file exists."""
    path = _cache_path(name)
    if not path.exists():
        return None
    syms = [ln.strip().upper() for ln in path.read_text().splitlines() if ln.strip()]
    return syms or None


def _cache_age_days(name: str) -> float | None:
    path = _cache_path(name)
    if not path.exists():
        return None
    return (time.time() - path.stat().st_mtime) / 86400.0


def _write_cached(name: str, syms: list[str]) -> None:
    _cache_path(name).write_text("\n".join(syms))


# ---------------------------------------------------------------------------
# HTTP with an explicit User-Agent (2026-08-13)
# ---------------------------------------------------------------------------
# Wikipedia answers HTTP 403 to the default urllib/pandas user-agent — which
# is what `pandas.read_html(url)` sends when you hand it a URL, because pandas
# fetches the page itself via urllib. Verified inside the api container:
#
#   default urllib UA                 -> HTTP 403  (126 bytes, error page)
#   any descriptive/browser UA        -> HTTP 200  (568 KB, the real article)
#
# So we never let pandas do the fetching. We fetch with `requests` + a
# descriptive UA (Wikimedia's UA policy asks for an identifiable agent with a
# contact URL) and hand pandas the HTML text. Same trick applies to any other
# HTML/CSV source that filters on UA.
_HTTP_UA = "cheetah-market-app/1.0 (+https://pounce.ajaykandakatla.dev)"


def _fetch_text(url: str, *, timeout: int = 20) -> str:
    """GET `url` with our descriptive User-Agent; raise on non-2xx."""
    import requests
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": _HTTP_UA})
    resp.raise_for_status()
    return resp.text


def _read_html_ua(url: str, *, timeout: int = 20):
    """`pandas.read_html`, but over HTML we fetched ourselves with a real UA.

    Never pass a URL straight to pandas.read_html — it fetches with the
    default urllib UA and Wikipedia 403s that.
    """
    import io
    import pandas as pd
    return pd.read_html(io.StringIO(_fetch_text(url, timeout=timeout)))


# --- source provenance ------------------------------------------------------
# Which source each list actually came from on the last resolve, so callers
# can tell "the real, fresh index" from "a 76-day-old snapshot" from "the
# wrong universe entirely". Without this, a stale list looks identical to a
# fresh one at the call site and degrades silently — exactly the failure this
# module hit between 2026-05-29 and 2026-08-13.
_LAST_SOURCE: dict[str, dict] = {}


def _record(name: str, source: str, syms: list[str], *,
            age_days: float | None = None) -> list[str]:
    _LAST_SOURCE[name] = {"source": source, "n": len(syms), "age_days": age_days}
    return syms


def last_source(name: str) -> dict | None:
    """How `name` was resolved on its last fetch, or None if never fetched.

    Returns ``{"source": str, "n": int, "age_days": float | None}`` where
    source is one of: ``cache`` (fresh, within TTL), ``wikipedia``,
    ``datahub``, ``stale-cache`` (expired but real), ``curated`` (WRONG
    universe — last-resort only), ``empty``.
    """
    rec = _LAST_SOURCE.get(name)
    return dict(rec) if rec else None


def is_stale(name: str) -> bool:
    """True when `name` last resolved to an expired cache — a real index
    snapshot, but one that has stopped tracking membership changes."""
    rec = _LAST_SOURCE.get(name)
    return bool(rec and rec["source"] == "stale-cache")


# --- constituent-count sanity gates -----------------------------------------
# A parse that silently returns 12 names (table shape changed, column renamed,
# an interstitial page that happens to contain a table) must NOT be cached and
# must NOT be served as "the S&P 500". Falling through to a stale-but-real
# snapshot is strictly better than scanning a truncated list. Bounds are wide
# enough to survive normal index drift — the S&P 500 carries ~503 share
# classes (a few issuers have two), the S&P 400 ~400.
# Sane size band per list. Ajay 2026-08-16: "add a count checks for returned
# values for all the tickers API like Russel 3000 and S&P 500 as well."
#
# Every band below is anchored on a MEASURED count taken 2026-08-16 (shown in
# the comment), widened to absorb legitimate index churn and dual-class adds.
# A list that lands outside its band is not a smaller universe — it is a parse
# that silently changed meaning, which is exactly how the scan came to run on
# 158 names while reporting "S&P 1500".
_EXPECTED_COUNTS: dict[str, tuple[int, int]] = {
    "sp500": (450, 530),          # measured 503
    "sp400": (350, 430),          # measured 400
    "sp600": (540, 650),          # measured 603
    # The Nasdaq-100 holds 100 companies but slightly more SYMBOLS, because a
    # few constituents have two share classes in the index (GOOG/GOOGL,
    # FOX/FOXA). Range, not equality, so a legitimate dual-class add does not
    # look like a parse failure.
    "nasdaq100": (95, 115),       # measured 102
    "sp1500": (1350, 1700),       # measured 1506 (500+400+600 layered)
    "russell1000": (900, 1150),   # measured 1001
    # Deliberately floored ABOVE the ~1030-name clean fallback (curated ∪ sp500
    # ∪ sp400). If the iShares file is missing we fall back to a list that is a
    # perfectly good universe but is NOT the Russell 3000 — and the whole point
    # of this band is to say so out loud rather than mislabel it.
    "russell3000": (1800, 3200),  # measured 2559
    # microcap is an optional layer (IWC holdings file); absent is legitimate,
    # so there is no lower bound — only an upper one to catch a bad parse.
    "microcap": (0, 2500),        # measured 1278
    "etf": (150, 600),            # measured 373
    "themes": (20, 300),          # measured 82, hand-curated
    "broad": (1800, 6000),        # measured 3707
    "massive": (3000, 7000),      # ~5300 per the fetcher's own docstring
}

# Last observed size per list, for the health check. name -> dict.
LAST_COUNTS: dict[str, dict] = {}


def _count_ok(name: str, syms: list[str]) -> bool:
    lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
    if lo <= len(syms) <= hi:
        return True
    log.warning("universe: %s parse returned %d names, outside the sane range "
                "%d-%d — rejecting this source", name, len(syms), lo, hi)
    return False


def _record_count(name: str, syms: list[str]) -> list[str]:
    """Observe a fetcher's result size. Returns `syms` unchanged.

    Distinct from `_count_ok`, which REJECTS a source mid-fallback-chain. This
    one runs at the boundary, where rejecting would leave the caller with
    nothing — so it logs loudly and records for `universe_counts()` instead.
    """
    n = len(syms or [])
    lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
    ok = lo <= n <= hi
    LAST_COUNTS[name] = {"count": n, "expected": [lo, hi], "ok": ok}
    if not ok:
        log.error("universe: %s returned %d names, OUTSIDE the sane range %d-%d "
                  "— the scan is running on the wrong universe", name, n, lo, hi)
    return syms


def _count_guarded(name: str, fn):
    """Wrap a public fetcher so every return path is size-checked at source.

    Applied by name after the definitions rather than at each `return`: these
    fetchers have up to six exit points each (cache hit, local file, network,
    mirror, stale cache, clean fallback) and guarding one of them is how the
    fallback paths escaped the check in the first place.
    """
    @functools.wraps(fn)
    def inner(*args, **kwargs):
        return _record_count(name, fn(*args, **kwargs))
    return inner


def universe_counts(names: list[str] | None = None) -> dict:
    """Call each list fetcher and report its size against its sane band.

    Used by the health audit and safe to call ad hoc — every fetcher is disk
    cached for 30 days, so this is cheap after the first pass.
    """
    import collections
    fetchers: "collections.OrderedDict[str, object]" = collections.OrderedDict((
        ("sp500", fetch_sp500), ("sp400", fetch_sp400), ("sp600", fetch_sp600),
        ("nasdaq100", fetch_nasdaq100), ("sp1500", fetch_sp1500),
        ("russell1000", fetch_russell1000), ("russell3000", fetch_russell3000),
        ("microcap", fetch_microcap), ("etf", fetch_etf_universe),
        ("themes", fetch_themes), ("broad", fetch_broad),
    ))
    out: dict = {}
    for name, fn in fetchers.items():
        if names and name not in names:
            continue
        lo, hi = _EXPECTED_COUNTS.get(name, (1, 10**9))
        try:
            n = len(fn())
            out[name] = {"count": n, "expected": [lo, hi], "ok": lo <= n <= hi,
                         "age_days": _cache_age_days(name)}
        except Exception as exc:
            out[name] = {"count": None, "expected": [lo, hi], "ok": False,
                         "error": f"{type(exc).__name__}: {exc}"[:160]}
    out["_failing"] = sorted(k for k, v in out.items()
                             if isinstance(v, dict) and not v.get("ok"))
    return out


def _dedup_symbols(raw) -> list[str]:
    """Uppercase, dot→dash (BRK.B → BRK-B), drop blanks/NaN, dedup in order."""
    seen, out = set(), []
    for s in raw:
        sym = str(s).strip().replace(".", "-").upper()
        if not sym or sym == "NAN" or sym in seen:
            continue
        seen.add(sym)
        out.append(sym)
    return out


# Independent-transport mirror of the same S&P 500 constituent table, served
# as a plain CSV from GitHub raw by the `datasets` org. Honest caveat: this is
# DERIVED from the same Wikipedia table, so it is not an independent *source
# of truth* — but it is an independent *delivery path*, which is precisely the
# failure mode that took Wikipedia out (UA filtering at the edge). If
# Wikipedia blocks or reshapes its table again, this keeps the list fresh.
_DATAHUB_SP500_URL = (
    "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/"
    "main/data/constituents.csv"
)


def _sp500_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
    return _dedup_symbols(tables[0]["Symbol"].tolist())


def _sp500_from_datahub() -> list[str]:
    import csv
    import io
    rows = csv.DictReader(io.StringIO(_fetch_text(_DATAHUB_SP500_URL)))
    return _dedup_symbols(r.get("Symbol", "") for r in rows)


def _sp400_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_400_companies")
    # The constituents table isn't always tables[0] on this page — find the
    # one that actually has a Symbol/Ticker column.
    for tb in tables:
        col = next((c for c in tb.columns
                    if str(c).lower() in ("symbol", "ticker")), None)
        if col is not None:
            return _dedup_symbols(tb[col].tolist())
    return []


def _sp600_from_wikipedia() -> list[str]:
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_S%26P_600_companies")
    for tb in tables:
        col = next((c for c in tb.columns
                    if str(c).lower() in ("symbol", "ticker")), None)
        if col is not None:
            return _dedup_symbols(tb[col].tolist())
    return []


def _resolve_index(name: str, loaders: list[tuple[str, object]],
                   *, on_exhausted: str) -> list[str]:
    """Shared resolve ladder for the S&P constituent lists.

        fresh cache → each live loader in order → stale cache → last resort

    A live loader only wins if it parses AND passes the count sanity gate;
    otherwise we keep walking. Every outcome is recorded via `_record` so
    callers can see whether they got the real, fresh index or a fallback.

    `on_exhausted` is "curated" (return the curated list — WRONG universe,
    sp500's historical behaviour, kept only so a scan still runs) or "empty".
    """
    cached = _read_cached(name)
    if cached:
        return _record(name, "cache", cached, age_days=_cache_age_days(name))

    failures: list[str] = []
    for label, loader in loaders:
        try:
            out = loader()
        except Exception as exc:
            failures.append(f"{label}: {exc}")
            continue
        if out and _count_ok(name, out):
            _write_cached(name, out)
            log.info("universe: fetched %d %s components from %s",
                     len(out), name, label)
            return _record(name, label, out, age_days=0.0)
        failures.append(f"{label}: rejected ({len(out)} names)")

    why = "; ".join(failures) or "no loaders"
    stale = _read_cached_stale(name)
    if stale:
        age = _cache_age_days(name) or 0.0
        log.warning("universe: %s live fetch failed (%s) — using STALE cached "
                    "list (%d names, %.0fd old)", name, why, len(stale), age)
        return _record(name, "stale-cache", stale, age_days=age)

    if on_exhausted == "curated":
        log.warning("universe: %s fetch failed (%s) and no cache exists — "
                    "falling back to the CURATED list, which is NOT %s",
                    name, why, name)
        return _record(name, "curated", list(UNIVERSE))
    log.warning("universe: %s fetch failed (%s) and no cache exists — "
                "skipping this layer", name, why)
    return _record(name, "empty", [])


def fetch_sp500() -> list[str]:
    """Return S&P 500 components, cached 30 days.

    Resolve order: fresh cache → Wikipedia → datahub CSV mirror → stale
    cache → curated.

    WIKIPEDIA 403 (2026-08-13): Wikipedia rejects the default urllib UA that
    `pandas.read_html(url)` sends, so the live fetch failed on every call and
    the cache aged out. The fix is `_read_html_ua` — fetch with requests + a
    descriptive User-Agent, then parse. Verified in-container: default UA
    403s, descriptive UA returns the full article.

    Two layers of protection remain behind that, because a scan that claims
    "S&P 500" while holding some other list is wrong data, not degraded data:

      - `datahub` is a second delivery path for the same table (GitHub raw
        CSV), so a repeat of the UA block doesn't re-freeze the list.
      - the STALE cache beats the curated list. Index membership turns over
        only a few names a quarter, so an expired snapshot is ~99% right,
        while the 158-name curated list is a different universe entirely
        (mega-caps + momentum movers). Curated is the true last resort and
        is reported as such via `last_source("sp500")`.
    """
    return _resolve_index(
        "sp500",
        [("wikipedia", _sp500_from_wikipedia), ("datahub", _sp500_from_datahub)],
        on_exhausted="curated",
    )


def fetch_sp400() -> list[str]:
    """Return S&P 400 MidCap components, cached 30 days.

    Mirror of fetch_sp500 against Wikipedia's S&P 400 list, and it hit the
    same 403 (sp400.txt had aged to 76 days alongside sp500.txt) — so it goes
    through the same UA'd fetch.

    These names are almost all already inside the Russell 3000, so this is
    belt-and-suspenders coverage. It falls back to the stale cache but NEVER
    to curated: returning large-caps here would pollute the mid-cap layer of
    a union, so the last resort is [].
    """
    return _resolve_index(
        "sp400",
        [("wikipedia", _sp400_from_wikipedia)],
        on_exhausted="empty",
    )


def fetch_sp600() -> list[str]:
    """Return S&P 600 SmallCap components, cached 30 days.

    Added 2026-08-13 (Ajay: "expand the scan to best companies beyond S and p
    500 increase in to 1000 others"). S&P 400 + S&P 600 together are ~1,000
    names OUTSIDE the S&P 500, and unlike a raw Russell slice they clear S&P's
    index-committee bar — including a positive-earnings requirement — so
    "best companies beyond the S&P 500" is a fair description of them.

    Same ladder and the same never-fall-back-to-curated rule as sp400: a
    large-cap list leaking into the small-cap layer would corrupt any union.
    """
    return _resolve_index(
        "sp600",
        [("wikipedia", _sp600_from_wikipedia)],
        on_exhausted="empty",
    )


def _nasdaq100_from_wikipedia() -> list[str]:
    """Nasdaq-100 constituents.

    NOTE the URL: the components table lives on the SEPARATE
    "List_of_NASDAQ-100_companies" page, not on the "Nasdaq-100" article — that
    one now carries only index history (milestones, yearly closes) and links
    out. Verified 2026-08-16: the article yields 0 tickers, the list page
    yields 102 across columns Ticker / Company / ICB Industry / ICB Subsector.

    The components table is identified by carrying BOTH a ticker column and a
    company/industry column, which the navbox and history tables do not.
    """
    tables = _read_html_ua("https://en.wikipedia.org/wiki/List_of_NASDAQ-100_companies")
    best: list[str] = []
    for tb in tables:
        cols = {str(c).lower() for c in tb.columns}
        tick = next((c for c in tb.columns
                     if str(c).lower() in ("symbol", "ticker")), None)
        if tick is None:
            continue
        if not any(k in c for c in cols
                   for k in ("company", "name", "industry", "sector")):
            continue
        syms = _dedup_symbols(tb[tick].tolist())
        if len(syms) > len(best):
            best = syms
    return best


def fetch_nasdaq100() -> list[str]:
    """Nasdaq-100 — the large-cap non-financial Nasdaq names.

    Added 2026-08-16 (Ajay: "Latest tickers as they change like getting added
    to SP 500 or Russel 3000 and Nasdaq"). Nasdaq was the one index family the
    app tracked nowhere: the S&P ladders cover the NYSE/Nasdaq blend by market
    cap and the Russell lists are broad-market, but neither tells you when a
    name JOINS the Nasdaq-100 — which is its own liquidity and flow event.

    Never falls back to curated: a large-cap growth list leaking in as
    "Nasdaq-100" would corrupt any membership diff built on top of it.
    """
    return _resolve_index(
        "nasdaq100",
        [("wikipedia", _nasdaq100_from_wikipedia)],
        on_exhausted="empty",
    )


def fetch_sp1500() -> list[str]:
    """S&P Composite 1500 = S&P 500 + S&P 400 MidCap + S&P 600 SmallCap.

    Deduped, order-stable (large -> mid -> small). Layers that fail resolve to
    [] rather than to curated, so a partial outage shrinks the universe instead
    of silently mixing in the wrong names — `last_source` reports each layer.
    """
    out: list[str] = []
    seen: set[str] = set()
    for part in (fetch_sp500(), fetch_sp400(), fetch_sp600()):
        for sym in part:
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out


# ============================================================================
# iShares CSV cleanup (added 2026-05-21)
# ----------------------------------------------------------------------------
# Two recurring sources of garbage in the raw iShares IWB CSV that the
# original ticker-shape regex didn't catch:
#
# 1. Class-share tickers come through with NO separator. iShares writes
#    "BRKB" (not "BRK.B" or "BRK-B"). yfinance only accepts "BRK-B" — so
#    these silently 404'd until we mapped them explicitly. The map below
#    covers every Russell 1000 / S&P 500 multi-class issuer as of 2026-05;
#    add new entries when iShares adds new dual-class IPOs.
#
# 2. Futures contracts used by the ETF for cash management — "ESM6"
#    (S&P 500 E-mini June 2026), "FAM6", "UBFUT", "XTSLA", etc. pass the
#    basic ticker regex but aren't equities. They're held inside the ETF
#    as cash-equivalent collateral, not as real holdings. Filter via
#    explicit blocklist + a futures-contract regex (single letter month
#    code H/M/U/Z + single digit year). Both layers — blocklist catches
#    named oddities, regex catches the next-year-future variants without
#    a code change.
# ============================================================================

# Real ticker → yfinance ticker remap for class-share names. Keys are the
# raw symbols iShares emits; values are the yfinance-accepted form.
_CLASS_SHARE_REMAP: dict[str, str] = {
    "BRKA":   "BRK-A",   # Berkshire Hathaway A
    "BRKB":   "BRK-B",   # Berkshire Hathaway B
    "BFA":    "BF-A",    # Brown-Forman A
    "BFB":    "BF-B",    # Brown-Forman B
    "CWENA":  "CWEN-A",  # Clearway Energy A
    "HEIA":   "HEI-A",   # HEICO A
    "LENB":   "LEN-B",   # Lennar B
    "UHALB":  "UHAL-B",  # U-Haul B
    "MOGA":   "MOG-A",   # Moog A
    "GEFB":   "GEF-B",   # Greif B
    "CRDA":   "CRD-A",   # Crawford A
    "CRDB":   "CRD-B",   # Crawford B
    "FCNCA":  "FCNCA",   # First Citizens — yfinance accepts as-is
    "JWA":    "JW-A",    # John Wiley A
    "JWB":    "JW-B",    # John Wiley B
    "RUSHA":  "RUSHA",   # Rush Enterprises A — yfinance accepts as-is
    "RUSHB":  "RUSHB",   # Rush Enterprises B — yfinance accepts as-is
}

# Hardcoded blocklist of non-equity symbols seen leaking through. These
# are futures contracts / ETF internal accounting placeholders that
# happen to have valid-looking ticker shapes. Lowercase comparison; we
# normalize incoming symbols to upper.
_NON_EQUITY_BLOCKLIST: set[str] = {
    "XTSLA",     # iShares internal Tesla proxy / not a real ticker
    "UBFUT",     # Ultra T-Bond futures collateral
    "MGEH",      # Common iShares cash-equivalent placeholder
    # Futures contracts seen in Q2 2026:
    "ESM6", "ESU6", "ESZ6", "ESH7",   # S&P 500 E-mini contracts
    "FAM6", "FAU6", "FAZ6",            # Russell 2000 mini futures
    "NQM6", "NQU6",                    # Nasdaq 100 E-mini
    "VXM6", "VXU6",                    # VIX futures
    "USD", "EUR", "JPY", "GBP",        # FX placeholders
    "MARGIN_USD", "CASH",              # iShares accounting rows
}

# Futures-contract pattern: ROOT (2-4 letters) + MONTH (H/M/U/Z) + YEAR (1 digit).
# Catches ESM6, FAM6, NQU7, etc. without needing a code update each year.
# Real equity tickers don't follow this pattern (only edge case: companies
# whose ticker ends in [HMUZ][0-9], which doesn't currently exist in Russell
# 1000 — checked 2026-05-21).
import re as _re
_FUTURES_PATTERN = _re.compile(r"^[A-Z]{1,3}[HMUZ][0-9]$")


def _normalize_ishares_ticker(raw: str) -> str | None:
    """Convert an iShares-emitted ticker to the yfinance form, or None
    if the symbol should be excluded from the equity universe.

    Order of operations:
      1. Drop known non-equity placeholders (XTSLA, UBFUT, CASH, etc.).
      2. Drop futures-contract patterns (ESM6, NQU7, etc.).
      3. Apply class-share remap (BRKB → BRK-B, BFA → BF-A, etc.).
      4. Convert any legacy dot notation (BRK.B → BRK-B).
      5. Final shape check — only allow ticker-like strings through.
    """
    s = (raw or "").strip().upper()
    if not s or s in {"-", "CASH"}:
        return None
    if s in _NON_EQUITY_BLOCKLIST:
        return None
    if _FUTURES_PATTERN.match(s):
        return None
    # Class-share remap takes precedence over dot-to-dash because
    # iShares typically emits the joined form (BRKB) not the dotted form.
    if s in _CLASS_SHARE_REMAP:
        return _CLASS_SHARE_REMAP[s]
    if "." in s:
        s = s.replace(".", "-")
    # Final shape check.
    if not _re.match(r"^[A-Z][A-Z0-9\-]{0,9}$", s):
        return None
    return s


def fetch_massive_universe(limit: int | None = None) -> list[str]:
    """Return all active US common stocks via Massive's reference endpoint.

    Used as a fallback when iShares blocks CSV downloads (their site
    sporadically serves HTML instead of CSV for IWB/IWV ETF holdings).
    Cached 30 days under 'massive_universe.txt'. Paginates through the
    /v3/reference/tickers endpoint until exhausted — typically 5-6 pages
    for ~5,300 active common stocks.

    Args:
        limit: optional cap on number of tickers returned (preserves
               alphabetical order from Massive). None returns the full list.
    """
    cache_name = "massive_universe"
    cached = _read_cached(cache_name)
    if cached:
        return cached[:limit] if limit else cached

    api_key = stocks_key()
    if not api_key:
        log.warning("universe: MASSIVE_API_KEY not set; cannot fetch Massive universe")
        return []
    try:
        import requests
    except ImportError:
        return []

    all_tickers: list[str] = []
    url = "https://api.massive.com/v3/reference/tickers"
    params: dict = {
        "market":  "stocks",
        "type":    "CS",       # Common Stock — drop preferreds, units, warrants
        "active":  "true",
        "limit":   1000,
        "apiKey":  api_key,
    }
    page = 1
    next_url = url
    next_params = params
    try:
        while next_url and page <= 10:  # safety: cap at 10 pages = 10,000 tickers
            r = requests.get(
                next_url,
                params=next_params if page == 1 else {"apiKey": api_key},
                timeout=20,
            )
            if r.status_code != 200:
                log.warning("universe: Massive tickers page %d returned HTTP %s",
                            page, r.status_code)
                break
            data = r.json()
            for entry in (data.get("results") or []):
                t = (entry.get("ticker") or "").upper().strip()
                if not t:
                    continue
                # Filter weird-shape tickers (units, warrants leak through with
                # suffixes like ABC.U, ABC.W). Allow [A-Z][A-Z0-9-]{0,9}.
                if not _re.match(r"^[A-Z][A-Z0-9\-]{0,9}$", t):
                    continue
                # Keep only major exchanges; drop OTC/PINK.
                exch = (entry.get("primary_exchange") or "").upper()
                if exch and exch not in {"XNYS", "XNAS", "ARCX", "BATS", "XASE"}:
                    continue
                all_tickers.append(t)
            next_url = data.get("next_url")
            page += 1
        # Dedup preserving order
        seen, out = set(), []
        for t in all_tickers:
            if t not in seen:
                seen.add(t)
                out.append(t)
        if not out:
            return []
        _write_cached(cache_name, out)
        log.info("universe: Massive universe cached — %d active US common stocks", len(out))
        return out[:limit] if limit else out
    except Exception as exc:
        log.warning("universe: Massive universe fetch failed (%s)", exc)
        return []


# --- iShares manually-downloaded SpreadsheetML loader -------------------
#
# Why this exists (2026-05-29): iShares' public CSV download endpoints
# (1467271812596.ajax?fileType=csv&...) now serve a Cloudflare-style HTML
# disclaimer interstitial instead of CSV unless the requester executes JS
# AND clicks "Individual Investor". Even Chrome TLS impersonation via
# curl_cffi fails. Headless browsers (Playwright) would work but add a
# heavy dep for one source.
#
# Pragmatic answer: Ajay downloads the IWB / IWV "Download Holdings" file
# from iShares (the button gives a .xls SpreadsheetML XML, not CSV) and
# drops it into `backend/sepa/data/`. We parse that file as the primary
# source. Russell reconstitutes annually + iShares rebalances quarterly,
# so a manual refresh every ~3 months keeps coverage current.

_DATA_DIR = Path(__file__).parent / "data"
_LOCAL_IWB_PATH = _DATA_DIR / "iShares-Russell-1000-ETF_fund.xls"
_LOCAL_IWV_PATH = _DATA_DIR / "iShares-Russell-3000-ETF_fund.xls"
# Micro-cap extension ("beyond Russell 3000", user 2026-05-30). The Russell
# 3000 ≈ Russell 1000 + Russell 2000, so true small/micro names below it come
# from the iShares Micro-Cap ETF (IWC) holdings. Same "Download Holdings" .xls
# format. Optional — if the file isn't present, the micro-cap layer is just
# skipped (the broad mode still returns R3000 ∪ ETFs).
_LOCAL_IWC_PATH = _DATA_DIR / "iShares-Micro-Cap-ETF_fund.xls"

# SpreadsheetML 2003 namespace — iShares' Holdings.xls export uses this.
_SS_NS = "{urn:schemas-microsoft-com:office:spreadsheet}"


def _load_ishares_local_xls(path: Path, *, source_label: str) -> list[str]:
    """Parse an iShares "Download Holdings" .xls (SpreadsheetML XML).

    Locates the 'Holdings' worksheet, finds the row whose first cell
    is 'Ticker', then iterates data rows pulling column 0 (Ticker)
    and column 3 (Asset Class) — filters to Equity only to drop
    cash / derivatives / future positions.

    Each surviving ticker is run through _normalize_ishares_ticker
    (class-share remap + futures/junk filter) for symmetry with the
    network path, and dedup'd.

    Raises FileNotFoundError if the file isn't present, RuntimeError
    on parse failure (bad XML, missing Holdings sheet, etc.).
    """
    if not path.exists():
        raise FileNotFoundError(f"iShares local file missing: {path}")

    # File age — useful warning when the user forgets to refresh quarterly.
    age_days = (time.time() - path.stat().st_mtime) / 86400
    if age_days > 120:
        log.warning(
            "universe: %s local file is %.0f days old (%s) — "
            "refresh from iShares.com 'Download Holdings'",
            source_label, age_days, path.name,
        )

    from lxml import etree
    # iShares files have occasional malformed bits; recover=True
    # lets lxml skip them rather than aborting the whole parse.
    parser = etree.XMLParser(recover=True)
    tree = etree.parse(str(path), parser)
    root = tree.getroot()

    holdings_ws = None
    for ws in root.findall(f"{_SS_NS}Worksheet"):
        if ws.get(f"{_SS_NS}Name") == "Holdings":
            holdings_ws = ws
            break
    if holdings_ws is None:
        raise RuntimeError(f"{source_label}: 'Holdings' worksheet not found in {path.name}")

    rows = holdings_ws.findall(f".//{_SS_NS}Row")

    def _cell_strings(row) -> list[str]:
        out = []
        for cell in row.findall(f"{_SS_NS}Cell"):
            data = cell.find(f"{_SS_NS}Data")
            out.append(data.text if data is not None and data.text else "")
        return out

    # Find the header row (first cell == 'Ticker'). iShares puts ~7 rows
    # of fund metadata above it; that count drifts so detect, don't hardcode.
    header_idx = None
    ticker_col = 0
    asset_class_col = None
    for i, r in enumerate(rows[:50]):
        cells = _cell_strings(r)
        if cells and cells[0].strip() == "Ticker":
            header_idx = i
            for j, h in enumerate(cells):
                if h.strip().lower() == "asset class":
                    asset_class_col = j
                    break
            break
    if header_idx is None:
        raise RuntimeError(f"{source_label}: header row with 'Ticker' not found in {path.name}")

    raw_tickers = []
    n_skipped_non_equity = 0
    for r in rows[header_idx + 1:]:
        cells = _cell_strings(r)
        if not cells:
            continue
        ticker_raw = (cells[ticker_col] if ticker_col < len(cells) else "").strip()
        if not ticker_raw:
            continue
        # Asset Class filter — drop cash, derivatives, futures, etc.
        if asset_class_col is not None and asset_class_col < len(cells):
            asset_class = cells[asset_class_col].strip().lower()
            if asset_class and asset_class != "equity":
                n_skipped_non_equity += 1
                continue
        raw_tickers.append(ticker_raw)

    # Same cleanup pipeline as the network path so behavior is identical.
    n_dropped_non_equity = 0
    n_dropped_shape = 0
    n_remapped_class = 0
    seen, out = set(), []
    for r in raw_tickers:
        r_up = r.strip().upper()
        norm = _normalize_ishares_ticker(r)
        if norm is None:
            if r_up in _NON_EQUITY_BLOCKLIST or _FUTURES_PATTERN.match(r_up):
                n_dropped_non_equity += 1
            else:
                n_dropped_shape += 1
            continue
        if r_up in _CLASS_SHARE_REMAP and norm != r_up:
            n_remapped_class += 1
        if norm not in seen:
            seen.add(norm)
            out.append(norm)

    log.info(
        "universe: %s local-xls loaded — kept=%d  "
        "class_share_remapped=%d  skipped_non_equity_row=%d  "
        "dropped_non_equity_norm=%d  dropped_shape=%d  age=%.0fd",
        source_label, len(out), n_remapped_class, n_skipped_non_equity,
        n_dropped_non_equity, n_dropped_shape, age_days,
    )
    return out


def fetch_russell1000() -> list[str]:
    """Return Russell 1000 components, cached 30 days.

    Source priority:
      1. ``backend/sepa/data/iShares-Russell-1000-ETF_fund.xls`` — manually
         downloaded SpreadsheetML export from iShares.com (their public
         CSV download URLs now require JS / Cloudflare clearance and
         can't be fetched programmatically). Quarterly refresh.
      2. Network fetch of the iShares IWB CSV URL (usually returns HTML
         interstitial these days; kept for if/when iShares relaxes).
      3. Clean fallback: curated ∪ S&P 500 ∪ S&P 400 MidCap.
    """
    cached = _read_cached("russell1000")
    if cached:
        return cached

    # --- (1) local SpreadsheetML file --------------------------------
    try:
        out = _load_ishares_local_xls(_LOCAL_IWB_PATH, source_label="russell1000")
        if out:
            _write_cached("russell1000", out)
            return out
    except FileNotFoundError:
        log.info("universe: russell1000 local xls absent — trying network")
    except Exception as exc:
        log.warning("universe: russell1000 local-xls parse failed (%s) — trying network", exc)

    # --- (2) network fetch (legacy path; usually 200/HTML now) -------
    try:
        import io
        import pandas as pd
        import requests
        url = (
            "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"
        )
        # Dynamic header detection — iShares periodically shifts the
        # leading-metadata row count (was 9, has been 7/10 historically).
        # Hard-coded skiprows breaks the day they shift again. Instead we
        # download the raw bytes and find the row that starts with the
        # canonical column header ``"Ticker"`` (always quoted).
        resp = requests.get(url, timeout=15,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; cheetah/0.1)"})
        resp.raise_for_status()
        text = resp.text
        lines = text.splitlines()
        header_idx = None
        for i, ln in enumerate(lines[:50]):
            # Header row has "Ticker" as first field (with or without
            # quotes). Match defensively against both forms.
            if ln.lstrip().startswith(("Ticker,", '"Ticker"')):
                header_idx = i
                break
        if header_idx is None:
            raise RuntimeError("iShares CSV: header row with 'Ticker' not found")
        # Re-parse from the located header. Use io.StringIO so we don't
        # re-hit the network.
        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
        # Pull raw tickers, then run each through the cleanup pipeline
        # that handles class-share remap + futures/junk filtering.
        raw = [str(s) for s in df["Ticker"].tolist() if isinstance(s, str)]
        n_dropped_non_equity = 0
        n_dropped_shape = 0
        n_remapped_class = 0
        seen, out = set(), []
        for r in raw:
            r_up = r.strip().upper()
            norm = _normalize_ishares_ticker(r)
            if norm is None:
                if r_up in _NON_EQUITY_BLOCKLIST or _FUTURES_PATTERN.match(r_up):
                    n_dropped_non_equity += 1
                else:
                    n_dropped_shape += 1
                continue
            if r_up in _CLASS_SHARE_REMAP and norm != r_up:
                n_remapped_class += 1
            if norm not in seen:
                seen.add(norm)
                out.append(norm)
        log.info(
            "universe: russell1000 cleaned — kept=%d  "
            "class_share_remapped=%d  dropped_non_equity=%d  dropped_shape=%d",
            len(out), n_remapped_class, n_dropped_non_equity, n_dropped_shape,
        )
        _write_cached("russell1000", out)
        return out
    except Exception as exc:
        log.warning(
            "universe: russell1000 network fetch failed (%s) — "
            "falling back to curated ∪ S&P 500 ∪ S&P 400 MidCap", exc,
        )
        # Deterministic, no-404 fallback: curated leaders + S&P 500 (large)
        # + S&P 400 (mid). Together ~1030 strict names from Wikipedia —
        # much cleaner than the Massive alphabetical grab which used to
        # silently truncate at A-C.
        try:
            sp500 = fetch_sp500()
            try:
                sp400 = fetch_sp400()
            except Exception:
                sp400 = []
            merged = list(dict.fromkeys(list(UNIVERSE) + sp500 + sp400))
            log.info(
                "universe: russell1000 via curated+sp500+sp400 = %d names",
                len(merged),
            )
            return merged
        except Exception as exc2:
            log.warning("universe: Wikipedia fallback also failed (%s) — using S&P 500 only", exc2)
            return fetch_sp500()


def fetch_russell3000() -> list[str]:
    """Return Russell 3000 components, cached 30 days.

    Source priority (same as fetch_russell1000):
      1. ``backend/sepa/data/iShares-Russell-3000-ETF_fund.xls`` — manually
         downloaded SpreadsheetML export.
      2. Network fetch of the IWV CSV URL (usually returns HTML now).
      3. Clean fallback: curated ∪ S&P 500 ∪ S&P 400 MidCap (~1030 names,
         strict; better than Massive's noisy alphabetical 5097).
    """
    cached = _read_cached("russell3000")
    if cached:
        return cached

    # --- (1) local SpreadsheetML file --------------------------------
    try:
        out = _load_ishares_local_xls(_LOCAL_IWV_PATH, source_label="russell3000")
        if out:
            _write_cached("russell3000", out)
            return out
    except FileNotFoundError:
        log.info("universe: russell3000 local xls absent — trying network")
    except Exception as exc:
        log.warning("universe: russell3000 local-xls parse failed (%s) — trying network", exc)

    # --- (2) network fetch (legacy path; usually 200/HTML now) -------
    try:
        import io
        import pandas as pd
        import requests
        url = (
            "https://www.ishares.com/us/products/239714/ishares-russell-3000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWV_holdings&dataType=fund"
        )
        # Same dynamic header detection as fetch_russell1000 — iShares
        # CSVs ship with a leading metadata block of varying row count.
        resp = requests.get(url, timeout=20,
                            headers={"User-Agent": "Mozilla/5.0 (compatible; cheetah/0.1)"})
        resp.raise_for_status()
        text = resp.text
        lines = text.splitlines()
        header_idx = None
        for i, ln in enumerate(lines[:50]):
            if ln.lstrip().startswith(("Ticker,", '"Ticker"')):
                header_idx = i
                break
        if header_idx is None:
            raise RuntimeError("iShares CSV: header row with 'Ticker' not found")
        df = pd.read_csv(io.StringIO(text), skiprows=header_idx)
        raw = [str(s) for s in df["Ticker"].tolist() if isinstance(s, str)]
        n_dropped_non_equity = 0
        n_dropped_shape = 0
        n_remapped_class = 0
        seen, out = set(), []
        for r in raw:
            r_up = r.strip().upper()
            norm = _normalize_ishares_ticker(r)
            if norm is None:
                if r_up in _NON_EQUITY_BLOCKLIST or _FUTURES_PATTERN.match(r_up):
                    n_dropped_non_equity += 1
                else:
                    n_dropped_shape += 1
                continue
            if r_up in _CLASS_SHARE_REMAP and norm != r_up:
                n_remapped_class += 1
            if norm not in seen:
                seen.add(norm)
                out.append(norm)
        log.info(
            "universe: russell3000 cleaned — kept=%d  "
            "class_share_remapped=%d  dropped_non_equity=%d  dropped_shape=%d",
            len(out), n_remapped_class, n_dropped_non_equity, n_dropped_shape,
        )
        _write_cached("russell3000", out)
        return out
    except Exception as exc:
        log.warning(
            "universe: russell3000 network fetch failed (%s) — "
            "falling back to curated ∪ S&P 500 ∪ S&P 400 MidCap", exc,
        )
        # Same clean fallback as russell1000 — strict ~1030 names from
        # Wikipedia instead of the noisy Massive 5097.
        try:
            sp500 = fetch_sp500()
            try:
                sp400 = fetch_sp400()
            except Exception:
                sp400 = []
            merged = list(dict.fromkeys(list(UNIVERSE) + sp500 + sp400))
            log.info(
                "universe: russell3000 via curated+sp500+sp400 = %d names",
                len(merged),
            )
            return merged
        except Exception as exc2:
            log.warning("universe: Wikipedia fallback also failed (%s) — using S&P 500 only", exc2)
            return fetch_sp500()


def fetch_microcap() -> list[str]:
    """Micro-cap names below the Russell 3000, from the local iShares
    Micro-Cap ETF (IWC) holdings .xls. Returns [] (not an error) when the
    file is absent — the broad universe is still valid without it.

    Cached 30 days like the other Russell sources.
    """
    cached = _read_cached("microcap")
    if cached:
        return cached
    if not _LOCAL_IWC_PATH.exists():
        log.info("universe: microcap IWC file absent (%s) — skipping micro-cap layer",
                 _LOCAL_IWC_PATH.name)
        return []
    try:
        out = _load_ishares_local_xls(_LOCAL_IWC_PATH, source_label="microcap")
        if out:
            _write_cached("microcap", out)
        return out
    except Exception as exc:
        log.warning("universe: microcap local-xls parse failed (%s) — skipping", exc)
        return []


def fetch_etf_universe() -> list[str]:
    """Broad list of liquid US-listed ETFs (see sepa/etf_universe.py).

    SEPA's liquidity gate + trend template filter downstream, so this list is
    intentionally over-inclusive. Static (no network), so no caching needed.
    """
    try:
        from .etf_universe import etf_universe as _etfs
        return _etfs()
    except Exception as exc:
        log.warning("universe: ETF universe import failed (%s)", exc)
        return []


def fetch_broad() -> list[str]:
    """Widest equity + ETF net (user 2026-05-30: "expand beyond Russell 3000
    alongside ETFs"):

        curated  ∪  Russell 3000  ∪  micro-caps (IWC, if present)  ∪  ETFs

    `curated` goes FIRST and is non-negotiable: the iShares Russell holdings
    are US-domiciled only, so foreign ADRs Ajay actively trades — ARM, ASML,
    TSM, SHOP, BABA, … — are NOT Russell constituents and silently vanished
    from `broad` (ARM dropped 2026-05-30: "it was in the list till
    yesterday"). The hand-picked curated list carries those names plus the
    mega-cap leaders, so unioning it back guarantees they're always scanned
    AND pre-warms them early. Dedup keeps first-seen order.
    """
    curated = list(UNIVERSE)
    # S&P 500 + 400 explicit union — almost entirely a subset of Russell 3000
    # already (so net-new is ~0), but it guarantees full S&P coverage even if
    # the quarterly iShares snapshot is stale on a recent index add, and it
    # restores the old fallback universe (curated ∪ sp500 ∪ sp400) the user
    # asked to preserve. Both fall back gracefully (sp500→curated, sp400→[]).
    sp500 = fetch_sp500()
    sp400 = fetch_sp400()
    # Build-out themes, for the same reason curated is here: the quantum /
    # SMR-nuclear / robotics names are pre-profit and several are foreign ADRs,
    # so they are in no S&P tier and the US-domiciled-only Russell holdings miss
    # the ADRs too. Measured 2026-08-15: 40 of the 42 theme names already
    # arrived via curated ∪ russell1000, but ARQQ and SYM reached NO layer, so
    # the Strong VCP board could never show them. Unioning the rosters closes
    # that without touching SEPA_UNIVERSE_MODE.
    themes = fetch_themes()
    equities = fetch_russell3000()
    micro = fetch_microcap()
    etfs = fetch_etf_universe()
    merged = list(dict.fromkeys(
        curated + themes + sp500 + sp400 + equities + micro + etfs
    ))
    log.info(
        "universe: broad mode = %d curated + %d themes + %d sp500 + %d sp400 "
        "+ %d R3000 + %d micro + %d ETF -> %d unique",
        len(curated), len(themes), len(sp500), len(sp400), len(equities),
        len(micro), len(etfs), len(merged),
    )
    return merged


# Orthogonal universe building blocks → fetcher. Used by the multi-select
# path in load_universe: the user picks any combination and we union + dedup
# (overlaps removed). Defined here, after every fetcher, so the direct
# function references resolve.
# Named aliases that expand to a set of components. Keep the membership here,
# next to the component map, so a page that offers "S&P 1500 + themes" cannot
# drift from what that phrase actually resolves to.
_UNIVERSE_ALIASES: dict[str, tuple[str, ...]] = {
    "sp1500_plus": ("sp1500", "curated", "themes"),
}


# The one place a component name maps to a fetcher. `load_universe` resolves
# single keys through the SAME map, so a name that works in a comma-separated
# multi-select cannot silently fail as a standalone mode — which is precisely
# how "sp1500" resolved to the curated 158.
_COMPONENT_FETCHERS: dict = {
    "curated":     lambda: list(UNIVERSE),
    "sp500":       lambda: fetch_sp500(),
    "sp400":       lambda: fetch_sp400(),
    # sp600/sp1500 existed as fetchers but were absent from this map, so
    # SEPA_UNIVERSE_MODE="curated,sp1500" silently resolved to the curated
    # ~158 names with only a log line. Registered 2026-08-15.
    "sp600":       lambda: fetch_sp600(),
    "sp1500":      lambda: fetch_sp1500(),
    "nasdaq100":   lambda: fetch_nasdaq100(),
    "themes":      lambda: fetch_themes(),
    "russell1000": lambda: fetch_russell1000(),
    "russell3000": lambda: fetch_russell3000(),
    "micro":       lambda: fetch_microcap(),
    "microcap":    lambda: fetch_microcap(),
    "etf":         lambda: fetch_etf_universe(),
    "etfs":        lambda: fetch_etf_universe(),
    "broad":       lambda: fetch_broad(),
}

# Late-bound via lambdas above so the _count_guarded wrappers installed at the
# bottom of this module are the ones actually called.
_KNOWN_COMPONENTS = frozenset(_COMPONENT_FETCHERS)


def _fetch_component(name: str) -> list[str]:
    fetchers = _COMPONENT_FETCHERS
    fn = fetchers.get(name)
    if fn is None:
        log.warning("universe: unknown component '%s' — skipping", name)
        return []
    try:
        return fn()
    except Exception as exc:
        log.warning("universe: component '%s' failed (%s) — skipping", name, exc)
        return []


def load_universe(mode: str | None = None) -> list[str]:
    """Resolve the active universe.

    Priority:
    1. `mode` argument (explicit caller choice)
    2. SEPA_UNIVERSE_FILE env var (path to one-ticker-per-line text file)
    3. SEPA_UNIVERSE env var (comma-separated literal)
    4. SEPA_UNIVERSE_MODE env var (one of: curated / sp500 / russell1000 /
       russell3000 / broad / all_us / expanded)
    5. Default: curated

    `broad` = Russell 3000 ∪ micro-caps (IWC, if present) ∪ broad ETF list —
    the widest net, equities + ETFs together.

    Always preserves dedup + insertion order. Always appends benchmarks
    (SPY/QQQ/IWM) so RS math has anchors.
    """
    file_path = os.getenv("SEPA_UNIVERSE_FILE")
    if file_path and Path(file_path).exists():
        syms = [ln.strip().upper() for ln in Path(file_path).read_text().splitlines() if ln.strip()]
        return _with_benchmarks(syms)

    env = os.getenv("SEPA_UNIVERSE")
    if env:
        syms = [s.strip().upper() for s in env.split(",") if s.strip()]
        return _with_benchmarks(syms)

    selected = (mode or os.getenv("SEPA_UNIVERSE_MODE") or "curated").lower()

    # Multi-select: a comma-separated list of components (e.g.
    # "russell3000,etf,micro"). Union each + dedup so overlaps are removed.
    # The frontend already strips subset-covered components, but the set
    # union here makes dedup correct regardless of what's sent.
    if "," in selected:
        combined: list[str] = []
        seen_parts: set[str] = set()
        for part in (p.strip() for p in selected.split(",")):
            if part and part not in seen_parts:
                seen_parts.add(part)
                combined.extend(_fetch_component(part))
        log.info("universe: multi-select [%s] -> %d unique (pre-benchmark)",
                 selected, len(dict.fromkeys(combined)))
        return _with_benchmarks(combined)

    # sp500 / russell1000 / russell3000 / broad used to have their own explicit
    # branches here, duplicating _COMPONENT_FETCHERS. That duplication IS the
    # bug this function shipped: the branch list and the component map drifted,
    # and every key present in one but not the other (sp1500, sp400, sp600,
    # nasdaq100, themes) fell through to curated. One map now, one lookup.
    if selected in ("russell3000_etf", "max"):
        # Widest net — Russell 3000 ∪ micro-caps ∪ broad ETF list. SEPA's
        # liquidity gate handles the small-cap / thin-ETF noise floor.
        selected = "broad"
    if selected == "all_us":
        # All active US common stocks via Massive (~5,300 names). Scans
        # take 8-10 minutes with the bulk-snapshot pre-warm — SEPA's
        # built-in liquidity gate handles the small-cap noise floor.
        return _with_benchmarks(fetch_massive_universe())
    if selected == "expanded":
        # Curated ∪ S&P 500 (curated wins on ordering)
        merged = list(dict.fromkeys(list(UNIVERSE) + fetch_sp500()))
        return _with_benchmarks(merged)

    # Named aliases that expand to a component set. `sp1500_plus` is the Chart
    # Maps and demand-reentry default, and it MUST include the themes — the
    # whole reason the rosters exist is that the S&P tiers structurally cannot
    # hold them.
    if selected in _UNIVERSE_ALIASES:
        parts = _UNIVERSE_ALIASES[selected]
        combined = []
        for part in parts:
            combined.extend(_fetch_component(part))
        log.info("universe: alias %s -> [%s] -> %d unique (pre-benchmark)",
                 selected, ",".join(parts), len(dict.fromkeys(combined)))
        return _with_benchmarks(combined)

    # Any single component name we actually know how to fetch. Before
    # 2026-08-16 this branch did not exist: `sp1500`, `sp400`, `sp600`,
    # `nasdaq100` and `themes` all fell through to the curated 158 SILENTLY,
    # identical to what a garbage key returned, so /supply-demand ran a
    # 158-name scan while its own UI said "S&P 1500".
    if selected in _KNOWN_COMPONENTS:
        return _with_benchmarks(_fetch_component(selected))

    if selected != "curated":
        log.error("universe: unknown mode %r — falling back to the curated %d "
                  "names. This is NOT the universe that was asked for.",
                  selected, len(UNIVERSE))
    return _with_benchmarks(list(dict.fromkeys(UNIVERSE)))


def _with_benchmarks(syms: list[str]) -> list[str]:
    """Append SPY/QQQ/IWM if not already in the list (for RS math)."""
    out = list(dict.fromkeys(syms))
    for b in ("SPY", "QQQ", "IWM"):
        if b not in out:
            out.append(b)
    return out


# ---------------------------------------------------------------------------
# Size guards, installed last so every fetcher is defined.
#
# Ajay 2026-08-16: "add a count checks for returned values for all the tickers
# API like Russel 3000 and S&P 500 as well."
#
# `_count_ok` already guarded the four lists that route through
# `_resolve_with_fallbacks`. Everything else — Russell 1000/3000, sp1500,
# microcap, ETFs, broad — had bespoke cache/fallback chains with up to six exit
# points each and no check on any of them. Wrapping by name covers every path,
# including the stale-cache and clean-fallback returns that are exactly where a
# list quietly becomes a different universe.
# ---------------------------------------------------------------------------
fetch_sp500 = _count_guarded("sp500", fetch_sp500)
fetch_sp400 = _count_guarded("sp400", fetch_sp400)
fetch_sp600 = _count_guarded("sp600", fetch_sp600)
fetch_nasdaq100 = _count_guarded("nasdaq100", fetch_nasdaq100)
fetch_sp1500 = _count_guarded("sp1500", fetch_sp1500)
fetch_russell1000 = _count_guarded("russell1000", fetch_russell1000)
fetch_russell3000 = _count_guarded("russell3000", fetch_russell3000)
fetch_microcap = _count_guarded("microcap", fetch_microcap)
fetch_etf_universe = _count_guarded("etf", fetch_etf_universe)
fetch_themes = _count_guarded("themes", fetch_themes)
fetch_broad = _count_guarded("broad", fetch_broad)
fetch_massive_universe = _count_guarded("massive", fetch_massive_universe)


BENCHMARK = "SPY"
