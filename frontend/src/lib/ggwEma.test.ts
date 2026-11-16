/* 👀 Gajjala's Watch LIVE — the 9 / 21 EMA step (2026-11-16, watch-live spec §3.4 / §4 WP-C). Ajay: "Realtime updates..
 * Like the 1 min chart I need it to be live live.. per sec change". Pinned two-sided against the backend's golden fixture
 * (pandas ewm(span, adjust=False) — the ONE EMA): ≤ 1 ulp at raw precision (pandas fuses the multiply-add; JS cannot)
 * and EQUAL after 6 dp (the server's own precision). NEGATIVES: alpha = 2/span fails; the unguarded step differs on an
 * equal-close row (the guard is load-bearing); the tips chain from the UNROUNDED value. The tip is drawn only under
 * GGW_LIVE_EMA_TIP (HIS CALL #1). */
import { describe, expect, it } from 'vitest';
import { EMA_FAST, EMA_SLOW } from './ema';
import { ggwEmaAlpha, ggwEmaStep, ggwEmaTips, ggwRound6 } from './ggwEma';

/* tsc-safe fixture read (the GajjalaBoard.potential.test readSource precedent): no node types in the app tsconfig, so
 * `node:fs` is imported dynamically; paths are relative to frontend/ (vitest's cwd). */
async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = (globalThis as any).process?.cwd?.() || '.';
const GOLDEN = '../backend/tests/fixtures/gajjala/ema_step_golden_2026_11_16.json';
async function readGolden(): Promise<{ spans: Record<string, { closes: number[]; ema: number[] }> }> {
  return JSON.parse((await fsMod()).readFileSync(`${root}/${GOLDEN}`, 'utf8'));
}
const SPANS = [EMA_FAST, EMA_SLOW];
const ulpOk = (got: number, want: number) => Math.abs(got - want) <= 2 * Number.EPSILON * Math.abs(want);
const unguarded = (p: number, c: number, span: number) => {
  const a = ggwEmaAlpha(span);
  return ((1 - a) * p + a * c) / ((1 - a) + a);
};
const alpha2Step = (p: number, c: number, span: number) => {
  if (p === c) return p;
  const a = 2 / span;
  return ((1 - a) * p + a * c) / ((1 - a) + a);
};

describe('👀 ggwEmaAlpha — pandas com → alpha, never a typed 2/(span+1)', () => {
  it('9 → 0.2 exactly, 21 → 1/11', () => {
    expect(ggwEmaAlpha(9)).toBe(0.2);
    expect(ggwEmaAlpha(21)).toBe(1 / 11);
  });
});

describe('👀 ggwEmaStep — the golden fixture (backend pandas, two-sided)', () => {
  it('every step is within 1 ulp of pandas and EQUAL after 6 dp, both spans', async () => {
    const g = await readGolden();
    for (const span of SPANS) {
      const { closes, ema } = g.spans[String(span)];
      expect(closes.length).toBe(ema.length);
      expect(closes.length).toBeGreaterThan(100);
      expect(ema[0]).toBe(closes[0]);
      for (let i = 1; i < closes.length; i += 1) {
        const got = ggwEmaStep(ema[i - 1], closes[i], span);
        expect(ulpOk(got, ema[i]), `span ${span} row ${i}: ${got} vs ${ema[i]}`).toBe(true);
        expect(ggwRound6(got), `span ${span} row ${i}`).toBe(ggwRound6(ema[i]));
      }
    }
  });

  it('the fixture carries ≥ 10 equal-close rows per span (recounted here, never trusted from the fixture)', async () => {
    const g = await readGolden();
    for (const span of SPANS) {
      const { closes, ema } = g.spans[String(span)];
      let n = 0;
      for (let i = 1; i < closes.length; i += 1) if (closes[i] === ema[i - 1]) n += 1;
      expect(n, `span ${span}`).toBeGreaterThanOrEqual(10);
    }
  });

  it('on an equal-close row the guarded step returns the running value bit-exactly', async () => {
    const g = await readGolden();
    for (const span of SPANS) {
      const { closes, ema } = g.spans[String(span)];
      for (let i = 1; i < closes.length; i += 1) {
        if (closes[i] === ema[i - 1]) expect(ggwEmaStep(ema[i - 1], closes[i], span)).toBe(ema[i]);
      }
    }
  });

  it('NEGATIVE: alpha = 2/span fails the 6-dp equality on ≥ 1 row per span', async () => {
    const g = await readGolden();
    for (const span of SPANS) {
      const { closes, ema } = g.spans[String(span)];
      let fails = 0;
      for (let i = 1; i < closes.length; i += 1) {
        if (ggwRound6(alpha2Step(ema[i - 1], closes[i], span)) !== ggwRound6(ema[i])) fails += 1;
      }
      expect(fails, `span ${span}`).toBeGreaterThanOrEqual(1);
    }
  });

  it('NEGATIVE: the UNGUARDED step differs from pandas at raw precision on ≥ 1 equal-close row (the guard is load-bearing)', async () => {
    const g = await readGolden();
    for (const span of SPANS) {
      const { closes, ema } = g.spans[String(span)];
      let differs = 0;
      for (let i = 1; i < closes.length; i += 1) {
        if (closes[i] === ema[i - 1] && unguarded(ema[i - 1], closes[i], span) !== ema[i]) differs += 1;
      }
      expect(differs, `span ${span}`).toBeGreaterThanOrEqual(1);
    }
  });
});

describe('👀 ggwEmaTips — chained unrounded, displayed at 6 dp', () => {
  it('two bars: tip₂ chains from tip₁ UNROUNDED — NEGATIVE: never from the rounded tip₁', () => {
    const tail = 1.4835731234567;
    const tips = ggwEmaTips(tail, [1.49, 1.5], 9);
    expect(tips).toEqual([1.484858, 1.487887]);
    const fromRounded = ggwRound6(ggwEmaStep(tips[0], 1.5, 9));
    expect(fromRounded).toBe(1.487886);
    expect(tips[1]).not.toBe(fromRounded);
  });
  it('each tip is rounded to 6 dp; no closes → no tips; an equal close keeps the value', () => {
    const tips = ggwEmaTips(2.1234567891, [2.5, 2.6, 2.7], 21);
    for (const t of tips) expect(t).toBe(Number(t.toFixed(6)));
    expect(tips).toHaveLength(3);
    expect(ggwEmaTips(2, [], 9)).toEqual([]);
    expect(ggwEmaTips(2.5, [2.5], 9)).toEqual([2.5]);
  });
});
