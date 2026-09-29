/* 💰 The Dual Momentum market-cap button + the served cap line (2026-09-29).
 * Ajay, verbatim: "Also a sort by market cap please".
 * Hand-written served `sorts` / `sort` / `cap_sort` shapes. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DualMomentumBoardNote, { DualMomentumSortToggle } from './DualMomentumBoardNote';
import { DM_SORT_MARKET_CAP, DM_SORT_MARKET_CAP_ASC, dmCapSortNext } from '../lib/chartMaps';
import type { CmDualMomentumBoard, CmSort } from '../lib/chartMaps';

const HI = '💰 Market cap — largest first';
const LO = '💰 Market cap — smallest first';
const SORTS: CmSort[] = [
  { key: 'default', label: '🏎️ Dual-momentum rank' },
  { key: 'nearest_demand', label: '📍 Nearest demand first' },
  { key: 'market_cap', label: HI },
  { key: 'market_cap_asc', label: LO },
];
const LINE = '💰 Ordered by market cap, largest first — the weekly shares-cache cap; display only, it gates nothing. 3 of 80 leaders have no cached market cap — they sit last, in rank order.';
const cap = () => screen.getByTestId('cm-dm-sort-market_cap') as HTMLButtonElement;
const board = (over: Partial<CmDualMomentumBoard> = {}): CmDualMomentumBoard => ({
  state: 'ready', counts: null, header: '🏎️ header', note: '🏎️ note', measured: false,
  sort: 'market_cap', ...over,
});

describe('dmCapSortNext', () => {
  it('largest first from anywhere, then smallest first, then back', () => {
    expect(dmCapSortNext(DM_SORT_MARKET_CAP)).toBe(DM_SORT_MARKET_CAP_ASC);
    expect(dmCapSortNext(DM_SORT_MARKET_CAP_ASC)).toBe(DM_SORT_MARKET_CAP);
    for (const v of ['default', 'nearest_demand', null, undefined, '', 'cap', 'MARKET_CAP']) {
      expect(dmCapSortNext(v)).toBe(DM_SORT_MARKET_CAP);
    }
    expect([DM_SORT_MARKET_CAP, DM_SORT_MARKET_CAP_ASC]).toEqual(['market_cap', 'market_cap_asc']);
  });
});

describe('DualMomentumSortToggle — the 💰 button', () => {
  afterEach(() => cleanup());

  it('from the rank: served largest-first label, not pressed; a click asks for market_cap', () => {
    const onSort = vi.fn();
    render(<DualMomentumSortToggle sorts={SORTS} sort="default" onSort={onSort} />);
    expect(cap().textContent).toBe(HI);
    expect(cap().getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(cap());
    expect(onSort).toHaveBeenCalledWith('market_cap');
    const buttons = Array.from(screen.getByTestId('cm-dm-toggle').querySelectorAll('button'));
    expect(buttons.map((b) => b.textContent)).toEqual(['🏎️ Dual-momentum rank', '📍 Nearest demand first', HI]);
  });

  it('served largest first: pressed, a second click flips to smallest first', () => {
    const onSort = vi.fn();
    render(<DualMomentumSortToggle sorts={SORTS} sort="market_cap" onSort={onSort} />);
    expect(cap().getAttribute('aria-pressed')).toBe('true');
    expect(cap().getAttribute('data-dir')).toBe('desc');
    expect(cap().textContent).toBe(HI);
    expect(screen.getByTestId('cm-dm-sort-default').getAttribute('aria-pressed')).toBe('false');
    fireEvent.click(cap());
    expect(onSort).toHaveBeenCalledWith('market_cap_asc');
  });

  it('served smallest first: the smallest label, pressed; a click flips back to largest', () => {
    const onSort = vi.fn();
    render(<DualMomentumSortToggle sorts={SORTS} sort="market_cap_asc" onSort={onSort} />);
    expect(cap().textContent).toBe(LO);
    expect(cap().getAttribute('data-dir')).toBe('asc');
    expect(cap().getAttribute('aria-pressed')).toBe('true');
    fireEvent.click(cap());
    expect(onSort).toHaveBeenCalledWith('market_cap');
  });

  it('NEGATIVE: either cap key not served -> no 💰 button, the 🏎️ / 📍 pair still renders', () => {
    for (const drop of ['market_cap', 'market_cap_asc']) {
      render(<DualMomentumSortToggle sorts={SORTS.filter((s) => s.key !== drop)} sort="default" onSort={() => {}} />);
      expect(screen.queryByTestId('cm-dm-sort-market_cap')).toBeNull();
      expect(screen.getByTestId('cm-dm-sort-nearest_demand')).toBeTruthy();
      cleanup();
    }
    render(<DualMomentumSortToggle sorts={[...SORTS.slice(0, 2), { key: 'market_cap', label: '' }, SORTS[3]]}
                                   sort="default" onSort={() => {}} />);
    expect(screen.queryByTestId('cm-dm-sort-market_cap')).toBeNull();
  });

  it('NEGATIVE: an unknown served sort presses nothing', () => {
    render(<DualMomentumSortToggle sorts={SORTS} sort="cap" onSort={() => {}} />);
    expect(cap().getAttribute('aria-pressed')).toBe('false');
    expect(cap().textContent).toBe(HI);
  });
});

describe('DualMomentumBoardNote — the served 💰 line', () => {
  afterEach(() => cleanup());
  const note = (b: CmDualMomentumBoard) => render(
    <MemoryRouter><DualMomentumBoardNote board={b} sorts={SORTS} sort={b.sort} onSort={() => {}} /></MemoryRouter>);

  it('prints the served line verbatim with role=status', () => {
    note(board({ cap_sort: { sort: 'market_cap', largest_first: true, ordered: 80, with_cap: 77,
                             no_cap: 3, line: LINE } }));
    const el = screen.getByTestId('cm-dm-cap-line');
    expect(el.textContent).toBe(LINE);
    expect(el.getAttribute('role')).toBe('status');
  });

  it('NEGATIVE: no / junk cap_sort -> no line, no junk text', () => {
    for (const junk of [null, undefined, 'x', ['a'], { line: 7 }, { line: '  ' }]) {
      note(board({ sort: 'default', cap_sort: junk as never }));
      expect(screen.queryByTestId('cm-dm-cap-line')).toBeNull();
      const txt = screen.getByTestId('cm-dm-board').textContent || '';
      for (const bad of ['[object Object]', 'NaN', 'undefined', 'bounce']) expect(txt.includes(bad), bad).toBe(false);
      cleanup();
    }
  });
});
