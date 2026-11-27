/* 🕐 2026-11-27 (spec sicheck §3.6 D1): the hover readout prints the bar's clock RANGE on the 🚩 board and 👀 Watch.
 * The stored stamp is the bar's END (the volume check of 11-27: NXAT's 08:10 bar of 771,509 is the 08:05–08:09 bar),
 * so the start is the stamp minus the bar size. Every other tab passes no barMin and prints exactly today's line. */
import { describe, expect, it } from 'vitest';
import {
  HOVER_FONT_SIZE, HOVER_TEXT_INSET, HOVER_TIP_W, barRange, hoverLines, hoverTipWidth, shortVol, textWidth, tfBarMin,
  type CmBar,
} from './chartMaps';
import { ggwBarStamp, ggwBucket } from './ggwLive';

const bar = (t: string, s?: string): CmBar => ({ t, o: 0.8334, h: 0.88, l: 0.82, c: 0.8399, v: 771509, ...(s ? { s } : {}) });

describe('tfBarMin', () => {
  it("'1m' 1, '5m' 5, '15m' 15", () => {
    expect(tfBarMin('1m')).toBe(1);
    expect(tfBarMin('5m')).toBe(5);
    expect(tfBarMin('15m')).toBe(15);
  });
  it('NEGATIVE: any other frame → null', () => {
    for (const tf of ['1d', 'D', '', '5', 5, null, undefined, '30m', '1M', {}]) expect(tfBarMin(tf)).toBeNull();
  });
});

describe('barRange', () => {
  it('the three spec examples: 5-min 08:10, 15-min 08:15, 1-min 08:10', () => {
    expect(barRange('2026-11-27 08:10', 5)).toBe('08:05–08:10');
    expect(barRange('2026-11-27 08:15', 15)).toBe('08:00–08:15');
    expect(barRange('2026-11-27 08:10', 1)).toBe('08:09–08:10');
  });
  it('a bar stamped 00:00 wraps to 23:55; a bar across the hour', () => {
    expect(barRange('2026-11-27 00:00', 5)).toBe('23:55–00:00');
    expect(barRange('2026-11-27 00:10', 15)).toBe('23:55–00:10');
    expect(barRange('2026-11-27 10:00', 5)).toBe('09:55–10:00');
  });
  it('NEGATIVE: barMin 0, negative, NaN, Infinity, a fraction, a string, absent → null', () => {
    for (const m of [0, -5, NaN, Infinity, 2.5, 0.5, '5', null, undefined]) {
      expect(barRange('2026-11-27 08:10', m as unknown)).toBeNull();
    }
  });
  it('NEGATIVE: a date-only, seconds, ISO "T", out-of-range or junk stamp → null', () => {
    for (const t of ['2026-11-27', '2026-11-27 08:10:00', '2026-11-27T08:10', '2026-11-27 24:00', '2026-11-27 08:60',
                     ' 2026-11-27 08:10', '08:10', '', null, undefined, 20261127]) {
      expect(barRange(t as unknown, 5)).toBeNull();
    }
  });
});

describe('hoverLines with barMin', () => {
  it('line 1 = date + range (+ tape); the date shown stays the stamp\'s', () => {
    expect(hoverLines(bar('2026-11-27 08:10'), 5)[0]).toBe('2026-11-27 08:05–08:10');
    expect(hoverLines(bar('2026-11-27 08:15'), 15)[0]).toBe('2026-11-27 08:00–08:15');
    expect(hoverLines(bar('2026-11-27 08:10'), 1)[0]).toBe('2026-11-27 08:09–08:10');
    expect(hoverLines(bar('2026-11-27 00:00'), 5)[0]).toBe('2026-11-27 23:55–00:00');
  });
  it('NEGATIVE: the AH / pre / forming suffix is kept after the range', () => {
    expect(hoverLines(bar('2026-11-27 08:10', 'pre'), 5)[0]).toBe('2026-11-27 08:05–08:10 · pre');
    expect(hoverLines(bar('2026-11-27 16:05', 'ah'), 5)[0]).toBe('2026-11-27 16:00–16:05 · AH');
    expect(hoverLines(bar('2026-11-27 16:05', 'forming'), 5)[0]).toBe('2026-11-27 16:00–16:05 · forming');
  });
  it('NEGATIVE: no barMin, 0, NaN, a fraction, a date-only stamp → exactly today\'s line', () => {
    const b = bar('2026-11-27 08:10', 'pre');
    const today = hoverLines(b);
    expect(today[0]).toBe('2026-11-27 08:10 · pre');
    for (const m of [undefined, 0, NaN, 2.5, -1]) expect(hoverLines(b, m as number)).toEqual(today);
    const d = bar('2026-11-27', 'ah');
    expect(hoverLines(d, 5)).toEqual(hoverLines(d));
    expect(hoverLines(d, 5)[0]).toBe('2026-11-27 · AH');
  });
  it('NEGATIVE: lines 2–4 (OHLC and the volume line through shortVol) are unchanged by a range', () => {
    const b = bar('2026-11-27 08:10', 'pre');
    const on = hoverLines(b, 5);
    const off = hoverLines(b);
    expect(on.slice(1)).toEqual(off.slice(1));
    expect(on[3]).toBe(`Vol ${shortVol(771509)}`);
    expect(on[3]).toBe('Vol 772K');
    expect(on).toHaveLength(4);
  });
  it('NEGATIVE: no bar → [] with or without barMin', () => {
    expect(hoverLines(null, 5)).toEqual([]);
    expect(hoverLines(undefined, 5)).toEqual([]);
  });
});

