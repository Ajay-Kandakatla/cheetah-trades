import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import gg1Golden from './__fixtures__/gajjala_1m_board_2026_10_27.json';
import {
  GG_LOOK_DEFAULT_ON, GG_LOOK_LS, GG_LOOK_VIDEO_LABEL, GG_LOOK_VIDEO_TITLE, GG_VIDEO_LOOK_VKEYS, loadGgLook, saveGgLook,
} from '../lib/gajjala';
import { VIDEO_LOOK_H } from '../lib/videoLook';
import { ggcPath } from '../lib/gajjalaCardView';
import { openViewTestId, sepaLinkTestId } from '../lib/cardLinks';

/* 📺 Video view on the 🚩 Gajjala cards — the board toggle + the served clock axis (2026-11-17, spec ggvideo WP-C).
 *
 * Ajay 2026-11-16: "Also the graphs in the videos are so clear like I can easily identify the trend" · "Why aren't our
 * regular ones like that". 2026-11-17: "Yes to all defaults" → 📺 ON by default, a toggle turns it off, remembered per
 * device; the served clock axis on every 🚩 5-min and 🧪 card, 📺 on or off; the 1-minute page NOT now; 🎾 cards keep 190.
 *
 * The REAL board and the REAL PatternChart (only the network chips are mocked). Boards are CLONES of the frozen 2026-10-13
 * hand fixture (5-min bars 08:00 → 10:25 ET, 30 per card); a served axis is added by hand in the payload builder — the
 * fixtures are never edited. jsdom has no usable localStorage → every test stubs one (the kiss_rvol precedent). Display
 * only, UNMEASURED: nothing here sorts, gates, rings or GETs on the look. */

vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

const HAND: Record<string, any> = (hand as any).boards;
const GG1: Record<string, any> = (gg1Golden as any).boards;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const VIEW_W = 620;
const BASE_H = 190;

/** The served axis for a hand tile: 04:00 → 16:00 on 5-min slots (144); the 08:00 bar closes 08:05 → slot 48, then one slot
 *  per bar — a mid-morning card, so the last candle sits well left of the right edge. Hand-built: the FE never computes one. */
function axisFor(n: number) {
  return {
    from_et: '04:00', to_et: '16:00', slots: 144, x: Array.from({ length: n }, (_, i) => 48 + i),
    shade: [{ from_slot: 0, to_slot: 66, kind: 'pre' }],
    ticks: [{ slot: 0, label: '4a' }, { slot: 66, label: '9:30' }, { slot: 143, label: '16' }],
    start_epoch: 0, frame_min: 5,
  };
}

type Opts = { sub?: string; axis?: boolean; tab?: string };
/** The 🚩 bull_flag board: PFAI carries the served axis (opts.axis), the other three cards none (an older API's shape). */
function gg5Board(opts: Opts = {}): any {
  const b = clone(HAND[opts.sub || 'bull_flag']);
  b.session = { ...b.session, refresh_sec: 0 };
  if (opts.tab) b.tab = opts.tab;
  if (opts.axis !== false) b.tiles[0].axis = axisFor(b.tiles[0].bars.length);
  return b;
}
/** The 🎾 sub: a 🚩 card WITH an axis, the 🎾 FCHL card WITHOUT one (its stored prior tail — two dates → no key served). */
function squeezeBoard(): any {
  const b = clone(HAND.reversal_squeeze);
  b.session = { ...b.session, refresh_sec: 0 };
  const bf = clone(HAND.bull_flag.tiles[0]);
  bf.axis = axisFor(bf.bars.length);
  b.tiles = [bf, clone(HAND.reversal_squeeze.tiles[0])];
  return b;
}
function gg1Board(): any {
  const b = clone(GG1.bull_flag);
  b.session = { ...(b.session || {}), refresh_sec: 0 };
  return b;
}

type Call = { method: string; url: string };
let calls: Call[] = [];
function stub(boards: { gg5?: () => any; gg1?: () => any; gga?: () => any } = {}) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    calls.push({ method: String(init?.method || 'GET').toUpperCase(), url: String(url) });
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.includes('/frames/')) return ok({});
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/chart-maps/gajjala-1m')) return ok((boards.gg1 || gg1Board)());
    if (u.pathname.endsWith('/chart-maps/gajjala-audited')) {
      return ok((boards.gga || (() => gg5Board({ tab: 'gajjala_audited' })))());
    }
    if (u.pathname.endsWith('/chart-maps/gajjala')) return ok((boards.gg5 || gg5Board)());
    return ok({});
  }));
}

