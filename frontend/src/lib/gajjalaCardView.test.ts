/* 🚩 Gajjala card → ⤢ three-chart view — the lib (2026-11-16, ggcard3 spec §3.2 / §4 WP-A).
 * Ajay 2026-11-16: "...default its 3 chart extension with 1 min, 3 min and 5 mins" → "Actually instead of 3 mins make it
 * 15 mins timeframe". NEGATIVES: the Watch's order is untouched (no 15m inserted); the card order carries no 3m;
 * parseFrame keeps the three optional keys ONLY when served (absent → undefined, never null / false); junk answers are
 * rejected; markers only on the frame the card drew. */
import { describe, expect, it } from 'vitest';
import fixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import type { GgTile } from './gajjala';
import {
  GGC_FETCH_FAILED, GGC_PATH, GGC_STRETCH_ORDER, ggcPath, ggcRow, parseGgc, type GgcPayload,
} from './gajjalaCardView';
import { GGW_STRETCH_ORDER, ggwStretchFrames, parseFrame, type GgwFrame } from './gajjalaWatch';

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
  it('NEGATIVE: ggwStretchFrames(frames) is still the Watch 5m / 3m / 1m — no 15m inserted', () => {
    expect(GGW_STRETCH_ORDER).toEqual(['5m', '3m', '1m']);
    expect(ggwStretchFrames([f('1m'), f('3m'), f('5m')]).map((x) => x.tf)).toEqual(['5m', '3m', '1m']);
    expect(ggwStretchFrames([f('1m'), f('15m'), f('5m')]).map((x) => x.tf)).toEqual(['5m', '1m', '15m']);
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
