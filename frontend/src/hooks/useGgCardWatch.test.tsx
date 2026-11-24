// REVERTED 2026-11-23 (👀 Watch layout default OFF — his "I cannot see the height of the chart"): the ON-mode cases here now seed 'gg-card-watch' = '1' explicitly.
import { StrictMode, useEffect, type ReactNode } from 'react';
import { act, fireEvent, render, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import watchFixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GGC_FETCH_FAILED, GGC_PATH, GGC_STRETCH_ORDER } from '../lib/gajjalaCardView';
import type { GgTile } from '../lib/gajjala';

/* 👀 useGgCardWatch — the card grid's Watch state (2026-11-18, spec cardview §3.2 / §4 WP-B).
 * Ajay 2026-11-18: "I need the watch list kinda chart formant view video view as default here too from the tabs pages".
 *
 * The REAL hook over a fake `fetch` and a hand-driven bus (the GajjalaBoard.card_view.test.tsx harness). Frames payloads are
 * CLONES of the 2026-11-15 Watch fixture's OMH frames relabelled 15m / 5m / 1m (fixtures never edited). NEGATIVES on every
 * block: GETs only for the names on screen, never on a quotes batch / a new tiles array / a 📺 flip; nothing at all while
 * not active; the 1-min page and Luk never draw it; an older answer never wins; an off-page name shows no live bars. */

const busHandlers = new Map<string, Set<(e: any) => void>>();
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: (e: any) => void) => {
    let s = busHandlers.get(type);
    if (!s) { s = new Set(); busHandlers.set(type, s); }
    s.add(fn);
    return () => { busHandlers.get(type)?.delete(fn); };
  },
}));
const metasCalls = { n: 0 };
vi.mock('../lib/ggwLive', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, ggwFrameMetas: (rows: any) => { metasCalls.n += 1; return m.ggwFrameMetas(rows); } };
});

import { useGgCardWatch, type GgCardWatch } from './useGgCardWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const START = Date.UTC(2026, 10, 13, 9, 0, 0) / 1000;
const at = (min: number, sec = 0) => START + min * 60 + sec;
const SRC_TF: Record<string, string> = { '15m': '3m', '5m': '5m', '1m': '1m' };
const SRC_MIN: Record<string, number> = { '15m': 3, '5m': 5, '1m': 1 };

function frame(sym: string, tf: string) {
  const omh = (watchFixture as any).rows[0];
  const f = clone(omh.frames.find((x: any) => x.tf === SRC_TF[tf]));
  f.tf = tf;
  f.tile.symbol = sym;
  f.tile.href = '';
  f.tile.lines = []; f.tile.bands = []; f.tile.markers = [];
  f.axis.start_epoch = START;
  f.axis.frame_min = SRC_MIN[tf];
  f.ema_tail = null;
  f.as_of_et = '10:30';
  f.stale = false;
  f.empty_text = null;
  return f;
}
function payload(sym: string, mark = '') {
  return {
    state: 'ok', symbol: sym, session: '2026-11-13', is_today: true, in_window: true, as_of_et: `10:30${mark}`, stale: false,
    text: null, frames: GGC_STRETCH_ORDER.map((tf) => frame(sym, tf)),
  };
}
const SYMS = ['SYM1', 'SYM2', 'SYM3', 'SYM4', 'SYM5', 'SYM6'];
function card(sym: string, over: Partial<GgTile> = {}): GgTile {
  return {
    symbol: sym, href: `/sepa/${sym}`, bars: [{ t: '2026-11-13 10:30', o: 1, h: 1, l: 1, c: 1, v: 1 }], stats: [], why: '', tf: '5m',
    lines: [{ label: 'TRIGGER 4.20', price: 4.2, tone: 'buy' }], bands: [], markers: [],
    gajjala: { plan_text: `plan of ${sym}` }, ...over,
  } as unknown as GgTile;
}
const cards = (syms = SYMS) => syms.map((s) => card(s));

