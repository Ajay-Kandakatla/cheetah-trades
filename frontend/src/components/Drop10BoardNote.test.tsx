/* Drop10BoardNote — prints the SERVED 🔻 board lines, nothing composed. */
import { describe, expect, it, vi, afterEach } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import Drop10BoardNote from './Drop10BoardNote';
import FIXTURE from './__fixtures__/drop10_tab_2026_10_02.json';
import type { CmDrop10Board } from '../lib/drop10';
import type { CmSort } from '../lib/chartMaps';

type Payload = { drop10_board: CmDrop10Board; sorts: CmSort[]; sort: string };
const F = FIXTURE as unknown as { default: Payload; warming: Payload };
const READY = F.default.drop10_board;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x)) as T;

afterEach(() => cleanup());

describe('Drop10BoardNote', () => {
  it('prints the served header, order, counts and note verbatim, and the served sorts', () => {
    const onSort = vi.fn();
    render(<Drop10BoardNote board={READY} sorts={F.default.sorts} sort="default" onSort={onSort} />);
    expect(screen.getByTestId('cm-drop10-header').textContent).toBe(READY.header);
    expect(screen.getByTestId('cm-drop10-order').textContent).toBe(READY.order_line);
    expect(screen.getByTestId('cm-drop10-counts').textContent).toBe(READY.count_line);
    expect(screen.getByTestId('cm-drop10-note').textContent).toBe(READY.note);
    expect(screen.getByTestId('cm-drop10-board').getAttribute('data-mode')).toBe('closed');
    const keys = F.default.sorts.map((s) => s.key);
    expect(keys).toEqual(['default', 'drop10_now', 'drop10_reclaim', 'drop10_rvol']);
    for (const s of F.default.sorts) {
      const b = screen.getByTestId(`cm-drop10-sort-${s.key}`);
      expect(b.textContent).toBe(s.label);
      expect(b.getAttribute('aria-pressed')).toBe(s.key === 'default' ? 'true' : 'false');
    }
    fireEvent.click(screen.getByTestId('cm-drop10-sort-drop10_rvol'));
    expect(onSort).toHaveBeenCalledWith('drop10_rvol');
    expect(screen.getByTestId('cm-drop10-sources').tagName).toBe('DETAILS');
  });

  it('NEGATIVE: pressed is the SERVED sort, never a guess', () => {
    render(<Drop10BoardNote board={READY} sorts={F.default.sorts} sort="drop10_now" onSort={() => {}} />);
    expect(screen.getByTestId('cm-drop10-sort-drop10_now').getAttribute('aria-pressed')).toBe('true');
    expect(screen.getByTestId('cm-drop10-sort-default').getAttribute('aria-pressed')).toBe('false');
  });

  it('the held-out fold renders the served names only when the served count is above zero', () => {
    const b = clone(READY);
    b.suspects = { n: 1, head: 'H-1 held out', lines: ['BRK-B — low −12.00% vs prior close 400.00: x'] };
    render(<Drop10BoardNote board={b} sorts={[]} sort="default" onSort={() => {}} />);
    expect(screen.getByTestId('cm-drop10-suspects').textContent).toContain('H-1 held out');
    expect(screen.getByTestId('cm-drop10-suspect').textContent).toContain('BRK-B');
    cleanup();
    const z = clone(READY);
    z.suspects = { n: 0, head: 'H-0', lines: [] };
    render(<Drop10BoardNote board={z} sorts={[]} sort="default" onSort={() => {}} />);
    expect(screen.queryByTestId('cm-drop10-suspects')).toBeNull();
  });

  it('NEGATIVE: warming shows only the served warming line as a status — no sources, no held-out fold', () => {
    const w = F.warming.drop10_board;
    render(<Drop10BoardNote board={w} sorts={F.warming.sorts} sort="default" onSort={() => {}} />);
    expect(screen.getByTestId('cm-drop10-board').getAttribute('data-state')).toBe('warming');
    expect(screen.getByTestId('cm-drop10-header').getAttribute('role')).toBe('status');
    expect(screen.getByTestId('cm-drop10-header').textContent).toBe(w.header);
    expect(screen.queryByTestId('cm-drop10-sources')).toBeNull();
    expect(screen.queryByTestId('cm-drop10-suspects')).toBeNull();
    expect(screen.queryByTestId('cm-drop10-counts')).toBeNull();
  });

  it('NEGATIVE: an absent, malformed or header-less block renders nothing', () => {
    for (const bad of [null, undefined, 'x', [], { state: 'ready' }, { header: '   ' }]) {
      const { container } = render(<Drop10BoardNote board={bad as unknown as CmDrop10Board} sorts={[]} onSort={() => {}} />);
      expect(container.innerHTML).toBe('');
      cleanup();
    }
  });
});
