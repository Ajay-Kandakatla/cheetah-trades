vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
/* 🔀 9/21 EMA cross blinker on the 👀 Gajjala's Watch (2026-11-15, SPEC blinker §3.5 / §3.9, WP-E (c), C9).
 * Ajay: "On All of the charts and also the tabs I need a new blinker to show me EMA uptrends 9 crossing over 21 EMA
 * please.." · FRAME "Each chart's own frame". Each frame serves its OWN `ema_blink` (frame-level, beside `ema_cross`);
 * the figcaption prints the dot first and the served sentence as one chip. The charts are chartOnly — the chart box
 * carries NO dot (the svg's top-right holds the price axis). NEGATIVES: a frame whose block does not blink → no dot, no
 * chip; the hand-captured fixture (no `ema_blink` anywhere) renders exactly as before; the FE types no word. */
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { parseGgw, type GgwBoard } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const TITLE = '🔀 served short title';
const BLOCKS: Record<string, any> = {
  '1m': { state: 'crossed_up', tier: 'fresh', blink: true, closeness: 0, tf: '1m', text: '● served 1m fresh', title: TITLE },
  '3m': { state: 'closing_in', tier: 'near', blink: true, closeness: 2, tf: '3m', text: '◐ served 3m near', title: TITLE },
  '5m': { state: 'none', tier: null, blink: false, closeness: null, tf: '5m', text: null, title: TITLE },
};

function board(mut: (b: any) => void = () => {}, withBlocks = true) {
  const b = clone(fixture) as any;
  b.rows = b.rows.filter((r: any) => r.state !== 'pending');
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  if (withBlocks) for (const f of b.rows[0].frames) f.ema_blink = clone(BLOCKS[f.tf]);
  mut(b);
  return b;
}
function stub(b: any) {
  vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, json: async () => b }) as unknown as Response));
}
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
async function mount(b: any) {
  stub(b);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch']}><GajjalaWatchBoard /></MemoryRouter>);
  await flush();
  await flush();
  return r;
}
const frame = (c: HTMLElement, sym: string, tf: string) =>
  c.querySelector(`[data-testid="ggw-tile-${sym}"] .ggw-frame[data-tf="${tf}"]`)!;

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🔀 blinker on the 👀 watch', () => {
  it('parseFrame keeps the served frame-level block; junk → null', () => {
    const p = parseGgw(board()) as GgwBoard;
    expect(p.rows[0].frames.map((f) => f.ema_blink?.tier ?? null)).toEqual(['fresh', 'near', null]);
    const j = parseGgw(board((b) => { b.rows[0].frames[0].ema_blink = 'x'; b.rows[0].frames[1].ema_blink = [1]; })) as GgwBoard;
    expect(j.rows[0].frames[0].ema_blink).toBeNull();
    expect(j.rows[0].frames[1].ema_blink).toBeNull();
    expect((parseGgw(board(() => {}, false)) as GgwBoard).rows[0].frames.every((f) => f.ema_blink === null)).toBe(true);
  });

  it('three frames, three states: the figcaption dot first per blinking frame + the served sentence chip', async () => {
    const { container } = await mount(board());
    const f1 = frame(container, 'OMH', '1m');
    const cap1 = f1.querySelector('figcaption')!;
    const dot1 = cap1.querySelector('[data-testid="ggw-ema-blink-dot-OMH-1m"]')!;
    expect(dot1.className).toBe('ema-blink-dot ema-blink-fresh');
    expect(cap1.firstElementChild).toBe(dot1);
    expect(cap1.querySelector('[data-testid="ggw-ema-blink-OMH-1m"]')!.textContent).toBe('● served 1m fresh');
    expect(cap1.querySelector('[data-testid="ggw-ema-blink-OMH-1m"]')!.className).toBe('ggw-chip ema-blink-chip');
    expect(cap1.querySelector('[data-testid="ggw-ema-blink-OMH-1m"]')!.getAttribute('title')).toBe(TITLE);
    const cap3 = frame(container, 'OMH', '3m').querySelector('figcaption')!;
    expect(cap3.querySelector('.ema-blink-dot')!.className).toBe('ema-blink-dot ema-blink-near');
    expect(cap3.querySelector('[data-testid="ggw-ema-blink-OMH-3m"]')!.textContent).toBe('◐ served 3m near');
    // NEGATIVE: the 5m block does not blink → no dot, no chip
    const cap5 = frame(container, 'OMH', '5m').querySelector('figcaption')!;
    expect(cap5.querySelector('.ema-blink-dot')).toBeNull();
    expect(cap5.querySelector('.ema-blink-chip')).toBeNull();
    expect(container.querySelectorAll('.ema-blink-dot')).toHaveLength(2);
  });

  it('NEGATIVE (C9): the chart box itself carries no dot and no line', async () => {
    const { container } = await mount(board());
    for (const box of Array.from(container.querySelectorAll('.ggw-chartbox'))) {
      expect(box.querySelector('.ema-blink-dot')).toBeNull();
      expect(box.querySelector('.ema-blink-line')).toBeNull();
    }
  });

  it('NEGATIVE: the hand-captured fixture (no blocks) renders exactly as before — no dot, no chip, captions unchanged', async () => {
    const { container } = await mount(board(() => {}, false));
    expect(container.querySelector('.ema-blink-dot')).toBeNull();
    expect(container.querySelector('.ema-blink-chip')).toBeNull();
    const labels = Array.from(container.querySelectorAll('.ggw-cap-label')).map((n) => n.textContent);
    expect(labels.length).toBeGreaterThan(0);
    const withB = await mount(board());
    const labels2 = Array.from(withB.container.querySelectorAll('[data-testid="ggw-tile-OMH"] .ggw-cap-label, [data-testid="ggw-tile-NVDA"] .ggw-cap-label'))
      .map((n) => n.textContent);
    expect(labels2.slice(0, labels.length)).toEqual(labels);
  });

  it('NEGATIVE: a blinking block with a blank text → the dot, but no empty chip', async () => {
    const { container } = await mount(board((b) => { b.rows[0].frames[0].ema_blink.text = '   '; }));
    const cap1 = frame(container, 'OMH', '1m').querySelector('figcaption')!;
    expect(cap1.querySelector('.ema-blink-dot')).not.toBeNull();
    expect(cap1.querySelector('.ema-blink-chip')).toBeNull();
  });
});
