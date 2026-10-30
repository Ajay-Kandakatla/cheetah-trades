import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import type { CurrentUser } from '../hooks/useUser';
import { GG_TAPE_PATH, _resetGgLiteCache } from './GgEntryTape';

/* 📈 Tape column on the 🏁 Track record list (2026-10-29, BUILD_SPEC31 D3 / D5).
 *
 * Ajay: "I wanna see this kind of graph in our Track record page this screenshot is from Promo circuit page." (the
 * Promo circuit table's TAPE column — a mini per row, hover for the served line, click for the full tape).
 *
 * Rendered from the 🏁 GOLDEN (gajjala_track_record_golden_2026_10_16.json — the served payload, never typed) on the
 * REAL GgEntryTape (no mock): IntersectionObserver is stubbed, so a mini GETs its lite tape only once its row is
 * "visible". Pinned: the 📋 list (plain AND the 🎯 A+-filtered list) draws the served Tape head SECOND (right after the
 * Ticker) and one mini cell per row with an id — 🚩 A+ AND 🧠 potential; the lite GET fires for the visible rows only, to
 * the board's own route (🚩 Gajjala's → /chart-maps/gajjala/entry-tape, the 1-minute page → /chart-maps/gajjala-1m/
 * entry-tape); 📈 (or a click on the mini) opens the full-tape row under the row, the ❌ loss line after it. NEGATIVES:
 * no lite GET before a row is visible; a row without an id → an empty cell; an older API (no views) → no column; the
 * shared component types no tape word; the 430 px phone: the table scrolls inside .gg-tr-scroll, no new px width. */

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

const clone = (x: any) => JSON.parse(JSON.stringify(x));
const TR5D: any = (trGolden as any).boards['5d'];
const P1 = '/chart-maps/gajjala-1m';
const P1_TAPE = `${P1}/entry-tape`;

/* The served variant block of the 1-minute page (the GajjalaBoard.variant test's copy — test data). */
const VARIANT_1M = {
  key: 'gajjala_1m', tab: 'gajjala_1m', label: "Gajjala's 1-min", title: 'served 1-minute title', honesty: 'served honesty',
  tfs: ['1m', '5m'], primary: '1m', slow: '5m', api_base: P1, record_from: '2026-10-27',
};
function trBoard(one = false): any {
  const b = clone(TR5D);
  b.session = { ...b.session, refresh_sec: 0 };
  if (one) { b.tab = 'gajjala_1m'; b.tf = '1m'; b.variant = clone(VARIANT_1M); }
  return b;
}

/* A served lite tape: a few closes and its served title (per id, so the hover is provably the served line). */
const T0 = Date.UTC(2026, 9, 16, 15, 0);
const bar = (t: number, c: number) => ({ t, o: c, h: c + 0.01, l: c - 0.01, c, v: 1000, s: 'rth' });
const tapeOf = (id: string, lite: boolean) => ({
  id, ticker: 'X', tf: 'served tf', lite, bars: [bar(T0, 1), bar(T0 + 300_000, 1.1), bar(T0 + 600_000, 1.2)], n_bars: 3,
  hlines: [], rules: [{ key: 'alert', at: new Date(T0 + 300_000).toISOString(), style: 'solid', tone: 'alert', label: 'served ring' }],
  dots: [], title: `served title of ${id}`, tone: 'up', note: null, aria: `served aria of ${id}`, as_of: 'now',
  legend: 'served legend', read: 'served read',
});

type Call = { method: string; path: string; q: URLSearchParams };
let calls: Call[] = [];
function stub(board: () => any) {
  calls = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    calls.push({ method: String(init?.method || 'GET').toUpperCase(), path: u.pathname, q: u.searchParams });
    const ok = (body: any) => ({ ok: true, status: 200, json: async () => clone(body) });
    if (u.pathname.endsWith('/scan')) return ok({ state: 'closed', latest_at: null, text: 'served closed line' });
    if (u.pathname.endsWith('/entry-tape')) return ok(tapeOf(u.searchParams.get('id') || '', u.searchParams.get('lite') === '1'));
    if (u.pathname.endsWith('/chart-maps/gajjala') || u.pathname.endsWith(P1)) return ok(board());
    return ok({});
  }));
}
const tapeGets = (path: string, lite: boolean) =>
  calls.filter((c) => c.method === 'GET' && c.path.endsWith(path) && (c.q.get('lite') === '1') === lite);

