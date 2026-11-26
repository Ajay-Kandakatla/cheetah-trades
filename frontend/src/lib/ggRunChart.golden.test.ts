/* 📅 The backend's golden payload through the FE parser (2026-11-26, spec runcharts rev 2 §4.3, package fe-mount).
 *
 * Ajay 2026-11-26: "I want you to have continous charts for previous day runners … I wanna able to horizontal scroll tp
 * check continuity like he does".
 *
 * `__fixtures__/ggRunChart.golden.json` is written by the backend engine test (be-chart, test 22 — never by hand), so this
 * file pins the two sides to ONE contract: what the engine serves, `parseGgrc` keeps whole. NEGATIVES: the checks below
 * reject a payload whose bars go backwards, whose sessions leave a gap, or that lost an EMA curve. */
import { describe, expect, it } from 'vitest';
import golden from './__fixtures__/ggRunChart.golden.json';
import { parseGgrc } from './ggRunChart';

type Sess = { from: number; to: number };

/** The sessions cover bars 0 … n − 1 in order, no gap, no overlap. */
function partitions(sessions: ReadonlyArray<Sess>, n: number): boolean {
  if (n === 0) return sessions.length === 0;
  if (sessions.length === 0 || sessions[0].from !== 0) return false;
  for (let i = 0; i < sessions.length; i += 1) {
    const s = sessions[i];
    if (s.from > s.to) return false;
    if (i > 0 && s.from !== sessions[i - 1].to + 1) return false;
  }
  return sessions[sessions.length - 1].to === n - 1;
}

const ascending = (xs: ReadonlyArray<number>): boolean => xs.every((x, i) => i === 0 || x > xs[i - 1]);
const clone = (): any => JSON.parse(JSON.stringify(golden));

describe('📅 golden payload → parseGgrc', () => {
  const raw: any = golden;
  const p = parseGgrc(raw);

  it('the golden is an ok payload with bars (the fixture is not an empty shell)', () => {
    expect(raw.state).toBe('ok');
    expect(Array.isArray(raw.bars)).toBe(true);
    expect(raw.bars.length).toBeGreaterThan(0);
    expect(raw.sessions.length).toBeGreaterThan(1);
  });

  it('parses, and keeps every bar', () => {
    expect(p).not.toBeNull();
    expect(p!.state).toBe('ok');
    expect(p!.bars.length).toBe(raw.bars.length);
  });

  it('x is strictly ascending', () => {
    expect(ascending(p!.bars.map((b) => b.x))).toBe(true);
  });

  it('the sessions partition the bars, every one kept', () => {
    expect(p!.sessions.length).toBe(raw.sessions.length);
    expect(partitions(p!.sessions, p!.bars.length)).toBe(true);
  });

  it('both EMA curves are kept, each the bar count long', () => {
    const tones = p!.curves.map((c) => c.tone);
    expect(tones).toContain('ema9');
    expect(tones).toContain('ema21');
    for (const c of p!.curves) expect(c.values.length).toBe(p!.bars.length);
  });

  it('the volume average is kept and index-aligned', () => {
    expect(p!.vol_avg).not.toBeNull();
    expect(p!.vol_avg!.values.length).toBe(p!.bars.length);
  });
});

describe('📅 golden — NEGATIVES (the checks bite)', () => {
  it('two bars swapped → parseGgrc refuses the payload', () => {
    const g = clone();
    [g.bars[0], g.bars[1]] = [g.bars[1], g.bars[0]];
    expect(parseGgrc(g)).toBeNull();
  });

  it('a NaN price → parseGgrc refuses the payload', () => {
    const g = clone();
    g.bars[0].c = NaN;
    expect(parseGgrc(g)).toBeNull();
  });

  it('an EMA curve one value short → that curve is dropped, so "both kept" would fail', () => {
    const g = clone();
    const k = g.curves.findIndex((c: any) => c.tone === 'ema21');
    g.curves[k].values = g.curves[k].values.slice(1);
    const q = parseGgrc(g);
    expect(q).not.toBeNull();
    expect(q!.curves.map((c) => c.tone)).not.toContain('ema21');
  });

  it('the partition check rejects a gap, an overlap, a short cover and a reversed session', () => {
    expect(partitions([{ from: 0, to: 3 }, { from: 5, to: 9 }], 10)).toBe(false);
    expect(partitions([{ from: 0, to: 5 }, { from: 5, to: 9 }], 10)).toBe(false);
    expect(partitions([{ from: 0, to: 3 }, { from: 4, to: 8 }], 10)).toBe(false);
    expect(partitions([{ from: 0, to: 3 }, { from: 4, to: 2 }], 10)).toBe(false);
    expect(partitions([{ from: 1, to: 9 }], 10)).toBe(false);
    expect(partitions([{ from: 0, to: 3 }, { from: 4, to: 9 }], 10)).toBe(true);
  });

  it('the ascending check rejects an equal neighbour', () => {
    expect(ascending([1, 2, 2, 3])).toBe(false);
    expect(ascending([1, 2, 3])).toBe(true);
  });
});
