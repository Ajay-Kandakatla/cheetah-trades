/* /portfolio — your positions, judged hold-or-sell.
 *
 * Manual-entry holdings + a per-position HOLD / TIGHTEN / TRIM / SELL verdict
 * with the R1/R2/R3 target ladder and the Minervini stop — the same sell-signal
 * logic (backend/sepa/position_lens.py) the SEPA cards use. This page answers
 * "do I keep holding this, or sell?" — not "should I buy" (that's the scanner).
 *
 * Rewritten 2026-06-02 (user): removed the Plaid connect/labels and the CSV
 * upload, deduped the title, and made it a focused manual-holdings + hold/sell
 * page. Holdings come from /portfolio/holdings (manual rows); add via the form,
 * remove via the 🗑. Backend untouched.
 */
import { useNavigate } from 'react-router-dom';
import { InfoButton } from '../components/InfoButton';
import { AddHoldingForm } from '../components/AddHoldingForm';
import { PositionSignal } from '../components/PositionSignal';
import { HoldingDiagnosis } from '../components/HoldingDiagnosis';
import { SepaTopPicks } from '../components/SepaTopPicks';
import { SepaRankLeaderboard } from '../components/SepaRankLeaderboard';
import { MarketPulsePanel } from '../components/MarketPulsePanel';
import { SepaRankCompare } from '../components/SepaRankCompare';
import { API } from '../lib/apiBase';
import { useHoldings, type HoldingRow } from '../hooks/usePortfolio';

const PageInfo = (
  <>
    <p>Your holdings, judged <strong>hold or sell</strong> — not buy.</p>
    <p>
      Each position gets a verdict — <strong>HOLD / TIGHTEN / TRIM / SELL</strong> —
      from the same Minervini sell-signal logic (Ch. 12–13) the scanner uses, plus
      the open <strong>R-multiple</strong>, the recommended <strong>stop</strong>,
      and the <strong>R1 / R2 / R3</strong> target ladder measured from the price
      you paid.
    </p>
    <p>Add positions manually below — ticker, shares, and your average cost.</p>
  </>
);

function money(n: number | null | undefined, signed = false): string {
  if (n == null) return '—';
  const sign = n < 0 ? '-' : signed ? '+' : '';
  return `${sign}$${Math.abs(n).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}
function pct(n: number | null | undefined): string {
  if (n == null) return '—';
  return `${n >= 0 ? '+' : ''}${n.toFixed(2)}%`;
}

export default function PortfolioPage() {
  const navigate = useNavigate();
  const { data, loading, error, refresh, updatedAt } = useHoldings(true);
  const rows: HoldingRow[] = data?.rows ?? [];

  const removeHolding = async (sym: string) => {
    if (!sym || !window.confirm(`Remove ${sym} from your positions?`)) return;
    try {
      const res = await fetch(`${API}/portfolio?ticker=${encodeURIComponent(sym)}`, {
        method: 'DELETE',
        credentials: 'include',
      });
      if (res.ok) await refresh();
    } catch {
      /* leave the row; the user can retry */
    }
  };

  const totalValue = rows.reduce((s, r) => s + (r.current_value ?? 0), 0);
  const totalPL = rows.reduce((s, r) => s + (r.pl_dollars ?? 0), 0);

  return (
    <div className="sepa-page">
      <div className="sepa-page__title">
        <div>
          <div className="eyebrow">№ — Hold or sell</div>
          <h1
            className="display sepa-page__h1"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
          >
            Portfolio
            <InfoButton inline title="Portfolio">{PageInfo}</InfoButton>
          </h1>
          <p className="lede">
            Your positions, judged <strong>hold or sell</strong> — each with a verdict,
            R-targets and a Minervini stop measured from your cost. Add what you own below.
          </p>
        </div>
      </div>

      {rows.length > 0 && (
        <div className="portfolio-totals mono">
          <span>{rows.length} position{rows.length === 1 ? '' : 's'}</span>
          <span>· value {money(totalValue)}</span>
          <span style={{ color: totalPL >= 0 ? '#10b981' : '#ef4444' }}>
            · open P&amp;L {money(totalPL, true)}
          </span>
          <span className="rank-lb__live" title={updatedAt ? `updated ${new Date(updatedAt).toLocaleTimeString()}` : 'live'}>
            {' · '}<span className="dot">●</span> live
          </span>
        </div>
      )}

      {loading && rows.length === 0 && (
        <p className="mono" style={{ opacity: 0.7, marginTop: '0.8rem' }}>…loading your positions</p>
      )}
      {error && (
        <p className="mono" style={{ color: '#f87171', marginTop: '0.8rem' }}>
          Couldn't load holdings — {error}
        </p>
      )}
      {!loading && !error && rows.length === 0 && (
        <div className="sepa-empty-card" style={{ marginTop: '0.8rem' }}>
          <div className="eyebrow">No positions yet</div>
          <p style={{ color: '#9aa8c8' }}>
            Add a stock above — ticker, shares, and the price you paid — and you'll get a
            hold/sell read with the R-target ladder.
          </p>
        </div>
      )}

      <div className="portfolio-list">
        {rows.map((r) => {
          // PER-SHARE average cost — `avg_cost` is per share; `cost_basis` is the
          // TOTAL dollars invested, so derive per-share from it as a fallback.
          const entry =
            r.avg_cost ??
            r.entry ??
            (r.cost_basis != null && r.quantity ? r.cost_basis / r.quantity : null);
          return (
            <div key={`${r.symbol}-${r.account_id || ''}`} className="portfolio-card">
              <div className="portfolio-card__top">
                <div className="portfolio-card__id">
                  <button
                    className="portfolio-card__sym"
                    onClick={() =>
                      navigate(`/sepa/${encodeURIComponent(r.symbol)}`, {
                        state: { from: '/portfolio', label: 'Portfolio' },
                      })
                    }
                    title="Open full SEPA analysis"
                  >
                    {r.symbol || '—'}
                  </button>
                  {r.name && (
                    <span className="portfolio-card__name">
                      {r.name.length > 40 ? r.name.slice(0, 40) + '…' : r.name}
                    </span>
                  )}
                </div>
                <button
                  type="button"
                  className="portfolio-card__rm"
                  title="Remove this position"
                  onClick={() => removeHolding(r.symbol)}
                >
                  🗑
                </button>
              </div>

              <div className="portfolio-card__nums mono">
                <span>{r.quantity.toLocaleString(undefined, { maximumFractionDigits: 4 })} sh</span>
                <span>cost {money(entry)}</span>
                <span>now {money(r.current_price)}</span>
                <span style={{ color: (r.pl_dollars ?? 0) >= 0 ? '#10b981' : '#ef4444' }}>
                  {money(r.pl_dollars, true)} ({pct(r.pl_pct)})
                </span>
              </div>

              <PositionSignal symbol={r.symbol} entry={entry} shares={r.quantity} stop={r.stop} />
              <HoldingDiagnosis symbol={r.symbol} defaultOpen />
            </div>
          );
        })}
      </div>

      <AddHoldingForm onAdded={refresh} />

      {/* Leadership + ranking BELOW your holdings (Ajay 2026-06-04). */}
      <SepaRankLeaderboard n={12} />
      <SepaRankCompare />
      <SepaTopPicks n={3} />

      {/* Overall market context — secondary to the per-stock reads above. */}
      <MarketPulsePanel holdings={rows} />
    </div>
  );
}
