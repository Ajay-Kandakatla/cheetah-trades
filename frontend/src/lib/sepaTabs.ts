/* sepaTabs — which tab the SEPA candidate page (/sepa/:symbol) opens on.
 *
 * Pulled out of SepaCandidate.tsx so the resolution is a pure, tested
 * function and the page cannot quietly grow a second fallback.
 *
 * The active tab lives in the URL (?tab=insider) so it survives reload, back/
 * forward, and deep-links from cards. Legacy #hash deep-links some chips still
 * emit are accepted too.
 *
 * DEFAULT: 'supply' — Ajay 2026-09-03: "when ever I click on SEPA I need it
 * to go Supply and Demand tab in all pages." Until then the bare
 * /sepa/:symbol landed on 'chart'; the 2026-08-17 Chart Maps / Back in Demand
 * deep links that asked for 'setup' are superseded by this default. Purposed
 * chips (insider, fundamentals, breakout tape, …) still pass ?tab= and win.
 */

export type Tab =
  | 'chart' | 'setup' | 'analysis' | 'trend' | 'breakout' | 'ranking'
  | 'fundamentals' | 'catalyst' | 'insider' | 'smartmoney' | 'chatter'
  | 'supply' | 'options' | 'tape';

// Display order. 'analysis' 3rd (Ajay 2026-06-16: "move the analysis tab
// closer"); supply beside analysis (Ajay 2026-08-25) — since the price
// supply/demand levels moved onto that tab it reads as analysis, not appendix.
export const TABS: Tab[] = [
  'chart', 'setup', 'analysis', 'supply', 'trend', 'breakout', 'ranking',
  'fundamentals', 'options', 'tape', 'catalyst', 'insider', 'smartmoney', 'chatter',
];

export const DEFAULT_TAB: Tab = 'supply';

export const HASH_TO_TAB: Record<string, Tab> = {
  chart: 'chart', setup: 'setup', trend: 'trend', breakout: 'breakout', ranking: 'ranking',
  fundamentals: 'fundamentals', analysis: 'analysis', options: 'options',
  tape: 'tape', orderflow: 'tape',
  catalyst: 'catalyst', insider: 'insider', smartmoney: 'smartmoney',
  chatter: 'chatter', supply: 'supply',
  // legacy hashes that don't map 1:1 to a tab → nearest sensible tab.
  // 'sales' merged into 'analysis' (Ajay 2026-06-16) — old deep-links redirect.
  sales: 'analysis',
  volume: 'breakout', 'dual-momentum': 'ranking',
};

/** `?tab=` wins when it names a real tab; else a legacy `#hash`; else the
 *  Supply / Demand default. Unknown values never leak through — a typo in a
 *  deep link lands on the default, not on an empty page. */
export function resolveSepaTab(tabParam: string | null | undefined, hash: string | null | undefined): Tab {
  if (tabParam && (TABS as string[]).includes(tabParam)) return tabParam as Tab;
  const key = (hash || '').replace(/^#/, '').toLowerCase();
  return HASH_TO_TAB[key] ?? DEFAULT_TAB;
}


/**
 * Bring the active tab button inside `nav` into view. Phones scroll the tab
 * strip sideways and 'supply' is 4th of 14, so a landing on the Supply /
 * Demand default (2026-09-03) could show the selected tab off-screen. Returns
 * whether it scrolled — jsdom has no scrollIntoView, so callers never assume.
 */
export function scrollActiveTabIntoView(nav: HTMLElement | null | undefined): boolean {
  const el = nav?.querySelector<HTMLElement>('.sepa-tab.is-active');
  if (!el || typeof el.scrollIntoView !== 'function') return false;
  el.scrollIntoView({ block: 'nearest', inline: 'center' });
  return true;
}
