import { render, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import live from '../lib/__fixtures__/longTerm.live_2026_11_12.json';

/* 🔔 The REAL payload through the REAL component (2026-11-13, pkzone spec main-session). The fixture is the read-only
 * probe's payload.json (throwaway container, worktree mounted RO, scripts/long_term_zone_probe.py) at 01:35 ET on
 * 2026-11-13: off-hours, so the 🔔 block reads the 11-12 close — TSM Agg, META C1, NVDA C2 — and today's log is empty.
 * Ajay 2026-11-12: "add an alert list when stocks reach Pankaj's zones and also tell me if you finish the long term tabs
 * in general". NEGATIVES: no NaN text, no closed-bar at_zone strip beside the 🔔 block, no "buy" word. */

vi.mock('./GrowthChip', () => ({ GrowthChip: () => null }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => null }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => null }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import LongTermBoard from './LongTermBoard';
import { LT_PATH } from '../lib/longTerm';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));

async function mount(body: unknown) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (
    String(url).includes(LT_PATH)
      ? { ok: true, status: 200, json: async () => clone(body) }
      : { ok: true, status: 200, json: async () => ({}) })));
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.lt-board:not([data-state="loading"])')).not.toBeNull());
  return r;
}

afterEach(() => { vi.unstubAllGlobals(); });

describe('📅 Long Term — the live 2026-11-13 payload renders', () => {
  it('the 🔔 block prints the three names in a zone at the 11-12 close, verbatim', async () => {
    const r = await mount(live);
    const alert = (live as any).zones.alert;
    expect(r.container.textContent).toContain(alert.title);
    expect(r.container.textContent).toContain(alert.as_of_text);
    for (const z of alert.now) {
      const node = r.container.querySelector(`[data-testid="lt-zone-now-${z.symbol}"]`);
      expect(node, z.symbol).not.toBeNull();
      expect(node!.textContent).toContain(z.text);
    }
    expect(alert.now.map((z: any) => z.symbol)).toEqual(['TSM', 'META', 'NVDA']);
    expect(r.container.textContent).toContain(alert.log_empty_text);
  });

  it('NEGATIVE: no NaN / undefined text, no at_zone strip beside the 🔔 block, no buy word in the block', async () => {
    const r = await mount(live);
    const text = r.container.textContent || '';
    expect(text).not.toMatch(/\bNaN\b|\bundefined\b/);
    expect(r.container.querySelector('[data-testid="lt-zone-TSM"]')).toBeNull();
    const zones = r.container.querySelector('[data-testid="lt-zones"]');
    expect(zones).not.toBeNull();
    expect(zones!.textContent || '').not.toMatch(/\bbuy\b/i);
  });
});
