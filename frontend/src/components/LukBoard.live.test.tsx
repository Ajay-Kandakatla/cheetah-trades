import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { CARD_LIVE_MS } from '../lib/cardLive';

/* 🔴 🥇 Luk realtime cards — the FE half (2026-11-12, lukrt spec §3.5 / WP-D). Ajay, verbatim: "Luks scan is not
 * realtime I see all dated values can you make it realtime".
 *
 * The REAL hook (hooks/useCardLive), the REAL splice (lib/cardLive.patchTile) and the REAL LukCard under a routed fetch
 * stub: GET /chart-maps/luk → a hand board shaped like luk/tab.build (each card's served `live_level`, the pass's served
 * `next_read_sec`); POST /chart-maps/live → a served answer shaped like chart_maps/live_card.compose (its `vs.text` /
 * `vs.pct_text` stand-ins for VS_TEXT / VS_PCT_TEXT — the board prints them verbatim). What is pinned: ONE poll, body
 * {symbols, levels} with the served levels verbatim and NO stream / variant; the served vs, pct and footer print; the
 * board re-reads at the served next-read time, re-armed after every GET (a failed one included).
 * NEGATIVES: no pct line without a served pct_text; no POST when closed or on 📓 / 🏁 / a scan sub; the overlay never
 * changes a card's state, label, order or the counts line; a stopped card is not in `levels` and prints no live line;
 * no next_read_sec → the cadence interval as before; no bus subscription, no EventSource. */

