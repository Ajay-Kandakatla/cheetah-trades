/* ✕ / × on Gajjala's Watch — hidden at once, never a dead tap (2026-11-19, watch-newest spec §3.4 step 6, WP-FE-board).
 * Ajay: "The X buttons are not working" (and the relayed "When I add a new ticket they are gettinf added in to que but not
 * active"). One `busy` used to disable EVERY ✕ / × while any write was in flight, and the removed tile stayed up with a
 * live ✕ until the re-GET. Now: `busy` = the add box's own POST only; a × hides its name NOW; writes run one after another
 * in a queue that cannot die (`then(task, task)`); ONE full re-GET when it drains; a served error / failed request brings
 * the name back; loads are sequenced. A write that never answers holds the queue (no abort time — HIS CALL #12).
 * NEGATIVES throughout. */
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import GajjalaWatchBoard from './GajjalaWatchBoard';
import { GGW_PATH, ggwSymbolPath } from '../lib/gajjalaWatch';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const RAW = fixture as any;
function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    get length() { return m.size; }, clear: () => m.clear(), key: (i: number) => Array.from(m.keys())[i] ?? null,
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
  } as Storage;
}
function rowOf(sym: string): any {
  const base = clone(RAW.rows[2]);
  base.symbol = sym;
  base.text = String(base.text).split('XYZQ').join(sym);
  return { ...base, auto: null, aplus: null, added_at: null };
}
let server: string[] = [];
let extra: Record<string, unknown> = {};
function board(): any {
  const b = clone(RAW);
  b.rows = server.map(rowOf);
  b.symbols = [...server];
  b.refresh_sec = 0;
  b.next_window_sec = null;
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  return { ...b, ...extra };
}
const res = (body: unknown) => ({ ok: true, json: async () => body }) as unknown as Response;
function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((a, b) => { resolve = a; reject = b; });
  return { promise, resolve, reject };
}

type Call = { url: string; method: string };
let calls: Call[] = [];
/** Per-request override: return a Response / a Promise (held) — or undefined for the default (the server list). */
let hook: (c: Call, nBoard: number) => Response | Promise<Response> | undefined = () => undefined;
let loc = '';
function Probe() { loc = useLocation().search; return null; }
const q = () => new URLSearchParams(loc);
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const flushN = async (n = 6) => { for (let i = 0; i < n; i += 1) await flush(); };

