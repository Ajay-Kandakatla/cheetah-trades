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
/* 📅 2026-11-26 (spec runcharts rev 2 §4.3): the chart is stubbed; the REAL host and the REAL open store mount it. */
vi.mock('../components/GgRunChart', () => ({
  default: (p: { symbol: string }) => <div data-testid="ggrc-stub" data-symbol={p.symbol} />,
}));

import ChartMaps from './ChartMaps';
import { closeGgRunChart, openGgRunChart } from '../lib/ggRunChart';

const BOARD = { tab: 'zones', count: 0, matched: 0, scanned: 100, tiles: [], disclaimer: 'Study board.' };
beforeEach(() => {
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL) => {
    const url = String(u);
    return { ok: true, json: async () => (url.includes('/chart-maps?') ? BOARD : {}) } as unknown as Response;
  }));
});
afterEach(() => { cleanup(); act(() => closeGgRunChart()); vi.unstubAllGlobals(); });

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

/* 📅 2026-11-26 — Ajay: "I want you to have continous charts for previous day runners … I wanna able to horizontal scroll
 * tp check continuity like he does". The host rides the EXISTING showRunners flag, right after the strip. */
describe('📅 the continuous-chart host rides showRunners', () => {
  async function openChart() {
    await act(async () => { openGgRunChart('MEDS', ['MEDS', 'MSS']); await new Promise((res) => setTimeout(res, 20)); });
  }
  it('owner on ?tab=gajjala: an open through the store draws the (stubbed) chart', async () => {
    owner();
    const { findByTestId, queryByTestId } = await mount('gajjala');
    expect(queryByTestId('ggrc-stub')).toBeNull();
    await openChart();
    expect((await findByTestId('ggrc-stub')).getAttribute('data-symbol')).toBe('MEDS');
  });
  it('the host draws nothing in place: the strip is still the 🔥 wrapper\'s next sibling, chart open or not', async () => {
    owner();
    const { getByTestId, findByTestId } = await mount('gajjala');
    expect(getByTestId('cm-hot-wrap').nextElementSibling).toBe(getByTestId('ggr-strip'));
    await openChart();
    await findByTestId('ggrc-stub');
    expect(getByTestId('cm-hot-wrap').nextElementSibling).toBe(getByTestId('ggr-strip'));
  });
  it('NEGATIVE: a loaded co-owner on 🚩 → no host', async () => {
    coOwner();
    const { queryByTestId } = await mount('gajjala');
    await openChart();
    expect(queryByTestId('ggrc-stub')).toBeNull();
  });
  it('NEGATIVE: while /auth/me loads on 🚩 → no host', async () => {
    USER.user = null; USER.loading = true;
    const { queryByTestId } = await mount('gajjala');
    await openChart();
    expect(queryByTestId('ggrc-stub')).toBeNull();
  });
  it('NEGATIVE: ChartMaps.tsx mounts <GgRunChartHost exactly once, behind showRunHost (2026-11-26: 🚩 + 👀 Watch, spec watchrun §3.5), after the strip', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/pages/ChartMaps.tsx`, 'utf8');
    expect(src.split('<GgRunChartHost').length - 1).toBe(1);
    expect(src).toContain('{showRunHost && <GgRunChartHost />}');
    expect(src.indexOf('{showRunners && <GgRunnersStrip />}')).toBeGreaterThan(-1);
    expect(src.indexOf('{showRunHost && <GgRunChartHost />}')).toBeGreaterThan(src.indexOf('{showRunners && <GgRunnersStrip />}'));
    expect(src).not.toMatch(/showRunChart/);
    expect(src).not.toMatch(/from '\.\.\/components\/GgRunChart'/);
    expect(src).not.toMatch(/lightweight-charts/);
  });
});
