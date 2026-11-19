/* 🚫 lib/ggwBroker — the Watch's served broker block + row word (2026-11-19, spec watchfid §3.3 / §4 WP-C tests 1–2).
 * Every word is a stand-in for a served one. NEGATIVES: junk / missing toggle or text → null; editable only on a served
 * `true`; an older payload (no block, no row word) → null and the parsed board equals the pre-change parse. */
import { describe, expect, it } from 'vitest';
import autoFixture from '../components/__fixtures__/gajjala_watch_board_auto_2026_11_17.json';
import oldFixture from '../components/__fixtures__/gajjala_watch_board_2026_11_15.json';
import { ggwBrokerText, parseGgwBroker } from './ggwBroker';
import { parseGgw, type GgwBoard } from './gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const BLOCK = {
  toggle: '🚫', text: '🚫 served broker word', title: 'served mark title', editable: true,
  fault_text: null, auto_text: '🚫 served kept-off line', auto_fault_text: null,
};

describe('🚫 parseGgwBroker', () => {
  it('keeps every served key', () => {
    expect(parseGgwBroker(clone(BLOCK))).toEqual(BLOCK);
  });
  it('NEGATIVE: junk / missing or blank toggle or text → null', () => {
    for (const junk of [null, undefined, 'x', 3, [], {}, { toggle: '🚫' }, { text: 't' }, { toggle: ' ', text: 't' },
      { toggle: '🚫', text: '' }, { toggle: 3, text: 't' }, { toggle: '🚫', text: ['t'] }]) {
      expect(parseGgwBroker(junk)).toBeNull();
    }
  });
  it('NEGATIVE: editable only when the server said true (never truthy)', () => {
    for (const v of [false, 'true', 1, null, undefined, {}]) {
      expect(parseGgwBroker({ ...BLOCK, editable: v })!.editable).toBe(false);
    }
    expect(parseGgwBroker({ ...BLOCK, editable: true })!.editable).toBe(true);
  });
  it('blank / junk lines → null; title absent → null', () => {
    const b = parseGgwBroker({ toggle: '🚫', text: 't', title: ' ', fault_text: 3, auto_text: '', auto_fault_text: [] })!;
    expect(b).toEqual({ toggle: '🚫', text: 't', title: null, editable: false, fault_text: null, auto_text: null, auto_fault_text: null });
  });
});

describe('🚫 parseGgw keeps the block and the row word', () => {
  it('a served block + a row word survive the parse', () => {
    const raw = clone(autoFixture) as any;
    raw.broker = clone(BLOCK);
    raw.rows[0].broker_text = '🚫 served broker word';
    const b = parseGgw(raw) as GgwBoard;
    expect(b.broker).toEqual(BLOCK);
    expect(b.rows[0].broker_text).toBe('🚫 served broker word');
    expect(b.rows[1].broker_text).toBeNull();
  });
  it('NEGATIVE: an older payload (no block, no row key) → broker null, every row word null; the rest is unchanged', () => {
    for (const fx of [oldFixture, autoFixture]) {
      const b = parseGgw(clone(fx)) as GgwBoard;
      expect(b.broker).toBeNull();
      expect(b.rows.every((r) => r.broker_text == null)).toBe(true);
      const { broker: _b, ...rest } = b;
      const withBlock = parseGgw({ ...clone(fx), broker: clone(BLOCK) }) as GgwBoard;
      const { broker: _w, ...restW } = withBlock;
      expect(restW).toEqual(rest);
    }
  });
  it('NEGATIVE: a junk block → null (no button anywhere)', () => {
    const b = parseGgw({ ...clone(autoFixture), broker: { toggle: '🚫' } }) as GgwBoard;
    expect(b.broker).toBeNull();
  });
});

describe('🚫 ggwBrokerText', () => {
  it('the row word first, the card tags word as fallback', () => {
    expect(ggwBrokerText({ broker_text: 'row word', tags: { broker_text: 'tags word' } })).toBe('row word');
    expect(ggwBrokerText({ broker_text: null, tags: { broker_text: 'tags word' } })).toBe('tags word');
    expect(ggwBrokerText({ tags: { broker_text: 'tags word' } })).toBe('tags word');
    expect(ggwBrokerText({ broker_text: 'row word' })).toBe('row word');
  });
  it('NEGATIVE: blank / missing everywhere → null', () => {
    expect(ggwBrokerText({})).toBeNull();
    expect(ggwBrokerText({ broker_text: ' ', tags: null })).toBeNull();
    expect(ggwBrokerText({ broker_text: '', tags: { broker_text: '  ' } })).toBeNull();
    expect(ggwBrokerText({ broker_text: null, tags: { broker_text: null } })).toBeNull();
  });
});
