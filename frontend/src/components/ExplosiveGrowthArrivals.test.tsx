import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { ExplosiveGrowth, stagedFilter, type GrowthRow, type StagedFilterOpts } from './ExplosiveGrowth';
import { passesDebtFilter, type DebtTier } from '../lib/balanceRead';
import { DEFAULT_SORT, DEFAULT_DIR, sortRows } from '../lib/growthSort';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';

/* ✨ Growth arrivals on the 🚀 Explosive Growth board (2026-10-12, spec P3).
 *
 * Ajay 2026-10-12: "... special emphasis wiht a tag or something ... and also
 * in the explosive growth too" / "I saw an alert for 7 in explosive growth".
 *
 * The pins: the four local filters were split into `stagedFilter` WITHOUT a
 * behaviour change; the ✨ tag renders only off the served flag + date; the
 * tag changes no order; ?focus= (and the push's &symbol=) highlights and
 * scrolls once; a hidden NEW name is blamed on the FIRST of his controls that
 * dropped it, with a one-click un-hide; the arrivals line is folded and
 * carries the served note verbatim. */

async function readSource(rel: string): Promise<string> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  const fs: any = mod?.default || mod;
  const root = (globalThis as any).process?.cwd?.() || '.';
  return fs.readFileSync(`${root}/${rel}`, 'utf8');
}

function row(over: Partial<GrowthRow> = {}): GrowthRow {
  return {
    symbol: 'AXTI', name: 'AXT Inc', price: 64.77, market_cap: 3.95e9,
    avg_dollar_vol: 41_000_000, liquid: true, promo_tagged: false,
    sales_growth_pct: 145.9, sales_prior_pct: 7.2, q_eps_growth_pct: 185.0,
    npm_latest_pct: 27.4, npm_expanding: true,
    sector: 'Technology', industry: 'Semiconductor Equipment & Materials',
    zone: { missing: false, in_band: true, intact: true,
            band: { lo: 60, hi: 62, touches: 3 }, order_block: false },
    warnings: [],
    ...over,
  };
}

const GROUPS = [
  { group: 'Technology', n: 4, n_scanned: 493, hit_rate_pct: 1.0,
    median_sales_growth_pct: 144.0, industries: [], symbols: ['AXTI'] },
  { group: 'Healthcare', n: 1, n_scanned: 629, hit_rate_pct: 0.2,
    median_sales_growth_pct: 300.0, industries: [], symbols: ['MGNX'] },
];

const STAMP = '2026-10-12T02:29:05+00:00';
const TRACKING_SINCE = '2026-09-12T19:51:22.782601+00:00';
const REFUSE = '⛔ $284M cap is under the $700M floor every other board uses — the engine will REFUSE to buy it';

type Extra = Record<string, unknown>;

function payload(rows: GrowthRow[], extra: Extra = {}) {
  return {
    rows, n: rows.length, groups: GROUPS, built_at: '2026-10-12T02:29:00',
    screen: { min_sales_growth_pct: 100, min_eps_growth_pct: 100,
              min_prior_sales_pct: 0, cap_floor: null, universe_mode: 'broad' },
    disclaimer: 'Discovery list, NOT a signal.',
    ...extra,
  };
}

/** Growth payload on /growth/board; the bounce-room POST gets `room` (or an
 *  empty read). */
function stub(rows: GrowthRow[], extra: Extra = {}, room: unknown = { rows: {}, pending: 0 }) {
  const spy = vi.fn(async (url: string) => {
    const u = String(url);
    if (u.includes('/supply-demand/bounce-room')) {
      return { ok: true, status: 200, json: async () => room } as unknown as Response;
    }
    return { ok: true, status: 200, json: async () => payload(rows, extra) } as unknown as Response;
  });
  vi.stubGlobal('fetch', spy);
  return spy;
}

function mount(path = '/chart-maps?tab=growth') {
  return render(
    <MemoryRouter initialEntries={[path]}><ExplosiveGrowth /></MemoryRouter>);
}

/** Data-row symbols in render order. */
const tickers = () => Array.from(
  document.querySelectorAll('tbody tr td:first-child a')).map((a) => a.textContent?.trim());

