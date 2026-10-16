import { describe, it, expect } from 'vitest';
import {
  CARD_LIVE_CLOSED_MS, CARD_LIVE_MS, CARD_LIVE_PATH, cardLiveSymbols, nextCadence, parseCardLive,
  patchTile, patchTiles, type CardLiveAnswer, type CardLiveQuote,
} from './cardLive';
import type { CmBar, CmTile } from './chartMaps';

/* lib/cardLive — the splice of POST /chart-maps/live into the board's tiles
 * (BUILD_SPEC8 §3.5 + AMENDMENTS8 C4). Shapes follow the frozen §3.3 answer.
 * NEGATIVES: an older / foreign-session / invalid served bar never touches the
 * bars; an invalid now block never touches the lines; nothing changed → the
 * SAME object back (identity drives PatternChart's memo). */

const LABELS = ['now', 'now · pre', 'now · AH'];

const bar = (t: string, c: number, extra: Partial<CmBar> = {}): CmBar =>
  ({ t, o: c - 0.1, h: c + 0.2, l: c - 0.3, c, v: 1000, ...extra });

const tile = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'XLAB', href: '/sepa/XLAB', why: '', bands: [], markers: [], stats: [],
  bars: [bar('2026-10-14', 1.3), bar('2026-10-15', 1.36), bar('2026-10-16', 2.64)],
  lines: [
    { price: 2.64, label: 'now', tone: 'now' },
    { price: 3.1, label: 'TARGET', tone: 'target' },
    { price: 1.2, label: 'STOP', tone: 'stop' },
  ],
  ...over,
});

const SERVED: CmBar = { t: '2026-10-16', o: 1.41, h: 2.95, l: 1.38, c: 2.77, v: 51234567.0 };
const NOW = { price: 2.77, label: 'now', session: null, add_line: false, as_of_epoch: 1792170940.5, as_of: 'x' };
const quote = (over: Partial<CardLiveQuote> = {}): CardLiveQuote =>
  ({ bar: SERVED, prev_t: '2026-10-15', now: NOW, ...over });

const answer = (quotes: Record<string, CardLiveQuote>): CardLiveAnswer => ({
  session: 'rth', as_of_epoch: 1792170942.1, as_of: 'a', footer: { live: 'L', stale: 'S' },
  now_labels: LABELS, cap: 250, asked: 1, served: 1, missing: [], fault: null, quotes,
});

describe('constants', () => {
  it('cadence and path', () => {
    expect(CARD_LIVE_MS).toBe(30_000);
    expect(CARD_LIVE_CLOSED_MS).toBe(30 * 60_000);
    expect(CARD_LIVE_PATH).toBe('/chart-maps/live');
  });
});

