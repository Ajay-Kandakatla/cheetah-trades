/* navSearch — the ⌘K palette's index + ranking over EVERY navigation entry.
 *
 * Ajay 2026-09-06: "give me a global search navigation like if I wanna search
 * or related like notification I want them to show up from all the
 * navigational menu."
 *
 * Pure: the index is built from the backend menu (hooks/useMyMenu — the
 * safe-by-construction surface, so a result can never point at a page the
 * user cannot reach) plus a few deep links into tabs of pages that ARE in the
 * menu. Ranking is deterministic and tested (navSearch.test.ts); the component
 * (components/GlobalSearch.tsx) only renders what this returns.
 */
import type { Menu, MenuItem } from '../hooks/useMyMenu';

export type NavEntry = {
  label: string;
  to: string;
  feature?: string;
  /** "Primary" / "Scanners" / "Tools ▸ <subgroup>" / "Profile" / "Admin". */
  group: string;
  /** Lower-cased search terms beyond the label (synonyms, group, deep-link words). */
  keywords: string[];
};

/** Alternate words a page answers to, keyed by catalog feature id. Kept even
 *  for ids that may not be in this user's menu — the index only ever reads
 *  the ids it actually has. "notification" must find Notifications AND the
 *  Alerts page; "alert" the reverse. */
export const NAV_SYNONYMS: Record<string, string[]> = {
  notifications:   ['push', 'phone', 'alerts', 'whatsapp', 'reminders', 'quiet', 'mute', 'settings'],
  alerts:          ['notification', 'push log', 'demand alert', 'bounce', 'supply break', 'why quiet', 'pushed', 'log'],
  'supply-demand': ['zones', 'in demand', 'back in demand', 'deep demand', 'bounce', 'room', 'demand board', 'zone edge'],
  'chart-maps':    ['deep demand', 'zones', 'catalysts', 'ict', 'overnight', 'maps', 'charts', 'vcp', 'support levels', 'promo', 'signals'],
  'demand-zones':  ['zones', 'supply', 'demand', 'bands'],
  zones:           ['zones', 'supply', 'demand', 'bands'],
  trading:         ['autopilot', 'auto-pilot', 'paper', 'positions', 'journal', 'exit', 'stops', 'alpaca', 'trading', 'autopsy'],
  catalysts:       ['news', '8-k', 'promo', 'movers', 'russell', 'seeding'],
  sepa:            ['scanner', 'minervini', 'breakouts', 'vcp', 'stage 2', 'trend template', 'candidates'],
  'sepa-global':   ['scanner', 'minervini', 'simple', 'friends'],
  'market-gauge':  ['regime', 'risk on', 'risk off', 'market health', 'exposure'],
  portfolio:       ['holdings', 'fidelity', 'supply ahead', 'positions', 'sell side'],
  watchlist:       ['list', 'tickers', 'stars'],
  research:        ['analysis', 'patterns', 'insider thesis'],
  live:            ['tape', 'ticker', 'stream', 'quotes'],
  morning:         ['brief', 'report', 'pre-market', 'premarket'],
  desk:            ['daily report', 'desk', 'persona', 'pre-market'],
  overnight:       ['gappers', 'after hours', 'pre-market', 'movers'],
  breakouts:       ['pivot', 'buy verdict', 'breakout tracker'],
  leaderboard:     ['top picks', 'rank', 'ranking'],
  rotation:        ['sectors', 'money flow', 'rsp', 'safe havens'],
  options:         ['pulse', 'flow', 'calls', 'puts'],
  'gex-board':     ['gamma', 'dealer', 'walls'],
  'signal-lab':    ['1 minute', 'orb', 'sweep', 'bos', 'buy sell tags'],
  'day-trading':   ['intraday', 'orb', 'fvg'],
  scalping:        ['intraday', 'shock fade'],
  patterns:        ['candles', 'accuracy', 'ledger'],
  pankaj:          ['analyst', 'picks'],
  track:           ['tracker'],
  todos:           ['tasks', 'reminders'],
  glossary:        ['terms', 'definitions'],
  learn:           ['learning', 'lessons'],
  'chart-school':  ['lessons', 'charts'],
  learning:        ['study', 'path'],
  usage:           ['heatmap', 'analytics'],
  chatter:         ['stocktwits', 'social'],
  'chatter-india': ['stocktwits', 'social', 'india'],
  health:          ['scans', 'status'],
};

