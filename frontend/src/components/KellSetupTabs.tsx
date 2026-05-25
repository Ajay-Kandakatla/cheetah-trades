/* KellSetupTabs — horizontal tab strip filtering the /kell page by
 * Oliver Kell's Cycle of Price Action setups. Ranked safest → most
 * aggressive (volatility_compression → climax_run). Same tier color
 * scheme as SepaSetupTabs so the visual coding is consistent across
 * pages — green/lime/yellow/amber/orange/red ladder.
 *
 * Tabs:
 *   ALL                    — combined feed of all 6 Kell kinds
 *   VOLATILITY_COMPRESSION — SAFE (ATR contraction)
 *   WEDGE_DROP             — SAFE-MOD (shakeout reversal)
 *   BASE_BREAK             — MODERATE (cup/VCP breakout)
 *   REVERSAL_EXTENSION     — AGGRESSIVE (bottom-turn extension)
 *   POWER_TREND            — AGGRESSIVE (stair-step continuation)
 *   CLIMAX_RUN             — DEFENSIVE (red, SELL/take-profit warning)
 *
 * Counts: same lazy strategy as SepaSetupTabs — only show numbers for
 * tabs whose data has been loaded (the active tab + any previously
 * visited tab via the module-level cache in useSetupsByKind).
 */
import type { CSSProperties } from 'react';
import { InfoButton } from './InfoButton';

export type KellTab =
  | 'all'
  | 'volatility_compression'   // SAFE
  | 'wedge_drop'               // SAFE-MOD
  | 'base_break'               // MODERATE
  | 'reversal_extension'       // AGGRESSIVE
  | 'power_trend'              // AGGRESSIVE
  | 'climax_run';              // DEFENSIVE (red, warning)

type Tier = 'safe' | 'safe_mod' | 'moderate' | 'aggressive' | 'defensive';

type TabMeta = {
  label: string;
  icon: string;
  tier: Tier;
  tierLabel: string;
};

// Ranked safest → most aggressive (defensive last because it's the warning).
const TAB_META: Record<KellTab, TabMeta> = {
  all: {
    label: 'All Kell setups',
    icon: '',
    tier: 'safe',
    tierLabel: 'Combined feed',
  },
  volatility_compression: {
    label: 'Volatility Compression',
    icon: '🟢',
    tier: 'safe',
    tierLabel: 'SAFE',
  },
  wedge_drop: {
    label: 'Wedge Drop',
    icon: '🟢',
    tier: 'safe_mod',
    tierLabel: 'SAFE-MOD',
  },
  base_break: {
    label: 'Base Break',
    icon: '🟡',
    tier: 'moderate',
    tierLabel: 'MODERATE',
  },
  reversal_extension: {
    label: 'Reversal Extension',
    icon: '🟠',
    tier: 'aggressive',
    tierLabel: 'AGGRESSIVE',
  },
  power_trend: {
    label: 'Power Trend',
    icon: '🟠',
    tier: 'aggressive',
    tierLabel: 'AGGRESSIVE',
  },
  climax_run: {
    label: 'Climax Run · ⚠',
    icon: '🔴',
    tier: 'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
  },
};

const TAB_ORDER: KellTab[] = [
  'all',
  'volatility_compression',
  'wedge_drop',
  'base_break',
  'reversal_extension',
  'power_trend',
  'climax_run',
];

const TIER_COLOR: Record<Tier, string> = {
  safe:       'rgba(34, 197, 94, 0.65)',   // green-500
  safe_mod:   'rgba(132, 204, 22, 0.65)',  // lime-500
  moderate:   'rgba(234, 179, 8, 0.65)',   // yellow-500
  aggressive: 'rgba(249, 115, 22, 0.65)',  // orange-500
  defensive:  'rgba(239, 68, 68, 0.7)',    // red-500
};

const TIER_ACTIVE_BG: Record<Tier, string> = {
  safe:       'rgba(34, 197, 94, 0.16)',
  safe_mod:   'rgba(132, 204, 22, 0.16)',
  moderate:   'rgba(234, 179, 8, 0.16)',
  aggressive: 'rgba(249, 115, 22, 0.16)',
  defensive:  'rgba(239, 68, 68, 0.18)',
};

type Props = {
  activeTab: KellTab;
  onTabChange: (tab: KellTab) => void;
  /** Count of matching rows per tab. Tabs not in the map (or value
   *  null/undefined) show no badge — used for tabs we haven't fetched
   *  yet so the page doesn't fan out 6 fetches at mount. */
  tabCounts: Partial<Record<KellTab, number | null>>;
};

