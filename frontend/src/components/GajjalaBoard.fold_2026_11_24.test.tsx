import '../test/ggCardWatchOff';
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import type { CurrentUser } from '../hooks/useUser';
import { GG_DIVERGENCE_SUB, GG_DIVERGING_SUB, GG_HIGH_SI_SUB, GG_TABLE_SUB } from '../lib/gajjala';
import { GG_FOLD_LS, resetGgFold } from '../lib/ggFold';
import { GG_FOLD_GLYPH } from './GgFold';
import { ggMemStorage } from '../test/ggCardWatchOff';

/* 🧹 🚩 Gajjala landing declutter — the board package (2026-11-24, spec ggclean §3.3 / §3.5 / §4 WP board tests 1–16).
 *
 * Ajay 2026-11-24: "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages
 * anymor" · "Add all of this too" · "Collapse all of this too".
 *
 * Pinned: on 🚩 only the action row (🔄 · 🧾 · ⓘ) is visible above the sub strip by default; the header text sits in the
 * closed `header` fold (segments A / B / C), mounted; faults and the answer to HIS 🔄 tap stay outside; the answer to the
 * scan ON OPEN folds [C1]; the 🚫 fault and a failed 🚫 write print as two outside nodes while closed [C4]; the ⚠️ line and
 * the open 🧾 sheet carry `order: 1` [C2]; every card sub folds its notes / panel / tally under `sub:<sub>`, opening UNDER the
 * controls row [C3]; the state lines print outside while closed. NEGATIVES: 🧪 Audited and the 1-minute page keep today's
 * DOM; a non-owner sees the toggle only; blocked storage → closed; nothing served is deleted or reworded. Every string is a
 * SENTINEL ("served …"); boards are CLONES of the goldens. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
const tracked: string[] = [];
vi.mock('../lib/usageTracker', () => ({ trackFeature: (k: string) => { tracked.push(k); } }));
vi.mock('./PatternChart', async (importOriginal) => {
  const m: any = await importOriginal();
  return { ...m, PatternChart: (props: any) => <div data-testid={`chart-${props.tile.symbol}`} /> };
});
vi.mock('./GgWatchButton', () => ({ GgWatchButton: () => <span /> }));
vi.mock('./GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('./RulesInfo', () => ({ RulesInfo: () => <span /> }));
vi.mock('./GgTimeWindow', () => ({ GgTimeWindow: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
let liveRet: { answer: any; footer: string | null } = { answer: null, footer: null };
vi.mock('../hooks/useCardLive', () => ({ useCardLive: () => liveRet }));
vi.mock('../hooks/useGgLive', () => ({ useGgLive: () => ({ quotesEvt: null, passNudge: 0, laneNudge: 0 }) }));

import GajjalaBoard from './GajjalaBoard';
import { MyDayLine } from './MyDayLine';

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

const OPEN: Record<string, any> = (onOpen as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const GUEST: CurrentUser = { ...OWNER, email: 'guest@example.com', is_admin: false };

const DAY_READ = {
  state: 'read', session: '2026-10-13', is_today: true, computed_at_et: '10:31 ET', grades_through_et: null,
  head: 'served day read head', counts: { on: 1, off: 0, read: 1, missing: 0, pending: 0 }, fold_text: 'served fold',
  chips: [], note: 'served day note', caption: 'served caption', read_date_text: 'served rule', tags: {},
};
const MY = {
  state: 'ok', date: '2026-10-13',
  my_day: { text: 'served my day text', next_text: null, quiet_text: null, footer: 'served my footer', data_text: 'served data' },
  trades: [], voided: [], aplus_today: [],
};
const SYM: string = OPEN.bull_flag.tiles[0].symbol;
const PASS_AT: string = OPEN.bull_flag.pass.at;

/** A 🚩 owner board (on-open golden clone), every header line served as a sentinel; no re-read timer. */
function gg(over: Record<string, any> = {}): any {
  const b = clone(OPEN.bull_flag);
  b.session = { ...b.session, refresh_sec: 0, badge: 'served badge', label: 'served session label' };
  b.strip = { ...b.strip, text: 'served strip text', trader_text: 'served trader line', trader_skip_text: 'served skip line' };
  b.scan = { ...b.scan, as_of_text: 'served as of line', note: null, rescan_label: 'served scan now' };
  b.push = { mode: 'live', text: 'served push line' };
  b.push_potential = { mode: 'live', text: 'served potential push line' };
  b.push_break = { mode: 'shadow', text: 'served break push line' };
  b.broker_flags = { ...b.broker_flags, text: 'served broker text', fault_text: null };
  b.day_read = clone(DAY_READ);
  b.order_note = 'served order note';
  b.list_note = 'served list note';
  b.awaiting = [{ setup: 'bull_flag', his_call: 1, text: 'served awaiting line' }];
  return { ...b, ...over };
}
const postA = (state: string, extra: Record<string, unknown> = {}) => ({
  state, latest_at: PASS_AT, eta_sec: null, poll_sec: null, wait_max_sec: null, text: `served ${state} answer`, ...extra,
});

