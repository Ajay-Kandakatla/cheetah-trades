/* 🏷️ parseRowTags + the row's `tags` key (2026-11-18, spec wtags §3.2 / §4 WP-B).
 * Ajay 2026-11-18: "Also add Short Interest tag and other tags on top of stock ticker information for me to read, like
 * here". The served block (backend gajjala_watch/tags.py) parses key for key; junk never draws a chip. Every word below
 * is a stand-in for a served one. */
import { describe, expect, it } from 'vitest';
import autoFixture from '../components/__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import { parseGgw, parseRowTags, type GgwBoard } from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const STAGES = {
  title: '🧭 served title', hint: 'served hint', sep: '→', text: '🎾 served chain',
  groups: [{ date: '2026-11-18', label: 'today', clock: true, tags: [{ setup: 'reversal_squeeze', text: '🎾 served tag' }] }],
};
const BLOCK = {
  on_board: true,
  setups: [{ setup: 'reversal_squeeze', label: '🎾 served label', state: 'forming', state_label: 'served state words' }],
  stages: STAGES,
  float: { text: 'Float 3.2M', shares: 3200000, src: 'served-src', as_of: '2026-11-17', suspect: false },
  broker_text: '🚫 served broker', trader_text: '📌 served trader', promo_text: '🎪 served promo',
};

describe('🏷️ parseRowTags', () => {
  it('a served block parses key for key', () => {
    expect(parseRowTags(clone(BLOCK))).toEqual(BLOCK);
  });
  it('NEGATIVE: on_board false / missing / truthy-not-true / junk → null', () => {
    expect(parseRowTags({ ...clone(BLOCK), on_board: false })).toBeNull();
    const { on_board: _drop, ...rest } = clone(BLOCK);
    expect(parseRowTags(rest)).toBeNull();
    expect(parseRowTags({ ...clone(BLOCK), on_board: 1 })).toBeNull();
    expect(parseRowTags({ ...clone(BLOCK), on_board: 'true' })).toBeNull();
    for (const junk of [null, undefined, 0, '', 'x', [], [BLOCK], true]) expect(parseRowTags(junk)).toBeNull();
  });
  it('NEGATIVE: a setups item without a served setup / label is dropped; missing state words → null', () => {
    const b = clone(BLOCK) as any;
    b.setups = [
      { setup: 'kiss_fly', label: '', state: 'forming' },
      { setup: '', label: '💋 x', state: 'forming' },
      { label: '💋 x' },
      'junk', null,
      { setup: 'kiss_fly', label: '💋 served', state: 'triggered' },
    ];
    expect(parseRowTags(b)!.setups).toEqual([{ setup: 'kiss_fly', label: '💋 served', state: 'triggered', state_label: null }]);
    b.setups = 'junk';
    expect(parseRowTags(b)!.setups).toEqual([]);
  });
  it('NEGATIVE: stages without a served title → null; float without text → null; blank texts → null', () => {
    const b = clone(BLOCK) as any;
    b.stages = { ...STAGES, title: '  ' };
    b.float = { shares: 1, text: '' };
    b.broker_text = ' ';
    b.trader_text = 7;
    b.promo_text = null;
    const t = parseRowTags(b)!;
    expect(t.stages).toBeNull();
    expect(t.float).toBeNull();
    expect(t.broker_text).toBeNull();
    expect(t.trader_text).toBeNull();
    expect(t.promo_text).toBeNull();
    expect(parseRowTags({ ...clone(BLOCK), stages: 'x', float: [1] })!.stages).toBeNull();
    expect(parseRowTags({ ...clone(BLOCK), float: { text: 'F', shares: 'x', src: 1, suspect: 'yes' } })!.float)
      .toEqual({ text: 'F', shares: null, src: null, as_of: null, suspect: false });
  });
});

describe('🏷️ parseGgw sets `tags` on every row', () => {
  it('null when absent; the served block when present — auto / aplus byte-equal to the 11-17 fixture', () => {
    const base = parseGgw(clone(autoFixture)) as GgwBoard;
    const raw = clone(autoFixture) as any;
    raw.rows[0].tags = clone(BLOCK);
    raw.rows[1].tags = { on_board: false };
    const b = parseGgw(raw) as GgwBoard;
    expect(b.rows).toHaveLength(base.rows.length);
    for (const r of base.rows) expect('tags' in r, r.symbol).toBe(true);
    expect(base.rows.every((r) => r.tags === null)).toBe(true);
    expect(b.rows[0].tags).toEqual(BLOCK);
    expect(b.rows[1].tags).toBeNull();
    b.rows.forEach((r, i) => {
      expect(JSON.stringify(r.auto)).toBe(JSON.stringify(base.rows[i].auto));
      expect(JSON.stringify(r.aplus)).toBe(JSON.stringify(base.rows[i].aplus));
      const { tags: _a, ...restNew } = r;
      const { tags: _b, ...restOld } = base.rows[i];
      expect(JSON.stringify(restNew)).toBe(JSON.stringify(restOld));
    });
  });
});
