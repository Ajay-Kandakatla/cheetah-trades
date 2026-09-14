/**
 * Long-term fundamentals — the ten metrics and the sector-relative score.
 *
 * Ajay 2026-09-14, with a ten-row checklist screenshot (OPM / EPS / D/E / ROE /
 * ROCE / Net Profit / Promoter Holding / Cash Flow / Balance Sheet / 10 Year
 * Sales, Profit Growth): *"Move them to fundamentals tab in the individual
 * ticker and give a score on the fundamentals ranking for longterm."*
 *
 * TWO THINGS THIS COMPONENT IS CAREFUL ABOUT, both of them honesty rules:
 *
 * 1. THE SCORE IS NOT A FORECAST UNTIL A STUDY SAYS IT IS. The backend ships
 *    `score_is_measured`, and while it is false every string here describes
 *    what the filings SAY and none of them predicts what the stock will DO.
 *    No "expected return", no "long-term winner", no green/red verdict on the
 *    number itself. Ajay's standing rule is that a measured number on a board
 *    he trades ships its backtest and a confidence interval; this number has
 *    neither yet, and three boards this year (Hot Pullback, KC Coiled, Bonde)
 *    shipped a claim that later measured null or inverted.
 *
 * 2. "PROMOTER HOLDING" IS NOT RENAMED, IT IS REPLACED, AND THE TAB SAYS SO.
 *    US issuers file no promoter holding. The row is labelled Institutional
 *    and carries both readings the backend keeps separate — the 13F-cadence
 *    ownership LEVEL and the block-print FLOW — with a note explaining the
 *    substitution rather than quietly showing a different number under his
 *    original label.
 *
 * Coverage is rendered as prominently as the score. A 62 backed by three
 * filed years is not the same number as a 62 backed by twelve, and the whole
 * reason he flagged it himself ("I know some of the stocks may not have 10
 * years") is that he expects the tab to be straight about it.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

export type LongTermMetrics = {
  opm: number | null; eps: number | null; de: number | null;
  roe: number | null; roce: number | null; net_profit: number | null;
  ocf: number | null; cash_conv: number | null; current_ratio: number | null;
  sales_cagr: number | null; profit_cagr: number | null;
};

export type LongTermResp = {
  symbol: string; ok: boolean; reason?: string | null;
  sector?: string | null; sector_n?: number; ranked?: boolean;
  rank_basis?: string | null; min_sector_n?: number;
  score?: number | null; covered_weight?: number | null;
  min_covered_weight?: number; score_used?: string[]; score_imputed?: string[];
  score_reason?: string | null; absent_because?: Record<string, string>;
  percentiles?: Record<string, number | null>;
  weights?: Record<string, number>;
  metrics?: LongTermMetrics;
  coverage?: {
    years_available?: number; years_for_growth?: number;
    growth_span?: string | null; has_10y?: boolean;
    latest_fiscal_year?: number | null; filing_date?: string | null;
  };
  history?: Array<{
    fy: number; revenues: number | null; net_income: number | null;
    eps: number | null; opm: number | null; roe: number | null;
    ocf: number | null; equity: number | null; assets: number | null;
    liabilities: number | null;
  }>;
  institutional?: {
    ownership_pct: number | null; block_share_pct: number | null;
    block_min_size?: number; note?: string;
  };
  score_is_measured?: boolean;
  score_origin?: string;
  built_at_iso?: string | null;
  stale?: boolean;
};

/** Compact money: 112,010,000,000 -> "$112.0B". Keeps a sign for losses. */
export function money(v: number | null | undefined): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  const neg = v < 0, a = Math.abs(v);
  const s = a >= 1e12 ? `${(a / 1e12).toFixed(2)}T`
    : a >= 1e9 ? `${(a / 1e9).toFixed(1)}B`
    : a >= 1e6 ? `${(a / 1e6).toFixed(1)}M`
    : a >= 1e3 ? `${(a / 1e3).toFixed(1)}K`
    : a.toFixed(0);
  return `${neg ? '−' : ''}$${s}`;
}

