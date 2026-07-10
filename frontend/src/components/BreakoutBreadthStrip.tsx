/* BreakoutBreadthStrip — the book's market thermometer on the Breakouts page.
 *
 * Daily count of volume-confirmed breakouts + the graded follow-through vs
 * failure record + Minervini's exposure posture (TLSW p.164/303/307; TTLAC
 * §5-§7). EXPOSURE GUIDANCE ONLY — the strip sizes positions, it never
 * gates an entry (TLSW p.165: never time individual buys off the market).
 * Built per Ajay 2026-07-10 "a few breakouts a day to gauge the market". */
import { useBreakoutBreadth } from '../hooks/useBreakoutBreadth';
import { countLine, ftSplit, readColor } from '../lib/breakoutBreadth';
import { InfoButton } from './InfoButton';

function Spark({ series }: { series: { n: number }[] }) {
  const vals = series.map((s) => s.n);
  if (vals.length < 2) return null;
  const W = 180, H = 36, P = 3;
  const hi = Math.max(...vals), lo = Math.min(...vals);
  const span = hi - lo || 1;
  const x = (i: number) => P + (i / (vals.length - 1)) * (W - 2 * P);
  const y = (v: number) => P + (1 - (v - lo) / span) * (H - 2 * P);
  const line = vals.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-label="Breakouts per day" style={{ display: 'block' }}>
      <path d={line} fill="none" stroke="var(--cm-slate,#8595ad)" strokeWidth="1.5" />
      <circle cx={x(vals.length - 1)} cy={y(vals[vals.length - 1])} r={2.5} fill="#38bdf8" />
    </svg>
  );
}

export function BreakoutBreadthStrip() {
  const data = useBreakoutBreadth();
  if (!data?.ok || !data.read) return null;   // rollups build nightly; hide until then

  const color = readColor(data.read.state);
  const split = ftSplit(data.recent_graded);
  const g = data.recent_graded;

  return (
    <section style={{ margin: '0.6rem 0 0.9rem', padding: '0.65rem 0.9rem', borderRadius: 8,
      background: `${color}0d`, border: `1px solid ${color}44` }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.8rem', flexWrap: 'wrap' }}>
        <span style={{ fontWeight: 800, color, fontSize: '0.92rem' }}>
          {data.read.icon} {data.read.label}
        </span>
        <span className="mono" style={{ fontSize: '0.8rem', color: 'var(--cm-text,#d1d5db)' }}>
          {countLine(data.today?.n_breakouts, data.avg10)}
        </span>
        {data.series && <Spark series={data.series} />}
        {split && g && (
          <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: '0.74rem', color: 'var(--cm-slate)' }}>
            <span style={{ display: 'inline-flex', width: 90, height: 8, borderRadius: 4, overflow: 'hidden' }}
                  title={`last ${g.n} graded breakouts (${g.window_bars}-day window): ${g.followed_through} followed through · ${g.failed} failed · ${g.stalled} stalled`}>
              <span style={{ width: `${split.ft * 100}%`, background: '#10b981' }} />
              <span style={{ width: `${split.stall * 100}%`, background: '#6b7280' }} />
              <span style={{ width: `${split.fail * 100}%`, background: '#ef4444' }} />
            </span>
            {g.failure_rate != null && <span>{Math.round(g.failure_rate * 100)}% failing</span>}
          </span>
        )}
        <InfoButton title="Breakout breadth — the book's market thermometer" inline align="left">
          <p><strong>Count:</strong> how many names broke out on confirmed volume each day.
            "You should see multiple waves of stocks emerging into new high ground" (TLSW p.164);
            an expanding leader list "should be viewed as a sign of strength" (TTLAC §7).</p>
          <p><strong>Grade:</strong> each breakout is checked 5 days later — did it follow through
            (TTLAC §1), stall, or <em>fail</em> back below the level it broke? "Rarely does a
            correct pivot point fail... in a healthy market" (TTLAC §6) — so mass failures are
            the p.303 warning of a hostile tape.</p>
          <p><strong>What it governs — position size, never entries.</strong> Expanding + working
            → step up the exposure ladder as your trades win (pilot buys → pyramid, TLSW p.307;
            TTLAC §5). Failing wholesale → pilot size and defense. But every valid pivot is still
            taken stock-by-stock: "if you concentrate on the general market solely for timing your
            individual stock purchases, you're likely to miss many of the really great selections"
            (TLSW p.165). A lone breakout with no confirming names is "normal" (TTLAC §7).</p>
        </InfoButton>
      </div>
      <p style={{ margin: '0.45rem 0 0', fontSize: '0.78rem', lineHeight: 1.5, color: 'var(--cm-text,#d1d5db)' }}>
        {data.read.guidance}
      </p>
    </section>
  );
}
