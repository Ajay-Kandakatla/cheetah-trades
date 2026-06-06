/* /market-gauge — the Pounce Market Gauge.
 *
 * Our own book-grounded read of the GENERAL MARKET's health: a 0-100 score, a
 * Constructive / Caution / Risk-Off state, a Minervini exposure band, and the
 * component breakdown that produced it. Educational — a regime read, not a
 * forecast. The same score shows top-right on every page (MarketGaugeBadge).
 */
import { InfoButton } from '../components/InfoButton';
import { useMarketGauge, type GaugeComponent } from '../hooks/useMarketGauge';

const PageInfo = (
  <>
    <p>
      The <strong>Market Gauge</strong> is our own read of the general market's
      health — <em>not</em> a copy of any paid third-party indicator (those
      formulas are undisclosed; we won't reverse-engineer a real-money signal).
      It composes the book-grounded market signals we already compute.
    </p>
    <p>
      <strong>Why it matters:</strong> O'Neil's CANSLIM “M” — about 3 of 4 stocks
      follow the general market. Minervini (Ch.&nbsp;5) trades <em>with</em> the
      market trend and (Ch.&nbsp;12–13, pp.&nbsp;303–305) scales exposure
      <em> down</em> in weak tapes, pyramiding back up only when it's “in gear.”
    </p>
    <p>
      <strong>It does not predict.</strong> Nobody reliably forecasts a week
      ahead. This reads the <em>current</em> regime so you react — buy-friendly
      vs. raise-cash — on probabilities, not a crystal ball.
    </p>
  </>
);

function stateClass(s?: string): string {
  return s ? `mg-state mg-state--${s}` : 'mg-state';
}

// Group pillars by category, preserving first-seen order.
function groupByCategory(comps: GaugeComponent[]): [string, GaugeComponent[]][] {
  const order: string[] = [];
  const map = new Map<string, GaugeComponent[]>();
  for (const c of comps) {
    const cat = c.category || 'Other';
    if (!map.has(cat)) { map.set(cat, []); order.push(cat); }
    map.get(cat)!.push(c);
  }
  return order.map((cat) => [cat, map.get(cat)!] as [string, GaugeComponent[]]);
}

function ComponentBar({ c }: { c: GaugeComponent }) {
  const pct = c.max > 0 ? Math.round((c.points / c.max) * 100) : 0;
  return (
    <div className="mg-comp">
      <div className="mg-comp__head">
        <span className="mg-comp__label">{c.label}</span>
        <span className="mg-comp__val mono">
          {String(c.value)} · {c.points}/{c.max}
        </span>
      </div>
      <div className="mg-comp__track">
        <div className={`mg-comp__fill mg-comp__fill--${pct >= 67 ? 'good' : pct >= 34 ? 'mid' : 'bad'}`} style={{ width: `${pct}%` }} />
      </div>
      <div className="mg-comp__basis mono">{c.basis}</div>
    </div>
  );
}

export function MarketGaugePage() {
  const g = useMarketGauge();

  return (
    <div className="sepa-page mg-page">
      <div className="sepa-page__title">
        <InfoButton title="Market Gauge">{PageInfo}</InfoButton>
        <div>
          <div className="eyebrow">№ — Market · Minervini / O'Neil</div>
          <h1 className="display sepa-page__h1">Market Gauge</h1>
          <p className="lede">
            A book-grounded read of the general market — read the regime, react
            on probabilities. Not a forecast, not advice.
          </p>
        </div>
      </div>

      {!g ? (
        <p className="mono" style={{ opacity: 0.7 }}>…reading the tape</p>
      ) : (
        <>
          {/* Headline score + state + exposure band */}
          <section className={`mg-hero mg-hero--${g.state}`}>
            <div className="mg-hero__score">
              <div className="mg-hero__num mono">{g.score}</div>
              <div className="mg-hero__outof mono">/ 100</div>
            </div>
            <div className="mg-hero__meta">
              <div className={stateClass(g.state)}>{g.state_label}</div>
              <div className="mg-hero__exposure">
                Minervini exposure guide:{' '}
                <strong>{g.exposure_band.low}–{g.exposure_band.high}%</strong> invested
                <div className="mg-hero__note">{g.exposure_band.note}</div>
              </div>
            </div>
          </section>

          {g.drivers && g.drivers.length > 0 && (
            <section className="mg-drivers">
              <div className="eyebrow">What's driving it</div>
              <ul>
                {g.drivers.map((d, i) => <li key={i}>{d}</li>)}
              </ul>
            </section>
          )}

          {/* Pillar breakdown, grouped by category */}
          <section className="mg-comps">
            <div className="eyebrow">Pillars</div>
            {groupByCategory(g.components).map(([cat, comps]) => (
              <div key={cat} className="mg-catgroup">
                <div className="mg-catgroup__label">{cat}</div>
                {comps.map((c) => <ComponentBar key={c.key} c={c} />)}
              </div>
            ))}
          </section>

          {/* How people "read the week" */}
          <section className="mg-explain">
            <div className="eyebrow">How disciplined traders “read the week”</div>
            <p>
              They don't forecast — they run a <strong>market-direction model</strong>
              {' '}and react. The four signals here are the classics:
            </p>
            <ul>
              <li><strong>Index trend</strong> — S&amp;P/Nasdaq above a rising 50/150/200-day stack = “in gear” (Minervini Trend Template, p.&nbsp;79).</li>
              <li><strong>Distribution days</strong> — higher-volume down-days on the indices; a cluster (~5+) signals institutions selling (O'Neil-style; configured thresholds).</li>
              <li><strong>Follow-through</strong> — after a low, a strong up-day on heavier volume confirms a new uptrend (Minervini p.&nbsp;248).</li>
              <li><strong>Breadth + macro regime</strong> — are most names participating, and what's the macro-risk backdrop.</li>
            </ul>
            <p className="mg-disclaimer">
              {g.disclaimer}
            </p>
          </section>
        </>
      )}
    </div>
  );
}
