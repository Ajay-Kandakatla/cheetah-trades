/* SepaSetupInfoBanner — compact horizontal info banner that renders
 * directly below the SepaSetupTabs strip. Always visible (no scrolling
 * to find it), gives the user the "what is this setup" at a glance the
 * moment they click a tab.
 *
 * Complements the SepaSetupInfoPanel (right-side sticky sidebar): the
 * sidebar has the full breakdown (entry/stop/target/hold/risk), this
 * banner gives the elevator pitch in one horizontal row.
 *
 * Hidden on the "all" tab — the All Candidates list doesn't need a
 * banner since it IS the default view.
 */
import type { SepaTab } from './SepaSetupTabs';

const TIER_COLOR: Record<string, string> = {
  safe:       '#22c55e',
  safe_mod:   '#84cc16',
  moderate:   '#facc15',
  mod_agg:    '#f59e0b',
  aggressive: '#fb923c',
  most_agg:   '#ef4444',
  neutral:    '#9aa8c8',
};

type BannerInfo = {
  title:     string;
  tier:      string;
  tierLabel: string;
  pitch:     string;     // one-line "what is this setup"
  entry:     string;     // short entry rule
  stop:      string;     // short stop rule
  hold:      string;     // hold time
};

const INFO: Partial<Record<SepaTab, BannerInfo>> = {
  vcp: {
    title:     'Volatility Contraction Pattern',
    tier:      'safe',
    tierLabel: 'SAFE',
    pitch:     "Minervini's textbook base — multiple tightening contractions, drying volume. The classic spring-coil setup.",
    entry:     'Pivot point',
    stop:      'Last contraction low',
    hold:      '4–16 weeks',
  },
  low_cheat: {
    title:     'Cheat — Low',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    pitch:     'Earliest entry inside a forming VCP base — buy near the LOW of the handle, before the textbook pivot.',
    entry:     'Near handle low',
    stop:      'Just below handle low',
    hold:      '4–12 weeks',
  },
  mid_cheat: {
    title:     'Cheat — Mid',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    pitch:     'Mid-handle pullback entry. After 2+ contractions formed, buy on a higher low within the handle.',
    entry:     'Mid-handle pullback',
    stop:      'Below recent contraction low',
    hold:      '4–10 weeks',
  },
  bull_flag: {
    title:     'Bull Flag Continuation',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    pitch:     'Stage 2 stock consolidates 5–15 days after a 15–30% leg up. Tight flag with drying volume = continuation set up.',
    entry:     'Break of flag high',
    stop:      'Just below flag low',
    hold:      '5–20 trading days',
  },
  peg: {
    title:     'Power Earnings Gap',
    tier:      'mod_agg',
    tierLabel: 'MOD-AGG',
    pitch:     "Minervini's post-earnings setup. SEPA-quality name gaps up 5%+ on 4×+ volume — institutions just confirmed.",
    entry:     'Take out gap-day high',
    stop:      'Below gap-day low',
    hold:      '3–10 days',
  },
  high_cheat: {
    title:     'Cheat — High',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     'Aggressive in-base entry just BELOW the pivot. Front-runs the breakout. No buffer for false breakout.',
    entry:     'Pivot × 0.99',
    stop:      'Below recent contraction low',
    hold:      '2–8 weeks',
  },
  episodic_pivot: {
    title:     'Episodic Pivot',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     'Pradeep Bonde — any 8%+ gap on 5×+ volume from a fundamental catalyst (FDA, contract, guidance, earnings).',
    entry:     'Gap day open / VWAP pullback',
    stop:      'Below gap-day low',
    hold:      '5–30 days',
  },
  post_earnings_drift: {
    title:     'Post-Earnings Drift',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     'Academic edge — names with strong earnings reactions keep trending for 1–90 days. Catch what you missed at the gap.',
    entry:     'Pullback to gap-day 5-day MA',
    stop:      'Below gap-day low',
    hold:      '10–60 days',
  },
  high_tight_flag: {
    title:     'High Tight Flag',
    tier:      'most_agg',
    tierLabel: 'MOST AGGRESSIVE',
    pitch:     "Minervini's rarest setup. 90–120% run in 4–8 weeks, then tight 15–25% flag for 3–5 weeks. Win rate ~50% but winners run 30%+.",
    entry:     'Break of flag high',
    stop:      'Below flag low',
    hold:      '2–8 weeks',
  },
};

export function SepaSetupInfoBanner({ activeTab }: { activeTab: SepaTab }) {
  if (activeTab === 'all') return null; // All Candidates needs no banner
  const info = INFO[activeTab];
  if (!info) return null;
  const color = TIER_COLOR[info.tier] || TIER_COLOR.neutral;
  return (
    <div
      style={{
        display:        'flex',
        flexWrap:       'wrap',
        gap:            '0.6rem 1.2rem',
        alignItems:     'center',
        padding:        '0.7rem 1rem',
        margin:         '0.4rem 0 0.8rem',
        background:     `linear-gradient(90deg, ${color}1a 0%, rgba(20,20,22,0.6) 30%)`,
        border:         `1px solid ${color}33`,
        borderLeft:     `4px solid ${color}`,
        borderRadius:   8,
        fontSize:       '0.84rem',
        lineHeight:     1.4,
      }}
      role="region"
      aria-label={`${info.title} info`}
    >
      {/* Title + tier pill */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexShrink: 0 }}>
        <span
          style={{
            fontSize:      '0.62rem',
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color:         color,
            fontWeight:    700,
            padding:       '0.15rem 0.5rem',
            border:        `1px solid ${color}66`,
            borderRadius:  10,
          }}
        >
          {info.tierLabel}
        </span>
        <strong style={{ fontSize: '0.95rem', color: '#f3e8c8' }}>{info.title}</strong>
      </div>

      {/* Pitch — flexible width */}
      <div style={{ flex: '1 1 280px', color: '#cfcfd4', minWidth: 220 }}>
        {info.pitch}
      </div>

      {/* Quick reference fields */}
      <div
        style={{
          display:        'flex',
          gap:            '1rem',
          flexWrap:       'wrap',
          fontSize:       '0.74rem',
          color:          '#9a9aa3',
          flexShrink:     0,
        }}
      >
        <Field label="ENTRY"  value={info.entry} />
        <Field label="STOP"   value={info.stop} accent="#ef4444" />
        <Field label="HOLD"   value={info.hold} />
      </div>
    </div>
  );
}

function Field({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column' }}>
      <span style={{ fontSize: '0.6rem', letterSpacing: '0.08em', color: '#6a6a72' }}>
        {label}
      </span>
      <span style={{ color: accent || '#cfcfd4', fontWeight: 500 }}>
        {value}
      </span>
    </div>
  );
}
