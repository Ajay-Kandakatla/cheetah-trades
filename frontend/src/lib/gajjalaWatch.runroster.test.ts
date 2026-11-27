/* 📅 parseGgw with the 📅 Runners keys (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay: "Ok then add them to our
 * watch list and track them please..". `board.runners` and `row.runner` are set ONLY when served — an older payload
 * (no key) parses byte-equal to before; junk → null. NEGATIVES throughout. */
import { describe, expect, it } from 'vitest';
import board from './__fixtures__/ggwAllRules.golden.json';
import gold from './__fixtures__/ggwRunRoster.golden.json';
import { parseGgw, type GgwBoard } from './gajjalaWatch';

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

describe('parseGgw — 📅 runners / runner', () => {
  it('NEGATIVE: no runners key and no runner key → neither key on the parsed board (byte-equal)', () => {
    const p = parseGgw(clone(board)) as GgwBoard;
    expect('runners' in p).toBe(false);
    for (const r of p.rows) expect('runner' in r).toBe(false);
  });
  it('served → parsed verbatim; the older payload\'s other keys are unchanged', () => {
    const raw = clone(board) as any;
    const before = parseGgw(clone(board)) as GgwBoard;
    raw.runners = clone(G.runners);
    raw.rows[0].runner = clone(G.row_runner);
    const p = parseGgw(raw) as GgwBoard;
    expect(p.runners!.rows.map((r) => r.symbol)).toEqual(G.runners.rows.map((r: any) => r.symbol));
    expect(p.rows[0].runner).toEqual(G.row_runner);
    expect('runner' in p.rows[1]).toBe(false);
    const { runners: _a, ...restP } = p;
    expect({ ...restP, rows: restP.rows.map(({ runner: _r, ...x }) => x) }).toEqual(before);
  });
  it('NEGATIVE: junk served → the key is present and null (nothing drawn)', () => {
    const raw = clone(board) as any;
    raw.runners = 'junk';
    raw.rows[0].runner = { seat_title: 'only a title' };
    const p = parseGgw(raw) as GgwBoard;
    expect(p.runners).toBeNull();
    expect(p.rows[0].runner).toBeNull();
  });
});
