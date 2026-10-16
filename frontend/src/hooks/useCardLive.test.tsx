import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCardLive } from './useCardLive';
import { CARD_LIVE_CLOSED_MS, CARD_LIVE_MS, type CardLiveAnswer } from '../lib/cardLive';
import type { CmTapeSession } from '../lib/chartMaps';

/* useCardLive — the Chart Maps card poll (BUILD_SPEC8 §3.5, AMENDMENTS8 C1/C3).
 * NEGATIVES: no POST while hidden, after unmount, when disabled or with no
 * symbols, while a request hangs; a closed session never polls at the fast
 * cadence; an answer from before a board refetch is dropped. C1: the board's
 * session stamp paces the poll before the last overlay answer. C3: one tick
 * right after every board refetch. */

const SYMS = ['IREN', 'NVDA', 'XLAB'];

const ans = (over: Partial<CardLiveAnswer> = {}): CardLiveAnswer => ({
  session: 'rth', as_of_epoch: 1792170942.1, as_of: '2026-10-16 11:15:42 ET',
  footer: { live: 'live · 11:15:42 ET', stale: 'last refresh 11:15 ET' },
  now_labels: ['now', 'now · pre', 'now · AH'], cap: 250, asked: 3, served: 3,
  missing: [], fault: null, quotes: {}, ...over,
});

type Resp = () => Promise<unknown>;
const ok = (j: unknown): Resp => async () => ({ ok: true, status: 200, json: async () => j });
const http = (status: number): Resp => async () => ({ ok: false, status, json: async () => ({ detail: 'x' }) });
const hang = (): Resp => () => new Promise(() => {});
function deferred(j: unknown) {
  let resolve!: () => void;
  const p = new Promise<unknown>((r) => { resolve = () => r({ ok: true, status: 200, json: async () => j }); });
  return { resp: (() => p) as Resp, resolve };
}

let queue: Resp[] = [];
let fallback: Resp = ok(ans());
const fetchMock = vi.fn((_url: string, _init?: RequestInit) => (queue.shift() ?? fallback)());
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));

const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

type P = { syms: readonly string[]; enabled: boolean; resetKey: unknown; initialSession?: CmTapeSession | null };
const mount = (p: Partial<P> = {}) => renderHook(
  (q: P) => useCardLive(q.syms, q.enabled, { resetKey: q.resetKey, initialSession: q.initialSession }),
  { initialProps: { syms: SYMS, enabled: true, resetKey: 1, initialSession: 'rth', ...p } as P });

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  queue = [];
  fallback = ok(ans());
  fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('useCardLive — cadence', () => {
  it('no request at mount; ONE POST after CARD_LIVE_MS with the exact request', async () => {
    const h = mount();
    await advance(CARD_LIVE_MS - 1000);
    expect(posts().length).toBe(0);
    expect(h.result.current.answer).toBeNull();
    await advance(1100);
    expect(posts().length).toBe(1);
    const [url, init] = posts()[0];
    expect(String(url).endsWith('/chart-maps/live')).toBe(true);
    expect(init?.method).toBe('POST');
    expect(init?.credentials).toBe('include');
    expect(init?.cache).toBe('no-store');
    expect(init?.body).toBe('{"symbols":["IREN","NVDA","XLAB"]}');
    expect(h.result.current.answer?.session).toBe('rth');
    expect(h.result.current.footer).toBe('live · 11:15:42 ET');
  });

  it('NEGATIVE document.hidden → zero POSTs over three cadences', async () => {
    const spy = vi.spyOn(document, 'hidden', 'get').mockReturnValue(true);
    mount();
    await advance(3 * CARD_LIVE_MS + 500);
    expect(posts().length).toBe(0);
    spy.mockRestore();
  });

  it('NEGATIVE unmount → zero POSTs after', async () => {
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    h.unmount();
    await advance(5 * CARD_LIVE_MS);
    expect(posts().length).toBe(1);
  });

  it('NEGATIVE enabled false, or no symbols → zero POSTs', async () => {
    const a = mount({ enabled: false });
    await advance(3 * CARD_LIVE_MS);
    a.unmount();
    const b = mount({ syms: [] });
    await advance(3 * CARD_LIVE_MS);
    b.unmount();
    expect(posts().length).toBe(0);
  });

  it('served "closed" → the next POST at CARD_LIVE_CLOSED_MS, NOT at 60 s', async () => {
    fallback = ok(ans({ session: 'closed', footer: { live: null, stale: 'last refresh 21:30 ET' } }));
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    expect(h.result.current.footer).toBe('last refresh 21:30 ET');
    await advance(60_000);
    expect(posts().length).toBe(1);
    await advance(CARD_LIVE_CLOSED_MS - 60_000);
    expect(posts().length).toBe(2);
  });

  it('NEGATIVE a hanging request → no second POST while it hangs', async () => {
    queue = [hang()];
    mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    await advance(10 * CARD_LIVE_MS);
    expect(posts().length).toBe(1);
  });

  it('hidden for longer than the cadence, then visible → an immediate POST', async () => {
    let hidden = true;
    const spy = vi.spyOn(document, 'hidden', 'get').mockImplementation(() => hidden);
    mount();
    await advance(CARD_LIVE_MS + 5000);
    expect(posts().length).toBe(0);
    hidden = false;
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await advance(50);
    expect(posts().length).toBe(1);
    spy.mockRestore();
  });

  it('NEGATIVE visible again soon after a tick → no extra POST', async () => {
    mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    await advance(2000);
    await act(async () => { document.dispatchEvent(new Event('visibilitychange')); });
    await advance(50);
    expect(posts().length).toBe(1);
  });
});