export type ExtraEntry = {
  /** Catalog feature id that must be in the index for this deep link to show. */
  parent: string;
  to: string;
  label: string;
  keywords: string[];
};

/** Deep links into tabs of pages already in the menu. Tab keys are the real
 *  ones: Chart Maps reads `?tab=` through lib/chartMaps.parseTab (CM_TABS),
 *  the SEPA ticker page through lib/sepaTabs.resolveSepaTab (TABS). An extra
 *  whose `to` equals its parent's (Notifications, Trading) is folded into the
 *  parent entry as keywords — the index dedupes by `to`. */
export const EXTRA_ENTRIES: ExtraEntry[] = [
  { parent: 'chart-maps', to: '/chart-maps?tab=zones',       label: 'Chart Maps ▸ Demand zones', keywords: ['zones', 'in demand', 'back in demand', 'demand', 'bands', 'pullback'] },
  { parent: 'chart-maps', to: '/chart-maps?tab=deep_demand', label: 'Chart Maps ▸ Deep Demand',  keywords: ['deep demand', 'zones', 'breaking resistance', 'zone edge'] },
  { parent: 'chart-maps', to: '/chart-maps?tab=catalysts',   label: 'Chart Maps ▸ Catalysts',    keywords: ['news', '8-k', 'promo', 'movers', 'russell', 'seeding'] },
  { parent: 'chart-maps', to: '/chart-maps?tab=ict',         label: 'Chart Maps ▸ ICT',          keywords: ['fvg', 'fair value gap', 'swing', 'liquidity', 'manipulation'] },
  { parent: 'chart-maps', to: '/chart-maps?tab=overnight',   label: 'Chart Maps ▸ Overnight',    keywords: ['gappers', 'after hours', 'pre-market', 'movers'] },
  { parent: 'sepa',       to: '/sepa?tab=supply',            label: 'SEPA ▸ Supply / Demand',    keywords: ['zones', 'supply', 'demand', 'in demand', 'levels'] },
  { parent: 'notifications', to: '/notifications',           label: 'Notifications ▸ push settings', keywords: ['push settings', 'mute', 'kinds', 'devices', 'quiet hours'] },
  { parent: 'trading',    to: '/trading',                    label: 'Trading ▸ Auto-Pilot journal', keywords: ['journal', 'auto-pilot', 'autopilot', 'paper trades', 'execution race'] },
];

/* ── normalisation ──────────────────────────────────────────────────────── */

/** Lower-case, drop punctuation / emoji, collapse whitespace. */
export function normalize(s: string): string {
  return (s || '')
    .toLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, ' ')
    .trim()
    .replace(/\s+/g, ' ');
}

/** A query token matches a text token when it is a prefix of it, or (for a
 *  query of ≥ 4 letters) the text token is a prefix of the query — so
 *  "alerts" still finds the synonym "alert" and vice versa. */
function tokenMatch(qt: string, tt: string): boolean {
  if (tt.startsWith(qt)) return true;
  return qt.length >= 4 && tt.length >= 3 && qt.startsWith(tt);
}

/** Every query token matches some token of `text`. */
function allTokensMatch(qTokens: string[], text: string): boolean {
  if (!qTokens.length) return false;
  const tt = text.split(' ');
  return qTokens.every((qt) => tt.some((t) => tokenMatch(qt, t)));
}

/** Letters of `q` (spaces removed) appear in order inside `text`. */
function isSubsequence(q: string, text: string): boolean {
  const a = q.replace(/\s+/g, '');
  const b = text.replace(/\s+/g, '');
  if (a.length < 3 || a.length > b.length) return false;
  let i = 0;
  for (let j = 0; j < b.length && i < a.length; j++) {
    if (b[j] === a[i]) i++;
  }
  return i === a.length;
}

/* ── index ──────────────────────────────────────────────────────────────── */

function section(items: MenuItem[], group: (it: MenuItem) => string): Array<{ it: MenuItem; group: string }> {
  return items.map((it) => ({ it, group: group(it) }));
}

/** Build the searchable index in menu order (Primary, Scanners, Tools,
 *  Profile, Admin). Deep links (EXTRA_ENTRIES) follow their parent, only when
 *  the parent feature is in the menu; entries are deduped by `to`, and a
 *  duplicate's label + keywords are folded into the first one. */