describe('patchTile — bars', () => {
  it('same date → the last bar is replaced, the other bars identity-equal', () => {
    const t = tile();
    const p = patchTile(t, quote(), LABELS);
    expect(p).not.toBe(t);
    expect(p.bars.length).toBe(3);
    expect(p.bars[2]).toEqual(SERVED);
    expect(p.bars[0]).toBe(t.bars[0]);
    expect(p.bars[1]).toBe(t.bars[1]);
  });

  it('identical bar and line → the SAME tile', () => {
    const t = tile({
      bars: [bar('2026-10-15', 1.36), { ...SERVED }],
      lines: [{ price: 2.77, label: 'now', tone: 'now' }],
    });
    expect(patchTile(t, quote(), LABELS)).toBe(t);
  });

  it('append only when prev_t === the last bar date; the first bar is kept', () => {
    const t = tile({ bars: [bar('2026-10-14', 1.3), bar('2026-10-15', 1.36)] });
    const p = patchTile(t, quote({ prev_t: '2026-10-15' }), LABELS);
    expect(p.bars.length).toBe(3);
    expect(p.bars[0]).toBe(t.bars[0]);
    expect(p.bars[1]).toBe(t.bars[1]);
    expect(p.bars[2]).toEqual(SERVED);
  });

  it('C4: append with prev_bar → the card\'s last bar is replaced by the closed bar (loses its s tag), then today appended', () => {
    const t = tile({ bars: [bar('2026-10-14', 1.3), bar('2026-10-15', 1.5, { s: 'ah' })] });
    const prev = bar('2026-10-15', 1.36);
    const pre: CmBar = { t: '2026-10-16', o: 1.41, h: 1.45, l: 1.41, c: 1.45, v: 0, s: 'pre' };
    const p = patchTile(t, quote({ bar: pre, prev_bar: prev }), LABELS);
    expect(p.bars.length).toBe(3);
    expect(p.bars[0]).toBe(t.bars[0]);
    expect(p.bars[1]).toEqual(prev);
    expect('s' in p.bars[1]).toBe(false);
    expect(p.bars[1]).not.toBe(t.bars[1]);
    expect(p.bars[2]).toEqual(pre);
  });

  it('NEGATIVE C4: a prev_bar of another date or an invalid one is not spliced (append only)', () => {
    const t = tile({ bars: [bar('2026-10-14', 1.3), bar('2026-10-15', 1.5, { s: 'ah' })] });
    for (const prev of [bar('2026-10-13', 1.36), { ...bar('2026-10-15', 1.36), c: NaN }]) {
      const p = patchTile(t, quote({ prev_bar: prev }), LABELS);
      expect(p.bars.length).toBe(3);
      expect(p.bars[1]).toBe(t.bars[1]);
    }
  });

  it('NEGATIVE newer bar but prev_t !== the last bar date (a Winners window) → bars unchanged', () => {
    const t = tile({ bars: [bar('2026-03-02', 10), bar('2026-03-03', 11)], lines: [] });
    expect(patchTile(t, quote({ prev_t: '2026-10-15' }), LABELS)).toBe(t);
    expect(patchTile(t, quote({ prev_t: null }), LABELS)).toBe(t);
  });

  it('NEGATIVE an older served bar → identity', () => {
    const t = tile({ lines: [] });
    expect(patchTile(t, quote({ bar: { ...SERVED, t: '2026-10-15' }, now: null }), LABELS).bars).toBe(t.bars);
    expect(patchTile(t, quote({ bar: { ...SERVED, t: '2026-10-09' }, now: null }), LABELS)).toBe(t);
  });

  it('NEGATIVE an intraday tile (last t carries a time) → bars unchanged', () => {
    const t = tile({ bars: [bar('2026-10-16 10:30', 2.6), bar('2026-10-16 10:35', 2.64)], lines: [] });
    expect(patchTile(t, quote(), LABELS)).toBe(t);
  });

  it('NEGATIVE an invalid served bar (NaN / 0 / negative / missing / s "x" / bad date) → bars unchanged', () => {
    const t = tile({ lines: [] });
    const bad: unknown[] = [
      { ...SERVED, c: NaN }, { ...SERVED, o: 0 }, { ...SERVED, l: -1 }, { ...SERVED, v: -5 },
      { ...SERVED, v: Infinity }, { t: '2026-10-16', o: 1, h: 2, l: 1 }, { ...SERVED, s: 'x' },
      { ...SERVED, t: '10/16/2026' }, { ...SERVED, h: null }, null,
    ];
    for (const b of bad) {
      expect(patchTile(t, quote({ bar: b as CmBar, now: null }), LABELS)).toBe(t);
    }
  });

  it('an empty bar list is never patched', () => {
    const t = tile({ bars: [], lines: [] });
    expect(patchTile(t, quote(), LABELS)).toBe(t);
  });
});

describe('patchTile — lines', () => {
  it('moves the now line and keeps target / stop identity-equal', () => {
    const t = tile();
    const p = patchTile(t, quote({ bar: null }), LABELS);
    expect(p.bars).toBe(t.bars);
    expect(p.lines[0]).toEqual({ price: 2.77, label: 'now', tone: 'now' });
    expect(p.lines[1]).toBe(t.lines[1]);
    expect(p.lines[2]).toBe(t.lines[2]);
  });

  it('"now" → served "now · pre"; "now · pre" → served "now" at the open', () => {
    const t1 = tile();
    const p1 = patchTile(t1, quote({ bar: null, now: { ...NOW, label: 'now · pre', session: 'premarket' } }), LABELS);
    expect(p1.lines[0].label).toBe('now · pre');
    const t2 = tile({ lines: [{ price: 2.5, label: 'now · pre', tone: 'now' }] });
    const p2 = patchTile(t2, quote({ bar: null }), LABELS);
    expect(p2.lines[0]).toEqual({ price: 2.77, label: 'now', tone: 'now' });
  });

  it('a custom label ("LAST · PRE") is kept; only the price moves', () => {
    const t = tile({ lines: [{ price: 2.5, label: 'LAST · PRE', tone: 'now' }] });
    const p = patchTile(t, quote({ bar: null, now: { ...NOW, label: 'now · pre' } }), LABELS);
    expect(p.lines[0]).toEqual({ price: 2.77, label: 'LAST · PRE', tone: 'now' });
  });

  it('no now line + add_line → one served line is added', () => {
    const t = tile({ lines: [{ price: 3.1, label: 'TARGET', tone: 'target' }] });
    const p = patchTile(t, quote({ bar: null, now: { ...NOW, label: 'now · AH', add_line: true } }), LABELS);
    expect(p.lines.length).toBe(2);
    expect(p.lines[0]).toBe(t.lines[0]);
    expect(p.lines[1]).toEqual({ price: 2.77, label: 'now · AH', tone: 'now' });
  });

  it('NEGATIVE no now line + !add_line → none added', () => {
    const t = tile({ lines: [{ price: 3.1, label: 'TARGET', tone: 'target' }] });
    expect(patchTile(t, quote({ bar: null }), LABELS)).toBe(t);
  });

  it('NEGATIVE now.price NaN / 0 / null or label "" → lines unchanged', () => {
    const t = tile();
    for (const now of [{ ...NOW, price: NaN }, { ...NOW, price: 0 }, { ...NOW, price: null },
      { ...NOW, label: '' }, { ...NOW, label: null }]) {
      expect(patchTile(t, quote({ bar: null, now: now as any }), LABELS)).toBe(t);
    }
  });

  it('NEGATIVE no quote → identity', () => {
    const t = tile();
    expect(patchTile(t, undefined, LABELS)).toBe(t);
  });
});