describe('useCardLive — failures keep the last good answer', () => {
  it('an HTTP failure after a good answer → footer = lastGood.footer.stale, answer kept', async () => {
    queue = [ok(ans()), http(503)];
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    const good = h.result.current.answer;
    expect(good).not.toBeNull();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(2);
    expect(h.result.current.footer).toBe('last refresh 11:15 ET');
    expect(h.result.current.answer).toBe(good);
  });

  it('a fault answer after a good answer → same', async () => {
    queue = [ok(ans()), ok(ans({ fault: 'live quotes unavailable', footer: { live: null, stale: null } }))];
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    const good = h.result.current.answer;
    await advance(CARD_LIVE_MS + 100);
    expect(h.result.current.footer).toBe('last refresh 11:15 ET');
    expect(h.result.current.answer).toBe(good);
  });

  it('a thrown fetch or a bad shape (a board payload) → same', async () => {
    queue = [ok(ans()), async () => { throw new Error('net'); }, ok({ tab: 'vcp', tiles: [] })];
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    const good = h.result.current.answer;
    await advance(CARD_LIVE_MS + 100);
    expect(h.result.current.footer).toBe('last refresh 11:15 ET');
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(3);
    expect(h.result.current.footer).toBe('last refresh 11:15 ET');
    expect(h.result.current.answer).toBe(good);
  });

  it('NEGATIVE a failure before any good answer → no footer word', async () => {
    queue = [http(500)];
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(h.result.current.footer).toBeNull();
    expect(h.result.current.answer).toBeNull();
  });
});

