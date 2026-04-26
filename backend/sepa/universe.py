"""Scanning universe — tickers we run SEPA against.

Three modes, selected via the `SEPA_UNIVERSE_MODE` env var or argument:

  - "curated"  (default) — the hand-picked ~130-name list below. Fast scans,
                           biased toward growth-friendly sectors.
  - "sp500"    — full S&P 500 (~500 names) fetched from Wikipedia and cached
                 30 days under ~/.cheetah/universe/sp500.txt.
  - "russell1000" — Russell 1000 holdings (~1000 names) fetched from iShares
                    IWB ETF holdings CSV. Cached 30 days.
  - "expanded" — curated ∪ sp500 union (deduped).

You can also point SEPA_UNIVERSE_FILE at any text file (one ticker per line)
or set SEPA_UNIVERSE to a comma-separated override.
"""
from __future__ import annotations

import logging
import os
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
    "CRDO", "ALAB", "ANET", "CRWV", "NEBIUS",
    # Software / cloud
    "CRM", "NOW", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "MDB", "PLTR",
    "SHOP", "TEAM", "WDAY", "HUBS", "CFLX", "SMAR", "TOST",
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
    # Small/mid momentum movers (edit freely)
    "RKLB", "ACHR", "JOBY", "SERV", "OKLO", "LUNR", "ASTS", "AEHR", "IONQ",
    "RGTI", "QBTS", "BBAI", "SOUN", "TEM", "HIMS", "DUOL", "RBLX", "DKNG",
    "SPOT", "RDDT", "APP", "APPN", "PATH", "BILL", "DOCN",
    # Anchor / benchmarks (not traded but used for RS math)
    "SPY", "QQQ", "IWM",
]


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


def _write_cached(name: str, syms: list[str]) -> None:
    _cache_path(name).write_text("\n".join(syms))


def fetch_sp500() -> list[str]:
    """Return S&P 500 components, cached 30 days.

    Source: Wikipedia's `List_of_S%26P_500_companies` article, which exposes a
    plain HTML table that pandas.read_html can parse.
    """
    cached = _read_cached("sp500")
    if cached:
        return cached
    try:
        import pandas as pd
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        )
        syms = [str(s).replace(".", "-").upper() for s in tables[0]["Symbol"].tolist()]
        # de-dup and drop blanks
        seen, out = set(), []
        for s in syms:
            if s and s not in seen:
                seen.add(s)
                out.append(s)
        _write_cached("sp500", out)
        log.info("universe: fetched %d S&P 500 components", len(out))
        return out
    except Exception as exc:
        log.warning("universe: S&P 500 fetch failed (%s) — falling back to curated", exc)
        return list(UNIVERSE)


def fetch_russell1000() -> list[str]:
    """Return Russell 1000 components, cached 30 days.

    Source: iShares IWB ETF holdings CSV — the most reliable public list of
    Russell 1000 components without paid data.
    """
    cached = _read_cached("russell1000")
    if cached:
        return cached
    try:
        import pandas as pd
        url = (
            "https://www.ishares.com/us/products/239707/ishares-russell-1000-etf/"
            "1467271812596.ajax?fileType=csv&fileName=IWB_holdings&dataType=fund"
        )
        df = pd.read_csv(url, skiprows=9)
        # iShares uses 'Ticker' column; equities only (drop CASH, TBills)
        syms = [str(s).strip().upper() for s in df["Ticker"].tolist()
                if isinstance(s, str) and s.strip() and s.strip() not in {"-", "CASH"}]
        # Dedup, dot-to-dash for tickers like BRK.B → BRK-B (yfinance convention)
        syms = [s.replace(".", "-") for s in syms]
        seen, out = set(), []
        for s in syms:
            if s not in seen:
                seen.add(s)
                out.append(s)
        _write_cached("russell1000", out)
        log.info("universe: fetched %d Russell 1000 components", len(out))
        return out
    except Exception as exc:
        log.warning("universe: Russell 1000 fetch failed (%s) — falling back to S&P 500", exc)
        return fetch_sp500()


def load_universe(mode: str | None = None) -> list[str]:
    """Resolve the active universe.

    Priority:
    1. `mode` argument (explicit caller choice)
    2. SEPA_UNIVERSE_FILE env var (path to one-ticker-per-line text file)
    3. SEPA_UNIVERSE env var (comma-separated literal)
    4. SEPA_UNIVERSE_MODE env var (one of: curated / sp500 / russell1000 / expanded)
    5. Default: curated

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

    if selected == "sp500":
        return _with_benchmarks(fetch_sp500())
    if selected == "russell1000":
        return _with_benchmarks(fetch_russell1000())
    if selected == "expanded":
        # Curated ∪ S&P 500 (curated wins on ordering)
        merged = list(dict.fromkeys(list(UNIVERSE) + fetch_sp500()))
        return _with_benchmarks(merged)
    return _with_benchmarks(list(dict.fromkeys(UNIVERSE)))


def _with_benchmarks(syms: list[str]) -> list[str]:
    """Append SPY/QQQ/IWM if not already in the list (for RS math)."""
    out = list(dict.fromkeys(syms))
    for b in ("SPY", "QQQ", "IWM"):
        if b not in out:
            out.append(b)
    return out


BENCHMARK = "SPY"
