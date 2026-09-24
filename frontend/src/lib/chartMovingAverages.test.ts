/* 9 EMA / 20 SMA / 200 SMA as three checkboxes — 2026-09-23.
 *
 * Ajay: "I need 9 EMA and 20 SMA on our charts and also 200 MA on our charts
 * as check boxes.." Three boxes, not one: hiding the 200 must not take the 9
 * with it.
 *
 * The negatives are the point:
 *   * a checkbox that hides a neighbouring family too;
 *   * three lines that arrive switched OFF, so he asks for lines and gets
 *     empty checkboxes;
 *   * a saved hidden-set from before these keys existed silently hiding them;
 *   * a new tone falling through to the grid grey, which is exactly how the
 *     2026-09-12 study overlays shipped invisible ("Non of these are showing
 *     up").
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { toneColor, curveLabels, barDomain, type CmCurve } from './chartMaps';
import {
  OVERLAY_GROUPS, DEFAULT_ON, defaultHidden, filterTile, loadHidden,
  presentGroups, STUDY_KEYS,
} from './chartOverlays';

const MA_KEYS = ['ema9', 'sma20', 'sma200'];

const curve = (tone: string, label: string, v: (number | null)[]): CmCurve =>
  ({ tone, label, values: v } as any);

const tile = (): any => ({
  symbol: 'X', href: '/x', markers: [], stats: [], why: '',
  bars: [
    { t: '2026-09-21', o: 10, h: 11, l: 9, c: 10, v: 1 },
    { t: '2026-09-22', o: 10, h: 11, l: 9, c: 10, v: 1 },
    { t: '2026-09-23', o: 10, h: 11, l: 9, c: 10, v: 1 },
  ],
  bands: [{ kind: 'demand', lo: 1, hi: 2 }],
  lines: [{ price: 2, label: 'BUY', tone: 'buy' }],
  curves: [
    curve('ema9', '9 EMA', [null, 9.8, 9.9]),
    curve('sma20', '20 SMA', [null, 9.5, 9.6]),
    curve('sma200', '200 SMA', [null, null, 8.4]),
    curve('keltner', 'KC mid', [9, 9, 9]),
  ],
});

describe('the three families', () => {
  it('registers exactly his three periods and nothing else', () => {
    const added = OVERLAY_GROUPS.filter((g) => MA_KEYS.includes(g.key));
    expect(added.map((g) => g.key)).toEqual(MA_KEYS);
    expect(added.map((g) => g.label)).toEqual(['9 EMA', '20 SMA', '200 SMA']);
    // Rule #1: no 50, no 21, no 10 sneaking in "for completeness".
    expect(OVERLAY_GROUPS.some((g) => /\b(10|21|50|100)\s*(EMA|SMA|MA)\b/i.test(g.label)))
      .toBe(false);
  });

  it('owns one tone each, and no family shares a tone with another', () => {
    const tones = OVERLAY_GROUPS.flatMap((g) => g.lineTones || []);
    expect(new Set(tones).size).toBe(tones.length);
    for (const k of MA_KEYS) {
      expect(OVERLAY_GROUPS.find((g) => g.key === k)!.lineTones).toEqual([k]);
    }
  });

  it('says the 200 is the SIMPLE average the SEPA gate reads', () => {
    const g = OVERLAY_GROUPS.find((x) => x.key === 'sma200')!;
    expect(g.hint.toLowerCase()).toContain('simple');
    expect(g.hint).toMatch(/Minervini|trend template|SEPA/i);
  });

  it('is NOT one of the uncited study families — an MA is a drawing', () => {
    for (const k of MA_KEYS) expect(STUDY_KEYS).not.toContain(k);
  });
});

describe('each checkbox hides exactly its own curve', () => {
  it.each(MA_KEYS)('hiding %s removes that curve and nothing else', (key) => {
    const out = filterTile(tile(), new Set([key]));
    expect(out.curves!.map((c: any) => c.tone))
      .toEqual(['ema9', 'sma20', 'sma200', 'keltner'].filter((t) => t !== key));
    // and it never touches the bands, the plan lines or the other families
    expect(out.bands!.map((b: any) => b.kind)).toEqual(['demand']);
    expect(out.lines!.map((l: any) => l.label)).toEqual(['BUY']);
  });

  it('NEGATIVE — hiding the 200 does not take the 9 or the 20 with it', () => {
    const out = filterTile(tile(), new Set(['sma200']));
    const tones = out.curves!.map((c: any) => c.tone);
    expect(tones).toContain('ema9');
    expect(tones).toContain('sma20');
    expect(tones).not.toContain('sma200');
  });

  it('NEGATIVE — hiding Keltner leaves all three averages drawn', () => {
    const out = filterTile(tile(), new Set(['keltner']));
    expect(out.curves!.map((c: any) => c.tone)).toEqual(MA_KEYS);
  });

  it('hides all three when all three boxes are off', () => {
    const out = filterTile(tile(), new Set(MA_KEYS));
    expect(out.curves!.map((c: any) => c.tone)).toEqual(['keltner']);
  });

  it('an empty hidden set is a no-op (identity)', () => {
    const t = tile();
    expect(filterTile(t, new Set())).toBe(t);
  });
});

describe('they ship ON', () => {
  it('all three are in DEFAULT_ON', () => {
    for (const k of MA_KEYS) expect(DEFAULT_ON).toContain(k);
  });

  it('defaultHidden hides none of them', () => {
    const hidden = defaultHidden();
    for (const k of MA_KEYS) expect(hidden.has(k)).toBe(false);
  });

  it('NEGATIVE — the unmeasured study families are still OFF by default', () => {
    // The reason the MAs may be on is that they are drawings, not reads. If
    // this ever flips, the reasoning in DEFAULT_ON's comment has been lost.
    const hidden = defaultHidden();
    for (const k of STUDY_KEYS) expect(hidden.has(k)).toBe(true);
  });

  it('a tile carrying MA curves offers all three checkboxes', () => {
    const keys = presentGroups([tile()]).map((g) => g.key);
    for (const k of MA_KEYS) expect(keys).toContain(k);
  });

  it('NEGATIVE — a board with no MA curves offers no MA checkbox', () => {
    const t = tile();
    t.curves = [curve('keltner', 'KC mid', [9, 9, 9])];
    const keys = presentGroups([t]).map((g) => g.key);
    for (const k of MA_KEYS) expect(keys).not.toContain(k);
  });
});

describe('a saved v2 hidden-set from BEFORE this change', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('still shows all three — no key bump was needed', () => {
    // Exactly what a browser saved on 09-14: the study families hidden, and
    // no mention of keys that did not exist yet. `saveHidden` writes only the
    // HIDDEN keys, so the new families cannot be in there.
    const saved = JSON.stringify(['amd', 'fib', 'meanrev', 'keltner', 'range']);
    vi.stubGlobal('window', { localStorage: { getItem: () => saved } });
    vi.stubGlobal('localStorage', { getItem: () => saved });
    const hidden = loadHidden();
    for (const k of MA_KEYS) expect(hidden.has(k)).toBe(false);
    expect(hidden.has('fib')).toBe(true);        // his own choices survive
  });

  it('a blocked / cleared store falls back to the default, MAs on', () => {
    vi.stubGlobal('window', {
      localStorage: { getItem: () => { throw new Error('blocked'); } },
    });
    const hidden = loadHidden();
    for (const k of MA_KEYS) expect(hidden.has(k)).toBe(false);
  });

  it('NEGATIVE — a set that DOES name them still hides them (his choice wins)', () => {
    const saved = JSON.stringify(['sma200']);
    vi.stubGlobal('window', { localStorage: { getItem: () => saved } });
    expect(loadHidden().has('sma200')).toBe(true);
    expect(loadHidden().has('ema9')).toBe(false);
  });
});

describe('the lines are drawn, and their labels do not collide', () => {
  it('NEGATIVE — no MA tone falls through to the grid grey', () => {
    const grey = toneColor('neutral' as any);
    for (const k of MA_KEYS) expect(toneColor(k as any)).not.toBe(grey);
  });

  it('the swatch in the ledger IS the colour of the line', () => {
    for (const k of MA_KEYS) {
      const g = OVERLAY_GROUPS.find((x) => x.key === k)!;
      expect(g.swatch).toBe(toneColor(k as any));
    }
    // three different colours, so three lines on one tile are tellable apart
    expect(new Set(MA_KEYS.map((k) => toneColor(k as any))).size).toBe(3);
  });

  it('each curve gets ONE gutter label, at its LAST non-null value', () => {
    const labels = curveLabels(tile().curves);
    expect(labels.map((l) => l.label))
      .toEqual(['9 EMA 9.90', '20 SMA 9.60', '200 SMA 8.40', 'KC mid 9.00']);
  });

  it('a curve that is all warm-up contributes no label at all', () => {
    expect(curveLabels([curve('sma200', '200 SMA', [null, null, null])])).toEqual([]);
  });

  it('the labels are de-collided by the same pass as the plan labels', async () => {
    const { lineLabels } = await import('./chartMaps');
    // Three averages stacked within a cent of each other, plus a BUY at the
    // same price — the 2026-09-08 overlap bug, on a new family.
    const lines = [
      { price: 100.0, label: 'BUY', tone: 'buy' as any },
      ...curveLabels([
        curve('ema9', '9 EMA', [100.0]),
        curve('sma20', '20 SMA', [100.0]),
        curve('sma200', '200 SMA', [100.0]),
      ]),
    ];
    const out = lineLabels(lines as any, { lo: 90, hi: 110 }, 320, 8, 9.5);
    const ys = out.map((i) => i.y).sort((a, b) => a - b);
    for (let i = 1; i < ys.length; i += 1) {
      expect(ys[i] - ys[i - 1]).toBeGreaterThanOrEqual(9.5);
    }
    // The BUY label is never the one that yields.
    expect(out.some((i) => i.text === 'BUY')).toBe(true);
  });

  it('a 200 SMA far below the candles never squashes the price action', () => {
    const bars = [{ t: '2026-09-23', o: 100, h: 101, l: 99, c: 100, v: 1 }] as any;
    const d = barDomain(bars, [], [], 6, [curve('sma200', '200 SMA', [12])]);
    expect(d.lo).toBeGreaterThan(90);     // the outlier is ignored by `stretch`
  });

  it('a null inside a curve is a GAP, not a value joined through', () => {
    // The drawn path splits on nulls (PatternChart), so the contract the
    // backend must honour is simply: nulls survive filterTile untouched.
    const t = tile();
    const out = filterTile(t, new Set(['keltner']));
    expect(out.curves!.find((c: any) => c.tone === 'sma200')!.values)
      .toEqual([null, null, 8.4]);
  });
});
