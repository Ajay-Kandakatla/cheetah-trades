/* SepaSetupTabs — horizontal tab strip that filters the SEPA candidate
 * list by Minervini setup category. Ranked safest → most aggressive so
 * cautious / new traders read top-to-bottom and graduate down the list
 * as conviction grows. Tier color (green / yellow / orange / red) lives
 * in the pill border so the risk gradient is visible at a glance.
 *
 *   ALL    — default; the existing SEPA list, no overlay
 *   VCP    — client-side filter on r.vcp?.has_base (no API call)
 *   Other  — `GET /setups/{kind}?only_pending=true` fetch via
 *            useSetupsByKind, with overlay strip on each matched card
 *
 * Counts: only rendered for tabs that have actually been opened (and
 * therefore have a cached fetch). Saves us from fanning out 7 fetches
 * on page load just to populate badges. Empty count = tab not yet
 * visited.
 */
import type { CSSProperties } from 'react';

export type SepaTab =
  | 'all'
  | 'vcp'
  | 'low_cheat'
  | 'mid_cheat'
  | 'bull_flag'
  | 'peg'
  | 'high_cheat'
  | 'episodic_pivot'
  | 'post_earnings_drift'
  | 'high_tight_flag';

type Tier = 'safe' | 'safe_mod' | 'moderate' | 'mod_agg' | 'aggressive' | 'most_agg';

type TabMeta = {
  label: string;
  icon: string;
  tier: Tier;
  tierLabel: string;
};

// Ranked safest → most aggressive. The order of TAB_ORDER below drives
// the on-screen left-to-right layout, so don't sort this alphabetically.
const TAB_META: Record<SepaTab, TabMeta> = {
  all: {
    label: 'All Candidates',
    icon: '',
    tier: 'safe',
    tierLabel: 'Full SEPA list',
  },
  vcp: {
    label: 'Volatility Contraction',
    icon: '🟢',
    tier: 'safe',
    tierLabel: 'SAFE',
  },
  low_cheat: {
    label: 'Cheat — Low',
    icon: '🟢',
    tier: 'safe_mod',
    tierLabel: 'SAFE-MOD',
  },
  mid_cheat: {
    label: 'Cheat — Mid',
    icon: '🟢',
    tier: 'safe_mod',
    tierLabel: 'SAFE-MOD',
  },
  bull_flag: {
    label: 'Bull Flag',
    icon: '🟡',
    tier: 'moderate',
    tierLabel: 'MODERATE',
  },
  peg: {
    label: 'Power Earnings Gap',
    icon: '🟡',
    tier: 'mod_agg',
    tierLabel: 'MODERATE-AGG',
  },
  high_cheat: {
    label: 'Cheat — High',
    icon: '🟠',
    tier: 'aggressive',
    tierLabel: 'AGGRESSIVE',
  },
  episodic_pivot: {
    label: 'Episodic Pivot',
    icon: '🟠',
    tier: 'aggressive',
    tierLabel: 'AGGRESSIVE',
  },
  post_earnings_drift: {
    label: 'Post-Earnings Drift',
    icon: '🟠',
    tier: 'aggressive',
    tierLabel: 'AGGRESSIVE',
  },
  high_tight_flag: {
    label: 'High Tight Flag',
    icon: '🔴',
    tier: 'most_agg',
    tierLabel: 'MOST AGGRESSIVE',
  },
};

const TAB_ORDER: SepaTab[] = [
  'all',
  'vcp',
  'low_cheat',
  'mid_cheat',
  'bull_flag',
  'peg',
  'high_cheat',
  'episodic_pivot',
  'post_earnings_drift',
  'high_tight_flag',
];

// Tier color → pill border. Same green/yellow/orange/red ladder you'd
// see in any risk-disclosure document. Keeps the visual coding obvious.
const TIER_COLOR: Record<Tier, string> = {
  safe:       'rgba(34, 197, 94, 0.65)',   // green-500
  safe_mod:   'rgba(132, 204, 22, 0.65)',  // lime-500
  moderate:   'rgba(234, 179, 8, 0.65)',   // yellow-500
  mod_agg:    'rgba(245, 158, 11, 0.65)',  // amber-500
  aggressive: 'rgba(249, 115, 22, 0.65)',  // orange-500
  most_agg:   'rgba(239, 68, 68, 0.7)',    // red-500
};

const TIER_ACTIVE_BG: Record<Tier, string> = {
  safe:       'rgba(34, 197, 94, 0.16)',
  safe_mod:   'rgba(132, 204, 22, 0.16)',
  moderate:   'rgba(234, 179, 8, 0.16)',
  mod_agg:    'rgba(245, 158, 11, 0.16)',
  aggressive: 'rgba(249, 115, 22, 0.16)',
  most_agg:   'rgba(239, 68, 68, 0.18)',
};

type Props = {
  activeTab: SepaTab;
  onTabChange: (tab: SepaTab) => void;
  /** Count of matching rows per tab. Tabs not in the map (or with value
   *  null/undefined) show no badge — used for tabs that haven't been
   *  opened yet so we don't pre-fetch every kind eagerly. */
  tabCounts: Partial<Record<SepaTab, number | null>>;
};

export function SepaSetupTabs({ activeTab, onTabChange, tabCounts }: Props) {
  return (
    <section
      style={{
        marginTop: '1rem',
        marginBottom: '0.85rem',
      }}
    >
      <div
        className="eyebrow"
        style={{ marginBottom: '0.35rem' }}
      >
        Setup category
      </div>
      <div
        role="tablist"
        aria-label="SEPA setup category filter"
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

/** Public helper — turns the SepaTab key into a human label, used by the
 *  empty-state copy in Sepa.tsx. Exported so the page doesn't need to
 *  know the internal TAB_META shape. */
export function tabLabel(tab: SepaTab): string {
  return TAB_META[tab].label;
}

/** Map of UI tab → backend `kind` string. `null` for tabs that don't
 *  hit the API at all (the "all" pass-through and the "vcp" client-side
 *  filter on already-loaded SEPA data). */
export const TAB_TO_KIND: Record<SepaTab, string | null> = {
  all: null,
  vcp: null,
  low_cheat: 'low_cheat',
  mid_cheat: 'mid_cheat',
  bull_flag: 'bull_flag',
  peg: 'peg',
  high_cheat: 'high_cheat',
  episodic_pivot: 'episodic_pivot',
  post_earnings_drift: 'post_earnings_drift',
  high_tight_flag: 'high_tight_flag',
};