export function pct(v: number | null | undefined, dp = 1): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  return `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(dp)}%`;
}

export function ratio(v: number | null | undefined, dp = 2): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return '—';
  return `${v < 0 ? '−' : ''}${Math.abs(v).toFixed(dp)}`;
}

/** Why a metric is blank, in his words rather than a reason code. */
export function absentLabel(code?: string): string | null {
  if (code === 'loss') return 'company lost money — scored low, not skipped';
  if (code === 'no_history') return 'not enough filed years';
  return null;
}

const ROWS: Array<{
  key: keyof LongTermMetrics; pctKey?: string; label: string;
  fmt: (v: number | null | undefined) => string; hint: string;
}> = [
  { key: 'opm', pctKey: 'opm', label: 'OPM', fmt: (v) => pct(v),
    hint: 'Operating profit ÷ revenue. What the business keeps before interest and tax.' },
  { key: 'eps', label: 'EPS', fmt: (v) => ratio(v),
    hint: 'Diluted earnings per share, latest filed fiscal year.' },
  { key: 'de', pctKey: 'de', label: 'D/E', fmt: (v) => ratio(v),
    hint: 'Total liabilities ÷ equity — not just long-term debt, so leases and payables count. Lower is better.' },
  { key: 'roe', pctKey: 'roe', label: 'ROE', fmt: (v) => pct(v),
    hint: 'Net income ÷ shareholder equity. Blank when equity is negative — the ratio lies there.' },
  { key: 'roce', pctKey: 'roce', label: 'ROCE', fmt: (v) => pct(v),
    hint: 'Operating income ÷ (assets − current liabilities). Return on all capital, debt included.' },
  { key: 'net_profit', label: 'Net profit', fmt: money,
    hint: 'Net income attributable to the parent, latest filed year.' },
  { key: 'ocf', label: 'Cash flow', fmt: money,
    hint: 'Net cash from operating activities.' },
  { key: 'cash_conv', pctKey: 'cash_conv', label: 'Cash conversion', fmt: (v) => ratio(v),
    hint: 'Operating cash flow ÷ net profit. Under 1.0 for long means reported profit is not arriving as cash.' },
  { key: 'current_ratio', label: 'Current ratio', fmt: (v) => ratio(v),
    hint: 'Current assets ÷ current liabilities — the balance-sheet liquidity read.' },
  { key: 'sales_cagr', pctKey: 'sales_cagr', label: '10y sales growth', fmt: (v) => pct(v),
    hint: 'Revenue CAGR across the filed years shown. Needs at least three.' },
  { key: 'profit_cagr', pctKey: 'profit_cagr', label: '10y profit growth', fmt: (v) => pct(v),
    hint: 'Net-income CAGR. Blank when either end is a loss — you cannot annualise growth from a loss.' },
];

