import { useEffect, useMemo, useState } from 'react';
import { useMarketStream } from '../hooks/useMarketStream';
import { useCheetahStocks } from '../hooks/useCheetahStocks';
import { useSepaScan } from '../hooks/useSepa';
import { QuoteRow } from '../components/QuoteRow';
import { WatchlistSection } from '../components/WatchlistSection';
import { StockDetailModal } from '../components/StockDetailModal';
import { SymbolSearch } from '../components/SymbolSearch';
import { OnDemandSepaModal } from '../components/OnDemandSepaModal';
import { MarketGaugeBanner } from '../components/MarketGaugeBanner';
import { WATCHLIST } from '../data/watchlist';

// Hardcoded fallback used only when no SEPA scan exists yet.
const FALLBACK_WATCHLIST = ['NVDA', 'META', 'AAPL', 'MSFT', 'TSLA', 'AMD', 'PLTR', 'CRDO'];
const SEPA_TOP_N = 20;
const STORAGE_KEY = 'live_symbols_v1';

const STATUS_LABEL: Record<string, string> = {
  connecting: 'Connecting',
  open: 'Live',
  closed: 'Closed',
  error: 'Offline',
};

export function LiveStream() {
  // Symbols persisted across reloads. On first visit (no localStorage), we
  // seed with the top N SEPA tickers by composite score. Subsequent visits
  // remember whatever tweaks the user made (added/removed names).
  const [symbols, setSymbols] = useState<string[]>(() => {
    if (typeof window === 'undefined') return FALLBACK_WATCHLIST;
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch {}
    return FALLBACK_WATCHLIST;
  });
  const [seededFromSepa, setSeededFromSepa] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const [sepaTarget, setSepaTarget] = useState<{ symbol: string; name?: string } | null>(null);
  const { quotes, status } = useMarketStream(symbols);
  const { stocks: cheetahStocks } = useCheetahStocks();
  const { data: sepaData } = useSepaScan();

  // Persist symbols to localStorage on every change so next visit restores them.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(symbols)); } catch {}
  }, [symbols]);

  // First-time seeding: if the user has never customized the live list AND
  // a SEPA scan has results, swap in the top N by composite score. Stops
  // running once seeded so subsequent SEPA scans don't trample the user's
  // additions/removals.
  useEffect(() => {
    if (seededFromSepa) return;
    if (typeof window === 'undefined') return;
    const userHasCustomList = !!localStorage.getItem(STORAGE_KEY);
    if (userHasCustomList) {
      setSeededFromSepa(true);
      return;
    }
    const rows = sepaData?.all_results;
    if (!rows || rows.length === 0) return;
    const top = [...rows]
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, SEPA_TOP_N)
      .map((r) => r.symbol);
    if (top.length > 0) {
      setSymbols(top);
      setSeededFromSepa(true);
    }
  }, [sepaData, seededFromSepa]);

  /** Replace the live symbols with the top N from the latest SEPA scan. */
  const reloadFromSepa = (n = SEPA_TOP_N) => {
    const rows = sepaData?.all_results;
    if (!rows || rows.length === 0) {
      // eslint-disable-next-line no-alert
      alert('No SEPA scan data yet. Run a scan from the SEPA tab first.');
      return;
    }
    const top = [...rows]
      .sort((a, b) => (b.score ?? 0) - (a.score ?? 0))
      .slice(0, n)
      .map((r) => r.symbol);
    setSymbols(top);
  };

  const scoreLookup = useMemo(() => {
    const map: Record<string, number> = {};
    cheetahStocks?.forEach((s) => {
      map[s.ticker] = s.score;
    });
    return map;
  }, [cheetahStocks]);

  // Company-name lookup for the ticker column. Three sources, in priority:
  //   1. SEPA scan results — has fresh names for every Russell 1000 ticker
  //   2. WATCHLIST static data — covers a curated set with hand-checked names
  //   3. cheetahStocks — fallback for niche tickers in that list
  // We never block on a name; if missing, the row just shows the bare ticker.
  const nameLookup = useMemo(() => {
    const map: Record<string, string> = {};
    sepaData?.all_results?.forEach((r: any) => {
      if (r?.symbol && r?.name) map[r.symbol] = r.name;
    });
    WATCHLIST.forEach((w) => {
      if (w.symbol && w.name && !map[w.symbol]) map[w.symbol] = w.name;
    });
    cheetahStocks?.forEach((s: any) => {
      if (s?.ticker && s?.name && !map[s.ticker]) map[s.ticker] = s.name;
    });
    return map;
  }, [sepaData, cheetahStocks]);

  const rows = useMemo(
    () => symbols.map((s) => quotes[s] ?? { symbol: s, ts: 0 }),
    [symbols, quotes],
  );

  // Pick the freshest tick across the whole table for the header timestamp.
  const newestTs = useMemo(
    () => Object.values(quotes).reduce((max, q) => Math.max(max, q.ts ?? 0), 0),
    [quotes],
  );
  const stalenessSec = newestTs ? Math.max(0, Math.floor(Date.now() / 1000 - newestTs)) : null;
  const stalenessLabel = (() => {
    if (stalenessSec == null) return null;
    if (stalenessSec < 5) return 'just now';
    if (stalenessSec < 60) return `${stalenessSec}s ago`;
    if (stalenessSec < 3600) return `${Math.round(stalenessSec / 60)}m ago`;
    return `${Math.round(stalenessSec / 3600)}h ago`;
  })();
  const anyStaleRow = useMemo(
    () => rows.some((r) => r.stale === true || r.source === 'sepa_cache'),
    [rows],
  );
  // When the live feed errors but we still have cached prices, downgrade
  // the badge from alarming red ERROR to neutral "Offline · last bar Xh ago".
  const effectiveStatus = (status === 'error' && newestTs > 0) ? 'closed' : status;

  const detailMeta = useMemo(
    () => (detail ? WATCHLIST.find((w) => w.symbol === detail) : undefined),
    [detail],
  );

  function addSymbol(sym: string) {
    const s = sym.trim().toUpperCase();
    if (!s) return;
    setSymbols((prev) => prev.includes(s) ? prev : [...prev, s]);
  }

  function removeSymbol(s: string) {
    setSymbols(symbols.filter((x) => x !== s));
  }

  return (
    <div className="cm-page cm-page--live">
      <MarketGaugeBanner />
      <header className="cm-pagehead">
        <div className="cm-pagehead__col">
          <div className="eyebrow">Live Feed</div>
          <h1 className="display cm-pagehead__title">Market Stream</h1>
          <p className="lede">
            Real-time quotes over Server-Sent Events. RSI, VWAP, and the
            sparkline trace are computed server-side — the canvas only renders
            what the pipeline delivers.
          </p>
        </div>

        <div className="cm-pagehead__aside">
          <div className={`cm-status cm-status--${effectiveStatus}`} role="status" aria-live="polite">
            <span className="cm-status__dot" aria-hidden="true" />
            <span className="cm-status__label">
              {STATUS_LABEL[effectiveStatus] ?? effectiveStatus.toUpperCase()}
            </span>
          </div>
          {stalenessLabel && (
            <div className="cm-status__sub mono" title={newestTs ? new Date(newestTs * 1000).toString() : undefined}>
              last update {stalenessLabel}
            </div>
          )}
          {anyStaleRow && (
            <div className="cm-status__sub cm-status__sub--warn">
              showing last bar — markets closed or feed offline
            </div>
          )}
        </div>
      </header>

      <section className="cm-live__controls">
        <div className="cm-live__form">
          <label className="eyebrow">Search any ticker</label>
          <SymbolSearch
            onAdd={(sym) => addSymbol(sym)}
            onAnalyze={(sym, name) => setSepaTarget({ symbol: sym, name })}
            placeholder="e.g. ASML, AVGO, TSLA — typeahead any US ticker"
          />
        </div>

        <div className="cm-live__sepa-actions">
          <span className="eyebrow">From SEPA</span>
          <div className="cm-live__sepa-btns">
            <button
              type="button"
              className="sepa-btn sepa-btn--ghost"
              onClick={() => reloadFromSepa(20)}
              disabled={!sepaData?.all_results?.length}
              title="Replace the live watchlist with the top 20 tickers from the most recent SEPA scan, ranked by composite score."
            >
              ↻ Top 20
            </button>
            <button
              type="button"
              className="sepa-btn sepa-btn--ghost"
              onClick={() => reloadFromSepa(50)}
              disabled={!sepaData?.all_results?.length}
              title="Top 50 from the latest SEPA scan."
            >
              ↻ Top 50
            </button>
            {sepaData?.candidate_count ? (
              <button
                type="button"
                className="sepa-btn sepa-btn--ghost"
                onClick={() => {
                  const cands = (sepaData.candidates ?? []).map((c: any) => c.symbol);
                  if (cands.length) setSymbols(cands);
                }}
                title="Load only stocks that passed every SEPA gate (Trend Template + RS≥70 + Stage 2 + tight base + entry setup + liquid)."
              >
                ↻ Candidates only ({sepaData.candidate_count})
              </button>
            ) : null}
          </div>
        </div>

        <div className="cm-live__count">
          <span className="eyebrow">Watching</span>
          <span className="mono">{symbols.length}</span>
        </div>
      </section>

      <div className="cm-live__table-wrap">
        <table className="cm-live__table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Price</th>
              <th>Day %</th>
              <th>RSI<sub>14</sub></th>
              <th>VWAP</th>
              <th>Trace</th>
              <th>Cheetah</th>
              <th>Open</th>
              <th>High</th>
              <th>Low</th>
              <th>Volume</th>
              <th>Feed</th>
              <th aria-label="Remove" />
            </tr>
          </thead>
          <tbody>
            {rows.map((q) => (
              <QuoteRow
                key={q.symbol}
                quote={q}
                cheetahScore={scoreLookup[q.symbol]}
                companyName={nameLookup[q.symbol]}
                onRemove={() => removeSymbol(q.symbol)}
                onSelect={() => setDetail(q.symbol)}
                onAnalyze={() => setSepaTarget({ symbol: q.symbol })}
              />
            ))}
          </tbody>
        </table>
      </div>

      <WatchlistSection onSelect={(sym) => setDetail(sym)} />

      <footer className="cm-disclaimer cm-disclaimer--footer">
        <span className="cm-disclaimer__label">Disclosure</span>
        <p>
          Educational and research tool. Finnhub's free tier is real-time for US
          equities during market hours and shows the last trade off-hours. RSI
          readings above 70 often signal overbought conditions and below 30
          oversold — not a buy or sell signal on their own. Not financial
          advice. Do not use for automated execution without verifying
          tick-by-tick accuracy against a licensed market-data vendor.
        </p>
      </footer>

      {detail && <StockDetailModal symbol={detail} meta={detailMeta} onClose={() => setDetail(null)} />}
      {sepaTarget && (
        <OnDemandSepaModal
          symbol={sepaTarget.symbol}
          name={sepaTarget.name}
          onClose={() => setSepaTarget(null)}
        />
      )}
    </div>
  );
}
