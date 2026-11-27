import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import watchFixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import boardSrc from './GajjalaBoard.tsx?raw';
import { GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import { GG_KISS_FILTER_LS } from '../lib/gajjala';
import { GG_LIKE_LS } from '../lib/ggLike';

/* 🧘 GG-like calm check — the 🚩 card chip, the 🚩 filter and the 🏁 mounts on the REAL board (2026-11-27, spec gglike §3.9,
 * WP fe-board). Ajay 2026-11-27: "find calmer and better setups.. I want to make sure we are finding similar setups to
 * Gajjala". The server judges each card and serves every word (the card block incl. `keep`, the board filter block, the 🏁
 * row chip and the GG-like-vs-not fold); the board draws them, hides only un-kept ✗ cards while HIS toggle is ON, and never
 * hides a card that rang or the `?focus=` name (C1). Boards are CLONES of the frozen fixtures; every served word here is a
 * CLONE value (no product sentence is typed). NEGATIVES throughout. Display only — nothing rings, gates or reorders. */

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return {
    ...m,
    PatternChart: (props: any) => (props.chartOnly
      ? <div data-testid="frame-chart" />
      : <div data-testid={`chart-${props.tile.symbol}`} />),
  };
});
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
const roomCalls: string[][] = [];
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: (syms: string[]) => {
    roomCalls.push([...syms]);
    return { map: new Map(), payload: null, loading: false, error: null, pending: 0 };
  },
}));

import GajjalaBoard from './GajjalaBoard';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const HAND: Record<string, any> = (hand as any).boards;
const POT: Record<string, any> = (potGolden as any).boards;

/* ---- served clones ---- */
const LIKE_BOARD = {
  label: '\u{1F9D8} clone like label', label_n_text: '{label} · {n}', hint: 'clone hint',
  hidden_text: '{n} clone hidden', reason_text: '{n} {label}', kept_text: '{n} clone kept',
  unknown_text: '{n} clone unknown', none_text: '{n} clone none', all_hidden_text: 'clone all hidden',
  show_all_text: 'clone show all', note: 'clone note sentence', separation_text: 'clone separation sentence',
  census_text: 'clone census sentence', rows: ['clone check row one', 'clone check row two'], source: 'clone',
};
type V = 'gg_like' | 'not' | 'unknown';
function blk(sym: string, verdict: V, o: { code?: string; label?: string; keep?: boolean } = {}) {
  return {
    verdict, tone: verdict === 'gg_like' ? 'ok' : verdict === 'not' ? 'no' : 'unknown',
    chip: `\u{1F9D8} clone chip ${sym}`, title: `clone title ${sym}`,
    reason: verdict === 'not' ? { code: o.code ?? 'near_high', label: o.label ?? 'clone under high' } : null,
    keep: o.keep === true,
    checks: [
      { key: 'base_bars', ok: verdict !== 'not', info: false, mark: verdict === 'not' ? '✗' : '✓', label: 'clone row label',
        value: 'clone value', need: 'clone need' },
      { key: 'lower_highs', ok: null, info: true, mark: 'ⓘ', label: 'clone info label', value: 'clone info value', need: null },
    ],
    info: null, source: 'read', source_text: null,
  };
}

type T = { sym: string; state?: string; like?: ReturnType<typeof blk> | null; kiss?: boolean | null; broker?: boolean };
function tileOf(base: any, spec: T, i: number, setup?: string): any {
  const t = clone(base.tiles[i % base.tiles.length]);
  t.symbol = spec.sym;
  t.href = `/stock/${spec.sym}`;
  delete t.focus;
  t.gajjala = { ...t.gajjala, state: spec.state ?? 'forming', ...(setup ? { setup } : {}) };
  if (spec.like) t.gajjala.gg_like = spec.like; else delete t.gajjala.gg_like;
  if (spec.kiss !== undefined) t.kiss_now = spec.kiss;
  return t;
}
function likeBoard(specs: T[], patch: Record<string, unknown> = {}): any {
  const b = clone(HAND.bull_flag);
  b.tiles = specs.map((s, i) => tileOf(HAND.bull_flag, s, i));
  b.gg_like = clone(LIKE_BOARD);
  return { ...b, ...patch };
}

