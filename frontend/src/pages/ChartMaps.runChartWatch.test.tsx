/* 📅 The continuous-chart host also rides 👀 Watch (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay: "Ok then add
 * them to our watch list and track them please..". A 📅 Runners roster name opens the EXISTING continuous chart, so its
 * host mounts on ?tab=gajjala_watch for the LOADED primary owner too; the 📅 strip itself stays 🚩 only.
 * The real page, fetch stubbed, the heavy boards and the chart stubbed. NEGATIVES throughout. */
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
vi.mock('../components/GgRunChart', () => ({
  default: (p: { symbol: string; list: string[] }) => <div data-testid="ggrc-stub" data-symbol={p.symbol} data-list={p.list.join(',')} />,
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
async function openChart() {
  await act(async () => { openGgRunChart('BGLC', ['BGLC', 'POM', 'NCPL']); await new Promise((res) => setTimeout(res, 20)); });
}
const owner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: true }; USER.loading = false; };
const coOwner = () => { USER.user = { email: 'x', is_admin: true, is_primary_admin: false }; USER.loading = false; };

describe('📅 the continuous-chart host on 👀 Watch', () => {
  it('loaded owner on ?tab=gajjala_watch: a roster open draws the (stubbed) chart with the roster list', async () => {
    owner();
    const { findByTestId, queryByTestId } = await mount('gajjala_watch');
    expect(queryByTestId('ggw-stub')).not.toBeNull();
    expect(queryByTestId('ggrc-stub')).toBeNull();
    await openChart();
    const ch = await findByTestId('ggrc-stub');
    expect(ch.getAttribute('data-symbol')).toBe('BGLC');
    expect(ch.getAttribute('data-list')).toBe('BGLC,POM,NCPL');
  });
  it('NEGATIVE: the 📅 strip stays 🚩 only — never on ?tab=gajjala_watch', async () => {
    owner();
    const { queryByTestId } = await mount('gajjala_watch');
    expect(queryByTestId('ggr-strip')).toBeNull();
  });
  it('still on 🚩 for the loaded owner (unchanged)', async () => {
    owner();
    const { findByTestId } = await mount('gajjala');
    await openChart();
    expect(await findByTestId('ggrc-stub')).not.toBeNull();
  });
  it('NEGATIVE: while /auth/me loads on ?tab=gajjala_watch → no host', async () => {
    USER.user = null; USER.loading = true;
    const { queryByTestId } = await mount('gajjala_watch');
    await openChart();
    expect(queryByTestId('ggrc-stub')).toBeNull();
  });
  it('NEGATIVE: a loaded co-owner (no Watch tab) → no host anywhere', async () => {
    coOwner();
    for (const t of ['gajjala_watch', 'gajjala']) {
      const { queryByTestId, unmount } = await mount(t);
      await openChart();
      expect(queryByTestId('ggrc-stub')).toBeNull();
      unmount();
      act(() => closeGgRunChart());
    }
  });
  it('NEGATIVE: any other tab → no host', async () => {
    owner();
    for (const t of [null, 'gajjala_audited', 'luk', 'replays']) {
      const { queryByTestId, unmount } = await mount(t);
      await openChart();
      expect(queryByTestId('ggrc-stub')).toBeNull();
      unmount();
      act(() => closeGgRunChart());
    }
  });
  it('NEGATIVE: ONE host mount in the page source, the strip still behind showRunners', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/pages/ChartMaps.tsx`, 'utf8');
    expect(src.split('<GgRunChartHost').length - 1).toBe(1);
    expect(src).toContain('{showRunners && <GgRunnersStrip />}');
    expect(src).toContain('{showRunHost && <GgRunChartHost />}');
    expect(src).toContain("const showRunHost = showRunners || (tab === 'gajjala_watch' && !meLoading && !!me?.is_primary_admin);");
  });
  it('NEGATIVE: the host mounts AFTER the strip, never behind the old showRunners-only literal; no lazy bypass', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const src: string = fs.readFileSync(`${root}/src/pages/ChartMaps.tsx`, 'utf8');
    expect(src.indexOf('{showRunHost && <GgRunChartHost />}'))
      .toBeGreaterThan(src.indexOf('{showRunners && <GgRunnersStrip />}'));
    expect(src).not.toContain('{showRunners && <GgRunChartHost />}');
    expect(src.split('const showRunHost =').length - 1).toBe(1);
    expect(src).not.toMatch(/showRunChart/);
    expect(src).not.toMatch(/from '\.\.\/components\/GgRunChart'/);
    expect(src).not.toMatch(/lightweight-charts/);
  });
  it('NEGATIVE: opening the chart on 👀 Watch leaves the board in place and brings no 📅 strip with it', async () => {
    owner();
    const { findByTestId, queryByTestId } = await mount('gajjala_watch');
    await openChart();
    await findByTestId('ggrc-stub');
    expect(queryByTestId('ggw-stub')).not.toBeNull();
    expect(queryByTestId('ggr-strip')).toBeNull();
  });
});
