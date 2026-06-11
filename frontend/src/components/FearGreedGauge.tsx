/* FearGreedGauge — CNN Business's Fear & Greed index, surfaced in-app.
 *
 * A semicircle dial (the familiar CNN look) with a needle at the live score, the
 * five sentiment zones, the previous-close / 1-week / 1-month / 1-year readings,
 * the seven component sub-indices as bars, and a recent trend sparkline. The
 * number is CNN's — attribution is shown. Sentiment context, not advice.
 */
import { useFearGreed, type FGPrev } from '../hooks/useFearGreed';
import { Sparkline } from './Sparkline';

// CNN's five bands + cut points (0-25 / 25-45 / 45-55 / 55-75 / 75-100).
const BANDS = [
  { max: 25, key: 'extreme_fear', label: 'Extreme Fear', color: '#e53935' },
  { max: 45, key: 'fear', label: 'Fear', color: '#fb8c00' },
  { max: 55, key: 'neutral', label: 'Neutral', color: '#bcae6b' },
  { max: 75, key: 'greed', label: 'Greed', color: '#7cb342' },
  { max: 101, key: 'extreme_greed', label: 'Extreme Greed', color: '#2e7d32' },
];

function bandColor(score: number): string {
  for (const b of BANDS) if (score < b.max) return b.color;
  return BANDS[BANDS.length - 1].color;
}

// Polar point on a semicircle: frac 0 → left end, 1 → right end, over the top.
function pt(cx: number, cy: number, r: number, frac: number): [number, number] {
  const a = Math.PI * (1 - Math.min(1, Math.max(0, frac)));
  return [cx + r * Math.cos(a), cy - r * Math.sin(a)];
}
function arc(cx: number, cy: number, r: number, f0: number, f1: number): string {
  const [x0, y0] = pt(cx, cy, r, f0);
  const [x1, y1] = pt(cx, cy, r, f1);
  return `M ${x0.toFixed(2)} ${y0.toFixed(2)} A ${r} ${r} 0 0 1 ${x1.toFixed(2)} ${y1.toFixed(2)}`;
}

function Dial({ score, color }: { score: number; color: string }) {
  const W = 280, H = 168, cx = 140, cy = 150, r = 116, sw = 22;
  const frac = Math.min(1, Math.max(0, score / 100));
  const bounds = [0, 0.25, 0.45, 0.55, 0.75, 1];
  const [nx, ny] = pt(cx, cy, r - 6, frac);
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" style={{ maxWidth: 320, display: 'block', margin: '0 auto' }}>
      {/* zone arcs */}
      {BANDS.map((b, i) => (
        <path key={b.key} d={arc(cx, cy, r, bounds[i], bounds[i + 1])}
              stroke={b.color} strokeWidth={sw} fill="none" strokeLinecap="butt" opacity={0.92} />
      ))}
      {/* end ticks */}
      <text x={cx - r} y={cy + 16} fontSize="11" fill="var(--ink-muted,#94a3b8)" textAnchor="middle">0</text>
      <text x={cx + r} y={cy + 16} fontSize="11" fill="var(--ink-muted,#94a3b8)" textAnchor="middle">100</text>
      {/* needle */}
      <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ink,#e5e7eb)" strokeWidth={3.5} strokeLinecap="round" />
      <circle cx={cx} cy={cy} r={8} fill="var(--ink,#e5e7eb)" />
      <circle cx={cx} cy={cy} r={3.5} fill={color} />
      {/* score */}
      <text x={cx} y={cy - 34} fontSize="44" fontWeight="800" fill={color} textAnchor="middle">{Math.round(score)}</text>
    </svg>
  );
}

function PrevRow({ label, p }: { label: string; p: FGPrev }) {
  if (!p) return null;
  return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, padding: '0.28rem 0' }}>
      <span style={{ color: 'var(--ink-muted,#94a3b8)', fontSize: '0.78rem' }}>{label}</span>
      <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6 }}>
        <span style={{ fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>{Math.round(p.value)}</span>
        <span style={{ fontSize: '0.72rem', color: bandColor(p.value), fontWeight: 600 }}>{p.rating_label}</span>
      </span>
    </div>
  );
}

