/* KellSetupInfoBanner — compact horizontal info banner rendered directly
 * below KellSetupTabs. Hidden on the "all" tab.
 *
 * Same shape as SepaSetupInfoBanner, content sourced from Oliver Kell's
 * "Victory in Stock Trading" (2021) — these are the author's published
 * rules, not invented. The Climax-Run banner reads as a warning rather
 * than a buy because the underlying pattern IS a sell signal.
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
  volatility_compression: {
    title:     'Volatility Compression',
    tier:      'safe',
    tierLabel: 'SAFE',
    pitch:     "Kell's ATR-based contraction. ATR_10 < 0.7×ATR_50, 5-day range under 4% of price, coiled near MA20/MA50, volume drying.",
    entry:     '5-day high × 1.005',
    stop:      'Just below 5-day low',
    hold:      '1–3 weeks',
  },
  wedge_drop: {
    title:     'Wedge Drop',
    tier:      'safe_mod',
    tierLabel: 'SAFE-MOD',
    pitch:     "3–7 day pullback wedge into MA21 or MA50, then a bullish reversal candle on volume. 'The shakeout that resolves to upside.'",
    entry:     'Reversal candle high + 1¢',
    stop:      'Just below reversal candle low',
    hold:      '3–10 days',
  },
  base_break: {
    title:     'Base Break',
    tier:      'moderate',
    tierLabel: 'MODERATE',
    pitch:     "Classic 30-day high breakout on >1.5× volume. Kell's cup-with-handle / VCP-completion entry.",
    entry:     '30-day pivot + 1¢',
    stop:      'Below 15-session base low',
    hold:      '5–20 days',
  },
  reversal_extension: {
    title:     'Reversal Extension',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     "Bottom-turn confirmation — recent swing low, then a strong bullish close above the prior 5-day high on >1.5× volume.",
    entry:     'Today\'s close × 1.005',
    stop:      'Just below the swing low',
    hold:      '5–20 days',
  },
  power_trend: {
    title:     'Power Trend',
    tier:      'aggressive',
    tierLabel: 'AGGRESSIVE',
    pitch:     "Stage-2 stair-step continuation. Higher highs with shallow pullbacks (<10%); latest pullback bottomed at MA21.",
    entry:     'Today\'s close × 1.005',
    stop:      'MA21 × 0.98',
    hold:      '2–6 weeks',
  },
  climax_run: {
    title:     'Climax Run · WARNING',
    tier:      'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
    pitch:     "Not an entry. Wide-range red/weak-close bar on 2.5×+ volume after a 50%+ run, stretched 30%+ above MA50. Lighten positions.",
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
