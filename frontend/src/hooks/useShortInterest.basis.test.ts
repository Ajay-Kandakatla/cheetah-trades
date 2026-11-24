import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, renderHook } from '@testing-library/react';
import { createElement } from 'react';
import {
  useShortInterest, _resetShortInterestCache,
  SI_FLUSH_MS, SI_CHUNK, SI_TTL_MS, SI_FOLLOWUP_MAX, SI_FOLLOWUP_MIN_MS, SI_FOLLOWUP_MAX_MS,
} from './useShortInterest';

/* 🩳 follow-up re-ask (2026-11-24, spec sidilute §3.7 [C5]). Ajay: "Make sure we are looking for Dilution.." · "Also split
 * related events and filing so we flag them in the right way". The map route marks a name whose share-count check is
 * queued or running with `basis.pending === true` + `retry_after_sec`; the hook re-asks it on ONE module timer — the k-th
 * re-ask after clamp(served × 2^(k-1), 5 s, 120 s), at most SI_FOLLOWUP_MAX in a row. NEGATIVES: an older API (no basis) →
 * today's behaviour, no timer; junk `pending` / `retry_after_sec`; the cap; a reset on a non-pending answer; a failed
 * follow-up keeps the last read; no listener → nothing asked. */

type Answer = Record<string, unknown> | null | 'throw';
let answer: (sym: string, call: number) => Answer;
let calls: string[][] = [];

const blk = (sym: string, chip: string, basis?: unknown) =>
  ({ symbol: sym, status: 'ok', chip, title: `served title ${sym}`, rows: [], ...(basis === undefined ? {} : { basis }) });
const PENDING = (sec: unknown = 20) => ({ status: 'pending', pending: true, retry_after_sec: sec });
const SMTK_CHIP = '🩳 SI 8.9% shs out · 1.0d · 10/30 · ⚠️ float stale · ✂️ split 11/23 · 📄 S-4 11/13';
const OLD_CHIP = '🩳 SI EXTREME 79.0% float · 1.0d · 10/30';

function stub() {
  calls = [];
  const f = vi.fn(async (url: string) => {
    const syms = decodeURIComponent(String(url).split('symbols=')[1] || '').split(',').filter(Boolean);
    calls.push(syms);
    const n = calls.length;
    const items: Record<string, unknown> = {};
    for (const s of syms) {
      const a = answer(s, n);
      if (a === 'throw') throw new Error('down');
      if (a) items[s] = a;
    }
    return { ok: true, json: async () => ({ items, n: Object.keys(items).length, max_symbols: 200 }) } as unknown as Response;
  });
  vi.stubGlobal('fetch', f);
  return f;
}

async function settle() {
  await act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
}
/** Exactly SI_FLUSH_MS: the GET goes out and answers at the same fake instant, so a served delay is measured from here. */
async function flush() {
  await act(async () => { await vi.advanceTimersByTimeAsync(SI_FLUSH_MS); });
  await settle();
}
async function advance(ms: number) {
  await act(async () => { await vi.advanceTimersByTimeAsync(ms); });
  await settle();
}

function Probe({ s }: { s: string }) {
  useShortInterest(s);
  return null;
}
const many = (syms: string[]) => createElement('div', null, syms.map((s) => createElement(Probe, { key: s, s })));

