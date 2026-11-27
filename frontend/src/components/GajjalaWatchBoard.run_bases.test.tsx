vi.mock('../lib/ggwFrames', async (orig) => (await import('../test/ggwFramesLegacy')).ggwFramesLegacy(orig));
/* 📶 GG's base count on the 👀 Gajjala's Watch 5-min chart (spec ggbase rev 2 WP-E, 2026-11-15).
 * Ajay: "There is a concept of 3 bases and climax run can you bake that in to the app please" · "I need that tracked in
 * to Gajjala's". The 5-min frame serves `run_bases` (backend build.run_bases_keys → the ONE engine's card_block — the
 * same line Gajjala's cards print); the figcaption prints its `text` verbatim as a chip with the served `title` on hover.
 * NEGATIVES: no block / blank text → no chip; the 1-/3-min frames print none; the FE types no word; a served
 * `counter_text` is never printed; the held chip is unchanged; the served `ellipses` are not drawn on this board's
 * 04:00-axis charts (PatternChart's ellipse layer maps by bar index — main session's call). */
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { parseGgw, type GgwBoard } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const TEXT = '📶 3rd base — climax run, GG peels early · forming since 11:10 ET · 5-min bars';
const TITLE = 'GG S8 40:54–41:18: “first base, second base, third base, this is a climax run” — served title';

function board(mut: (b: any) => void = () => {}) {
  const b = clone(fixture) as any;
  b.rows = b.rows.filter((r: any) => r.state !== 'pending');
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  const five = b.rows[0].frames.find((f: any) => f.tf === '5m');
  const bars = five.tile.bars;
  five.run_bases = { n: 2, state: 'forming', text: TEXT, title: TITLE, frame: '5m' };
  five.ellipses = [1, 2, 3].map((n) => ({
    kind: 'run_base', from_t: bars[10 * n].t, to_t: bars[10 * n + 5].t, lo: bars[10 * n].l, hi: bars[10 * n].h,
    label: `${n} base`, note: 'GG note', tone: 'structure', n,
  }));
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
// The junk-block NEGATIVE mounts the board 8 times (~1.5 s alone); under a loaded full suite it crossed vitest's
// 5 s default and its timeout cascaded into the next test. A per-test budget for that ONE test (test harness only —
// no app number); every assertion is unchanged.
const EIGHT_MOUNTS_TIMEOUT_MS = 20_000;
const cap = (c: HTMLElement, sym: string, tf: string) =>
  c.querySelector(`[data-testid="ggw-tile-${sym}"] .ggw-frame[data-tf="${tf}"] figcaption`)!;

beforeEach(() => { vi.useFakeTimers(); });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('📶 base count on the 👀 watch', () => {
  it('the 5-min figcaption prints the served line verbatim with the served title', async () => {
    const { container } = await mount(board());
    const chip = cap(container, 'OMH', '5m').querySelector('[data-testid="ggw-bases"]')!;
    expect(chip.textContent).toBe(TEXT);
    expect(chip.getAttribute('title')).toBe(TITLE);
    expect(chip.className).toBe('ggw-chip ggw-bases');
    expect(container.querySelectorAll('[data-testid="ggw-bases"]')).toHaveLength(1);
  });
  it('NEGATIVE: the 1-/3-min frames and a row without a block print no chip', async () => {
    const { container } = await mount(board());
    for (const tf of ['1m', '3m']) expect(cap(container, 'OMH', tf).querySelector('[data-testid="ggw-bases"]')).toBeNull();
    expect(container.querySelector('[data-testid="ggw-tile-NVDA"] [data-testid="ggw-bases"]')).toBeNull();
  });
  it('NEGATIVE: absent / null / blank / non-string text → no chip; a blank title → no hover', async () => {
    for (const rb of [undefined, null, { text: '   ', title: TITLE }, { text: null }, { text: 3 }, 'a string', []]) {
      const { container, unmount } = await mount(board((b) => {
        const five = b.rows[0].frames.find((f: any) => f.tf === '5m');
        if (rb === undefined) delete five.run_bases; else five.run_bases = rb;
      }));
      expect(container.querySelector('[data-testid="ggw-bases"]')).toBeNull();
      unmount();
    }
    const { container } = await mount(board((b) => { b.rows[0].frames[2].run_bases.title = '  '; }));
    expect(container.querySelector('[data-testid="ggw-bases"]')!.hasAttribute('title')).toBe(false);
  }, EIGHT_MOUNTS_TIMEOUT_MS);
  it('NEGATIVE: a stale counter_text and other served keys are never printed; the FE types no word', async () => {
    const { container } = await mount(board((b) => {
      Object.assign(b.rows[0].frames[2].run_bases, { counter_text: 'COUNTER-SHOULD-NOT-PRINT', state: 'STATE-WORD' });
    }));
    const c = cap(container, 'OMH', '5m');
    expect(container.textContent).not.toContain('COUNTER-SHOULD-NOT-PRINT');
    expect(container.textContent).not.toContain('STATE-WORD');
    expect(c.querySelector('[data-testid="ggw-bases"]')!.textContent).toBe(TEXT);
  });
  it('NEGATIVE: the held chip and the caption label are unchanged by the line', async () => {
    const plain = await mount(board((b) => { delete b.rows[0].frames[2].run_bases; }));
    const before = Array.from(plain.container.querySelectorAll('[data-testid="ggw-held"]')).map((h) => h.textContent);
    const labels0 = Array.from(plain.container.querySelectorAll('.ggw-cap-label')).map((h) => h.textContent);
    plain.unmount();
    const { container } = await mount(board());
    expect(Array.from(container.querySelectorAll('[data-testid="ggw-held"]')).map((h) => h.textContent)).toEqual(before);
    expect(Array.from(container.querySelectorAll('.ggw-cap-label')).map((h) => h.textContent)).toEqual(labels0);
  });
  it('NEGATIVE: the served ellipses are not drawn on the 04:00-axis chart (no run_base ring on the watch)', async () => {
    const { container } = await mount(board());
    expect(container.querySelectorAll('[data-ellipse-kind="run_base"]')).toHaveLength(0);
    expect(container.querySelectorAll('.pc-gg-ellipses')).toHaveLength(0);
  });
});

describe('📶 parseGgw', () => {
  it('keeps the trimmed text + title of the 5-min block, null elsewhere', () => {
    const p = parseGgw(board((b) => { b.rows[0].frames[2].run_bases.text = `  ${TEXT}  `; })) as GgwBoard;
    const fr = p.rows[0].frames;
    expect(fr.find((f) => f.tf === '5m')!.run_bases).toEqual({ text: TEXT, title: TITLE });
    expect(fr.filter((f) => f.tf !== '5m').map((f) => f.run_bases)).toEqual([null, null]);
    expect(p.rows[2].frames.map((f) => f.run_bases)).toEqual([null, null, null]);
  });
  it('NEGATIVE: junk blocks parse to null and never drop the frame', () => {
    for (const rb of [null, 'x', 7, [], { text: '' }, { title: 'only' }]) {
      const p = parseGgw(board((b) => { b.rows[0].frames[2].run_bases = rb; })) as GgwBoard;
      expect(p.rows[0].frames).toHaveLength(3);
      expect(p.rows[0].frames[2].run_bases).toBeNull();
    }
  });
});
