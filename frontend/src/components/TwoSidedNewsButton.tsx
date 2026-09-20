/* ⚖️ TwoSidedNewsButton — the bull case AND the bear case for one ticker.
 *
 * Ajay 2026-09-20: "I would like it to be in individual tickers" — the
 * two-sided read that already rides the 🔥 Hottest sector tiles, pointed at
 * the name whose page he is on. Sits beside 📰 "What's the news say?" on the
 * Catalyst tab: that button answers "more buyable / less / sell", this one
 * refuses to answer that and writes out both arguments instead.
 *
 * ON DEMAND ONLY. Nothing fetches until he clicks — the POST is the only call
 * that may reach the model, and it does so once per ET session date per name
 * (the backend serves the stored read back with `cached: true`). ↻ re-read
 * forces a fresh one.
 *
 * BOTH COLUMNS OR NEITHER. The backend refuses to return half a read
 * (`_usable`: both sides, 40+ characters each), and the two columns are the
 * same class so neither side can be given more room than the other. A bull
 * case laid out wider than its bear case is a recommendation with extra steps.
 *
 * EVERY NUMBER COMES FROM `facts`. The prose is rendered as prose and is never
 * parsed for numbers; the numeric block below it is built from the `facts`
 * object the backend computed. The model is told (rule 1 of the shared system
 * prompt) it may not state a number that is not in that block, and this file
 * is the reason that rule is checkable: what he reads as a number came off the
 * app's own research cache, the scan row and the earnings watch.
 *
 * NOT A SIGNAL. `read_by` names whichever model wrote it and the footer says
 * "not measured, not a signal" on every successful read.
 */
import { useState } from 'react';
import { API } from '../lib/apiBase';

type Headline = {
  title?: string | null; url?: string | null;
  source?: string | null; published?: number | string | null;
};

export type TwoSidedRead = {
  ok?: boolean;
  symbol?: string;
  date?: string | null;
  reason?: string | null;
  positive?: boolean;
  why_positive?: string | null;
  bull?: string | null;
  bear?: string | null;
  facts?: Record<string, unknown> | null;
  headlines?: Headline[];
  headline_count?: number | null;
  read_by?: string | null;
  measured?: boolean;
  window_hours?: number | null;
  cached?: boolean;
};

/* Labels for the facts block. A key with no label here still renders — the key
 * is shown as written rather than dropped, because a fact silently missing
 * from the block is a fact the reader cannot check the prose against. */
const FACT_LABEL: Record<string, string> = {
  symbol: 'Symbol',
  company: 'Company',
  last_close: 'Last close',
  sales_growth_yoy_pct: 'Sales growth YoY %',
  sales_prior_yoy_pct: 'Prior-quarter sales growth YoY %',
  sales_tier: 'Sales tier',
  sales_accelerating: 'Sales accelerating',
  eps_growth_yoy_pct: 'EPS growth YoY %',
  net_margin_pct: 'Net margin %',
  next_earnings: 'Next earnings',
  yoy_pair_comparable: 'Year-over-year pair is four quarters apart',
};

function factValue(v: unknown): string {
  if (typeof v === 'boolean') return v ? 'yes' : 'no';
  if (v === null || v === undefined || v === '') return '—';
  return String(v);
}

export function TwoSidedNewsButton({ symbol }: { symbol: string }) {
  const [data, setData] = useState<TwoSidedRead | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async (force = false) => {
    setLoading(true);
    setError(null);
    try {
      const r = await fetch(
        `${API}/news/two-sided/${encodeURIComponent(symbol)}${force ? '?force=true' : ''}`,
        { method: 'POST', credentials: 'include' },
      );
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      setData(await r.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const headlines = data?.headlines || [];

  return (
    <div className="tsn">
      {!data && !loading ? (
        <>
          <button type="button" className="sepa-btn sepa-btn--ghost tsn__cta"
                  data-testid="tsn-cta" onClick={() => void load()}>
            ⚖️ Bull / bear read
          </button>
          {error ? <p className="tsn__err mono">Couldn’t read the news: {error}</p> : null}
        </>
      ) : null}

      {loading ? (
        <div className="tsn__loading mono">⚖️ Writing both sides from today’s headlines…</div>
      ) : null}

      {data && !loading ? (
        <>
          {data.ok ? (
            <>
              <div className="tsn__cases" data-testid="tsn-cases">
                <div className="tsn__case" data-testid="tsn-bull">
                  <div className="tsn__case-head">Bull case</div>
                  <p className="tsn__case-body">{data.bull}</p>
                </div>
                <div className="tsn__case" data-testid="tsn-bear">
                  <div className="tsn__case-head">Bear case</div>
                  <p className="tsn__case-body">{data.bear}</p>
                </div>
              </div>
              {data.why_positive ? (
                <p className="tsn__why mono">
                  {data.positive ? 'Read as net favourable' : 'Read as not favourable'} — {data.why_positive}
                </p>
              ) : null}
            </>
          ) : (
            <div className="tsn__empty mono" data-testid="tsn-reason">
              {data.reason || 'No read today.'}
            </div>
          )}

          {data.facts && Object.keys(data.facts).length ? (
            <div className="tsn__facts" data-testid="tsn-facts">
              <div className="tsn__facts-head mono">
                The numbers — from this app, not from the model
              </div>
              <ul className="tsn__facts-list mono">
                {Object.entries(data.facts).map(([k, v]) => (
                  <li key={k}><span className="tsn__fact-k">{FACT_LABEL[k] || k}</span>
                    {': '}<span className="tsn__fact-v">{factValue(v)}</span></li>
                ))}
              </ul>
            </div>
          ) : null}

          {headlines.length ? (
            <ul className="tsn__news" data-testid="tsn-headlines">
              {headlines.map((h, i) => (
                <li key={h.url || i}>
                  {h.url
                    ? <a href={h.url} target="_blank" rel="noreferrer">{h.title || h.url}</a>
                    : <span>{h.title}</span>}
                  {h.source ? <span className="tsn__src mono"> · {h.source}</span> : null}
                </li>
              ))}
            </ul>
          ) : null}

          <div className="tsn__foot">
            {data.ok ? (
              <span className="tsn__read-by mono" data-testid="tsn-read-by">
                read by {data.read_by || 'llm'} · {data.date} · {data.headline_count} headlines
                {' '}· not measured, not a signal
              </span>
            ) : null}
            {data.cached ? <span className="tsn__cached mono"> · today’s stored read</span> : null}
            <button type="button" className="sepa-btn sepa-btn--ghost tsn__recheck"
                    data-testid="tsn-recheck"
                    onClick={() => void load(true)} disabled={loading}>
              ↻ re-read
            </button>
          </div>
          {error ? <p className="tsn__err mono">Couldn’t read the news: {error}</p> : null}
        </>
      ) : null}
    </div>
  );
}

export default TwoSidedNewsButton;
