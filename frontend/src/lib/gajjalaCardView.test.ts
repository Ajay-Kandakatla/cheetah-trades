/* 🚩 Gajjala card → ⤢ three-chart view — the lib (2026-11-16, ggcard3 spec §3.2 / §4 WP-A).
 * Ajay 2026-11-16: "...default its 3 chart extension with 1 min, 3 min and 5 mins" → "Actually instead of 3 mins make it
 * 15 mins timeframe". NEGATIVES: the Watch's order is untouched (no 15m inserted); the card order carries no 3m;
 * parseFrame keeps the three optional keys ONLY when served (absent → undefined, never null / false); junk answers are
 * rejected; markers only on the frame the card drew. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import type { GgTile } from './gajjala';
import {
  GGC_FETCH_FAILED, GGC_FRAME_MIN_PX, GGC_LAYOUT_KEY, GGC_NO_FRAMES, GGC_PATH, GGC_STRETCH_ORDER, GGC_WATCH_DEFAULT_ON,
  GGC_WATCH_LABEL, GGC_WATCH_LS, GGC_WATCH_TITLE, GGC_WATCH_VKEYS, ggcPath, ggcRow, ggcShown, loadGgcWatch, parseGgc,
  readGgcLayout, saveGgcLayout, saveGgcWatch, type GgcPayload,
} from './gajjalaCardView';
import { GG_VIDEO_LOOK_VKEYS } from './gajjala';
import { GGW_LAYOUT_DEFAULT, GGW_LAYOUT_KEY, GGW_STRETCH_ORDER, ggwStretchFrames, parseFrame, type GgwFrame } from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const f = (tf: string) => ({ tf } as unknown as GgwFrame);
/** OMH's served frames relabelled 15m / 5m / 1m (the fixture is never edited). */
function servedFrames(extra: (fr: any) => void = () => {}): any[] {
  const fr = clone((fixture as any).rows[0].frames) as any[];
  for (const x of fr) { if (x.tf === '3m') x.tf = '15m'; extra(x); }
  return fr;
}
function rawAnswer(over: Record<string, unknown> = {}): any {
  return {
    state: 'ok', symbol: 'OMH', session: '2026-11-13', is_today: true, in_window: true, as_of_et: '09:41', stale: false,
    text: null, frames: servedFrames((x) => { x.as_of_et = '09:41'; x.stale = false; x.empty_text = null; }), ...over,
  };
}

describe('🚩 the routes and the order', () => {
  it('GGC_PATH and ggcPath (trimmed, encoded)', () => {
    expect(GGC_PATH).toBe('/chart-maps/gajjala/frames');
    expect(ggcPath(' OMH ')).toBe('/chart-maps/gajjala/frames/OMH');
    expect(ggcPath('BRK.B')).toBe('/chart-maps/gajjala/frames/BRK.B');
    expect(ggcPath('A/B')).toBe('/chart-maps/gajjala/frames/A%2FB');
    expect(GGC_FETCH_FAILED).toBe('Could not load the three charts.');
  });
  // 2026-11-23 (vwapzones §3.9): the Watch's own order is now the card's 15 / 5 / 1 — equal, and no 3m in either.
  it('ggwStretchFrames(frames) is the Watch 15m / 5m / 1m == GGC_STRETCH_ORDER; NEGATIVE: no 3m named', () => {
    expect(GGW_STRETCH_ORDER).toEqual(['15m', '5m', '1m']);
    expect([...GGW_STRETCH_ORDER]).toEqual([...GGC_STRETCH_ORDER]);
    expect(GGW_STRETCH_ORDER as ReadonlyArray<string>).not.toContain('3m');
    expect(ggwStretchFrames([f('1m'), f('15m'), f('5m')]).map((x) => x.tf)).toEqual(['15m', '5m', '1m']);
  });
  it('ggwStretchFrames(frames, GGC_STRETCH_ORDER) = 15m / 5m / 1m; NEGATIVE: the order names no 3m', () => {
    expect(GGC_STRETCH_ORDER).toEqual(['15m', '5m', '1m']);
    expect(GGC_STRETCH_ORDER as ReadonlyArray<string>).not.toContain('3m');
    expect(ggwStretchFrames([f('1m'), f('5m'), f('15m')], GGC_STRETCH_ORDER).map((x) => x.tf)).toEqual(['15m', '5m', '1m']);
    expect(ggwStretchFrames([f('3m'), f('1m'), f('15m')], GGC_STRETCH_ORDER).map((x) => x.tf)).toEqual(['15m', '1m', '3m']);
  });
});

