import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { act, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ChartMaps } from './ChartMaps';
import { CARD_LIVE_MS } from '../lib/cardLive';
import { defaultHidden, saveHidden } from '../lib/chartOverlays';

/* 🔴 Live cards on the page (BUILD_SPEC8 §3.5 / §4 WP-C, AMENDMENTS8 C3).
 * Ajay 2026-10-16: "actual price is this  above but it stale value".
 *
 * A routed fetch stub: GET /chart-maps?… → a one-tile XLAB board (last bar
 * 2026-10-16 close 2.64, now line 2.64); POST /chart-maps/live → the frozen
 * §3.3 XLAB answer. The words on screen are the served ones — the page adds
 * none. NEGATIVES: nothing moves before the first tick; an older served bar
 * leaves the candle alone; a quote of NaN / null fields prints no junk; the
 * polls never count as board fetches. */

const XLAB_BARS = [
  { t: '2026-10-14', o: 1.3, h: 1.4, l: 1.25, c: 1.33, v: 2e6 },
  { t: '2026-10-15', o: 1.33, h: 1.4, l: 1.3, c: 1.36, v: 2e6 },
  { t: '2026-10-16', o: 1.41, h: 2.7, l: 1.38, c: 2.64, v: 4e7 },
];

const board = (nowPx: number) => ({
  tab: 'vcp', count: 1, matched: 1, scanned: 1, tape_session: 'rth',
  tiles: [{
    symbol: 'XLAB', name: 'XLAB Inc.', href: '/sepa/XLAB?tab=setup',
    bars: XLAB_BARS.map((b, i) => (i === XLAB_BARS.length - 1 ? { ...b, c: nowPx } : b)),
    bands: [], markers: [], stats: [], why: 'test tile', badges: [],
    lines: [{ price: nowPx, label: 'now', tone: 'now' }],
  }],
});

const LIVE = {
  session: 'rth', as_of_epoch: 1792170942.1, as_of: '2026-10-16 11:15:42 ET',
  footer: { live: 'live · 11:15:42 ET', stale: 'last refresh 11:15 ET' },
  now_labels: ['now', 'now · pre', 'now · AH'],
  cap: 250, asked: 1, served: 1, missing: [], fault: null,
  quotes: {
    XLAB: {
      bar: { t: '2026-10-16', o: 1.41, h: 2.95, l: 1.38, c: 2.77, v: 51234567.0 },
      prev_t: '2026-10-15',
      now: { price: 2.77, label: 'now', session: null, add_line: false,
             as_of_epoch: 1792170940.5, as_of: '11:15:40 ET' },
    },
  },
};

type Resp = () => Promise<unknown>;
const ok = (j: unknown): Resp => async () => ({ ok: true, status: 200, json: async () => j });
let boardPx = 2.64;
let liveQueue: Resp[] = [];
let liveFallback: Resp = ok(LIVE);

const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
  const u = String(url);
  if (u.endsWith('/chart-maps/live')) return (liveQueue.shift() ?? liveFallback)();
  if (u.includes('/chart-maps?')) return ok(board(boardPx))();
  return ok({ tab: 'vcp', count: 0, tiles: [] })();
});
const allCalls = () => fetchMock.mock.calls.map(([u]) => String(u));
const boardCalls = () => allCalls().filter((u) => u.includes('/chart-maps?'));
const livePosts = () => allCalls().filter((u) => u.endsWith('/chart-maps/live'));

const TRACK = vi.hoisted(() => ({ trackFeature: vi.fn() }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: TRACK.trackFeature }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps']), catalog: [], email: null }),
}));

const draw = () => render(<MemoryRouter initialEntries={['/chart-maps?tab=vcp']}><ChartMaps /></MemoryRouter>);
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const stamp = (c: HTMLElement) => (c.querySelector('.cm-scanstamp')?.textContent || '').trim();
const lastStats = (c: HTMLElement) => Array.from(c.querySelectorAll('.cm-stat'))
  .filter((s) => s.querySelector('.cm-stat-k')?.textContent === 'Last')
  .map((s) => s.querySelector('.cm-stat-v')?.textContent);
const text = (c: HTMLElement) => c.textContent || '';
/** The house-banned word (say "reversal"), assembled so this file never spells it. */
const BWORD = new RegExp(['b', 'o', 'u', 'n', 'c'].join(''), 'i');

/* The now line is its own ledger family and OFF by default; he reads it with
 * the box ticked (his screenshot), so the test viewer ticks it too. */
