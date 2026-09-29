/* AlertItems — every entry of a consolidated push, each ticker its own link.
 *
 * Ajay 2026-09-29: "I am unable to see the other that are hiddedn her … Can you
 * show them all and make all the tickers clicable individually?"
 * Pinned with negatives: only the SYMBOL is a link (never the line), a
 * lower-case or embedded token never links, the fold never hides an entry
 * for good, and no anchor ever sits inside another.
 */
import { describe, it, expect } from 'vitest';
import { fireEvent, render, screen, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { AlertItems, ITEMS_FOLD_AT, splitAtSymbol, tabFromUrl, type AlertItem } from './AlertItems';

const draw = (items: AlertItem[], notStored?: number | null) =>
  render(<MemoryRouter initialEntries={['/alerts']}><AlertItems items={items} notStored={notStored} /></MemoryRouter>);

const tape = (sym: string, i: number, pushed = true): AlertItem => ({
  symbol: sym, text: `${sym} 13:${String(10 + i).padStart(2, '0')}:00 — $1.0M buy burst`,
  url: `/sepa/${sym}?tab=tape&from=supply-demand`, pushed,
});

describe('splitAtSymbol', () => {
  it('finds the symbol at the start of a line', () => {
    expect(splitAtSymbol('CRWV 13:17 — x', 'CRWV')).toEqual(['', 'CRWV', ' 13:17 — x']);
  });
  it('finds it after an emoji marker', () => {
    expect(splitAtSymbol('🆕 NVDA · $1', 'NVDA')).toEqual(['🆕 ', 'NVDA', ' · $1']);
  });
  it('escapes the dot in a class share', () => {
    expect(splitAtSymbol('BRK.B $1 · x', 'BRK.B')).toEqual(['', 'BRK.B', ' $1 · x']);
    // NEGATIVE: the dot is literal, not "any character"
    expect(splitAtSymbol('BRKXB $1', 'BRK.B')).toBeNull();
  });
  it('NEGATIVE: ON inside ONTO is not ON', () => {
    expect(splitAtSymbol('ONTO 13:17 — x', 'ON')).toBeNull();
  });
  it('NEGATIVE: case-sensitive — crwv is not CRWV', () => {
    expect(splitAtSymbol('crwv 13:17 — x', 'CRWV')).toBeNull();
  });
});

describe('tabFromUrl', () => {
  it('reads the tab of a /sepa url only', () => {
    expect(tabFromUrl('/sepa/X?tab=tape&from=supply-demand')).toBe('tape');
    expect(tabFromUrl('/chart-maps?tab=support&symbol=X')).toBeNull();
    expect(tabFromUrl(null)).toBeNull();
    expect(tabFromUrl('/sepa/X')).toBeNull();
  });
});

describe('AlertItems render', () => {
  it(`folds above ${ITEMS_FOLD_AT}: 25 items show 20 + "show all 25", then all, then 20 again`, () => {
    const items = Array.from({ length: 25 }, (_, i) => tape(`S${String.fromCharCode(65 + i)}`, i));
    draw(items);
    expect(ITEMS_FOLD_AT).toBe(20);
    expect(screen.getAllByTestId('alert-item')).toHaveLength(20);
    const btn = screen.getByTestId('alert-items-toggle');
    expect(btn.textContent).toBe('show all 25');
    fireEvent.click(btn);
    expect(screen.getAllByTestId('alert-item')).toHaveLength(25);
    expect(btn.textContent).toBe('show fewer');
    fireEvent.click(btn);
    expect(screen.getAllByTestId('alert-item')).toHaveLength(20);
  });

  it('NEGATIVE: 20 items are fully open with no toggle', () => {
    draw(Array.from({ length: 20 }, (_, i) => tape('CRWV', i)));
    expect(screen.getAllByTestId('alert-item')).toHaveLength(20);
    expect(screen.queryByTestId('alert-items-toggle')).toBeNull();
  });

  it('a symbol:null line renders plain text with no link', () => {
    draw([{ symbol: null, text: '+3 more on the board', url: null, pushed: true }, tape('CRWV', 0)]);
    const rows = screen.getAllByTestId('alert-item');
    expect(rows[0].textContent).toBe('+3 more on the board');
    expect(within(rows[0]).queryAllByRole('link')).toHaveLength(0);
  });

  it('links ONLY the symbol, once, even when the line repeats it in lower case', () => {
    draw([{ symbol: 'CRWV', text: 'CRWV 13:17 — crwv again', url: '/sepa/CRWV?tab=tape&from=supply-demand', pushed: true }]);
    const row = screen.getByTestId('alert-item');
    const links = within(row).getAllByRole('link');
    expect(links).toHaveLength(1);
    expect(links[0].textContent).toBe('CRWV');
    expect(links[0].getAttribute('href')).toMatch(/^\/sepa\/CRWV\?tab=tape&from=alerts/);
    expect(row.textContent).toBe('CRWV 13:17 — crwv again');
    expect(screen.getByTestId('alert-item-tk-CRWV')).toBeInTheDocument();
  });

  it('prints the not-stored note', () => {
    draw([tape('CRWV', 0)], 4);
    expect(screen.getByTestId('alert-items-not-stored').textContent).toBe('+4 more not stored in this push');
  });

  it('NEGATIVE: notStored 0 or null renders no note', () => {
    const { unmount } = draw([tape('CRWV', 0)], 0);
    expect(screen.queryByTestId('alert-items-not-stored')).toBeNull();
    unmount();
    draw([tape('CRWV', 0)], null);
    expect(screen.queryByTestId('alert-items-not-stored')).toBeNull();
  });

  it('the off-push divider sits before the first unpushed entry and counts them', () => {
    const { container } = draw([tape('CRWV', 0), tape('KLAC', 1), tape('NVDA', 2, false), tape('AVGO', 3, false)]);
    const div = screen.getByTestId('alert-items-offpush');
    expect(div.textContent).toBe('+2 more not in the notification:');
    const kids = Array.from(container.querySelector('[data-testid="alert-items"]')!.children);
    expect(kids.indexOf(div)).toBe(2);
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('NEGATIVE: no divider when every entry was pushed', () => {
    const { container } = draw([tape('CRWV', 0), tape('KLAC', 1)]);
    expect(screen.queryByTestId('alert-items-offpush')).toBeNull();
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('a non-/sepa internal url links as-is; no url falls back to Supply/Demand', () => {
    draw([
      { symbol: 'PCT', text: 'PCT closed over x', url: '/chart-maps?tab=support&symbol=PCT', pushed: true },
      { symbol: 'NVDA', text: 'NVDA x', url: null, pushed: true },
    ]);
    const [pct, nvda] = screen.getAllByTestId('alert-item');
    expect(within(pct).getByRole('link').getAttribute('href')).toBe('/chart-maps?tab=support&symbol=PCT');
    expect(within(nvda).getByRole('link').getAttribute('href')).toMatch(/^\/sepa\/NVDA\?tab=supply&from=alerts/);
  });
});
