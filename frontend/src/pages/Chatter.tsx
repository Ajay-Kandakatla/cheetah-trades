import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type ChatterRow = {
  symbol: string;
  company_name?: string | null;
  mentions_7d: number | null;
  mentions_prior_7d: number | null;
  mention_velocity: number | null;
  sentiment_ratio: number | null;
  stocktwits_bullish: number | null;
  stocktwits_bearish: number | null;
  hn_stories: number | null;
  momentum_label: 'ramping' | 'steady' | 'fading' | 'quiet' | null;
  fetched_at: number | null;
  stale: boolean;
};

type ChatterPayload = {
  generated_at: number;
  generated_at_iso: string;
  n_total: number;
  n_cached: number;
  n_fetched: number;
  n_stale: number;
  rows: ChatterRow[];
  error?: string;
  message?: string;
};

const PageInfo = (
  <>
    <p>
      <strong>Forum Chatter</strong> aggregates crowd discussion for every
      stock in the latest SEPA scan, across four lanes:
    </p>
    <ul>
      <li>
        <strong>Reddit · Thoughtful</strong> — r/SecurityAnalysis, r/ValueInvesting,
        r/investing, r/stocks, r/options. Catches bear theses and quality concerns.
      </li>
      <li>
        <strong>Reddit · Momentum</strong> — r/wallstreetbets, r/StockMarket,
        r/pennystocks, r/Daytrading, r/swingtrading. Leading indicator for retail
        flow into Stage-2 leaders.
      </li>
      <li>
        <strong>StockTwits</strong> — Bullish vs Bearish user-tagged messages
        from the public stream. Ratio = bullish / (bullish + bearish).
      </li>
      <li>
        <strong>Hacker News</strong> — last 30 days, story-tagged, ticker or
        company-name match. Catches catalyst news for tech megacaps.
      </li>
    </ul>
    <p>
      <strong>Mention velocity</strong> = posts last 7 days ÷ posts the prior
      7 days. <strong>Ramping</strong> means velocity ≥ 1.5 with at least 3
      posts this week. <strong>Quiet</strong> means no posts and no StockTwits
      messages. Universe is the top-N by SEPA composite score from the most
      recent scan.
    </p>
    <p>
      <em>Reddit free-tier rate limits cap live fetches per call to keep your
      API quota safe — anything beyond is shown as "stale" until next refresh.</em>
    </p>
  </>
);

function fmt(v: number | null | undefined, suffix = ''): string {
  if (v == null) return '—';
  return `${v}${suffix}`;
}

function velocityClass(v: number | null | undefined): string {
  if (v == null) return 'cm-velocity cm-velocity--na';
  if (v >= 1.5) return 'cm-velocity cm-velocity--ramp';
  if (v <= 0.6) return 'cm-velocity cm-velocity--fade';
  return 'cm-velocity cm-velocity--steady';
}

function sentimentClass(r: number | null | undefined): string {
  if (r == null) return 'cm-sent cm-sent--na';
  if (r >= 0.65) return 'cm-sent cm-sent--bull';
  if (r <= 0.35) return 'cm-sent cm-sent--bear';
  return 'cm-sent cm-sent--mixed';
}

function labelClass(label: string | null | undefined): string {
  if (!label) return 'cm-mom cm-mom--na';
  return `cm-mom cm-mom--${label}`;
}

