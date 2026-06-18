import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

/* perfReporter — in-house web-vitals RUM (Ajay 2026-06-17). Locks: a captured
   metric is queued with its route + the user's CONNECTION quality, the batch
   beacons to /analytics/perf, an absent Network-Info API degrades to 'unknown',
   and a failed beacon never throws (RUM is non-critical). web-vitals + the
   beacon are mocked so the test is pure. */

const handlers: Record<string, (m: { name: string; value: number }) => void> = {};
vi.mock('web-vitals', () => ({
  onLCP: (cb: any) => { handlers.LCP = cb; },
  onINP: (cb: any) => { handlers.INP = cb; },
  onCLS: (cb: any) => { handlers.CLS = cb; },
  onFCP: (cb: any) => { handlers.FCP = cb; },
  onTTFB: (cb: any) => { handlers.TTFB = cb; },
}));

import { initPerfReporting, __test } from './perfReporter';

let beacon: ReturnType<typeof vi.fn>;

function setConnection(value: unknown) {
  Object.defineProperty(navigator, 'connection', { value, configurable: true, writable: true });
}

beforeEach(() => {
  __test.reset();
  beacon = vi.fn(() => true);
  Object.defineProperty(navigator, 'sendBeacon', { value: beacon, configurable: true, writable: true });
  setConnection({ effectiveType: '3g', downlink: 1.2, saveData: true });
});

afterEach(() => { vi.restoreAllMocks(); });

describe('perfReporter', () => {
  it('queues a web-vital with route + connection, then beacons on flush', () => {
    initPerfReporting();
    handlers.LCP({ name: 'LCP', value: 2345.678 });

    const q = __test.getQueue();
    expect(q).toHaveLength(1);
    expect(q[0]).toMatchObject({ metric: 'LCP', route: '/', conn: '3g', save_data: true, downlink: 1.2 });
    expect(q[0].value).toBeCloseTo(2345.678, 2);

    __test.flush();
    expect(beacon).toHaveBeenCalledTimes(1);
    expect(beacon.mock.calls[0][0]).toMatch(/\/analytics\/perf$/);
    expect(__test.getQueue()).toHaveLength(0);   // drained
  });

  it('degrades to unknown connection when the Network-Info API is absent', () => {
    setConnection(undefined);
    initPerfReporting();
    handlers.FCP({ name: 'FCP', value: 1000 });
    expect(__test.getQueue()[0]).toMatchObject({ conn: 'unknown', save_data: false });
  });

  it('never throws if the beacon fails (RUM is non-critical)', () => {
    beacon.mockImplementation(() => { throw new Error('blocked'); });
    initPerfReporting();
    handlers.TTFB({ name: 'TTFB', value: 200 });
    expect(() => __test.flush()).not.toThrow();
  });

  it('does not beacon when nothing is queued', () => {
    initPerfReporting();
    __test.flush();
    expect(beacon).not.toHaveBeenCalled();
  });
});
