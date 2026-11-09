/* GajjalaLaneTab — 🛰 stream entries + the lane nudge (GG LIVE P1, 2026-11-09).
 *
 * Ajay 2026-11-09: "make it more live with websockets or something else where
 * there is a low latency monitoring on the prices action changes please?"
 *
 * Locks: the served `status.stream.word` prints verbatim (NEG: absent / blank
 * → no line, the FE composes nothing); a `gajjala.update` of kind "lane"
 * re-GETs ONCE (two nudges 100 ms apart → one GET) and restarts the POLL_MS
 * interval (NEG: no extra GET at the old interval tick); NEG: a "quotes" or a
 * "pass" event never reloads the lane; unmount unsubscribes. The SSE bus is
 * mocked so the test can fire events. */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

type Handler = (evt: { type: string; ts: number; payload: unknown }) => void;
const bus: { fn: Handler | null; type: string | null; offs: number } = { fn: null, type: null, offs: 0 };
vi.mock('../lib/eventBus', () => ({
  subscribe: (type: string, fn: Handler) => {
    bus.type = type;
    bus.fn = fn;
    return () => { bus.fn = null; bus.offs += 1; };
  },
}));

import { GajjalaLaneTab, POLL_MS, LANE_NUDGE_COALESCE_MS, GG_LIVE_EVENT, isLaneNudge } from './GajjalaLaneTab';
import type { GajjalaPayload } from './GajjalaLaneTab';

const SHADOW_WORD = '🛰 Stream entries: SHADOW — the first regular print at or over the trigger is recorded; orders still go on the 1-minute check.';
const payload = (stream: unknown): GajjalaPayload => ({
  date: '2026-11-09', armed: true, mode: 'paper', as_of: '2026-11-09T15:00:00Z',
  status: { strategy: 'gajjala', enabled: true, paper: true, floors: 'gg', caps_text: 'served caps', stream } as GajjalaPayload['status'],
  today: [], recent: [], journal: { text: 'served journal' },
});

let gets = 0;
function stubFetch(body: GajjalaPayload) {
  gets = 0;
  vi.stubGlobal('fetch', vi.fn().mockImplementation((_url: unknown, init?: RequestInit) => {
    if (init?.method !== 'POST') gets += 1;
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  }));
}
const view = () => render(<MemoryRouter><GajjalaLaneTab /></MemoryRouter>);
const flush = async (ms = 0) => { await act(async () => { await vi.advanceTimersByTimeAsync(ms); }); };
const fire = (payload: unknown) => act(() => { bus.fn?.({ type: GG_LIVE_EVENT, ts: 1, payload }); });

beforeEach(() => { vi.useFakeTimers(); bus.fn = null; bus.type = null; bus.offs = 0; });
afterEach(() => { vi.useRealTimers(); vi.unstubAllGlobals(); });

describe('GajjalaLaneTab — 🛰 stream word (served)', () => {
  it('prints status.stream.word verbatim', async () => {
    stubFetch(payload({ mode: 'shadow', word: SHADOW_WORD, prints_today: 3, first_prints_today: 1 }));
    view();
    await flush();
    expect(screen.getByTestId('gg-lane-stream').textContent).toBe(SHADOW_WORD);
  });

  it('NEG: no stream block, or a blank word → no line (the FE composes nothing)', async () => {
    stubFetch(payload(undefined));
    const a = view();
    await flush();
    expect(screen.queryByTestId('gg-lane-stream')).toBeNull();
    a.unmount();
    stubFetch(payload({ mode: 'shadow', word: '   ', prints_today: 9 }));
    view();
    await flush();
    expect(screen.queryByTestId('gg-lane-stream')).toBeNull();
    expect(document.body.textContent).not.toMatch(/SHADOW|prints/);
  });
});

describe('GajjalaLaneTab — the lane nudge', () => {
  it('subscribes to gajjala.update and knows only kind "lane"', async () => {
    stubFetch(payload(null));
    view();
    await flush();
    expect(bus.type).toBe('gajjala.update');
    expect(isLaneNudge({ kind: 'lane', day: '2026-11-09', changed_at_epoch: 1 })).toBe(true);
    expect(isLaneNudge({ kind: 'quotes' })).toBe(false);
    expect(isLaneNudge({ kind: 'pass' })).toBe(false);
    expect(isLaneNudge(null)).toBe(false);
    expect(isLaneNudge('lane')).toBe(false);
  });

  it('two lane nudges 100 ms apart → ONE re-GET, after the coalesce window', async () => {
    stubFetch(payload(null));
    view();
    await flush();
    expect(gets).toBe(1);
    fire({ kind: 'lane', day: '2026-11-09', changed_at_epoch: 1 });
    await flush(100);
    fire({ kind: 'lane', day: '2026-11-09', changed_at_epoch: 2 });
    await flush(LANE_NUDGE_COALESCE_MS - 1);
    expect(gets).toBe(1);                                   // not yet
    await flush(1);
    expect(gets).toBe(2);
    await flush(LANE_NUDGE_COALESCE_MS * 4);
    expect(gets).toBe(2);                                   // NEG: one GET for two nudges
  });

  it('a nudge restarts the POLL_MS interval — NEG: no extra GET at the old tick', async () => {
    stubFetch(payload(null));
    view();
    await flush();
    expect(gets).toBe(1);
    await flush(POLL_MS / 2);
    fire({ kind: 'lane' });
    await flush(LANE_NUDGE_COALESCE_MS);
    expect(gets).toBe(2);
    await flush(POLL_MS / 2 - LANE_NUDGE_COALESCE_MS);     // the OLD interval's tick
    expect(gets).toBe(2);                                   // NEG: the old tick is gone
    await flush(POLL_MS / 2 + LANE_NUDGE_COALESCE_MS - 1);
    expect(gets).toBe(2);
    await flush(1);                                         // POLL_MS after the nudge's GET
    expect(gets).toBe(3);
  });

  it('NEG: quotes and pass events never reload the lane', async () => {
    stubFetch(payload(null));
    view();
    await flush();
    fire({ kind: 'quotes', variant: 'gajjala', quotes: { SAIQ: { price: 4.5, as_of_epoch: 1, vs: null } } });
    fire({ kind: 'pass', variant: 'gajjala', pass_id: 'p1', finished_at_epoch: 1 });
    fire(undefined);
    await flush(LANE_NUDGE_COALESCE_MS * 4);
    expect(gets).toBe(1);
  });

  it('unmount stops the poll, the pending nudge and the subscription', async () => {
    stubFetch(payload(null));
    const r = view();
    await flush();
    fire({ kind: 'lane' });
    r.unmount();
    expect(bus.offs).toBe(1);
    await flush(POLL_MS * 2);
    expect(gets).toBe(1);                                   // NEG: nothing after unmount
  });
});
