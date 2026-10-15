/* 🔥 Hottest — the six fundamentals cells, extracted (2026-10-14 b).
 *
 * Ajay 2026-10-14: "Can you add sort function on the headers and also 5 day
 * and 21 days columns to show how they were reacting in price like hot sectors
 * and also add sales tab make it like hot sector with some important metrics
 * like EPS, QUAlity and other colums that show the strength of the stock".
 *
 * The 🎢 High Beta Sales view prints the SAME six cells 🔥 Hottest prints
 * (Sales YoY, Sales trend, Q EPS, Margin, Quality, Next ER), so the cells moved
 * VERBATIM out of HottestSectors' NameRow into `HsFundCell` — one renderer,
 * never a second formula. This file pins that the move changed no byte:
 *
 *   1. GOLDEN — every name row's six fund `<td>`s' outerHTML equal a capture
 *      written by THIS test (HS_FUND_GOLDEN_WRITE=1) on the UNCHANGED
 *      HottestSectors.tsx, before the extraction. Two payloads: the real
 *      2026-09-28 read, and a clone of it with the edge cases the real read
 *      does not carry (pair checked-and-wrong, pair unchecked, every value
 *      missing, every flag on).
 *   2. `HsFundCell` per key on crafted rows, NEGATIVE cases included.
 *   3. `HS_FUND_KEYS` is HS_COLS minus the three legs, in order. */
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import REAL from './__fixtures__/hottest_real_2026_09_28.json';
import { HS_COLS, HS_FUND_KEYS, HsFundCell, HottestSectors, visibleCols } from './HottestSectors';
import type { HsFundKey, HsFundRow, HsName, HsPayload } from './HottestSectors';
import type { HsQualityInfo } from './HottestQualityInfo';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const GOLDEN_REL = 'src/components/__fixtures__/hottest_fund_cells_golden_2026_10_14.json';
const FUND_CELLS = 6;

type Golden = Record<string, { symbol: string; cells: string[] }[]>;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const env = (k: string): string | undefined =>
  (globalThis as { process?: { env?: Record<string, string | undefined> } }).process?.env?.[k];
async function fsMod(): Promise<any> {
  const mod: any = await import(/* @vite-ignore */ ('node:' + 'fs'));
  return mod?.default || mod;
}
const root = () => (globalThis as any).process?.cwd?.() || '.';

function memStorage(): Storage {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => (m.has(k) ? m.get(k)! : null),
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); }, clear: () => m.clear(),
    key: (i: number) => [...m.keys()][i] ?? null, get length() { return m.size; },
  } as Storage;
}

const allNames = (d: HsPayload): HsName[] => [
  ...(d.themes ?? []).flatMap((t) => t.names),
  ...d.sectors.flatMap((s) => s.industries.flatMap((i) => i.names)),
];

/** The real read with the edge cases it does not carry. Every name in it has
 *  `period_ok: true`; these five rows exercise the other branches. A name that
 *  appears twice (theme + sector) is edited in both places, so both rows agree. */
function edgePayload(): HsPayload {
  const d = clone(REAL) as unknown as HsPayload;
  const syms = [...new Set(allNames(d).map((r) => r.symbol))];
  const edit = (sym: string, f: (r: HsName) => void) => allNames(d).filter((r) => r.symbol === sym).forEach(f);
  edit(syms[0], (r) => { r.period_ok = false; });
  edit(syms[1], (r) => { r.period_ok = null; });
  edit(syms[2], (r) => {
    r.sales_yoy = null; r.sales_prior_yoy = null; r.sales_accelerating = null; r.sales_tier = null;
    r.q_eps_yoy = null; r.net_margin = null; r.margin_expanding = null; r.eq_score = null;
    r.eq_tier = null; r.code_33 = null; r.inventory_flag = null; r.next_earnings = null;
    r.earnings_when = null; delete r.period_ok;
  });
  edit(syms[3], (r) => {
    r.sales_accelerating = true; r.margin_expanding = true; r.code_33 = true; r.inventory_flag = true;
    r.earnings_when = 'BMO'; r.eq_tier = 'not_a_served_tier'; r.sales_tier = 'declining';
    r.sales_yoy = -12.34; r.q_eps_yoy = 0; r.net_margin = -3.21; r.eq_score = 0;
  });
  edit(syms[4], (r) => { r.sales_tier = 'weak'; r.next_earnings = '2026-11-03'; r.earnings_when = null; });
  return d;
}