type Call = { method: string; path: string; body: any };
let calls: Call[] = [];
let boardFor: (sub: string | null) => any = () => gg();
let boardStatus = 200;
let scanFor: (n: number) => { status: number; body: any } = () => ({ status: 200, body: postA('closed') });
let brokerAnswer: { status: number; body: any } = { status: 200, body: {} };
let mine: any = MY;
function stubFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, body: init?.body ? JSON.parse(String(init.body)) : null });
    const ok = (status: number, body: any) => ({ ok: status < 400, status, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) { const a = scanFor(posts().length); return ok(a.status, a.body); }
    if (u.pathname.endsWith('/chart-maps/gajjala/my-trades')) return ok(200, mine);
    if (u.pathname.includes('/chart-maps/gajjala/broker-flags')) return ok(brokerAnswer.status, brokerAnswer.body);
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(boardStatus, boardFor(u.searchParams.get('sub')));
    return ok(200, {});
  }));
}
const posts = () => calls.filter((c) => c.method === 'POST' && c.path.endsWith('/scan'));
const myGets = () => calls.filter((c) => c.path.endsWith('/my-trades'));
const brokerWrites = () => calls.filter((c) => c.path.includes('/broker-flags'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));

async function mount(q = 'tab=gajjala&sub=bull_flag', variant?: 'gajjala_1m' | 'gajjala_audited') {
  stubFetch();
  const r = render(
    <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
/** The owner mount that waits for the on-open POST and the 🧾 button. */
async function mountOwner(q?: string) {
  const r = await mount(q);
  await waitFor(() => expect(posts()).toHaveLength(1));
  await screen.findByTestId('my-day-open');
  await sleep(20);
  return r;
}

const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const inFold = (el: Element) => el.closest('.gg-fold-body') != null;
const shown = (el: Element | null): boolean => {
  for (let e: Element | null = el; e; e = e.parentElement) {
    if (e.hasAttribute('hidden')) return false;
    if ((e as HTMLElement).style?.display === 'none') return false;
  }
  return true;
};
/** The .gg-board children before the sub strip that are laid out (not inside a hidden body). */
const shownAbove = (c: HTMLElement) => {
  const out: Element[] = [];
  for (const el of Array.from(c.querySelector('.gg-board')!.children)) {
    if (el.classList.contains('gg-subs')) break;
    if (el.classList.contains('gg-fold-body')) {
      if (shown(el)) out.push(...Array.from(el.children));
    } else if (shown(el)) out.push(el);
  }
  return out;
};
const HIDDEN_HEAD = ['gg-strip-text', 'gg-strip-trader', 'gg-session-badge', 'gg-as-of', 'gg-broker-strip', 'day-read',
  'my-day-text', 'gg-push', 'gg-push-potential', 'gg-push-break'];

beforeEach(() => {
  resetGgFold();
  userRet = OWNER;
  boardFor = () => gg();
  boardStatus = 200;
  scanFor = () => ({ status: 200, body: postA('closed') });
  brokerAnswer = { status: 200, body: {} };
  mine = MY;
  liveRet = { answer: null, footer: null };
  tracked.length = 0;
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

describe('🧹 1–2 the header fold, owner', () => {
  it('1. default closed: 🔄 · 🧾 · ⓘ in the action row, in that order, visible; every header line mounted and hidden', async () => {
    const { container } = await mountOwner();
    const row = screen.getByTestId('gg-actions');
    const ids = ['gg-rescan', 'my-day-open', 'gg-head-toggle'];
    for (const id of ids) {
      expect(row.contains(screen.getByTestId(id)), id).toBe(true);
      expect(screen.getByTestId(id), id).toBeVisible();
    }
    expect(before(screen.getByTestId('gg-rescan'), screen.getByTestId('my-day-open'))).toBe(true);
    expect(before(screen.getByTestId('my-day-open'), screen.getByTestId('gg-head-toggle'))).toBe(true);
    expect(screen.getByTestId('gg-head-toggle').textContent).toBe(GG_FOLD_GLYPH);
    expect(screen.getByTestId('gg-head-toggle')).toHaveAttribute('aria-expanded', 'false');
    expect(screen.getByTestId('gg-head-toggle')).toHaveAttribute('aria-controls', 'gg-head-body');
    for (const id of HIDDEN_HEAD) {
      const el = screen.getByTestId(id);
      expect(inFold(el), id).toBe(true);
      expect(el, id).not.toBeVisible();
    }
    expect(screen.getByTestId('gg-rescan').closest('[data-testid="gg-strip"]')).toBeNull();
    expect(myGets()).toHaveLength(1);
    expect(container.querySelector('.gg-actions')).toBe(row);
  });

  it('2. a click opens everything, remembered as gg-fold:header = "1"; a remount reads it back; a second click closes it', async () => {
    const r = await mountOwner();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    for (const id of HIDDEN_HEAD) expect(screen.getByTestId(id), id).toBeVisible();
    expect(screen.getByTestId('gg-head-toggle')).toHaveAttribute('aria-expanded', 'true');
    expect(localStorage.getItem(`${GG_FOLD_LS}header`)).toBe('1');
    expect(tracked).toContain('gg-fold:header');
    r.unmount();
    resetGgFold();
    await mountOwner();
    for (const id of HIDDEN_HEAD) expect(screen.getByTestId(id), id).toBeVisible();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(localStorage.getItem(`${GG_FOLD_LS}header`)).toBe('0');
    for (const id of HIDDEN_HEAD) expect(screen.getByTestId(id), id).not.toBeVisible();
  });
});

describe('🧹 3 the controls work while closed', () => {
  for (const [state, tid, extra] of [
    ['closed', 'gg-scan-reused', {}],
    ['reused', 'gg-scan-reused', {}],
    ['started', 'gg-scanning', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 2 }],
  ] as const) {
    it(`a TAP answered ${state} POSTs once and prints the served line OUTSIDE every fold, visible`, async () => {
      scanFor = (n) => ({ status: 200, body: n <= 1 ? postA('closed') : postA(state, { text: `served tap ${state}`, ...extra }) });
      await mountOwner();
      fireEvent.click(screen.getByTestId('gg-rescan'));
      await waitFor(() => expect(screen.getByTestId(tid)).toHaveTextContent(`served tap ${state}`));
      expect(posts()).toHaveLength(2);
      const line = screen.getByTestId(tid);
      expect(inFold(line)).toBe(false);
      expect(line).toBeVisible();
      expect(screen.getAllByTestId(tid)).toHaveLength(1);
    });
  }

  it('🧾 opens the sheet, visible, inside no fold body; the 🚫 card toggle still writes', async () => {
    await mountOwner();
    fireEvent.click(screen.getByTestId('my-day-open'));
    const sheet = await screen.findByTestId('my-sheet');
    expect(sheet).toBeVisible();
    expect(inFold(sheet)).toBe(false);
    fireEvent.click(screen.getByTestId(`gg-broker-toggle-${SYM}`));
    await waitFor(() => expect(brokerWrites()).toHaveLength(1));
  });
});

describe('🧹 4 faults stay visible while closed', () => {
  const visibleOutside = (id: string, text?: string) => {
    const el = screen.getByTestId(id);
    if (text) expect(el.textContent).toBe(text);
    expect(inFold(el), id).toBe(false);
    expect(el, id).toBeVisible();
  };
  it('pass.stale', async () => {
    boardFor = () => { const b = gg(); b.pass = { ...b.pass, stale: true, stale_text: 'served stale line' }; return b; };
    await mountOwner();
    visibleOutside('gg-stale', 'served stale line');
  });
  it('pass.warming', async () => {
    boardFor = () => { const b = gg(); b.pass = { ...b.pass, warming: true, warming_text: 'served warming line' }; return b; };
    await mountOwner();
    visibleOutside('gg-warming', 'served warming line');
  });
  it('refused — answering the scan on open', async () => {
    scanFor = () => ({ status: 200, body: postA('refused', { text: 'served refused line' }) });
    await mountOwner();
    visibleOutside('gg-scan-refused', 'served refused line');
  });
  it('refused — answering a tap', async () => {
    scanFor = (n) => ({ status: 200, body: n <= 1 ? postA('closed') : postA('refused', { text: 'served refused line' }) });
    await mountOwner();
    fireEvent.click(screen.getByTestId('gg-rescan'));
    await screen.findByTestId('gg-scan-refused');
    visibleOutside('gg-scan-refused', 'served refused line');
  });
  it('a POST detail — answering the scan on open', async () => {
    scanFor = () => ({ status: 503, body: { detail: 'served post detail' } });
    await mountOwner();
    visibleOutside('gg-scan-err', 'served post detail');
  });
  it('a POST detail — answering a tap', async () => {
    scanFor = (n) => (n <= 1 ? { status: 200, body: postA('closed') } : { status: 503, body: { detail: 'served post detail' } });
    await mountOwner();
    fireEvent.click(screen.getByTestId('gg-rescan'));
    await screen.findByTestId('gg-scan-err');
    visibleOutside('gg-scan-err', 'served post detail');
  });
  it('scan.note (a partial pass)', async () => {
    boardFor = () => { const b = gg(); b.scan = { ...b.scan, note: 'served partial note' }; return b; };
    await mountOwner();
    visibleOutside('gg-scan-note', 'served partial note');
  });
  it('broker_flags.fault_text → gg-head-broker-fault outside (the strip itself hidden)', async () => {
    boardFor = () => { const b = gg(); b.broker_flags = { ...b.broker_flags, fault_text: 'served broker fault' }; return b; };
    await mountOwner();
    visibleOutside('gg-head-broker-fault', 'served broker fault');
    expect(screen.getByTestId('gg-broker-strip')).not.toBeVisible();
  });
  it('a failed 🚫 write detail → gg-head-broker-err outside', async () => {
    brokerAnswer = { status: 400, body: { detail: 'served write detail' } };
    await mountOwner();
    fireEvent.click(screen.getByTestId(`gg-broker-toggle-${SYM}`));
    await screen.findByTestId('gg-head-broker-err');
    visibleOutside('gg-head-broker-err', 'served write detail');
  });
  it('the board GET error', async () => {
    boardStatus = 500;
    stubFetch();
    const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}><GajjalaBoard /></MemoryRouter>);
    const e = await screen.findByTestId('gg-error');
    expect(inFold(e)).toBe(false);
    expect(e).toBeVisible();
    r.unmount();
  });
  it('[C4] fault_text AND a failed write served → BOTH outside, each once; NEGATIVE open → neither outside (the strip shows them)', async () => {
    boardFor = () => { const b = gg(); b.broker_flags = { ...b.broker_flags, editable: true, fault_text: 'served broker fault' }; return b; };
    brokerAnswer = { status: 400, body: { detail: 'served write detail' } };
    await mountOwner();
    fireEvent.click(screen.getByTestId(`gg-broker-toggle-${SYM}`));
    await screen.findByTestId('gg-head-broker-err');
    expect(screen.getAllByTestId('gg-head-broker-fault')).toHaveLength(1);
    expect(screen.getAllByTestId('gg-head-broker-err')).toHaveLength(1);
    visibleOutside('gg-head-broker-fault', 'served broker fault');
    visibleOutside('gg-head-broker-err', 'served write detail');
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(screen.queryByTestId('gg-head-broker-fault')).toBeNull();
    expect(screen.queryByTestId('gg-head-broker-err')).toBeNull();
    expect(screen.getByTestId('gg-broker-fault')).toBeVisible();
    expect(screen.getByTestId('gg-broker-err')).toBeVisible();
  });
  it('NEGATIVE: nothing served (the scan on open answered closed) → no fault node; only the action row above the sub strip', async () => {
    const { container } = await mountOwner();
    for (const id of ['gg-stale', 'gg-warming', 'gg-scan-refused', 'gg-scan-err', 'gg-scan-note', 'gg-head-broker-fault',
      'gg-head-broker-err', 'gg-error']) expect(screen.queryByTestId(id), id).toBeNull();
    expect(shownAbove(container).map((e) => e.getAttribute('data-testid'))).toEqual(['gg-actions']);
    expect(screen.getByTestId('gg-actions').textContent).toBe(`served scan now🧾 log trade${GG_FOLD_GLYPH}`);
  });
});

describe('🧹 5 the feed word', () => {
  it('NEGATIVE: a served degraded feed word is NOT visible while closed; it is once open', async () => {
    liveRet = { answer: { quotes: {}, stream: { on: false, state: 'down', word: 'served degraded word' } }, footer: 'served live footer' };
    boardFor = () => { const b = gg(); b.session = { ...b.session, refresh_sec: 300 }; return b; };
    await mountOwner();
    const w = screen.getByTestId('gg-live-feed-word');
    expect(w.textContent).toBe('served degraded word');
    expect(w).not.toBeVisible();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(screen.getByTestId('gg-live-feed-word')).toBeVisible();
  });
});

describe('🧹 6 the ⚠️ line and the sheet [C2]', () => {
  it('next_text visible while closed, once, order 1 + flex-basis 100%; the open sheet wrapper order 1; the buttons carry no order', async () => {
    mine = { ...clone(MY), my_day: { ...MY.my_day, next_text: 'served next trade warning' } };
    await mountOwner();
    const next = screen.getAllByTestId('my-day-next');
    expect(next).toHaveLength(1);
    expect(next[0].textContent).toBe('served next trade warning');
    expect(next[0]).toBeVisible();
    expect(inFold(next[0])).toBe(false);
    expect(next[0].style.order).toBe('1');
    expect(next[0].style.flexBasis).toBe('100%');
    expect(screen.getByTestId('gg-head-toggle').style.order).toBe('');
    expect(screen.getByTestId('my-day-open').style.order).toBe('');
    fireEvent.click(screen.getByTestId('my-day-open'));
    const wrap = (await screen.findByTestId('my-sheet')).parentElement as HTMLElement;
    expect(wrap.style.order).toBe('1');
    expect(wrap.style.flexBasis).toBe('100%');
  });
  it('NEGATIVE: next_text null → no ⚠️ node', async () => {
    await mountOwner();
    expect(screen.queryByTestId('my-day-next')).toBeNull();
  });
  it('NEGATIVE: textTo undefined (today\'s markup) → the sheet wrapper carries no order', async () => {
    stubFetch();
    render(<MyDayLine date="2026-10-13" />);
    fireEvent.click(await screen.findByTestId('my-day-open'));
    const wrap = (await screen.findByTestId('my-sheet')).parentElement as HTMLElement;
    expect(wrap.style.order).toBe('');
    expect(wrap.style.flexBasis).toBe('100%');
  });
});

describe('🧹 7 blocked storage', () => {
  it('NEGATIVE: getItem throws → renders closed', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => undefined, removeItem: () => undefined });
    await mountOwner();
    expect(screen.getByTestId('gg-strip')).not.toBeVisible();
    expect(screen.getByTestId('gg-actions')).toBeVisible();
  });
  it('NEGATIVE: setItem throws → still toggles for the visit', async () => {
    const m = ggMemStorage({ 'gg-card-watch': '0' });
    vi.stubGlobal('localStorage', { ...m, getItem: m.getItem, setItem: () => { throw new Error('blocked'); } });
    await mountOwner();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(screen.getByTestId('gg-strip')).toBeVisible();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(screen.getByTestId('gg-strip')).not.toBeVisible();
  });
});

