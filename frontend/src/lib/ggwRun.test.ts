/* ▶ lib/ggwRun — the run route, the chrome words and the parser (2026-11-24, spec ggrun §3.5 / §4 fe-run).
 * Ajay 2026-11-24: "On the Watch list I need a run button to run against Gajjalas rules of a stock …".
 * Positives: the path, the parser keeps the SERVED order and every string verbatim (gate_text included), flattens the
 * nested as_of / scanner blocks. NEGATIVES: junk / no string state → null; a row without key + label is dropped; a setup
 * without a string `setup` is dropped; never re-sorted; the lib types no rule or state word and no timer. Every word in
 * the fixture is a stand-in for a served one. */
import { describe, expect, it } from 'vitest';
import { GGW_PATH } from './gajjalaWatch';
import { GGW_RUN, GGW_RUN_PATH, ggwRunPath, ggwRunTitle, parseGgwRun } from './ggwRun';
import libSrc from './ggwRun.ts?raw';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SETUP = (setup: string, extra: Record<string, unknown> = {}) => ({
  setup, label: `served label ${setup}`, state: 'partial', state_label: `served state words ${setup}`, gate_text: null,
  plan_text: `served plan ${setup}`, variant_label: null, grade_label: null, vol_dried_text: null, frame: '5m',
  as_of_bar_t: '2026-11-24 10:35',
  criteria: [
    { key: `${setup}_a`, label: 'served row a', ok: true, value: 'served value a', need: 'served need a' },
    { key: `${setup}_b`, label: 'served row b', ok: false, value: null, need: null },
    { key: `${setup}_c`, label: 'served row c', ok: null, value: '', need: '' },
  ],
  tally_text: 'served tally', ...extra,
});
const ANSWER = {
  state: 'ok', symbol: 'OMH', title: 'served title OMH', text: null,
  as_of: { bar_t5: '2026-11-24 10:35', bar_t15: '2026-11-24 10:30', read_at_et: '10:36:12', text: 'served as-of line' },
  reused_text: null, scanner: { listed: true, text: 'served scanner line' }, float_text: 'served float line',
  volume_text: 'served volume line', note: 'served note',
  setups: [
    SETUP('reversal_squeeze', { state: 'none', state_label: 'served none words', gate_text: 'served gate sentence', criteria: [], tally_text: null, plan_text: null }),
    SETUP('bull_flag'), SETUP('kiss_fly'), SETUP('horizontal_fade'), SETUP('intraday_vcp'),
  ],
};

describe('ggwRun — the route and the chrome', () => {
  it('ggwRunPath == backend API_RUN_PATH with the symbol; trimmed and encoded', () => {
    expect(ggwRunPath('OMH')).toBe('/chart-maps/gajjala-watch/run/OMH');
    expect(GGW_RUN_PATH).toBe(`${GGW_PATH}/run`);
    expect(ggwRunPath('  brk.b ')).toBe('/chart-maps/gajjala-watch/run/brk.b');
    expect(ggwRunPath('A/B')).toBe('/chart-maps/gajjala-watch/run/A%2FB');
  });
  it('the chrome: "▶ Rules", ✕, the busy word, the failed word; the title names the symbol', () => {
    expect(`${GGW_RUN.glyph} ${GGW_RUN.label}`).toBe('▶ Rules');
    expect(GGW_RUN.close).toBe('✕');
    expect(GGW_RUN.busy).toBe('Reading the bars…');
    expect(GGW_RUN.failed).toBe("Could not run Gajjala's rules.");
    expect(ggwRunTitle('OMH')).toBe("Run Gajjala's rules on OMH");
  });
});