const debtSelect = () => Array.from(document.querySelectorAll('select'))
  .find((el) => Array.from(el.options).some((o) => o.value === 'all')) as HTMLSelectElement;

beforeEach(() => {
  _resetBounceRoomCache();
  try { localStorage.clear(); } catch { /* jsdom always has it */ }
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); _resetBounceRoomCache(); });

/* ── 3.9a: the staged filter ─────────────────────────────────────────────── */

/** The PRE-CHANGE inline chain, copied verbatim from ExplosiveGrowth.tsx
 *  `sortedRows` at 3259f97c (lines 357-361) — the behaviour pin. */
function preChange(rows: GrowthRow[], o: StagedFilterOpts): GrowthRow[] {
  const { onlyBuyable, onlyDemand, sector, debtTier } = o;
  let r = rows;
  if (onlyBuyable) r = r.filter((x) => !(x.warnings ?? []).some((w) => w.startsWith('⛔')));
  if (onlyDemand) r = r.filter((x) => x.zone?.in_band && x.zone?.intact);
  if (sector) r = r.filter((x) => (x.sector || '(unmapped)') === sector);
  if (debtTier) r = r.filter((x) => passesDebtFilter(x, debtTier as DebtTier));
  return r;
}

/* Each stage drops exactly one distinct row; E and F survive everything. */
const SIX: GrowthRow[] = [
  row({ symbol: 'AREF', warnings: [REFUSE] }),                                        // refused
  row({ symbol: 'BDEM', zone: { missing: false, in_band: true, intact: false } }),     // demand
  row({ symbol: 'CSEC', sector: 'Healthcare' }),                                       // sector
  row({ symbol: 'DDBT', cash: 10e6, debt: 1e9 }),                                      // debt (levered)
  row({ symbol: 'ESUR' }),
  row({ symbol: 'FSUR', cash: 100e6, debt: 0 }),
];
const ALL_ON: StagedFilterOpts = { onlyBuyable: true, onlyDemand: true, sector: 'Technology', debtTier: 'net cash' };
const ALL_OFF: StagedFilterOpts = { onlyBuyable: false, onlyDemand: false, sector: null, debtTier: null };
const syms = (rs: readonly GrowthRow[]) => rs.map((r) => r.symbol);

describe('stagedFilter — the behaviour-preserving split (C2)', () => {
  it('all four ON equals the pre-change inline chain, symbol for symbol', () => {
    const got = stagedFilter(SIX, ALL_ON);
    expect(syms(got.rows)).toEqual(syms(preChange(SIX, ALL_ON)));
    expect(syms(got.rows)).toEqual(['ESUR', 'FSUR']);
  });

  it('every single-stage combination equals the pre-change chain', () => {
    const opts: StagedFilterOpts[] = [
      { ...ALL_OFF, onlyBuyable: true }, { ...ALL_OFF, onlyDemand: true },
      { ...ALL_OFF, sector: 'Technology' }, { ...ALL_OFF, debtTier: 'net cash' },
      { ...ALL_OFF, sector: '(unmapped)' }, { ...ALL_OFF, debtTier: 'debt-free' },
    ];
    for (const o of opts) expect(syms(stagedFilter(SIX, o).rows)).toEqual(syms(preChange(SIX, o)));
  });

  it('all four OFF → the input rows in the input order, and NO kept entry', () => {
    const got = stagedFilter(SIX, ALL_OFF);
    expect(got.rows).toEqual(SIX);
    expect(got.kept.size).toBe(0);
  });

  it('only onlyBuyable → kept has exactly `refused`', () => {
    const got = stagedFilter(SIX, { ...ALL_OFF, onlyBuyable: true });
    expect([...got.kept.keys()]).toEqual(['refused']);
  });

  it('kept keys are in the board order: refused, demand, sector, debt', () => {
    expect([...stagedFilter(SIX, ALL_ON).kept.keys()]).toEqual(['refused', 'demand', 'sector', 'debt']);
  });

  it('kept.get(stage) holds every survivor of THAT stage, including names a later stage drops', () => {
    const k = stagedFilter(SIX, ALL_ON).kept;
    expect([...k.get('refused')!]).toEqual(['BDEM', 'CSEC', 'DDBT', 'ESUR', 'FSUR']);
    expect([...k.get('demand')!]).toEqual(['CSEC', 'DDBT', 'ESUR', 'FSUR']);
    expect([...k.get('sector')!]).toEqual(['DDBT', 'ESUR', 'FSUR']);
    expect([...k.get('debt')!]).toEqual(['ESUR', 'FSUR']);
  });

  it('NEGATIVE: an OFF stage never appears in kept (cannot be blamed)', () => {
    const k = stagedFilter(SIX, { ...ALL_OFF, sector: 'Technology' }).kept;
    expect(k.has('refused')).toBe(false);
    expect(k.has('demand')).toBe(false);
    expect(k.has('debt')).toBe(false);
  });

  it('NEGATIVE: the input array is never mutated', () => {
    const input = Object.freeze([...SIX]) as readonly GrowthRow[];
    const before = syms(input);
    stagedFilter(input, ALL_ON);
    stagedFilter(input, ALL_OFF);
    expect(syms(input)).toEqual(before);
  });

  it('NEGATIVE: the rendered table with every local filter ON draws the pre-change set, sorted as before', async () => {
    stub(SIX);
    mount();
    await waitFor(() => expect(tickers().length).toBe(6));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /at demand, floor intact/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Technology' }));
    fireEvent.change(debtSelect(), { target: { value: 'net cash' } });
    const want = syms(sortRows(preChange(SIX, ALL_ON), DEFAULT_SORT, DEFAULT_DIR));
    await waitFor(() => expect(tickers()).toEqual(want));
  });
});

