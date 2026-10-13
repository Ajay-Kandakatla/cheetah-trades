/* ✨ Growth arrivals — the three pure helpers behind his 2026-10-12 "yes"
 * answers on the Chart Maps strip (#5, #7, #8). No React, no fetch.
 *
 *  - `newestFirstSeen` — the newest SERVED `first_seen` in the arrivals list:
 *    the StudyNote `freshKey` that re-opens a folded line when a newer batch
 *    arrives (#7).
 *  - `withShowAll` — a chip href that also carries the page's own 🎯 override
 *    (`show=all`, read at ChartMaps.tsx `params.get('show') !== 'all'`) so an
 *    arrival the enterable cut would hide is drawn on landing (#5). URL only:
 *    nothing is persisted. It rides on every later tab click in that browser
 *    tab (tabSearch copies every param) until he toggles 🎯 back on.
 *  - `alsoOnLinks` — the served `also_on[]` membership (backend
 *    chart_maps/membership.py) as per-tab links (#8). Membership is "in the
 *    served top {limit}" of that tab as of its own build stamp — the title
 *    says so; nothing here judges staleness, it reads the served flag.
 */
import { CM_TABS, TAB_META, tabSearch, type CmTab } from './chartMaps';

/** The newest ISO `first_seen` among the served arrivals; null when none is a
 *  non-empty string. ISO stamps of one format compare lexicographically. */
export function newestFirstSeen(
  arrivals: readonly { first_seen?: string | null }[] | null | undefined,
): string | null {
  let best: string | null = null;
  for (const a of arrivals ?? []) {
    const s: unknown = a?.first_seen;
    if (typeof s !== 'string' || !s) continue;
    if (best === null || s > best) best = s;
  }
  return best;
}

/** `?a=1` → `?a=1&show=all`. Sets (never duplicates) `show=all`, keeps every
 *  other param; accepts an href with or without the leading `?`. */
export function withShowAll(href: string): string {
  const q = new URLSearchParams((href || '').replace(/^\?/, ''));
  q.set('show', 'all');
  return `?${q.toString()}`;
}

export type AlsoOnLink = {
  tab: CmTab;
  label: string;
  href: string;
  title: string;
  stale: boolean;
};

const PICTO = /\p{Extended_Pictographic}/u;

/** The label's leading emoji ("🚀 Breaking" → "🚀"); the whole label when it
 *  carries none ("Back in Demand"). */
export function tabGlyph(label: string): string {
  const head = (label || '').split(' ')[0] ?? '';
  return PICTO.test(head) ? head : label;
}

const TAB_ORDER = new Map<string, number>(CM_TABS.map((t, i) => [t, i]));

function str(v: unknown): string | null {
  return typeof v === 'string' && v ? v : null;
}

/** Per-tab links for one arrival from its SERVED `also_on[]`. Keeps entries
 *  whose `tab` is a page tab (CM_TABS — so `supply`, `growth` and anything
 *  unknown drop), ordered as the page orders its tabs. Malformed input → []. */
export function alsoOnLinks(
  a: { symbol: string; also_on?: unknown },
  params: URLSearchParams,
): AlsoOnLink[] {
  const raw = a?.also_on;
  if (!Array.isArray(raw)) return [];
  const seen = new Set<string>();
  const out: AlsoOnLink[] = [];
  for (const e of raw as unknown[]) {
    if (!e || typeof e !== 'object') continue;
    const o = e as Record<string, unknown>;
    const tab = str(o.tab);
    if (!tab || tab === 'growth' || !TAB_ORDER.has(tab) || seen.has(tab)) continue;
    seen.add(tab);
    const t = tab as CmTab;
    const label = TAB_META[t].label;
    const limit = typeof o.limit === 'number' && Number.isFinite(o.limit) ? o.limit : null;
    const asOf = str(o.source_as_of) ?? str(o.built_at);
    const stale = o.stale === true;
    const ttlName = str(o.ttl_name);
    const scope = limit != null ? `in the served top ${limit}` : 'in the served list';
    const when = asOf ? ` as of ${asOf.slice(0, 16).replace('T', ' ')}` : '';
    const staleNote = stale
      ? ` · stale: older than this tab's cache window${ttlName ? ` (${ttlName})` : ''}`
      : '';
    out.push({
      tab: t,
      label,
      href: `?${tabSearch(params, t)}`,
      title: `${label} · ${scope}${when}${staleNote}`,
      stale,
    });
  }
  out.sort((x, y) => (TAB_ORDER.get(x.tab) ?? 0) - (TAB_ORDER.get(y.tab) ?? 0));
  return out;
}