describe('hoverTipWidth', () => {
  it('NEGATIVE: the box keeps HOVER_TIP_W (104) without a range', () => {
    expect(HOVER_TIP_W).toBe(104);
    const b = bar('2026-11-27 08:10', 'pre');
    for (const m of [undefined, 0, NaN, 2.5]) expect(hoverTipWidth(b, m as number)).toBe(104);
    expect(hoverTipWidth(bar('2026-11-27'), 5)).toBe(104);
    expect(hoverTipWidth(null, 5)).toBe(104);
  });
  it('widens to fit line 1 when a range makes it longer — never narrower than 104', () => {
    const b = bar('2026-11-27 08:10', 'pre');
    const line = hoverLines(b, 5)[0];
    const w = hoverTipWidth(b, 5);
    expect(w).toBe(Math.max(104, Math.ceil(textWidth(line, HOVER_FONT_SIZE) + 2 * HOVER_TEXT_INSET)));
    expect(w).toBeGreaterThan(104);
    expect(w).toBeGreaterThanOrEqual(textWidth(line, HOVER_FONT_SIZE) + 2 * HOVER_TEXT_INSET);
  });
});

/* 🕐 Refix 2026-11-27 (verify: "live Watch bars are END-stamped too (ggwLive.ts:70)"): the 👀 Watch's forming candles
 * get their stamp from ggwBarStamp = fromEt + (bucket + 1) × frameMin — the same END label as the stored bars — so the
 * hover range of a live bar is exactly the bucket it folded. Pinned here so a change of either side breaks a test. */
describe('barRange on live Watch bars (ggwBarStamp, END-stamped)', () => {
  const DAY = '2026-11-27';
  const FROM = '04:00';
  const toMin = (hm: string) => Number(hm.slice(0, 2)) * 60 + Number(hm.slice(3, 5));
  it('every bucket of every served frame: range = [fromEt + bucket × fm, fromEt + (bucket + 1) × fm]', () => {
    for (const tf of ['1m', '5m', '15m']) {
      const fm = tfBarMin(tf) as number;
      const slots = Math.floor((20 * 60 - toMin(FROM)) / fm);
      for (let b = 0; b < slots; b++) {
        const t = ggwBarStamp(DAY, FROM, b, fm);
        const r = barRange(t, fm) as string;
        const [s, e] = r.split('–');
        expect(toMin(s)).toBe(toMin(FROM) + b * fm);
        expect(toMin(e)).toBe(toMin(FROM) + (b + 1) * fm);
      }
    }
  });
  it('a print folds into the bucket whose hover range holds it (closed=left): NXAT 08:05:00 and 08:09:59 → 08:05–08:10', () => {
    const start = Date.UTC(2026, 10, 27, 9, 0) / 1000;
    for (const [secs, want] of [[4 * 3600 + 5 * 60, '08:05–08:10'], [4 * 3600 + 9 * 60 + 59, '08:05–08:10'],
                                [4 * 3600 + 10 * 60, '08:10–08:15']] as const) {
      const b = ggwBucket(start + secs, start, 5);
      expect(barRange(ggwBarStamp(DAY, FROM, b, 5), 5)).toBe(want);
    }
  });
  it('NEGATIVE: neighbouring live buckets never overlap and leave no gap; the range never starts at the stamp', () => {
    for (const fm of [1, 5, 15]) {
      const slots = Math.floor((20 * 60 - toMin(FROM)) / fm);
      for (const b of [0, 47, Math.floor(slots / 2), slots - 2]) {
        const here = barRange(ggwBarStamp(DAY, FROM, b, fm), fm) as string;
        const next = barRange(ggwBarStamp(DAY, FROM, b + 1, fm), fm) as string;
        expect(here.split('–')[1]).toBe(next.split('–')[0]);
        expect(here.split('–')[0]).not.toBe(ggwBarStamp(DAY, FROM, b, fm).slice(11));
      }
    }
  });
  it('NEGATIVE: a live bar hovered without barMin keeps exactly today\'s line', () => {
    const lb: CmBar = { t: ggwBarStamp(DAY, FROM, 49, 5), o: 0.83, h: 0.88, l: 0.82, c: 0.84, v: 771509 };
    expect(lb.t).toBe('2026-11-27 08:10');
    expect(hoverLines(lb)[0]).toBe('2026-11-27 08:10');
    expect(hoverLines(lb, 5)[0]).toBe('2026-11-27 08:05–08:10');
  });
});