describe('🚩 parseFrame — the optional keys only when served', () => {
  it('served as_of_et / stale / empty_text are kept', () => {
    const raw = servedFrames()[0];
    Object.assign(raw, { as_of_et: '09:41', stale: true, empty_text: 'No 1-minute bars stored for OMH this session yet' });
    const p = parseFrame(raw, 'OMH')!;
    expect(p.as_of_et).toBe('09:41');
    expect(p.stale).toBe(true);
    expect(p.empty_text).toBe('No 1-minute bars stored for OMH this session yet');
  });
  it('served null / false stay null / false; junk stale → false', () => {
    const raw = servedFrames()[0];
    Object.assign(raw, { as_of_et: null, stale: false, empty_text: null });
    const p = parseFrame(raw, 'OMH')!;
    expect(p.as_of_et).toBeNull();
    expect(p.stale).toBe(false);
    expect(p.empty_text).toBeNull();
    expect(parseFrame({ ...raw, stale: 'yes' }, 'OMH')!.stale).toBe(false);
  });
  it('NEGATIVE: absent → undefined (the key is not there at all), never null / false', () => {
    const p = parseFrame(servedFrames()[0], 'OMH')!;
    for (const k of ['as_of_et', 'stale', 'empty_text']) expect(k in p, k).toBe(false);
    expect(p.as_of_et).toBeUndefined();
    expect(p.stale).toBeUndefined();
  });
});

describe('🚩 parseGgc', () => {
  it('reads an ok answer: three frames in served order, stale, stamps', () => {
    const p = parseGgc(rawAnswer({ stale: true })) as GgcPayload;
    expect(p.state).toBe('ok');
    expect(p.symbol).toBe('OMH');
    expect(p.stale).toBe(true);
    expect(p.as_of_et).toBe('09:41');
    expect(p.is_today).toBe(true);
    expect(p.frames.map((x) => x.tf)).toEqual(['1m', '15m', '5m']);
    expect(p.frames.every((x) => x.as_of_et === '09:41' && x.stale === false)).toBe(true);
  });
  it('a served error → its reason verbatim', () => {
    expect(parseGgc({ state: 'error', reason: 'KeyError' })).toEqual({ state: 'error', reason: 'KeyError' });
    expect(parseGgc({ state: 'error' })).toEqual({ state: 'error', reason: null });
  });
  it('NEGATIVE: junk, a missing frames list, no symbol, another state → null; junk frames dropped', () => {
    for (const junk of [null, undefined, 7, 'x', [], {}, { state: 'ok' }, { detail: 'Not a ticker' },
      rawAnswer({ frames: undefined }), rawAnswer({ frames: 'x' }), rawAnswer({ symbol: '' }), rawAnswer({ state: 'bad_symbol' })]) {
      expect(parseGgc(junk)).toBeNull();
    }
    const p = parseGgc(rawAnswer({ frames: [null, { tf: '' }, ...servedFrames()] })) as GgcPayload;
    expect(p.frames).toHaveLength(3);
  });
  it('NEGATIVE: stale is true only when served true', () => {
    expect((parseGgc(rawAnswer({ stale: 'true' })) as GgcPayload).stale).toBe(false);
    expect((parseGgc(rawAnswer({ stale: undefined })) as GgcPayload).stale).toBe(false);
  });
});