/* AAA reads GG-like · BBB / CCC ✗ forming (two reasons) · DDD can't tell · EEE no block · FFF ✗ that RANG (served keep) */
const SIX: T[] = [
  { sym: 'AAA', like: blk('AAA', 'gg_like') },
  { sym: 'BBB', like: blk('BBB', 'not', { code: 'near_high', label: 'clone under high' }) },
  { sym: 'CCC', like: blk('CCC', 'not', { code: 'base_bars', label: 'clone short base' }) },
  { sym: 'DDD', like: blk('DDD', 'unknown') },
  { sym: 'EEE', like: null },
  { sym: 'FFF', state: 'aplus', like: blk('FFF', 'not', { code: 'tennis_drop', label: 'clone small ball', keep: true }) },
];
const ALL_NOT: T[] = [
  { sym: 'NAA', like: blk('NAA', 'not', { code: 'near_high', label: 'clone under high' }) },
  { sym: 'NBB', like: blk('NBB', 'not', { code: 'near_high', label: 'clone under high' }) },
  { sym: 'NCC', like: blk('NCC', 'not', { code: 'ema_hold', label: 'clone under ema' }) },
];

/* ---- the 👀 card-watch frames answer (the card_watch harness: CLONES of the 11-15 Watch fixture's OMH frames) ---- */
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };
function frame(sym: string, tf: string) {
  const omh = (watchFixture as any).rows[0];
  const f = clone(omh.frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf; f.label = tf;
  f.tile.symbol = sym; f.tile.href = ''; f.tile.lines = []; f.tile.bands = []; f.tile.markers = [];
  f.axis.start_epoch = START; f.axis.frame_min = SRC_MIN[tf];
  f.ema_tail = null; f.as_of_et = '10:30'; f.stale = false; f.empty_text = null;
  return f;
}
const framesPayload = (sym: string) => ({
  state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: '10:30', stale: false,
  text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
});

let served: any = null;
function stub(b: any) {
  served = b;
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const u = new URL(String(url), 'http://x');
    if (u.pathname.startsWith(GGC_PATH + '/')) {
      const sym = decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1));
      return { ok: true, status: 200, json: async () => framesPayload(sym) };
    }
    if (u.pathname.endsWith('/scan')) return { ok: false, status: 404, json: async () => ({}) };
    if (/\/chart-maps\/gajjala$/.test(u.pathname)) return { ok: true, status: 200, json: async () => clone(served) };
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}

let store: Map<string, string>;
function mem(seed: Record<string, string>) {
  store = new Map(Object.entries(seed));
  return {
    getItem: (k: string) => (store.has(k) ? store.get(k)! : null),
    setItem: (k: string, v: string) => { store.set(k, String(v)); },
    removeItem: (k: string) => { store.delete(k); }, clear: () => store.clear(),
  };
}
const GRID = { 'gg-card-watch': '0' };
const WATCH = { 'gg-card-watch': '1' };

