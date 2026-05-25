/* KellSetupInfoPanel — context-sensitive sticky sidebar for the /kell
 * page. Mirror of SepaSetupInfoPanel: tier label, one-line pitch,
 * Entry/Stop/Target rules, hold time, risk note, and (where applicable)
 * a real-world example from market history.
 *
 * Content sourced from Oliver Kell's "Victory in Stock Trading" (2021)
 * and his Cycle of Price Action framework. The rules and tiers are
 * Kell's published criteria, not invented.
 */
import type { KellTab } from './KellSetupTabs';

const TIER_COLOR: Record<string, string> = {
  safe:        '#22c55e',
  safe_mod:    '#84cc16',
  moderate:    '#facc15',
  aggressive:  '#fb923c',
  defensive:   '#ef4444',
  neutral:     '#9aa8c8',
};

type InfoBlock = {
  title:     string;
  tier:      string;
  tierLabel: string;
  blurb:     string;
  entry:     string;
  stop:      string;
  target:    string;
  hold:      string;
  riskNote:  string;
  example?:  string;
};

const INFO: Record<KellTab, InfoBlock> = {
  all: {
    title:     'All Kell setups',
    tier:      'neutral',
    tierLabel: 'COMBINED FEED',
    blurb:     "Every detection across the six Cycle of Price Action scanners. Sorted by R:R within each kind — drill into a specific tab for pattern-specific entry rules.",
    entry:     'Per-card trigger — varies by pattern',
    stop:      'Per-card stop — pattern-specific',
    target:    'Per-card target — Kell\'s typical first-scale',
    hold:      'Pattern-specific',
    riskNote:  "Combined view — each Kell pattern has its own risk profile. Open the per-pattern tab on the left to see the canonical rules and risk notes.",
  },

  volatility_compression: {
    title:     'Volatility Compression',
    tier:      'safe',
    tierLabel: 'SAFE',
    blurb:     "Kell's ATR-based contraction setup. Recent volatility (ATR_10) is at least 30% below the long-term ATR (ATR_50), the last-week range is under 4% of price, and volume is drying up — the spring is coiled.",
    entry:     '5-day high × 1.005 (breakout above the coil)',
    stop:      'Just below the 5-day low — the coil floor',
    target:    'Trigger × 1.10 (Kell\'s typical 10% first leg)',
    hold:      '1–3 weeks (until volatility expands)',
    riskNote:  "If price breaks the coil low BEFORE breaking out, the compression resolves down — exit immediately. Compressions can extend for weeks; don't anticipate the break, wait for it.",
    example:   'NVDA mid-2023 multi-week consolidations, MSFT early-2024 base coil',
  },

  wedge_drop: {
    title:     'Wedge Drop',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    blurb:     "Kell's 'shakeout that resolves to upside.' A Stage-2 leader pulls back 3-7 days in a descending wedge that touches MA21 or MA50, then prints a bullish reversal candle on volume. Institutions step in at the moving average.",
    entry:     'Reversal candle high + 1¢ on confirmation day',
    stop:      'Just below the reversal candle low',
    target:    'Trigger × 1.08 (typical 8% first scale)',
    hold:      '3–10 trading days',
    riskNote:  "If the reversal candle low fails the next session, the wedge is breaking down — exit. False wedge drops are common on the first try; Kell suggests waiting for a CLOSE above trigger before adding size.",
    example:   'NVDA Aug 2023 (post-earnings wedge drop into MA21), AAPL late-2024 wedge resolutions',
  },

  base_break: {
    title:     'Base Break',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    blurb:     "Classic 30-day high breakout on volume. Kell's name for the cup-with-handle / VCP-completion entry — the textbook breakout from a base, confirmed by institutional volume.",
    entry:     '30-day pivot + 1¢ (entry on confirmation pullback or re-test)',
    stop:      'Below the 15-session base low',
    target:    'Trigger × 1.10 (Kell\'s typical 10% measured move)',
    hold:      '5–20 trading days (short window — already broken out)',
    riskNote:  "Breakout failures happen in clusters. If the broader market is choppy (regime not 'confirmed uptrend'), reduce size or skip — the win rate falls sharply when index volatility expands.",
    example:   'MSFT Dec 2023 cup-with-handle, META Feb 2024 base break',
  },

  reversal_extension: {
    title:     'Reversal Extension',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     "Kell's 'buy the bottom turn.' After a recent swing low (3-20 sessions ago), price extends above the prior 5-day high on a bullish close with >1.5× volume — the turn is confirmed, not anticipated.",
    entry:     "Today's close × 1.005 (small buffer over the extension)",
    stop:      'Just below the recent swing low',
    target:    'Trigger × 1.15 (15% typical first-leg target)',
    hold:      '5–20 days',
    riskNote:  "Stops are wider than other Kell setups because the swing low is deeper. Size SMALLER than your base-break positions — the volatility floor is further away, which means more $$ at risk per share.",
    example:   'TSLA Jan 2023 bottom turn, NVDA Oct 2022 reversal extension',
  },

  power_trend: {
    title:     'Power Trend',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     "Kell's stair-step continuation. A Stage-2 leader making higher highs (>=2 distinct HHs in 30 days, pullbacks under 10%) while holding above the 21-day EMA. Each pullback to MA21 is a fresh continuation entry on the rail.",
    entry:     "Today's close × 1.005 (continuation buy above MA21)",
    stop:      'MA21 × 0.98 (below MA21 with 2% buffer)',
    target:    'Trigger × 1.12 (next stair-step, ~12% leg)',
    hold:      '2–6 weeks (until MA21 break)',
    riskNote:  "When MA21 breaks on a CLOSE, the power trend is over — exit cleanly. Don't anchor to the prior leg's targets; the trend has changed character. A failed MA21 hold on rising volume is especially toxic — that's distribution.",
    example:   'NVDA 2023-2024 multiple stair-steps, COST 2024 power trend along MA21',
  },

  climax_run: {
    title:     'Climax Run · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    blurb:     "Not an entry — this is Kell's blow-off / exhaustion detection. A 50%+ run in 30 days prints a wide-range bar (>5% intraday) on 2.5×+ volume, closing red or in the lower third of range, while price is 30%+ stretched above MA50. Institutions are distributing into euphoria.",
    entry:     '— (NO ENTRY — this is a sell signal)',
    stop:      '— (no stop applies)',
    target:    '— (no target — TAKE PROFITS instead)',
    hold:      "— (act now: lighten 1/3 to 1/2 of the position)",
    riskNote:  "When you see this pattern on a name you OWN, scale out. Climax-run tops can give back 30-50% in days. Don't try to 'short' a Climax Run — Kell explicitly warns against it; the bounce can be violent before the real top.",
    example:   'GME Jan 2021 (textbook climax run), AMC June 2021, NVDA blow-off bars 2024',
  },
};

