import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import {
  GGC_FETCH_FAILED, GGC_NO_FRAMES, GGC_STRETCH_ORDER, GGC_WATCH_LABEL, GGC_WATCH_TITLE, ggcRow, parseGgc, type GgcPayload,
} from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';
import { GGW_LAYOUTS, GGW_PAGER, GGW_STRETCH, type GgwRow } from '../lib/gajjalaWatch';
import { YAHOO_LABEL } from '../lib/yahooLink';
import { TV_LABEL } from '../lib/tvChart';
import { SEPA_LINK_LABEL, sepaLinkTestId } from '../lib/cardLinks';
import type { GgCardWatch } from '../hooks/useGgCardWatch';

/* 👀 GgCardGrid — the card grid in the Watch layout (2026-11-18, spec cardview §3.5 / §4 WP-B). Ajay 2026-11-18: "I need
 * the watch list kinda chart formant view video view as default here too from the tabs pages".
 *
 * The three pieces on their own: the REAL Watch Tile / Frame / PatternChart, the REAL pager + pick (GajjalaWatchLayout), a
 * hand-built `cw` (the hook is tested in hooks/useGgCardWatch.test.tsx). Frames = CLONES of the 2026-11-15 Watch fixture's
 * OMH frames relabelled 15m / 5m / 1m; fixtures are never edited. NEGATIVES: not active → exactly today's .cm-grid and
 * nothing else (an empty list with the mode ON included [C7]); no pick on the phone; no × in the pager; no ✕ / ⤡ on a tile;
 * no band / ➖ diamonds under 📺; no FE-typed sentence; the fitted-row CSS wins by specificity [C4]. */

