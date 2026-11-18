/* 🎬 Replays on the Chart Maps page (2026-11-17, replays spec §3.3). Ajay: "Can you store the videos in to the app
 * please". The tab is his alone, the 👀 Watch gate: offered to the primary owner, offered while /auth/me is still loading,
 * hidden from a loaded non-owner — whose ?tab=replays lands on the first tab. The page keeps its capped width on this tab.
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
vi.mock('../components/ReplaysBoard', () => ({ default: () => <div data-testid="rp-stub" /> }));
vi.mock('../components/GajjalaWatchBoard', () => ({ default: () => <div data-testid="ggw-stub" /> }));
vi.mock('../components/GajjalaBoard', () => ({ default: () => <div data-testid="gg-stub" /> }));
vi.mock('../components/LukBoard', () => ({ default: () => <div data-testid="luk-stub" /> }));
vi.mock('../components/LongTermBoard', () => ({ default: () => <div data-testid="lt-stub" /> }));

import ChartMaps from './ChartMaps';
import { CM_TABS, DEFAULT_TAB, isRetiredTab } from '../lib/chartMaps';

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

describe('🎬 the tab is the primary owner\'s', () => {
  it('shown for is_primary_admin; ?tab=replays renders the board', async () => {
    owner();
    const { container, queryByTestId } = await mount('replays');
    expect(tabKeys(container)).toEqual(CM_TABS.filter((t) => !isRetiredTab(t)));   // WIDENED 2026-11-18: ⏹ retired tabs leave the strip
    expect(selected(container)).toBe('replays');
    expect(queryByTestId('rp-stub')).not.toBeNull();
  });
  it('shown while /auth/me loads — his deep link never bounces', async () => {
    USER.user = null; USER.loading = true;
    const { container, queryByTestId } = await mount('replays');
    expect(tabKeys(container)).toContain('replays');
    expect(queryByTestId('rp-stub')).not.toBeNull();
  });
  it('NEGATIVE: hidden for a loaded co-owner; their ?tab=replays lands on the first tab', async () => {
    coOwner();
    const { container, queryByTestId } = await mount('replays');
    expect(tabKeys(container)).not.toContain('replays');
    expect(tabKeys(container)).toEqual(CM_TABS.filter((t) => t !== 'gajjala_watch' && t !== 'replays' && !isRetiredTab(t)));   // WIDENED 2026-11-18
    expect(selected(container)).toBe(DEFAULT_TAB);
    expect(queryByTestId('rp-stub')).toBeNull();
  });
  it('NEGATIVE: hidden when /auth/me answered nobody', async () => {
    USER.user = null; USER.loading = false;
    const { container, queryByTestId } = await mount('replays');
    expect(tabKeys(container)).not.toContain('replays');
    expect(queryByTestId('rp-stub')).toBeNull();
  });
  it('NEGATIVE: the 📅 Long Term board is not what ?tab=replays mounts', async () => {
    owner();
    const { queryByTestId } = await mount('replays');
    expect(queryByTestId('lt-stub')).toBeNull();
  });
});

describe('🎬 the page width', () => {
  it('NEGATIVE: the replays tab keeps the capped page (no cm-page--wide)', async () => {
    owner();
    const { container } = await mount('replays');
    expect(container.querySelector('.cm-page')!.className).toBe('cm-page');
  });
});