interface Props {
  activeTab: KellTab;
}

export function KellSetupInfoPanel({ activeTab }: Props) {
  const info = INFO[activeTab];
  if (!info) return null;
  const color = TIER_COLOR[info.tier] || TIER_COLOR.neutral;
  return (
    <aside
      style={{
        flex:           '0 0 320px',
        position:       'sticky',
        top:            '1rem',
        alignSelf:      'flex-start',
        padding:        '1rem 1.1rem',
        background:     'rgba(20,20,22,0.65)',
        border:         `1px solid ${color}33`,
        borderLeft:     `4px solid ${color}`,
        borderRadius:   8,
        color:          '#cfcfd4',
        fontSize:       '0.84rem',
        lineHeight:     1.55,
      }}
      aria-label={`Kell setup info for ${info.title}`}
    >
      <div
        style={{
          fontSize:       '0.68rem',
          letterSpacing:  '0.1em',
          textTransform:  'uppercase',
          color:          color,
          fontWeight:     700,
          marginBottom:   4,
        }}
      >
        {info.tierLabel}
      </div>
      <h3
        style={{
          margin:    '0 0 0.6rem 0',
          fontSize:  '1.08rem',
          fontWeight: 700,
          color:     '#f3e8c8',
        }}
      >
        {info.title}
      </h3>
      <p style={{ margin: '0 0 0.9rem 0', fontSize: '0.86rem' }}>{info.blurb}</p>

      <Row label="Entry"  value={info.entry} />
      <Row label="Stop"   value={info.stop}   accent="#ef4444" />
      <Row label="Target" value={info.target} accent="#22c55e" />
      <Row label="Hold"   value={info.hold} />

      <div
        style={{
          marginTop:    '0.85rem',
          padding:      '0.5rem 0.65rem',
          background:   'rgba(239,68,68,0.08)',
          border:       '1px solid rgba(239,68,68,0.25)',
          borderRadius: 6,
          fontSize:     '0.76rem',
          color:        '#fca5a5',
        }}
      >
        <strong style={{ color: '#fca5a5' }}>⚠ Risk: </strong>{info.riskNote}
      </div>

      {info.example && (
        <div
          style={{
            marginTop: '0.7rem',
            fontSize:  '0.72rem',
            color:     '#9a9aa3',
            fontStyle: 'italic',
          }}
        >
          Examples: {info.example}
        </div>
      )}
    </aside>
  );
}

function Row({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div
      style={{
        display:        'grid',
        gridTemplateColumns: '64px 1fr',
        gap:            '0.5rem',
        margin:         '0.25rem 0',
        fontSize:       '0.78rem',
      }}
    >
      <span
        style={{
          color:         '#9a9aa3',
          textTransform: 'uppercase',
          fontSize:      '0.66rem',
          letterSpacing: '0.06em',
          paddingTop:    2,
        }}
      >
        {label}
      </span>
      <span style={{ color: accent || '#cfcfd4' }}>{value}</span>
    </div>
  );
}