vi.mock('./GgWatchButton', () => ({ GgWatchButton: ({ symbol }: any) => <span data-testid={`ggwatch-${symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./PromoOriginChip', () => ({ PromoOriginChip: () => <span /> }));
vi.mock('./SignalWatchButton', () => ({ SignalWatchButton: () => <span /> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));

import { GgCardGridFrame, GgCardTile, GgCardWatchToggle } from './GgCardGrid';
import { PatternChart } from './PatternChart';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const LABEL: Record<string, string> = { '15m': '15-min', '5m': '5-min', '1m': '1-min' };
function frame(sym: string, tf: string) {
  const f = clone((watchFixture as any).rows[0].frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.label = LABEL[tf];
  f.tile.symbol = sym;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  return f;
}
function rawPayload(sym: string, mut: (p: any) => void = () => {}) {
  const p: any = {
    state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
    text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
  };
  mut(p);
  return p;
}
const planCard = (sym: string): GgTile => ({
  symbol: sym, name: null, href: `/sepa/${sym}?tab=supply&tf=5m_today`, bars: [{ t: '2026-11-13 10:30', o: 1, h: 1, l: 1, c: 1, v: 1 }],
  stats: [], why: '', tf: '5m', gajjala: { plan_text: 'served plan: Entry above 4.10 · stop 3.80' },
  lines: [{ label: 'TRIGGER 4.15', price: 4.15, tone: 'buy' }, { label: 'STOP 3.95', price: 3.95, tone: 'stop' }],
  bands: [{ kind: 'gg_entry', lo: 4.0, hi: 4.05, label: '🧪 entry' }],
  markers: [
    { date: '2026-11-13 04:10', kind: 'ema_cross_up', label: 'served cross up' },
    { date: '2026-11-13 05:50', kind: 'ema_cross_dn', label: 'served cross dn' },
    { date: '2026-11-13 07:30', kind: 'buy', label: 'A+' },
  ],
} as unknown as GgTile);

type RowKind = 'ok' | 'text' | 'failed' | 'error' | 'loading';
function stubCw(over: Partial<GgCardWatch> = {}, rowKind: RowKind = 'ok', look?: 'video'): GgCardWatch {
  const rowOf = (card: GgTile): GgwRow => {
    if (rowKind === 'ok') return ggcRow(card, parseGgc(rawPayload(card.symbol)) as GgcPayload, look, { plan: false });
    if (rowKind === 'text') {
      return ggcRow(card, parseGgc(rawPayload(card.symbol, (p) => {
        p.text = 'served words: no bars stored for this name this session yet';
        for (const f of p.frames) { f.tile.bars = []; f.tile.curves = []; f.axis = null; f.empty_text = `served empty ${f.tf}`; }
      })) as GgcPayload, look, { plan: false });
    }
    if (rowKind === 'failed') return { symbol: card.symbol, state: 'error', text: GGC_FETCH_FAILED, ...GGC_NO_FRAMES };
    if (rowKind === 'error') return { symbol: card.symbol, state: 'error', text: 'served reason words', ...GGC_NO_FRAMES };
    return { symbol: card.symbol, state: 'loading', text: null, ...GGC_NO_FRAMES };
  };
  return {
    on: true, allowed: true, toggle: () => {}, active: true, phone: false, layout: 2, setLayout: vi.fn(),
    page: 0, pages: 2, paged: true, goPage: vi.fn(), pick: null, usePick: false, togglePick: vi.fn(),
    shown: (s: string) => s === 'AAA' || s === 'BBB', rowOf, liveOf: () => undefined,
    grid: GGW_LAYOUTS[2], fit: false, rowH: null,
    boardRef: { current: null }, headRef: { current: null }, gridRef: { current: null },
    ...over,
  };
}
const SYMS = ['AAA', 'BBB', 'CCC'];
const frameOf = (cw: GgCardWatch, loading = false, symbols = SYMS) => render(
  <MemoryRouter>
    <GgCardGridFrame cw={cw} loading={loading} symbols={symbols}><div className="gg-card" data-testid="child" /></GgCardGridFrame>
  </MemoryRouter>);
const ROUTE = '/chart-maps?tab=gajjala&sub=bull_flag';
const tileOf = (card: GgTile, cw: GgCardWatch, onStretch: (s: string) => void = () => {}) => render(
  <MemoryRouter initialEntries={[ROUTE]}><GgCardTile card={card} cw={cw} onStretch={onStretch} /></MemoryRouter>);

afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('👀 GgCardWatchToggle', () => {
  it('the label + title words, aria-pressed and the click', () => {
    const fn = vi.fn();
    const r = render(<GgCardWatchToggle on onToggle={fn} />);
    const b = screen.getByTestId('gg-card-watch');
    expect(b.textContent).toBe(GGC_WATCH_LABEL);
    expect(b.getAttribute('title')).toBe(GGC_WATCH_TITLE);
    expect(b.getAttribute('aria-pressed')).toBe('true');
    expect(b.className).toBe('cm-phase-btn gg-cardwatch-btn cm-phase-on');
    fireEvent.click(b);
    expect(fn).toHaveBeenCalledTimes(1);
    r.rerender(<GgCardWatchToggle on={false} onToggle={fn} />);
    expect(screen.getByTestId('gg-card-watch').getAttribute('aria-pressed')).toBe('false');
    expect(screen.getByTestId('gg-card-watch').className).toBe('cm-phase-btn gg-cardwatch-btn');
  });
});

describe('👀 GgCardGridFrame', () => {
  it('NEGATIVE: not active → EXACTLY today\'s div.cm-grid (stale + aria-busy as today) and nothing else', () => {
    const r = frameOf(stubCw({ active: false, on: false }), true);
    const g = r.container.firstElementChild as HTMLElement;
    expect(g.outerHTML).toBe('<div class="cm-grid cm-grid-stale" aria-busy="true"><div class="gg-card" data-testid="child"></div></div>');
    r.unmount();
    const r2 = frameOf(stubCw({ active: false, on: false }), false);
    expect((r2.container.firstElementChild as HTMLElement).outerHTML)
      .toBe('<div class="cm-grid"><div class="gg-card" data-testid="child"></div></div>');
    expect(r2.container.querySelector('[class*="ggw-"]')).toBeNull();
  });

  it('[C7] NEGATIVE: on true but active false (an empty list) → div.cm-grid only, no shell, no pick, no pager', () => {
    const r = frameOf(stubCw({ on: true, active: false }), false, []);
    expect(r.container.querySelector('.cm-grid')).not.toBeNull();
    expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
    expect(screen.queryByTestId('ggc-layout')).toBeNull();
    expect(screen.queryByTestId('ggc-pager')).toBeNull();
  });

  it('active → .ggw-board.gg-cardwatch > head (the pick) + pager (ggc-pager-*, NO ×) + the Watch grid with the frame floor', () => {
    const cw = stubCw();
    const r = frameOf(cw);
    const shell = screen.getByTestId('gg-cardwatch');
    expect(shell.className).toBe('ggw-board gg-cardwatch');
    expect(shell.querySelector('.ggw-head.gg-cardwatch-head [data-testid="ggc-layout"]')).not.toBeNull();
    for (const l of [1, 2, 4, 9]) expect(screen.getByTestId(`ggc-layout-${l}`)).toBeTruthy();
    expect(within(shell).getByText('per screen')).toBeTruthy();
    expect(screen.getByTestId('ggc-pager')).toBeTruthy();
    for (const s of SYMS) expect(screen.getByTestId(`ggc-pager-${s}`)).toBeTruthy();
    expect(r.container.querySelector('[data-testid^="ggc-pager-x-"]')).toBeNull();
    expect(r.container.querySelector('[data-testid^="ggw-pager"]')).toBeNull();
    expect(screen.getByTestId('ggc-pager-at').textContent).toBe('1 / 2');
    expect(screen.getByTestId('ggc-pager-AAA').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('ggc-pager-CCC').getAttribute('aria-pressed')).toBe('false');
    const grid = screen.getByTestId('gg-cardgrid');
    expect(grid.className).toBe('ggw-grid ggw-grid--cols2 gg-cardgrid');
    expect(grid.style.getPropertyValue('--ggc-frame-min')).toBe('160px');
    expect(grid.style.getPropertyValue('--ggw-row-h')).toBe('');
    expect(grid.getAttribute('data-layout')).toBe('2');
    expect(within(grid).getByTestId('child')).toBeTruthy();
    expect(r.container.querySelector('.cm-grid')).toBeNull();
    fireEvent.click(screen.getByTestId('ggc-pager-next'));
    expect(cw.goPage).toHaveBeenCalledWith(1);
    fireEvent.click(screen.getByTestId('ggc-pager-CCC'));
    expect(cw.togglePick).toHaveBeenCalledWith('CCC');
    fireEvent.click(screen.getByTestId('ggc-layout-4'));
    expect(cw.setLayout).toHaveBeenCalledWith(4);
  });

  it('fitted → ggw-grid--fit + --ggw-row-h; loading → cm-grid-stale + aria-busy on the Watch grid', () => {
    frameOf(stubCw({ fit: true, rowH: 640 }), true);
    const grid = screen.getByTestId('gg-cardgrid');
    expect(grid.className).toBe('ggw-grid ggw-grid--cols2 gg-cardgrid ggw-grid--fit cm-grid-stale');
    expect(grid.style.getPropertyValue('--ggw-row-h')).toBe('640px');
    expect(grid.getAttribute('aria-busy')).toBe('true');
  });

  it('NEGATIVE: the phone → no pick (the pager stays); one name → no pager', () => {
    const r = frameOf(stubCw({ phone: true }));
    expect(screen.queryByTestId('ggc-layout')).toBeNull();
    expect(screen.getByTestId('ggc-pager')).toBeTruthy();
    r.unmount();
    frameOf(stubCw(), false, ['AAA']);
    expect(screen.getByTestId('ggc-layout')).toBeTruthy();
    expect(screen.queryByTestId('ggc-pager')).toBeNull();
  });
});

describe('👀 GgCardTile', () => {
  it('an ok row → the Watch Tile, stacked 15m / 5m / 1m, SEPA page link + ➕ Watch in the head, ⤢ → onStretch; no ✕, no ⤡', () => {
    const fn = vi.fn();
    const r = tileOf(planCard('PFAI'), stubCw(), fn);
    const tile = screen.getByTestId('ggw-tile-PFAI');
    const stack = within(tile).getByTestId('ggw-stack-charts');
    expect([...stack.querySelectorAll('.ggw-frame')].map((f) => f.getAttribute('data-tf'))).toEqual(['15m', '5m', '1m']);
    expect(stack.querySelectorAll('svg').length).toBeGreaterThanOrEqual(3);
    const link = within(tile).getByTestId(sepaLinkTestId('PFAI'));
    expect(link.textContent).toBe(SEPA_LINK_LABEL);
    expect(link.previousElementSibling?.className).toBe('ggw-sym');
    expect(within(tile).getByTestId('ggwatch-PFAI')).toBeTruthy();
    fireEvent.click(within(tile).getByTestId('ggw-stretch-btn-PFAI'));
    expect(fn).toHaveBeenCalledWith('PFAI');
    expect(r.container.querySelector('.ggw-remove')).toBeNull();
    expect(r.container.querySelector('.ggw-unstretch')).toBeNull();
    expect(r.container.querySelector('[data-testid="ggw-stretch-prev"]')).toBeNull();
    /* the plan prints ONCE (the card's own CardExtras, below the tile) — never in the tile head */
    expect(within(tile).queryByTestId('ggw-row-text')).toBeNull();
  });

  it('the SEPA link href + state equal the old card\'s PatternChart SEPA link for the same tile and location', () => {
    const t = clone((hand as any).boards.bull_flag.tiles[0]) as GgTile;
    const a = render(<MemoryRouter initialEntries={[ROUTE]}><PatternChart tile={t} onOpenView={() => {}} /></MemoryRouter>);
    const oldHref = a.getByTestId(sepaLinkTestId(t.symbol)).getAttribute('href');
    a.unmount();
    tileOf(t, stubCw());
    const newHref = screen.getByTestId(sepaLinkTestId(t.symbol)).getAttribute('href');
    expect(oldHref).toBeTruthy();
    expect(newHref).toBe(oldHref);
  });

  it('NEGATIVE: a card with no usable href → no SEPA link (the ➕ Watch stays)', () => {
    tileOf({ ...planCard('PFAI'), href: 'https://evil.example/x' } as GgTile, stubCw());
    expect(screen.queryByTestId(sepaLinkTestId('PFAI'))).toBeNull();
    expect(screen.getByTestId('ggwatch-PFAI')).toBeTruthy();
  });

  it('a served `text` (no bars) → the words in the head and the three served empty frames, NO svg, never blank', () => {
    tileOf(planCard('PFAI'), stubCw({}, 'text'));
    const tile = screen.getByTestId('ggw-tile-PFAI');
    expect(within(tile).getByTestId('ggw-row-text').textContent).toBe('served words: no bars stored for this name this session yet');
    for (const tf of GGC_STRETCH_ORDER) {
      expect(within(tile).getByTestId(`ggw-frame-empty-PFAI-${tf}`).textContent).toBe(`served empty ${tf}`);
    }
    expect(tile.querySelectorAll('svg')).toHaveLength(0);
  });

  it('a failed load → GGC_FETCH_FAILED; a served error → its reason; loading → no words, no frames', () => {
    const r = tileOf(planCard('PFAI'), stubCw({}, 'failed'));
    expect(screen.getByTestId('ggw-row-text').textContent).toBe(GGC_FETCH_FAILED);
    r.unmount();
    const r2 = tileOf(planCard('PFAI'), stubCw({}, 'error'));
    expect(screen.getByTestId('ggw-row-text').textContent).toBe('served reason words');
    r2.unmount();
    tileOf(planCard('PFAI'), stubCw({}, 'loading'));
    expect(screen.queryByTestId('ggw-row-text')).toBeNull();
    expect(document.querySelectorAll('.ggw-frame')).toHaveLength(0);
  });

  it('📺 look → no band and no ➖ diamonds in any frame; bold EMAs + the A+ tag stay', () => {
    tileOf(planCard('PFAI'), stubCw({}, 'ok', 'video'));
    for (const tf of GGC_STRETCH_ORDER) {
      const el = screen.getByTestId(`ggw-frame-PFAI-${tf}`);
      expect(el.querySelectorAll('[data-band-kind]'), tf).toHaveLength(0);
      expect(el.querySelectorAll('.pc-ema-cross'), tf).toHaveLength(0);
      expect(el.querySelector('.pc-ema-bold'), tf).not.toBeNull();
    }
    expect([...screen.getByTestId('ggw-frame-PFAI-5m').querySelectorAll('text')].some((t) => t.textContent === 'A+')).toBe(true);
  });

  it('NEGATIVE: no look → the 🧪 band draws on every frame', () => {
    tileOf(planCard('PFAI'), stubCw());
    for (const tf of GGC_STRETCH_ORDER) {
      expect(screen.getByTestId(`ggw-frame-PFAI-${tf}`).querySelectorAll('[data-band-kind="gg_entry"]').length, tf).toBeGreaterThan(0);
    }
  });

  it('NEGATIVE: the tile types no new sentence — its visible text (outside the svgs) is served or a control word; no b-word', () => {
    const card = planCard('PFAI');
    const p = rawPayload('PFAI');
    tileOf(card, stubCw());
    const served = new Set<string>();
    const walk = (x: unknown) => {
      if (typeof x === 'string') served.add(x);
      else if (Array.isArray(x)) x.forEach(walk);
      else if (x && typeof x === 'object') Object.values(x).forEach(walk);
    };
    walk(p);
    walk(card);
    // WIDENED 2026-11-23 (+ TV_LABEL) — Ajay: "Also add traderview charts on charts please.." (question card: "TV ↗ button
    // only"): the TV ↗ link-out label is a control word like Yahoo ↗.
    const control = new Set<string>([GGC_WATCH_LABEL, 'per screen', ...Object.values(GGW_PAGER), ...Object.values(GGW_STRETCH),
      TV_LABEL, YAHOO_LABEL, SEPA_LINK_LABEL, '⚠️ ', '·', 'PFAI']);
    const tile = screen.getByTestId('ggw-tile-PFAI');
    const tw = document.createTreeWalker(tile, NodeFilter.SHOW_TEXT);
    const bad: string[] = [];
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      const s = (n.textContent || '').trim();
      if (!s || (n.parentElement && n.parentElement.closest('svg'))) continue;
      /* a caption joins served parts with the structural ' · ' (the Watch's Frame) — each part must be served */
      for (const part of s.split(' · ').map((x) => x.trim()).filter(Boolean)) {
        if (!served.has(part) && !control.has(part) && ![...served].some((v) => v.includes(part))) bad.push(part);
      }
    }
    expect(bad).toEqual([]);
    expect(tile.textContent || '').not.toMatch(/bounce/i);
  });
});

describe('👀 the fitted-row CSS [C4] — wins by specificity, never by sheet order', () => {
  it('the minmax rule\'s selector is .ggw-grid.ggw-grid--fit.gg-cardgrid (≥ 3 class tokens), after the pinned .gg-card rules', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const code = css.replace(/\/\*[\s\S]*?\*\//g, '');
    const m = code.match(/([^{};]+)\{\s*grid-auto-rows:\s*minmax\(var\(--ggw-row-h\)[^}]*\}/);
    expect(m).not.toBeNull();
    const sel = m![1].trim();
    expect(sel).toBe('.ggw-grid.ggw-grid--fit.gg-cardgrid');
    expect((sel.match(/\.[a-z][\w-]*/g) || []).length).toBeGreaterThanOrEqual(3);
    expect(css.indexOf('.ggw-grid.ggw-grid--fit.gg-cardgrid')).toBeGreaterThan(css.indexOf('.gg-card.gg-wide {'));
    /* the pinned first .gg-card rule is untouched (the 📱 phone contract) */
    expect(css).toContain('.gg-card { border-radius: 8px; min-width: 0; max-width: 100%; }');
    expect(css).toContain('.gg-card.gg-card--watch[hidden], .gg-cardgrid > .gg-focus-divider[hidden] { display: none; }');
  });

  it('an EMPTY frame in a fitted tile sizes to its words — frame AND chartbox get flex none (never 0 px, never clipped)', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const code = css.replace(/\/\*[\s\S]*?\*\//g, '');
    const media = code.slice(code.lastIndexOf('@media (min-width: 641px)', code.indexOf('.ggw-grid.ggw-grid--fit.gg-cardgrid')));
    expect(code).toContain('.gg-cardgrid.ggw-grid--fit .ggw-charts--stack > .ggw-frame[data-empty] { flex: none; }');
    expect(code).toContain('.gg-cardgrid.ggw-grid--fit .ggw-charts--stack > .ggw-frame[data-empty] > .ggw-chartbox { flex: none; min-height: auto; overflow: visible; }');
    /* both rules sit in the same desktop @media block as the fitted-row rule (the phone layout is untouched) */
    const block = media.slice(0, media.indexOf('\n}'));
    expect(block).toContain('.ggw-frame[data-empty] { flex: none; }');
    expect(block).toContain('.ggw-frame[data-empty] > .ggw-chartbox { flex: none;');
    expect(block).toContain('.ggw-grid.ggw-grid--fit.gg-cardgrid');
  });

  it('NEGATIVE: the empty-frame fix is scoped to .gg-cardgrid — no bare .ggw-frame[data-empty] rule and the Watch sheet is untouched', async () => {
    const code = (await readSource('src/styles/gajjala.css')).replace(/\/\*[\s\S]*?\*\//g, '');
    const sels = code.match(/[^{};]*\.ggw-frame\[data-empty\][^{]*\{/g) || [];
    expect(sels.length).toBeGreaterThanOrEqual(2);
    for (const s of sels) expect(s).toContain('.gg-cardgrid.ggw-grid--fit');
    const w = await readSource('src/styles/gajjalaWatch.css');
    expect(w).not.toContain('.gg-cardgrid');
  });

  it('NEGATIVE: the Watch\'s own fit rule is unchanged in gajjalaWatch.css', async () => {
    const w = await readSource('src/styles/gajjalaWatch.css');
    expect(w).toContain('.ggw-grid.ggw-grid--fit { grid-auto-rows: var(--ggw-row-h); }');
  });

  it('NEGATIVE: GgCardGrid.tsx draws through the Watch\'s Tile / pager / pick — declares none of them, no EventSource', async () => {
    const src = await readSource('src/components/GgCardGrid.tsx');
    expect(src).toMatch(/import \{ Tile \} from '\.\/GajjalaWatchTile'/);
    expect(src).toMatch(/import \{ GgwLayoutPick, GgwPager \} from '\.\/GajjalaWatchLayout'/);
    expect(src).not.toMatch(/function (Frame|Tile|GgwStretch|GgwPager|GgwLayoutPick)\b/);
    expect(src).not.toContain('new EventSource(');
    expect(src).not.toContain('04:00');
    expect(src).not.toMatch(/bounce/i);
  });
});