describe('🚩 ggcRow — the open card\'s plan on the served frames', () => {
  const card = (over: Partial<GgTile> = {}): GgTile => ({
    symbol: 'OMH', href: '/sepa/OMH?tab=supply&tf=5m_today', bars: [], stats: [], why: '',
    lines: [{ label: 'trigger', price: 4.2 } as any], bands: [{ lo: 3.9, hi: 4.0 } as any],
    markers: [{ date: '2026-11-13 09:35', kind: 'aplus' } as any],
    tf: '5m', gajjala: { plan_text: 'trigger 4.20 · stop 3.90 · risk 7.1%' } as any, ...over,
  } as GgTile);
  const pay = (over: Record<string, unknown> = {}) => parseGgc(rawAnswer(over)) as GgcPayload;

  it('lines and bands on all three frames; markers ONLY on the tf the card drew', () => {
    const c = card();
    const row = ggcRow(c, pay());
    expect(row.frames).toHaveLength(3);
    for (const fr of row.frames) {
      expect(fr.tile.lines).toBe(c.lines);
      expect(fr.tile.bands).toBe(c.bands);
    }
    expect(row.frames.find((x) => x.tf === '5m')!.tile.markers).toBe(c.markers);
  });
  it('NEGATIVE: the other frames carry markers: []; a card with no tf → markers nowhere', () => {
    const row = ggcRow(card(), pay());
    expect(row.frames.find((x) => x.tf === '15m')!.tile.markers).toEqual([]);
    expect(row.frames.find((x) => x.tf === '1m')!.tile.markers).toEqual([]);
    const none = ggcRow(card({ tf: null }), pay());
    for (const fr of none.frames) expect(fr.tile.markers).toEqual([]);
  });
  it('the served bars, axis and stamps pass through untouched', () => {
    const p = pay();
    const row = ggcRow(card(), p);
    row.frames.forEach((fr, i) => {
      expect(fr.tile.bars).toBe(p.frames[i].tile.bars);
      expect(fr.axis).toBe(p.frames[i].axis);
      expect(fr.as_of_et).toBe('09:41');
    });
    expect(row.rang).toEqual([]);
    expect(row.symbol).toBe('OMH');
  });
  it('text precedence: served text > plan_text > null; state no_bars only with served text', () => {
    expect(ggcRow(card(), pay({ text: 'No bars stored for OMH this session yet' })).text)
      .toBe('No bars stored for OMH this session yet');
    expect(ggcRow(card(), pay({ text: 'No bars stored for OMH this session yet' })).state).toBe('no_bars');
    expect(ggcRow(card(), pay()).text).toBe('trigger 4.20 · stop 3.90 · risk 7.1%');
    expect(ggcRow(card(), pay()).state).toBe('ok');
    expect(ggcRow(card({ gajjala: null }), pay()).text).toBeNull();
    expect(ggcRow(card({ gajjala: { plan_text: null } as any }), pay()).text).toBeNull();
  });
  it('stale + stamp passthrough; from_session only when not today', () => {
    const row = ggcRow(card(), pay({ stale: true, as_of_et: '08:02' }));
    expect(row.stale).toBe(true);
    expect(row.as_of_et).toBe('08:02');
    expect(row.from_session).toBeNull();
    expect(ggcRow(card(), pay({ is_today: false })).from_session).toBe('2026-11-13');
    expect(ggcRow(card(), pay()).stale).toBe(false);
  });
});

/* 📺 2026-11-17 (video view spec §3.4 / WP-D). Ajay 11-16: "the graphs in the videos are so clear like I can easily identify
 * the trend"; 11-17 "Yes to all defaults" → his call #4: inside 📺 hide the 🧪 entry band and the ➖ diamonds, keep the A+ tag,
 * trigger / stop and the now line. The ⤢ view strips through the SAME videoLayers the cards use. NEGATIVES: no look → the
 * card's own references (byte-identical rows); the card is never mutated; bars / axis / stamps / text are untouched. */
