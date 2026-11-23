/* 🔒 useRegSho (2026-11-22, spec htb §3.3 / §4 fe). ONE GET per page, URL exactly `${API}/short-interest/reg-sho`; a timer
 * ONLY for a valid `refreshing` payload (at most RS_FOLLOWUP_MAX in a row); a still-refreshing payload expires after
 * RS_RETRY_MS; a failure with nothing held draws nothing, a failed REFETCH keeps the last valid payload (refix 11-22);
 * either retries only after RS_RETRY_MS; no valid payload → no timer ever. */
import { createElement } from 'react';
import { act, cleanup, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { API } from '../lib/apiBase';
import {
  _resetRegShoCache, RS_FOLLOWUP_MAX, RS_FOLLOWUP_MAX_MS, RS_FOLLOWUP_MIN_MS, RS_RETRY_MS, RS_TTL_MS, useRegSho,
} from './useRegSho';

const AKAN = {
  state: 'on', symbol: 'AKAN', market: 'nasdaq', exchange: 'Nasdaq', as_of: '2026-11-20', stale: false,
  chip: 'served chip AKAN', short: 'served short AKAN', label: 'served label AKAN', title: 'served title AKAN',
};
const valid = (over: Record<string, unknown> = {}) => ({
  kind: 'reg_sho_threshold', as_of: '2026-11-20', complete: true, items: { AKAN }, fault_text: null,
  refreshing: false, retry_after_sec: null, ...over,
});

let seen: Record<string, string | null> = {};
function Probe({ symbol }: { symbol: string }) {
  const { tag, loaded, failed } = useRegSho(symbol);
  seen[symbol] = tag ? tag.chip : null;
  return createElement('span', { 'data-testid': `p-${symbol}`, 'data-loaded': String(loaded), 'data-failed': String(failed) },
    tag ? tag.chip : '');
}

function stubSeq(bodies: Array<unknown | Error>) {
  let i = 0;
  const f = vi.fn(async () => {
    const b = bodies[Math.min(i, bodies.length - 1)];
    i += 1;
    if (b instanceof Error) throw b;
    return { ok: true, json: async () => JSON.parse(JSON.stringify(b)) } as unknown as Response;
  });
  vi.stubGlobal('fetch', f);
  return f;
}
const flush = async () => { for (let k = 0; k < 4; k += 1) await act(async () => { await vi.advanceTimersByTimeAsync(0); }); };

describe('useRegSho', () => {
  beforeEach(() => { vi.useFakeTimers(); _resetRegShoCache(); seen = {}; });
  afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); _resetRegShoCache(); });

  it('N mounted chips → ONE GET, URL exactly ${API}/short-interest/reg-sho, no query string', async () => {
    const f = stubSeq([valid()]);
    render(createElement('div', null, ...['AKAN', 'AKANW', 'ZZZ', 'AKAN'].map((s, i) => createElement(Probe, { key: i, symbol: s }))));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(f.mock.calls[0]).toHaveLength(1);
    expect(String((f.mock.calls[0] as unknown[])[0])).toBe(`${API}/short-interest/reg-sho`);
    expect(String((f.mock.calls[0] as unknown[])[0])).not.toContain('?');
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(seen.AKANW).toBeNull();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('a fresh payload is not re-fetched inside RS_TTL_MS; a render after it re-fetches', async () => {
    const f = stubSeq([valid()]);
    const r = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(RS_TTL_MS - 1000); });
    r.rerender(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
    r.rerender(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
  });

  it('a refreshing payload → one re-GET after the served delay, at most RS_FOLLOWUP_MAX in a row', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} })]);
    render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(vi.getTimerCount()).toBe(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(19000); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(1000); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    for (let k = 0; k < 5; k += 1) { await act(async () => { await vi.advanceTimersByTimeAsync(20000); }); await flush(); }
    expect(f).toHaveBeenCalledTimes(1 + RS_FOLLOWUP_MAX);
    expect(vi.getTimerCount()).toBe(0);
  });

  it('the served delay is clamped to RS_FOLLOWUP_MIN_MS … RS_FOLLOWUP_MAX_MS', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 0 }), valid()]);
    render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(RS_FOLLOWUP_MIN_MS - 100); });
    expect(f).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    _resetRegShoCache();
    cleanup();
    const g = stubSeq([valid({ refreshing: true, retry_after_sec: 99999 }), valid()]);
    render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    await act(async () => { await vi.advanceTimersByTimeAsync(RS_FOLLOWUP_MAX_MS - 100); });
    expect(g).toHaveBeenCalledTimes(1);
    await act(async () => { await vi.advanceTimersByTimeAsync(200); });
    await flush();
    expect(g).toHaveBeenCalledTimes(2);
  });

  it('[C1] a payload still refreshing after the follow-ups is re-fetched on a render after RS_RETRY_MS (not RS_TTL_MS)', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 5, items: {} })]);
    const r = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    for (let k = 0; k < RS_FOLLOWUP_MAX; k += 1) { await act(async () => { await vi.advanceTimersByTimeAsync(5000); }); await flush(); }
    expect(f).toHaveBeenCalledTimes(1 + RS_FOLLOWUP_MAX);
    expect(vi.getTimerCount()).toBe(0);
    r.rerender(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(1 + RS_FOLLOWUP_MAX);
    await act(async () => { await vi.advanceTimersByTimeAsync(RS_RETRY_MS + 10); });
    r.rerender(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(2 + RS_FOLLOWUP_MAX);
    expect(RS_RETRY_MS).toBeLessThan(RS_TTL_MS);
  });

  it('a refreshing payload that lands with names then settles: the tag draws, the follow-up stops', async () => {
    const f = stubSeq([valid({ refreshing: true, retry_after_sec: 20, items: {} }), valid()]);
    render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(seen.AKAN).toBeNull();
    await act(async () => { await vi.advanceTimersByTimeAsync(20000); });
    await flush();
    expect(f).toHaveBeenCalledTimes(2);
    expect(seen.AKAN).toBe('served chip AKAN');
    expect(vi.getTimerCount()).toBe(0);
  });

  for (const [name, bodies] of [
    ['a rejected fetch', [new Error('down')]],
    ['a foreign body', [{ items: {}, n: 0, max_symbols: 200 }]],
    ['{}', [{}]],
  ] as const) {
    it(`NEGATIVE: ${name} → no tag, failed, NO timer; a retry only after RS_RETRY_MS`, async () => {
      const f = stubSeq(bodies as unknown as Array<unknown | Error>);
      const r = render(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(seen.AKAN).toBeNull();
      expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
      expect(vi.getTimerCount()).toBe(0);
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await act(async () => { await vi.advanceTimersByTimeAsync(RS_RETRY_MS - 1000); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(f).toHaveBeenCalledTimes(1);
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(vi.getTimerCount()).toBe(0);
    });
  }

  it('NEGATIVE: a fetch that throws synchronously → nothing, no crash, no timer', async () => {
    const f = vi.fn(() => { throw new Error('sync'); });
    vi.stubGlobal('fetch', f);
    const r = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(f).toHaveBeenCalledTimes(1);
    expect(r.getByTestId('p-AKAN').textContent).toBe('');
    expect(vi.getTimerCount()).toBe(0);
  });

  it('NEGATIVE: a non-ok response → nothing, no timer', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: false, status: 404, json: async () => valid() })));
    const r = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(r.getByTestId('p-AKAN').textContent).toBe('');
    expect(vi.getTimerCount()).toBe(0);
  });

  for (const [name, bad] of [
    ['a rejected fetch', new Error('down')],
    ['a body parseRegSho rejects', { items: {}, n: 0 }],
  ] as const) {
    it(`[refix 11-22] a failed REFETCH (${name}) keeps the earlier tag, reads failed, retries after RS_RETRY_MS, no timer`, async () => {
      const f = stubSeq([valid(), bad as unknown, valid({ items: {} })]);
      const r = render(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(seen.AKAN).toBe('served chip AKAN');
      await act(async () => { await vi.advanceTimersByTimeAsync(RS_TTL_MS + 10); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      expect(seen.AKAN).toBe('served chip AKAN');
      expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
      expect(r.getByTestId('p-AKAN').getAttribute('data-loaded')).toBe('true');
      expect(vi.getTimerCount()).toBe(0);
      // not re-fetched inside RS_RETRY_MS (no hammer)
      await act(async () => { await vi.advanceTimersByTimeAsync(RS_RETRY_MS - 1000); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(f).toHaveBeenCalledTimes(2);
      // NEGATIVE: the next VALID answer replaces the held one — a name it no longer lists draws nothing
      await act(async () => { await vi.advanceTimersByTimeAsync(2000); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
      expect(f).toHaveBeenCalledTimes(3);
      expect(seen.AKAN).toBeNull();
      expect(r.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('false');
    });
  }

  it('NEGATIVE: two failures in a row with a list held still keep it; a failure with NOTHING held draws nothing', async () => {
    const f = stubSeq([valid(), new Error('down'), new Error('down')]);
    const r = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    for (let k = 0; k < 2; k += 1) {
      await act(async () => { await vi.advanceTimersByTimeAsync(RS_TTL_MS + 10); });
      r.rerender(createElement(Probe, { symbol: 'AKAN' }));
      await flush();
    }
    expect(f).toHaveBeenCalledTimes(3);
    expect(seen.AKAN).toBe('served chip AKAN');
    cleanup();
    _resetRegShoCache();
    seen = {};
    stubSeq([new Error('down')]);
    const r2 = render(createElement(Probe, { symbol: 'AKAN' }));
    await flush();
    expect(seen.AKAN).toBeNull();
    expect(r2.getByTestId('p-AKAN').getAttribute('data-failed')).toBe('true');
  });
});
