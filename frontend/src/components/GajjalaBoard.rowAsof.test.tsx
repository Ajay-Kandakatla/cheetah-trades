/**
 * 🕐 2026-11-27 (spec sicheck §3.6 D4, K-3): the served `chips.row_asof` = {"text": "as of HH:MM"} prints on a card's chip
 * row RIGHT AFTER the volume chip — the row did not qualify on the shown pass, so its volume is that old (the number
 * itself stays the stale one, HIS CALL #15). The key is ABSENT on a row of the shown pass → no chip, the row identical.
 * Junk (a number, an object without text, a blank) → nothing. Boards are CLONES of the frozen 2026-10-13 hand fixture.
 */
import { cleanup, render, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';
import { shortVol } from '../lib/chartMaps';

const BOARDS: Record<string, any> = (fixture as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const SYM = 'PFAI';

function board(rowAsof?: unknown, present = true) {
  const b = clone(BOARDS.bull_flag);
  b.session = { ...b.session, refresh_sec: 0 };
  const chips = b.tiles.find((t: any) => t.symbol === SYM).gajjala.chips;
  if (present) chips.row_asof = rowAsof;
  else delete chips.row_asof;
  return b;
}

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/chart-maps/gajjala')
    && !String(url).includes('/scan') && !String(url).includes('entry-tape')
    ? { ok: true, status: 200, json: async () => clone(payload) }
    : { ok: true, status: 200, json: async () => ({}) })));
}

async function chipRow(payload: any): Promise<string[]> {
  stub(payload);
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  const tile = r.container.querySelector(`[data-testid="gg-tile-${SYM}"]`) as HTMLElement;
  expect(tile).not.toBeNull();
  const row = within(tile).getByTestId('gg-chip-row');
  return Array.from(row.querySelectorAll('span.cm-badge')).map((s) => s.textContent || '');
}

describe('GajjalaBoard 🕐 row_asof chip', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

  const VOL = `vol ${shortVol(13020000)} (min_av)`;

  it('prints the served text right after the volume chip', async () => {
    const chips = await chipRow(board({ text: 'as of 08:21' }));
    const i = chips.indexOf(VOL);
    expect(i).toBeGreaterThanOrEqual(0);
    expect(chips[i + 1]).toBe('as of 08:21');
    expect(chips.filter((c) => c === 'as of 08:21')).toHaveLength(1);
  });

  it('NEGATIVE: absent key → no chip, the row identical to the row with the chip removed', async () => {
    const without = await chipRow(board(undefined, false));
    cleanup();
    const withIt = await chipRow(board({ text: 'as of 08:21' }));
    expect(without.some((c) => c.startsWith('as of'))).toBe(false);
    expect(withIt.filter((c) => c !== 'as of 08:21')).toEqual(without);
  });

  for (const [name, junk] of [
    ['null', null], ['a number', 821], ['an object without text', {}], ['a numeric text', { text: 821 }],
    ['a blank text', { text: '   ' }], ['a blank string', ''], ['an array', ['as of 08:21']],
  ] as const) {
    it(`NEGATIVE: junk (${name}) → no chip, the row identical`, async () => {
      const without = await chipRow(board(undefined, false));
      cleanup();
      const got = await chipRow(board(junk));
      expect(got).toEqual(without);
    });
  }
});
