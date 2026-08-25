/* TickerLink — the href it actually builds.
 *
 * Ajay 2026-08-17: "Take me to the setup tab cirect from chart maps and demand
 * zone page" + the URL he pasted, /sepa/MOS?tab=setup&from=chart-maps.
 *
 * Why these are href assertions and not click assertions: the whole point of
 * this component is that the destination lives in a REAL anchor, so Cmd-click,
 * middle-click and "copy link address" all produce the same page a plain click
 * does. A test that only drove onClick would pass while the three of those
 * silently dropped the tab.
 */
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { TickerLink } from './TickerLink';

vi.mock('./WatchlistButton', () => ({ WatchlistButton: () => null }));
vi.mock('./TickerPrice', () => ({ TickerPrice: () => null }));

const href = (ui: React.ReactElement) => {
  render(<MemoryRouter>{ui}</MemoryRouter>);
  return screen.getByRole('link').getAttribute('href') || '';
};

describe('TickerLink href', () => {
  it('lands on the setup tab and remembers the source page', () => {
    expect(href(<TickerLink ticker="MOS" tab="setup" fromKey="supply-demand" />))
      .toBe('/sepa/MOS?tab=setup&from=supply-demand');
  });

  it('still produces a bare ticker link when neither is asked for', () => {
    // Every pre-existing callsite passes neither — none of them may gain a `?`.
    expect(href(<TickerLink ticker="NVDA" />)).toBe('/sepa/NVDA');
  });

  it('carries the tab even with no source key', () => {
    expect(href(<TickerLink ticker="NVDA" tab="setup" />)).toBe('/sepa/NVDA?tab=setup');
  });

  it('encodes a symbol that would otherwise break the path', () => {
    expect(href(<TickerLink ticker="BRK.B" tab="setup" />))
      .toBe('/sepa/BRK.B?tab=setup');
  });

  // --- negatives ---

  it('drops an unregistered source key rather than writing a dead param', () => {
    // Same rule as withSource: ?from= is only ever written for a key the
    // destination can resolve, so a read of that param is always trustworthy.
    expect(href(<TickerLink ticker="NVDA" tab="setup" fromKey="evil" />))
      .toBe('/sepa/NVDA?tab=setup');
  });

  it('does not write an empty tab param', () => {
    expect(href(<TickerLink ticker="NVDA" tab="" />)).toBe('/sepa/NVDA');
  });

  it('keeps the router state fallback alongside the query params', () => {
    // Belt and braces: state carries a human label the URL registry does not
    // know ("Back in Demand"), and it is what the back button prefers.
    render(
      <MemoryRouter>
        <TickerLink ticker="MOS" tab="setup" fromKey="supply-demand"
                    fromLabel="Back in Demand" />
      </MemoryRouter>,
    );
    expect(screen.getByRole('link')).toHaveAttribute(
      'href', '/sepa/MOS?tab=setup&from=supply-demand');
  });
});

// ── derived ?from= (Ajay 2026-08-24: "back button from supply demand doesnt
//    take me to same page ... it goes to sepa always") ───────────────────────
// A link opened in a fresh tab has no router state and no history, so the
// destination's back button can only read ?from=. It used to be opt-in per
// callsite and most Supply & Demand links forgot it; now it derives from the
// page the link is rendered on.
const hrefAt = (path: string, ui: React.ReactElement) => {
  render(<MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>);
  return screen.getByRole('link').getAttribute('href') || '';
};

describe('TickerLink derived source', () => {
  it('a link rendered on Supply & Demand carries ?from= without being asked', () => {
    expect(hrefAt('/supply-demand', <TickerLink ticker="CR" />))
      .toBe('/sepa/CR?from=supply-demand');
  });

  it('the derived key never overrides an explicit one', () => {
    expect(hrefAt('/supply-demand', <TickerLink ticker="CR" fromKey="chart-maps" />))
      .toBe('/sepa/CR?from=chart-maps');
  });

  it('an unregistered page still produces a bare link', () => {
    // Every page outside the registry keeps its old behaviour exactly.
    expect(hrefAt('/portfolio', <TickerLink ticker="CR" />)).toBe('/sepa/CR');
  });

  it('tab and derived source ride together', () => {
    expect(hrefAt('/demand-zones', <TickerLink ticker="CR" tab="setup" />))
      .toBe('/sepa/CR?tab=setup&from=demand-zones');
  });
});
