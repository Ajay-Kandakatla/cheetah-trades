/* MacroIndicators — live FRED macro dashboard for the Market Gauge page.
 *
 * CPI & Core CPI (YoY), unemployment, Fed funds and the 10y-3m curve — each with
 * the latest value, the change vs the prior print (colored by whether that move
 * is healthy), a trend sparkline, the reference date, and the next scheduled
 * release date. Lets you see "how CPI is changing" + "what's coming." Context for
 * the regime read, NOT a forecast.
 */
import { useMacroIndicators, type MacroIndicator } from '../hooks/useMacroIndicators';
import { Sparkline } from './Sparkline';

// Is this move the "good" direction? CPI/unemployment down = good; curve up =
// good; Fed funds is policy (neutral — we don't color it good/bad).
function changeColor(good: string, change: number | null): string {
  if (change == null || change === 0 || good === 'neutral') return 'var(--ink-muted,#94a3b8)';
  const rising = change > 0;
  const goodIsUp = good === 'up';
  return rising === goodIsUp ? '#10b981' : '#ef4444';
}

function fmt(v: number | null | undefined, unit: string): string {
  if (v == null) return '—';
  return `${v.toFixed(2)}${unit}`;
}

function Card({ ind }: { ind: MacroIndicator }) {
  const cc = changeColor(ind.good, ind.change);
  const arrow = ind.direction === 'up' ? '▲' : ind.direction === 'down' ? '▼' : '▶';
  const yoy = ind.transform === 'yoy';
  return (
    <div style={{
      padding: '0.7rem 0.8rem', borderRadius: 10, background: 'var(--bg-raised,#16181d)',
      border: '1px solid var(--hairline,#2a2a2a)', display: 'flex', flexDirection: 'column', gap: 4,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 6 }}>
        <span style={{ fontWeight: 700, fontSize: '0.86rem' }}>{ind.label}</span>
        {yoy && <span style={{ fontSize: '0.62rem', color: 'var(--ink-subtle,#6b7280)', border: '1px solid var(--hairline,#2a2a2a)', borderRadius: 4, padding: '0 4px' }}>YoY</span>}
      </div>
      <div style={{ fontSize: '0.66rem', color: 'var(--ink-subtle,#6b7280)', marginTop: -2 }}>{ind.blurb}</div>

      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 8, marginTop: 2 }}>
        <span style={{ fontSize: '1.5rem', fontWeight: 800, fontVariantNumeric: 'tabular-nums', lineHeight: 1.1 }}>
          {fmt(ind.value, ind.unit)}
        </span>
        <Sparkline values={ind.trend} width={92} height={26} />
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: '0.76rem' }}>
        <span style={{ color: cc, fontWeight: 700 }}>
          {arrow} {ind.change == null ? '—' : `${ind.change > 0 ? '+' : ''}${ind.change.toFixed(2)}`}
        </span>
        <span style={{ color: 'var(--ink-subtle,#6b7280)' }}>vs prior</span>
      </div>

      <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, fontSize: '0.66rem', color: 'var(--ink-subtle,#6b7280)', marginTop: 2 }}>
        <span>as of {ind.as_of_label}</span>
        {ind.next_release_label && <span>next: {ind.next_release_label}</span>}
      </div>
    </div>
  );
}

export function MacroIndicators() {
  const m = useMacroIndicators();
  if (!m) {
    return (
      <section className="mg-comps">
        <div className="eyebrow">Macro dashboard — inflation, jobs, rates</div>
        <p className="mono" style={{ opacity: 0.7 }}>…reading the macro tape</p>
      </section>
    );
  }
  if (!m.indicators.length) {
    return (
      <section className="mg-comps">
        <div className="eyebrow">Macro dashboard — inflation, jobs, rates</div>
        <p className="mono" style={{ opacity: 0.7 }}>
          {m.fred_available ? 'No macro data right now.' : 'FRED key not configured — macro dashboard unavailable.'}
        </p>
      </section>
    );
  }
  return (
    <section className="mg-comps" style={{ borderTop: '1px solid var(--hairline,#2a2a2a)', paddingTop: '1rem' }}>
      <div className="eyebrow">Macro dashboard — inflation, jobs, rates</div>
      <p style={{ fontSize: '0.78rem', color: 'var(--ink-muted,#94a3b8)', margin: '0.2rem 0 0.8rem' }}>
        Live from the St. Louis Fed (FRED) — how the macro backdrop is changing, and the next scheduled prints.
      </p>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '0.7rem' }}>
        {m.indicators.map((ind) => <Card key={ind.id} ind={ind} />)}
      </div>
      <div style={{ fontSize: '0.66rem', color: 'var(--ink-subtle,#6b7280)', marginTop: 10 }}>{m.disclaimer}</div>
    </section>
  );
}
