import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';

/* 🎾 2026-10-18 (DECISIONS13 D3, BUILD_SPEC13 §2 B2/B6). Ajay: "for the float
 * lower the better is what I wanna follow so sort it by lowest on top". The
 * backend orders the squeeze tiles and SERVES the ordering word as
 * `order_note` (tab.RS_ORDER_TEXT); the board prints it verbatim and types no
 * word of its own. The hand fixture is frozen (D5) — every case here is a CLONE. */

const BOARDS: Record<string, any> = (fixture as any).boards;
const SERVED = '\u{1F3BE} lowest float on top';

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

describe('GajjalaBoard 🎾 order_note (served, printed verbatim)', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  it('prints the served order_note verbatim on a squeeze clone', async () => {
    const { unmount } = await mount('reversal_squeeze', clone('reversal_squeeze', { order_note: SERVED }));
    const el = screen.getByTestId('gg-order-note');
    expect(el.textContent).toBe(SERVED);
    expect(el.className).toContain('gg-muted');
    unmount();
  });

  it('NEGATIVE: nothing when order_note is null', async () => {
    const { unmount } = await mount('reversal_squeeze', clone('reversal_squeeze', { order_note: null }));
    expect(screen.queryByTestId('gg-order-note')).toBeNull();
    unmount();
  });

  it('NEGATIVE: nothing when order_note is absent (an older API) or blank', async () => {
    const { unmount } = await mount('reversal_squeeze', clone('reversal_squeeze', {}));
    expect(screen.queryByTestId('gg-order-note')).toBeNull();
    unmount();
    const b = await mount('reversal_squeeze', clone('reversal_squeeze', { order_note: '   ' }));
    expect(screen.queryByTestId('gg-order-note')).toBeNull();
    b.unmount();
  });

  it('NEGATIVE: nothing on the bull_flag sub (the server serves null there)', async () => {
    const { container, unmount } = await mount('bull_flag', clone('bull_flag', { order_note: null }));
    expect(screen.queryByTestId('gg-order-note')).toBeNull();
    expect(container.textContent).not.toContain('lowest float');
    unmount();
  });

  it('NEGATIVE: no FE vocabulary — an unknown served word prints as that word', async () => {
    const word = 'zz served ordering word 42';
    const { container, unmount } = await mount('reversal_squeeze', clone('reversal_squeeze', { order_note: word }));
    expect(screen.getByTestId('gg-order-note').textContent).toBe(word);
    expect(container.textContent).not.toContain('lowest float');
    unmount();
  });
});
