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


def fetch_sp400() -> list[str]:
    """Return S&P 400 MidCap components, cached 30 days.

    Mirror of fetch_sp500 against Wikipedia's S&P 400 list. These names are
    almost all already inside the Russell 3000, so this is belt-and-suspenders
    coverage — it just guarantees mid-caps even if the iShares snapshot is
    stale. Returns [] (not curated) on failure so it can't pollute a union
    with large-caps. Also referenced by the russell* network fallback paths
    (previously called but never defined — a latent NameError).
    """
    cached = _read_cached("sp400")
    if cached:
        return cached
    try:
        import pandas as pd
        tables = pd.read_html(
            "https://en.wikipedia.org/wiki/List_of_S%26P_400_companies"
        )
        # Find the table that actually has a Symbol/Ticker column — the
        # constituents table isn't always tables[0] on this page.
        syms: list[str] = []
        for tb in tables:
            col = next((c for c in tb.columns if str(c).lower() in ("symbol", "ticker")), None)
            if col is not None:
                syms = [str(s).replace(".", "-").upper() for s in tb[col].tolist()]
                break
        seen, out = set(), []
        for s in syms:
            if s and s != "NAN" and s not in seen:
                seen.add(s)
                out.append(s)
        if out:
            _write_cached("sp400", out)
            log.info("universe: fetched %d S&P 400 MidCap components", len(out))
        return out
    except Exception as exc:
        log.warning("universe: S&P 400 fetch failed (%s) — skipping mid-cap layer", exc)
        return []


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
    equities = fetch_russell3000()
    micro = fetch_microcap()
    etfs = fetch_etf_universe()
    merged = list(dict.fromkeys(
        curated + sp500 + sp400 + equities + micro + etfs
    ))
    log.info(
        "universe: broad mode = %d curated + %d sp500 + %d sp400 + %d R3000 "
        "+ %d micro + %d ETF -> %d unique",
        len(curated), len(sp500), len(sp400), len(equities), len(micro),
        len(etfs), len(merged),
    )
    return merged


# Orthogonal universe building blocks → fetcher. Used by the multi-select
# path in load_universe: the user picks any combination and we union + dedup
# (overlaps removed). Defined here, after every fetcher, so the direct
# function references resolve.
def _fetch_component(name: str) -> list[str]:
    fetchers = {
        "curated":     lambda: list(UNIVERSE),
        "sp500":       fetch_sp500,
        "sp400":       fetch_sp400,
        "russell1000": fetch_russell1000,
        "russell3000": fetch_russell3000,
        "micro":       fetch_microcap,
        "microcap":    fetch_microcap,
        "etf":         fetch_etf_universe,
        "etfs":        fetch_etf_universe,
    }
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

    if selected == "sp500":
        return _with_benchmarks(fetch_sp500())
    if selected == "russell1000":
        return _with_benchmarks(fetch_russell1000())
    if selected == "russell3000":
        return _with_benchmarks(fetch_russell3000())
    if selected in ("broad", "russell3000_etf", "max"):
        # Russell 3000 ∪ micro-caps (IWC if present) ∪ broad ETF list.
        # The widest net — equities + ETFs together. SEPA's liquidity gate
        # handles the small-cap / thin-ETF noise floor downstream.
        return _with_benchmarks(fetch_broad())
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