type V = 'gajjala' | 'gajjala_1m' | 'gajjala_audited';
async function mount(variant: V = 'gajjala', sub = 'bull_flag') {
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=${variant}&sub=${sub}`]}>
      <GajjalaBoard variant={variant} />
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  await waitFor(() => expect(r.container.querySelector('.cm-grid .gg-card svg.cm-svg')).not.toBeNull());
  return r;
}

/** A recording in-memory store: every key read or written is kept in `touched`. */
function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries({ 'gg-card-watch': '0', ...seed }));   // 👀 2026-11-18: the small-card grid
  const touched = new Set<string>();
  return {
    touched,
    getItem: (k: string) => { touched.add(k); return m.has(k) ? m.get(k)! : null; },
    setItem: (k: string, v: string) => { touched.add(k); m.set(k, String(v)); },
    removeItem: (k: string) => { touched.add(k); m.delete(k); },
    clear: () => m.clear(),
    peek: (k: string) => (m.has(k) ? m.get(k)! : null),
  };
}
const blocked = () => ({
  getItem: (k: string) => { if (k === 'gg-card-watch') return '0'; throw new Error('blocked'); },   // 👀 2026-11-18: small cards
  setItem: () => { throw new Error('blocked'); },
  removeItem: () => { throw new Error('blocked'); },
  clear: () => undefined,
});

const svgOf = (sym: string) => screen.getByTestId(`gg-tile-${sym}`).querySelector('svg.cm-svg') as SVGSVGElement;
const vbH = (svg: Element) => Number((svg.getAttribute('viewBox') || '').split(/\s+/)[3]);
/** The candle wicks (vertical, coloured up / down, 0.9 wide — the A+ tag's stem is 1.2) — their x is the bar's x on the axis. */
const candleXs = (svg: Element) => [...svg.querySelectorAll('line')]
  .filter((l) => /--(positive|negative)/.test(l.getAttribute('stroke') || '') && l.getAttribute('stroke-width') === '0.9'
    && l.getAttribute('x1') === l.getAttribute('x2') && l.getAttribute('y1') !== l.getAttribute('y2'))
  .map((l) => Number(l.getAttribute('x1')));
const button = () => screen.queryByTestId('gg-look-video');
const board = (c: HTMLElement) => c.querySelector('.gg-board') as HTMLElement;
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));

function expectOneSlotPerBar(svg: Element, n: number) {
  const xs = candleXs(svg);
  expect(xs).toHaveLength(n);
  const d = xs.slice(1).map((x, i) => x - xs[i]);
  for (const s of d) expect(Math.abs(s - d[0])).toBeLessThan(1e-6);
  expect(xs[0]).toBeLessThan(0.1 * VIEW_W);
  expect(xs[n - 1]).toBeGreaterThan(0.7 * VIEW_W);
}
function expectServedAxis(svg: Element, n: number) {
  const xs = candleXs(svg);
  expect(xs).toHaveLength(n);
  /* slot 48..77 of 144: the first candle sits a third in (04:00 is the left edge), the last well left of the right edge */
  expect(xs[0]).toBeGreaterThan(0.25 * VIEW_W);
  expect(xs[n - 1]).toBeLessThan(0.6 * VIEW_W);
}

let store: ReturnType<typeof mem>;
beforeEach(() => { store = mem(); vi.stubGlobal('localStorage', store); });
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('📺 lib — loadGgLook / saveGgLook / the words', () => {
  it('absent → ON (the default); "1" → ON; "0" → OFF', () => {
    expect(GG_LOOK_DEFAULT_ON).toBe(true);
    expect(loadGgLook()).toBe(true);
    store.setItem(GG_LOOK_LS, '1');
    expect(loadGgLook()).toBe(true);
    store.setItem(GG_LOOK_LS, '0');
    expect(loadGgLook()).toBe(false);
  });

  it('NEGATIVE: any stored value that is not "1" reads OFF, never ON (strict)', () => {
    for (const v of ['candles', 'true', 'on', '', ' 1', '1 ', 'video']) {
      store.setItem(GG_LOOK_LS, v);
      expect(loadGgLook()).toBe(false);
    }
  });

  it('saveGgLook writes "1" / "0" under gg-video-look', () => {
    saveGgLook(false);
    expect(store.peek(GG_LOOK_LS)).toBe('0');
    saveGgLook(true);
    expect(store.peek(GG_LOOK_LS)).toBe('1');
  });

  it('NEGATIVE: load and save touch ONLY the gg-video-look key', () => {
    loadGgLook();
    saveGgLook(true);
    saveGgLook(false);
    loadGgLook();
    expect(GG_LOOK_LS).toBe('gg-video-look');
    expect([...store.touched]).toEqual(['gg-video-look']);
  });

  it('NEGATIVE: a blocked store reads ON and a save never throws; no localStorage at all reads ON', () => {
    vi.stubGlobal('localStorage', blocked());
    expect(() => loadGgLook()).not.toThrow();
    expect(loadGgLook()).toBe(true);
    expect(() => saveGgLook(false)).not.toThrow();
    vi.stubGlobal('localStorage', undefined);
    expect(loadGgLook()).toBe(true);
    expect(() => saveGgLook(true)).not.toThrow();
  });

  it('offered on the 🚩 5-min tab and 🧪 Audited only; the title says "4 AM" and names the 🎾 exception', () => {
    expect([...GG_VIDEO_LOOK_VKEYS]).toEqual(['gajjala', 'gajjala_audited']);
    expect(GG_VIDEO_LOOK_VKEYS).not.toContain('gajjala_1m');
    expect(GG_LOOK_VIDEO_LABEL).toBe('📺 Video view');
    expect(GG_LOOK_VIDEO_TITLE).toContain('4 AM');
    expect(GG_LOOK_VIDEO_TITLE).toContain('Reversal Squeeze');
    expect(GG_LOOK_VIDEO_TITLE).not.toContain('04:00');
    for (const w of ['edge', 'bounce', 'better entr']) expect(GG_LOOK_VIDEO_TITLE.toLowerCase()).not.toContain(w);
  });
});

describe('📺 ON by default on the 🚩 5-min and 🧪 Audited boards', () => {
  for (const variant of ['gajjala', 'gajjala_audited'] as const) {
    it(`${variant}: the toggle reads pressed; every card draws the video look at ${VIDEO_LOOK_H}`, async () => {
      stub();
      const { container, unmount } = await mount(variant);
      const b = button()!;
      expect(b).not.toBeNull();
      expect(b.getAttribute('aria-pressed')).toBe('true');
      expect(b.textContent).toBe(GG_LOOK_VIDEO_LABEL);
      expect(b.getAttribute('title')).toBe(GG_LOOK_VIDEO_TITLE);
      expect(b.className).toContain('cm-phase-on');
      expect(board(container).getAttribute('data-look')).toBe('video');
      for (const sym of ['PFAI', 'BKYI', 'TCRT', 'SCNI']) {
        const svg = svgOf(sym);
        expect(svg.getAttribute('data-look')).toBe('video');
        expect(svg.getAttribute('class')).toContain('pc-look-video');
        expect(svg.querySelector('.pc-ema-bold')).not.toBeNull();
        expect(vbH(svg)).toBe(VIDEO_LOOK_H);
      }
      unmount();
    });
  }

  it('the served axis draws PFAI on the clock (04:00 at the left, room on the right); a card without one keeps one slot per bar', async () => {
    stub();
    const { unmount } = await mount('gajjala');
    expectServedAxis(svgOf('PFAI'), 30);
    expectOneSlotPerBar(svgOf('BKYI'), 30);
    unmount();
  });

  it('📺 OFF keeps the served axis (his call #2: the axis on every card, 📺 on or off)', async () => {
    store.setItem(GG_LOOK_LS, '0');
    stub();
    const { unmount } = await mount('gajjala');
    expectServedAxis(svgOf('PFAI'), 30);
    expectOneSlotPerBar(svgOf('BKYI'), 30);
    unmount();
  });
});

describe('📺 the toggle — click, remembered, strict', () => {
  it('a click turns it OFF: unpressed, no data-look, no bold EMAs, height 190, "0" stored; a second click back ON, "1"', async () => {
    stub();
    const { container, unmount } = await mount('gajjala');
    fireEvent.click(button()!);
    expect(button()!.getAttribute('aria-pressed')).toBe('false');
    expect(button()!.className).not.toContain('cm-phase-on');
    expect(board(container).hasAttribute('data-look')).toBe(false);
    const svg = svgOf('PFAI');
    expect(svg.hasAttribute('data-look')).toBe(false);
    expect(container.querySelector('.pc-ema-bold')).toBeNull();
    expect(vbH(svg)).toBe(BASE_H);
    expect(store.peek(GG_LOOK_LS)).toBe('0');
    fireEvent.click(button()!);
    expect(button()!.getAttribute('aria-pressed')).toBe('true');
    expect(vbH(svgOf('PFAI'))).toBe(VIDEO_LOOK_H);
    expect(store.peek(GG_LOOK_LS)).toBe('1');
    unmount();
  });

  it('a stored "0" mounts OFF; a stored "1" mounts ON; absent mounts ON', async () => {
    for (const [seed, on] of [['0', false], ['1', true], [null, true]] as const) {
      store = mem(seed === null ? {} : { [GG_LOOK_LS]: seed });
      vi.stubGlobal('localStorage', store);
      stub();
      const { container, unmount } = await mount('gajjala');
      expect(button()!.getAttribute('aria-pressed')).toBe(String(on));
      expect(vbH(svgOf('PFAI'))).toBe(on ? VIDEO_LOOK_H : BASE_H);
      expect(container.querySelector('.pc-ema-bold') != null).toBe(on);
      unmount();
    }
  });

  it('NEGATIVE: a stored "candles" mounts OFF, never ON', async () => {
    store = mem({ [GG_LOOK_LS]: 'candles' });
    vi.stubGlobal('localStorage', store);
    stub();
    const { container, unmount } = await mount('gajjala');
    expect(button()!.getAttribute('aria-pressed')).toBe('false');
    expect(board(container).hasAttribute('data-look')).toBe(false);
    expect(vbH(svgOf('PFAI'))).toBe(BASE_H);
    unmount();
  });

  it('NEGATIVE: the board reads and writes no other key for the look (only gg-video-look is written on a toggle)', async () => {
    stub();
    const { unmount } = await mount('gajjala');
    const before = new Set(store.touched);
    store.touched.clear();
    fireEvent.click(button()!);
    expect([...store.touched]).toEqual([GG_LOOK_LS]);
    expect(before.has(GG_LOOK_LS)).toBe(true);
    unmount();
  });

  it('NEGATIVE: a blocked localStorage → ON, and a click still toggles in-session without throwing', async () => {
    vi.stubGlobal('localStorage', blocked());
    stub();
    const { unmount } = await mount('gajjala');
    expect(button()!.getAttribute('aria-pressed')).toBe('true');
    expect(() => fireEvent.click(button()!)).not.toThrow();
    expect(button()!.getAttribute('aria-pressed')).toBe('false');
    expect(vbH(svgOf('PFAI'))).toBe(BASE_H);
    unmount();
  });

  it('NEGATIVE: toggling sends no request — the fetch count and URLs are identical across two clicks; no URL names the look', async () => {
    stub();
    const { unmount } = await mount('gajjala');
    await sleep(30);
    const snap = calls.map((c) => `${c.method} ${c.url}`);
    fireEvent.click(button()!);
    await sleep(30);
    fireEvent.click(button()!);
    await sleep(30);
    expect(calls.map((c) => `${c.method} ${c.url}`)).toEqual(snap);
    for (const c of calls) expect(c.url).not.toMatch(/look|video/i);
    unmount();
  });
});

describe('📺 NEGATIVES — the 1-minute page and the 🎾 card', () => {
  it('not on gajjala_1m: no button, no data-look, height 190, no bold EMAs — even with "1" stored; its tiles carry no axis', async () => {
    store = mem({ [GG_LOOK_LS]: '1' });
    vi.stubGlobal('localStorage', store);
    for (const t of GG1.bull_flag.tiles) expect('axis' in t).toBe(false);
    stub();
    const { container, unmount } = await mount('gajjala_1m');
    expect(button()).toBeNull();
    expect(board(container).hasAttribute('data-look')).toBe(false);
    const svgs = [...container.querySelectorAll('.cm-grid .gg-card svg.cm-svg')];
    expect(svgs.length).toBe(GG1.bull_flag.tiles.length);
    for (const svg of svgs) {
      expect(svg.hasAttribute('data-look')).toBe(false);
      expect(vbH(svg)).toBe(BASE_H);
      expect(svg.querySelector('.pc-ema-bold')).toBeNull();
      expectOneSlotPerBar(svg, candleXs(svg).length);
    }
    unmount();
  });

  it('a 🎾 .gg-wide card keeps 190 under 📺 and draws one slot per bar; the 🚩 card beside it is 283 on its axis', async () => {
    stub({ gg5: squeezeBoard });
    const { unmount } = await mount('gajjala', 'reversal_squeeze');
    const sq = screen.getByTestId('gg-tile-FCHL');
    expect(sq.className).toContain('gg-wide');
    const sqSvg = svgOf('FCHL');
    expect(sqSvg.getAttribute('data-look')).toBe('video');
    expect(vbH(sqSvg)).toBe(BASE_H);
    expectOneSlotPerBar(sqSvg, HAND.reversal_squeeze.tiles[0].bars.length);
    expect(vbH(svgOf('PFAI'))).toBe(VIDEO_LOOK_H);
    expectServedAxis(svgOf('PFAI'), 30);
    unmount();
  });

  it('a board whose tiles carry no axis at all (an older API) draws every card one slot per bar under 📺', async () => {
    stub({ gg5: () => gg5Board({ axis: false }) });
    const { unmount } = await mount('gajjala');
    for (const sym of ['PFAI', 'BKYI', 'TCRT', 'SCNI']) {
      expect(svgOf(sym).getAttribute('data-look')).toBe('video');
      expectOneSlotPerBar(svgOf(sym), 30);
    }
    unmount();
  });
});

describe('📺 the ⤢ view and the SEPA link are untouched', () => {
  it('a card click still opens the ⤢ view (one frames GET) and the "SEPA page" link keeps tile.href, 📺 on and off', async () => {
    stub();
    const { unmount } = await mount('gajjala');
    const onHref = screen.getByTestId(sepaLinkTestId('PFAI')).getAttribute('href');
    expect(onHref).toContain(HAND.bull_flag.tiles[0].href);
    fireEvent.click(screen.getByTestId(openViewTestId('PFAI')));
    await screen.findByTestId('ggw-stretch');
    expect(calls.filter((c) => c.url.includes(ggcPath('PFAI')))).toHaveLength(1);
    unmount();

    store = mem({ [GG_LOOK_LS]: '0' });
    vi.stubGlobal('localStorage', store);
    stub();
    const off = await mount('gajjala');
    expect(screen.getByTestId(sepaLinkTestId('PFAI')).getAttribute('href')).toBe(onHref);
    off.unmount();
  });
});

describe('📺 source guards — phone + contract shape', () => {
  async function readSource(rel: string): Promise<string> {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    return fs.readFileSync(`${root}/${rel}`, 'utf8');
  }

  it('the button sits inside the "(5) bar size" .cm-phase row, carries no nowrap; .gg-card keeps min-width: 0', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const start = src.indexOf('<div className="cm-phase" role="tablist" aria-label="Bar size">');
    expect(start).toBeGreaterThan(0);
    const end = src.indexOf('(5b)', start);
    const row = src.slice(start, end);
    expect(row).toContain('data-testid="gg-look-video"');
    expect(row).toContain('cm-phase-btn gg-look-btn');
    expect(row).not.toMatch(/nowrap/);
    const css = await readSource('src/styles/gajjala.css');
    const m = css.match(/(^|\n)\s*\.gg-card\s*\{([^}]*)\}/);
    expect(m && m[2].trim()).toBe('border-radius: 8px; min-width: 0; max-width: 100%;');
  });

  it('the card passes axis= and look=; GgCardView gets look= AFTER boardSeq; no clock literal in the board', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    expect(src).toContain('axis={t.axis ?? null}');
    expect(src).toContain("look={lookOn ? 'video' : undefined}");
    expect(src).toMatch(/<GgCardView [^>]*boardSeq=\{boardSeq\} look=\{lookOn \? 'video' : undefined\}/);
    expect(src).not.toContain('04:00');
    expect(src).not.toContain('GG_CARD_AXIS_ALWAYS');
  });

  /* The doc's "Goldens moved" leaf counts are the fixtures' own: every `axis` value's leaves (a scalar or an empty
   * container = 1), counted per golden. A regen that moves the axis makes this fail until the doc is re-measured. */
  function axisLeaves(doc: unknown): { tiles: number; leaves: number } {
    const leaves = (o: unknown): number => {
      if (Array.isArray(o)) return o.length ? o.reduce((n: number, v) => n + leaves(v), 0) : 1;
      if (o && typeof o === 'object') {
        const vs = Object.values(o as Record<string, unknown>);
        return vs.length ? vs.reduce((n: number, v) => n + leaves(v), 0) : 1;
      }
      return 1;
    };
    let tiles = 0;
    let total = 0;
    const walk = (o: unknown): void => {
      if (Array.isArray(o)) { o.forEach(walk); return; }
      if (o && typeof o === 'object') {
        for (const [k, v] of Object.entries(o as Record<string, unknown>)) {
          if (k === 'axis') { tiles += 1; total += leaves(v); } else walk(v);
        }
      }
    };
    walk(doc);
    return { tiles, leaves: total };
  }

  it('the doc states the measured golden leaf counts, and they equal the fixtures (BOARD +656/16, on_open +84/2, potential +506/11)', async () => {
    const doc = await readSource('../docs/gajjala/video_view_2026_11_17.md');
    const board = axisLeaves(JSON.parse(await readSource('../backend/tests/fixtures/gajjala/gg5_board_2026_10_27.json')));
    const onOpen = axisLeaves(JSON.parse(await readSource('src/components/__fixtures__/gajjala_on_open_golden_2026_10_15.json')));
    const potential = axisLeaves(JSON.parse(await readSource('src/components/__fixtures__/gajjala_potential_golden_2026_10_15.json')));
    expect(board).toEqual({ tiles: 16, leaves: 656 });
    expect(onOpen).toEqual({ tiles: 2, leaves: 84 });
    expect(potential).toEqual({ tiles: 11, leaves: 506 });
    expect(doc).toContain(`**+${board.leaves} leaves on ${board.tiles} tiles**`);
    expect(doc).toContain(`on_open **+${onOpen.leaves} leaves on ${onOpen.tiles} tiles**`);
    expect(doc).toContain(`potential\n  **+${potential.leaves} leaves on ${potential.tiles} tiles**`);
    expect((doc.match(/0 changed, 0 removed\*\*, every added leaf under `\/axis`/g) || []).length).toBe(2);
  });

  it('NEGATIVE: the doc no longer carries the "not yet available … main session fills them in" placeholder', async () => {
    const doc = await readSource('../docs/gajjala/video_view_2026_11_17.md');
    expect(doc).not.toMatch(/not yet available/i);
    expect(doc).not.toMatch(/fills them in/i);
    expect(doc).not.toMatch(/WP-A's report/);
  });

  it('the planned main-session grep holds: no clock literal anywhere in lib/gajjala.ts (comments included); the refresh doc keeps its window in words', async () => {
    const lib = await readSource('src/lib/gajjala.ts');
    expect(lib).not.toContain('04:00');
    expect(lib).toContain('4 AM–8 PM ET window, 0 when closed');
    expect(lib).toContain('export function ggRefreshMs(');
  });

  it('NEGATIVE: the look reaches no fetch or query builder in the board', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const i = src.indexOf('const toggleLook = () => {');
    expect(i).toBeGreaterThan(0);
    const body = src.slice(i, src.indexOf('};', i));
    expect(body).not.toMatch(/fetch\(|setParam|ggQuery|setParams/);
    expect(src).not.toMatch(/ggQuery\([^)]*look/);
  });
});
