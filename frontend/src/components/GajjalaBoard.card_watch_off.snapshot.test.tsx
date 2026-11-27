import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import golden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';

/* 👀 2026-11-18 — the card grid in the Watch layout (spec cardview §4 WP-B step 1). Ajay: "I need the watch list kinda
 * chart formant view video view as default here too from the tabs pages".
 *
 * The OFF proof: with the per-device mode stored OFF (`gg-card-watch` = '0') the 🚩 card grid must stay byte-identical to
 * the grid drawn BEFORE the Watch layout was built. This file and its `.snap` were written and run on the UNMODIFIED board
 * (HEAD 3c0a2ade) before any product edit — the snapshot IS the pre-build DOM. The REAL board and the REAL PatternChart
 * (only the network chips are mocked — the videoLook harness); fixture CLONES only; the wall clock pinned. Display only:
 * nothing here sorts, gates, rings or trades.
 *
 * WIDENED 2026-11-23 — Ajay: "Also add traderview charts on charts please.. Yahoo has been hard to configure" (question
 * card: "TV ↗ button only"). The `.snap` was regenerated ONCE: the only change is one `TV ↗` button (cm-tv, testid
 * tv-link-SYM) right before every tile's Yahoo ↗ — 11 inserts, the rest byte-identical (checked by stripping them).
 *
 * WIDENED 2026-11-27 — Ajay: "find calmer and better setups.." (🧘 GG-like check, spec gglike §4 WP main-session). The
 * potential golden was regenerated with the served `gajjala.gg_like` block, so the `.snap` was regenerated ONCE more: the
 * only change is one `gg-like-card` chip (testid gg-like-card-SYM) on the 6 potential tiles that carry a block — 6
 * inserts, the rest byte-identical (checked by stripping them). The bull_flag grid (hand fixture) did not move. */

vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const HAND: Record<string, any> = (hand as any).boards;
const GOLD: Record<string, any> = (golden as any).boards;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

function boardFor(sub: string): any {
  const b = clone(sub === 'potential' ? GOLD.potential : HAND[sub]);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  return b;
}

function memStorage(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
  };
}

let frameGets = 0;
beforeEach(() => {
  frameGets = 0;
  vi.setSystemTime(new Date('2026-11-13T15:30:00Z'));
  vi.stubGlobal('localStorage', memStorage({ 'gg-card-watch': '0' }));
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.includes('/frames/')) { frameGets += 1; return ok({}); }
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/chart-maps/gajjala')) return ok(boardFor(u.searchParams.get('sub') || 'bull_flag'));
    return ok({});
  }));
});
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

async function gridHtml(sub: string): Promise<string> {
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}>
      <GajjalaBoard variant="gajjala" />
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  await waitFor(() => expect(r.container.querySelector('.cm-grid .gg-card svg.cm-svg')).not.toBeNull());
  const grid = r.container.querySelector('.cm-grid') as HTMLElement;
  expect(grid).not.toBeNull();
  return grid.outerHTML;
}

describe('👀 card grid stored OFF → the pre-build grid, byte for byte', () => {
  for (const sub of ['bull_flag', 'reversal_squeeze', 'potential']) {
    it(`${sub}: the .cm-grid HTML equals the snapshot taken on the unmodified board`, async () => {
      const html = await gridHtml(sub);
      expect(html).toMatchSnapshot();
      /* NEGATIVE: the OFF grid carries none of the Watch layout and asks for no frames */
      expect(html).not.toContain('ggw-');
      expect(html).not.toContain('gg-cardwatch');
      expect(html).not.toContain('gg-card--watch');
      expect(frameGets).toBe(0);
    });
  }
});