/* ── 3.9b: the ✨ NEW tag ────────────────────────────────────────────────── */

describe('✨ NEW tag on a row', () => {
  it('renders ✨ NEW · MM-DD with the full date on hover, only off the served flag + date', async () => {
    stub([row({ symbol: 'PGEN', is_new: true, first_seen: STAMP })]);
    mount();
    const tag = await screen.findByTestId('growth-new-PGEN');
    expect(tag.textContent).toBe('✨ NEW · 10-12');
    expect(tag.getAttribute('title')).toContain('2026-10-12');
    expect(tag.getAttribute('title')).toContain('not an entry');
    expect(tag.className).toBe('cm-badge cm-badge-new');
  });

  it('NEGATIVE: is_new false with a first_seen → no tag', async () => {
    stub([row({ symbol: 'PGEN', is_new: false, first_seen: STAMP })]);
    mount();
    await screen.findByText('PGEN');
    expect(screen.queryByTestId('growth-new-PGEN')).toBeNull();
  });

  it('NEGATIVE: is_new true with first_seen null → no tag', async () => {
    stub([row({ symbol: 'PGEN', is_new: true, first_seen: null })]);
    mount();
    await screen.findByText('PGEN');
    expect(screen.queryByTestId('growth-new-PGEN')).toBeNull();
  });

  it('NEGATIVE: the first cohort (first_seen == tracking_since, not new) → no tag', async () => {
    stub([row({ symbol: 'AXTI', is_new: false, first_seen: TRACKING_SINCE })]);
    mount();
    await screen.findByText('AXTI');
    expect(screen.queryByTestId('growth-new-AXTI')).toBeNull();
    expect(screen.queryByText(/✨ NEW/)).toBeNull();
  });

  it('NEGATIVE: an older payload with no arrival keys renders no tag and no arrivals UI', async () => {
    stub([row({ symbol: 'AXTI' })]);
    mount();
    await screen.findByText('AXTI');
    expect(screen.queryByText(/✨/)).toBeNull();
    expect(screen.queryByTestId('growth-arrivals-line')).toBeNull();
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
    expect(screen.queryByTestId('growth-focus-miss')).toBeNull();
  });

  it('NEGATIVE: no 🆕 glyph in the component source (C9)', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    expect(src).not.toContain('🆕');
  });
});