type Answer = { ok: boolean; body: any } | Promise<{ ok: boolean; body: any }>;
let answer: (sym: string) => Answer = (sym) => ({ ok: true, body: payload(sym) });
const fetchMock = vi.fn(async (url: string) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.startsWith(GGC_PATH + '/')) {
    const a = await answer(decodeURIComponent(u.pathname.slice(GGC_PATH.length + 1)));
    return { ok: a.ok, status: a.ok ? 200 : 500, json: async () => a.body };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const gets = () => fetchMock.mock.calls.map(([u]) => decodeURIComponent(String(u).split(GGC_PATH + '/')[1]));
const emit = (payload: unknown) => act(async () => {
  for (const fn of busHandlers.get('gajjala.update') || []) fn({ type: 'gajjala.update', ts: 0, payload });
});
const quotes = (q: Record<string, unknown>, variant = 'gajjala') => ({ kind: 'quotes', variant, quotes: q });
const qt = (price: number, asOf: number) => ({ price, as_of_epoch: asOf, vs: null, size: 700 });
const flush = () => act(async () => { await new Promise((r) => setTimeout(r, 0)); });

function mem(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
  };
}

type P = {
  tiles: GgTile[]; vkey: string; boardSeq: number; look?: 'video'; focus: string | null; stretched: boolean; enabled: boolean;
};
const base = (over: Partial<P> = {}): P => ({
  tiles: cards(), vkey: 'gajjala', boardSeq: 1, focus: null, stretched: false, enabled: true, ...over,
});
function hook(p: P = base(), wrapper?: (props: { children: ReactNode }) => JSX.Element) {
  return renderHook((props: P) => useGgCardWatch(props), { initialProps: p, wrapper });
}

