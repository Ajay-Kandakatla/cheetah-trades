/* ⏹ The 🚩 Gajjala 1-minute page retired 2026-11-18 (retire-1m spec §3.10). Ajay 2026-11-18: "This is good info stop 1 min
 * tab it was a good experiment" — then "But keep the one min chart in the watch list I still want them". The tab leaves
 * the strip (RETIRED_CM_TABS / isRetiredTab) but stays in CM_TABS so ?tab=gajjala_1m keeps routing to its 🏁 history;
 * the blurb and the two /notifications details say retired, past tense, and keep the 10-27 / 10-29 contract phrases.
 * NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import { CM_TABS, GAJJALA_TABS, RETIRED_CM_TABS, TAB_META, isRetiredTab, type CmTab } from './chartMaps';
import { CATEGORIES } from '../pages/Notifications';

const HIS_RETIRE = 'This is good info stop 1 min tab it was a good experiment';
const ASK_1 = 'Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles please.';
const HIS_29 = ['Only give me Gajjalas chart notifications from both tabs,', 'I am missing out the ones in noise.'];
const KINDS = ['gajjala_1m_setup', 'gajjala_1m_potential'] as const;

describe('⏹ RETIRED_CM_TABS / isRetiredTab (2026-11-18)', () => {
  it('exactly the 1-minute page', () => {
    expect(RETIRED_CM_TABS).toEqual(['gajjala_1m']);
    expect(isRetiredTab('gajjala_1m')).toBe(true);
  });
  it('NEGATIVE: no other tab is retired — 🚩, 🧪, 👀 and every CM_TABS entry but one stay', () => {
    expect(isRetiredTab('gajjala')).toBe(false);
    expect(isRetiredTab('gajjala_audited')).toBe(false);
    expect(isRetiredTab('gajjala_watch')).toBe(false);
    expect(CM_TABS.filter((t) => isRetiredTab(t))).toEqual(['gajjala_1m']);
  });
  it('NEGATIVE: still routable — CM_TABS and GAJJALA_TABS keep gajjala_1m (the deep link and the 🏁 history)', () => {
    expect(CM_TABS).toContain('gajjala_1m' as CmTab);
    expect(GAJJALA_TABS).toContain('gajjala_1m' as CmTab);
    expect(CM_TABS.indexOf('gajjala_1m')).toBe(CM_TABS.indexOf('gajjala_audited') + 1);
  });
});

describe('⏹ TAB_META.gajjala_1m blurb says retired (2026-11-18)', () => {
  const b = TAB_META.gajjala_1m.blurb;
  it('RETIRED 2026-11-18 + his sentence verbatim + the 10-27 contract phrases', () => {
    expect(TAB_META.gajjala_1m.label).toBe("Gajjala's 1-min");
    expect(b).toContain('RETIRED 2026-11-18');
    expect(b).toContain(HIS_RETIRE);
    expect(b).toContain(ASK_1);
    for (const need of ['CLOSED 1-minute candles', 'the Fade on 5-minute first', 'GG trades these setups on 5-minute bars',
      'Cheetah variant', '2026-10-27', 'UNMEASURED', 'Not advice.']) expect(b, need).toContain(need);
  });
  it('NEGATIVE: no "rings your phone", no shadow, no b-word, no "about once a minute", only 1-/5-minute digits', () => {
    expect(b).not.toContain('rings your phone');
    expect(b).not.toMatch(/\bshadow\b/i);
    expect(b).not.toMatch(/bounc/i);
    expect(b).not.toContain('about once a minute');
    for (const m of b.replace(/"[^"]*"/g, '').matchAll(/(\d+)-minute/g)) expect(['1', '5']).toContain(m[1]);
  });
});

describe('⏹ the two 1-minute /notifications details say retired, past tense (2026-11-18)', () => {
  for (const k of KINDS) {
    it(`${k}: RETIRED 2026-11-18 lead + LIVE SINCE 2026-10-29 + both 10-29 quotes + the shadow-days sentence`, () => {
      const d = CATEGORIES.find((c) => c.key === k)!.detail;
      expect(d.startsWith(`RETIRED 2026-11-18 — your call: "${HIS_RETIRE}"`)).toBe(true);
      expect(d).toContain('LIVE SINCE 2026-10-29');
      for (const h of HIS_29) expect(d).toContain(h);
      expect(d).toContain('From 2026-10-27 to 10-28 it ran in shadow');
      expect(d).toContain('WHAT FIRED:');
      expect(d).toContain('UNMEASURED');
    });
    it(`NEGATIVE ${k}: never "WHAT FIRES:", never a live/ON lead, never OFF BY DEFAULT or the b-word`, () => {
      const d = CATEGORIES.find((c) => c.key === k)!.detail;
      expect(d).not.toContain('WHAT FIRES:');
      expect(d).not.toMatch(/^ON FOR YOUR PHONE/);
      expect(d).not.toMatch(/OFF BY DEFAULT|this toggle changes nothing|until you say so|^SHADOW/);
      expect(d).not.toMatch(/bounc/i);
    });
  }
  it('NEGATIVE: 🚩 Gajjala\'s own (5-minute) kinds are not retired', () => {
    for (const k of ['gajjala_setup', 'gajjala_potential']) {
      const row = CATEGORIES.find((c) => c.key === k);
      expect(row, k).toBeTruthy();
      expect(row!.detail).not.toContain('RETIRED 2026-11-18');
    }
  });
});