function stub(body: unknown) {
  vi.stubGlobal('fetch', vi.fn((url: string) => {
    const s = String(url);
    if (s.includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    return Promise.resolve({ ok: true, json: () => Promise.resolve(clone(body)) } as Response);
  }));
}

/** Draw the payload through the REAL component, expand all, and read each
 *  name row's six fund cells (the six columns after the legs). */
async function fundCells(d: HsPayload): Promise<{ symbol: string; cells: string[] }[]> {
  stub(d);
  const { container, unmount } = render(
    <MemoryRouter>
      <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
        <HottestSectors />
      </EnterableFilterProvider>
    </MemoryRouter>);
  await screen.findAllByText(/Technology/);
  /* The expand-all button is a toggle: press it until every group is open
     (at most twice — a partly open board closes first, then opens all). */
  const want = allNames(d).length;
  for (let i = 0; i < 2 && container.querySelectorAll('tr.hs-name').length !== want; i += 1) {
    fireEvent.click(screen.getByTestId('hs-expand-all'));
  }
  await waitFor(() => expect(container.querySelectorAll('tr.hs-name').length).toBe(want));
  const at = 1 + visibleCols(d).findIndex((c) => c.key === 'sales_yoy');
  const out = Array.from(container.querySelectorAll('tr.hs-name')).map((tr) => ({
    symbol: /open (\S+) in a new tab/.exec(tr.getAttribute('title') || '')?.[1] || '',
    cells: Array.from(tr.children).slice(at, at + FUND_CELLS).map((td) => (td as HTMLElement).outerHTML),
  }));
  unmount();
  return out;
}

const SCENARIOS: Record<string, () => HsPayload> = {
  real: () => clone(REAL) as unknown as HsPayload,
  edge: edgePayload,
};

beforeEach(() => {
  vi.stubGlobal('localStorage', memStorage());
  _resetSignalWatchlist(); _resetBounceRoomCache();
});
afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('GOLDEN: the six fund cells are byte-identical to the pre-extraction capture', () => {
  it.runIf(!!env('HS_FUND_GOLDEN_WRITE'))('writes the golden (run on the UNCHANGED HottestSectors.tsx)', async () => {
    const out: Golden = {};
    for (const [k, f] of Object.entries(SCENARIOS)) out[k] = await fundCells(f());
    const fs = await fsMod();
    fs.writeFileSync(`${root()}/${GOLDEN_REL}`, JSON.stringify(out, null, 1) + '\n', 'utf8');
    expect(out.real.length).toBeGreaterThan(0);
  });

  for (const k of Object.keys(SCENARIOS)) {
    it(`${k}: every name row's six fund <td>s equal the golden`, async () => {
      const fs = await fsMod();
      const golden: Golden = JSON.parse(fs.readFileSync(`${root()}/${GOLDEN_REL}`, 'utf8'));
      const want = golden[k];
      expect(want.length).toBe(allNames(SCENARIOS[k]()).length);
      for (const row of want) expect(row.cells.length).toBe(FUND_CELLS);
      const got = await fundCells(SCENARIOS[k]());
      expect(got.map((r) => r.symbol)).toEqual(want.map((r) => r.symbol));
      got.forEach((r, i) => expect(r.cells).toEqual(want[i].cells));
    });
  }

  it('NEGATIVE: the golden is not vacuous — the edge capture differs from the real one', async () => {
    const fs = await fsMod();
    const golden: Golden = JSON.parse(fs.readFileSync(`${root()}/${GOLDEN_REL}`, 'utf8'));
    const flat = (g: { cells: string[] }[]) => g.map((r) => r.cells.join(''));
    expect(flat(golden.edge)).not.toEqual(flat(golden.real));
    const edge = golden.edge.map((r) => r.cells.join('')).join('');
    expect(edge).toContain('⚠ pair');
    expect(edge).toContain('unverified');
    expect(edge).toContain('hs-pair-');
  });
});

// ───────────────────────────────────────────── HsFundCell on crafted rows
const FULL: HsFundRow = {
  sales_yoy: 25.04, sales_prior_yoy: 18.2, sales_accelerating: true, sales_tier: 'strong',
  period_ok: true, q_eps_yoy: 140.4, net_margin: 21.37, margin_expanding: true, eq_score: 82,
  eq_tier: 'red_flag', code_33: true, inventory_flag: true, next_earnings: '2026-11-04',
  earnings_when: 'AMC',
};
const EMPTY: HsFundRow = {
  sales_yoy: null, sales_prior_yoy: null, sales_accelerating: null, sales_tier: null,
  period_ok: null, q_eps_yoy: null, net_margin: null, margin_expanding: null, eq_score: null,
  eq_tier: null, code_33: null, inventory_flag: null, next_earnings: null, earnings_when: null,
};
const INFO = { tiers: [{ key: 'red_flag', label: 'Red flag' }] } as unknown as HsQualityInfo;

function cell(k: HsFundKey, r: HsFundRow, extra: { info?: HsQualityInfo | null; testId?: string } = {}) {
  const { container } = render(
    <table><tbody><tr><HsFundCell k={k} r={r} symbol="ABC" {...extra} /></tr></tbody></table>);
  const tds = container.querySelectorAll('td');
  expect(tds.length).toBe(1);
  return tds[0] as HTMLElement;
}

describe('HsFundCell — one <td> per key, the Hottest words', () => {
  it('sales_yoy: signed 1 dp, ⚡ when accelerating, prior quarter on the hover', () => {
    const td = cell('sales_yoy', FULL);
    expect(td.textContent).toBe('+25.0% ⚡');
    expect(td.className).toBe('mono hs-num hs-up');
    expect(td.getAttribute('title')).toBe('prior quarter +18.2%');
  });
  it('sales_tier: chip + tier; q_eps_yoy 0 dp; net_margin ↑; eq_score + flags + served tier label; Next ER + when', () => {
    expect(cell('sales_tier', FULL).textContent).toBe('💪 strong');
    expect(cell('q_eps_yoy', FULL).textContent).toBe('+140%');
    expect(cell('net_margin', FULL).textContent).toBe('+21.4% ↑');
    const q = cell('eq_score', FULL, { info: INFO });
    expect(q.textContent).toBe('82 🎯 ⚠️');
    expect(q.getAttribute('title')).toBe('Red flag');
    // NEGATIVE: without a served explainer the hover is the raw key, never blank
    expect(cell('eq_score', FULL).getAttribute('title')).toBe('red_flag');
    expect(cell('next_earnings', FULL).textContent).toBe('2026-11-04 AMC');
  });
  it('NEGATIVE: every missing value prints "—", never "0" (and no flag, no tone)', () => {
    for (const k of HS_FUND_KEYS) {
      const td = cell(k, EMPTY);
      expect(td.textContent).toContain('—');
      expect(td.textContent).not.toMatch(/\b0\b|0%|NaN|undefined|null/);
      expect(td.textContent).not.toMatch(/[⚡↑🎯⚠️]/u);
      expect(td.className).not.toMatch(/hs-up|hs-dn/);
    }
    // NEGATIVE: a missing sales_prior_yoy sets no hover; a missing tier says why
    expect(cell('sales_yoy', EMPTY).hasAttribute('title')).toBe(false);
    expect(cell('sales_tier', EMPTY).getAttribute('title')).toBe('no filed quarterly series from our provider');
    expect(cell('eq_score', EMPTY).hasAttribute('title')).toBe(false);
  });
  it('a real zero prints as a zero (it is a value, not a missing one)', () => {
    const z = { ...EMPTY, sales_yoy: 0, q_eps_yoy: 0, net_margin: 0, eq_score: 0 };
    expect(cell('sales_yoy', z).textContent).toBe('+0.0%');
    expect(cell('q_eps_yoy', z).textContent).toBe('+0%');
    expect(cell('net_margin', z).textContent).toBe('+0.0%');
    expect(cell('eq_score', z).textContent).toBe('0');
  });
  it('period_ok: null → "unverified", false → "⚠ pair", true → no mark (mark id uses `symbol`)', () => {
    const nul = cell('sales_tier', { ...FULL, period_ok: null });
    expect(nul.textContent).toBe('💪 strongunverified');
    expect(nul.querySelector('[data-testid="hs-pair-ABC"]')!.className).toBe('bd-unverified');
    const no = cell('sales_tier', { ...FULL, period_ok: false });
    expect(no.textContent).toBe('💪 strong⚠ pair');
    expect(no.querySelector('[data-testid="hs-pair-ABC"]')!.className).toBe('bd-pair-warn');
    const ok = cell('sales_tier', { ...FULL, period_ok: true });
    expect(ok.textContent).toBe('💪 strong');
    // NEGATIVE: a checked-and-fine pair prints no tick and no mark at all
    expect(ok.querySelector('[data-testid^="hs-pair-"]')).toBeNull();
    // the mark rides the em-dash too when the tier was withheld
    expect(cell('sales_tier', { ...EMPTY, period_ok: false }).textContent).toBe(' —⚠ pair');
    // NEGATIVE: the pair mark lives on the tier cell only
    for (const k of HS_FUND_KEYS.filter((x) => x !== 'sales_tier')) {
      expect(cell(k, { ...FULL, period_ok: false }).querySelector('[data-testid^="hs-pair-"]')).toBeNull();
    }
  });
  it('testId sets data-testid on the <td>; NEGATIVE: without it the <td> carries none', () => {
    for (const k of HS_FUND_KEYS) {
      expect(cell(k, FULL, { testId: `cm-hb-cell-${k}-ABC` }).getAttribute('data-testid')).toBe(`cm-hb-cell-${k}-ABC`);
      expect(cell(k, FULL).hasAttribute('data-testid')).toBe(false);
    }
    // the testId never replaces the pair mark's own id
    const t = cell('sales_tier', { ...FULL, period_ok: false }, { testId: 'x' });
    expect(t.querySelector('[data-testid="hs-pair-ABC"]')).not.toBeNull();
  });
  it('NEGATIVE: no cell says bounce or a forecast word', () => {
    for (const k of HS_FUND_KEYS) {
      for (const r of [FULL, EMPTY]) {
        expect(cell(k, r, { info: INFO }).outerHTML).not.toMatch(/bounce|predict|potential to|likely to/i);
      }
    }
  });
});

describe('HS_FUND_KEYS', () => {
  it('is HS_COLS minus the three legs, in order', () => {
    const legs = ['rel_1d', 'rel_5d', 'rel_21d'];
    expect([...HS_FUND_KEYS]).toEqual(HS_COLS.map((c) => c.key).filter((k) => !legs.includes(k)));
    expect(HS_FUND_KEYS.length).toBe(FUND_CELLS);
    // NEGATIVE: no leg leaked in
    for (const l of legs) expect(HS_FUND_KEYS as readonly string[]).not.toContain(l);
  });
});
