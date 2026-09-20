/* TickerChips — every name in a digest push is its own real link.
 *
 * Ajay 2026-09-20: a digest ("AAA, BBB, CCC …") pushed one row that linked at
 * most ONE name. The rest were plain text, so reading the digest meant typing
 * the symbol in by hand.
 *
 * What is pinned here, with negatives, because real money reads these rows:
 *   - each chip is a real <a href="/sepa/SYM?…"> — so ⌘/Ctrl/middle-click is
 *     handled by the BROWSER, not by a handler that could send the wrong URL;
 *   - a ⌘-click does NOT navigate in-app and does NOT call window.open (the
 *     browser default IS the new tab — calling it too would open two);
 *   - a plain click navigates in-app;
 *   - `tab=` and `from=` ride in every href (the destination's back button has
 *     nothing else after a new-tab open);
 *   - the single-ticker fallback, the empty case (renders NOTHING) and
 *     duplicate collapse.
 */
import { describe, it, expect, afterEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router-dom';
import { TickerChips, chipList } from './TickerChips';

function Where() {
  const loc = useLocation();
  return <div data-testid="where">{loc.pathname + loc.search}</div>;
}

/** Rendered on /alerts so `sourceKeyFor` has a page to derive from when the
 *  caller passes no fromKey. */
function draw(ui: React.ReactNode, entry = '/alerts') {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="*" element={<>{ui}<Where /></>} />
      </Routes>
    </MemoryRouter>,
  );
}

const hrefs = (c: HTMLElement) =>
  [...c.querySelectorAll('a')].map((a) => a.getAttribute('href') || '');

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('TickerChips — the list it builds', () => {
  it('three tickers → three real anchors, each /sepa/SYM with the given tab and source', () => {
    const { container } = draw(
      <TickerChips tickers={['AAA', 'BBB', 'CCC']} ticker={null} tab="supply"
                   fromLabel="Alerts" fromKey="alerts" testIdPrefix="alert-tk" />,
    );
    const links = [...container.querySelectorAll('a')];
    expect(links).toHaveLength(3);
    for (const a of links) {
      const href = a.getAttribute('href') || '';
      expect(href).toMatch(/^\/sepa\/(AAA|BBB|CCC)\?/);
      expect(href).toMatch(/tab=supply/);
      expect(href).toMatch(/from=alerts/);
    }
    // Order is the body's order, not sorted.
    expect(links.map((a) => a.textContent)).toEqual(['AAA', 'BBB', 'CCC']);
    // Each chip is addressable by its own symbol.
    for (const t of ['AAA', 'BBB', 'CCC']) {
      expect(screen.getByTestId(`alert-tk-${t}`)).toBeInTheDocument();
    }
  });

  it('tickers empty + a single ticker → exactly one anchor', () => {
    const { container } = draw(
      <TickerChips tickers={[]} ticker="NVDA" fromKey="alerts" testIdPrefix="alert-tk" />,
    );
    expect(hrefs(container)).toHaveLength(1);
    expect(hrefs(container)[0]).toMatch(/^\/sepa\/NVDA\?/);
  });

  it('duplicates collapse and case is normalised — one chip per name', () => {
    const { container } = draw(
      <TickerChips tickers={['AAA', 'aaa', ' AAA ', 'BBB']} fromKey="alerts" />,
    );
    expect(hrefs(container)).toEqual([
      expect.stringMatching(/^\/sepa\/AAA\?/),
      expect.stringMatching(/^\/sepa\/BBB\?/),
    ]);
  });

  it('NEGATIVE: neither tickers nor ticker → renders nothing at all', () => {
    const { container } = draw(<TickerChips tickers={null} ticker={null} testIdPrefix="alert-tk" />);
    expect(container.querySelectorAll('a')).toHaveLength(0);
    expect(screen.queryByTestId('alert-tks')).not.toBeInTheDocument();
  });

  it('NEGATIVE: an all-blank list is the empty case, not a chip with no name', () => {
    const { container } = draw(<TickerChips tickers={['', '   ']} ticker={null} />);
    expect(container.querySelectorAll('a')).toHaveLength(0);
  });

  it('NEGATIVE: chips never nest an anchor inside an anchor', () => {
    const { container } = draw(<TickerChips tickers={['AAA', 'BBB']} fromKey="alerts" />);
    expect(container.querySelectorAll('a a')).toHaveLength(0);
  });

  it('with no fromKey the source is derived from the page the chips are ON', () => {
    const { container } = draw(
      <TickerChips tickers={['AAA']} testIdPrefix="bell-tk" />, '/notifications',
    );
    expect(hrefs(container)[0]).toMatch(/from=notifications/);
  });
});

describe('TickerChips — clicking', () => {
  it('a plain click navigates in-app to /sepa/AAA', () => {
    draw(<TickerChips tickers={['AAA', 'BBB']} fromKey="alerts" testIdPrefix="alert-tk" />);
    expect(screen.getByTestId('where')).toHaveTextContent('/alerts');
    fireEvent.click(screen.getByRole('link', { name: 'AAA' }), { button: 0 });
    expect(screen.getByTestId('where').textContent).toMatch(/^\/sepa\/AAA\?/);
  });

  it('NEGATIVE: a ⌘-click does not navigate in-app and does not call window.open', () => {
    const open = vi.fn();
    vi.stubGlobal('open', open);
    draw(<TickerChips tickers={['AAA', 'BBB']} fromKey="alerts" testIdPrefix="alert-tk" />);
    fireEvent.click(screen.getByRole('link', { name: 'BBB' }), { button: 0, metaKey: true });
    // The router location is untouched — the browser's own default (a new tab)
    // is what opens BBB, and it needs the href, which is why these are <a>s.
    expect(screen.getByTestId('where')).toHaveTextContent('/alerts');
    expect(open).not.toHaveBeenCalled();
    // The href the browser would follow.
    expect(screen.getByRole('link', { name: 'BBB' }).getAttribute('href')).toMatch(/^\/sepa\/BBB\?/);
  });

  it('NEGATIVE: a Ctrl-click is the same — no in-app navigation', () => {
    draw(<TickerChips tickers={['AAA']} fromKey="alerts" />);
    fireEvent.click(screen.getByRole('link', { name: 'AAA' }), { button: 0, ctrlKey: true });
    expect(screen.getByTestId('where')).toHaveTextContent('/alerts');
  });
});

describe('chipList', () => {
  it('prefers the list, falls back to the single, collapses, keeps order', () => {
    expect(chipList(['B', 'A', 'B'], 'Z')).toEqual(['B', 'A']);
    expect(chipList([], 'z')).toEqual(['Z']);
    expect(chipList(null, null)).toEqual([]);
    expect(chipList(undefined, undefined)).toEqual([]);
    // NEGATIVE: a null inside the list is dropped, never rendered as "NULL".
    expect(chipList(['A', null as unknown as string, 'B'], null)).toEqual(['A', 'B']);
  });
});
