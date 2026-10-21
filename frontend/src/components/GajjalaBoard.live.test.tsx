import { act, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import { CARD_LIVE_MS } from '../lib/cardLive';

/* 🔴 Gajjala cards live (2026-10-21, BUILD_SPEC20 D1/D2/D7).
 *
 * Ajay, on a StockTwits screenshot of SAIQ: "Are we not real time SAIQ already broke the EMA", "I see it on Stock
 * Twitz" and "If something is Potential add min on min for pricing and other updates to make them more realtime and
 * give us a better edge".
 *
 * The REAL hook (hooks/useCardLive) and the REAL splice (lib/cardLive.patchTiles) under a routed fetch stub:
 * GET /chart-maps/gajjala → the hand fixture's board; POST /chart-maps/live → a served answer shaped like
 * chart_maps/live_card.compose (its `vs.text` a stand-in for live_card.VS_TEXT — the board prints it verbatim and
 * types none of it). NEGATIVES: no POST outside the served window (refresh_sec 0 / absent) or on a sub with no tiles;
 * no `levels` for a tile without a trigger or stop; no live line without served words or on a faulted answer; the
 * 5-minute bars never take the daily bar; the board source types no live-vs word. */

const chartProps: any[] = [];
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
vi.mock('./PatternChart', () => ({
  PatternChart: (props: any) => {
    chartProps.push(props);
    return <div data-testid={`chart-${props.tile.symbol}`} />;
  },
}));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const PFAI_VS = '🔴 3.90 under the stop 3.95 on the live bar — the read moves when the 5-minute bar closes (10:30 ET)';
const nowBlock = (price: number) =>
  ({ price, label: 'now', session: null, add_line: true, as_of_epoch: 1792161435.0, as_of: '2026-10-13 10:27:15 ET' });
const LIVE = (over: Record<string, unknown> = {}) => ({
  session: 'rth', as_of_epoch: 1792161435.0, as_of: '2026-10-13 10:27:15 ET',
  footer: { live: 'live · 10:27:15 ET', stale: 'last refresh 10:27 ET' },
  now_labels: ['now', 'now · pre', 'now · AH'], cap: 250, asked: 4, served: 2, missing: [], fault: null,
  quotes: {
    PFAI: { bar: { t: '2026-10-13', o: 3.1, h: 4.3, l: 3.05, c: 3.9, v: 9e6 }, prev_t: '2026-10-10',
            now: nowBlock(3.9), vs: { kind: 'under_stop', text: PFAI_VS } },
    BKYI: { bar: null, prev_t: null, now: nowBlock(1.28) },
  },
  ...over,
});

let boardFor: (sub: string) => any = (sub) => clone(HAND[sub] || HAND.bull_flag);
let liveAnswer: () => any = () => LIVE();
const fetchMock = vi.fn(async (url: string, _init?: RequestInit) => {
  const u = new URL(String(url), 'http://x');
  if (u.pathname.endsWith('/chart-maps/live')) return { ok: true, status: 200, json: async () => liveAnswer() };
  if (u.pathname.endsWith('/chart-maps/gajjala')) {
    return { ok: true, status: 200, json: async () => boardFor(u.searchParams.get('sub') || 'bull_flag') };
  }
  return { ok: true, status: 200, json: async () => ({}) };
});
const posts = () => fetchMock.mock.calls.filter(([u]) => String(u).endsWith('/chart-maps/live'));
const body = (i: number) => JSON.parse(String(posts()[i][1]?.body));
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

const mount = async (q: string) => {
  const r = render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
};
const lastChart = (sym: string) => [...chartProps].reverse().find((p) => p.tile.symbol === sym);

beforeEach(() => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  chartProps.length = 0;
  fetchMock.mockClear();
  boardFor = (sub) => clone(HAND[sub] || HAND.bull_flag);
  liveAnswer = () => LIVE();
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('GajjalaBoard — 🔴 live cards: the poll', () => {
  it('in the served window: ONE POST after CARD_LIVE_MS with the tile symbols, sorted', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    expect(HAND.bull_flag.session.refresh_sec).toBeGreaterThan(0);
    await advance(CARD_LIVE_MS - 1000);
    expect(posts().length).toBe(0);              // the first board read waits one cadence
    await advance(1100);
    expect(posts().length).toBe(1);
    expect(posts()[0][1]?.method).toBe('POST');
    expect(body(0).symbols).toEqual(['BKYI', 'PFAI', 'SCNI', 'TCRT']);
  });

  it('levels: each tile\'s OWN served trigger / stop, the frame copied (the read\'s, else the tile\'s, else the board\'s)', async () => {
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      delete b.tiles[1].gajjala.frame;           // BKYI: no read frame served …
      b.tiles[1].tf = '15m';                     // … and it drew 15-minute bars → the tile's frame
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    const lv = body(0).levels;
    for (const t of HAND.bull_flag.tiles) {
      expect(lv[t.symbol].trigger).toBe(t.gajjala.trigger);
      expect(lv[t.symbol].stop).toBe(t.gajjala.stop);
    }
    expect(lv.PFAI.tf).toBe(HAND.bull_flag.tf);
    expect(lv.BKYI.tf).toBe('15m');
  });

  it('a 15-minute read on the 5-minute board sends the READ\'s frame (critic 2026-10-21: a ➖ fade reads 15m first)', async () => {
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      b.tiles[0].gajjala.frame = '15m';          // PFAI: the read is on 15-minute bars; the board / tile toggle is 5m
      b.tiles[0].tf = '5m';
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    expect(HAND.bull_flag.tf).toBe('5m');
    await advance(CARD_LIVE_MS + 100);
    expect(body(0).levels.PFAI.tf).toBe('15m');
  });

  it('NEGATIVE: a tile that DREW 15-minute bars but whose read is on 5m sends 5m (the drawn frame never wins)', async () => {
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      b.tiles[1].tf = '15m';                     // BKYI drew 15m; its served read frame stays '5m'
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    expect(HAND.bull_flag.tiles[1].gajjala.frame).toBe('5m');
    expect(body(0).levels.BKYI.tf).toBe('5m');
  });

  it('NEGATIVE: a tile with neither a trigger nor a stop sends no levels (its symbol still polls)', async () => {
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      b.tiles[2].gajjala.trigger = null;         // TCRT
      b.tiles[2].gajjala.stop = null;
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    expect(body(0).symbols).toContain('TCRT');
    expect(Object.keys(body(0).levels).sort()).toEqual(['BKYI', 'PFAI', 'SCNI']);
  });

  it('NEGATIVE: a sub whose tiles carry no plan (☀️ premarket) → the body is {symbols} only', async () => {
    await mount('tab=gajjala&sub=premarket');
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    expect(body(0)).toEqual({ symbols: ['LIFW', 'YJ'] });
  });

  it('NEGATIVE: refresh_sec 0 (closed) → zero POSTs over three cadences, no footer', async () => {
    boardFor = () => ({ ...clone(HAND.bull_flag), session: { ...HAND.bull_flag.session, refresh_sec: 0 } });
    await mount('tab=gajjala&sub=bull_flag');
    await advance(3 * CARD_LIVE_MS + 500);
    expect(posts().length).toBe(0);
    expect(screen.queryByTestId('gg-live-footer')).toBeNull();
  });

  it('NEGATIVE: no served refresh_sec at all → zero POSTs', async () => {
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      delete b.session.refresh_sec;
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    await advance(3 * CARD_LIVE_MS + 500);
    expect(posts().length).toBe(0);
  });

  it('NEGATIVE: 📓 Playbook (no tiles) → zero POSTs', async () => {
    await mount('tab=gajjala&sub=playbook');
    await advance(3 * CARD_LIVE_MS + 500);
    expect(posts().length).toBe(0);
  });

  it('NEGATIVE: levels never ride a URL', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    for (const [u] of fetchMock.mock.calls) expect(String(u)).not.toMatch(/levels|trigger=|stop=/);
  });
});

