/* SetupExplainer — collapsible "How to read this setup" card.
 *
 * Matches the CandleAnatomyExplainer pattern (left rule, expand toggle,
 * sectioned body with sub-cards). Renders inside Setups.tsx, one per tab.
 *
 * Each kind has its own explainer: what the setup is, what the
 * trigger/stop/target mean, how to actually place the orders at
 * Fidelity, what to avoid. Written for the user's stated context
 * (busy day, ≤30 min, $40k Fidelity account, bull-regime only).
 *
 * Collapsed by default — power users don't need this every visit. The
 * first-time user expands once, reads, then collapses.
 */
import { useState, type ReactNode } from 'react';

type Kind = 'peg' | 'orb' | 'inside_day';

type Field = {
  label:   string;
  meaning: string;
  detail:  string;
};

type Pitfall = {
  title: string;
  body:  string;
};

type ExplainerSpec = {
  kind:      Kind;
  emoji:     string;
  title:     string;
  oneLiner:  string;
  color:     string;
  hold:      string;
  target:    string;
  /** "Anatomy" — what the four numbers on every row actually mean. */
  fields:    Field[];
  /** Step-by-step on a sample setup, with concrete numbers. */
  worked:    { label: string; line: string }[];
  /** How to actually execute at Fidelity. */
  fidelity:  string[];
  /** Things that go wrong when people trade this naively. */
  pitfalls:  Pitfall[];
};