describe('patchTiles', () => {
  it('null answer and an all-unchanged answer → the SAME array', () => {
    const tiles = [tile({ symbol: 'AAA' }), tile({ symbol: 'BBB' })];
    expect(patchTiles(tiles, null)).toBe(tiles);
    expect(patchTiles(tiles, answer({ ZZZ: quote() }))).toBe(tiles);
    expect(patchTiles(tiles, answer({}))).toBe(tiles);
  });

  it('patches only the tile with a quote; the others keep identity', () => {
    const tiles = [tile({ symbol: 'AAA' }), tile({ symbol: 'XLAB' })];
    const out = patchTiles(tiles, answer({ XLAB: quote() }));
    expect(out).not.toBe(tiles);
    expect(out[0]).toBe(tiles[0]);
    expect(out[1].bars[2].c).toBe(2.77);
    expect(out[1].lines[0].price).toBe(2.77);
  });

  it('NEGATIVE a prototype key never resolves to a quote', () => {
    const tiles = [tile({ symbol: 'constructor' })];
    expect(patchTiles(tiles, answer({}))).toBe(tiles);
  });
});

describe('parseCardLive', () => {
  it('accepts the §3.3 shape', () => {
    const a = answer({ XLAB: quote() });
    expect(parseCardLive(a)).toBe(a);
  });

  it('NEGATIVE a board payload, missing / non-object quotes, footer missing, now_labels not string[]', () => {
    const a = answer({});
    expect(parseCardLive({ tab: 'vcp', count: 1, tiles: [] })).toBeNull();
    expect(parseCardLive({ ...a, quotes: undefined })).toBeNull();
    expect(parseCardLive({ ...a, quotes: [] })).toBeNull();
    expect(parseCardLive({ ...a, quotes: 'x' })).toBeNull();
    expect(parseCardLive({ ...a, quotes: null })).toBeNull();
    expect(parseCardLive({ ...a, footer: null })).toBeNull();
    expect(parseCardLive({ ...a, now_labels: 'now' })).toBeNull();
    expect(parseCardLive({ ...a, now_labels: ['now', 3] })).toBeNull();
    expect(parseCardLive(null)).toBeNull();
    expect(parseCardLive('x')).toBeNull();
    expect(parseCardLive({ detail: 'symbols must be a list of tickers' })).toBeNull();
  });
});

describe('cardLiveSymbols', () => {
  it('trims, uppercases, dedupes, sorts, skips empty', () => {
    expect(cardLiveSymbols([{ symbol: ' xlab ' }, { symbol: 'NVDA' }, { symbol: 'XLAB' }, { symbol: '' },
      { symbol: '  ' }, {}, { symbol: 'iren' }])).toEqual(['IREN', 'NVDA', 'XLAB']);
  });

  it('NEGATIVE null / undefined / a non-string symbol → nothing', () => {
    expect(cardLiveSymbols(null)).toEqual([]);
    expect(cardLiveSymbols(undefined)).toEqual([]);
    expect(cardLiveSymbols([{ symbol: 7 as unknown as string }])).toEqual([]);
  });
});

describe('nextCadence', () => {
  it('closed → the slow read; every other session and null → CARD_LIVE_MS', () => {
    expect(nextCadence('closed')).toBe(CARD_LIVE_CLOSED_MS);
    for (const s of ['rth', 'premarket', 'afterhours', null, undefined] as const) {
      expect(nextCadence(s)).toBe(CARD_LIVE_MS);
    }
  });
});
