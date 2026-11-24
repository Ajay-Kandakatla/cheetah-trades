/**
 * 🧾 MyDayLine + its GajjalaBoard mount (2026-11-23, spec accountability §3.4 / §3.5 / WP-FE). Ajay 2026-11-23: "Please
 * create a rule to warn me to not over trade and hold me accountable if I am missing out any gajjalas rules".
 *
 * Pinned: the line prints the SERVED my_day words verbatim (text, next_text, quiet_text, footer); the GET carries the
 * board's served session date; a successful journal write re-reads the line. NEGATIVES: owner_only / an HTTP error / a
 * network error / junk → nothing; a served null my_day → no line and the FE composes no count or quote; on the board a
 * non-owner (broker_flags null or absent) → no fetch and no button; the 1-minute page and 🧪 Audited never fetch; the
 * cards and their order are the same with and without the line. The payloads are HAND copies of the §3.5 shape.
 */
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_board_2026_10_13.json';
import GajjalaBoard from './GajjalaBoard';
import { todayEtKey } from '../lib/alertKinds';
import { MY_TRADES_PATH, MyDayLine, myDayDate, myTradesUrl, parseMyTrades } from './MyDayLine';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const BOARDS: Record<string, any> = (fixture as any).boards;

const OK = {
  state: 'ok', date: '2026-10-13',
  my_day: { text: 'served day text', next_text: 'served next text', quiet_text: 'served quiet text',
    footer: 'served footer', data_text: 'served data text' },
  trades: [{ id: 't1', sym: 'PFAI', verdict: 'missed', verdict_text: 'served verdict', checks: [], warned_at_tap: [],
    alert_id: null, alert_same: null, exit_text: 'served exit text' }],
  voided: [], totals: { n: 1, missed: 1, no_aplus: 0, kept_aplus: 0, warned_and_took: 0 },
  week: { n: 1, text: 'served week' }, tally_10d: {}, aplus_today: [],
};
const OWNER_ONLY = { state: 'owner_only', reason: 'served owner only', title: 'served title' };
const BROKER = { add_label: 'add', add_placeholder: 'ticker', broker: 'Fidelity', editable: false, empty_text: null,
  fault_text: null, remove_title: 'x', symbols: [], text: 'served tag', toggle: '🚫' };

type Call = { url: string; method: string; body: any };
let calls: Call[] = [];
const myGets = () => calls.filter((c) => c.method === 'GET' && c.url.includes(MY_TRADES_PATH));

function stub(opts: { board?: any; mine?: any | (() => any); mineStatus?: number; reject?: boolean }) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = String(url);
    const method = (init?.method || 'GET').toUpperCase();
    calls.push({ url: u, method, body: init?.body ? JSON.parse(String(init.body)) : null });
    if (u.includes(MY_TRADES_PATH)) {
      if (opts.reject) throw new Error('network');
      const p = typeof opts.mine === 'function' ? opts.mine() : opts.mine;
      return { ok: (opts.mineStatus ?? 200) < 400, status: opts.mineStatus ?? 200, json: async () => clone(p) };
    }
    if (opts.board && u.includes('/chart-maps/gajjala') && !u.includes('/scan') && !u.includes('entry-tape')) {
      return { ok: true, status: 200, json: async () => clone(opts.board) };
    }
    return { ok: true, status: 200, json: async () => ({}) };
  }));
}

afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🧾 parseMyTrades / myTradesUrl', () => {
  it('ok → the served shape; anything else → null', () => {
    expect(parseMyTrades(clone(OK))?.my_day?.text).toBe('served day text');
    expect(parseMyTrades(OWNER_ONLY)).toBeNull();
    expect(parseMyTrades({ state: 'error', reason: 'x' })).toBeNull();
    expect(parseMyTrades(null)).toBeNull();
    expect(parseMyTrades([1, 2])).toBeNull();
  });
  it('NEGATIVE: a my_day without a text string → null my_day; junk trades are dropped', () => {
    const p = parseMyTrades({ ...clone(OK), my_day: { text: 3 }, trades: [{ id: 'x' }, null, { sym: 'A' }] });
    expect(p?.my_day).toBeNull();
    expect(p?.trades).toEqual([]);
  });
  it('date rides only as a YYYY-MM-DD string', () => {
    expect(myTradesUrl('2026-11-23')).toMatch(/\/chart-maps\/gajjala\/my-trades\?date=2026-11-23$/);
    expect(myTradesUrl(null)).toMatch(/\/chart-maps\/gajjala\/my-trades$/);
    expect(myTradesUrl('11/23/2026')).toMatch(/\/chart-maps\/gajjala\/my-trades$/);
  });
  it('myDayDate: the session date rides only when it is today ET (2026-11-24 refix)', () => {
    const now = Date.UTC(2026, 10, 24, 17, 0);                      // 12:00 ET Tue 2026-11-24
    expect(myDayDate('2026-11-24', now)).toBe('2026-11-24');
  });
  it('NEGATIVE myDayDate: before the first pass the board is on yesterday → null (server default = today ET)', () => {
    const early = Date.UTC(2026, 10, 24, 8, 0);                     // 03:00 ET Tue; board still on Mon 2026-11-23
    expect(myDayDate('2026-11-23', early)).toBeNull();
    expect(myDayDate('2026-11-24', Date.UTC(2026, 10, 25, 4, 30))).toBe('2026-11-24');  // 23:30 ET same day
    expect(myDayDate('2026-11-24', Date.UTC(2026, 10, 25, 17, 0))).toBeNull();          // 12:00 ET the day after
    expect(myDayDate(null, early)).toBeNull();
    expect(myDayDate(undefined, early)).toBeNull();
  });
});