describe('useCardLive — board refetch (resetKey)', () => {
  it('resetKey change → answer null at once; a deferred in-flight answer from before is DROPPED', async () => {
    queue = [ok(ans())];
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(h.result.current.answer).not.toBeNull();
    const d = deferred(ans({ session: 'afterhours' }));
    queue = [d.resp, hang()];
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(2);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'rth' });
    expect(h.result.current.answer).toBeNull();
    await act(async () => { d.resolve(); });
    await advance(100);
    expect(h.result.current.answer).toBeNull();
  });

  it('C3: a board refetch fires ONE tick at once', async () => {
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    await advance(10_000);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'rth' });
    await advance(100);
    expect(posts().length).toBe(2);
    expect(h.result.current.answer).not.toBeNull();
    await advance(CARD_LIVE_MS - 1000);
    expect(posts().length).toBe(2);
    await advance(1100);
    expect(posts().length).toBe(3);
  });

  it('C1: lastGood "closed", then board data stamped "premarket" → a POST at 30 s (not 30 min)', async () => {
    queue = [ok(ans({ session: 'closed', footer: { live: null, stale: 'last refresh 03:55 ET' } })), http(503)];
    const h = mount({ initialSession: 'closed' });
    await advance(CARD_LIVE_CLOSED_MS + 100);
    expect(posts().length).toBe(1);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'premarket' });
    await advance(100);
    expect(posts().length).toBe(2);            // the C3 refetch tick (answered 503)
    await advance(CARD_LIVE_MS);
    expect(posts().length).toBe(3);            // paced by the board's premarket stamp
  });

  it('C1/C3 + D3 closed: 5-min board refetches that still say closed → ONE POST per 30 closed minutes, never zero', async () => {
    fallback = ok(ans({ session: 'closed', footer: { live: null, stale: 'last refresh 21:30 ET' } }));
    const h = mount({ initialSession: 'closed' });
    let k = 1;
    const refetchFor = async (minutes: number) => {
      for (let m = 0; m < minutes; m += 5) {
        await advance(5 * 60_000);
        k += 1;
        h.rerender({ syms: SYMS, enabled: true, resetKey: k, initialSession: 'closed' });
      }
      await advance(100);
    };
    await refetchFor(25);
    expect(posts().length).toBe(0);            // NEGATIVE: no refetch tick while closed
    await refetchFor(5);
    expect(posts().length).toBe(1);            // the 30-min closed read survived six refetches
    await refetchFor(60);
    expect(posts().length).toBe(3);            // 2 per hour, not 12
  });

  it('NEGATIVE closed: a refetch stamped closed right after a POST → no POST at once', async () => {
    fallback = ok(ans({ session: 'closed', footer: { live: null, stale: 'last refresh 21:30 ET' } }));
    const h = mount({ initialSession: 'closed' });
    await advance(CARD_LIVE_CLOSED_MS + 100);
    expect(posts().length).toBe(1);
    await advance(60_000);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'closed' });
    await advance(100);
    expect(posts().length).toBe(1);
    expect(h.result.current.answer).toBeNull();  // the board refetch still wins
    await advance(CARD_LIVE_CLOSED_MS - 60_000 - 1000);
    expect(posts().length).toBe(1);
    await advance(1100);
    expect(posts().length).toBe(2);            // paced from the last POST, not from the refetch
  });

  it('C1: closed pacing, then a refetch stamped "premarket" → a POST at once (the closed wait is dropped)', async () => {
    fallback = ok(ans({ session: 'premarket' }));
    const h = mount({ initialSession: 'closed' });
    await advance(5 * 60_000);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'closed' });
    await advance(100);
    expect(posts().length).toBe(0);
    await advance(5 * 60_000);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 3, initialSession: 'premarket' });
    await advance(100);
    expect(posts().length).toBe(1);
    await advance(CARD_LIVE_MS);
    expect(posts().length).toBe(2);
  });

  it('NEGATIVE the first board read waits one cadence (no tick at the first arm)', async () => {
    const h = mount({ syms: [] });
    await advance(5000);
    h.rerender({ syms: SYMS, enabled: true, resetKey: 2, initialSession: 'rth' });
    await advance(5000);
    expect(posts().length).toBe(0);
    await advance(CARD_LIVE_MS);
    expect(posts().length).toBe(1);
  });

  it('a new symbol set clears the footer of the previous board', async () => {
    const h = mount();
    await advance(CARD_LIVE_MS + 100);
    expect(h.result.current.footer).not.toBeNull();
    queue = [hang()];
    h.rerender({ syms: ['AAPL'], enabled: true, resetKey: 2, initialSession: 'rth' });
    await advance(50);
    expect(h.result.current.footer).toBeNull();
    expect(h.result.current.answer).toBeNull();
  });
});
