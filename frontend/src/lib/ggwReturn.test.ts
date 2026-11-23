/* ggwReturn — 👀 Gajjala's Watch: the return GET rule (2026-11-23, spec ggconn §3.2, WP-2).
 * The cadence below is a stand-in for the served `refresh_sec` (the rule types none). NEGATIVES: hidden, refresh_sec 0
 * (out of window), negative / NaN refresh_sec, a GET younger than one cadence → false. The parameter keys are pinned:
 * NO in-flight input [C9]. */
import { describe, expect, it } from 'vitest';
import { ggwReturnRefetch } from './ggwReturn';

const SERVED_REFRESH_SEC = 60;
const T0 = 1_700_000_000_000;
const at = (ageMs: number, over: Partial<Parameters<typeof ggwReturnRefetch>[0]> = {}) => ggwReturnRefetch({
  hidden: false, refreshSec: SERVED_REFRESH_SEC, lastIssuedMs: T0, nowMs: T0 + ageMs, ...over,
});

/* tsc pins the keys EXACTLY: a missing or an extra key (e.g. a busy / inFlight flag) fails the type check. */
type Args = Parameters<typeof ggwReturnRefetch>[0];
const KEYS: Record<keyof Args, true> = { hidden: true, refreshSec: true, lastIssuedMs: true, nowMs: true };

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

describe('ggwReturnRefetch — the return GET rule', () => {
  it('visible + the last full GET issued more than one served cadence ago → true', () => {
    expect(at(SERVED_REFRESH_SEC * 1000 + 1)).toBe(true);
    expect(at(SERVED_REFRESH_SEC * 1000 * 5)).toBe(true);
  });
  it('exactly one served cadence old → true (>=)', () => {
    expect(at(SERVED_REFRESH_SEC * 1000)).toBe(true);
  });
  it('the cadence is the SERVED one: a 30 s served cadence → true at 30 s, false at 29.999 s', () => {
    expect(at(30_000, { refreshSec: 30 })).toBe(true);
    expect(at(29_999, { refreshSec: 30 })).toBe(false);
  });
  it('NEGATIVE: younger than one cadence → false', () => {
    expect(at(SERVED_REFRESH_SEC * 1000 - 1)).toBe(false);
    expect(at(0)).toBe(false);
  });
  it('NEGATIVE: still hidden → false, however old the last GET', () => {
    expect(at(SERVED_REFRESH_SEC * 1000 * 10, { hidden: true })).toBe(false);
  });
  it('NEGATIVE: out of window (refresh_sec 0) → false, however old the last GET', () => {
    expect(at(SERVED_REFRESH_SEC * 1000 * 10, { refreshSec: 0 })).toBe(false);
  });
  it('NEGATIVE: a negative or NaN refresh_sec → false', () => {
    expect(at(SERVED_REFRESH_SEC * 1000 * 10, { refreshSec: -1 })).toBe(false);
    expect(at(SERVED_REFRESH_SEC * 1000 * 10, { refreshSec: Number.NaN })).toBe(false);
  });
  it('a never-stamped board (lastIssuedMs 0) in window and visible → true', () => {
    expect(ggwReturnRefetch({ hidden: false, refreshSec: SERVED_REFRESH_SEC, lastIssuedMs: 0, nowMs: T0 })).toBe(true);
  });
});

describe('ggwReturnRefetch — [C9] no in-flight input', () => {
  it('the parameter keys are exactly hidden / refreshSec / lastIssuedMs / nowMs', async () => {
    expect(Object.keys(KEYS).sort()).toEqual(['hidden', 'lastIssuedMs', 'nowMs', 'refreshSec']);
    const src = noComments(await readSource('src/lib/ggwReturn.ts'));
    const sig = src.match(/export function ggwReturnRefetch\(a: \{([\s\S]*?)\}\)/);
    expect(sig).not.toBeNull();
    const keys = Array.from(sig![1].matchAll(/(\w+)\s*:/g)).map((m) => m[1]).sort();
    expect(keys).toEqual(['hidden', 'lastIssuedMs', 'nowMs', 'refreshSec']);
  });
  it('NEGATIVE: the rule names no busy / in-flight / fullBusy and types no cadence number (only the s → ms 1000)', async () => {
    const src = noComments(await readSource('src/lib/ggwReturn.ts'));
    for (const bad of ['busy', 'Busy', 'inFlight', 'pending']) expect(src).not.toContain(bad);
    const nums = Array.from(src.matchAll(/\b\d[\d_]*\b/g)).map((m) => m[0]);
    expect(nums).toEqual(['0', '1000']);
  });
});
