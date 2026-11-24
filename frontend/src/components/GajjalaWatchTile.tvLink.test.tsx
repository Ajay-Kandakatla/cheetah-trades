/* 📺 TV ↗ on the 👀 Watch tile head and the ⤢ view, right BEFORE Yahoo ↗ (2026-11-23). Ajay: "Also add traderview
 * charts on charts please.. Yahoo has been hard to configure" · question card: "TV ↗ button only". A 3-frame tile has
 * no single frame, so NO interval rides (his TradingView opens his last-used interval). NEGATIVES: no interval on the
 * tile or the ⤢ view; Yahoo ↗ still opens Yahoo; exactly one TV ↗ per head; the click never reaches the tile. */
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import fixture from './__fixtures__/gajjala_watch_board_2026_11_15.json';
import { GgwStretch, Tile } from './GajjalaWatchTile';
import { parseGgw, type GgwBoard, type GgwRow } from '../lib/gajjalaWatch';
import { TV_LABEL, tvLinkTestId, tvTitle } from '../lib/tvChart';
import { YAHOO_LABEL, yahooTitle } from '../lib/yahooLink';

const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));
const row = (): GgwRow => (parseGgw(clone(fixture)) as GgwBoard).rows[0];
const S = (fixture as any).rows[0].symbol as string;
type P = Partial<Parameters<typeof Tile>[0]>;
const tile = (p: P = {}) => render(
  <MemoryRouter>
    <Tile row={row()} phone={false} fit={false} removeLabel="Remove" focused={false} busy={false}
          onRemove={() => {}} {...p} />
  </MemoryRouter>);

let open: ReturnType<typeof vi.fn>;
beforeEach(() => { open = vi.fn(); vi.stubGlobal('open', open); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); document.body.style.overflow = ''; });

describe('TV ↗ on the Watch tile head', () => {
  it('right BEFORE Yahoo ↗, same ggw-btn chip, title names TradingView', () => {
    tile({ onStretch: () => {} });
    const tv = screen.getByTestId(tvLinkTestId(S));
    const y = screen.getByRole('button', { name: yahooTitle(S) });
    expect(tv.textContent).toBe(TV_LABEL);
    expect(tv.className).toBe('ggw-btn ggw-tv');
    expect(tv.getAttribute('title')).toBe(tvTitle(S));
    expect(tv.nextElementSibling).toBe(y);
    expect(tv.parentElement!.className).toBe('ggw-actions');
  });

  it('opens his TradingView chart with NO interval, noopener; the click is cancelled and stops the bubble', () => {
    const onClick = vi.fn();
    render(
      <MemoryRouter>
        <div onClick={onClick}>
          <Tile row={row()} phone={false} fit={false} removeLabel="Remove" focused={false} busy={false} />
        </div>
      </MemoryRouter>);
    const tv = screen.getByTestId(tvLinkTestId(S));
    expect(fireEvent.click(tv)).toBe(false);
    expect(onClick).not.toHaveBeenCalled();
    expect(open).toHaveBeenCalledWith(`https://www.tradingview.com/chart/?symbol=${S}`, '_blank', 'noopener,noreferrer');
    expect(String(open.mock.calls[0][0])).not.toContain('interval');
  });

  it('NEGATIVE: exactly one TV ↗ and one Yahoo ↗ per head; Yahoo ↗ still opens Yahoo', () => {
    tile();
    expect(screen.getAllByText(TV_LABEL)).toHaveLength(1);
    expect(screen.getAllByText(YAHOO_LABEL)).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: yahooTitle(S) }));
    expect(open).toHaveBeenCalledWith(`https://finance.yahoo.com/quote/${S}/`, '_blank', 'noopener');
  });

  it('the compact head carries it too, before Yahoo ↗', () => {
    tile({ compact: true, onStretch: () => {} });
    const tv = screen.getByTestId(tvLinkTestId(S));
    expect(tv.nextElementSibling!.textContent).toBe(YAHOO_LABEL);
  });
});

describe('TV ↗ in the ⤢ view', () => {
  it('the stretch head carries TV ↗ before Yahoo ↗; NEGATIVE: no interval there either', () => {
    render(
      <MemoryRouter>
        <GgwStretch row={row()} phone={false} removeLabel="Remove" onClose={() => {}} onStep={() => {}} />
      </MemoryRouter>);
    const tvs = screen.getAllByTestId(tvLinkTestId(S));
    expect(tvs).toHaveLength(1);
    expect(tvs[0].nextElementSibling!.textContent).toBe(YAHOO_LABEL);
    fireEvent.click(tvs[0]);
    expect(open).toHaveBeenCalledWith(`https://www.tradingview.com/chart/?symbol=${S}`, '_blank', 'noopener,noreferrer');
  });
});
