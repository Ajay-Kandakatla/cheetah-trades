/* 🔥 Hottest — ⊞ Expand all, through the REAL component (2026-09-22).
 *
 * Ajay, over a screenshot of the Defense roster open: *"Also give me toggle
 * option to open them app on one click in stead of clicking on the carets"*.
 *
 * WHY THIS SUITE IS SHAPED THE WAY IT IS
 * --------------------------------------
 * The obvious test — "click ⊞, assert the roster's names render" — PASSES on a
 * top-level-only rule and would have shipped the ask half-answered. In the
 * DEFAULT view (`byIndustry` is on) a sector renders its INDUSTRIES and not its
 * names: the names hang off the industry caret. So the deep case asserts BOTH
 * halves — the roster's names AND a provider sector's name rows under their
 * industry — and the shallow case asserts that no industry row exists to open.
 *
 * THE GUARD: the 📰 news-tag rows share the very same open map (`${k}|tag`).
 * Without the `endsWith('|tag')` clause, one click dumps every LLM briefing
 * into the table. That is a pinned negative here, in both views.
 *
 * THE ROW COUNT on the button's hover is a FACT computed from the payload, not
 * a guess — so it is asserted against a hand-count as well as against
 * `expandRowCount`, or the two could be wrong together.
 */
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  HS_EXPAND_KEY, HottestSectors, allGroupsOpen, expandRowCount, isGroupOpen, openedKeys,
  readExpandAllPref, setAll, toggleKey, topLevelKeys, writeExpandAllPref,
} from './HottestSectors';
import type { HsOpen, HsPayload } from './HottestSectors';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { EnterableFilterProvider } from '../hooks/useEnterableFilter';
import { _resetBounceRoomCache } from '../hooks/useBounceRoom';

const name = (symbol: string, industry: string) => ({
  symbol, name: `${symbol} Inc`, industry,
  rel_1d: 1.2, rel_5d: 3.4, rel_21d: 5.6, d1_source: 'close' as const,
  sales_yoy: 12.3, sales_tier: 'strong', q_eps_yoy: 40, net_margin: 8.1,
  eq_score: 61, next_earnings: '2026-11-04',
});
const medians = {
  sales_yoy: 9, sales_tier: 'steady', q_eps_yoy: 11, net_margin: 6, eq_score: 55,
  rel_1d: 0.5, rel_5d: 2.1, rel_21d: 4.2, d1_source: 'close' as const,
};

/* His screenshot's six, verbatim. */
const DEFENSE = ['KRMN', 'RCAT', 'LASR', 'KTOS', 'ONDS', 'BBAI'];

const DAY_TAG = {
  date: '2026-09-19', sector: 'Technology', symbol: 'AVGO', company: 'Broadcom',
  positive: true, why_positive: 'a raised guide',
  bull: 'THE BULL SENTENCE ONLY THE BRIEFING CARRIES',
  bear: 'THE BEAR SENTENCE ONLY THE BRIEFING CARRIES',
  headline_count: 4, trigger: null, headlines: [], facts: null,
  read_by: 'the local model', measured: false,
};