describe('GajjalaBoard — 🔴 live cards: what reaches the card', () => {
  it('the served now line reaches PatternChart; BUY / STOP kept; the 5-minute bars never take the daily bar', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    await waitFor(() => expect(lastChart('PFAI').tile.lines.some((l: any) => l.tone === 'now')).toBe(true));
    const tile = lastChart('PFAI').tile;
    const served = HAND.bull_flag.tiles[0];
    expect(tile.lines).toEqual([...served.lines, { price: 3.9, label: 'now', tone: 'now' }]);
    expect(tile.bars).toEqual(served.bars);      // NEGATIVE: no daily candle spliced into 5-minute bars
    expect(tile.bars.some((b: any) => b.t === '2026-10-13')).toBe(false);
  });

  it('the served live words print verbatim under the plan line, as one wrapping line', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    const line = await screen.findByTestId('gg-live-PFAI');
    expect(line.textContent).toBe(PFAI_VS);
    expect(line.className).toContain('gg-line');  // the 📱 overflow-wrap: anywhere rule (styles/gajjala.css)
    const extras = line.closest('[data-testid="gg-extras"]')!;
    const plan = extras.querySelector('[data-testid="gg-plan"]')!;
    expect(plan.compareDocumentPosition(line) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: a quote without served words prints no live line (BKYI), nor does a tile with no quote', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    await screen.findByTestId('gg-live-PFAI');
    for (const s of ['BKYI', 'TCRT', 'SCNI']) expect(screen.queryByTestId(`gg-live-${s}`)).toBeNull();
    expect(document.body.textContent).not.toMatch(/undefined|NaN|\[object Object\]/);
  });

  it('NEGATIVE: before the first tick nothing live prints', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    expect(screen.queryByTestId('gg-live-PFAI')).toBeNull();
    expect(screen.queryByTestId('gg-live-footer')).toBeNull();
  });

  it('the served footer word prints after the "as of" stamp', async () => {
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    const f = await screen.findByTestId('gg-live-footer');
    expect(f.textContent).toBe('live · 10:27:15 ET');
    const asOf = screen.getByTestId('gg-as-of');
    expect(asOf.compareDocumentPosition(f) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it('NEGATIVE: the served window closes (refresh_sec → 0) → the "live" footer goes, and no POST follows', async () => {
    let closed = false;
    boardFor = () => {
      const b = clone(HAND.bull_flag);
      if (closed) b.session = { ...b.session, refresh_sec: 0 };
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    expect((await screen.findByTestId('gg-live-footer')).textContent).toBe('live · 10:27:15 ET');
    closed = true;
    await advance(HAND.bull_flag.session.refresh_sec * 1000 + 500);   // one board cadence → the board refetch serves 0
    await waitFor(() => expect(screen.queryByTestId('gg-live-footer')).toBeNull());
    const n = posts().length;
    await advance(10 * CARD_LIVE_MS);
    expect(posts().length).toBe(n);
    expect(screen.queryByTestId('gg-live-footer')).toBeNull();
  });

  it('NEGATIVE: a faulted answer prints no live line and no live footer', async () => {
    liveAnswer = () => LIVE({ fault: 'snapshot unavailable', footer: { live: null, stale: null } });
    await mount('tab=gajjala&sub=bull_flag');
    await advance(CARD_LIVE_MS + 100);
    expect(posts().length).toBe(1);
    expect(screen.queryByTestId('gg-live-PFAI')).toBeNull();
    expect(screen.queryByTestId('gg-live-footer')).toBeNull();
  });

  it('NEGATIVE: the board source types no live-vs word — every one is served (live_card.VS_TEXT)', async () => {
    const src = (await readSource('src/components/GajjalaBoard.tsx'))
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
    expect(src).not.toMatch(/over the trigger|under the stop|between the stop|on the live bar|bar closes/i);
    expect(src).toMatch(/useCardLive\(liveSyms, inWindow && liveSyms\.length > 0/);
  });
});
