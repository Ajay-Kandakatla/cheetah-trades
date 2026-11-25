import '../test/ggCardWatchOff';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import type { CurrentUser } from '../hooks/useUser';
import { resetGgFold } from '../lib/ggFold';
import { GG_FOLD_GLYPH } from './GgFold';

/* 💧 Volume dried — the served count line on the 🚩 board (2026-11-24, voldry spec §3.9 / WP fe).
 *
 * Ajay 2026-11-24: "Can you track something for me how many times have the stocks bumped right after volume dried up.. …
 * Can you send me notification of volume dried please.."
 *
 * Pinned: the served `push_vol_dried.text` prints VERBATIM in segment C (`gg-head-body-c`) right after ⚡, inside the closed
 * ⓘ header fold — hidden while closed, visible after the ⓘ tap. The landing stays 🔄 · 🧾 · ⓘ (STANDING declutter rule).
 * NEGATIVES: undefined / null / '' / whitespace / a non-string / a text-less block → no node; a 🧪 / 1-minute board without
 * the key → no node; the node is never outside `.gg-fold-body`; the b-word never appears. Strings are SENTINELS except the
 * one count-shaped line, which must print unchanged. Boards are CLONES of the on-open golden. */

let userRet: CurrentUser | null = null;
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: userRet, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: () => {} }));
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
vi.mock('../hooks/useCardLive', () => ({ useCardLive: () => ({ answer: null, footer: null }) }));
vi.mock('../hooks/useGgLive', () => ({ useGgLive: () => ({ quotesEvt: null, passNudge: 0, laneNudge: 0 }) }));

import GajjalaBoard from './GajjalaBoard';

const OPEN: Record<string, any> = (onOpen as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));
const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};
const MY = {
  state: 'ok', date: '2026-10-13',
  my_day: { text: 'served my day text', next_text: null, quiet_text: null, footer: 'served my footer', data_text: 'served data' },
  trades: [], voided: [], aplus_today: [],
};
const PASS_AT: string = OPEN.bull_flag.pass.at;
/* A count-shaped served line (the be-engine words are its own; the FE prints whatever is served, unchanged). */
const COUNT_LINE = '💧 7 recorded · 5 rang · 3 triggered · 2 hit +1R · 1 stop-first — last 10 sessions · UNMEASURED';
const VD = 'gg-push-vol-dried';

/** A 🚩 owner board (on-open golden clone); `vd` = the served push_vol_dried value ('omit' → no key at all). */
function gg(...args: any[]): any {
  const vd = args.length ? args[0] : { mode: 'live', text: COUNT_LINE };   /* an explicit undefined stays undefined */
  const b = clone(OPEN.bull_flag);
  b.session = { ...b.session, refresh_sec: 0 };
  b.scan = { ...b.scan, note: null, rescan_label: 'served scan now' };
  b.push = { mode: 'live', text: 'served push line' };
  b.push_potential = { mode: 'live', text: 'served potential push line' };
  b.push_break = { mode: 'live', text: 'served break push line' };
  if (vd === 'omit') delete b.push_vol_dried;
  else b.push_vol_dried = vd;
  return b;
}

let calls: { method: string; path: string }[] = [];
let boardFor: () => any = () => gg();
function stubFetch() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname });
    const ok = (status: number, body: any) => ({ ok: status < 400, status, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) {
      return ok(200, { state: 'closed', latest_at: PASS_AT, eta_sec: null, poll_sec: null, wait_max_sec: null, text: 'served closed answer' });
    }
    if (u.pathname.endsWith('/chart-maps/gajjala/my-trades')) return ok(200, MY);
    if (u.pathname.includes('/chart-maps/gajjala/broker-flags')) return ok(200, {});
    if (/\/chart-maps\/gajjala(-1m|-audited)?$/.test(u.pathname)) return ok(200, boardFor());
    return ok(200, {});
  }));
}
const posts = () => calls.filter((c) => c.method === 'POST' && c.path.endsWith('/scan'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));