/* IntersectionObserver stub: nothing is visible until show(el) says so. */
type Io = { cb: IntersectionObserverCallback; els: Element[]; dead: boolean };
let ios: Io[] = [];
class FakeIO {
  private me: Io;
  constructor(cb: IntersectionObserverCallback) { this.me = { cb, els: [], dead: false }; ios.push(this.me); }
  observe(el: Element) { this.me.els.push(el); }
  unobserve() { /* unused */ }
  disconnect() { this.me.dead = true; }
  takeRecords() { return []; }
}
function show(el: Element) {
  act(() => {
    for (const io of ios) {
      if (!io.dead && io.els.includes(el)) io.cb([{ isIntersecting: true, target: el } as any], io as any);
    }
  });
}

const mount = (q: string, variant?: 'gajjala_1m') => render(
  <MemoryRouter initialEntries={[`/chart-maps?${q}`]}>
    {variant ? <GajjalaBoard variant={variant} /> : <GajjalaBoard />}
  </MemoryRouter>);
const loaded = async (container: HTMLElement) =>
  waitFor(() => expect(container.querySelector('.gg-board')?.getAttribute('data-state')).toBe('loaded'));
const miniOf = (key: string) => screen.getByTestId(`gg-tr-row-${key}`).querySelector('[data-testid="gg-tape-mini"]');

const TR = TR5D.track_record;
const ROWS: any[] = TR.days.flatMap((d: any) => d.rows);
const POT = ROWS.find((r: any) => r.kind === 'potential' && r.id);
const APLUS = ROWS.find((r: any) => r.kind === 'aplus' && r.id && !String(r.id).startsWith('REPLAY:'));
const SYM_AT = TR.heads.findIndex((h: any) => h.key === 'symbol');