describe('📺 ggcRow(card, p, \'video\') — the overlay stripped like the cards', () => {
  const mixed = (over: Partial<GgTile> = {}): GgTile => ({
    symbol: 'OMH', href: '/sepa/OMH?tab=supply&tf=5m_today', bars: [], stats: [], why: '', tf: '5m',
    lines: [
      { label: 'TRIGGER 4.20', price: 4.2, tone: 'buy' }, { label: 'STOP 3.90', price: 3.9, tone: 'stop' },
      { label: 'now', price: 4.0, tone: 'now' }, { label: 'TARGET 4.80', price: 4.8, tone: 'target' },
      { label: '9 EMA', price: 4.05, tone: 'neutral' },
    ] as any,
    bands: [{ kind: 'gg_entry', lo: 3.95, hi: 4.05, label: '🧪 entry' }] as any,
    markers: [
      { date: '2026-11-13 09:35', kind: 'buy', label: 'A+' }, { date: '2026-11-13 09:40', kind: 'ema_cross_up' },
      { date: '2026-11-13 09:45', kind: 'ema_cross_dn' }, { date: '2026-11-13 09:50', kind: 'sweep', label: 'sw' },
    ] as any,
    gajjala: { plan_text: 'trigger 4.20 · stop 3.90 · risk 7.1%' } as any, ...over,
  } as GgTile);
  const pay = (over: Record<string, unknown> = {}) => parseGgc(rawAnswer(over)) as GgcPayload;

  it('every frame: bands [], lines only buy / stop / now, markers only kind buy and only on the card\'s tf', () => {
    const row = ggcRow(mixed(), pay(), 'video');
    expect(row.frames).toHaveLength(3);
    for (const fr of row.frames) {
      expect(fr.tile.bands).toEqual([]);
      expect((fr.tile.lines || []).map((l) => l.tone)).toEqual(['buy', 'stop', 'now']);
      for (const m of fr.tile.markers || []) expect(m.kind).toBe('buy');
    }
    expect(row.frames.find((x) => x.tf === '5m')!.tile.markers).toEqual([{ date: '2026-11-13 09:35', kind: 'buy', label: 'A+' }]);
    expect(row.frames.find((x) => x.tf === '15m')!.tile.markers).toEqual([]);
    expect(row.frames.find((x) => x.tf === '1m')!.tile.markers).toEqual([]);
  });

  it('NEGATIVE: a card with no tf → no markers on any frame under the look either', () => {
    for (const fr of ggcRow(mixed({ tf: null }), pay(), 'video').frames) expect(fr.tile.markers).toEqual([]);
  });

  it('NEGATIVE: no look (absent or undefined) → the card\'s OWN lines / bands / markers references, today\'s rows', () => {
    const c = mixed();
    for (const row of [ggcRow(c, pay()), ggcRow(c, pay(), undefined)]) {
      for (const fr of row.frames) {
        expect(fr.tile.lines).toBe(c.lines);
        expect(fr.tile.bands).toBe(c.bands);
      }
      expect(row.frames.find((x) => x.tf === '5m')!.tile.markers).toBe(c.markers);
    }
    const p = pay();
    expect(JSON.stringify(ggcRow(c, p, undefined))).toBe(JSON.stringify(ggcRow(c, p)));
  });

  it('NEGATIVE: the card is never mutated by the look', () => {
    const c = mixed();
    const before = clone(c);
    ggcRow(c, pay(), 'video');
    expect(c).toEqual(before);
    expect(c.bands).toHaveLength(1);
    expect(c.markers).toHaveLength(4);
  });

  it('NEGATIVE: bars, axis, stamps, text and state are the same with and without the look', () => {
    const p = pay({ stale: true, as_of_et: '08:02', is_today: false });
    const plain = ggcRow(mixed(), p);
    const video = ggcRow(mixed(), p, 'video');
    expect(video.text).toBe(plain.text);
    expect(video.state).toBe(plain.state);
    expect(video.stale).toBe(true);
    expect(video.as_of_et).toBe('08:02');
    expect(video.from_session).toBe(plain.from_session);
    video.frames.forEach((fr, i) => {
      expect(fr.tf).toBe(plain.frames[i].tf);
      expect(fr.tile.bars).toBe(p.frames[i].tile.bars);
      expect(fr.tile.curves).toBe(p.frames[i].tile.curves);
      expect(fr.axis).toBe(p.frames[i].axis);
    });
  });
});

/* 👀 2026-11-18 — the card grid in the Watch layout (spec cardview §3.1 / §4 WP-B). Ajay: "I need the watch list kinda chart
 * formant view video view as default here too from the tabs pages". NEGATIVES: a non-'1' value reads OFF; a blocked / absent
 * store reads the default and never throws; the 1-min page and Luk never draw it; the pick never reads the Watch's own key;
 * ggcRow with no opts is the 11-17 row; ggcShown never shows a name gone from the list. */
function memStore(seed: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(seed));
  const touched = new Set<string>();
  return {
    touched,
    getItem: (k: string) => { touched.add(k); return m.has(k) ? m.get(k)! : null; },
    setItem: (k: string, v: string) => { touched.add(k); m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    peek: (k: string) => (m.has(k) ? m.get(k)! : null),
  };
}
const blockedStore = () => ({
  getItem: () => { throw new Error('blocked'); },
  setItem: () => { throw new Error('blocked'); },
  removeItem: () => undefined, clear: () => undefined,
});

