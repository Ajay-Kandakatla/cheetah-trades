import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import onOpen from './__fixtures__/gajjala_on_open_golden_2026_10_15.json';
import potGolden from './__fixtures__/gajjala_potential_golden_2026_10_15.json';
import trGolden from './__fixtures__/gajjala_track_record_golden_2026_10_16.json';
import hand from './__fixtures__/gajjala_board_2026_10_13.json';
import type { CurrentUser } from '../hooks/useUser';

/* 🚫 Broker tag on Gajjala's board (2026-10-17, BUILD_SPEC12 §3.9 / §4 WP-B, AMENDMENTS12 F2 / F5).
 *
 * Ajay: his second and third lines of the ask (DECISIONS12 §The ask) — quoted verbatim in lib/gajjala.ts and the ✨
 * entry. A TAG, never a filter: nothing is hidden.
 *
 * Boards come from the GOLDEN fixtures the backend writes AS THE OWNER (tests/test_gajjala_on_open.py,
 * tests/test_gajjala_potential_tab.py, tests/test_gajjala_track_record_tab.py — the served payload, never typed), plus
 * in-file clones that put the SERVED tag (the golden block's own `text`) on one row of each kind. What is pinned: the
 * owner strip prints the served words only; ✕ → ONE DELETE then ONE board re-read; add → ONE POST then ONE re-read; one
 * write at a time (a double click sends ONE request, F2); the form never reloads the page; a served fault line replaces
 * the add box (F5); every surface prints the served tag verbatim beside its symbol and the pinned elements keep their
 * served text; the icon-only card toggle. NEGATIVES: mounting never calls the broker route; a 400 prints the served
 * detail and never re-reads; a 404 prints nothing; a row without `broker_text` gets no chip; a non-owner payload
 * (`broker_flags: null`) or an older API renders no strip, no toggle and no chip, and writes nothing. */

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
const TR: Record<string, any> = (trGolden as any).boards;
const HAND: Record<string, any> = (hand as any).boards;
const clone = (x: any) => JSON.parse(JSON.stringify(x));

const RECIPE = 'the goldens predate the 🚫 tag — regenerate them (never hand-edit): GG_WRITE_GOLDEN=1 python -m pytest '
  + 'tests/test_gajjala_on_open.py tests/test_gajjala_potential_tab.py tests/test_gajjala_track_record_tab.py -k golden';
/** The owner block as the backend served it — every word the strip / toggle / chip prints comes from here. */
const BLOCK = (): any => {
  const b = OPEN.bull_flag?.broker_flags;
  if (!b || typeof b !== 'object') throw new Error(RECIPE);
  return b;
};
const TAG = (): string => BLOCK().text;

const OWNER: CurrentUser = {
  email: 'owner@example.com', display_name: 'Owner', given_name: 'Owner', picture: null,
  is_default_user: false, is_admin: true,
};

