import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CurrentUser } from '../hooks/useUser';
import { API } from '../lib/apiBase';
import { LUK_REFRESH_FALLBACK_MS } from '../lib/luk';

/* 🔄 Luk's scan-now button (2026-11-11, lukscan spec §3.6 / WP-LUK-FE). Ajay, verbatim: "Can you put an ondeman scan
 * button for Luk' scans too". The GajjalaBoard.scan.test pattern: a `userRet` mock, a stubbed fetch, small SERVED poll
 * numbers that keep the real timers fast. What is pinned: the owner's 🔄 shows on every sub and in a closed session; a
 * tap POSTs LUK_SCAN_PATH once; every answer prints its served line; the poll is the SERVER's plan, bounded, and stops
 * when the awaited pass lands. NEGATIVES: no POST on mount (owner or not — button only, scan on open = HIS CALL H5); a
 * non-owner never sees the button and never POSTs; no scan block → no button, no crash; a double tap → ONE POST;
 * no_room (no poll fields) never polls; the FE types no scan word; no new setInterval. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('./LukStrip', () => ({ LukStrip: () => <div data-testid="m-strip" /> }));
vi.mock('./LukCard', () => ({ LukCard: ({ tile }: any) => <div data-testid={`m-tile-${tile.symbol}`} /> }));
vi.mock('./LukScreens', () => ({ LukScreens: () => <div data-testid="m-screens" /> }));
vi.mock('./LukPlaybook', () => ({ LukPlaybook: () => <div data-testid="m-playbook" /> }));
vi.mock('./LukTrackRecord', () => ({ LukTrackRecord: () => <div data-testid="m-track" /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span data-testid="rules-info" /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));

import LukBoard from './LukBoard';

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const GUEST: CurrentUser = { ...OWNER, email: 'guest@example.com', is_admin: false };

/* Test data shaped like the served LS / LW lines — the board prints whatever it is given. */
const OLD_AT = '2026-11-11T15:31:00+00:00';
const NEW_AT = '2026-11-11T15:33:12+00:00';
const LS4 = 'served scanning line LS4 (scan.scanning_text)';
const LABEL = 'served rescan label';
const TITLE = 'served rescan title LS9';
const CLOSED_ASOF = 'served closed as_of LS3';
const SUBS = ['pullback_reversal', 'premarket', 'playbook', 'track_record'];

function board(opts: { at?: string; state?: string; sub?: string; scan?: any } = {}) {
  const sub = opts.sub ?? 'pullback_reversal';
  const state = opts.state ?? 'idle';
  return clone({
    tab: 'luk', title: 'served title', sub,
    subs: SUBS.map((k) => ({ key: k, label: k, n: 0 })),
    session: { badge: 'served badge', refresh_sec: 300 },
    pass: { at: opts.at ?? OLD_AT, text: `served pass ${opts.at ?? OLD_AT}`, stale: false },
    tiles: sub === 'pullback_reversal' ? [{ symbol: (opts.at ?? OLD_AT) === OLD_AT ? 'OLD' : 'NEW', setup: sub, state: 'aplus' }] : [],
    screens: sub === 'premarket' ? { key: 'premarket', title: 'served screen', rows: [] } : null,
    scan: opts.scan !== undefined ? opts.scan : {
      state, on_demand: false, started_at_et: null, bars_through_et: null,
      as_of_text: state === 'closed' ? CLOSED_ASOF : 'served as_of',
      scanning_text: state === 'scanning' ? LS4 : null, text: null, note: null,
      rescan_label: LABEL, rescan_title: TITLE,
    },
  });
}
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
    if (u.pathname.endsWith('/chart-maps/luk/scan')) {
      if (typeof postAnswer === 'function') return postAnswer(posts().length);
      if (typeof postAnswer === 'number') return { ok: false, status: postAnswer, json: async () => ({ detail: postAnswer === 404 ? 'Not Found' : 'served 503 detail' }) };
      return { ok: true, status: 200, json: async () => clone(postAnswer) };
    }
    return { ok: true, status: 200, json: async () => getBoard(gets().length, u) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const posts = () => calls.filter((c) => c.path.endsWith('/chart-maps/luk/scan'));
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/luk'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
const bySub = (u: URL) => u.searchParams.get('sub') || 'pullback_reversal';

const mount = (q = 'tab=luk&sub=pullback_reversal') =>
  render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><LukBoard /></MemoryRouter>);

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

