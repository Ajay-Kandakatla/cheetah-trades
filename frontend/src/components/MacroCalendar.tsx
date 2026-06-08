/* MacroCalendar — tiered "what could move the regime" calendar on the gauge page.
 *
 * Upcoming data releases bucketed T1 market-movers / T2 trend-shapers / T3 context
 * (the ZONETRADER618 "Not All Data Is Equal" framework), with REAL FRED-scheduled
 * dates, plus earnings-ahead for tracked names so high-volatility days are flagged.
 * Reads /macro/calendar. Educational, not a forecast.
 */
import { useEffect, useState } from 'react';
import { API } from '../lib/apiBase';

type MEvent = { date: string; kind: string; tier: number; label: string };
type Payload = {
  available: boolean;
  days: number;
  tier_labels: Record<string, string>;
  tier_taxonomy: Record<string, string[]>;
  regime_weighting: string;
  macro: MEvent[];
  next_tier1: MEvent | null;
  earnings_by_day: { date: string; tickers: string[]; n: number }[];
  disclaimer: string;
};

function dLabel(date: string): string {
  const d = new Date(`${date}T12:00:00`);
  const today = new Date(); today.setHours(12, 0, 0, 0);
  const days = Math.round((d.getTime() - today.getTime()) / 86_400_000);
  const wd = d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
  const rel = days <= 0 ? 'today' : days === 1 ? 'tomorrow' : `in ${days}d`;
  return `${wd} · ${rel}`;
}

export function MacroCalendar() {
  const [d, setD] = useState<Payload | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const r = await fetch(`${API}/macro/calendar?days=14`);
        if (r.ok) setD(await r.json());
      } catch { /* best-effort */ }
    })();
  }, []);

  if (!d) return null;

  return (
    <section className="mc-cal">
      <div className="eyebrow">Macro calendar · what could move the regime</div>
      <p className="mc-cal__weight"><strong>Regime weighting:</strong> {d.regime_weighting}</p>

      {d.next_tier1 && (
        <div className="mc-cal__next">
          ⚡ Next market-mover: <strong>{d.next_tier1.label}</strong> — {dLabel(d.next_tier1.date)}
        </div>
      )}

      {d.macro.length > 0 ? (
        <div className="mc-cal__list">
          {d.macro.map((e, i) => (
            <div key={i} className="mc-ev">
              <span className={`mc-tb mc-tb--${e.tier}`}>T{e.tier}</span>
              <span className="mc-ev__label">{e.label}</span>
              <span className="mc-ev__date mono">{dLabel(e.date)}</span>
            </div>
          ))}
        </div>
      ) : (
        <p className="mono" style={{ opacity: 0.6 }}>No scheduled releases in the next {d.days} days.</p>
      )}

      {d.earnings_by_day.length > 0 && (
        <div className="mc-earn">
          <div className="mc-earn__head">Earnings to watch · your tracked names</div>
          {d.earnings_by_day.map((ed) => (
            <div key={ed.date} className="mc-earn__row">
              <span className="mc-earn__date mono">{dLabel(ed.date)}</span>
              <span className="mc-earn__tk">{ed.tickers.join(' · ')}</span>
            </div>
          ))}
        </div>
      )}

      <details className="mc-tiers">
        <summary>What the tiers mean</summary>
        {(['1', '2', '3'] as const).map((t) => (
          <div key={t} className="mc-tier">
            <span className={`mc-tb mc-tb--${t}`}>T{t}</span>
            <strong>{d.tier_labels[t]}</strong>
            <span className="mc-tier__items"> — {d.tier_taxonomy[t]?.join(' · ')}</span>
          </div>
        ))}
      </details>

      <p className="mc-cal__disc mono">{d.disclaimer}</p>
    </section>
  );
}
