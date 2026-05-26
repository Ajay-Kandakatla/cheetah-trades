/* KellSetupTabs — horizontal tab strip filtering the /kell page by
 * Oliver Kell's Cycle of Price Action setups. Ranked safest → most
 * aggressive (base_n_break → exhaustion_extension/wedge_drop). Same tier
 * color scheme as SepaSetupTabs so the visual coding is consistent
 * across pages — green/lime/yellow/amber/red ladder.
 *
 * Cycle order (book pp. 14-21):
 *   Reversal Extension → Wedge Pop → EMA Crossback → Base n' Break →
 *   Exhaustion Extension → Wedge Drop → (cycle repeats from RE).
 *
 * Tabs (display order: safest → most aggressive → warnings):
 *   ALL                    — combined feed of all 6 Kell kinds
 *   BASE_N_BREAK           — SAFE (longer base breakout)
 *   EMA_CROSSBACK          — SAFE-MOD (first pullback in new uptrend)
 *   WEDGE_POP              — MODERATE (first reclaim of EMAs)
 *   REVERSAL_EXTENSION     — AGGRESSIVE (capitulation bottom)
 *   EXHAUSTION_EXTENSION   — DEFENSIVE / WARN (2nd-3rd ext, SELL signal)
 *   WEDGE_DROP             — DEFENSIVE / WARN (cycle end, SELL signal)
 *
 * Counts: same lazy strategy as SepaSetupTabs — only show numbers for
 * tabs whose data has been loaded (the active tab + any previously
 * visited tab via the module-level cache in useSetupsByKind).
 */
import type { CSSProperties } from 'react';
import { InfoButton } from './InfoButton';

export type KellTab =
  | 'all'
  | 'base_n_break'           // SAFE
  | 'ema_crossback'          // SAFE-MOD
  | 'wedge_pop'              // MODERATE
  | 'reversal_extension'     // AGGRESSIVE
  | 'exhaustion_extension'   // DEFENSIVE / WARN (SELL signal)
  | 'wedge_drop';            // DEFENSIVE / WARN (SELL signal)

type Tier = 'safe' | 'safe_mod' | 'moderate' | 'aggressive' | 'defensive';

type TabMeta = {
  label: string;
  icon: string;
  tier: Tier;
  tierLabel: string;
};

// Ranked safest → most aggressive (defensive last because they are warnings).
const TAB_META: Record<KellTab, TabMeta> = {
  all: {
    label: 'All Kell setups',
    icon: '',
    tier: 'safe',
    tierLabel: 'Combined feed',
  },
  base_n_break: {
    label: "Base n' Break",
    icon: '🟢',
    tier: 'safe',
    tierLabel: 'SAFE',
  },
  ema_crossback: {
    label: 'EMA Crossback',
    icon: '🟢',
    tier: 'safe_mod',
    tierLabel: 'SAFE-MOD',
  },
  wedge_pop: {
    label: 'Wedge Pop',
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
  exhaustion_extension: {
    label: 'Exhaustion Extension · ⚠',
    icon: '🔴',
    tier: 'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
  },
  wedge_drop: {
    label: 'Wedge Drop · ⚠',
    icon: '🔴',
    tier: 'defensive',
    tierLabel: 'DEFENSIVE — SELL/TAKE PROFITS',
  },
};

const TAB_ORDER: KellTab[] = [
  'all',
  'base_n_break',
  'ema_crossback',
  'wedge_pop',
  'reversal_extension',
  'exhaustion_extension',
  'wedge_drop',
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
        style={{
          display:      'flex',
          alignItems:   'center',
          gap:          '0.45rem',
          marginBottom: '0.35rem',
        }}
      >
        <span className="eyebrow">Kell setup category</span>
        {/* InfoButton OUTSIDE the .eyebrow span — that class force-shrinks
            font to 10px on mobile and makes the "ⓘ" glyph invisible. */}
        <InfoButton inline title="Kell setup categories — what each chip means">
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
  // 30-second scan. Full detail per tab lives in the inline banner +
  // right sidebar after click. Book = Kell, Victory in Stock Trading
  // (2021) — every formula cites a page in backend/kell/<name>.py.
  const entries: Array<{ key: KellTab; pitch: string }> = [
    { key: 'all',                  pitch: "All Kell signals, sorted by R:R" },
    { key: 'base_n_break',         pitch: "5–15 day base at 10/20 EMA → breakout" },
    { key: 'ema_crossback',        pitch: "First EMA pullback in uptrend (light volume)" },
    { key: 'wedge_pop',            pitch: "First reclaim of 10/20 EMA after a wedge" },
    { key: 'reversal_extension',   pitch: "Capitulation bottom 5%+ below 10 EMA" },
    { key: 'exhaustion_extension', pitch: "⚠ SELL — 2nd/3rd extension from 10 EMA" },
    { key: 'wedge_drop',           pitch: "⚠ SELL — first close below both EMAs" },
  ];
  return (
    <>
      <p style={{ marginTop: 0, marginBottom: 8, fontSize: '0.82rem' }}>
        Kell's <strong>Cycle of Price Action</strong>. Left → right = safest → most aggressive.
        Last two tabs are SELL signals.
      </p>
      <ul style={{ paddingLeft: 0, listStyle: 'none', margin: 0 }}>
        {entries.map(({ key, pitch }) => {
          const meta = TAB_META[key];
          const color = TIER_COLOR[meta.tier];
          return (
            <li
              key={key}
              style={{
                display:        'grid',
                gridTemplateColumns: 'minmax(140px, auto) 1fr',
                gap:            '0.5rem',
                padding:        '0.25rem 0',
                alignItems:     'baseline',
                fontSize:       '0.8rem',
              }}
            >
              <span
                style={{
                  whiteSpace:    'nowrap',
                  padding:       '0.05rem 0.45rem',
                  borderRadius:  999,
                  borderLeft:    `3px solid ${color}`,
                  color:         '#f3e8c8',
                  fontWeight:    600,
                  fontSize:      '0.72rem',
                }}
              >
                {meta.icon && <span aria-hidden="true">{meta.icon} </span>}
                {meta.label}
              </span>
              <span style={{ color: '#cfcfd4', lineHeight: 1.35 }}>{pitch}</span>
            </li>
          );
        })}
      </ul>
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
  base_n_break:         'base_n_break',
  ema_crossback:        'ema_crossback',
  wedge_pop:            'wedge_pop',
  reversal_extension:   'reversal_extension',
  exhaustion_extension: 'exhaustion_extension',
  wedge_drop:           'wedge_drop',
};

export const KELL_KINDS: string[] = [
  'base_n_break',
  'ema_crossback',
  'wedge_pop',
  'reversal_extension',
  'exhaustion_extension',
  'wedge_drop',
];
