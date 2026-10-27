import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import type { CurrentUser } from '../hooks/useUser';
import { GG_TFS, parseGgTf } from '../lib/gajjala';
import { GG_VARIANT_BASE, ggBase, ggVariantKey } from './ggVariant';
import { GG_TAPE_PATH, _resetGgLiteCache, fetchGgLiteTape, ggTapePath } from './GgEntryTape';

/* 🚩 Gajjala's 1-minute page on the real board and the real Chart Maps page (2026-10-27, BUILD_SPEC27 §3.8 / §4 WP-D).
 *
 * Ajay 2026-10-27: "Can you create a new page, I would like you to do the same logic of Gajjalas but on 1 min candles
 * please." and "do everything and also add the track record for it from today..".
 *
 * ONE component draws both pages; the variant picks the endpoint base only (components/ggVariant.ts). Pinned here:
 * the 1-minute board GETs /chart-maps/gajjala-1m, POSTs /chart-maps/gajjala-1m/scan and reads its 🕰️ tapes from
 * /chart-maps/gajjala-1m/entry-tape; its bar-size toggle runs over the SERVED variant.tfs; the served title / honesty
 * print verbatim above the strip. On the real page, ?tab=gajjala_1m mounts it and a switch from 🚩 Gajjala's REMOUNTS
 * it (key="gajjala_1m" — a second on-open POST, to the 1-minute path). NEGATIVES: 🚩 Gajjala's still GETs / POSTs /
 * reads its tapes on the 5-minute paths and never names a 1-minute one; no 15m button on the 1-minute board, no 1m
 * button on the 5-minute one; '1m' never rides 🚩 Gajjala's GET; an absent / empty variant block prints nothing.
 *
 * Boards: SYNTHETIC in-file clones of the 2026-10-13 hand fixture, shaped as BUILD_SPEC27 §3.7 serves the 1-minute
 * board (tab "gajjala_1m", tf "1m", the `variant` block with WORDS_1M filled). The REAL payload test reads WP-C's
 * golden (gajjala_1m_board_2026_10_27.json, written by backend tests/test_gajjala_1m_page_2026_10_27.py under
 * GG_WRITE_GOLDEN=1) and FAILS — never skips — while that file is missing. */