export function ChatterPage() {
  const navigate = useNavigate();
  const [data, setData] = useState<ChatterPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [topN, setTopN] = useState(20);
  const [maxFetch, setMaxFetch] = useState(12);
  const [hideQuiet, setHideQuiet] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        top_n: String(topN),
        max_fetch: String(maxFetch),
      });
      const r = await fetch(`${API}/sepa/chatter?${params.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: ChatterPayload = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [topN, maxFetch]);

  useEffect(() => {
    load();
  }, [load]);

  const display = useMemo(() => {
    if (!data?.rows) return [];
    if (!hideQuiet) return data.rows;
    return data.rows.filter((r) => r.momentum_label && r.momentum_label !== 'quiet');
  }, [data, hideQuiet]);

  const noScan = data?.error === 'no_scan';

  return (
    <div className="sepa-page dm-page">
      <div className="sepa-page__title">
        <InfoButton title="Forum Chatter">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 07 — Crowd Signal</div>
          <h1 className="display sepa-page__h1">Forum Chatter</h1>
          <p className="lede">
            Reddit · StockTwits · Hacker News, ranked by mention velocity.
            Reuses the latest SEPA scan universe.
          </p>
        </div>
      </div>

      {/* Controls */}
      <section className="dm-controls">
        <label>
          <span className="eyebrow">Top N (universe)</span>
          <select value={topN} onChange={(e) => setTopN(Number(e.target.value))}>
            {[10, 20, 30, 50, 100].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label>
          <span className="eyebrow">Max live fetches</span>
          <select value={maxFetch} onChange={(e) => setMaxFetch(Number(e.target.value))}>
            {[0, 6, 12, 20, 30].map((n) => (
              <option key={n} value={n}>{n}</option>
            ))}
          </select>
        </label>
        <label className="dm-controls__toggle">
          <input
            type="checkbox"
            checked={hideQuiet}
            onChange={(e) => setHideQuiet(e.target.checked)}
          />
          <span>Hide quiet tickers</span>
        </label>
        <button type="button" className="dm-refresh" onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </section>

      {error && (
        <div className="sepa-empty-card">
          <div className="eyebrow">Error</div>
          <p>{error}</p>
        </div>
      )}

      {noScan && (
        <div className="sepa-empty-card">
          <div className="eyebrow">No scan data</div>
          <p>
            Forum Chatter reuses the latest <code>/sepa/scan</code> for its
            universe. Open the <strong>SEPA</strong> tab and click{' '}
            <strong>Scan</strong> first.
          </p>
        </div>
      )}

      {!noScan && data && (
        <section className="dm-results">
          <div className="dm-results__head">
            <div className="eyebrow">
              {data.n_total} tickers · {data.n_cached} cached · {data.n_fetched} fetched · {data.n_stale} stale
            </div>
            <div className="dm-results__sub mono">
              cap {maxFetch} live · 15-min cache
            </div>
          </div>

          <div className="dm-table-wrap">
            <table className="dm-table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>Symbol</th>
                  <th>Company</th>
                  <th>Momentum</th>
                  <th className="num">Mentions 7d</th>
                  <th className="num">Prior 7d</th>
                  <th className="num">Velocity</th>
                  <th className="num">Sentiment</th>
                  <th className="num">ST · Bull/Bear</th>
                  <th className="num">HN</th>
                </tr>
              </thead>
              <tbody>
                {display.map((row, idx) => (
                  <tr
                    key={row.symbol}
                    className={`dm-row ${row.stale ? 'dm-row--stale' : ''}`}
                    onClick={() => navigate(`/sepa/${encodeURIComponent(row.symbol)}`)}
                  >
                    <td className="mono">{idx + 1}</td>
                    <td className="mono dm-sym">
                      <strong>{row.symbol}</strong>
                    </td>
                    <td className="dm-name" title={row.company_name ?? ''}>
                      {row.company_name ?? '—'}
                    </td>
                    <td>
                      {row.stale ? (
                        <span className="cm-mom cm-mom--stale" title="Cache miss — refresh to fetch">stale</span>
                      ) : (
                        <span className={labelClass(row.momentum_label)}>
                          {row.momentum_label ?? '—'}
                        </span>
                      )}
                    </td>
                    <td className="num mono">{fmt(row.mentions_7d)}</td>
                    <td className="num mono">{fmt(row.mentions_prior_7d)}</td>
                    <td className={`num ${velocityClass(row.mention_velocity)}`}>
                      {row.mention_velocity == null ? '—' : `${row.mention_velocity}×`}
                    </td>
                    <td className={`num ${sentimentClass(row.sentiment_ratio)}`}>
                      {row.sentiment_ratio == null ? '—' : `${Math.round(row.sentiment_ratio * 100)}%`}
                    </td>
                    <td className="num mono">
                      {row.stocktwits_bullish == null
                        ? '—'
                        : `${row.stocktwits_bullish}/${row.stocktwits_bearish}`}
                    </td>
                    <td className="num mono">{fmt(row.hn_stories)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {display.length === 0 && (
            <div className="sepa-empty-card">
              <div className="eyebrow">No rows</div>
              <p>
                Nothing to show.
                {hideQuiet && ' Uncheck "Hide quiet tickers" — most names may be quiet on first run.'}
                {!hideQuiet && ' Bump max-live-fetches and refresh to populate the cache.'}
              </p>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
