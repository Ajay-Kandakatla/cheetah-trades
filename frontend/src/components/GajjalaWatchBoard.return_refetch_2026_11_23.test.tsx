/* 👀 Gajjala's Watch — the return GET on the REAL board (2026-11-23, spec ggconn §3.2, WP-2).
 * Back to the tab with the last full GET ISSUED at least one served refresh_sec ago → ONE full GET at once; the next one
 * a full refresh_sec after THAT landing. [C9] a GET that never answers does not block the return, and its late answer
 * (or rejection) changes nothing and arms nothing (loadSeq).
 * The REAL board, the REAL hook (useGgwLive), the 2026-11-15 fixture (served refresh_sec 60) minus its pending row.
 * fetch is a routed stub; the bus is a hand-driven `subscribe`. Every word is a stand-in for a served one. NEGATIVES:
 * a young GET (done or in flight) → none and the armed timer fires on time; a `visibilitychange` while still hidden →
 * none; out of window (refresh_sec 0) → none; owner_only → none; after unmount → none; the live-interest POST count is
 * the hook's own on return, none from this effect. */
import { act, render } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { CARD_LIVE_MS } from '../lib/cardLive';
import { GGW_FETCH_FAILED, GGW_LIVE_PATH, GGW_PATH, GGW_TAB } from '../lib/gajjalaWatch';

vi.mock('../lib/eventBus', () => ({ subscribe: () => () => {} }));

import GajjalaWatchBoard from './GajjalaWatchBoard';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const SERVED_TITLE = 'served title: current';
const OLD_TITLE = 'served title: the superseded answer';
function okBoard(mut: (b: any) => void = () => {}) {
  const b = clone(fixture) as any;
  b.rows = b.rows.filter((r: any) => r.state !== 'pending');
  delete b.pending_poll_sec;
  delete b.pending_wait_max_sec;
  b.symbols = b.rows.map((r: any) => r.symbol);
  b.title = SERVED_TITLE;
  mut(b);
  return b;
}
const REFRESH_MS = (fixture as any).refresh_sec * 1000;

type Call = { url: string; method: string };
type Gate = { resolve: (b: any) => void; reject: (e: unknown) => void };
let boardNow: () => any = () => okBoard();
let calls: Call[] = [];
let hangNext = false;
let gates: Gate[] = [];
function stubFetch() {
  calls = [];
  gates = [];
  hangNext = false;
  vi.stubGlobal('fetch', vi.fn(async (u: RequestInfo | URL, init?: RequestInit) => {
    const url = String(u);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url, method });
    if (method === 'POST' && url.endsWith(GGW_LIVE_PATH)) {
      return { ok: true, json: async () => ({ state: 'ok', stream: { on: true, word: 'served feed word', state: 'live' }, tab: GGW_TAB, symbols: [] }) } as unknown as Response;
    }
    if (method === 'GET' && url.endsWith(GGW_PATH) && hangNext) {
      hangNext = false;
      return new Promise<Response>((resolve, reject) => {
        gates.push({ resolve: (b) => resolve({ ok: true, json: async () => b } as unknown as Response), reject });
      });
    }
    return { ok: true, json: async () => boardNow() } as unknown as Response;
  }));
}
const fullGets = () => calls.filter((c) => c.method === 'GET' && c.url.endsWith(GGW_PATH));
const posts = () => calls.filter((c) => c.method === 'POST' && c.url.endsWith(GGW_LIVE_PATH));
const flush = () => act(async () => { await vi.advanceTimersByTimeAsync(0); });
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const setHidden = (h: boolean) => Object.defineProperty(document, 'hidden', { configurable: true, get: () => h });
const fireVis = () => act(async () => { document.dispatchEvent(new Event('visibilitychange')); await vi.advanceTimersByTimeAsync(0); });
const hide = () => { setHidden(true); return fireVis(); };
const show = () => { setHidden(false); return fireVis(); };
async function mount() {
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala_watch&per=9']}><GajjalaWatchBoard /></MemoryRouter>);
  await flush();
  await flush();
  return r;
}
const titleOf = (root: ParentNode) => root.querySelector('.ggw-title')?.textContent ?? null;