function ComponentBar({ label, blurb, score }: { label: string; blurb: string; score: number }) {
  const c = bandColor(score);
  return (
    <div style={{ marginBottom: 9 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8 }}>
        <span style={{ fontSize: '0.82rem', fontWeight: 600 }} title={blurb}>{label}</span>
        <span style={{ fontSize: '0.78rem', fontWeight: 700, color: c, fontVariantNumeric: 'tabular-nums' }}>{Math.round(score)}</span>
      </div>
      <div style={{ height: 6, borderRadius: 4, background: 'var(--bg-sunken,#0f1115)', marginTop: 3, overflow: 'hidden' }}>
        <div style={{ width: `${Math.min(100, Math.max(0, score))}%`, height: '100%', background: c, borderRadius: 4 }} />
      </div>
      <div style={{ fontSize: '0.66rem', color: 'var(--ink-subtle,#8a93a6)', marginTop: 2 }}>{blurb}</div>
    </div>
  );
}

export function FearGreedGauge() {
  const fg = useFearGreed();
  if (!fg || fg.score == null) {
    return (
      <section className="mg-comps">
        <div className="eyebrow">Market sentiment — CNN Fear &amp; Greed</div>
        <p className="mono" style={{ opacity: 0.7 }}>…reading sentiment</p>
      </section>
    );
  }
  const color = bandColor(fg.score);
  const histVals = (fg.history || []).map((h) => h.v);

  return (
    <section className="mg-comps" style={{ borderTop: '1px solid var(--hairline,#2a2a2a)', paddingTop: '1rem' }}>
      <div className="eyebrow">Market sentiment — CNN Fear &amp; Greed</div>

      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '1.2rem', alignItems: 'center', marginTop: '0.4rem' }}>
        {/* Dial + rating */}
        <div style={{ flex: '1 1 280px', minWidth: 260 }}>
          <Dial score={fg.score} color={color} />
          <div style={{ textAlign: 'center', marginTop: -6 }}>
            <span style={{ fontSize: '1.05rem', fontWeight: 800, color, letterSpacing: 0.3 }}>
              {fg.rating_label}
            </span>
          </div>
          {histVals.length > 2 && (
            <div style={{ marginTop: 8, display: 'flex', justifyContent: 'center', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: '0.66rem', color: 'var(--ink-subtle,#8a93a6)' }}>3-mo trend</span>
              <Sparkline values={histVals} width={150} height={26} />
            </div>
          )}
        </div>

        {/* Previous readings */}
        <div style={{ flex: '1 1 200px', minWidth: 190 }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--ink-subtle,#8a93a6)', marginBottom: 4, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Where it stood
          </div>
          <PrevRow label="Previous close" p={fg.previous.close} />
          <PrevRow label="1 week ago" p={fg.previous.week} />
          <PrevRow label="1 month ago" p={fg.previous.month} />
          <PrevRow label="1 year ago" p={fg.previous.year} />
        </div>
      </div>

      {/* Component sub-indices */}
      {fg.components.length > 0 && (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--ink-subtle,#8a93a6)', marginBottom: 8, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            What's driving it — 7 indicators
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0 1.4rem' }}>
            {fg.components.map((c) => (
              <ComponentBar key={c.key} label={c.label} blurb={c.blurb} score={c.score} />
            ))}
          </div>
        </div>
      )}

      <div style={{ fontSize: '0.66rem', color: 'var(--ink-subtle,#8a93a6)', marginTop: 10 }}>
        Source:{' '}
        <a href={fg.source_url} target="_blank" rel="noreferrer" style={{ color: 'var(--gold,#c9a227)' }}>
          {fg.source}
        </a>{' '}
        — {fg.disclaimer}
      </div>
    </section>
  );
}
