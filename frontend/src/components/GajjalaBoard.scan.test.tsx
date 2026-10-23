import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import type { CurrentUser } from '../hooks/useUser';

/* 🔄 Scan on open + 🎯 A+ line on Gajjala's board (2026-10-15, BUILD_SPEC5 §3.8 / §4 WP-C).
 *
 * Ajay: "When ever I open Gajjala's intiate a new scan of stocks.  In that moment and if there are any enterable
 * stocks on the top which I see in potential i guess".
 *
 * Boards come from the GOLDEN fixtures the backend writes (tests/test_gajjala_on_open.py and
 * tests/test_gajjala_potential_tab.py — the served payload, never typed). What is pinned: ONE POST per mount and only
 * for the owner (StrictMode included; a sub click never re-POSTs; a remount does); the poll is the SERVER's plan,
 * bounded, and gives up at its wait-max; the board it had stays on screen while a pass runs; the 🎯 line prints the
 * served rows and the served words only, on every sub, ahead of the 📈 Track. NEGATIVES: a non-owner or no user never
 * POSTs and sees no 🔄 button or scanning line; reused / closed / refused / 404 / network error never poll; a closed
 * session keeps the button, enabled, its title the served closed line (2026-10-23 — it hid before); a board from an older API (the hand fixture) renders as before. Small served poll numbers
 * keep the real timers fast. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => undefined }));
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

const OPEN: Record<string, any> = (onOpen as any).boards;
const POT: Record<string, any> = (potGolden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const GUEST: CurrentUser = { ...OWNER, email: 'guest@example.com', is_admin: false };

/* OLD = the 10:31 cron read the board had; NEW = the 10:41 on-open pass landing (its served pass.at differs). */
const OLD = () => clone(POT.bull_flag);
const NEW = () => clone(OPEN.bull_flag);
const OLD_AT: string = POT.bull_flag.pass.at;
/* Test data shaped like the served W4 / W10 / W12 / W14 lines — the board prints whatever it is given. */
const W4 = 'scanning… a pass started on open at 10:41:20 ET — the board below is the 10:31 ET read until it lands';
const scanningBoard = () => {
  const b = OLD();
  b.scan = { ...b.scan, state: 'scanning', scanning_text: W4, text: W4 };
  return b;
};
const post = (state: string, extra: Record<string, unknown> = {}) => ({
  state, latest_at: OLD_AT, eta_sec: null, poll_sec: null, wait_max_sec: null, text: `served ${state} line`, ...extra,
});

type Call = { method: string; path: string; url: string };
let calls: Call[] = [];
function stub(postAnswer: any, getBoard: (n: number, u: URL) => any) {
  calls = [];
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, url: String(url) });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
      if (typeof postAnswer === 'function') return { ok: true, status: 200, json: async () => clone(postAnswer(posts().length)) };
      if (postAnswer === 'throw') throw new Error('network down');
      if (typeof postAnswer === 'number') return { ok: false, status: postAnswer, json: async () => ({ detail: 'Not Found' }) };
      return { ok: true, status: 200, json: async () => clone(postAnswer) };
    }
    return { ok: true, status: 200, json: async () => getBoard(gets().length, u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const posts = () => calls.filter((c) => c.path.endsWith('/chart-maps/gajjala/scan'));
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));

const mount = (q = 'tab=gajjala&sub=bull_flag', strict = false) => {
  const tree = <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>;
  return render(strict ? <StrictMode>{tree}</StrictMode> : tree);
};
/** The ChartMaps ternary: switching away from tab=gajjala unmounts the board, switching back mounts a fresh one. */
function Toggle() {
  const [on, setOn] = useState(true);
  return (
    <>
      <button type="button" data-testid="toggle" onClick={() => setOn((v) => !v)}>toggle</button>
      {on ? <GajjalaBoard /> : null}
    </>
  );
}

/* the b-word is spelled split so this file never carries it */
const BANNED = new RegExp(['enterable', 'b' + 'ounce', 'NaN', 'undefined', 'None'].join('|'));

