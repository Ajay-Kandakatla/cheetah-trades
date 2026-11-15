/* 🎯 Enterable (zones) on the 📅 Long Term table (2026-11-14, ltenter spec §3.7 / §4 WP-FE). Ajay 2026-11-14: "Make a
 * enterable check box in longterm stocks with zone and filters please".
 *
 * The checkbox (default OFF, saved per viewer) hides the saved rows that are not inside / just above one of their zones;
 * a Zone column after Today prints the read (live print when the house flags it, else the closed bar, else the served
 * close). The filter runs before the Today sort, never reorders, never changes a request. Every word is served
 * (zone_rules.words / reasons / sources / levels). The four house chips are mocked inert (table.test pattern).
 * NEGATIVES throughout. XPEL's Pankaj-shaped 30–32 band is FIXTURE-ONLY (XPEL is not a 🧭 name) — it exercises no_price. */
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from '../lib/__fixtures__/longTerm.payload.json';
import { LT_PATH } from '../lib/longTerm';
import { CARD_LIVE_PATH } from '../lib/cardLive';
import { LT_ZONE_LS_KEY } from '../lib/ltZones';

vi.mock('./GrowthChip', () => ({ GrowthChip: () => null }));
vi.mock('./ShortInterestChip', () => ({ ShortInterestChip: () => null }));
vi.mock('./ExplosiveChip', () => ({ ExplosiveChip: () => null }));
vi.mock('./EnterableChip', () => ({ EnterableChip: () => null }));
vi.mock('../hooks/useBounceRoom', () => ({ useBounceRoom: () => ({ map: new Map(), payload: null }) }));

import LongTermBoard from './LongTermBoard';

const clone = <T,>(v: T): T => JSON.parse(JSON.stringify(v));
const SAVED = ['MANH', 'AMD', 'FIGS', 'ANET', 'NVDA', 'MPWR', 'XPEL', 'TSM'];
const R = (fixture as any).zone_rules;
const W: Record<string, string> = R.words;
const label = (code: string) => R.reasons.find((r: any) => r.code === code).label as string;
const NOT_A_SIGNAL = /None of these lists is a buy signal\.?/g;
const BANNED = /\b(buy|buying|bought|sell|selling|sold|entry|entries|exit|exits)\b/i;

/* Live answer (spec §3.8): rth, as_of 2026-11-14 10:31:05 ET; prints flagged add_line. NVDA 171.36 sits INSIDE C1
 * 170–175 (C1's bottom is C2's top); TSM 414.10 = +1.0% over Agg → just above; ANET 140 → above; AMD 160 → inside
 * conservative 1 148–160; MANH no quote. NEGATIVE: XPEL carries a print with add_line false (a carried print) → its cell
 * reads the bar (close), never "live". */
const DAY = '2026-11-14';
const qt = (price: number, prev: number, addLine = true, t = DAY) => ({
  bar: { t, o: price, h: price, l: price, c: price, v: 1 }, prev_t: '2026-11-13',
  prev_bar: { t: '2026-11-13', o: prev, h: prev, l: prev, c: prev, v: 1 },
  now: { price, label: 'now', session: null, add_line: addLine, as_of_epoch: 1, as_of: addLine ? '10:31:05 ET' : null },
});
const LIVE = (session: string | null = 'rth') => ({
  session, as_of: `${DAY} 10:31:05 ET`, footer: {}, now_labels: [], quotes: {
    NVDA: qt(171.36, 166.19), TSM: qt(414.1, 405.49), ANET: qt(140, 132.75), AMD: qt(160, 191.52), FIGS: qt(5, 10),
    XPEL: qt(31.5, 31, false, '2026-11-13'),
  },
});