describe('parseGgwRun', () => {
  it('flattens as_of / scanner and keeps every served string verbatim (gate_text included)', () => {
    const a = parseGgwRun(clone(ANSWER))!;
    expect(a).not.toBeNull();
    expect(a.state).toBe('ok');
    expect(a.symbol).toBe('OMH');
    expect(a.title).toBe('served title OMH');
    expect(a.as_of_text).toBe('served as-of line');
    expect(a.scanner_text).toBe('served scanner line');
    expect(a.scanner_listed).toBe(true);
    expect(a.float_text).toBe('served float line');
    expect(a.volume_text).toBe('served volume line');
    expect(a.note).toBe('served note');
    expect(a.reused_text).toBeNull();
    expect(a.text).toBeNull();
    expect(a.setups[0].gate_text).toBe('served gate sentence');
    expect(a.setups[0].state_label).toBe('served none words');
    expect(a.setups[0].criteria).toEqual([]);
    expect(a.setups[1].criteria).toEqual([
      { key: 'bull_flag_a', label: 'served row a', ok: true, value: 'served value a', need: 'served need a' },
      { key: 'bull_flag_b', label: 'served row b', ok: false, value: null, need: null },
      { key: 'bull_flag_c', label: 'served row c', ok: null, value: null, need: null },
    ]);
    expect(a.setups[1].tally_text).toBe('served tally');
    expect(a.setups[1].plan_text).toBe('served plan bull_flag');
  });
  it('keeps the SERVED setup order; NEGATIVE: a shuffled order is returned as served, never re-sorted', () => {
    expect(parseGgwRun(clone(ANSWER))!.setups.map((s) => s.setup))
      .toEqual(['reversal_squeeze', 'bull_flag', 'kiss_fly', 'horizontal_fade', 'intraday_vcp']);
    const b = clone(ANSWER);
    b.setups = [b.setups[3], b.setups[0], b.setups[4], b.setups[1], b.setups[2]];
    expect(parseGgwRun(b)!.setups.map((s) => s.setup))
      .toEqual(['horizontal_fade', 'reversal_squeeze', 'intraday_vcp', 'bull_flag', 'kiss_fly']);
    const c = clone(ANSWER);
    c.setups[1].criteria.reverse();
    expect(parseGgwRun(c)!.setups[1].criteria.map((x) => x.key)).toEqual(['bull_flag_c', 'bull_flag_b', 'bull_flag_a']);
  });
  it('a non-ok answer: its ONE sentence, null blocks, no setups', () => {
    const a = parseGgwRun({ state: 'not_listed', symbol: 'ZZZ', title: 'served t', text: 'served not-listed sentence',
      as_of: null, reused_text: null, scanner: null, float_text: null, volume_text: null, note: 'served note', setups: [] })!;
    expect(a.text).toBe('served not-listed sentence');
    expect(a.as_of_text).toBeNull();
    expect(a.scanner_text).toBeNull();
    expect(a.scanner_listed).toBeNull();
    expect(a.setups).toEqual([]);
  });
  it('NEGATIVE: junk / no string state → null', () => {
    for (const j of [null, undefined, 0, 'ok', [], [ANSWER], {}, { state: 5 }, { state: '' }, { state: null }]) {
      expect(parseGgwRun(j as unknown), JSON.stringify(j)).toBeNull();
    }
  });
  it('NEGATIVE: a row without a string key AND label is dropped; a setup without a string `setup` is dropped', () => {
    const b = clone(ANSWER) as any;
    b.setups[1].criteria = [{ label: 'no key', ok: true }, { key: 'k', ok: true }, { key: 1, label: 'x', ok: true },
      null, 'row', { key: 'kept', label: 'kept row', ok: 'yes' }];
    b.setups.push({ label: 'no setup key' }, null, 7, { setup: 5 });
    const a = parseGgwRun(b)!;
    expect(a.setups[1].criteria).toEqual([{ key: 'kept', label: 'kept row', ok: null, value: null, need: null }]);
    expect(a.setups).toHaveLength(5);
  });
  it('NEGATIVE: non-string / empty served fields read null (never a typed fallback word)', () => {
    const b = clone(ANSWER) as any;
    Object.assign(b, { title: '', text: 5, float_text: {}, volume_text: '  ', note: null, scanner: { listed: 'yes', text: 3 } });
    b.setups[0].gate_text = '';
    const a = parseGgwRun(b)!;
    expect([a.title, a.text, a.float_text, a.volume_text, a.note, a.scanner_text, a.scanner_listed, a.setups[0].gate_text])
      .toEqual([null, null, null, null, null, null, null, null]);
    expect(parseGgwRun({ state: 'ok', setups: 'x' })!.setups).toEqual([]);
  });
});

/* ── source guard ── */
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
/** Every quoted / template literal of the code (comments stripped) — the words this file could print. The served KEY
 *  `float_text` and the spec-named testid `ggw-run-float` are identifiers, not printed words. */
function literalsOf(src: string): string[] {
  const code = noComments(src);
  return Array.from(code.matchAll(/'(?:[^'\\\n]|\\.)*'|"(?:[^"\\\n]|\\.)*"|`(?:[^`\\]|\\.)*`/g))
    .map((m) => m[0].replace(/float_text|ggw-run-float/g, ''));
}
const RULE_WORDS = [/K3/, /volume dried/i, /tennis/i, /Squeeze/i, /A\+/, /forming/i, /partial/i, /float/i, /Yahoo/i, /Massive/i];

describe('ggwRun.ts source guard', () => {
  it('NEGATIVE: no rule or state word in any literal; no isOwner, no @, no timer', () => {
    expect(libSrc.length).toBeGreaterThan(500);
    const lits = literalsOf(libSrc);
    expect(lits.length).toBeGreaterThan(5);
    for (const l of lits) for (const w of RULE_WORDS) expect(l, `${w} in ${l}`).not.toMatch(w);
    const code = noComments(libSrc);
    expect(code).not.toMatch(/isOwner/);
    expect(code).not.toMatch(/@/);
    expect(code).not.toMatch(/setTimeout|setInterval/);
  });
});
