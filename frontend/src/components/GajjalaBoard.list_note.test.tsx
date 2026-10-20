import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';

/* 🌀 2026-10-20 (BUILD_SPEC18 D3/D6). Ajay: "show me stocks only that have 2
 * contractions". The backend cards only 🌀 reads with at least
 * K4_VCP_MIN_CYCLES contractions and SERVES the "counted, not listed" line as
 * `list_note` (tab.build); the board prints it verbatim and types no word and
 * no number of its own. The hand fixture is frozen — every case here is a CLONE. */

const BOARDS: Record<string, any> = (fixture as any).boards;
const SERVED = '\u{1F300} 13 with fewer than 2 contractions counted, not listed — his K4: a VCP needs at least 2 '
  + 'contractions, each tighter than the one before (S8 33:50)';

function clone(sub: string, patch: Record<string, unknown>) {
  return { ...JSON.parse(JSON.stringify(BOARDS[sub])), ...patch };
}

function stub(payload: any) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/chart-maps/gajjala')
    ? { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(payload)) }
    : { ok: true, status: 200, json: async () => ({}) })));
}

async function mount(sub: string, payload: any) {
  stub(payload);
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

const tileIds = (root: HTMLElement) => [...root.querySelectorAll('[data-testid^="gg-tile-"]')]
  .map((el) => el.getAttribute('data-testid'))
  .filter((id) => id && !id.startsWith('gg-tile-link-'));

describe('GajjalaBoard 🌀 list_note (served, printed verbatim)', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints the served list_note verbatim on an intraday_vcp clone', async () => {
    const { unmount } = await mount('intraday_vcp', clone('intraday_vcp', { list_note: SERVED }));
    const el = screen.getByTestId('gg-list-note');
    expect(el.textContent).toBe(SERVED);
    expect(el.className).toContain('gg-muted');
    unmount();
  });

  it('NEGATIVE: nothing when list_note is null', async () => {
    const { unmount } = await mount('intraday_vcp', clone('intraday_vcp', { list_note: null }));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    unmount();
  });

  it('NEGATIVE: nothing when list_note is absent (an older API) or blank', async () => {
    const a = await mount('intraday_vcp', clone('intraday_vcp', {}));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    a.unmount();
    const b = await mount('intraday_vcp', clone('intraday_vcp', { list_note: '   ' }));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    b.unmount();
  });

  it('NEGATIVE: a non-string list_note prints nothing, never "undefined" or "[object Object]"', async () => {
    const { container, unmount } = await mount('intraday_vcp', clone('intraday_vcp', { list_note: { k: 13 } }));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    expect(container.textContent).not.toContain('[object Object]');
    expect(container.textContent).not.toContain('undefined');
    unmount();
  });

  it('NEGATIVE: the board renders as before — same cards with and without the note', async () => {
    const a = await mount('intraday_vcp', clone('intraday_vcp', {}));
    const before = tileIds(a.container);
    const beforeText = a.container.textContent;
    a.unmount();
    const b = await mount('intraday_vcp', clone('intraday_vcp', { list_note: SERVED }));
    expect(tileIds(b.container)).toEqual(before);
    expect((b.container.textContent || '').replace(SERVED, '')).toBe(beforeText);
    b.unmount();
  });

  it('NEGATIVE: nothing on the bull_flag sub (the server serves null there)', async () => {
    const { container, unmount } = await mount('bull_flag', clone('bull_flag', { list_note: null }));
    expect(screen.queryByTestId('gg-list-note')).toBeNull();
    expect(container.textContent).not.toContain('counted, not listed');
    unmount();
  });

  it('NEGATIVE: no FE vocabulary — an unknown served word prints as that word', async () => {
    const word = 'zz served listing word 42';
    const { container, unmount } = await mount('intraday_vcp', clone('intraday_vcp', { list_note: word }));
    expect(screen.getByTestId('gg-list-note').textContent).toBe(word);
    expect(container.textContent).not.toContain('contractions counted');
    unmount();
  });

  it('NEGATIVE: the printed note never carries the b-word', async () => {
    const { unmount } = await mount('intraday_vcp', clone('intraday_vcp', { list_note: SERVED }));
    expect(screen.getByTestId('gg-list-note').textContent || '').not.toMatch(/boun/i);
    unmount();
  });
});