const payload = (over: Record<string, unknown> = {}): HsPayload => ({
  as_of: '2026-09-19', benchmark: { symbol: 'RSP' }, sorted_by: 'rel_5d',
  sorted_dir: 'desc', legs: ['rel_1d', 'rel_5d', 'rel_21d'],
  d1: { basis: 'close', live: false, close_as_of: '2026-09-19', benchmark: 'RSP',
        market_closed: null, in_session: false, session_window: '9:30-16:00 ET',
        reason: 'the market is closed' },
  themes: [{
    group: 'defense', n_full: 24, ranked: true, thin: false, basis: 'full membership',
    ...medians,
    names: DEFENSE.map((s) => name(s, 'Aerospace & Defense')), names_total: 24,
  }, {
    group: 'robotics', n_full: 12, ranked: true, thin: false, basis: 'full membership',
    ...medians, names: [name('SYM', 'Industrials')], names_total: 12,
  }],
  sectors: [{
    group: 'Technology', n_full: 40, sampled_of: 40, sampled_used: 40,
    basis: 'rotation grid sample', n_measured: 40, ...medians,
    day_tag: DAY_TAG,
    names: [name('NVDA', 'Semiconductors'), name('MSFT', 'Software')], names_total: 40,
    industries: [{
      group: 'Semiconductors', n_full: 18, ranked: true, thin: false,
      basis: 'full membership', ...medians,
      names: [name('NVDA', 'Semiconductors'), name('AMAT', 'Semiconductors')],
      names_total: 18,
    }, {
      group: 'Software', n_full: 22, ranked: true, thin: false, basis: 'full membership',
      ...medians, names: [name('MSFT', 'Software')], names_total: 22,
    }],
  }, {
    group: 'Healthcare', n_full: 30, sampled_of: 30, sampled_used: 30,
    basis: 'rotation grid sample', n_measured: 30, ...medians,
    names: [name('LLY', 'Drug Manufacturers')], names_total: 30,
    industries: [{
      group: 'Drug Manufacturers', n_full: 14, ranked: true, thin: false,
      basis: 'full membership', ...medians,
      names: [name('LLY', 'Drug Manufacturers')], names_total: 14,
    }],
  }],
  ...over,
});

/* HAND-COUNTED from the fixture above, so a bug in expandRowCount cannot make
 * the button's hover and its own helper agree with each other and be wrong.
 *   deep    = 6 defense names + 1 robotics name
 *           + Technology: 2 industry rows + (2 + 1) names
 *           + Healthcare: 1 industry row  + 1 name          = 14
 *   shallow = 6 + 1 + Technology's own 2 + Healthcare's own 1 = 10 */
const DEEP_ROWS = 14;
const SHALLOW_ROWS = 10;

const stubSeq = (bodies: unknown[]) => {
  const urls: string[] = [];
  const fn = vi.fn((url: string) => {
    if (String(url).includes('/supply-demand/bounce-room')) {
      return Promise.resolve({ ok: true, json: () => Promise.resolve({ rows: [] }) } as Response);
    }
    urls.push(String(url));
    const body = bodies[Math.min(urls.length - 1, bodies.length - 1)];
    return Promise.resolve({ ok: true, json: () => Promise.resolve(body) } as Response);
  });
  vi.stubGlobal('fetch', fn);
  return { fn, urls };
};

const view = () => render(
  <MemoryRouter>
    <EnterableFilterProvider enterableOnly={false} kind="demand" setEnterableOnly={() => {}}>
      <HottestSectors />
    </EnterableFilterProvider>
  </MemoryRouter>);

const groupRows = (c: HTMLElement) =>
  [...c.querySelectorAll('tr.hs-sector, tr.hs-industry')]
    .map((r) => r.querySelector('.hs-disc')?.textContent?.replace(/^[▾▸]\s*/, '') || '');
/** The TICKER of every name row, in print order. The company name is a link
 *  in the same cell since 2026-09-19, so the first anchor is the one. */
const nameCells = (c: HTMLElement) =>
  [...c.querySelectorAll('tr.hs-name td.hs-sym')].map((td) => td.querySelector('a')?.textContent);
/** One group's caret, by the label it prints. */
const caret = (c: HTMLElement, label: string) =>
  [...c.querySelectorAll('.hs-disc')]
    .find((b) => (b.textContent || '').replace(/^[▾▸]\s*/, '') === label) as HTMLElement;

/** Flip "Break into industries". */
const setByIndustry = (c: HTMLElement, on: boolean) => {
  const box = c.querySelector('.hs-toggle input') as HTMLInputElement;
  fireEvent.click(box);
  expect(box.checked).toBe(on);
};

/* The shared setup leaves no real Storage on the global, and this board's
 * whole point here is that the choice is REMEMBERED — so give the suite a
 * real in-memory one (the PromoCircuit `pcw.capFloor` precedent). */
