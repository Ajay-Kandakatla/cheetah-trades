import { describe, expect, it } from 'vitest';
import { CM_TABS, ENTERABLE_KIND, TAB_META, isBoardTab, parseTab } from './chartMaps';
import { BURST_EXEMPT } from './momentumBurst';

/* 📅 Long Term tab registry (2026-11-12, long-term spec §3.13, WP-FE). Ajay: "Save this entire list for me. In a New tab
 * - Long Term - Remember this analays criteria I am asking you to for this tab and keep updating it from all the other
 * tabs info.." Its slot is IMMEDIATELY after 🚀 Explosive Growth (his call, spec §7 #12); it is not a tile board; it has
 * no 🎯 read. NEGATIVES throughout. */
const ASK = 'Yeah I wanna find out the ones that are actually great in fundamentals and growth and sales and no debt but not growing in price action yet..';

describe('📅 Long Term — tab slot', () => {
  it('sits once, right after growth', () => {
    expect(CM_TABS.filter((t) => t === 'long_term')).toHaveLength(1);
    expect(CM_TABS.indexOf('long_term')).toBe(CM_TABS.indexOf('growth') + 1);
    expect(parseTab('long_term')).toBe('long_term');
    expect(parseTab(' LONG_TERM ')).toBe('long_term');
  });
  it('NEGATIVE: near-miss spellings do not parse to it (longterm = the ZONETRADER page name)', () => {
    for (const raw of ['longterm', 'long-term', 'long term', 'long_terms', 'lt']) expect(parseTab(raw)).not.toBe('long_term');
  });
});

describe('📅 Long Term — not a tile board, no 🎯 read', () => {
  it('NEGATIVE: isBoardTab is false; BURST_EXEMPT names its reason', () => {
    expect(isBoardTab('long_term')).toBe(false);
    expect(BURST_EXEMPT.long_term).toBe('his saved list keeps its saved order — the ⚡ burst is a daily-volume read');
    expect(BURST_EXEMPT.long_term).not.toMatch(new RegExp('b' + 'ounce', 'i'));
  });
  it('NEGATIVE: ENTERABLE_KIND has no long_term', () => {
    expect(Object.prototype.hasOwnProperty.call(ENTERABLE_KIND, 'long_term')).toBe(false);
  });
});

describe('📅 Long Term — TAB_META', () => {
  const m = TAB_META.long_term;
  it('label, his ask verbatim, UNMEASURED, not-a-signal sentence, owner only', () => {
    expect(m.label).toBe('\u{1F4C5} Long Term');
    expect(m.blurb).toContain(ASK);
    expect(m.blurb).toContain('UNMEASURED');
    expect(m.blurb).toMatch(/none of these lists is a buy signal/i);
    expect(m.blurb).toMatch(/owner only/);
  });
  it('NEGATIVE: no digit in the blurb or label', () => {
    expect(m.blurb).not.toMatch(/\d/);
    expect(m.label).not.toMatch(/\d/);
  });
  it('NEGATIVE: no b-word, no attribution, no buy/sell word beyond the not-a-signal sentence, no Pankaj', () => {
    const b = `${m.label} ${m.blurb}`.replace(/none of these lists is a buy signal\.?/gi, '');
    expect(b).not.toMatch(/\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b/i);
    expect(b).not.toMatch(new RegExp('b' + 'ounce', 'i'));
    expect(b).not.toMatch(new RegExp(['g' + 'hee', 'jhun' + 'jhunwala', 'junjun' + 'wala', 'big ' + 'bull'].join('|'), 'i'));
    expect(b).not.toMatch(/Pankaj/);
  });
});
