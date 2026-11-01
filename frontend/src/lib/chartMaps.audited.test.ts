import { describe, expect, it } from 'vitest';
import { CM_TABS, GAJJALA_OWN_PARAMS, GAJJALA_TABS, TAB_META, isBoardTab, parseTab, tabSearch, type CmTab } from './chartMaps';
import { GG_VARIANT_BASE, ggBase, ggVariantKey } from '../components/ggVariant';

/* 🧪 Gajjala · Audited tab registry (2026-11-01, gg-audited spec §3.8 / §4 WP-E). Ajay: "I would like you to create a
 * new tab for Gajjals when you modifiy with audit of End of day.." "Gajjals-Audited" "So we can keep track of
 * improvements on this tab". Its slot is right after 🚩 Gajjala's (design #7), before 🚩 Gajjala's 1-min; it is not a
 * tile board; the 🚩 border rule (tabSearch over GAJJALA_TABS) covers it; its endpoint base == backend variant.py
 * GGA.api_base. NEGATIVES: the border drops sub / tf / sort both ways; unknown variant keys stay 🚩 Gajjala's. */
const sw = (q: string, t: CmTab) => new URLSearchParams(tabSearch(new URLSearchParams(q), t));
const ASK = ['I would like you to create a new tab for Gajjals when you modifiy with audit of End of day..',
  'Gajjals-Audited', 'So we can keep track of improvements on this tab'];

describe('🧪 Gajjala · Audited — tab slot (2026-11-01)', () => {
  it('sits once: gajjala → gajjala_audited → gajjala_1m → doji_sweep', () => {
    expect(CM_TABS.filter((t) => t === 'gajjala_audited')).toHaveLength(1);
    expect(CM_TABS.indexOf('gajjala_audited')).toBe(CM_TABS.indexOf('gajjala') + 1);
    expect(CM_TABS.indexOf('gajjala_1m')).toBe(CM_TABS.indexOf('gajjala_audited') + 1);
    expect(CM_TABS.indexOf('doji_sweep')).toBe(CM_TABS.indexOf('gajjala_1m') + 1);
    expect(parseTab('gajjala_audited')).toBe('gajjala_audited');
    // NEGATIVE: the hyphenated endpoint spelling and his own spelling are not tab ids
    expect(parseTab('gajjala-audited')).not.toBe('gajjala_audited');
    expect(parseTab('gajjals-audited')).not.toBe('gajjala_audited');
  });

  it('is not a tile board (its own endpoint) — NEGATIVE: gajjala / gajjala_1m still are not either', () => {
    expect(isBoardTab('gajjala_audited')).toBe(false);
    expect(isBoardTab('gajjala')).toBe(false);
    expect(isBoardTab('gajjala_1m')).toBe(false);
    expect(GAJJALA_TABS).toEqual(['gajjala', 'gajjala_audited', 'gajjala_1m']);
  });

  it('TAB_META: the label, his ask verbatim, shadow, UNMEASURED', () => {
    const m = TAB_META.gajjala_audited;
    expect(m.label).toBe('🧪 Gajjala · Audited');
    for (const w of [...ASK, 'G1 · G2 · G4', 'G3 is lane-only', 'listed, never hidden', 'recorded in shadow, never sent',
      'starts 2026-11-01', 'UNMEASURED', 'Not advice.']) expect(m.blurb).toContain(w);
  });

  it('NEGATIVE: the blurb never says the b-word / "fake", never claims an edge or a win rate, never says it rings', () => {
    const b = TAB_META.gajjala_audited.blurb;
    expect(b).not.toMatch(new RegExp(['b' + 'ounce', 'fake'].join('|'), 'i'));
    expect(b).not.toMatch(/edge|win rate|rings your phone|phone rings/i);
    expect(TAB_META.gajjala_audited.label).not.toBe(TAB_META.gajjala.label);
    expect(TAB_META.gajjala_audited.label).not.toBe(TAB_META.gajjala_1m.label);
  });
});

describe('🧪 Gajjala · Audited — the 🚩 border rule (tabSearch)', () => {
  it('NEGATIVE: gajjala → gajjala_audited drops sub / tf / sort; other params ride', () => {
    const next = sw('tab=gajjala&sub=premarket&tf=15m&sort=change&universe=full', 'gajjala_audited');
    expect(next.get('tab')).toBe('gajjala_audited');
    for (const k of GAJJALA_OWN_PARAMS) expect(next.has(k)).toBe(false);
    expect(next.get('universe')).toBe('full');
  });

  it('NEGATIVE: gajjala_audited → gajjala drops them too', () => {
    const next = sw('tab=gajjala_audited&sub=bull_flag&tf=5m&sort=change', 'gajjala');
    expect(next.get('tab')).toBe('gajjala');
    for (const k of GAJJALA_OWN_PARAMS) expect(next.has(k)).toBe(false);
  });

  it('NEGATIVE: gajjala_audited ↔ gajjala_1m drops them both ways', () => {
    for (const [from, to] of [['gajjala_audited', 'gajjala_1m'], ['gajjala_1m', 'gajjala_audited']] as const) {
      const next = sw(`tab=${from}&sub=track_record&tf=5m&sort=change`, to);
      expect(next.get('tab')).toBe(to);
      for (const k of GAJJALA_OWN_PARAMS) expect(next.has(k)).toBe(false);
    }
  });

  it('NEGATIVE: gajjala_audited → support drops them (the border rule on the new tab)', () => {
    const next = sw('tab=gajjala_audited&sub=bull_flag&tf=5m&symbol=AAPL', 'support');
    for (const k of GAJJALA_OWN_PARAMS) expect(next.has(k)).toBe(false);
    expect(next.get('symbol')).toBe('AAPL');
  });

  it('a click on the tab it is already on keeps sub / tf / sort', () => {
    const next = sw('tab=gajjala_audited&sub=track_record&tf=15m&sort=wins', 'gajjala_audited');
    expect(next.get('sub')).toBe('track_record');
    expect(next.get('tf')).toBe('15m');
    expect(next.get('sort')).toBe('wins');
  });
});

describe('🧪 Gajjala · Audited — the endpoint base (ggVariant)', () => {
  it('GG_VARIANT_BASE.gajjala_audited == backend variant.py GGA.api_base', () => {
    expect(GG_VARIANT_BASE.gajjala_audited).toBe('/chart-maps/gajjala-audited');
    expect(ggBase('gajjala_audited')).toBe('/chart-maps/gajjala-audited');
    expect(ggVariantKey('gajjala_audited')).toBe('gajjala_audited');
  });

  it('NEGATIVE: an unknown key is 🚩 Gajjala’s; the other two bases never moved', () => {
    for (const k of [undefined, null, '', 'gga', 'GAJJALA_AUDITED', 'gajjala-audited', 'gajjals_audited', 42]) {
      expect(ggVariantKey(k)).toBe('gajjala');
    }
    expect(GG_VARIANT_BASE.gajjala).toBe('/chart-maps/gajjala');
    expect(GG_VARIANT_BASE.gajjala_1m).toBe('/chart-maps/gajjala-1m');
  });
});
