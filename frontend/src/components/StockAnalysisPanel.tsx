import { useEffect, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? 'http://localhost:8000';

type Bar0to100 = {
  score: number | null;
  label: string;
  metrics?: Record<string, any>;
};

type FundamentalPanel = {
  available: boolean;
  valuation: Bar0to100;
  quality: Bar0to100;
  growth_stability: Bar0to100;
  financial_health: Bar0to100;
};

type TechnicalCell = {
  horizon: string;
  score: number | null;
  label: string;  // "Weak" | "Neutral" | "Strong"
  metrics?: Record<string, any>;
};

type TechnicalPanel = {
  available: boolean;
  short_term: TechnicalCell;
  mid_term: TechnicalCell;
  long_term: TechnicalCell;
};

type EsgRow = { score: number | null; label: string; industry_quartile?: number; peer_count?: number };
type EsgPanel = {
  available: boolean;
  provider?: string;
  overall?: EsgRow;
  environment?: EsgRow;
  social?: EsgRow;
  governance?: EsgRow;
};

type AnalystHistoryBucket = {
  period: string | null;
  strongBuy: number; buy: number; hold: number; sell: number; strongSell: number;
  total: number;
  score: number | null;
};
type AnalystPanelData = {
  available: boolean;
  reason?: string;
  provider?: string;
  score_0_10?: number | null;
  label?: string;
  firms_consolidated?: number;
  distribution?: {
    strongBuy: number; buy: number; hold: number; sell: number; strongSell: number;
    bullish_pct: number | null;
  };
  target?: { mean: number | null; median: number | null; high: number | null; low: number | null; analyst_count: number | null };
  history?: AnalystHistoryBucket[];
};

type AnalysisPayload = {
  symbol: string;
  fetched_at_iso: string;
  fundamental: FundamentalPanel;
  technical: TechnicalPanel;
  esg: EsgPanel;
  analyst: AnalystPanelData;
  cached: boolean;
};

type Props = { symbol: string };

function fmt(v: any, digits = 2): string {
  if (v == null) return '—';
  if (typeof v === 'number') return v.toFixed(digits);
  return String(v);
}

function fmtPct(v: number | null | undefined): string {
  if (v == null) return '—';
  return `${v > 0 ? '+' : ''}${v.toFixed(1)}%`;
}

// --- Fundamental panel ------------------------------------------------------
function FundamentalBar({
  axis, value, leftLabel, rightLabel, score, hint,
}: {
  axis: string; value: string; leftLabel: string; rightLabel: string;
  score: number | null; hint?: string;
}) {
  const pct = score == null ? 0 : Math.max(0, Math.min(100, score));
  return (
    <div className="sa-bar-row">
      <div className="sa-bar-row__label" title={hint}>
        <strong>{axis}</strong>
        <span className="sa-bar-row__metrics mono">{value}</span>
      </div>
      <div className="sa-bar-row__track">
        <div className="sa-bar-row__fill" style={{ width: `${pct}%` }} />
        {score != null && (
          <div className="sa-bar-row__marker" style={{ left: `${pct}%` }}>
            <span className="sa-bar-row__marker-num">{score}</span>
          </div>
        )}
      </div>
      <div className="sa-bar-row__ends">
        <span>{leftLabel}</span>
        <span>{rightLabel}</span>
      </div>
    </div>
  );
}

function FundamentalSection({ data }: { data: FundamentalPanel }) {
  if (!data.available) {
    return <Empty title="Fundamental analysis" reason="No fundamentals available for this ticker." />;
  }
  const f = data;
  const pe = f.valuation.metrics?.pe;
  const roe = f.quality.metrics?.roe_pct;
  const rev = f.growth_stability.metrics?.revenue_growth_pct;
  const dte = f.financial_health.metrics?.debt_to_equity;
  return (
    <section className="sa-card">
      <div className="sa-card__head">
        <div>
          <h3>Fundamental analysis</h3>
          <div className="sa-card__sub mono">Composite of yfinance fundamentals · 0-100 each axis (higher = better)</div>
        </div>
      </div>
      <FundamentalBar
        axis="Valuation" leftLabel="Overvalued" rightLabel="Undervalued"
        value={pe != null ? `P/E ${fmt(pe, 1)}` : '—'}
        score={f.valuation.score}
        hint="Composite of P/E, P/B and P/S — lower multiples score higher."
      />
      <FundamentalBar
        axis="Quality" leftLabel="Low" rightLabel="High"
        value={roe != null ? `ROE ${roe.toFixed(1)}%` : '—'}
        score={f.quality.score}
        hint="ROE, ROA, profit margin, operating margin."
      />
      <FundamentalBar
        axis="Growth Stability" leftLabel="Low" rightLabel="High"
        value={rev != null ? `Rev ${fmtPct(rev)}` : '—'}
        score={f.growth_stability.score}
        hint="Revenue growth + earnings growth."
      />
      <FundamentalBar
        axis="Financial Health" leftLabel="Less Healthy" rightLabel="Healthy"
        value={dte != null ? `D/E ${fmt(dte, 0)}` : '—'}
        score={f.financial_health.score}
        hint="Debt/equity, current ratio, free cash flow positivity."
      />
    </section>
  );
}

// --- Technical sentiment ---------------------------------------------------
function TechnicalCell({ cell, name }: { cell: TechnicalCell; name: string }) {
  const cls =
    cell.label === 'Strong' ? 'sa-tech__cell sa-tech__cell--strong' :
    cell.label === 'Neutral' ? 'sa-tech__cell sa-tech__cell--neutral' :
    cell.label === 'Weak' ? 'sa-tech__cell sa-tech__cell--weak' :
    'sa-tech__cell sa-tech__cell--na';
  return (
    <div className="sa-tech__row">
      <div className="sa-tech__label">
        <strong>{name}</strong>
        <span className="sa-card__sub mono">{cell.horizon}</span>
      </div>
      <div className="sa-tech__bar">
        <div className="sa-tech__cell sa-tech__cell--bg">Weak</div>
        <div className="sa-tech__cell sa-tech__cell--bg">Neutral</div>
        <div className="sa-tech__cell sa-tech__cell--bg">Strong</div>
        <div className={cls}>{cell.label}</div>
      </div>
    </div>
  );
}

function TechnicalSection({ data }: { data: TechnicalPanel }) {
  if (!data.available) {
    return <Empty title="Technical sentiment" reason="Need at least 252 trading days of history." />;
  }
  return (
    <section className="sa-card">
      <div className="sa-card__head">
        <div>
          <h3>Technical sentiment</h3>
          <div className="sa-card__sub mono">Three time horizons · derived from cached price history</div>
        </div>
      </div>
      <TechnicalCell name="Short-term sentiment" cell={data.short_term} />
      <TechnicalCell name="Mid-term sentiment" cell={data.mid_term} />
      <TechnicalCell name="Long-term sentiment" cell={data.long_term} />
    </section>
  );
}

// --- ESG -------------------------------------------------------------------
function EsgBar({ row, name }: { row?: EsgRow; name: string }) {
  if (!row || row.score == null) {
    return (
      <div className="sa-esg__row">
        <div className="sa-esg__label"><strong>{name}</strong></div>
        <div className="sa-esg__pill sa-esg__pill--na">— No data</div>
      </div>
    );
  }
  const cls =
    row.label === 'Leader' ? 'sa-esg__pill sa-esg__pill--leader' :
    row.label === 'Average' ? 'sa-esg__pill sa-esg__pill--avg' :
    'sa-esg__pill sa-esg__pill--laggard';
  return (
    <div className="sa-esg__row">
      <div className="sa-esg__label"><strong>{name}</strong></div>
      <div className={cls}>{row.label.toUpperCase()}</div>
      <div className="sa-esg__score mono">{row.score?.toFixed(1)} / 10</div>
      {row.industry_quartile && (
        <div className="sa-esg__quartile">Quartile {row.industry_quartile} of 4</div>
      )}
    </div>
  );
}

function EsgSection({ data }: { data: EsgPanel }) {
  if (!data.available) {
    return <Empty title="ESG" reason="No Sustainalytics data available for this ticker via yfinance." />;
  }
  return (
    <section className="sa-card">
      <div className="sa-card__head">
        <div>
          <h3>Environmental, social, &amp; governance</h3>
          <div className="sa-card__sub mono">{data.provider ?? 'Sustainalytics'} · risk-adjusted score (higher = better)</div>
        </div>
      </div>
      <EsgBar name="Overall" row={data.overall} />
      <EsgBar name="Environment" row={data.environment} />
      <EsgBar name="Social" row={data.social} />
      <EsgBar name="Governance" row={data.governance} />
    </section>
  );
}

// --- Analyst consensus -----------------------------------------------------
function AnalystSection({ data }: { data: AnalystPanelData }) {
  if (!data.available) {
    return <Empty title="Analyst ratings" reason={data.reason ?? 'No analyst data available.'} />;
  }
  const labelClass =
    data.label === 'Very Bullish' ? 'sa-analyst__badge--vbull' :
    data.label === 'Bullish'      ? 'sa-analyst__badge--bull' :
    data.label === 'Neutral'      ? 'sa-analyst__badge--neutral' :
    data.label === 'Bearish'      ? 'sa-analyst__badge--bear' :
    'sa-analyst__badge--vbear';

  return (
    <section className="sa-card">
      <div className="sa-card__head">
        <div>
          <h3>Analyst ratings</h3>
          <div className="sa-card__sub mono">
            Consolidates {data.firms_consolidated ?? 0} analyst opinions · {data.provider}
          </div>
        </div>
      </div>

      <div className="sa-analyst">
        <div className={`sa-analyst__badge ${labelClass}`}>
          <div className="sa-analyst__badge-label">{data.label}</div>
          <div className="sa-analyst__badge-score">{data.score_0_10?.toFixed(1)}</div>
          <div className="sa-analyst__badge-sub">out of 10</div>
        </div>
        <div className="sa-analyst__detail">
          <div className="sa-analyst__row">
            <span className="eyebrow">Bullish</span>
            <span className="mono">{data.distribution?.bullish_pct?.toFixed(0)}% of analysts</span>
          </div>
          <div className="sa-analyst__dist">
            <Pill kind="vbull" count={data.distribution?.strongBuy ?? 0} label="Strong Buy" />
            <Pill kind="bull" count={data.distribution?.buy ?? 0} label="Buy" />
            <Pill kind="neutral" count={data.distribution?.hold ?? 0} label="Hold" />
            <Pill kind="bear" count={data.distribution?.sell ?? 0} label="Sell" />
            <Pill kind="vbear" count={data.distribution?.strongSell ?? 0} label="Strong Sell" />
          </div>
          {data.target?.mean != null && (
            <div className="sa-analyst__target">
              <span className="eyebrow">12-month price target</span>
              <span className="mono">
                mean {fmt(data.target.mean)} · median {fmt(data.target.median)} ·
                low {fmt(data.target.low)} · high {fmt(data.target.high)}
                {data.target.analyst_count ? ` (${data.target.analyst_count} analysts)` : ''}
              </span>
            </div>
          )}
        </div>
      </div>

      {data.history && data.history.length > 0 && (
        <div className="sa-analyst__history">
          <div className="eyebrow">1-year history (monthly buckets)</div>
          <div className="sa-analyst__hist-row">
            {data.history.map((h) => {
              const total = h.total || 1;
              const sb = (h.strongBuy / total) * 100;
              const b  = (h.buy / total) * 100;
              const ho = (h.hold / total) * 100;
              const s  = (h.sell / total) * 100;
              const ss = (h.strongSell / total) * 100;
              return (
                <div key={h.period ?? Math.random()} className="sa-analyst__hist-col" title={`${h.period} · score ${h.score}`}>
                  <div className="sa-analyst__hist-stack">
                    <div style={{ height: `${sb}%`, background: '#15803d' }} />
                    <div style={{ height: `${b}%`,  background: '#86efac' }} />
                    <div style={{ height: `${ho}%`, background: '#cbd5e1' }} />
                    <div style={{ height: `${s}%`,  background: '#f87171' }} />
                    <div style={{ height: `${ss}%`, background: '#991b1b' }} />
                  </div>
                  <div className="sa-analyst__hist-label">{(h.period || '').slice(2, 7)}</div>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
}

function Pill({ kind, count, label }: { kind: string; count: number; label: string }) {
  return (
    <span className={`sa-pill sa-pill--${kind}`}>
      <strong>{count}</strong> {label}
    </span>
  );
}

// --- Empty / loading -------------------------------------------------------
function Empty({ title, reason }: { title: string; reason: string }) {
  return (
    <section className="sa-card sa-card--empty">
      <h3>{title}</h3>
      <p className="muted">{reason}</p>
    </section>
  );
}

// --- Main panel ------------------------------------------------------------
export function StockAnalysisPanel({ symbol }: Props) {
  const [data, setData] = useState<AnalysisPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API}/sepa/analysis/${encodeURIComponent(symbol)}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j) => { if (!cancelled) setData(j); })
      .catch((e) => { if (!cancelled) setError(String(e)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [symbol]);

  if (loading && !data) {
    return <div className="sepa-drawer__loading"><div className="eyebrow">Loading analysis…</div></div>;
  }
  if (error) {
    return <div className="sepa-empty-card"><div className="eyebrow">Error</div><p>{error}</p></div>;
  }
  if (!data) return null;

  return (
    <div className="sa-stack">
      <div className="sa-meta mono">
        Analysis as of {new Date(data.fetched_at_iso).toLocaleString()}{' '}
        {data.cached && <span className="sa-meta__chip">cached</span>}
      </div>
      <div className="sa-grid">
        <FundamentalSection data={data.fundamental} />
        <TechnicalSection data={data.technical} />
        <EsgSection data={data.esg} />
        <AnalystSection data={data.analyst} />
      </div>
    </div>
  );
}