async function mount(variant?: 'gajjala_1m' | 'gajjala_audited') {
  stubFetch();
  const r = render(
    <MemoryRouter initialEntries={['/chart-maps?tab=gajjala&sub=bull_flag']}>
      {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
    </MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  return r;
}
async function mountOwner() {
  const r = await mount();
  await waitFor(() => expect(posts()).toHaveLength(1));
  await screen.findByTestId('my-day-open');
  await sleep(20);
  return r;
}
const inFold = (el: Element) => el.closest('.gg-fold-body') != null;
const before = (a: Element, b: Element) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const shown = (el: Element | null): boolean => {
  for (let e: Element | null = el; e; e = e.parentElement) {
    if (e.hasAttribute('hidden')) return false;
    if ((e as HTMLElement).style?.display === 'none') return false;
  }
  return true;
};
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

beforeEach(() => { resetGgFold(); userRet = OWNER; boardFor = () => gg(); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

describe('💧 the served count line in segment C', () => {
  it('prints verbatim inside gg-head-body-c, right after ⚡; hidden while the fold is closed, visible after the ⓘ tap', async () => {
    await mountOwner();
    const el = screen.getByTestId(VD);
    expect(el.textContent).toBe(COUNT_LINE);
    expect(el.closest('[data-testid="gg-head-body-c"]')).not.toBeNull();
    expect(inFold(el)).toBe(true);
    expect(el.classList.contains('gg-push-vol-dried')).toBe(true);
    // right after ⚡: its previous sibling is the break line
    expect(el.previousElementSibling?.getAttribute('data-testid')).toBe('gg-push-break');
    expect(before(screen.getByTestId('gg-push-break'), el)).toBe(true);
    expect(el).not.toBeVisible();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(screen.getByTestId(VD)).toBeVisible();
    expect(screen.getByTestId(VD).textContent).toBe(COUNT_LINE);
    expect(screen.getAllByTestId(VD)).toHaveLength(1);
  });

  it('a "N recorded · M rang · … hit +1R …" text prints unchanged, digits and all', async () => {
    const t = '💧 12 recorded · 9 rang · 4 triggered · 3 hit +1R · 2 stop-first — 1 not graded yet · UNMEASURED';
    boardFor = () => gg({ mode: 'off', text: t });
    await mountOwner();
    expect(screen.getByTestId(VD).textContent).toBe(t);
  });

  it('NEGATIVE: the landing stays 🔄 · 🧾 · ⓘ with the line served (nothing above the sub strip but the action row)', async () => {
    const { container } = await mountOwner();
    expect(shownAbove(container).map((e) => e.getAttribute('data-testid'))).toEqual(['gg-actions']);
    expect(screen.getByTestId('gg-actions').textContent).toBe(`served scan now🧾 log trade${GG_FOLD_GLYPH}`);
    expect(screen.getByTestId('gg-actions').textContent).not.toContain('💧');
  });

  it('NEGATIVE: the node is never outside .gg-fold-body — closed and open', async () => {
    const { container } = await mountOwner();
    const all = () => Array.from(container.querySelectorAll(`[data-testid="${VD}"], .gg-push-vol-dried`));
    expect(all()).toHaveLength(1);
    for (const n of all()) expect(inFold(n)).toBe(true);
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(all()).toHaveLength(1);
    for (const n of all()) expect(inFold(n)).toBe(true);
  });

  for (const [name, vd] of [
    ['the key absent', 'omit'],
    ['undefined', undefined],
    ['null', null],
    ['an empty text', { mode: 'live', text: '' }],
    ['a whitespace text', { mode: 'live', text: '   ' }],
    ['a non-string text', { mode: 'live', text: 7 }],
    ['a text-less block', { mode: 'live' }],
  ] as const) {
    it(`NEGATIVE: ${name} → no node (the ⚡ line still prints)`, async () => {
      boardFor = () => gg(vd);
      const { container } = await mountOwner();
      expect(screen.queryByTestId(VD)).toBeNull();
      expect(container.querySelector('.gg-push-vol-dried')).toBeNull();
      expect(screen.getByTestId('gg-push-break')).toBeInTheDocument();
    });
  }

  for (const v of ['gajjala_1m', 'gajjala_audited'] as const) {
    it(`NEGATIVE ${v}: a board without the key → no node`, async () => {
      boardFor = () => { const b = gg('omit'); if (v === 'gajjala_1m') { b.tab = 'gajjala_1m'; b.tf = '1m'; } return b; };
      const { container } = await mount(v);
      await sleep(20);
      expect(screen.queryByTestId(VD)).toBeNull();
      expect(container.querySelector('.gg-push-vol-dried')).toBeNull();
    });
  }

  it('NEGATIVE: the b-word never appears in the 💧 line or segment C', async () => {
    const { container } = await mountOwner();
    fireEvent.click(screen.getByTestId('gg-head-toggle'));
    expect(/bounc/i.test(screen.getByTestId(VD).textContent || '')).toBe(false);
    const segC = container.querySelector('[data-testid="gg-head-body-c"]')!;
    expect(/bounc/i.test(segC.textContent || '')).toBe(false);
  });
});

describe('💧 producer named in the source comments (refix 2026-11-24)', () => {
  it('names the served producer vol_dried.count_block via tab.push_vol_dried_block, in both files', async () => {
    const board = (await import('./GajjalaBoard.tsx?raw')).default as string;
    const lib = (await import('../lib/gajjala.ts?raw')).default as string;
    for (const src of [board, lib]) {
      expect(src).toContain('vol_dried.count_block()');
      expect(src).toContain('tab.push_vol_dried_block');
    }
  });

  it('never names the non-existent vol_dried.status()', async () => {
    const board = (await import('./GajjalaBoard.tsx?raw')).default as string;
    const lib = (await import('../lib/gajjala.ts?raw')).default as string;
    expect(board.includes('vol_dried.status(')).toBe(false);
    expect(lib.includes('vol_dried.status(')).toBe(false);
  });
});