describe('✨ the tag changes no order', () => {
  const plain = [
    row({ symbol: 'AAA', sales_growth_pct: 300 }),
    row({ symbol: 'BBB', sales_growth_pct: 200 }),
    row({ symbol: 'CCC', sales_growth_pct: 100 }),
  ];
  const tagged = plain.map((r) => (r.symbol === 'BBB' ? { ...r, is_new: true, first_seen: STAMP } : r));

  it('tbody order is identical with and without the tag', async () => {
    stub(plain);
    mount();
    await waitFor(() => expect(tickers().length).toBe(3));
    const without = tickers();
    cleanup();
    stub(tagged);
    mount();
    await screen.findByTestId('growth-new-BBB');
    expect(tickers()).toEqual(without);
  });

  it('a header sort with tags present gives the same order as without', async () => {
    stub(plain);
    mount();
    await waitFor(() => expect(tickers().length).toBe(3));
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    const without = tickers();
    cleanup();
    stub(tagged);
    mount();
    await screen.findByTestId('growth-new-BBB');
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    expect(tickers()).toEqual(without);
  });
});

/* ── ?focus= / ?symbol= ─────────────────────────────────────────────────── */

describe('?focus= highlights and scrolls once', () => {
  let scroll: ReturnType<typeof vi.fn>;
  const proto = Element.prototype as unknown as { scrollIntoView?: unknown };
  const orig = proto.scrollIntoView;
  beforeEach(() => { scroll = vi.fn(); proto.scrollIntoView = scroll; });
  afterEach(() => { proto.scrollIntoView = orig; });

  const ROWS = [
    row({ symbol: 'AXTI', is_new: true, first_seen: STAMP }),
    row({ symbol: 'BBB', sales_growth_pct: 500, sector: 'Healthcare' }),
    row({ symbol: 'MGNX', warnings: [REFUSE], sales_growth_pct: 90 }),
  ];

  it('?focus=AXTI → the row carries cm-row-focus and is scrolled ONCE, not again on a filter toggle or sort', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=AXTI');
    const tr = await screen.findByTestId('growth-row-AXTI');
    expect(tr.className).toBe('cm-row-focus');
    expect(screen.getByTestId('growth-row-BBB').className).toBe('');
    await waitFor(() => expect(scroll).toHaveBeenCalledTimes(1));
    expect(scroll.mock.contexts?.[0] ?? tr).toBe(tr);
    const box = screen.getByRole('checkbox', { name: /hide what the engine refuses/ });
    fireEvent.click(box);
    fireEvent.click(box);
    fireEvent.click(screen.getByRole('button', { name: /Sales YoY/ }));
    // a filter that REMOVES the focused row and brings it back remounts it
    fireEvent.click(screen.getByRole('button', { name: 'Healthcare' }));
    await waitFor(() => expect(screen.queryByTestId('growth-row-AXTI')).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: 'Healthcare' }));
    await screen.findByTestId('growth-row-AXTI');
    expect(screen.getByTestId('growth-row-AXTI').className).toBe('cm-row-focus');
    expect(scroll).toHaveBeenCalledTimes(1);
  });

  it('?symbol=AXTI (the 08:08 push link) focuses too', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&symbol=AXTI');
    expect((await screen.findByTestId('growth-row-AXTI')).className).toBe('cm-row-focus');
    expect(scroll).toHaveBeenCalledTimes(1);
  });

  it('focus wins over symbol when both are present', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=AXTI&symbol=BBB');
    expect((await screen.findByTestId('growth-row-AXTI')).className).toBe('cm-row-focus');
    expect(screen.getByTestId('growth-row-BBB').className).toBe('');
  });

  it('a lower-case focus is normalised', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=axti');
    expect((await screen.findByTestId('growth-row-AXTI')).className).toBe('cm-row-focus');
  });

  it('NEGATIVE: ?focus=NOPE → the miss line, every row still drawn, nothing scrolled', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=NOPE');
    const miss = await screen.findByTestId('growth-focus-miss');
    expect(miss.textContent).toBe('✨ NOPE is not on this board today.');
    expect(tickers()).toHaveLength(3);
    expect(document.querySelector('.cm-row-focus')).toBeNull();
    expect(scroll).not.toHaveBeenCalled();
  });

  it('NEGATIVE: a malformed focus (../x) is ignored — no miss line, no highlight', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=..%2Fx');
    await waitFor(() => expect(tickers()).toHaveLength(3));
    expect(screen.queryByTestId('growth-focus-miss')).toBeNull();
    expect(document.querySelector('.cm-row-focus')).toBeNull();
  });

  it('NEGATIVE: no param → no class, no scroll, no miss line', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth');
    await waitFor(() => expect(tickers()).toHaveLength(3));
    expect(document.querySelector('.cm-row-focus')).toBeNull();
    expect(scroll).not.toHaveBeenCalled();
    expect(screen.queryByTestId('growth-focus-miss')).toBeNull();
  });

  it('NEGATIVE: a browser without scrollIntoView (jsdom) never throws', async () => {
    proto.scrollIntoView = undefined;
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=AXTI');
    expect((await screen.findByTestId('growth-row-AXTI')).className).toBe('cm-row-focus');
  });
});