const SPECS: Record<Kind, ExplainerSpec> = {
  peg: {
    kind:     'peg',
    emoji:    '⚡',
    color:    '#3b82f6',
    title:    'PEG — Power Earnings Gap',
    oneLiner: "A quality stock just gapped ≥ 5% on ≥ 4× volume. You wait for the gap-day high to be taken out on a later session, then enter.",
    hold:     '3 to 10 days',
    target:   '3% to 8% (first take-profit at 6%)',
    fields: [
      {
        label:   'TRIGGER',
        meaning: 'gap-day high + 1¢',
        detail:  "Don't anticipate. Don't buy at market open hoping it runs. The signal is the market taking out the gap day's high on a later session — buyers proving they want it again. Buy-stop at this price, never market buy.",
      },
      {
        label:   'STOP',
        meaning: 'gap-day low − 1¢',
        detail:  "If price closes below the gap-day low, the setup is dead. Sell at next open. Never adjust this down — Minervini's #1 rule. The risk row tells you what % loss this stop equals.",
      },
      {
        label:   'TARGET',
        meaning: 'trigger × 1.06',
        detail:  "First take-profit at ~6% above entry. This is a conservative first scale-out — Minervini's published PEG ranges go 5-15%. Take 1/2 at target, trail the rest with a 21-day EMA or close-below-10-day stop.",
      },
      {
        label:   'R:R',
        meaning: 'reward ÷ risk',
        detail:  "Higher is better. Anything below 1.5 means the gap-day low is too far below the high — the stop swallows too much. We filter out R:R < 1.0 at the scanner level so the rows you see should be 1.2+.",
      },
    ],
    worked: [
      { label: 'Setup',   line: 'NVDA gapped from $138 close → $148 open on earnings beat. Day-day volume 4.8× average. Gap-day H/L: $151.20 / $146.80.' },
      { label: 'Wait',    line: 'Day 1 closes at $149.40. Day 2 ranges $147-150, no break. Day 3 opens $149, ticks up to $151.21 — trigger.' },
      { label: 'Entry',   line: 'Buy-stop $151.21 filled at $151.30. Risk = (151.30 − 146.79) = $4.51 per share = ~3% of capital.' },
      { label: 'Mgmt',    line: 'Day 5 hits $160.40 = +6% — sell 1/2. Move stop on remainder to breakeven $151.30.' },
      { label: 'Exit',    line: 'Day 8 closes below 21-EMA = exit remaining half. Net result on full position: roughly +4% to +5%, 1 week hold.' },
    ],
    fidelity: [
      'On Fidelity Active Trader Pro: place a BUY STOP order at the trigger price, GTC (good-till-cancelled, 60 days).',
      'Simultaneously place a SELL STOP-LOSS at the stop price, also GTC. (Bracket: only triggers if buy fills.)',
      'Optional: SELL LIMIT at the target for the half-out leg, GTC.',
      'On phone? Fidelity Mobile → Trade → Orders → Conditional Order → Bracket. Same three legs.',
      'Set a price alert at trigger so you know when to manage the position (Fidelity → Quote → bell icon).',
    ],
    pitfalls: [
      {
        title:   "Buying on day 1 at the gap-day open",
        body:    "The gap-day open is NOT the entry. ~40% of gaps fill back into the prior range within 5 days. Wait for the next session to break the gap-day HIGH — that's the signal that buyers came back.",
      },
      {
        title:   "Chasing if price runs past the trigger",
        body:    "If you missed the trigger and price is already 3%+ above it, skip the trade. The risk-to-stop is now too wide. There will be other PEGs — let this one go.",
      },
      {
        title:   "Ignoring the volume confirmation requirement",
        body:    "A 5% gap on normal volume is not a PEG, it's noise. The scanner requires 4× average volume specifically because that's what separates institutional-driven gaps from retail-news pops that fade.",
      },
    ],
  },

  orb: {
    kind:     'orb',
    emoji:    '🎯',
    color:    '#10b981',
    title:    'ORB — Opening Range Breakout',
    oneLiner: "From 9:30 to 9:45 ET, the market sets a high and a low. You buy a break of the high on real volume, then exit by close. Same-day trade.",
    hold:     'intraday only (close by 3:55 ET)',
    target:   '1% to 2% (often = the size of the opening range itself)',
    fields: [
      {
        label:   'TRIGGER',
        meaning: '9:30-9:45 high + 1¢',
        detail:  "The opening range is set in the first 15 minutes. Buy-stop just above the high. Stays valid until 3:55 ET (the watcher checks every minute for a confirmed break on volume).",
      },
      {
        label:   'STOP',
        meaning: '9:30-9:45 low − 1¢',
        detail:  "If price breaks below the opening-range low after triggering, the setup has failed. Exit immediately. No discretion.",
      },
      {
        label:   'TARGET',
        meaning: 'trigger + 1 × range',
        detail:  "First profit-take at 1× the opening range above the trigger (i.e. 1:1 R:R). Example: range was $148-150, trigger $150.01, target $152. Some traders use 1.5× or 2×; 1× is the conservative starting point.",
      },
      {
        label:   'CLOSE-BY',
        meaning: '3:55 ET hard exit',
        detail:  "If neither stop nor target hit, FLATTEN at 3:55 ET regardless. ORB doesn't carry overnight. You came in clean, you leave clean.",
      },
    ],
    worked: [
      { label: 'Setup',  line: 'CRWD opening range 9:30-9:45: H = $312.40, L = $309.80. Range = $2.60 = 0.83% of price. Range pct is within the 0.4%-3.5% acceptable band.' },
      { label: 'Wait',   line: '10:12 ET: minute bar closes at $312.55 with volume above the opening-range average. Trigger confirmed.' },
      { label: 'Entry',  line: 'Buy-stop $312.41 filled at $312.48. Stop $309.79. Target $315.00 (trigger + $2.60).' },
      { label: 'Mgmt',   line: '11:40 ET: price prints $315.10. Sell 1/2 at target. Move stop on remainder to breakeven $312.48.' },
      { label: 'Exit',   line: '2:18 ET: price stalls at $315.50. Take remaining half off at market. Net: ~1.4% in 4 hours.' },
    ],
    fidelity: [
      'After the 🎯 push notification (typically between 9:47 and 10:30 ET): tap into the ticker page.',
      'On Fidelity: place a BUY STOP order at the trigger price, GOOD FOR DAY ONLY (NOT GTC — this is intraday).',
      'Bracket with a SELL STOP-LOSS at the stop and a SELL LIMIT at the target. All day-only.',
      'Set a 3:50 ET alarm on your phone to manually flatten any remaining position if neither bracket fires.',
      'Margin reminder: ORB uses day-trading buying power. With $40k cash, you have up to $160k DT BP — way more than you need for a 1% target.',
    ],
    pitfalls: [
      {
        title:   "Buying the open instead of the breakout",
        body:    "The 9:30 print is NOT the entry. ~60% of opens reverse within 15 minutes. The OPENING RANGE is set BY 9:45 — that's why we wait.",
      },
      {
        title:   "Ignoring the volume requirement on the trigger bar",
        body:    "A break on dry volume is a fake-out 70% of the time. Our watcher requires the trigger bar to have ≥ 50% of the opening-range average minute volume specifically to filter these out.",
      },
      {
        title:   "Holding overnight 'just because it's still going up'",
        body:    "Don't. ORB is a one-day strategy. Overnight risk is a different game (gaps against you, news, premarket). If you like the name for longer, that's a SEPA or PEG setup — book the ORB profit and re-enter on the next setup type.",
      },
    ],
  },

  inside_day: {
    kind:     'inside_day',
    emoji:    '📦',
    color:    '#f59e0b',
    title:    'Inside-Day Breakout',
    oneLiner: "Yesterday's whole bar (high to low) sat INSIDE the day before's range. That's a coiled spring — buy a break of yesterday's high.",
    hold:     '1 to 3 days',
    target:   '1.5% to 3% (first take at +1.5× the inside-day range)',
    fields: [
      {
        label:   'TRIGGER',
        meaning: "yesterday's high + 1¢",
        detail:  "An inside day is a compression bar — supply and demand balanced within a tighter range than the prior day. The break of the upper bound is the signal that compression has resolved upward.",
      },
      {
        label:   'STOP',
        meaning: "yesterday's low − 1¢",
        detail:  "If price closes below yesterday's low, the compression failed — supply won. Exit. This is a tight stop by construction (inside the inside day), which is half the appeal of the setup.",
      },
      {
        label:   'TARGET',
        meaning: 'trigger + 1.5 × range',
        detail:  "First take-profit at 1.5× the inside-day range above the trigger. Mechanical. If you want to ride longer, trail with a 5-day moving-average close-below.",
      },
      {
        label:   'R:R',
        meaning: 'reward ÷ risk',
        detail:  "We filter to R:R ≥ 1.2 at the scanner. The setup is mathematically forced: stop and target are both computed off the same range, so the ratio depends on how the close sits within the range.",
      },
    ],
    worked: [
      { label: 'Setup',  line: "AVGO: Yesterday H/L = $1,742 / $1,728 (range $14). Day-before H/L = $1,750 / $1,725. Yesterday's bar is fully inside. Close $1,738 — in the upper half = bullish bias." },
      { label: 'Wait',   line: 'Tonight: place buy-stop at $1,742.01 and sell-stop at $1,727.99. Go to bed.' },
      { label: 'Entry',  line: 'Tomorrow 9:42 ET: buy-stop fills at $1,742.50. Risk = $14.51 per share = ~0.83%.' },
      { label: 'Mgmt',   line: '11:30 ET: price hits $1,763 (trigger + 1.5×$14 = $1,763). Sell 1/2 at target. Move stop on remainder to breakeven.' },
      { label: 'Exit',   line: 'Day 2 closes below 5-day MA = exit. Net: ~1.5% in two sessions, mostly hands-off.' },
    ],
    fidelity: [
      "Nightly (after the 6:35 PM ET scan push): open Setups → Inside-Day tab.",
      "For each setup you want to take: Fidelity → place a BUY STOP at the trigger, GTC.",
      "Bracket with SELL STOP-LOSS at the stop and SELL LIMIT at the target. All GTC.",
      "If the buy-stop doesn't fill within 2 days, it auto-expires on our side — cancel the standing Fidelity orders.",
      "Inside-Day is the most hands-off of the three. Set the orders and don't watch the screen.",
    ],
    pitfalls: [
      {
        title:   "Inside days that aren't really inside",
        body:    "An inside day requires both the high AND the low to be inside. Today's high < yesterday's high AND today's low > yesterday's low. The scanner enforces this strictly — but if you spot setups manually, double-check.",
      },
      {
        title:   "Tiny inside days on illiquid stocks",
        body:    "A 0.2% inside day is just a quiet session, not a compression. The scanner requires range ≥ 0.5% of close. Below that, the breakout payoff doesn't cover the spread + slippage.",
      },
      {
        title:   "Holding past day 3 hoping for more",
        body:    "Inside-day breakouts that haven't moved by day 3 usually don't. Time-stop at 48 hours after entry — flat it and find a fresh setup.",
      },
    ],
  },
};


