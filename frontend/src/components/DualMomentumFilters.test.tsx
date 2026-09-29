/* 🏎️ DualMomentumFilters — the 🌀 / 📍 / 🔑 boxes above the Dual Momentum grid (2026-09-29).
 * Ajay, verbatim: "Can you add AMD raided and near demand zone and near lower
 * Key level filters to dual momentum please".
 * Hand-written fixture in the served `dual_momentum_board.filters` shape. */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DualMomentumFilters } from './DualMomentumBoardNote';
import type { CmDmFilters } from '../lib/dmFilters';

const LINE = 'Filters on — 🌀 AMD raided: 5 pass, 75 hidden. 5 of 80 pass every ticked box (each count is over all 80 ranked leaders; a name can fail more than one).';
const served = (over: Partial<CmDmFilters> = {}): CmDmFilters => ({
  keys: ['amd', 'zone', 'level'], active: ['amd'], pool: 80, passed_all: 5,
  items: [
    { key: 'amd', label: '🌀 AMD raided', on: true, pass: 5, fail: 75, no_read: 0, hidden: 75,
      note: '🌀 AMD NOTE — MEASURED INVERTED' },
    { key: 'zone', label: '📍 Near demand zone', on: false, pass: 14, fail: 65, no_read: 1, hidden: 0,
      note: '📍 ZONE NOTE — UNMEASURED' },
    { key: 'level', label: '🔑 Near a lower key level', on: false, pass: 2, fail: 78, no_read: 0, hidden: 0,
      note: '🔑 LEVEL NOTE — UNMEASURED' },
  ],
  line: LINE, note: 'Ticked boxes narrow the leaders — every ticked box must pass.',
  near_demand_pct: 1, near_level_pct: 1, measured: false, ...over,
});
const box = (k: string) => screen.getByTestId(`cm-dm-filter-${k}`) as HTMLInputElement;

describe('DualMomentumFilters', () => {
  afterEach(() => cleanup());

  it('three boxes: served label + · served pass count; checked = served `on`', () => {
    render(<DualMomentumFilters filters={served()} onToggle={() => {}} />);
    const group = screen.getByTestId('cm-dm-filters');
    expect(group.getAttribute('role')).toBe('group');
    const labels = Array.from(group.querySelectorAll('label')).map((l) => l.textContent);
    expect(labels).toEqual(['🌀 AMD raided · 5', '📍 Near demand zone · 14', '🔑 Near a lower key level · 2']);
    expect(box('amd').checked).toBe(true);
    expect(box('zone').checked).toBe(false);
    expect(box('level').checked).toBe(false);
    // the unticked notes live in the hover only
    expect(group.querySelectorAll('label')[1].getAttribute('title')).toBe('📍 ZONE NOTE — UNMEASURED');
  });

  it('a click hands the key to onToggle (nothing flips locally)', () => {
    const onToggle = vi.fn();
    render(<DualMomentumFilters filters={served()} onToggle={onToggle} />);
    fireEvent.click(box('level'));
    expect(onToggle).toHaveBeenCalledWith('level');
    fireEvent.click(box('amd'));
    expect(onToggle).toHaveBeenLastCalledWith('amd');
    // checked is the SERVED on — still unchanged until a new payload lands
    expect(box('level').checked).toBe(false);
  });

  it('the served line verbatim with role=status; only ticked notes render', () => {
    render(<DualMomentumFilters filters={served()} onToggle={() => {}} />);
    const line = screen.getByTestId('cm-dm-filter-line');
    expect(line.textContent).toBe(LINE);
    expect(line.getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-dm-filter-note-amd').textContent).toBe('🌀 AMD NOTE — MEASURED INVERTED');
    expect(screen.queryByTestId('cm-dm-filter-note-zone')).toBeNull();
    expect(screen.queryByTestId('cm-dm-filter-note-level')).toBeNull();
    expect(screen.getByTestId('cm-dm-filters-note').textContent).toContain('every ticked box');
  });

  it('NEGATIVE: line null -> no line element; nothing ticked -> no notes', () => {
    const f = served({ active: [], passed_all: null, line: null,
                       items: served().items.map((i) => ({ ...i, on: false, hidden: 0 })) });
    render(<DualMomentumFilters filters={f} onToggle={() => {}} />);
    expect(screen.queryByTestId('cm-dm-filter-line')).toBeNull();
    expect(screen.queryByTestId('cm-dm-filters-note')).toBeNull();
    expect(document.querySelectorAll('[data-testid^="cm-dm-filter-note-"]')).toHaveLength(0);
    expect(screen.getByTestId('cm-dm-filters')).toBeTruthy();
  });

  it('NEGATIVE: null / {} / items not an array -> nothing rendered', () => {
    for (const bad of [null, undefined, {}, [], 'x', { items: 'x' }, { items: null }, { items: [] }]) {
      const { container } = render(<DualMomentumFilters filters={bad} onToggle={() => {}} />);
      expect(container.innerHTML, JSON.stringify(bad)).toBe('');
      cleanup();
    }
  });

  it('NEGATIVE: an unknown key or a label-less item is never rendered', () => {
    const f = served();
    f.items = [...f.items, { key: 'rsi', label: 'RSI', on: true, pass: 9, fail: 0, no_read: 0, hidden: 0, note: 'x' },
               { key: 'zone', label: '', on: false, pass: 1, fail: 0, no_read: 0, hidden: 0, note: 'y' } as never];
    render(<DualMomentumFilters filters={f} onToggle={() => {}} />);
    expect(screen.queryByTestId('cm-dm-filter-rsi')).toBeNull();
    expect(screen.getAllByTestId('cm-dm-filter-zone')).toHaveLength(1);
    expect(screen.getByTestId('cm-dm-filters').textContent).not.toContain('RSI');
  });

  it('NEGATIVE: no bounce / [object Object] / NaN / undefined in the text; a bad count prints no count', () => {
    const f = served();
    (f.items[2] as unknown as { pass: unknown }).pass = Number.NaN;
    const { container } = render(<DualMomentumFilters filters={f} onToggle={() => {}} />);
    const txt = container.textContent || '';
    for (const bad of ['bounce', 'Bounce', '[object Object]', 'NaN', 'undefined']) {
      expect(txt.includes(bad), bad).toBe(false);
    }
    expect(box('level').parentElement!.textContent).toBe('🔑 Near a lower key level');
  });
});