export function buildIndex(
  menu: Pick<Menu, 'primary' | 'scanners' | 'misc' | 'profile' | 'admin'>,
  subgroupOf: (feature?: string) => string | undefined = () => undefined,
): NavEntry[] {
  const ordered = [
    ...section(menu.primary ?? [], () => 'Primary'),
    ...section(menu.scanners ?? [], () => 'Scanners'),
    ...section(menu.misc ?? [], (it) => {
      const sub = subgroupOf(it.feature);
      return sub ? `Tools ▸ ${sub}` : 'Tools';
    }),
    ...section(menu.profile ?? [], () => 'Profile'),
    ...section(menu.admin ?? [], () => 'Admin'),
  ];

  const out: NavEntry[] = [];
  const byTo = new Map<string, NavEntry>();

  const push = (e: NavEntry) => {
    const key = e.to;
    const dup = byTo.get(key);
    if (dup) {
      // Same destination twice — keep the first, absorb the words of the
      // second so "push settings" still finds Notifications.
      const extra = [normalize(e.label), ...e.keywords].filter((k) => k && !dup.keywords.includes(k));
      dup.keywords.push(...extra);
      return;
    }
    byTo.set(key, e);
    out.push(e);
  };

  for (const { it, group } of ordered) {
    if (!it || !it.to) continue;
    const feature = it.feature;
    const syn = (feature && NAV_SYNONYMS[feature]) || [];
    const keywords = Array.from(new Set([
      ...(feature ? [normalize(feature)] : []),
      ...syn.map(normalize),
      normalize(group),
    ].filter(Boolean)));
    push({ label: it.label, to: it.to, feature, group, keywords });

    if (feature) {
      for (const ex of EXTRA_ENTRIES) {
        if (ex.parent !== feature) continue;
        push({
          label: ex.label,
          to: ex.to,
          feature,
          group,
          keywords: Array.from(new Set([normalize(feature), ...ex.keywords.map(normalize), normalize(group)].filter(Boolean))),
        });
      }
    }
  }
  return out;
}

/* ── search ─────────────────────────────────────────────────────────────── */

/** Rank tiers — lower wins. Inside a tier a tighter match (more of the
 *  matched text covered by the query — "Demand Zones" over "Chart Maps ▸
 *  Demand zones" for "zones") wins, then menu order. */
const TIER = { exact: 0, prefix: 1, word: 2, keyword: 3, fuzzy: 4 } as const;

type Hit = { tier: number; strength: number };

function tierOf(entry: NavEntry, q: string, qTokens: string[]): Hit | null {
  const label = normalize(entry.label);
  if (!label) return null;
  const cover = (text: string) => (text.length ? q.length / text.length : 0);
  if (label === q) return { tier: TIER.exact, strength: 1 };
  if (label.startsWith(q)) return { tier: TIER.prefix, strength: cover(label) };
  if (allTokensMatch(qTokens, label)) return { tier: TIER.word, strength: cover(label) };
  let best = 0;
  for (const k of entry.keywords) {
    if (k === q || k.startsWith(q) || allTokensMatch(qTokens, k)) best = Math.max(best, cover(k));
  }
  if (best > 0) return { tier: TIER.keyword, strength: best };
  if (isSubsequence(q, label)) return { tier: TIER.fuzzy, strength: cover(label) };
  return null;
}

/** Ranked results for `query`: exact / prefix label match, then whole-word
 *  label match, then synonym / keyword match, then a subsequence fuzzy match
 *  on the label. Blank query → the first `limit` entries in menu order. */
export function searchNav(index: NavEntry[], query: string, limit = 8): NavEntry[] {
  const q = normalize(query);
  const cap = Math.max(0, limit);
  if (!q) return index.slice(0, cap);
  const qTokens = q.split(' ');
  const scored: Array<{ e: NavEntry; hit: Hit; pos: number }> = [];
  index.forEach((e, pos) => {
    const hit = tierOf(e, q, qTokens);
    if (hit) scored.push({ e, hit, pos });
  });
  scored.sort((a, b) =>
    (a.hit.tier - b.hit.tier) || (b.hit.strength - a.hit.strength) || (a.pos - b.pos));
  return scored.slice(0, cap).map((s) => s.e);
}

/** True for an absolute http(s) destination — opened by the browser, not the router. */
export function isExternal(to: string): boolean {
  return /^https?:\/\//i.test(to || '');
}
