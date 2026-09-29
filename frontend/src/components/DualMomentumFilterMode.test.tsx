/* 🏎️ The "must match all" switch beside the 🌀 / 📍 / 🔑 boxes (2026-09-29).
 * Ajay, verbatim: "How can I see all of these? at the same time? is there a
 * check box selection?"
 * Hand-written fixture in the served `dual_momentum_board.filters` shape. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DualMomentumFilters } from './DualMomentumBoardNote';
import type { CmDmFilters } from '../lib/dmFilters';

const ANY_LINE = 'Filters on (any ticked box) — 🌀 AMD raided: 5 pass; 📍 Near demand zone: 12 pass; 🔑 Near a lower key level: 2 pass. 16 of 80 pass at least one ticked box, 64 hidden (they pass none of them; a leader passing several shows once, with a badge for each).';
const served = (over: Partial<CmDmFilters> = {}): CmDmFilters => ({
  keys: ['amd', 'zone', 'level'], active: ['amd', 'zone', 'level'], pool: 80,
  passed_all: 0, passed_any: 16, shown: 16, hidden: 64,
  mode: 'any', mode_param: 'dm_mode', mode_all_label: 'must match all',
  items: [
    { key: 'amd', label: '🌀 AMD raided', on: true, pass: 5, fail: 75, no_read: 0, hidden: 75, note: 'A' },
    { key: 'zone', label: '📍 Near demand zone', on: true, pass: 12, fail: 68, no_read: 0, hidden: 68, note: 'Z' },
    { key: 'level', label: '🔑 Near a lower key level', on: true, pass: 2, fail: 78, no_read: 0, hidden: 78, note: 'L' },
  ],
  line: ANY_LINE, note: 'Ticked boxes narrow the leaders — a leader passing ANY ticked box shows.',
  near_demand_pct: 1, near_level_pct: 1, measured: false, ...over,
});
const sw = () => screen.getByTestId('cm-dm-filter-mode') as HTMLInputElement;

describe('DualMomentumFilters — the "must match all" switch', () => {
  afterEach(() => cleanup());

  it('renders the served label after the boxes; unchecked in ANY; the served ANY line verbatim', () => {
    render(<DualMomentumFilters filters={served()} onToggle={() => {}} onToggleMode={() => {}} />);
    const group = screen.getByTestId('cm-dm-filters');
    const labels = Array.from(group.querySelectorAll('label')).map((l) => l.textContent);
    expect(labels[labels.length - 1]).toBe('must match all');
    expect(sw().checked).toBe(false);
    expect(screen.getByTestId('cm-dm-filter-line').textContent).toBe(ANY_LINE);
  });

  it('checked = the SERVED mode all; a click hands off to onToggleMode (nothing flips locally)', () => {
    const onToggleMode = vi.fn();
    render(<DualMomentumFilters filters={served({ mode: 'all' })} onToggle={() => {}} onToggleMode={onToggleMode} />);
    expect(sw().checked).toBe(true);
    fireEvent.click(sw());
    expect(onToggleMode).toHaveBeenCalledTimes(1);
    expect(sw().checked).toBe(true);
  });

  it('NEGATIVE: an unknown / missing served mode reads as unchecked (any)', () => {
    for (const mode of ['foo', undefined, 'ALL']) {
      render(<DualMomentumFilters filters={served({ mode })} onToggle={() => {}} onToggleMode={() => {}} />);
      expect(sw().checked, String(mode)).toBe(false);
      cleanup();
    }
  });

  it('NEGATIVE: no box ticked, no served label, or no handler -> no switch', () => {
    const none = served({ active: [], line: null, items: served().items.map((i) => ({ ...i, on: false, hidden: 0 })) });
    const cases: Array<[CmDmFilters, boolean]> = [[none, true], [served({ mode_all_label: undefined }), true],
      [served({ mode_all_label: '  ' }), true], [served(), false]];
    for (const [f, withHandler] of cases) {
      render(<DualMomentumFilters filters={f} onToggle={() => {}} onToggleMode={withHandler ? () => {} : undefined} />);
      expect(screen.queryByTestId('cm-dm-filter-mode')).toBeNull();
      expect(screen.getByTestId('cm-dm-filters')).toBeTruthy();
      cleanup();
    }
  });

  it('NEGATIVE: the switch composes no count and never says bounce', () => {
    const { container } = render(<DualMomentumFilters filters={served()} onToggle={() => {}} onToggleMode={() => {}} />);
    expect(sw().parentElement!.textContent).toBe('must match all');
    expect(/bounce|NaN|undefined|\[object Object\]/i.test(container.textContent || '')).toBe(false);
  });
});