function SectionHead({ children }: { children: ReactNode }) {
  return (
    <h4 style={{
      margin: '0.9rem 0 0.4rem',
      fontSize: '0.78rem',
      letterSpacing: '0.08em',
      textTransform: 'uppercase',
      color: 'var(--cm-slate)',
      fontWeight: 700,
    }}>
      {children}
    </h4>
  );
}


function FieldCard({ field, color }: { field: Field; color: string }) {
  return (
    <div style={{
      padding: '0.5rem 0.7rem',
      background: 'rgba(20,20,22,0.5)',
      border: '1px solid rgba(255,255,255,0.06)',
      borderLeft: `2px solid ${color}`,
      borderRadius: 4,
    }}>
      <div style={{
        fontSize: '0.66rem',
        fontWeight: 700,
        letterSpacing: '0.1em',
        color,
        marginBottom: 3,
      }}>
        {field.label}
      </div>
      <div className="mono" style={{
        fontSize: '0.76rem',
        color: 'var(--ink, inherit)',
        marginBottom: 4,
      }}>
        = {field.meaning}
      </div>
      <div style={{ fontSize: '0.78rem', lineHeight: 1.5, color: '#cfcfd4' }}>
        {field.detail}
      </div>
    </div>
  );
}


function PitfallCard({ p, color }: { p: Pitfall; color: string }) {
  return (
    <div style={{
      padding: '0.5rem 0.7rem',
      background: 'rgba(239,68,68,0.05)',
      borderLeft: `2px solid ${color}`,
      borderRadius: 4,
      marginBottom: '0.4rem',
    }}>
      <div style={{ fontWeight: 700, fontSize: '0.82rem', marginBottom: 3 }}>
        ⚠️ {p.title}
      </div>
      <div style={{ fontSize: '0.78rem', lineHeight: 1.5, color: '#cfcfd4' }}>
        {p.body}
      </div>
    </div>
  );
}


