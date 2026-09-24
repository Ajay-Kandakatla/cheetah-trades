import { describe, it, expect } from 'vitest';
import fixture from '../components/__fixtures__/amd_raids_orcl_2026_09_24.json';
import {
  amdRaidMarks, MARK_RE, occupiedFromMarkers, panelAlign, RAID_OFFSET, RAID_R, RAID_ROW,
  raidRadius, sanitizeAmdRaids, type AmdRaidGeom, type AmdRaidsBlock,
} from './amdRaids';
import type { CmBar } from './chartMaps';

/* 🌀 Every AMD raid on the daily Support tile (Ajay 2026-09-24: "Show all the
 * possible raids, past ones too and todays too."). The backend writes every
 * sentence; these pin the sanitizer (junk never reaches the screen) and the
 * circle placement (never outside the plot, never on top of another glyph). */

const RAW = (fixture as any).tile.amd_raids;
const BARS: CmBar[] = (fixture as any).tile.bars;
const clone = () => JSON.parse(JSON.stringify(RAW));

const flatGeom = (over: Partial<AmdRaidGeom> = {}): AmdRaidGeom => ({
  minGapBars: 3,
  lowY: () => 100,
  highY: () => 60,
  top: 10 + RAID_R,
  bottom: 190 - 10 - 4 - RAID_R,
  occupied: [],
  ...over,
});

const mkBars = (n: number): CmBar[] => Array.from({ length: n }, (_, i) => {
  const d = new Date(Date.UTC(2026, 0, 1 + i)).toISOString().slice(0, 10);
  return { t: d, o: 10, h: 11, l: 9, c: 10, v: 1 };
});

const block = (over: Partial<AmdRaidsBlock> = {}): AmdRaidsBlock => ({
  ...(sanitizeAmdRaids(clone()) as AmdRaidsBlock), ...over,
});

const lowRow = (date: string, mark: string | null, extra: Record<string, unknown> = {}) => ({
  direction: 'bullish', date, raid_level: 10, raid_price: 9, outcome: 'live',
  text: `row ${date}`, in_view: true, mark, n: mark ? 1 : null, ...extra,
});

describe('sanitizeAmdRaids', () => {
  it('keeps the served fixture whole', () => {
    const b = sanitizeAmdRaids(clone())!;
    expect(b.raids).toHaveLength(7);
    expect(b.today).toHaveLength(2);
    expect(b.draw_dirs).toEqual(['bullish']);
    expect(b.chains_in_view).toEqual({ bullish: 3, bearish: 1 });
    expect(b.chains_off_view).toBe(1);
    expect(b.chip!.text).toBe('3 low · 1 high raids · today low reclaimed (not closed)');
    expect(b.chip!.title.startsWith(b.verdict_basis_note!)).toBe(true);
    expect(b.cited).toBe(false);
  });

  it('NEGATIVE — null / array / string / number → null', () => {
    for (const junk of [null, undefined, [], [RAW], 'amd', 7, true]) {
      expect(sanitizeAmdRaids(junk)).toBeNull();
    }
  });

  it('NEGATIVE — drops rows with NaN, negative, unknown direction / outcome, bad date, no text', () => {
    const x = clone();
    x.raids = [
      lowRow('2026-09-01', '3'),
      lowRow('2026-09-02', '4', { raid_level: NaN }),
      lowRow('2026-09-03', '5', { raid_price: -1 }),
      lowRow('2026-09-04', '6', { direction: 'sideways' }),
      lowRow('2026-09-05', '7', { outcome: 'bounced' }),
      lowRow('2026-9-6', '8'),
      lowRow('2026-09-07', '9', { text: '   ' }),
      lowRow('2026-09-08', '10', { raid_level: Infinity }),
      null, 'row', 42,
    ];
    const b = sanitizeAmdRaids(x)!;
    expect(b.raids.map((r) => r.date)).toEqual(['2026-09-01']);
  });

  it('NEGATIVE — a string number is NOT coerced', () => {
    const x = clone();
    x.raids = [lowRow('2026-09-01', '3', { raid_level: '141.02' })];
    expect(sanitizeAmdRaids(x)!.raids).toHaveLength(0);
    x.raids = [lowRow('2026-09-01', '3', { depth_pct: '0.76', vol_ratio: '1.8', bars_ago: '16' })];
    const r = sanitizeAmdRaids(x)!.raids[0];
    expect(r.depth_pct).toBeNull();
    expect(r.vol_ratio).toBeNull();
    expect(r.bars_ago).toBeNull();
  });

  it('NEGATIVE — a bad mark becomes null; n must be a positive integer', () => {
    const x = clone();
    x.raids = [
      lowRow('2026-09-01', '<b>3</b>'), lowRow('2026-09-02', '3.2'),
      lowRow('2026-09-03', 'X1'), lowRow('2026-09-04', '1·2', { n: 1.5 }),
      lowRow('2026-09-05', '1234'),
    ];
    const b = sanitizeAmdRaids(x)!;
    expect(b.raids.map((r) => r.mark)).toEqual([null, null, null, '1·2', null]);
    expect(b.raids[3].n).toBeNull();
    for (const ok of ['1', '12', '3·2', 'H1', 'H12·3', '?']) expect(MARK_RE.test(ok)).toBe(true);
  });

  it('NEGATIVE — today entries need a known state, direction, a positive price and text', () => {
    const x = clone();
    const good = x.today[0];
    x.today = [
      good,
      { ...good, state: 'bouncing' },
      { ...good, direction: 'up' },
      { ...good, price: 0 },
      { ...good, price: NaN },
      { ...good, price: '139.80' },
      { ...good, text: '' },
      null,
    ];
    const b = sanitizeAmdRaids(x)!;
    expect(b.today).toHaveLength(1);
    expect(b.today[0].state).toBe('reclaimed');
  });

  it('NEGATIVE — junk draw_dirs → [], junk counts → 0, empty raids kept', () => {
    const x = clone();
    x.draw_dirs = 'bullish';
    x.chains_in_view = { bullish: -2, bearish: 'x' };
    x.chains_off_view = NaN;
    x.raids = [];
    const b = sanitizeAmdRaids(x)!;
    expect(b.draw_dirs).toEqual([]);
    expect(b.chains_in_view).toEqual({ bullish: 0, bearish: 0 });
    expect(b.chains_off_view).toBe(0);
    expect(b.raids).toEqual([]);
    const y = clone();
    y.draw_dirs = ['bullish', 'sideways', 7, null, 'bearish'];
    expect(sanitizeAmdRaids(y)!.draw_dirs).toEqual(['bullish', 'bearish']);
  });

  it('NEGATIVE — a chip without text is null; the tone is forced muted', () => {
    const x = clone();
    x.chip = { text: '', tone: 'good', title: 't' };
    expect(sanitizeAmdRaids(x)!.chip).toBeNull();
    x.chip = { tone: 'good' };
    expect(sanitizeAmdRaids(x)!.chip).toBeNull();
    x.chip = { text: '1 low raid', tone: 'good', title: 42 };
    expect(sanitizeAmdRaids(x)!.chip).toEqual({ text: '1 low raid', tone: 'muted', title: '' });
  });
});