const mem = () => {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => { m.set(k, String(v)); },
    removeItem: (k: string) => { m.delete(k); },
    clear: () => m.clear(), key: () => null, get length() { return m.size; },
  };
};

beforeEach(() => {
  _resetSignalWatchlist(); _resetBounceRoomCache();
  vi.stubGlobal('localStorage', mem());
});
afterEach(() => { vi.unstubAllGlobals(); });

// ---------------------------------------------------------------------------
// 1 · one click, in the view that actually loads
// ---------------------------------------------------------------------------
describe('⊞ in the DEFAULT view (byIndustry on)', () => {
  it('opens the rosters AND the sectors AND the industries under them', async () => {
    stubSeq([payload()]);
    const { container } = view();
    fireEvent.click(await screen.findByTestId('hs-expand-all'));

    // his screenshot's six, from the roster
    for (const s of DEFENSE) expect(await screen.findByText(s)).toBeInTheDocument();
    // AND a provider sector's NAME rows, which hang off the INDUSTRY caret in
    // this view — the half a top-level-only rule would have left blank
    expect(screen.getByText('AMAT')).toBeInTheDocument();
    expect(screen.getByText('LLY')).toBeInTheDocument();
    expect(groupRows(container)).toEqual([
      'Defense', 'Robotics', 'Technology', 'Semiconductors', 'Software',
      'Healthcare', 'Drug Manufacturers',
    ]);
    expect(container.querySelectorAll('tr.hs-name').length).toBe(DEEP_ROWS - 3);
  });

  it('the hover carries the exact DEEP row count for this payload', async () => {
    stubSeq([payload()]);
    view();
    const btn = await screen.findByTestId('hs-expand-all');
    expect(expandRowCount(payload(), true)).toBe(DEEP_ROWS);
    expect(btn.getAttribute('title')).toContain(`${DEEP_ROWS} rows from this payload`);
    expect(btn.getAttribute('title')).toContain('remembered on this browser');
    expect(btn.textContent).toContain('⊞ Expand all');
  });

  it('NEGATIVE: it opens NO 📰 news briefing', async () => {
    const { container } = (stubSeq([payload()]), view());
    fireEvent.click(await screen.findByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    expect(container.querySelectorAll('tr.hs-daytag').length).toBe(0);
    expect(screen.queryByText(DAY_TAG.bull)).toBe(null);
    expect(screen.queryByText(DAY_TAG.bear)).toBe(null);
    // …and the chip is still there, still closed, still clickable on its own
    const chip = screen.getByTitle(/A bull case AND a bear case/);
    expect(chip.getAttribute('aria-expanded')).toBe('false');
    fireEvent.click(chip);
    expect(await screen.findByText(DAY_TAG.bull)).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 2 · the other view — the depth follows the checkbox
// ---------------------------------------------------------------------------
describe('⊞ with "Break into industries" off', () => {
  it('opens rosters and sectors and prints their OWN names; no industry row exists', async () => {
    const { container } = (stubSeq([payload()]), view());
    await screen.findByTestId('hs-expand-all');
    setByIndustry(container, false);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('KRMN');
    expect(groupRows(container)).toEqual(['Defense', 'Robotics', 'Technology', 'Healthcare']);
    expect(container.querySelectorAll('tr.hs-industry').length).toBe(0);
    expect(screen.getByText('MSFT')).toBeInTheDocument();
    expect(screen.queryByText('AMAT')).toBe(null);   // lives only under an industry
    expect(container.querySelectorAll('tr.hs-name').length).toBe(SHALLOW_ROWS);
    expect(expandRowCount(payload(), false)).toBe(SHALLOW_ROWS);
    expect(screen.getByTestId('hs-expand-all').getAttribute('title'))
      .toContain(`${SHALLOW_ROWS} rows`);
  });

  it('NEGATIVE: no |i: key is open, and flipping the checkbox back re-opens them', async () => {
    const { container } = (stubSeq([payload()]), view());
    await screen.findByTestId('hs-expand-all');
    setByIndustry(container, false);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('MSFT');
    expect(container.querySelectorAll('tr.hs-industry').length).toBe(0);

    setByIndustry(container, true);
    expect(await screen.findByText('AMAT')).toBeInTheDocument();
    expect(container.querySelectorAll('tr.hs-industry').length).toBe(3);
    // the state itself holds NO per-caret entry — the depth was re-derived
    expect(isGroupOpen({ all: true, ov: {} }, 's:Technology|i:Software', true)).toBe(true);
    expect(isGroupOpen({ all: true, ov: {} }, 's:Technology|i:Software', false)).toBe(false);
  });

  it('NEGATIVE: no 📰 briefing opens in this view either', async () => {
    const { container } = (stubSeq([payload()]), view());
    await screen.findByTestId('hs-expand-all');
    setByIndustry(container, false);
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('MSFT');
    expect(container.querySelectorAll('tr.hs-daytag').length).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// 3 · the second click, and the carets he still moves by hand
// ---------------------------------------------------------------------------
describe('collapse, and the individual carets', () => {
  it('a second click puts the board back exactly where it mounted', async () => {
    const { container } = (stubSeq([payload()]), view());
    await screen.findByTestId('hs-expand-all');
    const atMount = { groups: groupRows(container), names: nameCells(container) };

    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    expect(screen.getByTestId('hs-expand-all').textContent).toContain('⊟ Collapse all');

    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(screen.queryByText('AMAT')).toBe(null));
    expect(groupRows(container)).toEqual(atMount.groups);
    expect(nameCells(container)).toEqual(atMount.names);
    expect(screen.getByTestId('hs-expand-all').textContent).toContain('⊞ Expand all');
  });

  it('NEGATIVE: a caret closed by hand under ⊞ stays closed, and a caret after ⊟ behaves as before', async () => {
    const { container } = (stubSeq([payload()]), view());
    fireEvent.click(await screen.findByTestId('hs-expand-all'));
    await screen.findByText('KRMN');

    // close the Defense roster by hand while everything else stays open
    fireEvent.click(caret(container, 'Defense'));
    await waitFor(() => expect(screen.queryByText('KRMN')).toBe(null));
    expect(screen.getByText('AMAT')).toBeInTheDocument();
    expect(screen.getByTestId('hs-expand-all').textContent).toContain('⊞ Expand all');

    // …and after a full collapse, one caret opens exactly one group
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('KRMN');
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(screen.queryByText('KRMN')).toBe(null));
    fireEvent.click(caret(container, 'Robotics'));
    expect(await screen.findByText('SYM')).toBeInTheDocument();
    expect(screen.queryByText('KRMN')).toBe(null);
    expect(screen.queryByText('AMAT')).toBe(null);
  });

  it('NEGATIVE: the toggle reorders nothing — group and name order survive both clicks', async () => {
    const { container } = (stubSeq([payload()]), view());
    fireEvent.click(await screen.findByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    const first = { groups: groupRows(container), names: nameCells(container) };
    expect(first.names).toEqual([...DEFENSE, 'SYM', 'NVDA', 'AMAT', 'MSFT', 'LLY']);

    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await waitFor(() => expect(screen.queryByText('AMAT')).toBe(null));
    fireEvent.click(screen.getByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    expect(groupRows(container)).toEqual(first.groups);
    expect(nameCells(container)).toEqual(first.names);
  });
});

// ---------------------------------------------------------------------------
// 4 · the choice is remembered, and a re-scan inherits it
// ---------------------------------------------------------------------------
describe('persistence, and a payload that arrives later', () => {
  it('unmount + remount reads hs.expandAll and comes back expanded', async () => {
    stubSeq([payload()]);
    const first = view();
    fireEvent.click(await screen.findByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    expect(localStorage.getItem(HS_EXPAND_KEY)).toBe('open');
    first.unmount();

    _resetBounceRoomCache();
    const { container } = view();
    expect(await screen.findByText('AMAT')).toBeInTheDocument();
    expect(await screen.findByText('KRMN')).toBeInTheDocument();
    expect(container.querySelectorAll('tr.hs-industry').length).toBe(3);
    expect(readExpandAllPref()).toBe(true);
  });

  it('a sector that only appears in the SECOND payload renders OPEN', async () => {
    const second = payload();
    second.sectors = [...second.sectors, {
      group: 'Energy', n_full: 20, sampled_of: 20, sampled_used: 20,
      basis: 'rotation grid sample', n_measured: 20, ...medians,
      names: [name('CEG', 'Utilities')], names_total: 20,
      industries: [{
        group: 'Utilities', n_full: 9, ranked: true, thin: false, basis: 'full membership',
        ...medians, names: [name('CEG', 'Utilities')], names_total: 9,
      }],
    }];
    stubSeq([payload(), second]);
    view();
    fireEvent.click(await screen.findByTestId('hs-expand-all'));
    await screen.findByText('AMAT');
    fireEvent.click(screen.getByTestId('hottest-rescan'));
    expect(await screen.findByText('CEG')).toBeInTheDocument();
    expect(screen.getByText(/Utilities/)).toBeInTheDocument();
  });

  it('NEGATIVE: a throwing localStorage still toggles, and the default stays closed', async () => {
    const boom = () => { throw new Error('private mode'); };
    const store = { getItem: boom, setItem: boom, removeItem: boom,
                    clear: boom, key: boom, length: 0 };
    vi.stubGlobal('localStorage', store as unknown as Storage);
    expect(readExpandAllPref()).toBe(null);
    expect(() => writeExpandAllPref(true)).not.toThrow();

    stubSeq([payload()]);
    const { container } = view();
    const btn = await screen.findByTestId('hs-expand-all');
    expect(screen.queryByText('KRMN')).toBe(null);       // default is closed
    act(() => { fireEvent.click(btn); });
    expect(await screen.findByText('AMAT')).toBeInTheDocument();
    expect(container.querySelectorAll('tr.hs-industry').length).toBe(3);
  });
});

// ---------------------------------------------------------------------------
// 5 · the pure helpers, on the shapes the board really builds
// ---------------------------------------------------------------------------
describe('the helpers', () => {
  it('openedKeys is the top level plus every industry, and never a |tag key', () => {
    const deep = openedKeys(payload(), true);
    expect(topLevelKeys(payload())).toEqual(['t:defense', 't:robotics', 's:Technology', 's:Healthcare']);
    expect(deep).toContain('s:Technology|i:Semiconductors');
    expect(deep).toContain('s:Healthcare|i:Drug Manufacturers');
    expect(deep.some((k) => k.endsWith('|tag'))).toBe(false);
    expect(openedKeys(payload(), false)).toEqual(topLevelKeys(payload()));
    expect(openedKeys(null, true)).toEqual([]);
  });

  it('allGroupsOpen is false on an empty board — the button never mounts saying Collapse', () => {
    expect(allGroupsOpen({ all: true, ov: {} }, [], true)).toBe(false);
    expect(allGroupsOpen({ all: true, ov: {} }, openedKeys(payload(), true), true)).toBe(true);
    const partly: HsOpen = { all: true, ov: { 't:defense': false } };
    expect(allGroupsOpen(partly, openedKeys(payload(), true), true)).toBe(false);
  });

  it('toggleKey flips what is on SCREEN, and setAll clears every hand-moved caret', () => {
    const o: HsOpen = { all: true, ov: {} };
    expect(toggleKey(o, 't:defense', true).ov['t:defense']).toBe(false);
    expect(toggleKey({ all: false, ov: {} }, 't:defense', true).ov['t:defense']).toBe(true);
    expect(setAll(false)).toEqual({ all: false, ov: {} });
  });

  it('expandRowCount counts the industry rows it reveals, and zero for an empty payload', () => {
    expect(expandRowCount(payload(), true)).toBe(DEEP_ROWS);
    expect(expandRowCount(payload(), false)).toBe(SHALLOW_ROWS);
    expect(expandRowCount(null, true)).toBe(0);
    expect(expandRowCount({ sectors: [] } as unknown as HsPayload, true)).toBe(0);
  });
});