describe('🧹 8 the variants keep today\'s DOM', () => {
  for (const v of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`NEGATIVE ${v}: no row, no toggle, no fold body; everything visible; 🔄 the strip's last child; today's order`, async () => {
      localStorage.setItem(`${GG_FOLD_LS}header`, '0');
      boardFor = () => {
        const b = gg();
        if (v === 'gajjala_1m') { b.tab = 'gajjala_1m'; b.tf = '1m'; }
        b.pass = { ...b.pass, stale: true, stale_text: 'served stale line', warming: true, warming_text: 'served warming line' };
        return b;
      };
      scanFor = () => ({ status: 200, body: postA('closed', { text: 'served closed answer' }) });
      const { container } = await mount('tab=gajjala&sub=bull_flag', v);
      await waitFor(() => expect(posts()).toHaveLength(1));
      const line = await screen.findByTestId('gg-scan-reused');
      expect(screen.queryByTestId('gg-actions')).toBeNull();
      expect(screen.queryByTestId('gg-head-toggle')).toBeNull();
      expect(screen.queryByTestId('gg-sub-toggle')).toBeNull();
      expect(container.querySelector('.gg-fold-body, .gg-fold-toggle, [data-testid="gg-my-day-slot"]')).toBeNull();
      const strip = screen.getByTestId('gg-strip');
      expect(strip.lastElementChild?.getAttribute('data-testid')).toBe('gg-rescan');
      for (const id of ['gg-strip-text', 'gg-as-of', 'gg-broker-strip', 'day-read', 'gg-push', 'gg-push-break', 'gg-counts', 'gg-order-note']) {
        expect(screen.getByTestId(id), id).toBeVisible();
      }
      expect(line).toBeVisible();
      const order = [strip, screen.getByTestId('gg-broker-strip'), screen.getByTestId('gg-stale'), screen.getByTestId('gg-warming'),
        screen.getByTestId('day-read'), line];
      for (let i = 1; i < order.length; i += 1) expect(before(order[i - 1], order[i]), String(i)).toBe(true);
      // the old sub order: the tally before the controls row
      expect(before(screen.getByTestId('gg-counts'), container.querySelector('.cm-phase')!)).toBe(true);
      expect(screen.queryByTestId('my-day')).toBeNull();
    });
  }
});