/* ── the ✨ N new hidden line ────────────────────────────────────────────── */

describe('✨ N new hidden by his controls', () => {
  const MGNX = row({ symbol: 'MGNX', sector: 'Healthcare', warnings: [REFUSE],
                     is_new: true, first_seen: STAMP, sales_growth_pct: 400 });
  const PGEN = row({ symbol: 'PGEN', is_new: true, first_seen: STAMP, sales_growth_pct: 300 });
  const AXTI = row({ symbol: 'AXTI', sales_growth_pct: 200 });

  it('a new ⛔ row + "hide what the engine refuses" → 1 hidden, named by HIS control', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    const line = await screen.findByTestId('growth-new-hidden');
    expect(line.textContent).toBe('✨ 1 new hidden (1 hide what the engine refuses)');
    expect(line.className).toBe('cm-hidden-count');
  });

  it('the reason is the one-click un-hide: it unticks the box and the row returns', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    const box = screen.getByRole('checkbox', { name: /hide what the engine refuses/ }) as HTMLInputElement;
    fireEvent.click(box);
    await waitFor(() => expect(tickers()).not.toContain('MGNX'));
    const btn = screen.getByTestId('growth-new-hidden').querySelector('button[data-reason="refused"]')!;
    expect(btn.className).toBe('cm-hidden-reason');
    fireEvent.click(btn);
    expect(box.checked).toBe(false);
    await waitFor(() => expect(tickers()).toContain('MGNX'));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });

  it('?focus= on the hidden row → the line says the focused name is one of them', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount('/chart-maps?tab=growth&focus=MGNX');
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    expect((await screen.findByTestId('growth-new-hidden')).textContent)
      .toBe('✨ 1 new hidden (1 hide what the engine refuses) · MGNX is one of them');
    expect(screen.queryByTestId('growth-focus-miss')).toBeNull();   // it IS on the board
  });

  it('NEGATIVE: focus on a DRAWN name never claims it is hidden', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount('/chart-maps?tab=growth&focus=PGEN');
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    expect((await screen.findByTestId('growth-new-hidden')).textContent).not.toContain('one of them');
  });

  it('dropped by BOTH ⛔ and sector → blamed on the FIRST stage (refused) only', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Technology' }));
    const line = await screen.findByTestId('growth-new-hidden');
    expect(line.textContent).toBe('✨ 1 new hidden (1 hide what the engine refuses)');
    expect(line.querySelector('button[data-reason="sector"]')).toBeNull();
  });

  it('NEGATIVE: buyable OFF + sector ON → blamed on the sector filter, never `refused`', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('button', { name: 'Technology' }));
    const line = await screen.findByTestId('growth-new-hidden');
    expect(line.textContent).toBe('✨ 1 new hidden (1 sector filter)');
    expect(line.querySelector('button[data-reason="refused"]')).toBeNull();
    fireEvent.click(line.querySelector('button[data-reason="sector"]')!);
    await waitFor(() => expect(tickers()).toContain('MGNX'));
  });

  it('two stages blamed → one button each, joined by " · "', async () => {
    const BDEM = row({ symbol: 'BDEM', is_new: true, first_seen: STAMP,
                       zone: { missing: false, in_band: false, intact: null } });
    stub([MGNX, PGEN, AXTI, BDEM]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: /at demand, floor intact/ }));
    expect((await screen.findByTestId('growth-new-hidden')).textContent)
      .toBe('✨ 2 new hidden (1 hide what the engine refuses · 1 at demand, floor intact)');
  });

  it('debt stage: the reason resets the Debt picker to show everything', async () => {
    const LEV = row({ symbol: 'LEV', is_new: true, first_seen: STAMP, cash: 10e6, debt: 1e9 });
    stub([LEV, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(2));
    fireEvent.change(debtSelect(), { target: { value: 'net cash' } });
    const line = await screen.findByTestId('growth-new-hidden');
    expect(line.textContent).toBe('✨ 1 new hidden (1 debt filter)');
    fireEvent.click(line.querySelector('button[data-reason="debt"]')!);
    expect(debtSelect().value).toBe('all');
    await waitFor(() => expect(tickers()).toContain('LEV'));
  });

  it('enterable stage: a BLOCKED read on a new row → "enterable only", and the button turns the cut off', async () => {
    const room = {
      as_of: '2026-10-12T11:00:00-04:00', pending: 0,
      rows: {
        PGEN: { symbol: 'PGEN', coverage: 'store', print: 10, fresh: true, room: { state: 'CLEAR' },
                enterable: { kind: 'demand', verdict: 'BLOCKED', reasons: ['proximity'],
                             reason_short: ['not at band'], reason_text: ['far above the band'],
                             measured: { status: 'pending' } } },
        AXTI: { symbol: 'AXTI', coverage: 'store', print: 61, fresh: true, room: { state: 'CLEAR' },
                enterable: { kind: 'demand', verdict: 'READY', reasons: [], reason_short: [],
                             reason_text: [], measured: { status: 'pending' } } },
      },
    };
    stub([PGEN, AXTI], {}, room);
    const set = vi.fn();
    render(
      <MemoryRouter initialEntries={['/chart-maps?tab=growth']}>
        <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={set}>
          <ExplosiveGrowth />
        </EnterableFilterProvider>
      </MemoryRouter>);
    const line = await screen.findByTestId('growth-new-hidden');
    expect(line.textContent).toBe('✨ 1 new hidden (1 enterable only)');
    expect(tickers()).toEqual(['AXTI']);
    fireEvent.click(line.querySelector('button[data-reason="enterable"]')!);
    expect(set).toHaveBeenCalledWith(false);
  });

  it('NEGATIVE: enterable ON but the tab kind is n/a → the stage is inert and never blamed', async () => {
    const room = { pending: 0, rows: {
      PGEN: { symbol: 'PGEN', coverage: 'store', enterable: { kind: 'demand', verdict: 'BLOCKED',
              reasons: ['proximity'], reason_short: ['not at band'], reason_text: ['x'] } } } };
    stub([PGEN, AXTI], {}, room);
    render(
      <MemoryRouter initialEntries={['/chart-maps?tab=growth']}>
        <EnterableFilterProvider enterableOnly kind="n/a" setEnterableOnly={() => {}}>
          <ExplosiveGrowth />
        </EnterableFilterProvider>
      </MemoryRouter>);
    await waitFor(() => expect(tickers()).toHaveLength(2));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });

  it('NEGATIVE: nothing hidden → no line', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /at demand, floor intact/ }));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });

  it('NEGATIVE: an OLD hidden row (is_new false) is never counted', async () => {
    const OLD = row({ symbol: 'OLDX', warnings: [REFUSE], is_new: false, first_seen: TRACKING_SINCE });
    stub([OLD, PGEN, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    await waitFor(() => expect(tickers()).not.toContain('OLDX'));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });

  it('NEGATIVE: is_new true without a first_seen is not counted as a hidden arrival', async () => {
    const NODATE = row({ symbol: 'NODT', warnings: [REFUSE], is_new: true, first_seen: null });
    stub([NODATE, AXTI]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(2));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    await waitFor(() => expect(tickers()).not.toContain('NODT'));
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });
});