let userRet: CurrentUser | null = null;
const tracked: string[] = [];
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => { tracked.push(k); } }));
vi.mock('./PatternChart', () => ({ PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: ({ symbol }: any) => <span data-testid={`growth-${symbol}`} /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: ({ symbol }: any) => <span data-testid={`short-${symbol}`} /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span data-testid="explosive" /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span data-testid="enterable" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: ({ section }: any) => <span data-testid="rules-info">{section}</span> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import GajjalaBoard from './GajjalaBoard';
import ChartMaps from '../pages/ChartMaps';
import { GG1M_PASSES, PASSES, TAPE_PASSES, cadenceOf, sessionLine, staleAfterSec } from '../pages/Alerts';
import { CATEGORIES, PRESETS } from '../pages/Notifications';
import { ALERT_KINDS, kindLabel } from '../lib/alertKinds';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const HAND: Record<string, any> = (hand as any).boards;
const TR5D: any = (trGolden as any).boards['5d'];

const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};

/* The served variant block as BUILD_SPEC27 §3.1 WORDS_1M fills it ({p}=1, {s}=5, {from}=2026-10-27) — test data. */
const VARIANT_1M = {
  key: 'gajjala_1m', tab: 'gajjala_1m', label: "Gajjala's 1-min",
  title: "\u{1F6A9} Gajjala's — the same rules on 1-minute candles · Cheetah variant · UNMEASURED",
  honesty: 'GG trades these setups on 5-minute bars; this page runs the same bar-count rules on 1-minute bars by your call (2026-10-27). Every alert here is recorded in shadow, never sent, until you say so. Nothing measured.',
  tfs: ['1m', '5m'], primary: '1m', slow: '5m', api_base: '/chart-maps/gajjala-1m', record_from: '2026-10-27',
};
const SCAN = { state: 'idle', on_demand: false, as_of_text: 'served as-of line', rescan_label: 'served rescan', rescan_title: 'served title' };

/** 🚩 Gajjala's board (no variant block) — the hand fixture, no timers. */
function gg5Board(sub = 'bull_flag'): any {
  const b = clone(HAND[sub] || HAND.bull_flag);
  b.session = { ...b.session, refresh_sec: 0 };
  b.scan = { ...SCAN };
  return b;
}
/** The 1-minute board (BUILD_SPEC27 §3.7): tab gajjala_1m, tf 1m, the variant block; tiles drawn on 1m, the last on 5m
 *  (the ➖ Fade's slow frame — the served per-tile tf). */
function gg1Board(sub = 'bull_flag'): any {
  const b = gg5Board(sub);
  b.tab = 'gajjala_1m';
  b.tf = '1m';
  b.variant = clone(VARIANT_1M);
  b.tiles = (b.tiles || []).map((t: any, i: number, all: any[]) => ({ ...t, tf: i === all.length - 1 ? '5m' : '1m' }));
  return b;
}
/** A 🏁 board with the 🕰️ view (rows with ids), from the 2026-10-16 golden; `one` = the 1-minute page's copy. */
function trBoard(one: boolean): any {
  const b = clone(TR5D);
  b.session = { ...b.session, refresh_sec: 0 };
  if (one) { b.tab = 'gajjala_1m'; b.tf = '1m'; b.variant = clone(VARIANT_1M); }
  return b;
}

type Call = { method: string; path: string; url: string; q: URLSearchParams };
let calls: Call[] = [];
const RULES = { sections: { gajjala: { title: 'R', emoji: '\u{1F6A9}', picks: [], stops: [], alerts: [], note: 'N' } } };
const TAPE = { id: 'x', ticker: 'X', tf: '1m', lite: true, bars: [], n_bars: 0, rules: [], title: 't', tone: null, note: null,
               aria: 'a', as_of: 'now' };
function stub(boards: { gg5?: (q: URLSearchParams) => any; gg1?: (q: URLSearchParams) => any } = {}) {
  calls = [];
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, url: String(url), q: u.searchParams });
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok(TAPE);
    if (u.pathname.endsWith('/chart-maps/gajjala-1m')) return ok((boards.gg1 || (() => gg1Board()))(u.searchParams));
    if (u.pathname.endsWith('/chart-maps/gajjala')) return ok((boards.gg5 || (() => gg5Board()))(u.searchParams));
    if (u.pathname.endsWith('/supply-demand/rules')) return ok(RULES);
    return ok({});
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const ends = (p: string) => calls.filter((c) => c.path.endsWith(p));
const getsTo = (p: string) => ends(p).filter((c) => c.method === 'GET');
const postsTo = (p: string) => ends(p).filter((c) => c.method === 'POST');
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));

const mount = (q: string, variant?: 'gajjala' | 'gajjala_1m') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
  </MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));

const P1 = '/chart-maps/gajjala-1m';
const P5 = '/chart-maps/gajjala';

