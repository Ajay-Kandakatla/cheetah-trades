import { render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import {
  GGC_CARD_SQUEEZE, GGC_FETCH_FAILED, GGC_NO_FRAMES, GGC_STRETCH_ORDER, ggcIsSqueeze, ggcRow, parseGgc, type GgcPayload,
} from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import { GGW_FIT_GROW, GGW_LAYOUTS, type GgwRow } from '../lib/gajjalaWatch';
import type { GgCardWatch } from '../hooks/useGgCardWatch';

/* 🎾 GgCardTile — the 🎾 card drawn as the 👀 Watch tile (2026-11-23, rswatch spec §3.8 / §3.9 / §4 WP fe-grid).
 * Ajay 2026-11-23: "In the reversal squeeze can you make the charts same as in watch list please".
 *
 * The REAL Watch Tile / Frame / PatternChart, a hand-built `cw` (the stubCw shape of GgCardGrid.test.tsx, cloned — the
 * GgCardWatch type has no new field). Frames = CLONES of the 2026-11-15 Watch fixture's OMH frames (3m relabelled 15m);
 * the squeeze payload is 1m / 5m / 15m, echoes `card: "squeeze"`, keeps the served cross markers + K5, and carries a
 * hand-built prior tail on the 5m (a lead axis). The 🎾 card = FCHL of the frozen 2026-10-13 hand fixture, cloned, with
 * `tf`, `ellipses` (one on tail bars) and an A+ marker set on the CLONE. Fixtures are never edited.
 * NEGATIVES: a bull_flag card with the SAME payload stacks; a 🎾 card whose row came from the PLAIN payload stacks (the
 * tile switches on the ROW, never on the card [C2]); loading / failed / served-error rows print what a stacked card
 * prints; no ✕, no tags row. CSS: the new block is appended after the 11-18 block, never edits it, no !important.
 * Display only, UNMEASURED. */

vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: any) => <span data-testid={`ggwatch-${symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./PromoOriginChip', () => ({ PromoOriginChip: () => <span /> }));
vi.mock('./SignalWatchButton', () => ({ SignalWatchButton: () => <span /> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgCardTile } from './GgCardGrid';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
const WATCH_ORDER = ['1m', '5m', '15m'];
const SYM = 'FCHL';
const PRIOR_DAY = '2026-11-12';
const tailStamp = (i: number) => {
  const m = 15 * 60 + 5 * (i + 1);
  return `${PRIOR_DAY} ${String(Math.floor(m / 60)).padStart(2, '0')}:${String(m % 60).padStart(2, '0')}`;
};
function frame(tf: string, squeeze: boolean) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = SYM;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  if (!squeeze) {
    f.tile.markers = []; f.ema_cross = null; f.uptrend = null;
  } else if (tf === '5m') {
    const tail = Array.from({ length: 12 }, (_, i) => ({ t: tailStamp(i), o: 3.9, h: 3.95, l: 3.85, c: 3.92, v: 1000, s: 'post' }));
    f.tile.bars = [...tail, ...f.tile.bars];
    for (const c of f.tile.curves) c.values = [...tail.map(() => 3.9), ...c.values];
    f.axis = { ...f.axis, lead: 60, slots: f.axis.slots + 60, x: [...tail.map((_, i) => i), ...f.axis.x.map((s: number) => s + 60)],
      shade: [{ from_slot: 12, to_slot: 60, kind: 'post' }, ...f.axis.shade.map((s: any) => ({ ...s, from_slot: s.from_slot + 60, to_slot: s.to_slot + 60 }))],
      ticks: [{ slot: 0, label: 'Nov 12' }, ...f.axis.ticks.map((t: any) => ({ ...t, slot: t.slot + 60 }))] };
  }
  return f;
}
const rawPlain = () => ({
  state: 'ok', symbol: SYM, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(tf, false)),
});
const rawSqueeze = () => ({ ...rawPlain(), frames: WATCH_ORDER.map((tf) => frame(tf, true)), card: GGC_CARD_SQUEEZE });
const plainP = () => parseGgc(rawPlain()) as GgcPayload;
const squeezeP = () => parseGgc(rawSqueeze()) as GgcPayload;
const SERVED_KINDS = ['earlier_try', 'tennis_ball'];
function squeezeCard(): GgTile {
  const t = clone((hand as any).boards.reversal_squeeze.tiles[0]);
  t.tf = '5m';
  t.ellipses = [
    { kind: 'earlier_try', from_t: tailStamp(1), to_t: tailStamp(4), lo: 3.85, hi: 3.95, label: 'earlier try', tone: 'structure' },
    { kind: 'tennis_ball', from_t: '2026-11-13 07:00', to_t: '2026-11-13 07:30', lo: 4.0, hi: 4.2, label: 'tennis ball', tone: 'structure' },
  ];
  t.markers = [{ date: '2026-11-13 07:30', kind: 'buy', label: 'A+' }];
  return t as GgTile;
}
const bullCard = (): GgTile => {
  const t = squeezeCard();
  return { ...t, gajjala: { ...(t.gajjala as any), setup: 'bull_flag' } } as GgTile;
};

type RowKind = 'squeeze' | 'plain' | 'failed' | 'error' | 'loading';
/** The stubCw shape of GgCardGrid.test.tsx:75-96, cloned. `squeeze` → what the hook's rowOf gives (squeeze opt for a 🎾
 *  card only); `plain` → a 🎾 card's row built from the PLAIN payload WITH the squeeze opt (the deploy skew). */
function stubCw(rowKind: RowKind = 'squeeze', look?: 'video', over: Partial<GgCardWatch> = {}): GgCardWatch {
  const rowOf = (card: GgTile): GgwRow => {
    if (rowKind === 'squeeze') return ggcRow(card, squeezeP(), look, ggcIsSqueeze(card) ? { plan: false, squeeze: true } : { plan: false });
    if (rowKind === 'plain') return ggcRow(card, plainP(), look, { plan: false, squeeze: true });
    if (rowKind === 'failed') return { symbol: card.symbol, state: 'error', text: GGC_FETCH_FAILED, ...GGC_NO_FRAMES };
    if (rowKind === 'error') return { symbol: card.symbol, state: 'error', text: 'served reason words', ...GGC_NO_FRAMES };
    return { symbol: card.symbol, state: 'loading', text: null, ...GGC_NO_FRAMES };
  };
  return {
    on: true, allowed: true, toggle: () => {}, active: true, phone: false, layout: 2, setLayout: vi.fn(),
    page: 0, pages: 1, paged: false, goPage: vi.fn(), pick: null, usePick: false, togglePick: vi.fn(),
    shown: () => true, rowOf, liveOf: () => undefined,
    grid: GGW_LAYOUTS[2], fit: false, rowH: null,
    boardRef: { current: null }, headRef: { current: null }, gridRef: { current: null },
    ...over,
  };
}
const ROUTE = '/chart-maps?tab=gajjala&sub=reversal_squeeze';
const tileOf = (card: GgTile, cw: GgCardWatch) => render(
  <MemoryRouter initialEntries={[ROUTE]}><GgCardTile card={card} cw={cw} onStretch={() => {}} /></MemoryRouter>);
const frameEl = (tf: string) => screen.getByTestId(`ggw-frame-${SYM}-${tf}`);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🎾 the 🎾 tile = the Watch Tile\'s own split branch', () => {
  for (const look of [undefined, 'video'] as const) {
    it(`(${look ?? 'no look'}) no stack; 1m on top; the pair = 5m then 15m; marks on the 5m incl. tail bars; diamonds + K5 on every frame`, () => {
      const r = tileOf(squeezeCard(), stubCw('squeeze', look));
      const tile = screen.getByTestId(`ggw-tile-${SYM}`);
      expect(within(tile).queryByTestId('ggw-stack-charts')).toBeNull();
      expect(within(tile).queryByTestId('ggw-stretch-charts')).toBeNull();
      const charts = tile.querySelector('.ggw-charts')!;
      expect(charts.className).toBe('ggw-dark ggw-charts');
      expect(charts.querySelector(':scope > .ggw-frame')!.getAttribute('data-tf')).toBe('1m');
      const pair = charts.querySelector(':scope > .ggw-frame-pair')!;
      expect([...pair.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['5m', '15m']);
      /* the squeeze marks: on the 5m only, the served kinds, one whose both stamps are TAIL bars (the tail reached the chart) */
      const g5 = frameEl('5m').querySelector('.pc-gg-ellipses');
      expect(g5).not.toBeNull();
      expect([...g5!.querySelectorAll('[data-ellipse-kind]')].map((e) => e.getAttribute('data-ellipse-kind'))).toEqual(SERVED_KINDS);
      for (const tf of ['1m', '15m']) expect(frameEl(tf).querySelector('.pc-gg-ellipses'), tf).toBeNull();
      /* the served 9/21 cross diamonds + the K5 chip on every frame that serves them */
      const p = squeezeP();
      for (const tf of WATCH_ORDER) {
        const served = p.frames.find((f) => f.tf === tf)!;
        const ups = served.tile.markers.filter((m) => m.kind === 'ema_cross_up').length;
        const dns = served.tile.markers.filter((m) => m.kind === 'ema_cross_dn').length;
        expect(ups + dns, tf).toBeGreaterThan(0);
        expect(frameEl(tf).querySelectorAll('[data-testid="pc-ema-cross-up"]').length, tf).toBe(ups);
        expect(frameEl(tf).querySelectorAll('[data-testid="pc-ema-cross-dn"]').length, tf).toBe(dns);
        expect(frameEl(tf).querySelector('.ggw-cap')!.textContent, tf).toContain(served.uptrend!.short);
      }
      /* the A+ tag on the card's frame only; no ✕ */
      expect([...frameEl('5m').querySelectorAll('text')].some((t) => t.textContent === 'A+')).toBe(true);
      expect(r.container.querySelector('.ggw-remove')).toBeNull();
    });
  }

  it('under fit: the top frame\'s flex-grow == GGW_FIT_GROW.top and the pair\'s == GGW_FIT_GROW.pair', () => {
    tileOf(squeezeCard(), stubCw('squeeze', undefined, { fit: true, rowH: 640 }));
    const charts = screen.getByTestId(`ggw-tile-${SYM}`).querySelector('.ggw-charts')!;
    const top = charts.querySelector(':scope > .ggw-frame') as HTMLElement;
    const pair = charts.querySelector(':scope > .ggw-frame-pair') as HTMLElement;
    expect(top.style.flexGrow).toBe(String(GGW_FIT_GROW.top));
    expect(pair.style.flexGrow).toBe(String(GGW_FIT_GROW.pair));
  });
});

describe('🎾 NEGATIVES — the tile switches on the ROW [C2]', () => {
  it('a bull_flag card with the SAME squeeze payload → stacked 15m / 5m / 1m, no pair, no squeeze marks', () => {
    tileOf(bullCard(), stubCw('squeeze'));
    const tile = screen.getByTestId(`ggw-tile-${SYM}`);
    const stack = within(tile).getByTestId('ggw-stack-charts');
    expect([...stack.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
    expect(tile.querySelector('.ggw-frame-pair')).toBeNull();
    expect(tile.querySelector('.pc-gg-ellipses')).toBeNull();
  });

  for (const look of [undefined, 'video'] as const) {
    it(`(${look ?? 'no look'}) a 🎾 card whose row came from the PLAIN payload (squeeze opt, no echo) → stacked 15m / 5m / 1m, no pair`, () => {
      tileOf(squeezeCard(), stubCw('plain', look));
      const tile = screen.getByTestId(`ggw-tile-${SYM}`);
      const stack = within(tile).getByTestId('ggw-stack-charts');
      expect([...stack.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
      expect(tile.querySelector('.ggw-frame-pair')).toBeNull();
      expect(tile.querySelector('.pc-gg-ellipses')).toBeNull();
    });
  }

  it('the plain-row 🎾 tile is the SAME DOM as the bull-flag card\'s tile on that row (today\'s look exactly)', () => {
    const a = tileOf(squeezeCard(), stubCw('plain'));
    const html = a.container.innerHTML;
    a.unmount();
    const b = tileOf(bullCard(), { ...stubCw(), rowOf: (c: GgTile) => ggcRow(c, plainP(), undefined, { plan: false }) });
    expect(b.container.innerHTML).toBe(html);
  });

  for (const kind of ['loading', 'failed', 'error'] as const) {
    it(`a ${kind} 🎾 row prints exactly what a stacked (bull-flag) card prints`, () => {
      const a = tileOf(squeezeCard(), stubCw(kind));
      const html = a.container.innerHTML;
      a.unmount();
      const b = tileOf(bullCard(), stubCw(kind));
      expect(b.container.innerHTML).toBe(html);
      if (kind === 'failed') expect(screen.getByTestId('ggw-row-text').textContent).toBe(GGC_FETCH_FAILED);
      if (kind === 'error') expect(screen.getByTestId('ggw-row-text').textContent).toBe('served reason words');
      expect(document.querySelectorAll('.ggw-frame')).toHaveLength(0);
    });
  }

  it('source: GgCardGrid.tsx switches on ggcRowSplit( and never on ggcIsSqueeze(; no tags={, still the Watch Tile', async () => {
    const src = await readSource('src/components/GgCardGrid.tsx');
    expect(src).toContain('ggcRowSplit(row)');
    expect(src).not.toContain('ggcIsSqueeze(');
    expect(src).not.toMatch(/\btags=\{/);
    expect(src).toContain("import { Tile } from './GajjalaWatchTile';");
    expect(src).toContain('{...(split ? {} : { stack: true, order: GGC_STRETCH_ORDER })}');
  });
});

/* the 11-18 block, comment-free, exactly as it shipped (gajjala.css) — the new block must never edit it */
const BLOCK_1118 = [
  '@media (min-width: 641px) {',
  '  ',
  '  .ggw-grid.ggw-grid--fit.gg-cardgrid { grid-auto-rows: minmax(var(--ggw-row-h), auto); }',
  '  .gg-cardgrid.ggw-grid--fit > .gg-card--watch > .ggw-tile { flex: 1 1 auto; min-height: 0; overflow: visible; }',
  '  .gg-cardgrid.ggw-grid--fit > .gg-card--watch > :not(.ggw-tile) { flex: none; }',
  '  .gg-cardgrid.ggw-grid--fit .ggw-charts--stack { flex: 1 1 auto; min-height: min-content; }',
  '  .gg-cardgrid.ggw-grid--fit .ggw-charts--stack > .ggw-frame:not([data-empty]) { min-height: var(--ggc-frame-min); }',
  '  ',
  '  .gg-cardgrid.ggw-grid--fit .ggw-charts--stack > .ggw-frame[data-empty] { flex: none; }',
  '  .gg-cardgrid.ggw-grid--fit .ggw-charts--stack > .ggw-frame[data-empty] > .ggw-chartbox { flex: none; min-height: auto; overflow: visible; }',
  '}',
].join('\n');
const NEW_SELECTORS = [
  '.gg-cardgrid.ggw-grid--fit .ggw-charts:not(.ggw-charts--stack)',
  '.gg-cardgrid.ggw-grid--fit .ggw-charts:not(.ggw-charts--stack) > .ggw-frame:not([data-empty])',
  '.gg-cardgrid.ggw-grid--fit .ggw-charts:not(.ggw-charts--stack) > .ggw-frame-pair',
  '.gg-cardgrid.ggw-grid--fit .ggw-charts:not(.ggw-charts--stack) > .ggw-frame[data-empty]',
  '.gg-cardgrid.ggw-grid--fit .ggw-charts:not(.ggw-charts--stack) > .ggw-frame[data-empty] > .ggw-chartbox',
];

describe('🎾 the CSS (source read) — appended after the 11-18 block', () => {
  it('the new selectors sit in ONE new @media (min-width: 641px) block placed after the 11-18 block; each starts .gg-cardgrid.ggw-grid--fit', async () => {
    const code = (await readSource('src/styles/gajjala.css')).replace(/\/\*[\s\S]*?\*\//g, '');
    const at1118 = code.indexOf(BLOCK_1118);
    expect(at1118).toBeGreaterThan(-1);
    const after = code.slice(at1118 + BLOCK_1118.length);
    const m = after.indexOf('@media (min-width: 641px) {');
    expect(m).toBeGreaterThan(-1);
    const block = after.slice(m, after.indexOf('\n}', m) + 2);
    for (const s of NEW_SELECTORS) expect(block, s).toContain(s);
    const rules = block.slice(block.indexOf('{') + 1, block.lastIndexOf('}'));
    const sels = (rules.match(/[^{}]+\{/g) || []).flatMap((x) => x.replace('{', '').split(',').map((y) => y.trim())).filter(Boolean);
    expect(sels.length).toBe(NEW_SELECTORS.length);
    for (const s of sels) expect(s.startsWith('.gg-cardgrid.ggw-grid--fit'), s).toBe(true);
    /* none of the new selectors exists anywhere before the 11-18 block's end */
    for (const s of NEW_SELECTORS) expect(code.slice(0, at1118 + BLOCK_1118.length), s).not.toContain(`${s} {`);
    expect(block).toContain('min-height: var(--ggc-frame-min)');
  });

  it('NEGATIVE: no !important; the Watch sheet carries no .gg-cardgrid; the 11-18 block text unchanged; the pinned first .gg-card rule unchanged', async () => {
    const css = await readSource('src/styles/gajjala.css');
    expect(css).not.toContain('!important');
    expect(await readSource('src/styles/gajjalaWatch.css')).not.toContain('.gg-cardgrid');
    expect(css.replace(/\/\*[\s\S]*?\*\//g, '')).toContain(BLOCK_1118);
    expect(css).toContain('.gg-card { border-radius: 8px; min-width: 0; max-width: 100%; }');
    /* the 11-18 block is still the LAST @media before the fitted-row rule (GgCardGrid.test.tsx's own reader) */
    const code = css.replace(/\/\*[\s\S]*?\*\//g, '');
    const media = code.slice(code.lastIndexOf('@media (min-width: 641px)', code.indexOf('.ggw-grid.ggw-grid--fit.gg-cardgrid')));
    expect(media.startsWith(BLOCK_1118)).toBe(true);
  });

  it('NEGATIVE: every .ggw-frame[data-empty] selector in the sheet is scoped to .gg-cardgrid.ggw-grid--fit (the 11-18 pin holds with the new block)', async () => {
    const code = (await readSource('src/styles/gajjala.css')).replace(/\/\*[\s\S]*?\*\//g, '');
    const sels = code.match(/[^{};]*\.ggw-frame\[data-empty\][^{]*\{/g) || [];
    expect(sels.length).toBe(4);
    for (const s of sels) expect(s).toContain('.gg-cardgrid.ggw-grid--fit');
  });
});