const busSubscribe = vi.fn(() => () => undefined);
const busHook = vi.fn();
vi.mock('../lib/eventBus', async (orig) => ({
  ...(await orig<typeof import('../lib/eventBus')>()), subscribe: busSubscribe, useBusEvent: busHook,
}));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: null, loading: false }) }));
vi.mock('./PatternChart', () => ({ PatternChart: (p: any) => <div data-testid={`chart-${p.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('./LukStrip', () => ({ LukStrip: () => <div /> }));
vi.mock('./LukScreens', () => ({ LukScreens: () => <div data-testid="m-screens" /> }));
vi.mock('./LukPlaybook', () => ({ LukPlaybook: () => <div data-testid="m-playbook" /> }));
vi.mock('./LukTrackRecord', () => ({ LukTrackRecord: () => <div data-testid="m-track" /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import LukBoard from './LukBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const LV_AAA = { trigger: 12.4, stop: 11.98, tf: '5m' };
const LV_BBB = { trigger: 8.2, stop: 7.91, tf: '5m' };
const TILE = (symbol: string, state: string, live_level: unknown) => ({
  symbol, href: `/sepa/${symbol}`, setup: 'opening_range_high', state, state_label: `served ${state} label`,
  trigger_text: `trigger served ${symbol}`, stop_text: `stop served ${symbol}`, criteria: [], chips: null, bars5: [],
  read_at_text: 'read 10:06 ET', live_level,
});
const SUBS = ['opening_range_high', 'pullback_reversal', 'premarket', 'playbook', 'track_record'];
function board(opts: { sub?: string; refresh?: number; next?: number | null } = {}) {
  const sub = opts.sub ?? 'opening_range_high';
  const setup = sub === 'opening_range_high' || sub === 'pullback_reversal';
  return clone({
    tab: 'luk', title: 'served title', sub, subs: SUBS.map((k) => ({ key: k, label: k, n: 1 })),
    session: { badge: 'served badge', refresh_sec: opts.refresh ?? 300, tape: 'rth' },
    pass: { at: '2026-11-12T15:31:00+00:00', text: 'served pass text · 3 of 3 board cards re-read', stale: false,
      ...(opts.next === undefined || opts.next === null ? {} : { next_read_sec: opts.next }) },
    counts_text: 'served counts 1 A+ · 1 triggered · 1 stopped',
    tiles: setup ? [TILE('AAA', 'aplus', LV_AAA), TILE('BBB', 'triggered', LV_BBB), TILE('CCC', 'stopped', null)] : [],
    screens: sub === 'premarket' ? { key: 'premarket', title: 'served screen', rows: [] } : null,
    playbook: sub === 'playbook' ? { title: 'pb', sections: [] } : null,
    track_record: sub === 'track_record' ? { title: 'tr' } : null,
  });
}

const VS_AAA = '🟢 12.55 over the trigger 12.40 on the live bar — served words';
const PCT_AAA = '+1.21% vs the trigger · +4.76% vs the stop';
const VS_BBB = '🟢 8.30 over the trigger 8.20 — served words';
const nowBlock = (price: number) => ({ price, label: 'now', session: null, add_line: true, as_of_epoch: 1794500000, as_of: '10:33:20 ET' });
const LIVE = () => ({
  session: 'rth', as_of_epoch: 1794500000, as_of: '10:33:20 ET',
  footer: { live: 'live · 10:33:20 ET', stale: 'last refresh 10:33 ET' },
  now_labels: ['now'], cap: 250, asked: 3, served: 3, missing: [], fault: null,
  quotes: {
    AAA: { bar: null, prev_t: null, now: nowBlock(12.55), vs: { kind: 'over_trigger', text: VS_AAA, pct_text: PCT_AAA } },
    BBB: { bar: null, prev_t: null, now: nowBlock(8.3), vs: { kind: 'over_trigger', text: VS_BBB } },
    CCC: { bar: null, prev_t: null, now: nowBlock(3.1) },
  },
});

let boardFor: (n: number, u: URL) => any = () => board();
let liveAnswer: () => any = LIVE;
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => liveAnswer() };
  if (u.pathname.endsWith('/chart-maps/luk')) {
    const n = gets().length;
    const b = boardFor(n, u);
    if (typeof b === 'number') return { ok: false, status: b, json: async () => ({}) };
    return { ok: true, status: 200, json: async () => b };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));
const gets = () => fetchMock.mock.calls.filter(([u, init]) =>
  new URL(String(u), 'http://x').pathname.endsWith('/chart-maps/luk') && String(init?.method || 'GET') === 'GET');
const body = (i: number) => JSON.parse(String(posts()[i][1]?.body));
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });
const mount = async (q = 'tab=luk&sub=opening_range_high') => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><LukBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.luk-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
let esCtor: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  fetchMock.mockClear();
  busSubscribe.mockClear();
  busHook.mockClear();
  boardFor = () => board();
  liveAnswer = LIVE;
  vi.stubGlobal('fetch', fetchMock);
  esCtor = vi.fn();
  vi.stubGlobal('EventSource', class { constructor(...a: unknown[]) { esCtor(...a); } });
});
afterEach(() => {
  /* restore the setInterval spies BEFORE the real timers come back — the other order leaves a dead fake behind. */
  vi.restoreAllMocks();
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe('LukBoard — 🔴 the live card poll', () => {
  it('in window on a setup sub: ONE POST after CARD_LIVE_MS, body {symbols, levels} — levels = the served live_levels verbatim, NO stream / variant', async () => {
    await mount();
    await advance(CARD_LIVE_MS - 1000);
    expect(posts()).toHaveLength(0);
    await advance(1100);
    expect(posts()).toHaveLength(1);
    expect(posts()[0][1]?.method).toBe('POST');
    const b = body(0);
    expect(Object.keys(b).sort()).toEqual(['levels', 'symbols']);
    expect(b.symbols).toEqual(['AAA', 'BBB', 'CCC']);
    expect(b.levels).toEqual({ AAA: LV_AAA, BBB: LV_BBB });
    expect(b).not.toHaveProperty('stream');
    expect(b).not.toHaveProperty('variant');
  });

  it('NEGATIVE: the stopped card (live_level null) is not in levels and prints no live line', async () => {
    await mount();
    await advance(CARD_LIVE_MS + 100);
    expect(body(0).levels).not.toHaveProperty('CCC');
    await screen.findByTestId('luk-live-AAA');
    expect(screen.queryByTestId('luk-live-CCC')).toBeNull();
    expect(screen.queryByTestId('luk-live-pct-CCC')).toBeNull();
  });

  it('the served vs text, pct text and footer print verbatim (the footer inside the pass line)', async () => {
    const { container } = await mount();
    expect(screen.queryByTestId('luk-live-footer')).toBeNull();
    await advance(CARD_LIVE_MS + 100);
    expect((await screen.findByTestId('luk-live-AAA')).textContent).toBe(VS_AAA);
    expect(screen.getByTestId('luk-live-pct-AAA').textContent).toBe(PCT_AAA);
    const foot = screen.getByTestId('luk-live-footer');
    expect(foot.textContent).toBe('live · 10:33:20 ET');
    expect(container.querySelector('.luk-passline')!.contains(foot)).toBe(true);
    expect(container.querySelector('.luk-passline button')).toBeNull();
  });

  it('NEGATIVE: a served vs without pct_text → the vs line prints, no pct line', async () => {
    await mount();
    await advance(CARD_LIVE_MS + 100);
    expect((await screen.findByTestId('luk-live-BBB')).textContent).toBe(VS_BBB);
    expect(screen.queryByTestId('luk-live-pct-BBB')).toBeNull();
  });

  it('NEGATIVE: closed (refresh_sec 0) → no POST, no footer, no live line', async () => {
    boardFor = () => board({ refresh: 0 });
    await mount();
    await advance(CARD_LIVE_MS * 3);
    expect(posts()).toHaveLength(0);
    expect(screen.queryByTestId('luk-live-footer')).toBeNull();
    expect(screen.queryByTestId('luk-live-AAA')).toBeNull();
  });

  for (const sub of ['playbook', 'track_record', 'premarket']) {
    it(`NEGATIVE: the ${sub} sub draws no cards → no POST, no footer`, async () => {
      boardFor = (_n, u) => board({ sub: u.searchParams.get('sub') || sub });
      await mount(`tab=luk&sub=${sub}`);
      await advance(CARD_LIVE_MS * 3);
      expect(posts()).toHaveLength(0);
      expect(screen.queryByTestId('luk-live-footer')).toBeNull();
    });
  }

  it('NEGATIVE: the overlay never changes data-state, the state label, the card order or the counts line', async () => {
    const { container } = await mount();
    const snap = () => ({
      order: Array.from(container.querySelectorAll('[data-testid^="luk-tile-"][data-state]')).map((e) => e.getAttribute('data-testid')),
      states: Array.from(container.querySelectorAll('[data-testid^="luk-tile-"][data-state]')).map((e) => e.getAttribute('data-state')),
      labels: ['AAA', 'BBB', 'CCC'].map((s) => screen.getByTestId(`luk-state-${s}`).textContent),
      counts: screen.getByTestId('luk-counts').textContent,
    });
    const before = snap();
    expect(before.order).toEqual(['luk-tile-AAA', 'luk-tile-BBB', 'luk-tile-CCC']);
    await advance(CARD_LIVE_MS + 100);
    await screen.findByTestId('luk-live-AAA');
    expect(snap()).toEqual(before);
  });

  it('NEGATIVE: no bus subscription and no EventSource — poll only', async () => {
    await mount();
    await advance(CARD_LIVE_MS * 2 + 100);
    expect(posts().length).toBeGreaterThan(0);
    expect(busSubscribe).not.toHaveBeenCalled();
    expect(busHook).not.toHaveBeenCalled();
    expect(esCtor).not.toHaveBeenCalled();
    const src = await readSource('src/components/LukBoard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const w of ['EventSource', 'eventBus', 'useGgLive', 'useBusEvent', 'stream:', 'variant:']) expect(code).not.toContain(w);
    expect(code.split('useCardLive(').length - 1).toBe(1);
  });
});

describe('LukBoard — 🔴 the re-read at the served next-read time', () => {
  it('re-reads at pass.next_read_sec, then again after each GET (a one-shot re-armed); NEGATIVE: no cadence interval', async () => {
    boardFor = () => board({ next: 45 });
    const si = vi.spyOn(window, 'setInterval');
    await mount();
    expect(gets()).toHaveLength(1);
    await advance(44_000);
    expect(gets()).toHaveLength(1);
    await advance(1_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await advance(45_500);
    await waitFor(() => expect(gets()).toHaveLength(3));
    expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(false);
  });

  it('NEGATIVE: no next_read_sec served → the served cadence interval exactly as before (no GET at 45 s)', async () => {
    const si = vi.spyOn(window, 'setInterval');
    await mount();
    await waitFor(() => expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(true));
    await advance(46_000);
    expect(gets()).toHaveLength(1);
    await advance(300_000 - 46_000 + 500);
    await waitFor(() => expect(gets()).toHaveLength(2));
  });

  it('NEGATIVE: a failed GET still re-arms — the board stays and the next read comes at its served time', async () => {
    boardFor = (n) => (n === 2 ? 503 : board({ next: 40 }));
    await mount();
    await advance(40_500);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await screen.findByTestId('luk-err');
    expect(screen.getByTestId('luk-title')).toBeTruthy();
    await advance(40_500);
    await waitFor(() => expect(gets()).toHaveLength(3));
    await waitFor(() => expect(screen.queryByTestId('luk-err')).toBeNull());
  });

  it('NEGATIVE: a non-positive / non-number next_read_sec → the cadence interval', async () => {
    for (const bad of [0, -5, '45']) {
      fetchMock.mockClear();
      boardFor = () => { const b = board(); b.pass.next_read_sec = bad; return b; };
      const si = vi.spyOn(window, 'setInterval');
      const r = await mount();
      await waitFor(() => expect(si.mock.calls.some((c) => c[1] === 300_000)).toBe(true));
      await advance(46_000);
      expect(gets()).toHaveLength(1);
      si.mockRestore();
      r.unmount();
    }
  });
});
