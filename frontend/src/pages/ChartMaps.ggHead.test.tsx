/* 🧹 🚩 landing declutter — the Chart Maps page rows on 🚩 (2026-11-24, spec ggclean §3.4 / WP `page`).
 *
 * Ajay 2026-11-24, three messages with screenshots:
 *   "Hide all of this nouce besides the scan button and log trade button no explantions on the landing pages anymor"
 *   "Add all of this too"
 *   "Collapse all of this too"
 *
 * The page builds the WHY blurb, the house ℹ️ Rules pair (🧨 explosive + 🩳 short interest) and the 🎯 Enterable bar
 * ONCE; on tab === 'gajjala' they travel through GgHeadPageContext into the REAL GajjalaBoard, which prints them first
 * inside its closed ⓘ header fold. Pinned here, on the real page + the real board (fetch stubbed):
 *  - default: the three rows are in the DOM, inside `gg-head-body`, not visible; the only visible text between the tab
 *    strip and the sub strip is the served scan label, "🧾 log trade" and the ⓘ glyph — the scan on open is stubbed as
 *    answered `closed`, and that answer is folded too [C1];
 *  - one tap on ⓘ shows them, in the order blurb → ℹ️ ×2 → 🎯 row → the board strip; `gg-fold:header` = '1';
 *  - 🎯 Enterable still writes / drops `?show=all`, and hides no 🚩 card either way.
 * NEGATIVES: zones / bonde / 🧪 Audited / the retired 1-min page keep the three rows in place, visible, in no fold body,
 * no ⓘ toggle — a stored open header key changes nothing there; a throwing storage read → the page renders, fold
 * closed; a stubbed board (no consumer of the context) → no crash, the rows simply absent on 🚩. */
import { act, cleanup, fireEvent, render, waitFor } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import hand from '../components/__fixtures__/gajjala_board_2026_10_13.json';
import { GG_FOLD_GLYPH } from '../components/GgFold';
import { GG_FOLD_HEADER, GG_FOLD_LS, resetGgFold } from '../lib/ggFold';
import { _resetRulesInfoCache } from '../hooks/useRulesInfo';
import { _resetGgLiteCache } from '../components/GgEntryTape';

const USER = vi.hoisted(() => ({ user: null as null | Record<string, unknown> }));
const GG = vi.hoisted(() => ({ stub: false }));
vi.mock('../hooks/useUser', () => ({ useCurrentUser: () => ({ user: USER.user, loading: false }) }));
vi.mock('../lib/usageTracker', () => ({ trackFeature: vi.fn() }));
vi.mock('../hooks/useMyFeatures', () => ({
  useMyFeatures: () => ({ loaded: true, features: new Set(['chart-maps', 'catalysts']), catalog: [], email: null }),
}));
vi.mock('../components/PatternChart', () => ({ PatternChart: (p: any) => <div data-testid={`chart-${p.tile?.symbol}`} /> }));
vi.mock('../components/GrowthChip', () => ({ GrowthChip: () => <span /> }));
vi.mock('../components/ShortInterestChip', () => ({ ShortInterestChip: () => <span /> }));
vi.mock('../components/ExplosiveChip', () => ({ ExplosiveChip: () => <span /> }));
vi.mock('../components/EnterableChip', () => ({ EnterableChip: () => <span /> }));
vi.mock('../hooks/useBounceRoom', () => ({
  useBounceRoom: () => ({ map: new Map(), payload: null, loading: false, error: null, pending: 0 }),
}));
vi.mock('../components/GajjalaWatchBoard', () => ({ default: () => <div data-testid="ggw-stub" /> }));
vi.mock('../components/LukBoard', () => ({ default: () => <div data-testid="luk-stub" /> }));
vi.mock('../components/LongTermBoard', () => ({ default: () => <div data-testid="lt-stub" /> }));
vi.mock('../components/BondeBoard', () => ({ default: () => <div data-testid="bonde-stub" /> }));
/* The REAL board, unless a case flips GG.stub (the "stubbed board" negative). */
vi.mock('../components/GajjalaBoard', async (orig) => {
  const real: any = await orig();
  const Real = real.default;
  return { ...real, default: (p: any) => (GG.stub ? <div data-testid="gg-stub" /> : <Real {...p} />) };
});