describe('🧹 9 a non-owner', () => {
  it('NEGATIVE: the row holds the toggle only; no 🔄, no 🧾, no POST; the fold still hides the strip and the boxes', async () => {
    userRet = GUEST;
    boardFor = () => ({ ...gg(), broker_flags: null });
    await mount();
    await sleep(40);
    const row = screen.getByTestId('gg-actions');
    expect([...row.children].map((c) => c.getAttribute('data-testid'))).toEqual(['gg-head-toggle']);
    expect(screen.queryByTestId('gg-rescan')).toBeNull();
    expect(screen.queryByTestId('my-day-open')).toBeNull();
    expect(posts()).toHaveLength(0);
    expect(myGets()).toHaveLength(0);
    for (const id of ['gg-strip-text', 'gg-as-of', 'gg-push', 'gg-push-potential', 'gg-push-break']) {
      expect(screen.getByTestId(id), id).not.toBeVisible();
    }
  });
});

/* ---- the sub folds ---- */

const HS = (over: Record<string, any> = {}) => ({
  title: 'served hs title', ask_text: 'served hs ask', counts_text: 'served hs counts', push_text: 'served hs push',
  honesty: 'served hs honesty', n: 1, faults_text: null, empty_text: 'served hs empty', chartless: [],
  ssr_new: { title: 'served ssr title', fault_text: null }, ...over,
});
function subBoard(sub: string, over: Record<string, any> = {}): any {
  const b = gg();
  b.sub = sub;
  /* the golden strip already serves every sub (📋 … 🩳 … 🏁) */
  return { ...b, ...over };
}
const T = (id: string) => screen.getByTestId(id);