/* ── the folded arrivals line ───────────────────────────────────────────── */

describe('✨ arrivals line (folded, served note verbatim — C8)', () => {
  const ROWS = [row({ symbol: 'PGEN', is_new: true, first_seen: STAMP })];

  it('a <details> whose summary carries the served count + window, FOLDED on first paint', async () => {
    stub(ROWS, { arrivals_n: 11, new_days: 30, arrivals_note: 'SERVED NOTE' });
    mount();
    const el = await screen.findByTestId('growth-arrivals-line');
    expect(el.tagName).toBe('DETAILS');
    expect((el as HTMLDetailsElement).open).toBe(false);
    expect(el.querySelector('summary')!.textContent).toContain('✨ 11 arrived in the last 30 days');
    const p = Array.from(el.querySelectorAll('p')).find((x) => x.textContent === 'SERVED NOTE');
    expect(p).toBeTruthy();
  });

  it('arrivals_note null → a plain one-line note with the headline, no <details>', async () => {
    stub(ROWS, { arrivals_n: 11, new_days: 30, arrivals_note: null });
    mount();
    const el = await screen.findByTestId('growth-arrivals-line');
    expect(el.tagName).toBe('DIV');
    expect(el.textContent).toBe('✨ 11 arrived in the last 30 days');
    expect(el.querySelector('details')).toBeNull();
  });

  it('NEGATIVE: arrivals_n 0 → no line', async () => {
    stub(ROWS, { arrivals_n: 0, new_days: 30, arrivals_note: 'SERVED NOTE' });
    mount();
    await screen.findByText('PGEN');
    expect(screen.queryByTestId('growth-arrivals-line')).toBeNull();
    expect(screen.queryByText(/arrived in the last/)).toBeNull();
  });

  it('NEGATIVE: arrivals_n absent → no line', async () => {
    stub(ROWS, { new_days: 30, arrivals_note: 'SERVED NOTE' });
    mount();
    await screen.findByText('PGEN');
    expect(screen.queryByTestId('growth-arrivals-line')).toBeNull();
  });

  it('NEGATIVE: the count is the SERVED arrivals_n, never the rows counted here', async () => {
    stub(ROWS, { arrivals_n: 4, new_days: 30, arrivals_note: null });
    mount();
    expect((await screen.findByTestId('growth-arrivals-line')).textContent)
      .toBe('✨ 4 arrived in the last 30 days');
  });
});

