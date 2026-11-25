import { describe, expect, it } from 'vitest';
import { CM_TABS, ENTERABLE_KIND, GAJJALA_OWN_PARAMS, GAJJALA_TABS, LUK_OWN_PARAMS, TAB_META, isBoardTab, parseTab, tabSearch, type CmTab } from './chartMaps';
import { BURST_EXEMPT } from './momentumBurst';

/* 🥇 Luk's tab registry (2026-11-01, luk spec §3.13 / WP-E). Ajay: "look at other winners of US stocks champion ship and
 * pic the next best one like Gajjala. Implement their strategy please if they have online resources." … "I need
 * something like Gajjlala that is exposed". Its slot is right after 🚩 Gajjala's 1-min, before 🕯️ Doji Sweep; it is not
 * a tile board; its own border rule (LUK_OWN_PARAMS — GAJJALA_TABS stays the three 🚩 pages). NEGATIVES throughout. */
const sw = (q: string, t: CmTab) => new URLSearchParams(tabSearch(new URLSearchParams(q), t));
const ASK = ['look at other winners of US stocks champion ship and pic the next best one like Gajjala. Implement their strategy please if they have online resources.',
  'I need something like Gajjlala that is exposed'];

describe('🥇 Luk\'s — tab slot', () => {
  it('sits once, right after gajjala_1m and right before doji_sweep', () => {
    expect(CM_TABS.filter((t) => t === 'luk')).toHaveLength(1);
    // WIDENED 2026-11-15 — 👀 gajjala_watch sits between gajjala_1m and luk (gajjala-watch spec §3.8)
    // RE-PINNED 2026-11-18 — 🎬 replays between 👀 gajjala_watch and 🥇 luk (Ajay: "Can you put replays tab next to the Gajjala's please")
    expect(CM_TABS.indexOf('replays')).toBe(CM_TABS.indexOf('gajjala_watch') + 1);
    expect(CM_TABS.indexOf('luk')).toBe(CM_TABS.indexOf('replays') + 1);
    expect(CM_TABS.indexOf('gajjala_watch')).toBe(CM_TABS.indexOf('gajjala_1m') + 1);
    expect(CM_TABS.indexOf('doji_sweep')).toBe(CM_TABS.indexOf('luk') + 1);
    expect(parseTab('luk')).toBe('luk');
    expect(parseTab(' LUK ')).toBe('luk');
  });
  it('NEGATIVE: near-miss spellings are not the tab', () => {
    for (const raw of ['luks', "luk's", 'martin_luk', 'lu k']) expect(parseTab(raw)).not.toBe('luk');
  });
});

describe('🥇 Luk\'s — not a tile board, not a 🚩 page', () => {
  it('isBoardTab is false; BURST_EXEMPT names its reason', () => {
    expect(isBoardTab('luk')).toBe(false);
    expect(BURST_EXEMPT.luk).toMatch(/his setup state orders this board/);
    expect(BURST_EXEMPT.luk).not.toMatch(new RegExp('b' + 'ounce', 'i'));
  });
  it('NEGATIVE: GAJJALA_TABS is still exactly the three 🚩 pages; ENTERABLE_KIND has no luk', () => {
    expect(GAJJALA_TABS).toEqual(['gajjala', 'gajjala_audited', 'gajjala_1m']);
    expect(Object.prototype.hasOwnProperty.call(ENTERABLE_KIND, 'luk')).toBe(false);
  });
});