describe('🧹 10–11 the 🩳 sub', () => {
  it('10. closed: the panel + tally mounted and hidden, the cards visible, ⓘ in the controls row; a click shows them all', async () => {
    boardFor = () => subBoard(GG_HIGH_SI_SUB, { high_si: HS() });
    const { container } = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const hidden = ['gg-hs-title', 'gg-hs-ask', 'gg-hs-counts', 'gg-hs-push', 'gg-ssrn', 'gg-hs-honesty', 'gg-counts', 'gg-counts-legend'];
    for (const id of hidden) {
      expect(T(id).closest('[data-testid="gg-sub-body"]'), id).not.toBeNull();
      expect(T(id), id).not.toBeVisible();
    }
    expect(T(`gg-tile-${SYM}`)).toBeVisible();
    const toggle = T('gg-sub-toggle');
    expect(container.querySelector('.cm-phase')!.contains(toggle)).toBe(true);
    expect(toggle).toHaveAttribute('aria-controls', 'gg-sub-body');
    fireEvent.click(toggle);
    // open: no hidden ancestor (the ⓘ legend is its own closed <details>, so the ancestor walk, not toBeVisible)
    for (const id of hidden) expect(shown(T(id)), id).toBe(true);
    expect(T('gg-hs-title')).toBeVisible();
    expect(localStorage.getItem(`${GG_FOLD_LS}sub:${GG_HIGH_SI_SUB}`)).toBe('1');
    // NEGATIVE: the header stays closed
    expect(T('gg-strip')).not.toBeVisible();
    expect(localStorage.getItem(`${GG_FOLD_LS}header`)).toBeNull();
  });

  it('10 [C3] the NEW order on 🚩, on purpose (2026-11-24, his call §7 #13): awaiting → controls row → body → first card', async () => {
    boardFor = () => subBoard(GG_HIGH_SI_SUB, { high_si: HS() });
    const { container } = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const seq = [T('gg-awaiting'), T('gg-sub-toggle'), T('gg-sub-body'), T(`gg-tile-${SYM}`)];
    for (let i = 1; i < seq.length; i += 1) expect(before(seq[i - 1], seq[i]), String(i)).toBe(true);
    expect(before(container.querySelector('.cm-phase')!, T('gg-counts'))).toBe(true);
  });

  it('10 NEGATIVE: opening 🩳 leaves bull_flag\'s fold closed', async () => {
    localStorage.setItem(`${GG_FOLD_LS}sub:${GG_HIGH_SI_SUB}`, '1');
    boardFor = (sub) => (sub === GG_HIGH_SI_SUB ? subBoard(GG_HIGH_SI_SUB, { high_si: HS() }) : subBoard('bull_flag'));
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(T('gg-hs-title')).toBeVisible();
    fireEvent.click(T('gg-sub-bull_flag'));
    await screen.findByTestId('gg-order-note');
    await waitFor(() => expect(screen.queryByTestId('gg-hs')).toBeNull());
    expect(T('gg-order-note')).not.toBeVisible();
    expect(T('gg-counts')).not.toBeVisible();
  });

  it('11. state lines while closed: chartless, faults, the SSR fault, in gg-substate; NEGATIVE open → no gg-substate', async () => {
    boardFor = () => subBoard(GG_HIGH_SI_SUB, { high_si: HS({
      faults_text: 'served hs faults', ssr_new: { title: 'served ssr title', fault_text: 'served ssr fault' },
      chartless: [{ symbol: 'ZZZ', text: 'served ZZZ listed', state_label: 'served label', href: '/chart-maps?tab=gajjala&focus=ZZZ' }],
    }) });
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    const st = T('gg-substate');
    expect(st).toBeVisible();
    expect(within(st).getByTestId('gg-substate-chartless-ZZZ').textContent).toBe('served ZZZ listed');
    expect(within(st).getByTestId('gg-substate-faults').textContent).toBe('served hs faults');
    expect(within(st).getByTestId('gg-substate-fault-ssr').textContent).toBe('served ssr fault');
    expect(before(T('gg-sub-body'), st)).toBe(true);
    fireEvent.click(T('gg-sub-toggle'));
    expect(screen.queryByTestId('gg-substate')).toBeNull();
    expect(T('gg-hs')).toBeVisible();
  });

  it('11. the empty line while closed (n 0, nothing chartless)', async () => {
    boardFor = () => subBoard(GG_HIGH_SI_SUB, { high_si: HS({ n: 0 }), tiles: [] });
    await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    expect(T('gg-substate-empty').textContent).toBe('served hs empty');
    expect(T('gg-substate-empty')).toBeVisible();
  });
});

