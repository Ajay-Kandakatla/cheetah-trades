/* CandleAnatomyExplainer — a compact "how to read this chart" key for
   the TradingView candle chart. The user is learning the framework
   and wanted notes on what wicks mean, what red vs green means,
   and which patterns are bullish/bearish.

   Rendered below the chart on the SEPA candidate detail page. Collapsed
   by default with an expand toggle so it doesn't crowd the chart for
   users who already know candles.
*/
import { useState } from 'react';

export function CandleAnatomyExplainer() {
  const [open, setOpen] = useState(false);

  return (
    <section
      style={{
        margin: '0.6rem 0 0',
        padding: '0.6rem 0.9rem',
        border: '1px solid var(--rule, #ddd)',
        borderLeft: '4px solid #f59e0b',
        borderRadius: 4,
        background: 'var(--bg-raised)',
      }}
    >
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'none',
          border: 0,
          color: 'var(--ink, inherit)',
          fontSize: '0.85rem',
          padding: 0,
          cursor: 'pointer',
          width: '100%',
          textAlign: 'left',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <span>
          <span style={{ marginRight: '0.4rem' }}>📈</span>
          <strong>How to read this chart</strong>
          <span style={{ color: 'var(--cm-slate)', marginLeft: '0.5rem', fontSize: '0.78rem' }}>
            candles, wicks, and what they tell you
          </span>
        </span>
        <span style={{ color: 'var(--cm-slate)', fontSize: '0.8rem' }}>
          {open ? '▲ hide' : '▼ explain'}
        </span>
      </button>

      {open && (
        <div style={{ marginTop: '0.7rem', fontSize: '0.82rem', lineHeight: 1.55 }}>
          {/* Color rules */}
          <SectionHead>1 · The body color tells you who won the day</SectionHead>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '0.5rem', marginTop: '0.3rem' }}>
            <ColorCard
              color="#10b981"
              label="GREEN body"
              meaning="Close > Open"
              detail="Buyers won the session. The price closed higher than it opened. Bullish day."
            />
            <ColorCard
              color="#ef4444"
              label="RED body"
              meaning="Close < Open"
              detail="Sellers won the session. The price closed lower than it opened. Bearish day."
            />
            <ColorCard
              color="#888"
              label="DOJI (thin)"
              meaning="Close ≈ Open"
              detail="Indecision. Neither side won. Often a turning point if it shows up after a strong trend."
            />
          </div>

          <div style={{
            marginTop: '0.5rem',
            fontSize: '0.74rem',
            color: 'var(--cm-slate)',
            fontStyle: 'italic',
          }}>
            The body shows the open-to-close range. The TOP of a green body is the close;
            the TOP of a red body is the open. Same body, opposite ends mean different things —
            this is the most common beginner confusion.
          </div>

          {/* Wicks */}
          <SectionHead>2 · The wicks (thin lines) show where price went but came back</SectionHead>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.5rem', marginTop: '0.3rem' }}>
            <WickCard
              label="UPPER wick (sticking up)"
              meaning="High of the day, rejected"
              detail="Price tried to push higher, sellers slapped it down. Long upper wick = 'rejection at the top' = bearish signal. Worse if it's at resistance."
              color="#ef4444"
            />
            <WickCard
              label="LOWER wick (sticking down)"
              meaning="Low of the day, bought back up"
              detail="Price tried to fall, buyers stepped in. Long lower wick = 'rejection at the bottom' = bullish signal. Especially powerful at support or a moving average."
              color="#10b981"
            />
          </div>

          <div style={{
            marginTop: '0.5rem',
            fontSize: '0.74rem',
            color: 'var(--cm-slate)',
            fontStyle: 'italic',
          }}>
            Wicks tell you where the market <em>tested</em>, not where it agreed to stay. A wick
            below your stop intraday is NOT the same as a close below your stop — this is exactly
            why Minervini's rule says "evaluate at close, not on wicks."
          </div>

          {/* Combo patterns */}
          <SectionHead>3 · Combos worth recognizing</SectionHead>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.78rem', marginTop: '0.3rem' }}>
            <thead>
              <tr style={{ color: 'var(--cm-slate)', textAlign: 'left' }}>
                <th style={{ padding: '0.25rem 0.4rem 0.25rem 0' }}>Shape</th>
                <th style={{ padding: '0.25rem 0.4rem' }}>Name</th>
                <th style={{ padding: '0.25rem 0' }}>What it usually means</th>
              </tr>
            </thead>
            <tbody>
              <Row
                shape="Green body + long lower wick"
                name="Hammer"
                meaning="Bullish. Sellers tried, buyers won. Strong reversal signal at the bottom of a pullback."
              />
              <Row
                shape="Red body + long upper wick"
                name="Shooting star"
                meaning="Bearish. Buyers tried, sellers won. Reversal signal at the top of a run."
              />
              <Row
                shape="Small body + long wicks both sides"
                name="Doji / Spinning top"
                meaning="Indecision. After a strong trend, often the first 'pause' before reversal."
              />
              <Row
                shape="Body fully engulfs prior candle"
                name="Engulfing"
                meaning="Bullish if green-engulfs-red, bearish if red-engulfs-green. Strong sentiment flip."
              />
              <Row
                shape="No wicks, big body"
                name="Marubozu"
                meaning="One-sided conviction. Trend bar — momentum likely continues next session."
              />
              <Row
                shape="Big green body on heavy volume"
                name="Breakout bar"
                meaning="What you want to see on a pivot day. Minervini wants 40-50% above avg volume."
              />
            </tbody>
          </table>

          {/* Real-time application */}
          <SectionHead>4 · Apply it to today's chart</SectionHead>
          <ul style={{ paddingLeft: '1.1rem', margin: '0.3rem 0 0' }}>
            <li style={{ marginBottom: 4 }}>
              <strong>Long lower wick on your position today?</strong> Buyers defending. Don't panic-sell on the intraday — wait for the close.
            </li>
            <li style={{ marginBottom: 4 }}>
              <strong>Long upper wick after a strong run?</strong> Profit-taking starting. Trail your stop tighter or sell partial.
            </li>
            <li style={{ marginBottom: 4 }}>
              <strong>Red body engulfing yesterday's green body?</strong> Sentiment flipped. If at a key MA (50-day), get defensive.
            </li>
            <li style={{ marginBottom: 4 }}>
              <strong>Several dojis in a row at the highs?</strong> Trend exhaustion. Lock in gains; don't add.
            </li>
          </ul>

          <div style={{
            marginTop: '0.7rem',
            padding: '0.5rem 0.7rem',
            background: 'rgba(245, 158, 11, 0.08)',
            borderLeft: '3px solid #f59e0b',
            borderRadius: 3,
            fontSize: '0.78rem',
            lineHeight: 1.5,
          }}>
            <strong style={{ color: '#f59e0b' }}>Key insight:</strong> The body matters more than
            the wick for daily decisions. A scary -8% intraday wick that closes flat (no body)
            is just noise. A small -2% red body that closes weak below the 50-day on heavy
            volume is the real signal. Train your eye on bodies first, wicks second.
          </div>
        </div>
      )}
    </section>
  );
}

