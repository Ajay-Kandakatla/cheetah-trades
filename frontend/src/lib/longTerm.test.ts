import { describe, expect, it } from 'vitest';
import fixture from './__fixtures__/longTerm.payload.json';
import {
  DASH, FETCH_FAILED, LT_CHART, LT_PATH, LT_TAB, listOr, ltCategoryRows, ltForwardLines, ltMark, ltSavedRows,
  ltSavedSymbols, ltState, ltText, ltToken, textOr, type LtForward, type LtPayload,
} from './longTerm';

/* 📅 Long Term — FE plumbing (2026-11-12, long-term spec §3.10 / §3.13, WP-FE). Ajay: "Save this entire list for me. In a
 * New tab - Long Term …". Pure helpers; every word and number is served. NEGATIVES throughout. */
const P = (): LtPayload => JSON.parse(JSON.stringify(fixture)) as LtPayload;

describe('📅 longTerm — route, tab, the one FE sentence', () => {
  it('the route literal equals the backend API_PATH and the tab key equals TAB_KEY', () => {
    expect(LT_PATH).toBe('/chart-maps/long-term');
    expect(LT_TAB).toBe('long_term');
  });
  it('FETCH_FAILED is the spec sentence; NEGATIVE: it carries no digit', () => {
    expect(FETCH_FAILED).toBe('Could not load the Long Term list.');
    expect(FETCH_FAILED).not.toMatch(/\d/);
  });
});

describe('📅 longTerm — textOr / ltText / listOr', () => {
  it('a served string passes through', () => {
    expect(textOr('Stage 2 · Advancing')).toBe('Stage 2 · Advancing');
    expect(ltText('x')).toBe('x');
  });
  it('NEGATIVE: null / undefined / blank / a number / NaN → the dash, never "null" / "NaN"', () => {
    for (const v of [null, undefined, '', '   ', 3, Number.NaN, {}]) expect(textOr(v)).toBe(DASH);
    expect(DASH).toBe('—');
    expect(ltText(null)).toBeNull();
  });
  it('listOr: an absent block is []', () => {
    expect(listOr(null)).toEqual([]);
    expect(listOr(undefined)).toEqual([]);
    expect(listOr([1])).toEqual([1]);
  });
});

describe('📅 longTerm — ltState', () => {
  it('the four served states', () => {
    for (const s of ['owner_only', 'error', 'seed_only', 'ready']) expect(ltState({ state: s })).toBe(s);
  });
  it('NEGATIVE: anything else is null (the board then prints FETCH_FAILED)', () => {
    for (const v of [null, undefined, {}, { state: 'READY' }, { state: 'loading' }, 'ready', { rows: [] }]) expect(ltState(v)).toBeNull();
  });
});

describe('📅 longTerm — saved rows (one per symbol)', () => {
  it('changed first, then categories in seed order', () => {
    expect(ltSavedSymbols(P())).toEqual(['MANH', 'AMD', 'FIGS', 'ANET', 'NVDA', 'MPWR', 'XPEL', 'TSM']);
  });
  it('NEGATIVE: a duplicate the server never sends is still drawn once (first place wins)', () => {
    const p = P();
    p.categories[3].rows.push(p.categories[2].rows[0]);
    expect(ltSavedRows(p).filter((r) => r.symbol === 'NVDA')).toHaveLength(1);
    expect(ltCategoryRows(p, 'pankaj').map((r) => r.symbol)).toEqual(['TSM']);
    expect(ltCategoryRows(p, 'quiet_strong').map((r) => r.symbol)).toEqual(['NVDA', 'MPWR', 'XPEL']);
  });
  it('NEGATIVE: a changed row is not drawn again under its category', () => {
    expect(ltCategoryRows(P(), 'capital_quality').map((r) => r.symbol)).toEqual(['ANET']);
  });
  it('NEGATIVE: no payload → no rows; an unknown category → []', () => {
    expect(ltSavedSymbols(null)).toEqual([]);
    expect(ltCategoryRows(P(), 'nope')).toEqual([]);
  });
});

describe('📅 longTerm — marks and tokens', () => {
  it('verdict marks are glyphs', () => {
    expect(ltMark('pass')).toBe('✓');
    expect(ltMark('fail')).toBe('✗');
    expect(ltMark('info')).toBe('ℹ');
    expect(ltMark('unknown')).toBe('?');
  });
  it('NEGATIVE: an unknown / missing verdict is "?", never ✓', () => {
    expect(ltMark(undefined)).toBe('?');
    expect(ltMark('PASS')).toBe('?');
  });
  it('ltToken strips anything not class-safe; NEGATIVE: non-strings → none', () => {
    expect(ltToken('started_moving')).toBe('started_moving');
    expect(ltToken('a b"<c')).toBe('abc');
    expect(ltToken(null)).toBe('none');
    expect(ltToken('')).toBe('none');
  });
});

describe('📅 longTerm — forward chart lines', () => {
  const fwd = (over: Partial<LtForward> = {}): LtForward => ({
    base_session: '2026-11-13', n_sessions: 22, too_early: false, line: 'x', counts_line: 'y',
    series: [{ key: 'list_pct', label: 'Saved list' }, { key: 'rsp_pct', label: 'RSP' }, { key: 'spy_pct', label: 'SPY' }],
    points: [
      { date: '2026-11-13', list_pct: 0, rsp_pct: 1, spy_pct: 2 },
      { date: '2026-11-20', list_pct: 4, rsp_pct: 3, spy_pct: 2 },
    ],
    ...over,
  });
  it('one line per served series, inside the viewBox', () => {
    const ls = ltForwardLines(fwd());
    expect(ls.map((l) => l.key)).toEqual(['list_pct', 'rsp_pct', 'spy_pct']);
    for (const l of ls) {
      for (const xy of l.points.split(' ')) {
        const [x, y] = xy.split(',').map(Number);
        expect(x).toBeGreaterThanOrEqual(0); expect(x).toBeLessThanOrEqual(LT_CHART.w);
        expect(y).toBeGreaterThanOrEqual(0); expect(y).toBeLessThanOrEqual(LT_CHART.h);
      }
    }
    const top = ls[0].points.split(' ')[1].split(',').map(Number)[1];
    const bottom = ls[0].points.split(' ')[0].split(',').map(Number)[1];
    expect(top).toBeLessThan(bottom);
  });
  it('NEGATIVE: too_early → no line at all', () => {
    expect(ltForwardLines(fwd({ too_early: true }))).toEqual([]);
    expect(ltForwardLines(null)).toEqual([]);
  });
  it('NEGATIVE: a non-finite / null value is a gap, never drawn as zero; an all-empty series draws nothing', () => {
    const ls = ltForwardLines(fwd({ points: [
      { date: 'a', list_pct: Number.NaN, rsp_pct: 1, spy_pct: null },
      { date: 'b', list_pct: 2, rsp_pct: 1, spy_pct: null },
    ] }));
    expect(ls.find((l) => l.key === 'list_pct')!.n).toBe(1);
    expect(ls.find((l) => l.key === 'spy_pct')).toBeUndefined();
    expect(ls.find((l) => l.key === 'rsp_pct')!.n).toBe(2);
  });
  it('NEGATIVE: no points or no series → []', () => {
    expect(ltForwardLines(fwd({ points: [] }))).toEqual([]);
    expect(ltForwardLines(fwd({ series: [] }))).toEqual([]);
  });
});