beforeEach(() => {
  busHandlers.clear();
  fetchMock.mockClear();
  metasCalls.n = 0;
  answer = (sym) => ({ ok: true, body: payload(sym) });
  vi.stubGlobal('fetch', fetchMock);
  vi.stubGlobal('EventSource', class {});
  vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '1' }));
});
afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('👀 frames GETs — the names on screen only, once per landed board read', () => {
  it('6 cards at 2 per screen → GETs for the first 2 only, in served order; boardSeq + 1 → exactly 2 more', async () => {
    const h = hook();
    await waitFor(() => expect(gets()).toEqual(['SYM1', 'SYM2']));
    expect(h.result.current.active).toBe(true);
    expect(h.result.current.on).toBe(true);
    expect(h.result.current.layout).toBe(2);
    h.rerender(base({ boardSeq: 2 }));
    await waitFor(() => expect(gets()).toEqual(['SYM1', 'SYM2', 'SYM1', 'SYM2']));
  });

  it('NEGATIVE: a NEW tiles array (same names), a 📺 flip and a quotes batch → zero GETs', async () => {
    const h = hook();
    await waitFor(() => expect(gets()).toHaveLength(2));
    h.rerender(base({ tiles: cards() }));
    h.rerender(base({ tiles: cards(), look: 'video' }));
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    await flush();
    expect(gets()).toHaveLength(2);
  });

  it('page 2 → GETs for SYM3 + SYM4 only; back to page 1 → 0 (already read for this boardSeq) [C5]', async () => {
    const h = hook();
    await waitFor(() => expect(gets()).toHaveLength(2));
    act(() => h.result.current.goPage(1));
    await waitFor(() => expect(gets()).toEqual(['SYM1', 'SYM2', 'SYM3', 'SYM4']));
    expect(h.result.current.page).toBe(1);
    act(() => h.result.current.goPage(0));
    await flush();
    expect(gets()).toHaveLength(4);
  });

  it('a ticker toggled on (SYM5) → ONE GET', async () => {
    const h = hook();
    await waitFor(() => expect(gets()).toHaveLength(2));
    act(() => h.result.current.togglePick('SYM5'));
    await waitFor(() => expect(gets()).toEqual(['SYM1', 'SYM2', 'SYM5']));
    expect(h.result.current.usePick).toBe(true);
    expect(h.result.current.shown('SYM5')).toBe(true);
    expect(h.result.current.shown('SYM3')).toBe(false);
  });

  it('NEGATIVE: enabled false (🏁 / 📋) → 0 GETs and no bus subscription; inactive', async () => {
    const h = hook(base({ enabled: false }));
    await flush();
    expect(gets()).toHaveLength(0);
    expect(busHandlers.get('gajjala.update')?.size ?? 0).toBe(0);
    expect(h.result.current.active).toBe(false);
  });

  it('NEGATIVE: no tiles (an empty sub) → inactive, 0 GETs, even with the mode ON [C7]', async () => {
    const h = hook(base({ tiles: [] }));
    await flush();
    expect(h.result.current.on).toBe(true);
    expect(h.result.current.active).toBe(false);
    expect(gets()).toHaveLength(0);
  });

  it('NEGATIVE: the 1-min page and Luk → allowed false, on false even with "1" stored; 0 GETs', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '1' }));
    for (const vkey of ['gajjala_1m', 'luk']) {
      const h = hook(base({ vkey }));
      await flush();
      expect(h.result.current.allowed).toBe(false);
      expect(h.result.current.on).toBe(false);
      expect(h.result.current.active).toBe(false);
      h.unmount();
    }
    expect(gets()).toHaveLength(0);
    expect(hook(base({ vkey: 'gajjala_audited' })).result.current.allowed).toBe(true);
  });

  it('NEGATIVE: a stored "0" → off, inactive, 0 GETs', async () => {
    vi.stubGlobal('localStorage', mem({ 'gg-card-watch': '0' }));
    const h = hook();
    await flush();
    expect(h.result.current.on).toBe(false);
    expect(h.result.current.active).toBe(false);
    expect(gets()).toHaveLength(0);
  });

  it('NEGATIVE: an older answer never overwrites a newer one (per-symbol newest wins)', async () => {
    let releaseOld: (() => void) | null = null;
    answer = (sym) => (sym === 'SYM1' && !releaseOld
      ? new Promise((res) => { releaseOld = () => res({ ok: true, body: payload(sym, ' old') }); })
      : { ok: true, body: payload(sym, ' new') });
    const h = hook();
    await waitFor(() => expect(gets()).toHaveLength(2));
    h.rerender(base({ boardSeq: 2 }));
    await waitFor(() => expect(gets()).toHaveLength(4));
    await waitFor(() => expect(h.result.current.rowOf(cards()[0]).as_of_et).toBe('10:30 new'));
    await act(async () => { releaseOld!(); await new Promise((r) => setTimeout(r, 0)); });
    expect(h.result.current.rowOf(cards()[0]).as_of_et).toBe('10:30 new');
  });

  it('NEGATIVE: a failed RE-read keeps the frames; a failed FIRST read prints GGC_FETCH_FAILED; a served error its reason', async () => {
    const tiles = cards();
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
    answer = () => ({ ok: false, body: null });
    h.rerender(base({ tiles, boardSeq: 2 }));
    await waitFor(() => expect(gets()).toHaveLength(4));
    await flush();
    expect(h.result.current.rowOf(tiles[0]).state).toBe('ok');
    expect(h.result.current.rowOf(tiles[0]).frames).toHaveLength(3);
    act(() => h.result.current.goPage(1));
    await waitFor(() => expect(h.result.current.rowOf(tiles[2]).state).toBe('error'));
    expect(h.result.current.rowOf(tiles[2]).text).toBe(GGC_FETCH_FAILED);
    answer = () => ({ ok: true, body: { state: 'error', reason: 'served reason words' } });
    act(() => h.result.current.goPage(2));
    await waitFor(() => expect(h.result.current.rowOf(tiles[4]).text).toBe('served reason words'));
    expect(h.result.current.rowOf(tiles[4]).frames).toEqual([]);
  });

  it('rows: loading → ok; the head text is the served text only (plan prints once, below)', async () => {
    const tiles = cards();
    const h = hook(base({ tiles }));
    expect(h.result.current.rowOf(tiles[0]).state).toBe('loading');
    await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
    expect(h.result.current.rowOf(tiles[0]).text).toBeNull();
    expect(h.result.current.rowOf(tiles[0]).frames.map((f) => f.tf)).toEqual(['15m', '5m', '1m']);
  });

  it('NEGATIVE: a name dropped from the list drops its load', async () => {
    const tiles = cards();
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[0]).state).toBe('ok'));
    h.rerender(base({ tiles: tiles.slice(1) }));
    await flush();
    expect(h.result.current.rowOf(tiles[0]).state).toBe('loading');
  });

  it('rowOf identity: patch card A → row A new, row B the SAME object (no redraw of B\'s svgs)', async () => {
    const tiles = cards();
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[1]).state).toBe('ok'));
    const a0 = h.result.current.rowOf(tiles[0]);
    const b0 = h.result.current.rowOf(tiles[1]);
    const patched = [{ ...tiles[0] }, ...tiles.slice(1)];
    h.rerender(base({ tiles: patched }));
    expect(h.result.current.rowOf(patched[0])).not.toBe(a0);
    expect(h.result.current.rowOf(patched[1])).toBe(b0);
    /* the 📺 flip rebuilds (the overlay is stripped) */
    h.rerender(base({ tiles: patched, look: 'video' }));
    expect(h.result.current.rowOf(patched[1])).not.toBe(b0);
  });
});