export function LongTermFundamentals({ symbol }: { symbol: string }) {
  const [data, setData] = useState<LongTermResp | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [showHistory, setShowHistory] = useState(false);

  useEffect(() => {
    let alive = true;
    setLoading(true); setErr(null);
    fetch(`${API}/sepa/longterm/${encodeURIComponent(symbol)}`, { cache: 'no-store' })
      .then((r) => r.json())
      .then((j) => { if (alive) { setData(j); setLoading(false); } })
      .catch((e) => { if (alive) { setErr(String(e)); setLoading(false); } });
    return () => { alive = false; };
  }, [symbol]);

  if (loading) return <div className="lt-note">Reading filed financials for {symbol}…</div>;
  if (err) return <div className="lt-note">Could not load fundamentals: {err}</div>;
  if (!data || !data.ok) {
    return (
      <div className="lt-note">
        <strong>No filed annual financials for {symbol}.</strong>{' '}
        {data?.reason || 'The provider returned nothing for this ticker.'} ETFs, trusts and
        very recent listings land here normally.
      </div>
    );
  }

  const m = data.metrics || ({} as LongTermMetrics);
  const cov = data.coverage || {};
  const inst = data.institutional || { ownership_pct: null, block_share_pct: null };
  const pcts = data.percentiles || {};
  const absent = data.absent_because || {};
  const measured = data.score_is_measured === true;
  const yrs = cov.years_available ?? 0;

  return (
    <div className="lt-wrap">
      {/* ---------- the score ---------- */}
      <div className="lt-scorecard">
        <div className="lt-scorenum">
          <div className="lt-score-value">
            {data.ranked && data.score !== null && data.score !== undefined
              ? data.score.toFixed(0) : '—'}
          </div>
          <div className="lt-score-of">/ 100</div>
        </div>
        <div className="lt-scorebody">
          <div className="lt-score-title">Long-term fundamentals score</div>
          {data.ranked ? (
            <div className="lt-score-sub">
              Percentile-ranked against <strong>{data.sector_n}</strong>{' '}
              <strong>{data.sector}</strong> peers. Higher means better than more of
              its own sector on the weighted metrics below — {' '}
              <strong>not</strong> a prediction about the share price.
            </div>
          ) : (
            <div className="lt-score-sub">
              <strong>Not ranked.</strong>{' '}
              {data.score_reason
                || (data.sector
                  ? `${data.sector} has fewer than ${data.min_sector_n} priced peers to rank against.`
                  : 'No sector on file for this ticker.')}{' '}
              The metrics below are still the filed numbers.
            </div>
          )}
          {!measured && (
            <div className="lt-unmeasured">
              This score is Cheetah's own composite — it is not from any book or published
              method, and <strong>it has not been tested against forward returns yet</strong>.
              Read it as a description of the filings, not a forecast.
            </div>
          )}
        </div>
      </div>

      {/* ---------- coverage, stated up front ---------- */}
      <div className="lt-coverage">
        <span className={cov.has_10y ? 'lt-cov-ok' : 'lt-cov-thin'}>
          {yrs} filed {yrs === 1 ? 'year' : 'years'}
        </span>
        {cov.growth_span && <span> · growth measured {cov.growth_span}</span>}
        {!cov.has_10y && (
          <span className="lt-cov-warn">
            {' '}· fewer than 10 years, so the growth rows span what exists
          </span>
        )}
        {cov.latest_fiscal_year && <span> · latest FY {cov.latest_fiscal_year}</span>}
        {cov.filing_date && <span> · filed {cov.filing_date}</span>}
        {data.ranked && data.covered_weight !== null && data.covered_weight !== undefined
          && data.covered_weight < 1 && (
          <span className="lt-cov-warn">
            {' '}· scored on {Math.round(data.covered_weight * 100)}% of the weights
          </span>
        )}
      </div>

      {/* ---------- the ten metrics ---------- */}
      <div className="lt-tablewrap">
        <table className="lt-table">
          <thead>
            <tr>
              <th>Metric</th>
              <th className="lt-r">Value</th>
              <th className="lt-r">vs sector</th>
            </tr>
          </thead>
          <tbody>
            {ROWS.map((r) => {
              const v = m[r.key];
              const p = r.pctKey ? pcts[r.pctKey] : undefined;
              const why = r.pctKey ? absentLabel(absent[r.pctKey]) : null;
              return (
                <tr key={r.key}>
                  <td>
                    <span className="lt-metric" title={r.hint}>{r.label}</span>
                    {why && <span className="lt-why"> — {why}</span>}
                  </td>
                  <td className="lt-r lt-val">{r.fmt(v)}</td>
                  <td className="lt-r">
                    {p === null || p === undefined
                      ? <span className="lt-dim">—</span>
                      : <span className="lt-pctl">{Math.round(p)}<small>th</small></span>}
                  </td>
                </tr>
              );
            })}
            {/* Institutional — the promoter-holding slot, labelled honestly */}
            <tr className="lt-inst">
              <td>
                <span className="lt-metric">Institutional</span>
                <span className="lt-why"> — stands in for promoter holding</span>
              </td>
              <td className="lt-r lt-val">
                {pct(inst.ownership_pct)} held
                {inst.block_share_pct !== null && inst.block_share_pct !== undefined && (
                  <> · {pct(inst.block_share_pct)} in blocks</>
                )}
              </td>
              <td className="lt-r">
                {pcts.inst === null || pcts.inst === undefined
                  ? <span className="lt-dim">—</span>
                  : <span className="lt-pctl">{Math.round(pcts.inst)}<small>th</small></span>}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <p className="lt-promoter">
        <strong>On promoter holding:</strong> US companies file nothing equivalent — it is an
        Indian exchange disclosure. The two readings that do exist are shown instead: the
        share held by institutions (a 13F-cadence level) and the share of the last session's
        volume that printed in blocks of {inst.block_min_size?.toLocaleString() || '5,000'}+
        shares (today's flow). They are kept separate on purpose; a level is not a flow.
      </p>

      {/* ---------- the filed history ---------- */}
      {(data.history?.length || 0) > 0 && (
        <div className="lt-history">
          <button type="button" className="lt-toggle"
            onClick={() => setShowHistory((s) => !s)}
            aria-expanded={showHistory}>
            {showHistory ? 'Hide' : 'Show'} the {data.history!.length}-year filed history
          </button>
          {showHistory && (
            <div className="lt-tablewrap">
              <table className="lt-table lt-hist">
                <thead>
                  <tr>
                    <th>FY</th><th className="lt-r">Revenue</th><th className="lt-r">Net profit</th>
                    <th className="lt-r">EPS</th><th className="lt-r">OPM</th>
                    <th className="lt-r">ROE</th><th className="lt-r">Op. cash flow</th>
                  </tr>
                </thead>
                <tbody>
                  {data.history!.map((h) => (
                    <tr key={h.fy}>
                      <td className="lt-val">{h.fy}</td>
                      <td className="lt-r lt-val">{money(h.revenues)}</td>
                      <td className="lt-r lt-val">{money(h.net_income)}</td>
                      <td className="lt-r lt-val">{ratio(h.eps)}</td>
                      <td className="lt-r lt-val">{pct(h.opm)}</td>
                      <td className="lt-r lt-val">{pct(h.roe)}</td>
                      <td className="lt-r lt-val">{money(h.ocf)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* ---------- how the score is built ---------- */}
      {data.weights && (
        <details className="lt-weights">
          <summary>How this score is built</summary>
          <p>
            Each metric is turned into a percentile <em>within the stock's own sector</em> —
            ROCE and D/E are not comparable between a bank and a software company, so one
            universe-wide ranking would score the sector rather than the company. Those
            percentiles are then combined with these weights:
          </p>
          <ul>
            {Object.entries(data.weights)
              .sort((a, b) => b[1] - a[1])
              .map(([k, w]) => (
                <li key={k}><code>{k}</code> — {Math.round(w * 100)}%</li>
              ))}
          </ul>
          <p>
            A metric with no value drops out and the rest are renormalised — <em>except</em>{' '}
            when it is missing because the company lost money. That is an answer, not a gap,
            so it scores low and still votes; otherwise a loss-making name would be graded
            only on the metrics it happens to be good at. A name needs{' '}
            {Math.round((data.min_covered_weight ?? 0.7) * 100)}% of the weights to be ranked
            at all.
          </p>
          <p className="lt-origin">{data.score_origin}</p>
        </details>
      )}

      {data.built_at_iso && (
        <div className="lt-built">
          Sector ranking built {data.built_at_iso.replace('T', ' ').slice(0, 16)} ET
          {data.stale && <span className="lt-cov-warn"> · overdue for a rebuild</span>}
        </div>
      )}
    </div>
  );
}