export function KellSetupTabs({ activeTab, onTabChange, tabCounts }: Props) {
  return (
    <section style={{ marginTop: '1rem', marginBottom: '0.85rem' }}>
      <div
        className="eyebrow"
        style={{
          marginBottom: '0.35rem',
          display:      'inline-flex',
          alignItems:   'center',
          gap:          '0.3rem',
        }}
      >
        Kell setup category
        <InfoButton title="Kell setup categories — what each chip means">
          <KellCategoriesLegend />
        </InfoButton>
      </div>
      <div
        role="tablist"
        aria-label="Kell setup category filter"
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '0.4rem',
          alignItems: 'center',
        }}
      >
        {TAB_ORDER.map((t) => {
          const meta = TAB_META[t];
          const active = activeTab === t;
          const color = TIER_COLOR[meta.tier];
          const activeBg = TIER_ACTIVE_BG[meta.tier];
          const count = tabCounts[t];
          const hasCount = count != null;

          const style: CSSProperties = {
            padding: '0.45rem 0.85rem',
            background: active ? activeBg : 'rgba(255,255,255,0.03)',
            border: `1px solid ${active ? color : 'rgba(255,255,255,0.08)'}`,
            borderLeft: `3px solid ${color}`,
            borderRadius: 999,
            color: active ? '#f3e8c8' : '#cfcfd4',
            fontFamily: 'inherit',
            fontWeight: active ? 700 : 500,
            fontSize: '0.82rem',
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.35rem',
            transition: 'background 120ms ease, border-color 120ms ease',
          };

          return (
            <button
              key={t}
              role="tab"
              aria-selected={active}
              onClick={() => onTabChange(t)}
              title={meta.tierLabel}
              style={style}
            >
              {meta.icon && <span aria-hidden="true">{meta.icon}</span>}
              <span>{meta.label}</span>
              {hasCount && (
                <span
                  style={{
                    fontSize: '0.7rem',
                    color: active ? '#f3e8c8' : '#9aa8c8',
                    background: 'rgba(0,0,0,0.25)',
                    borderRadius: 999,
                    padding: '0.05rem 0.4rem',
                    fontWeight: 600,
                  }}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}

function KellCategoriesLegend() {
  const entries: Array<{ key: KellTab; pitch: string }> = [
    { key: 'all',                     pitch: "Combined feed of every Kell scan — see all six patterns in one grid, sorted by R:R." },
    { key: 'volatility_compression',  pitch: "ATR-based contraction — recent volatility 30%+ below long-term, coiled near MA20/MA50, volume drying. Wait for the expansion break." },
    { key: 'wedge_drop',              pitch: "3-7 day pullback wedge into MA21 or MA50, then a bullish reversal candle on volume. 'The shakeout that resolves to upside.'" },
    { key: 'base_break',              pitch: "Classic 30-day high breakout on >1.5× volume. Kell's name for the cup-with-handle / VCP-completion entry." },
    { key: 'reversal_extension',      pitch: "Recent swing low (3-20 sessions ago) followed by a strong bullish close above the prior 5-day high on >1.5× volume. The bottom turn confirmed." },
    { key: 'power_trend',             pitch: "Stage-2 stair-step — higher highs with shallow pullbacks, latest pullback bottomed at MA21. Continuation buy on the rail." },
    { key: 'climax_run',              pitch: "WARNING — not an entry. Wide-range red bar on 2.5×+ volume after a 50%+ run, stretched 30%+ above MA50. Lighten positions." },
  ];
  return (
    <>
      <p style={{ marginTop: 0 }}>
        Oliver Kell's <strong>Cycle of Price Action</strong> (book: <em>Victory in Stock Trading</em>, 2021).
        Patterns ranked safest → most aggressive, with <strong>Climax Run</strong> as a defensive warning rather than an entry.
      </p>
      <ul style={{ paddingLeft: 0, listStyle: 'none', margin: 0 }}>
        {entries.map(({ key, pitch }) => {
          const meta = TAB_META[key];
          const color = TIER_COLOR[meta.tier];
          return (
            <li
              key={key}
              style={{
                display:      'grid',
                gridTemplateColumns: 'auto 1fr',
                gap:          '0.6rem',
                padding:      '0.45rem 0',
                borderBottom: '1px solid rgba(255,255,255,0.06)',
                alignItems:   'baseline',
              }}
            >
              <span
                style={{
                  whiteSpace:    'nowrap',
                  padding:       '0.15rem 0.55rem',
                  borderRadius:  999,
                  border:        `1px solid ${color}66`,
                  borderLeft:    `3px solid ${color}`,
                  color:         '#f3e8c8',
                  fontWeight:    600,
                  fontSize:      '0.78rem',
                }}
              >
                {meta.icon && <span aria-hidden="true">{meta.icon} </span>}
                {meta.label}
              </span>
              <span style={{ color: '#cfcfd4', fontSize: '0.85rem', lineHeight: 1.5 }}>
                {pitch}
              </span>
            </li>
          );
        })}
      </ul>
      <p style={{ fontSize: '0.78rem', color: '#9a9aa3', marginBottom: 0 }}>
        Counts appear after you open each tab — Kell scanners are lazy-loaded
        so the page doesn't fan out six fetches at mount.
      </p>
    </>
  );
}

export function kellTabLabel(tab: KellTab): string {
  return TAB_META[tab].label;
}

/** UI tab → backend `kind` string. `null` for the combined "all" view
 *  which doesn't hit a single endpoint (the page fans out per-kind
 *  fetches and merges client-side). */
export const KELL_TAB_TO_KIND: Record<KellTab, string | null> = {
  all: null,
  volatility_compression: 'volatility_compression',
  wedge_drop:             'wedge_drop',
  base_break:             'base_break',
  reversal_extension:     'reversal_extension',
  power_trend:            'power_trend',
  climax_run:             'climax_run',
};

export const KELL_KINDS: string[] = [
  'volatility_compression',
  'wedge_drop',
  'base_break',
  'reversal_extension',
  'power_trend',
  'climax_run',
];