describe('🧾 MyDayLine', () => {
  it('prints the served my_day words verbatim and GETs with the date', async () => {
    stub({ mine: OK });
    render(<MyDayLine date="2026-10-13" />);
    await screen.findByTestId('my-day-line');
    expect(screen.getByTestId('my-day-text').textContent).toBe('served day text');
    expect(screen.getByTestId('my-day-next').textContent).toBe('served next text');
    expect(screen.getByTestId('my-day-quiet').textContent).toBe('served quiet text');
    expect(screen.getByTestId('my-day-footer').textContent).toBe('served footer');
    expect(myGets()).toHaveLength(1);
    expect(myGets()[0].url).toContain('?date=2026-10-13');
  });

  it('null next / quiet → those lines are absent', async () => {
    stub({ mine: { ...clone(OK), my_day: { text: 'served day text', next_text: null, quiet_text: null, footer: 'f' } } });
    render(<MyDayLine date="2026-10-13" />);
    await screen.findByTestId('my-day-text');
    expect(screen.queryByTestId('my-day-next')).toBeNull();
    expect(screen.queryByTestId('my-day-quiet')).toBeNull();
  });

  it('NEGATIVE: owner_only → renders nothing', async () => {
    stub({ mine: OWNER_ONLY });
    const { container } = render(<MyDayLine date="2026-10-13" />);
    await waitFor(() => expect(myGets()).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(container.innerHTML).toBe('');
    expect(screen.queryByTestId('my-day-open')).toBeNull();
  });

  it('NEGATIVE: an HTTP error / a network error → renders nothing', async () => {
    stub({ mine: { detail: 'x' }, mineStatus: 500 });
    const a = render(<MyDayLine date="2026-10-13" />);
    await waitFor(() => expect(myGets()).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(a.container.innerHTML).toBe('');
    a.unmount();
    stub({ reject: true });
    const b = render(<MyDayLine date="2026-10-13" />);
    await waitFor(() => expect(myGets()).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(b.container.innerHTML).toBe('');
  });

  it('NEGATIVE: served null my_day → no line; the FE composes no count or quote (only the 🧾 button)', async () => {
    stub({ mine: { ...clone(OK), my_day: null } });
    render(<MyDayLine date="2026-10-13" />);
    const btn = await screen.findByTestId('my-day-open');
    expect(screen.queryByTestId('my-day-line')).toBeNull();
    expect(screen.getByTestId('my-day').textContent).toBe(btn.textContent);
    expect(screen.getByTestId('my-day').textContent).not.toMatch(/\d/);
  });

  it('the 🧾 button opens the sheet; a successful log re-reads the line', async () => {
    let n = 0;
    stub({ mine: () => (n++ === 0 ? OK : { ...clone(OK), my_day: { ...OK.my_day, text: 'served day text 2' } }) });
    render(<MyDayLine date="2026-10-13" />);
    fireEvent.click(await screen.findByTestId('my-day-open'));
    expect(screen.getByTestId('my-sheet')).toBeTruthy();
    expect(screen.getByTestId('my-sheet-data').textContent).toBe('served data text');
    fireEvent.change(screen.getByTestId('my-sheet-sym'), { target: { value: 'pfai' } });
    fireEvent.change(screen.getByTestId('my-sheet-entry'), { target: { value: '3.1' } });
    fireEvent.click(screen.getByTestId('my-sheet-grade-A+'));
    fireEvent.click(screen.getByTestId('my-sheet-patience-patient'));
    fireEvent.click(screen.getByTestId('my-sheet-discipline-kept'));
    fireEvent.click(screen.getByTestId('my-sheet-send'));
    await waitFor(() => expect(screen.getByTestId('my-day-text').textContent).toBe('served day text 2'));
    expect(myGets()).toHaveLength(2);
  });

  it('source guard: no GG quote, no count words, no b-word, no email in either file', async () => {
    for (const rel of ['src/components/MyDayLine.tsx', 'src/components/MyTradeSheet.tsx']) {
      const src = await readSource(rel);
      expect(src).not.toMatch(/bounce/i);
      expect(src).not.toMatch(/@[a-z0-9-]+\.(com|dev)/i);
      expect(src).not.toMatch(/trades maximum|two, three, four|take the day off|price and volume to prove/i);
      expect(src).not.toMatch(/\bS[89] \d/);
    }
  });
});

/* ---- the GajjalaBoard mount ---- */

function board(patch: Record<string, unknown>) {
  const b = { ...clone(BOARDS.bull_flag), ...patch };
  b.session = { ...b.session, refresh_sec: 0 };
  return b;
}

async function mountBoard(payload: any, variant?: 'gajjala_1m' | 'gajjala_audited', mine: any = OK) {
  stub({ board: payload, mine });
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board[data-state="loaded"]')).not.toBeNull());
  return r;
}

const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const DAY_READ = { state: 'absent', head: 'served head', caption: 'served caption', chips: [], read_date_text: 'r' };

describe('🧾 GajjalaBoard mount', () => {
  it('owner (served broker_flags) on 🚩 5-min: ONE GET with the served session date; the line sits under 🌫️ Day read', async () => {
    const today = todayEtKey();
    const b = board({ broker_flags: clone(BROKER), day_read: clone(DAY_READ) });
    b.session = { ...b.session, date: today };
    const { container } = await mountBoard(b);
    const line = await screen.findByTestId('my-day');
    expect(myGets()).toHaveLength(1);
    expect(myGets()[0].url).toContain(`?date=${today}`);
    expect(before(screen.getByTestId('day-read'), line)).toBe(true);
    expect(before(line, container.querySelector('.gg-subs')!)).toBe(true);
    expect(screen.getByTestId('my-day-text').textContent).toBe('served day text');
  });

  it('NEGATIVE: the board still on the last market day (not today ET) → ONE GET with no date (2026-11-24 refix)', async () => {
    await mountBoard(board({ broker_flags: clone(BROKER) }));        // fixture session date 2026-10-13
    await screen.findByTestId('my-day');
    expect(myGets()).toHaveLength(1);
    expect(myGets()[0].url).not.toContain('?date=');
    expect(myGets()[0].url).toMatch(/\/chart-maps\/gajjala\/my-trades$/);
  });

  it('NEGATIVE: non-owner (broker_flags null) → no fetch, no button', async () => {
    await mountBoard(board({ broker_flags: null }));
    await new Promise((r) => setTimeout(r, 0));
    expect(myGets()).toHaveLength(0);
    expect(screen.queryByTestId('my-day-open')).toBeNull();
  });

  it('NEGATIVE: an older API without broker_flags → no fetch, no button', async () => {
    const b = board({});
    delete b.broker_flags;
    await mountBoard(b);
    await new Promise((r) => setTimeout(r, 0));
    expect(myGets()).toHaveLength(0);
    expect(screen.queryByTestId('my-day')).toBeNull();
  });

  for (const v of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`NEGATIVE: ${v} with broker_flags → no fetch, no line`, async () => {
      const b = board({ broker_flags: clone(BROKER) });
      if (v === 'gajjala_1m') { b.tab = 'gajjala_1m'; b.tf = '1m'; }
      await mountBoard(b, v);
      await new Promise((r) => setTimeout(r, 0));
      expect(myGets()).toHaveLength(0);
      expect(screen.queryByTestId('my-day')).toBeNull();
    });
  }

  it('NEGATIVE: owner_only answer on the board → nothing drawn', async () => {
    await mountBoard(board({ broker_flags: clone(BROKER) }), undefined, OWNER_ONLY);
    await waitFor(() => expect(myGets()).toHaveLength(1));
    await new Promise((r) => setTimeout(r, 0));
    expect(screen.queryByTestId('my-day')).toBeNull();
  });

  it('NEGATIVE: words only — the cards and their order are the same with and without the line', async () => {
    const ids = (root: HTMLElement) => [...root.querySelectorAll('[data-testid^="gg-tile-"]')]
      .map((el) => el.getAttribute('data-testid'));
    const a = await mountBoard(board({ broker_flags: null }));
    const without = ids(a.container);
    expect(without.length).toBeGreaterThan(0);
    a.unmount();
    const b = await mountBoard(board({ broker_flags: clone(BROKER) }));
    await screen.findByTestId('my-day');
    expect(ids(b.container)).toEqual(without);
  });
});
