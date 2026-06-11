/* ChartReadingGuide — "❓ How to read" button + modal for every candle chart
 * (Ajay 2026-06-10: "on the how to read the chart I would like to have —
 * this candle chart shows picture of all the possibilities and explains").
 *
 * All candles are drawn inline as SVG, so the pictures always match the
 * app's own chart colors. The reversal frequencies quoted on the pattern
 * cards MIRROR backend/patterns/candles_daily.py BULKOWSKI_CANDLE — verified
 * verbatim against thepatternsite.com (adversarial pass 2026-06-09). Do not
 * edit a number here without editing it there: same source, same wording.
 * Honesty caveat at the bottom is the backend CAVEAT, same rule. */
import { useState } from 'react';
import { createPortal } from 'react-dom';

const GREEN = '#10b981';
const RED = '#ef4444';
const WICK = '#94a3b8';
const SUB = '#8a93a6';

/** One candle: body between bodyTop/bodyBot, wick hi→lo (SVG y grows down). */
function Candle({ x, hi, bodyTop, bodyBot, lo, color, w = 12 }: {
  x: number; hi: number; bodyTop: number; bodyBot: number; lo: number;
  color: string; w?: number;
}) {
  return (
    <g>
      <line x1={x} x2={x} y1={hi} y2={lo} stroke={WICK} strokeWidth={1.4} />
      <rect x={x - w / 2} y={bodyTop} width={w} height={Math.max(1.5, bodyBot - bodyTop)}
            fill={color} rx={1} />
    </g>
  );
}

function Mini({ children, w = 96 }: { children: React.ReactNode; w?: number }) {
  return (
    <svg viewBox={`0 0 ${w} 64`} width={w} height={64}
         style={{ display: 'block', background: 'var(--bg-sunken,#0f1115)', borderRadius: 6 }}>
      {children}
    </svg>
  );
}

type Card = {
  title: string;
  tone: 'bull' | 'bear' | 'neutral';
  pic: React.ReactNode;
  read: string;
  stat?: string;
};

const SINGLE_CARDS: Card[] = [
  {
    title: 'Strong up candle',
    tone: 'bull',
    pic: <Mini><Candle x={48} hi={8} bodyTop={10} bodyBot={54} lo={56} color={GREEN} w={16} /></Mini>,
    read: 'Close near the high, big body, tiny wicks — buyers in control the whole session. On BIG volume at a pivot this is the breakout confirmation SEPA wants.',
  },
  {
    title: 'Strong down candle',
    tone: 'bear',
    pic: <Mini><Candle x={48} hi={8} bodyTop={10} bodyBot={54} lo={56} color={RED} w={16} /></Mini>,
    read: 'Close near the low, big body — sellers in control. On heavy volume inside a base or at highs, that\'s distribution.',
  },
  {
    title: 'Hammer',
    tone: 'bull',
    pic: <Mini><Candle x={48} hi={14} bodyTop={14} bodyBot={26} lo={58} color={GREEN} /></Mini>,
    read: 'Long LOWER wick after a down-move: sellers pushed it down, buyers bought it all back. Strongest when the next day closes above its high.',
    stat: 'Bulkowski: bullish reversal 60% of the time (reversal rank 26/103; overall performance rank 65/103)',
  },
  {
    title: 'Shooting star',
    tone: 'bear',
    pic: <Mini><Candle x={48} hi={6} bodyTop={40} bodyBot={52} lo={52} color={RED} /></Mini>,
    read: 'Long UPPER wick after an up-move: buyers tried, sellers slapped it back down. A wick into a pivot that fails to hold is a failed breakout.',
    stat: 'Bulkowski: bearish reversal 59% of the time — he calls that "near random" (overall performance rank 55/103)',
  },
  {
    title: 'Doji',
    tone: 'neutral',
    pic: <Mini><Candle x={48} hi={10} bodyTop={31} bodyBot={33} lo={54} color={WICK} /></Mini>,
    read: 'Open ≈ close — a stand-off. Says "pause", not "reverse". Meaning comes from where it sits (after a run? at support?) and what the NEXT candle does.',
    stat: 'Bulkowski (southern doji): bullish reversal just 52% of the time — a coin flip (overall performance rank 78/103)',
  },
  {
    title: 'Spinning top',
    tone: 'neutral',
    pic: <Mini><Candle x={48} hi={10} bodyTop={28} bodyBot={38} lo={54} color={GREEN} /></Mini>,
    read: 'Small body, wicks both sides — indecision. A cluster of these on SHRINKING volume inside a base is constructive (tightening); after a long run it\'s a tired trend.',
  },
];