describe('LukBoard — 🔄 scan now (button only)', () => {
  beforeEach(() => { userRet = OWNER; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  for (const sub of SUBS) {
    it(`owner: the 🔄 button shows on the ${sub} sub with the served label and title`, async () => {
      stub(post('reused'), (_n, u) => board({ sub: bySub(u) }));
      mount(`tab=luk&sub=${sub}`);
      const btn = await screen.findByTestId('luk-rescan');
      expect(btn).toHaveTextContent(LABEL);
      expect(btn).toHaveAttribute('title', TITLE);
      expect(btn.className).toBe('gg-rescan');
      expect(btn).not.toBeDisabled();
    });
  }

  it('owner, closed session: the button stays, enabled, its title the served closed line; a tap prints the closed line', async () => {
    stub(post('closed'), () => board({ state: 'closed' }));
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    expect(btn).not.toBeDisabled();
    expect(btn).toHaveAttribute('title', CLOSED_ASOF);
    fireEvent.click(btn);
    expect(await screen.findByTestId('luk-scan-note')).toHaveTextContent('served closed line');
    expect(screen.queryByTestId('luk-scanning')).toBeNull();
    const n = gets().length;
    await sleep(120);
    expect(gets()).toHaveLength(n);
  });

  it('NEGATIVE: NO POST on mount — owner (button only; scan on open = HIS CALL H5)', async () => {
    stub(post('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 }), () => board());
    mount();
    await screen.findByTestId('luk-rescan');
    await sleep(150);
    expect(posts()).toHaveLength(0);
    expect(gets()).toHaveLength(1);
  });

  for (const [who, u] of [['a non-owner (is_admin false)', GUEST], ['no user', null]] as const) {
    it(`NEGATIVE: ${who} → no button and ZERO POSTs, even with rescan_label served`, async () => {
      userRet = u as CurrentUser | null;
      stub(post('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 }), () => board());
      mount();
      await screen.findByTestId('m-tile-OLD');
      await sleep(120);
      expect(screen.queryByTestId('luk-rescan')).toBeNull();
      expect(screen.queryByTestId('luk-scanning')).toBeNull();
      expect(posts()).toHaveLength(0);
      expect(gets()).toHaveLength(1);
    });
  }

  it('NEGATIVE: owner with no scan block (fault payload) → no button, no crash', async () => {
    stub(post('started'), () => board({ scan: null }));
    mount();
    await screen.findByTestId('m-tile-OLD');
    expect(screen.queryByTestId('luk-rescan')).toBeNull();
    await sleep(60);
    expect(posts()).toHaveLength(0);
  });

  it('NEGATIVE: a blank served label → no button', async () => {
    const b = board(); b.scan.rescan_label = '  ';
    stub(post('started'), () => clone(b));
    mount();
    await screen.findByTestId('m-tile-OLD');
    expect(screen.queryByTestId('luk-rescan')).toBeNull();
  });

  it('a tap POSTs exactly `${API}/chart-maps/luk/scan` once, method POST, credentials include', async () => {
    const spy = stub(post('reused'), () => board());
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    await waitFor(() => expect(posts()).toHaveLength(1));
    expect(posts()[0].url).toBe(`${API}/chart-maps/luk/scan`);
    expect(posts()[0].method).toBe('POST');
    const init = spy.mock.calls.find((c) => String(c[0]).endsWith('/chart-maps/luk/scan'))![1] as RequestInit;
    expect(init.credentials).toBe('include');
    await sleep(60);
    expect(posts()).toHaveLength(1);
  });

  it('aria-busy="true" and disabled while the POST is out; a double tap → ONE POST', async () => {
    let release: (v: any) => void = () => undefined;
    stub(() => new Promise((r) => { release = r; }), () => board());
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    fireEvent.click(btn);
    fireEvent.click(btn);
    await waitFor(() => expect(btn).toHaveAttribute('aria-busy', 'true'));
    expect(btn).toBeDisabled();
    fireEvent.click(btn);
    expect(posts()).toHaveLength(1);
    await act(async () => { release({ ok: true, status: 200, json: async () => post('reused') }); });
    await waitFor(() => expect(btn).not.toHaveAttribute('aria-busy'));
    expect(btn).not.toBeDisabled();
    expect(posts()).toHaveLength(1);
  });

  it('started: the served line + data-scanning + disabled + title = the line; a GET each served step; stops when pass.at moves', async () => {
    const started = post('started', { eta_sec: 0.15, poll_sec: 0.05, wait_max_sec: 3 });
    let tapped = 0;
    stub(started, () => {
      if (!tapped) return board();
      tapped += 1;
      return tapped <= 3 ? board({ state: 'scanning' }) : board({ at: NEW_AT });
    });
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    tapped = 1;
    fireEvent.click(btn);
    const line = await screen.findByTestId('luk-scanning');
    expect(line).toHaveTextContent(started.text);
    expect(line).toHaveAttribute('role', 'status');
    expect(btn).toHaveAttribute('data-scanning', 'true');
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute('title', started.text);
    // a GET serving scan.state "scanning" → the served scanning line; the old board stays.
    await waitFor(() => expect(screen.getByTestId('luk-scanning')).toHaveTextContent(LS4), { timeout: 2000 });
    expect(screen.getByTestId('m-tile-OLD')).toBeTruthy();
    // the new pass.at with scan idle → the line goes, the new board shows, the button is live again.
    await screen.findByTestId('m-tile-NEW', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('luk-scanning')).toBeNull());
    expect(btn).not.toHaveAttribute('data-scanning');
    expect(btn).not.toBeDisabled();
    const n = gets().length;
    await sleep(200);
    expect(gets()).toHaveLength(n);
  });

  it('NEGATIVE: a board with the old pass.at never ends the poll; it gives up past the served wait_max — GETs bounded', async () => {
    const eta = 0.05; const poll = 0.05; const max = 0.4;
    stub(post('started', { eta_sec: eta, poll_sec: poll, wait_max_sec: max }), (n) => (n <= 1 ? board() : board({ state: 'scanning' })));
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    await screen.findByTestId('luk-scanning');
    await waitFor(() => expect(screen.queryByTestId('luk-scanning')).toBeNull(), { timeout: 3000 });
    const polled = gets().length - 1;
    expect(polled).toBeGreaterThan(0);
    expect(polled).toBeLessThanOrEqual(Math.ceil((max - eta) / poll) + 2);
    await sleep(300);
    expect(gets().length - 1).toBe(polled);
    expect(screen.getByTestId('m-tile-OLD')).toBeTruthy();
  });

  it('NEGATIVE: a moved pass.at while scan.state is still "scanning" does not end the poll', async () => {
    let tapped = 0;
    stub(post('waiting', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 3 }), () => {
      if (!tapped) return board();
      tapped += 1;
      return tapped <= 3 ? board({ at: NEW_AT, state: 'scanning' }) : board({ at: NEW_AT });
    });
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    tapped = 1;
    await screen.findByTestId('luk-scanning');
    await screen.findByTestId('m-tile-NEW', {}, { timeout: 2000 });
    expect(screen.getByTestId('luk-scanning')).toBeTruthy();
    await waitFor(() => expect(screen.queryByTestId('luk-scanning')).toBeNull(), { timeout: 2000 });
    expect(tapped).toBeGreaterThan(3);
  });

  for (const state of ['started', 'waiting']) {
    it(`NEGATIVE: 🔄 on a board one pass behind (${state}) → the old board never ends the poll; only a read after the answer does`, async () => {
      const MID_AT = '2026-11-11T15:32:05+00:00';
      const click = post(state, { latest_at: MID_AT, eta_sec: 0.2, poll_sec: 0.05, wait_max_sec: 3 });
      let tapped = 0;
      stub(click, () => {
        if (!tapped) return board();
        tapped += 1;
        return tapped <= 3 ? board({ at: MID_AT, state: 'scanning' }) : board({ at: NEW_AT });
      });
      mount();
      const btn = await screen.findByTestId('luk-rescan');
      tapped = 1;
      fireEvent.click(btn);
      expect(await screen.findByTestId('luk-scanning')).toHaveTextContent(click.text);
      await sleep(100);
      expect(screen.getByTestId('luk-scanning')).toBeTruthy();
      expect(screen.getByTestId('m-tile-OLD')).toBeTruthy();
      await screen.findByTestId('m-tile-NEW', {}, { timeout: 2000 });
      await waitFor(() => expect(screen.queryByTestId('luk-scanning')).toBeNull());
      expect(posts()).toHaveLength(1);
    });
  }

  it('waiting (slot_wait, with a plan): polls the same way and stops when the awaited pass lands', async () => {
    stub(post('waiting', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 3 }), (n) => (n <= 2 ? board() : board({ at: NEW_AT })));
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    expect(await screen.findByTestId('luk-scanning')).toHaveTextContent('served waiting line');
    await screen.findByTestId('m-tile-NEW', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('luk-scanning')).toBeNull());
    const n = gets().length;
    await sleep(200);
    expect(gets()).toHaveLength(n);
  });

  it('NEGATIVE [C7]: waiting with null eta / poll / wait_max (no_room) → NO poll GET, no data-scanning, button live; the note until the next board GET', async () => {
    const noRoom = post('waiting', { text: 'served no_room LW16 line' });
    stub(noRoom, (_n, u) => board({ sub: bySub(u) }));
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    fireEvent.click(btn);
    expect(await screen.findByTestId('luk-scan-note')).toHaveTextContent(noRoom.text);
    expect(screen.queryByTestId('luk-scanning')).toBeNull();
    expect(btn).not.toHaveAttribute('data-scanning');
    await waitFor(() => expect(btn).not.toBeDisabled());
    await sleep(200);
    expect(gets()).toHaveLength(1);
    expect(screen.getByTestId('luk-scan-note')).toBeTruthy();
    // the next board GET (a sub click) clears it.
    fireEvent.click(screen.getByTestId('luk-sub-premarket'));
    await screen.findByTestId('m-screens');
    await waitFor(() => expect(screen.queryByTestId('luk-scan-note')).toBeNull());
  });

  it('reused for the pass on screen → the served note until the next GET that starts after the answer; no extra GET', async () => {
    const reused = post('reused', { text: 'served reused LW11 line' });
    stub(reused, (_n, u) => board({ sub: bySub(u) }));
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    expect(await screen.findByTestId('luk-scan-note')).toHaveTextContent(reused.text);
    await sleep(150);
    expect(gets()).toHaveLength(1);
    expect(screen.getByTestId('luk-scan-note')).toBeTruthy();
    fireEvent.click(screen.getByTestId('luk-sub-playbook'));
    await screen.findByTestId('m-playbook');
    await waitFor(() => expect(screen.queryByTestId('luk-scan-note')).toBeNull());
  });

  it('reused for a NEWER pass → exactly ONE extra GET, the served line until it lands, then the new board', async () => {
    const reused = post('reused', { latest_at: NEW_AT, text: 'served reused newer line' });
    stub(reused, (n) => (n <= 1 ? board() : board({ at: NEW_AT })));
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    await screen.findByTestId('m-tile-NEW', {}, { timeout: 2000 });
    await waitFor(() => expect(screen.queryByTestId('luk-scan-note')).toBeNull());
    await sleep(200);
    expect(gets()).toHaveLength(2);
    expect(screen.queryByTestId('luk-scanning')).toBeNull();
  });

  it('refused → the served line in luk-scan-refused; no poll', async () => {
    stub(post('refused', { text: 'served refused LW17 line' }), () => board());
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    expect(await screen.findByTestId('luk-scan-refused')).toHaveTextContent('served refused LW17 line');
    expect(screen.queryByTestId('luk-scan-note')).toBeNull();
    await sleep(120);
    expect(gets()).toHaveLength(1);
  });

  it('non-ok 503 with a string detail → luk-scan-err prints the served detail; no poll', async () => {
    stub(503, () => board());
    mount();
    fireEvent.click(await screen.findByTestId('luk-rescan'));
    expect(await screen.findByTestId('luk-scan-err')).toHaveTextContent('served 503 detail');
    await sleep(120);
    expect(gets()).toHaveLength(1);
  });

  it('NEGATIVE: 404 → nothing printed, no poll, the button idle again', async () => {
    stub(404, () => board());
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    fireEvent.click(btn);
    await waitFor(() => expect(posts()).toHaveLength(1));
    await waitFor(() => expect(btn).not.toBeDisabled());
    await sleep(120);
    for (const id of ['luk-scan-err', 'luk-scan-note', 'luk-scan-refused', 'luk-scanning']) expect(screen.queryByTestId(id)).toBeNull();
    expect(gets()).toHaveLength(1);
  });

  it('every answer replaces the line of the one before it', async () => {
    stub((k: number) => ({ ok: true, status: 200, json: async () => (k <= 1 ? post('refused', { text: 'first refused' }) : post('closed', { text: 'then closed' })) }), () => board());
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    fireEvent.click(btn);
    await screen.findByTestId('luk-scan-refused');
    await waitFor(() => expect(btn).not.toBeDisabled());
    fireEvent.click(btn);
    expect(await screen.findByTestId('luk-scan-note')).toHaveTextContent('then closed');
    expect(screen.queryByTestId('luk-scan-refused')).toBeNull();
  });

  it('NEGATIVE: no new setInterval — the poll is a setTimeout chain on the SERVED plan', async () => {
    stub(post('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 0.3 }), () => board({ state: 'scanning' }));
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    // spy only across plain sleeps (testing-library's waitFor runs its own 50 ms interval).
    const si = vi.spyOn(window, 'setInterval');
    const st = vi.spyOn(window, 'setTimeout');
    fireEvent.click(btn);
    await sleep(150);
    expect(screen.getByTestId('luk-scanning')).toBeTruthy();
    await sleep(400);
    expect(screen.queryByTestId('luk-scanning')).toBeNull();
    const intervals = si.mock.calls.map((c) => c[1]);
    const served = st.mock.calls.map((c) => c[1]).filter((ms) => ms === 50);
    si.mockRestore();
    st.mockRestore();
    // only the board's own cadence interval may (re)start — the served 300 s, or the fallback before a board lands.
    for (const ms of intervals) expect([300_000, LUK_REFRESH_FALLBACK_MS]).toContain(ms);
    expect(served.length).toBeGreaterThan(0);
    expect(gets().length).toBeGreaterThan(1);
    const src = await readSource('src/components/LukBoard.tsx');
    expect(src.split('setInterval(').length - 1).toBe(1);
  });
});

describe('LukBoard source — 🔄 the FE types no scan word and never POSTs on mount', () => {
  it('NEGATIVE: none of the served scan sentences is typed in the component', async () => {
    const src = await readSource('src/components/LukBoard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/.*$/gm, '');
    for (const w of ['scanning…', 'scan now', 'on demand', 'has not landed', 'too close to', 'reused (', 'still running',
      'switched off', 'could not start', 'no scan;', 'last pass', 'rings no device', 'outside 🥇']) {
      expect(code).not.toContain(w);
    }
  });
  it('NEGATIVE: startScan is called only from the button onClick (no mount effect)', async () => {
    const src = await readSource('src/components/LukBoard.tsx');
    const uses = src.match(/startScan\(\)/g) || [];
    expect(uses).toHaveLength(1);
    expect(src).toMatch(/onClick=\{\(\) => void startScan\(\)\}/);
  });
  it('the button JSX carries gg-rescan, luk-rescan and disabled={scanning || posting}', async () => {
    const src = await readSource('src/components/LukBoard.tsx');
    expect(src).toMatch(/className="gg-rescan" data-testid="luk-rescan" disabled=\{scanning \|\| posting\}/);
    expect(src).toMatch(/LUK_SCAN_PATH/);
  });
});

/* 🔄 2026-11-11 (lukstale WP-FE §3.4): the owner's button sits in the title row, right after the title, and its served
 * answer lines print under that row, above the honesty paragraph — for every state. The file's `board()` carries no
 * `honesty`; this describe's fixture adds a served one. NEGATIVES: a non-owner / no user never sees the button (the
 * title and the pass line still print); no inline style inside the title row (the 📱 430 px case — jsdom has no
 * layout, the stylesheet pins live in LukBoard.phone.test.tsx). */
describe('🔄 right after the title (2026-11-11)', () => {
  const HONESTY = 'served honesty line';
  const hb = (opts: Parameters<typeof board>[0] = {}) => ({ ...board(opts), honesty: HONESTY });
  const before = (a: Element, b: Element) => (a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0;
  beforeEach(() => { userRet = OWNER; });
  afterEach(() => { vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('owner: the button is inside luk-topline, after the title, before the honesty line and the pass line; the pass line holds no button', async () => {
    stub(post('reused'), () => hb());
    const { container } = mount();
    const btn = await screen.findByTestId('luk-rescan');
    const top = screen.getByTestId('luk-topline');
    expect(top.contains(btn)).toBe(true);
    const title = screen.getByTestId('luk-title');
    expect(top.contains(title)).toBe(true);
    expect(title.tagName).toBe('H2');
    expect(before(title, btn)).toBe(true);
    expect(before(btn, screen.getByTestId('luk-honesty'))).toBe(true);
    expect(before(btn, screen.getByTestId('luk-pass'))).toBe(true);
    const passline = container.querySelector('.luk-passline')!;
    expect(passline).not.toBeNull();
    expect(passline.querySelector('button')).toBeNull();
    expect(container.querySelectorAll('[data-testid="luk-rescan"]')).toHaveLength(1);
  });

  const answers: Array<[string, any, string, string]> = [
    ['started', post('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 3 }), 'luk-scanning', 'served started line'],
    ['reused', post('reused', { text: 'served reused line' }), 'luk-scan-note', 'served reused line'],
    ['closed', post('closed', { text: 'served closed answer' }), 'luk-scan-note', 'served closed answer'],
    ['refused', post('refused', { text: 'served refused answer' }), 'luk-scan-refused', 'served refused answer'],
    ['503', 503, 'luk-scan-err', 'served 503 detail'],
  ];
  for (const [name, answer, id, text] of answers) {
    it(`owner, ${name}: the served answer line prints verbatim BEFORE the honesty line`, async () => {
      stub(answer, () => hb());
      mount();
      fireEvent.click(await screen.findByTestId('luk-rescan'));
      const line = await screen.findByTestId(id);
      expect(line.textContent).toBe(text);
      expect(before(screen.getByTestId('luk-topline'), line)).toBe(true);
      expect(before(line, screen.getByTestId('luk-honesty'))).toBe(true);
    });
  }

  for (const [who, u] of [['a non-owner (is_admin false)', GUEST], ['no user', null]] as const) {
    it(`NEGATIVE: ${who} → no luk-rescan anywhere; the title still prints; the pass line keeps badge + pass text`, async () => {
      userRet = u as CurrentUser | null;
      stub(post('started'), () => hb());
      const { container } = mount();
      await screen.findByTestId('m-tile-OLD');
      expect(container.querySelector('[data-testid="luk-rescan"]')).toBeNull();
      expect(screen.getByTestId('luk-title')).toHaveTextContent('served title');
      expect(screen.getByTestId('luk-topline').contains(screen.getByTestId('luk-title'))).toBe(true);
      const passline = container.querySelector('.luk-passline')!;
      expect(passline.contains(screen.getByTestId('luk-session-badge'))).toBe(true);
      expect(passline.contains(screen.getByTestId('luk-pass'))).toBe(true);
    });
  }

  it('NEGATIVE: owner, blank title → the button still renders in the title row; no title h2', async () => {
    const b = hb(); b.title = '  ';
    stub(post('reused'), () => clone(b));
    mount();
    const btn = await screen.findByTestId('luk-rescan');
    expect(screen.getByTestId('luk-topline').contains(btn)).toBe(true);
    expect(screen.queryByTestId('luk-title')).toBeNull();
  });

  it('NEGATIVE: owner, blank title AND blank label → no title row, no button', async () => {
    const b = hb(); b.title = ''; b.scan.rescan_label = ' ';
    stub(post('reused'), () => clone(b));
    mount();
    await screen.findByTestId('m-tile-OLD');
    expect(screen.queryByTestId('luk-topline')).toBeNull();
    expect(screen.queryByTestId('luk-rescan')).toBeNull();
  });

  it('NEGATIVE: owner, no scan block → no button; the title row still holds the title', async () => {
    stub(post('reused'), () => hb({ scan: null }));
    mount();
    await screen.findByTestId('m-tile-OLD');
    expect(screen.queryByTestId('luk-rescan')).toBeNull();
    expect(screen.getByTestId('luk-topline').contains(screen.getByTestId('luk-title'))).toBe(true);
  });

  it('owner at 430 px: nothing inside the title row carries a style attribute; NEGATIVE (source): no style={, ONE button, ONE startScan()', async () => {
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: 430 });
    const b = hb(); b.title = 'served title that is very long and wraps on a phone · UNMEASURED';
    stub(post('reused'), () => clone(b));
    mount();
    await screen.findByTestId('luk-rescan');
    const top = screen.getByTestId('luk-topline');
    expect(top.getAttribute('style')).toBeNull();
    for (const el of Array.from(top.querySelectorAll('*'))) expect(el.getAttribute('style')).toBeNull();
    const src = await readSource('src/components/LukBoard.tsx');
    expect(src).not.toContain('style={');
    expect(src.split('data-testid="luk-rescan"').length - 1).toBe(1);
    expect(src.split('onClick={() => void startScan()}').length - 1).toBe(1);
    expect(src).toContain('his setup state orders this board');
  });
});
