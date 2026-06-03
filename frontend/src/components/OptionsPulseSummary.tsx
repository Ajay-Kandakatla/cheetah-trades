import { useMemo } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import type { MouseEvent } from 'react';
import { openTickerWithModifier } from './TickerLink';
import { useOptionsPulse, type SoirRow } from '../hooks/useOptionsPulse';

/* ==========================================================================
   OptionsPulseSummary — compact "Schaeffer signals today" card.

   Designed to be embedded on the Overnight Tape, Morning Brief, or any
   other page where the user wants a quick read on which way the options
   crowd is contrarianly positioned. Reads from the cached SOIR scan
   (nightly 5:30pm ET cron) — no extra fetches per render beyond the one
   /options/soir call this hook makes.

   Two columns: top BULLISH and top BEARISH names by SOIR percentile
   distance from neutral. Click any row → SEPA candidate page so the user
   can immediately verify the trend + setup pillars match.
   ========================================================================== */

type Props = {
  /** Max names to show per side. Default 5; pass 3 for the densest layouts. */
  topN?: number;
};

export function OptionsPulseSummary({ topN = 5 }: Props) {
  const { data, loading } = useOptionsPulse();
  const nav = useNavigate();
  const location = useLocation();

  const { bullish, bearish, total } = useMemo(() => {
    const rows = data?.rows ?? [];
    const bull = rows
      .filter((r) => r.signal === 'BULLISH')
      .sort((a, b) => -((a.soir_percentile ?? 0) - (b.soir_percentile ?? 0)))
      .slice(0, topN);
    const bear = rows
      .filter((r) => r.signal === 'BEARISH')
      .sort((a, b) => (a.soir_percentile ?? 100) - (b.soir_percentile ?? 100))
      .slice(0, topN);
    return { bullish: bull, bearish: bear, total: rows.length };
  }, [data, topN]);

  // Only render the card when we have at least one signal. An empty
  // section is just clutter on the overnight page.
  const hasContent = bullish.length > 0 || bearish.length > 0;

  if (loading) return null;
  if (!data || !hasContent) return null;

  return (
    <section className="op-summary">
      <header className="op-summary__head">
        <div>
          <div className="eyebrow">Options Pulse · SOIR</div>
          <h2 className="op-summary__title">Schaeffer signals today</h2>
        </div>
        <div className="op-summary__meta mono">
          {bullish.length} bullish · {bearish.length} bearish · {total} scanned
          {' · '}
          <Link to="/options" className="op-summary__more">open full list →</Link>
        </div>
      </header>

      <p className="op-summary__lede">
        Tickers where the options crowd is contrarianly positioned vs the
        underlying trend — fuel for a move when the wrong-footed side starts
        unwinding. Use these alongside the gappers below: a gapper that's
        also <strong>BULLISH</strong> here is two frameworks agreeing.
      </p>

      <div className="op-summary__cols">
        {bullish.length > 0 && (
          <div className="op-summary__col op-summary__col--bull">
            <div className="op-summary__col-head">
              <span className="op-summary__col-tag op-summary__col-tag--bull">★ Bullish</span>
              <span className="mono op-summary__col-sub">crowd in puts → unwind = upside</span>
            </div>
            {bullish.map((r) => <SoirRowMini key={r.symbol} r={r} onClick={(e) => openTickerWithModifier(e, nav, location, r.symbol, 'Options Pulse')} />)}
          </div>
        )}
        {bearish.length > 0 && (
          <div className="op-summary__col op-summary__col--bear">
            <div className="op-summary__col-head">
              <span className="op-summary__col-tag op-summary__col-tag--bear">Bearish</span>
              <span className="mono op-summary__col-sub">crowd in calls → unwind = downside</span>
            </div>
            {bearish.map((r) => <SoirRowMini key={r.symbol} r={r} onClick={(e) => openTickerWithModifier(e, nav, location, r.symbol, 'Options Pulse')} />)}
          </div>
        )}
      </div>
    </section>
  );
}

function SoirRowMini({ r, onClick }: { r: SoirRow; onClick: (e: MouseEvent) => void }) {
  return (
    <button
      type="button"
      className="op-summary__row mono"
      onClick={onClick}
      title={r.reason}
    >
      <span className="op-summary__row-sym">{r.symbol}</span>
      <span className="op-summary__row-meta">
        SOIR {r.soir?.toFixed(2) ?? '—'}
        {r.soir_percentile != null && ` · ${r.soir_percentile.toFixed(0)}th pct`}
      </span>
      <span className="op-summary__row-em">
        ±{r.expected_move_pct?.toFixed(1) ?? '—'}%
      </span>
    </button>
  );
}