const MULTI_CARDS: Card[] = [
  {
    title: 'Bullish engulfing',
    tone: 'bull',
    pic: (
      <Mini>
        <Candle x={36} hi={20} bodyTop={24} bodyBot={40} lo={44} color={RED} />
        <Candle x={58} hi={12} bodyTop={16} bodyBot={48} lo={52} color={GREEN} w={14} />
      </Mini>
    ),
    read: 'Green body swallows the prior red body after a decline — buyers overwhelmed yesterday\'s sellers.',
    stat: 'Bulkowski: bullish reversal 63% of the time, BUT overall performance rank 84/103 — "the post breakout performance can be dreadful"',
  },
  {
    title: 'Bearish engulfing',
    tone: 'bear',
    pic: (
      <Mini>
        <Candle x={36} hi={20} bodyTop={24} bodyBot={40} lo={44} color={GREEN} />
        <Candle x={58} hi={12} bodyTop={16} bodyBot={48} lo={52} color={RED} w={14} />
      </Mini>
    ),
    read: 'Red body swallows the prior green body after an advance. On a holding near highs, tighten the stop — but see the stat.',
    stat: 'Bulkowski: bearish reversal 79% of the time (rank 5/103) yet "does not imply a lasting reversal" — overall rank 91/103',
  },
  {
    title: 'Morning star',
    tone: 'bull',
    pic: (
      <Mini w={120}>
        <Candle x={30} hi={10} bodyTop={12} bodyBot={40} lo={44} color={RED} />
        <Candle x={60} hi={40} bodyTop={44} bodyBot={50} lo={56} color={WICK} w={8} />
        <Candle x={90} hi={14} bodyTop={18} bodyBot={46} lo={50} color={GREEN} />
      </Mini>
    ),
    read: 'Big red → small pause candle gapped lower → big green closing into the first candle\'s body. A 3-act bottom: panic, stand-off, reclaim.',
    stat: 'Bulkowski: bullish reversal 78% of the time (rank 6/103) and the rare candle with a strong post-breakout trend — overall rank 12/103',
  },
];

function VolumePic() {
  const bars = [
    { h: 12, c: RED }, { h: 16, c: RED }, { h: 10, c: GREEN }, { h: 8, c: RED },
    { h: 7, c: GREEN }, { h: 6, c: RED }, { h: 5, c: GREEN },              // dry-up
    { h: 30, c: GREEN },                                                  // breakout
    { h: 18, c: GREEN }, { h: 14, c: GREEN },
  ];
  return (
    <svg viewBox="0 0 130 40" width={130} height={40}
         style={{ display: 'block', background: 'var(--bg-sunken,#0f1115)', borderRadius: 6 }}>
      {bars.map((b, i) => (
        <rect key={i} x={4 + i * 12.4} y={36 - b.h} width={9} height={b.h} fill={b.c} opacity={0.8} rx={1} />
      ))}
    </svg>
  );
}

const toneColor = (t: Card['tone']) => (t === 'bull' ? GREEN : t === 'bear' ? RED : WICK);