beforeEach(() => { userRet = OWNER; tracked.length = 0; _resetGgLiteCache(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

describe('ggVariant — the endpoint base per page (2026-10-27)', () => {
  it('GG_VARIANT_BASE == backend variant.py api_base for both pages', () => {
    expect(GG_VARIANT_BASE).toEqual({ gajjala: '/chart-maps/gajjala', gajjala_1m: '/chart-maps/gajjala-1m' });
    expect(ggBase('gajjala_1m')).toBe(P1);
    expect(ggBase('gajjala')).toBe(P5);
  });

  it('NEGATIVE: an unknown / missing key is 🚩 Gajjala’s (fail to GG5, as variant.of does)', () => {
    for (const k of [undefined, null, '', 'gajjala_5m', 'GAJJALA_1M', 'toString', 42]) {
      expect(ggVariantKey(k)).toBe('gajjala');
      expect(ggBase(k)).toBe(P5);
    }
  });

  it("the 🕰️ tape route: 🚩 Gajjala's keeps GG_TAPE_PATH; the 1-minute page its own", () => {
    expect(ggTapePath('gajjala')).toBe(GG_TAPE_PATH);
    expect(ggTapePath('gajjala_1m')).toBe('/chart-maps/gajjala-1m/entry-tape');
  });

  it('NEGATIVE: the lite tape cache is keyed by route AND id — a 5-minute entry never answers the 1-minute page', async () => {
    stub();
    await fetchGgLiteTape('2026-10-27|AAA|bull_flag|aplus');
    await fetchGgLiteTape('2026-10-27|AAA|bull_flag|aplus', ggTapePath('gajjala_1m'));
    await fetchGgLiteTape('2026-10-27|AAA|bull_flag|aplus', ggTapePath('gajjala_1m'));
    expect(ends('/chart-maps/gajjala/entry-tape')).toHaveLength(1);
    expect(ends('/chart-maps/gajjala-1m/entry-tape')).toHaveLength(1);
  });
});

describe('GajjalaBoard variant="gajjala_1m" — its own endpoint (2026-10-27)', () => {
  it('GETs /chart-maps/gajjala-1m? and POSTs /chart-maps/gajjala-1m/scan ONCE (owner)', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    await sleep(30);
    expect(getsTo(P1).length).toBeGreaterThan(0);
    expect(getsTo(P1)[0].url).toContain('/chart-maps/gajjala-1m?');
    expect(getsTo(P1)[0].q.get('sub')).toBe('bull_flag');
    expect(postsTo(`${P1}/scan`)).toHaveLength(1);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_1m');
  });

  it('NEGATIVE: the 1-minute board never GETs or POSTs a 5-minute path', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    await sleep(30);
    expect(getsTo(P5)).toHaveLength(0);
    expect(postsTo(`${P5}/scan`)).toHaveLength(0);
    expect(calls.some((c) => /\/chart-maps\/gajjala(\/|\?|$)/.test(c.url.replace(/^https?:\/\/[^/]+/, '')))).toBe(false);
  });

  it("NEGATIVE: the default board (no prop) is 🚩 Gajjala's — /chart-maps/gajjala? + its scan path, never a 1-minute one", async () => {
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    await sleep(30);
    expect(getsTo(P5)[0].url).toContain('/chart-maps/gajjala?');
    expect(postsTo(`${P5}/scan`)).toHaveLength(1);
    expect(ends(P1)).toHaveLength(0);
    expect(postsTo(`${P1}/scan`)).toHaveLength(0);
    expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala');
  });

  it('the usage key names the page: chart-maps:tab:gajjala_1m:<sub> (NEGATIVE: 🚩 keeps chart-maps:tab:gajjala:<sub>)', async () => {
    stub();
    const a = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(a.container);
    expect(tracked).toContain('chart-maps:tab:gajjala_1m:bull_flag');
    expect(tracked).not.toContain('chart-maps:tab:gajjala:bull_flag');
    cleanup();
    tracked.length = 0;
    const b = mount('tab=gajjala&sub=bull_flag');
    await loaded(b.container);
    expect(tracked).toContain('chart-maps:tab:gajjala:bull_flag');
    expect(tracked.some((k) => k.includes('gajjala_1m'))).toBe(false);
  });
});

describe('the bar-size toggle runs over the SERVED variant.tfs (2026-10-27)', () => {
  it('1-minute board: 1m + 5m buttons, 1m on', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(screen.getByTestId('gg-tf-1m')).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByTestId('gg-tf-5m')).toHaveAttribute('aria-selected', 'false');
    expect(screen.getByTestId('gg-tf-1m').textContent).toBe('1m');
  });

  it('NEGATIVE: no 15m button on the 1-minute board', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(screen.queryByTestId('gg-tf-15m')).toBeNull();
  });

  it("NEGATIVE: 🚩 Gajjala's still shows 5m + 15m and no 1m button", async () => {
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(screen.getByTestId('gg-tf-5m')).toBeTruthy();
    expect(screen.getByTestId('gg-tf-15m')).toBeTruthy();
    expect(screen.queryByTestId('gg-tf-1m')).toBeNull();
  });

  it('a 5m click on the 1-minute board re-reads the 1-minute endpoint with tf=5m', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    fireEvent.click(screen.getByTestId('gg-tf-5m'));
    await waitFor(() => expect(getsTo(P1).some((c) => c.q.get('tf') === '5m')).toBe(true));
    expect(getsTo(P5)).toHaveLength(0);
  });

  it("NEGATIVE: ?tf=1m never rides 🚩 Gajjala's GET", async () => {
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag&tf=1m');
    await loaded(container);
    await sleep(30);
    expect(getsTo(P5).length).toBeGreaterThan(0);
    for (const c of getsTo(P5)) expect(c.q.has('tf')).toBe(false);
    expect(parseGgTf('1m')).toBeNull();
    expect(GG_TFS).toEqual(['5m', '15m']);
  });

  it('the 1-minute board reads ?tf=1m once its served frames are in hand', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag&tf=1m', 'gajjala_1m');
    await loaded(container);
    await waitFor(() => expect(getsTo(P1).some((c) => c.q.get('tf') === '1m')).toBe(true));
  });

  // 2026-10-27 (critic finding 5): the deep link rides the FIRST GET — no 5m GET, no second fetch, no 5m flash.
  it('the 1-minute board sends ?tf=1m on its FIRST GET; NEGATIVE: no GET without it, no second GET', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag&tf=1m', 'gajjala_1m');
    await loaded(container);
    await sleep(30);
    const gets = getsTo(P1);
    expect(gets.length).toBe(1);
    expect(gets[0].q.get('tf')).toBe('1m');
  });

  it("a 1-minute board's 5m tile carries the served-frame badge; NEGATIVE: a 1m tile on 🚩 Gajjala's carries none", async () => {
    stub();
    const one = gg1Board();
    const last = one.tiles[one.tiles.length - 1].symbol;
    const first = one.tiles[0].symbol;
    stub({ gg1: () => one });
    const a = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(a.container);
    expect(screen.getByTestId(`gg-frame-${last}`).textContent).toBe('5-min read');
    expect(screen.queryByTestId(`gg-frame-${first}`)).toBeNull();
    cleanup();
    const five = gg5Board();
    five.tiles = five.tiles.map((t: any) => ({ ...t, tf: '1m' }));
    stub({ gg5: () => five });
    const b = mount('tab=gajjala&sub=bull_flag');
    await loaded(b.container);
    for (const t of five.tiles) expect(screen.queryByTestId(`gg-frame-${t.symbol}`)).toBeNull();
  });
});

