/* 📅 Previous-day runners strip in the 🔥 slot on 🚩 (2026-11-22). Ajay: "remove hot sectors mess from Gajjalas top view I
 * need a new thing there.. use that space between the parent tab of Gajjala and watch tab to be for previous day runners
 * but remove them if they don't run the current day". The real page, fetch stubbed, the heavy boards stubbed.
 * 🔥 is never unmounted (spec D7): a hidden wrapper on 🚩. NEGATIVES throughout. */
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
vi.mock('../components/HotSectors', () => ({ default: () => <div data-testid="hot-stub" /> }));
vi.mock('../components/GgRunnersStrip', () => ({ default: () => <div data-testid="ggr-strip" /> }));

import ChartMaps from './ChartMaps';

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
const owner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: true }; USER.loading = false; };
const coOwner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: false }; USER.loading = false; };

describe('📅 the runners strip takes the 🔥 slot on 🚩', () => {
  it('owner on ?tab=gajjala: 🔥 hidden (still mounted), the strip shows', async () => {
    owner();
    const { getByTestId, queryByTestId } = await mount('gajjala');
    expect(getByTestId('cm-hot-wrap').hidden).toBe(true);
    expect(queryByTestId('hot-stub')).not.toBeNull();
    expect(queryByTestId('ggr-strip')).not.toBeNull();
  });
  it('the strip sits where 🔥 sits — right after the 🔥 wrapper, above the tab bar', async () => {
    owner();
    const { getByTestId } = await mount('gajjala');
    const hot = getByTestId('cm-hot-wrap');
    const strip = getByTestId('ggr-strip');
    const bar = getByTestId('cm-tabs-bar');
    expect(hot.nextElementSibling).toBe(strip);
    expect(strip.compareDocumentPosition(bar) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
  it('NEGATIVE: owner on any other tab keeps 🔥 and gets no strip', async () => {
    owner();
    for (const t of [null, 'gajjala_watch', 'gajjala_audited', 'luk', 'replays']) {
      const { getByTestId, queryByTestId, unmount } = await mount(t);
      expect(getByTestId('cm-hot-wrap').hidden).toBe(false);
      expect(queryByTestId('ggr-strip')).toBeNull();
      unmount();
    }
  });
  it('NEGATIVE: a loaded co-owner on 🚩 keeps 🔥 and never gets the strip', async () => {
    coOwner();
    const { getByTestId, queryByTestId } = await mount('gajjala');
    expect(getByTestId('cm-hot-wrap').hidden).toBe(false);
    expect(queryByTestId('ggr-strip')).toBeNull();
  });
  it('NEGATIVE: while /auth/me loads on 🚩, 🔥 is hidden and no strip yet', async () => {
    USER.user = null; USER.loading = true;
    const { getByTestId, queryByTestId } = await mount('gajjala');
    expect(getByTestId('cm-hot-wrap').hidden).toBe(true);
    expect(queryByTestId('ggr-strip')).toBeNull();
  });
  it('NEGATIVE: the wrapper carries no class (the [hidden] vs display trap)', async () => {
    owner();
    const { getByTestId } = await mount('gajjala');
    expect(getByTestId('cm-hot-wrap').getAttribute('class')).toBeNull();
  });
});
