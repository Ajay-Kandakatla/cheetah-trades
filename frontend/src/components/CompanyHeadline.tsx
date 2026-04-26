import { useEffect, useRef, useState } from 'react';

const API = (import.meta as any).env?.VITE_API_BASE ?? '';

type Headline = {
  market_cap: number | null;
  shareholder_equity: number | null;
  book_value_per_share: number | null;
  shares_outstanding: number | null;
  revenue_ttm: number | null;
  enterprise_value: number | null;
  total_debt: number | null;
  total_cash: number | null;
};

type Props = { symbol: string };

function fmtBig(v: number | null | undefined): string {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e12) return `$${(v / 1e12).toFixed(2)}T`;
  if (a >= 1e9)  return `$${(v / 1e9).toFixed(2)}B`;
  if (a >= 1e6)  return `$${(v / 1e6).toFixed(1)}M`;
  if (a >= 1e3)  return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

/**
 * CompanyHeadline — compact horizontal strip for the SepaCandidate page
 * header. Surfaces the four most-asked figures (current net worth = market
 * cap, shareholders' equity, TTM revenue, enterprise value) right under
 * the symbol so users don't have to drill into the Analysis tab.
 *
 * Pulls from the same /sepa/analysis endpoint the Analysis tab uses, so
 * the cache is shared and there's no extra provider hit.
 */
export function CompanyHeadline({ symbol }: Props) {
  const [h, setH] = useState<Headline | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setH(null);
    setError(false);
    fetch(`${API}/sepa/analysis/${encodeURIComponent(symbol)}`)
      .then((r) => r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`)))
      .then((j) => {
        if (cancelled) return;
        const head = j?.fundamental?.headline;
        if (head) setH(head); else setError(true);
      })
      .catch(() => { if (!cancelled) setError(true); })
      ;
    return () => { cancelled = true; };
  }, [symbol]);

  if (error) return null;

  return (
    <div className="cm-headline">
      <Stat
        label="Current net worth"
        value={fmtBig(h?.market_cap)}
        loading={!h}
        info={{
          title: 'Current net worth (Market capitalization)',
          body: (
            <>
              <p>Often shortened to "market cap" — what the stock market is paying for the entire company right now.</p>
              <p><strong>Formula:</strong> share price × shares outstanding</p>
              <p>This number floats with the share price every trading day. It's the headline figure for company size.</p>
            </>
          ),
        }}
      />
      <Stat
        label="Shareholders' equity"
        value={fmtBig(h?.shareholder_equity)}
        loading={!h}
        info={{
          title: "Shareholders' equity (Book value)",
          body: (
            <>
              <p>The accounting net worth — total assets minus total liabilities. What shareholders would technically own if the company sold everything and paid off all debts tomorrow.</p>
              <p><strong>Formula:</strong> book value per share × shares outstanding</p>
              <p>It usually trails market capitalization because the market prices in expected future growth. The ratio market cap ÷ equity is the Price-to-Book (P/B) ratio.</p>
            </>
          ),
        }}
      />
      <Stat
        label="Revenue · Trailing 12 Months (TTM)"
        value={fmtBig(h?.revenue_ttm)}
        loading={!h}
        info={{
          title: 'Revenue · Trailing 12 Months (TTM)',
          body: (
            <>
              <p>Top-line sales over the last four reported quarters. The actual money the business brought in — before any costs, expenses, or taxes are deducted.</p>
              <p><strong>Formula:</strong> sum of the last 4 quarterly revenue figures</p>
              <p>"TTM" stands for Trailing Twelve Months — a rolling 1-year window that updates each quarter, smoothing out seasonality.</p>
            </>
          ),
        }}
      />
      <Stat
        label="Enterprise Value (EV)"
        value={fmtBig(h?.enterprise_value)}
        loading={!h}
        info={{
          title: 'Enterprise Value (EV)',
          body: (
            <>
              <p>The total cost an acquirer would pay to buy the whole business outright. Market capitalization tells you the equity value; Enterprise Value adds the debt the acquirer would inherit and subtracts the cash they would absorb.</p>
              <p><strong>Formula:</strong> market capitalization + total debt − total cash</p>
              <p>Acquirers care about EV/Revenue and EV/EBITDA (Earnings Before Interest, Taxes, Depreciation, and Amortization) more than P/E because those ratios are independent of how the target funds itself.</p>
            </>
          ),
        }}
      />
    </div>
  );
}

type InfoSpec = { title: string; body: React.ReactNode };

function Stat({ label, value, loading, info }: { label: string; value: string; loading: boolean; info: InfoSpec }) {
  return (
    <div className="cm-headline__stat">
      <div className="cm-headline__label">
        {label}
        <CmInfoDot info={info} />
      </div>
      <div className={`cm-headline__value mono ${loading ? 'is-loading' : ''}`}>{loading ? '…' : value}</div>
    </div>
  );
}

function CmInfoDot({ info }: { info: InfoSpec }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('keydown', onKey);
    document.addEventListener('mousedown', onDoc);
    return () => {
      document.removeEventListener('keydown', onKey);
      document.removeEventListener('mousedown', onDoc);
    };
  }, [open]);

  return (
    <span className="cm-headline__info" ref={ref}>
      <button
        type="button"
        className="cm-headline__info-btn"
        aria-label={`What is ${info.title}?`}
        aria-expanded={open}
        onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }}
      >ⓘ</button>
      {open && (
        <span className="cm-headline__info-pop" role="dialog" aria-label={info.title}>
          <span className="cm-headline__info-head">
            <strong>{info.title}</strong>
            <button
              type="button"
              className="cm-headline__info-close"
              aria-label="Close"
              onClick={(e) => { e.stopPropagation(); setOpen(false); }}
            >×</button>
          </span>
          <span className="cm-headline__info-body">{info.body}</span>
        </span>
      )}
    </span>
  );
}
