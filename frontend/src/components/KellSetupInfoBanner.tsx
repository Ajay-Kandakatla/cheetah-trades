/* KellSetupInfoBanner — compact horizontal info banner rendered directly
 * below KellSetupTabs. Hidden on the "all" tab.
 *
 * Same shape as SepaSetupInfoBanner, content sourced from Oliver Kell's
 * "Victory in Stock Trading" (2021) Cycle of Price Action chapter (pp.
 * 14-27). The Exhaustion Extension and Wedge Drop banners read as
 * warnings rather than buys because the underlying patterns ARE sell
 * signals.
 */
import type { KellTab } from './KellSetupTabs';

const TIER_COLOR: Record<string, string> = {
  safe:       '#22c55e',
  safe_mod:   '#84cc16',
  moderate:   '#facc15',
  aggressive: '#fb923c',
  defensive:  '#ef4444',
  neutral:    '#9aa8c8',
};

type BannerInfo = {
  title:     string;
  tier:      string;
  tierLabel: string;
  pitch:     string;
  entry:     string;
  stop:      string;
  hold:      string;
};

const INFO: Partial<Record<KellTab, BannerInfo>> = {
  base_n_break: {
    title:     "Base n' Break",
    tier:      'safe',
    tierLabel: 'SAFE',
    pitch:     "5-15 day base on the 10/20 EMA with volume drying, then breakout on >1.3× volume (book pp. 18-19, 39).",
    entry:     'Base pivot + 1¢',
    stop:      'min(20 EMA, base low) − 1¢',
    hold:      '2–10 days',
  },
  ema_crossback: {
    title:     'EMA Crossback',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    pitch:     "First pullback to the 10/20 EMA on LIGHT volume inside a confirmed uptrend (book pp. 18, 27).",
    entry:     "Today's bar high + 1¢",
    stop:      'min(20 EMA, 3-day low) − 1¢',
    hold:      '3–10 days',
  },
  wedge_pop: {
    title:     'Wedge Pop',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    pitch:     "First close above BOTH 10 EMA and 20 EMA after a downtrend tightened into a wedge (book pp. 17, 23-24).",
    entry:     "Today's bar high + 1¢",
    stop:      'min(lows[−7:])',
    hold:      '1–4 days',
  },
  reversal_extension: {
    title:     'Reversal Extension',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     "Bullish reversal bar on >1.5× volume after price extended ≥5% below the 10 EMA (book pp. 16, 22-23).",
    entry:     'Reversal bar high + 1¢',
    stop:      'Reversal bar low − 1¢',
    hold:      '3–10 days to 20 EMA',
  },
  exhaustion_extension: {
    title:     'Exhaustion Extension · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    pitch:     "Not an entry. 2nd or 3rd extension ≥8% above the 10 EMA on >2× volume, wide-range bar. Take profits (book pp. 19, 25, 40).",
    entry:     '— (no entry)',
    stop:      '— (no stop)',
    hold:      '— (act now)',
  },
  wedge_drop: {
    title:     'Wedge Drop · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    pitch:     "Not an entry. First close BELOW both EMAs after a recent Exhaustion Extension on >1.3× volume. Cycle is over (book pp. 18, 20, 24, 41).",
    entry:     '— (no entry)',
    stop:      '— (no stop)',
    hold:      '— (act now)',
  },
};

export function KellSetupInfoBanner({ activeTab }: { activeTab: KellTab }) {
  if (activeTab === 'all') return null;
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

      <div style={{ flex: '1 1 280px', color: '#cfcfd4', minWidth: 220 }}>
        {info.pitch}
      </div>

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