describe('the served title / honesty above the strip (2026-10-27)', () => {
  it('prints variant.title and variant.honesty verbatim, before the strip', async () => {
    stub();
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(screen.getByTestId('gg-page-title').textContent).toBe(VARIANT_1M.title);
    expect(screen.getByTestId('gg-page-honesty').textContent).toBe(VARIANT_1M.honesty);
    const order = Array.from(container.querySelectorAll('[data-testid="gg-page-title"], [data-testid="gg-page-honesty"], [data-testid="gg-strip"]'))
      .map((e) => e.getAttribute('data-testid'));
    expect(order).toEqual(['gg-page-title', 'gg-page-honesty', 'gg-strip']);
  });

  it("NEGATIVE: 🚩 Gajjala's (no variant block) prints neither", async () => {
    stub();
    const { container } = mount('tab=gajjala&sub=bull_flag');
    await loaded(container);
    expect(screen.queryByTestId('gg-page-title')).toBeNull();
    expect(screen.queryByTestId('gg-page-honesty')).toBeNull();
  });

  it('NEGATIVE: a variant block with a null title and a blank honesty prints nothing — the FE types no fallback', async () => {
    const b = gg1Board();
    b.variant.title = null;
    b.variant.honesty = '   ';
    stub({ gg1: () => b });
    const { container } = mount('tab=gajjala_1m&sub=bull_flag', 'gajjala_1m');
    await loaded(container);
    expect(screen.queryByTestId('gg-page-title')).toBeNull();
    expect(screen.queryByTestId('gg-page-honesty')).toBeNull();
    // the toggle still follows the served frames
    expect(screen.getByTestId('gg-tf-1m')).toBeTruthy();
  });
});