beforeEach(() => {
  vi.useFakeTimers();
  boardNow = () => okBoard();
  stubFetch();
  vi.stubGlobal('EventSource', class {});
  setHidden(false);
});
afterEach(() => { setHidden(false); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('👀 return GET — the chain', () => {
  it('fixture self-check: the served refresh_sec is 60 and the board is ok in window', () => {
    expect(REFRESH_MS).toBe(60_000);
    expect(okBoard().state).toBe('ok');
  });
  it('hidden across a tick → 0 GETs (the tick re-arms); return → EXACTLY one GET at once; the next one refresh_sec after that landing', async () => {
    await mount();
    expect(fullGets()).toHaveLength(1);
    await hide();
    await advance(REFRESH_MS + 10_000);                // the 60 s tick fires hidden: re-armed, no fetch
    expect(fullGets()).toHaveLength(1);
    await show();
    expect(fullGets()).toHaveLength(2);                // ONE at once
    await advance(REFRESH_MS - 100);
    expect(fullGets()).toHaveLength(2);                // 59.9 s after the landing → none
    await advance(200);
    expect(fullGets()).toHaveLength(3);                // +0.2 s → one
    await advance(REFRESH_MS - 300);                   // that GET landed at +60 s; 59.9 s after it → none
    expect(fullGets()).toHaveLength(3);                // and the chain runs on from there, one at a time
    await advance(200);
    expect(fullGets()).toHaveLength(4);
  });
  it('five rapid hide / show after the return GET → still one', async () => {
    await mount();
    await hide();
    await advance(REFRESH_MS + 5_000);
    await show();
    expect(fullGets()).toHaveLength(2);
    for (let i = 0; i < 5; i += 1) { await hide(); await advance(100); await show(); }
    expect(fullGets()).toHaveLength(2);
  });
});

describe('👀 return GET — [C9] a GET that never answers', () => {
  async function deadThenReturn() {
    const r = await mount();
    hangNext = true;
    await advance(REFRESH_MS);                          // the visible 60 s tick issues GET #2: it never answers
    expect(fullGets()).toHaveLength(2);
    expect(gates).toHaveLength(1);
    await hide();
    await advance(REFRESH_MS + 10_000);                 // GET #2 is now more than one cadence old
    expect(fullGets()).toHaveLength(2);                 // nothing re-armed the chain (GET #2 never landed)
    await show();
    expect(fullGets()).toHaveLength(3);                 // the dead one does not block the return: EXACTLY one new GET
    return r;
  }
  it('its late ANSWER changes nothing and arms nothing (the chain stays on the return GET\'s landing)', async () => {
    const r = await deadThenReturn();
    expect(titleOf(r.container)).toBe(SERVED_TITLE);
    await advance(20_000);
    await act(async () => { gates[0].resolve(okBoard((b) => { b.title = OLD_TITLE; })); await vi.advanceTimersByTimeAsync(0); });
    expect(titleOf(r.container)).toBe(SERVED_TITLE);    // superseded: dropped (loadSeq)
    expect(fullGets()).toHaveLength(3);
    await advance(REFRESH_MS - 20_000 - 100);           // 59.9 s after the return GET's landing → none
    expect(fullGets()).toHaveLength(3);
    await advance(200);                                 // 60.1 s → one (a re-arm at the late answer would put it 20 s later)
    expect(fullGets()).toHaveLength(4);
    await advance(REFRESH_MS + 20_000);
    expect(fullGets()).toHaveLength(5);                 // ONE chain, never two
  });
  it('its late REJECTION changes nothing and arms nothing (no ⚠️ failed line)', async () => {
    const r = await deadThenReturn();
    await advance(20_000);
    await act(async () => { gates[0].reject(new Error('503')); await vi.advanceTimersByTimeAsync(0); });
    expect(r.container.textContent).not.toContain(`⚠️ ${GGW_FETCH_FAILED}`);
    expect(fullGets()).toHaveLength(3);
    await advance(REFRESH_MS - 20_000 - 100);
    expect(fullGets()).toHaveLength(3);
    await advance(200);
    expect(fullGets()).toHaveLength(4);
  });
  it('NEGATIVE: a GET in flight and YOUNGER than one cadence at the return → no second one', async () => {
    await mount();
    hangNext = true;
    await advance(REFRESH_MS);                          // GET #2 issued, never answers
    expect(fullGets()).toHaveLength(2);
    await hide();
    await advance(10_000);
    await show();                                       // GET #2 is 10 s old
    expect(fullGets()).toHaveLength(2);
  });
});

describe('👀 return GET — NEGATIVES', () => {
  it('the last full GET younger than one cadence → no GET, and the armed timer still fires on time', async () => {
    await mount();
    await advance(10_000);
    await hide();
    await advance(20_000);
    await show();                                       // 30 s after the landing
    expect(fullGets()).toHaveLength(1);
    await advance(REFRESH_MS - 30_000 - 100);
    expect(fullGets()).toHaveLength(1);
    await advance(200);                                 // 60.1 s after the first landing: the chain's own tick
    expect(fullGets()).toHaveLength(2);
  });
  it('a visibilitychange while STILL hidden → none', async () => {
    await mount();
    await hide();
    await advance(REFRESH_MS + 10_000);
    await fireVis();
    await fireVis();
    expect(fullGets()).toHaveLength(1);
  });
  it('out of window (refresh_sec 0) → none', async () => {
    boardNow = () => okBoard((b) => { b.refresh_sec = 0; b.next_window_sec = null; });
    await mount();
    await hide();
    await advance(REFRESH_MS * 3);
    await show();
    expect(fullGets()).toHaveLength(1);
  });
  it('owner_only → none', async () => {
    boardNow = () => ({ state: 'owner_only', reason: 'Shown to the account owner only.', title: 'x' });
    await mount();
    await hide();
    await advance(REFRESH_MS * 3);
    await show();
    expect(fullGets()).toHaveLength(1);
  });
  it('after unmount → none', async () => {
    const r = await mount();
    await hide();
    r.unmount();
    await advance(REFRESH_MS * 3);
    await show();
    expect(fullGets()).toHaveLength(1);
  });
  it('the live-interest POST count: on return only the hook\'s own POST, none from this effect or its landing', async () => {
    await mount();
    expect(posts()).toHaveLength(1);                    // the hook's arm
    await hide();
    await advance(REFRESH_MS + 10_000);                 // hidden: the hook's 30 s ticks POST nothing
    expect(posts()).toHaveLength(1);
    await show();
    expect(fullGets()).toHaveLength(2);
    expect(posts()).toHaveLength(2);                    // the hook's own return POST (last one ≥ CARD_LIVE_MS old)
    await flush();
    await advance(CARD_LIVE_MS - 100);
    expect(posts()).toHaveLength(2);                    // the landing (same list) adds none
  });
  it('NEGATIVE: a young return (both rules say no) → no GET and no POST', async () => {
    await mount();
    await advance(5_000);
    await hide();
    await advance(5_000);
    await show();
    expect(fullGets()).toHaveLength(1);
    expect(posts()).toHaveLength(1);
  });
});

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
const noComments = (t: string) => t.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');

describe('👀 return GET — source guards', () => {
  it('ggwReturnRefetch( exactly once; ONE visibilitychange listener; fullAt stamped right after ++loadSeq', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchBoard.tsx'));
    expect(src.match(/ggwReturnRefetch\(/g) ?? []).toHaveLength(1);
    expect(src.match(/addEventListener\('visibilitychange'/g) ?? []).toHaveLength(1);
    expect(src).toMatch(/const my = \+\+loadSeq\.current;\s*fullAt\.current = Date\.now\(\);\s*getJson\(GGW_PATH\)/);
    expect(src.match(/fullAt\.current = /g) ?? []).toHaveLength(1);     // stamped at ISSUE only, never at a landing
  });
  it('NEGATIVE: no 30_000 / 60_000 literal, no fullBusy, no .finally in loadAll; ggwRowLive(r) still present', async () => {
    const src = noComments(await readSource('src/components/GajjalaWatchBoard.tsx'));
    for (const bad of ['30_000', '60_000', '30000', '60000', 'fullBusy']) expect(src).not.toContain(bad);
    const loadAll = src.slice(src.indexOf('const loadAll = useCallback'), src.indexOf('loadAllRef.current = loadAll;'));
    expect(loadAll.length).toBeGreaterThan(0);
    expect(loadAll).not.toContain('.finally');
    expect(src).toMatch(/ggwRowLive\(r\)/);
    expect(src).toMatch(/ggwFrameMetas\(load\.p\.rows\)/);
  });
});
