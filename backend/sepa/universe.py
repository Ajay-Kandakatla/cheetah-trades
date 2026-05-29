"""Scanning universe — tickers we run SEPA against.

Three modes, selected via the `SEPA_UNIVERSE_MODE` env var or argument:

  - "curated"  (default) — the hand-picked ~130-name list below. Fast scans,
                           biased toward growth-friendly sectors.
  - "sp500"    — full S&P 500 (~500 names) fetched from Wikipedia and cached
                 30 days under ~/.cheetah/universe/sp500.txt.
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
    "CRDO", "ALAB", "ANET", "CRWV", "NBIS",
    # Software / cloud
    "CRM", "NOW", "SNOW", "DDOG", "NET", "CRWD", "PANW", "ZS", "MDB", "PLTR",
    "SHOP", "TEAM", "WDAY", "HUBS", "TOST",
    # Removed 2026-05-29 — dead in live yfinance + Yahoo Finance:
    #   CFLT  (Confluent — verify status; remove unless renamed)
    #   SMAR  (Smartsheet — taken private by Vista / Blackstone Q1 2025)
    # Consumer growth
    "ABNB", "UBER", "DASH", "BKNG", "CMG", "LULU", "DECK", "COST", "WMT",
    # Health / biotech leaders
    "LLY", "UNH", "ISRG", "VRTX", "REGN", "BMRN", "RMD", "BSX",
    # Fintech / payments
    # Note: SQ → XYZ (Block Inc rebrand January 2025).
    "V", "MA", "PYPL", "AXP", "COIN", "HOOD", "XYZ", "SOFI", "NU", "MELI",
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

    api_key = os.getenv("MASSIVE_API_KEY")
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


def fetch_russell1000() -> list[str]:
    """Return Russell 1000 components, cached 30 days.

    Primary source: iShares IWB ETF holdings CSV. As of 2026-05, iShares
    has begun serving HTML landing pages instead of CSV for some download
    URLs — when that happens we fall back to ``fetch_massive_universe(1000)``
    which returns the first 1000 active US common stocks (alphabetical).
    Not strictly the Russell 1000 by market cap, but a comparable
    institutional-quality universe slice.
    """
    cached = _read_cached("russell1000")
    if cached:
        return cached
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
        log.warning("universe: Russell 1000 fetch failed (%s) — trying Massive fallback", exc)
        # NOTE: Massive's /v3/reference/tickers endpoint returns tickers in
        # ALPHABETICAL order, not by market cap. A naive `limit=1000` would
        # give us only A→C tickers (~1000 names) and silently drop every
        # leader from D onwards (DASH, META, MU, NVDA, NFLX, ORCL, PLTR,
        # SMCI, TSLA, etc.). To prevent that, we ALWAYS prepend the curated
        # leader list (~130 mega/large-caps) and grab the next ~2000
        # alphabetical from Massive on top.
        massive = fetch_massive_universe(limit=2000)
        if massive:
            merged = list(dict.fromkeys(list(UNIVERSE) + massive))
            log.info("universe: russell1000 via curated+Massive = %d names "
                     "(%d curated + %d Massive, deduped)",
                     len(merged), len(UNIVERSE), len(massive))
            return merged
        log.warning("universe: Massive fallback also empty — using S&P 500")
        return fetch_sp500()


def fetch_russell3000() -> list[str]:
    """Return Russell 3000 components, cached 30 days.

    Source: iShares IWV ETF holdings CSV — the canonical source for the
    full Russell 3000 universe. Mirrors fetch_russell1000() exactly,
    including the dynamic-header parse and the _normalize_ishares_ticker
    cleanup pipeline (class-share remap + futures/junk filter).
    """
    cached = _read_cached("russell3000")
    if cached:
        return cached
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
        log.warning("universe: Russell 3000 fetch failed (%s) — trying Massive fallback", exc)
        # Same alphabetical-cutoff guard as fetch_russell1000() — prepend
        # the curated leader list so we never lose mega/large-caps.
        massive = fetch_massive_universe(limit=5000)
        if massive:
            merged = list(dict.fromkeys(list(UNIVERSE) + massive))
            log.info("universe: russell3000 via curated+Massive = %d names", len(merged))
            return merged
        log.warning("universe: Massive fallback also empty — using Russell 1000")
        return fetch_russell1000()


def load_universe(mode: str | None = None) -> list[str]:
    """Resolve the active universe.

    Priority:
    1. `mode` argument (explicit caller choice)
    2. SEPA_UNIVERSE_FILE env var (path to one-ticker-per-line text file)
    3. SEPA_UNIVERSE env var (comma-separated literal)
    4. SEPA_UNIVERSE_MODE env var (one of: curated / sp500 / russell1000 / russell3000 / expanded)
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
    if selected == "russell3000":
        return _with_benchmarks(fetch_russell3000())
    if selected == "all_us":
        # All active US common stocks via Massive (~5,300 names). Scans
        # take 8-10 minutes with the bulk-snapshot pre-warm — SEPA's
        # built-in liquidity gate handles the small-cap noise floor.
        return _with_benchmarks(fetch_massive_universe())
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
