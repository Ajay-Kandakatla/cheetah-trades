import { useEffect, useState } from 'react';

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
        hint="Market cap = price × shares outstanding. What the market is paying for the entire company today."
      />
      <Stat
        label="Shareholders' equity"
        value={fmtBig(h?.shareholder_equity)}
        loading={!h}
        hint="Book value × shares outstanding. The accounting net worth — what shareholders technically own."
      />
      <Stat
        label="Revenue · TTM"
        value={fmtBig(h?.revenue_ttm)}
        loading={!h}
        hint="Sum of the last 4 quarters' total revenue. The actual money the business brought in."
      />
      <Stat
        label="Enterprise value"
        value={fmtBig(h?.enterprise_value)}
        loading={!h}
        hint="Market cap + total debt − total cash. What an acquirer would actually pay."
      />
    </div>
  );
}

function Stat({ label, value, loading, hint }: { label: string; value: string; loading: boolean; hint: string }) {
  return (
    <div className="cm-headline__stat" title={hint}>
      <div className="cm-headline__label">{label}</div>
      <div className={`cm-headline__value mono ${loading ? 'is-loading' : ''}`}>{loading ? '…' : value}</div>
    </div>
  );
}
