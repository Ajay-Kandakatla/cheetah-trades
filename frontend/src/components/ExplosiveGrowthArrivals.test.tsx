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
    /* The only ✨ left is the always-drawn "✨ new only (0)" control (refix
     * 2026-10-13, spec §0 #2) — no tag, no line. */
    expect(screen.queryByText(/✨ NEW/)).toBeNull();
    expect(screen.getAllByText(/✨/).map((el) => el.textContent)).toEqual(['✨ new only (0)']);
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
    // a filter that would REMOVE the focused row: since #6 (2026-10-12) the
    // focused row stays DRAWN, exempt and marked; it never scrolls again
    fireEvent.click(screen.getByRole('button', { name: 'Healthcare' }));
    await waitFor(() => expect(screen.getByTestId('growth-row-AXTI').className)
      .toBe('cm-row-focus cm-row-exempt'));
    expect(screen.getByTestId('growth-focus-exempt')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Healthcare' }));
    await waitFor(() => expect(screen.getByTestId('growth-row-AXTI').className).toBe('cm-row-focus'));
    expect(screen.queryByTestId('growth-focus-exempt')).toBeNull();
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

  it('?focus= on the hidden row → it is DRAWN (exempt, #6), so the ✨ line no longer counts it', async () => {
    stub([MGNX, PGEN, AXTI]);
    mount('/chart-maps?tab=growth&focus=MGNX');
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    expect((await screen.findByTestId('growth-focus-exempt')).textContent)
      .toBe('✨ MGNX shown because you opened it from ✨ — hidden by hide what the engine refuses');
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();     // MGNX was the only hidden arrival
    expect(screen.queryByTestId('growth-focus-miss')).toBeNull();     // it IS on the board
    expect(document.body.textContent).not.toContain('one of them');
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

/* ══ 2026-10-12 his-call package P2 (board-fe): #2 ✨ new only, #6 the focus
 * exemption, #7 the board line's open rule, #1 the MEASURED wording. ═══════ */

const PREV_PP_LITERALS = ['+8.6pp', '+8.6pp'];

/** The committed component's pp-literal count, read from `git show HEAD:` —
 *  so the guard is "does not grow" against what is actually on the branch.
 *  Falls back to the pin above when git is not reachable (a tarball CI). */
async function headPpCount(): Promise<number> {
  try {
    const cp: any = await import(/* @vite-ignore */ ('node:' + 'child_process'));
    const out: string = (cp.default || cp).execSync(
      'git show HEAD:frontend/src/components/ExplosiveGrowth.tsx',
      { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] });
    return (out.match(/[+−-]?\d+(?:\.\d+)?\s*pp\b/g) ?? []).length;
  } catch {
    return PREV_PP_LITERALS.length;
  }
}

const NEW_ON: StagedFilterOpts = { ...ALL_OFF, onlyNew: true };

/** An in-memory Storage (the StudyNote tests' shape): the runner's global
 *  `localStorage` is not a reliable jsdom store, so every test that reads or
 *  asserts on storage installs its own. */
function memStore(init: Record<string, string> = {}) {
  const m = new Map<string, string>(Object.entries(init));
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(),
    key: (i: number) => Array.from(m.keys())[i] ?? null,
    get length() { return m.size; },
    _m: m,
  };
}

describe('#2 stagedFilter — ✨ new only (pure)', () => {
  const MIX: GrowthRow[] = [
    row({ symbol: 'NEW1', is_new: true, first_seen: STAMP }),
    row({ symbol: 'OLD1', is_new: false, first_seen: TRACKING_SINCE }),
    row({ symbol: 'NOREAD' }),                                  // older payload: no is_new
    row({ symbol: 'NEW2', is_new: true, first_seen: STAMP }),
  ];

  it('ON keeps only is_new === true, in input order, and records a `new` kept + dropped entry', () => {
    const got = stagedFilter(MIX, NEW_ON);
    expect(syms(got.rows)).toEqual(['NEW1', 'NEW2']);
    expect([...got.kept.keys()]).toEqual(['new']);
    expect([...got.kept.get('new')!]).toEqual(['NEW1', 'NEW2']);
    expect(got.dropped.get('new')).toBe(2);
  });

  it('NEGATIVE: a row with is_new undefined (older payload) is dropped as NOT new', () => {
    expect(syms(stagedFilter(MIX, NEW_ON).rows)).not.toContain('NOREAD');
  });

  it('NEGATIVE: OFF (absent or false) → no `new` kept, no `new` dropped, rows untouched', () => {
    for (const o of [ALL_OFF, { ...ALL_OFF, onlyNew: false }]) {
      const got = stagedFilter(MIX, o);
      expect(got.rows).toEqual(MIX);
      expect(got.kept.has('new')).toBe(false);
      expect(got.dropped.has('new')).toBe(false);
      expect(got.dropped.size).toBe(0);
    }
  });

  it('NEGATIVE: the input array is never mutated', () => {
    const input = Object.freeze([...MIX]) as readonly GrowthRow[];
    stagedFilter(input, NEW_ON);
    expect(syms(input)).toEqual(['NEW1', 'OLD1', 'NOREAD', 'NEW2']);
  });

  it('runs AFTER debt: kept keys in board order with every stage ON', () => {
    const rows = SIX.map((r) => ({ ...r, is_new: r.symbol === 'ESUR' }));
    const got = stagedFilter(rows, { ...ALL_ON, onlyNew: true });
    expect([...got.kept.keys()]).toEqual(['refused', 'demand', 'sector', 'debt', 'new']);
    expect(syms(got.rows)).toEqual(['ESUR']);
  });

  it('[C10] dropped = before.length − after.length per ON stage, absent for OFF stages', () => {
    const rows = SIX.map((r) => ({ ...r, is_new: r.symbol === 'ESUR' }));
    const got = stagedFilter(rows, { ...ALL_ON, onlyNew: true });
    expect(Object.fromEntries(got.dropped)).toEqual(
      { refused: 1, demand: 1, sector: 1, debt: 1, new: 1 });
    const one = stagedFilter(rows, { ...ALL_OFF, sector: 'Technology' });
    expect([...one.dropped.keys()]).toEqual(['sector']);
    expect(one.dropped.get('sector')).toBe(1);
  });

  it('[C10] NEGATIVE: a DUPLICATED symbol is counted twice by dropped, where kept set sizes would say once', () => {
    const dup: GrowthRow[] = [
      row({ symbol: 'DUPX', is_new: false }), row({ symbol: 'DUPX', is_new: false }),
      row({ symbol: 'NEWY', is_new: true, first_seen: STAMP }),
    ];
    const got = stagedFilter(dup, { ...ALL_OFF, onlyBuyable: true, onlyNew: true });
    const setDiff = got.kept.get('refused')!.size - got.kept.get('new')!.size;
    expect(setDiff).toBe(1);                       // the undercount C10 names
    expect(got.dropped.get('new')).toBe(2);        // the array truth
    expect(got.dropped.get('refused')).toBe(0);
  });
});

/* ── #2 rendered ─────────────────────────────────────────────────────────── */

describe('#2 ✨ new only checkbox on the board', () => {
  const N1 = row({ symbol: 'NWA', is_new: true, first_seen: STAMP, sales_growth_pct: 150 });
  const N2 = row({ symbol: 'NWB', is_new: true, first_seen: STAMP, sales_growth_pct: 350 });
  const O1 = row({ symbol: 'OLA', is_new: false, first_seen: TRACKING_SINCE, sales_growth_pct: 250 });
  const O2 = row({ symbol: 'OLB', is_new: false, first_seen: TRACKING_SINCE, sales_growth_pct: 450 });
  const U1 = row({ symbol: 'UNR', sales_growth_pct: 120 });       // no arrival read
  const box = () => screen.getByTestId('growth-new-only') as HTMLInputElement;

  it('OFF on first paint, label carries the served new count, every row drawn', async () => {
    stub([N1, N2, O1, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    expect(box().checked).toBe(false);
    expect(box().closest('label')!.textContent).toBe('✨ new only (2)');
    expect(screen.queryByTestId('growth-new-only-hidden')).toBeNull();
  });

  it('ON → only is_new === true rows; the line says how many it hid and over which window', async () => {
    stub([N1, N2, O1, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    fireEvent.click(box());
    await waitFor(() => expect(tickers().sort()).toEqual(['NWA', 'NWB']));
    const line = screen.getByTestId('growth-new-only-hidden');
    expect(line.className).toBe('cm-hidden-count');
    expect(line.textContent).toBe('✨ new only: 2 hidden (not new in the last 30 days) · show all');
  });

  it('a row with no arrival read is hidden as NOT new, and the line says so', async () => {
    stub([N1, O1, U1], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(box());
    await waitFor(() => expect(tickers()).toEqual(['NWA']));
    expect(screen.getByTestId('growth-new-only-hidden').textContent).toBe(
      '✨ new only: 2 hidden (not new in the last 30 days) · 1 row carries no arrival read and counts as not new · show all');
  });

  it('`show all` unticks the box and every row returns', async () => {
    stub([N1, N2, O1, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    fireEvent.click(box());
    await waitFor(() => expect(tickers()).toHaveLength(2));
    fireEvent.click(screen.getByTestId('growth-new-only-hidden').querySelector('button')!);
    expect(box().checked).toBe(false);
    await waitFor(() => expect(tickers()).toHaveLength(4));
    expect(screen.queryByTestId('growth-new-only-hidden')).toBeNull();
  });

  it('NEGATIVE: ON never produces the "N new hidden" line (it never drops a new name)', async () => {
    stub([N1, N2, O1, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    fireEvent.click(box());
    await screen.findByTestId('growth-new-only-hidden');
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
    expect(document.querySelector('button[data-reason="new"]')).toBeNull();
  });

  it('NEGATIVE: it sorts nothing — the drawn order equals the unfiltered order with the old rows removed', async () => {
    stub([N1, O1, N2, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    const without = tickers().filter((t) => t === 'NWA' || t === 'NWB');
    fireEvent.click(box());
    await waitFor(() => expect(tickers()).toHaveLength(2));
    expect(tickers()).toEqual(without);
  });

  it('NEGATIVE: ticking it changes no other checkbox and no select', async () => {
    stub([N1, N2, O1, O2], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(4));
    const others = () => Array.from(document.querySelectorAll('input[type="checkbox"]'))
      .filter((el) => el !== box()).map((el) => (el as HTMLInputElement).checked);
    const selects = () => Array.from(document.querySelectorAll('select')).map((el) => el.value);
    const before = [others(), selects()];
    fireEvent.click(box());
    await screen.findByTestId('growth-new-only-hidden');
    expect([others(), selects()]).toEqual(before);
  });

  it('NEGATIVE: new_days missing → the window clause is omitted, never "undefined"', async () => {
    stub([N1, O1]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(2));
    fireEvent.click(box());
    const t = (await screen.findByTestId('growth-new-only-hidden')).textContent!;
    expect(t).toBe('✨ new only: 1 hidden (not new) · show all');
    expect(t).not.toContain('undefined');
    expect(t).not.toContain('null');
  });

  it('NEGATIVE: an older payload with no arrival read on any row → the control is STILL drawn, OFF, reading (0)', async () => {
    stub([row({ symbol: 'AXTI' }), row({ symbol: 'BBBB' })], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(2));
    expect(box().checked).toBe(false);
    expect(box().closest('label')!.textContent).toBe('✨ new only (0)');
    expect(screen.queryByTestId('growth-new-only-hidden')).toBeNull();
  });

  it('NEGATIVE: all-old payload, ON → every row hidden and the line says ALL of them carry no arrival read', async () => {
    stub([row({ symbol: 'AXTI' }), row({ symbol: 'BBBB' }), row({ symbol: 'CCCC' })], { new_days: 30 });
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(3));
    fireEvent.click(box());
    await waitFor(() => expect(tickers()).toHaveLength(0));
    expect(screen.getByTestId('growth-new-only-hidden').textContent).toBe(
      '✨ new only: 3 hidden (not new in the last 30 days) · 3 rows carry no arrival read and count as not new · show all');
    expect(screen.queryByTestId('growth-new-hidden')).toBeNull();
  });

  it('NEGATIVE: all-old payload, ON then `show all` → every row returns and the line goes', async () => {
    stub([row({ symbol: 'AXTI' }), row({ symbol: 'BBBB' })]);
    mount();
    await waitFor(() => expect(tickers()).toHaveLength(2));
    fireEvent.click(box());
    await waitFor(() => expect(tickers()).toHaveLength(0));
    fireEvent.click(screen.getByTestId('growth-new-only-hidden').querySelector('button')!);
    expect(box().checked).toBe(false);
    await waitFor(() => expect(tickers()).toHaveLength(2));
    expect(screen.queryByTestId('growth-new-only-hidden')).toBeNull();
  });
});

/* ── #6 the focus exemption ─────────────────────────────────────────────── */

/** The enterable HiddenCount line (the only `N hidden` line that is not ✨/💎). */
const enterLine = () => Array.from(document.querySelectorAll('div.cm-hidden-count'))
  .find((el) => /^\d+ hidden/.test(el.textContent ?? '')) as HTMLElement | undefined;
const enterHidden = () => Number((enterLine()?.textContent ?? '').match(/^(\d+) hidden/)![1]);
const chipN = (code: string) => {
  const b = enterLine()?.querySelector(`button[data-reason="${code}"]`);
  return b ? Number((b.textContent ?? '').match(/^(\d+)/)![1]) : 0;
};
const allChipN = () => Array.from(enterLine()?.querySelectorAll('button[data-reason]') ?? [])
  .reduce((s, b) => s + Number((b.textContent ?? '0').match(/^(\d+)/)?.[1] ?? 0), 0);

describe('#6 ?focus= draws a row his filters hide — ONE row, marked, no filter written', () => {
  const MGNX = row({ symbol: 'MGNX', sector: 'Healthcare', warnings: [REFUSE],
                     is_new: true, first_seen: STAMP, sales_growth_pct: 90 });
  const RFX2 = row({ symbol: 'RFXB', warnings: [REFUSE], is_new: true, first_seen: STAMP, sales_growth_pct: 80 });
  const OLDR = row({ symbol: 'OLDR', warnings: [REFUSE], is_new: false, first_seen: TRACKING_SINCE, sales_growth_pct: 70 });
  const PGEN = row({ symbol: 'PGEN', is_new: true, first_seen: STAMP, sales_growth_pct: 300 });
  const AXTI = row({ symbol: 'AXTI', is_new: false, first_seen: TRACKING_SINCE, sales_growth_pct: 200 });
  const ROWS = [MGNX, RFX2, OLDR, PGEN, AXTI];
  const refuses = () => screen.getByRole('checkbox', { name: /hide what the engine refuses/ }) as HTMLInputElement;

  it('"hide what the engine refuses" ON → MGNX drawn FIRST, exempt, marked; the other refused rows stay hidden', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=MGNX');
    await waitFor(() => expect(tickers()).toHaveLength(5));
    fireEvent.click(refuses());
    await waitFor(() => expect(tickers()).toEqual(['MGNX', 'PGEN', 'AXTI']));
    const tr = screen.getByTestId('growth-row-MGNX');
    expect(tr.className).toBe('cm-row-focus cm-row-exempt');
    expect(tr.getAttribute('data-exempt')).toBe('true');
    expect(screen.getByTestId('growth-focus-exempt').textContent)
      .toBe('✨ MGNX shown because you opened it from ✨ — hidden by hide what the engine refuses');
    expect(screen.getByTestId('growth-focus-exempt').className).toBe('cm-hidden-count');
    expect(refuses().checked).toBe(true);                              // the box is NOT flipped
    // the ✨ line counts the OTHER hidden arrival only — MGNX is drawn
    expect(screen.getByTestId('growth-new-hidden').textContent)
      .toBe('✨ 1 new hidden (1 hide what the engine refuses)');
    expect(document.querySelectorAll('[data-exempt="true"]')).toHaveLength(1);
  });

  it('sector filter → the marker names the sector filter', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=MGNX');
    await waitFor(() => expect(tickers()).toHaveLength(5));
    fireEvent.click(screen.getByRole('button', { name: 'Technology' }));
    await waitFor(() => expect(tickers()[0]).toBe('MGNX'));
    expect(screen.getByTestId('growth-focus-exempt').textContent)
      .toBe('✨ MGNX shown because you opened it from ✨ — hidden by sector filter');
    expect(tickers()).toHaveLength(5);                                 // every other row is Technology
    expect(tickers().filter((t) => t === 'MGNX')).toHaveLength(1);     // drawn once, never duplicated
    expect(screen.getByRole('button', { name: /clear filter \(Technology\)/ })).toBeTruthy();  // filter still ON
  });

  it('✨ new only ON + a focus on an INCUMBENT (?symbol= from an old push) → drawn, "hidden by ✨ new only"', async () => {
    stub(ROWS, { new_days: 30 });
    mount('/chart-maps?tab=growth&symbol=AXTI');
    await waitFor(() => expect(tickers()).toHaveLength(5));
    fireEvent.click(screen.getByTestId('growth-new-only'));
    await waitFor(() => expect(tickers()[0]).toBe('AXTI'));
    expect(screen.getByTestId('growth-focus-exempt').textContent)
      .toBe('✨ AXTI shown because you opened it from ✨ — hidden by ✨ new only');
    expect(tickers().sort()).toEqual(['AXTI', 'MGNX', 'PGEN', 'RFXB']);
    // the new-only count line is the stage's own drop count — AXTI included (it WAS dropped)
    expect(screen.getByTestId('growth-new-only-hidden').textContent)
      .toContain('2 hidden');
  });

  /* The enterable stage: three BLOCKED rows, two under one reason. */
  const ROOM = {
    as_of: '2026-10-12T11:00:00-04:00', pending: 0,
    rows: Object.fromEntries([
      ['MGNX', 'proximity', 'not at band'], ['PGEN', 'proximity', 'not at band'],
      ['RFXB', 'room', 'no room'],
    ].map(([s, code, short]) => [s, {
      symbol: s, coverage: 'store', print: 10, fresh: true, room: { state: 'CLEAR' },
      enterable: { kind: 'demand', verdict: 'BLOCKED', reasons: [code], reason_short: [short],
                   reason_text: ['x'], measured: { status: 'pending' } } }]).concat([
      ['AXTI', { symbol: 'AXTI', coverage: 'store', print: 61, fresh: true, room: { state: 'CLEAR' },
                 enterable: { kind: 'demand', verdict: 'READY', reasons: [], reason_short: [],
                              reason_text: [], measured: { status: 'pending' } } }],
      ['OLDR', { symbol: 'OLDR', coverage: 'store', print: 61, fresh: true, room: { state: 'CLEAR' },
                 enterable: { kind: 'demand', verdict: 'READY', reasons: [], reason_short: [],
                              reason_text: [], measured: { status: 'pending' } } }],
    ])),
  };
  const mountEnter = (path: string, set = vi.fn()) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <EnterableFilterProvider enterableOnly kind="demand" setEnterableOnly={set}>
          <ExplosiveGrowth />
        </EnterableFilterProvider>
      </MemoryRouter>);
    return set;
  };

  it('[C3] enterable stage: marker names "enterable only"; HiddenCount is exactly ONE lower; chips stay the engine\'s own', async () => {
    stub(ROWS, {}, ROOM);
    mountEnter('/chart-maps?tab=growth');
    await waitFor(() => expect(enterLine()).toBeTruthy());
    await waitFor(() => expect(enterHidden()).toBe(3));
    const base = { hidden: enterHidden(), prox: chipN('proximity'), room: chipN('room') };
    expect(base).toEqual({ hidden: 3, prox: 2, room: 1 });
    expect(allChipN()).toBe(base.hidden);                       // the invariant, no focus
    cleanup(); _resetBounceRoomCache();

    stub(ROWS, {}, ROOM);
    const set = mountEnter('/chart-maps?tab=growth&focus=MGNX');
    await screen.findByTestId('growth-focus-exempt');
    await waitFor(() => expect(enterHidden()).toBe(2));
    expect(screen.getByTestId('growth-focus-exempt').textContent)
      .toBe('✨ MGNX shown because you opened it from ✨ — hidden by enterable only');
    expect(tickers()[0]).toBe('MGNX');
    expect(chipN('proximity')).toBe(base.prox - 1);             // MGNX's reason, one lower
    expect(chipN('room')).toBe(base.room);                      // the other reason untouched
    expect(allChipN()).toBe(enterHidden());                     // sum(reasons[].hidden) === hidden
    expect(tickers()).not.toContain('PGEN');                    // every other blocked row stays hidden
    expect(tickers()).not.toContain('RFXB');
    expect(set).not.toHaveBeenCalled();                         // no filter setter fired
  });

  it('[C3] quality stage: the 💎 hidden line and its per-key count are exactly ONE lower', async () => {
    const fail = { grade: 'none', passed: 0, failed: 1, unknown: 0, answered: 1, rank_key: 0,
                   components: { net_cash: { verdict: 'fail', why: 'cash <= debt' } } };
    const pass = { grade: 'all', passed: 1, failed: 0, unknown: 0, answered: 1, rank_key: 1,
                   components: { net_cash: { verdict: 'pass', why: 'cash > debt' } } };
    const q = (r: GrowthRow, read: unknown) => ({ ...r, warnings: [], capital_quality: read as GrowthRow['capital_quality'] });
    const QROWS = [q(MGNX, fail), q(RFX2, fail), q(PGEN, pass), q(AXTI, pass)];
    const summary = {
      n: 4, grades: { all: 2, none: 2 }, measured: false, measured_note: 'NOT MEASURED',
      components: [{ key: 'net_cash', kind: 'definitional', label: 'net cash',
                     pass_n: 2, fail_n: 2, unknown_n: 0, hides_n: 2 }],
    };
    stub(QROWS, { capital_quality_summary: summary });
    mount('/chart-maps?tab=growth');
    fireEvent.click(await screen.findByTestId('eg-qchip-net_cash'));
    await waitFor(() => expect(tickers()).toEqual(['PGEN', 'AXTI']));
    const baseKey = screen.getByTestId('eg-qhidden-net_cash').textContent;
    expect(baseKey).toMatch(/^2 /);
    expect(screen.getByTestId('eg-qhidden').textContent).toContain('2 showing');
    cleanup();

    stub(QROWS, { capital_quality_summary: summary });
    mount('/chart-maps?tab=growth&focus=MGNX');
    fireEvent.click(await screen.findByTestId('eg-qchip-net_cash'));
    await waitFor(() => expect(tickers()).toEqual(['MGNX', 'PGEN', 'AXTI']));
    expect(screen.getByTestId('growth-focus-exempt').textContent)
      .toBe('✨ MGNX shown because you opened it from ✨ — hidden by quality chips');
    expect(screen.getByTestId('eg-qhidden-net_cash').textContent).toMatch(/^1 /);
    expect(screen.getByTestId('eg-qhidden').textContent).toContain('2 showing');
    expect(tickers()).not.toContain('RFXB');
  });

  it('NEGATIVE: focus on a DRAWN row → no marker, no duplicate, counts identical to no focus', async () => {
    stub(ROWS, {}, ROOM);
    mountEnter('/chart-maps?tab=growth');
    await waitFor(() => expect(enterHidden()).toBe(3));
    const noFocus = { line: enterLine()!.textContent, rows: tickers() };
    cleanup(); _resetBounceRoomCache();

    stub(ROWS, {}, ROOM);
    mountEnter('/chart-maps?tab=growth&focus=AXTI');
    await waitFor(() => expect(enterHidden()).toBe(3));
    expect(screen.queryByTestId('growth-focus-exempt')).toBeNull();
    expect(document.querySelector('[data-exempt]')).toBeNull();
    expect(screen.getByTestId('growth-row-AXTI').className).toBe('cm-row-focus');
    expect(enterLine()!.textContent).toBe(noFocus.line);
    expect(tickers()).toEqual(noFocus.rows);
  });

  it('NEGATIVE: ?focus=NOPE with a filter ON → the miss line only, nothing exempt', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth&focus=NOPE');
    await waitFor(() => expect(tickers()).toHaveLength(5));
    fireEvent.click(refuses());
    await waitFor(() => expect(tickers()).toEqual(['PGEN', 'AXTI']));
    expect(screen.getByTestId('growth-focus-miss').textContent).toBe('✨ NOPE is not on this board today.');
    expect(screen.queryByTestId('growth-focus-exempt')).toBeNull();
    expect(screen.getByTestId('growth-new-hidden').textContent)
      .toBe('✨ 2 new hidden (2 hide what the engine refuses)');
  });

  it('NEGATIVE: landing on an exempt focus writes no localStorage key and fires no filter setter', async () => {
    const store = memStore();
    vi.stubGlobal('localStorage', store);
    stub(ROWS, {}, ROOM);
    const set = mountEnter('/chart-maps?tab=growth&focus=MGNX');
    await screen.findByTestId('growth-focus-exempt');
    expect(set).not.toHaveBeenCalled();
    expect([...store._m.keys()]).toEqual([]);
    for (const el of Array.from(document.querySelectorAll('input[type="checkbox"]'))) {
      expect((el as HTMLInputElement).checked).toBe(false);       // every local box still at its default
    }
    expect(Array.from(document.querySelectorAll('select')).map((el) => el.value)).toEqual(['all']);
  });

  it('NEGATIVE: unfocus (no param) with the filter ON → the refused rows simply stay hidden', async () => {
    stub(ROWS);
    mount('/chart-maps?tab=growth');
    await waitFor(() => expect(tickers()).toHaveLength(5));
    fireEvent.click(refuses());
    await waitFor(() => expect(tickers()).toEqual(['PGEN', 'AXTI']));
    expect(screen.queryByTestId('growth-focus-exempt')).toBeNull();
  });
});

/* ── #7 the board's arrivals line opens on a fresh batch ─────────────────── */

describe('#7 the board arrivals line follows the strip\'s open rule (freshKey)', () => {
  const ROWS = [row({ symbol: 'PGEN', is_new: true, first_seen: STAMP })];
  const NEWER = '2026-10-19T02:29:05+00:00';
  const extra = (stamp: string) => ({
    arrivals_n: 1, new_days: 30, arrivals_note: 'SERVED NOTE',
    arrivals: [{ symbol: 'PGEN', first_seen: stamp }, { symbol: 'OLDX', first_seen: '2026-10-01T00:00:00+00:00' }],
  });
  const det = () => screen.getByTestId('growth-arrivals-line') as HTMLDetailsElement;
  const fold = () => { const el = det(); el.open = false; fireEvent(el, new Event('toggle')); };
  beforeEach(() => { vi.stubGlobal('localStorage', memStore()); });

  it('opens on first paint for a viewer who never folded it', async () => {
    stub(ROWS, extra(STAMP));
    mount();
    await screen.findByTestId('growth-arrivals-line');
    await waitFor(() => expect(det().open).toBe(true));
  });

  it('NEGATIVE: same batch after his fold → stays folded on the next visit', async () => {
    stub(ROWS, extra(STAMP));
    mount();
    await waitFor(() => expect(det().open).toBe(true));
    fold();
    cleanup();
    stub(ROWS, extra(STAMP));
    mount();
    await screen.findByTestId('growth-arrivals-line');
    await new Promise((r) => setTimeout(r, 20));
    expect(det().open).toBe(false);
  });

  it('a NEWER batch (newest served first_seen later than at his fold) re-opens it', async () => {
    stub(ROWS, extra(STAMP));
    mount();
    await waitFor(() => expect(det().open).toBe(true));
    fold();
    cleanup();
    stub(ROWS, extra(NEWER));
    mount();
    await screen.findByTestId('growth-arrivals-line');
    await waitFor(() => expect(det().open).toBe(true));
  });

  it('NEGATIVE: no served arrivals list (older payload) → today\'s folded first paint', async () => {
    stub(ROWS, { arrivals_n: 1, new_days: 30, arrivals_note: 'SERVED NOTE' });
    mount();
    await screen.findByTestId('growth-arrivals-line');
    await new Promise((r) => setTimeout(r, 20));
    expect(det().open).toBe(false);
  });

  it('NEGATIVE: a throwing localStorage with a served batch → opens and the board renders', async () => {
    const boom = () => { throw new Error('blocked'); };
    vi.stubGlobal('localStorage', { getItem: boom, setItem: boom, removeItem: boom,
                                    clear: () => {}, key: () => null, length: 0 });
    stub(ROWS, extra(STAMP));
    mount();
    await screen.findByTestId('growth-arrivals-line');
    await waitFor(() => expect(det().open).toBe(true));
    expect(tickers()).toEqual(['PGEN']);
    expect(() => fold()).not.toThrow();
  });

  it('source: the board line passes freshKey = newestFirstSeen(served arrivals) — never a typed stamp', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    expect(src).toMatch(/freshKey=\{newestFirstSeen\(data\?\.arrivals \?\? \[\]\)\}/);
    expect(src).toMatch(/from '\.\.\/lib\/growthArrivalsFresh'/);
  });
});

/* ── #1 the MEASURED wording on the board ───────────────────────────────── */

describe('#1 MEASURED 2026-09-21 — served fold + reworded 📣 note', () => {
  const ROWS = [row({ symbol: 'PGEN' })];
  const SM = { headline: 'SERVED HEADLINE 2026-09-21', body: 'SERVED BODY with +9.99pp that the FE never types' };
  const ER = { earnings_fresh_summary: { window_days: 7, n: 1, n_fresh: 1, n_known: 1, n_unknown: 0,
                                         as_of: '2026-10-12', most_recent: null } };

  it('growth-screen-measured renders the SERVED headline and body verbatim, folded', async () => {
    stub(ROWS, { screen_measured: SM });
    mount();
    const el = await screen.findByTestId('growth-screen-measured');
    expect(el.tagName).toBe('DETAILS');
    expect(el.querySelector('summary')!.textContent).toContain(SM.headline);
    expect(Array.from(el.querySelectorAll('p')).some((p) => p.textContent === SM.body)).toBe(true);
    expect((el as HTMLDetailsElement).open).toBe(false);
  });

  it('NEGATIVE: payload without screen_measured → no fold, the board still renders', async () => {
    stub(ROWS);
    mount();
    await screen.findByText('PGEN');
    expect(screen.queryByTestId('growth-screen-measured')).toBeNull();
  });

  it('NEGATIVE: screen_measured with an empty body (or null) → no fold', async () => {
    for (const sm of [{ headline: 'H', body: '' }, null]) {
      stub(ROWS, { screen_measured: sm });
      mount();
      await screen.findByText('PGEN');
      expect(screen.queryByTestId('growth-screen-measured')).toBeNull();
      cleanup();
    }
  });

  it('the 📣 note says "measured 2026-09-21" and NEVER "never been measured"', async () => {
    stub(ROWS, ER);
    mount();
    await screen.findByText('PGEN');
    const note = document.querySelector('.eg-ernote')!;
    expect(note.textContent).toContain('measured 2026-09-21');
    expect(note.textContent).not.toMatch(/never been measured/i);
    expect(note.textContent).not.toMatch(/BACKTESTED/);
  });

  it('NEGATIVE: the component source never says the screen is unmeasured', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    expect(src).not.toMatch(/never been measured/i);
    expect(src).not.toMatch(/NOTHING HERE IS BACKTESTED/);
  });

  it('NEGATIVE: the pp-literal count in the component does not grow (vs git HEAD)', async () => {
    const src = await readSource('src/components/ExplosiveGrowth.tsx');
    const now = (src.match(/[+−-]?\d+(?:\.\d+)?\s*pp\b/g) ?? []).length;
    expect(now).toBeLessThanOrEqual(await headPpCount());
    expect(now).toBeLessThanOrEqual(PREV_PP_LITERALS.length);
  });

  it('NEGATIVE: no "bounce" anywhere on the board with every new control on', async () => {
    stub([row({ symbol: 'PGEN', is_new: true, first_seen: STAMP }),
          row({ symbol: 'MGNX', warnings: [REFUSE], is_new: true, first_seen: STAMP })],
         { screen_measured: SM, new_days: 30, arrivals_n: 2, arrivals_note: 'N',
           arrivals: [{ symbol: 'PGEN', first_seen: STAMP }] });
    mount('/chart-maps?tab=growth&focus=MGNX');
    await screen.findByTestId('growth-screen-measured');
    fireEvent.click(screen.getByRole('checkbox', { name: /hide what the engine refuses/ }));
    fireEvent.click(screen.getByTestId('growth-new-only'));
    await screen.findByTestId('growth-focus-exempt');
    expect((document.body.textContent ?? '').toLowerCase()).not.toContain('bounce');
  });
});
