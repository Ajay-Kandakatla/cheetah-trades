/* 🏎️ Dual Momentum filter boxes — ANY (default) vs "must match all" (2026-09-29).
 * Ajay, verbatim: "How can I see all of these? at the same time? is there a
 * check box selection?"
 * The mode param parser, boardQuery, and the card ladder routing the served
 * filter badges onto the identity line. */
import { describe, expect, it } from 'vitest';
import { DM_MODE_ALL, DM_MODE_ANY, DM_MODE_PARAM, parseDmMode } from './dmFilters';
import { boardQuery, type CmBadge, type CmTile } from './chartMaps';
import { cardLadder } from './cardLadder';

const LABELS = ['🌀 AMD raided', '📍 Near demand zone', '🔑 Near a lower key level'];

describe('parseDmMode', () => {
  it("'all' in any case / spacing -> all", () => {
    for (const v of ['all', 'ALL', ' All ']) expect(parseDmMode(v), v).toBe(DM_MODE_ALL);
    expect(DM_MODE_PARAM).toBe('dm_mode');
  });
  it('NEGATIVE: absent / blank / unknown / non-string -> any (the default)', () => {
    for (const v of [null, undefined, '', '  ', 'any', 'foo', 'and', 'alll']) {
      expect(parseDmMode(v as string | null | undefined), String(v)).toBe(DM_MODE_ANY);
    }
    expect(parseDmMode(7 as unknown as string)).toBe(DM_MODE_ANY);
  });
});

describe('boardQuery sends dm_mode=all on the Dual Momentum tab only', () => {
  it('dual_momentum + all -> dm_mode=all beside dm', () => {
    const q = new URLSearchParams(boardQuery({ tab: 'dual_momentum', dmFilters: 'amd,zone', dmMode: 'all' }));
    expect(q.get('dm_mode')).toBe('all');
    expect(q.get('dm')).toBe('amd,zone');
  });
  it('NEGATIVE: any / foo / absent -> no dm_mode (ANY is the server default)', () => {
    for (const dmMode of [undefined, 'any', 'foo', '']) {
      const q = new URLSearchParams(boardQuery({ tab: 'dual_momentum', dmFilters: 'amd', dmMode }));
      expect(q.has('dm_mode'), String(dmMode)).toBe(false);
    }
  });
  it('NEGATIVE: another tab never carries it', () => {
    for (const tab of ['zones', 'key_levels', 'amd'] as const) {
      expect(new URLSearchParams(boardQuery({ tab, dmMode: 'all' })).has('dm_mode'), tab).toBe(false);
    }
  });
});

const tile = (badges: CmBadge[]): CmTile => ({
  symbol: 'ZZZ', href: '/sepa/ZZZ', bars: [{ t: '2026-09-29', o: 1, h: 2, l: 0.5, c: 1.5, v: 1 }],
  bands: [], lines: [], markers: [], stats: [], why: '', badges,
});

describe('cardLadder — the served filter badges sit on the identity line', () => {
  it('each served box label lands in IDENT beside the 🏎️ rank chip, in served order', () => {
    const l = cardLadder(tile([
      { text: '🏎️ #3 dual momentum', tone: 'good' },
      ...LABELS.map((text, i) => ({ text, tone: 'good' as const, dm_filter: ['amd', 'zone', 'level'][i] })),
    ]));
    expect(l.ident.map((b) => b.text)).toEqual(['🏎️ #3 dual momentum', ...LABELS]);
    expect(l.setup.badges).toEqual([]);
    expect(l.price).toEqual([]);
  });
  it('NEGATIVE: the 🔑 position pill still goes to PRICE; a near-miss text is not IDENT', () => {
    const l = cardLadder(tile([
      { text: '🔑 0.41% above PWL 97.20', tone: 'muted' },
      { text: '🌀 AMD raided today', tone: 'good' },
    ]));
    expect(l.price.map((b) => b.text)).toEqual(['🔑 0.41% above PWL 97.20']);
    expect(l.ident).toEqual([]);
    expect(l.setup.badges.map((b) => b.text)).toEqual(['🌀 AMD raided today']);
  });
});
