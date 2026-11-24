/* 📺 TV ↗ on every chart tile, right BEFORE Yahoo ↗ (2026-11-23). Ajay: "Also add traderview charts on charts please..
 * Yahoo has been hard to configure" · question card: "TV ↗ button only". The interval is the frame the served
 * tile.href carries; none when it carries no known frame. NEGATIVES: the click never follows the tile link or opens
 * the ⤢ view; Yahoo ↗ still opens Yahoo's quote page; a junk / absent tf → no interval; chartOnly draws neither. */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter, useLocation } from 'react-router-dom';
import { PatternChart } from './PatternChart';
import { _resetSignalWatchlist } from '../hooks/useSignalWatchlist';
import { resetGgwList } from '../lib/ggWatchList';
import { TV_LABEL, tvLinkTestId, tvTitle } from '../lib/tvChart';
import { YAHOO_LABEL, yahooTitle } from '../lib/yahooLink';
import type { CmBar, CmTile } from '../lib/chartMaps';

const bars = (n = 40): CmBar[] => Array.from({ length: n }, (_, i) => {
  const c = 10 + i * 0.1;
  return { t: `2026-07-${String((i % 27) + 1).padStart(2, '0')}`, o: c - 0.1, h: c + 0.3, l: c - 0.4, c, v: 1_000 };
});
const tileOf = (href: string, symbol = 'IONQ'): CmTile => ({
  symbol, name: 'IonQ Inc', href, bars: bars(), bands: [], lines: [], markers: [], stats: [], why: '',
});

let loc = { pathname: '', search: '' };
function Probe() { const l = useLocation(); loc = { pathname: l.pathname, search: l.search }; return null; }
const START = '/chart-maps?tab=gajjala';
const draw = (tile: CmTile, props: Record<string, unknown> = {}) => render(
  <MemoryRouter initialEntries={[START]}>
    <Probe />
    <PatternChart tile={tile} {...props} />
  </MemoryRouter>,
);
let open: ReturnType<typeof vi.fn>;
beforeEach(() => {
  resetGgwList();
  _resetSignalWatchlist();
  vi.stubGlobal('fetch', vi.fn(() => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) })));
  open = vi.fn();
  vi.stubGlobal('open', open);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('TV ↗ on the chart tile', () => {
  it('sits right BEFORE Yahoo ↗ in the action row, same cm-tv chip', () => {
    draw(tileOf('/sepa/IONQ?tab=supply'));
    const tv = screen.getByTestId(tvLinkTestId('IONQ'));
    const y = screen.getByRole('button', { name: yahooTitle('IONQ') });
    expect(tv.textContent).toBe(TV_LABEL);
    expect(tv.className).toBe('cm-tv');
    expect(y.className).toBe('cm-tv');
    expect(tv.getAttribute('aria-label')).toBe(tvTitle('IONQ'));
    expect(tv.nextElementSibling).toBe(y);
    expect(tv.parentElement!.className).toBe('cm-tile-actions');
  });

  it('a served &tf=5m_today / 15m / 1min opens that interval; the click cancels the tile link', () => {
    for (const [tf, iv] of [['5m_today', '5'], ['15m', '15'], ['1min', '1'], ['daily', 'D']]) {
      cleanup();
      open.mockClear();
      draw(tileOf(`/sepa/IONQ?tab=supply&tf=${tf}`));
      const tv = screen.getByTestId(tvLinkTestId('IONQ'));
      expect(fireEvent.click(tv), tf).toBe(false);
      expect(open).toHaveBeenCalledWith(`https://www.tradingview.com/chart/?symbol=IONQ&interval=${iv}`, '_blank', 'noopener,noreferrer');
      expect(loc.pathname + loc.search).toBe(START);
    }
  });

  it('NEGATIVE: an href with no tf, or a junk tf, sends NO interval', () => {
    for (const href of ['/sepa/IONQ?tab=supply', '/sepa/IONQ?tab=supply&tf=5m', '/sepa/IONQ?tab=supply&tf=junk', '']) {
      cleanup();
      open.mockClear();
      draw(tileOf(href));
      fireEvent.click(screen.getByTestId(tvLinkTestId('IONQ')));
      expect(open, href).toHaveBeenCalledWith('https://www.tradingview.com/chart/?symbol=IONQ', '_blank', 'noopener,noreferrer');
      expect(String(open.mock.calls[0][0])).not.toContain('interval');
    }
  });

  it('dash share class → TradingView dot', () => {
    draw(tileOf('/sepa/BRK-B?tab=supply', 'BRK-B'));
    fireEvent.click(screen.getByTestId(tvLinkTestId('BRK-B')));
    expect(open).toHaveBeenCalledWith('https://www.tradingview.com/chart/?symbol=BRK.B', '_blank', 'noopener,noreferrer');
  });

  it('NEGATIVE: TV ↗ never opens the ⤢ view, never navigates the card', () => {
    const fn = vi.fn();
    draw(tileOf('/sepa/IONQ?tab=supply&tf=5m_today'), { onOpenView: fn });
    const tv = screen.getByTestId(tvLinkTestId('IONQ'));
    fireEvent.click(tv);
    expect(fn).not.toHaveBeenCalled();
    expect(open).toHaveBeenCalledTimes(1);
    expect(loc.pathname + loc.search).toBe(START);
  });

  it('NEGATIVE: Yahoo ↗ is unchanged — Yahoo quote page, no tradingview, no interval', () => {
    draw(tileOf('/sepa/IONQ?tab=supply&tf=15m'));
    const y = screen.getByRole('button', { name: yahooTitle('IONQ') });
    expect(y.textContent).toBe(YAHOO_LABEL);
    fireEvent.click(y);
    expect(open).toHaveBeenCalledWith('https://finance.yahoo.com/quote/IONQ/', '_blank', 'noopener');
    expect(String(open.mock.calls[0][0])).not.toContain('tradingview');
  });

  it('NEGATIVE: exactly one TV ↗ per tile; chartOnly draws neither link-out', () => {
    draw(tileOf('/sepa/IONQ?tab=supply'));
    expect(screen.getAllByText(TV_LABEL)).toHaveLength(1);
    cleanup();
    draw(tileOf('/sepa/IONQ?tab=supply'), { chartOnly: true });
    expect(screen.queryByText(TV_LABEL)).toBeNull();
    expect(screen.queryByText(YAHOO_LABEL)).toBeNull();
  });
});