async function mount(search = '&per=2') {
  vi.stubGlobal('matchMedia', (qq: string) => ({ matches: false, media: qq, addEventListener: () => {}, removeEventListener: () => {} }));
  let nBoard = 0;
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    const c = { url, method };
    calls.push(c);
    if (method === 'GET' && url.endsWith(GGW_PATH)) nBoard += 1;
    const o = hook(c, nBoard);
    if (o !== undefined) return o;
    if (url.includes('/chart-maps/gajjala-watch/symbols/')) {
      const sym = decodeURIComponent(url.split('/').pop() as string).toUpperCase();
      if (method === 'DELETE') {
        server = server.filter((s) => s !== sym);
        return res({ state: 'removed', symbols: server, symbol: sym, text: null });
      }
      if (method === 'POST') {
        if (!server.includes(sym)) server = [sym, ...server];
        return res({ state: 'added', symbols: server, symbol: sym, text: `${sym} added` });
      }
    }
    return res(board());
  }));
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?tab=gajjala_watch${search}`]}><GajjalaWatchBoard /><Probe /></MemoryRouter>);
  await flushN(4);
  return r.container;
}
const tileEl = (s: string) => screen.queryByTestId(`ggw-tile-${s}`);
const tileX = (s: string) => tileEl(s)!.querySelector('button.ggw-remove') as HTMLButtonElement;
const pagerX = (s: string) => screen.queryByTestId(`ggw-pager-x-${s}`) as HTMLButtonElement | null;
const dels = () => calls.filter((c) => c.method === 'DELETE');
const isBoardGet = (c: Call) => c.method === 'GET' && c.url.endsWith(GGW_PATH);
const boardGetsAfter = (c: Call) => calls.slice(calls.indexOf(c) + 1).filter(isBoardGet);
const msg = () => screen.queryByTestId('ggw-msg')?.textContent ?? null;
const input = (c: HTMLElement) => c.querySelector('input.ggw-input') as HTMLInputElement;
function submit(c: HTMLElement, sym: string) {
  fireEvent.change(input(c), { target: { value: sym } });
  fireEvent.submit(input(c).closest('form')!);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.stubGlobal('localStorage', memStorage());
  calls = [];
  server = ['A', 'B', 'C', 'D'];
  extra = {};
  hook = () => undefined;
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('✕ / × hide at once and are never a dead tap', { timeout: 20000 }, () => {
  it('✕ hides while a POST is in flight: tile + pager item leave at once, nothing disabled; the DELETE goes AFTER the POST, then ONE full GET', async () => {
    const post = deferred<Response>();
    hook = (c) => (c.method === 'POST' ? post.promise : undefined);
    const c = await mount();
    submit(c, 'NEW');
    await flush();
    expect(input(c).disabled).toBe(true);                                  // the box: its own POST only
    fireEvent.click(tileX('A'));
    expect(tileEl('A')).toBeNull();
    expect(pagerX('A')).toBeNull();
    expect(screen.queryByTestId('ggw-pager-A')).toBeNull();
    expect(tileX('B').disabled).toBe(false);
    expect(pagerX('B')!.disabled).toBe(false);
    await flushN();
    expect(dels()).toHaveLength(0);                                        // serialized: waits its turn
    server = ['NEW', ...server];
    post.resolve(res({ state: 'added', symbols: server, symbol: 'NEW', text: 'NEW added' }));
    await flushN();
    const p = calls.find((x) => x.method === 'POST')!;
    expect(dels()).toHaveLength(1);
    expect(calls.indexOf(dels()[0])).toBeGreaterThan(calls.indexOf(p));
    expect(boardGetsAfter(p)).toHaveLength(1);
    expect(boardGetsAfter(dels()[0])).toHaveLength(1);
    expect(tileEl('A')).toBeNull();
    expect(input(c).disabled).toBe(false);
  });
  it('[C2] the queue never dies: the first DELETE fails on the network while a second × waits → the first comes back (msg null), the second STILL goes out, ONE full GET', async () => {
    const first = deferred<Response>();
    hook = (c) => (c.method === 'DELETE' && c.url.endsWith(ggwSymbolPath('A')) ? first.promise : undefined);
    await mount();
    fireEvent.click(pagerX('A')!);
    await flush();
    fireEvent.click(pagerX('B')!);
    expect(tileEl('A')).toBeNull();
    expect(tileEl('B')).toBeNull();
    await flushN();
    expect(dels()).toHaveLength(1);
    first.reject(new TypeError('network'));
    await flushN();
    expect(dels().map((d) => d.url.split('/').pop())).toEqual(['A', 'B']);
    expect(boardGetsAfter(dels()[0])).toHaveLength(1);
    expect(tileEl('A')).not.toBeNull();                                    // the server still lists it: it comes back
    expect(tileEl('B')).toBeNull();
    expect(msg()).toBeNull();
  });
  it('[C2] a 200 with a junk body (r.json rejects) → the next write still goes out', async () => {
    hook = (c) => (c.method === 'DELETE' && c.url.endsWith(ggwSymbolPath('A'))
      ? ({ ok: true, json: () => Promise.reject(new SyntaxError('junk')) } as unknown as Response) : undefined);
    await mount();
    fireEvent.click(pagerX('A')!);
    fireEvent.click(pagerX('B')!);
    await flushN();
    expect(dels().map((d) => d.url.split('/').pop())).toEqual(['A', 'B']);
    expect(tileEl('A')).not.toBeNull();                                    // no confirmed answer → the reload shows it
    expect(tileEl('B')).toBeNull();
  });
  it('NEGATIVE (HIS CALL #12, the honest hold): a POST that never answers → a × still hides at once and is not disabled; its DELETE is NOT sent; nothing re-shows it', async () => {
    extra = { refresh_sec: 60 };
    hook = (c) => (c.method === 'POST' ? new Promise<Response>(() => {}) : undefined);
    const c = await mount();
    submit(c, 'NEW');
    await flush();
    fireEvent.click(tileX('A'));
    expect(tileEl('A')).toBeNull();
    expect(pagerX('B')!.disabled).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(130_000); });  // two minute re-GETs still list A
    expect(dels()).toHaveLength(0);
    expect(calls.filter(isBoardGet).length).toBeGreaterThanOrEqual(3);
    expect(tileEl('A')).toBeNull();
  });
  it('pager × and tile ✕ send the same DELETE path (ggwSymbolPath)', async () => {
    await mount();
    fireEvent.click(pagerX('A')!);
    await flushN();
    fireEvent.click(tileX('B'));
    await flushN();
    expect(dels()).toHaveLength(2);
    expect(dels()[0].url.endsWith(ggwSymbolPath('A'))).toBe(true);
    expect(dels()[1].url.endsWith(ggwSymbolPath('B'))).toBe(true);
    expect(dels()[0].url.replace(/A$/, 'B')).toBe(dels()[1].url);
  });
  it('a × on a picked name prunes it from show=; the last picked name → no show=', async () => {
    await mount('&per=2&show=A,B');
    expect(q().get('show')).toBe('A,B');
    fireEvent.click(tileX('A'));
    await flushN();
    expect(q().get('show')).toBe('B');
    fireEvent.click(tileX('B'));
    await flushN();
    expect(q().has('show')).toBe(false);
  });
  it('NEGATIVE: a served error → the name comes back with the served words; a network failure → it comes back, msg null', async () => {
    let mode: 'error' | 'net' = 'error';
    hook = (c) => {
      if (c.method !== 'DELETE') return undefined;
      return mode === 'error' ? res({ state: 'error', symbols: [], symbol: 'A', text: 'served error words' })
        : Promise.reject(new TypeError('network'));
    };
    await mount();
    fireEvent.click(tileX('A'));
    expect(tileEl('A')).toBeNull();
    await flushN();
    expect(tileEl('A')).not.toBeNull();
    expect(msg()).toBe('served error words');
    mode = 'net';
    fireEvent.click(tileX('A'));
    expect(tileEl('A')).toBeNull();
    await flushN();
    expect(tileEl('A')).not.toBeNull();
    expect(msg()).toBeNull();
  });
  it('NEGATIVE: a stale full GET issued before the DELETE but resolving after the post-DELETE GET never re-shows the name', async () => {
    extra = { refresh_sec: 60 };
    const stale = deferred<Response>();
    hook = (c, n) => (c.method === 'GET' && c.url.endsWith(GGW_PATH) && n === 2 ? stale.promise : undefined);
    await mount();
    await act(async () => { await vi.advanceTimersByTimeAsync(60_100); });  // the minute GET (#2) is out, held
    expect(calls.filter(isBoardGet)).toHaveLength(2);
    const before = board();                                                 // the server's board BEFORE the ×: lists A
    fireEvent.click(tileX('A'));
    await flushN();
    expect(calls.filter(isBoardGet)).toHaveLength(3);                       // the post-DELETE GET answered (no A)
    expect(tileEl('A')).toBeNull();
    stale.resolve(res(before));
    await flushN();
    expect(tileEl('A')).toBeNull();
  });
  it('NEGATIVE: a confirmed removal that the next server board still lists is shown again (truth wins)', async () => {
    hook = (c) => (c.method === 'DELETE' ? res({ state: 'removed', symbols: server, symbol: 'A', text: null }) : undefined);
    await mount();
    fireEvent.click(tileX('A'));
    expect(tileEl('A')).toBeNull();
    await flushN();
    expect(tileEl('A')).not.toBeNull();
  });
  it('NEGATIVE: the add box is disabled only during its own POST', async () => {
    const del = deferred<Response>();
    const post = deferred<Response>();
    hook = (c) => (c.method === 'DELETE' ? del.promise : c.method === 'POST' ? post.promise : undefined);
    const c = await mount();
    fireEvent.click(tileX('A'));
    await flush();
    expect(input(c).disabled).toBe(false);
    fireEvent.change(input(c), { target: { value: 'NEW' } });
    expect((c.querySelector('button.ggw-add-btn') as HTMLButtonElement).disabled).toBe(false);
    fireEvent.submit(input(c).closest('form')!);
    await flush();
    expect(input(c).disabled).toBe(true);
    del.resolve(res({ state: 'removed', symbols: [], symbol: 'A', text: null }));
    await flushN();
    expect(calls.filter((x) => x.method === 'POST')).toHaveLength(1);
    expect(input(c).disabled).toBe(true);
    post.resolve(res({ state: 'added', symbols: [], symbol: 'NEW', text: 'NEW added' }));
    await flushN();
    expect(input(c).disabled).toBe(false);
  });
  it('three rapid × on three names → three DELETEs in tap order, ONE reload', async () => {
    await mount();
    fireEvent.click(pagerX('C')!);
    fireEvent.click(pagerX('A')!);
    fireEvent.click(pagerX('B')!);
    expect(['A', 'B', 'C'].map(tileEl)).toEqual([null, null, null]);
    await flushN(10);
    expect(dels().map((d) => d.url.split('/').pop())).toEqual(['C', 'A', 'B']);
    expect(boardGetsAfter(dels()[0])).toHaveLength(1);
    expect(tileEl('D')).not.toBeNull();
  });
});
