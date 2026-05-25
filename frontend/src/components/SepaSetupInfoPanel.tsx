/* SepaSetupInfoPanel — context-sensitive info card that explains the
 * currently-selected setup category. Renders to the right of the SEPA
 * results grid as a sticky sidebar.
 *
 * Each setup gets a structured card:
 *   - Tier label + risk color
 *   - One-line "what is this"
 *   - Entry / Stop / Target rules (Minervini's published criteria)
 *   - Typical hold time
 *   - Risk note ("when this fails")
 *
 * The content here is the Minervini-canon (or Pradeep Bonde for Episodic
 * Pivot) — text adapted from the books / public writings, not invented.
 */
import type { SepaTab } from './SepaSetupTabs';

const TIER_COLOR: Record<string, string> = {
  safe:        '#22c55e',
  safe_mod:    '#84cc16',
  moderate:    '#facc15',
  mod_agg:     '#f59e0b',
  aggressive:  '#fb923c',
  most_agg:    '#ef4444',
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

const INFO: Record<SepaTab, InfoBlock> = {
  all: {
    title:     'All Candidates',
    tier:      'neutral',
    tierLabel: 'FULL LIST',
    blurb:     "Every analyzed SEPA name, ranked by composite score. Risky (late-stage base) names sink to the bottom.",
    entry:     'Per-card pivot — varies by setup type',
    stop:      'Per-card stop — defaults to MA50 break or 7% below entry',
    target:    'Held until trend template breaks',
    hold:      'Multi-week to multi-month',
    riskNote:  "This is the universe view. Drill into a specific setup tab on the left for actionable entries.",
  },

  vcp: {
    title:     'Volatility Contraction Pattern (VCP)',
    tier:      'safe',
    tierLabel: 'SAFE',
    blurb:     "Minervini's textbook setup. A stock forms a series of progressively-tighter consolidations as volume dries up — the spring coils.",
    entry:     'Pivot point = last contraction\'s high + small buffer',
    stop:      'Just below the last contraction\'s low (typically 3–8% risk)',
    target:    '20–25% on the first leg; trail with the MA50',
    hold:      '4–16 weeks',
    riskNote:  'Failure = base breaks down through the contraction lows. Cut quickly — VCP failures often cascade.',
    example:   'NVDA 2023, MU 2017, AAPL 2020',
  },

  low_cheat: {
    title:     'Low Cheat',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    blurb:     'Earliest entry inside a forming VCP base — buy near the LOW of the handle, before the textbook pivot. Tighter stop, lower risk.',
    entry:     'Buy 0.5% above current close when price is in the lower third of the handle range',
    stop:      'Just below the handle low (tighter than full VCP)',
    target:    'First scale at the textbook pivot, then ride to VCP target',
    hold:      '4–12 weeks',
    riskNote:  'You\'re anticipating the breakout — if base breaks down, you\'re first to get stopped. Discipline matters.',
  },

  mid_cheat: {
    title:     'Mid Cheat',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    blurb:     'Mid-handle pullback entry. After 2+ contractions formed, buy on a higher low within the handle.',
    entry:     'Buy on a break above the previous contraction\'s high',
    stop:      'Just below the most recent contraction low',
    target:    'Pivot × 1.03 first, then full VCP target',
    hold:      '4–10 weeks',
    riskNote:  'If a third contraction goes deeper than the prior two, the base is failing — exit.',
  },

  bull_flag: {
    title:     'Bull Flag Continuation',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    blurb:     'A strong stock (Stage 2, RS ≥ 80) consolidates 5–15 days after a 15–30% leg up. Tight, low-volume flag with drying volume = continuation set up.',
    entry:     'Buy break of the flag high + 1 cent',
    stop:      'Just below the flag low',
    target:    'Measured-move: flag high + (60% of the prior leg up)',
    hold:      '5–20 trading days',
    riskNote:  'Flag depth > 15% from peak = base failing, not a flag. Volume rising during consolidation = distribution.',
    example:   'TSLA 2020 Q3, NVDA 2023 multiple flags',
  },

  peg: {
    title:     'Power Earnings Gap (PEG)',
    tier:      'mod_agg',
    tierLabel: 'MOD-AGG',
    blurb:     "Minervini's post-earnings setup. A SEPA-quality name gaps up 5%+ on 4×+ volume after earnings — the institutions just confirmed the thesis.",
    entry:     'Buy when price takes out the gap-day HIGH + 1 cent (often day 2-5)',
    stop:      'Just below the gap-day LOW',
    target:    'Trigger × 1.06 first scale, ride to typical Minervini 20%',
    hold:      '3–10 days',
    riskNote:  'If price closes below the gap-day low, setup is invalidated. Stale gap (> 5 days untriggered) loses statistical edge.',
  },

  high_cheat: {
    title:     'High Cheat',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     'Aggressive in-base entry just BELOW the pivot. You\'re front-running the breakout.',
    entry:     'Buy at pivot × 0.99 — front of the breakout candle',
    stop:      'Just below the most recent contraction low',
    target:    'Pivot × 1.05 first, ride VCP target',
    hold:      '2–8 weeks',
    riskNote:  'No buffer for false breakout. If the breakout fails, you eat the full retracement.',
  },

  episodic_pivot: {
    title:     'Episodic Pivot (Bonde)',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     'Pradeep Bonde\'s setup, endorsed by Minervini. ANY 8%+ gap on 5×+ volume from a fundamental catalyst (FDA, contract, guidance, earnings). No base required.',
    entry:     'Buy on the gap day open OR first pullback to VWAP',
    stop:      'Below the gap-day low (wide — these are volatile)',
    target:    'Hold for the drift; trail with 5-day moving average',
    hold:      '5–30 days',
    riskNote:  'No base = no support floor. If the catalyst was hype not substance, gap fills fast. Confirm catalyst quality before sizing up.',
    example:   'Most biotech FDA approvals, NVDA Aug 2023 guidance',
  },

  post_earnings_drift: {
    title:     'Post-Earnings Drift',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    blurb:     "Academic edge — stocks with strong earnings reactions continue trending for 1-90 days. Catches names you missed at the gap.",
    entry:     'Pullback to gap-day 5-day moving average OR breakout above today\'s close',
    stop:      'Below the gap-day low (the original support)',
    target:    'Gap-day high × 1.15 (typical drift magnitude)',
    hold:      '10–60 days',
    riskNote:  'Drift can stall if the broader market rolls over. Watch for distribution days clustering on the name.',
  },

  high_tight_flag: {
    title:     'High Tight Flag (HTF)',
    tier:      'most_agg',
    tierLabel: 'MOST AGGRESSIVE',
    blurb:     "Minervini's most aggressive setup. A stock runs 90–120%+ in 4–8 weeks, then consolidates only 15–25% in a tight 3–5 week flag. Rare, explosive when it triggers.",
    entry:     'Buy break of the flag high + 1 cent',
    stop:      'Below the flag low (wide stop, but the move is big)',
    target:    'Flag high × 1.30 (30%+ continuation typical)',
    hold:      '2–8 weeks',
    riskNote:  'Win rate is only ~50% — losers happen and the wide stop bites. Size SMALLER than VCP positions. Wait for clean flag — don\'t front-run.',
    example:   'GME 2021, BBBY 2022, AMC 2021',
  },
};

interface Props {
  activeTab: SepaTab;
}

export function SepaSetupInfoPanel({ activeTab }: Props) {
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
      aria-label={`Setup info for ${info.title}`}
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