import ChartMaps from './ChartMaps';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const HAND: Record<string, any> = (hand as any).boards;

const OWNER = { email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true, is_primary_admin: true };

/* Test data only — every string below is a sentinel, printed verbatim by the components under test. */
const SCAN = { state: 'idle', on_demand: false, as_of_text: 'served as-of line', rescan_label: 'served rescan',
  rescan_title: 'served title' };
const BROKER = { add_label: 'add', add_placeholder: 'ticker', broker: 'Fidelity', editable: false, empty_text: null,
  fault_text: null, remove_title: 'x', symbols: [], text: 'served tag', toggle: '\u{1F6AB}' };
const MINE = {
  state: 'ok', date: '2026-10-13',
  my_day: { text: 'served day text', next_text: null, quiet_text: null, footer: null, data_text: null },
  trades: [], voided: [], totals: { n: 0, missed: 0, no_aplus: 0, kept_aplus: 0, warned_and_took: 0 },
  week: { n: 0, text: 'served week' }, tally_10d: {}, aplus_today: [],
};
const RULES = { sections: {
  explosive: { title: 'served explosive', emoji: '\u{1F9E8}', picks: ['p'], stops: [], alerts: [], note: 'n' },
  short_interest: { title: 'served si', emoji: '\u{1FA73}', picks: ['p'], stops: [], alerts: [], note: 'n' },
  enterable: { title: 'served enterable', emoji: '\u{1F3AF}', picks: ['p'], stops: [], alerts: [], note: 'n' },
  in_demand: { title: 'served in demand', emoji: '\u{1F7E2}', picks: ['p'], stops: [], alerts: [], note: 'n' },
} };
const SCAN_CLOSED = { state: 'closed', latest_at: null, text: 'served closed line' };
const PAGE_BOARD = { tab: 'zones', count: 0, matched: 0, scanned: 100, tiles: [], disclaimer: 'Study board.' };

/** 🚩 board (and its 🧪 / 1-min copies): the 2026-10-13 hand fixture, no timers, the owner's scan + 🚫 blocks. */
function ggBoard(tab = 'gajjala'): any {
  const b = clone(HAND.bull_flag);
  b.tab = tab;
  b.session = { ...b.session, refresh_sec: 0, first15: false };
  b.scan = { ...SCAN };
  b.broker_flags = clone(BROKER);
  return b;
}

/** A Map-backed localStorage (this jsdom has none); `getThrows` = blocked storage. */
let LS = new Map<string, string>();
function fakeStorage(opts: { getThrows?: boolean } = {}) {
  return {
    getItem: (k: string) => { if (opts.getThrows) throw new Error('blocked'); return LS.has(k) ? (LS.get(k) as string) : null; },
    setItem: (k: string, v: string) => { LS.set(k, String(v)); },
    removeItem: (k: string) => { LS.delete(k); },
    clear: () => { LS.clear(); },
    key: (i: number) => Array.from(LS.keys())[i] ?? null,
    get length() { return LS.size; },
  };
}

type Call = { method: string; path: string };
let calls: Call[] = [];
function stub() {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname });
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    const p = u.pathname;
    if (p.endsWith('/supply-demand/rules')) return ok(RULES);
    if (p.endsWith('/my-trades')) return ok(MINE);
    if (p.endsWith('/scan')) return ok(SCAN_CLOSED);
    if (p.endsWith('/entry-tape')) return ok({});
    if (p.endsWith('/chart-maps/gajjala-audited')) return ok(ggBoard('gajjala_audited'));
    if (p.endsWith('/chart-maps/gajjala-1m')) return ok(ggBoard('gajjala_1m'));
    if (p.endsWith('/chart-maps/gajjala')) return ok(ggBoard());
    if (p.endsWith('/chart-maps')) return ok(PAGE_BOARD);
    return ok({});
  }));
}

