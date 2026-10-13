import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';

/* 🚩 Gajjala's board through the REAL PatternChart, on the payload fixture
 * (spec §5.4). Today the fixture is a HAND fixture in the §3.4.1 served shape;
 * the main session swaps in a capture from the branch API with the same
 * layout ({boards: {<sub>: payload}}) and this file runs unchanged. Every sub
 * must render, the volume pane and both EMAs must draw, and nothing he reads
 * may say NaN / undefined / None / bounce. */

const BOARDS: Record<string, any> = (fixture as any).boards;

function stub(sub: string) {
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/chart-maps/gajjala')) return { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(BOARDS[sub])) };
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}

describe('GajjalaBoard × the payload fixture (real PatternChart)', () => {
  afterEach(() => { vi.unstubAllGlobals(); });

  for (const sub of Object.keys(BOARDS)) {
    it(`renders the ${sub} board: every served tile, no NaN / undefined / None / bounce`, async () => {
      stub(sub);
      const b = BOARDS[sub];
      const { container, unmount } = render(
        <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${sub}`]}><GajjalaBoard /></MemoryRouter>);
      // Wait on the board LANDING, never on the strip text: tab.strip_text is
      // None when no pass has run (closed day, before 04:00), and a real
      // capture of that state must render, not time out.
      await waitFor(() => expect(container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
      expect(screen.getByTestId('gg-sub-bull_flag')).toBeTruthy();
      if (sub === 'playbook') {
        expect(screen.getByTestId('gg-playbook')).toBeTruthy();
        expect(container.querySelectorAll('svg')).toHaveLength(0);
      } else {
        for (const t of b.tiles) expect(screen.getByTestId(`gg-tile-${t.symbol}`)).toBeTruthy();
        const drawn = b.tiles.filter((t: any) => t.bars.length);
        // one price svg per drawn tile, each with its 📊 volume pane.
        expect(container.querySelectorAll('.pc-vol-pane').length).toBe(drawn.length);
      }
      const txt = container.textContent || '';
      expect(txt).not.toMatch(/bounce/i);
      expect(txt).not.toMatch(/NaN|undefined|\bNone\b|\[object Object\]/);
      unmount();
    });
  }

  // REAL tab.build payloads with no pass on file (fixture `no_pass_boards`):
  // strip.text null, as_of null, refresh_sec 0, no tiles.
  const NO_PASS: Record<string, any> = (fixture as any).no_pass_boards || {};
  it('the fixture carries the no-pass boards', () => {
    expect(Object.keys(NO_PASS).sort()).toEqual(['before_first_pass', 'closed_day']);
  });
  for (const [name, b] of Object.entries(NO_PASS)) {
    it(`NEGATIVE: a no-pass board (${name}) renders — no strip text, no as-of, the served empty_note, no timer`, async () => {
      expect(b.strip.text).toBeNull();
      const si = vi.spyOn(window, 'setInterval');
      vi.stubGlobal('fetch', vi.fn(async (url: string) => (String(url).includes('/chart-maps/gajjala')
        ? { ok: true, status: 200, json: async () => JSON.parse(JSON.stringify(b)) }
        : { ok: true, status: 200, json: async () => ({}) })));
      const { container, unmount } = render(
        <MemoryRouter initialEntries={['/chart-maps?tab=gajjala']}><GajjalaBoard /></MemoryRouter>);
      await waitFor(() => expect(container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
      expect(screen.getByTestId('gg-sub-bull_flag')).toBeTruthy();
      expect(screen.queryByTestId('gg-strip-text')).toBeNull();
      expect(screen.queryByTestId('gg-as-of')).toBeNull();
      expect(screen.getByTestId('gg-session-badge')).toHaveTextContent(b.session.badge);
      expect(screen.getByTestId('gg-empty')).toHaveTextContent(b.empty_note);
      expect(screen.queryAllByTestId(/^gg-tile-/)).toHaveLength(0);
      expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(false);
      const txt = container.textContent || '';
      expect(txt).not.toMatch(/bounce/i);
      expect(txt).not.toMatch(/NaN|undefined|\bNone\b|null|\[object Object\]/);
      si.mockRestore();
      unmount();
    });
  }

  it('the 9 and 21 EMA draw in two different colours on a real tile', async () => {
    stub('bull_flag');
    const { container } = render(
      <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}><GajjalaBoard /></MemoryRouter>);
    await screen.findByTestId('gg-tile-PFAI');
    const tile = screen.getByTestId('gg-tile-PFAI');
    const strokes = new Set([...tile.querySelectorAll('path, polyline')].map((p) => p.getAttribute('stroke')).filter(Boolean));
    expect([...strokes].some((s) => String(s).includes('#2563eb'))).toBe(true);
    expect([...strokes].some((s) => String(s).includes('#f59e0b'))).toBe(true);
    expect(container.textContent).toContain('BUY > 4.12');
  });
});
