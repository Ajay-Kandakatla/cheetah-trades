import { useCallback, useEffect, useMemo, useState } from 'react';
import { InfoButton } from '../components/InfoButton';
import { ChatterIndiaPanel } from '../components/ChatterIndiaPanel';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type IndiaRow = {
  symbol: string;
  company_name: string | null;
  mentions_7d: number | null;
  mentions_prior_7d: number | null;
  mention_velocity: number | null;
  engagement: number | null;
  vp_topics: number | null;
  mc_articles: number | null;
  momentum_label: 'ramping' | 'steady' | 'fading' | 'quiet' | null;
  fetched_at: number | null;
  stale: boolean;
};

type IndiaPayload = {
  generated_at: number;
  generated_at_iso: string;
  n_total: number;
  n_cached: number;
  n_fetched: number;
  n_stale: number;
  rows: IndiaRow[];
};

const PageInfo = (
  <>
    <p>
      <strong>Indian Stock Chatter</strong> — crowd discussion across India-native
      portals, ranked by engagement and mention velocity. Universe is the
      Nifty 50 (hardcoded — see <code>india_universe.py</code>).
    </p>
    <ul>
      <li>
        <strong>Reddit · India</strong> — r/IndianStockMarket,
        r/IndiaInvestments, r/NSEbets, r/StockMarketIndia, r/DalalStreetTalks.
        Searches both the bare ticker and the full company name (Indian retail
        uses both interchangeably).
      </li>
      <li>
        <strong>ValuePickr</strong> — high-quality value-investor forum
        (forum.valuepickr.com) using their Discourse JSON search. Long-form
        research and bull/bear theses.
      </li>
      <li>
        <strong>MoneyControl News</strong> — most-iconic Indian retail news
        source, scraped from the per-stock tag page. Catches catalyst stories
        (earnings, M&amp;A, regulatory) that move Indian stocks.
      </li>
    </ul>
    <p>
      <strong>Engagement</strong> = ValuePickr likes + posts (×5 weight) plus
      top Reddit upvotes. <strong>Velocity</strong> = mentions last 7 days ÷
      mentions the prior 7 days.
    </p>
    <p>
      <em>No StockTwits or Hacker News here — both are US-centric and rarely
      mention NSE tickers. India gets its own native lanes instead.</em>
    </p>
  </>
);

function fmt(v: number | null | undefined): string {
  if (v == null) return '—';
  return String(v);
}

function velocityClass(v: number | null | undefined): string {
  if (v == null) return 'cm-velocity cm-velocity--na';
  if (v >= 1.5) return 'cm-velocity cm-velocity--ramp';
  if (v <= 0.6) return 'cm-velocity cm-velocity--fade';
  return 'cm-velocity cm-velocity--steady';
}

function labelClass(label: string | null | undefined): string {
  if (!label) return 'cm-mom cm-mom--na';
  return `cm-mom cm-mom--${label}`;
}

export function ChatterIndiaPage() {
  const [data, setData] = useState<IndiaPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [maxFetch, setMaxFetch] = useState(12);
  const [hideQuiet, setHideQuiet] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ max_fetch: String(maxFetch) });
      const r = await fetch(`${API}/sepa/chatter-in?${params.toString()}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const j: IndiaPayload = await r.json();
      setData(j);
      setError(null);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [maxFetch]);

  useEffect(() => {
    if (!selected) load();
  }, [load, selected]);

  const display = useMemo(() => {
    if (!data?.rows) return [];
    if (!hideQuiet) return data.rows;
    return data.rows.filter((r) => r.momentum_label && r.momentum_label !== 'quiet');
  }, [data, hideQuiet]);

  // If a row is selected, show the per-ticker panel
  if (selected) {
    return (
      <div className="sepa-page dm-page">
        <ChatterIndiaPanel symbol={selected} onClose={() => setSelected(null)} />
      </div>
    );
  }

  return (
    <div className="sepa-page dm-page">
      <div className="sepa-page__title">
        <InfoButton title="Indian Stock Chatter">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ 08 — Crowd Signal · India</div>
          <h1 className="display sepa-page__h1">Chatter · India</h1>
          <p className="lede">
            Reddit India · ValuePickr · MoneyControl, ranked across the
            Nifty 50 by engagement and mention velocity.
          </p>
        </div>
      </div>

      <section className="dm-controls">
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

      {data && (
        <section className="dm-results">
          <div className="dm-results__head">
            <div className="eyebrow">
              {data.n_total} tickers · {data.n_cached} cached · {data.n_fetched} fetched · {data.n_stale} stale
            </div>
            <div className="dm-results__sub mono">
              cap {maxFetch} live · 15-min cache · click row to drill in
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
                  <th className="num">Engagement</th>
                  <th className="num">VP topics</th>
                  <th className="num">MC articles</th>
                </tr>
              </thead>
              <tbody>
                {display.map((row, idx) => (
                  <tr
                    key={row.symbol}
                    className={`dm-row ${row.stale ? 'dm-row--stale' : ''}`}
                    onClick={() => setSelected(row.symbol)}
                  >
                    <td className="mono">{idx + 1}</td>
                    <td className="mono dm-sym"><strong>{row.symbol}</strong></td>
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
                    <td className="num mono">
                      {row.engagement == null ? '—' : row.engagement.toLocaleString()}
                    </td>
                    <td className="num mono">{fmt(row.vp_topics)}</td>
                    <td className="num mono">{fmt(row.mc_articles)}</td>
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