describe('GajjalaBoard — 🔄 scan on open', () => {
  beforeEach(() => { userRet = OWNER; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('owner: exactly ONE POST to the scan path, method POST, on mount', async () => {
    stub(post('reused'), () => OLD());
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await sleep(60);
    expect(posts()).toHaveLength(1);
    expect(posts()[0].method).toBe('POST');
  });

  it('owner inside <StrictMode>: still ONE POST', async () => {
    stub(post('reused'), () => OLD());
    mount('tab=gajjala&sub=bull_flag', true);
    await screen.findByTestId('gg-tile-AAA');
    await sleep(60);
    expect(posts()).toHaveLength(1);
  });

  it('NEGATIVE: sub clicks never POST again (same mount)', async () => {
    stub(post('reused'), (_n, u) => clone(POT[u.searchParams.get('sub') || 'bull_flag'] || POT.bull_flag));
    mount();
    await screen.findByTestId('gg-tile-AAA');
    fireEvent.click(screen.getByTestId('gg-sub-potential'));
    await screen.findByTestId('gg-track');
    fireEvent.click(screen.getByTestId('gg-sub-bull_flag'));
    await screen.findByTestId('gg-tile-AAA');
    await sleep(60);
    expect(posts()).toHaveLength(1);
    expect(gets().length).toBeGreaterThanOrEqual(3);
  });

  it('unmount + remount (switching away and back) → a second POST', async () => {
    stub(post('reused'), () => OLD());
    render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}><Toggle /></MemoryRouter>);
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    fireEvent.click(screen.getByTestId('toggle'));
    expect(screen.queryByTestId('gg-tile-AAA')).toBeNull();
    fireEvent.click(screen.getByTestId('toggle'));
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(2));
  });

  for (const [who, u] of [['a non-owner (is_admin false)', GUEST], ['no user', null]] as const) {
    it(`NEGATIVE: ${who} → ZERO POSTs, no 🔄 button, no scanning line; the served 🎯 line still renders`, async () => {
      userRet = u as CurrentUser | null;
      stub(post('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 }), () => NEW());
      mount();
      await screen.findByTestId('gg-tile-GGA');
      await sleep(120);
      expect(posts()).toHaveLength(0);
      expect(screen.queryByTestId('gg-rescan')).toBeNull();
      expect(screen.queryByTestId('gg-scanning')).toBeNull();
      expect(screen.getByTestId('gg-aplus-title')).toHaveTextContent(OPEN.bull_flag.enterable.title);
      expect(screen.getByTestId('gg-as-of')).toHaveTextContent(OPEN.bull_flag.scan.as_of_text);
      expect(gets()).toHaveLength(1);
    });
  }

  it('started: the POST line shows, the PREVIOUS board stays while the pass runs, then the new pass replaces it', async () => {
    const started = post('started', { eta_sec: 0.4, poll_sec: 0.05, wait_max_sec: 3 });
    stub(started, (n) => (n <= 1 ? OLD() : n <= 3 ? scanningBoard() : NEW()));
    mount();
    await screen.findByTestId('gg-tile-AAA');
    expect(await screen.findByTestId('gg-scanning')).toHaveTextContent(started.text);
    expect(screen.getByTestId('gg-scanning')).toHaveAttribute('role', 'status');
    // GETs returning the old pass.at with scan.state "scanning": the served scanning line, the old tiles stay.
    await waitFor(() => expect(screen.getByTestId('gg-scanning')).toHaveTextContent(W4), { timeout: 2000 });
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
    expect(screen.queryByTestId('gg-tile-GGA')).toBeNull();
    // the new pass.at with scan.state "idle": the line goes, the new tiles show.
    await screen.findByTestId('gg-tile-GGA', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('gg-scanning')).toBeNull());
    expect(screen.queryByTestId('gg-tile-AAA')).toBeNull();
    expect(screen.getByTestId('gg-as-of')).toHaveTextContent(OPEN.bull_flag.scan.as_of_text);
    const n = gets().length;
    await sleep(200);
    expect(gets()).toHaveLength(n);
  });

  it('NEGATIVE: the poll gives up after the served wait_max_sec — the line goes, no more GETs, GETs bounded', async () => {
    const eta = 0.05; const poll = 0.05; const max = 0.4;
    stub(post('started', { eta_sec: eta, poll_sec: poll, wait_max_sec: max }), (n) => (n <= 1 ? OLD() : scanningBoard()));
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await screen.findByTestId('gg-scanning');
    await waitFor(() => expect(screen.queryByTestId('gg-scanning')).toBeNull(), { timeout: 3000 });
    const polled = gets().length - 1;
    expect(polled).toBeGreaterThan(0);
    expect(polled).toBeLessThanOrEqual(Math.ceil((max - eta) / poll) + 2);
    await sleep(300);
    expect(gets().length - 1).toBe(polled);
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
  });

  it('waiting: polls the same way and stops when the awaited pass lands', async () => {
    const waiting = post('waiting', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 3 });
    stub(waiting, (n) => (n <= 2 ? OLD() : NEW()));
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await screen.findByTestId('gg-tile-GGA', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('gg-scanning')).toBeNull());
    const n = gets().length;
    await sleep(200);
    expect(gets()).toHaveLength(n);
  });

  /* Fix round 1 (2026-10-16): the board on screen can trail the server's latest by one re-read (the board re-reads
   * every 300 s, the cron lands every 300 s). A 🔄 click answered with latest_at = the server's newer pass must NOT
   * judge "landed" on that older board — only on a board read after the POST answered. */
  for (const state of ['started', 'waiting']) {
    it(`NEGATIVE: 🔄 on a board one pass behind (${state}) → the scanning line stays and the poll re-reads`, async () => {
      const MID_AT = '2026-10-13T14:36:00+00:00';
      expect(MID_AT).not.toBe(OLD_AT);
      expect(MID_AT).not.toBe(OPEN.bull_flag.pass.at);
      const click = post(state, { latest_at: MID_AT, eta_sec: 0.2, poll_sec: 0.05, wait_max_sec: 3 });
      const mid = () => { const b = OLD(); b.pass = { ...b.pass, at: MID_AT }; b.scan = { ...b.scan, state: 'scanning', scanning_text: W4 }; return b; };
      let clicked = 0;
      stub((n: number) => (n <= 1 ? post('reused') : click), () => {
        if (!clicked) return OLD();
        clicked += 1;
        return clicked <= 3 ? mid() : NEW();
      });
      mount();
      const btn = await screen.findByTestId('gg-rescan');
      await waitFor(() => expect(posts()).toHaveLength(1));
      await sleep(50);
      expect(screen.queryByTestId('gg-scanning')).toBeNull();
      const before = gets().length;
      clicked = 1;
      fireEvent.click(btn);
      expect(await screen.findByTestId('gg-scanning')).toHaveTextContent(click.text);
      await sleep(100);
      expect(screen.getByTestId('gg-scanning')).toBeTruthy();
      expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
      await waitFor(() => expect(gets().length).toBeGreaterThan(before), { timeout: 2000 });
      await screen.findByTestId('gg-tile-GGA', {}, { timeout: 2000 });
      await waitFor(() => expect(screen.queryByTestId('gg-scanning')).toBeNull());
      expect(posts()).toHaveLength(2);
    });
  }

  /* Fix round 2 (2026-10-16): a 🔄 click answered "reused" for a pass NEWER than the board on screen re-reads ONCE
   * (the board re-reads on the served cadence only, so it could trail a whole cadence), the served line meanwhile. */
  const NEW_AT: string = OPEN.bull_flag.pass.at;
  const later = <T,>(ms: number, v: T) => new Promise<T>((r) => setTimeout(() => r(v), ms));

  it('🔄 answered reused with a NEWER latest_at → exactly ONE re-read, the served line until it lands, then the new tiles', async () => {
    expect(NEW_AT).not.toBe(OLD_AT);
    const reused = post('reused', { latest_at: NEW_AT, text: 'served reused W11 line' });
    stub((n: number) => (n <= 1 ? post('reused') : reused), (n) => (n <= 1 ? OLD() : later(250, NEW())));
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await sleep(50);
    expect(gets()).toHaveLength(1);
    // 2026-10-20: the on-open answer (reused for the pass on screen) prints its served line too; the click replaces it.
    expect(screen.getByTestId('gg-scan-reused')).toHaveTextContent('served reused line');
    fireEvent.click(btn);
    expect(await screen.findByTestId('gg-scan-reused')).toHaveTextContent(reused.text);
    expect(screen.getByTestId('gg-scan-reused')).toHaveAttribute('role', 'status');
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    await screen.findByTestId('gg-tile-GGA', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('gg-scan-reused')).toBeNull());
    expect(gets()).toHaveLength(2);
    expect(screen.getByTestId('gg-as-of')).toHaveTextContent(OPEN.bull_flag.scan.as_of_text);
    await sleep(250);
    expect(gets()).toHaveLength(2);
    expect(posts()).toHaveLength(2);
  });

  it('NEGATIVE: 🔄 answered reused with the SAME latest_at as the board on screen → no extra GET, no poll; the served line shows (2026-10-20)', async () => {
    stub(post('reused', { text: 'served reused W11 line' }), () => OLD());
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    fireEvent.click(btn);
    await waitFor(() => expect(posts()).toHaveLength(2));
    await sleep(200);
    expect(gets()).toHaveLength(1);
    expect(screen.getByTestId('gg-scan-reused')).toHaveTextContent('served reused W11 line');
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    expect(screen.getByTestId('gg-rescan')).not.toBeDisabled();
  });

  it('NEGATIVE: reused for a newer pass whose re-read still answers the older pass → ONE re-read only, never a loop', async () => {
    stub((n: number) => (n <= 1 ? post('reused') : post('reused', { latest_at: NEW_AT })), () => OLD());
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    fireEvent.click(btn);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await sleep(300);
    expect(gets()).toHaveLength(2);
    expect(screen.queryByTestId('gg-scan-reused')).toBeNull();
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
  });

  it('NEGATIVE: reused on mount while the first GET is still in flight and lands the same pass → NO extra GET; the line stays (the in-flight read never clears it)', async () => {
    stub(post('reused'), () => later(150, OLD()));
    mount();
    expect(await screen.findByTestId('gg-scan-reused')).toHaveTextContent('served reused line');
    await screen.findByTestId('gg-tile-AAA', {}, { timeout: 2000 });
    await waitFor(() => expect(posts()).toHaveLength(1));
    await sleep(250);
    expect(gets()).toHaveLength(1);
    expect(screen.getByTestId('gg-scan-reused')).toHaveTextContent('served reused line');
  });

  /* Fix round 2 (2026-10-16): a GET slower than the served poll — a poll step never starts a GET over one in flight,
   * so the board lands and the board it had stays on screen for the whole wait (never a blank board). */
  it('NEGATIVE: GET latency 3× the served poll → the board lands on mount and the old tiles stay for the whole scan', async () => {
    const poll = 0.05; const max = 1; const lat = 3 * poll * 1000;
    stub(post('started', { eta_sec: poll, poll_sec: poll, wait_max_sec: max }), (n) => later(lat, n <= 1 ? OLD() : scanningBoard()));
    const { container } = mount();
    await screen.findByTestId('gg-tile-AAA', {}, { timeout: 2000 });
    expect(await screen.findByTestId('gg-scanning')).toBeTruthy();
    let checks = 0; let shown = 0;
    while (screen.queryByTestId('gg-scanning') && checks < 40) {
      await sleep(40);
      checks += 1;
      if (container.querySelector('[data-state="loaded"]') && screen.queryByTestId('gg-tile-AAA')) shown += 1;
    }
    expect(checks).toBeGreaterThan(5);
    expect(shown).toBe(checks);
    expect(gets().length).toBeGreaterThan(2);
    expect(gets().length).toBeLessThanOrEqual(Math.ceil((max * 1000) / lat) + 2);
  });

  it('eta equal to the served wait_max (waiting for the first pass) → exactly ONE re-read, then the line goes', async () => {
    const waiting = post('waiting', { eta_sec: 0.3, poll_sec: 0.05, wait_max_sec: 0.3 });
    stub(waiting, () => OLD());
    mount();
    await screen.findByTestId('gg-tile-AAA');
    expect(await screen.findByTestId('gg-scanning')).toHaveTextContent(waiting.text);
    await waitFor(() => expect(screen.queryByTestId('gg-scanning')).toBeNull(), { timeout: 3000 });
    expect(gets().length - 1).toBe(1);
    await sleep(250);
    expect(gets().length - 1).toBe(1);
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
  });

  for (const state of ['reused', 'closed']) {
    it(`NEGATIVE: ${state} → no scanning line and NO extra GET`, async () => {
      stub(post(state, { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 }), () => OLD());
      mount();
      await screen.findByTestId('gg-tile-AAA');
      await waitFor(() => expect(posts()).toHaveLength(1));
      await sleep(200);
      expect(screen.queryByTestId('gg-scanning')).toBeNull();
      expect(screen.queryByTestId('gg-scan-refused')).toBeNull();
      expect(gets()).toHaveLength(1);
    });
  }

  it('refused → the served refused line, no poll', async () => {
    const refused = post('refused', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 });
    stub(refused, () => OLD());
    mount();
    expect(await screen.findByTestId('gg-scan-refused')).toHaveTextContent(refused.text);
    await sleep(200);
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    expect(gets()).toHaveLength(1);
    expect(screen.getByTestId('gg-tile-AAA')).toBeTruthy();
  });

  for (const [label, answer] of [['POST 404', 404], ['a network error', 'throw']] as const) {
    it(`NEGATIVE: ${label} → nothing shown, no poll, the button idle again`, async () => {
      stub(answer, () => OLD());
      mount();
      await screen.findByTestId('gg-tile-AAA');
      await waitFor(() => expect(posts()).toHaveLength(1));
      await sleep(200);
      expect(screen.queryByTestId('gg-scanning')).toBeNull();
      expect(screen.queryByTestId('gg-scan-refused')).toBeNull();
      expect(screen.queryByTestId('gg-scan-reused')).toBeNull();
      expect(screen.queryByTestId('gg-scan-err')).toBeNull();
      expect(screen.getByTestId('gg-rescan')).not.toBeDisabled();
      expect(screen.getByTestId('gg-rescan')).not.toHaveAttribute('aria-busy');
      expect(gets()).toHaveLength(1);
    });
  }

  it('🔄 owner: the served label; disabled while scanning with the served line as its title + data-scanning (a click then sends nothing)', async () => {
    stub(post('started', { eta_sec: 1, poll_sec: 1, wait_max_sec: 2 }), () => OLD());
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    expect(btn).toHaveTextContent(POT.bull_flag.scan.rescan_label);
    await screen.findByTestId('gg-scanning');
    expect(screen.getByTestId('gg-rescan')).toBeDisabled();
    // 2026-10-23 ("why is it disabled"): the dimmed button says why — the served scanning line, never an FE word.
    expect(screen.getByTestId('gg-rescan')).toHaveAttribute('title', 'served started line');
    expect(screen.getByTestId('gg-rescan')).toHaveAttribute('data-scanning', 'true');
    fireEvent.click(screen.getByTestId('gg-rescan'));
    await sleep(50);
    expect(posts()).toHaveLength(1);
  });

  it('🔄 a click when idle → a second POST; idle = the served rescan_title, no data-scanning', async () => {
    stub(post('reused'), () => OLD());
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAttribute('title', POT.bull_flag.scan.rescan_title);
    expect(btn).not.toHaveAttribute('data-scanning');
    fireEvent.click(btn);
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(posts()[1].method).toBe('POST');
  });

  /* 2026-10-23, Ajay: "why am I not seeing the scan button it hides itself?" — it hid whenever scan_block served
   * state "closed" (out of the pass window). Now it stays, enabled, its title the served closed line; a tap POSTs and
   * the served closed answer prints (the every-tap rule). The as-of line still falls back to "as of …". */
  it('🔄 stays on screen when scan.state is closed (2026-10-23) — enabled, its title the served closed line; a tap still POSTs', async () => {
    const CLOSED_LINE = 'market closed — last pass 15:56 ET 2026-10-17 (served)';
    const closed = () => { const b = OLD(); b.scan = { ...b.scan, state: 'closed', as_of_text: CLOSED_LINE }; return b; };
    stub(post('closed'), closed);
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    const btn = screen.getByTestId('gg-rescan');
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveTextContent(POT.bull_flag.scan.rescan_label);
    expect(btn).toHaveAttribute('title', CLOSED_LINE);
    expect(btn).not.toHaveAttribute('data-scanning');
    expect(screen.getByTestId('gg-as-of')).toHaveTextContent(`as of ${POT.bull_flag.pass.as_of_et}`);
    fireEvent.click(btn);
    await waitFor(() => expect(posts()).toHaveLength(2));
    expect(await screen.findByTestId('gg-scan-reused')).toHaveTextContent('served closed line');
  });

  it('NEGATIVE: no served rescan_label → no button, closed or not', async () => {
    stub(post('reused'), () => { const b = OLD(); b.scan = { ...b.scan, rescan_label: null }; return b; });
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(screen.queryByTestId('gg-rescan')).toBeNull();
    cleanup();
    stub(post('closed'), () => { const b = OLD(); b.scan = { ...b.scan, state: 'closed', rescan_label: null }; return b; });
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(screen.queryByTestId('gg-rescan')).toBeNull();
  });

  it('NEGATIVE: a non-owner sees no button in a closed session either, and never POSTs', async () => {
    userRet = GUEST;
    stub(post('closed'), () => { const b = OLD(); b.scan = { ...b.scan, state: 'closed' }; return b; });
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await sleep(80);
    expect(posts()).toHaveLength(0);
    expect(screen.queryByTestId('gg-rescan')).toBeNull();
  });

  it('the served scan.note shows; NEGATIVE: none when the note is null', async () => {
    const note = '2 of 9 names were not re-read on open — served note';
    stub(post('reused'), (n) => { const b = NEW(); if (n === 1) b.scan.note = note; return b; });
    mount();
    expect(await screen.findByTestId('gg-scan-note')).toHaveTextContent(note);
    cleanup();
    stub(post('reused'), () => NEW());
    mount();
    await screen.findByTestId('gg-tile-GGA');
    expect(screen.queryByTestId('gg-scan-note')).toBeNull();
  });
});

