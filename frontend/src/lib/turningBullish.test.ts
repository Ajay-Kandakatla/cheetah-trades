import { describe, it, expect } from 'vitest';
import { CM_TABS, TAB_META, barDomain, curveLabels, parseTab,
         type CmCurve, type CmTile } from './chartMaps';
import { filterTile, hiddenForTab, presentGroups, tabFamily } from './chartOverlays';

/* Turning Bullish — the KC Coiled and AMD Raided tabs (Ajay 2026-09-13).
 *
 * The negatives carry this file. Both boards are UNCITED and UNMEASURED, both
 * families are OFF in the default overlay set, and the Keltner channel is the
 * app's first per-bar overlay — three separate ways for a tab to open showing
 * either nothing at all or a line that is not where it claims to be. */

const curve = (values: (number | null)[], label = 'KC mid'): CmCurve =>
  ({ tone: 'keltner', label, values });

describe('the two tabs are registered', () => {
  it('both appear in CM_TABS and both have copy', () => {
    expect(CM_TABS).toContain('keltner');
    expect(CM_TABS).toContain('amd');
    expect(TAB_META.keltner.label).toMatch(/KC/);
    expect(TAB_META.amd.label).toMatch(/AMD/);
  });

  it('LEADS with the inverted measurement, not with the mechanics', () => {
    // The one thing on either page that changes what he does with it. Both
    // reads were measured against a placebo on 2026-09-13 and both came back
    // INVERTED on their own claim; a blurb that opened with the setup and
    // mentioned the study at the end would be burying it.
    expect(TAB_META.keltner.blurb).toMatch(/^MEASURED 2026-09-13 AND THE CLAIM IS INVERTED/);
    expect(TAB_META.amd.blurb).toMatch(/^MEASURED 2026-09-13 AND THE CLAIM IS INVERTED/);
  });

  it('every rate is quoted next to its placebo and a CI — his standing rule', () => {
    expect(TAB_META.keltner.blurb).toMatch(/40\.0% of the time/);
    expect(TAB_META.keltner.blurb).toMatch(/against 55\.0%/);
    expect(TAB_META.keltner.blurb).toMatch(/95% CI/);
    expect(TAB_META.amd.blurb).toMatch(/42\.7% vs 51\.6%/);
    expect(TAB_META.amd.blurb).toMatch(/95% CI/);
  });

  it('names the re-runnable script under each board', () => {
    // "Any measured number on a board he trades ships its re-runnable script
    // + a CI, never a bare point estimate."
    expect(TAB_META.keltner.blurb).toMatch(/turning_bullish_keltner_study\.py/);
    expect(TAB_META.amd.blurb).toMatch(/turning_bullish_amd_study\.py/);
  });

  it('NEGATIVE — neither blurb claims a direction from compression', () => {
    for (const b of [TAB_META.keltner.blurb, TAB_META.amd.blurb]) {
      expect(b).not.toMatch(/coiled to run|markup next|accumulation complete/i);
    }
    expect(TAB_META.keltner.blurb).toMatch(/COMPRESSION, NOT A DIRECTION/);
    // The board-size cut must never be sold as an accuracy gain.
    expect(TAB_META.amd.blurb).toMatch(/BOARD-SIZE cut, never an accuracy gain/);
  });

  it('?tab=keltner and ?tab=amd resolve, and a typo still lands somewhere real', () => {
    expect(parseTab('keltner')).toBe('keltner');
    expect(parseTab('AMD')).toBe('amd');
    expect(parseTab('keltners')).toBe(CM_TABS[0]);
  });
});