describe('🧹 12 every other sub', () => {
  it('🧨 and 🌱: panel hidden in gg-sub-body, state lines outside, cards visible', async () => {
    const dv = { title: 'served dv title', n_today: 1, faults_text: 'served dv faults', chartless: [], empty_text: 'served dv empty' };
    const dg = { title: 'served dg title', n: 1, faults_text: 'served dg faults', chartless: [], empty_text: 'served dg empty' };
    boardFor = (sub) => (sub === GG_DIVERGING_SUB ? subBoard(GG_DIVERGING_SUB, { diverging: dg }) : subBoard(GG_DIVERGENCE_SUB, { divergence: dv }));
    await mount(`tab=gajjala&sub=${GG_DIVERGENCE_SUB}`);
    expect(T('gg-dv-title')).not.toBeVisible();
    expect(T('gg-dv').closest('[data-testid="gg-sub-body"]')).not.toBeNull();
    expect(T('gg-substate-faults').textContent).toBe('served dv faults');
    expect(T(`gg-tile-${SYM}`)).toBeVisible();
    fireEvent.click(T(`gg-sub-${GG_DIVERGING_SUB}`));
    await screen.findByTestId('gg-dg');
    expect(T('gg-dg-title')).not.toBeVisible();
    expect(T('gg-substate-faults').textContent).toBe('served dg faults');
    expect(T(`gg-tile-${SYM}`)).toBeVisible();
  });

  it('a setup sub: order note + tally hidden, the cards visible; 🎯, awaiting, empty, unchecked stay visible', async () => {
    boardFor = () => subBoard('bull_flag', { postmarket: { unchecked_text: 'served unchecked line' } });
    await mount('tab=gajjala&sub=bull_flag');
    for (const id of ['gg-order-note', 'gg-list-note', 'gg-counts']) expect(T(id), id).not.toBeVisible();
    for (const id of ['gg-aplus', 'gg-awaiting', 'gg-unchecked', `gg-tile-${SYM}`]) {
      expect(T(id), id).toBeVisible();
      expect(inFold(T(id)), id).toBe(false);
    }
  });

  it('NEGATIVE: an empty card sub keeps its served empty note visible', async () => {
    boardFor = () => subBoard('bull_flag', { tiles: [], empty_note: 'served empty note' });
    await mount('tab=gajjala&sub=bull_flag');
    expect(T('gg-empty')).toBeVisible();
    expect(T('gg-counts')).not.toBeVisible();
  });

  it('☀️: the Day-2 note hidden, title + rows visible', async () => {
    boardFor = () => subBoard('premarket', {
      day2: { title: 'served day2 title', note: 'served day2 note', rows: [{ symbol: 'DDD', text: 'served DDD row', href: null }] },
    });
    await mount('tab=gajjala&sub=premarket');
    expect(T('gg-day2-note')).not.toBeVisible();
    expect(T('gg-day2-note').closest('[data-testid="gg-sub-body-day2"]')).not.toBeNull();
    expect(T('gg-day2-title')).toBeVisible();
    expect(T('gg-day2-row-DDD')).toBeVisible();
  });

  it('🔝 the Focus head hidden, the divider and the cards visible', async () => {
    boardFor = () => {
      const b = subBoard('bull_flag', { focus: { text: 'served focus head' } });
      b.tiles = b.tiles.map((t: any) => ({ ...t, focus: true }));
      return b;
    };
    await mount('tab=gajjala&sub=bull_flag');
    expect(T('gg-focus-head')).not.toBeVisible();
    expect(T('gg-focus-divider')).toBeVisible();
    expect(T(`gg-tile-${SYM}`)).toBeVisible();
  });

  it('📋: the order text hidden in gg-sub-body-table, the title visible, ⓘ beside the title', async () => {
    boardFor = () => subBoard(GG_TABLE_SUB, {
      tiles: [], table: { title: 'served table title', heads: [], rows: [], order_text: 'served table order', honesty: 'served table honesty' },
    });
    await mount(`tab=gajjala&sub=${GG_TABLE_SUB}`);
    expect(T('gg-all-order')).not.toBeVisible();
    expect(T('gg-all-title')).toBeVisible();
    expect(T('gg-all-head').contains(T('gg-sub-toggle'))).toBe(true);
    fireEvent.click(T('gg-sub-toggle'));
    expect(T('gg-all-order')).toBeVisible();
  });

  for (const sub of ['track_record', 'playbook']) {
    it(`NEGATIVE ${sub}: no gg-sub-toggle, no sub fold body`, async () => {
      boardFor = () => subBoard(sub, { tiles: [] });
      const { container } = await mount(`tab=gajjala&sub=${sub}`);
      expect(screen.queryByTestId('gg-sub-toggle')).toBeNull();
      expect(container.querySelector('[data-fold^="sub:"]')).toBeNull();
      expect(T('gg-order-note')).toBeVisible();
    });
  }
});