describe('🥇 Luk\'s — TAB_META', () => {
  const m = TAB_META.luk;
  /* 2026-11-01 (luk-live spec §3.7): Ajay "Lets make it live. also alerts too." — the blurb says live + his quote.
   * RE-PINNED 2026-11-25 (Ajay: "Kill the alerts on 1 min time frame they are not reliable"): shadow, never sent since 2026-11-25 + his 11-25 words; the 11-01 words kept as history. */
  it('the label and his asks verbatim, shadow + never sent since 2026-11-25 + both quotes, UNMEASURED, 2026-11-01', () => {
    expect(m.label).toBe("🥇 Luk's");
    for (const w of [...ASK, 'recorded in shadow, never sent, since 2026-11-25', '"Kill the alerts on 1 min time frame they are not reliable"',
      'rang your phone 2026-11-01 to 2026-11-24', '"Lets make it live. also alerts too."',
      'UNMEASURED', 'starts 2026-11-01', 'Not advice.']) {
      expect(m.blurb).toContain(w);
    }
  });
  it('NEGATIVE: the live sentence is gone now that it is shadow (RE-PINNED 2026-11-25 (Ajay: "Kill the alerts on 1 min time frame they are not reliable"))', () => {
    expect(m.blurb).not.toContain('rings your phone');
  });
  it('NEGATIVE: no b-word, no "edge", no house forecast word (chart_maps/high_beta_tab.FORBIDDEN_WORDS), no win rate', () => {
    const b = `${m.label} ${m.blurb}`;
    expect(b).not.toMatch(new RegExp(['b' + 'ounce', 'fake', 'rebound', 'will reverse', 'poised', 'expected to', 'likely to',
      'potential to', "won't drop", 'won’t drop', 'predict'].join('|'), 'i'));
    expect(b).not.toMatch(/\bedge\b/i);
    expect(b).not.toMatch(/win rate/i);
    expect(m.label).not.toBe(TAB_META.gajjala.label);
  });
});

describe('🥇 Luk\'s — the border rule (tabSearch over LUK_OWN_PARAMS)', () => {
  it('LUK_OWN_PARAMS = sub, span, cat, sort (2026-11-02: + the 🏁 category / wins-first chips)', () => {
    expect(LUK_OWN_PARAMS).toEqual(['sub', 'span', 'cat', 'sort']);
  });
  it('NEGATIVE (2026-11-02): luk → zones drops the 🏁 cat / sort; other params ride', () => {
    const next = sw('tab=luk&sub=track_record&span=5d&cat=win&sort=rang&universe=full', 'zones');
    for (const k of ['sub', 'span', 'cat', 'sort']) expect(next.has(k)).toBe(false);
    expect(next.get('universe')).toBe('full');
  });
  it('NEGATIVE (2026-11-02): another tab → luk drops a stray cat / sort', () => {
    const next = sw('tab=zones&cat=win&sort=change', 'luk');
    expect(next.get('tab')).toBe('luk');
    expect(next.has('cat')).toBe(false);
    expect(next.has('sort')).toBe(false);
  });
  it('a click on luk itself keeps cat / sort (2026-11-02)', () => {
    const next = sw('tab=luk&sub=track_record&cat=loss&sort=rang', 'luk');
    expect(next.get('cat')).toBe('loss');
    expect(next.get('sort')).toBe('rang');
  });
  it('NEGATIVE: luk → zones drops sub / span; other params ride', () => {
    const next = sw('tab=luk&sub=premarket&span=5d&universe=full', 'zones');
    expect(next.get('tab')).toBe('zones');
    expect(next.has('sub')).toBe(false);
    expect(next.has('span')).toBe(false);
    expect(next.get('universe')).toBe('full');
  });
  it('NEGATIVE: catalysts → luk drops the catalysts `sub` (it means something else there)', () => {
    const next = sw('tab=catalysts&sub=medical&span=10d', 'luk');
    expect(next.get('tab')).toBe('luk');
    expect(next.has('sub')).toBe(false);
    expect(next.has('span')).toBe(false);
  });
  it('NEGATIVE: luk ↔ gajjala_1m drops sub / span and the 🚩 params both ways', () => {
    const a = sw('tab=gajjala_1m&sub=bull_flag&tf=1m&sort=change&span=today', 'luk');
    for (const k of [...GAJJALA_OWN_PARAMS, ...LUK_OWN_PARAMS]) expect(a.has(k)).toBe(false);
    const b = sw('tab=luk&sub=track_record&span=all', 'gajjala_1m');
    for (const k of LUK_OWN_PARAMS) expect(b.has(k)).toBe(false);
  });
  it('a click on luk itself keeps them', () => {
    const next = sw('tab=luk&sub=track_record&span=all', 'luk');
    expect(next.get('sub')).toBe('track_record');
    expect(next.get('span')).toBe('all');
  });
});