describe('👀 live — one fold, every loaded row; the display gated by shown [C2]', () => {
  it('a batch of THIS variant moves a SHOWN name; NEGATIVE: another variant\'s batch changes nothing', async () => {
    const h = hook();
    await waitFor(() => expect(h.result.current.rowOf(cards()[0]).state).toBe('ok'));
    expect(h.result.current.liveOf('SYM1')).toBeUndefined();
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    const l1 = h.result.current.liveOf('SYM1');
    expect(l1).toBeDefined();
    expect(Object.keys(l1!.by).sort()).toEqual(['15m', '1m', '5m']);
    await emit(quotes({ SYM1: qt(9.9, at(392)) }, 'gajjala_audited'));
    expect(h.result.current.liveOf('SYM1')).toBe(l1);
  });

  it('a batch while SYM3 is off-page → no live shown; ▶ to its page (0 GETs) → the earlier prints show', async () => {
    const h = hook();
    await waitFor(() => expect(gets()).toHaveLength(2));
    act(() => h.result.current.goPage(1));
    await waitFor(() => expect(h.result.current.rowOf(cards()[2]).state).toBe('ok'));
    act(() => h.result.current.goPage(0));
    await emit(quotes({ SYM3: qt(5.5, at(391)) }));
    expect(h.result.current.liveOf('SYM3')).toBeUndefined();
    const n = gets().length;
    act(() => h.result.current.goPage(1));
    await flush();
    expect(gets()).toHaveLength(n);
    const l3 = h.result.current.liveOf('SYM3');
    expect(l3).toBeDefined();
    expect(l3!.by['5m'][0].c).toBe(5.5);
  });

  it('NEGATIVE: a name dropped from the list loses its bucket on the next batch', async () => {
    const all = cards();
    const h = hook(base({ tiles: all }));
    await waitFor(() => expect(h.result.current.rowOf(all[0]).state).toBe('ok'));
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    expect(h.result.current.liveOf('SYM1')).toBeDefined();
    h.rerender(base({ tiles: all.slice(1) }));
    await emit(quotes({ SYM2: qt(4.2, at(391, 5)) }));
    h.rerender(base({ tiles: all }));
    await waitFor(() => expect(h.result.current.rowOf(all[0]).state).toBe('ok'));
    expect(h.result.current.liveOf('SYM1')).toBeUndefined();
  });

  it('NEGATIVE: a quotes batch (and a patched card) never recomputes the frame metas', async () => {
    const tiles = cards();
    const h = hook(base({ tiles }));
    await waitFor(() => expect(h.result.current.rowOf(tiles[1]).state).toBe('ok'));
    await flush();
    const n = metasCalls.n;
    await emit(quotes({ SYM1: qt(4.1, at(391)) }));
    h.rerender(base({ tiles: [{ ...tiles[0] }, ...tiles.slice(1)] }));
    await emit(quotes({ SYM1: qt(4.2, at(391, 9)) }));
    expect(metasCalls.n).toBe(n);
  });
});