describe('the 🕰️ entry tape reads the page it sits in (2026-10-27)', () => {
  const firstTlKey = (b: any): string => {
    const kinds: string[] = b.track_record.views.kinds;
    for (const d of b.track_record.days) for (const r of d.rows) if (kinds.includes(r.kind) && r.id) return r.key;
    throw new Error('no timeline row with an id in the golden');
  };

  it('inside the 1-minute board every tape fetch goes to /chart-maps/gajjala-1m/entry-tape (lite and full)', async () => {
    const b = trBoard(true);
    stub({ gg1: () => b });
    const { container } = mount('tab=gajjala_1m&sub=track_record&view=timeline', 'gajjala_1m');
    await loaded(container);
    await waitFor(() => expect(ends(`${P1}/entry-tape`).some((c) => c.q.get('lite') === '1')).toBe(true));
    fireEvent.click(screen.getByTestId(`gg-tl-open-${firstTlKey(b)}`));
    await waitFor(() => expect(ends(`${P1}/entry-tape`).some((c) => !c.q.has('lite'))).toBe(true));
    // NEGATIVE: never the 5-minute tape route
    expect(ends('/chart-maps/gajjala/entry-tape')).toHaveLength(0);
  });

  it("NEGATIVE: 🚩 Gajjala's board keeps GG_TAPE_PATH and never names the 1-minute route", async () => {
    const b = trBoard(false);
    stub({ gg5: () => b });
    const { container } = mount('tab=gajjala&sub=track_record&view=timeline');
    await loaded(container);
    await waitFor(() => expect(ends(GG_TAPE_PATH).some((c) => c.q.get('lite') === '1')).toBe(true));
    fireEvent.click(screen.getByTestId(`gg-tl-open-${firstTlKey(b)}`));
    await waitFor(() => expect(ends(GG_TAPE_PATH).some((c) => !c.q.has('lite'))).toBe(true));
    expect(ends(`${P1}/entry-tape`)).toHaveLength(0);
  });
});

describe('ChartMaps mounts the 1-minute board (2026-10-27)', () => {
  const page = (q: string) => render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><ChartMaps /></MemoryRouter>);

  it('?tab=gajjala_1m mounts GajjalaBoard variant="gajjala_1m" — it fetches /chart-maps/gajjala-1m?', async () => {
    stub();
    const { container } = page('tab=gajjala_1m');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_1m'));
    await waitFor(() => expect(getsTo(P1).length).toBeGreaterThan(0));
    expect(getsTo(P1)[0].url).toContain('/chart-maps/gajjala-1m?');
    expect(getsTo(P5)).toHaveLength(0);
    expect(screen.getByRole('tab', { name: "Gajjala's 1-min" })).toHaveAttribute('aria-selected', 'true');
  });

  it("NEGATIVE: ?tab=gajjala still fetches /chart-maps/gajjala? and never the 1-minute endpoint", async () => {
    stub();
    const { container } = page('tab=gajjala');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala'));
    await waitFor(() => expect(getsTo(P5).length).toBeGreaterThan(0));
    expect(getsTo(P5)[0].url).toContain('/chart-maps/gajjala?');
    expect(ends(P1)).toHaveLength(0);
  });

  it('switching gajjala → gajjala_1m REMOUNTS: a second on-open POST, to the 1-minute path (key="gajjala_1m")', async () => {
    stub();
    const { container } = page('tab=gajjala&sub=bull_flag');
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
    await waitFor(() => expect(postsTo(`${P5}/scan`)).toHaveLength(1));
    fireEvent.click(screen.getByRole('tab', { name: "Gajjala's 1-min" }));
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala_1m'));
    await waitFor(() => expect(postsTo(`${P1}/scan`)).toHaveLength(1));
    await waitFor(() => expect(getsTo(P1).length).toBeGreaterThan(0));
    await sleep(30);
    // NEGATIVE: the 1-minute board POSTs nothing to the 5-minute path; the 5-minute board's one POST stays one
    expect(postsTo(`${P5}/scan`)).toHaveLength(1);
    // the 5-minute `sub` did not cross the border (tabSearch over GAJJALA_TABS)
    expect(getsTo(P1)[0].q.has('sub')).toBe(false);
    // the board on screen is the fresh 1-minute one, its served title printed
    expect(within(container.querySelector('.gg-board') as HTMLElement).getByTestId('gg-page-title').textContent).toBe(VARIANT_1M.title);
  });

  it('NEGATIVE: switching back gajjala_1m → gajjala remounts the 5-minute board (its own POST, its own path)', async () => {
    stub();
    const { container } = page('tab=gajjala_1m');
    await waitFor(() => expect(postsTo(`${P1}/scan`)).toHaveLength(1));
    fireEvent.click(screen.getByRole('tab', { name: "Gajjala's" }));
    await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-variant')).toBe('gajjala'));
    await waitFor(() => expect(postsTo(`${P5}/scan`)).toHaveLength(1));
    await sleep(30);
    expect(postsTo(`${P1}/scan`)).toHaveLength(1);
    expect(screen.queryByTestId('gg-page-title')).toBeNull();
  });
});

