/* PatternsBoard — 📐 Chart Patterns, mounted as a Chart Maps tab (2026-09-09).
 *
 * Ajay: "Can you move chart patterns in to the Chartmaps page please and show
 * the winning charts".
 *
 * What these pin, and why. He has real money on this app and NONE of these
 * patterns beats a coin flip in his own ledger, so the two things that would
 * mislead him are (a) the board losing the link to the charts that actually
 * worked — the only honest use of it — and (b) the per-pattern link silently
 * dropping its filter, which would send him to an "all patterns" wall and read
 * as "these are this pattern's winners". Both are pinned here.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { PatternsBoard, winnersHref } from './PatternsPage';

const NAV = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => NAV };
});
vi.mock('../hooks/useCurrentUser', () => ({ useCurrentUser: () => ({ user: null }) }));

const LATEST = {
  ok: true,
  generated_at: 1789000000,
  results: [
    { symbol: 'BKH', pattern: 'cup_with_handle', status: 'confirmed', confirmed_date: '2026-09-09',
      last_close: 72.82, neckline: 74.16, stop: 70.51, target: 78.24, ext_past_confirm_pct: 0.4,
      lows: [{ price: 70.1, date: '2026-07-14' }], sepa: { is_candidate: true, rs_rank: 71, stage: 2 } },
    { symbol: 'CRC', pattern: 'double_bottom', status: 'forming', to_confirm_pct: 1.8,
      last_close: 56.7, neckline: 57.7, stop: 50.51, target: 62.21,
      lows: [{ price: 50.9, date: '2026-08-01' }], sepa: {} },
  ],
  validation: {},
};

function stubFetch() {
  return vi.fn((url: string) => {
    const body = String(url).includes('/patterns/latest') ? LATEST
      : String(url).includes('/patterns/accuracy') ? { ok: true, patterns: {}, candles: {}, pending: 0 }
      : { ok: true };
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });
}

const draw = () => render(<MemoryRouter><PatternsBoard /></MemoryRouter>);

beforeEach(() => { NAV.mockClear(); vi.stubGlobal('fetch', stubFetch()); });
afterEach(() => { vi.unstubAllGlobals(); });

describe('winnersHref — the link into the charts that worked', () => {
  it('filters Past Winners to the pattern you are looking at', () => {
    expect(winnersHref('cup_with_handle')).toBe('/chart-maps?tab=winners&pattern=cup_with_handle');
    expect(winnersHref('inverse_head_shoulders'))
      .toBe('/chart-maps?tab=winners&pattern=inverse_head_shoulders');
  });

  it('drops the filter rather than sending a broken one (NEGATIVE)', () => {
    // An empty/absent pattern must not produce `&pattern=` — the winners tab
    // reads that as a real filter and would render an empty wall.
    for (const junk of [null, undefined, '']) {
      expect(winnersHref(junk as string | null)).toBe('/chart-maps?tab=winners');
    }
  });

  it('escapes anything that would break the query string', () => {
    expect(winnersHref('a b&c=d')).toBe('/chart-maps?tab=winners&pattern=a%20b%26c%3Dd');
  });
});

describe('PatternsBoard — mounted as a tab', () => {
  it('drops the page title (the tab header says it) but keeps the board', async () => {
    draw();
    expect(await screen.findByText('BKH')).toBeInTheDocument();
    // The standalone page's lede must not double up under the tab heading.
    expect(screen.queryByText(/confirmation-line discipline/)).not.toBeVisible();
  });

  it('offers the winning charts at board level', async () => {
    draw();
    const btn = await screen.findByRole('button', { name: /Show the winning charts/i });
    fireEvent.click(btn);
    expect(NAV).toHaveBeenCalledWith('/chart-maps?tab=winners');
  });

  it('every card links to ITS OWN pattern winners, not the whole wall', async () => {
    draw();
    await screen.findByText('BKH');
    const links = screen.getAllByRole('button', { name: /winning charts/i });
    // one board-level door + one per card
    expect(links.length).toBe(1 + LATEST.results.length);
    fireEvent.click(links[1]);
    expect(NAV).toHaveBeenCalledWith('/chart-maps?tab=winners&pattern=cup_with_handle');
  });
});
