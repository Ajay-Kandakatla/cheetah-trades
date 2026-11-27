/* 📅 The two served chips on a seated name's compact tile (2026-11-26, spec watchrun rev 2 §3.5, WP fe-roster). Ajay: "Ok
 * then add them to our watch list and track them please..". GgwProvLine draws `row.runner` day · seat after the when chip
 * (hover = the served seat title); GgwDrawer prints the served seat title. NEGATIVE: a row without `runner` draws nothing
 * new; junk `runner` draws nothing. */
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import board from '../lib/__fixtures__/ggwAllRules.golden.json';
import gold from '../lib/__fixtures__/ggwRunRoster.golden.json';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import { GgwDrawer, GgwProvLine } from './GajjalaWatchCompact';

const G = gold as any;
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
function row(runner?: unknown, org = true): GgwRow {
  const raw = clone(board) as any;
  if (runner !== undefined) raw.rows[0].runner = runner;
  if (!org) raw.rows[0].org = null;
  return (parseGgw(raw) as GgwBoard).rows[0];
}
afterEach(() => cleanup());

describe('📅 runner chips on the tile', () => {
  it('after the when chip: the served day chip, then the served seat chip (hover = the served seat title)', () => {
    const r = row(clone(G.row_runner));
    render(<GgwProvLine row={r} />);
    const line = screen.getByTestId(`ggw-prov-${r.symbol}`);
    const kids = Array.from(line.children).map((e) => e.getAttribute('data-testid'));
    expect(kids.slice(0, 3)).toEqual([`ggw-when-${r.symbol}`, `ggw-runner-day-${r.symbol}`, `ggw-runner-seat-${r.symbol}`]);
    expect(screen.getByTestId(`ggw-runner-day-${r.symbol}`).textContent).toBe(G.row_runner.day_text);
    expect(screen.getByTestId(`ggw-runner-seat-${r.symbol}`).textContent).toBe(G.row_runner.seat_text);
    expect(screen.getByTestId(`ggw-runner-seat-${r.symbol}`).getAttribute('title')).toBe(G.row_runner.seat_title);
  });
  it('a seated name with no other time chip still gets its line', () => {
    const r = row(clone(G.row_runner), false);
    render(<GgwProvLine row={r} />);
    expect(screen.getByTestId(`ggw-runner-day-${r.symbol}`)).not.toBeNull();
  });
  it('the drawer prints the served seat title (a phone has no hover)', () => {
    const r = row(clone(G.row_runner));
    render(<GgwDrawer row={r} open />);
    expect(screen.getByTestId('ggw-runner-title').textContent).toBe(G.row_runner.seat_title);
  });
  it('NEGATIVE: a tile without `runner` draws no new chip and no drawer line', () => {
    const r = row();
    const a = render(<><GgwProvLine row={r} /><GgwDrawer row={r} open /></>);
    expect(a.container.querySelector('[data-testid^="ggw-runner-"]')).toBeNull();
  });
  it('NEGATIVE: junk `runner` → nothing new; no runner and no org → no line at all', () => {
    const r = row({ seat_title: 'x' });
    const a = render(<GgwProvLine row={r} />);
    expect(a.container.querySelector('[data-testid^="ggw-runner-"]')).toBeNull();
    a.unmount();
    const bare = render(<GgwProvLine row={row(undefined, false)} />);
    expect(bare.container.innerHTML).toBe('');
  });
});