function Loc() {
  const l = useLocation();
  return <output data-testid="loc">{l.search}</output>;
}
const page = (q: string) => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}><Loc /><ChartMaps /></MemoryRouter>);
const settle = (ms = 30) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
const byId = (c: HTMLElement, id: string) => c.querySelector(`[data-testid="${id}"]`) as HTMLElement | null;
const allById = (c: HTMLElement, id: string) => Array.from(c.querySelectorAll(`[data-testid="${id}"]`)) as HTMLElement[];
const shown = (el: Element) => !el.closest('[hidden]');
/** The blurb is a StudyNote `<details>`: its own visibility is its `<summary>` (jest-dom reads a closed details as hidden). */
const blurbHead = (c: HTMLElement) => { const b = byId(c, 'cm-blurb')!; return (b.querySelector('summary') ?? b) as HTMLElement; };
const before = (a: Node, b: Node) => !!(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);
const checkbox = (c: HTMLElement) => c.querySelector('.cm-enterable-bar input[type="checkbox"]') as HTMLInputElement | null;
const tileIds = (c: HTMLElement) => Array.from(c.querySelectorAll('[data-testid^="gg-tile-"]'))
  .map((e) => e.getAttribute('data-testid') as string).filter((t) => !t.startsWith('gg-tile-link-')).sort();