describe('🧹 13 nothing deleted, nothing reworded (constraint a)', () => {
  it('NEGATIVE: every served sentinel string is in the DOM while both folds are closed', async () => {
    boardFor = () => subBoard(GG_HIGH_SI_SUB, { high_si: HS() });
    scanFor = () => ({ status: 200, body: postA('closed', { text: 'served closed on open answer' }) });
    const { container } = await mount(`tab=gajjala&sub=${GG_HIGH_SI_SUB}`);
    await screen.findByTestId('my-day-text');
    await screen.findByTestId('gg-scan-reused');
    const all = container.textContent || '';
    for (const s of ['served strip text', 'served trader line', 'served skip line', 'served badge', 'served session label',
      'served as of line', 'served broker text', 'served day read head', 'served my day text', 'served my footer',
      'served closed on open answer', 'served push line', 'served potential push line', 'served break push line',
      'served order note', 'served list note', 'served awaiting line', 'served hs title', 'served hs ask', 'served hs counts',
      'served hs push', 'served hs honesty', 'served ssr title']) expect(all, s).toContain(s);
    expect(T('gg-head-toggle')).toHaveAttribute('aria-expanded', 'false');
    expect(T('gg-sub-toggle')).toHaveAttribute('aria-expanded', 'false');
  });
});

describe('🧹 14 MyDayLine bare mode', () => {
  it('textTo: the sentence lands in the slot, the button stays in the row, ONE GET (no remount when the slot appears)', async () => {
    await mountOwner();
    const slot = T('gg-my-day-slot');
    expect(slot.contains(T('my-day-text'))).toBe(true);
    expect(T('gg-actions').contains(T('my-day-open'))).toBe(true);
    expect(T('my-day').style.display).toBe('contents');
    expect(T('my-day').className).toContain('gg-my-day--bare');
    expect(myGets()).toHaveLength(1);
  });
  it('NEGATIVE: textTo null → the button, no sentence anywhere', async () => {
    stubFetch();
    render(<MyDayLine date="2026-10-13" textTo={null} />);
    await screen.findByTestId('my-day-open');
    expect(screen.queryByTestId('my-day-text')).toBeNull();
  });
  it('NEGATIVE: textTo undefined → today\'s markup (the box, the sentence inside the section)', async () => {
    stubFetch();
    render(<MyDayLine date="2026-10-13" />);
    await screen.findByTestId('my-day-open');
    expect(T('my-day').contains(T('my-day-text'))).toBe(true);
    expect(T('my-day').style.display).toBe('flex');
    expect(T('my-day').className).toBe('cm-note gg-my-day');
  });
});

