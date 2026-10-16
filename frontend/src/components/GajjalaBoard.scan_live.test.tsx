import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '../hooks/useUser';

/* 🔄 scan on open + 🎯 A+ banner — the LIVE capture (BUILD_SPEC5 §4 WP-M / §5.4.10, 2026-10-16).
 *
 * Ajay 2026-10-15: "When ever I open Gajjala's intiate a new scan of stocks.  In that
 * moment and if there are any enterable stocks on the top which I see in potential i guess"
 *
 * Renders the payloads the main session captured from the branch api
 * (__fixtures__/gajjala_on_open_live_2026_10_15.json — never typed by hand; SKIPPED while
 * the file is absent). Shape-only: the capture may be a closed-state board (no pass on
 * file), so these assert only what holds on ANY real payload — the 🎯 line is present,
 * the as-of line is a served string, every banner row prints its served text, and no
 * NaN / undefined / None / the b-word / "enterable" reaches the DOM. The board composes
 * no word of its own. */

const GUEST: CurrentUser = { email: 'guest@example.com', is_admin: false } as any;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: GUEST, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
async function readJsonIfPresent(rel: string): Promise<any | null> {
  const fs = await fsMod();
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}

const LIVE: any = await readJsonIfPresent('src/components/__fixtures__/gajjala_on_open_live_2026_10_15.json');
const LB: Record<string, any> = LIVE?.boards || {};
const SUBS = Object.keys(LB);
const clone = (x: any) => JSON.parse(JSON.stringify(x));

function stubFetch(sub: string) {
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: any) => {
    if (init?.method === 'POST') return { ok: true, status: 200, json: async () => clone(LIVE?.post || {}) };
    const u = new URL(String(url), 'http://x');
    const key = u.searchParams.get('sub') || sub;
    return { ok: true, status: 200, json: async () => clone(LB[key] || LB[sub]) };
  }));
}
const mount = (sub: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}><GajjalaBoard /></MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

const BANNED = /NaN|undefined|\bNone\b|\[object Object\]/;
const BWORD = new RegExp(['b', 'ounce'].join(''), 'i');

describe('GajjalaBoard — 🔄 scan on open + 🎯 A+ banner (LIVE capture)', () => {
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  it.skipIf(!LIVE)('the capture holds at least one board and the POST answer', () => {
    expect(SUBS.length).toBeGreaterThan(0);
    expect(typeof LIVE._recipe).toBe('string');
    expect(LIVE.post && typeof LIVE.post.state).toBe('string');
    for (const sub of SUBS) {
      expect(LB[sub].scan, `${sub}: scan block`).toBeTruthy();
      expect(LB[sub].enterable, `${sub}: enterable block`).toBeTruthy();
    }
  });

  it.skipIf(!LIVE)('every captured sub renders the 🎯 line and a SERVED as-of line', async () => {
    for (const sub of SUBS) {
      stubFetch(sub);
      const { container, unmount } = mount(sub);
      await loaded(container);
      const b = LB[sub];
      expect(screen.getByTestId('gg-aplus'), `${sub}: gg-aplus`).toBeTruthy();
      const asOf = screen.queryByTestId('gg-as-of');
      if (asOf) {
        const servedAsOf = [b.scan?.as_of_text, b.pass?.as_of_et ? `as of ${b.pass.as_of_et}` : null].filter(Boolean);
        expect(servedAsOf, `${sub}: as-of is a served string`).toContain(asOf.textContent);
      }
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it.skipIf(!LIVE)('every banner row prints its served text, in the served order (the FE composes nothing)', async () => {
    for (const sub of SUBS) {
      stubFetch(sub);
      const { container, unmount } = mount(sub);
      await loaded(container);
      const rows = Array.from(container.querySelectorAll('[data-testid^="gg-aplus-row-"]'));
      const served = (LB[sub].enterable?.rows || []) as any[];
      expect(rows.length, `${sub}: row count`).toBe(served.length);
      served.forEach((r, i) => expect(rows[i].textContent, `${sub}: row ${i}`).toBe(r.text));
      if (!served.length && LB[sub].enterable?.empty_text) {
        expect(screen.getByTestId('gg-aplus-empty').textContent).toBe(LB[sub].enterable.empty_text);
      }
      unmount();
      vi.unstubAllGlobals();
    }
  });

  it.skipIf(!LIVE)('NEGATIVE: never NaN / undefined / None / the b-word / "enterable" in the rendered text', async () => {
    for (const sub of SUBS) {
      stubFetch(sub);
      const { container, unmount } = mount(sub);
      await loaded(container);
      const txt = container.textContent || '';
      expect(txt, sub).not.toMatch(BANNED);
      expect(txt, sub).not.toMatch(BWORD);
      expect(txt.toLowerCase(), sub).not.toContain('enterable');
      unmount();
      vi.unstubAllGlobals();
    }
  });
});