async function mount(b: any, opts: { sub?: string; q?: string; seed?: Record<string, string> } = {}) {
  vi.stubGlobal('localStorage', mem({ ...GRID, ...(opts.seed || {}) }));
  stub(b);
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?tab=gajjala&sub=${opts.sub ?? 'bull_flag'}${opts.q ?? ''}`]}>
      <GajjalaBoard />
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  await act(async () => { await new Promise((res) => setTimeout(res, 20)); });
  return r;
}

/** Every card in the DOM, in DOM order (cards hidden by the card-watch pager included). */
const cards = (c: HTMLElement) => [...c.querySelectorAll('[data-testid^="gg-tile-"]')]
  .map((e) => e.getAttribute('data-testid') || '').filter((id) => /^gg-tile-[A-Z]+$/.test(id))
  .map((id) => id.slice('gg-tile-'.length));
const toggle = () => screen.queryByTestId('gg-like-toggle');
const line = () => screen.queryByTestId('gg-like-hidden');

beforeEach(() => { roomCalls.length = 0; busHandlers.clear(); vi.stubGlobal('EventSource', class {}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧘 the card chip — ONE chip, the list closed until tapped', () => {
  it('a card with a served block draws ONE chip (the served words) in the pills row; no list until the tap; the tap opens it', async () => {
    const { container } = await mount(likeBoard(SIX));
    const card = screen.getByTestId('gg-tile-BBB');
    const chips = card.querySelectorAll('.gg-like-chip');
    expect(chips).toHaveLength(1);
    const chip = chips[0] as HTMLElement;
    expect(chip.textContent).toBe('\u{1F9D8} clone chip BBB');
    expect(chip.getAttribute('title')).toBe('clone title BBB');
    expect(chip.closest('.gg-pills')).not.toBeNull();
    expect(within(card).queryByTestId('gg-like-list-BBB')).toBeNull();
    expect(card.textContent).not.toContain('clone row label');
    fireEvent.click(chip);
    const list = within(card).getByTestId('gg-like-list-BBB');
    expect(list.textContent).toContain('clone row label');
    expect(list.querySelector('.gg-like-row--info')?.textContent).toContain('clone info label');
    expect(container.querySelectorAll('[data-testid^="gg-like-list-"]')).toHaveLength(1);
  });

  it('NEGATIVE: a card without the key draws nothing new — its DOM equals the same card on a board with no gg_like at all', async () => {
    const a = await mount(likeBoard(SIX));
    const withKeys = screen.getByTestId('gg-tile-EEE').outerHTML;
    expect(screen.getByTestId('gg-tile-EEE').querySelector('.gg-like-chip')).toBeNull();
    a.unmount();
    const bare = likeBoard(SIX.map((s) => ({ ...s, like: null })));
    delete bare.gg_like;
    await mount(bare);
    expect(screen.getByTestId('gg-tile-EEE').outerHTML).toBe(withKeys);
  });

  it('NEGATIVE: a junk block (foreign verdict / blank chip) draws no chip and is never hidden', async () => {
    const junk = [{ ...blk('JAA', 'not'), verdict: 'maybe' }, { ...blk('JBB', 'not'), chip: '  ' }];
    const b = likeBoard([{ sym: 'AAA', like: blk('AAA', 'gg_like') }, { sym: 'JAA' }, { sym: 'JBB' }]);
    b.tiles[1].gajjala.gg_like = junk[0];
    b.tiles[2].gajjala.gg_like = junk[1];
    const { container } = await mount(b, { seed: { [GG_LIKE_LS.board]: '1' } });
    expect(screen.getByTestId('gg-tile-JAA').querySelector('.gg-like-chip')).toBeNull();
    expect(screen.getByTestId('gg-tile-JBB').querySelector('.gg-like-chip')).toBeNull();
    expect(cards(container)).toEqual(['AAA', 'JAA', 'JBB']);
  });
});

describe('🧘 the toggle — served label + live count, default OFF, absent without the served block', () => {
  it('default OFF: the toggle prints the served label with the live count BEFORE it is tapped; every card drawn; no line', async () => {
    const { container } = await mount(likeBoard(SIX));
    const t = toggle()!;
    expect(t.textContent).toBe('\u{1F9D8} clone like label · 1');
    expect(t.getAttribute('aria-pressed')).toBe('false');
    expect(t.getAttribute('title')).toBe('clone hint');
    expect(t.className).toContain('cm-phase-btn');
    /* in the controls row, before the ⓘ */
    const row = t.closest('.cm-phase') as HTMLElement;
    expect(row).not.toBeNull();
    const kids = [...row.children];
    expect(kids.indexOf(t)).toBeLessThan(kids.indexOf(screen.getByTestId('gg-sub-toggle')));
    expect(cards(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']);
    expect(line()).toBeNull();
  });

  it('a board of ✗ cards reads "· 0" before the tap', async () => {
    await mount(likeBoard(ALL_NOT));
    expect(toggle()!.textContent).toBe('\u{1F9D8} clone like label · 0');
  });

  it('NEGATIVE: no served board block → no toggle (the card chips still draw); a stored ON hides nothing', async () => {
    const b = likeBoard(SIX);
    delete b.gg_like;
    const { container } = await mount(b, { seed: { [GG_LIKE_LS.board]: '1' } });
    expect(toggle()).toBeNull();
    expect(line()).toBeNull();
    expect(cards(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']);
    expect(screen.getByTestId('gg-tile-BBB').querySelector('.gg-like-chip')).not.toBeNull();
  });

  it('NEGATIVE: a served board block but no card with a parsed block → no toggle', async () => {
    const { container } = await mount(likeBoard(SIX.map((s) => ({ ...s, like: null }))), { seed: { [GG_LIKE_LS.board]: '1' } });
    expect(toggle()).toBeNull();
    expect(cards(container)).toHaveLength(6);
  });
});

describe('🧘 ON — only un-kept ✗ cards leave; served order; the served line; show all', () => {
  it('ON hides BBB and CCC only, keeps the served order, prints the served count line; show all turns it OFF', async () => {
    const { container } = await mount(likeBoard(SIX));
    const roomBefore = roomCalls[roomCalls.length - 1];
    const countsBefore = screen.getByTestId('gg-counts').textContent;
    fireEvent.click(toggle()!);
    expect(toggle()!.getAttribute('aria-pressed')).toBe('true');
    expect(store.get(GG_LIKE_LS.board)).toBe('1');
    expect(cards(container)).toEqual(['AAA', 'DDD', 'EEE', 'FFF']);
    expect(line()!.textContent).toContain(
      '2 clone hidden (1 clone short base · 1 clone under high) · 1 clone kept · 1 clone unknown · 1 clone none');
    expect(line()!.textContent).not.toContain('clone all hidden');
    /* NEGATIVE: the room POST symbols, the counts line and the served tiles are untouched */
    expect(roomCalls[roomCalls.length - 1]).toEqual(roomBefore);
    expect(roomBefore).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']);
    expect(screen.getByTestId('gg-counts').textContent).toBe(countsBefore);
    expect(served.tiles.map((t: any) => t.symbol)).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']);
    /* the toggle's count is unchanged by its own filter */
    expect(toggle()!.textContent).toBe('\u{1F9D8} clone like label · 1');
    fireEvent.click(screen.getByTestId('gg-like-hidden-show-all'));
    expect(cards(container)).toEqual(['AAA', 'BBB', 'CCC', 'DDD', 'EEE', 'FFF']);
    expect(toggle()!.getAttribute('aria-pressed')).toBe('false');
    expect(store.get(GG_LIKE_LS.board)).toBe('0');
    expect(line()).toBeNull();
  });

  it('NEGATIVE: the can\'t-tell card, the no-block card and the rang ✗ card (served keep) stay drawn while ON', async () => {
    await mount(likeBoard(SIX), { seed: { [GG_LIKE_LS.board]: '1' } });
    for (const s of ['DDD', 'EEE', 'FFF']) expect(screen.getByTestId(`gg-tile-${s}`)).toBeTruthy();
    expect(screen.queryByTestId('gg-tile-BBB')).toBeNull();
  });
});

describe('🧘 the push link [C1] — ?focus= on a ✗ forming card is never hidden (grid AND card-watch)', () => {
  for (const [mode, seed] of [['grid', GRID], ['card-watch', WATCH]] as const) {
    it(`${mode}: filter ON from storage + ?focus=BBB → BBB drawn, gg-focus, scrolled ONCE, counted as kept; CCC hidden`, async () => {
      const calls: string[] = [];
      const orig = (Element.prototype as any).scrollIntoView;
      (Element.prototype as any).scrollIntoView = function scrollIntoView(this: HTMLElement) {
        calls.push(this.getAttribute('data-testid') || '');
      };
      try {
        const { container } = await mount(likeBoard(SIX), { q: '&focus=BBB', seed: { ...seed, [GG_LIKE_LS.board]: '1' } });
        if (mode === 'card-watch') await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
        else expect(screen.queryByTestId('gg-cardwatch')).toBeNull();
        const card = screen.getByTestId('gg-tile-BBB');
        expect(card.className).toContain('gg-focus');
        expect(card.hidden).toBe(false);
        await waitFor(() => expect(calls.filter((c) => c === 'gg-tile-BBB')).toHaveLength(1));
        await act(async () => { await new Promise((res) => setTimeout(res, 30)); });
        expect(calls.filter((c) => c === 'gg-tile-BBB')).toHaveLength(1);
        expect(screen.queryByTestId('gg-tile-CCC')).toBeNull();
        expect(cards(container)).toEqual(['AAA', 'BBB', 'DDD', 'EEE', 'FFF']);
        expect(line()!.textContent).toContain('1 clone hidden (1 clone short base)');
        expect(line()!.textContent).toContain('2 clone kept');
      } finally {
        (Element.prototype as any).scrollIntoView = orig;
      }
    });

    it(`${mode} NEGATIVE: the same board with no focus → BBB and CCC hidden; the rang FFF (served keep) still drawn`, async () => {
      const { container } = await mount(likeBoard(SIX), { seed: { ...seed, [GG_LIKE_LS.board]: '1' } });
      if (mode === 'card-watch') await waitFor(() => expect(screen.getByTestId('gg-cardwatch')).toBeTruthy());
      expect(screen.queryByTestId('gg-tile-BBB')).toBeNull();
      expect(screen.queryByTestId('gg-tile-CCC')).toBeNull();
      expect(cards(container)).toEqual(['AAA', 'DDD', 'EEE', 'FFF']);
      expect(line()!.textContent).toContain('1 clone kept');
    });
  }
});

describe('🧘 the empty board [C3] — every card ✗ and none kept', () => {
  it('ON → no card, the line STARTS with the served all-hidden words and offers show all; no gg-empty; show all restores every card', async () => {
    const { container } = await mount(likeBoard(ALL_NOT), { seed: { [GG_LIKE_LS.board]: '1' } });
    expect(cards(container)).toEqual([]);
    const l = line()!;
    expect(l.textContent!.startsWith('clone all hidden')).toBe(true);
    expect(l.textContent).toContain('3 clone hidden (2 clone under high · 1 clone under ema)');
    expect(screen.queryByTestId('gg-empty')).toBeNull();
    expect(toggle()!.textContent).toBe('\u{1F9D8} clone like label · 0');
    fireEvent.click(screen.getByTestId('gg-like-hidden-show-all'));
    expect(cards(container)).toEqual(['NAA', 'NBB', 'NCC']);
    expect(line()).toBeNull();
  });

  it('NEGATIVE: OFF the same board draws every card and no line', async () => {
    const { container } = await mount(likeBoard(ALL_NOT));
    expect(cards(container)).toEqual(['NAA', 'NBB', 'NCC']);
    expect(line()).toBeNull();
  });
});

describe('🧘 ON with nothing to hide [T10] — show all is always drawn while ON', () => {
  const ALL_LIKE: T[] = [{ sym: 'AAA', like: blk('AAA', 'gg_like') }];
  it('ON (stored) on a board of GG-like cards only → every card drawn, the line drawn with show all and no count words; show all turns it OFF', async () => {
    const { container } = await mount(likeBoard(ALL_LIKE), { seed: { [GG_LIKE_LS.board]: '1' } });
    expect(toggle()!.getAttribute('aria-pressed')).toBe('true');
    expect(cards(container)).toEqual(['AAA']);
    const l = line()!;
    expect(l).not.toBeNull();
    expect(l.querySelector('.gg-like-hidden-line')).toBeNull();
    expect(screen.getByTestId('gg-like-hidden-show-all')).toBeTruthy();
    fireEvent.click(screen.getByTestId('gg-like-hidden-show-all'));
    expect(toggle()!.getAttribute('aria-pressed')).toBe('false');
    expect(store.get(GG_LIKE_LS.board)).toBe('0');
    expect(line()).toBeNull();
    expect(cards(container)).toEqual(['AAA']);
  });

  it('NEGATIVE: OFF the same board draws no line and no show all', async () => {
    await mount(likeBoard(ALL_LIKE));
    expect(line()).toBeNull();
    expect(screen.queryByTestId('gg-like-hidden-show-all')).toBeNull();
  });
});

describe('🧘 the note lives in the sub fold only; 💋 + 🧘 compose; the 🚫 header stays put', () => {
  it('note / separation / census / rows sit inside the closed sub fold body and nowhere above the cards', async () => {
    const { container } = await mount(likeBoard(SIX));
    const body = screen.getByTestId('gg-sub-body');
    expect(body.hidden).toBe(true);
    const note = within(body).getByTestId('gg-like-note');
    expect(note.textContent).toContain('clone note sentence');
    expect(note.textContent).toContain('clone separation sentence');
    expect(note.textContent).toContain('clone census sentence');
    expect(note.textContent).toContain('clone check row two');
    const rest = (container.querySelector('.gg-board') as HTMLElement).cloneNode(true) as HTMLElement;
    rest.querySelectorAll('[data-testid="gg-sub-body"]').forEach((n) => n.remove());
    for (const w of ['clone note sentence', 'clone separation sentence', 'clone census sentence', 'clone check row one']) {
      expect(rest.textContent).not.toContain(w);
    }
    expect(container.querySelectorAll('[data-testid="gg-like-note"]')).toHaveLength(1);
  });

  it('💋 and 🧘 compose: 💋 drops kiss_now false, 🧘 drops un-kept ✗ of what is left; order kept; both lines print', async () => {
    const KISS = { label: '\u{1F48B} clone', hint: 'clone', hidden_text_template: '{shown} shown · {hidden} kiss hidden · {unknown} kiss unknown' };
    const b = clone(HAND.bull_flag);
    b.sub = 'kiss_fly';
    b.kiss_filter = KISS;
    b.gg_like = clone(LIKE_BOARD);
    const specs: T[] = [
      { sym: 'KAA', like: blk('KAA', 'gg_like'), kiss: true },
      { sym: 'KBB', like: blk('KBB', 'gg_like'), kiss: false },
      { sym: 'KCC', like: blk('KCC', 'not'), kiss: true },
      { sym: 'KDD', like: blk('KDD', 'unknown'), kiss: null },
    ];
    b.tiles = specs.map((s, i) => tileOf(HAND.bull_flag, s, i, 'kiss_fly'));
    const { container } = await mount(b, { sub: 'kiss_fly', seed: { [GG_KISS_FILTER_LS]: '1', [GG_LIKE_LS.board]: '1' } });
    expect(cards(container)).toEqual(['KAA', 'KDD']);
    expect(screen.getByTestId('gg-kiss-filter-line').textContent).toBe('3 shown · 1 kiss hidden · 1 kiss unknown');
    expect(line()!.textContent).toContain('1 clone hidden');
    /* the toggle counts the cards the 💋 split left (KBB is out) */
    expect(toggle()!.textContent).toBe('\u{1F9D8} clone like label · 1');
  });

  it('the 🚫 section header still sits right before the first 🚫 card that is DRAWN (the first 🚫 card hidden by 🧘)', async () => {
    const b = clone(POT.potential);
    delete b.focus;
    for (const t of b.tiles) delete t.focus;
    const tag = b.broker_flags.text;
    b.broker_flags = { ...b.broker_flags, symbols: ['CCC', 'HHH'],
      section: { key: 'broker', title: tag, text: `${tag} · 2`, hint: null, n: 2, symbols: ['CCC', 'HHH'] } };
    for (const t of b.tiles) {
      if (['CCC', 'HHH'].includes(t.symbol)) t.broker_text = tag;
      t.gajjala = { ...t.gajjala, gg_like: t.symbol === 'CCC' ? blk('CCC', 'not') : blk(t.symbol, 'gg_like') };
    }
    b.gg_like = clone(LIKE_BOARD);
    const { container } = await mount(b, { sub: 'potential', seed: { [GG_LIKE_LS.board]: '1' } });
    const grid = container.querySelector('.cm-grid') as HTMLElement;
    const seq = [...grid.children].map((e) => {
      const id = e.getAttribute('data-testid') || '';
      return id === 'gg-broker-section' ? 'HEAD' : id.replace('gg-tile-', '');
    });
    expect(seq).toEqual(['EEE', 'DDD', 'AAA', 'JJJ', 'HEAD', 'HHH']);
  });
});

describe('🏁 the row chip and the GG-like-vs-not fold', () => {
  const SPLIT = {
    label: '\u{1F9D8} clone split label', title: 'clone split title',
    lines: ['clone split line one', 'clone split line two', 'clone split line three'], note: 'clone split note',
  };
  function trBoard(withSplit: boolean): any {
    const b = clone((trGolden as any).boards.today);
    const rows = b.track_record.days[0].rows;
    rows[0].gg_like = { verdict: 'not', chip: '\u{1F9D8} clone row chip', tone: 'no', title: 'clone row title',
                        source: 'computed_later', source_text: 'clone later words' };
    rows[1].gg_like = { verdict: 'maybe', chip: '\u{1F9D8} junk', tone: 'no', title: null, source: 'ring', source_text: null };
    if (withSplit) b.track_record.gg_like_split = SPLIT; else delete b.track_record.gg_like_split;
    return b;
  }

  it('the served row chip beside the 📶 chip (title + source words on hover); the fold is CLOSED and prints every served line in order', async () => {
    const b = trBoard(true);
    const key0 = b.track_record.days[0].rows[0].key;
    const key1 = b.track_record.days[0].rows[1].key;
    await mount(b, { sub: 'track_record' });
    const chip = screen.getByTestId(`gg-tr-like-${key0}`);
    expect(chip.textContent).toBe('\u{1F9D8} clone row chip');
    expect(chip.getAttribute('title')).toBe('clone row title · clone later words');
    expect(chip.className).toContain('gg-like-no');
    expect(screen.queryByTestId(`gg-tr-like-${key1}`)).toBeNull();
    const fold = screen.getByTestId('gg-tr-like') as HTMLDetailsElement;
    expect(fold.tagName).toBe('DETAILS');
    expect(fold.open).toBe(false);
    expect(fold.className).toContain('gg-tr-rule');
    expect(fold.querySelector('summary')!.textContent).toBe(SPLIT.label);
    expect(within(fold).getByTestId('gg-tr-like-title').textContent).toBe(SPLIT.title);
    expect(within(fold).getAllByTestId('gg-tr-like-line').map((e) => e.textContent)).toEqual(SPLIT.lines);
    expect(within(fold).getByTestId('gg-tr-like-note').textContent).toBe(SPLIT.note);
    /* after the rule fold */
    const rule = screen.getByTestId('gg-tr-rule');
    expect(rule.compareDocumentPosition(fold) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: no gg_like_split → no fold; a junk split (no words) → no fold', async () => {
    const a = await mount(trBoard(false), { sub: 'track_record' });
    expect(screen.queryByTestId('gg-tr-like')).toBeNull();
    a.unmount();
    const b = trBoard(false);
    b.track_record.gg_like_split = { label: ' ', title: null, lines: [], note: null };
    await mount(b, { sub: 'track_record' });
    expect(screen.queryByTestId('gg-tr-like')).toBeNull();
  });
});

describe('📱 430 px guard + source guards', () => {
  const code = boardSrc.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');

  it('the card chip mounts INSIDE the wrapping .gg-pills row; the toggle is a wrapping .cm-phase-btn of the controls row', () => {
    const pills = code.match(/<div className="gg-pills">([\s\S]*?)<\/div>/);
    expect(pills).not.toBeNull();
    expect(pills![1]).toContain('<GgLikeCard like={like} sym={sym} />');
    const controls = code.match(/<div className="cm-phase" role="tablist" aria-label="Bar size">([\s\S]*?)<GgFoldToggle testid="gg-sub-toggle"/);
    expect(controls).not.toBeNull();
    expect(controls![1]).toContain('<GgLikeToggle');
  });

  it('the 🧘 stylesheet keeps the chip, the toggle and the line wrapping (overflow-wrap: anywhere, min-width: 0)', async () => {
    const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
    const fs: any = mod?.default || mod;
    const root = (globalThis as any).process?.cwd?.() || '.';
    const css: string = fs.readFileSync(`${root}/src/styles/ggLike.css`, 'utf8');
    const gajjala: string = fs.readFileSync(`${root}/src/styles/gajjala.css`, 'utf8');
    for (const sel of ['.gg-like-chip', '.gg-like-toggle', '.gg-like-hidden']) {
      const m = css.match(new RegExp(`(^|\\n)\\s*${sel.replace('.', '\\.')}\\s*\\{([^}]*)\\}`));
      expect(m, sel).not.toBeNull();
      expect(m![2]).toMatch(/overflow-wrap:\s*anywhere/);
      expect(m![2]).toMatch(/min-width:\s*0\b/);
    }
    expect(css).not.toMatch(/white-space:\s*nowrap/);
    expect(gajjala).toMatch(/\.gg-pills\s*\{[^}]*flex-wrap:\s*wrap/);
  });

  it('NEGATIVE: the board calls ggLikeSplit with the keep (focus) argument, mounts GgLikeNote only in the sub fold, and types no served 🧘 word', () => {
    expect(code).toMatch(/ggLikeSplit\(kissSplit\.visible, likeOf, likeActive, \(t\) => t\.symbol === focus\)/);
    expect(code).toMatch(/const liveTiles = likeSplit\.visible;/);
    const notes = code.match(/<GgLikeNote\b/g) || [];
    expect(notes).toHaveLength(1);
    const body = code.match(/<GgFoldBody id="gg-sub-body" testid="gg-sub-body">([\s\S]*?)<\/GgFoldBody>/);
    expect(body![1]).toContain('<GgLikeNote');
    const lower = code.toLowerCase();
    for (const w of ['gg-like only', 'tennis', 'not gg-like', "can't tell", 'still shown', 'show all']) {
      expect(lower).not.toContain(w);
    }
    expect(code).not.toContain('gg-like-only:watch');
  });
});
