/* ⏹ The 🚩 Gajjala 1-minute page retired 2026-11-18 (retire-1m spec §3.10). Ajay 2026-11-18: "This is good info stop 1 min
 * tab it was a good experiment" — then "But keep the one min chart in the watch list I still want them". The strip drops
 * the "Gajjala's 1-min" tab (isRetiredTab); ?tab=gajjala_1m still mounts the board for its 🏁 history; 🚩, 🧪 and 👀 stay.
 * The real page, fetch stubbed, the heavy boards stubbed (the ChartMaps.watch.test.tsx harness). NEGATIVES throughout. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const USER = vi.hoisted(() => ({ user: null as null | Record<string, unknown>, loading: true }));
const GG = vi.hoisted(() => ({ variants: [] as (string | undefined)[] }));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: USER.user, loading: USER.loading }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps', 'catalysts']), catalog: [], email: null }),
}));
vi.mock('../components/GajjalaWatchBoard', () => ({ default: () => <div data-testid="ggw-stub" /> }));
vi.mock('../components/GajjalaBoard', () => ({
  default: (p: { variant?: string }) => { GG.variants.push(p.variant); return <div data-testid="gg-stub" data-variant={p.variant ?? ''} />; },
}));
vi.mock('../components/LukBoard', () => ({ default: () => <div data-testid="luk-stub" /> }));
vi.mock('../components/LongTermBoard', () => ({ default: () => <div data-testid="lt-stub" /> }));

import ChartMaps from './ChartMaps';
import { CM_TABS, TAB_META } from '../lib/chartMaps';

const BOARD = { tab: 'zones', count: 0, matched: 0, scanned: 100, tiles: [], disclaimer: 'Study board.' };
beforeEach(() => {
  GG.variants = [];
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
const anchors = (c: HTMLElement) => Array.from(c.querySelectorAll('.cm-tabs > a'));
const tabKeys = (c: HTMLElement) => anchors(c).map((a) => new URLSearchParams(a.getAttribute('href')!.slice(1)).get('tab'));
const tabTexts = (c: HTMLElement) => anchors(c).map((a) => (a.textContent || '').trim());
const owner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: true }; USER.loading = false; };
const coOwner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: false }; USER.loading = false; };

describe('⏹ the strip drops the 1-minute page (2026-11-18)', () => {
  it('owner: no "Gajjala\'s 1-min" tab; 🚩 Gajjala\'s, 🧪 Audited and 👀 Watch stay, in CM_TABS order', async () => {
    owner();
    const { container } = await mount(null);
    expect(tabKeys(container)).not.toContain('gajjala_1m');
    expect(tabTexts(container).some((t) => t.includes(TAB_META.gajjala_1m.label))).toBe(false);
    expect(tabKeys(container)).toEqual(expect.arrayContaining(['gajjala', 'gajjala_audited', 'gajjala_watch']));
    expect(tabTexts(container).some((t) => t.includes(TAB_META.gajjala.label))).toBe(true);
    expect(tabTexts(container).some((t) => t.includes('\u{1F9EA} Gajjala · Audited'))).toBe(true);
    expect(tabTexts(container).some((t) => t.includes(TAB_META.gajjala_watch.label))).toBe(true);
    expect(tabKeys(container)).toEqual(CM_TABS.filter((t) => t !== 'gajjala_1m'));
  });
  it('NEGATIVE: a loaded co-owner loses the 1-minute tab AND the 👀 Watch — nothing else', async () => {
    coOwner();
    const { container } = await mount(null);
    expect(tabKeys(container)).toEqual(CM_TABS.filter((t) => t !== 'gajjala_1m' && t !== 'gajjala_watch' && t !== 'replays'));   // 2026-11-18 rebase: 🎬 Replays is owner-only too
  });
});

describe('⏹ ?tab=gajjala_1m still routes (the 🏁 history page)', () => {
  it('owner: the deep link mounts the board with variant gajjala_1m, though the strip has no tab for it', async () => {
    owner();
    const { container, queryByTestId } = await mount('gajjala_1m');
    expect(queryByTestId('gg-stub')).not.toBeNull();
    expect(queryByTestId('gg-stub')!.getAttribute('data-variant')).toBe('gajjala_1m');
    expect(tabKeys(container)).not.toContain('gajjala_1m');
    expect(container.querySelector('.cm-tabs > a[aria-selected="true"]')).toBeNull();
  });
  it('owner: ?tab=gajjala still mounts the 🚩 board with no variant (GG5 unchanged)', async () => {
    owner();
    const { queryByTestId } = await mount('gajjala');
    expect(queryByTestId('gg-stub')).not.toBeNull();
    expect(queryByTestId('gg-stub')!.getAttribute('data-variant')).toBe('');
  });
  it('NEGATIVE: a non-owner\'s ?tab=gajjala_1m ALSO renders — the page was never owner-only', async () => {
    coOwner();
    const { queryByTestId } = await mount('gajjala_1m');
    expect(queryByTestId('gg-stub')).not.toBeNull();
    expect(queryByTestId('gg-stub')!.getAttribute('data-variant')).toBe('gajjala_1m');
  });
  it('NEGATIVE: nobody signed in — ?tab=gajjala_1m still renders, and it never bounces to the first tab', async () => {
    USER.user = null; USER.loading = false;
    const { queryByTestId } = await mount('gajjala_1m');
    expect(queryByTestId('gg-stub')).not.toBeNull();
    expect(GG.variants).toContain('gajjala_1m');
  });
});