describe('🧹 16 the scan on open [C1]', () => {
  it('closed on open → folded in segment B, the 🔄 title the served closed line; a TAP closed → outside, once; open → still once', async () => {
    boardFor = () => { const b = gg(); b.scan = { ...b.scan, state: 'closed', as_of_text: 'served closed as of' }; return b; };
    scanFor = (n) => ({ status: 200, body: postA('closed', { text: n <= 1 ? 'served on open closed' : 'served tap closed' }) });
    await mountOwner();
    const onOpenLine = await screen.findByTestId('gg-scan-reused');
    expect(onOpenLine.textContent).toBe('served on open closed');
    expect(onOpenLine.closest('[data-testid="gg-head-body-b"]')).not.toBeNull();
    expect(onOpenLine).not.toBeVisible();
    expect(T('gg-rescan')).toHaveAttribute('title', 'served closed as of');
    fireEvent.click(T('gg-rescan'));
    await waitFor(() => expect(T('gg-scan-reused')).toHaveTextContent('served tap closed'));
    expect(screen.getAllByTestId('gg-scan-reused')).toHaveLength(1);
    expect(inFold(T('gg-scan-reused'))).toBe(false);
    expect(T('gg-scan-reused')).toBeVisible();
    fireEvent.click(T('gg-head-toggle'));
    expect(screen.getAllByTestId('gg-scan-reused')).toHaveLength(1);
  });

  it('started on open → gg-scanning in segment B, hidden; the 🔄 button carries data-scanning', async () => {
    scanFor = () => ({ status: 200, body: postA('started', { eta_sec: 0.05, poll_sec: 0.05, wait_max_sec: 2 }) });
    await mountOwner();
    const s = await screen.findByTestId('gg-scanning');
    expect(s.closest('[data-testid="gg-head-body-b"]')).not.toBeNull();
    expect(s).not.toBeVisible();
    expect(T('gg-rescan')).toHaveAttribute('data-scanning', 'true');
  });

  it('NEGATIVE: refused on open → gg-scan-refused visible; a non-ok detail on open → gg-scan-err visible', async () => {
    scanFor = () => ({ status: 200, body: postA('refused', { text: 'served refused on open' }) });
    const a = await mountOwner();
    expect(T('gg-scan-refused')).toBeVisible();
    a.unmount();
    resetGgFold();
    scanFor = () => ({ status: 500, body: { detail: 'served detail on open' } });
    await mountOwner();
    expect(T('gg-scan-err')).toBeVisible();
  });

  it('NEGATIVE: an unknown state "error" with text on open → the line stays OUTSIDE, visible', async () => {
    scanFor = () => ({ status: 200, body: postA('error', { text: 'served unknown state line' }) });
    await mountOwner();
    const line = await screen.findByTestId('gg-scan-reused');
    expect(line.textContent).toBe('served unknown state line');
    expect(inFold(line)).toBe(false);
    expect(line).toBeVisible();
  });
});

describe('🧹 source guards', () => {
  it('the board types no new word and gates the header fold on the 5-min page only', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const code = src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:])\/\/[^\n]*/g, '$1');
    expect(code).toMatch(/const foldOn = vkey === 'gajjala';/);
    expect(code).toMatch(/const headKey = foldOn \? GG_FOLD_HEADER : null;/);
    expect(code).not.toMatch(/'(started|waiting|reused|closed)'\]/);   // the state list lives in lib/ggFold
    expect(code).toMatch(/setScanFromOpen\(viaOpen && ggFoldScanAnswer\(resp\.state\)\);/);
    expect((code.match(/<GgHighSiPanel /g) || [])).toHaveLength(1);
    expect((code.match(/data-testid="gg-scanning"/g) || [])).toHaveLength(1);
    expect((code.match(/data-testid="gg-rescan"/g) || [])).toHaveLength(1);
    // the faults are never children of a fold body: each sits after the segment it follows closes
    for (const id of ['gg-stale', 'gg-warming', 'gg-scan-refused', 'gg-scan-err', 'gg-scan-note', 'gg-head-broker-fault', 'gg-head-broker-err']) {
      const at = code.indexOf(`data-testid="${id}"`);
      expect(at, id).toBeGreaterThan(0);
      const open = code.lastIndexOf('<GgFoldBody', at);
      const close = code.lastIndexOf('</GgFoldBody>', at);
      expect(close, id).toBeGreaterThan(open);
    }
    const md = await readSource('src/components/MyDayLine.tsx');
    expect(md).not.toMatch(/bounce|@[a-z0-9-]+\.(com|dev)/i);
  });
});