describe('the two 1-minute kinds on /alerts, /notifications and the kind registry (2026-10-27, SHADOW)', () => {
  const KINDS = ['gajjala_1m_setup', 'gajjala_1m_potential'] as const;

  it('alertKinds labels both — the shadow word in the label, the 🚩 / 🧠 emoji, the trading group', () => {
    expect(ALERT_KINDS.gajjala_1m_setup).toEqual({ emoji: '\u{1F6A9}', label: 'Gajjala 1-min A+ (shadow)', group: 'trading' });
    expect(ALERT_KINDS.gajjala_1m_potential).toEqual({ emoji: '\u{1F9E0}', label: 'Gajjala 1-min potential (shadow)', group: 'trading' });
    expect(kindLabel('gajjala_1m_setup')).toBe('\u{1F6A9} Gajjala 1-min A+ (shadow)');
    // NEGATIVE: 🚩 Gajjala's own kinds keep their labels
    expect(ALERT_KINDS.gajjala_setup.label).toBe('Gajjala A+ setup');
    expect(ALERT_KINDS.gajjala_potential.label).toBe('Gajjala potential');
  });

  it('Notifications: one row each, the BUILD_SPEC27 labels, SHADOW + UNMEASURED in the detail', () => {
    const want: Record<string, string> = { gajjala_1m_setup: 'Gajjala 1-min A+ (shadow)', gajjala_1m_potential: 'Gajjala 1-min potential (shadow)' };
    for (const k of KINDS) {
      const rows = CATEGORIES.filter((c) => c.key === k);
      expect(rows, k).toHaveLength(1);
      expect(rows[0].label).toBe(want[k]);
      expect(rows[0].group).toBe('trading');
      expect(rows[0].detail).toMatch(/^SHADOW/);
      expect(rows[0].detail).toContain('UNMEASURED');
      expect(rows[0].detail).toContain('never sent');
    }
  });

  it('NEGATIVE: the details never promise a ring, never say OFF BY DEFAULT or the b-word, and Essentials does not switch them on', () => {
    for (const k of KINDS) {
      const d = CATEGORIES.find((c) => c.key === k)!.detail;
      expect(d).not.toMatch(/ON FOR YOUR PHONE|rings your phone|LIVE SINCE|OFF BY DEFAULT/);
      expect(d).not.toMatch(new RegExp('b' + 'ounce', 'i'));
      const ess = PRESETS.find((p) => p.id === 'essentials')!;
      expect((ess.pref as Record<string, unknown>)[k]).not.toBe(true);
    }
  });

  // 2026-10-27 (critic finding 1/2): the two rows moved from PASSES into their own GG1M_PASSES strip.
  it('Alerts: both PASS rows on the minute fallback (60) — stale after staleAfterSec(60) = 300 s (== GG1M_STALE_AFTER_SEC)', () => {
    for (const k of KINDS) {
      const meta = GG1M_PASSES.find((m) => m.key === k);
      expect(meta, k).toBeTruthy();
      expect(meta!.fallbackCadenceSec).toBe(60);
      expect(meta!.label).toContain('shadow');
      expect(cadenceOf(undefined, meta!)).toBe(60);
    }
    expect(staleAfterSec(60)).toBe(300);
    // the rows sit in kind order
    expect(GG1M_PASSES.map((m) => m.key)).toEqual([...KINDS]);
  });

  it('NEGATIVE: the 1-minute rows are NOT in PASSES — the header still counts the 7 intraday passes', () => {
    for (const k of KINDS) expect(PASSES.some((m) => m.key === k)).toBe(false);
    expect(PASSES).toHaveLength(7);
    expect(PASSES[PASSES.length - 1].key).toBe('gajjala_potential');
  });

  it('NEGATIVE: two stale 1-minute rows (the page switched off) never turn the header to a warning', () => {
    const now = '2026-10-27T11:00:00-04:00';
    const passes: Record<string, any> = {};
    for (const m of PASSES) passes[m.key] = { date: '2026-10-27', as_of: now, counts: {} };
    for (const k of KINDS) passes[k] = { date: '2026-10-27', as_of: '2026-10-27T09:00:00-04:00', counts: {} };
    const status = { in_session: true, now_et: now, gate: { min_room_pct: 5, max_above_demand_pct: 1 }, passes };
    expect(sessionLine(status as any, '2026-10-27')).toBe('Session open — all 7 passes reported within cadence.');
  });

  it("NEGATIVE: they are not tape passes, and 🚩 Gajjala's own rows keep their 5-minute fallback", () => {
    for (const k of KINDS) expect(TAPE_PASSES.some((m) => m.key === k)).toBe(false);
    expect(PASSES.find((m) => m.key === 'gajjala_setup')!.fallbackCadenceSec).toBe(300);
    expect(PASSES.find((m) => m.key === 'gajjala_potential')!.fallbackCadenceSec).toBe(300);
  });
});