beforeEach(() => {
  userRet = null; ios = []; calls = []; _resetGgLiteCache();
  vi.stubGlobal('IntersectionObserver', FakeIO);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('📈 the 🏁 list draws the Promo Tape column (golden)', () => {
  it('the golden serves views + 🚩 A+ and 🧠 potential rows with ids, the Ticker head first (NEGATIVE: never a silent skip)', () => {
    expect(TR.views?.tape_head).toBeTruthy();
    expect(POT).toBeTruthy();
    expect(APLUS).toBeTruthy();
    expect(SYM_AT).toBe(0);
  });

  it('the served Tape head SECOND and a mini cell per row with an id — A+ AND 🧠; the served 📈 toggle on each', async () => {
    stub(() => trBoard());
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    for (const d of TR.days) {
      const table = screen.getByTestId(`gg-tr-day-${d.date}`).parentElement!.querySelector('table.gg-tr-table')!;
      const labels = TR.heads.map((h: any) => h.label);
      labels.splice(SYM_AT + 1, 0, TR.views.tape_head);
      expect([...table.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(labels);
      for (const r of d.rows) {
        const tds = screen.getByTestId(`gg-tr-row-${r.key}`).querySelectorAll(':scope > td');
        expect(tds).toHaveLength(TR.heads.length + 1);
        expect(tds[SYM_AT].className).toContain('gg-tr-sym');
        expect(tds[SYM_AT + 1].className).toBe('ptt__mini-cell');
        expect(tds[SYM_AT + 1].querySelector('[data-testid="gg-tape-mini"]'), r.key).not.toBeNull();
        const btn = screen.getByTestId(`gg-tr-open-${r.key}`);
        expect(btn.textContent).toBe(TR.views.tape_toggle);
        expect(btn.getAttribute('title')).toBe(TR.views.tape_toggle_title);
        expect(btn.getAttribute('aria-expanded')).toBe('false');
      }
    }
    const kinds = new Set(ROWS.filter((r: any) => miniOf(r.key)).map((r: any) => r.kind));
    expect([...kinds].sort()).toEqual(['aplus', 'potential']);
    // NEGATIVE: no full tape until 📈
    expect(screen.queryAllByTestId(/^gg-tr-tape-/)).toHaveLength(0);
    expect(screen.queryAllByTestId('gg-tape')).toHaveLength(0);
  });

  it('the lite GET fires for the VISIBLE rows only, to 🚩 Gajjala\'s route; the hover = the served title', async () => {
    stub(() => trBoard());
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    // NEGATIVE: nothing visible → no tape GET at all
    expect(calls.filter((c) => c.path.endsWith('/entry-tape'))).toHaveLength(0);
    show(miniOf(POT.key)!);
    show(miniOf(APLUS.key)!);
    await waitFor(() => expect(tapeGets(GG_TAPE_PATH, true)).toHaveLength(2));
    expect(tapeGets(GG_TAPE_PATH, true).map((c) => c.q.get('id')).sort()).toEqual([POT.id, APLUS.id].sort());
    await waitFor(() => expect(miniOf(POT.key)!.getAttribute('title')).toBe(`served title of ${POT.id}`));
    expect(miniOf(APLUS.key)!.getAttribute('title')).toBe(`served title of ${APLUS.id}`);
    expect(miniOf(POT.key)!.querySelector('svg')!.getAttribute('width')).toBe('100');
    // NEGATIVE: the other rows stay unfetched; never the 1-minute route; never a full tape
    for (const r of ROWS) if (r.key !== POT.key && r.key !== APLUS.key) expect(miniOf(r.key)!.getAttribute('title'), r.key).toBeNull();
    expect(calls.filter((c) => c.path.endsWith(P1_TAPE))).toHaveLength(0);
    expect(tapeGets(GG_TAPE_PATH, false)).toHaveLength(0);
  });

  it('📈 on a 🧠 row opens the full-tape row under it (full GET, colspan = heads + Tape); the ❌ loss line after it', async () => {
    const b = trBoard();
    const pot = b.track_record.days.flatMap((d: any) => d.rows).find((r: any) => r.key === POT.key);
    pot.loss_text = 'served loss facts';
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    const row = screen.getByTestId(`gg-tr-row-${POT.key}`);
    expect(row.nextElementSibling!.querySelector(`[data-testid="gg-tr-loss-${POT.key}"]`)).not.toBeNull();
    fireEvent.click(screen.getByTestId(`gg-tr-open-${POT.key}`));
    const tapeRow = screen.getByTestId(`gg-tr-tape-${POT.key}`);
    expect(row.nextElementSibling).toBe(tapeRow);
    expect(tapeRow.className).toBe('ptt__row');
    expect(tapeRow.querySelector('td')!.getAttribute('colspan')).toBe(String(TR.heads.length + 1));
    expect(screen.getByTestId(`gg-tr-open-${POT.key}`).getAttribute('aria-expanded')).toBe('true');
    const loss = screen.getByTestId(`gg-tr-loss-${POT.key}`);
    expect(tapeRow.nextElementSibling).toBe(loss.closest('tr'));
    expect(loss.getAttribute('colspan')).toBe(String(TR.heads.length + 1));
    await waitFor(() => expect(tapeGets(GG_TAPE_PATH, false).map((c) => c.q.get('id'))).toEqual([POT.id]));
    await waitFor(() => expect(within(tapeRow).getByTestId('gg-tape-read').textContent).toBe('served read'));
    // only that row opened; a second click closes it
    expect(screen.queryAllByTestId(/^gg-tr-tape-/)).toHaveLength(1);
    fireEvent.click(screen.getByTestId(`gg-tr-open-${POT.key}`));
    expect(screen.queryByTestId(`gg-tr-tape-${POT.key}`)).toBeNull();
    // a click on the mini itself opens it too (the Promo pattern)
    fireEvent.click(miniOf(APLUS.key)!);
    expect(screen.getByTestId(`gg-tr-tape-${APLUS.key}`)).toBeTruthy();
  });

  it('NEGATIVE: a row without an id → an empty Tape cell (no mini, no 📈); the other rows keep theirs', async () => {
    const b = trBoard();
    const bare = b.track_record.days.flatMap((d: any) => d.rows).find((r: any) => r.key === POT.key);
    delete bare.id;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    const cell = screen.getByTestId(`gg-tr-row-${POT.key}`).querySelectorAll(':scope > td')[SYM_AT + 1];
    expect(cell.className).toBe('ptt__mini-cell');
    expect(cell.textContent).toBe('');
    expect(cell.children).toHaveLength(0);
    expect(screen.queryByTestId(`gg-tr-open-${POT.key}`)).toBeNull();
    for (const r of ROWS) if (r.key !== POT.key) expect(screen.getByTestId(`gg-tr-open-${r.key}`), r.key).toBeTruthy();
  });

  it('the 🎯 A+-filtered list has the column too: every served aplus.days row with its mini, the Tape head second', async () => {
    expect(TR.aplus?.days?.length).toBeGreaterThan(0);
    const aplusKind = TR.kinds.find((k: any) => k.key !== TR.kinds[0].key).key;
    stub(() => trBoard());
    const { container } = mount(`tab=gajjala&sub=track_record&sort=rang&kind=${aplusKind}`);
    await loaded(container);
    const want = TR.aplus.days.flatMap((d: any) => d.rows.map((r: any) => r.key));
    expect(screen.getAllByTestId(/^gg-tr-row-/).map((r) => r.getAttribute('data-testid'))).toEqual(want.map((k: string) => `gg-tr-row-${k}`));
    for (const k of want) {
      const tds = screen.getByTestId(`gg-tr-row-${k}`).querySelectorAll(':scope > td');
      expect(tds[SYM_AT + 1].querySelector('[data-testid="gg-tape-mini"]'), k).not.toBeNull();
    }
    for (const t of container.querySelectorAll('table.gg-tr-table')) {
      expect(t.querySelectorAll('thead th')[SYM_AT + 1].textContent).toBe(TR.views.tape_head);
    }
  });

  it('NEGATIVE: an older API (no views) → no Tape head, no Tape cell, no tape GET — the tables as shipped', async () => {
    const b = trBoard();
    delete b.track_record.views;
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    expect(container.querySelectorAll('td.ptt__mini-cell')).toHaveLength(0);
    expect(screen.queryAllByTestId('gg-tape-mini')).toHaveLength(0);
    for (const t of container.querySelectorAll('table.gg-tr-table')) {
      expect([...t.querySelectorAll('thead th')].map((th) => th.textContent)).toEqual(TR.heads.map((h: any) => h.label));
    }
    expect(calls.filter((c) => c.path.endsWith('/entry-tape'))).toHaveLength(0);
  });
});

describe('📈 the Tape column on 🚩 Gajjala\'s 1-min reads the 1-minute route', () => {
  it('a 🧠 row\'s lite AND full tape GET /chart-maps/gajjala-1m/entry-tape — NEGATIVE: never the 5-minute route', async () => {
    stub(() => trBoard(true));
    const { container } = mount('tab=gajjala_1m&sub=track_record&sort=rang', 'gajjala_1m');
    await loaded(container);
    expect(calls.some((c) => c.path.endsWith(P1))).toBe(true);
    show(miniOf(POT.key)!);
    await waitFor(() => expect(tapeGets(P1_TAPE, true).map((c) => c.q.get('id'))).toEqual([POT.id]));
    fireEvent.click(screen.getByTestId(`gg-tr-open-${POT.key}`));
    await waitFor(() => expect(tapeGets(P1_TAPE, false).map((c) => c.q.get('id'))).toEqual([POT.id]));
    expect(calls.filter((c) => c.path.endsWith(GG_TAPE_PATH))).toHaveLength(0);
  });
});

/* ---- source + stylesheet guards (the GajjalaBoard.phone / legend pattern — jsdom has no layout) ---- */
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}
function fnBody(src: string, name: string): string | null {
  const a = src.indexOf(`\nfunction ${name}(`);
  if (a < 0) return null;
  const e = src.indexOf('\n}\n', a + 1);
  return src.slice(a, e < 0 ? undefined : e)
    .replace(/\{\/\*[\s\S]*?\*\/\}/g, '').replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/[^\n]*$/gm, '');
}
/** Every typed word in a body: its JSX text and its string literals (template holes blanked). */
function typed(body: string): string[] {
  const jsx = [...body.matchAll(/>([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean);
  const lits = [...body.matchAll(/'([^'\n]*)'|"([^"\n]*)"|`([^`]*)`/g)].map((m) => (m[1] ?? m[2] ?? m[3]).replace(/\$\{[^}]*\}/g, ' '));
  return [...jsx, ...lits];
}
/** The served tape words a body must never type: the golden's views strings + tape.py's ENTRY_TAPE_WORDS phrases. */
function servedTapeWords(tapePy: string): string[] {
  const out = new Set<string>([TR.views.tape_head, TR.views.tape_toggle, TR.views.tape_toggle_title]);
  const block = /^ENTRY_TAPE_WORDS = \{([\s\S]*?)\n\}/m.exec(tapePy);
  for (const m of (block?.[1] || '').matchAll(/^\s*"\w+":\s*"((?:[^"\\]|\\.)*)"/gm)) {
    const p = m[1].split('{')[0].trim();
    if (p.length >= 4) out.add(p);
  }
  return [...out];
}
const hits = (body: string, words: string[]) => typed(body).flatMap((s) => words.filter((w) =>
  (w === TR.views.tape_head ? new RegExp(`\\b${w}\\b`).test(s) : s.includes(w))).map((w) => `${w} in "${s.trim()}"`));
const jsxText = (body: string) => [...body.matchAll(/>([^<>{}\n]+)</g)].map((m) => m[1].trim()).filter(Boolean);

describe('📈 the shared Tape row types no tape word (every word is served by tape.py)', () => {
  it('GgTrTapeRow / GgTrTapeCell / GgTrHead / GgEntryTimelineRow: no JSX text, no served tape word, no number formatting', async () => {
    const src = await readSource('src/components/GajjalaBoard.tsx');
    const words = servedTapeWords(await readSource('../backend/chart_maps/gajjala/tape.py'));
    expect(words.length).toBeGreaterThan(10);
    for (const n of ['GgTrTapeRow', 'GgTrTapeCell', 'GgTrHead', 'GgEntryTimelineRow']) {
      const b = fnBody(src, n);
      expect(b, n).not.toBeNull();
      expect(jsxText(b!), n).toEqual([]);
      expect(hits(b!, words), n).toEqual([]);
      expect(b!, n).not.toMatch(/toFixed|Math\.|%|toLocale|Intl\./);
    }
    // ONE copy: the list and the timeline both mount the shared row; the cell markup exists once
    expect(src.split('ptt__mini-cell').length - 1).toBe(1);
    expect(src).toContain('tid="gg-tr" />');
    expect(src).toContain('tid="gg-tl" />');
  });

  it('NEGATIVE: the same matchers flag a body that types the Tape head, the toggle or a tape sentence', async () => {
    const words = servedTapeWords(await readSource('../backend/chart_maps/gajjala/tape.py'));
    const bad = '\nfunction X() {\n  return <th>Tape</th>;\n}\n';
    expect(jsxText(bad)).toEqual(['Tape']);
    expect(hits(`const t = '${TR.views.tape_toggle}';`, words)).not.toEqual([]);
    expect(hits("const t = 'the trigger never printed';", words)).not.toEqual([]);
    expect(hits('const c = `ptt__toggle is-on`; const k = \'__tape\';', words)).toEqual([]);
  });
});

describe('📱 the Tape column on the 430 px phone — the table scrolls inside .gg-tr-scroll', () => {
  const scrollRule = (css: string) => (/(^|\n)\s*\.gg-tr-scroll\s*\{([^}]*)\}/.exec(css) || [])[2] ?? null;
  const tapeRules = (css: string) => [...css.matchAll(/\n([^{}\n]*ptt__[^{}\n]*)\{([^}]*)\}/g)].map((m) => ({ sel: m[1].trim(), decl: m[2] }));
  const PRE_FIX = '.gg-tr-scroll { max-width: 100%; }\n.gg-tr-table .ptt__mini-cell { width: 160px; }\n';

  it('.gg-tr-scroll is overflow-x: auto + max-width: 100%; the Tape-cell rules read every 🏁 table and set no px width', async () => {
    const css = await readSource('src/styles/gajjala.css');
    const decl = scrollRule(css);
    expect(decl).not.toBeNull();
    expect(decl).toMatch(/overflow-x:\s*auto/);
    expect(decl).toMatch(/max-width:\s*100%/);
    const rules = tapeRules(css);
    expect(rules.map((r) => r.sel)).toContain('.gg-tr-table .ptt__mini-cell');
    for (const r of rules) expect(r.decl, r.sel).not.toMatch(/(?:^|[;\s])(?:min-|max-)?width:\s*\d+px/);
  });

  it('NEGATIVE: a stylesheet without the scroll overflow, or with a px-wide Tape cell, fails the same matchers', () => {
    expect(scrollRule(PRE_FIX)).not.toMatch(/overflow-x:\s*auto/);
    expect(tapeRules(PRE_FIX).some((r) => /(?:^|[;\s])(?:min-|max-)?width:\s*\d+px/.test(r.decl))).toBe(true);
  });

  it('every list table sits inside .gg-tr-scroll and the Tape cell is the second cell (no page-wide overflow source)', async () => {
    stub(() => trBoard());
    const { container } = mount('tab=gajjala&sub=track_record&sort=rang');
    await loaded(container);
    const tables = [...container.querySelectorAll('table.gg-tr-table')];
    expect(tables.length).toBe(TR.days.length);
    for (const t of tables) expect(t.parentElement!.className).toBe('gg-tr-scroll');
    for (const cell of container.querySelectorAll('td.ptt__mini-cell')) {
      expect(cell.parentElement!.children[SYM_AT + 1]).toBe(cell);
      expect(cell.getAttribute('style')).toBeNull();
    }
  });
});