function CardBox({ c }: { c: Card }) {
  return (
    <div style={{ border: `1px solid ${toneColor(c.tone)}33`, borderRadius: 10,
                  padding: '0.55rem 0.65rem', background: `${toneColor(c.tone)}07` }}>
      <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start' }}>
        {c.pic}
        <div style={{ minWidth: 0 }}>
          <div style={{ fontWeight: 700, fontSize: '0.84rem', color: toneColor(c.tone) }}>
            {c.tone === 'bull' ? '▲ ' : c.tone === 'bear' ? '▼ ' : '◆ '}{c.title}
          </div>
          <div style={{ fontSize: '0.76rem', lineHeight: 1.45 }}>{c.read}</div>
          {c.stat && (
            <div className="mono" style={{ fontSize: '0.72rem', color: SUB, marginTop: 3 }}>
              {c.stat}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export function ChartReadingGuide() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="mono"
              title="How to read this candle chart — every candle shape, what it means, and how to read the volume bars"
              style={{ fontSize: '0.72rem', padding: '6px 12px', borderRadius: 6, cursor: 'pointer',
                       background: 'transparent', color: 'inherit',
                       border: '1px solid var(--hairline,#2a2a2a)' }}>
        ❓ How to read
      </button>
      {open && createPortal(
        <div onClick={() => setOpen(false)}
             style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.65)', zIndex: 1200,
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      padding: '1rem', overflowY: 'auto' }}>
          <div onClick={(e) => e.stopPropagation()}
               style={{ background: 'var(--bg-raised,#1a1a1a)', color: 'var(--ink,inherit)',
                        border: '1px solid var(--rule,#333)', borderRadius: 8, width: '100%',
                        maxWidth: 'min(820px, calc(100vw - 2rem))', maxHeight: '90vh',
                        overflow: 'auto', padding: '1.1rem clamp(0.8rem, 3vw, 1.3rem)' }}>
            <header style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline',
                             marginBottom: '0.7rem' }}>
              <div>
                <div className="eyebrow">📖 How to read this chart</div>
                <h2 className="display" style={{ margin: '0.2rem 0 0', fontSize: '1.25rem' }}>
                  Candles, the possibilities, and volume
                </h2>
              </div>
              <button onClick={() => setOpen(false)}
                      style={{ background: 'none', border: 0, color: 'var(--cm-slate)', cursor: 'pointer',
                               fontSize: '1.4rem', lineHeight: 1, padding: '8px 10px', margin: '-8px -10px 0 0' }}>×</button>
            </header>

            {/* 1 — anatomy */}
            <section style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>1 · One candle = one session</div>
              <div style={{ display: 'flex', gap: 14, alignItems: 'center', flexWrap: 'wrap' }}>
                <svg viewBox="0 0 210 90" width={210} height={90}
                     style={{ background: 'var(--bg-sunken,#0f1115)', borderRadius: 6 }}>
                  <Candle x={60} hi={10} bodyTop={24} bodyBot={62} lo={78} color={GREEN} w={18} />
                  <Candle x={150} hi={10} bodyTop={24} bodyBot={62} lo={78} color={RED} w={18} />
                  <text x={78} y={15} fontSize={10} fill="#94a3b8">high</text>
                  <text x={78} y={28} fontSize={10} fill={GREEN}>close</text>
                  <text x={78} y={64} fontSize={10} fill="#94a3b8">open</text>
                  <text x={78} y={82} fontSize={10} fill="#94a3b8">low</text>
                  <text x={168} y={28} fontSize={10} fill="#94a3b8">open</text>
                  <text x={168} y={64} fontSize={10} fill={RED}>close</text>
                  <text x={44} y={88} fontSize={10} fill={GREEN}>up day</text>
                  <text x={132} y={88} fontSize={10} fill={RED}>down day</text>
                </svg>
                <p style={{ fontSize: '0.8rem', maxWidth: 420, lineHeight: 1.5 }}>
                  The <b>body</b> spans open→close (<span style={{ color: GREEN }}>green = closed higher</span>,{' '}
                  <span style={{ color: RED }}>red = closed lower</span>). The thin <b>wicks</b> mark the session's
                  high/low — price that traded there but <em>didn't hold</em>. Reading a candle = asking
                  "who won the session, and how decisively?"
                </p>
              </div>
            </section>

            {/* 2 — single-candle possibilities */}
            <section style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>2 · The single-candle possibilities</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(330px, 100%), 1fr))', gap: 8 }}>
                {SINGLE_CARDS.map((c) => <CardBox key={c.title} c={c} />)}
              </div>
            </section>

            {/* 3 — multi-candle reads */}
            <section style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>3 · Two- and three-candle reads (the ones our scanner flags)</div>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(min(330px, 100%), 1fr))', gap: 8 }}>
                {MULTI_CARDS.map((c) => <CardBox key={c.title} c={c} />)}
              </div>
            </section>

            {/* 4 — volume */}
            <section style={{ marginBottom: 14 }}>
              <div className="eyebrow" style={{ marginBottom: 6 }}>4 · The volume bars underneath</div>
              <div style={{ display: 'flex', gap: 14, alignItems: 'flex-start', flexWrap: 'wrap' }}>
                <VolumePic />
                <ul style={{ fontSize: '0.78rem', lineHeight: 1.55, margin: 0, paddingLeft: '1.1rem', maxWidth: 520 }}>
                  <li><b>Height</b> = shares traded; <b>color</b> = that day's direction. Volume is the conviction
                    behind the candle — a big candle on thin volume is a claim without a signature.</li>
                  <li><b>Quiet shrinking volume</b> while price tightens in a base = supply drying up (what the
                    VCP check looks for) — constructive.</li>
                  <li><b>A volume spike on the up candle through a pivot</b> (the tall green bar) = demand
                    confirming the breakout. That's the ≥1.5× average the buy gate wants.</li>
                  <li><b>Heavy volume on red days</b> at highs or inside a base = distribution — the stage
                    classifier downgrades on exactly this.</li>
                </ul>
              </div>
            </section>

            <p className="mono" style={{ fontSize: '0.72rem', color: SUB, lineHeight: 1.5 }}>
              Reversal frequencies are Bulkowski's daily-bar measurements, hindsight, no costs — quoted with his
              own deflating verdicts on purpose. Academic tests find NO standalone trading value in candle
              patterns (Marshall 2006; Horton 2009). Candles are context for the SEPA/volume decision,
              never a signal by themselves. Same-day reads are provisional until the CLOSE.
            </p>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
}
