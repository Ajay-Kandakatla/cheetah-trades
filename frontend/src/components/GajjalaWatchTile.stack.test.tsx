/* 👀 the Watch tile's opt-in props for the 🚩 / 🧪 card grid (2026-11-18, cardview spec §3.4 / §4 WP-A). Ajay 2026-11-18:
 * "I need the watch list kinda chart formant view video view as default here too from the tabs pages".
 * `stack` stacks the frames in `order` on a board tile; `extra` sits right after SYM; `onRemove` is optional (no ✕
 * without it); a Frame printing served empty words carries data-empty="1" and, in stack mode only, flexGrow 0.
 * NEGATIVES: the ⤢ view keeps flexGrow 1 and its own testid; a Watch tile keeps its 1m-on-top split with no data-empty;
 * no ✕ without onRemove; no extra → today's head; the tile types no sentence of its own. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import { GGW_PAGER, GGW_STRETCH, parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import { YAHOO_LABEL } from '../lib/yahooLink';
import { TV_LABEL } from '../lib/tvChart';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
const S = (fixture as any).rows[0].symbol as string;
const WORDS = `No 1-minute bars stored for ${S} this session yet — a pass has to read it first`;

/** OMH's served row, frames relabelled 15m / 5m / 1m as the card view serves them; `mut` edits the raw frames. */
function cardRow(mut: (fr: any) => void = () => {}): GgwRow {
  const raw = clone(fixture) as any;
  const r = raw.rows[0];
  for (const f of r.frames) { if (f.tf === '3m') f.tf = '15m'; mut(f); }
  raw.rows = [r];
  return (parseGgw(raw) as GgwBoard).rows[0];
}
const emptyOneMin = () => cardRow((fr) => { if (fr.tf === '1m') { fr.tile.bars = []; fr.empty_text = WORDS; } });
const watchRow = (): GgwRow => (parseGgw(clone(fixture)) as GgwBoard).rows[0];
type P = Partial<Parameters<typeof Tile>[0]>;
const tile = (row: GgwRow, p: P = {}) => render(
  <MemoryRouter>
    <Tile row={row} phone={false} fit={false} removeLabel="Remove" focused={false} busy={false} {...p} />
  </MemoryRouter>);
const headKids = (sym: string) => Array.from(screen.getByTestId(`ggw-tile-${sym}`).querySelector('.ggw-tile-head')!.children)
  .map((c) => `${c.tagName}.${c.className}`);
const growOf = (sym: string, tf: string) => (document.querySelector(`[data-testid="ggw-frame-${sym}-${tf}"]`) as HTMLElement).style.flexGrow;