export function SetupExplainer({ kind }: { kind: Kind }) {
  const spec = SPECS[kind];
  const [open, setOpen] = useState(false);

  return (
    <section
      style={{
        margin: '0.4rem 0 1rem',
        padding: '0.6rem 0.9rem',
        border: '1px solid rgba(255,255,255,0.08)',
        borderLeft: `4px solid ${spec.color}`,
        borderRadius: 5,
        background: 'rgba(20,20,22,0.65)',
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
          fontFamily: 'inherit',
        }}
      >
        <span>
          <span style={{ marginRight: '0.4rem' }}>{spec.emoji}</span>
          <strong>How to read {spec.title}</strong>
          <span style={{ color: '#9a9aa3', marginLeft: '0.5rem', fontSize: '0.76rem' }}>
            anatomy · worked example · Fidelity steps · pitfalls
          </span>
        </span>
        <span style={{ color: '#9a9aa3', fontSize: '0.78rem' }}>
          {open ? '▲ hide' : '▼ explain'}
        </span>
      </button>

      {open && (
        <div style={{ marginTop: '0.7rem', fontSize: '0.84rem', lineHeight: 1.55 }}>
          {/* One-liner header */}
          <div style={{
            padding: '0.5rem 0.7rem',
            background: `rgba(20,20,22,0.6)`,
            borderLeft: `2px solid ${spec.color}`,
            borderRadius: 4,
            fontSize: '0.86rem',
            marginBottom: '0.3rem',
          }}>
            <strong style={{ color: spec.color }}>In one sentence:</strong>{' '}
            {spec.oneLiner}
          </div>

          <div style={{ display: 'flex', gap: '1.4rem', fontSize: '0.74rem',
                        color: '#9a9aa3', marginBottom: '0.2rem' }}>
            <span>Hold: <strong style={{ color: '#cfcfd4' }}>{spec.hold}</strong></span>
            <span>Target: <strong style={{ color: '#cfcfd4' }}>{spec.target}</strong></span>
          </div>

          {/* Anatomy — what the four fields on each row mean */}
          <SectionHead>1 · What the row's four numbers mean</SectionHead>
          <div style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: '0.5rem',
            marginTop: '0.3rem',
          }}>
            {spec.fields.map(f => (
              <FieldCard key={f.label} field={f} color={spec.color} />
            ))}
          </div>

          {/* Worked example */}
          <SectionHead>2 · One full worked example</SectionHead>
          <div style={{
            background: 'rgba(20,20,22,0.5)',
            border: '1px solid rgba(255,255,255,0.06)',
            borderRadius: 4,
            padding: '0.5rem 0.7rem',
          }}>
            {spec.worked.map((w, i) => (
              <div key={i} style={{
                display: 'grid',
                gridTemplateColumns: '60px 1fr',
                gap: '0.5rem',
                padding: '0.25rem 0',
                borderBottom: i < spec.worked.length - 1 ? '1px dashed rgba(255,255,255,0.07)' : 'none',
                fontSize: '0.78rem',
                lineHeight: 1.45,
              }}>
                <span style={{
                  fontSize: '0.66rem',
                  fontWeight: 700,
                  color: spec.color,
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  paddingTop: 2,
                }}>
                  {w.label}
                </span>
                <span style={{ color: '#cfcfd4' }}>{w.line}</span>
              </div>
            ))}
          </div>

          {/* Fidelity steps */}
          <SectionHead>3 · Place at Fidelity in 60 seconds</SectionHead>
          <ol style={{ margin: '0.2rem 0 0', paddingLeft: '1.2rem', fontSize: '0.8rem',
                       lineHeight: 1.55, color: '#cfcfd4' }}>
            {spec.fidelity.map((step, i) => (
              <li key={i} style={{ marginBottom: 3 }}>{step}</li>
            ))}
          </ol>

          {/* Pitfalls */}
          <SectionHead>4 · Common ways this goes wrong</SectionHead>
          {spec.pitfalls.map((p, i) => (
            <PitfallCard key={i} p={p} color="#ef4444" />
          ))}
        </div>
      )}
    </section>
  );
}