/* ── wording + source pins ──────────────────────────────────────────────── */

describe('wording and source pins', () => {
  it('NEGATIVE: the rendered board (with arrivals) never says "bounce"', async () => {
    stub([row({ symbol: 'PGEN', is_new: true, first_seen: STAMP }),
          row({ symbol: 'MGNX', warnings: [REFUSE], is_new: true, first_seen: STAMP })],
         { arrivals_n: 2, new_days: 30, arrivals_note: 'SERVED NOTE' });
    mount('/chart-maps?tab=growth&focus=NOPE');
    await screen.findByTestId('growth-arrivals-line');
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    await screen.findByTestId('growth-new-hidden');
    expect((document.body.textContent ?? '').toLowerCase()).not.toContain('bounce');
  });

  it('NEGATIVE: no arrivals research number, pp or CI literal is typed into the component', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    // the only pp literal in the file is the pre-existing intact-floor title (+8.6pp, twice)
    expect(src.match(/[+−-]?\d+(?:\.\d+)?pp/g)).toEqual(['+8.6pp', '+8.6pp']);
    expect(src).not.toMatch(/\bCI\b/);
    for (const n of ['3.69', '5.58', '8.93', '1.37', '1.10', '6.38', '10.13', '11.77',
                     'G100_ARRIVE', 'board_growth_measured']) {
      expect(src).not.toContain(n);
    }
  });

  it('NEGATIVE: the arrivals line is not opened by default and no eg-* token was added for it', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    expect(src).not.toContain('defaultOpen');
    for (const t of ['eg-new', 'eg-arriv', 'eg-focus', 'eg-row-focus']) expect(src).not.toContain(t);
  });

  it('NEGATIVE: no admin email in the component source', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    expect(src).not.toContain('@gmail');
    expect(src).not.toContain('ajaykandakatla');
  });
});