function mem() {
  const m = new Map<string, string>();
  return { getItem: (k: string) => (m.has(k) ? m.get(k)! : null), setItem: (k: string, v: string) => { m.set(k, String(v)); },
           removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear() };
}
function stub(board: unknown = fixture, live: unknown = { detail: 'none' }) {
  const f = vi.fn(async (url: string, _init?: RequestInit) => {
    const u = String(url);
    if (u.includes(LT_PATH)) return { ok: true, status: 200, json: async () => clone(board) };
    if (u.includes(CARD_LIVE_PATH)) return { ok: true, status: 200, json: async () => clone(live) };
    return { ok: true, status: 200, json: async () => ({}) };
  });
  vi.stubGlobal('fetch', f);
  return f;
}
async function mount(board: unknown = fixture, live?: unknown) {
  const f = stub(board, live);
  const r = render(<MemoryRouter initialEntries={['/chart-maps?tab=long_term']}><LongTermBoard /></MemoryRouter>);
  await waitFor(() => expect(r.container.querySelector('.lt-board[data-state="ready"]')).not.toBeNull());
  return { ...r, f };
}
const rowsOnPage = (c: HTMLElement) => [...c.querySelectorAll('tr.lt-tr')].map((n) => n.getAttribute('data-testid')!.slice('lt-row-'.length));
const tick = () => act(() => { fireEvent.click(screen.getByTestId('lt-zf-on')); });
const cell = (s: string) => screen.getByTestId(`lt-zcell-${s}`);
async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