/** 🚩 loaded: the board, the 🧾 button (its own GET) and the answer to the scan on open have all landed. */
async function ggLoaded(c: HTMLElement) {
  await waitFor(() => expect(c.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
  await waitFor(() => expect(byId(c, 'my-day-open')).not.toBeNull());
  await waitFor(() => expect(byId(c, 'gg-scan-reused')).not.toBeNull());
  await waitFor(() => expect(c.querySelectorAll('[data-testid="rules-info-pill"]').length).toBe(3));
  await settle();
}

/** Every non-blank text node between the tab strip and the sub strip that is not inside a `[hidden]` subtree. */
function visibleTextBetweenTabsAndSubs(c: HTMLElement): string[] {
  const bar = byId(c, 'cm-tabs-bar')!;
  const subs = c.querySelector('.gg-subs')!;
  expect(bar).not.toBeNull();
  expect(subs).not.toBeNull();
  const out: string[] = [];
  const w = document.createTreeWalker(c, NodeFilter.SHOW_TEXT);
  for (let n = w.nextNode(); n; n = w.nextNode()) {
    if (bar.contains(n) || subs.contains(n)) continue;
    if (!before(bar, n) || !before(n, subs)) continue;
    if (n.parentElement && !shown(n.parentElement)) continue;
    const t = (n.textContent || '').trim();
    if (t) out.push(t);
  }
  return out;
}

beforeEach(() => {
  LS = new Map();
  vi.stubGlobal('localStorage', fakeStorage());
  resetGgFold();
  _resetRulesInfoCache();
  _resetGgLiteCache();
  USER.user = OWNER;
  GG.stub = false;
  stub();
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  LS = new Map();
  resetGgFold();
  USER.user = null;
  GG.stub = false;
});

describe('🚩 the page rows ride the board’s closed ⓘ header fold (2026-11-24)', () => {
  it('default: the blurb, the three ℹ️ Rules pills and the 🎯 checkbox are in the DOM, inside gg-head-body, not visible', async () => {
    const { container } = page('tab=gajjala');
    await ggLoaded(container);
    const body = byId(container, 'gg-head-body')!;
    expect(body).not.toBeNull();
    expect(body.hasAttribute('hidden')).toBe(true);
    const blurb = byId(container, 'cm-blurb')!;
    expect(blurb).not.toBeNull();
    expect(body.contains(blurb)).toBe(true);
    expect(blurbHead(container)).not.toBeVisible();
    const pills = allById(container, 'rules-info-pill');
    expect(pills).toHaveLength(3);
    for (const p of pills) {
      expect(body.contains(p)).toBe(true);
      expect(p).not.toBeVisible();
    }
    const box = checkbox(container)!;
    expect(box).not.toBeNull();
    expect(body.contains(box)).toBe(true);
    expect(box).not.toBeVisible();
    // each row once — never twice (not left in place as well)
    expect(allById(container, 'cm-blurb')).toHaveLength(1);
    expect(container.querySelectorAll('.cm-enterable-bar')).toHaveLength(1);
    // the rows sit inside the board now, not above it
    expect(container.querySelector('.gg-board')!.contains(blurb)).toBe(true);
  });

  it('the only visible text between the tab strip and the sub strip: the scan label, 🧾 log trade, ⓘ [C1: the on-open `closed` answer is folded]', async () => {
    const { container } = page('tab=gajjala');
    await ggLoaded(container);
    // the answer to the scan on open IS in the DOM (nothing deleted), folded
    const reused = byId(container, 'gg-scan-reused')!;
    expect(reused.textContent).toBe(SCAN_CLOSED.text);
    expect(reused).not.toBeVisible();
    expect(visibleTextBetweenTabsAndSubs(container)).toEqual([SCAN.rescan_label, '\u{1F9FE} log trade', GG_FOLD_GLYPH]);
    // NEGATIVE: the served sentences are present, just not shown
    expect(container.textContent).toContain(HAND.bull_flag.strip.text);
    expect(container.textContent).toContain('served day text');
    expect(visibleTextBetweenTabsAndSubs(container).join(' ')).not.toContain(HAND.bull_flag.strip.text);
  });

  it('one tap on ⓘ → all visible, in the order blurb → ℹ️ ×2 → 🎯 row → gg-strip; gg-fold:header = "1"', async () => {
    const { container } = page('tab=gajjala');
    await ggLoaded(container);
    const toggle = byId(container, 'gg-head-toggle')!;
    expect(toggle.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(toggle);
    await waitFor(() => expect(byId(container, 'gg-head-toggle')!.getAttribute('aria-expanded')).toBe('true'));
    expect(localStorage.getItem(`${GG_FOLD_LS}${GG_FOLD_HEADER}`)).toBe('1');
    const blurb = byId(container, 'cm-blurb')!;
    const pills = allById(container, 'rules-info-pill');
    const bar = container.querySelector('.cm-enterable-bar')!;
    const strip = byId(container, 'gg-strip')!;
    for (const el of [blurbHead(container), ...pills, bar, strip, checkbox(container)!]) expect(el).toBeVisible();
    expect(before(blurb, pills[0])).toBe(true);
    expect(before(pills[0], pills[1])).toBe(true);
    expect(before(pills[1], bar)).toBe(true);
    expect(bar.contains(pills[2])).toBe(true);
    expect(before(bar, strip)).toBe(true);
    // the action row stays above all of it
    expect(before(byId(container, 'gg-actions')!, blurb)).toBe(true);
  });

  it('🎯 Enterable (fold open): unticking writes ?show=all, ticking drops it; NEGATIVE the 🚩 tile ids are the same either way', async () => {
    localStorage.setItem(`${GG_FOLD_LS}${GG_FOLD_HEADER}`, '1');
    const { container } = page('tab=gajjala');
    await ggLoaded(container);
    await waitFor(() => expect(tileIds(container).length).toBeGreaterThan(0));
    const tilesOn = tileIds(container);
    const box = checkbox(container)!;
    expect(box).toBeVisible();
    expect(box.checked).toBe(true);
    expect(new URLSearchParams(byId(container, 'loc')!.textContent || '').get('show')).toBeNull();
    fireEvent.click(box);
    await waitFor(() => expect(new URLSearchParams(byId(container, 'loc')!.textContent || '').get('show')).toBe('all'));
    await settle();
    expect(checkbox(container)!.checked).toBe(false);
    expect(tileIds(container)).toEqual(tilesOn);
    fireEvent.click(checkbox(container)!);
    await waitFor(() => expect(new URLSearchParams(byId(container, 'loc')!.textContent || '').get('show')).toBeNull());
    await settle();
    expect(checkbox(container)!.checked).toBe(true);
    expect(tileIds(container)).toEqual(tilesOn);
  });
});

describe('NEGATIVE: every other tab keeps the three rows in place (2026-11-24)', () => {
  const inPlace = (c: HTMLElement, onBoard: boolean) => {
    const blurb = byId(c, 'cm-blurb')!;
    expect(blurb).not.toBeNull();
    expect(blurbHead(c)).toBeVisible();
    expect(blurb.closest('.gg-fold-body')).toBeNull();
    const pills = allById(c, 'rules-info-pill');
    expect(pills.length).toBeGreaterThanOrEqual(3);
    for (const p of pills) {
      expect(p).toBeVisible();
      expect(p.closest('.gg-fold-body')).toBeNull();
    }
    const box = checkbox(c)!;
    expect(box).not.toBeNull();
    expect(box).toBeVisible();
    expect(box.closest('.gg-fold-body')).toBeNull();
    expect(byId(c, 'gg-head-toggle')).toBeNull();
    expect(c.querySelector('.gg-fold-body')).toBeNull();
    // today's position: the rows sit above the tab body, never inside a board
    const gg = c.querySelector('.gg-board');
    if (onBoard) {
      expect(gg).not.toBeNull();
      expect(gg!.contains(blurb)).toBe(false);
      expect(before(blurb, gg!)).toBe(true);
      expect(before(c.querySelector('.cm-enterable-bar')!, gg!)).toBe(true);
    }
    expect(before(blurb, pills[0])).toBe(true);
  };

  for (const [tab, onBoard] of [['zones', false], ['bonde', false], ['gajjala_audited', true], ['gajjala_1m', true]] as const) {
    it(`?tab=${tab}: blurb / rules / 🎯 in place, visible, in no fold body, no ⓘ toggle`, async () => {
      const { container } = page(`tab=${tab}`);
      await waitFor(() => expect(byId(container, 'cm-blurb')).not.toBeNull());
      await waitFor(() => expect(allById(container, 'rules-info-pill').length).toBeGreaterThanOrEqual(3));
      if (onBoard) await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
      await settle();
      inPlace(container, onBoard);
    });

    it(`?tab=${tab}: a stored OPEN header key changes nothing there`, async () => {
      localStorage.setItem(`${GG_FOLD_LS}${GG_FOLD_HEADER}`, '1');
      const { container } = page(`tab=${tab}`);
      await waitFor(() => expect(byId(container, 'cm-blurb')).not.toBeNull());
      await waitFor(() => expect(allById(container, 'rules-info-pill').length).toBeGreaterThanOrEqual(3));
      if (onBoard) await waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
      await settle();
      inPlace(container, onBoard);
    });
  }
});

describe('NEGATIVE: storage and a stubbed board (2026-11-24)', () => {
  it('localStorage.getItem throwing → the page renders, the 🚩 fold is closed, the rows are inside it', async () => {
    vi.stubGlobal('localStorage', fakeStorage({ getThrows: true }));
    const { container } = page('tab=gajjala');
    await ggLoaded(container);
    expect(byId(container, 'gg-head-toggle')!.getAttribute('aria-expanded')).toBe('false');
    const body = byId(container, 'gg-head-body')!;
    expect(body.hasAttribute('hidden')).toBe(true);
    expect(body.contains(byId(container, 'cm-blurb'))).toBe(true);
    expect(blurbHead(container)).not.toBeVisible();
    expect(byId(container, 'gg-rescan')).toBeVisible();
    expect(byId(container, 'my-day-open')).toBeVisible();
  });

  it('a stubbed board (no consumer of the context) → no crash; on 🚩 the rows are simply absent', async () => {
    GG.stub = true;
    const { container } = page('tab=gajjala');
    await waitFor(() => expect(byId(container, 'gg-stub')).not.toBeNull());
    await settle(50);
    expect(byId(container, 'cm-tabs-bar')).not.toBeNull();
    expect(byId(container, 'cm-blurb')).toBeNull();
    expect(allById(container, 'rules-info-pill')).toHaveLength(0);
    expect(checkbox(container)).toBeNull();
    expect(container.querySelector('.cm-enterable-bar')).toBeNull();
  });

  it('NEGATIVE: a stubbed board on ?tab=zones still shows the three rows (the context carries nothing there)', async () => {
    GG.stub = true;
    const { container } = page('tab=zones');
    await waitFor(() => expect(byId(container, 'cm-blurb')).not.toBeNull());
    await waitFor(() => expect(allById(container, 'rules-info-pill').length).toBeGreaterThanOrEqual(3));
    expect(checkbox(container)).not.toBeNull();
    expect(blurbHead(container)).toBeVisible();
  });
});