/* ── the REAL payload (WP-C's golden) through the real component — FAILS while the file is missing, never skips ── */
async function readJson(rel: string): Promise<any | null> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  const p = `${root}/${rel}`;
  return fs.existsSync(p) ? JSON.parse(fs.readFileSync(p, 'utf8')) : null;
}
const REAL_REL = 'src/components/__fixtures__/gajjala_1m_board_2026_10_27.json';
const REAL: any = await readJson(REAL_REL);
const realBoards = (): Record<string, any> => {
  const bs = REAL?.boards && typeof REAL.boards === 'object' ? REAL.boards : {};
  return Object.fromEntries(Object.entries(bs).filter(([, b]) => b && typeof b === 'object')) as Record<string, any>;
};
const SWEEP_BANNED = ['5-minute pass', '5-minute bar', 'every 5 minutes', 'tab=gajjala&'];

describe('the REAL 1-minute payload (WP-C golden gajjala_1m_board_2026_10_27.json) through the real board', () => {
  it('the golden exists (pending WP-C until written) and every real board renders on the 1-minute endpoint: served title / honesty verbatim, the served frames on the toggle', async () => {
    expect(REAL, `${REAL_REL} is missing — WP-C writes it (GG_WRITE_GOLDEN=1)`).not.toBeNull();
    const boards = realBoards();
    for (const k of ['potential', 'bull_flag', 'track_record']) expect(Object.keys(boards), `board ${k}`).toContain(k);
    for (const [name, board] of Object.entries(boards)) {
      expect(board.tab, name).toBe('gajjala_1m');
      expect(board.variant?.tfs, name).toEqual(['1m', '5m']);
      stub({ gg1: () => board });
      const { container } = mount(`tab=gajjala_1m&sub=${encodeURIComponent(board.sub)}`, 'gajjala_1m');
      await loaded(container);
      expect(getsTo(P1).length, name).toBeGreaterThan(0);
      expect(getsTo(P5), name).toHaveLength(0);
      if (typeof board.variant.title === 'string' && board.variant.title.trim()) {
        expect(screen.getByTestId('gg-page-title').textContent, name).toBe(board.variant.title);
      }
      if (typeof board.variant.honesty === 'string' && board.variant.honesty.trim()) {
        expect(screen.getByTestId('gg-page-honesty').textContent, name).toBe(board.variant.honesty);
      }
      if (board.sub !== 'track_record' && board.sub !== 'playbook') {
        expect(screen.getByTestId('gg-tf-1m'), name).toBeTruthy();
        expect(screen.getByTestId('gg-tf-5m'), name).toBeTruthy();
        // NEGATIVE: no 15m button from a real 1-minute payload
        expect(screen.queryByTestId('gg-tf-15m'), name).toBeNull();
      } else if (board.sub === 'track_record' && board.track_record?.title) {
        expect(screen.getByTestId('gg-tr-title').textContent, name).toBe(board.track_record.title);
      }
      // NEGATIVE: the served-words sweep — no 5-minute cadence word, no 5-minute deep link on the 1-minute page
      // 2026-10-27 (WP-E): BUILD_SPEC27 §4 WP-C exempts exactly the served HONESTY's "GG trades these setups on
      // 5-minute bars" — that sentence is cut out (every copy of it) before the sweep; nothing else is exempt.
      const hon = typeof board.variant?.honesty === 'string' ? board.variant.honesty : '';
      const text = hon ? (container.textContent || '').split(hon).join(' ') : (container.textContent || '');
      for (const bad of SWEEP_BANNED) expect(text.includes(bad), `${name}: "${bad}"`).toBe(false);
      for (const a of Array.from(container.querySelectorAll('a[href]'))) {
        expect(a.getAttribute('href') || '', name).not.toMatch(/[?&]tab=gajjala(&|$)/);
      }
      cleanup();
    }
  });
});