afterEach(() => { cleanup(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

describe('(a) stack: the frames stacked in order on a board tile', () => {
  it('15m above 5m above 1m in DOM order; NEGATIVE: no ⤡, no ◀ ▶, no ⤢ testid block', () => {
    tile(cardRow(), { stack: true, order: GGC_STRETCH_ORDER, onStretch: () => {} });
    const block = screen.getByTestId('ggw-stack-charts');
    expect(block.className).toBe('ggw-dark ggw-charts ggw-charts--stretch ggw-charts--stack');
    expect(Array.from(block.querySelectorAll(':scope > figure')).map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
    expect(screen.queryByTestId('ggw-stretch-charts')).toBeNull();
    expect(screen.queryByTestId('ggw-unstretch')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-prev')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-next')).toBeNull();
    expect(screen.getByTestId(`ggw-stretch-btn-${S}`).textContent).toBe(GGW_STRETCH.open);
    expect(document.querySelector('.ggw-frame-pair')).toBeNull();
  });
  it('NEGATIVE: stack with no frames → no charts block at all', () => {
    const r = cardRow();
    tile({ ...r, frames: [] }, { stack: true, order: GGC_STRETCH_ORDER });
    expect(screen.queryByTestId('ggw-stack-charts')).toBeNull();
    expect(document.querySelector('.ggw-charts')).toBeNull();
  });
});

describe('(b) onRemove is optional', () => {
  it('NEGATIVE: no onRemove → no ✕ button', () => {
    tile(cardRow(), { stack: true, order: GGC_STRETCH_ORDER });
    expect(document.querySelector('.ggw-remove')).toBeNull();
    expect(screen.getByTestId(`ggw-tile-${S}`).textContent).not.toContain('✕');
  });
  it('with onRemove → the ✕ exactly as today (title, label, busy, the click passes SYM)', () => {
    const onRemove = vi.fn();
    tile(watchRow(), { onRemove });
    const x = document.querySelector('.ggw-remove') as HTMLButtonElement;
    expect(x.textContent).toBe('✕');
    expect(x.getAttribute('title')).toBe(`Remove ${S}`);
    expect(x.getAttribute('aria-label')).toBe(`Remove ${S}`);
    expect(x.disabled).toBe(false);
    fireEvent.click(x);
    expect(onRemove.mock.calls).toEqual([[S]]);
    cleanup();
    tile(watchRow(), { onRemove, busy: true });
    expect((document.querySelector('.ggw-remove') as HTMLButtonElement).disabled).toBe(true);
  });
});

describe('(c) extra sits right after SYM', () => {
  it('the extra node is the next sibling of .ggw-sym, before the A+ chip', () => {
    const row = { ...cardRow(), aplus: { tag: '🎯', text: 'A+ 09:41', title: null, items: [] } };
    tile(row, { stack: true, order: GGC_STRETCH_ORDER, extra: <span data-testid="x-extra">E</span> });
    const sym = screen.getByTestId(`ggw-tile-${S}`).querySelector('.ggw-sym')!;
    expect(sym.nextElementSibling).toBe(screen.getByTestId('x-extra'));
    expect(screen.getByTestId('x-extra').nextElementSibling).toBe(screen.getByTestId('ggw-aplus'));
  });
  it("NEGATIVE: absent → the head's child list is today's (same as a Watch tile's)", () => {
    tile(watchRow(), { onRemove: () => {} });
    const watch = headKids(S);
    expect(watch[0]).toBe('B.ggw-sym');
    cleanup();
    tile(watchRow(), { onRemove: () => {}, extra: undefined });
    expect(headKids(S)).toEqual(watch);
    cleanup();
    tile(watchRow(), { onRemove: () => {}, extra: <i data-testid="x-extra" /> });
    expect(headKids(S)).toHaveLength(watch.length + 1);
  });
});

describe('(d) an empty frame: data-empty + flexGrow 0 in stack mode only', () => {
  it('stack + fit: the empty 1m → data-empty="1" and flexGrow 0; 15m / 5m → 1 and no data-empty', () => {
    tile(emptyOneMin(), { stack: true, fit: true, order: GGC_STRETCH_ORDER });
    const one = screen.getByTestId(`ggw-frame-${S}-1m`);
    expect(one.getAttribute('data-empty')).toBe('1');
    expect(screen.getByTestId(`ggw-frame-empty-${S}-1m`).textContent).toBe(WORDS);
    expect(growOf(S, '1m')).toBe('0');
    for (const tf of ['15m', '5m']) {
      expect(growOf(S, tf)).toBe('1');
      expect(screen.getByTestId(`ggw-frame-${S}-${tf}`).hasAttribute('data-empty')).toBe(false);
    }
  });
  it('NEGATIVE: stack without fit → no inline style on any frame', () => {
    tile(emptyOneMin(), { stack: true, fit: false, order: GGC_STRETCH_ORDER });
    for (const tf of ['15m', '5m', '1m']) expect(screen.getByTestId(`ggw-frame-${S}-${tf}`).getAttribute('style')).toBeNull();
  });
  it('NEGATIVE: the ⤢ view (GgwStretch kind="card") keeps flexGrow 1 on the same empty frame and NO ggw-stack-charts', () => {
    render(<MemoryRouter><GgwStretch row={emptyOneMin()} phone={false} removeLabel={null} onClose={() => {}} onStep={null}
                                     order={GGC_STRETCH_ORDER} kind="card" /></MemoryRouter>);
    expect(screen.queryByTestId('ggw-stack-charts')).toBeNull();
    const block = screen.getByTestId('ggw-stretch-charts');
    expect(block.className).toBe('ggw-dark ggw-charts ggw-charts--stretch');
    for (const tf of ['15m', '5m', '1m']) expect(growOf(S, tf)).toBe('1');
    expect(screen.getByTestId(`ggw-frame-${S}-1m`).getAttribute('data-empty')).toBe('1');
  });
  it('NEGATIVE: onUnstretch wins over stack (the ⤢ tile is never a stack tile)', () => {
    tile(emptyOneMin(), { stack: true, fit: true, order: GGC_STRETCH_ORDER, onUnstretch: () => {} });
    expect(screen.queryByTestId('ggw-stack-charts')).toBeNull();
    expect(growOf(S, '1m')).toBe('1');
  });
});

describe('(e) a Watch tile renders exactly as today', () => {
  it('NEGATIVE: no stack + onRemove + 1m/3m/5m → 1m on top, 3m + 5m in the pair, no data-empty, no stack block', () => {
    const { container } = tile(watchRow(), { onRemove: () => {}, fit: true });
    const charts = container.querySelector('.ggw-charts')!;
    expect(charts.className).toBe('ggw-dark ggw-charts');
    expect(charts.firstElementChild!.getAttribute('data-tf')).toBe('1m');
    expect(Array.from(charts.querySelectorAll('.ggw-frame-pair > figure')).map((f) => f.getAttribute('data-tf'))).toEqual(['3m', '5m']);
    expect(container.querySelector('[data-empty]')).toBeNull();
    expect(screen.queryByTestId('ggw-stack-charts')).toBeNull();
    expect(screen.queryByTestId('ggw-stretch-charts')).toBeNull();
    expect(container.querySelector('.ggw-remove')).not.toBeNull();
  });
});

describe('(f) the tile types no sentence of its own', () => {
  /** Every string the fixture serves, anywhere in it. */
  const served = new Set<string>();
  const walk = (x: unknown) => {
    if (typeof x === 'string') served.add(x.trim());
    else if (Array.isArray(x)) x.forEach(walk);
    else if (x && typeof x === 'object') Object.values(x).forEach(walk);
  };
  walk(fixture);
  served.add(WORDS);
  // WIDENED 2026-11-23 (+ TV_LABEL) — Ajay: "Also add traderview charts on charts please.." (question card: "TV ↗ button
  // only"): the TV ↗ link-out label is a structural control glyph like Yahoo ↗.
  const GLYPHS = new Set<string>([GGW_STRETCH.open, TV_LABEL, YAHOO_LABEL, '✕', '⚠️', GGW_PAGER.prev, GGW_PAGER.next]);
  it('every visible text node outside the svg is served (or a structural glyph); split on " · " and a leading ⚠️', () => {
    const { container } = tile(emptyOneMin(), { stack: true, fit: true, order: GGC_STRETCH_ORDER, onStretch: () => {} });
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
    const bad: string[] = [];
    let n = 0;
    for (let t = walker.nextNode(); t; t = walker.nextNode()) {
      if ((t.parentElement as Element).closest('svg')) continue;
      const txt = (t.textContent || '').trim();
      if (!txt) continue;
      n += 1;
      for (const part of txt.replace(/^⚠️\s*/, '').split(' · ')) {
        const p = part.trim();
        if (p && !served.has(p) && !GLYPHS.has(p)) bad.push(p);
      }
    }
    expect(n).toBeGreaterThan(3);
    expect(bad).toEqual([]);
  });
  it('NEGATIVE: the tile file renders no house chip, no 📡 and no feed word', async () => {
    const src = await readSource('src/components/GajjalaWatchTile.tsx');
    expect(src).not.toMatch(/<(GrowthChip|ExplosiveChip|ShortInterestChip)\b/);
    expect(src).not.toContain('📡');
    expect(noComments(src)).not.toMatch(/['"`][^'"`\n]*\b(kicked|quiet|reconnect)/i);
  });
});