describe('the tab forces its own overlay family', () => {
  it('un-hides the family this tab is about, and nothing else', () => {
    const hidden = new Set(['keltner', 'amd', 'fib']);
    const forKc = hiddenForTab(hidden, 'keltner');
    expect(forKc.has('keltner')).toBe(false);
    expect(forKc.has('amd')).toBe(true);
    expect(forKc.has('fib')).toBe(true);
  });

  it('NEGATIVE — returns the SAME set when there is nothing to force', () => {
    // Identity, not just equality: `tabHidden` is a memo dependency, and a new
    // Set on every render would re-filter all 24 tiles every time.
    const hidden = new Set(['keltner']);
    expect(hiddenForTab(hidden, 'zones')).toBe(hidden);
    expect(hiddenForTab(new Set(['amd']), 'keltner')).not.toBe(hidden);
  });

  it('NEGATIVE — no other tab claims a family', () => {
    expect(tabFamily('keltner')).toBe('keltner');
    expect(tabFamily('amd')).toBe('amd');
    for (const t of CM_TABS) {
      if (t !== 'keltner' && t !== 'amd') expect(tabFamily(t)).toBeUndefined();
    }
  });
});

describe('filterTile gates the curve and the sentence with the drawing', () => {
  const tile = {
    symbol: 'MU', href: '/x', bars: [], bands: [], lines: [], markers: [],
    stats: [], why: '',
    curves: [curve([1, 2, 3])],
    badges: [{ text: 'Setup ready', tone: 'warn' as const },
             { text: 'KC coiled up', tone: 'good' as const, group: 'keltner' },
             { text: 'AMD raided', tone: 'good' as const, group: 'amd' }],
  } as unknown as CmTile;

  it('drops the curve AND its verdict when the family is hidden', () => {
    const out = filterTile(tile, new Set(['keltner']));
    expect(out.curves).toHaveLength(0);
    expect(out.badges?.map((b) => b.text)).toEqual(['Setup ready', 'AMD raided']);
  });

  it('NEGATIVE — a badge with no group is a BOARD badge and is never filtered', () => {
    // Setup ready / Vol drying are the tab's own reads. Filtering them with an
    // overlay checkbox would silently strip the board's own verdict.
    const out = filterTile(tile, new Set(['keltner', 'amd', 'demand', 'fib']));
    expect(out.badges?.map((b) => b.text)).toEqual(['Setup ready']);
  });

  it('NEGATIVE — an empty hidden set is identity, curves included', () => {
    expect(filterTile(tile, new Set())).toBe(tile);
  });

  it('a curve-only tile still gets its checkbox in the ledger', () => {
    // The 🌀 tab draws NO flat KC lines, so a `presentGroups` that only looked
    // at bands and lines would render a ledger with no Keltner entry at all.
    const groups = presentGroups([tile]).map((g) => g.key);
    expect(groups).toContain('keltner');
  });
});

describe('the curve is drawn where it actually was', () => {
  it('labels a curve at its LAST real value, not its first', () => {
    const [l] = curveLabels([curve([10, 20, 30.456])]);
    expect(l.price).toBeCloseTo(30.456);
    expect(l.label).toBe('KC mid 30.46');
    expect(l.tone).toBe('keltner');
  });

  it('NEGATIVE — trailing nulls do not become the label', () => {
    // A tile whose last bar is today's live extended-hours print has no
    // channel value for it; labelling that gap would print "KC mid NaN".
    const [l] = curveLabels([curve([10, 20, 30, null])]);
    expect(l.price).toBe(30);
  });

  it('NEGATIVE — an all-null curve produces NO label', () => {
    expect(curveLabels([curve([null, null])])).toHaveLength(0);
    expect(curveLabels([])).toHaveLength(0);
  });

  it('the price domain stretches to hold the channel', () => {
    // The channel can run wider than the candles. Without this the band is
    // clipped at the edge of the plot and reads as if price broke it.
    const bars = [{ t: '2026-09-01', o: 10, h: 10.5, l: 9.5, c: 10, v: 1 }];
    const narrow = barDomain(bars as any, [], []);
    const wide = barDomain(bars as any, [], [], 6, [curve([11.2])]);
    expect(wide.hi).toBeGreaterThan(narrow.hi);
  });

  it('NEGATIVE — an absurd curve value does NOT squash the candles', () => {
    // Same outlier guard every other overlay gets: more than one chart-height
    // away and it is ignored rather than rescaling the chart around it.
    const bars = [{ t: '2026-09-01', o: 10, h: 10.5, l: 9.5, c: 10, v: 1 }];
    const d = barDomain(bars as any, [], [], 6, [curve([9_999])]);
    expect(d.hi).toBeLessThan(100);
  });
});
