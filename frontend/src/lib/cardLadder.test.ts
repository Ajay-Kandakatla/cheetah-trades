import { describe, it, expect, afterEach, vi } from 'vitest';
import {
  cardLadder, orderChips, readMoreExpandPref, writeMoreExpandPref, CM_MORE_EXPAND_KEY,
  FOLD_GROUPS, planLineKey, type Ladder,
} from './cardLadder';
import { pxText, nowLabelText, type CmBadge, type CmTile } from './chartMaps';
import { VOYA, CBL, HCSG, ORKA_LIKE, EVERY_LITERAL } from './__fixtures__/cardLadder.tiles';

/* 📋 The entry ladder's classifier (Ajay 2026-09-24: "I want them to
 * categorized in a good way so I have enough info for entry of a stock").
 * Live tiles first, then every served literal, then the negatives the spec
 * requires. Strings only — the classifier never parses a number. */

const texts = (bs: CmBadge[]) => bs.map((b) => b.text);
const foldTexts = (l: Ladder, g: keyof Ladder['more']) =>
  l.more[g].map((it) => it.badge?.text ?? it.stat?.k ?? `slot:${it.slot}`);

/** Every string the ladder would print, for the NaN / undefined sweep. */
function allStrings(l: Ladder): string[] {
  const out: string[] = [];
  const walk = (v: unknown) => {
    if (typeof v === 'string') out.push(v);
    else if (Array.isArray(v)) v.forEach(walk);
    else if (v && typeof v === 'object') Object.values(v).forEach(walk);
  };
  walk(l);
  return out;
}