describe('amdRaidMarks — which raids get a circle', () => {
  it('in-view closed rows with a mark + today entries with a mark, draw_dirs only (no "1", no "H1")', () => {
    const marks = amdRaidMarks(block(), BARS, flatGeom({ minGapBars: 1 }));
    expect(marks.map((m) => m.mark)).toEqual(['1·2', '1·3', '2', '3', '4']);
    expect(marks.every((m) => m.dir === 'bullish')).toBe(true);
    const live = marks.find((m) => m.mark === '4')!;
    expect(live.live).toBe(true);
    expect(live.i).toBe(BARS.length - 1);
    expect(marks.filter((m) => m.live)).toHaveLength(1);
  });

  it('joins by DATE — a row whose date is not on the drawn bars is skipped', () => {
    const b = block({ raids: [
      sanitizeAmdRaids({ raids: [lowRow('2019-01-02', '9')] })!.raids[0],
      sanitizeAmdRaids({ raids: [lowRow(BARS[10].t, '1')] })!.raids[0],
    ], today: [] });
    const marks = amdRaidMarks(b, BARS, flatGeom());
    expect(marks.map((m) => [m.mark, m.i])).toEqual([['1', 10]]);
  });

  it('bearish drawn only when draw_dirs says so, preferring above the candle', () => {
    const b = block({ draw_dirs: ['bullish', 'bearish'] });
    const h1 = amdRaidMarks(b, BARS, flatGeom()).find((m) => m.mark === 'H1')!;
    expect(h1.side).toBe('above');
    expect(h1.y).toBe(60 - RAID_OFFSET);
  });

  it('a "?" mark is unsure and live', () => {
    const x = clone();
    x.today[0] = { ...x.today[0], state: 'sweeping', mark: '?', n: null };
    const m = amdRaidMarks(sanitizeAmdRaids(x), BARS, flatGeom()).find((k) => k.mark === '?')!;
    expect(m.unsure).toBe(true);
    expect(m.live).toBe(true);
  });

  it('NEGATIVE — null block, no bars, nothing in draw_dirs → no circles, no throw', () => {
    expect(amdRaidMarks(null, BARS, flatGeom())).toEqual([]);
    expect(amdRaidMarks(block(), [], flatGeom())).toEqual([]);
    expect(amdRaidMarks(block({ draw_dirs: [] }), BARS, flatGeom())).toEqual([]);
  });
});