type Call = { method: string; path: string; url: string; init?: RequestInit };
let calls: Call[] = [];
type Answer = { ok: boolean; status: number; body?: any } | (() => Promise<{ ok: boolean; status: number; body?: any }>);
let brokerAnswer: Answer = { ok: true, status: 200, body: {} };
function stub(getBoard: (n: number, u: URL) => any) {
  calls = [];
  const spy = vi.fn(async (url: string, init?: RequestInit) => {
    const u = new URL(String(url), 'http://x');
    const method = String(init?.method || 'GET').toUpperCase();
    calls.push({ method, path: u.pathname, url: String(url), init });
    if (u.pathname.endsWith('/chart-maps/gajjala/scan')) return { ok: false, status: 404, json: async () => ({ detail: 'Not Found' }) };
    if (u.pathname.includes('/chart-maps/gajjala/broker-flags')) {
      const a = typeof brokerAnswer === 'function' ? await brokerAnswer() : brokerAnswer;
      return { ok: a.ok, status: a.status, json: async () => clone(a.body ?? {}) };
    }
    return { ok: true, status: 200, json: async () => clone(getBoard(gets().length, u)) };
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}
const gets = () => calls.filter((c) => c.method === 'GET' && c.path.endsWith('/chart-maps/gajjala'));
const brokers = () => calls.filter((c) => c.path.includes('/chart-maps/gajjala/broker-flags'));
const sleep = (ms: number) => act(() => new Promise<void>((r) => setTimeout(r, ms)));
const mount = (q = 'tab=gajjala&sub=bull_flag') =>
  render(<MemoryRouter initialEntries={[`/chart-maps?${q}`]}><GajjalaBoard /></MemoryRouter>);
const withSyms = (b: any, symbols: string[]) => { const c = clone(b); c.broker_flags = { ...BLOCK(), symbols }; return c; };
/** As the server serves it: the list AND the tile tag come from ONE flags set (tab.broker_text_for folds "." / "-"). */
const fold = (s: string) => String(s).toUpperCase().replace(/\./g, '-');
const withTagged = (b: any, symbols: string[]) => {
  const c = withSyms(b, symbols);
  const on = new Set(symbols.map(fold));
  for (const t of c.tiles || []) if (on.has(fold(t.symbol))) t.broker_text = TAG();
  return c;
};
const chipCount = (c: HTMLElement) => c.querySelectorAll('.gg-broker').length;

describe('GajjalaBoard — 🚫 broker tag (owner strip)', () => {
  beforeEach(() => { userRet = null; brokerAnswer = { ok: true, status: 200, body: {} }; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('the goldens carry the owner block and the per-row key (regenerated by WP-A)', () => {
    for (const [name, b] of [['on-open bull_flag', OPEN.bull_flag], ['potential bull_flag', POT.bull_flag],
                             ['potential 🧠', POT.potential], ['track record 5d', TR['5d']]] as const) {
      expect(b && typeof b === 'object' && 'broker_flags' in b, `${name}: ${RECIPE}`).toBe(true);
    }
    expect(BLOCK().editable).toBe(true);
    expect(BLOCK().symbols).toEqual([]);
    expect(JSON.stringify(onOpen).includes('"broker_text"'), RECIPE).toBe(true);
  });

  it('owner golden: the strip prints the served text, the served empty line and the served placeholder; NEGATIVE mounting never calls /broker-flags and adds no GET', async () => {
    stub(() => OPEN.bull_flag);
    mount();
    const strip = await screen.findByTestId('gg-broker-strip');
    await sleep(40);
    expect(within(strip).getByTestId('gg-broker-text').textContent).toBe(BLOCK().text);
    expect(within(strip).getByTestId('gg-broker-empty').textContent).toBe(BLOCK().empty_text);
    const input = within(strip).getByTestId('gg-broker-input') as HTMLInputElement;
    expect(input.getAttribute('placeholder')).toBe(BLOCK().add_placeholder);
    expect(input.getAttribute('aria-label')).toBe(BLOCK().add_placeholder);
    expect(within(strip).getByTestId('gg-broker-add').textContent).toBe(BLOCK().add_label);
    expect(within(strip).queryByTestId('gg-broker-fault')).toBeNull();
    expect(within(strip).queryByTestId('gg-broker-err')).toBeNull();
    expect(brokers()).toHaveLength(0);
    expect(gets()).toHaveLength(1);
    // the golden tags nothing (his list is empty): no chip anywhere
    expect(chipCount(document.body)).toBe(0);
  });

  it('✕ → ONE DELETE …/broker-flags/ABCD with credentials include, then ONE board re-read', async () => {
    stub(() => withSyms(OPEN.bull_flag, ['ABCD']));
    mount();
    const sym = await screen.findByTestId('gg-broker-sym-ABCD');
    expect(sym.textContent).toBe('ABCD✕');
    const del = screen.getByTestId('gg-broker-del-ABCD');
    expect(del.getAttribute('title')).toBe(BLOCK().remove_title);
    expect(del.getAttribute('aria-label')).toBe(BLOCK().remove_title);
    expect(screen.queryByTestId('gg-broker-empty')).toBeNull();
    fireEvent.click(del);
    await waitFor(() => expect(gets()).toHaveLength(2));
    await sleep(40);
    expect(brokers()).toHaveLength(1);
    const c = brokers()[0];
    expect(c.method).toBe('DELETE');
    expect(c.path.endsWith('/chart-maps/gajjala/broker-flags/ABCD')).toBe(true);
    expect(c.init?.credentials).toBe('include');
    expect(c.init?.body).toBeUndefined();
    expect(gets()).toHaveLength(2);
  });

  it('add: "abcd" + Enter → ONE POST body {"symbol":"abcd"} (sent as typed, credentials include), then ONE re-read; the form never reloads (preventDefault)', async () => {
    stub(() => OPEN.bull_flag);
    mount();
    const input = await screen.findByTestId('gg-broker-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '  abcd ' } });
    const form = input.closest('form')!;
    expect(fireEvent.submit(form)).toBe(false);                    // default prevented — Enter never reloads the page
    await waitFor(() => expect(gets()).toHaveLength(2));
    await sleep(40);
    expect(brokers()).toHaveLength(1);
    const c = brokers()[0];
    expect(c.method).toBe('POST');
    expect(c.path.endsWith('/chart-maps/gajjala/broker-flags')).toBe(true);
    expect(c.init?.body).toBe('{"symbol":"abcd"}');
    expect(c.init?.credentials).toBe('include');
    expect((c.init?.headers as Record<string, string>)['Content-Type']).toBe('application/json');
    expect(gets()).toHaveLength(2);
    expect((screen.getByTestId('gg-broker-input') as HTMLInputElement).value).toBe('');
  });

  it('the add button submits the same ONE POST', async () => {
    stub(() => OPEN.bull_flag);
    mount();
    const input = await screen.findByTestId('gg-broker-input');
    fireEvent.change(input, { target: { value: 'WXYZ' } });
    fireEvent.click(screen.getByTestId('gg-broker-add'));
    await waitFor(() => expect(gets()).toHaveLength(2));
    expect(brokers().map((c) => [c.method, c.init?.body])).toEqual([['POST', '{"symbol":"WXYZ"}']]);
  });

  it('NEGATIVE an empty add field sends nothing', async () => {
    stub(() => OPEN.bull_flag);
    mount();
    const input = await screen.findByTestId('gg-broker-input');
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.submit(input.closest('form')!);
    await sleep(60);
    expect(brokers()).toHaveLength(0);
    expect(gets()).toHaveLength(1);
  });

  it('NEGATIVE a 400 prints the SERVED detail and never re-reads', async () => {
    brokerAnswer = { ok: false, status: 400, body: { detail: 'served bad-symbol line' } };
    stub(() => OPEN.bull_flag);
    mount();
    const input = await screen.findByTestId('gg-broker-input');
    fireEvent.change(input, { target: { value: '1BAD' } });
    fireEvent.submit(input.closest('form')!);
    expect((await screen.findByTestId('gg-broker-err')).textContent).toBe('served bad-symbol line');
    await sleep(60);
    expect(brokers()).toHaveLength(1);
    expect(gets()).toHaveLength(1);
  });

  it('NEGATIVE a 503 without a string detail prints nothing (the FE types no word) and never re-reads', async () => {
    brokerAnswer = { ok: false, status: 503, body: { detail: 5 } };
    stub(() => withSyms(OPEN.bull_flag, ['ABCD']));
    mount();
    fireEvent.click(await screen.findByTestId('gg-broker-del-ABCD'));
    await sleep(80);
    expect(brokers()).toHaveLength(1);
    expect(screen.queryByTestId('gg-broker-err')).toBeNull();
    expect(gets()).toHaveLength(1);
  });

  it('NEGATIVE a 404 prints nothing and never re-reads', async () => {
    brokerAnswer = { ok: false, status: 404, body: { detail: 'Not Found' } };
    stub(() => withSyms(OPEN.bull_flag, ['ABCD']));
    mount();
    fireEvent.click(await screen.findByTestId('gg-broker-del-ABCD'));
    await sleep(80);
    expect(brokers()).toHaveLength(1);
    expect(screen.queryByTestId('gg-broker-err')).toBeNull();
    expect(gets()).toHaveLength(1);
  });

  it('F2: one write at a time — every broker control is disabled while a write is in flight; NEGATIVE a double click / double Enter sends ONE request', async () => {
    let release: (v: { ok: boolean; status: number; body?: any }) => void = () => undefined;
    brokerAnswer = () => new Promise((r) => { release = r; });
    stub(() => withSyms(OPEN.bull_flag, ['ABCD']));
    mount();
    const del = await screen.findByTestId('gg-broker-del-ABCD');
    fireEvent.click(del);
    fireEvent.click(del);
    const toggle = screen.getByTestId('gg-broker-toggle-GGA');
    fireEvent.click(toggle);
    const input = screen.getByTestId('gg-broker-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: 'WXYZ' } });
    fireEvent.submit(input.closest('form')!);
    fireEvent.submit(input.closest('form')!);
    await sleep(30);
    expect(brokers()).toHaveLength(1);
    for (const id of ['gg-broker-del-ABCD', 'gg-broker-input', 'gg-broker-add', 'gg-broker-toggle-GGA']) {
      expect((screen.getByTestId(id) as HTMLButtonElement).disabled, id).toBe(true);
    }
    await act(async () => { release({ ok: true, status: 200, body: {} }); });
    await waitFor(() => expect(gets()).toHaveLength(2));
    await sleep(30);
    expect(brokers()).toHaveLength(1);
    expect((screen.getByTestId('gg-broker-del-ABCD') as HTMLButtonElement).disabled).toBe(false);
  });

  it('F5: a served fault line replaces the add box — no input, no ✕, no toggle, never the empty line', async () => {
    stub(() => {
      const b = clone(OPEN.bull_flag);
      const blk: any = { ...BLOCK(), editable: false, symbols: ['SEED'], fault_text: 'served fault line' };
      delete blk.empty_text;                                       // F5: a fault never serves the empty line
      b.broker_flags = blk;
      return b;
    });
    mount();
    const strip = await screen.findByTestId('gg-broker-strip');
    expect(within(strip).getByTestId('gg-broker-fault').textContent).toBe('served fault line');
    expect(within(strip).getByTestId('gg-broker-text').textContent).toBe(BLOCK().text);
    expect(within(strip).getByTestId('gg-broker-sym-SEED').textContent).toBe('SEED');
    expect(within(strip).queryByTestId('gg-broker-del-SEED')).toBeNull();
    expect(within(strip).queryByTestId('gg-broker-input')).toBeNull();
    expect(within(strip).queryByTestId('gg-broker-add')).toBeNull();
    expect(within(strip).queryByTestId('gg-broker-empty')).toBeNull();
    expect(screen.queryByTestId('gg-broker-toggle-GGA')).toBeNull();
    expect(brokers()).toHaveLength(0);
  });

  it('NEGATIVE editable false with no fault line → no strip at all', async () => {
    stub(() => { const b = clone(OPEN.bull_flag); b.broker_flags = { ...BLOCK(), editable: false }; return b; });
    mount();
    await screen.findByTestId('gg-tile-GGA');
    expect(screen.queryByTestId('gg-broker-strip')).toBeNull();
    expect(screen.queryByTestId('gg-broker-toggle-GGA')).toBeNull();
  });
});

describe('GajjalaBoard — 🚫 the card toggle', () => {
  beforeEach(() => { userRet = null; brokerAnswer = { ok: true, status: 200, body: {} }; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('one icon-only toggle per tile, the served title / label / icon, aria-pressed == the served tag', async () => {
    stub(() => withTagged(POT.bull_flag, ['JJJ']));
    mount();
    await screen.findByTestId('gg-tile-AAA');
    const tiles: string[] = POT.bull_flag.tiles.map((t: any) => t.symbol);
    expect(document.querySelectorAll('.gg-broker-toggle').length).toBe(tiles.length);
    for (const s of tiles) {
      const t = within(screen.getByTestId(`gg-tile-${s}`)).getByTestId(`gg-broker-toggle-${s}`);
      expect(t.getAttribute('title')).toBe(BLOCK().text);
      expect(t.getAttribute('aria-label')).toBe(BLOCK().text);
      expect(t.textContent).toBe(BLOCK().toggle);
      expect(t.getAttribute('aria-pressed')).toBe(String(s === 'JJJ'));
    }
  });

  it('an unflagged card → POST {symbol: SYM}; a flagged card → DELETE …/SYM; each then ONE re-read', async () => {
    stub(() => withTagged(POT.bull_flag, ['JJJ']));
    mount();
    fireEvent.click(await screen.findByTestId('gg-broker-toggle-AAA'));
    await waitFor(() => expect(gets()).toHaveLength(2));
    fireEvent.click(screen.getByTestId('gg-broker-toggle-JJJ'));
    await waitFor(() => expect(gets()).toHaveLength(3));
    expect(brokers().map((c) => [c.method, c.path.split('/chart-maps/gajjala/')[1], c.init?.body])).toEqual([
      ['POST', 'broker-flags', '{"symbol":"AAA"}'],
      ['DELETE', 'broker-flags/JJJ', undefined],
    ]);
  });

  it('F8 fold (critic 2026-10-17): his list holds MOG.A, the tile is MOG-A — the toggle reads the SERVED tag: aria-pressed true, click → DELETE …/MOG-A', async () => {
    const b = clone(POT.bull_flag);
    b.tiles.find((t: any) => t.symbol === 'JJJ').symbol = 'MOG-A';
    stub(() => withTagged(b, ['MOG.A']));
    mount();
    const t = await screen.findByTestId('gg-broker-toggle-MOG-A');
    expect(t.getAttribute('aria-pressed')).toBe('true');
    expect(within(screen.getByTestId('gg-tile-MOG-A')).getByTestId('gg-broker-tile-MOG-A').textContent).toBe(TAG());
    fireEvent.click(t);
    await waitFor(() => expect(gets()).toHaveLength(2));
    expect(brokers().map((c) => [c.method, c.path.split('/chart-maps/gajjala/')[1]])).toEqual([['DELETE', 'broker-flags/MOG-A']]);
  });

  it('NEGATIVE the list alone never lights a toggle — only the served tile tag does (the FE re-derives nothing)', async () => {
    stub(() => withSyms(POT.bull_flag, ['JJJ']));
    mount();
    expect((await screen.findByTestId('gg-broker-toggle-JJJ')).getAttribute('aria-pressed')).toBe('false');
    expect(screen.queryByTestId('gg-broker-tile-JJJ')).toBeNull();
  });
});

describe('GajjalaBoard — 🚫 the served chip on every surface', () => {
  beforeEach(() => { userRet = null; });
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  it('setup tile + 🎯 row + 🪦 graveyard (on-open bull_flag clone): each chip == the served tag; the pinned elements keep their text', async () => {
    const b = withSyms(OPEN.bull_flag, ['GGA', 'ZZZ']);
    b.tiles[0].broker_text = TAG();
    b.enterable.rows[0].broker_text = TAG();
    b.graveyard_today = ['ZZZ'];
    b.graveyard_text = 'served graveyard line: ZZZ';
    b.graveyard_broker_text = `${TAG()}: ZZZ`;
    stub(() => b);
    const { container } = mount();
    const tile = await screen.findByTestId('gg-broker-tile-GGA');
    expect(tile.textContent).toBe(TAG());
    expect(within(screen.getByTestId('gg-chips-GGA')).getByTestId('gg-broker-tile-GGA')).toBe(tile);
    const r = b.enterable.rows[0];
    const id = `${r.symbol}-${r.setup}`;
    expect(screen.getByTestId(`gg-broker-aplus-${id}`).textContent).toBe(TAG());
    expect(screen.getByTestId(`gg-aplus-row-${id}`).textContent).toBe(r.text);
    expect(document.querySelectorAll('[data-testid^="gg-aplus-row-"]').length).toBe(b.enterable.rows.length);
    expect(screen.getByTestId('gg-graveyard').textContent).toBe('served graveyard line: ZZZ');
    expect(screen.getByTestId('gg-graveyard-broker').textContent).toBe(`${TAG()}: ZZZ`);
    expect(chipCount(container)).toBe(2);                          // .gg-broker = the two row tags (the graveyard is a line)
    // the prefix counters never see a broker element (no broker testid starts gg-tile- / gg-aplus-row-)
    for (const sel of ['[data-testid^="gg-tile-"]', '[data-testid^="gg-aplus-row-"]']) {
      expect([...document.querySelectorAll(sel)].some((e) => /broker/.test(e.getAttribute('data-testid') || ''))).toBe(false);
    }
  });

  it('🧠 strip row (potential bull_flag clone): chip after the row button, the row keeps its served line + tells', async () => {
    const b = withSyms(POT.bull_flag, ['JJJ']);
    const r = b.potential.rows.find((x: any) => x.symbol === 'JJJ');
    r.broker_text = TAG();
    stub(() => b);
    const { container } = mount();
    const chip = await screen.findByTestId(`gg-broker-pot-JJJ-${r.setup}`);
    expect(chip.textContent).toBe(TAG());
    const row = screen.getByTestId('gg-potential-row-JJJ');
    expect(row.textContent).toBe(r.text + (r.tells || []).map((t: any) => t.text).join(''));
    expect(row.contains(chip)).toBe(false);
    expect(chipCount(container)).toBe(1);
    expect(screen.queryByTestId('gg-broker-pot-AAA-bull_flag')).toBeNull();   // NEGATIVE the unflagged row
  });

  it('📈 Track row + 👀 watch symbol (🧠 sub clone): chips beside the link, the link text unchanged', async () => {
    const b = withSyms(POT.potential, ['DDD', 'PMX']);
    const tr = b.track.today.rows[0];
    tr.broker_text = TAG();
    b.watch.symbols[0].broker_text = TAG();
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=potential');
    const id = `${tr.symbol}-${tr.setup}`;
    const chip = await screen.findByTestId(`gg-broker-track-${id}`);
    expect(chip.textContent).toBe(TAG());
    expect(screen.getByTestId(`gg-track-row-${id}`).querySelector('a.gg-track-text')!.textContent).toBe(tr.text);
    const w = b.watch.symbols[0];
    expect(screen.getByTestId(`gg-broker-watch-${w.symbol}`).textContent).toBe(TAG());
    expect(screen.getByTestId(`gg-watch-tk-${w.symbol}`).textContent).toBe(w.symbol);
    expect(screen.queryByTestId(`gg-broker-watch-${b.watch.symbols[1].symbol}`)).toBeNull();
    expect(chipCount(container)).toBe(2);
  });

  it('🌙 recap row (post-market clone): chip after the row, the row text unchanged', async () => {
    const b = clone(HAND.postmarket);
    b.broker_flags = { ...BLOCK(), symbols: ['PFAI'] };
    const r = b.postmarket.recap.rows[0];
    r.broker_text = TAG();
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=postmarket');
    const id = `${r.symbol}-${r.setup ?? ''}`;
    const chip = await screen.findByTestId(`gg-broker-recap-${id}`);
    expect(chip.textContent).toBe(TAG());
    expect(screen.getByTestId(`gg-recap-row-${id}`).textContent).toBe(`${r.symbol} ${r.text}${TAG()}`);
    expect(chipCount(container)).toBe(1);
  });

  it('🏁 Track record row (track-record golden clone): chip in the symbol cell beside the link, the link text unchanged', async () => {
    const b = withSyms(TR['5d'], ['XLAB']);
    const rows = b.track_record.days.flatMap((d: any) => d.rows);
    const row = rows.find((x: any) => x.symbol === 'XLAB');
    row.broker_text = TAG();
    stub(() => b);
    const { container } = mount('tab=gajjala&sub=track_record&span=5d');
    const chip = await screen.findByTestId(`gg-tr-broker-${row.key}`);
    expect(chip.textContent).toBe(TAG());
    const tr = screen.getByTestId(`gg-tr-row-${row.key}`);
    expect(tr.contains(chip)).toBe(true);
    expect(chip.closest('td')!.querySelector('a')!.textContent).toBe('XLAB');
    expect(chipCount(container)).toBe(1);                          // NEGATIVE every other row: no chip
  });
});

describe('GajjalaBoard — 🚫 NEGATIVES: a non-owner and an older API see nothing', () => {
  afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); userRet = null; });

  const nonOwner = (b: any) => {
    const c = clone(b);
    c.broker_flags = null;
    const walk = (x: any) => {
      if (Array.isArray(x)) x.forEach(walk);
      else if (x && typeof x === 'object') for (const k of Object.keys(x)) { if (k === 'broker_text') x[k] = null; else walk(x[k]); }
    };
    walk(c);
    return c;
  };

  for (const [name, q, b] of [
    ['bull_flag', 'tab=gajjala&sub=bull_flag', () => OPEN.bull_flag],
    ['🧠 potential', 'tab=gajjala&sub=potential', () => POT.potential],
    ['🏁 track record', 'tab=gajjala&sub=track_record&span=5d', () => TR['5d']],
  ] as const) {
    it(`non-owner payload (${name}): no strip, no toggle, no chip, zero broker writes — even for an is_admin user`, async () => {
      userRet = OWNER;
      stub(() => nonOwner(b()));
      const { container } = mount(q);
      await waitFor(() => expect(container.querySelector('.gg-board')!.getAttribute('data-state')).toBe('loaded'));
      await sleep(40);
      expect(screen.queryByTestId('gg-broker-strip')).toBeNull();
      expect(container.querySelectorAll('.gg-broker-toggle').length).toBe(0);
      expect(chipCount(container)).toBe(0);
      expect(brokers()).toHaveLength(0);
    });
  }

  it('the hand fixture (an older API, no broker keys) renders nothing of the tag', async () => {
    userRet = OWNER;
    stub(() => HAND.bull_flag);
    const { container } = mount();
    await screen.findByTestId('gg-strip');
    await waitFor(() => expect(container.querySelector('.gg-board')!.getAttribute('data-state')).toBe('loaded'));
    expect(screen.queryByTestId('gg-broker-strip')).toBeNull();
    expect(container.querySelectorAll('.gg-broker-toggle, .gg-broker').length).toBe(0);
    expect(brokers()).toHaveLength(0);
  });

  it('a chip is never composed: an empty / non-string broker_text prints nothing', async () => {
    const b = withSyms(OPEN.bull_flag, []);
    b.tiles[0].broker_text = '  ';
    b.enterable.rows[0].broker_text = 5;
    stub(() => b);
    const { container } = mount();
    await screen.findByTestId('gg-tile-GGA');
    expect(chipCount(container)).toBe(0);
  });
});