describe('👀 loadGgcWatch / saveGgcWatch — default ON, strict "1"', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  it('absent → ON (the default); "1" → ON; "0" → OFF', () => {
    const st = memStore();
    vi.stubGlobal('localStorage', st);
    expect(GGC_WATCH_LS).toBe('gg-card-watch');
    expect(GGC_WATCH_DEFAULT_ON).toBe(true);
    expect(loadGgcWatch()).toBe(true);
    st.setItem(GGC_WATCH_LS, '1');
    expect(loadGgcWatch()).toBe(true);
    st.setItem(GGC_WATCH_LS, '0');
    expect(loadGgcWatch()).toBe(false);
  });
  it('NEGATIVE: any stored value that is not "1" reads OFF ("true", "on", " 1", "")', () => {
    const st = memStore();
    vi.stubGlobal('localStorage', st);
    for (const v of ['true', 'on', ' 1', '1 ', '', 'watch']) {
      st.setItem(GGC_WATCH_LS, v);
      expect(loadGgcWatch()).toBe(false);
    }
  });
  it('saveGgcWatch writes "1" / "0"; load + save touch ONLY gg-card-watch', () => {
    const st = memStore();
    vi.stubGlobal('localStorage', st);
    saveGgcWatch(false);
    expect(st.peek(GGC_WATCH_LS)).toBe('0');
    saveGgcWatch(true);
    expect(st.peek(GGC_WATCH_LS)).toBe('1');
    loadGgcWatch();
    expect([...st.touched]).toEqual(['gg-card-watch']);
  });
  it('NEGATIVE: a throwing store → ON and a save never throws; no storage at all → ON', () => {
    vi.stubGlobal('localStorage', blockedStore());
    expect(loadGgcWatch()).toBe(true);
    expect(() => saveGgcWatch(false)).not.toThrow();
    vi.stubGlobal('localStorage', undefined);
    expect(loadGgcWatch()).toBe(true);
    expect(() => saveGgcWatch(true)).not.toThrow();
  });
});

describe('👀 GGC_WATCH_VKEYS — the 🚩 5-min tab and 🧪 Audited only', () => {
  it('deep-equals GG_VIDEO_LOOK_VKEYS', () => {
    expect([...GGC_WATCH_VKEYS]).toEqual([...GG_VIDEO_LOOK_VKEYS]);
    expect([...GGC_WATCH_VKEYS]).toEqual(['gajjala', 'gajjala_audited']);
  });
  it('NEGATIVE: never the retired 1-minute page, never Luk', () => {
    expect(GGC_WATCH_VKEYS).not.toContain('gajjala_1m');
    expect(GGC_WATCH_VKEYS).not.toContain('luk');
  });
});

describe('👀 readGgcLayout / saveGgcLayout — its own key, the Watch parser', () => {
  afterEach(() => { vi.unstubAllGlobals(); });
  it('absent / junk / blocked → GGW_LAYOUT_DEFAULT (2); "9" → 9; "1" → 1; "4" → 4', () => {
    expect(GGC_LAYOUT_KEY).toBe('ggc.layout');
    const st = memStore();
    vi.stubGlobal('localStorage', st);
    expect(readGgcLayout()).toBe(GGW_LAYOUT_DEFAULT);
    expect(GGW_LAYOUT_DEFAULT).toBe(2);
    for (const [v, want] of [['9', 9], ['1', 1], ['4', 4], ['3', 2], ['junk', 2], ['', 2]] as const) {
      st.setItem(GGC_LAYOUT_KEY, v);
      expect(readGgcLayout()).toBe(want);
    }
    vi.stubGlobal('localStorage', blockedStore());
    expect(readGgcLayout()).toBe(2);
    expect(() => saveGgcLayout(4)).not.toThrow();
  });
  it('NEGATIVE: never reads or writes the Watch\'s ggw.layout (seed ggw.layout=9 → still 2)', () => {
    const st = memStore({ [GGW_LAYOUT_KEY]: '9' });
    vi.stubGlobal('localStorage', st);
    expect(readGgcLayout()).toBe(2);
    saveGgcLayout(4);
    expect(st.peek(GGC_LAYOUT_KEY)).toBe('4');
    expect(st.peek(GGW_LAYOUT_KEY)).toBe('9');
    expect([...st.touched]).toEqual(['ggc.layout']);
  });
});