const bare = (over: Partial<CmTile> = {}): CmTile => ({
  symbol: 'ZZZ', href: '/sepa/ZZZ', bars: [{ t: '2026-09-24', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [], lines: [], markers: [], stats: [], why: '', ...over,
});

describe('cardLadder — live Back in Demand tiles (2026-09-24)', () => {
  it('VOYA: 🎯 alone in ENTRY, the approach line in PRICE, six reads folded', () => {
    const l = cardLadder(VOYA);
    expect(l.enterableOnFace).toBe(true);
    expect(l.entry).toEqual([]);
    expect(l.approach?.text).toBe('↓ Came down from 97.37 (-1.3% today), holding 0.3% off the 95.78 low');
    expect(l.why).toBeNull();
    expect(l.plan.buyZone).toEqual({ lo: 94.86, hi: 97.08 });
    expect(l.plan.lines.map((x) => x.tone)).toEqual(['buy', 'stop', 'target']);
    expect(l.plan.stats.map((s) => s.k)).toEqual(['R:R', 'room']);
    expect(texts(l.timing.badges)).toEqual(['📌 2 board days · since Sep 24']);
    expect(l.timing.stats.map((s) => s.k)).toEqual(['Back in']);
    expect(foldTexts(l, 'risk')).toEqual(['Break-even', 'Liquidity', 'slot:last']);
    expect(foldTexts(l, 'tape')).toEqual(['Float/day']);
    expect(foldTexts(l, 'sector')).toEqual(['— sector flat Financial Services -0.5% vs RSP (5d)']);
    expect(foldTexts(l, 'reads')).toEqual(['slot:zone']);
    expect(l.zone).toEqual({ text: 'At Demand · favorable', tone: 'muted', onFace: false });
    expect(l.moreCount).toBe(6);
    expect(l.moreWarn).toEqual([]);
    expect(l.dropped).toEqual(expect.arrayContaining(['Bands', 'why-tail', 'On board', 'Sector flow (5d)']));
    expect(l.plan.lastOnFace).toBe(false);          // Last 96.09 === entry 96.09
  });

  it('CBL: five folded, the long room value is carried whole', () => {
    const l = cardLadder(CBL);
    expect(l.moreCount).toBe(5);
    expect(l.plan.stats.find((s) => s.k === 'room')!.v).toBe('+6.6% -> 55.78 · weak 53.01 first');
    expect(l.approach?.tone).toBe('good');
  });

  it('HCSG: At Supply · caution sits on the face in amber; four folded', () => {
    const l = cardLadder(HCSG);
    expect(l.zone).toEqual({ text: 'At Supply · caution', tone: 'warn', onFace: true });
    expect(l.moreCount).toBe(4);
    expect(foldTexts(l, 'reads')).toEqual([]);
  });

  it('ORKA-like: ⛔ in ENTRY, the floor detail + cold sector folded (10), the cold sector flagged', () => {
    const l = cardLadder(ORKA_LIKE);
    expect(l.enterableOnFace).toBe(true);
    expect(l.entryNotes).toEqual(['weak day']);
    expect(texts(l.priceAfter)).toEqual(['🔻 Still distributing — CMF -0.07']);
    expect(foldTexts(l, 'floor')).toEqual(['Band', 'Liquidity swept', '🎯 swept the stops']);
    expect(foldTexts(l, 'tape')).toEqual(['Float/day', 'Dark heavy']);
    expect(l.moreCount).toBe(10);
    expect(texts(l.moreWarn)).toEqual(['🧊 cold sector Biotechnology -2.1% vs RSP (5d)']);
    expect(l.dropped).toContain('Sector flow (5d)');
  });
});

describe('cardLadder — every served literal lands in its rung', () => {
  const tile = bare({ badges: EVERY_LITERAL.map(([text]) => ({ text, tone: 'muted' as const })) });
  const l = cardLadder(tile);
  const where = (text: string): string => {
    const face: Array<[string, CmBadge[]]> = [
      ['ident', l.ident], ['entry', l.entry], ['price', l.price], ['priceAfter', l.priceAfter],
      ['plan', l.plan.pills], ['timing', l.timing.badges], ['setup', l.setup.badges],
    ];
    for (const [k, xs] of face) if (xs.some((b) => b.text === text)) return k;
    for (const g of FOLD_GROUPS) if (l.more[g].some((it) => it.badge?.text === text)) return g;
    return 'nowhere';
  };
  for (const [text, rung] of EVERY_LITERAL) {
    it(`${text} → ${rung}`, () => expect(where(text)).toBe(rung));
  }
  it('the Holdings cost line leads ENTRY; the rest are warn → good → muted', () => {
    const l2 = cardLadder(bare({ badges: [
      { text: 'Qualifier', tone: 'muted' }, { text: '🔪 falling knife', tone: 'warn' },
      { text: 'Buyable', tone: 'good' }, { text: '-10.5% vs your cost', tone: 'warn' },
    ] }));
    expect(texts(l2.entry)).toEqual(['-10.5% vs your cost', '🔪 falling knife', 'Buyable', 'Qualifier']);
  });
});

describe('cardLadder — NEGATIVE cases', () => {
  it('1. an unknown badge goes to SETUP on the face, never the fold', () => {
    const l = cardLadder(bare({ badges: [{ text: '🦄 brand new chip', tone: 'warn' }] }));
    expect(texts(l.setup.badges)).toEqual(['🦄 brand new chip']);
    expect(l.moreCount).toBe(0);
  });

  it('2. an unknown stat key goes to SETUP, never dropped', () => {
    const l = cardLadder(bare({ stats: [{ k: 'Mystery', v: '42' }] }));
    expect(l.setup.stats).toEqual([{ k: 'Mystery', v: '42' }]);
    expect(l.dropped).toEqual([]);
  });

  it('3. a Bands stat whose text differs from the 🪜 sentence → both render', () => {
    const t = { ...VOYA, stats: VOYA.stats.map((s) => (s.k === 'Bands' ? { ...s, v: s.v + ' ' } : s)) };
    const l = cardLadder(t);
    expect(l.plan.stats.map((s) => s.k)).toContain('Bands');
    expect(l.dropped).not.toContain('Bands');
  });

  it('4. a why whose tail does not match the approach is shown whole; the zone gets no head word', () => {
    const l = cardLadder({ ...HCSG, why: 'caution — something else entirely' });
    expect(l.why).toBe('caution — something else entirely');
    expect(l.zone?.text).toBe('At Supply');
    expect(l.dropped).not.toContain('why-tail');
  });

  it('5. On board 3d beside a 2-day 📌 pill → both render; stats stay when their pill is absent', () => {
    const l = cardLadder({ ...VOYA, stats: VOYA.stats.map((s) => (s.k === 'On board' ? { ...s, v: '3d' } : s)) });
    expect(l.timing.stats.map((s) => s.k)).toEqual(['Back in', 'On board']);
    expect(texts(l.timing.badges)).toEqual(['📌 2 board days · since Sep 24']);
    const noPills = cardLadder({ ...VOYA, badges: [] });
    expect(noPills.timing.mergedBoard).toBe('On board 2d · Back in 1d');
    expect(foldTexts(noPills, 'tape')).toEqual(['Float/day']);
    expect(foldTexts(noPills, 'sector')).toEqual(['Sector flow (5d)']);
    expect(noPills.dropped).not.toContain('On board');
    expect(noPills.dropped).not.toContain('Sector flow (5d)');
  });

  it('6. 🐆 2.7%/day beside Float/day 2.66% → both stay in TAPE (dedupe only on equality)', () => {
    const l = cardLadder(bare({
      badges: [{ text: '🐆 Fast supply — 2.7%/day', tone: 'good' }],
      stats: [{ k: 'Float/day', v: '2.66%' }],
    }));
    expect(foldTexts(l, 'tape')).toEqual(['Float/day', '🐆 Fast supply — 2.7%/day']);
    const same = cardLadder(bare({
      badges: [{ text: '🐆 Fast supply — 2.7%/day', tone: 'good' }],
      stats: [{ k: 'Float/day', v: '2.7%' }],
    }));
    expect(foldTexts(same, 'tape')).toEqual(['🐆 Fast supply — 2.7%/day']);
  });

  it('7. Last ≠ every plan price → on the face; Last === the entry → fold RISK', () => {
    const moved = { ...VOYA, bars: [...VOYA.bars.slice(0, -1), { ...VOYA.bars[VOYA.bars.length - 1], c: 96.5 }] };
    const l = cardLadder(moved);
    expect(l.plan.lastOnFace).toBe(true);
    expect(foldTexts(l, 'risk')).not.toContain('slot:last');
    expect(cardLadder(VOYA).plan.lastOnFace).toBe(false);
  });

  it('8. no served band → no buy zone; NaN / undefined prices never reach a label', () => {
    const noBand = cardLadder({ ...VOYA, enterable: { ...VOYA.enterable!, band: null } });
    expect(noBand.plan.buyZone).toBeNull();
    const junk = cardLadder({
      ...VOYA,
      lines: [{ price: NaN, label: 'BUY', tone: 'buy' }, { price: undefined as any, label: 'STOP', tone: 'stop' }],
      enterable: { ...VOYA.enterable!, band: { lo: NaN, hi: undefined as any } },
    });
    for (const s of allStrings(junk)) {
      expect(s).not.toMatch(/NaN|undefined/);
    }
  });

  it('9. pxText: 3 dp under a dollar, 2 above, null for non-numbers; nowLabelText unchanged', () => {
    expect(pxText(0.4567)).toBe('0.457');
    expect(pxText(96.09)).toBe('96.09');
    expect(pxText(NaN)).toBeNull();
    expect(pxText(undefined)).toBeNull();
    expect(pxText('96.09')).toBeNull();
    expect(pxText(Infinity)).toBeNull();
    expect(nowLabelText('now', 4.17)).toBe('now 4.17');
    expect(nowLabelText('now', 0.4567)).toBe('now 0.457');
    expect(nowLabelText('now', NaN)).toBe('now');
  });

  it('10. At_Demand folds into READS; At_Supply / Mid_Range / Clear_Runway sit in ENTRY', () => {
    for (const st of ['At_Supply', 'Mid_Range', 'Clear_Runway']) {
      const l = cardLadder(bare({ badges: [{ text: st, tone: 'muted' }] }));
      expect(l.zone?.onFace).toBe(true);
      expect(l.zone?.text).toBe(st.split('_').join(' '));
      expect(foldTexts(l, 'reads')).toEqual([]);
    }
    const d = cardLadder(bare({ badges: [{ text: 'At_Demand', tone: 'muted' }] }));
    expect(d.zone?.onFace).toBe(false);
    expect(foldTexts(d, 'reads')).toEqual(['slot:zone']);
  });

  it('10b. only supply-side zone states tint amber; Clear Runway / Mid Range stay muted', () => {
    for (const st of ['At_Supply', 'Into_Supply', 'Extended_No_Support']) {
      const l = cardLadder(bare({ badges: [{ text: st, tone: 'muted' }] }));
      expect(l.zone?.tone, st).toBe('warn');
    }
    for (const st of ['Clear_Runway', 'Mid_Range']) {
      const l = cardLadder(bare({ badges: [{ text: st, tone: 'muted' }] }));
      expect(l.zone?.onFace, st).toBe(true);
      expect(l.zone?.tone, st).toBe('muted');
    }
    const d = cardLadder(bare({ badges: [{ text: 'At_Demand', tone: 'muted' }] }));
    expect(d.zone?.tone).toBe('muted');
  });

  it('11. an empty tile (the IndexZones shape) → every rung empty, nothing folded', () => {
    const l = cardLadder(bare({ bars: [] }));
    expect([l.ident, l.entry, l.price, l.priceAfter, l.setup.badges, l.setup.stats, l.plan.pills,
            l.plan.stats, l.plan.lines, l.timing.badges, l.timing.stats].every((x) => x.length === 0)).toBe(true);
    expect(l.approach).toBeNull();
    expect(l.zone).toBeNull();
    expect(l.why).toBeNull();
    expect(l.moreCount).toBe(0);
    expect(l.moreWarn).toEqual([]);
  });

  it('12. grouped study badges (amd / keltner) are in no ladder bucket', () => {
    const l = cardLadder(ORKA_LIKE);
    const every = allStrings(l);
    expect(every).not.toContain('AMD raided · today');
    expect(every).not.toContain('KC lower half · squeeze 3b · 0.61× wide');
  });

  it('13. a folded warn chip is flagged; 🔪 falling knife is ENTRY, never moreWarn', () => {
    const l = cardLadder(bare({ badges: [
      { text: '🔪 band broken', tone: 'warn' }, { text: '🔪 falling knife', tone: 'warn' },
    ] }));
    expect(texts(l.moreWarn)).toEqual(['🔪 band broken']);
    expect(texts(l.entry)).toEqual(['🔪 falling knife']);
    const calm = cardLadder(bare({ badges: [{ text: '— sector flat X +0.1% vs RSP (5d)', tone: 'muted' }] }));
    expect(calm.moreWarn).toEqual([]);
  });

  it('14. null / [] / junk badges and stats never throw', () => {
    for (const junk of [null, undefined, [], 'x', 7, [null, 3, { text: 5 }, { k: 1 }, {}]]) {
      expect(() => cardLadder(bare({ badges: junk as any, stats: junk as any, lines: junk as any }))).not.toThrow();
    }
    expect(() => cardLadder(null as any)).not.toThrow();
  });

  it('15. the input is never reordered or mutated (frozen)', () => {
    const t = JSON.parse(JSON.stringify(ORKA_LIKE));
    const deepFreeze = (o: any) => { Object.values(o).forEach((v) => v && typeof v === 'object' && deepFreeze(v)); return Object.freeze(o); };
    deepFreeze(t);
    const before = JSON.stringify(t);
    expect(() => cardLadder(t)).not.toThrow();
    expect(JSON.stringify(t)).toBe(before);
  });

  it('orderChips is stable: ties keep the served order', () => {
    const bs: CmBadge[] = [
      { text: 'a', tone: 'muted' }, { text: 'b', tone: 'warn' }, { text: 'c', tone: 'muted' },
      { text: 'd', tone: 'good' }, { text: 'e', tone: 'warn' },
    ];
    expect(texts(orderChips(bs))).toEqual(['b', 'e', 'd', 'a', 'c']);
  });

  it('outerChips: a chip the wrapper prints neither renders nor counts in the fold', () => {
    const t = { ...VOYA, explosive: { room: null } as any };
    expect(foldTexts(cardLadder(t), 'reads')).toEqual(['slot:explosive', 'slot:zone']);
    expect(foldTexts(cardLadder(t, { skip: ['explosive'] }), 'reads')).toEqual(['slot:zone']);
    expect(cardLadder(VOYA, { skip: ['enterable'] }).enterableOnFace).toBe(false);
  });

  it('the n/a enterable kind folds into READS, never the face', () => {
    const l = cardLadder(bare({ enterable: { kind: 'n/a', verdict: null, reasons: [], reason_text: [], reason_short: [] } }));
    expect(l.enterableOnFace).toBe(false);
    expect(foldTexts(l, 'reads')).toEqual(['slot:enterable']);
  });
});

describe('⊞ expand-all preference (the 🔥 Hottest convention)', () => {
  const mem = () => {
    const m = new Map<string, string>();
    return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
             setItem: (k: string, v: string) => { m.set(k, String(v)); } };
  };
  afterEach(() => { vi.unstubAllGlobals(); });

  it('never chosen → null (closed); open / closed round-trip under its own key', () => {
    const store = mem();
    vi.stubGlobal('localStorage', store);
    expect(readMoreExpandPref()).toBeNull();
    writeMoreExpandPref(true);
    expect(store.getItem(CM_MORE_EXPAND_KEY)).toBe('open');
    expect(readMoreExpandPref()).toBe(true);
    writeMoreExpandPref(false);
    expect(store.getItem(CM_MORE_EXPAND_KEY)).toBe('closed');
    expect(readMoreExpandPref()).toBe(false);
  });

  it('NEGATIVE: a junk value reads as never chosen; a throwing store is null, never a crash', () => {
    const store = mem();
    store.setItem(CM_MORE_EXPAND_KEY, 'yes please');
    vi.stubGlobal('localStorage', store);
    expect(readMoreExpandPref()).toBeNull();
    vi.stubGlobal('localStorage', {
      getItem: () => { throw new Error('blocked'); },
      setItem: () => { throw new Error('blocked'); },
    });
    expect(readMoreExpandPref()).toBeNull();
    expect(() => writeMoreExpandPref(true)).not.toThrow();
  });
});

describe('cardLadder — repair round 2026-09-25', () => {
  it('D4 NEGATIVE: a heat pill on one window beside a Sector flow stat it does not contain → both stay in SECTOR', () => {
    /* The 2026-09-10 inversion case: pill toned on 5d, stat on another read. */
    const l = cardLadder(bare({
      badges: [{ text: '🔥 hot sector Tech +2.1% vs RSP (5d)', tone: 'good' }],
      stats: [{ k: 'Sector flow (5d)', v: 'Tech -11.9%' }],
    }));
    expect(foldTexts(l, 'sector')).toEqual(expect.arrayContaining(
      ['🔥 hot sector Tech +2.1% vs RSP (5d)', 'Sector flow (5d)']));
    expect(foldTexts(l, 'sector')).toHaveLength(2);
    expect(l.dropped).not.toContain('Sector flow (5d)');
    /* POSITIVE twin: the stat's text IS in the pill → the stat drops. */
    const same = cardLadder(bare({
      badges: [{ text: '🔥 hot sector Tech +2.1% vs RSP (5d)', tone: 'good' }],
      stats: [{ k: 'Sector flow (5d)', v: 'Tech +2.1%' }],
    }));
    expect(same.dropped).toContain('Sector flow (5d)');
  });

  it('🎯 in PRICE only for the Gabbar position shapes; any other 🎯 badge lands in SETUP (the safety net)', () => {
    const l = cardLadder(bare({ badges: [
      { text: '🎯 In Gabbar band (aggressive)', tone: 'good' },
      { text: '🎯 1.4% above aggressive', tone: 'warn' },
      { text: '🎯 2.0% below aggressive 2', tone: 'warn' },
      { text: '🎯 something new', tone: 'muted' },
    ] }));
    expect(texts(l.price)).toEqual(expect.arrayContaining(
      ['🎯 In Gabbar band (aggressive)', '🎯 1.4% above aggressive', '🎯 2.0% below aggressive 2']));
    expect(texts(l.price)).not.toContain('🎯 something new');
    expect(texts(l.setup.badges)).toContain('🎯 something new');
    /* The swept-stops 🎯 is still FLOOR detail, never PRICE. */
    const sw = cardLadder(bare({ badges: [{ text: '🎯 swept the stops', tone: 'good' }] }));
    expect(texts(sw.price)).toEqual([]);
    expect(foldTexts(sw, 'floor')).toEqual(['🎯 swept the stops']);
  });

  it('planLineKey: the fixed word only for the canonical served label; anything else prints its own label', () => {
    expect(planLineKey('stop', 'STOP', 'Stop')).toBe('Stop');
    expect(planLineKey('target', 'TARGET', 'Target')).toBe('Target');
    expect(planLineKey('cost', 'your cost 12.34', 'Cost')).toBe('Cost');
    expect(planLineKey('ownstop', 'your stop 10.00', 'Your stop')).toBe('Your stop');
    /* NEGATIVE: Breaking's lid, Support's overhead, Holdings' 200d MA, a ceiling. */
    expect(planLineKey('target', 'BREAK', 'Target')).toBe('BREAK');
    expect(planLineKey('target', 'overhead 553.67', 'Target')).toBe('overhead 553.67');
    expect(planLineKey('target', 'ceiling 45.00', 'Target')).toBe('ceiling 45.00');
    expect(planLineKey('stop', '200d', 'Stop')).toBe('200d');
    expect(planLineKey('target', 'target', 'Target')).toBe('target');   // case differs → not canonical
    /* No served label → nothing contradicts the tone word. */
    expect(planLineKey('stop', '', 'Stop')).toBe('Stop');
    expect(planLineKey('stop', undefined, 'Stop')).toBe('Stop');
  });
});

describe('cardLadder — 🔑 key levels (2026-09-25)', () => {
  // Ajay 2026-09-25: "I wanna know when key levels are broken for a stock."
  // The chip and the fold line are SERVED strings (key_levels.tile_block);
  // the ladder only places them.
  const kl = (over: Record<string, unknown> = {}) => ({
    session: '2026-09-25', frame: 'daily', phase: 'rth', measured: false, verified: true,
    levels: [], drawn: [], rule: 'r', stale_note: null,
    chip: { text: '🔑 broke PWL 95.78 ↓ 10:42', tone: 'warn' },
    fold: '🔑 RTH levels · PWH 102.10 +2.0% · PWL 95.78 −1.2% broke 10:42',
    ...over,
  });
  const withKl = (block: unknown, over: Partial<CmTile> = {}) =>
    bare({ key_levels: block as any, ...over });

  it('the chip lands in PRICE (keyLevel) — not approach, SETUP, ENTRY, PLAN or the fold', () => {
    const l = cardLadder(withKl(kl(), {
      badges: [{ text: '↓ Came down from 97.37 (-1.3% today)', tone: 'muted' }],
    }));
    expect(l.keyLevel).toEqual({ text: '🔑 broke PWL 95.78 ↓ 10:42', tone: 'warn' });
    expect(l.approach?.text).toBe('↓ Came down from 97.37 (-1.3% today)');
    const everywhereElse = [
      ...texts(l.entry), ...texts(l.price), ...texts(l.priceAfter), ...texts(l.setup.badges),
      ...texts(l.plan.pills), ...texts(l.timing.badges), ...l.moreWarn.map((b) => b.text),
    ];
    expect(everywhereElse.some((t) => t.includes('broke PWL'))).toBe(false);
  });

  it('the close-phase wordings land in PRICE too', () => {
    for (const text of ['🔑 closed under PWL 95.78', '🔑 closed back over PWL 95.78',
      '🔑 after-hrs under PWL 95.78', '🔑 gapped through PWL 95.78 ↓', '🔑 broke PWH 102.10 ↑ · pre-mkt']) {
      expect(cardLadder(withKl(kl({ chip: { text, tone: 'warn' } }))).keyLevel?.text).toBe(text);
    }
  });

  it('the fold line is ONE READS item, and moreCount counts it', () => {
    const l = cardLadder(withKl(kl()));
    expect(foldTexts(l, 'reads')).toEqual(['slot:keylevels']);
    expect(l.moreCount).toBe(1);
    for (const g of FOLD_GROUPS.filter((x) => x !== 'reads')) expect(l.more[g]).toEqual([]);
  });

  it('NEGATIVE: no chip served → keyLevel null, but the fold line still folds', () => {
    const l = cardLadder(withKl(kl({ chip: null })));
    expect(l.keyLevel).toBeNull();
    expect(foldTexts(l, 'reads')).toEqual(['slot:keylevels']);
  });

  it('NEGATIVE: an empty / whitespace / non-string fold adds no fold item and no count', () => {
    for (const fold of [null, '', '   ', 42, undefined]) {
      const l = cardLadder(withKl(kl({ fold })));
      expect(foldTexts(l, 'reads')).toEqual([]);
      expect(l.moreCount).toBe(0);
    }
  });

  it('NEGATIVE: null, a missing block or a malformed one → no pill, no fold, no throw', () => {
    const junk: unknown[] = [
      null, undefined, 'x', 7, [], {},
      kl({ levels: 'nope' }), kl({ levels: null }),
      kl({ chip: { text: '', tone: 'warn' } }), kl({ chip: { text: '  ', tone: 'warn' } }),
      kl({ chip: { text: 42, tone: 'warn' } }), kl({ chip: 'broke PWL' }), kl({ chip: [] }),
    ];
    for (const block of junk) {
      let l: Ladder | null = null;
      expect(() => { l = cardLadder(withKl(block)); }).not.toThrow();
      expect(l!.keyLevel).toBeNull();
      expect(allStrings(l!).some((s) => s.includes('undefined') || s.includes('NaN'))).toBe(false);
    }
    // levels not an array → the whole block is malformed: nothing folds either
    expect(foldTexts(cardLadder(withKl(kl({ levels: 'nope' }))), 'reads')).toEqual([]);
  });

  it('NEGATIVE: an unknown chip tone reads as warn — a real break is never greyed', () => {
    expect(cardLadder(withKl(kl({ chip: { text: '🔑 broke PWL 95.78 ↓', tone: 'loud' } }))).keyLevel?.tone)
      .toBe('warn');
    expect(cardLadder(withKl(kl({ chip: { text: '🔑 broke PWL 95.78 ↓', tone: 'muted' } }))).keyLevel?.tone)
      .toBe('muted');
  });

  it('NEGATIVE: key lines never reach PLAN, and do not decide `Last` on the face', () => {
    const l = cardLadder(bare({
      bars: [{ t: '2026-09-24', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
      lines: [{ price: 1.5, label: '🔑 PWH 1.50', tone: 'key' },
              { price: 1.2, label: '🔑 PWL 1.20', tone: 'key_broken' }],
    }));
    expect(l.plan.lines).toEqual([]);
    expect(l.plan.lastOnFace).toBe(true);
  });

  it('NEGATIVE: the input tile is not mutated', () => {
    const t = Object.freeze(withKl(Object.freeze(kl())));
    expect(() => cardLadder(t)).not.toThrow();
  });
});

describe('cardLadder — 🔑 Key Levels tab position pill (2026-09-28)', () => {
  // Ajay 2026-09-28: "Also create me tab for keylevel main. Sort them by
  // stocks that are near lower keylevels". The tab serves one 🔑 badge per
  // tile (key_levels.near_text); the ladder routes it to PRICE, whole.
  const withBadge = (text: string, over: Partial<CmTile> = {}) =>
    bare({ badges: [{ text, tone: 'muted' }], ...over });

  it('a served 🔑 distance pill lands in PRICE', () => {
    const l = cardLadder(withBadge('🔑 0.41% above PWL 97.20'));
    expect(texts(l.price)).toEqual(['🔑 0.41% above PWL 97.20']);
    expect(texts(l.setup.badges)).toEqual([]);
  });

  it('the at / under-in-buffer wordings land in PRICE too', () => {
    for (const text of ['🔑 at PML 41.10', '🔑 0.10% under PWL 42.25 — not through (0.15% breaks it) · tested · day close']) {
      expect(texts(cardLadder(withBadge(text)).price)).toEqual([text]);
    }
  });

  it('a long served text (made … the last session / … tested (low went …)) stays ONE pill, untruncated', () => {
    const text = '🔑 0.22% above 52wL 33.60 · made Mon 09-28, the last session · Mon 09-28 tested (low went 1.18% under) · last close';
    const l = cardLadder(withBadge(text));
    expect(l.price).toHaveLength(1);
    expect(l.price[0].text).toBe(text);
    const elsewhere = [...texts(l.entry), ...texts(l.priceAfter), ...texts(l.setup.badges),
      ...texts(l.plan.pills), ...texts(l.timing.badges), ...l.moreWarn.map((b) => b.text)];
    expect(elsewhere.some((t) => t.includes('last session') || t.includes('low went'))).toBe(false);
    expect(l.moreCount).toBe(0);
  });

  it('NEGATIVE: the served key CHIP still lands in keyLevel, not duplicated into PRICE', () => {
    const l = cardLadder(bare({
      badges: [{ text: '🔑 0.41% above PWL 97.20', tone: 'muted' }],
      key_levels: {
        session: '2026-09-28', frame: 'daily', phase: 'rth', measured: false, verified: true,
        levels: [], drawn: [], rule: 'r', stale_note: null, fold: null,
        chip: { text: '🔑 broke PML 95.10 ↓ 10:42', tone: 'warn' },
      },
    }));
    expect(l.keyLevel).toEqual({ text: '🔑 broke PML 95.10 ↓ 10:42', tone: 'warn' });
    expect(texts(l.price)).toEqual(['🔑 0.41% above PWL 97.20']);
    expect(texts(l.price).some((t) => t.includes('broke PML'))).toBe(false);
  });

  it('NEGATIVE: an unknown non-🔑 badge still falls through to SETUP', () => {
    const l = cardLadder(withBadge('Something the ladder never heard of'));
    expect(texts(l.setup.badges)).toEqual(['Something the ladder never heard of']);
    expect(l.price).toEqual([]);
  });

  it('NEGATIVE: a bare 🔑 with no space is not a position pill', () => {
    const l = cardLadder(withBadge('🔑'));
    expect(l.price).toEqual([]);
    expect(texts(l.setup.badges)).toEqual(['🔑']);
  });
});

describe('cardLadder — 🏎️ Dual Momentum tab (2026-09-29)', () => {
  const RANK = '\u{1F3CE}\u{FE0F} #3 dual momentum';          // dual_momentum_tab.RANK_CHIP_FMT
  const DIST = '→ 3.21% above the demand band';            // board._dist_badge
  const NO_BAND = '→ no demand band under the price';      // NO_BAND_TEXT
  const NO_DOC = '→ no demand band — no stored bands for this name';
  const NO_PRINT = '→ no print to read the bands against';
  const dmTile = (over: Partial<CmTile> = {}): CmTile => bare({
    symbol: 'DMX',
    badges: [{ text: RANK, tone: 'good' }, { text: DIST, tone: 'warn' }],
    stats: [
      { k: '12m', v: '+566.1%' }, { k: '6m', v: '+120.4%' }, { k: '3m', v: '+31.0%' },
      { k: '1m', v: '+4.2%' }, { k: 'RS', v: '97' },
      { k: 'Room', v: '+12.4% -> 52.30' }, { k: 'Band', v: 'floor intact' },
    ],
    why: '\u{1F3CE}\u{FE0F} #3 dual momentum · 12m +566.1% · 3.21% above its demand band 45.10–46.00 · room +12.4% -> 52.30 · floor intact',
    ...over,
  });

  it('the served rank chip routes to IDENT, the distance badge to PRICE', () => {
    const l = cardLadder(dmTile());
    expect(texts(l.ident)).toEqual([RANK]);
    expect(texts(l.price)).toEqual([DIST]);
    expect(texts(l.setup.badges)).toEqual([]);
  });

  it('Room lands in PLAN, Band in the FLOOR fold, the returns and RS in SETUP; no To band', () => {
    const l = cardLadder(dmTile());
    expect(l.plan.stats.map((s) => s.k)).toEqual(['Room']);
    expect(foldTexts(l, 'floor')).toEqual(['Band']);
    expect(l.setup.stats.map((s) => s.k)).toEqual(['12m', '6m', '3m', '1m', 'RS']);
    const keys = [...l.plan.stats, ...l.setup.stats, ...l.timing.stats].map((s) => s.k);
    expect(keys).not.toContain('To band');
  });

  it('the distance to the band is printed EXACTLY ONCE across the rungs (critic 9a, Rule #5)', () => {
    const l = cardLadder(dmTile());
    const rungs = allStrings({ ...l, why: null });
    expect(rungs.filter((s) => s.includes('3.21%'))).toHaveLength(1);
  });

  it('the three NO_* texts route to PRICE, never to SETUP', () => {
    for (const t of [NO_BAND, NO_DOC, NO_PRINT]) {
      const l = cardLadder(dmTile({ badges: [{ text: RANK, tone: 'good' }, { text: t, tone: 'muted' }] }));
      expect(texts(l.price), t).toEqual([t]);
      expect(texts(l.setup.badges), t).toEqual([]);
    }
  });

  it('NEGATIVE: 🏎 WITHOUT the VS16, and a 🏎️ badge that is not "#rank", do NOT route to IDENT', () => {
    const noVs = '\u{1F3CE} #3 dual momentum';
    const other = '\u{1F3CE}\u{FE0F} Dual momentum leader';
    const l = cardLadder(bare({ badges: [{ text: noVs, tone: 'good' }, { text: other, tone: 'good' }] }));
    expect(texts(l.ident)).toEqual([]);
    expect(texts(l.setup.badges)).toEqual([noVs, other]);
  });

  it('NEGATIVE: no NaN / undefined / [object Object] anywhere on a DM ladder', () => {
    for (const s of allStrings(cardLadder(dmTile()))) {
      expect(s.includes('NaN'), s).toBe(false);
      expect(s.includes('undefined'), s).toBe(false);
      expect(s.includes('[object Object]'), s).toBe(false);
    }
  });
});

describe('cardLadder — 🏔️ ATH tab pills (2026-09-29)', () => {
  // Ajay 2026-09-29: "Can you give me a new tab - for all the stocks that are
  // reaching all time highs? call it ATH." The tab serves one 🏔️ / ↘️ badge
  // per tile (ath_tab.tile_badge) — a distance to a high, routed to PRICE.
  const withBadge = (text: string, tone: CmBadge['tone'] = 'good') =>
    bare({ badges: [{ text, tone }] });

  it('the served 🏔️ and ↘️ pills land in PRICE, whole', () => {
    for (const text of [
      '\u{1F3D4}\u{FE0F} 0.40% under the all-time high 101.20 (2026-09-25)',
      '\u{1F3D4}\u{FE0F} new high since 2003-09 today · +1.20% over 99.00 (2026-07) — not proven all-time',
    ]) {
      const l = cardLadder(withBadge(text));
      expect(texts(l.price)).toEqual([text]);
      expect(texts(l.setup.badges)).toEqual([]);
    }
    const slip = '\u{2198}\u{FE0F} 4.10% under the 52-week high 88.00 set 2026-09-17 (7 sessions ago)';
    const l = cardLadder(withBadge(slip, 'warn'));
    expect(texts(l.price)).toEqual([slip]);
    expect(l.moreWarn.map((b) => b.text)).not.toContain(slip);
  });

  it('NEGATIVE: 🏔 without VS16 and a plain "ATH" badge stay in SETUP', () => {
    for (const text of ['\u{1F3D4} 0.40% under the all-time high 101.20', 'ATH', '\u{2198} 4.10% under']) {
      const l = cardLadder(withBadge(text));
      expect(l.price).toEqual([]);
      expect(texts(l.setup.badges)).toEqual([text]);
    }
  });
});

describe('cardLadder — 🛡️ Resiliency tab (2026-09-30)', () => {
  // Ajay 2026-09-30: "Can you build me a new tab- Resileincy. …" The tab
  // serves a 🛡️ hold-record chip (IDENT), a 📅 today pill on a T1/T2 session
  // (PRICE) and one badge per ticked box passed (IDENT).
  const HOLD = '\u{1F6E1}\u{FE0F} T1 held 34/43 (79%)';        // resiliency_tab.T1_BADGE_FMT
  const HOLD2 = '\u{1F6E1}\u{FE0F} T2 held 70/96 (73%)';
  const TODAY_UP = '\u{1F4C5} T1 today · holding +0.42%';      // TODAY_HOLD_FMT
  const TODAY_DN = '\u{1F4C5} T1 today · down -1.20%';         // TODAY_DOWN_FMT
  const TODAY_T2 = '\u{1F4C5} T2 today · holding +0.10%';
  const BOXES = ['\u{1F6E1}\u{FE0F} Held on T1', '\u{1F6E1}\u{FE0F} Held on T2',
    '\u{1F4C8} Bullish tape EOD', '\u{1F305} Bullish tape pre-market'];
  const resTile = (over: Partial<CmTile> = {}): CmTile => bare({
    symbol: 'RSX',
    badges: [{ text: HOLD, tone: 'good' }, { text: TODAY_UP, tone: 'good' }, { text: BOXES[0], tone: 'good' }],
    stats: [
      { k: 'T1 held', v: '34/43 · 79% · SPY down: 15/19' }, { k: 'T2 held', v: '70/96 · 73% · SPY down: 30/44' },
      { k: 'EOD tape', v: '09-29 · +1.20% · closed at 78% of range · vol 1.34× 50d' },
      { k: 'Pre-market', v: 'not open' }, { k: 'Today', v: '+0.42% vs 227.21 · pre-market 08:52 ET' },
      { k: 'T1 worst', v: '-3.12% · 2026-03-11 CPI' }, { k: 'Last T1', v: '+0.35% · 2026-09-16 FOMC decision (SPY -0.12%)' },
      { k: 'σ · β', v: '1.9%/day · β 0.62' },
    ],
    ...over,
  });

  it('the hold chips and every box badge route to IDENT; the 📅 today pills to PRICE', () => {
    const l = cardLadder(resTile());
    expect(texts(l.ident)).toEqual([HOLD, BOXES[0]]);
    expect(texts(l.price)).toEqual([TODAY_UP]);
    expect(texts(l.setup.badges)).toEqual([]);
    for (const t of [HOLD2, ...BOXES]) expect(texts(cardLadder(bare({ badges: [{ text: t, tone: 'good' }] })).ident), t).toEqual([t]);
    for (const t of [TODAY_DN, TODAY_T2]) {
      const one = cardLadder(bare({ badges: [{ text: t, tone: 'warn' }] }));
      expect(texts(one.price), t).toEqual([t]);
      expect(one.moreWarn.map((b) => b.text), t).not.toContain(t);
    }
  });

  it('T1 held / T2 held / EOD tape / Pre-market / Today stay on the face; T1 worst, Last T1 and σ · β fold into READS', () => {
    const l = cardLadder(resTile());
    expect(l.setup.stats.map((s) => s.k)).toEqual(['T1 held', 'T2 held', 'EOD tape', 'Pre-market', 'Today']);
    expect(foldTexts(l, 'reads')).toEqual(['T1 worst', 'Last T1', 'σ · β']);
    expect(l.plan.stats).toEqual([]);
  });

  it('NEGATIVE: the other 🛡️ literals keep their rungs — Gabbar position on PRICE, the put wall in TAPE', () => {
    const gab = '\u{1F6E1}\u{FE0F} In Gabbar band (conservative)';
    const wall = '\u{1F6E1}\u{FE0F} Put wall 180 · 12k OI';
    const l = cardLadder(bare({ badges: [{ text: gab, tone: 'good' }, { text: wall, tone: 'muted' }] }));
    expect(texts(l.price)).toEqual([gab]);
    expect(foldTexts(l, 'tape')).toEqual([wall]);
    expect(texts(l.ident)).toEqual([]);
  });

  it('NEGATIVE: near-misses do not route to IDENT / PRICE (no VS16, other tier, a box label with a suffix)', () => {
    for (const t of ['\u{1F6E1} T1 held 34/43 (79%)', '\u{1F6E1}\u{FE0F} T3 held 1/2 (50%)',
                     '\u{1F4C8} Bullish tape EOD (x)', '\u{1F305} Bullish tape', '\u{1F4C5} T3 today · holding +0.10%',
                     '\u{1F4C5} today']) {
      const l = cardLadder(bare({ badges: [{ text: t, tone: 'good' }] }));
      expect(texts(l.ident), t).toEqual([]);
      if (!t.startsWith('\u{1F6E1}\u{FE0F} ')) expect(texts(l.price), t).toEqual([]);
    }
  });

  it('NEGATIVE: no NaN / undefined / [object Object] anywhere on a Resiliency ladder', () => {
    for (const s of allStrings(cardLadder(resTile()))) {
      expect(s.includes('NaN'), s).toBe(false);
      expect(s.includes('undefined'), s).toBe(false);
      expect(s.includes('[object Object]'), s).toBe(false);
    }
/* 🧱 The served 1% pad (2026-09-30): the PLAN buy zone passes the enterable
 * band's pad_lo through when well-formed, drops it otherwise. The ladder never
 * computes a pad. */
describe('cardLadder — the served pad under the buy zone', () => {
  const withBand = (band: Record<string, unknown> | null) =>
    cardLadder({ ...VOYA, enterable: { ...VOYA.enterable!, band: band as never } });

  it('passes pad_lo through', () => {
    expect(withBand({ lo: 133, hi: 135, pad_lo: 131.67 }).plan.buyZone)
      .toEqual({ lo: 133, hi: 135, pad_lo: 131.67 });
    expect(withBand({ kind: 'demand', lo: 133, hi: 135, pad_lo: 131.67 }).plan.buyZone?.pad_lo)
      .toBe(131.67);
  });

  // --- negatives ---
  it('NEGATIVE: malformed pads are dropped — no pad_lo key at all', () => {
    for (const pad_lo of [undefined, null, NaN, '131.67', 133, 140, 0, -1]) {
      const z = withBand({ lo: 133, hi: 135, pad_lo }).plan.buyZone;
      expect(z).toEqual({ lo: 133, hi: 135 });
      expect(z && 'pad_lo' in z).toBe(false);
    }
  });

  it('NEGATIVE: a supply-kind band never carries a pad', () => {
    expect(withBand({ kind: 'supply', lo: 133, hi: 135, pad_lo: 131.67 }).plan.buyZone)
      .toEqual({ lo: 133, hi: 135 });
  });

  it('NEGATIVE: the live 2026-09-25 boards (no pad served) → no buy zone carries pad_lo', async () => {
    const raw = (await import('../components/__fixtures__/card_ladder_live_2026_09_25.json?raw')).default;
    const live = JSON.parse(raw) as { boards: Record<string, { tiles: CmTile[] }> };
    let zones = 0;
    for (const b of Object.values(live.boards)) {
      for (const t of b.tiles) {
        const z = cardLadder(t).plan.buyZone;
        if (!z) continue;
        zones += 1;
        expect('pad_lo' in z).toBe(false);
      }
    }
    expect(zones).toBeGreaterThan(0);
  });
});