beforeEach(() => { vi.stubGlobal('localStorage', mem()); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('🎯 the checkbox — default OFF, then a stable filter', () => {
  it('default OFF: every saved row, "showing all", NEGATIVE: no sheet / level / reason chip in the DOM', async () => {
    const { container } = await mount();
    expect(rowsOnPage(container)).toEqual(SAVED);
    expect((screen.getByTestId('lt-zf-on') as HTMLInputElement).checked).toBe(false);
    expect(screen.getByTestId('lt-zf-count')).toHaveTextContent('showing all');
    expect(screen.getByTestId('lt-zf-show-only')).toBeTruthy();
    expect(container.querySelector('[data-testid^="lt-zf-src-"]')).toBeNull();
    expect(container.querySelector('[data-testid^="lt-zf-lvl-"]')).toBeNull();
    expect(container.querySelector('[data-testid^="lt-zf-reason-"]')).toBeNull();
    expect(screen.getByTestId('lt-zf-bar').textContent).toContain('🎯 Enterable (zones)');
    expect(screen.getByTestId('lt-zf-on').closest('label')!.getAttribute('title')).toBe(R.text);
  });

  it('tick → only enterable rows, saved order kept; "N hidden" + served reason chips with counts; chips appear', async () => {
    const { container } = await mount();
    tick();
    expect(rowsOnPage(container)).toEqual(['AMD', 'NVDA', 'TSM']);
    for (const s of ['MANH', 'ANET', 'XPEL', 'FIGS', 'MPWR']) expect(screen.queryByTestId(`lt-row-${s}`)).toBeNull();
    const count = screen.getByTestId('lt-zf-count');
    expect(count.textContent).toMatch(/^5 hidden/);
    expect(screen.getByTestId('lt-zf-reason-no_zone')).toHaveTextContent(`3 ${label('no_zone')}`);
    expect(screen.getByTestId('lt-zf-reason-above')).toHaveTextContent(`1 ${label('above')}`);
    expect(screen.getByTestId('lt-zf-reason-no_price')).toHaveTextContent(`1 ${label('no_price')}`);
    expect(screen.getByTestId('lt-zf-reason-no_zone').getAttribute('title')).toBe(W.not_house_chip);
    /* NEGATIVE: a reason that holds back nothing gets no chip */
    expect(screen.queryByTestId('lt-zf-reason-below')).toBeNull();
    expect(screen.queryByTestId('lt-zf-reason-filtered')).toBeNull();
    /* chip order: baseline desc, then the served label asc ("above the zone — too far" < "no price read") */
    expect([...count.querySelectorAll('[data-testid^="lt-zf-reason-"]')].map((n) => n.getAttribute('data-testid')))
      .toEqual(['lt-zf-reason-no_zone', 'lt-zf-reason-above', 'lt-zf-reason-no_price']);
    for (const s of R.sources) expect(screen.getByTestId(`lt-zf-src-${s.key}`)).toHaveTextContent(s.label);
    for (const l of R.levels) {
      const chip = screen.getByTestId(`lt-zf-lvl-${l.source}:${l.key}`);
      expect(chip).toHaveTextContent(l.label);
      expect(chip.getAttribute('aria-pressed')).toBe('true');
    }
    expect(screen.getByTestId('lt-zf-src-both').getAttribute('aria-pressed')).toBe('true');
  });

  it('a reason chip un-hides exactly its rows (MANH + FIGS + MPWR), hidden drops by 3, the chip stays pressed', async () => {
    const { container } = await mount();
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-reason-no_zone')); });
    expect(rowsOnPage(container)).toEqual(['MANH', 'AMD', 'FIGS', 'NVDA', 'MPWR', 'TSM']);
    expect(screen.getByTestId('lt-zf-count').textContent).toMatch(/^2 hidden/);
    const chip = screen.getByTestId('lt-zf-reason-no_zone');
    expect(chip.getAttribute('aria-pressed')).toBe('true');
    expect(chip).toHaveTextContent(`3 ${label('no_zone')}`);
    expect(screen.queryByTestId('lt-row-ANET')).toBeNull();
    expect(screen.queryByTestId('lt-row-XPEL')).toBeNull();
  });

  it('"show all" turns it OFF; the 🎯 enterable only button turns it back ON', async () => {
    const { container } = await mount();
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-show-all')); });
    expect((screen.getByTestId('lt-zf-on') as HTMLInputElement).checked).toBe(false);
    expect(rowsOnPage(container)).toEqual(SAVED);
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-show-only')); });
    expect((screen.getByTestId('lt-zf-on') as HTMLInputElement).checked).toBe(true);
    expect(rowsOnPage(container)).toEqual(['AMD', 'NVDA', 'TSM']);
  });

  it('source chip Gabbar → only Gabbar-banded names; a Pankaj level chip renders disabled (never hidden)', async () => {
    const { container } = await mount();
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-src-gabbar')); });
    expect(rowsOnPage(container)).toEqual(['AMD']);
    /* TSM, NVDA, XPEL carry Pankaj bands only → filtered; ANET's Gabbar bands read above */
    expect(screen.getByTestId('lt-zf-reason-filtered')).toHaveTextContent(`3 ${label('filtered')}`);
    expect(screen.getByTestId('lt-zf-reason-above')).toHaveTextContent(`1 ${label('above')}`);
    expect((screen.getByTestId('lt-zf-lvl-pankaj:Agg') as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByTestId('lt-zf-lvl-gabbar:aggressive') as HTMLButtonElement).disabled).toBe(false);
  });

  it('a level chip while all are pressed keeps ONLY that level; un-pressing it returns to all', async () => {
    const { container } = await mount();
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-lvl-pankaj:C2')); });
    expect(screen.getByTestId('lt-zf-lvl-pankaj:C2').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('lt-zf-lvl-pankaj:Agg').getAttribute('aria-pressed')).toBe('false');
    expect(rowsOnPage(container)).toEqual(['NVDA']);
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-lvl-pankaj:C2')); });
    expect(screen.getByTestId('lt-zf-lvl-pankaj:Agg').getAttribute('aria-pressed')).toBe('true');
    expect(rowsOnPage(container)).toEqual(['AMD', 'NVDA', 'TSM']);
  });

  it('tick + Today sort → the shown rows sorted worst first, hidden rows stay hidden', async () => {
    const { container } = await mount(fixture, LIVE());
    await waitFor(() => expect(cell('TSM').textContent).toContain(W.live));
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-reason-no_zone')); });
    act(() => { fireEvent.click(container.querySelector<HTMLButtonElement>('[data-testid="lt-sort-today"]')!); });
    /* saved order AMD, FIGS; FIGS −50% today, AMD −16.5% → worst first = FIGS, AMD */
    const s2 = within(screen.getByTestId('lt-cat-s2_growth'));
    expect([...s2.getByTestId('lt-table-s2_growth').querySelectorAll('tr.lt-tr')].map((n) => n.getAttribute('data-testid')))
      .toEqual(['lt-row-FIGS', 'lt-row-AMD']);
    expect(screen.queryByTestId('lt-row-ANET')).toBeNull();
  });

  it('NEGATIVE: the live POST asks for the SAME saved symbol list with the filter ON (no request change)', async () => {
    const { f } = await mount(fixture, LIVE());
    tick();
    await act(async () => { await new Promise((r) => setTimeout(r, 10)); });
    const calls = f.mock.calls.filter((c) => String(c[0]).includes(CARD_LIVE_PATH));
    expect(calls.length).toBeGreaterThan(0);
    for (const c of calls) expect([...JSON.parse(String(c[1]?.body)).symbols].sort()).toEqual([...SAVED].sort());
    expect(f.mock.calls.filter((c) => String(c[0]).includes(LT_PATH))).toHaveLength(1);
  });
});

describe('🎯 per-viewer storage (lt_zone_filter_v1)', () => {
  it('written on change and honoured on remount', async () => {
    const a = await mount();
    tick();
    act(() => { fireEvent.click(screen.getByTestId('lt-zf-reason-no_price')); });
    const saved = JSON.parse(window.localStorage.getItem(LT_ZONE_LS_KEY)!);
    expect(saved).toEqual({ on: true, source: 'both', levels: [], unhide: ['no_price'] });
    a.unmount();
    const b = await mount();
    await waitFor(() => expect((screen.getByTestId('lt-zf-on') as HTMLInputElement).checked).toBe(true));
    expect(rowsOnPage(b.container)).toEqual(['AMD', 'NVDA', 'XPEL', 'TSM']);
  });
  it('NEGATIVE: a stored {on:false, source:gabbar} leaves the column unfiltered — TSM reads inside, never "filtered"', async () => {
    window.localStorage.setItem(LT_ZONE_LS_KEY, JSON.stringify({ on: false, source: 'gabbar', levels: [], unhide: [] }));
    await mount();
    expect(cell('TSM').textContent).toContain('inside Pankaj Agg 400–410 · close 11-13');
    expect(cell('TSM').textContent).not.toContain(W.filtered);
  });
  it('NEGATIVE: storage that throws → the board renders in the default state (OFF, every row)', async () => {
    vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
    const { container } = await mount();
    expect((screen.getByTestId('lt-zf-on') as HTMLInputElement).checked).toBe(false);
    expect(rowsOnPage(container)).toEqual(SAVED);
    tick();
    expect(rowsOnPage(container)).toEqual(['AMD', 'NVDA', 'TSM']);
  });
});

describe('🎯 the Zone column', () => {
  it('Zone header sits right after Today', async () => {
    const { container } = await mount();
    const ths = [...container.querySelector('table.lt-table thead')!.querySelectorAll('th')].map((t) => t.textContent);
    expect(ths.slice(0, 3)).toEqual(['Ticker', 'Today', 'Zone']);
  });
  it('rth live: TSM just above (live HH:MM:SS ET); NVDA inside C1 (live); ANET above; AMD inside conservative 1', async () => {
    await mount(fixture, LIVE());
    await waitFor(() => expect(cell('TSM').textContent).toContain('live'));
    expect(cell('TSM').firstChild!.textContent).toBe('just above Pankaj Agg 400–410 · +1.0% · live 10:31:05 ET');
    expect(cell('NVDA').firstChild!.textContent).toBe('inside Pankaj C1 170–175 · live 10:31:05 ET');
    expect(cell('ANET').firstChild!.textContent).toBe('above the zone Pankaj Agg 120–125 · +12.0% · live 10:31:05 ET');
    expect(cell('AMD').firstChild!.textContent).toBe('inside Gabbar conservative 1 148–160 · live 10:31:05 ET');
    expect(cell('TSM').getAttribute('data-state')).toBe('near');
    expect(cell('TSM').getAttribute('data-enterable')).toBe('true');
    expect(cell('ANET').className).toContain('lt-z-above');
  });
  it('NEGATIVE: a carried print (add_line false) reads the bar — "close", never "live"', async () => {
    await mount(fixture, LIVE());
    await waitFor(() => expect(cell('TSM').textContent).toContain('live'));
    expect(cell('XPEL').firstChild!.textContent).toBe('inside Pankaj C1 30–32 · close 11-13');
    expect(cell('XPEL').textContent).not.toContain(W.live);
  });
  it('a closed-session answer reads the closed bar with the served close word + MM-DD', async () => {
    await mount(fixture, LIVE('closed'));
    await waitFor(() => expect(cell('TSM').firstChild!.textContent).toBe('just above Pankaj Agg 400–410 · +1.0% · close 11-14'));
    expect(cell('TSM').textContent).not.toContain(W.live);
  });
  it('no live answer → the served close read, verbatim', async () => {
    await mount();
    for (const s of ['TSM', 'NVDA', 'ANET', 'AMD']) {
      const row = [...(fixture as any).changed, ...(fixture as any).categories.flatMap((c: any) => c.rows)].find((r: any) => r.symbol === s);
      expect(cell(s).firstChild!.textContent).toBe(row.zone.close.text);
    }
  });
  it('MANH = the served no_zone word; XPEL = the served no_price word', async () => {
    await mount();
    expect(cell('MANH').textContent).toBe(W.no_zone);
    expect(cell('XPEL').textContent).toBe(W.no_price);
  });
  it('the Gabbar note renders the served gabbar_text (ANET); NEGATIVE: no note node when null (MANH)', async () => {
    await mount();
    expect(screen.getByTestId('lt-zcell-note-ANET')).toHaveTextContent((fixture as any).categories[1].rows[1].zone.gabbar_text);
    expect(screen.queryByTestId('lt-zcell-note-MANH')).toBeNull();
  });
  it('NEGATIVE: an older API with no zone_rules → no bar, no Zone column, every row shows', async () => {
    const p = clone(fixture) as any;
    delete p.zone_rules;
    const { container } = await mount(p);
    expect(screen.queryByTestId('lt-zf-bar')).toBeNull();
    expect(container.querySelector('[data-testid^="lt-zcell-"]')).toBeNull();
    expect(rowsOnPage(container)).toEqual(SAVED);
  });
});

describe('🎯 sections, ids, words', () => {
  it('a table whose rows are all hidden prints the served section_empty line and no <table> (⚠️ changed, 💎)', async () => {
    await mount();
    tick();
    expect(screen.getByTestId('lt-zf-empty-changed')).toHaveTextContent(W.section_empty);
    expect(screen.getByTestId('lt-changed').querySelector('table')).toBeNull();
    expect(screen.getByTestId('lt-zf-empty-capital_quality')).toHaveTextContent(W.section_empty);
    expect(screen.queryByTestId('lt-zf-empty-pankaj')).toBeNull();
  });
  it('the data-section order is unchanged with the bar mounted (the bar carries none)', async () => {
    const { container } = await mount();
    const order = [...container.querySelectorAll('[data-section]')].map((n) => n.getAttribute('data-section'));
    expect(order).toEqual(['header', 'digest', 'zones', 'started_moving', 'changed',
      'category', 'category', 'category', 'category', 'forward', 'history', 'rules']);
    expect(screen.getByTestId('lt-zf-bar').hasAttribute('data-section')).toBe(false);
    expect(screen.getByTestId('lt-header').nextElementSibling).toBe(screen.getByTestId('lt-zf-bar'));
  });
  it('NEGATIVE: no testid collision — lt-zone-TSM is the 🧭 strip\'s ONE node; no lt-zone-<sym> for a row off the strip', async () => {
    const p = clone(fixture) as any;
    delete p.zones.alert;
    const { container } = await mount(p);
    expect(screen.getAllByTestId('lt-zone-TSM')).toHaveLength(1);
    expect(screen.getByTestId('lt-zone-TSM').tagName).toBe('LI');
    const strip = new Set(p.zones.at_zone.map((z: any) => `lt-zone-${z.symbol}`));
    for (const s of SAVED) {
      const id = `lt-zone-${s}`;
      if (!strip.has(id)) expect(container.querySelector(`[data-testid="${id}"]`), id).toBeNull();
    }
    const ids = [...container.querySelectorAll('[data-testid^="lt-zone-"]')].map((n) => n.getAttribute('data-testid'));
    for (const id of ids) expect(strip.has(id), String(id)).toBe(true);
  });
  it('NEGATIVE: no "NaN" / "undefined" / "null" / "Infinity" on the page, OFF and ON, live or not', async () => {
    const { container } = await mount(fixture, LIVE());
    await waitFor(() => expect(cell('TSM').textContent).toContain('live'));
    expect(container.textContent).not.toMatch(/NaN|Infinity|undefined|\bnull\b/);
    tick();
    expect(container.textContent).not.toMatch(/NaN|Infinity|undefined|\bnull\b/);
  });
  it('NEGATIVE: rendered text minus the one allowed sentence has no banned word and no b-word (OFF and ON)', async () => {
    const { container } = await mount(fixture, LIVE());
    tick();
    const text = (container.textContent || '').replace(NOT_A_SIGNAL, '');
    expect(text).not.toMatch(BANNED);
    expect(text).not.toMatch(/bounce/i);
    expect(R.text).not.toMatch(BANNED);
  });
  it('NEGATIVE: no digit in a JSX text literal of LtZoneFilterBar.tsx (every count is served)', async () => {
    const src = (await readSource('src/components/LtZoneFilterBar.tsx'))
      .replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
    const literals = [...src.matchAll(/>([^<>{}]*)[<{]/g), ...src.matchAll(/\}([^<>{}]*)[<{]/g)].map((m) => m[1]).filter((t) => t.trim());
    expect(literals.length).toBeGreaterThan(0);
    for (const t of literals) expect(t, t).not.toMatch(/\d/);
  });
  it('source guards: saved-order phrase, no house filter name, one room call, no storage in the board, ids only lt-zf / lt-zcell', async () => {
    const board = await readSource('src/components/LongTermBoard.tsx');
    expect(board).toContain('his saved list keeps its saved order');
    expect(board).toContain('the 🎯 zone checkbox is a stable filter over the saved rows — it never reorders them');
    expect(board).not.toMatch(/EnterableFilter|enterableFilter/);
    expect(board.match(/useBounceRoom\(/g)).toHaveLength(1);
    expect(board).not.toMatch(/localStorage/);
    /* the pre-build count of `lt-zone-` in LongTermBoard.tsx (the 🧭 strip / 🔔 ids only) — 12 at HEAD 25bb584a */
    expect((board.match(/lt-zone-/g) || []).length).toBe(12);
    const lib = await readSource('src/lib/ltZones.ts');
    expect((lib.match(/try \{/g) || []).length).toBeGreaterThanOrEqual(2);
    const bar = await readSource('src/components/LtZoneFilterBar.tsx');
    expect(bar).not.toContain('lt-zone-');
    expect(bar.replace(NOT_A_SIGNAL, '')).not.toMatch(BANNED);
    expect(bar).not.toMatch(/\bbounce\b/i);
    expect(bar).not.toMatch(/EnterableFilter|enterableFilter/);
  });
});