describe('🩳 useShortInterest — follow-up re-ask of a pending share-count check', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetShortInterestCache(); });
  afterEach(() => { _resetShortInterestCache(); vi.useRealTimers(); vi.unstubAllGlobals(); });

  it('constants are the spec numbers', () => {
    expect(SI_FOLLOWUP_MAX).toBe(6);
    expect(SI_FOLLOWUP_MIN_MS).toBe(5000);
    expect(SI_FOLLOWUP_MAX_MS).toBe(120000);
  });

  it('a pending block is re-asked after the served delay and the chip updates; then no timer', async () => {
    answer = (s, n) => (n === 1 ? blk(s, OLD_CHIP, PENDING(20)) : blk(s, SMTK_CHIP, { status: 'ok', float_refused: 'diluted' }));
    const f = stub();
    const h = renderHook(() => useShortInterest('SMTK'));
    await flush();
    expect(h.result.current.read?.chip).toBe(OLD_CHIP);
    expect(f).toHaveBeenCalledTimes(1);
    await advance(19999);
    expect(f).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(f).toHaveBeenCalledTimes(2);
    expect(calls[1]).toEqual(['SMTK']);
    expect(h.result.current.read?.chip).toBe(SMTK_CHIP);
    expect(vi.getTimerCount()).toBe(0);
    await advance(SI_TTL_MS - 30000);
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('a block that carries its OWN basis AND pending: true is re-asked too [C5]', async () => {
    const own = { status: 'ok', float_refused: 'diluted', flags: [{ key: 'split', emoji: '✂️', short: '✂️ split 11/23', text: 't' }] };
    answer = (s, n) => (n === 1 ? blk(s, SMTK_CHIP, { ...own, pending: true, retry_after_sec: 20 }) : blk(s, SMTK_CHIP, own));
    const f = stub();
    renderHook(() => useShortInterest('SMTK'));
    await flush();
    await advance(20000);
    expect(f).toHaveBeenCalledTimes(2);
    await advance(SI_FOLLOWUP_MAX_MS * 4);
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('NEGATIVE: no basis key (older API) → exactly today: one GET, no timer, no re-ask inside the TTL', async () => {
    answer = (s) => blk(s, OLD_CHIP);
    const f = stub();
    const h = renderHook(() => useShortInterest('SMTK'));
    await flush();
    expect(h.result.current).toEqual({ read: expect.objectContaining({ chip: OLD_CHIP }), loaded: true, failed: false });
    expect(vi.getTimerCount()).toBe(0);
    await advance(SI_TTL_MS - 1000);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('NEGATIVE: pending a string / 1 / null → not pending, no re-ask', async () => {
    for (const p of ['true', 1, null]) {
      _resetShortInterestCache();
      answer = (s) => blk(s, OLD_CHIP, { status: 'pending', pending: p, retry_after_sec: 20 });
      const f = stub();
      const h = renderHook(() => useShortInterest('SMTK'));
      await flush();
      expect(vi.getTimerCount(), String(p)).toBe(0);
      await advance(SI_FOLLOWUP_MAX_MS * 2);
      expect(f, String(p)).toHaveBeenCalledTimes(1);
      h.unmount();
    }
  });

  it('NEGATIVE: retry_after_sec NaN / negative / a string → the minimum delay, never a tight loop', async () => {
    for (const sec of [NaN, -5, '20']) {
      _resetShortInterestCache();
      answer = (s, n) => (n === 1 ? blk(s, OLD_CHIP, PENDING(sec)) : blk(s, OLD_CHIP));
      const f = stub();
      const h = renderHook(() => useShortInterest('SMTK'));
      await flush();
      await advance(SI_FOLLOWUP_MIN_MS - 1);
      expect(f, String(sec)).toHaveBeenCalledTimes(1);
      await advance(1);
      expect(f, String(sec)).toHaveBeenCalledTimes(2);
      h.unmount();
    }
  });

  it('the delays double and stop at SI_FOLLOWUP_MAX_MS; after SI_FOLLOWUP_MAX pending answers in a row the re-asks stop', async () => {
    answer = (s) => blk(s, OLD_CHIP, PENDING(20));
    const f = stub();
    renderHook(() => useShortInterest('SMTK'));
    await flush();
    const gaps = [20000, 40000, 80000, 120000, 120000, 120000];
    expect(gaps).toHaveLength(SI_FOLLOWUP_MAX);
    for (let i = 0; i < gaps.length; i++) {
      await advance(gaps[i] - 1);
      expect(f, `before re-ask ${i + 1}`).toHaveBeenCalledTimes(i + 1);
      await advance(1);
      expect(f, `re-ask ${i + 1}`).toHaveBeenCalledTimes(i + 2);
    }
    expect(vi.getTimerCount()).toBe(0);
    await advance(SI_FOLLOWUP_MAX_MS * 3);
    expect(f).toHaveBeenCalledTimes(1 + SI_FOLLOWUP_MAX);
  });

  it('NEGATIVE: a non-pending answer resets the count — the next pending answer starts again at the served delay', async () => {
    answer = (s, n) => (n === 3 ? blk(s, OLD_CHIP) : blk(s, OLD_CHIP, PENDING(20)));
    const f = stub();
    const a = renderHook(() => useShortInterest('SMTK'));
    await flush();
    await advance(20000);
    await advance(40000);
    expect(f).toHaveBeenCalledTimes(3);           // the 3rd answer is not pending → cleared
    expect(vi.getTimerCount()).toBe(0);
    a.unmount();
    await advance(SI_TTL_MS);
    renderHook(() => useShortInterest('SMTK'));  // the TTL refetch answers pending again
    await flush();
    expect(f).toHaveBeenCalledTimes(4);
    await advance(19999);
    expect(f).toHaveBeenCalledTimes(4);
    await advance(1);
    expect(f).toHaveBeenCalledTimes(5);           // 20 s again, not 80 s
  });

  it('NEGATIVE: a failed follow-up keeps the last read and ends the series (no retry loop)', async () => {
    answer = (s, n) => (n === 1 ? blk(s, OLD_CHIP, PENDING(20)) : 'throw');
    const f = stub();
    const h = renderHook(() => useShortInterest('SMTK'));
    await flush();
    await advance(20000);
    expect(f).toHaveBeenCalledTimes(2);
    expect(h.result.current.read?.chip).toBe(OLD_CHIP);
    expect(h.result.current.failed).toBe(false);
    expect(vi.getTimerCount()).toBe(0);
    await advance(SI_FOLLOWUP_MAX_MS * 3);
    expect(f).toHaveBeenCalledTimes(2);
    h.unmount();
    answer = (s) => blk(s, OLD_CHIP, PENDING(20));   // the failure ended the series: a later pending answer starts at 20 s
    await advance(SI_TTL_MS);
    renderHook(() => useShortInterest('SMTK'));
    await flush();
    expect(f).toHaveBeenCalledTimes(3);
    await advance(19999);
    expect(f).toHaveBeenCalledTimes(3);
    await advance(1);
    expect(f).toHaveBeenCalledTimes(4);
  });

  it('NEGATIVE: no listener mounted when the timer fires → nothing is asked and the map clears', async () => {
    answer = (s) => blk(s, OLD_CHIP, PENDING(20));
    const f = stub();
    const a = renderHook(() => useShortInterest('SMTK'));
    await flush();
    a.unmount();
    await advance(20000);
    expect(f).toHaveBeenCalledTimes(1);
    renderHook(() => useShortInterest('SMTK'));  // inside the TTL: the cache answers, and the cleared map asks nothing
    await flush();
    await advance(SI_FOLLOWUP_MAX_MS * 3);
    expect(f).toHaveBeenCalledTimes(1);
  });

  it('due symbols go out together in chunks of SI_CHUNK on ONE timer', async () => {
    answer = (s, n) => (n <= 2 ? blk(s, OLD_CHIP, PENDING(20)) : blk(s, OLD_CHIP));
    const f = stub();
    const syms = Array.from({ length: 250 }, (_, i) => `P${i}`);
    render(many(syms));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(vi.getTimerCount()).toBe(1);
    await advance(20000);
    expect(f).toHaveBeenCalledTimes(4);
    expect(calls[2]).toHaveLength(SI_CHUNK);
    expect(calls[3]).toHaveLength(250 - SI_CHUNK);
    expect([...calls[2], ...calls[3]].sort()).toEqual([...syms].sort());
  });

  it('two names on different delays share ONE timer; each is re-asked on its own clock', async () => {
    answer = (s, n) => (n === 1 ? blk(s, OLD_CHIP, PENDING(s === 'AAA' ? 10 : 30)) : blk(s, OLD_CHIP));
    const f = stub();
    render(many(['AAA', 'BBB']));
    await flush();
    expect(vi.getTimerCount()).toBe(1);
    await advance(10000);
    expect(calls[1]).toEqual(['AAA']);
    expect(vi.getTimerCount()).toBe(1);
    await advance(20000);
    expect(calls[2]).toEqual(['BBB']);
    expect(f).toHaveBeenCalledTimes(3);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: _resetShortInterestCache clears the follow-up timer and map', async () => {
    answer = (s) => blk(s, OLD_CHIP, PENDING(20));
    const f = stub();
    renderHook(() => useShortInterest('SMTK'));
    await flush();
    expect(vi.getTimerCount()).toBe(1);
    _resetShortInterestCache();
    expect(vi.getTimerCount()).toBe(0);
    await advance(SI_FOLLOWUP_MAX_MS * 2);
    expect(f).toHaveBeenCalledTimes(1);
  });
});