describe('GajjalaBoard — 🎯 the served A+ line', () => {
  beforeEach(() => { userRet = GUEST; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  for (const sub of Object.keys(OPEN)) {
    it(`renders on the ${sub} sub of the on-open golden — rows link to the served href with the served text`, async () => {
      stub(post('reused'), () => clone(OPEN[sub]));
      mount(`tab=gajjala&sub=${sub}`);
      const banner = await screen.findByTestId('gg-aplus');
      const block = OPEN[sub].enterable;
      expect(within(banner).getByTestId('gg-aplus-title').textContent).toBe(block.title);
      expect(block.rows.length).toBeGreaterThan(0);
      for (const r of block.rows) {
        const el = within(banner).getByTestId(`gg-aplus-row-${r.symbol}-${r.setup}`);
        expect(el.tagName).toBe('A');
        expect(el.getAttribute('href')).toBe(r.href);
        expect(el.textContent).toBe(r.text);
      }
      expect(within(banner).getByTestId('gg-aplus-note').textContent).toBe(block.note);
      expect(banner.textContent || '').not.toMatch(BANNED);
      expect(screen.getByTestId('gg-as-of').textContent).toBe(OPEN[sub].scan.as_of_text);
      expect(screen.getByTestId('gg-as-of').textContent || '').not.toMatch(BANNED);
    });
  }

  for (const [name, b] of [['🧠 golden', POT.potential], ['on-open golden', OPEN.potential]] as const) {
    it(`on the ${name} 🧠 Potential sub the 🎯 line precedes the 📈 Track`, async () => {
      stub(post('reused'), () => clone(b));
      mount('tab=gajjala&sub=potential');
      const track = await screen.findByTestId('gg-track');
      const banner = screen.getByTestId('gg-aplus');
      expect(banner.compareDocumentPosition(track) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      expect(banner.compareDocumentPosition(screen.getByTestId('gg-counts')) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
      for (const r of b.enterable.rows) {
        expect(within(banner).getByTestId(`gg-aplus-row-${r.symbol}-${r.setup}`).textContent).toBe(r.text);
      }
    });
  }

  it('the 🎯 line sits right under the sub strip, before the board error line', async () => {
    stub(post('reused'), () => OLD());
    mount();
    const banner = await screen.findByTestId('gg-aplus');
    const subs = screen.getByRole('tablist', { name: 'Gajjala setups' });
    expect(subs.compareDocumentPosition(banner) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(subs.nextElementSibling).toBe(banner);
  });

  it('no rows → the served empty line, no row, no title', async () => {
    const empty = '🎯 No A+ right now · scanned on open 10:41 ET · UNMEASURED';
    stub(post('reused'), () => { const b = NEW(); b.enterable = { ...b.enterable, title: null, rows: [], empty_text: empty }; return b; });
    mount();
    expect(await screen.findByTestId('gg-aplus-empty')).toHaveTextContent(empty);
    expect(screen.queryAllByTestId(/^gg-aplus-row-/)).toHaveLength(0);
    expect(screen.queryByTestId('gg-aplus-title')).toBeNull();
  });

  it('NEGATIVE: a malformed served row (no symbol / no text) is dropped, never printed as "undefined"', async () => {
    stub(post('reused'), () => {
      const b = NEW();
      b.enterable.rows = [...b.enterable.rows, { setup: 'kiss_fly', text: 'x' }, { symbol: 'ZZZ', setup: 'kiss_fly' }, null];
      return b;
    });
    mount();
    const banner = await screen.findByTestId('gg-aplus');
    expect(within(banner).queryAllByTestId(/^gg-aplus-row-/)).toHaveLength(OPEN.bull_flag.enterable.rows.length);
    expect(banner.textContent || '').not.toMatch(BANNED);
  });

  it('a row without a safe in-app href is plain text, never a link', async () => {
    stub(post('reused'), () => {
      const b = NEW();
      b.enterable.rows = b.enterable.rows.map((r: any) => ({ ...r, href: '//evil.example/x' }));
      return b;
    });
    mount();
    const r = OPEN.bull_flag.enterable.rows[0];
    const el = await screen.findByTestId(`gg-aplus-row-${r.symbol}-${r.setup}`);
    expect(el.tagName).toBe('SPAN');
    expect(el.textContent).toBe(r.text);
  });

  it('NEGATIVE: a board from an older API (hand fixture, no scan / enterable) renders as before', async () => {
    userRet = OWNER;
    stub(post('reused'), () => clone(HAND.bull_flag));
    mount();
    await screen.findByTestId('gg-tile-PFAI');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(screen.queryByTestId('gg-aplus')).toBeNull();
    expect(screen.queryByTestId('gg-rescan')).toBeNull();
    expect(screen.queryByTestId('gg-scan-note')).toBeNull();
    expect(screen.getByTestId('gg-as-of')).toHaveTextContent(`as of ${HAND.bull_flag.pass.as_of_et}`);
  });

  it('the served read_at chip renders on its card; NEGATIVE: null prints nothing', async () => {
    const readAt = 'read at the 10:36 ET pass';
    stub(post('reused'), () => { const b = NEW(); b.tiles[0].gajjala.chips.read_at = readAt; return b; });
    mount();
    const tile = await screen.findByTestId('gg-tile-GGA');
    expect(within(tile).getByTestId('gg-chip-row')).toHaveTextContent(readAt);
    cleanup();
    stub(post('reused'), () => NEW());
    mount();
    const tile2 = await screen.findByTestId('gg-tile-GGA');
    expect(within(tile2).queryByText(/read at/)).toBeNull();
  });
});

/* 🔄 Scan now answers every tap (2026-10-20). Ajay, a screenshot of the button: "This can button has been unresponsive
 * for me". The api answered every tap 200; the board printed nothing for `reused` when the pass was the one on screen
 * and for `closed`, nothing for a non-ok answer, and only dimmed while a pass ran. Pinned here: every plan-less answer
 * prints its SERVED line until the first board read that STARTS after it (a read already in flight never clears it —
 * the test above) or the next tap; the button is disabled + aria-busy while the POST is out; a non-ok answer prints the
 * served `detail` when it is a string (404 → nothing, the house rule); NEGATIVES: no served text → no line, never
 * "undefined"; a network error → nothing and the button idle. No FE timer anywhere (the contracts block pins that). */
describe('GajjalaBoard — 🔄 scan now answers every tap (2026-10-20)', () => {
  beforeEach(() => { userRet = OWNER; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
  const wait = <T,>(ms: number, v: T) => new Promise<T>((r) => setTimeout(() => r(v), ms));
  const bySub = (_n: number, u: URL) => clone(POT[u.searchParams.get('sub') || 'bull_flag'] || POT.bull_flag);
  /** A POST that answers `answer` after `ms`; GETs answer at once. */
  function stubSlowPost(ms: number, answer: any) {
    calls = [];
    const spy = vi.fn(async (url: string, init?: RequestInit) => {
      const u = new URL(String(url), 'http://x');
      const method = String(init?.method || 'GET').toUpperCase();
      calls.push({ method, path: u.pathname, url: String(url) });
      if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
        await wait(ms, null);
        return { ok: true, status: 200, json: async () => clone(answer) };
      }
      return { ok: true, status: 200, json: async () => bySub(0, u) };
    });
    vi.stubGlobal('fetch', spy);
  }
  /** A non-ok POST with the given status and JSON body (the house stub types `{ detail: 'Not Found' }` for every number). */
  function stubFailedPost(status: number, body: unknown) {
    calls = [];
    const spy = vi.fn(async (url: string, init?: RequestInit) => {
      const u = new URL(String(url), 'http://x');
      const method = String(init?.method || 'GET').toUpperCase();
      calls.push({ method, path: u.pathname, url: String(url) });
      if (u.pathname.endsWith('/chart-maps/gajjala/scan')) return { ok: false, status, json: async () => clone(body) };
      return { ok: true, status: 200, json: async () => bySub(0, u) };
    });
    vi.stubGlobal('fetch', spy);
  }

  it('🔄 reused for the pass on screen → the served line shows at once, no extra GET, and goes on the first board read started after it', async () => {
    const line = '🔄 the 10:32 ET pass finished 38 s ago — reused (served W11 line)';
    stub((n: number) => (n <= 1 ? post('reused', { text: 'served on-open line' }) : post('reused', { text: line })), bySub);
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await screen.findByTestId('gg-tile-AAA');
    const before = gets().length;
    fireEvent.click(btn);
    expect(await screen.findByTestId('gg-scan-reused')).toHaveTextContent(line);
    expect(screen.getByTestId('gg-scan-reused')).toHaveAttribute('role', 'status');
    await sleep(150);
    expect(gets()).toHaveLength(before);
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    expect(screen.getByTestId('gg-rescan')).not.toBeDisabled();
    // a board read that STARTS after the answer (a sub click) lands → the line goes
    fireEvent.click(screen.getByTestId('gg-sub-potential'));
    await screen.findByTestId('gg-track');
    await waitFor(() => expect(screen.queryByTestId('gg-scan-reused')).toBeNull());
    expect(posts()).toHaveLength(2);
  });

  it('closed → the served closed line, no poll, not the error class', async () => {
    stub(post('closed', { text: 'market closed — no scan on open; last pass 15:56 ET 2026-10-17 (served)' }), () => OLD());
    mount();
    const el = await screen.findByTestId('gg-scan-reused');
    expect(el).toHaveTextContent('market closed — no scan on open; last pass 15:56 ET 2026-10-17 (served)');
    expect(el.className).not.toContain('cm-note-err');
    await sleep(200);
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    expect(screen.queryByTestId('gg-scan-refused')).toBeNull();
    expect(gets()).toHaveLength(1);
  });

  it('NEGATIVE: an answer without a served text prints no line, never "undefined"', async () => {
    stub(post('reused', { text: null }), () => OLD());
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    fireEvent.click(btn);
    await waitFor(() => expect(posts()).toHaveLength(2));
    await sleep(100);
    expect(screen.queryByTestId('gg-scan-reused')).toBeNull();
    expect(screen.queryByTestId('gg-scan-err')).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/undefined|null/);
  });

  it('the button is disabled and aria-busy while the POST is out; idle again when it answers, the served line on screen', async () => {
    stubSlowPost(200, post('reused', { text: 'served reused line' }));
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('aria-busy', 'true');
    fireEvent.click(btn);
    await sleep(30);
    expect(posts()).toHaveLength(1);
    await waitFor(() => expect(screen.getByTestId('gg-rescan')).not.toBeDisabled(), { timeout: 2000 });
    expect(screen.getByTestId('gg-rescan')).not.toHaveAttribute('aria-busy');
    expect(screen.getByTestId('gg-scan-reused')).toHaveTextContent('served reused line');
    expect((screen.getByTestId('gg-scan-reused').textContent || '')).not.toMatch(BANNED);
  });

  it('a non-ok answer with a served detail → the detail line (error class); NEGATIVE: a 404 or a non-string detail prints nothing', async () => {
    stubFailedPost(503, { detail: 'the scan store did not answer (served detail)' });
    mount();
    const el = await screen.findByTestId('gg-scan-err');
    expect(el).toHaveTextContent('the scan store did not answer (served detail)');
    expect(el.className).toContain('cm-note-err');
    expect(screen.queryByTestId('gg-scan-reused')).toBeNull();
    expect(screen.queryByTestId('gg-scanning')).toBeNull();
    expect(screen.getByTestId('gg-rescan')).not.toBeDisabled();
    cleanup();
    stubFailedPost(404, { detail: 'Not Found' });
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await sleep(100);
    expect(screen.queryByTestId('gg-scan-err')).toBeNull();
    cleanup();
    stubFailedPost(500, { detail: { code: 7 } });
    mount();
    await screen.findByTestId('gg-tile-AAA');
    await waitFor(() => expect(posts()).toHaveLength(1));
    await sleep(100);
    expect(screen.queryByTestId('gg-scan-err')).toBeNull();
    expect(document.body.textContent || '').not.toMatch(/\[object Object\]|undefined/);
  });

  it('a second tap replaces the line with the new answer; a later failed answer clears it', async () => {
    let fail = false;
    const spyBody = (n: number) => (n <= 1 ? post('reused', { text: 'first served line' }) : post('closed', { text: 'second served line' }));
    calls = [];
    const spy = vi.fn(async (url: string, init?: RequestInit) => {
      const u = new URL(String(url), 'http://x');
      const method = String(init?.method || 'GET').toUpperCase();
      calls.push({ method, path: u.pathname, url: String(url) });
      if (u.pathname.endsWith('/chart-maps/gajjala/scan')) {
        if (fail) return { ok: false, status: 502, json: async () => { throw new Error('html body'); } };
        return { ok: true, status: 200, json: async () => clone(spyBody(posts().length)) };
      }
      return { ok: true, status: 200, json: async () => OLD() };
    });
    vi.stubGlobal('fetch', spy);
    mount();
    const btn = await screen.findByTestId('gg-rescan');
    expect(await screen.findByTestId('gg-scan-reused')).toHaveTextContent('first served line');
    fireEvent.click(btn);
    await waitFor(() => expect(screen.getByTestId('gg-scan-reused')).toHaveTextContent('second served line'));
    expect(screen.queryByText('first served line')).toBeNull();
    fail = true;
    fireEvent.click(screen.getByTestId('gg-rescan'));
    await waitFor(() => expect(posts()).toHaveLength(3));
    await waitFor(() => expect(screen.queryByTestId('gg-scan-reused')).toBeNull());
    expect(screen.queryByTestId('gg-scan-err')).toBeNull();
    expect(screen.getByTestId('gg-rescan')).not.toBeDisabled();
  });
});
