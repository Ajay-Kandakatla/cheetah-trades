/* 🔀 The tab-button dot on the real Chart Maps page (2026-11-15, ema-blink spec §3.9 / §4 WP-F (b), (c)). Ajay: "Or
 * atleast closing in on other tabs for me." The server names the tabs (keys of `tabs`); a dot shows only for a served
 * tab with n > 0 and a tier; its class is ema-blink-<tier>, its title the served words; the anchor's text stays exactly
 * TAB_META[t].label. Fetch stubbed, the heavy boards stubbed. NEGATIVES throughout. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const USER = vi.hoisted(() => ({ user: null as null | Record<string, unknown>, loading: false }));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: USER.user, loading: USER.loading }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps', 'catalysts']), catalog: [], email: null }),
}));
vi.mock('../components/GajjalaWatchBoard', () => ({ default: () => <div data-testid="ggw-stub" /> }));
vi.mock('../components/GajjalaBoard', () => ({ default: () => <div data-testid="gg-stub" /> }));
vi.mock('../components/LukBoard', () => ({ default: () => <div data-testid="luk-stub" /> }));
vi.mock('../components/LongTermBoard', () => ({ default: () => <div data-testid="lt-stub" /> }));

import ChartMaps from './ChartMaps';
import { CM_TABS, TAB_META, type CmTab } from '../lib/chartMaps';
import { EMA_BLINK_TABS_PATH } from '../lib/emaBlinkTabs';

const BOARD = { tab: 'zones', count: 0, matched: 0, scanned: 100, tiles: [], disclaimer: 'Study board.' };
const FEED = {
  as_of: '2026-11-16T14:40:00Z', session: '2026-11-16', in_window: true, refresh_sec: 60,
  info: 'served info', n_means: 'served n_means',
  tabs: {
    gajjala: { n: 3, crossed_up: 1, closing_in: 2, tier: 'fresh', frame: '5m',
               top: { symbol: 'ABCD', tier: 'fresh', closeness: 0 }, text: '3 cards served words · closest ABCD' },
    gajjala_audited: { n: 1, crossed_up: 0, closing_in: 1, tier: 'near', frame: '5m',
                       top: { symbol: 'WXYZ', tier: 'near', closeness: 2 }, text: 'WXYZ served words' },
    gajjala_1m: { n: 0, crossed_up: 0, closing_in: 0, tier: null, frame: '1m', top: null, text: null },
    luk: { n: 2, crossed_up: 0, closing_in: 2, tier: 'closing', frame: '5m', top: null, text: 'luk served words' },
    gajjala_watch: null,
    not_a_tab_the_fe_lists: { n: 9, tier: 'fresh', text: 'ignored' },
  },
};
let feed: unknown = FEED;
let blinkCalls = 0;

beforeEach(() => {
  feed = FEED;
  blinkCalls = 0;
  USER.user = { email: 'x', is_admin: true, is_primary_admin: true }; USER.loading = false;
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    if (url.endsWith(EMA_BLINK_TABS_PATH)) {
      blinkCalls += 1;
      return { ok: true, status: 200, json: async () => feed } as unknown as Response;
    }
    return { ok: true, status: 200, json: async () => (url.includes('/chart-maps?') ? BOARD : {}) } as unknown as Response;
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function mount(tab: string | null = 'zones') {
  const r = render(
    <MemoryRouter initialEntries={[tab ? `/chart-maps?tab=${tab}` : '/chart-maps']}><ChartMaps /></MemoryRouter>);
  await act(async () => { await new Promise((res) => setTimeout(res, 20)); });
  return r;
}
const anchorOf = (c: HTMLElement, t: string) => Array.from(c.querySelectorAll<HTMLAnchorElement>('.cm-tabs > a'))
  .find((a) => new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab') === t) || null;
const dots = (c: HTMLElement) => Array.from(c.querySelectorAll<HTMLElement>('.cm-tab-blink'))
  .map((d) => d.getAttribute('data-testid'));

describe('(b) the dot rides exactly the served tabs with n > 0 and a tier', () => {
  it('one GET of the feed on mount, from ANY tab (the dot pulls him to a tab he is not on)', async () => {
    await mount('zones');
    expect(blinkCalls).toBe(1);
  });
  it('gajjala / gajjala_audited / luk dot; class = ema-blink-<tier>; title + aria-label = the served words', async () => {
    const { container } = await mount('zones');
    expect(dots(container).sort()).toEqual(['cm-tab-blink-gajjala', 'cm-tab-blink-gajjala_audited', 'cm-tab-blink-luk']);
    const g = container.querySelector<HTMLElement>('[data-testid="cm-tab-blink-gajjala"]')!;
    expect(g.className).toBe('cm-tab-blink ema-blink-fresh');
    expect(g.getAttribute('title')).toBe('3 cards served words · closest ABCD');
    expect(g.getAttribute('aria-label')).toBe('3 cards served words · closest ABCD');
    expect(container.querySelector('[data-testid="cm-tab-blink-gajjala_audited"]')!.className)
      .toBe('cm-tab-blink ema-blink-near');
    expect(container.querySelector('[data-testid="cm-tab-blink-luk"]')!.className)
      .toBe('cm-tab-blink ema-blink-closing');
    expect(anchorOf(container, 'gajjala')!.contains(g)).toBe(true);
  });
  it('the dot also shows on the ACTIVE tab', async () => {
    const { container } = await mount('gajjala');
    expect(anchorOf(container, 'gajjala')!.getAttribute('aria-selected')).toBe('true');
    expect(container.querySelector('[data-testid="cm-tab-blink-gajjala"]')).not.toBeNull();
  });
  it('NEGATIVE: n 0 → no dot; gajjala_watch null → no dot; a key the FE does not list → ignored', async () => {
    const { container } = await mount('zones');
    expect(anchorOf(container, 'gajjala_1m')).not.toBeNull();
    expect(container.querySelector('[data-testid="cm-tab-blink-gajjala_1m"]')).toBeNull();
    expect(anchorOf(container, 'gajjala_watch')).not.toBeNull();
    expect(container.querySelector('[data-testid="cm-tab-blink-gajjala_watch"]')).toBeNull();
    expect(container.querySelector('[data-testid="cm-tab-blink-not_a_tab_the_fe_lists"]')).toBeNull();
    expect(dots(container)).toHaveLength(3);
  });
  it('NEGATIVE: an unknown tier or a tierless tab → no dot', async () => {
    feed = { ...FEED, tabs: { gajjala: { n: 3, tier: 'warp', text: 'x' }, luk: { n: 2, tier: null, text: 'x' } } };
    const { container } = await mount('zones');
    expect(dots(container)).toEqual([]);
  });
  it('NEGATIVE: a junk / empty / failed feed → no dot anywhere, the strip renders', async () => {
    for (const f of ['junk', {}, { tabs: null }, null]) {
      feed = f;
      const { container } = await mount('zones');
      expect(dots(container)).toEqual([]);
      expect(container.querySelectorAll('.cm-tabs > a').length).toBeGreaterThan(0);
      cleanup();
    }
    vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
      const url = String(u);
      if (url.endsWith(EMA_BLINK_TABS_PATH)) return { ok: false, status: 500, json: async () => ({}) } as unknown as Response;
      return { ok: true, status: 200, json: async () => BOARD } as unknown as Response;
    }));
    const { container } = await mount('zones');
    expect(dots(container)).toEqual([]);
  });
});

describe('(c) the label text is untouched', () => {
  it('every anchor\'s text content is exactly TAB_META[t].label, dot or no dot', async () => {
    const { container } = await mount('zones');
    for (const t of CM_TABS) {
      const a = anchorOf(container, t);
      if (!a) continue;
      expect(a.textContent).toBe(TAB_META[t as CmTab].label);
    }
    const g = anchorOf(container, 'gajjala')!;
    expect(g.querySelector('.cm-tab-blink')).not.toBeNull();
    expect(g.textContent).toBe(TAB_META.gajjala.label);
  });
  it('NEGATIVE (source): ChartMaps imports the tab CSS once and renders the dot from the served feed only', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const src: string = fs.readFileSync(`${(globalThis as any).process.cwd()}/src/pages/ChartMaps.tsx`, 'utf8');
    expect(src.split("import '../styles/emaBlinkTab.css';").length - 1).toBe(1);
    expect(src.split('useEmaBlinkTabs(').length - 1).toBe(1);
    expect(src.split('cm-tab-blink').length - 1).toBe(2);   // the class + the testid, one span
  });
});