describe('amdRaidMarks — stacking', () => {
  const bars = mkBars(60);
  const rows = (dates: number[]) => sanitizeAmdRaids({
    raids: dates.map((i, k) => lowRow(bars[i].t, String(k + 1))), draw_dirs: ['bullish'],
  })!;

  it('adjacent bars take different rows; far bars share row 0', () => {
    const marks = amdRaidMarks(rows([10, 11, 30]), bars, flatGeom({ minGapBars: 3 }));
    expect(marks.map((m) => m.row)).toEqual([0, 1, 0]);
    expect(marks[1].y - marks[0].y).toBe(RAID_ROW);
    expect(marks[0].y).toBe(100 + RAID_OFFSET);
  });

  it('an amd_a / touch_d on the raid bar pushes the circle to row 1', () => {
    for (const kind of ['amd_a', 'touch_d', 'amd_x']) {
      const occ = occupiedFromMarkers([{ date: bars[10].t, kind }], bars);
      expect(occ).toEqual([{ i: 10, side: 'below' }]);
      const [m] = amdRaidMarks(rows([10]), bars, flatGeom({ occupied: occ }));
      expect(m.row).toBe(1);
      expect(m.side).toBe('below');
    }
  });

  it('occupiedFromMarkers: amd_d / touch_s are above; others and off-bar dates ignored', () => {
    const occ = occupiedFromMarkers([
      { date: bars[3].t, kind: 'amd_d' }, { date: bars[4].t, kind: 'touch_s' },
      { date: bars[5].t, kind: 'kc_sq' }, { date: bars[6].t, kind: 'amd_m' },
      { date: '2019-01-01', kind: 'amd_a' }, { date: bars[7].t + 'T00:00:00', kind: 'touch_d' },
    ] as any, bars);
    expect(occ).toEqual([{ i: 3, side: 'above' }, { i: 4, side: 'above' }, { i: 7, side: 'below' }]);
    expect(occupiedFromMarkers(null as any, bars)).toEqual([]);
  });

  it('a low near the plot bottom SKIPS the out-of-plot rows and goes above the candle', () => {
    const bottom = 170.8;
    const [m] = amdRaidMarks(rows([10]), bars, flatGeom({
      lowY: () => 165, highY: () => 150, bottom,
    }));
    expect(m.side).toBe('above');
    expect(m.y).toBe(150 - RAID_OFFSET);
  });

  it('a row just inside the bottom is used; one just past it is skipped, never clamped', () => {
    const [m] = amdRaidMarks(rows([10]), bars, flatGeom({ lowY: () => 160, bottom: 170 }));
    expect(m.side).toBe('below');
    expect(m.row).toBe(0);
    const out = amdRaidMarks(rows([10]), bars, flatGeom({ lowY: () => 163, bottom: 170 }));
    expect(out[0].side).toBe('above');
  });

  it('NEGATIVE — no free row anywhere → omitted, no throw', () => {
    const out = amdRaidMarks(rows([10]), bars, flatGeom({
      lowY: () => 400, highY: () => -400,
    }));
    expect(out).toEqual([]);
    const nan = amdRaidMarks(rows([10]), bars, flatGeom({ lowY: () => NaN, highY: () => NaN }));
    expect(nan).toEqual([]);
  });

  it('NEGATIVE — never a y outside [top, bottom]; 50 rows → unique marks, no throw', () => {
    const b = sanitizeAmdRaids({
      raids: Array.from({ length: 50 }, (_, k) => lowRow(bars[k].t, String(k + 1))),
      draw_dirs: ['bullish'],
    })!;
    const g = flatGeom({ lowY: (i) => 40 + (i % 9) * 15, highY: (i) => 30 + (i % 9) * 15 });
    const out = amdRaidMarks(b, bars, g);
    expect(out.length).toBeGreaterThan(0);
    expect(new Set(out.map((m) => m.mark)).size).toBe(out.length);
    for (const m of out) {
      expect(m.y).toBeGreaterThanOrEqual(g.top);
      expect(m.y).toBeLessThanOrEqual(g.bottom);
    }
    // no two circles share a side+row within minGapBars
    for (const a of out) for (const c of out) {
      if (a === c) continue;
      if (a.side === c.side && a.row === c.row) {
        expect(Math.abs(a.i - c.i)).toBeGreaterThanOrEqual(g.minGapBars);
      }
    }
  });
});

describe('panelAlign / raidRadius', () => {
  it('right when the panel fits left of the chip’s right edge', () => {
    expect(panelAlign({ left: 700, right: 760 }, 1400)).toBe('right');
  });
  it('left when it only fits rightwards', () => {
    expect(panelAlign({ left: 20, right: 90 }, 1400)).toBe('left');
  });
  it('fixed on a narrow phone', () => {
    expect(panelAlign({ left: 100, right: 180 }, 320)).toBe('fixed');
  });
  it('raidRadius grows for wider marks', () => {
    expect(raidRadius('4')).toBe(RAID_R);
    expect(raidRadius('H1')).toBe(RAID_R);
    expect(raidRadius('3·2')).toBeGreaterThan(RAID_R);
    expect(raidRadius('12·3')).toBeGreaterThan(raidRadius('3·2'));
    expect(raidRadius('')).toBe(RAID_R);
  });
});