function SectionHead({ children }: { children: React.ReactNode }) {
  return (
    <h4 style={{
      margin: '0.9rem 0 0',
      fontSize: '0.78rem',
      color: '#f59e0b',
      letterSpacing: '0.06em',
      textTransform: 'uppercase',
    }}>{children}</h4>
  );
}

function ColorCard({ color, label, meaning, detail }: {
  color: string; label: string; meaning: string; detail: string;
}) {
  return (
    <div style={{
      padding: '0.5rem 0.7rem',
      background: 'rgba(255,255,255,0.03)',
      borderLeft: `3px solid ${color}`,
      borderRadius: 3,
    }}>
      <div style={{ color, fontWeight: 700, fontSize: '0.78rem' }}>
        <span style={{
          display: 'inline-block',
          width: 14, height: 18,
          background: color,
          marginRight: '0.4rem',
          verticalAlign: 'middle',
        }} />
        {label}
      </div>
      <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 2 }}>{meaning}</div>
      <div style={{ fontSize: '0.76rem', marginTop: '0.3rem', lineHeight: 1.4 }}>{detail}</div>
    </div>
  );
}

function WickCard({ label, meaning, detail, color }: {
  label: string; meaning: string; detail: string; color: string;
}) {
  return (
    <div style={{
      padding: '0.5rem 0.7rem',
      background: 'rgba(255,255,255,0.03)',
      borderLeft: `3px solid ${color}`,
      borderRadius: 3,
    }}>
      <div style={{ color, fontWeight: 700, fontSize: '0.78rem' }}>{label}</div>
      <div className="mono" style={{ fontSize: '0.7rem', color: 'var(--cm-slate)', marginTop: 2 }}>{meaning}</div>
      <div style={{ fontSize: '0.76rem', marginTop: '0.3rem', lineHeight: 1.4 }}>{detail}</div>
    </div>
  );
}

function Row({ shape, name, meaning }: { shape: string; name: string; meaning: string }) {
  return (
    <tr style={{ borderTop: '1px dashed var(--hairline, #444)' }}>
      <td style={{ padding: '0.32rem 0.4rem 0.32rem 0', fontSize: '0.76rem' }}>{shape}</td>
      <td style={{ padding: '0.32rem 0.4rem', fontWeight: 600 }}>{name}</td>
      <td style={{ padding: '0.32rem 0', fontSize: '0.76rem' }}>{meaning}</td>
    </tr>
  );
}
