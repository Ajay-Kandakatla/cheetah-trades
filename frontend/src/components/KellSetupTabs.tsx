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
  const entries: Array<{ key: KellTab; pitch: string }> = [
    { key: 'all',                  pitch: "Combined feed of every Kell scan — see all six patterns in one grid, sorted by R:R." },
    { key: 'base_n_break',         pitch: "5-15 day consolidation finding support at the 10/20 EMA, then breakout on >1.3× volume. Kell's lower-risk 'buy against the moving averages' entry (book pp. 18-19, 39)." },
    { key: 'ema_crossback',        pitch: "First pullback to the 10/20 EMA inside a confirmed uptrend on LIGHT volume — Kell's lowest-risk add point (book pp. 18, 27)." },
    { key: 'wedge_pop',            pitch: "First close above BOTH 10 EMA and 20 EMA after a downtrend tightens into a wedge. The Stage 1→2 turn (book pp. 17, 23-24)." },
    { key: 'reversal_extension',   pitch: "Bullish reversal candle on >1.5× volume after price extended ≥5% below the 10 EMA. The capitulation bottom — risky to catch (book pp. 16, 22-23)." },
    { key: 'exhaustion_extension', pitch: "WARNING — not an entry. 2nd or 3rd extension ≥8% above the 10 EMA on 2×+ volume, wide-range bar. Take profits (book pp. 19, 25, 40)." },
    { key: 'wedge_drop',           pitch: "WARNING — not an entry. First close below BOTH EMAs after a recent Exhaustion Extension on >1.3× volume. Cycle is over (book pp. 18, 20, 24, 41)." },
  ];
  return (
    <>
      <p style={{ marginTop: 0 }}>
        Oliver Kell's <strong>Cycle of Price Action</strong> (book: <em>Victory in Stock Trading</em>, 2021, pp. 14-21).
        Six phases, in order: Reversal Extension → Wedge Pop → EMA Crossback → Base n' Break → Exhaustion Extension → Wedge Drop → (cycle repeats).
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
        The two WARNING tabs (Exhaustion Extension, Wedge Drop) are SELL signals — they have no entry/stop/target and run in any market regime. The four BUY tabs only scan in confirmed uptrends.
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
