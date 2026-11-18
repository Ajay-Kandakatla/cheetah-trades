/* 👀 Gajjala's Watch on the Chart Maps page (2026-11-15, gajjala-watch spec §3.8 / C4.8 / C4.1). Ajay: "I need dashboard
 * to add tickers to Gajjalas watch dashboard." The tab is his alone: offered to the primary owner, offered while /auth/me
 * is still loading (so his push deep link never bounces), hidden from a loaded non-owner — whose ?tab=gajjala_watch lands
 * on the first tab (the catalysts shape). The page drops its 1500 px cap on this tab only (3×3 on his 27-inch monitor).
 * The real page, fetch stubbed, the heavy boards stubbed. NEGATIVES throughout. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const USER = vi.hoisted(() => ({ user: null as null | Record<string, unknown>, loading: true }));
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
import { CM_TABS, DEFAULT_TAB, isRetiredTab } from '../lib/chartMaps';

/* RE-PINNED 2026-11-18 (retire-1m spec §3.10): the strip = CM_TABS minus RETIRED_CM_TABS (🚩 gajjala_1m retired —
 * Ajay: "This is good info stop 1 min tab it was a good experiment"). */
const STRIP_TABS = CM_TABS.filter((t) => !isRetiredTab(t));

const BOARD = { tab: 'zones', count: 0, matched: 0, scanned: 100, tiles: [], disclaimer: 'Study board.' };
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    return { ok: true, json: async () => (url.includes('/chart-maps?') ? BOARD : {}) } as unknown as Response;
  }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

async function mount(tab: string | null) {
  const r = render(
    <MemoryRouter initialEntries={[tab ? `/chart-maps?tab=${tab}` : '/chart-maps']}><ChartMaps /></MemoryRouter>);
  await act(async () => { await new Promise((res) => setTimeout(res, 20)); });
  return r;
}
const tabKeys = (c: HTMLElement) => Array.from(c.querySelectorAll('.cm-tabs > a'))
  .map((a) => new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab'));
const selected = (c: HTMLElement) => {
  const a = c.querySelector('.cm-tabs > a[aria-selected="true"]');
  return a ? new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab') : null;
};
const owner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: true }; USER.loading = false; };
const coOwner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: false }; USER.loading = false; };

describe('👀 the tab is the primary owner\'s', () => {
  it('shown for is_primary_admin; ?tab=gajjala_watch renders the board', async () => {
    owner();
    const { container, queryByTestId } = await mount('gajjala_watch');
    expect(tabKeys(container)).toEqual(STRIP_TABS);
    expect(selected(container)).toBe('gajjala_watch');
    expect(queryByTestId('ggw-stub')).not.toBeNull();
  });
  it('shown while /auth/me loads — his push deep link never bounces', async () => {
    USER.user = null; USER.loading = true;
    const { container, queryByTestId } = await mount('gajjala_watch');
    expect(tabKeys(container)).toContain('gajjala_watch');
    expect(queryByTestId('ggw-stub')).not.toBeNull();
  });
  it('NEGATIVE: hidden for a loaded co-owner; their ?tab=gajjala_watch lands on the first tab', async () => {
    coOwner();
    const { container, queryByTestId } = await mount('gajjala_watch');
    expect(tabKeys(container)).not.toContain('gajjala_watch');
    expect(tabKeys(container)).toEqual(STRIP_TABS.filter((t) => t !== 'gajjala_watch' && t !== 'replays'));   // WIDENED 2026-11-17 (🎬 replays owner-only) + 2026-11-18 (⏹ retired tabs leave the strip)
    expect(selected(container)).toBe(DEFAULT_TAB);
    expect(queryByTestId('ggw-stub')).toBeNull();
  });
  it('NEGATIVE: hidden when /auth/me answered nobody', async () => {
    USER.user = null; USER.loading = false;
    const { container, queryByTestId } = await mount('gajjala_watch');
    expect(tabKeys(container)).not.toContain('gajjala_watch');
    expect(queryByTestId('ggw-stub')).toBeNull();
  });
});

describe('👀 [C4.1] the wide page', () => {
  it('the watch tab\'s page carries cm-page--wide', async () => {
    owner();
    const { container } = await mount('gajjala_watch');
    expect(container.querySelector('.cm-page')!.className).toBe('cm-page cm-page--wide');
  });
  it('NEGATIVE: every other tab keeps the capped page', async () => {
    owner();
    for (const t of [null, 'gajjala', 'gajjala_1m', 'luk', 'long_term']) {
      const { container } = await mount(t);
      expect(container.querySelector('.cm-page')!.className).toBe('cm-page');
      cleanup();
    }
  });
  it('NEGATIVE (source): cm-page--wide is set only on the gajjala_watch branch', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const src: string = fs.readFileSync(`${(globalThis as any).process.cwd()}/src/pages/ChartMaps.tsx`, 'utf8');
    const hits = src.split('cm-page--wide').length - 1;
    expect(hits).toBe(1);
    expect(src).toContain("tab === 'gajjala_watch' ? 'cm-page cm-page--wide' : 'cm-page'");
  });
});