const memStorage = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => { m.clear(); },
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
  } as Storage;
};
const showNowLine = () => {
  vi.stubGlobal('localStorage', memStorage());
  const h = defaultHidden();
  h.delete('now');
  saveHidden(h);
};

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  boardPx = 2.64;
  liveQueue = [];
  liveFallback = ok(LIVE);
  fetchMock.mockClear();
  vi.stubGlobal('fetch', fetchMock);
  showNowLine();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('ChartMaps — live cards', () => {
  it('after one cadence the card reads the served now label and the stamp ends with the served footer', async () => {
    const { container } = draw();
    expect(await screen.findByText('XLAB')).toBeInTheDocument();
    // NEGATIVE before the first tick: neither the moved label nor the footer.
    expect(text(container)).toContain('now 2.64');
    expect(text(container)).not.toContain('now 2.77');
    expect(stamp(container).endsWith('live · 11:15:42 ET')).toBe(false);
    expect(livePosts().length).toBe(0);
    await advance(CARD_LIVE_MS + 200);
    expect(livePosts().length).toBe(1);
    expect(text(container)).toContain('now 2.77');
    expect(text(container)).not.toContain('now 2.64');
    expect(stamp(container).endsWith('live · 11:15:42 ET')).toBe(true);
    expect(lastStats(container).length).toBeGreaterThan(0);
    expect(lastStats(container).every((v) => v === '2.77')).toBe(true);
  });

  it('NEGATIVE an older served bar leaves the Last stat at 2.64', async () => {
    liveFallback = ok({ ...LIVE, quotes: { XLAB: { ...LIVE.quotes.XLAB,
      bar: { ...LIVE.quotes.XLAB.bar, t: '2026-10-15' } } } });
    const { container } = draw();
    await screen.findByText('XLAB');
    await advance(CARD_LIVE_MS + 200);
    expect(livePosts().length).toBe(1);
    const last = lastStats(container);
    expect(last.length).toBeGreaterThan(0);
    expect(last.every((v) => v === '2.64')).toBe(true);
  });

  it('NEGATIVE a quote of NaN / null fields → no junk in the DOM, the board read stays', async () => {
    liveFallback = ok({ ...LIVE, quotes: { XLAB: {
      bar: { t: '2026-10-16', o: NaN, h: null, l: 1.38, c: NaN, v: null },
      prev_t: null,
      now: { price: NaN, label: null, session: null, add_line: true, as_of_epoch: null, as_of: null },
    } } });
    const { container } = draw();
    await screen.findByText('XLAB');
    await advance(CARD_LIVE_MS + 200);
    expect(livePosts().length).toBe(1);
    const html = container.innerHTML;
    for (const bad of ['NaN', 'undefined', 'null', '[object Object]']) {
      expect(html.includes(bad), bad).toBe(false);
    }
    /* The b-word: never in a word he reads, and never anywhere in the card. The
     * page's tab strip keeps the internal `tab=quick_` key in an href (an
     * identifier, labelled "Quick Reversal"), so the page-wide check is on text. */
    expect(BWORD.test(text(container))).toBe(false);
    const card = screen.getByText('XLAB').closest('.cm-tile') as HTMLElement;
    expect(card).toBeTruthy();
    expect(BWORD.test(card.innerHTML)).toBe(false);
    expect(text(container)).toContain('now 2.64');
  });

  it('a POST failure after a good answer → the stamp reads the served stale word', async () => {
    liveQueue = [ok(LIVE), async () => ({ ok: false, status: 503, json: async () => ({}) })];
    const { container } = draw();
    await screen.findByText('XLAB');
    await advance(CARD_LIVE_MS + 200);
    expect(stamp(container).endsWith('live · 11:15:42 ET')).toBe(true);
    await advance(CARD_LIVE_MS + 200);
    expect(livePosts().length).toBe(2);
    expect(stamp(container).endsWith('last refresh 11:15 ET')).toBe(true);
    expect(text(container)).toContain('now 2.77');   // the last good overlay stays
  });

  it('refetch wins: the 5-min board read shows 2.70 until the refetch tick lands, then the overlay re-applies (C3)', async () => {
    const { container } = draw();
    await screen.findByText('XLAB');
    await advance(CARD_LIVE_MS + 200);
    expect(text(container)).toContain('now 2.77');
    // Hold the polls that follow so the refetch window can be read.
    let release!: () => void;
    const held = new Promise<unknown>((r) => { release = () => r({ ok: true, status: 200, json: async () => LIVE }); });
    const before = boardCalls().length;
    boardPx = 2.70;
    liveFallback = () => held;
    await advance(5 * 60_000 - CARD_LIVE_MS);
    expect(boardCalls().length).toBe(before + 1);
    expect(text(container)).toContain('now 2.70');
    expect(text(container)).not.toContain('now 2.77');
    await act(async () => { release(); });
    await advance(100);
    expect(text(container)).toContain('now 2.77');
  });

  it('NEGATIVE the polls never count as board fetches', async () => {
    draw();
    await screen.findByText('XLAB');
    const before = boardCalls().length;
    await advance(2 * CARD_LIVE_MS + 400);
    expect(livePosts().length).toBe(2);
    expect(boardCalls().length).toBe(before);
  });
});