describe('👀 the control words and the frame floor', () => {
  it('label + title are FE control words; no b-word', () => {
    expect(GGC_WATCH_LABEL).toBe('👀 Watch layout');
    expect(GGC_WATCH_TITLE).toContain('2 per screen');
    expect(`${GGC_WATCH_LABEL} ${GGC_WATCH_TITLE}`.toLowerCase()).not.toContain('bounce');
    expect(GGC_FRAME_MIN_PX).toBe(160);
  });
  it('GGC_NO_FRAMES is the frame-less row part', () => {
    expect(GGC_NO_FRAMES).toEqual({ from_session: null, as_of_et: null, stale: false, frames: [], rang: [] });
  });
});

describe('👀 ggcRow(card, p, look, { plan: false }) — the board tile head', () => {
  const tile = (over: Partial<GgTile> = {}): GgTile => ({
    symbol: 'OMH', href: '/sepa/OMH', bars: [], stats: [], why: '', tf: '5m',
    lines: [{ label: 'TRIGGER 4.20', price: 4.2, tone: 'buy' }] as any,
    bands: [{ kind: 'gg_entry', lo: 3.95, hi: 4.05, label: 'entry' }] as any,
    markers: [{ date: '2026-11-13 09:35', kind: 'buy', label: 'A+' }] as any,
    gajjala: { plan_text: 'trigger 4.20 · stop 3.90 · risk 7.1%' } as any, ...over,
  } as GgTile);
  const pay = (over: Record<string, unknown> = {}) => parseGgc(rawAnswer(over)) as GgcPayload;

  it('head text = the served text ONLY (the plan prints once, below); frames identical to the no-opts row', () => {
    const c = tile();
    const p = pay();
    const a = ggcRow(c, p, undefined, { plan: false });
    const b = ggcRow(c, p);
    expect(a.text).toBeNull();
    expect(b.text).toBe('trigger 4.20 · stop 3.90 · risk 7.1%');
    expect(JSON.stringify(a.frames)).toBe(JSON.stringify(b.frames));
    const v1 = ggcRow(c, p, 'video', { plan: false });
    const v2 = ggcRow(c, p, 'video');
    expect(JSON.stringify(v1.frames)).toBe(JSON.stringify(v2.frames));
    const words = pay({ text: 'No bars stored for OMH this session yet' });
    expect(ggcRow(c, words, undefined, { plan: false }).text).toBe('No bars stored for OMH this session yet');
    expect(ggcRow(c, words, undefined, { plan: false }).state).toBe('no_bars');
  });
  it('NEGATIVE: no opts / { plan: true } / {} → byte-identical to the 11-17 row', () => {
    const c = tile();
    const p = pay();
    const base = JSON.stringify(ggcRow(c, p));
    expect(JSON.stringify(ggcRow(c, p, undefined, {}))).toBe(base);
    expect(JSON.stringify(ggcRow(c, p, undefined, { plan: true }))).toBe(base);
    expect(JSON.stringify(ggcRow(c, p, undefined, undefined))).toBe(base);
  });
});

describe('👀 ggcShown — pages, pick, all', () => {
  const S = ['A', 'B', 'C', 'D', 'E'];
  it('pages of 2: page 0 → A B; page 1 → C D; page 2 → E; a page past the end clamps to the last', () => {
    expect([...ggcShown(S, 0, 2, null)]).toEqual(['A', 'B']);
    expect([...ggcShown(S, 1, 2, null)]).toEqual(['C', 'D']);
    expect([...ggcShown(S, 2, 2, null)]).toEqual(['E']);
    expect([...ggcShown(S, 9, 2, null)]).toEqual(['E']);
    expect([...ggcShown(S, -1, 2, null)]).toEqual(['A', 'B']);
  });
  it('size Infinity (the phone without a pager) → all', () => {
    expect([...ggcShown(S, 3, Infinity, ['B'])]).toEqual(S);
  });
  it('a pick → the pick, whatever the page', () => {
    expect([...ggcShown(S, 0, 2, ['D', 'E'])]).toEqual(['D', 'E']);
  });
  it('NEGATIVE: a pick whose names left the list → only the names still listed; none left → the page', () => {
    expect([...ggcShown(S, 0, 2, ['E', 'ZZZ'])]).toEqual(['E']);
    expect([...ggcShown(S, 1, 2, ['ZZZ'])]).toEqual(['C', 'D']);
    expect([...ggcShown(S, 0, 2, [])]).toEqual(['A', 'B']);
  });
  it('NEGATIVE: an empty list shows nothing', () => {
    expect(ggcShown([], 0, 2, null).size).toBe(0);
  });
});