describe('👀 ?focus= and the keys', () => {
  it('focus SYM5 at 2 per screen → SYM5 shown on the FIRST render that has the tiles', async () => {
    const seen: boolean[] = [];
    renderHook((p: P) => { const cw = useGgCardWatch(p); seen.push(cw.shown('SYM5')); return cw; },
      { initialProps: base({ focus: 'SYM5' }) });
    expect(seen[0]).toBe(true);
    await waitFor(() => expect(gets()).toEqual(['SYM5', 'SYM6']));
  });

  it('[C3] under <StrictMode>: SYM5 shown on BOTH dev renders of the first commit; the page settles once; a later refresh with the same focus leaves a moved page alone', async () => {
    const seen: Array<{ shown: boolean; page: number }> = [];
    const h = renderHook((p: P) => { const cw = useGgCardWatch(p); seen.push({ shown: cw.shown('SYM5'), page: cw.page }); return cw; },
      { initialProps: base({ focus: 'SYM5' }), wrapper: StrictMode });
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen[0]).toEqual({ shown: true, page: 2 });
    expect(seen[1]).toEqual({ shown: true, page: 2 });
    for (const s of seen) expect(s.page).toBe(2);
    act(() => h.result.current.goPage(0));
    expect(h.result.current.page).toBe(0);
    h.rerender(base({ focus: 'SYM5', tiles: cards(), boardSeq: 2 }));
    await flush();
    expect(h.result.current.page).toBe(0);
    expect(h.result.current.shown('SYM5')).toBe(false);
  });

  it('NEGATIVE: a focus not on the list → page 0, nothing moves', () => {
    const h = hook(base({ focus: 'ZZZZ' }));
    expect(h.result.current.page).toBe(0);
    expect(h.result.current.shown('SYM1')).toBe(true);
  });

  it('← → page the view; NEGATIVE: not inside an input, not while the ⤢ view is open', async () => {
    const h = hook();
    act(() => { fireEvent.keyDown(document, { key: 'ArrowRight' }); });
    expect(h.result.current.page).toBe(1);
    act(() => { fireEvent.keyDown(document, { key: 'ArrowLeft' }); });
    expect(h.result.current.page).toBe(0);
    const input = document.createElement('input');
    document.body.appendChild(input);
    act(() => { fireEvent.keyDown(input, { key: 'ArrowRight' }); });
    expect(h.result.current.page).toBe(0);
    input.remove();
    h.rerender(base({ stretched: true }));
    act(() => { fireEvent.keyDown(document, { key: 'ArrowRight' }); });
    expect(h.result.current.page).toBe(0);
  });

  it('the per-screen pick keeps the first shown card and is stored under ggc.layout', () => {
    const st = mem();
    vi.stubGlobal('localStorage', st);
    const h = hook();
    act(() => h.result.current.goPage(2));
    act(() => h.result.current.setLayout(1));
    expect(h.result.current.layout).toBe(1);
    expect(h.result.current.page).toBe(4);
    expect(st.getItem('ggc.layout')).toBe('1');
    expect(st.getItem('ggw.layout')).toBeNull();
  });
});

/* [C1] / [C5] the toggle under the SAME boardSeq — a harness that mounts the shell the way GgCardGridFrame does */
function Shell({ p, onCw }: { p: P; onCw: (cw: GgCardWatch) => void }) {
  const cw = useGgCardWatch(p);
  useEffect(() => { onCw(cw); });
  return (
    <div className="ggw-board" ref={cw.boardRef}>
      <div className="ggw-head" ref={cw.headRef} />
      {cw.active ? <div className="ggw-grid" ref={cw.gridRef} data-testid="g" /> : null}
    </div>
  );
}

describe('👀 the toggle OFF → ON under the same boardSeq', () => {
  it('[C1] re-measures: rowH a number and fit true after ON; NEGATIVE: OFF → rowH null, fit false', async () => {
    vi.spyOn(Element.prototype, 'getBoundingClientRect').mockImplementation(function (this: Element) {
      const top = this.classList.contains('ggw-board') ? 100 : 160;
      return { width: 1200, height: 10, top, left: 0, right: 1200, bottom: top + 10, x: 0, y: top, toJSON: () => ({}) } as DOMRect;
    });
    vi.stubGlobal('innerHeight', 900);
    let cw: GgCardWatch | null = null;
    render(<Shell p={base()} onCw={(c) => { cw = c; }} />);
    await waitFor(() => expect(cw!.rowH).not.toBeNull());
    expect(cw!.fit).toBe(true);
    act(() => cw!.toggle());
    await waitFor(() => expect(cw!.rowH).toBeNull());
    expect(cw!.fit).toBe(false);
    expect(cw!.active).toBe(false);
    act(() => cw!.toggle());
    await waitFor(() => expect(cw!.rowH).not.toBeNull());
    expect(typeof cw!.rowH).toBe('number');
    expect(cw!.fit).toBe(true);
  });

  it('[C5] OFF clears; ON again with the same boardSeq → exactly min(per screen, n) GETs; within one span page 2 → 1 → 0', async () => {
    let cw: GgCardWatch | null = null;
    render(<Shell p={base()} onCw={(c) => { cw = c; }} />);
    await waitFor(() => expect(gets()).toHaveLength(2));
    act(() => cw!.toggle());
    await flush();
    expect(gets()).toHaveLength(2);
    expect(cw!.rowOf(cards()[0]).state).toBe('loading');
    act(() => cw!.toggle());
    await waitFor(() => expect(gets()).toHaveLength(4));
    expect(gets().slice(2)).toEqual(['SYM1', 'SYM2']);
    act(() => cw!.goPage(1));
    await waitFor(() => expect(gets()).toHaveLength(6));
    act(() => cw!.goPage(0));
    await flush();
    expect(gets()).toHaveLength(6);
  });
});
